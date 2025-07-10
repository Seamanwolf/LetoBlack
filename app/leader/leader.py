from flask import Blueprint, render_template, redirect, url_for, flash, session, jsonify, request, current_app
from flask_login import login_required, current_user
from app.leader import leader_bp
from app.db_connection import get_connection as get_db_connection
from app.utils import get_notifications_count, get_department_weekly_stats
from app.decorators import role_required
from datetime import datetime, timedelta
import json
from dateutil.relativedelta import relativedelta
from werkzeug.security import generate_password_hash
import mysql.connector

@leader_bp.route('/add_report_by_leader', methods=['POST'])
@login_required
def add_report_by_leader():
    if current_user.role != 'leader':
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    user_id = session.get('id')
    department = session.get('department')

    connection = get_db_connection()
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

    connection = get_db_connection()
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
    connection = get_db_connection()
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
    connection = get_db_connection()
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
            return redirect(url_for('broker.broker_dashboard'))
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
        connection = get_db_connection()
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
        connection = get_db_connection()
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
    с
    return redirect(url_for('leader.leader_dashboard'))

# Маршрут для главной страницы руководителя
@leader_bp.route('/main')
@login_required
@role_required(['leader', 'deputy'])
def leader_main():
    """Главная страница руководителя с таблицей отчетов и настройками полей"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Получаем настройки отображения полей
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (session.get('department'),))
        result = cursor.fetchone()
        hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}

        # Определяем все поля
        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        # Обязательные поля
        mandatory_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls'
        ]

        # Необязательные поля
        optional_fields = [field for field in all_fields if field not in mandatory_fields]

        # Названия полей
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

        # Получаем период из параметров запроса
        period = request.args.get('period', '7')
        try:
            period_days = int(period)
        except:
            period_days = 7

        # Получаем отчеты сотрудников за выбранный период
        cursor.execute("""
            SELECT 
                u.full_name,
                s.date,
                s.deals, s.reservations, s.online_showings, s.offline_showings,
                s.repeat_showings, s.new_clients, s.cold_calls, s.adscian, s.adsavito,
                s.mailouts, s.resales, s.banners, s.results, s.exclusives, s.stories,
                s.total_ads_avito, s.total_ads_cian, s.incoming_cold_calls, s.stationary_calls
            FROM Scores s
            JOIN User u ON s.user_id = u.id
            WHERE u.department = %s AND s.date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY s.date DESC, u.full_name ASC
        """, (session.get('department'), period_days))
        
        reports = cursor.fetchall()

        # Получаем количество уведомлений
        notifications_count = get_notifications_count()

        return render_template(
            'leader/leader_main.html',
            reports=reports,
            all_fields=all_fields,
            mandatory_fields=mandatory_fields,
            optional_fields=optional_fields,
            hidden_fields=hidden_fields,
            field_names=field_names,
            notifications_count=notifications_count,
            current_period=period_days
        )
    except Exception as e:
        print(f"Ошибка при загрузке главной страницы: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('main.index'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/get_chart_data')
@login_required
@role_required(['leader', 'deputy'])
def get_chart_data():
    """Возвращает данные для графиков на главной странице руководителя."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        department = current_user.department
        
        # Получаем ID всех сотрудников в отделе
        cursor.execute("SELECT id FROM User WHERE department = %s", (department,))
        user_ids = [row['id'] for row in cursor.fetchall()]

        if not user_ids:
            return jsonify({'success': True, 'chartData': {}, 'stats': {
                'totalDeals': 0, 'totalShowings': 0, 'totalCalls': 0, 'totalClients': 0
            }})

        # Определяем период (последние 7 дней)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=6)
        
        # Подготавливаем запрос
        placeholders = ', '.join(['%s'] * len(user_ids))
        query = f"""
            SELECT * FROM Scores 
            WHERE user_id IN ({placeholders}) AND `date` BETWEEN %s AND %s
        """
        
        params = user_ids + [start_date.date(), end_date.date()]
        cursor.execute(query, params)
        reports = cursor.fetchall()
        
        # Обработка данных для статистики и графиков
        stats = {
            'totalDeals': 0, 'totalShowings': 0, 'totalCalls': 0, 'totalClients': 0
        }
        daily_activity = {}
        deals_data = {}
        showings_data = {}
        calls_data = {}

        # Инициализируем дни
        for i in range(7):
            day = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            daily_activity[day] = 0
            deals_data[day] = 0
            showings_data[day] = 0
            calls_data[day] = 0

        for report in reports:
            report_date_str = report['date'].strftime('%Y-%m-%d')
            
            deals = report.get('deals', 0)
            
            online_showings = report.get('online_showings', 0)
            offline_showings = report.get('offline_showings', 0)
            repeat_showings = report.get('repeat_showings', 0)
            showings = online_showings + offline_showings + repeat_showings
            
            cold_calls = report.get('cold_calls', 0)
            incoming_cold_calls = report.get('incoming_cold_calls', 0)
            stationary_calls = report.get('stationary_calls', 0)
            calls = cold_calls + incoming_cold_calls + stationary_calls
            
            new_clients = report.get('new_clients', 0)
            
            activity = deals + showings + calls + new_clients
            
            stats['totalDeals'] += deals
            stats['totalShowings'] += showings
            stats['totalCalls'] += calls
            stats['totalClients'] += new_clients
            
            if report_date_str in daily_activity:
                daily_activity[report_date_str] += activity
                deals_data[report_date_str] += deals
                showings_data[report_date_str] += showings
                calls_data[report_date_str] += calls

        # Формируем данные для графиков
        sorted_daily_keys = sorted(daily_activity.keys())
        
        chartData = {
            'totalDeals': stats['totalDeals'],
            'totalShowings': stats['totalShowings'],
            'totalCalls': stats['totalCalls'],
            'totalClients': stats['totalClients'],
            'dailyLabels': [datetime.strptime(d, '%Y-%m-%d').strftime('%d.%m') for d in sorted_daily_keys],
            'dailyActivity': [daily_activity[d] for d in sorted_daily_keys],
            'trendLabels': [datetime.strptime(d, '%Y-%m-%d').strftime('%d.%m') for d in sorted_daily_keys],
            'dealsData': [deals_data[d] for d in sorted_daily_keys],
            'showingsData': [showings_data[d] for d in sorted_daily_keys],
            'callsData': [calls_data[d] for d in sorted_daily_keys]
        }

        return jsonify({'success': True, 'chartData': chartData, 'stats': stats})

    except Exception as e:
        print(f"Error in get_chart_data: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

@leader_bp.route('/statistics')
@login_required
@role_required(['leader', 'deputy'])
def statistics():
    """Страница статистики с фильтрами"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем список сотрудников отдела
        cursor.execute("""
            SELECT id, full_name 
            FROM User 
            WHERE department = %s AND (status IS NULL OR status != 'fired')
            ORDER BY full_name
        """, (session.get('department'),))
        
        employees = cursor.fetchall()
        
        # Получаем количество уведомлений
        notifications_count = get_notifications_count()
        
        return render_template(
            'leader/statistics.html',
            employees=employees,
            notifications_count=notifications_count
        )
        
    except Exception as e:
        print(f"Ошибка при загрузке страницы статистики: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('leader.leader_main'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/get_statistics_data')
@login_required
@role_required(['leader', 'deputy'])
def get_statistics_data():
    """Получает данные для страницы статистики"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем параметры фильтрации
        period = request.args.get('period', '7')
        employee_id = request.args.get('employee_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Строим условие WHERE для дат
        date_condition = ""
        params = [session.get('department')]
        
        if period == 'custom' and start_date and end_date:
            date_condition = "AND s.date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        elif period == 'all':
            date_condition = ""
        else:
            try:
                period_days = int(period)
                date_condition = "AND s.date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)"
                params.append(period_days)
            except:
                date_condition = "AND s.date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
                params.append(7)
        
        # Добавляем фильтр по сотруднику
        employee_condition = ""
        if employee_id:
            employee_condition = "AND u.id = %s"
            params.append(employee_id)
        
        # Получаем детальную статистику
        query = f"""
            SELECT 
                u.full_name,
                s.date,
                s.deals, s.reservations, s.online_showings, s.offline_showings,
                s.repeat_showings, s.new_clients, s.cold_calls, s.adscian, s.adsavito,
                s.mailouts, s.resales, s.banners, s.results, s.exclusives, s.stories,
                s.total_ads_avito, s.total_ads_cian, s.incoming_cold_calls, s.stationary_calls
            FROM Scores s
            JOIN User u ON s.user_id = u.id
            WHERE u.department = %s {date_condition} {employee_condition}
            ORDER BY s.date DESC, u.full_name ASC
        """
        
        cursor.execute(query, params)
        statistics = cursor.fetchall()
        
        # Вычисляем сводную статистику
        summary = {
            'totalDeals': 0,
            'totalShowings': 0,
            'totalCalls': 0,
            'totalClients': 0
        }
        
        for row in statistics:
            summary['totalDeals'] += row['deals'] or 0
            summary['totalShowings'] += (row['online_showings'] or 0) + (row['offline_showings'] or 0)
            summary['totalCalls'] += row['cold_calls'] or 0
            summary['totalClients'] += row['new_clients'] or 0
        
        return jsonify({
            'success': True,
            'statistics': statistics,
            'summary': summary
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/export_statistics')
@login_required
@role_required(['leader', 'deputy'])
def export_statistics():
    """Экспорт статистики в Excel"""
    try:
        import pandas as pd
        from io import BytesIO
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем параметры фильтрации (те же, что и в get_statistics_data)
        period = request.args.get('period', '7')
        employee_id = request.args.get('employee_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Строим условие WHERE для дат
        date_condition = ""
        params = [session.get('department')]
        
        if period == 'custom' and start_date and end_date:
            date_condition = "AND s.date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        elif period == 'all':
            date_condition = ""
        else:
            try:
                period_days = int(period)
                date_condition = "AND s.date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)"
                params.append(period_days)
            except:
                date_condition = "AND s.date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
                params.append(7)
        
        # Добавляем фильтр по сотруднику
        employee_condition = ""
        if employee_id:
            employee_condition = "AND u.id = %s"
            params.append(employee_id)
        
        # Получаем данные
        query = f"""
            SELECT 
                u.full_name as 'Сотрудник',
                s.date as 'Дата',
                s.deals as 'Сделки',
                s.reservations as 'Брони',
                s.online_showings as 'Показы онлайн',
                s.offline_showings as 'Показы офлайн',
                s.repeat_showings as 'Повторные показы',
                s.new_clients as 'Новые клиенты',
                s.cold_calls as 'Холодные звонки',
                s.adscian as 'Реклама Циан',
                s.adsavito as 'Реклама Авито',
                s.mailouts as 'Рассылки',
                s.resales as 'Вторички',
                s.banners as 'Баннеры',
                s.results as 'Сработки',
                s.exclusives as 'Эксклюзивы',
                s.stories as 'Сторис',
                s.total_ads_avito as 'Реклама Авито (общ.)',
                s.total_ads_cian as 'Реклама Циан (общ.)',
                s.incoming_cold_calls as 'Входящие',
                s.stationary_calls as 'Стационар'
            FROM Scores s
            JOIN User u ON s.user_id = u.id
            WHERE u.department = %s {date_condition} {employee_condition}
            ORDER BY s.date DESC, u.full_name ASC
        """
        
        cursor.execute(query, params)
        data = cursor.fetchall()
        
        # Создаем DataFrame
        df = pd.DataFrame(data)
        
        # Создаем Excel файл в памяти
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Статистика', index=False)
        
        output.seek(0)
        
        # Возвращаем файл
        from flask import make_response
        response = make_response(output.read())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = 'attachment; filename=statistics.xlsx'
        
        return response
        
    except ImportError:
        flash('Для экспорта в Excel требуется установка библиотеки pandas', 'warning')
        return redirect(url_for('leader.statistics'))
    except Exception as e:
        print(f"Ошибка при экспорте: {e}")
        flash(f'Ошибка при экспорте: {str(e)}', 'danger')
        return redirect(url_for('leader.statistics'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/leader/settings')
@login_required
@role_required(['leader', 'deputy'])
def settings():
    """Страница настроек"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Получаем настройки отображения полей
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (session.get('department'),))
        result = cursor.fetchone()
        hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}

        # Определяем все поля
        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        # Обязательные поля
        mandatory_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls'
        ]

        # Необязательные поля
        optional_fields = [field for field in all_fields if field not in mandatory_fields]

        # Названия полей
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

        return render_template(
            'leader/settings.html',
            all_fields=all_fields,
            mandatory_fields=mandatory_fields,
            optional_fields=optional_fields,
            hidden_fields=hidden_fields,
            field_names=field_names,
            notifications_count=notifications_count
        )
        
    except Exception as e:
        print(f"Ошибка при загрузке страницы настроек: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('leader.leader_main'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/dashboard')
@login_required
@role_required(['leader', 'deputy'])
def leader_dashboard():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Получаем данные о сотрудниках отдела
        cursor.execute("""
            SELECT id, full_name, role, status
            FROM User 
            WHERE department = %s AND (status IS NULL OR status != 'fired')
            ORDER BY full_name
        """, (session.get('department'),))
        employees = cursor.fetchall()

        # Получаем статистику отдела за текущий месяц
        today = datetime.now().date()
        start_date = today.replace(day=1)  # Первый день текущего месяца
        end_date = today

        department_stats = get_department_statistics(session.get('department'), start_date, end_date)
        if department_stats is None:
            department_stats = {
                'total_employees': len(employees),
                'new_employees': 0,
                'completed_tasks': 0,
                'avg_tasks_per_employee': 0,
                'avg_activity': 0,
                'activity_trend': 0,
                'total_hours': 0,
                'avg_hours_per_employee': 0
            }

        # Получаем количество уведомлений
        notifications_count = get_notifications_count()

        return render_template(
            'leader_dashboard.html',
            employees=employees,
            stats=department_stats,
            notifications_count=notifications_count
        )
    except Exception as e:
        print(f"Ошибка при загрузке дашборда: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('main.index'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/leader/update_stats', methods=['POST'])
@login_required
def update_stats():
    """Обновляет статистику сотрудника."""
    if current_user.role != 'leader':
        return jsonify(success=False, message='Доступ запрещен'), 403

    user_id = request.form.get('user_id')
    date_val = request.form.get('date')

    if not user_id or not date_val:
        return jsonify(success=False, message='Не указан пользователь или дата'), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Проверяем, что пользователь из нашего отдела
        cursor.execute(
            "SELECT department FROM User WHERE id = %s",
            (user_id,)
        )
        user_dept = cursor.fetchone()
        
        if not user_dept or user_dept['department'] != session.get('department'):
            return jsonify(success=False, message='Нет доступа к данному пользователю'), 403

        # Получаем настройки полей
        cursor.execute(
            "SELECT hidden_fields FROM DepartmentSettings WHERE department = %s",
            (session.get('department'),)
        )
        result = cursor.fetchone()
        hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}

        # Собираем данные из формы
        mandatory_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings',
            'repeat_showings', 'new_clients', 'cold_calls'
        ]

        optional_fields = [
            'adscian', 'adsavito', 'mailouts', 'resales', 'banners',
            'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        data = {}
        for field in mandatory_fields:
            data[field] = request.form.get(field, 0)

        for field in optional_fields:
            if not hidden_fields.get(field, False):
                data[field] = request.form.get(field, 0)

        # Проверяем существование записи
        cursor.execute(
            "SELECT id FROM Scores WHERE user_id = %s AND date = %s",
            (user_id, date_val)
        )
        existing = cursor.fetchone()

        if existing:
            # Обновляем существующую запись
            set_clause = ', '.join(f"{k} = %s" for k in data.keys())
            values = list(data.values()) + [user_id, date_val]
            query = f"UPDATE Scores SET {set_clause} WHERE user_id = %s AND date = %s"
        else:
            # Создаем новую запись
            fields = ['user_id', 'date'] + list(data.keys())
            values = [user_id, date_val] + list(data.values())
            placeholders = ', '.join(['%s'] * len(values))
            query = f"INSERT INTO Scores ({', '.join(fields)}) VALUES ({placeholders})"

        cursor.execute(query, values)
        connection.commit()

        return jsonify(success=True, message='Статистика обновлена')

    except Exception as e:
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        connection.close()


def get_department_statistics(department_id, start_date, end_date):
    """
    Получает статистику отдела за указанный период
    """
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Получаем настройки скрытых полей
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department_id,))
        result = cursor.fetchone()
        hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}

        # Определяем все возможные поля
        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        # Определяем поля для отображения
        fields_to_display = [field for field in all_fields if not hidden_fields.get(field, False)]

        # Названия полей для отображения
        field_names = {
            'deals': 'Сделки',
            'reservations': 'Брони',
            'online_showings': 'Онлайн показы',
            'offline_showings': 'Офлайн показы',
            'repeat_showings': 'Повторные показы',
            'new_clients': 'Новый клиент',
            'cold_calls': 'Холодные звонки',
            'adscian': 'Объявления ЦИАН',
            'adsavito': 'Объявления Авито',
            'mailouts': 'Рассылки',
            'resales': 'Повторные продажи',
            'banners': 'Баннеры',
            'results': 'Результаты',
            'exclusives': 'Эксклюзивы',
            'stories': 'Истории',
            'total_ads_avito': 'Всего объявлений Авито',
            'total_ads_cian': 'Всего объявлений ЦИАН',
            'incoming_cold_calls': 'Входящие холодные звонки',
            'stationary_calls': 'Стационарные звонки'
        }

        # Разделяем поля на суммируемые и поля с последним значением
        sum_fields = [field for field in fields_to_display if field not in ['total_ads_avito', 'total_ads_cian']]
        last_fields = [field for field in ['total_ads_avito', 'total_ads_cian'] if field in fields_to_display]

        # Строим SQL-запрос динамически
        sum_fields_sql = ", ".join([f"SUM(Scores.{field}) AS {field}" for field in sum_fields])
        last_fields_sql = ", ".join([f"MAX(Scores.{field}) AS {field}" for field in last_fields])
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

        # Получаем дополнительную статистику
        cursor.execute("""
            SELECT COUNT(*) as total_employees,
                   SUM(CASE WHEN hire_date >= %s THEN 1 ELSE 0 END) as new_employees
            FROM User
            WHERE department = %s AND (status IS NULL OR status != 'fired')
        """, (start_date.strftime('%Y-%m-%d'), department_id))
        employee_stats = cursor.fetchone()

        # Заглушка для статистики задач (пока таблица Tasks не реализована)
        task_stats = {
            'completed_tasks': 0,
            'completion_rate': 0
        }

        # Формируем итоговую статистику
        department_stats = {
            'total_employees': employee_stats['total_employees'],
            'new_employees': employee_stats['new_employees'],
            'completed_tasks': task_stats['completed_tasks'],
            'avg_tasks_per_employee': 0,
            'avg_activity': 0,  # Будет рассчитано позже
            'activity_trend': 0,  # Будет рассчитано позже
            'scores': scores,
            'field_names': field_names,
            'fields_to_display': fields_to_display
        }

        # Рендерим строки таблицы
        table_rows = render_template('department_statistics_table_rows.html',
                                   scores=scores,
                                   sum_fields=sum_fields,
                                   last_fields=last_fields,
                                   field_names=field_names)

        department_stats['table_rows'] = table_rows

        return department_stats

    except Exception as e:
        print(f"Ошибка при получении статистики отдела: {e}")
        return None
    finally:
        cursor.close()
        connection.close()


@leader_bp.route('/leader/department_users')
@login_required
def show_department_users():
    if current_user.role != 'leader':
        flash('У вас нет доступа к этой странице.', 'danger')
        return redirect(url_for('auth.login'))

    department = session.get('department')

    connection = get_db_connection()
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
    department_id = session.get('department')
    
    # Вычисляем начало и конец текущего месяца
    today = datetime.now().date()
    start_date = today.replace(day=1)  # Первый день текущего месяца
    # Определяем последний день месяца (следующий месяц - 1 день)
    next_month = today.replace(day=28) + timedelta(days=4)  # Гарантированно перейдем в следующий месяц
    end_date = next_month.replace(day=1) - timedelta(days=1)  # Последний день текущего месяца
    
    return get_department_statistics(department_id, start_date, end_date)

@leader_bp.route('/department_statistics/month', methods=['POST'])
@login_required
def department_month_statistics():
    # Этот маршрут просто вызывает существующую функцию monthly_statistics для совместимости
    return department_monthly_statistics()

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


@leader_bp.route('/manage_fields', methods=['POST'])
@login_required
@role_required(['leader', 'deputy'])
def manage_fields():
    try:
        department = session.get('department')
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Все необязательные поля
        optional_fields = [
            'adscian', 'adsavito', 'mailouts', 'resales', 'banners',
            'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        # Инициализируем hidden_fields
        hidden_fields = {}

        # Устанавливаем значения на основе полученных данных
        for field in optional_fields:
            value = request.form.get(field)
            hidden_fields[field] = (value == 'off')  # True если 'off' (скрыто), False если 'on' (видимо)

        # Проверяем, существует ли уже запись для этого отдела
        cursor.execute("SELECT id FROM DepartmentSettings WHERE department = %s", (department,))
        result = cursor.fetchone()

        # Обновляем или вставляем запись в базе данных
        if result:
            cursor.execute("""
                UPDATE DepartmentSettings SET hidden_fields = %s WHERE department = %s
            """, (json.dumps(hidden_fields), department))
        else:
            cursor.execute("""
                INSERT INTO DepartmentSettings (department, hidden_fields) VALUES (%s, %s)
            """, (department, json.dumps(hidden_fields)))

        connection.commit()
        
        return jsonify({'success': True, 'message': 'Настройки полей сохранены'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/leader/department_statistics', methods=['GET'])
@login_required
def department_statistics():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Получаем настройки отображения полей
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (session.get('department'),))
        result = cursor.fetchone()
        hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}

        # Определяем все поля
        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]
        
        # Названия полей
        field_names = {
            'deals': 'Сделки', 'reservations': 'Брони', 'online_showings': 'Показы онлайн',
            'offline_showings': 'Показы офлайн', 'repeat_showings': 'Повторные показы',
            'new_clients': 'Новый клиент', 'cold_calls': 'Холодные звонки', 'adscian': 'Реклама Циан',
            'adsavito': 'Реклама Авито', 'mailouts': 'Рассылки', 'resales': 'Вторички',
            'banners': 'Баннеры', 'results': 'Сработки', 'exclusives': 'Эксклюзивы',
            'stories': 'Сторис', 'total_ads_avito': 'Реклама Авито (общ.)',
            'total_ads_cian': 'Реклама Циан (общ.)', 'incoming_cold_calls': 'Входящие',
            'stationary_calls': 'Стационар (737)',
        }

        # Получаем статистику отдела за текущий месяц
        today = datetime.now().date()
        start_date = today.replace(day=1)
        end_date = today

        stats = get_department_statistics(session.get('department'), start_date, end_date)
        if not stats:
            flash('Ошибка при загрузке статистики отдела', 'danger')
            stats = {} # Обеспечиваем, что stats - это словарь

        # Получаем количество уведомлений
        notifications_count = get_notifications_count()

        return render_template(
            'department_statistics.html',
            stats=stats,
            hidden_fields=hidden_fields,
            all_fields=all_fields,
            field_names=field_names,
            notifications_count=notifications_count
        )
    except Exception as e:
        print(f"Ошибка при загрузке страницы статистики отдела: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('leader.leader_dashboard'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@leader_bp.route('/leader/edit_user/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user_by_leader(id):
    if current_user.role != 'leader':
        flash('Только руководители могут редактировать данные пользователей.', 'danger')
        return redirect(url_for('leader.leader_dashboard'))

    connection = get_db_connection()
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

        connection = get_db_connection()
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

    connection = get_db_connection()
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
            connection = get_db_connection()
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


@leader_bp.route('/department_statistics/<period>', methods=['POST'])
@login_required
def get_period_statistics(period):
    """Получает статистику отдела за указанный период."""
    if current_user.role != 'leader':
        return jsonify(success=False, message='Доступ запрещен'), 403

    department = session.get('department')
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        end_date = datetime.now().date()
        
        # Определяем начальную дату в зависимости от периода
        if period == 'week':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date - timedelta(days=30)
        elif period == 'year':
            start_date = end_date - timedelta(days=365)
        else:
            return jsonify(success=False, message='Неверный период'), 400

        # Получаем список сотрудников отдела
        cursor.execute("""
            SELECT u.id, u.full_name
            FROM User u
            WHERE u.department = %s AND u.role = 'user'
            ORDER BY u.full_name
        """, (department,))
        users = cursor.fetchall()

        # Получаем все поля для статистики
        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]

        # Получаем статистику по дням для графика
        cursor.execute(f"""
            SELECT 
                DATE(date) as date,
                {', '.join(f'SUM({field}) as {field}' for field in all_fields)}
            FROM Scores
            WHERE user_id IN (
                SELECT id FROM User 
                WHERE department = %s AND role = 'user'
            )
            AND date BETWEEN %s AND %s
            GROUP BY DATE(date)
            ORDER BY date
        """, (department, start_date, end_date))
        daily_stats = cursor.fetchall()

        # Получаем общую статистику по сотрудникам
        user_stats = []
        for user in users:
            cursor.execute(f"""
                SELECT {', '.join(f'SUM({field}) as {field}' for field in all_fields)}
                FROM Scores
                WHERE user_id = %s AND date BETWEEN %s AND %s
            """, (user['id'], start_date, end_date))
            stats = cursor.fetchone()
            user_stats.append({
                'name': user['full_name'],
                'stats': stats if stats else {}
            })

        # Форматируем данные для графиков
        dates = [str(stat['date']) for stat in daily_stats]
        deals_data = [stat['deals'] or 0 for stat in daily_stats]
        showings_data = [(stat['online_showings'] or 0) + (stat['offline_showings'] or 0) for stat in daily_stats]
        calls_data = [stat['cold_calls'] or 0 for stat in daily_stats]

        # Форматируем данные для таблицы
        table_data = []
        for user in user_stats:
            row = {
                'name': user['name'],
                'stats': {
                    field: user['stats'].get(field, 0) or 0
                    for field in all_fields
                }
            }
            table_data.append(row)

        return jsonify({
            'success': True,
            'chart_data': {
                'labels': dates,
                'deals': deals_data,
                'showings': showings_data,
                'calls': calls_data
            },
            'table_data': table_data
        })

    except Exception as e:
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        connection.close()

# API для получения данных дашборда
@leader_bp.route('/api/dashboard_data')
@login_required
@role_required(['leader', 'deputy'])
def get_dashboard_data():
    try:
        # Получаем параметры
        period = request.args.get('period', 'month')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        department_id = current_user.department

        # 1. Загружаем настройки полей
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (department_id,))
        result = cursor.fetchone()
        hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}
        
        # 2. Определяем все поля и их названия
        all_fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]
        field_names = {
            'deals': 'Сделки', 'reservations': 'Брони', 'online_showings': 'Показы онлайн',
            'offline_showings': 'Показы офлайн', 'repeat_showings': 'Повторные показы',
            'new_clients': 'Новый клиент', 'cold_calls': 'Холодные звонки', 'adscian': 'Реклама Циан',
            'adsavito': 'Реклама Авито', 'mailouts': 'Рассылки', 'resales': 'Вторички',
            'banners': 'Баннеры', 'results': 'Сработки', 'exclusives': 'Эксклюзивы',
            'stories': 'Сторис', 'total_ads_avito': 'Реклама Авито (общ.)',
            'total_ads_cian': 'Реклама Циан (общ.)', 'incoming_cold_calls': 'Входящие',
            'stationary_calls': 'Стационар (737)'
        }

        # Определяем даты периода
        # ... (логика определения start_dt и end_dt) ...
        today = datetime.now().date()
        if start_date_str and end_date_str:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        # ... (остальная логика для week, month, year) ...
        else:
            start_dt = today.replace(day=1)
            end_dt = today

        # Получаем сотрудников отдела
        cursor.execute(
            "SELECT id, full_name, role, status FROM User WHERE department = %s AND (status IS NULL OR status != 'fired')",
            (department_id,)
        )
        employees = cursor.fetchall()
        
        # 3. Для каждого сотрудника вычисляем ВСЮ статистику
        sum_fields_sql = ", ".join([f"SUM({field}) as {field}" for field in all_fields])
        for employee in employees:
            cursor.execute(
                f"SELECT {sum_fields_sql} FROM Scores WHERE user_id = %s AND date BETWEEN %s AND %s",
                (employee['id'], start_dt, end_dt)
            )
            stats_data = cursor.fetchone()
            for field in all_fields:
                employee[field] = stats_data[field] or 0 if stats_data else 0
            
            # Получаем активность отдельно
            cursor.execute(
                "SELECT AVG(activity) as avg_activity FROM user_activity WHERE user_id = %s AND date BETWEEN %s AND %s",
                (employee['id'], start_dt, end_dt)
            )
            activity_data = cursor.fetchone()
            employee['activity'] = round(float(activity_data['avg_activity']), 1) if activity_data and activity_data['avg_activity'] else 0

        # ... (расчет общей статистики для карточек: stats) ...
        stats = { 'employees_count': len(employees) } # Упрощено для краткости

        # 4. Возвращаем все данные
        return jsonify({
            'success': True,
            'stats': stats,
            'employees': employees,
            'all_fields': all_fields,
            'hidden_fields': hidden_fields,
            'field_names': field_names
        })
        
    except Exception as e:
        print(f"Ошибка в get_dashboard_data: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@leader_bp.route('/add_report', methods=['POST'])
@login_required
@role_required(['leader', 'deputy'])
def add_leader_report():
    """Сохраняет отчет для сотрудника или для себя (лидера)"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Если employee_id не передан, отчет заполняется для текущего пользователя (лидера)
        employee_id = request.form.get('employee_id', current_user.id)
        date_str = request.form.get('date')

        if not date_str:
            return jsonify({'success': False, 'message': 'Не указана дата'})
        
        # Проверяем, что дата не в будущем
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if report_date > date.today():
            return jsonify({'success': False, 'message': 'Нельзя заполнять отчет на будущую дату'})

        # Проверяем, что у лидера есть права на этого сотрудника
        if str(employee_id) != str(current_user.id):
            cursor.execute("SELECT department FROM User WHERE id = %s", (employee_id,))
            emp_dept = cursor.fetchone()
            if not emp_dept or emp_dept[0] != current_user.department:
                return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

        # Удаляем существующий отчет на эту дату для этого пользователя
        cursor.execute("DELETE FROM Scores WHERE user_id = %s AND date = %s", (employee_id, date_str))

        # Собираем данные
        fields = [
            'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
            'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
            'banners', 'results', 'exclusives', 'stories', 'total_ads_avito', 'total_ads_cian',
            'incoming_cold_calls', 'stationary_calls'
        ]
        
        values = {'user_id': employee_id, 'date': date_str}
        for field in fields:
            value = request.form.get(field)
            if value and value.isdigit():
                values[field] = int(value)
            else:
                values[field] = 0
        
        # Сохраняем новый отчет
        columns = ', '.join(values.keys())
        placeholders = ', '.join(['%s'] * len(values))
        
        query = f"INSERT INTO Scores ({columns}) VALUES ({placeholders})"
        cursor.execute(query, list(values.values()))
        
        connection.commit()
        
        return jsonify({'success': True})

    except Exception as e:
        if 'connection' in locals() and connection.is_connected():
            connection.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

@leader_bp.route('/get_employee_info/<int:employee_id>')
@login_required
@role_required(['leader', 'deputy'])
def get_employee_info(employee_id):
    """Получает информацию о сотруднике для просмотра."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Проверяем, что сотрудник принадлежит отделу текущего руководителя
        cursor.execute("""
            SELECT 
                u.id,
                u.full_name,
                u.login,
                u.role,
                u.position,
                u.department,
                u.personal_email as email,
                u.Phone as phone,
                u.hire_date,
                u.corporate_email,
                u.birth_date,
                u.notes,
                u.rr,
                u.site,
                u.documents,
                u.pc_login,
                u.pc_password,
                u.crm_id,
                u.office,
                u.fire_date,
                u.crm_login,
                u.crm_password,
                u.status
            FROM User u
            WHERE u.id = %s AND u.department = %s
        """, (employee_id, session.get('department')))
        
        employee = cursor.fetchone()
        
        if not employee:
            return jsonify(success=False, message='Сотрудник не найден или не принадлежит вашему отделу'), 404

        # Форматируем дату
        if employee['hire_date']:
            employee['hire_date'] = employee['hire_date'].strftime('%d.%m.%Y')

        return jsonify(success=True, employee=employee)

    except Exception as e:
        return jsonify(success=False, message=str(e)), 500
    finally:
        cursor.close()
        connection.close()


@leader_bp.route('/my_department')
@login_required
@role_required(['leader', 'deputy'])
def my_department():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Получаем данные о сотрудниках отдела (исключая текущего пользователя)
        cursor.execute("""
            SELECT id, full_name, role, status, position, Phone, personal_email, hire_date
            FROM User 
            WHERE department = %s AND (status IS NULL OR status != 'fired') AND id != %s
            ORDER BY full_name
        """, (session.get('department'), session.get('id')))
        employees = cursor.fetchall()

        # Получаем статистику отдела за текущий месяц
        today = datetime.now().date()
        start_date = today.replace(day=1)  # Первый день текущего месяца
        end_date = today

        department_stats = get_department_statistics(session.get('department'), start_date, end_date)
        if department_stats is None:
            department_stats = {
                'total_employees': len(employees),
                'new_employees': 0,
                'completed_tasks': 0,
                'avg_tasks_per_employee': 0,
                'avg_activity': 0,
                'activity_trend': 0,
                'total_hours': 0,
                'avg_hours_per_employee': 0
            }

        # Определяем поля для формы отчета
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
        cursor.execute("SELECT hidden_fields FROM DepartmentSettings WHERE department = %s", (session.get('department'),))
        result = cursor.fetchone()
        hidden_fields = json.loads(result['hidden_fields']) if result and result.get('hidden_fields') else {}

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

        return render_template(
            'leader/my_department.html',
            employees=employees,
            stats=department_stats,
            mandatory_fields=mandatory_fields,
            optional_fields=optional_fields,
            hidden_fields=hidden_fields,
            field_names=field_names,
            notifications_count=notifications_count
        )
    except Exception as e:
        print(f"Ошибка при загрузке страницы отдела: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('main.index'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

# Маршрут для страницы настроек отображения
@leader_bp.route('/display_settings', methods=['GET', 'POST'])
@login_required
@role_required(['leader', 'deputy'])
def display_settings():
    if request.method == 'POST':
        # Сохраняем настройки в сессию
        session['display_settings'] = {
            'show_role': request.form.get('show_role') == 'on',
            'show_name': request.form.get('show_name') == 'on',
            'show_status': request.form.get('show_status') == 'on'
        }
        flash('Настройки отображения сохранены', 'success')
        return redirect(url_for('leader.my_department'))

    # Получаем текущие настройки из сессии или используем значения по умолчанию
    display_settings = session.get('display_settings', {
        'show_role': True,
        'show_name': True,
        'show_status': True
    })

    # Получаем количество уведомлений
    notifications_count = get_notifications_count()

    return render_template(
        'display_settings.html',
        display_settings=display_settings,
        notifications_count=notifications_count
    )

# API для сохранения настроек отображения
@leader_bp.route('/api/save_display_settings', methods=['POST'])
@login_required
@role_required(['leader', 'deputy'])
def save_display_settings():
    try:
        settings = request.json
        
        # Обязательные поля всегда должны быть включены
        settings['show_role'] = True
        settings['show_name'] = True
        
        # Сохраняем настройки в сессии
        session['display_settings'] = settings
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Ошибка при сохранении настроек: {e}")
        return jsonify({'success': False, 'message': str(e)})

# API для получения настроек отображения
@leader_bp.route('/api/get_display_settings')
@login_required
@role_required(['leader', 'deputy'])
def get_display_settings():
    try:
        # Загружаем настройки из сессии или используем значения по умолчанию
        display_settings = session.get('display_settings', {
            'show_role': True,
            'show_name': True,
            'show_position': True,
            'show_phone': True,
            'show_email': True,
            'show_status': True,
            'show_office': False,
            'show_last_active': False
        })
        
        return jsonify({'success': True, 'settings': display_settings})
    except Exception as e:
        print(f"Ошибка при получении настроек: {e}")
        return jsonify({'success': False, 'message': str(e)})

# API для получения данных сотрудников отдела
@leader_bp.route('/api/department_employees')
@login_required
@role_required(['leader', 'deputy'])
def get_department_employees():
    try:
        # Получаем параметры
        period = request.args.get('period', 'month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Не удалось подключиться к базе данных'})
            
        cursor = conn.cursor(dictionary=True)
        
        # Получаем ID отдела текущего руководителя
        cursor.execute(
            "SELECT department as department_id FROM User WHERE id = %s",
            (current_user.id,)
        )
        department = cursor.fetchone()
        
        if not department:
            return jsonify({'success': False, 'message': 'Отдел не найден'})
        
        department_id = department['department_id']
        
        # Получаем сотрудников отдела
        cursor.execute(
            """
            SELECT u.id, u.full_name, u.role, u.login, u.status
            FROM User u
            WHERE u.department = %s AND (u.status IS NULL OR u.status != 'fired')
            ORDER BY CASE 
                WHEN u.role = 'leader' THEN 1
                WHEN u.role = 'deputy' THEN 2
                ELSE 3
            END, u.full_name ASC
            """,
            (department_id,)
        )
        employees = cursor.fetchall()
        
        return jsonify({'success': True, 'employees': employees})
    except Exception as e:
        print(f"Ошибка при получении сотрудников: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# API для получения статистики сотрудника
@leader_bp.route('/api/employee_statistics/<int:employee_id>')
@login_required
@role_required(['leader', 'deputy'])
def get_employee_statistics(employee_id):
    try:
        # Получаем параметры
        period = request.args.get('period', 'month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, что сотрудник принадлежит отделу текущего руководителя
        cursor.execute(
            """
            SELECT u.id, u.department
            FROM User u
            JOIN User leader ON u.department = leader.department
            WHERE u.id = %s AND leader.id = %s
            """,
            (employee_id, current_user.id)
        )
        employee = cursor.fetchone()
        
        if not employee:
            return jsonify({'success': False, 'message': 'Сотрудник не найден или не принадлежит вашему отделу'})
        
        # Определяем временной интервал для выборки статистики
        date_condition = ""
        date_params = []
        
        # Используем указанный произвольный период, если он задан
        if start_date and end_date:
            date_condition = "AND date BETWEEN %s AND %s"
            date_params = [start_date, end_date]
        # Иначе используем период из параметра period
        elif period == 'week':
            date_condition = "AND date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
        elif period == 'month':
            date_condition = "AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
        elif period == 'year':
            date_condition = "AND date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)"
        
        # Получаем статистику сотрудника
        query = f"""
            SELECT 
                SUM(deals) as total_deals,
                SUM(reservations) as total_reservations,
                SUM(online_showings) as total_online_showings,
                SUM(offline_showings) as total_offline_showings,
                SUM(repeat_showings) as total_repeat_showings,
                SUM(new_clients) as total_new_clients,
                SUM(cold_calls) as total_cold_calls,
                COUNT(*) as days_reported
            FROM Scores
            WHERE user_id = %s {date_condition}
        """
        
        params = [employee_id] + date_params
        cursor.execute(query, tuple(params))
        stats = cursor.fetchone()
        
        return jsonify({'success': True, 'statistics': stats})
    except Exception as e:
        print(f"Ошибка при получении статистики: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Маршрут для просмотра статистики сотрудника
@leader_bp.route('/employee_statistics/<int:employee_id>')
@login_required
@role_required(['leader', 'deputy'])
def employee_statistics(employee_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, что сотрудник принадлежит отделу текущего руководителя
        cursor.execute(
            """
            SELECT u.*, d.name as department_name
            FROM User u
            JOIN Department d ON u.department = d.id
            JOIN User leader ON u.department = leader.department
            WHERE u.id = %s AND leader.id = %s
            """,
            (employee_id, current_user.id)
        )
        employee = cursor.fetchone()
        
        if not employee:
            flash('Сотрудник не найден или не принадлежит вашему отделу', 'danger')
            return redirect(url_for('leader.my_department'))
        
        # Получаем количество уведомлений
        notifications_count = get_notifications_count()
        
        return render_template(
            'leader/employee_statistics.html',
            employee=employee,
            notifications_count=notifications_count
        )
    except Exception as e:
        print(f"Ошибка при загрузке статистики сотрудника: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('leader.my_department'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Маршрут для временного входа под сотрудником
@leader_bp.route('/impersonate/<int:employee_id>')
@login_required
@role_required(['leader', 'deputy'])
def impersonate_employee(employee_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем, что сотрудник принадлежит отделу текущего руководителя
        cursor.execute(
            """
            SELECT u.id, u.role
            FROM User u
            JOIN User leader ON u.department = leader.department
            WHERE u.id = %s AND leader.id = %s
            """,
            (employee_id, current_user.id)
        )
        employee = cursor.fetchone()
        
        if not employee:
            flash('Сотрудник не найден или не принадлежит вашему отделу', 'danger')
            return redirect(url_for('leader.my_department'))
        
        if employee['role'] in ['leader', 'deputy', 'admin']:
            flash('Нельзя войти под руководителем или администратором', 'danger')
            return redirect(url_for('leader.my_department'))
        
        # Сохраняем текущего пользователя
        session['original_user_id'] = current_user.id
        
        # Входим под сотрудником
        session['id'] = employee_id
        
        flash(f'Вы вошли под сотрудником (ID: {employee_id})', 'success')
        return redirect(url_for('main.index'))
    except Exception as e:
        print(f"Ошибка при входе под сотрудником: {e}")
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return redirect(url_for('leader.my_department'))
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

