from datetime import datetime
from app.utils import create_db_connection
from werkzeug.utils import secure_filename
import os

class News:
    TABLE_NAME = 'News'

    def __init__(self, id=None, title=None, body=None, image_path=None, created_by=None, created_at=None, publish_at=None, is_published=False):
        self.id = id
        self.title = title
        self.body = body
        self.image_path = image_path
        self.created_by = created_by
        self.created_at = created_at or datetime.utcnow()
        self.publish_at = publish_at
        self.is_published = is_published

    @staticmethod
    def create_table():
        sql = f"""
        CREATE TABLE IF NOT EXISTS {News.TABLE_NAME} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            image_path VARCHAR(255) NULL,
            created_by INT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            publish_at DATETIME NULL,
            is_published TINYINT(1) NOT NULL DEFAULT 0,
            INDEX idx_publish (is_published, publish_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        conn = create_db_connection()
        if conn:
            with conn.cursor() as c:
                c.execute(sql)
            conn.commit()
            conn.close()

    @staticmethod
    def from_row(row):
        return News(
            id=row['id'],
            title=row['title'],
            body=row['body'],
            image_path=row.get('image_path'),
            created_by=row.get('created_by'),
            created_at=row['created_at'],
            publish_at=row.get('publish_at'),
            is_published=bool(row.get('is_published', 0))
        )

    @staticmethod
    def get_all(limit=100, include_unpublished=True):
        conn = create_db_connection(); cur = conn.cursor(dictionary=True)
        sql = f"SELECT * FROM {News.TABLE_NAME} "
        if not include_unpublished:
            sql += "WHERE is_published=1 AND (publish_at IS NULL OR publish_at<=NOW()) "
        sql += "ORDER BY publish_at DESC, created_at DESC LIMIT %s"
        cur.execute(sql, (limit,))
        data = [News.from_row(r) for r in cur.fetchall()]
        cur.close(); conn.close(); return data

    @staticmethod
    def get_by_id(news_id):
        conn = create_db_connection(); cur = conn.cursor(dictionary=True)
        cur.execute(f"SELECT * FROM {News.TABLE_NAME} WHERE id=%s", (news_id,))
        row = cur.fetchone(); cur.close(); conn.close()
        return News.from_row(row) if row else None

    @staticmethod
    def get_roles(news_id):
        conn = create_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT role_id FROM NewsRoles WHERE news_id = %s", (news_id,))
        roles = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return roles

    @staticmethod
    def set_roles(news_id, role_ids):
        conn = create_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM NewsRoles WHERE news_id = %s", (news_id,))
        if role_ids:
            values = [(news_id, role_id) for role_id in role_ids]
            cur.executemany("INSERT INTO NewsRoles (news_id, role_id) VALUES (%s, %s)", values)
        conn.commit()
        cur.close()
        conn.close()

    def save_with_roles(self, file_storage, role_ids):
        conn = create_db_connection()
        cur = conn.cursor()
        try:
            img_path_db = self.image_path
            if file_storage and file_storage.filename:
                fn = datetime.utcnow().strftime('%Y%m%d%H%M%S_') + secure_filename(file_storage.filename)
                folder = 'app/static/news'
                os.makedirs(folder, exist_ok=True)
                file_storage.save(os.path.join(folder, fn))
                img_path_db = f'news/{fn}'
            
            self.image_path = img_path_db

            if self.id:
                sql = f"""UPDATE {self.TABLE_NAME} SET title=%s, body=%s, image_path=%s, publish_at=%s, is_published=%s WHERE id=%s"""
                params = (self.title, self.body, self.image_path, self.publish_at, self.is_published, self.id)
                cur.execute(sql, params)
            else:
                sql = f"""INSERT INTO {self.TABLE_NAME} (title, body, image_path, created_by, publish_at, is_published) VALUES (%s,%s,%s,%s,%s,%s)"""
                params = (self.title, self.body, self.image_path, self.created_by, self.publish_at, self.is_published)
                cur.execute(sql, params)
                self.id = cur.lastrowid
            
            cur.execute("DELETE FROM NewsRoles WHERE news_id = %s", (self.id,))
            if role_ids:
                values = [(self.id, role_id) for role_id in role_ids]
                cur.executemany("INSERT INTO NewsRoles (news_id, role_id) VALUES (%s, %s)", values)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def delete(news_id):
        conn = create_db_connection(); cur = conn.cursor();
        cur.execute("DELETE FROM NewsRoles WHERE news_id = %s", (news_id,))
        cur.execute(f"DELETE FROM {News.TABLE_NAME} WHERE id=%s", (news_id,));
        conn.commit(); cur.close(); conn.close()

    @staticmethod
    def publish_scheduled_news():
        """
        Переводит все новости, у которых наступило время публикации, в статус опубликовано
        """
        conn = create_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(f"""
                UPDATE {News.TABLE_NAME}
                SET is_published=1
                WHERE is_published=0 AND publish_at IS NOT NULL AND publish_at<=NOW()
            """)
            conn.commit()
        finally:
            cur.close()
            conn.close()