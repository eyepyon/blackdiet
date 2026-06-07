# ローカル開発環境 セットアップ手順

## 構成の概要

ローカル開発環境は**外部サービス依存ゼロ**で動作します。

| 項目 | ローカル (development) | 本番 (GCP) |
|---|---|---|
| データベース | **SQLite** (ファイル: `instance/dev.db`) | Cloud SQL PostgreSQL 15 |
| セッション | Flaskファイルセッション (`flask_session/`) | Cloud Memorystore (Redis) |
| Redis | **不要** | Cloud Memorystore |
| 静的ファイル | ローカルファイル配信 | Google Cloud Storage |

PostgreSQLもRedisもインストール不要。`python run.py` だけで起動できます。

---

## 前提条件

- Python 3.12 以上
- Git
- Docker Desktop（Docker Composeを使う場合のみ）

---

## 手順1: リポジトリのクローン

```bash
git clone <リポジトリURL>
cd 3939spot
```

---

## 手順2: 仮想環境の作成・有効化

```bash
# 仮想環境を作成
python -m venv venv

# 有効化 (Mac/Linux)
source venv/bin/activate

# 有効化 (Windows)
venv\Scripts\activate
```

プロンプトの先頭に `(venv)` と表示されれば有効化成功です。

---

## 手順3: 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

---

## 手順4: 環境変数の設定

`.env.example` をコピーして `.env` を作成します。

```bash
cp .env.example .env
```

ローカル開発に必要な最低限の設定（`.env`）:

```dotenv
# Flask
FLASK_ENV=development
SECRET_KEY=なんでもいいローカル用文字列

# DB: SQLite（このままでOK、変更不要）
DATABASE_URL=sqlite:///dev.db

# LINE APIキー（LINEログインを実際に試す場合のみ設定）
LINE_CHANNEL_ID=your-line-channel-id
LINE_CHANNEL_SECRET=your-line-channel-secret
LINE_REDIRECT_URI=http://localhost:5000/auth/line/callback
LINE_MESSAGING_CHANNEL_SECRET=your-messaging-channel-secret
LINE_MESSAGING_CHANNEL_ACCESS_TOKEN=your-messaging-channel-access-token

# Google Maps（マップページを表示する場合のみ設定）
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```

> **REDIS_URL・DATABASE_URLのPostgreSQL設定は不要です。** ローカルではSQLiteとFlaskファイルセッションが自動的に使われます。

> **注意**: `.env` は `.gitignore` で除外済みです。絶対にGitにコミットしないでください。

---

## 手順5: DBの初期化

```bash
flask db upgrade
```

`instance/dev.db` (SQLiteファイル) が作成されます。初回のみ必要です。

---

## 手順6: 開発サーバーの起動

```bash
python run.py
```

または

```bash
flask run
```

ブラウザで http://localhost:5000 にアクセスしてトップページが表示されれば起動成功です。

---

## Docker Composeを使う場合

DockerがインストールされていればPython・venvのセットアップを省略できます。こちらもSQLiteを使用します。

```bash
# 起動（初回はイメージビルドが入るので少し時間がかかります）
docker compose up

# バックグラウンドで起動
docker compose up -d

# 停止
docker compose down
```

http://localhost:5000 でアクセスできます。コードを変更すると自動リロードされます。

SQLiteのDBファイルはDockerボリューム (`sqlite_data`) に保存されるため、コンテナを停止してもデータは残ります。

---

## テストの実行

```bash
# 全テスト実行
pytest

# 詳細ログ付き
pytest -v

# 特定のテストファイルのみ
pytest tests/test_coupons.py

# プロパティベーステスト（Hypothesis）
pytest tests/property/
```

テストは自動的に `FLASK_ENV=testing` でSQLiteのインメモリDBを使用するため、実際のDBファイルには影響しません。

---

## ローカル→本番の環境変数切り替え

本番デプロイ時（GCP Cloud Run）では以下に切り替えます。ローカルの `.env` は変更不要です。

| 環境変数 | ローカル (development) | 本番 (production) |
|---|---|---|
| `FLASK_ENV` | `development` | `production` |
| `DATABASE_URL` | `sqlite:///dev.db` | `postgresql+pg8000://...` (Cloud SQL) |
| `REDIS_URL` | 未設定 | `redis://REDIS_IP:6379/0` (Cloud Memorystore) |

本番の環境変数はGCPコンソールのCloud Run「環境変数」または Secret Manager で管理します（[03_setup_gcp.md](./03_setup_gcp.md) を参照）。

---

## よくある問題

### `flask: command not found`

仮想環境が有効化されていない可能性があります。

```bash
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

### `ModuleNotFoundError`

```bash
pip install -r requirements.txt
```

### DBマイグレーションエラー

SQLiteファイルを削除してやり直します（ローカルのみ。データが消えます）。

```bash
rm instance/dev.db
flask db upgrade
```

### LINEログインが `redirect_uri_mismatch` になる

LINE DevelopersコンソールのコールバックURLと `.env` の `LINE_REDIRECT_URI` が一致しているか確認してください。

```dotenv
# ローカル用
LINE_REDIRECT_URI=http://localhost:5000/auth/line/callback
```
