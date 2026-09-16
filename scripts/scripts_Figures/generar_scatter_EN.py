import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from scipy import stats

# ==========================================
# STRICT JOURNAL CONFIGURATION (IJSAMI)
# ==========================================
mpl.rcParams['font.family'] = 'serif'
# Fallback list: if 'Times New Roman' (Microsoft-proprietary) is not installed
# on the system running this script (e.g. Linux/Overleaf), matplotlib will use
# the first available font from this list instead of silently falling back to
# a sans-serif font.
mpl.rcParams['font.serif'] = ['Times New Roman', 'Nimbus Roman No9 L',
                               'Liberation Serif', 'Nimbus Roman', 'Times']
mpl.rcParams['mathtext.fontset'] = 'stix'   # Math font visually compatible with Times
mpl.rcParams['axes.labelsize'] = 18      # aumentado de 16 a 18
mpl.rcParams['xtick.labelsize'] = 15     # aumentado de 13 a 15
mpl.rcParams['ytick.labelsize'] = 15     # aumentado de 13 a 15
mpl.rcParams['legend.fontsize'] = 13     # aumentado de 11 a 13

ARCHIVO_WIFI = 'davis_wifi_logger.csv'
ARCHIVOS_SDR = [
    'historial_davis_2026-08-29.csv',
    'historial_davis_2026-08-30.csv',
    'historial_davis_2026-08-31.csv',
    'historial_davis_2026-09-01.csv',
    'historial_davis_2026-09-02.csv',
    'historial_davis_2026-09-03.csv'
]
VENTANA_ARCHIVO_MIN = 30
DESFASE_RELOJ_MIN = 61


def encontrar_desfase_minutos(t_ref, y_ref, t_test, y_test, freq='1min', max_lag_min=180, paso_min=1):
    s_ref = pd.Series(np.asarray(y_ref, dtype=float), index=pd.DatetimeIndex(t_ref)).sort_index()
    s_test = pd.Series(np.asarray(y_test, dtype=float), index=pd.DatetimeIndex(t_test)).sort_index()
    inicio = max(s_ref.index.min(), s_test.index.min())
    fin = min(s_ref.index.max(), s_test.index.max())
    rejilla = pd.date_range(inicio, fin, freq=freq)
    s_ref_r = s_ref.reindex(s_ref.index.union(rejilla)).interpolate(method='time').reindex(rejilla)
    s_test_r = s_test.reindex(s_test.index.union(rejilla)).interpolate(method='time').reindex(rejilla)
    mejor_lag, mejor_error = 0, np.inf
    for lag in range(-max_lag_min, max_lag_min + 1, paso_min):
        despl = s_test_r.shift(lag)
        comb = pd.concat([s_ref_r, despl], axis=1).dropna()
        if len(comb) < 30:
            continue
        error = np.mean((comb.iloc[:, 0] - comb.iloc[:, 1]) ** 2)
        if error < mejor_error:
            mejor_error, mejor_lag = error, lag
    return mejor_lag


def scatter_panel(ax, x, y, title, color):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    r, _ = stats.pearsonr(x, y)
    pendiente, intercepto, r_reg, _, _ = stats.linregress(x, y)
    r2 = r_reg ** 2

    ax.scatter(x, y, s=10, alpha=0.35, color=color, edgecolor='none')

    lim_min, lim_max = min(x.min(), y.min()), max(x.max(), y.max())
    margen = (lim_max - lim_min) * 0.05
    rango = [lim_min - margen, lim_max + margen]
    ax.plot(rango, rango, 'k--', linewidth=1.5, label='1:1 Line')

    x_fit = np.array(rango)
    y_fit = pendiente * x_fit + intercepto
    ax.plot(x_fit, y_fit, color='black', linewidth=1.8, alpha=0.8, label='SDR~Davis regression')

    ax.set_xlim(rango)
    ax.set_ylim(rango)
    etiqueta_corta = title.split(',')[0]
    ax.set_xlabel(f'{etiqueta_corta} — Davis (Commercial)')
    ax.set_ylabel(f'{etiqueta_corta} — SDR')
    ax.grid(True, linestyle=':', alpha=0.5)

    texto = (fr"$r$ = {r:.3f}" + "\n" +
             fr"$R^2$ = {r2:.3f}" + "\n" +
             fr"slope = {pendiente:.3f}" + "\n" +
             fr"intercept = {intercepto:.2f}")
    ax.text(0.05, 0.95, texto, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))
    ax.legend(loc='lower right', fontsize=9)
    ax.set_title(title, fontsize=13)


try:
    # ==========================================
    # LOAD DATA
    # ==========================================
    print("Loading WiFiLogger...")
    df_wifi = pd.read_csv(ARCHIVO_WIFI)
    df_wifi['Datetime'] = pd.to_datetime(df_wifi['Date'] + ' ' + df_wifi['Time'], format='mixed', dayfirst=False)
    fecha_inicio = pd.to_datetime('2026-08-29 00:00:00')
    fecha_fin = pd.to_datetime('2026-09-03 23:59:59')
    df_wifi = df_wifi[(df_wifi['Datetime'] >= fecha_inicio) & (df_wifi['Datetime'] <= fecha_fin)].copy()
    for c in ['Temp Out', 'Out Hum', 'Solar Rad.', 'UV Index']:
        df_wifi[c] = pd.to_numeric(df_wifi[c], errors='coerce')
    df_wifi['Temp_C_Wifi'] = (df_wifi['Temp Out'] - 32) * 5.0 / 9.0
    df_wifi = df_wifi.dropna(subset=['Temp_C_Wifi', 'Out Hum', 'Solar Rad.', 'UV Index']).sort_values('Datetime')

    print("Loading SDR (6 days)...")
    df_sdr = pd.concat([pd.read_csv(a) for a in ARCHIVOS_SDR], ignore_index=True)
    df_sdr['Fecha_Hora'] = pd.to_datetime(df_sdr['Fecha_Hora'], format='mixed')
    for c in ['Temp_C', 'Humedad_%', 'Radiacion_W_m2', 'Indice_UV']:
        df_sdr[c] = pd.to_numeric(df_sdr[c], errors='coerce')
    df_sdr = df_sdr.dropna(subset=['Temp_C', 'Humedad_%', 'Radiacion_W_m2', 'Indice_UV']).sort_values('Fecha_Hora')

    print("Correcting clock offset...")
    desfase_min = encontrar_desfase_minutos(
        df_wifi['Datetime'], df_wifi['Temp_C_Wifi'], df_sdr['Fecha_Hora'], df_sdr['Temp_C']
    )
    print(f"-> Offset applied to SDR: {desfase_min} min")
    df_sdr['Fecha_Hora'] = df_sdr['Fecha_Hora'] + pd.Timedelta(minutes=desfase_min)
    df_sdr_indexed = df_sdr.set_index('Fecha_Hora').sort_index()

    # ==========================================
    # INSTANTANEOUS MATCH
    # ==========================================
    df_eval_inst = pd.merge_asof(
        df_wifi[['Datetime', 'Temp_C_Wifi', 'Out Hum', 'Solar Rad.', 'UV Index']],
        df_sdr[['Fecha_Hora', 'Temp_C', 'Humedad_%', 'Radiacion_W_m2', 'Indice_UV']],
        left_on='Datetime', right_on='Fecha_Hora', direction='nearest', tolerance=pd.Timedelta('5 minutes')
    ).dropna().copy()
    print(f"-> Instantaneous matched pairs: {len(df_eval_inst)}")

    # ==========================================
    # 30-MIN AVERAGED MATCH (Solar Rad and UV Index, Davis archive method)
    # ==========================================
    df_sdr_avg = df_sdr_indexed[['Radiacion_W_m2', 'Indice_UV']].rolling(
        f'{VENTANA_ARCHIVO_MIN}min', min_periods=15
    ).mean().rename(columns={'Radiacion_W_m2': 'Radiacion_avg', 'Indice_UV': 'UV_avg'}).reset_index()

    df_eval_avg = pd.merge_asof(
        df_wifi[['Datetime', 'Solar Rad.', 'UV Index']],
        df_sdr_avg,
        left_on='Datetime', right_on='Fecha_Hora', direction='nearest', tolerance=pd.Timedelta('2 minutes')
    ).dropna().copy()
    print(f"-> 30-min averaged matched pairs: {len(df_eval_avg)}")

    # ==========================================
    # FIGURE 1: SCATTER 1:1 (INSTANTANEOUS, ENGLISH LABELS) — direct translation
    # ==========================================
    print("\nGenerating English scatter 1:1 (instantaneous)...")
    fig1, axes1 = plt.subplots(2, 2, figsize=(12, 11))
    scatter_panel(axes1[0, 0], df_eval_inst['Temp_C_Wifi'], df_eval_inst['Temp_C'], 'Temperature (°C)', 'darkred')
    scatter_panel(axes1[0, 1], df_eval_inst['Out Hum'], df_eval_inst['Humedad_%'], 'Relative Humidity (%)', 'darkblue')
    scatter_panel(axes1[1, 0], df_eval_inst['Solar Rad.'], df_eval_inst['Radiacion_W_m2'], 'Solar Radiation (W/m²)', 'darkorange')
    scatter_panel(axes1[1, 1], df_eval_inst['UV Index'], df_eval_inst['Indice_UV'], 'UV Index (UVI)', 'indigo')
    plt.tight_layout()
    plt.savefig('Supplementary_S3_Scatter_1to1.pdf', format='pdf', bbox_inches='tight')  # No incluida en el manuscrito final
    print("File 'Supplementary_S3_Scatter_1to1.pdf' generated successfully!")

    # ==========================================
    # FIGURE 2: SCATTER 1:1 VARIANT — Solar/UV using the 30-min averaged (Davis) method
    # ==========================================
    print("\nGenerating English scatter 1:1 variant (Solar/UV 30-min averaged)...")
    fig2, axes2 = plt.subplots(2, 2, figsize=(12, 11))
    scatter_panel(axes2[0, 0], df_eval_inst['Temp_C_Wifi'], df_eval_inst['Temp_C'], 'Temperature (°C)', 'darkred')
    scatter_panel(axes2[0, 1], df_eval_inst['Out Hum'], df_eval_inst['Humedad_%'], 'Relative Humidity (%)', 'darkblue')
    scatter_panel(axes2[1, 0], df_eval_avg['Solar Rad.'], df_eval_avg['Radiacion_avg'],
                  'Solar Radiation (W/m², 30-min average)', 'darkorange')
    scatter_panel(axes2[1, 1], df_eval_avg['UV Index'], df_eval_avg['UV_avg'],
                  'UV Index (UVI, 30-min average)', 'indigo')
    plt.tight_layout()
    plt.savefig('Supplementary_S4_Scatter_1to1_Averaged.pdf', format='pdf', bbox_inches='tight')  # No incluida en el manuscrito final
    print("File 'Supplementary_S4_Scatter_1to1_Averaged.pdf' generated successfully!")

except Exception as e:
    print(f"General error in the process: {e}")
