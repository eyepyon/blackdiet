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
from flask import jsonify

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



# ──────────────────────────────────────────
# @login_required デコレーター
# ──────────────────────────────────────────

class TestLoginRequired:
    """@login_required デコレーターのテスト。

    テスト用保護エンドポイントは TestingConfig の create_app 時に登録済みの
    /api/protected および /protected/page を使用する。
    """

    def _clear_session(self, client):
        """セッションをクリアするヘルパー。"""
        with client.session_transaction() as sess:
            sess.clear()

    def _set_logged_in(self, client, user_id="test-user-id-123"):
        """セッションにログイン情報を設定するヘルパー。"""
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["line_id"] = "Utest_line_id"

    def test_unauthenticated_api_returns_401(self, client):
        """未ログイン状態で保護されたAPIルートにアクセスすると401が返ること。"""
        self._clear_session(client)
        resp = client.get("/api/protected")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_unauthenticated_api_accept_json_returns_401(self, client):
        """Accept: application/json ヘッダー付きで未ログインアクセスすると401が返ること。"""
        self._clear_session(client)
        resp = client.get(
            "/api/protected",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_unauthenticated_page_redirects_to_line_login(self, client):
        """未ログイン状態で保護されたページルートにアクセスするとLINEログインへリダイレクトされること。"""
        self._clear_session(client)
        resp = client.get("/protected/page")
        assert resp.status_code == 302
        location = resp.headers.get("Location", "")
        assert "/auth/line/login" in location
        assert "next=" in location

    def test_unauthenticated_page_redirect_contains_next_url(self, client):
        """リダイレクト先のnextパラメータに元のURLが含まれること。"""
        self._clear_session(client)
        resp = client.get("/protected/page")
        assert resp.status_code == 302
        location = resp.headers.get("Location", "")
        assert "/protected/page" in location

    def test_authenticated_user_can_access_api(self, client):
        """ログイン済み状態ではAPIルートに通過できること。"""
        self._set_logged_in(client, "test-user-id-123")
        resp = client.get("/api/protected")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "ok"

    def test_authenticated_user_can_access_page(self, client):
        """ログイン済み状態ではページルートに通過できること。"""
        self._set_logged_in(client, "test-user-id-456")
        resp = client.get("/protected/page")
        assert resp.status_code == 200

    def test_login_required_preserves_function_name(self, app):
        """functools.wraps により元の関数名が保持されること。"""
        from app.utils.decorators import login_required

        def my_view():
            """my view docstring"""
            return "hello"

        wrapped = login_required(my_view)
        assert wrapped.__name__ == "my_view"
        assert wrapped.__doc__ == "my view docstring"

    def test_unauthenticated_page_with_json_accept_returns_401(self, client):
        """pageルートでもAccept: application/jsonなら401が返ること。"""
        self._clear_session(client)
        resp = client.get(
            "/protected/page",
            headers={"Accept": "application/json"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data is not None
        assert "error" in data


# ──────────────────────────────────────────
# POST /auth/logout
# ──────────────────────────────────────────

class TestLogout:
    """POST /auth/logout のテスト。"""

    def _set_logged_in(self, client, user_id: str = "test-user-id-logout"):
        """セッションにログイン情報を設定するヘルパー。"""
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["line_id"] = "Utest_logout_user"

    def test_logout_returns_200_with_ok_json(self, client):
        """ログアウトで 200 と {"status": "ok"} が返ること。"""
        self._set_logged_in(client)
        resp = client.post("/auth/logout")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["message"] == "ログアウトしました"

    def test_logout_clears_session(self, client):
        """ログアウト後にセッションの user_id が消えること。"""
        self._set_logged_in(client)
        client.post("/auth/logout")
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_logout_clears_line_id_from_session(self, client):
        """ログアウト後にセッションの line_id も消えること。"""
        self._set_logged_in(client)
        client.post("/auth/logout")
        with client.session_transaction() as sess:
            assert "line_id" not in sess

    def test_logout_when_not_logged_in_returns_200(self, client):
        """未ログイン状態でもログアウトは 200 を返すこと。"""
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.post("/auth/logout")
        assert resp.status_code == 200


# ──────────────────────────────────────────
# GET /auth/me
# ──────────────────────────────────────────

class TestMe:
    """GET /auth/me のテスト。"""

    def test_me_unauthenticated_returns_401(self, client):
        """未ログイン状態で /auth/me にアクセスすると 401 が返ること。"""
        with client.session_transaction() as sess:
            sess.clear()
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        data = resp.get_json()
        assert data is not None
        assert data["error"] == "未ログインです"

    def test_me_authenticated_returns_user_dict(self, client, app, db):
        """ログイン済みで /auth/me にアクセスするとユーザー情報が返ること。"""
        # DB にユーザーを作成
        from app import db as _db
        from app.models.user import User

        with app.app_context():
            user = User(
                line_id="Ume_test_user",
                display_name="テストユーザーme",
                picture_url="https://example.com/me.jpg",
                is_active=True,
            )
            _db.session.add(user)
            _db.session.commit()
            user_id = str(user.id)

        # セッションにログイン情報を設定
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["line_id"] = "Ume_test_user"

        resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert data["line_id"] == "Ume_test_user"
        assert data["display_name"] == "テストユーザーme"
        assert data["is_active"] is True
        assert "id" in data

    def test_me_returns_all_expected_fields(self, client, app, db):
        """返却 JSON に User.to_dict() の全フィールドが含まれること。"""
        from app import db as _db
        from app.models.user import User

        with app.app_context():
            user = User(
                line_id="Ume_fields_user",
                display_name="フィールドテスト",
                picture_url=None,
                home_area="渋谷区",
                is_active=True,
            )
            _db.session.add(user)
            _db.session.commit()
            user_id = str(user.id)

        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["line_id"] = "Ume_fields_user"

        resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        expected_keys = {
            "id", "line_id", "display_name", "picture_url",
            "home_area", "interest_areas", "is_active",
            "created_at", "updated_at",
        }
        assert expected_keys <= set(data.keys())

    def test_me_nonexistent_user_in_db_returns_404(self, client):
        """セッションに存在するがDBに存在しないユーザーIDでは 404 が返ること。"""
        with client.session_transaction() as sess:
            sess["user_id"] = "00000000-0000-0000-0000-000000000000"
            sess["line_id"] = "Ughost_user"

        resp = client.get("/auth/me")
        assert resp.status_code == 404


# ──────────────────────────────────────────
# POST /webhook/line
# ──────────────────────────────────────────

class TestLineWebhook:
    """POST /webhook/line のテスト。

    LINE Messaging API Webhook の署名検証・イベント処理を検証する。
    テスト環境では LINE_MESSAGING_CHANNEL_SECRET が空のため署名検証はスキップされる。
    署名検証テストでは明示的にシークレットを設定して検証する。
    """

    # ── ヘルパー ──────────────────────────────

    @staticmethod
    def _make_payload(event_type: str, line_id: str) -> dict:
        """テスト用 LINE Webhook ペイロードを生成する。"""
        return {
            "events": [
                {
                    "type": event_type,
                    "source": {
                        "type": "user",
                        "userId": line_id,
                    },
                }
            ]
        }

    @staticmethod
    def _make_signature(body: bytes, secret: str) -> str:
        """HMAC-SHA256 署名を生成する（LINE 仕様）。"""
        import base64
        import hashlib
        import hmac as hmac_lib

        return base64.b64encode(
            hmac_lib.new(
                secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

    # ── follow イベント ───────────────────────

    def test_follow_event_activates_existing_user(self, client, app, db):
        """follow イベントで既存ユーザーが is_active=True になること（要件6.5）。"""
        # 事前に非アクティブなユーザーを作成
        with app.app_context():
            user = User(
                line_id="Uwebhook_follow_existing",
                display_name="フォローテスト",
                is_active=False,
            )
            _db.session.add(user)
            _db.session.commit()

        payload = self._make_payload("follow", "Uwebhook_follow_existing")
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        with app.app_context():
            user = User.query.filter_by(line_id="Uwebhook_follow_existing").first()
            assert user is not None
            assert user.is_active is True

    def test_follow_event_creates_new_user_when_not_exists(self, client, app, db):
        """follow イベントでユーザーが存在しない場合、新規作成して is_active=True になること。"""
        payload = self._make_payload("follow", "Uwebhook_follow_new")
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200

        with app.app_context():
            user = User.query.filter_by(line_id="Uwebhook_follow_new").first()
            assert user is not None
            assert user.is_active is True

    def test_follow_event_keeps_active_user_active(self, client, app, db):
        """follow イベントで既に is_active=True のユーザーは引き続き True のままであること。"""
        with app.app_context():
            user = User(
                line_id="Uwebhook_follow_already_active",
                is_active=True,
            )
            _db.session.add(user)
            _db.session.commit()

        payload = self._make_payload("follow", "Uwebhook_follow_already_active")
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200

        with app.app_context():
            user = User.query.filter_by(line_id="Uwebhook_follow_already_active").first()
            assert user.is_active is True

    # ── unfollow イベント ─────────────────────

    def test_unfollow_event_deactivates_user(self, client, app, db):
        """unfollow イベントでユーザーが is_active=False になること（要件6.6）。"""
        with app.app_context():
            user = User(
                line_id="Uwebhook_unfollow",
                display_name="アンフォローテスト",
                is_active=True,
            )
            _db.session.add(user)
            _db.session.commit()

        payload = self._make_payload("unfollow", "Uwebhook_unfollow")
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        with app.app_context():
            user = User.query.filter_by(line_id="Uwebhook_unfollow").first()
            assert user is not None
            assert user.is_active is False

    def test_unfollow_event_for_unknown_user_returns_200(self, client, app, db):
        """unfollow イベントで未登録ユーザーの場合もエラーなく 200 が返ること。"""
        payload = self._make_payload("unfollow", "Uwebhook_unfollow_unknown")
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200

    # ── 署名検証 ──────────────────────────────

    def test_valid_signature_is_accepted(self, client, app, db):
        """正しい署名があればリクエストが処理されること。"""
        import json as json_lib

        secret = "test_messaging_secret"
        app.config["LINE_MESSAGING_CHANNEL_SECRET"] = secret

        payload = self._make_payload("follow", "Uwebhook_sig_valid")
        body = json_lib.dumps(payload, separators=(",", ":")).encode("utf-8")
        sig = self._make_signature(body, secret)

        resp = client.post(
            "/webhook/line",
            data=body,
            content_type="application/json",
            headers={"X-Line-Signature": sig},
        )

        assert resp.status_code == 200

        # シークレットをリセット（テスト間の干渉防止）
        app.config["LINE_MESSAGING_CHANNEL_SECRET"] = ""

    def test_invalid_signature_returns_400(self, client, app, db):
        """署名が不正な場合に 400 が返ること。"""
        import json as json_lib

        secret = "test_messaging_secret_invalid"
        app.config["LINE_MESSAGING_CHANNEL_SECRET"] = secret

        payload = self._make_payload("follow", "Uwebhook_sig_invalid")
        body = json_lib.dumps(payload, separators=(",", ":")).encode("utf-8")

        resp = client.post(
            "/webhook/line",
            data=body,
            content_type="application/json",
            headers={"X-Line-Signature": "invalid_signature_value"},
        )

        assert resp.status_code == 400

        # シークレットをリセット
        app.config["LINE_MESSAGING_CHANNEL_SECRET"] = ""

    def test_missing_signature_header_returns_400(self, client, app, db):
        """署名ヘッダーがない場合に 400 が返ること。"""
        import json as json_lib

        secret = "test_messaging_secret_missing"
        app.config["LINE_MESSAGING_CHANNEL_SECRET"] = secret

        payload = self._make_payload("follow", "Uwebhook_sig_missing")
        body = json_lib.dumps(payload, separators=(",", ":")).encode("utf-8")

        resp = client.post(
            "/webhook/line",
            data=body,
            content_type="application/json",
            # X-Line-Signature ヘッダーなし
        )

        assert resp.status_code == 400

        # シークレットをリセット
        app.config["LINE_MESSAGING_CHANNEL_SECRET"] = ""

    def test_empty_secret_skips_signature_verification(self, client, app, db):
        """LINE_MESSAGING_CHANNEL_SECRET が空の場合は署名検証をスキップすること（テスト環境）。"""
        app.config["LINE_MESSAGING_CHANNEL_SECRET"] = ""

        payload = self._make_payload("follow", "Uwebhook_no_secret")
        resp = client.post(
            "/webhook/line",
            json=payload,
            # 署名ヘッダーなし
        )

        assert resp.status_code == 200

    # ── 不明なイベント ────────────────────────

    def test_unknown_event_type_is_ignored_returns_200(self, client, app, db):
        """不明なイベントタイプは無視して 200 が返ること。"""
        payload = {
            "events": [
                {
                    "type": "message",
                    "source": {"type": "user", "userId": "Uwebhook_unknown_event"},
                    "message": {"type": "text", "text": "こんにちは"},
                }
            ]
        }
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        # DB にユーザーが作成されていないこと（未登録ユーザーなので）
        with app.app_context():
            user = User.query.filter_by(line_id="Uwebhook_unknown_event").first()
            assert user is None

    def test_empty_events_list_returns_200(self, client, app, db):
        """events が空リストの場合も 200 が返ること（LINE ping など）。"""
        payload = {"events": []}
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_response_always_returns_status_ok(self, client, app, db):
        """レスポンスは常に {"status": "ok"} を返すこと（LINE 仕様）。"""
        payload = self._make_payload("follow", "Uwebhook_status_ok")
        resp = client.post(
            "/webhook/line",
            json=payload,
            headers={"X-Line-Signature": "dummy"},
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"status": "ok"}
