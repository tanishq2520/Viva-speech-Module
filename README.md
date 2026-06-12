# 🎙️ AI Viva System — Speech Pipeline Module

This is the **Speech Pipeline Module** for the AI Viva System. It handles all auditory interactions with the student, including fetching questions, speaking them aloud, recording voice responses under intelligent silence/time caps, transcribing those responses, and saving them back to the database.

> [!NOTE]  
> **Handover Notice**: This module **does not** perform scoring, grading, or validation. The teammate in charge of the scoring/grading module should read the final transcriptions from this database module to run their evaluation.

---

## 🚀 Quick Start in 3 Steps

If you want to spin up and test the system immediately, follow these three commands:

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the Database:**
   ```bash
   python setup_db.py
   ```

3. **Start the Viva Session:**
   ```bash
   python viva_speech.py
   ```

---

## 📋 Table of Contents
1. [📖 Project Overview](#-project-overview)
2. [🛠️ Tech Stack with Reasons](#️-tech-stack-with-reasons)
3. [🗄️ Database Schema](#️-database-schema)
4. [📊 Variable Map](#-variable-map)
5. [📁 File Structure](#-file-structure)
6. [⚙️ How to Run](#️-how-to-run)
7. [🤝 How to Connect Your Module to Mine](#-how-to-connect-your-module-to-mine)
8. [⏱️ Timer Logic](#️-timer-logic)
9. [❌ Common Errors and Fixes](#-common-errors-and-fixes)
10. [🔧 Reset and Utility Commands](#-reset-and-utility-commands)
11. [✍️ Contact / Handover Notes](#️-contact--handover-notes)

---

## 📖 Project Overview

This module automates the speech-based testing loop of a viva session. 

### What It Does:
* Reads a question from the SQLite database.
* Converts the text of that question into high-quality spoken audio and plays it aloud.
* Waits for 2 seconds to avoid capturing the system's own speakers.
* Captures 0.5s of ambient noise as a noise profile.
* Captures real-time microphone input.
* Checks each chunk for speech vs. background noise (VAD mode 1).
* Stops recording automatically if the student is silent for 8 seconds OR if they reach a hard cap of 30 seconds.
* Cleans the recording using the ambient noise profile.
* Transcribes the audio into plain text (Whisper small model, English-only).
* Saves the text back to the database row for that question.

### What It Does NOT Do:
* **Scoring / Grading**: It does not evaluate the correctness of the answer.
* **Validation**: It does not check if the answer is off-topic or gibberish.

### Pipeline Flow Diagram:

```text
  +-------------------------------------------------------+
  |                   SQLite (viva.db)                    |
  |     - Reads question_text where answer is NULL        |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |              Text-To-Speech (edge-tts)                |
  |     - Speaks question out loud (Windows MCI)          |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |              2-Second Guard Pause Buffer              |
  |     - Ensures mic doesn't record system voice         |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |            Microphone Capture (pyaudio)               |
  |     - Opens mic stream (16kHz, mono, 512 chunk)       |
  |     - Captures 0.5s ambient noise first               |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |          Voice Activity Detection (webrtcvad)         |
  |     - Monitors active speech vs. silence (mode 1)     |
  |     - Silence > 8s OR total time > 30s -> Stop        |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |               Noise Reduction (noisereduce)           |
  |     - Cleans answer.wav using noise profile           |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |             Transcription (faster-whisper)            |
  |     - Converts recorded answer.wav to plain text      |
  |     - Uses 'small' model, en-only, logprob filter     |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |             Transcription (faster-whisper)            |
  |     - Converts recorded answer.wav to plain text      |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |                   SQLite (viva.db)                    |
  |     - UPDATE row's viva_answers with transcript       |
  +-------------------------------------------------------+
```

---

## 🛠️ Tech Stack with Reasons

We selected these packages to maintain a high-quality user experience without needing external software (like C compilers or system-level audio decoders) on Windows:

| Library | Role in Project | Why Chosen Over Alternatives |
| :--- | :--- | :--- |
| **`sqlite3`** | Local relational database storage. | Standard Python library requiring zero installation, server config, or external credentials. |
| **`edge-tts`** | Text-to-Speech (TTS) synthesis. | Connects to Edge's high-quality neural voice service. Sounds much more human than offline alternatives like `pyttsx3`. |
| **`pyaudio`** | Capture microphone audio stream. | Industry-standard Python wrapper around PortAudio, providing reliable low-level control of raw audio input. |
| **`webrtcvad`** | Voice Activity Detection (VAD). | Built by Google for WebRTC. Extremely fast, lightweight, runs locally, and handles noise filtering better than simple amplitude thresholding. (Installed via `webrtcvad-wheels` for precompiled Windows binaries). |
| **`faster-whisper`** | Speech-to-Text (STT) transcription. | Re-implementation of OpenAI's Whisper using CTranslate2. Up to 4x faster than original Whisper with lower memory footprint; runs locally on CPU using `int8` precision. |
| **`noisereduce`** | Background noise reduction. | Cleans ambient/background noise using a spectral gating algorithm. Runs locally and improves transcription accuracy. |
| **`soundfile`** | Wave file reading/writing. | Flexible audio loader that handles metadata and raw data conversion seamlessly for python numpy structures. |
| **`librosa`** | Audio processing (resampling). | Standard python library for music and audio analysis. Provides robust resampling algorithms to match sample rates. |

---

## 🗄️ Database Schema

### Database File
* **File Name**: `viva.db`
* **Location**: Root directory of the project

### Table Name
* `viva_questions`

### Column Descriptions
| Column Name | Data Type | Purpose | Nullable? | Role |
| :--- | :--- | :--- | :--- | :--- |
| **`id`** | `INTEGER` | Primary key (autoincrements) | No | Identifies the question. |
| **`question_text`** | `TEXT` | The actual viva question to ask | No | **Input** (Read by my module). |
| **`viva_answers`** | `TEXT` | Transcribed student answer | Yes | **Output** (Filled by my module). |

### Table Creation SQL
```sql
CREATE TABLE IF NOT EXISTS viva_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    viva_answers TEXT DEFAULT NULL
);
```

### Insert Sample Question SQL
```sql
INSERT INTO viva_questions (question_text) 
VALUES ('Explain the difference between a process and a thread.');
```

### Verification SQL
```sql
SELECT id, question_text, viva_answers FROM viva_questions;
```

### Reset Answers SQL
```sql
UPDATE viva_questions SET viva_answers = NULL;
```

### Add New Question SQL
```sql
INSERT INTO viva_questions (question_text) VALUES ('What is virtual memory?');
```

---

## 📊 Variable Map

Here are the critical variables carrying data through our pipeline:

| Variable | Type | Holds | Source | Passes To |
| :--- | :--- | :--- | :--- | :--- |
| `questions` | `list[tuple]` | List of row tuples `(id, question_text)` | SQLite fetch query | Loop iterator |
| `question_text` | `str` | Text of the current question | `questions` list unpack | `edge_tts.Communicate` |
| `data` | `bytes` | Raw 16-bit PCM audio chunk (640 bytes) | `stream.read(CHUNK_SIZE)` | VAD checker and `frames` list |
| `frames` | `list[bytes]` | Buffer holding all recorded audio chunks | Append inside recording loop | `wave.writeframes` |
| `start_time` | `float` | Epoch timestamp of recording start | `time.time()` | Elapsed time checker |
| `last_speech_time`| `float` | Epoch timestamp of last speech detection | `time.time()` | Silence timeout checker |
| `answer_text` | `str` | Final plain text transcription | `transcribe_answer()` | SQLite update statement |

---

## 📁 File Structure

* **[requirements.txt](file:///d:/Project/SN_Bose%20Viva%20system/requirements.txt)**: Python package dependencies with locked versions.
* **[setup_db.py](file:///d:/Project/SN_Bose%20Viva%20system/setup_db.py)**: Database initializer. Creates `viva.db` and populates 5 Computer Science questions.
* **[viva_speech.py](file:///d:/Project/SN_Bose%20Viva%20system/viva_speech.py)**: **The main application script**. Loops through questions, manages TTS playback, triggers VAD recording, transcribes, and updates the database.
* **[manage_db.py](file:///d:/Project/SN_Bose%20Viva%20system/manage_db.py)**: Database utility script to view, reset, and manually append new questions.
* **[speak_question.py](file:///d:/Project/SN_Bose%20Viva%20system/speak_question.py)**: Independent utility to test the edge-tts engine.
* **[record_answer.py](file:///d:/Project/SN_Bose%20Viva%20system/record_answer.py)**: Independent utility to test microphone capture and VAD limits.
* **[transcribe_answer.py](file:///d:/Project/SN_Bose%20Viva%20system/transcribe_answer.py)**: Independent utility to test audio file transcription via faster-whisper.

---

## ⚙️ How to Run

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```
*Expected Output:*
```text
Collecting edge-tts==7.2.8 ...
Collecting pyaudio==0.2.14 ...
Collecting webrtcvad-wheels==2.0.14 ...
Collecting faster-whisper==1.2.1 ...
Successfully installed aiohttp-3.14.1 edge-tts-7.2.8 webrtcvad-wheels-2.0.14 pyaudio-0.2.14 faster-whisper-1.2.1 ...
```

### Step 2: Initialize Database
```bash
python setup_db.py
```
*Expected Output:*
```text
Database and table 'viva_questions' created successfully.
Inserted 5 dummy computer science questions.

--- Verifying database contents ---
ID: 1
Question: Explain the difference between a process and a thread.
Answer: None
...
```

### Step 3: Run the Main Pipeline
```bash
python viva_speech.py
```
*Expected Output:*
```text
Loading faster-whisper model (base size, CPU, int8)...
Model loaded successfully.

Found 5 unanswered questions. Starting Viva Session...

==================================================
Question ID 1: Explain the difference between a process and a thread.
==================================================
Speaking question aloud...
Waiting 1 second before opening microphone...

Recording student answer... (Speak now)
..****..................*******......*****..*****...................................
Recording stopped. Reason: silence timeout
Audio recorded successfully (4.80 seconds)
Transcribing recorded answer...
Final Answer Text: 'and the thread is lighter version of it.'
Question [1] answered and saved.

==================================================
Question ID 2: What is virtual memory and how does it work?
==================================================
...
```

---

## 🤝 How to Connect Your Module to Mine

If you are developing the scoring, grading, or validation module, follow these rules:

1. **Where to read from**: 
   * Connect to the same SQLite database (`viva.db`).
   * Fetch the transcribed text from the `viva_answers` column of the `viva_questions` table.
   ```python
   # Example connection code
   import sqlite3
   conn = sqlite3.connect("viva.db")
   cursor = conn.cursor()
   cursor.execute("SELECT id, question_text, viva_answers FROM viva_questions")
   results = cursor.fetchall()
   ```
2. **Answer Format**: 
   * The transcription is returned as a **plain, lowercase/sentence-case Python string** (`str`).
   * If the user remained silent or no speech was transcribed, it will be saved as an empty string (`''`).
3. **Where to hook in your scoring logic**:
   * Open `viva_speech.py`.
   * Find the main loop around line 195:
     ```python
     # 4. Transcribe response
     answer_text = transcribe_answer(whisper_model)
     print(f"Final Answer Text: '{answer_text}'")
     
     # ---> INSERT YOUR SCORING LOGIC HERE <---
     # e.g., score = evaluate_answer(question_text, answer_text)
     # cursor.execute("UPDATE viva_questions SET score = ? WHERE id = ?", (score, q_id))
     
     # 5. Save back to the database
     cursor.execute("UPDATE viva_questions SET viva_answers = ? WHERE id = ?", (answer_text, q_id))
     ```
4. **What NOT to touch**:
   * **Do not edit `play_mp3_windows()`**: It uses low-level Windows DLL functions. Changing directories or handles will crash playback.
   * **Do not modify VAD timing buffers**: `CHUNK_SIZE = 512` is requested for PyAudio recording. However, since `webrtcvad` only accepts 10ms, 20ms, or 30ms frames, our script implements an internal `vad_buffer` that extracts exactly `320` samples (20ms frames) for VAD. Altering these rates will cause VAD initialization or classification failures.

---

## ⏱️ Timer Logic

* **2-Second Guard Pause**:
  * *Why*: When the computer finishes speaking the question, the microphone needs a buffer pause. If recording starts immediately, it will catch the echo of the system speaker reading the last syllable.
  * *Where*: Regulated in `viva_speech.py` using `await asyncio.sleep(2.0)`.
* **8-Second Silence Auto-Submit**:
  * *How*: We initialize `last_speech_time` to the recording start time. The microphone reads 512-sample chunks. If `webrtcvad` marks a sub-frame as speech, we update `last_speech_time = time.time()`. If `time.time() - last_speech_time >= 8.0`, the loop breaks.
  * *Result*: If the student stops speaking for 8 seconds (or doesn't speak at all at the start), the recording ends and submits.
* **30-Second Hard Cap**:
  * *How*: Tracks `elapsed_time = time.time() - start_time`. If `elapsed_time >= 30.0`, the loop breaks immediately, saving whatever speech was recorded up to that second.
* **2-Second Minimum Active Recording**:
  * *Why*: Prevents accidental immediate submission from a brief noise spike right after recording starts.
  * *How*: Even if silence is detected (elapsed since last speech >= 8.0s), the loop will continue recording unless the active speaking time (time since the first speech frame was detected) is at least `2.0` seconds. Note: If the student never starts speaking, the absolute silence timeout (8.0s from session start) takes priority to prevent getting stuck.
* **is_recording_active (Skip Leading Silence)**:
  * *Why*: Silence at the very beginning of the recording (before the student starts talking) is skipped, so the recorded WAV file only contains the student's actual answer. We only start appending chunks to `frames` after the first speech frame is detected.

---

## ❌ Common Errors and Fixes

### 1. Microphone Not Detected / Device Error
* **Error**: `OSError: [Errno -9996] Invalid input device`
* **Fix**: Ensure your microphone is plugged in, active in Windows sound settings, and set as the default recording device. PyAudio queries the system's default input device.

### 2. `edge-tts` Connection Failure
* **Error**: WebSocket errors or timeout.
* **Fix**: `edge-tts` requires an active internet connection to contact Microsoft's neural voice servers. Verify your network connection.

### 3. Transcription is Extremely Slow
* **Error**: Takes more than 10 seconds to transcribe a short sentence.
* **Fix**: Ensure `device="cpu"` and `compute_type="int8"` are set in the `WhisperModel` constructor. Running on CPU without int8 quantization will slow down response time dramatically.

### 4. Database is Locked
* **Error**: `sqlite3.OperationalError: database is locked`
* **Fix**: Only one process can write to the SQLite database at a time. Close any external database viewer (like DB Browser for SQLite) or running python terminals that are holding open connections.

---

## 🔧 Reset and Utility Commands

Here are the terminal commands and SQL queries you can use to manage the database.

### 🖥️ Terminal Commands

#### 1. View all questions and answers in the console:
Use the helper script to view the database table formatted directly in your terminal:
```bash
python manage_db.py view
```

#### 2. Reset all student answers back to NULL:
To clear all responses and start a fresh testing session, use this helper command:
```bash
python manage_db.py reset
```
Alternatively, you can run it as a quick python one-liner without using the helper script:
```bash
python -c "import sqlite3; conn=sqlite3.connect('viva.db'); conn.cursor().execute('UPDATE viva_questions SET viva_answers = NULL'); conn.commit(); conn.close(); print('All answers reset to NULL successfully!')"
```

#### 3. Add a new viva question:
Use the helper script to easily insert a new question into the table (make sure to wrap the question in double quotes):
```bash
python manage_db.py add "What is polymorphism in Object-Oriented Programming?"
```

---

### 🗄️ SQL Commands (For Database Viewers)
These raw SQL queries are executed by the scripts but can also be run in any external SQLite editor (like DB Browser for SQLite) connected to `viva.db`:

#### View All Questions and Answers
```sql
SELECT id, question_text, viva_answers FROM viva_questions;
```

#### Reset All Answers to NULL
```sql
UPDATE viva_questions SET viva_answers = NULL;
```

#### Add a Question
```sql
INSERT INTO viva_questions (question_text) 
VALUES ('What is the purpose of an index in a database?');
```

#### Delete a Specific Question
```sql
DELETE FROM viva_questions WHERE id = 5;
```

#### Wipe and Recreate Table
```sql
DROP TABLE IF EXISTS viva_questions;
CREATE TABLE viva_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    viva_answers TEXT DEFAULT NULL
);
```

---

## ✍️ Contact / Handover Notes

* **Module Author**: Tanishq Pal
* **Handover Date**: June 12, 2026
* **Notes**: The speech module is fully calibrated. Please hook your scoring logic directly in `viva_speech.py` where indicated or read the `viva_answers` column asynchronously. Reach out if you need assistance mapping audio channels.
