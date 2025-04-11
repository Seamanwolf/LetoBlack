from app.utils import create_db_connection
from datetime import datetime

class Floor:
    def __init__(self, id=None, floor=None, city_id=None, created_at=None, updated_at=None):
        self.id = id
        self.floor = floor
        self.city_id = city_id
        self.created_at = created_at
        self.updated_at = updated_at
        
    def __repr__(self):
        return f'<Floor {self.floor}>'

    def save(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            now = datetime.now()
            if self.id is None:
                cursor.execute(
                    "INSERT INTO Floor (floor, city_id, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                    (self.floor, self.city_id, now, now)
                )
                self.id = cursor.lastrowid
                self.created_at = now
                self.updated_at = now
            else:
                cursor.execute(
                    "UPDATE Floor SET floor = %s, city_id = %s, updated_at = %s WHERE id = %s",
                    (self.floor, self.city_id, now, self.id)
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
            cursor.execute("DELETE FROM Floor WHERE id = %s", (self.id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT f.*, c.name as city_name 
                FROM Floor f
                LEFT JOIN City c ON f.city_id = c.id
                ORDER BY c.name, f.floor
            """)
            floors = cursor.fetchall()
            result = []
            for floor in floors:
                floor_obj = Floor(
                    id=floor['id'],
                    floor=floor['floor'],
                    city_id=floor['city_id'],
                    created_at=floor.get('created_at'),
                    updated_at=floor.get('updated_at')
                )
                floor_obj._city_name = floor.get('city_name')
                result.append(floor_obj)
            return result
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_by_id(id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT f.*, c.name as city_name 
                FROM Floor f
                LEFT JOIN City c ON f.city_id = c.id
                WHERE f.id = %s
            """, (id,))
            floor = cursor.fetchone()
            if not floor:
                return None
            
            floor_obj = Floor(
                id=floor['id'],
                floor=floor['floor'],
                city_id=floor['city_id'],
                created_at=floor.get('created_at'),
                updated_at=floor.get('updated_at')
            )
            floor_obj._city_name = floor.get('city_name')
            return floor_obj
        finally:
            cursor.close()
            conn.close()

    def to_dict(self):
        return {
            'id': self.id,
            'floor': self.floor,
            'city_id': self.city_id,
            'city_name': getattr(self, '_city_name', None),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        } 