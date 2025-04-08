# reception_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from flask_login import login_required, current_user
from app.utils import create_db_connection
from datetime import datetime
import mysql.connector
import json
import os

admin_bp = Blueprint('admin', __name__, template_folder='templates/reception')

def get_unified_departments_and_positions():
    """
    Получает унифицированный список отделов и должностей, согласованный между разными частями системы.
    Отделяет роли (должности) от отделов.
    """
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем список всех отделов
        cursor.execute("""
            SELECT DISTINCT department FROM User 
            WHERE department IS NOT NULL AND department != '' 
            ORDER BY department
        """)
        departments_from_user = [row['department'] for row in cursor.fetchall()]
        
        # Получаем список отделов из таблицы Departments (если такая есть)
        try:
            cursor.execute("SELECT name FROM Department ORDER BY name")
            departments_from_dept_table = [row['name'] for row in cursor.fetchall()]
        except mysql.connector.Error:
            departments_from_dept_table = []
            
        # Получаем список отделов из телефонных номеров
        cursor.execute("""
            SELECT DISTINCT department FROM user_phone_numbers 
            WHERE department IS NOT NULL AND department != ''
            ORDER BY department
        """)
        departments_from_phones = [row['department'] for row in cursor.fetchall()]
        
        # Объединяем все списки и удаляем дубликаты
        all_departments = list(set(departments_from_user + departments_from_dept_table + departments_from_phones))
        
        # Получаем список должностей (ролей)
        cursor.execute("""
            SELECT DISTINCT position FROM User 
            WHERE position IS NOT NULL AND position != '' 
            ORDER BY position
        """)
        positions = [row['position'] for row in cursor.fetchall()]
        
        # Список должностей, которые могут ошибочно быть в отделах
        role_keywords = [
            'Руководитель', 'руководитель', 
            'Директор', 'директор',
            'Менеджер', 'менеджер',
            'Администратор', 'администратор',
            'HR', 'hr',
            'Зам', 'зам'
        ]
        
        # Определяем, какие записи из departments на самом деле являются должностями
        departments_to_remove = []
        roles_to_add = []
        
        for dept in all_departments:
            # Проверяем, содержит ли название отдела ключевые слова должностей
            if any(keyword in dept for keyword in role_keywords):
                # Проверяем, есть ли сотрудники с этим отделом
                cursor.execute("SELECT COUNT(*) as count FROM User WHERE department = %s", (dept,))
                count = cursor.fetchone()['count']
                
                # Если это отдел с малым количеством сотрудников, вероятно это роль
                if count <= 3:  # Порог, который можно настроить
                    departments_to_remove.append(dept)
                    if dept not in positions:
                        roles_to_add.append(dept)
        
        # Удаляем должности из списка отделов
        clean_departments = [dept for dept in all_departments if dept not in departments_to_remove]
        
        # Добавляем найденные должности в список должностей
        positions.extend(roles_to_add)
        
        # Окончательная сортировка
        sorted_departments = sorted(clean_departments)
        sorted_positions = sorted(set(positions))  # Удаляем дубликаты
        
        return sorted_departments, sorted_positions
        
    except mysql.connector.Error as err:
        current_app.logger.error(f"Ошибка при получении унифицированного списка отделов и должностей: {err}")
        return [], []
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/dashboard')
@login_required
def reception_dashboard():
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Выбираем всех АКТИВНЫХ сотрудников для дашборда Ресепшн
        query = """
            SELECT User.id, User.full_name, User.department, 
                   User.Phone AS personal_phone, User.corp_phone AS corporate_number, 
                   User.office, User.login AS login_pc, User.hire_date, User.is_active,
                   User.status, Candidates.password, Candidates.birth_date, Candidates.personal_email, 
                   User.role, User.position, User.pc_login, User.pc_password, 
                   Candidates.crm_id, User.documents, User.rr, User.site
            FROM User 
            LEFT JOIN Candidates ON User.login = Candidates.login_pc
            WHERE User.termination_date IS NULL OR User.termination_date = ''
            ORDER BY User.department, User.position, User.full_name ASC
        """
        cursor.execute(query)
        employees = cursor.fetchall()
        
        # Получаем статистику по отделам (количество сотрудников)
        query_stats = """
            SELECT department, COUNT(*) as count
            FROM User
            WHERE termination_date IS NULL OR termination_date = ''
            GROUP BY department
            ORDER BY department
        """
        cursor.execute(query_stats)
        department_stats = cursor.fetchall()
        
        # Преобразуем статистику в словарь для удобства
        department_counts = {item['department']: item['count'] for item in department_stats}
        
        # Используем унифицированный список отделов
        sorted_departments, sorted_positions = get_unified_departments_and_positions()
        
        # Отладочный вывод
        current_app.logger.info(f"Список отделов для дашборда (унифицированный): {sorted_departments}")
        
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения данных для дашборда Ресепшн: %s", err)
        flash("Ошибка получения данных.", "danger")
        employees = []
        department_counts = {}
        sorted_departments = []
        sorted_positions = []
    finally:
        cursor.close()
        connection.close()
    
    return render_template("reception/dashboard.html", 
                           employees=employees, 
                           department_counts=department_counts,
                           sorted_departments=sorted_departments,
                           positions=sorted_positions)

@admin_bp.route('/get_employee_data', methods=['GET'])
@login_required
def get_employee_data():
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({"success": False, "error": "ID сотрудника не указан"}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем основные данные сотрудника
        query = """
            SELECT U.*, 
                  C.birth_date, C.city as office, C.personal_email, C.crm_id, 
                  C.referral, C.password, C.corporate_email
            FROM User AS U
            LEFT JOIN Candidates AS C ON U.login = C.login_pc
            WHERE U.id = %s
        """
        cursor.execute(query, (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            return jsonify({"success": False, "error": "Сотрудник не найден"}), 404
        
        # Форматируем даты для JSON
        if employee.get('hire_date') and not isinstance(employee['hire_date'], str):
            employee['hire_date'] = employee['hire_date'].strftime('%Y-%m-%d')
        if employee.get('birth_date') and not isinstance(employee['birth_date'], str):
            employee['birth_date'] = employee['birth_date'].strftime('%Y-%m-%d')
        if employee.get('termination_date') and not isinstance(employee['termination_date'], str):
            employee['termination_date'] = employee['termination_date'].strftime('%Y-%m-%d')
        if employee.get('fire_date') and not isinstance(employee['fire_date'], str):
            employee['fire_date'] = employee['fire_date'].strftime('%Y-%m-%d')
        
        # Проверяем, есть ли фото
        cursor.execute("SELECT photo_url FROM EmployeePhotos WHERE employee_id = %s", (employee_id,))
        photo = cursor.fetchone()
        if photo:
            employee['photo_url'] = photo['photo_url']
        
        # Переименуем поля для совместимости с интерфейсом
        if 'documents' in employee:
            employee['has_documents'] = employee['documents']
        if 'rr' in employee:
            employee['has_rr'] = employee['rr']
        if 'site' in employee:
            employee['has_site'] = employee['site']
        if 'Phone' in employee:
            employee['personal_phone'] = employee['Phone']
        
        return jsonify(employee)
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения данных сотрудника: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/get_employee_history', methods=['GET'])
@login_required
def get_employee_history():
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({"success": False, "error": "ID сотрудника не указан"}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем данные из User, чтобы найти login_pc
        cursor.execute("SELECT login FROM User WHERE id = %s", (employee_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "error": "Сотрудник не найден"}), 404
        
        login_pc = user['login']
        
        # Получаем историю изменений из CandidateHistory по login_pc через Candidates
        query = """
            SELECT CH.* 
            FROM CandidateHistory CH
            JOIN Candidates C ON CH.candidate_id = C.id
            WHERE C.login_pc = %s
            ORDER BY CH.timestamp DESC
        """
        cursor.execute(query, (login_pc,))
        history = cursor.fetchall()
        
        # Форматируем timestamp для JSON
        for entry in history:
            entry['timestamp'] = entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        
        # Также получаем историю из UserHistory
        query = """
            SELECT * FROM UserHistory
            WHERE user_id = %s
            ORDER BY timestamp DESC
        """
        cursor.execute(query, (employee_id,))
        user_history = cursor.fetchall()
        
        # Форматируем timestamp для JSON
        for entry in user_history:
            entry['timestamp'] = entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            
        # Объединяем истории
        combined_history = history + user_history
        
        # Сортируем по timestamp (от новых к старым)
        combined_history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({"success": True, "history": combined_history})
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения истории сотрудника: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/get_phone_history', methods=['GET'])
@login_required
def get_phone_history():
    """
    Получает историю изменений телефонных номеров для сотрудника из таблицы phone_numbers_history
    """
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    employee_id = request.args.get('employee_id')
    if not employee_id:
        return jsonify({"success": False, "error": "ID сотрудника не указан"}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем историю номеров из phone_numbers_history
        query = """
            SELECT 
                pnh.id, 
                pnh.operator_id, 
                pnh.old_number, 
                pnh.new_number, 
                pnh.changed_at,
                u.full_name as employee_name
            FROM phone_numbers_history pnh
            LEFT JOIN User u ON pnh.operator_id = u.id
            WHERE pnh.operator_id = %s
            ORDER BY pnh.changed_at DESC
        """
        cursor.execute(query, (employee_id,))
        history = cursor.fetchall()
        
        # Форматируем даты для JSON
        for entry in history:
            if entry['changed_at']:
                entry['changed_at'] = entry['changed_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({"success": True, "history": history})
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения истории телефонных номеров: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/get_number_history', methods=['GET'])
@login_required
def get_number_history():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    corporate_number = request.args.get('number')
    if not corporate_number:
        return jsonify({"success": False, "error": "Номер не указан"}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Так как таблица NumberHistory не существует, возвращаем пустой список
        return jsonify({"success": True, "history": []})
        
        '''
        # Получаем историю номера
        query = """
            SELECT 
                NH.date, 
                NH.notes,
                U.full_name as user_name
            FROM NumberHistory NH
            JOIN User U ON NH.user_id = U.id
            WHERE NH.number = %s
            ORDER BY NH.date DESC
        """
        cursor.execute(query, (corporate_number,))
        history = cursor.fetchall()
        
        # Форматируем даты для JSON
        for entry in history:
            entry['date'] = entry['date'].strftime('%Y-%m-%d')
        
        return jsonify({"success": True, "history": history})
        '''
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения истории номера: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/update_employee', methods=['POST'])
@login_required
def update_employee():
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    employee_id = request.form.get('id')
    if not employee_id:
        return jsonify({"success": False, "error": "ID сотрудника не указан"}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем текущие данные для сравнения и логирования изменений
        cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
        old_user_data = cursor.fetchone()
        if not old_user_data:
            return jsonify({"success": False, "error": "Сотрудник не найден"}), 404
        
        # Получаем login_pc для поиска в таблице Candidates
        login_pc = old_user_data['login']
        
        # Обновляем основные данные в таблице User
        user_update_fields = {
            'full_name': request.form.get('full_name'),
            'department': request.form.get('department'),
            'position': request.form.get('position'),
            'Phone': request.form.get('personal_phone'),
            'corp_phone': request.form.get('corporate_number'),
            'hire_date': request.form.get('hire_date') or None,
            'termination_date': request.form.get('termination_date') or None,
            'fire_date': request.form.get('fire_date') or None,
            'office': request.form.get('office'),
            'pc_login': request.form.get('pc_login'),
            'pc_password': request.form.get('pc_password'),
            'personal_email': request.form.get('personal_email'),
            'documents': 1 if request.form.get('documents') == 'on' else 0,
            'rr': 1 if request.form.get('rr') == 'on' else 0,
            'site': 1 if request.form.get('site') == 'on' else 0,
            'notes': request.form.get('notes', '')
        }
        
        # Строим SQL запрос
        update_fields = []
        update_values = []
        for field, value in user_update_fields.items():
            if value is not None:  # Исключаем None значения
                update_fields.append(f"{field} = %s")
                update_values.append(value)
        
        if update_fields:
            update_query = f"UPDATE User SET {', '.join(update_fields)} WHERE id = %s"
            update_values.append(employee_id)
            cursor.execute(update_query, update_values)
            connection.commit()
            
            # Проверяем изменение корпоративного номера для записи в phone_numbers_history
            old_corp_phone = old_user_data.get('corp_phone')
            new_corp_phone = user_update_fields.get('corp_phone')
            
            if old_corp_phone != new_corp_phone and new_corp_phone is not None and new_corp_phone != '':
                # Добавляем запись в таблицу phone_numbers_history
                phone_history_query = """
                    INSERT INTO phone_numbers_history (operator_id, old_number, new_number)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(phone_history_query, (
                    employee_id,
                    old_corp_phone if old_corp_phone else '',
                    new_corp_phone
                ))
                connection.commit()
                current_app.logger.info(f"Добавлена запись в phone_numbers_history для сотрудника ID={employee_id}, старый номер: {old_corp_phone}, новый номер: {new_corp_phone}")
            
            # Логируем изменения в UserHistory
            now = datetime.now()
            for field, new_value in user_update_fields.items():
                old_value = old_user_data.get(field)
                # Проверяем, изменилось ли значение
                if old_value != new_value and new_value is not None:
                    # Форматируем даты для логирования
                    if isinstance(old_value, datetime):
                        old_value = old_value.strftime('%Y-%m-%d')
                    if field in ('hire_date', 'termination_date', 'fire_date') and new_value:
                        try:
                            # Проверяем, что дата в правильном формате
                            datetime.strptime(new_value, '%Y-%m-%d')
                        except ValueError:
                            continue
                    
                    # Логируем изменение
                    log_query = """
                        INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by, changed_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(log_query, (
                        employee_id,
                        field,
                        str(old_value) if old_value is not None else "",
                        str(new_value),
                        current_user.id,
                        now
                    ))
                    connection.commit()
        
        # Обновляем данные в Candidates, если есть login_pc
        if login_pc:
            cursor.execute("SELECT id FROM Candidates WHERE login_pc = %s", (login_pc,))
            candidate = cursor.fetchone()
            if candidate:
                candidate_id = candidate['id']
                # Получаем текущие данные кандидата
                cursor.execute("SELECT * FROM Candidates WHERE id = %s", (candidate_id,))
                old_candidate_data = cursor.fetchone()
                
                # Поля, которые можно обновить в Candidates
                candidate_update_fields = {
                    'corporate_email': request.form.get('corporate_email'),
                    'password': request.form.get('password'),
                    'crm_id': request.form.get('crm_id'),
                    'personal_phone': request.form.get('personal_phone'),
                    'birth_date': request.form.get('birth_date') or None,
                    'city': request.form.get('office')
                }
                
                # Строим SQL запрос
                update_fields = []
                update_values = []
                for field, value in candidate_update_fields.items():
                    if value is not None:  # Исключаем None значения
                        update_fields.append(f"{field} = %s")
                        update_values.append(value)
                
                if update_fields:
                    update_query = f"UPDATE Candidates SET {', '.join(update_fields)} WHERE id = %s"
                    update_values.append(candidate_id)
                    cursor.execute(update_query, update_values)
                    connection.commit()
                    
                    # Логируем изменения в CandidateHistory
                    now = datetime.now()
                    for field, new_value in candidate_update_fields.items():
                        old_value = old_candidate_data.get(field)
                        # Проверяем, изменилось ли значение
                        if old_value != new_value and new_value is not None:
                            # Форматируем даты для логирования
                            if isinstance(old_value, datetime):
                                old_value = old_value.strftime('%Y-%m-%d')
                            if field == 'birth_date' and new_value:
                                try:
                                    # Проверяем, что дата в правильном формате
                                    datetime.strptime(new_value, '%Y-%m-%d')
                                except ValueError:
                                    continue
                            
                            # Логируем изменение
                            log_query = """
                                INSERT INTO CandidateHistory (candidate_id, timestamp, user, field_changed, old_value, new_value)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """
                            cursor.execute(log_query, (
                                candidate_id,
                                now,
                                current_user.full_name,
                                field,
                                str(old_value) if old_value is not None else "",
                                str(new_value)
                            ))
                            connection.commit()
        
        # Обработка загруженного фото, если есть
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename:
                try:
                    # Создаем директорию для хранения фото, если еще не существует
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'employee_photos')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # Генерируем уникальное имя файла
                    filename = f"{employee_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
                    filepath = os.path.join(upload_folder, filename)
                    
                    # Сохраняем файл
                    photo.save(filepath)
                    
                    # Путь для доступа из веб
                    photo_url = url_for('static', filename=f'uploads/employee_photos/{filename}')
                    
                    # Обновляем или добавляем запись в EmployeePhotos
                    cursor.execute("SELECT * FROM EmployeePhotos WHERE employee_id = %s", (employee_id,))
                    photo_record = cursor.fetchone()
                    
                    if photo_record:
                        query = "UPDATE EmployeePhotos SET photo_url = %s WHERE employee_id = %s"
                        cursor.execute(query, (photo_url, employee_id))
                    else:
                        query = "INSERT INTO EmployeePhotos (employee_id, photo_url) VALUES (%s, %s)"
                        cursor.execute(query, (employee_id, photo_url))
                    connection.commit()
                    
                    current_app.logger.info(f"Фото сохранено: {filepath}, URL: {photo_url}")
                except Exception as e:
                    current_app.logger.error(f"Ошибка при сохранении фото: {str(e)}")
        
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка обновления данных сотрудника: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/numbers')
@login_required
def phone_numbers():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        flash("Доступ запрещён.", "danger")
        return redirect(url_for('auth.login'))
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем номера из таблицы user_phone_numbers
        query = """
            SELECT upn.id, upn.phone_number, upn.prohibit_issuance, upn.department,
                   u.full_name AS assigned_to
            FROM user_phone_numbers upn
            LEFT JOIN User u ON upn.assigned_operator_id = u.id
            ORDER BY upn.department, upn.phone_number
        """
        cursor.execute(query)
        numbers = cursor.fetchall()
        
        # Используем унифицированный список отделов
        sorted_departments, _ = get_unified_departments_and_positions()
        
        # Отладочный вывод
        current_app.logger.info(f"Список отделов для выпадающего списка (унифицированный): {sorted_departments}")
        
        # Проверяем, не пустой ли список отделов
        if not sorted_departments:
            current_app.logger.warning("Список отделов пуст")
            flash("Внимание: список отделов пуст. Для корректной работы системы необходимо добавить отделы.", "warning")
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения номеров: %s", err)
        flash("Ошибка получения номеров.", "danger")
        numbers = []
        sorted_departments = []
    finally:
        cursor.close()
        connection.close()
    
    # Убираем режим отладки
    current_app.logger.info(f"Отправка в шаблон. sorted_departments: {sorted_departments}, длина: {len(sorted_departments)}")
    return render_template("reception/phone_numbers.html", 
                          numbers=numbers, 
                          sorted_departments=sorted_departments,
                          debug=False)

@admin_bp.route('/add_number', methods=['POST'])
@login_required
def add_number():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    data = request.get_json()  # ожидается JSON с phone_number и department
    
    # Подробная отладка начала функции
    current_app.logger.info("=== ОТЛАДКА ADD_NUMBER ===")
    current_app.logger.info(f"Получены данные: {data}")
    
    # Если это тестовый запрос, отвечаем без добавления в базу
    if data.get('test') == True:
        current_app.logger.info("Тестовый запрос - проверка соединения")
        
        # Проверяем соединение с БД
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT COUNT(*) as count FROM user_phone_numbers")
                result = cursor.fetchone()
                
                # Проверяем наличие таблицы user_phone_numbers
                cursor.execute("SHOW TABLES LIKE 'user_phone_numbers'")
                tables = cursor.fetchall()
                
                # Проверяем структуру таблицы
                cursor.execute("DESCRIBE user_phone_numbers")
                columns = cursor.fetchall()
                
                connection_info = {
                    'connection': True,
                    'db_info': {
                        'host': os.getenv('DB_HOST', '192.168.4.14'),
                        'user': os.getenv('DB_USER', 'test_user'),
                        'database': os.getenv('DB_NAME', 'Brokers')
                    },
                    'table_exists': len(tables) > 0,
                    'table_structure': columns,
                    'record_count': result['count'] if result else 0
                }
                
                return jsonify({
                    'success': True, 
                    'message': 'Соединение с базой данных установлено успешно', 
                    'connection_info': connection_info
                })
            except mysql.connector.Error as err:
                current_app.logger.error(f"Ошибка при тестовом запросе: {err}")
                return jsonify({
                    'success': False, 
                    'message': f'Ошибка при выполнении тестового запроса: {str(err)}',
                    'error_type': type(err).__name__
                }), 500
            finally:
                cursor.close()
                connection.close()
        else:
            current_app.logger.error("Не удалось подключиться к БД при тестовом запросе")
            return jsonify({
                'success': False, 
                'message': 'Не удалось подключиться к базе данных',
                'db_config': {
                    'host': os.getenv('DB_HOST', '192.168.4.14'),
                    'user': os.getenv('DB_USER', 'test_user'),
                    'database': os.getenv('DB_NAME', 'Brokers')
                }
            }), 500
    
    phone_number = data.get('phone_number')
    department = data.get('department')
    
    current_app.logger.info(f"Извлеченные значения: phone_number='{phone_number}', department='{department}'")
    
    # Проверяем корректность данных
    if not phone_number or not department:
        current_app.logger.warning(f"Недостаточно данных: phone_number='{phone_number}', department='{department}'")
        return jsonify({'success': False, 'message': 'Необходимо указать номер телефона и отдел'}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Проверяем, есть ли уже такой номер в базе
        check_query = "SELECT * FROM user_phone_numbers WHERE phone_number = %s"
        current_app.logger.info(f"Проверка существования номера: SQL={check_query}, params=({phone_number},)")
        
        cursor.execute(check_query, (phone_number,))
        existing_number = cursor.fetchone()
        
        if existing_number:
            current_app.logger.warning(f"Номер '{phone_number}' уже существует в базе: {existing_number}")
            return jsonify({'success': False, 'message': 'Номер уже существует в базе'}), 400
        
        # Проверяем, существует ли указанный отдел в таблице User
        dept_check_query = "SELECT COUNT(*) as count FROM User WHERE department = %s"
        current_app.logger.info(f"Проверка отдела в User: SQL={dept_check_query}, params=({department},)")
        
        cursor.execute(dept_check_query, (department,))
        department_exists = cursor.fetchone()['count'] > 0
        current_app.logger.info(f"Отдел '{department}' в User: {department_exists}")
        
        # Если отдела нет в User, проверяем user_phone_numbers
        if not department_exists:
            dept_check_query2 = "SELECT COUNT(*) as count FROM user_phone_numbers WHERE department = %s"
            current_app.logger.info(f"Проверка отдела в phone_numbers: SQL={dept_check_query2}, params=({department},)")
            
            cursor.execute(dept_check_query2, (department,))
            department_exists = cursor.fetchone()['count'] > 0
            current_app.logger.info(f"Отдел '{department}' в phone_numbers: {department_exists}")
        
        # Добавляем номер
        insert_query = "INSERT INTO user_phone_numbers (phone_number, department) VALUES (%s, %s)"
        current_app.logger.info(f"Добавление номера: SQL={insert_query}, params=({phone_number}, {department})")
        
        try:
            cursor.execute(insert_query, (phone_number, department))
            insert_result = cursor.rowcount
            current_app.logger.info(f"Результат добавления номера: rowcount={insert_result}")
            
            # Получаем ID добавленного номера для журнала
            cursor.execute("SELECT LAST_INSERT_ID() as id")
            number_id = cursor.fetchone()['id']
            current_app.logger.info(f"ID добавленного номера: {number_id}")
            
            # Проверим, действительно ли номер добавлен
            cursor.execute("SELECT * FROM user_phone_numbers WHERE id = %s", (number_id,))
            check_added = cursor.fetchone()
            current_app.logger.info(f"Проверка добавленного номера: {check_added}")
            
            # Добавляем запись в историю через phone_numbers_history
            try:
                log_query = """
                    INSERT INTO phone_numbers_history (operator_id, new_number, note)
                    VALUES (%s, %s, %s)
                """
                log_params = (current_user.id, phone_number, f"Номер добавлен в отдел {department}")
                current_app.logger.info(f"Добавление в историю: SQL={log_query}, params={log_params}")
                
                cursor.execute(log_query, log_params)
                log_result = cursor.rowcount
                current_app.logger.info(f"Результат добавления в историю: rowcount={log_result}")
                
                connection.commit()
                current_app.logger.info("Транзакция подтверждена")
            except mysql.connector.Error as log_err:
                # Если ошибка при записи в историю, просто логируем её, но не прерываем работу
                current_app.logger.error(f"Ошибка при добавлении записи в историю номеров: {log_err}")
                # Но все равно подтверждаем транзакцию для номера
                connection.commit()
        except mysql.connector.Error as ins_err:
            current_app.logger.error(f"Ошибка при добавлении номера: {ins_err}")
            raise ins_err
        
        # Добавляем предупреждение, если отдела нет
        if not department_exists:
            current_app.logger.warning(f"Отдел '{department}' не существует в системе")
            return jsonify({
                'success': True, 
                'message': 'Номер добавлен, но указанный отдел не существует в системе. Рекомендуется добавить отдел в справочник.',
                'warning': True
            })
        
        current_app.logger.info("Номер успешно добавлен")
        return jsonify({'success': True, 'message': 'Номер добавлен'})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error(f"КРИТИЧЕСКАЯ ОШИБКА при добавлении номера: {err}")
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        connection.close()
        current_app.logger.info("=== КОНЕЦ ОТЛАДКИ ADD_NUMBER ===")

@admin_bp.route('/move_number', methods=['POST'])
@login_required
def move_number():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    number_id = data.get('number_id')
    new_department = data.get('new_department')
    
    if not number_id or not new_department:
        return jsonify({'success': False, 'message': 'Не указан ID номера или новый отдел'}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем текущие данные для логирования
        cursor.execute("SELECT * FROM user_phone_numbers WHERE id = %s", (number_id,))
        old_data = cursor.fetchone()
        if not old_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Обновляем отдел
        query = "UPDATE user_phone_numbers SET department = %s WHERE id = %s"
        cursor.execute(query, (new_department, number_id))
        connection.commit()
        
        # Логируем изменение в phone_numbers_history
        try:
            log_query = """
                INSERT INTO phone_numbers_history (operator_id, old_number, new_number, note)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(log_query, (
                current_user.id,
                old_data['phone_number'],
                old_data['phone_number'],
                f"Номер перемещен из отдела {old_data['department']} в отдел {new_department}"
            ))
            connection.commit()
        except mysql.connector.Error as log_err:
            # Если ошибка при записи в историю, просто логируем её, но не прерываем работу
            current_app.logger.error("Ошибка при добавлении записи в историю номеров: %s", log_err)
        
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при перемещении номера: %s", err)
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/update_number', methods=['POST'])
@login_required
def update_number():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    number_id = data.get('number_id')
    phone_number = data.get('phone_number')
    prohibit_issuance = data.get('prohibit_issuance')
    
    if not number_id or not phone_number:
        return jsonify({'success': False, 'message': 'Не указаны обязательные поля'}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем текущие данные для логирования
        cursor.execute("SELECT * FROM user_phone_numbers WHERE id = %s", (number_id,))
        old_data = cursor.fetchone()
        if not old_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Обновляем данные
        query = "UPDATE user_phone_numbers SET phone_number = %s, prohibit_issuance = %s WHERE id = %s"
        cursor.execute(query, (phone_number, prohibit_issuance, number_id))
        connection.commit()
        
        # Если номер изменился, логируем это в phone_numbers_history
        if old_data['phone_number'] != phone_number:
            try:
                log_query = """
                    INSERT INTO phone_numbers_history (operator_id, old_number, new_number, note)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(log_query, (
                    current_user.id,
                    old_data['phone_number'], 
                    phone_number,
                    f"Номер изменен с {old_data['phone_number']} на {phone_number}"
                ))
                connection.commit()
            except mysql.connector.Error as log_err:
                # Если ошибка при записи в историю, просто логируем её, но не прерываем работу
                current_app.logger.error("Ошибка при добавлении записи в историю номеров: %s", log_err)
        
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при обновлении номера: %s", err)
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/update_prohibit', methods=['POST'])
@login_required
def update_prohibit():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    number_id = data.get('number_id')
    prohibit_issuance = data.get('prohibit_issuance')
    
    if number_id is None or prohibit_issuance is None:
        return jsonify({'success': False, 'message': 'Не указаны обязательные поля'}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        query = "UPDATE user_phone_numbers SET prohibit_issuance = %s WHERE id = %s"
        cursor.execute(query, (prohibit_issuance, number_id))
        connection.commit()
        
        # Получаем данные номера для лога
        cursor.execute("SELECT * FROM user_phone_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        
        # Записываем изменение в журнал
        try:
            status_text = 'запрещен' if prohibit_issuance else 'разрешен'
            log_query = """
                INSERT INTO phone_numbers_history (operator_id, new_number, note)
                VALUES (%s, %s, %s)
            """
            cursor.execute(log_query, (
                current_user.id,
                number_data['phone_number'],
                f"Статус выдачи изменен на: {status_text}"
            ))
            connection.commit()
        except mysql.connector.Error as log_err:
            # Если ошибка при записи в историю, просто логируем её
            current_app.logger.error("Ошибка при добавлении записи в историю номеров: %s", log_err)
        
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при обновлении статуса выдачи: %s", err)
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/delete_number', methods=['POST'])
@login_required
def delete_number():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    number_id = data.get('number_id')
    
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем данные номера перед удалением для лога
        cursor.execute("SELECT * FROM user_phone_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
        
        # Удаляем номер
        query = "DELETE FROM user_phone_numbers WHERE id = %s"
        cursor.execute(query, (number_id,))
        connection.commit()
        
        # Логируем удаление в phone_numbers_history
        try:
            log_query = """
                INSERT INTO phone_numbers_history (operator_id, old_number, note)
                VALUES (%s, %s, %s)
            """
            cursor.execute(log_query, (
                current_user.id,
                number_data['phone_number'],
                f"Номер удален из системы"
            ))
            connection.commit()
        except mysql.connector.Error as log_err:
            # Если ошибка при записи в историю, просто логируем её
            current_app.logger.error("Ошибка при добавлении записи в историю номеров: %s", log_err)
        
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при удалении номера: %s", err)
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/fire_employee', methods=['POST'])
@login_required
def fire_employee():
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    employee_id = request.form.get('id')
    termination_date = request.form.get('termination_date') or datetime.now().strftime('%Y-%m-%d')
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем текущие данные для логирования изменений
        cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
        old_user_data = cursor.fetchone()
        if not old_user_data:
            return jsonify({"success": False, "error": "Сотрудник не найден"}), 404
        
        # Обновляем дату увольнения
        query = "UPDATE User SET termination_date = %s WHERE id = %s"
        cursor.execute(query, (termination_date, employee_id))
        connection.commit()
        
        # Логируем изменение в UserHistory
        log_query = """
            INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(log_query, (
            employee_id,
            'termination_date',
            old_user_data.get('termination_date', ''),
            termination_date,
            current_user.id,
            datetime.now()
        ))
        connection.commit()
        
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при увольнении сотрудника: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/restore_employee', methods=['POST'])
@login_required
def restore_employee():
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    employee_id = request.form.get('id')
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем текущие данные для логирования изменений
        cursor.execute("SELECT * FROM User WHERE id = %s", (employee_id,))
        old_user_data = cursor.fetchone()
        if not old_user_data:
            return jsonify({"success": False, "error": "Сотрудник не найден"}), 404
        
        # Очищаем дату увольнения
        query = "UPDATE User SET termination_date = NULL WHERE id = %s"
        cursor.execute(query, (employee_id,))
        connection.commit()
        
        # Логируем изменение в UserHistory
        log_query = """
            INSERT INTO UserHistory (user_id, changed_field, old_value, new_value, changed_by, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(log_query, (
            employee_id,
            'termination_date',
            old_user_data.get('termination_date', ''),
            '',
            current_user.id,
            datetime.now()
        ))
        connection.commit()
        
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при восстановлении сотрудника: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/assign_number', methods=['POST'])
@login_required
def assign_number():
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    number_id = data.get('number_id')
    employee_id = data.get('employee_id')
    
    if not number_id:
        return jsonify({'success': False, 'message': 'Не указан ID номера'}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем данные о номере
        cursor.execute("SELECT * FROM user_phone_numbers WHERE id = %s", (number_id,))
        number_data = cursor.fetchone()
        if not number_data:
            return jsonify({'success': False, 'message': 'Номер не найден'}), 404
            
        # Получаем данные о сотруднике, если указан ID сотрудника
        employee_name = None
        if employee_id:
            cursor.execute("SELECT id, full_name FROM User WHERE id = %s", (employee_id,))
            employee = cursor.fetchone()
            if not employee:
                return jsonify({'success': False, 'message': 'Сотрудник не найден'}), 404
            employee_name = employee['full_name']
            
            # Освобождаем текущий корпоративный номер сотрудника, если есть
            cursor.execute("SELECT corp_phone FROM User WHERE id = %s", (employee_id,))
            user_data = cursor.fetchone()
            old_number = user_data.get('corp_phone')
            
            # Если у сотрудника уже есть номер, обновляем историю
            if old_number:
                log_query = """
                    INSERT INTO phone_numbers_history (operator_id, old_number, new_number, changed_at)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(log_query, (
                    employee_id,
                    old_number,
                    number_data['phone_number'],
                    datetime.now()
                ))
                
            # Обновляем корпоративный номер сотрудника
            cursor.execute("UPDATE User SET corp_phone = %s WHERE id = %s", 
                          (number_data['phone_number'], employee_id))
        
        # Обновляем привязку номера
        if employee_id:
            # Назначаем номер сотруднику
            cursor.execute("UPDATE user_phone_numbers SET assigned_operator_id = %s WHERE id = %s", 
                          (employee_id, number_id))
            
            # Добавляем запись в историю
            log_query = """
                INSERT INTO phone_numbers_history (operator_id, new_number, note)
                VALUES (%s, %s, %s)
            """
            cursor.execute(log_query, (
                current_user.id, 
                number_data['phone_number'],
                f"Номер назначен сотруднику {employee_name}"
            ))
        else:
            # Освобождаем номер
            cursor.execute("UPDATE user_phone_numbers SET assigned_operator_id = NULL WHERE id = %s", 
                          (number_id,))
            
            # Добавляем запись в историю
            log_query = """
                INSERT INTO phone_numbers_history (operator_id, new_number, note)
                VALUES (%s, %s, %s)
            """
            cursor.execute(log_query, (
                current_user.id, 
                number_data['phone_number'],
                "Номер освобожден"
            ))
        
        connection.commit()
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при назначении номера: %s", err)
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/get_employees', methods=['GET'])
@login_required
def get_employees():
    # Проверяем, что авторизованный пользователь имеет роль backoffice и отдел "Ресепшн"
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Получаем всех АКТИВНЫХ сотрудников для списка
        query = """
            SELECT id, full_name, department, position
            FROM User 
            WHERE (termination_date IS NULL OR termination_date = '')
            ORDER BY department, position, full_name ASC
        """
        cursor.execute(query)
        employees = cursor.fetchall()
        
        # Группируем сотрудников по отделам
        departments = {}
        for emp in employees:
            dept = emp['department'] or 'Без отдела'
            if dept not in departments:
                departments[dept] = []
            departments[dept].append({
                'id': emp['id'],
                'name': emp['full_name'],
                'position': emp['position']
            })
        
        # Сортируем отделы
        sorted_departments = sorted(departments.keys())
        
        result = []
        for dept in sorted_departments:
            result.append({
                'department': dept,
                'employees': departments[dept]
            })
        
        return jsonify({"success": True, "departments": result})
    except mysql.connector.Error as err:
        current_app.logger.error("Ошибка получения списка сотрудников: %s", err)
        return jsonify({"success": False, "error": str(err)}), 500
    finally:
        cursor.close()
        connection.close()

@admin_bp.route('/add_department', methods=['POST'])
@login_required
def add_department():
    """
    Создает новую запись для отдела в справочнике, чтобы он отображался в выпадающих списках.
    """
    if not (current_user.role == 'backoffice' and current_user.department == "Ресепшн"):
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    department_name = data.get('department_name')
    
    if not department_name:
        return jsonify({'success': False, 'message': 'Название отдела не указано'}), 400
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Проверяем, есть ли уже такой отдел
        cursor.execute("SELECT COUNT(*) as count FROM User WHERE department = %s", (department_name,))
        dept_exists_in_user = cursor.fetchone()['count'] > 0
        
        cursor.execute("SELECT COUNT(*) as count FROM user_phone_numbers WHERE department = %s", (department_name,))
        dept_exists_in_numbers = cursor.fetchone()['count'] > 0
        
        if dept_exists_in_user or dept_exists_in_numbers:
            return jsonify({'success': False, 'message': 'Такой отдел уже существует в системе'}), 400
        
        # Создаем запись нового отдела в таблице Departments (если её нет, создаем запись прямо в телефонных номерах)
        try:
            cursor.execute("INSERT INTO Department (name) VALUES (%s)", (department_name,))
            connection.commit()
            dept_added = True
        except mysql.connector.Error as err:
            # Если таблицы Departments нет, добавляем запись в номера
            dept_added = False
            current_app.logger.warning("Ошибка при добавлении в таблицу Departments: %s", err)
            
        # Если не удалось добавить в таблицу Departments, добавляем пустой номер в таблицу номеров 
        # с указанным отделом, чтобы отдел появился в списках
        if not dept_added:
            cursor.execute("INSERT INTO user_phone_numbers (phone_number, department, prohibit_issuance) VALUES (%s, %s, 1)", 
                          (f"DEPT_{department_name}", department_name))
            connection.commit()
            
        return jsonify({'success': True, 'message': 'Отдел успешно добавлен'})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error("Ошибка при добавлении отдела: %s", err)
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        cursor.close()
        connection.close()
