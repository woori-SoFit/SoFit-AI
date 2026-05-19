"""
SoFit AI - Gemini LLM 기반 자연어 조언 생성 모듈

[역할]
- SHAP 분석 결과(강점/개선 포인트)를 Gemini LLM에 전달
- 소상공인이 이해할 수 있는 자연어 조언으로 변환
- 강점 2개 + 개선 포인트 2개 기반 조언 생성

[개선 불가 요소 필터링]
- 업력(business_age_months), 경영주 경력(owner_experience_years),
  전통시장 여부(is_traditional_market), 역세권 여부(is_near_subway) 등
  사업자가 직접 개선하기 어려운 요소는 조언 대상에서 제외
"""

import logging
from typing import Any

import google.generativeai as genai

from app.core.config import settings
from schemas import ShapFeature

logger = logging.getLogger(__name__)

# 개선 불가능한 피처 목록 (사업자가 직접 변경할 수 없는 요소)
UNCONTROLLABLE_FEATURES: set[str] = {
    "business_age_months",           # 업력
    "owner_experience_years",        # 경영주 동업종 경력
    "is_traditional_market",         # 전통시장 여부
    "is_near_subway",                # 역세권 여부
    "commercial_saturation_score",   # 상권 포화도
    "commercial_trend",              # 상권 트렌드
    "industry_trend",                # 업종 트렌드
}

# 피처명 → 한국어 설명 매핑
FEATURE_NAMES_KR: dict[str, str] = {
    "business_age_months": "업력(개월)",
    "quarterly_revenue_growth_rate": "분기별 매출 증가율",
    "annual_revenue_growth_rate": "연간 매출 증가율",
    "revenue_vs_industry_avg_ratio": "업종 평균 대비 매출 비율",
    "avg_monthly_transaction_3m": "최근 3개월 평균 거래금액",
    "avg_monthly_transaction_6m": "최근 6개월 평균 거래금액",
    "avg_monthly_transaction_12m": "최근 12개월 평균 거래금액",
    "days_since_last_transaction": "최종 결제일로부터 경과일",
    "max_inactive_days": "최장 영업 부재기간",
    "online_platform_activity_index": "온라인 플랫폼 활동 지수",
    "revenue_growth_per_employee_3m": "직원당 매출증가율(3개월)",
    "revenue_growth_per_employee_6m": "직원당 매출증가율(6개월)",
    "revenue_growth_per_employee_12m": "직원당 매출증가율(12개월)",
    "revenue_growth_per_business_age_3m": "업력 대비 매출증가율(3개월)",
    "revenue_growth_per_business_age_6m": "업력 대비 매출증가율(6개월)",
    "revenue_growth_per_business_age_12m": "업력 대비 매출증가율(12개월)",
    "online_accessibility_score": "온라인 정보 접근성 점수",
    "is_near_subway": "역세권 여부",
    "commercial_saturation_score": "상권 포화도",
    "is_traditional_market": "전통시장 여부",
    "commercial_trend": "상권 트렌드",
    "industry_trend": "업종 트렌드",
    "review_rating": "리뷰 평점",
    "review_count": "리뷰 수",
    "delivery_rating": "배달앱 평점",
    "delivery_order_count": "배달앱 주문 수",
    "positive_review_ratio": "긍정 리뷰 비율",
    "has_online_reservation": "온라인 예약 여부",
    "owner_experience_years": "경영주 동업종 경력(년)",
    "employee_count": "직원 수",
    "has_sns": "SNS 운영 여부",
}


class Advisor:
    """Gemini LLM을 활용한 자연어 조언 생성기."""

    def __init__(self) -> None:
        self._model: Any = None
        self._is_ready: bool = False

    def setup(self) -> None:
        """Gemini API 초기화."""
        if not settings.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY가 설정되지 않았습니다. 자연어 조언 생성 불가."
            )
            return

        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(settings.gemini_model)
        self._is_ready = True
        logger.info("Gemini Advisor 초기화 완료 (모델: %s)", settings.gemini_model)

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    def _filter_controllable(
        self, features: list[ShapFeature], top_n: int = 2
    ) -> list[ShapFeature]:
        """개선 불가능한 피처를 제외하고 상위 N개 반환."""
        controllable = [f for f in features if f.feature_name not in UNCONTROLLABLE_FEATURES]
        return controllable[:top_n]

    def get_keywords(
        self,
        strengths: list[ShapFeature],
        improvements: list[ShapFeature],
    ) -> tuple[list[str], list[str]]:
        """
        강점/개선 포인트에서 한국어 키워드 3개씩 추출.
        개선 포인트는 개선 불가 요소를 제외한 후 추출.

        Returns:
            (strength_keywords, improvement_keywords): 각 3개 한국어 키워드 리스트
        """
        # 강점 상위 3개 한국어 키워드
        strength_keywords = []
        for feat in strengths[:3]:
            kr_name = FEATURE_NAMES_KR.get(feat.feature_name, feat.feature_name)
            strength_keywords.append(kr_name)

        # 개선 포인트: 개선 불가 요소 제외 후 상위 3개
        controllable_improvements = [
            f for f in improvements if f.feature_name not in UNCONTROLLABLE_FEATURES
        ]
        improvement_keywords = []
        for feat in controllable_improvements[:3]:
            kr_name = FEATURE_NAMES_KR.get(feat.feature_name, feat.feature_name)
            improvement_keywords.append(kr_name)

        return strength_keywords, improvement_keywords

    async def generate_advice(
        self,
        s_grade: str,
        target_grade: str,
        strengths: list[ShapFeature],
        improvements: list[ShapFeature],
    ) -> str:
        """
        SHAP 결과를 기반으로 자연어 조언을 생성.

        Args:
            s_grade: 현재 예측 등급 (예: "S7")
            target_grade: 목표 등급 (예: "S6")
            strengths: 강점 피처 목록
            improvements: 개선 포인트 피처 목록

        Returns:
            자연어 조언 문자열
        """
        if not self._is_ready:
            return "자연어 조언 생성이 불가합니다. (Gemini API 미설정)"

        # 강점 상위 2개
        top_strengths = self._filter_controllable(strengths, top_n=2)
        # 개선 포인트 상위 2개 (개선 불가 요소 제외)
        top_improvements = self._filter_controllable(improvements, top_n=2)

        # 프롬프트 구성
        prompt = self._build_prompt(s_grade, target_grade, top_strengths, top_improvements)

        try:
            response = await self._model.generate_content_async(prompt)
            advice = response.text.strip()
            logger.info("자연어 조언 생성 완료 (%d자)", len(advice))
            return advice
        except Exception as e:
            logger.error("Gemini 호출 실패: %s", str(e))
            return f"조언 생성 중 오류가 발생했습니다: {str(e)}"

    def _build_prompt(
        self,
        s_grade: str,
        target_grade: str,
        strengths: list[ShapFeature],
        improvements: list[ShapFeature],
    ) -> str:
        """LLM 프롬프트 구성."""

        strengths_text = ""
        for feat in strengths:
            kr_name = FEATURE_NAMES_KR.get(feat.feature_name, feat.feature_name)
            strengths_text += f"  - {kr_name}: 현재 값 {feat.feature_value} (기여도: {feat.shap_value:+.4f})\n"

        improvements_text = ""
        for feat in improvements:
            kr_name = FEATURE_NAMES_KR.get(feat.feature_name, feat.feature_name)
            improvements_text += f"  - {kr_name}: 현재 값 {feat.feature_value} (기여도: {feat.shap_value:+.4f})\n"

        prompt = f"""당신은 소상공인 금융 컨설턴트입니다.
아래 분석 결과를 바탕으로 소상공인에게 성장 등급을 올리기 위한 조언을 작성해주세요.

[현재 상황]
- 현재 성장 등급: {s_grade} (S1이 최고, S10이 최저)
- 목표 등급: {target_grade}

[잘하고 있는 점 (강점)]
{strengths_text if strengths_text else "  - 해당 없음"}

[개선이 필요한 점]
{improvements_text if improvements_text else "  - 해당 없음"}

[작성 규칙]
1. 강점은 격려하며 유지하도록 조언
2. 개선 포인트는 구체적이고 실행 가능한 방법을 제안
3. 전문 용어 없이 소상공인이 이해할 수 있는 쉬운 말로 작성
4. 전체 3~5문장으로 간결하게 작성
5. 한국어로 작성
6. '-해요'체로 친근하게 작성
"""
        return prompt
