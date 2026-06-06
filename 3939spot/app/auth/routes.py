"""
Auth_System routes
- GET  /auth/line/login       LINE OAuthページへリダイレクト
- GET  /auth/line/callback    OAuth callbackハンドラー
- POST /auth/logout           セッション破棄
- GET  /auth/me               現在ユーザー情報
- POST /webhook/line          LINE Messaging API Webhook
"""

from __future__ import annotations

import hashlib
import hmac
import base64
import logging
import secrets

import requests as http_requests

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
    """LINE Messaging API Webhook。

    LINE から送信される follow / unfollow / block イベントを処理する。

    署名検証:
      - ``X-Line-Signature`` ヘッダーの HMAC-SHA256 署名を検証する。
      - ``LINE_MESSAGING_CHANNEL_SECRET`` が空（テスト環境）の場合は検証をスキップ。
      - 署名不一致の場合は 400 を返す。

    イベント処理:
      - ``follow``: line_id でユーザーを検索し ``is_active=True`` に更新（存在しなければ新規作成）。
      - ``unfollow`` / ``block``: line_id でユーザーを検索し ``is_active=False`` に更新。
      - その他のイベントは無視する。

    Returns:
        常に ``{"status": "ok"}`` を 200 で返す（LINE 仕様）。
    """
    channel_secret = current_app.config.get("LINE_MESSAGING_CHANNEL_SECRET", "")

    # ── 署名検証 ──────────────────────────────
    if channel_secret:
        signature = request.headers.get("X-Line-Signature", "")
        body = request.get_data()  # 生のリクエストボディ（bytes）
        expected_sig = base64.b64encode(
            hmac.new(
                channel_secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        if not hmac.compare_digest(expected_sig, signature):
            logger.warning("LINE Webhook 署名不一致: received=%r", signature)
            abort(400)

    # ── ペイロード解析 ────────────────────────
    payload = request.get_json(silent=True) or {}
    events = payload.get("events", [])

    for event in events:
        event_type = event.get("type")
        source = event.get("source", {})
        line_id = source.get("userId")

        if not line_id:
            logger.debug("LINE Webhook: userId なし、スキップ: type=%s", event_type)
            continue

        if event_type == "follow":
            # ブロック解除 / 友だち追加 → is_active=True
            user = User.query.filter_by(line_id=line_id).first()
            if user is None:
                user = User(line_id=line_id, is_active=True)
                db.session.add(user)
                logger.info("LINE follow: 新規ユーザー作成: line_id=%s", line_id)
            else:
                user.is_active = True
                logger.info("LINE follow: ユーザー再アクティブ化: line_id=%s", line_id)
            db.session.commit()

        elif event_type in ("unfollow", "block"):
            # ブロック / 退会 → is_active=False（通知停止）
            user = User.query.filter_by(line_id=line_id).first()
            if user is not None:
                user.is_active = False
                db.session.commit()
                logger.info("LINE %s: ユーザー非アクティブ化: line_id=%s", event_type, line_id)
            else:
                logger.debug("LINE %s: 未登録ユーザー: line_id=%s", event_type, line_id)

        elif event_type == "message":
            # テキストメッセージに応答
            reply_token = event.get("replyToken")
            msg_obj = event.get("message", {})
            if msg_obj.get("type") != "text" or not reply_token:
                continue

            text = (msg_obj.get("text") or "").strip()
            base_url = current_app.config.get("LINE_REDIRECT_URI", "").rsplit("/auth/", 1)[0]

            if "提携店検索" in text or ("提携店" in text and "検索" in text) or text == "提携店":
                reply_text = f"提携スポットマップはこちら：\n{base_url}/map"
            elif "交換券" in text or "履歴" in text:
                reply_text = f"交換券一覧はこちら：\n{base_url}/coupon/list"
            else:
                reply_text = f"3939SPOTへようこそ！\n{base_url}/"

            _send_line_reply(reply_token, reply_text)
            logger.debug("LINE message 応答: line_id=%s text=%r", line_id, text)

        else:
            logger.debug("LINE Webhook: 未対応イベント type=%s、スキップ", event_type)
    return jsonify({"status": "ok"}), 200


# ──────────────────────────────────────────
# LINE Messaging API ヘルパー
# ──────────────────────────────────────────

def _send_line_reply(reply_token: str, message: str) -> None:
    """LINE Messaging API Reply でメッセージを送信する。

    LINE_MESSAGING_CHANNEL_ACCESS_TOKEN が空ならスキップ。

    Args:
        reply_token: Webhook イベントの replyToken。
        message: 送信するテキストメッセージ。
    """
    access_token = current_app.config.get("LINE_MESSAGING_CHANNEL_ACCESS_TOKEN", "")
    if not access_token:
        logger.debug("_send_line_reply: アクセストークン未設定、スキップ")
        return

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    body = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": message}],
    }

    try:
        resp = http_requests.post(url, json=body, headers=headers, timeout=5)
        if not resp.ok:
            logger.warning(
                "_send_line_reply: 送信失敗 status=%s body=%s",
                resp.status_code,
                resp.text,
            )
    except Exception as exc:
        logger.error("_send_line_reply: 例外発生: %s", exc)
