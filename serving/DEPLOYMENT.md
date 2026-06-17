# AI 서버 배포 및 운영 가이드

## 개요

SoFit AI 서버는 FastAPI 기반으로, LightGBM 모델을 이용한 S등급 산출 및 SHAP/LLM 조언 생성을 수행합니다.
Spring BE에서 HTTP로 호출하며, Docker 컨테이너로 온프레미스 서버에 배포됩니다.

---

## 인프라 구성

| 항목 | 값 |
|------|------|
| 앱 서버 | `172.21.33.238` (dev-app) |
| CI/CD 서버 | Jenkins + SonarQube |
| Docker Registry | `172.21.33.225:5000` (프라이빗) |
| 이미지명 | `sofit-ai` |
| 포트 | `8000` |

---

## 사전 준비사항

### 1. 환경변수

앱 서버에 `.env` 파일 또는 docker-compose 환경변수로 아래 값을 설정합니다:

| 환경변수 | 설명 | 예시 |
|----------|------|------|
| `GEMINI_API_KEY` | Gemini LLM API 키 | `AIzaSy...` |
| `DB_HOST` | MySQL 호스트 | `172.21.33.238` |
| `DB_USERNAME` | MySQL 사용자 | `sofit` |
| `DB_PASSWORD` | MySQL 비밀번호 | (비밀) |
| `DB_NAME` | 데이터베이스명 | `sofit` |
| `DB_PORT` | MySQL 포트 (기본값: 3306) | `3306` |
| `MODEL_VERSION` | 모델 버전 (기본값: v1) | `v1` |
| `MODEL_DIR` | 모델 디렉토리 (기본값: 자동 탐색) | `/app/models` |

### 2. 모델 파일

- 모델 파일(`scb_model_v1.pkl`)은 `.gitignore` 대상이므로 Git에 포함되지 않음
- 온프레미스 서버의 `/home/ubuntu/models/` 디렉토리에 배치
- Docker 실행 시 볼륨 마운트로 컨테이너 내부 `/app/models`에 연결

### 3. DB 테이블

- `s_grade_feature` 테이블이 존재해야 함 (Spring BE가 관리)
- AI 서버는 SELECT 권한만 필요 (INSERT/UPDATE 없음)

---

## 로컬 실행 (개발용)

```bash
# 1. 가상환경 활성화
source .venv/bin/activate

# 2. 패키지 설치
pip install -r serving/requirements.txt

# 3. .env 파일 확인 (프로젝트 루트)
cat .env

# 4. 모델 파일 확인
ls models/scb_model_v1.pkl

# 5. 서버 실행
cd serving
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 동작 확인

```bash
# 헬스체크
curl http://localhost:8000/health

# S등급 산출 테스트
curl -X POST http://localhost:8000/api/s-grade/predict \
  -H "Content-Type: application/json" \
  -d '{"biz_data_id": 1}'
```

---

## Docker 빌드 및 실행

### 수동 빌드 (프로젝트 루트에서)

```bash
docker build -t sofit-ai:dev -f serving/Dockerfile .
```

### 수동 실행

```bash
docker run -d \
  --name sofit-ai \
  -p 8000:8000 \
  -v /home/ubuntu/models:/app/models \
  -e GEMINI_API_KEY=<API키> \
  -e DB_HOST=172.21.33.238 \
  -e DB_USERNAME=sofit \
  -e DB_PASSWORD=<비밀번호> \
  -e DB_NAME=sofit \
  -e MODEL_DIR=/app/models \
  sofit-ai:dev
```

### docker-compose 예시

```yaml
services:
  sofit-ai:
    image: 172.21.33.225:5000/sofit-ai:main
    container_name: sofit-ai
    ports:
      - "8000:8000"
    volumes:
      - /home/ubuntu/models:/app/models
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DB_HOST=${DB_HOST}
      - DB_USERNAME=${DB_USERNAME}
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_NAME=${DB_NAME}
      - MODEL_DIR=/app/models
    restart: unless-stopped
```

---

## CI/CD 파이프라인 (Jenkins)

### 트리거 조건

- `main`, `dev` 브랜치 push 시 자동 실행
- feat/* 브랜치는 빌드하지 않음

### 파이프라인 단계

```
1. 브랜치 필터 → main/dev만 통과
2. Checkout → 소스 코드 가져오기
3. Prepare Model → 모델 파일 준비 (현재 수동)
4. Docker Build & Push → 이미지 빌드 후 프라이빗 레지스트리 push
5. Deploy (main만) → 앱 서버에 SSH 접속하여 pull + docker-compose up
```

### 배포 흐름

```
코드 push (main) → Jenkins 빌드 → Docker 이미지 push
→ 앱 서버에서 pull → docker-compose up -d sofit-ai
```

---

## 월별 배치 실행

월별 배치는 crontab으로 스케줄링됩니다. Docker 컨테이너 내부가 아닌 호스트에서 실행합니다.

### crontab 설정

```bash
# 매월 1일 23:40 — 월별 배치 (전체 회원 등급 갱신)
40 23 1 * * cd /home/ubuntu/SoFit-AI && python -m batch.run_batch
```

### 수동 실행

```bash
cd /home/ubuntu/SoFit-AI
python -m batch.run_batch --type manual --triggered-by <은행원_user_id>
```

---

## 모니터링 및 헬스체크

### 헬스체크 엔드포인트

```
GET /health
→ {"status": "ok", "model_loaded": true}
```

- `model_loaded: false`이면 모델 파일 마운트 상태 확인 필요
- docker-compose에 healthcheck 설정 권장:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### 로그 확인

```bash
# 컨테이너 로그
docker logs -f sofit-ai

# 최근 100줄
docker logs --tail 100 sofit-ai
```

---

## 모델 교체 절차

1. AI 팀장이 로컬에서 학습 완료 → `scb_model_v2.pkl` 생성
2. 앱 서버의 `/home/ubuntu/models/`에 파일 복사
3. 환경변수 `MODEL_VERSION=v2` 변경 (docker-compose.yml 또는 .env)
4. 컨테이너 재시작: `docker-compose restart sofit-ai`
5. 헬스체크로 모델 로드 확인: `curl http://localhost:8000/health`

---

## 장애 대응

| 증상 | 원인 | 조치 |
|------|------|------|
| 503 (모델 미로드) | 모델 파일 없음 또는 경로 불일치 | `/app/models/` 마운트 확인, `MODEL_DIR` 환경변수 확인 |
| 500 (DB 에러) | MySQL 연결 실패 | `DB_HOST`, 네트워크, MySQL 상태 확인 |
| 500 (예측 실패) | 피처 타입 불일치 | 로그에서 상세 에러 확인, 모델 버전과 피처 스키마 호환성 점검 |
| 422 (요청 파싱 실패) | request body 형식 불일치 | `{"biz_data_id": int}` snake_case 확인 |
| Gemini 조언 빈 문자열 | API 키 만료 또는 할당량 초과 | `GEMINI_API_KEY` 유효성 확인 |

---

## 보안 참고사항

- 컨테이너는 non-root 사용자(`appuser`)로 실행
- AI 서버는 DB SELECT 권한만 보유 (쓰기 불가)
- `.env` 파일은 `.gitignore` 대상 — Git에 커밋하지 않음
- API는 내부망에서만 접근 가능 (외부 노출 없음)
