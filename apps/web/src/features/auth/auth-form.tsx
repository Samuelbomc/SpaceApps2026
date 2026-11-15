'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useSession } from './session';

export default function AuthForm({ register = false }: { register?: boolean }) {
  const router = useRouter();
  const { session, loading, authenticate, error: connectionError } = useSession();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [show, setShow] = useState(false);
  useEffect(() => { if (session) router.replace('/fincas'); }, [session, router]);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError('');
    const form = new FormData(event.currentTarget);
    const password = String(form.get('password'));
    if (register && password !== form.get('confirm')) { setError('Las contraseñas no coinciden.'); return; }
    setPending(true);
    try {
      await authenticate(register ? 'register' : 'login', { email: String(form.get('email')), password,
        ...(register ? { display_name: String(form.get('display_name')) } : {}) });
      router.replace('/fincas');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo acceder a tu cuenta.'); }
    finally { setPending(false); }
  }
  return <div className="auth-shell"><div className="auth-story">
    <Link href="/" className="brand">field<span>shift</span></Link>
    <div><span className="eyebrow">CADA FINCA TIENE SU HISTORIA</span><h1>Tu tierra.<br />Tus datos.<br /><span>Un mejor contexto.</span></h1><p>Organiza la información de tu finca y reúne tus mediciones en un mismo lugar.</p><div className="auth-benefits"><span>01 <strong>Registra tus fincas</strong></span><span>02 <strong>Conserva tus observaciones</strong></span><span>03 <strong>Prepara análisis con datos propios</strong></span></div></div>
    <p className="auth-local-note">Tus archivos se guardan en el servidor local del proyecto y se consultan desde tu cuenta.</p>
  </div><div className="auth-panel"><Link className="back-link" href="/">← Volver al territorio</Link><div className="auth-card">
    <span className="eyebrow">TU ESPACIO EN FIELD SHIFT</span><h2>{register ? 'Crea tu cuenta' : 'Qué bueno volver a tu finca.'}</h2><p>{register ? 'Empieza con tus datos de acceso. Después podrás registrar tu primera finca.' : 'Ingresa para consultar tus fincas y sus datasets.'}</p>
    <form onSubmit={event => void submit(event)}>
      {register && <label>Tu nombre<input name="display_name" required maxLength={100} autoComplete="name" placeholder="¿Cómo te llamas?" disabled={pending} /></label>}
      <label>Correo electrónico<input name="email" type="email" required maxLength={254} autoComplete="email" placeholder="tu@correo.com" disabled={pending} /></label>
      <label>Contraseña<div className="password-field"><input name="password" type={show ? 'text' : 'password'} required minLength={register ? 15 : 1} maxLength={128} autoComplete={register ? 'new-password' : 'current-password'} placeholder={register ? 'Al menos 15 caracteres' : 'Tu contraseña'} disabled={pending} /><button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Ocultar contraseña' : 'Mostrar contraseña'}>{show ? 'Ocultar' : 'Mostrar'}</button></div></label>
      {register && <label>Repite tu contraseña<input name="confirm" type={show ? 'text' : 'password'} required minLength={15} maxLength={128} autoComplete="new-password" disabled={pending} /></label>}
      {(error || connectionError) && <div className="form-error" role="alert">{error || connectionError}</div>}
      <button className="primary" disabled={pending || loading} type="submit">{pending ? 'Un momento…' : register ? 'Crear mi cuenta' : 'Ingresar'} <span>↗</span></button>
    </form>
    <p className="auth-alternative">{register ? '¿Ya tienes una cuenta?' : '¿Es tu primera visita?'} <Link href={register ? '/login' : '/registro'}>{register ? 'Inicia sesión' : 'Crea tu cuenta'}</Link></p>
  </div></div></div>;
}
