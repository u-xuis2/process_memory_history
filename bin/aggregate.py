#!/usr/bin/env python3
"""
集計CLI
プロセスメモリ履歴データを集計してTSVファイルを生成するコマンドラインツール
"""

import argparse
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.aggregator import create_aggregator


def parse_arguments():
    """コマンドライン引数の解析"""
    parser = argparse.ArgumentParser(
        description="プロセスメモリ履歴データを集計してTSVファイルを生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 過去24時間のデータを15分足で集計
  python3 bin/aggregate.py --hours 24 --output memory_24h.tsv
  
  # 過去1週間のデータを1時間足で集計
  python3 bin/aggregate.py --days 7 --interval 60 --output memory_1week.tsv
  
  # 特定期間のデータを集計
  python3 bin/aggregate.py --start "2025-06-01 00:00:00" --end "2025-06-02 00:00:00" --output memory_specific.tsv
  
  # データディレクトリを指定
  python3 bin/aggregate.py --hours 12 --data-dir /path/to/data --output memory_12h.tsv
        """
    )
    
    # 時間指定オプション（相互排他）
    time_group = parser.add_mutually_exclusive_group(required=True)
    time_group.add_argument(
        "--hours",
        type=int,
        help="過去N時間のデータを集計（例: --hours 24）"
    )
    time_group.add_argument(
        "--days",
        type=int,
        help="過去N日のデータを集計（例: --days 7）"
    )
    time_group.add_argument(
        "--range",
        nargs=2,
        metavar=("START", "END"),
        help="期間を指定してデータを集計（例: --range \"2025-06-01 00:00:00\" \"2025-06-02 00:00:00\"）"
    )
    
    # その他のオプション
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="集計間隔（分）（デフォルト: 15分）"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="出力TSVファイル名"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./output",
        help="データディレクトリ（デフォルト: ./output）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細な進捗情報を表示"
    )
    
    return parser.parse_args()


def calculate_time_range(args) -> tuple:
    """引数から時間範囲を計算"""
    now = datetime.now()
    
    if args.hours is not None:
        start_time = now - timedelta(hours=args.hours)
        end_time = now
    elif args.days is not None:
        start_time = now - timedelta(days=args.days)
        end_time = now
    elif args.range is not None:
        try:
            start_time = datetime.strptime(args.range[0], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(args.range[1], "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            print(f"エラー: 日時の形式が正しくありません: {repr(e)}", 
                  file=sys.stderr, flush=True)
            print("形式: YYYY-MM-DD HH:MM:SS", file=sys.stderr, flush=True)
            sys.exit(108)
    else:
        # ここには到達しないはず（argparseでチェック済み）
        print("エラー: 時間範囲が指定されていません", file=sys.stderr, flush=True)
        sys.exit(109)
    
    if start_time >= end_time:
        print("エラー: 開始時刻が終了時刻以降に設定されています", file=sys.stderr, flush=True)
        sys.exit(110)
    
    return start_time, end_time


def main():
    """メイン関数"""
    try:
        # 引数の解析
        args = parse_arguments()
        
        if args.verbose:
            print("=== プロセスメモリ履歴集計CLI ===", file=sys.stderr, flush=True)
            print(f"データディレクトリ: {args.data_dir}", file=sys.stderr, flush=True)
            print(f"集計間隔: {args.interval}分", file=sys.stderr, flush=True)
            print(f"出力ファイル: {args.output}", file=sys.stderr, flush=True)
        
        # 時間範囲の計算
        start_time, end_time = calculate_time_range(args)
        
        if args.verbose:
            print(f"集計期間: {start_time} ～ {end_time}", file=sys.stderr, flush=True)
            duration = end_time - start_time
            print(f"集計期間長: {duration}", file=sys.stderr, flush=True)
        
        # 集計処理クラスの初期化
        aggregator = create_aggregator(args.data_dir)
        
        # ローソク足データの生成
        if args.verbose:
            print("ローソク足データの生成を開始...", file=sys.stderr, flush=True)
        
        candle_data = aggregator.aggregate_to_candles(
            start_time, end_time, args.interval
        )
        
        if not candle_data:
            print("警告: 指定期間内にデータが見つかりませんでした", file=sys.stderr, flush=True)
            print("データディレクトリとファイル名を確認してください", file=sys.stderr, flush=True)
            sys.exit(0)
        
        # TSVファイルの出力
        if args.verbose:
            print("TSVファイルの出力を開始...", file=sys.stderr, flush=True)
        
        tsv_file, mapping_file = aggregator.export_to_tsv(candle_data, args.output)
        
        # 完了メッセージ
        print(f"集計完了", file=sys.stderr, flush=True)
        print(f"TSVファイル: {tsv_file}", file=sys.stderr, flush=True)
        print(f"PID対応表: {mapping_file}", file=sys.stderr, flush=True)
        
        # 統計情報の表示
        total_pids = len(candle_data)
        total_time_points = len(set(
            candle.timestamp 
            for pid_candles in candle_data.values() 
            for candle in pid_candles
        ))
        
        print(f"PID数: {total_pids}件", file=sys.stderr, flush=True)
        print(f"時間ポイント数: {total_time_points}件", file=sys.stderr, flush=True)
        
        # 上位メモリ使用プロセスの表示（最新時点）
        if args.verbose and candle_data:
            print("上位メモリ使用プロセス（最新時点）:", file=sys.stderr, flush=True)
            latest_values = []
            
            for pid, pid_candles in candle_data.items():
                if pid_candles:
                    latest_candle = max(pid_candles, key=lambda x: x.timestamp)
                    latest_values.append((pid, latest_candle.close_value))
            
            latest_values.sort(key=lambda x: x[1], reverse=True)
            
            for i, (pid, rss) in enumerate(latest_values[:10]):
                cmd = aggregator.pid_cmd_mapping.get(
                    aggregator._extract_original_pid(pid), "unknown"
                )
                print(f"  {i+1}. PID:{pid} RSS:{rss}KB CMD:{cmd[:50]}...", 
                      file=sys.stderr, flush=True)
        
    except KeyboardInterrupt:
        print("中断されました", file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"エラー: 集計処理中にエラーが発生しました: {repr(e)}", 
              file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(111)


if __name__ == "__main__":
    main()