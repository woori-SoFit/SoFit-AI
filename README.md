# SoFit-AI

소상공인 성장 S등급(S1~S10) 추론 및 SHAP 기반 XAI 설명 생성 AI 서버.
Spring Batch에서만 호출하며, FastAPI + LightGBM으로 구성됩니다.

---

## 프로젝트 구조

```
SoFit-AI/
├── research/              # 모델 학습 및 실험 (로컬 전용, 아카이브)
│   ├── requirements.txt   # 학습/실험 환경 의존성
│   ├── data_preprocessing.py
│   ├── train.py
│   └── notebook/
│       ├── 01_eda_and_training.ipynb
│       └── 02_xai_analysis.ipynb
├── serving/               # FastAPI 서빙 코드 (운영 환경)
│   ├── requirements.txt       # 서빙 프로덕션 의존성
│   ├── requirements-dev.txt   # 서빙 테스트/개발 의존성
│   ├── Dockerfile
│   ├── main.py
│   ├── predictor.py
│   ├── explainer.py
│   ├── schemas.py
│   └── app/
│       ├── core/
│       │   ├── config.py
│       │   └── constants.py
│       └── api/
│           └── deps.py
├── data/                  # 로컬 학습용 데이터셋 (.gitignore 적용)
│   └── generate_data.py   # 합성 데이터 생성 스크립트
├── models/                # 모델 파일 (.gitignore 적용)
├── Jenkinsfile
└── README.md
```

---

## 환경 설정

### 공통 사전 요구사항

- Python 3.11 이상
- Git

### 1. 레포 클론

```bash
git clone <레포 URL>
cd SoFit-AI
```

### 2. 가상환경 생성

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS / Linux
# .venv\Scripts\activate   # Windows
```

---

### 3-A. 모델 학습 / 데이터 생성 환경 (research)

데이터 생성(`generate_data.py`), EDA, 모델 학습(`train.py`) 등 로컬 실험에 사용합니다.

```bash
pip install -r research/requirements.txt
```

**합성 데이터 생성 실행:**

```bash
python data/generate_data.py
```

생성된 CSV는 `data/` 폴더에 저장됩니다 (`.gitignore` 적용으로 커밋되지 않음).

**Jupyter 노트북 실행:**

```bash
jupyter notebook research/notebook/
```

---

### 3-B. 서빙 개발 / 테스트 환경 (serving)

FastAPI 서버 개발 및 pytest 실행에 사용합니다.

```bash
pip install -r serving/requirements-dev.txt
```

**로컬 서버 실행:**

```bash
cd serving
uvicorn main:app --reload --port 8000
```

**테스트 실행:**

```bash
cd serving
pytest tests/ -v --cov=. --cov-report=term-missing
```

**린트 / 포맷 검사:**

```bash
cd serving
ruff check .
ruff format --check .
```

---

### 3-C. 서빙 프로덕션 환경 (Docker)

Jenkins CI가 자동으로 빌드 및 배포합니다. 수동으로 빌드할 경우:

```bash
# 레포 루트에서 실행 (빌드 컨텍스트: 루트)
docker build -t sofit-ai:local -f serving/Dockerfile .
docker run -p 8000:8000 -v $(pwd)/models:/app/models sofit-ai:local
```

---

## 모델 파일 관리

모델 파일(`.pkl`)은 보안 및 용량 문제로 Git에 포함되지 않습니다.

- 학습은 AI 팀장 로컬 컴퓨터에서 수행
- 결과물(`.pkl`)을 온프레미스 서버의 `models/` 디렉토리에 직접 복사
- 파일명 형식: `scb_model_v1.pkl` (버전 포함)
- 모델 교체 시 서버 재시작 필요

모델 다운로드 링크: _(추후 업데이트 예정)_

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 및 모델 로드 상태 확인 |
| POST | `/predict` | S등급 추론 + SHAP 설명 반환 |

> **주의**: 이 API는 Spring Batch 전용입니다. 사용자 직접 호출 불가.
