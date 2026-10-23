import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { LogIn, UserPlus } from 'lucide-react';
import { api } from '../api';
import { useAuth } from '../auth';
import { Btn, ErrorBox, Picto } from '../ui';

export default function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get('next') || '/';
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [invite, setInvite] = useState(params.get('invite') ?? '');
  const [inviteRequired, setInviteRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const signup = mode === 'signup';

  useEffect(() => {
    setError(null);
    if (signup) api.authConfig().then((c) => setInviteRequired(c.invite_required)).catch(() => undefined);
  }, [signup]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = signup
        ? await api.signup({ email, password, name, invite_code: invite || undefined })
        : await api.login(email, password);
      setUser(res.user);
      navigate(next.startsWith('/') ? next : '/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sign on-sign auth-screen">
      <header className="land-nav">
        <Link to="/welcome" className="brand" style={{ padding: 0 }}>
          <Picto>
            <svg width="26" height="26" viewBox="0 0 64 64" aria-hidden>
              <path d="M10 32h34M32 18l14 14-14 14" fill="none" stroke="#ffcc00" strokeWidth="8" strokeLinecap="square" />
            </svg>
          </Picto>
          <span className="brand-name">NotForgotten</span>
        </Link>
      </header>
      <div className="auth-grid">
        <div className="auth-copy">
          <h1 className="land-title" style={{ fontSize: 'clamp(2.6rem, 6vw, 4.6rem)' }}>
            {signup ? 'Your memory, on schedule.' : 'Welcome back.'}
          </h1>
          <p className="land-sub">
            {signup
              ? 'Create an account to keep your library, review history and exam plans in sync across your laptop and phone.'
              : 'Log in to see what is due and pick up where you left off.'}
          </p>
        </div>
        <form className="surface auth-form" onSubmit={submit} noValidate>
          <div className="panel-head">
            <Picto size="sm">{signup ? <UserPlus size={18} /> : <LogIn size={18} />}</Picto>
            <h2>{signup ? 'Create your account' : 'Log in'}</h2>
          </div>
          <div className="panel-body field-stack">
            {signup && (
              <label className="field">
                <span className="label">Name</span>
                <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" placeholder="What should we call you?" />
              </label>
            )}
            <label className="field">
              <span className="label">Email</span>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
            </label>
            <label className="field">
              <span className="label">Password</span>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={signup ? 'new-password' : 'current-password'}
                minLength={signup ? 8 : undefined}
                required
              />
              {signup && <span className="small muted">At least 8 characters.</span>}
            </label>
            {signup && inviteRequired && (
              <label className="field">
                <span className="label">Beta invite code</span>
                <input className="input" value={invite} onChange={(e) => setInvite(e.target.value)} autoComplete="off" required />
              </label>
            )}
            {error && <ErrorBox error={error} />}
            <div>
              <Btn type="submit" size="big" disabled={busy || !email || !password}>
                {busy ? (signup ? 'Creating account…' : 'Logging in…') : signup ? 'Create account' : 'Log in'}
              </Btn>
            </div>
            <p className="small">
              {signup ? (
                <>
                  Already have an account? <Link to={`/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`}>Log in</Link>
                </>
              ) : (
                <>
                  New here? <Link to={`/signup${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`}>Create an account</Link>
                </>
              )}
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
