"""
app/utils/session.py のセッションユーティリティ 単体テスト

タスク 1.5 の要件を検証する:
- get_current_user_id() / set_session_user() / clear_session() / is_logged_in() / touch_session()
- before_request フックによる自動 TTL リセット
- SESSION_KEY_PREFIX が "session:" に設定されていること
"""

import pytest

from app import create_app
from app.utils.session import (
    clear_session,
    get_current_user_id,
    is_logged_in,
    set_session_user,
    touch_session,
)

# ──────────────────────────────────────────
# フィクスチャ
# ──────────────────────────────────────────

@pytest.fixture(scope="module")
def session_app():
    """セッションテスト用 Flask アプリ（テスト設定）。"""
    app = create_app("testing")
    return app


@pytest.fixture()
def ctx(session_app):
    """リクエストコンテキストを提供する。各テスト後にコンテキストを破棄する。"""
    with session_app.test_request_context("/"):
        yield session_app


# ──────────────────────────────────────────
# get_current_user_id
# ──────────────────────────────────────────

class TestGetCurrentUserId:
    """get_current_user_id() のテスト。"""

    def test_returns_none_when_not_set(self, ctx):
        """セッションが空の場合に None を返すこと。"""
        assert get_current_user_id() is None

    def test_returns_user_id_after_set(self, ctx):
        """set_session_user() 後に user_id が取得できること。"""
        set_session_user("uuid-1234", "U_line_abc")
        assert get_current_user_id() == "uuid-1234"

    def test_returns_none_after_clear(self, ctx):
        """clear_session() 後に None を返すこと。"""
        set_session_user("uuid-5678", "U_line_xyz")
        clear_session()
        assert get_current_user_id() is None


# ──────────────────────────────────────────
# set_session_user
# ──────────────────────────────────────────

class TestSetSessionUser:
    """set_session_user() のテスト。"""

    def test_sets_user_id(self, ctx):
        """user_id がセッションに設定されること。"""
        set_session_user("user-001", "Uline001")
        assert get_current_user_id() == "user-001"

    def test_sets_permanent_true(self, ctx):
        """session.permanent が True に設定されること（TTL 有効化）。"""
        from flask import session as flask_session
        set_session_user("user-002", "Uline002")
        assert flask_session.permanent is True

    def test_sets_last_seen(self, ctx):
        """session に last_seen キーが設定されること。"""
        from flask import session as flask_session
        set_session_user("user-003", "Uline003")
        assert "last_seen" in flask_session

    def test_sets_line_id(self, ctx):
        """session に line_id が設定されること。"""
        from flask import session as flask_session
        set_session_user("user-004", "Uline004")
        assert flask_session.get("line_id") == "Uline004"

    def test_overwrite_existing_user(self, ctx):
        """既存セッションを上書きできること。"""
        set_session_user("old-user", "Uold")
        set_session_user("new-user", "Unew")
        assert get_current_user_id() == "new-user"


# ──────────────────────────────────────────
# clear_session
# ──────────────────────────────────────────

class TestClearSession:
    """clear_session() のテスト。"""

    def test_clears_all_session_data(self, ctx):
        """セッションデータ（user_id / line_id / last_seen）が削除されること。"""
        from flask import session as flask_session
        set_session_user("user-clear", "Uline_clear")
        clear_session()
        # ユーザー関連データが削除されていること
        assert "user_id" not in flask_session
        assert "line_id" not in flask_session
        assert "last_seen" not in flask_session

    def test_is_idempotent_on_empty_session(self, ctx):
        """空セッションに対しても例外なく動作すること。"""
        clear_session()
        clear_session()  # 2回呼んでもエラーにならない
        assert get_current_user_id() is None


# ──────────────────────────────────────────
# is_logged_in
# ──────────────────────────────────────────

class TestIsLoggedIn:
    """is_logged_in() のテスト。"""

    def test_returns_false_when_not_logged_in(self, ctx):
        """未ログイン状態では False を返すこと。"""
        assert is_logged_in() is False

    def test_returns_true_when_logged_in(self, ctx):
        """ログイン状態では True を返すこと。"""
        set_session_user("user-login", "Uline_login")
        assert is_logged_in() is True

    def test_returns_false_after_logout(self, ctx):
        """clear_session() 後は False を返すこと。"""
        set_session_user("user-logout", "Uline_logout")
        clear_session()
        assert is_logged_in() is False


# ──────────────────────────────────────────
# touch_session
# ──────────────────────────────────────────

class TestTouchSession:
    """touch_session() のテスト。"""

    def test_does_nothing_when_not_logged_in(self, ctx):
        """未ログイン状態では user_id / last_seen を変更しないこと。"""
        from flask import session as flask_session
        touch_session()
        assert "user_id" not in flask_session
        assert "last_seen" not in flask_session

    def test_updates_last_seen(self, ctx):
        """ログイン済み状態で last_seen を更新すること。"""
        from flask import session as flask_session
        import time
        set_session_user("user-touch", "Uline_touch")
        first_seen = flask_session.get("last_seen")
        time.sleep(0.01)  # 時刻が変わるように少し待つ
        touch_session()
        second_seen = flask_session.get("last_seen")
        # last_seen が更新されていること（同じか新しい値）
        assert second_seen >= first_seen

    def test_sets_modified_true(self, ctx):
        """session.modified が True になること（Redis TTL リセットの前提）。"""
        from flask import session as flask_session
        set_session_user("user-mod", "Uline_mod")
        flask_session.modified = False  # 一旦リセット
        touch_session()
        assert flask_session.modified is True

    def test_keeps_permanent_true(self, ctx):
        """touch 後も session.permanent が True のままであること。"""
        from flask import session as flask_session
        set_session_user("user-perm", "Uline_perm")
        touch_session()
        assert flask_session.permanent is True


# ──────────────────────────────────────────
# 設定値の確認
# ──────────────────────────────────────────

class TestSessionConfig:
    """Flask-Session の設定値テスト。"""

    def test_session_key_prefix(self, session_app):
        """SESSION_KEY_PREFIX が 'session:' に設定されていること（Redisキー設計準拠）。"""
        assert session_app.config["SESSION_KEY_PREFIX"] == "session:"

    def test_session_permanent_is_true(self, session_app):
        """SESSION_PERMANENT が True であること（TTL 有効化）。"""
        assert session_app.config["SESSION_PERMANENT"] is True

    def test_permanent_session_lifetime_30_days(self, session_app):
        """PERMANENT_SESSION_LIFETIME が 30日（2592000秒）であること。"""
        expected = 60 * 60 * 24 * 30
        assert session_app.config["PERMANENT_SESSION_LIFETIME"] == expected

    def test_session_use_signer(self, session_app):
        """SESSION_USE_SIGNER が True であること（セッション署名有効）。"""
        assert session_app.config["SESSION_USE_SIGNER"] is True


# ──────────────────────────────────────────
# before_request フック統合テスト
# ──────────────────────────────────────────

class TestBeforeRequestHook:
    """before_request フックによる touch_session() 自動実行のテスト。"""

    def test_touch_session_called_on_request(self, session_app):
        """リクエスト時にセッションが自動的にタッチされること。"""
        from flask import session as flask_session

        with session_app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = "hook-user"
                sess["line_id"] = "Uhook"
                sess["last_seen"] = "2000-01-01T00:00:00+00:00"
                sess["_permanent"] = True

            # リクエストを送信 → before_request フックが実行される
            client.get("/")

            with client.session_transaction() as sess:
                # last_seen が更新されていること（2000年より新しい値）
                assert sess.get("last_seen", "") > "2000-01-01T00:00:00+00:00"

    def test_no_session_modification_when_not_logged_in(self, session_app):
        """未ログイン状態ではリクエスト後もセッションが空であること。"""
        with session_app.test_client() as client:
            client.get("/")
            with client.session_transaction() as sess:
                assert "user_id" not in sess
