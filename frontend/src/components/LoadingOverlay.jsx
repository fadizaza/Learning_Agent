import React, { useEffect, useState } from 'react';

function TimeBasedLoading({ steps }) {
  const [activeStep, setActiveStep] = useState(0);
  const [progress, setProgress] = useState(0);

  const totalDuration = steps.reduce((sum, s) => sum + s.duration, 0);

  useEffect(() => {
    const start = Date.now();
    let raf;

    const tick = () => {
      const elapsed = Date.now() - start;

      let acc = 0;
      for (let i = 0; i < steps.length; i++) {
        if (elapsed < acc + steps[i].duration) {
          setActiveStep(i);
          const stepProgress = (elapsed - acc) / steps[i].duration;
          const prevStepsProgress = steps.slice(0, i).reduce((s, st) => s + st.duration, 0);
          const overall = prevStepsProgress + stepProgress * steps[i].duration;
          setProgress(Math.min((overall / totalDuration) * 90, 90));
          break;
        }
        acc += steps[i].duration;
      }

      if (elapsed < totalDuration) {
        raf = requestAnimationFrame(tick);
      } else {
        setActiveStep(steps.length - 1);
        setProgress(90);
      }
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [steps, totalDuration]);

  const step = steps[activeStep];

  return (
    <div className="loading-overlay">
      <div className="loading-card flash-card card-purple">
        <div className="loading-agent-badge">
          <span className="loading-agent-icon">{step.icon || '🤖'}</span>
          <span className="loading-agent-name">{step.agentName}</span>
        </div>

        <div className="loading-steps-track">
          {steps.map((s, i) => (
            <div key={i} className={`loading-step-dot ${i < activeStep ? 'done' : ''} ${i === activeStep ? 'active' : ''}`}>
              <span className="step-number">{i < activeStep ? '✓' : i + 1}</span>
              <span className="step-label">{s.shortLabel}</span>
            </div>
          ))}
        </div>

        <div className="loading-spinner-row">
          <div className="loading-spinner" />
          <div className="loading-text">
            <p className="loading-message">{step.message}</p>
            {step.subMessage && <p className="loading-sub-message">{step.subMessage}</p>}
          </div>
        </div>

        <div className="loading-progress-container">
          <div className="loading-progress-bar">
            <div className="loading-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="loading-progress-text">{Math.round(progress)}%</span>
        </div>

        <div className="loading-dots">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      </div>
    </div>
  );
}

function getStepIcon(step) {
  switch (step) {
    case 'content': return '📝';
    case 'content_retry': return '🔄';
    case 'validator': return '🔍';
    case 'quality': return '✅';
    case 'quiz': return '🧪';
    case 'quiz_retry': return '🔄';
    default: return '🤖';
  }
}

function getStepLabel(step, t) {
  const p = t.loading.pipeline;
  switch (step) {
    case 'content': return p.lesson1?.short || 'Content';
    case 'content_retry': return p.lesson1?.short || 'Content';
    case 'validator': return p.lesson2?.short || 'Validator';
    case 'quality': return p.lesson3?.short || 'Quality';
    case 'quiz': return p.quiz1?.short || 'Quiz';
    case 'quiz_retry': return p.quiz1?.short || 'Quiz';
    default: return step;
  }
}

function getAgentMessage(step, t) {
  const p = t.loading.pipeline;
  switch (step) {
    case 'content': return p.lesson1?.message || 'Generating content...';
    case 'content_retry': return 'Regenerating content...';
    case 'validator': return p.lesson2?.message || 'Validating...';
    case 'quality': return p.lesson3?.message || 'Checking quality...';
    case 'quiz': return p.quiz1?.message || 'Creating quiz...';
    case 'quiz_retry': return 'Regenerating quiz...';
    default: return 'Processing...';
  }
}

function StreamBasedLoading({ pipelineState, t }) {
  const { learningOutcomes, steps, currentAgent, currentStep, completedSteps, validationResults } = pipelineState;
  const agentMap = t.loading.agentMap || {};
  const criteriaMap = t.loading.criteriaMap || {};

  const completedStepsList = completedSteps.map(s => s.step);
  const allSteps = steps.length > 0 ? steps : ['content', 'validator', 'quality'];

  const completedScore = completedSteps.reduce((sum, s) => {
    if (s.score) return sum + s.score;
    return sum + (s.result === 'success' || s.result === 'approved' ? 100 : 0);
  }, 0);
  const completedCount = completedSteps.length;
  const totalSteps = allSteps.length;
  const progress = totalSteps > 0 ? Math.min(((completedCount) / totalSteps) * 90, 90) : 0;

  return (
    <div className="loading-overlay">
      <div className="loading-card flash-card card-purple">
        <div className="loading-agent-badge">
          <span className="loading-agent-icon">{currentAgent ? getStepIcon(currentStep) : '🤖'}</span>
          <span className="loading-agent-name">{currentAgent ? (agentMap[currentAgent] || currentAgent) : 'Pipeline'}</span>
        </div>

        {learningOutcomes.length > 0 && (
          <div className="loading-learning-outcomes">
            <div className="loading-lo-header">
              <span className="loading-lo-icon">🎯</span>
              <span className="loading-lo-title">{t.loading.learningOutcomes || 'Learning Outcomes'}</span>
            </div>
            <ul className="loading-lo-list">
              {learningOutcomes.map((outcome, i) => (
                <li key={i} className="loading-lo-item">
                  <span className="loading-lo-check">✓</span>
                  <span className="loading-lo-text">{outcome}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="loading-steps-track">
          {allSteps.map((step, i) => {
            const isDone = completedStepsList.includes(step);
            const isActive = currentStep === step;
            return (
              <div key={i} className={`loading-step-dot ${isDone ? 'done' : ''} ${isActive ? 'active' : ''}`}>
                <span className="step-number">{isDone ? '✓' : i + 1}</span>
                <span className="step-label">{getStepLabel(step, t)}</span>
              </div>
            );
          })}
        </div>

        {currentAgent && (
          <div className="loading-spinner-row">
            <div className="loading-spinner" />
            <div className="loading-text">
              <p className="loading-message">{getAgentMessage(currentStep, t)}</p>
              <p className="loading-sub-message">{t.loading.contactingAI || 'Contacting AI model...'}</p>
            </div>
          </div>
        )}

        {completedSteps.length > 0 && (
          <div className="loading-completed-steps">
            {completedSteps.map((step, i) => (
              <div key={i} className={`loading-completed-step ${step.result === 'success' || step.result === 'approved' ? 'success' : 'rejected'}`}>
                <div className="completed-step-header">
                  <span className="completed-step-icon">
                    {step.result === 'success' || step.result === 'approved' ? '✓' : '✗'}
                  </span>
                   <span className="completed-step-agent">{agentMap[step.agent] || step.agent}</span>
                  {step.score !== undefined && (
                    <span className="completed-step-score">{step.score}/100</span>
                  )}
                  <span className={`completed-step-status ${step.result}`}>
                    {step.result === 'approved' ? (t.loading.approved || 'APPROVED') :
                     step.result === 'rejected' ? (t.loading.rejected || 'REJECTED') :
                     step.result === 'success' ? (t.loading.success || 'SUCCESS') :
                     step.result}
                  </span>
                </div>

                {step.criteria && Object.keys(step.criteria).length > 0 && (
                  <div className="completed-step-criteria">
                    {Object.entries(step.criteria).map(([key, value]) => (
                      <div key={key} className="criteria-row">
                        <span className="criteria-name">{criteriaMap[key] || key}</span>
                        <div className="criteria-bar-container">
                          <div className="criteria-bar" style={{ width: `${value}%` }} />
                        </div>
                        <span className="criteria-value">{value}%</span>
                      </div>
                    ))}
                  </div>
                )}

                {step.issues && step.issues.length > 0 && (
                  <div className="completed-step-issues">
                    <span className="issues-label">{t.loading.issues || 'Issues:'}</span>
                    {step.issues.map((issue, j) => (
                      <span key={j} className="issue-item">• {issue}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="loading-progress-container">
          <div className="loading-progress-bar">
            <div className="loading-progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="loading-progress-text">{Math.round(progress)}%</span>
        </div>

        <div className="loading-dots">
          <span className="dot" />
          <span className="dot" />
          <span className="dot" />
        </div>
      </div>
    </div>
  );
}

export default function LoadingOverlay({ steps, pipelineState, t }) {
  if (pipelineState) {
    return <StreamBasedLoading pipelineState={pipelineState} t={t} />;
  }
  return <TimeBasedLoading steps={steps} />;
}
