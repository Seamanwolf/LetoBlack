from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import current_user
from app.utils import create_db_connection, login_required
import logging
from datetime import datetime
from app.routes.admin import admin_routes_bp
from app.routes.auth import auth_bp, redirect_based_on_role
import hashlib
import os
from werkzeug.utils import secure_filename
import time
import re
from app.models.corp_number import CorpNumber

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

@admin_routes_bp.route('/personnel')
@login_required
def personnel():
    logger.debug("Начало выполнения функции personnel")
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        flash('У вас нет доступа к этой странице', 'error')
        return redirect_based_on_role(current_user)
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем статистику (исключая суперадмина с ID=1)
        cursor.execute('''
            SELECT 
                COUNT(*) as total_employees,
                SUM(CASE WHEN fire_date IS NULL THEN 1 ELSE 0 END) as active_employees,
                SUM(CASE WHEN fire_date IS NOT NULL THEN 1 ELSE 0 END) as fired_employees
            FROM User
            WHERE id != 1
        ''')
        stats = cursor.fetchone()
        
        # Получаем список отделов из таблицы Department
        cursor.execute('SELECT id, name FROM Department ORDER BY display_order ASC, name ASC')
        departments = cursor.fetchall()
        
        # Получаем сотрудников по отделам
        employees_by_department = {}
        for department in departments:
            cursor.execute('''
                SELECT 
                    u.id,
                    u.full_name,
                    u.position,
                    u.Phone as personal_number,
                    u.corp_phone as corporate_number,
                    u.role,
                    u.status,
                    u.fire_date,
                    u.corporate_email
                FROM User u
                WHERE u.department_id = %s AND u.fire_date IS NULL AND u.id != 1
                ORDER BY 
                    CASE 
                        WHEN u.role = 'manager' THEN 1
                        WHEN u.role = 'deputy' THEN 2
                        ELSE 3
                    END,
                    u.full_name
            ''', (department['id'],))
            employees = cursor.fetchall()
            
            # Выводим диагностическую информацию
            logger.debug(f"Запрос для отдела {department['name']} (ID: {department['id']}) вернул {len(employees)} сотрудников")
            
            if employees:
                employees_by_department[department['name']] = employees
        
        # Проверяем, есть ли сотрудники для всех отделов
        if not employees_by_department:
            # Если ни одного сотрудника не найдено, попробуем выполнить альтернативный запрос
            cursor.execute('''
                SELECT 
                    u.id,
                    u.full_name,
                    u.position,
                    u.Phone as personal_number,
                    u.corp_phone as corporate_number,
                    u.role,
                    u.status,
                    u.fire_date,
                    u.corporate_email,
                    d.name as department_name
                FROM User u
                JOIN Department d ON u.department_id = d.id
                WHERE u.fire_date IS NULL AND u.id != 1
                ORDER BY d.display_order ASC, d.name ASC, u.full_name
            ''')
            all_employees = cursor.fetchall()
            
            logger.debug(f"Альтернативный запрос вернул {len(all_employees)} сотрудников")
            
            # Группировка по отделам
            for employee in all_employees:
                dept_name = employee['department_name']
                if dept_name not in employees_by_department:
                    employees_by_department[dept_name] = []
                employees_by_department[dept_name].append(employee)
        
        return render_template('admin/personnel.html',
                             total_employees=stats['total_employees'],
                             active_employees=stats['active_employees'],
                             fired_employees=stats['fired_employees'],
                             avg_score=0,  # Временно установим 0, так как колонки score нет
                             departments=departments,
                             now=datetime.now(),
                             employees_by_department=employees_by_department)
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы персонала: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return redirect_based_on_role(current_user)
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_employee', methods=['GET'])
@login_required
def get_employee_api():
    """Получение данных сотрудника по ID"""
    logger.debug("Начало выполнения функции get_employee_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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
        
        # Получаем данные сотрудника с учетом новой структуры телефонов
        query = """
            SELECT 
                u.id, u.full_name, u.login, u.Phone as personal_number,
                u.department_id, u.role, u.hire_date, u.fire_date,
                u.fired, u.personal_email, u.pc_login, u.pc_password,
                u.birth_date, u.position, u.office, u.corporate_email,
                u.corp_phone as corporate_number,
                u.documents, u.rr, u.site, u.crm_id,
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
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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

@admin_routes_bp.route('/api/fire_employee', methods=['POST'])
@login_required
def fire_employee_api():
    """Увольнение сотрудника через API"""
    logger.debug("Начало выполнения функции fire_employee_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.json
        if not data:
            logger.warning("Данные не получены в запросе")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
        employee_id = data.get('id')
        fire_date = data.get('fire_date')
        
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400
            
        if not fire_date:
            logger.warning("Дата увольнения не указана в запросе")
            return jsonify({'success': False, 'message': 'Дата увольнения не указана'}), 400
            
        # Защита от увольнения суперадмина
        if int(employee_id) == 1:
            logger.warning(f"Попытка увольнения суперадмина (ID=1) пользователем {current_user.login}")
            return jsonify({'success': False, 'message': 'Невозможно уволить суперадмина из системы'}), 403
        
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
                fired = 1
            WHERE id = %s
        """, (fire_date, employee_id))
        
        # Обновляем статус в UserActivity
        cursor.execute("""
            UPDATE UserActivity 
            SET status = 'offline'
            WHERE user_id = %s
        """, (employee_id,))
        
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
        
        # Получаем список отделов из таблицы Department
        cursor.execute('SELECT id, name FROM Department ORDER BY name')
        departments = cursor.fetchall()
        
        # Получаем список уволенных сотрудников
        cursor.execute("""
            SELECT u.*, d.name as department_name, 
                   DATEDIFF(u.fire_date, u.hire_date) as days_worked
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            WHERE u.status = 'fired' OR u.fire_date IS NOT NULL
            ORDER BY u.fire_date DESC
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

@admin_routes_bp.route('/admin/rehire_employee', methods=['POST'])
@login_required
def rehire_employee():
    """Восстановление уволенного сотрудника"""
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
        cursor.execute("SELECT id, full_name, status FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            return jsonify({'success': False, 'message': 'Сотрудник не найден'})
        
        # Обновляем запись сотрудника
        cursor.execute("""
            UPDATE User 
            SET status = 'offline', 
                fire_date = NULL 
            WHERE id = %s
        """, (employee_id,))
        
        connection.commit()
        
        return jsonify({
            'success': True, 
            'message': f"Сотрудник успешно восстановлен"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при восстановлении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при восстановлении сотрудника: {str(e)}'})
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@admin_routes_bp.route('/api/update_department_order', methods=['POST'])
@admin_routes_bp.route('/admin/api/update_department_order', methods=['POST'])
@login_required
def update_department_order_api():
    """Обновление порядка отделов через API"""
    logger.debug("Начало выполнения функции update_department_order_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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
        
        # Проверяем, установлен ли порядоковый номер
        current_order = department.get('display_order')
        if current_order is None:
            # Если порядок не установлен, назначаем максимальное значение + 1
            cursor.execute("SELECT MAX(display_order) as max_order FROM Department")
            max_order = cursor.fetchone().get('max_order') or 0
            current_order = max_order + 1
            cursor.execute("UPDATE Department SET display_order = %s WHERE id = %s", 
                         (current_order, department_id))
            conn.commit()
        
        if direction == 'up':
            # Найти отдел с меньшим порядком
            cursor.execute("""
                SELECT id, name, display_order FROM Department 
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
                conn.commit()
                logger.info(f"Отдел {department['name']} (ID={department_id}) перемещен вверх")
                
        elif direction == 'down':
            # Найти отдел с большим порядком
            cursor.execute("""
                SELECT id, name, display_order FROM Department 
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
                logger.info(f"Отдел {department['name']} (ID={department_id}) перемещен вниз")
        
        return jsonify({
            'success': True, 
            'message': f"Порядок отделов успешно обновлен"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении порядка отделов: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении порядка отделов: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/api/add_employee', methods=['POST'])
@login_required
def add_employee_api():
    """Добавление нового сотрудника через API"""
    logger.debug("Начало выполнения функции add_employee_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        data = request.get_json()
        full_name = data.get('full_name')
        department_id = data.get('department_id')
        position = data.get('position')
        role = data.get('role')
        login = data.get('login')
        password = data.get('password')
        corporate_email = data.get('corporate_email')
        
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
        
        Phone = data.get('Phone', '')
        hire_date = data.get('hire_date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT id FROM User WHERE login = %s", (login,))
        if cursor.fetchone():
            logger.warning(f"Пользователь с логином {login} уже существует")
            return jsonify({
                'success': False, 
                'message': f'Пользователь с логином {login} уже существует'
            }), 400
        
        cursor.execute("SELECT id FROM User WHERE corporate_email = %s", (corporate_email,))
        if cursor.fetchone():
            logger.warning(f"Пользователь с почтой {corporate_email} уже существует")
            return jsonify({
                'success': False, 
                'message': f'Пользователь с почтой {corporate_email} уже существует'
            }), 400
        
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        
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
        
        # Защита от удаления суперадмина
        if int(employee_id) == 1:
            logger.warning(f"Попытка удаления суперадмина (ID=1) пользователем {current_user.login}")
            return jsonify({'success': False, 'message': 'Невозможно удалить суперадмина из системы'})
        
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
        
        logger.info(f"Сотрудник с ID={employee_id} успешно удален")
        return jsonify({
            'success': True, 
            'message': 'Сотрудник успешно удален'
        })
    
    except Exception as e:
        logger.error(f"Ошибка при удалении сотрудника: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при удалении сотрудника: {str(e)}'})
    
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
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})

    try:
        # Проверяем наличие данных формы
        if not request.form and not request.files:
            logger.warning("Данные не получены в запросе (ни form, ни files)")
            return jsonify({'success': False, 'message': 'Данные не получены'}), 400
            
        # Получаем данные из формы
        employee_id = request.form.get('id')
        if not employee_id:
            logger.warning("ID сотрудника не указан в запросе")
            return jsonify({'success': False, 'message': 'ID сотрудника не указан'}), 400

        # Логируем все полученные данные формы
        logger.debug("=== Полученные данные формы ===")
        logger.debug(f"Все поля формы: {dict(request.form)}")
        logger.debug(f"Все файлы: {dict(request.files)}")
        logger.debug("=== Конец данных формы ===")

        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Получаем текущие данные сотрудника
        cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404

        # Проверяем, нужно ли удалить фото
        if request.form.get('delete_photo') == '1':
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
            'full_name', 'department_id', 'position', 'role', 
            'Phone', 'corporate_email', 'personal_email', 'pc_login', 'pc_password',
            'crm_id', 'hire_date', 'birth_date', 'notes',
            'documents', 'rr', 'site'
        ]

        # Обработка чекбоксов
        boolean_fields = ['documents', 'rr', 'site']
        logger.debug("=== Обработка чекбоксов ===")
        for field in boolean_fields:
            if field in request.form:
                value = 1 if request.form.get(field) == 'on' else 0
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
                
            if field in request.form and field not in ['hire_date', 'birth_date']:
                value = request.form.get(field)
                if value is not None:
                    update_data[field] = value
                    logger.debug(f"Текстовое поле {field}: {value}")

        # Обработка дат
        for date_field in ['hire_date', 'birth_date']:
            if date_field in request.form and request.form.get(date_field):
                try:
                    date_value = datetime.strptime(request.form.get(date_field), '%Y-%m-%d').date()
                    update_data[date_field] = date_value
                except ValueError:
                    logger.warning(f"Неверный формат даты для поля {date_field}: {request.form.get(date_field)}")

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
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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
                END as field_name,
                CASE 
                    WHEN uh.changed_field = 'department_id' THEN 
                        (SELECT name FROM Department WHERE id = uh.old_value)
                    ELSE uh.old_value
                END as old_value,
                CASE 
                    WHEN uh.changed_field = 'department_id' THEN 
                        (SELECT name FROM Department WHERE id = uh.new_value)
                    ELSE uh.new_value
                END as new_value
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

@admin_routes_bp.route('/admin/api/update_department_positions', methods=['POST'])
@admin_routes_bp.route('/api/update_department_positions', methods=['POST'])
@login_required
def update_department_positions_api():
    """Обновление порядка отделов через API с помощью drag-and-drop"""
    logger.debug("Начало выполнения функции update_department_positions_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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
        
        if not dragged_id or not target_id or not position:
            logger.warning("Не указаны ID отделов или позиция")
            return jsonify({'success': False, 'message': 'Не указаны ID отделов или позиция'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существование отделов
        cursor.execute("SELECT id, name, display_order FROM Department WHERE id IN (%s, %s)", 
                     (dragged_id, target_id))
        departments = cursor.fetchall()
        
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
        logger.error(f"Ошибка при обновлении порядка отделов: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении порядка отделов: {str(e)}'}), 500
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
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        flash('У вас нет доступа к этой странице', 'error')
        return redirect_based_on_role(current_user)
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем номера из таблицы corp_numbers
        query = """
            SELECT id, phone_number, department, assigned_to, prohibit_issuance,
                   whatsapp, telegram, blocked
            FROM corp_numbers
            ORDER BY department, phone_number
        """
        cursor.execute(query)
        numbers = cursor.fetchall()
        
        # Получаем список отделов
        cursor.execute('SELECT id, name FROM Department ORDER BY display_order ASC, name ASC')
        departments = cursor.fetchall()
        
        # Получаем список отделов из corp_numbers для унификации
        cursor.execute("""
            SELECT DISTINCT department FROM corp_numbers 
            WHERE department IS NOT NULL AND department != ''
            ORDER BY department
        """)
        departments_from_phones = cursor.fetchall()
        
        # Объединяем отделы из разных источников
        all_departments = []
        for dept in departments:
            all_departments.append(dept['name'])
        
        for dept in departments_from_phones:
            if dept['department'] and dept['department'] not in all_departments:
                all_departments.append(dept['department'])
        
        sorted_departments = sorted(all_departments)
        
        # Подсчет статистики по номерам
        total_numbers = len(numbers)
        assigned_numbers = sum(1 for n in numbers if n.get('assigned_to'))
        free_numbers = total_numbers - assigned_numbers
        prohibited_numbers = sum(1 for n in numbers if n.get('prohibit_issuance'))
        
        return render_template('admin/phone_numbers.html',
                               numbers=numbers,
                               sorted_departments=sorted_departments,
                               total_numbers=total_numbers,
                               assigned_numbers=assigned_numbers,
                               free_numbers=free_numbers,
                               prohibited_numbers=prohibited_numbers)
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы корпоративных номеров: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return redirect_based_on_role(current_user)
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/add_number', methods=['POST'])
@login_required
def add_number_api():
    """Добавление нового номера"""
    logger.debug("Начало выполнения функции add_number_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    phone_number = data.get('phone_number', '').strip()
    department = data.get('department')
    whatsapp = data.get('whatsapp', 0)
    telegram = data.get('telegram', 0)
    blocked = data.get('blocked', 0)
    additional_numbers = data.get('additional_numbers', [])
    
    if not phone_number or not department:
        return jsonify({'success': False, 'message': 'Необходимо указать номер телефона и отдел'}), 400
    
    # Удаляем префикс +7, если он присутствует
    cleaned_number = phone_number
    if phone_number.startswith('+7'):
        cleaned_number = phone_number[2:]
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, есть ли уже такой номер в базе (проверяем по очищенному номеру)
        cursor.execute("SELECT * FROM corp_numbers WHERE phone_number = %s", (cleaned_number,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Номер уже существует в базе'}), 400
        
        # Добавляем основной номер (сохраняем без префикса +7)
        cursor.execute("""
            INSERT INTO corp_numbers 
            (phone_number, department, whatsapp, telegram, blocked) 
            VALUES (%s, %s, %s, %s, %s)
        """, (cleaned_number, department, whatsapp, telegram, blocked))
        
        # Получаем ID нового номера
        new_number_id = cursor.lastrowid
        
        # Добавляем дополнительные номера, если есть
        for additional_number in additional_numbers:
            if additional_number.strip():  # Проверяем, что номер не пустой
                # Удаляем префикс +7, если он присутствует
                add_number = additional_number.strip()
                if add_number.startswith('+7'):
                    add_number = add_number[2:]
                
                cursor.execute("""
                    INSERT INTO additional_phone_numbers 
                    (corp_number_id, phone_number) 
                    VALUES (%s, %s)
                """, (new_number_id, add_number))
        
        conn.commit()
        
        # Логируем добавление номера
        try:
            log_message = f"Номер добавлен в отдел {department}."
            
            # Добавляем информацию о статусах
            if whatsapp:
                log_message += " WhatsApp: Да."
            if telegram:
                log_message += " Telegram: Да."
            if blocked:
                log_message += " Блокировка: Да."
            
            # Добавляем информацию о дополнительных номерах
            if additional_numbers:
                log_message += f" Дополнительные номера: {', '.join(additional_numbers)}."
            
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, new_number, note)
                VALUES (%s, %s, %s)
            """, (current_user.id, cleaned_number, log_message))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        return jsonify({'success': True, 'message': 'Номер успешно добавлен', 'number_id': new_number_id})
    except Exception as e:
        logger.error(f"Ошибка при добавлении номера: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при добавлении номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/update_number', methods=['POST'])
@login_required
def update_number_api():
    """Обновление номера"""
    logger.debug("Начало выполнения функции update_number_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    number_id = data.get('number_id')
    phone_number = data.get('phone_number', '').strip()
    whatsapp = data.get('whatsapp')
    telegram = data.get('telegram')
    blocked = data.get('blocked')
    prohibit_issuance = data.get('prohibit_issuance')
    new_additional_numbers = data.get('new_additional_numbers', [])
    
    if not number_id or not phone_number:
        return jsonify({'success': False, 'message': 'Необходимо указать ID номера и номер телефона'}), 400
    
    # Удаляем префикс +7, если он присутствует
    cleaned_number = phone_number
    if phone_number.startswith('+7'):
        cleaned_number = phone_number[2:]
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем текущие данные для логирования
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        old_data = cursor.fetchone()
        if not old_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Проверяем, не пытаемся ли мы изменить номер на уже существующий
        if cleaned_number != old_data['phone_number']:
            cursor.execute("SELECT * FROM corp_numbers WHERE phone_number = %s AND id != %s", (cleaned_number, number_id))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'Номер уже существует в базе'}), 400
        
        # Обновляем данные
        cursor.execute("""
            UPDATE corp_numbers 
            SET phone_number = %s, 
                whatsapp = %s, 
                telegram = %s, 
                blocked = %s, 
                prohibit_issuance = %s 
            WHERE id = %s
        """, (cleaned_number, whatsapp, telegram, blocked, prohibit_issuance, number_id))
        
        # Добавляем новые дополнительные номера
        if new_additional_numbers:
            for additional_number in new_additional_numbers:
                if additional_number.strip():  # Проверяем, что номер не пустой
                    # Удаляем префикс +7, если он присутствует
                    add_number = additional_number.strip()
                    if add_number.startswith('+7'):
                        add_number = add_number[2:]
                    
                    cursor.execute("""
                        INSERT INTO additional_phone_numbers 
                        (corp_number_id, phone_number) 
                        VALUES (%s, %s)
                    """, (number_id, add_number))
        
        conn.commit()
        
        # Логируем изменение номера
        try:
            log_message = f"Номер изменен с {old_data['phone_number']} на {cleaned_number}."
            
            # Добавляем информацию об изменении статусов
            if old_data['whatsapp'] != whatsapp:
                log_message += f" WhatsApp: {'Да' if whatsapp else 'Нет'}."
            if old_data['telegram'] != telegram:
                log_message += f" Telegram: {'Да' if telegram else 'Нет'}."
            if old_data['blocked'] != blocked:
                log_message += f" Блокировка: {'Да' if blocked else 'Нет'}."
            if old_data['prohibit_issuance'] != prohibit_issuance:
                log_message += f" Запрет выдачи: {'Да' if prohibit_issuance else 'Нет'}."
            
            # Добавляем информацию о новых дополнительных номерах
            if new_additional_numbers:
                log_message += f" Добавлены дополнительные номера: {', '.join(new_additional_numbers)}."
            
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, new_number)
                VALUES (%s, %s, %s)
            """, (
                current_user.id,
                old_data['phone_number'],
                cleaned_number
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        return jsonify({'success': True, 'message': 'Номер успешно обновлен'})
    except Exception as e:
        logger.error(f"Ошибка при обновлении номера: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/update_prohibit', methods=['POST'])
@login_required
def update_prohibit():
    """Обновление статуса запрета выдачи номера"""
    logger.debug("Начало выполнения функции update_prohibit")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    number_id = data.get('number_id')
    prohibit_issuance = data.get('prohibit_issuance')
    
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем текущие данные для логирования
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Обновляем статус запрета
        cursor.execute("UPDATE corp_numbers SET prohibit_issuance = %s WHERE id = %s",
                       (prohibit_issuance, number_id))
        conn.commit()
        
        # Логируем изменение
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
            
        return jsonify({'success': True, 'message': 'Статус запрета выдачи обновлен'})
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса запрета выдачи: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении статуса: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/delete_number', methods=['POST'])
@login_required
def delete_number_api():
    """Удаление номера"""
    logger.debug("Начало выполнения функции delete_number_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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
@admin_routes_bp.route('/move_number', methods=['POST'])  # Альтернативный маршрут
@login_required
def move_number_api():
    """Перемещение номера между отделами"""
    logger.setLevel(logging.DEBUG)  # Устанавливаем максимальный уровень логирования
    logger.debug("============ НАЧАЛО ВЫПОЛНЕНИЯ ФУНКЦИИ move_number_api ============")
    logger.debug(f"URL запроса: {request.path}")
    logger.debug(f"METHOD: {request.method}")
    logger.debug(f"Content-Type: {request.headers.get('Content-Type', 'не указан')}")
    logger.debug(f"Размер данных запроса: {request.content_length} байт")
    
    # Логируем тело запроса
    try:
        request_json = request.get_json()
        logger.debug(f"Тело запроса (JSON): {request_json}")
    except Exception as e:
        logger.error(f"Ошибка при чтении JSON: {e}")
        request_json = None
        
    # Также пробуем получить данные из формы
    form_data = request.form.to_dict() if request.form else {}
    if form_data:
        logger.debug(f"Данные формы: {form_data}")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    # Получаем данные из запроса
    data = request.get_json() or form_data
    if not data:
        logger.error("Данные не получены: ни JSON, ни form-data")
        return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
    number_id = data.get('number_id')
    new_department = data.get('new_department')
    is_free_numbers = data.get('is_free_numbers', False)
    
    logger.debug(f"Параметры запроса: number_id={number_id}, new_department={new_department}, is_free_numbers={is_free_numbers}")
    
    if not number_id or not new_department:
        logger.error("Не указан ID номера или новый отдел")
        return jsonify({'success': False, 'message': 'Необходимо указать ID номера и новый отдел'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем текущие данные для логирования
        logger.debug(f"Выполняем запрос SELECT для номера с ID={number_id}")
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        
        if not number_data:
            logger.error(f"Номер с ID={number_id} не найден в базе данных")
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        old_department = number_data.get('department')
        logger.debug(f"Текущие данные номера: {number_data}")
        logger.debug(f"Текущий отдел: {old_department}")
        
        # Проверяем специальное значение "свободные"
        if new_department == 'свободные' or is_free_numbers:
            logger.debug(f"Перемещение номера {number_id} в свободные номера (установка department=NULL)")
            query = "UPDATE corp_numbers SET department = NULL WHERE id = %s"
            logger.debug(f"SQL запрос: {query} с параметром: {number_id}")
            cursor.execute(query, (number_id,))
            note = "Номер перемещен в список свободных номеров"
        else:
            # Стандартное перемещение между отделами
            logger.debug(f"Стандартное перемещение номера {number_id} в отдел {new_department}")
            query = "UPDATE corp_numbers SET department = %s WHERE id = %s"
            logger.debug(f"SQL запрос: {query} с параметрами: {new_department}, {number_id}")
            cursor.execute(query, (new_department, number_id))
            note = f"Номер перемещен в отдел {new_department}"
        
        # Проверяем, сколько строк было изменено
        affected_rows = cursor.rowcount
        logger.debug(f"Количество измененных строк: {affected_rows}")
        
        conn.commit()
        logger.debug("Изменения успешно сохранены в БД (commit)")
        
        # Проверка, что изменения сохранились
        logger.debug(f"Проверяем, что изменения сохранились в БД для номера с ID={number_id}")
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        updated_data = cursor.fetchone()
        logger.debug(f"Обновленные данные номера: {updated_data}")
        
        # Логируем перемещение
        try:
            log_message = number_data['phone_number']
            if new_department == 'свободные' or is_free_numbers:
                log_message += " -> Свободные номера"
            else:
                log_message += f" -> {new_department}"
                
            logger.debug(f"Добавляем запись в историю: {log_message}")
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, new_number, note)
                VALUES (%s, %s, %s, %s)
            """, (
                current_user.id,
                number_data['phone_number'],
                log_message,
                f"Перемещение из {old_department or 'Свободные номера'} в {new_department if new_department != 'свободные' else 'Свободные номера'}"
            ))
            conn.commit()
            logger.debug("Запись в историю добавлена успешно")
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        logger.debug(f"Функция move_number_api завершена успешно с сообщением: {note}")
        logger.debug("============ КОНЕЦ ВЫПОЛНЕНИЯ ФУНКЦИИ move_number_api ============")
        return jsonify({'success': True, 'message': note})
    except Exception as e:
        logger.error(f"ОШИБКА при перемещении номера: {str(e)}")
        logger.exception("Полная трассировка ошибки:")
        return jsonify({'success': False, 'message': f'Ошибка при перемещении номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()
            logger.debug("Соединение с БД закрыто")

@admin_routes_bp.route('/api/assign_number', methods=['POST'])
@admin_routes_bp.route('/assign_number', methods=['POST'])  # Альтернативный маршрут
@login_required
def assign_number_api():
    """Назначение номера сотруднику"""
    logger.debug("Начало выполнения функции assign_number_api")
    logger.debug(f"URL запроса: {request.path}")
    logger.debug(f"Тело запроса: {request.get_json()}")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Данные не получены'}), 400
        
    number_id = data.get('number_id')
    employee_id = data.get('employee_id')
    
    logger.debug(f"Параметры запроса: number_id={number_id}, employee_id={employee_id}")
    
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем данные номера
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        logger.debug(f"Данные номера: {number_data}")
        
        # Получаем статус Telegram для использования в логировании
        telegram_status = number_data.get('telegram', 0)
        
        if employee_id:
            # Получаем данные сотрудника
            cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
            employee = cursor.fetchone()
            if not employee:
                return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
            
            logger.debug(f"Данные сотрудника: {employee}")
            
            # Назначаем номер сотруднику
            cursor.execute("UPDATE corp_numbers SET assigned_to = %s WHERE id = %s",
                          (employee['full_name'], number_id))
            
            # Также обновляем поле corp_phone в таблице User
            cursor.execute("UPDATE User SET corp_phone = %s WHERE id = %s",
                          (number_data['phone_number'], employee_id))
            
            note = f"Номер назначен сотруднику {employee['full_name']}"
        else:
            # Освобождаем номер
            cursor.execute("UPDATE corp_numbers SET assigned_to = NULL WHERE id = %s", (number_id,))
            
            # Если номер был закреплен за сотрудником, находим его и снимаем привязку
            if number_data['assigned_to']:
                cursor.execute("UPDATE User SET corp_phone = NULL WHERE full_name = %s", 
                             (number_data['assigned_to'],))
            
            note = "Номер освобожден"
        
        conn.commit()
        
        # Проверяем, что изменения сохранились
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        updated_number = cursor.fetchone()
        logger.debug(f"Обновленные данные номера: {updated_number}")
        
        # Логируем назначение
        try:
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, new_number)
                VALUES (%s, %s, %s)
            """, (
                current_user.id,
                number_data['phone_number'],
                number_data['phone_number'] + " - Telegram: " + ('Да' if telegram_status else 'Нет')
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        return jsonify({'success': True, 'message': note})
    except Exception as e:
        logger.error(f"Ошибка при назначении номера: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при назначении номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_employees_for_number', methods=['GET'])
@login_required
def get_employees_for_number():
    """Получение списка сотрудников для назначения номера"""
    logger.debug("Начало выполнения функции get_employees_for_number")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем список активных сотрудников
        cursor.execute("""
            SELECT id, full_name, department,
                  CONCAT(full_name, ' (', department, ')') AS display_name
            FROM User
            WHERE is_active = 1 AND fired = 0
            ORDER BY full_name
        """)
        employees = cursor.fetchall()
        
        return jsonify({'success': True, 'employees': employees})
    except Exception as e:
        logger.error(f"Ошибка при получении списка сотрудников: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении списка сотрудников: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/add_department', methods=['POST'])
@login_required
def add_department_api():
    """Добавление нового отдела"""
    logger.debug("Начало выполнения функции add_department_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    department_name = data.get('department_name')
    
    if not department_name:
        return jsonify({'success': False, 'message': 'Необходимо указать название отдела'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, существует ли уже такой отдел
        cursor.execute("SELECT * FROM Department WHERE name = %s", (department_name,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'Отдел с таким названием уже существует'}), 400
        
        # Определяем следующий порядковый номер для нового отдела
        cursor.execute("SELECT MAX(display_order) as max_order FROM Department")
        result = cursor.fetchone()
        next_order = 1
        if result and result['max_order'] is not None:
            next_order = result['max_order'] + 1
        
        # Добавляем новый отдел
        cursor.execute("INSERT INTO Department (name, display_order) VALUES (%s, %s)", 
                       (department_name, next_order))
        conn.commit()
        
        # Получаем ID нового отдела
        cursor.execute("SELECT LAST_INSERT_ID() as id")
        new_id = cursor.fetchone()['id']
        
        return jsonify({
            'success': True, 
            'message': f'Отдел {department_name} успешно добавлен',
            'department_id': new_id,
            'department_name': department_name
        })
    except Exception as e:
        logger.error(f"Ошибка при добавлении отдела: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при добавлении отдела: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close() 

@admin_routes_bp.route('/api/update_whatsapp', methods=['POST'])
@login_required
def update_whatsapp():
    """Обновление статуса WhatsApp для номера"""
    logger.debug("Начало выполнения функции update_whatsapp")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    number_id = data.get('number_id')
    whatsapp = data.get('whatsapp')
    
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем текущие данные для логирования
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Обновляем статус WhatsApp
        cursor.execute("UPDATE corp_numbers SET whatsapp = %s WHERE id = %s",
                       (whatsapp, number_id))
        conn.commit()
        
        # Логируем изменение
        try:
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, note)
                VALUES (%s, %s, %s)
            """, (
                current_user.id,
                number_data['phone_number'],
                f"Изменен статус WhatsApp: {'Да' if whatsapp else 'Нет'}"
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        return jsonify({'success': True, 'message': 'Статус WhatsApp обновлен'})
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса WhatsApp: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении статуса: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/update_telegram', methods=['POST'])
@login_required
def update_telegram():
    """Обновление статуса Telegram для номера"""
    logger.debug("Начало выполнения функции update_telegram")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    number_id = data.get('number_id')
    telegram = data.get('telegram')
    
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем текущие данные для логирования
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Обновляем статус Telegram
        cursor.execute("UPDATE corp_numbers SET telegram = %s WHERE id = %s",
                       (telegram, number_id))
        conn.commit()
        
        # Логируем изменение
        try:
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, note)
                VALUES (%s, %s, %s)
            """, (
                current_user.id,
                number_data['phone_number'],
                f"Изменен статус Telegram: {'Да' if telegram else 'Нет'}"
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        return jsonify({'success': True, 'message': 'Статус Telegram обновлен'})
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса Telegram: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении статуса: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/update_blocked', methods=['POST'])
@login_required
def update_blocked():
    """Обновление статуса блокировки для номера"""
    logger.debug("Начало выполнения функции update_blocked")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.get_json()
    number_id = data.get('number_id')
    blocked = data.get('blocked')
    
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем текущие данные для логирования
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Обновляем статус блокировки
        cursor.execute("UPDATE corp_numbers SET blocked = %s WHERE id = %s",
                       (blocked, number_id))
        conn.commit()
        
        # Логируем изменение
        try:
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, new_number)
                VALUES (%s, %s, %s)
            """, (
                current_user.id,
                number_data['phone_number'],
                number_data['phone_number'] + " - Блокировка: " + ('Да' if blocked else 'Нет')
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        return jsonify({'success': True, 'message': 'Статус блокировки обновлен'})
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса блокировки: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении статуса: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_free_numbers', methods=['GET'])
@admin_routes_bp.route('/get_free_numbers', methods=['GET'])  # Альтернативный маршрут
@login_required
def get_free_numbers():
    """Получение списка свободных номеров"""
    logger.debug("Начало выполнения функции get_free_numbers")
    logger.debug(f"URL запроса: {request.path}")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем список действительно свободных номеров (без отдела)
        cursor.execute("""
            SELECT id, phone_number, department, whatsapp, telegram, blocked, prohibit_issuance
            FROM corp_numbers
            WHERE department IS NULL OR department = ''
            ORDER BY phone_number
        """)
        truly_free_numbers = cursor.fetchall()
        
        # Получаем список номеров, не закрепленных за сотрудниками, но с отделами
        cursor.execute("""
            SELECT id, phone_number, department, whatsapp, telegram, blocked, prohibit_issuance
            FROM corp_numbers
            WHERE (assigned_to IS NULL OR assigned_to = '') 
            AND department IS NOT NULL AND department != ''
            ORDER BY department, phone_number
        """)
        department_free_numbers = cursor.fetchall()
        
        # Объединяем результаты, помечая действительно свободные номера
        numbers = truly_free_numbers + department_free_numbers
        
        # Добавляем пометку "Свободный номер" для тех, которые не имеют отдела
        for number in truly_free_numbers:
            number['is_truly_free'] = True
            number['department'] = 'Свободные номера'
            
        return jsonify({
            'success': True, 
            'numbers': numbers,
            'truly_free_count': len(truly_free_numbers),
            'department_free_count': len(department_free_numbers)
        })
    except Exception as e:
        logger.error(f"Ошибка при получении списка свободных номеров: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении списка номеров: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_free_numbers_by_department', methods=['GET'])
@login_required
def get_free_numbers_by_department():
    """Получение списка свободных номеров по ID отдела"""
    logger.debug("Начало выполнения функции get_free_numbers_by_department")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    department_id = request.args.get('department_id')
    if not department_id:
        return jsonify({'success': False, 'message': 'Не указан ID отдела'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем название отдела по ID
        cursor.execute("SELECT name FROM Department WHERE id = %s", (department_id,))
        department = cursor.fetchone()
        
        if not department:
            return jsonify({'success': False, 'message': 'Отдел не найден'}), 404
        
        department_name = department['name']
        
        # Получаем список свободных номеров для указанного отдела
        cursor.execute("""
            SELECT id, phone_number, department, whatsapp, telegram, blocked, prohibit_issuance
            FROM corp_numbers
            WHERE (assigned_to IS NULL OR assigned_to = '') 
            AND department = %s
            AND (prohibit_issuance IS NULL OR prohibit_issuance = 0) 
            ORDER BY phone_number
        """, (department_name,))
        
        numbers = cursor.fetchall()
        
        # Также получаем все неназначенные номера (если в отделе нет свободных)
        if not numbers:
            cursor.execute("""
                SELECT id, phone_number, department, whatsapp, telegram, blocked, prohibit_issuance
                FROM corp_numbers
                WHERE (assigned_to IS NULL OR assigned_to = '') 
                AND (prohibit_issuance IS NULL OR prohibit_issuance = 0)
                ORDER BY phone_number
            """)
            all_free_numbers = cursor.fetchall()
            
            return jsonify({
                'success': True, 
                'numbers': numbers,
                'all_free_numbers': all_free_numbers,
                'department_name': department_name
            })
        
        return jsonify({
            'success': True, 
            'numbers': numbers,
            'department_name': department_name
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка свободных номеров по отделу: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении списка номеров: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_additional_numbers', methods=['GET'])
@login_required
def get_additional_numbers():
    """Получение списка дополнительных номеров для основного номера"""
    logger.debug("Начало выполнения функции get_additional_numbers")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    number_id = request.args.get('number_id')
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID основного номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существование основного номера
        cursor.execute("SELECT * FROM corp_numbers WHERE id = %s", (number_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Основной номер не найден'}), 404
        
        # Получаем дополнительные номера
        cursor.execute("""
            SELECT id, phone_number, created_at 
            FROM additional_phone_numbers 
            WHERE corp_number_id = %s 
            ORDER BY created_at
        """, (number_id,))
        additional_numbers = cursor.fetchall()
        
        return jsonify({'success': True, 'additional_numbers': additional_numbers})
    except Exception as e:
        logger.error(f"Ошибка при получении дополнительных номеров: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении дополнительных номеров: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/delete_additional_number', methods=['POST'])
@login_required
def delete_additional_number():
    """Удаление дополнительного номера"""
    logger.debug("Начало выполнения функции delete_additional_number")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    data = request.json
    additional_number_id = data.get('additional_number_id')
    
    if not additional_number_id:
        return jsonify({'success': False, 'message': 'Не указан ID дополнительного номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем данные номера для логирования
        cursor.execute("SELECT * FROM additional_phone_numbers WHERE id = %s", (additional_number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Дополнительный номер не найден'}), 404
        
        # Удаляем номер
        cursor.execute("DELETE FROM additional_phone_numbers WHERE id = %s", (additional_number_id,))
        conn.commit()
        
        # Логируем удаление
        try:
            cursor.execute("""
                INSERT INTO phone_numbers_history 
                (operator_id, old_number, new_number)
                VALUES (%s, %s, %s)
            """, (
                current_user.id,
                number_data['phone_number'],
                number_data['phone_number'] + " - Удален"
            ))
            conn.commit()
        except Exception as log_err:
            logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
        
        return jsonify({'success': True, 'message': 'Дополнительный номер успешно удален'})
    except Exception as e:
        logger.error(f"Ошибка при удалении дополнительного номера: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при удалении дополнительного номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@admin_routes_bp.route('/api/get_number', methods=['GET'])
@login_required
def get_number_api():
    """Получение данных номера по ID"""
    logger.debug("Начало выполнения функции get_number_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        return jsonify({'success': False, 'message': 'Недостаточно прав для выполнения операции'})
    
    number_id = request.args.get('id')
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем данные номера
        cursor.execute("""
            SELECT id, phone_number, department, assigned_to, 
                   whatsapp, telegram, blocked, prohibit_issuance
            FROM corp_numbers WHERE id = %s
        """, (number_id,))
        number = cursor.fetchone()
        
        if not number:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        return jsonify({'success': True, 'number': number})
    except Exception as e:
        logger.error(f"Ошибка при получении данных номера: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при получении данных номера: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

def fix_phone_number_prefix(phone_number):
    """
    Исправляет дублирующиеся префиксы +7 в номерах телефонов
    """
    if not phone_number:
        return ''
    
    # Удаляем пробелы и скобки
    cleaned = re.sub(r'[\s\(\)]', '', phone_number)
    
    # Исправляем двойные префиксы +7+7
    if cleaned.startswith('+7+7'):
        cleaned = '+7' + cleaned[3:]
    
    # Убираем еще лишние +7, если они есть в середине номера
    cleaned = re.sub(r'\+7(\+7)+', '+7', cleaned)
    
    # Если номер начинается с 7 (без +), добавляем +
    if cleaned.startswith('7') and not cleaned.startswith('+7'):
        cleaned = '+' + cleaned
    
    return cleaned

@admin_routes_bp.route('/api/fix_phone_prefixes', methods=['POST'])
@login_required
def fix_phone_prefixes():
    """Исправление дублирующихся префиксов +7 в номерах телефонов"""
    conn = None
    try:
        # Создаем подключение к базе данных
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем все номера из базы данных
        cursor.execute("SELECT id, phone_number FROM corp_numbers WHERE phone_number LIKE '+7+7%'")
        numbers = cursor.fetchall()
        fixed_count = 0
        
        # Проходим по всем номерам и исправляем префиксы
        for number in numbers:
            original = number['phone_number']
            fixed = fix_phone_number_prefix(original)
            
            if original != fixed:
                cursor.execute(
                    "UPDATE corp_numbers SET phone_number = %s WHERE id = %s",
                    (fixed, number['id'])
                )
                fixed_count += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'fixed_count': fixed_count,
            'message': f'Исправлено {fixed_count} номеров с дублирующимися префиксами'
        })
    
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Ошибка при исправлении префиксов: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Произошла ошибка: {str(e)}'
        })
    
    finally:
        if conn:
            conn.close() 