import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { LintResult, QuestionDTO } from '../types';

interface Props {
  description: string;
  useLlm: boolean;
  answers: Record<string, unknown>;
  isOpen: boolean;
  onToggle: () => void;
  onQuestionChange: (
    question: QuestionDTO | null,
    progress: { answered: number; total: number },
    findings?: string[],
    resolved?: Record<string, number | number[]> | null,
  ) => void;
  onAnswer: (id: string, value: unknown) => void;
  onReset: () => void;
  onDeckBuilt: (deck: string, lint: LintResult, message: string) => void;
}

/**
 * Step-by-step reservoir interview + file ingestion.
 *
 * The server is stateless: this component owns the answers dict and
 * round-trips it on every /interview/next call, so a reload resumes
 * exactly where the user left off. Every question is skippable - Skip
 * records the declared default server-side, so the terminal state always
 * builds a deck (the "interview hung" state is not representable).
 */
export default function InterviewPanel({
  description,
  useLlm,
  answers,
  isOpen,
  onToggle,
  onQuestionChange,
  onAnswer,
  onReset,
  onDeckBuilt,
}: Props) {
  const [question, setQuestion] = useState<QuestionDTO | null>(null);
  const [input, setInput] = useState('');
  const [progress, setProgress] = useState({ answered: 0, total: 0 });
  const [findings, setFindings] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingestNote, setIngestNote] = useState<string[]>([]);

  // The answers dict is owned by the parent store; the fetch closure reads
  // the latest value through a ref so we never fire a stale request.
  const answersRef = useRef(answers);
  answersRef.current = answers;
  const lastDescription = useRef<string>('');

  const fetchNext = useCallback(async () => {
    if (!description.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.interviewNext({
        description,
        answers: answersRef.current,
        use_llm: useLlm,
      });
      setQuestion(res.question);
      setProgress(res.progress);
      setFindings(res.findings);
      setDone(res.question === null);
      setInput(res.question?.default == null ? '' : String(res.question.default));
      onQuestionChange(res.question, res.progress, res.findings, res.resolved ?? undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Interview failed');
    } finally {
      setBusy(false);
    }
  }, [description, useLlm, onQuestionChange]);

  // Fetch the first question when the panel opens, and whenever the
  // description changes underneath an in-progress interview.
  useEffect(() => {
    if (!isOpen) return;
    if (description.trim() && description !== lastDescription.current) {
      lastDescription.current = description;
      void fetchNext();
    }
  }, [isOpen, description, fetchNext]);

  const handleAnswer = useCallback(async () => {
    if (!question) return;
    setBusy(true);
    setError(null);
    const raw = input.trim();
    let value: unknown = raw === '' ? null : raw;
    if (question.kind === 'number' && raw !== '') {
      const n = parseFloat(raw);
      if (!Number.isFinite(n)) {
        setError(`${raw} is not a number.`);
        setBusy(false);
        return;
      }
      value = n;
    }
    onAnswer(question.id, value);
    // Wait for the parent store to commit the answer before the next
    // fetch reads it back through answersRef.
    await new Promise((resolve) => setTimeout(resolve, 0));
    answersRef.current = { ...answersRef.current, [question.id]: value };
    await fetchNext();
  }, [question, input, onAnswer, fetchNext]);

  const handleSkip = useCallback(async () => {
    if (!question) return;
    onAnswer(question.id, null);
    await new Promise((resolve) => setTimeout(resolve, 0));
    answersRef.current = { ...answersRef.current, [question.id]: null };
    await fetchNext();
  }, [question, onAnswer, fetchNext]);

  const handleFinish = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.interviewFinish({
        description,
        answers: answersRef.current,
        use_llm: useLlm,
      });
      setFindings(res.findings);
      onDeckBuilt(res.deck, res.lint, 'Interview complete.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Interview failed');
    } finally {
      setBusy(false);
    }
  }, [description, useLlm, onDeckBuilt]);

  const handleRestart = useCallback(() => {
    setQuestion(null);
    setDone(false);
    setFindings([]);
    setIngestNote([]);
    setError(null);
    lastDescription.current = '';
    onReset();
  }, [onReset]);

  const handleIngest = useCallback(
    async (text: string, source: string) => {
      setBusy(true);
      setError(null);
      try {
        const res = await api.ingestParse(text);
        setIngestNote([
          `Read ${source} as ${res.detected}.`,
          ...res.findings,
        ]);
        // The patch rides along as a special answer so the spec picks it
        // up before the next question is computed.
        onAnswer('__ingest', text);
        await new Promise((resolve) => setTimeout(resolve, 0));
        answersRef.current = { ...answersRef.current, __ingest: text };
        await fetchNext();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not read file');
      } finally {
        setBusy(false);
      }
    },
    [onAnswer, fetchNext],
  );

  const handleFile = useCallback(
    async (file: File) => {
      setBusy(true);
      setError(null);
      try {
        const res = await api.ingestUpload(file);
        setIngestNote([
          `Read ${file.name} as ${res.detected}.`,
          ...res.findings,
        ]);
        const text = await file.text();
        onAnswer('__ingest', text);
        await new Promise((resolve) => setTimeout(resolve, 0));
        answersRef.current = { ...answersRef.current, __ingest: text };
        await fetchNext();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not read file');
      } finally {
        setBusy(false);
      }
    },
    [onAnswer, fetchNext],
  );

  const pct = progress.total > 0 ? Math.round((progress.answered / progress.total) * 100) : 0;

  return (
    <div className="card">
      <button onClick={onToggle} className="w-full flex items-center justify-between p-4 text-left">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-textSecondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="font-medium text-textPrimary">Reservoir interview</span>
          {progress.total > 0 && (
            <span className="text-xs text-textMuted">
              {progress.answered}/{progress.total}
            </span>
          )}
        </div>
        <svg className={`w-4 h-4 text-textSecondary transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-4 pb-4 space-y-3 border-t border-border">
          <p className="text-xs text-textMuted pt-3">
            Answer one section at a time. Skipping a question keeps the extracted default,
            so you always end up with a buildable deck.
          </p>

          {/* File / paste ingestion */}
          <div className="space-y-2">
            <label className="block text-xs font-medium text-textSecondary">
              Import a grid file, table, or keyword export
            </label>
            <div className="flex gap-2">
              <input
                type="file"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleFile(file);
                  e.target.value = '';
                }}
                className="text-xs text-textSecondary file:mr-2 file:rounded file:border-0 file:bg-surfaceHover file:px-2 file:py-1 file:text-textPrimary"
              />
            </div>
            <textarea
              rows={3}
              placeholder="...or paste PORO / PERMX / a PVDG table / a numeric grid here"
              onPaste={(e) => {
                const text = e.clipboardData.getData('text');
                if (text.trim()) void handleIngest(text, 'pasted text');
              }}
              className="input w-full font-mono text-xs resize-none"
            />
            {ingestNote.length > 0 && (
              <ul className="text-xs text-textSecondary space-y-1">
                {ingestNote.map((n, i) => (
                  <li key={i}>• {n}</li>
                ))}
              </ul>
            )}
          </div>

          {/* Progress */}
          {progress.total > 0 && (
            <div className="w-full bg-surfaceHover rounded-full h-1.5">
              <div className="bg-primary h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
            </div>
          )}

          {/* Current question */}
          {question && (
            <div className="space-y-2 p-3 rounded border border-border bg-surfaceHover/40">
              <div className="text-xs uppercase tracking-wide text-textMuted">{question.section}</div>
              <p className="text-sm text-textPrimary">{question.prompt}</p>
              {question.kind === 'select' && question.options ? (
                <select
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  className="input w-full"
                >
                  {question.options.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') void handleAnswer(); }}
                  placeholder={question.default == null ? 'leave blank to skip' : ''}
                  className="input w-full"
                />
              )}
              {question.units && (
                <p className="text-xs text-textMuted">{question.units}</p>
              )}
              <div className="flex gap-2 pt-1">
                <button onClick={() => void handleAnswer()} disabled={busy} className="btn-primary btn-sm flex-1">
                  {busy ? '...' : 'Answer'}
                </button>
                <button onClick={() => void handleSkip()} disabled={busy} className="btn-secondary btn-sm">
                  Skip
                </button>
              </div>
            </div>
          )}

          {done && (
            <div className="p-3 rounded bg-success/10 border border-success text-sm text-textPrimary">
              All sections covered. Build the deck when you are happy with the answers.
            </div>
          )}

          {findings.length > 0 && (
            <ul className="text-xs text-warning space-y-1">
              {findings.map((f, i) => (
                <li key={i}>• {f}</li>
              ))}
            </ul>
          )}

          {error && (
            <div className="p-2 rounded bg-error/20 border border-error text-error text-xs">{error}</div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={() => void handleFinish()} disabled={busy || !description.trim()} className="btn-primary btn-sm flex-1">
              Build from answers
            </button>
            <button onClick={handleRestart} disabled={busy} className="btn-secondary btn-sm">
              Restart
            </button>
          </div>
        </div>
      )}
    </div>
  );
}