from app.db_connection import execute_query
from datetime import datetime

class Department:
    def __init__(self, id=None, name=None, floor_id=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.floor_id = floor_id
        self.created_at = created_at
        self.updated_at = updated_at
        
    def __repr__(self):
        return f'<Department {self.name}>'

    @property
    def employee_count(self):
        query = """
            SELECT COUNT(*) as count 
            FROM User 
            WHERE department = %s
        """
        result = execute_query(query, (self.name,))
        return result[0]['count'] if result else 0

    def save(self):
        if self.id:
            query = """
                UPDATE departments 
                SET name = %s, floor_id = %s, updated_at = NOW() 
                WHERE id = %s
            """
            execute_query(query, (self.name, self.floor_id, self.id), fetch=False)
        else:
            query = """
                INSERT INTO departments (name, floor_id, created_at, updated_at) 
                VALUES (%s, %s, NOW(), NOW())
            """
            self.id = execute_query(query, (self.name, self.floor_id), fetch=False)

    def delete(self):
        query = "DELETE FROM departments WHERE id = %s"
        execute_query(query, (self.id,), fetch=False)

    @staticmethod
    def get_all():
        query = "SELECT * FROM departments ORDER BY name"
        departments = execute_query(query)
        return [Department(**dept) for dept in departments] if departments else []

    @staticmethod
    def get_by_id(department_id):
        query = "SELECT * FROM departments WHERE id = %s"
        result = execute_query(query, (department_id,))
        if result:
            return Department(**result[0])
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'floor_id': self.floor_id,
            'employee_count': self.employee_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 