import React, { useState } from 'react';
import Home from './components/Home';
import Syllabus from './components/Syllabus';
import Lesson from './components/Lesson';
import Quiz from './components/Quiz';
import Results from './components/Results';
import './App.css';

const STEPS = { HOME: 'home', SYLLABUS: 'syllabus', LESSON: 'lesson', QUIZ: 'quiz', RESULTS: 'results' };

export default function App() {
  const [step, setStep] = useState(STEPS.HOME);
  const [session, setSession] = useState(null);
  const [activeModule, setActiveModule] = useState(null);
  const [lesson, setLesson] = useState(null);
  const [quiz, setQuiz] = useState(null);
  const [results, setResults] = useState(null);

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
        <h1>وكيل التعلم الذكي</h1>
        {session && (
          <div className="session-info">
            <span>{session.grade} — {session.subject} — {session.topic}</span>
            <span className="badge">{session.level === 'Beginner' ? 'مبتدئ' : session.level === 'Intermediate' ? 'متوسط' : 'متقدم'}</span>
          </div>
        )}
      </header>
      <main className="app-main">
        {step === STEPS.HOME && <Home onStart={handleStart} />}
        {step === STEPS.SYLLABUS && session && (
          <Syllabus
            session={session}
            onSelectModule={handleSelectModule}
            onNewTopic={handleNewTopic}
          />
        )}
        {step === STEPS.LESSON && session && activeModule && (
          <Lesson
            session={session}
            module={activeModule}
            onLessonReady={handleLessonReady}
            onStartQuiz={handleStartQuiz}
            onBack={handleBackToSyllabus}
          />
        )}
        {step === STEPS.QUIZ && session && activeModule && quiz && (
          <Quiz
            session={session}
            module={activeModule}
            quiz={quiz}
            lesson={lesson}
            onSubmit={handleQuizSubmit}
            onBack={handleBackToSyllabus}
          />
        )}
        {step === STEPS.RESULTS && session && activeModule && (
          <Results
            session={session}
            module={activeModule}
            results={results}
            onContinue={handleBackToSyllabus}
            onNewTopic={handleNewTopic}
          />
        )}
      </main>
    </div>
  );
}
