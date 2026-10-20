from flask import Flask, render_template, request, redirect, url_for, flash, Response
import sqlite3, csv, io, os, base64, datetime, json, shutil
from pathlib import Path

try:
    import cv2
    import numpy as np
    CV_AVAILABLE = hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create")
except Exception:
    cv2, np, CV_AVAILABLE = None, None, False

app = Flask(__name__)
app.secret_key = os.environ.get("CLASSPULSE_SECRET", "change-this-development-secret")
ROOT = Path(__file__).resolve().parent
DB = ROOT / "attendance.db"
FACES = ROOT / "data" / "faces"
FACES.mkdir(parents=True, exist_ok=True)
CASCADE_PATH = None
if cv2:
    try:
        CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    except Exception:
        pass

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS students(
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_code TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL, email TEXT DEFAULT '', face_consent INTEGER DEFAULT 0,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attendance(
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
          date TEXT NOT NULL, time TEXT NOT NULL, status TEXT NOT NULL,
          source TEXT NOT NULL, note TEXT DEFAULT '',
          UNIQUE(student_id,date));
        CREATE TABLE IF NOT EXISTS engagement(
          id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL,
          date TEXT NOT NULL, participation INTEGER DEFAULT 0, quiz_score INTEGER DEFAULT 0,
          polls INTEGER DEFAULT 0, note TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, happened_at TEXT NOT NULL,
          action TEXT NOT NULL, detail TEXT NOT NULL);
        """)
        count = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if count == 0:
            now = datetime.datetime.now().isoformat(timespec="seconds")
            demo = [
                ("STU001","Aarav Sharma","aarav@example.com"),
                ("STU002","Diya Patel","diya@example.com"),
                ("STU003","Kabir Verma","kabir@example.com"),
                ("STU004","Meera Singh","meera@example.com"),
            ]
            con.executemany("INSERT INTO students(student_code,name,email,created_at) VALUES(?,?,?,?)",
                            [(c,n,e,now) for c,n,e in demo])

def audit(action, detail):
    with db() as con:
        con.execute("INSERT INTO audit(happened_at,action,detail) VALUES(?,?,?)",
                    (datetime.datetime.now().isoformat(timespec="seconds"), action, detail))

def today():
    return datetime.date.today().isoformat()

def student_by_id(sid):
    with db() as con:
        return con.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()

def mark_attendance(student_id, source, note=""):
    s = student_by_id(student_id)
    if not s:
        return False, "Student not found."
    now = datetime.datetime.now()
    with db() as con:
        con.execute("""INSERT INTO attendance(student_id,date,time,status,source,note)
        VALUES(?,?,?,?,?,?) ON CONFLICT(student_id,date) DO UPDATE SET
        time=excluded.time,status='Present',source=excluded.source,note=excluded.note""",
        (student_id, now.date().isoformat(), now.strftime("%H:%M:%S"), "Present", source, note))
    audit("attendance_marked", f"{s['student_code']} marked Present via {source}")
    return True, f"Attendance marked Present for {s['name']}."

def decode_image(data_url):
    if not cv2:
        return None
    try:
        raw = data_url.split(",", 1)[1] if "," in data_url else data_url
        arr = np.frombuffer(base64.b64decode(raw), dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None

def face_crop(image):
    if not cv2 or not CASCADE_PATH or image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detector = cv2.CascadeClassifier(CASCADE_PATH)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(70,70))
    if len(faces) != 1:
        return None
    x,y,w,h = faces[0]
    crop = gray[y:y+h, x:x+w]
    return cv2.resize(crop, (200,200))

def get_recognizer():
    if not CV_AVAILABLE:
        return None, "OpenCV face module is unavailable. Install requirements.txt with opencv-contrib-python."
    samples, labels, id_to_student = [], [], {}
    label = 0
    for folder in FACES.iterdir():
        if not folder.is_dir():
            continue
        try: sid = int(folder.name)
        except ValueError: continue
        s = student_by_id(sid)
        if not s or not s["face_consent"]: continue
        images = list(folder.glob("*.png"))
        if not images: continue
        id_to_student[label] = sid
        for path in images:
            im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if im is not None:
                samples.append(cv2.resize(im, (200,200)))
                labels.append(label)
        label += 1
    if not samples:
        return None, "No consented face samples enrolled yet."
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(samples, np.array(labels, dtype=np.int32))
    return (recognizer, id_to_student), None

@app.route("/")
def dashboard():
    date = request.args.get("date", today())
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        present = con.execute("SELECT COUNT(*) FROM attendance WHERE date=? AND status='Present'", (date,)).fetchone()[0]
        rows = con.execute("""SELECT s.*, a.status, a.time, a.source FROM students s
          LEFT JOIN attendance a ON a.student_id=s.id AND a.date=? ORDER BY s.name""", (date,)).fetchall()
        recent = con.execute("SELECT happened_at,action,detail FROM audit ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("dashboard.html", date=date, total=total, present=present,
                           absent=max(total-present,0), rows=rows, recent=recent,
                           rate=round(present*100/total) if total else 0)

@app.route("/students", methods=["GET","POST"])
def students():
    if request.method == "POST":
        code = request.form.get("student_code","").strip().upper()
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip()
        if not code or not name:
            flash("Student code and name are required.", "error")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO students(student_code,name,email,created_at) VALUES(?,?,?,?)",
                                (code,name,email,datetime.datetime.now().isoformat(timespec="seconds")))
                audit("student_added", f"{code} — {name}")
                flash("Student added successfully.", "success")
            except sqlite3.IntegrityError:
                flash("That student code already exists.", "error")
        return redirect(url_for("students"))
    with db() as con:
        rows = con.execute("SELECT s.*, (SELECT COUNT(*) FROM attendance a WHERE a.student_id=s.id AND a.status='Present') AS days_present FROM students s ORDER BY name").fetchall()
    return render_template("students.html", students=rows, cv_available=CV_AVAILABLE)

@app.post("/students/<int:sid>/delete")
def delete_student(sid):
    s = student_by_id(sid)
    if s:
        with db() as con:
            con.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
            con.execute("DELETE FROM engagement WHERE student_id=?", (sid,))
            con.execute("DELETE FROM students WHERE id=?", (sid,))
        shutil.rmtree(FACES / str(sid), ignore_errors=True)
        audit("student_deleted", f"{s['student_code']} — {s['name']}")
        flash("Student and their local face samples deleted.", "success")
    return redirect(url_for("students"))

@app.post("/students/<int:sid>/consent")
def consent(sid):
    enabled = 1 if request.form.get("face_consent") == "yes" else 0
    with db() as con:
        con.execute("UPDATE students SET face_consent=? WHERE id=?", (enabled,sid))
    if not enabled:
        shutil.rmtree(FACES / str(sid), ignore_errors=True)
    audit("face_consent_changed", f"student_id={sid}, consent={bool(enabled)}")
    flash("Face consent updated. Turning consent off also deletes enrolled face samples.", "success")
    return redirect(url_for("students"))

@app.post("/face/enroll/<int:sid>")
def face_enroll(sid):
    s = student_by_id(sid)
    if not s:
        return {"ok":False,"message":"Student not found."}, 404
    if not s["face_consent"]:
        return {"ok":False,"message":"Enable explicit face consent on the Students page first."}, 400
    if not CV_AVAILABLE:
        return {"ok":False,"message":"Face module unavailable. Install requirements.txt."}, 400
    payload = request.get_json(silent=True) or {}
    image = decode_image(payload.get("image",""))
    crop = face_crop(image)
    if crop is None:
        return {"ok":False,"message":"Exactly one clear face was not detected. Improve lighting and try again."}, 400
    folder = FACES / str(sid)
    folder.mkdir(parents=True, exist_ok=True)
    filename = folder / f"sample_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    cv2.imwrite(str(filename), crop)
    audit("face_sample_enrolled", f"{s['student_code']} — local sample saved")
    return {"ok":True,"message":"Face sample saved locally. Capture 3–5 samples with slightly different angles/light."}

@app.route("/attendance", methods=["GET","POST"])
def attendance():
    date = request.values.get("date", today())
    if request.method == "POST":
        sid = request.form.get("student_id", type=int)
        action = request.form.get("action","Present")
        if sid and action in ("Present","Absent","Unverified"):
            s = student_by_id(sid)
            if s:
                now = datetime.datetime.now()
                with db() as con:
                    con.execute("""INSERT INTO attendance(student_id,date,time,status,source,note) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(student_id,date) DO UPDATE SET time=excluded.time,status=excluded.status,source=excluded.source,note=excluded.note""",
                    (sid,date,now.strftime("%H:%M:%S"),action,request.form.get("source","manual"),request.form.get("note","")))
                audit("attendance_updated", f"{s['student_code']} set to {action} via {request.form.get('source','manual')}")
                flash(f"{s['name']}: {action}", "success")
        return redirect(url_for("attendance", date=date))
    with db() as con:
        rows = con.execute("""SELECT s.id,s.student_code,s.name,a.status,a.time,a.source,a.note
        FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.date=?
        ORDER BY s.name""",(date,)).fetchall()
        roster = con.execute("SELECT id,student_code,name,face_consent FROM students ORDER BY name").fetchall()
    return render_template("attendance.html", date=date, rows=rows, students=roster,
                           cv_available=CV_AVAILABLE)

@app.post("/face/recognize")
def face_recognize():
    if not CV_AVAILABLE:
        return {"ok":False,"message":"Face module unavailable. Install requirements.txt."}, 400
    payload = request.get_json(silent=True) or {}
    crop = face_crop(decode_image(payload.get("image","")))
    if crop is None:
        return {"ok":False,"message":"Exactly one clear face was not detected."}, 400
    model, err = get_recognizer()
    if err:
        return {"ok":False,"message":err}, 400
    recognizer, labels = model
    label, confidence = recognizer.predict(crop)
    # LBPH lower confidence is a closer match. Threshold is a conservative starting point, not a guarantee.
    if confidence > 65 or label not in labels:
        return {"ok":False,"message":f"No confident match (distance {confidence:.1f}). Use manual attendance."}, 200
    sid = labels[label]
    s = student_by_id(sid)
    if not s:
        return {"ok":False,"message":"Matched record no longer exists."}, 400
    return {"ok":True,"student_id":sid,"student_code":s["student_code"],"name":s["name"],
            "confidence_distance":round(float(confidence),1),
            "message":"Suggested match only. Verify the student's identity and confirm before marking attendance."}

@app.post("/attendance/confirm-face")
def confirm_face():
    sid = request.form.get("student_id", type=int)
    if not request.form.get("confirmed"):
        flash("Please confirm the student's identity before marking attendance.", "error")
    elif sid:
        ok, msg = mark_attendance(sid, "face-assisted", "Teacher confirmed suggested match")
        flash(msg, "success" if ok else "error")
    return redirect(url_for("attendance"))

@app.route("/engagement", methods=["GET","POST"])
def engagement():
    date = request.values.get("date", today())
    if request.method == "POST":
        sid = request.form.get("student_id", type=int)
        participation = max(0,min(100,request.form.get("participation",0,type=int)))
        quiz = max(0,min(100,request.form.get("quiz_score",0,type=int)))
        polls = max(0,min(100,request.form.get("polls",0,type=int)))
        note = request.form.get("note","").strip()
        if sid and student_by_id(sid):
            with db() as con:
                con.execute("INSERT INTO engagement(student_id,date,participation,quiz_score,polls,note) VALUES(?,?,?,?,?,?)",
                            (sid,date,participation,quiz,polls,note))
            audit("engagement_recorded", f"student_id={sid}, date={date}")
            flash("Activity data saved.", "success")
        return redirect(url_for("engagement",date=date))
    with db() as con:
        roster = con.execute("SELECT id,student_code,name FROM students ORDER BY name").fetchall()
        rows = con.execute("""SELECT s.student_code,s.name,e.participation,e.quiz_score,e.polls,e.note,
        ROUND((e.participation+e.quiz_score+e.polls)/3.0) AS activity_score
        FROM engagement e JOIN students s ON s.id=e.student_id WHERE e.date=?
        ORDER BY activity_score DESC""",(date,)).fetchall()
    return render_template("engagement.html", date=date, students=roster, rows=rows)

@app.get("/reports.csv")
def reports():
    date = request.args.get("date",today())
    with db() as con:
        rows = con.execute("""SELECT s.student_code,s.name,s.email,COALESCE(a.status,'Unmarked') status,
        COALESCE(a.time,'') time,COALESCE(a.source,'') source,
        COALESCE(e.participation,'') participation,COALESCE(e.quiz_score,'') quiz_score,COALESCE(e.polls,'') polls
        FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.date=?
        LEFT JOIN engagement e ON e.student_id=s.id AND e.date=? ORDER BY s.name""",(date,date)).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student Code","Name","Email","Attendance","Time","Source","Participation","Quiz Score","Polls"])
    writer.writerows([tuple(r) for r in rows])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":f"attachment; filename=classpulse_{date}.csv"})

@app.get("/about")
def about():
    return render_template("about.html", cv_available=CV_AVAILABLE)

@app.get("/health")
def health():
    return {"app":"ClassPulse AI","status":"ok","face_module_available":CV_AVAILABLE,
            "speech_mode":"browser Web Speech API","database":"SQLite"}

init_db()
if __name__ == "__main__":
    app.run(debug=True)
