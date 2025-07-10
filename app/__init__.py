import os
from flask import Flask
from flask_login import LoginManager

def create_app():
    """
    Создает и настраивает экземпляр приложения Flask.
    """
    app = Flask(__name__)
    
    # Загрузка конфигурации
    app.config.from_object('app.config')

    # Инициализация LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.get_by_id(int(user_id))

    # Регистрация обработчиков контекста
    from app.context_processors import inject_permissions, inject_accessible_modules
    app.context_processor(inject_permissions)
    app.context_processor(inject_accessible_modules)

    # --- Регистрация всех Blueprints ---

    # Основные маршруты
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Админские маршруты
    from app.routes.admin.dashboard import admin_dashboard_bp
    app.register_blueprint(admin_dashboard_bp)
    
    from app.routes.admin.news import bp as admin_news_bp
    app.register_blueprint(admin_news_bp)

    from app.routes.admin.database import bp as admin_database_bp
    app.register_blueprint(admin_database_bp)
    
    from app.routes.admin.roles import roles_bp
    app.register_blueprint(roles_bp)
    
    from app.routes.admin.logs import bp as admin_logs_bp
    app.register_blueprint(admin_logs_bp)
    
    from app.routes.admin.organization import bp as admin_organization_bp
    app.register_blueprint(admin_organization_bp)

    from app.routes.admin import admin_routes_bp
    app.register_blueprint(admin_routes_bp)
    
    from app.admin import admin_bp
    app.register_blueprint(admin_bp)
    
    # Модули приложения
    from app.news import news_bp
    app.register_blueprint(news_bp)
    
    from app.rating import rating_bp
    app.register_blueprint(rating_bp)
    
    from app.leader import leader_bp
    app.register_blueprint(leader_bp)
    
    from app.callcenter import callcenter_bp
    app.register_blueprint(callcenter_bp)
    
    from app.helpdesk import helpdesk_bp
    app.register_blueprint(helpdesk_bp)
    
    from app.itinvent import itinvent_bp
    app.register_blueprint(itinvent_bp)
    
    from app.avito import avito_bp
    app.register_blueprint(avito_bp)
    
    from app.broker import broker_bp
    app.register_blueprint(broker_bp)

    from app.reception import reception_bp
    app.register_blueprint(reception_bp)
    
    from app.backoffice import backoffice_bp
    app.register_blueprint(backoffice_bp)
    
    from app.hr import hr_bp
    app.register_blueprint(hr_bp)
    
    # from app.utils import utils_bp
    # app.register_blueprint(utils_bp)
    
    from app.routes.api import api_bp
    app.register_blueprint(api_bp)

    # VATS модуль
    from app.vats import vats_bp
    app.register_blueprint(vats_bp)

    # Регистрируем функции для шаблонов
    from app.utils import register_template_functions
    register_template_functions(app)

    return app
