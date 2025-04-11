from app.utils import create_db_connection
from datetime import datetime

class Department:
    def __init__(self, id=None, name=None, location_id=None, leader_id=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.location_id = location_id
        self.leader_id = leader_id
        self.created_at = created_at
        self.updated_at = updated_at
        self._location_name = None
        self._leader_name = None
        
    def __repr__(self):
        return f'<Department {self.name}>'

    @property
    def location(self):
        return {
            'id': self.location_id,
            'name': self._location_name if self._location_name else 'Не указано'
        }

    @property
    def leader(self):
        return {
            'id': self.leader_id,
            'full_name': self._leader_name if self._leader_name else 'Не назначен'
        }

    @property
    def employee_count(self):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM User 
                WHERE department_id = %s
            """, (self.id,))
            result = cursor.fetchone()
            return result['count'] if result else 0
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT d.*, 
                       l.name as location_name,
                       u.full_name as leader_name
                FROM Department d
                LEFT JOIN Location l ON d.location_id = l.id
                LEFT JOIN User u ON d.leader_id = u.id
                ORDER BY d.name
            """)
            departments = cursor.fetchall()
            result = []
            for dept in departments:
                department = Department(
                    id=dept['id'],
                    name=dept['name'],
                    location_id=dept['location_id'],
                    leader_id=dept['leader_id'],
                    created_at=dept['created_at'],
                    updated_at=dept['updated_at']
                )
                department._location_name = dept['location_name']
                department._leader_name = dept['leader_name']
                result.append(department)
            return result
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_by_id(department_id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT d.*, 
                       l.name as location_name,
                       u.full_name as leader_name
                FROM Department d
                LEFT JOIN Location l ON d.location_id = l.id
                LEFT JOIN User u ON d.leader_id = u.id
                WHERE d.id = %s
            """, (department_id,))
            result = cursor.fetchone()
            if not result:
                return None
            
            department = Department(
                id=result['id'],
                name=result['name'],
                location_id=result['location_id'],
                leader_id=result['leader_id'],
                created_at=result['created_at'],
                updated_at=result['updated_at']
            )
            department._location_name = result['location_name']
            department._leader_name = result['leader_name']
            return department
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
                    """INSERT INTO Department 
                       (name, location_id, leader_id, created_at, updated_at) 
                       VALUES (%s, %s, %s, %s, %s)""",
                    (self.name, self.location_id, self.leader_id, now, now)
                )
                self.id = cursor.lastrowid
                self.created_at = now
                self.updated_at = now
            else:
                cursor.execute(
                    """UPDATE Department 
                       SET name = %s, location_id = %s, leader_id = %s, updated_at = %s 
                       WHERE id = %s""",
                    (self.name, self.location_id, self.leader_id, now, self.id)
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
            cursor.execute("DELETE FROM Department WHERE id = %s", (self.id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location_id': self.location_id,
            'leader_id': self.leader_id,
            'employee_count': self.employee_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'location': self.location,
            'leader': self.leader
        } 