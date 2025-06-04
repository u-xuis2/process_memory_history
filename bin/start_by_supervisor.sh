#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}/.."

# プロセスメモリ履歴取得のsupervisor用の開始スクリプト

# ログディレクトリの作成
mkdir -p logs

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


# フォアグラウンドでプロセス開始
python3 src/main.py
