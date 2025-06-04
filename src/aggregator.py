#!/usr/bin/env python3
"""
集計処理モジュール
JSONファイルから15分足ローソク足を生成し、TSVファイルとして出力する
"""

import json
import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import glob


class ProcessDataPoint:
    """プロセスデータポイントクラス"""
    
    def __init__(self, timestamp: datetime, pid: int, cmd: str, rss: int):
        self.timestamp = timestamp
        self.pid = pid
        self.cmd = cmd
        self.rss = rss


class CandleData:
    """ローソク足データクラス"""
    
    def __init__(self, timestamp: datetime):
        self.timestamp = timestamp
        self.open_value = 0
        self.close_value = 0
        self.high_value = 0
        self.low_value = 0
        self.data_points = []
    
    def add_data_point(self, rss: int):
        """データポイントを追加"""
        self.data_points.append(rss)
        
        if len(self.data_points) == 1:
            # 最初のデータポイント
            self.open_value = rss
            self.close_value = rss
            self.high_value = rss
            self.low_value = rss
        else:
            # 2個目以降のデータポイント
            self.close_value = rss
            self.high_value = max(self.high_value, rss)
            self.low_value = min(self.low_value, rss)


class MemoryAggregator:
    """メモリ情報集計クラス"""
    
    def __init__(self, data_directory: str = "./output"):
        self.data_directory = data_directory
        self.pid_cmd_mapping = {}  # PID重複管理
        self.pid_counters = {}  # PID連番管理
    
    def aggregate_to_candles(self, start_time: datetime, end_time: datetime, 
                           interval_minutes: int = 15) -> Dict[str, List[CandleData]]:
        """
        指定期間のデータを15分足ローソク足に集計
        """
        try:
            print(f"集計期間: {start_time} ～ {end_time}", file=sys.stderr, flush=True)
            print(f"集計間隔: {interval_minutes}分", file=sys.stderr, flush=True)
            
            # JSONファイルの読み込み
            raw_data = self._load_json_files(start_time, end_time)
            print(f"読み込みファイル数: {len(raw_data)}件", file=sys.stderr, flush=True)
            
            # プロセスデータの抽出と正規化
            process_data = self._extract_process_data(raw_data)
            print(f"プロセスデータ件数: {len(process_data)}件", file=sys.stderr, flush=True)
            
            # 時間間隔でグループ化
            time_groups = self._group_by_time_interval(process_data, interval_minutes)
            print(f"時間グループ数: {len(time_groups)}件", file=sys.stderr, flush=True)
            
            # PID別にローソク足データを生成
            candle_data = self._generate_candles(time_groups)
            print(f"PID数: {len(candle_data)}件", file=sys.stderr, flush=True)
            
            return candle_data
            
        except Exception as e:
            print(f"エラー: ローソク足集計中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            raise
    
    def export_to_tsv(self, candle_data: Dict[str, List[CandleData]], 
                     output_file: str) -> Tuple[str, str]:
        """
        ローソク足データをTSVファイルとPID-CMD対応表として出力
        """
        try:
            print(f"TSVファイル出力開始: {output_file}", file=sys.stderr, flush=True)
            
            # PID一覧の取得
            pid_list = sorted(candle_data.keys(), key=lambda x: self._extract_original_pid(x))
            
            # 時間軸の取得
            all_timestamps = set()
            for pid_candles in candle_data.values():
                for candle in pid_candles:
                    all_timestamps.add(candle.timestamp)
            
            sorted_timestamps = sorted(all_timestamps)
            
            # TSVファイルの書き込み
            tsv_lines = []
            
            # ヘッダー行（ローソク足4値を展開）
            header = ["時間"]
            for pid in pid_list:
                header.extend([f"{pid}_始値", f"{pid}_高値", f"{pid}_安値", f"{pid}_終値"])
            tsv_lines.append("\t".join(header))
            
            # データ行
            for timestamp in sorted_timestamps:
                row = [timestamp.strftime("%Y-%m-%d %H:%M:%S")]
                
                for pid in pid_list:
                    open_val = high_val = low_val = close_val = ""
                    if pid in candle_data:
                        for candle in candle_data[pid]:
                            if candle.timestamp == timestamp:
                                # ローソク足4値を設定
                                open_val = str(candle.open_value)
                                high_val = str(candle.high_value)
                                low_val = str(candle.low_value)
                                close_val = str(candle.close_value)
                                break
                    
                    # 始値、高値、安値、終値の順で追加
                    row.extend([open_val, high_val, low_val, close_val])
                
                tsv_lines.append("\t".join(row))
            
            # 出力ファイル名の正規化（.tsv拡張子の確保）
            if not output_file.endswith('.tsv'):
                normalized_output_file = output_file + '.tsv'
            else:
                normalized_output_file = output_file
            
            # TSVファイル書き込み
            with open(normalized_output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(tsv_lines))
            
            # PID-CMD対応表の作成
            base_name = normalized_output_file.replace('.tsv', '')
            mapping_file = base_name + '_pid_mapping.tsv'
            mapping_lines = ["PID\tCOMMAND"]
            
            for pid in pid_list:
                cmd = self.pid_cmd_mapping.get(self._extract_original_pid(pid), "unknown")
                mapping_lines.append(f"{pid}\t{cmd}")
            
            with open(mapping_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(mapping_lines))
            
            print(f"TSVファイル出力完了: {normalized_output_file}", file=sys.stderr, flush=True)
            print(f"PID対応表出力完了: {mapping_file}", file=sys.stderr, flush=True)
            print(f"時間軸: {len(sorted_timestamps)}件, PID軸: {len(pid_list)}件", 
                  file=sys.stderr, flush=True)
            
            return normalized_output_file, mapping_file
            
        except Exception as e:
            print(f"エラー: TSV出力中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            raise
    
    def _load_json_files(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """指定期間のJSONファイルを読み込み"""
        json_files = []
        
        # JSONファイルのパターンマッチング
        pattern = os.path.join(self.data_directory, "memory_*.json")
        file_paths = glob.glob(pattern)
        
        for file_path in file_paths:
            try:
                # ファイル名から時刻を抽出
                filename = os.path.basename(file_path)
                if filename.startswith("memory_") and filename.endswith(".json"):
                    time_part = filename[7:22]  # memory_20250604_123456.json の時刻部分
                    file_time = datetime.strptime(time_part, "%Y%m%d_%H%M%S")
                    
                    # 期間内のファイルのみ処理
                    if start_time <= file_time <= end_time:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            json_files.append(data)
                
            except Exception as e:
                print(f"警告: JSONファイル読み込みエラー: {file_path} - {repr(e)}", 
                      file=sys.stderr, flush=True)
                continue
        
        return json_files
    
    def _extract_process_data(self, raw_data: List[Dict[str, Any]]) -> List[ProcessDataPoint]:
        """JSONデータからプロセスデータを抽出"""
        process_data = []
        
        for data in raw_data:
            try:
                timestamp_str = data.get("timestamp", "")
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                
                for item in data.get("items", []):
                    pid = item.get("pid")
                    cmd = item.get("cmd", "")
                    rss = item.get("rss", 0)
                    
                    if pid is not None:
                        # PID重複処理
                        normalized_pid = self._handle_pid_duplication(pid, cmd)
                        
                        process_data.append(ProcessDataPoint(timestamp, normalized_pid, cmd, rss))
                
            except Exception as e:
                print(f"警告: プロセスデータ抽出エラー: {repr(e)}", file=sys.stderr, flush=True)
                continue
        
        return process_data
    
    def _handle_pid_duplication(self, pid: int, cmd: str) -> str:
        """PID重複処理（同一PIDで異なるコマンドの場合、連番を付与）"""
        if pid not in self.pid_cmd_mapping:
            # 初回登録
            self.pid_cmd_mapping[pid] = cmd
            return str(pid)
        
        if self.pid_cmd_mapping[pid] == cmd:
            # 同じコマンドなので通常のPID
            return str(pid)
        else:
            # 異なるコマンドなので連番を付与
            if pid not in self.pid_counters:
                self.pid_counters[pid] = 2  # 最初は(2)から
            else:
                self.pid_counters[pid] += 1
            
            new_pid = f"{pid}({self.pid_counters[pid]})"
            self.pid_cmd_mapping[pid] = cmd  # 最新のコマンドで更新
            return new_pid
    
    def _group_by_time_interval(self, process_data: List[ProcessDataPoint], 
                              interval_minutes: int) -> Dict[Tuple[datetime, str], List[ProcessDataPoint]]:
        """時間間隔でプロセスデータをグループ化"""
        groups = {}
        
        for data_point in process_data:
            # 時間間隔の開始時刻を計算
            minute = (data_point.timestamp.minute // interval_minutes) * interval_minutes
            interval_start = data_point.timestamp.replace(minute=minute, second=0, microsecond=0)
            
            key = (interval_start, data_point.pid)
            if key not in groups:
                groups[key] = []
            groups[key].append(data_point)
        
        return groups
    
    def _generate_candles(self, time_groups: Dict[Tuple[datetime, str], List[ProcessDataPoint]]) -> Dict[str, List[CandleData]]:
        """時間グループからローソク足データを生成"""
        candle_data = {}
        
        for (timestamp, pid), data_points in time_groups.items():
            if pid not in candle_data:
                candle_data[pid] = []
            
            # ローソク足の作成
            candle = CandleData(timestamp)
            
            # 時系列順にソート
            sorted_points = sorted(data_points, key=lambda x: x.timestamp)
            
            for point in sorted_points:
                candle.add_data_point(point.rss)
            
            candle_data[pid].append(candle)
        
        # 各PIDのローソク足を時系列順にソート
        for pid in candle_data:
            candle_data[pid].sort(key=lambda x: x.timestamp)
        
        return candle_data
    
    def _extract_original_pid(self, pid_str: str) -> int:
        """PID文字列から元のPID番号を抽出"""
        if '(' in pid_str:
            return int(pid_str.split('(')[0])
        return int(pid_str)


def create_aggregator(data_directory: str = "./output") -> MemoryAggregator:
    """集計処理クラスを作成"""
    return MemoryAggregator(data_directory)


if __name__ == "__main__":
    # テスト実行
    aggregator = create_aggregator()
    
    print("=== 集計処理テスト ===", file=sys.stderr, flush=True)
    
    try:
        # 過去1時間のデータを集計
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        candle_data = aggregator.aggregate_to_candles(start_time, end_time, 15)
        
        if candle_data:
            output_file = "test_aggregate.tsv"
            tsv_file, mapping_file = aggregator.export_to_tsv(candle_data, output_file)
            print(f"テスト完了: {tsv_file}, {mapping_file}", file=sys.stderr, flush=True)
        else:
            print("テストデータが見つかりませんでした", file=sys.stderr, flush=True)
        
    except Exception as e:
        print(f"テスト失敗: {repr(e)}", file=sys.stderr, flush=True)
        sys.exit(1)