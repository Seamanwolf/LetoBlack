from functools import wraps
from flask import flash, redirect, url_for, abort, request
from flask_login import current_user

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
        admin_role = any(role.name == 'admin' for role in current_user.roles)
        if not admin_role:
            flash('У вас недостаточно прав для доступа к этой странице', 'danger')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    
    return decorated_function

def role_required(role_name):
    """
    Декоратор, который проверяет, что текущий пользователь имеет указанную роль.
    В противном случае перенаправляет на главную страницу.
    
    Args:
        role_name (str): Название роли, которая требуется для доступа
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
                
            # Проверяем наличие указанной роли у пользователя
            has_role = any(role.name == role_name for role in current_user.roles)
            if not has_role:
                flash('У вас недостаточно прав для доступа к этой странице', 'danger')
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
            admin_role = any(role.name == 'admin' for role in current_user.roles)
            if admin_role:
                return f(*args, **kwargs)
                
            # Проверяем наличие разрешения у пользователя через его роли
            has_permission = False
            for role in current_user.roles:
                if role.has_permission(module_name, action):
                    has_permission = True
                    break
            
            if not has_permission:
                flash(f'У вас недостаточно прав для {action} в модуле {module_name}', 'danger')
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
    admin_role = any(role.name == 'admin' for role in current_user.roles)
    if admin_role:
        return True
        
    # Проверяем наличие разрешения у пользователя через его роли
    for role in current_user.roles:
        if role.has_permission(module_name, action):
            return True
    
    return False 