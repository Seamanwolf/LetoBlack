import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        connection = mysql.connector.connect(
            host='192.168.2.225',
            user='root',
            password='Podego53055',
            database='login'
        )
        return connection
    except Error as e:
        print(f"Ошибка подключения к базе данных: {e}")
        return None

def execute_query(query, params=None, fetch=True):
    connection = get_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        if fetch:
            result = cursor.fetchall()
        else:
            connection.commit()
            result = cursor.lastrowid
            
        cursor.close()
        connection.close()
        return result
    except Error as e:
        print(f"Ошибка выполнения запроса: {e}")
        if connection:
            connection.close()
        return None 