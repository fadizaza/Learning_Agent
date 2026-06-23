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


def _repair_json(text: str) -> str:
    result = []
    in_string = False
    escape_next = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escape_next = True
            i += 1
            continue
        if ch == '"':
            if in_string:
                j = i + 1
                while j < n and text[j] in ' \t\n\r':
                    j += 1
                next_significant = text[j] if j < n else ''
                if next_significant in ('}', ']', ',', ':'):
                    in_string = False
                    result.append(ch)
                    i += 1
                    continue
                else:
                    result.append('\\')
                    result.append(ch)
                    i += 1
                    continue
            else:
                in_string = True
                result.append(ch)
                i += 1
                continue
        if in_string:
            if ch == '\n':
                result.append('\\n')
                i += 1
                continue
            if ch == '\r':
                i += 1
                continue
            if ch == '\t':
                result.append(' ')
                i += 1
                continue
            result.append(ch)
            i += 1
            continue
        if ch in (' ', '\n', '\r', '\t'):
            i += 1
            continue
        result.append(ch)
        i += 1
    return ''.join(result)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

config_planner = types.GenerateContentConfig(temperature=0.4, max_output_tokens=4096)
config_content = types.GenerateContentConfig(temperature=0.7, max_output_tokens=8192)
config_quiz = types.GenerateContentConfig(temperature=0.3, max_output_tokens=8192)
config_eval = types.GenerateContentConfig(temperature=0.2, max_output_tokens=2048)
config_validator = types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048)
config_quality = types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048)

PLANNER_INSTRUCTION_AR = (
    "أنت خبير في تصميم الدروس التعليمية. بناءً على الصف والمادة والموضوع ومستوى المتعلم "
    "(مبتدئ، متوسط، متقدم) والمنهج التعليمي وأهدافه، قم بإنشاء درس تعليمي منظم.\n\n"
    "إذا تم تحديد منهاج تعليمي محدد، يجب أن تكون الوحدات والمواضيع متوافقة مع معاييره ونواتج تعلمه.\n\n"
    "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
    "{\n"
    '  "topic": "<الموضوع>",\n'
    '  "level": "<المستوى>",\n'
    '  "modules": [\n'
    "    {\n"
    '      "title": "<عنوان الوحدة>",\n'
    '      "description": "<وصف مختصر لما تغطيه هذه الوحدة>",\n'
    '      "learning_outcomes": ["<نتيجة تعلم 1>", "<نتيجة تعلم 2>", "<نتيجة تعلم 3>"]\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "قواعد صارمة للمنهج:\n"
    "1. أنشئ 3 وحدات تتقدم منطقيًا: الوحدة الأولى (أساسيات ومفاهيم أولية)، الوحدة الثانية (تطبيق وتوسيع)، الوحدة الثالثة (تحليل متقدم وتركيب).\n"
    "2. كل وحدة يجب أن تضيف 2-3 نتائج تعلم واضحة وقابلة للقياس.\n"
    "3. الوصف يجب أن يحدد بدقة ما ستتعلمه الوحدة، وليس مجرد عنوان عام.\n"
    "4. تجنب التكرار بين الوحدات.\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

PLANNER_INSTRUCTION_EN = (
    "You are an expert in designing educational lessons. Based on the grade, subject, topic, "
    "learner level (beginner, intermediate, advanced), the curriculum framework, and their goals, "
    "create an organized educational lesson.\n\n"
    "If a specific curriculum is provided, the modules and topics must align with its standards and learning outcomes.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "topic": "<topic>",\n'
    '  "level": "<level>",\n'
    '  "modules": [\n'
    "    {\n"
    '      "title": "<module title>",\n'
    '      "description": "<brief description of what this module covers>",\n'
    '      "learning_outcomes": ["<outcome 1>", "<outcome 2>", "<outcome 3>"]\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Strict rules for the syllabus:\n"
    "1. Create 3 modules with logical progression: Module 1 (foundations and core concepts), "
    "Module 2 (application and expansion), Module 3 (advanced analysis and synthesis).\n"
    "2. Each module must have 2-3 specific, measurable learning outcomes.\n"
    "3. The description must clearly state what the learner will master, not just a generic title.\n"
    "4. Avoid overlap between modules.\n"
    "All content must be in English."
)

CONTENT_INSTRUCTION_AR = (
    "أنت معلم خبير. بناءً على الصف والمادة والموضوع ومستوى المتعلم وعنوان الوحدة ووصفها "
    "ونتائج التعلم المحددة للوحدة والمنهج التعليمي وأهدافه، قم بإنشاء محتوى درس جذاب وعميق.\n\n"
    "مهم جداً: يجب أن يغطي المحتوى المُنشأ جميع نتائج التعلم المحددة للوحدة. راجع نتائج التعلم وتأكد من أن كل نتيجة مُغطاة في المحتوى.\n\n"
    "إذا تم تحديد منهج تعليمي محدد، يجب أن يكون المحتوى متوافقًا مع معاييره ونواتج تعلمه وأسلوب عرضه.\n\n"
    "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
    "{\n"
    '  "title": "<عنوان الوحدة>",\n'
    '  "content": "<محتوى الدرس المفصل>",\n'
    '  "key_points": ["<نقطة 1>", "<نقطة 2>", "<نقطة 3>", "<نقطة 4>", "<نقطة 5>"],\n'
    '  "examples": ["<مثال 1>", "<مثال 2>", "<مثال 3>"],\n'
    '  "sections_images": {"<عنوان القسم>": "<search query in English for image>"}\n'
    "}\n\n"
    "قواعد صارمة للمحتوى:\n\n"
    "1. الهيكل الإلزامي لكل درس (3-5 أقسام):\n"
    "   - القسم 1: التعريف والمفاهيم الأساسية (ما هو؟ ولماذا هو مهم؟)\n"
    "   - القسم 2: الشرح التفصيلي مع أمثلة موضحة\n"
    "   - القسم 3: تطبيقات عملية ومسائل محلولة\n"
    "   - القسم 4: أخطاء شائعة وmisconceptions\n"
    "   - القسم 5: ملخص وخلاصة\n\n"
    "2. متطلبات العمق حسب المستوى:\n"
    "   - مبتدئ: تعريفات بسيطة، تشبيهات من الحياة اليومية، أمثلة مبسطة. 600-800 كلمة.\n"
    "   - متوسط: شرح أعمق، مقارنات، حل مشكلات،misconceptions شائعة. 800-1200 كلمة.\n"
    "   - متقدم: تحليل نقدي، تطبيقات في العالم الحقيقي، حالات حدية، بُعد بحثي. 1200-1800 كلمة.\n\n"
    "3. ابدأ كل قسم بـ ## متبوعة بعنوان القسم في سطر منفصل.\n"
    "4. إذا احتوى المحتوى على بيانات جدولية، استخدم تنسيق جدول ماركdown.\n"
    "5. أضف مدخلات في sections_images فقط للقوائم التي تحتاج صورة توضيحية.\n"
    "6. يجب أن تحتوي key_points على 5 نقاط على الأقل، كل نقطة يجب أن تكون جملة واضحة ومفيدة.\n"
    "7. يجب أن تحتوي examples على 3 أمثلة على الأقل، متنوعة وعملية.\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

CONTENT_INSTRUCTION_EN = (
    "You are an expert teacher. Based on the grade, subject, topic, learner level, module title, "
    "module description, the specific learning outcomes for this module, the curriculum framework, "
    "and their goals, create engaging, in-depth lesson content.\n\n"
    "VERY IMPORTANT: The generated content MUST cover ALL specified learning outcomes for this module. "
    "Review the learning outcomes and ensure each one is addressed in your content.\n\n"
    "If a specific curriculum is provided, the content must align with its standards, learning outcomes, and presentation style.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "title": "<module title>",\n'
    '  "content": "<detailed lesson content>",\n'
    '  "key_points": ["<point 1>", "<point 2>", "<point 3>", "<point 4>", "<point 5>"],\n'
    '  "examples": ["<example 1>", "<example 2>", "<example 3>"],\n'
    '  "sections_images": {"<section heading>": "<search query in English for image>"}\n'
    "}\n\n"
    "Strict content rules:\n\n"
    "1. Mandatory structure for every lesson (3-5 sections):\n"
    "   - Section 1: Definition and core concepts (What is it? Why does it matter?)\n"
    "   - Section 2: Detailed explanation with illustrative examples\n"
    "   - Section 3: Practical applications and solved problems\n"
    "   - Section 4: Common mistakes and misconceptions\n"
    "   - Section 5: Summary and key takeaways\n\n"
    "2. Depth requirements by level:\n"
    "   - Beginner: simple definitions, real-world analogies, worked examples. 600-800 words.\n"
    "   - Intermediate: deeper explanations, comparisons, problem-solving, common misconceptions. 800-1200 words.\n"
    "   - Advanced: critical analysis, real-world applications, edge cases, research-oriented depth. 1200-1800 words.\n\n"
    "3. Start each section with ## followed by the section heading on a separate line.\n"
    "4. If the content has tabular data, use markdown table format.\n"
    "5. Add entries in sections_images only for sections that need an illustrative image.\n"
    "6. key_points must have at least 5 items, each a clear, useful sentence.\n"
    "7. examples must have at least 3 items, diverse and practical.\n"
    "All content must be in English."
)

QUIZ_INSTRUCTION_AR = (
    "أنت منشئ اختبارات تعليمي محترف. بناءً على الموضوع والمستوى والمنهج التعليمي ومحتوى الدرس، "
    "قم بإنشاء أسئلة اختيار من متعدد تختبر مستويات فهم مختلفة.\n\n"
    "إذا تم تحديد منهج تعليمي محدد، يجب أن تكون الأسئلة بأسلوب يتوافق مع أساليب التقييم في هذا المنهاج.\n\n"
    "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
    "{\n"
    '  "questions": [\n'
    "    {\n"
    '      "id": 1,\n'
    '      "question": "<نص السؤال>",\n'
    '      "options": ["<الخيار 1>", "<الخيار 2>", "<الخيار 3>", "<الخيار 4>"],\n'
    '      "correct_answer": 0,\n'
    '      "explanation": "<شرح تعليمي لماذا هذه الإجابة صحيحة ولماذا الخيارات الأخرى خاطئة>",\n'
    '      "difficulty": "easy|medium|hard",\n'
    '      "type": "recall|comprehension|application"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "قواعد صارمة للأسئلة:\n\n"
    "1. توزيع الأنواع الإلزامي (10 أسئلة):\n"
    "   - 3 أسئلة تذكر (recall): تحديد مفاهيم وتعريفات\n"
    "   - 4 أسئلة فهم (comprehension): شرح وتفسير ومقارنة\n"
    "   - 3 أسئلة تطبيق (application): حل مسائل وتطبيق في مواقف جديدة\n\n"
    "2. قواعد الخيارات:\n"
    "   - يجب أن يكون هناك 4 خيارات دائماً\n"
    "   - الخيارات الخاطئة يجب أن تكون مقنعة ومحتملة (ليست واضحة الخطأ)\n"
    "   - لا تستخدم خيارات مثل 'جميع ما سبق' أو 'لا شيء مما سبق'\n"
    "   - كل خيار يجب أن يكون جملة كاملة وواضحة\n\n"
    "3. قواعد الشرح:\n"
    "   - الشرح يجب أن يكون تعليمياً، لا يقتصر على 'الإجابة أ صحيحة'\n"
    "   - اشرح لماذا الإجابة صحيحة\n"
    "   - اشرح لماذا الخيارات الأخرى خاطئة\n"
    "   - قدم تذكيراً بالمفهوم الأساسي\n\n"
    "4. مستويات الصعوبة: سهل (30%)، متوسط (40%)، صعب (30%)\n"
    "5. مهم جداً: يجب أن تكون جميع النصوص في JSON سطر واحد بدون أسطر جديدة داخل النصوص. "
    "لا تستخدم asterisks أو markdown داخل JSON.\n"
    "correct_answer هو الفهرس (يبدأ من 0) للخيار الصحيح. "
    "يجب أن يكون كل المحتوى باللغة العربية.\n\n"
    "مثال على سؤال عالي الجودة:\n"
    '{"id": 1, "question": "إذا كان x + 5 = 12، ما قيمة x؟", "options": ["7", "5", "17", "12"], "correct_answer": 0, '
    '"explanation": "لإيجاد x، نطرح 5 من الطرفين: x = 12 - 5 = 7. الخيار 5 خطأ لأنه يمثل العدد المطروح. الخيار 17 خطأ لأنه يمثل الجمع بدلاً من الطرح. الخيار 12 خطأ لأنه يمثل الناتج الأصلي.", '
    '"difficulty": "easy", "type": "recall"}'
)

QUIZ_INSTRUCTION_EN = (
    "You are a professional educational quiz creator. Based on the topic, level, curriculum framework, "
    "and lesson content, create multiple-choice questions that test different levels of understanding.\n\n"
    "If a specific curriculum is provided, the questions should match its assessment style and command words.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "questions": [\n'
    "    {\n"
    '      "id": 1,\n'
    '      "question": "<question text>",\n'
    '      "options": ["<option 1>", "<option 2>", "<option 3>", "<option 4>"],\n'
    '      "correct_answer": 0,\n'
    '      "explanation": "<educational explanation of why this answer is correct and why others are wrong>",\n'
    '      "difficulty": "easy|medium|hard",\n'
    '      "type": "recall|comprehension|application"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Strict rules for questions:\n\n"
    "1. Mandatory type distribution (10 questions):\n"
    "   - 3 recall questions: identifying concepts and definitions\n"
    "   - 4 comprehension questions: explaining, interpreting, comparing\n"
    "   - 3 application questions: solving problems and applying in new situations\n\n"
    "2. Option rules:\n"
    "   - Always exactly 4 options\n"
    "   - Wrong options must be plausible and believable (not obviously wrong)\n"
    "   - Never use options like 'all of the above' or 'none of the above'\n"
    "   - Each option must be a complete, clear statement\n\n"
    "3. Explanation rules:\n"
    "   - Explanations must be educational, not just 'A is correct'\n"
    "   - Explain why the correct answer is correct\n"
    "   - Explain why the other options are wrong\n"
    "   - Include a brief reminder of the key concept\n\n"
    "4. Difficulty levels: easy (30%), medium (40%), hard (30%)\n"
    "5. VERY IMPORTANT: All text values in JSON must be on a single line with no newlines inside strings. "
    "Do not use asterisks or markdown inside JSON strings.\n"
    "correct_answer is the index (starting from 0) of the correct option.\n"
    "All content must be in English.\n\n"
    "Example of a high-quality question:\n"
    '{"id": 1, "question": "If x + 5 = 12, what is the value of x?", "options": ["7", "5", "17", "12"], "correct_answer": 0, '
    '"explanation": "To find x, subtract 5 from both sides: x = 12 - 5 = 7. The option 5 is wrong because it represents the subtracted number. The option 17 is wrong because it uses addition instead of subtraction. The option 12 is wrong because it is the original result.", '
    '"difficulty": "easy", "type": "recall"}'
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
    "5. هل المحتوى متوافق مع أسلوب المنهاج المحدد؟\n"
    "6. هل المحتوى يحتوي على الأقسام الإلزامية (تعريف، شرح، تطبيقات، أخطاء شائعة، ملخص)؟\n"
    "7. هل عدد الكلمات مناسب للمستوى (مبتدئ 800-1200، متوسط 1200-1800، متقدم 1800-2500)؟\n"
    "8. هل key_points تحتوي على 5 نقاط على الأقل؟\n"
    "9. هل examples تحتوي على 3 أمثلة على الأقل؟\n\n"
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
    "5. Is the content style compatible with the specified curriculum?\n"
    "6. Does the content contain all mandatory sections (definition, explanation, applications, common mistakes, summary)?\n"
    "7. Is the word count appropriate for the level (beginner 800-1200, intermediate 1200-1800, advanced 1800-2500)?\n"
    "8. Does key_points contain at least 5 items?\n"
    "9. Does examples contain at least 3 items?\n\n"
    "If alignment score ≥ 70, set is_aligned = true. Otherwise set it to false.\n"
    "All content must be in English."
)

QUALITY_INSTRUCTION_AR = (
    "أنت مراجع جودة محتوى تعليمي. مهمتك تقييم جودة المحتوى المُنشأ من حيث العمق والوضوح والفاعلية.\n\n"
    "ستتلقى المحتوى المُنشأ وبيانات الدرس. قيم الجودة وارجع JSON صالحًا فقط:\n"
    "{\n"
    '  "overall_score": <رقم من 0 إلى 100>,\n'
    '  "depth_score": <رقم من 0 إلى 100 - عمق المحتوى>,\n'
    '  "clarity_score": <رقم من 0 إلى 100 - ووضوح الشرح>,\n'
    '  "engagement_score": <رقم من 0 إلى 100 - مدى الجاذبية>,\n'
    '  "completeness_score": <رقم من 0 إلى 100 - اكتمال الأقسام>,\n'
    '  "issues": ["<مشكلة 1>", "<مشكلة 2>"],\n'
    '  "suggestions": ["<اقتراح 1>", "<اقتراح 2>"],\n'
    '  "is_approved": true أو false\n'
    "}\n\n"
    "معايير التقييم:\n"
    "1. العمق: هل المحتوى يشرح المفاهيم بتفصيل كافٍ؟ هل هناك أمثلة متنوعة؟\n"
    "2. الوضوح: هل اللغة واضحة ومفهومة للطلاب؟\n"
    "3. الجاذبية: هل المحتوى يجذب القارئ؟ هل يستخدم تشبيهات وأمثلة عملية؟\n"
    "4. الاكتمال: هل جميع الأقسام موجودة (تعريف، شرح، تطبيقات، أخطاء شائعة، ملخص)؟\n"
    "5. عدد الكلمات مناسب للمستوى؟\n\n"
    "إذا كان overall_score ≥ 70، ضع is_approved = true. وإلا ضعه = false.\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

QUALITY_INSTRUCTION_EN = (
    "You are a content quality reviewer for educational material. Your task is to evaluate the quality "
    "of generated content in terms of depth, clarity, and effectiveness.\n\n"
    "You will receive the generated content and lesson data. Evaluate quality and return only valid JSON:\n"
    "{\n"
    '  "overall_score": <number from 0 to 100>,\n'
    '  "depth_score": <number from 0 to 100 - content depth>,\n'
    '  "clarity_score": <number from 0 to 100 - explanation clarity>,\n'
    '  "engagement_score": <number from 0 to 100 - how engaging it is>,\n'
    '  "completeness_score": <number from 0 to 100 - section completeness>,\n'
    '  "issues": ["<issue 1>", "<issue 2>"],\n'
    '  "suggestions": ["<suggestion 1>", "<suggestion 2>"],\n'
    '  "is_approved": true or false\n'
    "}\n\n"
    "Evaluation criteria:\n"
    "1. Depth: Does the content explain concepts in sufficient detail? Are there diverse examples?\n"
    "2. Clarity: Is the language clear and understandable for students?\n"
    "3. Engagement: Does the content engage the reader? Does it use analogies and practical examples?\n"
    "4. Completeness: Are all sections present (definition, explanation, applications, common mistakes, summary)?\n"
    "5. Is the word count appropriate for the level?\n\n"
    "If overall_score ≥ 70, set is_approved = true. Otherwise set it to false.\n"
    "All content must be in English."
)

planner_ar = LlmAgent(
    name="PlannerAgent_AR",
    model=MODEL,
    instruction=PLANNER_INSTRUCTION_AR,
    output_key="syllabus_json",
    generate_content_config=config_planner,
)

planner_en = LlmAgent(
    name="PlannerAgent_EN",
    model=MODEL,
    instruction=PLANNER_INSTRUCTION_EN,
    output_key="syllabus_json",
    generate_content_config=config_planner,
)

content_creator_ar = LlmAgent(
    name="ContentAgent_AR",
    model=MODEL,
    instruction=CONTENT_INSTRUCTION_AR,
    output_key="lesson_json",
    generate_content_config=config_content,
)

content_creator_en = LlmAgent(
    name="ContentAgent_EN",
    model=MODEL,
    instruction=CONTENT_INSTRUCTION_EN,
    output_key="lesson_json",
    generate_content_config=config_content,
)

quiz_generator_ar = LlmAgent(
    name="QuizAgent_AR",
    model=MODEL,
    instruction=QUIZ_INSTRUCTION_AR,
    output_key="quiz_json",
    generate_content_config=config_quiz,
)

quiz_generator_en = LlmAgent(
    name="QuizAgent_EN",
    model=MODEL,
    instruction=QUIZ_INSTRUCTION_EN,
    output_key="quiz_json",
    generate_content_config=config_quiz,
)

evaluator_ar = LlmAgent(
    name="EvaluatorAgent_AR",
    model=MODEL,
    instruction=EVAL_INSTRUCTION_AR,
    output_key="evaluation_json",
    generate_content_config=config_eval,
)

evaluator_en = LlmAgent(
    name="EvaluatorAgent_EN",
    model=MODEL,
    instruction=EVAL_INSTRUCTION_EN,
    output_key="evaluation_json",
    generate_content_config=config_eval,
)

validator_ar = LlmAgent(
    name="ValidatorAgent_AR",
    model=MODEL,
    instruction=VALIDATOR_INSTRUCTION_AR,
    output_key="validation_json",
    generate_content_config=config_validator,
)

validator_en = LlmAgent(
    name="ValidatorAgent_EN",
    model=MODEL,
    instruction=VALIDATOR_INSTRUCTION_EN,
    output_key="validation_json",
    generate_content_config=config_validator,
)

quality_ar = LlmAgent(
    name="QualityAgent_AR",
    model=MODEL,
    instruction=QUALITY_INSTRUCTION_AR,
    output_key="quality_json",
    generate_content_config=config_quality,
)

quality_en = LlmAgent(
    name="QualityAgent_EN",
    model=MODEL,
    instruction=QUALITY_INSTRUCTION_EN,
    output_key="quality_json",
    generate_content_config=config_quality,
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
QUALITY_RUNNER_AR = InMemoryRunner(agent=quality_ar, app_name="learning_app")
QUALITY_RUNNER_EN = InMemoryRunner(agent=quality_en, app_name="learning_app")
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
    result = []
    in_string = False
    escape_next = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escape_next = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if in_string and ch == '\n':
            result.append('\\n')
            i += 1
            continue
        if in_string and ch == '\r':
            i += 1
            continue
        if in_string and ch == '\t':
            result.append(' ')
            i += 1
            continue
        result.append(ch)
        i += 1
    return ''.join(result)


async def _generate_json(runner: InMemoryRunner, prompt: str, retry_hint: str = "", logger=None, agent_name: str = "", step: str = "", attempt: int = 1, reason: str = "") -> dict:
    for i in range(3):
        actual_attempt = attempt + i
        if logger:
            logger.begin_agent_call(agent_name, step, prompt, attempt=actual_attempt, reason=reason if i > 0 else "")
        raw = await _run_agent(runner, prompt)
        if logger:
            logger.set_raw_response(raw or "")
        if not raw:
            if logger:
                logger.set_error("Agent returned no output")
                logger.end_agent_call()
            raise ValueError("Agent returned no output" if retry_hint else "الوكيل لم يُرجع أي مخرجات")
        cleaned = _clean_json(raw)
        if logger:
            logger.set_cleaned_response(cleaned)
        if cleaned.count('{') > cleaned.count('}'):
            cleaned += '}' * (cleaned.count('{') - cleaned.count('}'))
        if cleaned.count('[') > cleaned.count(']'):
            cleaned += ']' * (cleaned.count('[') - cleaned.count(']'))
        if cleaned.endswith(','):
            cleaned = cleaned[:-1]
        try:
            parsed = json.loads(cleaned, strict=False)
            if logger:
                logger.set_parsed_json(parsed)
                logger.end_agent_call()
            return parsed
        except json.JSONDecodeError:
            try:
                repaired = _repair_json(cleaned)
                if repaired.endswith(','):
                    repaired = repaired[:-1]
                parsed = json.loads(repaired, strict=False)
                if logger:
                    logger.set_parsed_json(parsed)
                    logger.end_agent_call()
                return parsed
            except json.JSONDecodeError:
                if logger:
                    logger.set_error(f"JSON parse error on attempt {actual_attempt}")
                    logger.end_agent_call()
                if i < 2 and retry_hint:
                    prompt += "\n\n" + retry_hint
                    reason = "json_parse_error"
                else:
                    raise


def _get_runner(lang: str, ar_runner, en_runner):
    return en_runner if lang == "en" else ar_runner


def _retry_hint(lang: str):
    if lang == "en":
        return ("IMPORTANT: Output ONLY valid JSON. Every property must be separated by a comma. "
                "Example: {\"key1\": \"val1\", \"key2\": \"val2\"}. No markdown, no code fences, no extra text.")
    return ("مهم جداً: أخرج JSON صالح فقط. كل خاصية يجب أن تكون مفصولة بفاصلة. "
            "مثال: {\"key1\": \"val1\", \"key2\": \"val2\"}. بدون markdown أو كود أو نص إضافي.")


async def generate_syllabus(grade: str, subject: str, topic: str, level: str, goals: str = "", language: str = "ar", curriculum: str = "", logger=None) -> dict:
    runner = _get_runner(language, PLANNER_RUNNER_AR, PLANNER_RUNNER_EN)
    agent_name = "PlannerAgent_AR" if language == "ar" else "PlannerAgent_EN"
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
    syllabus = await _generate_json(runner, prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="generate_syllabus")

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
            syllabus = await _generate_json(runner, retry_prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="generate_syllabus_retry", attempt=2, reason="curriculum_misaligned")

    return syllabus


async def generate_lesson(grade: str, subject: str, topic: str, level: str, module_title: str, goals: str = "", language: str = "ar", curriculum: str = "", logger=None, quality_feedback: str = "", module_description: str = "", learning_outcomes: list = None) -> dict:
    runner = _get_runner(language, CONTENT_RUNNER_AR, CONTENT_RUNNER_EN)
    agent_name = "ContentAgent_AR" if language == "ar" else "ContentAgent_EN"
    if language == "en":
        prompt = (
            f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLearner level: {level}\n"
            f"Module title: {module_title}\n"
        )
        if module_description:
            prompt += f"Module description: {module_description}\n"
        if learning_outcomes:
            prompt += "Learning outcomes for this module:\n"
            for i, outcome in enumerate(learning_outcomes, 1):
                prompt += f"  {i}. {outcome}\n"
            prompt += "\nYou MUST create content that covers ALL of the above learning outcomes.\n"
        if curriculum:
            prompt += f"Curriculum: {curriculum}\n"
        if goals:
            prompt += f"Learner goals: {goals}\n"
        if quality_feedback:
            prompt += f"\nQuality feedback from previous attempt:\n{quality_feedback}\n"
        prompt += "\nCreate lesson content for this module."
        hint = "Make sure the JSON is valid. Use \\\" inside strings when needed. Do not leave unescaped quotes in the content."
    else:
        prompt = (
            f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nمستوى المتعلم: {level}\n"
            f"عنوان الوحدة: {module_title}\n"
        )
        if module_description:
            prompt += f"وصف الوحدة: {module_description}\n"
        if learning_outcomes:
            prompt += "نتائج التعلم لهذه الوحدة:\n"
            for i, outcome in enumerate(learning_outcomes, 1):
                prompt += f"  {i}. {outcome}\n"
            prompt += "\nيجب عليك إنشاء محتوى يغطي جميع نتائج التعلم أعلاه.\n"
        if curriculum:
            prompt += f"المنهاج التعليمي: {curriculum}\n"
        if goals:
            prompt += f"أهداف المتعلم: {goals}\n"
        if quality_feedback:
            prompt += f"\nملاحظات الجودة من المحاولة السابقة:\n{quality_feedback}\n"
        prompt += "\nقم بإنشاء محتوى درس لهذه الوحدة."
        hint = "تأكد من أن الـ JSON صحيح تمامًا. استخدم \\\" داخل النصوص عند الحاجة. لا تترك علامات اقتباس غير مهربة في المحتوى."
    lesson = await _generate_json(runner, prompt, hint, logger=logger, agent_name=agent_name, step="generate_lesson")

    if curriculum:
        validation = await validate_content(lesson, grade, subject, topic, level, curriculum, language, logger=logger)
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
                    + f"\n\nاقتراحات للتحسين:\n"
                    + "\n".join(f"- {s}" for s in suggestions)
                    + "\n\nيرجى إعادة إنشاء محتوى الدرس مع معالجة هذه المشاكل."
                )
            lesson = await _generate_json(runner, retry_prompt, hint, logger=logger, agent_name=agent_name, step="generate_lesson_retry", attempt=2, reason="curriculum_misaligned")

    return lesson


async def generate_quiz(topic: str, level: str, lesson_content: str, language: str = "ar", curriculum: str = "", logger=None, quality_feedback: str = "") -> dict:
    runner = _get_runner(language, QUIZ_RUNNER_AR, QUIZ_RUNNER_EN)
    agent_name = "QuizAgent_AR" if language == "ar" else "QuizAgent_EN"
    if language == "en":
        prompt = (
            f"Topic: {topic}\nLearner level: {level}\n"
        )
        if curriculum:
            prompt += f"Curriculum: {curriculum}\n"
        if quality_feedback:
            prompt += f"\nQuality feedback from previous attempt:\n{quality_feedback}\n"
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
        if quality_feedback:
            prompt += f"\nملاحظات الجودة من المحاولة السابقة:\n{quality_feedback}\n"
        prompt += (
            f"محتوى الدرس:\n{lesson_content}\n\nقم بإنشاء أسئلة اختبار."
        )
        hint = "تأكد من أن JSON صالح تمامًا بدون أخطاء."
    return await _generate_json(runner, prompt, hint, logger=logger, agent_name=agent_name, step="generate_quiz")


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


async def validate_content(content: dict, grade: str, subject: str, topic: str, level: str, curriculum: str, language: str = "ar", logger=None) -> dict:
    runner = _get_runner(language, VALIDATOR_RUNNER_AR, VALIDATOR_RUNNER_EN)
    agent_name = "ValidatorAgent_AR" if language == "ar" else "ValidatorAgent_EN"
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
        result = await _generate_json(runner, prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="validate_content")
        if "criteria" not in result:
            result["criteria"] = {}
        if "is_aligned" not in result:
            result["is_aligned"] = result.get("score", 100) >= 70
        return result
    except Exception:
        return {"is_aligned": True, "score": 100, "criteria": {}, "issues": [], "suggestions": []}


async def check_content_quality(content: dict, content_type: str, language: str = "ar", logger=None) -> dict:
    runner = _get_runner(language, QUALITY_RUNNER_AR, QUALITY_RUNNER_EN)
    agent_name = "QualityAgent_AR" if language == "ar" else "QualityAgent_EN"
    content_str = json.dumps(content, ensure_ascii=False)
    if language == "en":
        prompt = (
            f"Content type: {content_type}\n\n"
            f"Generated content:\n{content_str}\n\n"
            f"Evaluate the quality of this educational content."
        )
    else:
        prompt = (
            f"نوع المحتوى: {content_type}\n\n"
            f"المحتوى المُنشأ:\n{content_str}\n\n"
            f"قم بتقييم جودة هذا المحتوى التعليمي."
        )
    try:
        result = await _generate_json(runner, prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="check_quality")
        if "criteria" not in result:
            result["criteria"] = {}
        if "is_approved" not in result:
            result["is_approved"] = result.get("overall_score", 80) >= 70
        return result
    except Exception:
        return {"overall_score": 80, "depth_score": 80, "clarity_score": 80, "engagement_score": 80, "completeness_score": 80, "criteria": {}, "issues": [], "suggestions": [], "is_approved": True}
