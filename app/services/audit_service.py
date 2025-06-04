from app.models.audit_log import AuditLog
from app.utils import logger

class AuditService:
    @staticmethod
    def log_user_action(user, action, object_type=None, object_id=None, details=None, status='success', ip=None):
        try:
            user_id = getattr(user, 'id', None) if user else None
            username = getattr(user, 'login', None) if user else None
            log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                object_type=object_type,
                object_id=object_id,
                details=details,
                status=status,
                ip=ip
            )
            sql = '''
                INSERT INTO audit_log (user_id, username, action, object_type, object_id, details, status, ip, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            conn = None
            try:
                from app.db_connection import create_db_connection
                conn = create_db_connection()
                cursor = conn.cursor()
                cursor.execute(sql, (
                    log.user_id, log.username, log.action, log.object_type, log.object_id,
                    log.details, log.status, log.ip, log.timestamp
                ))
                conn.commit()
                cursor.close()
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            logger.error(f"Ошибка при логировании действия пользователя: {e}") 