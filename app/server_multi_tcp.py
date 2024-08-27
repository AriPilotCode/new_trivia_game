from sqlite3 import OperationalError
from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import random
import json
import requests
from requests.exceptions import HTTPError, RequestException
from loguru import logger
from sqlalchemy.dialects.postgresql import psycopg2
from werkzeug.security import generate_password_hash
import os
import time
import psycopg2
from psycopg2 import OperationalError
from flask import Flask, render_template, request, redirect, url_for, session, g
import hmac
import hashlib

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'  # Add a secret key for session management

DATABASE = {
    'host': 'db',  # Name of the PostgreSQL service in docker-compose 'localhost'/'db'
    'port': '5432',
    'dbname': 'mydatabase',
    'user': 'user',
    'password': 'password'
}

MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds
MAX_MSG_SIZE = 1024
SERVER_PORT = 5679
SERVER_IP = "0.0.0.0"
# USERS_FILE = '/Users/arielglazer/cybellum/Trivia_game-/tusers.json'
# QUESTIONS_CACHE_FILE = '/Users/arielglazer/cybellum/Trivia_game-/app/data/questions_cache.json'
# QUESTIONS_CACHE_FILE_FOR_NOAM = '/Users/arielglazer/cybellum/Trivia_game-/app/data/questions_for_noam.json'
QUESTIONS_CACHE_FILE = '/app/app/data/questions_cache.json'
QUESTIONS_CACHE_FILE_FOR_NOAM = '/app/app/data/questions_for_noam.json'
# Define category mapping
CATEGORY_MAPPING = {
    'General Knowledge': 9,
    'Books': 10,
    'Film': 11,
    'Music': 12,
    'Musicals & Theatres': 13,
    'Video Games': 15,
    'Board Games': 16,
    'Science & Nature': 17,
    'Computers': 18,
    'Gadgets': 19,
    'Nature': 20,
    'Sports': 21,
    'Geography': 22,
    'History': 23,
    'Politics': 24,
    'Art': 25,
    'Animals': 26,
    'Vehicles': 27,
    'Celebrities': 29,
    'Art & Literature': 30
}


# Load users from file
# try:
#     with open(USERS_FILE, 'r') as f:
#         users = json.load(f)
# except json.JSONDecodeError as e:
#     logger.error(f"JSON decoding error: {e}")
# except Exception as e:
#     logger.error(f"Error loading users: {e}")

def load_user_database():
    try:
        conn = get_db()  # Get the database connection
        with conn.cursor() as cursor:
            cursor.execute("SELECT username, password, score, questions_asked FROM users")
            rows = cursor.fetchall()
            users = {row[0]: {'password': row[1], 'score': row[2], 'questions_asked': row[3]} for row in rows}
        return users
    except Exception as e:
        logger.error(f"Error loading users from database: {e}")
        return {}


# def save_user_database(users):
#     with open(USERS_FILE, 'w') as file:
#         json.dump(users, file)


def clear_questions_cache():
    try:
        with open(QUESTIONS_CACHE_FILE, 'w') as file:
            file.write('')  # Write an empty string to clear the file
        print("Questions cache cleared.")
    except Exception as e:
        print(f"Error clearing questions cache: {e}")
def clear_questions_asked(username):
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                UPDATE users
                SET questions_asked = '{}'
                WHERE username = %s
                ''',
                (username,)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Error clearing questions asked for user {username}: {e}")


def update_questions_asked(username, question_id):
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            # Define the SQL query to append to the JSON array
            update_query = '''
            UPDATE users
            SET questions_asked = COALESCE(questions_asked, '[]'::jsonb) || %s::jsonb
            WHERE username = %s;
            '''

            # Convert the question_id to a JSON array format
            question_id_json = json.dumps([question_id])

            # Execute the query with the JSON array value and username
            cursor.execute(update_query, (question_id_json, username))

        # Commit the transaction
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating questions asked for user {username}: {e}")


def save_user_score(username, new_score):
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute(
                '''
                UPDATE users
                SET score = %s
                WHERE username = %s
                ''',
                (new_score, username)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving user score to the database for {username}: {e}")


def load_questions(difficulty=None, category_name=None):
    questions = {}

    # If difficulty and category are provided, try to fetch the appropriate questions
    if difficulty and category_name:
        # Fetch questions and update the cache if needed
        questions = fetch_and_cache_questions(difficulty, category_name)
    else:
        # Check if the cache file exists
        if os.path.exists(QUESTIONS_CACHE_FILE):
            with open(QUESTIONS_CACHE_FILE, 'r') as f:
                # Check if the file is empty
                if os.stat(QUESTIONS_CACHE_FILE).st_size == 0:
                    logger.info("Questions cache file is empty. Fetching new questions...")
                    questions = fetch_and_cache_questions(difficulty, category_name)
                else:
                    try:
                        questions = json.load(f)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from cache file: {e}")
                        logger.info("Fetching new questions due to cache file error...")
                        questions = fetch_and_cache_questions(difficulty, category_name)
        else:
            logger.info("Questions cache file does not exist. Fetching new questions...")
            questions = fetch_and_cache_questions(difficulty, category_name)

    return questions


def load_question_for_noam():
    with open(QUESTIONS_CACHE_FILE_FOR_NOAM, 'r') as f:
        questions = json.load(f)
    return questions


def fetch_and_cache_questions(difficulty, category_name):

    category_id = CATEGORY_MAPPING.get(category_name, None)
    if os.path.exists(QUESTIONS_CACHE_FILE) and os.path.getsize(QUESTIONS_CACHE_FILE) > 0:
        with open(QUESTIONS_CACHE_FILE, 'r') as f:
            questions = json.load(f)
        return questions
    url = f'https://opentdb.com/api.php?amount=50&category={category_id}&difficulty={difficulty}&lang=he'
    max_retries = 5
    backoff_factor = 1
    questions = {}

    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            counter = 1
            for item in data['results']:
                questions[counter] = {
                    'question': item['question'],
                    'correct_answer': item['correct_answer'],
                    'incorrect_answers': item['incorrect_answers']
                }
                counter += 1

            with open(QUESTIONS_CACHE_FILE, 'w') as f:
                json.dump(questions, f, indent=4)
            break
        except HTTPError as http_err:
            if response.status_code == 429:
                wait_time = backoff_factor * (2 ** attempt)
                logger.warning(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"HTTP error occurred: {http_err}")
                break
        except RequestException as req_err:
            logger.error(f"Request error occurred: {req_err}")
            break
        except Exception as err:
            logger.error(f"Other error occurred: {err}")
            break

    return questions


# def load_user_database():
#     return users

def filter_question_asked(username, question_data):
    users = load_user_database()
    questions_list = [i for i in question_data.keys() if i not in users[username].get('questions_asked', [])]
    return questions_list


def create_random_question(username, difficulty, category_name):
    users = load_user_database()

    if username not in users:
        logger.error(f"User {username} not found")
        return None
    if username == 'noam':
        question_data = load_question_for_noam()
    # Fetch questions based on the selected difficulty and category
    else:
        question_data = fetch_and_cache_questions(difficulty, category_name)

    not_asked_question_list = filter_question_asked(username, question_data)
    try:
        question_id = random.choice(not_asked_question_list)
        question_info = question_data[question_id]

        # # Ensure 'questions_asked' exists
        # if 'questions_asked' not in users[username]:
        #     users[username]['questions_asked'] = []
        #     users[username]['questions_asked'].append(question_id)
        update_questions_asked(username, question_id)

        # with open(USERS_FILE, 'w') as f:
        #     json.dump(users, f, indent=4)

        q_list = question_info['incorrect_answers']
        q_list.append(question_info['correct_answer'])
        q_list.sort()

        return {
            "key": question_id,
            "question": question_info['question'],
            "answers": q_list
        }
    except Exception as e:
        logger.error(f"Error creating question: {e}")
        return None


# Route for the login page
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('select'))
    return render_template('login.html')


# Route to handle the login logic
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_user_database()
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            data = request.form

        if not data:
            return jsonify({"status": "error", "message": "Invalid data format"}), 400

        username = data.get('username')
        password = data.get('password')

        if username in users and verify_password(users[username]['password'], password):
            session['username'] = username
            logger.info(f"User {username} logged in successfully.")
            return jsonify({"status": "success", "message": "Login successful!"}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid username or password"}), 401

    return render_template('login.html')


def get_db():
    if 'db' not in g:
        retries = 0
        while retries < MAX_RETRIES:
            try:
                g.db = psycopg2.connect(
                    host=DATABASE['host'],
                    port=DATABASE['port'],
                    dbname=DATABASE['dbname'],
                    user=DATABASE['user'],
                    password=DATABASE['password']
                )
                print("Database connection successful.")
                return g.db
            except OperationalError as e:
                print(f"Database connection failed: {e}")
                retries += 1
                print(f"Retrying ({retries}/{MAX_RETRIES}) in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)

        # If the loop exits, it means all retries failed
        raise Exception("Failed to connect to the database after multiple attempts.")
    return g.db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, 'db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cur = get_db().cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            cur = db.cursor()
            cur.execute(f.read())
            db.commit()
            cur.close()


def generate_password_hash(password, algorithm='sha256', iterations=260000):
    salt = os.urandom(16).hex()
    hash_bytes = hashlib.pbkdf2_hmac(
        hash_name=algorithm,
        password=password.encode('utf-8'),
        salt=salt.encode('utf-8'),
        iterations=iterations
    )
    hash_hex = hash_bytes.hex()
    return f"{algorithm}:{iterations}${salt}${hash_hex}"


def verify_password(stored_password, provided_password):
    algorithm_and_iterations, salt, hash_value = stored_password.split('$')
    algorithm, iterations = algorithm_and_iterations.split(':')
    iterations = int(iterations)

    hash_bytes = hashlib.pbkdf2_hmac(
        hash_name=algorithm,
        password=provided_password.encode('utf-8'),
        salt=salt.encode('utf-8'),
        iterations=iterations
    )

    provided_hash = hash_bytes.hex()
    return hmac.compare_digest(provided_hash, hash_value)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Check if the content type is JSON
        if request.is_json:
            data = request.json  # Get JSON data from the request
        else:
            # If not JSON, handle form data
            data = request.form

        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"status": "error", "message": "Username and password are required"}), 400
        hashed_password = generate_password_hash(password)
        try:
            conn = get_db()
            with conn.cursor() as cursor:
                cursor.execute(
                    '''
                    INSERT INTO users (username, password, score, questions_asked)
                    VALUES (%s, %s, %s, %s)
                    ''',
                    (username, hashed_password, 0, [])  # Insert default values for score and questions_asked
                )
            conn.commit()
            return jsonify({"status": "success", "message": "Registration successful!"}), 200
        except psycopg2.IntegrityError:
            return jsonify({"status": "error", "message": "Username already exists"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return render_template('register.html')

# Route for the selection page
@app.route('/select')
def select():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('select.html')

# Route to handle the selection of category/difficulty


@app.route('/submit_selection', methods=['POST'])
def submit_selection():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 403

    data = request.get_json()
    difficulty = data.get('difficulty')
    category = data.get('category')

    # Verify if the category_id is valid
    if category not in CATEGORY_MAPPING:
        return jsonify({'status': 'error', 'message': 'Invalid category'}), 400

    # Save the selected difficulty and category ID in session
    session['difficulty'] = difficulty
    session['category'] = category

    return jsonify({'status': 'success', 'message': 'Selection successful!'}), 200


# Route for the game page
@app.route('/game')
def game():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('game.html')


# Route to get a random question
@app.route('/question', methods=['GET'])
def get_question():
    username = session.get('username')
    difficulty = session.get('difficulty')
    category = session.get('category')
    users = load_user_database()
    if username in users:
        question = create_random_question(username, difficulty, category)
        if question:
            return jsonify({"question": question}), 200
        else:
            return jsonify({"status": "error", "message": "No more questions available"}), 200
    else:
        return jsonify({"status": "error", "message": "User not found"}), 404

# Route to submit an answer
@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    logger.info(f"Received data: {data}")

    users = load_user_database()
    username = data.get('username')
    question_key = data.get('questionKey')
    answer = data.get('answer')

    if not username or not question_key or not answer:
        logger.error("Missing data in request")
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    if username not in users:
        logger.error(f"User {username} not found")
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    if username == 'noam':
        question_data = load_question_for_noam()
    else:
        question_data = load_questions()
    if str(question_key) not in question_data:
        logger.error(f"Invalid question key: {question_key}")
        return jsonify({'status': 'error', 'message': 'Invalid question key'}), 404

    correct_answer = question_data[str(question_key)]['correct_answer']
    if answer == correct_answer:
        logger.info(f"Correct answer for question {question_key} by user {username}")

        # Add points for the correct answer
        # user_data = users[username]
        # user_data['score'] = user_data.get('score', 0) + 20  # Add 20 points for a correct answer
        # Assume 'users' is a dictionary containing user data

        user_data = users[username]
        new_score = user_data.get('score', 0) + 20  # Add 20 points for a correct answer
        # Save the updated score to the database
        save_user_score(username, new_score)

        return jsonify({'status': 'success', 'message': 'תְּשׁוּבָה נְכוֹנָה!'}), 200
    else:
        logger.info(f"Incorrect answer for question {question_key} by user {username}")
        return jsonify(
            {'status': 'error', 'message': f' טָעוּת!! הַתְּשׁוּבָה הִיא {correct_answer} '}), 200


@app.route('/score', methods=['GET'])
def get_score():
    username = session.get('username')

    if not username:
        return jsonify({"status": "error", "message": "User not logged in"}), 401

    users = load_user_database()

    user_data = users.get(username)

    if not user_data:
        return jsonify({"status": "error", "message": "User not found"}), 404

    score = user_data.get("score", 0)  # Default score to 0 if not found

    return jsonify({"status": "success", "score": score}), 200

# Route to get the high score
@app.route('/highscore', methods=['GET'])
def get_highscore():
    return jsonify({"highscore": "highest score is 100"}), 200

# Route to get logged users
@app.route('/logged_users', methods=['GET'])
def get_logged_users():
    return jsonify({"logged_users": ["user1", "user2"]}), 200

# Route to handle user logout

@app.route('/logout', methods=['POST'])
def logout():
    users = load_user_database()
    username = session.pop('username', None)

    if username:
        clear_questions_asked(username)  # Clear the questions_asked list
    if username != 'noam':
        clear_questions_cache()
        # with open(USERS_FILE, 'w') as file:
        #     json.dump(users, file)  # Save the updated user data

        return jsonify({"status": "success", "message": "Logged out successfully!"}), 200
    else:
        return jsonify({"status": "error", "message": "No active session found!"}), 400


def create_users_table():
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                score INT DEFAULT 0,  -- Integer column for score
                questions_asked JSONB DEFAULT '[]'
            );
        ''')
        conn.commit()


def main():
    logger.info(f"Starting server on {SERVER_IP}:{SERVER_PORT}")

    # Ensure that create_users_table runs within the Flask application context
    with app.app_context():
        create_users_table()  # Create the users table

    # Start the Flask app
    app.run(host=SERVER_IP, port=SERVER_PORT, debug=True)


if __name__ == '__main__':
    main()
