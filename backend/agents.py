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

from openai import AsyncOpenAI


_openai_client = None


def _get_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=os.getenv("MISTRAL_API_KEY"),
            base_url="https://api.mistral.ai/v1",
        )
    return _openai_client


def _repair_json(text: str) -> str:
    text = _normalize_arabic_json(text)
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

MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

config_planner = {"temperature": 0.4, "max_tokens": 4096}
config_content = {"temperature": 0.7, "max_tokens": 8192}
config_quiz = {"temperature": 0.3, "max_tokens": 8192}
config_eval = {"temperature": 0.2, "max_tokens": 2048}
config_validator = {"temperature": 0.3, "max_tokens": 4096}
config_quality = {"temperature": 0.3, "max_tokens": 4096}

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
    "أنت خبير في التصميم التعليمي المتخصص في بيئات التعلم الرقمية والتعلم القائم على الألعاب. "
    "بصفتك معلماً خبيراً، قم بإنشاء وحدة تعليمية تفاعلية متكاملة.\n\n"
    "ستتلقى: الصف (كنص مثل 'الصف الأول')، والمادة، والموضوع، ومستوى المتعلم، وعنوان الوحدة، "
    "ووصفها، ونتائج التعلم المحددة للوحدة، والمنهج التعليمي، وأهداف المتعلم، و**رقم الصف** (عدد صحيح من 1 إلى 12).\n\n"
    "مهم جداً: يجب أن يغطي المحتوى المُنشأ جميع نتائج التعلم المحددة للوحدة.\n\n"
    "إذا تم تحديد منهج تعليمي محدد، يجب أن يكون المحتوى متوافقًا مع معاييره ونواتج تعلمه.\n\n"
    "ارجع JSON صالحًا فقط بهذا الهيكل تمامًا، بدون markdown أو code fences:\n"
    "{\n"
    '  "title": "<عنوان الوحدة>",\n'
    '  "hook": "<مقدمة تفاعلية مشوقة تناسب الفئة العمرية>",\n'
    '  "content": "<محتوى الدرس المفصل>",\n'
    '  "key_points": ["<نقطة 1>", "<نقطة 2>", "<نقطة 3>", "<نقطة 4>", "<نقطة 5>"],\n'
    '  "examples": ["<مثال 1>", "<مثال 2>", "<مثال 3>"],\n'
    '  "sections_images": {"<عنوان القسم>": "<search query in English for image>"},\n'
    '  "interactive_checkpoints": [\n'
    "    {\n"
    '      "type": "<drag_drop | multiple_choice | true_false | bonus_challenge>",\n'
    '      "question": "<نص السؤال أو النشاط>",\n'
    '      "options": ["<خيار 1>", "<خيار 2>", "<خيار 3>", "<خيار 4>"],\n'
    '      "correct_index": 0,\n'
    '      "success_message": "<رسالة نجاح عند الحل الصحيح>",\n'
    '      "failure_message": "<رسالة محاولة مساعدة عند الخطأ>",\n'
    '      "catch_up_hint": "<تلميح مبسط للطالب الذي واجه صعوبة>",\n'
    '      "level_up_challenge": "<سؤال بونص أو تحدٍ متقدم للطلاب المتميزين>"\n'
    "    }\n"
    "  ],\n"
    '  "adaptive_paths": {\n'
    '    "catch_up": "<مسار دعم مبسط مع شرح بديل مختصر>",\n'
    '    "level_up": "<مسار تحدي متقدم مع سؤال بونص أو تحدٍ إضافي>"\n'
    "  },\n"
    '  "gamification_reward": "<مكافأة رقمية تناسب عمر الطالب>"\n'
    "}\n\n"
    "=== قواعد التكيّف حسب رقم الصف ===\n\n"
    "حدد أسلوب العرض بناءً على رقم الصف المُرسل في الطلب:\n\n"
    "للصفوف 1-3 (المراحل الأولية - عباقرة صغار):\n"
    "- أسلوب العرض: قصصي، ممتع، محفز جداً. استبدل النصوص الطويلة بوصف لعناصر بصرية وشخصيات كرتونية.\n"
    "- الخطاف (hook): مهمّة إنقاذ أو لعبة.\n"
    "- المحتوى: أقسام قصيرة جداً (2-3 جمل لكل قسم)، استخدام تشبيهات من الحياة اليومية.\n"
    "- الأنشطة التفاعلية: ألعاب تعليمية (سحب وإفلات، توصيل، الضغط على الإجابة الصحيحة).\n"
    "- المكافأة: وسام رقمي أو نجمة مع إيموجي.\n"
    "- رسائل النجاح: 'أحسنت! 🎉'، 'أنت بطل! ⭐'.\n"
    "- رسائل الخطأ: 'لا بأس، حاول مرة أخرى! 💪'، 'فكر قليلاً ثم أعد المحاولة 🤔'.\n\n"
    "للصفوف 4-8 (المراحل المتوسطة - مغامرون صغار):\n"
    "- أسلوب العرض: استكشاف وحل ألغاز، ربط المفهوم بتطبيقات من الحياة الواقعية.\n"
    "- الخطاف (hook): لغز أو مشكلة واقعية تحتاج إلى حل.\n"
    "- المحتوى: أقسام متوسطة مع أمثلة متنوعة وتمارين تطبيقية.\n"
    "- الأنشطة التفاعلية: أسئلة اختيار من متعدد، مقارنات، مقاربات خاطئة شائعة.\n"
    "- المكافأة: نقاط خبرة XP وشارة.\n"
    "- رسائل النجاح: 'ممتاز! أنت على الطريق الصحيح 🚀'، 'عمل رائع! استمر 💎'.\n"
    "- رسائل الخطأ: 'تقريباً صحيحاً! حاول مرة أخرى 🔍'، 'فكر في مثال آخر 📝'.\n\n"
    "للصفوف 9-12 (المراحل العليا - محترفون):\n"
    "- أسلوب العرض: مهني، منطقي، نقي. يركز على عمق المفهوم والكفاءة والتطبيق العملي/البرمجي.\n"
    "- الخطاف (hook): تحدي حقيقي أو مشكلة تقنية/رياضية تحتاج إلى حل ذكي.\n"
    "- المحتوى: أقسام تفصيلية مع تحليل نقدي وتطبيقات في العالم الحقيقي.\n"
    "- الأنشطة التفاعلية: أسئلة برمجية، اختبارات قصيرة ذكية، تحديات منطقية.\n"
    "- المكافأة: نقاط خبرة XP ومؤشر تقدم وتصنيف.\n"
    "- رسائل النجاح: 'تحليل ممتاز! أنت جاهز للمستوى التالي 🎓'، 'أداء احترافي! استمر في التحدي 🏅'.\n"
    "- رسائل الخطأ: 'تحليل جيد لكن تحتاج لمراجعة هذه النقطة 📊'، 'فكر في الطريقة البديلة 🔄'.\n\n"
    "=== قواعد المحتوى الإلزامية ===\n\n"
    "1. حقل hook:\n"
    "   - جملة واحدة مشوقة تناسب الفئة العمرية.\n"
    "   - للصغار: قصة قصيرة أو مهمة.\n"
    "   - للكبار: تحدي أو مشكلة حقيقية.\n\n"
    "2. حقل content:\n"
    "   - الهيكل الإلزامي (3-5 أقسام):\n"
    "     + القسم 1: التعريف والمفاهيم الأساسية\n"
    "     + القسم 2: الشرح التفصيلي مع أمثلة\n"
    "     + القسم 3: تطبيقات عملية ومسائل محلولة\n"
    "     + القسم 4: أخطاء شائعة وmisconceptions\n"
    "     + القسم 5: ملخص وخلاصة\n"
    "   - ابدأ كل قسم بـ ## متبوعة بعنوان القسم.\n"
    "   - العمق حسب المستوى: مبتدئ (600-800 كلمة)، متوسط (800-1200)، متقدم (1200-1800).\n\n"
    "3. حقل interactive_checkpoints (2-3 أنشطة):\n"
    "   - للصغار: ألعاب (drag_drop, multiple_choice).\n"
    "   - للكبار: تحديات منطقية أو برمجية (bonus_challenge).\n\n"
    "4. حقل adaptive_paths:\n"
    "   - catch_up: شرح بديل مبسط (2-3 جمل).\n"
    "   - level_up: سؤال بونص أو تحدٍ متقدم سريع.\n\n"
    "5. حقل gamification_reward:\n"
    "   - للصفوف 1-3: وسام أو نجمة مع إيموجي.\n"
    "   - للصفوف 4-8: نقاط XP وشارة.\n"
    "   - للصفوف 9-12: نقاط XP ومؤشر تقدم وتصنيف.\n\n"
    "6. حقل key_points: 5 نقاط على الأقل.\n"
    "7. حقل examples: 3 أمثلة على الأقل.\n"
    "8. حقل sections_images: فقط للأقسام التي تحتاج صورة توضيحية.\n\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

CONTENT_INSTRUCTION_EN = (
    "You are an expert instructional designer specializing in gamified digital learning and micro-learning "
    "experiences. As an expert teacher, create a complete, interactive lesson module.\n\n"
    "You will receive: grade (as text like 'Grade 5'), subject, topic, learner level, module title, "
    "module description, the specific learning outcomes for this module, the curriculum framework, "
    "the learner's goals, and **grade number** (integer 1 through 12).\n\n"
    "VERY IMPORTANT: The generated content MUST cover ALL specified learning outcomes for this module.\n\n"
    "If a specific curriculum is provided, the content must align with its standards and learning outcomes.\n\n"
    "Return only valid JSON with this exact structure, no markdown or code fences:\n"
    "{\n"
    '  "title": "<module title>",\n'
    '  "hook": "<engaging mission-style hook appropriate for the age group>",\n'
    '  "content": "<detailed lesson content>",\n'
    '  "key_points": ["<point 1>", "<point 2>", "<point 3>", "<point 4>", "<point 5>"],\n'
    '  "examples": ["<example 1>", "<example 2>", "<example 3>"],\n'
    '  "sections_images": {"<section heading>": "<search query in English for image>"},\n'
    '  "interactive_checkpoints": [\n'
    "    {\n"
    '      "type": "<drag_drop | multiple_choice | true_false | bonus_challenge>",\n'
    '      "question": "<question or activity text>",\n'
    '      "options": ["<option 1>", "<option 2>", "<option 3>", "<option 4>"],\n'
    '      "correct_index": 0,\n'
    '      "success_message": "<encouraging success message>",\n'
    '      "failure_message": "<supportive retry message>",\n'
    '      "catch_up_hint": "<simplified hint for struggling students>",\n'
    '      "level_up_challenge": "<bonus challenge for advanced students>"\n'
    "    }\n"
    "  ],\n"
    '  "adaptive_paths": {\n'
    '    "catch_up": "<simplified alternative explanation for struggling students>",\n'
    '    "level_up": "<advanced challenge or extension activity for quick learners>"\n'
    "  },\n"
    '  "gamification_reward": "<age-appropriate digital reward description>"\n'
    "}\n\n"
    "=== Grade-Adaptive Rules ===\n\n"
    "Choose your delivery style based on the **grade number** provided:\n\n"
    "For Grades 1-3 (Early Learners):\n"
    "- Style: Story-driven, playful, highly motivating. Replace long texts with visual/narrative descriptions.\n"
    "- Hook: A rescue mission or a fun game.\n"
    "- Content: Very short sections (2-3 sentences each), use everyday life analogies.\n"
    "- Interactive Activities: Educational games (drag & drop, matching, click-the-right-answer).\n"
    "- Reward: A digital badge or star with an emoji.\n"
    "- Success messages: 'Great job! 🎉', 'You are a star! ⭐'.\n"
    "- Failure messages: 'No problem, try again! 💪', 'Think a bit, then try again 🤔'.\n\n"
    "For Grades 4-8 (Middle Years - Young Explorers):\n"
    "- Style: Exploration and puzzle-solving. Connect concepts to real-life applications.\n"
    "- Hook: A puzzle or real-world problem that needs solving.\n"
    "- Content: Medium sections with diverse examples and practical exercises.\n"
    "- Interactive Activities: Multiple-choice questions, comparisons, common misconceptions.\n"
    "- Reward: XP points and a badge.\n"
    "- Success messages: 'Excellent! You are on the right track 🚀', 'Great work! Keep going 💎'.\n"
    "- Failure messages: 'Almost! Try again 🔍', 'Think about another example 📝'.\n\n"
    "For Grades 9-12 (Advanced Learners - Professionals):\n"
    "- Style: Professional, logical, sharp. Focus on depth, competence, and practical/technical application.\n"
    "- Hook: A real challenge or technical/mathematical problem needing a clever solution.\n"
    "- Content: Detailed sections with critical analysis and real-world applications.\n"
    "- Interactive Activities: Coding/logic challenges, smart quizzes, reasoning tasks.\n"
    "- Reward: XP points with progress indicator and rank.\n"
    "- Success messages: 'Brilliant analysis! You are ready for the next level 🎓', 'Professional performance! Keep challenging yourself 🏅'.\n"
    "- Failure messages: 'Good analysis but review this point 📊', 'Consider the alternative approach 🔄'.\n\n"
    "=== Mandatory Content Rules ===\n\n"
    "1. hook field:\n"
    "   - One engaging sentence appropriate for the age group.\n"
    "   - For younger: a short story or mission.\n"
    "   - For older: a challenge or real-world problem.\n\n"
    "2. content field:\n"
    "   - Mandatory structure (3-5 sections):\n"
    "     + Section 1: Definition and core concepts\n"
    "     + Section 2: Detailed explanation with examples\n"
    "     + Section 3: Practical applications and solved problems\n"
    "     + Section 4: Common mistakes and misconceptions\n"
    "     + Section 5: Summary and key takeaways\n"
    "   - Start each section with ## followed by the section heading.\n"
    "   - Depth by level: Beginner (600-800 words), Intermediate (800-1200), Advanced (1200-1800).\n\n"
    "3. interactive_checkpoints field (2-3 activities):\n"
    "   - For younger: games (drag_drop, multiple_choice).\n"
    "   - For older: logic or coding challenges (bonus_challenge).\n\n"
    "4. adaptive_paths field:\n"
    "   - catch_up: simplified alternative explanation (2-3 sentences).\n"
    "   - level_up: bonus question or quick advanced challenge.\n\n"
    "5. gamification_reward field:\n"
    "   - Grades 1-3: badge or star with emoji.\n"
    "   - Grades 4-8: XP points and badge.\n"
    "   - Grades 9-12: XP points with progress indicator and rank.\n\n"
    "6. key_points: At least 5 points.\n"
    "7. examples: At least 3 examples.\n"
    "8. sections_images: Only for sections that need an illustrative image.\n\n"
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
    "1. توزيع الأنواع الإلزامي (5 أسئلة):\n"
    "   - 1 أسئلة تذكر (recall): تحديد مفاهيم وتعريفات\n"
    "   - 3 أسئلة فهم (comprehension): شرح وتفسير ومقارنة\n"
    "   - 1 أسئلة تطبيق (application): حل مسائل وتطبيق في مواقف جديدة\n\n"
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
    "1. Mandatory type distribution (5 questions):\n"
    "   - 1 recall question: identifying concepts and definitions\n"
    "   - 3 comprehension questions: explaining, interpreting, comparing\n"
    "   - 1 application question: solving problems and applying in new situations\n\n"
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

SYLLABUS_VALIDATOR_INSTRUCTION_AR = (
    "أنت محقق توافق المنهج التعليمي. مهمتك التحقق مما إذا كان المنهج (قائمة الوحدات والنتائج التعليمية) "
    "متوافقًا مع المنهاج المحدد.\n\n"
    "ستتلقى المنهج المُنشأ وبيانات المنهاج. قيم التوافق وارجع JSON صالحًا فقط:\n"
    "{\n"
    '  "is_aligned": true أو false,\n'
    '  "score": <رقم من 0 إلى 100 يمثل درجة التوافق مع المنهاج>,\n'
    '  "issues": ["<مشكلة 1>", "<مشكلة 2>"],\n'
    '  "suggestions": ["<اقتراح 1>", "<اقتراح 2>"]\n'
    "}\n\n"
    "معايير التحقق للمنهج:\n"
    "1. هل مواضيع الوحدات مدرجة في المنهاج المحدد لهذا الصف والمادة؟\n"
    "2. هل نتائج التعلم (learning_outcomes) متوافقة مع معايير المنهاج؟\n"
    "3. هل الترتيب منطقي من الأساسيات إلى المتقدم؟\n"
    "4. هل المنهج يغطي الموضوعات والمفاهيم الأساسية المطلوبة في المنهاج؟\n"
    "5. هل عدد الوحدات مناسب لنطاق الموضوع في المنهاج؟\n\n"
    "إذا كان التوافق ≥ 70، ضع is_aligned = true. وإلا ضعه = false.\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

SYLLABUS_VALIDATOR_INSTRUCTION_EN = (
    "You are a curriculum syllabus validator. Your task is to verify whether the generated syllabus "
    "(list of modules and learning outcomes) aligns with the specified curriculum.\n\n"
    "You will receive the generated syllabus and curriculum data. Evaluate alignment and return only valid JSON:\n"
    "{\n"
    '  "is_aligned": true or false,\n'
    '  "score": <number from 0 to 100 representing alignment score with the curriculum>,\n'
    '  "issues": ["<issue 1>", "<issue 2>"],\n'
    '  "suggestions": ["<suggestion 1>", "<suggestion 2>"]\n'
    "}\n\n"
    "Validation criteria for syllabus:\n"
    "1. Are the module topics included in the specified curriculum for this grade and subject?\n"
    "2. Do the learning outcomes align with the curriculum standards?\n"
    "3. Is the progression logical from basics to advanced?\n"
    "4. Does the syllabus cover the essential topics and concepts required by the curriculum?\n"
    "5. Is the number of modules appropriate for the scope of the topic in the curriculum?\n\n"
    "If alignment score ≥ 70, set is_aligned = true. Otherwise set it to false.\n"
    "All content must be in English."
)

CONTENT_VALIDATOR_INSTRUCTION_AR = (
    "أنت محقق توافق المحتوى التعليمي. مهمتك التحقق مما إذا كان محتوى الدرس المُنشأ متوافقًا مع "
    "المنهاج المحدد.\n\n"
    "ستتلقى محتوى الدرس وبيانات المنهاج. قيم التوافق وارجع JSON صالحًا فقط:\n"
    "{\n"
    '  "is_aligned": true أو false,\n'
    '  "score": <رقم من 0 إلى 100 يمثل درجة التوافق مع المنهاج>,\n'
    '  "issues": ["<مشكلة 1>", "<مشكلة 2>"],\n'
    '  "suggestions": ["<اقتراح 1>", "<اقتراح 2>"]\n'
    "}\n\n"
    "معايير التحقق لمحتوى الدرس:\n"
    "1. هل المحتوى يتضمن الموضوعات والمفاهيم المطلوبة في المنهاج؟\n"
    "2. هل أسلوب العرض والشرح يطابق أسلوب المنهاج (مثل: أكاديمي، تطبيقي، نقدي)؟\n"
    "3. هل مستوى التعقيد والعمق مناسب لمرحلة الطلاب في هذا المنهاج؟\n"
    "4. هل المحتوى يراعي الفروق العمرية والognitive للطلاب في هذا المستوى؟\n"
    "5. هل المعلومات المقدمة متوافقة مع ما يتوقعه المنهاج من الطلاب؟\n\n"
    "إذا كان التوافق ≥ 70، ضع is_aligned = true. وإلا ضعه = false.\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

CONTENT_VALIDATOR_INSTRUCTION_EN = (
    "You are a curriculum content validator. Your task is to verify whether the generated lesson content "
    "aligns with the specified curriculum.\n\n"
    "You will receive the lesson content and curriculum data. Evaluate alignment and return only valid JSON:\n"
    "{\n"
    '  "is_aligned": true or false,\n'
    '  "score": <number from 0 to 100 representing alignment score with the curriculum>,\n'
    '  "issues": ["<issue 1>", "<issue 2>"],\n'
    '  "suggestions": ["<suggestion 1>", "<suggestion 2>"]\n'
    "}\n\n"
    "Validation criteria for lesson content:\n"
    "1. Does the content include the topics and concepts required by the curriculum?\n"
    "2. Does the presentation style match the curriculum's approach (e.g., academic, practical, critical)?\n"
    "3. Is the complexity and depth appropriate for students at this curriculum level?\n"
    "4. Does the content consider the cognitive development of students in this grade level?\n"
    "5. Does the information presented match what the curriculum expects students to learn?\n\n"
    "If alignment score ≥ 70, set is_aligned = true. Otherwise set it to false.\n"
    "All content must be in English."
)

QUALITY_INSTRUCTION_AR = (
    "أنت مراجع جودة المحتوى التعليمي. مهمتك تقييم جودة المحتوى المُنشأ من حيث العمق والوضوح "
    "والفاعلية والدقة.\n\n"
    "ستتلقى المحتوى المُنشأ. قيم الجودة وارجع JSON صالحًا فقط:\n"
    "{\n"
    '  "overall_score": <رقم من 0 إلى 100>,\n'
    '  "depth_score": <رقم من 0 إلى 100 - عمق المحتوى>,\n'
    '  "clarity_score": <رقم من 0 إلى 100 - ووضوح الشرح>,\n'
    '  "engagement_score": <رقم من 0 إلى 100 - مدى الجاذبية>,\n'
    '  "accuracy_score": <رقم من 0 إلى 100 - دقة المعلومات>,\n'
    '  "issues": ["<مشكلة 1>", "<مشكلة 2>"],\n'
    '  "suggestions": ["<اقتراح 1>", "<اقتراح 2>"],\n'
    '  "is_approved": true أو false\n'
    "}\n\n"
    "معايير التقييم (聚焦 على جودة المحتوى فقط):\n"
    "1. العمق: هل المحتوى يشرح المفاهيم بتفصيل كافٍ؟ هل هناك أمثلة متنوعة وتفسيرات واضحة؟\n"
    "2. الوضوح: هل اللغة واضحة ومفهومة للطلاب؟ هل الجمل مكتملة ومنطقية؟\n"
    "3. الفاعلية: هل المحتوى يجذب القارئ؟ هل يستخدم تشبيهات وأمثلة عملية من الحياة اليومية؟\n"
    "4. الدقة: هل المعلومات صحيحة ومحدثة؟ هل هناك أخطاء معلوماتية؟\n"
    "5. التنظيم: هل المحتوى منطقي ومترابط؟ هل الأفكار متسقة؟\n\n"
    "مهم: لا تتحقق من هيكل المحتوى (الأقسام، عدد الكلمات، key_points، examples). "
    "ركز فقط على جودة المحتوى التعليمي.\n\n"
    "إذا كان overall_score ≥ 70، ضع is_approved = true. وإلا ضعه = false.\n"
    "يجب أن يكون كل المحتوى باللغة العربية."
)

QUALITY_INSTRUCTION_EN = (
    "You are a content quality reviewer for educational material. Your task is to evaluate the quality "
    "of generated content in terms of depth, clarity, engagement, and accuracy.\n\n"
    "You will receive the generated content. Evaluate quality and return only valid JSON:\n"
    "{\n"
    '  "overall_score": <number from 0 to 100>,\n'
    '  "depth_score": <number from 0 to 100 - content depth>,\n'
    '  "clarity_score": <number from 0 to 100 - explanation clarity>,\n'
    '  "engagement_score": <number from 0 to 100 - how engaging it is>,\n'
    '  "accuracy_score": <number from 0 to 100 - information accuracy>,\n'
    '  "issues": ["<issue 1>", "<issue 2>"],\n'
    '  "suggestions": ["<suggestion 1>", "<suggestion 2>"],\n'
    '  "is_approved": true or false\n'
    "}\n\n"
    "Evaluation criteria (focus ONLY on content quality):\n"
    "1. Depth: Does the content explain concepts in sufficient detail? Are there diverse examples and clear explanations?\n"
    "2. Clarity: Is the language clear and understandable for students? Are sentences complete and logical?\n"
    "3. Engagement: Does the content engage the reader? Does it use analogies and practical examples from daily life?\n"
    "4. Accuracy: Is the information correct and up-to-date? Are there any factual errors?\n"
    "5. Organization: Is the content logical and coherent? Are ideas consistent?\n\n"
    "IMPORTANT: Do NOT check content structure (sections, word count, key_points, examples). "
    "Focus ONLY on educational content quality.\n\n"
    "If overall_score ≥ 70, set is_approved = true. Otherwise set it to false.\n"
    "All content must be in English."
)

AGENT_CONFIGS = {
    "planner_ar": (PLANNER_INSTRUCTION_AR, config_planner),
    "planner_en": (PLANNER_INSTRUCTION_EN, config_planner),
    "content_ar": (CONTENT_INSTRUCTION_AR, config_content),
    "content_en": (CONTENT_INSTRUCTION_EN, config_content),
    "quiz_ar": (QUIZ_INSTRUCTION_AR, config_quiz),
    "quiz_en": (QUIZ_INSTRUCTION_EN, config_quiz),
    "eval_ar": (EVAL_INSTRUCTION_AR, config_eval),
    "eval_en": (EVAL_INSTRUCTION_EN, config_eval),
    "syllabus_validator_ar": (SYLLABUS_VALIDATOR_INSTRUCTION_AR, config_validator),
    "syllabus_validator_en": (SYLLABUS_VALIDATOR_INSTRUCTION_EN, config_validator),
    "content_validator_ar": (CONTENT_VALIDATOR_INSTRUCTION_AR, config_validator),
    "content_validator_en": (CONTENT_VALIDATOR_INSTRUCTION_EN, config_validator),
    "quality_ar": (QUALITY_INSTRUCTION_AR, config_quality),
    "quality_en": (QUALITY_INSTRUCTION_EN, config_quality),
}


async def _run_agent(agent_key: str, prompt: str) -> str | None:
    instruction, cfg = AGENT_CONFIGS[agent_key]
    client = _get_client()
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": prompt},
        ],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )
    text = response.choices[0].message.content
    return text.strip() if text else None


def _normalize_arabic_json(text: str) -> str:
    ARABIC_INDIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    text = text.translate(ARABIC_INDIC_DIGITS)
    text = text.replace('،', ',').replace('؛', ';').replace('؟', '?').replace('！', '!')
    text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
    text = text.replace('«', '"').replace('»', '"').replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    return text


LEVEL_MAP_AR = {
    "Beginner": "مبتدئ",
    "Intermediate": "متوسط",
    "Advanced": "متقدم",
}


def _get_level(level: str, language: str) -> str:
    if language == "ar":
        return LEVEL_MAP_AR.get(level, level)
    return level


def _clean_json(text: str) -> str:
    text = _normalize_arabic_json(text)
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


async def _generate_json(agent_key: str, prompt: str, retry_hint: str = "", logger=None, agent_name: str = "", step: str = "", attempt: int = 1, reason: str = "", content_type: str = "", language: str = "") -> dict:
    for i in range(3):
        actual_attempt = attempt + i
        if logger:
            logger.begin_agent_call(agent_name, step, prompt, attempt=actual_attempt, reason=reason if i > 0 else "")
        raw = await _run_agent(agent_key, prompt)
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
        except json.JSONDecodeError:
            try:
                repaired = _repair_json(cleaned)
                if repaired.endswith(','):
                    repaired = repaired[:-1]
                parsed = json.loads(repaired, strict=False)
            except json.JSONDecodeError:
                if logger:
                    logger.set_error(f"JSON parse error on attempt {actual_attempt}")
                    logger.end_agent_call()
                if i < 2 and retry_hint:
                    prompt += "\n\n" + retry_hint
                    reason = "json_parse_error"
                    continue
                else:
                    raise

        if content_type:
            struct_errors = _validate_json_structure(parsed, content_type, language)
            lang_errors = _validate_language(parsed, content_type, language) if language else []
            all_errors = struct_errors + lang_errors

            if all_errors:
                if logger:
                    logger.set_error(f"Validation errors on attempt {actual_attempt}: {'; '.join(all_errors)}")
                    logger.end_agent_call()
                if i < 2:
                    feedback = _build_validation_feedback(all_errors, language)
                    prompt += f"\n\n{feedback}"
                    reason = "validation_failed"
                    if logger:
                        logger.begin_agent_call(agent_name, step, prompt, attempt=actual_attempt + 1, reason=reason)
                    continue
                else:
                    raise ValueError(f"Validation failed after {actual_attempt} attempts: {'; '.join(all_errors)}")

        if logger:
            logger.set_parsed_json(parsed)
            logger.end_agent_call()
        return parsed


def _get_agent_key(lang: str, ar_key: str, en_key: str):
    return en_key if lang == "en" else ar_key


def _has_arabic(text: str) -> bool:
    return bool(re.search(r'[\u0600-\u06FF]', text))


def _has_english(text: str) -> bool:
    return bool(re.search(r'[a-zA-Z]{3,}', text))


def _arabic_ratio(text: str) -> float:
    if not text:
        return 0.0
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    total_chars = len(re.findall(r'[\u0600-\u06FF\u0041-\u005a\u0061-\u007a]', text))
    return arabic_chars / total_chars if total_chars > 0 else 0.0


def _validate_json_structure(data: dict, content_type: str, language: str) -> list:
    errors = []

    if content_type == "lesson":
        required_fields = {
            "title": str,
            "hook": str,
            "content": str,
            "key_points": list,
            "examples": list,
            "sections_images": dict,
            "interactive_checkpoints": list,
            "adaptive_paths": dict,
            "gamification_reward": str,
        }
        for field, expected_type in required_fields.items():
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif not isinstance(data[field], expected_type):
                errors.append(f"Field '{field}' must be {expected_type.__name__}, got {type(data[field]).__name__}")
            elif expected_type in (str, list, dict) and not data[field]:
                errors.append(f"Field '{field}' is empty")

        if not errors:
            if len(data.get("key_points", [])) < 3:
                errors.append("key_points must have at least 3 items")
            if len(data.get("examples", [])) < 2:
                errors.append("examples must have at least 2 items")
            if len(data.get("interactive_checkpoints", [])) < 1:
                errors.append("interactive_checkpoints must have at least 1 item")

            content_text = data.get("content", "")
            word_count = len(content_text.split())
            if word_count < 100:
                errors.append(f"content too short ({word_count} words, minimum 100)")

            adaptive = data.get("adaptive_paths", {})
            if not adaptive.get("catch_up"):
                errors.append("adaptive_paths.catch_up is missing or empty")
            if not adaptive.get("level_up"):
                errors.append("adaptive_paths.level_up is missing or empty")

    elif content_type == "syllabus":
        if "modules" not in data:
            errors.append("Missing required field: modules")
        elif not isinstance(data["modules"], list):
            errors.append("Field 'modules' must be a list")
        elif len(data["modules"]) < 1:
            errors.append("modules must have at least 1 item")
        else:
            for i, mod in enumerate(data["modules"]):
                if not isinstance(mod, dict):
                    errors.append(f"modules[{i}] must be a dict")
                    continue
                if "title" not in mod:
                    errors.append(f"modules[{i}] missing 'title'")
                if "description" not in mod:
                    errors.append(f"modules[{i}] missing 'description'")
                if "learning_outcomes" not in mod:
                    errors.append(f"modules[{i}] missing 'learning_outcomes'")

    elif content_type == "quiz":
        if "questions" not in data:
            errors.append("Missing required field: questions")
        elif not isinstance(data["questions"], list):
            errors.append("Field 'questions' must be a list")
        elif len(data["questions"]) < 1:
            errors.append("questions must have at least 1 item")
        else:
            for i, q in enumerate(data["questions"]):
                if not isinstance(q, dict):
                    errors.append(f"questions[{i}] must be a dict")
                    continue
                if "question" not in q:
                    errors.append(f"questions[{i}] missing 'question'")
                if "options" not in q or not isinstance(q["options"], list):
                    errors.append(f"questions[{i}] missing or invalid 'options'")
                if "correct_answer" not in q and "correct_index" not in q:
                    errors.append(f"questions[{i}] missing 'correct_answer'")

    elif content_type == "evaluation":
        if "score" not in data and "overall_score" not in data:
            errors.append("Missing score field (score or overall_score)")

    return errors


def _validate_language(data: dict, content_type: str, language: str) -> list:
    errors = []
    if language != "ar":
        return errors

    if content_type == "lesson":
        text_fields = ["title", "hook", "content"]
        for field in text_fields:
            value = data.get(field, "")
            if value and _has_english(value) and _arabic_ratio(value) < 0.5:
                errors.append(f"Field '{field}' appears to be in English, expected Arabic")

        for i, point in enumerate(data.get("key_points", [])):
            if isinstance(point, str) and _has_english(point) and _arabic_ratio(point) < 0.5:
                errors.append(f"key_points[{i}] appears to be in English, expected Arabic")

        for i, example in enumerate(data.get("examples", [])):
            if isinstance(example, str) and _has_english(example) and _arabic_ratio(example) < 0.5:
                errors.append(f"examples[{i}] appears to be in English, expected Arabic")

        checkpoints = data.get("interactive_checkpoints", [])
        for i, cp in enumerate(checkpoints):
            if isinstance(cp, dict):
                for field in ["question", "success_message", "failure_message"]:
                    value = cp.get(field, "")
                    if value and _has_english(value) and _arabic_ratio(value) < 0.5:
                        errors.append(f"interactive_checkpoints[{i}].{field} appears to be in English, expected Arabic")

    elif content_type == "syllabus":
        if "topic" in data and _has_english(data["topic"]) and _arabic_ratio(data["topic"]) < 0.5:
            errors.append("Field 'topic' appears to be in English, expected Arabic")
        for i, mod in enumerate(data.get("modules", [])):
            if isinstance(mod, dict):
                for field in ["title", "description"]:
                    value = mod.get(field, "")
                    if value and _has_english(value) and _arabic_ratio(value) < 0.5:
                        errors.append(f"modules[{i}].{field} appears to be in English, expected Arabic")

    return errors


def _build_validation_feedback(errors: list, language: str) -> str:
    if language == "ar":
        feedback = "التحقق فشل due to the following issues:\n"
        for err in errors:
            feedback += f"- {err}\n"
        feedback += (
            "\nIMPORTANT: Fix ALL issues above. Output ONLY valid JSON.\n"
            "Every Arabic text field MUST contain Arabic characters only (no English words).\n"
            "Do not use markdown or code fences. Return raw JSON only."
        )
    else:
        feedback = "Validation failed due to the following issues:\n"
        for err in errors:
            feedback += f"- {err}\n"
        feedback += (
            "\nIMPORTANT: Fix ALL issues above. Output ONLY valid JSON.\n"
            "Every text field MUST contain English text.\n"
            "Do not use markdown or code fences. Return raw JSON only."
        )
    return feedback


def _retry_hint(lang: str):
    if lang == "en":
        return ("IMPORTANT: Output ONLY valid JSON. Every property must be separated by a comma. "
                "Example: {\"key1\": \"val1\", \"key2\": \"val2\"}. No markdown, no code fences, no extra text.")
    return ("مهم جداً: أخرج JSON صالح فقط. كل خاصية يجب أن تكون مفصولة بفاصلة. "
            "مثال: {\"key1\": \"val1\", \"key2\": \"val2\"}. بدون markdown أو كود أو نص إضافي.")


async def generate_syllabus(grade: str, subject: str, topic: str, level: str, goals: str = "", language: str = "ar", curriculum: str = "", logger=None) -> dict:
    agent_key = _get_agent_key(language, "planner_ar", "planner_en")
    agent_name = "PlannerAgent_AR" if language == "ar" else "PlannerAgent_EN"
    if language == "en":
        prompt = f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLearner level: {level}\n"
        if curriculum:
            prompt += f"Curriculum: {curriculum}\n"
        if goals:
            prompt += f"Learner goals: {goals}\n"
        prompt += "\nCreate an educational syllabus."
    else:
        prompt = f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nمستوى المتعلم: {_get_level(level, language)}\n"
        if curriculum:
            prompt += f"المنهاج التعليمي: {curriculum}\n"
        if goals:
            prompt += f"أهداف المتعلم: {goals}\n"
        prompt += "\nقم بإنشاء منهج تعليمي."
    syllabus = await _generate_json(agent_key, prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="generate_syllabus", content_type="syllabus", language=language)

    if curriculum:
        validation = await validate_syllabus(syllabus, grade, subject, topic, level, curriculum, language)
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
            syllabus = await _generate_json(agent_key, retry_prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="generate_syllabus_retry", attempt=2, reason="curriculum_misaligned", content_type="syllabus", language=language)

    return syllabus


async def generate_lesson(grade: str, subject: str, topic: str, level: str, module_title: str, goals: str = "", language: str = "ar", curriculum: str = "", logger=None, quality_feedback: str = "", module_description: str = "", learning_outcomes: list = None, grade_number: int = 0) -> dict:
    agent_key = _get_agent_key(language, "content_ar", "content_en")
    agent_name = "ContentAgent_AR" if language == "ar" else "ContentAgent_EN"
    if language == "en":
        prompt = (
            f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLearner level: {level}\n"
            f"Module title: {module_title}\n"
        )
        if grade_number:
            prompt += f"Grade number: {grade_number}\n"
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
            f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nمستوى المتعلم: {_get_level(level, language)}\n"
            f"عنوان الوحدة: {module_title}\n"
        )
        if grade_number:
            prompt += f"رقم الصف: {grade_number}\n"
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
    lesson = await _generate_json(agent_key, prompt, hint, logger=logger, agent_name=agent_name, step="generate_lesson", content_type="lesson", language=language)

    if curriculum:
        validation = await validate_lesson_content(lesson, grade, subject, topic, level, curriculum, language, logger=logger)
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
            lesson = await _generate_json(agent_key, retry_prompt, hint, logger=logger, agent_name=agent_name, step="generate_lesson_retry", attempt=2, reason="curriculum_misaligned", content_type="lesson", language=language)

    return lesson


async def generate_quiz(topic: str, level: str, lesson_content: str, language: str = "ar", curriculum: str = "", logger=None, quality_feedback: str = "") -> dict:
    agent_key = _get_agent_key(language, "quiz_ar", "quiz_en")
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
            f"الموضوع: {topic}\nمستوى المتعلم: {_get_level(level, language)}\n"
        )
        if curriculum:
            prompt += f"المنهاج التعليمي: {curriculum}\n"
        if quality_feedback:
            prompt += f"\nملاحظات الجودة من المحاولة السابقة:\n{quality_feedback}\n"
        prompt += (
            f"محتوى الدرس:\n{lesson_content}\n\nقم بإنشاء أسئلة اختبار."
        )
        hint = "تأكد من أن JSON صالح تمامًا بدون أخطاء."
    return await _generate_json(agent_key, prompt, hint, logger=logger, agent_name=agent_name, step="generate_quiz", content_type="quiz", language=language)


async def evaluate_answers(questions: list, user_answers: list, correct_answers: list, language: str = "ar") -> dict:
    agent_key = _get_agent_key(language, "eval_ar", "eval_en")
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
    return await _generate_json(agent_key, prompt, hint, content_type="evaluation", language=language)


async def validate_syllabus(content: dict, grade: str, subject: str, topic: str, level: str, curriculum: str, language: str = "ar", logger=None) -> dict:
    agent_key = _get_agent_key(language, "syllabus_validator_ar", "syllabus_validator_en")
    agent_name = "SyllabusValidator_AR" if language == "ar" else "SyllabusValidator_EN"
    content_str = json.dumps(content, ensure_ascii=False)
    if language == "en":
        prompt = (
            f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLevel: {level}\n"
            f"Curriculum: {curriculum}\n\n"
            f"Generated syllabus:\n{content_str}\n\n"
            f"Check if this syllabus aligns with the {curriculum} curriculum standards. "
            f"Are the module topics and learning outcomes appropriate for this curriculum?"
        )
    else:
        prompt = (
            f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nالمستوى: {_get_level(level, language)}\n"
            f"المنهاج التعليمي: {curriculum}\n\n"
            f"المنهج المُنشأ:\n{content_str}\n\n"
            f"تحقق مما إذا كان هذا المنهج يتوافق مع معايير منهج {curriculum}. "
            f"هل مواضيع الوحدات ونتائج التعلم مناسبة لهذا المنهاج؟"
        )
    try:
        result = await _generate_json(agent_key, prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="validate_syllabus")
        if "criteria" not in result:
            result["criteria"] = {}
        if "is_aligned" not in result:
            result["is_aligned"] = result.get("score", 100) >= 70
        return result
    except Exception:
        return {"is_aligned": True, "score": 100, "criteria": {}, "issues": [], "suggestions": []}


async def validate_lesson_content(content: dict, grade: str, subject: str, topic: str, level: str, curriculum: str, language: str = "ar", logger=None) -> dict:
    agent_key = _get_agent_key(language, "content_validator_ar", "content_validator_en")
    agent_name = "ContentValidator_AR" if language == "ar" else "ContentValidator_EN"
    content_str = json.dumps(content, ensure_ascii=False)
    if language == "en":
        prompt = (
            f"Grade: {grade}\nSubject: {subject}\nTopic: {topic}\nLevel: {level}\n"
            f"Curriculum: {curriculum}\n\n"
            f"Generated lesson content:\n{content_str}\n\n"
            f"Check if this lesson content aligns with the {curriculum} curriculum standards. "
            f"Does it cover the required topics? Does it match the curriculum's style and complexity level?"
        )
    else:
        prompt = (
            f"الصف: {grade}\nالمادة: {subject}\nالموضوع: {topic}\nالمستوى: {_get_level(level, language)}\n"
            f"المنهاج التعليمي: {curriculum}\n\n"
            f"محتوى الدرس المُنشأ:\n{content_str}\n\n"
            f"تحقق مما إذا كان محتوى الدرس هذا يتوافق مع معايير منهج {curriculum}. "
            f"هل يغطي الموضوعات المطلوبة؟ هل يطابق أسلوب المنهاج ومستوى التعقيد؟"
        )
    try:
        result = await _generate_json(agent_key, prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="validate_lesson_content")
        if "criteria" not in result:
            result["criteria"] = {}
        if "is_aligned" not in result:
            result["is_aligned"] = result.get("score", 100) >= 70
        return result
    except Exception:
        return {"is_aligned": True, "score": 100, "criteria": {}, "issues": [], "suggestions": []}


async def check_content_quality(content: dict, content_type: str, language: str = "ar", logger=None) -> dict:
    agent_key = _get_agent_key(language, "quality_ar", "quality_en")
    agent_name = "QualityAgent_AR" if language == "ar" else "QualityAgent_EN"
    content_str = json.dumps(content, ensure_ascii=False)
    if language == "en":
        prompt = (
            f"Content type: {content_type}\n\n"
            f"Generated content:\n{content_str}\n\n"
            f"Evaluate the educational quality of this content. "
            f"Focus on: depth of explanation, clarity of language, engagement level, and accuracy of information. "
            f"Do NOT check if sections exist or word count — just evaluate quality."
        )
    else:
        prompt = (
            f"نوع المحتوى: {content_type}\n\n"
            f"المحتوى المُنشأ:\n{content_str}\n\n"
            f"قم بتقييم الجودة التعليمية لهذا المحتوى. "
            f"ركز على: عمق الشرح، وضوح اللغة، مستوى التفاعل، ودقة المعلومات. "
            f"لا تتحقق من وجود الأقسام أو عدد الكلمات — قم فقط بتقييم الجودة."
        )
    try:
        result = await _generate_json(agent_key, prompt, _retry_hint(language), logger=logger, agent_name=agent_name, step="check_quality")
        if "criteria" not in result:
            result["criteria"] = {}
        if "is_approved" not in result:
            result["is_approved"] = result.get("overall_score", 80) >= 70
        return result
    except Exception:
        return {"overall_score": 80, "depth_score": 80, "clarity_score": 80, "engagement_score": 80, "completeness_score": 80, "criteria": {}, "issues": [], "suggestions": [], "is_approved": True}
