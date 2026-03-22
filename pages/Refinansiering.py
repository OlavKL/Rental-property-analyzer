import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Finansieringskalkulator", layout="wide")

st.title("Finansieringskalkulator")
st.write(
    "Beregn lånekapasitet ut fra inntekt, gjeld og egenkapital, og se mulig refinansiering av bolig etter x antall år."
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


def to_annual_income(amount: float, period: str) -> float:
    if period == "Månedlig":
        return amount * 12
    return amount


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


def get_remaining_debt(loan_df: pd.DataFrame, year: int, start_debt: float) -> float:
    if year == 0:
        return start_debt
    month = year * 12
    if month <= len(loan_df):
        return float(loan_df.iloc[month - 1]["Restgjeld"])
    return 0.0


# -------------------------
# Sidebar: Inntekter
# -------------------------
st.sidebar.header("Inntekter")

if "incomes" not in st.session_state:
    st.session_state.incomes = [
        {"name": "Inntekt 1", "amount": 300_000, "period": "Årlig"}
    ]

income_rows = []
total_annual_income = 0.0

remove_income_idx = None

for i, income in enumerate(st.session_state.incomes):
    st.sidebar.markdown(f"**Inntekt {i+1}**")

    income["name"] = st.sidebar.text_input(
        f"Navn {i}",
        value=income["name"],
        key=f"income_name_{i}",
        label_visibility="collapsed"
    )

    income["amount"] = st.sidebar.number_input(
        f"Beløp {i}",
        min_value=0,
        value=int(income["amount"]),
        step=10_000,
        key=f"income_amount_{i}",
        label_visibility="collapsed"
    )

    income["period"] = st.sidebar.radio(
        f"Periode {i}",
        ["Årlig", "Månedlig"],
        horizontal=True,
        index=0 if income["period"] == "Årlig" else 1,
        key=f"income_period_{i}",
        label_visibility="collapsed"
    )

    col_a, col_b = st.sidebar.columns([1, 1])
    with col_a:
        if st.button(f"Fjern denne", key=f"remove_income_{i}"):
            remove_income_idx = i
    with col_b:
        st.write("")

    annualized = to_annual_income(income["amount"], income["period"])
    total_annual_income += annualized

    income_rows.append({
        "Navn": income["name"],
        "Registrert beløp": format_nok(income["amount"]),
        "Periode": income["period"],
        "Årsinntekt": format_nok(annualized),
    })

    st.sidebar.markdown("---")

if remove_income_idx is not None and len(st.session_state.incomes) > 1:
    st.session_state.incomes.pop(remove_income_idx)
    st.rerun()

if st.sidebar.button("Legg til inntekt"):
    st.session_state.incomes.append(
        {"name": f"Inntekt {len(st.session_state.incomes)+1}", "amount": 100_000, "period": "Årlig"}
    )
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Gjeld")

other_debt = st.sidebar.number_input(
    "Annen gjeld (studielån, billån, kreditt, osv.)",
    min_value=0,
    value=0,
    step=50_000,
)

equity = st.sidebar.number_input(
    "Tilgjengelig egenkapital",
    min_value=0,
    value=500_000,
    step=50_000,
)



st.sidebar.divider()
st.sidebar.header("Bolig / eksisterende lån")

property_value_today = st.sidebar.number_input(
    "Boligens verdi i dag",
    min_value=0,
    value=3_250_000,
    step=50_000,
)

current_loan_amount = st.sidebar.number_input(
    "Lån på boligen i dag",
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
    "Nedbetalingstid (år)",
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

refinance_ltv_percent = st.sidebar.slider(
    "Maks belåningsgrad ved refinansiering (%)",
    min_value=0,
    max_value=100,
    value=85,
    step=1,
)

st.sidebar.divider()
st.sidebar.header("Verdiutvikling")

growth_mode = st.sidebar.radio(
    "Velg metode for verdiutvikling",
    ["Fast prosent", "Slingring / scenario"],
)

if growth_mode == "Fast prosent":
    annual_growth_percent = st.sidebar.number_input(
        "Årlig verdiutvikling (%)",
        min_value=-10.0,
        max_value=20.0,
        value=3.0,
        step=0.1,
    )
    growth_low = annual_growth_percent
    growth_base = annual_growth_percent
    growth_high = annual_growth_percent
else:
    growth_low = st.sidebar.number_input(
        "Lavt scenario (%)",
        min_value=-15.0,
        max_value=20.0,
        value=1.0,
        step=0.1,
    )
    growth_base = st.sidebar.number_input(
        "Base scenario (%)",
        min_value=-15.0,
        max_value=20.0,
        value=3.0,
        step=0.1,
    )
    growth_high = st.sidebar.number_input(
        "Høyt scenario (%)",
        min_value=-15.0,
        max_value=20.0,
        value=5.0,
        step=0.1,
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
income_based_max_loan = max(0.0, total_annual_income * income_multiple - other_debt)
total_buying_power = income_based_max_loan + equity

if loan_type == "Annuitetslån":
    loan_df = annuity_schedule(current_loan_amount, interest_rate, repayment_years)
else:
    loan_df = serial_schedule(current_loan_amount, interest_rate, repayment_years)

loan_df["År"] = loan_df["Måned"] / 12

remaining_debt = get_remaining_debt(loan_df, years_forward, current_loan_amount)

property_values_low = property_value_projection(property_value_today, growth_low, years_forward)
property_values_base = property_value_projection(property_value_today, growth_base, years_forward)
property_values_high = property_value_projection(property_value_today, growth_high, years_forward)

future_value_low = property_values_low[-1]
future_value_base = property_values_base[-1]
future_value_high = property_values_high[-1]

max_new_loan_low = future_value_low * (refinance_ltv_percent / 100)
max_new_loan_base = future_value_base * (refinance_ltv_percent / 100)
max_new_loan_high = future_value_high * (refinance_ltv_percent / 100)

refinance_room_low = max(0, max_new_loan_low - remaining_debt)
refinance_room_base = max(0, max_new_loan_base - remaining_debt)
refinance_room_high = max(0, max_new_loan_high - remaining_debt)

releasable_after_buffer_low = max(0, refinance_room_low - buffer_amount)
releasable_after_buffer_base = max(0, refinance_room_base - buffer_amount)
releasable_after_buffer_high = max(0, refinance_room_high - buffer_amount)

projected_income_headroom_low = max(0, income_based_max_loan - max_new_loan_low)
projected_income_headroom_base = max(0, income_based_max_loan - max_new_loan_base)
projected_income_headroom_high = max(0, income_based_max_loan - max_new_loan_high)

actual_refinance_capacity_low = min(income_based_max_loan, max_new_loan_low) - remaining_debt
actual_refinance_capacity_base = min(income_based_max_loan, max_new_loan_base) - remaining_debt
actual_refinance_capacity_high = min(income_based_max_loan, max_new_loan_high) - remaining_debt

actual_refinance_capacity_low = max(0, actual_refinance_capacity_low)
actual_refinance_capacity_base = max(0, actual_refinance_capacity_base)
actual_refinance_capacity_high = max(0, actual_refinance_capacity_high)

actual_refinance_after_buffer_low = max(0, actual_refinance_capacity_low - buffer_amount)
actual_refinance_after_buffer_base = max(0, actual_refinance_capacity_base - buffer_amount)
actual_refinance_after_buffer_high = max(0, actual_refinance_capacity_high - buffer_amount)

current_ltv = (current_loan_amount / property_value_today * 100) if property_value_today > 0 else 0.0
future_ltv_base = (remaining_debt / future_value_base * 100) if future_value_base > 0 else 0.0

if not loan_df.empty:
    first_payment = loan_df.iloc[0]["Terminbeløp"]
else:
    first_payment = 0.0


# -------------------------
# Nøkkeltall
# -------------------------
st.subheader("Nøkkeltall")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Samlet årsinntekt", format_mill(total_annual_income), help=format_nok(total_annual_income))

with col2:
    st.metric("Annen gjeld", format_mill(other_debt), help=format_nok(other_debt))

with col3:
    st.metric("Lånekapasitet før eiendom", format_mill(income_based_max_loan))

st.divider()


# -------------------------
# Inntektsoversikt
# -------------------------
st.subheader("Inntektsoversikt")

income_df = pd.DataFrame(income_rows)
st.dataframe(income_df, use_container_width=True, hide_index=True)

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
                "Samlet årsinntekt",
                "Valgt inntektsmultippel",
                "Annen gjeld",
                "Prosjektert lånekapasitet",
                "Egenkapital",
                "Total kjøpekraft",
                "Boligverdi i dag",
                "Boliglån i dag",
                "Lånetype",
                "Nominell rente",
                "Nedbetalingstid",
                "Første terminbeløp",
                "Dagens belåningsgrad",
            ],
            "Verdi": [
                format_nok(total_annual_income),
                f"{income_multiple:.1f}x",
                format_nok(other_debt),
                format_nok(income_based_max_loan),
                format_nok(equity),
                format_nok(total_buying_power),
                format_nok(property_value_today),
                format_nok(current_loan_amount),
                loan_type,
                f"{interest_rate:.2f} %",
                f"{repayment_years} år",
                format_nok(first_payment),
                f"{current_ltv:.1f} %",
            ]
        }
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

with summary_right:
    refi_df = pd.DataFrame(
        {
            "Scenario": ["Lav", "Base", "Høy"],
            f"Boligverdi etter {years_forward} år": [
                format_nok(future_value_low),
                format_nok(future_value_base),
                format_nok(future_value_high),
            ],
            f"Restgjeld etter {years_forward} år": [
                format_nok(remaining_debt),
                format_nok(remaining_debt),
                format_nok(remaining_debt),
            ],
            "Maks lån ved LTV-grense": [
                format_nok(max_new_loan_low),
                format_nok(max_new_loan_base),
                format_nok(max_new_loan_high),
            ],
            "Faktisk mulig refinansiering": [
                format_nok(actual_refinance_capacity_low),
                format_nok(actual_refinance_capacity_base),
                format_nok(actual_refinance_capacity_high),
            ],
            "Etter buffer": [
                format_nok(actual_refinance_after_buffer_low),
                format_nok(actual_refinance_after_buffer_base),
                format_nok(actual_refinance_after_buffer_high),
            ],
        }
    )
    st.dataframe(refi_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Beskjed / tolkning
# -------------------------
if actual_refinance_capacity_base > 0:
    st.success(
        f"Basert på base scenario kan du potensielt refinansiere omtrent {format_nok(actual_refinance_capacity_base)} etter {years_forward} år."
    )
else:
    st.warning(
        "Basert på base scenario ser det ikke ut til at du har rom for ekstra refinansiering ennå."
    )

st.markdown(
    f"""
- **Samlet årsinntekt:** {format_nok(total_annual_income)}
- **Prosjektert lånekapasitet:** {format_nok(income_based_max_loan)}
- **Tilgjengelig egenkapital:** {format_nok(equity)}
- **Total kjøpekraft:** {format_nok(total_buying_power)}
- **Estimert restgjeld etter {years_forward} år:** {format_nok(remaining_debt)}
- **Mulig refinansiering i base scenario:** {format_nok(actual_refinance_capacity_base)}
- **Mulig refinansiering etter buffer:** {format_nok(actual_refinance_after_buffer_base)}
"""
)

st.divider()


# -------------------------
# Graf: verdi vs restgjeld
# -------------------------
st.subheader("Boligverdi vs. restgjeld over tid")

years_axis = list(range(0, years_forward + 1))
remaining_debt_by_year = [get_remaining_debt(loan_df, year, current_loan_amount) for year in years_axis]

fig, ax = plt.subplots(figsize=(11, 5.5))

ax.plot(years_axis, property_values_base, label="Boligverdi (base)", linewidth=2)
ax.plot(years_axis, remaining_debt_by_year, label="Restgjeld", linewidth=2)

if growth_mode == "Slingring / scenario":
    ax.plot(years_axis, property_values_low, label="Boligverdi (lav)", linestyle="--", linewidth=1.8)
    ax.plot(years_axis, property_values_high, label="Boligverdi (høy)", linestyle="--", linewidth=1.8)

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
st.subheader("År-for-år oversikt (base scenario)")

year_rows = []

for year in years_axis:
    property_value = property_values_base[year]
    debt = get_remaining_debt(loan_df, year, current_loan_amount)
    available_loan_ltv = property_value * (refinance_ltv_percent / 100)
    allowed_total_loan = min(income_based_max_loan, available_loan_ltv)
    refinance_room = max(0, allowed_total_loan - debt)
    equity_in_home = property_value - debt

    year_rows.append({
        "År": year,
        "Estimert boligverdi": format_nok(property_value),
        "Restgjeld": format_nok(debt),
        "Egenkapital i bolig": format_nok(equity_in_home),
        "Maks lån ved LTV": format_nok(available_loan_ltv),
        "Maks lån justert for inntekt": format_nok(allowed_total_loan),
        "Mulig refinansiering": format_nok(refinance_room),
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
**Samlet årsinntekt** = summen av alle inntekter, omregnet til årsbasis.

**Prosjektert lånekapasitet** = årsinntekt × valgt inntektsmultippel minus annen gjeld.

**Total kjøpekraft** = lånekapasitet + tilgjengelig egenkapital.

**Restgjeld** = hvor mye av boliglånet som gjenstår etter valgt antall år.

**Maks lån ved LTV** = hvor mye banken teoretisk kan tillate basert på valgt belåningsgrad av boligverdien.

**Maks lån justert for inntekt** = laveste av:
1. inntektsbasert lånekapasitet
2. maks lån basert på belåningsgrad

**Mulig refinansiering** = hvor mye mer lån du potensielt kan ta opp sammenlignet med restgjelden på det tidspunktet.

**Etter buffer** = mulig refinansiering minus ønsket buffer.
"""
    )
