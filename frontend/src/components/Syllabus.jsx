import React, { useEffect, useState } from 'react';
import { getSession } from '../api';

const ICONS = ['📖', '🔬', '🧮', '🌍'];

export default function Syllabus({ session, onSelectModule, onNewTopic, language, t }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [flipped, setFlipped] = useState({});

  useEffect(() => {
    load();
  }, [session.session_id]);

  const load = async () => {
    setLoading(true);
    try {
      const s = await getSession(session.session_id);
      setData(s);
    } catch {
      setData(session);
    } finally {
      setLoading(false);
    }
  };

  const toggleFlip = (idx) => {
    setFlipped((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const handleStartLesson = (e, mod, idx) => {
    e.stopPropagation();
    onSelectModule(mod, idx);
  };

  if (loading) return <div className="spinner" />;

  const syllabus = data?.syllabus || session.syllabus;
  const progress = data?.progress || [];
  const modules = syllabus?.modules || [];

  const getModuleStatus = (idx) => {
    const p = progress.find((x) => x.module_index === idx);
    if (!p) return 'pending';
    return p.completed ? 'completed' : 'pending';
  };

  const extractPoints = (desc, stripTitle) => {
    let text = desc;
    if (stripTitle && text.startsWith(stripTitle)) {
      text = text.slice(stripTitle.length).replace(/^[:.\s،,]+/, '');
    }
    const words = text.split(' ');
    const points = [];
    let current = '';
    for (const w of words) {
      if (current && current.length + w.length > 35) {
        points.push(current + '...');
        break;
      }
      current += (current ? ' ' : '') + w;
      if (w.endsWith('.') || w.endsWith('،')) {
        points.push(current);
        current = '';
        if (points.length >= 3) break;
      }
    }
    if (current && points.length < 3) points.push(current);
    return points.length > 0 ? points : [desc];
  };

  return (
    <div>
      <div className="flash-card card-purple">
        <h2>📚 {syllabus?.topic || session.topic}</h2>
        <p style={{ fontSize: 14, color: '#888' }}>
          {t.syllabus.levelLabel} <span className="badge">
            {session.level === 'Beginner' ? t.levelBeginner : session.level === 'Intermediate' ? t.levelIntermediate : t.levelAdvanced}
          </span>
        </p>
      </div>
      <div className="flash-card card-blue">
        <h3>🛣️ {t.syllabus.learningPath} ({modules.length} {t.syllabus.modulesUnit})</h3>
        {modules.length === 0 ? (
          <p style={{ fontSize: 14, color: '#888' }}>{t.syllabus.noModules}</p>
        ) : (
          <div className="flip-grid">
            {modules.map((mod, i) => {
              const status = getModuleStatus(i);
              const points = extractPoints(mod.description, mod.title);
              return (
                <div
                  key={i}
                  className={`flip-card ${flipped[i] ? 'flipped' : ''} ${status === 'completed' ? 'completed' : ''}`}
                  onClick={() => toggleFlip(i)}
                >
                  <div className="flip-card-inner">
                    <div className="flip-card-front">
                      <div className="card-icon">{ICONS[i % ICONS.length]}</div>
                      <div className="card-number">{t.syllabus.unit} {i + 1}</div>
                      <div className="card-title">{mod.title}</div>
                      <div className="card-hint">{t.syllabus.tapHint}</div>
                    </div>
                    <div className="flip-card-back">
                      <div className="back-content">
                        <ul className="back-points">
                          {points.map((p, pi) => (
                            <li key={pi}>{p}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="back-actions">
                        <span className={`back-status ${status}`}>
                          {status === 'completed' ? t.syllabus.completed : t.syllabus.pending}
                        </span>
                        <button className="back-btn" onClick={(e) => handleStartLesson(e, mod, i)}>
                          {status === 'completed' ? t.syllabus.retryLesson : t.syllabus.startLesson}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <div className="actions">
        <button className="btn btn-secondary" onClick={onNewTopic}>{t.syllabus.newTopic}</button>
      </div>
    </div>
  );
}
