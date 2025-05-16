from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import current_user
from app.utils import create_db_connection, login_required
import logging
from datetime import datetime
from app.routes.admin import admin_routes_bp
from app.routes.auth import redirect_based_on_role
import hashlib
import os
from werkzeug.utils import secure_filename
import time

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
                WHERE u.department_id = %s AND u.fire_date IS NULL
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
                WHERE u.fire_date IS NULL
                ORDER BY d.name, u.full_name
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
@admin_routes_bp.route('/admin/api/fire_employee', methods=['POST'])
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
                status = 'fired'
            WHERE id = %s
        """, (fire_date, employee_id))
        
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
        
        # Получаем список отделов из таблицы Department с учетом порядка отображения
        cursor.execute('SELECT id, name, display_order FROM Department ORDER BY display_order ASC, name ASC')
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
@login_required
def add_employee_api():
    """Добавление нового сотрудника через API"""
    logger.debug("Начало выполнения функции add_employee_api")
    
    if current_user.role != 'admin' and current_user.role != 'leader':
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
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        
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
    if current_user.role != 'admin' and current_user.role != 'leader':
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
        
        logger.debug(f"Получено {len(ordered_departments_dict)} отделов и {total_numbers} номеров")
        
        return render_template('admin/phone_numbers.html',
                               numbers=numbers,
                               departments_dict=ordered_departments_dict,
                               departments=departments,
                               dept_id_map=dept_id_map,  # Передаем сопоставление имени->ID
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
    """Обновление порядка отделов через API с помощью drag-and-drop"""
    # Расширенное логирование для отладки ошибки 405
    logger.critical("=================== НАЧАЛО ОБРАБОТКИ ЗАПРОСА ===================")
    logger.critical(f"ПУТЬ URL: {request.path}")
    logger.critical(f"ПОЛНЫЙ URL: {request.url}")
    logger.critical(f"МЕТОД ЗАПРОСА: {request.method}")
    logger.critical(f"ЗАГОЛОВКИ: {dict(request.headers)}")
    logger.critical(f"ДАННЫЕ JSON: {request.get_data(as_text=True)}")
    logger.critical(f"BLUEPRINT: {request.blueprint}")
    logger.critical(f"ENDPOINT: {request.endpoint}")
    logger.critical("=================== КОНЕЦ ДАННЫХ ЗАПРОСА ===================")
    
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
@login_required
def move_number_api():
    """Перемещение номера между отделами"""
    logger.debug("Начало выполнения функции move_number_api")
    if current_user.role != 'admin' and current_user.role != 'leader':
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
    """Получить полностью свободные номера (не принадлежат ни одному отделу)"""
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, phone_number, assigned_to, whatsapp, telegram, blocked, prohibit_issuance, created_at, updated_at
            FROM corp_numbers
            WHERE department IS NULL OR department = ''
        """)
        numbers = cursor.fetchall()
        return jsonify({'success': True, 'numbers': numbers})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 