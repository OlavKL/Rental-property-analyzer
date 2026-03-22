import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Finansieringskalkulator", layout="wide")

st.title("Finansieringskalkulator")
st.write(
    "Beregn lånekapasitet ut fra inntekt og gjeld, og se hvordan eiendom, verdistigning og leieinntekter kan påvirke fremtidig kapasitet."
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

        rows.append(
            {
                "Måned": month,
                "Terminbeløp": payment,
                "Avdrag": principal_payment,
                "Renter": interest,
                "Restgjeld": balance,
            }
        )

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

        rows.append(
            {
                "Måned": month,
                "Terminbeløp": payment,
                "Avdrag": principal_payment,
                "Renter": interest,
                "Restgjeld": balance,
            }
        )

    return pd.DataFrame(rows)


def get_remaining_debt(loan_df: pd.DataFrame, year: int, start_debt: float) -> float:
    if year == 0:
        return start_debt

    month = year * 12
    if month <= len(loan_df):
        return float(loan_df.iloc[month - 1]["Restgjeld"])
    return 0.0


def property_value_projection(start_value: float, annual_growth_percent: float, years_forward: int) -> list[float]:
    values = []
    for year in range(0, years_forward + 1):
        future_value = start_value * ((1 + annual_growth_percent / 100) ** year)
        values.append(future_value)
    return values


# -------------------------
# Session state
# -------------------------
if "incomes" not in st.session_state:
    st.session_state.incomes = [
        {"name": "Inntekt 1", "amount": 300_000, "period": "Årlig"}
    ]


# -------------------------
# Sidebar: Inntekter
# -------------------------
st.sidebar.header("Inntekter")

income_rows = []
total_annual_income = 0.0
remove_income_idx = None

for i, income in enumerate(st.session_state.incomes):
    st.sidebar.markdown(f"**Inntekt {i+1}**")

    income["name"] = st.sidebar.text_input(
        f"Navn på inntekt {i+1}",
        value=income["name"],
        key=f"income_name_{i}",
        label_visibility="collapsed",
    )

    income["amount"] = st.sidebar.number_input(
        f"Beløp for inntekt {i+1}",
        min_value=0,
        value=int(income["amount"]),
        step=10_000,
        key=f"income_amount_{i}",
        label_visibility="collapsed",
    )

    current_period_index = 0 if income["period"] == "Årlig" else 1
    income["period"] = st.sidebar.radio(
        f"Periode for inntekt {i+1}",
        ["Årlig", "Månedlig"],
        horizontal=True,
        index=current_period_index,
        key=f"income_period_{i}",
        label_visibility="collapsed",
    )

    if st.sidebar.button(f"Fjern denne", key=f"remove_income_{i}"):
        remove_income_idx = i

    annualized = to_annual_income(income["amount"], income["period"])
    total_annual_income += annualized

    income_rows.append(
        {
            "Navn": income["name"],
            "Registrert beløp": format_nok(income["amount"]),
            "Periode": income["period"],
            "Årsinntekt": format_nok(annualized),
        }
    )

    st.sidebar.markdown("---")

if remove_income_idx is not None and len(st.session_state.incomes) > 1:
    st.session_state.incomes.pop(remove_income_idx)
    st.rerun()

if st.sidebar.button("Legg til inntekt"):
    st.session_state.incomes.append(
        {
            "name": f"Inntekt {len(st.session_state.incomes) + 1}",
            "amount": 100_000,
            "period": "Årlig",
        }
    )
    st.rerun()


# -------------------------
# Sidebar: Gjeld / finansiering
# -------------------------
st.sidebar.header("Gjeld og finansiering")

other_debt = st.sidebar.number_input(
    "Annen gjeld (studielån, billån, kreditt, osv.)",
    min_value=0,
    value=0,
    step=50_000,
)

income_multiple = st.sidebar.number_input(
    "Inntektsmultippel",
    min_value=0.0,
    max_value=10.0,
    value=5.0,
    step=0.1,
)

income_based_max_loan = max(0.0, total_annual_income * income_multiple - other_debt)


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
# Eiendom / eksisterende lån
# -------------------------
st.subheader("Eiendom / eksisterende lån")

property_col1, property_col2 = st.columns(2)

with property_col1:
    property_value_today = st.number_input(
        "Kjøpspris / verdi i dag",
        min_value=0,
        value=3_250_000,
        step=50_000,
    )

    purchase_year = st.number_input(
        "Kjøpsår",
        min_value=1900,
        max_value=2100,
        value=2026,
        step=1,
    )

    current_loan_amount = st.number_input(
        "Lån på eiendommen",
        min_value=0,
        value=2_700_000,
        step=50_000,
    )

    loan_type = st.selectbox(
        "Lånetype",
        ["Annuitetslån", "Serielån"],
    )

with property_col2:
    interest_rate = st.number_input(
        "Nominell rente (%)",
        min_value=0.0,
        max_value=20.0,
        value=5.5,
        step=0.1,
    )

    repayment_years = st.number_input(
        "Nedbetalingstid (år)",
        min_value=1,
        max_value=40,
        value=30,
        step=1,
    )

    years_forward = st.slider(
        "Hvor mange år frem?",
        min_value=1,
        max_value=30,
        value=5,
        step=1,
    )

    refinance_ltv_percent = st.slider(
        "Maks belåningsgrad ved refinansiering (%)",
        min_value=0,
        max_value=100,
        value=85,
        step=1,
    )


st.markdown("### Verdiutvikling og leie")

growth_col1, growth_col2, growth_col3 = st.columns(3)

with growth_col1:
    annual_growth_percent = st.number_input(
        "Årlig verdistigning (%)",
        min_value=-10.0,
        max_value=20.0,
        value=3.0,
        step=0.1,
    )

with growth_col2:
    monthly_rent = st.number_input(
        "Månedlig leieinntekt",
        min_value=0,
        value=0,
        step=1_000,
    )

with growth_col3:
    rent_factor = st.number_input(
        "Leie × faktor",
        min_value=0,
        max_value=50,
        value=10,
        step=1,
        help="Konservativ banktilnærming kan være månedlig leie × 10",
    )


# -------------------------
# Beregninger
# -------------------------
if loan_type == "Annuitetslån":
    loan_df = annuity_schedule(current_loan_amount, interest_rate, repayment_years)
else:
    loan_df = serial_schedule(current_loan_amount, interest_rate, repayment_years)

remaining_debt = get_remaining_debt(loan_df, years_forward, current_loan_amount)

future_property_value = property_value_today * ((1 + annual_growth_percent / 100) ** years_forward)
max_loan_on_property = future_property_value * (refinance_ltv_percent / 100)
extractable_equity = max(0.0, max_loan_on_property - remaining_debt)

rent_based_extra_capacity = monthly_rent * rent_factor
total_loan_capacity_after_rent = income_based_max_loan + rent_based_extra_capacity

future_available_loan_capacity = max(0.0, total_loan_capacity_after_rent - remaining_debt)
current_available_loan_capacity = max(0.0, total_loan_capacity_after_rent - current_loan_amount)

is_currently_capped = current_loan_amount >= total_loan_capacity_after_rent
is_future_capped = remaining_debt >= total_loan_capacity_after_rent

current_ltv = (current_loan_amount / property_value_today * 100) if property_value_today > 0 else 0.0
future_ltv = (remaining_debt / future_property_value * 100) if future_property_value > 0 else 0.0

if not loan_df.empty:
    first_payment = float(loan_df.iloc[0]["Terminbeløp"])
else:
    first_payment = 0.0


# -------------------------
# Inntektsoversikt
# -------------------------
st.subheader("Inntektsoversikt")

income_df = pd.DataFrame(income_rows)
st.dataframe(income_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Eiendomsanalyse
# -------------------------
st.subheader("Eiendomsanalyse")

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.metric(f"Verdi etter {years_forward} år", format_mill(future_property_value))

with c2:
    st.metric(f"Restgjeld etter {years_forward} år", format_mill(remaining_debt))

with c3:
    st.metric("Mulig EK å hente ut", format_mill(extractable_equity))

with c4:
    st.metric("Økt lånekapasitet fra leie", format_mill(rent_based_extra_capacity))

with c5:
    st.metric("Ledig lånekapasitet", format_mill(future_available_loan_capacity))
    
st.markdown(
    f"""
- **Kjøpsår:** {purchase_year}
- **Dagens verdi / kjøpspris:** {format_nok(property_value_today)}
- **Lån på eiendommen i dag:** {format_nok(current_loan_amount)}
- **Første terminbeløp:** {format_nok(first_payment)}
- **Dagens belåningsgrad:** {current_ltv:.1f} %
- **Belåningsgrad etter {years_forward} år:** {future_ltv:.1f} %
- **Lånekapasitet før leie:** {format_nok(income_based_max_loan)}
- **Økning fra månedlig leie × {int(rent_factor)}:** {format_nok(rent_based_extra_capacity)}
- **Total lånekapasitet:** {format_nok(total_loan_capacity_after_rent)}
- **Mulig egenkapital å hente ut etter {years_forward} år:** {format_nok(extractable_equity)}
"""
)

st.divider()


# -------------------------
# Oppsummeringstabeller
# -------------------------
st.subheader("Oppsummering")

summary_left, summary_right = st.columns(2)

with summary_left:
    summary_df = pd.DataFrame(
        {
            "Post": [
                "Samlet årsinntekt",
                "Annen gjeld",
                "Inntektsmultippel",
                "Lånekapasitet før leie",
                "Månedlig leie",
                f"Leie × faktor ({int(rent_factor)})",
                "Økt lånekapasitet fra leie",
                "Total lånekapasitet",
            ],
            "Verdi": [
                format_nok(total_annual_income),
                format_nok(other_debt),
                f"{income_multiple:.1f}x",
                format_nok(income_based_max_loan),
                format_nok(monthly_rent),
                f"{int(rent_factor)}",
                format_nok(rent_based_extra_capacity),
                format_nok(total_loan_capacity_after_rent),
            ],
        }
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

with summary_right:
    property_summary_df = pd.DataFrame(
        {
            "Post": [
                "Kjøpsår",
                "Dagens verdi / kjøpspris",
                "Lån i dag",
                "Lånetype",
                "Rente",
                "Nedbetalingstid",
                f"Verdi etter {years_forward} år",
                f"Restgjeld etter {years_forward} år",
                "Maks lån ved refinansiering",
                "Mulig EK å hente ut",
            ],
            "Verdi": [
                str(purchase_year),
                format_nok(property_value_today),
                format_nok(current_loan_amount),
                loan_type,
                f"{interest_rate:.2f} %",
                f"{repayment_years} år",
                format_nok(future_property_value),
                format_nok(remaining_debt),
                format_nok(max_loan_on_property),
                format_nok(extractable_equity),
            ],
        }
    )
    st.dataframe(property_summary_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Graf: verdi vs restgjeld
# -------------------------
st.subheader("Boligverdi vs. restgjeld over tid")

years_axis = list(range(0, years_forward + 1))
property_values = property_value_projection(property_value_today, annual_growth_percent, years_forward)
remaining_debt_by_year = [get_remaining_debt(loan_df, year, current_loan_amount) for year in years_axis]

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
    debt = get_remaining_debt(loan_df, year, current_loan_amount)
    equity = property_value - debt
    max_loan_year = property_value * (refinance_ltv_percent / 100)
    extractable_year = max(0.0, max_loan_year - debt)

    year_rows.append(
        {
            "År": year,
            "Estimert boligverdi": format_nok(property_value),
            "Restgjeld": format_nok(debt),
            "Egenkapital i bolig": format_nok(equity),
            "Maks lån ved refinansiering": format_nok(max_loan_year),
            "Mulig EK å hente ut": format_nok(extractable_year),
        }
    )

year_df = pd.DataFrame(year_rows)
st.dataframe(year_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Forklaring
# -------------------------
with st.expander("Hva betyr tallene?"):
    st.write(
        """
**Lånekapasitet før eiendom** = samlet årsinntekt × inntektsmultippel minus annen gjeld.

**Økt lånekapasitet fra leie** = månedlig leie × valgt faktor.

**Total lånekapasitet** = lånekapasitet før eiendom + økningen fra leie.

**Estimert boligverdi etter x år** = dagens verdi fremskrevet med valgt årlig verdistigning.

**Restgjeld etter x år** = hvor mye av lånet som gjenstår etter valgt antall år.

**Maks lån ved refinansiering** = boligverdi × valgt belåningsgrad.

**Mulig EK å hente ut** = maks lån ved refinansiering minus restgjeld.
"""
    )
