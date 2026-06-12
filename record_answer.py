import pyaudio
import webrtcvad
import time
import wave
import os

def record_answer():
    # Audio settings
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK_SIZE = 320  # 20ms frames at 16000Hz (320 samples)
    
    # Initialize PyAudio
    p = pyaudio.PyAudio()
    
    # Initialize VAD
    vad = webrtcvad.Vad()
    vad.set_mode(2)  # Aggressiveness level: 2
    
    # Open the microphone stream
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )
    
    print("Recording started. Speak into the microphone...")
    
    frames = []
    start_time = time.time()
    last_speech_time = start_time
    stop_reason = ""
    
    try:
        while True:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Check 30-second hard cap
            if elapsed_time >= 32.0:
                stop_reason = "max time reached"
                break
                
            # Check 5-second silence timeout
            if current_time - last_speech_time >= 5.0:
                stop_reason = "silence timeout"
                break
                
            # Read chunk from microphone
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            
            # Check chunk for speech
            # data should be exactly CHUNK_SIZE * 2 bytes (since 16-bit = 2 bytes per sample)
            is_speech = vad.is_speech(data, RATE)
            
            if is_speech:
                last_speech_time = time.time()
                print("🎙️", end="", flush=True)  # Visual indicator of speech
            else:
                print(".", end="", flush=True)   # Visual indicator of silence
                
            # Short sleep to prevent CPU spinning too fast (optional, but pyaudio read blocks)
            # No sleep needed because stream.read is blocking by default
            
    except KeyboardInterrupt:
        stop_reason = "manual interrupt"
        print("\nRecording stopped manually.")
        
    finally:
        print(f"\nRecording stopped. Reason: {stop_reason}")
        
        # Cleanup stream and PyAudio
        stream.stop_stream()
        stream.close()
        p.terminate()
        
    # Save the recorded audio as answer.wav
    wav_filename = "answer.wav"
    try:
        wf = wave.open(wav_filename, "wb")
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
        wf.close()
        print(f"Audio saved successfully to {wav_filename} ({len(frames) * 0.02:.2f} seconds)")
    except Exception as e:
        print(f"Error saving wave file: {e}")

if __name__ == "__main__":
    record_answer()
