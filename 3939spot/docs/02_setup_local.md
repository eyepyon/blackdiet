# ローカル開発環境 セットアップ手順

## 前提条件

- Python 3.12 以上
- Git
- Docker Desktop（Docker Composeを使う場合）

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

`.env` を編集して最低限以下を設定します。

```dotenv
FLASK_ENV=development
SECRET_KEY=ローカル開発用の任意の文字列

# ローカル開発はSQLiteを使用（PostgreSQL不要）
DATABASE_URL=sqlite:///dev.db

# LINE APIキー（動作確認する場合は実際の値を設定）
LINE_CHANNEL_ID=your-line-channel-id
LINE_CHANNEL_SECRET=your-line-channel-secret
LINE_REDIRECT_URI=http://localhost:5000/auth/line/callback
LINE_MESSAGING_CHANNEL_SECRET=your-messaging-channel-secret
LINE_MESSAGING_CHANNEL_ACCESS_TOKEN=your-messaging-channel-access-token

# Google Maps（マップ機能を使う場合）
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```

> **注意**: `.env` ファイルは `.gitignore` で除外されています。絶対にGitにコミットしないでください。

---

## 手順5: DBマイグレーションの実行

```bash
flask db upgrade
```

初回実行時にSQLiteのDBファイル (`instance/dev.db`) が作成されます。

---

## 手順6: 開発サーバーの起動

```bash
flask run
```

または

```bash
python run.py
```

ブラウザで http://localhost:5000 にアクセスしてトップページが表示されれば起動成功です。

---

## Docker Composeを使う場合

Dockerがインストールされていれば、Python・仮想環境の手順を省略できます。

```bash
# 起動
docker compose up

# バックグラウンドで起動
docker compose up -d

# 停止
docker compose down
```

http://localhost:5000 でアクセスできます。

コードを変更すると自動リロードされます（`--reload` オプションが有効）。

---

## テストの実行

```bash
# 全テスト実行
pytest

# 詳細ログ付き
pytest -v

# 特定のテストファイルのみ
pytest tests/test_coupons.py

# プロパティベーステスト
pytest tests/property/
```

---

## よくある問題

### `flask: command not found`

仮想環境が有効化されていない可能性があります。

```bash
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

### `ModuleNotFoundError`

依存パッケージがインストールされていない可能性があります。

```bash
pip install -r requirements.txt
```

### DBマイグレーションエラー

既存のDBファイルを削除してやり直します（ローカルのみ）。

```bash
rm instance/dev.db
flask db upgrade
```

### LINEログインがリダイレクトエラーになる

LINE Developersコンソールで設定した「コールバックURL」と `.env` の `LINE_REDIRECT_URI` が一致しているか確認してください。ローカルは `http://localhost:5000/auth/line/callback` になります。
