"""
SoFit AI - 데이터 전처리 모듈

[역할]
- CSV 원본 데이터를 LGBM 학습에 적합한 형태로 변환
- 범주형 변수 인코딩, 불필요 컬럼 제거, 타입 정합성 보장
- train/validation/test 분리 (stratified)

[피처 구성]
- 계량 변수 (A1~A10): 수치형 그대로 사용
- 비계량 변수 (B1~B6): bool → int, ENUM → LightGBM category 타입
- 제외 컬럼: feature_id, biz_data_id, user_id, created_at (식별자/메타)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

# ── 컬럼 분류 ────────────────────────────────────────────────

# 모델 입력에서 제외할 메타 컬럼
META_COLS: list[str] = ["feature_id", "biz_data_id", "user_id", "created_at"]

# 라벨 컬럼
TARGET_COL: str = "target_s_grade"

# ENUM 범주형 컬럼 (LightGBM category 타입으로 처리)
CATEGORICAL_COLS: list[str] = ["commercial_trend", "industry_trend"]

# bool 컬럼 (0/1 정수로 변환)
BOOL_COLS: list[str] = [
    "is_near_subway",
    "is_traditional_market",
    "has_online_reservation",
    "has_sns",
]

# S등급 순서 정의 (S1 = 최고 등급 → index 0)
GRADE_ORDER: list[str] = [
    "S1", "S2", "S3", "S4", "S5",
    "S6", "S7", "S8", "S9", "S10",
]


def load_raw(csv_path: Path) -> pd.DataFrame:
    """CSV 파일을 로드하고 기본 타입을 정리한다."""
    logger.info("데이터 로드 중: %s", csv_path)
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    logger.info("로드 완료 — 행: %d, 열: %d", len(df), len(df.columns))
    return df


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    피처 인코딩 및 타입 변환.

    - bool 컬럼 → int (0/1)
    - ENUM 컬럼 → pandas category (LightGBM이 자동으로 범주형 처리)
    - 메타 컬럼 제거
    """
    df = df.copy()

    # bool → int
    for col in BOOL_COLS:
        if col in df.columns:
            df[col] = df[col].astype(int)

    # ENUM → category
    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df[col] = df[col].astype("category")

    # 메타 컬럼 제거
    drop_cols = [c for c in META_COLS if c in df.columns]
    df = df.drop(columns=drop_cols)

    return df


def encode_target(series: pd.Series) -> tuple[pd.Series, LabelEncoder]:
    """
    S등급 문자열 → 정수 인덱스 변환.
    S1 → 0, S2 → 1, ..., S10 → 9 (SGrade.from_index와 동일한 순서).

    Returns:
        (인코딩된 시리즈, 역변환용 LabelEncoder)
    """
    le = LabelEncoder()
    le.classes_ = pd.array(GRADE_ORDER)  # 순서 고정
    encoded = series.map({grade: idx for idx, grade in enumerate(GRADE_ORDER)})
    return encoded.astype(int), le


def split_data(
    df: pd.DataFrame,
    target_col: str = TARGET_COL,
    test_size: float = 0.15,
    val_size: float = 0.15,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
           pd.Series, pd.Series, pd.Series]:
    """
    Stratified train / validation / test 분리.

    비율: train 70% / val 15% / test 15%

    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test
    """
    X = df.drop(columns=[target_col])
    y = df[target_col]

    # 1차 분리: train+val vs test
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )

    # 2차 분리: train vs val (val_size를 train+val 기준으로 재계산)
    val_ratio_of_trainval = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval,
        test_size=val_ratio_of_trainval,
        stratify=y_trainval,
        random_state=random_state,
    )

    logger.info(
        "데이터 분리 완료 — train: %d, val: %d, test: %d",
        len(X_train), len(X_val), len(X_test),
    )
    return X_train, X_val, X_test, y_train, y_val, y_test


def preprocess(
    csv_path: Path,
    test_size: float = 0.15,
    val_size: float = 0.15,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame,
           pd.Series, pd.Series, pd.Series,
           LabelEncoder]:
    """
    전체 전처리 파이프라인 실행.

    Returns:
        X_train, X_val, X_test, y_train, y_val, y_test, label_encoder
    """
    df = load_raw(csv_path)
    df = encode_features(df)

    # 라벨 인코딩
    df[TARGET_COL], le = encode_target(df[TARGET_COL])

    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        df,
        target_col=TARGET_COL,
        test_size=test_size,
        val_size=val_size,
        random_state=random_state,
    )

    return X_train, X_val, X_test, y_train, y_val, y_test, le
