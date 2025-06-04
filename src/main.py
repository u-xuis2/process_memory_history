#!/usr/bin/env python3
"""
メイン常駐プロセス
プロセスメモリ履歴取得ツールのメインモジュール
"""

import signal
import sys
import time
import traceback
import threading
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.validator import create_validator
from src.collector import create_collector
from src.file_manager import create_file_manager


class ProcessMemoryHistoryDaemon:
    """プロセスメモリ履歴取得デーモンクラス"""
    
    def __init__(self):
        self.running = True
        self.config = None
        self.validator = None
        self.collector = None
        self.file_manager = None
        self.cleanup_thread = None
        self.last_cleanup_time = 0
        
        # シグナルハンドラーの設定
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def initialize(self):
        """初期化処理"""
        try:
            print("プロセスメモリ履歴取得デーモンを初期化中...", file=sys.stderr, flush=True)
            
            # 設定の読み込み
            self.config = load_config()
            print("設定ファイル読み込み完了", file=sys.stderr, flush=True)
            
            # セキュリティバリデーターの初期化
            self.validator = create_validator(self.config.get_allowed_output_paths())
            
            # セキュリティチェック
            if not self._perform_security_checks():
                print("セキュリティチェックに失敗しました", file=sys.stderr, flush=True)
                sys.exit(104)
            
            # コンポーネントの初期化
            self.collector = create_collector(
                self.config.get_top_count(),
                self.config.get_process_group_by()
            )
            
            self.file_manager = create_file_manager(
                self.config.get_output_directory(),
                self.config.get_file_retention_count(),
                self.config.get_max_file_size_mb()
            )
            
            print("初期化完了", file=sys.stderr, flush=True)
            
        except Exception as e:
            print(f"エラー: 初期化中にエラーが発生しました: {repr(e)}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            sys.exit(105)
    
    def run(self):
        """メインループの実行"""
        try:
            print("プロセスメモリ履歴取得デーモン開始", file=sys.stderr, flush=True)
            print(f"収集間隔: {self.config.get_collection_interval()}秒", file=sys.stderr, flush=True)
            print(f"上位件数: {self.config.get_top_count()}件", file=sys.stderr, flush=True)
            print(f"出力ディレクトリ: {self.config.get_output_directory()}", file=sys.stderr, flush=True)
            
            # クリーンアップスレッドの開始
            self._start_cleanup_thread()
            
            # メインループ
            while self.running:
                try:
                    loop_start_time = time.time()
                    
                    # メモリ情報の収集
                    memory_data = self.collector.collect()
                    
                    # ディスク容量チェック
                    if not self.file_manager.check_disk_space():
                        print("ディスク容量不足のため緊急クリーンアップを実行", file=sys.stderr, flush=True)
                        self.file_manager.emergency_cleanup()
                    
                    # JSONファイルの保存
                    saved_file = self.file_manager.save_json(memory_data)
                    
                    if self.config.is_debug_enabled():
                        print(f"データ収集完了: {len(memory_data['items'])}件, " +
                              f"総メモリ: {memory_data['total_mb']}MB, " +
                              f"ファイル: {saved_file}", file=sys.stderr, flush=True)
                    
                    # インターバル計算（処理時間を考慮）
                    processing_time = time.time() - loop_start_time
                    sleep_time = max(0, self.config.get_collection_interval() - processing_time)
                    
                    # 1秒間隔で中断フラグをチェックしながら待機
                    elapsed_sleep = 0
                    while elapsed_sleep < sleep_time and self.running:
                        time.sleep(min(1, sleep_time - elapsed_sleep))
                        elapsed_sleep += 1
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"エラー: メインループ中にエラーが発生しました: {repr(e)}", 
                          file=sys.stderr, flush=True)
                    if self.config.is_debug_enabled():
                        traceback.print_exc(file=sys.stderr)
                    
                    # エラー発生時は少し待ってから再試行（1秒間隔で中断チェック）
                    error_sleep_time = min(10, self.config.get_collection_interval())
                    elapsed_sleep = 0
                    while elapsed_sleep < error_sleep_time and self.running:
                        time.sleep(1)
                        elapsed_sleep += 1
            
        except Exception as e:
            print(f"エラー: メインループで致命的なエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            sys.exit(106)
    
    def stop(self):
        """デーモンの停止"""
        if self.running:
            print("プロセスメモリ履歴取得デーモンを停止中...", file=sys.stderr, flush=True)
            self.running = False

            # クリーンアップスレッドの停止
            if self.cleanup_thread and self.cleanup_thread.is_alive():
                self.cleanup_thread.join(timeout=2)
            
            print("プロセスメモリ履歴取得デーモン停止完了", file=sys.stderr, flush=True)
    
    def _signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        signal_names = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT"}
        signal_name = signal_names.get(signum, f"Signal {signum}")
        print(f"{signal_name}を受信しました。デーモンを停止します。", file=sys.stderr, flush=True)
        self.stop()
    
    def _perform_security_checks(self) -> bool:
        """セキュリティチェックの実行"""
        try:
            print("セキュリティチェックを実行中...", file=sys.stderr, flush=True)
            
            # 実行権限チェック
            if not self.validator.validate_execution_permissions():
                return False
            
            # 出力ディレクトリチェック
            if not self.validator.validate_output_directory(self.config.get_output_directory()):
                return False
            
            # 設定ファイル権限チェック（警告のみ）
            self.validator.validate_config_file_permissions("settings.json")
            
            print("セキュリティチェック完了", file=sys.stderr, flush=True)
            return True
            
        except Exception as e:
            print(f"エラー: セキュリティチェック中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return False
    
    def _start_cleanup_thread(self):
        """クリーンアップスレッドの開始"""
        def cleanup_worker():
            counter = 0
            while self.running:
                try:
                    counter += 1
                    
                    # 60回に1回（60秒に1回）クリーンアップ間隔をチェック
                    if counter >= 60:
                        counter = 0
                        current_time = time.time()
                        
                        # クリーンアップ間隔チェック
                        if current_time - self.last_cleanup_time >= self.config.get_cleanup_interval():
                            print("定期クリーンアップを実行中...", file=sys.stderr, flush=True)
                            
                            deleted_count = self.file_manager.cleanup_old_files()
                            self.last_cleanup_time = current_time
                            
                            # 統計情報の出力
                            file_count = self.file_manager.get_file_count()
                            dir_size = self.file_manager.get_directory_size_mb()
                            print(f"クリーンアップ完了: {deleted_count}件削除, " +
                                  f"残りファイル: {file_count}件, " +
                                  f"ディレクトリサイズ: {dir_size:.2f}MB", file=sys.stderr, flush=True)
                    
                    # 1秒間隔でチェック
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"警告: クリーンアップスレッドでエラーが発生しました: {repr(e)}", 
                          file=sys.stderr, flush=True)
                    if self.config.is_debug_enabled():
                        traceback.print_exc(file=sys.stderr)
                    time.sleep(1)
        
        self.cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        print("クリーンアップスレッド開始", file=sys.stderr, flush=True)


def main():
    """メイン関数"""
    daemon = ProcessMemoryHistoryDaemon()
    
    try:
        daemon.initialize()
        daemon.run()
    except KeyboardInterrupt:
        pass
    except SystemExit:
        pass
    except Exception as e:
        print(f"致命的エラー: {repr(e)}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(107)
    finally:
        daemon.stop()


if __name__ == "__main__":
    main()