import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { GeoBoundariesService } from '../../services/geo-boundaries.service';
import { BoundaryMetadata } from '../../models/geo.models';

/**
 * Provenance of everything drawn on the map: official boundaries (with the
 * processing recorded by the pipeline), background imagery and label fonts.
 */
@Component({
  selector: 'app-map-provenance',
  imports: [DatePipe, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styles: `
    details { padding: 0; }
    summary {
      padding: var(--sp-4) var(--sp-5);
      font-weight: 700;
      cursor: pointer;
    }
    .body { display: grid; gap: var(--sp-4); padding: 0 var(--sp-5) var(--sp-5); font-size: var(--fs-sm); }
    h3 { font-size: var(--fs-sm); margin-bottom: var(--sp-2); }
    p { color: var(--c-ink-muted); }
    .cite { font-size: var(--fs-xs); font-style: italic; }
  `,
  template: `
    <details class="card">
      <summary>Fuentes y procesamiento del mapa</summary>
      <div class="body">
        <section>
          <h3>Límites administrativos</h3>
          @if (meta(); as m) {
            <dl class="spec-list">
              <dt>Fuente</dt>
              <dd>{{ m.source.institution }} · {{ m.source.product }}</dd>
              <dt>Consultado</dt>
              <dd>{{ m.retrievedAt | date: 'longDate' }}</dd>
              <dt>Sistema</dt>
              <dd>WGS84 (EPSG:4326)</dd>
              <dt>Generalización</dt>
              <dd>
                ≈ {{ m.processing.simplification.municipalitiesToleranceDeg * 111000 | number: '1.0-0' }} m
                (municipios)
              </dd>
              @if (m.quality.municipalities.areaDeviationPct; as d) {
                <dt>Cambio de área</dt>
                <dd>promedio {{ d.mean }} %, máx. {{ d.max }} %</dd>
              }
            </dl>
            <p>{{ m.source.officialLimitsNote }} Límites simplificados para visualización; no aptos para uso catastral o legal.</p>
            <p class="cite">{{ m.source.citation }}</p>
          } @else if (failed()) {
            <p>No se pudo cargar la ficha de metadatos. Fuente: DANE, Marco Geoestadístico Nacional 2025.</p>
          } @else {
            <p>Cargando metadatos…</p>
          }
        </section>
        <section>
          <h3>Imágenes de fondo</h3>
          <p>
            Vista global: NASA Blue Marble (relieve sombreado y batimetría) servida por NASA GIBS,
            composición estática (≈ 500 m). Al acercarse a municipios: Sentinel-2 cloudless 2025 de
            EOX (Copernicus, 10 m por píxel; licencia CC BY-NC-SA 4.0, uso no comercial). Ambas son
            solo contexto visual: no son datos analíticos ni representan condiciones actuales.
          </p>
        </section>
        <section>
          <h3>Tipografía de etiquetas</h3>
          <p>Servidor público de fuentes de OpenFreeMap (sin clave de acceso).</p>
        </section>
      </div>
    </details>
  `,
})
export class MapProvenance {
  protected readonly meta = signal<BoundaryMetadata | null>(null);
  protected readonly failed = signal(false);

  constructor() {
    inject(GeoBoundariesService)
      .metadata()
      .then((m) => this.meta.set(m))
      .catch(() => this.failed.set(true));
  }
}
