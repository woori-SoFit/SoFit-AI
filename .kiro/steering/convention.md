## Branch

**브랜치 구조**

```cpp
main                        ← 릴리즈용 (추후 구축)
dev                         ← 통합 개발 브랜치
feat/SOFIT-티켓번호-기능명  ← 작업 브랜치
```

**브랜치 명**

```cpp
feat/SOFIT-1-회원가입-API
```

**코드 구현 하실 때**

1. Jira에서 이슈 생성
2. Jira에서 브랜치 자동 생성 (`feat/` 꼭 붙여주세요)
    - 브랜치 수동 생성 (지라 티켓 번호 꼭 붙여주세요. ex. `SOFIT-33`)
3. 해당 브랜치에서 작업
4. PR 생성
5. 팀원 리뷰 후 dev에 머지

## 커밋 컨벤션

```java
[SOFIT-30] Chore: Docker Compose 설정 수정
```

| 태그 | 설명 |
| --- | --- |
| Feat | 새로운 기능 추가 |
| Fix | 버그 수정 |
| Refactor | 코드 리팩토링 (기능 변화 없음) |
| Style | 포맷팅, 세미콜론 누락, 들여쓰기 등 |
| Docs | README, 주석 등 문서 수정 |
| Test | 테스트 코드 추가/수정 |
| Chore | 빌드 설정, 패키지 매니저 설정 등 자잘한 작업 |

## Jira 이슈 컨벤션

**이슈 타입**

| 타입 | 용도 | 커밋 태그 |
| --- | --- | --- |
| Task | 기능 개발 | [Feat] |
| Bug | 버그 수정 | [Fix] |

**Label**

```cpp
BE / FE / AI / DevOps
```

**이슈 제목**

```java
[Feat/Bug/Refactor] Title
```

**Task 템플릿**

```java
## 기능 요약

## 작업 내용
- [ ]
- [ ]
- [ ]

## 참고 사항
-

```

Bug **템플릿**

```jsx
## 버그 설명

## 재현 방법 (Given-When-Then)
**Given**
- 
**When**
- 
**Then**
- 

## 기대한 동작

## 실제 동작

## 환경 정보
(ex)
- Spring Boot: 3.3.1
- JDK: 17
- DB: MySQL 8.0.28
- OS: Windows 11

## 에러 로그 or 캡처
> 필요 시 에러 로그 일부 또는 화면 캡처 첨부

```

- Refactoring template (사용안함)
    
    ```jsx
    ## 목적
    
    ## 작업 항목
    - [ ]
    - [ ]
    - [ ]
    
    ## 참고사항
    - 
    
    ## 추후 해보고 싶은 것
    -
    
    ```
    

## PR 컨벤션

**제목**

```java
[Feat/Bug/Refactor] Title
```

**PR 템플릿 (`.github/pull-request-template.md`)**

```java
## 기능 설명

이번 PR에서 구현한 기능을 간단히 설명해주세요.

- 

## 작업 상세 내용

- [ ] 
- [ ] 
- [ ] 

## 확인한 내용

- [ ] 로컬 실행 확인
- [ ] 주요 기능 동작 확인
- [ ] 에러 로그 확인
- [ ] 기존 기능 영향 여부 확인

## 📸 스크린샷 / 실행 결과

## 기타 공유사항

## 관련 이슈

- closes #
```

## Jira 자동화

### 설정된 자동화 규칙

```cpp
브랜치 생성 (feat/SOFIT-23-OOO) → Jira 이슈 자동으로 진행 중 변
```

### 버그 전용 보드

```
Jira → Board → Filter: issuetype = Bug
버그만 따로 칸반 보드에서 관리
```