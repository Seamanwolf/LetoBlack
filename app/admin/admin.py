from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory, abort, current_app
from app.admin import admin_bp
from app.utils import create_db_connection, login_required, get_department_weekly_stats, get_notifications_count
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_required as flask_login_required, current_user
import logging
from app.backoffice import add_backoffice_staff, update_backoffice_staff, delete_backoffice_staff, change_user_password
import os
import traceback
from datetime import datetime, date

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LOGO_PATH = '/home/LetoBlack/static/logo.bmp'

@admin_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))
    
    # Dummy data - replace this with actual database query results
    data = [
        {"department": "Sales", "deals_count": 150, "total_commission": 12000},
        {"department": "R&D", "deals_count": 80, "total_commission": 8000},
        {"department": "Marketing", "deals_count": 90, "total_commission": 5000}
    ]
    return render_template('admin_dashboard.html', data=data)

@admin_bp.route('/check_username', methods=['POST'])
@login_required
def check_username():
    username = request.form.get('username')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM User WHERE login = %s", (username,))
        user = cursor.fetchone()
        return jsonify({'exists': user is not None})
    except mysql.connector.Error as err:
        return jsonify({'exists': False, 'message': str(err)})
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/admin/admins')
@login_required
def show_admins():
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, login, full_name, department, Phone, hire_date FROM User WHERE role = 'admin'")
    admins = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('show_admins.html', admins=admins)

@admin_bp.route('/api/get_admin', methods=['GET'])
@login_required
def get_admin():
    admin_id = request.args.get('id')
    
    connection = create_db_connection()
    if not connection:
        return jsonify({'success': False, 'message': 'Ошибка подключения к базе данных'}), 500

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, login, full_name, Phone, department, hire_date FROM User WHERE id = %s AND role = 'admin'", (admin_id,))
        admin = cursor.fetchone()
        
        if not admin:
            logger.warning(f"Admin not found for ID: {admin_id}")
            return jsonify({'success': False, 'message': 'Администратор не найден'})
        
        logger.debug(f"Fetched admin data: {admin}")
        return jsonify({'success': True, **admin})
    except Exception as e:
        logger.error(f"Error fetching admin: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/save_ldap', methods=['POST'])
@login_required
def save_ldap():
    # Получение данных из формы
    domain = request.form.get('ldap-domain')
    controller_address = request.form.get('ldap-controller')
    username = request.form.get('ldap-username')
    password = request.form.get('ldap-password')

    # Сохранение данных (можно сохранить в базе данных или конфиге)
    ldap_settings['domain'] = domain
    ldap_settings['controller_address'] = controller_address
    ldap_settings['username'] = username
    ldap_settings['password'] = password

    flash('Настройки LDAP сохранены успешно.', 'success')
    return redirect(url_for('settings'))

@admin_bp.route('/upload_logo', methods=['POST'])
@login_required
def upload_logo():
    # Проверяем, есть ли файл в запросе
    if 'logo' not in request.files:
        flash('Нет файла для загрузки')
        return redirect(url_for('settings'))

    file = request.files['logo']

    # Проверяем, выбран ли файл
    if file.filename == '':
        flash('Файл не выбран')
        return redirect(url_for('settings'))

    # Проверяем, что файл имеет разрешение bmp
    if file and file.filename.endswith('.bmp'):
        file.save(LOGO_PATH)  # Сохраняем файл по указанному пути с именем logo.bmp
        flash('Логотип успешно загружен и сохранен как logo.bmp')
    else:
        flash('Неправильный формат файла. Загрузите файл с расширением .bmp')

    return redirect(url_for('settings'))

@admin_bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@admin_bp.route('/api/update_admin', methods=['POST'])
@login_required
def update_admin():
    data = request.json
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE User
            SET login = %s, full_name = %s, Phone = %s, department = %s, hire_date = %s
            WHERE id = %s AND role = 'admin'
        """, (
            data.get('login'),
            data.get('full_name'),
            data.get('Phone'),
            data.get('department'),
            data.get('hire_date'),
            data.get('id')
        ))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/api/delete_admin', methods=['POST'])
@login_required
def delete_admin():
    admin_id = request.json.get('id')
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM User WHERE id = %s AND role = 'admin'", (admin_id,))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/admin/leaders')
@login_required
def show_leaders():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, login, full_name, department, Phone, hire_date FROM User WHERE role = 'leader' AND fired = FALSE")
    leaders = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('leaders.html', leaders=leaders)

@admin_bp.route('/admin/leaders/add', methods=['POST'])
@login_required
def add_leader():
    data = request.json 

    login = data.get('login')
    full_name = data.get('full_name')
    department = data.get('department')
    phone = data.get('phone')
    password = data.get('password')
    hire_date = data.get('hire_date')

    hashed_password = generate_password_hash(password) 
    role = 'leader'

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO User (login, full_name, password, Phone, hire_date, role, department) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
            (login, full_name, hashed_password, phone, hire_date, role, department)
        )
        connection.commit()
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/api/update_leader', methods=['POST'])
@login_required
def update_leader():
    data = request.json
    print(f"Received data to update leader: {data}")

    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Проверяем, есть ли поле password
        if data.get('password'):
            hashed_password = generate_password_hash(data['password'])
            cursor.execute("""
                UPDATE User
                SET login = %s,
                    full_name = %s,
                    phone = %s,
                    department = %s,
                    hire_date = %s,
                    password = %s,
                    role = 'leader'
                WHERE id = %s
            """, (
                data['login'],
                data['full_name'],
                data['phone'],
                data['department'],
                data['hire_date'],
                hashed_password,
                data['id']
            ))
        else:
            cursor.execute("""
                UPDATE User
                SET login = %s,
                    full_name = %s,
                    phone = %s,
                    department = %s,
                    hire_date = %s,
                    role = 'leader'
                WHERE id = %s
            """, (
                data['login'],
                data['full_name'],
                data['phone'],
                data['department'],
                data['hire_date'],
                data['id']
            ))

        connection.commit()
        print("Leader updated successfully")
        return jsonify({'success': True})

    except Exception as e:
        connection.rollback()
        print(f"Error updating leader: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/admin/leaders/edit/<int:id>', methods=['POST'])
@login_required
def edit_leader(id):
    data = request.json
    print(f"Полученные данные для редактирования: {data}")

    login = data.get('login')
    full_name = data.get('full_name')
    phone = data.get('phone')
    department = data.get('department')
    hire_date = data.get('hire_date')
    password = data.get('password')

    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Если передали новый пароль
        if password:
            hashed_password = generate_password_hash(password)
            cursor.execute("""
                UPDATE User 
                SET 
                    login = %s,
                    full_name = %s,
                    phone = %s,
                    password = %s,
                    department = %s,
                    hire_date = %s,
                    role = 'leader'
                WHERE id = %s
            """, (
                login,
                full_name,
                phone,
                hashed_password,
                department,
                hire_date,
                id
            ))
            print(f"Пароль обновлён + роль leader для пользователя ID: {id}")
        else:
            cursor.execute("""
                UPDATE User
                SET 
                    login = %s,
                    full_name = %s,
                    phone = %s,
                    department = %s,
                    hire_date = %s,
                    role = 'leader'
                WHERE id = %s
            """, (
                login,
                full_name,
                phone,
                department,
                hire_date,
                id
            ))
            print(f"Обновлены данные + роль leader для пользователя ID: {id} без изменения пароля")

        connection.commit()
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        print(f"Ошибка при редактировании: {err}")
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        connection.close()


@admin_bp.route('/delete_leader', methods=['POST'])
@login_required
def delete_leader():
    leader_id = request.form['leader_id']
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM Leaders WHERE id = %s", (leader_id,))
        connection.commit()
        flash('Руководитель успешно удален', 'success')
    except mysql.connector.Error as err:
        connection.rollback()
        flash(f'Ошибка при удалении руководителя: {err}', 'danger')
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('admin.show_fired_leaders'))

@admin_bp.route('/admin/change_role', methods=['POST'])
@login_required
def change_user_role():
    print("change_user_role called")  # Отладка: вызов функции

    if current_user.role != 'admin':
        print("Access denied: user is not an admin")  # Отладка: проверка роли
        return jsonify({'success': False, 'message': 'Доступ разрешён только администраторам'}), 403

    data = request.json
    print(f"Received data: {data}")  # Отладка: входные данные

    user_id = data.get('user_id')
    new_role = data.get('new_role')

    if not user_id or not new_role:
        print("Missing required fields: user_id or new_role")  # Отладка: отсутствие данных
        return jsonify({'success': False, 'message': 'Не указаны необходимые данные'}), 400

    connection = create_db_connection()
    if not connection:
        print("Database connection failed")  # Отладка: ошибка подключения к БД
        return jsonify({'success': False, 'message': 'Ошибка подключения к базе данных'}), 500

    cursor = connection.cursor()
    try:
        print(f"Attempting to update role for user_id={user_id} to new_role={new_role}")  # Отладка: попытка обновления
        cursor.execute("UPDATE User SET role = %s WHERE id = %s", (new_role, user_id))
        connection.commit()
        print("Role updated successfully")  # Отладка: успешное обновление
        return jsonify({'success': True, 'message': 'Роль успешно обновлена'})
    except mysql.connector.Error as err:
        connection.rollback()
        print(f"Error updating role: {err}")  # Отладка: ошибка при обновлении
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        connection.close()
        print("Database connection closed")  # Отладка: закрытие соединения


@admin_bp.route('/admin/leaders/change_password/<int:id>', methods=['POST'])
@login_required
def change_leader_password(id):
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    if new_password != confirm_password:
        flash('Пароли не совпадают.', 'danger')
        return redirect(url_for('edit_leader', id=id))

    hashed_password = generate_password_hash(new_password)
    connection = create_db_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE User SET password = %s WHERE id = %s", (hashed_password, id))
    connection.commit()
    cursor.close()
    connection.close()

    flash('Пароль успешно изменён.', 'success')
    return redirect(url_for('edit_leader', id=id))

@admin_bp.route('/api/get_leader/<int:id>', methods=['GET'])
@login_required
def get_leader(id):
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Извлекаем нужные поля, включая role, чтобы убедиться, что это действительно лидер
    cursor.execute("""
        SELECT 
            id, 
            login, 
            full_name, 
            department, 
            phone,
            hire_date,
            role
        FROM User 
        WHERE id = %s 
          AND role = 'leader'
    """, (id,))
    leader = cursor.fetchone()

    cursor.close()
    connection.close()

    if leader:
        # Возвращаем данные в формате JSON
        return jsonify({'success': True, **leader})
    else:
        return jsonify({'success': False, 'message': 'Руководитель не найден'})


@admin_bp.route('/admin/fired_leaders')
@login_required
def show_fired_leaders():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, login, full_name, department, Phone, hire_date, fire_date FROM User WHERE role = 'leader' AND fired = TRUE")
    fired_leaders = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('fired_leaders.html', fired_leaders=fired_leaders)

@admin_bp.route('/api/fire_leader', methods=['POST'])
@login_required
def fire_leader():
    data = request.json
    leader_id = data.get('id')
    fire_date = datetime.now().date()  # Получаем текущую дату
    print(f"Firing leader with ID: {leader_id}")

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE User SET fired = TRUE, fire_date = %s, Phone = '' WHERE id = %s", (fire_date, leader_id))
        connection.commit()
        print("Leader fired successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        print(f"Error firing leader: {err}")
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/rehire_leader', methods=['POST'])
@login_required
def rehire_leader():
    leader_id = request.form['leader_id']
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE User SET fired = FALSE, fire_date = NULL WHERE id = %s", (leader_id,))
        connection.commit()
        flash('Руководитель успешно восстановлен', 'success')
    except mysql.connector.Error as err:
        connection.rollback()
        flash(f'Ошибка при восстановлении руководителя: {err}', 'danger')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('admin.show_fired_leaders'))



@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM User WHERE login = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if user and check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['username'] = user['login']
            session['id'] = user['id']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            session['department'] = user.get('department')
            session['admin_id'] = user['id']  # Сохраняем admin_id в сессии
            
            # Добавляем ukc_kc в сессию
            session['ukc_kc'] = user.get('ukc_kc')
            logger.debug(f"Пользователь 'ukc_kc': {user.get('ukc_kc')}")

            if user['role'] == 'operator':
                # Записываем время входа оператора в сессию
                session['login_time'] = datetime.now()
                # Устанавливаем статус оператора как "Онлайн"
                update_operator_status(user['id'], 'Онлайн')
                return redirect(url_for('callcenter.operator_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'leader':
                return redirect(url_for('leader_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash("Неверный логин или пароль", "danger")

    return render_template('login.html')




@admin_bp.route('/admin/users')
@login_required
def show_users():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, login, department FROM User")
    users = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('users.html', users=users)

@admin_bp.route('/api/get_broker', methods=['GET'])
@login_required
def get_broker():
    broker_id = request.args.get('id')
    print(f"Fetching broker with ID: {broker_id}")
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Получаем информацию о пользователе
        cursor.execute("""
            SELECT id, login, full_name, Phone, department, hire_date, role 
            FROM User WHERE id = %s
        """, (broker_id,))
        broker = cursor.fetchone()
        print(f"Fetched broker data: {broker}")

        if not broker:
            print("Broker not found")
            return jsonify({'success': False, 'message': 'Брокер не найден'})

        # Возвращаем данные, включая текущую роль
        return jsonify({'success': True, **broker})

    except Exception as e:
        print(f"Error fetching broker: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()


@admin_bp.route('/admin/brokers')
@login_required
def show_brokers():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id, login, full_name, department, Phone, hire_date FROM User WHERE role = 'user' AND fired = FALSE")
    brokers = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('brokers.html', brokers=brokers)

@admin_bp.route('/api/update_broker', methods=['POST'])
@login_required
def update_broker():
    print("Function update_broker called")  # Отладка: функция вызвана

        data = request.json
    print(f"Received data: {data}")  # Отладка: входные данные

        if not data:
        print("No data received!")  # Отладка: данные отсутствуют
        return jsonify({'success': False, 'message': 'No data received'}), 400

    connection = create_db_connection()
    if not connection:
        print("Failed to connect to the database")  # Отладка: ошибка подключения к БД
        return jsonify({'success': False, 'message': 'Database connection failed'}), 500

    cursor = connection.cursor()

    try:
        # Проверяем, передан ли новый пароль
        if data.get('password'):
            hashed_password = generate_password_hash(data['password'])
            print("Updating broker with new password")  # Отладка: обновление с паролем
            
            cursor.execute("""
                UPDATE User
                SET login = %s, full_name = %s, Phone = %s, department = %s, hire_date = %s, password = %s, role = %s
                WHERE id = %s
            """, (
                data['login'],
                data['full_name'],
                data['Phone'],
                data['department'],
                data['hire_date'],
                hashed_password,
                data['role'],
                data['id']
            ))
        else:
            print("Updating broker without changing password")  # Отладка: обновление без изменения пароля
            
            cursor.execute("""
                UPDATE User
                SET login = %s, full_name = %s, Phone = %s, department = %s, hire_date = %s, role = %s
                WHERE id = %s
            """, (
                data['login'],
                data['full_name'],
                data['Phone'],
                data['department'],
                data['hire_date'],
                data['role'],
                data['id']
            ))

        connection.commit()
        print("Broker updated successfully")  # Отладка: успешное обновление
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        print(f"Error while updating broker: {e}")  # Отладка: ошибка
        return jsonify({'success': False, 'message': str(e)})
    finally:
            cursor.close()
        connection.close()
        print("Database connection closed")  # Отладка: соединение закрыто

@admin_bp.route('/api/add_broker', methods=['POST'])
@login_required
def add_broker():
    """Добавление нового сотрудника"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Недостаточно прав'}), 403

    try:
        # Получаем данные из формы
        login = request.form.get('login')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        department_id = request.form.get('department_id')
        position = request.form.get('position', '')
        hire_date = request.form.get('hire_date')
        personal_email = request.form.get('personal_email', '')
        pc_login = request.form.get('pc_login', '')
        pc_password = request.form.get('pc_password', '')
        birth_date = request.form.get('birth_date')
        ukc_kc = request.form.get('ukc_kc', 'УКЦ')

        # Проверяем обязательные поля
        if not all([login, password, full_name]):
            return jsonify({'success': False, 'message': 'Не заполнены обязательные поля'}), 400
            
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Проверяем, существует ли пользователь с таким логином
            cursor.execute("SELECT id FROM User WHERE login = %s", (login,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Пользователь с таким логином уже существует'}), 409

            # Получаем название отдела по ID
            department = ''
            if department_id:
                try:
                    department_id = int(department_id)
                    cursor.execute("SELECT name FROM Department WHERE id = %s", (department_id,))
                    dept_result = cursor.fetchone()
                    if not dept_result:
                        return jsonify({'success': False, 'message': 'Отдел не найден'}), 404
                    department = dept_result['name']
                except ValueError:
                    return jsonify({'success': False, 'message': 'Неверный ID отдела'}), 400
                except Exception as e:
                    logger.error(f"Ошибка при получении отдела: {str(e)}")
                    return jsonify({'success': False, 'message': f'Ошибка при получении отдела: {str(e)}'}), 500

            # Хешируем пароль
            hashed_password = generate_password_hash(password)

            # Форматируем даты
            try:
                if hire_date:
                    hire_date = datetime.strptime(hire_date, '%Y-%m-%d').date()
                if birth_date:
                    birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except ValueError as e:
                return jsonify({'success': False, 'message': f'Неверный формат даты: {str(e)}'}), 400

            # Добавляем пользователя
            cursor.execute("""
                INSERT INTO User (login, password, full_name, phone, department_id, position, 
                                hire_date, personal_email, pc_login, pc_password, birth_date, ukc_kc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (login, hashed_password, full_name, phone, department_id, position,
                  hire_date, personal_email, pc_login, pc_password, birth_date, ukc_kc))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Сотрудник успешно добавлен'})
    
    except Exception as e:
            logger.error(f"Ошибка при добавлении сотрудника: {str(e)}")
            return jsonify({'success': False, 'message': f'Ошибка при добавлении сотрудника: {str(e)}'}), 500
    finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.error(f"Ошибка при обработке запроса: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обработке запроса: {str(e)}'}), 500

@admin_bp.route('/api/delete_broker', methods=['POST'])
@login_required
def delete_broker():
    broker_id = request.form.get('broker_id')
    print(f"Attempting to delete broker with ID: {broker_id}")
    
    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Удаление из таблицы UserNotifications
        print(f"Deleting from UserNotifications table for user_id: {broker_id}")
        cursor.execute("DELETE FROM UserNotifications WHERE user_id = %s", (broker_id,))
        
        # Удаление из таблицы Scores
        print(f"Deleting from Scores table for user_id: {broker_id}")
        cursor.execute("DELETE FROM Scores WHERE user_id = %s", (broker_id,))
        
        # Удаление из таблицы Rating
        print(f"Deleting from Rating table for user_id: {broker_id}")
        cursor.execute("DELETE FROM Rating WHERE user_id = %s", (broker_id,))
        
        # Удаление из таблицы User
        print(f"Deleting from User table for id: {broker_id}")
        cursor.execute("DELETE FROM User WHERE id = %s", (broker_id,))
        
        connection.commit()
        print("Broker and associated records deleted successfully")
        return redirect(url_for('admin.show_fired_brokers'))
    except Exception as e:
        connection.rollback()
        print(f"Error deleting broker: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()


@admin_bp.route('/api/fire_broker', methods=['POST'])
@login_required
def fire_broker():
    data = request.json
    broker_id = data.get('id')
    fire_date = datetime.now().date()  # Получаем текущую дату
    print(f"Firing broker with ID: {broker_id}")

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE User SET fired = TRUE, fire_date = %s, Phone = '' WHERE id = %s", (fire_date, broker_id))
        connection.commit()
        print("Broker fired successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        print(f"Error firing broker: {err}")
        return jsonify({'success': False, 'message': str(err)})
    finally:
            cursor.close()
        connection.close()

@admin_bp.route('/rehire_broker', methods=['POST'])
@login_required
def rehire_broker():
    broker_id = request.form['broker_id']
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE User SET fired = FALSE, fire_date = NULL WHERE id = %s", (broker_id,))
        connection.commit()
        flash('Брокер успешно восстановлен', 'success')
    except mysql.connector.Error as err:
        connection.rollback()
        flash(f'Ошибка при восстановлении брокера: {err}', 'danger')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('admin.show_fired_brokers'))



@admin_bp.route('/admin/fired_brokers')
@login_required
def show_fired_brokers():
    try:
        connection = create_db_connection()
        if not connection:
            flash("Ошибка подключения к базе данных", "danger")
            return render_template('fired_employees.html', error=True, employees_by_department={}, departments=[], positions=[])
        
        cursor = connection.cursor(dictionary=True)
        
        # Получаем уволенных сотрудников, объединяя данные из User и Candidates
        cursor.execute("""
                    SELECT 
                        u.id, 
                        u.full_name, 
                u.department, 
                COALESCE(u.position, c.position) as position, 
                u.Phone as phone, 
                u.fire_date AS termination_date, 
                u.hire_date,
                u.office,
                u.corp_phone AS corporate_number,
                c.personal_email,
                c.birth_date, 
                c.city,
                c.referral
                    FROM User u
            LEFT JOIN Candidates c ON u.login = c.login_pc
            WHERE u.fired = 1
            ORDER BY u.department, u.fire_date DESC
        """)
        
        fired_employees = cursor.fetchall()
        
        # Получаем список всех отделов и должностей для фильтров
        cursor.execute("SELECT DISTINCT department FROM User WHERE fired = 1 ORDER BY department")
        departments = [row['department'] for row in cursor.fetchall() if row['department']]
        
        cursor.execute("SELECT DISTINCT position FROM User WHERE fired = 1 AND position IS NOT NULL AND position != '' ORDER BY position")
        positions = [row['position'] for row in cursor.fetchall() if row['position']]
        
        if not positions:  # Если в User нет должностей, попробуем взять их из Candidates
            cursor.execute("""
                SELECT DISTINCT c.position 
                FROM User u
                JOIN Candidates c ON u.login = c.login_pc
                WHERE u.fired = 1 AND c.position IS NOT NULL AND c.position != ''
                ORDER BY c.position
            """)
            positions_rows = cursor.fetchall()
            positions = [row['position'] for row in positions_rows if row['position']]
        
            cursor.close()
            connection.close()

        # Преобразуем даты в строковый формат для отображения
        for employee in fired_employees:
            if employee['termination_date']:
                employee['termination_date'] = employee['termination_date'].strftime('%d.%m.%Y')
            if employee['hire_date']:
                employee['hire_date'] = employee['hire_date'].strftime('%d.%m.%Y')
        
        # Группируем сотрудников по отделам
        employees_by_department = {}
        for employee in fired_employees:
            department = employee['department'] or 'Без отдела'
            if department not in employees_by_department:
                employees_by_department[department] = []
            employees_by_department[department].append(employee)
        
        return render_template(
            'fired_employees.html', 
            employees_by_department=employees_by_department,
            departments=departments,
            positions=positions
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка уволенных сотрудников: {str(e)}")
        flash(f"Произошла ошибка: {str(e)}", "danger")
        return render_template('fired_employees.html', error=True, employees_by_department={}, departments=[], positions=[])


@admin_bp.route('/api/add_user', methods=['POST'])
@login_required
def add_user():
    data = request.json
    login = data.get('login')
    full_name = data.get('full_name')
    phone = data.get('phone')
    hire_date = data.get('hire_date')
    password = data.get('password')
    hashed_password = generate_password_hash(password)
    role = data.get('role', 'user')

    if session.get('role') == 'admin':
        department = data.get('department')
    elif session.get('role') == 'leader':
        department = session.get('department')
        role = 'user' 

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO User (login, full_name, password, Phone, role, department, hire_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (login, full_name, hashed_password, phone, role, department, hire_date))
        id = cursor.lastrowid
        connection.commit()
        flash('Пользователь успешно добавлен. User ID: ' + str(id), 'success')
    except mysql.connector.Error as err:
        flash(f'Ошибка при добавлении пользователя: {err}', 'danger')
    finally:
        cursor.close()
        connection.close()

    return jsonify({'success': True})



@admin_bp.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    connection = create_db_connection()
    if request.method == 'POST':
        login = request.form['login']
        department = request.form['department']
        phone = request.form['full_phone']
        # Пароль изменяться не будет в этой форме, только логин, отдел и телефон
        cursor = connection.cursor()
        cursor.execute("UPDATE User SET login = %s, department = %s, Phone = %s WHERE id = %s", (login, department, phone, id))
        connection.commit()
        cursor.close()
        connection.close()

        flash('Данные пользователя успешно обновлены', 'success')
        return redirect(url_for('show_brokers'))
    else:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, login, department, Phone FROM User WHERE id = %s", (id,))
        user = cursor.fetchone()
            cursor.close()
        connection.close()
        return render_template('edit_user.html', user=user)

@admin_bp.route('/api/delete_employee', methods=['DELETE'])
@login_required
def delete_employee_api():
    logger.debug("Начало выполнения функции delete_employee_api")
    
    if current_user.role != 'admin':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    # Пробуем получить ID из разных источников, так как jQuery может отправлять данные по-разному
    employee_id = request.args.get('id') or request.form.get('id')
    logger.debug(f"Запрошено удаление сотрудника с ID: {employee_id}")
        
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
        return jsonify({'success': False, 'message': 'ID сотрудника не указан'})
    
    try:
        logger.debug("Подключение к базе данных")
        connection = create_db_connection()
        if not connection:
            logger.error("Не удалось подключиться к базе данных")
            return jsonify({'success': False, 'message': 'Ошибка подключения к базе данных'})
            
        cursor = connection.cursor(dictionary=True)
        
        # Проверяем, что сотрудник уже уволен, проверяя только поле fired
        logger.debug(f"Проверка статуса сотрудника с ID={employee_id}")
        cursor.execute("SELECT id, full_name, fired, fire_date FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'})
        
        logger.debug(f"Данные сотрудника: {employee}")
        
        # Проверяем, уволен ли сотрудник по полю fired
        if not employee['fired']:
            logger.warning(f"Попытка удалить активного сотрудника с ID={employee_id}")
            return jsonify({'success': False, 'message': 'Нельзя удалить активного сотрудника. Сначала его необходимо уволить.'})
        
        # Получаем login_pc сотрудника
        logger.debug(f"Получение login сотрудника с ID={employee_id}")
        cursor.execute("SELECT login FROM User WHERE id = %s", (employee_id,))
        user_data = cursor.fetchone()
        user_login = user_data['login'] if user_data else None
        
        # Удаляем связанные записи из UserHistory
        logger.debug(f"Удаление записей из UserHistory для user_id={employee_id}")
        cursor.execute("DELETE FROM UserHistory WHERE user_id = %s", (employee_id,))
        logger.debug(f"Удалено записей из UserHistory: {cursor.rowcount}")
        
        # Удаляем связанные записи из UserNotifications, если они существуют
        logger.debug(f"Удаление записей из UserNotifications для user_id={employee_id}")
        cursor.execute("DELETE FROM UserNotifications WHERE user_id = %s", (employee_id,))
        logger.debug(f"Удалено записей из UserNotifications: {cursor.rowcount}")
        
        # Удаляем связанные записи из Rating, если они существуют
        logger.debug(f"Удаление записей из Rating для user_id={employee_id}")
        cursor.execute("DELETE FROM Rating WHERE user_id = %s", (employee_id,))
        logger.debug(f"Удалено записей из Rating: {cursor.rowcount}")
        
        # Удаляем связанную запись из Candidates, если она существует
        if user_login:
            logger.debug(f"Удаление записи из Candidates для login_pc={user_login}")
            cursor.execute("DELETE FROM Candidates WHERE login_pc = %s", (user_login,))
            logger.debug(f"Удалено записей из Candidates: {cursor.rowcount}")
        
        # Удаляем запись из User
        logger.debug(f"Удаление сотрудника с ID={employee_id}")
        cursor.execute("DELETE FROM User WHERE id = %s", (employee_id,))
        
        # Проверяем, что запись удалена
        rows_affected = cursor.rowcount
        logger.debug(f"Удалено записей из User: {rows_affected}")
        
        if rows_affected == 0:
            logger.warning(f"Ни одна запись не была удалена для сотрудника с ID={employee_id}")
            return jsonify({'success': False, 'message': 'Не удалось удалить сотрудника'})
        
        connection.commit()
        logger.info(f"Сотрудник {employee.get('full_name')} (ID={employee_id}) успешно удален")
        return jsonify({'success': True, 'message': 'Сотрудник успешно удален'})
        
    except Exception as e:
        logger.error(f"Ошибка при удалении сотрудника: {str(e)}")
        logger.error(traceback.format_exc())  # Добавляем вывод трейсбека для более подробной информации
        if 'connection' in locals():
            connection.rollback()
        return jsonify({'success': False, 'message': f'Ошибка при удалении: {str(e)}'})
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
        logger.debug("Завершение функции delete_employee_api")

@admin_bp.route('/personnel_dashboard')
@login_required
def personnel_dashboard():
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('main.index'))
        
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Получение статистики
    cursor.execute("SELECT COUNT(*) as total FROM User WHERE status != 'fired'")
    total_employees = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as active FROM User WHERE status = 'Онлайн'")
    active_employees = cursor.fetchone()['active']
    
    cursor.execute("SELECT COUNT(*) as fired FROM User WHERE status = 'fired'")
    fired_employees = cursor.fetchone()['fired']
    
    cursor.execute("SELECT COUNT(*) as departments FROM Department")
    departments_count = cursor.fetchone()['departments']
    
    # Получение данных для графиков
    # Динамика численности персонала за последние 30 дней
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count 
        FROM User 
        WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    staff_dynamics = cursor.fetchall()
    
    # Преобразование данных для графика
    dates = []
    staff_counts = []
    for item in staff_dynamics:
        dates.append(item['date'].strftime('%d.%m'))
        staff_counts.append(item['count'])
    
    # Распределение по отделам
    cursor.execute("""
        SELECT d.name, COUNT(u.id) as count
        FROM Department d
        LEFT JOIN User u ON d.id = u.department_id AND u.status != 'fired'
        GROUP BY d.id, d.name
    """)
    department_distribution = cursor.fetchall()
    
    department_names = []
    department_counts = []
    for item in department_distribution:
        department_names.append(item['name'])
        department_counts.append(item['count'])
    
    # Последние наймы
    cursor.execute("""
        SELECT u.full_name, d.name as department, u.position, u.created_at as hire_date
        FROM User u
        JOIN Department d ON u.department_id = d.id
        WHERE u.status != 'fired'
        ORDER BY u.created_at DESC
        LIMIT 5
    """)
    recent_hires = cursor.fetchall()
    
    # Последние увольнения
    cursor.execute("""
        SELECT u.full_name, d.name as department, u.position, u.fire_date
        FROM User u
        JOIN Department d ON u.department_id = d.id
        WHERE u.status = 'fired' AND u.fire_date IS NOT NULL
        ORDER BY u.fire_date DESC
        LIMIT 5
    """)
    recent_fires = cursor.fetchall()
    
    cursor.close()
    connection.commit()
    connection.close()
    
    return render_template('admin/personnel_dashboard.html',
                          total_employees=total_employees,
                          active_employees=active_employees,
                          fired_employees=fired_employees,
                          departments_count=departments_count,
                          dates=dates,
                          staff_counts=staff_counts,
                          department_names=department_names,
                          department_counts=department_counts,
                          recent_hires=recent_hires,
                          recent_fires=recent_fires)

@admin_bp.route('/admin/personnel')
@login_required
def personnel():
    """Страница управления персоналом"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('main.index'))
        
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем список всех отделов
        cursor.execute("SELECT id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()
        
        # Получаем список всех сотрудников с дополнительными полями
        cursor.execute("""
            SELECT u.id, u.login, u.full_name, u.Phone, u.department_id, 
                   u.position, u.hire_date, u.status, u.role, 
                   u.corp_phone, u.corporate_email, u.personal_email,
                   d.name as department_name
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            WHERE u.role != 'admin'
            ORDER BY u.full_name
        """)
        employees = cursor.fetchall()
        
        # Получаем статистику
        cursor.execute("SELECT COUNT(*) as total FROM User WHERE role != 'admin'")
        total_employees = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as active FROM User WHERE status = 'Онлайн' AND role != 'admin'")
        active_employees = cursor.fetchone()['active']
        
        cursor.execute("SELECT COUNT(*) as fired FROM User WHERE fired = 1 AND role != 'admin'")
        fired_employees = cursor.fetchone()['fired']
        
        # Создаем словарь с количеством сотрудников по отделам
        employees_by_department = {}
        for department in departments:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM User
                WHERE department_id = %s AND role != 'admin'
            """, (department['id'],))
            result = cursor.fetchone()
            employees_by_department[department['name']] = result['count']
        
            cursor.close()
            conn.close()
        
        return render_template('admin/personnel.html',
                             departments=departments,
                             employees=employees,
                             total_employees=total_employees,
                             active_employees=active_employees,
                             fired_employees=fired_employees,
                             employees_by_department=employees_by_department)
                             
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы персонала: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'danger')
        return redirect(url_for('main.index'))
