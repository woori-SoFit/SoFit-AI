"""
MySQL 연결 테스트 스크립트.
환경변수 DB_HOST, DB_USERNAME, DB_PASSWORD를 사용하여 연결을 확인한다.
"""

import os
import sys

from dotenv import load_dotenv
import pymysql

# 프로젝트 루트의 .env 로드
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_HOST = os.getenv("DB_HOST")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "sofit")  # 기본값 sofit
DB_PORT = int(os.getenv("DB_PORT", "3306"))


def test_connection() -> bool:
    """MySQL 연결 테스트. 성공 시 True, 실패 시 False 반환."""
    print("=" * 50)
    print("MySQL 연결 테스트")
    print("=" * 50)
    print(f"  Host: {DB_HOST}")
    print(f"  Port: {DB_PORT}")
    print(f"  User: {DB_USERNAME}")
    print(f"  Database: {DB_NAME}")
    print("-" * 50)

    # 환경변수 누락 체크
    if not all([DB_HOST, DB_USERNAME, DB_PASSWORD]):
        print("[FAIL] 환경변수가 설정되지 않았습니다.")
        print("  필요한 환경변수: DB_HOST, DB_USERNAME, DB_PASSWORD")
        return False

    try:
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USERNAME,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            connect_timeout=10,
        )

        with connection.cursor() as cursor:
            # 1. 연결 확인
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"[OK] 연결 성공 (SELECT 1 = {result[0]})")

            # 2. DB 버전 확인
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"[OK] MySQL 버전: {version[0]}")

            # 3. 현재 데이터베이스 확인
            cursor.execute("SELECT DATABASE()")
            db = cursor.fetchone()
            print(f"[OK] 현재 DB: {db[0]}")

            # 4. 테이블 목록 확인
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            if tables:
                print(f"[OK] 테이블 수: {len(tables)}")
                for table in tables:
                    print(f"     - {table[0]}")
            else:
                print("[INFO] 테이블이 아직 없습니다.")

        connection.close()
        print("-" * 50)
        print("[SUCCESS] MySQL 연결 테스트 완료")
        return True

    except pymysql.err.OperationalError as e:
        print(f"[FAIL] 연결 실패: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] 예상치 못한 오류: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
