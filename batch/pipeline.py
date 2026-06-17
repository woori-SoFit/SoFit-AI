"""
S등급 산출 배치 파이프라인.

처리 흐름 (월별 배치):
1. 전체 사용자의 최신 s_grade_feature 데이터 조회 (biz_data_id → my_biz_data.business_number 기준)
2. 해당 사용자의 s_grade_feature 데이터로 LightGBM 모델 추론
3. SHAP 기반 XAI 설명 생성
4. Gemini LLM으로 자연어 조언 생성 (user_advice + admin_advice)
5. 결과를 s_grade_report에 적재
6. s_grade_history 상태를 COMPLETED로 갱신 + evaluated_at 기록

[건별 산출]
- 건별 S등급 산출은 FastAPI 서빙 서버에서 처리 (일일 배치 제거됨)

[재시도 전략]
- 배치 내부 메모리에서 최대 3회 즉시 재시도
- 3회 실패 → FAILED 처리
- 배치 시작 시 CALCULATING 고아 건을 REQUESTED로 1회 복구 (이전 배치 비정상 종료 대응)
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

# serving 모듈 재사용을 위해 경로 추가
# 로컬: batch/ → parent.parent = repo root, serving 디렉토리 추가
# Docker: /app/batch/ → parent.parent = /, /app에 serving 소스가 이미 존재
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_serving_path = _PROJECT_ROOT / "serving"
if _serving_path.exists():
    sys.path.insert(0, str(_serving_path))
# Docker 환경에서는 /app이 WORKDIR이므로 별도 추가 불필요 (uvicorn이 /app을 sys.path에 포함)

from app.core.constants import SGrade
from batch.config import GEMINI_API_KEY, GEMINI_MODEL, MODEL_PATH, SHAP_TOP_N, GEMINI_API_DELAY_SEC, GEMINI_API_RETRY_DELAY_SEC
from batch.db import (
    STATUS_CALCULATING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_REQUESTED,
    complete_grade_history,
    complete_requested_for_user,
    fail_grade_history,
    fetch_all_latest_features,
    get_connection,
    insert_batch_execution,
    insert_grade_history,
    insert_grade_report,
    recover_orphaned_calculating,
    update_batch_execution,
    update_grade_history_status,
)

logger = logging.getLogger(__name__)

# 최대 재시도 횟수 (배치 내부 메모리에서 관리)
MAX_RETRY_COUNT: int = 3

# 모델 입력에 사용되는 피처 컬럼 (s_grade_feature 테이블 순서)
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

    # DECIMAL 컬럼 → float 변환 (PyMySQL이 Decimal 객체로 반환하므로)
    decimal_cols = [
        "quarterly_revenue_growth_rate", "annual_revenue_growth_rate",
        "revenue_vs_industry_avg_ratio",
        "avg_monthly_transaction_3m", "avg_monthly_transaction_6m", "avg_monthly_transaction_12m",
        "online_platform_activity_index",
        "revenue_growth_per_employee_3m", "revenue_growth_per_employee_6m", "revenue_growth_per_employee_12m",
        "revenue_growth_per_business_age_3m", "revenue_growth_per_business_age_6m", "revenue_growth_per_business_age_12m",
        "online_accessibility_score", "commercial_saturation_score",
        "review_rating", "delivery_rating", "positive_review_ratio",
    ]
    for col in decimal_cols:
        if col in df.columns:
            df[col] = df[col].astype(float)

    # INT 컬럼 명시적 변환 (혹시 object로 들어올 경우 대비)
    int_cols = [
        "business_age_months", "days_since_last_transaction", "max_inactive_days",
        "review_count", "delivery_order_count", "owner_experience_years", "employee_count",
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].astype(int)

    # bool 컬럼 → int (DB에서 TINYINT로 오지만 명시적 변환)
    bool_cols = [
        "is_near_subway", "is_traditional_market",
        "has_online_reservation", "has_sns",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(int)

    # categorical 컬럼 타입 변환 (학습 시 category로 지정된 컬럼)
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
    LightGBM 네이티브 pred_contrib를 사용하여 category 타입 호환 문제를 우회.

    Returns:
        (strengths, improvements): 각각 {feature_name, shap_value, feature_value} 리스트
    """
    booster = model.booster_
    n_features = len(FEATURE_COLUMNS)
    n_classes = 10  # S1~S10

    contrib = booster.predict(input_df, pred_contrib=True)
    contrib = contrib.reshape(1, n_classes, n_features + 1)
    # target_class의 SHAP 값 추출 (bias 제외)
    combined = contrib[0, target_class, :n_features]

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


async def generate_user_advice(
    s_grade: str,
    target_grade: str,
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> str:
    """Gemini LLM으로 유저 전용 자연어 조언 생성."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY 미설정 — 유저 조언 생성 건너뜀")
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
        prompt = _build_s1_user_prompt(s_grade, top_strengths)
    else:
        prompt = _build_user_prompt(s_grade, target_grade, top_strengths, controllable_improvements)

    try:
        response = await model.generate_content_async(prompt)
        advice = response.text.strip()
        logger.info("유저 조언 생성 완료 (grade: %s, %d자)", s_grade, len(advice))
        return advice
    except Exception as e:
        logger.error("Gemini 호출 실패 (유저 조언): %s", str(e))
        return ""


async def generate_admin_advice(
    s_grade: str,
    target_grade: str,
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> str:
    """Gemini LLM으로 은행원 전용 분석 텍스트 생성."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY 미설정 — 은행원 조언 생성 건너뜀")
        return ""

    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = _build_admin_prompt(s_grade, target_grade, strengths, improvements)

    try:
        response = await model.generate_content_async(prompt)
        advice = response.text.strip()
        logger.info("은행원 조언 생성 완료 (grade: %s, %d자)", s_grade, len(advice))
        return advice
    except Exception as e:
        logger.error("Gemini 호출 실패 (은행원 조언): %s", str(e))
        return ""


def _build_user_prompt(
    s_grade: str,
    target_grade: str,
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> str:
    """일반 등급용 유저 LLM 프롬프트."""
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
3. 전체 4문장. 각 문장마다 줄바꿈하여 저장.
4. 한국어로 작성
5. '-해요'체로 친근하게 작성
6. 목표하는 등급을 언급하지 않기
"""


def _build_s1_user_prompt(s_grade: str, strengths: list[dict[str, Any]]) -> str:
    """S1 등급용 유저 LLM 프롬프트 (개선 조언 없이 강점 유지 조언만)."""
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
3. 전체 4문장. 각 문장마다 줄바꿈하여 저장.
4. 한국어로 작성
5. '-해요'체로 친근하게 작성
"""


def _build_admin_prompt(
    s_grade: str,
    target_grade: str,
    strengths: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
) -> str:
    """은행원 전용 LLM 프롬프트 (심사 참고용 분석 텍스트)."""
    strengths_text = ""
    for feat in strengths:
        kr_name = FEATURE_NAMES_KR.get(feat["feature_name"], feat["feature_name"])
        strengths_text += f"• {kr_name}: 현재 값 {feat['feature_value']} (SHAP 기여도: {feat['shap_value']:+.6f})\n"

    improvements_text = ""
    for feat in improvements:
        kr_name = FEATURE_NAMES_KR.get(feat["feature_name"], feat["feature_name"])
        improvements_text += f"• {kr_name}: 현재 값 {feat['feature_value']} (SHAP 기여도: {feat['shap_value']:+.6f})\n"

    return f"""당신은 은행 대출 심사를 보조하는 AI 분석가입니다.
아래 소상공인의 성장 S등급 산출 근거를 은행원이 심사에 참고할 수 있도록 요약해주세요.

[산출 결과]
- 성장 등급: {s_grade} (S1 최고 ~ S10 최저)
- 목표 등급: {target_grade}

[긍정 기여 요인 (강점)]
{strengths_text if strengths_text else "• 해당 없음"}

[부정 기여 요인 (약점)]
{improvements_text if improvements_text else "• 해당 없음"}

[작성 규칙]
1. 객관적이고 간결한 분석 톤으로 작성 (경어 사용)
2. 전체 4문장으로 핵심 요약. 각 문장마다 줄바꿈하여 저장. 
3. 강점과 리스크 요인을 균형 있게 기술
4. 한국어로 작성
5. 사업자 성장 가능성에 대한 종합 판단 포함
"""


async def process_single_user(
    model: Any,
    row: dict[str, Any],
    s_grade_id: int,
    batch_execution_id: int,
    conn: Any,
) -> None:
    """
    월별 배치용: 단일 사용자 처리 (추론 → SHAP → 조언 → DB 적재).
    s_grade_id는 호출자(run_monthly_batch)가 재시도 루프 바깥에서 생성하여 전달한다.
    """
    user_id = row["user_id"]
    feature_id = row["feature_id"]

    logger.info("월별 처리 시작: user_id=%d, s_grade_id=%d", user_id, s_grade_id)

    # 상태 → CALCULATING
    update_grade_history_status(conn, s_grade_id, STATUS_CALCULATING)
    conn.commit()

    # 1. 피처 준비 및 모델 추론
    input_df = prepare_features(row)
    s_grade, score = predict_grade(model, input_df)
    target_grade = get_target_grade(s_grade)

    logger.info(
        "추론 완료: user_id=%d, grade=%s, score=%.4f, target=%s",
        user_id, s_grade.value, score, target_grade.value,
    )

    # 2. SHAP 계산
    target_class = target_grade.to_index()
    strengths, improvements = compute_shap(model, input_df, target_class)

    # 3. 키워드 및 상세 추출
    strength_keywords, improvement_keywords = extract_keywords(strengths, improvements)
    strength_details, improvement_details = extract_details(strengths, improvements)

    # S1인 경우 개선점 비우기
    if s_grade == SGrade.S1:
        improvement_keywords = []
        improvement_details = {}

    # 4. LLM 조언 생성 (유저용 + 은행원용)
    user_advice = await generate_user_advice(
        s_grade.value, target_grade.value, strengths, improvements
    )
    # Gemini API rate limit 방지용 딜레이
    await asyncio.sleep(GEMINI_API_DELAY_SEC)
    admin_advice = await generate_admin_advice(
        s_grade.value, target_grade.value, strengths, improvements
    )

    # 5. DB 적재
    insert_grade_report(
        conn,
        s_grade_id=s_grade_id,
        user_id=user_id,
        feature_id=feature_id,
        s_grade=s_grade.value,
        target_grade=target_grade.value,
        strength_keywords=json.dumps(strength_keywords, ensure_ascii=False),
        improvement_keywords=json.dumps(improvement_keywords, ensure_ascii=False),
        strength_details=json.dumps(strength_details, ensure_ascii=False),
        improvement_details=json.dumps(improvement_details, ensure_ascii=False),
        user_advice=user_advice,
        admin_advice=admin_advice,
    )

    # s_grade_history → COMPLETED + evaluated_at
    complete_grade_history(conn, s_grade_id)

    # 해당 사용자의 기존 REQUESTED 건도 함께 COMPLETED 처리
    completed_requests = complete_requested_for_user(conn, user_id)
    if completed_requests > 0:
        logger.info(
            "user_id=%d의 기존 REQUESTED 요청 %d건 함께 완료 처리",
            user_id, completed_requests,
        )

    # 건별 커밋
    conn.commit()

    logger.info(
        "월별 처리 완료: user_id=%d, grade=%s, s_grade_id=%d",
        user_id, s_grade.value, s_grade_id,
    )


async def run_monthly_batch(
    execution_type: str = "AUTO",
    triggered_by: int | None = None,
) -> None:
    """월별 배치 메인 실행 함수 (MONTHLY). 전체 사용자 등급 갱신."""
    logger.info("=" * 60)
    logger.info("S등급 산출 월별 배치 시작 (MONTHLY, type=%s)", execution_type)
    logger.info("=" * 60)

    # 모델 로드
    model = load_model()

    with get_connection() as conn:
        # 고아 건 복구 (이전 배치 비정상 종료 대응)
        recover_orphaned_calculating(conn)
        conn.commit()

        # 전체 사용자의 최신 피처 조회
        all_features = fetch_all_latest_features(conn)

        if not all_features:
            logger.info("처리할 사용자가 없습니다. 배치 종료.")
            return

        # 배치 실행 이력 생성
        batch_execution_id = insert_batch_execution(
            conn,
            execution_type=execution_type,
            execution_cycle="MONTHLY",
            total_count=len(all_features),
            triggered_by=triggered_by,
        )
        conn.commit()
        logger.info("배치 실행 ID: %d, 대상 건수: %d", batch_execution_id, len(all_features))

        success_count = 0
        fail_count = 0
        last_error = None

        for row in all_features:
            user_id = row["user_id"]
            feature_id = row["feature_id"]

            # s_grade_history 신규 생성 — 재시도 루프 바깥에서 1회만 수행
            s_grade_id = insert_grade_history(conn, user_id, feature_id, batch_execution_id)
            conn.commit()

            retry_count = 0
            success = False

            while retry_count < MAX_RETRY_COUNT and not success:
                try:
                    await process_single_user(model, row, s_grade_id, batch_execution_id, conn)
                    success = True
                    success_count += 1
                    # Gemini API rate limit 방지: 다음 사용자 처리 전 딜레이
                    await asyncio.sleep(GEMINI_API_DELAY_SEC)
                except Exception as e:
                    retry_count += 1
                    conn.rollback()
                    logger.error(
                        "월별 처리 실패 (시도 %d/%d): user_id=%d, error=%s",
                        retry_count, MAX_RETRY_COUNT, user_id, str(e),
                        exc_info=True,
                    )
                    # 재시도 전 딜레이 (rate limit 회피를 위해 더 긴 대기)
                    await asyncio.sleep(GEMINI_API_RETRY_DELAY_SEC)

                    if retry_count >= MAX_RETRY_COUNT:
                        fail_count += 1
                        last_error = str(e)
                        fail_grade_history(conn, s_grade_id)
                        conn.commit()
                        logger.warning(
                            "최종 실패: user_id=%d (%d회 재시도 후 FAILED)",
                            user_id, MAX_RETRY_COUNT,
                        )

        # 배치 실행 이력 업데이트
        final_status = STATUS_COMPLETED if fail_count == 0 else STATUS_FAILED
        update_batch_execution(
            conn, batch_execution_id, final_status, success_count, fail_count, last_error
        )
        conn.commit()

        logger.info("-" * 60)
        logger.info(
            "월별 배치 완료: 성공=%d, 실패=%d, 상태=%s",
            success_count, fail_count, final_status,
        )
        logger.info("=" * 60)
