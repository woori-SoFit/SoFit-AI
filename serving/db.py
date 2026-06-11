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
    )
    try:
        yield conn
    finally:
        conn.close()


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
