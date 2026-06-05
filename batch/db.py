"""
MySQL 데이터베이스 연결 및 쿼리 모듈.
배치 처리에 필요한 CRUD 작업을 담당한다.

[트랜잭션 규칙]
- db.py는 쿼리 실행만 담당한다 (commit/rollback 하지 않음).
- 트랜잭션 경계(commit/rollback)는 pipeline 계층에서 관리한다.

[테이블 매핑]
- s_grade_history: S등급 산출 요청 및 상태 관리 (READ + UPDATE + INSERT)
- s_grade_feature: 모델 입력 피처 (READ)
- s_grade_report: SHAP 기반 XAI 결과 저장 (INSERT)
- batch_execution_history: 배치 실행 이력 (INSERT + UPDATE)
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
STATUS_CALCULATING = "CALCULATING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_RUNNING = "RUNNING"


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


def fetch_requested_grades(conn: pymysql.connections.Connection) -> list[dict[str, Any]]:
    """
    일일 배치: status='REQUESTED'인 s_grade_history 목록을 조회.
    Spring Boot가 미리 채워놓은 s_feature_id를 이용하여 s_grade_feature과 JOIN.
    """
    sql = """
        SELECT
            h.s_grade_id,
            h.user_id,
            h.feature_id,
            h.requested_at,
            f.*
        FROM s_grade_history h
        JOIN s_grade_feature f ON f.feature_id = h.feature_id
        WHERE h.status = %s
        ORDER BY h.requested_at ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (STATUS_REQUESTED,))
        results = cursor.fetchall()
    logger.info("REQUESTED 상태 S등급 산출 요청 %d건 조회", len(results))
    return results


def fetch_all_latest_features(conn: pymysql.connections.Connection) -> list[dict[str, Any]]:
    """
    월별 배치용: 전체 사용자의 최신 s_grade_feature 레코드를 조회.
    사용자별 created_at이 가장 최근인 레코드 1건만 반환.
    """
    sql = """
        SELECT f.*
        FROM s_grade_feature f
        INNER JOIN (
            SELECT user_id, MAX(created_at) AS max_created_at
            FROM s_grade_feature
            GROUP BY user_id
        ) latest ON f.user_id = latest.user_id AND f.created_at = latest.max_created_at
        ORDER BY f.user_id ASC
    """
    with conn.cursor() as cursor:
        cursor.execute(sql)
        results = cursor.fetchall()
    logger.info("월별 배치 대상: 전체 %d명 사용자의 최신 피처 조회", len(results))
    return results


# ── 고아 건 복구 ──────────────────────────────────────────────


def recover_orphaned_calculating(conn: pymysql.connections.Connection) -> int:
    """
    배치 시작 시, 이전 배치에서 비정상 종료로 CALCULATING에 남은 건을
    REQUESTED로 복구한다 (다음 배치에서 재처리).
    단, 같은 건이 무한 복구되지 않도록 1회 복구 후 다시 CALCULATING → FAILED.

    Returns: 복구된 건수
    """
    sql = """
        UPDATE s_grade_history
        SET status = %s
        WHERE status = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (STATUS_REQUESTED, STATUS_CALCULATING))
        recovered = cursor.rowcount

    if recovered > 0:
        logger.info("고아 건 복구: %d건을 CALCULATING → REQUESTED로 되돌림", recovered)
    return recovered


# ── s_grade_history 상태 관련 ─────────────────────────────────


def update_grade_history_status(
    conn: pymysql.connections.Connection,
    s_grade_id: int,
    status: str,
    batch_execution_id: int | None = None,
) -> None:
    """s_grade_history 상태 업데이트. batch_execution_id가 주어지면 함께 기록."""
    if batch_execution_id is not None:
        sql = """
            UPDATE s_grade_history
            SET status = %s, batch_execution_id = %s
            WHERE s_grade_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, batch_execution_id, s_grade_id))
    else:
        sql = """
            UPDATE s_grade_history
            SET status = %s
            WHERE s_grade_id = %s
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, (status, s_grade_id))


def complete_grade_history(
    conn: pymysql.connections.Connection,
    s_grade_id: int,
) -> None:
    """s_grade_history를 COMPLETED로 변경하고 evaluated_at을 기록."""
    sql = """
        UPDATE s_grade_history
        SET status = %s, evaluated_at = %s
        WHERE s_grade_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (STATUS_COMPLETED, datetime.now(), s_grade_id))


def fail_grade_history(
    conn: pymysql.connections.Connection,
    s_grade_id: int,
) -> None:
    """s_grade_history를 FAILED로 변경."""
    sql = """
        UPDATE s_grade_history
        SET status = %s
        WHERE s_grade_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (STATUS_FAILED, s_grade_id))


def complete_requested_for_user(
    conn: pymysql.connections.Connection,
    user_id: int,
) -> int:
    """
    월별 배치에서 사용자 처리 완료 시,
    해당 사용자의 REQUESTED 상태 s_grade_history를 함께 COMPLETED 처리.
    Returns: 처리된 건수
    """
    sql = """
        UPDATE s_grade_history
        SET status = %s, evaluated_at = %s
        WHERE user_id = %s AND status = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (STATUS_COMPLETED, datetime.now(), user_id, STATUS_REQUESTED))
        return cursor.rowcount


# ── batch_execution_history 관련 ──────────────────────────────


def insert_batch_execution(
    conn: pymysql.connections.Connection,
    execution_type: str,
    execution_cycle: str,
    total_count: int,
    triggered_by: int | None = None,
) -> int:
    """batch_execution_history에 배치 시작 레코드 삽입. execution_id 반환."""
    sql = """
        INSERT INTO batch_execution_history
            (execution_type, execution_cycle, triggered_by, status, total_count, started_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (execution_type, execution_cycle, triggered_by, STATUS_RUNNING, total_count, datetime.now()))
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


# ── s_grade_report 관련 ───────────────────────────────────────


def insert_grade_report(
    conn: pymysql.connections.Connection,
    s_grade_id: int,
    user_id: int,
    feature_id: int,
    s_grade: str,
    target_grade: str,
    strength_keywords: str,
    improvement_keywords: str,
    strength_details: str,
    improvement_details: str,
    user_advice: str,
    admin_advice: str,
) -> None:
    """s_grade_report 테이블에 XAI 결과 삽입."""
    now = datetime.now()
    sql = """
        INSERT INTO s_grade_report
            (s_grade_id, user_id, feature_id, s_grade, target_grade,
             strength_keywords, improvement_keywords,
             strength_details, improvement_details,
             user_advice, admin_advice, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (
                s_grade_id, user_id, feature_id, s_grade, target_grade,
                strength_keywords, improvement_keywords,
                strength_details, improvement_details,
                user_advice, admin_advice, now, now,
            ),
        )


# ── 월별 배치: s_grade_history 신규 생성 ──────────────────────


def insert_grade_history(
    conn: pymysql.connections.Connection,
    user_id: int,
    feature_id: int,
    batch_execution_id: int,
) -> int:
    """
    월별 배치에서 s_grade_history에 신규 레코드를 REQUESTED로 생성한다.
    이후 pipeline에서 CALCULATING → COMPLETED 순으로 상태가 변경된다.
    s_grade_id 반환.
    """
    sql = """
        INSERT INTO s_grade_history
            (user_id, feature_id, batch_execution_id, status, requested_at)
        VALUES (%s, %s, %s, %s, %s)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (user_id, feature_id, batch_execution_id, STATUS_REQUESTED, datetime.now()))
        return cursor.lastrowid
