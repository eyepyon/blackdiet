"""
PartnerApplication モデル（`partner_applications` テーブル）。

提携店申し込みを管理する。status は 'pending' | 'approved' | 'rejected' に制限する。
UUIDType は user.py で定義したカスタム TypeDecorator を再利用する。
"""

from uuid import uuid4

from sqlalchemy import CheckConstraint, func

from app import db
from app.models.user import UUIDType


class PartnerApplication(db.Model):
    """提携店申し込みを表すモデル。"""

    __tablename__ = "partner_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_partner_applications_status",
        ),
    )

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid4,
    )
    shop_name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text, nullable=False)
    contact_name = db.Column(db.String(255), nullable=False)
    contact_email = db.Column(db.String(255), nullable=False)
    wifi_info = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending")
    # status: 'pending' | 'approved' | 'rejected'
    submitted_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
    )
    reviewed_at = db.Column(db.DateTime(timezone=True))
    reviewer_id = db.Column(
        UUIDType,
        db.ForeignKey("admin_users.id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PartnerApplication id={self.id} shop_name={self.shop_name!r} "
            f"status={self.status!r}>"
        )

    def to_dict(self) -> dict:
        """JSON シリアライズ可能な辞書を返す。"""
        return {
            "id": str(self.id) if self.id is not None else None,
            "shop_name": self.shop_name,
            "address": self.address,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "wifi_info": self.wifi_info,
            "status": self.status,
            "submitted_at": (
                self.submitted_at.isoformat()
                if self.submitted_at is not None
                else None
            ),
            "reviewed_at": (
                self.reviewed_at.isoformat()
                if self.reviewed_at is not None
                else None
            ),
            "reviewer_id": (
                str(self.reviewer_id) if self.reviewer_id is not None else None
            ),
        }
