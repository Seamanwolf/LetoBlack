from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import current_user
from app.utils import create_db_connection, login_required
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from app.routes.admin import admin_routes_bp

@admin_routes_bp.route('/personnel')
@login_required
def personnel():
    logger.debug("Начало выполнения функции personnel")
    if current_user.role != 'admin' and current_user.role != 'leader':
        logger.warning(f"Отказано в доступе пользователю {current_user.login} с ролью {current_user.role}")
        flash('У вас нет доступа к этой странице', 'error')
        return redirect(url_for('admin_routes.admin_dashboard'))
    
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
        
        # Получаем список отделов из таблицы Department
        cursor.execute('SELECT id, name FROM Department ORDER BY name')
        departments = cursor.fetchall()
        
        # Получаем сотрудников по отделам
        employees_by_department = {}
        for department in departments:
            cursor.execute('''
                SELECT 
                    u.id,
                    u.full_name,
                    u.position,
                    u.phone,
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
                    u.phone,
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
                             employees_by_department=employees_by_department)
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы персонала: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return redirect(url_for('admin_routes.admin_dashboard'))
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
        
        # Получаем данные сотрудника
        cursor.execute("""
            SELECT 
                id, 
                full_name, 
                position, 
                department_id,
                (SELECT name FROM Department WHERE id = User.department_id) as department,
                phone as Phone,
                role,
                hire_date,
                status,
                fire_date,
                corporate_email
            FROM User 
            WHERE id = %s
        """, (employee_id,))
        
        employee = cursor.fetchone()
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
            
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

@admin_routes_bp.route('/api/update_employee', methods=['POST'])
@login_required
def update_employee_api():
    """Обновление данных сотрудника через API"""
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
            'full_name', 'position', 'phone', 'department', 'role', 'corporate_email'
        ]

        for field in text_fields:
            new_value = data.get(field)
            if new_value is not None and field in employee and new_value != employee[field]:
                update_fields[field] = new_value

        # Обработка дат
        date_fields = ['hire_date']
        for field in date_fields:
            new_value = data.get(field)
            if new_value and field in employee:
                try:
                    # Проверяем формат даты
                    if isinstance(new_value, str):
                        formatted_date = datetime.strptime(new_value, '%Y-%m-%d').date()
                        if formatted_date != employee[field]:
                            update_fields[field] = formatted_date
                except ValueError:
                    logger.warning(f"Неверный формат даты для поля {field}: {new_value}")
                    continue

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
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, существует ли сотрудник
        cursor.execute("SELECT id, full_name FROM User WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            logger.warning(f"Сотрудник с ID={employee_id} не найден")
            return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
        
        # Получаем дополнительные данные
        corporate_email = data.get('corporate_email', '')
        personal_email = data.get('personal_email', '')
        crm_id = data.get('crm_id', '')
        password = data.get('password', '')
        
        # Обновляем данные сотрудника
        cursor.execute("""
            UPDATE User 
            SET 
                fire_date = %s,
                corporate_email = %s,
                personal_email = %s,
                crm_id = %s,
                password = %s,
                status = 'offline'
            WHERE id = %s
        """, (fire_date, corporate_email, personal_email, crm_id, password, employee_id))
        
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
        return redirect(url_for('auth.login'))
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Получаем список уволенных сотрудников
        cursor.execute("""
            SELECT u.*, d.name as department_name
            FROM User u
            LEFT JOIN Department d ON u.department_id = d.id
            WHERE u.status = 'fired' OR u.fire_date IS NOT NULL
            ORDER BY u.fire_date DESC
        """)
        fired_employees = cursor.fetchall()
        
        # Форматируем даты для отображения
        for employee in fired_employees:
            if employee['fire_date']:
                employee['fire_date'] = employee['fire_date'].strftime('%d.%m.%Y')
            if employee['hire_date']:
                employee['hire_date'] = employee['hire_date'].strftime('%d.%m.%Y')
        
        return render_template('admin/fired_employees.html',
                              fired_employees=fired_employees)
    
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы уволенных сотрудников: {e}")
        flash(f'Ошибка при получении данных: {str(e)}', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    finally:
        cursor.close()
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
        
        department_id = data.get('id')
        new_order = data.get('order')
        
        if not department_id or not new_order:
            logger.warning("ID отдела или порядок не указаны")
            return jsonify({'success': False, 'message': 'ID отдела или порядок не указаны'}), 400
        
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существование отдела
        cursor.execute("SELECT id, name FROM Department WHERE id = %s", (department_id,))
        department = cursor.fetchone()
        
        if not department:
            logger.warning(f"Отдел с ID={department_id} не найден")
            return jsonify({'success': False, 'message': 'Отдел не найден'}), 404
        
        # Обновляем порядок отдела
        cursor.execute("""
            UPDATE Department
            SET display_order = %s 
            WHERE id = %s
        """, (new_order, department_id))
        
        conn.commit()
        
        logger.info(f"Порядок отдела {department['name']} (ID={department_id}) успешно обновлен")
        return jsonify({
            'success': True, 
            'message': f"Порядок отдела {department['name']} успешно обновлен"
        })
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении порядка отдела: {str(e)}")
        return jsonify({'success': False, 'message': f'Ошибка при обновлении порядка отдела: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close() 