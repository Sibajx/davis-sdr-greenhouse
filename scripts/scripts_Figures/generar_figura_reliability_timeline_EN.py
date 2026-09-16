import re
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl

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
mpl.rcParams['axes.labelsize'] = 20      # aumentado de 18 a 20
mpl.rcParams['xtick.labelsize'] = 16     # aumentado de 14 a 16
mpl.rcParams['ytick.labelsize'] = 16     # aumentado de 14 a 16
mpl.rcParams['legend.fontsize'] = 14     # aumentado de 12 a 14

# ==========================================
# INPUT FILES
# ==========================================
ARCHIVO_LOG = 'davis_monitor.log'
ARCHIVOS_SDR = [
    'historial_davis_2026-08-29.csv',
    'historial_davis_2026-08-30.csv',
    'historial_davis_2026-08-31.csv',
    'historial_davis_2026-09-01.csv',
    'historial_davis_2026-09-02.csv',
    'historial_davis_2026-09-03.csv'
]

try:
    # ==========================================
    # DATA FOR PANEL (a) AND (b): WATCHDOG EVENTS
    # ==========================================
    print("Extracting Watchdog events from the log...")
    patron_watchdog = re.compile(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[WARNING\] MainThread: Watchdog SDR activado'
    )
    timestamps = []
    with open(ARCHIVO_LOG, encoding='utf-8', errors='ignore') as f:
        for linea in f:
            m = patron_watchdog.match(linea)
            if m:
                timestamps.append(pd.to_datetime(m.group(1)))
    s_watchdog_full = pd.Series(sorted(timestamps))
    FECHA_INICIO_PRUEBA = pd.Timestamp('2026-08-29 00:00:00')
    FECHA_FIN_PRUEBA = pd.Timestamp('2026-09-03 23:59:59')
    s_watchdog = s_watchdog_full[(s_watchdog_full >= FECHA_INICIO_PRUEBA) & (s_watchdog_full <= FECHA_FIN_PRUEBA)].reset_index(drop=True)
    print(f"-> Total Watchdog events (full log): {len(s_watchdog_full)}")
    print(f"-> Watchdog events within the 6-day test window (Aug 29 - Sep 3): {len(s_watchdog)}")

    intervalos_min = s_watchdog.diff().dropna().dt.total_seconds().values / 60.0
    print(f"-> Empirical MTBF (mean): {intervalos_min.mean():.2f} min")

    # ==========================================
    # DATA FOR PANEL (c): DATABASE WRITE INTERVALS
    # ==========================================
    print("Loading write timestamps (per-minute records)...")
    dfs = [pd.read_csv(a) for a in ARCHIVOS_SDR]
    df_escrituras = pd.concat(dfs, ignore_index=True)
    df_escrituras['Fecha_Hora'] = pd.to_datetime(df_escrituras['Fecha_Hora'], format='mixed')
    df_escrituras = df_escrituras.sort_values('Fecha_Hora').reset_index(drop=True)

    intervalos_escritura_s = df_escrituras['Fecha_Hora'].diff().dropna().dt.total_seconds().values
    media_escritura = intervalos_escritura_s.mean()
    jitter_escritura = intervalos_escritura_s.std()
    print(f"-> N writes: {len(df_escrituras)}  N intervals: {len(intervalos_escritura_s)}")
    print(f"-> Mean write interval: {media_escritura:.3f} s  |  Jitter: {jitter_escritura:.4f} s")

    # ==========================================
    # COMPOSITE 3-PANEL FIGURE
    # ==========================================
    print("Generating PDF...")
    fig, (axa, axb, axc) = plt.subplots(3, 1, figsize=(11, 12))

    # --- PANEL (a): WATCHDOG EVENT TIMELINE ---
    axa.eventplot(s_watchdog, orientation='horizontal', colors='firebrick', linewidths=1.2, linelengths=0.8)
    axa.set_xlim(FECHA_INICIO_PRUEBA, FECHA_FIN_PRUEBA)
    axa.set_yticks([])
    axa.set_ylabel('Watchdog\nRestart')
    axa.set_title(f'(a) Watchdog restart chronology (N = {len(s_watchdog)})',
                  fontsize=15, loc='left')
    axa.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    axa.grid(True, axis='x', linestyle=':', alpha=0.5)

    # --- PANEL (b): TIME BETWEEN FAILURES ---
    axb.scatter(np.arange(1, len(intervalos_min) + 1), intervalos_min,
                color='darkorange', edgecolor='black', linewidth=0.4, s=28, alpha=0.8)
    axb.axhline(intervalos_min.mean(), color='darkblue', linestyle='--', linewidth=1.8,
                label=f'MTBF = {intervalos_min.mean():.2f} min')
    axb.set_yscale('log')
    axb.set_ylabel('TBF (min, log scale)')
    axb.set_xlabel('Restart event number')
    axb.set_title('(b) Time between consecutive failures (TBF)', fontsize=15, loc='left')
    axb.grid(True, which='both', linestyle=':', alpha=0.5)
    axb.legend(loc='upper right')

    # --- PANEL (c): DATABASE WRITE STABILITY ---
    idx = np.arange(1, len(intervalos_escritura_s) + 1)
    axc.scatter(idx, intervalos_escritura_s, color='darkgreen', s=4, alpha=0.35,
                label='Observed intervals')
    axc.axhline(60.0, color='black', linestyle='-', linewidth=1.3, alpha=0.7,
                label='Nominal period (60 s)')
    axc.axhline(media_escritura, color='darkred', linestyle='--', linewidth=1.8,
                label=fr'Mean = {media_escritura:.2f} s, $\sigma$ (jitter) = {jitter_escritura:.3f} s')
    axc.set_ylim(58.5, 62.5)
    axc.set_ylabel('Write interval (s)')
    axc.set_xlabel('Write number (per-minute record)')
    axc.set_title('(c) Stability of the SQLite (WAL) persistence layer', fontsize=15, loc='left')
    axc.grid(True, linestyle=':', alpha=0.5)
    axc.legend(loc='upper right')

    plt.tight_layout()
    plt.savefig('Figure_9_Reliability_Timeline.pdf', format='pdf', bbox_inches='tight')  # Figura 9 oficial del manuscrito
    print("File 'Figure_9_Reliability_Timeline.pdf' generated successfully!")

except Exception as e:
    print(f"General error in the process: {e}")
