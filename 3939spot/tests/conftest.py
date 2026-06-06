"""
pytest 共通フィクスチャ
"""

import pytest

from app import create_app, db as _db


@pytest.fixture(scope="session")
def app():
    """テスト用 Flask アプリを生成し、SQLite in-memory DB を初期化する。"""
    flask_app = create_app("testing")

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture(scope="session")
def client(app):
    """テスト用クライアントを返す。"""
    return app.test_client()


@pytest.fixture(scope="session")
def app_context(app):
    """アプリコンテキストを提供する。"""
    with app.app_context():
        yield app


@pytest.fixture(scope="function")
def db(app):
    """
    各テスト関数に DB セッションを提供し、テスト終了後にテーブルデータをリセットする。

    テーブル定義（スキーマ）はセッション単位で維持し、
    各テスト後にすべてのテーブルを切り捨てることでテスト間の独立性を保つ。
    """
    with app.app_context():
        yield _db
        # テスト後に全テーブルをリセット（スキーマは保持）
        _db.session.remove()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()
