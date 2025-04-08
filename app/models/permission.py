from datetime import datetime
from app.utils import create_db_connection

class Permission:
    """Модель разрешения для роли на действия с определенным модулем"""
    
    def __init__(self, id=None, module_name=None, can_view=False, can_create=False, 
                 can_edit=False, can_delete=False, description=None, created_at=None, updated_at=None):
        self.id = id
        self.module_name = module_name
        self.can_view = can_view
        self.can_create = can_create
        self.can_edit = can_edit
        self.can_delete = can_delete
        self.description = description
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def save(self):
        """Сохраняет или обновляет разрешение в базе данных"""
        connection = create_db_connection()
        cursor = connection.cursor()
        
        now = datetime.utcnow()
        
        if self.id:
            # Обновляем существующее разрешение
            query = """
            UPDATE permissions
            SET module_name = %s, can_view = %s, can_create = %s, 
                can_edit = %s, can_delete = %s, description = %s, updated_at = %s
            WHERE id = %s
            """
            cursor.execute(query, (
                self.module_name, self.can_view, self.can_create,
                self.can_edit, self.can_delete, self.description, now, self.id
            ))
        else:
            # Создаем новое разрешение
            query = """
            INSERT INTO permissions (module_name, can_view, can_create, can_edit, 
                            can_delete, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                self.module_name, self.can_view, self.can_create,
                self.can_edit, self.can_delete, self.description, now, now
            ))
            self.id = connection.insert_id()
        
        connection.commit()
        cursor.close()
        connection.close()
        return self
    
    def delete(self):
        """Удаляет разрешение из базы данных"""
        if not self.id:
            return False
            
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Сначала удаляем связи в таблице role_permissions
        cursor.execute("DELETE FROM role_permissions WHERE permission_id = %s", (self.id,))
        
        # Затем удаляем само разрешение
        cursor.execute("DELETE FROM permissions WHERE id = %s", (self.id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    
    def to_dict(self):
        """Возвращает данные разрешения в виде словаря"""
        return {
            'id': self.id,
            'module_name': self.module_name,
            'can_view': self.can_view,
            'can_create': self.can_create,
            'can_edit': self.can_edit,
            'can_delete': self.can_delete,
            'description': self.description,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at
        }
    
    @classmethod
    def get_by_id(cls, permission_id):
        """Получает разрешение по ID"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM permissions WHERE id = %s"
        cursor.execute(query, (permission_id,))
        permission_data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if permission_data:
            return cls(
                id=permission_data['id'],
                module_name=permission_data['module_name'],
                can_view=permission_data['can_view'],
                can_create=permission_data['can_create'],
                can_edit=permission_data['can_edit'],
                can_delete=permission_data['can_delete'],
                description=permission_data['description'],
                created_at=permission_data['created_at'],
                updated_at=permission_data['updated_at']
            )
        return None
    
    @classmethod
    def get_by_module(cls, module_name):
        """Получает разрешения по имени модуля"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM permissions WHERE module_name = %s"
        cursor.execute(query, (module_name,))
        permissions_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=perm_data['id'],
            module_name=perm_data['module_name'],
            can_view=perm_data['can_view'],
            can_create=perm_data['can_create'],
            can_edit=perm_data['can_edit'],
            can_delete=perm_data['can_delete'],
            description=perm_data['description'],
            created_at=perm_data['created_at'],
            updated_at=perm_data['updated_at']
        ) for perm_data in permissions_data]
    
    @classmethod
    def get_all(cls):
        """Получает все разрешения"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM permissions"
        cursor.execute(query)
        permissions_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=perm_data['id'],
            module_name=perm_data['module_name'],
            can_view=perm_data['can_view'],
            can_create=perm_data['can_create'],
            can_edit=perm_data['can_edit'],
            can_delete=perm_data['can_delete'],
            description=perm_data['description'],
            created_at=perm_data['created_at'],
            updated_at=perm_data['updated_at']
        ) for perm_data in permissions_data]
    
    @classmethod
    def get_or_create(cls, module_name, can_view=False, can_create=False, can_edit=False, can_delete=False, description=None):
        """Получает существующее разрешение или создает новое"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Ищем разрешение с точно такими же параметрами
        query = """
        SELECT * FROM permissions 
        WHERE module_name = %s AND can_view = %s AND can_create = %s 
            AND can_edit = %s AND can_delete = %s
        """
        cursor.execute(query, (module_name, can_view, can_create, can_edit, can_delete))
        permission_data = cursor.fetchone()
        
        if permission_data:
            permission = cls(
                id=permission_data['id'],
                module_name=permission_data['module_name'],
                can_view=permission_data['can_view'],
                can_create=permission_data['can_create'],
                can_edit=permission_data['can_edit'],
                can_delete=permission_data['can_delete'],
                description=permission_data['description'],
                created_at=permission_data['created_at'],
                updated_at=permission_data['updated_at']
            )
        else:
            # Создаем новое разрешение
            now = datetime.utcnow()
            insert_query = """
            INSERT INTO permissions (module_name, can_view, can_create, can_edit, 
                            can_delete, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                module_name, can_view, can_create, can_edit, can_delete, description, now, now
            ))
            connection.commit()
            
            permission_id = connection.insert_id()
            permission = cls(
                id=permission_id,
                module_name=module_name,
                can_view=can_view,
                can_create=can_create,
                can_edit=can_edit,
                can_delete=can_delete,
                description=description,
                created_at=now,
                updated_at=now
            )
        
        cursor.close()
        connection.close()
        return permission
    
    def __repr__(self):
        permissions = []
        if self.can_view:
            permissions.append('view')
        if self.can_create:
            permissions.append('create')
        if self.can_edit:
            permissions.append('edit')
        if self.can_delete:
            permissions.append('delete')
            
        return f'<Permission {self.module_name}: {", ".join(permissions)}>' 