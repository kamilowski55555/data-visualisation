import warnings
import pandas as pd
import plotly.graph_objects as go
import report_creator as rc

warnings.filterwarnings('ignore')

TEMPLATE = 'plotly_white'

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

total_rev   = df['Revenue'].sum()
n_orders    = df['InvoiceNo'].nunique()
n_customers = int(df['CustomerID'].nunique())
n_countries = df['Country'].nunique()


_df1 = top_countries.sort_values('Przychod')
fp1_top10 = go.Figure(go.Bar(
    x=_df1['Przychod'].tolist(),
    y=_df1['Kraj'].tolist(),
    orientation='h',
    marker_color='#3949ab',
    hovertemplate='<b>%{y}</b><br>Przychód: £%{x:,.0f}<extra></extra>'
))
fp1_top10.update_layout(xaxis_title='Łączny przychód (GBP)', template=TEMPLATE, height=450)
fp1_top10.update_xaxes(tickprefix='£', tickformat=',.0f')

fp2_monthly = go.Figure(go.Scatter(
    x=monthly['YearMonth_str'].tolist(),
    y=monthly['Przychod'].tolist(),
    fill='tozeroy',
    fillcolor='rgba(63,81,181,0.25)',
    line=dict(color='#3f51b5', width=2),
    mode='lines+markers',
    marker=dict(size=6),
    hovertemplate='%{x}<br>Przychód: £%{y:,.0f}<extra></extra>'
))
fp2_monthly.update_layout(xaxis_title='Miesiąc', yaxis_title='Przychód (GBP)', template=TEMPLATE, height=400)
fp2_monthly.update_yaxes(tickprefix='£', tickformat=',.0f')

DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Sunday']
DAY_PL    = {'Monday': 'Poniedziałek', 'Tuesday': 'Wtorek', 'Wednesday': 'Środa', 'Thursday': 'Czwartek', 'Friday': 'Piątek', 'Sunday': 'Niedziela'}
hmap = df.groupby(['DayOfWeek', 'Hour'])['Revenue'].sum().unstack(fill_value=0)
hmap = hmap.reindex([d for d in DAY_ORDER if d in hmap.index])
hmap.index = [DAY_PL.get(d, d) for d in hmap.index]

fp3_heatmap = go.Figure(data=go.Heatmap(
    z=(hmap / 1_000).values,
    x=[f"{h}:00" for h in hmap.columns],
    y=hmap.index.tolist(),
    colorscale='YlOrRd',
    hovertemplate='Dzień: %{y}<br>Godzina: %{x}<br>Przychód: £%{z:.1f}k<extra></extra>'
))
fp3_heatmap.update_layout(xaxis_title='Godzina dnia', yaxis_title='Dzień tygodnia', template=TEMPLATE, height=450)

top6 = top_countries['Kraj'].head(6).tolist()
order_vals = df[df['Country'].isin(top6)].groupby(['InvoiceNo', 'Country'])['Revenue'].sum().reset_index().rename(columns={'Country': 'Kraj', 'Revenue': 'Wartosc'})
box_order = order_vals.groupby('Kraj')['Wartosc'].median().sort_values(ascending=False).index.tolist()

fp4_boxplot = go.Figure()
for country in box_order:
    country_vals = order_vals[order_vals['Kraj'] == country]['Wartosc']
    fp4_boxplot.add_trace(go.Box(
        y=country_vals.tolist(),
        name=country,
        boxpoints=False,
        hovertemplate='<b>%{x}</b><br>Wartość: £%{y:,.0f}<extra></extra>'
    ))
fp4_boxplot.update_layout(xaxis_title='Kraj', yaxis_title='Wartość zamówienia (GBP)', template=TEMPLATE, height=450)
fp4_boxplot.update_yaxes(tickprefix='£', tickformat=',.0f')

_df5 = top_products.sort_values('Przychod')
fp5_top15_prod = go.Figure(go.Bar(
    x=_df5['Przychod'].tolist(),
    y=_df5['Produkt'].tolist(),
    orientation='h',
    marker_color='#00897b',
    hovertemplate='<b>%{y}</b><br>Przychód: £%{x:,.0f}<extra></extra>'
))
fp5_top15_prod.update_layout(xaxis_title='Łączny przychód (GBP)', template=TEMPLATE, height=500)
fp5_top15_prod.update_xaxes(tickprefix='£', tickformat=',.0f')

fp_inter_monthly = go.Figure(go.Scatter(x=monthly['YearMonth_str'].tolist(), y=monthly['Przychod'].tolist(), fill='tozeroy', fillcolor='rgba(63,81,181,0.25)', line=dict(color='#3f51b5', width=2), mode='lines+markers', marker=dict(size=5), hovertemplate='%{x}<br>Przychód: \xa3%{y:,.0f}<extra></extra>'))
fp_inter_monthly.update_layout(xaxis_title='Miesiąc', yaxis_title='Przychód (GBP)', template=TEMPLATE, height=400)

_df2 = top20_countries.sort_values('Przychod_k')
fp_inter_countries20 = go.Figure(go.Bar(x=_df2['Przychod_k'].tolist(), y=_df2['Kraj'].tolist(), orientation='h', hovertemplate='<b>%{y}</b><br>Przychód: \xa3%{x:.1f}k<extra></extra>'))
fp_inter_countries20.update_layout(xaxis_title='Przychód (tys. GBP)', template=TEMPLATE, height=540)
fp_inter_countries20.update_xaxes(tickprefix='\xa3', ticksuffix='k', tickformat='.0f')

_df3 = top_products.sort_values('Przychod_k')
fp_inter_products15 = go.Figure(go.Bar(x=_df3['Przychod_k'].tolist(), y=_df3['Produkt'].tolist(), orientation='h', hovertemplate='<b>%{y}</b><br>Przychód: \xa3%{x:.1f}k<extra></extra>'))
fp_inter_products15.update_layout(xaxis_title='Przychód (tys. GBP)', template=TEMPLATE, height=480)
fp_inter_products15.update_xaxes(tickprefix='\xa3', ticksuffix='k', tickformat='.0f')

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
        rc.Markdown(f"Zbiór danych **Online Retail** (UCI ML Repository) zawiera transakcje brytyjskiego sklepu e-commerce z lat 2010-2011. Analiza obejmuje {n_orders:,} zamówień od {n_customers:,} klientów z {n_countries} krajów. Celem jest identyfikacja wzorców sprzedaży, sezonowości oraz kluczowych rynków zbytu."),
        
        rc.Heading("Struktura geograficzna sprzedaży", level=2),
        rc.Markdown("Zdecydowana większość przychodu pochodzi z rynku brytyjskiego, jednak sklep obsługuje klientów na całym świecie."),
        
        rc.Group(
            rc.Widget(fp1_top10, label="Top 10 krajów według przychodu "),
            rc.Widget(fp5_top15_prod, label="Top 15 produktów według przychodu ")
        ),
        rc.Widget(fp_inter_countries20, label="Top 20 krajów wg przychodu"),
        
        rc.Separator(),

        rc.Heading("Zmiany w czasie - sezonowość sprzedaży", level=2),
        rc.Markdown("Wyraźny wzrost sprzedaży obserwuje się w miesiącach jesiennych (wrzesień-listopad) - efekt przedświątecznych zakupów."),
        rc.Widget(fp2_monthly, label="Miesięczny przychód ze sprzedaży (Interaktywny liniowy)"),
        rc.Widget(fp_inter_monthly, label="Miesięczny przychód ze sprzedaży"),
        
        rc.Separator(),

        rc.Heading("Wzorce behawioralne klientów", level=2),
        rc.Markdown("Analiza aktywności zakupowej w podziale na dni tygodnia i godziny pozwala zidentyfikować szczyty sprzedaży."),
        rc.Widget(fp3_heatmap, label="Rozkład sprzedaży wg dnia tygodnia i godziny"),
        rc.Widget(fp4_boxplot, label="Rozkład wartości zamówień - top kraje bez wartości skrajnych"),
        rc.Widget(fp_inter_products15, label="Top 15 produktów wg przychodu")
    )
    
    out_filename = 'P_02_Kot_Gorecki.html'
    report.save(view, out_filename)

print(f'Raport został pomyślnie zapisany: {out_filename}')