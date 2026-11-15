/** Navigation entries for the header and footer. */
export interface NavLink {
  label: string;
  path: string;
  fragment?: string;
}

export interface NavGroup {
  label: string;
  links: readonly NavLink[];
}

export type NavEntry = ({ kind: 'link' } & NavLink) | ({ kind: 'group' } & NavGroup);

/** "Inicio" dropdown: the home page and its two reference sections. */
export const HOME_GROUP: NavGroup = {
  label: 'Inicio',
  links: [
    { label: 'Inicio', path: '/' },
    { label: 'Cómo funciona', path: '/', fragment: 'como-funciona' },
    { label: 'Fuentes y métodos', path: '/', fragment: 'fuentes' },
  ],
};

/** Shown to visitors without a session. */
export const PUBLIC_NAV: readonly NavEntry[] = [
  { kind: 'link', label: 'Inicio', path: '/' },
  { kind: 'link', label: 'Exploración', path: '/explorar' },
];

/** Shown once the user is signed in. */
export const APP_NAV: readonly NavEntry[] = [
  { kind: 'link', label: 'Exploración', path: '/explorar' },
  { kind: 'link', label: 'Mis fincas', path: '/fincas' },
];
