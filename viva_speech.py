import asyncio
import sqlite3
import os
import ctypes
import time
import wave
import pyaudio
import webrtcvad
from faster_whisper import WhisperModel

DB_NAME = "viva.db"
TEMP_TTS_FILE = "temp_question.mp3"
TEMP_RECORD_FILE = "answer.wav"

def play_mp3_windows(file_path):
    """Play an MP3 file using the native Windows MCI interface."""
    abs_path = os.path.abspath(file_path)
    winmm = ctypes.windll.winmm
    
    # Close any open instance just in case
    winmm.mciSendStringW("close temp_audio", None, 0, None)
    
    # Open the file
    open_cmd = f'open "{abs_path}" type mpegvideo alias temp_audio'
    res = winmm.mciSendStringW(open_cmd, None, 0, None)
    if res != 0:
        raise RuntimeError(f"Failed to open audio file via MCI (Error code: {res})")
        
    # Play the file and wait for completion
    play_cmd = 'play temp_audio wait'
    winmm.mciSendStringW(play_cmd, None, 0, None)
    
    # Close the file
    winmm.mciSendStringW("close temp_audio", None, 0, None)

async def speak_question(text):
    """Generate TTS audio and play it aloud."""
    import edge_tts
    voice = "en-US-GuyNeural"
    communicate = edge_tts.Communicate(text, voice)
    
    # Save TTS as a temporary file
    await communicate.save(TEMP_TTS_FILE)
    
    try:
        # Play TTS audio
        play_mp3_windows(TEMP_TTS_FILE)
    finally:
        # Clean up temporary TTS file
        if os.path.exists(TEMP_TTS_FILE):
            try:
                os.remove(TEMP_TTS_FILE)
            except Exception as e:
                print(f"Warning: Could not remove temporary TTS file: {e}")

def record_answer():
    """Record microphone input with Voice Activity Detection (VAD) control."""
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK_SIZE = 320  # 20ms frames at 16000Hz (320 samples)
    
    p = pyaudio.PyAudio()
    vad = webrtcvad.Vad()
    vad.set_mode(2)  # Aggressiveness level: 2
    
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )
    
    print("\nRecording student answer... (Speak now)")
    
    frames = []
    start_time = time.time()
    last_speech_time = start_time
    stop_reason = ""
    
    try:
        while True:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Check 30-second hard cap
            if elapsed_time >= 30.0:
                stop_reason = "max time reached"
                break
                
            # Check 5-second silence timeout
            if current_time - last_speech_time >= 5.0:
                stop_reason = "silence timeout"
                break
                
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            
            is_speech = vad.is_speech(data, RATE)
            
            if is_speech:
                last_speech_time = time.time()
                print("*", end="", flush=True)
            else:
                print(".", end="", flush=True)
                
    except KeyboardInterrupt:
        stop_reason = "manual interrupt"
        print("\nRecording interrupted by user.")
    finally:
        print(f"\nRecording stopped. Reason: {stop_reason}")
        stream.stop_stream()
        stream.close()
        p.terminate()
        
    # Save audio as answer.wav
    try:
        wf = wave.open(TEMP_RECORD_FILE, "wb")
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wf.close()
        print(f"Audio recorded successfully ({len(frames) * 0.02:.2f} seconds)")
    except Exception as e:
        print(f"Error saving wave file: {e}")

def transcribe_answer(model):
    """Transcribe answer.wav using the preloaded faster-whisper model."""
    if not os.path.exists(TEMP_RECORD_FILE):
        print(f"Error: {TEMP_RECORD_FILE} not found.")
        return ""
        
    print("Transcribing recorded answer...")
    segments, info = model.transcribe(TEMP_RECORD_FILE, beam_size=5)
    
    text_segments = []
    for segment in segments:
        text_segments.append(segment.text)
        
    transcribed_text = " ".join(text_segments).strip()
    
    # Clean up recording file
    if os.path.exists(TEMP_RECORD_FILE):
        try:
            os.remove(TEMP_RECORD_FILE)
        except Exception as e:
            print(f"Warning: Could not remove temporary recording file: {e}")
            
    return transcribed_text

async def main():
    if not os.path.exists(DB_NAME):
        print(f"Error: Database '{DB_NAME}' not found. Please run setup_db.py first.")
        return

    # Load faster-whisper model once at the start of the session to avoid reload latency
    print("Loading faster-whisper model (base size, CPU, int8)...")
    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    print("Model loaded successfully.")

    # Connect to database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Fetch all questions where answer is NULL
    cursor.execute("SELECT id, question_text FROM viva_questions WHERE viva_answers IS NULL ORDER BY id ASC")
    questions = cursor.fetchall()
    
    if not questions:
        print("\nNo unanswered questions found in the database.")
        conn.close()
        return

    print(f"\nFound {len(questions)} unanswered questions. Starting Viva Session...")

    for q_id, question_text in questions:
        print("\n" + "="*50)
        print(f"Question ID {q_id}: {question_text}")
        print("="*50)
        
        # 1. Speak the question
        print("Speaking question aloud...")
        await speak_question(question_text)
        
        # 2. Wait 1 second (pause buffer)
        print("Waiting 1 second before opening microphone...")
        await asyncio.sleep(1.0)
        
        # 3. Record response
        record_answer()
        
        # 4. Transcribe response
        answer_text = transcribe_answer(whisper_model)
        print(f"Final Answer Text: '{answer_text}'")
        
        # 5. Save back to the database
        cursor.execute("UPDATE viva_questions SET viva_answers = ? WHERE id = ?", (answer_text, q_id))
        conn.commit()
        print(f"Question [{q_id}] answered and saved.")
        
    conn.close()
    print("\nViva session complete!")

if __name__ == "__main__":
    asyncio.run(main())
