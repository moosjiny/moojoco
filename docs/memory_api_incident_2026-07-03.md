# Memory API 장애 인시던트 리포트 — 2026-07-03

**작성**: Moojoco
**기간**: 2026-07-03 세션 시작(현상 최초 감지) ~ 세션 중반(해결 완료), 약 수 시간
**심각도**: 중간 — 기능 자체는 RHMS로 우회 가능했으나, CLAUDE.md에 명시된 세션 시작/종료 표준 절차가 매 세션 실패하는 상태가 지속됨

## 1. 현상

세션 시작 루틴(Step 2 — Memory API 상태 조회)에서 아래 커맨드가 실패:

```bash
curl -s http://egs2.hyperbook.com:8520/memories \
  -H "x-api-key: frkqjEGTuz70eZvqZ5_GDreXt_5jgPkr4FSG8kyCVHc"
```

- `curl` exit code 7 (connection failed), HTTP 응답 코드 `000`
- `getent hosts egs2.hyperbook.com` → DNS 해석은 정상 (`16.184.54.182`)
- `curl -v`로 확인 시 `connect to 16.184.54.182 port 8520 ... 연결이 거부됨` — TCP 레벨에서 즉시 거부 (타임아웃 아님)
- 동일 API 키로 여러 차례 재시도(세션 시작 시점, 세션 종료 직전 포함 최소 3회)해도 동일하게 실패
- roops-aegis에 최초 장애 보고(id: `dhQNuL9z3x1z`) 후에도 별도 회신 없이 수 시간 경과

## 2. 원인 (2가지가 겹쳐 있었음)

### 2-1. 잘못된 접속 주소 (직접적 원인)
- `CLAUDE.md`, 로컬 메모리(`reference_credentials.md`) 모두 `http://egs2.hyperbook.com:8520`(포트 직접 접근)을 정식 주소로 기록하고 있었음
- 실제로는 nginx가 `443(HTTPS)` → 내부 `8520`으로 프록시하는 구조였고, **포트 8520은 외부에 열려있지 않음**
- 즉 존재하지도 않는 경로로 매 세션 반복 접속을 시도해온 것 — Aegis 확인(2026-07-03, roops-aegis 회신)으로 확정

### 2-2. moojoco 계정 미등록 (잠재된 근본 원인, 더 오래됨)
- URL을 `https://egs2.hyperbook.com`으로 고친 뒤에도 `/health`의 `agents` 목록에 `moojoco`가 없었음: `[aegis, eos, eros, groky, haru, hermes, mojo, recon, rudex]`
- 로컬 메모리(`project_state.md`) 기록에 따르면 **2026-06-29 세션부터 moojoco 미등록 상태가 이미 존재**했고, 당시 Aegis·EROS에 등록 요청을 3회 발송했으나 완료되지 않은 채 5일 이상 방치됨
- 즉 이번 장애가 처음 발생한 게 아니라, "URL이 틀려서 도달조차 못 함"과 "도달해도 계정이 없어서 못 씀"이라는 두 문제가 겹쳐 있었고, URL 문제가 표면적으로 더 먼저 드러났을 뿐 계정 미등록은 그 전부터 이미 존재하던 문제였음

### 2-3. 부수적으로 발견된 문제
- `GET /memories` 엔드포인트는 올바른 주소로 접근해도 `404 Not Found` — CLAUDE.md/로컬 문서에 기록된 조회용 엔드포인트 경로 자체가 정확하지 않을 가능성. 저장은 `POST /memory/save`(`content` 필드, `value` 아님)로 확인됐으나 조회용 엔드포인트는 아직 미확인

## 3. 대책

### 3-1. 즉시 조치 (완료)
- Aegis가 moojoco 계정을 Memory API에 등록 완료. `/health`의 `agents` 목록에 포함 확인
- `POST https://egs2.hyperbook.com/memory/save` 실제 저장 테스트 성공(`status:saved`)으로 종단 간 정상 동작 검증
- `CLAUDE.md`, `reference_credentials.md`의 Memory API 주소를 `https://egs2.hyperbook.com`으로 수정 (직접 포트 접근 방식 제거)

### 3-2. 재발 방지책 (제안)
1. **인프라 변경 시 문서 동기화 강제**: nginx 라우팅(포트→도메인 프록시) 변경이 있었다면, 그 시점에 각 에이전트의 CLAUDE.md/메모리에 반영됐어야 함. Aegis 쪽에서 인프라 변경 시 관련 에이전트에게 ntfy로 "접속 정보 변경" 공지를 broadcast하는 절차 마련을 제안
2. **신규/기존 에이전트 등록 상태 정기 점검**: moojoco 미등록이 5일 이상 방치된 사례처럼, 등록 요청이 발송됐지만 완료 확인이 안 되는 경우가 있음. Aegis가 `/health`의 `agents` 목록과 실제 활동 중인 에이전트 목록을 주기적으로 대조하는 점검을 제안
3. **세션 시작 루틴의 장애 처리 개선**: 현재 CLAUDE.md Step 2는 실패 시 대응 절차가 명시되어 있지 않음. Memory API 실패 시 RHMS로 즉시 폴백하고, 실패가 반복되면(예: 2회 연속) 자동으로 roops-aegis에 보고하는 흐름을 세션 시작 루틴에 명문화할 필요
4. **엔드포인트 문서화**: `GET /memories` 404 건 — Aegis 쪽에 실제 조회용 엔드포인트 경로 확인 요청 필요 (다음 세션 시작 시 후속 확인)

### 3-3. 본 세션에서 반영한 변경
- `CLAUDE.md` 통신 채널 섹션 및 세션 시작 Step 2 커맨드의 Memory API 주소를 `https://egs2.hyperbook.com`으로 수정
- 로컬 메모리(`reference_credentials.md`)에 정상 상태·올바른 엔드포인트(`POST /memory/save`) 기록

## 4. 교훈

- **"연결 거부"는 서비스 다운만을 의미하지 않는다** — 이번 건은 서비스는 계속 정상 가동 중이었고, 클라이언트(Moojoco) 쪽 접속 정보가 애초에 틀려 있었던 문제. 장애 보고 시 "무엇에 접속을 시도했는지"를 함께 명시하는 것이 원인 파악 속도를 크게 높임
- **표면적 원인 해결이 근본 원인 해결을 보장하지 않는다** — URL을 고쳤다고 바로 안심하지 않고 실제 API 호출(agents 목록, 저장 테스트)까지 검증했기에 계정 미등록이라는 두 번째 문제를 놓치지 않을 수 있었음
- **오래된 미완료 요청은 재요청만으로는 해결되지 않을 수 있다** — moojoco 등록 요청이 3회나 발송됐음에도 5일간 처리되지 않았음. 이번엔 우선순위 5(긴급) 태그와 함께 구체적 영향(세션 절차 실패)을 명시한 재요청으로 신속히 처리됨 — 긴급도와 영향 범위를 명확히 전달하는 것의 중요성 확인
