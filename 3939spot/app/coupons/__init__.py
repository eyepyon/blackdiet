from flask import Blueprint

# REST API用Blueprint
coupons_api_bp = Blueprint("coupons_api", __name__)

# SSRページ用Blueprint（/coupon prefix）
coupons_page_bp = Blueprint("coupons_page", __name__)

from app.coupons import routes  # noqa: E402, F401
