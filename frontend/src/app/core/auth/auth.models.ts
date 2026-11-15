/** Public profile of the signed-in user. Never contains passwords or tokens. */
export interface UserProfile {
  id: string;
  name: string;
  email: string;
}

export interface UserSession {
  user: UserProfile;
  startedAt: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

/** User-facing error raised by an AuthGateway (message is shown as-is). */
export class AuthError extends Error {}
