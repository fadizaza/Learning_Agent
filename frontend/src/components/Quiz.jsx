import React, { useState, useCallback } from 'react';
import { submitQuiz } from '../api';

export default function Quiz({ session, module, quiz, onSubmit, onBack, language, t }) {
  const [answers, setAnswers] = useState({});
  const [submittedQuestions, setSubmittedQuestions] = useState({});
  const [questionResults, setQuestionResults] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [quizComplete, setQuizComplete] = useState(false);
  const [finalResults, setFinalResults] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isRetryMode, setIsRetryMode] = useState(false);
  const [retryQuestions, setRetryQuestions] = useState([]);

  const questions = isRetryMode ? retryQuestions : (quiz?.questions || []);

  const handleSelect = useCallback((qIndex, optIndex) => {
    if (submittedQuestions[qIndex]) return;
    setAnswers((prev) => ({ ...prev, [qIndex]: optIndex }));
  }, [submittedQuestions]);

  const checkAnswer = useCallback((qIndex) => {
    if (answers[qIndex] === undefined || submittedQuestions[qIndex]) return;

    const question = questions[qIndex];
    const isCorrect = answers[qIndex] === question.correct_answer;

    setSubmittedQuestions((prev) => ({ ...prev, [qIndex]: true }));
    setQuestionResults((prev) => ({
      ...prev,
      [qIndex]: {
        isCorrect,
        userAnswer: answers[qIndex],
        correctAnswer: question.correct_answer,
      },
    }));
  }, [answers, submittedQuestions, questions]);

  const handleSubmitAll = async () => {
    const allQuestions = isRetryMode ? retryQuestions : quiz?.questions || [];
    const unanswered = allQuestions.filter((_, i) => {
      const actualIndex = isRetryMode ? i : i;
      return answers[actualIndex] === undefined;
    });

    if (unanswered.length > 0) {
      setError(t.quiz.allAnswered);
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const userAnswers = allQuestions.map((_, i) => answers[i]);
      const correctAnswers = allQuestions.map((q) => q.correct_answer);

      const result = await submitQuiz(
        session.session_id,
        module.index,
        allQuestions,
        userAnswers,
        correctAnswers,
        language,
        retryCount
      );

      setFinalResults(result);
      setQuizComplete(true);
      onSubmit(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetryWrong = () => {
    const allQuestions = quiz?.questions || [];
    const wrongIndices = [];

    allQuestions.forEach((_, i) => {
      if (questionResults[i] && !questionResults[i].isCorrect) {
        wrongIndices.push(i);
      }
    });

    if (wrongIndices.length === 0) {
      return;
    }

    const wrongQuestions = wrongIndices.map((i) => allQuestions[i]);

    setRetryQuestions(wrongQuestions);
    setIsRetryMode(true);
    setRetryCount((prev) => prev + 1);

    const newAnswers = {};
    const newSubmitted = {};
    const newResults = {};

    wrongIndices.forEach((origIdx, newIdx) => {
      newAnswers[newIdx] = undefined;
      newSubmitted[newIdx] = false;
      newResults[newIdx] = undefined;
    });

    setAnswers(newAnswers);
    setSubmittedQuestions(newSubmitted);
    setQuestionResults(newResults);
    setQuizComplete(false);
    setFinalResults(null);
  };

  const allAnswered = questions.every((_, i) => answers[i] !== undefined);
  const allSubmitted = questions.every((_, i) => submittedQuestions[i]);
  const wrongCount = Object.values(questionResults).filter((r) => r && !r.isCorrect).length;

  if (questions.length === 0) {
    return (
      <div className="flash-card card-pink" style={{ textAlign: 'center' }}>
        <h2>🧪 {t.quiz.title}</h2>
        <p>{t.quiz.noQuestions}</p>
        <button className="btn btn-secondary" onClick={onBack}>{t.quiz.back}</button>
      </div>
    );
  }

  return (
    <div>
      <div className="flash-card card-purple" style={{ textAlign: 'center' }}>
        <h2>🧪 {t.quiz.title}: {module.title}</h2>
        {isRetryMode ? (
          <p style={{ fontSize: 14, color: '#f39c12' }}>
            {t.quiz.retryMode || 'Retry Mode'} — {questions.length} {t.quiz.wrongQuestions || 'wrong questions'}
          </p>
        ) : (
          <p style={{ fontSize: 14, color: '#888' }}>{t.quiz.answerAll}</p>
        )}
        {!isRetryMode && (
          <p style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
            {t.quiz.questionCount?.replace('{count}', questions.length) || `${questions.length} questions`}
          </p>
        )}
      </div>

      {questions.map((q, qi) => {
        const isSubmitted = submittedQuestions[qi];
        const result = questionResults[qi];

        let cardClass = 'card-blue';
        if (isSubmitted) {
          cardClass = result?.isCorrect ? 'card-green' : 'card-pink';
        }

        return (
          <div key={isRetryMode ? `retry-${qi}` : qi} className={`flash-card ${cardClass}`} style={{ animationDelay: `${qi * 0.15}s` }}>
            <div className="quiz-question">
              <h3>
                <span style={{ color: '#764ba2' }}>{t.quiz.questionPrefix}{qi + 1}:</span> {q.question}
              </h3>
              {q.options.map((opt, oi) => {
                let optionClass = 'quiz-option';
                if (answers[qi] === oi) {
                  optionClass += ' selected';
                }
                if (isSubmitted) {
                  if (oi === q.correct_answer) {
                    optionClass += ' correct';
                  } else if (answers[qi] === oi && oi !== q.correct_answer) {
                    optionClass += ' incorrect';
                  }
                }

                return (
                  <label
                    key={oi}
                    className={optionClass}
                    onClick={() => handleSelect(qi, oi)}
                    style={{
                      animationDelay: `${oi * 0.08}s`,
                      cursor: isSubmitted ? 'default' : 'pointer',
                    }}
                  >
                    {opt}
                    {isSubmitted && oi === q.correct_answer && (
                      <span className="option-indicator correct-indicator">✓</span>
                    )}
                    {isSubmitted && answers[qi] === oi && oi !== q.correct_answer && (
                      <span className="option-indicator incorrect-indicator">✗</span>
                    )}
                  </label>
                );
              })}

              {!isSubmitted && answers[qi] !== undefined && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => checkAnswer(qi)}
                  style={{ marginTop: 10 }}
                >
                  {t.quiz.checkAnswer || 'Check Answer'}
                </button>
              )}

              {isSubmitted && q.explanation && (
                <div className={`explanation ${result?.isCorrect ? 'explanation-correct' : 'explanation-incorrect'}`}>
                  <strong>{result?.isCorrect ? (t.quiz.correctAnswer || '✓ Correct!') : (t.quiz.wrongAnswer || '✗ Incorrect')}:</strong> {q.explanation}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {error && <p style={{ color: '#ea4335', fontSize: 14, marginBottom: 12, textAlign: 'center' }}>{error}</p>}

      <div className="flash-card card-orange" style={{ textAlign: 'center' }}>
        <h3>📊 {t.quiz.progress || 'Progress'}</h3>
        <p style={{ fontSize: 16, margin: '10px 0' }}>
          {Object.values(questionResults).filter((r) => r?.isCorrect).length} / {questions.length} {t.quiz.correct || 'correct'}
        </p>
        {allSubmitted && !quizComplete && wrongCount > 0 && retryCount === 0 && (
          <button className="btn btn-primary" onClick={handleRetryWrong} style={{ marginTop: 10 }}>
            {t.quiz.retryWrong?.replace('{count}', wrongCount) || `Retry ${wrongCount} Wrong Questions`}
          </button>
        )}
      </div>

      <div className="actions" style={{ justifyContent: 'center' }}>
        <button className="btn btn-secondary" onClick={onBack}>{t.quiz.backToSyllabus}</button>
        {!isRetryMode && allAnswered && !quizComplete && (
          <button className="btn btn-success" onClick={handleSubmitAll} disabled={submitting}>
            {submitting ? t.quiz.submitting : t.quiz.submit}
          </button>
        )}
        {isRetryMode && allAnswered && !quizComplete && (
          <button className="btn btn-success" onClick={handleSubmitAll} disabled={submitting}>
            {submitting ? t.quiz.submitting : t.quiz.submitRetry || 'Submit Retry'}
          </button>
        )}
      </div>
    </div>
  );
}
