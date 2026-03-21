import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Refinansieringskalkulator", layout="wide")

st.title("Refinansieringskalkulator")
st.write(
    "Beregn estimert boligverdi, restgjeld og hvor mye du potensielt kan refinansiere etter x antall år."
)


# -------------------------
# Hjelpefunksjoner
# -------------------------
def format_nok(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,.0f} kr".replace(",", " ")


def format_mill(value: float) -> str:
    if abs(value) >= 1_000_000:
        mill = value / 1_000_000
        return f"{mill:.3f}".rstrip("0").rstrip(".") + " mill"
    return format_nok(value)


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
            "Terminbeløp": payment,
            "Avdrag": principal_payment,
            "Renter": interest,
            "Restgjeld": balance
        })

    return pd.DataFrame(rows)


def serial_schedule(principal: float, annual_rate_percent: float, years: int) -> pd.DataFrame:
    months = years * 12
    monthly_rate = annual_rate_percent / 100 / 12

    if principal <= 0 or months <= 0:
        return pd.DataFrame(columns=["Måned", "Terminbeløp", "Avdrag", "Renter", "Restgjeld"])

    monthly_principal = principal / months
    balance = principal
    rows = []

    for month in range(1, months + 1):
        interest = balance * monthly_rate

        if month == months:
            principal_payment = balance
        else:
            principal_payment = monthly_principal

        payment = principal_payment + interest
        balance -= principal_payment
        balance = max(balance, 0)

        rows.append({
            "Måned": month,
            "Terminbeløp": payment,
            "Avdrag": principal_payment,
            "Renter": interest,
            "Restgjeld": balance
        })

    return pd.DataFrame(rows)


def property_value_projection(start_value: float, annual_growth_percent: float, years_forward: int) -> list[float]:
    values = []
    for year in range(0, years_forward + 1):
        future_value = start_value * ((1 + annual_growth_percent / 100) ** year)
        values.append(future_value)
    return values


# -------------------------
# Sidebar / input
# -------------------------
st.sidebar.header("Inndata")

purchase_price = st.sidebar.number_input(
    "Kjøpesum / dagens verdi",
    min_value=0,
    value=3_250_000,
    step=50_000,
)

loan_amount = st.sidebar.number_input(
    "Opprinnelig lånebeløp",
    min_value=0,
    value=2_700_000,
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
    "Opprinnelig nedbetalingstid (år)",
    min_value=1,
    max_value=40,
    value=30,
    step=1,
)

years_forward = st.sidebar.slider(
    "Hvor mange år frem?",
    min_value=1,
    max_value=30,
    value=5,
    step=1,
)

annual_growth_percent = st.sidebar.number_input(
    "Årlig verdiutvikling (%)",
    min_value=-10.0,
    max_value=20.0,
    value=3.0,
    step=0.1,
)

refinance_ltv_percent = st.sidebar.slider(
    "Maks belåningsgrad ved refinansiering (%)",
    min_value=0,
    max_value=100,
    value=85,
    step=1,
)

buffer_amount = st.sidebar.number_input(
    "Ønsket buffer (kr)",
    min_value=0,
    value=100_000,
    step=25_000,
)


# -------------------------
# Beregninger
# -------------------------
if loan_type == "Annuitetslån":
    loan_df = annuity_schedule(loan_amount, interest_rate, repayment_years)
else:
    loan_df = serial_schedule(loan_amount, interest_rate, repayment_years)

loan_df["År"] = loan_df["Måned"] / 12

selected_month = years_forward * 12
if selected_month <= len(loan_df):
    remaining_debt = loan_df.iloc[selected_month - 1]["Restgjeld"]
else:
    remaining_debt = 0.0

property_values = property_value_projection(purchase_price, annual_growth_percent, years_forward)
future_property_value = property_values[-1]

max_new_loan = future_property_value * (refinance_ltv_percent / 100)
potential_refinance_amount = max(0, max_new_loan - remaining_debt)
releasable_equity_after_buffer = max(0, potential_refinance_amount - buffer_amount)

current_ltv = (loan_amount / purchase_price * 100) if purchase_price > 0 else 0.0
future_ltv_before_refi = (remaining_debt / future_property_value * 100) if future_property_value > 0 else 0.0

if not loan_df.empty:
    first_payment = loan_df.iloc[0]["Terminbeløp"]
else:
    first_payment = 0.0


# -------------------------
# Nøkkeltall
# -------------------------
st.subheader("Nøkkeltall")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Dagens verdi",
        format_mill(purchase_price),
        help=format_nok(purchase_price)
    )

with col2:
    st.metric(
        f"Verdi etter {years_forward} år",
        format_mill(future_property_value),
        help=format_nok(future_property_value)
    )

with col3:
    st.metric(
        f"Restgjeld etter {years_forward} år",
        format_mill(remaining_debt),
        help=format_nok(remaining_debt)
    )

with col4:
    st.metric(
        "Mulig nytt maks lån",
        format_mill(max_new_loan),
        help=f"{refinance_ltv_percent} % av estimert boligverdi"
    )

with col5:
    st.metric(
        "Mulig refinansiering",
        format_mill(potential_refinance_amount),
        help="Estimert mulig økning i lån før buffer."
    )

st.divider()


# -------------------------
# Oppsummering
# -------------------------
st.subheader("Oppsummering")

summary_left, summary_right = st.columns([1, 1])

with summary_left:
    summary_df = pd.DataFrame(
        {
            "Post": [
                "Dagens verdi",
                "Opprinnelig lånebeløp",
                "Lånetype",
                "Rente",
                "Nedbetalingstid",
                "Første terminbeløp",
                "Dagens belåningsgrad",
                f"Estimert verdi etter {years_forward} år",
                f"Restgjeld etter {years_forward} år",
                f"Belåningsgrad etter {years_forward} år",
            ],
            "Verdi": [
                format_nok(purchase_price),
                format_nok(loan_amount),
                loan_type,
                f"{interest_rate:.2f} %",
                f"{repayment_years} år",
                format_nok(first_payment),
                f"{current_ltv:.1f} %",
                format_nok(future_property_value),
                format_nok(remaining_debt),
                f"{future_ltv_before_refi:.1f} %",
            ]
        }
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

with summary_right:
    refi_df = pd.DataFrame(
        {
            "Post": [
                "Maks belåningsgrad ved refinansiering",
                "Mulig nytt maks lån",
                "Mulig refinansierbart beløp",
                "Valgt buffer",
                "Frigjørbar EK etter buffer",
            ],
            "Verdi": [
                f"{refinance_ltv_percent:.0f} %",
                format_nok(max_new_loan),
                format_nok(potential_refinance_amount),
                format_nok(buffer_amount),
                format_nok(releasable_equity_after_buffer),
            ]
        }
    )
    st.dataframe(refi_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Beskjed / tolkning
# -------------------------
if potential_refinance_amount > 0:
    st.success(
        f"Basert på forutsetningene kan du potensielt øke lånet med omtrent {format_nok(potential_refinance_amount)} etter {years_forward} år."
    )
else:
    st.warning(
        "Basert på forutsetningene ser det ikke ut til at du har rom for ekstra refinansiering ennå."
    )

st.markdown(
    f"""
- **Estimert boligverdi etter {years_forward} år:** {format_nok(future_property_value)}
- **Restgjeld etter {years_forward} år:** {format_nok(remaining_debt)}
- **Mulig nytt maks lån ved {refinance_ltv_percent:.0f} % belåning:** {format_nok(max_new_loan)}
- **Mulig refinansierbart beløp:** {format_nok(potential_refinance_amount)}
- **Frigjørbar EK etter buffer på {format_nok(buffer_amount)}:** {format_nok(releasable_equity_after_buffer)}
"""
)

st.divider()


# -------------------------
# Graf: verdi vs restgjeld
# -------------------------
st.subheader("Boligverdi vs. restgjeld over tid")

years_axis = list(range(0, years_forward + 1))
remaining_debt_by_year = []

for year in years_axis:
    month = year * 12
    if month == 0:
        remaining_debt_by_year.append(loan_amount)
    elif month <= len(loan_df):
        remaining_debt_by_year.append(loan_df.iloc[month - 1]["Restgjeld"])
    else:
        remaining_debt_by_year.append(0.0)

fig, ax = plt.subplots(figsize=(11, 5.5))

ax.plot(years_axis, property_values, label="Estimert boligverdi", linewidth=2)
ax.plot(years_axis, remaining_debt_by_year, label="Restgjeld", linewidth=2)

ax.set_xlabel("År")
ax.set_ylabel("Beløp (kr)")
ax.set_title("Utvikling i boligverdi og restgjeld")
ax.set_xlim(0, years_forward)
ax.set_xticks(range(0, years_forward + 1, 1))
ax.grid(True, linestyle="--", alpha=0.5)

ax.legend()
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

st.pyplot(fig)

st.divider()


# -------------------------
# År-for-år tabell
# -------------------------
st.subheader("År-for-år oversikt")

year_rows = []

for year in years_axis:
    property_value = property_values[year]

    if year == 0:
        debt = loan_amount
    else:
        month = year * 12
        debt = loan_df.iloc[month - 1]["Restgjeld"] if month <= len(loan_df) else 0.0

    available_loan = property_value * (refinance_ltv_percent / 100)
    refinance_room = max(0, available_loan - debt)
    equity = property_value - debt

    year_rows.append({
        "År": year,
        "Estimert boligverdi": format_nok(property_value),
        "Restgjeld": format_nok(debt),
        "Egenkapital": format_nok(equity),
        "Maks lån ved refinansiering": format_nok(available_loan),
        "Mulig refinansierbart beløp": format_nok(refinance_room),
    })

year_df = pd.DataFrame(year_rows)
st.dataframe(year_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Forklaring
# -------------------------
with st.expander("Hva betyr tallene?"):
    st.write(
        """
**Estimert boligverdi** = dagens verdi fremskrevet med valgt årlig verdiutvikling.

**Restgjeld** = hvor mye av lånet som gjenstår etter valgt antall år, basert på valgt lånetype, rente og nedbetalingstid.

**Mulig nytt maks lån** = hvor mye banken teoretisk kan la deg låne ved valgt belåningsgrad på estimert boligverdi.

**Mulig refinansierbart beløp** = nytt maks lån minus restgjeld.

**Frigjørbar EK etter buffer** = refinansierbart beløp minus den bufferen du ønsker å holde igjen.
"""
    )
