import React, { useEffect, useState } from 'react';

export default function LoadingOverlay({ steps }) {
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
