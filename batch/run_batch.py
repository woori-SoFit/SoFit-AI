"""
S등급 산출 배치 실행 엔트리포인트.

사용법:
    # 일일 배치 — 자동 (crontab)
    python -m batch.run_batch --cycle daily

    # 월별 배치 — 자동 (crontab)
    python -m batch.run_batch --cycle monthly

    # 수동 트리거 (은행원이 관리자 페이지에서 실행)
    python -m batch.run_batch --cycle daily --type manual --triggered-by 2001
    python -m batch.run_batch --cycle monthly --type manual --triggered-by 2001

    # 기본값: daily, auto
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
    parser.add_argument(
        "--type",
        choices=["auto", "manual"],
        default="auto",
        help="실행 유형: auto(crontab 자동) / manual(은행원 수동 트리거)",
    )
    parser.add_argument(
        "--triggered-by",
        type=int,
        default=None,
        help="수동 실행 시 트리거한 은행원의 user_id (--type manual일 때 필수)",
    )
    args = parser.parse_args()

    # manual인데 triggered-by가 없으면 에러
    if args.type == "manual" and args.triggered_by is None:
        parser.error("--type manual일 때 --triggered-by는 필수입니다.")

    execution_type = args.type.upper()  # AUTO / MANUAL
    triggered_by = args.triggered_by

    if args.cycle == "monthly":
        asyncio.run(run_monthly_batch(execution_type=execution_type, triggered_by=triggered_by))
    else:
        asyncio.run(run_batch(execution_type=execution_type, triggered_by=triggered_by))


if __name__ == "__main__":
    main()
