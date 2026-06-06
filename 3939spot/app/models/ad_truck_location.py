"""
AdTruckLocation モデル（`ad_truck_locations` テーブル）。

ADトラックの現在位置情報を管理する。
UUIDType は user.py で定義したカスタム TypeDecorator を再利用する。
"""

from uuid import uuid4

from sqlalchemy import func

from app import db
from app.models.user import UUIDType


class AdTruckLocation(db.Model):
    """ADトラックの位置情報を表すモデル。"""

    __tablename__ = "ad_truck_locations"

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid4,
    )
    spot_id = db.Column(
        UUIDType,
        db.ForeignKey("spots.id"),
        nullable=False,
    )
    area = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_by = db.Column(
        UUIDType,
        db.ForeignKey("admin_users.id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AdTruckLocation id={self.id} spot_id={self.spot_id} "
            f"area={self.area!r}>"
        )

    def to_dict(self) -> dict:
        """JSON シリアライズ可能な辞書を返す。"""
        return {
            "id": str(self.id) if self.id is not None else None,
            "spot_id": str(self.spot_id) if self.spot_id is not None else None,
            "area": self.area,
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at is not None else None
            ),
            "updated_by": (
                str(self.updated_by) if self.updated_by is not None else None
            ),
        }
