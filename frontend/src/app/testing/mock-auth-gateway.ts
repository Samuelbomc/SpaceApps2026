import { Injectable } from '@angular/core';
import { AuthGateway } from '../core/auth/auth-gateway';
import {
  AuthError,
  LoginRequest,
  RegisterRequest,
  UserProfile,
  UserSession,
} from '../core/auth/auth.models';

const STORAGE_KEY = 'test-session';
const LATENCY_MS = 350;

/** Test fixture. Never import this provider from production code. */
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

  async logout(): Promise<void> {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable: nothing to clear */
    }
  }

  private start(user: UserProfile): UserSession {
    return this.persist({ user, startedAt: new Date().toISOString() });
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
  return `test-${normalize(email)}`;
}

function nameFromEmail(email: string): string {
  const local = normalize(email)
    .split('@')[0]
    .replace(/[._-]+/g, ' ')
    .trim();
  return local ? local.charAt(0).toUpperCase() + local.slice(1) : 'Usuario de prueba';
}
