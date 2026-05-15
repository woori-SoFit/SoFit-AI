# 데이터 전처리 설계 문서

## 개요

`data_preprocessing.py`는 합성 데이터 CSV(`s_input_feature_40k.csv`)를 LightGBM 학습에 적합한 형태로 변환하는 모듈입니다.

---

## 전처리 파이프라인 흐름

```
CSV 로드 → 피처 인코딩 → 라벨 인코딩 → Stratified Split
```

| 단계 | 함수 | 설명 |
|------|------|------|
| 1 | `load_raw()` | CSV 파일 로드, 기본 타입 정리 |
| 2 | `encode_features()` | bool/ENUM 변환, 메타 컬럼 제거 |
| 3 | `encode_target()` | S등급 문자열 → 정수 인덱스 (0~9) |
| 4 | `split_data()` | train 70% / val 15% / test 15% 분리 |

전체를 한 번에 실행하려면 `preprocess()` 함수를 호출합니다.

---

## 컬럼 분류 기준

### 제거 대상 (메타 컬럼)

모델 학습에 사용하지 않는 식별자/메타 정보입니다.

| 컬럼 | 제거 이유 |
|------|-----------|
| `feature_id` | PK — 순번일 뿐 예측에 무의미 |
| `biz_data_id` | FK — 원본 데이터 참조용 |
| `user_id` | FK — 사용자 식별용 |
| `created_at` | 피처 생성 시각 — 시계열 모델이 아니므로 불필요 |

### bool 컬럼 → int 변환

LightGBM은 bool 타입을 직접 처리하지 못하므로 0/1 정수로 변환합니다.

| 컬럼 | 의미 |
|------|------|
| `is_near_subway` | 역세권 여부 |
| `is_traditional_market` | 전통시장 여부 |
| `has_online_reservation` | 온라인 예약 여부 |
| `has_sns` | SNS 운영 여부 |

### ENUM 컬럼 → pandas category

LightGBM의 네이티브 범주형(categorical) 처리를 활용합니다. One-hot 인코딩 대비 메모리 효율적이고, 트리 분할 시 최적 조합을 자동 탐색합니다.

| 컬럼 | 값 |
|------|-----|
| `commercial_trend` | GROWING / STABLE / DECLINING |
| `industry_trend` | GROWING / STABLE / DECLINING |

### 수치형 컬럼 (변환 없이 그대로 사용)

계량 변수(A1~A10)와 비계량 수치 변수(B1, B3 일부, B5 일부, B6 일부)는 별도 스케일링 없이 원본 값을 사용합니다. LightGBM은 트리 기반 모델이므로 피처 스케일링이 불필요합니다.

---

## 라벨 인코딩

| S등급 | 인덱스 | 의미 |
|-------|--------|------|
| S1 | 0 | 최고 등급 |
| S2 | 1 | |
| ... | ... | |
| S10 | 9 | 최저 등급 |

`serving/app/core/constants.py`의 `SGrade.from_index()`와 동일한 매핑을 사용하여, 학습 시 인코딩과 서빙 시 디코딩이 일치하도록 보장합니다.

---

## 데이터 분리 전략

```
전체 40,000건
├── train: 28,000건 (70%)
├── validation: 6,000건 (15%)
└── test: 6,000건 (15%)
```

- **Stratified Split**: S등급 분포가 가우시안 형태(S1: 2%, S5/S6: 20%)로 불균형하므로, 각 분할에서 등급 비율이 동일하게 유지되도록 층화 추출합니다.
- **2단계 분리**: 먼저 train+val vs test를 나누고, 이후 train vs val을 분리합니다. 이렇게 하면 test set이 학습 과정에 전혀 노출되지 않습니다.

---

## 설계 결정 사항

### 스케일링을 하지 않는 이유

LightGBM은 트리 기반 모델로, 분할 기준(threshold)만 사용합니다. 피처 값의 절대 크기가 모델 성능에 영향을 주지 않으므로 StandardScaler/MinMaxScaler를 적용하지 않습니다.

### One-hot 인코딩 대신 category 타입을 쓰는 이유

- ENUM 컬럼의 카디널리티가 3으로 낮아 One-hot도 가능하지만, LightGBM의 네이티브 범주형 처리가 최적 분할 조합을 자동 탐색하므로 성능이 더 좋습니다.
- 피처 수가 늘어나지 않아 SHAP 해석 시에도 직관적입니다.

### LabelEncoder 순서 고정

`sklearn.LabelEncoder`는 기본적으로 알파벳 순으로 정렬하므로, S1 → S10 → S2 ... 순서가 됩니다. 이를 방지하기 위해 `le.classes_`를 `["S1", "S2", ..., "S10"]`으로 직접 고정합니다.

---

## 사용 예시

```python
from pathlib import Path
from research.data_preprocessing import preprocess

X_train, X_val, X_test, y_train, y_val, y_test, le = preprocess(
    Path("data/s_input_feature_40k.csv")
)

# X_train.shape → (28000, 31)
# y_train 값 범위 → 0~9 (S1~S10)
```

---

## 최종 피처 목록 (31개)

| 구분 | 피처명 | 타입 |
|------|--------|------|
| A1 | business_age_months | int |
| A2 | quarterly_revenue_growth_rate | float |
| A3 | annual_revenue_growth_rate | float |
| A4 | revenue_vs_industry_avg_ratio | float |
| A5 | avg_monthly_transaction_3m | float |
| A5 | avg_monthly_transaction_6m | float |
| A5 | avg_monthly_transaction_12m | float |
| A6 | days_since_last_transaction | int |
| A7 | max_inactive_days | int |
| A8 | online_platform_activity_index | float |
| A9 | revenue_growth_per_employee_3m | float |
| A9 | revenue_growth_per_employee_6m | float |
| A9 | revenue_growth_per_employee_12m | float |
| A10 | revenue_growth_per_business_age_3m | float |
| A10 | revenue_growth_per_business_age_6m | float |
| A10 | revenue_growth_per_business_age_12m | float |
| B1 | online_accessibility_score | float |
| B2 | is_near_subway | int (0/1) |
| B3 | commercial_saturation_score | float |
| B3 | is_traditional_market | int (0/1) |
| B3 | commercial_trend | category |
| B4 | industry_trend | category |
| B5 | review_rating | float |
| B5 | review_count | int |
| B5 | delivery_rating | float |
| B5 | delivery_order_count | int |
| B5 | positive_review_ratio | float |
| B5 | has_online_reservation | int (0/1) |
| B6 | owner_experience_years | int |
| B6 | employee_count | int |
| B6 | has_sns | int (0/1) |
