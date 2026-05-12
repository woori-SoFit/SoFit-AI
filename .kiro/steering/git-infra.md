# git-infra

# SoFit Git & 인프라 컨벤션

## 커밋 컨벤션

```
[Feat] 새로운 기능 추가
[Fix] 버그 수정
[Refactor] 코드 리팩토링 (기능 변화 없음)
[Style] 포맷팅, 세미콜론 누락, 들여쓰기 등
[Docs] README, 주석 등 문서 수정
[Test] 테스트 코드 추가/수정
[Chore] 빌드 설정, 패키지 매니저 등 자잘한 작업
```

예시: `[Feat] 대출 신청 API 구현 - SOFIT-123`

## 브랜치 전략

- Jira 이슈 번호로 브랜치 생성
- 브랜치명: `feature/SOFIT-123-loan-application`
- 레포별로 Jenkins 파이프라인이 따로 구성되어 있으므로 별도 접두사 불필요

## PR 규칙

- PR 제목에 Jira 이슈 번호 포함
- SonarQube 품질 게이트 통과 후 머지
- 최소 1명 리뷰 승인 필요
- steering 파일 변경은 팀 전체 리뷰

## CI/CD (Jenkins)

- 레포별로 파이프라인 독립 구성
    - SoFit-backend → BE 파이프라인
    - SoFit-frontend → FE 파이프라인
    - SoFit-AI → AI 파이프라인
- SonarQube 코드 품질 검사 초기부터 적용
- SoFit-external-mock은 CI/CD 없음 (별도 노트북 수동 운영)

## 인프라

- **온프레미스 OpenStack**
    - `dev-app`: 애플리케이션 서버 (4 vCPUs / 4GB RAM / 40GB)
    - `sofit-cicd`: Jenkins + SonarQube (4 vCPUs / 4GB RAM / 40GB)
- **컨테이너**: Docker + Docker Compose
- **DB**: MySQL (메인), PostgreSQL (SonarQube 전용), Redis (세션)
- SonarQube DB(PostgreSQL)와 서비스 DB(MySQL) 혼동 금지

## 환경 분리

- Dev: 개발/테스트용 (현재 운영)
- Release: 프로덕션 (이중화 포함, 추후 구축)
- 환경별 설정: `application-dev.yml` / `application-release.yml` 분리