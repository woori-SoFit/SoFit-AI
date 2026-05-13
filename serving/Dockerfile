# ────────────────────────────────────────────────────────────
# Stage 1: builder
#   - 의존성 설치만 수행하여 최종 이미지 크기를 줄입니다.
# ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# 시스템 패키지 업데이트 및 빌드에 필요한 최소 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt만 먼저 복사 → 의존성 레이어 캐시 활용
COPY serving/requirements.txt .

# 가상환경 생성 후 의존성 설치 (site-packages를 /venv에 격리)
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt


# ────────────────────────────────────────────────────────────
# Stage 2: runtime
#   - builder에서 만든 venv만 복사하여 최소 이미지 구성
# ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# 보안: root가 아닌 전용 사용자로 실행
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# builder 스테이지의 가상환경 복사
COPY --from=builder /venv /venv

# 애플리케이션 소스 복사
# Jenkinsfile에서 빌드 컨텍스트가 레포 루트이므로 serving/ 경로로 지정
COPY serving/ .

# 모델 파일 마운트 포인트 생성 (실제 .pkl 파일은 .gitignore 대상)
# 온프레미스 서버에서 docker-compose volumes로 마운트하여 사용
RUN mkdir -p /app/models

# 소유권 변경
RUN chown -R appuser:appgroup /app

USER appuser

# 가상환경 PATH 등록
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# uvicorn으로 FastAPI 앱 실행
# main.py 위치: serving/main.py → 컨테이너 내 /app/main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
