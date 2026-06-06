"""
Coupon モデル（`coupons` テーブル）。

DBはSQLiteを使用。1日1枚制限（JST日付）はアプリ層（Coupon_System / Redis）で制御する。
DB制約はシンプルな (user_id, spot_id) UniqueConstraintとstatusのCheckConstraintのみ。
"""

from uuid import uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint, func

from app import db
from app.models.user import UUIDType


class Coupon(db.Model):
    """交換券を表すモデル。"""

    __tablename__ = "coupons"
    __table_args__ = (
        # 1日1枚制限はRedisとアプリ層で担保。DB制約はユーザー×スポットの重複防止のみ。
        UniqueConstraint("user_id", "spot_id", name="unique_user_spot"),
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
