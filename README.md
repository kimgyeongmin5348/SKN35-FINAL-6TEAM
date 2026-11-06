# SKN35-FINAL-6TEAM — BUILDWISE

고객 상담·피드백을 분석하고, 역할별 AI 에이전트의 작업을 오피스 UI로 보여주는 프로젝트입니다.

현재는 **폴더 구조만 준비된 단계**입니다. 새 폴더에는 Git 추적을 위한 `.gitkeep`만 있으며, 서버·LLM·데이터셋·배포 환경은 구현하거나 연결하지 않았습니다. 모델, 프론트엔드 프레임워크, 데이터베이스는 추후 확정합니다.

## 프로젝트 구조

하나의 저장소에서 백엔드와 프론트엔드를 함께 관리합니다. 에이전트는 우선 하나의 백엔드 내부 모듈로 나누며, 개별 서비스로 배포하는 구조는 전제하지 않습니다.

```text
SKN35-FINAL-6TEAM/
├── backend/
│   ├── app/
│   │   ├── api/v1/                 # HTTP API, 실시간 이벤트 연결 진입점
│   │   ├── core/                   # 환경 설정, 로깅, 공통 오류 처리
│   │   ├── schemas/                # 백엔드 내부·API 입출력 데이터 모델
│   │   ├── agents/
│   │   │   ├── consultation/       # 상담, 요구사항 추출, 피드백 분석
│   │   │   ├── solution/           # 추천 후보 설계, 재설계
│   │   │   ├── validation/         # 검증 도구 실행, 근거 취합
│   │   │   └── quotation/          # 비교 결과·견적 구성
│   │   ├── orchestration/         # 작업 실행, 상태, 인계, 재시도, 요구사항 버전
│   │   ├── services/              # 상담 이력·문서 생성·발송 승인 등 업무 처리
│   │   ├── integrations/
│   │   │   ├── llm/               # LLM 제공자 연결
│   │   │   ├── speech/            # 음성 인식·합성 연결
│   │   │   ├── catalog/           # 제품·가격·공식 사양 데이터 연결
│   │   │   └── email/             # 이메일 서비스 연결
│   │   ├── rules/                 # 호환성·예산 등 결정적인 검증 규칙
│   │   └── db/
│   │       ├── models/            # 데이터베이스 저장 모델
│   │       └── repositories/      # 저장·조회 접근 로직
│   ├── migrations/               # 데이터베이스 스키마 변경 이력
│   └── tests/
│       ├── unit/                  # 개별 로직 테스트
│       └── integration/           # API·에이전트·저장소 연결 테스트
├── frontend/
│   ├── src/
│   │   ├── app/                   # 앱 시작점, 라우팅, 전역 구성
│   │   ├── features/
│   │   │   ├── consultation/      # 음성·텍스트 상담 화면
│   │   │   ├── office/            # 오피스 렌더링, 캐릭터, 상태 시각화
│   │   │   ├── requirements/      # 현재 조건·고객 피드백 표시 및 수정
│   │   │   ├── results/           # 추천 후보·검증·견적 결과
│   │   │   └── timeline/          # 실제 이벤트·산출물 연결
│   │   └── shared/
│   │       ├── api/               # 공통 API·SSE 또는 WebSocket 클라이언트
│   │       ├── components/        # 여러 기능에서 사용하는 UI 구성요소
│   │       ├── types/             # 프론트엔드 공통 타입
│   │       └── utils/             # 공통 유틸리티
│   ├── public/                    # 배포 시 그대로 제공할 정적 파일
│   └── tests/e2e/                 # 사용자 흐름 전체 테스트
├── contracts/
│   ├── api/                       # 팀이 공유하는 API 명세
│   ├── events/                    # 이벤트 이름·필드·상태 전환 규격
│   └── examples/                  # 합의된 요청·응답·이벤트 예시
├── data/
│   ├── raw/                       # 수집한 원본 자료
│   ├── processed/                 # 정제·구조화한 제품 및 근거 데이터
│   ├── fixtures/                  # 개발·연동 확인용 가상 샘플
│   └── evaluation/                # 평가용 입력·기대 결과 데이터
├── docs/
│   ├── planning/                  # 기획서, 요구사항, 일정·역할 분담
│   ├── architecture/              # 시스템 구조·데이터 흐름 설명
│   └── decisions/                 # 기술 선택과 변경 이유 기록
├── infra/
│   ├── docker/                    # 컨테이너 실행 설정
│   └── deploy/                    # 배포 환경 설정
├── scripts/
│   ├── data/                      # 데이터 수집·정제·검증 작업 스크립트
│   └── dev/                       # 로컬 개발 보조 스크립트
├── .github/workflows/             # 향후 CI·CD 자동화
├── assets/                        # 기존 오피스 에셋·생성 스크립트 유지
├── ui/                            # 기존 오피스 시연용 HTML 유지
├── main.py                        # 기존 초기 진입 파일 유지
├── pyproject.toml                 # 현재 Python 프로젝트·의존성 설정
├── uv.lock                        # 현재 Python 의존성 잠금 파일
└── README.md
```

## 폴더별 경계

- `api/`는 요청 접수와 응답을 담당하고, 실행 흐름은 `orchestration/`에서 관리합니다.
- `agents/`에는 역할별 판단·프롬프트·도구 조합을 둡니다. 각 역할의 프롬프트와 전용 도구는 해당 에이전트 폴더 안에서 관리합니다.
- `rules/`는 LLM과 분리하여 검증할 수 있는 규칙을, `integrations/`는 외부 서비스 통신을 담당합니다.
- `services/`는 문서 생성과 발송 승인 같은 업무 로직을, `db/repositories/`는 저장과 조회를 담당합니다.
- `schemas/`는 입출력 모델, `db/models/`는 저장 모델입니다. 팀 간 공개 규격은 `contracts/`에 모읍니다. 구현 후 자동 생성 가능한 API 명세·타입은 생성 기준을 정해 중복 수정을 줄입니다.
- 프론트엔드는 기능별로 화면·상태·전용 로직을 모읍니다. 여러 기능에서 실제로 공유하는 것만 `shared/`로 옮깁니다. 단위 테스트는 대상 기능 가까이에 두고 전체 흐름 테스트는 `tests/e2e/`에 둡니다.
- `data/fixtures/`의 가상 샘플과 실제 제품 자료·평가 데이터를 구분합니다. 원본의 출처와 정제 과정은 데이터 확보 단계에서 함께 기록합니다.
- 기존 `ui/`와 `assets/`는 현재 시연의 경로를 유지합니다. 정식 프론트엔드 도입 시 에셋 제공 방식과 이전 범위를 별도로 결정합니다.

## 5인 팀 담당 기준

| 담당 | 주로 작업할 경로 |
|---|---|
| 상담·피드백 | `backend/app/agents/consultation/`, `backend/app/integrations/llm/`, `backend/app/integrations/speech/` |
| 설계·데이터 | `backend/app/agents/solution/`, `backend/app/integrations/catalog/`, `data/`, `scripts/data/` |
| 검증·평가 | `backend/app/agents/validation/`, `backend/app/rules/`, `data/evaluation/` |
| 백엔드 통합·견적 | `backend/app/api/`, `backend/app/orchestration/`, `backend/app/agents/quotation/`, `backend/app/services/`, `backend/app/db/` |
| 프론트엔드 | `frontend/`, 기존 `ui/`와 `assets/` 연계 |

공통 스키마·계약·설정과 배포 구성은 담당자를 정해 조율합니다. 각 담당자는 자기 기능의 테스트와 통합까지 함께 책임집니다. `.gitkeep`는 해당 폴더에 실제 파일이 추가되면 제거할 수 있습니다.
