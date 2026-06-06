"""
Coupon モデル（`coupons` テーブル）。

unique_daily_spot 制約は PostgreSQL の date_trunc・timezone 関数を使った
式インデックスに依存するため、SQLite（テスト環境）では関数式なしの
UniqueConstraint(user_id, spot_id) をフォールバックとして使用する。
JST 日付ベースの1日1枚制限はアプリ層（Coupon_System）で制御する。
"""

from uuid import uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint, func, event
from sqlalchemy.engine import Engine

from app import db
from app.models.user import UUIDType


# ──────────────────────────────────────────
# Coupon モデル
# ──────────────────────────────────────────

def _build_table_args(dialect_name: str) -> tuple:
    """
    ダイアレクトに応じた __table_args__ を生成する。

    - PostgreSQL: date_trunc + timezone 関数を用いた式ベースの UniqueConstraint
    - SQLite（他）: シンプルな UniqueConstraint(user_id, spot_id) にフォールバック
                    JST 日付の重複制御はアプリ層で補完する。
    """
    check = CheckConstraint(
        "status IN ('active', 'used', 'expired')",
        name="ck_coupons_status",
    )
    if dialect_name == "postgresql":
        from sqlalchemy import cast
        from sqlalchemy.types import Date
        unique = UniqueConstraint(
            "user_id",
            "spot_id",
            func.date_trunc("day", cast(func.timezone("Asia/Tokyo", "issued_at"), Date)),
            name="unique_daily_spot",
        )
    else:
        # SQLite など: 関数式インデックス非対応のため (user_id, spot_id) のみ
        unique = UniqueConstraint(
            "user_id",
            "spot_id",
            name="unique_daily_spot",
        )
    return (unique, check)


class Coupon(db.Model):
    """交換券を表すモデル。"""

    __tablename__ = "coupons"

    # __table_args__ はクラス定義時点では dialect が不明なため、
    # 遅延評価ロジックを使う。テーブル作成前に _resolve_table_args() で確定する。
    __table_args__ = (
        # デフォルトは SQLite フォールバック（テーブル作成前に上書きされる）
        UniqueConstraint("user_id", "spot_id", name="unique_daily_spot"),
        CheckConstraint(
            "status IN ('active', 'used', 'expired')",
            name="ck_coupons_status",
        ),
    )

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid4,
    )
    user_id = db.Column(
        UUIDType,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    spot_id = db.Column(
        UUIDType,
        db.ForeignKey("spots.id"),
        nullable=False,
    )
    coupon_code = db.Column(db.String(64), unique=True, nullable=False)
    issued_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    used_spot_id = db.Column(
        UUIDType,
        db.ForeignKey("spots.id"),
    )
    status = db.Column(db.String(20), default="active")
    # status: 'active' | 'used' | 'expired'
    expiry_notified = db.Column(db.Boolean, default=False)

    def __repr__(self) -> str:
        return (
            f"<Coupon id={self.id} coupon_code={self.coupon_code!r} "
            f"status={self.status!r} user_id={self.user_id}>"
        )

    def to_dict(self) -> dict:
        """JSON シリアライズ可能な辞書を返す。"""
        return {
            "id": str(self.id) if self.id is not None else None,
            "user_id": str(self.user_id) if self.user_id is not None else None,
            "spot_id": str(self.spot_id) if self.spot_id is not None else None,
            "coupon_code": self.coupon_code,
            "issued_at": (
                self.issued_at.isoformat() if self.issued_at is not None else None
            ),
            "expires_at": (
                self.expires_at.isoformat() if self.expires_at is not None else None
            ),
            "used_at": (
                self.used_at.isoformat() if self.used_at is not None else None
            ),
            "used_spot_id": (
                str(self.used_spot_id) if self.used_spot_id is not None else None
            ),
            "status": self.status,
            "expiry_notified": self.expiry_notified,
        }
