from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash
from app.utils import create_db_connection, update_operator_status
from app.models.user import User
from datetime import datetime
from os import path
import time
import traceback

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему"""
    # Если пользователь уже авторизован, перенаправляем на соответствующую страницу
    if current_user.is_authenticated:
        return redirect_based_on_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Введите имя пользователя и пароль', 'danger')
            return redirect(url_for('auth.login'))
        
        # Проверяем данные пользователя
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT u.*, ur.role_id, r.name as role_name 
                FROM User u 
                LEFT JOIN UserRole ur ON u.id = ur.user_id 
                LEFT JOIN Role r ON ur.role_id = r.id 
                WHERE u.login = %s
            """, (username,))
            user_data = cursor.fetchone()
            
            if user_data and check_password_hash(user_data['password'], password):
                # Создаем объект пользователя
                user = User(
                    id=user_data['id'],
                    login=user_data['login'],
                    password=user_data['password'],
                    full_name=user_data['full_name'],
                    role=user_data['role_name'] or user_data['role']  # Используем role_name из Role или старый role
                )
                
                # Авторизуем пользователя
                login_user(user)
                
                # Сохраняем данные в сессии
                session['username'] = user_data['login']
                session['id'] = user_data['id']
                session['role'] = user_data['role_name'] or user_data['role']
                session['full_name'] = user_data['full_name']
                session['department'] = user_data.get('department')
                session['ukc_kc'] = user_data.get('ukc_kc')
                session.permanent = True
                
                # Обновляем статус пользователя
                cursor.execute("UPDATE User SET status = 'Онлайн' WHERE id = %s", (user_data['id'],))
                connection.commit()
                
                # Если есть next параметр, используем его
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                
                # Иначе перенаправляем на основе роли
                return redirect_based_on_role(user)
            else:
                flash('Неверное имя пользователя или пароль', 'danger')
        except Exception as e:
            current_app.logger.error(f"Ошибка при аутентификации: {e}")
            traceback.print_exc()
            flash('Произошла ошибка при входе в систему', 'danger')
        finally:
            cursor.close()
            connection.close()
    
    # Проверяем наличие логотипа
    logo_png_path = path.join(current_app.static_folder, 'images/logo.png')
    logo_bmp_path = path.join(current_app.static_folder, 'images/logo.bmp')
    
    logo_exists = path.exists(logo_png_path)
    logo_url = url_for('static', filename='images/logo.png')
    
    if not logo_exists and path.exists(logo_bmp_path):
        logo_exists = True
        logo_url = url_for('static', filename='images/logo.bmp')
    
    # Добавляем метку времени для предотвращения кеширования
    now = int(time.time())
    
    return render_template('auth/login.html', logo_url=logo_url if logo_exists else None, now=now)

def redirect_based_on_role(user):
    """Перенаправляет пользователя на соответствующую страницу на основе его роли"""
    if user.role == 'operator':
        session['login_time'] = datetime.now()
        update_operator_status(user.id, 'Онлайн')
        return redirect(url_for('callcenter.operator_dashboard'))
    elif user.role == 'admin':
        return redirect(url_for('admin_routes_unique.index'))
    elif user.role == 'leader':
        return redirect(url_for('leader.leader_dashboard'))
    elif user.role == 'backoffice':
        department = user.department if hasattr(user, 'department') else None
        if department == 'HR':
            return redirect(url_for('hr.candidates_list'))
        elif department == 'Ресепшн':
            return redirect(url_for('reception.reception_dashboard'))
        else:
            return redirect('/vats')
    elif user.role == 'user':
        return redirect('/vats')
    else:
        return redirect(url_for('main.index'))

@auth_bp.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    # Обновляем статус пользователя на "Офлайн"
    if current_user.is_authenticated:
        connection = create_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("UPDATE User SET status = 'Офлайн' WHERE id = %s", (current_user.id,))
            connection.commit()
        finally:
            cursor.close()
            connection.close()
    
    # Очищаем сессию
    session.clear()
    logout_user()
    
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('auth.login')) 