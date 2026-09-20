import sqlite3
import subprocess


def run_command(user_input):
    # VULNERABILITY: command injection
    subprocess.run(f"ls {user_input}", shell=True, check=False)

def query_db(username, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # VULNERABILITY: SQL injection
    cursor.execute(f"SELECT * FROM users WHERE user='{username}' AND pass='{password}'")

SECRET_KEY = "hardcoded-super-secret-key-12345"  # VULNERABILITY: hardcoded secret
