"""
S등급 산출 서빙용 DB 조회 모듈.

[역할]
- biz_data_id로 s_grade_feature 테이블에서 피처 데이터 조회 (SELECT만)
- DB 쓰기 권한 없음 (INSERT/UPDATE는 Spring BE가 담당)

[테이블]
- s_grade_feature: 모델 입력 피처 (READ only)
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_connection() -> Generator[pymysql.connections.Connection, None, None]:
    """MySQL 읽기 전용 커넥션 컨텍스트 매니저."""
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_username,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        connect_timeout=10,
        autocommit=True,
        init_command="SET time_zone='+09:00'",
    )
    try:
        yield conn
    finally:
        conn.close()


def fetch_latest_batch_execution() -> dict[str, Any] | None:
    """
    batch_execution_history에서 가장 최근 레코드를 조회한다.

    Returns:
        최근 배치 실행 레코드 딕셔너리 (없으면 None)
    """
    sql = """
        SELECT execution_id, execution_type, execution_cycle,
               status, total_count, success_count, fail_count,
               error_message, started_at, completed_at
        FROM batch_execution_history
        ORDER BY started_at DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchone()


def fetch_batch_status_summary(execution_id: int) -> dict[str, Any]:
    """
    특정 배치 실행 ID 기준으로 s_grade_history 상태별 건수를 집계한다.

    Returns:
        {"completed": int, "failed": int, "calculating": int, "requested": int}
    """
    sql = """
        SELECT status, COUNT(*) AS cnt
        FROM s_grade_history
        WHERE batch_execution_id = %s
        GROUP BY status
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (execution_id,))
            rows = cursor.fetchall()

    summary = {"completed": 0, "failed": 0, "calculating": 0, "requested": 0}
    for row in rows:
        status_lower = row["status"].lower()
        if status_lower in summary:
            summary[status_lower] = row["cnt"]
    return summary


def is_batch_running_in_db() -> bool:
    """
    DB에서 가장 최근 batch_execution_history 레코드의 status가
    RUNNING이면 배치가 실행 중으로 간주한다.
    서버 재시작 대응용.

    Returns:
        True면 실행 중
    """
    latest = fetch_latest_batch_execution()
    if latest is None:
        return False
    return latest["status"] in ("RUNNING",)


def fetch_feature_by_biz_data_id(biz_data_id: int) -> dict[str, Any] | None:
    """
    biz_data_id로 s_grade_feature 테이블에서 피처 데이터를 조회한다.

    Args:
        biz_data_id: s_grade_feature 테이블에서 조회할 biz_data_id

    Returns:
        피처 데이터 딕셔너리 (없으면 None)
    """
    sql = """
        SELECT *
        FROM s_grade_feature
        WHERE biz_data_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, (biz_data_id,))
            result = cursor.fetchone()

    if result:
        logger.info("피처 조회 성공: biz_data_id=%d, feature_id=%d", biz_data_id, result["feature_id"])
    else:
        logger.warning("피처 조회 실패: biz_data_id=%d에 해당하는 데이터 없음", biz_data_id)

    return result
