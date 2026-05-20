# 배치 테스트 가이드

## 사전 준비

### 1. 환경변수 확인
프로젝트 루트의 `.env` 파일에 아래 값이 설정되어 있어야 합니다:
```
DB_HOST=<호스트>
DB_USERNAME=<유저이름>
DB_PASSWORD=<비밀번호>
GEMINI_API_KEY=<API키>
```

### 2. 패키지 설치
```bash
pip install -r batch/requirements.txt
```

### 3. 모델 파일 확인
```bash
ls models/scb_model_v1.pkl
```

### 4. DB 테이블 생성 (최초 1회)
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/ddl/V1__create_s_grade_tables.sql
```

---

## 테스트 시나리오

### 시나리오 1: 일일 배치 (DAILY) 테스트

**목적**: `s_calculation_request`에 REQUESTED 상태인 건만 처리되는지 확인

#### Step 1: 기존 데이터 초기화
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/reset_test_data.sql
```

#### Step 2: 일일 배치용 테스트 데이터 삽입
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/insert_daily_test_data.sql
```

#### Step 3: 배치 실행
```bash
python -m batch.run_batch --cycle daily
```

#### Step 4: 결과 확인
```sql
-- 1. s_calculation_request 상태 확인 (COMPLETED여야 함)
SELECT request_id, target_user_id, status, retry_count, completed_at
FROM s_calculation_request;

-- 2. s_evaluation_history 확인 (is_latest=1인 레코드 생성)
SELECT s_evaluation_id, user_id, grade, score, is_latest, status
FROM s_evaluation_history;

-- 3. shap_explanation 확인 (강점/개선 키워드 생성)
SELECT result_id, user_id, s_grade, target_grade,
       strength_keywords, improvement_keywords, advice
FROM shap_explanation;

-- 4. batch_execution_history 확인
SELECT execution_id, execution_cycle, status, total_count, success_count, fail_count
FROM batch_execution_history;
```

#### 기대 결과
- `s_calculation_request`: 2건 모두 `COMPLETED`
- `s_evaluation_history`: 2건 생성, `is_latest=1`
- `shap_explanation`: 2건 생성, 키워드/상세 포함
- `batch_execution_history`: `DAILY`, `COMPLETED`, success_count=2

---

### 시나리오 2: 월별 배치 (MONTHLY) 테스트

**목적**: 전체 사용자 등급 갱신 + REQUESTED 건 흡수 확인

#### Step 1: 기존 데이터 초기화
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/reset_test_data.sql
```

#### Step 2: 월별 배치용 테스트 데이터 삽입
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/insert_monthly_test_data.sql
```

#### Step 3: 배치 실행
```bash
python -m batch.run_batch --cycle monthly
```

#### Step 4: 결과 확인
```sql
-- 1. 전체 사용자 등급 갱신 확인
SELECT s_evaluation_id, user_id, grade, score, is_latest
FROM s_evaluation_history
WHERE is_latest = 1;

-- 2. REQUESTED 건이 함께 COMPLETED 처리되었는지 확인
SELECT request_id, target_user_id, status, s_evaluation_id
FROM s_calculation_request;

-- 3. batch_execution_history 확인
SELECT execution_id, execution_cycle, status, total_count, success_count
FROM batch_execution_history;
```

#### 기대 결과
- `s_evaluation_history`: 3건 생성 (전체 사용자), 모두 `is_latest=1`
- `s_calculation_request`: user_id=1001의 REQUESTED 건이 `COMPLETED`로 변경
- `batch_execution_history`: `MONTHLY`, `COMPLETED`, success_count=3

---

### 시나리오 3: 재시도 전략 테스트

**목적**: 실패 건이 REQUESTED로 롤백되고, 3회 초과 시 FAILED 처리되는지 확인

#### Step 1: 기존 데이터 초기화
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/reset_test_data.sql
```

#### Step 2: 재시도 테스트 데이터 삽입
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/insert_retry_test_data.sql
```

#### Step 3: 배치 실행
```bash
python -m batch.run_batch --cycle daily
```

#### Step 4: 결과 확인
```sql
-- IN_PROGRESS 고아 건이 복구되었는지 확인
SELECT request_id, status, retry_count, error_message
FROM s_calculation_request
ORDER BY request_id;
```

#### 기대 결과
- request_id=1: `COMPLETED` (정상 처리)
- request_id=2: `REQUESTED`, retry_count=1 (고아 건 복구됨, 다음 배치에서 재시도)
- request_id=3: `FAILED`, retry_count=3 (최대 재시도 초과)

---

## 빠른 전체 테스트 (한 번에 실행)

```bash
# 1. 초기화
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/reset_test_data.sql

# 2. 일일 배치 테스트
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/insert_daily_test_data.sql
python -m batch.run_batch --cycle daily
echo "=== 일일 배치 완료 ==="

# 3. 초기화 후 월별 배치 테스트
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/reset_test_data.sql
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/insert_monthly_test_data.sql
python -m batch.run_batch --cycle monthly
echo "=== 월별 배치 완료 ==="
```
