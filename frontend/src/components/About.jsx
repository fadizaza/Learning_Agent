import React, { useState } from 'react';
import { getTranslation } from '../i18n';
import './About.css';

export default function About() {
  const [language, setLanguage] = useState('ar');
  const t = getTranslation(language);

  const toggleLanguage = () => {
    setLanguage((prev) => (prev === 'ar' ? 'en' : 'ar'));
  };

  const isAr = language === 'ar';

  return (
    <div className={`about-page ${isAr ? 'rtl' : 'ltr'}`}>
      <button className="about-lang-toggle" onClick={toggleLanguage}>
        {isAr ? 'EN' : 'ع'}
      </button>

      <div className="about-card">
        <div className="about-logo">🎓</div>
        <h1 className="about-title">
          {isAr ? 'Learning Agent' : 'Learning Agent'}
        </h1>
        <p className="about-subtitle">
          {isAr
            ? 'منصة تعلم تكيفية مدعومة بالذكاء الاصطناعي'
            : 'AI-Powered Adaptive Learning Platform'}
        </p>

        <div className="about-section">
          <h2>{isAr ? 'عن المنصة' : 'About the Platform'}</h2>
          <p>
            {isAr
              ? 'Learning Agent منصة تعليمية ذكية تستخدم الذكاء الاصطناعي لإنشاء دروس تفاعلية مخصصة لكل طالب. تقدم المنهج دروساً وأسئلة وتقييمات متنوعة تتكيف مع مستوى الطالب واحتياجاته التعليمية.'
              : 'Learning Agent is an intelligent educational platform that uses AI to generate personalized interactive lessons for every student. The curriculum includes lessons, quizzes, and assessments that adapt to the student\'s level and learning needs.'}
          </p>
        </div>

        <div className="about-section">
          <h2>{isAr ? 'المميزات' : 'Features'}</h2>
          <ul className="about-features">
            <li>
              <span className="feature-icon">📚</span>
              <span>{isAr ? 'منهج تعليمي مخصص بالذكاء الاصطناعي' : 'AI-generated personalized curriculum'}</span>
            </li>
            <li>
              <span className="feature-icon">🎯</span>
              <span>{isAr ? 'دروس تفاعلية مع نقاط تحقق' : 'Interactive lessons with checkpoints'}</span>
            </li>
            <li>
              <span className="feature-icon">🧩</span>
              <span>{isAr ? 'مسارات تعلم تكيفية (追-up و level-up)' : 'Adaptive learning paths (catch-up & level-up)'}</span>
            </li>
            <li>
              <span className="feature-icon">📝</span>
              <span>{isAr ? 'اختبارات وتقييمات فورية' : 'Quizzes and instant assessments'}</span>
            </li>
            <li>
              <span className="feature-icon">🌍</span>
              <span>{isAr ? 'دعم اللغة العربية والإنجليزية' : 'Arabic and English language support'}</span>
            </li>
            <li>
              <span className="feature-icon">🎮</span>
              <span>{isAr ? 'gamification مع مكافآت رقمية' : 'Gamification with digital rewards'}</span>
            </li>
          </ul>
        </div>

        <div className="about-section">
          <h2>{isAr ? 'التقنيات' : 'Technologies'}</h2>
          <div className="about-tags">
            <span className="tag">React</span>
            <span className="tag">FastAPI</span>
            <span className="tag">Python</span>
            <span className="tag">Mistral AI</span>
            <span className="tag">SQLite</span>
            <span className="tag">Edge TTS</span>
          </div>
        </div>

        <div className="about-section about-contact">
          <h2>{isAr ? 'تواصل معي' : 'Contact'}</h2>
          <p className="about-developer">
            {isAr ? 'المطور' : 'Developer'}: <strong>Fadi Zaza</strong>
          </p>
          <a href="mailto:fadizaza@gmail.com" className="about-email">
            📧 fadizaza@gmail.com
          </a>
        </div>

        <div className="about-footer">
          <p>© 2026 Learning Agent. {isAr ? 'جميع الحقوق محفوظة' : 'All rights reserved.'}</p>
        </div>
      </div>
    </div>
  );
}
