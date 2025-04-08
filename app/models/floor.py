from app.db_connection import execute_query
from datetime import datetime

class Floor:
    def __init__(self, id=None, name=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.created_at = created_at
        self.updated_at = updated_at
        
    def __repr__(self):
        return f'<Floor {self.name}>'

    def save(self):
        if self.id:
            query = """
                UPDATE floors 
                SET name = %s, updated_at = NOW() 
                WHERE id = %s
            """
            execute_query(query, (self.name, self.id), fetch=False)
        else:
            query = """
                INSERT INTO floors (name, created_at, updated_at) 
                VALUES (%s, NOW(), NOW())
            """
            self.id = execute_query(query, (self.name,), fetch=False)

    def delete(self):
        query = "DELETE FROM floors WHERE id = %s"
        execute_query(query, (self.id,), fetch=False)

    @staticmethod
    def get_all():
        query = "SELECT * FROM floors ORDER BY name"
        floors = execute_query(query)
        return [Floor(**floor) for floor in floors] if floors else []

    @staticmethod
    def get_by_id(floor_id):
        query = "SELECT * FROM floors WHERE id = %s"
        result = execute_query(query, (floor_id,))
        if result:
            return Floor(**result[0])
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 