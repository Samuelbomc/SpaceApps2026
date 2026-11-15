'use client';
import { useState } from 'react';
import AreaMap from '../map/area-map';
import { api, type Farm, type FarmCatalog, type FarmWrite } from '../../lib/api';

export default function FarmForm({ farm, catalog, csrf, onSaved, onCancel }: { farm?: Farm; catalog: FarmCatalog; csrf: string; onSaved: (farm: Farm) => void; onCancel: () => void }) {
  const [draft, setDraft] = useState({ name: farm?.name || '', municipality: farm?.municipality || '', latitude: farm ? String(farm.latitude) : '', longitude: farm ? String(farm.longitude) : '', area: farm ? String(farm.area_ha) : '', altitude: farm?.altitude_m == null ? '' : String(farm.altitude_m), ph: farm?.soil_ph == null ? '' : String(farm.soil_ph), crops: farm?.current_crops?.join(', ') || '', soil: farm?.soil_texture || 'unknown', irrigation: farm?.irrigation || 'unknown', notes: farm?.notes || '' });
  const [boundary, setBoundary] = useState<FarmWrite['boundary']>(farm?.boundary || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [clearVersion, setClearVersion] = useState(0);
  const [mapAnchor, setMapAnchor] = useState({ latitude: farm?.latitude ?? 6.2442, longitude: farm?.longitude ?? -75.5812 });
  function field(key: keyof typeof draft, value: string) { setDraft(current => ({ ...current, [key]: value })); }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const body: FarmWrite = { name: draft.name, municipality: draft.municipality, latitude: Number(draft.latitude), longitude: Number(draft.longitude), area_ha: Number(draft.area), altitude_m: draft.altitude ? Number(draft.altitude) : null, soil_ph: draft.ph ? Number(draft.ph) : null, soil_texture: draft.soil as FarmWrite['soil_texture'], irrigation: draft.irrigation as FarmWrite['irrigation'], current_crops: draft.crops.split(',').map(value => value.trim()).filter(Boolean), notes: draft.notes, boundary };
    try { onSaved(await api<Farm>(farm ? `farms/${farm.farm_id}?revision=${farm.revision}` : 'farms', { method: farm ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify(body) })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo guardar la finca.'); }
    finally { setBusy(false); }
  }
  return <section className="farm-card"><div className="farm-card-heading"><div><span className="eyebrow">FICHA DE TU FINCA</span><h2>{farm ? 'Editar información' : 'Registra tu primera ubicación'}</h2></div><button className="secondary" type="button" onClick={onCancel} disabled={busy}>Cancelar</button></div>
    <p className="farm-help">Completa lo que conoces. Puedes dejar sin especificar los datos de suelo o riego que todavía no tengas.</p>
    <form onSubmit={event => void submit(event)}><fieldset disabled={busy} className="farm-fields">
      <label>Nombre de la finca<input value={draft.name} onChange={event => field('name', event.target.value)} required maxLength={120} placeholder="El nombre de tu finca" /></label>
      <label>Municipio<input value={draft.municipality} onChange={event => field('municipality', event.target.value)} maxLength={120} placeholder="Municipio o vereda" /></label>
      <div className="farm-map-field" inert={busy}><h3>¿Dónde está tu finca?</h3><p className="farm-help">Mueve el mapa y delimita tu ubicación real para completar sus coordenadas y una superficie aproximada. También puedes escribirlas abajo.</p><AreaMap {...mapAnchor} name={farm?.name || 'la ubicación inicial'} technical={false} initialBoundary={boundary} clearSelectionVersion={clearVersion} onSelect={area => {
        setBoundary({ west: area.west, south: area.south, east: area.east, north: area.north });
        setDraft(current => ({ ...current, latitude: ((area.north + area.south) / 2).toFixed(7), longitude: ((area.west + area.east) / 2).toFixed(7), area: (area.areaM2 / 10000).toFixed(6) }));
      }} />{boundary && <p className="farm-help">Área delimitada guardada en la ficha. Si cambias las coordenadas manualmente se reemplazará por un punto.</p>}</div>
      <label>Latitud<input type="number" step="any" min={-80} max={80} value={draft.latitude} onChange={event => { field('latitude', event.target.value); setBoundary(null); setClearVersion(value => value + 1); }} required placeholder="Ej. 6.2" /></label>
      <label>Longitud<input type="number" step="any" min={-180} max={180} value={draft.longitude} onChange={event => { field('longitude', event.target.value); setBoundary(null); setClearVersion(value => value + 1); }} required placeholder="Ej. -75.4" /></label>
      <div className="full-width"><button className="secondary" type="button" onClick={() => {
        const latitude = Number(draft.latitude), longitude = Number(draft.longitude);
        if (!draft.latitude || !draft.longitude || !Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude)>80 || Math.abs(longitude)>180) { setError('Escribe coordenadas válidas antes de centrar el mapa.'); return; }
        setError(''); setMapAnchor({ latitude, longitude });
      }}>Centrar mapa con estas coordenadas</button></div>
      <label>Superficie en hectáreas<input type="number" step="any" min={0.0001} max={1000000} value={draft.area} onChange={event => field('area', event.target.value)} required /><small>1 hectárea = 10.000 m². Puedes corregir la estimación del mapa.</small></label>
      <label>Altitud en metros · opcional<input type="number" step="any" min={-500} max={9000} value={draft.altitude} onChange={event => field('altitude', event.target.value)} /></label>
      <label>Tipo de suelo<select value={draft.soil} onChange={event => field('soil', event.target.value)}>{catalog.soil_textures.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label>pH del suelo · opcional<input type="number" step="any" min={0} max={14} value={draft.ph} onChange={event => field('ph', event.target.value)} /><small>Indícalo si cuentas con una medición.</small></label>
      <label>Tipo de riego<select value={draft.irrigation} onChange={event => field('irrigation', event.target.value)}>{catalog.irrigation_types.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label>Cultivos actuales<input value={draft.crops} onChange={event => field('crops', event.target.value)} maxLength={1600} placeholder="Separa los nombres con comas" /></label>
      <label className="full-width">Notas · opcional<textarea rows={3} value={draft.notes} onChange={event => field('notes', event.target.value)} maxLength={2000} placeholder="Información que quieras conservar sobre tu finca" /></label>
    </fieldset>{error && <div role="alert" className="form-error">{error}</div>}<button className="primary" disabled={busy}>{busy ? 'Guardando…' : 'Guardar finca'} <span>↗</span></button></form>
  </section>;
}
