from datetime import datetime
from app.utils import create_db_connection

class Role:
    """Модель роли пользователя в системе"""
    
    def __init__(self, id=None, name=None, display_name=None, description=None, role_type='custom', is_system=False, created_at=None, updated_at=None):
        self.id = id
        self.name = name  # Системное имя (только латиница, цифры и _)
        self.display_name = display_name  # Отображаемое имя
        self.description = description  # Описание роли
        self.type = role_type  # Тип роли: system, backoffice, custom
        self.is_system = is_system  # Системная роль (нельзя удалить или изменить)
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def has_permission(self, module_name, action):
        """Проверяет, имеет ли роль указанное разрешение для модуля"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT p.can_view, p.can_create, p.can_edit, p.can_delete
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        WHERE rp.role_id = %s AND p.module_name = %s
        """
        
        cursor.execute(query, (self.id, module_name))
        permission = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if permission and permission.get(f'can_{action}', False):
            return True
        return False
    
    def get_permissions(self):
        """Получает все разрешения роли"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT p.*
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        WHERE rp.role_id = %s
        """
        
        cursor.execute(query, (self.id,))
        permissions = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return permissions
    
    def add_permission(self, permission_id):
        """Добавляет разрешение роли"""
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Проверяем, есть ли уже такое разрешение у роли
        check_query = "SELECT COUNT(*) FROM role_permissions WHERE role_id = %s AND permission_id = %s"
        cursor.execute(check_query, (self.id, permission_id))
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            insert_query = "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)"
            cursor.execute(insert_query, (self.id, permission_id))
            connection.commit()
        
        cursor.close()
        connection.close()
    
    def remove_permission(self, permission_id):
        """Удаляет разрешение у роли"""
        connection = create_db_connection()
        cursor = connection.cursor()
        
        query = "DELETE FROM role_permissions WHERE role_id = %s AND permission_id = %s"
        cursor.execute(query, (self.id, permission_id))
        connection.commit()
        
        cursor.close()
        connection.close()
    
    def update_permissions(self, permissions_ids):
        """Обновляет список разрешений роли"""
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Удаляем все текущие разрешения
        delete_query = "DELETE FROM role_permissions WHERE role_id = %s"
        cursor.execute(delete_query, (self.id,))
        
        # Добавляем новые разрешения
        if permissions_ids:
            values = [(self.id, perm_id) for perm_id in permissions_ids]
            insert_query = "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)"
            cursor.executemany(insert_query, values)
        
        connection.commit()
        cursor.close()
        connection.close()
    
    def save(self):
        """Сохраняет или обновляет роль в базе данных"""
        connection = create_db_connection()
        cursor = connection.cursor()
        
        now = datetime.utcnow()
        
        if self.id:
            # Обновляем существующую роль
            query = """
            UPDATE roles
            SET name = %s, display_name = %s, description = %s, 
                type = %s, is_system = %s, updated_at = %s
            WHERE id = %s
            """
            cursor.execute(query, (
                self.name, self.display_name, self.description,
                self.type, self.is_system, now, self.id
            ))
        else:
            # Создаем новую роль
            query = """
            INSERT INTO roles (name, display_name, description, type, is_system, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                self.name, self.display_name, self.description,
                self.type, self.is_system, now, now
            ))
            self.id = connection.insert_id()
        
        connection.commit()
        cursor.close()
        connection.close()
        return self
    
    def delete(self):
        """Удаляет роль из базы данных"""
        if self.is_system:
            raise ValueError("Системные роли нельзя удалить")
        
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Удаляем связи роли с разрешениями
        cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (self.id,))
        
        # Удаляем связи роли с пользователями
        cursor.execute("DELETE FROM user_roles WHERE role_id = %s", (self.id,))
        
        # Удаляем саму роль
        cursor.execute("DELETE FROM roles WHERE id = %s", (self.id,))
        
        connection.commit()
        cursor.close()
        connection.close()
    
    def to_dict(self):
        """Возвращает данные роли в виде словаря"""
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'type': self.type,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at
        }
    
    @classmethod
    def get_by_id(cls, role_id):
        """Получает роль по ID"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM roles WHERE id = %s"
        cursor.execute(query, (role_id,))
        role_data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if role_data:
            return cls(
                id=role_data['id'],
                name=role_data['name'],
                display_name=role_data['display_name'],
                description=role_data['description'],
                role_type=role_data['type'],
                is_system=role_data['is_system'],
                created_at=role_data['created_at'],
                updated_at=role_data['updated_at']
            )
        return None
    
    @classmethod
    def get_by_name(cls, name):
        """Получает роль по имени"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM roles WHERE name = %s"
        cursor.execute(query, (name,))
        role_data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if role_data:
            return cls(
                id=role_data['id'],
                name=role_data['name'],
                display_name=role_data['display_name'],
                description=role_data['description'],
                role_type=role_data['type'],
                is_system=role_data['is_system'],
                created_at=role_data['created_at'],
                updated_at=role_data['updated_at']
            )
        return None
    
    @classmethod
    def get_all(cls):
        """Получает все роли"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM roles ORDER BY id"
        cursor.execute(query)
        roles_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=role_data['id'],
            name=role_data['name'],
            display_name=role_data['display_name'],
            description=role_data['description'],
            role_type=role_data['type'],
            is_system=role_data['is_system'],
            created_at=role_data['created_at'],
            updated_at=role_data['updated_at']
        ) for role_data in roles_data]
    
    @classmethod
    def get_system_roles(cls):
        """Возвращает все системные роли"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM roles WHERE is_system = TRUE"
        cursor.execute(query)
        roles_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=role_data['id'],
            name=role_data['name'],
            display_name=role_data['display_name'],
            description=role_data['description'],
            role_type=role_data['type'],
            is_system=role_data['is_system'],
            created_at=role_data['created_at'],
            updated_at=role_data['updated_at']
        ) for role_data in roles_data]
    
    @classmethod
    def get_backoffice_roles(cls):
        """Возвращает все бэк-офисные роли"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM roles WHERE type = 'backoffice'"
        cursor.execute(query)
        roles_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=role_data['id'],
            name=role_data['name'],
            display_name=role_data['display_name'],
            description=role_data['description'],
            role_type=role_data['type'],
            is_system=role_data['is_system'],
            created_at=role_data['created_at'],
            updated_at=role_data['updated_at']
        ) for role_data in roles_data]
    
    @classmethod
    def get_custom_roles(cls):
        """Возвращает все пользовательские роли"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM roles WHERE type = 'custom'"
        cursor.execute(query)
        roles_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=role_data['id'],
            name=role_data['name'],
            display_name=role_data['display_name'],
            description=role_data['description'],
            role_type=role_data['type'],
            is_system=role_data['is_system'],
            created_at=role_data['created_at'],
            updated_at=role_data['updated_at']
        ) for role_data in roles_data]
    
    def __repr__(self):
        return f'<Role {self.name}>' 