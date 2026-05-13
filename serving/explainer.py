import logging
from typing import Any

import numpy as np
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
    ) -> list[ShapFeature]:
        """
        입력 배열에 대한 SHAP 값을 계산하고 상위 N개 기여 변수를 반환.

        Args:
            input_array: 모델 입력 배열 (shape: [1, n_features])
            feature_names: 피처명 목록
            feature_values: 원본 피처 값 딕셔너리

        Returns:
            상위 shap_top_n개 ShapFeature 목록 (|SHAP 값| 기준 내림차순)
        """
        if not self.is_ready:
            raise RuntimeError("Explainer가 초기화되지 않았습니다.")

        # SHAP 값 계산 (다중 클래스: 예측 클래스 기준 값 사용)
        shap_values = self._explainer.shap_values(input_array)

        # 다중 클래스인 경우 shap_values는 리스트 — 평균 절댓값으로 통합
        if isinstance(shap_values, list):
            combined = np.mean(np.abs(shap_values), axis=0)[0]
        else:
            combined = shap_values[0]

        # 절댓값 기준 상위 N개 인덱스 추출
        top_indices = np.argsort(np.abs(combined))[::-1][: settings.shap_top_n]

        result: list[ShapFeature] = []
        for idx in top_indices:
            name = feature_names[idx]
            result.append(
                ShapFeature(
                    feature_name=name,
                    shap_value=float(combined[idx]),
                    feature_value=feature_values.get(name),
                )
            )

        return result
