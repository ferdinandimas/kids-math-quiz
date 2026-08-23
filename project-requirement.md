# Kids Math Quiz — Project Requirements

## 1. Purpose and Scope

Kids Math Quiz is a lightweight, mobile-oriented web application for two named
child profiles to practise basic arithmetic. It presents an adaptive stream of
addition and subtraction questions, records daily performance, calculates a
cash-style reward for correct answers, and provides a seven-day comparison
dashboard.

This document is reverse-engineered from the implementation. It describes
implemented requirements, not proposed future scope.

## 2. Users and Roles

| Role | Implemented capabilities |
| --- | --- |
| Child learner | Select one of the configured profiles, answer maths questions with an on-screen numeric keypad, receive correctness feedback, and view personal progress. |
| Parent/operator | View the seven-day statistics for both profiles and clear all persisted quiz data using the configured administrator password. |

The application currently supports exactly these profiles: `althafandra` and
`alleia`. There is no account registration, general authentication, or
role-based access control beyond the clear-data password.

## 3. Functional Requirements

### 3.1 Profile and session management

1. A visitor opening `/` must be directed to the start flow. A visitor with no
   selected profile must see `/home`; one with a selected profile must resume at
   `/quiz`.
2. The home page must let a visitor select either configured child profile and
   then redirect them to the quiz.
3. The server must maintain a browser session in the HTTP-only, `SameSite=Lax`
   cookie named `math_sess`. The session identifier must be securely generated.
4. A selected profile and the currently presented question ID must be stored
   server-side against that session.
5. Selecting **Ganti Akun** must clear the selected profile and active question
   from the current session, then return the visitor to the profile-selection
   page. It must not remove accumulated daily statistics.
6. On a new calendar day, the application must reset the session's daily
   counters and active question, while retaining the profile selection and the
   historic daily aggregates.

### 3.2 Quiz delivery and answer flow

1. A profile must receive questions only from its assigned question bank:
   `althafandra` uses bank version 1 and `alleia` uses bank version 2.
2. Each bank must contain 400 deterministic, unique addition/subtraction
   questions generated from a fixed seed. Subtraction questions must not have a
   negative result.
3. The question endpoint must return a question ID, human-readable arithmetic
   prompt, and bank version; it must never expose the answer in the question
   payload.
4. The quiz UI must provide a touch-friendly numeric keypad and show the typed
   answer. It must automatically submit after 600 ms without further input.
5. A learner may enter up to six digits. The current UI contains internal
   backspace/clear helpers, but does not expose controls for them; this is an
   implementation limitation, not an available user requirement.
6. The server must accept an answer only when its `qid` matches the question
   currently stored in the session. Out-of-sync, missing, or unknown questions
   must be rejected with an explanatory message.
7. Answers must be parsed as integers. An empty or non-numeric answer is
   incorrect.
8. Each submitted answer must produce correctness feedback. Correct answers
   show a positive popup and incorrect answers show the correct answer; the
   next question loads automatically after 1.2 or 1.6 seconds respectively.
9. Each issued question must increment *served* count. Each accepted answer
   must increment *answered* count exactly once. A correct answer must also
   increment *correct* count and earned reward.
10. The application must stop serving questions once the profile has answered
    its daily limit and display that the learner can continue tomorrow.

### 3.3 Adaptive difficulty and learner level

1. Questions must be labelled easy, medium, or hard according to their numeric
   answer: `<= 10`, `<= 30`, and `> 30` respectively.
2. Difficulty selection must use the profile's previous seven days of results:
   - Before 50 served questions, select easy questions (falling back to medium
     or any available question).
   - At below 60% accuracy, select easy questions.
   - At 60–79% accuracy, select easy questions 70% of the time and medium
     questions otherwise.
   - At 80% or higher, select hard questions 10% of the time, medium questions
     50% of the time, and easy questions otherwise, with graceful fallbacks.
3. The quiz screen must show a learner level derived from the seven-day
   *answered* count and accuracy: **Pemula** before 50 answers or below 60%,
   **Menengah** at 60–79%, and **Mahir** at 80% or higher.

### 3.4 Reward and statistics

1. Every correct answer must earn the configured fixed reward (currently
   Rp 50). Incorrect answers earn nothing.
2. The quiz page must show today's answered count, correct count, earned amount,
   and daily answer limit for the active profile.
3. A public statistics page must display both profiles' last seven calendar
   days, including days with no activity.
4. For each profile, the statistics page must show daily and seven-day totals
   for answered questions, correct answers, accuracy, and earned reward.
5. Accuracy must be rounded to the nearest whole percent and calculated as
   `correct_count / answered_count * 100`; it must be zero when no questions
   have been answered.
6. The statistics API must also report served counts, the active profile's
   current-day counts, the seven-day date range, and a generation timestamp.

### 3.5 Administration

1. The statistics page must expose a **Clear DB** action.
2. The action must ask for confirmation and the administrator password.
3. The server must reject an invalid password with HTTP 401.
4. On a valid password, the system must permanently delete all session and
   daily-statistics records and compact the SQLite database. The UI must reload
   the displayed statistics after a successful clear.

## 4. Web and API Contract

| Endpoint | Behaviour |
| --- | --- |
| `GET /`, `GET /start` | Starts or resumes the session flow. |
| `GET /home` | Profile-selection HTML page. |
| `GET /home/{child}` | Validates and selects a profile, then redirects to quiz. |
| `GET /quiz` | Active learner quiz page; redirects home when no profile is selected. |
| `GET /stats` | Seven-day comparison dashboard. |
| `GET /api/question` | Returns the next permitted question and records it as the session's active question. |
| `POST /api/answer` | Accepts JSON `{ "qid", "answer" }`, validates the active question, records the result, and returns correctness plus the correct answer. |
| `GET /api/stats` | Returns active-session counts and seven-day recap data for both profiles. |
| `POST /api/logout` | Removes profile selection and active question from the current session. |
| `POST /api/admin/clear` | Accepts `{ "password" }` and clears all persisted data if valid. |
| `GET /manifest.json`, `/manifest.webmanifest` | Returns the installable web-app manifest. |
| `GET /health` | Returns `{ "ok": true }` for liveness checking. |

Unknown UI routes must redirect to `/home`. Unknown API routes must return a
JSON 404 response. Missing static files must remain 404 responses.

## 5. Data Requirements

The application must use SQLite. The database path is configurable; it defaults
to `math_app.sqlite3`.

| Store | Required fields and meaning |
| --- | --- |
| `sessions` | `session_id` primary key; selected `child`; active `day`; per-session served, answered, correct, and earned counters; `current_qid`; and creation timestamp. |
| `child_daily` | One row per `(child, day)` containing served, answered, correct, and earned aggregates. |

Database schema initialization must be safe to run on startup. The application
must also add the `answered_count` column to older databases when missing.

## 6. Configuration and Runtime Requirements

| Setting | Current default / value | Purpose |
| --- | --- | --- |
| `DB_PATH` | `math_app.sqlite3` | SQLite database file location. |
| `ADMIN_CLEAR_PASSWORD` | `masukaja` | Password for the destructive clear action. It must be overridden in a real deployment. |
| `DAILY_LIMIT` | 400 | Per-child daily answered-question limit. |
| `REWARD_PER_CORRECT` | 50 | Reward added for each correct answer. |
| `COOKIE_NAME` | `math_sess` | Browser session cookie name. |

The backend is a Python 3.9+ FastAPI application with Uvicorn as its ASGI
server. The importable application object is `app.main:app`; the existing
README command (`uvicorn main:app --reload`) does not match the current source
layout.

## 7. User Experience and Platform Requirements

1. Pages must be responsive and optimized for a touchscreen, with a dark visual
   theme, large controls, and disabled browser pinch/zoom interactions.
2. The app must expose an installable web-app manifest with standalone display,
   theme colours, start URL `/home`, and a 512px icon.
3. Quiz and statistics pages attempt to register `/static/sw.js`. The current
   service-worker file is empty, so the implementation provides no defined
   offline caching or offline quiz capability.
4. Static assets must be served under `/static`.

## 8. Security and Operational Constraints

1. Session cookies must be HTTP-only and use `SameSite=Lax`; the current code
   does not set the `Secure` attribute, so HTTPS deployment hardening remains a
   deployment requirement.
2. The clear-data password must be supplied through `ADMIN_CLEAR_PASSWORD`,
   not left at its committed default.
3. The clear endpoint is intentionally destructive and has no rate limiting,
   CSRF protection, audit log, or user-role authentication in the current
   implementation. Deployments that expose it beyond a trusted household
   network require those controls.
4. The application is designed for local/lightweight use. SQLite write
   operations are performed in short independent connections; high-concurrency
   multi-user deployment is outside the demonstrated scope.

## 9. Out of Scope in the Current Implementation

- Multiplication, division, negative-result questions, free-form child accounts,
  educator accounts, and content management.
- Persistent individual-question history, retry tracking, badges, leaderboards,
  or reports beyond the rolling seven-day aggregate.
- Offline operation despite the PWA metadata.
- Automated tests and a production deployment configuration.
