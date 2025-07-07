from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory, abort, current_app
from app.admin import admin_bp
from app.utils import create_db_connection, login_required, admin_required, get_department_weekly_stats, get_notifications_count, save_logo, save_background
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_required as flask_login_required, current_user
import logging
from app.backoffice import add_backoffice_staff, update_backoffice_staff, delete_backoffice_staff, change_user_password
import os
import traceback
from datetime import datetime, date
from os import path, makedirs
from app.db_connection import get_connection

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LOGO_PATH = '/home/LetoBlack/static/logo.bmp'

@admin_bp.route('/delete_logo', methods=['POST'])
@login_required
def delete_logo():
    try:
        logo_path = os.path.join(current_app.static_folder, 'images', 'logo.bmp')
        if os.path.exists(logo_path):
            os.remove(logo_path)
            flash('Логотип успешно удален', 'success')
        else:
            flash('Логотип не найден', 'warning')
    except Exception as e:
        flash(f'Ошибка при удалении логотипа: {str(e)}', 'danger')
    return redirect(url_for('admin.settings'))

@admin_bp.route('/delete_background', methods=['POST'])
@login_required
def delete_background():
    try:
        bg_path = os.path.join(current_app.static_folder, 'images', 'real_estate_bg.jpg')
        if os.path.exists(bg_path):
            os.remove(bg_path)
            flash('Фоновое изображение успешно удалено', 'success')
        else:
            flash('Фоновое изображение не найдено', 'warning')
    except Exception as e:
        flash(f'Ошибка при удалении фонового изображения: {str(e)}', 'danger')
    return redirect(url_for('admin.settings'))

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
    return redirect(url_for('admin.settings'))

@admin_bp.route('/upload_logo', methods=['POST'])
@login_required
@admin_required
def upload_logo():
    if 'logo' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('admin.settings'))

    file = request.files['logo']
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('admin.settings'))
        
    try:
        save_logo(file)
        flash('Логотип успешно загружен', 'success')
    except Exception as e:
        flash(f'Ошибка при загрузке логотипа: {str(e)}', 'error')
        
    return redirect(url_for('admin.settings'))

@admin_bp.route('/upload_background', methods=['POST'])
@login_required
@admin_required
def upload_background():
    if 'background' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('admin.settings'))
        
    file = request.files['background']
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('admin.settings'))
        
    try:
        save_background(file)
        flash('Фоновое изображение успешно загружено', 'success')
    except Exception as e:
        flash(f'Ошибка при загрузке фонового изображения: {str(e)}', 'error')
        
        return redirect(url_for('admin.settings'))
    
@admin_bp.route('/settings')
@login_required
@admin_required
def settings():
    """Страница настроек системы"""
    # Получаем текущие настройки
    logo_url = url_for('static', filename='images/logo.bmp')
    background_url = url_for('static', filename='images/real_estate_bg.jpg')
    
    return render_template('admin/settings.html',
                         logo_url=logo_url if path.exists(path.join(current_app.static_folder, 'images/logo.bmp')) else None,
                         background_url=background_url if path.exists(path.join(current_app.static_folder, 'images/real_estate_bg.jpg')) else None)

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
    """Обновление данных сотрудника"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Недостаточно прав'}), 403

    conn = None
    cursor = None
    try:
        # Получаем данные из формы
        user_id = request.form.get('user_id')
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
        if not all([user_id, full_name]):
            return jsonify({'success': False, 'message': 'Не заполнены обязательные поля'}), 400

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Проверяем существование пользователя
        cursor.execute("SELECT id FROM User WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

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

        # Форматируем даты
        try:
            if hire_date:
                hire_date = datetime.strptime(hire_date, '%Y-%m-%d').date()
            if birth_date:
                birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
        except ValueError as e:
            return jsonify({'success': False, 'message': f'Неверный формат даты: {str(e)}'}), 400

        # Обновляем данные пользователя
        cursor.execute("""
            UPDATE User 
            SET full_name = %s, phone = %s, department_id = %s, position = %s,
                hire_date = %s, personal_email = %s, pc_login = %s, pc_password = %s,
                birth_date = %s, ukc_kc = %s
            WHERE id = %s
        """, (full_name, phone, department_id, position, hire_date, personal_email,
              pc_login, pc_password, birth_date, ukc_kc, user_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Данные сотрудника успешно обновлены'})
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка при обновлении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении сотрудника: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/api/add_broker', methods=['POST'])
@login_required
def add_broker():
    """Добавление нового сотрудника"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Недостаточно прав'}), 403

    conn = None
    cursor = None
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
        if conn:
            conn.rollback()
        logger.error(f"Ошибка при добавлении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при добавлении сотрудника: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/api/delete_broker', methods=['POST'])
@login_required
def delete_broker():
    broker_id = request.form.get('broker_id')
    print(f"Attempting to delete broker with ID: {broker_id}")
    
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        
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
        if connection:
            connection.rollback()
        print(f"Error deleting broker: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@admin_bp.route('/api/fire_broker', methods=['POST'])
@login_required
def fire_broker():
    data = request.json
    broker_id = data.get('id')
    fire_date = datetime.now().date()
    print(f"Firing broker with ID: {broker_id}")

    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE User SET fired = TRUE, fire_date = %s, Phone = '' WHERE id = %s", (fire_date, broker_id))
        connection.commit()
        print("Broker fired successfully")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        if connection:
            connection.rollback()
        print(f"Error firing broker: {err}")
        return jsonify({'success': False, 'message': str(err)})
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@admin_bp.route('/rehire_broker', methods=['POST'])
@login_required
def rehire_broker():
    broker_id = request.form.get('broker_id')
    connection = None
    cursor = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE User SET fired = FALSE, fire_date = NULL WHERE id = %s", (broker_id,))
        connection.commit()
        return redirect(url_for('admin.show_fired_brokers'))
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



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

# Дублирующий маршрут personnel_dashboard удален - используется версия из personnel.py

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
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/show_fired_employees')
@login_required
def show_fired_employees():
    """Страница уволенных сотрудников"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем список уволенных сотрудников
        cursor.execute("""
            SELECT u.*, d.name as department_name
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            WHERE u.fired = 1 OR u.fire_date IS NOT NULL
            ORDER BY u.fire_date DESC
        """)
        employees = cursor.fetchall()
        
        # Получаем статистику
        cursor.execute("SELECT COUNT(*) as total FROM User WHERE role != 'admin'")
        total_employees = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as active FROM User WHERE status = 'Онлайн' AND role != 'admin'")
        active_employees = cursor.fetchone()['active']
        
        cursor.execute("SELECT COUNT(*) as fired FROM User WHERE fired = 1 AND role != 'admin'")
        fired_employees = cursor.fetchone()['fired']
        
        # Получаем список всех отделов
        cursor.execute("SELECT id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()
        
        # Форматируем даты для отображения
        for employee in employees:
            if employee['fire_date']:
                employee['fire_date'] = employee['fire_date'].strftime('%d.%m.%Y')
            if employee['hire_date']:
                employee['hire_date'] = employee['hire_date'].strftime('%d.%m.%Y')
        
        return render_template('admin/fired_employees.html',
                              employees=employees,
                              total_employees=total_employees,
                              active_employees=active_employees,
                              fired_employees=fired_employees,
                              departments=departments)
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы уволенных сотрудников: {e}")
        flash(f'Ошибка при получении данных: {str(e)}', 'danger')
        return redirect(url_for('main.index'))
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@admin_bp.route('/api/edit_user', methods=['POST'])
def api_edit_user():
    try:
        data = request.get_json()
        user_id = data.get('id')
        full_name = data.get('full_name')
        phone = data.get('phone')
        department_id = data.get('department_id')
        position = data.get('position')
        hire_date = data.get('hire_date')
        personal_email = data.get('personal_email')
        pc_login = data.get('pc_login')
        pc_password = data.get('pc_password')
        birth_date = data.get('birth_date')
        ukc_kc = data.get('ukc_kc')

        if not all([user_id, full_name, phone, department_id, position, hire_date]):
            return jsonify({'success': False, 'message': 'Все поля, кроме личной почты, логина и пароля ПК, являются обязательными'}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            UPDATE User 
            SET full_name = %s, phone = %s, department_id = %s, position = %s,
                hire_date = %s, personal_email = %s, pc_login = %s, pc_password = %s,
                birth_date = %s, ukc_kc = %s
            WHERE id = %s
        """, (full_name, phone, department_id, position, hire_date, personal_email,
              pc_login, pc_password, birth_date, ukc_kc, user_id))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Данные сотрудника успешно обновлены'})
    except Exception as e:
        logger.error(f"Ошибка при обновлении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении сотрудника: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@admin_bp.route('/update_department_order', methods=['POST'])
@login_required
def update_department_order():
    """Обновление порядка отделов"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Недостаточно прав'}), 403
    
    try:
        data = request.json
        department_id = data.get('department_id')
        direction = data.get('direction')
        
        if not department_id or not direction:
            return jsonify({'success': False, 'message': 'Не указан ID отдела или направление'}), 400
            
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем текущий порядок отдела
        cursor.execute("SELECT id, name, display_order FROM Department WHERE id = %s", (department_id,))
        department = cursor.fetchone()
        
        if not department:
            return jsonify({'success': False, 'message': 'Отдел не найден'}), 404
        
        current_order = department['display_order'] or 0
        
        # Получаем соседний отдел в зависимости от направления
        if direction == 'up':
            cursor.execute("""
                SELECT id, name, display_order 
                FROM Department 
                WHERE display_order < %s 
                ORDER BY display_order DESC 
                LIMIT 1
            """, (current_order,))
        else:  # down
            cursor.execute("""
                SELECT id, name, display_order 
                FROM Department 
                WHERE display_order > %s 
                ORDER BY display_order ASC 
                LIMIT 1
            """, (current_order,))
        
        neighbor = cursor.fetchone()
        
        if not neighbor:
            return jsonify({'success': False, 'message': 'Невозможно переместить отдел'}), 400
        
        # Меняем порядок отделов
        cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", (neighbor['display_order'], department_id))
        cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", (current_order, neighbor['id']))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': f"Порядок отделов успешно обновлен: {department['name']} и {neighbor['name']}"
        })
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении порядка отделов: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении порядка отделов: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_bp.route('/initialize_roles_tables', methods=['GET'])
@login_required
@admin_required
def initialize_roles_tables():
    """Инициализирует таблицы ролей, модулей и разрешений"""
    conn = create_db_connection()
    
    try:
        # Создаем таблицу Role
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `Role` (
          `id` INT AUTO_INCREMENT PRIMARY KEY,
          `name` VARCHAR(50) NOT NULL UNIQUE COMMENT 'Название роли',
          `display_name` VARCHAR(100) NOT NULL COMMENT 'Отображаемое имя роли',
          `description` TEXT COMMENT 'Описание роли',
          `role_type` ENUM('system', 'backoffice', 'custom') DEFAULT 'custom',
          `is_system` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Системная роль (нельзя удалить)',
          `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
        """)
        
        # Создаем таблицу Module
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `Module` (
          `id` INT AUTO_INCREMENT PRIMARY KEY,
          `name` VARCHAR(50) NOT NULL UNIQUE COMMENT 'Системное имя модуля',
          `display_name` VARCHAR(100) NOT NULL COMMENT 'Отображаемое имя модуля',
          `description` TEXT COMMENT 'Описание модуля',
          `url_path` VARCHAR(100) COMMENT 'URL-путь модуля',
          `icon` VARCHAR(50) COMMENT 'Иконка для меню',
          `order` INT DEFAULT 0 COMMENT 'Порядок отображения',
          `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Активен ли модуль',
          `parent_id` INT NULL COMMENT 'ID родительского модуля для подразделов',
          `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
          FOREIGN KEY (`parent_id`) REFERENCES `Module`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
        """)
        
        # Создаем таблицу RolePermission
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `RolePermission` (
          `id` INT AUTO_INCREMENT PRIMARY KEY,
          `role_id` INT NOT NULL,
          `module_id` INT NOT NULL,
          `can_view` TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'Право на просмотр',
          `can_edit` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Право на редактирование',
          `can_create` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Право на создание',
          `can_delete` TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Право на удаление',
          `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
          FOREIGN KEY (`role_id`) REFERENCES `Role`(`id`) ON DELETE CASCADE,
          FOREIGN KEY (`module_id`) REFERENCES `Module`(`id`) ON DELETE CASCADE,
          UNIQUE KEY `unique_role_module` (`role_id`, `module_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
        """)
        
        # Создаем таблицу UserRole
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `UserRole` (
          `id` INT AUTO_INCREMENT PRIMARY KEY,
          `user_id` INT NOT NULL,
          `role_id` INT NOT NULL,
          `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `updated_at` DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
          FOREIGN KEY (`user_id`) REFERENCES `User`(`id`) ON DELETE CASCADE,
          FOREIGN KEY (`role_id`) REFERENCES `Role`(`id`) ON DELETE CASCADE,
          UNIQUE KEY `unique_user_role` (`user_id`, `role_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
        """)
        
        # Проверяем, есть ли уже роли в таблице Role
        cursor.execute("SELECT COUNT(*) FROM `Role`")
        role_count = cursor.fetchone()[0]
        
        if role_count == 0:
            # Заполняем таблицу базовыми ролями
            cursor.execute("""
            INSERT INTO `Role` (`name`, `display_name`, `description`, `role_type`, `is_system`) VALUES
            ('admin', 'Администратор', 'Полный доступ ко всем разделам системы', 'system', 1),
            ('leader', 'Руководитель', 'Доступ к управлению и отчетам', 'system', 1),
            ('operator', 'Оператор', 'Базовый доступ к системе', 'system', 1),
            ('user', 'Пользователь', 'Минимальные права доступа', 'system', 1),
            ('backoffice', 'Бэк-офис', 'Работа с документами', 'backoffice', 0);
            """)
        
        # Проверяем, есть ли уже модули в таблице Module
        cursor.execute("SELECT COUNT(*) FROM `Module`")
        module_count = cursor.fetchone()[0]
        
        if module_count == 0:
            # Заполняем таблицу базовыми модулями
            cursor.execute("""
            INSERT INTO `Module` (`name`, `display_name`, `description`, `url_path`, `icon`, `order`, `is_active`) VALUES
            ('dashboard', 'Дашборд', 'Главная страница системы', '/dashboard', 'fas fa-home', 1, 1),
            ('news', 'Новости', 'Управление новостями', '/news', 'fas fa-newspaper', 2, 1),
            ('rating', 'Рейтинг', 'Рейтинг брокеров', '/rating', 'fas fa-chart-line', 3, 1),
            ('personnel', 'Персонал', 'Управление сотрудниками', '/personnel', 'fas fa-users', 4, 1),
            ('settings', 'Настройки', 'Настройки системы', '/admin/settings', 'fas fa-cog', 5, 1),
            ('callcenter', 'Колл-центр', 'Управление колл-центром', '/callcenter', 'fas fa-phone', 6, 1),
            ('helpdesk', 'Хелпдеск', 'Система поддержки', '/helpdesk', 'fas fa-headset', 7, 1);
            """)
            
            # Получаем ID администратора
            cursor.execute("SELECT id FROM `Role` WHERE name = 'admin'")
            admin_role_id = cursor.fetchone()[0]
            
            # Добавляем все права администратору на все модули
            cursor.execute("""
            INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
            SELECT %s, id, 1, 1, 1, 1 FROM `Module`
            """, (admin_role_id,))
            
            # Получаем ID руководителя
            cursor.execute("SELECT id FROM `Role` WHERE name = 'leader'")
            leader_role_id = cursor.fetchone()[0]
            
            # Добавляем права руководителю на просмотр и редактирование некоторых модулей
            cursor.execute("""
            INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
            SELECT %s, id, 1, 1, 1, 0 FROM `Module` WHERE `name` IN ('dashboard', 'personnel', 'rating')
            """, (leader_role_id,))
            
            # Права только на просмотр для руководителя
            cursor.execute("""
            INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
            SELECT %s, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('news', 'settings')
            """, (leader_role_id,))
            
            # Получаем ID оператора
            cursor.execute("SELECT id FROM `Role` WHERE name = 'operator'")
            operator_role_id = cursor.fetchone()[0]
            
            # Добавляем права оператору
            cursor.execute("""
            INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
            SELECT %s, id, 1, 1, 1, 0 FROM `Module` WHERE `name` IN ('callcenter')
            """, (operator_role_id,))
            
            cursor.execute("""
            INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
            SELECT %s, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('dashboard', 'news')
            """, (operator_role_id,))
            
            # Получаем ID пользователя
            cursor.execute("SELECT id FROM `Role` WHERE name = 'user'")
            user_role_id = cursor.fetchone()[0]
            
            # Добавляем базовые права пользователю
            cursor.execute("""
            INSERT INTO `RolePermission` (`role_id`, `module_id`, `can_view`, `can_edit`, `can_create`, `can_delete`)
            SELECT %s, id, 1, 0, 0, 0 FROM `Module` WHERE `name` IN ('dashboard', 'news')
            """, (user_role_id,))
            
        conn.commit()
        flash('Таблицы ролей успешно инициализированы', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Ошибка при инициализации таблиц ролей: {str(e)}', 'danger')
    finally:
            conn.close()
    
    return redirect(url_for('roles.index'))

@admin_bp.route('/save_notification', methods=['POST'])
@login_required
def save_notification():
    """Сохранение уведомления на рабочем столе"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'error')
        return redirect(url_for('admin.settings'))

    # Здесь должна быть логика сохранения уведомления на рабочем столе
    flash('Уведомление сохранено', 'success')
    return redirect(url_for('admin.settings'))

@admin_bp.route('/toggle_system_maintenance', methods=['POST'])
@login_required
def toggle_system_maintenance():
    """Включение/выключение режима обслуживания"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'error')
        return redirect(url_for('admin.settings'))
        
    try:
        # Здесь логика переключения режима
        flash('Настройки сохранены', 'success')
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'error')
    
    return redirect(url_for('admin.settings'))

@admin_bp.route('/reset_user_password/<int:user_id>', methods=['POST'])
@login_required
def reset_user_password(user_id):
    """Сброс пароля пользователя"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'error')
        return redirect(url_for('admin.settings'))

    # Здесь должна быть логика сброса пароля пользователя
    flash('Пароль пользователя успешно сброшен', 'success')
    return redirect(url_for('admin.settings'))

@admin_bp.route('/settings/logs')
@login_required
@admin_required
def settings_logs():
    """
    Страница просмотра логов действий пользователей с фильтрами
    """
    from app.models.audit_log import AuditLog
    from flask import request
    # Получаем фильтры из query-параметров
    username = request.args.get('username')
    action = request.args.get('action')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    # Формируем SQL-запрос с учётом фильтров
    sql = 'SELECT * FROM audit_log WHERE 1=1'
    params = []
    if username:
        sql += ' AND username LIKE %s'
        params.append(f'%{username}%')
    if action:
        sql += ' AND action = %s'
        params.append(action)
    if status:
        sql += ' AND status = %s'
        params.append(status)
    if date_from:
        sql += ' AND timestamp >= %s'
        params.append(date_from)
    if date_to:
        sql += ' AND timestamp <= %s'
        params.append(date_to)
    sql += ' ORDER BY timestamp DESC LIMIT 200'
    conn = create_db_connection()  # Заменяю get_connection() на create_db_connection()
    logs = []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        logs = cursor.fetchall()
        cursor.close()
    finally:
        if conn:
            conn.close()
    # Для фильтров actions/status можно получить уникальные значения
    actions = set([log['action'] for log in logs])
    statuses = set([log['status'] for log in logs])
    return render_template(
        'admin/settings_logs.html',
        logs=logs,
        actions=actions,
        statuses=statuses,
        active_page='settings',
        active_tab='logs',
        filters={'username': username, 'action': action, 'status': status, 'date_from': date_from, 'date_to': date_to}
    )
