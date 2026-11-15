"""
Extrae los rangos de ECOCROP (hoja 'ECOCROP' del Excel de cultivos rotables)
a datos/ecocrop_cultivos.csv, que es lo que lee motor_rotacion.py.

Uso:  python actualizar_ecocrop.py
Correrlo de nuevo cada vez que se cambie la hoja ECOCROP del Excel.
"""

from pathlib import Path

import pandas as pd

DATOS = Path(__file__).parent / "datos"
EXCEL = DATOS / "Cultivos_rotables_mas_sembrados_y_aptos_Antioquia.xlsx"

e = pd.read_excel(EXCEL, sheet_name="ECOCROP")
e = e[e["Codigo_ECOCROP"].notna()]  # quita las filas de notas
cols = {
    "Especie_ECOCROP": "ESPECIE_ECOCROP",
    "Temp_Optima_Min_(°C)": "T_OPT_MIN",
    "Temp_Optima_Max_(°C)": "T_OPT_MAX",
    "Temp_Absoluta_Min_(°C)": "T_ABS_MIN",
    "Temp_Absoluta_Max_(°C)": "T_ABS_MAX",
    "Precipitacion_Optima_Min_(mm/año)": "P_OPT_MIN",
    "Precipitacion_Optima_Max_(mm/año)": "P_OPT_MAX",
    "Precipitacion_Absoluta_Min_(mm/año)": "P_ABS_MIN",
    "Precipitacion_Absoluta_Max_(mm/año)": "P_ABS_MAX",
    "Altitud_Absoluta_Max_(msnm)": "ALT_MAX",
    "Ciclo_Cultivo_Min_(dias)": "CICLO_MIN_DIAS",
    "Ciclo_Cultivo_Max_(dias)": "CICLO_MAX_DIAS",
    "Codigo_ECOCROP": "CODIGO_ECOCROP",
}
out = e[list(cols)].rename(columns=cols).drop_duplicates("ESPECIE_ECOCROP")
out["ALT_MAX"] = pd.to_numeric(out["ALT_MAX"], errors="coerce")
out.to_csv(DATOS / "ecocrop_cultivos.csv", index=False)
print(f"{len(out)} especies guardadas en datos/ecocrop_cultivos.csv")
print(
    out[
        [
            "ESPECIE_ECOCROP",
            "T_OPT_MIN",
            "T_OPT_MAX",
            "T_ABS_MIN",
            "T_ABS_MAX",
            "P_OPT_MIN",
            "P_OPT_MAX",
        ]
    ].to_string(index=False)
)
