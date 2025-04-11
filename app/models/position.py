from app.utils import create_db_connection
from datetime import datetime

class Position:
    def __init__(self, id=None, name=None, description=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM Position")
            positions = cursor.fetchall()
            return [Position(**position) for position in positions]
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_by_id(id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM Position WHERE id = %s", (id,))
            position = cursor.fetchone()
            return Position(**position) if position else None
        finally:
            cursor.close()
            conn.close()
    
    def save(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            if self.id is None:
                cursor.execute(
                    "INSERT INTO Position (name, description, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                    (self.name, self.description, datetime.utcnow(), datetime.utcnow())
                )
                self.id = cursor.lastrowid
            else:
                cursor.execute(
                    "UPDATE Position SET name = %s, description = %s, updated_at = %s WHERE id = %s",
                    (self.name, self.description, datetime.utcnow(), self.id)
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def delete(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM Position WHERE id = %s", (self.id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 