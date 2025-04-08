from flask import jsonify, render_template, flash, redirect, request, url_for
from flask_login import current_user
from app.utils import create_db_connection, login_required
from .vats_utils import format_phone_number, find_user_by_name, update_telnum_route
from .filter_utils import update_ats_filter
from . import avito_bp

# Пример маршрута для страницы "Авито Про"
@avito_bp.route('/avito_pro/<category>')
@login_required
def avito_category(category):
    if current_user.role != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('auth.login'))
    
    # Проверяем, что категория валидна
    valid_categories = ['Вторички', 'Загородная коммерция', 'HR', 'Резерв', 'Блок', 'Архив']
    if category not in valid_categories:
        flash("Неверная категория.", "danger")
        return redirect(url_for('avito.avito_category', category='Вторички'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    if category == 'Блок':
        query = """
            SELECT AvitoNumbers.*, User.full_name AS employee_full_name 
            FROM AvitoNumbers 
            LEFT JOIN User ON AvitoNumbers.employee_id = User.id 
            WHERE AvitoNumbers.status = 'blocked'
            ORDER BY original_category, account_group
        """
        cursor.execute(query)
    elif category == 'Архив':
        query = """
            SELECT AvitoNumbers.*, User.full_name AS employee_full_name 
            FROM AvitoNumbers 
            LEFT JOIN User ON AvitoNumbers.employee_id = User.id 
            WHERE AvitoNumbers.status = 'archived'
            ORDER BY account_group
        """
        cursor.execute(query)
    else:
        query = """
            SELECT AvitoNumbers.*, User.full_name AS employee_full_name 
            FROM AvitoNumbers 
            LEFT JOIN User ON AvitoNumbers.employee_id = User.id 
            WHERE AvitoNumbers.category = %s 
            AND AvitoNumbers.status = 'active'
            ORDER BY account_group
        """
        cursor.execute(query, (category,))
    
    numbers = cursor.fetchall()
    cursor.close()
    connection.close()

    # Группируем данные по account_group
    grouped_numbers = {}
    for number in numbers:
        group = number['account_group']
        if group not in grouped_numbers:
            grouped_numbers[group] = []
        grouped_numbers[group].append(number)

    return render_template('avito/avito_category.html', grouped_numbers=grouped_numbers, category=category)

# Добавляем маршрут /category/<category> для соответствия ссылкам в шаблонах
@avito_bp.route('/category/<category>')
@login_required
def category(category):
    return avito_category(category)

@avito_bp.route('/avito_pro/add_avito_acc', methods=['POST'])
@login_required
def add_avito_acc():
    if current_user.role != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('auth.login'))

    # Получаем данные из формы
    account_group = request.form.get('account_group')
    sim_number = request.form.get('sim_number')
    email = request.form.get('email')
    password = request.form.get('password')
    category = request.form.get('category')  # Добавляем категорию

    # Проверка на пустые поля
    if not account_group or not sim_number or not email or not password or not category:
        flash("Пожалуйста, заполните все поля.", "danger")
        return redirect(url_for('avito.avito_category', category='Вторички'))  # Возврат на категорию

    # Подключение к базе данных
    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Вставка данных в базу данных
        cursor.execute("""
            INSERT INTO AvitoNumbers (account_group, sim_number, email, password, category, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
        """, (account_group, sim_number, email, password, category))

        # Сохраняем изменения
        connection.commit()
        flash("Номер успешно добавлен!", "success")

    except Exception as e:
        connection.rollback()  # Откатить изменения в случае ошибки
        flash(f"Ошибка при добавлении номера: {e}", "danger")
    finally:
        cursor.close()
        connection.close()

    # Перенаправляем обратно на страницу категории
    return redirect(url_for('avito.avito_category', category=category))


@avito_bp.route('/avito_pro/block_number/<int:number_id>', methods=['POST'])
@login_required
def block_number(number_id):
    if current_user.role != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('auth.login'))

    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # 1. Сначала получаем текущую категорию
        cursor.execute("SELECT category FROM AvitoNumbers WHERE id = %s", (number_id,))
        current_category = cursor.fetchone()[0]

        # 2. Обновляем запись
        cursor.execute("""
            UPDATE AvitoNumbers 
            SET 
                status = 'blocked',
                original_category = %s,
                category = 'Блок'
            WHERE id = %s
        """, (current_category, number_id))
        
        connection.commit()
        flash("Номер успешно заблокирован и перемещен в Блок", "success")

    except Exception as e:
        connection.rollback()
        flash(f"Ошибка при блокировке: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    # Перенаправляем в категорию, откуда был заблокирован номер
    return redirect(url_for('avito.avito_category', category=current_category))


@avito_bp.route('/avito_pro/unblock_number/<int:number_id>', methods=['POST'])
@login_required
def unblock_number(number_id):
    if current_user.role != 'admin':
        flash("Доступ запрещен", "danger")
        return redirect(url_for('auth.login'))

    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Получаем оригинальную категорию
        cursor.execute("SELECT original_category FROM AvitoNumbers WHERE id = %s", (number_id,))
        original_category = cursor.fetchone()[0]

        # Возвращаем в исходную категорию и сбрасываем данные
        cursor.execute("""
            UPDATE AvitoNumbers 
            SET 
                status = 'active',
                category = %s,
                original_category = NULL,
                employee_id = NULL,
                department = NULL
            WHERE id = %s
        """, (original_category, number_id))
        
        connection.commit()
        flash("Номер возвращен в категорию: " + original_category, "success")

    except Exception as e:
        connection.rollback()
        flash(f"Ошибка: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('avito.avito_category', category='Блок'))


@avito_bp.route('/avito_pro/bulk_upload', methods=['POST'])
@login_required
def avito_bulk_upload():
    if current_user.role != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('auth.login'))

    file = request.files.get('file')
    if not file:
        flash("Пожалуйста, выберите файл для загрузки.", "danger")
        return redirect(url_for('avito.avito_category', category='Вторички'))

    # Пример обработки файла (например, CSV)
    connection = create_db_connection()
    cursor = connection.cursor()
    
    # Пример обработки CSV
    import csv
    file_data = csv.reader(file.stream.read().decode("utf-8").splitlines())
    for row in file_data:
        sim_number, account_group, email, password = row
        cursor.execute("INSERT INTO AvitoBulkUpload (sim_number, account_group, email, password) VALUES (%s, %s, %s, %s)",
                       (sim_number, account_group, email, password))
    
    connection.commit()
    cursor.close()
    connection.close()

    flash("Номера успешно загружены.", "success")
    return redirect(url_for('avito.avito_category', category='Вторички'))


@avito_bp.route('/avito_pro/assign_number/<int:number_id>', methods=['POST'])
@login_required
def assign_number(number_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    employee_id = request.json.get('employee_id')
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Обновляем данные номера
        cursor.execute("""
            UPDATE AvitoNumbers 
            SET employee_id = %s,
                department = (SELECT department FROM User WHERE id = %s),
                redirect_status = 'not_set',
                filter_status = 'not_set'
            WHERE id = %s AND status = 'active'
        """, (employee_id, employee_id, number_id))
        
        # Получаем обновленные данные
        cursor.execute("""
            SELECT 
                AvitoNumbers.*, 
                User.full_name AS employee_full_name,
                User.department
            FROM AvitoNumbers
            LEFT JOIN User ON AvitoNumbers.employee_id = User.id
            WHERE AvitoNumbers.id = %s
        """, (number_id,))
        result = cursor.fetchone()
        
        connection.commit()
        return jsonify({
            'success': True,
            'employee_full_name': result['employee_full_name'],
            'department': result['department']
        })
        
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()


@avito_bp.route('/avito_pro/unassign_number/<int:number_id>', methods=['POST'])
@login_required
def unassign_number(number_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE AvitoNumbers
            SET employee_id = NULL,
                department = NULL,
                redirect_status = 'not_set',
                filter_status = 'not_set'
            WHERE id = %s
        """, (number_id,))
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()



@avito_bp.route('/avito_pro/search_employee', methods=['GET'])
@login_required
def search_employee():
    query = request.args.get('query', '')  # Получаем строку для поиска
    if not query:
        return jsonify([])  # Если ничего не введено, возвращаем пустой список

    # Поиск сотрудников в базе данных
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, full_name, department
        FROM User
        WHERE full_name LIKE %s AND is_active = 1 AND fired = 0 
        LIMIT 10
    """, ('%' + query + '%',))
    
    employees = cursor.fetchall()
    cursor.close()
    connection.close()

    return jsonify(employees)


@avito_bp.route('/avito_pro/move_number/<int:number_id>', methods=['POST'])
@login_required
def move_number(number_id):
    if current_user.role != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('auth.login'))

    new_category = request.form.get('new_category')
    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        # Обновляем категорию и сбрасываем сотрудника при перемещении из Резерва
        cursor.execute("""
            UPDATE AvitoNumbers 
            SET category = %s,
                employee_id = CASE WHEN %s = 'Резерв' THEN employee_id ELSE NULL END,
                department = CASE WHEN %s = 'Резерв' THEN department ELSE NULL END
            WHERE id = %s
        """, (new_category, new_category, new_category, number_id))
        
        connection.commit()
        flash(f"Номер успешно перемещен в {new_category}", "success")
    except Exception as e:
        connection.rollback()
        flash(f"Ошибка при перемещении: {str(e)}", "danger")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('avito.avito_category', category=request.form.get('current_category')))


@avito_bp.route('/avito_pro/archive_number/<int:number_id>', methods=['POST'])
@login_required
def archive_number(number_id):
    if current_user.role != 'admin':
        flash("Доступ запрещен", "danger")
        return redirect(url_for('auth.login'))

    print(f"=== Начало обработки архивации номера {number_id} ===")
    connection = create_db_connection()
    
    try:
        # Используем курсор, возвращающий словари
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM AvitoNumbers WHERE id = %s", (number_id,))
        current_data = cursor.fetchone()
        
        if not current_data:
            flash("Номер не найден.", "danger")
            return redirect(url_for('avito.avito_category', category=request.form.get('current_category')))
        
        # Определяем значение original_category: если текущая категория не "Блок", берем текущую, иначе оставляем прежнее значение
        orig_category = current_data['category'] if current_data['category'] != 'Блок' else current_data.get('original_category')
        
        cursor.execute("""
            UPDATE AvitoNumbers 
            SET category = 'Архив',
                status = 'archived',
                original_category = %s
            WHERE id = %s
        """, (orig_category, number_id))
        connection.commit()
        print("Изменения сохранены в БД")
        
        # Дополнительная проверка обновления (при необходимости)
        cursor.execute("SELECT * FROM AvitoNumbers WHERE id = %s", (number_id,))
        updated_data = cursor.fetchone()
        print(f"Данные после обновления: {updated_data}")
        
        flash("Номер перемещен в Архив", "success")
    
    except Exception as e:
        connection.rollback()
        print(f"ОШИБКА: {str(e)}")
        flash(f"Ошибка: {str(e)}", "danger")
    
    finally:
        cursor.close()
        connection.close()
        print("=== Завершение обработки ===")
    
    return redirect(url_for('avito.avito_category', category=request.form.get('current_category')))



@avito_bp.route('/avito_pro/restore_number/<int:number_id>', methods=['POST'])
@login_required
def restore_number(number_id):
    if current_user.role != 'admin':
        flash("Доступ запрещен", "danger")
        return redirect(url_for('auth.login'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    target_category = 'Архив'  # Значение по умолчанию, если что-то пойдет не так
    try:
        # Получаем original_category
        cursor.execute("SELECT original_category FROM AvitoNumbers WHERE id = %s", (number_id,))
        result = cursor.fetchone()
        if not result:
            flash("Номер не найден.", "danger")
            return redirect(url_for('avito.avito_category', category='Архив'))
        
        original_category = result.get('original_category')
        # Если original_category не указана, перемещаем в Резерв
        target_category = original_category if original_category else 'Резерв'
        
        # Восстанавливаем номер: меняем категорию, статус на 'active' и сбрасываем original_category
        cursor.execute("""
            UPDATE AvitoNumbers 
            SET category = %s,
                status = 'active',
                original_category = NULL
            WHERE id = %s
        """, (target_category, number_id))
        connection.commit()
        flash(f"Номер восстановлен в категорию: {target_category}", "success")
    
    except Exception as e:
        connection.rollback()
        flash(f"Ошибка: {str(e)}", "danger")
    
    finally:
        cursor.close()
        connection.close()
    
    # Перенаправляем на страницу целевой категории, чтобы восстановленный номер отобразился
    return redirect(url_for('avito.avito_category', category=target_category))


@avito_bp.route('/avito_pro/setup_redirect/<int:number_id>', methods=['POST'])
@login_required
def setup_redirect(number_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Получаем номер + имя сотрудника
        cursor.execute("""
            SELECT AvitoNumbers.*,
                   User.full_name AS employee_full_name
            FROM AvitoNumbers
            LEFT JOIN User ON AvitoNumbers.employee_id = User.id
            WHERE AvitoNumbers.id = %s
        """, (number_id,))
        avito_number = cursor.fetchone()
        if not avito_number:
            return jsonify({'success': False, 'error': 'Номер не найден'}), 404

        if not avito_number.get('employee_id'):
            return jsonify({'success': False, 'error': 'У номера не назначен сотрудник'}), 400

        employee_name = avito_number.get('employee_full_name') or ''
        if not employee_name:
            return jsonify({'success': False, 'error': 'Не найдено имя сотрудника'}), 400

        # Форматируем сим-карту
        sim = avito_number.get('sim_number', '')
        formatted_phone = format_phone_number(sim)
        if not formatted_phone:
            return jsonify({'success': False, 'error': 'Неверный формат номера SIM'}), 400

        # Ищем сотрудника в ВАТС
        user_info = find_user_by_name(employee_name)
        if not user_info:
            return jsonify({
                'success': False, 
                'error': f"Сотрудник '{employee_name}' не найден в ВАТС"
            }), 404

        user_login = user_info.get('login')
        success, error_msg = update_telnum_route(formatted_phone, user_login)

        if success:
            # Записываем redirect_status = 'ok'
            cursor.execute("""
                UPDATE AvitoNumbers
                SET redirect_status = 'ok'
                WHERE id = %s
            """, (number_id,))
            connection.commit()
            return jsonify({'success': True, 'message': 'Переадресация выполнена успешно.'})
        else:
            # Записываем redirect_status = 'error'
            cursor.execute("""
                UPDATE AvitoNumbers
                SET redirect_status = 'error'
                WHERE id = %s
            """, (number_id,))
            connection.commit()
            return jsonify({'success': False, 'error': error_msg}), 500

    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()


@avito_bp.route('/avito_pro/setup_filter/<int:number_id>', methods=['POST'])
@login_required
def setup_filter(number_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # 1) Ищем нужную запись AvitoNumbers + User
        cursor.execute("""
            SELECT AvitoNumbers.*, User.full_name AS employee_full_name
            FROM AvitoNumbers
            LEFT JOIN User ON AvitoNumbers.employee_id = User.id
            WHERE AvitoNumbers.id = %s
        """, (number_id,))
        avito_number = cursor.fetchone()

        if not avito_number:
            return jsonify({'success': False, 'error': 'Номер не найден'}), 404

        if not avito_number.get('employee_id'):
            return jsonify({'success': False, 'error': 'У номера не назначен сотрудник'}), 400

        employee_name = avito_number.get('employee_full_name') or ''
        if not employee_name:
            return jsonify({'success': False, 'error': 'Не найдено имя сотрудника'}), 400

        # 2) Берём category (например, 'Вторички', 'Загородная коммерция'), department (текст), sim_number
        category = avito_number.get('category', '')
        department = avito_number.get('department', '')
        sim_number = avito_number.get('sim_number', '')

        try:
            update_ats_filter(category, employee_name, department, sim_number)  # Вызов функции фильтрации

            # Если всё ок
            cursor.execute("""
                UPDATE AvitoNumbers
                SET filter_status = 'ok'
                WHERE id = %s
            """, (number_id,))
            connection.commit()

            return jsonify({'success': True, 'message': 'Фильтрация выполнена успешно.'})

        except Exception as e:
            cursor.execute("""
                UPDATE AvitoNumbers
                SET filter_status = 'error'
                WHERE id = %s
            """, (number_id,))
            connection.commit()

            return jsonify({'success': False, 'error': str(e)}), 500

    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        connection.close()