import os
import configparser
from datetime import timedelta

# Загрузка конфигурации из файла config.ini
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config = configparser.ConfigParser()

# Если файл конфигурации существует, загружаем его
if os.path.exists(config_path):
    config.read(config_path)
else:
    # Иначе используем значения по умолчанию
    config['database'] = {
        'host': '192.168.2.225',
        'port': '3306',
        'user': 'root',
        'password': 'Podego53055',
        'database': 'Brokers'
    }
    config['app'] = {
        'secret_key': 'your-secret-key-here',
        'upload_folder': '/home/helpdesk_leto/attach/',
        'attachments_server_url': 'http://192.168.2.112/'
    }
    
    # Сохраняем конфигурацию по умолчанию
    try:
        with open(config_path, 'w') as f:
            config.write(f)
    except Exception as e:
        print(f"Ошибка при создании файла конфигурации: {e}")

# Класс конфигурации для Flask-приложения
class Config:
    # Секретный ключ для сессий
    SECRET_KEY = config.get('app', 'secret_key', fallback='your-secret-key-here')
    
    # Конфигурация базы данных
    db_config = {
        'host': config.get('database', 'host', fallback='192.168.2.225'),
        'port': int(config.get('database', 'port', fallback='3306')),
        'user': config.get('database', 'user', fallback='root'),
        'password': config.get('database', 'password', fallback='Podego53055'),
        'database': config.get('database', 'database', fallback='Brokers'),
    }
    
    # Параметры сессий
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # Папка для загрузки файлов
    UPLOAD_FOLDER = config.get('app', 'upload_folder', fallback='/home/helpdesk_leto/attach/')
    
    # URL сервера вложений
    ATTACHMENTS_SERVER_URL = config.get('app', 'attachments_server_url', fallback='http://192.168.2.112/')
    
    # Папка для загрузки файлов средних сделок
    AVG_DEALS_UPLOAD_FOLDER = '/home/user/avg_deals_uploads'
    
    # Папка для логов
    LOG_FOLDER = 'logs'
    
    # Настройки для Flask-SocketIO
    CORS_ALLOWED_ORIGINS = "*"
    
    # Папка для статических файлов
    STATIC_FOLDER = 'static'
    
    # URL-путь для статических файлов
    STATIC_URL_PATH = '/static'
    
    # Общие настройки приложения
    DEBUG = False
    TESTING = False 