"""
セッション操作ユーティリティ

Flask標準の署名付きCookieセッションを使用したセッション管理ヘルパー。
Redis・Flask-Session不要。SECRET_KEY で署名されたCookieにデータを保存する。

注意: Cookieに保存できるデータは4KB以内。機密データ（パスワード等）は保存しない。
TTL: PERMANENT_SESSION_LIFETIME（30日）、最終アクセスごとにCookieが再発行される。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import session

logger = logging.getLogger(__name__)

# セッション内で使用するキー名
_KEY_USER_ID = "user_id"
_KEY_LINE_ID = "line_id"
_KEY_LAST_SEEN = "last_seen"


def get_current_user_id() -> str | None:
    """現在のセッションからユーザーIDを取得する。

    Returns:
        ユーザーID 文字列。未ログインまたはセッション未設定の場合は None。
    """
    return session.get(_KEY_USER_ID)


def set_session_user(user_id: str, line_id: str) -> None:
    """セッションにユーザー情報を設定する。

    Flask標準のCookieセッションに保存。PERMANENT_SESSION_LIFETIME（30日）が TTL。
    session.permanent = True でブラウザを閉じてもCookieが残る。

    Args:
        user_id: データベース上のユーザー UUID 文字列。
        line_id: LINE ユーザー ID 文字列。
    """
    session[_KEY_USER_ID] = user_id
    session[_KEY_LINE_ID] = line_id
    session[_KEY_LAST_SEEN] = _now_iso()
    session.permanent = True
    session.modified = True
    logger.debug("セッションを設定しました: user_id=%s", user_id)


def clear_session() -> None:
    """セッションをクリアする。"""
    session.clear()
    logger.debug("セッションをクリアしました。")


def is_logged_in() -> bool:
    """ログイン状態を確認する。

    Returns:
        セッションに ``user_id`` が存在する場合は True、それ以外は False。
    """
    return bool(session.get(_KEY_USER_ID))


def touch_session() -> None:
    """セッションの最終アクセス時刻を更新してCookieの有効期限をリセットする。

    ログイン済みセッションが存在する場合のみ更新する。
    session.modified = True でFlaskがCookieを再発行し、TTL（30日）がリセットされる。
    """
    if not is_logged_in():
        return
    session[_KEY_LAST_SEEN] = _now_iso()
    session.permanent = True
    session.modified = True
    logger.debug("セッション TTL をリセットしました。")


def get_session_expiry_info() -> dict | None:
    """セッションの有効期限情報を返す。

    Returns:
        有効期限情報の辞書、またはセッションが存在しない場合は None。
    """
    if not is_logged_in():
        return None

    last_seen_str = session.get(_KEY_LAST_SEEN)
    if not last_seen_str:
        return None

    try:
        last_seen = datetime.fromisoformat(last_seen_str)
    except (ValueError, TypeError):
        logger.warning("last_seen の解析に失敗しました: %s", last_seen_str)
        return None

    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    expires_at = last_seen + timedelta(days=30)
    now = datetime.now(timezone.utc)
    remaining = (expires_at - now).total_seconds()

    return {
        "last_seen": last_seen,
        "expires_at": expires_at,
        "remaining_seconds": max(0, int(remaining)),
        "is_expired": remaining <= 0,
    }


# ──────────────────────────────────────────
# 内部ヘルパー
# ──────────────────────────────────────────

def _now_iso() -> str:
    """現在時刻を ISO 8601 形式の文字列で返す（UTC）。"""
    return datetime.now(timezone.utc).isoformat()
