from oauth2client.service_account import ServiceAccountCredentials
import gspread
import pandas as pd
import mysql.connector
import logging
import pymysql

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

CREDENTIALS_FILE = '/home/sergey/gapi/GAPI.json'

def create_db_connection():
    try:
        connection = pymysql.connect(
            host='192.168.2.225',
            port=3306,
            user='test_user',
            password='password',
            database="Brokers"
        )
        logging.info("Database connection established")
        return connection
    except pymysql.Error as err:
        logging.error(f"Error connecting to database: {err}")
        raise

def fetch_google_sheet_data(sheet_name):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1TMKRjy6Qi6fp3Heri2PUox0dSHr4gp_05Ac23WrxOrI/edit?gid=0#gid=0')
        worksheet = sheet.worksheet(sheet_name)

        data = worksheet.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])
        logging.info(f"Data fetched from Google Sheet {sheet_name}")
        return df
    except Exception as e:
        logging.error(f"Error fetching data from Google Sheets: {e}")
        raise

def update_ratings_from_google_sheets():
    try:
        df = fetch_google_sheet_data('Лист1')  # Лист1 для данных скоринга

        logging.debug("Исходные данные из Google Sheets (Лист1):")
        logging.debug(df.head(30))  # Отладка: вывод первых 30 строк данных

        # Явная замена запятых на точки в столбце 'Скоринг' и преобразование к float
        df['Скоринг'] = df['Скоринг'].str.replace(',', '.').astype(float)

        # Выведем строки, где 'Скоринг' содержит дробные значения
        logging.debug("Строки с дробными значениями 'Скоринг':")
        logging.debug(df[df['Скоринг'] % 1 != 0])

        # Приведение значений к диапазону 0.0 - 5.0 и округление до одной цифры после запятой
        df['Скоринг'] = df['Скоринг'].apply(lambda x: round(min(max(x, 0.0), 5.0), 1) if pd.notnull(x) else x)

        logging.debug("Данные после преобразования:")
        logging.debug(df.head(30))  # Отладка: вывод первых 30 строк данных после преобразования

        for index, row in df.iterrows():
            last_name = row['Сотрудник']
            rating = row['Скоринг']

            logging.info(f"Updating rating for {last_name} to {rating}")  # Отладка: вывод данных для обновления

            connection = create_db_connection()
            cursor = connection.cursor()

            try:
                cursor.execute("""
                    UPDATE Rating r
                    JOIN User u ON u.id = r.user_id
                    SET r.quarterly_rating = %s
                    WHERE u.full_name LIKE %s
                """, (rating, '%' + last_name + '%'))
                connection.commit()
                logging.info(f"Rating updated for {last_name}")
            except Exception as e:
                logging.error(f"Error updating rating for {last_name}: {e}")
                connection.rollback()
            finally:
                cursor.close()
                connection.close()
    except Exception as e:
        logging.error(f"Error in update_ratings_from_google_sheets: {e}")

def map_deals_to_score(deals):
    if deals == 0:
        return 0
    elif deals in [1, 2]:
        return 1
    elif deals == 3:
        return 2
    elif deals in [4, 5]:
        return 3
    elif deals in [6, 7]:
        return 4
    else:
        return 5

def update_avg_deals_from_google_sheets():
    try:
        df = fetch_google_sheet_data('Лист1')  # Лист1 также содержит данные по количеству сделок

        logging.debug("Исходные данные из Google Sheets (Лист1):")
        logging.debug(df.head(30))  # Отладка: вывод первых 30 строк данных

        # Заменить пустые значения на '0' и преобразовать в int
        df['кол-во сделок'] = df['кол-во сделок'].replace('', '0').astype(int)
        df['avg_deals'] = df['кол-во сделок'].apply(map_deals_to_score)

        logging.debug("Данные после преобразования:")
        logging.debug(df.head(30))  # Отладка: вывод первых 30 строк данных после преобразования

        for index, row in df.iterrows():
            last_name = row['Сотрудник']
            avg_deals = row['avg_deals']

            logging.info(f"Updating avg_deals for {last_name} to {avg_deals}")  # Отладка: вывод данных для обновления

            connection = create_db_connection()
            cursor = connection.cursor()

            try:
                cursor.execute("""
                    UPDATE Rating r
                    JOIN User u ON u.id = r.user_id
                    SET r.avg_deals = %s
                    WHERE u.full_name LIKE %s
                """, (avg_deals, '%' + last_name + '%'))
                connection.commit()
                logging.info(f"Avg deals updated for {last_name}")
            except Exception as e:
                logging.error(f"Error updating avg_deals for {last_name}: {e}")
                connection.rollback()
            finally:
                cursor.close()
                connection.close()
    except Exception as e:
        logging.error(f"Error in update_avg_deals_from_google_sheets: {e}")

def map_cards_to_score(cards):
    if cards <= 5:
        return 5
    elif 6 <= cards <= 15:
        return 4
    elif 16 <= cards <= 25:
        return 3
    elif 26 <= cards <= 35:
        return 2
    elif 36 <= cards <= 45:
        return 1
    else:
        return 0

def update_crm_cards_from_google_sheets():
    try:
        df = fetch_google_sheet_data('Заполнение карт')

        logging.debug("Исходные данные из Google Sheets (Заполнение карт):")
        logging.debug(df.head(30))  # Отладка: вывод первых 30 строк данных

        # Заменить пустые значения на '0' и преобразовать в int
        df['Карты'] = df['Карты'].replace('', '0').astype(int)
        df['crm_cards'] = df['Карты'].apply(map_cards_to_score)

        logging.debug("Данные после преобразования:")
        logging.debug(df.head(30))  # Отладка: вывод первых 30 строк данных после преобразования

        for index, row in df.iterrows():
            last_name = row['Сотрудник']
            crm_cards = row['crm_cards']

            logging.info(f"Updating crm_cards for {last_name} to {crm_cards}")  # Отладка: вывод данных для обновления

            connection = create_db_connection()
            cursor = connection.cursor()

            try:
                cursor.execute("""
                    UPDATE Rating r
                    JOIN User u ON u.id = r.user_id
                    SET r.crm_cards = %s
                    WHERE u.full_name LIKE %s
                """, (crm_cards, '%' + last_name + '%'))
                connection.commit()
                logging.info(f"CRM cards updated for {last_name}")
            except Exception as e:
                logging.error(f"Error updating crm_cards for {last_name}: {e}")
                connection.rollback()
            finally:
                cursor.close()
                connection.close()
    except Exception as e:
        logging.error(f"Error in update_crm_cards_from_google_sheets: {e}")

if __name__ == '__main__':
    update_ratings_from_google_sheets()
    update_avg_deals_from_google_sheets()
    update_crm_cards_from_google_sheets()
