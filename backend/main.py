import json
import os
import sys
import time

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
from fastapi.responses import StreamingResponse
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
    check_content_quality,
)
from logger import LessonLogger, extract_lesson_stats, extract_quiz_stats

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

TTS_VOICES = {
    "ar": "ar-SA-ZariyahNeural",
    "en": "en-US-AriaNeural",
}

TTS_ERROR_MESSAGES = {
    "ar": "فشل في تحويل النص إلى صوت",
    "en": "Failed to convert text to speech",
}

API_ERROR_MESSAGES = {
    "ar": {
        "session_not_found": "الجلسة غير موجودة",
        "syllabus_failed": "فشل في إنشاء المنهج",
        "lesson_failed": "فشل في إنشاء الدرس",
        "quiz_failed": "فشل في إنشاء الاختبار",
        "eval_failed": "فشل في التقييم",
    },
    "en": {
        "session_not_found": "Session not found",
        "syllabus_failed": "Failed to generate syllabus",
        "lesson_failed": "Failed to generate lesson",
        "quiz_failed": "Failed to generate quiz",
        "eval_failed": "Failed to evaluate answers",
    },
}


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "message": "AI Learning Agent API"}


class StartRequest(BaseModel):
    grade: str
    subject: str
    topic: str
    level: str
    goals: str = ""
    language: str = "ar"
    curriculum: str = ""


class LessonRequest(BaseModel):
    session_id: str
    module_index: int
    module_title: str
    language: str = "ar"


class QuizRequest(BaseModel):
    session_id: str
    module_index: int
    module_title: str
    lesson_content: str
    language: str = "ar"


class SubmitRequest(BaseModel):
    session_id: str
    module_index: int
    questions: list
    user_answers: list
    correct_answers: list
    language: str = "ar"
    retry_count: int = 0


@app.on_event("startup")
def startup():
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("Warning: GEMINI_API_KEY not set in backend/.env")
        print("   Get a key from: https://aistudio.google.com/apikey")
    init_db()


@app.post("/api/sessions")
async def start_learning(req: StartRequest):
    lang = req.language if req.language in ("ar", "en") else "ar"
    msgs = API_ERROR_MESSAGES[lang]
    session_id = str(uuid.uuid4())[:8]
    content_hash = compute_content_hash(req.grade, req.subject, req.topic, req.level, req.goals, lang, req.curriculum)

    existing = find_syllabus_by_content_hash(content_hash, req.grade, req.subject, req.topic, req.level, req.goals, lang, req.curriculum)
    if existing:
        syllabus = existing
    else:
        try:
            syllabus = await generate_syllabus(req.grade, req.subject, req.topic, req.level, req.goals, lang, req.curriculum)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"{msgs['syllabus_failed']}: {e}")

    create_session(session_id, req.grade, req.subject, req.topic, req.level, req.goals, json.dumps(syllabus), content_hash, lang, req.curriculum)
    init_progress(session_id, syllabus.get("modules", []))

    return {
        "session_id": session_id,
        "grade": req.grade,
        "subject": req.subject,
        "topic": req.topic,
        "level": req.level,
        "goals": req.goals,
        "language": lang,
        "curriculum": req.curriculum,
        "syllabus": syllabus,
    }


@app.get("/api/sessions/{session_id}")
def get_session_info(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    syllabus = json.loads(session["syllabus"]) if session["syllabus"] else None
    progress = get_progress(session_id)
    return {
        "session_id": session["id"],
        "grade": session["grade"],
        "subject": session["subject"],
        "topic": session["topic"],
        "level": session["level"],
        "language": session.get("language", "ar"),
        "curriculum": session.get("curriculum", ""),
        "syllabus": syllabus,
        "progress": progress,
    }


@app.get("/api/sessions/{session_id}/progress")
def get_session_progress(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    progress = get_progress(session_id)
    return {"session_id": session_id, "progress": progress}


@app.post("/api/lessons")
async def get_lesson(req: LessonRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    lang = session.get("language", "ar")
    msgs = API_ERROR_MESSAGES[lang]
    grade, subject, topic, level, goals = session["grade"], session["subject"], session["topic"], session["level"], session.get("goals", "")
    curriculum = session.get("curriculum", "")

    syllabus = json.loads(session["syllabus"]) if session["syllabus"] else {}
    modules = syllabus.get("modules", [])
    module_data = modules[req.module_index] if req.module_index < len(modules) else {}
    module_description = module_data.get("description", "")
    learning_outcomes = module_data.get("learning_outcomes", [])

    log = LessonLogger(
        session_id=req.session_id,
        module_index=req.module_index,
        module_title=req.module_title,
        request_params={"grade": grade, "subject": subject, "topic": topic, "level": level, "language": lang, "curriculum": curriculum, "goals": goals},
    )

    content_hash = compute_content_hash(grade, subject, topic, level, goals, lang, curriculum)

    cached = get_cached_lesson_by_content(content_hash, req.module_index)
    if cached:
        log.set_final_result(status="cached_from_content_hash")
        log.save()
        return cached

    cached = get_cached_lesson(req.session_id, req.module_index)
    if cached:
        log.set_final_result(status="cached_from_session")
        log.save()
        return cached

    cached = find_cached_lesson_by_params(grade, subject, topic, level, goals, req.module_index, lang, curriculum)
    if cached:
        save_lesson_to_cache(content_hash, req.module_index, json.dumps(cached))
        log.set_final_result(status="cached_from_params")
        log.save()
        return cached

    try:
        lesson = await generate_lesson(session["grade"], session["subject"], session["topic"], session["level"], req.module_title, session.get("goals", ""), lang, curriculum, logger=log, module_description=module_description, learning_outcomes=learning_outcomes)
    except Exception as e:
        log.set_final_result(status="error", word_count=0)
        log.save()
        raise HTTPException(status_code=500, detail=f"{msgs['lesson_failed']}: {e}")

    quality = await check_content_quality(lesson, "lesson", lang, logger=log)
    if not quality.get("is_approved", True):
        issues = quality.get("issues", [])
        suggestions = quality.get("suggestions", [])
        retry_feedback = (
            f"Quality issues found:\n" + "\n".join(f"- {i}" for i in issues)
            + f"\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in suggestions)
        ) if lang == "en" else (
            f"مشاكل في جودة المحتوى:\n" + "\n".join(f"- {i}" for i in issues)
            + f"\n\nاقتراحات للتحسين:\n" + "\n".join(f"- {s}" for s in suggestions)
        )
        try:
            lesson = await generate_lesson(
                session["grade"], session["subject"], session["topic"], session["level"],
                req.module_title, session.get("goals", ""), lang, curriculum, logger=log,
                quality_feedback=retry_feedback, module_description=module_description,
                learning_outcomes=learning_outcomes
            )
        except Exception:
            pass

    t_start = time.time()
    lesson = await resolve_images(lesson)
    t_images = int((time.time() - t_start) * 1000)

    lesson_json = json.dumps(lesson)
    save_lesson_to_cache(content_hash, req.module_index, lesson_json)
    save_lesson(req.session_id, req.module_index, lesson_json)

    stats = extract_lesson_stats(lesson)
    log.set_final_result(status="success", **stats)
    log.save()
    return lesson


@app.post("/api/quiz")
async def get_quiz(req: QuizRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    lang = session.get("language", "ar")
    msgs = API_ERROR_MESSAGES[lang]
    curriculum = session.get("curriculum", "")

    log = LessonLogger(
        session_id=req.session_id,
        module_index=req.module_index,
        module_title=req.module_title,
        request_params={"topic": session["topic"], "level": session["level"], "language": lang, "curriculum": curriculum},
    )

    try:
        quiz = await generate_quiz(session["topic"], session["level"], req.lesson_content, lang, curriculum, logger=log)
    except Exception as e:
        log.set_final_result(status="error")
        log.save()
        raise HTTPException(status_code=500, detail=f"{msgs['quiz_failed']}: {e}")

    quality = await check_content_quality(quiz, "quiz", lang, logger=log)
    if not quality.get("is_approved", True):
        issues = quality.get("issues", [])
        suggestions = quality.get("suggestions", [])
        retry_feedback = (
            f"Quality issues found:\n" + "\n".join(f"- {i}" for i in issues)
            + f"\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in suggestions)
        ) if lang == "en" else (
            f"مشاكل في جودة المحتوى:\n" + "\n".join(f"- {i}" for i in issues)
            + f"\n\nاقتراحات للتحسين:\n" + "\n".join(f"- {s}" for s in suggestions)
        )
        try:
            quiz = await generate_quiz(session["topic"], session["level"], req.lesson_content, lang, curriculum, logger=log, quality_feedback=retry_feedback)
        except Exception:
            pass

    stats = extract_quiz_stats(quiz)
    log.set_final_result(status="success", **stats)
    log.save()
    return quiz


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/lessons/stream")
async def stream_lesson(req: LessonRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    lang = session.get("language", "ar")
    msgs = API_ERROR_MESSAGES[lang]
    grade, subject, topic, level, goals = session["grade"], session["subject"], session["topic"], session["level"], session.get("goals", "")
    curriculum = session.get("curriculum", "")

    syllabus = json.loads(session["syllabus"]) if session["syllabus"] else {}
    modules = syllabus.get("modules", [])
    module_data = modules[req.module_index] if req.module_index < len(modules) else {}
    module_description = module_data.get("description", "")
    learning_outcomes = module_data.get("learning_outcomes", [])

    log = LessonLogger(
        session_id=req.session_id,
        module_index=req.module_index,
        module_title=req.module_title,
        request_params={"grade": grade, "subject": subject, "topic": topic, "level": level, "language": lang, "curriculum": curriculum, "goals": goals},
    )

    content_hash = compute_content_hash(grade, subject, topic, level, goals, lang, curriculum)

    cached = get_cached_lesson_by_content(content_hash, req.module_index)
    if cached:
        log.set_final_result(status="cached_from_content_hash")
        log.save()
        async def cached_response():
            yield _sse_event("lesson_ready", {"lesson": cached, "learning_outcomes": learning_outcomes})
        return StreamingResponse(cached_response(), media_type="text/event-stream")

    cached = get_cached_lesson(req.session_id, req.module_index)
    if cached:
        log.set_final_result(status="cached_from_session")
        log.save()
        async def cached_response2():
            yield _sse_event("lesson_ready", {"lesson": cached, "learning_outcomes": learning_outcomes})
        return StreamingResponse(cached_response2(), media_type="text/event-stream")

    cached = find_cached_lesson_by_params(grade, subject, topic, level, goals, req.module_index, lang, curriculum)
    if cached:
        save_lesson_to_cache(content_hash, req.module_index, json.dumps(cached))
        log.set_final_result(status="cached_from_params")
        log.save()
        async def cached_response3():
            yield _sse_event("lesson_ready", {"lesson": cached, "learning_outcomes": learning_outcomes})
        return StreamingResponse(cached_response3(), media_type="text/event-stream")

    async def generate_stream():
        yield _sse_event("pipeline_started", {
            "learning_outcomes": learning_outcomes,
            "module_description": module_description,
            "module_title": req.module_title,
            "steps": ["content", "validator", "quality"],
        })

        yield _sse_event("agent_started", {
            "agent": "ContentAgent",
            "step": "content",
            "message": "Generating lesson content..." if lang == "en" else "جاري إنشاء محتوى الدرس...",
        })

        try:
            lesson = await generate_lesson(session["grade"], session["subject"], session["topic"], session["level"], req.module_title, session.get("goals", ""), lang, curriculum, logger=log, module_description=module_description, learning_outcomes=learning_outcomes)
        except Exception as e:
            log.set_final_result(status="error", word_count=0)
            log.save()
            yield _sse_event("error", {"message": f"{msgs['lesson_failed']}: {e}"})
            return

        yield _sse_event("agent_completed", {
            "agent": "ContentAgent",
            "step": "content",
            "result": "success",
        })

        yield _sse_event("agent_started", {
            "agent": "ValidatorAgent",
            "step": "validator",
            "message": "Validating curriculum alignment..." if lang == "en" else "جاري التحقق من توافق المنهج...",
        })

        quality = await check_content_quality(lesson, "lesson", lang, logger=log)
        quality_criteria = quality.get("criteria", {})
        quality_score = quality.get("overall_score", 80)
        quality_approved = quality.get("is_approved", True)

        yield _sse_event("agent_completed", {
            "agent": "QualityAgent",
            "step": "quality",
            "result": "approved" if quality_approved else "rejected",
            "score": quality_score,
            "criteria": quality_criteria,
            "issues": quality.get("issues", []),
            "suggestions": quality.get("suggestions", []),
        })

        if not quality_approved:
            issues = quality.get("issues", [])
            suggestions = quality.get("suggestions", [])
            retry_feedback = (
                f"Quality issues found:\n" + "\n".join(f"- {i}" for i in issues)
                + f"\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in suggestions)
            ) if lang == "en" else (
                f"مشاكل في جودة المحتوى:\n" + "\n".join(f"- {i}" for i in issues)
                + f"\n\nاقتراحات للتحسين:\n" + "\n".join(f"- {s}" for s in suggestions)
            )
            try:
                lesson = await generate_lesson(
                    session["grade"], session["subject"], session["topic"], session["level"],
                    req.module_title, session.get("goals", ""), lang, curriculum, logger=log,
                    quality_feedback=retry_feedback, module_description=module_description,
                    learning_outcomes=learning_outcomes
                )
                yield _sse_event("agent_started", {
                    "agent": "ContentAgent",
                    "step": "content_retry",
                    "message": "Regenerating content based on quality feedback..." if lang == "en" else "جاري إعادة إنشاء المحتوى بناءً على ملاحظات الجودة...",
                })
                yield _sse_event("agent_completed", {
                    "agent": "ContentAgent",
                    "step": "content_retry",
                    "result": "success",
                })
            except Exception:
                pass

        t_start = time.time()
        lesson = await resolve_images(lesson)
        t_images = int((time.time() - t_start) * 1000)

        lesson_json = json.dumps(lesson)
        save_lesson_to_cache(content_hash, req.module_index, lesson_json)
        save_lesson(req.session_id, req.module_index, lesson_json)

        stats = extract_lesson_stats(lesson)
        log.set_final_result(status="success", **stats)
        log.save()

        yield _sse_event("lesson_ready", {"lesson": lesson, "learning_outcomes": learning_outcomes})

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


@app.post("/api/quiz/stream")
async def stream_quiz(req: QuizRequest):
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    lang = session.get("language", "ar")
    msgs = API_ERROR_MESSAGES[lang]
    curriculum = session.get("curriculum", "")

    log = LessonLogger(
        session_id=req.session_id,
        module_index=req.module_index,
        module_title=req.module_title,
        request_params={"topic": session["topic"], "level": session["level"], "language": lang, "curriculum": curriculum},
    )

    async def generate_stream():
        yield _sse_event("pipeline_started", {
            "learning_outcomes": [],
            "module_title": req.module_title,
            "steps": ["quiz", "quality"],
        })

        yield _sse_event("agent_started", {
            "agent": "QuizAgent",
            "step": "quiz",
            "message": "Creating quiz questions..." if lang == "en" else "جاري إنشاء أسئلة الاختبار...",
        })

        try:
            quiz = await generate_quiz(session["topic"], session["level"], req.lesson_content, lang, curriculum, logger=log)
        except Exception as e:
            log.set_final_result(status="error")
            log.save()
            yield _sse_event("error", {"message": f"{msgs['quiz_failed']}: {e}"})
            return

        yield _sse_event("agent_completed", {
            "agent": "QuizAgent",
            "step": "quiz",
            "result": "success",
        })

        yield _sse_event("agent_started", {
            "agent": "QualityAgent",
            "step": "quality",
            "message": "Checking quiz quality..." if lang == "en" else "جاري فحص جودة الأسئلة...",
        })

        quality = await check_content_quality(quiz, "quiz", lang, logger=log)
        quality_criteria = quality.get("criteria", {})
        quality_score = quality.get("overall_score", 80)
        quality_approved = quality.get("is_approved", True)

        yield _sse_event("agent_completed", {
            "agent": "QualityAgent",
            "step": "quality",
            "result": "approved" if quality_approved else "rejected",
            "score": quality_score,
            "criteria": quality_criteria,
            "issues": quality.get("issues", []),
            "suggestions": quality.get("suggestions", []),
        })

        if not quality_approved:
            issues = quality.get("issues", [])
            suggestions = quality.get("suggestions", [])
            retry_feedback = (
                f"Quality issues found:\n" + "\n".join(f"- {i}" for i in issues)
                + f"\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in suggestions)
            ) if lang == "en" else (
                f"مشاكل في جودة المحتوى:\n" + "\n".join(f"- {i}" for i in issues)
                + f"\n\nاقتراحات للتحسين:\n" + "\n".join(f"- {s}" for s in suggestions)
            )
            try:
                quiz = await generate_quiz(session["topic"], session["level"], req.lesson_content, lang, curriculum, logger=log, quality_feedback=retry_feedback)
                yield _sse_event("agent_started", {
                    "agent": "QuizAgent",
                    "step": "quiz_retry",
                    "message": "Regenerating quiz based on quality feedback..." if lang == "en" else "جاري إعادة إنشاء الاختبار بناءً على ملاحظات الجودة...",
                })
                yield _sse_event("agent_completed", {
                    "agent": "QuizAgent",
                    "step": "quiz_retry",
                    "result": "success",
                })
            except Exception:
                pass

        stats = extract_quiz_stats(quiz)
        log.set_final_result(status="success", **stats)
        log.save()

        yield _sse_event("quiz_ready", {"quiz": quiz})

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


@app.post("/api/evaluate")
async def submit_quiz(req: SubmitRequest):
    lang = req.language if req.language in ("ar", "en") else "ar"
    msgs = API_ERROR_MESSAGES[lang]
    try:
        result = await evaluate_answers(req.questions, req.user_answers, req.correct_answers, lang)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{msgs['eval_failed']}: {e}")

    score = result.get("score", 0)
    complete_module(req.session_id, req.module_index, score)
    save_quiz_attempt(
        req.session_id,
        req.module_index,
        json.dumps(req.questions),
        json.dumps(req.user_answers),
        score,
        result.get("feedback", ""),
        req.retry_count,
    )

    return result


class TTSRequest(BaseModel):
    text: str
    language: str = "ar"


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    lang = req.language if req.language in ("ar", "en") else "ar"
    voice = TTS_VOICES[lang]
    try:
        import edge_tts
        communicate = edge_tts.Communicate(req.text, voice)
        audio = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        from fastapi.responses import Response
        return Response(content=audio, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{TTS_ERROR_MESSAGES[lang]}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", reload=True, port=8000)
