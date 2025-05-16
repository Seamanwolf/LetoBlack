from app.utils import create_db_connection
from datetime import datetime

class CorpNumber:
    def __init__(self, id=None, phone_number=None, department=None, assigned_to=None, 
                 whatsapp=False, telegram=False, blocked=False, prohibit_issuance=False):
        self.id = id
        self.phone_number = phone_number
        self.department = department
        self.assigned_to = assigned_to
        self.whatsapp = whatsapp
        self.telegram = telegram
        self.blocked = blocked
        self.prohibit_issuance = prohibit_issuance
    
    def __repr__(self):
        return f'<CorpNumber {self.phone_number}>'
    
    @staticmethod
    def get_all():
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT * FROM corp_numbers
                ORDER BY department, id
            """)
            numbers = cursor.fetchall()
            result = []
            for num in numbers:
                corp_number = CorpNumber(
                    id=num['id'],
                    phone_number=num['phone_number'],
                    department=num['department'],
                    assigned_to=num['assigned_to'],
                    whatsapp=bool(num['whatsapp']),
                    telegram=bool(num['telegram']),
                    blocked=bool(num['blocked']),
                    prohibit_issuance=bool(num['prohibit_issuance'])
                )
                result.append(corp_number)
            return result
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_by_id(number_id):
        conn = create_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT * FROM corp_numbers
                WHERE id = %s
            """, (number_id,))
            result = cursor.fetchone()
            if not result:
                return None
            
            corp_number = CorpNumber(
                id=result['id'],
                phone_number=result['phone_number'],
                department=result['department'],
                assigned_to=result['assigned_to'],
                whatsapp=bool(result['whatsapp']),
                telegram=bool(result['telegram']),
                blocked=bool(result['blocked']),
                prohibit_issuance=bool(result['prohibit_issuance'])
            )
            return corp_number
        finally:
            cursor.close()
            conn.close()
    
    def save(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            if self.id is None:
                cursor.execute(
                    """INSERT INTO corp_numbers 
                       (phone_number, department, assigned_to, whatsapp, telegram, blocked, prohibit_issuance) 
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (self.phone_number, self.department, self.assigned_to, 
                     self.whatsapp, self.telegram, self.blocked, self.prohibit_issuance)
                )
                self.id = cursor.lastrowid
            else:
                cursor.execute(
                    """UPDATE corp_numbers 
                       SET phone_number = %s, department = %s, assigned_to = %s,
                           whatsapp = %s, telegram = %s, blocked = %s, prohibit_issuance = %s
                       WHERE id = %s""",
                    (self.phone_number, self.department, self.assigned_to, 
                     self.whatsapp, self.telegram, self.blocked, self.prohibit_issuance, self.id)
                )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def delete(self):
        conn = create_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM corp_numbers WHERE id = %s", (self.id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'department': self.department,
            'assigned_to': self.assigned_to,
            'whatsapp': self.whatsapp,
            'telegram': self.telegram,
            'blocked': self.blocked,
            'prohibit_issuance': self.prohibit_issuance
        } 