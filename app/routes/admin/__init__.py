from flask import Blueprint, render_template
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.models.location import Location

admin_routes_bp = Blueprint('admin_routes', __name__, url_prefix='/admin')

@admin_routes_bp.route('/')
def index():
    # Получаем количество записей для каждой сущности
    user_count = User.count()
    role_count = Role.count()
    department_count = Department.count()
    location_count = Location.count()
    
    # Здесь можно добавить логику получения последних действий
    recent_actions = []
    
    return render_template('admin/index.html',
                         user_count=user_count,
                         role_count=role_count,
                         department_count=department_count,
                         location_count=location_count,
                         recent_actions=recent_actions)

# Импортируем модули после создания Blueprint
from app.routes.admin import roles, personnel, dashboard 