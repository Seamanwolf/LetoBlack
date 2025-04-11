from app.utils import create_db_connection
from datetime import datetime

class Employee:
    def __init__(self, id=None, user_id=None, position_id=None, department_id=None, hire_date=None, fire_date=None, created_at=None, updated_at=None, full_name=None, position=None, department=None, is_active=None, fired=None):
        self.id = id
        self.user_id = user_id
        self.position_id = position_id
        self.department_id = department_id
        self.hire_date = hire_date
        self.fire_date = fire_date
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_name = None
        self.first_name = None
        self.middle_name = None
        self.full_name = full_name
        self.position = position
        self.department = department
        self._is_active = is_active
        self._fired = fired
    
    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT 
                    id as user_id,
                    full_name,
                    position,
                    department,
                    department_id,
                    hire_date,
                    termination_date as fire_date,
                    is_active,
                    fired
                FROM User
                WHERE is_active = 1 OR fired = 0
            """)
            employees = cursor.fetchall()
            return [Employee(**employee) for employee in employees]
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_by_id(id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT 
                    id as user_id,
                    full_name,
                    position,
                    department,
                    department_id,
                    hire_date,
                    termination_date as fire_date,
                    is_active,
                    fired
                FROM User
                WHERE id = %s
            """, (id,))
            employee = cursor.fetchone()
            return Employee(**employee) if employee else None
        finally:
            cursor.close()
            conn.close()
    
    def save(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            if self.user_id is None:
                # Создание нового сотрудника не поддерживается через эту модель
                # Это должно делаться через модель User
                raise NotImplementedError("Создание нового сотрудника не поддерживается через эту модель")
            else:
                cursor.execute(
                    """UPDATE User 
                       SET position = %s, department = %s, department_id = %s, 
                           hire_date = %s, termination_date = %s, 
                           fired = %s, is_active = %s
                       WHERE id = %s""",
                    (self.position, self.department, self.department_id, 
                     self.hire_date, self.fire_date, 
                     self.fire_date is not None, self.fire_date is None, self.user_id)
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def delete(self):
        # Вместо удаления, помечаем сотрудника как уволенного
        self.fire_date = datetime.now().date()
        self.save()
    
    @property
    def is_active(self):
        if self._is_active is not None:
            return self._is_active
        return self.fire_date is None
    
    def to_dict(self):
        return {
            'id': self.user_id,
            'user_id': self.user_id,
            'position': self.position,
            'department': self.department,
            'department_id': self.department_id,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'fire_date': self.fire_date.isoformat() if self.fire_date else None,
            'full_name': self.full_name,
            'is_active': self.is_active
        }
    
    def __repr__(self):
        return f'<Employee {self.full_name}>' 