/**
 * Application identity.
 *
 * The final product name has NOT been decided by the team (see CLAUDE.md,
 * "Project Decision Update"). Everything below is a neutral placeholder;
 * renaming the product only requires editing this file (and index.html <title>).
 */
export const APP_IDENTITY = {
  name: 'Inteligencia Agroterritorial',
  isPlaceholderName: true,
  tagline: 'Inteligencia territorial para una agricultura más resiliente',
  challenge: 'NASA Space Apps Challenge 2026',
  challengeTheme: 'Field Shift: Adapting Farms with NASA Data',
  institution: 'Universidad de Antioquia',
} as const;

/** Builds a consistent browser-tab title for routes. */
export function pageTitle(section: string): string {
  return `${section} · ${APP_IDENTITY.name}`;
}
