#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}"

echo "環境を準備しています..."

# 必要なディレクトリが存在するかチェック
directories=("src" "bin" "supervisor" "test" "logs" "output")
for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "ディレクトリを作成: $dir"
        mkdir -p "$dir"
    fi
done

# 設定ファイルのコピー
if [ ! -f "settings.json" ]; then
    if [ -f "settings.json.template" ]; then
        echo "設定ファイルをコピー: settings.json"
        cp settings.json.template settings.json
        chmod 600 settings.json
    else
        echo "エラー: settings.json.templateが見つかりません"
        exit 101
    fi
fi

# 権限設定
chmod 755 bin/*.sh 2>/dev/null || true
chmod 755 supervisor/*.sh 2>/dev/null || true
chmod 755 test/*.sh 2>/dev/null || true

echo "環境準備完了"
echo "設定ファイル: $(pwd)/settings.json"
echo "出力ディレクトリ: $(pwd)/output"