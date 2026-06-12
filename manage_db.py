import sqlite3
import sys
import os

DB_NAME = "viva.db"

def get_connection():
    if not os.path.exists(DB_NAME):
        print(f"Error: Database '{DB_NAME}' not found. Run setup_db.py first.")
        sys.exit(1)
    return sqlite3.connect(DB_NAME)

def view_db():
    """Display all rows in the viva_questions table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_text, viva_answers FROM viva_questions")
    rows = cursor.fetchall()
    conn.close()

    print("\n" + "=" * 50)
    print("           VIVA QUESTIONS & ANSWERS")
    print("=" * 50)
    for row in rows:
        q_id, question, answer = row
        answer_display = answer if answer is not None else "[NULL] (Unanswered)"
        if answer_display == "":
            answer_display = "[Empty String] (No speech detected / Silence)"
            
        print(f"ID:       {q_id}")
        print(f"Question: {question}")
        print(f"Answer:   {answer_display}")
        print("-" * 50)
    print(f"Total Questions: {len(rows)}\n")

def reset_answers():
    """Reset all answers in the table back to NULL."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE viva_questions SET viva_answers = NULL")
    conn.commit()
    conn.close()
    print("Successfully reset all answers to NULL! You can now run viva_speech.py again.")

def add_question(question_text):
    """Add a new question to the database."""
    if not question_text.strip():
        print("Error: Question text cannot be empty.")
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO viva_questions (question_text) VALUES (?)", (question_text.strip(),))
    conn.commit()
    q_id = cursor.lastrowid
    conn.close()
    print(f"Successfully added new question (ID: {q_id}): '{question_text}'")

def print_usage():
    print("Usage: python manage_db.py [command]")
    print("\nCommands:")
    print("  view                - View all questions and their saved answers")
    print("  reset               - Clear all saved answers (sets them to NULL)")
    print("  add \"[Question]\"    - Add a new question to the viva session")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "view":
        view_db()
    elif cmd == "reset":
        reset_answers()
    elif cmd == "add":
        if len(sys.argv) < 3:
            print("Error: Please specify the question text in double quotes.")
            print("Example: python manage_db.py add \"What is polymorphism?\"")
            sys.exit(1)
        add_question(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        print_usage()
        sys.exit(1)
