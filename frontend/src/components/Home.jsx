import React, { useState } from 'react';
import { startSession } from '../api';

const SUBJECTS = [
  'اللغة العربية',
  'العلوم',
  'الرياضيات',
  'التاريخ',
  'الجغرافيا',
  'اللغة الإنجليزية',
  'الفيزياء',
  'الكيمياء',
  'الأحياء',
  'التربية الإسلامية',
  'البرمجة وتقنية المعلومات',
  'الفنون',
  'الاقتصاد',
  'الفلسفة',
  'علم النفس',
  'علوم الحاسوب',
];

const GRADES = [
  'الصف الأول ',
  'الصف الثاني ',
  'الصف الثالث ',
  'الصف الرابع ',
  'الصف الخامس ',
  'الصف السادس ',
  'الصف السابع ',
  'الصف الثامن ',
  'الصف التاسع ',
  'الصف العاشر ',
  'الصف الحادي عشر ',
  'الصف الثاني عشر ',
];

const LEVEL_LABELS = { Beginner: 'مبتدئ', Intermediate: 'متوسط', Advanced: 'متقدم' };

export default function Home({ onStart }) {
  const [grade, setGrade] = useState('');
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [level, setLevel] = useState('Beginner');
  const [goals, setGoals] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!grade || !subject || !topic.trim()) return;
    setLoading(true);
    setError('');
    try {
      const session = await startSession(grade, subject, topic.trim(), level, goals.trim());
      onStart(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isValid = grade && subject && topic.trim();

  return (
    <div>
      <div className="flash-card card-pink">
        <div className="welcome-banner">
          <span className="emoji-big">🧠</span>
          <h2>ماذا تريد أن تتعلم اليوم؟</h2>
          <p>اختر المادة واكتب الموضوع وابدأ رحلة التعلم!</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>المادة</label>
            <select value={subject} onChange={(e) => setSubject(e.target.value)} disabled={loading}>
              <option value="">-- اختر المادة --</option>
              {SUBJECTS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>الصف</label>
            <select value={grade} onChange={(e) => setGrade(e.target.value)} disabled={loading}>
              <option value="">-- اختر الصف --</option>
              {GRADES.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>الموضوع</label>
            <input
              type="text"
              placeholder="مثال: التفاضل والتكامل، النحو، الجبر..."
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label>مستواك</label>
            <select value={level} onChange={(e) => setLevel(e.target.value)} disabled={loading}>
              <option value="Beginner">مبتدئ</option>
              <option value="Intermediate">متوسط</option>
              <option value="Advanced">متقدم</option>
            </select>
          </div>
          <div className="form-group">
            <label>أهداف التعلم (اختياري)</label>
            <textarea
              placeholder="مثال: أريد فهم الأساسيات وحل المسائل بنفسي..."
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
              disabled={loading}
              rows={3}
            />
          </div>

          {isValid && !loading && (
            <div className="summary-card">
              <h3>📋 ملخص طلبك</h3>
              <div className="summary-row">
                <div><strong>المادة:</strong> {subject}</div>
                <div><strong>الصف:</strong> {grade}</div>
                <div><strong>الموضوع:</strong> {topic}</div>
                <div><strong>المستوى:</strong> {LEVEL_LABELS[level]}</div>
                {goals && <div><strong>الأهداف:</strong> {goals}</div>}
              </div>
            </div>
          )}

          {error && <p style={{ color: '#ea4335', fontSize: 14, marginBottom: 12 }}>{error}</p>}
          <button type="submit" className="btn btn-primary" disabled={loading || !isValid}>
            {loading ? 'جارٍ إنشاء خطة التعلم...' : 'ابدأ التعلم 🚀'}
          </button>
        </form>
      </div>
    </div>
  );
}
