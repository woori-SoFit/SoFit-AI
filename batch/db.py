"""
MySQL 데이터베이스 연결 및 쿼리 모듈.
배치 처리에 필요한 CRUD 작업을 담당한다.

[트랜잭션 규칙]
- db.py는 쿼리 실행만 담당한다 (commit/rollback 하지 않음).
- 트랜잭션 경계(commit/rollback)는 pipeline 계층에서 관리한다.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

import pymysql
from pymysql.cursors import DictCursor

from batch.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USERNAME

logger = logging.getLogger(__name__)

# ── 상태값 상수 ───────────────────────────────────────────────
STATUS_REQUESTED = "REQUESTED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_RUNNING = "RUNNING"

MAX_RETRY_COUNT: int = 3


@contextmanager
def get_connection() -> Generator[pymysql.connections.Connection, None, None]:
    """
    MySQL 커넥션 컨텍스트 매니저.
    예외 발생 시 rollback을 명시적으로 수행하여 미커밋 트랜잭션이 남지 않도록 한다.
    """
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
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 조회 함수 ────────────────────────────────────────────────


def fetch_requested_calculations(conn: pymysql.connections.Connection) -> list[dict[str, Any]]:
    """
    status='REQUESTED'인 s_calculation_request 목록을 조회.
    해당 사용자의 s_input_feature 데이터를 JOIN하여 반환.
    retry_count가 최대 재시도 횟수 미만인 건만 대상.
    """
    sql = """
        SELECT
            r.request_id,
            r.target_user_id,
            r.retry_count,
            f.*
        FROM s_calculation_request r
        JOIN s_input_feature f ON f.user_id = r.target_user_id
        WHERE r.status = %s
          AND r.retry_count < %s
        ORDER BY r.requested_at ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (STATUS_REQUESTED, MAX_RETRY_COUNT))
        results = cursor.fetchall()
    logger.info("REQUESTED 상태 산출 요청 %d건 조회 (retry < %d)", len(results), MAX_RETRY_COUNT)
    return results


def fetch_all_latest_features(conn: pymysql.connections.Connection) -> list[dict[str, Any]]:
    """
    월별 배치용: 전체 사용자의 최신 s_input_feature 레코드를 조회.
    사용자별 created_at이 가장 최근인 레코드 1건만 반환.
    """
    sql = """
        SELECT f.*
        FROM s_input_feature f
        INNER JOIN (
            SELECT user_id, MAX(created_at) AS max_created_at
            FROM s_input_feature
            GROUP BY user_id
        ) latest ON f.user_id = latest.user_id AND f.created_at = latest.max_created_at
        ORDER BY f.user_id ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        results = cursor.fetchall()
    logger.info("월별 배치 대상: 전체 %d명 사용자의 최신 피처 조회", len(results))
    return results


# ── s_calculation_request 관련 ────────────────────────────────


def update_request_status(
    conn: pymysql.connections.Connection,
    request_id: int,
    status: str,
    s_evaluation_id: int | None = None,
    error_message: str | None = None,
) -> None:
    """s_calculation_request 상태 업데이트."""
    if status == STATUS_COMPLETED:
        sql = """
            UPDATE s_calculation_request
            SET status = %s, s_evaluation_id = %s, completed_at = %s
            WHERE request_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, s_evaluation_id, datetime.now(), request_id))
    elif status == STATUS_FAILED:
        sql = """
            UPDATE s_calculation_request
            SET status = %s, error_message = %s
            WHERE request_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, error_message, request_id))
    else:
        sql = """
            UPDATE s_calculation_request
            SET status = %s
            WHERE request_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, request_id))


def complete_requests_for_user(
    conn: pymysql.connections.Connection,
    user_id: int,
    s_evaluation_id: int,
) -> int:
    """
    월별 배치에서 사용자 처리 완료 시, 해당 사용자의 REQUESTED 상태 요청을 함께 COMPLETED 처리.
    Returns: 처리된 요청 건수
    """
    sql = """
        UPDATE s_calculation_request
        SET status = %s, s_evaluation_id = %s, completed_at = %s
        WHERE target_user_id = %s AND status = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (STATUS_COMPLETED, s_evaluation_id, datetime.now(), user_id, STATUS_REQUESTED))
        return cursor.rowcount


# ── batch_execution_history 관련 ──────────────────────────────


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
        VALUES (%s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (execution_type, execution_cycle, STATUS_RUNNING, total_count, datetime.now()))
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


# ── s_evaluation_history 관련 ─────────────────────────────────


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
    기존 is_latest=0 → 새 레코드 is_latest=1.
    s_evaluation_id 반환.
    """
    sql_update = """
        UPDATE s_evaluation_history
        SET is_latest = 0
        WHERE user_id = %s AND is_latest = 1
    """
    sql_insert = """
        INSERT INTO s_evaluation_history
            (user_id, biz_data_id, batch_execution_id, grade, score, is_latest, status, evaluated_at)
        VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql_update, (user_id,))
        cursor.execute(
            sql_insert,
            (user_id, biz_data_id, batch_execution_id, grade, score, STATUS_COMPLETED, datetime.now()),
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


# ── shap_explanation 관련 ─────────────────────────────────────


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


# ── 재시도 전략 관련 함수 ─────────────────────────────────────


def recover_orphaned_requests(conn: pymysql.connections.Connection) -> int:
    """
    전략 B: 배치 시작 시 고아 건 복구.
    IN_PROGRESS 상태로 남아있는 건을 REQUESTED로 되돌리고 retry_count를 1 증가.
    단일 프로세스 배치이므로 IN_PROGRESS는 이전 실행에서 비정상 종료된 건.

    Returns:
        복구된 건수
    """
    sql_recover = """
        UPDATE s_calculation_request
        SET status = %s, retry_count = retry_count + 1
        WHERE status = %s
          AND retry_count < %s
    """
    sql_fail = """
        UPDATE s_calculation_request
        SET status = %s, error_message = '최대 재시도 횟수 초과 (비정상 종료 복구)'
        WHERE status = %s
          AND retry_count >= %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql_recover, (STATUS_REQUESTED, STATUS_IN_PROGRESS, MAX_RETRY_COUNT))
        recovered = cursor.rowcount

        cursor.execute(sql_fail, (STATUS_FAILED, STATUS_IN_PROGRESS, MAX_RETRY_COUNT))
        failed = cursor.rowcount

    if recovered > 0:
        logger.info("고아 건 복구: %d건을 REQUESTED로 되돌림 (retry_count +1)", recovered)
    if failed > 0:
        logger.warning("고아 건 최종 실패: %d건 FAILED 처리 (최대 재시도 초과)", failed)

    return recovered


def rollback_request_on_failure(
    conn: pymysql.connections.Connection,
    request_id: int,
    error_message: str,
    current_retry_count: int,
) -> None:
    """
    전략 C: 실패 시 즉시 롤백.
    retry_count를 1 증가시키고:
    - 최대 재시도 미만이면 REQUESTED로 되돌림 (다음 배치에서 재시도)
    - 최대 재시도 이상이면 FAILED 처리 (관리자 알림 대상)
    """
    new_retry_count = current_retry_count + 1

    if new_retry_count >= MAX_RETRY_COUNT:
        sql = """
            UPDATE s_calculation_request
            SET status = %s, retry_count = %s, error_message = %s
            WHERE request_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (STATUS_FAILED, new_retry_count, error_message, request_id))
        logger.warning(
            "최종 실패 처리: request_id=%d (retry_count=%d, 최대 %d회 초과)",
            request_id, new_retry_count, MAX_RETRY_COUNT,
        )
    else:
        sql = """
            UPDATE s_calculation_request
            SET status = %s, retry_count = %s, error_message = %s
            WHERE request_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (STATUS_REQUESTED, new_retry_count, error_message, request_id))
        logger.info(
            "재시도 대기: request_id=%d (retry_count=%d/%d)",
            request_id, new_retry_count, MAX_RETRY_COUNT,
        )
