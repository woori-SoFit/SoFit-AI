"""
S등급 산출 배치 실행 엔트리포인트.

사용법:
    # 일일 배치 (REQUESTED 건만 처리)
    python -m batch.run_batch --cycle daily

    # 월별 배치 (전체 사용자 등급 갱신 + REQUESTED 건 흡수)
    python -m batch.run_batch --cycle monthly

    # 기본값: daily
    python -m batch.run_batch

스케줄링 (crontab 예시):
    # 매일 23:40 — 단, 매월 1일은 제외 (월별 배치가 대신 처리)
    40 23 2-31 * * cd /app/SoFit-AI && python -m batch.run_batch --cycle daily

    # 매월 1일 23:40 — 월별 배치 (전체 회원 + REQUESTED 건 포함)
    40 23 1 * * cd /app/SoFit-AI && python -m batch.run_batch --cycle monthly
"""

import argparse
import asyncio
import logging
import sys

from batch.pipeline import run_batch, run_monthly_batch

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main() -> None:
    """배치 실행."""
    parser = argparse.ArgumentParser(description="SoFit S등급 산출 배치")
    parser.add_argument(
        "--cycle",
        choices=["daily", "monthly"],
        default="daily",
        help="배치 주기: daily(일일, REQUESTED 건만) / monthly(월별, 전체 사용자)",
    )
    args = parser.parse_args()

    if args.cycle == "monthly":
        asyncio.run(run_monthly_batch())
    else:
        asyncio.run(run_batch())


if __name__ == "__main__":
    main()
