import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.constants import SGrade

logger = logging.getLogger(__name__)


class Predictor:
    """
    LGBM 모델 로드 및 S등급 추론.
    서버 시작 시 모델을 로드하고, 모델 교체는 서버 재시작으로 처리.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._is_loaded: bool = False

    def load(self, model_path: Path) -> None:
        """
        모델 파일(.pkl)을 로드.
        파일이 없으면 경고 로그만 남기고 서버는 정상 기동 (모델 없이 시작 허용).
        """
        if not model_path.exists():
            logger.warning(
                "모델 파일을 찾을 수 없습니다: %s — 서버는 기동되지만 추론 불가 상태입니다.",
                model_path,
            )
            return

        with open(model_path, "rb") as f:
            self._model = pickle.load(f)

        self._is_loaded = True
        logger.info("모델 로드 완료: %s", model_path)

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def predict(self, features: dict[str, Any]) -> tuple[SGrade, np.ndarray]:
        """
        피처 딕셔너리를 받아 S등급과 SHAP 계산용 입력 배열을 반환.

        Returns:
            (s_grade, input_array): 예측된 S등급과 모델 입력 배열
        Raises:
            RuntimeError: 모델이 로드되지 않은 경우
        """
        if not self._is_loaded:
            raise RuntimeError(
                "모델이 로드되지 않았습니다. 모델 파일을 서버에 배치한 후 재시작하세요."
            )

        # 피처 딕셔너리 → DataFrame (모델 입력 형식)
        input_df = pd.DataFrame([features])

        # 클래스 확률 예측 (shape: [1, 10] — S1~S10 각 확률)
        probabilities = self._model.predict_proba(input_df)
        predicted_index = int(np.argmax(probabilities[0]))

        s_grade = SGrade.from_index(predicted_index)
        return s_grade, input_df.values
