import { useState, useCallback } from 'react';
import { useChatStore } from '../stores/useAppStore';
import { api } from '../api/client';
import type { ExplainRequest, ExplainResponse, QuizRequest, QuizResponse, QuizQuestion, ExplanationLevel, Citation, LearningReportRequest, LearningReportResponse } from '../api/client';

export default function Learn() {
  const { sessionId, messages } = useChatStore();

  // Explain tab state
  const [explainQuestion, setExplainQuestion] = useState('');
  const [explainLevel, setExplainLevel] = useState<ExplanationLevel>('intermediate');
  const [explainResponse, setExplainResponse] = useState<ExplainResponse | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);

  // Quiz tab state
  const [quizScenario, setQuizScenario] = useState('5-year waterflood with water breakthrough at year 3');
  const [quizLevel, setQuizLevel] = useState<ExplanationLevel>('intermediate');
  const [quizNQuestions, setQuizNQuestions] = useState(3);
  const [quizResponse, setQuizResponse] = useState<QuizResponse | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({});
  const [quizLoading, setQuizLoading] = useState(false);
  const [quizError, setQuizError] = useState<string | null>(null);

  // Learning Report tab state
  const [learningReport, setLearningReport] = useState<LearningReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  // Active tab
  const [activeTab, setActiveTab] = useState<'explain' | 'quiz' | 'report'>('explain');

  // Handle explain submit
  const handleExplain = useCallback(async () => {
    if (!explainQuestion.trim()) {
      setExplainError('Please enter a question');
      return;
    }

    setExplainLoading(true);
    setExplainError(null);

    try {
      const request: ExplainRequest = {
        topic: explainQuestion,
        kpis: null,
        level: explainLevel,
        context: null,
      };
      const response = await api.explainConcept(request);
      setExplainResponse(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to get explanation';
      setExplainError(message);
      console.error('Explain error:', err);
    } finally {
      setExplainLoading(false);
    }
  }, [explainQuestion, explainLevel]);

  // Handle follow-up question click
  const handleFollowUp = useCallback((question: string) => {
    setExplainQuestion(question);
    handleExplain();
  }, [handleExplain]);

  // Handle quiz generate
  const handleGenerateQuiz = useCallback(async () => {
    if (!quizScenario.trim()) {
      setQuizError('Please enter a scenario summary');
      return;
    }

    setQuizLoading(true);
    setQuizError(null);
    setQuizAnswers({});

    try {
      const request: QuizRequest = {
        scenario_summary: quizScenario,
        level: quizLevel,
        n_questions: quizNQuestions,
        topic_focus: null,
      };
      const response = await api.generateQuiz(request);
      setQuizResponse(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to generate quiz';
      setQuizError(message);
      console.error('Quiz error:', err);
    } finally {
      setQuizLoading(false);
    }
  }, [quizScenario, quizLevel, quizNQuestions]);

  // Handle quiz answer selection - guard against overwriting existing answer
  const handleAnswer = useCallback((questionIndex: number, selectedIndex: number) => {
    setQuizAnswers(prev => prev[questionIndex] !== undefined ? prev : { ...prev, [questionIndex]: selectedIndex });
  }, []);

  // Calculate score
  const score = quizResponse ? Object.entries(quizAnswers).reduce((acc, [idx, selected]) => {
    const qIdx = parseInt(idx);
    const question = quizResponse.questions[qIdx];
    return acc + (question && selected === question.correct_index ? 1 : 0);
  }, 0) : 0;

  const totalAnswered = Object.keys(quizAnswers).length;

  // Handle learning report generation
  const handleGenerateReport = useCallback(async () => {
    setReportLoading(true);
    setReportError(null);

    try {
      const conversationHistory = messages.map(msg => ({ role: msg.role, content: msg.content }));
      const request: LearningReportRequest = {
        session_id: sessionId,
        conversation_history: conversationHistory,
      };
      const response = await api.learningReport(request);
      setLearningReport(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to generate learning report';
      setReportError(message);
      console.error('Learning report error:', err);
    } finally {
      setReportLoading(false);
    }
  }, [sessionId, messages]);

  return (
    <div className="flex flex-col h-full bg-page">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
        <div>
          <h1 className="text-xl font-semibold text-textPrimary">Learn</h1>
          <p className="text-sm text-textSecondary">
            Explain reservoir concepts or test your knowledge with generated quizzes
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border bg-surface">
        {[
          { id: 'explain', label: 'Explain', icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> },
          { id: 'quiz', label: 'Quiz', icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg> },
          { id: 'report', label: 'Learning Report', icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as 'explain' | 'quiz' | 'report')}
            className={`tab flex items-center gap-2 px-4 py-2.5 ${activeTab === tab.id ? 'tab-active' : ''}`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 lg:p-6">
        {/* Explain Tab */}
        {activeTab === 'explain' && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Input Section */}
            <div className="card p-4">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-textPrimary mb-2">
                    Your Question
                  </label>
                  <textarea
                    value={explainQuestion}
                    onChange={(e) => setExplainQuestion(e.target.value)}
                    rows={4}
                    placeholder="e.g., Why did water cut spike after 3 years of waterflood? What is capillary pressure? Explain relative permeability hysteresis."
                    className="input w-full font-mono text-sm resize-none"
                    disabled={explainLoading}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-textPrimary mb-2">
                    Explanation Level
                  </label>
                  <div className="flex gap-3">
                    {['beginner', 'intermediate', 'advanced'].map((level) => (
                      <button
                        key={level}
                        onClick={() => setExplainLevel(level as ExplanationLevel)}
                        className={`flex-1 px-4 py-2 rounded text-sm font-medium transition-colors ${
                          explainLevel === level
                            ? 'bg-primary text-page'
                            : 'bg-surface border border-border text-textSecondary hover:text-textPrimary hover:border-primary/50'
                        }`}
                        disabled={explainLoading}
                      >
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  onClick={handleExplain}
                  disabled={explainLoading || !explainQuestion.trim()}
                  className="btn-primary w-full py-3 text-base disabled:opacity-50"
                >
                  {explainLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Explaining...
                    </span>
                  ) : (
                    'Ask'
                  )}
                </button>

                {explainError && (
                  <div className="p-3 rounded bg-error/20 border border-error text-error text-sm">
                    {explainError}
                  </div>
                )}
              </div>
            </div>

            {/* Response Section */}
            {explainResponse && (
              <div className="space-y-4">
                {/* Explanation Text */}
                <div className="card p-4">
                  <h3 className="font-semibold text-textPrimary mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Explanation ({explainResponse.level})
                  </h3>
                  <div className="prose prose-invert max-w-none whitespace-pre-wrap text-sm leading-relaxed">
                    {explainResponse.text}
                  </div>
                </div>

                {/* Citations */}
                {explainResponse.citations.length > 0 && (
                  <div className="card p-4">
                    <h3 className="font-semibold text-textPrimary mb-3 flex items-center gap-2">
                      <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Citations ({explainResponse.citations.length})
                    </h3>
                    <ul className="space-y-3">
                      {explainResponse.citations.map((citation, idx) => (
                        <li key={idx} className="text-sm">
                          <div className="font-medium text-textPrimary">{citation.title}</div>
                          <div className="text-textMuted text-xs font-mono mb-1">{citation.source_id}</div>
                          {citation.url_or_path && (
                            <a href={citation.url_or_path} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primaryHover text-xs underline">
                              {citation.url_or_path}
                            </a>
                          )}
                          <div className="mt-1 text-textSecondary line-clamp-2">{citation.snippet}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Follow-up Questions */}
                {explainResponse.follow_up_questions.length > 0 && (
                  <div className="card p-4">
                    <h3 className="font-semibold text-textPrimary mb-3 flex items-center gap-2">
                      <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Follow-up Questions
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {explainResponse.follow_up_questions.map((q, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleFollowUp(q)}
                          className="px-3 py-1.5 text-xs rounded border border-border text-textSecondary hover:text-textPrimary hover:border-primary/50 hover:bg-surfaceHover transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Quiz Tab */}
        {activeTab === 'quiz' && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Quiz Generator */}
            {!quizResponse && (
              <div className="card p-6">
                <h2 className="text-lg font-semibold text-textPrimary mb-4">Generate Quiz</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-textPrimary mb-2">
                      Scenario Summary
                    </label>
                    <textarea
                      value={quizScenario}
                      onChange={(e) => setQuizScenario(e.target.value)}
                      rows={3}
                      placeholder="Describe the simulation scenario (e.g., '5-year waterflood with water breakthrough at year 3')"
                      className="input w-full font-mono text-sm resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-textPrimary mb-2">
                        Level
                      </label>
                      <select
                        value={quizLevel}
                        onChange={(e) => setQuizLevel(e.target.value as ExplanationLevel)}
                        className="input w-full"
                      >
                        <option value="beginner">Beginner</option>
                        <option value="intermediate">Intermediate</option>
                        <option value="advanced">Advanced</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-textPrimary mb-2">
                        Number of Questions (3-5)
                      </label>
                      <input
                        type="number"
                        value={quizNQuestions}
                        onChange={(e) => setQuizNQuestions(Math.max(3, Math.min(5, parseInt(e.target.value) || 3)))}
                        min={3}
                        max={5}
                        className="input w-full"
                      />
                    </div>
                  </div>

                  <button
                    onClick={handleGenerateQuiz}
                    disabled={quizLoading || !quizScenario.trim()}
                    className="btn-primary w-full py-3 text-base disabled:opacity-50"
                  >
                    {quizLoading ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Generating...
                      </span>
                    ) : (
                      'Generate Quiz'
                    )}
                  </button>

                  {quizError && (
                    <div className="p-3 rounded bg-error/20 border border-error text-error text-sm">
                      {quizError}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Quiz Questions */}
            {quizResponse && (
              <div className="space-y-4">
                {/* Score Header */}
                <div className="card p-4 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <h2 className="text-lg font-semibold text-textPrimary">
                      {quizResponse.scenario_summary}
                    </h2>
                    <span className="badge badge-primary text-sm">
                      {quizResponse.questions.length} Questions
                    </span>
                    <span className="badge badge-outline text-sm">
                      Level: {quizLevel}
                    </span>
                  </div>
                  <div className="text-lg font-mono font-semibold text-textPrimary">
                    Score: {score} / {totalAnswered}
                    {totalAnswered === quizResponse.questions.length && (
                      <span className="ml-2 text-sm font-normal text-textSecondary">
                        ({Math.round((score / quizResponse.questions.length) * 100)}%)
                      </span>
                    )}
                  </div>
                </div>

                {/* Questions */}
                <div className="space-y-4">
                  {quizResponse.questions.map((question, qIdx) => {
                    const selectedAnswer = quizAnswers[qIdx];
                    const isAnswered = selectedAnswer !== undefined;
                    const isCorrect = isAnswered && selectedAnswer === question.correct_index;

                    return (
                      <div key={qIdx} className="card p-4 space-y-3">
                        <div className="flex items-start gap-3">
                          <span className="text-sm font-medium text-textMuted flex-shrink-0 w-6">
                            Q{qIdx + 1}.
                          </span>
                          <p className="text-textPrimary flex-1">{question.question}</p>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {question.options.map((option, oIdx) => {
                            const isSelected = isAnswered && selectedAnswer === oIdx;
                            const isCorrectOption = oIdx === question.correct_index;

                            let borderClass = 'border-border';
                            let bgClass = 'bg-surface';
                            let textClass = 'text-textPrimary';

                            if (isAnswered) {
                              if (isCorrectOption) {
                                borderClass = 'border-success';
                                bgClass = 'bg-success/10';
                                textClass = 'text-success';
                              } else if (isSelected) {
                                borderClass = 'border-error';
                                bgClass = 'bg-error/10';
                                textClass = 'text-error';
                              }
                            } else {
                              borderClass = 'border-border hover:border-primary/50';
                              bgClass = 'hover:bg-surfaceHover';
                            }

                            return (
                              <button
                                key={oIdx}
                                onClick={() => !isAnswered && handleAnswer(qIdx, oIdx)}
                                disabled={isAnswered}
                                className={`p-3 rounded border text-sm text-left transition-all ${borderClass} ${bgClass} ${textClass} ${
                                  !isAnswered ? 'hover:border-primary/50 hover:bg-surfaceHover' : ''
                                }`}
                              >
                                <span className="font-mono mr-2 text-textMuted">{String.fromCharCode(65 + oIdx)}.</span>
                                {option}
                              </button>
                            );
                          })}
                        </div>

                        {/* Explanation - shown after answering */}
                        {isAnswered && (
                          <div className={`p-3 rounded border ${
                            isCorrect ? 'bg-success/10 border-success' : 'bg-error/10 border-error'
                          }`}>
                            <div className="flex items-center gap-2 mb-1">
                              <span className={isCorrect ? 'text-success' : 'text-error'}>
                                {isCorrect ? (
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                ) : (
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                )}
                              </span>
                              <span className="font-medium text-sm">
                                {isCorrect ? 'Correct' : 'Incorrect'}
                              </span>
                            </div>
                            <p className="text-sm text-textSecondary">{question.explanation}</p>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {question.topic_tags.map((tag, tIdx) => (
                                <span key={tIdx} className="px-2 py-0.5 text-xs rounded bg-surface border border-border text-textMuted">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Retry Button */}
                <div className="flex justify-center">
                  <button
                    onClick={() => {
                      setQuizResponse(null);
                      setQuizAnswers({});
                    }}
                    className="btn-secondary"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    New Quiz
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Learning Report Tab */}
        {activeTab === 'report' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="card p-6">
              <h2 className="text-lg font-semibold text-textPrimary mb-4">Learning Report</h2>
              <p className="text-sm text-textSecondary mb-4">
                Generate a summary of your learning session including topics covered, key concepts, and quiz performance.
              </p>

              {!learningReport ? (
                <button
                  onClick={handleGenerateReport}
                  disabled={reportLoading || messages.length === 0}
                  className="btn-primary w-full py-3 text-base disabled:opacity-50"
                >
                  {reportLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Generating Report...
                    </span>
                  ) : (
                    'Generate Learning Report'
                  )}
                </button>
              ) : null}

              {reportError && (
                <div className="p-3 rounded bg-error/20 border border-error text-error text-sm">
                  {reportError}
                </div>
              )}

              {learningReport && (
                <div className="space-y-6 mt-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="card p-4">
                      <div className="text-2xl font-bold text-textPrimary">{learningReport.explanations_generated}</div>
                      <div className="text-sm text-textSecondary">Explanations Generated</div>
                    </div>
                    <div className="card p-4">
                      <div className="text-2xl font-bold text-textPrimary">{learningReport.questions_asked}</div>
                      <div className="text-sm text-textSecondary">Questions Asked</div>
                    </div>
                    <div className="card p-4">
                      <div className="text-2xl font-bold text-textPrimary">{learningReport.key_concepts.length}</div>
                      <div className="text-sm text-textSecondary">Key Concepts</div>
                    </div>
                  </div>

                  {/* Topics Covered */}
                  <div className="card p-4">
                    <h3 className="font-semibold text-textPrimary mb-3">Topics Covered</h3>
                    <ul className="space-y-2">
                      {learningReport.topics_covered.map((topic, idx) => (
                        <li key={idx} className="text-sm text-textSecondary flex items-center gap-2">
                          <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          {topic}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Key Concepts */}
                  <div className="card p-4">
                    <h3 className="font-semibold text-textPrimary mb-3">Key Concepts</h3>
                    <div className="flex flex-wrap gap-2">
                      {learningReport.key_concepts.map((concept, idx) => (
                        <span key={idx} className="px-3 py-1 text-sm rounded bg-primary/20 text-primary border border-primary/30">
                          {concept}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Quiz Scores */}
                  {learningReport.quiz_scores && Object.keys(learningReport.quiz_scores).length > 0 && (
                    <div className="card p-4">
                      <h3 className="font-semibold text-textPrimary mb-3">Quiz Scores</h3>
                      <div className="space-y-2">
                        {Object.entries(learningReport.quiz_scores).map(([quiz, score], idx) => (
                          <div key={idx} className="flex items-center justify-between">
                            <span className="text-sm text-textSecondary">{quiz}</span>
                            <span className="font-mono font-medium text-textPrimary">{Math.round(score * 100)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Citations Used */}
                  {learningReport.citations_used.length > 0 && (
                    <div className="card p-4">
                      <h3 className="font-semibold text-textPrimary mb-3">Citations Used</h3>
                      <ul className="space-y-2">
                        {learningReport.citations_used.map((citation, idx) => (
                          <li key={idx} className="text-sm">
                            <div className="font-medium text-textPrimary">{citation.title}</div>
                            <div className="text-textMuted text-xs font-mono">{citation.source_id}</div>
                            {citation.url_or_path && (
                              <a href={citation.url_or_path} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primaryHover text-xs underline">
                                {citation.url_or_path}
                              </a>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Markdown Report */}
                  <div className="card p-4">
                    <h3 className="font-semibold text-textPrimary mb-3">Full Report (Markdown)</h3>
                    <div className="prose prose-invert max-w-none whitespace-pre-wrap text-sm bg-page border border-border p-4 rounded">
                      {learningReport.markdown}
                    </div>
                  </div>

                  <button
                    onClick={() => setLearningReport(null)}
                    className="btn-secondary"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Generate New Report
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}