#!/usr/bin/env python3
"""
セキュリティバリデーションモジュール
出力ディレクトリの安全性チェックやファイル権限チェックを行う
"""

import os
import sys
import stat
import traceback
from pathlib import Path
from typing import List


class SecurityValidator:
    """セキュリティバリデーションクラス"""
    
    # システムディレクトリ（書き込み禁止）
    SYSTEM_DIRECTORIES = {
        "/etc", "/usr", "/var", "/bin", "/sbin", "/boot", "/dev", "/proc", "/sys",
        "/lib", "/lib64", "/run", "/root"
    }
    
    def __init__(self, allowed_output_paths: List[str]):
        """
        許可された出力パスで初期化
        """
        self.allowed_output_paths = [os.path.abspath(path) for path in allowed_output_paths]
    
    def validate_output_directory(self, directory: str) -> bool:
        """
        出力ディレクトリの安全性をチェック
        """
        try:
            abs_dir = os.path.abspath(directory)
            
            # ディレクトリトラバーサル攻撃の検出
            if self._has_directory_traversal(directory):
                print(f"セキュリティエラー: ディレクトリトラバーサルが検出されました: {directory}", 
                      file=sys.stderr, flush=True)
                return False
            
            # システムディレクトリへの書き込み禁止
            if self._is_system_directory(abs_dir):
                print(f"セキュリティエラー: システムディレクトリへの書き込みは禁止されています: {abs_dir}", 
                      file=sys.stderr, flush=True)
                return False
            
            # 許可された出力パスかチェック
            if not self._is_allowed_output_path(abs_dir):
                print(f"セキュリティエラー: 許可されていない出力パスです: {abs_dir}", 
                      file=sys.stderr, flush=True)
                print(f"許可されたパス: {self.allowed_output_paths}", file=sys.stderr, flush=True)
                return False
            
            # ディレクトリの作成権限チェック
            if not self._check_directory_writable(abs_dir):
                print(f"セキュリティエラー: ディレクトリに書き込み権限がありません: {abs_dir}", 
                      file=sys.stderr, flush=True)
                return False
            
            return True
            
        except Exception as e:
            print(f"セキュリティエラー: ディレクトリバリデーション中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return False
    
    def validate_config_file_permissions(self, config_path: str) -> bool:
        """
        設定ファイルの権限をチェック
        """
        try:
            if not os.path.exists(config_path):
                print(f"警告: 設定ファイルが存在しません: {config_path}", file=sys.stderr, flush=True)
                return False
            
            file_stat = os.stat(config_path)
            file_mode = stat.filemode(file_stat.st_mode)
            octal_mode = oct(file_stat.st_mode)[-3:]
            
            # 推奨権限: 600 (所有者のみ読み書き可能)
            if octal_mode != "600":
                print(f"警告: 設定ファイルの権限が推奨値(600)ではありません: {config_path} ({file_mode}, {octal_mode})", 
                      file=sys.stderr, flush=True)
                print(f"推奨: chmod 600 {config_path}", file=sys.stderr, flush=True)
                return False
            
            return True
            
        except Exception as e:
            print(f"エラー: 設定ファイル権限チェック中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return False
    
    def validate_execution_permissions(self) -> bool:
        """
        実行権限の確認
        """
        try:
            # 一般ユーザー権限での実行を確認
            if os.getuid() == 0:
                print("警告: root権限で実行されています。セキュリティリスクがあります。", 
                      file=sys.stderr, flush=True)
                return False
            
            return True
            
        except Exception as e:
            print(f"エラー: 実行権限チェック中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return False
    
    def _has_directory_traversal(self, path: str) -> bool:
        """ディレクトリトラバーサル攻撃の検出"""
        # 危険なパターンをチェック
        dangerous_patterns = ["../", "..\\", "..", "%2e%2e", "%2f", "%5c"]
        normalized_path = path.lower()
        
        for pattern in dangerous_patterns:
            if pattern in normalized_path:
                return True
        
        return False
    
    def _is_system_directory(self, abs_path: str) -> bool:
        """システムディレクトリかチェック"""
        for sys_dir in self.SYSTEM_DIRECTORIES:
            if abs_path.startswith(sys_dir):
                return True
        return False
    
    def _is_allowed_output_path(self, abs_path: str) -> bool:
        """許可された出力パスかチェック"""
        for allowed_path in self.allowed_output_paths:
            # 許可されたパス内またはそのサブディレクトリかチェック
            if abs_path.startswith(allowed_path):
                return True
        return False
    
    def _check_directory_writable(self, directory: str) -> bool:
        """ディレクトリが書き込み可能かチェック"""
        try:
            # ディレクトリが存在しない場合は作成を試行
            if not os.path.exists(directory):
                os.makedirs(directory, mode=0o755, exist_ok=True)
            
            # 書き込み権限をテスト
            test_file = os.path.join(directory, ".write_test")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                return True
            except OSError:
                return False
                
        except Exception:
            return False
    
    def validate_file_size(self, file_path: str, max_size_mb: float) -> bool:
        """
        ファイルサイズが制限内かチェック
        """
        try:
            if not os.path.exists(file_path):
                return True  # ファイルが存在しない場合はOK
            
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            if file_size_mb > max_size_mb:
                print(f"エラー: ファイルサイズが制限を超えています: {file_path} ({file_size_mb:.2f}MB > {max_size_mb}MB)", 
                      file=sys.stderr, flush=True)
                return False
            
            return True
            
        except Exception as e:
            print(f"エラー: ファイルサイズチェック中にエラーが発生しました: {repr(e)}", 
                  file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return False


def create_validator(allowed_output_paths: List[str]) -> SecurityValidator:
    """セキュリティバリデーターを作成"""
    return SecurityValidator(allowed_output_paths)


if __name__ == "__main__":
    # テスト実行
    validator = create_validator(["./output", "/tmp/process_memory"])
    
    print("=== セキュリティバリデーションテスト ===", file=sys.stderr, flush=True)
    
    # 正常なパステスト
    test_cases = [
        ("./output", True),
        ("/tmp/process_memory", True),
        ("../../../etc", False),
        ("/etc/passwd", False),
        ("./output/../../../root", False),
    ]
    
    for test_path, expected in test_cases:
        result = validator.validate_output_directory(test_path)
        status = "OK" if result == expected else "NG"
        print(f"{status}: {test_path} -> {result} (期待値: {expected})", file=sys.stderr, flush=True)
    
    # 実行権限テスト
    exec_result = validator.validate_execution_permissions()
    print(f"実行権限チェック: {exec_result}", file=sys.stderr, flush=True)