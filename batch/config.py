"""
배치 설정 모듈.
환경변수에서 DB 접속 정보 및 모델 경로를 로드한다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── DB 설정 ──────────────────────────────────────────────────
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
DB_USERNAME: str = os.getenv("DB_USERNAME", "root")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
DB_NAME: str = os.getenv("DB_NAME", "sofit")

# ── 모델 설정 ────────────────────────────────────────────────
MODEL_VERSION: str = os.getenv("MODEL_VERSION", "v1")
MODEL_DIR: Path = _PROJECT_ROOT / "models"
MODEL_PATH: Path = MODEL_DIR / f"scb_model_{MODEL_VERSION}.pkl"

# ── SHAP 설정 ────────────────────────────────────────────────
SHAP_TOP_N: int = int(os.getenv("SHAP_TOP_N", "5"))

# ── Gemini LLM 설정 ──────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
