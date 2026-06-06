"""
Spot モデル（`spots` テーブル）。

スポット種別は 'ad_truck' | 'ship_truck' | 'store' | 'raspi' の4種類に限定。
UUIDType は user.py で定義したカスタム TypeDecorator を再利用する。
"""

from uuid import uuid4
from decimal import Decimal

from sqlalchemy import CheckConstraint, func

from app import db
from app.models.user import UUIDType


# ──────────────────────────────────────────
# Spot モデル
# ──────────────────────────────────────────

VALID_SPOT_TYPES = ("ad_truck", "ship_truck", "store", "raspi")


class Spot(db.Model):
    """WiFiスポット・ADトラック・出荷トラック・RasPiルーターを表すモデル。"""

    __tablename__ = "spots"
    __table_args__ = (
        CheckConstraint(
            "spot_type IN ('ad_truck', 'ship_truck', 'store', 'raspi')",
            name="ck_spots_spot_type",
        ),
    )

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid4,
    )
    name = db.Column(db.String(255), nullable=False)
    spot_type = db.Column(db.String(20), nullable=False)
    # spot_type: 'ad_truck' | 'ship_truck' | 'store' | 'raspi'
    ssid = db.Column(db.String(100))
    ap_mac = db.Column(db.String(17))
    address = db.Column(db.Text)
    area = db.Column(db.String(100))
    latitude = db.Column(db.Numeric(9, 6))
    longitude = db.Column(db.Numeric(9, 6))
    business_hours = db.Column(db.Text)
    wifi_info = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    qr_token = db.Column(db.String(100), unique=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<Spot id={self.id} name={self.name!r} "
            f"spot_type={self.spot_type!r} is_active={self.is_active}>"
        )

    def to_dict(self) -> dict:
        """JSON シリアライズ可能な辞書を返す。"""
        return {
            "id": str(self.id) if self.id is not None else None,
            "name": self.name,
            "spot_type": self.spot_type,
            "ssid": self.ssid,
            "ap_mac": self.ap_mac,
            "address": self.address,
            "area": self.area,
            "latitude": (
                float(self.latitude) if self.latitude is not None else None
            ),
            "longitude": (
                float(self.longitude) if self.longitude is not None else None
            ),
            "business_hours": self.business_hours,
            "wifi_info": self.wifi_info,
            "is_active": self.is_active,
            "qr_token": self.qr_token,
            "created_at": (
                self.created_at.isoformat() if self.created_at is not None else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at is not None else None
            ),
        }
