import asyncio
import sqlite3
import os
import ctypes
import time
import edge_tts

DB_NAME = "viva.db"
TEMP_AUDIO_FILE = "temp_question.mp3"

def play_mp3_windows(file_path):
    """Play an MP3 file using the native Windows MCI interface (no external dependencies)."""
    abs_path = os.path.abspath(file_path)
    winmm = ctypes.windll.winmm
    
    # Close any open instance just in case
    winmm.mciSendStringW("close temp_audio", None, 0, None)
    
    # Open the file
    open_cmd = f'open "{abs_path}" type mpegvideo alias temp_audio'
    res = winmm.mciSendStringW(open_cmd, None, 0, None)
    if res != 0:
        raise RuntimeError(f"Failed to open audio file via MCI (Error code: {res})")
        
    # Play the file and wait for it to complete
    play_cmd = 'play temp_audio wait'
    winmm.mciSendStringW(play_cmd, None, 0, None)
    
    # Close the file to release resources
    winmm.mciSendStringW("close temp_audio", None, 0, None)

async def main():
    # 1. Fetch the first question from database
    if not os.path.exists(DB_NAME):
        print(f"Error: Database file '{DB_NAME}' not found. Please run setup_db.py first.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, question_text FROM viva_questions ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print("No questions found in the database.")
        return
        
    q_id, question_text = row
    print(f"Fetched Question ID {q_id}: '{question_text}'")
    
    # 2. Convert text to speech using edge-tts
    # We will use a standard clear English voice
    voice = "en-US-GuyNeural"
    communicate = edge_tts.Communicate(question_text, voice)
    
    print(f"Generating TTS audio with voice '{voice}'...")
    await communicate.save(TEMP_AUDIO_FILE)
    
    # 3. Play the generated MP3
    print("Speaking question out loud...")
    try:
        play_mp3_windows(TEMP_AUDIO_FILE)
        print("Question spoken successfully")
    except Exception as e:
        print(f"Error playing audio: {e}")
    finally:
        # 4. Clean up temporary audio file
        if os.path.exists(TEMP_AUDIO_FILE):
            try:
                os.remove(TEMP_AUDIO_FILE)
            except Exception as e:
                print(f"Warning: Could not remove temporary file {TEMP_AUDIO_FILE}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
