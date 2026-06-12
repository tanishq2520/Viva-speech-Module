from faster_whisper import WhisperModel
import os

def transcribe_answer():
    wav_filename = "answer.wav"
    if not os.path.exists(wav_filename):
        print(f"Error: {wav_filename} not found. Please record an answer first.")
        return ""
        
    print(f"Loading '{wav_filename}' and initializing faster-whisper ('base' model on CPU with int8)...")
    
    # Initialize the Whisper model
    # Model size: 'base', device: 'cpu', compute_type: 'int8'
    model = WhisperModel("base", device="cpu", compute_type="int8")
    
    # Transcribe the audio
    # beam_size=5 is standard for good accuracy
    segments, info = model.transcribe(wav_filename, beam_size=5)
    
    print(f"Detected language: {info.language} with probability {info.language_probability:.2f}")
    
    # Collect transcription segments
    text_segments = []
    for segment in segments:
        text_segments.append(segment.text)
        
    # Join and clean up text
    full_text = " ".join(text_segments).strip()
    
    print("\n--- Transcription Result ---")
    print(full_text)
    print("----------------------------")
    
    return full_text

if __name__ == "__main__":
    transcribe_answer()
