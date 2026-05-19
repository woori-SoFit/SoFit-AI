"""
SoFit AI - SHAP 기반 XAI 설명 생성 모듈

[역할]
- 학습된 LightGBM 모델의 예측 결과에 대해 SHAP 값을 계산
- "한 단계 위 등급"을 목표로 하여 등급 상승에 필요한 개선 포인트를 추출
- 각 피처의 기여 방향(강점/개선 필요)과 크기를 반환
- 추후 BE에서 LLM(Gemini)을 통해 자연어 설명으로 변환됨

[XAI 전략]
- 예측된 등급이 아닌, 한 단계 위 등급(target class)의 SHAP 값을 사용
- 양수: 목표 등급 방향으로 이미 기여 중 (강점, 유지 권장)
- 음수: 목표 등급 도달을 방해 (개선 포인트, 조언 대상)
- 예: S7 예측 → S6 기준 SHAP 계산 → "S6이 되려면 뭘 개선해야 하는가"

[설계 원칙]
- TreeExplainer 사용 (LightGBM 최적화, 정확한 SHAP 값 보장)
- 서버 시작 시 1회 초기화, 이후 요청마다 재사용 (싱글턴)
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
import shap

from app.core.config import settings
from schemas import ShapFeature

logger = logging.getLogger(__name__)


class Explainer:
    """
    SHAP 기반 XAI 설명 생성.
    S등급 산출 근거(기여 변수 top-N, 기여 방향)를 반환.
    """

    def __init__(self) -> None:
        self._explainer: shap.TreeExplainer | None = None

    def setup(self, model: Any) -> None:
        """모델 객체로 TreeExplainer 초기화."""
        self._explainer = shap.TreeExplainer(model)
        logger.info("SHAP Explainer 초기화 완료")

    @property
    def is_ready(self) -> bool:
        return self._explainer is not None

    def explain(
        self,
        input_array: np.ndarray,
        feature_names: list[str],
        feature_values: dict[str, Any],
        predicted_class: int | None = None,
    ) -> tuple[list[ShapFeature], list[ShapFeature]]:
        """
        입력 배열에 대한 SHAP 값을 계산하고 긍정/부정 기여 변수 Top5를 반환.

        Args:
            input_array: 모델 입력 배열 (shape: [1, n_features])
            feature_names: 피처명 목록
            feature_values: 원본 피처 값 딕셔너리
            predicted_class: 목표 클래스 인덱스 (0~9).
                             한 단계 위 등급의 인덱스를 전달.
                             None이면 전체 클래스 평균 절댓값으로 통합.

        Returns:
            (strengths, improvements):
                - strengths: 긍정 기여 Top5 (강점, 양수 SHAP 값 큰 순)
                - improvements: 부정 기여 Top5 (개선 포인트, 음수 SHAP 절댓값 큰 순)

        SHAP 값 해석 (한 단계 위 등급 기준):
            - 양수: 목표 등급 방향으로 이미 기여 중 (강점)
            - 음수: 목표 등급 도달을 방해하는 요소 (개선 포인트)
        """
        if not self.is_ready:
            raise RuntimeError("Explainer가 초기화되지 않았습니다.")

        # DataFrame으로 변환하여 피처명 보존 (SHAP 호환성)
        input_df = pd.DataFrame(input_array, columns=feature_names)

        # ── [추가된 가드레일 로직] 수치형 컬럼들의 object 타입 깨짐 방지 ──
        # input_array가 object 배열일 경우 모든 컬럼이 object 타입이 되므로 수치형 타입을 복원합니다.
        for col in input_df.columns:
            val = feature_values.get(col)
            if isinstance(val, (int, np.integer)):
                input_df[col] = input_df[col].astype(int)
            elif isinstance(val, (float, np.floating)):
                input_df[col] = input_df[col].astype(float)
            elif isinstance(val, bool):
                input_df[col] = input_df[col].astype(bool)
        # ─────────────────────────────────────────────────────────────────

        # LightGBM 학습 시 category 타입이었던 컬럼을 복원
        # (학습 시 categorical_feature로 지정된 컬럼과 dtype이 일치해야 함)
        categorical_cols = ["commercial_trend", "industry_trend"]
        for col in categorical_cols:
            if col in input_df.columns:
                input_df[col] = input_df[col].astype("category")

        # SHAP 값 계산
        shap_values = self._explainer.shap_values(input_df)

        # 다중 클래스: shap_values는 리스트 [클래스0, 클래스1, ..., 클래스9]
        # 각 원소 shape: (1, n_features)
        if isinstance(shap_values, list):
            if predicted_class is not None and 0 <= predicted_class < len(shap_values):
                combined = shap_values[predicted_class][0]
            else:
                combined = np.mean(np.abs(shap_values), axis=0)[0]
        elif shap_values.ndim == 3:
            # (n_samples, n_features, n_classes)
            if predicted_class is not None:
                combined = shap_values[0, :, predicted_class]
            else:
                combined = np.mean(np.abs(shap_values[0]), axis=1)
        else:
            combined = shap_values[0]

        # 긍정 기여 (양수) — 값이 큰 순으로 Top5
        positive_indices = np.where(combined > 0)[0]
        positive_sorted = positive_indices[np.argsort(combined[positive_indices])[::-1]]
        positive_top = positive_sorted[: settings.shap_top_n]

        strengths: list[ShapFeature] = []
        for idx in positive_top:
            name = feature_names[idx]
            strengths.append(
                ShapFeature(
                    feature_name=name,
                    shap_value=round(float(combined[idx]), 6),
                    feature_value=feature_values.get(name),
                )
            )

        # 부정 기여 (음수) — 절댓값이 큰 순으로 Top5
        negative_indices = np.where(combined < 0)[0]
        negative_sorted = negative_indices[np.argsort(np.abs(combined[negative_indices]))[::-1]]
        negative_top = negative_sorted[: settings.shap_top_n]

        improvements: list[ShapFeature] = []
        for idx in negative_top:
            name = feature_names[idx]
            improvements.append(
                ShapFeature(
                    feature_name=name,
                    shap_value=round(float(combined[idx]), 6),
                    feature_value=feature_values.get(name),
                )
            )

        return strengths, improvements