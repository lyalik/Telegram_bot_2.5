from flask import Flask, render_template, request
import sqlite3
import config

app = Flask(__name__)

# Подключение к базе данных
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()


@app.route('/')
def index():
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE status='privileged'")
    privileged_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='subscription'")
    total_income = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='donation'")
    total_donations = cursor.fetchone()[0] or 0

    return render_template('index.html', total_users=total_users, privileged_users=privileged_users,
                           total_income=total_income, total_donations=total_donations)


@app.route('/users')
def users():
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    return render_template('users.html', users=users)


@app.route('/transactions')
def transactions():
    cursor.execute("SELECT * FROM transactions")
    transactions = cursor.fetchall()
    return render_template('transactions.html', transactions=transactions)


@app.route('/update_status', methods=['POST'])
def update_status():
    user_id = request.form['user_id']
    status = request.form['status']
    cursor.execute("UPDATE users SET status=? WHERE telegram_id=?", (status, user_id))
    conn.commit()
    return 'Status updated successfully'


if __name__ == '__main__':
    app.run(debug=True)