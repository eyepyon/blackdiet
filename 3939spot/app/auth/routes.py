"""
Auth_System routes
- GET  /auth/line/login       LINE OAuthページへリダイレクト
- GET  /auth/line/callback    OAuth callbackハンドラー
- POST /auth/logout           セッション破棄
- GET  /auth/me               現在ユーザー情報
- POST /webhook/line          LINE Messaging API Webhook
"""

from __future__ import annotations

import logging
import secrets

from flask import abort, current_app, jsonify, redirect, request, session, url_for

from app import db
from app.auth import auth_bp, webhook_bp
from app.auth.line_client import build_authorize_url, fetch_access_token, fetch_profile
from app.models.user import User
from app.utils.session import clear_session, get_current_user_id, set_session_user

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# GET /auth/line/login
# ──────────────────────────────────────────

@auth_bp.route("/line/login")
def line_login():
    """LINE OAuthログインページへリダイレクトする。

    CSRF防止のため state トークンをセッションに保存する。
    ``next`` クエリパラメータがある場合はセッションに保存し、
    ログイン後のリダイレクト先として使用する。
    """
    # CSRF 防止: state トークンを生成してセッションに保存
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    session.modified = True

    # ログイン後のリダイレクト先を保存
    next_url = request.args.get("next")
    if next_url:
        session["oauth_next"] = next_url

    authorize_url = build_authorize_url(
        client_id=current_app.config.get("LINE_CHANNEL_ID", ""),
        redirect_uri=current_app.config.get("LINE_REDIRECT_URI", ""),
        state=state,
    )

    logger.debug("LINE OAuthリダイレクト: state=%s", state)
    return redirect(authorize_url)


# ──────────────────────────────────────────
# GET /auth/line/callback
# ──────────────────────────────────────────

@auth_bp.route("/line/callback")
def line_callback():
    """LINE OAuth コールバックを処理する。

    1. ``state`` パラメータの検証（CSRF防止）
    2. ``code`` パラメータを使って LINE Token Endpoint でアクセストークンを取得
    3. アクセストークンを使って LINE Profile Endpoint でプロフィール情報を取得
    4. ``line_id`` でユーザーを検索し、存在しなければ新規作成
    5. セッションを設定し、``next`` があればそこへ、なければ ``/`` へリダイレクト
    """
    # ── 1. state 検証（CSRF防止） ──────────
    received_state = request.args.get("state", "")
    expected_state = session.pop("oauth_state", None)

    if not expected_state or not secrets.compare_digest(received_state, expected_state):
        logger.warning(
            "OAuth state 不一致: received=%r, expected=%r",
            received_state,
            expected_state,
        )
        abort(403)

    # ── 2. アクセストークン取得 ────────────
    code = request.args.get("code")
    if not code:
        logger.warning("LINE callback: code パラメータがありません")
        abort(400)

    try:
        token_data = fetch_access_token(
            code=code,
            client_id=current_app.config.get("LINE_CHANNEL_ID", ""),
            client_secret=current_app.config.get("LINE_CHANNEL_SECRET", ""),
            redirect_uri=current_app.config.get("LINE_REDIRECT_URI", ""),
        )
    except Exception as exc:  # requests.HTTPError など
        logger.error("LINE トークン取得エラー: %s", exc)
        abort(503)

    access_token = token_data.get("access_token")
    if not access_token:
        logger.error("LINE トークンレスポンスに access_token がありません: %s", token_data)
        abort(503)

    # ── 3. プロフィール取得 ────────────────
    try:
        profile = fetch_profile(access_token)
    except Exception as exc:
        logger.error("LINE プロフィール取得エラー: %s", exc)
        abort(503)

    line_id = profile.get("userId")
    if not line_id:
        logger.error("LINE プロフィールに userId がありません: %s", profile)
        abort(503)

    display_name = profile.get("displayName")
    picture_url = profile.get("pictureUrl")

    # ── 4. ユーザー取得または新規作成 ───────
    user = User.query.filter_by(line_id=line_id).first()
    if user is None:
        user = User(
            line_id=line_id,
            display_name=display_name,
            picture_url=picture_url,
            is_active=True,
        )
        db.session.add(user)
        logger.info("新規ユーザー作成: line_id=%s", line_id)
    else:
        # 既存ユーザー: プロフィール情報を更新し、ブロック解除時に is_active を回復
        user.display_name = display_name
        user.picture_url = picture_url
        if not user.is_active:
            user.is_active = True
            logger.info("ユーザー再アクティブ化: line_id=%s", line_id)

    db.session.commit()

    # ── 5. セッション設定 & リダイレクト ────
    set_session_user(user_id=str(user.id), line_id=line_id)

    next_url = session.pop("oauth_next", None) or "/"
    logger.debug("ログイン成功: user_id=%s → next=%s", user.id, next_url)
    return redirect(next_url)


# ──────────────────────────────────────────
# POST /auth/logout
# ──────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """セッションを破棄してログアウトする。"""
    user_id = get_current_user_id()
    clear_session()
    logger.debug("ログアウト: user_id=%s", user_id)
    return jsonify({"status": "ok", "message": "ログアウトしました"}), 200


# ──────────────────────────────────────────
# GET /auth/me
# ──────────────────────────────────────────

@auth_bp.route("/me")
def me():
    """現在ログイン中のユーザー情報を返す。"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "未ログインです"}), 401

    user = db.session.get(User, user_id)
    if user is None:
        clear_session()
        return jsonify({"error": "ユーザーが見つかりません"}), 404

    return jsonify(user.to_dict()), 200


# ──────────────────────────────────────────
# POST /webhook/line
# ──────────────────────────────────────────

@webhook_bp.route("/webhook/line", methods=["POST"])
def line_webhook():
    """LINE Messaging API Webhook（stub）"""
    return jsonify({"status": "stub", "endpoint": "POST /webhook/line"}), 200
