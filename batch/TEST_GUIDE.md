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

### 시나리오 1: 월별 배치 (MONTHLY) 테스트

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
python -m batch.run_batch
```

#### Step 4: 결과 확인
```sql
-- 1. 전체 사용자 등급 갱신 확인
SELECT s_grade_id, user_id, status, evaluated_at
FROM s_grade_history
WHERE status = 'COMPLETED';

-- 2. s_grade_report 결과 확인
SELECT s_grade_id, user_id, s_grade, target_grade
FROM s_grade_report;

-- 3. REQUESTED 건이 함께 COMPLETED 처리되었는지 확인
SELECT s_grade_id, user_id, status
FROM s_grade_history
WHERE user_id = 1;

-- 4. batch_execution_history 확인
SELECT execution_id, execution_cycle, status, total_count, success_count
FROM batch_execution_history;
```

#### 기대 결과
- `s_grade_history`: 3건 이상 `COMPLETED` (전체 사용자 + user_id=1의 기존 REQUESTED 건 흡수)
- `s_grade_report`: 3건 생성 (전체 사용자)
- `batch_execution_history`: `MONTHLY`, `COMPLETED`, success_count=3

---

### 시나리오 2: 수동 배치 트리거 테스트

**목적**: 은행원이 관리자 페이지에서 수동으로 월별 배치를 실행하는 경우

#### Step 1: 기존 데이터 초기화
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/reset_test_data.sql
```

#### Step 2: 월별 배치용 테스트 데이터 삽입
```bash
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/insert_monthly_test_data.sql
```

#### Step 3: 수동 배치 실행
```bash
python -m batch.run_batch --type manual --triggered-by 2001
```

#### Step 4: 결과 확인
```sql
-- batch_execution_history에서 MANUAL 확인
SELECT execution_id, execution_type, triggered_by, status
FROM batch_execution_history;
```

#### 기대 결과
- `batch_execution_history`: `execution_type=MANUAL`, `triggered_by=2001`

---

## 빠른 전체 테스트 (한 번에 실행)

```bash
# 1. 초기화
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/reset_test_data.sql

# 2. 월별 배치 테스트
mysql -h $DB_HOST -u $DB_USERNAME -p sofit < database/test/insert_monthly_test_data.sql
python -m batch.run_batch
echo "=== 월별 배치 완료 ==="
```

---

## 참고

- 건별 S등급 산출은 FastAPI 서빙 서버에서 처리됩니다 (일일 배치 제거됨).
- 재시도 전략: 배치 내부 메모리에서 최대 3회 재시도 후 FAILED 처리.
