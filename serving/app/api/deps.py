from typing import Annotated

from fastapi import Depends, HTTPException, status

from explainer import Explainer
from predictor import Predictor

# 앱 시작 시 main.py의 lifespan에서 주입되는 싱글턴 객체
_predictor: Predictor | None = None
_explainer: Explainer | None = None


def set_predictor(predictor: Predictor) -> None:
    global _predictor
    _predictor = predictor


def set_explainer(explainer: Explainer) -> None:
    global _explainer
    _explainer = explainer


def get_predictor() -> Predictor:
    """
    Predictor 의존성 주입.
    모델이 로드되지 않은 경우 503 반환.
    """
    if _predictor is None or not _predictor.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="모델이 아직 로드되지 않았습니다. 잠시 후 다시 시도하세요.",
        )
    return _predictor


def get_explainer() -> Explainer:
    """
    Explainer 의존성 주입.
    초기화되지 않은 경우 503 반환.
    """
    if _explainer is None or not _explainer.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Explainer가 초기화되지 않았습니다.",
        )
    return _explainer


# FastAPI Depends 타입 별칭
PredictorDep = Annotated[Predictor, Depends(get_predictor)]
ExplainerDep = Annotated[Explainer, Depends(get_explainer)]
