from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from werkzeug.security import generate_password_hash
from . import admin_bp
from app.utils import login_required, create_db_connection
from app.db.role_dao import RoleDAO
from app.db.user_dao_updated import UserDAO
from datetime import datetime
from flask_login import current_user

# Создаем экземпляр UserDAO и RoleDAO с конфигурацией БД из приложения
def get_user_dao():
    db_config = current_app.config.get('DB_CONFIG', {})
    return UserDAO(db_config)

def get_role_dao():
    db_config = current_app.config.get('DB_CONFIG', {})
    return RoleDAO(db_config)

@admin_bp.route('/users')
@login_required
def users_list():
    """
    Страница списка пользователей
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    user_dao = get_user_dao()
    users = user_dao.get_all_users(include_fired=False)
    
    return render_template(
        'admin/users_list.html',
        users=users,
        active_page='users'
    )

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def user_edit(user_id):
    """
    Страница редактирования пользователя
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    user_dao = get_user_dao()
    role_dao = get_role_dao()
    
    user = user_dao.get_user_by_id(user_id)
    
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('admin.users_list'))
    
    # Получаем списки всех ролей и отделов
    all_roles = role_dao.get_all_roles()
    
    # Создаем подключение к базе данных
    connection = create_db_connection()
    if connection is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('admin.users_list'))
    
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Получаем список всех отделов
        cursor.execute("SELECT id, name FROM Departments ORDER BY name")
        all_departments = cursor.fetchall()
        
        if request.method == 'POST':
            # Получаем данные формы
            full_name = request.form.get('full_name')
            department_id = request.form.get('department_id')
            role_id = request.form.get('role_id')
            position = request.form.get('position')
            ukc_kc = request.form.get('ukc_kc')
            phone = request.form.get('phone')
            email = request.form.get('email')
            pc_login = request.form.get('pc_login')
            office = request.form.get('office')
            corp_phone = request.form.get('corp_phone')
            fired = request.form.get('fired') == 'on'
            
            # Опционально обновляем пароль
            new_password = request.form.get('new_password')
            
            # SQL запрос на обновление пользователя
            update_fields = []
            params = []
            
            if full_name:
                update_fields.append("full_name = %s")
                params.append(full_name)
            
            if department_id:
                update_fields.append("department_id = %s")
                params.append(department_id)
            
            if role_id:
                update_fields.append("role_id = %s")
                params.append(role_id)
            
            if position:
                update_fields.append("position = %s")
                params.append(position)
            
            update_fields.append("Phone = %s")
            params.append(phone)
            
            update_fields.append("personal_email = %s")
            params.append(email)
            
            update_fields.append("pc_login = %s")
            params.append(pc_login)
            
            update_fields.append("office = %s")
            params.append(office)
            
            update_fields.append("corp_phone = %s")
            params.append(corp_phone)
            
            update_fields.append("fired = %s")
            params.append(fired)
            
            if fired and not user.fire_date:
                update_fields.append("fire_date = %s")
                params.append(datetime.now().date())
            elif not fired and user.fire_date:
                update_fields.append("fire_date = NULL")
            
            if new_password:
                update_fields.append("password = %s")
                params.append(generate_password_hash(new_password))
            
            # Добавляем user_id в конец params
            params.append(user_id)
            
            # Формируем и выполняем SQL запрос
            sql = f"UPDATE User SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = %s"
            cursor.execute(sql, params)
            
            # Обновляем настройки колл-центра, если указан номер УКЦ/КЦ
            if ukc_kc:
                # Проверяем, существует ли запись
                cursor.execute("SELECT id FROM CallCenterSettings WHERE user_id = %s", (user_id,))
                cc_settings = cursor.fetchone()
                
                if cc_settings:
                    # Обновляем существующую запись
                    cursor.execute(
                        "UPDATE CallCenterSettings SET ukc_kc = %s, updated_at = NOW() WHERE user_id = %s",
                        (ukc_kc, user_id)
                    )
                else:
                    # Создаем новую запись
                    cursor.execute(
                        "INSERT INTO CallCenterSettings (user_id, ukc_kc, created_at) VALUES (%s, %s, NOW())",
                        (user_id, ukc_kc)
                    )
            
            connection.commit()
            flash('Пользователь успешно обновлен', 'success')
            return redirect(url_for('admin.users_list'))
    
    except Exception as e:
        connection.rollback()
        flash(f'Ошибка при обновлении пользователя: {e}', 'danger')
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    
    return render_template(
        'admin/user_form.html',
        user=user,
        all_roles=all_roles,
        all_departments=all_departments,
        active_page='users'
    )

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
def user_add():
    """
    Страница добавления нового пользователя
    """
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('userlist.dashboard'))
    
    user_dao = get_user_dao()
    role_dao = get_role_dao()
    
    # Получаем списки всех ролей
    all_roles = role_dao.get_all_roles()
    
    # Создаем подключение к базе данных
    connection = create_db_connection()
    if connection is None:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('admin.users_list'))
    
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Получаем список всех отделов
        cursor.execute("SELECT id, name FROM Departments ORDER BY name")
        all_departments = cursor.fetchall()
        
        if request.method == 'POST':
            # Получаем данные формы
            login = request.form.get('login')
            password = request.form.get('password')
            full_name = request.form.get('full_name')
            department_id = request.form.get('department_id')
            role_id = request.form.get('role_id')
            position = request.form.get('position')
            ukc_kc = request.form.get('ukc_kc')
            phone = request.form.get('phone')
            email = request.form.get('email')
            pc_login = request.form.get('pc_login')
            office = request.form.get('office')
            corp_phone = request.form.get('corp_phone')
            
            # Проверяем, не существует ли пользователя с таким логином
            cursor.execute("SELECT id FROM User WHERE login = %s", (login,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash('Пользователь с таким логином уже существует', 'danger')
                return render_template(
                    'admin/user_form.html',
                    user=None,
                    is_new=True,
                    all_roles=all_roles,
                    all_departments=all_departments,
                    active_page='users'
                )
            
            # Вставляем нового пользователя
            sql = """
            INSERT INTO User (
                login, password, full_name, department_id, role_id, position, 
                Phone, personal_email, pc_login, office, corp_phone, hired_date, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            
            # Хешируем пароль
            hashed_password = generate_password_hash(password)
            
            # Выполняем вставку
            cursor.execute(sql, (
                login, hashed_password, full_name, department_id, role_id, position,
                phone, email, pc_login, office, corp_phone, datetime.now().date()
            ))
            
            # Получаем ID нового пользователя
            user_id = cursor.lastrowid
            
            # Если указан номер УКЦ/КЦ, добавляем запись в CallCenterSettings
            if ukc_kc:
                cursor.execute(
                    "INSERT INTO CallCenterSettings (user_id, ukc_kc, created_at) VALUES (%s, %s, NOW())",
                    (user_id, ukc_kc)
                )
            
            # Создаем запись в UserActivity
            cursor.execute(
                "INSERT INTO UserActivity (user_id, status, last_activity, created_at) VALUES (%s, %s, NOW(), NOW())",
                (user_id, 'offline')
            )
            
            connection.commit()
            flash('Пользователь успешно создан', 'success')
            return redirect(url_for('admin.users_list'))
    
    except Exception as e:
        connection.rollback()
        flash(f'Ошибка при создании пользователя: {e}', 'danger')
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    
    return render_template(
        'admin/user_form.html',
        user=None,
        is_new=True,
        all_roles=all_roles,
        all_departments=all_departments,
        active_page='users'
    ) 