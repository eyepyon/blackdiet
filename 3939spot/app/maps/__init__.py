from flask import Blueprint

# REST API用Blueprint
maps_api_bp = Blueprint("maps_api", __name__)

# SSRマップページ用Blueprint（/map prefix）
maps_page_bp = Blueprint("maps_page", __name__)

from app.maps import routes  # noqa: E402, F401
