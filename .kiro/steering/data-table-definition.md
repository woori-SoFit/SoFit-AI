# 테이블 명세서 (임시파일)

### S 입력 피처 `s_input_feature`

> **BaseEntity 상속** (created_at 포함). My Biz Data를 LightGBM 모델 입력용 계량·비계량 변수로 가공한 결과. 배치 실행 시 이 테이블의 데이터를 AI 서버에 전달한다.
> 

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