from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.routes.auth import redirect_based_on_role

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Главная страница"""
    # Если пользователь авторизован, перенаправляем на соответствующую страницу
    if current_user.is_authenticated:
        # Прямое перенаправление по ролям для избежания циклического редиректа
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard.admin_dashboard'))
        elif current_user.role == 'leader':
            return redirect(url_for('leader.leader_dashboard'))
        elif current_user.role == 'operator':
            return redirect(url_for('callcenter.operator_dashboard'))
        elif current_user.role == 'user':
            return redirect('/vats')
        elif current_user.role == 'backoffice':
            return redirect('/vats')
    
    # Если пользователь не авторизован, перенаправляем на страницу входа
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Общая страница дашборда, определяет куда перенаправить пользователя"""
    # Прямое перенаправление по ролям
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard.admin_dashboard'))
    elif current_user.role == 'leader':
        return redirect(url_for('leader.leader_dashboard'))
    elif current_user.role == 'operator':
        return redirect(url_for('callcenter.operator_dashboard'))
    elif current_user.role == 'user':
        return redirect('/vats')
    elif current_user.role == 'backoffice':
        return redirect('/vats')
    else:
        return redirect(url_for('auth.login')) 