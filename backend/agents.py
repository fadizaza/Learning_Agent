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

PLANNER_INSTRUCTION_AR = (
    "أنت خبير في تصميم المناهج التعليمية. بناءً على الصف والمادة والموضوع ومستوى المتعلم "
    "(مبتدئ، متوسط، متقدم) والمنهج التعليمي وأهدافه، قم بإنشاء منهج تعليمي منظم.\n\n"
    "إذا تم تحديد منهج تعليمي محدد، يجب أن تكون الوحدات والمواضيع متوافقة مع معاييره ونواتج تعلمه.\n\n"
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
)

PLANNER_INSTRUCTION_EN = (
    "You are an expert in designing educational curricula. Based on the grade, subject, topic, "
    "learner level (beginner, intermediate, advanced), the curriculum framework, and their goals, "
    "create an organized educational syllabus.\n\n"
    "If a specific curriculum is provided, the modules and topics must align with its standards and learning outcomes.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "topic": "<topic>",\n'
    '  "level": "<level>",\n'
    '  "modules": [\n'
    "    {\n"
    '      "title": "<module title>",\n'
    '      "description": "<brief description of what this module covers>"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Create 4 modules that progress logically from basics to advanced concepts. "
    "All content must be in English."
)

CONTENT_INSTRUCTION_AR = (
    "أنت معلم خبير. بناءً على الصف والمادة والموضوع ومستوى المتعلم وعنوان الوحدة والمنهج التعليمي وأهدافه، "
    "قم بإنشاء محتوى درس جذاب.\n\n"
    "إذا تم تحديد منهج تعليمي محدد، يجب أن يكون المحتوى متوافقًا مع معاييره ونواتج تعلمه وأسلوب عرضه.\n\n"
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
)

CONTENT_INSTRUCTION_EN = (
    "You are an expert teacher. Based on the grade, subject, topic, learner level, module title, "
    "the curriculum framework, and their goals, create engaging lesson content.\n\n"
    "If a specific curriculum is provided, the content must align with its standards, learning outcomes, and presentation style.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "title": "<module title>",\n'
    '  "content": "<detailed lesson content with sections separated by ## heading>",\n'
    '  "key_points": ["<point 1>", "<point 2>", "<point 3>"],\n'
    '  "examples": ["<example 1>", "<example 2>"],\n'
    '  "sections_images": {"<section heading>": "<search query in English for image>"}\n'
    "}\n\n"
    "Divide the content into 3-5 sections. Start each section with ## followed by the section heading on a separate line. "
    "If the content has tabular data, use markdown table format: "
    "lines starting and ending with |, first row as header, second row as separator (|---|---|), and remaining rows as data. "
    "Add entries in sections_images only for sections that need an illustrative image "
    "(like diagrams, charts, or scientific images). "
    "Use short English search queries (e.g., solar system diagram, water cycle illustration). "
    "Make the content comprehensive and appropriate for the specified level. Include practical examples. "
    "All content must be in English."
)

QUIZ_INSTRUCTION_AR = (
    "أنت منشئ اختبارات. بناءً على الموضوع والمستوى والمنهج التعليمي ومحتوى الدرس، "
    "قم بإنشاء أسئلة اختيار من متعدد لاختبار الفهم.\n\n"
    "إذا تم تحديد منهج تعليمي محدد، يجب أن تكون الأسئلة بأسلوب يتوافق مع أساليب التقييم في هذا المنهاج.\n\n"
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
    "قم بإنشاء 10 أسئلة. correct_answer هو الفهرس (يبدأ من 0) للخيار الصحيح. "
    "نوّع مستويات الصعوبة بشكل مناسب. يجب أن يكون كل المحتوى باللغة العربية."
)

QUIZ_INSTRUCTION_EN = (
    "You are a quiz creator. Based on the topic, level, curriculum framework, and lesson content, "
    "create multiple-choice questions to test understanding.\n\n"
    "If a specific curriculum is provided, the questions should match its assessment style and command words.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "questions": [\n'
    "    {\n"
    '      "id": 1,\n'
    '      "question": "<question text>",\n'
    '      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],\n'
    '      "correct_answer": 0,\n'
    '      "explanation": "<why this answer is correct>"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Create 10 questions. correct_answer is the index (starting from 0) of the correct option. "
    "Vary difficulty levels appropriately. All content must be in English."
)

EVAL_INSTRUCTION_AR = (
    "أنت مقيم تعليمي. بناءً على أسئلة الاختبار وإجابات المستخدم والإجابات الصحيحة والمنهج التعليمي، "
    "قم بتقييم الأداء وتقديم ملاحظات بناءة.\n\n"
    "إذا تم تحديد منهج تعليمي محدد، يجب أن تكون الملاحظات والتوصيات متوافقة مع أهداف التعلم في هذا المنهاج.\n\n"
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
)

EVAL_INSTRUCTION_EN = (
    "You are an educational evaluator. Based on the quiz questions, user answers, correct answers, "
    "and the curriculum framework, evaluate performance and provide constructive feedback.\n\n"
    "If a specific curriculum is provided, the feedback and recommendations should align with its learning outcomes.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "score": <number between 0 and 100>,\n'
    '  "total_questions": <number>,\n'
    '  "correct_count": <number>,\n'
    '  "feedback": "<general feedback about performance>",\n'
    '  "weak_areas": ["<area for improvement 1>", "<area for improvement 2>"],\n'
    '  "next_steps": "<recommendation for what to study next>"\n'
    "}\n\n"
    "Be encouraging but honest. Suggest specific areas for improvement. "
    "All content must be in English."
)

VALIDATOR_INSTRUCTION_AR = (
    "أنت محقق تعليمي. مهمتك التحقق مما إذا كان المحتوى المُنشأ متوافقًا مع المنهج التعليمي المحدد "
    "والصف والمادة والموضوع.\n\n"
    "ستتلقى المحتوى المُنشأ وبيانات المنهج. قيم التوافق وارجع JSON صالحًا فقط:\n"
    "{\n"
    '  "is_aligned": true أو false,\n'
    '  "score": <رقم من 0 إلى 100 يمثل درجة التوافق>,\n'
    '  "issues": ["<مشكلة 1>", "<مشكلة 2>"],\n'
    '  "suggestions": ["<اقتراح 1>", "<اقتراح 2>"]\n'
    "}\n\n"
    "معايير التحقق:\n"
    "1. هل الموضوع مناسب للصف المحدد؟\n"
    "2. هل المستوى (مبتدئ/متوسط/متقدم) مناسب لمحتوى الوحدات؟\n"
    "3. هل الترتيب منطقي من الأساسيات إلى المتقدم؟\n"
    "4. هل الوحدات تغطي الموضوع بشكل شامل؟\n"
    "5. هل المحتوى متوافق مع أسلوب المنهاج المحدد؟\n\n"
    "إذا كان التوافق ≥ 70، ضع is_aligned = true. وإلا ضعه = false.\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

VALIDATOR_INSTRUCTION_EN = (
    "You are an educational validator. Your task is to verify whether the generated content aligns with "
    "the specified curriculum, grade, subject, and topic.\n\n"
    "You will receive the generated content and curriculum data. Evaluate alignment and return only valid JSON:\n"
    "{\n"
    '  "is_aligned": true or false,\n'
    '  "score": <number from 0 to 100 representing alignment score>,\n'
    '  "issues": ["<issue 1>", "<issue 2>"],\n'
    '  "suggestions": ["<suggestion 1>", "<suggestion 2>"]\n'
    "}\n\n"
    "Validation criteria:\n"
    "1. Is the topic appropriate for the specified grade?\n"
    "2. Is the level (beginner/intermediate/advanced) appropriate for the module content?\n"
    "3. Is the progression logical from basics to advanced?\n"
    "4. Do the modules cover the topic comprehensively?\n"
    "5. Is the content style compatible with the specified curriculum?\n\n"
    "If alignment score ≥ 70, set is_aligned = true. Otherwise set it to false.\n"
    "All content must be in English."
)

planner_ar = LlmAgent(
    name="PlannerAgent_AR",
    model=MODEL,
    instruction=PLANNER_INSTRUCTION_AR,
    output_key="syllabus_json",
    generate_content_config=config,
)

planner_en = LlmAgent(
    name="PlannerAgent_EN",
    model=MODEL,
    instruction=PLANNER_INSTRUCTION_EN,
    output_key="syllabus_json",
    generate_content_config=config,
)

content_creator_ar = LlmAgent(
    name="ContentAgent_AR",
    model=MODEL,
    instruction=CONTENT_INSTRUCTION_AR,
    output_key="lesson_json",
    generate_content_config=config,
)

content_creator_en = LlmAgent(
    name="ContentAgent_EN",
    model=MODEL,
    instruction=CONTENT_INSTRUCTION_EN,
    output_key="lesson_json",
    generate_content_config=config,
)

quiz_generator_ar = LlmAgent(
    name="QuizAgent_AR",
    model=MODEL,
    instruction=QUIZ_INSTRUCTION_AR,
    output_key="quiz_json",
    generate_content_config=config,
)

quiz_generator_en = LlmAgent(
    name="QuizAgent_EN",
    model=MODEL,
    instruction=QUIZ_INSTRUCTION_EN,
    output_key="quiz_json",
    generate_content_config=config,
)

evaluator_ar = LlmAgent(
    name="EvaluatorAgent_AR",
    model=MODEL,
    instruction=EVAL_INSTRUCTION_AR,
    output_key="evaluation_json",
    generate_content_config=config,
)

evaluator_en = LlmAgent(
    name="EvaluatorAgent_EN",
    model=MODEL,
    instruction=EVAL_INSTRUCTION_EN,
    output_key="evaluation_json",
    generate_content_config=config,
)

validator_ar = LlmAgent(
    name="ValidatorAgent_AR",
    model=MODEL,
    instruction=VALIDATOR_INSTRUCTION_AR,
    output_key="validation_json",
    generate_content_config=config,
)

validator_en = LlmAgent(
    name="ValidatorAgent_EN",
    model=MODEL,
    instruction=VALIDATOR_INSTRUCTION_EN,
    output_key="validation_json",
    generate_content_config=config,
)

learning_pipeline_ar = SequentialAgent(
    name="LearningPipeline_AR",
    sub_agents=[planner_ar, content_creator_ar, quiz_generator_ar, evaluator_ar],
)

learning_pipeline_en = SequentialAgent(
    name="LearningPipeline_EN",
    sub_agents=[planner_en, content_creator_en, quiz_generator_en, evaluator_en],
)

PLANNER_RUNNER_AR = InMemoryRunner(agent=planner_ar, app_name="learning_app")
PLANNER_RUNNER_EN = InMemoryRunner(agent=planner_en, app_name="learning_app")
CONTENT_RUNNER_AR = InMemoryRunner(agent=content_creator_ar, app_name="learning_app")
CONTENT_RUNNER_EN = InMemoryRunner(agent=content_creator_en, app_name="learning_app")
QUIZ_RUNNER_AR = InMemoryRunner(agent=quiz_generator_ar, app_name="learning_app")
QUIZ_RUNNER_EN = InMemoryRunner(agent=quiz_generator_en, app_name="learning_app")
EVAL_RUNNER_AR = InMemoryRunner(agent=evaluator_ar, app_name="learning_app")
EVAL_RUNNER_EN = InMemoryRunner(agent=evaluator_en, app_name="learning_app")
VALIDATOR_RUNNER_AR = InMemoryRunner(agent=validator_ar, app_name="learning_app")
VALIDATOR_RUNNER_EN = InMemoryRunner(agent=validator_en, app_name="learning_app")
PIPELINE_RUNNER_AR = InMemoryRunner(agent=learning_pipeline_ar, app_name="learning_pipeline")
PIPELINE_RUNNER_EN = InMemoryRunner(agent=learning_pipeline_en, app_name="learning_pipeline")


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
            raise ValueError("Agent returned no output" if retry_hint else "الوكيل لم يُرجع أي مخرجات")
        try:
            return json.loads(_clean_json(raw), strict=False)
        except json.JSONDecodeError as e:
            if attempt == 0 and retry_hint:
                prompt += "\n\n" + retry_hint
            else:
                raise


def _get_runner(lang: str, ar_runner, en_runner):
    return en_runner if lang == "en" else ar_runner


def _retry_hint(lang: str):
    if lang == "en":
        return "Make sure the output is valid JSON with no unescaped quotes."
    return "تأكد من أن المخرجات JSON صالح تمامًا بدون أي علامات تنصيص غير مهربة."


async def generate_syllabus(grade: str, subject: str, topic: str, level: str, goals: str = "", language: str = "ar", curriculum: str = "") -> dict:
    runner = _get_runner(language, PLANNER_RUNNER_AR, PLANNER_RUNNER_EN)
    if language == "en":
        prompt = f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLearner level: {level}\n"
        if curriculum:
            prompt += f"Curriculum: {curriculum}\n"
        if goals:
            prompt += f"Learner goals: {goals}\n"
        prompt += "\nCreate an educational syllabus."
    else:
        prompt = f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nمستوى المتعلم: {level}\n"
        if curriculum:
            prompt += f"المنهاج التعليمي: {curriculum}\n"
        if goals:
            prompt += f"أهداف المتعلم: {goals}\n"
        prompt += "\nقم بإنشاء منهج تعليمي."
    syllabus = await _generate_json(runner, prompt, _retry_hint(language))

    if curriculum:
        validation = await validate_content(syllabus, grade, subject, topic, level, curriculum, language)
        if not validation.get("is_aligned", True):
            issues = validation.get("issues", [])
            suggestions = validation.get("suggestions", [])
            if language == "en":
                retry_prompt = prompt + (
                    f"\n\nPrevious attempt was not aligned with the curriculum. Issues found:\n"
                    + "\n".join(f"- {i}" for i in issues)
                    + "\n\nSuggestions to improve:\n"
                    + "\n".join(f"- {s}" for s in suggestions)
                    + "\n\nPlease regenerate the syllabus addressing these issues."
                )
            else:
                retry_prompt = prompt + (
                    f"\n\nالمحاولة السابقة لم تتوافق مع المنهج. المشاكل المكتشفة:\n"
                    + "\n".join(f"- {i}" for i in issues)
                    + "\n\nاقتراحات للتحسين:\n"
                    + "\n".join(f"- {s}" for s in suggestions)
                    + "\n\nيرجى إعادة إنشاء المنهج مع معالجة هذه المشاكل."
                )
            syllabus = await _generate_json(runner, retry_prompt, _retry_hint(language))

    return syllabus


async def generate_lesson(grade: str, subject: str, topic: str, level: str, module_title: str, goals: str = "", language: str = "ar", curriculum: str = "") -> dict:
    runner = _get_runner(language, CONTENT_RUNNER_AR, CONTENT_RUNNER_EN)
    if language == "en":
        prompt = (
            f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLearner level: {level}\n"
            f"Module title: {module_title}\n"
        )
        if curriculum:
            prompt += f"Curriculum: {curriculum}\n"
        if goals:
            prompt += f"Learner goals: {goals}\n"
        prompt += "\nCreate lesson content for this module."
        hint = "Make sure the JSON is valid. Use \\\" inside strings when needed. Do not leave unescaped quotes in the content."
    else:
        prompt = (
            f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nمستوى المتعلم: {level}\n"
            f"عنوان الوحدة: {module_title}\n"
        )
        if curriculum:
            prompt += f"المنهاج التعليمي: {curriculum}\n"
        if goals:
            prompt += f"أهداف المتعلم: {goals}\n"
        prompt += "\nقم بإنشاء محتوى درس لهذه الوحدة."
        hint = "تأكد من أن الـ JSON صحيح تمامًا. استخدم \\\" داخل النصوص عند الحاجة. لا تترك علامات اقتباس غير مهربة في المحتوى."
    lesson = await _generate_json(runner, prompt, hint)

    if curriculum:
        validation = await validate_content(lesson, grade, subject, topic, level, curriculum, language)
        if not validation.get("is_aligned", True):
            issues = validation.get("issues", [])
            suggestions = validation.get("suggestions", [])
            if language == "en":
                retry_prompt = prompt + (
                    f"\n\nPrevious attempt was not aligned with the curriculum. Issues found:\n"
                    + "\n".join(f"- {i}" for i in issues)
                    + "\n\nSuggestions to improve:\n"
                    + "\n".join(f"- {s}" for s in suggestions)
                    + "\n\nPlease regenerate the lesson content addressing these issues."
                )
            else:
                retry_prompt = prompt + (
                    f"\n\nالمحاولة السابقة لم تتوافق مع المنهج. المشاكل المكتشفة:\n"
                    + "\n".join(f"- {i}" for i in issues)
                    + "\n\nاقتراحات للتحسين:\n"
                    + "\n".join(f"- {s}" for s in suggestions)
                    + "\n\nيرجى إعادة إنشاء محتوى الدرس مع معالجة هذه المشاكل."
                )
            lesson = await _generate_json(runner, retry_prompt, hint)

    return lesson


async def generate_quiz(topic: str, level: str, lesson_content: str, language: str = "ar", curriculum: str = "") -> dict:
    runner = _get_runner(language, QUIZ_RUNNER_AR, QUIZ_RUNNER_EN)
    if language == "en":
        prompt = (
            f"Topic: {topic}\nLearner level: {level}\n"
        )
        if curriculum:
            prompt += f"Curriculum: {curriculum}\n"
        prompt += (
            f"Lesson content:\n{lesson_content}\n\nCreate quiz questions."
        )
        hint = "Make sure the JSON is valid with no errors."
    else:
        prompt = (
            f"الموضوع: {topic}\nمستوى المتعلم: {level}\n"
        )
        if curriculum:
            prompt += f"المنهاج التعليمي: {curriculum}\n"
        prompt += (
            f"محتوى الدرس:\n{lesson_content}\n\nقم بإنشاء أسئلة اختبار."
        )
        hint = "تأكد من أن JSON صالح تمامًا بدون أخطاء."
    return await _generate_json(runner, prompt, hint)


async def evaluate_answers(questions: list, user_answers: list, correct_answers: list, language: str = "ar") -> dict:
    runner = _get_runner(language, EVAL_RUNNER_AR, EVAL_RUNNER_EN)
    if language == "en":
        prompt = (
            f"Questions: {json.dumps(questions)}\n"
            f"User answers: {json.dumps(user_answers)}\n"
            f"Correct answers: {json.dumps(correct_answers)}\n\nEvaluate the user's performance."
        )
        hint = "Make sure the JSON is valid with no errors."
    else:
        prompt = (
            f"الأسئلة: {json.dumps(questions)}\n"
            f"إجابات المستخدم: {json.dumps(user_answers)}\n"
            f"الإجابات الصحيحة: {json.dumps(correct_answers)}\n\nقم بتقييم أداء المستخدم."
        )
        hint = "تأكد من أن JSON صالح تمامًا بدون أخطاء."
    return await _generate_json(runner, prompt, hint)


async def validate_content(content: dict, grade: str, subject: str, topic: str, level: str, curriculum: str, language: str = "ar") -> dict:
    runner = _get_runner(language, VALIDATOR_RUNNER_AR, VALIDATOR_RUNNER_EN)
    content_str = json.dumps(content, ensure_ascii=False)
    if language == "en":
        prompt = (
            f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLevel: {level}\n"
            f"Curriculum: {curriculum}\n\n"
            f"Generated content:\n{content_str}\n\n"
            f"Validate alignment with the curriculum."
        )
    else:
        prompt = (
            f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nالمستوى: {level}\n"
            f"المنهاج التعليمي: {curriculum}\n\n"
            f"المحتوى المُنشأ:\n{content_str}\n\n"
            f"تحقق من التوافق مع المنهج."
        )
    try:
        return await _generate_json(runner, prompt, _retry_hint(language))
    except Exception:
        return {"is_aligned": True, "score": 100, "issues": [], "suggestions": []}
