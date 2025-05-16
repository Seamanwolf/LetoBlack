from flask import current_app, session, flash, redirect, url_for, request, jsonify, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_login import login_required as flask_login_required, current_user
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import traceback
import os
import logging
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import Cursor
from werkzeug.utils import secure_filename

utils_bp = Blueprint('utils', __name__)

logger = logging.getLogger(__name__)

# Класс-обертка для курсора, который преобразует результаты в словари
class DictCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self.description = cursor.description
    
    def fetchone(self):
        row = self.cursor.fetchone()
        if row:
            return dict(zip([col[0] for col in self.cursor.description], row))
        return None
    
    def fetchall(self):
        rows = self.cursor.fetchall()
        if rows:
            column_names = [col[0] for col in self.cursor.description]
            return [dict(zip(column_names, row)) for row in rows]
        return []
    
    def __getattr__(self, attr):
        return getattr(self.cursor, attr)

# Конфигурация для подключения к БД
import configparser
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')

# Загружаем переменные окружения из config.env
load_dotenv('config.env')

# Стандартные параметры подключения, если файл конфигурации не найден
default_db_config = {
    'host': os.getenv('DB_HOST', '192.168.2.225'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'test_user'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'Brokers')
}

# Пробуем загрузить параметры из файла конфигурации
try:
    if os.path.exists(config_path):
        config.read(config_path)
        
        # Проверяем, существует ли секция 'database'
        if config.has_section('database'):
            db_config = {
                'host': config.get('database', 'host'),
                'user': config.get('database', 'user'),
                'password': config.get('database', 'password'),
                'database': config.get('database', 'database')
            }
            
            # Если указан порт, добавляем его
            if config.has_option('database', 'port'):
                db_config['port'] = config.getint('database', 'port')
                
            logger.info(f"Загружена конфигурация БД из файла: {config_path}")
        else:
            logger.warning(f"В файле {config_path} отсутствует секция 'database'. Используем параметры из config.env.")
            db_config = default_db_config
    else:
        logger.warning(f"Файл конфигурации {config_path} не найден. Используем параметры из config.env.")
        db_config = default_db_config
        
    # Создаем подключение к базе данных через PyMySQL
    try:
        # Проверяем подключение
        connection = pymysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            port=db_config['port'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor
        )
        connection.close()
        logger.info("Проверка подключения к базе данных успешна.")
    except Exception as e:
        logger.error(f"Ошибка при проверке подключения к базе данных: {e}")
except Exception as err:
    logger.error(f"Ошибка при инициализации конфигурации БД: {err}")
    db_config = default_db_config

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Пожалуйста, авторизуйтесь для доступа к этой странице.", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_department():
    return session.get('department')

def create_db_connection():
    """
    Создает соединение с базой данных используя PyMySQL
    """
    try:
        # Подключаемся напрямую через PyMySQL
        connection = pymysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            port=db_config['port'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor
        )
        return connection
    except Exception as err:
        logger.error(f"Ошибка при подключении к базе данных: {err}")
        return None

# Переопределяем метод cursor для автоматического оборачивания в DictCursorWrapper
# если запрошен dictionary=True
original_cursor = pymysql.connections.Connection.cursor

def patched_cursor(self, *args, **kwargs):
    dictionary = kwargs.pop('dictionary', False)
    cursor = original_cursor(self, *args, **kwargs)
    if dictionary:
        return DictCursorWrapper(cursor)
    return cursor

# Применяем патч
pymysql.connections.Connection.cursor = patched_cursor

def update_user_activity(user_id, status):
    """
    Обновляет статус активности пользователя
    """
    connection = create_db_connection()
    if connection is None:
        logger.error("Нет подключения к базе данных для обновления статуса активности.")
        return False

    cursor = None
    try:
        cursor = connection.cursor()
        
        # Проверяем, есть ли уже запись для пользователя
        cursor.execute("SELECT id FROM UserActivity WHERE user_id = %s", (user_id,))
        activity = cursor.fetchone()
        
        if activity:
            # Обновляем существующую запись
            cursor.execute(
                "UPDATE UserActivity SET status = %s, last_activity = NOW(), updated_at = NOW() WHERE user_id = %s", 
                (status, user_id)
            )
        else:
            # Создаем новую запись
            cursor.execute(
                "INSERT INTO UserActivity (user_id, status, last_activity) VALUES (%s, %s, NOW())", 
                (user_id, status)
            )
        
        connection.commit()
        logger.info(f"Статус пользователя с ID {user_id} обновлён на {status}.")
        return True
    except Exception as err:
        if connection:
            connection.rollback()
        logger.error(f"Ошибка при обновлении статуса активности пользователя: {err}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_user_status(user_id):
    """
    Получает текущий статус активности пользователя
    """
    connection = create_db_connection()
    if connection is None:
        logger.error("Нет подключения к базе данных для получения статуса активности.")
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT status, last_activity FROM UserActivity WHERE user_id = %s", 
            (user_id,)
        )
        result = cursor.fetchone()
        return result
    except Exception as err:
        logger.error(f"Ошибка при получении статуса активности пользователя: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_department_weekly_stats(department):
    """
    Получает статистику по отделу за последнюю неделю
    """
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    
    # Формируем список полей для выборки
    sum_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'incoming_cold_calls', 'stationary_calls'
    ]
    
    # Создаем часть SQL-запроса для выборки суммируемых полей
    sum_fields_sql = ",\n".join([f"SUM(Scores.{field}) as {field}" for field in sum_fields])
    
    query = f"""
    SELECT 
        {sum_fields_sql}
    FROM Scores
    JOIN User ON Scores.user_id = User.id
    WHERE 
        User.department = %s AND 
        Scores.date BETWEEN %s AND %s
    """
    
    cursor.execute(query, (department, start_date, end_date))
    result = cursor.fetchone()
    
    cursor.close()
    connection.close()
    
    return result

def get_notifications_count(user_id=None):
    """
    Получает количество уведомлений для текущего пользователя по роли
    Параметр user_id в текущей реализации не используется, но может понадобиться в будущем
    """
    role = session.get('role')
    
    if not role:
        logger.warning("Роль пользователя не установлена в сессии")
        return 0
    
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    # Теперь запрос фильтрует по роли из Roles
    query = f"""
    SELECT COUNT(*) as count
    FROM Notifications n
    JOIN Roles r ON n.role_id = r.id
    WHERE r.name = %s
    """
    
    cursor.execute(query, (role,))
    result = cursor.fetchone()
    
    cursor.close()
    connection.close()
    
    return result['count'] if result else 0

def get_user_info(user_id):
    """
    Получает полную информацию о пользователе, включая роль, статус активности и настройки колл-центра
    """
    connection = create_db_connection()
    if connection is None:
        logger.error("Нет подключения к базе данных для получения информации о пользователе.")
        return None

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            u.id, 
            u.login, 
            u.full_name, 
            u.department,
            u.department_id,
            r.name as role,
            r.display_name as role_display_name,
            c.ukc_kc,
            a.status,
            a.last_activity,
            u.hired_date,
            u.fire_date,
            u.fired,
            u.position,
            u.personal_email,
            u.pc_login,
            u.Phone,
            u.office,
            u.corp_phone
        FROM User u
        LEFT JOIN Roles r ON u.role_id = r.id
        LEFT JOIN CallCenterSettings c ON u.id = c.user_id
        LEFT JOIN UserActivity a ON u.id = a.user_id
        WHERE u.id = %s
        """
        
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        
        return result
    except Exception as err:
        logger.error(f"Ошибка при получении информации о пользователе: {err}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def execute_sql_file(file_path):
    """
    Выполняет SQL-скрипт из указанного файла через подключение к базе данных.
    Возвращает True при успехе, иначе False.
    """
    import pymysql
    try:
        connection = create_db_connection()
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        with connection.cursor() as cursor:
            for statement in sql.split(';'):
                stmt = statement.strip()
                if stmt:
                    cursor.execute(stmt)
        connection.commit()
        return True
    except Exception as e:
        print(f"Ошибка при выполнении SQL-файла: {e}")
        if 'connection' in locals():
            connection.rollback()
        return False
    finally:
        if 'connection' in locals():
            connection.close()

def update_operator_status(operator_id, status):
    """
    Обновляет статус оператора (онлайн/оффлайн)
    """
    connection = create_db_connection()
    if connection is None:
        logger.error("Нет подключения к базе данных для обновления статуса оператора.")
        return False

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE UserActivity SET status = %s, last_activity = NOW(), updated_at = NOW() WHERE user_id = %s",
            (status, operator_id)
        )
        connection.commit()
        logger.info(f"Статус оператора с ID {operator_id} обновлён на {status}.")
        return True
    except Exception as err:
        if connection:
            connection.rollback()
        logger.error(f"Ошибка при обновлении статуса оператора: {err}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("У вас нет прав для доступа к этой странице.", "danger")
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def save_logo(file):
    """
    Сохраняет загруженный логотип в директорию static/images.
    Возвращает путь к сохранённому файлу или None в случае ошибки.
    """
    if file and file.filename:
        filename = secure_filename(file.filename)
        logo_path = os.path.join(current_app.static_folder, 'images', filename)
        file.save(logo_path)
        return os.path.join('images', filename)
    return None

def save_background(file):
    """
    Сохраняет загруженный фоновый файл в директорию static/images.
    Возвращает путь к сохранённому файлу или None в случае ошибки.
    """
    if file and file.filename:
        filename = secure_filename(file.filename)
        background_path = os.path.join(current_app.static_folder, 'images', filename)
        file.save(background_path)
        return os.path.join('images', filename)
    return None

def authenticate_user(login, password):
    """Аутентификация пользователя"""
    try:
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем пользователя
        cursor.execute("""
            SELECT u.*, r.name as role_name, r.type as role_type
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN roles r ON ur.role_id = r.id
            WHERE u.login = %s
        """, (login,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return None
            
        # Проверяем пароль
        if not check_password_hash(user_data['password'], password):
            return None
            
        # Создаем объект пользователя
        user = User(
            id=user_data['id'],
            login=user_data['login'],
            full_name=user_data['full_name'],
            role=user_data['role_name'],
            department=user_data['department']
        )
        
        # Добавляем дополнительные атрибуты
        user.role_type = user_data['role_type']
        user.is_active = user_data['is_active']
        user.last_login = user_data['last_login']
        
        return user
        
    except Exception as e:
        print(f"Ошибка аутентификации: {str(e)}")
        return None
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_user_accessible_modules(user):
    """
    Получает список доступных модулей для пользователя
    
    Args:
        user: Объект пользователя
        
    Returns:
        list: Список доступных модулей
    """
    if not user:
        return []
        
    # Базовые модули, доступные всем пользователям
    modules = ['profile', 'news']
    
    # Добавляем модули в зависимости от роли пользователя
    if user.is_admin:
        modules.extend(['admin', 'personnel', 'settings'])
    elif user.is_hr():
        modules.extend(['hr', 'personnel'])
    elif user.is_leader():
        modules.extend(['leader', 'rating'])
    elif user.is_callcenter():
        modules.extend(['callcenter'])
    elif user.is_helpdesk():
        modules.extend(['helpdesk'])
    elif user.is_itinvent():
        modules.extend(['itinvent'])
    elif user.is_avito():
        modules.extend(['avito'])
    elif user.is_reception():
        modules.extend(['reception'])
    elif user.is_backoffice():
        modules.extend(['backoffice'])
    elif user.is_vats():
        modules.extend(['vats'])
        
    return modules 