#!/bin/sh
# Minimal scheduling-only verification: every 3 min report the current time to
# the Teams home channel. No M365, no writes — isolates "does cron fire + deliver".
export HOME=/opt/data
hermes cron create \
  --schedule "every 3m" \
  --name "sched-test" \
  --deliver teams \
  --prompt "スケジューリング動作確認です。現在時刻を日本語で1行だけ報告してください。"
