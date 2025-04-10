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
    
            # Определение доступных модулей для пользователя через RolePermission
            redirect_url = None
            
            try:
                connection = create_db_connection()
                if connection:
                    with connection.cursor(dictionary=True) as cursor:
                        # Проверяем наличие разрешений на основе роли пользователя в таблице UserRole
                        cursor.execute("""
                            SELECT m.name, m.url_path, rp.can_view 
                            FROM Module m
                            JOIN RolePermission rp ON m.id = rp.module_id
                            JOIN UserRole ur ON rp.role_id = ur.role_id
                            WHERE ur.user_id = %s AND rp.can_view = 1
                            ORDER BY m.order ASC
                        """, (user.id,))
                        
                        modules = cursor.fetchall()
                        
                        if modules:
                            # Логируем доступные модули
                            current_app.logger.info(f"Доступные модули для пользователя {user.id}: {[m['name'] for m in modules]}")
                            
                            # Используем первый доступный модуль для перенаправления
                            for module in modules:
                                if module['url_path']:
                                    redirect_url = f"/{module['url_path']}"
                                    current_app.logger.info(f"Перенаправление на модуль: {module['name']} ({redirect_url})")
                                    break
            except Exception as e:
                current_app.logger.error(f"Ошибка при определении доступных модулей: {e}")
                traceback.print_exc()
            
            # Если не нашли доступных модулей через RolePermission, используем стандартную логику
            if not redirect_url:
                current_app.logger.warning(f"Не найдены доступные модули через RolePermission, используем стандартное перенаправление")
                
                if user.role == 'operator':
                    session['login_time'] = datetime.now()
                    update_operator_status(user.id, 'Онлайн')
                    redirect_url = url_for('callcenter.operator_dashboard')
                elif user.role == 'admin':
                    redirect_url = url_for('admin.admin_dashboard')
                    current_app.logger.info(f"User is admin, redirecting to {redirect_url}")
                elif user.role == 'leader':
                    redirect_url = url_for('leader.leader_dashboard')
                elif user.role == 'user':
                    # Для тестовой роли "user" проверяем доступ к модулям ВАТС и Колл-центр
                    ватс_url = "/vats"  # согласно данным из базы для модуля ВАТС (id=11)
                    callcenter_url = "/vats"  # согласно данным из базы для модуля Колл-центр (id=6)
                    
                    # Сначала проверяем доступ к Колл-центру
                    if modules and any(m['name'] == 'Колл-центр' for m in modules):
                        redirect_url = callcenter_url
                    # Затем к ВАТС
                    elif modules and any(m['name'] == 'ВАТС' for m in modules):
                        redirect_url = ватс_url
                    else:
                        # Если доступа к нужным модулям нет, отправляем на страницу без доступа
                        flash("У вас нет доступа к системе. Обратитесь к администратору.", "danger")
                        return redirect(url_for('auth.login'))
                elif user.role == 'backoffice':
                    # Получаем department из данных пользователя
                    user_department = user_data.get('department')
                    
                    if user_department == 'HR':
                        redirect_url = url_for('hr.candidates_list')
                    elif user_department == 'Ресепшн':
                        redirect_url = url_for('reception.reception_dashboard')
                    else:
                        # Для бэкофиса без определенного департамента смотрим доступные модули
                        ватс_url = "/vats"
                        callcenter_url = "/vats"
                        
                        # Проверяем доступ к модулям через RolePermission
                        if modules and any(m['name'] == 'Колл-центр' for m in modules):
                            redirect_url = callcenter_url
                        elif modules and any(m['name'] == 'ВАТС' for m in modules):
                            redirect_url = ватс_url
                        else:
                            redirect_url = url_for('main.index')  # На главную, если нет доступа к специфическим модулям
                else:
                    redirect_url = url_for('userlist.dashboard')
                    
            current_app.logger.info(f"Redirecting to {redirect_url}")
            if redirect_url:
                return redirect(redirect_url)
            else:
                flash("У вас нет доступа к системе. Обратитесь к администратору.", "danger")
                return redirect(url_for('auth.login'))
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

