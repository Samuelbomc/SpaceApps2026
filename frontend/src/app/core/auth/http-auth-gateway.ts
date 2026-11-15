import { Injectable } from '@angular/core';
import { createAPIClient, APIError, type AuthSession } from '@field-shift/api-client';
import { AuthGateway } from './auth-gateway';
import { AuthError, LoginRequest, RegisterRequest, UserProfile, UserSession } from './auth.models';
@Injectable()
export class HttpAuthGateway extends AuthGateway {
  private readonly client = createAPIClient();
  private generation = 0;
  private current: AuthSession | null = null;
  private accept(session: AuthSession): UserSession {
    this.current = session;
    return {
      user: {
        id: session.user.user_id,
        name: session.user.display_name,
        email: session.user.email,
      },
      isDemo: false,
      startedAt: session.user.created_at,
    };
  }
  override async restore(): Promise<UserSession | null> {
    const version = ++this.generation;
    try {
      const session = await this.client.request<AuthSession>('auth/me');
      return version === this.generation ? this.accept(session) : null;
    } catch (error) {
      if (version === this.generation) this.current = null;
      if (error instanceof APIError && error.status === 401) return null;
      throw error;
    }
  }
  override async login(body: LoginRequest): Promise<UserSession> {
    ++this.generation;
    return this.accept(
      await this.client.request<AuthSession>('auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    );
  }
  override async register(body: RegisterRequest): Promise<UserSession> {
    ++this.generation;
    return this.accept(
      await this.client.request<AuthSession>('auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: body.name,
          email: body.email,
          password: body.password,
        }),
      }),
    );
  }
  override csrfHeaders(): Record<string, string> {
    return this.current ? { 'X-CSRF-Token': this.current.csrf_token } : {};
  }
  override async logout(): Promise<void> {
    ++this.generation;
    try {
      await this.client.request('auth/logout', { method: 'POST', headers: this.csrfHeaders() });
    } catch (error) {
      if (!(error instanceof APIError && error.status === 401)) throw error;
    }
    this.current = null;
  }
  override async requestPasswordReset(): Promise<void> {
    throw new AuthError('La recuperación de contraseña todavía no está disponible.');
  }
  override async updateProfile(_changes: Pick<UserProfile, 'name'>): Promise<UserSession> {
    throw new AuthError('La edición de nombre todavía no está disponible.');
  }
}
