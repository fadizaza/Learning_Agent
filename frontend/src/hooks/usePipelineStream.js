import { useState, useRef, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function usePipelineStream() {
  const [pipelineState, setPipelineState] = useState({
    learningOutcomes: [],
    moduleDescription: '',
    moduleTitle: '',
    steps: [],
    currentAgent: null,
    currentStep: null,
    currentAttempt: 1,
    completedSteps: [],
    validationResults: {},
    isComplete: false,
    result: null,
    error: null,
  });

  const eventSourceRef = useRef(null);

  const startLessonStream = useCallback((sessionId, moduleIndex, moduleTitle, language = 'ar') => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setPipelineState({
      learningOutcomes: [],
      moduleDescription: '',
      moduleTitle: '',
      steps: [],
      currentAgent: null,
      currentStep: null,
      completedSteps: [],
      validationResults: {},
      isComplete: false,
      result: null,
      error: null,
    });

    const body = JSON.stringify({ session_id: sessionId, module_index: moduleIndex, module_title: moduleTitle, language });

    fetch(`${API_BASE}/api/lessons/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    }).then(response => {
      if (!response.ok) {
        throw new Error('Stream failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventType = '';
      let eventData = '';

      const processChunk = ({ done, value }) => {
        if (done) return;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6);
          } else if (line === '' && eventType && eventData) {
            try {
              const data = JSON.parse(eventData);
              handleEvent(eventType, data);
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
            eventType = '';
            eventData = '';
          }
        }

        reader.read().then(processChunk);
      };

      reader.read().then(processChunk);
    }).catch(err => {
      setPipelineState(prev => ({ ...prev, error: err.message }));
    });

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const startQuizStream = useCallback((sessionId, moduleIndex, moduleTitle, lessonContent, language = 'ar') => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setPipelineState({
      learningOutcomes: [],
      moduleDescription: '',
      moduleTitle: '',
      steps: [],
      currentAgent: null,
      currentStep: null,
      completedSteps: [],
      validationResults: {},
      isComplete: false,
      result: null,
      error: null,
    });

    const body = JSON.stringify({ session_id: sessionId, module_index: moduleIndex, module_title: moduleTitle, lesson_content: lessonContent, language });

    fetch(`${API_BASE}/api/quiz/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    }).then(response => {
      if (!response.ok) {
        throw new Error('Stream failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventType = '';
      let eventData = '';

      const processChunk = ({ done, value }) => {
        if (done) return;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6);
          } else if (line === '' && eventType && eventData) {
            try {
              const data = JSON.parse(eventData);
              handleEvent(eventType, data);
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
            eventType = '';
            eventData = '';
          }
        }

        reader.read().then(processChunk);
      };

      reader.read().then(processChunk);
    }).catch(err => {
      setPipelineState(prev => ({ ...prev, error: err.message }));
    });

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleEvent = useCallback((eventType, data) => {
    switch (eventType) {
      case 'pipeline_started':
        setPipelineState(prev => ({
          ...prev,
          learningOutcomes: data.learning_outcomes || [],
          moduleDescription: data.module_description || '',
          moduleTitle: data.module_title || '',
          steps: data.steps || [],
        }));
        break;

      case 'agent_started':
        setPipelineState(prev => ({
          ...prev,
          currentAgent: data.agent,
          currentStep: data.step,
          currentAttempt: data.attempt || 1,
        }));
        break;

      case 'agent_completed':
        setPipelineState(prev => {
          const newCompleted = [...prev.completedSteps, {
            agent: data.agent,
            step: data.step,
            result: data.result,
            score: data.score,
            criteria: data.criteria || {},
            issues: data.issues || [],
            suggestions: data.suggestions || [],
            attempt: data.attempt || 1,
          }];

          const newValidationResults = { ...prev.validationResults };
          if (data.criteria && Object.keys(data.criteria).length > 0) {
            newValidationResults[data.step] = {
              score: data.score,
              criteria: data.criteria,
              result: data.result,
              issues: data.issues || [],
              suggestions: data.suggestions || [],
            };
          }

          return {
            ...prev,
            completedSteps: newCompleted,
            validationResults: newValidationResults,
            currentAgent: null,
            currentStep: null,
            currentAttempt: 1,
          };
        });
        break;

      case 'lesson_ready':
        setPipelineState(prev => ({
          ...prev,
          isComplete: true,
          result: data.lesson,
          learningOutcomes: data.learning_outcomes || prev.learningOutcomes,
        }));
        break;

      case 'quiz_ready':
        setPipelineState(prev => ({
          ...prev,
          isComplete: true,
          result: data.quiz,
        }));
        break;

      case 'error':
        setPipelineState(prev => ({
          ...prev,
          error: data.message,
        }));
        break;

      default:
        break;
    }
  }, []);

  return {
    pipelineState,
    startLessonStream,
    startQuizStream,
  };
}
