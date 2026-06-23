import React, { useState } from 'react';
import { startSession } from '../api';
import LoadingOverlay from './LoadingOverlay';

export default function Home({ onStart, language, t }) {
  const [grade, setGrade] = useState('');
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [level, setLevel] = useState('Beginner');
  const [curriculum, setCurriculum] = useState('');
  const [goals, setGoals] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!grade || !subject || !topic.trim()) return;
    setLoading(true);
    setError('');
    try {
      const session = await startSession(grade, subject, topic.trim(), level, goals.trim(), language, curriculum);
      onStart(session);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isValid = grade && subject && topic.trim();

  if (loading) {
    const p = t.loading.pipeline;
    return (
      <LoadingOverlay
        steps={[
          { agentName: p.syllabus1.agent, message: p.syllabus1.message, subMessage: p.syllabus1.sub, shortLabel: p.syllabus1.short, icon: '🤖', duration: 8000 },
          { agentName: p.syllabus2.agent, message: p.syllabus2.message, subMessage: p.syllabus2.sub, shortLabel: p.syllabus2.short, icon: '🔍', duration: 8000 },
        ]}
      />
    );
  }

  return (
    <div>
      <div className="flash-card card-pink">
        <div className="welcome-banner">
          <span className="emoji-big">🧠</span>
          <h2>{t.home.welcomeTitle}</h2>
          <p>{t.home.welcomeSubtitle}</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>{t.home.subjectLabel}</label>
            <select value={subject} onChange={(e) => setSubject(e.target.value)} disabled={loading}>
              <option value="">{t.home.subjectPlaceholder}</option>
              {t.subjects.map((s, i) => (
                <option key={i} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>{t.home.gradeLabel}</label>
            <select value={grade} onChange={(e) => setGrade(e.target.value)} disabled={loading}>
              <option value="">{t.home.gradePlaceholder}</option>
              {t.grades.map((g, i) => (
                <option key={i} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>{t.home.topicLabel}</label>
            <input
              type="text"
              placeholder={t.home.topicPlaceholder}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label>{t.home.levelLabel}</label>
            <select value={level} onChange={(e) => setLevel(e.target.value)} disabled={loading}>
              <option value="Beginner">{t.levelBeginner}</option>
              <option value="Intermediate">{t.levelIntermediate}</option>
              <option value="Advanced">{t.levelAdvanced}</option>
            </select>
          </div>
          <div className="form-group">
            <label>{t.home.curriculumLabel}</label>
            <select value={curriculum} onChange={(e) => setCurriculum(e.target.value)} disabled={loading}>
              <option value="">{t.home.curriculumPlaceholder}</option>
              {t.curricula.map((c, i) => (
                <option key={i} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>{t.home.goalsLabel}</label>
            <textarea
              placeholder={t.home.goalsPlaceholder}
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
              disabled={loading}
              rows={3}
            />
          </div>

          {isValid && !loading && (
            <div className="summary-card">
              <h3>📋 {t.home.summaryTitle}</h3>
              <div className="summary-row">
                <div><strong>{t.home.summarySubject}</strong> {subject}</div>
                <div><strong>{t.home.summaryGrade}</strong> {grade}</div>
                <div><strong>{t.home.summaryTopic}</strong> {topic}</div>
                <div><strong>{t.home.summaryLevel}</strong> {level === 'Beginner' ? t.levelBeginner : level === 'Intermediate' ? t.levelIntermediate : t.levelAdvanced}</div>
                {curriculum && <div><strong>{t.home.summaryCurriculum}</strong> {curriculum}</div>}
                {goals && <div><strong>{t.home.summaryGoals}</strong> {goals}</div>}
              </div>
            </div>
          )}

          {error && <p style={{ color: '#ea4335', fontSize: 14, marginBottom: 12 }}>{error}</p>}
          <button type="submit" className="btn btn-primary" disabled={loading || !isValid}>
            {t.home.submit}
          </button>
        </form>
      </div>
    </div>
  );
}
