import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import set_explainer, set_predictor
from app.core.config import settings
from explainer import Explainer
from predictor import Predictor
from schemas import HealthResponse, PredictRequest, PredictResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 싱글턴 객체 — lifespan에서 초기화 후 deps.py를 통해 주입
predictor = Predictor()
explainer = Explainer()


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

    # SHAP 설명 생성
    feature_names = list(request.features.keys())
    shap_features = explainer.explain(
        input_array=input_array,
        feature_names=feature_names,
        feature_values=request.features,
    )

    return PredictResponse(
        user_id=request.user_id,
        s_grade=s_grade,
        shap_features=shap_features,
    )
