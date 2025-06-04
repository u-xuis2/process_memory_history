#!/bin/bash

umask 077

CURRENT_PATH=`pwd`
EXE_PATH=`dirname "${0}"`
EXE_NAME=`basename "${0}"`

set -uo pipefail

cd "${EXE_PATH}/.."

# プロセスメモリ履歴取得デーモン状態確認スクリプト

PIDFILE="./logs/process_memory_history.pid"
LOGFILE="./logs/process_memory_history.log"

echo "=== プロセスメモリ履歴取得デーモン 状態確認 ==="

# PIDファイルの確認
if [ ! -f "$PIDFILE" ]; then
    echo "状態: 停止中"
    echo "理由: PIDファイルが見つかりません ($PIDFILE)"
    exit 0
fi

# PIDの読み込み
PID=$(cat "$PIDFILE")
echo "PIDファイル: $PIDFILE"
echo "PID: $PID"

# プロセスの存在確認
if ! kill -0 "$PID" 2>/dev/null; then
    echo "状態: 停止中（異常）"
    echo "理由: PIDに対応するプロセスが見つかりません"
    echo "対処: PIDファイルを削除してください: rm -f $PIDFILE"
    exit 1
fi

# プロセス情報の表示
echo "状態: 実行中"
echo ""

# プロセス詳細情報
echo "--- プロセス詳細 ---"
ps -p "$PID" -o pid,ppid,user,time,etime,pcpu,pmem,cmd

echo ""

# メモリ使用量
echo "--- メモリ使用量 ---"
ps -p "$PID" -o pid,rss,vsz,pmem --no-headers | while read pid rss vsz pmem; do
    rss_mb=$((rss / 1024))
    vsz_mb=$((vsz / 1024))
    echo "RSS: ${rss_mb}MB (${rss}KB)"
    echo "VSZ: ${vsz_mb}MB (${vsz}KB)"
    echo "Memory%: ${pmem}%"
done

echo ""

# ファイル出力状況
echo "--- 出力ファイル状況 ---"
OUTPUT_DIR="./output"
if [ -d "$OUTPUT_DIR" ]; then
    FILE_COUNT=$(find "$OUTPUT_DIR" -name "memory_*.json" | wc -l)
    echo "出力ディレクトリ: $OUTPUT_DIR"
    echo "JSONファイル数: $FILE_COUNT"
    
    if [ $FILE_COUNT -gt 0 ]; then
        LATEST_FILE=$(find "$OUTPUT_DIR" -name "memory_*.json" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
        LATEST_TIME=$(stat -c %y "$LATEST_FILE" | cut -d'.' -f1)
        LATEST_SIZE=$(stat -c %s "$LATEST_FILE")
        LATEST_SIZE_KB=$((LATEST_SIZE / 1024))
        
        echo "最新ファイル: $(basename "$LATEST_FILE")"
        echo "更新時刻: $LATEST_TIME"
        echo "ファイルサイズ: ${LATEST_SIZE_KB}KB"
    fi
    
    # ディスク使用量
    TOTAL_SIZE=$(du -s "$OUTPUT_DIR" | cut -f1)
    TOTAL_SIZE_MB=$((TOTAL_SIZE / 1024))
    echo "ディレクトリサイズ: ${TOTAL_SIZE_MB}MB"
else
    echo "出力ディレクトリが見つかりません: $OUTPUT_DIR"
fi

echo ""

# ログファイル状況
echo "--- ログファイル状況 ---"
if [ -f "$LOGFILE" ]; then
    LOG_SIZE=$(stat -c %s "$LOGFILE")
    LOG_SIZE_KB=$((LOG_SIZE / 1024))
    LOG_LINES=$(wc -l < "$LOGFILE")
    
    echo "ログファイル: $LOGFILE"
    echo "ファイルサイズ: ${LOG_SIZE_KB}KB"
    echo "行数: $LOG_LINES"
    
    echo ""
    echo "--- 最新ログ（末尾10行） ---"
    tail -10 "$LOGFILE"
else
    echo "ログファイルが見つかりません: $LOGFILE"
fi

echo ""

# 設定ファイル確認
echo "--- 設定確認 ---"
if [ -f "settings.json" ]; then
    SETTINGS_PERM=$(stat -c %a settings.json)
    echo "設定ファイル: settings.json (権限: $SETTINGS_PERM)"
    
    # 設定の主要項目を表示
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "
import json
try:
    with open('settings.json', 'r') as f:
        config = json.load(f)
    print(f'収集間隔: {config.get(\"collection\", {}).get(\"interval_seconds\", \"N/A\")}秒')
    print(f'上位件数: {config.get(\"collection\", {}).get(\"top_count\", \"N/A\")}件')
    print(f'出力ディレクトリ: {config.get(\"output\", {}).get(\"directory\", \"N/A\")}')
    print(f'保持ファイル数: {config.get(\"output\", {}).get(\"file_retention_count\", \"N/A\")}件')
except Exception as e:
    print(f'設定ファイル読み込みエラー: {e}')
" 2>/dev/null || echo "設定ファイルの解析に失敗しました"
    fi
else
    echo "設定ファイルが見つかりません: settings.json"
fi

echo ""
echo "状態確認完了"