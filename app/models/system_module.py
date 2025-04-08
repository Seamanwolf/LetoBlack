from datetime import datetime
from app.utils import create_db_connection

class SystemModule:
    """Модель модуля системы, для которого могут быть установлены разрешения"""
    
    def __init__(self, id=None, name=None, display_name=None, description=None, 
                 is_active=True, icon=None, order=0, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.display_name = display_name
        self.description = description
        self.is_active = is_active
        self.icon = icon
        self.order = order
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def save(self):
        """Сохраняет или обновляет модуль в базе данных"""
        connection = create_db_connection()
        cursor = connection.cursor()
        
        now = datetime.utcnow()
        
        if self.id:
            # Обновляем существующий модуль
            query = """
            UPDATE system_modules
            SET name = %s, display_name = %s, description = %s, is_active = %s,
                icon = %s, `order` = %s, updated_at = %s
            WHERE id = %s
            """
            cursor.execute(query, (
                self.name, self.display_name, self.description, self.is_active,
                self.icon, self.order, now, self.id
            ))
        else:
            # Создаем новый модуль
            query = """
            INSERT INTO system_modules (name, display_name, description, is_active,
                                       icon, `order`, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (
                self.name, self.display_name, self.description, self.is_active,
                self.icon, self.order, now, now
            ))
            self.id = connection.insert_id()
        
        connection.commit()
        cursor.close()
        connection.close()
        return self
    
    def delete(self):
        """Удаляет модуль из базы данных"""
        if not self.id:
            return False
            
        connection = create_db_connection()
        cursor = connection.cursor()
        
        # Проверяем, есть ли разрешения, связанные с этим модулем
        cursor.execute("SELECT COUNT(*) FROM permissions WHERE module_name = %s", (self.name,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Если есть связанные разрешения, сначала удаляем их
            cursor.execute("""
                DELETE FROM role_permissions 
                WHERE permission_id IN (SELECT id FROM permissions WHERE module_name = %s)
            """, (self.name,))
            cursor.execute("DELETE FROM permissions WHERE module_name = %s", (self.name,))
        
        # Удаляем модуль
        cursor.execute("DELETE FROM system_modules WHERE id = %s", (self.id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
    
    def to_dict(self):
        """Возвращает данные модуля в виде словаря"""
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'is_active': self.is_active,
            'icon': self.icon,
            'order': self.order,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at
        }
    
    @classmethod
    def get_by_id(cls, module_id):
        """Получает модуль по ID"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM system_modules WHERE id = %s"
        cursor.execute(query, (module_id,))
        module_data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if module_data:
            return cls(
                id=module_data['id'],
                name=module_data['name'],
                display_name=module_data['display_name'],
                description=module_data['description'],
                is_active=module_data['is_active'],
                icon=module_data['icon'],
                order=module_data['order'],
                created_at=module_data['created_at'],
                updated_at=module_data['updated_at']
            )
        return None
    
    @classmethod
    def get_by_name(cls, name):
        """Получает модуль по имени"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM system_modules WHERE name = %s"
        cursor.execute(query, (name,))
        module_data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if module_data:
            return cls(
                id=module_data['id'],
                name=module_data['name'],
                display_name=module_data['display_name'],
                description=module_data['description'],
                is_active=module_data['is_active'],
                icon=module_data['icon'],
                order=module_data['order'],
                created_at=module_data['created_at'],
                updated_at=module_data['updated_at']
            )
        return None
    
    @classmethod
    def get_all(cls):
        """Получает все модули"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM system_modules ORDER BY `order`"
        cursor.execute(query)
        modules_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=module_data['id'],
            name=module_data['name'],
            display_name=module_data['display_name'],
            description=module_data['description'],
            is_active=module_data['is_active'],
            icon=module_data['icon'],
            order=module_data['order'],
            created_at=module_data['created_at'],
            updated_at=module_data['updated_at']
        ) for module_data in modules_data]
    
    @classmethod
    def get_active_modules(cls):
        """Получает все активные модули системы, отсортированные по порядку"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM system_modules WHERE is_active = TRUE ORDER BY `order`"
        cursor.execute(query)
        modules_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return [cls(
            id=module_data['id'],
            name=module_data['name'],
            display_name=module_data['display_name'],
            description=module_data['description'],
            is_active=module_data['is_active'],
            icon=module_data['icon'],
            order=module_data['order'],
            created_at=module_data['created_at'],
            updated_at=module_data['updated_at']
        ) for module_data in modules_data]
    
    @classmethod
    def get_or_create(cls, name, display_name, description=None, is_active=True, icon=None, order=0):
        """Получает существующий модуль или создает новый"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM system_modules WHERE name = %s"
        cursor.execute(query, (name,))
        module_data = cursor.fetchone()
        
        if module_data:
            module = cls(
                id=module_data['id'],
                name=module_data['name'],
                display_name=module_data['display_name'],
                description=module_data['description'],
                is_active=module_data['is_active'],
                icon=module_data['icon'],
                order=module_data['order'],
                created_at=module_data['created_at'],
                updated_at=module_data['updated_at']
            )
        else:
            # Создаем новый модуль
            now = datetime.utcnow()
            insert_query = """
            INSERT INTO system_modules (name, display_name, description, is_active,
                                       icon, `order`, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                name, display_name, description, is_active, icon, order, now, now
            ))
            connection.commit()
            
            module_id = connection.insert_id()
            module = cls(
                id=module_id,
                name=name,
                display_name=display_name,
                description=description,
                is_active=is_active,
                icon=icon,
                order=order,
                created_at=now,
                updated_at=now
            )
        
        cursor.close()
        connection.close()
        return module
    
    def __repr__(self):
        status = "активен" if self.is_active else "неактивен"
        return f'<SystemModule {self.name}: {status}>' 