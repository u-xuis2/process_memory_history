#!/usr/bin/env python3
"""
メモリ情報収集モジュール
psコマンドでプロセス情報を取得し、構造化して返す
"""

import subprocess
import sys
import traceback
import socket
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


class ProcessInfo:
    """プロセス情報クラス"""
    
    def __init__(self, pid: int, cmd: str, rss: int, group: str):
        self.pid = pid
        self.cmd = cmd
        self.rss = rss  # KB単位
        self.group = group


class MemoryCollector:
    """メモリ情報収集クラス"""
    
    def __init__(self, top_count: int = 40, process_group_by: str = "command"):
        self.top_count = top_count
        self.process_group_by = process_group_by
        self.hostname = self._get_hostname()
    
    def collect(self) -> Dict[str, Any]:
        """
        メモリ情報を収集して構造化データを返す
        """
        try:
            # psコマンドでプロセス情報を取得
            raw_processes = self._get_process_list()
            
            # プロセス情報の構造化
            processes = self._parse_process_list(raw_processes)
            
            # プロセスグループ化とソート
            grouped_processes = self._group_and_sort_processes(processes)
            
            # 上位件数に絞り込み
            top_processes = grouped_processes[:self.top_count]
            
            # 合計メモリ使用量の計算
            total_kb = sum(proc.rss for proc in top_processes)
            total_mb = total_kb / 1024
            total_gb = total_mb / 1024
            total_tb = total_gb / 1024
            
            # 構造化データの生成
            result = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hostname": self.hostname,
                "items": [
                    {
                        "pid": proc.pid,
                        "cmd": proc.cmd,
                        "rss": proc.rss,
                        "group": proc.group
                    }
                    for proc in top_processes
                ],
                "total_mb": round(total_mb, 1),
                "total_gb": round(total_gb, 3),
                "total_tb": round(total_tb, 6)
            }
            
            return result
            
        except Exception as e:
            print(f"エラー: メモリ情報収集中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            raise
    
    def _get_process_list(self) -> str:
        """psコマンドでプロセス一覧を取得"""
        try:
            # ps aux --sort=-rss でメモリ使用量順にソート
            cmd = ["ps", "aux", "--sort=-rss"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
            
        except subprocess.CalledProcessError as e:
            print(f"エラー: psコマンドの実行に失敗しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            print(f"stderr: {e.stderr}", file=sys.stderr, flush=True)
            raise
        except FileNotFoundError:
            print("エラー: psコマンドが見つかりません", file=sys.stderr, flush=True)
            raise
    
    def _parse_process_list(self, ps_output: str) -> List[ProcessInfo]:
        """psコマンドの出力をパースしてProcessInfoのリストを返す"""
        processes = []
        lines = ps_output.strip().split('\n')
        
        # ヘッダー行をスキップ
        if len(lines) < 2:
            print("警告: psコマンドの出力が空です", file=sys.stderr, flush=True)
            return processes
        
        for line in lines[1:]:  # ヘッダー行をスキップ
            try:
                process_info = self._parse_process_line(line)
                if process_info:
                    processes.append(process_info)
            except Exception as e:
                print(f"警告: プロセス行のパース中にエラーが発生しました: {repr(e)}", 
                      file=sys.stderr, flush=True)
                print(f"行: {line}", file=sys.stderr, flush=True)
                continue
        
        return processes
    
    def _parse_process_line(self, line: str) -> Optional[ProcessInfo]:
        """プロセス行をパースしてProcessInfoを返す"""
        # ps auxの出力形式:
        # USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
        parts = line.split(None, 10)  # 最大11個に分割（COMMANDにスペースが含まれる可能性があるため）
        
        if len(parts) < 11:
            return None
        
        try:
            pid = int(parts[1])
            rss = int(parts[5])  # RSS (KB)
            command = parts[10].strip()
            
            # プロセスグループの決定
            group = self._determine_group(pid, command)
            
            # コマンドを簡素化（パス削除、引数削除）
            simplified_cmd = self._simplify_command(command)
            
            return ProcessInfo(pid, simplified_cmd, rss, group)
            
        except (ValueError, IndexError) as e:
            print(f"警告: プロセス情報のパース中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            return None
    
    def _determine_group(self, pid: int, command: str) -> str:
        """プロセスグループを決定"""
        if self.process_group_by == "pid":
            return str(pid)
        else:  # command
            # コマンド名の最初の部分をグループ名とする
            cmd_parts = command.split()
            if cmd_parts:
                cmd_name = cmd_parts[0]
                # パスからファイル名のみ抽出
                if '/' in cmd_name:
                    cmd_name = cmd_name.split('/')[-1]
                return cmd_name
            return "unknown"
    
    def _simplify_command(self, command: str) -> str:
        """コマンドを簡素化"""
        # 長すぎるコマンドは切り詰める
        max_length = 100
        if len(command) > max_length:
            command = command[:max_length] + "..."
        
        return command
    
    def _group_and_sort_processes(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """プロセスをグループ化してソート"""
        if self.process_group_by == "command":
            # コマンド別にグループ化し、各グループで最大メモリ使用量のプロセスを選択
            groups = {}
            for proc in processes:
                if proc.group not in groups or proc.rss > groups[proc.group].rss:
                    groups[proc.group] = proc
            
            # メモリ使用量でソート
            grouped_processes = sorted(groups.values(), key=lambda x: x.rss, reverse=True)
        else:
            # PIDの場合はそのままソート
            grouped_processes = sorted(processes, key=lambda x: x.rss, reverse=True)
        
        return grouped_processes
    
    def _get_hostname(self) -> str:
        """ホスト名を取得"""
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"


def create_collector(top_count: int = 40, process_group_by: str = "command") -> MemoryCollector:
    """メモリコレクターを作成"""
    return MemoryCollector(top_count, process_group_by)


if __name__ == "__main__":
    # テスト実行
    collector = create_collector()
    
    print("=== メモリ情報収集テスト ===", file=sys.stderr, flush=True)
    
    try:
        result = collector.collect()
        print(f"収集件数: {len(result['items'])}件", file=sys.stderr, flush=True)
        print(f"総メモリ使用量: {result['total_mb']}MB ({result['total_gb']}GB)", 
              file=sys.stderr, flush=True)
        print(f"ホスト名: {result['hostname']}", file=sys.stderr, flush=True)
        print(f"タイムスタンプ: {result['timestamp']}", file=sys.stderr, flush=True)
        
        # 上位5件の表示
        print("上位5件:", file=sys.stderr, flush=True)
        for i, item in enumerate(result['items'][:5]):
            print(f"  {i+1}. PID:{item['pid']} RSS:{item['rss']}KB GROUP:{item['group']}", 
                  file=sys.stderr, flush=True)
            print(f"     CMD:{item['cmd']}", file=sys.stderr, flush=True)
        
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"テスト失敗: {repr(e)}", file=sys.stderr, flush=True)
        sys.exit(1)