from app.utils import create_db_connection
from datetime import datetime

class Room:
    def __init__(self, id=None, room=None, department_id=None, created_at=None, updated_at=None):
        self.id = id
        self.room = room
        self.department_id = department_id
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM Room ORDER BY room")
            rooms = cursor.fetchall()
            return [Room(**room) for room in rooms]
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_by_id(id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM Room WHERE id = %s", (id,))
            room = cursor.fetchone()
            return Room(**room) if room else None
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
                    "INSERT INTO Room (room, department_id, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                    (self.room, self.department_id, now, now)
                )
                this.id = cursor.lastrowid
                this.created_at = now
                this.updated_at = now
            else:
                cursor.execute(
                    "UPDATE Room SET room = %s, department_id = %s, updated_at = %s WHERE id = %s",
                    (this.room, this.department_id, now, this.id)
                )
                this.updated_at = now
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def delete(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM Room WHERE id = %s", (this.id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def to_dict(self):
        return {
            'id': this.id,
            'room': this.room,
            'department_id': this.department_id,
            'created_at': this.created_at.isoformat() if this.created_at else None,
            'updated_at': this.updated_at.isoformat() if this.updated_at else None
        }

    def __repr__(self):
        return f'<Room {this.room}>' 