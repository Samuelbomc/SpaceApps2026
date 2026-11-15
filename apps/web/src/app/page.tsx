'use client';

import { useEffect, useState } from 'react';
import { AccountMenu } from '../features/auth/session';
import Link from 'next/link';
import AreaMap from '../features/map/area-map';
import type { Coordinate } from '../features/map/area';
import { SimpleConditions, TechnicalObservations, AnalysisTrace } from '../features/analysis/observation-views';
import { api, APIError, loadObservationHistory, type Analysis, type MapPlace, type ObservationHistory, type Region, type Status } from '../lib/api';

const labels: Record<string, string> = {
  T2M: 'Temperatura media', T2M_MIN: 'Temperatura mínima', T2M_MAX: 'Temperatura máxima',
  RH2M: 'Humedad relativa', WS2M: 'Viento a 2 m', WS10M: 'Viento a 10 m', ALLSKY_SFC_SW_DWN: 'Radiación solar',
};
const analysisLabels: Record<Analysis['status'], string> = {
  pending_model: 'Modelos pendientes', insufficient_data: 'Observaciones insuficientes',
  pending_run: 'Análisis aún no generado',
  pending_recommendations: 'Motor agronómico pendiente', ready: 'Análisis disponible',
};
const simpleAnalysisLabels: Record<Analysis['status'], string> = {
  pending_model: 'Las predicciones aún no están disponibles.',
  insufficient_data: 'Faltan datos para preparar las predicciones.',
  pending_run: 'Las predicciones todavía no se han calculado.',
  pending_recommendations: 'Predicciones disponibles; recomendaciones en preparación.',
  ready: 'Predicciones disponibles.',
};
function displayUnit(unit: string) {
  return ({ C: '°C', '%': '%', 'm/s': 'm/s', 'MJ/m^2/day': 'MJ/m²/día', 'kW-hr/m^2/day': 'kWh/m²/día' } as Record<string, string>)[unit] || unit;
}
function dateAfter(value: string, days: number) {
  const day = new Date(`${value}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() + days);
  return day.toISOString().slice(0, 10);
}
function queryDate() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}
const planningHorizons = [7, 15, 30, 60] as const;

export default function Home() {
  const [queriedOn, setQueriedOn] = useState(queryDate);
  const [technical, setTechnical] = useState(false);
  const [regions, setRegions] = useState<Region[]>([]);
  const [regionId, setRegionId] = useState('');
  const [status, setStatus] = useState<Status | null>(null);
  const [observations, setObservations] = useState<ObservationHistory | null>(null);
  const [observationRefresh, setObservationRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [horizonDays, setHorizonDays] = useState<number>(7);
  const [analysisRefresh, setAnalysisRefresh] = useState(0);
  const [analysisError, setAnalysisError] = useState('');
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [mapCenter, setMapCenter] = useState<Coordinate | null>(null);
  const [mapPlace, setMapPlace] = useState<MapPlace | null>(null);
  const [locating, setLocating] = useState(false);
  const [placeError, setPlaceError] = useState(false);
  const centerLatitude = mapCenter ? Number(mapCenter.latitude.toFixed(3)) : null;
  const centerLongitude = mapCenter ? Number(mapCenter.longitude.toFixed(3)) : null;

  useEffect(() => {
    if (centerLatitude === null || centerLongitude === null) return;
    const controller = new AbortController();
    setMapPlace(null); setPlaceError(false); setLocating(true);
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout>;
    async function lookup() {
      try {
        const place = await api<MapPlace>(`places/reverse?latitude=${centerLatitude}&longitude=${centerLongitude}`, { signal: controller.signal });
        if (!controller.signal.aborted) { setMapPlace(place); setLocating(false); }
      } catch (reason) {
        if (controller.signal.aborted) return;
        if (reason instanceof APIError && [429, 503].includes(reason.status) && attempts < 2) {
          attempts += 1; timer = setTimeout(lookup, 2000 * attempts);
        } else { setPlaceError(true); setLocating(false); }
      }
    }
    // Consultar tras detener el mapa; el movimiento y zoom continuos no generan solicitudes.
    timer = setTimeout(lookup, 900);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [centerLatitude, centerLongitude]);

  useEffect(() => {
    try { setTechnical(window.localStorage.getItem('fieldshift.technical-view') === 'true'); }
    catch { /* La vista sigue funcionando si el navegador bloquea el almacenamiento. */ }
  }, []);

  function selectView(next: boolean) {
    setTechnical(next);
    try { window.localStorage.setItem('fieldshift.technical-view', String(next)); }
    catch { /* La preferencia se mantiene durante esta sesión de la página. */ }
  }

  useEffect(() => {
    let active = true;
    Promise.all([api<Region[]>('regions'), api<Status>('status')])
      .then(([items, state]) => {
        if (!active) return;
        setRegions(items); setRegionId(items[0]?.region_id || ''); setStatus(state);
      }).catch(e => { if (active) setError(e.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!regionId) return;
    const controller = new AbortController();
    setLoading(true); setHistoryError(''); setObservations(null);
    loadObservationHistory(regionId, controller.signal)
      .then(history => { if (!controller.signal.aborted) setObservations(history); })
      .catch(e => { if (!controller.signal.aborted) setHistoryError(e instanceof Error ? e.message : 'No se pudo consultar el histórico completo.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [regionId, observationRefresh]);

  useEffect(() => {
    if (!regionId) return;
    const controller = new AbortController();
    setAnalyzing(true); setAnalysis(null); setAnalysisError('');
    api<Analysis | null>(`regions/${encodeURIComponent(regionId)}/latest-analysis?horizon_days=${horizonDays}&as_of=${queriedOn}`,
      { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setAnalysis(result); })
      .catch(e => {
        if (!controller.signal.aborted) setAnalysisError(e instanceof Error ? e.message : 'No se pudo consultar el análisis.');
      })
      .finally(() => { if (!controller.signal.aborted) setAnalyzing(false); });
    return () => controller.abort();
  }, [regionId, horizonDays, analysisRefresh, queriedOn]);

  function requestAnalysis() { setQueriedOn(queryDate()); setAnalysisRefresh(value => value + 1); }
  const region = regions.find(item => item.region_id === regionId);
  const history = observations?.region_id === regionId ? observations : null;
  const rows = history?.items || [];
  const latest = Object.values(rows.reduce<Record<string, (typeof rows)[number]>>((items, row) => {
    if (!items[row.variable] && row.value !== null && row.quality === 'provider_value_unvalidated') items[row.variable] = row;
    return items;
  }, {}));
  const nextRun = status?.schedule?.retry_at || status?.schedule?.next_run_at;
  const runDate = nextRun ? new Date(nextRun).toLocaleString('es-CO', { timeZone: 'America/Bogota', dateStyle: 'medium', timeStyle: 'short' }) : null;
  const latestAnalysis = analysis?.request.region_id === regionId && (analysis.request.horizon_days ?? 7) === horizonDays && analysis.request.forecast_start_date === queriedOn ? analysis : null;
  const modelReady = status?.climate_model === 'configured' && status?.soil_model === 'configured';

  const updatedAt = history?.last_updated_at ? new Date(history.last_updated_at).toLocaleString('es-CO', { timeZone: 'America/Bogota', dateStyle: 'long', timeStyle: 'short' }) : null;
  const historicalContent = <>
    {historyError && <div className="error" role="alert"><strong>No se pudo consultar el histórico.</strong><p>{historyError}</p></div>}
    <TechnicalObservations rows={rows} total={history?.total ?? 0} loading={loading} />
  </>;
  const analysisContent = <>
        <section className="planning-controls" aria-label="Plazo de predicciones y recomendaciones">
          <label htmlFor="planning-horizon">{technical ? 'Horizonte del análisis' : '¿A cuántos días quieres planificar?'}
            <select id="planning-horizon" value={horizonDays} disabled={!regionId} onChange={event => { setQueriedOn(queryDate()); setHorizonDays(Number(event.target.value)); }}>
              {planningHorizons.map(days => <option key={days} value={days}>{days} días</option>)}
            </select>
          </label>
          {analyzing && <span className="planning-status" role="status">Consultando el análisis de {horizonDays} días…</span>}
        </section>
        {analysisError && <div className="error" role="alert"><strong>No se pudo consultar el análisis de {horizonDays} días.</strong><p>{technical ? analysisError : 'Intenta consultar de nuevo en unos momentos.'}</p><button onClick={requestAnalysis}>Reintentar análisis</button></div>}
        <div className="analysis-period" aria-live="polite" aria-atomic="true">
          <span className="eyebrow">PERIODO DE PREDICCIONES Y RECOMENDACIONES</span>
          <h2>Análisis para un periodo de los próximos <span>{horizonDays} días</span></h2>
          {latestAnalysis && latestAnalysis.request.reference_date < dateAfter(queriedOn, -7) && <p className="period-warning">Las últimas observaciones tienen más de siete días de antigüedad y pueden no reflejar las condiciones actuales.</p>}
        </div>
        <div className="analysis-sections" aria-busy={analyzing}>
          <section id="predictions" className="section-destination" aria-labelledby="predictions-title">
            <div className="section-heading"><div><span className="eyebrow">CLIMA Y SUELO</span><h2 id="predictions-title">Predicciones</h2></div></div>
            <div className="empty"><span className="empty-icon">◷</span><h3>{analyzing ? 'Consultando predicciones…' : latestAnalysis ? (technical ? analysisLabels : simpleAnalysisLabels)[latestAnalysis.status] : 'Las predicciones están por llegar.'}</h3><p>{technical && latestAnalysis?.messages?.length ? latestAnalysis.messages.join(' ') : 'Aquí verás las predicciones de clima y suelo cuando estén disponibles.'}</p>
              {[latestAnalysis?.climate, latestAnalysis?.soil].map(forecast => forecast && <div className="result-values" key={forecast.model_kind}><h4>{forecast.model_kind === 'climate' ? 'Clima' : 'Suelo'}</h4>{technical && <p>Modelo: {forecast.model_version}</p>}{forecast.values.map(item => <p key={item.variable}>{technical ? item.variable : labels[item.variable] || item.variable}: <strong>{item.value} {technical ? item.unit : displayUnit(item.unit)}</strong>{technical && <> · {item.aggregation}</>}</p>)}{Boolean(forecast.limitations?.length) && <p>{forecast.limitations?.join(' · ')}</p>}</div>)}
              <button className="primary" onClick={() => void requestAnalysis()} disabled={!regionId || analyzing}>{analyzing ? 'Consultando…' : technical ? `Consultar análisis a ${horizonDays} días` : 'Consultar predicciones'} <span>↗</span></button>
            </div>
          </section>
          <section id="recommendations" className="section-destination" aria-labelledby="recommendations-title">
            <div className="section-heading"><div><span className="eyebrow">PLANIFICA TU COSECHA</span><h2 id="recommendations-title">Rotaciones y cultivos</h2></div></div>
            <div className="empty">{technical && latestAnalysis?.recommendations && <p>Motor: {latestAnalysis.recommendations.engine_version}</p>}<span className="empty-icon">♧</span><h3>{analyzing ? 'Consultando recomendaciones…' : latestAnalysis?.recommendations ? 'Alternativas para comparar.' : `Aún no hay recomendaciones para ${horizonDays} días.`}</h3><p>{technical ? 'Las recomendaciones combinarán clima, suelo, requisitos de cultivos y reglas agronómicas locales.' : 'Aquí podrás comparar opciones de cultivos y el orden en que podrías sembrarlos.'}</p>{latestAnalysis?.recommendations?.alternatives.map(rotation => <article className="rotation" key={rotation.name}><h4>{rotation.name}</h4><p>{rotation.crops.join(' → ')}</p><p>{rotation.reasons.join(' · ')}</p><p>{rotation.risks?.join(' · ')}</p></article>) || <span className="tag">{technical ? 'Motor agronómico pendiente' : 'Recomendaciones aún no disponibles'}</span>}</div>
          </section>
        </div>
  </>;

  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Field Shift inicio">field<span>shift</span><sup>●</sup></a>
      <div className="workspace"><span>NASA Space Apps · Colombia</span></div>
      <nav aria-label="Secciones"><a href="#territory" className="nav-active" aria-current="page">◫ <span>Mi territorio</span><span className="nav-arrow">↗</span></a><Link href="/fincas">♧ <span>Mis fincas y datos</span></Link></nav>
      <div className="sidebar-note"><span className="orbit">◎</span><strong>Fuentes de datos</strong><p>NASA POWER, GPM, SMAP, SRTM, Landsat, ECOSTRESS y GRACE.</p>{technical && <span className="small-label">RESOLUCIÓN NATIVA POR FUENTE</span>}</div>
      <div className="sidebar-footer"><span className="avatar">FS</span><div>Field Shift<small>Entorno de desarrollo</small></div></div>
    </aside>
    <main>
      <header className="topbar"><span><strong>Análisis de tu territorio</strong></span><div className="view-controls"><AccountMenu /><span className="environment"><i /> Datos históricos</span><fieldset className="view-selector" aria-describedby="view-description">
        <legend>Nivel de detalle</legend>
        <div className="view-options">
          <label className="view-option"><input type="radio" name="view-detail" value="simple" checked={!technical} onChange={() => selectView(false)} /><span>Simple</span></label>
          <label className="view-option"><input type="radio" name="view-detail" value="technical" checked={technical} onChange={() => selectView(true)} /><span>Técnico</span></label>
        </div>
      </fieldset></div></header>
      <div className="content">
        <div className="heading"><div><div className="eyebrow">CADA DECISIÓN EMPIEZA CON CONTEXTO</div><h1>Conoce tu territorio<span>.</span></h1><p>Explora las condiciones que acompañan a tu próxima cosecha.</p></div><span className="period-badge">↻ {technical ? 'Ingesta cada 7 días' : 'Actualización cada 7 días'}</span></div>
        <p id="view-description" className="view-description" aria-live="polite">{technical ? 'Explora series históricas, cobertura, calidad de las fuentes y trazabilidad de los modelos.' : 'Consulta las predicciones, compara opciones de cultivo y revisa las condiciones recientes de tu zona.'}</p>
        <section className="map-location" aria-label="Lugar en el mapa"><div><span className="small-label">EXPLORANDO EN EL MAPA</span><strong role="status" aria-live="polite">{locating ? 'Identificando el lugar…' : mapPlace?.label || (placeError ? 'No se pudo identificar el lugar' : mapCenter ? 'Lugar sin nombre disponible' : 'Cargando mapa…')}</strong></div>{mapCenter && (technical || (!locating && !mapPlace?.label)) && <span className="map-location-coordinates">{mapCenter.latitude.toFixed(5)}, {mapCenter.longitude.toFixed(5)}</span>}</section>
        <div className="data-update" role="status"><div><span className="small-label">Última actualización de los datos</span><strong>{loading ? 'Consultando…' : historyError ? 'No disponible' : updatedAt || 'Sin datos almacenados'}</strong></div><button disabled={loading || !regionId} onClick={() => { requestAnalysis(); setObservationRefresh(value => value + 1); }}>Actualizar vista</button></div>
        {historyError && !technical && <p className="observation-note" role="alert">No pudimos cargar todos los datos. Actualiza la vista para reintentar.</p>}
        {error && <div className="error" role="alert"><strong>No se pudo completar la consulta.</strong><p>{technical ? error : 'No pudimos cargar la información. Intenta de nuevo en unos momentos.'}</p><button onClick={() => window.location.reload()}>Reintentar conexión</button></div>}
        <section className="overview section-destination" id="territory" aria-label="Mapa y estado del territorio"><div className="map-panel">
          {region ? <AreaMap latitude={region.latitude} longitude={region.longitude} name={region.name} technical={technical} onCenterChange={setMapCenter} /> : <div className="map-placeholder"><div className="crosshair">⊕</div><p>{loading ? 'Cargando ubicaciones…' : 'Conecta la API para explorar una ubicación'}</p></div>}
        </div><div className="context-card"><span className="small-label">EL ESTADO DE TUS DATOS</span><h2>Primero observar.<br />Después decidir.</h2><p>{technical ? 'Consulta la ingesta y la disponibilidad de los modelos.' : 'Estos datos describen tu zona. Las predicciones y las recomendaciones aparecerán cuando estén listas.'}</p>
          {technical ? <>
            <div className="context-line"><span>Última ingesta</span><strong>{status?.recent_runs[0]?.status || 'Sin ejecuciones registradas'}</strong></div>
            <div className="context-line"><span>Próxima ejecución</span><strong>{runDate || 'Sin programación conectada'}</strong></div>
            {Boolean(status?.schedule?.pending_sources?.length) && <div className="context-line"><span>Fuentes pendientes</span><strong>{status?.schedule?.pending_sources?.join(', ')}</strong></div>}
            <div className="context-line"><span>Fallos consecutivos</span><strong>{status?.schedule?.consecutive_failures ?? 0}</strong></div>
            {status?.schedule?.last_error && <p>{status.schedule.last_error}</p>}
            <div className="context-line"><span>Modelos predictivos</span><strong>{modelReady ? 'Configurados' : 'Por implementar'}</strong></div>
          </> : <>
            <div className="context-line"><span>Datos de la zona</span><strong>{loading ? 'Buscando…' : latest.length ? 'Hay observaciones disponibles' : 'Sin datos disponibles'}</strong></div>
            <div className="context-line"><span>Actualización</span><strong>{!status ? 'Sin conexión' : status.schedule?.retry_at ? 'Reintentando obtener datos' : !status.recent_runs.length ? 'Primera actualización pendiente' : status.recent_runs[0].status === 'ok' ? 'Última consulta completada' : 'Consulta en proceso o incompleta'}</strong></div>
            <div className="context-line"><span>Predicciones</span><strong>{latestAnalysis?.climate || latestAnalysis?.soil ? 'Hay resultados disponibles' : 'Aún sin resultados'}</strong></div>
          </>}
        </div></section>
        {technical ? <>
          {historicalContent}
          {analysisContent}
          <AnalysisTrace analysis={latestAnalysis} />
        </> : <>
          {analysisContent}
          <SimpleConditions rows={rows} loading={loading} />
        </>}
        <footer className="page-footer"><span>FIELD SHIFT <span>·</span> NASA SPACE APPS</span><p>{technical ? 'La escala del dato importa. Una ubicación precisa conserva la resolución nativa de cada fuente.' : 'Información de tu zona para acompañar tus decisiones agrícolas.'}</p></footer>
      </div>
    </main>
  </div>;
}
