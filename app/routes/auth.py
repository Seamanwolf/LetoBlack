from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash
from app.utils import create_db_connection
from app.models.user import User
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему"""
    # Если пользователь уже авторизован, перенаправляем на главную
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Проверяем данные пользователя
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM User WHERE login = %s", (username,))
            user_data = cursor.fetchone()
            
            if user_data and check_password_hash(user_data['password'], password):
                # Создаем объект пользователя
                user = User(
                    id=user_data['id'],
                    login=user_data['login'],
                    password=user_data['password'],
                    full_name=user_data['full_name'],
                    role=user_data['role']
                )
                
                # Авторизуем пользователя
                login_user(user)
                
                # Сохраняем дополнительные данные в сессии
                session['username'] = user_data['login']
                session['id'] = user_data['id']
                session['role'] = user_data['role']
                session['full_name'] = user_data['full_name']
                session['department'] = user_data.get('department')
                
                # Обновляем статус пользователя на "online"
                cursor.execute("UPDATE User SET status = 'Онлайн' WHERE id = %s", (user_data['id'],))
                connection.commit()
                
                # Перенаправляем пользователя на соответствующую страницу
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('main.index'))
            else:
                flash('Неверное имя пользователя или пароль', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    if current_user.is_authenticated:
        # Обновляем статус пользователя на "offline"
        connection = create_db_connection()
        cursor = connection.cursor()
        
        try:
            cursor.execute("UPDATE User SET status = 'offline' WHERE id = %s", (current_user.id,))
            connection.commit()
        finally:
            cursor.close()
            connection.close()
    
    logout_user()
    session.clear()
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('auth.login')) 