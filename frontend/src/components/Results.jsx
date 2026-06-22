import React from 'react';

export default function Results({ session, module, results, onContinue, onNewTopic, language, t }) {
  if (!results) {
    return (
      <div className="flash-card card-pink" style={{ textAlign: 'center' }}>
        <h2>📊 {t.results.title}</h2>
        <p>{t.results.noResults}</p>
        <div className="actions" style={{ justifyContent: 'center' }}>
          <button className="btn btn-secondary" onClick={onContinue}>{t.results.backToSyllabus}</button>
        </div>
      </div>
    );
  }

  const score = Math.round(results.score || 0);
  const gradeText = score >= 80 ? t.results.gradeExcellent : score >= 60 ? t.results.gradeGood : score >= 40 ? t.results.gradePractice : t.results.gradeImprove;
  const emoji = score >= 80 ? '🏆' : score >= 60 ? '🌟' : score >= 40 ? '💪' : '📚';

  return (
    <div>
      <div className="flash-card card-purple" style={{ textAlign: 'center' }}>
        <h2>📊 {t.results.quizResults}: {module.title}</h2>
        <div className="result-score">
          <div className="score-value">{score}%</div>
          <div className="score-label">
            <span style={{ fontSize: 24 }}>{emoji}</span> {gradeText}
          </div>
          <div className="score-label" style={{ marginTop: 6 }}>
            {results.correct_count} / {results.total_questions} {t.results.correctOf}
          </div>
        </div>
      </div>

      <div className="flash-card card-blue">
        <h3>💬 {t.results.feedback}</h3>
        <p className="result-feedback">{results.feedback}</p>
      </div>

      {results.weak_areas && results.weak_areas.length > 0 && (
        <div className="flash-card card-pink">
          <h3>🎯 {t.results.improvementAreas}</h3>
          <ul className="weak-areas">
            {results.weak_areas.map((area, i) => (
              <li key={i} style={{ animationDelay: `${i * 0.1}s` }}>{area}</li>
            ))}
          </ul>
        </div>
      )}

      {results.next_steps && (
        <div className="flash-card card-green">
          <h3>🚀 {t.results.nextSteps}</h3>
          <p className="result-feedback">{results.next_steps}</p>
        </div>
      )}

      <div className="actions" style={{ justifyContent: 'center' }}>
        <button className="btn btn-primary" onClick={onContinue}>{t.results.backToSyllabus}</button>
        <button className="btn btn-secondary" onClick={onNewTopic}>{t.results.newTopic}</button>
      </div>
    </div>
  );
}
