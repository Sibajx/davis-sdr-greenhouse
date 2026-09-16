import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
mpl.rcParams['axes.labelsize'] = 18
mpl.rcParams['xtick.labelsize'] = 15
mpl.rcParams['ytick.labelsize'] = 15
mpl.rcParams['legend.fontsize'] = 13

WIFI_FILE = 'davis_wifi_logger.csv'
SDR_FILES = [
    'historial_davis_2026-08-29.csv',
    'historial_davis_2026-08-30.csv',
    'historial_davis_2026-08-31.csv',
    'historial_davis_2026-09-01.csv',
    'historial_davis_2026-09-02.csv',
    'historial_davis_2026-09-03.csv'
]

ARCHIVE_WINDOW_MIN = 30    # Confirmed archive interval of the WiFiLogger
CLOCK_OFFSET_MIN = 61      # Clock offset already detected previously (temperature)


def compute_metrics(davis, sdr):
    davis = np.asarray(davis, dtype=float)
    sdr = np.asarray(sdr, dtype=float)
    mae = np.mean(np.abs(sdr - davis))
    rmse = np.sqrt(np.mean((sdr - davis) ** 2))
    bias = np.mean(sdr - davis)
    r, _ = stats.pearsonr(davis, sdr)
    slope, intercept, r_reg, _, _ = stats.linregress(davis, sdr)
    return {'MAE': mae, 'RMSE': rmse, 'Bias': bias, 'r': r, 'R2': r_reg ** 2, 'N': len(davis)}


try:
    # ==========================================
    # DATA LOADING
    # ==========================================
    print("Loading WiFiLogger...")
    df_wifi = pd.read_csv(WIFI_FILE)
    df_wifi['Datetime'] = pd.to_datetime(df_wifi['Date'] + ' ' + df_wifi['Time'], format='mixed', dayfirst=False)
    start_date = pd.to_datetime('2026-08-29 00:00:00')
    end_date = pd.to_datetime('2026-09-03 23:59:59')
    df_wifi = df_wifi[(df_wifi['Datetime'] >= start_date) & (df_wifi['Datetime'] <= end_date)].copy()
    for c in ['Temp Out', 'Out Hum', 'Solar Rad.', 'UV Index']:
        df_wifi[c] = pd.to_numeric(df_wifi[c], errors='coerce')
    df_wifi['Temp_C_Wifi'] = (df_wifi['Temp Out'] - 32) * 5.0 / 9.0
    df_wifi = df_wifi.dropna(subset=['Temp_C_Wifi', 'Out Hum', 'Solar Rad.', 'UV Index']).sort_values('Datetime')

    print("Loading SDR data (1-minute resolution)...")
    df_sdr = pd.concat([pd.read_csv(a) for a in SDR_FILES], ignore_index=True)
    df_sdr['Fecha_Hora'] = pd.to_datetime(df_sdr['Fecha_Hora'], format='mixed')
    for c in ['Temp_C', 'Humedad_%', 'Radiacion_W_m2', 'Indice_UV']:
        df_sdr[c] = pd.to_numeric(df_sdr[c], errors='coerce')
    df_sdr = df_sdr.dropna(subset=['Temp_C', 'Humedad_%', 'Radiacion_W_m2', 'Indice_UV']).sort_values('Fecha_Hora')

    # Apply the already-detected clock offset correction
    df_sdr['Fecha_Hora'] = df_sdr['Fecha_Hora'] + pd.Timedelta(minutes=CLOCK_OFFSET_MIN)
    df_sdr = df_sdr.set_index('Fecha_Hora').sort_index()

    # ==========================================
    # 30-MIN MOVING AVERAGE (REPLICATING THE DAVIS ARCHIVE METHOD)
    # "Average over the archive period" -> a backward-looking window that
    # ends exactly at the record's timestamp.
    # ==========================================
    print(f"Computing a {ARCHIVE_WINDOW_MIN}-min backward-looking moving average over the SDR data...")
    df_sdr_avg = df_sdr[['Temp_C', 'Humedad_%', 'Radiacion_W_m2', 'Indice_UV']].rolling(
        f'{ARCHIVE_WINDOW_MIN}min', min_periods=15
    ).mean()
    df_sdr_avg = df_sdr_avg.rename(columns={
        'Temp_C': 'Temp_C_avg', 'Humedad_%': 'Humedad_avg',
        'Radiacion_W_m2': 'Radiacion_avg', 'Indice_UV': 'UV_avg'
    }).reset_index()

    # Instantaneous SDR series (for comparison, nearest-point matching — the previous method)
    df_sdr_inst = df_sdr.reset_index()

    # ==========================================
    # MATCHING: AVERAGED SDR vs WIFILOGGER
    # ==========================================
    df_eval_avg = pd.merge_asof(
        df_wifi[['Datetime', 'Temp_C_Wifi', 'Out Hum', 'Solar Rad.', 'UV Index']],
        df_sdr_avg,
        left_on='Datetime', right_on='Fecha_Hora',
        direction='nearest', tolerance=pd.Timedelta('2 minutes')
    ).dropna().copy()

    # MATCHING: INSTANTANEOUS SDR vs WIFILOGGER (previous method, for reference)
    df_eval_inst = pd.merge_asof(
        df_wifi[['Datetime', 'Temp_C_Wifi', 'Out Hum', 'Solar Rad.', 'UV Index']],
        df_sdr_inst[['Fecha_Hora', 'Temp_C', 'Humedad_%', 'Radiacion_W_m2', 'Indice_UV']],
        left_on='Datetime', right_on='Fecha_Hora',
        direction='nearest', tolerance=pd.Timedelta('5 minutes')
    ).dropna().copy()

    print(f"-> Matched pairs (30-min average): {len(df_eval_avg)}")
    print(f"-> Matched pairs (instantaneous, reference): {len(df_eval_inst)}")

    # ==========================================
    # METRIC COMPARISON: INSTANTANEOUS vs AVERAGED
    # ==========================================
    pairs = {
        'Temperature (°C)':       ('Temp_C_Wifi', 'Temp_C', 'Temp_C_avg'),
        'Relative Humidity (%)':  ('Out Hum', 'Humedad_%', 'Humedad_avg'),
        'Solar Radiation (W/m²)': ('Solar Rad.', 'Radiacion_W_m2', 'Radiacion_avg'),
        'UV Index (UVI)':         ('UV Index', 'Indice_UV', 'UV_avg'),
    }

    print("\n" + "=" * 92)
    print(f"{'Variable':<24}{'':>4}{'MAE (inst)':>11}{'MAE (avg30)':>12}{'':>4}{'r (inst)':>10}{'r (avg30)':>10}{'R2 (avg30)':>12}")
    print("=" * 92)
    summary = {}
    for name, (col_davis, col_inst, col_avg) in pairs.items():
        m_inst = compute_metrics(df_eval_inst[col_davis], df_eval_inst[col_inst])
        m_avg = compute_metrics(df_eval_avg[col_davis], df_eval_avg[col_avg])
        summary[name] = {'inst': m_inst, 'avg': m_avg}
        print(f"{name:<24}{'':>4}{m_inst['MAE']:>11.3f}{m_avg['MAE']:>12.3f}{'':>4}"
              f"{m_inst['r']:>10.4f}{m_avg['r']:>10.4f}{m_avg['R2']:>12.4f}")
    print("=" * 92)

    df_summary = pd.DataFrame({
        (name, method): values
        for name, d in summary.items() for method, values in d.items()
    }).T
    df_summary.to_csv('Supplementary_S6_Davis_Averaging_Comparison_Table.csv')
    print("\nTable saved to 'Supplementary_S6_Davis_Averaging_Comparison_Table.csv'")

    # ==========================================
    # FIGURE: INSTANTANEOUS SDR vs 30-MIN AVERAGED SDR vs WIFILOGGER
    # (Solar Radiation and UV Index only, where the effect is visible)
    # ==========================================
    print("\nGenerating comparison figure...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    ax1.plot(df_eval_inst['Fecha_Hora'], df_eval_inst['Radiacion_W_m2'],
              color='lightsalmon', linewidth=1.0, alpha=0.6, label='Instantaneous SDR (raw)')
    ax1.plot(df_eval_avg['Datetime'], df_eval_avg['Radiacion_avg'],
              color='darkorange', linewidth=2.2, label='30-min averaged SDR (Davis method)')
    ax1.plot(df_wifi['Datetime'], df_wifi['Solar Rad.'],
              color='dimgray', linestyle='--', linewidth=1.8, marker='o', markersize=3,
              label='Commercial WiFiLogger')
    ax1.set_ylabel('Solar Irradiance (W/m²)')
    ax1.grid(True, linestyle=':', alpha=0.5)
    ax1.legend(loc='upper right', fontsize=10)

    ax2.plot(df_eval_inst['Fecha_Hora'], df_eval_inst['Indice_UV'],
              color='thistle', linewidth=1.0, alpha=0.6, label='Instantaneous SDR (raw)')
    ax2.plot(df_eval_avg['Datetime'], df_eval_avg['UV_avg'],
              color='indigo', linewidth=2.2, label='30-min averaged SDR (Davis method)')
    ax2.plot(df_wifi['Datetime'], df_wifi['UV Index'],
              color='dimgray', linestyle='--', linewidth=1.8, marker='o', markersize=3,
              label='Commercial WiFiLogger')
    ax2.set_ylabel('UV Index (UVI)')
    ax2.set_xlabel('Date and Time')
    ax2.grid(True, linestyle=':', alpha=0.5)
    ax2.legend(loc='upper right', fontsize=10)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))
    fig.autofmt_xdate(rotation=0, ha='center')

    plt.tight_layout()
    plt.savefig('Supplementary_S6_Davis_Averaging_Validation.pdf', format='pdf', bbox_inches='tight')  # Not included in the final manuscript
    print("File 'Supplementary_S6_Davis_Averaging_Validation.pdf' generated successfully!")

except Exception as e:
    print(f"General error in the process: {e}")
