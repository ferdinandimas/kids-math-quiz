from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="app/web/templates")

def home_page_html(request: Request, ):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "title": "Altha dan Leia Quiz"}
    )

def quiz_page_html(request: Request, reward, daily_limit):
    return templates.TemplateResponse(
        "quiz.html",
        {
            "request": request,
            "REWARD_PER_CORRECT": reward,
            "DAILY_LIMIT": daily_limit,
            "title": "Altha dan Leia Quiz"
        }
    )

def stats_page_html(request: Request):
    return templates.TemplateResponse(
        "stats.html",
        {"request": request, "title": "Altha dan Leia Quiz"}
    )