"""
Auth_System テスト

対象エンドポイント:
  GET  /auth/line/login     → LINE 認可URL へのリダイレクト
  GET  /auth/line/callback  → LINE OAuth コールバック処理
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from app import db as _db
from app.models.user import User


# ──────────────────────────────────────────
# テスト用フィクスチャ
# ──────────────────────────────────────────

@pytest.fixture(scope="function")
def db(app):
    """各テスト後にテーブルをリセットする DB フィクスチャ。"""
    with app.app_context():
        yield _db
        _db.session.remove()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


# ──────────────────────────────────────────
# GET /auth/line/login
# ──────────────────────────────────────────

class TestLineLogin:
    """GET /auth/line/login のテスト。"""

    def test_redirects_to_line_authorize_url(self, client, app):
        """LINE 認可エンドポイントへリダイレクトされること。"""
        with app.test_request_context():
            resp = client.get("/auth/line/login")

        assert resp.status_code == 302
        location = resp.headers.get("Location", "")
        assert "access.line.me" in location

    def test_redirect_url_contains_required_params(self, client, app):
        """リダイレクト URL に必要なパラメータが含まれること。"""
        app.config["LINE_CHANNEL_ID"] = "test_channel_id"
        app.config["LINE_REDIRECT_URI"] = "https://example.com/auth/line/callback"

        resp = client.get("/auth/line/login")
        assert resp.status_code == 302

        location = resp.headers["Location"]
        parsed = urlparse(location)
        params = parse_qs(parsed.query)

        assert params.get("response_type") == ["code"]
        assert params.get("client_id") == ["test_channel_id"]
        assert "redirect_uri" in params
        assert "state" in params
        assert "scope" in params
        assert "profile" in params["scope"][0]
        assert "openid" in params["scope"][0]

    def test_state_stored_in_session(self, client, app):
        """state トークンがセッションに保存されること（CSRF 防止）。"""
        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get("/auth/line/login")
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            assert "oauth_state" in sess
            assert len(sess["oauth_state"]) > 10  # 十分な長さの state

    def test_next_param_stored_in_session(self, client, app):
        """next クエリパラメータがセッションに保存されること。"""
        resp = client.get("/auth/line/login?next=/coupon/get")
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            assert sess.get("oauth_next") == "/coupon/get"

    def test_no_next_param_not_stored(self, client, app):
        """next クエリパラメータがない場合はセッションに保存されないこと。"""
        with client.session_transaction() as sess:
            sess.pop("oauth_next", None)

        client.get("/auth/line/login")

        with client.session_transaction() as sess:
            assert "oauth_next" not in sess


# ──────────────────────────────────────────
# GET /auth/line/callback
# ──────────────────────────────────────────

class TestLineCallback:
    """GET /auth/line/callback のテスト。"""

    def _setup_session_with_state(self, client, state: str, next_url: str | None = None):
        """テスト用に oauth_state をセッションに設定するヘルパー。"""
        with client.session_transaction() as sess:
            sess["oauth_state"] = state
            if next_url:
                sess["oauth_next"] = next_url

    def test_successful_callback_creates_user_and_sets_session(self, client, app, db):
        """正常なコールバックでユーザーが作成されセッションが設定されること。"""
        state = "valid_state_token_abc123"
        self._setup_session_with_state(client, state)

        mock_token = {"access_token": "mock_access_token_xyz"}
        mock_profile = {
            "userId": "Utest_line_id_001",
            "displayName": "テストユーザー",
            "pictureUrl": "https://example.com/pic.jpg",
        }

        with patch("app.auth.routes.fetch_access_token", return_value=mock_token), \
             patch("app.auth.routes.fetch_profile", return_value=mock_profile):
            resp = client.get(f"/auth/line/callback?code=auth_code_abc&state={state}")

        # ログイン後は / へリダイレクト
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/"

        # セッションにユーザーIDが設定されていること
        with client.session_transaction() as sess:
            assert "user_id" in sess
            assert "line_id" in sess
            assert sess["line_id"] == "Utest_line_id_001"

        # DB にユーザーが作成されていること
        with app.app_context():
            user = User.query.filter_by(line_id="Utest_line_id_001").first()
            assert user is not None
            assert user.display_name == "テストユーザー"
            assert user.is_active is True

    def test_callback_redirects_to_next_url(self, client, app, db):
        """next URL がセッションにある場合、そこへリダイレクトされること。"""
        state = "state_with_next"
        self._setup_session_with_state(client, state, next_url="/coupon/get?spot=abc")

        mock_token = {"access_token": "mock_token"}
        mock_profile = {
            "userId": "Utest_next_user",
            "displayName": "ネクストユーザー",
            "pictureUrl": None,
        }

        with patch("app.auth.routes.fetch_access_token", return_value=mock_token), \
             patch("app.auth.routes.fetch_profile", return_value=mock_profile):
            resp = client.get(f"/auth/line/callback?code=some_code&state={state}")

        assert resp.status_code == 302
        assert "/coupon/get" in resp.headers["Location"]

    def test_existing_user_is_updated_not_duplicated(self, client, app, db):
        """既存ユーザーが更新され、重複作成されないこと。"""
        # 事前にユーザーを作成
        with app.app_context():
            existing_user = User(
                line_id="Uexisting_user",
                display_name="旧名前",
                picture_url=None,
                is_active=True,
            )
            _db.session.add(existing_user)
            _db.session.commit()
            user_id = str(existing_user.id)

        state = "state_existing_user"
        self._setup_session_with_state(client, state)

        mock_token = {"access_token": "tok"}
        mock_profile = {
            "userId": "Uexisting_user",
            "displayName": "新名前",
            "pictureUrl": "https://example.com/new_pic.jpg",
        }

        with patch("app.auth.routes.fetch_access_token", return_value=mock_token), \
             patch("app.auth.routes.fetch_profile", return_value=mock_profile):
            resp = client.get(f"/auth/line/callback?code=code_abc&state={state}")

        assert resp.status_code == 302

        # 同じ line_id のユーザーが 1 人だけであること（重複なし）
        with app.app_context():
            users = User.query.filter_by(line_id="Uexisting_user").all()
            assert len(users) == 1
            assert users[0].display_name == "新名前"

    def test_inactive_user_reactivated_on_login(self, client, app, db):
        """is_active=False のユーザーがログインすると is_active=True に戻ること。"""
        with app.app_context():
            inactive_user = User(
                line_id="Uinactive_user",
                display_name="非アクティブ",
                is_active=False,
            )
            _db.session.add(inactive_user)
            _db.session.commit()

        state = "state_reactivate"
        self._setup_session_with_state(client, state)

        mock_token = {"access_token": "tok"}
        mock_profile = {
            "userId": "Uinactive_user",
            "displayName": "復活ユーザー",
            "pictureUrl": None,
        }

        with patch("app.auth.routes.fetch_access_token", return_value=mock_token), \
             patch("app.auth.routes.fetch_profile", return_value=mock_profile):
            client.get(f"/auth/line/callback?code=code&state={state}")

        with app.app_context():
            user = User.query.filter_by(line_id="Uinactive_user").first()
            assert user.is_active is True

    def test_state_mismatch_returns_403(self, client, app):
        """state 不一致の場合に 403 が返ること（CSRF 防止）。"""
        with client.session_transaction() as sess:
            sess["oauth_state"] = "correct_state"

        resp = client.get("/auth/line/callback?code=some_code&state=wrong_state")
        assert resp.status_code == 403

    def test_missing_state_returns_403(self, client, app):
        """state パラメータがない場合に 403 が返ること。"""
        with client.session_transaction() as sess:
            sess["oauth_state"] = "some_state"

        resp = client.get("/auth/line/callback?code=some_code")
        assert resp.status_code == 403

    def test_no_session_state_returns_403(self, client, app):
        """セッションに oauth_state がない場合に 403 が返ること。"""
        with client.session_transaction() as sess:
            sess.pop("oauth_state", None)

        resp = client.get("/auth/line/callback?code=some_code&state=any_state")
        assert resp.status_code == 403

    def test_missing_code_returns_400(self, client, app):
        """code パラメータがない場合に 400 が返ること。"""
        state = "valid_state"
        with client.session_transaction() as sess:
            sess["oauth_state"] = state

        resp = client.get(f"/auth/line/callback?state={state}")
        assert resp.status_code == 400

    def test_line_token_api_failure_returns_503(self, client, app):
        """LINE Token API が失敗した場合に 503 が返ること。"""
        import requests as req_lib

        state = "valid_state_503"
        with client.session_transaction() as sess:
            sess["oauth_state"] = state

        with patch(
            "app.auth.routes.fetch_access_token",
            side_effect=req_lib.HTTPError("LINE API error"),
        ):
            resp = client.get(f"/auth/line/callback?code=bad_code&state={state}")

        assert resp.status_code == 503

    def test_line_profile_api_failure_returns_503(self, client, app):
        """LINE Profile API が失敗した場合に 503 が返ること。"""
        import requests as req_lib

        state = "valid_state_profile_503"
        with client.session_transaction() as sess:
            sess["oauth_state"] = state

        with patch("app.auth.routes.fetch_access_token", return_value={"access_token": "tok"}), \
             patch(
                 "app.auth.routes.fetch_profile",
                 side_effect=req_lib.HTTPError("Profile API error"),
             ):
            resp = client.get(f"/auth/line/callback?code=valid_code&state={state}")

        assert resp.status_code == 503

    def test_state_consumed_after_callback(self, client, app, db):
        """コールバック処理後に oauth_state がセッションから削除されること（リプレイ攻撃防止）。"""
        state = "state_one_time"
        self._setup_session_with_state(client, state)

        mock_token = {"access_token": "tok"}
        mock_profile = {
            "userId": "Uone_time_state_user",
            "displayName": "ワンタイム",
            "pictureUrl": None,
        }

        with patch("app.auth.routes.fetch_access_token", return_value=mock_token), \
             patch("app.auth.routes.fetch_profile", return_value=mock_profile):
            client.get(f"/auth/line/callback?code=code&state={state}")

        # 同じ state で再度リクエストすると 403 になること
        resp = client.get(f"/auth/line/callback?code=code&state={state}")
        assert resp.status_code == 403
