"""
S등급 산출 배치 파이프라인.

처리 흐름:
1. s_calculation_request에서 REQUESTED 상태 조회
2. 해당 사용자의 s_input_feature 데이터로 LightGBM 모델 추론
3. SHAP 기반 XAI 설명 생성
4. Gemini LLM으로 자연어 조언 생성
5. 결과를 s_evaluation_history, shap_explanation에 적재
6. s_calculation_request 상태를 COMPLETED로 갱신
"""

import asyncio
import json
import logging
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap

# serving 모듈 재사용을 위해 경로 추가
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "serving"))

from app.core.constants import SGrade
from batch.config import GEMINI_API_KEY, GEMINI_MODEL, MODEL_PATH, SHAP_TOP_N
from batch.db import (
    fetch_requested_calculations,
    get_connection,
    insert_batch_execution,
    insert_evaluation_and_update_latest,
    insert_shap_explanation,
    update_batch_execution,
    update_evaluation_result_id,
    update_request_status,
)

logger = logging.getLogger(__name__)

# 모델 입력에 사용되는 피처 컬럼 (s_input_feature 테이블 순서)
FEATURE_COLUMNS: list[str] = [
    "business_age_months",
    "quarterly_revenue_growth_rate",
    "annual_revenue_growth_rate",
    "revenue_vs_industry_avg_ratio",
    "avg_monthly_transaction_3m",
    "avg_monthly_transaction_6m",
    "avg_monthly_transaction_12m",
    "days_since_last_transaction",
    "max_inactive_days",
    "online_platform_activity_index",
    "revenue_growth_per_employee_3m",
    "revenue_growth_per_employee_6m",
    "revenue_growth_per_employee_12m",
    "revenue_growth_per_business_age_3m",
    "revenue_growth_per_business_age_6m",
    "revenue_growth_per_business_age_12m",
    "online_accessibility_score",
    "is_near_subway",
    "commercial_saturation_score",
    "is_traditional_market",
    "commercial_trend",
    "industry_trend",
    "review_rating",
    "review_count",
    "delivery_rating",
    "delivery_order_count",
    "positive_review_ratio",
    "has_online_reservation",
    "owner_experience_years",
    "employee_count",
    "has_sns",
]

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

# 개선 불가능한 피처 (사업자가 직접 변경할 수 없는 요소)
UNCONTROLLABLE_FEATURES: set[str] = {
    "business_age_months",
    "owner_experience_years",
    "is_traditional_market",
    "is_near_subway",
    "commercial_saturation_score",
    "commercial_trend",
    "industry_trend",
}


def load_model() -> Any:
    """LightGBM 모델 로드."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {MODEL_PATH}")

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    logger.info("모델 로드 완료: %s", MODEL_PATH)
    return model


def prepare_features(row: dict[str, Any]) -> pd.DataFrame:
    """DB 조회 결과 row에서 모델 입력용 DataFrame을 생성."""
    features = {col: row[col] for col in FEATURE_COLUMNS}
    df = pd.DataFrame([features])

    # bool 컬럼 → int (DB에서 TINYINT로 오지만 명시적 변환)
    bool_cols = [
        "is_near_subway", "is_traditional_market",
        "has_online_reservation", "has_sns",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(int)

    # categorical 컬럼 타입 변환 (학습 시 category로 지정된 컬럼)
    # LightGBM predict_proba는 category 타입을 기대함
    categorical_cols = ["commercial_trend", "industry_trend"]
    for col in categorical_cols:
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df


def predict_grade(model: Any, input_df: pd.DataFrame) -> tuple[SGrade, float]:
    """모델 추론 → S등급 + 원점수 반환."""
    probabilities = model.predict_proba(input_df)
    predicted_index = int(np.argmax(probabilities[0]))
    score = float(probabilities[0][predicted_index])
    s_grade = SGrade.from_index(predicted_index)
    return s_grade, score


def get_target_grade(s_grade: SGrade) -> SGrade:
    """한 단계 위 등급 반환. S1이면 S1 유지."""
    current_index = s_grade.to_index()
    if current_index == 0:
        return SGrade.S1
    return SGrade.from_index(current_index - 1)


def compute_shap(
    model: Any,
    input_df: pd.DataFrame,
    target_class: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    SHAP 값 계산 → 강점/개선 포인트 Top-N 반환.

    Returns:
        (strengths, improvements): 각각 {feature_name, shap_value, feature_value} 리스트
    """
    # SHAP TreeExplainer는 수치형만 허용하므로 category → 정수 코드로 변환
    shap_df = input_df.copy()
    categorical_cols = ["commercial_trend", "industry_trend"]
    for col in categorical_cols:
        if col in shap_df.columns and shap_df[col].dtype.name == "category":
            shap_df[col] = shap_df[col].cat.codes.astype(int)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(shap_df)

    # 다중 클래스: shap_values는 리스트 [클래스0, ..., 클래스9]
    if isinstance(shap_values, list):
        combined = shap_values[target_class][0]
    elif shap_values.ndim == 3:
        combined = shap_values[0, :, target_class]
    else:
        combined = shap_values[0]

    feature_names = FEATURE_COLUMNS
    feature_values = input_df.iloc[0].to_dict()

    # 강점 (양수, 큰 순)
    positive_indices = np.where(combined > 0)[0]
    positive_sorted = positive_indices[np.argsort(combined[positive_indices])[::-1]]
    strengths = []
    for idx in positive_sorted[:SHAP_TOP_N]:
        name = feature_names[idx]
        strengths.append({
            "feature_name": name,
            "shap_value": round(float(combined[idx]), 6),
            "feature_value": feature_values.get(name),
        })

    # 개선 포인트 (음수, 절댓값 큰 순)
    negative_indices = np.where(combined < 0)[0]
    negative_sorted = negative_indices[np.argsort(np.abs(combined[negative_indices]))[::-1]]
    improvements = []
    for idx in negative_sorted[:SHAP_TOP_N]:
        name = feature_names[idx]
        improvements.append({
            "feature_name": name,
            "shap_value": round(float(combined[idx]), 6),
            "feature_value": feature_values.get(name),
        })

    return strengths, improvements


def extract_keywords(
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """강점/개선 포인트에서 한국어 키워드 3개씩 추출."""
    strength_keywords = [
        FEATURE_NAMES_KR.get(f["feature_name"], f["feature_name"])
        for f in strengths[:3]
    ]

    # 개선 포인트: 개선 불가 요소 제외 후 상위 3개
    controllable = [f for f in improvements if f["feature_name"] not in UNCONTROLLABLE_FEATURES]
    improvement_keywords = [
        FEATURE_NAMES_KR.get(f["feature_name"], f["feature_name"])
        for f in controllable[:3]
    ]

    return strength_keywords, improvement_keywords


def extract_details(
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, float]]:
    """강점/개선 포인트 각 5개를 {한국어명: SHAP값} 형태로 반환."""
    strength_details = {
        FEATURE_NAMES_KR.get(f["feature_name"], f["feature_name"]): f["shap_value"]
        for f in strengths[:5]
    }
    improvement_details = {
        FEATURE_NAMES_KR.get(f["feature_name"], f["feature_name"]): f["shap_value"]
        for f in improvements[:5]
    }
    return strength_details, improvement_details


async def generate_advice(
    s_grade: str,
    target_grade: str,
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> str:
    """Gemini LLM으로 자연어 조언 생성."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY 미설정 — 조언 생성 건너뜀")
        return ""

    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    # 개선 불가 요소 제외
    controllable_improvements = [
        f for f in improvements if f["feature_name"] not in UNCONTROLLABLE_FEATURES
    ][:2]
    top_strengths = strengths[:2]

    # S1인 경우 개선 조언 불필요
    if s_grade == "S1":
        prompt = _build_s1_prompt(s_grade, top_strengths)
    else:
        prompt = _build_prompt(s_grade, target_grade, top_strengths, controllable_improvements)

    try:
        response = await model.generate_content_async(prompt)
        advice = response.text.strip()
        logger.info("조언 생성 완료 (user grade: %s, %d자)", s_grade, len(advice))
        return advice
    except Exception as e:
        logger.error("Gemini 호출 실패: %s", str(e))
        return f"조언 생성 중 오류 발생: {str(e)}"


def _build_prompt(
    s_grade: str,
    target_grade: str,
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> str:
    """일반 등급용 LLM 프롬프트."""
    strengths_text = ""
    for feat in strengths:
        kr_name = FEATURE_NAMES_KR.get(feat["feature_name"], feat["feature_name"])
        strengths_text += f"• {kr_name}: 현재 값 {feat['feature_value']} (기여도: {feat['shap_value']:+.4f})\n"

    improvements_text = ""
    for feat in improvements:
        kr_name = FEATURE_NAMES_KR.get(feat["feature_name"], feat["feature_name"])
        improvements_text += f"• {kr_name}: 현재 값 {feat['feature_value']} (기여도: {feat['shap_value']:+.4f})\n"

    return f"""당신은 소상공인 금융 컨설턴트입니다.
아래 분석 결과를 바탕으로 소상공인에게 성장 등급을 올리기 위한 조언을 작성해주세요.

[현재 상황]
- 현재 성장 등급: {s_grade} (S1이 최고, S10이 최저)
- 목표 등급: {target_grade}

[잘하고 있는 점 (강점)]
{strengths_text if strengths_text else "• 해당 없음"}

[개선이 필요한 점]
{improvements_text if improvements_text else "• 해당 없음"}

[작성 규칙]
1. 아래 형식을 반드시 따라 작성하세요:
   • 첫 문장: 강점을 격려하는 말 (1문장)
   • 둘째~셋째 문장: 개선 포인트별 구체적이고 실행 가능한 조언 (각 1문장)
   • 마지막 문장: 종합 격려 (1문장)
2. 전문 용어 없이 소상공인이 이해할 수 있는 쉬운 말로 작성
3. 전체 3~5문장, 각 문장은 bullet(•)로 시작
4. 한국어로 작성
5. '-해요'체로 친근하게 작성
6. 목표하는 등급을 언급하지 않기
"""


def _build_s1_prompt(s_grade: str, strengths: list[dict[str, Any]]) -> str:
    """S1 등급용 LLM 프롬프트 (개선 조언 없이 강점 유지 조언만)."""
    strengths_text = ""
    for feat in strengths:
        kr_name = FEATURE_NAMES_KR.get(feat["feature_name"], feat["feature_name"])
        strengths_text += f"• {kr_name}: 현재 값 {feat['feature_value']} (기여도: {feat['shap_value']:+.4f})\n"

    return f"""당신은 소상공인 금융 컨설턴트입니다.
이 사업자는 최고 등급(S1)을 달성했습니다. 현재 강점을 유지하도록 격려하는 조언을 작성해주세요.

[현재 상황]
- 현재 성장 등급: {s_grade} (최고 등급)

[잘하고 있는 점 (강점)]
{strengths_text}

[작성 규칙]
1. 최고 등급 달성을 축하하고 현재 강점을 유지하도록 격려
2. 전문 용어 없이 소상공인이 이해할 수 있는 쉬운 말로 작성
3. 전체 2~3문장, 각 문장은 bullet(•)로 시작
4. 한국어로 작성
5. '-해요'체로 친근하게 작성
"""


async def process_single_request(
    model: Any,
    row: dict[str, Any],
    batch_execution_id: int,
    conn: Any,
) -> None:
    """단일 산출 요청 처리 (추론 → SHAP → 조언 → DB 적재)."""
    request_id = row["request_id"]
    user_id = row["target_user_id"]
    biz_data_id = row["biz_data_id"]

    logger.info("처리 시작: request_id=%d, user_id=%d", request_id, user_id)

    # 1. 요청 상태 → IN_PROGRESS
    update_request_status(conn, request_id, "IN_PROGRESS")
    conn.commit()

    # 2. 피처 준비 및 모델 추론
    input_df = prepare_features(row)
    s_grade, score = predict_grade(model, input_df)
    target_grade = get_target_grade(s_grade)

    logger.info(
        "추론 완료: user_id=%d, grade=%s, score=%.4f, target=%s",
        user_id, s_grade.value, score, target_grade.value,
    )

    # 3. SHAP 계산
    target_class = target_grade.to_index()
    strengths, improvements = compute_shap(model, input_df, target_class)

    # 4. 키워드 및 상세 추출
    strength_keywords, improvement_keywords = extract_keywords(strengths, improvements)
    strength_details, improvement_details = extract_details(strengths, improvements)

    # S1인 경우 개선점 비우기
    if s_grade == SGrade.S1:
        improvement_keywords = []
        improvement_details = {}

    # 5. LLM 조언 생성
    advice = await generate_advice(
        s_grade.value, target_grade.value, strengths, improvements
    )

    # 6. DB 적재 (트랜잭션)
    # 6-1. s_evaluation_history 삽입 + is_latest 갱신
    evaluation_id = insert_evaluation_and_update_latest(
        conn, user_id, biz_data_id, batch_execution_id, s_grade.value, score
    )

    # 6-2. shap_explanation 삽입
    result_id = insert_shap_explanation(
        conn,
        evaluation_id=evaluation_id,
        user_id=user_id,
        s_grade=s_grade.value,
        target_grade=target_grade.value,
        strength_keywords=json.dumps(strength_keywords, ensure_ascii=False),
        improvement_keywords=json.dumps(improvement_keywords, ensure_ascii=False),
        strength_details=json.dumps(strength_details, ensure_ascii=False),
        improvement_details=json.dumps(improvement_details, ensure_ascii=False),
        advice=advice,
    )

    # 6-3. evaluation에 result_id 연결
    update_evaluation_result_id(conn, evaluation_id, result_id)

    # 6-4. 요청 상태 → COMPLETED
    update_request_status(conn, request_id, "COMPLETED", s_evaluation_id=evaluation_id)

    # 커밋 (건별 커밋으로 부분 실패 시 이미 처리된 건 보존)
    conn.commit()

    logger.info(
        "처리 완료: request_id=%d, user_id=%d, grade=%s, evaluation_id=%d",
        request_id, user_id, s_grade.value, evaluation_id,
    )


async def run_batch() -> None:
    """배치 메인 실행 함수."""
    logger.info("=" * 60)
    logger.info("S등급 산출 배치 시작")
    logger.info("=" * 60)

    # 모델 로드
    model = load_model()

    with get_connection() as conn:
        # REQUESTED 상태 조회
        requests = fetch_requested_calculations(conn)

        if not requests:
            logger.info("처리할 요청이 없습니다. 배치 종료.")
            return

        # 배치 실행 이력 생성
        batch_execution_id = insert_batch_execution(
            conn,
            execution_type="AUTO",
            execution_cycle="DAILY",
            total_count=len(requests),
        )
        logger.info("배치 실행 ID: %d, 대상 건수: %d", batch_execution_id, len(requests))

        success_count = 0
        fail_count = 0
        last_error = None

        for row in requests:
            try:
                await process_single_request(model, row, batch_execution_id, conn)
                success_count += 1
            except Exception as e:
                fail_count += 1
                last_error = str(e)
                logger.error(
                    "처리 실패: request_id=%d, error=%s",
                    row["request_id"], str(e),
                    exc_info=True,
                )
                # 실패한 건은 롤백
                conn.rollback()

        # 배치 실행 이력 업데이트
        final_status = "COMPLETED" if fail_count == 0 else "FAILED"
        update_batch_execution(
            conn, batch_execution_id, final_status, success_count, fail_count, last_error
        )

        logger.info("-" * 60)
        logger.info(
            "배치 완료: 성공=%d, 실패=%d, 상태=%s",
            success_count, fail_count, final_status,
        )
        logger.info("=" * 60)
