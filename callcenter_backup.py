from flask import Blueprint, request, jsonify, render_template, send_file, flash, redirect, url_for, session, current_app
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import requests
import logging
import sys
from colorama import init, Fore, Style
import pandas as pd
from werkzeug.utils import secure_filename
import os
import random
import mysql.connector
from mysql.connector import pooling
import tempfile
import atexit
from functools import wraps
from app.utils import update_operator_status, create_db_connection
from datetime import datetime, timedelta, date
import pytz
import re
from . import callcenter_bp
from app.utils import login_required
from flask_login import login_required as flask_login_required, current_user
import traceback
import threading
import io
import gspread
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLIENT_SECRET_FILE = '/home/LetoBlack/client_secret.json'
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid"
]

user_statuses = {}
user_statuses_lock = threading.Lock()

@socketio.on('connect', namespace='/call_center')
def handle_connect():
    if current_user.is_authenticated:
        user_id = current_user.id
        user_role = get_user_role(user_id)
        if not user_role:
            logger.warning(f"Роль пользователя с ID {user_id} не найдена.")
            return False  # Отключить соединение, если роль не определена
        
        # Проверяем, что пользователь имеет роль callcenter или admin
        if user_role not in ['callcenter', 'admin']:
            logger.info(f"Пользователь с ID {user_id} и ролью {user_role} подключился к call_center без ukc_kc")
            join_room(user_role)
            return True
            
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
        SELECT uk.ukc_kc 
        FROM user_ukc uk 
        WHERE uk.user_id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if user:
            room = user['ukc_kc']
            join_room(room)
            logger.info(f"User {user_id} joined room: {room}")
            with user_statuses_lock:
                user_statuses[user_id] = 'Онлайн'
            emit('user_status_changed', {'user_id': user_id, 'status': 'Онлайн'}, room=room)
        cursor.close()
    else:
        logger.warning("Unauthenticated user attempted to connect to /call_center namespace.")
        return False  # Отключить соединение

@socketio.on('disconnect', namespace='/call_center')
def handle_disconnect():
    if current_user.is_authenticated:
        user_id = current_user.id
        user_role = get_user_role(user_id)
        if not user_role:
            logger.warning(f"Роль пользователя с ID {user_id} не найдена при отключении.")
            return
        leave_room(user_role)
        logger.info(f"User {user_id} left room: {user_role}")
        with user_statuses_lock:
            user_statuses[user_id] = 'Оффлайн'
        emit('user_status_changed', {'user_id': user_id, 'status': 'Оффлайн'}, room=user_role)
    else:
        logger.warning("Unauthenticated user disconnected from /call_center namespace.")

def timedelta_to_time_str(timedelta_obj):
    total_seconds = timedelta_obj.total_seconds()
    hours = int(total_seconds // 3600) % 24
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

@callcenter_bp.route('/call_center_dashboard')
@login_required
def call_center_dashboard():
    # Значения по умолчанию для статистики
    default_stats = {
        'total_operators': 0,
        'active_operators': 0,
        'calls_today': 0,
        'avg_call_duration': '00:00'
    }
    
    # Пустые списки по умолчанию
    default_operators = []
    default_numbers = []
    default_database_records = []

    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Получаем статистику операторов
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_operators,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_operators,
                    SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive_operators
                FROM CallCenterOperators o
                JOIN User u ON o.user_id = u.id
                LEFT JOIN Calls c ON c.number = o.current_phone
                GROUP BY o.id
                ORDER BY o.status DESC, u.full_name
            """)
            operators_stats = cursor.fetchone() or default_stats
        except Exception as e:
            logger.error(f"Ошибка при получении статистики операторов: {str(e)}")
            operators_stats = default_stats

        # Получаем список операторов
        try:
            cursor.execute("""
                SELECT 
                    o.id,
                    u.full_name as name,
                    o.status,
                    COUNT(c.id) as active_calls
                FROM CallCenterOperators o
                JOIN User u ON o.user_id = u.id
                LEFT JOIN Calls c ON c.number = o.current_phone
                GROUP BY o.id
                ORDER BY o.status DESC, u.full_name
            """)
            operators = cursor.fetchall() or default_operators
        except Exception as e:
            logger.error(f"Ошибка при получении списка операторов: {str(e)}")
            operators = default_operators

        # Получаем статистику звонков
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as calls_today,
                    AVG(TIMESTAMPDIFF(SECOND, '00:00:00', time)) as avg_duration
                FROM ScoringKC
                WHERE date = CURDATE()
            """)
            calls_stats = cursor.fetchone() or {'calls_today': 0, 'avg_duration': 0}
        except Exception as e:
            logger.error(f"Ошибка при получении статистики звонков: {str(e)}")
            calls_stats = {'calls_today': 0, 'avg_duration': 0}

        # Получаем список номеров
        try:
            cursor.execute("""
                SELECT 
                    c.id,
                    c.number as phone,
                    'active' as status,
                    u.full_name as operator
                FROM Calls c
                LEFT JOIN User u ON u.id = %s
                ORDER BY c.id DESC
                LIMIT 100
            """, (current_user.id,))
            numbers = cursor.fetchall() or default_numbers
        except Exception as e:
            logger.error(f"Ошибка при получении списка номеров: {str(e)}")
            numbers = default_numbers

        # Получаем записи базы данных - используем ScoringKC
        try:
            cursor.execute("""
                SELECT 
                    s.id,
                    DATE_FORMAT(s.date, '%Y-%m-%d') as date,
                    DATE_FORMAT(s.time, '%H:%i') as time,
                    s.operator as operator_name,
                    u.full_name as client_name,
                    s.status
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                ORDER BY s.date DESC, s.time DESC
                LIMIT 100
            """)
            database_records = cursor.fetchall() or default_database_records
        except Exception as e:
            logger.error(f"Ошибка при получении записей базы данных: {str(e)}")
            database_records = default_database_records

        # Форматируем среднюю длительность звонка
        avg_duration = calls_stats.get('avg_duration', 0) or 0
        minutes = int(avg_duration // 60)
        seconds = int(avg_duration % 60)
        avg_duration_str = f"{minutes:02d}:{seconds:02d}"

        # Формируем словарь статистики
        stats = {
            'total_operators': operators_stats.get('total_operators', 0),
            'active_operators': operators_stats.get('active_operators', 0),
            'calls_today': calls_stats.get('calls_today', 0),
            'avg_call_duration': avg_duration_str
        }

        # Получаем данные о категориях, объектах и источниках
        try:
            cursor.execute("SELECT id, category_name FROM CallCategories WHERE archived = 0 ORDER BY `order`")
            categories = cursor.fetchall() or []
            
            cursor.execute("SELECT id, object_name FROM ObjectKC WHERE archived = 0 ORDER BY `order`")
            objects = cursor.fetchall() or []
            
            cursor.execute("SELECT id, source_name FROM SourceKC WHERE archived = 0 ORDER BY `order`")
            sources = cursor.fetchall() or []
        except Exception as e:
            logger.error(f"Ошибка при получении справочников: {str(e)}")
            categories = []
            objects = []
            sources = []

        return render_template('callcenter/dashboard.html',
                             stats=stats,
                             operators=operators,
                             numbers=numbers,
                             database_records=database_records,
                             categories=categories,
                             objects=objects,
                             sources=sources)

    except Exception as e:
        logger.error(f"Ошибка при загрузке дашборда колл-центра: {str(e)}")
        logger.error(traceback.format_exc())
        flash('Произошла ошибка при загрузке дашборда', 'error')
        return render_template('callcenter/dashboard.html',
                             stats=default_stats,
                             operators=default_operators,
                             numbers=default_numbers,
                             database_records=default_database_records,
                             categories=[],
                             objects=[],
                             sources=[])
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

def current_timeline():
    timezone = pytz.timezone('Europe/Moscow')  # Укажите ваш часовой пояс
    now = datetime.now(timezone)
    hour = now.hour
    weekday = now.weekday()
    if 9 <= hour < 18 and weekday < 5:
        return 'daily'
    else:
        return 'nighty'
    
def get_user_role(user_id):
    """
    Определяет роль пользователя по его ID.
    """
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT role FROM User WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            return user['role']
        else:
            return None
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении роли пользователя: {err}")
        return None
    finally:
        cursor.close()
        connection.close()

@callcenter_bp.route('/get_current_statuses', methods=['GET'])
@login_required
def get_current_statuses():
    room = request.args.get('room')
    if not room:
        return jsonify({'error': 'Комната не указана'}), 400
    statuses = []
    with user_statuses_lock:
        for uid, status in user_statuses.items():
            user_role = get_user_role(uid)
            if user_role == room:
                statuses.append({'user_id': uid, 'status': status})
    return jsonify({'statuses': statuses})

@callcenter_bp.route('/api/fire_operator', methods=['POST'])
@login_required
def fire_operator():
    data = request.form  
    operator_id = data.get('operator_id')
    current_app.logger.info(f"Получен запрос на увольнение оператора с ID: {operator_id}")
    print(f"Получен запрос на увольнение оператора с ID: {operator_id}")
    fire_date = datetime.now().date()  # Получаем текущую дату
    if not operator_id:
        current_app.logger.error("Не указан ID оператора.")
        return jsonify({'success': False, 'message': 'Не указан ID оператора.'})
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE User 
            SET fired = TRUE, fire_date = %s, status = 'Офлайн', Phone = '' 
            WHERE id = %s
        """, (fire_date, operator_id))
        connection.commit()

        current_app.logger.info(f"Оператор с ID {operator_id} успешно уволен")
        print(f"Оператор с ID {operator_id} успешно уволен")
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        connection.rollback()
        current_app.logger.error(f"Ошибка при увольнении оператора: {err}")
        print(f"Ошибка при увольнении оператора: {err}")
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        connection.close()

@callcenter_bp.route('/admin/fired_operators')
@login_required
def show_fired_operators():
    # Проверяем, имеет ли пользователь доступ к этой странице
    if current_user.role not in ['admin', 'callcenter']:
        flash("У вас нет доступа к этой странице", "danger")
        return redirect(url_for('home'))
        
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
    SELECT u.id, u.login, u.full_name, uk.ukc_kc, u.Phone, u.hire_date, u.fire_date 
    FROM User u
    LEFT JOIN user_ukc uk ON u.id = uk.user_id
    WHERE u.role = 'operator' AND u.fired = TRUE
    """)
    fired_operators = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('fired_operators.html', fired_operators=fired_operators)
from flask import jsonify

@callcenter_bp.route('/send_notification', methods=['POST'])
@login_required
def send_notification():
    if current_user.role != 'admin':
        flash("Доступ разрешен только администраторам.", "danger")
        return redirect(url_for('admin_dashboard'))
    message = request.form['notification_message']
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Notifications (message, is_for_operator) VALUES (%s, %s)", (message, True))
        notification_id = cursor.lastrowid
        cursor.execute("SELECT id FROM User WHERE role = 'operator' AND is_active = 1")
        users = cursor.fetchall()
        for user in users:
            cursor.execute(
                "INSERT INTO UserNotifications (user_id, notification_id, is_read) VALUES (%s, %s, %s)",
                (user[0], notification_id, False)
            )
        cursor.execute("SELECT id FROM vats_operators WHERE is_active = 1")
        vats_users = cursor.fetchall()
        for vats_user in vats_users:
            cursor.execute(
                "INSERT INTO VatsUserNotifications (vats_operator_id, notification_id, is_read) VALUES (%s, %s, %s)",
                (vats_user[0], notification_id, False)
            )
        connection.commit()
        flash('Уведомление успешно отправлено операторам.', 'success')
    except mysql.connector.Error as e:
        connection.rollback()
        flash(f'Ошибка при отправке уведомления: {e}', 'danger')
        print(f"Ошибка: {e}")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/get_notifications', methods=['GET'])
@login_required
def get_notifications():
    user_id = session.get('id')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Сначала получаем роль пользователя
        cursor.execute("SELECT role FROM User WHERE id = %s", (user_id,))
        user_role_data = cursor.fetchone()
        
        if not user_role_data:
            return jsonify([])
        
        user_role = user_role_data['role']
        
        # Проверяем роль пользователя
        if user_role in ['callcenter', 'admin']:
            cursor.execute("""
            SELECT uk.ukc_kc 
            FROM user_ukc uk 
            WHERE uk.user_id = %s
            """, (user_id,))
            user = cursor.fetchone()
            if user:
                cursor.execute("""
                    SELECT n.id, n.message, n.created_at, un.is_read
                    FROM Notifications n
                    JOIN UserNotifications un ON n.id = un.notification_id
                    WHERE un.user_id = %s AND n.is_for_operator = TRUE
                    ORDER BY n.created_at DESC
                """, (user_id,))
                notifications = cursor.fetchall()
                return jsonify(notifications)
        
        # Для других ролей получаем уведомления без привязки к ukc_kc
        cursor.execute("""
            SELECT n.id, n.message, n.created_at, un.is_read
            FROM Notifications n
            JOIN UserNotifications un ON n.id = un.notification_id
            WHERE un.user_id = %s
            ORDER BY n.created_at DESC
        """, (user_id,))
        notifications = cursor.fetchall()
        return jsonify(notifications)
    except Exception as e:
        logger.error(f"Ошибка при получении уведомлений: {e}")
        return jsonify([])
    finally:
        cursor.close()
        connection.close()

@callcenter_bp.route('/add_entry', methods=['POST'])
@login_required
def add_entry():
    # Ваш код для обработки формы
    entry_data = [...]  # Данные записи
    sync_with_google_sheets(entry_data)  # Вызов функции синхронизации
    return redirect(url_for('callcenter.call_center_dashboard'))

from gspread.utils import extract_id_from_url

@callcenter_bp.route('/authorize_google')
@login_required
def authorize_google():
    # Настройка Flow
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('callcenter.google_auth_callback', _external=True)
    )
    # Генерация URL авторизации
    auth_url, _ = flow.authorization_url(prompt='consent')
    return redirect(auth_url)

import requests

def convert_value(value):
    if isinstance(value, date):
        return value.isoformat()
    elif isinstance(value, timedelta):
        return str(value)
    return value


def convert_row_partial(row, selected_fields, field_mapping):
    converted_row = {}
    for key in selected_fields:
        if key in row:
            value = row[key]
            if isinstance(value, date):
                converted_row[field_mapping[key]] = value.strftime('%Y-%m-%d')  # Форматирование даты
            elif isinstance(value, timedelta):
                converted_row[field_mapping[key]] = str(value)  # Преобразование timedelta в строку
            else:
                converted_row[field_mapping[key]] = value
    return converted_row


@callcenter_bp.route('/deauthorize_google', methods=['GET'])
@login_required
def deauthorize_google():
    import requests

    # Попробуем отозвать токен, если он есть в базе
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT token FROM GoogleAuth LIMIT 1")
        auth_data = cursor.fetchone()
        if auth_data:
            revoke_url = f"https://accounts.google.com/o/oauth2/revoke?token={auth_data['token']}"
            response = requests.post(revoke_url)
            if response.status_code == 200:
                logger.info("Google токен успешно отозван.")
            else:
                logger.warning(f"Не удалось отозвать токен. Код ответа: {response.status_code}")
        
        # Удаляем записи авторизации из базы данных
        cursor.execute("DELETE FROM GoogleAuth")
        connection.commit()
    except Exception as e:
        logger.error(f"Ошибка при деавторизации: {e}")
        connection.rollback()
    finally:
        cursor.close()
        connection.close()

    # Удаляем все данные, связанные с Google из сессии
    keys_to_remove = [key for key in session.keys() if key.startswith('google_')]
    for key in keys_to_remove:
        session.pop(key, None)
    
    flash('Вы успешно деавторизовались из Google.', 'success')
    return redirect(url_for('callcenter.integrations'))

def refresh_google_credentials():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri="https://black.leto-realty.ru/google_auth_callback"  # Укажите правильный URI
    )
    return flow

@callcenter_bp.route('/sync_data', methods=['POST'])
@login_required
def sync_data():
    import logging
    from datetime import date, timedelta
    import gspread
    from google.oauth2.credentials import Credentials
    import json

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("SyncDataLogger")

    # Словарь для сопоставления имен полей БД и названий столбцов на русском
    field_mapping = {
        'scoring_id': 'ID записи',
        'date': 'Дата',
        'time': 'Время',
        'broker_name': 'Брокер',
        'department_name': 'Отдел',
        'floor_name': 'Группа',
        'object_name': 'Объект',
        'source_name': 'Источник',
        'client_id': 'ID клиента',
        'budget': 'Бюджет',
        'operator': 'Оператор',
        'operator_id': 'ID оператора',
        'status': 'Статус',
        'operator_type': 'Тип оператора'
    }

    # Получаем из тела запроса список выбранных полей
    data = request.get_json()
    selected_fields = data.get('fields', [])
    logger.debug(f"Selected fields: {selected_fields}")

    if not selected_fields:
        return jsonify({'success': False, 'message': 'Не выбрано ни одного поля для выгрузки.'}), 400

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Проверяем наличие авторизационных данных
        if 'google_credentials' not in session:
            logger.debug("Google credentials not found in session, fetching from database.")
            cursor.execute("""
                SELECT token, refresh_token, token_uri, client_id, client_secret, scopes 
                FROM GoogleAuth LIMIT 1
            """)
            google_auth = cursor.fetchone()
            if not google_auth:
                logger.error("Google credentials not found in database.")
                return jsonify({'success': False, 'message': 'Авторизация в Google отсутствует.'}), 400

            # Восстанавливаем токены
            session['google_credentials'] = {
                'token': google_auth['token'],
                'refresh_token': google_auth['refresh_token'],
                'token_uri': google_auth['token_uri'],
                'client_id': google_auth['client_id'],
                'client_secret': google_auth['client_secret'],
                'scopes': google_auth['scopes']
            }

        credentials = Credentials(**session['google_credentials'])
        gc = gspread.authorize(credentials)

        logger.debug("Fetching integration URL from database.")
        cursor.execute("SELECT id, url FROM Integrations WHERE type = 'GoogleSheet' LIMIT 1")
        integration = cursor.fetchone()

        if not integration:
            logger.error("No integration found.")
            return jsonify({'success': False, 'message': 'Синхронизация не настроена.'}), 400

        google_sheet_url = integration['url']
        logger.debug(f"Integration URL: {google_sheet_url}")

        # Сохраняем выбранные поля в базе данных (в поле selected_fields)
        cursor.execute("""
            UPDATE Integrations 
            SET selected_fields = %s
            WHERE id = %s
        """, (json.dumps(selected_fields), integration['id']))
        connection.commit()

        # Получение данных
        logger.debug("Fetching data from ScoringKC table with relations.")
        cursor.execute("""
            SELECT 
                ScoringKC.id AS scoring_id,
                ScoringKC.date,
                ScoringKC.time,
                BrokerUser.full_name AS broker_name,
                ScoringKC.department_id AS department_name,
                CallCategories.category_name AS floor_name,
                ObjectKC.object_name AS object_name,
                SourceKC.source_name AS source_name,
                ScoringKC.client_id,
                ScoringKC.budget,
                ScoringKC.operator,
                ScoringKC.operator_id,
                ScoringKC.status,
                ScoringKC.operator_type
            FROM ScoringKC
            LEFT JOIN User AS BrokerUser ON ScoringKC.broker_id = BrokerUser.id
            LEFT JOIN CallCategories ON ScoringKC.floor_id = CallCategories.id
            LEFT JOIN ObjectKC ON ScoringKC.object_id = ObjectKC.id
            LEFT JOIN SourceKC ON ScoringKC.source_id = SourceKC.id
        """)
        rows = cursor.fetchall()

        if not rows:
            logger.warning("No data found in ScoringKC table.")
            return jsonify({'success': False, 'message': 'Нет данных для синхронизации.'}), 400

        logger.debug(f"Fetched {len(rows)} rows from ScoringKC.")

        # Преобразование данных: формируем список строк, начиная с заголовков
        values = [[field_mapping[f] for f in selected_fields]]  # Заголовки
        for row in rows:
            row_values = []
            for f in selected_fields:
                value = row.get(f)
                if isinstance(value, date):
                    row_values.append(value.isoformat())
                elif isinstance(value, timedelta):
                    row_values.append(str(value))
                else:
                    row_values.append(value)
            values.append(row_values)

        # Обновление Google Таблицы
        sheet = gc.open_by_url(google_sheet_url)
        worksheet = sheet.worksheet("Лист1")
        worksheet.clear()
        worksheet.update('A1', values)

        # Обновляем время последней синхронизации
        cursor.execute("UPDATE Integrations SET last_synced_at = NOW() WHERE type = 'GoogleSheet'")
        connection.commit()
        logger.info("Synchronization completed successfully.")

        return jsonify({'success': True, 'message': 'Синхронизация завершена успешно!'})
    except Exception as e:
        logger.error(f"Error during synchronization: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Ошибка синхронизации: {e}'}), 500
    finally:
        cursor.close()
        connection.close()
        logger.debug("Database connection closed.")

@callcenter_bp.route('/partial_sync_data', methods=['POST'])
def partial_sync_data():  # Убрали @login_required
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("PartialSyncDataLogger")

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        # Проверяем наличие интеграции Google Sheet
        cursor.execute("SELECT url FROM Integrations WHERE type = 'GoogleSheet' LIMIT 1")
        integration = cursor.fetchone()
        if not integration:
            logger.error("No integration found.")
            return jsonify({'success': False, 'message': 'Синхронизация не настроена.'}), 400
        google_sheet_url = integration['url']

        # Проверяем авторизационные данные Google
        cursor.execute("SELECT token, refresh_token, token_uri, client_id, client_secret, scopes FROM GoogleAuth LIMIT 1")
        google_auth = cursor.fetchone()
        if not google_auth:
            logger.error("Google credentials not found in database.")
            return jsonify({'success': False, 'message': 'Авторизация в Google отсутствует.'}), 400

        # Десериализация scopes, если они сохранены в виде JSON-строки
        scopes = google_auth['scopes']
        if isinstance(scopes, str):
            try:
                scopes = json.loads(scopes)
            except json.JSONDecodeError as decode_err:
                logger.error(f"Error decoding scopes: {decode_err}")
                return jsonify({'success': False, 'message': 'Неверный формат scopes.'}), 400

        # Восстанавливаем credentials с корректным списком scopes
        credentials = Credentials(
            token=google_auth['token'],
            refresh_token=google_auth['refresh_token'],
            token_uri=google_auth['token_uri'],
            client_id=google_auth['client_id'],
            client_secret=google_auth['client_secret'],
            scopes=scopes
        )

        # Авторизация в Google
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_url(google_sheet_url)

        worksheet_name = "Лист1"
        try:
            worksheet = sheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=worksheet_name, rows="100", cols="20")

        # Считываем существующие ID из первого столбца
        existing_ids = worksheet.col_values(1)
        if existing_ids and existing_ids[0] == "ID записи":
            existing_ids = existing_ids[1:]

        existing_ids_int = set()
        for val in existing_ids:
            try:
                existing_ids_int.add(int(val))
            except ValueError:
                pass

        max_existing_id = max(existing_ids_int) if existing_ids_int else 0

        # Выборка данных из базы с учетом существующих ID
        sql = """
            SELECT 
                ScoringKC.id AS scoring_id,
                ScoringKC.date,
                ScoringKC.time,
                BrokerUser.full_name AS broker_name,
                ScoringKC.department_id AS department_name,
                CallCategories.category_name AS floor_name,
                ObjectKC.object_name AS object_name,
                SourceKC.source_name AS source_name,
                ScoringKC.client_id,
                ScoringKC.budget,
                ScoringKC.operator,
                ScoringKC.operator_id,
                ScoringKC.status,
                ScoringKC.operator_type
            FROM ScoringKC
            LEFT JOIN User AS BrokerUser ON ScoringKC.broker_id = BrokerUser.id
            LEFT JOIN CallCategories ON ScoringKC.floor_id = CallCategories.id
            LEFT JOIN ObjectKC ON ScoringKC.object_id = ObjectKC.id
            LEFT JOIN SourceKC ON ScoringKC.source_id = SourceKC.id
            WHERE ScoringKC.id > %s
            ORDER BY ScoringKC.id
        """
        cursor.execute(sql, (max_existing_id,))
        rows = cursor.fetchall()
        if not rows:
            logger.info("No new data to sync.")
            return jsonify({'success': True, 'message': 'Нет новых данных для синхронизации.'})

        selected_fields = [
            'scoring_id', 'date', 'time', 'broker_name', 'department_name', 'floor_name',
            'object_name', 'source_name', 'client_id', 'budget', 'operator', 'operator_id',
            'status', 'operator_type'
        ]
        field_mapping = {
            'scoring_id': 'ID записи',
            'date': 'Дата',
            'time': 'Время',
            'broker_name': 'Брокер',
            'department_name': 'Отдел',
            'floor_name': 'Группа',
            'object_name': 'Объект',
            'source_name': 'Источник',
            'client_id': 'ID клиента',
            'budget': 'Бюджет',
            'operator': 'Оператор',
            'operator_id': 'ID оператора',
            'status': 'Статус',
            'operator_type': 'Тип оператора'
        }

        # Добавляем заголовки, если лист пустой
        existing_data = worksheet.get_all_values()
        if not existing_data:
            header = [field_mapping[f] for f in selected_fields]
            worksheet.append_row(header, value_input_option='USER_ENTERED')

        # Формируем строки для добавления в Google Sheets
        new_values = []
        for row in rows:
            row_values = [convert_value(row[f]) for f in selected_fields]  # Применяем конвертер
            new_values.append(row_values)

        # Добавляем новые строки
        worksheet.append_rows(new_values, value_input_option='USER_ENTERED')
        logger.info(f"✅ Добавлено {len(new_values)} новых строк в Google Sheets.")

        # Обновляем время последней синхронизации
        try:
            cursor.execute("UPDATE Integrations SET last_synced_at = NOW() WHERE type = 'GoogleSheet'")
            connection.commit()
            logger.info("Last sync time updated.")
        except Exception as e:
            logger.error(f"Error updating last sync time: {e}", exc_info=True)

        return jsonify({'success': True, 'message': 'Синхронизация завершена успешно!'})
    except Exception as e:
        logger.error(f"Error in partial sync: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Ошибка синхронизации: {e}'}), 500
    finally:
        cursor.close()
        connection.close()
        logger.debug("Database connection closed.")
        
@callcenter_bp.route('/delete_sync', methods=['POST'])
@login_required
def delete_sync():
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM Integrations WHERE type = 'GoogleSheet'")
        connection.commit()
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        connection.close()

@callcenter_bp.route('/get_operator_status', methods=['GET'])
@login_required
def get_operator_status():
    user_id = session.get('id')
    if not user_id:
        return jsonify({'error': 'Пользователь не авторизован.'}), 401
    user_role = get_user_role(user_id)
    if not user_role:
        return jsonify({'error': 'Роль пользователя не определена.'}), 400
    with user_statuses_lock:
        status = user_statuses.get(user_id, 'Оффлайн')
    today = date.today()
    try:
        connection = create_db_connection()
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT status 
                FROM User 
                WHERE id = %s
            """, (user_id,))
            user = cursor.fetchone()
            cursor.execute("""
                SELECT active_time 
                FROM OperatorActivity
                WHERE operator_id = %s AND date = %s
            """, (user_id, today))
            activity = cursor.fetchone()
        connection.close()
        if activity:
            active_time_today = activity['active_time']
        else:
            active_time_today = 0
        return jsonify({
            'operator': {
                'id': user_id,
                'status': status,
                'active_time_today': active_time_today
            }
        }), 200
    except mysql.connector.Error as err:
        current_app.logger.error(f"Database error in get_operator_status: {err}")
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in get_operator_status: {e}")
        return jsonify({'error': 'Unexpected error'}), 500

@callcenter_bp.route('/operator_dashboard')
@login_required
def operator_dashboard():
    connection = None
    cursor = None
    
    try:
        user_id = current_user.id  
        user_role = current_user.role
        
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем статус оператора из CallCenterOperators
        cursor.execute("""
            SELECT status 
            FROM CallCenterOperators 
            WHERE user_id = %s
        """, (user_id,))
        operator_status = cursor.fetchone()
        
        # Если пользователь не является оператором КЦ, проверяем статус из User
        if not operator_status:
            cursor.execute("""
                SELECT status 
                FROM User
                WHERE id = %s
            """, (user_id,))
            operator_status = cursor.fetchone()
        
        status = operator_status['status'] if operator_status else 'inactive'
        
        # Получаем все активные уведомления для пользователя
        cursor.execute("""
            SELECT n.id, n.message, un.is_read
            FROM Notifications n
            JOIN UserNotifications un ON n.id = un.notification_id
            WHERE un.user_id = %s AND (n.is_for_operator = TRUE OR %s)
            ORDER BY n.created_at DESC
        """, (user_id, user_role == 'admin'))
        notifications = cursor.fetchall()
        
        # Получаем данные для таблицы
        if user_role == 'admin':
            query = """
                SELECT ScoringKC.id AS scoring_id, ScoringKC.date, ScoringKC.time, BrokerUser.full_name AS broker_name, 
                       ScoringKC.department_id, CallCategories.category_name AS floor_name, 
                       ObjectKC.object_name AS object_name, SourceKC.source_name AS source_name, 
                       ScoringKC.client_id, ScoringKC.operator, ScoringKC.operator_id
                FROM ScoringKC
                JOIN User AS BrokerUser ON ScoringKC.broker_id = BrokerUser.id
                JOIN CallCategories ON ScoringKC.floor_id = CallCategories.id
                JOIN ObjectKC ON ScoringKC.object_id = ObjectKC.id
                JOIN SourceKC ON ScoringKC.source_id = SourceKC.id
                ORDER BY ScoringKC.date DESC, ScoringKC.time DESC
            """
            params = ()
            logger.info("Admin user. Fetching all entries.")
            cursor.execute(query, params)
            entries = cursor.fetchall()
        else:
            # Для обычного оператора - только его записи
            query = """
                SELECT ScoringKC.id AS scoring_id, ScoringKC.date, ScoringKC.time, BrokerUser.full_name AS broker_name, 
                       ScoringKC.department_id, CallCategories.category_name AS floor_name, 
                       ObjectKC.object_name AS object_name, SourceKC.source_name AS source_name, 
                       ScoringKC.client_id, ScoringKC.operator, ScoringKC.operator_id
                FROM ScoringKC
                JOIN User AS BrokerUser ON ScoringKC.broker_id = BrokerUser.id
                JOIN CallCategories ON ScoringKC.floor_id = CallCategories.id
                JOIN ObjectKC ON ScoringKC.object_id = ObjectKC.id
                JOIN SourceKC ON ScoringKC.source_id = SourceKC.id
                WHERE ScoringKC.operator_id = %s
                ORDER BY ScoringKC.date DESC, ScoringKC.time DESC
            """
            params = (user_id,)
            logger.info(f"Regular user {user_id}. Fetching user's entries.")
            cursor.execute(query, params)
            entries = cursor.fetchall()
        
        # Получаем список групп (категорий)
        cursor.execute("SELECT id, category_name FROM CallCategories WHERE archived = 0 ORDER BY `order`")
        categories = cursor.fetchall()
        
        # Получаем список объектов
        cursor.execute("SELECT id, object_name FROM ObjectKC WHERE archived = 0 ORDER BY `order`")
        objects = cursor.fetchall()
        
        # Получаем список источников
        cursor.execute("SELECT id, source_name FROM SourceKC WHERE archived = 0 ORDER BY `order`")
        sources = cursor.fetchall()
        
        # Получаем список брокеров для селекта
        cursor.execute("""
            SELECT id, full_name 
            FROM User 
            WHERE role = 'broker' AND active = 1
            ORDER BY full_name
        """)
        brokers = cursor.fetchall()
        
        # Получаем список отделов
        cursor.execute("SELECT id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()
        
        # Проверяем, есть ли пользователь в черном списке
        cursor.execute("SELECT id FROM Blacklist WHERE user_id = %s", (user_id,))
        is_in_blacklist = cursor.fetchone() is not None
        
        return render_template(
            'operator_dashboard.html',
            status=status,
            notifications=notifications,
            entries=entries,
            categories=categories,
            objects=objects,
            sources=sources,
            brokers=brokers,
            departments=departments,
            is_in_blacklist=is_in_blacklist
        )
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке панели оператора: {str(e)}")
        logger.error(traceback.format_exc())
        flash('Произошла ошибка при загрузке данных', 'error')
        return render_template(
            'operator_dashboard.html',
            status='inactive',
            notifications=[],
            entries=[],
            categories=[],
            objects=[],
            sources=[],
            brokers=[],
            departments=[],
            is_in_blacklist=False
        )
        
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@callcenter_bp.route('/toggle_status', methods=['POST'])
@login_required
def toggle_status():
    operator_id = session.get('id')
    if not operator_id:
        return jsonify({'success': False, 'message': 'Пользователь не авторизован.'}), 401
    with user_statuses_lock:
        current_status = user_statuses.get(operator_id, 'Оффлайн')
        new_status = 'Онлайн' if current_status == 'Оффлайн' else 'Оффлайн'
        user_statuses[operator_id] = new_status
    user_role = get_user_role(operator_id)
    if not user_role:
        return jsonify({'success': False, 'message': 'Роль пользователя не определена.'}), 400
    socketio.emit(
        'status_update',
        {'operator_id': operator_id, 'new_status': new_status},
        room=user_role,
        namespace='/call_center'
    )
    return jsonify({'success': True, 'new_status': new_status})

@callcenter_bp.route('/get_all_operators_status', methods=['GET'])
@login_required
def get_all_operators_status():
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, status FROM User WHERE role = 'operator'
        """)
        operators = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify(operators)
    except mysql.connector.Error as err:
        current_app.logger.error(f"Database error: {err}")
        return jsonify({'error': 'Database error'}), 500

@callcenter_bp.route('/heartbeat', methods=['POST'])
@login_required
def heartbeat():
    if current_user.role != 'operator':
        return jsonify({'error': 'Access denied'}), 403
    user_id = session.get('id')
    today = date.today()
    now = datetime.now()
    try:
        connection = create_db_connection()
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT active_time, last_active 
                FROM OperatorActivity
                WHERE operator_id = %s AND date = %s
            """, (user_id, today))
            result = cursor.fetchone()
            if result:
                last_active = result['last_active']
                active_time_today = result['active_time']
                if last_active is not None:
                    delta = (now - last_active).total_seconds()
                    if delta < 0:
                        delta = 0
                    cursor.execute("""
                        UPDATE OperatorActivity
                        SET active_time = active_time + %s, last_active = %s
                        WHERE operator_id = %s AND date = %s
                    """, (int(delta), now, user_id, today))
            else:
                cursor.execute("""
                    INSERT INTO OperatorActivity (operator_id, date, active_time, last_active)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, today, 60, now))
        connection.commit()
        with user_statuses_lock:
            user_statuses[user_id] = 'Онлайн'
        user_role = get_user_role(user_id)
        if user_role:
            socketio.emit(
                'user_status_changed',
                {'user_id': user_id, 'status': 'Онлайн'},
                room=user_role,
                namespace='/call_center'
            )
        update_operator_status(user_id, 'Онлайн')
        return jsonify({'status': 'success'}), 200
    except mysql.connector.Error as err:
        current_app.logger.error(f"Database error in heartbeat: {err}")
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in heartbeat: {e}")
        return jsonify({'error': 'Unexpected error'}), 500
    finally:
        connection.close()

@callcenter_bp.route('/get_transfer_clients', methods=['GET'])
@flask_login_required
def get_transfer_clients():
    user_id = session.get('id')
    user_role = session.get('role')
    
    if user_role not in ['КЦ', 'УКЦ']:
        return jsonify({"success": False, "message": "Недостаточно прав."}), 403
    
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT ukc_kc FROM User WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "Пользователь не найден."}), 404
        operator_type = user['ukc_kc']
        cursor.execute("""
            SELECT 
                ScoringKC.id AS scoring_id,
                ScoringKC.date,
                ScoringKC.time,
                User.full_name AS broker_name,
                CallCategories.category_name AS floor_name,
                ObjectKC.object_name AS object_name,
                SourceKC.source_name AS source_name,
                ScoringKC.client_id,
                ScoringKC.operator,
                ScoringKC.operator_id
            FROM 
                ScoringKC
            JOIN 
                User ON ScoringKC.broker_id = User.id
            JOIN 
                CallCategories ON ScoringKC.floor_id = CallCategories.id
            LEFT JOIN 
                ObjectKC ON ScoringKC.object_id = ObjectKC.id
            LEFT JOIN 
                SourceKC ON ScoringKC.source_id = SourceKC.id
            WHERE 
                ScoringKC.status = 'transferred' AND  -- Предполагается, что статус 'transferred' обозначает переданного клиента
                ScoringKC.operator_type = %s
            ORDER BY 
                ScoringKC.date DESC, ScoringKC.time DESC
        """, (operator_type,))
        transferred_clients = cursor.fetchall()
        return jsonify({
            "success": True,
            "transferred_clients": transferred_clients
        }), 200
    except mysql.connector.Error as err:
        current_app.logger.error(f"Ошибка при получении переданных клиентов: {err}")
        return jsonify({"success": False, "message": "Ошибка при получении данных."}), 500
    finally:
        cursor.close()
        connection.close()

@callcenter_bp.route('/integrations', methods=['GET', 'POST'])
@login_required
def integrations():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    if request.method == 'POST':
        # Получаем URL из формы
        google_sheet_url = request.form.get('google_sheet_url')
        if google_sheet_url:
            try:
                # Обновляем или добавляем запись
                cursor.execute("SELECT * FROM Integrations WHERE type = 'GoogleSheet' LIMIT 1")
                integration = cursor.fetchone()
                if integration:
                    cursor.execute(
                        "UPDATE Integrations SET url = %s, last_synced_at = NULL WHERE id = %s",
                        (google_sheet_url, integration['id'])
                    )
                else:
                    cursor.execute(
                        "INSERT INTO Integrations (type, url) VALUES ('GoogleSheet', %s)",
                        (google_sheet_url,)
                    )
                connection.commit()
                flash('Ссылка на Google Таблицу сохранена.', 'success')
            except Exception as e:
                connection.rollback()
                logger.error(f"Error saving integration: {e}", exc_info=True)
                flash('Ошибка сохранения интеграции.', 'danger')

    # Проверяем авторизацию
    cursor.execute("SELECT * FROM GoogleAuth LIMIT 1")
    google_auth = cursor.fetchone()

    # Проверяем URL и время последней синхронизации
    cursor.execute("SELECT url, last_synced_at FROM Integrations WHERE type = 'GoogleSheet' LIMIT 1")
    integration = cursor.fetchone()
    sync_url = integration['url'] if integration else None
    last_synced_at = integration['last_synced_at'] if integration else None

    cursor.close()
    connection.close()

    return render_template(
        'integrations.html',
        google_auth=google_auth,
        sync_url=sync_url,
        last_synced_at=last_synced_at
    )


@callcenter_bp.route('/google_auth_callback')
@login_required
def google_auth_callback():
    import json
    import requests
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('callcenter.google_auth_callback', _external=True)
    )

    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        # Извлечение информации о пользователе из id_token
        user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {credentials.token}"}
        user_info_response = requests.get(user_info_url, headers=headers)
        user_info = user_info_response.json()

        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute("SELECT id FROM GoogleAuth LIMIT 1")
            existing_auth = cursor.fetchone()

            if existing_auth:
                cursor.execute("""
                    UPDATE GoogleAuth
                    SET token=%s, refresh_token=%s, token_uri=%s, client_id=%s, client_secret=%s, scopes=%s, created_at=NOW(), user_email=%s
                    WHERE id=%s
                """, (
                    credentials.token,
                    credentials.refresh_token,
                    credentials.token_uri,
                    credentials.client_id,
                    credentials.client_secret,
                    json.dumps(credentials.scopes),
                    user_info.get("email"),
                    existing_auth['id']
                ))
            else:
                cursor.execute("""
                    INSERT INTO GoogleAuth (token, refresh_token, token_uri, client_id, client_secret, scopes, user_email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    credentials.token,
                    credentials.refresh_token,
                    credentials.token_uri,
                    credentials.client_id,
                    credentials.client_secret,
                    json.dumps(credentials.scopes),
                    user_info.get("email")
                ))
            connection.commit()
        except Exception as e:
            logger.error(f"Error saving Google credentials: {e}", exc_info=True)
            connection.rollback()
            flash('Ошибка сохранения данных авторизации.', 'danger')
        finally:
            cursor.close()
            connection.close()

        # Обновляем данные сессии
        session['google_user_info'] = {
            'email': user_info.get("email"),
            'name': user_info.get("name"),
            'picture': user_info.get("picture")
        }

        # Сохраняем credentials в сессии
        session['google_credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        flash('Вы успешно авторизовались в Google.', 'success')
    except Exception as e:
        logger.error(f"Ошибка при авторизации Google: {e}", exc_info=True)
        flash('Ошибка авторизации Google.', 'danger')

    return redirect(url_for('callcenter.integrations'))


@callcenter_bp.before_request
def before_request():
    exempt_endpoints = ['login', 'static']
    current_endpoint = request.endpoint
    if any(current_endpoint.startswith(endpoint) for endpoint in exempt_endpoints):
        return
    if 'id' in session and session.get('role') == 'operator':
        user_id = session['id']
        today = date.today()
        now = datetime.now()
        try:
            connection = create_db_connection()
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT active_time, last_active 
                    FROM OperatorActivity
                    WHERE operator_id = %s AND date = %s
                """, (user_id, today))
                result = cursor.fetchone()
                if result:
                    last_active = result['last_active']
                    active_time_today = result['active_time']
                    if last_active is not None:
                        delta = (now - last_active).total_seconds()
                        if delta < 0:
                            delta = 0
                        cursor.execute("""
                            UPDATE OperatorActivity
                            SET active_time = active_time + %s, last_active = %s
                            WHERE operator_id = %s AND date = %s
                        """, (int(delta), now, user_id, today))
                else:
                    cursor.execute("""
                        INSERT INTO OperatorActivity (operator_id, date, active_time, last_active)
                        VALUES (%s, %s, %s, %s)
                    """, (user_id, today, 60, now))
                connection.commit()
            connection.close()
            # Обновление статуса пользователя на 'Онлайн'
            with user_statuses_lock:
                user_statuses[user_id] = 'Онлайн'
            # Эмитим событие об изменении статуса
            user_role = get_user_role(user_id)
            if user_role:
                socketio.emit(
                    'user_status_changed',
                    {'user_id': user_id, 'status': 'Онлайн'},
                    room=user_role,
                    namespace='/call_center'
                )
        except mysql.connector.Error as err:
            current_app.logger.error(f"Database error in before_request: {err}")
        except Exception as e:
            current_app.logger.error(f"Unexpected error in before_request: {e}")
        finally:
            if connection and connection.is_connected():
                connection.close()

@callcenter_bp.route('/report_dashboard')
@login_required
def report_dashboard():
    try:
        report_type = request.args.get('type', 'daily')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
    
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем данные согласно типу отчета
        if report_type == 'daily':
            report_title = 'Отчет за сегодня'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE s.date = CURDATE()
                ORDER BY s.time DESC
            """
            params = ()
        
        elif report_type == 'monthly':
            report_title = 'Отчет за текущий месяц'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE MONTH(s.date) = MONTH(CURDATE()) 
                  AND YEAR(s.date) = YEAR(CURDATE())
                ORDER BY s.date DESC, s.time DESC
            """
            params = ()
        
        elif report_type == 'yearly':
            report_title = 'Отчет за текущий год'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE YEAR(s.date) = YEAR(CURDATE())
                ORDER BY s.date DESC, s.time DESC
            """
            params = ()
        
        elif report_type == 'custom' and start_date and end_date:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            report_title = f'Отчет с {start_date} по {end_date}'
            query = """
                SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE s.date BETWEEN %s AND %s
                ORDER BY s.date DESC, s.time DESC
            """
            params = (start_date_obj, end_date_obj)
        
        else:
            report_title = 'Отчет за сегодня'
            query = """
            SELECT 
                    s.id, 
                    s.date, 
                    s.time, 
                    u.full_name AS broker_name,
                    s.department_id, 
                    c.category_name AS floor_name,
                    o.object_name, 
                    src.source_name, 
                    s.client_id, 
                    s.operator
                FROM ScoringKC s
                JOIN User u ON s.broker_id = u.id
                JOIN CallCategories c ON s.floor_id = c.id
                JOIN ObjectKC o ON s.object_id = o.id
                JOIN SourceKC src ON s.source_id = src.id
                WHERE s.date = CURDATE()
                ORDER BY s.time DESC
            """
            params = ()
        
        cursor.execute(query, params)
        entries = cursor.fetchall()
        
        # Получаем общие данные (категории, объекты, источники)
    common_data = get_common_data()
    
    if report_type == "custom":
        return render_template(
            'report_dashboard.html',
            entries=entries,
            report_title=report_title,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            **common_data
        )
    else:
        return render_template(
            'report_dashboard.html',
            entries=entries,
            report_title=report_title,
            report_type=report_type,
            **common_data
        )
        
    except Exception as e:
        logger.error(f"Ошибка при формировании отчета: {str(e)}")
        logger.error(traceback.format_exc())
        flash('Произошла ошибка при формировании отчета', 'error')
        return render_template(
            'report_dashboard.html',
            entries=[],
            report_title='Ошибка',
            report_type='daily'
        )
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

@callcenter_bp.route('/api/leads/yearly', methods=['GET'])
@login_required
def get_yearly_leads():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    first_day_of_year = datetime.now().replace(month=1, day=1)
    today = datetime.now()

    cursor.execute('''
        SELECT DATE(date) AS date, COUNT(*) AS count
        FROM ScoringKC
        WHERE date BETWEEN %s AND %s
        GROUP BY DATE(date)
        ORDER BY DATE(date)
    ''', (first_day_of_year, today))
    results = cursor.fetchall()
    labels = [result['date'].strftime('%Y-%m-%d') for result in results]
    values = [result['count'] for result in results]
    cursor.close()
    connection.close()
    return jsonify({'labels': labels, 'values': values})

@callcenter_bp.route('/api/leads/monthly', methods=['GET'])
@login_required
def get_monthly_leads():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    first_day_of_month = datetime.now().replace(day=1)
    today = datetime.now()
    cursor.execute('''
        SELECT DATE(date) AS date, COUNT(*) AS count
        FROM ScoringKC
        WHERE date BETWEEN %s AND %s
        GROUP BY DATE(date)
        ORDER BY DATE(date)
    ''', (first_day_of_month, today))
    results = cursor.fetchall()
    labels = [result['date'].strftime('%d') for result in results]
    values = [result['count'] for result in results]
    cursor.close()
    connection.close()
    return jsonify({'labels': labels, 'values': values})

@callcenter_bp.route('/api/leads/daily', methods=['GET'])
@login_required
def get_daily_leads():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    today = datetime.now().date()
    cursor.execute('''
        SELECT HOUR(time) AS hour, MINUTE(time) DIV 5 AS interval_5min, COUNT(*) AS count
        FROM ScoringKC
        WHERE date = %s
        GROUP BY HOUR(time), MINUTE(time) DIV 5
        ORDER BY HOUR(time), MINUTE(time) DIV 5
    ''', (today,))
    results = cursor.fetchall()
    labels = [f"{result['hour']:02d}:{result['interval_5min']*5:02d}" for result in results]
    values = [result['count'] for result in results]
    cursor.close()
    connection.close()
    return jsonify({'labels': labels, 'values': values})

def get_common_data():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Получаем категории
        cursor.execute("SELECT id, category_name FROM CallCategories WHERE archived = 0 ORDER BY `order`")
        categories = cursor.fetchall()
        
        # Получаем объекты
        cursor.execute("SELECT id, object_name FROM ObjectKC WHERE archived = 0 ORDER BY `order`")
        objects = cursor.fetchall()
        
        # Получаем источники
        cursor.execute("SELECT id, source_name FROM SourceKC WHERE archived = 0 ORDER BY `order`")
        sources = cursor.fetchall()
        
        # Получаем операторов
        cursor.execute("""
            SELECT u.id, u.full_name, c.status 
            FROM User u
            LEFT JOIN CallCenterOperators c ON u.id = c.user_id
            WHERE u.role = 'operator' AND u.active = 1
            ORDER BY u.full_name
        """)
    operators = cursor.fetchall()
        
        # Получаем брокеров
        cursor.execute("""
            SELECT id, full_name 
            FROM User 
            WHERE role = 'broker' AND active = 1
            ORDER BY full_name
        """)
    brokers = cursor.fetchall()
        
        # Получаем отделы
        cursor.execute("SELECT id, name FROM Department ORDER BY name")
    departments = cursor.fetchall()
        
    return {
            'categories': categories,
            'objects': objects,
            'sources': sources,
        'operators': operators,
        'brokers': brokers,
            'departments': departments
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении общих данных: {str(e)}")
        return {
            'categories': [],
            'objects': [],
            'sources': [],
            'operators': [],
            'brokers': [],
            'departments': []
        }
        
    finally:
        cursor.close()
        connection.close()

@callcenter_bp.route('/report_by_day')
@login_required
def report_by_day():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT 
            ScoringKC.id, 
            ScoringKC.date, 
            ScoringKC.time,
            broker.full_name AS broker_name,
            ScoringKC.department_id,
            CallCategories.category_name AS floor_name,
            ObjectKC.object_name AS object_name,
            SourceKC.source_name AS source_name,
            ScoringKC.client_id,
            operator.full_name AS operator_name,
            operator.ukc_kc
        FROM 
            ScoringKC
        LEFT JOIN 
            User AS broker ON ScoringKC.broker_id = broker.id
        LEFT JOIN 
            User AS operator ON ScoringKC.operator_id = operator.id
        LEFT JOIN 
            CallCategories ON ScoringKC.floor_id = CallCategories.id
        LEFT JOIN 
            ObjectKC ON ScoringKC.object_id = ObjectKC.id
        LEFT JOIN 
            SourceKC ON ScoringKC.source_id = SourceKC.id
        WHERE 
            ScoringKC.date = %s
        ORDER BY 
            ScoringKC.date DESC, ScoringKC.time DESC
    ''', (today,))
    
    entries = cursor.fetchall()
    common_data = get_common_data()
    cursor.close()
    connection.close()
    report_title = "Отчет за день"
    report_type = "day"
    return render_template('report_dashboard.html', entries=entries, report_title=report_title, report_type=report_type, **common_data)

@callcenter_bp.route('/report_by_month')
@login_required
def report_by_month():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    first_day_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT 
            ScoringKC.id, 
            ScoringKC.date, 
            ScoringKC.time,
            broker.full_name AS broker_name,
            ScoringKC.department_id,
            CallCategories.category_name AS floor_name,
            ObjectKC.object_name AS object_name,
            SourceKC.source_name AS source_name,
            ScoringKC.client_id,
            operator.full_name AS operator_name,
            operator.ukc_kc
        FROM 
            ScoringKC
        LEFT JOIN 
            User AS broker ON ScoringKC.broker_id = broker.id
        LEFT JOIN 
            User AS operator ON ScoringKC.operator_id = operator.id
        LEFT JOIN 
            CallCategories ON ScoringKC.floor_id = CallCategories.id
        LEFT JOIN 
            ObjectKC ON ScoringKC.object_id = ObjectKC.id
        LEFT JOIN 
            SourceKC ON ScoringKC.source_id = SourceKC.id
        WHERE 
            ScoringKC.date BETWEEN %s AND %s
        ORDER BY 
            ScoringKC.date DESC, ScoringKC.time DESC
    ''', (first_day_of_month, today))
    
    entries = cursor.fetchall()
    common_data = get_common_data()
    cursor.close()
    connection.close()
    report_title = "Отчет за месяц"
    report_type = "month"
    return render_template('report_dashboard.html', entries=entries, report_title=report_title, report_type=report_type, **common_data)

@callcenter_bp.route('/report_by_year')
@login_required
def report_by_year():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    first_day_of_year = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT 
            ScoringKC.id, 
            ScoringKC.date, 
            ScoringKC.time,
            broker.full_name AS broker_name,
            ScoringKC.department_id,
            c.category_name AS floor_name,
            o.object_name, 
            src.source_name, 
            s.client_id, 
            s.operator
        FROM ScoringKC s
        JOIN User u ON s.broker_id = u.id
        JOIN CallCategories c ON s.floor_id = c.id
        JOIN ObjectKC o ON s.object_id = o.id
        JOIN SourceKC src ON s.source_id = src.id
        WHERE YEAR(s.date) = YEAR(CURDATE())
        ORDER BY s.date DESC, s.time DESC
    ''', (first_day_of_year, today))
    
    entries = cursor.fetchall()
    common_data = get_common_data()
    cursor.close()
    connection.close()
    report_title = "Отчет за год"
    report_type = "year"
    return render_template('report_dashboard.html', entries=entries, report_title=report_title, report_type=report_type, **common_data)

@callcenter_bp.route('/report_custom', methods=['POST'])
@login_required
def report_custom():
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    if not start_date or not end_date:
        flash("Пожалуйста, выберите оба периода.")
        return redirect(url_for('report_dashboard'))
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('''
        SELECT 
            ScoringKC.id, 
            ScoringKC.date, 
            ScoringKC.time,
            broker.full_name AS broker_name,
            ScoringKC.department_id,
            CallCategories.category_name AS floor_name,
            ObjectKC.object_name AS object_name,
            SourceKC.source_name AS source_name,
            ScoringKC.client_id,
            operator.full_name AS operator_name,
            operator.ukc_kc
        FROM 
            ScoringKC
        LEFT JOIN 
            User AS broker ON ScoringKC.broker_id = broker.id
        LEFT JOIN 
            User AS operator ON ScoringKC.operator_id = operator.id
        LEFT JOIN 
            CallCategories ON ScoringKC.floor_id = CallCategories.id
        LEFT JOIN 
            ObjectKC ON ScoringKC.object_id = ObjectKC.id
        LEFT JOIN 
            SourceKC ON ScoringKC.source_id = SourceKC.id
        WHERE 
            ScoringKC.date BETWEEN %s AND %s
        ORDER BY 
            ScoringKC.date DESC, ScoringKC.time DESC
    ''', (start_date, end_date))
    
    entries = cursor.fetchall()
    common_data = get_common_data()
    cursor.close()
    connection.close()
    report_title = f"Отчет за период {start_date} - {end_date}"
    report_type = "custom"
    return render_template('report_dashboard.html', entries=entries, report_title=report_title, report_type=report_type, start_date=start_date, end_date=end_date, **common_data)

@callcenter_bp.route('/export_excel')
@login_required
def export_excel():
    report_type = request.args.get('report_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not report_type:
        flash("Неверный тип отчета.")
        return redirect(url_for('report_dashboard'))
    if report_type == "year":
        first_day = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
        last_day = datetime.now().strftime('%Y-%m-%d')
        sheet_name = "Отчет за год"
    elif report_type == "month":
        first_day = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        last_day = datetime.now().strftime('%Y-%m-%d')
        sheet_name = "Отчет за месяц"
    elif report_type == "day":
        first_day = datetime.now().strftime('%Y-%m-%d')
        last_day = first_day
        sheet_name = "Отчет за день"
    elif report_type == "custom":
        if not start_date or not end_date:
            flash("Пожалуйста, укажите начальную и конечную даты для отчета.")
            return redirect(url_for('report_dashboard'))
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(date_pattern, start_date) or not re.match(date_pattern, end_date):
            flash("Неверный формат дат. Используйте YYYY-MM-DD.")
            return redirect(url_for('report_dashboard'))
        first_day = start_date
        last_day = end_date
        sheet_name = f"Отчет за период {start_date} - {end_date}"
    else:
        flash("Неверный тип отчета.")
        return redirect(url_for('report_dashboard'))
    sheet_name = sanitize_sheet_name(sheet_name)
    
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('''
            SELECT 
                ScoringKC.id, 
                ScoringKC.date, 
                ScoringKC.time,
                broker.full_name AS broker_name,
                ScoringKC.department_id,
                CallCategories.category_name AS floor_name,
                ObjectKC.object_name AS object_name,
                SourceKC.source_name AS source_name,
                ScoringKC.client_id,
                operator.full_name AS operator_name,
                operator.ukc_kc
            FROM 
                ScoringKC
            LEFT JOIN 
                User AS broker ON ScoringKC.broker_id = broker.id
            LEFT JOIN 
                User AS operator ON ScoringKC.operator_id = operator.id
            LEFT JOIN 
                CallCategories ON ScoringKC.floor_id = CallCategories.id
            LEFT JOIN 
                ObjectKC ON ScoringKC.object_id = ObjectKC.id
            LEFT JOIN 
                SourceKC ON ScoringKC.source_id = SourceKC.id
            WHERE 
                ScoringKC.date BETWEEN %s AND %s
            ORDER BY 
                ScoringKC.date DESC, ScoringKC.time DESC
        ''', (first_day, last_day))
        
        entries = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        current_app.logger.error(f"Ошибка при выполнении SQL-запроса: {err}")
        flash("Ошибка при получении данных из базы данных.", "danger")
        return redirect(url_for('report_dashboard'))
    finally:
        cursor.close()
        connection.close()
    if not entries:
        flash("Нет данных для экспорта в выбранный период.", "info")
        return redirect(url_for('report_dashboard'))
    df = pd.DataFrame(entries)
    df.rename(columns={
        'id': 'ID',
        'date': 'Дата',
        'time': 'Время',
        'broker_name': 'Брокер',
        'department_id': 'Отдел',
        'floor_name': 'Группа',
        'object_name': 'Объект',
        'source_name': 'Источник',
        'client_id': 'ID Клиента',
        'operator_name': 'Оператор',
        'ukc_kc': 'УКЦ/КЦ'
    }, inplace=True)
    if 'Время' in df.columns:
        df['Время'] = df['Время'].astype(str).str.replace('0 days ', '')
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    filename = f"{sheet_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output, 
        download_name=filename, 
        as_attachment=True, 
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@callcenter_bp.route('/delete_entry/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT operator_id FROM ScoringKC WHERE id = %s", (entry_id,))
        entry = cursor.fetchone()
        if not entry:
            flash('Запись не найдена.', 'danger')
            return jsonify({'status': 'error', 'message': 'Запись не найдена.'}), 404
        user_role = session.get('role')
        user_id = session.get('id')
        if user_role != 'admin' and entry['operator_id'] != user_id:
            flash('У вас нет прав для удаления этой записи.', 'danger')
            return jsonify({'status': 'error', 'message': 'У вас нет прав для удаления этой записи.'}), 403
        cursor.execute("DELETE FROM ScoringKC WHERE id = %s", (entry_id,))
        connection.commit()
        current_app.logger.info(f"Record with ID {entry_id} successfully deleted.")
        flash('Запись успешно удалена!', 'success')
        return jsonify({'status': 'success'}), 200
    except mysql.connector.Error as err:
        current_app.logger.error(f"Ошибка при удалении записи: {err}")
        return jsonify({'status': 'error', 'message': str(err)}), 500
    except Exception as e:
        ccurrent_app.logger.error(f"Неизвестная ошибка: {e}")
        return jsonify({'status': 'error', 'message': 'Неизвестная ошибка.'}), 500
    finally:
        cursor.close()
        connection.close()

@callcenter_bp.route('/edit_entry', methods=['GET', 'POST'])
@login_required
def edit_entry():
    if request.method == 'GET':
        return render_template(
            'edit_page.html',
            brokers=brokers,
            operators=operators,
            floors=floors,
            objects=objects,
            sources=sources,
            entry=entry
        )
    
    elif request.method == 'POST':
        entry_id = request.form.get('entry_id')
        broker_id = request.form.get('broker_id')
        floor_id = request.form.get('floor_id')
        object_id = request.form.get('object_id')
        source_id = request.form.get('source_id')
        client_id = request.form.get('client_id')
        operator_id = request.form.get('operator_id')
        current_app.logger.debug("----- Debugging /edit_entry -----")
        current_app.logger.debug(f"Received entry_id: {entry_id}")
        current_app.logger.debug(f"Received broker_id: {broker_id}")
        current_app.logger.debug(f"Received floor_id: {floor_id}")
        current_app.logger.debug(f"Received object_id: {object_id}")
        current_app.logger.debug(f"Received source_id: {source_id}")
        current_app.logger.debug(f"Received client_id: {client_id}")
        current_app.logger.debug(f"Received operator_id: {operator_id}")
        if not all([entry_id, broker_id, floor_id, object_id, source_id, client_id, operator_id]):
            current_app.logger.error("Некорректные данные - отсутствуют необходимые поля.")
            flash('Пожалуйста, заполните все обязательные поля.', 'danger')
            return redirect(url_for('callcenter.operator_dashboard'))

        try:
            connection = create_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT department FROM User WHERE id = %s", (broker_id,))
            broker_data = cursor.fetchone()
            department_id = broker_data['department'] if broker_data else None
            current_app.logger.debug(f"Department ID: {department_id}")
            if not department_id:
                current_app.logger.error("Не удалось определить департамент для выбранного брокера.")
                flash('Не удалось определить департамент для выбранного брокера.', 'danger')
                return redirect(url_for('callcenter.operator_dashboard'))
            cursor.execute("SELECT operator_id FROM ScoringKC WHERE id = %s", (entry_id,))
            entry = cursor.fetchone()
            if not entry:
                current_app.logger.error("Запись не найдена.")
                flash('Запись не найдена.', 'danger')
                return redirect(url_for('callcenter.operator_dashboard'))
            user_role = session.get('role')
            user_id = session.get('id')
            entry_operator_id = entry['operator_id']
            if user_role != 'admin' and entry_operator_id != user_id:
                current_app.logger.error("У пользователя нет прав для редактирования этой записи.")
                flash('У вас нет прав для редактирования этой записи.', 'danger')
                return redirect(url_for('callcenter.operator_dashboard'))
            cursor.execute("SELECT full_name, role, fired FROM User WHERE id = %s", (operator_id,))
            operator_info = cursor.fetchone()
            if not operator_info:
                current_app.logger.error("Выбранный оператор не существует.")
                flash('Выбранный оператор не существует.', 'danger')
                return redirect(url_for('callcenter.operator_dashboard'))
            operator_role = operator_info['role']
            operator_fired = operator_info['fired']
            operator_name = operator_info['full_name'] if operator_info['full_name'] else 'Неизвестный оператор'
            if operator_role != 'operator':
                current_app.logger.error("Выбранный пользователь не имеет роли оператора.")
                flash('Выбранный пользователь не имеет роли оператора.', 'danger')
                return redirect(url_for('callcenter.operator_dashboard'))
            if operator_fired:
                current_app.logger.error("Выбранный оператор уволен.")
                flash('Выбранный оператор уволен и не может быть назначен.', 'danger')
                return redirect(url_for('callcenter.operator_dashboard'))
            current_app.logger.debug(f"Operator Name: {operator_name}")
            update_query = '''
                UPDATE ScoringKC
                SET broker_id = %s,
                    department_id = %s,
                    floor_id = %s,
                    object_id = %s,
                    source_id = %s,
                    client_id = %s,
                    operator = %s,
                    operator_id = %s
                WHERE id = %s
            '''
            current_app.logger.debug(f"Executing update_query with values: broker_id={broker_id}, department_id={department_id}, "
                             f"floor_id={floor_id}, object_id={object_id}, source_id={source_id}, client_id={client_id}, "
                             f"operator={operator_name}, operator_id={operator_id}, entry_id={entry_id}")
            cursor.execute(update_query, (
                broker_id,
                department_id,
                floor_id,
                object_id,
                source_id,
                client_id,
                operator_name,
                operator_id,
                entry_id
            ))
            connection.commit()
            current_app.logger.info("Record successfully updated in ScoringKC.")
            cursor.execute("SELECT * FROM ScoringKC WHERE id = %s", (entry_id,))
            updated_entry = cursor.fetchone()
            current_app.logger.debug(f"Updated entry: {updated_entry}")
            flash('Запись успешно обновлена!', 'success')
        except mysql.connector.Error as err:
            current_app.logger.error(f"Ошибка при обновлении записи: {err}")
            flash(f"Ошибка при обновлении записи: {err}", 'danger')
        except Exception as e:
            current_app.logger.error(f"Неизвестная ошибка: {e}")
            flash('Произошла неизвестная ошибка.', 'danger')
        finally:
            cursor.close()
            connection.close()
        if user_role == 'admin':
            return redirect(url_for('callcenter.report_dashboard'))
        else:
            return redirect(url_for('callcenter.operator_dashboard'))

def get_current_timeline():
    timezone = pytz.timezone('Europe/Moscow')  # Укажите ваш часовой пояс
    now = datetime.now(timezone)
    hour = now.hour
    weekday = now.weekday()
    if 9 <= hour < 18 and weekday < 5:
        return 'daily'
    else:
        return 'nighty'

@callcenter_bp.route('/submit_data', methods=['POST'])
@login_required
def submit_data():
    try:
        # Получение данных из формы
        floor_id = request.form.get('floor')
        broker_id = request.form.get('broker')
        object_id = request.form.get('object') or None
        source_id = request.form.get('source') or None
        client_id = request.form.get('client_id')
        operator_id = current_user.id  # Используем current_user вместо session
        
        # Проверка наличия operator_id
        if not operator_id:
            flash('Не удалось определить оператора.', 'danger')
            current_app.logger.error("Ошибка: operator_id не найден в сессии.")
            return redirect(url_for('callcenter.operator_dashboard'))
        
        current_app.logger.debug(f"Received data - Floor ID: {floor_id}, Broker ID: {broker_id}, Object ID: {object_id}, Source ID: {source_id}, Client ID: {client_id}")
        
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получение имени оператора
        cursor.execute("SELECT full_name, ukc_kc FROM User WHERE id = %s", (operator_id,))
        user_info = cursor.fetchone()
        operator_name = user_info['full_name'] if user_info else 'Неизвестный оператор'
        ukc_kc = user_info['ukc_kc'] if user_info else None
        current_app.logger.debug(f"Operator Name: {operator_name}, УКЦ/КЦ: {ukc_kc}")
        
        # Получение department_id брокера
        cursor.execute("SELECT department FROM User WHERE id = %s", (broker_id,))
        broker_data = cursor.fetchone()
        department_id = broker_data['department'] if broker_data else None
        current_app.logger.debug(f"Department ID: {department_id}")
        
        # Проверка наличия обязательных данных
        if not all([floor_id, broker_id, client_id, operator_name, department_id, ukc_kc]):
            current_app.logger.error("Ошибка: Отсутствуют необходимые данные для вставки.")
            flash('Пожалуйста, заполните все обязательные поля.', 'danger')
            return redirect(url_for('callcenter.operator_dashboard'))
        
        # Получение текущей даты и времени
        current_date = datetime.now().date()
        current_time = datetime.now().time()
        
        # Формирование SQL-запроса для INSERT
        insert_sql = '''
            INSERT INTO ScoringKC (date, time, broker_id, department_id, object_id, source_id, client_id, operator, floor_id, operator_id, status, operator_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''
        insert_params = (
            current_date,
            current_time,
            broker_id,
            department_id,
            object_id,
            source_id,
            client_id,
            operator_name,
            floor_id,
            operator_id,
            'transferred',   # Устанавливаем статус как 'transferred'
            ukc_kc           # Тип оператора ('КЦ' или 'УКЦ')
        )
        cursor.execute(insert_sql, insert_params)
        connection.commit()
        current_app.logger.info("Data successfully inserted into ScoringKC")
        scoringkc_id = cursor.lastrowid
        
        # Получение новой записи для эмиссии события
        select_sql = """
            SELECT 
                ScoringKC.id AS scoring_id,
                ScoringKC.date AS date,
                ScoringKC.time AS time,
                ScoringKC.broker_id,
                ScoringKC.department_id,
                ScoringKC.object_id,
                ScoringKC.source_id,
                ScoringKC.client_id,
                ScoringKC.operator,
                ScoringKC.floor_id,
                ScoringKC.operator_id,
                User.full_name AS broker_name, 
                CallCategories.category_name AS floor_name,
                ObjectKC.object_name AS object_name,
                SourceKC.source_name AS source_name,
                OperatorUser.ukc_kc AS operator_ukc_kc
            FROM ScoringKC
            JOIN User ON ScoringKC.broker_id = User.id
            JOIN CallCategories ON ScoringKC.floor_id = CallCategories.id
            LEFT JOIN ObjectKC ON ScoringKC.object_id = ObjectKC.id
            LEFT JOIN SourceKC ON ScoringKC.source_id = SourceKC.id
            LEFT JOIN User AS OperatorUser ON ScoringKC.operator_id = OperatorUser.id
            WHERE ScoringKC.id = %s
        """
        select_params = (scoringkc_id,)
        current_app.logger.debug(f"Executing SQL: {select_sql} with params {select_params}")
        cursor.execute(select_sql, select_params)
        new_entry = cursor.fetchone()
        current_app.logger.debug(f"New Entry Retrieved: {new_entry}")
        
        if not new_entry:
            current_app.logger.error("Ошибка: Новая запись не найдена.")
            flash("Внутренняя ошибка сервера.", 'danger')
            return redirect(url_for('callcenter.operator_dashboard'))
        
        # Преобразование полей date и time в строки
        new_entry['date'] = new_entry['date'].strftime('%d.%m.%Y') if new_entry['date'] else ''
        if isinstance(new_entry['time'], timedelta):
            new_entry['time'] = timedelta_to_time_str(new_entry['time'])
        elif isinstance(new_entry['time'], (datetime.time, datetime.datetime)):
            new_entry['time'] = new_entry['time'].strftime('%H:%M:%S')
        else:
            new_entry['time'] = str(new_entry['time'])
        
        # Эмитируем событие 'client_transferred' в соответствующую комнату
        operator_type = new_entry.get('operator_ukc_kc')
        if not operator_type:
            current_app.logger.error("Ошибка: operator_type не найден в новой записи.")
            flash("Внутренняя ошибка сервера.", 'danger')
            return redirect(url_for('callcenter.operator_dashboard'))
        
        if operator_type not in ['КЦ', 'УКЦ']:
            current_app.logger.error(f"Ошибка: operator_type содержит недопустимое значение: {operator_type}")
            flash("Внутренняя ошибка сервера.", 'danger')
            return redirect(url_for('callcenter.operator_dashboard'))
        
        # Эмитируем событие 'client_transferred' в соответствующую комнату
        try:
            socketio.emit(
                'client_transferred',  # Название события
                {'client': new_entry},  # Данные
                room=operator_type,     # Комната ('КЦ' или 'УКЦ')
                namespace='/call_center'
            )
            current_app.logger.info(f"Эмитировано событие 'client_transferred' в комнату '{operator_type}' для клиента ID={client_id}")
        except Exception as e:
            current_app.logger.error(f"Ошибка при эмиссии события: {e}")
            flash('Произошла ошибка при обновлении данных.', 'danger')
    
        flash('Запись успешно добавлена!', 'success')
    
    except Exception as e:
        traceback.print_exc()
        current_app.logger.error(f"Ошибка при обработке данных: {e}")
        flash(f"Ошибка: {e}", 'danger')
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
    return redirect(url_for('callcenter.operator_dashboard'))


def get_calls_data():
    current_timeline = get_current_timeline()
    connection = create_db_connection()
    data = {}
    categories_order = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT category_name FROM CallCategories WHERE archived = 0 ORDER BY `order` ASC")
            categories = cursor.fetchall()
            categories_order = [category['category_name'] for category in categories]
            cursor.execute("""
                SELECT Calls.number, CallCategories.category_name, Calls.timeline 
                FROM Calls
                JOIN CallCategories ON Calls.category_id = CallCategories.id
                WHERE Calls.timeline = %s AND Calls.hide = 'no'
                ORDER BY RAND()
            """, (current_timeline,))
            calls = cursor.fetchall()
            for call in calls:
                category_name = call['category_name']
                if category_name not in data:
                    data[category_name] = []
                data[category_name].append(call)
        except mysql.connector.Error as e:
            print(f"Ошибка при получении данных из БД: {e}")
        finally:
            cursor.close()
            connection.close()
    ordered_data = {}
    for category in categories_order:
        ordered_data[category] = data.get(category, [])
    return ordered_data, categories_order

@callcenter_bp.route('/add_operator', methods=['GET', 'POST'])
@login_required
def add_operator():
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        username = request.form['username']
        fullname = request.form['fullname']
        ukc_kc = request.form['ukc_kc']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        role = 'operator'
        status = 'Офлайн'
        department = ukc_kc
        connection = create_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO User (login, full_name, password, role, ukc_kc, status, department)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (username, fullname, hashed_password, role, ukc_kc, status, department))
            connection.commit()
            flash('Оператор успешно добавлен', 'success')
        except mysql.connector.Error as e:
            flash(f'Ошибка при добавлении оператора: {e}', 'danger')
            print(f"Ошибка при добавлении оператора: {e}")
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('add_operator'))
    today = date.today()
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute('''
        SELECT User.id, User.full_name, User.login, User.ukc_kc, User.last_active,
               IFNULL(SUM(OperatorActivity.active_time), 0) AS active_time_today
        FROM User
        LEFT JOIN OperatorActivity ON User.id = OperatorActivity.operator_id AND OperatorActivity.date = %s
        WHERE User.role = 'operator'
        GROUP BY User.id, User.full_name, User.login, User.ukc_kc, User.last_active
    ''', (today,))
    operators = cursor.fetchall()
    cursor.close()
    connection.close()
    tz = pytz.timezone('Europe/Moscow')
    current_time = datetime.now(tz)
    offline_threshold = current_time - timedelta(minutes=2)
    for operator in operators:
        last_active = operator.get('last_active')
        print(f"Operator ID: {operator['id']}, Last Active: {last_active}")
        if last_active:
            if isinstance(last_active, datetime):
                last_active = last_active.replace(tzinfo=pytz.utc).astimezone(tz)
            elif isinstance(last_active, str):
                last_active = datetime.strptime(last_active, '%Y-%m-%d %H:%M:%S')
                last_active = tz.localize(last_active)
            if last_active >= offline_threshold:
                operator['status'] = 'Онлайн'
            else:
                operator['status'] = 'Офлайн'
        else:
            operator['status'] = 'Офлайн'
    return render_template('add_operator.html', operators=operators)

@callcenter_bp.route('/add_to_blacklist', methods=['POST'])
@login_required
def add_to_blacklist():
    try:
        user_id = request.form['user_id']
        added_at = datetime.now()  # Текущее время
        if not user_id:
            flash('Ошибка: не указан пользователь для добавления в ЧС.', 'danger')
            return redirect(url_for('callcenter.manage_objects_sources'))
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM Blacklist WHERE user_id = %s", (user_id,))
        if cursor.fetchone():
            flash('Пользователь уже в черном списке.', 'warning')
            cursor.close()
            connection.close()
            return redirect(url_for('callcenter.manage_objects_sources'))
        cursor.execute("""
            INSERT INTO Blacklist (user_id, added_at) 
            VALUES (%s, %s)
        """, (user_id, added_at))
        connection.commit()
        cursor.close()
        connection.close()
        flash('Пользователь добавлен в черный список.', 'success')
    except Exception as e:
        print(f"Ошибка при добавлении в черный список: {e}")
        flash('Произошла ошибка при добавлении пользователя в черный список.', 'danger')
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/search_broker', methods=['GET'])
@login_required
def search_broker():
    search_term = request.args.get('term', '')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, full_name 
        FROM User 
        WHERE role IN ('user', 'leader', 'backoffice') AND full_name LIKE %s
        ORDER BY full_name ASC
        LIMIT 10
    """, (f"%{search_term}%",))
    brokers = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(brokers)

@callcenter_bp.route('/search_department', methods=['GET'])
@login_required
def search_department():
    search_term = request.args.get('term', '')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT DISTINCT department 
        FROM User 
        WHERE department LIKE %s 
        ORDER BY department ASC
        LIMIT 10
    """, (f"%{search_term}%",))
    departments = cursor.fetchall()
    cursor.close()
    connection.close()
    results = [dept['department'] for dept in departments]
    return jsonify(results)

@callcenter_bp.route('/search_floor', methods=['GET'])
@login_required
def search_floor():
    search_term = request.args.get('term', '')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT category_name 
        FROM CallCategories 
        WHERE category_name LIKE %s 
        ORDER BY category_name ASC
        LIMIT 10
    """, (f"%{search_term}%",))
    floors = cursor.fetchall()
    cursor.close()
    connection.close()
    results = [floor['category_name'] for floor in floors]
    return jsonify(results)

@callcenter_bp.route('/search_object', methods=['GET'])
@login_required
def search_object():
    search_term = request.args.get('term', '')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT object_name 
        FROM ObjectKC 
        WHERE object_name LIKE %s 
        ORDER BY object_name ASC
        LIMIT 10
    """, (f"%{search_term}%",))
    objects = cursor.fetchall()
    cursor.close()
    connection.close()
    results = [obj['object_name'] for obj in objects]
    return jsonify(results)

@callcenter_bp.route('/search_source', methods=['GET'])
@login_required
def search_source():
    search_term = request.args.get('term', '')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT source_name 
        FROM SourceKC 
        WHERE source_name LIKE %s 
        ORDER BY source_name ASC
        LIMIT 10
    """, (f"%{search_term}%",))
    sources = cursor.fetchall()
    cursor.close()
    connection.close()
    results = [source['source_name'] for source in sources]
    return jsonify(results)

@callcenter_bp.route('/remove_from_blacklist/<int:blacklist_id>', methods=['POST'])
@login_required
def remove_from_blacklist(blacklist_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM Blacklist WHERE id = %s", (blacklist_id,))
        connection.commit()
        flash('Пользователь удален из черного списка.', 'success')
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Ошибка при удалении из черного списка: {e}")
        flash('Произошла ошибка при удалении пользователя из черного списка.', 'danger')
    return redirect(url_for('callcenter.manage_objects_sources'))


def get_blacklist():
    connection = create_db_connection()
    blacklist = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT Blacklist.id, User.full_name, Blacklist.added_at, Adder.full_name AS added_by
                FROM Blacklist
                JOIN User ON Blacklist.user_id = User.id
                JOIN User AS Adder ON Blacklist.added_by = Adder.id
                ORDER BY Blacklist.added_at DESC
            """)
            blacklist = cursor.fetchall()
        except mysql.connector.Error as e:
            print(f"Ошибка при получении черного списка: {e}")
        finally:
            cursor.close()
            connection.close()
    return blacklist

@callcenter_bp.route('/edit_operator', methods=['POST'])
@login_required
def edit_operator():
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    operator_id = request.form.get('operator_id')
    fullname = request.form['fullname']
    login = request.form['login']
    ukc_kc = request.form['ukc_kc']
    status = request.form['status']
    password = request.form['password']
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE User 
            SET login = %s, full_name = %s, ukc_kc = %s, status = %s 
            WHERE id = %s
        """, (login, fullname, ukc_kc, status, operator_id))
        if password:
            hashed_password = generate_password_hash(password)
            cursor.execute("""
                UPDATE User 
                SET password = %s 
                WHERE id = %s
            """, (hashed_password, operator_id))
        connection.commit()
        flash('Оператор успешно обновлён', 'success')
    except mysql.connector.Error as e:
        flash(f'Ошибка при обновлении оператора: {e}', 'danger')
        print(f"Ошибка при обновлении оператора: {e}")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('add_operator'))

@callcenter_bp.route('/delete_operator', methods=['POST'])
@login_required
def delete_operator():
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    operator_id = request.form.get('operator_id')
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM User WHERE id = %s", (operator_id,))
        connection.commit()
        flash('Оператор успешно удалён.', 'success')
    except mysql.connector.Error as e:
        flash(f'Ошибка при удалении оператора: {e}', 'danger')
        print(f"Ошибка при удалении оператора: {e}")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for('add_operator'))

@callcenter_bp.route('/manage_calls', methods=['GET', 'POST'])
@login_required
def manage_calls():
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT id, category_name FROM CallCategories")
    categories = cursor.fetchall()
    category_filter = request.args.get('category_filter', '')
    time_filter = request.args.get('time_filter', '')
    query = """
    SELECT Calls.*, CallCategories.category_name
    FROM Calls
    JOIN CallCategories ON Calls.category_id = CallCategories.id
    """
    filters = []
    if category_filter:
        filters.append(f"Calls.category_id = {category_filter}")
    if time_filter:
        filters.append(f"timeline = '{time_filter}'")
    if filters:
        query += " WHERE " + " AND ".join(filters)
    cursor.execute(query)
    calls = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('manage_calls.html', filtered_calls=calls, categories=categories, time_of_day_names=current_app.config['TIME_OF_DAY_NAMES'])

@callcenter_bp.route('/edit_base', methods=['GET'])
def edit_base():
    notifications = Notification.query.all()
    return render_template('edit_base.html', notifications=notifications)

@callcenter_bp.route('/delete_notification/<int:notification_id>', methods=['POST'])
@login_required
def remove_notification(notification_id):
    print(f'Получен запрос на удаление уведомления с ID: {notification_id}')  # Отладка
    user_id = session.get('id')
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT ukc_kc FROM User WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if user:
            cursor.execute("DELETE FROM UserNotifications WHERE notification_id = %s AND user_id = %s", (notification_id, user_id))
        else:
            cursor.execute("SELECT operator_type FROM vats_operators WHERE id = %s", (user_id,))
            vats_user = cursor.fetchone()
            if vats_user:
                cursor.execute("DELETE FROM VatsUserNotifications WHERE notification_id = %s AND vats_operator_id = %s", (notification_id, user_id))
            else:
                return jsonify({'status': 'error', 'message': 'Пользователь не найден.'}), 404
        cursor.execute("""
            SELECT COUNT(*) AS count FROM UserNotifications WHERE notification_id = %s
        """, (notification_id,))
        count_user = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) AS count FROM VatsUserNotifications WHERE notification_id = %s
        """, (notification_id,))
        count_vats = cursor.fetchone()['count']
        if count_user == 0 and count_vats == 0:
            cursor.execute("DELETE FROM Notifications WHERE id = %s", (notification_id,))
        connection.commit()
        flash('Уведомление успешно удалено.', 'success')
        return jsonify({'status': 'success'})
    except mysql.connector.Error as e:
        connection.rollback()
        flash(f'Ошибка при удалении уведомления: {e}', 'danger')
        print(f"Ошибка при удалении уведомления: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        cursor.close()
        connection.close()


@callcenter_bp.route('/edit_call/<int:call_id>', methods=['POST'])
@login_required
def edit_call(call_id):
    call_number = request.form.get('call_number')

    if not call_number:
        flash('Новый номер вызова не предоставлен.', 'danger')
        return redirect(url_for('callcenter.manage_calls'))

    # Дополнительная валидация номера вызова (пример: проверка на цифровой формат и длину)
    if not call_number.isdigit() or len(call_number) < 7:
        flash('Неверный формат номера вызова.', 'danger')
        return redirect(url_for('callcenter.manage_calls'))

    connection = None
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Обновление номера вызова
        update_query = 'UPDATE Calls SET number = %s WHERE id = %s'
        cursor.execute(update_query, (call_number, call_id))
        connection.commit()
        
        # Получение обновленной записи
        select_query = """
            SELECT c.*, cc.category_name, u.full_name AS operator_name, u.ukc_kc
            FROM Calls c
            JOIN CallCategories cc ON c.category_id = cc.id
            JOIN User u ON c.operator_id = u.id
            WHERE c.id = %s
        """
        cursor.execute(select_query, (call_id,))
        call = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if call:
            operator_type = call.get('ukc_kc', 'УКЦ')  # Предполагается, что поле ukc_kc есть в таблице User
            operator_id = call.get('operator_id')
            operator_name = call.get('operator_name', 'Неизвестный оператор')
            
            if operator_type in ['КЦ', 'УКЦ'] and operator_id:
                event_data = {
                    'operator_id': operator_id,
                    'operator_name': operator_name,
                    'new_number': call_number
                }
                socketio.emit(
                    'number_changed',
                    event_data,
                    room=operator_type,
                    namespace='/call_center'
                )
                current_app.logger.info(f"Sent 'number_changed' event to room '{operator_type}' for operator ID {operator_id}")
            else:
                current_app.logger.warning(f"Invalid operator_type '{operator_type}' or missing operator_id for call ID {call_id}. Event not sent.")
        
        flash('Номер успешно обновлен', 'success')
        return redirect(url_for('callcenter.manage_calls'))
    
    except mysql.connector.Error as err:
        if connection and connection.is_connected():
            connection.rollback()
        current_app.logger.error(f"Database error during edit_call: {err}")
        flash(f"Ошибка при обновлении номера: {err}", 'danger')
        return redirect(url_for('callcenter.manage_calls'))
    
    except Exception as e:
        if connection and connection.is_connected():
            connection.rollback()
        current_app.logger.error(f"Unexpected error during edit_call: {e}")
        flash('Произошла неизвестная ошибка при обновлении номера.', 'danger')
        return redirect(url_for('callcenter.manage_calls'))
    
    finally:
        if connection and connection.is_connected():
            connection.close()

@callcenter_bp.route('/add_category', methods=['POST'])
@login_required
def add_category():
    try:
    category_name = request.form['category_name']
    connection = create_db_connection()
    cursor = connection.cursor()
        
        # Получаем максимальный порядок
        cursor.execute("SELECT MAX(`order`) as max_order FROM CallCategories")
        result = cursor.fetchone()
        next_order = 0 if not result or not result[0] else result[0] + 1
        
        # Добавляем новую категорию
        cursor.execute("""
            INSERT INTO CallCategories (category_name, `order`, archived) 
            VALUES (%s, %s, 0)
        """, (category_name, next_order))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Категория успешно добавлена!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при добавлении категории: {str(e)}")
        flash(f"Ошибка при добавлении категории: {str(e)}", 'error')
    
        return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/add_object', methods=['POST'])
@login_required
def add_object():
    try:
    object_name = request.form['object_name']
    connection = create_db_connection()
    cursor = connection.cursor()
        
        # Получаем максимальный порядок
        cursor.execute("SELECT MAX(`order`) as max_order FROM ObjectKC")
        result = cursor.fetchone()
        next_order = 0 if not result or not result[0] else result[0] + 1
        
        # Добавляем новый объект
        cursor.execute("""
            INSERT INTO ObjectKC (object_name, `order`, archived) 
            VALUES (%s, %s, 0)
        """, (object_name, next_order))
        
    connection.commit()
    cursor.close()
    connection.close()
        
    flash('Объект успешно добавлен!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при добавлении объекта: {str(e)}")
        flash(f"Ошибка при добавлении объекта: {str(e)}", 'error')
    
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/archive_object/<int:object_id>', methods=['POST'])
@login_required
def archive_object(object_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Проверяем, существует ли объект
        cursor.execute("SELECT id FROM ObjectKC WHERE id = %s", (object_id,))
        if not cursor.fetchone():
            flash('Объект не найден', 'error')
            return redirect(url_for('callcenter.manage_objects_sources'))
        
        # Архивируем объект
        cursor.execute("""
            UPDATE ObjectKC
            SET archived = 1
            WHERE id = %s
        """, (object_id,))
        
            connection.commit()
        cursor.close()
        connection.close()
        
        flash('Объект успешно архивирован!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при архивировании объекта: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    
        return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/archive_category/<int:category_id>', methods=['POST'])
@login_required
def archive_category(category_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor()

        # Проверяем, существует ли категория
        cursor.execute("SELECT id FROM CallCategories WHERE id = %s", (category_id,))
        if not cursor.fetchone():
            flash('Категория не найдена', 'error')
            return redirect(url_for('callcenter.manage_objects_sources'))
        
        # Архивируем категорию
        cursor.execute("""
            UPDATE CallCategories
            SET archived = 1
            WHERE id = %s
        """, (category_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Категория успешно архивирована!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при архивировании категории: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    
        return redirect(url_for('callcenter.manage_objects_sources'))



@callcenter_bp.route('/archive_source/<int:source_id>', methods=['POST'])
@login_required
def archive_source(source_id):
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Проверяем, существует ли источник
        cursor.execute("SELECT id FROM SourceKC WHERE id = %s", (source_id,))
        if not cursor.fetchone():
            flash('Источник не найден', 'error')
            return redirect(url_for('callcenter.manage_objects_sources'))
        
        # Архивируем источник
        cursor.execute("""
            UPDATE SourceKC
            SET archived = 1
            WHERE id = %s
        """, (source_id,))
        
            connection.commit()
        cursor.close()
        connection.close()
        
        flash('Источник успешно архивирован!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при архивировании источника: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    
        return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/add_source', methods=['POST'])
@login_required
def add_source():
    try:
    source_name = request.form['source_name']
    connection = create_db_connection()
    cursor = connection.cursor()
        
        # Получаем максимальный порядок
        cursor.execute("SELECT MAX(`order`) as max_order FROM SourceKC")
        result = cursor.fetchone()
        next_order = 0 if not result or not result[0] else result[0] + 1
        
        # Добавляем новый источник
        cursor.execute("""
            INSERT INTO SourceKC (source_name, `order`, archived) 
            VALUES (%s, %s, 0)
        """, (source_name, next_order))
        
    connection.commit()
    cursor.close()
    connection.close()
        
    flash('Источник успешно добавлен!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при добавлении источника: {str(e)}")
        flash(f"Ошибка при добавлении источника: {str(e)}", 'error')
    
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/edit_object', methods=['POST'])
@login_required
def edit_object():
    try:
        object_id = request.form['object_id']
        new_object_name = request.form['object_name']
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE ObjectKC
            SET object_name = %s
            WHERE id = %s
        """, (new_object_name, object_id))
        connection.commit()
        cursor.close()
        connection.close()
        flash('Название объекта успешно обновлено!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при редактировании объекта: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/edit_source', methods=['POST'])
@login_required
def edit_source():
    try:
        source_id = request.form['source_id']
        new_source_name = request.form['source_name']
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE SourceKC
            SET source_name = %s
            WHERE id = %s
        """, (new_source_name, source_id))
        connection.commit()
        cursor.close()
        connection.close()
        flash('Название источника успешно обновлено!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при редактировании источника: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/manage_categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True) 
        print("Успешно подключено к базе данных")
        cursor.execute("SELECT * FROM CallCategories")
        categories = cursor.fetchall()
        cursor.close()
        connection.close()
        return render_template('manage_categories.html', categories=categories)
    else:
        flash('Ошибка подключения к базе данных', 'danger')
        return redirect(url_for('auth.login'))

@callcenter_bp.route('/manage_objects_sources')
@login_required
def manage_objects_sources():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Фильтрация только активных объектов
        cursor.execute("SELECT id, object_name FROM ObjectKC WHERE archived = 0 ORDER BY `order`")
        objects = cursor.fetchall()

        # Фильтрация только активных источников
        cursor.execute("SELECT id, source_name FROM SourceKC WHERE archived = 0 ORDER BY `order`")
        sources = cursor.fetchall()

        # Фильтрация только активных категорий
        cursor.execute("SELECT id, category_name FROM CallCategories WHERE archived = 0 ORDER BY `order`")
        categories = cursor.fetchall()

        # Получение черного списка
        cursor.execute("""
            SELECT b.id, u.full_name, b.added_at
            FROM Blacklist b
            JOIN User u ON b.user_id = u.id
            ORDER BY b.added_at DESC
        """)
        blacklist = cursor.fetchall()
        
        # Получение уведомлений для админов
        cursor.execute("""
            SELECT id, message, created_at, 
                   CASE WHEN EXISTS (SELECT 1 FROM UserNotifications WHERE notification_id = id AND is_read = 1) 
                   THEN 1 ELSE 0 END as is_read
            FROM Notifications
            ORDER BY created_at DESC
            LIMIT 10
        """)
        notifications = cursor.fetchall()
        
        cursor.close()
        connection.close()

        return render_template(
            'manage_objects_sources.html',
            objects=objects,
            sources=sources,
            categories=categories,
            blacklist=blacklist,
            notifications=notifications
        )
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных для редактирования базы: {str(e)}")
        flash('Произошла ошибка при загрузке данных', 'error')
        return redirect(url_for('callcenter.call_center_dashboard'))

@callcenter_bp.route('/update_order', methods=['POST'])
@login_required
def update_order():
    if current_user.role not in ['admin', 'operator']:
        return jsonify({'status': 'error', 'message': 'Нет доступа'}), 403
    
    data = request.get_json()
    logger.info(f'Получены данные для изменения порядка: {data}')  # Логируем полученные данные
    
    table = data.get('table')
    order = data.get('order')
    
    if not table or not order:
        return jsonify({'status': 'error', 'message': 'Некорректные данные'}), 400
    
    table_mapping = {
        'object-table': ('ObjectKC', 'id'),
        'source-table': ('SourceKC', 'id'),
        'category-table': ('CallCategories', 'id')
    }
    
    if table not in table_mapping:
        return jsonify({'status': 'error', 'message': 'Неизвестная таблица'}), 400
    
    table_name, id_field = table_mapping[table]
    
    try:
        connection = create_db_connection()
        cursor = connection.cursor()
        
        for item in order:
            item_id = item.get('id')
            position = item.get('position')
            
            if item_id is None or position is None:
                continue
            
            query = f"UPDATE {table_name} SET `order` = %s WHERE {id_field} = %s"
            cursor.execute(query, (position, item_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'status': 'success'})
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении порядка: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@callcenter_bp.route('/edit_item', methods=['POST'])
@login_required
def edit_item():
    item_id = request.form['id']
    item_type = request.form['type']
    new_name = request.form['name']
    connection = create_db_connection()
    cursor = connection.cursor()
    if item_type == 'object':
        cursor.execute("UPDATE ObjectKC SET name = %s WHERE id = %s", (new_name, item_id))
    elif item_type == 'source':
        cursor.execute("UPDATE SourceKC SET name = %s WHERE id = %s", (new_name, item_id))
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify(success=True)

@callcenter_bp.route('/archive_item', methods=['POST'])
@login_required
def archive_item():
    item_id = request.form['id']
    item_type = request.form['type']
    action = request.form['action']
    connection = create_db_connection()
    cursor = connection.cursor()
    archived = 1 if action == 'archive' else 0
    if item_type == 'object':
        cursor.execute("UPDATE ObjectKC SET archived = %s WHERE id = %s", (archived, item_id))
    elif item_type == 'source':
        cursor.execute("UPDATE SourceKC SET archived = %s WHERE id = %s", (archived, item_id))
    connection.commit()
    cursor.close()
    connection.close()
    return jsonify(success=True)

@callcenter_bp.route('/add_call', methods=['POST'])
@login_required
def add_call():
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    number = request.form['number']
    category_id = request.form['category_id']  # Теперь используем ID категории
    timeline = request.form.get('timeline', 'daily')
    connection = create_db_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO Calls (number, category_id, timeline) VALUES (%s, %s, %s)", (number, category_id, timeline))
    connection.commit()
    cursor.close()
    connection.close()
    flash('Номер успешно добавлен', 'success')
    return redirect(url_for('manage_calls'))

@callcenter_bp.route('/edit_categories', methods=['POST'])
@login_required
def edit_categories():
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    category_name = request.form['category_name']
    print(f"Adding category: {category_name}")
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO Calls (category, number, timeline, hide) VALUES (%s, '', 'daily', 'no')", (category_name,))
        connection.commit()
        print("Category added successfully.")
    except mysql.connector.Error as e:
        print(f"Error while adding category: {e}")
    finally:
        cursor.close()
        connection.close()
    flash('Категория успешно добавлена', 'success')
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/edit_category', methods=['POST'])
@login_required
def edit_category():
    try:
        category_id = request.form['category_id']
        new_category_name = request.form['category_name']
    connection = create_db_connection()
    cursor = connection.cursor()
        cursor.execute("""
            UPDATE CallCategories
            SET category_name = %s
            WHERE id = %s
        """, (new_category_name, category_id))
        connection.commit()
        cursor.close()
        connection.close()
        flash('Название категории успешно обновлено!', 'success')
    except Exception as e:
        logger.error(f"Ошибка при редактировании категории: {str(e)}")
        flash(f"Ошибка: {str(e)}", 'error')
    return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/delete_call/<int:call_id>', methods=['POST'])
@login_required
def delete_call(call_id):
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('auth.login'))
    connection = create_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM Calls WHERE id = %s", (call_id,))
    connection.commit()
    cursor.close()
    connection.close()
    flash('Вызов удалён', 'success')
    return redirect(url_for('manage_calls'))

@callcenter_bp.route('/delete_category/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    if current_user.role != 'admin':
        flash('Требуются права администратора', 'danger')
        return redirect(url_for('callcenter.manage_objects_sources'))
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM CallCategories WHERE id = %s", (category_id,))
        connection.commit()
        cursor.close()
        connection.close()
        flash('Категория успешно удалена!', 'success')
        return redirect(url_for('callcenter.manage_objects_sources'))
    except mysql.connector.Error as e:
        flash(f'Ошибка: {str(e)}', 'danger')
        return redirect(url_for('callcenter.manage_objects_sources'))

@callcenter_bp.route('/rename_category', methods=['POST'])
@login_required
def rename_category():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Требуются права администратора'}), 403
    category_id = request.form['category_id']
    new_category_name = request.form['new_category_name']
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE CallCategories SET category_name = %s WHERE id = %s", (new_category_name, category_id))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({'success': True, 'category': {'id': category_id, 'category_name': new_category_name}})
    except mysql.connector.Error as e:
        return jsonify({'success': False, 'message': str(e)})

@callcenter_bp.route('/archives')
@login_required
def archives():
    """
    Отображает страницу с архивированными объектами, источниками и категориями
    """
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Получаем архивированные объекты
        cursor.execute("SELECT id, object_name FROM ObjectKC WHERE archived = 1 ORDER BY `order`")
        archived_objects = cursor.fetchall()
        
        # Получаем архивированные источники
        cursor.execute("SELECT id, source_name FROM SourceKC WHERE archived = 1 ORDER BY `order`")
        archived_sources = cursor.fetchall()
        
        # Получаем архивированные категории
        cursor.execute("SELECT id, category_name FROM CallCategories WHERE archived = 1 ORDER BY `order`")
        archived_categories = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template(
            'manage_archives.html',
            archived_objects=archived_objects,
            archived_sources=archived_sources,
            archived_categories=archived_categories
        )
    
    except Exception as e:
        logger.error(f"Ошибка при загрузке архива: {str(e)}")
        flash('Произошла ошибка при загрузке данных архива', 'error')
        return redirect(url_for('callcenter.manage_objects_sources'))


@callcenter_bp.route('/restore_item', methods=['POST'])
@login_required
def restore_item():
    """
    Восстанавливает элемент из архива, устанавливая archived = 0
    """
    try:
        item_type = request.form['item_type']
        item_id = request.form['item_id']
        
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Таблица в зависимости от типа элемента
        if item_type == 'object':
            table = 'ObjectKC'
        elif item_type == 'source':
            table = 'SourceKC'
        elif item_type == 'category':
            table = 'CallCategories'
        else:
            return jsonify({
                'success': False,
                'message': 'Неизвестный тип элемента'
            })
        
        # Устанавливаем archived = 0
        cursor.execute(f"UPDATE {table} SET archived = 0 WHERE id = %s", (item_id,))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'{item_type} успешно восстановлен'
        })
    
    except Exception as e:
        logger.error(f"Ошибка при восстановлении элемента: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        })


@callcenter_bp.route('/delete_item_permanently', methods=['POST'])
@login_required
def delete_item_permanently():
    """
    Полностью удаляет элемент из базы данных
    """
    try:
        item_type = request.form['item_type']
        item_id = request.form['item_id']
        
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Таблица в зависимости от типа элемента
        if item_type == 'object':
            table = 'ObjectKC'
        elif item_type == 'source':
            table = 'SourceKC'
        elif item_type == 'category':
            table = 'CallCategories'
        else:
            return jsonify({
                'success': False,
                'message': 'Неизвестный тип элемента'
            })
        
        # Удаляем элемент навсегда
        cursor.execute(f"DELETE FROM {table} WHERE id = %s", (item_id,))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'{item_type} успешно удален навсегда'
        })
    
    except Exception as e:
        logger.error(f"Ошибка при удалении элемента: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        })