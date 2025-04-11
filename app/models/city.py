from app.utils import create_db_connection
from datetime import datetime

class City:
    def __init__(self, id=None, name=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM City ORDER BY name")
            cities = cursor.fetchall()
            return [City(**city) for city in cities]
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_by_id(id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM City WHERE id = %s", (id,))
            city = cursor.fetchone()
            return City(**city) if city else None
        finally:
            cursor.close()
            conn.close()
    
    def save(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            now = datetime.now()
            if self.id is None:
                cursor.execute(
                    "INSERT INTO City (name, created_at, updated_at) VALUES (%s, %s, %s)",
                    (self.name, now, now)
                )
                self.id = cursor.lastrowid
                self.created_at = now
                self.updated_at = now
            else:
                cursor.execute(
                    "UPDATE City SET name = %s, updated_at = %s WHERE id = %s",
                    (self.name, now, self.id)
                )
                self.updated_at = now
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def delete(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM City WHERE id = %s", (self.id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<City {self.name}>' 