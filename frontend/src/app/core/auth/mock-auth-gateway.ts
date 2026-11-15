import { Injectable } from '@angular/core';
import { AuthGateway } from './auth-gateway';
import { AuthError, LoginRequest, RegisterRequest, UserProfile, UserSession } from './auth.models';

const STORAGE_KEY = 'demo-session';
const LATENCY_MS = 350;

/**
 * DEMONSTRATION ONLY — not real authentication.
 *
 * - Accepts any well-formed e-mail and password; nothing is verified.
 * - Passwords are discarded immediately: never stored, logged or sent anywhere.
 * - Only the public profile (name, e-mail) is kept, in sessionStorage, so the demo
 *   survives a reload in the same tab and disappears when the tab is closed.
 * - No account, farm or analysis is stored in a database.
 */
@Injectable()
export class MockAuthGateway extends AuthGateway {
  restore(): UserSession | null {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as UserSession) : null;
    } catch {
      return null;
    }
  }

  async login({ email }: LoginRequest): Promise<UserSession> {
    await delay();
    return this.start({ id: idFor(email), name: nameFromEmail(email), email: normalize(email) });
  }

  async register({ name, email }: RegisterRequest): Promise<UserSession> {
    await delay();
    if (!name.trim()) throw new AuthError('Escribe tu nombre.');
    return this.start({ id: idFor(email), name: name.trim(), email: normalize(email) });
  }

  async requestPasswordReset(): Promise<void> {
    // No e-mail is sent in the demonstration.
    await delay();
  }

  async updateProfile(changes: Pick<UserProfile, 'name'>): Promise<UserSession> {
    await delay();
    const current = this.restore();
    if (!current) throw new AuthError('No hay una sesión activa.');
    return this.persist({ ...current, user: { ...current.user, name: changes.name.trim() } });
  }

  async logout(): Promise<void> {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable: nothing to clear */
    }
  }

  private start(user: UserProfile): UserSession {
    return this.persist({ user, isDemo: true, startedAt: new Date().toISOString() });
  }

  private persist(session: UserSession): UserSession {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch {
      /* private mode / blocked storage: session lives in memory only */
    }
    return session;
  }
}

function delay(): Promise<void> {
  return new Promise((r) => setTimeout(r, LATENCY_MS));
}

function normalize(email: string): string {
  return email.trim().toLowerCase();
}

function idFor(email: string): string {
  return `demo-${normalize(email)}`;
}

function nameFromEmail(email: string): string {
  const local = normalize(email).split('@')[0].replace(/[._-]+/g, ' ').trim();
  return local ? local.charAt(0).toUpperCase() + local.slice(1) : 'Usuario de demostración';
}
