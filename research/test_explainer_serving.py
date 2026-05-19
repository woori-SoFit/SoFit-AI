"""
serving/explainer.py 로직 검증 테스트 스크립트

[실행 방법]
    python3 research/test_explainer_serving.py

[목적]
    serving/explainer.py의 explain() 메서드가
    긍정 기여 Top5 / 부정 기여 Top5를 올바르게 분리 반환하는지 확인
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "serving"))

from research.data_preprocessing import GRADE_ORDER, preprocess
from explainer import Explainer
from app.core.constants import SGrade


def main() -> None:
    # ── 1. 모델 및 데이터 로드 ────────────────────────────────
    model_path = PROJECT_ROOT / "models" / "scb_model_v1.pkl"
    data_path = PROJECT_ROOT / "data" / "s_input_feature_40k.csv"

    with open(model_path, "rb") as f:
        model = pickle.load(f)

    X_train, X_val, X_test, y_train, y_val, y_test, le = preprocess(data_path)

    # ── 2. Explainer 초기화 (서빙과 동일한 방식) ──────────────
    explainer = Explainer()
    explainer.setup(model)
    assert explainer.is_ready, "Explainer 초기화 실패"

    # ── 3. 중간~낮은 등급 샘플 선택 ──────────────────────────
    low_grade_mask = y_test >= 4  # S5 이하
    sample_idx = y_test[low_grade_mask].index[0]

    sample_input = X_test.loc[[sample_idx]]
    feature_names = X_test.columns.tolist()
    feature_values = {name: sample_input.iloc[0][name] for name in feature_names}

    # ── 4. 예측 ──────────────────────────────────────────────
    predicted_proba = model.predict_proba(sample_input)[0]
    predicted_class = int(np.argmax(predicted_proba))
    predicted_grade = GRADE_ORDER[predicted_class]

    # ── 5. 한 단계 위 등급 기준 SHAP (서빙 로직과 동일) ───────
    target_class = max(0, predicted_class - 1)
    target_grade = GRADE_ORDER[target_class]

    strengths, improvements = explainer.explain(
        input_array=sample_input.values,
        feature_names=feature_names,
        feature_values=feature_values,
        predicted_class=target_class,
    )

    # ── 6. 검증 ──────────────────────────────────────────────
    # 강점: 모두 양수여야 함
    for s in strengths:
        assert s.shap_value > 0, f"강점인데 음수: {s.feature_name} = {s.shap_value}"

    # 개선 포인트: 모두 음수여야 함
    for imp in improvements:
        assert imp.shap_value < 0, f"개선 포인트인데 양수: {imp.feature_name} = {imp.shap_value}"

    # 강점은 내림차순 정렬
    strength_values = [s.shap_value for s in strengths]
    assert strength_values == sorted(strength_values, reverse=True), "강점이 내림차순이 아님"

    # 개선 포인트는 절댓값 내림차순 정렬
    imp_abs_values = [abs(imp.shap_value) for imp in improvements]
    assert imp_abs_values == sorted(imp_abs_values, reverse=True), "개선 포인트가 절댓값 내림차순이 아님"

    print("✅ 모든 검증 통과!")
    print()

    # ── 7. 결과 출력 ─────────────────────────────────────────
    result = {
        "predicted_grade": predicted_grade,
        "target_grade": target_grade,
        "description": f"{predicted_grade} → {target_grade} 달성을 위한 분석",
        "strengths_top5": {
            s.feature_name: {"shap_value": s.shap_value, "feature_value": s.feature_value}
            for s in strengths
        },
        "improvements_top5": {
            imp.feature_name: {"shap_value": imp.shap_value, "feature_value": imp.feature_value}
            for imp in improvements
        },
    }

    print(json.dumps(result, indent=2, ensure_ascii=False, default=lambda x: float(x) if hasattr(x, 'item') else str(x)))


if __name__ == "__main__":
    main()
