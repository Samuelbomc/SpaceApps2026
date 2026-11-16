import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-technical-reference',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="section" aria-labelledby="reference-title">
      <div class="container">
        <header class="reference-head">
          <p class="eyebrow">Paper · AgroGeo</p>
          <h1 id="reference-title">Referencia técnica</h1>
          <p class="intro">
            Consulta el documento del proyecto sobre la arquitectura, las fuentes de observación
            terrestre, los modelos y la planificación de rotaciones de cultivos en Antioquia.
          </p>
        </header>
        <article class="card paper" aria-labelledby="paper-title">
          <div>
            <h2 id="paper-title" lang="en">
              Field Shift: An Earth-Observation-Informed Decision Support System for Crop Rotation
              Planning in Antioquia, Colombia
            </h2>
            <p class="metadata">PDF · 15 páginas · Inglés</p>
          </div>
          <div class="paper-actions">
            <a
              class="btn btn--primary"
              href="/documents/paper.pdf"
              target="_blank"
              rel="noopener noreferrer"
              >Abrir paper <span class="sr-only">en una pestaña nueva</span></a
            >
            <a class="btn btn--secondary" href="/documents/paper.pdf" download="AgroGeo-paper.pdf">
              Descargar PDF
            </a>
          </div>
        </article>
        <iframe
          class="paper-viewer"
          src="/documents/paper.pdf"
          title="Visor del paper técnico de Field Shift"
          loading="lazy"
        ></iframe>
        <p class="viewer-help">
          Si tu navegador no muestra el documento, utiliza «Abrir paper» o «Descargar PDF».
        </p>
      </div>
    </section>
  `,
  styles: `
    .reference-head {
      max-width: 52rem;
      margin-bottom: var(--sp-6);
    }
    .intro {
      margin-top: var(--sp-3);
      color: var(--c-ink-muted);
    }
    .paper {
      display: grid;
      gap: var(--sp-5);
      margin-bottom: var(--sp-5);
    }
    .paper h2 {
      font-size: var(--fs-lg);
      line-height: 1.5;
      max-width: 60rem;
    }
    .metadata,
    .viewer-help {
      margin-top: var(--sp-3);
      color: var(--c-ink-muted);
    }
    .paper-actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--sp-3);
    }
    .paper-viewer {
      display: block;
      width: 100%;
      height: 78vh;
      min-height: 28rem;
      border: 1px solid var(--c-border);
      border-radius: var(--radius-sm);
      background: white;
    }
    .viewer-help {
      font-size: var(--fs-sm);
    }
  `,
})
export class TechnicalReference {}
