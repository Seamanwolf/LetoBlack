from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.routes.auth import redirect_based_on_role

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Главная страница"""
    if current_user.is_authenticated:
        return redirect_based_on_role(current_user)
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Панель управления"""
    return redirect_based_on_role(current_user) 