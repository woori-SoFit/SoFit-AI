# data-table

# 테이블 명세서

## S 입력 피처 `s_input_feature`

> **BaseEntity 상속** (created_at 포함). My Biz Data를 LightGBM 모델 입력용 계량·비계량 변수로 가공한 결과. 배치 실행 시 이 테이블의 데이터를 AI 서버에 전달한다.
> 

**인덱스:**
- `idx_s_input_feature_user_created` → (user_id, created_at)
- `idx_s_input_feature_biz_data` → (biz_data_id)

| 컬럼명 | 타입 | 설명 | 변수 |
| --- | --- | --- | --- |
| feature_id | BIGINT | 입력 피처 고유 ID (PK) |  |
| biz_data_id | BIGINT | 원본 My Biz Data ID (FK → my_biz_data) |  |
| user_id | BIGINT | 사업자 사용자 ID (FK → users) |  |
| **— 계량 변수 (A) —** |  |  |  |
| business_age_months | INT | 업력 (개월) | A1 |
| quarterly_revenue_growth_rate | DECIMAL(5,2) | 전분기 대비 최근분기 매출증가율 (%) | A2 |
| annual_revenue_growth_rate | DECIMAL(5,2) | 전년도 대비 최근년도 매출증가율 (%) | A3 |
| revenue_vs_industry_avg_ratio | DECIMAL(5,2) | 매출 / 동일업종 평균매출 비율 | A4 |
| avg_monthly_transaction_3m | DECIMAL(15,2) | 최근 3개월 평균 거래금액 (원) | A5 |
| avg_monthly_transaction_6m | DECIMAL(15,2) | 최근 6개월 평균 거래금액 (원) | A5 |
| avg_monthly_transaction_12m | DECIMAL(15,2) | 최근 12개월 평균 거래금액 (원) | A5 |
| days_since_last_transaction | INT | 최종 결제일로부터의 기간 (일) | A6 |
| max_inactive_days | INT | 최장 영업징후 부재기간 (일) | A7 |
| online_platform_activity_index | DECIMAL(5,2) | 온라인 플랫폼 활동성·성장성 지수 | A8 |
| revenue_growth_per_employee_3m | DECIMAL(5,2) | 매출증가율 / 근로자수 (3개월) | A9 |
| revenue_growth_per_employee_6m | DECIMAL(5,2) | 매출증가율 / 근로자수 (6개월) | A9 |
| revenue_growth_per_employee_12m | DECIMAL(5,2) | 매출증가율 / 근로자수 (12개월) | A9 |
| revenue_growth_per_business_age_3m | DECIMAL(5,2) | 매출증가율 / 업력 (3개월) | A10 |
| revenue_growth_per_business_age_6m | DECIMAL(5,2) | 매출증가율 / 업력 (6개월) | A10 |
| revenue_growth_per_business_age_12m | DECIMAL(5,2) | 매출증가율 / 업력 (12개월) | A10 |
| **— 비계량 변수 (B) —** |  |  |  |
| online_accessibility_score | DECIMAL(5,2) | 사업장 온라인 정보 접근성 점수 | B1 |
| is_near_subway | BOOLEAN | 역세권 여부 (500m 이내) | B2 |
| commercial_saturation_score | DECIMAL(5,2) | 상권 포화도 점수 | B3 |
| is_traditional_market | BOOLEAN | 전통시장 여부 | B3 |
| commercial_trend | ENUM | 상권 트렌드: `GROWING` / `STABLE` / `DECLINING` | B3 |
| industry_trend | ENUM | 업종 트렌드: `GROWING` / `STABLE` / `DECLINING` | B4 |
| review_rating | DECIMAL(3,1) | 평점 | B5 |
| review_count | INT | 리뷰 수 | B5 |
| delivery_rating | DECIMAL(3,1) | 배달앱 평점 | B5 |
| delivery_order_count | INT | 배달앱 주문 수 | B5 |
| positive_review_ratio | DECIMAL(5,2) | 긍정 리뷰 비율 (%) | B5 |
| has_online_reservation | BOOLEAN | 온라인 예약 여부 | B5 |
| owner_experience_years | INT | 경영주 동업종 경력 (년) | B6 |
| employee_count | INT | 직원 수 | B6 |
| has_sns | BOOLEAN | SNS 운영 여부 | B6 |
| created_at | DATETIME | 피처 생성 일시 |  |

---

## 배치 실행 이력 `batch_execution_history`

> Python Batch 전체 사용자 대상 자동·수동 실행 이력.
AUTO는 정기 스케줄, MANUAL은 모델·변수 변경 등 수동 배치 작업이 필요한 경우.
> 

**인덱스:**
- `idx_batch_execution_status` → (status)
- `idx_batch_execution_cycle_started` → (execution_cycle, started_at)

| 컬럼명 | 타입 | 설명 |
| --- | --- | --- |
| execution_id | BIGINT | 배치 실행 고유 ID (PK) |
| execution_type | ENUM | 실행 유형: `AUTO` 정기 자동 배치 / `MANUAL` 수동 배치 |
| execution_cycle | ENUM | 배치 주기: `DAILY` 일일 배치 (24시간) / `MONTHLY` 월별 배치 (30일) |
| triggered_by | BIGINT | 수동 실행을 트리거한 개발자 ID (자동 배치 시 NULL, FK → users) |
| status | ENUM | 실행 상태: `RUNNING` 실행중 / `COMPLETED` 완료 / `FAILED` 실패 |
| total_count | INT | 배치 대상 총 건수 |
| success_count | INT | 성공 건수 |
| fail_count | INT | 실패 건수 |
| error_message | TEXT | 실패 시 에러 메시지 (성공 시 NULL) |
| started_at | DATETIME | 배치 시작 일시 |
| completed_at | DATETIME | 배치 완료 일시 (실행 중이거나 실패 시 NULL) |

---

## S 등급 산출 이력 `s_evaluation_history`

> S 등급 산출 결과 이력. 배치 실행마다 row가 추가되며 `is_latest`로 현재 등급을 식별한다.
⚠️ `is_latest` 갱신 시 반드시 트랜잭션으로 처리: 기존 레코드 FALSE → 새 레코드 TRUE
> 

**인덱스:**
- `idx_s_evaluation_user_latest` → (user_id, is_latest)
- `idx_s_evaluation_batch` → (batch_execution_id)

| 컬럼명 | 타입 | 설명 |
| --- | --- | --- |
| s_evaluation_id | BIGINT | S 등급 산출 고유 ID (PK) |
| user_id | BIGINT | 평가 대상 사업자 ID (FK → users) |
| result_id | BIGINT | SHAP 설명 ID (FK → shap_explanation) |
| biz_data_id | BIGINT | 산출에 사용된 My Biz Data ID (FK → my_biz_data) |
| batch_execution_id | BIGINT | 산출을 트리거한 배치 실행 ID (FK → batch_execution_history) |
| grade | VARCHAR(5) | S 등급 결과 (S1~S10, 산출 전 NULL) |
| score | DECIMAL(10,4) | LightGBM 모델 원점수 |
| is_latest | BOOLEAN | 현재 최신 등급 여부 (사용자별 가장 최근 산출에만 TRUE) |
| status | ENUM | 산출 상태: `PENDING` 대기 / `CALCULATING` 계산중 / `COMPLETED` 완료 / `FAILED` 실패 |
| evaluated_at | DATETIME | 등급 산출 완료 일시 |

---

## S 산출 요청 `s_calculation_request`

> 은행원이 특정 고객의 S 등급 산출을 요청한 이력.
대출 진행 시 자동으로 S 산출 요청이 들어가게 되며, 24시간 배치 시 이 부분에 대한 요청에 대해서만 S 등급 및 SHAP 산출이 이루어진다.
> 

**인덱스:**
- `idx_s_calc_request_status` → (status)
- `idx_s_calc_request_target_user` → (target_user_id)

| 컬럼명 | 타입 | 설명 |
| --- | --- | --- |
| request_id | BIGINT | 요청 고유 ID (PK) |
| user_id | BIGINT | 산출 대상 고객 ID (FK → users) |
| feature_id | BIGINT | 입력 피처 ID |
| status | ENUM | 요청 처리 상태: `REQUESTED` 요청됨 / `IN_PROGRESS` 처리중 / `COMPLETED` 완료 |
| requested_at | DATETIME | 요청 일시 |
| completed_at | DATETIME | 산출 완료 일시 |

---

## SHAP 설명 `shap_explanation`

> S등급 산출 근거를 설명하는 SHAP 기반 XAI 결과. 고객 리포트 및 은행원 심사 참고용으로 활용.
**BaseEntity 상속** (created_at 포함).
> 
> 
> **target_grade 규칙:** 현재 등급의 바로 위 등급 (예: S6 → S5). S1인 경우 target_grade = “S1” (최고 등급이므로 개선점 불필요).
> 
> **S1 등급 특수 처리:** s_grade = “S1”인 경우 improvement_keywords = [], improvement_details = {}, advice에 개선 조언 미포함.
> 

**인덱스:**
- `idx_shap_explanation_evaluation` → (evaluation_id)
- `idx_shap_explanation_user` → (user_id)

| 컬럼명 | 타입 | 설명 |
| --- | --- | --- |
| result_id | BIGINT | 결과 식별자 (PK) |
| evaluation_id | BIGINT | 산출 ID (FK → s_evaluation_history) |
| user_id | BIGINT | 사용자 ID (FK → users) |
| s_grade | VARCHAR(10) | 현재 등급 (예: “S6”) |
| target_grade | VARCHAR(10) | 목표 등급 (예: “S5”). S1이면 “S1” |
| strength_keywords | JSON | 강점 키워드 목록 (Array) |
| improvement_keywords | JSON | 개선점 키워드 목록 (Array). S1이면 빈 배열 [] |
| strength_details | JSON | 강점 상세 점수 Map (Key-Value) |
| improvement_details | JSON | 개선점 상세 점수 Map (Key-Value). S1이면 빈 객체 {} |
| advice | TEXT | AI 생성 조언 텍스트. S1이면 강점 유지 조언만 포함 |
| created_at | DATETIME | 데이터 생성 일시 |

---

## 배치 처리 규칙 요약

### 일일 배치 (DAILY, 24시간 주기)

- **대상**: 신규 가입 후 S등급 미산출 USER + 대출 신청한 USER
- **식별 방법**: `s_evaluation_history`에 해당 user_id 레코드가 없거나, `s_calculation_request`에 `REQUESTED` 상태인 건

### 월별 배치 (MONTHLY, 30일 주기)

- **대상**: 전체 회원
- **처리 방식**: 페이징(chunk) 단위로 커밋하여 전체 롤백 방지

### 멱등성 보장

- 배치 중간 실패 시 재실행 가능하도록 `batch_execution_id`로 이미 처리된 건 식별
- `is_latest` 갱신은 반드시 트랜잭션 단위로 처리 (이전 레코드 FALSE → 새 레코드 TRUE)