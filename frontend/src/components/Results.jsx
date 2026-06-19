import React from 'react';

const GRADE_EMOJI = {
  'ممتاز!': '🏆',
  'أحسنت!': '🌟',
  'واصل التدريب!': '💪',
  'بحاجة إلى تحسين': '📚',
};

export default function Results({ session, module, results, onContinue, onNewTopic }) {
  if (!results) {
    return (
      <div className="flash-card card-pink" style={{ textAlign: 'center' }}>
        <h2>📊 النتائج</h2>
        <p>لا توجد نتائج متاحة.</p>
        <div className="actions" style={{ justifyContent: 'center' }}>
          <button className="btn btn-secondary" onClick={onContinue}>🔙 العودة إلى المنهج</button>
        </div>
      </div>
    );
  }

  const score = Math.round(results.score || 0);
  const grade = score >= 80 ? 'ممتاز!' : score >= 60 ? 'أحسنت!' : score >= 40 ? 'واصل التدريب!' : 'بحاجة إلى تحسين';
  const emoji = GRADE_EMOJI[grade];

  return (
    <div>
      <div className="flash-card card-purple" style={{ textAlign: 'center' }}>
        <h2>📊 نتائج الاختبار: {module.title}</h2>
        <div className="result-score">
          <div className="score-value">{score}%</div>
          <div className="score-label">
            <span style={{ fontSize: 24 }}>{emoji}</span> {grade}
          </div>
          <div className="score-label" style={{ marginTop: 6 }}>
            {results.correct_count} من {results.total_questions} إجابات صحيحة
          </div>
        </div>
      </div>

      <div className="flash-card card-blue">
        <h3>💬 التعليقات</h3>
        <p className="result-feedback">{results.feedback}</p>
      </div>

      {results.weak_areas && results.weak_areas.length > 0 && (
        <div className="flash-card card-pink">
          <h3>🎯 مجالات التحسين</h3>
          <ul className="weak-areas">
            {results.weak_areas.map((area, i) => (
              <li key={i} style={{ animationDelay: `${i * 0.1}s` }}>{area}</li>
            ))}
          </ul>
        </div>
      )}

      {results.next_steps && (
        <div className="flash-card card-green">
          <h3>🚀 الخطوات التالية</h3>
          <p className="result-feedback">{results.next_steps}</p>
        </div>
      )}

      <div className="actions" style={{ justifyContent: 'center' }}>
        <button className="btn btn-primary" onClick={onContinue}>🔙 العودة إلى المنهج</button>
        <button className="btn btn-secondary" onClick={onNewTopic}>➕ موضوع جديد</button>
      </div>
    </div>
  );
}
