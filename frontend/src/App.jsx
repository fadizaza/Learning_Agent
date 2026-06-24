import React, { useState, useEffect } from 'react';
import Home from './components/Home';
import Syllabus from './components/Syllabus';
import Lesson from './components/Lesson';
import Quiz from './components/Quiz';
import Results from './components/Results';
import { getTranslation } from './i18n';
import './App.css';

const STEPS = { HOME: 'home', SYLLABUS: 'syllabus', LESSON: 'lesson', QUIZ: 'quiz', RESULTS: 'results' };

export default function App() {
  const [step, setStep] = useState(STEPS.HOME);
  const [session, setSession] = useState(null);
  const [activeModule, setActiveModule] = useState(null);
  const [lesson, setLesson] = useState(null);
  const [quiz, setQuiz] = useState(null);
  const [results, setResults] = useState(null);
  const [language, setLanguage] = useState('ar');

  const t = getTranslation(language);

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
  }, [language]);

  const toggleLanguage = () => {
    setLanguage((prev) => (prev === 'ar' ? 'en' : 'ar'));
  };

  const handleStart = (s) => {
    setSession(s);
    setStep(STEPS.SYLLABUS);
  };

  const handleSelectModule = async (mod, index) => {
    setActiveModule({ ...mod, index });
    setStep(STEPS.LESSON);
  };

  const handleLessonReady = (l) => {
    setLesson(l);
  };

  const handleStartQuiz = (q) => {
    setQuiz(q);
    setStep(STEPS.QUIZ);
  };

  const handleQuizSubmit = (r) => {
    setResults(r);
    setStep(STEPS.RESULTS);
  };

  const handleBackToLesson = () => {
    setQuiz(null);
    setResults(null);
    setStep(STEPS.LESSON);
  };

  const handleBackToSyllabus = () => {
    setActiveModule(null);
    setLesson(null);
    setQuiz(null);
    setResults(null);
    setStep(STEPS.SYLLABUS);
  };

  const handleNewTopic = () => {
    setSession(null);
    setActiveModule(null);
    setLesson(null);
    setQuiz(null);
    setResults(null);
    setStep(STEPS.HOME);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>{t.appTitle}</h1>
        <div className="header-right">
          {session && (
            <div className="session-info">
              <span>{session.grade} — {session.subject} — {session.topic}</span>
              <span className="badge">
                {session.level === 'Beginner' ? t.levelBeginner : session.level === 'Intermediate' ? t.levelIntermediate : t.levelAdvanced}
              </span>
            </div>
          )}
          <button className="lang-toggle" onClick={toggleLanguage}>
            {language === 'ar' ? 'EN' : 'ع'}
          </button>
        </div>
      </header>
      <main className="app-main">
        {step === STEPS.HOME && <Home onStart={handleStart} language={language} t={t} />}
        {step === STEPS.SYLLABUS && session && (
          <Syllabus
            session={session}
            onSelectModule={handleSelectModule}
            onNewTopic={handleNewTopic}
            language={language}
            t={t}
          />
        )}
        {step === STEPS.LESSON && session && activeModule && (
          <Lesson
            session={session}
            module={activeModule}
            onLessonReady={handleLessonReady}
            onStartQuiz={handleStartQuiz}
            onBack={handleBackToSyllabus}
            language={language}
            t={t}
          />
        )}
        {step === STEPS.QUIZ && session && activeModule && quiz && (
          <Quiz
            session={session}
            module={activeModule}
            quiz={quiz}
            lesson={lesson}
            onSubmit={handleQuizSubmit}
            onBack={handleBackToLesson}
            language={language}
            t={t}
          />
        )}
        {step === STEPS.RESULTS && session && activeModule && (
          <Results
            session={session}
            module={activeModule}
            results={results}
            onContinue={handleBackToSyllabus}
            onNewTopic={handleNewTopic}
            language={language}
            t={t}
          />
        )}
      </main>
    </div>
  );
}
