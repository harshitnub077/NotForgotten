// Typed client for the NotForgotten API.

export type Preview = Record<string, { label: string; interval_days: number; interval: string; stability: number }>;

export interface Card {
  id: string;
  concept_id: string;
  document_id: string;
  kind: 'qa' | 'cloze' | 'explain';
  prompt: string;
  answer: string;
  explanation: string;
  origin: string;
  is_new: boolean;
  stability: number | null;
  difficulty: number | null;
  due: string | null;
  last_review: string | null;
  reps: number;
  lapses: number;
  retrievability: number | null;
  half_life_days: number | null;
  preview?: Preview;
  reason?: string;
  concept_name?: string;
  suspended?: boolean;
}

export interface ConceptSummary {
  id: string;
  name: string;
  summary: string;
  keywords: string[];
  document_id: string;
  document_title: string;
  position: number;
  cards: number;
  learned: number;
  due: number;
  retention: number | null;
  stability: number | null;
  difficulty: number | null;
  mastery: number;
}

export interface ForecastDay {
  day: number;
  date: string;
  due: number;
  retention_if_idle: number;
  retention_if_kept: number;
}

export interface Exam {
  id: string;
  name: string;
  exam_date: string;
  target: number;
  document_ids: string[];
  days_left: number;
}

export interface Today {
  due: number;
  new: number;
  estimated_minutes: number;
  reviewed_today: number;
  goal_minutes: number;
  retention_now: number | null;
  desired_retention: number;
  cards_total: number;
  cards_learned: number;
  concepts_total: number;
  documents_total: number;
  streak: { current: number; longest: number; reviewed_today: boolean };
  at_risk: (ConceptSummary & { retention: number })[];
  forecast: ForecastDay[];
  next_due: string | null;
  exams: Exam[];
}

export interface QueueResponse {
  session_id: string;
  mode: string;
  cards: Card[];
}

export interface Grade {
  score: number;
  rating: number;
  verdict: 'correct' | 'partial' | 'incorrect';
  feedback: string;
  missing: string[];
  method: string;
}

export interface AnswerResult {
  card_id: string;
  rating: number;
  retrievability_before: number | null;
  stability_before: number | null;
  stability_after: number;
  difficulty_after: number;
  interval_days: number;
  interval: string;
  due: string;
  half_life_days: number;
  concept_retention: number | null;
}

export interface SessionSummary {
  session_id: string;
  reviews: number;
  correct?: number;
  ratings?: Record<string, number>;
  minutes?: number;
  stability_gained_days?: number;
  mean_confidence?: number | null;
  concepts?: number;
}

export interface Doc {
  id: string;
  title: string;
  filename: string | null;
  kind: string;
  source_url: string | null;
  size_bytes: number;
  chunk_count: number;
  concept_count: number;
  card_count: number;
  status: 'processing' | 'ready' | 'failed';
  error: string | null;
  is_demo: number;
  created_at: string;
  review_count?: number;
  concepts?: ConceptSummary[];
}

export interface Job {
  id: string;
  document_id: string | null;
  status: 'running' | 'done' | 'failed';
  stage: string;
  progress: number;
  message: string;
  log: { t: string; stage: string; message: string }[];
}

export interface Link {
  id: string;
  name: string;
  retention: number | null;
}

export interface ConceptDetail extends ConceptSummary {
  effective_retention: number | null;
  prerequisites: Link[];
  dependents: Link[];
  related: Link[];
  weak_foundations: Link[];
  curve: { t: number; r: number | null }[];
  cards_detail: Card[];
  passages: { id: string; page: number; text: string }[];
  feynman: { id: string; score: number; created_at: string; result: Feynman }[];
}

export interface Feynman {
  score: number;
  coverage: number;
  clarity: number;
  covered: string[];
  missing: string[];
  feedback: string;
  follow_up: string;
  method: string;
}

export interface GraphNode {
  id: string;
  name: string;
  document_id: string;
  document_title: string;
  retention: number | null;
  effective_retention: number | null;
  cards: number;
  learned: number;
  due: number;
  stability: number | null;
  mastery: number;
}

export interface GraphData {
  at: string;
  days_ahead: number;
  nodes: GraphNode[];
  edges: { source: string; target: string; weight: number; kind: 'prerequisite' | 'related' }[];
}

export interface Calibration {
  n: number;
  brier: number | null;
  ece: number | null;
  overconfidence: number | null;
  resolution: number | null;
  mean_confidence?: number;
  accuracy?: number;
  bins: { lo: number; hi: number; confidence: number; accuracy: number; count: number }[];
}

export interface Insights {
  reviews_total: number;
  minutes_total: number;
  days_studied: number;
  streak: { current: number; longest: number; reviewed_today: boolean };
  heatmap: { date: string; count: number; minutes: number }[];
  true_retention: { all_time: number | null; last_30d: number | null; n: number };
  model_fit: { predicted: number | null; actual: number | null };
  calibration: Calibration;
  forecast: ForecastDay[];
  stability_histogram: { label: string; count: number }[];
  difficulty_histogram: { label: string; count: number }[];
  ratings: Record<string, number>;
  knowledge_days: number;
  cards_learned: number;
  model: {
    desired_retention: number;
    parameters: number[];
    personalized: boolean;
    last_fit: FitResult | null;
    decay: number;
  };
}

export interface FitResult {
  improved: boolean;
  n_predictions: number;
  loss_before: number;
  loss_after: number;
  rmse_before: number;
  rmse_after: number;
  fitted_at: string;
  parameters?: number[];
}

export interface ExamPlan {
  id: string;
  name: string;
  exam_date: string;
  target: number;
  document_ids: string[];
  days_left: number;
  total_cards: number;
  new_cards: number;
  daily: { day: number; date: string; reviews: number; new: number; minutes: number }[];
  projected_retention: number;
  projected_retention_no_plan: number;
  cards_below_target: number;
  current_retention_at_exam: number | null;
  today_minutes: number;
}

export interface Settings {
  desired_retention: number;
  daily_new_limit: number;
  daily_goal_minutes: number;
  use_llm: boolean;
  parameters_personalized: boolean;
  fsrs_parameters: number[];
  llm: { provider: string | null; model: string | null; available: boolean; last_error: string | null };
}

export interface SearchHit {
  chunk_id: string;
  document_id: string;
  concept_id: string;
  concept_name: string;
  document_title: string;
  page: number;
  text: string;
  semantic: number;
  urgency: number;
  score: number;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (res.status === 401 && !path.startsWith('/auth/')) {
    // Session expired or signed out elsewhere: let the app route to log-in.
    window.dispatchEvent(new Event('nf:unauthorized'));
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') msg = body.detail;
      else if (Array.isArray(body.detail)) msg = body.detail.map((d: { msg: string }) => d.msg).join('; ');
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const tz = () => -new Date().getTimezoneOffset();
const body = (data: unknown) => JSON.stringify(data);

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export const api = {
  authConfig: () => request<{ invite_required: boolean }>('/auth/config'),
  me: () => request<{ user: User }>('/auth/me'),
  signup: (data: { email: string; password: string; name: string; invite_code?: string }) =>
    request<{ user: User }>('/auth/signup', { method: 'POST', body: body(data) }),
  login: (email: string, password: string) =>
    request<{ user: User }>('/auth/login', { method: 'POST', body: body({ email, password }) }),
  logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
  updateProfile: (name: string) => request<{ user: User }>('/auth/me', { method: 'PATCH', body: body({ name }) }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ ok: boolean }>('/auth/password', { method: 'POST', body: body({ current_password, new_password }) }),
  deleteAccount: (password: string) => request<{ deleted: boolean }>('/auth/delete', { method: 'POST', body: body({ password }) }),
  exportData: () => request<Record<string, unknown>>('/auth/export'),
  health: () => request<{ status: string; llm: Settings['llm'] }>('/health'),
  today: () => request<Today>(`/today?tz_offset=${tz()}`),
  insights: () => request<Insights>(`/insights?tz_offset=${tz()}`),
  optimize: () => request<FitResult>('/insights/optimize', { method: 'POST' }),

  queue: (params: Record<string, string | number | undefined>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== '' && q.set(k, String(v)));
    return request<QueueResponse>(`/review/queue?${q}`);
  },
  grade: (card_id: string, response: string) => request<Grade>('/review/grade', { method: 'POST', body: body({ card_id, response }) }),
  answer: (data: {
    card_id: string;
    rating: number;
    response?: string;
    score?: number;
    confidence?: number;
    duration_ms?: number;
    session_id?: string;
  }) => request<AnswerResult>('/review/answer', { method: 'POST', body: body(data) }),
  session: (id: string) => request<SessionSummary>(`/review/session/${id}`),

  documents: () => request<Doc[]>('/documents'),
  document: (id: string) => request<Doc>(`/documents/${id}`),
  deleteDocument: (id: string) => request<{ deleted: string }>(`/documents/${id}`, { method: 'DELETE' }),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<{ job_id: string; document_id: string }>('/documents/upload', { method: 'POST', body: fd });
  },
  addText: (title: string, text: string) =>
    request<{ job_id: string; document_id: string }>('/documents/text', { method: 'POST', body: body({ title, text }) }),
  addUrl: (url: string) => request<{ job_id: string; document_id: string }>('/documents/url', { method: 'POST', body: body({ url }) }),
  jobs: () => request<Job[]>('/jobs'),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  search: (q: string) => request<SearchHit[]>(`/search?q=${encodeURIComponent(q)}&k=8`),

  concepts: () => request<ConceptSummary[]>('/concepts'),
  concept: (id: string) => request<ConceptDetail>(`/concepts/${id}`),
  graph: (days: number) => request<GraphData>(`/graph?days=${days}`),
  feynman: (id: string, explanation: string) =>
    request<Feynman>(`/concepts/${id}/feynman`, { method: 'POST', body: body({ explanation }) }),
  generate: (id: string, n = 3) => request<{ created: number }>(`/concepts/${id}/generate`, { method: 'POST', body: body({ n }) }),

  updateCard: (id: string, patch: Partial<Pick<Card, 'prompt' | 'answer' | 'explanation'>> & { suspended?: boolean }) =>
    request(`/cards/${id}`, { method: 'PATCH', body: body(patch) }),
  deleteCard: (id: string) => request(`/cards/${id}`, { method: 'DELETE' }),
  createCard: (data: { concept_id: string; kind: string; prompt: string; answer: string }) =>
    request<{ id: string }>('/cards', { method: 'POST', body: body(data) }),

  exams: () => request<Exam[]>('/exams'),
  exam: (id: string) => request<ExamPlan>(`/exams/${id}`),
  createExam: (data: { name: string; exam_date: string; target: number; document_ids: string[] }) =>
    request<ExamPlan>('/exams', { method: 'POST', body: body(data) }),
  deleteExam: (id: string) => request(`/exams/${id}`, { method: 'DELETE' }),

  settings: () => request<Settings>('/settings'),
  patchSettings: (patch: Partial<Pick<Settings, 'desired_retention' | 'daily_new_limit' | 'daily_goal_minutes' | 'use_llm'>>) =>
    request<Settings>('/settings', { method: 'PATCH', body: body(patch) }),
  resetModel: () => request('/settings/reset-model', { method: 'POST' }),
  loadDemo: () => request<{ job_id: string }>('/demo', { method: 'POST' }),
  clearDemo: () => request<{ deleted: number }>('/demo', { method: 'DELETE' }),
  cardsFromChat: (text: string, concept_id: string) =>
    request<{ created: number }>('/tutor/cards', { method: 'POST', body: body({ text, concept_id, n: 3 }) }),
};

export type TutorEvent =
  | { type: 'meta'; sources: SearchHit[]; fading: { id: string; name: string; retention: number }[] }
  | { type: 'token'; text: string }
  | { type: 'error'; message: string }
  | { type: 'done'; llm: Settings['llm'] };

export async function streamTutor(
  payload: { message: string; history: { role: string; content: string }[]; mode: string },
  onEvent: (e: TutorEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/tutor/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, 'The tutor is unavailable right now.');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = chunk.split('\n').find((l) => l.startsWith('data: '));
      if (line) onEvent(JSON.parse(line.slice(6)) as TutorEvent);
    }
  }
}

export const getCard = (id: string) => fetch(`/api/cards/${id}`).then((r) => r.json() as Promise<Card>);
