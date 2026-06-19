import json
import os
import re
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=4096)

planner = LlmAgent(
    name="PlannerAgent",
    model=MODEL,
    instruction=(
        "أنت خبير في تصميم المناهج التعليمية. بناءً على الصف والمادة والموضوع ومستوى المتعلم "
        "(مبتدئ، متوسط، متقدم) وأهدافه، قم بإنشاء منهج تعليمي منظم.\n\n"
        "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
        "{\n"
        '  "topic": "<الموضوع>",\n'
        '  "level": "<المستوى>",\n'
        '  "modules": [\n'
        "    {\n"
        '      "title": "<عنوان الوحدة>",\n'
        '      "description": "<وصف مختصر لما تغطيه هذه الوحدة>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "قم بإنشاء 4 وحدات تتقدم منطقيًا من الأساسيات إلى المفاهيم المتقدمة. "
        "يجب أن يكون كل المحتوى باللغة العربية."
    ),
    output_key="syllabus_json",
    generate_content_config=config,
)

content_creator = LlmAgent(
    name="ContentAgent",
    model=MODEL,
    instruction=(
        "أنت معلم خبير. بناءً على الصف والمادة والموضوع ومستوى المتعلم وعنوان الوحدة وأهدافه، "
        "قم بإنشاء محتوى درس جذاب.\n\n"
        "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
        "{\n"
        '  "title": "<عنوان الوحدة>",\n'
        '  "content": "<محتوى الدرس المفصل مع أقسام مفصولة بالعنوان ## عنوان القسم>",\n'
        '  "key_points": ["<نقطة 1>", "<نقطة 2>", "<نقطة 3>"],\n'
        '  "examples": ["<مثال 1>", "<مثال 2>"],\n'
        '  "sections_images": {"<عنوان القسم>": "<search query in English for image>"}\n'
        "}\n\n"
        "قسّم المحتوى إلى 3-5 أقسام. ابدأ كل قسم بـ ## متبوعة بعنوان القسم في سطر منفصل. "
        "إذا احتوى المحتوى على بيانات جدولية، استخدم تنسيق جدول ماركdown: "
        "أسطر تبدأ بـ | وتنتهي بـ |، والصف الأول رأس، والصف الثاني فاصل (|---|---|)، وباقي الأسطر بيانات. "
        "أضف مدخلات في sections_images فقط للقوائم التي تحتاج صورة توضيحية (مثل الرسوم البيانية أو المخططات أو الصور العلمية). "
        "استخدم عبارة بحث باللغة الإنجليزية مختصرة (مثل: solar system diagram، water cycle illustration). "
        "اجعل المحتوى شاملاً ومناسبًا للمستوى المحدد. قم بتضمين أمثلة عملية. "
        "يجب أن يكون كل المحتوى باللغة العربية."
    ),
    output_key="lesson_json",
    generate_content_config=config,
)

quiz_generator = LlmAgent(
    name="QuizAgent",
    model=MODEL,
    instruction=(
        "أنت منشئ اختبارات. بناءً على الموضوع والمستوى ومحتوى الدرس، "
        "قم بإنشاء أسئلة اختيار من متعدد لاختبار الفهم.\n\n"
        "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "id": 1,\n'
        '      "question": "<نص السؤال>",\n'
        '      "options": ["<أ. الخيار>", "<ب. الخيار>", "<ج. الخيار>", "<د. الخيار>"],\n'
        '      "correct_answer": 0,\n'
        '      "explanation": "<لماذا هذه الإجابة صحيحة>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "قم بإنشاء 4 أسئلة. correct_answer هو الفهرس (يبدأ من 0) للخيار الصحيح. "
        "نوّع مستويات الصعوبة بشكل مناسب. يجب أن يكون كل المحتوى باللغة العربية."
    ),
    output_key="quiz_json",
    generate_content_config=config,
)

evaluator = LlmAgent(
    name="EvaluatorAgent",
    model=MODEL,
    instruction=(
        "أنت مقيم تعليمي. بناءً على أسئلة الاختبار وإجابات المستخدم والإجابات الصحيحة، "
        "قم بتقييم الأداء وتقديم ملاحظات بناءة.\n\n"
        "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
        "{\n"
        '  "score": <رقم بين 0 و 100>,\n'
        '  "total_questions": <عدد>,\n'
        '  "correct_count": <عدد>,\n'
        '  "feedback": "<ملاحظات عامة عن الأداء>",\n'
        '  "weak_areas": ["<مجال للتحسين 1>", "<مجال للتحسين 2>"],\n'
        '  "next_steps": "<توصية بما يجب دراسته بعد ذلك>"\n'
        "}\n\n"
        "كن مشجعًا ولكن صادقًا. اقترح مجالات محددة للتحسين. "
        "يجب أن يكون كل المحتوى باللغة العربية."
    ),
    output_key="evaluation_json",
    generate_content_config=config,
)

learning_pipeline = SequentialAgent(
    name="LearningPipeline",
    sub_agents=[planner, content_creator, quiz_generator, evaluator],
)

PLANNER_RUNNER = InMemoryRunner(agent=planner, app_name="learning_app")
CONTENT_RUNNER = InMemoryRunner(agent=content_creator, app_name="learning_app")
QUIZ_RUNNER = InMemoryRunner(agent=quiz_generator, app_name="learning_app")
EVAL_RUNNER = InMemoryRunner(agent=evaluator, app_name="learning_app")
PIPELINE_RUNNER = InMemoryRunner(agent=learning_pipeline, app_name="learning_pipeline")


async def _run_agent(runner: InMemoryRunner, prompt: str) -> str | None:
    events = await runner.run_debug(
        user_messages=prompt,
        user_id="api_user",
        session_id="api_session",
    )
    for event in reversed(events):
        if event.content and event.content.parts:
            text = "".join(p.text for p in event.content.parts if p.text)
            if text:
                return text.strip()
    return None


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    text = text.strip()
    text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text


async def _generate_json(runner: InMemoryRunner, prompt: str, retry_hint: str = "") -> dict:
    for attempt in range(2):
        raw = await _run_agent(runner, prompt)
        if not raw:
            raise ValueError("الوكيل لم يُرجع أي مخرجات")
        try:
            return json.loads(_clean_json(raw), strict=False)
        except json.JSONDecodeError as e:
            if attempt == 0 and retry_hint:
                prompt += "\n\n" + retry_hint
            else:
                raise


async def generate_syllabus(grade: str, subject: str, topic: str, level: str, goals: str = "") -> dict:
    prompt = f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nمستوى المتعلم: {level}\n"
    if goals:
        prompt += f"أهداف المتعلم: {goals}\n"
    prompt += "\nقم بإنشاء منهج تعليمي."
    return await _generate_json(PLANNER_RUNNER, prompt,
        "تأكد من أن المخرجات JSON صالح تمامًا بدون أي علامات تنصيص غير مهربة.")


async def generate_lesson(grade: str, subject: str, topic: str, level: str, module_title: str, goals: str = "") -> dict:
    prompt = (
        f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nمستوى المتعلم: {level}\n"
        f"عنوان الوحدة: {module_title}\n"
    )
    if goals:
        prompt += f"أهداف المتعلم: {goals}\n"
    prompt += "\nقم بإنشاء محتوى درس لهذه الوحدة."
    return await _generate_json(CONTENT_RUNNER, prompt,
        "تأكد من أن الـ JSON صحيح تمامًا. استخدم \\\" داخل النصوص عند الحاجة. لا تترك علامات اقتباس غير مهربة في المحتوى.")


async def generate_quiz(topic: str, level: str, lesson_content: str) -> dict:
    prompt = (
        f"الموضوع: {topic}\nمستوى المتعلم: {level}\n"
        f"محتوى الدرس:\n{lesson_content}\n\nقم بإنشاء أسئلة اختبار."
    )
    return await _generate_json(QUIZ_RUNNER, prompt,
        "تأكد من أن JSON صالح تمامًا بدون أخطاء.")


async def evaluate_answers(questions: list, user_answers: list, correct_answers: list) -> dict:
    prompt = (
        f"الأسئلة: {json.dumps(questions)}\n"
        f"إجابات المستخدم: {json.dumps(user_answers)}\n"
        f"الإجابات الصحيحة: {json.dumps(correct_answers)}\n\nقم بتقييم أداء المستخدم."
    )
    return await _generate_json(EVAL_RUNNER, prompt,
        "تأكد من أن JSON صالح تمامًا بدون أخطاء.")
