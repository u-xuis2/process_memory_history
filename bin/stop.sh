#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}/.."

# プロセスメモリ履歴取得デーモン停止スクリプト

PIDFILE="./logs/process_memory_history.pid"

# PIDファイルの確認
if [ ! -f "$PIDFILE" ]; then
    echo "警告: PIDファイルが見つかりません: $PIDFILE" >&2
    echo "プロセスが実行されていない可能性があります" >&2
    exit 0
fi

# PIDの読み込み
PID=$(cat "$PIDFILE")

# プロセスの存在確認
if ! kill -0 "$PID" 2>/dev/null; then
    echo "警告: PIDに対応するプロセスが見つかりません (PID: $PID)" >&2
    rm -f "$PIDFILE"
    exit 0
fi

echo "プロセスメモリ履歴取得デーモンを停止します (PID: $PID)..."

# 正常終了シグナル送信 (SIGTERM)
kill -TERM "$PID" 2>/dev/null

# 終了待機（最大10秒）
WAIT_TIME=0
MAX_WAIT=10

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "プロセスメモリ履歴取得デーモンが正常に停止しました"
        rm -f "$PIDFILE"
        exit 0
    fi
    sleep 1
    WAIT_TIME=$((WAIT_TIME + 1))
done

echo "警告: プロセスが正常に停止しませんでした。強制終了を試行します..." >&2

# 強制終了シグナル送信 (SIGKILL)
kill -KILL "$PID" 2>/dev/null

# 強制終了後の確認
sleep 2
if ! kill -0 "$PID" 2>/dev/null; then
    echo "プロセスメモリ履歴取得デーモンが強制終了されました"
    rm -f "$PIDFILE"
    exit 0
else
    echo "エラー: プロセスの停止に失敗しました (PID: $PID)" >&2
    echo "手動でプロセスを確認してください: ps aux | grep $PID" >&2
    exit 116
fi