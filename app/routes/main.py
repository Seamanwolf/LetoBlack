from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Главная страница сайта"""
    # Если пользователь авторизован, перенаправляем на соответствующую панель
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.admin_dashboard'))
        elif current_user.role == 'leader':
            return redirect(url_for('admin_routes.personnel'))
        elif current_user.role == 'user':
            # Пользователи с ролью 'user' перенаправляются на страницу ВАТС
            return redirect('/vats')
        else:
            return redirect(url_for('admin_routes.personnel'))
    
    # Для неавторизованных пользователей показываем главную страницу
    return redirect(url_for('auth.login')) 