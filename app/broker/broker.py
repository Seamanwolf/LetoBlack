from flask import render_template, redirect, url_for, flash, session, request, jsonify
from flask_login import current_user

from app.broker import broker_bp
from app.utils import login_required, create_db_connection, get_notifications_count

import json
from datetime import datetime, timedelta


@broker_bp.route('/dashboard')
@login_required
def broker_dashboard():
    """Дашборд брокера. Показывает статистику отдела за 7 дней и форму отчёта."""

    # Доступен только обычному пользователю
    if current_user.role != 'user':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('main.index'))

    department = session.get('department')
    user_id = session.get('id')

    if not department:
        flash('Не удалось определить отдел пользователя.', 'danger')
        return redirect(url_for('main.index'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Получаем настройки скрытых полей для отдела
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
        result = cursor.fetchone()
        hidden_fields_data = result.get('hidden_fields') if result else None
        hidden_fields = json.loads(hidden_fields_data) if hidden_fields_data else {}

        # Списки полей
        mandatory_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls'
        ]

        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        optional_fields = [field for field in all_fields if field not in mandatory_fields]

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

        # Формируем диапазон дат (последние 7 дней)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=6)

        # Динамическое формирование SQL с агрегациями
        fields_sql = ",\n".join([f"SUM(Scores.{field}) AS {field}" for field in all_fields])

        query = f"""
        SELECT User.id, User.full_name, {fields_sql}
        FROM Scores
        JOIN User ON Scores.user_id = User.id
        WHERE User.department = %s AND Scores.date BETWEEN %s AND %s
        GROUP BY User.id
        ORDER BY User.full_name
        """

        cursor.execute(query, (department, start_date, end_date))
        weekly_stats = cursor.fetchall()

        notifications_count = get_notifications_count()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        'broker/dashboard.html',
        weekly_stats=weekly_stats,
        mandatory_fields=mandatory_fields,
        optional_fields=optional_fields,
        hidden_fields=hidden_fields,
        field_names=field_names,
        all_fields=all_fields,
        notifications_count=notifications_count,
    )


# -----------------------
# Личная статистика
# -----------------------


@broker_bp.route('/my_stats')
@login_required
def my_stats():
    """Отображает расширенную статистику текущего пользователя (заглушка)."""
    if current_user.role != 'user':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('main.index'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Поля как в дашборде
    mandatory_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls'
    ]

    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    optional_fields = [f for f in all_fields if f not in mandatory_fields]

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

    # Определяем скрытые поля
    department = session.get('department')
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
    res = cursor.fetchone()
    hidden_fields = json.loads(res['hidden_fields']) if res and res.get('hidden_fields') else {}

    # Получаем данные за последние 30 дней
    cursor.execute(
        """SELECT date, {fields} FROM Scores WHERE user_id=%s ORDER BY date DESC LIMIT 30""".format(
            fields=", ".join(all_fields)
        ),
        (session.get('id'),)
    )
    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        'broker/my_stats.html',
        rows=rows,
        mandatory_fields=mandatory_fields,
        optional_fields=optional_fields,
        hidden_fields=hidden_fields,
        field_names=field_names,
    )


# -----------------------
# Добавление дневного отчёта
# -----------------------


@broker_bp.route('/add_report', methods=['POST'])
@login_required
def add_report():
    """Сохраняет отчёт брокера за день (AJAX)."""

    if current_user.role != 'user':
        return jsonify(success=False, message='Доступ запрещён'), 403

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Определяем поля аналогично broker_dashboard
    mandatory_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls'
    ]

    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    optional_fields = [field for field in all_fields if field not in mandatory_fields]

    # Получаем скрытые поля
    department = session.get('department')
    cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department,))
    result = cursor.fetchone()
    hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}

    data = {}
    # Обязательные
    for field in mandatory_fields:
        data[field] = request.form.get(field) or 0

    # Необязательные, если не скрыты
    for field in optional_fields:
        if not hidden_fields.get(field, False):
            data[field] = request.form.get(field) or 0
        else:
            data[field] = None

    date_val = request.form.get('date')
    if not date_val:
        return jsonify(success=False, message='Дата обязательна'), 400

    fields = ['user_id', 'date'] + list(data.keys())
    values = [session.get('id'), date_val] + list(data.values())

    placeholders = ','.join(['%s'] * len(values))
    query = f"INSERT INTO Scores ({', '.join(fields)}) VALUES ({placeholders})"

    try:
        cursor.execute(query, values)
        connection.commit()
        return jsonify(success=True, message='Отчёт добавлен')
    except Exception as err:
        connection.rollback()
        return jsonify(success=False, message=str(err)), 500
    finally:
        cursor.close()
        connection.close()


# -----------------------
# API: данные статистики по периоду
# -----------------------


@broker_bp.route('/stats_data')
@login_required
def stats_data():
    """Возвращает статистику текущего пользователя за выбранный период (week, month, year, custom)."""

    if current_user.role != 'user':
        return jsonify(success=False, message='Forbidden'), 403

    period = request.args.get('period', 'week')
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    today = datetime.now().date()

    if period == 'week':
        start_date = today - timedelta(days=6)
        end_date = today
    elif period == 'month':
        start_date = today - timedelta(days=29)
        end_date = today
    elif period == 'year':
        start_date = today - timedelta(days=364)
        end_date = today
    elif period == 'custom':
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except Exception:
            return jsonify(success=False, message='Некорректные даты'), 400
    else:
        return jsonify(success=False, message='Неверный период'), 400

    all_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
        'incoming_cold_calls', 'stationary_calls'
    ]

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Детализация по датам
        fields_sql = ", ".join([f"SUM({f}) AS {f}" for f in all_fields])
        cursor.execute(
            f"""
            SELECT date, {fields_sql}
            FROM Scores
            WHERE user_id=%s AND date BETWEEN %s AND %s
            GROUP BY date
            ORDER BY date ASC
            """,
            (session.get('id'), start_date, end_date)
        )
        rows = cursor.fetchall()

        # Суммы за период
        cursor.execute(
            f"""
            SELECT {fields_sql}
            FROM Scores
            WHERE user_id=%s AND date BETWEEN %s AND %s
            """,
            (session.get('id'), start_date, end_date)
        )
        totals = cursor.fetchone()

        # Подготовка ответа
        for r in rows:
            r['date'] = r['date'].strftime('%Y-%m-%d') if r.get('date') else ''

        return jsonify(success=True, rows=rows, totals=totals)
    except Exception as err:
        return jsonify(success=False, message=str(err)), 500
    finally:
        cursor.close()
        connection.close() 