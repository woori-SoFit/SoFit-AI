from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    애플리케이션 설정.
    환경변수로 오버라이드 가능 (예: MODEL_VERSION=v2).
    """

    # 모델 버전 및 경로 설정
    model_version: str = "v1"
    model_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "models"

    @property
    def model_path(self) -> Path:
        """모델 파일 경로 반환. 예: <project_root>/models/scb_model_v1.pkl"""
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
        env_file = str(Path(__file__).resolve().parent.parent.parent.parent / ".env")
        env_file_encoding = "utf-8"


# 싱글턴 인스턴스 — 앱 전체에서 공유
settings = Settings()
