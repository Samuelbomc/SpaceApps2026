import { Injectable, inject } from '@angular/core';
import { createAPIClient, APIError } from '@agrogeo/api-client';
import { AuthService } from '../auth/auth.service';
@Injectable({ providedIn: 'root' })
export class Backend {
  readonly client = createAPIClient();
  private readonly auth = inject(AuthService);
  async write<T>(path: string, method: string, body?: unknown): Promise<T> {
    await this.auth.ready;
    const multipart = body instanceof FormData;
    return this.client.request<T>(path, {
      method,
      headers: {
        ...this.auth.csrfHeaders(),
        ...(multipart ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : multipart ? (body as FormData) : JSON.stringify(body),
    });
  }
}
export function errorMessage(error: unknown): string {
  return error instanceof APIError || error instanceof Error
    ? error.message
    : 'No se pudo completar la operación.';
}
