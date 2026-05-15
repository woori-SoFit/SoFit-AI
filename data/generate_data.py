"""
SoFit AI - 합성 학습 데이터 생성기 (고도화 버전)

[설계 원칙]
- 단순 랜덤이 아닌 '현재 지표 → 1년 뒤 성과' 시뮬레이션 기반 라벨링
- 변수 간 논리적 상관관계 유지 (매출 ↑ → 리뷰 수 ↑ 등)
- 비선형 성공 패턴 반영 (직원 적어도 온라인 활동성 높으면 고성장 가능)
- 외부 노이즈(경기 변동, 지역 특성) 추가로 현실적 오차 포함
- s_input_feature 테이블 명세서의 모든 컬럼(A1~B6) 포함
"""

import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ── 설정 ────────────────────────────────────────────────────
# N = 10_000
N=30
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)


# ── 1단계: 잠재적 성장 역량(Latent Growth Potential) 생성 ──
# 각 사업체의 '숨겨진 성장 역량'을 먼저 정의.
# 이 값이 피처 생성과 라벨링 모두에 영향을 주어 변수 간 상관관계를 만든다.
def _generate_latent_potential(n: int) -> np.ndarray:
    """
    0~1 사이의 잠재 성장 역량 점수.
    S1(최고) 방향으로 갈수록 1에 가까움.
    베타 분포로 중간 등급에 데이터가 몰리도록 설계.
    """
    return np.random.beta(a=2.0, b=2.0, size=n)


def generate_data(n: int = N) -> pd.DataFrame:
    lp = _generate_latent_potential(n)  # 잠재 성장 역량 (0~1)

    # ── 2단계: 계량 변수 (A) 생성 ───────────────────────────

    # A1: 업력 (개월) — 잠재력과 약한 양의 상관 (오래된 가게가 안정적이나 신생도 고성장 가능)
    business_age_months = np.clip(
        (np.random.normal(36, 24, n) + lp * 20).astype(int), 1, 120
    )

    # A2, A3: 매출증가율 — 잠재력이 높을수록 성장률 높음 + 노이즈
    quarterly_revenue_growth_rate = np.round(
        np.random.normal(2.0, 8.0, n) + lp * 20, 2
    )
    annual_revenue_growth_rate = np.round(
        np.random.normal(5.0, 15.0, n) + lp * 40, 2
    )

    # A4: 매출/업종평균 비율 — 잠재력과 양의 상관
    revenue_vs_industry_avg_ratio = np.round(
        np.clip(np.random.normal(1.0, 0.4, n) + lp * 0.6, 0.3, 3.0), 2
    )

    # TODO: 수치 고쳐야 함. 값 너무 높음 
    # A5: 평균 거래금액 — 잠재력이 높을수록 매출 높음 (로그 정규 분포)
    base_revenue = np.exp(
        np.random.normal(np.log(15_000_000), 0.8, n) + lp * 1.0
    )
    avg_monthly_transaction_3m = np.round(
        np.clip(base_revenue, 3_000_000, 80_000_000), 2
    )
    # 6개월, 12개월은 3개월 기준에서 약간의 변동
    avg_monthly_transaction_6m = np.round(
        np.clip(avg_monthly_transaction_3m * np.random.uniform(0.88, 1.12, n),
                3_000_000, 80_000_000), 2
    )
    avg_monthly_transaction_12m = np.round(
        np.clip(avg_monthly_transaction_6m * np.random.uniform(0.88, 1.12, n),
                3_000_000, 80_000_000), 2
    )

    # A6: 최종 결제일로부터의 기간 — 잠재력 높을수록 최근 거래 (짧음)
    days_since_last_transaction = np.clip(
        (np.random.exponential(3, n) * (1 - lp * 0.7)).astype(int), 0, 30
    )

    # A7: 최장 영업 부재기간 — 잠재력 높을수록 짧음
    max_inactive_days = np.clip(
        (np.random.exponential(5, n) * (1 - lp * 0.6)).astype(int), 0, 60
    )

    # A8: 온라인 플랫폼 활동성 지수 — 잠재력과 강한 양의 상관
    online_platform_activity_index = np.round(
        np.clip(np.random.normal(50, 20, n) + lp * 30, 0, 100), 2
    )

    # B6 먼저 생성 (A9 계산에 필요)
    employee_count = np.clip(
        (np.random.randint(1, 5, n)).astype(int), 1, 4
    )

    # 경영주 경력
    owner_experience_years = np.clip(
        (np.random.normal(3, 4, n) + lp * 5).astype(int), 1, 30
    )
    has_sns = np.random.random(n) < (0.3 + lp * 0.6)  # 잠재력 높을수록 SNS 운영 확률 높음

    # A9: 매출증가율 / 근로자수
    revenue_growth_per_employee_3m = np.round(
        quarterly_revenue_growth_rate / employee_count, 2
    )
    revenue_growth_per_employee_6m = np.round(
        (quarterly_revenue_growth_rate * 1.1) / employee_count, 2
    )
    revenue_growth_per_employee_12m = np.round(
        annual_revenue_growth_rate / employee_count, 2
    )

    # A10: 매출증가율 / 업력
    revenue_growth_per_business_age_3m = np.round(
        quarterly_revenue_growth_rate / business_age_months, 4
    )
    revenue_growth_per_business_age_6m = np.round(
        (quarterly_revenue_growth_rate * 1.1) / business_age_months, 4
    )
    revenue_growth_per_business_age_12m = np.round(
        annual_revenue_growth_rate / business_age_months, 4
    )

    # ── 3단계: 비계량 변수 (B) 생성 ─────────────────────────

    # B1: 온라인 접근성 점수 — 온라인 활동성과 양의 상관
    online_accessibility_score = np.round(
        np.clip(online_platform_activity_index * 0.7
                + np.random.normal(20, 10, n), 0, 100), 2
    )

    # B2: 역세권 여부 — 잠재력과 약한 양의 상관
    is_near_subway = np.random.random(n) < (0.2 + lp * 0.3)

    # B3: 상권 포화도, 전통시장, 상권 트렌드
    commercial_saturation_score = np.round(
        np.clip(np.random.normal(65, 15, n), 20, 100), 2
    )
    is_traditional_market = np.random.random(n) < 0.2

    # 상권 트렌드: 잠재력 높을수록 GROWING 상권에 위치할 확률 높음
    commercial_trend_raw = np.random.random(n)
    growing_threshold = 0.1 + lp * 0.3
    stable_threshold = growing_threshold + 0.5
    commercial_trend = np.where(
        commercial_trend_raw < growing_threshold, 'GROWING',
        np.where(commercial_trend_raw < stable_threshold, 'STABLE', 'DECLINING')
    )

    # B4: 업종 트렌드
    industry_trend_raw = np.random.random(n)
    ind_growing = 0.1 + lp * 0.35
    ind_stable = ind_growing + 0.55
    industry_trend = np.where(
        industry_trend_raw < ind_growing, 'GROWING',
        np.where(industry_trend_raw < ind_stable, 'STABLE', 'DECLINING')
    )

    # B5: 리뷰 관련 — 매출과 양의 상관 (매출 높으면 리뷰 많음)
    revenue_normalized = (avg_monthly_transaction_3m - 3_000_000) / (80_000_000 - 3_000_000)

    review_rating = np.round(
        np.clip(np.random.normal(3.8, 0.5, n) + lp * 0.8, 1.0, 5.0), 1
    )
    review_count = np.clip(
        (np.random.exponential(100, n) * (0.3 + revenue_normalized * 2)
         + lp * 200).astype(int), 0, 2000
    )
    delivery_rating = np.round(
        np.clip(review_rating + np.random.normal(0, 0.2, n), 1.0, 5.0), 1
    )
    delivery_order_count = np.clip(
        (np.random.exponential(200, n) * (0.2 + online_platform_activity_index / 100 * 3)
         + lp * 500).astype(int), 0, 5000
    )
    positive_review_ratio = np.round(
        np.clip(60 + review_rating * 6 + np.random.normal(0, 5, n), 40, 100), 2
    )
    has_online_reservation = np.random.random(n) < (0.2 + lp * 0.5)

    # ── 4단계: 미래 성과 시뮬레이션 → S등급 라벨링 ──────────

    # [핵심 설계]
    # '1년 뒤 성과 점수(future_score)'를 여러 시나리오로 계산.
    # 단순 합산이 아닌 비선형 상호작용 항을 포함하여
    # 모델이 복잡한 패턴을 학습할 수 있도록 설계.

    # 기본 성장 동력 (매출 성장 + 업종/상권 환경)
    growth_momentum = (
        annual_revenue_growth_rate / 100 * 0.25
        + quarterly_revenue_growth_rate / 100 * 0.15
        + revenue_vs_industry_avg_ratio * 0.10
    )

    # 온라인 전환 역량 (비선형: 활동성 × 접근성 × SNS 시너지)
    online_synergy = (
        (online_platform_activity_index / 100)
        * (online_accessibility_score / 100)
        * (1 + has_sns.astype(float) * 0.5)
        * 0.20
    )

    # 고객 신뢰도 (리뷰 평점 × 긍정 비율 — 리뷰 수가 적으면 신뢰도 낮춤)
    review_credibility = np.log1p(review_count) / np.log1p(2000)
    customer_trust = (
        (review_rating / 5) * (positive_review_ratio / 100) * review_credibility * 0.15
    )

    # 운영 안정성 (결제 공백 없음 + 업력)
    operational_stability = (
        (1 - days_since_last_transaction / 30) * 0.08
        + np.log1p(business_age_months) / np.log1p(120) * 0.05
    )

    # 입지 프리미엄 (역세권 × 상권 트렌드)
    location_premium = (
        is_near_subway.astype(float) * 0.03
        + (commercial_trend == 'GROWING').astype(float) * 0.04
        - (commercial_trend == 'DECLINING').astype(float) * 0.03
        + (industry_trend == 'GROWING').astype(float) * 0.03
        - (industry_trend == 'DECLINING').astype(float) * 0.02
    )

    # [비선형 상호작용 항]
    # "직원 적어도 온라인 활동성 높으면 고성장" 시나리오
    lean_online_bonus = np.where(
        (employee_count <= 2) & (online_platform_activity_index > 70),
        0.08, 0.0
    )
    # "경험 많은 사장 + SNS + 배달 활성화" 시나리오
    experienced_digital_bonus = np.where(
        (owner_experience_years >= 5) & has_sns & (delivery_order_count > 500),
        0.06, 0.0
    )
    # "전통시장이지만 온라인 전환 성공" 역발상 시나리오
    traditional_digital_bonus = np.where(
        is_traditional_market & (online_platform_activity_index > 60),
        0.05, 0.0
    )

    # 외부 노이즈 (경기 변동, 지역 특성 — 설명 불가능한 현실적 오차)
    external_noise = np.random.normal(0, 0.06, n)

    # 최종 미래 성과 점수 합산
    future_score = (
        growth_momentum
        + online_synergy
        + customer_trust
        + operational_stability
        + location_premium
        + lean_online_bonus
        + experienced_digital_bonus
        + traditional_digital_bonus
        + external_noise
    )

    # 점수를 S1~S10으로 변환 (분위수 기반 — 각 등급 균등 분포)
    # S1이 가장 높은 등급이므로 점수 높을수록 S1에 가까움
    percentiles = np.percentile(future_score, np.linspace(0, 100, 11))
    grade_index = np.digitize(future_score, percentiles[1:-1])  # 0~9
    grade_index = np.clip(grade_index, 0, 9)
    # 점수 높을수록 S1 → 역순 매핑
    target_s_grade = np.array([f'S{10 - i}' for i in grade_index])

    # ── 5단계: 데이터프레임 조립 ─────────────────────────────
    base_date = datetime(2026, 5, 15, 8, 56, 0)
    created_at = [
        base_date - timedelta(
            days=int(np.random.randint(0, 365)),
            minutes=int(np.random.randint(0, 1440))
        )
        for _ in range(n)
    ]

    data = {
        # PK / FK
        'feature_id': np.arange(1, n + 1),
        'biz_data_id': np.random.choice(range(1000, 50000), n, replace=False),
        'user_id': np.random.choice(range(1, 20000), n),
        # 계량 변수 (A)
        'business_age_months': business_age_months,
        'quarterly_revenue_growth_rate': quarterly_revenue_growth_rate,
        'annual_revenue_growth_rate': annual_revenue_growth_rate,
        'revenue_vs_industry_avg_ratio': revenue_vs_industry_avg_ratio,
        'avg_monthly_transaction_3m': avg_monthly_transaction_3m,
        'avg_monthly_transaction_6m': avg_monthly_transaction_6m,
        'avg_monthly_transaction_12m': avg_monthly_transaction_12m,
        'days_since_last_transaction': days_since_last_transaction,
        'max_inactive_days': max_inactive_days,
        'online_platform_activity_index': online_platform_activity_index,
        'revenue_growth_per_employee_3m': revenue_growth_per_employee_3m,
        'revenue_growth_per_employee_6m': revenue_growth_per_employee_6m,
        'revenue_growth_per_employee_12m': revenue_growth_per_employee_12m,
        'revenue_growth_per_business_age_3m': revenue_growth_per_business_age_3m,
        'revenue_growth_per_business_age_6m': revenue_growth_per_business_age_6m,
        'revenue_growth_per_business_age_12m': revenue_growth_per_business_age_12m,
        # 비계량 변수 (B)
        'online_accessibility_score': online_accessibility_score,
        'is_near_subway': is_near_subway,
        'commercial_saturation_score': commercial_saturation_score,
        'is_traditional_market': is_traditional_market,
        'commercial_trend': commercial_trend,
        'industry_trend': industry_trend,
        'review_rating': review_rating,
        'review_count': review_count,
        'delivery_rating': delivery_rating,
        'delivery_order_count': delivery_order_count,
        'positive_review_ratio': positive_review_ratio,
        'has_online_reservation': has_online_reservation,
        'owner_experience_years': owner_experience_years,
        'employee_count': employee_count,
        'has_sns': has_sns,
        'created_at': created_at,
        # 타겟 라벨
        'target_s_grade': target_s_grade,
    }

    return pd.DataFrame(data)


# ── 실행 ─────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f"합성 데이터 {N:,}건 생성 중...")
    df = generate_data(N)

    # 저장
    output_dir = os.path.join(os.path.dirname(__file__))
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, 's_input_feature_10k.csv')
    df.to_csv(file_path, index=False, encoding='utf-8-sig')
    print(f"✅ '{file_path}'에 저장 완료")

    # 검증 출력
    print("\n[등급 분포 확인] — 균등 분포에 가까울수록 학습에 유리")
    print(df['target_s_grade'].value_counts().sort_index())

    print("\n[주요 변수 기술 통계]")
    print(df[[
        'avg_monthly_transaction_3m',
        'online_platform_activity_index',
        'review_rating',
        'annual_revenue_growth_rate',
        'employee_count',
    ]].describe().round(2))

    print("\n[비선형 시나리오 검증]")
    # "직원 적고 온라인 활동성 높은" 그룹의 등급 분포
    lean_online = df[(df['employee_count'] <= 2) & (df['online_platform_activity_index'] > 70)]
    print(f"  소규모+고온라인 그룹 ({len(lean_online)}건) S1~S3 비율: "
          f"{(lean_online['target_s_grade'].isin(['S1','S2','S3'])).mean():.1%}")

    # 전체 S1~S3 비율과 비교
    overall_top3 = (df['target_s_grade'].isin(['S1', 'S2', 'S3'])).mean()
    print(f"  전체 S1~S3 비율: {overall_top3:.1%} (소규모+고온라인 그룹이 더 높아야 정상)")
