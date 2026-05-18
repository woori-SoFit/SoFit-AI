"""
SoFit AI - LightGBM 모델 학습 스크립트

[실행 방법]
    python research/train.py

[출력]
    models/scb_model_v1.pkl  — 학습된 LightGBM 파이프라인 (전처리 포함)

[설계 원칙]
- 다중 클래스 분류 (S1~S10, 10클래스)
- LightGBM 네이티브 범주형 지원 활용 (commercial_trend, industry_trend)
- Early stopping으로 과적합 방지
- 학습 완료 후 test set 성능 리포트 출력
- 모델 파일은 models/ 디렉토리에 저장 (.gitignore 대상)
"""

from __future__ import annotations

import logging
import pickle
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    cohen_kappa_score,
)

# 프로젝트 루트를 sys.path에 추가 (research/ 하위에서 실행 시 대비)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from research.data_preprocessing import GRADE_ORDER, preprocess

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── 경로 설정 ────────────────────────────────────────────────
DATA_PATH = PROJECT_ROOT / "data" / "s_input_feature_40k.csv"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_VERSION = "v1"
MODEL_PATH = MODEL_DIR / f"scb_model_{MODEL_VERSION}.pkl"

# ── LightGBM 하이퍼파라미터 ──────────────────────────────────
LGBM_PARAMS: dict = {
    # 목적 함수: 다중 클래스 분류 (S1~S10, 10클래스)
    "objective": "multiclass",
    "num_class": 10,
    "metric": "multi_logloss",

    # 트리 구조
    "num_leaves": 63,
    "max_depth": -1,          # 제한 없음 (num_leaves로 복잡도 제어)
    "min_child_samples": 30,  # 과적합 방지: 리프 노드 최소 샘플 수

    # 학습률 및 정규화
    "learning_rate": 0.05,
    "n_estimators": 1000,     # early stopping으로 실제 트리 수 결정
    "subsample": 0.8,         # 행 샘플링 (배깅)
    "subsample_freq": 1,
    "colsample_bytree": 0.8,  # 열 샘플링
    "reg_alpha": 0.1,         # L1 정규화
    "reg_lambda": 0.1,        # L2 정규화
    # AutoML: 최적의 하이퍼파라미터 값 찾아냄 

    # 클래스 불균형 처리
    "class_weight": "balanced",

    # 재현성
    "random_state": 42,
    "verbose": -1,

    # 성능
    "n_jobs": -1,
}

# Early stopping 설정
EARLY_STOPPING_ROUNDS = 50


def train() -> None:
    """전체 학습 파이프라인 실행."""

    # ── 1. 데이터 전처리 ─────────────────────────────────────
    logger.info("=" * 60)
    logger.info("SoFit AI - LightGBM 학습 시작")
    logger.info("=" * 60)

    if not DATA_PATH.exists():
        logger.error(
            "데이터 파일을 찾을 수 없습니다: %s\n"
            "먼저 'python data/generate_data.py'를 실행하세요.",
            DATA_PATH,
        )
        sys.exit(1)

    X_train, X_val, X_test, y_train, y_val, y_test, le = preprocess(DATA_PATH)

    logger.info("피처 수: %d", X_train.shape[1])
    logger.info("피처 목록: %s", list(X_train.columns))

    # ── 2. 모델 학습 ─────────────────────────────────────────
    logger.info("LightGBM 학습 시작 (early stopping: %d rounds)", EARLY_STOPPING_ROUNDS)

    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[
            lgb.early_stopping(stopping_rounds=EARLY_STOPPING_ROUNDS, verbose=True),
            lgb.log_evaluation(period=50),
        ],
    )

    logger.info("학습 완료 — 최적 트리 수: %d", model.best_iteration_)

    # ── 3. 성능 평가 ─────────────────────────────────────────
    _evaluate(model, X_val, y_val, split_name="Validation")
    _evaluate(model, X_test, y_test, split_name="Test")

    # ── 4. 피처 중요도 출력 ───────────────────────────────────
    _print_feature_importance(model, X_train.columns.tolist())

    # ── 5. 모델 저장 ─────────────────────────────────────────
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    logger.info("=" * 60)
    logger.info("모델 저장 완료: %s", MODEL_PATH)
    logger.info("=" * 60)


def _evaluate(
    model: lgb.LGBMClassifier,
    X: "pd.DataFrame",
    y: "pd.Series",
    split_name: str,
) -> None:
    """분류 성능 지표 출력."""
    y_pred = model.predict(X)
    acc = accuracy_score(y, y_pred)
    kappa = cohen_kappa_score(y, y_pred, weights="quadratic")

    logger.info("-" * 40)
    logger.info("[%s] Accuracy: %.4f | Quadratic Kappa: %.4f", split_name, acc, kappa)
    logger.info(
        "\n%s",
        classification_report(
            y, y_pred,
            target_names=GRADE_ORDER,
            digits=3,
        ),
    )


def _print_feature_importance(
    model: lgb.LGBMClassifier,
    feature_names: list[str],
    top_n: int = 15,
) -> None:
    """피처 중요도 상위 N개 출력 (gain 기준)."""
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]

    logger.info("-" * 40)
    logger.info("피처 중요도 상위 %d개 (gain 기준):", top_n)
    for rank, idx in enumerate(sorted_idx[:top_n], start=1):
        logger.info("  %2d. %-45s %.2f", rank, feature_names[idx], importances[idx])


if __name__ == "__main__":
    train()
