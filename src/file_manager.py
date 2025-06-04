#!/usr/bin/env python3
"""
ファイル管理モジュール
JSONファイルの原子性を保証した出力、古いファイルの削除、ディスク容量監視を行う
"""

import json
import os
import sys
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


class FileManager:
    """ファイル管理クラス"""
    
    def __init__(self, output_directory: str, file_retention_count: int, max_file_size_mb: float):
        self.output_directory = output_directory
        self.file_retention_count = file_retention_count
        self.max_file_size_mb = max_file_size_mb
        self._ensure_output_directory()
    
    def save_json(self, data: Dict[str, Any]) -> str:
        """
        JSONデータを原子性を保証してファイルに保存
        """
        try:
            # ファイル名の生成 (タイムスタンプベース)
            timestamp = datetime.now()
            filename = f"memory_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(self.output_directory, filename)
            
            # 原子性を保証するため、一時ファイルに書き込み後にrename
            temp_filepath = filepath + ".tmp"
            
            # JSONデータの書き込み
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()  # バッファを強制的にフラッシュ
                os.fsync(f.fileno())  # OSレベルでの書き込み保証
            
            # 原子的にファイル名を変更
            os.rename(temp_filepath, filepath)
            
            # ファイルサイズチェック
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                print(f"警告: ファイルサイズが制限を超えています: {filepath} ({file_size_mb:.2f}MB)", 
                      file=sys.stderr, flush=True)
            
            print(f"ファイル保存完了: {filepath} ({file_size_mb:.2f}MB)", 
                  file=sys.stderr, flush=True)
            
            return filepath
            
        except Exception as e:
            # 一時ファイルのクリーンアップ
            try:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            except:
                pass
            
            print(f"エラー: JSONファイル保存中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            raise
    
    def cleanup_old_files(self) -> int:
        """
        古いファイルを削除して指定件数に制限
        """
        try:
            # JSONファイル一覧を取得
            json_files = self._get_json_files()
            
            if len(json_files) <= self.file_retention_count:
                return 0  # 削除の必要なし
            
            # 削除対象ファイルの決定
            files_to_delete = json_files[self.file_retention_count:]
            deleted_count = 0
            
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"古いファイルを削除: {file_path}", file=sys.stderr, flush=True)
                except OSError as e:
                    print(f"警告: ファイル削除に失敗しました: {file_path} - {repr(e)}", 
                          file=sys.stderr, flush=True)
            
            print(f"ファイルクリーンアップ完了: {deleted_count}件削除", file=sys.stderr, flush=True)
            return deleted_count
            
        except Exception as e:
            print(f"エラー: ファイルクリーンアップ中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return 0
    
    def check_disk_space(self, min_free_gb: float = 1.0) -> bool:
        """
        ディスク容量をチェック
        """
        try:
            # ディスク使用量の取得
            total, used, free = shutil.disk_usage(self.output_directory)
            
            free_gb = free / (1024 ** 3)
            total_gb = total / (1024 ** 3)
            used_gb = used / (1024 ** 3)
            usage_percent = (used / total) * 100
            
            print(f"ディスク使用量: {used_gb:.1f}GB / {total_gb:.1f}GB ({usage_percent:.1f}%) " +
                  f"空き容量: {free_gb:.1f}GB", file=sys.stderr, flush=True)
            
            if free_gb < min_free_gb:
                print(f"警告: ディスク容量不足です。空き容量: {free_gb:.1f}GB (最小要求: {min_free_gb}GB)", 
                      file=sys.stderr, flush=True)
                return False
            
            return True
            
        except Exception as e:
            print(f"エラー: ディスク容量チェック中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return False
    
    def get_file_count(self) -> int:
        """JSONファイル数を取得"""
        try:
            return len(self._get_json_files())
        except Exception:
            return 0
    
    def get_directory_size_mb(self) -> float:
        """出力ディレクトリのサイズを取得（MB単位）"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.output_directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.isfile(filepath):
                        total_size += os.path.getsize(filepath)
            return total_size / (1024 * 1024)
        except Exception as e:
            print(f"警告: ディレクトリサイズ計算中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            return 0.0
    
    def emergency_cleanup(self) -> int:
        """
        緊急時のクリーンアップ（ディスク容量不足時）
        通常のretention_countより多くのファイルを削除
        """
        try:
            print("緊急時クリーンアップを開始します", file=sys.stderr, flush=True)
            
            # 通常の半分の件数まで削除
            emergency_retention = max(1, self.file_retention_count // 2)
            original_retention = self.file_retention_count
            
            self.file_retention_count = emergency_retention
            deleted_count = self.cleanup_old_files()
            self.file_retention_count = original_retention
            
            print(f"緊急時クリーンアップ完了: {deleted_count}件削除", file=sys.stderr, flush=True)
            return deleted_count
            
        except Exception as e:
            print(f"エラー: 緊急時クリーンアップ中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return 0
    
    def _ensure_output_directory(self):
        """出力ディレクトリの存在を確認し、必要に応じて作成"""
        try:
            if not os.path.exists(self.output_directory):
                os.makedirs(self.output_directory, mode=0o755, exist_ok=True)
                print(f"出力ディレクトリを作成しました: {self.output_directory}", 
                      file=sys.stderr, flush=True)
        except Exception as e:
            print(f"エラー: 出力ディレクトリの作成に失敗しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            raise
    
    def _get_json_files(self) -> List[str]:
        """出力ディレクトリ内のJSONファイル一覧を作成日時順で取得"""
        try:
            files = []
            
            for filename in os.listdir(self.output_directory):
                if filename.endswith('.json') and not filename.endswith('.tmp'):
                    filepath = os.path.join(self.output_directory, filename)
                    if os.path.isfile(filepath):
                        files.append(filepath)
            
            # ファイルの作成日時でソート（新しい順）
            files.sort(key=lambda x: os.path.getctime(x), reverse=True)
            return files
            
        except Exception as e:
            print(f"警告: JSONファイル一覧取得中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            return []


def create_file_manager(output_directory: str, file_retention_count: int, max_file_size_mb: float) -> FileManager:
    """ファイルマネージャーを作成"""
    return FileManager(output_directory, file_retention_count, max_file_size_mb)


if __name__ == "__main__":
    # テスト実行
    fm = create_file_manager("./test_output", 5, 10.0)
    
    print("=== ファイル管理テスト ===", file=sys.stderr, flush=True)
    
    try:
        # テストデータの保存
        test_data = {
            "timestamp": datetime.now().isoformat(),
            "hostname": "test-host",
            "items": [
                {"pid": 1234, "cmd": "test-process", "rss": 102400, "group": "test"},
                {"pid": 5678, "cmd": "another-process", "rss": 51200, "group": "test2"}
            ],
            "total_mb": 150.0,
            "total_gb": 0.147,
            "total_tb": 0.0001
        }
        
        # ファイル保存テスト
        filepath = fm.save_json(test_data)
        print(f"テストファイル保存成功: {filepath}", file=sys.stderr, flush=True)
        
        # ディスク容量チェック
        disk_ok = fm.check_disk_space()
        print(f"ディスク容量チェック: {'OK' if disk_ok else 'NG'}", file=sys.stderr, flush=True)
        
        # ファイル数チェック
        file_count = fm.get_file_count()
        print(f"現在のファイル数: {file_count}", file=sys.stderr, flush=True)
        
        # ディレクトリサイズチェック
        dir_size = fm.get_directory_size_mb()
        print(f"ディレクトリサイズ: {dir_size:.2f}MB", file=sys.stderr, flush=True)
        
        # クリーンアップテスト（実際には実行しない）
        print("クリーンアップテストはスキップします", file=sys.stderr, flush=True)
        
    except Exception as e:
        print(f"テスト失敗: {repr(e)}", file=sys.stderr, flush=True)
        sys.exit(1)