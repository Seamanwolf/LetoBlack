from flask import Blueprint

admin_routes_bp = Blueprint('admin_routes', __name__)

from app.routes.admin import roles, personnel, dashboard 