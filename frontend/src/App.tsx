import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  CalendarClock,
  Map as MapIcon,
  MessageSquareText,
  Moon,
  Settings as SettingsIcon,
  Sun,
  SunMoon,
  Repeat2,
  LogOut,
} from 'lucide-react';
import { api, type Today as TodayData } from './api';
import { AuthProvider, useAuth } from './auth';
import { Picto, Skeleton, ToastProvider, useTheme } from './ui';

const Today = lazy(() => import('./pages/Today'));
const Review = lazy(() => import('./pages/Review'));
const Library = lazy(() => import('./pages/Library'));
const DocumentPage = lazy(() => import('./pages/DocumentPage'));
const ConceptPage = lazy(() => import('./pages/ConceptPage'));
const Graph = lazy(() => import('./pages/Graph'));
const Tutor = lazy(() => import('./pages/Tutor'));
const Insights = lazy(() => import('./pages/Insights'));
const Exams = lazy(() => import('./pages/Exams'));
const Settings = lazy(() => import('./pages/Settings'));
const Landing = lazy(() => import('./pages/Landing'));
const AuthPage = lazy(() => import('./pages/AuthPage'));

const NAV = [
  { to: '/', label: 'Today', hint: 'What to study next', icon: ArrowRight, short: 'Today' },
  { to: '/review', label: 'Review', hint: 'Recall, graded', icon: Repeat2, short: 'Review', count: true },
  { to: '/library', label: 'Library', hint: 'Sources & concepts', icon: BookOpen, short: 'Library' },
  { to: '/map', label: 'Knowledge map', hint: 'See it fade, in time', icon: MapIcon, short: 'Map' },
  { to: '/tutor', label: 'Tutor', hint: 'Ask, get quizzed', icon: MessageSquareText, short: 'Tutor' },
  { to: '/insights', label: 'Insights', hint: 'Your memory, measured', icon: BarChart3, short: 'Insights' },
  { to: '/exams', label: 'Exams', hint: 'Plan back from the date', icon: CalendarClock, short: 'Exams' },
];
const TABS = ['/', '/review', '/library', '/tutor', '/exams'];

function useQueueCount() {
  const location = useLocation();
  const [today, setToday] = useState<TodayData | null>(null);
  useEffect(() => {
    api.today().then(setToday).catch(() => undefined);
  }, [location.pathname]);
  return today ? today.due + today.new : null;
}

function Rail() {
  const count = useQueueCount();
  const { user, logout } = useAuth();
  const [theme, setTheme] = useTheme();
  const [llm, setLlm] = useState<string>('Checking AI…');
  useEffect(() => {
    api
      .health()
      .then((h) => setLlm(h.llm.available ? `AI: ${h.llm.provider}` : 'AI offline · local mode'))
      .catch(() => setLlm('Server unreachable'));
  }, []);
  const nextTheme = theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system';
  const ThemeIcon = theme === 'system' ? SunMoon : theme === 'light' ? Sun : Moon;

  return (
    <aside className="rail" aria-label="Main navigation">
      <NavLink to="/welcome" className="brand" aria-label="NotForgotten — about">
        <Picto>
          <svg width="26" height="26" viewBox="0 0 64 64" aria-hidden>
            <path d="M10 32h34M32 18l14 14-14 14" fill="none" stroke="#ffcc00" strokeWidth="8" strokeLinecap="square" />
          </svg>
        </Picto>
        <span>
          <span className="brand-name">NotForgotten</span>
          <span className="brand-sub" style={{ display: 'block' }}>
            Memory, on schedule
          </span>
        </span>
      </NavLink>
      <nav>
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => `rail-link${isActive ? ' active' : ''}`}>
            <Picto>
              <item.icon size={22} strokeWidth={2.4} />
            </Picto>
            <span>
              <span className="rail-label" style={{ display: 'block' }}>
                {item.label}
              </span>
              <span className="rail-hint" style={{ display: 'block' }}>
                {item.hint}
              </span>
            </span>
            {item.count && count ? <span className="rail-count">{count}</span> : <span />}
          </NavLink>
        ))}
      </nav>
      <div className="rail-foot">
        <NavLink to="/settings" className="rail-foot-row" style={{ fontWeight: 700, textDecoration: 'none', color: 'inherit' }}>
          <SettingsIcon size={18} /> Settings
        </NavLink>
        <button
          className="rail-foot-row link-btn"
          style={{ textDecoration: 'none', color: 'inherit' }}
          onClick={() => setTheme(nextTheme)}
          aria-label={`Theme: ${theme}. Switch to ${nextTheme}`}
        >
          <ThemeIcon size={18} /> Theme: {theme}
        </button>
        <div className="rail-foot-row">
          <span className={`dot${llm.startsWith('AI:') ? ' live' : ''}`} /> {llm}
        </div>
        {user && (
          <div className="rail-user">
            <span style={{ minWidth: 0 }}>
              <b style={{ display: 'block' }}>{user.name || 'Your account'}</b>
              <span className="rail-email">{user.email}</span>
            </span>
            <button className="icon-btn" onClick={logout} aria-label="Sign out" title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}

function TabBar() {
  const count = useQueueCount();
  return (
    <nav className="tabbar" aria-label="Main navigation">
      {NAV.filter((n) => TABS.includes(n.to)).map((item) => (
        <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => `tab${isActive ? ' active' : ''}`}>
          <item.icon size={22} strokeWidth={2.4} />
          {item.short}
          {item.count && count ? <span className="visually-hidden">{count} cards</span> : null}
        </NavLink>
      ))}
    </nav>
  );
}

function Shell() {
  const location = useLocation();
  const { user, loading } = useAuth();
  const PUBLIC = ['/welcome', '/login', '/signup'];
  const bare = PUBLIC.includes(location.pathname);
  const focus = location.pathname === '/review'; // review sessions hide the phone tab bar
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  const routes = (
    <Suspense
      fallback={
        <div className="page">
          <Skeleton h={160} />
          <Skeleton h={320} />
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<Today />} />
        <Route path="/review" element={<Review />} />
        <Route path="/library" element={<Library />} />
        <Route path="/library/:id" element={<DocumentPage />} />
        <Route path="/concept/:id" element={<ConceptPage />} />
        <Route path="/map" element={<Graph />} />
        <Route path="/tutor" element={<Tutor />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/exams" element={<Exams />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/welcome" element={<Landing />} />
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <AuthPage mode="login" />} />
        <Route path="/signup" element={user ? <Navigate to="/" replace /> : <AuthPage mode="signup" />} />
        <Route path="*" element={<Today />} />
      </Routes>
    </Suspense>
  );

  if (bare) return routes;
  if (loading)
    return (
      <div className="page">
        <Skeleton h={160} />
      </div>
    );
  if (!user) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`} replace />;
  }
  return (
    <div className="shell">
      <Rail />
      <main className={`main${focus ? ' focus' : ''}`} id="main">
        {routes}
      </main>
      {!focus && <TabBar />}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Shell />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
