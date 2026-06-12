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
* Waits for 1 second to avoid capturing the system's own speakers.
* Captures real-time microphone input.
* Checks each 20ms chunk for speech vs. background noise.
* Stops recording automatically if the student is silent for 5 seconds OR if they reach a hard cap of 30 seconds.
* Transcribes the audio into plain text.
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
  |              1-Second Guard Pause Buffer              |
  |     - Ensures mic doesn't record system voice         |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |            Microphone Capture (pyaudio)               |
  |     - Opens mic stream (16kHz, mono, 320 chunk)       |
  +                           |                           |
                              v
  +-------------------------------------------------------+
  |          Voice Activity Detection (webrtcvad)         |
  |     - Monitors active speech vs. silence              |
  |     - Silence > 5s OR total time > 30s -> Stop        |
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
   * **Do not modify VAD timing buffers**: `CHUNK_SIZE = 320` is specifically chosen for a sample rate of `16000` to yield exactly `20ms` frames. Changing this will cause `webrtcvad` to throw validation errors.

---

## ⏱️ Timer Logic

* **1-Second Guard Pause**:
  * *Why*: When the computer finishes speaking the question, the microphone needs a buffer pause. If recording starts immediately, it will catch the echo of the system speaker reading the last syllable.
  * *Where*: Regulated in `viva_speech.py` using `await asyncio.sleep(1.0)`.
* **5-Second Silence Auto-Submit**:
  * *How*: We initialize `last_speech_time` to the recording start time. The microphone reads 20ms frames. If `webrtcvad` marks a frame as speech, we update `last_speech_time = time.time()`. If `time.time() - last_speech_time >= 5.0`, the loop breaks.
  * *Result*: If the student stops speaking for 5 seconds (or doesn't speak at all at the start), the recording immediately ends and submits.
* **30-Second Hard Cap**:
  * *How*: Tracks `elapsed_time = time.time() - start_time`. If `elapsed_time >= 30.0`, the loop breaks immediately, saving whatever speech was recorded up to that second.

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

These SQL queries are available inside `manage_db.py` but can also be executed in any SQLite viewer:

### View All Questions and Answers
```sql
SELECT id, question_text, viva_answers FROM viva_questions;
```

### Reset All Answers
```sql
UPDATE viva_questions SET viva_answers = NULL;
```

### Add a Question
```sql
INSERT INTO viva_questions (question_text) 
VALUES ('What is the purpose of an index in a database?');
```

### Delete a Specific Question
```sql
DELETE FROM viva_questions WHERE id = 5;
```

### Wipe and Recreate Table
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
