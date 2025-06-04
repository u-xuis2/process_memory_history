# プロセスメモリ履歴取得ツール

プロセスのメモリ使用量を定期的に収集し、履歴データとして保存・集計するツールです。

## 概要

- プロセスのメモリ使用量（RSS）を定期的に収集
- JSONファイルとして安全に保存
- 15分足ローソク足での集計機能
- TSVファイルでの出力
- セキュリティ機能とバリデーション
- supervisor対応

## 機能

### 基本機能
- プロセスメモリ情報の定期収集（psコマンド使用）
- JSONファイルでの安全な保存（原子性保証）
- 古いファイルの自動削除
- ディスク容量監視

### 集計機能
- 15分足ローソク足の生成
- PID重複時の処理（同一PIDで異なるコマンドに連番付与）
- TSVファイル出力
- PID-CMD対応表の生成

### セキュリティ機能
- 出力ディレクトリの制限
- ディレクトリトラバーサル攻撃の防止
- ファイル権限チェック
- 実行権限の確認

## ディレクトリ構成

```
process_memory_history/
├── src/                    # ソースコード
│   ├── main.py            # メイン常駐プロセス
│   ├── collector.py       # メモリ情報収集
│   ├── file_manager.py    # ファイル管理
│   ├── aggregator.py      # 集計処理
│   ├── config.py          # 設定管理
│   └── validator.py       # セキュリティバリデーション
├── bin/                   # 実行スクリプト
│   ├── start.sh          # 開始スクリプト
│   ├── stop.sh           # 停止スクリプト
│   ├── status.sh         # 状態確認スクリプト
│   └── aggregate.py      # 集計CLI
├── supervisor/           # supervisor設定
│   ├── *.conf.template   # 設定テンプレート
│   └── setup_supervisor.sh # supervisor設定スクリプト
├── test/                 # テストスクリプト
│   ├── test_collector.sh # コレクター機能テスト
│   └── test_aggregator.sh # 集計機能テスト
├── logs/                 # ログディレクトリ
├── output/               # 出力ディレクトリ（デフォルト）
├── settings.json.template # 設定ファイルテンプレート
├── ready.sh             # 環境準備スクリプト
└── README.md            # このファイル
```

## セットアップ

### 1. 環境準備

```bash
bash ready.sh
```

### 2. 設定ファイル編集（必要に応じて）

```bash
vi settings.json
```

主な設定項目：
- `collection.interval_seconds`: 収集間隔（秒）
- `collection.top_count`: 上位プロセス数
- `output.directory`: 出力ディレクトリ
- `output.file_retention_count`: ファイル保持件数

### 3. 権限設定

```bash
chmod 600 settings.json
```

## 使用方法

### 手動実行

```bash
# 開始
bash bin/start.sh

# 状態確認
bash bin/status.sh

# 停止
bash bin/stop.sh
```

### supervisor経由での実行

```bash
# supervisor設定の生成
bash supervisor/setup_supervisor.sh

# supervisor設定の登録
sudo cp supervisor/process_memory_history.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update

# プロセス管理
sudo supervisorctl start process_memory_history
sudo supervisorctl status process_memory_history
sudo supervisorctl stop process_memory_history
```

### 集計機能

```bash
# 過去24時間のデータを15分足で集計
python3 bin/aggregate.py --hours 24 --output memory_24h.tsv

# 過去1週間のデータを1時間足で集計
python3 bin/aggregate.py --days 7 --interval 60 --output memory_1week.tsv

# 特定期間のデータを集計
python3 bin/aggregate.py --range "2025-06-01 00:00:00" "2025-06-02 00:00:00" --output memory_specific.tsv

# 詳細な進捗表示
python3 bin/aggregate.py --hours 24 --output memory_24h.tsv --verbose
```

## 出力ファイル形式

### JSONファイル（収集データ）

```json
{
  "timestamp": "2025-06-04T12:34:56+09:00",
  "hostname": "server01",
  "items": [
    {
      "pid": 1234,
      "cmd": "python main.py",
      "rss": 102400,
      "group": "python"
    }
  ],
  "total_mb": 1024.5,
  "total_gb": 1.0,
  "total_tb": 0.001
}
```

### TSVファイル（集計データ）

- 1行目: ヘッダー（時間, PID1_始値, PID1_高値, PID1_安値, PID1_終値, PID2_始値, ...）
- 2行目以降: データ（時間, ローソク足4値, ローソク足4値, ...）
- 時間形式: YYYY-MM-DD HH:MM:SS
- 各PIDに対して始値・高値・安値・終値の4列が出力される
- 値なしの場合は空文字

### PID対応表（TSVファイル）

```
PID     COMMAND
1234    python main.py
1234(2) python another.py
5678    nginx: worker process
```

## トラブルシューティング

### プロセスが開始しない

1. 設定ファイルの確認
```bash
python3 src/config.py
```

2. 権限の確認
```bash
ls -la settings.json
# 600 であることを確認
```

3. ログの確認
```bash
tail -f logs/process_memory_history.log
```

### ディスク容量不足

設定ファイルで以下を調整：
- `file_retention_count`: ファイル保持件数を削減
- `cleanup_interval_seconds`: クリーンアップ間隔を短縮

### セキュリティエラー

出力ディレクトリが許可されているかチェック：
```bash
python3 src/validator.py
```

### 集計でデータが見つからない

1. データファイルの確認
```bash
ls -la output/memory_*.json
```

2. 時間範囲の確認
```bash
# ファイル名から時刻を確認
ls output/ | head -5
```

## テスト

### 機能テスト

```bash
# コレクター機能テスト
bash test/test_collector.sh

# 集計機能テスト
bash test/test_aggregator.sh
```

### 手動テスト

```bash
# 短時間実行テスト
timeout 10s python3 src/main.py

# 集計テスト（過去1時間）
python3 bin/aggregate.py --hours 1 --output test.tsv --verbose
```

## セキュリティ注意事項

1. **権限の最小化**
   - 一般ユーザーで実行してください
   - root権限は不要です

2. **設定ファイルの保護**
   - settings.jsonの権限を600に設定
   - 機密情報は含めないでください

3. **出力ディレクトリの制限**
   - allowed_output_pathsで出力先を制限
   - システムディレクトリへの書き込みは禁止

4. **ディスク容量の監視**
   - 定期的にディスク使用量を確認
   - 自動クリーンアップ機能を活用

## 要件

- Python 3.6+
- psコマンド（プロセス情報取得）
- 十分なディスク容量

