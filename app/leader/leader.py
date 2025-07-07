from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory, abort, current_app
from app.leader import leader_bp
from app.utils import create_db_connection, login_required, get_notifications_count, get_department_weekly_stats
from functools import wraps
from flask_login import login_required as flask_login_required, current_user
from datetime import datetime, timedelta, date
import json
from dateutil.relativedelta import relativedelta

@leader_bp.route('/add_report_by_leader', methods=['POST'])
@login_required
def add_report_by_leader():
    if current_user.role != 'leader':
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    user_id = session.get('id')
    department = session.get('department')

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Получаем настройки видимости полей
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
    result = cursor.fetchone()
    if result and result.get('hidden_fields'):
        hidden_fields = json.loads(result['hidden_fields'])
    else:
        hidden_fields = {}

    # Обязательные и необязательные поля
    mandatory_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls'
    ]

    optional_fields = [
        'adscian', 'adsavito', 'mailouts', 'resales', 'banners',
        'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    # Собираем данные из формы
    data = {}
    for field in mandatory_fields:
        data[field] = request.form.get(field)

    for field in optional_fields:
        if not hidden_fields.get(field, False):
            data[field] = request.form.get(field)
        else:
            data[field] = None  # Поле скрыто, данные не сохраняем

    date = request.form.get('date')

    # Формируем список полей и значений для вставки в БД
    fields = ['user_id', 'date'] + list(data.keys())
    values = [user_id, date] + list(data.values())

    # Создаем строку с плейсхолдерами для запроса
    placeholders = ', '.join(['%s'] * len(values))

    query = f"INSERT INTO Scores ({', '.join(fields)}) VALUES ({placeholders})"

    try:
        cursor.execute(query, values)
        connection.commit()
        return jsonify({'success': True, 'message': 'Отчет успешно добавлен'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()



@leader_bp.route('/api/mark_notifications_read', methods=['POST'])
@login_required
def mark_notifications_read():
    user_id = session.get('id')
    if not user_id:
        return jsonify(success=False, message="User ID not found in session"), 400

    connection = create_db_connection()
    cursor = connection.cursor()
    query = f"""
    UPDATE UserNotifications
    SET is_read = TRUE
    WHERE user_id = %s AND is_read = FALSE
    """
    cursor.execute(query, (user_id,))
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify(success=True)


@leader_bp.route('/api/get_notifications')
@login_required
def api_get_notifications():
    user_id = session.get('id')
    user_role = session.get('role')
    if not user_id or not user_role:
        return jsonify([]), 403

    print(f"Fetching notifications for user_id: {user_id} with role: {user_role}")
    notifications = get_notifications_by_user_and_role(user_id, user_role)
    return jsonify([{'message': n['message'], 'is_read': n['is_read']} for n in notifications])

def get_notifications_by_user_and_role(user_id, role):
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    query = f"""
    SELECT n.message, un.is_read
    FROM Notifications n
    JOIN UserNotifications un ON n.id = un.notification_id
    WHERE un.user_id = %s AND n.is_for_{role} = TRUE
    ORDER BY n.created_at DESC
    """
    print(f"Executing query: {query}")
    cursor.execute(query, (user_id,))
    notifications = cursor.fetchall()
    print(f"Notifications fetched: {notifications}")
    cursor.close()
    connection.close()

    return notifications


@leader_bp.route('/impersonate/<int:user_id>', methods=['GET'])
@login_required
def impersonate_user(user_id):
    # Проверяем, является ли текущий пользователь лидером или администратором
    if current_user.role not in ['leader', 'admin']:
        flash("У вас нет прав на выполнение этого действия.", "danger")
        return redirect(url_for('leader.leader_dashboard'))

    # Сохраняем данные текущего пользователя (руководителя), если это первый раз
    if 'original_user_id' not in session:
        session['original_user_id'] = session.get('id')
        session['original_user_full_name'] = session.get('full_name', 'Пользователь')
        session['original_role'] = session.get('role')
        session['original_department'] = session.get('department')

    # Подключаемся к базе данных
    connection = create_db_connection()
    if connection is None:
        flash("Не удалось подключиться к базе данных.", "danger")
        return redirect(url_for('leader.leader_dashboard'))

    try:
        cursor = connection.cursor(dictionary=True)

        # Получаем данные о пользователе, которого хотим имперсонировать
        cursor.execute("SELECT * FROM User WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()

        if not user_data:
            flash("Пользователь не найден.", "danger")
            return redirect(url_for('leader.leader_dashboard'))

        # Обновляем данные сессии для имперсонированного пользователя
        session['id'] = user_data['id']
        session['full_name'] = user_data['full_name']
        session['role'] = user_data['role']
        session['department'] = user_data['department']

        # Добавляем лог для отладки
        print("Сессия после имперсонации:", session)

        flash(f"Вы сейчас действуете от имени {user_data['full_name']}.", "success")

        # Проверяем роль нового пользователя и перенаправляем
        if user_data['role'] == 'user':
            return redirect(url_for('main.dashboard'))  # Перенаправляем на маршрут пользователя
        elif user_data['role'] == 'leader':
            return redirect(url_for('leader.leader_dashboard'))  # Перенаправляем на маршрут руководителя
        else:
            flash("Роль пользователя не поддерживается.", "danger")
            return redirect(url_for('leader.leader_dashboard'))

    except Exception as e:
        flash(f"Произошла ошибка: {e}", "danger")
        return redirect(url_for('leader.leader_dashboard'))
    finally:
        cursor.close()
        connection.close()


@leader_bp.route('/revert_impersonation')
@login_required
def revert_impersonation():
    print("Запуск revert_impersonation")
    if 'original_user_id' in session:
        original_user_id = session.pop('original_user_id')
        print("ID оригинального пользователя:", original_user_id)

        # Получаем данные оригинального пользователя
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM User WHERE id = %s", (original_user_id,))
            original_user_data = cursor.fetchone()

            if not original_user_data:
                print("Не удалось найти оригинального пользователя с ID:", original_user_id)
                flash("Не удалось восстановить данные оригинального пользователя.", "danger")
                return redirect(url_for('leader.leader_dashboard'))

            print("Получены данные оригинального пользователя:", original_user_data)

            # Восстанавливаем данные в сессии
            session['id'] = original_user_data['id']
            session['role'] = original_user_data['role']
            session['full_name'] = original_user_data['full_name']
            session['department'] = original_user_data['department']
            print("Сессия восстановлена для оригинального пользователя:", session)

            flash("Вы вернулись к своему профилю.", "success")
        except Exception as e:
            print("Ошибка при восстановлении пользователя:", e)
            flash(f"Произошла ошибка: {e}", "danger")
        finally:
            cursor.close()
            connection.close()
            print("Соединение с базой данных закрыто.")
    else:
        print("Не найден оригинальный пользователь в сессии.")
        flash("Вы не в режиме имперсонации.", "danger")

    return redirect(url_for('leader.leader_dashboard'))



@leader_bp.route('/return_to_leader')
@login_required
def return_to_leader():
    if 'original_user_id' in session:
        # Восстановление ID и данных оригинального пользователя (руководителя)
        user_id = session['original_user_id']
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM User WHERE id = %s", (user_id,))
        original_user = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if original_user:
            session['id'] = user_id
            session['username'] = original_user['login']
            session['role'] = original_user['role']
            session['full_name'] = original_user['full_name']
            session['department'] = original_user['department']
            
            # Очищаем временные значения в сессии
            session.pop('original_user_id', None)
            session.pop('original_user_full_name', None)
            
            flash('Вы вернулись к своему профилю.', 'success')
        else:
            flash("Оригинальный пользователь не найден.", "danger")
            return redirect(url_for('auth.login'))
    else:
        flash("Вы не находитесь в режиме имперсонации.", "danger")
    
    return redirect(url_for('leader.leader_dashboard'))

@leader_bp.route('/leader/dashboard', methods=['GET', 'POST'])
@login_required
def leader_dashboard():
    # Проверка роли пользователя
    if current_user.role != 'leader':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    # Получение информации об отделе и ID пользователя из сессии
    department = session.get('department')
    user_id = session.get('id')

    # Проверка наличия department и user_id в сессии
    if not user_id or not department:
        flash("Не удалось загрузить данные пользователя. Пожалуйста, попробуйте войти снова.", "danger")
        return redirect(url_for('auth.login'))

    # Подключение к базе данных
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Получение информации о руководителе
        cursor.execute("SELECT full_name, department FROM User WHERE id = %s", (user_id,))
        leader_info = cursor.fetchone()

        # Если информация о руководителе не найдена
        if not leader_info:
            flash("Информация о руководителе не найдена.", "danger")
            return redirect(url_for('auth.login'))

        # Получение статистики по отделу за последние 7 дней
        weekly_stats = get_department_weekly_stats(department)

        # Получение количества уведомлений
        notifications_count = get_notifications_count()

        # Получаем настройки видимости полей
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
        result = cursor.fetchone()
        
        # Обработка данных скрытых полей
        hidden_fields_data = result.get('hidden_fields') if result else None
        field_settings = json.loads(hidden_fields_data) if hidden_fields_data else {}

        # Обязательные поля
        mandatory_fields = [
            'deals',            # Сделки
            'reservations',     # Брони
            'online_showings',  # Показы онлайн
            'offline_showings', # Показы офлайн
            'repeat_showings',  # Повторные показы
            'new_clients',      # Новый клиент
            'cold_calls'        # Холодные звонки
        ]

        # Все возможные поля
        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        # Необязательные поля
        optional_fields = [field for field in all_fields if field not in mandatory_fields]

        # Названия полей для отображения
        field_names = {
            'deals': 'Сделки',
            'reservations': 'Брони',
            'online_showings': 'Показы онлайн',
            'offline_showings': 'Показы офлайн',
            'repeat_showings': 'Повторные показы',
            'new_clients': 'Новый клиент',
            'cold_calls': 'Холодные звонки',
            'adscian': 'Реклама Циан',
            'adsavito': 'Реклама Авито',
            'mailouts': 'Рассылки',
            'resales': 'Вторички',
            'banners': 'Баннеры',
            'results': 'Сработки',
            'exclusives': 'Эксклюзивы',
            'stories': 'Сторис',
            'total_ads_avito': 'Реклама Авито (общ.)',
            'total_ads_cian': 'Реклама Циан (общ.)',
            'incoming_cold_calls': 'Входящие',
            'stationary_calls': 'Стационар (737)',
        }

    except mysql.connector.Error as err:
        current_app.logger.error(f"Ошибка при загрузке данных для дашборда руководителя: {err}")
        flash("Ошибка загрузки данных. Пожалуйста, попробуйте позже.", "danger")
        return redirect(url_for('auth.login'))
    
    finally:
        # Закрытие соединения с базой данных
        cursor.close()
        connection.close()

    # Отправка данных в шаблон
    return render_template(
        'leader_dashboard.html',
        leader_info=leader_info,
        weekly_stats=weekly_stats,
        notifications_count=notifications_count,
        field_settings=field_settings,
        mandatory_fields=mandatory_fields,
        optional_fields=optional_fields,
        field_names=field_names
    )


def get_department_statistics(department_id, start_date, end_date):
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get hidden fields settings
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department_id,))
    result = cursor.fetchone()
    if result and result.get('hidden_fields'):
        hidden_fields = json.loads(result['hidden_fields'])
    else:
        hidden_fields = {}

    # Define all possible fields
    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    # Determine which fields to display based on hidden fields
    fields_to_display = [field for field in all_fields if not hidden_fields.get(field, False)]

    # Build SQL query dynamically based on fields_to_display
    fields_sql = ", ".join([f"SUM(Scores.{field}) AS {field}" for field in fields_to_display])

    query = f"""
    SELECT User.full_name,
           {fields_sql}
    FROM Scores
    JOIN User ON Scores.user_id = User.id
    WHERE User.department = %s AND Scores.date >= %s AND Scores.date <= %s
    GROUP BY User.id
    ORDER BY User.full_name ASC
    """
    cursor.execute(query, (department_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    scores = cursor.fetchall()

    cursor.close()
    connection.close()

    # Render the table rows using a separate template
    table_rows = render_template('department_statistics_table_rows.html',
                                 scores=scores,
                                 fields_to_display=fields_to_display)

    return jsonify({'table_rows': table_rows})


@leader_bp.route('/leader/department_users')
@login_required
def show_department_users():
    if current_user.role != 'leader':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('auth.login'))

    department = session.get('department')

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT id, login, full_name
    FROM User
    WHERE department = %s AND fired = FALSE AND role = 'user'
    """

    cursor.execute(query, (department,))
    users = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('department_users.html', users=users)

@leader_bp.route('/department_statistics/daily', methods=['POST'])
@login_required
def department_daily_statistics():
    if session.get('role') != 'leader':
        return jsonify({'error': 'Доступ запрещен'}), 403
    selected_date = request.form.get('selected_date')
    department_id = session.get('department')
    start_date = datetime.strptime(selected_date, '%Y-%m-%d')
    end_date = start_date
    return get_department_statistics(department_id, start_date, end_date)

@leader_bp.route('/department_statistics/weekly', methods=['POST'])
@login_required
def department_weekly_statistics():
    if session.get('role') != 'leader':
        return jsonify({'error': 'Доступ запрещен'}), 403
    department_id = session.get('department')
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday() + 7)  # Начало прошлой недели (понедельник)
    end_of_week = start_of_week + timedelta(days=6)  # Конец прошлой недели (воскресенье)
    start_date = start_of_week
    end_date = end_of_week
    return get_department_statistics(department_id, start_date, end_date)

@leader_bp.route('/department_statistics/monthly', methods=['POST'])
@login_required
def department_monthly_statistics():
    if session.get('role') != 'leader':
        return jsonify({'error': 'Доступ запрещен'}), 403
    department_id = session.get('department')
    selected_month = request.form.get('selected_month')  # Format 'YYYY-MM'
    try:
        year, month = map(int, selected_month.split('-'))
    except ValueError:
        return jsonify({'error': 'Некорректный формат месяца.'}), 400
    start_date = datetime(year, month, 1)
    end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
    return get_department_statistics(department_id, start_date, end_date)

@leader_bp.route('/department_statistics/yearly', methods=['POST'])
@login_required
def department_yearly_statistics():
    if session.get('role') != 'leader':
        return jsonify({'error': 'Доступ запрещен'}), 403
    department_id = session.get('department')
    selected_year = request.form.get('selected_year')
    try:
        year = int(selected_year)
    except ValueError:
        return jsonify({'error': 'Некорректный формат года.'}), 400
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    return get_department_statistics(department_id, start_date, end_date)


@leader_bp.route('/department_statistics/custom', methods=['POST'])
@login_required
def department_custom_statistics():
    if session.get('role') != 'leader':
        return jsonify({'error': 'Доступ запрещен'}), 403
    department_id = session.get('department')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Некорректный формат дат.'}), 400
    return get_department_statistics(department_id, start_date, end_date)

def get_department_statistics(department_id, start_date, end_date):
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Получаем настройки скрытых полей
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department_id,))
    result = cursor.fetchone()
    if result and result.get('hidden_fields'):
        hidden_fields = json.loads(result['hidden_fields'])
    else:
        hidden_fields = {}

    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    fields_to_display = [field for field in all_fields if not hidden_fields.get(field, False)]

    # Определяем названия полей для отображения
    field_names = {
        'deals': 'Сделки',
        'reservations': 'Брони',
        'online_showings': 'Показы онлайн',
        'offline_showings': 'Показы офлайн',
        'repeat_showings': 'Повторные показы',
        'new_clients': 'Новый клиент',
        'cold_calls': 'Холодные звонки',
        'adscian': 'Реклама Циан',
        'adsavito': 'Реклама Авито',
        'mailouts': 'Рассылки',
        'resales': 'Вторички',
        'banners': 'Баннеры',
        'results': 'Сработки',
        'exclusives': 'Эксклюзивы',
        'stories': 'Сторис',
        'total_ads_avito': 'Реклама Авито (общ.)',
        'total_ads_cian': 'Реклама Циан (общ.)',
        'incoming_cold_calls': 'Входящие',
        'stationary_calls': 'Стационар (737)',
    }

    # Разделяем поля на суммируемые и поля с последним значением
    sum_fields = [field for field in fields_to_display if field not in ['total_ads_avito', 'total_ads_cian']]
    last_fields = [field for field in ['total_ads_avito', 'total_ads_cian'] if field in fields_to_display]

    # Строим SQL-запрос динамически на основе отображаемых полей
    sum_fields_sql = ", ".join([f"SUM(Scores.{field}) AS {field}" for field in sum_fields])
    last_fields_sql = ", ".join([f"MAX(Scores.{field}) AS {field}" for field in last_fields])

    # Объединяем все поля
    all_fields_sql = ", ".join(filter(None, [sum_fields_sql, last_fields_sql]))

    query = f"""
    SELECT User.full_name,
           {all_fields_sql}
    FROM Scores
    JOIN User ON Scores.user_id = User.id
    WHERE User.department = %s AND Scores.date >= %s AND Scores.date <= %s
    GROUP BY User.id, User.full_name
    ORDER BY User.full_name ASC
    """
    cursor.execute(query, (department_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    scores = cursor.fetchall()

    cursor.close()
    connection.close()

    # Рендерим строки таблицы с помощью отдельного шаблона
    table_rows = render_template('department_statistics_table_rows.html',
                                 scores=scores,
                                 sum_fields=sum_fields,
                                 last_fields=last_fields,
                                 field_names=field_names)

    return jsonify({'table_rows': table_rows})


@leader_bp.route('/manage_fields', methods=['POST'])
@login_required
def manage_fields():
    if current_user.role != 'leader':
        flash('Доступно только для руководителей.', 'danger')
        return redirect(url_for('main.dashboard'))

    department = session.get('department')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Получаем текущие настройки скрытых полей
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
    result = cursor.fetchone()
    if result:
        hidden_fields = json.loads(result.get('hidden_fields', '{}'))
    else:
        hidden_fields = {}

    # Все необязательные поля
    optional_fields = [
        'adscian', 'adsavito', 'mailouts', 'resales', 'banners',
        'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    # Обновляем настройки на основе данных из формы
    for field in optional_fields:
        hidden_fields[field] = not bool(request.form.get(field))

    # Обновляем запись в базе данных
    if result:
        cursor.execute("""
            UPDATE DepartmentSettings SET hidden_fields = %s WHERE department = %s
        """, (json.dumps(hidden_fields), department))
    else:
        cursor.execute("""
            INSERT INTO DepartmentSettings (department, hidden_fields) VALUES (%s, %s)
        """, (department, json.dumps(hidden_fields)))

    connection.commit()
    cursor.close()
    connection.close()

    flash('Настройки видимости полей обновлены.', 'success')
    return redirect(url_for('leader.leader_dashboard'))

@leader_bp.route('/leader/department_statistics', methods=['GET'])
@login_required
def department_statistics():
    if current_user.role != 'leader':
        flash('Доступно только для руководителей.', 'danger')
        return redirect(url_for('main.dashboard'))

    department_id = session.get('department')

    # Получаем настройки видимости полей для отдела
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department_id,))
    result = cursor.fetchone()
    if result and result.get('hidden_fields'):
        hidden_fields = json.loads(result['hidden_fields'])
    else:
        hidden_fields = {}

    # Определяем обязательные и необязательные поля
    mandatory_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls'
    ]

    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    # Фильтруем поля на основе настроек видимости
    fields_to_display = [field for field in all_fields if not hidden_fields.get(field, False)]

    field_names = {
        'deals': 'Сделки',
        'reservations': 'Брони',
        'online_showings': 'Показы онлайн',
        'offline_showings': 'Показы офлайн',
        'repeat_showings': 'Повторные показы',
        'new_clients': 'Новый клиент',
        'cold_calls': 'Холодные звонки',
        'adscian': 'Реклама Циан',
        'adsavito': 'Реклама Авито',
        'mailouts': 'Рассылки',
        'resales': 'Вторички',
        'banners': 'Баннеры',
        'results': 'Сработки',
        'exclusives': 'Эксклюзивы',
        'stories': 'Сторис',
        'total_ads_avito': 'Реклама Авито (общ.)',
        'total_ads_cian': 'Реклама Циан (общ.)',
        'incoming_cold_calls': 'Входящие',
        'stationary_calls': 'Стационар (737)',
    }

    # Получаем количество уведомлений
    notifications_count = get_notifications_count()

    cursor.close()
    connection.close()

    return render_template('department_statistics.html',
                           field_names=field_names,
                           fields_to_display=fields_to_display,
                           notifications_count=notifications_count)


@leader_bp.route('/leader/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user_by_leader(id):
    if current_user.role != 'leader':
        flash('Только руководители могут редактировать данные пользователей.', 'danger')
        return redirect(url_for('leader.leader_dashboard'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        # Получаем данные из формы
        login = request.form['login']
        full_name = request.form['full_name']
        password = request.form.get('password')  # Может быть None, если пароль не обновляется

        try:
            # Если пароль обновляется, его нужно сначала захешировать
            if password:
                hashed_password = generate_password_hash(password)
                update_query = "UPDATE User SET login = %s, full_name = %s, password = %s WHERE id = %s AND department = %s"
                cursor.execute(update_query, (login, full_name, hashed_password, id, session['department']))
            else:
                # Если пароль не обновляется, меняем только логин и полное имя
                update_query = "UPDATE User SET login = %s, full_name = %s WHERE id = %s AND department = %s"
                cursor.execute(update_query, (login, full_name, id, session['department']))

            connection.commit()
            flash('Данные пользователя успешно обновлены', 'success')
        except mysql.connector.Error as err:
            flash(f'Ошибка при обновлении данных пользователя: {err}', 'danger')
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('leader_dashboard'))

    # За пределами POST запроса, получаем текущие данные пользователя для редактирования
    cursor.execute("SELECT login, full_name FROM User WHERE id = %s AND department = %s", (id, session['department']))
    user = cursor.fetchone()
    cursor.close()
    connection.close()

    if user:
        # Если пользователь найден, отправляем его данные в шаблон
        return render_template('edit_user_by_leader.html', user=user, user_id=id)
    else:
        # Если пользователь не найден, выводим сообщение об ошибке
        flash('Пользователь не найден или вы не имеете права на его редактирование.', 'danger')
        return redirect(url_for('leader.leader_dashboard'))

@leader_bp.route('/leader/add_user', methods=['GET', 'POST'])
def add_user_by_leader():
    if current_user.role != 'leader':
        flash('Только руководители могут добавлять пользователей.', 'danger')
        return redirect(url_for('leader_dashboard'))
        department_id = session.get('department')

    if request.method == 'POST':
        login = request.form['login']
        full_name = request.form['full_name']
        password = request.form['password']
        department = session.get('department')  # Отдел руководителя
        hashed_password = generate_password_hash(password)
        role = 'user'  # Назначаем роль автоматически

        connection = create_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO User (login, full_name, password, role, department) VALUES (%s, %s, %s, %s, %s)", 
                           (login, full_name, hashed_password, role, department))
            id = cursor.lastrowid  # Получаем ID только что добавленного пользователя
            connection.commit()
            flash('Пользователь успешно добавлен. User ID: ' + str(id), 'success')
        except mysql.connector.Error as err:
            flash(f'Ошибка при добавлении пользователя: {err}', 'danger')
        finally:
            cursor.close()
            connection.close()

        return redirect(url_for('show_department_users'))

    return render_template('add_user_by_leader.html')

@leader_bp.route('/leader/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user_by_leader(id):
    if current_user.role != 'leader':
        flash('Только руководители могут удалять пользователей.', 'danger')
        return redirect(url_for('leader.leader_dashboard'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT department FROM User WHERE id = %s", (id,))
        user_department = cursor.fetchone()
        print("User Department:", user_department)  # Отладка

        if user_department and user_department['department'] == session['department']:
            cursor.execute("DELETE FROM User WHERE id = %s", (id,))
            connection.commit()
            print("User deleted successfully.")  # Отладка
            flash('Пользователь успешно удален.', 'success')
        else:
            print("User not found or does not belong to the leader's department.")  # Отладка
            flash('Невозможно удалить пользователя. Пользователь не найден или не принадлежит к вашему отделу.', 'danger')
    except mysql.connector.Error as err:
        flash(f'Ошибка при удалении пользователя: {err}', 'danger')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('show_department_users'))

@leader_bp.route('/leader/change_password/<int:user_id>', methods=['GET', 'POST'])
@login_required
def change_password_by_leader(user_id):
    if current_user.role != 'leader':
        flash('Доступно только для руководителей.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash('Пароли не совпадают.', 'danger')
            return render_template('change_password_by_leader.html', user_id=user_id)

        # Обновляем пароль пользователя
        hashed_password = generate_password_hash(new_password)
        try:
            connection = create_db_connection()
            cursor = connection.cursor()
            cursor.execute("UPDATE User SET password = %s WHERE id = %s", (hashed_password, user_id))
            connection.commit()
            flash('Пароль успешно изменен.', 'success')
        except Exception as e:
            flash(f'Произошла ошибка: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
        
        return redirect(url_for('leader.leader_dashboard'))
    else:
        return render_template('change_password_by_leader.html', user_id=user_id)

