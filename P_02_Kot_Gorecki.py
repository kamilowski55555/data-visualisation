import warnings
import math
import random
import pandas as pd
import plotly.graph_objects as go
import report_creator as rc

warnings.filterwarnings('ignore')

TEMPLATE = 'plotly_white'

class StaticPlotlyWidget:
    def __init__(self, fig):
        self.fig = fig
        
    def _repr_html_(self):
        # Generujemy czysty HTML wykresu, wyłączając automatyczną 
        # responsywność responsywność JS, która wymusza rotację etykiet
        return self.fig.to_html(
            full_html=True, 
            include_plotlyjs=True, 
            config={'responsive': False}
        )

# Helper do ładnego i krótkiego formatowania wartości wewnątrz kół
def format_val(val):
    if val >= 1_000_000: return f"£{val/1_000_000:.1f}M"
    if val >= 1_000: return f"£{val/1_000:.0f}k"
    return f"£{val:.0f}"

# ── 1. Wczytywanie i przygotowanie danych ─────────────────────────────────────
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

# ── 2. Agregaty i struktury danych ───────────────────────────────────────────
by_country = (df.groupby('Country')['Revenue']
              .sum().sort_values(ascending=False)
              .reset_index()
              .rename(columns={'Country': 'Kraj', 'Revenue': 'Przychod'}))

# Poprawka 3: Ścisłe Top 5 krajów
top5_countries = by_country.head(5).copy()
top5_countries['Przychod_k'] = top5_countries['Przychod'] / 1_000

# Dane miesięczne ogółem
monthly = (df.groupby('YearMonth')['Revenue']
           .sum().reset_index()
           .rename(columns={'Revenue': 'Przychod'}))
monthly['YearMonth_str'] = monthly['YearMonth'].astype(str)

# Dane do wykresu UK vs Reszta Świata
df['Is_UK'] = df['Country'].apply(lambda x: 'United Kingdom' if x == 'United Kingdom' else 'Reszta Świata')
monthly_uk_rest = df.groupby(['YearMonth', 'Is_UK'])['Revenue'].sum().unstack(fill_value=0).reset_index()
monthly_uk_rest['YearMonth_str'] = monthly_uk_rest['YearMonth'].astype(str)

# Top 10 Klientów (Lojalność)
top_customers = df.groupby('CustomerID')['Revenue'].sum().sort_values(ascending=False).head(10).reset_index()
top_customers['CustomerID'] = top_customers['CustomerID'].astype(int).astype(str)

# Wolumen sprzedanych sztuk wg godzin
hourly_qty = df.groupby('Hour')['Quantity'].sum().reset_index()

# Nowa agregacja: Podział klientów na przedziały wydatków
customer_all_spending = df.groupby('CustomerID')['Revenue'].sum().reset_index()

# Definiujemy granice przedziałów oraz ich czytelne etykiety
bins = [0, 1000, 5000, 10000, 25000, 50000, 100000, float('inf')]
labels = ['<1k', '1-5k', '5-10k', '10-25k', '25-50k', '50-100k', '100k+']

# Dyskretyzacja danych (przypisanie do kubłów) i zliczenie klientów
customer_all_spending['Przedzial'] = pd.cut(customer_all_spending['Revenue'], bins=bins, labels=labels, right=False)
spending_intervals = customer_all_spending['Przedzial'].value_counts().reindex(labels).reset_index()
spending_intervals.columns = ['Przedzial', 'Liczba_Klientow']

# Statystyki ogólne do KPI
total_rev   = df['Revenue'].sum()
n_orders    = df['InvoiceNo'].nunique()
n_customers = int(df['CustomerID'].nunique())
n_countries = df['Country'].nunique()

# Nowa agregacja: Różnica w popularności produktów (UK vs Reszta Świata)
# Obliczamy łączną ilość sztuk dla każdego produktu w podziale na UK i rynki zagraniczne
prod_geo = df.groupby(['Description', 'Is_UK'])['Quantity'].sum().unstack(fill_value=0)

# Przeskalowanie (Normalizacja): Obliczamy procentowy udział każdego produktu w całkowitym wolumenie danego rynku
total_qty_uk = df[df['Is_UK'] == 'United Kingdom']['Quantity'].sum()
total_qty_rest = df[df['Is_UK'] == 'Reszta Świata']['Quantity'].sum()

prod_geo['UK_share'] = (prod_geo['United Kingdom'] / total_qty_uk) * 100
prod_geo['Rest_share'] = (prod_geo['Reszta Świata'] / total_qty_rest) * 100

# Obliczamy różnicę w punktach procentowych (p.p.)
# Wartości dodatnie = produkt relatywnie popularniejszy w UK
# Wartości ujemne = produkt relatywnie popularniejszy poza UK
prod_geo['Diff'] = prod_geo['UK_share'] - prod_geo['Rest_share']
prod_geo = prod_geo.reset_index()
prod_geo['Produkt'] = prod_geo['Description'].str.title().str[:40]

# Wybieramy top 10 produktów najbardziej odchylonych w stronę UK oraz top 10 w stronę Świata
uk_leaning = prod_geo.sort_values('Diff', ascending=False).head(10)
rest_leaning = prod_geo.sort_values('Diff', ascending=True).head(10)

# Łączymy wyniki i sortujemy, aby wykres rósł płynnie od dołu do góry
prod_diff_df = pd.concat([rest_leaning, uk_leaning]).sort_values('Diff')


# ── 3. GENEROWANIE INTERAKTYWNYCH WYKRESÓW PLOTLY ─────────────────────────────

# Poprawka 1 & Poprawka 9: Wykres bąbelkowy z upakowanym kształtem (cluster) i dużymi kołami
# UK jako wielkie koło, a spośród rynków zagranicznych pokazujemy TOP 5 osobno;
# wszystkie pozostałe kraje agregujemy w jeden bąbelek "Pozostałe (N krajów)".
uk_row      = by_country[by_country['Kraj'] == 'United Kingdom'].iloc[0]
uk_revenue  = uk_row['Przychod']
non_uk      = by_country[by_country['Kraj'] != 'United Kingdom'].reset_index(drop=True)
others_revenue = non_uk['Przychod'].sum()

TOP_N = 5
top_others = non_uk.head(TOP_N)[['Kraj', 'Przychod']].copy()
rest = non_uk.iloc[TOP_N:]
if len(rest) > 0:
    pozostale = pd.DataFrame([{
        'Kraj': f'Pozostałe ({len(rest)} krajów)',
        'Przychod': rest['Przychod'].sum()
    }])
    others_rows = pd.concat([top_others, pozostale], ignore_index=True)
else:
    others_rows = top_others.reset_index(drop=True)

# ── Stałe płótno + mapowanie 1 jednostka danych = 1 piksel ────────────────────
# Rozmiar bąbli (marker) jest podawany w pikselach, więc aby pozycje i rozmiary
# były spójne (brak nakładania się), ustawiamy stałą szerokość/wysokość oraz
# zakresy osi równe wymiarom obszaru rysowania w px. Wtedy promień w px = promień
# w jednostkach danych i pakowanie kół jest dokładne.
FIG_W, FIG_H = 1100, 560
MARGIN = dict(t=90, b=40, l=40, r=40)
plot_w = FIG_W - MARGIN['l'] - MARGIN['r']
plot_h = FIG_H - MARGIN['t'] - MARGIN['b']

# Średnice w px: pole koła proporcjonalne do przychodu (UK = D_MAX)
D_MAX = 250.0
max_rev = uk_revenue  # UK jest największy, więc to globalne maksimum skali
def px_diam(v):
    return D_MAX * math.sqrt(v / max_rev)

uk_d  = px_diam(uk_row['Przychod'])
oth_d = [px_diam(v) for v in others_rows['Przychod']]
oth_r = [d / 2 for d in oth_d]

# Krótkie nazwy (NAD kołem) i kwoty (w ŚRODKU koła). "Pozostałe (N krajów)" -> "Pozostałe".
oth_disp   = ['Pozostałe' if str(k).startswith('Pozostałe') else str(k) for k in others_rows['Kraj']]
oth_amount = [format_val(v) for v in others_rows['Przychod']]   # kwota trafia do środka koła
# Kolory: zagregowane "Pozostałe" dostaje neutralny szary, reszta - morską zieleń
oth_colors = ['#607d8b' if str(k).startswith('Pozostałe') else '#00897b' for k in others_rows['Kraj']]

# ── Okrąg ograniczający = KOŁO + JEDNOLINIOWA nazwa nad nim ────────────────────
# Pakujemy te okręgi, więc ani koła, ani podpisy nie mają prawa się nakładać.
CHAR_W  = 6.5    # przybliżona szerokość znaku nazwy (px)
LABEL_H = 15.0   # wysokość jednej linii podpisu (px)
LBL_GAP = 4.0    # odstęp podpisu od krawędzi koła
def _name_halfwidth(name):
    return len(name) * CHAR_W / 2

eff_r, voff = [], []
for k in range(len(oth_r)):
    r  = oth_r[k]
    hw = _name_halfwidth(oth_disp[k])
    top = r + LBL_GAP + LABEL_H            # od środka koła w górę do szczytu nazwy
    eff_r.append(max((top + r) / 2, r, hw))
    voff.append((top - r) / 2)             # środek okręgu ograniczającego nad środkiem koła

# UK: lewa strona, wyśrodkowane w pionie
uk_cx = uk_d / 2 + 20
uk_cy = plot_h / 2

# ── Pakowanie: algorytm siłowy (rozpychanie okręgów ograniczających + przyciąganie) ──
rng = random.Random(7)
PAD = 6.0
pts = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in oth_r]
n = len(pts)
for _ in range(600):
    # 1) Rozpychanie nakładających się par
    for i in range(n):
        for j in range(i + 1, n):
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            dist = math.hypot(dx, dy) or 1e-6
            need = eff_r[i] + eff_r[j] + PAD
            if dist < need:
                push = (need - dist) / 2
                ux, uy = dx / dist, dy / dist
                pts[i][0] -= ux * push; pts[i][1] -= uy * push
                pts[j][0] += ux * push; pts[j][1] += uy * push
    # 2) Delikatne przyciąganie do środka (utrzymuje grupę zbitą)
    for p in pts:
        p[0] *= 0.985; p[1] *= 0.985

# Środki KÓŁ = środki okręgów ograniczających przesunięte w dół o voff
mark_x = [p[0] for p in pts]
mark_y = [p[1] - voff[k] for k, p in enumerate(pts)]

# Przesuwamy grupę tuż obok UK (mały odstęp) i centrujemy w pionie względem koła UK
group_left = min(mark_x[k] - oth_r[k] for k in range(n))
group_cy   = sum(mark_y) / n
GAP = 70  # odstęp między kołem UK a grupą
shift_x = (uk_cx + uk_d / 2 + GAP) - group_left
shift_y = uk_cy - group_cy
other_x = [mark_x[k] + shift_x for k in range(n)]
other_y = [mark_y[k] + shift_y for k in range(n)]

# Wyśrodkowanie całego układu w poziomie (z uwzględnieniem szerokości nazw)
hw = [_name_halfwidth(oth_disp[k]) for k in range(n)]
content_left  = uk_cx - uk_d / 2
content_right = max(other_x[k] + max(oth_r[k], hw[k]) for k in range(n))
center_shift  = (plot_w - (content_right - content_left)) / 2 - content_left
uk_cx  += center_shift
other_x = [x + center_shift for x in other_x]

fp1_bubble = go.Figure()

# Seria 1: UK – etykieta wewnątrz koła (białą czcionką)
fp1_bubble.add_trace(go.Scatter(
    x=[uk_cx], y=[uk_cy],
    mode='markers+text',
    text=[format_val(uk_row['Przychod'])],
    textposition='middle center',
    textfont=dict(color='white', size=14, family='Segoe UI', weight='bold'),
    marker=dict(size=[uk_d], sizemode='diameter',
                color='#1a237e', line=dict(color='white', width=1.5)),
    customdata=[[uk_row['Kraj'], uk_row['Przychod']]],
    hovertemplate='<b>Kraj: %{customdata[0]}</b><br>Pełny Przychód: £%{customdata[1]:,.2f}<extra></extra>',
    showlegend=False
))

# Seria 2: pozostałe kraje – KWOTA w środku koła
fp1_bubble.add_trace(go.Scatter(
    x=other_x, y=other_y,
    mode='markers+text',
    text=oth_amount,
    textposition='middle center',
    textfont=dict(color='white', size=10, family='Segoe UI', weight='bold'),
    marker=dict(size=oth_d, sizemode='diameter',
                color=oth_colors, line=dict(color='white', width=1.5)),
    customdata=list(zip(others_rows['Kraj'], others_rows['Przychod'])),
    hovertemplate='<b>Kraj: %{customdata[0]}</b><br>Pełny Przychód: £%{customdata[1]:,.2f}<extra></extra>',
    showlegend=False
))

# Nazwy krajów NAD kołami (kwoty są wewnątrz kół)
fp1_bubble.add_annotation(
    x=uk_cx, y=uk_cy + uk_d / 2,
    text=f"<b>{uk_row['Kraj']}</b>",
    showarrow=False, yanchor='bottom', yshift=4,
    font=dict(color='#1a237e', size=12, family='Segoe UI')
)
for k in range(n):
    fp1_bubble.add_annotation(
        x=other_x[k], y=other_y[k] + oth_r[k],
        text=f"<b>{oth_disp[k]}</b>",
        showarrow=False, yanchor='bottom', yshift=3,
        font=dict(color='#00695c', size=11, family='Segoe UI')
    )

fp1_bubble.update_layout(
    title=f"Proporcja rynkowa: UK ({format_val(uk_revenue)}) vs Reszta Świata Łącznie ({format_val(others_revenue)})",
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, plot_w]),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, plot_h]),
    template=TEMPLATE, width=FIG_W, height=FIG_H, autosize=False,
    margin=MARGIN
)


# Wykres 2 – Miesięczny przychód ze sprzedaży
fp2_monthly = go.Figure(go.Scatter(
    x=monthly['YearMonth_str'].tolist(), y=monthly['Przychod'].tolist(),
    fill='tozeroy', fillcolor='rgba(63,81,181,0.25)',
    line=dict(color='#3f51b5', width=2),
    mode='lines+markers', marker=dict(size=6),
    hovertemplate='%{x}<br>Przychód: £%{y:,.0f}<extra></extra>'
))
fp2_monthly.update_layout(xaxis_title='Miesiąc', yaxis_title='Przychód (GBP)', template=TEMPLATE, height=400)
fp2_monthly.update_yaxes(tickprefix='£', tickformat=',.0f')


# Poprawka 6: Heatmapa ze skalą biało-niebieską
DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Sunday']
DAY_PL    = {'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa', 'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Sunday': 'Niedziela'}
hmap = df.groupby(['DayOfWeek', 'Hour'])['Revenue'].sum().unstack(fill_value=0)
hmap = hmap.reindex([d for d in DAY_ORDER if d in hmap.index])
hmap.index = [DAY_PL.get(d, d) for d in hmap.index]

fp3_heatmap = go.Figure(data=go.Heatmap(
    z=(hmap / 1_000).values,
    x=[f"{h}:00" for h in hmap.columns],
    y=hmap.index.tolist(),
    colorscale=[[0, '#ffffff'], [1, '#0d47a1']],  # Paleta od czystej bieli do ciemnego niebieskiego
    hovertemplate='Dzień: %{y}<br>Godzina: %{x}<br>Przychód: £%{z:.1f}k<extra></extra>'
))
fp3_heatmap.update_layout(xaxis_title='Godzina dnia', yaxis_title='Dzień tygodnia', template=TEMPLATE, height=450)


# Poprawka 7 (Rozwiązanie problemu plamy punktów UK): Zgrupowany czysty BOX PLOT bez surowych punktów
top6 = by_country.head(6)['Kraj'].tolist()
order_vals = df[df['Country'].isin(top6)].groupby(['InvoiceNo', 'Country'])['Revenue'].sum().reset_index().rename(columns={'Country': 'Kraj', 'Revenue': 'Wartosc'})
box_order = order_vals.groupby('Kraj')['Wartosc'].median().sort_values(ascending=False).index.tolist()

# Odcinamy ekstremalne anomalie dla zachowania przejrzystej skali osi Y
q1 = order_vals['Wartosc'].quantile(0.25)
q3 = order_vals['Wartosc'].quantile(0.75)
iqr = q3 - q1
limit_gorny = q3 + 1.5 * iqr
order_vals_clean = order_vals[order_vals['Wartosc'] <= limit_gorny]

fp4_box = go.Figure()
for country in box_order:
    country_vals = order_vals_clean[order_vals_clean['Kraj'] == country]['Wartosc']
    fp4_box.add_trace(go.Box(
        y=country_vals.tolist(),
        name=country,
        boxpoints=False,  # KLUCZOWA POPRAWKA: całkowicie ukrywa kropki, grupując dane w czytelne skrzynki
        hovertemplate='<b>%{x}</b><br>Mediana zamówienia: £%{y:,.0f}<extra></extra>'
    ))
fp4_box.update_layout(xaxis_title='Kraj', yaxis_title='Wartość zamówienia (GBP)', template=TEMPLATE, height=450)
fp4_box.update_yaxes(tickprefix='£', tickformat=',.0f')


# Wykres 5: Top 5 rynków zagranicznych (zamiast Top 20)
_df2 = top5_countries.sort_values('Przychod_k')
fp_inter_countries5 = go.Figure(go.Bar(
    x=_df2['Przychod_k'].tolist(), y=_df2['Kraj'].tolist(),
    orientation='h', marker_color='#3f51b5',
    hovertemplate='<b>%{y}</b><br>Przychód: £%{x:.1f}k<extra></extra>'
))
fp_inter_countries5.update_layout(xaxis_title='Przychód (tys. GBP)', template=TEMPLATE, height=400)
fp_inter_countries5.update_xaxes(tickprefix='£', ticksuffix='k', tickformat='.0f')


# Wykres 6: Nowy trend - Porównanie trendu: UK vs Świat
fp_uk_vs_rest = go.Figure()
fp_uk_vs_rest.add_trace(go.Bar(x=monthly_uk_rest['YearMonth_str'], y=monthly_uk_rest['United Kingdom'], name='United Kingdom', marker_color='#1a237e'))
fp_uk_vs_rest.add_trace(go.Bar(x=monthly_uk_rest['YearMonth_str'], y=monthly_uk_rest['Reszta Świata'], name='Reszta Świata', marker_color='#00897b'))
fp_uk_vs_rest.update_layout(barmode='group', xaxis_title='Miesiąc', yaxis_title='Przychód (GBP)', template=TEMPLATE, height=400)
fp_uk_vs_rest.update_yaxes(tickprefix='£', tickformat=',.0f')


# Wykresy dodatkowe z punktu 8
fp_top_customers = go.Figure(go.Bar(x=top_customers['CustomerID'], y=top_customers['Revenue'], marker_color='#8e24aa', hovertemplate='ID Klienta: %{x}<br>Wartość: £%{y:,.2f}<extra></extra>'))
fp_top_customers.update_layout(xaxis_title='ID Klienta', yaxis_title='Suma zakupów (GBP)', template=TEMPLATE, height=400, xaxis=dict(type='category'))
fp_top_customers.update_yaxes(tickprefix='£', tickformat=',.0f')

fp_hourly_qty = go.Figure(go.Scatter(x=hourly_qty['Hour'], y=hourly_qty['Quantity'], mode='lines+markers', line=dict(color='#e65100', width=3), hovertemplate='Godzina: %{x}:00<br>Ilość sztuk: %{y:,}<extra></extra>'))
fp_hourly_qty.update_layout(xaxis_title='Godzina transakcji', yaxis_title='Liczba sprzedanych sztuk', template=TEMPLATE, height=400, xaxis=dict(tickmode='linear'))

# Nowy wykres: Liczba klientów w przedziałach wydatków
fp_customer_segments = go.Figure(go.Bar(
    x=spending_intervals['Przedzial'],
    y=spending_intervals['Liczba_Klientow'],
    marker_color='#0288d1',
    text=spending_intervals['Liczba_Klientow'],
    textposition='auto',
    hovertemplate='Przedział: %{x}<br>Liczba klientów: %{y:,}<extra></extra>'
))
fp_customer_segments.update_layout(
    xaxis_title='Przedział całkowitych wydatków (GBP)',
    yaxis_title='Liczba unikalnych klientów',
    template=TEMPLATE,
    height=400
)

# Nowy wykres: Różnica popularności produktów (Skala względna UK vs Reszta Świata)
fp_product_diff = go.Figure(go.Bar(
    x=prod_diff_df['Diff'],
    y=prod_diff_df['Produkt'],
    orientation='h',
    # Kolorowanie warunkowe: Morska zieleń dla Reszty Świata, Ciemny niebieski dla UK
    marker_color=['#00897b' if d < 0 else '#1a237e' for d in prod_diff_df['Diff']],
    hovertemplate='<b>%{y}</b><br>Różnica udziału: %{x:.3f} p.p.<extra></extra>'
))

fp_product_diff.update_layout(
    title="Profilowanie asortymentu: Produkty specyficzne dla rynków zagranicznych (<span style='color:#00897b'>Reszta Świata</span>) vs <span style='color:#1a237e'>Wielka Brytania</span>",
    xaxis_title='Różnica udziału w wolumenie rynku (Punkty Procentowe: Udział UK % - Udział Świata %)',
    yaxis_title='Produkt',
    template=TEMPLATE,
    height=600
)


# ── POPRAWKA DLA WSZYSTKICH WYKRESÓW: BEZWZGLĘDNA ORIENTACJA POZIOMA ETYKIET ──
all_charts = [fp1_bubble, fp2_monthly, fp3_heatmap, fp4_box, fp_inter_countries5, fp_uk_vs_rest, fp_top_customers, fp_hourly_qty, fp_customer_segments, fp_product_diff]
for chart in all_charts:
    # Wymuszamy kąt 0 stopni (idealnie poziomo) oraz włączamy autodobieranie marginesów
    chart.update_xaxes(tickangle=0, automargin=True, overwrite=True)
    chart.update_yaxes(tickangle=0, automargin=True, overwrite=True)


# ── 4. BUDOWANIE INTERAKTYWNEGO RAPORTU (report-creator API) ──────────────────
print('Kompilacja raportu HTML...')


with rc.ReportCreator(
    title="Analiza sprzedaży e-commerce",
    description=f"Źródło danych: UCI Machine Learning Repository  ·  Rynek UK, 2010-2011  ·  {n_orders:,} zamówień  ·  {n_customers:,} klientów",
    footer="Skrypt wygenerowany automatycznie za pomocą pakietu report-creator  ·  Autorzy: K. Kot, W. Górecki"
) as report:

    view = rc.Block(
        
        rc.Group(
            rc.Metric(heading="Łączny przychód", value=f"£{total_rev/1_000_000:.2f}M"),
            rc.Metric(heading="Liczba zamówień", value=f"{n_orders:,}"),
            rc.Metric(heading="Unikalni klienci", value=f"{n_customers:,}"),
            rc.Metric(heading="Obsługiwane kraje", value=str(n_countries)),
            label="Kluczowe wskaźniki efektywności (KPI)"
        ),
        
        rc.Separator(),
        
        rc.Heading("Cel i zakres analizy", level=2),
        rc.Markdown(f"Zbiór danych **Online Retail** (UCI ML Repository) zawiera transakcje brytyjskiego sklepu e-commerce z lat 2010–2011. Analiza obejmuje {n_orders:,} zamówień od {n_customers:,} klientów z {n_countries} krajów. Celem jest identyfikacja wzorców sprzedaży, sezonowości oraz kluczowych rynków zbytu."),
        
        rc.Heading("Struktura geograficzna sprzedaży", level=2),
        rc.Markdown("Wizualizacja proporcji sprzedaży rodzimej (UK) na tle rynków międzynarodowych."),
        
        rc.Widget(StaticPlotlyWidget(fp1_bubble), label="Globalna struktura przychodów: Zgrupowany wykres bąbelkowy (UK vs Pozostałe Kraje)"),
        rc.Widget(StaticPlotlyWidget(fp_inter_countries5), label="Top 5 rynków zagranicznych według generowanego przychodu"),
        rc.Widget(StaticPlotlyWidget(fp_product_diff), label="Analiza preferencji produktowych: Produkty charakterystyczne rynkowo (Różnica w p.p. udziału wolumenu)"),

        rc.Separator(),

        rc.Heading("Sezonowość i dynamika przychodów", level=2),
        rc.Markdown("Porównanie ogólnego trendu czasowego z uwzględnieniem podziału na rynki krajowe i zagraniczne."),
        rc.Widget(StaticPlotlyWidget(fp2_monthly), label="Miesięczny przychód całkowity sklepu (Wykres liniowy)"),
        rc.Widget(StaticPlotlyWidget(fp_uk_vs_rest), label="Miesięczny przychód: Wielka Brytania w zestawieniu z resztą świata"),
        
        rc.Separator(),

        # Sekcja 4
        rc.Heading("Wzorce behawioralne klientów oraz analizy dedykowane", level=2),
        rc.Markdown("Identyfikacja szczytów aktywności, rozkładów wartości koszyków zakupowych oraz kluczowych dla biznesu odbiorców."),
        rc.Widget(StaticPlotlyWidget(fp3_heatmap), label="Rozkład wartości sprzedaży według dnia tygodnia i godziny (Skala niebieska)"),
        rc.Widget(StaticPlotlyWidget(fp4_box), label="Rozkład wartości pojedynczych zamówień dla top krajów (Wykres pudełkowy - wartości pogrupowane)"),
        
        # Zaktualizowana grupa zawierająca 3 wykresy analiz strukturalnych
        rc.Group(
            rc.Widget(StaticPlotlyWidget(fp_top_customers), label="Top 10 Klientów sklepu według łącznej sumy zakupów (Analiza Lojalności)"),
            rc.Widget(StaticPlotlyWidget(fp_customer_segments), label="Segmentacja bazy odbiorców: Liczba klientów w przedziałach wartości zakupów"),
            rc.Widget(StaticPlotlyWidget(fp_hourly_qty), label="Całkowity wolumen sprzedanych produktów według godzin transakcji")
        )
    )
    
    out_filename = 'P_02_Kot_Gorecki.html'
    report.save(view, out_filename)

print(f'Raport został pomyślnie zapisany w pliku: {out_filename}')