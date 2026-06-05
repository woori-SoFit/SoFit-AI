-- ====================================================================
-- 1. s_grade_feature 테이블 Mock Data (2건)
-- ====================================================================
-- 데이터 설명:
-- 1번째 행: 일반적인 성장세 매장 (분기/연간 매출 증가, 온라인 활성화 양호)
-- 2번째 행: 전통시장 내 위치한 오프라인 중심 매장 (배달 없음, 업력 김)
INSERT INTO s_grade_feature (
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
(
    1, 101, 1001,
    24, 12.50, 8.30, 1.20,
    15000000.00, 14200000.00, 13500000.00,
    1, 5, 78.50,
    4.16, 3.10, 2.80,
    0.52, 0.45, 0.38,
    85.00, true, 65.20, false,
    'GROWING', 'GROWING', 4.8, 120, 4.5, 350,
    92.50, true, 5, 3, true, NOW()
),
(
    2, 102, 1002,
    120, -2.10, 1.50, 0.85,
    8500000.00, 9000000.00, 8800000.00,
    3, 15, 12.00,
    -2.10, 0.75, 0.50,
    -0.02, 0.01, 0.01,
    30.00, false, 40.00, true,
    'STABLE', 'STABLE', 4.2, 15, 0.0, 0,
    80.00, false, 15, 1, false, NOW()
);

-- ====================================================================
-- 2. s_grade_history 테이블 Mock Data (2건)
-- ====================================================================
-- 데이터 설명:
-- 1번째 행: 1001번 고객이 대출 신청을 하여 배치 처리를 기다리는 요청 상태 (REQUESTED)
-- 2번째 행: 1002번 고객에 대해 요청된 상태 (REQUESTED)
INSERT INTO s_grade_history (
    s_grade_id, user_id, feature_id, batch_execution_id, status, requested_at, evaluated_at
) VALUES
(
    1, 1001, 1, NULL, 'REQUESTED', NOW(), NULL
),
(
    2, 1002, 2, NULL, 'REQUESTED', DATE_SUB(NOW(), INTERVAL 1 HOUR), NULL
);
