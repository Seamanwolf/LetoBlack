from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes.auth import redirect_based_on_role
from app.models.user import User
from app.models.action import Action
from app import db

admin_dashboard_bp = Blueprint('admin_dashboard', __name__)

@admin_dashboard_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Панель управления администратора"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'error')
        return redirect_based_on_role(current_user)
    
    try:
        # Получаем статистику
        connection = None
        cursor = None
        try:
            from app.utils import create_db_connection
            connection = create_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            # Получаем количество пользователей
            cursor.execute("SELECT COUNT(*) as users_count FROM User")
            users_data = cursor.fetchone()
            users_count = users_data['users_count'] if users_data else 0
            
            # Получаем количество онлайн пользователей
            cursor.execute("SELECT COUNT(*) as online_count FROM User WHERE status = 'Онлайн'")
            online_data = cursor.fetchone()
            online_users = online_data['online_count'] if online_data else 0
            
            # Получаем последние действия
            cursor.execute("""
                SELECT u.full_name, a.action_type, a.created_at
                FROM UserActivity a
                JOIN User u ON a.user_id = u.id
                ORDER BY a.created_at DESC
                LIMIT 10
            """)
            recent_actions = cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        
        return render_template('admin/dashboard.html',
                             users_count=users_count,
                             online_users=online_users,
                             recent_actions=recent_actions)
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'error')
        return redirect_based_on_role(current_user) 