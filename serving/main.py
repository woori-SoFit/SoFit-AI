import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import set_explainer, set_predictor
from app.core.config import settings
from app.core.constants import SGrade
from advisor import Advisor
from explainer import Explainer
from predictor import Predictor
from schemas import (
    HealthResponse,
    PredictRequest,
    PredictResponse,
    SGradePredictErrorResponse,
    SGradePredictRequest,
    SGradePredictResponse,
    ShapExplanation,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 싱글턴 객체 — lifespan에서 초기화 후 deps.py를 통해 주입
predictor = Predictor()
explainer = Explainer()
advisor = Advisor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    서버 시작/종료 시 실행되는 lifespan 핸들러.
    모델 로드 실패 시에도 서버는 정상 기동 (503으로 응답).
    """
    # 시작 시: 모델 로드
    logger.info("서버 시작 — 모델 로드를 시작합니다. 경로: %s", settings.model_path)
    predictor.load(settings.model_path)

    if predictor.is_loaded:
        explainer.setup(predictor._model)

    # Gemini LLM Advisor 초기화
    advisor.setup()

    set_predictor(predictor)
    set_explainer(explainer)

    logger.info(
        "서버 준비 완료 — 모델 로드 상태: %s",
        "정상" if predictor.is_loaded else "모델 없음 (추론 불가)",
    )

    yield

    # 종료 시: 필요한 정리 작업
    logger.info("서버 종료")


app = FastAPI(
    title="SoFit AI 서버",
    description="소상공인 성장 S등급(S1~S10) 추론 및 SHAP 설명 생성 API. Spring Batch 전용.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["헬스체크"])
async def health_check() -> HealthResponse:
    """서버 및 모델 상태 확인."""
    return HealthResponse(status="ok", model_loaded=predictor.is_loaded)


@app.post("/predict", response_model=PredictResponse, tags=["추론"])
async def predict(
    request: PredictRequest,
) -> PredictResponse:
    """
    S등급 추론 엔드포인트.
    Spring Batch에서만 호출. 필수 필드 누락 시 422 반환.
    모델 미로드 시 503 반환.
    """
    # 모델 로드 여부 확인 (deps 없이 직접 체크 — 더 명확한 에러 메시지 제공)
    if not predictor.is_loaded:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="모델이 로드되지 않았습니다. 모델 파일을 서버에 배치한 후 재시작하세요.",
        )

    # S등급 추론
    s_grade, input_array = predictor.predict(request.features)

    # SHAP 설명 생성 (한 단계 위 등급 기준 — 등급 상승을 위한 개선 포인트 제공)
    # S1이면 이미 최고 등급이므로 S1 기준 유지
    target_class = max(0, s_grade.to_index() - 1)
    target_grade = SGrade.from_index(target_class)

    feature_names = list(request.features.keys())
    strengths, improvements = explainer.explain(
        input_array=input_array,
        feature_names=feature_names,
        feature_values=request.features,
        predicted_class=target_class,
    )

    # 한국어 키워드 추출 (강점 3개 + 개선 포인트 3개)
    strength_kw, improvement_kw = advisor.get_keywords(strengths, improvements)

    # 관리자용 상세 기여도 (강점 5개 + 개선 포인트 5개, 한국어: 숫자)
    strength_details, improvement_details = advisor.get_details(strengths, improvements)

    return PredictResponse(
        user_id=request.user_id,
        s_grade=s_grade,
        shap_explanation=ShapExplanation(
            target_grade=target_grade,
            strengths=strengths,
            improvements=improvements,
        ),
        strength_keywords=strength_kw,
        improvement_keywords=improvement_kw,
        strength_details=strength_details,
        improvement_details=improvement_details,
        advice=await advisor.generate_advice(
            s_grade=s_grade.value,
            target_grade=target_grade.value,
            strengths=strengths,
            improvements=improvements,
        ),
    )


# ── 모델 입력 피처 컬럼 목록 (s_grade_feature 테이블 순서) ────────
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


@app.post(
    "/api/s-grade/predict",
    response_model=SGradePredictResponse,
    responses={
        404: {"model": SGradePredictErrorResponse},
        500: {"model": SGradePredictErrorResponse},
        503: {"model": SGradePredictErrorResponse},
    },
    tags=["S등급 산출"],
)
async def predict_s_grade(request: SGradePredictRequest) -> SGradePredictResponse:
    """
    건별 S등급 산출 엔드포인트.
    Spring BE가 회원가입 시 호출. biz_data_id로 DB에서 피처를 조회하여 추론.

    처리 흐름:
    1. biz_data_id로 s_grade_feature SELECT
    2. LGBM 모델 추론 → S등급 예측
    3. SHAP 계산 → 강점/개선 항목 분류 및 키워드 추출
    4. Gemini LLM → user_advice, admin_advice 생성
    5. JSON Response 반환 (DB 쓰기 없음)
    """
    from asyncio import to_thread

    from fastapi import HTTPException, status

    from db import fetch_feature_by_biz_data_id

    # 모델 로드 확인
    if not predictor.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SGradePredictErrorResponse(
                error="MODEL_NOT_LOADED",
                message="모델이 로드되지 않았습니다. 서버 재시작이 필요합니다.",
            ).model_dump(),
        )

    # 1. DB에서 피처 조회 (동기 I/O → 스레드풀에서 실행하여 이벤트 루프 블로킹 방지)
    try:
        row = await to_thread(fetch_feature_by_biz_data_id, request.biz_data_id)
    except Exception as e:
        logger.error("DB 조회 실패: biz_data_id=%d, error=%s", request.biz_data_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SGradePredictErrorResponse(
                error="DB_CONNECTION_ERROR",
                message="피처 데이터 조회 중 오류가 발생했습니다.",
            ).model_dump(),
        )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SGradePredictErrorResponse(
                error="FEATURE_NOT_FOUND",
                message=f"biz_data_id={request.biz_data_id}에 해당하는 feature 데이터가 없습니다.",
            ).model_dump(),
        )

    # 2. 피처 딕셔너리 구성
    features = {col: row[col] for col in FEATURE_COLUMNS}

    # 3. 모델 추론
    try:
        s_grade, input_df = predictor.predict(features)
    except Exception as e:
        logger.error("모델 예측 실패: biz_data_id=%d, error=%s", request.biz_data_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SGradePredictErrorResponse(
                error="MODEL_PREDICTION_FAILED",
                message="모델 예측 중 오류가 발생했습니다.",
            ).model_dump(),
        )

    # 4. 목표 등급 계산 (한 단계 위, S1이면 None)
    if s_grade == SGrade.S1:
        target_grade = None
        target_class = 0
    else:
        target_class = s_grade.to_index() - 1
        target_grade = SGrade.from_index(target_class)

    # 5. SHAP 계산
    feature_names = FEATURE_COLUMNS
    strengths, improvements = explainer.explain(
        input_array=input_df,
        feature_names=feature_names,
        feature_values=features,
        predicted_class=target_class,
    )

    # 6. 키워드 및 상세 추출
    strength_keywords, improvement_keywords = advisor.get_keywords(strengths, improvements)
    strength_details, improvement_details = advisor.get_details(strengths, improvements)

    # S1인 경우 개선점 비우기
    if s_grade == SGrade.S1:
        improvement_keywords = []
        improvement_details = {}

    # 7. LLM 조언 생성 (유저용 + 은행원용)
    user_advice = await advisor.generate_advice(
        s_grade=s_grade.value,
        target_grade=target_grade.value if target_grade else s_grade.value,
        strengths=strengths,
        improvements=improvements,
    )
    admin_advice = await advisor.generate_admin_advice(
        s_grade=s_grade.value,
        target_grade=target_grade.value if target_grade else s_grade.value,
        strengths=strengths,
        improvements=improvements,
    )

    return SGradePredictResponse(
        s_grade=s_grade.value,
        target_grade=target_grade.value if target_grade else None,
        strength_keywords=strength_keywords,
        improvement_keywords=improvement_keywords,
        strength_details=strength_details,
        improvement_details=improvement_details,
        user_advice=user_advice,
        admin_advice=admin_advice,
    )
