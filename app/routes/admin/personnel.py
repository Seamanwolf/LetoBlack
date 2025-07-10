from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import current_user, login_user
from app.utils import create_db_connection, login_required
import logging
from datetime import datetime
from app.routes.admin import admin_routes_bp
from app.routes.auth import redirect_based_on_role
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
import time
from app.models.user import User, normalize_role

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Создаем обработчик для записи в файл
log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'app.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Создаем обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Создаем форматтер для логов
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Добавляем обработчики к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def has_admin_or_leader_role(user):
    """Проверяет, имеет ли пользователь роль admin или leader"""
    normalized_role = normalize_role(user.role)
    return normalized_role in ['admin', 'leader']

def has_admin_role(user):
    """Проверяет, имеет ли пользователь роль admin"""
    normalized_role = normalize_role(user.role)
    return normalized_role == 'admin'

@admin_routes_bp.route('/personnel')
@login_required
def personnel():
    logger.debug("Начало выполнения функции personnel")
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        flash('У вас нет доступа к этой странице', 'error')
        return redirect_based_on_role(current_user)
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем статистику
        cursor.execute('''
            SELECT 
                COUNT(*) as total_employees,
                SUM(CASE WHEN fire_date IS NULL THEN 1 ELSE 0 END) as active_employees,
                SUM(CASE WHEN fire_date IS NOT NULL THEN 1 ELSE 0 END) as fired_employees
            FROM User
        ''')
        stats = cursor.fetchone()
        
        # Получаем список отделов из таблицы Department с учетом порядка отображения
        cursor.execute('SELECT id, name, display_order FROM Department ORDER BY display_order ASC, name ASC')
        departments = cursor.fetchall()
        
        # Добавляем сотрудников к каждому отделу
        for department in departments:
            cursor.execute('''
                SELECT 
                    u.id,
                    u.full_name,
                    u.position,
                    u.Phone as phone,
                    u.corp_phone as corporate_phone,
                    u.role,
                    u.role_id,
                    u.status,
                    u.rr,
                    u.site,
                    u.documents,
                    CASE 
                        WHEN u.status = 'online' THEN 1
                        WHEN u.last_active > NOW() - INTERVAL 5 MINUTE THEN 1
                        ELSE 0
                    END as online_status,
                    u.fire_date,
                    u.corporate_email,
                    ep.photo_url
                FROM User u
                LEFT JOIN UserActivity ua ON u.id = ua.user_id
                LEFT JOIN EmployeePhotos ep ON u.id = ep.employee_id
                WHERE u.department_id = %s AND u.fire_date IS NULL
                ORDER BY 
                    CASE 
                        WHEN u.role = 'leader' OR u.role = '2' OR u.role_id = 2 THEN 1
                        WHEN u.role = 'deputy' THEN 2
                        WHEN u.position LIKE '%%руководитель%%' OR u.position LIKE '%%Руководитель%%' OR u.position LIKE '%%РОП%%' THEN 1
                        WHEN u.position LIKE '%%заместитель%%' OR u.position LIKE '%%Заместитель%%' OR u.position LIKE '%%зам%%' OR u.position LIKE '%%Зам%%' THEN 2
                        ELSE 3
                    END,
                    u.full_name
            ''', (department['id'],))
            employees = cursor.fetchall()
            
            # Формируем полные URL для фотографий
            for employee in employees:
                if employee.get('photo_url'):
                    # Если путь уже содержит /static/, используем его как есть
                    if employee['photo_url'].startswith('/static/'):
                        employee['photo_url'] = employee['photo_url']
                    else:
                        # Иначе формируем полный путь
                        employee['photo_url'] = f"/static/uploads/employee_photos/{employee['photo_url']}"
                else:
                    # Если фото нет, устанавливаем дефолтное
                    employee['photo_url'] = "/static/img/default-avatar.svg"
                
                # Преобразуем статус для отображения
                if employee.get('status'):
                    status_display_mapping = {
                        'online': 'Онлайн',
                        'offline': 'Офлайн',
                        'active': 'Активен',
                        'blocked': 'Заблокирован',
                        'fired': 'Уволен'
                    }
                    employee['status_display'] = status_display_mapping.get(employee['status'], employee['status'])
                else:
                    employee['status_display'] = 'Офлайн'
            
            # Выводим диагностическую информацию
            logger.debug(f"Запрос для отдела {department['name']} (ID: {department['id']}) вернул {len(employees)} сотрудников")
            if employees:
                logger.debug(f"Отдел '{department['name']}': employees = {employees}, length = {len(employees)}")
            
            # Добавляем список сотрудников к отделу
            department['employees'] = employees
        
        # Диагностика перед передачей в template
        logger.debug(f"Передаем в template {len(departments)} отделов")
        for dept in departments:
            logger.debug(f"Отдел '{dept['name']}': employees = {dept.get('employees', 'KEY_NOT_SET')}, length = {len(dept.get('employees', []))}")
        
        return render_template('admin/personnel.html',
                             total_employees=stats['total_employees'],
                             active_employees=stats['active_employees'],
                             fired_employees=stats['fired_employees'],
                             avg_score=0,  # Временно установим 0, так как колонки score нет
                             departments=departments,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы персонала: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return redirect_based_on_role(current_user)
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_employee', methods=['GET'])
@admin_routes_bp.route('/admin/api/get_employee', methods=['GET'])
@login_required
def get_employee_api():
    """Получение данных сотрудника по ID"""
    logger.debug("Начало выполнения функции get_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        # Получаем ID сотрудника из запроса
        employee_id = request.args.get('id')
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
            
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем данные сотрудника с учетом реальной структуры таблицы
        query = """
            SELECT 
                u.id, u.full_name, u.login, u.Phone,
                u.department_id, u.role, u.role_id, u.hire_date, u.fire_date,
                u.fired, u.personal_email, u.pc_login, u.pc_password,
                u.birth_date, u.position, u.office, u.corporate_email,
                u.corp_phone, u.documents, u.rr, u.site, u.crm_id,
                u.notes, u.status, u.last_active, u.crm_login, u.crm_password,
                d.name as department_name,
                ep.photo_url
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            LEFT JOIN EmployeePhotos ep ON u.id = ep.employee_id
            WHERE u.id = %s
        """
        logger.debug(f"SQL запрос для получения данных сотрудника: {query}")
        cursor.execute(query, (employee_id,))
        employee = cursor.fetchone()

        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
            
        # Логируем полученные данные
        logger.debug(f"Полученные данные сотрудника: {employee}")

        # Преобразуем даты в строковый формат для JSON
        if employee.get('hire_date'):
            employee['hire_date'] = employee['hire_date'].strftime('%Y-%m-%d')
        if employee.get('fire_date'):
            employee['fire_date'] = employee['fire_date'].strftime('%Y-%m-%d')
        
        # Формируем полный URL для фотографии
        if employee.get('photo_url'):
            # Если путь уже содержит /static/, используем его как есть
            if employee['photo_url'].startswith('/static/'):
                employee['photo_url'] = employee['photo_url']
            else:
                # Иначе формируем полный путь
                employee['photo_url'] = f"/static/uploads/employee_photos/{employee['photo_url']}"
        else:
            # Если фото нет, устанавливаем дефолтное
            employee['photo_url'] = "/static/img/default-avatar.svg"
        
        # Преобразуем статус для отображения
        if employee.get('status'):
            status_display_mapping = {
                'online': 'Онлайн',
                'offline': 'Офлайн',
                'active': 'Активен',
                'blocked': 'Заблокирован',
                'fired': 'Уволен'
            }
            employee['status_display'] = status_display_mapping.get(employee['status'], employee['status'])
        else:
            employee['status_display'] = 'Офлайн'
            
        logger.info(f"Данные сотрудника с ID={employee_id} успешно получены")
        return jsonify({'success': True, 'employee': employee})
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении данных: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_employee_login', methods=['GET'])
@login_required
def get_employee_login_api():
    """Получение логина сотрудника по ID"""
    logger.debug("Начало выполнения функции get_employee_login_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        # Получаем ID сотрудника из запроса
        employee_id = request.args.get('id')
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
            
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем логин сотрудника
        cursor.execute("SELECT login FROM User WHERE id = %s", (employee_id,))
        result = cursor.fetchone()
        
        if not result or not result.get('login'):
            logger.warning(f"Логин для сотрудника с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Логин не найден'}), 404
            
        logger.info(f"Логин сотрудника с ID={employee_id} успешно получен")
        return jsonify({'success': True, 'login': result['login']})
        
    except Exception as e:
        logger.error(f"Ошибка при получении логина сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении логина: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/update_employee_json', methods=['POST'])
@login_required
def update_employee_api():
    """Обновление данных сотрудника через API (JSON)"""
    logger.debug("Начало выполнения функции update_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        # Получаем данные из JSON
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
            
        # Получаем ID сотрудника
        employee_id = data.get('id')
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Получаем текущие данные сотрудника
        cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404

        # Подготовка данных для обновления
        update_fields = {}

        # Обработка текстовых полей
        text_fields = [
            'full_name', 'position', 'Phone', 'corp_phone', 'department_id', 'role', 'corporate_email'
        ]

        for field in text_fields:
            new_value = data.get(field)
            if new_value is not None:
                # Обработка телефонных номеров
                if field == 'corp_phone' and new_value:
                    if new_value.startswith('+7'):
                        new_value = new_value[2:]
                if field in employee and new_value != employee[field]:
                    update_fields[field] = new_value

        # Специальная обработка corporate_number -> corp_phone
        if 'corporate_number' in data:
            value = data.get('corporate_number')
            if value and value.startswith('+7'):
                value = value[2:]
            update_fields['corp_phone'] = value

        # Специальная обработка personal_number -> corp_phone
        if 'personal_number' in data:
            value = data.get('personal_number')
            if value and value.startswith('+7'):
                value = value[2:]
            update_fields['corp_phone'] = value

        # Если есть поля для обновления
        if update_fields:
            # Формируем SQL-запрос для обновления
            update_query = "UPDATE User SET "
            update_values = []
            for field, value in update_fields.items():
                update_query += f"{field} = %s, "
                update_values.append(value)
            update_query = update_query.rstrip(", ") + " WHERE id = %s"
            update_values.append(employee_id)

            # Логируем SQL запрос и значения
            logger.debug(f"SQL запрос: {update_query}")
            logger.debug(f"Значения: {update_values}")

            # Выполняем обновление
            cursor.execute(update_query, tuple(update_values))
            conn.commit()
            
            # Проверяем результат обновления
            cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
            updated_employee = cursor.fetchone()
            logger.debug(f"Обновленные данные сотрудника: {updated_employee}")
            
            logger.info(f"Данные сотрудника с ID={employee_id} успешно обновлены")
            return jsonify({'success': True, 'message': 'Данные сотрудника успешно обновлены'})
        else:
            logger.info(f"Нет изменений для сотрудника с ID={employee_id}")
            return jsonify({'success': True, 'message': 'Нет изменений для сохранения'})
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении данных: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/block_employee', methods=['POST'])
@admin_routes_bp.route('/admin/api/block_employee', methods=['POST'])
@login_required
def block_employee_api():
    """Блокировка сотрудника через API"""
    logger.debug("Начало выполнения функции block_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        employee_id = data.get('id')
        block_reason = data.get('block_reason', '')
        
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, существует ли сотрудник
        cursor.execute("SELECT id, full_name, status FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
        
        # Обновляем статус сотрудника на "заблокирован"
        cursor.execute("""
            UPDATE User 
            SET status = 'blocked'
            WHERE id = %s
        """, (employee_id,))
        
        # Добавляем запись в историю
        cursor.execute("""
            INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by)
            VALUES (%s, 'status', %s, 'blocked', %s)
        """, (employee_id, employee['status'], current_user.id))
        
        # Если указана причина блокировки, добавляем дополнительную запись
        if block_reason:
            cursor.execute("""
                INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by)
                VALUES (%s, 'block_reason', '', %s, %s)
            """, (employee_id, block_reason, current_user.id))
        
        conn.commit()
        
        logger.info(f"Сотрудник {employee['full_name']} (ID={employee_id}) успешно заблокирован")
        return jsonify({
            'success': True, 
            'message': f"Сотрудник {employee['full_name']} успешно заблокирован"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при блокировке сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при блокировке сотрудника: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()



@admin_routes_bp.route('/api/fire_employee', methods=['POST'])
@admin_routes_bp.route('/admin/api/fire_employee', methods=['POST'])
@login_required
def fire_employee_api():
    """Увольнение сотрудника через API"""
    logger.debug("Начало выполнения функции fire_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        employee_id = data.get('id')
        fire_date = data.get('fire_date')
        fire_reason = data.get('fire_reason', '')
        
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
            
        if not fire_date:
            logger.warning("Дата увольнения не указана в запросе")
            return jsonify({'success': False, 'message': 'Дата увольнения не указана'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, существует ли сотрудник
        cursor.execute("SELECT id, full_name FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
        
        # Обновляем данные сотрудника
        cursor.execute("""
            UPDATE User 
            SET 
                fire_date = %s,
                fired = 1,
                status = 'fired'
            WHERE id = %s
        """, (fire_date, employee_id))
        
        # Добавляем запись в историю
        cursor.execute("""
            INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by)
            VALUES (%s, 'fire_date', NULL, %s, %s)
        """, (employee_id, fire_date, current_user.id))
        
        conn.commit()
        
        logger.info(f"Сотрудник {employee['full_name']} (ID={employee_id}) успешно уволен")
        return jsonify({
            'success': True, 
            'message': f"Сотрудник {employee['full_name']} успешно уволен"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при увольнении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при увольнении сотрудника: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/unblock_employee', methods=['POST'])
@admin_routes_bp.route('/admin/api/unblock_employee', methods=['POST'])
@login_required
def unblock_employee_api():
    """Разблокировка сотрудника через API"""
    logger.debug("Начало выполнения функции unblock_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        employee_id = data.get('id')
        unblock_reason = data.get('unblock_reason', '')
        
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, существует ли сотрудник
        cursor.execute("SELECT id, full_name, status FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
        
        # Разблокируем сотрудника (обновляем статус)
        cursor.execute("""
            UPDATE User 
            SET 
                status = 'active',
                last_active = NOW()
            WHERE id = %s
        """, (employee_id,))
        
        # Добавляем запись в историю
        cursor.execute("""
            INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by)
            VALUES (%s, 'status', %s, 'active', %s)
        """, (employee_id, employee['status'], current_user.id))
        
        # Если указана причина разблокировки, добавляем дополнительную запись
        if unblock_reason:
            cursor.execute("""
                INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by)
                VALUES (%s, 'unblock_reason', '', %s, %s)
            """, (employee_id, unblock_reason, current_user.id))
        
        conn.commit()
        
        logger.info(f"Сотрудник {employee['full_name']} (ID={employee_id}) успешно разблокирован")
        return jsonify({
            'success': True, 
            'message': f"Сотрудник {employee['full_name']} успешно разблокирован"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при разблокировке сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при разблокировке сотрудника: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_available_phones', methods=['GET'])
@admin_routes_bp.route('/admin/api/get_available_phones', methods=['GET'])
@login_required
def get_available_phones_api():
    """Получение списка доступных корпоративных номеров"""
    logger.debug("Начало выполнения функции get_available_phones_api")
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав'})
        
    try:
        department_id = request.args.get('department_id')
        current_employee_id = request.args.get('current_employee_id')  # ID текущего сотрудника
        
        if not department_id:
            logger.warning("ID отдела не указан в запросе")
            return jsonify({'success': False, 'message': 'ID отдела не указан'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем название отдела по ID
        cursor.execute("SELECT name FROM Department WHERE id = %s", (department_id,))
        department = cursor.fetchone()
        
        if not department:
            logger.warning(f"Отдел с ID={department_id} не найден")
            return jsonify({'success': False, 'message': 'Отдел не найден'}), 404
        
        department_name = department['name']
        
        # Получаем все номера, закрепленные за отделом
        cursor.execute("""
            SELECT corp_phone as phone_number, full_name as assigned_to, id as employee_id
            FROM User 
            WHERE department_id = %s AND corp_phone IS NOT NULL AND corp_phone != ''
            ORDER BY corp_phone
        """, (department_id,))
        
        department_numbers = cursor.fetchall()
        
        # Формируем список доступных номеров
        available_numbers = []
        
        for number in department_numbers:
            phone_number = number['phone_number']
            
            # Форматируем номер телефона
            if not phone_number.startswith('+7'):
                if len(phone_number) == 10:
                    phone_number = '+7' + phone_number
                elif len(phone_number) == 11 and phone_number.startswith('7'):
                    phone_number = '+' + phone_number
                elif len(phone_number) == 11 and phone_number.startswith('8'):
                    phone_number = '+7' + phone_number[1:]
                else:
                    phone_number = '+7' + phone_number
            
            # Определяем статус номера
            if str(number['employee_id']) == str(current_employee_id):
                # Это номер текущего сотрудника
                status = 'current'
                status_text = 'текущий номер'
            elif number['assigned_to']:
                # Номер занят другим сотрудником
                status = 'occupied'
                status_text = f'занят ({number["assigned_to"]})'
            else:
                # Номер свободен
                status = 'free'
                status_text = 'свободен'
            
            available_numbers.append({
                'phone_number': phone_number,
                'assigned_to': number['assigned_to'],
                'status': status,
                'status_text': status_text
            })
        
        # Если в отделе нет номеров, попробуем найти в таблице корпоративных номеров
        if not available_numbers:
            # Попробуем найти в таблице corp_numbers
            cursor.execute("""
                SELECT phone_number, assigned_to 
                FROM corp_numbers 
                WHERE department = %s AND blocked = 0
                ORDER BY phone_number
            """, (department_name,))
            
            corp_numbers = cursor.fetchall()
            
            for number in corp_numbers:
                phone_number = number['phone_number']
                
                # Форматируем номер телефона
                if not phone_number.startswith('+7'):
                    if len(phone_number) == 10:
                        phone_number = '+7' + phone_number
                    elif len(phone_number) == 11:
                        phone_number = '+' + phone_number
                    else:
                        phone_number = '+7' + phone_number
                
                status = 'free' if not number['assigned_to'] else 'occupied'
                status_text = 'свободен' if not number['assigned_to'] else f'занят ({number["assigned_to"]})'
                
                available_numbers.append({
                    'phone_number': phone_number,
                    'assigned_to': number['assigned_to'],
                    'status': status,
                    'status_text': status_text
                })
        
        logger.info(f"Найдено {len(available_numbers)} номеров для отдела {department_name}")
        return jsonify({'success': True, 'numbers': available_numbers})
        
    except Exception as e:
        logger.error(f"Ошибка при получении доступных номеров: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении номеров: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/change_employee_password', methods=['POST'])
@admin_routes_bp.route('/admin/api/change_employee_password', methods=['POST'])
@login_required
def change_employee_password_api():
    """Смена пароля сотрудника (только для администратора)"""
    logger.debug("Начало выполнения функции change_employee_password_api")
    
    if current_user.role != 'admin':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        employee_id = data.get('employee_id')
        new_password = data.get('new_password')
        
        if not employee_id or not new_password:
            logger.warning("ID сотрудника или новый пароль не указаны")
            return jsonify({'success': False, 'message': 'ID сотрудника или новый пароль не указаны'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, существует ли сотрудник
        cursor.execute("SELECT id, full_name, login FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
        
        # Хэшируем новый пароль стандартным методом Flask (Werkzeug)
        password_hash = generate_password_hash(new_password)
        
        # Обновляем пароль сотрудника
        cursor.execute("UPDATE User SET password = %s WHERE id = %s", (password_hash, employee_id))
        
        # Добавляем запись в историю
        cursor.execute("""
            INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by)
            VALUES (%s, 'password', 'скрыто', 'изменен', %s)
        """, (employee_id, current_user.id))
        
        conn.commit()
        
        logger.info(f"Пароль сотрудника {employee['full_name']} (ID={employee_id}) изменен администратором {current_user.login}")
        return jsonify({'success': True, 'message': f"Пароль сотрудника {employee['full_name']} успешно изменен"})
        
    except Exception as e:
        logger.error(f"Ошибка при смене пароля сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при смене пароля: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/fired_employees')
@login_required
def fired_employees():
    """Страница уволенных сотрудников"""
    if current_user.role != 'admin':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect_based_on_role(current_user)
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Получаем статистику
        cursor.execute('''
            SELECT 
                COUNT(*) as total_employees,
                SUM(CASE WHEN fire_date IS NULL THEN 1 ELSE 0 END) as active_employees,
                SUM(CASE WHEN fire_date IS NOT NULL THEN 1 ELSE 0 END) as fired_employees
            FROM User
        ''')
        stats = cursor.fetchone()
        
        # Получаем список отделов из таблицы Department с учетом порядка отображения
        cursor.execute('SELECT id, name, display_order FROM Department ORDER BY display_order ASC, name ASC')
        departments = cursor.fetchall()
        
        # Получаем список уволенных сотрудников с последним корпоративным номером
        cursor.execute("""
            SELECT 
                u.*, 
                d.name as department_name, 
                DATEDIFF(u.fire_date, u.hire_date) as days_worked,
                COALESCE(
                    (SELECT pnh.new_number 
                     FROM phone_numbers_history pnh 
                     WHERE pnh.operator_id = u.id 
                     ORDER BY pnh.changed_at DESC 
                     LIMIT 1),
                    '+79998887766'
                ) as last_corp_number
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            WHERE u.status = 'fired' OR u.fire_date IS NOT NULL
            ORDER BY 
                CASE 
                    WHEN u.role = 'leader' OR u.role = '2' OR u.role_id = 2 THEN 1
                    WHEN u.role = 'deputy' THEN 2
                    ELSE 3
                END,
                u.fire_date DESC
        """)
        fired_employees_list = cursor.fetchall()
        
        # Форматируем даты для отображения
        for employee in fired_employees_list:
            if employee['fire_date']:
                employee['fire_date_formatted'] = employee['fire_date'].strftime('%d.%m.%Y')
            else:
                employee['fire_date_formatted'] = ''
                
            if employee['hire_date']:
                employee['hire_date_formatted'] = employee['hire_date'].strftime('%d.%m.%Y')
            else:
                employee['hire_date_formatted'] = ''
                
            if employee['birth_date']:
                employee['birth_date_formatted'] = employee['birth_date'].strftime('%d.%m.%Y')
            else:
                employee['birth_date_formatted'] = ''
        
        return render_template('admin/fired_employees.html',
                              total_employees=stats['total_employees'],
                              active_employees=stats['active_employees'],
                              fired_employees=stats['fired_employees'],
                              departments=departments,
                              employees=fired_employees_list)
    
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы уволенных сотрудников: {e}")
        flash(f'Ошибка при получении данных: {str(e)}', 'danger')
        return redirect_based_on_role(current_user)
    
    finally:
        cursor.close()
        connection.close()

@admin_routes_bp.route('/api/update_department_order', methods=['POST'])
@login_required
def update_department_order_api():
    """Обновление порядка отделов через API"""
    logger.debug("Начало выполнения функции update_department_order_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        department_id = data.get('department_id')
        direction = data.get('direction')
        
        if not department_id or not direction:
            logger.warning("ID отдела или направление не указаны")
            return jsonify({'success': False, 'message': 'ID отдела или направление не указаны'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существование отдела
        cursor.execute("SELECT id, name, display_order FROM Department WHERE id = %s", (department_id,))
        department = cursor.fetchone()
        
        if not department:
            logger.warning(f"Отдел с ID={department_id} не найден")
            return jsonify({'success': False, 'message': 'Отдел не найден'}), 404
        
        current_order = department.get('display_order') or 0
        
        if direction == 'up':
            # Найти отдел с меньшим порядком
            cursor.execute("""
                SELECT id, display_order FROM Department 
                WHERE display_order < %s
                ORDER BY display_order DESC
                LIMIT 1
            """, (current_order,))
            prev_dept = cursor.fetchone()
            
            if prev_dept:
                # Меняем местами порядок
                cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                              (current_order, prev_dept['id']))
                cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                              (prev_dept['display_order'], department_id))
                
        elif direction == 'down':
            # Найти отдел с большим порядком
            cursor.execute("""
                SELECT id, display_order FROM Department 
                WHERE display_order > %s
                ORDER BY display_order ASC
                LIMIT 1
            """, (current_order,))
            next_dept = cursor.fetchone()
            
            if next_dept:
                # Меняем местами порядок
                cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                              (current_order, next_dept['id']))
                cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                              (next_dept['display_order'], department_id))
        
        conn.commit()
        
        logger.info(f"Порядок отдела {department['name']} (ID={department_id}) успешно обновлен")
        return jsonify({
            'success': True, 
            'message': f"Порядок отдела успешно обновлен"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении порядка отдела: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении порядка отдела: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/add_employee', methods=['POST'])
@admin_routes_bp.route('/admin/api/add_employee', methods=['POST'])
@login_required
def add_employee_api():
    """Добавление нового сотрудника через API"""
    logger.debug("Начало выполнения функции add_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        # Обязательные поля
        full_name = data.get('full_name')
        department_id = data.get('department_id')
        position = data.get('position')
        role = data.get('role')
        login = data.get('login')
        password = data.get('password')
        corporate_email = data.get('corporate_email')
        
        # Проверка обязательных полей
        if not all([full_name, department_id, position, role, login, password, corporate_email]):
            missing_fields = []
            if not full_name: missing_fields.append('ФИО')
            if not department_id: missing_fields.append('Отдел')
            if not position: missing_fields.append('Должность')
            if not role: missing_fields.append('Роль')
            if not login: missing_fields.append('Логин')
            if not password: missing_fields.append('Пароль')
            if not corporate_email: missing_fields.append('Корпоративная почта')
            
            logger.warning(f"Не заполнены обязательные поля: {', '.join(missing_fields)}")
            return jsonify({
                'success': False, 
                'message': f'Не заполнены обязательные поля: {", ".join(missing_fields)}'
            }), 400
        
        # Дополнительные поля
        Phone = data.get('Phone', '')
        hire_date = data.get('hire_date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, существует ли уже пользователь с таким логином
        cursor.execute("SELECT id FROM User WHERE login = %s", (login,))
        if cursor.fetchone():
            logger.warning(f"Пользователь с логином {login} уже существует")
            return jsonify({
                'success': False, 
                'message': f'Пользователь с логином {login} уже существует'
            }), 400
        
        # Проверяем, существует ли уже пользователь с такой почтой
        cursor.execute("SELECT id FROM User WHERE corporate_email = %s", (corporate_email,))
        if cursor.fetchone():
            logger.warning(f"Пользователь с почтой {corporate_email} уже существует")
            return jsonify({
                'success': False, 
                'message': f'Пользователь с почтой {corporate_email} уже существует'
            }), 400
        
        # Хешируем пароль перед сохранением
        hashed_password = generate_password_hash(password)
        
        # Создаем нового пользователя
        cursor.execute("""
            INSERT INTO User (
                full_name, department_id, position, role, login, password, 
                corporate_email, Phone, hire_date, status, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, 
                %s, %s, %s, %s, %s
            )
        """, (
            full_name, department_id, position, role, login, hashed_password,
            corporate_email, Phone, hire_date, 'offline', datetime.now()
        ))
        
        conn.commit()
        new_employee_id = cursor.lastrowid
        
        logger.info(f"Сотрудник {full_name} успешно добавлен с ID={new_employee_id}")
        return jsonify({
            'success': True, 
            'message': f"Сотрудник {full_name} успешно добавлен",
            'employee_id': new_employee_id
        })
    
    except Exception as e:
        logger.error(f"Ошибка при добавлении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при добавлении сотрудника: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/admin/delete_employee', methods=['POST'])
@login_required
def delete_employee():
    """Полное удаление сотрудника из системы"""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'У вас нет доступа к этой операции'})
    
    try:
        data = request.json
        employee_id = data.get('id')
        
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'})
        
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Проверяем, что сотрудник существует и уволен
        cursor.execute("SELECT id, full_name, status, fire_date FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            return jsonify({'success': False, 'message': 'Сотрудник не найден'})
        
        if employee['fire_date'] is None and employee['status'] != 'fired':
            return jsonify({'success': False, 'message': 'Нельзя удалить активного сотрудника. Сначала его необходимо уволить.'})
        
        # Получаем login сотрудника
        cursor.execute("SELECT login FROM User WHERE id = %s", (employee_id,))
        user_data = cursor.fetchone()
        user_login = user_data['login'] if user_data else None
        
        # Удаляем связанные записи из UserHistory
        cursor.execute("DELETE FROM UserHistory WHERE user_id = %s", (employee_id,))
        
        # Удаляем связанные записи из UserNotifications, если они существуют
        cursor.execute("DELETE FROM UserNotifications WHERE user_id = %s", (employee_id,))
        
        # Удаляем связанные записи из Rating, если они существуют
        cursor.execute("DELETE FROM Rating WHERE user_id = %s", (employee_id,))
        
        # Удаляем связанную запись из Candidates, если она существует
        if user_login:
            cursor.execute("DELETE FROM Candidates WHERE login_pc = %s", (user_login,))
        
        # Удаляем запись из User
        cursor.execute("DELETE FROM User WHERE id = %s", (employee_id,))
        
        connection.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Сотрудник успешно удален'
        })
    
    except Exception as e:
        logger.error(f"Ошибка при удалении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при удалении сотрудника: {str(e)}'}), 500
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@admin_routes_bp.route('/api/update_employee', methods=['POST'])
@admin_routes_bp.route('/admin/api/update_employee', methods=['POST'])
@login_required
def update_employee():
    """Обновление данных сотрудника через API (form-data)"""
    logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования
    logger.debug("=== Начало функции update_employee ===")
    logger.debug(f"Текущий пользователь: {current_user.login}, роль: {current_user.role}")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        # Проверяем наличие данных - поддерживаем как JSON, так и form-data
        data_source = None
        if request.json:
            data_source = request.json
            logger.debug("Получены данные в JSON формате")
        elif request.form:
            data_source = request.form
            logger.debug("Получены данные в form-data формате")
        else:
            logger.warning("Данные не получены в запросе (ни JSON, ни form-data)")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
            
        # Получаем ID сотрудника из любого источника
        employee_id = data_source.get('employee_id') or data_source.get('id')
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400

        # Логируем все полученные данные
        logger.debug("=== Полученные данные ===")
        logger.debug(f"Все поля данных: {dict(data_source) if hasattr(data_source, 'keys') else data_source}")
        if request.files:
            logger.debug(f"Все файлы: {dict(request.files)}")
        logger.debug("=== Конец данных ===")

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Получаем текущие данные сотрудника
        cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404

        # Проверяем, нужно ли удалить фото (только для form-data)
        if data_source.get('delete_photo') == '1':
            try:
                # Получаем текущее фото
                cursor.execute("SELECT photo_url FROM EmployeePhotos WHERE employee_id = %s", (employee_id,))
                photo = cursor.fetchone()
                
                if photo and photo['photo_url']:
                    # Удаляем файл с диска
                    file_path = os.path.join(current_app.root_path, photo['photo_url'].lstrip('/'))
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    # Удаляем запись из БД
                    cursor.execute("DELETE FROM EmployeePhotos WHERE employee_id = %s", (employee_id,))
                    conn.commit()
                    logger.info(f"Фото сотрудника {employee_id} успешно удалено")
            except Exception as e:
                logger.error(f"Ошибка при удалении фото: {str(e)}")
                return jsonify({'success': False, 'message': f'Ошибка при удалении фото: {str(e)}'}), 500

        # Обработка фото, если оно было загружено
        if 'employee_photo' in request.files:
            photo_file = request.files['employee_photo']
            if photo_file and photo_file.filename:
                try:
                    # Проверяем тип файла
                    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                    if not photo_file.filename.lower().endswith(tuple(allowed_extensions)):
                        return jsonify({'success': False, 'message': 'Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF'}), 400
                    
                    # Проверяем размер файла (максимум 5MB)
                    if photo_file.content_length and photo_file.content_length > 5 * 1024 * 1024:
                        return jsonify({'success': False, 'message': 'Размер файла превышает 5MB'}), 400
                    
                    # Генерируем уникальное имя файла
                    filename = secure_filename(f"{employee_id}_{int(time.time())}_{photo_file.filename}")
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'employee_photos')
                    
                    # Создаем директорию, если она не существует
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # Сохраняем файл
                    file_path = os.path.join(upload_folder, filename)
                    photo_file.save(file_path)
                    
                    # Относительный путь для сохранения в БД
                    relative_path = f'/static/uploads/employee_photos/{filename}'
                    
                    # Проверяем, есть ли уже фото у сотрудника
                    cursor.execute("SELECT id FROM EmployeePhotos WHERE employee_id = %s", (employee_id,))
                    existing_photo = cursor.fetchone()
                    
                    if existing_photo:
                        # Обновляем существующее фото
                        cursor.execute("UPDATE EmployeePhotos SET photo_url = %s WHERE employee_id = %s", 
                                    (relative_path, employee_id))
                    else:
                        # Добавляем новое фото
                        cursor.execute("INSERT INTO EmployeePhotos (employee_id, photo_url) VALUES (%s, %s)", 
                                    (employee_id, relative_path))
                    
                    conn.commit()
                    logger.info(f"Фото сотрудника {employee_id} успешно сохранено: {file_path}")
                    
                except Exception as e:
                    logger.error(f"Ошибка при сохранении фото: {str(e)}")
                    return jsonify({'success': False, 'message': f'Ошибка при сохранении фото: {str(e)}'}), 500

        # Подготовка данных для обновления
        update_data = {}
        fields_to_update = [
            'full_name', 'department_id', 'position', 'role_id',
            'Phone', 'corporate_email', 'personal_email', 'pc_login', 'pc_password',
            'crm_id', 'hire_date', 'birth_date', 'notes', 'office', 'fire_date',
            'corp_phone', 'login', 'documents', 'rr', 'site', 'crm_login', 'crm_password'
        ]

        # Обработка чекбоксов
        boolean_fields = ['documents', 'rr', 'site']
        logger.debug("=== Обработка чекбоксов ===")
        for field in boolean_fields:
            if field in data_source:
                # Для JSON данных - проверяем на true/false
                if isinstance(data_source, dict):
                    value = 1 if data_source.get(field) in [True, 'true', 'on', '1', 1] else 0
                else:
                    # Для form-data
                    value = 1 if data_source.get(field) == 'on' else 0
                update_data[field] = value
                logger.debug(f"Чекбокс {field}: {value}")
            else:
                update_data[field] = 0
                logger.debug(f"Чекбокс {field} не установлен, значение: 0")

        # Обработка текстовых полей и остальных данных
        logger.debug("=== Обработка текстовых полей ===")
        for field in fields_to_update:
            if field in boolean_fields:
                continue  # Чекбоксы уже обработаны выше
                
            if field in data_source and field not in ['hire_date', 'birth_date']:
                value = data_source.get(field)
                if value is not None:
                    # Специальная обработка для поля login - не обновляем если пустое
                    if field == 'login' and (value == '' or value is None):
                        logger.debug(f"Поле login пустое, пропускаем обновление")
                        continue
                    
                    # Разрешаем пустые строки для некоторых полей
                    update_data[field] = value if value != '' else None
                    logger.debug(f"Текстовое поле {field}: {value if value != '' else 'NULL'}")
        
        # Специальная обработка для роли (может приходить как role или role_id)
        if 'role' in data_source and data_source.get('role'):
            update_data['role'] = data_source.get('role')
            logger.debug(f"Поле role: {data_source.get('role')}")
        elif 'role_id' in data_source and data_source.get('role_id'):
            update_data['role'] = data_source.get('role_id')
            logger.debug(f"Поле role (из role_id): {data_source.get('role_id')}")

        # Обработка дат
        for date_field in ['hire_date', 'birth_date', 'fire_date']:
            if date_field in data_source and data_source.get(date_field):
                try:
                    date_value = datetime.strptime(data_source.get(date_field), '%Y-%m-%d').date()
                    update_data[date_field] = date_value
                except ValueError:
                    logger.warning(f"Неверный формат даты для поля {date_field}: {data_source.get(date_field)}")
        
        # Обработка статуса - только если он действительно изменился
        if 'status' in data_source:
            status_value = data_source.get('status')
            if status_value:
                # Преобразуем длинные статусы в короткие коды
                status_mapping = {
                    'Онлайн': 'online',
                    'Офлайн': 'offline', 
                    'Активен': 'active',
                    'Заблокирован': 'blocked',
                    'Уволен': 'fired'
                }
                final_status = status_mapping.get(status_value, status_value)
                
                # Обновляем статус только если он отличается от текущего
                if final_status != employee.get('status'):
                    update_data['status'] = final_status
                    logger.debug(f"Поле status изменено: {employee.get('status')} -> {final_status}")
                else:
                    logger.debug(f"Поле status не изменилось: {final_status}")
            else:
                logger.debug(f"Поле status пустое, пропускаем обновление")
        else:
            logger.debug(f"Поле status не передано, пропускаем обновление")

        # Если есть поля для обновления
        if update_data:
            # Формируем SQL-запрос для обновления
            update_query = "UPDATE User SET "
            update_values = []
            
            for field, value in update_data.items():
                update_query += f"{field} = %s, "
                update_values.append(value)
                
                # Логируем изменение в историю
                if field in employee and str(employee[field]) != str(value):
                    cursor.execute("""
                        INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (employee_id, field, str(employee[field]), str(value), current_user.id))
                
            update_query = update_query.rstrip(", ") + " WHERE id = %s"
            update_values.append(employee_id)

            # Логируем финальный SQL запрос и значения
            logger.debug("=== Финальный SQL запрос ===")
            logger.debug(f"SQL запрос: {update_query}")
            logger.debug(f"Значения: {update_values}")
            logger.debug("=== Конец отладки SQL ===")

            # Выполняем обновление
            cursor.execute(update_query, tuple(update_values))
            conn.commit()
            
            logger.info(f"Данные сотрудника с ID={employee_id} успешно обновлены")
            return jsonify({'success': True, 'message': 'Данные сотрудника успешно обновлены'})
        else:
            logger.info(f"Нет изменений для сотрудника с ID={employee_id}")
            return jsonify({'success': True, 'message': 'Нет изменений для сохранения'})
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении данных: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/employee_history/<int:employee_id>', methods=['GET'])
@login_required
def employee_history(employee_id):
    """Получение истории изменений сотрудника через прямой ID в пути"""
    logger.debug(f"Запрос истории для сотрудника с ID={employee_id} через прямой путь")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Проверяем существование сотрудника
        cursor.execute("SELECT id FROM User WHERE id = %s", (employee_id,))
        if not cursor.fetchone():
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404

        # Получаем историю изменений
        cursor.execute("""
            SELECT 
                uh.*,
                u.full_name as changed_by_name,
                CASE 
                    WHEN uh.changed_field = 'department_id' THEN 'Отдел'
                    WHEN uh.changed_field = 'position' THEN 'Должность'
                    WHEN uh.changed_field = 'role' THEN 'Роль'
                    WHEN uh.changed_field = 'Phone' THEN 'Личный телефон'
                    WHEN uh.changed_field = 'corp_phone' THEN 'Корпоративный телефон'
                    WHEN uh.changed_field = 'corporate_email' THEN 'Корпоративная почта'
                    WHEN uh.changed_field = 'personal_email' THEN 'Личная почта'
                    WHEN uh.changed_field = 'pc_login' THEN 'Логин ПК'
                    WHEN uh.changed_field = 'pc_password' THEN 'Пароль ПК'
                    WHEN uh.changed_field = 'documents' THEN 'Документы'
                    WHEN uh.changed_field = 'rr' THEN 'РР'
                    WHEN uh.changed_field = 'site' THEN 'Сайт'
                    WHEN uh.changed_field = 'crm_id' THEN 'CRM ID'
                    ELSE uh.changed_field
                END as field_name
            FROM UserHistory uh
            LEFT JOIN User u ON uh.changed_by = u.id
            WHERE uh.user_id = %s
            ORDER BY uh.changed_at DESC
        """, (employee_id,))
        
        history = cursor.fetchall()
        
        # Проверка наличия истории
        if not history:
            logger.info(f"История изменений для сотрудника с ID={employee_id} пуста")
            return jsonify({'success': True, 'history': []})
        
        # Форматируем даты
        for record in history:
            record['changed_at'] = record['changed_at'].strftime('%d.%m.%Y %H:%M:%S')
            
        logger.info(f"История изменений для сотрудника с ID={employee_id} успешно получена")
        return jsonify({'success': True, 'history': history})
        
    except Exception as e:
        logger.error(f"Ошибка при получении истории изменений: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении истории изменений: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/phone_numbers')
@login_required
def phone_numbers():
    """Страница управления корпоративными номерами"""
    logger.debug("Начало выполнения функции phone_numbers")
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        flash('У вас нет доступа к этой странице', 'error')
        return redirect_based_on_role(current_user)
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем список отделов с id, name и display_order
        cursor.execute('SELECT id, name, display_order FROM Department ORDER BY display_order ASC, name ASC')
        departments = cursor.fetchall()
        
        # Создаем словарь соответствия id -> name для отделов
        department_dict = {str(dept['id']): dept['name'] for dept in departments}
        
        # Создаем словарь соответствия name -> id для отделов
        dept_id_map = {dept['name']: dept['id'] for dept in departments}
        
        # Получаем номера из таблицы corp_numbers с присоединением Department
        query = """
            SELECT 
                cn.id, 
                cn.phone_number, 
                cn.department, 
                cn.assigned_to, 
                cn.prohibit_issuance,
                cn.whatsapp, 
                cn.telegram, 
                cn.blocked,
                d.name as department_name,
                d.id as department_id,
                d.display_order
            FROM corp_numbers cn
            LEFT JOIN Department d ON cn.department = CAST(d.id AS CHAR)
            ORDER BY d.display_order ASC, cn.phone_number
        """
        cursor.execute(query)
        numbers = cursor.fetchall()
        
        # Группируем номера по отделам для отображения на странице
        departments_dict = {}
        
        # Первый проход: создаем пустые списки для всех отделов, сохраняя порядок отображения
        ordered_departments = []
        
        for dept in departments:
            department_name = dept['name']
            departments_dict[department_name] = []
            ordered_departments.append(department_name)
        
        # Второй проход: добавляем номера в соответствующие отделы
        for number in numbers:
            dept_id = number['department']
            
            # Если у номера есть department_name из JOIN, используем его
            if number.get('department_name'):
                # Сохраняем название отдела для отображения
                department_name = number['department_name']
                
                # Добавляем название отдела в номер для отображения в шаблоне
                number['department_display'] = department_name
            else:
                # Если нет результата JOIN, пробуем найти название в словаре
                department_name = department_dict.get(dept_id, f"Отдел {dept_id}")
                
                # Добавляем название отдела в номер для отображения в шаблоне
                number['department_display'] = department_name
            
            # Добавляем номер в список соответствующего отдела, если отдел существует
            if department_name in departments_dict:
                departments_dict[department_name].append(number)
        
        # Создаем OrderedDict для сохранения порядка отделов
        from collections import OrderedDict
        ordered_departments_dict = OrderedDict()
        for dept_name in ordered_departments:
            if dept_name in departments_dict:
                ordered_departments_dict[dept_name] = departments_dict[dept_name]
        
        # Подсчет статистики по номерам
        total_numbers = len(numbers)
        assigned_numbers = sum(1 for n in numbers if n.get('assigned_to'))
        free_numbers = total_numbers - assigned_numbers
        prohibited_numbers = sum(1 for n in numbers if n.get('prohibit_issuance'))
        
        logger.debug(f"Получено {len(departments)} отделов и {total_numbers} номеров")
        
        # Дополнительная статистика для шаблона
        whatsapp_count = sum(1 for n in numbers if n.get('whatsapp'))
        telegram_count = sum(1 for n in numbers if n.get('telegram'))
        
        # Получаем список свободных номеров (без assigned_to)
        free_numbers_list = [n for n in numbers if not n.get('assigned_to')]
        
        # Группируем номера по отделам для передачи в шаблон
        departments_with_numbers = []
        for dept in departments:
            dept_numbers = [n for n in numbers if str(n.get('department')) == str(dept['id'])]
            if dept_numbers:  # Только отделы с номерами
                dept_copy = dict(dept)
                dept_copy['phone_numbers'] = dept_numbers
                departments_with_numbers.append(dept_copy)
        
        return render_template('admin/phone_numbers.html',
                               numbers=numbers,
                               departments=departments_with_numbers,
                               dept_id_map=dept_id_map,
                               total_numbers=total_numbers,
                               assigned_numbers=assigned_numbers,
                               free_numbers_count=free_numbers,
                               prohibited_numbers=prohibited_numbers,
                               whatsapp_count=whatsapp_count,
                               telegram_count=telegram_count,
                               free_numbers=free_numbers_list)
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы корпоративных номеров: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return redirect_based_on_role(current_user)
    finally:
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/personnel_dashboard')
@login_required  
def personnel_dashboard():
    """Страница дашборда персонала с чистыми стилями"""
    logger.debug("Начало выполнения функции personnel_dashboard")
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        flash('У вас нет доступа к этой странице', 'error')
        return redirect_based_on_role(current_user)
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получение статистики
        cursor.execute("SELECT COUNT(*) as total FROM User WHERE fire_date IS NULL")
        total_employees = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as active FROM User WHERE status = 'online' AND fire_date IS NULL")
        active_employees = cursor.fetchone()['active']

        cursor.execute("SELECT COUNT(*) as fired FROM User WHERE fire_date IS NOT NULL")
        fired_employees = cursor.fetchone()['fired']

        cursor.execute("SELECT COUNT(*) as departments FROM Department")
        departments_count = cursor.fetchone()['departments']

        # Получение данных для графиков
        cursor.execute("""
            SELECT DATE(hire_date) as date, COUNT(*) as count 
            FROM User
            WHERE hire_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(hire_date)
            ORDER BY date
        """)
        staff_dynamics = cursor.fetchall()

        dates = []
        staff_counts = []
        for item in staff_dynamics:
            if item['date']:
                dates.append(item['date'].strftime('%d.%m'))
                staff_counts.append(item['count'])

        # Распределение по отделам
        cursor.execute("""
            SELECT d.name, COUNT(u.id) as count
            FROM Department d
            LEFT JOIN User u ON d.id = u.department_id AND u.fire_date IS NULL
            GROUP BY d.id, d.name
            ORDER BY count DESC
        """)
        department_distribution = cursor.fetchall()

        department_names = [dept['name'] for dept in department_distribution]
        department_counts = [dept['count'] for dept in department_distribution]

        # Последние наймы
        cursor.execute("""
            SELECT u.full_name, u.position, d.name as department, 
                   DATE_FORMAT(u.hire_date, '%d.%m.%Y') as hire_date
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            WHERE u.hire_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            ORDER BY u.hire_date DESC
            LIMIT 10
        """)
        recent_hires = cursor.fetchall()

        # Последние увольнения
        cursor.execute("""
            SELECT u.full_name, u.position, d.name as department,
                   DATE_FORMAT(u.fire_date, '%d.%m.%Y') as fire_date
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            WHERE u.fire_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            ORDER BY u.fire_date DESC
            LIMIT 10
        """)
        recent_fires = cursor.fetchall()

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

    except Exception as e:
        logger.error(f"Ошибка при загрузке дашборда персонала: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return redirect_based_on_role(current_user)
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/test_route')
def test_blueprint_route():
    """Тестовый маршрут для проверки работы blueprint"""
    logger.critical("Тестовый маршрут сработал!")
    return jsonify({
        'success': True,
        'message': 'Тестовый маршрут успешно вызван',
        'blueprint': 'admin_routes_bp',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@admin_routes_bp.route('/api/update_department_positions', methods=['POST'])
@admin_routes_bp.route('/admin/api/update_department_positions', methods=['POST'])
@login_required
def update_department_positions_api():
    """Обновление должностей в отделе"""
    # ... (логика)
    logger.critical("=================== НАЧАЛО ДАННЫХ ЗАПРОСА ===================")
    # ... (логика)
    logger.critical("=================== КОНЕЦ ДАННЫХ ЗАПРОСА ===================")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        dragged_id = data.get('dragged_id')
        target_id = data.get('target_id')
        position = data.get('position')  # 'before' или 'after'
        
        logger.debug(f"Получены данные: dragged_id={dragged_id}, target_id={target_id}, position={position}")
        
        if not dragged_id or not target_id or not position:
            logger.warning("Не указаны ID отделов или позиция")
            return jsonify({'success': False, 'message': 'Не указаны ID отделов или позиция'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существование отделов
        cursor.execute("SELECT id, name, display_order FROM Department WHERE id IN (%s, %s)", 
                     (dragged_id, target_id))
        departments = cursor.fetchall()
        
        logger.debug(f"Найдены отделы: {departments}")
        
        if len(departments) != 2:
            logger.warning(f"Один или оба отдела не найдены: dragged_id={dragged_id}, target_id={target_id}")
            return jsonify({'success': False, 'message': 'Один или оба отдела не найдены'}), 404
        
        # Находим отделы по ID
        dragged_dept = next((d for d in departments if str(d['id']) == str(dragged_id)), None)
        target_dept = next((d for d in departments if str(d['id']) == str(target_id)), None)
        
        if not dragged_dept or not target_dept:
            logger.warning(f"Не удалось идентифицировать отделы: dragged_dept={dragged_dept}, target_dept={target_dept}")
            return jsonify({'success': False, 'message': 'Не удалось идентифицировать отделы'}), 500
        
        # Убеждаемся, что у всех отделов установлен порядковый номер
        cursor.execute("SELECT id, display_order FROM Department ORDER BY display_order")
        all_departments = cursor.fetchall()
        
        # Проверяем наличие порядковых номеров и обновляем, если отсутствуют
        for i, dept in enumerate(all_departments):
            if dept['display_order'] is None:
                cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                             (i + 1, dept['id']))
        
        # Если позиция 'before', перемещаем перед целевым отделом
        if position == 'before':
            target_order = target_dept['display_order']
            
            # Увеличиваем порядковый номер для всех отделов, которые идут после целевого
            cursor.execute("""
                UPDATE Department 
                SET display_order = display_order + 1 
                WHERE display_order >= %s AND id != %s
            """, (target_order, dragged_id))
            
            # Устанавливаем новый порядковый номер для перетаскиваемого отдела
            cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                         (target_order, dragged_id))
            
        # Если позиция 'after', перемещаем после целевого отдела
        elif position == 'after':
            target_order = target_dept['display_order']
            
            # Увеличиваем порядковый номер для всех отделов, которые идут после целевого + 1
            cursor.execute("""
                UPDATE Department 
                SET display_order = display_order + 1 
                WHERE display_order > %s AND id != %s
            """, (target_order, dragged_id))
            
            # Устанавливаем новый порядковый номер для перетаскиваемого отдела
            cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                         (target_order + 1, dragged_id))
        
        conn.commit()
        
        # Финальная перенумерация для предотвращения пробелов и дублирования
        cursor.execute("SELECT id FROM Department ORDER BY display_order")
        ordered_departments = cursor.fetchall()
        
        for i, dept in enumerate(ordered_departments):
            cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                         (i + 1, dept['id']))
        
        conn.commit()
        
        logger.info(f"Порядок отделов успешно обновлен: отдел {dragged_id} перемещен {position} отдела {target_id}")
        return jsonify({
            'success': True, 
            'message': f"Порядок отделов успешно обновлен"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении порядка отделов: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Ошибка при обновлении порядка отделов: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/api/delete_number', methods=['POST'])
@login_required
def delete_number_api():
    """Удаление номера"""
    logger.debug("Начало выполнения функции delete_number_api")
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    data = request.get_json()
    number_id = data.get('number_id')
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Получаем данные номера перед удалением для лога
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        # Удаляем номер
        cursor.execute("DELETE FROM corp_numbers WHERE id = %s", (number_id,))
        conn.commit()
        # Логируем удаление
        try:
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number)
                VALUES (%s, %s)
            """, (
                current_user.id,
                number_data['phone_number']
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        return jsonify({'success': True, 'message': 'Номер успешно удален'})
    except Exception as e:
        logger.error(f"Ошибка при удалении номера: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при удалении номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/api/move_number', methods=['POST'])
@login_required
def move_number_api():
    """Перемещение номера между отделами"""
    logger.debug("Начало выполнения функции move_number_api")
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    data = request.get_json()
    number_id = data.get('number_id')
    new_department = data.get('new_department')
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Получаем текущие данные для лога
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        # Если перемещаем в свободные номера
        if new_department is None or new_department == '' or new_department == 'free':
            cursor.execute("UPDATE corp_numbers SET department = NULL, assigned_to = NULL WHERE id = %s", (number_id,))
            note = "Номер перемещен в свободные номера"
        else:
            cursor.execute("UPDATE corp_numbers SET department = %s, assigned_to = NULL WHERE id = %s", (new_department, number_id))
            note = f"Номер перемещен в отдел {new_department}"
        conn.commit()
        # Логируем перемещение
        try:
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, new_number, note)
                VALUES (%s, %s, %s, %s)
            """, (
                current_user.id,
                number_data['phone_number'],
                new_department if new_department else 'free',
                note
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        return jsonify({'success': True, 'message': note})
    except Exception as e:
        logger.error(f"Ошибка при перемещении номера: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при перемещении номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/api/free_numbers', methods=['GET'])
@login_required
def get_free_numbers_api():
    """Получение списка свободных номеров"""
    if current_user.role not in ['admin', 'leader']:
        return jsonify({'success': False, 'message': 'Недостаточно прав'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем свободные номера
        cursor.execute("""
            SELECT id, phone_number
            FROM PhoneNumbers 
            WHERE department_id IS NULL 
               OR assigned_to IS NULL 
               OR assigned_to = ''
            ORDER BY phone_number
        """)
        free_numbers = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'free_numbers': free_numbers
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении свободных номеров: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})
    finally:
        if 'conn' in locals():
            conn.close()

# ==========================================================================
# API ДЛЯ УПРАВЛЕНИЯ СТАТУСОМ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================================================

@admin_routes_bp.route('/api/heartbeat', methods=['POST'])
@admin_routes_bp.route('/admin/api/heartbeat', methods=['POST'])
@login_required
def heartbeat():
    """Обновление статуса активности пользователя"""
    try:
        user_id = current_user.id
        
        conn = create_db_connection()
        cursor = conn.cursor()
        
        # Обновляем статус пользователя на короткий код
        cursor.execute("UPDATE User SET status = %s, last_active = NOW() WHERE id = %s", 
                      ('online', user_id))
        
        # Проверяем, есть ли уже запись для пользователя в UserActivity
        cursor.execute("SELECT id FROM UserActivity WHERE user_id = %s", (user_id,))
        activity = cursor.fetchone()
        
        if activity:
            # Обновляем существующую запись
            cursor.execute(
                "UPDATE UserActivity SET status = %s, last_activity = NOW(), updated_at = NOW() WHERE user_id = %s", 
                ('online', user_id)
            )
        else:
            # Создаем новую запись
            cursor.execute(
                "INSERT INTO UserActivity (user_id, status, last_activity) VALUES (%s, %s, NOW())", 
                (user_id, 'online')
            )
        
        conn.commit()
        return jsonify({'success': True, 'status': 'online'})
        
    except Exception as e:
        logger.error(f"Ошибка при отправке heartbeat: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_positions', methods=['GET'])
@admin_routes_bp.route('/admin/api/get_positions', methods=['GET'])
@login_required
def get_positions_api():
    """Получение списка должностей"""
    logger.debug("Начало выполнения функции get_positions_api")
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем все должности
        cursor.execute("SELECT id, name, description FROM Position ORDER BY name")
        positions = cursor.fetchall()
        
        logger.info(f"Получено {len(positions)} должностей")
        return jsonify({'success': True, 'positions': positions})
        
    except Exception as e:
        logger.error(f"Ошибка при получении должностей: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении должностей: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_roles', methods=['GET'])
@admin_routes_bp.route('/admin/api/get_roles', methods=['GET'])
@login_required
def get_roles_api():
    """Получение списка ролей"""
    logger.debug("Начало выполнения функции get_roles_api")
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем все роли
        cursor.execute("SELECT id, name, description FROM Role ORDER BY name")
        roles = cursor.fetchall()
        
        logger.info(f"Получено {len(roles)} ролей")
        return jsonify({'success': True, 'roles': roles})
        
    except Exception as e:
        logger.error(f"Ошибка при получении ролей: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении ролей: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/admin/impersonate/<int:employee_id>')
@admin_routes_bp.route('/impersonate/<int:employee_id>')
@login_required
def impersonate_employee(employee_id):
    """Вход под другим пользователем (только для администраторов)"""
    logger.debug(f"Начало выполнения функции impersonate_employee для сотрудника {employee_id}")
    
    if current_user.role != 'admin':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        flash('У вас нет прав для входа под другим пользователем', 'error')
        return redirect(url_for('admin_routes_unique.personnel'))
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем данные сотрудника
        cursor.execute("""
            SELECT id, login, full_name, role, department_id 
            FROM User 
            WHERE id = %s AND fire_date IS NULL
        """, (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден или уволен")
            flash('Сотрудник не найден или уволен', 'error')
            return redirect(url_for('admin_routes_unique.personnel'))
        
        # Сохраняем данные администратора для возврата
        session['admin_user_id'] = current_user.id
        session['admin_full_name'] = current_user.full_name

        # Создаём объект User для сотрудника
        normalized_role = normalize_role(employee['role'])
        impersonated_user = User(
            id=employee['id'],
            login=employee['login'],
            password='',  # пароль не нужен для login_user
            full_name=employee['full_name'],
            role=normalized_role,
            department=employee.get('department_id')
        )
        # Вручную устанавливаем "сырые" данные о роли для свойства roles
        impersonated_user._roles = [impersonated_user.create_role_object(normalized_role)]

        # Логинимся как сотрудник
        login_user(impersonated_user, force=True)

        # Сохраняем данные в сессии (как при обычном логине)
        session['username'] = impersonated_user.login
        session['id'] = impersonated_user.id
        session['role'] = impersonated_user.role
        session['full_name'] = impersonated_user.full_name
        session['department'] = impersonated_user.department
        session.permanent = True

        logger.info(f"Администратор {current_user.login} вошел под пользователем {impersonated_user.login} ({impersonated_user.full_name})")
        flash(f'Вы вошли как {impersonated_user.full_name}', 'success')

        # Перенаправляем в зависимости от роли сотрудника
        if impersonated_user.role == 'user':
            return redirect(url_for('broker.broker_dashboard'))
        elif impersonated_user.role == 'admin':
            return redirect(url_for('admin_routes_unique.personnel'))
        else:
            return redirect(url_for('main.index'))
        
    except Exception as e:
        logger.error(f"Ошибка при входе под пользователем: {str(e)}")
        flash('Произошла ошибка при входе под пользователем', 'error')
        return redirect(url_for('admin_routes_unique.personnel'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/admin/stop_impersonation')
@admin_routes_bp.route('/stop_impersonation')
@login_required
def stop_impersonation():
    """Остановка impersonation и возврат к администратору"""
    logger.debug("Начало выполнения функции stop_impersonation")
    
    if 'admin_user_id' not in session:
        flash('Вы не находитесь в режиме impersonation', 'error')
        return redirect(url_for('main.index'))
    
    try:
        admin_user_id = session.get('admin_user_id')
        if not admin_user_id:
            flash('Сессионные данные администратора не найдены', 'error')
            return redirect(url_for('main.index'))

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, login, full_name, role, department_id FROM User WHERE id=%s", (admin_user_id,))
        admin_data = cursor.fetchone()
        if not admin_data:
            flash('Администратор не найден', 'error')
            return redirect(url_for('main.index'))

        admin_user = User(
            id=admin_data['id'],
            login=admin_data['login'],
            password='',
            full_name=admin_data['full_name'],
            role=admin_data['role'],
            department=admin_data.get('department_id')
        )

        login_user(admin_user, force=True)

        # Восстанавливаем сессию администратора
        session['username'] = admin_user.login
        session['id'] = admin_user.id
        session['role'] = admin_user.role
        session['full_name'] = admin_user.full_name
        session['department'] = admin_user.department
        session.permanent = True

        session.pop('admin_user_id', None)
        session.pop('admin_full_name', None)

        logger.info("Impersonation остановлен, возврат к администратору")
        flash('Вы вернулись к своему аккаунту', 'success')

        # Возвращаемся к администратору
        return redirect(url_for('admin_routes_unique.personnel'))
        
    except Exception as e:
        logger.error(f"Ошибка при остановке impersonation: {str(e)}")
        flash('Произошла ошибка при возврате к своему аккаунту', 'error')
        return redirect(url_for('main.index'))

@admin_routes_bp.route('/api/get_employee_history', methods=['GET'])
@admin_routes_bp.route('/admin/api/get_employee_history', methods=['GET'])
@login_required
def get_employee_history_api():
    """Получение истории действий с сотрудником"""
    logger.debug("Начало выполнения функции get_employee_history_api")
    
    try:
        employee_id = request.args.get('id')
        if not employee_id:
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
            
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем историю действий
        cursor.execute("""
            SELECT 
                uh.id,
                uh.changed_field,
                uh.old_value,
                uh.new_value,
                uh.changed_at,
                uh.changed_by,
                u.full_name as changed_by_name
            FROM UserHistory uh
            LEFT JOIN User u ON uh.changed_by = u.id
            WHERE uh.user_id = %s
            ORDER BY uh.changed_at DESC
            LIMIT 20
        """, (employee_id,))
        
        history = cursor.fetchall()
        
        # Форматируем даты и добавляем описание действия
        for record in history:
            if record['changed_at']:
                record['created_at'] = record['changed_at'].strftime('%d.%m.%Y %H:%M')
            
            # Создаем описание действия
            field_name = record.get('changed_field', 'Поле')
            old_val = record.get('old_value', 'не указано')
            new_val = record.get('new_value', 'не указано')
            
            # Переводим названия полей на русский
            field_translations = {
                'full_name': 'ФИО',
                'position': 'Должность', 
                'department_id': 'Отдел',
                'department': 'Отдел',
                'Phone': 'Личный телефон',
                'corp_phone': 'Корпоративный телефон',
                'corporate_email': 'Корпоративная почта',
                'personal_email': 'Личная почта',
                'pc_login': 'Логин ПК',
                'pc_password': 'Пароль ПК',
                'crm_id': 'CRM ID',
                'crm_login': 'Логин CRM',
                'crm_password': 'Пароль CRM',
                'documents': 'Документы',
                'rr': 'RR доступ',
                'site': 'Доступ к сайту',
                'role': 'Роль',
                'role_id': 'Роль в системе',
                'status': 'Статус',
                'hire_date': 'Дата приема на работу',
                'birth_date': 'Дата рождения',
                'fire_date': 'Дата увольнения',
                'notes': 'Комментарии',
                'office': 'Офис',
                'login': 'Логин в систему',
                'last_active': 'Последняя активность',
                'block_reason': 'Причина блокировки',
                'unblock_reason': 'Причина разблокировки'
            }
            
            translated_field = field_translations.get(field_name, field_name)
            
            # Специальная обработка для причин блокировки/разблокировки
            if field_name in ['block_reason', 'unblock_reason']:
                record['description'] = f"{translated_field}: {new_val}"
            else:
                record['description'] = f"{translated_field}: '{old_val}' → '{new_val}'"
            record['action_type'] = 'updated'
        
        logger.info(f"Получено {len(history)} записей истории для сотрудника {employee_id}")
        return jsonify({'success': True, 'history': history})
        
    except Exception as e:
        logger.error(f"Ошибка при получении истории сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении истории: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/move_employee', methods=['POST'])
@admin_routes_bp.route('/admin/api/move_employee', methods=['POST'])
@login_required
def move_employee_api():
    """Перемещение сотрудника в другой отдел"""
    logger.debug("Начало выполнения функции move_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
            
        employee_id = data.get('employee_id')
        new_department_id = data.get('new_department_id')
        
        if not employee_id or not new_department_id:
            return jsonify({'success': False, 'message': 'Не указаны необходимые данные'}), 400

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существование сотрудника
        cursor.execute("SELECT id, full_name, department_id FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        if not employee:
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
            
        # Проверяем существование отдела
        cursor.execute("SELECT id, name FROM Department WHERE id = %s", (new_department_id,))
        department = cursor.fetchone()
        if not department:
            return jsonify({'success': False, 'message': 'Отдел не найден'}), 404
        
        # Обновляем отдел сотрудника
        cursor.execute("UPDATE User SET department_id = %s WHERE id = %s", (new_department_id, employee_id))
        conn.commit()
        
        logger.info(f"Сотрудник {employee['full_name']} (ID: {employee_id}) перемещен в отдел {department['name']} (ID: {new_department_id})")
        
        return jsonify({
            'success': True, 
            'message': f"Сотрудник {employee['full_name']} успешно перемещен в отдел {department['name']}"
        })
        
    except Exception as e:
        logger.error(f"Ошибка при перемещении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при перемещении сотрудника: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_fired_employee', methods=['GET'])
@admin_routes_bp.route('/admin/api/get_fired_employee', methods=['GET'])
@login_required
def get_fired_employee_api():
    """Получение данных уволенного сотрудника по ID"""
    logger.debug("Начало выполнения функции get_fired_employee_api")
    
    if current_user.role not in ['admin', 'leader']:
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        # Получаем ID сотрудника из запроса
        employee_id = request.args.get('id')
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
            
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем данные уволенного сотрудника с дополнительными полями
        query = """
            SELECT 
                u.id, u.full_name, u.login, u.Phone,
                u.department_id, u.role, u.role_id, u.hire_date, u.fire_date,
                u.fired, u.personal_email, u.pc_login, u.pc_password,
                u.birth_date, u.position, u.office, u.corporate_email,
                u.corp_phone, u.documents, u.rr, u.site, u.crm_id,
                u.notes, u.status, u.last_active, u.crm_login, u.crm_password,
                d.name as department_name,
                ep.photo_url,
                DATEDIFF(u.fire_date, u.hire_date) as days_worked,
                COALESCE(
                    (SELECT pnh.new_number 
                     FROM phone_numbers_history pnh 
                     WHERE pnh.operator_id = u.id 
                     ORDER BY pnh.changed_at DESC 
                     LIMIT 1),
                    '+79998887766'
                ) as last_corp_number
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            LEFT JOIN EmployeePhotos ep ON u.id = ep.employee_id
            WHERE u.id = %s AND (u.status = 'fired' OR u.fire_date IS NOT NULL)
        """
        logger.debug(f"SQL запрос для получения данных уволенного сотрудника: {query}")
        cursor.execute(query, (employee_id,))
        employee = cursor.fetchone()

        if not employee:
            logger.warning(f"Уволенный сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Уволенный сотрудник не найден'}), 404
            
        # Логируем полученные данные
        logger.debug(f"Полученные данные уволенного сотрудника: {employee}")

        # Преобразуем даты в строковый формат для JSON
        if employee.get('hire_date'):
            hire_date_obj = employee['hire_date']
            employee['hire_date'] = hire_date_obj.strftime('%Y-%m-%d')
            employee['hire_date_formatted'] = hire_date_obj.strftime('%d.%m.%Y')
        if employee.get('fire_date'):
            fire_date_obj = employee['fire_date']
            employee['fire_date'] = fire_date_obj.strftime('%Y-%m-%d')
            employee['fire_date_formatted'] = fire_date_obj.strftime('%d.%m.%Y')
        if employee.get('birth_date'):
            birth_date_obj = employee['birth_date']
            employee['birth_date_formatted'] = birth_date_obj.strftime('%d.%m.%Y')
        
        # Формируем полный URL для фотографии
        if employee.get('photo_url'):
            # Если путь уже содержит /static/, используем его как есть
            if employee['photo_url'].startswith('/static/'):
                employee['photo_url'] = employee['photo_url']
            else:
                # Иначе формируем полный путь
                employee['photo_url'] = f"/static/uploads/employee_photos/{employee['photo_url']}"
        else:
            # Если фото нет, устанавливаем дефолтное
            employee['photo_url'] = "/static/img/default-avatar.svg"
        
        # Преобразуем статус для отображения
        if employee.get('status'):
            status_display_mapping = {
                'online': 'Онлайн',
                'offline': 'Офлайн',
                'active': 'Активен',
                'blocked': 'Заблокирован',
                'fired': 'Уволен'
            }
            employee['status_display'] = status_display_mapping.get(employee['status'], employee['status'])
        else:
            employee['status_display'] = 'Уволен'
            
        logger.info(f"Данные уволенного сотрудника с ID={employee_id} успешно получены")
        return jsonify({'success': True, 'employee': employee})
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных уволенного сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении данных: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/dashboard_data', methods=['GET'])
@admin_routes_bp.route('/admin/api/dashboard_data', methods=['GET'])
@login_required
def dashboard_data_api():
    """Возвращает данные для дашборда персонала в зависимости от выбранного периода (week, month, year)"""
    logger.debug("Начало выполнения функции dashboard_data_api")
    if current_user.role not in ['admin', 'leader']:
        return jsonify({'success': False, 'message': 'Недостаточно прав'}), 403

    try:
        period = request.args.get('period', 'week')
        # Определяем количество дней для периода
        days_map = {
            'week': 7,
            'month': 30,
            'year': 365
        }
        days = days_map.get(period, 30)

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Динамика численности персонала (наймы за период)
        cursor.execute(
            """
            SELECT DATE(hire_date) as date, COUNT(*) as count
            FROM User
            WHERE hire_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
              AND fire_date IS NULL
            GROUP BY DATE(hire_date)
            ORDER BY date
            """,
            (days,)
        )
        staff_dynamics = cursor.fetchall()
        dates = []
        staff_counts = []
        for item in staff_dynamics:
            if item['date']:
                dates.append(item['date'].strftime('%d.%m'))
                staff_counts.append(item['count'])

        # Распределение по отделам (активные сотрудники)
        cursor.execute(
            """
            SELECT d.name, COUNT(u.id) as count
            FROM Department d
            LEFT JOIN User u ON d.id = u.department_id AND u.fire_date IS NULL
            GROUP BY d.id, d.name
            ORDER BY count DESC
            """
        )
        department_distribution = cursor.fetchall()
        department_names = [d['name'] for d in department_distribution]
        department_counts = [d['count'] for d in department_distribution]

        return jsonify({
            'success': True,
            'dates': dates,
            'staff_counts': staff_counts,
            'department_names': department_names,
            'department_counts': department_counts
        })

    except Exception as e:
        logger.error(f"Ошибка в dashboard_data_api: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()