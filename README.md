# SoFit-AI

소상공인 대출 플랫폼 **SoFit**의 AI 모노레포입니다. 
소상공인 **성장 S등급(S1~S10)** 추론과 **SHAP 기반 XAI 설명**, 그리고 **Gemini LLM 자연어 조언**을 생성합니다.
FastAPI 위에서 LightGBM 모델을 서빙하며, Spring BE(건별 산출)와 월별 배치(전체 회원 갱신) 두 가지 경로로 호출됩니다.


<img width="350" alt="우리FISA 6기 - SOFIT 최종발표" src="https://github.com/user-attachments/assets/dbf557f1-ef31-46c8-8eff-f0cbdd4723c9" />
<img width="350" alt="우리FISA 6기 - SOFIT 최종발표 (1)" src="https://github.com/user-attachments/assets/553f5af6-9428-4daf-bc27-d2e78a2ce2c4" />

> **등급 방향 주의**: `S1`이 가장 높고 `S10`이 가장 낮은 등급입니다. CB 점수와 결합한 **SCB 점수**와는 별개의 지표이므로 혼용하지 않습니다.

---

## 핵심 설계 의도

이 서버는 단순히 "등급을 매기는" 것을 넘어, **왜 그 등급인지**와 **무엇을 하면 등급이 오르는지**를 설명하는 것을 목표로 설계되었습니다.

- **모델: LightGBM** — 수치형·범주형이 섞인 정형 데이터, 제한된 데이터 규모, 결측치 네이티브 처리, SHAP과의 호환성을 함께 고려한 선택입니다.
- **XAI: "한 단계 위 등급" 기준 SHAP** — 예측된 등급이 아니라 **한 단계 위 목표 등급(target class)** 을 기준으로 SHAP 값을 계산합니다. 이렇게 하면 "지금 등급의 이유"가 아니라 **"다음 등급에 도달하려면 무엇을 개선해야 하는가"** 라는, 사용자에게 실질적으로 도움이 되는 관점의 설명을 얻을 수 있습니다. 양수 기여는 강점(유지 권장), 음수 기여는 개선 포인트로 분류합니다. (`S1`은 최고 등급이므로 개선 포인트를 생성하지 않습니다.)
- **개선 불가 요소 필터링** — 업력, 경영주 경력, 전통시장·역세권 여부, 상권/업종 트렌드처럼 사업자가 직접 바꿀 수 없는 변수는 조언 대상에서 제외하여, 실행 가능한 조언만 남깁니다.
- **조언의 이원화** — 동일한 SHAP 근거로 **고객용 조언**(쉬운 말, 친근한 `-해요`체, 4문장)과 **은행원용 분석**(객관적·간결한 심사 보조 요약)을 각각 생성합니다.
- **역할 분리** — AI 서버는 `s_grade_feature` 테이블에 대한 **읽기 전용** 권한만 사용합니다. 결과 저장(`s_grade_history`, `s_grade_report` 등)은 Spring BE 또는 배치가 담당합니다.

---

## 프로젝트 구조

```
SoFit-AI/
├── research/                  # 모델 학습·실험 (로컬 전용)
│   ├── data_preprocessing.py  # 전처리 + stratified train/val/test 분리
│   ├── train.py               # LightGBM 다중 클래스(S1~S10) 학습 → models/scb_model_v1.pkl
│   ├── test_*.py              # explainer / advisor / SHAP 출력 점검 스크립트
│   ├── notebook/              # EDA 및 XAI 분석 노트북
│   ├── DATA_PREPROCESSING.md
│   └── requirements.txt
│
├── serving/                   # FastAPI 서빙 (운영 환경)
│   ├── main.py                # 엔드포인트 정의 + lifespan(모델/Explainer/Advisor 초기화)
│   ├── predictor.py           # .pkl 로드 및 S등급 추론
│   ├── explainer.py           # SHAP(TreeExplainer) 기반 강점/개선 포인트 추출
│   ├── advisor.py             # Gemini LLM 조언 생성 (고객용 + 은행원용)
│   ├── db.py                  # s_grade_feature 읽기 전용 조회
│   ├── schemas.py             # Pydantic 요청/응답 스키마
│   ├── app/core/              # config(settings), constants(SGrade)
│   ├── app/api/deps.py        # 싱글턴 의존성 주입
│   ├── Dockerfile             # 멀티스테이지 빌드 (builder → runtime)
│   ├── DEPLOYMENT.md          # 배포·운영 가이드
│   ├── requirements.txt       # 서빙 프로덕션 의존성
│   └── requirements-dev.txt   # 테스트/개발 의존성
│
├── batch/                     # 월별 배치 (전체 회원 등급 갱신)
│   ├── pipeline.py            # 배치 본체 (조회 → 추론 → SHAP → LLM → 적재)
│   ├── run_batch.py           # CLI 엔트리포인트 (crontab / 수동 트리거)
│   ├── db.py                  # 배치용 DB R/W (history, report, execution)
│   ├── config.py              # 환경변수 로드
│   ├── HANDOVER_SPRING_BOOT.md
│   ├── TEST_GUIDE.md
│   └── requirements.txt
│
├── database/                  # 스키마 및 테스트 데이터
│   ├── ddl/V1__create_s_grade_tables.sql
│   ├── V1.1__insert_mock_s_grade_data.sql
│   └── test/                  # 월별 테스트 데이터 삽입/초기화 SQL
│
├── data/                      # 로컬 학습용 데이터 (.gitignore)
│   └── generate_data.py       # 합성 데이터 생성 스크립트
├── models/                    # 모델 파일 (.gitignore)
├── Jenkinsfile                # CI/CD 파이프라인
└── README.md
```

---

## 아키텍처 개요

```
                          ┌──────────────────────────────────────────┐
   회원가입 (건별)         │            SoFit-AI (FastAPI)              │
 Spring BE ──────────────▶│  POST /api/s-grade/predict                 │
                          │   1) biz_data_id → s_grade_feature 조회     │
                          │   2) LightGBM 추론 → S등급                   │
                          │   3) SHAP(한 단계 위 등급 기준) → 강점/개선   │
                          │   4) Gemini → 고객용 + 은행원용 조언          │
                          │   5) JSON 반환 (DB 쓰기 없음)                │
   월별 (전체 갱신)         │                                            │
 crontab / 관리자 ────────▶│  POST /api/s-grade/batch (비동기 트리거)     │
                          │  GET  /api/s-grade/batch/status            │
                          │   → batch.pipeline 실행                     │
                          │   → s_grade_report / s_grade_history 적재    │
                          └──────────────────────────────────────────┘
                                            │
                                            ▼ (읽기: s_grade_feature)
                                    ┌──────────────┐
                                    │    MySQL     │
                                    └──────────────┘
```

서빙과 배치는 `serving/explainer.py`, `serving/advisor.py` 등 추론·설명 로직을 **공유**합니다. 배치는 `sys.path`에 `serving/`을 추가해 동일 모듈을 재사용하므로, 추론 결과의 일관성이 유지됩니다.

---

## API 엔드포인트

| 메서드 | 경로 | 호출 주체 | 설명 |
|--------|------|-----------|------|
| `GET`  | `/health` | 모니터링 | 서버 및 모델 로드 상태 확인 |
| `POST` | `/api/s-grade/predict` | Spring BE | **건별 산출** — `biz_data_id`로 피처를 DB 조회 후 등급·SHAP·조언 반환 |
| `POST` | `/api/s-grade/batch` | crontab / 관리자 | **월별 배치** 비동기 트리거 (즉시 `202`, 중복 실행 시 `409`) |
| `GET`  | `/api/s-grade/batch/status` | 관리자 페이지 | 최근 배치 실행 상태·진행 건수 집계 조회 |
| `POST` | `/predict` | (레거시) | 피처를 직접 전달받는 추론 엔드포인트 |

### `/api/s-grade/predict` 응답 요약
- `s_grade`, `target_grade` (다음 목표 등급, `S1`이면 `null`)
- `strength_keywords` / `improvement_keywords` — 고객 리포트용 한국어 키워드
- `strength_details` / `improvement_details` — 항목별 SHAP 기여도(관리자용)
- `user_advice` — 고객용 자연어 조언
- `admin_advice` — 은행원용 분석 요약

주요 에러: `404 FEATURE_NOT_FOUND`, `500 DB_CONNECTION_ERROR` / `MODEL_PREDICTION_FAILED`, `503 MODEL_NOT_LOADED`.

---

## 데이터베이스

서버 기동 시 `s_grade_feature` 테이블이 존재해야 하며, 모델 입력 피처는 **31개** 컬럼입니다(매출 증가율, 거래 활동성, 업력/직원 대비 성장성, 상권·입지, 리뷰·배달, 온라인 활동 등).

| 테이블 | 서빙 권한 | 배치 권한 | 용도 |
|--------|-----------|-----------|------|
| `s_grade_feature` | READ | READ | 모델 입력 피처 |
| `s_grade_history` | – | READ/WRITE | 등급 산출 요청·상태(`REQUESTED`/`CALCULATING`/`COMPLETED`/`FAILED`) |
| `s_grade_report` | – | WRITE | 산출 결과·조언 적재 |
| `batch_execution_history` | READ | WRITE | 배치 실행 이력(`RUNNING`/`COMPLETED`/`FAILED`) |

DDL은 `database/ddl/V1__create_s_grade_tables.sql`, 목업/테스트 데이터는 `database/V1.1__...`, `database/test/`를 참고하세요.

---

## 환경 설정

### 사전 요구사항
- Python 3.11 이상
- Git
- (서빙·배치) 접근 가능한 MySQL 인스턴스
- Google Gemini API 키

### 1. 클론 및 가상환경

```bash
git clone https://github.com/woori-SoFit/SoFit-AI.git
cd SoFit-AI

python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 2. 환경변수 (`.env`)

프로젝트 루트에 `.env` 파일을 생성합니다.

```env
# Gemini LLM
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-3.1-flash-lite

# MySQL
DB_HOST=localhost
DB_PORT=3306
DB_USERNAME=sofit
DB_PASSWORD=your_password
DB_NAME=sofit

# 모델 (선택 — 기본값 존재)
MODEL_VERSION=v1
# MODEL_DIR=/app/models
```

`GEMINI_API_KEY`가 비어 있으면 서버는 정상 기동하되 조언 생성만 비활성화되고, 모델 파일이 없으면 추론 요청에 `503`을 반환합니다(서버 자체는 기동).

### 3-A. 모델 학습 / 데이터 생성 (research)

```bash
pip install -r research/requirements.txt

python data/generate_data.py            # 합성 데이터 생성 → data/ (gitignore)
python research/train.py                # LightGBM 학습 → models/scb_model_v1.pkl
jupyter notebook research/notebook/     # EDA · XAI 분석
```

학습은 다중 클래스(S1~S10, 10클래스) 분류로, LightGBM 네이티브 범주형 처리와 early stopping을 사용하며 stratified 분리(test 15%)로 평가합니다.

### 3-B. 서빙 로컬 실행 (serving)

```bash
pip install -r serving/requirements-dev.txt

cd serving
uvicorn main:app --reload --port 8000

# 테스트 / 린트
pytest -v --cov=. --cov-report=term-missing
ruff check . && ruff format --check .
```

### 3-C. 월별 배치 실행 (batch)

```bash
pip install -r batch/requirements.txt

# 자동(crontab) 실행
python -m batch.run_batch

# 수동 트리거 (관리자 user_id 지정)
python -m batch.run_batch --type manual --triggered-by 2001
```

crontab 예시 (매월 1일 23:40):

```cron
40 23 1 * * cd /app/SoFit-AI && python -m batch.run_batch
```

배치는 항목별로 메모리 내 **최대 3회 즉시 재시도**하며, 시작 시 이전 비정상 종료로 남은 `CALCULATING` 고아 건을 `REQUESTED`로 1회 복구합니다.

### 3-D. Docker 빌드 (운영)

빌드 컨텍스트는 **레포 루트**입니다(`serving/`과 `batch/`를 함께 이미지에 포함).

```bash
docker build -t sofit-ai:local -f serving/Dockerfile .
docker run -p 8000:8000 -v $(pwd)/models:/app/models sofit-ai:local
```

---

## 모델 파일 관리

모델 파일(`scb_model_v1.pkl`)은 보안·용량 문제로 **Git에 포함하지 않습니다**(`.gitignore`).

- 학습은 로컬에서 수행하고, 산출된 `.pkl`을 온프레미스 서버 `models/` 디렉토리에 직접 배치합니다.
- 파일명 규칙: `scb_model_<버전>.pkl` (예: `scb_model_v1.pkl`).
- Docker 운영 시 호스트의 모델 디렉토리를 컨테이너 `/app/models`로 볼륨 마운트합니다.
- **모델 교체 시 서버 재시작이 필요합니다** (기동 시 1회 로드 후 싱글턴으로 재사용).

### 학습된 모델 다운로드

직접 학습하지 않고 바로 서버를 띄우고 싶다면, 배포된 학습 모델을 내려받아 `models/` 디렉토리에 두면 됩니다.

| 버전 | 파일 | 다운로드 | 체크섬(SHA256) |
|------|------|----------|----------------|
| v1 | `scb_model_v1.pkl` | [다운로드](https://github.com/woori-SoFit/SoFit-AI/releases/download/model-v1/scb_model_v1.pkl) | [`scb_model_v1.pkl.sha256`](https://github.com/woori-SoFit/SoFit-AI/releases/download/model-v1/scb_model_v1.pkl.sha256) |

> 위 링크는 GitHub Releases 배포를 가정한 예시 경로입니다. 실제 릴리스 태그(`model-v1` 등)를 생성한 뒤 URL을 맞춰주세요.

**1) 모델 디렉토리 준비 후 다운로드** (OS 공통)

```bash
mkdir -p models
curl -L -o models/scb_model_v1.pkl \
  https://github.com/woori-SoFit/SoFit-AI/releases/download/model-v1/scb_model_v1.pkl
curl -L -o models/scb_model_v1.pkl.sha256 \
  https://github.com/woori-SoFit/SoFit-AI/releases/download/model-v1/scb_model_v1.pkl.sha256
```

**2) 무결성 검증** (`.pkl`은 로드 시 코드 실행 위험이 있으므로 권장)

```bash
cd models

# macOS
shasum -a 256 -c scb_model_v1.pkl.sha256

# Linux
sha256sum -c scb_model_v1.pkl.sha256
```

`scb_model_v1.pkl: OK` 가 출력되면 정상입니다. (Windows PowerShell은 `Get-FileHash scb_model_v1.pkl -Algorithm SHA256` 으로 해시를 출력해 체크섬 파일 값과 직접 비교하세요.)

> **보안 주의**: 모델은 pickle 포맷이라 신뢰할 수 없는 출처의 파일을 로드하면 임의 코드가 실행될 수 있습니다. 공식 릴리스에서만 받고, 반드시 체크섬을 검증하세요.

### (관리자용) 새 모델 릴리스 배포

학습 후 새 모델을 배포할 때는 GitHub Releases에 에셋으로 첨부합니다(파일당 2GiB 미만, 대역폭 제한 없음).

```bash
# 체크섬 생성
shasum -a 256 scb_model_v1.pkl > scb_model_v1.pkl.sha256   # macOS
# sha256sum scb_model_v1.pkl > scb_model_v1.pkl.sha256     # Linux

# GitHub CLI로 릴리스 생성 및 에셋 업로드
gh release create model-v1 \
  scb_model_v1.pkl scb_model_v1.pkl.sha256 \
  --title "SCB Model v1" \
  --notes "학습 데이터: s_input_feature_40k / Accuracy: ~0.45 / QWK: ~0.89"
```

릴리스 노트에는 학습 데이터 버전과 평가 지표를 함께 남겨 모델 카드 역할을 하도록 합니다. 학습 데이터가 합성 데이터이므로 공개 릴리스 배포가 적합하며, 실데이터로 전환 시에는 사내 오브젝트 스토리지(OpenStack Swift 등) + 만료형 링크로 비공개 배포하는 것을 권장합니다.

---

## CI/CD

`Jenkinsfile`은 온프레미스 환경에서 다음 단계를 수행합니다.

1. **Cleanup** — 72시간 경과한 dangling 이미지 정리(디스크 고갈 방지)
2. **Checkout** — 소스 체크아웃
3. **Prepare Model** — 모델 파일 준비 단계(현재는 플레이스홀더). 릴리스나 사내 스토리지에서 모델을 받아오는 로직을 이 단계에 채워 자동화할 수 있습니다.
4. **Docker Build & Push** — `serving/Dockerfile`로 빌드 후 프라이빗 레지스트리(`172.21.33.225:5000`)에 push
5. **Deploy** — 앱 서버에 SSH 접속하여 이미지 pull 후 `docker compose up -d sofit-ai`

상세 인프라·환경변수·운영 절차는 `serving/DEPLOYMENT.md`, Spring 연동 변경사항은 `batch/HANDOVER_SPRING_BOOT.md`를 참고하세요.

---

## 기술 스택

| 영역 | 사용 기술 |
|------|-----------|
| 웹 프레임워크 | FastAPI, Uvicorn |
| 검증 | Pydantic v2, pydantic-settings |
| ML / XAI | LightGBM, SHAP, scikit-learn, NumPy, pandas |
| LLM | Google Gemini (`google-generativeai`) |
| DB | MySQL, PyMySQL |
| 인프라 | Docker(멀티스테이지), Jenkins, 프라이빗 레지스트리 |
