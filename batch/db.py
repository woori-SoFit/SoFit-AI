"""
MySQL 데이터베이스 연결 및 쿼리 모듈.
배치 처리에 필요한 CRUD 작업을 담당한다.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

import pymysql
from pymysql.cursors import DictCursor

from batch.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USERNAME

logger = logging.getLogger(__name__)


@contextmanager
def get_connection() -> Generator[pymysql.connections.Connection, None, None]:
    """MySQL 커넥션 컨텍스트 매니저."""
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USERNAME,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        connect_timeout=10,
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()


def fetch_requested_calculations(conn: pymysql.connections.Connection) -> list[dict[str, Any]]:
    """
    status='REQUESTED'인 s_calculation_request 목록을 조회.
    해당 사용자의 s_input_feature 데이터를 JOIN하여 반환.
    """
    sql = """
        SELECT
            r.request_id,
            r.target_user_id,
            f.*
        FROM s_calculation_request r
        JOIN s_input_feature f ON f.user_id = r.target_user_id
        WHERE r.status = 'REQUESTED'
        ORDER BY r.requested_at ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        results = cursor.fetchall()
    logger.info("REQUESTED 상태 산출 요청 %d건 조회", len(results))
    return results


def update_request_status(
    conn: pymysql.connections.Connection,
    request_id: int,
    status: str,
    s_evaluation_id: int | None = None,
) -> None:
    """s_calculation_request 상태 업데이트."""
    if status == "COMPLETED":
        sql = """
            UPDATE s_calculation_request
            SET status = %s, s_evaluation_id = %s, completed_at = %s
            WHERE request_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, s_evaluation_id, datetime.now(), request_id))
    else:
        sql = """
            UPDATE s_calculation_request
            SET status = %s
            WHERE request_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, request_id))


def insert_batch_execution(
    conn: pymysql.connections.Connection,
    execution_type: str,
    execution_cycle: str,
    total_count: int,
) -> int:
    """batch_execution_history에 배치 시작 레코드 삽입. execution_id 반환."""
    sql = """
        INSERT INTO batch_execution_history
            (execution_type, execution_cycle, status, total_count, started_at)
        VALUES (%s, %s, 'RUNNING', %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (execution_type, execution_cycle, total_count, datetime.now()))
        conn.commit()
        return cursor.lastrowid


def update_batch_execution(
    conn: pymysql.connections.Connection,
    execution_id: int,
    status: str,
    success_count: int,
    fail_count: int,
    error_message: str | None = None,
) -> None:
    """batch_execution_history 상태 업데이트."""
    sql = """
        UPDATE batch_execution_history
        SET status = %s, success_count = %s, fail_count = %s,
            error_message = %s, completed_at = %s
        WHERE execution_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (status, success_count, fail_count, error_message, datetime.now(), execution_id),
        )
        conn.commit()


def insert_evaluation_and_update_latest(
    conn: pymysql.connections.Connection,
    user_id: int,
    biz_data_id: int,
    batch_execution_id: int,
    grade: str,
    score: float,
) -> int:
    """
    s_evaluation_history에 새 레코드 삽입 + is_latest 갱신.
    트랜잭션으로 처리: 기존 is_latest=0 → 새 레코드 is_latest=1.
    s_evaluation_id 반환.
    """
    # 1. 기존 최신 레코드의 is_latest를 0으로 변경
    sql_update = """
        UPDATE s_evaluation_history
        SET is_latest = 0
        WHERE user_id = %s AND is_latest = 1
    """
    # 2. 새 레코드 삽입
    sql_insert = """
        INSERT INTO s_evaluation_history
            (user_id, biz_data_id, batch_execution_id, grade, score, is_latest, status, evaluated_at)
        VALUES (%s, %s, %s, %s, %s, 1, 'COMPLETED', %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql_update, (user_id,))
        cursor.execute(
            sql_insert,
            (user_id, biz_data_id, batch_execution_id, grade, score, datetime.now()),
        )
        return cursor.lastrowid


def insert_shap_explanation(
    conn: pymysql.connections.Connection,
    evaluation_id: int,
    user_id: int,
    s_grade: str,
    target_grade: str,
    strength_keywords: str,
    improvement_keywords: str,
    strength_details: str,
    improvement_details: str,
    advice: str,
) -> int:
    """shap_explanation 테이블에 XAI 결과 삽입. result_id 반환."""
    sql = """
        INSERT INTO shap_explanation
            (evaluation_id, user_id, s_grade, target_grade,
             strength_keywords, improvement_keywords,
             strength_details, improvement_details, advice, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (
                evaluation_id, user_id, s_grade, target_grade,
                strength_keywords, improvement_keywords,
                strength_details, improvement_details, advice, datetime.now(),
            ),
        )
        return cursor.lastrowid


def update_evaluation_result_id(
    conn: pymysql.connections.Connection,
    evaluation_id: int,
    result_id: int,
) -> None:
    """s_evaluation_history의 result_id를 SHAP 결과 ID로 업데이트."""
    sql = """
        UPDATE s_evaluation_history
        SET result_id = %s
        WHERE s_evaluation_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (result_id, evaluation_id))
