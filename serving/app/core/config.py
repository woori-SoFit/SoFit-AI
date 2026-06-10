from pathlib import Path

from pydantic_settings import BaseSettings

# 프로젝트 루트 탐색: .env 파일이 있는 디렉토리를 기준으로 결정
# 로컬: serving/app/core/config.py → 4단계 위 = repo root
# Docker: /app/app/core/config.py → 3단계 위 = /app
_THIS_FILE = Path(__file__).resolve()


def _find_project_root() -> Path:
    """
    .env 파일 또는 models/ 디렉토리가 존재하는 조상 디렉토리를 프로젝트 루트로 결정.
    찾지 못하면 /app (Docker 기본값) 반환.
    """
    current = _THIS_FILE.parent
    for _ in range(5):  # 최대 5단계까지 탐색
        if (current / ".env").exists() or (current / "models").exists():
            return current
        current = current.parent
    return Path("/app")


_PROJECT_ROOT = _find_project_root()


class Settings(BaseSettings):
    """
    애플리케이션 설정.
    환경변수로 오버라이드 가능 (예: MODEL_DIR=/app/models).
    """

    # 모델 버전 및 경로 설정
    model_version: str = "v1"
    model_dir: Path = _PROJECT_ROOT / "models"

    @property
    def model_path(self) -> Path:
        """모델 파일 경로 반환. 예: /app/models/scb_model_v1.pkl"""
        return self.model_dir / f"scb_model_{self.model_version}.pkl"

    # SHAP 설명 시 반환할 상위 기여 변수 개수
    shap_top_n: int = 5

    # Gemini LLM 설정
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"

    # DB 설정 (s_grade_feature 읽기 전용)
    db_host: str = "localhost"
    db_port: int = 3306
    db_username: str = ""
    db_password: str = ""
    db_name: str = "sofit"

    class Config:
        env_file = str(_PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"


# 싱글턴 인스턴스 — 앱 전체에서 공유
settings = Settings()
