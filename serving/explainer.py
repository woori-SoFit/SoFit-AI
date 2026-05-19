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
    ) -> list[ShapFeature]:
        """
        입력 배열에 대한 SHAP 값을 계산하고 상위 N개 기여 변수를 반환.

        Args:
            input_array: 모델 입력 배열 (shape: [1, n_features])
            feature_names: 피처명 목록
            feature_values: 원본 피처 값 딕셔너리
            predicted_class: 목표 클래스 인덱스 (0~9).
                             한 단계 위 등급의 인덱스를 전달.
                             None이면 전체 클래스 평균 절댓값으로 통합.

        Returns:
            상위 shap_top_n개 ShapFeature 목록 (|SHAP 값| 기준 내림차순)

        SHAP 값 해석 (한 단계 위 등급 기준):
            - 양수: 목표 등급 방향으로 이미 기여 중 (강점)
            - 음수: 목표 등급 도달을 방해하는 요소 (개선 포인트)
        """
        if not self.is_ready:
            raise RuntimeError("Explainer가 초기화되지 않았습니다.")

        # DataFrame으로 변환하여 피처명 보존 (SHAP 호환성)
        input_df = pd.DataFrame(input_array, columns=feature_names)

        # SHAP 값 계산
        shap_values = self._explainer.shap_values(input_df)

        # 다중 클래스: shap_values는 리스트 [클래스0, 클래스1, ..., 클래스9]
        # 각 원소 shape: (1, n_features)
        if isinstance(shap_values, list):
            if predicted_class is not None and 0 <= predicted_class < len(shap_values):
                # 예측된 클래스의 SHAP 값 사용 (해당 등급에 대한 기여도)
                combined = shap_values[predicted_class][0]
            else:
                # 클래스 미지정 시 전체 클래스 평균 절댓값으로 통합
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
                    shap_value=round(float(combined[idx]), 6),
                    feature_value=feature_values.get(name),
                )
            )

        return result
