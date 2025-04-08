from flask_login import UserMixin

class User:
    def __init__(self, id, login, full_name, role, ukc_kc, department=None, is_active=True):
        self.id = id
        self.login = login
        self.full_name = full_name
        self.role = role
        self.ukc_kc = ukc_kc
        self.department = department
        self._is_active = is_active  # значение по умолчанию для is_active

    # Проверка аутентификации
    @property
    def is_authenticated(self):
        return True

    # Проверка активности
    @property
    def is_active(self):
        return True

    # Проверка для "гостей"
    @property
    def is_anonymous(self):
        return False

    # Метод для получения ID пользователя
    def get_id(self):
        return str(self.id)
