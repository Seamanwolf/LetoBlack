from flask_login import current_user
from app.decorators import has_permission
from app.utils import get_user_accessible_modules

def inject_permissions():
    """
    Добавляет функцию для проверки разрешений в шаблонах
    """
    def check_permission(module_name, action):
        """
        Проверяет разрешение на выполнение действия в указанном модуле
        
        Args:
            module_name (str): Название модуля
            action (str): Название действия (view, create, edit, delete)
            
        Returns:
            bool: True, если у пользователя есть разрешение, иначе False
        """
        return has_permission(module_name, action)
    
    def check_role(role_name):
        """
        Проверяет наличие указанной роли у пользователя
        
        Args:
            role_name (str): Название роли
            
        Returns:
            bool: True, если у пользователя есть указанная роль, иначе False
        """
        if not current_user.is_authenticated:
            return False
        return current_user.has_role(role_name)
    
    def get_user_roles():
        """
        Возвращает список ролей текущего пользователя
        
        Returns:
            list: Список объектов ролей пользователя
        """
        if not current_user.is_authenticated:
            return []
        return list(current_user.roles)
    
    return dict(
        has_permission=check_permission,
        has_role=check_role,
        get_user_roles=get_user_roles
    )

def inject_accessible_modules():
    """
    Добавляет список доступных модулей в контекст шаблонов
    """
    if current_user.is_authenticated:
        accessible_modules = get_user_accessible_modules(current_user)
    else:
        accessible_modules = []
    return dict(accessible_modules=accessible_modules) 