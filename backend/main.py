import json
import os
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

import uuid
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    init_db,
    create_session,
    get_session,
    init_progress,
    get_progress,
    complete_module,
    save_quiz_attempt,
    save_lesson,
    get_cached_lesson,
    compute_content_hash,
    find_syllabus_by_content_hash,
    save_lesson_to_cache,
    get_cached_lesson_by_content,
    find_cached_lesson_by_params,
)
from agents import (
    generate_syllabus,
    generate_lesson,
    generate_quiz,
    evaluate_answers,
)

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")


async def resolve_images(lesson: dict) -> dict:
    if not UNSPLASH_ACCESS_KEY:
        return lesson
    images = lesson.get("sections_images") or {}
    if not images:
        return lesson
    resolved = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for heading, query in images.items():
            try:
                resp = await client.get(
                    "https://api.unsplash.com/search/photos",
                    params={"query": query, "per_page": 1},
                    headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("results"):
                        resolved[heading] = data["results"][0]["urls"]["small"]
            except Exception:
                pass
    lesson["sections_images"] = resolved
    return lesson


app = FastAPI(title="AI Learning Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRequest(BaseModel):
    grade: str
    subject: str
    topic: str
    level: str
    goals: str = ""


class LessonRequest(BaseModel):
    session_id: str
    module_index: int
    module_title: str


class QuizRequest(BaseModel):
    session_id: str
    module_index: int
    module_title: str
    lesson_content: str


class SubmitRequest(BaseModel):
    session_id: str
    module_index: int
    questions: list
    user_answers: list
    correct_answers: list


@app.on_event("startup")
def startup():
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("⚠️  تحذير: GEMINI_API_KEY غير مضبوط في backend/.env")
        print("   احصل على مفتاح من: https://aistudio.google.com/apikey")
    init_db()


@app.post("/api/sessions")
async def start_learning(req: StartRequest):
    session_id = str(uuid.uuid4())[:8]
    content_hash = compute_content_hash(req.grade, req.subject, req.topic, req.level, req.goals)

    existing = find_syllabus_by_content_hash(content_hash, req.grade, req.subject, req.topic, req.level, req.goals)
    if existing:
        syllabus = existing
    else:
        try:
            syllabus = await generate_syllabus(req.grade, req.subject, req.topic, req.level, req.goals)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"فشل في إنشاء المنهج: {e}")

    create_session(session_id, req.grade, req.subject, req.topic, req.level, req.goals, json.dumps(syllabus), content_hash)
    init_progress(session_id, syllabus.get("modules", []))

    return {
        "session_id": session_id,
        "grade": req.grade,
        "subject": req.subject,
        "topic": req.topic,
        "level": req.level,
        "goals": req.goals,
        "syllabus": syllabus,
    }


@app.get("/api/sessions/{session_id}")
def get_session_info(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    syllabus = json.loads(session["syllabus"]) if session["syllabus"] else None
    progress = get_progress(session_id)
    return {
        "session_id": session["id"],
        "grade": session["grade"],
        "subject": session["subject"],
        "topic": session["topic"],
        "level": session["level"],
        "syllabus": syllabus,
        "progress": progress,
    }


@app.get("/api/sessions/{session_id}/progress")
def get_session_progress(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    progress = get_progress(session_id)
    return {"session_id": session_id, "progress": progress}


@app.post("/api/lessons")
async def get_lesson(req: LessonRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")

    grade, subject, topic, level, goals = session["grade"], session["subject"], session["topic"], session["level"], session.get("goals", "")

    content_hash = compute_content_hash(grade, subject, topic, level, goals)

    cached = get_cached_lesson_by_content(content_hash, req.module_index)
    if cached:
        return cached

    cached = get_cached_lesson(req.session_id, req.module_index)
    if cached:
        return cached

    # Fallback: try to find a lesson from any other session with same params (pre-content_hash sessions)
    cached = find_cached_lesson_by_params(grade, subject, topic, level, goals, req.module_index)
    if cached:
        save_lesson_to_cache(content_hash, req.module_index, json.dumps(cached))
        return cached

    try:
        lesson = await generate_lesson(session["grade"], session["subject"], session["topic"], session["level"], req.module_title, session.get("goals", ""))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل في إنشاء الدرس: {e}")
    lesson = await resolve_images(lesson)
    lesson_json = json.dumps(lesson)
    save_lesson_to_cache(content_hash, req.module_index, lesson_json)
    save_lesson(req.session_id, req.module_index, lesson_json)
    return lesson


@app.post("/api/quiz")
async def get_quiz(req: QuizRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="الجلسة غير موجودة")
    try:
        quiz = await generate_quiz(session["topic"], session["level"], req.lesson_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل في إنشاء الاختبار: {e}")
    return quiz


@app.post("/api/evaluate")
async def submit_quiz(req: SubmitRequest):
    try:
        result = await evaluate_answers(req.questions, req.user_answers, req.correct_answers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل في التقييم: {e}")

    score = result.get("score", 0)
    complete_module(req.session_id, req.module_index, score)
    save_quiz_attempt(
        req.session_id,
        req.module_index,
        json.dumps(req.questions),
        json.dumps(req.user_answers),
        score,
        result.get("feedback", ""),
    )

    return result


class TTSRequest(BaseModel):
    text: str


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    try:
        import edge_tts
        communicate = edge_tts.Communicate(req.text, "ar-SA-ZariyahNeural")
        audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        from fastapi.responses import Response
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل في تحويل النص إلى صوت: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", reload=True, port=8000)
