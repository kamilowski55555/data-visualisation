import warnings
import math
import random
import pandas as pd
import plotly.graph_objects as go
import report_creator as rc

warnings.filterwarnings("ignore")

TEMPLATE = "plotly_white"


class StaticPlotlyWidget:
    def __init__(self, fig):
        self.fig = fig

    def _repr_html_(self):
        return self.fig.to_html(
            full_html=True, include_plotlyjs=True, config={"responsive": False}
        )


def format_val(val):
    if val >= 1_000_000:
        return f"£{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"£{val / 1_000:.0f}k"
    return f"£{val:.0f}"


print("Wczytywanie danych...")
df = pd.read_excel("Online Retail.xlsx", engine="openpyxl")
df = df[~df["InvoiceNo"].astype(str).str.startswith("C")]
df = df[(df["Quantity"] > 0) & (df["UnitPrice"] > 0)]
df = df.dropna(subset=["CustomerID"])

df["Revenue"] = df["Quantity"] * df["UnitPrice"]
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
df["YearMonth"] = df["InvoiceDate"].dt.to_period("M")
df["DayOfWeek"] = df["InvoiceDate"].dt.day_name()
df["Hour"] = df["InvoiceDate"].dt.hour

print(f"Wierszy po czyszczeniu: {len(df):,}")

pareto_data = (
    df.groupby("Description")["Revenue"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)
total_revenue_pareto = pareto_data["Revenue"].sum()
total_products_count = len(pareto_data)

pareto_data["Cum_Revenue"] = pareto_data["Revenue"].cumsum()
pareto_data["Cum_Rev_Pct"] = (pareto_data["Cum_Revenue"] / total_revenue_pareto) * 100
pareto_data["Cum_Prod_Pct"] = ((pareto_data.index + 1) / total_products_count) * 100

rev_at_20_pct_prod = pareto_data.iloc[
    (pareto_data["Cum_Prod_Pct"] - 20).abs().idxmin()
]["Cum_Rev_Pct"]
by_country = (
    df.groupby("Country")["Revenue"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
    .rename(columns={"Country": "Kraj", "Revenue": "Przychod"})
)


top5_countries = by_country[by_country["Kraj"] != "United Kingdom"].head(5).copy()
top5_countries["Przychod_k"] = top5_countries["Przychod"] / 1_000


monthly = (
    df.groupby("YearMonth")["Revenue"]
    .sum()
    .reset_index()
    .rename(columns={"Revenue": "Przychod"})
)
monthly["YearMonth_str"] = monthly["YearMonth"].dt.strftime("%m.%Y")


df["Is_UK"] = df["Country"].apply(
    lambda x: "United Kingdom" if x == "United Kingdom" else "Reszta Świata"
)
monthly_uk_rest = (
    df.groupby(["YearMonth", "Is_UK"])["Revenue"]
    .sum()
    .unstack(fill_value=0)
    .reset_index()
)
monthly_uk_rest["YearMonth_str"] = monthly_uk_rest["YearMonth"].dt.strftime("%m.%Y")

top_customers = (
    df.groupby("CustomerID")["Revenue"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)
top_customers["CustomerID"] = top_customers["CustomerID"].astype(int).astype(str)

hourly_qty = df.groupby("Hour")["Quantity"].sum().reset_index()

prod_summary = (
    df.groupby("Description")
    .agg(Sztuki=("Quantity", "sum"), Przychod=("Revenue", "sum"))
    .reset_index()
)
top_products = prod_summary.sort_values("Przychod", ascending=False).head(12).copy()
top_products["Produkt"] = top_products["Description"].str.title().str[:35]
customer_all_spending = df.groupby("CustomerID")["Revenue"].sum().reset_index()
bins = [0, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, float("inf")]
labels = [
    "<100",
    "100-250",
    "250-500",
    "500-1k",
    "1-2.5k",
    "2.5-5k",
    "5-10k",
    "10-25k",
    "25k+",
]
customer_all_spending["Przedzial"] = pd.cut(
    customer_all_spending["Revenue"], bins=bins, labels=labels, right=False
)
spending_intervals = (
    customer_all_spending["Przedzial"].value_counts().reindex(labels).reset_index()
)
spending_intervals.columns = ["Przedzial", "Liczba_Klientow"]
total_rev = df["Revenue"].sum()
n_orders = df["InvoiceNo"].nunique()
n_customers = int(df["CustomerID"].nunique())
n_countries = df["Country"].nunique()
prod_geo = df.groupby(["Description", "Is_UK"])["Quantity"].sum().unstack(fill_value=0)
total_qty_uk = df[df["Is_UK"] == "United Kingdom"]["Quantity"].sum()
total_qty_rest = df[df["Is_UK"] == "Reszta Świata"]["Quantity"].sum()
prod_geo["UK_share"] = (prod_geo["United Kingdom"] / total_qty_uk) * 100
prod_geo["Rest_share"] = (prod_geo["Reszta Świata"] / total_qty_rest) * 100
prod_geo["Diff"] = prod_geo["UK_share"] - prod_geo["Rest_share"]
prod_geo = prod_geo.reset_index()
prod_geo["Produkt"] = prod_geo["Description"].str.title().str[:40]
uk_leaning = prod_geo.sort_values("Diff", ascending=False).head(10)
rest_leaning = prod_geo.sort_values("Diff", ascending=True).head(10)

prod_diff_df = pd.concat([rest_leaning, uk_leaning]).sort_values("Diff")

fp_pareto = go.Figure()
fp_pareto.add_trace(
    go.Scatter(
        x=pareto_data["Cum_Prod_Pct"],
        y=pareto_data["Cum_Rev_Pct"],
        mode="lines",
        line=dict(color="#d32f2f", width=3),
        name="Skumulowany przychód",
        hovertemplate="Top %{x:.1f}% produktów<br>Generuje: %{y:.1f}% przychodu<extra></extra>",
    )
)
fp_pareto.add_vline(
    x=20,
    line_dash="dash",
    line_color="#777777",
    annotation_text="Progowe 20% produktów",
    annotation_position="top left",
)
fp_pareto.add_hline(
    y=80,
    line_dash="dash",
    line_color="#777777",
    annotation_text="Progowe 80% przychodu",
    annotation_position="bottom right",
)
fp_pareto.add_trace(
    go.Scatter(
        x=[20],
        y=[80],
        mode="markers",
        marker=dict(color="black", size=10, symbol="x"),
        name="Punkt idealnego Pareto (20/80)",
        hovertemplate="Punkt odniesienia 20/80<extra></extra>",
    )
)
fp_pareto.update_layout(
    title="Weryfikacja zasady Pareto: Skumulowany udział produktów w całkowitym przychodzie",
    xaxis_title="Skumulowany procent liczby produktów (od najważniejszego)",
    yaxis_title="Skumulowany procent łącznego przychodu (%)",
    template=TEMPLATE,
    height=450,
    showlegend=False,
    xaxis=dict(ticksuffix="%", range=[0, 105]),
    yaxis=dict(ticksuffix="%", range=[0, 105]),
)

uk_row = by_country[by_country["Kraj"] == "United Kingdom"].iloc[0]
uk_revenue = uk_row["Przychod"]
non_uk = by_country[by_country["Kraj"] != "United Kingdom"].reset_index(drop=True)
others_revenue = non_uk["Przychod"].sum()
TOP_N = 5
top_others = non_uk.head(TOP_N)[["Kraj", "Przychod"]].copy()
rest = non_uk.iloc[TOP_N:]
if len(rest) > 0:
    pozostale = pd.DataFrame(
        [
            {
                "Kraj": f"Pozostałe ({len(rest)} krajów)",
                "Przychod": rest["Przychod"].sum(),
            }
        ]
    )
    others_rows = pd.concat([top_others, pozostale], ignore_index=True)
else:
    others_rows = top_others.reset_index(drop=True)

FIG_W, FIG_H = 1100, 560
MARGIN = dict(t=90, b=40, l=40, r=40)
plot_w = FIG_W - MARGIN["l"] - MARGIN["r"]
plot_h = FIG_H - MARGIN["t"] - MARGIN["b"]

D_MAX = 250.0
max_rev = uk_revenue

def px_diam(v):
    return D_MAX * math.sqrt(v / max_rev)

uk_d = px_diam(uk_row["Przychod"])
oth_d = [px_diam(v) for v in others_rows["Przychod"]]
oth_r = [d / 2 for d in oth_d]

oth_disp = [
    "Pozostałe" if str(k).startswith("Pozostałe") else str(k)
    for k in others_rows["Kraj"]
]
oth_amount = [format_val(v) for v in others_rows["Przychod"]]
oth_colors = [
    "#607d8b" if str(k).startswith("Pozostałe") else "#00897b"
    for k in others_rows["Kraj"]
]

CHAR_W = 6.5
LABEL_H = 15.0
LBL_GAP = 4.0

def _name_halfwidth(name):
    return len(name) * CHAR_W / 2

eff_r, voff = [], []
for k in range(len(oth_r)):
    r = oth_r[k]
    hw = _name_halfwidth(oth_disp[k])
    top = r + LBL_GAP + LABEL_H
    eff_r.append(max((top + r) / 2, r, hw))
    voff.append((top - r) / 2)

uk_cx = uk_d / 2 + 20
uk_cy = plot_h / 2

rng = random.Random(7)
PAD = 6.0
pts = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in oth_r]
n = len(pts)
for _ in range(600):
    for i in range(n):
        for j in range(i + 1, n):
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            dist = math.hypot(dx, dy) or 1e-6
            need = eff_r[i] + eff_r[j] + PAD
            if dist < need:
                push = (need - dist) / 2
                ux, uy = dx / dist, dy / dist
                pts[i][0] -= ux * push
                pts[i][1] -= uy * push
                pts[j][0] += ux * push
                pts[j][1] += uy * push

    for p in pts:
        p[0] *= 0.985
        p[1] *= 0.985

mark_x = [p[0] for p in pts]
mark_y = [p[1] - voff[k] for k, p in enumerate(pts)]

group_left = min(mark_x[k] - oth_r[k] for k in range(n))
group_cy = sum(mark_y) / n
GAP = 70
shift_x = (uk_cx + uk_d / 2 + GAP) - group_left
shift_y = uk_cy - group_cy
other_x = [mark_x[k] + shift_x for k in range(n)]
other_y = [mark_y[k] + shift_y for k in range(n)]

hw = [_name_halfwidth(oth_disp[k]) for k in range(n)]
content_left = uk_cx - uk_d / 2
content_right = max(other_x[k] + max(oth_r[k], hw[k]) for k in range(n))
center_shift = (plot_w - (content_right - content_left)) / 2 - content_left
uk_cx += center_shift
other_x = [x + center_shift for x in other_x]
fp1_bubble = go.Figure()
fp1_bubble.add_trace(
    go.Scatter(
        x=[uk_cx],
        y=[uk_cy],
        mode="markers+text",
        text=[format_val(uk_row["Przychod"])],
        textposition="middle center",
        textfont=dict(color="white", size=14, family="Segoe UI", weight="bold"),
        marker=dict(
            size=[uk_d],
            sizemode="diameter",
            color="#1a237e",
            line=dict(color="white", width=1.5),
        ),
        customdata=[[uk_row["Kraj"], uk_row["Przychod"]]],
        hovertemplate="<b>Kraj: %{customdata[0]}</b><br>Pełny Przychód: £%{customdata[1]:,.2f}<extra></extra>",
        showlegend=False,
    )
)
fp1_bubble.add_trace(
    go.Scatter(
        x=other_x,
        y=other_y,
        mode="markers+text",
        text=oth_amount,
        textposition="middle center",
        textfont=dict(color="white", size=10, family="Segoe UI", weight="bold"),
        marker=dict(
            size=oth_d,
            sizemode="diameter",
            color=oth_colors,
            line=dict(color="white", width=1.5),
        ),
        customdata=list(zip(others_rows["Kraj"], others_rows["Przychod"])),
        hovertemplate="<b>Kraj: %{customdata[0]}</b><br>Pełny Przychód: £%{customdata[1]:,.2f}<extra></extra>",
        showlegend=False,
    )
)
fp1_bubble.add_annotation(
    x=uk_cx,
    y=uk_cy + uk_d / 2,
    text=f"<b>{uk_row['Kraj']}</b>",
    showarrow=False,
    yanchor="bottom",
    yshift=4,
    font=dict(color="#1a237e", size=12, family="Segoe UI"),
)
for k in range(n):
    name_color = (
        "#607d8b"
        if str(others_rows["Kraj"].iloc[k]).startswith("Pozostałe")
        else "#00695c"
    )
    fp1_bubble.add_annotation(
        x=other_x[k],
        y=other_y[k] + oth_r[k],
        text=f"<b>{oth_disp[k]}</b>",
        showarrow=False,
        yanchor="bottom",
        yshift=3,
        font=dict(color=name_color, size=11, family="Segoe UI"),
    )
fp1_bubble.update_layout(
    title=f"Proporcja rynkowa: UK ({format_val(uk_revenue)}) vs Reszta Świata Łącznie ({format_val(others_revenue)})",
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, plot_w]),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, plot_h]),
    template=TEMPLATE,
    width=FIG_W,
    height=FIG_H,
    autosize=False,
    margin=MARGIN,
)
fp2_monthly = go.Figure(
    go.Scatter(
        x=monthly["YearMonth_str"].tolist(),
        y=monthly["Przychod"].tolist(),
        fill="tozeroy",
        fillcolor="rgba(63,81,181,0.25)",
        line=dict(color="#3f51b5", width=2),
        mode="lines+markers",
        marker=dict(size=6),
        hovertemplate="%{x}<br>Przychód: £%{y:,.0f}<extra></extra>",
    )
)
fp2_monthly.update_layout(
    xaxis_title="Miesiąc",
    yaxis_title="Przychód (GBP)",
    template=TEMPLATE,
    height=400,
    xaxis=dict(type="category"),
)
fp2_monthly.update_yaxes(tickprefix="£", tickformat=",.0f", tick0=200000, dtick=200000)

DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
DAY_PL = {
    "Monday": "Poniedziałek",
    "Tuesday": "Wtorek",
    "Wednesday": "Środa",
    "Thursday": "Czwartek",
    "Friday": "Piątek",
    "Saturday": "Sobota",
    "Sunday": "Niedziela",
}
hmap = df.groupby(["DayOfWeek", "Hour"])["Revenue"].sum().unstack(fill_value=0)
hmap = hmap.reindex(DAY_ORDER, fill_value=0)
hmap.index = [DAY_PL.get(d, d) for d in hmap.index]
fp3_heatmap = go.Figure(
    data=go.Heatmap(
        z=(hmap / 1_000).values,
        x=[f"{h}:00" for h in hmap.columns],
        y=hmap.index.tolist(),
        colorscale=[[0, "#ffffff"], [1, "#0d47a1"]],
        hovertemplate="Dzień: %{y}<br>Godzina: %{x}<br>Przychód: £%{z:.1f}k<extra></extra>",
    )
)
fp3_heatmap.update_layout(
    xaxis_title="Godzina dnia",
    yaxis_title="Dzień tygodnia",
    template=TEMPLATE,
    height=450,
)
top6 = by_country.head(6)["Kraj"].tolist()
order_vals = (
    df[df["Country"].isin(top6)]
    .groupby(["InvoiceNo", "Country"])["Revenue"]
    .sum()
    .reset_index()
    .rename(columns={"Country": "Kraj", "Revenue": "Wartosc"})
)
box_order = (
    order_vals.groupby("Kraj")["Wartosc"]
    .median()
    .sort_values(ascending=False)
    .index.tolist()
)

q1 = order_vals["Wartosc"].quantile(0.25)
q3 = order_vals["Wartosc"].quantile(0.75)
iqr = q3 - q1
limit_gorny = q3 + 1.5 * iqr
order_vals_clean = order_vals[order_vals["Wartosc"] <= limit_gorny]
fp4_box = go.Figure()
for country in box_order:
    country_vals = order_vals_clean[order_vals_clean["Kraj"] == country]["Wartosc"]
    fp4_box.add_trace(
        go.Box(
            y=country_vals.tolist(),
            name=country,
            boxpoints=False,
            hovertemplate="<b>%{x}</b><br>Mediana zamówienia: £%{y:,.0f}<extra></extra>",
        )
    )
fp4_box.update_layout(
    xaxis_title="Kraj",
    yaxis_title="Wartość zamówienia (GBP)",
    template=TEMPLATE,
    height=450,
)
fp4_box.update_yaxes(tickprefix="£", tickformat=",.0f")
_df2 = top5_countries.sort_values("Przychod_k")
fp_inter_countries5 = go.Figure(
    go.Bar(
        x=_df2["Przychod_k"].tolist(),
        y=_df2["Kraj"].tolist(),
        orientation="h",
        marker_color="#3f51b5",
        hovertemplate="<b>%{y}</b><br>Przychód: £%{x:.1f}k<extra></extra>",
    )
)
fp_inter_countries5.update_layout(
    xaxis_title="Przychód (tys. GBP)", template=TEMPLATE, height=400
)
fp_inter_countries5.update_xaxes(tickprefix="£", ticksuffix="k", tickformat=".0f")
fp_uk_vs_rest = go.Figure()
fp_uk_vs_rest.add_trace(
    go.Bar(
        x=monthly_uk_rest["YearMonth_str"],
        y=monthly_uk_rest["United Kingdom"],
        name="United Kingdom",
        marker_color="#1a237e",
    )
)
fp_uk_vs_rest.add_trace(
    go.Bar(
        x=monthly_uk_rest["YearMonth_str"],
        y=monthly_uk_rest["Reszta Świata"],
        name="Reszta Świata",
        marker_color="#00897b",
    )
)
fp_uk_vs_rest.update_layout(
    barmode="group",
    xaxis_title="Miesiąc",
    yaxis_title="Przychód (GBP)",
    template=TEMPLATE,
    height=400,
    xaxis=dict(type="category"),
)
fp_uk_vs_rest.update_yaxes(tickprefix="£", tickformat=",.0f")
fp_top_customers = go.Figure(
    go.Bar(
        x=top_customers["CustomerID"],
        y=top_customers["Revenue"],
        marker_color="#8e24aa",
        hovertemplate="ID Klienta: %{x}<br>Wartość: £%{y:,.2f}<extra></extra>",
    )
)
fp_top_customers.update_layout(
    xaxis_title="ID Klienta",
    yaxis_title="Suma zakupów (GBP)",
    template=TEMPLATE,
    height=400,
    xaxis=dict(type="category"),
)
fp_top_customers.update_yaxes(tickprefix="£", tickformat=",.0f")
fp_hourly_qty = go.Figure(
    go.Scatter(
        x=hourly_qty["Hour"],
        y=hourly_qty["Quantity"],
        mode="lines+markers",
        line=dict(color="#e65100", width=3),
        hovertemplate="Godzina: %{x}:00<br>Ilość sztuk: %{y:,}<extra></extra>",
    )
)
fp_hourly_qty.update_layout(
    xaxis_title="Godzina transakcji",
    yaxis_title="Liczba sprzedanych sztuk",
    template=TEMPLATE,
    height=400,
    xaxis=dict(tickmode="linear"),
)
fp_customer_segments = go.Figure(
    go.Bar(
        x=spending_intervals["Przedzial"],
        y=spending_intervals["Liczba_Klientow"],
        marker_color="#0288d1",
        textposition="auto",
        hovertemplate="Przedział: %{x}<br>Liczba klientów: %{y:,}<extra></extra>",
    )
)
fp_customer_segments.update_layout(
    xaxis_title="Przedział całkowitych wydatków (GBP)",
    yaxis_title="Liczba unikalnych klientów",
    template=TEMPLATE,
    height=400,
)
fp_product_diff = go.Figure(
    go.Bar(
        x=prod_diff_df["Diff"],
        y=prod_diff_df["Produkt"],
        orientation="h",
        marker_color=["#00897b" if d < 0 else "#1a237e" for d in prod_diff_df["Diff"]],
        hovertemplate="<b>%{y}</b><br>Różnica udziału: %{x:.3f} p.p.<extra></extra>",
    )
)
fp_product_diff.update_layout(
    title="Profilowanie asortymentu: Produkty specyficzne dla rynków zagranicznych. (<span style='color:#00897b'>Reszta Świata</span>) vs <span style='color:#1a237e'>Wielka Brytania</span>",
    xaxis_title="Różnica udziału w wolumenie rynku (Różnica w Punktach Procentowych)",
    yaxis_title="Produkt",
    template=TEMPLATE,
    height=600,
)

prod_plot = top_products.iloc[::-1]
fp_top_products = go.Figure()
fp_top_products.add_trace(
    go.Bar(
        y=prod_plot["Produkt"],
        x=prod_plot["Sztuki"],
        name="Liczba sztuk",
        orientation="h",
        marker_color="#26a69a",
        hovertemplate="<b>%{y}</b><br>Sprzedane sztuki: %{x:,}<extra></extra>",
    )
)
fp_top_products.add_trace(
    go.Scatter(
        y=prod_plot["Produkt"],
        x=prod_plot["Przychod"],
        name="Przychód",
        xaxis="x2",
        mode="markers+lines",
        line=dict(color="#1a237e", width=2),
        marker=dict(size=9),
        hovertemplate="<b>%{y}</b><br>Przychód: £%{x:,.0f}<extra></extra>",
    )
)
rev_upper = math.ceil(top_products["Przychod"].max() / 20000) * 20000
fp_top_products.update_layout(
    title=dict(
        text="Top 12 produktów: wolumen sprzedaży vs generowany przychód",
        y=0.97,
        yanchor="top",
    ),
    xaxis=dict(
        title=dict(text="Liczba sprzedanych sztuk", font=dict(color="#26a69a")),
        tickfont=dict(color="#26a69a"),
    ),
    xaxis2=dict(
        title=dict(text="Przychód (GBP)", font=dict(color="#1a237e")),
        tickfont=dict(color="#1a237e"),
        tickprefix="£",
        tickformat=",.0f",
        overlaying="x",
        side="top",
        showgrid=False,
        range=[0, rev_upper],
        tick0=0,
        dtick=20000,
    ),
    yaxis=dict(title="Produkt"),
    legend=dict(orientation="h", yanchor="bottom", y=1.18, xanchor="right", x=1),
    template=TEMPLATE,
    height=560,
    margin=dict(t=150),
)

all_charts = [
    fp1_bubble,
    fp2_monthly,
    fp3_heatmap,
    fp4_box,
    fp_inter_countries5,
    fp_uk_vs_rest,
    fp_top_customers,
    fp_hourly_qty,
    fp_customer_segments,
    fp_product_diff,
    fp_top_products,
    fp_pareto,
]
for chart in all_charts:
    chart.update_xaxes(tickangle=0, automargin=True, overwrite=True)
    chart.update_yaxes(tickangle=0, automargin=True, overwrite=True)

print("Kompilacja raportu HTML...")
with rc.ReportCreator(
    title="Analiza sprzedaży e-commerce",
    description=f"Źródło danych: UCI Machine Learning Repository  ·  Rynek UK, 2010-2011  ·  {n_orders:,} zamówień  ·  {n_customers:,} klientów",
    footer="Skrypt wygenerowany automatycznie za pomocą pakietu report-creator  ·  Autorzy: K. Kot, W. Górecki",
) as report:
    view = rc.Block(
        rc.Group(
            rc.Metric(
                heading="Łączny przychód", value=f"£{total_rev / 1_000_000:.2f}M"
            ),
            rc.Metric(heading="Liczba zamówień", value=f"{n_orders:,}"),
            rc.Metric(heading="Unikalni klienci", value=f"{n_customers:,}"),
            rc.Metric(heading="Obsługiwane kraje", value=str(n_countries)),
            label="Kluczowe wskaźniki efektywności (KPI)",
        ),
        rc.Separator(),
        rc.Heading("Cel i zakres analizy", level=2),
        rc.Markdown(
            f"Zbiór danych **Online Retail** (UCI ML Repository) zawiera transakcje brytyjskiego sklepu e-commerce z lat 2010–2011. Analiza obejmuje {n_orders:,} zamówień od {n_customers:,} klientów z {n_countries} krajów. Celem jest identyfikacja wzorców sprzedaży, sezonowości oraz kluczowych rynków zbytu."
        ),
        rc.Heading("Struktura geograficzna sprzedaży", level=2),
        rc.Markdown(
            "Wizualizacja proporcji sprzedaży rodzimej (UK) na tle rynków międzynarodowych."
        ),
        rc.Widget(
            StaticPlotlyWidget(fp1_bubble),
            label="Globalna struktura przychodów (UK vs Pozostałe Kraje)",
        ),
        rc.Widget(
            StaticPlotlyWidget(fp_inter_countries5),
            label="Top 5 rynków zagranicznych wg generowanego przychodu",
        ),
        rc.Widget(
            StaticPlotlyWidget(fp_product_diff),
            label="Analiza preferencji produktowych: Produkty charakterystyczne rynkowo (Różnica w p.p. udziału wolumenu)",
        ),
        rc.Separator(),
        rc.Heading("Analiza asortymentu (bestsellery)", level=2),
        rc.Markdown(
            "Zestawienie najlepiej sprzedających się produktów: liczba sprzedanych sztuk w porównaniu z generowanym przychodem."
        ),
        rc.Widget(
            StaticPlotlyWidget(fp_top_products),
            label="Top 12 produktów: wolumen sprzedaży (sztuki) vs generowany przychód",
        ),
        rc.Separator(),
        rc.Heading("Weryfikacja hipotezy biznesowej: Zasada Pareto (80/20)", level=2),
        rc.Markdown(
            f"Analiza koncentracji struktury asortymentowej pozwala ocenić stopień dywersyfikacji przychodów. W badanym portfolio produktowym e-sklepu **top 20% asortymentu odpowiada za {rev_at_20_pct_prod:.1f}% łącznego przychodu**. Wynik ten potwierdza silną obecność rynkowej reguły Pareto – relatywnie wąski trzon oferty generuje lwią część całości obrotu przedsiębiorstwa."
        ),
        rc.Widget(
            StaticPlotlyWidget(fp_pareto),
            label="Krzywa Lorenza / Wykres koncentracji przychodu Pareto",
        ),
        rc.Separator(),
        rc.Heading("Sezonowość i dynamika przychodów", level=2),
        rc.Markdown(
            "Porównanie ogólnego trendu czasowego z uwzględnieniem podziału na rynki krajowe i zagraniczne."
        ),
        rc.Widget(
            StaticPlotlyWidget(fp2_monthly),
            label="Miesięczny przychód całkowity sklepu",
        ),
        rc.Widget(
            StaticPlotlyWidget(fp_uk_vs_rest),
            label="Miesięczny przychód: Wielka Brytania w zestawieniu z resztą świata",
        ),
        rc.Separator(),
        rc.Heading("Wzorce behawioralne klientów oraz analizy dedykowane", level=2),
        rc.Markdown(
            "Identyfikacja szczytów aktywności, rozkładów wartości koszyków zakupowych oraz kluczowych dla biznesu odbiorców."
        ),
        rc.Widget(
            StaticPlotlyWidget(fp3_heatmap),
            label="Rozkład wartości sprzedaży według dnia tygodnia i godziny (Skala niebieska)",
        ),
        rc.Widget(
            StaticPlotlyWidget(fp4_box),
            label="Rozkład wartości pojedynczych zamówień dla top krajów",
        ),
        rc.Group(
            rc.Widget(
                StaticPlotlyWidget(fp_top_customers),
                label="Top 10 Klientów sklepu według łącznej sumy zakupów (Analiza Lojalności)",
            ),
            rc.Widget(
                StaticPlotlyWidget(fp_customer_segments),
                label="Segmentacja bazy odbiorców: Liczba klientów w przedziałach wartości zakupów",
            ),
            rc.Widget(
                StaticPlotlyWidget(fp_hourly_qty),
                label="Całkowity wolumen sprzedanych produktów według godzin transakcji",
            ),
        ),
    )
    out_filename = "P_02_Kot_Gorecki.html"
    report.save(view, out_filename)
    
print(f"Raport został pomyślnie zapisany w pliku: {out_filename}")
