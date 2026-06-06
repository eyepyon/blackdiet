"""
Coupon_System サービス層。

Redis不要。SQLiteへの直接クエリで1日1枚制限を実現する。

issue_coupon(user_id, spot_id) → Coupon | None
- JST日付でその日のCouponレコードを検索（DBクエリ）
- 未取得なら新規Couponを保存して返す
- 既取得なら None を返す（ALREADY_ISSUED）
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from app import db
from app.models.coupon import Coupon

logger = logging.getLogger(__name__)

# 日本標準時 UTC+9
JST = timezone(timedelta(hours=9))


# ──────────────────────────────────────────
# JST ユーティリティ
# ──────────────────────────────────────────

def get_jst_date() -> str:
    """日本標準時の現在日付を 'YYYY-MM-DD' 形式で返す。"""
    return datetime.now(JST).strftime("%Y-%m-%d")


def get_jst_day_range() -> tuple[datetime, datetime]:
    """
    現在のJST日（00:00:00〜23:59:59）をUTCのdatetimeペアで返す。

    SQLiteはタイムゾーン非対応のため、JST日の開始・終了をUTCに変換して
    範囲クエリに使用する。

    Returns:
        (day_start_utc, day_end_utc): UTC基準のdatetimeタプル
    """
    now_jst = datetime.now(JST)
    # JST当日の 00:00:00
    day_start_jst = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    # JST当日の 23:59:59.999999
    day_end_jst = now_jst.replace(hour=23, minute=59, second=59, microsecond=999999)
    # UTC に変換（SQLiteストレージ形式に合わせる）
    return day_start_jst.astimezone(timezone.utc), day_end_jst.astimezone(timezone.utc)


def ttl_until_midnight_jst() -> int:
    """JST翌日00:00までの残り秒数を返す。（互換性のため残存）"""
    now_jst = datetime.now(JST)
    tomorrow_midnight = (now_jst + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(int((tomorrow_midnight - now_jst).total_seconds()), 1)


# ──────────────────────────────────────────
# 重複チェック（SQLiteクエリ）
# ──────────────────────────────────────────

def _already_issued_today(user_id: str, spot_id: str) -> bool:
    """
    同日同スポットで既に交換券を取得済みかどうかをSQLiteに直接問い合わせる。

    issued_at をJST日付の範囲（UTC変換後）でフィルタリングする。
    SQLiteはNaive datetimeで保存するため、UTC範囲クエリで対応する。

    Args:
        user_id: ユーザーUUID文字列
        spot_id: スポットUUID文字列

    Returns:
        True: 当日取得済み / False: 未取得
    """
    day_start, day_end = get_jst_day_range()

    # SQLiteのNaive datetime（UTC保存）に合わせて比較
    # issued_at は server_default=func.now() でUTC naive として保存される
    existing = Coupon.query.filter(
        Coupon.user_id == user_id,
        Coupon.spot_id == spot_id,
        Coupon.issued_at >= day_start.replace(tzinfo=None),
        Coupon.issued_at <= day_end.replace(tzinfo=None),
    ).first()

    return existing is not None


# ──────────────────────────────────────────
# 交換券発行ロジック
# ──────────────────────────────────────────

def issue_coupon(user_id: str, spot_id: str) -> "Coupon | None":
    """
    交換券を発行する。Redis不要のSQLite版。

    1日1枚制限はSQLiteへの直接クエリで実現する。
    同日同スポットで既に発行済みの場合は None を返す（ALREADY_ISSUED）。

    Args:
        user_id: ユーザーの UUID 文字列。
        spot_id: スポットの UUID 文字列。

    Returns:
        新規発行された Coupon オブジェクト、または None（既発行の場合）。
    """
    # ── 重複チェック（DBクエリ） ─────────────
    if _already_issued_today(user_id, spot_id):
        logger.debug(
            "交換券取得済み（当日）: user_id=%s spot_id=%s date=%s",
            user_id, spot_id, get_jst_date(),
        )
        return None  # ALREADY_ISSUED

    # ── 新規発行 ────────────────────────────
    coupon = Coupon(
        user_id=user_id,
        spot_id=spot_id,
        coupon_code=secrets.token_urlsafe(48),
        expires_at=datetime.now(JST) + timedelta(days=30),
    )
    db.session.add(coupon)
    db.session.commit()

    logger.info(
        "交換券発行: user_id=%s spot_id=%s coupon_id=%s",
        user_id, spot_id, coupon.id,
    )
    return coupon
