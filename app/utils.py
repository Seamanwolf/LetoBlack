import mysql.connector
from flask import current_app, session, flash, redirect, url_for, request, jsonify, Blueprint
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_login import login_required as flask_login_required, current_user
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import traceback
from mysql.connector import pooling
import configparser
import os
import logging
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import Cursor
from werkzeug.utils import secure_filename
from PIL import Image

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

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('У вас нет прав для доступа к этой странице', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_department():
    return session.get('department')

def create_db_connection():
    """
    Создает соединение с базой данных.
    Нужно всегда закрывать соединение после использования!
    """
    try:
        # Если используется пул соединений
        if 'pool' in globals():
            try:
                return pool.get_connection()
            except Exception as e:
                logger.error(f"Ошибка при получении соединения из пула: {e}")
                # Пробуем создать новое соединение, если пул не работает
                
        # Если пула нет или он не работает
        config = get_db_config()
        connection = mysql.connector.connect(**config)
        return connection
    except Exception as e:
        logger.error(f"Ошибка при создании соединения с БД: {e}")
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

def update_operator_status(user_id, status):
    try:
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("UPDATE User SET status = %s, last_active = NOW() WHERE id = %s", (status, user_id))
        connection.commit()
        
        # Получаем ukc_kc из новой таблицы user_ukc
        cursor.execute("""
        SELECT uk.ukc_kc 
        FROM user_ukc uk 
        WHERE uk.user_id = %s
        """, (user_id,))
        user = cursor.fetchone()
        
        if user:
            room = user['ukc_kc']
            # Дополнительная логика
            print(f"User {user_id} status updated to {status} in room {room}")
        else:
            print(f"User with ID {user_id} not found.")
    except Exception as e:
        print(f"Error updating operator status: {e}")
    finally:
        cursor.close()
        connection.close()


def authenticate_user(username, password):
    connection = create_db_connection()
    if connection is None:
        current_app.logger.error("Нет подключения к базе данных для аутентификации.")
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, login, full_name, role, password FROM User WHERE login = %s AND fired = FALSE", (username,))
        user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            return user
        else:
            return None
    except mysql.connector.Error as err:
        current_app.logger.error(f"Ошибка при аутентификации пользователя: {err}")
        return None
    finally:
        cursor.close()
        connection.close()

def get_notifications_count(user_id=None):
    role = session.get('role')  # Роль текущего пользователя

    if not role:
        print("Роль пользователя не установлена в сессии")  # Отладка отсутствия роли
        return 0  # Или другое значение по умолчанию, например, None
    
    # Пользовательский ID игнорируется в текущей реализации, но может использоваться в будущем
    # для фильтрации по конкретному пользователю

    # Подключение к базе данных
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Составление запроса с фильтрацией по роли
    query = """
    SELECT COUNT(*) as count
    FROM Notifications
    WHERE is_for_{role} = TRUE
    """.format(role=role)

    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return result['count'] if result else 0

def get_department_weekly_stats(department):
    current_user_id = session.get('id')
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    
    # Формируем список полей для выборки, исключая поля, которые будут взяты за конкретный день
    sum_fields = [
        'deals', 'reservations', 'online_showings', 'offline_showings', 'repeat_showings',
        'new_clients', 'cold_calls', 'adscian', 'adsavito', 'mailouts', 'resales',
        'banners', 'results', 'exclusives', 'stories', 'incoming_cold_calls', 'stationary_calls'
    ]
    
    # Создаем часть SQL-запроса для выборки суммируемых полей
    sum_fields_sql = ",\n".join([f"SUM(Scores.{field}) as {field}" for field in sum_fields])
    
    # Добавляем поля для конкретного дня с условием
    # Предполагается, что за каждый день для пользователя может быть только одна запись
    total_ads_cian_sql = f"MAX(CASE WHEN Scores.date = '{end_date}' THEN Scores.total_ads_cian ELSE 0 END) as total_ads_cian"
    total_ads_avito_sql = f"MAX(CASE WHEN Scores.date = '{end_date}' THEN Scores.total_ads_avito ELSE 0 END) as total_ads_avito"
    
    query = f"""
    SELECT 
        User.id,
        User.full_name,
        {sum_fields_sql},
        {total_ads_cian_sql},
        {total_ads_avito_sql}
    FROM Scores
    JOIN User ON Scores.user_id = User.id
    WHERE User.department = %s 
      AND Scores.date >= %s 
      AND Scores.date <= %s
    GROUP BY User.id, User.full_name
    """
    
    cursor.execute(query, (department, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    stats = cursor.fetchall()
    cursor.close()
    connection.close()
    
    return stats

@utils_bp.route('/department_statistics/daily', methods=['POST'])
@login_required
def department_daily_statistics():
    if current_user.role != 'leader':
        return jsonify({'error': 'Доступ запрещен'}), 403

    selected_date = request.form.get('selected_date')
    department_id = session.get('department')

    start_date = datetime.strptime(selected_date, '%Y-%m-%d')
    end_date = start_date

    return get_department_statistics(department_id, start_date, end_date)

@utils_bp.route('/department_statistics/weekly', methods=['POST'])
@login_required
def department_weekly_statistics():
    if current_user.role != 'leader':
        return jsonify({'error': 'Доступ запрещен'}), 403

    department_id = session.get('department')

    # Получаем текущую дату и вычисляем диапазон прошлой недели
    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday() + 7)  # Начало прошлой недели (понедельник)
    end_of_week = start_of_week + timedelta(days=6)  # Конец прошлой недели (воскресенье)

    start_date = start_of_week
    end_date = end_of_week

    return get_department_statistics(department_id, start_date, end_date)


@utils_bp.route('/department_statistics/monthly', methods=['POST'])
@login_required
def department_monthly_statistics():
    if current_user.role != 'leader':
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


@utils_bp.route('/department_statistics/yearly', methods=['POST'])
@login_required
def department_yearly_statistics():
    if current_user.role != 'leader':
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


@utils_bp.route('/department_statistics/custom', methods=['POST'])
@login_required
def department_custom_statistics():
    if current_user.role != 'leader':
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

def sync_with_google_sheets(data):
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread

    # Настройка авторизации
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(credentials)

    # Открытие Google Таблицы
    sheet = client.open_by_url('URL ВАШЕЙ GOOGLE ТАБЛИЦЫ')  # Подставьте URL таблицы
    worksheet = sheet.get_worksheet(0)  # Первый лист

    # Добавление данных
    worksheet.append_row(data)

def close_all_connections():
    """Закрывает все активные соединения с базой данных и пересоздает пул"""
    logger.info("Запрос на закрытие всех соединений с базой данных")
    try:
        # Закрытие всех соединений на стороне сервера
        config = get_db_config()
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        # Сначала получаем список всех соединений для нашего пользователя
        cursor.execute("SHOW PROCESSLIST")
        processes = cursor.fetchall()
        
        # Подсчитываем и закрываем соединения
        count = 0
        for process in processes:
            process_id = process[0]
            user = process[1]
            host = process[2]
            
            # Закрываем только соединения нашего пользователя
            if user == config['user']:
                try:
                    cursor.execute(f"KILL {process_id}")
                    count += 1
                    logger.debug(f"Закрыто соединение ID: {process_id}, User: {user}, Host: {host}")
                except Exception as e:
                    logger.warning(f"Не удалось закрыть соединение {process_id}: {str(e)}")
        
        logger.info(f"Закрыто {count} соединений с базой данных")
        
        # Закрываем текущее соединение
        cursor.close()
        conn.close()
        
        # Пересоздаем пул соединений, если он существует
        global pool
        if 'pool' in globals() and pool is not None:
            try:
                pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="mypool",
                    pool_size=30,
                    pool_reset_session=True,
                    **config,
                    use_pure=True,
                    autocommit=True,
                    connection_timeout=5,
                    time_zone='+03:00'
                )
                logger.info("Пул подключений к базе данных успешно пересоздан.")
            except Exception as e:
                logger.error(f"Ошибка при пересоздании пула подключений: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при закрытии соединений: {str(e)}")
        return False

def get_db_config():
    """Получает конфигурацию подключения к базе данных"""
    config = {
        'host': '192.168.2.225',
        'port': 3306,
        'user': 'test_user',
        'password': 'password',
        'database': 'Brokers'
    }
    
    # Пытаемся загрузить конфигурацию из файла
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    if os.path.exists(config_path):
        try:
            cfg = configparser.ConfigParser()
            cfg.read(config_path)
            if 'database' in cfg:
                for key in config.keys():
                    if key in cfg['database']:
                        config[key] = cfg['database'][key]
            else:
                logger.warning(f"В файле {config_path} отсутствует секция 'database'. Используем параметры из config.env.")
        except Exception as e:
            logger.error(f"Ошибка при чтении файла конфигурации {config_path}: {str(e)}")
    
    # Пытаемся загрузить из переменных окружения через config.env
    env_vars = {
        'DB_HOST': 'host',
        'DB_PORT': 'port',
        'DB_USER': 'user',
        'DB_PASSWORD': 'password',
        'DB_NAME': 'database'
    }
    
    for env_var, config_key in env_vars.items():
        env_value = os.getenv(env_var)
        if env_value:
            config[config_key] = env_value
    
    return config

class DBConnectionManager:
    """
    Контекстный менеджер для автоматического закрытия соединений с БД
    Использование:
    with DBConnectionManager() as conn:
        cursor = conn.cursor()
        # выполняем операции с БД
    # соединение автоматически закрывается при выходе из блока with
    """
    def __init__(self):
        self.connection = None
        
    def __enter__(self):
        self.connection = create_db_connection()
        return self.connection
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            try:
                self.connection.close()
            except Exception as e:
                logger.error(f"Ошибка при закрытии соединения: {e}")

def save_uploaded_file(file, target_dir, filename):
    """
    Сохраняет загруженный файл с заданным именем в указанную директорию.
    
    Args:
        file: FileStorage объект из Flask
        target_dir: директория для сохранения
        filename: желаемое имя файла
    
    Returns:
        str: путь к сохраненному файлу
    """
    # Создаем директорию, если она не существует
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    file_path = os.path.join(target_dir, filename)
    
    try:
        # Открываем изображение с помощью PIL
        img = Image.open(file)
        
        # Конвертируем в нужный формат
        if filename.endswith('.bmp'):
            img.save(file_path, 'BMP')
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            img.save(file_path, 'JPEG')
        elif filename.endswith('.png'):
            img.save(file_path, 'PNG')
        else:
            # Если формат не поддерживается, сохраняем как есть
            file.save(file_path)
            
        return file_path
    except Exception as e:
        current_app.logger.error(f"Ошибка при сохранении файла: {str(e)}")
        raise

def save_logo(file):
    """
    Сохраняет логотип компании.
    
    Args:
        file: FileStorage объект из Flask
    
    Returns:
        str: путь к сохраненному файлу
    """
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images')
    return save_uploaded_file(file, static_dir, 'logo.bmp')

def save_background(file):
    """
    Сохраняет фоновое изображение.
    
    Args:
        file: FileStorage объект из Flask
    
    Returns:
        str: путь к сохраненному файлу
    """
    images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images')
    return save_uploaded_file(file, images_dir, 'real_estate_bg.jpg')

