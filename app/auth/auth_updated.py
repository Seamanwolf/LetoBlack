from flask import render_template, request, redirect, url_for, flash, session, current_app
from app.auth import auth_bp
from app.utils import create_db_connection, login_required
from datetime import datetime
from flask_login import login_user
from app.models import User
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import traceback

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        current_app.logger.info(f"Attempting to authenticate user: {username}")
        
        user_data = authenticate_user(username, password)
        
        if user_data:
            current_app.logger.info("User authenticated successfully.")
            current_app.logger.debug(f"User data: {user_data}")
            
            user = User(**user_data)
            login_user(user)
            
            # Установка дополнительных данных в сессию
            session['id'] = user.id
            session['department'] = user_data.get('department')
            session['role'] = user_data.get('role')
            session['ukc_kc'] = user_data.get('ukc_kc')
            session.permanent = True
            
            # Обновляем статус активности пользователя
            update_user_activity(user.id, 'online')
            
            # Перенаправление пользователя по роли
            if user.role == 'operator':
                session['login_time'] = datetime.now()
                return redirect(url_for('callcenter.operator_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
            elif user.role == 'leader':
                return redirect(url_for('leader.leader_dashboard'))
            elif user.role == 'backoffice' and user.department == 'Ресепшн':
                return redirect(url_for('reception.reception_dashboard'))
            elif user.role == 'backoffice' and user.department == 'HR':
                return redirect(url_for('hr.candidates_list'))
            else:
                return redirect(url_for('main.dashboard'))
        else:
            current_app.logger.warning("Authentication failed.")
            flash("Неверный логин или пароль", "danger")
            return redirect(url_for('auth.login'))
    
    return render_template('login.html')

def update_user_activity(user_id, status):
    """
    Обновляет статус активности пользователя
    """
    connection = create_db_connection()
    if connection is None:
        current_app.logger.error("Нет подключения к базе данных для обновления статуса.")
        return

    cursor = None
    try:
        cursor = connection.cursor()
        
        # Проверяем, есть ли уже запись для пользователя
        cursor.execute("SELECT id FROM UserActivity WHERE user_id = %s", (user_id,))
        activity = cursor.fetchone()
        
        if activity:
            # Обновляем существующую запись
            cursor.execute(
                "UPDATE UserActivity SET status = %s, last_activity = NOW(), updated_at = NOW() WHERE user_id = %s", 
                (status, user_id)
            )
        else:
            # Создаем новую запись
            cursor.execute(
                "INSERT INTO UserActivity (user_id, status, last_activity) VALUES (%s, %s, NOW())", 
                (user_id, status)
            )
        
        connection.commit()
        current_app.logger.info(f"Статус пользователя с ID {user_id} обновлён на {status}.")
        
        # Дополнительно для операторов колл-центра
        cursor.execute("""
            SELECT r.name AS role, c.ukc_kc 
            FROM User u 
            JOIN Roles r ON u.role_id = r.id
            LEFT JOIN CallCenterSettings c ON u.id = c.user_id
            WHERE u.id = %s
        """, (user_id,))
        
        user_info = cursor.fetchone()
        if user_info and user_info[0] == 'operator' and user_info[1]:
            current_app.logger.info(f"Оператор колл-центра {user_id} ({user_info[1]}) обновил статус на {status}.")
    
    except Exception as err:
        connection.rollback()
        current_app.logger.error(f"Ошибка при обновлении статуса пользователя: {err}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def authenticate_user(username, password):
    """
    Аутентифицирует пользователя по логину и паролю
    """
    current_app.logger.info(f"Attempting to authenticate user: {username}")
    
    connection = create_db_connection()
    if connection is None:
        current_app.logger.error("Нет подключения к базе данных для аутентификации.")
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Запрос с использованием представления UserFullView или объединения таблиц
        query = """
        SELECT 
            u.id, 
            u.login, 
            u.full_name, 
            r.name AS role, 
            c.ukc_kc, 
            u.department, 
            u.password 
        FROM User u
        JOIN Roles r ON u.role_id = r.id
        LEFT JOIN CallCenterSettings c ON u.id = c.user_id
        WHERE u.login = %s AND u.fired = FALSE
        """
        
        cursor.execute(query, (username,))
        
        user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            user.pop('password', None)  # Удалить пароль из данных пользователя
            return user  # Возвращаем полный словарь с данными пользователя
        return None
    except Exception as err:
        current_app.logger.error(f"Ошибка при аутентификации пользователя: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close() 