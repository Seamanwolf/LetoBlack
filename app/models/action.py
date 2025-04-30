from app import db
from datetime import datetime
from app.utils import create_db_connection

class Action:
    """
    Модель для действий пользователей в системе
    """
    def __init__(self, id=None, user_id=None, action_type=None, details=None, created_at=None):
        self.id = id
        self.user_id = user_id
        self.action_type = action_type
        self.details = details
        self.created_at = created_at or datetime.now()
    
    @staticmethod
    def query():
        return ActionQuery()
        
    @staticmethod
    def add(user_id, action_type, details=None):
        """Добавляет запись о действии пользователя"""
        connection = create_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO UserActivity (user_id, action_type, details)
                VALUES (%s, %s, %s)
                """,
                (user_id, action_type, details)
            )
            connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении действия: {e}")
            return False
        finally:
            cursor.close()
            connection.close()
    
    @staticmethod
    def log_activity(username, action, details=None):
        """Логирует действие пользователя в таблицу activity_log"""
        connection = create_db_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO activity_log (username, action, details, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (username, action, details)
            )
            connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при логировании действия: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

class ActionQuery:
    """Класс для выполнения запросов к таблице UserActivity"""
    
    def __init__(self):
        self._order_by = None
        self._limit = None
        
    def order_by(self, column):
        """Устанавливает сортировку результатов"""
        self._order_by = column
        return self
        
    def limit(self, limit):
        """Ограничивает количество результатов"""
        self._limit = limit
        return self
        
    def all(self):
        """Получает все действия с применением фильтров"""
        connection = create_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        try:
            query = """
                SELECT a.*, u.full_name 
                FROM UserActivity a
                JOIN User u ON a.user_id = u.id
            """
            
            if self._order_by:
                query += f" ORDER BY {self._order_by}"
                
            if self._limit:
                query += f" LIMIT {self._limit}"
                
            cursor.execute(query)
            results = cursor.fetchall()
            
            actions = []
            for row in results:
                action = Action(
                    id=row['id'],
                    user_id=row['user_id'],
                    action_type=row['action_type'],
                    details=row.get('details'),
                    created_at=row['created_at']
                )
                # Добавляем дополнительные данные
                action.full_name = row['full_name']
                
                actions.append(action)
                
            return actions
        except Exception as e:
            print(f"Ошибка при получении действий: {e}")
            return []
        finally:
            cursor.close()
            connection.close()
            
    def count(self):
        """Возвращает количество действий"""
        connection = create_db_connection()
        cursor = connection.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM UserActivity")
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Ошибка при подсчете действий: {e}")
            return 0
        finally:
            cursor.close()
            connection.close() 