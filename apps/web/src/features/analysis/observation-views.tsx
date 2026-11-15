'use client';

import { useId, useState } from 'react';
import type { Analysis, ObservationPage } from '../../lib/api';
import { dailySegments, isUsable, latestFor, summarizeObservations, type ObservationSeries } from './observation-summary';

type Rows = ObservationPage['items'];

function date(value: string) { return new Date(`${value}T12:00:00Z`).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }); }
function unit(value: string) { return value === 'C' ? '°C' : value; }

export function SimpleConditions({ rows, loading }: { rows: Rows; loading: boolean }) {
  const cards = [
    { variables: ['T2M'], title: 'Temperatura', explanation: 'Temperatura media del aire durante ese día.' },
    { variables: ['RH2M'], title: 'Humedad del aire', explanation: 'Describe la humedad atmosférica; no la humedad de la tierra.' },
    { variables: ['WS2M', 'WS10M'], title: 'Viento', explanation: 'Velocidad del viento medida a la altura indicada por la fuente.' },
  ];
  return <section className="simple-conditions" aria-labelledby="conditions-title">
    <div className="section-heading"><div><span className="eyebrow">CONTEXTO DE TU ZONA</span><h2 id="conditions-title">Últimas condiciones conocidas</h2></div></div>
    <div className="metrics">{cards.map(card => {
      const row = latestFor(rows, card.variables);
      return <article className="metric" key={card.title}><span className="small-label">{card.title}</span>
        <div className="metric-value">{loading ? '…' : row ? <>{row.value?.toLocaleString('es-CO', { maximumFractionDigits: 1 })}<small>{unit(row.unit)}</small></> : <span className="condition-unavailable">Sin dato disponible</span>}</div>
        <p className="metric-explanation">{card.explanation}</p>
        {row && <span className="muted">Último dato: {date(row.date)}</span>}
      </article>;
    })}</div>
    <p className="observation-note">Datos generales de la zona, con controles básicos y sin contraste local. Estas observaciones no indican por sí solas si conviene sembrar.</p>
  </section>;
}

function SeriesChart({ series }: { series: ObservationSeries }) {
  const titleId = useId();
  const valid = series.rows.filter(isUsable);
  if (!valid.length) return <p className="observation-note">Esta serie no tiene valores que superen los controles básicos.</p>;
  const minimum = Math.min(...valid.map(row => row.value));
  const maximum = Math.max(...valid.map(row => row.value));
  const first = Date.parse(series.rows[0].date), last = Date.parse(series.rows[series.rows.length - 1].date);
  const x = (day: string) => first === last ? 330 : 55 + (Date.parse(day) - first) / (last - first) * 550;
  const y = (value: number) => maximum === minimum ? 100 : 155 - (value - minimum) / (maximum - minimum) * 120;
  return <figure className="series-chart"><figcaption>{series.variable} · {series.source} · {series.unit}</figcaption>
    <svg viewBox="0 0 640 200" role="img" aria-labelledby={titleId}>
      <title id={titleId}>{`Serie de ${series.variable}: ${valid.length} valores con control básico, entre ${series.rows[0].date} y ${series.rows[series.rows.length - 1].date}. Los huecos no se interpolan.`}</title>
      {[35, 95, 155].map(height => <line key={height} x1="55" x2="605" y1={height} y2={height} className="chart-grid" />)}
      <text x="5" y="39">{maximum.toFixed(1)}</text><text x="5" y="159">{minimum.toFixed(1)}</text>
      {dailySegments(series.rows).map((segment, index) => <polyline key={index} points={segment.map(row => `${x(row.date)},${y(row.value)}`).join(' ')} className="chart-line" />)}
      {valid.map((row, index) => <circle key={`${row.date}-${index}`} cx={x(row.date)} cy={y(row.value)} r="3" className="chart-point"><title>{`${row.date}: ${row.value} ${row.unit}`}</title></circle>)}
      <text x="55" y="186">{series.rows[0].date}</text><text x="605" y="186" textAnchor="end">{series.rows[series.rows.length - 1].date}</text>
    </svg>
    <p className="muted">Resolución: {series.resolution}. Sin interpolación: los días sin valores válidos quedan separados.</p>
  </figure>;
}

export function TechnicalObservations({ rows, total, loading }: { rows: Rows; total: number; loading: boolean }) {
  const summary = summarizeObservations(rows);
  const [selected, setSelected] = useState('');
  const [requestedPage, setRequestedPage] = useState(0);
  const page = Math.min(requestedPage, Math.max(0, Math.ceil(rows.length / 100) - 1));
  const series = summary.series.find(item => item.key === selected) || summary.series.find(item => item.rows.some(isUsable)) || summary.series[0];
  return <section id="observations" className="technical-observations" aria-labelledby="information-title">
    <div className="section-heading"><div><span className="eyebrow">EXPLORACIÓN Y CONTROL DE DATOS</span><h2 id="information-title">Histórico, cobertura y calidad</h2></div></div>
    {loading ? <p role="status">Consultando observaciones históricas…</p> : <>
      <div className="quality-summary">
        <article><strong>{rows.length}</strong><span>Registros recibidos</span></article>
        <article><strong>{summary.usable}</strong><span>Con valor y control básico</span></article>
        <article><strong>{summary.missing}</strong><span>Valores ausentes</span></article>
        <article><strong>{summary.days}</strong><span>Días con registros</span></article>
      </div>
      <p className="observation-note">Todo el histórico almacenado de esta ubicación ({total} registros). Cobertura recibida: {summary.firstDate ? `${summary.firstDate} → ${summary.lastDate}` : 'sin registros'}. El recuento de días no certifica cobertura completa por variable o producto.</p>
      {series && <div className="technical-panel"><label className="series-select">Serie temporal<select value={series.key} onChange={event => setSelected(event.target.value)}>{summary.series.map(item => <option key={item.key} value={item.key}>{item.source} · {item.variable} · {item.unit} · {item.resolution}</option>)}</select></label><SeriesChart series={series} />
        <div className="quality-tags">{Object.entries(summary.quality).map(([quality, count]) => <span key={quality}>{quality}: <strong>{count}</strong></span>)}</div>
      </div>}
      {rows.length > 0 ? <details className="raw-observations"><summary>Inspeccionar registros y unidades originales ({rows.length})</summary><div className="data-table"><table><thead><tr><th>Fecha UTC</th><th>Variable</th><th>Fuente</th><th>Valor</th><th>Unidad</th><th>Calidad</th><th>Resolución</th></tr></thead><tbody>{rows.slice(page * 100, page * 100 + 100).map((row, index) => <tr key={`${row.source}-${row.variable}-${row.date}-${index}`}><td>{row.date}</td><td>{row.variable}</td><td>{row.source}</td><td>{row.value ?? 'Sin dato'}</td><td>{row.unit}</td><td>{row.quality}</td><td>{row.resolution}</td></tr>)}</tbody></table></div><div className="table-pagination"><button disabled={page === 0} onClick={() => setRequestedPage(page - 1)}>Anterior</button><span>Registros {page * 100 + 1}–{Math.min(rows.length, page * 100 + 100)} de {rows.length}</span><button disabled={(page + 1) * 100 >= rows.length} onClick={() => setRequestedPage(page + 1)}>Siguiente</button></div></details> : <p className="observation-note">No hay observaciones almacenadas para esta ubicación.</p>}
    </>}
  </section>;
}

export function AnalysisTrace({ analysis }: { analysis: Analysis | null }) {
  return <details className="analysis-trace"><summary>Trazabilidad de modelos y entradas</summary>
    <dl><dt>Estado</dt><dd>{analysis?.status || 'Sin análisis'}</dd><dt>ID del análisis</dt><dd>{analysis?.analysis_id || 'No generado'}</dd><dt>Huella de las entradas</dt><dd>{analysis?.input_snapshot_id || 'No generada'}</dd><dt>Modelo climático</dt><dd>{analysis?.climate?.model_version || 'Sin resultado'}</dd><dt>Modelo de suelo</dt><dd>{analysis?.soil?.model_version || 'Sin resultado'}</dd><dt>Motor agronómico</dt><dd>{analysis?.recommendations?.engine_version || 'Sin resultado'}</dd></dl>
    <p className="observation-note">El contrato actual no incluye métricas de validación ni intervalos de incertidumbre; no se presentan estimaciones de confianza.</p>
  </details>;
}
