'use client';

import { useEffect, useId, useRef, useState } from 'react';
import type { Map as LeafletMap, Rectangle } from 'leaflet';
import { areaGeoJSON, convertSquareSize, rectangleArea, squareArea, squareSideMetres, type AreaSelection, type AreaSizeUnit, type Coordinate } from './area';

type Props = Coordinate & { name: string; technical: boolean; onSelect?: (area: AreaSelection) => void; onCenterChange?: (center: Coordinate) => void; initialBoundary?: Pick<AreaSelection, 'west' | 'south' | 'east' | 'north'> | null; clearSelectionVersion?: number; };
export default function AreaMap({ latitude, longitude, name, technical, onSelect, onCenterChange, initialBoundary, clearSelectionVersion = 0 }: Props) {
  const initialBoundaryRef = useRef(initialBoundary);
  const onSelectRef = useRef(onSelect);
  const onCenterChangeRef = useRef(onCenterChange);
  useEffect(() => { onSelectRef.current = onSelect; initialBoundaryRef.current = initialBoundary; }, [onSelect, initialBoundary]);
  useEffect(() => { onCenterChangeRef.current = onCenterChange; }, [onCenterChange]);
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const rectangle = useRef<Rectangle | null>(null);
  const sizeRef = useRef<{ value: string; unit: AreaSizeUnit }>({ value: '1000', unit: 'm2' });
  const areaRef = useRef<AreaSelection | null>(null);
  const selectRef = useRef<(area: AreaSelection) => void>(() => {});
  const [size, setSize] = useState('1000');
  const [unit, setUnit] = useState<AreaSizeUnit>('m2');
  const inputId = useId();
  const [area, setArea] = useState<AreaSelection | null>(null);
  const [message, setMessage] = useState('Elige un tamaño y haz clic en el lugar que quieras delimitar.');
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let current: LeafletMap | null = null;
    setArea(null); areaRef.current = null; setReady(false); setError('');
    setMessage('Escribe un tamaño y haz clic en el mapa para colocar el cuadrado.');
    import('leaflet').then(L => {
      if (cancelled || !container.current) return;
      current = L.map(container.current, { scrollWheelZoom: false, minZoom: 3, maxZoom: 19 }).setView([latitude, longitude], 14);
      map.current = current;
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(current);
      L.control.scale({ imperial: false }).addTo(current);
      if (onSelectRef.current) L.circleMarker([latitude, longitude], { radius: 5, color: '#142a1d', fillColor: '#ffffff', fillOpacity: 1 }).addTo(current).bindTooltip('Centro inicial del mapa; delimita la ubicación real de tu finca');
      selectRef.current = selected => {
        if (!current) return;
        const firstSelection = areaRef.current === null;
        rectangle.current?.remove();
        rectangle.current = L.rectangle([[selected.south, selected.west], [selected.north, selected.east]], { color: '#8ad7a4', weight: 2, fillOpacity: .2 }).addTo(current);
        setArea(selected); areaRef.current = selected; setError(''); onSelectRef.current?.(selected);
        if (firstSelection) current.fitBounds(rectangle.current.getBounds(), { maxZoom: 19, padding: [35, 35], animate: false });
        setMessage('Área delimitada. Puedes seleccionar otra ubicación o descargar su geometría.');
      };
      const saved = initialBoundaryRef.current;
      if (saved) {
        try {
          const selected = rectangleArea({ latitude: saved.south, longitude: saved.west }, { latitude: saved.north, longitude: saved.east });
          rectangle.current = L.rectangle([[saved.south, saved.west], [saved.north, saved.east]], { color: '#8ad7a4', weight: 2, fillOpacity: .2 }).addTo(current);
          setArea(selected); areaRef.current = selected;
          if (selected.areaM2 >= 1 && selected.areaM2 <= 100000000) {
            const savedValue = String(Number(convertSquareSize(selected.areaM2, 'm2', sizeRef.current.unit).toPrecision(12)));
            sizeRef.current = { value: savedValue, unit: sizeRef.current.unit }; setSize(savedValue);
          }
          current.fitBounds(rectangle.current.getBounds(), { maxZoom: 19, padding: [35, 35], animate: false });
          setMessage('Área guardada de la finca. Puedes delimitar otra para reemplazarla.');
        } catch { setError('El área guardada supera los límites de este selector; puedes conservarla o cambiar sus coordenadas.'); }
      }
      current.on('click', event => {
        const point = { latitude: event.latlng.lat, longitude: event.latlng.lng };
        try {
          const size = sizeRef.current;
          selectRef.current(squareArea(point, squareSideMetres(Number(size.value), size.unit)));
        } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo delimitar el área.'); }
      });
      const reportCenter = () => {
        const center = current?.getCenter().wrap();
        if (center) onCenterChangeRef.current?.({ latitude: center.lat, longitude: center.lng });
      };
      current.on('moveend', reportCenter);
      reportCenter();
      setReady(true);
    }).catch(() => { if (!cancelled) setError('No se pudo cargar el mapa interactivo. Recarga la página para reintentar.'); });
    return () => { cancelled = true; current?.remove(); map.current = null; rectangle.current = null; selectRef.current = () => {}; };
  }, [latitude, longitude]);

  useEffect(() => {
    if (!clearSelectionVersion) return;
    rectangle.current?.remove(); rectangle.current = null; areaRef.current = null; setArea(null);
    setMessage('Coordenadas editadas manualmente. Puedes centrar el mapa o delimitar otra área.');
  }, [clearSelectionVersion]);

  function changeSize(value: string, nextUnit: AreaSizeUnit) {
    sizeRef.current = { value, unit: nextUnit }; setSize(value); setUnit(nextUnit);
    try {
      const sideM = squareSideMetres(Number(value), nextUnit);
      setError('');
      const selected = areaRef.current;
      if (selected) selectRef.current(squareArea({ latitude: (selected.north + selected.south) / 2, longitude: (selected.east + selected.west) / 2 }, sideM));
      else setMessage('Haz clic en el mapa para colocar el cuadrado del tamaño indicado.');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Tamaño inválido.'); }
  }

  function changeUnit(nextUnit: AreaSizeUnit) {
    try {
      const converted = convertSquareSize(Number(size), unit, nextUnit);
      // Cambiar de unidad conserva el tamaño y la ubicación del área actual.
      const value = String(Number(converted.toPrecision(12)));
      sizeRef.current = { value, unit: nextUnit }; setSize(value); setUnit(nextUnit); setError('');
    } catch { changeSize(size, nextUnit); }
  }

  function download() {
    if (!area) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(areaGeoJSON(area), null, 2)], { type: 'application/geo+json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'area-seleccionada.geojson'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  let requestedSide: number | null = null;
  try { requestedSide = squareSideMetres(Number(size), unit); } catch { /* El campo informa el tamaño inválido. */ }
  const format = (value: number, digits = 2) => value.toLocaleString('es-CO', { maximumFractionDigits: digits });
  return <div className="area-map">
    <div className="area-map-tools"><label htmlFor={`${inputId}-size`}>Superficie del cuadrado<input id={`${inputId}-size`} type="number" step="any" min={unit === 'ha' ? .0001 : unit === 'km2' ? .000001 : 1} max={unit === 'ha' ? 10000 : unit === 'km2' ? 100 : 100000000} value={size} disabled={!ready} aria-describedby={`${inputId}-help`} onChange={event => changeSize(event.target.value, unit)} /></label>
      <label htmlFor={`${inputId}-unit`}>Unidad<select id={`${inputId}-unit`} value={unit} disabled={!ready} onChange={event => changeUnit(event.target.value as AreaSizeUnit)}><option value="m2">Metros cuadrados (m²)</option><option value="km2">Kilómetros cuadrados (km²)</option><option value="ha">Hectáreas (ha)</option></select></label>
      <button type="button" disabled={!ready || requestedSide === null} onClick={() => {
      const center = map.current?.getCenter(); if (!center) return;
      try { selectRef.current(squareArea({ latitude: center.lat, longitude: center.lng }, squareSideMetres(Number(size), unit))); }
      catch (reason) { setError(reason instanceof Error ? reason.message : 'Área inválida.'); }
    }}>Marcar en el centro</button></div>
    <p id={`${inputId}-help`} className="map-size-help">{requestedSide !== null ? `Equivale a un cuadrado de ${format(requestedSide)} × ${format(requestedSide)} m.` : 'Indica una superficie entre 1 m² y 100 km².'}</p>
    <div className="map-frame"><div ref={container} className="interactive-map" role="region" aria-label={onCenterChange ? 'Mapa para explorar y delimitar un área' : `Mapa para delimitar un área cerca de ${name}`} />{onCenterChange && <span className="map-center-marker" aria-hidden="true" />}</div>
    <p className="map-instructions" role="status">{message}</p>
    {error && <p className="map-selection-error" role="alert">{error}</p>}
    {area && <div className="area-selection"><strong>Área seleccionada: ≈ {format(area.widthM)} × {format(area.heightM)} m</strong><span>Superficie aproximada: {format(area.areaM2)} m² ({format(area.areaM2 / 10000, 6)} ha)</span>
      {technical && <code>BBOX: [{area.west.toFixed(7)}, {area.south.toFixed(7)}, {area.east.toFixed(7)}, {area.north.toFixed(7)}]</code>}
      {onSelect && <p>Esta área se incluirá en la ficha al guardar la finca. Aún no se han consultado ni recortado datos NASA para ella.</p>}
      <div className="area-selection-actions"><button type="button" onClick={() => {
        if (map.current && rectangle.current) map.current.fitBounds(rectangle.current.getBounds(), { maxZoom: 19, padding: [35, 35], animate: false });
      }}>Ver área completa</button><button type="button" onClick={download}>Descargar área GeoJSON</button></div>
    </div>}
  </div>;
}
