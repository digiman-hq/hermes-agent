#!/bin/sh
# Demo cron: every 3 min, exercise the client's 3 asks (SharePoint update +
# mail draft + scheduling) as one workflow and report to the Teams home channel.
# Runs on the torajima gateway (codex_app_server) using softeria ms365 tools.
export HOME=/opt/data
hermes cron create \
  --schedule "every 3m" \
  --name "m365-demo" \
  --deliver teams \
  --prompt "次を順に実行し、結果を1つのメッセージで日本語で簡潔に報告してください。ツールはms365を使用。1) DigiMan SharePointサイトのドキュメントライブラリに demo-status.txt を『現在時刻: <時刻>』という内容で作成/上書き更新する。2) その内容を要約したメールの下書きを admin@DigiManAI.onmicrosoft.com 宛に作成する（送信はしない）。3) 実行結果（ファイルのURL・下書き作成の成否・時刻）を報告する。"
