import streamlit as st
import pandas as pd

st.title("Agder Deal Scanner")

st.write("Prototype for analysing property deals in Agder.")

data = pd.DataFrame({
    "City": ["Kristiansand", "Grimstad", "Arendal"],
    "Price": [3200000, 2900000, 2600000],
    "Bedrooms": [3,3,2],
    "Estimated Rent": [18000,17000,15000]
})

data["Annual Rent"] = data["Estimated Rent"] * 12
data["Gross Yield"] = data["Annual Rent"] / data["Price"]

st.subheader("Property Deals")

st.dataframe(data)
