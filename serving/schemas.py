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
    shap_value: float = Field(..., description="SHAP 기여값 (양수: 강점, 음수: 개선 포인트)")
    feature_value: Any = Field(..., description="실제 입력값")


class ShapExplanation(BaseModel):
    """
    SHAP 설명 결과.
    한 단계 위 등급을 목표로 긍정/부정 기여 변수를 분리하여 제공.
    """

    target_grade: SGrade = Field(..., description="목표 등급 (한 단계 위)")
    strengths: list[ShapFeature] = Field(
        ..., description="강점 Top5 — 목표 등급 방향으로 이미 기여 중인 변수"
    )
    improvements: list[ShapFeature] = Field(
        ..., description="개선 포인트 Top5 — 목표 등급 도달을 방해하는 변수"
    )


class PredictResponse(BaseModel):
    """
    S등급 추론 응답 스키마.
    등급(S1~S10) + SHAP 설명 + 자연어 조언 포함.
    BE가 이 응답을 DB에 저장 (AI 서버는 DB 직접 접근 금지).
    """

    user_id: int = Field(..., description="사용자 ID")
    s_grade: SGrade = Field(..., description="성장 S등급 (S1~S10)")
    shap_explanation: ShapExplanation = Field(
        ..., description="SHAP 기반 등급 상승 가이드 (강점 + 개선 포인트)"
    )
    strength_keywords: list[str] = Field(
        ..., description="잘하고 있는 점 3가지 (한국어 키워드)"
    )
    improvement_keywords: list[str] = Field(
        ..., description="노력이 필요한 점 3가지 (한국어 키워드)"
    )
    advice: str = Field(
        default="", description="LLM이 생성한 자연어 조언 (Gemini 기반)"
    )


class HealthResponse(BaseModel):
    """헬스체크 응답."""

    status: str = "ok"
    model_loaded: bool = Field(..., description="모델 로드 여부")
