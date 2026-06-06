"""
Alembic 環境設定ファイル（Flask-Migrate 標準構成）

Flask-Migrate が `flask db migrate` / `flask db upgrade` を実行するときに
このファイルが読み込まれます。

- run_migrations_offline(): DB接続なしでSQLを生成（オフラインモード）
- run_migrations_online():  実際のDB接続でマイグレーションを実行（オンラインモード）

Flask アプリケーションコンテキストを利用して SQLAlchemy の接続情報を取得し、
app/models/__init__.py で登録されたすべてのモデルのメタデータを Alembic に渡します。
"""

import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app

# ────────────────────────────────────────────────────────────
# Alembic Config オブジェクト（alembic.ini の設定値にアクセス可能）
# ────────────────────────────────────────────────────────────
config = context.config

# alembic.ini の logging 設定を Python logging に反映する
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")


def get_engine():
    """
    Flask-SQLAlchemy の db エンジンを取得する。
    Flask 2.x 以降と Flask-SQLAlchemy 3.x 以降の両方に対応するヘルパー。
    """
    try:
        # Flask-SQLAlchemy 3.x (get_engine が存在する場合)
        return current_app.extensions["migrate"].db.get_engine()
    except (TypeError, AttributeError):
        # Flask-SQLAlchemy 2.x 以前
        return current_app.extensions["migrate"].db.engine


def get_engine_url():
    """
    エンジンの接続 URL を文字列として返す。
    パスワード等の機密情報はマスクせず、Alembic に正確な URL を渡す。
    """
    try:
        return get_engine().url.render_as_string(hide_password=False)
    except AttributeError:
        return str(get_engine().url)


# ────────────────────────────────────────────────────────────
# target_metadata の設定
# Flask-SQLAlchemy + Flask-Migrate が使用するモデルメタデータを登録する。
# app/models/__init__.py をインポートすることで、すべてのモデルクラスが
# SQLAlchemy の MetaData に登録された状態になる。
# ────────────────────────────────────────────────────────────

# Flask アプリケーションコンテキスト内でのみ有効なため、
# current_app.extensions["migrate"].db.metadata を参照する。
target_db = current_app.extensions["migrate"].db

# すべてのモデルを MetaData に登録するためにインポートする
# （副作用として各モデルクラスが db.metadata に登録される）
# Flask-Migrate は既にアプリケーションコンテキスト内でこのファイルを実行するため、
# ここでは直接インポートするだけでよい。
import app.models  # noqa: F401 – モデルを MetaData に登録

target_metadata = target_db.metadata

# Alembic の接続 URL を Flask アプリの設定から取得して上書きする
config.set_main_option("sqlalchemy.url", get_engine_url())


# ────────────────────────────────────────────────────────────
# オフラインマイグレーション
# DB 接続なしで SQL ファイルを生成するモード。
# `alembic upgrade --sql head` 等で使用される。
# ────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    'offline' モードでマイグレーションを実行する。

    DB への実際の接続は行わず、URL だけを使って Dialect を設定し、
    SQL スクリプトを標準出力またはファイルに出力する。
    target_metadata を渡すことで `--autogenerate` オプションが機能する。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # PostgreSQL 固有オプション: スキーマ比較時に型を正確に判定
        compare_type=True,
        # PostgreSQL 固有オプション: サーバーデフォルト値の変更を検出
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ────────────────────────────────────────────────────────────
# オンラインマイグレーション
# 実際の DB 接続を使ってマイグレーションを実行するモード。
# `flask db upgrade` で通常実行されるモード。
# ────────────────────────────────────────────────────────────

def run_migrations_online() -> None:
    """
    'online' モードでマイグレーションを実行する。

    エンジンを作成して DB に接続し、実際の DDL を実行する。
    Flask-Migrate が提供する db エンジンをそのまま利用することで、
    Flask アプリの設定（DATABASE_URL 等）が自動的に反映される。
    """

    def process_revision_directives(context, revision, directives):
        """
        空のマイグレーションファイルが生成されないようにするフック。
        モデルに変更がない場合に空のリビジョンファイルを作成しない。
        """
        if getattr(config, "cmd_opts", None) and config.cmd_opts.autogenerate:
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("スキーマ変更なし。マイグレーションファイルは生成されません。")

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # PostgreSQL 固有オプション
            compare_type=True,
            compare_server_default=True,
            # 空マイグレーション防止フック
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


# ────────────────────────────────────────────────────────────
# エントリーポイント: オフライン / オンラインを自動判定して実行
# ────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
