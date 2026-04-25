import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

folder = Path("historical-csvs/round3")

st.title("IMC Prosperity CSV Viewer: Round 3")

csv_files = list(folder.glob("*.csv"))

selected_file = st.selectbox(
    "Choose a CSV file",
    csv_files,
    format_func=lambda path: path.name
)

df = pd.read_csv(selected_file, sep=";")

# filter by product

if "product" in df.columns:
    product = st.selectbox("Choose product", df["product"].unique())
    df = df[df["product"] == product]

if "symbol" in df.columns:
    symbol = st.selectbox("Choose symbol", df["symbol"].unique())
    df = df[df["symbol"] == symbol]

st.subheader("Data Preview")
st.dataframe(df)

st.subheader("Columns")
st.write(list(df.columns))

# choose x and y columns
x_column = st.selectbox("X-axis column", df.columns)

numeric_columns = df.select_dtypes(include="number").columns
y_column = st.selectbox("Y-axis column", numeric_columns)

fig, ax = plt.subplots(figsize=(50, 25))
# changing it too large crashes it

df.plot(
    x=x_column,
    y=y_column,
    kind="line",
    ax=ax
)

ax.set_title(selected_file.stem)
ax.set_xlabel(x_column)
ax.set_ylabel(y_column)

st.pyplot(fig)

"""
To run this, install Streamlit, Pandas, and Matplotlib:
pip install streamlit pandas matplotlib or python3 -m pip install streamlit pandas matplotlib inside your venv idk

then run: streamlit run data-analysis.py to open app in browser
"""