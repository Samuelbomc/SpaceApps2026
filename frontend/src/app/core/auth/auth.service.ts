import { Injectable, computed, inject, signal } from '@angular/core';
import { AuthGateway } from './auth-gateway';
import { LoginRequest, RegisterRequest, UserSession } from './auth.models';

/**
 * Session state for the UI (signals). Components talk to this service only;
 * the gateway behind it decides how authentication actually happens.
 *
 * NOTE: route guards in the frontend are a UX convenience. Real access control
 * must be enforced by the backend once it exists.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly gateway = inject(AuthGateway);
  private readonly sessionState = signal<UserSession | null>(this.gateway.restore());

  readonly session = this.sessionState.asReadonly();
  readonly user = computed(() => this.sessionState()?.user ?? null);
  readonly isAuthenticated = computed(() => this.sessionState() !== null);
  readonly isDemo = computed(() => this.sessionState()?.isDemo ?? false);

  async login(request: LoginRequest): Promise<void> {
    this.sessionState.set(await this.gateway.login(request));
  }

  async register(request: RegisterRequest): Promise<void> {
    this.sessionState.set(await this.gateway.register(request));
  }

  requestPasswordReset(email: string): Promise<void> {
    return this.gateway.requestPasswordReset(email);
  }

  async updateName(name: string): Promise<void> {
    this.sessionState.set(await this.gateway.updateProfile({ name }));
  }

  async logout(): Promise<void> {
    await this.gateway.logout();
    this.sessionState.set(null);
  }
}
