"""
Gemini LLM 자연어 조언 생성 테스트 스크립트

[실행 방법]
    python3 research/test_advisor.py

[사전 조건]
    - .env 파일에 GEMINI_API_KEY 설정 필요
    - models/scb_model_v1.pkl 존재 필요
    - pip install google-generativeai python-dotenv

[출력]
    - 예측 등급 및 목표 등급
    - 강점/개선 포인트 Top5
    - 한국어 키워드 3개씩
    - 관리자용 상세 기여도 (한국어: 숫자) 5개씩
    - Gemini가 생성한 자연어 조언
"""

import asyncio
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "serving"))

# .env 로드 (GEMINI_API_KEY)
load_dotenv(PROJECT_ROOT / "serving" / ".env")

from research.data_preprocessing import GRADE_ORDER, preprocess
from advisor import Advisor
from explainer import Explainer
from app.core.constants import SGrade


async def main() -> None:
    # ── 1. 모델 및 데이터 로드 ────────────────────────────────
    model_path = PROJECT_ROOT / "models" / "scb_model_v1.pkl"
    data_path = PROJECT_ROOT / "data" / "s_input_feature_40k.csv"

    with open(model_path, "rb") as f:
        model = pickle.load(f)

    X_train, X_val, X_test, y_train, y_val, y_test, le = preprocess(data_path)

    # ── 2. Explainer & Advisor 초기화 ─────────────────────────
    explainer = Explainer()
    explainer.setup(model)

    advisor = Advisor()
    advisor.setup()

    if not advisor.is_ready:
        print("❌ Gemini API 키가 설정되지 않았습니다.")
        print("   serving/.env 파일에 GEMINI_API_KEY=your-key 를 추가하세요.")
        return

    print("✅ Explainer & Advisor 초기화 완료")

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
    s_grade = SGrade.from_index(predicted_class)

    # 한 단계 위 등급
    target_class = max(0, predicted_class - 1)
    target_grade = GRADE_ORDER[target_class]

    print(f"\n[샘플 정보]")
    print(f"  예측 등급: {predicted_grade}")
    print(f"  목표 등급: {target_grade}")

    # ── 5. SHAP 설명 생성 ────────────────────────────────────
    strengths, improvements = explainer.explain(
        input_array=sample_input.values,
        feature_names=feature_names,
        feature_values=feature_values,
        predicted_class=target_class,
    )

    print(f"\n[강점 Top5]")
    for s in strengths:
        print(f"  ✓ {s.feature_name}: {s.feature_value} (SHAP: {s.shap_value:+.4f})")

    print(f"\n[개선 포인트 Top5]")
    for imp in improvements:
        print(f"  ✗ {imp.feature_name}: {imp.feature_value} (SHAP: {imp.shap_value:+.4f})")

    # ── 6. 한국어 키워드 추출 (3개씩) ─────────────────────────
    strength_kw, improvement_kw = advisor.get_keywords(strengths, improvements)

    print(f"\n[잘하고 있는 점 (한국어 키워드 3개)]")
    for i, kw in enumerate(strength_kw, 1):
        print(f"  {i}. {kw}")

    print(f"\n[노력이 필요한 점 (한국어 키워드 3개)]")
    for i, kw in enumerate(improvement_kw, 1):
        print(f"  {i}. {kw}")

    # ── 7. 관리자용 상세 기여도 (5개씩) ───────────────────────
    strength_details, improvement_details = advisor.get_details(strengths, improvements)

    print(f"\n[관리자용 — 강점 상세 기여도]")
    for kr_name, value in strength_details.items():
        print(f"  {kr_name}: {value:+.6f}")

    print(f"\n[관리자용 — 개선 포인트 상세 기여도]")
    for kr_name, value in improvement_details.items():
        print(f"  {kr_name}: {value:+.6f}")

    # ── 8. LLM 자연어 조언 생성 ──────────────────────────────
    print(f"\n[Gemini 자연어 조언 생성 중...]")
    advice = await advisor.generate_advice(
        s_grade=s_grade.value,
        target_grade=SGrade.from_index(target_class).value,
        strengths=strengths,
        improvements=improvements,
    )

    print(f"\n{'=' * 60}")
    print(f"[생성된 조언]")
    print(f"{'=' * 60}")
    print(advice)
    print(f"{'=' * 60}")

    # ── 9. JSON 형태 출력 (API 응답 시뮬레이션) ───────────────
    print(f"\n[API 응답 형태]")
    response = {
        "user_id": 12345,
        "s_grade": predicted_grade,
        "shap_explanation": {
            "target_grade": target_grade,
            "strengths": [
                {"feature_name": s.feature_name, "shap_value": s.shap_value, "feature_value": s.feature_value}
                for s in strengths
            ],
            "improvements": [
                {"feature_name": imp.feature_name, "shap_value": imp.shap_value, "feature_value": imp.feature_value}
                for imp in improvements
            ],
        },
        "strength_keywords": strength_kw,
        "improvement_keywords": improvement_kw,
        "strength_details": strength_details,
        "improvement_details": improvement_details,
        "advice": advice,
    }
    print(json.dumps(response, indent=2, ensure_ascii=False, default=lambda x: float(x) if hasattr(x, 'item') else str(x)))


if __name__ == "__main__":
    asyncio.run(main())
