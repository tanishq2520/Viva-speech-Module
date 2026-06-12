import asyncio
import sqlite3
import os
import ctypes
import time
import wave
import pyaudio
import webrtcvad
import numpy as np
import soundfile as sf
import noisereduce as nr
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
    """Record microphone input with VAD control, retry on error, and apply noise reduction."""
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK_SIZE = 512  # Exact 512 chunk size requested
    
    p = pyaudio.PyAudio()
    vad = webrtcvad.Vad()
    vad.set_mode(1)  # VAD aggressiveness: 1 (less aggressive, handles soft speech/accents)
    
    stream = None
    
    def open_stream():
        return p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
    try:
        stream = open_stream()
    except Exception as e:
        print(f"Error opening microphone stream initially: {e}")
        p.terminate()
        return

    # Capture first 0.5 seconds of audio silently as noise profile
    # 0.5 seconds of audio = 8000 samples. With CHUNK_SIZE = 512, we need 16 chunks (16 * 512 = 8192 samples = 0.512s)
    print("Calibrating ambient noise (keep silent)...")
    noise_frames = []
    reconnected = False
    
    i = 0
    while i < 16:
        try:
            noise_chunk = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            noise_frames.append(noise_chunk)
            i += 1
        except (OSError, Exception) as e:
            if not reconnected:
                print(f"\nWarning: Mic connection lost during calibration ({e}). Reconnecting...")
                reconnected = True
                try:
                    if stream:
                        stream.stop_stream()
                        stream.close()
                except:
                    pass
                time.sleep(1.0)
                try:
                    stream = open_stream()
                    print("Mic reconnected")
                    noise_frames = []
                    i = 0  # Restart calibration
                except Exception as re_err:
                    print(f"Failed to reconnect mic: {re_err}")
                    break
            else:
                print(f"Error: Mic failed again after reconnect: {e}")
                break
                
    if len(noise_frames) < 16:
        print("Failed to capture noise profile. Aborting recording.")
        try:
            stream.stop_stream()
            stream.close()
        except:
            pass
        p.terminate()
        return

    print("\nRecording student answer... (Speak now)")
    
    frames = []
    start_time = time.time()
    last_speech_time = start_time
    stop_reason = ""
    is_recording_active = False
    recording_active_start_time = None
    
    # webrtcvad requires 10ms, 20ms, or 30ms frames.
    # We buffer CHUNK_SIZE (512) data and feed exactly 320 sample chunks (20ms) to VAD.
    vad_buffer = b""
    VAD_FRAME_BYTES = 320 * 2  # 320 samples * 2 bytes/sample = 640 bytes
    
    reconnected = False
    while True:
        try:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Check 30-second hard cap
            if elapsed_time >= 30.0:
                stop_reason = "max time reached"
                break
                
            # Check silence timeout
            if is_recording_active:
                # 8-second silence threshold (student has started speaking)
                if current_time - last_speech_time >= 8.0:
                    # Enforce minimum active recording duration of 2.0 seconds
                    active_duration = current_time - recording_active_start_time
                    if active_duration >= 2.0:
                        stop_reason = "silence timeout"
                        break
            else:
                # Student hasn't started speaking yet: timeout after 8s of absolute silence from loop start
                if current_time - start_time >= 8.0:
                    stop_reason = "silence timeout"
                    break
            
            # Read chunk from stream
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            
            # Only start saving audio chunks after recording is active (skips leading silence)
            if is_recording_active:
                frames.append(data)
                
            # Run VAD on chunks of 20ms (320 samples)
            vad_buffer += data
            is_speech = False
            while len(vad_buffer) >= VAD_FRAME_BYTES:
                frame = vad_buffer[:VAD_FRAME_BYTES]
                vad_buffer = vad_buffer[VAD_FRAME_BYTES:]
                if vad.is_speech(frame, RATE):
                    is_speech = True
                    
            if is_speech:
                last_speech_time = time.time()
                if not is_recording_active:
                    is_recording_active = True
                    recording_active_start_time = time.time()
                    print("\n[Recording Active - Speech Detected]")
                    # Include the chunk that triggered active recording
                    frames.append(data)
                print("*", end="", flush=True)
            else:
                print(".", end="", flush=True)
                
        except (OSError, Exception) as e:
            if not reconnected:
                print(f"\nWarning: Mic connection lost ({e}). Reconnecting...")
                reconnected = True
                try:
                    if stream:
                        stream.stop_stream()
                        stream.close()
                except:
                    pass
                time.sleep(1.0)
                try:
                    stream = open_stream()
                    print("Mic reconnected")
                    continue
                except Exception as re_err:
                    print(f"Failed to reconnect mic: {re_err}")
                    stop_reason = f"mic disconnected: {re_err}"
                    break
            else:
                print(f"\nError: Mic failed again after reconnect: {e}")
                stop_reason = f"mic error: {e}"
                break
                
    # Close audio streams
    try:
        stream.stop_stream()
        stream.close()
    except:
        pass
    p.terminate()
    print(f"\nRecording stopped. Reason: {stop_reason}")
    
    # Save raw audio as answer.wav
    try:
        wf = wave.open(TEMP_RECORD_FILE, "wb")
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames) if frames else b"\x00" * 32000)
        wf.close()
    except Exception as e:
        print(f"Error saving raw wave file: {e}")
        return
        
    # Apply Noise Reduction and Verify Sample Rate
    try:
        # Verify and read using soundfile
        audio_data, sample_rate = sf.read(TEMP_RECORD_FILE)
        
        # Verify sample rate, resample using librosa if mismatched
        if sample_rate != 16000:
            print(f"Warning: Sample rate mismatch ({sample_rate} Hz). Resampling to 16000 Hz...")
            import librosa
            audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=16000)
            sample_rate = 16000
            
        # Convert captured noise frames to float32 numpy array to match soundfile's float output
        noise_data = np.frombuffer(b"".join(noise_frames), dtype=np.int16).astype(np.float32) / 32768.0
        
        # Perform noise reduction
        clean_audio = nr.reduce_noise(y=audio_data, sr=sample_rate, y_noise=noise_data)
        
        # Write clean audio back to TEMP_RECORD_FILE
        sf.write(TEMP_RECORD_FILE, clean_audio, sample_rate)
        print(f"Ambient noise reduction applied successfully. Saved to {TEMP_RECORD_FILE}")
    except Exception as e:
        print(f"Warning: Error during noise reduction or resampling: {e}")

def transcribe_answer(model):
    """Transcribe answer.wav using preloaded model with language and confidence filters."""
    if not os.path.exists(TEMP_RECORD_FILE):
        print(f"Error: {TEMP_RECORD_FILE} not found.")
        return ""
        
    print("Transcribing recorded answer...")
    
    # Transcribe: small model, en language, no condition on previous text to prevent chaining hallucinations
    segments, info = model.transcribe(
        TEMP_RECORD_FILE,
        beam_size=5,
        language="en",
        condition_on_previous_text=False
    )
    
    text_segments = []
    for segment in segments:
        # Confidence filter: skip or tag segments with avg_logprob below -1.0
        if segment.avg_logprob < -1.0:
            print(f"Skipping unreliable segment (logprob: {segment.avg_logprob:.2f}): '{segment.text}' -> replaced with [unclear]")
            text_segments.append("[unclear]")
        else:
            text_segments.append(segment.text)
            
    transcribed_text = " ".join(text_segments).strip()
    
    # Clean up temporary recording file
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

    # Download the faster-whisper small model with progress bar indicator
    print("Checking and downloading faster-whisper small model from Hugging Face...")
    from huggingface_hub import snapshot_download
    model_dir = snapshot_download(repo_id="Systran/faster-whisper-small")
    
    # Load model from local cache directory
    print("Loading faster-whisper model (small size, CPU, int8) into memory...")
    whisper_model = WhisperModel(model_dir, device="cpu", compute_type="int8")
    print("Model loaded successfully.")

    # Connect to database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Fetch unanswered questions
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
        
        # 2. Wait 2 seconds (buffer pause)
        print("Waiting 2 seconds before opening microphone...")
        await asyncio.sleep(2.0)
        
        # 3. Record response (captures 0.5s ambient noise, then starts recording on voice)
        record_answer()
        
        # 4. Transcribe response
        answer_text = transcribe_answer(whisper_model)
        
        # 5. Format check: Save "[No response]" if empty or whitespace
        if not answer_text or not answer_text.strip():
            answer_text = "[No response]"
            
        print(f"Final Answer Text: '{answer_text}'")
        
        # 6. Save back to the database
        cursor.execute("UPDATE viva_questions SET viva_answers = ? WHERE id = ?", (answer_text, q_id))
        conn.commit()
        print(f"Question [{q_id}] answered and saved.")
        
    conn.close()
    print("\nViva session complete!")

if __name__ == "__main__":
    asyncio.run(main())
