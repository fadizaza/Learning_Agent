const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export function startSession(grade, subject, topic, level, goals = '', language = 'ar', curriculum = '') {
  return api('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ grade, subject, topic, level, goals, language, curriculum }),
  });
}

export function getSession(id) {
  return api(`/api/sessions/${id}`);
}

export function getProgress(id) {
  return api(`/api/sessions/${id}/progress`);
}

export function getLesson(sessionId, moduleIndex, moduleTitle, language = 'ar') {
  return api('/api/lessons', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, module_index: moduleIndex, module_title: moduleTitle, language }),
  });
}

export function getQuiz(sessionId, moduleIndex, moduleTitle, lessonContent, language = 'ar') {
  return api('/api/quiz', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, module_index: moduleIndex, module_title: moduleTitle, lesson_content: lessonContent, language }),
  });
}

export function submitQuiz(sessionId, moduleIndex, questions, userAnswers, correctAnswers, language = 'ar', retryCount = 0) {
  return api('/api/evaluate', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, module_index: moduleIndex, questions, user_answers: userAnswers, correct_answers: correctAnswers, language, retry_count: retryCount }),
  });
}

export function getTTS(text, language = 'ar') {
  const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  return fetch(`${API_BASE_URL}/api/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language }),
  });
}
