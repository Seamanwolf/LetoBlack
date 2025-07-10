from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.utils import show_toast

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Главная страница - перенаправляет на логин"""
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Дашборд для обычных пользователей"""
    return render_template('dashboard.html')

# Тестовый маршрут удален

 