from flask_login import UserMixin

class User(UserMixin):
    """
    Модель пользователя для работы с Flask-Login
    """
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 0)
        self.login = kwargs.get('login', '')
        self.full_name = kwargs.get('full_name', '')
        self.role = kwargs.get('role', 'user')  # название роли из таблицы Roles
        self.department = kwargs.get('department', '')
        self.department_id = kwargs.get('department_id')
        self.ukc_kc = kwargs.get('ukc_kc')  # теперь из таблицы CallCenterSettings
        self.status = kwargs.get('status', 'offline')  # теперь из таблицы UserActivity
        self.last_active = kwargs.get('last_activity')  # теперь из таблицы UserActivity
        self.position = kwargs.get('position', '')
        self.hire_date = kwargs.get('hire_date')
        self.fire_date = kwargs.get('fire_date')
        self.fired = kwargs.get('fired', False)
        self.role_display_name = kwargs.get('role_display_name', '')
        self.role_type = kwargs.get('role_type', 'custom')
        self.is_system_role = kwargs.get('is_system', False)
        self._permissions = kwargs.get('permissions', {})  # словарь разрешений {module_name: {can_view: bool, can_edit: bool, ...}}
        
    def is_admin(self):
        """Проверяет, является ли пользователь администратором"""
        return self.role == 'admin'
        
    def is_leader(self):
        """Проверяет, является ли пользователь руководителем"""
        return self.role == 'leader'
        
    def is_operator(self):
        """Проверяет, является ли пользователь оператором колл-центра"""
        return self.role == 'operator'
        
    def is_backoffice(self):
        """Проверяет, является ли пользователь бэк-офисом"""
        return self.role_type == 'backoffice'
        
    def is_active(self):
        """Определяет, активен ли аккаунт пользователя"""
        return not self.fired
        
    def is_online(self):
        """Проверяет, онлайн ли пользователь"""
        return self.status == 'online'
    
    def has_module_access(self, module_name):
        """Проверяет, имеет ли пользователь доступ к модулю"""
        # Администратор имеет доступ ко всем модулям
        if self.is_admin():
            return True
            
        if module_name in self._permissions:
            return self._permissions[module_name].get('can_view', False)
            
        return False
        
    def can_create(self, module_name):
        """Проверяет, может ли пользователь создавать в модуле"""
        if self.is_admin():
            return True
            
        if module_name in self._permissions:
            return self._permissions[module_name].get('can_create', False)
            
        return False
        
    def can_edit(self, module_name):
        """Проверяет, может ли пользователь редактировать в модуле"""
        if self.is_admin():
            return True
            
        if module_name in self._permissions:
            return self._permissions[module_name].get('can_edit', False)
            
        return False
        
    def can_delete(self, module_name):
        """Проверяет, может ли пользователь удалять в модуле"""
        if self.is_admin():
            return True
            
        if module_name in self._permissions:
            return self._permissions[module_name].get('can_delete', False)
            
        return False
    
    def get_accessible_modules(self):
        """Возвращает список модулей, к которым у пользователя есть доступ"""
        if self.is_admin():
            return [module for module, perms in self._permissions.items()]
        
        return [module for module, perms in self._permissions.items() 
                if perms.get('can_view', False)]
        
    def to_dict(self):
        """Преобразует объект в словарь для передачи в API"""
        return {
            'id': self.id,
            'login': self.login,
            'full_name': self.full_name,
            'role': self.role,
            'role_display_name': self.role_display_name,
            'role_type': self.role_type,
            'department': self.department,
            'department_id': self.department_id,
            'ukc_kc': self.ukc_kc,
            'status': self.status,
            'last_active': self.last_active,
            'position': self.position,
            'hire_date': self.hire_date,
            'fire_date': self.fire_date,
            'fired': self.fired,
            'is_admin': self.is_admin(),
            'is_leader': self.is_leader(),
            'is_operator': self.is_operator(),
            'is_backoffice': self.is_backoffice(),
            'is_online': self.is_online(),
            'permissions': self._permissions
        } 