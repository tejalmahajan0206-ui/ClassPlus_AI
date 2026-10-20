# ClassPulse AI — Multimodal Attendance & Engagement Agent

A beginner-friendly Flask + SQLite educational prototype with roster management, daily attendance, opt-in face-assisted matching, browser-based voice-assisted lookup, activity analytics, audit trail, and CSV export.

## Important reality check
- **Face module:** OpenCV Haar detection + LBPH matching against locally enrolled, consented face samples. The result is only a *suggestion*. A teacher must confirm the identity before attendance is marked. Recognition can be wrong.
- **Audio module:** Browser Web Speech API transcribes a spoken student name/code. The app does not upload or save audio. Browser support and speech-service availability vary.
- **Engagement analytics:** Uses manually entered participation, quiz score, and poll values. It does not infer emotion, attention, or learning from camera/microphone.
- This is a **local demo**, not a secure production system. It has no login/roles, no liveness detection, no encrypted face storage, and no robust anti-spoofing. Do not expose it to the public internet.

## Requirements
- Python 3.10+
- Windows 10/11 or macOS/Linux
- Webcam for face functions
- Recent Chrome/Edge is recommended for browser speech recognition

## Run on Windows (PowerShell)
Open the extracted `ClassPulse_AI` folder in VS Code, then Terminal → New Terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

If PowerShell blocks activation, use this temporary terminal-only command:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```
If you already created `.venv`, do not recreate it; activate it and continue with pip install.

## Features
1. Dashboard with date filter, present count, rate and audit activity
2. Add/delete students and student-code uniqueness validation
3. Manual attendance statuses: Present / Absent / Unverified
4. Face consent toggle, local sample enrollment, face-assisted suggested matching, teacher confirmation
5. Voice-assisted student lookup via browser Web Speech API, teacher confirmation
6. Activity data entry: participation, quiz score, polls; transparent average score
7. CSV report export including attendance and activity values
8. Health endpoint: `/health`
9. Privacy and limitations page

## Suggested demo flow
1. Open Students, add a test student.
2. Enable face consent for that student and enroll 3–5 samples.
3. Open Attendance, start camera and try a face match; confirm only if the identity is correct.
4. Try voice lookup in Chrome/Edge. Review the transcript before selecting the student.
5. Mark another student manually to demonstrate fallback.
6. Add activity data under Engagement and export the CSV.

## Project workflow / EPIC mapping
- **EPIC 1 — Requirements & setup:** Python environment, dependencies, SQLite schema, health endpoint.
- **EPIC 2 — Vision module:** face consent, enrollment, detection, LBPH match suggestion, manual confirmation.
- **EPIC 3 — Audio module:** browser speech-to-text, transcript review, roster lookup and confirmation.
- **EPIC 4 — AI implementation:** CV-based face matching plus speech-assisted input; these are practical prototype modules, not a large multimodal neural network.
- **EPIC 5 — Analytics:** activity score, attendance rate, audit events, date-filtered CSV report.
- **EPIC 6 — Interface/testing:** responsive UI, error messages, manual fallback, privacy notes, local deployment instructions.

## Data and privacy
- SQLite file: `attendance.db` (created automatically)
- Face samples: `data/faces/<student_id>/` (local cropped images)
- Disable face consent to delete that student's samples; deleting the student also deletes their samples.
- To reset all demo data, stop the app and delete `attendance.db` and the contents of `data/faces/`. This resets records; do this only if you no longer need them.
- Obtain informed consent before collecting face samples. Follow your institution's policies and applicable laws.

## Known limitations / next steps
- Add authentication and teacher/admin roles before real use.
- Add tests, audit export, database migrations, secure configuration and deployment hardening.
- Evaluate recognition accuracy fairly across lighting, pose, camera quality and user groups; tune thresholds with documented test data.
- Add liveness/anti-spoofing only with a clear privacy review and appropriate evaluation.
- Voice support varies by browser; manual entry remains available.


## 🎥 Project Demo Video

Watch the ClassPulse AI project demo video here:

https://drive.google.com/file/d/1fmhxIRG0SH9xrbqUNadOSP1wsVFANyF2/view?usp=drive_link
