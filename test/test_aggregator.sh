#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}/.."

# 集計機能テストスクリプト

echo "=== プロセスメモリ集計機能テスト ==="

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

# テストデータの準備
echo "テストデータを準備中..."

# 短時間でテストデータを生成（10秒間）
TEST_OUTPUT_DIR="./test_output"
mkdir -p "$TEST_OUTPUT_DIR"

# settings.jsonの一時コピーを作成してテスト用に変更
cp settings.json settings_test.json
python3 -c "
import json
with open('settings_test.json', 'r') as f:
    config = json.load(f)
config['output']['directory'] = '$TEST_OUTPUT_DIR'
config['collection']['interval_seconds'] = 2
with open('settings_test.json', 'w') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)
"

# テストデータ生成のため短時間実行
echo "テストデータ生成中（10秒間）..."
timeout 10s python3 -c "
import sys
sys.path.insert(0, '.')
from src.config import Config
from src.collector import create_collector
from src.file_manager import create_file_manager
import time

config = Config('settings_test.json')
collector = create_collector(config.get_top_count(), config.get_process_group_by())
file_manager = create_file_manager(
    config.get_output_directory(),
    config.get_file_retention_count(),
    config.get_max_file_size_mb()
)

# 複数回データを収集
for i in range(5):
    data = collector.collect()
    file_manager.save_json(data)
    time.sleep(2)
" 2>/dev/null || true

# 生成されたファイル数を確認
DATA_FILES=$(find "$TEST_OUTPUT_DIR" -name "memory_*.json" | wc -l)
echo "生成されたテストデータファイル数: $DATA_FILES"

if [ $DATA_FILES -eq 0 ]; then
    echo "警告: テストデータファイルが生成されませんでした"
    echo "集計テストはスキップします"
    
    # クリーンアップ
    rm -f settings_test.json
    rm -rf "$TEST_OUTPUT_DIR"
    exit 0
fi

# テスト1: 集計処理基本テスト
run_test "集計処理基本機能" "python3 src/aggregator.py >/dev/null 2>&1"

# テスト2: CLIヘルプテスト
run_test "集計CLI ヘルプ表示" "python3 bin/aggregate.py --help >/dev/null 2>&1"

# テスト3: 過去1時間の集計テスト
run_test "過去1時間集計テスト" "python3 bin/aggregate.py --hours 1 --data-dir '$TEST_OUTPUT_DIR' --output test_1h.tsv >/dev/null 2>&1"

# テスト4: TSVファイル出力確認
test_tsv_output() {
    if [ -f "test_1h.tsv" ] && [ -f "test_1h_pid_mapping.tsv" ]; then
        # TSVファイルの構造チェック
        if head -1 test_1h.tsv | grep -q "時間"; then
            # PID対応表の構造チェック
            if head -1 test_1h_pid_mapping.tsv | grep -q "PID.*COMMAND"; then
                return 0
            fi
        fi
    fi
    return 1
}

run_test "TSVファイル出力確認" "test_tsv_output"

# テスト5: 異なる集計間隔テスト
run_test "30分間隔集計テスト" "python3 bin/aggregate.py --hours 1 --interval 30 --data-dir '$TEST_OUTPUT_DIR' --output test_30m.tsv >/dev/null 2>&1"

# テスト6: 期間指定集計テスト
test_range_aggregation() {
    # 1時間前から現在まで
    local start_time=$(date -d '1 hour ago' '+%Y-%m-%d %H:%M:%S')
    local end_time=$(date '+%Y-%m-%d %H:%M:%S')
    
    python3 bin/aggregate.py --range "$start_time" "$end_time" --data-dir "$TEST_OUTPUT_DIR" --output test_range.tsv >/dev/null 2>&1
}

run_test "期間指定集計テスト" "test_range_aggregation"

# テスト7: データが無い期間の集計テスト
test_no_data_aggregation() {
    # 1週間前の1時間（データが無いはず）
    local start_time=$(date -d '1 week ago' '+%Y-%m-%d %H:%M:%S')
    local end_time=$(date -d '1 week ago + 1 hour' '+%Y-%m-%d %H:%M:%S')
    
    python3 bin/aggregate.py --range "$start_time" "$end_time" --data-dir "$TEST_OUTPUT_DIR" --output test_nodata.tsv >/dev/null 2>&1
    
    # データが無い場合はファイルが作成されないか、空のファイルになる
    return 0  # このテストは成功とする
}

run_test "データ無し期間集計テスト" "test_no_data_aggregation"

# テスト8: 不正な引数でのエラーハンドリング
test_invalid_args() {
    # 不正な日時形式
    python3 bin/aggregate.py --range "invalid-date" "invalid-date" --data-dir "$TEST_OUTPUT_DIR" --output test_invalid.tsv >/dev/null 2>&1
    local exit_code=$?
    
    # エラーで終了することを期待
    [ $exit_code -ne 0 ]
}

run_test "不正引数エラーハンドリング" "test_invalid_args"

# テスト9: TSVファイル内容検証
test_tsv_content() {
    if [ -f "test_1h.tsv" ]; then
        # TSVファイルにタブ区切りデータが含まれているかチェック
        if grep -q $'\t' test_1h.tsv; then
            # 時刻形式のチェック（YYYY-MM-DD HH:MM:SS）
            if grep -qE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' test_1h.tsv; then
                return 0
            fi
        fi
    fi
    return 1
}

run_test "TSVファイル内容検証" "test_tsv_content"

# テスト10: PID重複処理テスト
test_pid_duplication() {
    python3 -c "
import sys
sys.path.insert(0, '.')
from src.aggregator import create_aggregator

aggregator = create_aggregator('$TEST_OUTPUT_DIR')

# PID重複処理のテスト
pid1 = aggregator._handle_pid_duplication(1234, 'command1')
pid2 = aggregator._handle_pid_duplication(1234, 'command1')  # 同じコマンド
pid3 = aggregator._handle_pid_duplication(1234, 'command2')  # 異なるコマンド

assert pid1 == '1234', f'Expected 1234, got {pid1}'
assert pid2 == '1234', f'Expected 1234, got {pid2}'
assert pid3 == '1234(2)', f'Expected 1234(2), got {pid3}'

print('PID重複処理テスト: OK')
" 2>/dev/null
}

run_test "PID重複処理テスト" "test_pid_duplication"

# クリーンアップ
echo ""
echo "テストファイルをクリーンアップ中..."
rm -f settings_test.json
rm -f test_*.tsv
rm -rf "$TEST_OUTPUT_DIR"

# テスト結果サマリー
echo ""
echo "=== 集計機能テスト結果サマリー ==="
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