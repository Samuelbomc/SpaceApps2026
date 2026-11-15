'use client';
import { useEffect, useRef, useState } from 'react';
import { api, type DatasetUploadResult, type FarmCatalog, type FarmDataset, type FarmModelContext } from '../../lib/api';

export default function FarmData({ farmId, csrf, catalog }: { farmId: string; csrf: string; catalog: FarmCatalog }) {
  const [datasets, setDatasets] = useState<FarmDataset[]>([]);
  const [context, setContext] = useState<FarmModelContext | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setLoaded(false); setContext(null); setError('');
    Promise.all([api<FarmDataset[]>(`farms/${farmId}/datasets`, { signal: controller.signal }), api<FarmModelContext>(`farms/${farmId}/model-context`, { signal: controller.signal })])
      .then(([items, metadata]) => { if (!controller.signal.aborted) { setDatasets(items); setContext(metadata); setLoaded(true); } })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'No se pudieron cargar los archivos.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [farmId, refresh]);
  function template() {
    const url = URL.createObjectURL(new Blob([[...catalog.required_columns, ...catalog.optional_columns].join(',') + '\n'], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'plantilla-datos-finca.csv'; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const selected = file.current?.files?.[0]; if (!selected) return;
    if (selected.size > catalog.max_file_bytes) { setError('El CSV no puede superar 5 MiB.'); return; }
    setBusy(true); setError(''); setNotice('');
    const body = new FormData(); body.append('file', selected);
    try {
      const result = await api<DatasetUploadResult>(`farms/${farmId}/datasets`, { method: 'POST', headers: { 'X-CSRF-Token': csrf }, body });
      setNotice(result.duplicate ? 'Este archivo ya estaba registrado. No se duplicaron sus datos.' : `Dataset guardado: ${result.dataset.row_count} observaciones.`);
      if (file.current) file.current.value = '';
      setRefresh(value => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo cargar el CSV.'); }
    finally { setBusy(false); }
  }
  async function remove(dataset: FarmDataset) {
    if (!window.confirm(`¿Eliminar ${dataset.original_filename} y sus observaciones de esta finca?`)) return;
    setBusy(true); setError(''); setNotice('');
    try { await api<void>(`farms/${farmId}/datasets/${dataset.dataset_id}`, { method: 'DELETE', headers: { 'X-CSRF-Token': csrf } }); setNotice('Dataset eliminado.'); setRefresh(value => value + 1); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo eliminar el archivo.'); }
    finally { setBusy(false); }
  }
  return <>
    <section className="farm-card"><div className="farm-card-heading"><div><span className="eyebrow">MEDICIONES PROPIAS</span><h2>Datos de tu finca</h2></div><button className="secondary" onClick={template}>Descargar plantilla CSV</button></div>
      <p className="farm-help">Carga tus observaciones históricas de clima, suelo o cosecha. Cada archivo se guarda de forma privada en el servidor local del proyecto.</p>
      <form className="dataset-upload" onSubmit={event => void upload(event)}><label htmlFor="farm-file">Selecciona un archivo CSV<input ref={file} id="farm-file" type="file" accept=".csv,text/csv" required disabled={busy} /></label><button className="primary" disabled={busy}>{busy ? 'Procesando…' : 'Cargar dataset'} <span>↗</span></button></form>
      <p className="farm-help">Hasta 5 MiB y {catalog.max_rows.toLocaleString('es-CO')} filas. UTF-8, fechas AAAA-MM-DD y punto decimal. Usa una fila por fecha, variable y cultivo; el cultivo solo es obligatorio para el rendimiento de una cosecha.</p>
      <details className="dataset-guide"><summary>Ver variables y unidades admitidas</summary><div className="data-table"><table><thead><tr><th>Dato</th><th>Variable en CSV</th><th>Unidad exacta</th></tr></thead><tbody>{catalog.variables.map(item => <tr key={item.variable}><td>{item.label}</td><td><code>{item.variable}</code></td><td>{item.unit}</td></tr>)}</tbody></table></div></details>
      {error && <div className="form-error" role="alert">{error}</div>}{notice && <p className="success-note" role="status">{notice}</p>}
      {loading ? <p className="farm-help" role="status">Consultando archivos…</p> : !loaded ? <p className="farm-help">No pudimos recuperar la lista de archivos. <button className="secondary" onClick={() => setRefresh(value => value + 1)}>Reintentar</button></p> : !datasets.length ? <div className="farm-empty"><strong>Todavía no has cargado datasets.</strong><p>Descarga la plantilla, agrega tus mediciones reales y carga el archivo.</p></div> : <div className="dataset-list">{datasets.map(item => <article key={item.dataset_id}><div><h3>{item.original_filename}</h3><p>{item.row_count.toLocaleString('es-CO')} observaciones · {item.first_date} → {item.last_date}</p><p>{item.variables.map(variable => catalog.variables.find(option => option.variable === variable)?.label || variable).join(' · ')}</p><span className="tag">Formato revisado · mediciones sin verificar</span><details><summary>Procedencia del archivo</summary><code>SHA-256: {item.sha256}</code><p>Fechas locales de Colombia · conservado con su archivo original.</p></details></div><div className="dataset-actions"><a className="secondary" href={`/backend/farms/${farmId}/datasets/${item.dataset_id}/download`}>Descargar</a><button className="text-danger" disabled={busy} onClick={() => void remove(item)}>Eliminar</button></div></article>)}</div>}
    </section>
    <section className="farm-card model-preparation"><span className="eyebrow">CONTEXTO PARA EL ANÁLISIS</span><h2>Una base propia para los modelos</h2><p className="farm-help">La ficha y tus observaciones se preparan como un conjunto identificable. Antes de utilizarlas, debemos alinear fechas y unidades con NASA y validar el modelo para tu zona.</p>
      <div className="farm-context-stats"><div><strong>{context?.observation_count ?? '—'}</strong><span>Observaciones locales</span></div><div><strong>{context?.dataset_ids.length ?? '—'}</strong><span>Datasets con observaciones</span></div><div><strong>{context?.conflict_count ?? '—'}</strong><span>Solapamientos por revisar</span></div></div>
      <p className="farm-help">Los modelos todavía no están conectados a estos datos. Subir un archivo no garantiza una mejora de precisión y no genera predicciones nuevas.</p>
      {context && <details className="dataset-guide"><summary>Ver trazabilidad y validaciones pendientes</summary><code>Huella de entradas: {context.snapshot_id}</code><ul>{context.limitations.map(message => <li key={message}>{message}</li>)}</ul><p>Datos NASA de esta finca: pendientes de ingesta.</p></details>}
    </section>
  </>;
}
