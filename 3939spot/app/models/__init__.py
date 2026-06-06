"""
SQLAlchemy モデルパッケージ。
db インスタンスは app/__init__.py で初期化され、ここから再エクスポートする。

使い方:
    from app.models import db, User, Spot, Coupon, Session, PartnerApplication, AdminUser, AdTruckLocation
"""

from app import db
from app.models.user import User
from app.models.spot import Spot
from app.models.coupon import Coupon
from app.models.admin_user import AdminUser
from app.models.session import Session
from app.models.partner_application import PartnerApplication
from app.models.ad_truck_location import AdTruckLocation

__all__ = [
    "db",
    "User",
    "Spot",
    "Coupon",
    "AdminUser",
    "Session",
    "PartnerApplication",
    "AdTruckLocation",
]
