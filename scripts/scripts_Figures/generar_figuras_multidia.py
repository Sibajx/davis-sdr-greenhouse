import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl

# ==========================================
# CONFIGURACIÓN ESTRICTA PARA EL JOURNAL (IJSAMI)
# Genera: Figuras 3-8 del manuscrito final (perfiles multi-día)
#
# NOTA TÉCNICA: se probó texto compuesto con LaTeX real (usetex=True,
# mathptmx/Times), y aunque funciona para texto simple, matplotlib tiene un
# bug conocido al combinarlo con el formato de fecha de dos líneas que usamos
# en el eje X ("Aug 29\n00:00") -> falla con "Missing $ inserted". Como las
# figuras ya publicadas en el manuscrito se generaron con este mismo enfoque
# de fuente (no con usetex), se mantiene por consistencia y robustez.
# ==========================================
mpl.rcParams['font.family'] = 'serif'
mpl.rcParams['font.serif'] = ['Times New Roman', 'Nimbus Roman No9 L',
                               'Liberation Serif', 'Nimbus Roman', 'Times']
mpl.rcParams['mathtext.fontset'] = 'stix'
mpl.rcParams['axes.labelsize'] = 22      # Etiquetas (X, Y) — aumentado de 20 a 22
mpl.rcParams['xtick.labelsize'] = 18     # Números Eje X — aumentado de 16 a 18
mpl.rcParams['ytick.labelsize'] = 18     # Números Eje Y — aumentado de 16 a 18
mpl.rcParams['legend.fontsize'] = 16     # Leyenda — aumentado de 14 a 16

# ==========================================
# ARCHIVOS DE LOS 6 DÍAS CONTINUOS
# ==========================================
ARCHIVOS_CSV = [
    'historial_davis_2026-08-29.csv',
    'historial_davis_2026-08-30.csv',
    'historial_davis_2026-08-31.csv',
    'historial_davis_2026-09-01.csv',
    'historial_davis_2026-09-02.csv',
    'historial_davis_2026-09-03.csv',
]

try:
    print("Cargando los 6 días continuos...")
    dfs = [pd.read_csv(a) for a in ARCHIVOS_CSV]
    df = pd.concat(dfs, ignore_index=True)

    # Parseo de fechas (SIN dayfirst=True: el formato ya es ISO YYYY-MM-DD sin ambigüedad;
    # dayfirst=True combinado con format='mixed' puede invertir día/mes en fechas como 09-01, 09-02, 09-03)
    df['Fecha_Hora'] = pd.to_datetime(df['Fecha_Hora'], format='mixed')
    df['Temp_C'] = pd.to_numeric(df['Temp_C'], errors='coerce')
    df['Humedad_%'] = pd.to_numeric(df['Humedad_%'], errors='coerce')
    df['Radiacion_W_m2'] = pd.to_numeric(df['Radiacion_W_m2'], errors='coerce')
    df['Indice_UV'] = pd.to_numeric(df['Indice_UV'], errors='coerce')
    df = df.dropna(subset=['Fecha_Hora']).sort_values('Fecha_Hora').reset_index(drop=True)

    print(f"-> Rango cargado: {df['Fecha_Hora'].min()} a {df['Fecha_Hora'].max()}  ({len(df)} registros)")

    print("Aplicando suavizado matemático (Media Móvil 15 min)...")
    df['Temp_Suav'] = df['Temp_C'].rolling(window=15, center=True, min_periods=1).mean()
    df['Hum_Suav'] = df['Humedad_%'].rolling(window=15, center=True, min_periods=1).mean()
    df['Solar_Suav'] = df['Radiacion_W_m2'].rolling(window=15, center=True, min_periods=1).mean()
    df['UV_Suav'] = df['Indice_UV'].rolling(window=15, center=True, min_periods=1).mean()

    # Función auxiliar para formatear el Eje X (Fecha + Hora, ya que abarca varios días)
    def formatear_eje_x(ax, fig):
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        fig.autofmt_xdate(rotation=0, ha='center')

    print("Generando Figura 3: Temperatura (Multi-día)...")
    fig1, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df['Fecha_Hora'], df['Temp_C'], label='Raw Data', color='lightcoral', linewidth=1, alpha=0.6)
    ax.plot(df['Fecha_Hora'], df['Temp_Suav'], label='15-min Moving Average', color='darkred', linewidth=2.5)
    ax.set_xlabel('Date and Time')
    ax.set_ylabel('Temperature (°C)')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='best')
    formatear_eje_x(ax, fig1)
    fig1.tight_layout()
    fig1.savefig('Figure_3_Temperature_MultiDay.pdf', format='pdf', bbox_inches='tight')
    plt.close(fig1)

    print("Generando Figura 4: Humedad (Multi-día)...")
    fig2, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df['Fecha_Hora'], df['Humedad_%'], label='Raw Data', color='lightskyblue', linewidth=1, alpha=0.8)
    ax.plot(df['Fecha_Hora'], df['Hum_Suav'], label='15-min Moving Average', color='darkblue', linewidth=2.5)
    ax.set_xlabel('Date and Time')
    ax.set_ylabel('Relative Humidity (%)')
    ax.set_ylim(0, 105)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='lower left')
    formatear_eje_x(ax, fig2)
    fig2.tight_layout()
    fig2.savefig('Figure_4_Humidity_MultiDay.pdf', format='pdf', bbox_inches='tight')
    plt.close(fig2)

    print("Generando Figura 5: Termodinámica (Temp vs Humedad, Multi-día)...")
    fig3, ax_t = plt.subplots(figsize=(14, 6))
    c_temp, c_hum = 'darkred', 'darkblue'
    ax_t.set_xlabel('Date and Time')
    ax_t.set_ylabel('Temperature (°C)', color=c_temp)
    ax_t.plot(df['Fecha_Hora'], df['Temp_C'], color='lightcoral', linewidth=1, alpha=0.5)
    l1 = ax_t.plot(df['Fecha_Hora'], df['Temp_Suav'], color=c_temp, linewidth=2.5, label='Temperature (°C)')
    ax_t.tick_params(axis='y', labelcolor=c_temp)
    ax_t.grid(True, linestyle='--', alpha=0.5)

    ax_h = ax_t.twinx()
    ax_h.set_ylabel('Relative Humidity (%)', color=c_hum)
    ax_h.plot(df['Fecha_Hora'], df['Humedad_%'], color='lightskyblue', linewidth=1, alpha=0.5)
    l2 = ax_h.plot(df['Fecha_Hora'], df['Hum_Suav'], color=c_hum, linewidth=2.5, label='Humidity (%)')
    ax_h.tick_params(axis='y', labelcolor=c_hum)
    ax_h.set_ylim(0, 105)

    lineas = l1 + l2
    ax_t.legend(lineas, [l.get_label() for l in lineas], loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=2)
    formatear_eje_x(ax_t, fig3)
    fig3.tight_layout()
    fig3.savefig('Figure_5_Temp_vs_Humidity_MultiDay.pdf', format='pdf', bbox_inches='tight')
    plt.close(fig3)

    print("Generando Figura 6: Radiación Solar (Multi-día)...")
    fig4, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df['Fecha_Hora'], df['Radiacion_W_m2'], label='Raw Data', color='gold', linewidth=1.2, alpha=0.7)
    ax.plot(df['Fecha_Hora'], df['Solar_Suav'], label='15-min Moving Average', color='darkorange', linewidth=2.5)
    ax.set_xlabel('Date and Time')
    ax.set_ylabel('Solar Irradiance (W/m²)')
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    formatear_eje_x(ax, fig4)
    fig4.tight_layout()
    fig4.savefig('Figure_6_Solar_MultiDay.pdf', format='pdf', bbox_inches='tight')
    plt.close(fig4)

    print("Generando Figura 7: Índice UV (Multi-día)...")
    fig5, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df['Fecha_Hora'], df['Indice_UV'], label='Raw Data', color='plum', linewidth=1.2, alpha=0.7)
    ax.plot(df['Fecha_Hora'], df['UV_Suav'], label='15-min Moving Average', color='indigo', linewidth=2.5)
    ax.set_xlabel('Date and Time')
    ax.set_ylabel('UV Index (UVI)')
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right')
    formatear_eje_x(ax, fig5)
    fig5.tight_layout()
    fig5.savefig('Figure_7_UV_MultiDay.pdf', format='pdf', bbox_inches='tight')
    plt.close(fig5)

    print("Generando Figura 8: Solar vs UV (Multi-día)...")
    fig6, ax_s = plt.subplots(figsize=(14, 6))
    c_sol, c_uv = 'darkorange', 'indigo'
    ax_s.set_xlabel('Date and Time')
    ax_s.set_ylabel('Solar Irradiance (W/m²)', color=c_sol)
    ax_s.plot(df['Fecha_Hora'], df['Radiacion_W_m2'], color='gold', linewidth=1, alpha=0.5)
    ls1 = ax_s.plot(df['Fecha_Hora'], df['Solar_Suav'], color=c_sol, linewidth=2.5, label='Solar Irradiance')
    ax_s.tick_params(axis='y', labelcolor=c_sol)
    ax_s.grid(True, linestyle='--', alpha=0.5)
    ax_s.set_ylim(bottom=0)

    ax_uv = ax_s.twinx()
    ax_uv.set_ylabel('UV Index (UVI)', color=c_uv)
    ax_uv.plot(df['Fecha_Hora'], df['Indice_UV'], color='plum', linewidth=1, alpha=0.5)
    ls2 = ax_uv.plot(df['Fecha_Hora'], df['UV_Suav'], color=c_uv, linewidth=2.5, label='UV Index')
    ax_uv.tick_params(axis='y', labelcolor=c_uv)
    ax_uv.set_ylim(bottom=0)

    lineas_s = ls1 + ls2
    ax_s.legend(lineas_s, [l.get_label() for l in lineas_s], loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=2)
    formatear_eje_x(ax_s, fig6)
    fig6.tight_layout()
    fig6.savefig('Figure_8_Solar_vs_UV_MultiDay.pdf', format='pdf', bbox_inches='tight')
    plt.close(fig6)

    print("\n✅ ¡PROCESO COMPLETADO! Se han generado las Figuras 3-8 (.pdf) del manuscrito final.")

except FileNotFoundError as e:
    print(f"❌ Error: No se encontró un archivo -> {e}")
except Exception as e:
    print(f"❌ Error durante la generación: {e}")
