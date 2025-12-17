from datetime import date

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.config import CHILDREN, REWARD_PER_CORRECT, DAILY_LIMIT
from app.services.session_service import SessionService
from app.services.stats_service import StatsService
from app.services.question_service import QuestionService
from app.services.admin_service import AdminService
from app.web.templates import templates

def build_router(
    session_svc: SessionService,
    stats_svc: StatsService,
    q_svc: QuestionService,
    admin_svc: AdminService,
):
    r = APIRouter()

    @r.get("/favicon.ico")
    def favicon():
        return Response(status_code=204)

    @r.get("/.well-known/{path:path}")
    def well_known(path: str):
        return Response(status_code=204)

    @r.get("/")
    def root(request: Request):
        resp = RedirectResponse(url="/start")
        session_svc.get_or_create(request, resp)
        return resp

    @r.get("/start")
    def start(request: Request):
        resp = RedirectResponse(url="/home")
        sess = session_svc.get_or_create(request, resp)
        if session_svc.require_child(sess):
            return RedirectResponse(url="/quiz")
        return resp

    @r.get("/home", response_class=HTMLResponse)
    def home_page(request: Request):
        resp = templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "DAILY_LIMIT": DAILY_LIMIT,
                "REWARD_PER_CORRECT": REWARD_PER_CORRECT,
            }
        )
        session_svc.get_or_create(request, resp)  # set cookie / session ke response ini
        return resp

    @r.get("/home/{child}")
    def select_child(request: Request, child: str):
        resp = RedirectResponse(url="/quiz", status_code=303)
        sess = session_svc.get_or_create(request, resp)
        child = (child or "").strip().lower()
        if child not in CHILDREN:
            return RedirectResponse(url="/home", status_code=303)
        session_svc.set_child(sess, child)
        return resp

    @r.get("/quiz", response_class=HTMLResponse)
    def quiz_page(request: Request):
        placeholder = HTMLResponse(content="")
        sess = session_svc.get_or_create(request, placeholder)
        child = session_svc.require_child(sess)
        stat = session_svc.get_stats(sess) or {}

        if not child:
            return RedirectResponse(url="/home")

        today = date.today().isoformat()
        recap = stats_svc.get_daily_recap(child, [today])

        days = stats_svc.last_n_days(7)
        week_recap = {c: stats_svc.get_daily_recap(c, days) for c in CHILDREN}
        week_accuracy = week_recap[child]["totals"]["accuracy_pct"]
        week_answered = week_recap[child]["totals"]["answered_count"]

        level = (
            "Pemula" if (week_answered or 0) < 50
            else "Mahir" if week_accuracy >= 80
            else "Menengah" if week_accuracy >= 60
            else "Pemula"
        )

        resp = templates.TemplateResponse(
            "quiz.html",
            {
                "request": request,
                "child": child,
                "answered_today": int(recap["days"][0].get("answered_count", 0) or 0),
                "correct_count": int(recap["days"][0].get("correct_count", 0) or 0),
                "earned": int(recap["days"][0].get("earned", 0) or 0),
                "level": level,
                "DAILY_LIMIT": DAILY_LIMIT,
                "REWARD_PER_CORRECT": REWARD_PER_CORRECT,
            }
        )
        session_svc.get_or_create(request, resp)
        return resp

    @r.get("/stats", response_class=HTMLResponse)
    def stats_page(request: Request):
        resp = templates.TemplateResponse(
            "stats.html",
            {"request": request, "title": "Quiz Statistics"}
        )
        session_svc.get_or_create(request, resp)
        return resp

    @r.get("/api/stats")
    def api_stats(request: Request):
        resp = JSONResponse({})
        sess = session_svc.get_or_create(request, resp)
        s = session_svc.get_stats(sess) or {}
        child = session_svc.require_child(sess)

        days = stats_svc.last_n_days(7)
        recap = {c: stats_svc.get_daily_recap(c, days) for c in CHILDREN}

        today = date.today().isoformat()
        today_recap = stats_svc.get_daily_recap(child, [today])

        payload = {
            "ok": True,
            "child": s.get("child"),
            "day": s.get("day"),
            "served_count": int(today_recap["days"][0].get("served_count", 0) or 0),
            "answered_count": int(today_recap["days"][0].get("answered_count", 0) or 0),
            "correct_count": int(today_recap["days"][0].get("correct_count", 0) or 0),
            "earned": int(today_recap["days"][0].get("earned", 0) or 0),
            "recap7": {
                "range": {"start": days[0], "end": days[-1]},
                "generated_at": session_svc.now_str(),
                "children": recap,
            },
        }
        return JSONResponse(payload)

    @r.get("/api/question")
    def api_question(request: Request):
        resp = JSONResponse({})
        sess = session_svc.get_or_create(request, resp)
        stats = session_svc.get_stats(sess)

        if not stats or not stats.get("child"):
            return JSONResponse({"ok": False, "message": "Pilih akun dulu."}, status_code=400)

        child = stats["child"]

        payload, code = q_svc.get_question_payload(sess, child)

        if not payload.get("ok"):
            return JSONResponse(payload, status_code=code)

        qid = payload["qid"]
        session_svc.set_current_qid(sess, qid)

        today = session_svc.today_str()
        stats_svc.inc_served(sess, child, today)

        return JSONResponse(payload)

    @r.post("/api/answer")
    async def api_answer(request: Request):
        resp = JSONResponse({})
        sess = session_svc.get_or_create(request, resp)
        stats = session_svc.get_stats(sess)

        if not stats or not stats.get("child"):
            return JSONResponse({"ok": False, "message": "Pilih akun dulu."}, status_code=400)

        child = stats["child"]
        body = await request.json()
        qid = (body.get("qid") or "").strip()
        ans = (body.get("answer") or "").strip()

        if not stats.get("current_qid") or qid != stats["current_qid"]:
            return JSONResponse({"ok": False, "message": "Soal tidak sinkron. Klik Next lagi."}, status_code=400)

        q, correct_val, correct = q_svc.evaluate_answer(qid, ans)
        if not q:
            return JSONResponse({"ok": False, "message": "Soal tidak ditemukan."}, status_code=400)

        today = session_svc.today_str()
        stats_svc.inc_answered(sess, child, today)

        if correct:
            stats_svc.mark_correct(sess, child, today, REWARD_PER_CORRECT)

        session_svc.set_current_qid(sess, None)
        return JSONResponse({"ok": True, "correct": correct, "correct_answer": correct_val})

    @r.post("/api/logout")
    def api_logout(request: Request):
        sess = request.cookies.get("math_sess")
        if sess:
            session_svc.logout(sess)
        return JSONResponse({"ok": True})

    @r.post("/api/admin/clear")
    async def api_admin_clear(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        ok, msg = admin_svc.clear_db(body.get("password") or "")
        return JSONResponse({"ok": ok, "message": msg}, status_code=200 if ok else 401)

    @r.get("/manifest.json")
    @r.get("/manifest.webmanifest")
    def manifest():
        return {
            "name": "Altha dan Leia Quiz",
            "short_name": "Altha dan Leia Quiz",
            "start_url": "/home",
            "display": "standalone",
            "background_color": "#070b14",
            "theme_color": "#070b14",
            "icons": [{"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"}],
        }

    @r.get("/health")
    def health():
        return {"ok": True}

    return r