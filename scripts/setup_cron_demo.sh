#!/bin/sh
# Demo cron: every 3 min, check DigiMan SharePoint and report to the Teams home
# channel. Runs on the torajima gateway (codex_app_server) using ms365 tools.
export HOME=/opt/data
hermes cron create \
  --schedule "every 3m" \
  --name "m365-demo" \
  --deliver teams \
  --prompt "DigiMan SharePointサイトのドキュメントライブラリのファイル数と現在時刻を確認し、1行で日本語で報告してください。ツールはms365を使ってください。"
