'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useSession } from '../../features/auth/session';
import FarmForm from '../../features/auth/farm-form';
import FarmData from '../../features/auth/farm-data';
import { api, APIError, type Farm, type FarmCatalog } from '../../lib/api';

export default function FarmsPage() {
  const router = useRouter();
  const { session, loading, signOut, refresh: refreshSession } = useSession();
  const [farms, setFarms] = useState<Farm[]>([]);
  const [catalog, setCatalog] = useState<FarmCatalog | null>(null);
  const [owner, setOwner] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [editing, setEditing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  useEffect(() => { if (!loading && !session) router.replace('/login'); }, [session, loading, router]);
  useEffect(() => {
    if (!session) return;
    const controller = new AbortController(); setError('');
    Promise.all([api<Farm[]>('farms', { signal: controller.signal }), api<FarmCatalog>('farms/catalog', { signal: controller.signal })])
      .then(([items, options]) => { if (!controller.signal.aborted) { setFarms(items); setCatalog(options); setOwner(session.user.user_id); setSelectedId(current => items.some(item => item.farm_id === current) ? current : items[0]?.farm_id || ''); setCreating(!items.length); } })
      .catch(reason => { if (!controller.signal.aborted) { setError(reason instanceof Error ? reason.message : 'No se pudo consultar tu catálogo.'); if (reason instanceof APIError && reason.status === 401) void refreshSession(); } });
    return () => controller.abort();
  }, [session?.user.user_id, refresh, refreshSession]); // eslint-disable-line react-hooks/exhaustive-deps
  async function logout() { try { await signOut(); router.replace('/login'); } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo cerrar la sesión.'); } }
  if (loading || !session) return <div className="workspace-loading" role="status">Consultando tu cuenta…</div>;
  const ready = owner === session.user.user_id && catalog !== null;
  const farm = ready ? farms.find(item => item.farm_id === selectedId) : undefined;
  function saved(value: Farm) { setFarms(current => [...current.filter(item => item.farm_id !== value.farm_id), value]); setSelectedId(value.farm_id); setCreating(false); setEditing(false); }
  return <div className="farm-app"><header className="farm-header"><Link href="/" className="brand">field<span>shift</span></Link><Link href="/">← Ver territorio</Link><div><span>{session.user.display_name}</span><button className="secondary" onClick={() => void logout()}>Cerrar sesión</button></div></header>
    <main className="farm-main"><div className="heading"><div><span className="eyebrow">TU INFORMACIÓN, EN UN SOLO LUGAR</span><h1>Mis fincas<span>.</span></h1><p>Configura tus ubicaciones y conserva los datos que conoces de tu tierra.</p></div><button className="primary" disabled={!ready} onClick={() => { setCreating(true); setEditing(false); }}>Registrar finca <span>＋</span></button></div>
      {error && <div className="form-error" role="alert">{error} <button className="secondary" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></div>}
      {!ready ? (error ? null : <p role="status">Cargando tu catálogo…</p>) : <div className="farm-workspace"><aside className="farm-list"><span className="small-label">TUS UBICACIONES · {farms.length}</span>{farms.map(item => <button key={item.farm_id} aria-pressed={selectedId === item.farm_id && !creating} onClick={() => { setSelectedId(item.farm_id); setCreating(false); setEditing(false); }}><strong>{item.name}</strong><span>{item.municipality || 'Municipio sin especificar'}</span><small>{item.area_ha.toLocaleString('es-CO')} ha</small></button>)}{!farms.length && <p>Tu primera finca aparecerá aquí cuando la guardes.</p>}</aside>
        <div className="farm-details">{creating || editing ? <FarmForm key={creating ? 'new-farm' : `${farm?.farm_id}-${farm?.revision}`} farm={creating ? undefined : farm} catalog={catalog} csrf={session.csrf_token} onSaved={saved} onCancel={() => { setCreating(false); setEditing(false); }} /> : farm ? <>
          <section className="farm-card"><div className="farm-card-heading"><div><span className="eyebrow">FICHA DE LA FINCA</span><h2>{farm.name}</h2><p className="farm-help">{farm.municipality || 'Municipio sin especificar'} · Actualizada el {new Date(farm.updated_at).toLocaleDateString('es-CO')}</p></div><button className="secondary" onClick={() => setEditing(true)}>Editar ficha</button></div>
            <dl className="farm-facts"><div><dt>Superficie</dt><dd>{farm.area_ha.toLocaleString('es-CO')} ha</dd></div><div><dt>Suelo</dt><dd>{catalog.soil_textures.find(item => item.value === farm.soil_texture)?.label || 'Sin especificar'}</dd></div><div><dt>Riego</dt><dd>{catalog.irrigation_types.find(item => item.value === farm.irrigation)?.label || 'Sin especificar'}</dd></div><div><dt>pH</dt><dd>{farm.soil_ph ?? 'Sin medición'}</dd></div><div><dt>Cultivos</dt><dd>{farm.current_crops?.join(', ') || 'Sin especificar'}</dd></div><div><dt>Ubicación</dt><dd>{farm.latitude.toFixed(5)}, {farm.longitude.toFixed(5)}{farm.boundary ? ' · Área delimitada' : ' · Punto'}</dd></div></dl>{farm.notes && <p className="farm-help">{farm.notes}</p>}
          </section><FarmData key={`${farm.farm_id}-${farm.revision}`} farmId={farm.farm_id} csrf={session.csrf_token} catalog={catalog} />
        </> : <div className="farm-empty"><h2>Empieza por registrar tu finca.</h2><button className="primary" onClick={() => setCreating(true)}>Registrar finca</button></div>}</div>
      </div>}
    </main></div>;
}
