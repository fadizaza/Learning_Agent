import React, { useState } from 'react';
import { submitQuiz } from '../api';

export default function Quiz({ session, module, quiz, onSubmit, onBack }) {
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const questions = quiz?.questions || [];

  const handleSelect = (qIndex, optIndex) => {
    setAnswers((prev) => ({ ...prev, [qIndex]: optIndex }));
  };

  const handleSubmit = async () => {
    const unanswered = questions.filter((_, i) => answers[i] === undefined);
    if (unanswered.length > 0) {
      setError('يرجى الإجابة على جميع الأسئلة قبل الإرسال.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const userAnswers = questions.map((_, i) => answers[i]);
      const correctAnswers = questions.map((q) => q.correct_answer);
      const result = await submitQuiz(
        session.session_id,
        module.index,
        questions,
        userAnswers,
        correctAnswers
      );
      onSubmit(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (questions.length === 0) {
    return (
      <div className="flash-card card-pink" style={{ textAlign: 'center' }}>
        <h2>🧪 اختبار</h2>
        <p>لا توجد أسئلة متاحة.</p>
        <button className="btn btn-secondary" onClick={onBack}>🔙 رجوع</button>
      </div>
    );
  }

  return (
    <div>
      <div className="flash-card card-purple" style={{ textAlign: 'center' }}>
        <h2>🧪 اختبار: {module.title}</h2>
        <p style={{ fontSize: 14, color: '#888' }}>أجب على جميع الأسئلة لإكمال هذه الوحدة</p>
      </div>

      {questions.map((q, qi) => (
        <div key={qi} className="flash-card card-blue" style={{ animationDelay: `${qi * 0.15}s` }}>
          <div className="quiz-question">
            <h3><span style={{ color: '#764ba2' }}>س{qi + 1}:</span> {q.question}</h3>
            {q.options.map((opt, oi) => (
              <label
                key={oi}
                className={`quiz-option ${answers[qi] === oi ? 'selected' : ''}`}
                onClick={() => handleSelect(qi, oi)}
                style={{ animationDelay: `${oi * 0.08}s` }}
              >
                {opt}
              </label>
            ))}
          </div>
        </div>
      ))}

      {error && <p style={{ color: '#ea4335', fontSize: 14, marginBottom: 12, textAlign: 'center' }}>{error}</p>}

      <div className="actions" style={{ justifyContent: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>🔙 العودة إلى المنهج</button>
        <button className="btn btn-success" onClick={handleSubmit} disabled={submitting}>
          {submitting ? 'جارٍ التقييم...' : '✅ إرسال الإجابات'}
        </button>
      </div>
    </div>
  );
}
