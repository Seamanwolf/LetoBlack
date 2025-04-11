from app.utils import create_db_connection
from datetime import datetime

class Location:
    def __init__(self, id=None, name=None, address=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.address = address
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Получаем все локации
            cursor.execute("""
                SELECT *
                FROM Location
                ORDER BY name
            """)
            locations = cursor.fetchall()
            return [Location(**location) for location in locations]
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_by_id(id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Получаем локацию
            cursor.execute("""
                SELECT *
                FROM Location
                WHERE id = %s
            """, (id,))
            location = cursor.fetchone()
            return Location(**location) if location else None
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
                    "INSERT INTO Location (name, address, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                    (self.name, self.address, now, now)
                )
                self.id = cursor.lastrowid
                self.created_at = now
                self.updated_at = now
            else:
                cursor.execute(
                    "UPDATE Location SET name = %s, address = %s, updated_at = %s WHERE id = %s",
                    (self.name, self.address, now, self.id)
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def delete(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM Location WHERE id = %s", (self.id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        location_str = f"ID: {self.id}"
        if self.name:
            location_str += f", Название: {self.name}"
        if self.address:
            location_str += f", Адрес: {self.address}"
        return f"<Location {location_str}>" 