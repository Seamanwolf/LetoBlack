from datetime import datetime
from app.db_connection import get_connection

class AuditLog:
    def __init__(self, user_id=None, username=None, action=None, object_type=None, object_id=None, details=None, status=None, ip=None, timestamp=None):
        self.user_id = user_id
        self.username = username
        self.action = action
        self.object_type = object_type
        self.object_id = object_id
        self.details = details
        self.status = status
        self.ip = ip
        self.timestamp = timestamp or datetime.utcnow()

    @staticmethod
    def create_table():
        sql = '''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NULL,
            username VARCHAR(128) NULL,
            action VARCHAR(64) NOT NULL,
            object_type VARCHAR(64) NULL,
            object_id VARCHAR(64) NULL,
            details TEXT NULL,
            status VARCHAR(32) NOT NULL,
            ip VARCHAR(64) NULL,
            timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        '''
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        cursor.close()
 