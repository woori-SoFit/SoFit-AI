from typing import Any

from pydantic import BaseModel, Field

from app.core.constants import SGrade


# ── 요청(Request) 스키마 ──────────────────────────────────────

class PredictRequest(BaseModel):
    """
    S등급 추론 요청 스키마.
    Spring Batch에서 호출 시 전달하는 소상공인 사업자 데이터(My Biz Data).
    필드 누락 시 422 Unprocessable Entity 반환 (추론 불가 처리).
    """

    user_id: int = Field(..., description="사용자 ID")
    features: dict[str, Any] = Field(
        ...,
        description="모델 입력 피처 (My Biz Data 기반). 예: 월매출, 순이익, 현금흐름, 업종순위 등",
    )


# ── 응답(Response) 스키마 ────────────────────────────────────

class ShapFeature(BaseModel):
    """SHAP 기여 변수 단일 항목."""

    feature_name: str = Field(..., description="피처명")
    shap_value: float = Field(..., description="SHAP 기여값 (양수: 등급 상승 기여, 음수: 등급 하락 기여)")
    feature_value: Any = Field(..., description="실제 입력값")


class PredictResponse(BaseModel):
    """
    S등급 추론 응답 스키마.
    등급(S1~S10) + SHAP 설명 포함.
    BE가 이 응답을 DB에 저장 (AI 서버는 DB 직접 접근 금지).
    """

    user_id: int = Field(..., description="사용자 ID")
    s_grade: SGrade = Field(..., description="성장 S등급 (S1~S10)")
    shap_features: list[ShapFeature] = Field(
        ..., description="상위 N개 SHAP 기여 변수 목록"
    )


class HealthResponse(BaseModel):
    """헬스체크 응답."""

    status: str = "ok"
    model_loaded: bool = Field(..., description="모델 로드 여부")
