"""
SHAP 출력 형태 비교 테스트 스크립트

[실행 방법]
    python3 research/test_shap_output.py

[출력]
    두 가지 XAI 전략을 비교:
    1. 한 단계 위 등급 목표 (예: S7 → S6 기준 SHAP)
    2. S1 등급 목표 (최고 등급 기준 SHAP)

    각 전략별로:
    - positive_top5: 이미 잘하고 있는 요소 (강점)
    - negative_top5: 등급 상승을 위해 개선해야 할 요소 (개선 포인트)
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import shap

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from research.data_preprocessing import GRADE_ORDER, preprocess


def extract_shap_for_class(
    shap_values,
    target_class: int,
    feature_names: list[str],
    feature_values: dict[str, any],
) -> dict:
    """특정 목표 클래스 기준으로 SHAP 값을 추출하여 Top5 긍정/부정 분리."""

    # shap_values 형태에 따라 분기
    if isinstance(shap_values, list):
        sample_shap = shap_values[target_class][0]
    elif shap_values.ndim == 3:
        # (n_samples, n_features, n_classes)
        sample_shap = shap_values[0, :, target_class]
    else:
        sample_shap = shap_values[0]

    # {피처명: {"shap_value": ..., "feature_value": ...}} 형태로 구성
    shap_detail = {}
    for name, sv in zip(feature_names, sample_shap):
        shap_detail[name] = {
            "shap_value": round(float(sv), 6),
            "feature_value": feature_values.get(name),
        }

    # 양수: 목표 등급 방향으로 이미 기여하고 있는 요소 (강점)
    positive = {k: v for k, v in shap_detail.items() if v["shap_value"] > 0}
    positive_top5 = dict(
        sorted(positive.items(), key=lambda x: x[1]["shap_value"], reverse=True)[:5]
    )

    # 음수: 목표 등급 도달을 방해하는 요소 (개선 포인트)
    negative = {k: v for k, v in shap_detail.items() if v["shap_value"] < 0}
    negative_top5 = dict(
        sorted(negative.items(), key=lambda x: abs(x[1]["shap_value"]), reverse=True)[:5]
    )

    return {
        "strengths_top5": positive_top5,
        "improvements_top5": negative_top5,
    }


def main() -> None:
    # ── 1. 모델 및 데이터 로드 ────────────────────────────────
    model_path = PROJECT_ROOT / "models" / "scb_model_v1.pkl"
    data_path = PROJECT_ROOT / "data" / "s_input_feature_40k.csv"

    with open(model_path, "rb") as f:
        model = pickle.load(f)

    X_train, X_val, X_test, y_train, y_val, y_test, le = preprocess(data_path)

    # ── 2. 샘플 선택 (중간~낮은 등급 유저를 선택하여 비교 의미 있게) ──
    # S5 이하(index 4 이상)인 샘플 중 첫 번째 선택
    low_grade_mask = y_test >= 4  # S5, S6, S7, S8, S9, S10
    low_grade_indices = y_test[low_grade_mask].index
    sample_idx = low_grade_indices[0]

    sample_input = X_test.loc[[sample_idx]]
    true_grade = GRADE_ORDER[y_test.loc[sample_idx]]

    # ── 3. 예측 ──────────────────────────────────────────────
    predicted_proba = model.predict_proba(sample_input)[0]
    predicted_class = int(np.argmax(predicted_proba))
    predicted_grade = GRADE_ORDER[predicted_class]

    feature_names = X_test.columns.tolist()

    # ── 4. SHAP 값 계산 ──────────────────────────────────────
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample_input)

    # 피처 원본 값 딕셔너리
    feature_values = {name: sample_input.iloc[0][name] for name in feature_names}

    # ── 5. 전략 1: 한 단계 위 등급 목표 ──────────────────────
    # S7(index 6) → S6(index 5) 기준
    one_step_up_class = max(0, predicted_class - 1)
    one_step_up_grade = GRADE_ORDER[one_step_up_class]

    strategy_one_step = extract_shap_for_class(shap_values, one_step_up_class, feature_names, feature_values)

    # ── 6. 전략 2: S1 등급 목표 (최고 등급) ───────────────────
    s1_class = 0  # S1 = index 0
    strategy_s1 = extract_shap_for_class(shap_values, s1_class, feature_names, feature_values)

    # ── 7. 결과 출력 ─────────────────────────────────────────
    result = {
        "sample_info": {
            "true_grade": true_grade,
            "predicted_grade": predicted_grade,
            "confidence": round(float(predicted_proba[predicted_class]), 4),
        },
        "strategy_1_one_step_up": {
            "target_grade": one_step_up_grade,
            "description": f"{predicted_grade} → {one_step_up_grade} 달성을 위한 분석",
            **strategy_one_step,
        },
        "strategy_2_target_s1": {
            "target_grade": "S1",
            "description": f"{predicted_grade} → S1 달성을 위한 분석",
            **strategy_s1,
        },
    }

    print(json.dumps(result, indent=2, ensure_ascii=False, default=lambda x: float(x) if hasattr(x, 'item') else str(x)))


if __name__ == "__main__":
    main()
