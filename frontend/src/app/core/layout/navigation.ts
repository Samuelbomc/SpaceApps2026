/** Primary navigation entries, shared by the header and footer. */
export interface NavItem {
  label: string;
  path: string;
  fragment?: string;
}

export const PRIMARY_NAV: readonly NavItem[] = [
  { label: 'Inicio', path: '/' },
  { label: 'Portal de datos', path: '/datos' },
  { label: 'Espacio del agricultor', path: '/agricultor' },
  { label: 'Fuentes y método', path: '/', fragment: 'fuentes' },
];
