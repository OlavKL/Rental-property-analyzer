import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Verdiutvikling", layout="wide")

st.title("Verdiutvikling")
st.write("Se hvordan boligverdi, restgjeld og egenkapital utvikler seg over tid – og hvordan gearing påvirker avkastningen på egenkapitalen.")


# -------------------------
# Hjelpefunksjoner
# -------------------------
def format_nok(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,.0f} kr".replace(",", " ")


def annuity_monthly_payment(principal: float, annual_rate_percent: float, years: int) -> float:
    months = years * 12
    monthly_rate = annual_rate_percent / 100 / 12

    if principal <= 0 or months <= 0:
        return 0.0

    if monthly_rate == 0:
        return principal / months

    return principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)


def annuity_schedule(principal: float, annual_rate_percent: float, years: int) -> pd.DataFrame:
    months = years * 12
    monthly_rate = annual_rate_percent / 100 / 12
    payment = annuity_monthly_payment(principal, annual_rate_percent, years)

    balance = principal
    rows = []

    for month in range(1, months + 1):
        interest = balance * monthly_rate
        principal_payment = payment - interest

        if month == months:
            principal_payment = balance
            payment = principal_payment + interest

        balance -= principal_payment
        balance = max(balance, 0)

        rows.append({
            "Måned": month,
            "Restgjeld": balance
        })

    return pd.DataFrame(rows)


def serial_schedule(principal: float, annual_rate_percent: float, years: int) -> pd.DataFrame:
    months = years * 12
    monthly_rate = annual_rate_percent / 100 / 12

    if principal <= 0 or months <= 0:
        return pd.DataFrame(columns=["Måned", "Restgjeld"])

    monthly_principal = principal / months
    balance = principal
    rows = []

    for month in range(1, months + 1):
        if month == months:
            principal_payment = balance
        else:
            principal_payment = monthly_principal

        balance -= principal_payment
        balance = max(balance, 0)

        rows.append({
            "Måned": month,
            "Restgjeld": balance
        })

    return pd.DataFrame(rows)


# -------------------------
# Sidebar / input
# -------------------------
st.sidebar.header("Inndata")

purchase_price = st.sidebar.number_input(
    "Kjøpspris",
    min_value=0,
    value=3_250_000,
    step=50_000,
)

equity_amount = st.sidebar.number_input(
    "Egenkapital ved kjøp",
    min_value=0,
    value=552_500,
    step=10_000,
)

loan_amount = st.sidebar.number_input(
    "Lånebeløp",
    min_value=0,
    value=2_697_500,
    step=50_000,
)

loan_type = st.sidebar.selectbox(
    "Lånetype",
    ["Annuitetslån", "Serielån"],
)

interest_rate = st.sidebar.number_input(
    "Nominell rente (%)",
    min_value=0.0,
    max_value=20.0,
    value=5.5,
    step=0.1,
)

repayment_years = st.sidebar.number_input(
    "Nedbetalingstid (år)",
    min_value=1,
    max_value=40,
    value=30,
    step=1,
)

annual_growth = st.sidebar.number_input(
    "Forventet årlig verdivekst (%)",
    min_value=-10.0,
    max_value=20.0,
    value=4.0,
    step=0.1,
)

analysis_years = st.sidebar.number_input(
    "Analyseperiode (år)",
    min_value=1,
    max_value=40,
    value=30,
    step=1,
)


# -------------------------
# Låneskjema
# -------------------------
if loan_type == "Annuitetslån":
    loan_df = annuity_schedule(loan_amount, interest_rate, repayment_years)
else:
    loan_df = serial_schedule(loan_amount, interest_rate, repayment_years)

loan_df["År"] = (loan_df["Måned"] / 12)

# Hent restgjeld ved slutten av hvert år
year_rows = []
for year in range(0, analysis_years + 1):
    if year == 0:
        remaining_debt = loan_amount
    else:
        month_index = min(year * 12, len(loan_df))
        if month_index == 0:
            remaining_debt = loan_amount
        elif month_index <= len(loan_df):
            remaining_debt = loan_df.iloc[month_index - 1]["Restgjeld"]
        else:
            remaining_debt = 0.0

    property_value = purchase_price * ((1 + annual_growth / 100) ** year)
    equity_value = property_value - remaining_debt
    equity_gain = equity_value - equity_amount

    equity_return_percent = (equity_gain / equity_amount * 100) if equity_amount > 0 else 0.0
    property_return_percent = ((property_value - purchase_price) / purchase_price * 100) if purchase_price > 0 else 0.0

    gearing_multiple = (equity_return_percent / property_return_percent) if property_return_percent != 0 else 0.0

    year_rows.append({
        "År": year,
        "Boligverdi": property_value,
        "Restgjeld": remaining_debt,
        "Egenkapital": equity_value,
        "Egenkapitalgevinst": equity_gain,
        "Avkastning bolig (%)": property_return_percent,
        "Avkastning på EK (%)": equity_return_percent,
        "Gearing-effekt (x)": gearing_multiple
    })

result_df = pd.DataFrame(year_rows)


# -------------------------
# Valgt år / snapshot
# -------------------------
selected_year = min(analysis_years, repayment_years)
selected_row = result_df[result_df["År"] == selected_year].iloc[0]

property_value_selected = selected_row["Boligverdi"]
remaining_debt_selected = selected_row["Restgjeld"]
equity_selected = selected_row["Egenkapital"]
equity_gain_selected = selected_row["Egenkapitalgevinst"]
equity_return_selected = selected_row["Avkastning på EK (%)"]
property_return_selected = selected_row["Avkastning bolig (%)"]
gearing_selected = selected_row["Gearing-effekt (x)"]


# -------------------------
# Toppkort
# -------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Kjøpspris", format_nok(purchase_price))

with col2:
    st.metric(f"Boligverdi etter {selected_year} år", format_nok(property_value_selected))

with col3:
    st.metric(f"Restgjeld etter {selected_year} år", format_nok(remaining_debt_selected))

with col4:
    st.metric(f"Egenkapital etter {selected_year} år", format_nok(equity_selected))

st.divider()


# -------------------------
# Oppsummering
# -------------------------
st.subheader("Oppsummering")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.metric("Egenkapital ved kjøp", format_nok(equity_amount))
    st.metric("Egenkapitalgevinst", format_nok(equity_gain_selected))

with col_b:
    st.metric("Boligens verdiendring", f"{property_return_selected:.1f} %")
    st.metric("Avkastning på egenkapital", f"{equity_return_selected:.1f} %")

with col_c:
    st.metric("Gearing-effekt", f"{gearing_selected:.2f}x")
    st.caption("Viser hvor mange ganger høyere EK-avkastningen er enn selve boligprisveksten i prosent.")

if property_return_selected > 0 and equity_return_selected > property_return_selected:
    st.success(
        f"Med {annual_growth:.1f} % årlig verdivekst stiger boligen i verdi, og fordi deler av kjøpet er finansiert med lån, blir avkastningen på egenkapitalen høyere enn selve prisveksten på boligen."
    )
elif property_return_selected < 0:
    st.warning(
        "Negativ verdiutvikling kan slå hardere ut på egenkapitalen når du bruker belåning. Gearing virker begge veier."
    )

st.divider()


# -------------------------
# Graf: verdi, gjeld og EK
# -------------------------
st.subheader("Boligverdi, restgjeld og egenkapital over tid")

fig1, ax1 = plt.subplots(figsize=(11, 5.5))

ax1.plot(result_df["År"], result_df["Boligverdi"], label="Boligverdi", linewidth=2)
ax1.plot(result_df["År"], result_df["Restgjeld"], label="Restgjeld", linewidth=2)
ax1.plot(result_df["År"], result_df["Egenkapital"], label="Egenkapital", linewidth=2)

ax1.set_xlabel("År")
ax1.set_ylabel("Beløp (kr)")
ax1.set_title("Utvikling i boligverdi, restgjeld og egenkapital")
ax1.set_xlim(0, analysis_years)
ax1.set_xticks(range(0, analysis_years + 1, 5 if analysis_years >= 10 else 1))
ax1.grid(True, linestyle="--", alpha=0.5)
ax1.legend()
ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)

st.pyplot(fig1)

st.divider()


# -------------------------
# Graf: avkastning på bolig vs EK
# -------------------------
st.subheader("Gearing-effekt over tid")

fig2, ax2 = plt.subplots(figsize=(11, 5.5))

ax2.plot(result_df["År"], result_df["Avkastning bolig (%)"], label="Boligens verdiendring (%)", linewidth=2)
ax2.plot(result_df["År"], result_df["Avkastning på EK (%)"], label="Avkastning på egenkapital (%)", linewidth=2)

ax2.set_xlabel("År")
ax2.set_ylabel("Avkastning (%)")
ax2.set_title("Hvordan belåning forsterker avkastning på egenkapital")
ax2.set_xlim(0, analysis_years)
ax2.set_xticks(range(0, analysis_years + 1, 5 if analysis_years >= 10 else 1))
ax2.grid(True, linestyle="--", alpha=0.5)
ax2.legend()
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)

st.pyplot(fig2)

st.divider()


# -------------------------
# Tabell
# -------------------------
st.subheader("År-for-år-tabell")

table_df = result_df.copy()

for col in ["Boligverdi", "Restgjeld", "Egenkapital", "Egenkapitalgevinst"]:
    table_df[col] = table_df[col].apply(format_nok)

for col in ["Avkastning bolig (%)", "Avkastning på EK (%)"]:
    table_df[col] = table_df[col].apply(lambda x: f"{x:.1f} %")

table_df["Gearing-effekt (x)"] = table_df["Gearing-effekt (x)"].apply(lambda x: f"{x:.2f}x" if x != 0 else "-")

st.dataframe(table_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Forklaring
# -------------------------
with st.expander("Hva betyr gearing-effekt?"):
    st.write(
        """
**Gearing** betyr at du bruker lån for å forsterke avkastningen på egenkapitalen din.

Eksempel:
- Bolig kjøpes for 3 250 000 kr
- Du går inn med 552 500 kr i egenkapital
- Resten finansieres med lån

Hvis boligen stiger i verdi, skjer verdiøkningen på **hele boligen**, ikke bare på egenkapitalen du skjøt inn.
Derfor kan en årlig verdiøkning på for eksempel 4 % gi en langt høyere prosentvis avkastning på egenkapitalen.

Men dette virker også motsatt vei:
- Faller boligverdien, kan egenkapitalen falle mye raskere
- Gearing øker derfor både oppside og nedside
"""
    )
