-- ============================================================
-- 재시도 전략 테스트용 데이터
-- 시나리오:
--   - request_id=1: 정상 REQUESTED (처리 성공 예상)
--   - request_id=2: IN_PROGRESS 고아 건 (이전 배치에서 비정상 종료, retry_count=0)
--                   → 배치 시작 시 REQUESTED로 복구되어 재시도
--   - request_id=3: IN_PROGRESS 고아 건 (retry_count=2, 이미 2회 실패)
--                   → 배치 시작 시 retry_count=3이 되어 FAILED 처리
-- ============================================================

-- 1. s_input_feature: 3명의 사용자 피처 데이터
INSERT INTO s_input_feature (
    feature_id, biz_data_id, user_id,
    business_age_months, quarterly_revenue_growth_rate, annual_revenue_growth_rate, revenue_vs_industry_avg_ratio,
    avg_monthly_transaction_3m, avg_monthly_transaction_6m, avg_monthly_transaction_12m,
    days_since_last_transaction, max_inactive_days, online_platform_activity_index,
    revenue_growth_per_employee_3m, revenue_growth_per_employee_6m, revenue_growth_per_employee_12m,
    revenue_growth_per_business_age_3m, revenue_growth_per_business_age_6m, revenue_growth_per_business_age_12m,
    online_accessibility_score, is_near_subway, commercial_saturation_score, is_traditional_market,
    commercial_trend, industry_trend, review_rating, review_count, delivery_rating, delivery_order_count,
    positive_review_ratio, has_online_reservation, owner_experience_years, employee_count, has_sns, created_at
) VALUES
(1, 101, 1001,
 24, 12.50, 8.30, 1.20,
 15000000.00, 14200000.00, 13500000.00,
 1, 5, 78.50,
 4.16, 3.10, 2.80,
 0.52, 0.45, 0.38,
 85.00, 1, 65.20, 0,
 'GROWING', 'GROWING', 4.8, 120, 4.5, 350,
 92.50, 1, 5, 3, 1, NOW()),
(2, 102, 1002,
 120, -2.10, 1.50, 0.85,
 8500000.00, 9000000.00, 8800000.00,
 3, 15, 12.00,
 -2.10, 0.75, 0.50,
 -0.02, 0.01, 0.01,
 30.00, 0, 40.00, 1,
 'STABLE', 'STABLE', 4.2, 15, 0.0, 0,
 80.00, 0, 15, 1, 0, NOW()),
(3, 103, 1003,
 6, 25.00, 0.00, 0.60,
 5000000.00, 4500000.00, 0.00,
 0, 2, 92.00,
 12.50, 0.00, 0.00,
 4.17, 0.00, 0.00,
 95.00, 1, 80.00, 0,
 'GROWING', 'GROWING', 4.9, 85, 4.7, 520,
 95.00, 1, 1, 2, 1, NOW());

-- 2. s_calculation_request: 다양한 상태의 요청
INSERT INTO s_calculation_request (
    request_id, target_user_id, s_evaluation_id, status, retry_count, error_message, requested_at, completed_at
) VALUES
-- 정상 REQUESTED (처리 성공 예상)
(1, 1001, NULL, 'REQUESTED', 0, NULL, NOW(), NULL),
-- IN_PROGRESS 고아 건 (retry_count=0 → 복구 후 retry_count=1, REQUESTED로 변경)
(2, 1002, NULL, 'IN_PROGRESS', 0, '이전 배치에서 비정상 종료', DATE_SUB(NOW(), INTERVAL 2 HOUR), NULL),
-- IN_PROGRESS 고아 건 (retry_count=2 → 복구 시 retry_count=3 → FAILED 처리)
(3, 1003, NULL, 'IN_PROGRESS', 2, '2회 연속 실패', DATE_SUB(NOW(), INTERVAL 3 HOUR), NULL);
