'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { api, APIError, type AuthSession } from '../../lib/api';

type SessionState = { session: AuthSession | null; loading: boolean; error: string; refresh: () => Promise<void>;
  authenticate: (kind: 'login' | 'register', body: Record<string, string>) => Promise<void>; signOut: () => Promise<void> };
const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const channel = useRef<BroadcastChannel | null>(null);
  const refresh = useCallback(async () => {
    const version = ++generation.current;
    try { const result = await api<AuthSession>('auth/me'); if (version === generation.current) { setSession(result); setError(''); } }
    catch (reason) {
      if (version !== generation.current) return;
      setSession(null);
      setError(reason instanceof APIError && reason.status === 401 ? '' : 'No pudimos conectar con tu cuenta.');
    } finally { if (version === generation.current) setLoading(false); }
  }, []);
  useEffect(() => {
    void refresh();
    const onFocus = () => { void refresh(); };
    window.addEventListener('focus', onFocus);
    if ('BroadcastChannel' in window) {
      channel.current = new BroadcastChannel('fieldshift-session');
      channel.current.onmessage = () => { void refresh(); };
    }
    return () => { window.removeEventListener('focus', onFocus); channel.current?.close(); };
  }, [refresh]);
  async function authenticate(kind: 'login' | 'register', body: Record<string, string>) {
    const current = await api<AuthSession>(`auth/${kind}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    generation.current++; setLoading(false); setSession(current); setError(''); channel.current?.postMessage('changed');
  }
  async function signOut() {
    if (!session) return;
    try { await api<void>('auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': session.csrf_token } }); }
    catch (reason) { if (!(reason instanceof APIError && reason.status === 401)) throw reason; }
    generation.current++; setSession(null); channel.current?.postMessage('changed');
  }
  return <SessionContext.Provider value={{ session, loading, error, refresh, authenticate, signOut }}>{children}</SessionContext.Provider>;
}
export function useSession() {
  const state = useContext(SessionContext);
  if (!state) throw new Error('Falta SessionProvider.');
  return state;
}
export function AccountMenu() {
  const { session, loading } = useSession();
  if (loading) return <span className="account-loading">Cuenta…</span>;
  return session ? <Link className="account-link" href="/fincas"><span className="account-avatar" aria-hidden="true">{session.user.display_name.slice(0, 1).toUpperCase()}</span>Mis fincas</Link>
    : <Link className="account-link" href="/login">Ingresar a mi cuenta <span aria-hidden="true">↗</span></Link>;
}
