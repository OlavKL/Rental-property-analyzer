import json
import re
from urllib.parse import urlparse, urlunparse

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="Utleie-kalkulator", layout="wide")

st.title("Utleiekalkulator")
st.write("Beregn egenkapital, lånekostnader, total EK-belastning og netto kontantstrøm før skatt.")


# -------------------------
# Hjelpefunksjoner: FINN-url
# -------------------------
def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "nb-NO,nb;q=0.9,en;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text


def clean_text(value):
    if value is None:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value or None


def extract_first_number(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def find_json_ld_objects(soup: BeautifulSoup) -> list[dict]:
    objects = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                objects.extend([x for x in data if isinstance(x, dict)])
            elif isinstance(data, dict):
                objects.append(data)
        except Exception:
            continue
    return objects


def recursive_find_value(obj, wanted_keys: set[str]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in wanted_keys:
                return v
            found = recursive_find_value(v, wanted_keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = recursive_find_value(item, wanted_keys)
            if found is not None:
                return found
    return None


def normalize_ownership(value: str | None) -> str | None:
    if not value:
        return None

    v = value.lower().strip()

    if "selveier" in v:
        return "Selveier"
    if "andel" in v:
        return "Andel"
    if "aksje" in v:
        return "Aksje"
    if "borettslag" in v:
        return "Andel"

    return clean_text(value)


def is_valid_area(area: str | None) -> bool:
    if not area:
        return False

    area = clean_text(area)
    if not area:
        return False

    bad_fragments = [
        "vedlikeholdsfond",
        "felleskost",
        "prisantydning",
        "totalpris",
        "omkostninger",
        "andel fellesgjeld",
        "kommunale avgifter",
        "strøm",
        "soverom",
    ]

    lower_area = area.lower()
    if any(fragment in lower_area for fragment in bad_fragments):
        return False

    if len(area) < 2 or len(area) > 40:
        return False

    return True


def extract_area_from_address(address: str | None) -> str | None:
    if not address:
        return None

    match = re.search(r",\s*\d{4}\s+([A-ZÆØÅa-zæøå .\-]+)$", address)
    if match:
        candidate = clean_text(match.group(1))
        if is_valid_area(candidate):
            return candidate

    return None


def extract_address_candidates(text: str) -> list[str]:
    if not text:
        return []

    patterns = [
        r"\b[A-ZÆØÅ][A-Za-zÆØÅæøå0-9.\- ]{2,40}\s+\d+[A-Za-z]?,\s*\d{4}\s+[A-ZÆØÅ][A-Za-zÆØÅæøå.\- ]{2,30}\b",
        r"\b[A-ZÆØÅ][A-Za-zÆØÅæøå0-9.\- ]{2,40}\s+\d+[A-Za-z]?\s*,\s*\d{4}\s+[A-ZÆØÅ][A-Za-zÆØÅæøå.\- ]{2,30}\b",
    ]

    candidates = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            cleaned = clean_text(match)
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

    return candidates


def choose_best_address(candidates: list[str]) -> str | None:
    if not candidates:
        return None

    # Velg korteste plausible kandidat først
    candidates = sorted(candidates, key=len)

    for candidate in candidates:
        if "," in candidate and re.search(r"\d{4}", candidate):
            return candidate

    return candidates[0]


def extract_address_from_links(soup: BeautifulSoup) -> str | None:
    candidates = []

    for a_tag in soup.find_all("a", href=True):
        text = clean_text(a_tag.get_text(" ", strip=True))
        if not text:
            continue
        candidates.extend(extract_address_candidates(text))

    return choose_best_address(candidates)


def extract_address_from_visible_text(full_text: str) -> str | None:
    candidates = extract_address_candidates(full_text)
    return choose_best_address(candidates)


def extract_address_from_raw_html(html: str) -> str | None:
    candidates = extract_address_candidates(html)
    return choose_best_address(candidates)


def extract_address_from_title(soup: BeautifulSoup) -> str | None:
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string

    title = clean_text(title) or ""
    candidates = extract_address_candidates(title)
    return choose_best_address(candidates)


def parse_finn_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ", strip=True)
    full_text = clean_text(full_text) or ""

    result = {
        "purchase_price": None,
        "common_costs": None,
        "area": None,
        "address": None,
        "ownership": None,
    }

    # 0) Adresse: prøv flere kilder i prioritert rekkefølge
    address = (
        extract_address_from_links(soup)
        or extract_address_from_visible_text(full_text)
        or extract_address_from_raw_html(html)
        or extract_address_from_title(soup)
    )

    if address:
        result["address"] = address
        result["area"] = extract_area_from_address(address)

    # 1) JSON-LD
    jsonld_objects = find_json_ld_objects(soup)
    jsonld_price = None
    jsonld_area = None

    for obj in jsonld_objects:
        if jsonld_price is None:
            jsonld_price = recursive_find_value(obj, {"price"})
        if jsonld_area is None:
            jsonld_area = recursive_find_value(obj, {"addresslocality", "addressregion", "locality"})
        if jsonld_price is not None and jsonld_area is not None:
            break

    if jsonld_price is not None and result["purchase_price"] is None:
        result["purchase_price"] = extract_first_number(str(jsonld_price))

    if isinstance(jsonld_area, str) and not result["area"]:
        candidate = clean_text(jsonld_area)
        if is_valid_area(candidate):
            result["area"] = candidate

    # 2) Pris
    price_patterns = [
        r"Totalpris\s*([\d\s\u00A0.,]+)\s*kr",
        r"Prisantydning\s*([\d\s\u00A0.,]+)\s*kr",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, full_text, flags=re.IGNORECASE)
        if match:
            parsed_price = extract_first_number(match.group(1))
            if parsed_price:
                result["purchase_price"] = parsed_price
                break

    # 3) Felleskostnader
    common_cost_patterns = [
        r"Felleskost/mnd\.?\s*([\d\s\u00A0.,]+)\s*kr",
        r"Felleskostnader\s*([\d\s\u00A0.,]+)\s*kr",
        r"Felleskostnader pr\. mnd\.?\s*([\d\s\u00A0.,]+)\s*kr",
        r"Felleskostnader per måned\s*([\d\s\u00A0.,]+)\s*kr",
    ]
    for pattern in common_cost_patterns:
        match = re.search(pattern, full_text, flags=re.IGNORECASE)
        if match:
            parsed_common_costs = extract_first_number(match.group(1))
            if parsed_common_costs is not None:
                result["common_costs"] = parsed_common_costs
                break

    # 4) Eierform
    ownership_patterns = [
        r"Eierform\s*(Selveier)",
        r"Eierform\s*(Andel)",
        r"Eierform\s*(Aksje)",
        r"Eierform\s*(Borettslag)",
        r"\bselveier\b",
        r"\bandel\b",
        r"\baksje\b",
        r"\bborettslag\b",
    ]
    for pattern in ownership_patterns:
        match = re.search(pattern, full_text, flags=re.IGNORECASE)
        if match:
            ownership_raw = match.group(1) if match.groups() else match.group(0)
            result["ownership"] = normalize_ownership(ownership_raw)
            break

    # 5) Siste backup for område
    if not result["area"]:
        area_patterns = [
            r",\s*\d{4}\s+([A-ZÆØÅa-zæøå .\-]{2,30})",
            r"\b([A-ZÆØÅ][A-ZÆØÅa-zæøå\- ]+)\s+\d{4}\b",
        ]
        for pattern in area_patterns:
            match = re.search(pattern, full_text, flags=re.IGNORECASE)
            if match:
                candidate = clean_text(match.group(1))
                if is_valid_area(candidate):
                    result["area"] = candidate
                    break

    result["ownership"] = normalize_ownership(result["ownership"])

    if not is_valid_area(result["area"]):
        result["area"] = None

    return result
def annuity_payment(principal: float, annual_rate_percent: float, years: int) -> float:
    months = years * 12
    monthly_rate = annual_rate_percent / 100 / 12

    if principal <= 0 or months <= 0:
        return 0.0

    if monthly_rate == 0:
        return principal / months

    payment = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    return payment


def serial_schedule_first_month(principal: float, annual_rate_percent: float, years: int) -> tuple[float, float, float]:
    months = years * 12
    monthly_rate = annual_rate_percent / 100 / 12

    if principal <= 0 or months <= 0:
        return 0.0, 0.0, 0.0

    monthly_principal = principal / months
    first_month_interest = principal * monthly_rate
    first_month_total = monthly_principal + first_month_interest

    return first_month_total, monthly_principal, first_month_interest


def serial_schedule_last_month(principal: float, annual_rate_percent: float, years: int) -> tuple[float, float, float]:
    months = years * 12
    monthly_rate = annual_rate_percent / 100 / 12

    if principal <= 0 or months <= 0:
        return 0.0, 0.0, 0.0

    monthly_principal = principal / months
    remaining_before_last = monthly_principal
    last_month_interest = remaining_before_last * monthly_rate
    last_month_total = monthly_principal + last_month_interest

    return last_month_total, monthly_principal, last_month_interest


def monthly_payment_by_loan_type(principal: float, annual_rate_percent: float, years: int, loan_type: str) -> float:
    if loan_type == "Annuitetslån":
        return annuity_payment(principal, annual_rate_percent, years)
    first_total, _, _ = serial_schedule_first_month(principal, annual_rate_percent, years)
    return first_total


def calculate_rate_hikes_tolerated(
    loan_amount: float,
    base_nominal_rate: float,
    repayment_years: int,
    loan_type: str,
    monthly_rent: float,
    monthly_operating_costs: float,
    step_size: float = 0.25,
    max_steps: int = 100,
) -> int:
    tolerated_steps = 0

    for step in range(1, max_steps + 1):
        test_rate = base_nominal_rate + step * step_size
        test_monthly_loan_cost = monthly_payment_by_loan_type(
            loan_amount, test_rate, repayment_years, loan_type
        )
        test_cashflow = monthly_rent - monthly_operating_costs - test_monthly_loan_cost

        if test_cashflow >= 0:
            tolerated_steps += 1
        else:
            break

    return tolerated_steps


def format_nok(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,.0f} kr".replace(",", " ")


def format_mill(value: float) -> str:
    if value >= 1_000_000:
        mill = value / 1_000_000
        return f"{mill:.3f}".rstrip("0").rstrip(".") + " mill"
    return format_nok(value)


# -------------------------
# Session state defaults
# -------------------------
defaults = {
    "purchase_price": 3_000_000,
    "equity_percent": 15,
    "max_loan_amount": 2_700_000,
    "closing_cost_percent": 2.5,
    "monthly_rent": 18_000,
    "electricity": 1_000,
    "common_costs": 2_500,
    "municipal_fees": 800,
    "other_costs": 500,
    "loan_type": "Annuitetslån",
    "rate_type": "Nominell rente",
    "rate_input": 4.85,
    "repayment_years": 30,
    "finn_url": "",
    "detected_area": "",
    "detected_address": "",
    "detected_ownership": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# -------------------------
# Sidebar: FINN-import
# -------------------------
st.sidebar.header("Hent fra FINN")
st.sidebar.text_input(
    "Lim inn FINN-url",
    key="finn_url",
    placeholder="https://www.finn.no/realestate/homes/ad.html?finnkode=..."
)

if st.sidebar.button("Hent fra annonse"):
    url = normalize_url(st.session_state["finn_url"])

    if not url:
        st.sidebar.warning("Lim inn en URL først.")
    else:
        try:
            html = fetch_html(url)
            scraped = parse_finn_page(html)

            found_anything = False

            if scraped["purchase_price"] is not None:
                st.session_state["purchase_price"] = scraped["purchase_price"]
                found_anything = True

            if scraped["common_costs"] is not None:
                st.session_state["common_costs"] = scraped["common_costs"]
                found_anything = True

            if scraped["address"]:
                st.session_state["detected_address"] = scraped["address"]
                found_anything = True

            if scraped["area"]:
                st.session_state["detected_area"] = scraped["area"]
                found_anything = True

            if scraped["ownership"]:
                st.session_state["detected_ownership"] = scraped["ownership"]
                found_anything = True

                if scraped["ownership"] in ["Andel", "Aksje"]:
                    st.session_state["closing_cost_percent"] = 0.0
                elif scraped["ownership"] == "Selveier":
                    if st.session_state["closing_cost_percent"] == 0.0:
                        st.session_state["closing_cost_percent"] = 2.5

            if found_anything:
                st.sidebar.success("Fant data og fylte inn det som var tilgjengelig.")
            else:
                st.sidebar.warning("Fant ingen tydelige felter i annonsen. Legg inn manuelt.")

        except requests.HTTPError as e:
            st.sidebar.error(f"HTTP-feil: {e}")
        except requests.RequestException as e:
            st.sidebar.error(f"Nettverksfeil: {e}")
        except Exception as e:
            st.sidebar.error(f"Noe gikk galt: {e}")

if st.session_state["detected_address"]:
    st.sidebar.caption(f"Adresse fra annonse: {st.session_state['detected_address']}")

if st.session_state["detected_area"]:
    st.sidebar.caption(f"Område fra annonse: {st.session_state['detected_area']}")

if st.session_state["detected_ownership"]:
    st.sidebar.caption(f"Eierform fra annonse: {st.session_state['detected_ownership']}")


# -------------------------
# Sidebar / input
# -------------------------
st.sidebar.header("Inndata")

purchase_price = st.sidebar.number_input(
    "Kjøpesum",
    min_value=0,
    step=50_000,
    key="purchase_price",
)

equity_percent = st.sidebar.slider(
    "EK-krav (%)",
    min_value=0,
    max_value=100,
    step=1,
    key="equity_percent",
)

max_loan_amount = st.sidebar.number_input(
    "Maks lån",
    min_value=0,
    step=50_000,
    key="max_loan_amount",
)

closing_cost_percent = st.sidebar.number_input(
    "Omkostninger / dokumentavgift (%)",
    min_value=0.0,
    max_value=20.0,
    step=0.1,
    key="closing_cost_percent",
)

monthly_rent = st.sidebar.number_input(
    "Månedlig leie",
    min_value=0,
    step=500,
    key="monthly_rent",
)

electricity = st.sidebar.number_input(
    "Strøm per måned",
    min_value=0,
    step=100,
    key="electricity",
)

common_costs = st.sidebar.number_input(
    "Felleskost per måned",
    min_value=0,
    step=100,
    key="common_costs",
)

municipal_fees = st.sidebar.number_input(
    "Kommunale avgifter per måned",
    min_value=0,
    step=100,
    key="municipal_fees",
)

other_costs = st.sidebar.number_input(
    "Andre kostnader per måned",
    min_value=0,
    step=100,
    key="other_costs",
)

loan_type = st.sidebar.selectbox(
    "Lånetype",
    ["Annuitetslån", "Serielån"],
    key="loan_type",
)

rate_type = st.sidebar.selectbox(
    "Rentetype",
    ["Nominell rente", "Effektiv rente"],
    key="rate_type",
)

rate_input = st.sidebar.number_input(
    "Rente (%)",
    min_value=0.0,
    max_value=20.0,
    step=0.1,
    key="rate_input",
)

repayment_years = st.sidebar.number_input(
    "Nedbetalingstid (år)",
    min_value=1,
    max_value=40,
    step=1,
    key="repayment_years",
)


# -------------------------
# Info fra annonse
# -------------------------
if (
    st.session_state["detected_area"]
    or st.session_state["detected_address"]
    or st.session_state["detected_ownership"]
    or st.session_state["purchase_price"]
    or st.session_state["common_costs"]
):
    st.subheader("Data hentet fra annonse")

    col1, col2 = st.columns(2)

    with col1:
        st.write(
            "**Kjøpesum:**",
            format_mill(st.session_state["purchase_price"]) if st.session_state["purchase_price"] else "Fant ikke"
        )
        st.write(
            "**Felleskost:**",
            format_nok(st.session_state["common_costs"]) if st.session_state["common_costs"] else "Fant ikke"
        )
        st.write(
            "**Adresse:**",
            st.session_state["detected_address"] or "Fant ikke"
        )

    with col2:
        # Hvis område ikke ble funnet, prøv å vise det utledet fra adresse
        area_to_show = st.session_state["detected_area"]
        if not area_to_show and st.session_state["detected_address"]:
            area_to_show = extract_area_from_address(st.session_state["detected_address"])

        st.write(
            "**Område:**",
            area_to_show or "Fant ikke"
        )
        st.write(
            "**Eierform:**",
            st.session_state["detected_ownership"] or "Fant ikke"
        )

    st.caption("Tall som ikke ble funnet automatisk kan du fylle inn manuelt i sidepanelet.")
    st.divider()


# -------------------------
# Beregninger: EK og finansiering
# -------------------------
closing_costs = purchase_price * (closing_cost_percent / 100)
required_equity_base = purchase_price * (equity_percent / 100)

loan_amount = min(max_loan_amount, purchase_price)
ltv_percent = (loan_amount / purchase_price * 100) if purchase_price > 0 else 0.0

purchase_gap_due_to_loan_limit = max(0, purchase_price - max_loan_amount - required_equity_base)
minimum_cash_needed_to_close = purchase_price + closing_costs - max_loan_amount
total_equity_needed = required_equity_base + closing_costs + purchase_gap_due_to_loan_limit


# -------------------------
# Beregninger: rente, drift og yield
# -------------------------
if rate_type == "Nominell rente":
    nominal_rate = rate_input
    effective_rate = (1 + nominal_rate / 100 / 12) ** 12 - 1
    effective_rate = effective_rate * 100
else:
    effective_rate = rate_input
    nominal_rate = 12 * ((1 + effective_rate / 100) ** (1 / 12) - 1)
    nominal_rate = nominal_rate * 100

annual_rent = monthly_rent * 12
gross_yield_percent = (
    annual_rent / (purchase_price + closing_costs) * 100
) if (purchase_price + closing_costs) > 0 else 0.0
monthly_operating_costs = electricity + common_costs + municipal_fees + other_costs

if loan_type == "Annuitetslån":
    monthly_loan_cost = annuity_payment(loan_amount, nominal_rate, repayment_years)
    monthly_principal_payment = None
    monthly_interest_payment = None
    loan_info_text = "Fast terminbeløp hver måned."
else:
    first_total, first_principal, first_interest = serial_schedule_first_month(
        loan_amount, nominal_rate, repayment_years
    )
    last_total, last_principal, last_interest = serial_schedule_last_month(
        loan_amount, nominal_rate, repayment_years
    )
    monthly_loan_cost = first_total
    monthly_principal_payment = first_principal
    monthly_interest_payment = first_interest
    loan_info_text = "Terminbeløpet er høyest i starten og synker over tid."

monthly_cashflow_before_tax = monthly_rent - monthly_operating_costs - monthly_loan_cost
annual_cashflow_before_tax = monthly_cashflow_before_tax * 12
break_even_rent = monthly_operating_costs + monthly_loan_cost

rate_hikes_tolerated = calculate_rate_hikes_tolerated(
    loan_amount=loan_amount,
    base_nominal_rate=nominal_rate,
    repayment_years=repayment_years,
    loan_type=loan_type,
    monthly_rent=monthly_rent,
    monthly_operating_costs=monthly_operating_costs,
    step_size=0.25,
    max_steps=100,
)

max_tolerated_nominal_rate = nominal_rate + rate_hikes_tolerated * 0.25


# -------------------------
# Viktigste nøkkeltall først
# -------------------------
st.subheader("Nøkkeltall")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric(
        "Kjøpesum",
        format_mill(purchase_price),
        help=format_nok(purchase_price)
    )

with col2:
    st.metric(
        "Brutto yield",
        f"{gross_yield_percent:.2f} %",
        help="(Månedlig leie × 12) / (kjøpesum + omkostninger). Løpende kostnader er ikke inkludert."
    )

with col3:
    st.metric("Break-even leie", format_nok(break_even_rent))

with col4:
    st.metric(
        "Netto kontantstrøm / mnd",
        format_nok(monthly_cashflow_before_tax),
        help="Leie minus alle kostnader inkludert strøm, felleskostnader, avgifter og hele terminbeløpet på lånet (både renter og avdrag). Viser faktisk penger inn/ut av konto per måned."
    )

with col5:
    st.metric(
        "Rente-stresstest",
        f"{rate_hikes_tolerated} stk",
        help="Antall rentehopp (0,25 %-poeng økninger) en tåler før månedlig netto kontantstrøm blir negativ."
    )

st.divider()


# -------------------------
# EK-struktur + diagram
# -------------------------
left_top, right_top = st.columns([1, 1])

with left_top:
    st.subheader(f"Kontantbehov: {format_nok(total_equity_needed)}")

    ek_krav = required_equity_base
    omkost = closing_costs
    ekstra_ek = purchase_gap_due_to_loan_limit

    fig, ax = plt.subplots(figsize=(5, 6))

    ax.bar(["Totalt EK-behov"], [ek_krav], label="EK-krav")
    ax.bar(["Totalt EK-behov"], [omkost], bottom=[ek_krav], label="Omkostninger / dokumentavgift")
    ax.bar(
        ["Totalt EK-behov"],
        [ekstra_ek],
        bottom=[ek_krav + omkost],
        label="Ekstra EK pga. lånegrense"
    )

    if ek_krav > 0:
        ax.text(
            0,
            ek_krav / 2,
            f"EK-krav\n{format_nok(ek_krav)}",
            ha="center",
            va="center",
            color="white",
            fontsize=10,
            fontweight="bold"
        )

    if omkost > 0:
        ax.text(
            0,
            ek_krav + omkost / 2,
            f"Omkost\n{format_nok(omkost)}",
            ha="center",
            va="center",
            color="white",
            fontsize=10,
            fontweight="bold"
        )

    if ekstra_ek > 0:
        ax.text(
            0,
            ek_krav + omkost + ekstra_ek / 2,
            f"Ekstra EK\n{format_nok(ekstra_ek)}",
            ha="center",
            va="center",
            color="white",
            fontsize=10,
            fontweight="bold"
        )

    ax.set_ylabel("Beløp (kr)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    st.pyplot(fig)

with right_top:
    st.subheader("EK-struktur")

    equity_df = pd.DataFrame(
        {
            "Post": [
                "EK-krav",
                "Omkostninger / dokumentavgift",
                "Ekstra EK pga. lånebegrensning",
                "Totalt EK-behov",
                "Maks lån",
                "Belåningsgrad",
                "Minimum kontantbehov for å lukke kjøpet",
            ],
            "Verdi": [
                format_nok(required_equity_base),
                format_nok(closing_costs),
                format_nok(purchase_gap_due_to_loan_limit),
                format_nok(total_equity_needed),
                format_nok(max_loan_amount),
                f"{ltv_percent:.1f} %",
                format_nok(minimum_cash_needed_to_close),
            ],
        }
    )

    st.dataframe(equity_df, use_container_width=True, hide_index=True)

st.divider()

# -------------------------
# Låneberegning og kontantstrøm
# -------------------------
left, right = st.columns([1.2, 1])

with left:
    st.subheader("Låneberegning")

    if loan_type == "Annuitetslån":
        loan_df = pd.DataFrame(
            {
                "Post": [
                    "Lånetype",
                    "Lånebeløp",
                    "Belåningsgrad",
                    "Nominell rente",
                    "Effektiv rente",
                    "Nedbetalingstid",
                    "Månedlig terminbeløp",
                ],
                "Verdi": [
                    loan_type,
                    format_nok(loan_amount),
                    f"{ltv_percent:.1f} %",
                    f"{nominal_rate:.2f} %",
                    f"{effective_rate:.2f} %",
                    f"{repayment_years} år",
                    format_nok(monthly_loan_cost),
                ],
            }
        )
    else:
        last_total, _, _ = serial_schedule_last_month(loan_amount, nominal_rate, repayment_years)

        loan_df = pd.DataFrame(
            {
                "Post": [
                    "Lånetype",
                    "Lånebeløp",
                    "Belåningsgrad",
                    "Nominell rente",
                    "Effektiv rente",
                    "Nedbetalingstid",
                    "Første måneds avdrag",
                    "Første måneds renter",
                    "Første måneds totalbeløp",
                    "Siste måneds totalbeløp",
                ],
                "Verdi": [
                    loan_type,
                    format_nok(loan_amount),
                    f"{ltv_percent:.1f} %",
                    f"{nominal_rate:.2f} %",
                    f"{effective_rate:.2f} %",
                    f"{repayment_years} år",
                    format_nok(monthly_principal_payment or 0),
                    format_nok(monthly_interest_payment or 0),
                    format_nok(monthly_loan_cost),
                    format_nok(last_total),
                ],
            }
        )

    st.dataframe(loan_df, use_container_width=True, hide_index=True)
    st.caption(loan_info_text)

with right:
    st.subheader("Kontantstrøm før skatt")

    cashflow_df = pd.DataFrame(
        {
            "Post": [
                "Månedlig leie",
                "Strøm",
                "Felleskost",
                "Kommunale avgifter",
                "Andre kostnader",
                "Lånekostnad per måned",
                "Netto kontantstrøm per måned",
                "Netto kontantstrøm per år",
                "Break-even leie per måned",
                "Yield",
            ],
            "Verdi": [
                format_nok(monthly_rent),
                format_nok(electricity),
                format_nok(common_costs),
                format_nok(municipal_fees),
                format_nok(other_costs),
                format_nok(monthly_loan_cost),
                format_nok(monthly_cashflow_before_tax),
                format_nok(annual_cashflow_before_tax),
                format_nok(break_even_rent),
                f"{gross_yield_percent:.2f} %",
            ],
        }
    )

    st.dataframe(cashflow_df, use_container_width=True, hide_index=True)

st.divider()


# -------------------------
# Oppsummering
# -------------------------
st.subheader("Oppsummering")

if purchase_gap_due_to_loan_limit > 0:
    st.warning(
        f"Lånegrensen gjør at du må skyte inn ekstra {format_nok(purchase_gap_due_to_loan_limit)} utover ordinært EK-krav."
    )
else:
    st.success("Maks lån er høy nok til å dekke kjøpet innenfor valgt EK-krav.")

if monthly_cashflow_before_tax > 0:
    st.success(
        f"Boligen gir positiv netto kontantstrøm før skatt på {format_nok(monthly_cashflow_before_tax)} per måned."
    )
elif monthly_cashflow_before_tax < 0:
    st.error(
        f"Boligen gir negativ netto kontantstrøm før skatt på {format_nok(abs(monthly_cashflow_before_tax))} per måned."
    )
else:
    st.info("Boligen går omtrent i null før skatt.")

st.write(
    f"""
- **Kjøpesum:** {format_nok(purchase_price)}
- **Lånebeløp:** {format_nok(loan_amount)}
- **Belåningsgrad:** {ltv_percent:.1f} %
- **EK-krav:** {format_nok(required_equity_base)}
- **Omkostninger:** {format_nok(closing_costs)}
- **Ekstra EK pga. lånegrense:** {format_nok(purchase_gap_due_to_loan_limit)}
- **Totalt EK-behov:** {format_nok(total_equity_needed)}
- **Månedlige driftskostnader ekskl. lån:** {format_nok(monthly_operating_costs)}
- **Break-even leie:** {format_nok(break_even_rent)} per måned
- **Prosjektert netto kontantstrøm:** {format_nok(monthly_cashflow_before_tax)} per måned
- **Brutto yield:** {gross_yield_percent:.2f} %
- **Antall rentehopp på 0,25 %-poeng du tåler:** {rate_hikes_tolerated}
"""
)

st.divider()


# -------------------------
# Forklaringer
# -------------------------
with st.expander("Hva betyr tallene?"):
    st.write(
        """
**Yield** = årlig leieinntekt (månedlig leie × 12) delt på kjøpesum + omkostninger.

**Break-even leie** = hvor høy leien må være for at kontantstrøm før skatt blir 0.

**Prosjektert netto kontantstrøm per måned** = leie minus lånekostnader og øvrige månedlige kostnader.

**Antall rentehopp du tåler** = hvor mange hopp på 0,25 %-poeng renten kan øke før netto månedlig kontantstrøm blir negativ.

**EK-krav** = prosentandel av kjøpesummen du må dekke med egenkapital.

**Omkostninger / dokumentavgift** = transaksjonskostnader som kommer i tillegg til kjøpesummen.

**Ekstra EK pga. lånebegrensning** = ekstra kontanter du må legge inn hvis maks lån er lavere enn det som trengs for å finansiere kjøpet.

**Totalt EK-behov** = EK-krav + omkostninger + eventuelt ekstra tilskudd fordi lånet ikke dekker nok.
"""
    )
