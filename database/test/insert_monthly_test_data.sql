-- ============================================================
-- 월별 배치 (MONTHLY) 테스트용 데이터
-- 시나리오:
--   - 3명의 사용자가 s_grade_feature에 존재 (전체 회원)
--   - user_id=1001에 대해 기존 REQUESTED 요청 1건 존재 (월별 배치가 흡수해야 함)
--   - user_id=1002, 1003은 REQUESTED 없이 피처만 존재 (월별 배치에서 신규 처리)
-- ============================================================

-- 1. s_grade_feature: 3명의 사용자 피처 데이터
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
-- user_id=1001: 성장세 매장 (기존 REQUESTED 요청 있음)
(1, 1, 1,
 24, 12.50, 8.30, 1.20,
 15000000.00, 14200000.00, 13500000.00,
 1, 5, 78.50,
 4.16, 3.10, 2.80,
 0.52, 0.45, 0.38,
 85.00, 1, 65.20, 0,
 'GROWING', 'GROWING', 4.8, 120, 4.5, 350,
 92.50, 1, 5, 3, 1, NOW()),
-- user_id=1002: 전통시장 오프라인 매장
(2, 2, 2,
 120, -2.10, 1.50, 0.85,
 8500000.00, 9000000.00, 8800000.00,
 3, 15, 12.00,
 -2.10, 0.75, 0.50,
 -0.02, 0.01, 0.01,
 30.00, 0, 40.00, 1,
 'STABLE', 'STABLE', 4.2, 15, 0.0, 0,
 80.00, 0, 15, 1, 0, NOW()),
-- user_id=1003: 온라인 중심 신규 매장
(3, 3, 3,
 6, 25.00, 0.00, 0.60,
 5000000.00, 4500000.00, 0.00,
 0, 2, 92.00,
 12.50, 0.00, 0.00,
 4.17, 0.00, 0.00,
 95.00, 1, 80.00, 0,
 'GROWING', 'GROWING', 4.9, 85, 4.7, 520,
 95.00, 1, 1, 2, 1, NOW());

-- 2. s_grade_history: user_id=1001에 대한 기존 REQUESTED 요청 1건
--    (월별 배치가 이 건을 흡수하여 COMPLETED로 변경해야 함)
INSERT INTO s_grade_history (
    s_grade_id, user_id, feature_id, batch_execution_id, status, requested_at, evaluated_at
) VALUES
(1, 1, 1, NULL, 'REQUESTED', NOW(), NULL);
