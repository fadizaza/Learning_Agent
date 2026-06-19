const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'فشل الطلب');
  }
  return res.json();
}

export function startSession(grade, subject, topic, level, goals = '') {
  return api('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ grade, subject, topic, level, goals }),
  });
}

export function getSession(id) {
  return api(`/api/sessions/${id}`);
}

export function getProgress(id) {
  return api(`/api/sessions/${id}/progress`);
}

export function getLesson(sessionId, moduleIndex, moduleTitle) {
  return api('/api/lessons', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, module_index: moduleIndex, module_title: moduleTitle }),
  });
}

export function getQuiz(sessionId, moduleIndex, moduleTitle, lessonContent) {
  return api('/api/quiz', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, module_index: moduleIndex, module_title: moduleTitle, lesson_content: lessonContent }),
  });
}

export function submitQuiz(sessionId, moduleIndex, questions, userAnswers, correctAnswers) {
  return api('/api/evaluate', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, module_index: moduleIndex, questions, user_answers: userAnswers, correct_answers: correctAnswers }),
  });
}
