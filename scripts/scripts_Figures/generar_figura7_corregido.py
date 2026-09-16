import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import matplotlib as mpl

# ==========================================
# CONFIGURACIÓN ESTRICTA PARA EL JOURNAL (IJSAMI)
# ==========================================
mpl.rcParams['font.family'] = 'serif'
# Lista de alternativas en orden de preferencia: si 'Times New Roman' (fuente
# propietaria de Microsoft) no está instalada en el sistema donde se ejecute
# este script (p. ej. Linux/Overleaf), matplotlib usará la primera disponible
# de esta lista en vez de caer silenciosamente en una fuente sans-serif.
mpl.rcParams['font.serif'] = ['Times New Roman', 'Nimbus Roman No9 L',
                               'Liberation Serif', 'Nimbus Roman', 'Times']
mpl.rcParams['mathtext.fontset'] = 'stix'   # Fuente matemática visualmente compatible con Times
mpl.rcParams['axes.labelsize'] = 22      # aumentado de 20 a 22
mpl.rcParams['xtick.labelsize'] = 18     # aumentado de 16 a 18
mpl.rcParams['ytick.labelsize'] = 18     # aumentado de 16 a 18
mpl.rcParams['legend.fontsize'] = 16     # aumentado de 14 a 16

# ==========================================
# CONFIGURACIÓN DE ARCHIVOS
# ==========================================
ARCHIVO_WIFI = 'davis_wifi_logger.csv'

# Tus 6 días continuos del SDR
ARCHIVOS_SDR = [
    'historial_davis_2026-08-29.csv',
    'historial_davis_2026-08-30.csv',
    'historial_davis_2026-08-31.csv',
    'historial_davis_2026-09-01.csv',
    'historial_davis_2026-09-02.csv',
    'historial_davis_2026-09-03.csv'
]

# ==========================================
# FUNCIÓN: DETECCIÓN AUTOMÁTICA DE DESFASE (CROSS-CORRELATION)
# ==========================================
def encontrar_desfase_minutos(t_ref, y_ref, t_test, y_test,
                               freq='1min', max_lag_min=180, paso_min=1):
    """
    Encuentra el desfase (en minutos) que hay que SUMAR a t_test
    para que la señal y_test quede alineada con y_ref.

    Regulariza ambas series a una rejilla temporal común y prueba
    desplazamientos discretos, quedándose con el de menor error
    cuadrático medio.
    """
    s_ref = pd.Series(np.asarray(y_ref, dtype=float), index=pd.DatetimeIndex(t_ref)).sort_index()
    s_test = pd.Series(np.asarray(y_test, dtype=float), index=pd.DatetimeIndex(t_test)).sort_index()

    inicio = max(s_ref.index.min(), s_test.index.min())
    fin = min(s_ref.index.max(), s_test.index.max())
    rejilla = pd.date_range(inicio, fin, freq=freq)

    s_ref_r = s_ref.reindex(s_ref.index.union(rejilla)).interpolate(method='time').reindex(rejilla)
    s_test_r = s_test.reindex(s_test.index.union(rejilla)).interpolate(method='time').reindex(rejilla)

    mejor_lag, mejor_error = 0, np.inf
    for lag in range(-max_lag_min, max_lag_min + 1, paso_min):
        despl = s_test_r.shift(lag)  # shift en pasos de 'freq' (1 min)
        comb = pd.concat([s_ref_r, despl], axis=1).dropna()
        if len(comb) < 30:
            continue
        error = np.mean((comb.iloc[:, 0] - comb.iloc[:, 1]) ** 2)
        if error < mejor_error:
            mejor_error, mejor_lag = error, lag

    return mejor_lag


try:
    print("Cargando y procesando datos del WiFiLogger...")
    df_wifi = pd.read_csv(ARCHIVO_WIFI)

    # Formato Americano del WiFi Logger (Mes/Día/Año)
    df_wifi['Datetime'] = pd.to_datetime(df_wifi['Date'] + ' ' + df_wifi['Time'], format='mixed', dayfirst=False)

    # Filtrar fechas
    fecha_inicio = pd.to_datetime('2026-08-29 00:00:00')
    fecha_fin = pd.to_datetime('2026-09-03 23:59:59')
    df_wifi = df_wifi[(df_wifi['Datetime'] >= fecha_inicio) & (df_wifi['Datetime'] <= fecha_fin)].copy()

    # Forzar numéricos y convertir Fahrenheit a Celsius
    df_wifi['Temp Out'] = pd.to_numeric(df_wifi['Temp Out'], errors='coerce')
    df_wifi['Out Hum'] = pd.to_numeric(df_wifi['Out Hum'], errors='coerce')

    df_wifi['Temp_C_Wifi'] = (df_wifi['Temp Out'] - 32) * 5.0 / 9.0
    df_wifi['Hum_Wifi'] = df_wifi['Out Hum']
    df_wifi = df_wifi.dropna(subset=['Temp_C_Wifi', 'Hum_Wifi']).sort_values('Datetime')

    print("Cargando y procesando datos del SDR...")
    lista_dfs = []
    for archivo in ARCHIVOS_SDR:
        if os.path.exists(archivo):
            lista_dfs.append(pd.read_csv(archivo))

    df_sdr = pd.concat(lista_dfs, ignore_index=True)
    df_sdr['Fecha_Hora'] = pd.to_datetime(df_sdr['Fecha_Hora'], format='mixed')
    df_sdr['Temp_C'] = pd.to_numeric(df_sdr['Temp_C'], errors='coerce')
    df_sdr['Humedad_%'] = pd.to_numeric(df_sdr['Humedad_%'], errors='coerce')

    df_sdr = df_sdr.dropna(subset=['Temp_C', 'Humedad_%']).sort_values('Fecha_Hora')

    # ==========================================
    # DETECCIÓN Y CORRECCIÓN DEL DESFASE TEMPORAL
    # ==========================================
    print("Detectando desfase temporal entre SDR y WiFiLogger (usando Temperatura)...")
    desfase_min = encontrar_desfase_minutos(
        df_wifi['Datetime'], df_wifi['Temp_C_Wifi'],
        df_sdr['Fecha_Hora'], df_sdr['Temp_C']
    )
    print(f"-> Desfase detectado: {desfase_min} minutos (se suma al timestamp del SDR)")

    df_sdr['Fecha_Hora'] = df_sdr['Fecha_Hora'] + pd.Timedelta(minutes=desfase_min)

    # EMPAREJAMIENTO DE DATOS (Matching) -- ya con timestamps corregidos
    df_eval = pd.merge_asof(
        df_wifi[['Datetime', 'Temp_C_Wifi', 'Hum_Wifi']],
        df_sdr[['Fecha_Hora', 'Temp_C', 'Humedad_%']],
        left_on='Datetime',
        right_on='Fecha_Hora',
        direction='nearest',
        tolerance=pd.Timedelta('5 minutes')
    )
    df_eval = df_eval.dropna().copy()

    # CÁLCULOS ESTADÍSTICOS (MAE)
    error_temp = np.mean(np.abs(df_eval['Temp_C_Wifi'] - df_eval['Temp_C']))
    error_hum = np.mean(np.abs(df_eval['Hum_Wifi'] - df_eval['Humedad_%']))
    print(f"-> MAE Temperatura (post-corrección): {error_temp:.3f} °C")
    print(f"-> MAE Humedad (post-corrección): {error_hum:.3f} %")

    # ==========================================
    # DIBUJO DE LA GRÁFICA COMPARATIVA JOURNAL-READY
    # ==========================================
    print("Generando PDF para IJSAMI...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # --- PANEL 1: TEMPERATURA ---
    ax1.plot(df_eval['Datetime'], df_eval['Temp_C_Wifi'],
             label='Commercial WiFiLogger', color='dimgray', linestyle='--', linewidth=2, marker='o', markersize=4)
    ax1.plot(df_eval['Datetime'], df_eval['Temp_C'],
             label='SDR Edge Architecture (Proposed)', color='darkred', linewidth=2.5, alpha=0.8)

    ax1.set_ylabel('Temperature (°C)')
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper right')

    # --- PANEL 2: HUMEDAD ---
    ax2.plot(df_eval['Datetime'], df_eval['Hum_Wifi'],
             label='Commercial WiFiLogger', color='dimgray', linestyle='--', linewidth=2, marker='o', markersize=4)
    ax2.plot(df_eval['Datetime'], df_eval['Humedad_%'],
             label='SDR Edge Architecture (Proposed)', color='darkblue', linewidth=2.5, alpha=0.8)

    ax2.set_ylabel('Relative Humidity (%)')
    ax2.set_xlabel('Date and Time')
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='lower right')

    # Formato del Eje X: Mes y Día
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    fig.autofmt_xdate(rotation=0, ha='center')

    plt.tight_layout()

    # GUARDAR DIRECTO COMO PDF VECTORIAL
    plt.savefig('Supplementary_S1_Validation_Temp_Humidity_MultiDay.pdf', format='pdf', bbox_inches='tight')  # No incluida en el manuscrito final
    print("¡Archivo 'Supplementary_S1_Validation_Temp_Humidity_MultiDay.pdf' generado exitosamente!")

except Exception as e:
    print(f"Error general en el proceso: {e}")
