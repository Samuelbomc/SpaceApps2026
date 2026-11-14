import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IntegrationStatus } from '../../../../core/catalog/data-nature';
import { StatusBadge } from '../../../../shared/ui/status-badge/status-badge';

interface ModuleEntry {
  id: string;
  label: string;
  title: string;
  audience: string;
  summary: string;
  capabilities: string[];
  path: string;
  cta: string;
  status: IntegrationStatus;
  accent: 'water' | 'forest';
}

/** The two product modules as entry points. */
@Component({
  selector: 'app-home-modules',
  imports: [RouterLink, StatusBadge],
  templateUrl: './modules.html',
  styleUrl: './modules.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeModules {
  protected readonly modules: ModuleEntry[] = [
    {
      id: 'data',
      label: 'Módulo A · Público',
      title: 'Portal de datos agroambientales',
      audience: 'Investigación, estudiantes, instituciones, asistencia técnica y público general.',
      summary:
        'Explora, compara y consulta información ambiental y agrícola del territorio, con su procedencia y limitaciones siempre visibles.',
      capabilities: [
        'Exploración geográfica por municipio',
        'Variables ambientales e históricos',
        'Contexto agrícola de fuentes oficiales',
        'Metadatos, procedencia y descargas',
      ],
      path: '/datos',
      cta: 'Explorar el portal',
      status: 'in-development',
      accent: 'water',
    },
    {
      id: 'farm',
      label: 'Módulo B · Agricultores',
      title: 'Espacio del agricultor',
      audience: 'Agricultores, agricultoras y extensionistas que acompañan sus decisiones.',
      summary:
        'Registra tu finca, tu historial y tus prioridades para comparar estrategias de rotación con beneficios, riesgos y evidencia explicados.',
      capabilities: [
        'Perfil de finca, suelo y agua',
        'Historial de cultivos',
        'Prioridades y restricciones',
        'Comparación de tres o más rotaciones',
      ],
      path: '/agricultor',
      cta: 'Ir al espacio del agricultor',
      status: 'in-development',
      accent: 'forest',
    },
  ];
}
