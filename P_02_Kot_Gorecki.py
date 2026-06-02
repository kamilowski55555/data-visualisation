import warnings
import math
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

# Statystyki ogólne do KPI
total_rev   = df['Revenue'].sum()
n_orders    = df['InvoiceNo'].nunique()
n_customers = int(df['CustomerID'].nunique())
n_countries = df['Country'].nunique()


# ── 3. GENEROWANIE INTERAKTYWNYCH WYKRESÓW PLOTLY ─────────────────────────────

# Poprawka 1 & Poprawka 9: Wykres bąbelkowy z upakowanym kształtem (cluster) i dużymi kołami
df_bubble = by_country.head(10).copy()
uk_revenue = df_bubble[df_bubble['Kraj'] == 'United Kingdom']['Przychod'].values[0]
others_revenue = by_country[by_country['Kraj'] != 'United Kingdom']['Przychod'].sum()

x_pos = []
y_pos = []
other_count = 0

for i, row in df_bubble.iterrows():
    if row['Kraj'] == 'United Kingdom':
        x_pos.append(2.2)  # Pozycja wielkiego koła UK
        y_pos.append(2.5)
    else:
        # Konstruujemy kołowy "cluster" dla pozostałych 9 krajów wokół punktu (5.5, 2.5)
        angle = (other_count * 2 * math.pi) / 9
        radius = 0.95  # Promień zbicia grupy ze sobą
        x_pos.append(5.4 + radius * math.cos(angle))
        y_pos.append(2.5 + radius * math.sin(angle))
        other_count += 1

# Drastycznie zwiększamy maksymalny rozmiar bąbli, aby tekst mieścił się idealnie
max_size = 240
sizeref = max(df_bubble['Przychod']) / (max_size ** 2)

fp1_bubble = go.Figure(go.Scatter(
    x=x_pos, y=y_pos,
    mode='markers+text',
    text=[format_val(r) for r in df_bubble['Przychod']],
    textposition='middle center',
    textfont=dict(color='white', size=11, family='Segoe UI', weight='bold'),
    marker=dict(
        size=df_bubble['Przychod'],
        sizemode='area',
        sizeref=sizeref,
        color=['#1a237e'] + ['#00897b'] * 9,
        line=dict(color='white', width=1.5)
    ),
    customdata=list(zip(df_bubble['Kraj'], df_bubble['Przychod'])),
    hovertemplate='<b>Kraj: %{customdata[0]}</b><br>Pełny Przychód: £%{customdata[1]:,.2f}<extra></extra>'
))
fp1_bubble.update_layout(
    title=f" roporcja rynkowa: UK ({format_val(uk_revenue)}) vs Reszta Świata Łącznie ({format_val(others_revenue)})",
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 7.5]),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 5]),
    template=TEMPLATE, height=480
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


# ── POPRAWKA DLA WSZYSTKICH WYKRESÓW: BEZWZGLĘDNA ORIENTACJA POZIOMA ETYKIET ──
all_charts = [fp1_bubble, fp2_monthly, fp3_heatmap, fp4_box, fp_inter_countries5, fp_uk_vs_rest, fp_top_customers, fp_hourly_qty]
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
        
        rc.Group(
            rc.Widget(StaticPlotlyWidget(fp_top_customers), label="Top 10 Klientów sklepu według łącznej sumy zakupów (Analiza Lojalności)"),
            rc.Widget(StaticPlotlyWidget(fp_hourly_qty), label="Całkowity wolumen sprzedanych produktów według godzin transakcji")
        )
    )
    
    out_filename = 'P_02_Kot_Gorecki.html'
    report.save(view, out_filename)

print(f'Raport został pomyślnie zapisany w pliku: {out_filename}')