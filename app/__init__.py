from flask import Flask
from flask_login import LoginManager
from config import Config
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import os
from flask import render_template
from app.utils import execute_sql_file

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, авторизуйтесь для доступа к этой странице.'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    """Создание и настройка экземпляра приложения"""
    app = Flask(__name__, 
                static_folder=config_class.STATIC_FOLDER,
                static_url_path=config_class.STATIC_URL_PATH)
    app.config.from_object(config_class)
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # Создаем директорию для статических файлов, если она не существует
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_class.STATIC_FOLDER)
    images_dir = os.path.join(static_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # Инициализация расширений с приложением
    login_manager.init_app(app)
    
    # Импорт и регистрация контекстных процессоров
    from app import context_processors
    context_processors.init_app(app)
    
    # Импорт моделей
    from app.models import User
    from app.models.role import Role
    from app.models.permission import Permission
    from app.models.system_module import SystemModule
    from app.models.department import Department
    from app.models.position import Position
    from app.models.location import Location
    from app.models.employee import Employee
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))
    
    # Создание таблиц организационной структуры
    sql_file = os.path.join(os.path.dirname(__file__), 'sql', 'create_organization_tables.sql')
    logger.info(f"Путь к SQL-файлу: {sql_file}")
    logger.info(f"Файл существует: {os.path.exists(sql_file)}")
    
    if os.path.exists(sql_file):
        result = execute_sql_file(sql_file)
        logger.info(f"Результат выполнения SQL-файла: {result}")
    else:
        logger.error(f"SQL-файл не найден: {sql_file}")
    
    # Импорт и регистрация маршрутов
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.admin import admin_bp
    from app.routes.admin import admin_routes_bp
    from app.routes.admin.roles import roles_bp
    from app.routes.admin.organization import bp as admin_organization_bp
    from app.routes.admin.dashboard import admin_dashboard_bp
    from app.callcenter.callcenter import callcenter_bp
    from app.vats.vats import vats_bp
    from app.avito.avito import avito_bp
    from app.helpdesk.helpdesk import helpdesk_bp
    from app.reception import reception_bp
    from app.rating.rating import rating_bp
    from app.itinvent.itinvent import itinvent_bp
    from app.userlist.userlist import userlist_bp
    from app.news import news_bp
    from app.routes.api import api_bp
    
    logger.debug("Регистрация маршрутов...")
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(admin_organization_bp, url_prefix='/admin')
    app.register_blueprint(admin_dashboard_bp)
    app.register_blueprint(callcenter_bp)
    app.register_blueprint(vats_bp)
    app.register_blueprint(avito_bp)
    app.register_blueprint(helpdesk_bp)
    app.register_blueprint(reception_bp)
    app.register_blueprint(rating_bp)
    app.register_blueprint(itinvent_bp)
    app.register_blueprint(userlist_bp)
    app.register_blueprint(news_bp, url_prefix='/news')
    
    # Регистрируем admin_routes_bp с префиксом /admin
    logger.debug("Регистрация admin_routes_bp с префиксом /admin")
    app.register_blueprint(admin_routes_bp, url_prefix='/admin', name='admin_routes_unique')
    
    # Регистрируем api_bp с префиксом /api
    logger.debug("Регистрация api_bp с префиксом /api")
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Регистрируем admin_bp с префиксом /admin_old
    logger.debug("Регистрация admin_bp с префиксом /admin_old")
    app.register_blueprint(admin_bp, url_prefix='/admin_old', name='admin_old_unique')
    
    logger.debug("Все маршруты зарегистрированы")
    
    # Импорт и регистрация CLI команд
    from app import commands
    commands.init_app(app)
    
    # Обработчики ошибок
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
    
    # Планировщик задач
    scheduler = BackgroundScheduler(timezone='Europe/Moscow')
    
    # Задача для очистки подключений к базе данных
    def clean_db_connections():
        logging.info("Очистка подключений к базе данных")
        from app.utils import close_all_connections
        close_all_connections()
    
    # Запускаем задачу очистки каждые 10 минут
    scheduler.add_job(func=clean_db_connections, trigger="interval", minutes=10)
    
    # Запускаем планировщик
    scheduler.start()
    
    # Завершаем планировщик при завершении приложения
    atexit.register(lambda: scheduler.shutdown())
    
    # Настройка логгера на уровне приложения
    app.logger = logging.getLogger(__name__)
    
    # Добавляем контекстный процессор для доступа к модулям
    @app.context_processor
    def inject_accessible_modules():
        def get_accessible_modules():
            from app.utils import get_user_accessible_modules
            from flask_login import current_user
            
            if current_user.is_authenticated:
                return get_user_accessible_modules(current_user)
            return []
            
        return {'get_accessible_modules': get_accessible_modules}
    
    return app
