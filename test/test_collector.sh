#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}/.."

# コレクター機能テストスクリプト

echo "=== プロセスメモリ収集機能テスト ==="

# テスト結果カウンター
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# テスト関数
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo ""
    echo "テスト $TOTAL_TESTS: $test_name"
    echo "コマンド: $test_command"
    
    if eval "$test_command"; then
        echo "結果: PASS"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "結果: FAIL"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# 前提条件チェック
echo "前提条件をチェック中..."

if [ ! -f "settings.json" ]; then
    echo "エラー: settings.jsonが見つかりません"
    echo "ready.shを実行してください"
    exit 118
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "エラー: python3が見つかりません"
    exit 119
fi

echo "前提条件: OK"

# テスト1: 設定ファイル読み込みテスト
run_test "設定ファイル読み込み" "python3 src/config.py >/dev/null 2>&1"

# テスト2: セキュリティバリデーションテスト
run_test "セキュリティバリデーション" "python3 src/validator.py >/dev/null 2>&1"

# テスト3: メモリ情報収集テスト
run_test "メモリ情報収集" "python3 src/collector.py >/dev/null 2>&1"

# テスト4: ファイル管理テスト
run_test "ファイル管理機能" "python3 src/file_manager.py >/dev/null 2>&1"

# テスト5: 短時間実行テスト（5秒間）
run_test "短時間実行テスト" "timeout 5s python3 src/main.py >/dev/null 2>&1; [ \$? -eq 124 ]"

# テスト6: JSONファイル出力確認
test_json_output() {
    local latest_file=$(ls -t ./output/memory_*.json 2>/dev/null | head -1)
    if [ -n "$latest_file" ] && [ -f "$latest_file" ]; then
        if python3 -c "
import json
with open('$latest_file', 'r') as f:
    data = json.load(f)
    assert 'timestamp' in data
    assert 'hostname' in data
    assert 'items' in data
    assert isinstance(data['items'], list)
    print('JSONファイル構造: OK')
" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

run_test "JSONファイル出力確認" "test_json_output"

# テスト7: コマンドライン引数テスト
run_test "集計CLI基本テスト" "python3 bin/aggregate.py --help >/dev/null 2>&1"

# テスト8: 管理スクリプト構文チェック
run_test "管理スクリプト構文チェック" "bash -n bin/start.sh && bash -n bin/stop.sh && bash -n bin/status.sh"

# テスト9: supervisor設定生成テスト
run_test "supervisor設定生成" "bash supervisor/setup_supervisor.sh >/dev/null 2>&1"

# テスト10: セキュリティテスト（不正パス）
test_security() {
    python3 -c "
import sys
sys.path.insert(0, '.')
from src.validator import create_validator

validator = create_validator(['./output'])

# 不正パステスト
test_cases = [
    ('../../../etc', False),
    ('/etc/passwd', False),
    ('./output', True),
]

for path, expected in test_cases:
    result = validator.validate_output_directory(path)
    assert result == expected, f'Security test failed for {path}: {result} != {expected}'

print('セキュリティテスト: OK')
" 2>/dev/null
}

run_test "セキュリティテスト" "test_security"

# テスト結果サマリー
echo ""
echo "=== テスト結果サマリー ==="
echo "総テスト数: $TOTAL_TESTS"
echo "成功: $PASSED_TESTS"
echo "失敗: $FAILED_TESTS"

if [ $FAILED_TESTS -eq 0 ]; then
    echo "結果: 全テスト成功"
    exit 0
else
    echo "結果: $FAILED_TESTS 件のテストが失敗しました"
    exit 1
fi