import json
import time
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class LessonLogger:
    def __init__(self, session_id: str, module_index: int, module_title: str, request_params: dict):
        self.session_id = session_id
        self.module_index = module_index
        self.module_title = module_title
        self.request_params = request_params
        self.pipeline = []
        self.final_result = {}
        self.start_time = time.time()
        self._current_step = None
        self._step_start = None

    def begin_agent_call(self, agent_name: str, step: str, prompt: str, attempt: int = 1, reason: str = ""):
        self._current_step = {
            "agent": agent_name,
            "step": step,
            "attempt": attempt,
            "reason": reason,
            "prompt_sent": prompt,
            "raw_response": "",
            "cleaned_response": "",
            "parsed_json": None,
            "json_parse_status": "pending",
            "error": None,
            "duration_ms": 0,
        }
        self._step_start = time.time()

    def set_raw_response(self, raw: str):
        if self._current_step:
            self._current_step["raw_response"] = raw

    def set_cleaned_response(self, cleaned: str):
        if self._current_step:
            self._current_step["cleaned_response"] = cleaned

    def set_parsed_json(self, parsed: dict):
        if self._current_step:
            self._current_step["parsed_json"] = parsed
            self._current_step["json_parse_status"] = "success"

    def set_error(self, error: str):
        if self._current_step:
            self._current_step["error"] = error
            self._current_step["json_parse_status"] = "failed"

    def end_agent_call(self):
        if self._current_step and self._step_start:
            self._current_step["duration_ms"] = int((time.time() - self._step_start) * 1000)
            self.pipeline.append(self._current_step)
            self._current_step = None
            self._step_start = None

    def log_image_resolve(self, resolved: int, failed: int, duration_ms: int):
        self.pipeline.append({
            "agent": "Unsplash",
            "step": "resolve_images",
            "images_resolved": resolved,
            "images_failed": failed,
            "duration_ms": duration_ms,
        })

    def set_final_result(self, status: str, word_count: int = 0, sections_count: int = 0,
                         key_points_count: int = 0, examples_count: int = 0, questions_count: int = 0):
        self.final_result = {
            "status": status,
            "word_count": word_count,
            "sections_count": sections_count,
            "key_points_count": key_points_count,
            "examples_count": examples_count,
            "questions_count": questions_count,
        }

    def save(self):
        total_ms = int((time.time() - self.start_time) * 1000)
        log_data = {
            "session_id": self.session_id,
            "module_index": self.module_index,
            "module_title": self.module_title,
            "timestamp": datetime.now().isoformat(),
            "request_params": self.request_params,
            "pipeline": self.pipeline,
            "final_result": self.final_result,
            "total_duration_ms": total_ms,
        }
        filename = f"lesson_{self.session_id}_{self.module_index}_{int(self.start_time)}.json"
        filepath = LOGS_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        return str(filepath)


def count_words(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def extract_lesson_stats(lesson: dict) -> dict:
    content = lesson.get("content", "")
    key_points = lesson.get("key_points", [])
    examples = lesson.get("examples", [])
    sections = [s for s in content.split("## ") if s.strip()] if content else []
    return {
        "word_count": count_words(content),
        "sections_count": len(sections),
        "key_points_count": len(key_points),
        "examples_count": len(examples),
    }


def extract_quiz_stats(quiz: dict) -> dict:
    questions = quiz.get("questions", [])
    return {
        "questions_count": len(questions),
    }
