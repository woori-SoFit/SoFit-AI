# Spring Boot 인수인계 문서 — S등급 배치 연동

## 개요

Python 배치와 Spring Boot 간의 연동 사항을 정리한 문서입니다.
Python 배치 리팩토링 완료 후, Spring Boot 쪽에서 맞춰야 할 변경사항을 기술합니다.

> **변경사항**: 일일 배치(DAILY)가 제거되었습니다.
> 건별 S등급 산출은 FastAPI 서빙 서버에서 처리합니다.
> 월별 배치(MONTHLY)만 Python 배치로 유지됩니다.

---

## 1. 테이블 변경 요약

### 삭제된 테이블
- `s_calculation_request` → 없어짐
- `s_evaluation_history` → 없어짐
- `shap_explanation` → 없어짐
- `s_input_feature` → 이름 변경

### 신규/변경 테이블

| 기존 | 변경 후 | 비고 |
|---|---|---|
| `s_input_feature` | `s_grade_feature` | 테이블명 변경 + `user_id` 컬럼 제거 |
| `s_calculation_request` | `s_grade_history` | 구조 대폭 변경 |
| `s_evaluation_history` + `shap_explanation` | `s_grade_history` + `s_grade_report` | 2개 테이블로 분리 재구성 |

### `s_grade_feature` 변경사항
- `user_id` 컬럼 **제거됨**
- 사용자 식별: `biz_data_id` → `my_biz_data.business_number`로 JOIN하여 식별

---

## 2. `s_grade_history` — Spring Boot가 INSERT하는 테이블

### 컬럼 구조

| 컬럼 | 타입 | Spring Boot 역할 |
|---|---|---|
| `s_grade_id` | BIGINT AUTO_INCREMENT | PK, 자동생성 |
| `user_id` | BIGINT NOT NULL | 대출 신청한 고객 ID |
| `feature_id` | BIGINT NULL (FK → s_grade_feature) | 해당 사용자의 최신 `s_grade_feature.feature_id` |
| `batch_execution_id` | BIGINT NULL (FK → batch_execution_history) | **NULL로 INSERT** (Python이 나중에 채움) |
| `status` | ENUM | **'REQUESTED'로 INSERT** |
| `requested_at` | DATETIME | NOW() |
| `evaluated_at` | DATETIME NULL | NULL (Python이 완료 시 채움) |

### Spring Boot가 해야 할 일

> **참고**: 일일 배치가 제거되었으므로, `s_grade_history`에 REQUESTED INSERT는
> 건별 산출 시 FastAPI 호출 전/후 흐름에서 관리합니다. (상세는 별도 안내 예정)

---

## 3. `s_grade_feature` — Spring Boot가 INSERT하는 테이블

기존 `s_input_feature`에서 테이블명 변경 + `user_id` 컬럼 제거.

- `user_id` 컬럼이 없어졌으므로, 사용자 식별은 `biz_data_id` → `my_biz_data.business_number`로 JOIN하여 수행
- My Biz Data 수집 완료 후 피처 가공 결과를 INSERT하는 로직에서 `user_id` 제거

---

## 4. 수동 배치 트리거 (은행원 관리자 페이지)

### 흐름

```
프론트 (관리자 페이지)
  → POST /admin/batch/trigger
  → Spring Boot admin-backend
      1. 세션에서 은행원 user_id 추출 (triggered_by용)
      2. 대상 s_grade_history FAILED → REQUESTED로 복구
      3. ProcessBuilder로 Python 월별 배치 실행
  → 프론트에 "배치 트리거 완료" 응답
```

### Step 2: FAILED → REQUESTED 복구

```sql
UPDATE s_grade_history
SET status = 'REQUESTED'
WHERE user_id IN (#{targetUserIds})
  AND status = 'FAILED';
```

### Step 3: Python 배치 CLI 실행

```java
ProcessBuilder pb = new ProcessBuilder(
    "python3", "-m", "batch.run_batch",
    "--type", "manual",
    "--triggered-by", String.valueOf(adminUserId)
);
pb.directory(new File("/app/SoFit-AI"));  // 프로젝트 루트
pb.redirectErrorStream(true);
Process process = pb.start();
```

### CLI 옵션 설명

| 옵션 | 값 | 설명 |
|---|---|---|
| `--type` | `auto` / `manual` | 실행 유형. manual이면 batch_execution_history에 MANUAL로 기록 |
| `--triggered-by` | int | 트리거한 은행원 user_id. manual일 때 필수 |

---

## 5. `s_grade_report` — Python이 INSERT, Spring Boot가 READ

### 컬럼 구조 (조회용)

| 컬럼 | 설명 | 사용처 |
|---|---|---|
| `s_grade_id` | PK (= s_grade_history.s_grade_id) | JOIN 키 |
| `user_id` | 사용자 ID | 조회 필터 |
| `s_grade` | 산출된 등급 (S1~S10) | 고객 리포트, 은행원 심사 |
| `target_grade` | 목표 등급 (한 단계 위) | 리포트 |
| `strength_keywords` | JSON Array (한국어) | 고객 리포트 |
| `improvement_keywords` | JSON Array (한국어) | 고객 리포트 |
| `strength_details` | JSON Object {키워드: SHAP값} | 은행원 심사 |
| `improvement_details` | JSON Object {키워드: SHAP값} | 은행원 심사 |
| `user_advice` | TEXT (LLM 생성) | 고객 리포트 |
| `admin_advice` | TEXT (LLM 생성) | 은행원 심사 화면 |

### 조회 예시

```sql
-- 고객용: 최신 등급 리포트
SELECT r.s_grade, r.target_grade, r.strength_keywords,
       r.improvement_keywords, r.user_advice
FROM s_grade_report r
JOIN s_grade_history h ON h.s_grade_id = r.s_grade_id
WHERE h.user_id = #{userId} AND h.status = 'COMPLETED'
ORDER BY h.evaluated_at DESC
LIMIT 1;

-- 은행원용: 심사 화면 (상세 포함)
SELECT r.*
FROM s_grade_report r
JOIN s_grade_history h ON h.s_grade_id = r.s_grade_id
WHERE h.user_id = #{userId} AND h.status = 'COMPLETED'
ORDER BY h.evaluated_at DESC
LIMIT 1;
```

---

## 6. `batch_execution_history` — Python이 INSERT/UPDATE, Spring Boot가 READ

### 관리자 배치 이력 조회

```sql
SELECT execution_id, execution_type, execution_cycle,
       triggered_by, status, total_count, success_count, fail_count,
       started_at, completed_at
FROM batch_execution_history
ORDER BY started_at DESC;
```

---

## 7. 상태 ENUM 정리

### s_grade_history.status
| 값 | 설명 | 누가 설정 |
|---|---|---|
| `REQUESTED` | 산출 요청됨 | Spring Boot (INSERT 시) |
| `CALCULATING` | 산출 중 | Python (배치 처리 시작 시) |
| `COMPLETED` | 완료 | Python (배치 처리 완료 시) |
| `FAILED` | 실패 (3회 재시도 후) | Python (최종 실패 시) |

### batch_execution_history.status
| 값 | 설명 |
|---|---|
| `RUNNING` | 배치 실행 중 |
| `COMPLETED` | 배치 정상 완료 |
| `FAILED` | 1건 이상 실패 |

---

## 8. 체크리스트

Spring Boot에서 변경해야 할 사항:

- [ ] Entity 변경: `SCalculationRequest` → `SGradeHistory` (새 구조)
- [ ] Entity 변경: `SInputFeature` → `SGradeFeature` (테이블명 변경 + `user_id` 컬럼 제거)
- [ ] Entity 변경: `SEvaluationHistory` 삭제
- [ ] Entity 변경: `ShapExplanation` → `SGradeReport` (새 구조, READ 전용)
- [ ] `s_grade_feature` INSERT 로직에서 `user_id` 제거 (사용자 식별은 `biz_data_id` → `my_biz_data` JOIN)
- [ ] 건별 S등급 산출: FastAPI 서빙 서버 호출로 변경 (일일 배치 제거)
- [ ] 성장S등급 조회 API: `s_grade_report` JOIN `s_grade_history` 조회로 변경
- [ ] 관리자 수동 배치 API: FAILED → REQUESTED 복구 + ProcessBuilder로 Python 월별 배치 실행 (`--cycle` 옵션 제거)
- [ ] 배치 이력 조회 API: `batch_execution_history` 조회 (기존과 동일)
