from flask import Blueprint, render_template
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.models.location import Location
from app.utils import create_db_connection

admin_routes_bp = Blueprint('admin_routes_unique', __name__, url_prefix='/admin')

@admin_routes_bp.route('/')
def index():
    # Получаем количество записей для каждой сущности через соединение с БД
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Подсчет пользователей
        cursor.execute("SELECT COUNT(*) as count FROM User")
        user_count = cursor.fetchone()['count']
        
        # Подсчет ролей
        cursor.execute("SELECT COUNT(*) as count FROM Role")
        role_count = cursor.fetchone()['count']
        
        # Подсчет отделов
        cursor.execute("SELECT COUNT(*) as count FROM Department")
        department_count = cursor.fetchone()['count']
        
        # Подсчет локаций
        cursor.execute("SELECT COUNT(*) as count FROM Location")
        location_count = cursor.fetchone()['count']
        
        # Здесь можно добавить логику получения последних действий
        cursor.execute("""
            SELECT a.*, u.full_name 
            FROM UserActivity a
            JOIN User u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT 10
        """)
        recent_actions = cursor.fetchall()
        
        return render_template('admin/index.html',
                             user_count=user_count,
                             role_count=role_count,
                             department_count=department_count,
                             location_count=location_count,
                             recent_actions=recent_actions)
    except Exception as e:
        return render_template('admin/index.html',
                             user_count=0,
                             role_count=0,
                             department_count=0,
                             location_count=0,
                             recent_actions=[],
                             error_message=str(e))
    finally:
        cursor.close()
        connection.close()

# Импортируем модули после создания Blueprint
from app.routes.admin import roles, personnel, dashboard 