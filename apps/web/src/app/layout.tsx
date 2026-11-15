import type { Metadata, Viewport } from 'next';
import 'leaflet/dist/leaflet.css';
import './globals.css';
import { SessionProvider } from '../features/auth/session';

export const metadata: Metadata = {
  title: 'Field Shift · Tu territorio, con contexto',
  description: 'Observaciones NASA para comprender el clima y preparar decisiones agrícolas.',
};

export const viewport: Viewport = { colorScheme: 'dark', themeColor: '#101612' };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es"><body><SessionProvider>{children}</SessionProvider></body></html>;
}
