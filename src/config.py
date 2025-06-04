#!/usr/bin/env python3
"""
設定管理モジュール
settings.jsonの読み込みとバリデーションを行う
"""

import json
import os
import sys
import traceback
from typing import Dict, Any, List


class Config:
    """設定管理クラス"""
    
    def __init__(self, config_path: str = "settings.json"):
        """
        設定ファイルを読み込んで初期化
        """
        self.config_path = config_path
        self.config = {}
        self._load_config()
        self._validate_config()
    
    def _load_config(self):
        """設定ファイルを読み込む"""
        try:
            if not os.path.exists(self.config_path):
                print(f"エラー: 設定ファイルが見つかりません: {self.config_path}", file=sys.stderr, flush=True)
                sys.exit(100)
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
                
        except json.JSONDecodeError as e:
            print(f"エラー: 設定ファイルのJSON形式が不正です: {repr(e)}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            sys.exit(101)
        except Exception as e:
            print(f"エラー: 設定ファイル読み込み中にエラーが発生しました: {repr(e)}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            sys.exit(102)
    
    def _validate_config(self):
        """設定値のバリデーション"""
        try:
            # デフォルト値の設定
            defaults = {
                "collection": {
                    "interval_seconds": 60,
                    "top_count": 40,
                    "process_group_by": "command"
                },
                "output": {
                    "directory": "./output",
                    "file_retention_count": 1440,
                    "cleanup_interval_seconds": 3600
                },
                "security": {
                    "allowed_output_paths": ["./output", "/tmp/process_memory"],
                    "max_file_size_mb": 100
                },
                "logging": {
                    "level": "INFO",
                    "enable_debug": False
                }
            }
            
            # デフォルト値のマージ
            self._merge_defaults(defaults)
            
            # バリデーション実行
            self._validate_collection_settings()
            self._validate_output_settings()
            self._validate_security_settings()
            self._validate_logging_settings()
            
        except Exception as e:
            print(f"エラー: 設定値バリデーション中にエラーが発生しました: {repr(e)}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            sys.exit(103)
    
    def _merge_defaults(self, defaults: Dict[str, Any]):
        """デフォルト値をマージ"""
        for section, default_values in defaults.items():
            if section not in self.config:
                self.config[section] = {}
            
            for key, default_value in default_values.items():
                if key not in self.config[section]:
                    self.config[section][key] = default_value
    
    def _validate_collection_settings(self):
        """収集設定のバリデーション"""
        collection = self.config["collection"]
        
        # interval_secondsの範囲チェック
        interval = collection["interval_seconds"]
        if not isinstance(interval, int) or not (10 <= interval <= 300):
            raise ValueError(f"interval_secondsは10-300秒の範囲で設定してください: {interval}")
        
        # top_countの範囲チェック
        top_count = collection["top_count"]
        if not isinstance(top_count, int) or not (1 <= top_count <= 1000):
            raise ValueError(f"top_countは1-1000件の範囲で設定してください: {top_count}")
        
        # process_group_byの値チェック
        group_by = collection["process_group_by"]
        if group_by not in ["command", "pid"]:
            raise ValueError(f"process_group_byは'command'または'pid'を設定してください: {group_by}")
    
    def _validate_output_settings(self):
        """出力設定のバリデーション"""
        output = self.config["output"]
        
        # file_retention_countの範囲チェック
        retention = output["file_retention_count"]
        if not isinstance(retention, int) or retention < 1:
            raise ValueError(f"file_retention_countは1以上を設定してください: {retention}")
        
        # cleanup_interval_secondsの範囲チェック
        cleanup_interval = output["cleanup_interval_seconds"]
        if not isinstance(cleanup_interval, int) or cleanup_interval < 60:
            raise ValueError(f"cleanup_interval_secondsは60秒以上を設定してください: {cleanup_interval}")
    
    def _validate_security_settings(self):
        """セキュリティ設定のバリデーション"""
        security = self.config["security"]
        
        # allowed_output_pathsの型チェック
        allowed_paths = security["allowed_output_paths"]
        if not isinstance(allowed_paths, list) or len(allowed_paths) == 0:
            raise ValueError("allowed_output_pathsは空でない配列を設定してください")
        
        # max_file_size_mbの範囲チェック
        max_size = security["max_file_size_mb"]
        if not isinstance(max_size, (int, float)) or max_size <= 0:
            raise ValueError(f"max_file_size_mbは正の数値を設定してください: {max_size}")
    
    def _validate_logging_settings(self):
        """ログ設定のバリデーション"""
        logging = self.config["logging"]
        
        # levelの値チェック
        level = logging["level"]
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            raise ValueError(f"levelは{valid_levels}のいずれかを設定してください: {level}")
        
        # enable_debugの型チェック
        debug = logging["enable_debug"]
        if not isinstance(debug, bool):
            raise ValueError(f"enable_debugはbool値を設定してください: {debug}")
    
    def get(self, section: str, key: str = None) -> Any:
        """設定値を取得"""
        if key is None:
            return self.config.get(section, {})
        return self.config.get(section, {}).get(key)
    
    def get_collection_interval(self) -> int:
        """収集間隔を取得"""
        return self.config["collection"]["interval_seconds"]
    
    def get_top_count(self) -> int:
        """上位件数を取得"""
        return self.config["collection"]["top_count"]
    
    def get_process_group_by(self) -> str:
        """プロセスグループ化方式を取得"""
        return self.config["collection"]["process_group_by"]
    
    def get_output_directory(self) -> str:
        """出力ディレクトリを取得"""
        return self.config["output"]["directory"]
    
    def get_file_retention_count(self) -> int:
        """ファイル保持件数を取得"""
        return self.config["output"]["file_retention_count"]
    
    def get_cleanup_interval(self) -> int:
        """クリーンアップ間隔を取得"""
        return self.config["output"]["cleanup_interval_seconds"]
    
    def get_allowed_output_paths(self) -> List[str]:
        """許可された出力パスを取得"""
        return self.config["security"]["allowed_output_paths"]
    
    def get_max_file_size_mb(self) -> float:
        """最大ファイルサイズを取得"""
        return self.config["security"]["max_file_size_mb"]
    
    def get_log_level(self) -> str:
        """ログレベルを取得"""
        return self.config["logging"]["level"]
    
    def is_debug_enabled(self) -> bool:
        """デバッグモードが有効かを取得"""
        return self.config["logging"]["enable_debug"]


def load_config(config_path: str = "settings.json") -> Config:
    """設定を読み込んで返す"""
    return Config(config_path)


if __name__ == "__main__":
    # テスト実行
    try:
        config = load_config()
        print("設定読み込み成功", file=sys.stderr, flush=True)
        print(f"収集間隔: {config.get_collection_interval()}秒", file=sys.stderr, flush=True)
        print(f"上位件数: {config.get_top_count()}件", file=sys.stderr, flush=True)
        print(f"出力ディレクトリ: {config.get_output_directory()}", file=sys.stderr, flush=True)
    except SystemExit:
        pass