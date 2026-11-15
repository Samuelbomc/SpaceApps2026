/** Identidad compartida de AgroGeo para navegación, títulos y contenido. */
export const APP_IDENTITY = {
  name: 'AgroGeo',
  tagline: 'Inteligencia territorial para una agricultura más resiliente',
  challenge: 'NASA Space Apps Challenge 2026',
  institution: 'Universidad de Antioquia',
} as const;

/** Builds a consistent browser-tab title for routes. */
export function pageTitle(section: string): string {
  return `${section} · ${APP_IDENTITY.name}`;
}
