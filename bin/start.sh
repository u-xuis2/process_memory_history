#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}/.."

# プロセスメモリ履歴取得デーモン開始スクリプト

PIDFILE="./logs/process_memory_history.pid"
LOGFILE="./logs/process_memory_history.log"

# ログディレクトリの作成
mkdir -p logs

# 既存プロセスのチェック
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "エラー: プロセスは既に実行中です (PID: $PID)" >&2
        exit 112
    else
        echo "警告: PIDファイルが残っていますが、プロセスは存在しません。削除します。" >&2
        rm -f "$PIDFILE"
    fi
fi

# 設定ファイルの確認
if [ ! -f "settings.json" ]; then
    echo "エラー: 設定ファイルが見つかりません: settings.json" >&2
    echo "ready.shを実行して環境を準備してください。" >&2
    exit 113
fi

# 設定ファイルの権限チェック
SETTINGS_PERM=$(stat -c %a settings.json)
if [ "$SETTINGS_PERM" != "600" ]; then
    echo "警告: 設定ファイルの権限が推奨値(600)ではありません: $SETTINGS_PERM" >&2
    echo "推奨: chmod 600 settings.json" >&2
fi

# Pythonの存在確認
if ! command -v python3 >/dev/null 2>&1; then
    echo "エラー: python3が見つかりません" >&2
    exit 114
fi

# メインプロセスの開始
echo "プロセスメモリ履歴取得デーモンを開始します..."
echo "ログファイル: $LOGFILE"
echo "PIDファイル: $PIDFILE"

# バックグラウンドでプロセス開始
nohup python3 src/main.py >> "$LOGFILE" 2>&1 &
DAEMON_PID=$!

# PIDファイルの作成
echo "$DAEMON_PID" > "$PIDFILE"

# プロセス開始の確認
sleep 2
if kill -0 "$DAEMON_PID" 2>/dev/null; then
    echo "プロセスメモリ履歴取得デーモンが開始されました (PID: $DAEMON_PID)"
    echo "ログの確認: tail -f $LOGFILE"
    echo "停止コマンド: bash bin/stop.sh"
else
    echo "エラー: デーモンの開始に失敗しました" >&2
    rm -f "$PIDFILE"
    echo "ログを確認してください: cat $LOGFILE" >&2
    exit 115
fi