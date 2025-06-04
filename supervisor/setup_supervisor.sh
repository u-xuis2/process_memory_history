#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}/.."

PROJECT_NAME=process_memory_history
SCRIPT_DIR="${EXE_PATH}"
PROJECT_PATH=$(cd "$(dirname "$SCRIPT_DIR")" && pwd) 
USER=$(whoami)
PATH_ENV="$PATH"

echo "プロジェクトパス: $PROJECT_PATH"
echo "実行ユーザー: $USER"

# ログディレクトリの作成
mkdir -p "$PROJECT_PATH/logs"

# テンプレートファイルの確認
if [ ! -f "$SCRIPT_DIR/$PROJECT_NAME.conf.template" ]; then
    echo "エラー: テンプレートファイルが見つかりません: $SCRIPT_DIR/$PROJECT_NAME.conf.template" >&2
    exit 117
fi

# supervisor設定ファイルの生成
sed "s|__PROJECT_PATH__|$PROJECT_PATH|g; s|__USER__|$USER|g; s|__PATH__|$PATH_ENV|g" \
    "$SCRIPT_DIR/$PROJECT_NAME.conf.template" > "$SCRIPT_DIR/$PROJECT_NAME.conf"

echo "supervisor設定ファイルを生成しました: $SCRIPT_DIR/$PROJECT_NAME.conf"
echo ""

# 設定ファイルの内容を表示
echo "--- 生成された設定ファイルの内容 ---"
cat "$SCRIPT_DIR/$PROJECT_NAME.conf"
echo "--- 設定ファイル内容ここまで ---"
echo ""

echo "次の手順でsupervisorに登録してください:"
echo "1. sudo cp $SCRIPT_DIR/$PROJECT_NAME.conf /etc/supervisor/conf.d/"
echo "2. sudo supervisorctl reread"
echo "3. sudo supervisorctl update"
echo "4. sudo supervisorctl start $PROJECT_NAME"
echo ""
echo "supervisor管理コマンド:"
echo "  状態確認: sudo supervisorctl status $PROJECT_NAME"
echo "  開始: sudo supervisorctl start $PROJECT_NAME"
echo "  停止: sudo supervisorctl stop $PROJECT_NAME"
echo "  再起動: sudo supervisorctl restart $PROJECT_NAME"
echo "  ログ確認: sudo supervisorctl tail $PROJECT_NAME"