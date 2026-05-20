"""
S등급 산출 배치 실행 엔트리포인트.

사용법:
    python -m batch.run_batch

처리 대상:
    s_calculation_request 테이블에서 status='REQUESTED'인 건
"""

import asyncio
import logging
import sys

from batch.pipeline import run_batch

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def main() -> None:
    """배치 실행."""
    asyncio.run(run_batch())


if __name__ == "__main__":
    main()
