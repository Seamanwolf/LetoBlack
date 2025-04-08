# vats_utils.py
import requests

VATS_API_KEY = "d1b0ef65-e491-43f9-967b-df67d4657dbb"
VATS_API_URL = "https://leto.megapbx.ru/crmapi/v1"

def format_phone_number(phone):
    """
    Приводит номер к формату '7xxxxxxxxxx'.
    Возвращает None, если формат некорректный.
    """
    if isinstance(phone, int):
        phone = str(phone)
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    if len(phone) == 10 and phone.isdigit():
        phone = "7" + phone
    elif phone.startswith("8") and len(phone) == 11:
        phone = "7" + phone[1:]
    elif phone.startswith("+7") and len(phone) == 12:
        phone = "7" + phone[2:]
    elif not phone.startswith("7") or len(phone) != 11:
        return None

    return phone

def get_all_users():
    """
    Возвращает список всех сотрудников из ВАТС.
    """
    headers = {
        "X-API-KEY": VATS_API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.get(f"{VATS_API_URL}/users", headers=headers)
    if response.status_code == 200:
        return response.json().get("items", [])
    else:
        print(f"Ошибка при получении списка сотрудников: {response.status_code}, {response.text}")
        return []

def find_user_by_name(employee_name):
    """
    Ищет в ВАТС сотрудника по точному совпадению поля 'name' (регистронезависимо).
    Возвращает dict с данными сотрудника или None.
    """
    users = get_all_users()
    employee_name = employee_name.strip().lower()
    for user in users:
        user_name = (user.get("name") or "").strip().lower()
        if user_name == employee_name:
            return user
    return None

def update_telnum_route(formatted_phone, user_login):
    """
    Настраивает переадресацию (маршрут) номера 'formatted_phone'
    на сотрудника с логином 'user_login' в ВАТС.
    """
    headers = {
        "X-API-KEY": VATS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "type": "user",
        "user": user_login,
        "greeting": False
    }
    response = requests.post(f"{VATS_API_URL}/telnums/{formatted_phone}",
                             headers=headers, json=payload)
    if response.status_code == 200:
        return True, None
    else:
        error_msg = f"{response.status_code}, {response.text}"
        return False, error_msg
