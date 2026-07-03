# Torajima Microsoft Teams 連携デプロイ Runbook

作成日: 2026-07-03 / 対象: Mac Mini (DigiMannoMac-mini) の hermes-torajima インスタンス

---

## 1. 目的
顧客企業 **Torajima** に hermes ボットを **Microsoft Teams** で引き渡す前に、
**Digiman 側で先に動作検証**するための構成。顧客は Teams を実利用中だが、
検証用に Digiman 自身のテナントが必要だったため、新規 M365 テナントを開設して検証した。

## 2. 環境 / 前提
- **Mac Mini** (`DigiMannoMac-mini`, Tailscale tailnet `tail809feb.ts.net`) で
  ユーザー別マルチ hermes を運用 (hkang / adachi / ebine / torajima)。
- 運用ツール: `/Users/digiman/dev/hermes-agent/hermes-user.sh <user> up|down`
  + `docker-compose.multiuser.yml` + `users/<user>.env`。
- リポジトリは `main` (この Dockerfile には `--extra teams` が無い)。
  → **teams を含むイメージは別途ビルド済みの `hermes-agent-teams:latest` のみ**。
- 外部公開は **Tailscale Funnel**。ダッシュボードは tailnet 限定 (9119〜9122)。
  Caddy は `auto_https off` (TLS 終端は tailscale が担当)。

## 3. 参照したファイル / コード
- `website/docs/user-guide/messaging/teams.md` … 設定手順・config 構造・env 一覧
- `plugins/platforms/teams/plugin.yaml` … 必要な env (TEAMS_CLIENT_ID/SECRET/TENANT_ID 等)
- `plugins/platforms/teams/adapter.py` … 認証情報は **env 優先、config.extra フォールバック**
  (`os.getenv(...) or extra.get(...)`) → env で渡す方針に決定
- `docker-compose.multiuser.yml` / `hermes-user.sh` … gateway 共用・`--build` 方式を把握

## 4. 実施手順
1. **M365 テナント開設**: Business Standard 1ヶ月無料試用 → `DigiManAI.onmicrosoft.com`
   (管理者 = グローバル管理者)。Teams の **カスタムアプリのアップロード(サイドロード)を ON**。
2. **Teams CLI** インストール (`@microsoft/teams.cli@preview` 3.0.0) + ログイン
   (SSH では Keychain のロック解除後にトークンが保持される)。
3. **ボット登録**:
   `teams app create -n "Hermes-Torajima" -e https://digimanmac-mini.tail809feb.ts.net:8443/api/messages`
   → CLIENT_ID / CLIENT_SECRET / TENANT_ID を取得。
4. **override compose 作成**: `docker-compose.torajima.yml`
   (teams イメージ + ポート 3978 + TEAMS_* env)。
5. **hermes-user.sh パッチ**: `docker-compose.<user>.yml` があれば自動で `-f` 追加、
   override がある場合は `--build` を省略 (teams イメージの上書き防止)。
6. **認証情報の注入**: `users/torajima.env` に TEAMS_* 5個を追加。
7. **config.yaml**: `~/.hermes-torajima/config.yaml` に `platforms.teams.enabled: true`
   (重複ブロックの整理を含む)。
8. **Funnel**: `tailscale funnel --bg --https=8443 http://127.0.0.1:3978`
   (443 は既に localhost:8765 で使用中。8443/10000 が空いていた)。
9. **起動 & 検証**: teams イメージで再起動 → `curl .../8443/health` = `ok`
   → Teams でボットをインストールし DM → **ボット応答を確認**。

## 5. 生成 / 変更されたもの (Mac Mini)
| ファイル | 変更 | バックアップ |
|---|---|---|
| `dev/hermes-agent/docker-compose.torajima.yml` | 新規 (torajima 専用 override) | — |
| `dev/hermes-agent/hermes-user.sh` | override 自動認識 + build 制御 | `hermes-user.sh.bak-teams2` |
| `dev/hermes-agent/users/torajima.env` | TEAMS_* 5個を追加 | `users/torajima.env.bak-teams` |
| `~/.hermes-torajima/config.yaml` | `platforms.teams.enabled: true` | `config.yaml.bak-teams` |
| Tailscale funnel | 8443 → localhost:3978 を追加 (`--bg`, 永続) | — |
| Docker | `hermes-torajima` が `hermes-agent-teams:latest` + ポート 3978 で再生成 | — |

## 6. 主要な識別子
- テナント: `DigiManAI.onmicrosoft.com` / Tenant ID `d1bb8c2f-c460-4a3b-a05e-627c6118b5e9`
- Bot/App ID (=CLIENT_ID): `a99cd792-710e-47e4-9223-bb6af9319d91`
- 管理者/テスターの Object ID (TEAMS_ALLOWED_USERS): `55206f0e-76ae-4cfd-98ee-710d017ffb2d`
- webhook endpoint: `https://digimanmac-mini.tail809feb.ts.net:8443/api/messages`
- インストールリンク:
  `https://teams.microsoft.com/l/app/a99cd792-710e-47e4-9223-bb6af9319d91?installAppPackage=true&appTenantId=d1bb8c2f-c460-4a3b-a05e-627c6118b5e9`

## 7. 検証結果
- OK: ローカル `curl 127.0.0.1:3978/health` = `ok`
- OK: 公開 `curl .../8443/health` = `ok` (インターネット→Funnel→コンテナ全区間)
- OK: Teams でボットに DM → ボットが応答 (往復配管が完全動作)
- OK: `hermes-user.sh torajima up` でも teams イメージ+ポートを維持 (再起動の永続性)

## 8. 残課題 / 注意
- 【重要】**モデル provider が fleet 全体で未動作** (Teams とは無関係):
  全インスタンスが `providers:{}` + キー無し + OAuth トークン無し、
  OpenRouter/Nous アカウントが **クレジット/決済エラー**。
  ボットが実際に回答するには → クレジット補充 + `~/.hermes-torajima/.env` に
  `OPENROUTER_API_KEY` を設定 **または** `docker exec -it hermes-torajima hermes auth`。
- 【セキュリティ】**CLIENT_SECRET のローテーション推奨** (チャットに露出済み)。本番前に再発行。
- 実際の顧客展開時は **顧客テナント**にボットを別途登録 (またはマルチテナント化) が必要。
  現在のボットは `DigiManAI` テナント専用。

## 9. 運用 / ロールバック
- 再起動: `cd ~/dev/hermes-agent && ./hermes-user.sh torajima up` (down も同様)。
- Funnel 停止: `tailscale funnel --https=8443 off`。
- ロールバック: 各 `*.bak-*` ファイルで復元後に `hermes-user.sh torajima up`。

## 10. 補足 (SSH ターミナルの注意)
SSH 経由のターミナルは長い貼り付け行を `\n  ` で崩すことがある。
短い単一行のコマンド、または base64 を `fold` で分割して
`base64 --decode < file` (macOS の base64 は positional 引数不可、`-i`/stdin を使う) で復元する。
