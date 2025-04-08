from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, abort, current_app, session
from app.utils import create_db_connection, login_required, get_user_department, get_department_weekly_stats, get_notifications_count, login_required
from werkzeug.utils import secure_filename
from functools import wraps
import os
from app.extensions import socketio
import mysql.connector
from datetime import datetime, timedelta, date
from . import userlist_bp
from flask_login import login_required as flask_login_required, current_user
import json
from dateutil.relativedelta import relativedelta


@userlist_bp.route('/my_statistics')
@login_required
def my_statistics():
    user_id = session.get('id')
    print(f"Debug: user_id = {user_id}")  # Отладочное сообщение

    if not user_id:
        print("Debug: user_id is None or not set")
        return "Пользователь не найден", 404

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Получаем отдел пользователя
    cursor.execute("SELECT department FROM User WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    print(f"Debug: result = {result}")  # Отладочное сообщение
    if not result:
        cursor.close()
        connection.close()
        return "Пользователь не найден", 404
    department_id = result['department']

    # Получаем настройки скрытых полей от руководителя
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department_id,))
    result = cursor.fetchone()
    if result and result.get('hidden_fields'):
        hidden_fields = json.loads(result['hidden_fields'])
    else:
        hidden_fields = {}

    # Определяем все возможные поля
    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    # Определяем обязательные поля
    mandatory_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls'
    ]

    # Определяем необязательные поля
    optional_fields = [field for field in all_fields if field not in mandatory_fields]

    # Определяем, какие поля отображать на основе скрытых полей
    fields_to_display = [field for field in all_fields if not hidden_fields.get(field, False)]

    # Имена полей для отображения в заголовках таблицы
    field_names = {
        'deals': 'Сделки',
        'reservations': 'Брони',
        'online_showings': 'Показы онлайн',
        'offline_showings': 'Показы офлайн',
        'repeat_showings': 'Повторные показы',
        'new_clients': 'Новые клиенты',
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
        'incoming_cold_calls': 'Входящие звонки',
        'stationary_calls': 'Стационар (737)',
    }

    cursor.close()
    connection.close()

    return render_template('my_statistics.html',
                           fields_to_display=fields_to_display,
                           field_names=field_names,
                           mandatory_fields=mandatory_fields,
                           optional_fields=optional_fields,
                           hidden_fields=hidden_fields)


def get_user_stats(user_id):
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Список всех полей, которые вы хотите получить из таблицы Scores
    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls', 'adscian', 'adsavito',
        'mailouts', 'resales', 'banners', 'results', 'exclusives', 'stories',
        'total_ads_avito', 'total_ads_cian', 'incoming_cold_calls', 'stationary_calls'
    ]
    
    # Формируем часть SQL-запроса с полями
    fields_sql = ", ".join([f"SUM({field}) as {field}" for field in all_fields])
    
    query = f"""
    SELECT {fields_sql}
    FROM Scores
    WHERE user_id = %s
    """
    
    cursor.execute(query, (user_id,))
    stats = cursor.fetchone()
    
    cursor.close()
    connection.close()
    
    return stats

@userlist_bp.route('/my_statistics/daily', methods=['POST'])
@login_required
def my_daily_statistics():
    user_id = session.get('id')
    selected_date = request.form.get('selected_date')

    if not selected_date:
        return jsonify({'error': 'Дата не указана'}), 400

    try:
        start_date = datetime.strptime(selected_date, '%Y-%m-%d')
        end_date = start_date
    except ValueError:
        return jsonify({'error': 'Некорректный формат даты'}), 400

    return get_user_statistics(user_id, start_date, end_date)

@userlist_bp.route('/my_statistics/weekly', methods=['POST'])
@login_required
def my_weekly_statistics():
    user_id = session.get('id')

    # Получаем текущую дату и вычисляем диапазон прошлой недели
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday() + 7)  # Начало прошлой недели (понедельник)
    end_of_week = start_of_week + timedelta(days=6)  # Конец прошлой недели (воскресенье)

    start_date = start_of_week
    end_date = end_of_week

    return get_user_statistics(user_id, start_date, end_date)

@userlist_bp.route('/my_statistics/monthly', methods=['POST'])
@login_required
def my_monthly_statistics():
    user_id = session.get('id')
    selected_month = request.form.get('selected_month')  # Формат 'YYYY-MM'

    if not selected_month:
        return jsonify({'error': 'Месяц не указан'}), 400

    try:
        year, month = map(int, selected_month.split('-'))
        start_date = datetime(year, month, 1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
    except ValueError:
        return jsonify({'error': 'Некорректный формат месяца'}), 400

    return get_user_statistics(user_id, start_date, end_date)

@userlist_bp.route('/my_statistics/yearly', methods=['POST'])
@login_required
def my_yearly_statistics():
    user_id = session.get('id')
    selected_year = request.form.get('selected_year')

    if not selected_year:
        return jsonify({'error': 'Год не указан'}), 400

    try:
        year = int(selected_year)
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
    except ValueError:
        return jsonify({'error': 'Некорректный формат года'}), 400

    return get_user_statistics(user_id, start_date, end_date)

@userlist_bp.route('/my_statistics/custom', methods=['POST'])
@login_required
def my_custom_statistics():
    user_id = session.get('id')
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify({'error': 'Начальная и конечная даты должны быть указаны'}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Некорректный формат дат'}), 400

    return get_user_statistics(user_id, start_date, end_date)

def get_user_statistics(user_id, start_date, end_date):
    print(f"Получение статистики для user_id: {user_id} с {start_date} по {end_date}")

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Получаем ID отдела пользователя
    cursor.execute("SELECT department FROM User WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    if not result:
        print("Пользователь не найден в таблице User")
        cursor.close()
        connection.close()
        return jsonify({'error': 'Пользователь не найден'}), 404
    department_id = result['department']
    print(f"ID отдела пользователя: {department_id}")

    # Получаем настройки скрытых полей от руководителя
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department_id,))
    result = cursor.fetchone()
    if result and result.get('hidden_fields'):
        hidden_fields = json.loads(result['hidden_fields'])
        print(f"Скрытые поля из настроек отдела: {hidden_fields}")
    else:
        hidden_fields = {}
        print("Скрытых полей нет или они не заданы")

    # Определяем все возможные поля
    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    # Определяем, какие поля отображать на основе скрытых полей
    fields_to_display = [field for field in all_fields if not hidden_fields.get(field, False)]
    print(f"Поля для отображения: {fields_to_display}")

    # Проверяем, есть ли поля для отображения
    if not fields_to_display:
        print("Нет полей для отображения после применения скрытых полей")
        cursor.close()
        connection.close()
        return jsonify({'error': 'Нет доступных данных для отображения'}), 404

    # Определяем отображаемые названия полей
    field_names = {
        'deals': 'Сделки',
        'reservations': 'Брони',
        'online_showings': 'Показы онлайн',
        'offline_showings': 'Показы офлайн',
        'repeat_showings': 'Повторные показы',
        'new_clients': 'Новые клиенты',
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
        'incoming_cold_calls': 'Входящие звонки',
        'stationary_calls': 'Стационар (737)',
    }

    # Динамически строим SQL-запрос на основе fields_to_display
    fields_sql = ", ".join([f"SUM(Scores.{field}) AS {field}" for field in fields_to_display])

    query = f"""
    SELECT Scores.date,
           {fields_sql}
    FROM Scores
    WHERE Scores.user_id = %s AND Scores.date >= %s AND Scores.date <= %s
    GROUP BY Scores.date
    ORDER BY Scores.date ASC
    """
    print(f"Выполняемый SQL-запрос:\n{query}")
    print(f"Параметры запроса: user_id={user_id}, start_date={start_date.strftime('%Y-%m-%d')}, end_date={end_date.strftime('%Y-%m-%d')}")

    try:
        cursor.execute(query, (user_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        scores = cursor.fetchall()
        print(f"Полученные данные scores: {scores}")
    except Exception as e:
        print(f"Ошибка при выполнении запроса: {e}")
        cursor.close()
        connection.close()
        return jsonify({'error': 'Ошибка при получении данных'}), 500

    cursor.close()
    connection.close()

    # Проверяем, получили ли мы какие-либо данные
    if not scores:
        print("Запрос выполнен успешно, но данных нет")
        return jsonify({'error': 'Данные не найдены за указанный период'}), 404

    # Рендерим строки таблицы с помощью отдельного шаблона
    try:
        table_rows = render_template('user_statistics_table_rows.html',
                                     scores=scores,
                                     fields_to_display=fields_to_display,
                                     field_names=field_names)
        print(f"Сгенерированные строки таблицы:\n{table_rows}")
    except Exception as e:
        print(f"Ошибка при рендеринге шаблона: {e}")
        return jsonify({'error': 'Ошибка при отображении данных'}), 500

    return jsonify({'table_rows': table_rows})


@userlist_bp.route('/logout')
@login_required
def logout():
    user_id = session.get('id')
    if user_id:
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("UPDATE User SET status = 'Офлайн', last_active = NULL WHERE id = %s", (user_id,))
        connection.commit()
        cursor.close()
        connection.close()
    
    session.clear()
    flash('Вы вышли из системы.', 'success')
    return redirect(url_for('auth.login'))


def fill_missing_days(scores):
    if not scores:
        return []

    # Создаем список всех дней за последние 7 дней
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    all_dates = [start_date + timedelta(days=i) for i in range(7)]

    # Преобразуем даты в формат YYYY-MM-DD
    all_dates_str = [date.strftime('%Y-%m-%d') for date in all_dates]

    # Создаем словарь, где ключи - даты, значения - отчеты за соответствующий день
    scores_dict = {score['date']: score for score in scores}

    filled_scores = []
    for date in all_dates_str:
        # Если есть отчет за текущий день, добавляем его в новый список
        if date in scores_dict:
            filled_scores.append(scores_dict[date])
        # Если отчета за текущий день нет, используем предыдущий отчет
        else:
            if filled_scores:
                # Копируем данные предыдущего дня
                previous_day_score = filled_scores[-1].copy()
                # Заменяем дату на текущий день
                previous_day_score['date'] = date
                filled_scores.append(previous_day_score)

    return filled_scores


@userlist_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if session.get('role') != 'user':
        flash('У вас нет доступа к этой странице', 'danger')
        return redirect(url_for('auth.login'))

    # Добавляем логи для отладки
    print("Сессия пользователя:", session)

    user_id = session.get('id')
    department = session.get('department')

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Получаем настройки видимости полей для отдела пользователя
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
    result = cursor.fetchone()
    hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}
    print(f"Скрытые поля для отдела {department}: {hidden_fields}")

    # Определяем все возможные поля
    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls', 'adscian', 'adsavito',
        'mailouts', 'resales', 'banners', 'results', 'exclusives', 'stories',
        'total_ads_avito', 'total_ads_cian', 'incoming_cold_calls', 'stationary_calls'
    ]

    # Определяем обязательные поля
    mandatory_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls'
    ]

    # Определяем необязательные поля
    optional_fields = [field for field in all_fields if field not in mandatory_fields]

    # Определяем, какие поля отображать на основе скрытых полей
    fields_to_display = [field for field in all_fields if not hidden_fields.get(field, False)]
    print(f"Поля для отображения: {fields_to_display}")

    # Имена полей для отображения в заголовках таблицы
    field_names = {
        'deals': 'Сделки',
        'reservations': 'Брони',
        'online_showings': 'Показы онлайн',
        'offline_showings': 'Показы офлайн',
        'repeat_showings': 'Повторные показы',
        'new_clients': 'Новые клиенты',
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
        'incoming_cold_calls': 'Входящие звонки',
        'stationary_calls': 'Стационар (737)',
    }

    # Получаем количество уведомлений
    try:
        notifications_count = get_notifications_count(user_id)
        print(f"Количество уведомлений: {notifications_count}")
    except Exception as e:
        print(f"Ошибка при получении количества уведомлений: {e}")
        notifications_count = 0

    # Закрываем соединение
    cursor.close()
    connection.close()

    # Получаем статистику по отделу за последние 7 дней
    weekly_stats = get_department_weekly_stats(department)
    if weekly_stats:
        print(f"Статистика отдела за последние 7 дней: {weekly_stats}")
    else:
        print("Статистика отдела за последние 7 дней не найдена или произошла ошибка.")

    return render_template(
        'dashboard.html',
        mandatory_fields=mandatory_fields,
        optional_fields=optional_fields,
        fields_to_display=fields_to_display,
        hidden_fields=hidden_fields,
        field_names=field_names,
        notifications_count=notifications_count,
        weekly_stats=weekly_stats  # Передаём статистику в шаблон
    )


def get_my_weekly_stats(user_id, period):
    # Определяем сегодняшнюю дату
    today = date.today()
    
    # Определяем start_date и end_date в зависимости от значения period
    if period == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'last_month':
        first_day_of_current_month = today.replace(day=1)
        end_date = first_day_of_current_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif period == 'this_year':
        start_date = date(today.year, 1, 1)
        end_date = today
    elif period == 'last_year':
        last_year = today.year - 1
        start_date = date(last_year, 1, 1)
        end_date = date(last_year, 12, 31)
    else:
        return "Неверный период", 400  # Возвращаем ошибку при некорректном периоде

    # Подключаемся к базе данных
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    if period in ['last_month', 'this_month']:
        query = """
            SELECT user_id, date, deals, showings, adscian, adsavito, cold_calls, new_clients, mailouts, resales, banners, results, exclusives, stories
            FROM Scores
            WHERE user_id = %s AND date >= %s AND date <= %s
            ORDER BY date ASC
        """
        cursor.execute(query, (user_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        scores = cursor.fetchall()

        # Инициализация итогов
        totals = {key: 0 for key in ['deals', 'showings', 'adscian', 'adsavito', 'cold_calls', 'new_clients', 'mailouts', 'resales', 'banners', 'results', 'exclusives', 'stories']}
        for score in scores:
            for key, value in score.items():
                if key not in ['user_id', 'date'] and value is not None:
                    totals[key] += value

    elif period in ['this_year', 'last_year']:
        query = """
            SELECT 
                MONTH(date) as month,
                SUM(deals) as deals,
                SUM(showings) as showings,
                SUM(adscian) as adscian,
                SUM(adsavito) as adsavito,
                SUM(cold_calls) as cold_calls,
                SUM(new_clients) as new_clients,
                SUM(mailouts) as mailouts,
                SUM(resales) as resales,
                SUM(banners) as banners,
                SUM(results) as results,
                SUM(exclusives) as exclusives,
                SUM(stories) as stories
            FROM Scores
            WHERE user_id = %s AND date >= %s AND date <= %s
            GROUP BY MONTH(date)
            ORDER BY month ASC
        """
        cursor.execute(query, (user_id, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        monthly_data = cursor.fetchall()

        # Отладочный вывод
        print("Данные по месяцам из базы данных:")
        for data in monthly_data:
            print(data)

        # Инициализация структуры данных для итогов по месяцам
        scores = []
        month_names = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                       'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        for i, month_name in enumerate(month_names, start=1):
            # Ищем данные по текущему месяцу в monthly_data
            month_data = next((item for item in monthly_data if item['month'] == i), None)
            if month_data:
                # Если есть данные, преобразуем их в формат с названием месяца
                formatted_month_data = {
                    'date': month_name,  # Используем ключ 'date' для согласованности
                    'deals': int(month_data['deals']) if month_data['deals'] else 0,
                    'showings': int(month_data['showings']) if month_data['showings'] else 0,
                    'adscian': int(month_data['adscian']) if month_data['adscian'] else 0,
                    'adsavito': int(month_data['adsavito']) if month_data['adsavito'] else 0,
                    'cold_calls': int(month_data['cold_calls']) if month_data['cold_calls'] else 0,
                    'new_clients': int(month_data['new_clients']) if month_data['new_clients'] else 0,
                    'mailouts': int(month_data['mailouts']) if month_data['mailouts'] else 0,
                    'resales': int(month_data['resales']) if month_data['resales'] else 0,
                    'banners': int(month_data['banners']) if month_data['banners'] else 0,
                    'results': int(month_data['results']) if month_data['results'] else 0,
                    'exclusives': int(month_data['exclusives']) if month_data['exclusives'] else 0,
                    'stories': int(month_data['stories']) if month_data['stories'] else 0,
                }
                scores.append(formatted_month_data)
            else:
                # Если данных нет, добавляем месяц с нулевыми значениями
                scores.append({
                    'date': month_name,  # Используем ключ 'date' для согласованности
                    'deals': 0, 'showings': 0, 'adscian': 0, 'adsavito': 0, 
                    'cold_calls': 0, 'new_clients': 0, 'mailouts': 0, 
                    'resales': 0, 'banners': 0, 'results': 0, 
                    'exclusives': 0, 'stories': 0
                })

        # Отладочный вывод
        print("Отформатированные данные с названиями месяцев:")
        for score in scores:
            print(score)

        totals = None  # Итоги для года не считаем, так как данные агрегированы по месяцам

    else:
        # Обработка некорректного значения period
        cursor.close()
        connection.close()
        return "Неверный период", 400

    cursor.close()
    connection.close()

    return render_template(
        'my_statistics.html',
        scores=scores,
        totals=totals,
        period=period if period else "выберите период",
        mandatory_fields=mandatory_fields,
        optional_fields=optional_fields,
        hidden_fields=hidden_fields,
        field_names=field_names
    )



@userlist_bp.route('/admin/manage_notifications', methods=['GET', 'POST'])
@login_required
def manage_notifications():
    if session.get('role') != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('admin_dashboard'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        message = request.form['message']
        is_for_admin = 'is_for_admin' in request.form
        is_for_leader = 'is_for_leader' in request.form
        is_for_user = 'is_for_user' in request.form

        cursor.execute("""
            INSERT INTO Notifications (message, is_for_admin, is_for_leader, is_for_user)
            VALUES (%s, %s, %s, %s)
        """, (message, is_for_admin, is_for_leader, is_for_user))
        notification_id = cursor.lastrowid
        connection.commit()

        # Создание записей в UserNotifications для каждой роли
        if is_for_admin:
            assign_notifications_to_users('admin', notification_id, cursor)
        if is_for_leader:
            assign_notifications_to_users('leader', notification_id, cursor)
        if is_for_user:
            assign_notifications_to_users('user', notification_id, cursor)

        connection.commit()
        flash('Уведомление добавлено', 'success')

    # Загрузка всех уведомлений для отображения в таблице
    cursor.execute("SELECT * FROM Notifications ORDER BY created_at DESC")
    notifications = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('manage_notifications.html', notifications=notifications)

@userlist_bp.route('/delete_notification/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    if session.get('role') != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('admin_dashboard'))

    connection = create_db_connection()
    cursor = connection.cursor()
    # Удаление связей из UserNotifications
    cursor.execute("DELETE FROM UserNotifications WHERE notification_id = %s", (notification_id,))
    # Удаление уведомления
    cursor.execute("DELETE FROM Notifications WHERE id = %s", (notification_id,))
    connection.commit()
    cursor.close()
    connection.close()

    flash('Уведомление удалено', 'success')
    return redirect(url_for('manage_notifications'))

def assign_notifications_to_users(role, notification_id, cursor):
    cursor.execute("""
        SELECT id FROM User WHERE role = %s
    """, (role,))
    users = cursor.fetchall()
    for user in users:
        cursor.execute("""
            INSERT INTO UserNotifications (user_id, notification_id, is_read)
            VALUES (%s, %s, FALSE)
        """, (user['id'], notification_id))


@userlist_bp.route('/view_notifications')
@login_required
def view_notifications():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    role = session.get('role')

    query = """
    SELECT message FROM Notifications
    WHERE is_for_%s = TRUE
    ORDER BY created_at DESC
    """
    cursor.execute(query, (role,))
    notifications = cursor.fetchall()
    print(notifications)  # Отладочный вывод уведомлений
    cursor.close()
    connection.close()

    return jsonify(notifications)


def get_department_stats(department):
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls', 'adscian', 'adsavito',
        'mailouts', 'resales', 'banners', 'results', 'exclusives', 'stories',
        'total_ads_avito', 'total_ads_cian', 'incoming_cold_calls', 'stationary_calls'
    ]
    
    fields_sql = ", ".join([f"SUM({field}) as {field}" for field in all_fields])
    
    query = f"""
    SELECT {fields_sql}
    FROM Scores
    JOIN User ON Scores.user_id = User.id
    WHERE User.department = %s
    """
    
    # Отладка: выводим запрос в консоль
    print(f"Executing query: {query}")

    cursor.execute(query, (department,))
    stats = cursor.fetchone()
    
    # Отладка: выводим полученные результаты
    print(f"Stats fetched: {stats}")

    cursor.close()
    connection.close()
    
    return stats


@userlist_bp.route('/add_report', methods=['GET', 'POST'])
@login_required
def add_report():
    user_id = session.get('id')
    department = session.get('department')

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Получаем настройки видимости полей для отдела пользователя
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
    result = cursor.fetchone()
    if result:
        hidden_fields = json.loads(result.get('hidden_fields', '{}'))
    else:
        hidden_fields = {}

    # Определяем обязательные и необязательные поля
    mandatory_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings',
        'repeat_showings', 'new_clients', 'cold_calls'
    ]

    optional_fields = [
        'adscian', 'adsavito', 'mailouts', 'resales', 'banners',
        'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

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

    if request.method == 'POST':
        date = request.form.get('date')

        # Проверка даты
        if not date:
            return jsonify({'success': False, 'message': 'Дата обязательна.'})

        # Собираем данные обязательных полей
        data = {}
        for field in mandatory_fields:
            value = request.form.get(field, None)
            if value is None or value == '':
                return jsonify({'success': False, 'message': f'Поле "{field_names.get(field, field)}" обязательно.'})
            try:
                data[field] = int(value)
            except ValueError:
                return jsonify({'success': False, 'message': f'Поле "{field_names.get(field, field)}" должно быть числом.'})

        # Собираем данные необязательных полей, если они не скрыты
        for field in optional_fields:
            if not hidden_fields.get(field, False):
                value = request.form.get(field, None)
                if value and value != '':
                    try:
                        data[field] = int(value)
                    except ValueError:
                        return jsonify({'success': False, 'message': f'Поле "{field_names.get(field, field)}" должно быть числом.'})
                else:
                    data[field] = None  # Поле пустое
            else:
                data[field] = None  # Поле скрыто, данные не сохраняем

        # Формируем список полей и значений для вставки в БД
        fields = ['user_id', 'date'] + list(data.keys())
        values = [user_id, date] + list(data.values())

        # Создаем строку с плейсхолдерами для запроса
        placeholders = ', '.join(['%s'] * len(values))

        # Создаем строку с названиями полей для вставки
        fields_sql = ', '.join(fields)

        query = f"INSERT INTO Scores ({fields_sql}) VALUES ({placeholders})"

        try:
            cursor.execute(query, values)
            connection.commit()
            return jsonify({'success': True, 'message': 'Отчет успешно добавлен'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Ошибка при добавлении отчета: {str(e)}'})
        finally:
            cursor.close()
            connection.close()
    else:
        cursor.close()
        connection.close()
        return render_template(
            'add_report.html',
            mandatory_fields=mandatory_fields,
            optional_fields=optional_fields,
            hidden_fields=hidden_fields,
            field_names=field_names
        )

