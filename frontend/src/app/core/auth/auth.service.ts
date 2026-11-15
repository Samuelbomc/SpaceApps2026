import { Injectable, DestroyRef, computed, inject, signal } from '@angular/core';
import { AuthGateway } from './auth-gateway';
import { LoginRequest, RegisterRequest, UserSession } from './auth.models';

/**
 * Session state for the UI (signals). Components talk to this service only;
 * the gateway behind it decides how authentication actually happens.
 *
 * NOTE: route guards in the frontend are a UX convenience. Real access control
 * is enforced by FastAPI.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly gateway = inject(AuthGateway);
  private readonly sessionState = signal<UserSession | null>(null);

  readonly loading = signal(true);
  readonly error = signal('');
  private generation = 0;
  readonly ready = this.restore();
  constructor() {
    if (typeof window === 'undefined') return;
    const focus = () => {
      void this.restore();
    };
    window.addEventListener('focus', focus);
    inject(DestroyRef).onDestroy(() => window.removeEventListener('focus', focus));
  }
  private async restore(): Promise<void> {
    const version = ++this.generation;
    try {
      const session = await this.gateway.restore();
      if (version === this.generation) {
        this.sessionState.set(session);
        this.error.set('');
      }
    } catch {
      if (version === this.generation) {
        this.sessionState.set(null);
        this.error.set('No pudimos comprobar la sesión. Reintenta iniciar sesión.');
      }
    } finally {
      if (version === this.generation) this.loading.set(false);
    }
  }
  csrfHeaders(): Record<string, string> {
    return this.gateway.csrfHeaders();
  }
  readonly session = this.sessionState.asReadonly();
  readonly user = computed(() => this.sessionState()?.user ?? null);
  readonly isAuthenticated = computed(() => this.sessionState() !== null);
  readonly isDemo = computed(() => this.sessionState()?.isDemo ?? false);

  async login(request: LoginRequest): Promise<void> {
    await this.ready;
    const version = ++this.generation;
    const session = await this.gateway.login(request);
    if (version !== this.generation) return;
    this.sessionState.set(session);
    this.error.set('');
  }

  async register(request: RegisterRequest): Promise<void> {
    await this.ready;
    const version = ++this.generation;
    const session = await this.gateway.register(request);
    if (version !== this.generation) return;
    this.sessionState.set(session);
    this.error.set('');
  }

  requestPasswordReset(email: string): Promise<void> {
    return this.gateway.requestPasswordReset(email);
  }

  async updateName(name: string): Promise<void> {
    this.sessionState.set(await this.gateway.updateProfile({ name }));
  }

  async logout(): Promise<void> {
    ++this.generation;
    await this.gateway.logout();
    this.sessionState.set(null);
  }
}
