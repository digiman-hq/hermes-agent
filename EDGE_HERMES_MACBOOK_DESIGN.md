# edge_hermes — MacBook 검증 배포 설계서

작성: PM (edge_hermes) / 대상: 하연의 MacBook Pro (`macbookpro.tail809feb.ts.net`)
상태: **설계 개정본 (codex app_server 확정 반영, 2026-07-16)**
관련 문서: [`TORAJIMA_TEAMS_DEPLOY.md`](./TORAJIMA_TEAMS_DEPLOY.md) (macmini 기존 Runbook)

---

## 0. TL;DR (역할별 요약)

- **목표**: 기존엔 macmini에 바로 배포했지만, 이번엔 **이 MacBook에서 먼저 배포·검증** → 완성되면 macmini로 이식.
- **dev 할 일**: 단일 인스턴스 hermes(torajima) 컨테이너 선기동 → 사용자가 `hermes setup`에서 **Codex(codex app_server) OAuth** 연결 → Teams/Funnel 연결. **(메모리는 이번 라운드 제외)**
- **qa 할 일**: health → Funnel 공개 → Teams 왕복 → **codex app_server 실제 응답** + 데모 시나리오까지 증거 기반 검증. (메모리 검증 제외)
- **pm(나)**: 본 설계서 유지·조율. 코드 수정·검수는 안 함.

---

## 1. 목적 / 배경

- 고객 **Torajima** 인계 전 Digiman 측 사전 검증 구성을 **MacBook에서 재현**한다.
- macmini는 provider(OpenRouter/Nous)가 결제 문제로 미동작이었음 → 이번엔 **codex app server(OpenAI Codex 백엔드에 OAuth 연결)를 뇌로** 써서 봇이 실제 응답하게 한다. **API 키/크레딧 불필요**(token cost는 로그인 계정에 부담).
- **메모리는 codex app_server 제약상 내장 memory 불가 → memory MCP 서버로 제공**(§5).

---

## 2. 기존(macmini) → 이 PC 변경점 매핑 (핵심)

| 영역 | macmini (기존) | 이 MacBook (변경) | 근거 |
|------|----------------|-------------------|------|
| 배포 구조 | 멀티유저 `hermes-user.sh` + `docker-compose.multiuser.yml` + `users/<user>.env` | **단일 인스턴스** (torajima 하나만) | 결정사항 |
| 모델 provider | OpenRouter/Nous (미동작) | **codex app server** (`hermes setup`→Codex→OAuth, API키 없음) | 결정사항 (§4) |
| 메모리 | (특별 설정 없음) | **이번 라운드 제외** (내장 memory는 app_server 불가 → 필요 시 memory MCP, 스미나가 컨펌 후) | 결정사항 (§5) |
| tailscale DNS | `digimanmac-mini.tail809feb.ts.net` | **`macbookpro.tail809feb.ts.net`** (100.103.165.109, active) | `tailscale status` |
| Funnel | 8443 → 127.0.0.1:3978 | **동일 패턴 8443 → 3978** (포트 전부 비어있음) | `lsof` 확인 |
| Teams 봇 등록 | endpoint = `.../digimanmac-mini...:8443/api/messages` | **기존 봇의 messaging endpoint를 이 PC 주소로 변경** | 결정사항 |
| Docker | 운영 중 | ✅ 기동 완료 (사용자) | — |

> **⚠️ 결정적 사실**: hermes 코드/config에는 **공개 엔드포인트 호스트명이 존재하지 않는다.** hermes는 로컬 `0.0.0.0:3978/api/messages`만 리스닝한다(`plugins/platforms/teams/adapter.py:105,768-779`). 공개 URL은 **오직 Microsoft Bot Framework 봇 등록 쪽**에만 있다(`adapter.py:1358`). 따라서 "봇 엔드포인트를 이 PC로 변경"은 **① Microsoft 측 봇 재등록 + ② 이 PC Funnel 구성**이며, hermes 코드는 건드리지 않는다.

---

## 3. 상세 설계 — ① 배포 구조 (단일 인스턴스)

- macmini의 멀티유저 오케스트레이션(`hermes-user.sh`) 대신 **단일 `docker-compose`로 torajima 인스턴스 하나만** 기동.
- **이미지: 표준 `docker build`로 충분** (dev 정정, PM 확인). 현재 main `Dockerfile:187`이 이미 `uv sync ... --extra all --extra messaging --extra teams ...`를 포함하므로, 기본 이미지에 **Teams 의존성이 이미 들어감**. → macmini 시절의 별도 `hermes-agent-teams:latest` 빌드/이식 절차는 **불필요**.
  - (구 Runbook §2의 "main Dockerfile에 teams extra 없음" 전제는 최신 main과 불일치 → 폐기.)
- 컨테이너 노출 포트: **3978**(hermes teams webhook 기본값, `adapter.py:104`).
- config/state 경로: 단일 인스턴스이므로 `~/.hermes-torajima/` 그대로 재사용 가능.

**dev 작업**: 이 PC용 단일 compose 파일 작성(예: `docker-compose.edge.yml`) — teams 이미지 + 포트 3978 + env 주입. 멀티유저 스크립트는 이식 전까지 사용 안 함.

---

## 4. 상세 설계 — ② 모델 provider (codex OAuth — **런타임 = codex_responses 확정**)

> **✅ 런타임 확정: `codex_responses` (Suminaga 동의, 2026-07-16/17)**. provider=`openai-codex`, model=`gpt-5.4-mini`, OAuth(`/opt/data/auth.json`, device_code). 인증은 ChatGPT/Codex 구독 OAuth(app_server와 동일): API 키 전부 미설정, 호출 `base_url=https://chatgpt.com/backend-api/codex`, 내부 판정 `billing_mode=subscription_included`.
>
> **과금 정확 (2026-07-17 정책)**: OpenAI **API키 종량과금은 없음**. 단 ChatGPT Codex는 완전 무과금 아님 — **구독 포함량 우선 사용 → 초과 시** 계정에 Codex credits 구매/Auto top-up ON이면 flexible credit 잔액에서 token rate card로 차감+자동결제 가능. **무예산 보장하려면 계정 Codex Settings→Usage Dashboard에서 Auto top-up OFF 확인.** (app_server도 동일.) 근거: help.openai.com codex-in-chatgpt / flexible-usage-credits / codex-rate-card-2.
>
> (이하 검토 이력)
>
> **dev 스모크 검증 결과**:
> - ✅ codex_responses에서 **실제 모델 응답 성공** (EDGE_CODEX_OK).
> - ✅ **내장 memory 정상 동작** (add/remove 성공, `/opt/data/memories/MEMORY.md` 기록 확인) → `_AGENT_LOOP_TOOLS` 하드블록은 **app_server 전용**. **codex_responses면 메모리가 그냥 켜진다** → §5 "메모리 보류"는 responses 선택 시 불필요해짐.
> - ⚠️ **M365 MCP는 이 fresh 컨테이너에 미등록** (`/opt/data/config.yaml` mcp_servers 비어있음, config.toml 없음, MSGRAPH creds absent). macmini 설정 미이식 상태 → 어느 런타임이든 **M365 MCP를 config.yaml에 새로 등록 + MSGRAPH creds 필요**.
>
> → **결론: 런타임 선택은 사실상 "메모리"만의 문제.** codex_responses = 뇌+메모리 다 동작(추천). app_server = 메모리는 MCP 별도 필요. M365·Teams는 어느 쪽이든 동일 작업. **Suminaga가 app_server를 특별히 원하지 않으면 codex_responses 권장.**

> **해석 (Slack 스레드 근거)**: "codex 서버"는 API 키 직결도, 자체 호스팅도 아니다. **hermes 내장 `hermes setup`의 provider 선택에서 "Codex"를 고르면**, hermes에 내장된 **codex app server 연결 모듈**이 OpenAI **Codex 백엔드에 OAuth로 연결**된다. `hermes setup`이 출력하는 **URL로 OpenAI에 로그인·승인**하면 끝. **API 키 발급/충전 불필요** — token cost는 로그인한 계정(구독)에 붙는다.

**설정 방법 (API 키 아님)**:
```
컨테이너 안에서:  hermes setup  →  provider 선택에서 "Codex" 선택
              →  출력된 URL을 브라우저에서 열어 OpenAI 로그인 + 승인(OAuth)
```
- `model.provider`/`base_url`/`OPENAI_API_KEY` 를 **수동으로 넣지 않는다.** setup 마법사가 codex app_server 연결을 config에 기록한다.
- 관련 구조: app_server는 에이전트 루프를 **codex 서브프로세스**에 위임하고, hermes 툴은 **stateless MCP 콜백**으로만 노출된다(이 특성이 §5 메모리 설계를 바꾼다).

**OAuth 계정 (결정)**:
- **1차 검증**: **사용자(하연) 개인 계정**으로 OAuth 승인 (임시).
- **후속**: 스미나가 씨 계정(원래 token cost 부담 주체)으로 **교체** — 이식/데모 전 재승인.

**⛔ 확인 필요**:
1. `hermes setup`의 provider 목록에 뜨는 **정확한 "Codex" 옵션 라벨** (dev가 컨테이너에서 실행해 확인)
2. OAuth 승인은 **사용자가 직접** (브라우저 로그인) — 자동화 불가
3. (주의) 사용자 계정이 **ChatGPT Plus**면 Codex-native 커넥터(SharePoint/Outlook)가 제한적 → M365는 별도 MCP/Graph로 붙임(§5·별도 이슈, 스레드 참조)

---

## 5. 상세 설계 — ③ 메모리 (**이번 라운드 보류 — 스미나가 컨펌 대기**)

> **🟡 결정 (2026-07-16, 사용자)**: 이번 라운드는 **메모리 제외**. codex 뇌 + Teams + 데모(메일/SharePoint)만 먼저 통과시키고, **memory MCP 도입은 스미나가 씨 컨펌 후** 후속 라운드에서 결정. 아래 기술 배경은 컨펌 논의용으로 보존.

> **🔴 왜 메모리가 별도 작업인가 (양자택일, 코드 검증됨)**: codex app_server를 provider로 쓰면 **hermes 내장 memory는 구조적으로 사용 불가**(`model_tools.py:594` `_AGENT_LOOP_TOOLS={todo,memory,session_search,delegate_task}` → `:1043`에서 loop 밖 호출 시 하드 에러). setup 토글로 못 뚫음. 따라서 **"codex 뇌 + 메모리"를 원하면 memory MCP가 유일한 길**이고, "내장 memory"를 원하면 뇌를 네이티브 provider로 바꿔야(=codex app_server 포기) 한다. 데모 시나리오엔 메모리 동작이 포함되지 않으므로 이번 제외가 안전.

**왜 내장 memory가 안 되나 (구조적 제약)**:
- 내장 memory는 hermes 에이전트 루프의 **라이브 상태**(세션 DB, memory manager)에 접근해야 한다.
- 그러나 app_server는 루프를 **codex 서브프로세스**에 넘기고, hermes 툴은 **stateless MCP 콜백**으로만 노출된다. 콜백 서브프로세스는 부모 AIAgent의 memory manager에 접근 불가 → **`model_tools.py:1043`에서 하드 블록**.
- 즉 config에서 `memory_enabled: true`를 켜도 app_server 하에선 런타임 에러. **설정으로 못 뚫는다.**

**해결: memory MCP 서버 부착** (M365를 MCP로 붙인 것과 동일 방식):
1. **memory MCP 서버 설치** — 예: 공식 `@modelcontextprotocol/server-memory`(지식그래프 기반 영속 메모리, node 실행) 또는 타 memory MCP.
2. **데이터 영속** — 저장소(repo/DB)를 **볼륨**(`/opt/data/...`)에 두어 재기동에도 유지.
3. **config 등록** — `config.yaml`의 `mcp_servers`에 등록 → codex-runtime으로 마이그레이션(또는 `config.toml` 직접).
4. **무인 자동승인** — `HERMES_CODEX_TRUSTED_MCP_SERVERS`에 그 서버명 추가.

→ 이러면 app_server에서도 "이거 기억해둬" / "아까 그거 뭐였지" 가 동작한다.

**"메모리 전부 사용" 요구의 번역**: 내장 memory 플래그(×) → **memory MCP 서버 1개 부착(○)**. 큐레이션 메모리·세션검색·스킬 자기개선 같은 hermes 내장 학습루프는 app_server 하에선 기대 불가(내장 memory에 묶여 있음). 필요하면 memory MCP가 제공하는 영속 기억으로 대체.

**⛔ 확인 필요**:
1. 어떤 **memory MCP 서버**를 쓸지 확정 (공식 server-memory 기본 권장)
2. 볼륨 경로 / 영속 정책
3. `HERMES_CODEX_TRUSTED_MCP_SERVERS` 등록으로 데모 중 승인 프롬프트 안 뜨게

> Honcho·hindsight 등 내장 memory provider 계열은 app_server 하에선 무의미 → 이번 범위 제외.

---

## 6. 상세 설계 — ④ Teams 봇 엔드포인트 (이 PC로 변경)

hermes는 로컬 3978만 리스닝하므로, "이 PC로 변경"은 **네트워크/등록 레이어** 작업이다.

**6-1. 이 PC Funnel 구성** (macmini와 동일 패턴, 포트 전부 비어있음):
```bash
tailscale funnel --bg --https=8443 http://127.0.0.1:3978
```
→ 공개 URL: `https://macbookpro.tail809feb.ts.net:8443/api/messages`

**6-2. Microsoft Bot Framework 봇 등록 endpoint 변경** (기존 봇 재사용):
- 기존 봇 `Hermes-Torajima` (CLIENT_ID `a99cd792-710e-47e4-9223-bb6af9319d91`, 테넌트 `DigiManAI`)의 **messaging endpoint를 이 PC 주소로 변경**.
  - 변경 전: `https://digimanmac-mini.tail809feb.ts.net:8443/api/messages`
  - 변경 후: `https://macbookpro.tail809feb.ts.net:8443/api/messages`
- 수단: Azure 포털의 Bot 리소스 messaging endpoint 수정, 또는 `teams app update` 계열.

> **트레이드오프(사용자 승인됨)**: 봇 하나의 endpoint를 이 PC로 돌리므로, **검증 기간 동안 macmini 쪽 Teams 왕복은 중단**된다. 이식 완료 후 endpoint를 macmini로 되돌리면 원복.

**6-3. hermes 측 Teams env** (config는 그대로, 값만 이식):
```bash
# users/torajima.env
TEAMS_CLIENT_ID=a99cd792-710e-47e4-9223-bb6af9319d91
TEAMS_CLIENT_SECRET=<기존 값 — macmini users/torajima.env 에서 복사>
TEAMS_TENANT_ID=d1bb8c2f-c460-4a3b-a05e-627c6118b5e9
TEAMS_ALLOWED_USERS=55206f0e-76ae-4cfd-98ee-710d017ffb2d
# TEAMS_PORT=3978  (기본값, 생략 가능)
```
- config.yaml: `platforms.teams.enabled: true`.

> **🔐 CLIENT_SECRET 방침 (확정)**: 봇 자격증명은 기기와 무관하므로 **이번 검증은 기존 시크릿 재사용**(macmini `users/torajima.env`의 `TEAMS_CLIENT_SECRET` 값을 이 PC로 복사). 재발급은 **실제 고객 인계 직전에만** 수행(노출 이력 세탁용, Runbook §8). → 검증 블로커 아님.

---

## 7. dev 구현 체크리스트 (순서 = 결정된 A안)

- [x] Docker Desktop 기동 (선행) — 사용자 완료 ✅
- [ ] **① 컨테이너 선기동**: 표준 `docker build`(main Dockerfile:187이 `--extra teams` 포함) + 단일 `docker-compose.edge.yml`(포트 3978) → 빈 껍데기라도 먼저 up. **사용자가 이 안에서 `hermes setup`을 돌릴 수 있게 인터랙티브 진입 경로(exec) 확보.**
- [ ] **② provider 연결(사용자 실행)**: 컨테이너 안 `hermes setup` → **Codex 선택** → 출력 URL로 **OAuth 승인(1차: 하연 개인계정)**. dev는 옵션 라벨·진입 방법만 안내.
- [ ] ~~**③ memory MCP 부착**~~ → **이번 라운드 제외 (스미나가 컨펌 후)**. 필요 시: memory MCP(`@modelcontextprotocol/server-memory`) → `config.yaml` `mcp_servers` 등록 → `HERMES_CODEX_TRUSTED_MCP_SERVERS` 추가 → 볼륨 영속.
- [ ] **④ Teams env**: `~/.hermes-torajima/.env`에 `TEAMS_*` 5종(기존 시크릿 macmini `users/torajima.env`에서 복사) + `config.yaml` `platforms.teams.enabled: true`.
- [ ] **⑤ Funnel**: `tailscale funnel --bg --https=8443 http://127.0.0.1:3978`
- [ ] **⑥ 봇 endpoint 변경**: Microsoft 측 봇 messaging endpoint를 `https://macbookpro.tail809feb.ts.net:8443/api/messages`로 변경
- (참고) `OPENAI_API_KEY` 수동 주입 **없음** — provider는 OAuth(codex app_server).

## 8. qa 검증 체크리스트 (pass/fail 기준 — qa 리뷰 반영)

각 항목은 "동작함" 수준이 아니라 **명시적 판정 기준 + 증거**를 남긴다.

- [ ] **8-1 health (로컬·공개 분리 판정)**: HTTP **200 + body 정확값/JSON 필드** + timeout 명시. 로컬 `127.0.0.1:3978/health`, 공개 `macbookpro.tail809feb.ts.net:8443/health` 각각 개별 판정.
- [ ] **8-2 공개면 노출 점검(보안)**: 공개 `/api/messages`에 **무인증/잘못된 토큰** 요청 시 **401/403** 반환 확인 → Funnel이 webhook 외 관리면/기타 경로를 노출하지 않음을 검증.
- [ ] **8-3 Teams 왕복**: **고유 nonce 포함 DM 1건** → 응답 **내용·지연·중복응답 없음**까지 기록. **허용되지 않은 사용자 거부**(`TEAMS_ALLOWED_USERS` 밖)도 별도 확인.
- [ ] **8-4 모델 실제 응답(codex app_server, 핵심)**: 고정 프롬프트의 "의미 있는 답변"만으론 불충분 → **gateway/agent 로그에서 codex app_server 호출 성공 증거 + OAuth 세션 유효 + fallback 미사용** 확인. **도구 없이 1회 + 간단 tool-call 후 최종응답 1회** 각각 권장.
- [ ] **8-5 재기동 영속성**: compose **down/up 후 health→Teams→모델까지 재검증**. **config/state·memory MCP 볼륨 유지**, **OAuth 세션 재기동 후 유지**, **secret/토큰 비노출**(`docker logs`/`inspect`) 확인.
- [ ] ~~**8-6 메모리 판정**~~ → **이번 라운드 제외** (메모리 미도입). 대신 **데모 시나리오 검증**: 메일 초안 작성 / SharePoint 검색·갱신 / 3분 주기 자동실행 / 멀티스텝 연쇄가 Teams에서 동작하는지. (메모리는 후속 라운드에서 memory MCP 도입 시 재추가.)
- [ ] **8-7 장애 진단(음성 테스트)**: **OAuth 미승인/만료 또는 memory MCP 미기동** 상태에서 health·Teams 수신은 살아있되 **사용자에게 실패가 명확히 반환** + **토큰/secret이 로그에 없음** 1건 확인.

> **qa E2E 착수 조건**: ①컨테이너 up ②codex OAuth 승인 ③memory MCP 부착 ④Teams endpoint 변경 완료 후 dev "구현 완료" 신호. 그때 위 8-1~8-7 기준으로 실행.

## 9. 이식(macmini) 시 되돌릴 점

- Microsoft 봇 endpoint를 `digimanmac-mini...:8443`으로 원복.
- 이 PC Funnel 해제: `tailscale funnel --https=8443 off`.
- macmini는 멀티유저 구조이므로, 검증 완료된 config/mcp_servers/Teams 설정을 macmini의 `users/torajima.env` + `~/.hermes-torajima/config.yaml`에 반영. **컨테이너+설정 통째 이식**이 가장 깔끔.
- **codex OAuth 재승인 필요**: 1차 검증은 하연 개인계정 → 이식/데모 전 **스미나가 씨 계정으로 재승인**(token cost 주체 교체). memory MCP 볼륨도 함께 이전.

## 10. 미해결 / 블로커 (2026-07-16 갱신 — codex app_server 확정 반영)

**남은 블로커:**
1. **codex OAuth 승인** — 컨테이너 up 후 사용자가 `hermes setup`→Codex→URL 로그인 (1차: 하연 개인계정). ← 최우선
2. **기존 Teams CLIENT_SECRET 값 확보** — macmini `users/torajima.env`에서 복사 (§6-3).

**후속/컨펌 대기:**
- **메모리(memory MCP)** — 이번 라운드 제외, **스미나가 씨 컨펌 후** 도입 여부 결정 (§5).

**해소/변경된 항목:**
- ~~OpenAI API 키 발급·충전~~ → **불필요**. codex app_server는 OAuth(계정 구독)로 token cost 부담 → 키/크레딧 없음.
- ~~내장 memory 플래그로 전부 ON~~ → app_server에선 **구조적 불가**(§5). 이번 라운드 메모리 제외.
- ~~CLIENT_SECRET 재발급~~ → 기존 값 재사용, 재발급은 고객 인계 직전에만.
- ~~Honcho~~ → 제외 확정.
- ~~Docker 데몬~~ → 기동 완료 ✅.
- ~~M365 인증(MSGRAPH/로그인)~~ → **완료** ✅. softeria device-code OAuth 성공, 토큰 `/opt/data/ms365` 영속, Graph 실호출 통과. (막판 블로커였던 `530035`는 2026-07-01부터 신규 테넌트 Security Defaults가 device-code 차단 → 보안 기본값 Disabled로 해소. **데모 후 재활성화 필요**.)

---

## 11. 데모 시나리오 설계 (dev 인계용)

> 목표: Teams에서 hermes를 **M365 업무 에이전트**로 시연. 스미나가 씨 요구 4종(메일 초안 / SharePoint 업데이트 / 3분 자동실행 / 멀티스텝 연쇄) 충족. **매 실행이 반드시 무언가를 생성·갱신·통지**하도록 설계해 데모 중 "안 움직임"을 방지.

### 11-0. ⚠️ 선행: 데이터 준비 (현재 테넌트 비어있음)
dev 검증에서 **SharePoint 사이트 0개**. 데모 전 DigiManAI에 샘플 데이터 필요:
- SharePoint 사이트 1개 + 문서 라이브러리/리스트에 샘플 항목 몇 개 (예: 営業案件/提案書 리스트, 샘플 문서)
- `admin@DigiManAI` 메일함에 샘플 메일 몇 통
- (사용자가 진행 중 — "デモ用ファイルを入れている中")

### 11-1. 실제 M365 툴 이름 (dev 확인, softeria 106개 중)
| 용도 | 툴 이름 |
|------|--------|
| SharePoint 사이트 검색 | `search-sharepoint-sites` |
| 파일 검색 | `search-onedrive-files` |
| 메일 목록/검색 | `list-mail-messages` |
| 메일 본문 | `get-mail-message` |
| 사용자 조회 | `get-current-user` |
| 메일 초안 생성 (쓰기) | (create-draft/create-mail류 — dev가 106개 중 확정) |
| SharePoint/리스트 갱신 (쓰기) | (update-list-item/upload류 — dev가 확정) |

### 11-2. Part A — 대화형 (Teams DM, 발표자가 봇에 입력)
데모 대사 흐름:
1. "SharePointのサイト一覧を見せて" → `search-sharepoint-sites`
2. "〇〇について資料を検索して" → `search-onedrive-files`
3. "最近の受信メールを3件教えて" → `list-mail-messages`
4. **★멀티스텝 목玉**: "SharePointの〇〇の情報をもとに、△△さん宛のフォローアップメール下書きを作成して" → 검색 → 본문 취득 → **메일 초안 생성**
5. "実行内容をSharePointの活動ログに記録して" → **SharePoint 리스트/파일 갱신**

### 11-3. Part B — 자동 스케줄 (cron, 3분마다)
hermes 내장 스케줄러 job **`m365-demo-pulse`** — 3분 간격(데모용; 본번 30분). **매 실행 고정 5단계** (항상 출력 생성):
1. SharePoint 대상 리스트/라이브러리 최신 항목 조회
2. 메일함 신착 확인
3. 위 정보 요약 → **팔로우업 메일 초안 1건 생성**
4. SharePoint 활동 로그에 **타임스탬프 실행 기록 추가** (← 매 실행 "변화" 보장)
5. Teams **home 채널에 요약 통지** (확인/생성/갱신 내용)

### 11-4. dev 구현 노트
- cron = hermes 내장 스케줄러에 위 프롬프트를 job 등록. 멀티스텝 신뢰성 부족하면 hermes **skill**로 고정.
- **`TEAMS_HOME_CHANNEL`** 설정 필요 (cron 통지 대상 채널 ID — plugin.yaml optional_env).
- 메일은 **초안만, 발송 X** (Mail.Send 스코프 미부여 — 의도적).
- 대상 SharePoint 사이트/리스트·메일함을 프롬프트에 고정하려면 실제 ID/이름 필요.

### 11-5. qa 검증 (M3)
- cron 3분마다 fire → Teams home 게시 + 메일 초안 생성 + SharePoint 로그 갱신, 3연속 확인.
- Part A 대화형 실시간 동작(각 툴 호출 성공).
- 증거: Teams 메시지, 메일함 초안, SharePoint 로그 타임스탬프.

### 11-6. 열린 입력 (사용자/dev 확정 필요)
1. `TEAMS_HOME_CHANNEL` — 어느 Teams 채널에 통지할지
2. 대상 **SharePoint 사이트/리스트** 이름·ID
3. **샘플 데이터** 투입 완료 여부 (SharePoint 항목 + 메일)
4. 메일 초안 수신인(데모용 더미 주소)
