from functools import wraps
from flask import flash, redirect, url_for, abort, request
from flask_login import current_user
from app.utils import show_toast

def admin_required(f):
    """
    Декоратор, который проверяет, что текущий пользователь имеет роль администратора.
    В противном случае перенаправляет на главную страницу.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
            
        # Проверяем наличие роли admin у пользователя
        admin_role = False
        
        # Поддержка старого способа (через прямой атрибут role)
        if hasattr(current_user, 'role') and current_user.role == 'admin':
            admin_role = True
        
        # Поддержка нового способа (через свойство roles)
        elif hasattr(current_user, 'roles') and current_user.roles:
            admin_role = any(role.name == 'admin' for role in current_user.roles)
            
        if not admin_role:
            show_toast('У вас недостаточно прав для доступа к этой странице', 'error')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    
    return decorated_function

def role_required(role_name):
    """
    Декоратор, который проверяет, что текущий пользователь имеет указанную роль.
    В противном случае перенаправляет на главную страницу.
    
    Args:
        role_name (str or list): Название роли или список ролей, одна из которых требуется для доступа
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
                
            # Проверяем наличие указанной роли у пользователя
            has_role = False
            
            # Преобразуем аргумент role_name в список, если это строка
            roles = role_name if isinstance(role_name, list) else [role_name]
            
            # Поддержка старого способа (через прямой атрибут role)
            if hasattr(current_user, 'role') and current_user.role in roles:
                has_role = True
            
            # Поддержка нового способа (через свойство roles)
            elif hasattr(current_user, 'roles') and current_user.roles:
                has_role = any(role.name in roles for role in current_user.roles)
                
            if not has_role:
                show_toast('У вас недостаточно прав для доступа к этой странице', 'error')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator

def permission_required(module_name, action):
    """
    Декоратор, который проверяет, что текущий пользователь имеет разрешение
    на выполнение указанного действия в указанном модуле.
    
    Args:
        module_name (str): Название модуля
        action (str): Название действия (view, create, edit, delete)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            # Проверяем наличие роли admin у пользователя (у админа есть все права)
            admin_role = False
            
            # Поддержка старого способа (через прямой атрибут role)
            if hasattr(current_user, 'role') and current_user.role == 'admin':
                admin_role = True
            
            # Поддержка нового способа (через свойство roles)
            elif hasattr(current_user, 'roles') and current_user.roles:
                admin_role = any(role.name == 'admin' for role in current_user.roles)
                
            if admin_role:
                return f(*args, **kwargs)
                
            # Проверяем наличие разрешения у пользователя через его роли
            has_permission = False
            
            # Для новой системы ролей
            if hasattr(current_user, 'roles') and current_user.roles:
                for role in current_user.roles:
                    if hasattr(role, 'has_permission') and role.has_permission(module_name, action):
                        has_permission = True
                        break
            
            if not has_permission:
                show_toast(f'У вас недостаточно прав для {action} в модуле {module_name}', 'error')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator

def has_permission(module_name, action):
    """
    Функция для проверки, имеет ли текущий пользователь разрешение 
    на выполнение указанного действия в указанном модуле.
    
    Args:
        module_name (str): Название модуля
        action (str): Название действия (view, create, edit, delete)
        
    Returns:
        bool: True, если у пользователя есть разрешение, иначе False
    """
    if not current_user.is_authenticated:
        return False
    
    # У администратора есть все права
    admin_role = False
            
    # Поддержка старого способа (через прямой атрибут role)
    if hasattr(current_user, 'role') and current_user.role == 'admin':
        admin_role = True
    
    # Поддержка нового способа (через свойство roles)
    elif hasattr(current_user, 'roles') and current_user.roles:
        admin_role = any(role.name == 'admin' for role in current_user.roles)
        
    if admin_role:
        return True
        
    # Проверяем наличие разрешения у пользователя через его роли (для новой системы)
    if hasattr(current_user, 'roles') and current_user.roles:
        for role in current_user.roles:
            if hasattr(role, 'has_permission') and role.has_permission(module_name, action):
                return True
    
    return False 