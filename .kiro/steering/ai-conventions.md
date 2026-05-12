# ai-conventions

# SoFit AI 개발 컨벤션

## 역할

- Spring Batch 요청을 받아 LGBM 모델로 S등급(S1~S10) 산출
- SHAP 값 기반 XAI 설명 생성 (기여 변수 top-N, 기여 방향, 개선 로드맵)
- 사용자 직접 호출 불가 — Spring Batch에서만 호출

## 프로젝트 구조

```
SoFit-AI/
├── research/              # 모델 학습 및 실험 소스코드 (아카이브)
│   ├── data_preprocessing.py
│   ├── train.py           # 로컬에서 실행할 학습 스크립트
│   └── notebook/          # EDA나 실험 기록용 Jupyter Notebook
│       └── 01_eda_and_training.ipynb
│       └── 02_xai_analysis.ipynb     <-- SHAP 수치를 분석하고 시각화해본 실험 기록 추가
├── serving/               # FastAPI 서빙 코드 (실제 운영 시 사용)
│   ├── app/
│   │   ├── core/              # 설정 및 S1~S10 상수 관리 (SCB 혼동 원천 차단)
│   │   │   ├── config.py      # 모델 버전(v1, v2 등) 및 경로 설정 관리
│   │   │   └── constants.py   # S1~S10 등급 Enum 정의 (SCB 점수와 혼동 방지)
│   │   ├── api/           # 의존성 주입 (모델/XAI 객체 효율적 관리)
│   │   │   └── deps.py        # 모델 객체 주입(Dependency Injection) 관리
│   │   ├── main.py        # API 엔드포인트
│   │   ├── explainer.py   # SHAP을 이용한 설명(XAI) 로직
│   │   ├── schemas.py     # Request/Response Pydantic 모델 정의
│   │   └── predictor.py   # 모델 로드 및 추론 로직
│   ├── tests/                 # CI/CD 환경에서 422 에러 및 추론 결과 검증용 유닛 테스트
│   ├── requirements.txt
│   └── Dockerfile
├── models/                # [.gitignore] 실제 모델 파일(.pkl, .h5 등)이 저장될 곳
├── data/                  # [.gitignore] 로컬 학습용 데이터셋
├── .gitignore             # models/와 data/ 폴더 내부 파일 제외 설정
└── README.md              # 모델 및 데이터셋 다운로드 링크 기재
```

## 모델 관리

- 모델 파일(.pkl): 온프레미스 서버 `models/` 디렉토리에 저장
- 학습은 AI 팀장 로컬 컴퓨터에서 수행 → .pkl 결과물을 서버로 복사
- 모델 버전 관리: 파일명에 버전 포함 (`scb_model_v1.pkl`)
- 서버 시작 시 모델 로드, 모델 교체는 서버 재시작으로 처리

## S등급 vs SCB 점수 구분

- **S등급**: LGBM ML 모델 출력값 (S1~S10) — AI 서버 담당
- **SCB 점수**: CB 점수 + S 가산점 — AI 서버 관여 없음
- 코드/변수명에서 혼용 금지

## API 규칙

- 필수 입력 변수 누락 시 422 반환 (추론 불가 처리)
- 추론 결과는 BE가 DB에 저장 (AI 서버 DB 직접 접근 금지)
- 응답: 등급(S1~S10) + SHAP 설명 포함

## 코딩 규칙

- Python 타입 힌트 필수
- Pydantic으로 요청/응답 스키마 정의
- 함수/변수명: snake_case
- 클래스명: PascalCase