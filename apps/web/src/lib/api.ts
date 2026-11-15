// Adaptador temporal del frontend actual. El cliente compartido no depende de Next.js.
export * from '../../../../packages/api-client/src/index.ts';
import { createAPIClient } from '../../../../packages/api-client/src/index.ts';
const client = createAPIClient();
export const api = client.request;
export const loadObservationHistory = client.loadObservationHistory;
