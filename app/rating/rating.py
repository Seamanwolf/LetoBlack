from flask import Blueprint, Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory, abort
from app.utils import create_db_connection, login_required
from werkzeug.security import generate_password_hash
from functools import wraps
from flask_login import login_required as flask_login_required, current_user
from google.oauth2.credentials import Credentials
import gspread

rating_bp = Blueprint('rating', __name__)

@rating_bp.route('/api/update_ratings', methods=['POST'])
def update_ratings():
    update_ratings_from_google_sheets()
    return jsonify({'success': True})

@rating_bp.route('/show_rating')
@login_required
def show_rating():
    if current_user.role != 'admin':
        flash('Доступ разрешен только администраторам.', 'danger')
        return redirect(url_for('auth.login'))

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT u.id, u.full_name, u.department, u.hire_date, 
           IFNULL(r.quarterly_rating, 0) as quarterly_rating, 
           IFNULL(r.avg_deals, 0) as avg_deals, 
           IFNULL(r.properties, 0) as properties, 
           IFNULL(r.scripts, 0) as scripts, 
           IFNULL(r.crm_cards, 0) as crm_cards
    FROM User u
    LEFT JOIN Rating r ON u.id = r.user_id
    WHERE (u.role = 'user' OR u.role = 'broker') AND u.fired = FALSE
    """
    cursor.execute(query)
    ratings = cursor.fetchall()
    cursor.close()
    connection.close()

    for rating in ratings:
        rating['avg_score'] = round(sum([
            rating['quarterly_rating'],
            rating['avg_deals'],
            rating['properties'],
            rating['scripts'],
            rating['crm_cards']
        ]) / 5, 1)

    ratings.sort(key=lambda x: x['avg_score'], reverse=True)
    return render_template('rating.html', ratings=ratings)


@rating_bp.route('/api/add_rating', methods=['POST'])
@login_required
def add_rating():
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.json
    full_name = data.get('full_name')

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT id FROM User WHERE full_name = %s", (full_name,))
    user = cursor.fetchone()

    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'})

    try:
        cursor.execute("""
            INSERT INTO Rating (user_id, quarterly_rating, avg_deals, properties, scripts, crm_cards)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user['id'],
            data.get('quarterly_rating', 0),
            data.get('avg_deals', 0),
            data.get('properties', 0),
            data.get('scripts', 0),
            data.get('crm_cards', 0)
        ))
        connection.commit()
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

    return jsonify({'success': True})

def classify_deals(deal_count):
    try:
        deal_count = int(deal_count)
    except ValueError:
        return 0
    if deal_count == 0:
        return 0
    elif 1 <= deal_count <= 2:
        return 1
    elif deal_count == 3:
        return 2
    elif 4 <= deal_count <= 5:
        return 3
    elif 6 <= deal_count <= 7:
        return 4
    elif deal_count >= 8:
        return 5
    return 0  # Default return value if none of the conditions are met

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@rating_bp.route('/api/upload_avg_deals', methods=['POST'])
def upload_avg_deals():
    logging.info("Received request to upload_avg_deals")
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(AVG_DEALS_UPLOAD_FOLDER, filename)
        file.save(file_path)
        logging.info(f"File {filename} saved to {file_path}")

        try:
            # Load the Excel file
            df = pd.read_excel(file_path)
            logging.debug(f"Excel file loaded: {df.head()}")

            # Load user data from the database
            connection = create_db_connection()
            user_df = pd.read_sql('SELECT id, full_name FROM User', connection)
            logging.debug(f"User table loaded: {user_df.head()}")

            # Extract last names with improved cleaning
            user_df['last_name'] = user_df['full_name'].apply(lambda x: x.split()[0].strip().lower())
            df['Главный_фамилии'] = df['Главный'].str.lower().str.split()
            df['Сработка_фамилии'] = df['Сработка'].str.lower().str.split()

            # Flatten the lists of last names and create a new DataFrame
            all_last_names = pd.concat([df['Главный_фамилии'].explode(), df['Сработка_фамилии'].explode()]).reset_index(drop=True).to_frame(name='last_name')

            # Check for unique last names
            logging.debug(f"Last names in User table: {user_df['last_name'].unique()}")
            logging.debug(f"Last names in Excel file: {all_last_names['last_name'].unique()}")

            # Merge data based on last names
            merged_df = pd.merge(user_df, all_last_names, how='left', on='last_name')
            logging.debug(f"Merged DataFrame: {merged_df.head()}")

            # Display rows without matches for debugging
            unmatched_df = merged_df[merged_df['last_name'].isna()]
            logging.debug(f"Unmatched rows: {unmatched_df}")

            # Count deals for each user and classify them
            deal_counts = all_last_names['last_name'].value_counts().to_dict()
            merged_df['Ср.кол-во сделок'] = merged_df['last_name'].map(deal_counts).fillna(0).astype(int).apply(classify_deals)
            logging.debug(f"Classified DataFrame: {merged_df.head()}")

            # Update database
            cursor = connection.cursor()
            for index, row in merged_df.iterrows():
                if pd.notna(row['Ср.кол-во сделок']):
                    logging.debug(f"Updating user_id {row['id']} with avg_deals {row['Ср.кол-во сделок']}")
                    cursor.execute('UPDATE Rating SET avg_deals = %s WHERE user_id = %s', (row['Ср.кол-во сделок'], row['id']))
            connection.commit()
            logging.info("Database update complete")
            cursor.close()
            connection.close()

            return jsonify({'message': 'File successfully processed and data updated'}), 200
        except Exception as e:
            logging.error(f"Error during file upload and processing: {e}")
            return jsonify({'message': f"Error during file upload and processing: {e}"}), 500
    else:
        return jsonify({'message': 'Invalid file type'}), 400

@rating_bp.route('/api/update_rating', methods=['POST'])
@login_required
def update_rating():
    data = request.json
    print(f"Received data for updating rating: {data}")  # Отладка

    connection = create_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE Rating
            SET quarterly_rating = %s, avg_deals = %s, properties = %s, scripts = %s, crm_cards = %s
            WHERE user_id = %s
        """, (
            data.get('quarterly_rating'),
            data.get('avg_deals'),
            data.get('properties'),
            data.get('scripts'),
            data.get('crm_cards'),
            # , data.get('call_duration'),
            # data.get('experience'),
            data.get('user_id')
        ))
        connection.commit()
        print("Rating updated successfully")  # Отладка
        return jsonify({'success': True})
    except Exception as e:
        connection.rollback()
        print(f"Error updating rating: {str(e)}")  # Отладка
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

@rating_bp.route('/api/get_rating', methods=['GET'])
@login_required
def get_rating():
    full_name = request.args.get('full_name')
    print(f"Fetching rating for user: {full_name}")  # Отладка

    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.*, u.full_name, u.id as user_id
        FROM Rating r
        JOIN User u ON r.user_id = u.id
        WHERE u.full_name = %s
    """, (full_name,))
    rating = cursor.fetchone()
    cursor.close()
    connection.close()

    if not rating:
        print("Rating not found for user:", full_name)  # Отладка
        return jsonify({'success': False, 'message': 'Рейтинг не найден'})

    print("Fetched rating:", rating)  # Отладка
    return jsonify({'success': True, **rating})

@rating_bp.route('/api/clear_values', methods=['POST'])
@login_required
def clear_values():
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            UPDATE Rating
            SET quarterly_rating = 0, avg_deals = 0, properties = 0, scripts = 0, crm_cards = 0
            -- , call_duration = 0, experience = 0
        """)
        connection.commit()
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        connection.close()

    return jsonify({'success': True})


@rating_bp.route('/integral_rating')
@login_required
def integral_rating():
    # Получаем все записи из таблицы integral_ratings
    connection = create_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM integral_ratings")
    records = cursor.fetchall()
    cursor.close()
    connection.close()

    # Вычисляем интегральный рейтинг для каждой записи по формуле:
    # (общая выручка / 120) * (количество сделок) с округлением до 3 знаков
    for record in records:
        try:
            total_revenue = float(record['total_revenue'])
            deals = int(record['deals'])
            rating = (total_revenue / 120) * deals
        except Exception:
            rating = 0.0
        record['integral_rating'] = round(rating, 3)
    # Сортируем записи по убыванию интегрального рейтинга
    records.sort(key=lambda r: r['integral_rating'], reverse=True)
    return render_template('integral_rating.html', records=records)

@rating_bp.route('/sync_integral_rating', methods=['POST'])
@login_required
def sync_integral_rating():
    # Получаем URL Google Таблицы из формы (поле выбора ссылки)
    google_sheet_url = request.form.get('google_sheet_url')
    if not google_sheet_url:
        flash('Ссылка на Google Таблицу не указана', 'danger')
        return redirect(url_for('rating.integral_rating'))
    try:
        # Используем сохранённые google_credentials (интеграция уже настроена)
        if 'google_credentials' not in session:
            flash('Необходима авторизация в Google', 'danger')
            return redirect(url_for('callcenter.integrations'))
        credentials = Credentials(**session['google_credentials'])
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_url(google_sheet_url)
        # Предположим, что данные находятся на листе "Лист1"
        worksheet = sheet.worksheet("Лист1")
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            flash('В таблице нет данных', 'danger')
            return redirect(url_for('rating.integral_rating'))
        header = data[0]
        try:
            idx_name = header.index("ФИО")
            idx_revenue = header.index("Общая выручка")
            idx_deals = header.index("Количество сделок")
        except ValueError:
            flash('В таблице отсутствуют необходимые колонки (ФИО, Общая выручка, Количество сделок)', 'danger')
            return redirect(url_for('rating.integral_rating'))
        today_str = date.today().strftime('%Y-%m-%d')
        records_to_insert = []
        for row in data[1:]:
            try:
                full_name = row[idx_name].strip()
                total_revenue = float(row[idx_revenue].replace(',', '.'))
                deals = int(row[idx_deals])
                records_to_insert.append((today_str, full_name, total_revenue, deals))
            except Exception:
                continue
        if not records_to_insert:
            flash('В таблице не найдено корректных записей', 'danger')
            return redirect(url_for('rating.integral_rating'))
        # Сохраняем данные в БД – предварительно удаляем записи за текущую дату, чтобы избежать дублирования
        connection = create_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM integral_ratings WHERE date = %s", (today_str,))
        insert_query = "INSERT INTO integral_ratings (date, full_name, total_revenue, deals) VALUES (%s, %s, %s, %s)"
        cursor.executemany(insert_query, records_to_insert)
        connection.commit()
        cursor.close()
        connection.close()
        flash('Данные успешно синхронизированы', 'success')
    except Exception as e:
        flash(f"Ошибка при синхронизации: {str(e)}", 'danger')
    return redirect(url_for('rating.integral_rating'))

@rating_bp.route('/delete_integral_table', methods=['POST'])
@login_required
def delete_integral_table():
    """
    Этот маршрут удаляет запись об интеграции Google Таблицы из базы данных.
    Предполагается, что информация об интеграции хранится в таблице 'integral_integration'.
    После успешного удаления возвращается JSON-ответ с success=True.
    """
    connection = create_db_connection()
    cursor = connection.cursor()
    try:
        # Удаляем запись об интеграции (если таблица интеграции имеет другую структуру,
        # адаптируйте запрос соответственно)
        cursor.execute("DELETE FROM integral_integration")
        connection.commit()
        return jsonify({'success': True, 'message': 'Интеграция удалена'}), 200
    except Exception as e:
        connection.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        connection.close()