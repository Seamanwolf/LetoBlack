from flask import Blueprint, request, jsonify, render_template, current_app, send_file, flash, redirect, url_for, session
from flask_socketio import emit, join_room, leave_room, Namespace
from app.extensions import socketio
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
from flask_login import login_required as flask_login_required, current_user

init(autoreset=True)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Инициализация Blueprint
vats_bp = Blueprint('vats', __name__, template_folder='templates', static_folder='static')

# Создание пула подключений
try:
    connection_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=20,  # Увеличено с 10 до 20 для предотвращения исчерпания пула
        pool_reset_session=True,
        host='192.168.4.14',
        port=3306,
        user='test_user',
        password='password',
        database="Brokers"
    )
    logger.info("Пул подключений к базе данных успешно создан.")
except mysql.connector.Error as err:
    logger.error(f"Ошибка при создании пула подключений: {err}")
    sys.exit(1)  # Завершить приложение при ошибке подключения

running_jobs = set()

def get_db_connection():
    try:
        conn = connection_pool.get_connection()
        logger.debug("Получено новое подключение из пула.")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Не удалось получить соединение из пула: {err}")
        return None

API_KEY = "d1b0ef65-e491-43f9-967b-df67d4657dbb"
API_URL = "https://leto.megapbx.ru/crmapi/v1"

CRM_API_URL = "https://leto.yucrm.ru/api/v1/a4d4a75094d8f9d8597085ac0ac12a51/employees/list"

headers = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

operators = [
    {"name": "Лето", "crm_id": "646", "megapbx_id": "operator1"},
    {"name": "НеЛето", "crm_id": "331", "megapbx_id": "operator2"},
    {"name": "УКЦ 7", "crm_id": "1532", "megapbx_id": "karasev_denis"},
    {"name": "УКЦ 6", "crm_id": "1526", "megapbx_id": "dfgvasc"},
    {"name": "УКЦ 5", "crm_id": "1525", "megapbx_id": "gubarev_sergej"},
    {"name": "УКЦ 4", "crm_id": "1511", "megapbx_id": "u29"},
    {"name": "УКЦ 3", "crm_id": "1507", "megapbx_id": "u53"},
    {"name": "УКЦ 12", "crm_id": "1642", "megapbx_id": "call12"},
    {"name": "УКЦ 11", "crm_id": "1641", "megapbx_id": "call11"},
    {"name": "УКЦ 10", "crm_id": "1580", "megapbx_id": "u33"},
    {"name": "Тестовый опертаор", "crm_id": "201", "megapbx_id": "krivolapov_nikolay"},
]

# Обновленный класс для пространства имен '/call_center'
class CallCenterNamespace(Namespace):
    def on_connect(self):
        user_id = session.get('id')
        user_role = session.get('role')
        logger.debug(f"Попытка подключения: user_id={user_id}, user_role={user_role}")
        if user_id and user_role == 'operator':
            operator = fetch_operator_by_id(user_id)
            if operator:
                room = operator['operator_type']  # 'КЦ' или 'УКЦ'
                join_room(room)
                logger.info(f"Пользователь {user_id} с ролью 'operator' подключился и присоединился к '{room}'")
            else:
                logger.warning(f"Оператор с user_id={user_id} не найден.")
                return False  # Отключить соединение, если оператор не найден
        else:
            logger.warning(f"Пользователь {user_id} с ролью '{user_role}' попытался подключиться к пространству имен '/call_center'")
            return False  # Отключить соединение, если не 'operator'

    def on_disconnect(self):
        user_id = session.get('id')
        user_role = session.get('role')
        if user_id and user_role == 'operator':
            # Получаем operator_type из базы данных
            operator = fetch_operator_by_id(user_id)
            if operator:
                room = operator['operator_type']
                leave_room(room)
                logger.info(f"Пользователь {user_id} с ролью 'operator' отключился и покинул '{room}'")

def fetch_operator_by_id(user_id):
    conn = get_db_connection()
    if conn is None:
        logger.error("Не удалось подключиться к базе данных для получения данных оператора.")
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT operator_type FROM vats_operators WHERE id = %s", (user_id,))
        operator = cursor.fetchone()
        return operator
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении operator_type: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

# Регистрация пространства имен
socketio.on_namespace(CallCenterNamespace('/call_center'))

def api_request(method, endpoint, data=None):
    url = f"{API_URL}{endpoint}"
    logger.info(f"Отправка {method} запроса к {url}")

    try:
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f'Неподдерживаемый метод: {method}')

        logger.info(f"Получен ответ от API. Статус код: {response.status_code}")
        logger.debug(f"Тело ответа: {response.text[:200]}...")

        if response.status_code in [200, 201, 204]:
            return True if response.status_code == 204 else response.json()
        else:
            logger.error(f'Ошибка API: {response.status_code} - {response.text}')
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при выполнении запроса к MegaPBX API: {e}")
        return None

def get_crm_numbers():
    result = {}
    headers_crm = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-API-KEY': 'c37e6b664daf6e2962d9af2c1ef3ce32'  # Ваш API ключ
    }
    
    try:
        url = f"{CRM_API_URL}?limit=2000"
        response = requests.get(url, headers=headers_crm)
        
        if response.status_code == 200:
            response_data = response.json()
            employees = response_data.get('result', {}).get('list', [])
            
            for emp in employees:
                emp_id = str(emp['id'])
                emp_name = emp.get('name', '').strip()
                phone = emp.get('phone') or emp.get('second_phone')
                
                if phone:
                    result[emp_id] = {'name': emp_name, 'phone': phone}
        
            logger.info(f"Получено {len(result)} записей из CRM")
        else:
            logger.error(f"Не удалось получить данные из CRM. Статус код: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при получении данных из CRM: {e}")
    
    return result

def get_ats_number(megapbx_id):
    logger.info(f"Получение номера АТС для MegaPBX ID: {megapbx_id}")
    number = get_megapbx_number(megapbx_id)
    if number:
        logger.info(f"Получен номер АТС для MegaPBX ID {megapbx_id}: {number}")
        return number
    else:
        logger.info(f"Номер АТС не найден для MegaPBX ID {megapbx_id}.")
        return None

def get_megapbx_number(megapbx_id):
    logger.info(f"Получение номера MegaPBX для логина: {megapbx_id}")
    result = api_request('GET', f'/users/{megapbx_id}')
    if result and isinstance(result, dict):
        phone = result.get('telnum')
        if phone:
            logger.info(f"Получен номер для {megapbx_id}: {phone}")
            return phone
        else:
            logger.info(f"Номер не найден для {megapbx_id}.")
            return None
    logger.warning(f"Номер не найден для логина: {megapbx_id}")
    return None

def format_phone_number(number):
    cleaned_number = ''.join(filter(str.isdigit, number))

    if len(cleaned_number) == 10:
        return '7' + cleaned_number
    elif len(cleaned_number) == 11 and cleaned_number.startswith('7'):
        return cleaned_number
    else:
        return None

def fetch_operator_data(operator_id):
    conn = get_db_connection()
    if conn is None:
        logger.error("Не удалось подключиться к базе данных.")
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vats_operators WHERE id = %s", (operator_id,))
        operator = cursor.fetchone()
        if not operator:
            logger.warning(f"Оператор с ID {operator_id} не найден.")
            return None
        return operator
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении данных оператора с ID {operator_id}: {err}")
        return None
    finally:
        cursor.close()
        conn.close()

def update_crm_number(operator, new_number):
    update_url = f"https://leto.yucrm.ru/api/v1/a4d4a75094d8f9d8597085ac0ac12a51/employees/update/{operator['crm_id']}"
    data = {"phone": new_number}
    try:
        logger.info(f"Попытка обновить номер в CRM для {operator['operator_name']} на {new_number}. URL: {update_url}, данные: {data}")
        response = requests.post(update_url, headers=headers, json=data)
        logger.info(f"CRM Update Response for {operator['operator_name']}: Status Code {response.status_code}, Response Body: {response.text}")
        if response.status_code == 200:
            logger.info(f"Номер в CRM для {operator['operator_name']} успешно обновлен на {new_number}")
            return True
        else:
            logger.error(f"Ошибка при обновлении номера в CRM для {operator['operator_name']}: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при обновлении номера в CRM для {operator['operator_name']}: {e}")
        return False

@vats_bp.route('/change_numbers', methods=['POST'])
@flask_login_required
def change_numbers():
    if current_user.role != 'operator':
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403

    data = request.get_json()
    group = data.get('group')
    # Допустимые значения групп: "Лето" и "НеЛето"
    if group not in ['Лето', 'НеЛето']:
        return jsonify({'success': False, 'message': 'Неверная группа'}), 400

    # Получаем операторов из таблицы vats_operators для выбранной группы
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM vats_operators WHERE operator_type = %s AND is_active = TRUE", (group,))
    operators = cursor.fetchall()
    cursor.close()
    connection.close()

    results = []
    # Для каждого оператора вызываем уже существующую функцию смены номера
    # Функция change_operator_number импортирована из vats.py
    for operator in operators:
        success = manual_change_number(operator)
        results.append({
            'operator_id': operator['id'],
            'operator_name': operator['operator_name'],
            'success': success
        })

    return jsonify({'success': True, 'results': results})

def update_megapbx_number(cursor, operator, new_number):
    old_number = get_megapbx_number(operator['megapbx_id'])
    logger.info(f"Получен старый номер '{old_number}' для оператора '{operator['operator_name']}'")
    logger.debug(f"Old number is: '{old_number}'")
    
    # Проверяем наличие старого номера
    if old_number:
        disable_result = api_request('POST', f'/sims/{old_number}/disable')
        logger.info(f"Результат отключения старого номера {old_number} для оператора '{operator['operator_name']}' : {disable_result}")

        if not disable_result:
            logger.error(f"Ошибка при отключении старой SIM-карты для оператора '{operator['operator_name']}'")
            return False
    else:
        logger.info(f"Старый номер отсутствует для оператора '{operator['operator_name']}'. Пропуск отключения.")

    # Назначение нового номера
    assign_result = api_request('POST', f'/sims/{new_number}/user/{operator["megapbx_id"]}')
    logger.info(f"Результат назначения нового номера {new_number} для оператора '{operator['operator_name']}' в MegaPBX: {assign_result}")

    if assign_result:
        logger.info(f"Номер в MegaPBX для оператора '{operator['operator_name']}' успешно обновлен на {new_number}")
        return True
    else:
        logger.error(f"Ошибка при назначении нового номера в MegaPBX для оператора '{operator['operator_name']}'")
        return False

def change_operator_number(operator, new_number=None):
    print(f"change_operator_number: Начало обновления номера для оператора: {operator['operator_name']}")
    logger.info(f"Начало обновления номера для оператора: {operator['operator_name']}")

    conn = get_db_connection()
    if conn is None:
        print("change_operator_number: Не удалось подключиться к базе данных.")
        logger.error("Не удалось подключиться к базе данных.")
        return False

    cursor = conn.cursor(dictionary=True)
    if not new_number:
        # Получить назначенный оператору номер из базы данных
        new_number = get_next_assigned_number(cursor, operator['id'])
        if not new_number:
            print("change_operator_number: Не удалось получить назначенный номер для оператора.")
            logger.error("Не удалось получить назначенный номер для оператора.")
            return False

    # Получаем старый номер из таблицы vats_operators
    cursor.execute("SELECT current_number FROM vats_operators WHERE id = %s", (operator['id'],))
    current_data = cursor.fetchone()
    old_number = current_data['current_number'] if current_data else None
    print(f"change_operator_number: Старый номер для оператора '{operator['operator_name']}': {old_number}")
    logger.debug(f"Старый номер для оператора '{operator['operator_name']}': {old_number}")

    # Обновляем номер в CRM и MegaPBX
    crm_updated = update_crm_number(operator, new_number)
    print(f"change_operator_number: Результат обновления номера в CRM: {crm_updated}")
    logger.info(f"Обновление номера в CRM для оператора '{operator['operator_name']}': {crm_updated}")

    megapbx_updated = update_megapbx_number(cursor, operator, new_number)
    print(f"change_operator_number: Результат обновления номера в MegaPBX: {megapbx_updated}")
    logger.info(f"Обновление номера в MegaPBX для оператора '{operator['operator_name']}': {megapbx_updated}")

    if crm_updated and megapbx_updated:
        # Записываем изменение в историю и обновляем current_number и previous_number
        try:
            # Обновляем историю
            insert_history_query = """
                INSERT INTO vats_numbers_history (operator_id, old_number, new_number, changed_at)
                VALUES (%s, %s, %s, NOW())
            """
            cursor.execute(insert_history_query, (operator['id'], old_number, new_number))
            print(f"change_operator_number: Запись в историю номера для оператора ID={operator['id']}")
            logger.info(f"Запись в историю номера для оператора ID={operator['id']}")

            # Обновляем current_number и previous_number
            update_numbers_query = """
                UPDATE vats_operators
                SET previous_number = %s, current_number = %s
                WHERE id = %s
            """
            cursor.execute(update_numbers_query, (old_number, new_number, operator['id']))
            print(f"change_operator_number: Обновление current_number и previous_number для оператора ID={operator['id']}")
            logger.info(f"Обновление current_number и previous_number для оператора ID={operator['id']}")

            conn.commit()
            print(f"change_operator_number: Номер для оператора '{operator['operator_name']}' успешно обновлен в обеих системах")
            logger.info(f"Номер для оператора '{operator['operator_name']}' успешно обновлен в обеих системах")

            # Отправляем уведомление только после успешной смены номера
            room = operator["operator_type"]  # 'КЦ' или 'УКЦ'
            logger.debug(f"Отправка уведомления 'number_changed' в комнату '{room}' на namespace '/call_center'")
            print(f"change_operator_number: Отправка уведомления 'number_changed' в комнату '{room}' на namespace '/call_center'")

            socketio.emit(
                'number_changed',
                {'operator_name': operator['operator_name'], 'new_number': new_number},
                room=room,
                namespace='/call_center'
            )
            logger.info(f"Уведомление 'number_changed' отправлено для оператора '{operator['operator_name']}', новый номер={new_number}")
            print(f"change_operator_number: Уведомление 'number_changed' отправлено для оператора '{operator['operator_name']}', новый номер={new_number}")

            return True
        except mysql.connector.Error as err:
            print(f"change_operator_number: Ошибка при записи истории номера для оператора '{operator['operator_name']}': {err}")
            logger.error(f"Ошибка при записи истории номера для оператора '{operator['operator_name']}': {err}")
            conn.rollback()
            return False
    elif crm_updated:
        print(f"change_operator_number: Номер обновлен только в CRM для оператора '{operator['operator_name']}'. Ошибка при обновлении в MegaPBX.")
        logger.warning(f"Номер обновлен только в CRM для оператора '{operator['operator_name']}'. Ошибка при обновлении в MegaPBX.")
    elif megapbx_updated:
        print(f"change_operator_number: Номер обновлен только в MegaPBX для оператора '{operator['operator_name']}'. Ошибка при обновлении в CRM.")
        logger.warning(f"Номер обновлен только в MegaPBX для оператора '{operator['operator_name']}'. Ошибка при обновлении в CRM.")
    else:
        print(f"change_operator_number: Произошла ошибка при обновлении номера в обеих системах для оператора '{operator['operator_name']}'")
        logger.error(f"Произошла ошибка при обновлении номера в обеих системах для оператора '{operator['operator_name']}'")
    return False

@vats_bp.route('/add_number', methods=['POST'])
def add_number():
    data = request.get_json()
    phone_number = data.get('phone_number')
    if not phone_number:
        return jsonify({"success": False, "message": "Не указан номер телефона."}), 400

    # Форматируем и проверяем номер телефона
    formatted_number = format_phone_number(phone_number)
    if not formatted_number:
        return jsonify({"success": False, "message": "Некорректный формат номера телефона."}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"success": False, "message": "Не удалось подключиться к базе данных."}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        # Проверка уникальности номера
        cursor.execute("SELECT id FROM phone_numbers WHERE phone_number = %s", (formatted_number,))
        existing = cursor.fetchone()
        if existing:
            return jsonify({"success": False, "message": "Номер телефона уже существует."}), 400

        # Вставка нового номера
        insert_query = "INSERT INTO phone_numbers (phone_number, assigned_operator_id) VALUES (%s, NULL)"
        cursor.execute(insert_query, (formatted_number,))
        conn.commit()
        return jsonify({"success": True, "message": "Номер телефона успешно добавлен."}), 201
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении номера телефона: {err}")
        conn.rollback()
        return jsonify({"success": False, "message": "Ошибка при добавлении номера телефона."}), 500
    finally:
        cursor.close()
        conn.close()

def get_next_assigned_number(cursor, operator_id):
    """Получает следующий назначенный номер оператора из базы данных, выбирая по порядку."""
    try:
        # Получить все номера, отсортированные по ID
        cursor.execute("""
            SELECT phone_number FROM phone_numbers 
            WHERE assigned_operator_id = %s 
            ORDER BY id ASC
        """, (operator_id,))
        assigned_numbers = cursor.fetchall()
        logger.debug(f"Назначенные номера для оператора ID={operator_id}: {[num['phone_number'] for num in assigned_numbers]}")

        if not assigned_numbers:
            logger.error(f"Нет назначенных номеров для оператора ID={operator_id}.")
            return None

        # Получить последний использованный номер оператора из истории
        cursor.execute("""
            SELECT new_number FROM vats_numbers_history
            WHERE operator_id = %s
            ORDER BY changed_at DESC LIMIT 1
        """, (operator_id,))
        last_used = cursor.fetchone()

        # Если есть последний использованный номер, найдём его в списке и выберем следующий по порядку
        if last_used:
            last_used_number = last_used['new_number']
            logger.debug(f"Последний использованный номер для оператора ID={operator_id}: {last_used_number}")
            # Найти индекс последнего использованного номера
            index = next((i for i, num in enumerate(assigned_numbers) if num['phone_number'] == last_used_number), -1)
            if index == -1:
                logger.warning(f"Последний использованный номер {last_used_number} не найден среди назначенных номеров для оператора ID={operator_id}.")
                next_index = 0
            else:
                # Получить индекс следующего номера в списке
                next_index = (index + 1) % len(assigned_numbers)
        else:
            # Если нет записи в истории, начинаем с первого номера
            next_index = 0
            logger.debug(f"Нет записей в истории для оператора ID={operator_id}. Начинаем с первого номера.")

        selected_number = assigned_numbers[next_index]['phone_number']
        logger.debug(f"Выбранный номер для оператора ID={operator_id}: {selected_number}")
        return selected_number
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении назначенного номера: {err}")
        return None


def mark_as_not_found_in_history(operator_id, not_found_number):
    """Добавить в историю запись о том, что номер не был найден в MegaPBX."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        insert_history_query = """
            INSERT INTO vats_numbers_history (operator_id, old_number, new_number, changed_at)
            VALUES (%s, %s, 'Не найден', NOW())
        """
        cursor.execute(insert_history_query, (operator_id, not_found_number))
        conn.commit()
        logger.info(f"Номер {not_found_number} помечен как 'не найден' для оператора ID {operator_id}")
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении записи о ненайденном номере: {err}")
    finally:
        cursor.close()
        conn.close()


def change_numbers_periodically():
    job_id = "change_numbers_periodically"
    if job_id in running_jobs:
        logger.warning("Автоматическая смена номеров уже выполняется, пропуск.")
        print("change_numbers_periodically: Автоматическая смена номеров уже выполняется, пропуск.")
        return

    running_jobs.add(job_id)
    try:
        logger.info("change_numbers_periodically: Запуск автоматической смены номеров")
        print("change_numbers_periodically: Запуск автоматической смены номеров")

        conn = get_db_connection()
        if conn is None:
            logger.error("Не удалось подключиться к базе данных для автоматической смены номеров.")
            print("change_numbers_periodically: Не удалось подключиться к базе данных для автоматической смены номеров.")
            return
        cursor = conn.cursor(dictionary=True)
        try:
            # Выбираем только активных операторов
            cursor.execute("""
                SELECT id, operator_name, crm_id, megapbx_id, operator_type 
                FROM vats_operators 
                WHERE is_active = TRUE
            """)
            operators = cursor.fetchall()
            print(f"change_numbers_periodically: Найдено {len(operators)} активных операторов.")
            logger.info(f"Начинается автоматическая смена номеров для {len(operators)} активных операторов.")

            if not operators:
                logger.info("Нет активных операторов для автоматической смены номеров.")
                print("change_numbers_periodically: Нет активных операторов для автоматической смены номеров.")
                return

            for operator in operators:
                logger.debug(f"Обработка оператора ID={operator['id']}, Name={operator['operator_name']}")
                print(f"change_numbers_periodically: Обработка оператора ID={operator['id']}, Name={operator['operator_name']}")

                new_number = get_next_assigned_number(cursor, operator['id'])
                if new_number:
                    logger.info(f"Получен новый номер {new_number} для оператора '{operator['operator_name']}'")
                    print(f"change_numbers_periodically: Получен новый номер {new_number} для оператора '{operator['operator_name']}'")

                    success = change_operator_number(operator, new_number)
                    print(f"change_numbers_periodically: Результат смены номера для оператора '{operator['operator_name']}': {success}")
                    logger.info(f"Результат смены номера для оператора '{operator['operator_name']}': {success}")

                    if success:
                        # Отправляем уведомление только после успешной смены номера
                        room = operator["operator_type"]  # 'КЦ' или 'УКЦ'
                        logger.debug(f"Отправка уведомления 'number_changed' в комнату '{room}' на namespace '/call_center'")
                        print(f"change_numbers_periodically: Отправка уведомления 'number_changed' в комнату '{room}' на namespace '/call_center'")

                        if socketio:
                            socketio.emit(
                                 'number_changed',
                                 {'operator_name': operator['operator_name'], 'new_number': new_number},
                                 room=room,
                                 namespace='/call_center'
                            )
                            logger.info(f"Уведомление 'number_changed' отправлено для оператора '{operator['operator_name']}', новый номер={new_number}")
                            print(f"change_operator_number: Уведомление 'number_changed' отправлено для оператора '{operator['operator_name']}', новый номер={new_number}")
                        else:
                            logger.warning("SocketIO не инициализирован, уведомление не отправлено.")
                            print("change_operator_number: SocketIO не инициализирован, уведомление не отправлено.")
                else:
                    logger.warning(f"Не удалось получить следующий назначенный номер для оператора '{operator['operator_name']}'")
                    print(f"change_numbers_periodically: Не удалось получить следующий назначенный номер для оператора '{operator['operator_name']}'")
        except mysql.connector.Error as err:
            logger.error(f"Ошибка при выполнении автоматической смены номеров: {err}")
            print(f"change_numbers_periodically: Ошибка при выполнении автоматической смены номеров: {err}")
        finally:
            cursor.close()
            conn.close()
            print("change_numbers_periodically: Соединение с базой данных закрыто")
            logger.debug("Соединение с базой данных закрыто")
        logger.info("Автоматическая смена номеров завершена.")
        print("change_numbers_periodically: Автоматическая смена номеров завершена.")
    finally:
        running_jobs.discard(job_id)
        print("change_numbers_periodically: Сброс флага выполнения задания")
        logger.debug("Сброс флага выполнения задания")

def get_available_numbers():
    conn = get_db_connection()
    if conn is None:
        logger.error("Не удалось подключиться к базе данных при получении доступных номеров.")
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, phone_number FROM phone_numbers WHERE assigned_operator_id IS NULL")
        available_numbers = cursor.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении доступных номеров: {err}")
        available_numbers = []
    finally:
        cursor.close()
        conn.close()
    return available_numbers

def get_assigned_numbers(operator_id):
    conn = get_db_connection()
    if conn is None:
        logger.error("Не удалось подключиться к базе данных при получении подключенных номеров.")
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, phone_number FROM phone_numbers WHERE assigned_operator_id = %s", (operator_id,))
        assigned_numbers = cursor.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении подключенных номеров: {err}")
        assigned_numbers = []
    finally:
        cursor.close()
        conn.close()
    return assigned_numbers

@vats_bp.route('/', methods=['GET'])
def index():
    return render_template('vats.html')

@vats_bp.route('/get_operators_json', methods=['GET'])
def get_operators_json():
    operators = []
    
    # Получение всех номеров из CRM
    crm_numbers = get_crm_numbers()
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({"success": False, "message": "Не удалось подключиться к базе данных"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, operator_name, crm_id, megapbx_id, current_number, previous_number, operator_type, is_active
            FROM vats_operators
        """)
        operators_db = cursor.fetchall()

        for operator in operators_db:
            crm_id_str = str(operator['crm_id'])
            crm_entry = crm_numbers.get(crm_id_str, {})
            crm_number = crm_entry.get('phone')

            ats_number = get_ats_number(operator['megapbx_id'])

            # Проверяем, есть ли назначенные номера
            cursor.execute("SELECT COUNT(*) as count FROM phone_numbers WHERE assigned_operator_id = %s", (operator['id'],))
            result = cursor.fetchone()
            has_assigned_numbers = result['count'] > 0

            operators.append({
                "id": operator['id'],
                "operator_name": operator['operator_name'],
                "operator_type": operator['operator_type'],
                "crm_id": operator['crm_id'],
                "megapbx_id": operator['megapbx_id'],
                "current_number": operator['current_number'] or '—',
                "previous_number": operator['previous_number'] or '—',
                "crm_number": format_phone_number(crm_number) if crm_number else '—',
                "ats_number": ats_number or '—',
                "is_active": operator['is_active'],
                "has_assigned_numbers": has_assigned_numbers  # Добавлено
            })
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении операторов: {err}")
        return jsonify({"success": False, "message": "Ошибка при получении операторов"}), 500
    finally:
        cursor.close()
        conn.close()

    logger.info(f"Получено {len(operators)} операторов с номерами из CRM.")
    return jsonify({"success": True, "operators": operators}), 200


@vats_bp.route('/update_operator_activity', methods=['POST'])
def update_operator_activity():
    data = request.get_json()
    operator_id = data.get('operator_id')
    is_active = data.get('is_active')

    if operator_id is None or is_active is None:
        return jsonify({'success': False, 'message': 'Неверные данные.'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'message': 'Не удалось подключиться к базе данных.'}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE vats_operators SET is_active = %s WHERE id = %s", (is_active, operator_id))
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Оператор не найден.'}), 404
        conn.commit()
        logger.info(f"Статус активности оператора ID {operator_id} обновлён на {is_active}.")
        return jsonify({'success': True, 'message': 'Статус активности оператора обновлён.'}), 200
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при обновлении статуса активности: {err}")
        conn.rollback()
        return jsonify({'success': False, 'message': 'Ошибка при обновлении статуса.'}), 500
    finally:
        cursor.close()
        conn.close()


@vats_bp.route('/get_available_numbers', methods=['GET'])
def get_available_numbers_route():
    available_numbers = get_available_numbers()
    return jsonify({"available_numbers": available_numbers}), 200

@vats_bp.route('/get_assigned_numbers', methods=['GET'])
def get_assigned_numbers_route():
    operator_id = request.args.get('operator_id')
    if not operator_id:
        return jsonify({"assigned_numbers": []})
    
    assigned_numbers = get_assigned_numbers(operator_id)
    return jsonify({"assigned_numbers": assigned_numbers}), 200

@vats_bp.route('/assign_numbers', methods=['POST'])
def assign_numbers():
    data = request.json
    operator_id = data.get('operator_id')
    number_ids = data.get('number_ids')  # Список ID номеров для назначения

    if not operator_id:
        return jsonify({"success": False, "message": "Не указан ID оператора"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"success": False, "message": "Не удалось подключиться к базе данных"}), 500

    cursor = conn.cursor()
    try:
        # Снять все номера, назначенные этому оператору
        cursor.execute("""
            UPDATE phone_numbers 
            SET assigned_operator_id = NULL 
            WHERE assigned_operator_id = %s
        """, (operator_id,))

        # Назначить новые номера
        if number_ids:
            format_strings = ','.join(['%s'] * len(number_ids))
            query = f"""
                UPDATE phone_numbers 
                SET assigned_operator_id = %s 
                WHERE id IN ({format_strings})
            """
            cursor.execute(query, (operator_id, *number_ids))

        conn.commit()
        return jsonify({"success": True, "message": "Номера успешно обновлены"}), 200
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при обновлении номеров: {err}")
        conn.rollback()
        return jsonify({"success": False, "message": "Ошибка при обновлении номеров"}), 500
    finally:
        cursor.close()
        conn.close()


@vats_bp.route('/add_operator', methods=['POST'])
def add_operator():
    data = request.get_json() or request.form
    crm_id = data.get('crm_id')
    megapbx_id = data.get('megapbx_id')
    current_number = data.get('current_number')
    operator_type = data.get('operator_type')
    operator_name = data.get('operator_name')

    # Валидация обязательных полей
    if not crm_id or not megapbx_id or not operator_type or not operator_name:
        return jsonify({"success": False, "message": "Необходимо заполнить CRM ID, MegaPBX ID, тип оператора и имя оператора."}), 400

    # Валидация operator_type
    if operator_type not in ['КЦ', 'УКЦ']:
        return jsonify({"success": False, "message": "Некорректный тип оператора. Выберите КЦ или УКЦ."}), 400

    # Валидация формата текущего номера, если он указан
    if current_number:
        formatted_number = format_phone_number(current_number)
        if not formatted_number:
            return jsonify({"success": False, "message": "Некорректный формат текущего номера."}), 400
    else:
        formatted_number = None  # Если номер не указан

    conn = get_db_connection()
    if conn is None:
        return jsonify({"success": False, "message": "Не удалось подключиться к базе данных."}), 500

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Проверка уникальности CRM ID и MegaPBX ID
            cursor.execute("SELECT id FROM vats_operators WHERE crm_id = %s OR megapbx_id = %s", (crm_id, megapbx_id))
            existing = cursor.fetchone()
            if existing:
                return jsonify({"success": False, "message": "Оператор с таким CRM ID или MegaPBX ID уже существует."}), 400

            # Вставка нового оператора
            insert_query = """
                INSERT INTO vats_operators (crm_id, megapbx_id, current_number, operator_type, operator_name)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (crm_id, megapbx_id, formatted_number, operator_type, operator_name))
            conn.commit()

        logger.info(f"Новый оператор добавлен: CRM ID={crm_id}, MegaPBX ID={megapbx_id}, Текущий номер={formatted_number}, Тип={operator_type}, Имя={operator_name}")
        return jsonify({"success": True, "message": "Оператор успешно добавлен."}), 201
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении оператора: {err}")
        conn.rollback()
        return jsonify({"success": False, "message": "Ошибка при добавлении оператора."}), 500
    finally:
        conn.close()

@vats_bp.route('/delete_operator/<int:operator_id>', methods=['DELETE'])
def delete_operator(operator_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({"success": False, "message": "Не удалось подключиться к базе данных"}), 500

    cursor = conn.cursor()
    try:
        # Проверка существования оператора
        cursor.execute("SELECT * FROM vats_operators WHERE id = %s", (operator_id,))
        operator = cursor.fetchone()
        if not operator:
            return jsonify({"success": False, "message": "Оператор не найден"}), 404

        # Удаление оператора
        cursor.execute("DELETE FROM vats_operators WHERE id = %s", (operator_id,))
        
        # Установить assigned_operator_id на NULL для номеров, назначенных этому оператору
        cursor.execute("UPDATE phone_numbers SET assigned_operator_id = NULL WHERE assigned_operator_id = %s", (operator_id,))
        
        conn.commit()
        logger.info(f"Оператор с ID {operator_id} успешно удален.")
        return jsonify({"success": True, "message": "Оператор успешно удален."}), 200
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при удалении оператора: {err}")
        conn.rollback()
        return jsonify({"success": False, "message": "Ошибка при удалении оператора."}), 500
    finally:
        cursor.close()
        conn.close()

@vats_bp.route('/history', methods=['GET'])
def history():
    conn = get_db_connection()
    if conn is None:
        logger.error("Не удалось подключиться к базе данных при получении истории изменений.")
        return render_template('history.html', history=[])
    cursor = conn.cursor(dictionary=True)
    try:
        history_query = """
            SELECT h.operator_id, o.operator_name, h.old_number, h.new_number, h.changed_at
            FROM vats_numbers_history h
            JOIN vats_operators o ON h.operator_id = o.id
            ORDER BY h.changed_at DESC
        """
        cursor.execute(history_query)
        history_entries = cursor.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении истории изменений: {err}")
        history_entries = []
    finally:
        cursor.close()
        conn.close()

    return render_template('history.html', history=history_entries)

def find_phone_column(df):
    # Список возможных названий столбцов с номерами телефонов
    phone_keywords = [
        'phone', 'телефон', 'номер', 'phone number', 'mobile', 'мобильный',
        'тел', 'tel', 'contact', 'контакт', 'номер телефона', 'phone numder'
    ]
    
    # Сначала ищем точные совпадения
    for column in df.columns:
        if column.strip().lower() in phone_keywords:
            return column
    
    # Затем ищем частичные совпадения
    for column in df.columns:
        column_lower = column.strip().lower()
        if any(keyword in column_lower for keyword in phone_keywords):
            return column
    
    # Если не нашли по названию, пытаемся определить по содержимому
    for column in df.columns:
        # Проверяем первые 5 непустых значений в столбце
        values = df[column].dropna().head(5).astype(str)
        
        # Проверяем, похожи ли значения на номера телефонов
        if all(len(''.join(filter(str.isdigit, str(v)))) >= 10 for v in values):
            return column
    
    # Если столбец не найден, возвращаем None
    return None


@vats_bp.route('/upload_numbers', methods=['POST'])
def upload_numbers():
    logger.info("Начало обработки загрузки файла")
    if 'excel_file' not in request.files:
        logger.error("Файл не найден в запросе")
        return jsonify({"success": False, "message": "Файл не найден"}), 400

    file = request.files['excel_file']
    logger.info(f"Получен файл: {file.filename}")

    if file.filename == '':
        logger.error("Пустое имя файла")
        return jsonify({"success": False, "message": "Файл не выбран"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Изменяем путь к директории загрузок
        upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
        logger.info(f"Путь к директории загрузок: {upload_folder}")

        # Убедитесь, что папка для загрузки существует
        if not os.path.exists(upload_folder):
            try:
                os.makedirs(upload_folder)
                logger.info(f"Создана папка для загрузок: {upload_folder}")
            except Exception as e:
                logger.error(f"Ошибка при создании папки для загрузок: {str(e)}")
                return jsonify({"success": False, "message": f"Не удалось создать папку для загрузок: {str(e)}"}), 500

        filepath = os.path.join(upload_folder, filename)
        logger.info(f"Полный путь к файлу: {filepath}")
        
        try:
            file.save(filepath)
            logger.info("Файл успешно сохранен")
        except Exception as e:
            logger.error(f"Ошибка при сохранении файла: {str(e)}")
            return jsonify({"success": False, "message": f"Не удалось сохранить файл: {str(e)}"}), 500

        # Парсинг Excel-файла
        try:
            logger.info("Начало чтения Excel-файла")
            df = pd.read_excel(filepath)
            logger.info(f"Excel-файл успешно прочитан. Количество строк: {len(df)}")

            phone_column = find_phone_column(df)
            if phone_column is None:
                logger.error("Не найден столбец с номерами телефонов")
                return jsonify({"success": False, "message": "Не найден столбец с номерами телефонов"}), 400

            logger.info(f"Найден столбец с номерами: {phone_column}")

            conn = get_db_connection()
            if conn is None:
                logger.error("Не удалось подключиться к базе данных")
                return jsonify({"success": False, "message": "Не удалось подключиться к базе данных"}), 500
            
            cursor = conn.cursor(dictionary=True)
            inserted = 0
            skipped = 0
            errors = []

            for index, row in df.iterrows():
                try:
                    phone_number = str(row[phone_column]).strip()
                    logger.debug(f"Обработка номера: {phone_number}")

                    # Проверка формата номера
                    formatted_number = format_phone_number(phone_number)
                    if not formatted_number:
                        logger.warning(f"Некорректный формат номера в строке {index + 1}: {phone_number}")
                        errors.append(f"Строка {index + 1}: Некорректный формат номера {phone_number}")
                        skipped += 1
                        continue

                    # Проверка уникальности номера
                    cursor.execute("SELECT id FROM phone_numbers WHERE phone_number = %s", (formatted_number,))
                    existing = cursor.fetchone()
                    if existing:
                        logger.warning(f"Номер {formatted_number} уже существует в базе")
                        errors.append(f"Строка {index + 1}: Номер {formatted_number} уже существует в базе")
                        skipped += 1
                        continue

                    # Вставка нового номера
                    insert_query = "INSERT INTO phone_numbers (phone_number, assigned_operator_id) VALUES (%s, NULL)"
                    cursor.execute(insert_query, (formatted_number,))
                    inserted += 1
                    logger.debug(f"Успешно добавлен номер: {formatted_number}")

                except Exception as e:
                    logger.error(f"Ошибка при обработке строки {index + 1}: {str(e)}")
                    errors.append(f"Строка {index + 1}: {str(e)}")
                    skipped += 1

            conn.commit()
            cursor.close()
            conn.close()

            result_message = f"Номера успешно загружены: добавлено {inserted}, пропущено {skipped}."
            if errors:
                result_message += f"\nОшибки:\n" + "\n".join(errors[:10])
                if len(errors) > 10:
                    result_message += f"\n...и еще {len(errors) - 10} ошибок"

            logger.info(result_message)
            return jsonify({
                "success": True,
                "message": result_message,
                "details": {
                    "inserted": inserted,
                    "skipped": skipped,
                    "errors": errors[:10]  # Отправляем только первые 10 ошибок
                }
            }), 200

        except Exception as e:
            logger.error(f"Ошибка при обработке Excel-файла: {str(e)}")
            if 'conn' in locals() and conn.is_connected():
                conn.rollback()
                conn.close()
            return jsonify({"success": False, "message": f"Ошибка при обработке файла: {str(e)}"}), 500
        finally:
            # Удаление загруженного файла после обработки
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    logger.info(f"Временный файл удален: {filepath}")
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {filepath}: {str(e)}")
    else:
        logger.error(f"Недопустимый тип файла: {file.filename}")
        return jsonify({"success": False, "message": "Недопустимый тип файла"}), 400

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls'}

def get_users_for_operator(megapbx_id):
    conn = get_db_connection()
    if not conn:
        logger.error("Не удалось подключиться к базе данных для получения пользователей")
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, login FROM User
            WHERE login = %s AND role = 'operator' AND ukc_kc = 'КЦ'
        """, (megapbx_id,))
        users = cursor.fetchall()
        return users
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении пользователей для MegaPBX ID {megapbx_id}: {err}")
        return []
    finally:
        cursor.close()
        conn.close()

@vats_bp.route('/edit_numbers', methods=['GET', 'POST'])
def edit_numbers():
    if request.method == 'POST':
        # Обработка удаления одного номера
        number_id = request.form.get('delete_number_id')
        if number_id:
            conn = get_db_connection()
            if conn is None:
                return jsonify({"success": False, "message": "Не удалось подключиться к базе данных"}), 500
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM phone_numbers WHERE id = %s", (number_id,))
                conn.commit()
                return jsonify({"success": True, "message": "Номер успешно удален"}), 200
            except mysql.connector.Error as err:
                logger.error(f"Ошибка при удалении номера: {err}")
                conn.rollback()
                return jsonify({"success": False, "message": "Ошибка при удалении номера"}), 500
            finally:
                cursor.close()
                conn.close()

        # Обработка удаления нескольких номеров
        delete_number_ids = request.json.get('delete_number_ids')
        if delete_number_ids:
            conn = get_db_connection()
            if conn is None:
                return jsonify({"success": False, "message": "Не удалось подключиться к базе данных"}), 500
            cursor = conn.cursor()
            try:
                # Удаление всех выбранных номеров
                cursor.executemany("DELETE FROM phone_numbers WHERE id = %s", [(num_id,) for num_id in delete_number_ids])
                conn.commit()
                return jsonify({"success": True, "message": f"{len(delete_number_ids)} номера(ов) успешно удалены"}), 200
            except mysql.connector.Error as err:
                logger.error(f"Ошибка при удалении выбранных номеров: {err}")
                conn.rollback()
                return jsonify({"success": False, "message": "Ошибка при удалении выбранных номеров"}), 500
            finally:
                cursor.close()
                conn.close()

    # GET запрос: отображение списка номеров
    conn = get_db_connection()
    if conn is None:
        logger.error("Не удалось подключиться к базе данных при редактировании номеров.")
        return render_template('edit_numbers.html', numbers=[])
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT pn.id, pn.phone_number, o.operator_name
            FROM phone_numbers pn
            LEFT JOIN vats_operators o ON pn.assigned_operator_id = o.id
        """)
        numbers = cursor.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении номеров: {err}")
        numbers = []
    finally:
        cursor.close()
        conn.close()
    return render_template('edit_numbers.html', numbers=numbers)
                           
def manual_change_number(operator_id):
    print(f"manual_change_number: Получен запрос на смену номера для оператора ID={operator_id}")
    logger.info(f"Получение запроса на смену номера для оператора ID={operator_id}")

    # Получение информации о выбранном операторе из базы данных
    conn = get_db_connection()
    if conn is None:
        print("manual_change_number: Не удалось подключиться к базе данных")
        logger.error("Не удалось подключиться к базе данных")
        return jsonify({"success": False, "message": "Не удалось подключиться к базе данных"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM vats_operators WHERE id = %s", (operator_id,))
        operator = cursor.fetchone()
        print(f"manual_change_number: Получен оператор: {operator}")
        if not operator:
            print(f"manual_change_number: Оператор с ID={operator_id} не найден")
            logger.warning(f"Оператор с ID={operator_id} не найден")
            return jsonify({"success": False, "message": "Оператор не найден"}), 404

        # Получить следующий назначенный номер для оператора
        new_number = get_next_assigned_number(cursor, operator['id'])
        print(f"manual_change_number: Получен новый номер для оператора ID={operator_id}: {new_number}")
        if not new_number:
            print(f"manual_change_number: Не удалось получить назначенный номер для оператора ID={operator_id}")
            logger.error("Не удалось получить назначенный номер для оператора.")
            return jsonify({"success": False, "message": "Не удалось получить назначенный номер для оператора."}), 500

        # Изменение номера для оператора
        operator_data = {
            "id": operator['id'],
            "operator_name": operator['operator_name'],
            "crm_id": operator['crm_id'],
            "megapbx_id": operator['megapbx_id'],
            "operator_type": operator['operator_type']
        }
        print(f"manual_change_number: Начало смены номера для оператора: {operator_data}")
        logger.info(f"Начало смены номера для оператора: {operator_data['operator_name']} (ID={operator_data['id']})")

        success = change_operator_number(operator_data, new_number)
        print(f"manual_change_number: Результат смены номера: {success}")
        logger.info(f"Результат смены номера для оператора ID={operator_id}: {success}")

        if success:
            logger.info(f"Номер для оператора '{operator['operator_name']}' успешно изменен на {new_number}")
            print(f"manual_change_number: Номер для оператора '{operator['operator_name']}' успешно изменен на {new_number}")

            return jsonify({
                "success": True,
                "message": f"Номер для '{operator['operator_name']}' успешно изменен на {new_number}"
            }), 200
        else:
            # Здесь можно уточнить причину ошибки
            print(f"manual_change_number: Ошибка при смене номера для оператора ID={operator_id}")
            logger.error("Ошибка при смене номера")
            return jsonify({"success": False, "message": "Ошибка при смене номера"}), 500
    except mysql.connector.Error as err:
        print(f"manual_change_number: Ошибка при получении оператора или смене номера: {err}")
        logger.error(f"Ошибка при получении оператора или смене номера: {err}")
        return jsonify({"success": False, "message": "Ошибка при смене номера"}), 500
    finally:
        cursor.close()
        conn.close()
        print("manual_change_number: Соединение с базой данных закрыто")
        logger.debug("Соединение с базой данных закрыто")

@vats_bp.route('/manual_change_number', methods=['POST'])
def manual_change_number_route():
    print("manual_change_number_route: Начало обработки запроса")
    logger.debug("manual_change_number_route: Начало обработки запроса")
    
    # Получаем значение группы из запроса
    selected_group = request.json.get('group')
    print(f"manual_change_number_route: Полученная группа: {selected_group}")
    logger.debug(f"manual_change_number_route: Полученная группа: {selected_group}")
    
    if selected_group:
        # Убираем пробелы для удобства сравнения
        selected_group = selected_group.replace(" ", "")
        print(f"manual_change_number_route: Группа после удаления пробелов: {selected_group}")
        logger.debug(f"manual_change_number_route: Группа после удаления пробелов: {selected_group}")
    else:
        print("manual_change_number_route: Группа не указана в запросе")
        logger.debug("manual_change_number_route: Группа не указана в запросе")
    
    # Определяем целевую группу (противоположную выбранной)
    # Используем lower() для устойчивого сравнения
    if selected_group.lower() == "лето":
        target = "НеЛето"
    elif selected_group.lower() in ["нелето", "нетлето"]:
        target = "Лето"
    else:
        target = None
    print(f"manual_change_number_route: Определена целевая группа: {target}")
    logger.debug(f"manual_change_number_route: Определена целевая группа: {target}")
    
    # Статическая мапа по CRM ID
    STATIC_CRM_IDS = {
        "Лето": "646",
        "НеЛето": "331"
    }
    
    def get_operator_id_by_crm(crm_id):
        conn = get_db_connection()
        if conn is None:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM vats_operators WHERE crm_id = %s", (crm_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return row['id']
        return None
    
    if target:
        operator_id = get_operator_id_by_crm(STATIC_CRM_IDS[target])
        print(f"manual_change_number_route: Получен operator_id по CRM {STATIC_CRM_IDS[target]}: {operator_id}")
        logger.debug(f"manual_change_number_route: Получен operator_id по CRM {STATIC_CRM_IDS[target]}: {operator_id}")
        if operator_id is None:
            return jsonify({"success": False, "message": f"Оператор с CRM ID {STATIC_CRM_IDS[target]} не найден"}), 404
    else:
        operator_id = session.get('id')
        print(f"manual_change_number_route: Целевая группа не определена, используем operator_id из сессии: {operator_id}")
        logger.debug(f"manual_change_number_route: Целевая группа не определена, используем operator_id из сессии: {operator_id}")
    
    print(f"manual_change_number_route: Вызов функции manual_change_number с operator_id: {operator_id}")
    logger.debug(f"manual_change_number_route: Вызов функции manual_change_number с operator_id: {operator_id}")
    
    result = manual_change_number(operator_id)
    print(f"manual_change_number_route: Результат работы manual_change_number: {result}")
    logger.debug(f"manual_change_number_route: Результат работы manual_change_number: {result}")
    return result


@vats_bp.route('/download_template', methods=['GET'])
def download_template():
    # Создание DataFrame с примерными данными
    df = pd.DataFrame({
        'Phone Number': ['79001234567', '79007654321']
    })

    # Создание временного файла
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        df.to_excel(tmp.name, index=False)
        tmp_path = tmp.name

    try:
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name='phone_numbers_template.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке шаблона: {e}")
        return jsonify({"success": False, "message": "Не удалось скачать шаблон"}), 500
    finally:
        # Удаление временного файла после отправки
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@vats_bp.route('/test_change_numbers', methods=['POST'])
def test_change_numbers():
    change_numbers_periodically()
    return jsonify({"success": True, "message": "Номер успешно изменен"}), 200