-- ============================================================
-- SoFit S등급 관련 테이블 DDL
-- 버전: V1
-- 설명: S등급 산출에 필요한 테이블 생성 (입력 피처, 배치 이력, 산출 이력, 산출 요청, SHAP 설명)
-- 대상 DB: sofit (MySQL 8.x)
-- ============================================================

-- ------------------------------------------------------------
-- 1. 배치 실행 이력
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch_execution_history (
    execution_id        BIGINT          NOT NULL AUTO_INCREMENT,
    execution_type      ENUM('AUTO', 'MANUAL') NOT NULL COMMENT '실행 유형: AUTO 정기 자동 / MANUAL 수동',
    execution_cycle     ENUM('DAILY', 'MONTHLY') NOT NULL COMMENT '배치 주기: DAILY 일일(24h) / MONTHLY 월별(30d)',
    triggered_by        BIGINT          NULL COMMENT '수동 실행 트리거 개발자 ID (자동 시 NULL)',
    status              ENUM('RUNNING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'RUNNING' COMMENT '실행 상태',
    total_count         INT             NOT NULL DEFAULT 0 COMMENT '배치 대상 총 건수',
    success_count       INT             NOT NULL DEFAULT 0 COMMENT '성공 건수',
    fail_count          INT             NOT NULL DEFAULT 0 COMMENT '실패 건수',
    error_message       TEXT            NULL COMMENT '실패 시 에러 메시지',
    started_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '배치 시작 일시',
    completed_at        DATETIME        NULL COMMENT '배치 완료 일시',

    PRIMARY KEY (execution_id),
    INDEX idx_batch_execution_status (status),
    INDEX idx_batch_execution_cycle_started (execution_cycle, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Python Batch 실행 이력. AUTO/MANUAL, DAILY/MONTHLY 구분';

-- ------------------------------------------------------------
-- 2. S 입력 피처
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS s_input_feature (
    feature_id                          BIGINT          NOT NULL AUTO_INCREMENT,
    biz_data_id                         BIGINT          NOT NULL COMMENT '원본 My Biz Data ID',
    user_id                             BIGINT          NOT NULL COMMENT '사업자 사용자 ID',

    -- 계량 변수 (A)
    business_age_months                 INT             NOT NULL COMMENT 'A1: 업력 (개월)',
    quarterly_revenue_growth_rate       DECIMAL(5,2)    NOT NULL COMMENT 'A2: 전분기 대비 최근분기 매출증가율 (%)',
    annual_revenue_growth_rate          DECIMAL(5,2)    NOT NULL COMMENT 'A3: 전년도 대비 최근년도 매출증가율 (%)',
    revenue_vs_industry_avg_ratio       DECIMAL(5,2)    NOT NULL COMMENT 'A4: 매출/동일업종 평균매출 비율',
    avg_monthly_transaction_3m          DECIMAL(15,2)   NOT NULL COMMENT 'A5: 최근 3개월 평균 거래금액 (원)',
    avg_monthly_transaction_6m          DECIMAL(15,2)   NOT NULL COMMENT 'A5: 최근 6개월 평균 거래금액 (원)',
    avg_monthly_transaction_12m         DECIMAL(15,2)   NOT NULL COMMENT 'A5: 최근 12개월 평균 거래금액 (원)',
    days_since_last_transaction         INT             NOT NULL COMMENT 'A6: 최종 결제일로부터의 기간 (일)',
    max_inactive_days                   INT             NOT NULL COMMENT 'A7: 최장 영업징후 부재기간 (일)',
    online_platform_activity_index      DECIMAL(5,2)    NOT NULL COMMENT 'A8: 온라인 플랫폼 활동성·성장성 지수',
    revenue_growth_per_employee_3m      DECIMAL(5,2)    NOT NULL COMMENT 'A9: 매출증가율/근로자수 (3개월)',
    revenue_growth_per_employee_6m      DECIMAL(5,2)    NOT NULL COMMENT 'A9: 매출증가율/근로자수 (6개월)',
    revenue_growth_per_employee_12m     DECIMAL(5,2)    NOT NULL COMMENT 'A9: 매출증가율/근로자수 (12개월)',
    revenue_growth_per_business_age_3m  DECIMAL(5,2)    NOT NULL COMMENT 'A10: 매출증가율/업력 (3개월)',
    revenue_growth_per_business_age_6m  DECIMAL(5,2)    NOT NULL COMMENT 'A10: 매출증가율/업력 (6개월)',
    revenue_growth_per_business_age_12m DECIMAL(5,2)    NOT NULL COMMENT 'A10: 매출증가율/업력 (12개월)',

    -- 비계량 변수 (B)
    online_accessibility_score          DECIMAL(5,2)    NOT NULL COMMENT 'B1: 사업장 온라인 정보 접근성 점수',
    is_near_subway                      TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'B2: 역세권 여부 (500m 이내)',
    commercial_saturation_score         DECIMAL(5,2)    NOT NULL COMMENT 'B3: 상권 포화도 점수',
    is_traditional_market               TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'B3: 전통시장 여부',
    commercial_trend                    ENUM('GROWING', 'STABLE', 'DECLINING') NOT NULL COMMENT 'B3: 상권 트렌드',
    industry_trend                      ENUM('GROWING', 'STABLE', 'DECLINING') NOT NULL COMMENT 'B4: 업종 트렌드',
    review_rating                       DECIMAL(3,1)    NOT NULL DEFAULT 0.0 COMMENT 'B5: 평점',
    review_count                        INT             NOT NULL DEFAULT 0 COMMENT 'B5: 리뷰 수',
    delivery_rating                     DECIMAL(3,1)    NOT NULL DEFAULT 0.0 COMMENT 'B5: 배달앱 평점',
    delivery_order_count                INT             NOT NULL DEFAULT 0 COMMENT 'B5: 배달앱 주문 수',
    positive_review_ratio               DECIMAL(5,2)    NOT NULL DEFAULT 0.00 COMMENT 'B5: 긍정 리뷰 비율 (%)',
    has_online_reservation              TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'B5: 온라인 예약 여부',
    owner_experience_years              INT             NOT NULL DEFAULT 0 COMMENT 'B6: 경영주 동업종 경력 (년)',
    employee_count                      INT             NOT NULL DEFAULT 0 COMMENT 'B6: 직원 수',
    has_sns                             TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'B6: SNS 운영 여부',

    created_at                          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '피처 생성 일시',

    PRIMARY KEY (feature_id),
    INDEX idx_s_input_feature_user_created (user_id, created_at),
    INDEX idx_s_input_feature_biz_data (biz_data_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='My Biz Data → LightGBM 모델 입력용 계량·비계량 변수 가공 결과';

-- ------------------------------------------------------------
-- 3. S 등급 산출 이력
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS s_evaluation_history (
    s_evaluation_id     BIGINT          NOT NULL AUTO_INCREMENT,
    user_id             BIGINT          NOT NULL COMMENT '평가 대상 사업자 ID',
    result_id           BIGINT          NULL COMMENT 'SHAP 설명 ID (산출 완료 후 설정)',
    biz_data_id         BIGINT          NOT NULL COMMENT '산출에 사용된 My Biz Data ID',
    batch_execution_id  BIGINT          NOT NULL COMMENT '산출을 트리거한 배치 실행 ID',
    grade               VARCHAR(5)      NULL COMMENT 'S 등급 결과 (S1~S10, 산출 전 NULL)',
    score               DECIMAL(10,4)   NULL COMMENT 'LightGBM 모델 원점수',
    is_latest           TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '현재 최신 등급 여부 (사용자별 최근 산출에만 1)',
    status              ENUM('PENDING', 'CALCULATING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'PENDING' COMMENT '산출 상태',
    evaluated_at        DATETIME        NULL COMMENT '등급 산출 완료 일시',

    PRIMARY KEY (s_evaluation_id),
    INDEX idx_s_evaluation_user_latest (user_id, is_latest),
    INDEX idx_s_evaluation_batch (batch_execution_id),
    CONSTRAINT fk_s_evaluation_batch
        FOREIGN KEY (batch_execution_id) REFERENCES batch_execution_history (execution_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='S 등급 산출 결과 이력. is_latest 갱신 시 트랜잭션 필수';

-- ------------------------------------------------------------
-- 4. S 산출 요청 (은행원 개별 요청)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS s_calculation_request (
    request_id          BIGINT          NOT NULL AUTO_INCREMENT,
    target_user_id      BIGINT          NOT NULL COMMENT '산출 대상 고객 ID',
    s_evaluation_id     BIGINT          NULL COMMENT '산출 결과 ID (완료 전 NULL)',
    status              ENUM('REQUESTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'REQUESTED' COMMENT '요청 처리 상태',
    retry_count         INT             NOT NULL DEFAULT 0 COMMENT '재시도 횟수 (최대 3회 초과 시 FAILED)',
    error_message       TEXT            NULL COMMENT '최종 실패 시 에러 메시지',
    requested_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '요청 일시',
    completed_at        DATETIME        NULL COMMENT '산출 완료 일시',

    PRIMARY KEY (request_id),
    INDEX idx_s_calc_request_status (status),
    INDEX idx_s_calc_request_target_user (target_user_id),
    CONSTRAINT fk_s_calc_request_evaluation
        FOREIGN KEY (s_evaluation_id) REFERENCES s_evaluation_history (s_evaluation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='은행원 개별 S등급 산출 요청. 배치와 별도로 즉시 산출 트리거';

-- ------------------------------------------------------------
-- 5. SHAP 설명
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shap_explanation (
    result_id               BIGINT          NOT NULL AUTO_INCREMENT,
    evaluation_id           BIGINT          NOT NULL COMMENT '산출 ID',
    user_id                 BIGINT          NOT NULL COMMENT '사용자 ID',
    s_grade                 VARCHAR(10)     NOT NULL COMMENT '현재 등급 (예: S6)',
    target_grade            VARCHAR(10)     NOT NULL COMMENT '목표 등급 (예: S5). S1이면 S1',
    strength_keywords       JSON            NOT NULL COMMENT '강점 키워드 목록 (Array)',
    improvement_keywords    JSON            NOT NULL COMMENT '개선점 키워드 목록 (Array). S1이면 []',
    strength_details        JSON            NOT NULL COMMENT '강점 상세 점수 Map (Key-Value)',
    improvement_details     JSON            NOT NULL COMMENT '개선점 상세 점수 Map (Key-Value). S1이면 {}',
    advice                  TEXT            NOT NULL COMMENT 'AI 생성 조언. S1이면 강점 유지 조언만 포함',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성 일시',

    PRIMARY KEY (result_id),
    INDEX idx_shap_explanation_evaluation (evaluation_id),
    INDEX idx_shap_explanation_user (user_id),
    CONSTRAINT fk_shap_evaluation
        FOREIGN KEY (evaluation_id) REFERENCES s_evaluation_history (s_evaluation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='SHAP 기반 XAI 결과. target_grade: 현재 등급 바로 위. S1이면 개선점 미생성';

-- ------------------------------------------------------------
-- 6. s_evaluation_history.result_id FK 추가 (순환 참조 방지를 위해 후순위 설정)
-- ------------------------------------------------------------
ALTER TABLE s_evaluation_history
    ADD CONSTRAINT fk_s_evaluation_result
        FOREIGN KEY (result_id) REFERENCES shap_explanation (result_id);
