import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import plotly.graph_objects as go
import pandas as pd
from io import BytesIO
import base64
import warnings

warnings.filterwarnings('ignore')

sns.set_theme(style='whitegrid', palette='husl', font_scale=1.0)
plt.rcParams['figure.facecolor'] = 'white'
TEMPLATE = 'plotly_white'

# ── Dane ──────────────────────────────────────────────────────────────────────
print('Wczytywanie danych...')
df = pd.read_excel('Online Retail.xlsx', engine='openpyxl')
df = df[~df['InvoiceNo'].astype(str).str.startswith('C')]
df = df[(df['Quantity'] > 0) & (df['UnitPrice'] > 0)]
df = df.dropna(subset=['CustomerID'])

df['Revenue']    = df['Quantity'] * df['UnitPrice']
df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
df['YearMonth']  = df['InvoiceDate'].dt.to_period('M')
df['DayOfWeek']  = df['InvoiceDate'].dt.day_name()
df['Hour']       = df['InvoiceDate'].dt.hour

print(f'Wierszy po czyszczeniu: {len(df):,}')

# ── Agregaty ──────────────────────────────────────────────────────────────────
by_country = (df.groupby('Country')['Revenue']
              .sum().sort_values(ascending=False)
              .reset_index()
              .rename(columns={'Country': 'Kraj', 'Revenue': 'Przychod'}))

top_countries  = by_country.head(10)
top20_countries = by_country.head(20).copy()
top20_countries['Przychod_k'] = top20_countries['Przychod'] / 1_000

monthly = (df.groupby('YearMonth')['Revenue']
           .sum().reset_index()
           .rename(columns={'Revenue': 'Przychod'}))
monthly['YearMonth_str'] = monthly['YearMonth'].astype(str)

top_products = (df.groupby('Description')['Revenue']
                .sum().sort_values(ascending=False)
                .head(15).reset_index()
                .rename(columns={'Description': 'Produkt', 'Revenue': 'Przychod'}))
top_products['Produkt']    = top_products['Produkt'].str.title().str[:40]
top_products['Przychod_k'] = top_products['Przychod'] / 1_000

# ── Helpers ───────────────────────────────────────────────────────────────────
def _to_b64(fig: plt.Figure) -> str:
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _gbp(x, _=None) -> str:
    if x >= 1_000_000:
        return f'\xa3{x / 1_000_000:.1f}M'
    if x >= 1_000:
        return f'\xa3{x / 1_000:.0f}k'
    return f'\xa3{x:.0f}'


def _clean(ax: plt.Axes) -> None:
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


# ── Wykres 1 (Matplotlib) – Top 10 krajów ────────────────────────────────────
fig1, ax1 = plt.subplots(figsize=(9, 6))
bars = ax1.barh(top_countries['Kraj'], top_countries['Przychod'],
                color=sns.color_palette('husl', 10), edgecolor='white', linewidth=0.5)
ax1.set_xlabel('Łączny przychód (GBP)', fontsize=11)
ax1.set_title('Top 10 krajów według przychodu ze sprzedaży', fontsize=13, fontweight='bold', pad=12)
ax1.xaxis.set_major_formatter(mticker.FuncFormatter(_gbp))
ax1.set_xlim(0, top_countries['Przychod'].max() * 1.16)
for bar, val in zip(bars, top_countries['Przychod']):
    ax1.text(val * 1.01, bar.get_y() + bar.get_height() / 2,
             _gbp(val), va='center', fontsize=8, color='#333')
_clean(ax1)
img1 = _to_b64(fig1)
plt.close(fig1)

# ── Wykres 2 (Matplotlib) – Miesięczny przychód ──────────────────────────────
fig2, ax2 = plt.subplots(figsize=(11, 5))
ax2.fill_between(monthly['YearMonth_str'], monthly['Przychod'], alpha=0.25, color='#3f51b5')
ax2.plot(monthly['YearMonth_str'], monthly['Przychod'],
         color='#3f51b5', linewidth=2, marker='o', markersize=5)
ax2.set_xlabel('Miesiąc', fontsize=11)
ax2.set_ylabel('Przychód (GBP)', fontsize=11)
ax2.set_title('Miesięczny przychód ze sprzedaży (2010–2011)', fontsize=13, fontweight='bold', pad=12)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(_gbp))
plt.xticks(rotation=45, ha='right', fontsize=8)
_clean(ax2)
img2 = _to_b64(fig2)
plt.close(fig2)

# ── Wykres 3 (Seaborn) – Heatmapa sprzedaży wg dnia tygodnia i godziny ───────
DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Sunday']
DAY_PL    = {
    'Monday': 'Poniedzialek', 'Tuesday': 'Wtorek',  'Wednesday': 'Sroda',
    'Thursday': 'Czwartek',   'Friday':  'Piatek',   'Sunday':    'Niedziela',
}
hmap = df.groupby(['DayOfWeek', 'Hour'])['Revenue'].sum().unstack(fill_value=0)
hmap = hmap.reindex([d for d in DAY_ORDER if d in hmap.index])
hmap.index = [DAY_PL.get(d, d) for d in hmap.index]

fig3, ax3 = plt.subplots(figsize=(12, 5))
sns.heatmap(hmap / 1_000, cmap='YlOrRd', ax=ax3,
            linewidths=0.3, cbar_kws={'label': 'Przychod (tys. GBP)'})
ax3.set_xlabel('Godzina dnia', fontsize=11)
ax3.set_ylabel('Dzien tygodnia', fontsize=11)
ax3.set_title('Rozkład sprzedaży wg dnia tygodnia i godziny', fontsize=13, fontweight='bold', pad=12)
img3 = _to_b64(fig3)
plt.close(fig3)

# ── Wykres 4 (Seaborn) – Boxplot wartości zamówień ───────────────────────────
top6 = top_countries['Kraj'].head(6).tolist()
order_vals = (df[df['Country'].isin(top6)]
              .groupby(['InvoiceNo', 'Country'])['Revenue']
              .sum().reset_index()
              .rename(columns={'Country': 'Kraj', 'Revenue': 'Wartosc zamowienia'}))
box_order = (order_vals.groupby('Kraj')['Wartosc zamowienia']
             .median().sort_values(ascending=False).index.tolist())

fig4, ax4 = plt.subplots(figsize=(10, 5))
sns.boxplot(data=order_vals, x='Kraj', y='Wartosc zamowienia',
            order=box_order, palette='husl', ax=ax4, width=0.5, linewidth=1.5, showfliers=False)
ax4.set_xlabel('Kraj', fontsize=11)
ax4.set_ylabel('Wartość zamówienia (GBP)', fontsize=11)
ax4.set_title('Rozkład wartości zamówień – top kraje (bez wartości skrajnych)',
              fontsize=13, fontweight='bold', pad=12)
ax4.yaxis.set_major_formatter(mticker.FuncFormatter(_gbp))
_clean(ax4)
img4 = _to_b64(fig4)
plt.close(fig4)

# ── Wykres 5 (Matplotlib) – Top 15 produktów ─────────────────────────────────
fig5, ax5 = plt.subplots(figsize=(9, 7))
bars5 = ax5.barh(top_products['Produkt'], top_products['Przychod'],
                 color=sns.color_palette('husl', 15), edgecolor='white', linewidth=0.5)
ax5.set_xlabel('Łączny przychód (GBP)', fontsize=11)
ax5.set_title('Top 15 produktów według przychodu', fontsize=13, fontweight='bold', pad=12)
ax5.xaxis.set_major_formatter(mticker.FuncFormatter(_gbp))
ax5.set_xlim(0, top_products['Przychod'].max() * 1.18)
for bar, val in zip(bars5, top_products['Przychod']):
    ax5.text(val * 1.01, bar.get_y() + bar.get_height() / 2,
             _gbp(val), va='center', fontsize=7.5, color='#333')
_clean(ax5)
img5 = _to_b64(fig5)
plt.close(fig5)

# ── Plotly 1 – Interaktywny obszarowy ────────────────────────────────────────
fp1 = go.Figure(go.Scatter(
    x=monthly['YearMonth_str'].tolist(),
    y=monthly['Przychod'].tolist(),
    fill='tozeroy',
    fillcolor='rgba(63,81,181,0.25)',
    line=dict(color='#3f51b5', width=2),
    mode='lines+markers',
    marker=dict(size=5),
    hovertemplate='%{x}<br>Przychod: \xa3%{y:,.0f}<extra></extra>',
))
fp1.update_layout(title='Miesieczny przychod ze sprzedazy (interaktywny)',
                  xaxis_title='Miesiac', yaxis_title='Przychod (GBP)',
                  template=TEMPLATE, height=400)
html_p1 = fp1.to_html(full_html=False, include_plotlyjs=False)

# ── Plotly 2 – Top 20 krajów ──────────────────────────────────────────────────
_df2  = top20_countries.sort_values('Przychod_k')
_x2   = _df2['Przychod_k'].tolist()
_y2   = _df2['Kraj'].tolist()
_n2   = [(_v - min(_x2)) / (max(_x2) - min(_x2)) for _v in _x2]
fp2 = go.Figure(go.Bar(
    x=_x2, y=_y2, orientation='h',
    marker_color=[f'rgb({int(255*(1-v))},{int(180*(1-v))},{int(50+200*v)})' for v in _n2],
    hovertemplate='<b>%{y}</b><br>Przychod: \xa3%{x:.1f}k<extra></extra>',
))
fp2.update_layout(title='Top 20 krajow wg przychodu (interaktywny)',
                  xaxis_title='Przychod (tys. GBP)', template=TEMPLATE, height=540)
fp2.update_xaxes(tickprefix='\xa3', ticksuffix='k', tickformat='.0f')
html_p2 = fp2.to_html(full_html=False, include_plotlyjs=False)

# ── Plotly 3 – Top 15 produktów ───────────────────────────────────────────────
_df3  = top_products.sort_values('Przychod_k')
_x3   = _df3['Przychod_k'].tolist()
_y3   = _df3['Produkt'].tolist()
_n3   = [(_v - min(_x3)) / (max(_x3) - min(_x3)) for _v in _x3]
fp3 = go.Figure(go.Bar(
    x=_x3, y=_y3, orientation='h',
    marker_color=[f'rgb({int(68+150*v)},{int(1+85*v)},{int(84+80*(1-v))})' for v in _n3],
    hovertemplate='<b>%{y}</b><br>Przychod: \xa3%{x:.1f}k<extra></extra>',
))
fp3.update_layout(title='Top 15 produktow wg przychodu (interaktywny)',
                  xaxis_title='Przychod (tys. GBP)', template=TEMPLATE, height=480)
fp3.update_xaxes(tickprefix='\xa3', ticksuffix='k', tickformat='.0f')
html_p3 = fp3.to_html(full_html=False, include_plotlyjs=False)

# ── Statystyki do KPI ─────────────────────────────────────────────────────────
total_rev   = df['Revenue'].sum()
n_orders    = df['InvoiceNo'].nunique()
n_customers = int(df['CustomerID'].nunique())
n_countries = df['Country'].nunique()

# ── HTML Raport ───────────────────────────────────────────────────────────────
REPORT = f"""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>P_02 – Analiza sprzedazy e-commerce</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f0f2f5;color:#2c3e50;line-height:1.6}}
    header{{background:linear-gradient(120deg,#1a237e 0%,#3949ab 55%,#5c6bc0 100%);color:#fff;padding:2.5rem 3rem 2rem}}
    header h1{{font-size:1.65rem;font-weight:700;margin-bottom:.3rem}}
    header p{{opacity:.8;font-size:.92rem}}
    .tags{{margin-top:.9rem}}
    .tag{{display:inline-block;background:rgba(255,255,255,.15);border-radius:20px;padding:.2rem .75rem;font-size:.78rem;margin:.2rem .3rem .2rem 0}}
    .container{{max-width:1100px;margin:2rem auto;padding:0 1.5rem}}
    .kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
    .kpi{{background:#fff;border-radius:10px;padding:1.1rem 1rem;box-shadow:0 2px 8px rgba(0,0,0,.07);border-top:4px solid;text-align:center}}
    .kpi.a{{border-color:#3f51b5}}.kpi.b{{border-color:#00897b}}.kpi.c{{border-color:#f57c00}}.kpi.d{{border-color:#8e24aa}}
    .kv{{font-size:1.7rem;font-weight:700}}.kl{{font-size:.78rem;color:#666;margin-top:.2rem}}
    .sec{{background:#fff;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.07);padding:1.8rem 2rem;margin-bottom:2rem}}
    .sec-h{{font-size:1.05rem;font-weight:600;color:#1a237e;border-left:4px solid #3f51b5;padding-left:.7rem;margin-bottom:.8rem}}
    .sec-d{{font-size:.88rem;color:#666;margin-bottom:1.4rem}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem}}
    .full{{grid-column:1/-1}}
    @media(max-width:720px){{.grid{{grid-template-columns:1fr}}.full{{grid-column:1}}.kpi-row{{grid-template-columns:repeat(2,1fr)}}}}
    .card{{background:#fafbfd;border:1px solid #e4e8ef;border-radius:8px;padding:1rem;overflow:hidden}}
    .card-t{{font-size:.8rem;font-weight:600;color:#555;text-align:center;margin-bottom:.6rem;text-transform:uppercase;letter-spacing:.04em}}
    .card img{{width:100%;border-radius:4px;display:block}}
    footer{{text-align:center;padding:2rem 1rem;font-size:.8rem;color:#aaa}}
  </style>
</head>
<body>
<header>
  <h1>Analiza sprzedazy e-commerce &ndash; Online Retail Dataset</h1>
  <p>Zrodlo: UCI Machine Learning Repository &nbsp;&middot;&nbsp; Rynek UK, 2010&ndash;2011 &nbsp;&middot;&nbsp; {n_orders:,} zamowien &nbsp;&middot;&nbsp; {n_customers:,} klientow</p>
  <div class="tags">
    <span class="tag">pandas</span>
    <span class="tag">matplotlib</span>
    <span class="tag">seaborn</span>
    <span class="tag">plotly</span>
  </div>
</header>

<div class="container">
  <div class="kpi-row">
    <div class="kpi a"><div class="kv">&pound;{total_rev/1_000_000:.2f}M</div><div class="kl">Laczny przychod</div></div>
    <div class="kpi b"><div class="kv">{n_orders:,}</div><div class="kl">Zamowien</div></div>
    <div class="kpi c"><div class="kv">{n_customers:,}</div><div class="kl">Klientow</div></div>
    <div class="kpi d"><div class="kv">{n_countries}</div><div class="kl">Krajow</div></div>
  </div>

  <div class="sec">
    <div class="sec-h">Cel i zakres analizy</div>
    <p class="sec-d">
      Zbior danych <strong>Online Retail</strong> (UCI ML Repository) zawiera transakcje
      brytyjskiego sklepu e-commerce z lat 2010&ndash;2011. Analiza obejmuje {n_orders:,} zamowien
      od {n_customers:,} klientow z {n_countries} krajow.
      Celem jest identyfikacja wzorcow sprzedazy, sezonowosci oraz kluczowych rynkow zbytu.
    </p>
  </div>

  <div class="sec">
    <div class="sec-h">Struktura geograficzna sprzedazy</div>
    <p class="sec-d">Zdecydowana wiekszosc przychodu pochodzi z rynku brytyjskiego, jednak sklep obsluguje klientow na calym swiecie.</p>
    <div class="grid">
      <div class="card">
        <div class="card-t">Top 10 krajow wg przychodu (matplotlib)</div>
        <img src="data:image/png;base64,{img1}" alt="Top kraje">
      </div>
      <div class="card">
        <div class="card-t">Top 15 produktow wg przychodu (matplotlib)</div>
        <img src="data:image/png;base64,{img5}" alt="Top produkty">
      </div>
      <div class="card full">
        <div class="card-t">Top 20 krajow wg przychodu &ndash; interaktywny (plotly)</div>
        {html_p2}
      </div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-h">Zmiany w czasie &ndash; sezonowosc sprzedazy</div>
    <p class="sec-d">Wyrazny wzrost sprzedazy obserwuje sie w miesiacach jesiennych (wrzesien&ndash;listopad) &ndash; efekt przedswiatecznych zakupow.</p>
    <div class="grid">
      <div class="card full">
        <div class="card-t">Miesieczny przychod &ndash; wykres liniowy (matplotlib)</div>
        <img src="data:image/png;base64,{img2}" alt="Przychod miesięczny">
      </div>
      <div class="card full">
        <div class="card-t">Miesieczny przychod &ndash; interaktywny (plotly)</div>
        {html_p1}
      </div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-h">Wzorce behawioralne klientow</div>
    <p class="sec-d">Analiza aktywnosci zakupowej w podziale na dni tygodnia i godziny pozwala zidentyfikowac szczyty sprzedazy.</p>
    <div class="grid">
      <div class="card full">
        <div class="card-t">Heatmapa sprzedazy &ndash; dzien tygodnia &times; godzina (seaborn)</div>
        <img src="data:image/png;base64,{img3}" alt="Heatmapa aktywnosci">
      </div>
      <div class="card full">
        <div class="card-t">Rozklad wartosci zamowien wg krajow &ndash; boxplot (seaborn)</div>
        <img src="data:image/png;base64,{img4}" alt="Boxplot zamowien">
      </div>
      <div class="card full">
        <div class="card-t">Top 15 produktow &ndash; interaktywny (plotly)</div>
        {html_p3}
      </div>
    </div>
  </div>
</div>

<footer>
  Zrodlo danych: UCI Machine Learning Repository &ndash; Online Retail Dataset (Daqing Chen, 2012) &nbsp;&middot;&nbsp;
  Python 3 &ndash; pandas, matplotlib, seaborn, plotly &nbsp;&middot;&nbsp;
  K. Kot, W. Gorecki
</footer>
</body>
</html>"""

out = 'P_02_Kot_Gorecki.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(REPORT)
print(f'Raport zapisany: {out}')
