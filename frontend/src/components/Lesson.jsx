import React, { useEffect, useState, useRef, useCallback } from 'react';
import { getLesson, getQuiz, getTTS } from '../api';

const CARD_COLORS = ['card-blue', 'card-green', 'card-orange', 'card-pink', 'card-purple'];

function parseSections(content, sectionsImages = {}) {
  const lines = content.split('\n');
  const sections = [];
  let current = null;

  for (const rawLine of lines) {
    const trimmed = rawLine.trim();
    const boldMatch = trimmed.match(/^\*\*(.+)\*\*$/);
    if (boldMatch) {
      current = { heading: boldMatch[1], lines: [] };
      sections.push(current);
    } else if (trimmed.startsWith('## ')) {
      current = { heading: trimmed.replace('## ', ''), lines: [] };
      sections.push(current);
    } else if (trimmed.startsWith('# ')) {
      if (sections.length === 0) {
        current = { heading: trimmed.replace('# ', ''), lines: [] };
        sections.push(current);
      }
    } else {
      if (!current) {
        current = { heading: null, lines: [] };
        sections.push(current);
      }
      current.lines.push(rawLine);
    }
  }

  if (sections.length === 0) {
    sections.push({ heading: null, lines: [] });
  }

  for (const section of sections) {
    if (section.heading && sectionsImages[section.heading]) {
      section.imageUrl = sectionsImages[section.heading];
    }
  }

  return sections;
}

function parseTableRow(row) {
  const trimmed = row.trim();
  const parts = trimmed.split('|');
  if (trimmed.startsWith('|')) parts.shift();
  if (trimmed.endsWith('|')) parts.pop();
  return parts.map(p => p.replace(/\*/g, '').trim());
}

function isTableSeparator(line) {
  const cells = parseTableRow(line);
  return cells.length > 0 && cells.every(c => /^:?-+:?$/.test(c));
}

function renderTable(rows, key) {
  let header = null;
  let bodyStart = 0;
  for (let j = 0; j < rows.length; j++) {
    if (isTableSeparator(rows[j])) {
      if (j > 0) header = parseTableRow(rows[j - 1]);
      bodyStart = j + 1;
      break;
    }
  }
  const body = rows.slice(bodyStart);
  return (
    <table key={key} className="lesson-table">
      {header && (
        <thead>
          <tr>{header.map((cell, ci) => <th key={ci}>{cell}</th>)}</tr>
        </thead>
      )}
      <tbody>
        {body.map((row, ri) => (
          <tr key={ri}>{parseTableRow(row).map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
        ))}
      </tbody>
    </table>
  );
}

function renderLines(lines) {
  const elements = [];
  let i = 0;
  while (i < lines.length) {
    const rawLine = lines[i];
    const clean = rawLine.replace(/\*/g, '');
    if (rawLine.trim().startsWith('|')) {
      const tableRows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableRows.push(lines[i]);
        i++;
      }
      elements.push(renderTable(tableRows, elements.length));
    } else {
      if (clean.startsWith('- ')) {
        elements.push(<li key={i} style={{ marginRight: 20, marginBottom: 6 }}>{clean.replace('- ', '')}</li>);
      } else if (!clean.trim()) {
        elements.push(<br key={i} />);
      } else {
        elements.push(<p key={i} style={{ marginBottom: 10, lineHeight: 1.8 }}>{clean}</p>);
      }
      i++;
    }
  }
  return elements;
}

export default function Lesson({ session, module, onLessonReady, onStartQuiz, onBack, language, t }) {
  const [lesson, setLesson] = useState(null);
  const [sections, setSections] = useState([]);
  const [currentCard, setCurrentCard] = useState(0);
  const [quizLoading, setQuizLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [speaking, setSpeaking] = useState(false);
  const [sectionSpeaking, setSectionSpeaking] = useState(null);
  const audioRef = useRef(null);
  const sectionAudioRef = useRef(null);

  const stopListening = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setSpeaking(false);
  }, []);

  const stopSectionSpeech = useCallback(() => {
    if (sectionAudioRef.current) {
      sectionAudioRef.current.pause();
      sectionAudioRef.current = null;
    }
    setSectionSpeaking(null);
  }, []);

  const speakSection = async (text, sectionKey) => {
    stopSectionSpeech();
    stopListening();
    setSectionSpeaking(sectionKey);
    try {
      const res = await getTTS(text, language);
      if (!res.ok) {
        setSectionSpeaking(null);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      sectionAudioRef.current = audio;
      audio.onended = () => {
        setSectionSpeaking(null);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setSectionSpeaking(null);
        URL.revokeObjectURL(url);
      };
      audio.play();
    } catch {
      setSectionSpeaking(null);
    }
  };

  useEffect(() => {
    load();
    return () => { stopListening(); stopSectionSpeech(); };
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'ArrowRight') {
        if (language === 'ar') goNext();
        else goPrev();
      } else if (e.key === 'ArrowLeft') {
        if (language === 'ar') goPrev();
        else goNext();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [currentCard, sections.length, language]);

  useEffect(() => {
    stopListening();
    stopSectionSpeech();
  }, [currentCard]);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const l = await getLesson(session.session_id, module.index, module.title, language);
      setLesson(l);
      onLessonReady(l);
      setSections(parseSections(l.content || '', l.sections_images || {}));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const goTo = (index) => {
    if (index === currentCard || index < 0 || index >= sections.length) return;
    setCurrentCard(index);
  };

  const goNext = () => goTo(currentCard + 1);

  const goPrev = () => goTo(currentCard - 1);

  const stripMarkdown = (text) => {
    return text
      .replace(/\*/g, '')
      .split('\n')
      .map((line) => line.replace(/^#{1,6}\s+/, '').replace(/^[-*]\s+/, '').replace(/^\d+[.)]\s+/, ''))
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  };

  const getCurrentCardText = () => {
    if (!section) return '';
    const parts = [];
    if (section.heading) parts.push(stripMarkdown(section.heading));
    const body = section.lines
      .map((l) => stripMarkdown(l))
      .filter(Boolean)
      .join(' ');
    if (body) parts.push(body);
    return parts.join('. ');
  };

  const speak = async (text) => {
    setSpeaking(true);
    try {
      const res = await getTTS(text, language);
      if (!res.ok) {
        setSpeaking(false);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        setSpeaking(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setSpeaking(false);
        URL.revokeObjectURL(url);
      };
      audio.play();
    } catch {
      setSpeaking(false);
    }
  };

  const startListening = () => {
    stopListening();
    stopSectionSpeech();
    const text = getCurrentCardText();
    if (!text) return;
    speak(text);
  };

  const toggleListening = () => {
    if (speaking) {
      stopListening();
    } else {
      startListening();
    }
  };

  const handleQuiz = async () => {
    if (!lesson) return;
    stopListening();
    setQuizLoading(true);
    try {
      const content = lesson.content || JSON.stringify(lesson);
      const q = await getQuiz(session.session_id, module.index, module.title, content, language);
      onStartQuiz(q);
    } catch (err) {
      setError(err.message);
    } finally {
      setQuizLoading(false);
    }
  };

  if (loading) return <div className="spinner" />;
  if (error) return (
    <div className="flash-card card-pink">
      <p style={{ color: '#ea4335' }}>{error}</p>
      <button className="btn btn-secondary" onClick={load}>{t.lesson.retry}</button>
    </div>
  );

  if (sections.length === 0) {
    return (
      <div className="flash-card card-pink">
        <p style={{ color: '#ea4335' }}>{t.lesson.noContent}</p>
        <button className="btn btn-secondary" onClick={onBack}>{t.lesson.backToSyllabus}</button>
      </div>
    );
  }

  const colorClass = CARD_COLORS[currentCard % CARD_COLORS.length];
  const section = sections[currentCard];

  return (
    <div>
      <div className="flash-card card-purple">
        <h2>📖 {lesson?.title || module.title}</h2>
      </div>

      <div key={currentCard} className={`flash-card ${colorClass} card-section`}>
        <button
          className={`tts-btn ${speaking ? 'playing' : ''}`}
          onClick={toggleListening}
          title={speaking ? t.lesson.stop : t.lesson.listen}
        >
          {speaking ? '⏹' : '🔊'}
          <span className="tts-label">{speaking ? t.lesson.stop : t.lesson.listen}</span>
          {speaking && <span className="wave-bars"><span /><span /><span /></span>}
        </button>
        {section.heading && <h3 className="section-heading">{section.heading}</h3>}
        {section.imageUrl && (
          <img src={section.imageUrl} alt={section.heading || ''} className="lesson-image" />
        )}
        <div className="lesson-content">
          {renderLines(section.lines)}
        </div>
      </div>

      {sections.length > 1 && (
        <div className="card-nav">
          <button className="btn btn-sm" onClick={goPrev} disabled={currentCard === 0}>
            {t.lesson.prev}
          </button>
          <div className="nav-dots">
            {sections.map((_, i) => (
              <span
                key={i}
                className={`nav-dot ${i === currentCard ? 'active' : ''}`}
                onClick={() => goTo(i)}
              />
            ))}
          </div>
          <button className="btn btn-sm" onClick={goNext} disabled={currentCard === sections.length - 1}>
            {t.lesson.next}
          </button>
        </div>
      )}

      <div className="card-counter">
        {currentCard + 1} / {sections.length}
      </div>

      {lesson?.key_points && lesson.key_points.length > 0 && (
        <div className="flash-card card-green">
          <div className="section-header">
            <h3>💡 {t.lesson.keyPoints}</h3>
            <button
              className={`tts-btn ${sectionSpeaking === 'key_points' ? 'playing' : ''}`}
              onClick={() => {
                if (sectionSpeaking === 'key_points') {
                  stopSectionSpeech();
                } else {
                  speakSection(lesson.key_points.map(p => p.replace(/\*/g, '')).join('. '), 'key_points');
                }
              }}
              title={sectionSpeaking === 'key_points' ? t.lesson.stop : t.lesson.listen}
            >
              {sectionSpeaking === 'key_points' ? '⏹' : '🔊'}
              <span className="tts-label">{sectionSpeaking === 'key_points' ? t.lesson.stop : t.lesson.listen}</span>
              {sectionSpeaking === 'key_points' && <span className="wave-bars"><span /><span /><span /></span>}
            </button>
          </div>
          <ul className="key-points">
            {lesson.key_points.map((p, i) => (
              <li key={i} style={{ animationDelay: `${i * 0.1}s` }}>{p.replace(/\*/g, '')}</li>
            ))}
          </ul>
        </div>
      )}

      {lesson?.examples && lesson.examples.length > 0 && (
        <div className="flash-card card-orange">
          <div className="section-header">
            <h3>📝 {t.lesson.examples}</h3>
            <button
              className={`tts-btn ${sectionSpeaking === 'examples' ? 'playing' : ''}`}
              onClick={() => {
                if (sectionSpeaking === 'examples') {
                  stopSectionSpeech();
                } else {
                  speakSection(lesson.examples.map(ex => ex.replace(/\*/g, '')).join('. '), 'examples');
                }
              }}
              title={sectionSpeaking === 'examples' ? t.lesson.stop : t.lesson.listen}
            >
              {sectionSpeaking === 'examples' ? '⏹' : '🔊'}
              <span className="tts-label">{sectionSpeaking === 'examples' ? t.lesson.stop : t.lesson.listen}</span>
              {sectionSpeaking === 'examples' && <span className="wave-bars"><span /><span /><span /></span>}
            </button>
          </div>
          <ul className="examples">
            {lesson.examples.map((ex, i) => (
              <li key={i} style={{ animationDelay: `${i * 0.1}s` }}>{ex.replace(/\*\*/g, '')}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="actions">
        <button className="btn btn-secondary" onClick={onBack}>{t.lesson.backToSyllabus}</button>
        <button className="btn btn-success" onClick={handleQuiz} disabled={quizLoading}>
          {quizLoading ? t.lesson.loadingQuiz : t.lesson.startQuiz}
        </button>
      </div>
    </div>
  );
}
