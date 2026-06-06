# ベースイメージ: python:3.12-slim
FROM python:3.12-slim

# Python の標準的な最適化環境変数
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# psycopg2-binary に必要なシステム依存パッケージをインストール
# --no-install-recommends でイメージサイズを最小化
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# 依存ライブラリのレイヤーキャッシュ最適化:
# requirements.txt を先にコピーして pip install することで、
# アプリコードが変更されても依存ライブラリ層は再ビルドされない
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# セキュリティ: non-root ユーザーで実行
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

# Cloud Run / gunicorn が listen するポート
EXPOSE 8080

# gunicorn でアプリを起動
# --workers 2: CPU バウンドな処理向けに 2 ワーカー
# --threads 4: 各ワーカーで I/O 並行処理
# --timeout 120: LINE API / Cloud SQL 等の外部通信に余裕を持たせる
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120", "run:app"]
