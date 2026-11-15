import { LoginRequest, RegisterRequest, UserSession } from './auth.models';

/** Authentication contract. HttpAuthGateway delegates production access to FastAPI. */
export abstract class AuthGateway {
  /** Restores an existing session (e.g. after a page reload), if any. */
  abstract restore(): Promise<UserSession | null> | UserSession | null;
  csrfHeaders(): Record<string, string> {
    return {};
  }
  abstract login(request: LoginRequest): Promise<UserSession>;
  abstract register(request: RegisterRequest): Promise<UserSession>;
  abstract logout(): Promise<void>;
}
