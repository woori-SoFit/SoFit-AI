# tech-stack

# SoFit 기술 스택

## Backend (SoFit-backend)

- **언어/프레임워크**: Java, Spring Boot
- **모듈 구조**: Gradle 멀티모듈
    - `common`: 공통 엔티티, 예외, 응답 포맷, 유틸
    - `gateway`: 클라이언트 요청 라우팅
    - `user-backend`: USER 대상 API 서버
    - `admin-backend`: BANK_ADMIN, DEV_ADMIN 대상 API 서버
- **DB**: MySQL (메인), Redis (세션)
- **ORM**: JPA (QueryDSL은 필요 시 추후 추가)
- **인증**: 세션 기반 (MVP), Redis 세션 저장
- **배치**: Spring Batch
    - 일일 배치: 신규 USER + 대출 신청 USER S등급 산출
    - 월별 배치: 전체 회원 S등급 갱신
- **AI 호출**: RestTemplate (내부망 HTTP, Spring Batch에서만 호출)
- **LLM 연동**: Spring AI + Gemini (SHAP 결과 → 자연어 변환, BE에서 처리)
- **로그 수집**: Spring AOP (api_logs 테이블)
- **테스트**: JUnit 5 + Mockito
- **커버리지**: JaCoCo (SonarQube 연동용 커버리지 리포트 생성)
- **정적 분석**: SonarQube (JaCoCo 리포트 + CheckStyle 기반 코드 품질 게이트)

## AI (SoFit-AI)

- **언어/프레임워크**: Python, FastAPI
- **ML 모델**: LightGBM (LGBM)
- **모델 파일**: .pkl 온프레미스 서버 로컬 저장 (`models/` 디렉토리)
- **모델 학습**: AI 팀장 로컬 컴퓨터에서 학습 → .pkl 결과물을 온프레미스 서버로 복사
- **XAI**: SHAP 기반 설명 생성
- **역할**: 성장S등급(S1~S10) 추론 + SHAP 설명 생성
- **호출 주체**: Spring Batch만 호출 가능
- **테스트**: pytest + pytest-cov (커버리지)
- **정적 분석**: ruff (린트 + 포맷), SonarQube 연동

## Frontend (SoFit-frontend)

- **언어/프레임워크**: TypeScript, React
- **구조**: 모노레포
    - `packages/user`: 고객용 앱
    - `packages/admin`: 은행원+개발자용 앱
    - `packages/common`: 공통 컴포넌트, 훅, 타입, 유틸
- **상태관리**: React Query (서버 상태) + Zustand (클라이언트 상태)
- **스타일링**: Tailwind CSS
- **테스트**: Vitest + React Testing Library
- **정적 분석**: ESLint + SonarQube 연동

## DevOps (SoFit-DevOps)

- **컨테이너**: Docker + Docker Compose
- **인프라**: OpenStack 온프레미스
    - `dev-app`: 애플리케이션 서버 (4 vCPUs / 4GB RAM / 40GB)
    - `sofit-cicd`: Jenkins + SonarQube 서버 (4 vCPUs / 4GB RAM / 40GB)
- **CI/CD**: Jenkins (BE/FE/AI 레포별 파이프라인)
- **코드 품질**: SonarQube (PostgreSQL 사용)
- **배포 환경**: Dev → Release (이중화 포함, 추후 구축)

## External Mock (SoFit-external-mock)

- 국세청 API, CB사, 금융인증서 Mock
- 별도 노트북에서 운영 (CI/CD, 이중화 없음)
- My Biz Data는 External Mock 경유 없이 DB에 직접 저장