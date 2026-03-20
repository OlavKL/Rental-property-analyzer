import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Lånekalkulator", layout="wide")

st.title("Lånekalkulator")
st.write("Sammenlign annuitetslån og serielån med fokus på avdrag, renter og terminbeløp.")


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


# -------------------------
# Sidebar
# -------------------------
st.sidebar.header("Inndata")

loan_amount = st.sidebar.number_input(
    "Lånebeløp",
    min_value=0,
    value=2_500_000,
    step=50_000,
)

rate_input = st.sidebar.number_input(
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

show_months = st.sidebar.slider(
    "Hvor mange måneder vil du vise i tabell?",
    min_value=6,
    max_value=60,
    value=12,
    step=6,
)


# -------------------------
# Beregninger
# -------------------------
ann_df = annuity_schedule(loan_amount, rate_input, repayment_years)
ser_df = serial_schedule(loan_amount, rate_input, repayment_years)

ann_total_paid = ann_df["Terminbeløp"].sum()
ann_total_interest = ann_df["Renter"].sum()

ser_total_paid = ser_df["Terminbeløp"].sum()
ser_total_interest = ser_df["Renter"].sum()

ann_first_payment = ann_df.iloc[0]["Terminbeløp"] if not ann_df.empty else 0
ser_first_payment = ser_df.iloc[0]["Terminbeløp"] if not ser_df.empty else 0
ser_last_payment = ser_df.iloc[-1]["Terminbeløp"] if not ser_df.empty else 0


# -------------------------
# Toppkort
# -------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Lånebeløp", format_nok(loan_amount))

with col2:
    st.metric("Rente", f"{rate_input:.2f} %")

with col3:
    st.metric("Annuitet første termin", format_nok(ann_first_payment))

with col4:
    st.metric("Serie første termin", format_nok(ser_first_payment))

st.divider()


# -------------------------
# Oppsummeringstabell
# -------------------------
st.subheader("Sammenligning")

comparison_df = pd.DataFrame({
    "Post": [
        "Første terminbeløp",
        "Siste terminbeløp",
        "Totalt betalt",
        "Total rentekostnad"
    ],
    "Annuitetslån": [
        format_nok(ann_first_payment),
        format_nok(ann_df.iloc[-1]["Terminbeløp"]),
        format_nok(ann_total_paid),
        format_nok(ann_total_interest)
    ],
    "Serielån": [
        format_nok(ser_first_payment),
        format_nok(ser_last_payment),
        format_nok(ser_total_paid),
        format_nok(ser_total_interest)
    ]
})

st.dataframe(comparison_df, use_container_width=True, hide_index=True)

if ser_total_interest < ann_total_interest:
    st.success(
        f"Serielån gir lavere total rentekostnad enn annuitetslån, med omtrent {format_nok(ann_total_interest - ser_total_interest)} lavere renter totalt."
    )

st.divider()


# -------------------------
# Graf: terminbeløp
# -------------------------
st.subheader("Terminbeløp over tid")

fig1, ax1 = plt.subplots(figsize=(10, 5))
ax1.plot(ann_df["Måned"], ann_df["Terminbeløp"], label="Annuitetslån")
ax1.plot(ser_df["Måned"], ser_df["Terminbeløp"], label="Serielån")
ax1.set_xlabel("Måned")
ax1.set_ylabel("Beløp (kr)")
ax1.set_title("Terminbeløp per måned")
ax1.legend()
ax1.spines["top"].set_visible(False)
ax1.spines["right"].set_visible(False)
st.pyplot(fig1)

st.divider()


# -------------------------
# Graf: renter vs avdrag første 24 måneder
# -------------------------
st.subheader("Renter og avdrag")

months_to_plot = min(24, len(ann_df))

fig2, ax2 = plt.subplots(figsize=(10, 5))
ax2.plot(ann_df["Måned"][:months_to_plot], ann_df["Renter"][:months_to_plot], label="Annuitet - renter")
ax2.plot(ann_df["Måned"][:months_to_plot], ann_df["Avdrag"][:months_to_plot], label="Annuitet - avdrag")
ax2.plot(ser_df["Måned"][:months_to_plot], ser_df["Renter"][:months_to_plot], label="Serie - renter")
ax2.plot(ser_df["Måned"][:months_to_plot], ser_df["Avdrag"][:months_to_plot], label="Serie - avdrag")
ax2.set_xlabel("Måned")
ax2.set_ylabel("Beløp (kr)")
ax2.set_title("Renter og avdrag de første 24 månedene")
ax2.legend()
ax2.spines["top"].set_visible(False)
ax2.spines["right"].set_visible(False)
st.pyplot(fig2)

st.divider()


# -------------------------
# Tabeller
# -------------------------
left, right = st.columns(2)

with left:
    st.subheader("Annuitetslån – første måneder")
    ann_show = ann_df.head(show_months).copy()
    for col in ["Terminbeløp", "Avdrag", "Renter", "Restgjeld"]:
        ann_show[col] = ann_show[col].apply(format_nok)
    st.dataframe(ann_show, use_container_width=True, hide_index=True)

with right:
    st.subheader("Serielån – første måneder")
    ser_show = ser_df.head(show_months).copy()
    for col in ["Terminbeløp", "Avdrag", "Renter", "Restgjeld"]:
        ser_show[col] = ser_show[col].apply(format_nok)
    st.dataframe(ser_show, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Forklaring
# -------------------------
with st.expander("Hva er forskjellen på annuitetslån og serielån?"):
    st.write(
        """
**Annuitetslån**
- Du betaler omtrent samme terminbeløp hver måned.
- I starten er en større del renter.
- Etter hvert går mer av betalingen til avdrag.

**Serielån**
- Du betaler like stort avdrag hver måned.
- Rentene er høyest i starten og faller etter hvert.
- Derfor er terminbeløpet høyest i starten og synker over tid.

**Typisk forskjell**
- Annuitetslån = jevnere belastning per måned
- Serielån = lavere totale renter, men tyngre i starten
"""
    )
