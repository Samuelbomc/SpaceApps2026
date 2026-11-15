import { LoginRequest, RegisterRequest, UserProfile, UserSession } from './auth.models';

/**
 * Contract between the UI and whatever performs authentication.
 *
 * Today it is implemented by MockAuthGateway (frontend-only demonstration).
 * When the FastAPI backend exists, add an HttpAuthGateway that implements this
 * class and swap the provider in app.config.ts — no component needs to change.
 */
export abstract class AuthGateway {
  /** Restores an existing session (e.g. after a page reload), if any. */
  abstract restore(): UserSession | null;
  abstract login(request: LoginRequest): Promise<UserSession>;
  abstract register(request: RegisterRequest): Promise<UserSession>;
  abstract requestPasswordReset(email: string): Promise<void>;
  abstract updateProfile(changes: Pick<UserProfile, 'name'>): Promise<UserSession>;
  abstract logout(): Promise<void>;
}
