from flask import render_template, request, redirect, url_for, flash, session, current_app
from app.auth import auth_bp
from app.utils import authenticate_user, update_operator_status, login_required
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
        
        print(f"INFO: Attempting to authenticate user: {username}")  # Логирование попытки логина
        current_app.logger.info(f"Attempting to authenticate user: {username}")
        
        user_data = authenticate_user(username, password)
        
        if user_data:
            print("INFO: User authenticated successfully.")  # Логирование успешной аутентификации
            print(f"DEBUG: User data: {user_data}")  # Логирование данных пользователя
            current_app.logger.info("User authenticated successfully.")
            current_app.logger.debug(f"User data: {user_data}")
            
            # Создаем объект User для Flask-Login
            user = User(**user_data)
            
            # Явно логиним пользователя с помощью Flask-Login
            login_success = login_user(user)
            current_app.logger.debug(f"Flask-Login login_user() result: {login_success}")
            
            # Установка дополнительных данных в сессию, если необходимо
            session['logged_in'] = True
            session['id'] = user.id
            session['department'] = user_data.get('department')
            session['role'] = user_data.get('role')
            session['ukc_kc'] = user_data.get('ukc_kc')
            session.permanent = True
            
            # Логирование данных сессии
            print(f"INFO: Session ID: {session.get('id')}")
            print(f"INFO: Session Department: {session.get('department')}")
            print(f"INFO: Session Role: {session.get('role')}")
            print(f"INFO: Session UKC_KC: {session.get('ukc_kc')}")
            current_app.logger.info(f"Session data: ID={session.get('id')}, Department={session.get('department')}, Role={session.get('role')}")
    
            # Перенаправление пользователя по роли
            redirect_url = url_for('userlist.dashboard')  # Значение по умолчанию
            
            if user.role == 'operator':
                session['login_time'] = datetime.now()
                update_operator_status(user.id, 'Онлайн')
                redirect_url = url_for('callcenter.operator_dashboard')
            elif user.role == 'admin':
                redirect_url = url_for('admin.admin_dashboard')
                current_app.logger.info(f"User is admin, redirecting to {redirect_url}")
            elif user.role == 'leader':
                redirect_url = url_for('leader.leader_dashboard')
            elif user.role == 'backoffice' and user.department == 'Ресепшн':
                redirect_url = url_for('reception.reception_dashboard')
            elif user.role == 'backoffice' and user.department == 'HR':
                redirect_url = url_for('hr.candidates_list')
                
            current_app.logger.info(f"Redirecting to {redirect_url}")
            return redirect(redirect_url)
        else:
            print("WARNING: Authentication failed.")  # Логирование неудачной аутентификации
            current_app.logger.warning("Authentication failed.")
            flash("Неверный логин или пароль", "danger")
            return redirect(url_for('auth.login'))
    
    return render_template('login.html')

def create_db_connection():
    try:
        connection = pymysql.connect(
            host='192.168.2.225',
            port=3306,
            user='test_user',
            password='password',
            database="Brokers"
        )
        return connection
    except pymysql.Error as err:
        current_app.logger.error(f"Ошибка подключения к базе данных на 192.168.2.225:3306: {err}")
        return None

def update_operator_status(operator_id, status):
    connection = create_db_connection()
    if connection is None:
        current_app.logger.error("Нет подключения к базе данных для обновления статуса оператора.")
        return

    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE User SET status = %s WHERE id = %s", (status, operator_id))
        connection.commit()
        current_app.logger.info(f"Статус оператора с ID {operator_id} обновлён на {status}.")
    except pymysql.Error as err:
        current_app.logger.error(f"Ошибка при обновлении статуса оператора: {err}")
    finally:
        cursor.close()
        connection.close()

def authenticate_user(username, password):
    """Аутентифицирует пользователя по логину и паролю"""
    current_app.logger.info(f"Attempting to authenticate user: {username}")
    
    connection = create_db_connection()
    if connection is None:
        current_app.logger.error("Нет подключения к базе данных для аутентификации.")
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        # Получаем данные пользователя без поля ukc_kc
        cursor.execute(
            "SELECT id, login, full_name, role, department, password "
            "FROM User WHERE login = %s AND fired = FALSE",
            (username,)
        )
        
        user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            user.pop('password', None)  # Удалить пароль из данных пользователя
            
            # Для ролей callcenter и admin получаем ukc_kc из отдельной таблицы
            if user['role'] in ['callcenter', 'admin']:
                try:
                    cursor.execute("SELECT ukc_kc FROM user_ukc WHERE user_id = %s", (user['id'],))
                    ukc_data = cursor.fetchone()
                    if ukc_data:
                        user['ukc_kc'] = ukc_data['ukc_kc']
                    else:
                        user['ukc_kc'] = 'УКЦ'  # Значение по умолчанию
                except Exception as e:
                    current_app.logger.error(f"Ошибка при получении ukc_kc: {e}")
                    user['ukc_kc'] = 'УКЦ'  # Значение по умолчанию
            
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

