import sqlite3
import os

DB_NAME = "viva.db"

def create_database():
    # Connect to the database (it will be created if it doesn't exist)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create the viva_questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS viva_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            viva_answers TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    print("Database and table 'viva_questions' created successfully.")
    
    # Check if table already has data, if so, skip inserting dummy questions to prevent duplicates
    cursor.execute("SELECT COUNT(*) FROM viva_questions")
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Dummy computer science viva questions
        dummy_questions = [
            ("Explain the difference between a process and a thread.",),
            ("What is virtual memory and how does it work?",),
            ("Explain the concept of time complexity and Big O notation.",),
            ("What are the differences between TCP and UDP?",),
            ("What is a primary key and how does it differ from a foreign key in database design?",)
        ]
        
        cursor.executemany("INSERT INTO viva_questions (question_text) VALUES (?)", dummy_questions)
        conn.commit()
        print(f"Inserted {len(dummy_questions)} dummy computer science questions.")
    else:
        print(f"Table already contains {count} records. Skipping inserting dummy questions.")

    conn.close()

def verify_database():
    print("\n--- Verifying database contents ---")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, question_text, viva_answers FROM viva_questions")
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"ID: {row[0]}")
        print(f"Question: {row[1]}")
        print(f"Answer: {row[2]}")
        print("-" * 40)
        
    conn.close()

if __name__ == "__main__":
    create_database()
    verify_database()
