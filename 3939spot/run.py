"""
3939SPOT - アプリケーションエントリーポイント

使用方法:
  開発:    python run.py
  本番:    gunicorn --bind 0.0.0.0:8080 run:app
"""

import os

from app import create_app

# 環境変数 FLASK_ENV から設定名を取得（未設定時は 'development'）
config_name = os.environ.get("FLASK_ENV", "development")

# gunicorn が `run:app` で参照できるよう、モジュールレベルに公開
app = create_app(config_name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
