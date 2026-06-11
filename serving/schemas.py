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
    strength_details: dict[str, float] = Field(
        ..., description="관리자용 — 강점 5개 {한국어 파라미터명: SHAP 기여도}"
    )
    improvement_details: dict[str, float] = Field(
        ..., description="관리자용 — 개선 포인트 5개 {한국어 파라미터명: SHAP 기여도}"
    )
    advice: str = Field(
        default="", description="LLM이 생성한 자연어 조언 (Gemini 기반)"
    )


class HealthResponse(BaseModel):
    """헬스체크 응답."""

    status: str = "ok"
    model_loaded: bool = Field(..., description="모델 로드 여부")


# ── 건별 S등급 산출 API (Spring BE → Python) ──────────────────

class SGradePredictRequest(BaseModel):
    """
    건별 S등급 산출 요청.
    Spring BE가 회원가입 시 호출. biz_data_id만 전달하면 Python이 DB에서 피처를 조회.
    """

    biz_data_id: int = Field(..., description="s_grade_feature 테이블에서 피처를 조회할 key")


class SGradePredictResponse(BaseModel):
    """
    건별 S등급 산출 응답.
    Spring BE가 이 응답을 받아서 s_grade_history / s_grade_report에 저장.
    """

    s_grade: str = Field(..., description="산출된 등급 (S1~S10)")
    target_grade: str | None = Field(None, description="다음 목표 등급 (S1이면 null)")
    strength_keywords: list[str] = Field(..., description="강점 키워드 목록 (고객 리포트용)")
    improvement_keywords: list[str] = Field(..., description="개선 키워드 목록 (고객 리포트용)")
    strength_details: dict[str, float] = Field(..., description="강점 항목별 SHAP 기여도")
    improvement_details: dict[str, float] = Field(..., description="개선 항목별 SHAP 기여도 (음수)")
    user_advice: str = Field(..., description="고객용 자연어 조언 (LLM 생성)")
    admin_advice: str = Field(..., description="은행원용 상세 분석 (내부 변수 포함 가능)")


class SGradePredictErrorResponse(BaseModel):
    """건별 S등급 산출 에러 응답."""

    error: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 상세 메시지")
