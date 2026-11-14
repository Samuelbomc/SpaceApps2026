import { ChangeDetectionStrategy, Component } from '@angular/core';

/**
 * Explains how NASA Earth observations feed the analysis (observe → process →
 * interpret → decide) and what these data are NOT, to prevent misinterpretation.
 */
@Component({
  selector: 'app-home-earth-observation',
  templateUrl: './earth-observation.html',
  styleUrl: './earth-observation.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeEarthObservation {
  protected readonly steps = [
    {
      verb: 'Observar',
      title: 'Satélites de la NASA',
      text: 'Precipitación (GPM IMERG), humedad superficial del suelo (SMAP), vegetación (HLS), temperatura de superficie (ECOSTRESS), relieve (SRTM) y variables agroclimáticas (NASA POWER).',
    },
    {
      verb: 'Procesar',
      title: 'Flujo reproducible',
      text: 'Cada fuente se descarga, valida y armoniza registrando unidades, fechas, resolución y control de calidad. Remuestrear no agrega detalle espacial.',
    },
    {
      verb: 'Interpretar',
      title: 'Indicadores agroambientales',
      text: 'Anomalías de lluvia, periodos secos, tendencias de vegetación y pendiente, con definiciones explícitas y su escala de validez.',
    },
    {
      verb: 'Decidir',
      title: 'Con el agricultor',
      text: 'Los indicadores se combinan con el historial y las prioridades de la finca para comparar rotaciones. La decisión final requiere validación local.',
    },
  ] as const;

  protected readonly caveats = [
    {
      is: 'Humedad superficial del suelo (SMAP)',
      isNot: 'la humedad en la zona de raíces',
    },
    { is: 'NDVI (índice de vegetación)', isNot: 'una medida de la salud del suelo ni del rendimiento' },
    { is: 'Temperatura de superficie terrestre', isNot: 'la temperatura del aire' },
    { is: 'Datos de NASA POWER', isNot: 'observaciones meteorológicas de la finca' },
    { is: 'Estadísticas municipales', isNot: 'información de una finca en particular' },
  ] as const;
}
