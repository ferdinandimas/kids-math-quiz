from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import random
import sqlite3
import secrets
from datetime import datetime, date, timedelta

APP_TITLE = "Kids Math Quiz"
DAILY_LIMIT = 400
REWARD_PER_CORRECT = 50  # rupiah
COOKIE_NAME = "math_sess"
DB_PATH = os.getenv("DB_PATH", "math_app.sqlite3")
ADMIN_CLEAR_PASSWORD = "masukaja"

CHILDREN = ["althafandra", "alleia"]

def difficulty_from_answer(ans: int) -> str:
    if ans <= 10:
        return "easy"
    if ans <= 20:
        return "medium"
    if ans >= 50:
        return "hard"
    # range 21-49: kamu bisa anggap medium atau bikin "hard" versi ringan
    return "medium"


def make_q(qver: int, idx: int, a: int, op: str, b: int) -> dict:
    if op == "+":
        ans = a + b
        prompt = f"{a} + {b} = ?"
    elif op == "-":
        ans = a - b
        prompt = f"{a} - {b} = ?"
    else:
        raise ValueError("op must be '+' or '-'")

    return {
        "id": f"v{qver}_q{idx:04d}",
        "prompt": prompt,
        "answer": ans,
        "difficulty": difficulty_from_answer(ans),
        "op": "add" if op == "+" else "sub"
    }


def generate_bank_add_sub(
    qver: int,
    *,
    seed: int,
    target_size: int,
    single_digit_add: int,
    single_digit_sub: int,
    teen_add: int,
    teen_sub: int,
    two_digit_sub_v1: int,
    two_digit_sub_v2: int,
) -> list[dict]:
    rng = random.Random(seed)
    seen = set()
    out = []
    idx = 1

    def add_unique(a: int, op: str, b: int):
        nonlocal idx
        key = (a, op, b)
        if key in seen:
            return False

        # validasi biar anak tidak ketemu negatif
        if op == "-" and a < b:
            return False

        q = make_q(qver, idx, a, op, b)
        seen.add(key)
        out.append(q)
        idx += 1
        return True

    # helper: ambil random sampai quota terpenuhi
    def fill(quota: int, gen_fn):
        tries = 0
        while quota > 0 and tries < 200000:
            a, op, b = gen_fn()
            if add_unique(a, op, b):
                quota -= 1
            tries += 1

    # 1) single digit addition (1-9 + 1-9)
    fill(single_digit_add, lambda: (rng.randint(1, 9), "+", rng.randint(1, 9)))

    # 2) single digit subtraction (1-9 - 1-9, no negative)
    fill(single_digit_sub, lambda: (rng.randint(1, 9), "-", rng.randint(1, 9)))

    # 3) teen addition (10-20 range typical)
    # contoh: 10-20 + 0-9
    fill(teen_add, lambda: (rng.randint(10, 20), "+", rng.randint(1, 9)))

    # 4) teen subtraction (10-20 - 1-9)
    fill(teen_sub, lambda: (rng.randint(10, 20), "-", rng.randint(1, 9)))

    # 5) two digit subtraction (20-99) - (1-50), no negative
    fill(two_digit_sub_v1, lambda: (rng.randint(20, 60), "-", rng.randint(1, 20)))
    fill(two_digit_sub_v2, lambda: (rng.randint(20, 99), "-", rng.randint(1, 50)))

    # kalau masih kurang, topping random campuran
    def topping():
        mode = rng.random()
        if mode < 0.45:
            return (rng.randint(0, 9), "+", rng.randint(0, 9))
        if mode < 0.70:
            return (rng.randint(0, 9), "-", rng.randint(0, 9))
        if mode < 0.85:
            return (rng.randint(10, 20), "+", rng.randint(0, 9))
        return (rng.randint(10, 20), "-", rng.randint(0, 9))

    fill(max(0, target_size - len(out)), topping)

    # trim kalau kebanyakan
    return out[:target_size]


# V1: dominan easy, sedikit medium, hard hampir tidak muncul kecuali tens_sub
BANK_V1 = generate_bank_add_sub(
    1,
    seed=101,
    target_size=400,
    single_digit_add=50,
    single_digit_sub=50,
    teen_add=100,
    teen_sub=100,
    two_digit_sub_v1=70,
    two_digit_sub_v2=30,
)

# V2: lebih menantang, lebih banyak teen dan tens
BANK_V2 = generate_bank_add_sub(
    2,
    seed=202,
    target_size=400,
    single_digit_add=20,
    single_digit_sub=20,
    teen_add=130,
    teen_sub=130,
    two_digit_sub_v1=30,
    two_digit_sub_v2=70,
)

QUESTION_BY_ID = {q["id"]: q for q in (BANK_V1 + BANK_V2)}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def today_str():
    return date.today().isoformat()


def now_str():
    return datetime.now().isoformat(timespec="seconds")


def new_session_id():
    return secrets.token_urlsafe(24)


def init_db():
    conn = db()
    cur = conn.cursor()

    # Session per browser
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            child TEXT,
            day TEXT,
            served_count INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0,
            earned INTEGER NOT NULL DEFAULT 0,
            current_qid TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    # Rekap per anak per hari (ini yang dipakai /stats)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS child_daily (
            child TEXT NOT NULL,
            day TEXT NOT NULL,
            served_count INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0,
            earned INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (child, day)
        )
        """
    )

    conn.commit()
    conn.close()


def clear_database():
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions")
    cur.execute("DELETE FROM child_daily")
    conn.commit()
    cur.execute("VACUUM")
    conn.commit()
    conn.close()


def get_or_create_session(request: Request, response: Response) -> str:
    sess = request.cookies.get(COOKIE_NAME)
    conn = db()
    cur = conn.cursor()

    if not sess:
        sess = new_session_id()
        cur.execute(
            """
            INSERT INTO sessions(session_id, child, day, served_count, correct_count, earned, current_qid, created_at)
            VALUES (?, NULL, ?, 0, 0, 0, NULL, ?)
            """,
            (sess, today_str(), now_str()),
        )
        conn.commit()
        response.set_cookie(COOKIE_NAME, sess, httponly=True, samesite="lax")
        conn.close()
        return sess

    row = cur.execute("SELECT * FROM sessions WHERE session_id = ?", (sess,)).fetchone()
    if not row:
        cur.execute(
            """
            INSERT INTO sessions(session_id, child, day, served_count, correct_count, earned, current_qid, created_at)
            VALUES (?, NULL, ?, 0, 0, 0, NULL, ?)
            """,
            (sess, today_str(), now_str()),
        )
        conn.commit()
        response.set_cookie(COOKIE_NAME, sess, httponly=True, samesite="lax")
        conn.close()
        return sess

    # reset harian untuk session UI
    if row["day"] != today_str():
        cur.execute(
            """
            UPDATE sessions
            SET day = ?, served_count = 0, correct_count = 0, earned = 0, current_qid = NULL
            WHERE session_id = ?
            """,
            (today_str(), sess),
        )
        conn.commit()

    conn.close()
    return sess


def require_child(session_id: str):
    conn = db()
    row = conn.execute("SELECT child FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return row and row["child"]


def set_child(session_id: str, child: str):
    conn = db()
    conn.execute("UPDATE sessions SET child = ? WHERE session_id = ?", (child, session_id))
    conn.commit()
    conn.close()


def get_session_stats(session_id: str):
    conn = db()
    row = conn.execute(
        """
        SELECT child, day, served_count, correct_count, earned, current_qid
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_current_qid(session_id: str, qid):
    conn = db()
    conn.execute("UPDATE sessions SET current_qid = ? WHERE session_id = ?", (qid, session_id))
    conn.commit()
    conn.close()


def split_bank_by_difficulty(bank):
    easy = [q for q in bank if q.get("difficulty") == "easy"]
    medium = [q for q in bank if q.get("difficulty") == "medium"]
    hard = [q for q in bank if q.get("difficulty") == "hard"]
    return easy, medium, hard


def pick_adaptive_question(child: str, bank: list[dict]):
    easy, med, hard = split_bank_by_difficulty(bank)

    # fallback safety
    if not bank:
        raise ValueError("Bank soal kosong")
    if not easy and not med and not hard:
        return random.choice(bank)

    days = last_n_days(7)
    recap = get_daily_recap(child, days)

    served7 = int(recap["totals"].get("served_count", 0) or 0)
    acc = int(recap["totals"].get("accuracy_pct", 0) or 0)

    # GATING: sebelum 50 soal, tetap pemula
    if served7 < 50:
        # dominan easy, tapi kalau bank kamu belum ada easy, fallback aman
        return random.choice(easy or med or bank)

    r = random.random()

    if acc < 60:
        return random.choice(easy or bank)

    if acc < 80:
        if r < 0.7:
            return random.choice(easy or bank)
        return random.choice(med or easy or bank)

    # acc >= 80
    if r < 0.1 and hard:
        return random.choice(hard)
    if r < 0.6 and med:
        return random.choice(med)
    return random.choice(easy or med or bank)


def upsert_daily(child: str, day: str):
    conn = db()
    conn.execute(
        """
        INSERT INTO child_daily(child, day, served_count, correct_count, earned)
        VALUES (?, ?, 0, 0, 0)
        ON CONFLICT(child, day) DO NOTHING
        """,
        (child, day),
    )
    conn.commit()
    conn.close()


def increment_served(session_id: str, child: str):
    day = today_str()
    upsert_daily(child, day)

    conn = db()
    conn.execute("UPDATE sessions SET served_count = served_count + 1 WHERE session_id = ?", (session_id,))
    conn.execute(
        "UPDATE child_daily SET served_count = served_count + 1 WHERE child = ? AND day = ?",
        (child, day),
    )
    conn.commit()
    conn.close()


def mark_correct(session_id: str, child: str):
    day = today_str()
    upsert_daily(child, day)

    conn = db()
    conn.execute(
        """
        UPDATE sessions
        SET correct_count = correct_count + 1,
            earned = earned + ?
        WHERE session_id = ?
        """,
        (REWARD_PER_CORRECT, session_id),
    )
    conn.execute(
        """
        UPDATE child_daily
        SET correct_count = correct_count + 1,
            earned = earned + ?
        WHERE child = ? AND day = ?
        """,
        (REWARD_PER_CORRECT, child, day),
    )
    conn.commit()
    conn.close()


def last_n_days(n: int):
    # returns list of YYYY-MM-DD oldest -> newest
    end = date.today()
    days = [(end - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]
    return days


def get_daily_recap(child: str, days: list[str]):
    conn = db()
    rows = conn.execute(
        """
        SELECT day, served_count, correct_count, earned
        FROM child_daily
        WHERE child = ?
          AND day >= ?
          AND day <= ?
        ORDER BY day ASC
        """,
        (child, days[0], days[-1]),
    ).fetchall()
    conn.close()

    by_day = {r["day"]: dict(r) for r in rows}
    out = []
    for d in days:
        r = by_day.get(d, {"day": d, "served_count": 0, "correct_count": 0, "earned": 0})
        served = int(r["served_count"])
        correct = int(r["correct_count"])
        acc = round((correct / served) * 100) if served > 0 else 0
        out.append(
            {
                "day": d,
                "served_count": served,
                "correct_count": correct,
                "earned": int(r["earned"]),
                "accuracy_pct": acc,
            }
        )

    total_served = sum(x["served_count"] for x in out)
    total_correct = sum(x["correct_count"] for x in out)
    total_earned = sum(x["earned"] for x in out)
    total_acc = round((total_correct / total_served) * 100) if total_served > 0 else 0

    return {
        "child": child,
        "days": out,
        "totals": {
            "served_count": total_served,
            "correct_count": total_correct,
            "earned": total_earned,
            "accuracy_pct": total_acc,
        },
    }


app = FastAPI(title=APP_TITLE)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/.well-known/{path:path}")
def well_known(path: str):
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    resp = RedirectResponse(url="/start")
    get_or_create_session(request, resp)
    return resp


@app.get("/start", response_class=HTMLResponse)
def start(request: Request):
    resp = RedirectResponse(url="/select")
    sess = get_or_create_session(request, resp)
    if require_child(sess):
        return RedirectResponse(url="/practice")
    return resp


@app.get("/select", response_class=HTMLResponse)
def select_page(request: Request):
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" href="/static/icon-512.png">
  <meta name="theme-color" content="#070b14">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="apple-touch-icon" href="/static/icon-512.png">
  <title>Altha dan Leia Quiz - Pilih Akun</title>
  <style>
    body {{
      margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: #0b1220; color: #e8eefc;
      display: flex; align-items: center; justify-content: center; min-height: 100vh;
    }}
    .card {{
      width: min(520px, 92vw);
      background: #121b2f; border: 1px solid #243055;
      border-radius: 18px; padding: 22px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.35);
      margin: 0px 20px;
    }}
    h1 {{ margin: 0 0 12px 0; font-size: 22px; }}
    p {{ margin: 0 0 16px 0; opacity: 0.9; }}
    .btns {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    }}
    a {{ text-decoration: none; }}
    button {{
      width: 100%;
      height: 90px; border-radius: 16px; border: 1px solid #2c3a66;
      background: #1a2543; color: #e8eefc; font-size: 20px; font-weight: 700;
      cursor: pointer;
    }}
    button:active {{ transform: scale(0.99); }}
    .note {{ margin-top: 14px; font-size: 13px; opacity: 0.75; }}
    .links {{ margin-top: 14px; font-size: 13px; opacity: 0.85; display:flex; gap: 12px; }}
    .links a {{ color: #b8d1ff; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Pilih akun dulu</h1>
    <p>Siapa yang mau latihan hari ini?</p>
    <div class="btns">
      <a href="/select/althafandra"><button type="button">Althafandra</button></a>
      <a href="/select/alleia"><button type="button">Alleia</button></a>
    </div>
    <div class="note">Batas {DAILY_LIMIT} soal per hari per anak. Reward Rp {REWARD_PER_CORRECT} per jawaban benar.</div>
    <div class="links">
      <a href="/stats">Lihat Statistik 7 Hari</a>
    </div>
  </div>
</body>
</html>
"""
    resp = HTMLResponse(content=html)
    get_or_create_session(request, resp)
    return resp


@app.get("/select/{child}")
def select_child(request: Request, child: str):
    resp = RedirectResponse(url="/practice", status_code=303)
    sess = get_or_create_session(request, resp)
    child = (child or "").strip().lower()
    if child not in CHILDREN:
        return RedirectResponse(url="/select", status_code=303)
    set_child(sess, child)
    return resp


@app.get("/practice", response_class=HTMLResponse)
def practice_page(request: Request):
    placeholder = HTMLResponse(content="")
    sess = get_or_create_session(request, placeholder)

    child = require_child(sess)
    if not child:
        return RedirectResponse(url="/select")

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" href="/static/icon-512.png">
  <meta name="theme-color" content="#070b14">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="apple-touch-icon" href="/static/icon-512.png">
  <title>Altha dan Leia Quiz - Latihan Matematika</title>
  <style>
    :root {{
      --bg: #070b14;
      --panel: #0f1730;
      --panel2: #101c3b;
      --border: #21305b;
      --text: #e9f0ff;
      --muted: rgba(233,240,255,0.75);
    }}
    body {{
      margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: var(--bg); color: var(--text);
      height: 100vh;
      overflow: hidden;
    }}
    .wrap {{
      height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 10px;
      padding: 12px;
      box-sizing: border-box;
    }}
    .top {{
      display: flex; gap: 10px; align-items: center; justify-content: space-between;
      background: var(--panel); border: 1px solid var(--border);
      border-radius: 14px; padding: 12px;
    }}
    .stat {{
      display: flex; flex-direction: column;
      font-size: 12px; color: var(--muted);
    }}
    .stat strong {{ color: var(--text); font-size: 14px; }}
    .question {{
      background: var(--panel2); border: 1px solid var(--border);
      border-radius: 14px; padding: 16px;
      display: grid; grid-template-rows: auto auto auto;
      align-content: start;
      gap: 10px;
    }}
    .prompt {{
      font-size: clamp(26px, 5vw, 46px);
      font-weight: 800;
      letter-spacing: 0.5px;
      margin: 25px 10px;
    }}
    .answerbox {{
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 12px;
      height: 64px;
      display: flex; align-items: center; justify-content: center;
      font-size: 34px; font-weight: 900;
    }}
    .msg {{
      min-height: 22px;
      color: var(--muted);
      font-weight: 700;
      font-size: 25px;
      margin: 0px 10px;
      margin-top: 25px;
    }}
    .pad {{
      background: var(--panel); border: 1px solid var(--border);
      border-radius: 14px; padding: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }}
    button {{
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(255,255,255,0.08);
      color: var(--text);
      height: min(12vh, 90px);
      font-size: clamp(22px, 4vw, 34px);
      font-weight: 900;
      cursor: pointer;
      user-select: none;
      -webkit-tap-highlight-color: transparent;
    }}
    button:active {{ transform: scale(0.99); }}
    .bottom {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    .wide {{
      height: min(10vh, 84px);
      font-size: clamp(18px, 3.2vw, 26px);
      background: rgba(80,130,255,0.18);
      border: 1px solid rgba(120,170,255,0.30);
    }}
    .danger {{
      background: rgba(255,90,90,0.14);
      border: 1px solid rgba(255,120,120,0.26);
    }}
    a {{
      color: rgba(180,210,255,0.95);
      text-decoration: none;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="stat">
        <div>Nama</div>
        <strong id="childName"></strong>
        <div style="font-size:12px; margin-bottom:15px;">
          Tingkat: <strong id="level">-</strong>
        </div>
        <a href="/stats">Lihat Statistik</a>
      </div>
      <div class="stat" style="text-align:right;">
        <div>Hari ini</div>
        <strong><span id="served">0</span> / {DAILY_LIMIT} soal</strong>
        <div style="font-size:12px; color: var(--muted);">Benar: <span id="correct">0</span> | Hadiah: Rp <span id="earned">0</span></div>
      </div>
    </div>

    <div class="question">
      <div class="prompt" id="prompt">Memuat soal...</div>
      <div class="answerbox" id="answerbox">-</div>
      <div class="msg" id="msg"></div>
    </div>

    <div class="pad">
      <div class="grid">
        <button onclick="tap('1')">1</button>
        <button onclick="tap('2')">2</button>
        <button onclick="tap('3')">3</button>
        <button onclick="tap('4')">4</button>
        <button onclick="tap('5')">5</button>
        <button onclick="tap('6')">6</button>
        <button onclick="tap('7')">7</button>
        <button onclick="tap('8')">8</button>
        <button onclick="tap('9')">9</button>
        <button class="danger" onclick="backspace()">⌫</button>
        <button onclick="tap('0')">0</button>
        <button class="danger" onclick="clearAll()">C</button>
      </div>

      <div class="bottom" style="margin-top:10px;">
        <button class="wide danger" onclick="resetAccount()">Ganti Akun</button>
        <button class="wide" onclick="nextQ()">Next</button>
      </div>
    </div>
  </div>

<script>
let currentQid = null;
let answerStr = "";
let locked = false;
let autoTimer = null;

function levelFromAccuracy(acc, served7) {{
  // gating: minimal 50 soal dulu baru boleh naik tingkat
  if ((served7 ?? 0) < 50) return "Pemula";

  if (acc >= 80) return "Mahir";
  if (acc >= 60) return "Menengah";
  return "Pemula";
}}

function setMsg(t) {{
  document.getElementById("msg").textContent = t || "";
}}

function renderAnswer() {{
  document.getElementById("answerbox").textContent = answerStr.length ? answerStr : "-";
}}

function tap(d) {{
  if (locked) return;
  if (answerStr.length >= 6) return;
  answerStr += d;
  renderAnswer();

  // auto-check setelah berhenti input 600ms
  if (autoTimer) clearTimeout(autoTimer);
  autoTimer = setTimeout(() => {{
    // jangan submit kalau kosong
    if (!answerStr.length) return;
    nextQ(); // pakai existing flow, tidak bikin endpoint baru
  }}, 600);
}}

function backspace() {{
  if (locked) return;
  answerStr = answerStr.slice(0, -1);
  renderAnswer();
  if (autoTimer) clearTimeout(autoTimer);
}}

function clearAll() {{
  if (locked) return;
  answerStr = "";
  renderAnswer();
  if (autoTimer) clearTimeout(autoTimer);
}}

async function loadSessionStats() {{
  const r = await fetch("/api/stats");
  const data = await r.json();

  document.getElementById("childName").textContent = data.child || "";
  document.getElementById("served").textContent = data.served_count ?? 0;
  document.getElementById("correct").textContent = data.correct_count ?? 0;
  document.getElementById("earned").textContent = data.earned ?? 0;

  // ambil akurasi 7 hari untuk level
  if (data.recap7 && data.recap7.children && data.child) {{
    const recap = data.recap7.children[data.child];
    const acc = recap?.totals?.accuracy_pct ?? 0;
    const served7 = recap?.totals?.served_count ?? 0;
    document.getElementById("level").textContent = levelFromAccuracy(acc, served7);
  }}
}}

async function loadQuestion() {{
  setMsg("");
  answerStr = "";
  renderAnswer();

  const r = await fetch("/api/question");
  const data = await r.json();

  if (!data.ok) {{
    document.getElementById("prompt").textContent = data.message || "Tidak bisa ambil soal.";
    locked = true;
    return;
  }}

  currentQid = data.qid;
  document.getElementById("prompt").textContent = data.prompt;
  locked = false;

  await loadSessionStats();
}}

async function nextQ() {{
  if (autoTimer) clearTimeout(autoTimer);
  autoTimer = null;

  if (locked) return;
  if (!currentQid) return;

  locked = true;

  const payload = {{
    qid: currentQid,
    answer: answerStr
  }};

  const r = await fetch("/api/answer", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify(payload)
  }});
  const data = await r.json();

  if (!data.ok) {{
    setMsg(data.message || "Ada masalah.");
    locked = false;
    return;
  }}

  if (data.correct) {{
    setMsg("Benar! kamu dapat Rp {REWARD_PER_CORRECT}");
  }} else {{
    setMsg("Salah. Jawaban benar: " + data.correct_answer);
  }}

  await loadSessionStats();

  setTimeout(() => {{
    loadQuestion();
  }}, 1500);
}}

async function resetAccount() {{
  await fetch("/api/logout", {{ method: "POST" }});
  window.location.href = "/select";
}}

(async function init() {{
  await loadSessionStats();
  await loadQuestion();
}})();

if ("serviceWorker" in navigator) {{
  navigator.serviceWorker.register("/static/sw.js");
}}
</script>

</body>
</html>
"""
    resp = HTMLResponse(content=html)
    get_or_create_session(request, resp)
    return resp


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request):
    # session cookie optional, tapi kita tetap set kalau belum ada
    resp = HTMLResponse(content="")
    get_or_create_session(request, resp)

    html = """
<!doctype html>
<html>
<
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" href="/static/icon-512.png">
  <meta name="theme-color" content="#070b14">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Altha dan Leia Quiz - Stats 7 Hari</title>
  <style>
    :root{
      --bg:#070b14;
      --panel:#0f1730;
      --panel2:#101c3b;
      --border:#21305b;
      --text:#e9f0ff;
      --muted: rgba(233,240,255,0.75);
    }
    body{
      margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: var(--bg); color: var(--text);
      min-height: 100vh;
      padding: 14px;
      box-sizing: border-box;
    }
    .top{
      display:flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;
      background: var(--panel); border: 1px solid var(--border);
      border-radius: 14px; padding: 12px;
      align-items: center;
    }
    a{ color: rgba(180,210,255,0.95); text-decoration:none; font-weight: 800; }
    .wrap{
      margin-top: 12px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    @media (max-width: 900px){
      .wrap{ grid-template-columns: 1fr; }
    }
    .card{
      background: var(--panel2);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
    }
    .title{
      display:flex; justify-content: space-between; align-items: baseline;
      gap: 10px;
    }
    .title h2{ margin:0; font-size: 18px; }
    .totals{
      display:grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-top: 10px;
    }
    .mini{
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 12px;
      padding: 10px;
    }
    .mini .k{ font-size: 12px; color: var(--muted); font-weight: 700; }
    .mini .v{ margin-top: 4px; font-size: 16px; font-weight: 900; }
    table{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 13px;
      overflow: hidden;
      border-radius: 12px;
    }
    th, td{
      padding: 10px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      text-align: left;
      white-space: nowrap;
    }
    th{ color: var(--muted); font-weight: 900; }
    .muted{ color: var(--muted); }
    .right{ text-align: right; }
  </style>
</head>
<body>
  <div class="top">
    <div>
      <div style="font-weight:900; font-size:18px;">Rekap 7 Hari Terakhir</div>
      <div class="muted" id="rangeText">Memuat...</div>
    </div>
    <div style="display:flex; gap:12px; align-items:center;">
      <a href="/select">Pilih Akun</a>
      <a href="/practice">Kembali ke Quiz</a>
      <button id="clearBtn" style="
        height: 38px;
        border-radius: 12px;
        border: 1px solid rgba(255,120,120,0.26);
        background: rgba(255,90,90,0.14);
        color: var(--text);
        font-weight: 900;
        cursor: pointer;
        padding: 0 12px;
      ">Clear DB</button>
    </div>
  </div>

  <div class="wrap">
    <div class="card" id="card_althafandra">
      <div class="title">
        <h2>Althafandra</h2>
        <div class="muted" id="updated_a"></div>
      </div>

      <div class="totals">
        <div class="mini"><div class="k">Total Soal</div><div class="v" id="a_total_served">0</div></div>
        <div class="mini"><div class="k">Total Benar</div><div class="v" id="a_total_correct">0</div></div>
        <div class="mini"><div class="k">Akurasi</div><div class="v" id="a_total_acc">0%</div></div>
        <div class="mini"><div class="k">Total Hadiah</div><div class="v" id="a_total_earned">Rp 0</div></div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Tanggal</th>
            <th class="right">Soal</th>
            <th class="right">Benar</th>
            <th class="right">Akurasi</th>
            <th class="right">Hadiah</th>
          </tr>
        </thead>
        <tbody id="a_rows"></tbody>
      </table>
    </div>

    <div class="card" id="card_alleia">
      <div class="title">
        <h2>Alleia</h2>
        <div class="muted" id="updated_b"></div>
      </div>

      <div class="totals">
        <div class="mini"><div class="k">Total Soal</div><div class="v" id="b_total_served">0</div></div>
        <div class="mini"><div class="k">Total Benar</div><div class="v" id="b_total_correct">0</div></div>
        <div class="mini"><div class="k">Akurasi</div><div class="v" id="b_total_acc">0%</div></div>
        <div class="mini"><div class="k">Total Hadiah</div><div class="v" id="b_total_earned">Rp 0</div></div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Tanggal</th>
            <th class="right">Soal</th>
            <th class="right">Benar</th>
            <th class="right">Akurasi</th>
            <th class="right">Hadiah</th>
          </tr>
        </thead>
        <tbody id="b_rows"></tbody>
      </table>
    </div>
  </div>

<script>
function tdRight(v){
  return `<td class="right">${v}</td>`;
}

function renderChild(prefix, recap){
  const t = recap.totals || {};
  document.getElementById(prefix + "_total_served").textContent = t.served_count ?? 0;
  document.getElementById(prefix + "_total_correct").textContent = t.correct_count ?? 0;
  document.getElementById(prefix + "_total_acc").textContent = (t.accuracy_pct ?? 0) + "%";
  document.getElementById(prefix + "_total_earned").textContent = "Rp " + (t.earned ?? 0);

  const rowsEl = document.getElementById(prefix + "_rows");
  rowsEl.innerHTML = "";

  (recap.days || []).forEach(d => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${d.day}</td>` +
      tdRight(d.served_count ?? 0) +
      tdRight(d.correct_count ?? 0) +
      tdRight((d.accuracy_pct ?? 0) + "%") +
      tdRight("Rp " + (d.earned ?? 0));
    rowsEl.appendChild(tr);
  });
}

async function load(){
  const r = await fetch("/api/stats");
  const data = await r.json();
  if (!data.ok){
    document.getElementById("rangeText").textContent = data.message || "Gagal memuat.";
    return;
  }

  if (data.recap7 && data.recap7.range){
    document.getElementById("rangeText").textContent =
      "Rentan: " + data.recap7.range.start + " sampai " + data.recap7.range.end;
  } else {
    document.getElementById("rangeText").textContent = "7 hari terakhir";
  }

  const ra = (data.recap7 && data.recap7.children && data.recap7.children.althafandra) ? data.recap7.children.althafandra : null;
  const rb = (data.recap7 && data.recap7.children && data.recap7.children.alleia) ? data.recap7.children.alleia : null;

  if (ra) renderChild("a", ra);
  if (rb) renderChild("b", rb);

  const ts = (data.recap7 && data.recap7.generated_at) ? data.recap7.generated_at : "";
  document.getElementById("updated_a").textContent = ts ? ("Updated: " + ts) : "";
  document.getElementById("updated_b").textContent = ts ? ("Updated: " + ts) : "";
}

document.getElementById("clearBtn").addEventListener("click", async () => {
  const pwd = prompt("Masukkan password untuk clear database:");
  if (!pwd) return;

  const ok = confirm("Yakin mau hapus SEMUA data quiz dan statistik?");
  if (!ok) return;

  const r = await fetch("/api/admin/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password: pwd })
  });

  const data = await r.json();
  alert(data.message || (data.ok ? "OK" : "Gagal"));

  if (data.ok) load();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js");
}

load();
</script>
</body>
</html>
"""
    resp = HTMLResponse(content=html)
    get_or_create_session(request, resp)
    return resp


@app.get("/api/stats")
def api_stats(request: Request):
    # This endpoint returns:
    # - session stats (for quiz page)
    # - recap7 for both children (for /stats page)
    resp = JSONResponse({})
    sess = get_or_create_session(request, resp)
    s = get_session_stats(sess) or {}

    days = last_n_days(7)
    recap = {}
    for c in CHILDREN:
        recap[c] = get_daily_recap(c, days)

    payload = {
        "ok": True,
        # session fields (used by quiz)
        "child": s.get("child"),
        "day": s.get("day"),
        "served_count": s.get("served_count", 0),
        "correct_count": s.get("correct_count", 0),
        "earned": s.get("earned", 0),
        # recap fields (used by /stats)
        "recap7": {
            "range": {"start": days[0], "end": days[-1]},
            "generated_at": now_str(),
            "children": recap,
        },
    }
    return JSONResponse(payload)


@app.get("/api/question")
def api_question(request: Request):
    resp = JSONResponse({})
    sess = get_or_create_session(request, resp)
    stats = get_session_stats(sess)
    if not stats or not stats.get("child"):
        return JSONResponse({"ok": False, "message": "Pilih akun dulu."}, status_code=400)

    child = stats["child"]

    # pilih versi + bank per anak
    if child == "alleia":
        bank = BANK_V1
        qver = 1 # Lebih mudah
        picker = "adaptive"
    elif child == "althafandra":
        bank = BANK_V2
        qver = 2 # Lebih sulit
        # picker = "random"
        picker = "adaptive"
    else:
        return JSONResponse({"ok": False, "message": "Akun tidak dikenal."}, status_code=400)

    # limit per anak per hari (berdasarkan child_daily, bukan session)
    today = last_n_days(1)[0]
    r = get_daily_recap(child, [today])
    served_today = r["days"][0]["served_count"]
    if served_today >= DAILY_LIMIT:
        return JSONResponse(
            {"ok": False, "message": f"Batas hari ini sudah tercapai ({DAILY_LIMIT} soal). Besok lanjut ya."}
        )

    # pilih soal
    if picker == "adaptive":
        q = pick_adaptive_question(child=child, bank=bank)
    else:
        q = random.choice(bank)

    qid = q["id"]

    set_current_qid(sess, qid)
    increment_served(sess, child)

    # optional: ambil dari mapping global (kalau kamu tetap pakai QUESTION_BY_ID gabungan)
    q_full = QUESTION_BY_ID.get(qid, q)
    if not q_full:
        return JSONResponse({"ok": False, "message": "Soal tidak ditemukan."}, status_code=500)

    return JSONResponse({"ok": True, "qid": qid, "prompt": q_full["prompt"], "version": qver})


@app.post("/api/answer")
async def api_answer(request: Request):
    resp = JSONResponse({})
    sess = get_or_create_session(request, resp)
    stats = get_session_stats(sess)
    if not stats or not stats.get("child"):
        return JSONResponse({"ok": False, "message": "Pilih akun dulu."}, status_code=400)

    child = stats["child"]

    body = await request.json()
    qid = (body.get("qid") or "").strip()
    ans = (body.get("answer") or "").strip()

    # wajib match current_qid supaya tidak bisa spam reward
    if not stats.get("current_qid") or qid != stats["current_qid"]:
        return JSONResponse({"ok": False, "message": "Soal tidak sinkron. Klik Next lagi."}, status_code=400)

    q = QUESTION_BY_ID.get(qid)
    if not q:
        return JSONResponse({"ok": False, "message": "Soal tidak ditemukan."}, status_code=400)

    try:
        user_val = int(ans) if ans != "" else None
    except ValueError:
        user_val = None

    correct_val = int(q["answer"])
    correct = user_val is not None and user_val == correct_val

    if correct:
        mark_correct(sess, child)

    # clear current_qid supaya answer tidak bisa diulang
    set_current_qid(sess, None)

    return JSONResponse({"ok": True, "correct": correct, "correct_answer": correct_val})


@app.post("/api/logout")
def api_logout(request: Request):
    sess = request.cookies.get(COOKIE_NAME)
    if sess:
        conn = db()
        conn.execute("UPDATE sessions SET child = NULL, current_qid = NULL WHERE session_id = ?", (sess,))
        conn.commit()
        conn.close()
    return JSONResponse({"ok": True})


@app.post("/api/admin/clear")
async def api_admin_clear(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    pwd = (body.get("password") or "").strip()
    if pwd != ADMIN_CLEAR_PASSWORD:
        return JSONResponse({"ok": False, "message": "Password salah."}, status_code=401)

    clear_database()
    return JSONResponse({"ok": True, "message": "Database sudah dikosongkan."})


@app.get("/manifest.json")
@app.get("/manifest.webmanifest")
def manifest():
    return {
        "name": "Altha dan Leia Quiz",
        "short_name": "Altha dan Leia Quiz",
        "start_url": "/select",
        "display": "standalone",
        "background_color": "#070b14",
        "theme_color": "#070b14",
        "icons": [
            {
                "src": "/static/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }


@app.get("/health")
def health():
    return {"ok": True}