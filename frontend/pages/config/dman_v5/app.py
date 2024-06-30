import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yaml
from plotly.subplots import make_subplots

from CONFIG import BACKEND_API_HOST, BACKEND_API_PORT
from backend.services.backend_api_client import BackendAPIClient
from frontend.st_utils import initialize_st_page, get_backend_api_client

# Initialize the Streamlit page
initialize_st_page(title="D-Man V5", icon="📊", initial_sidebar_state="expanded")

@st.cache_data
def get_candles(connector_name, trading_pair, interval, max_records):
    backend_client = BackendAPIClient(BACKEND_API_HOST, BACKEND_API_PORT)
    return backend_client.get_real_time_candles(connector_name, trading_pair, interval, max_records)

@st.cache_data
def add_indicators(df, macd_fast, macd_slow, macd_signal, diff_lookback):
    # MACD
    df.ta.macd(fast=macd_fast, slow=macd_slow, signal=macd_signal, append=True)

    # Decision Logic
    macdh = df[f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"]
    macdh_diff = df[f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"].diff(diff_lookback)

    long_condition = (macdh > 0) & (macdh_diff > 0)
    short_condition = (macdh < 0) & (macdh_diff < 0)

    df["signal"] = 0
    df.loc[long_condition, "signal"] = 1
    df.loc[short_condition, "signal"] = -1

    return df

st.write("## Configuration")
c1, c2, c3 = st.columns(3)
with c1:
    connector_name = st.text_input("Connector Name", value="binance_perpetual")
    trading_pair = st.text_input("Trading Pair", value="WLD-USDT")
with c2:
    interval = st.selectbox("Candle Interval", ["1m", "3m", "5m", "15m", "30m"], index=1)
    max_records = st.number_input("Max Records", min_value=100, max_value=10000, value=1000)
with c3:
    macd_fast = st.number_input("MACD Fast", min_value=1, value=21)
    macd_slow = st.number_input("MACD Slow", min_value=1, value=42)
    macd_signal = st.number_input("MACD Signal", min_value=1, value=9)
    diff_lookback = st.number_input("MACD Diff Lookback", min_value=1, value=5)

# Fetch and process data
candle_data = get_candles(connector_name, trading_pair, interval, max_records)
df = pd.DataFrame(candle_data)
df.index = pd.to_datetime(df['timestamp'], unit='s')
df = add_indicators(df, macd_fast, macd_slow, macd_signal, diff_lookback)

# Prepare data for signals
signals = df[df['signal'] != 0]
buy_signals = signals[signals['signal'] == 1]
sell_signals = signals[signals['signal'] == -1]


# Define your color palette
tech_colors = {
    'upper_band': '#4682B4',
    'middle_band': '#FFD700',
    'lower_band': '#32CD32',
    'buy_signal': '#1E90FF',
    'sell_signal': '#FF0000',
}

# Create a subplot with 3 rows
fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                    vertical_spacing=0.05,  # Adjust spacing to make the plot look better
                    subplot_titles=('Candlestick', 'MACD Line and Histogram', 'Trading Signals'),
                    row_heights=[0.5, 0.3, 0.2])  # Adjust heights to give more space to candlestick and MACD

# Candlestick and Bollinger Bands
fig.add_trace(go.Candlestick(x=df.index,
                             open=df['open'],
                             high=df['high'],
                             low=df['low'],
                             close=df['close'],
                             name="Candlesticks", increasing_line_color='#2ECC71', decreasing_line_color='#E74C3C'),
              row=1, col=1)

# MACD Line and Histogram
fig.add_trace(go.Scatter(x=df.index, y=df[f"MACD_{macd_fast}_{macd_slow}_{macd_signal}"], line=dict(color='orange'), name='MACD Line'), row=2, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df[f"MACDs_{macd_fast}_{macd_slow}_{macd_signal}"], line=dict(color='purple'), name='MACD Signal'), row=2, col=1)
fig.add_trace(go.Bar(x=df.index, y=df[f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"], name='MACD Histogram', marker_color=df[f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"].apply(lambda x: '#FF6347' if x < 0 else '#32CD32')), row=2, col=1)
# Signals plot
fig.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals['close'], mode='markers',
                         marker=dict(color=tech_colors['buy_signal'], size=10, symbol='triangle-up'),
                         name='Buy Signal'), row=1, col=1)
fig.add_trace(go.Scatter(x=sell_signals.index, y=sell_signals['close'], mode='markers',
                         marker=dict(color=tech_colors['sell_signal'], size=10, symbol='triangle-down'),
                         name='Sell Signal'), row=1, col=1)

# Trading Signals
fig.add_trace(go.Scatter(x=signals.index, y=signals['signal'], mode='markers', marker=dict(color=signals['signal'].map({1: '#1E90FF', -1: '#FF0000'}), size=10), name='Trading Signals'), row=3, col=1)

# Update layout settings for a clean look
fig.update_layout(height=1000, title="MACD and Bollinger Bands Strategy", xaxis_title="Time", yaxis_title="Price", template="plotly_dark", showlegend=True)
fig.update_xaxes(rangeslider_visible=False, row=1, col=1)
fig.update_xaxes(rangeslider_visible=False, row=2, col=1)
fig.update_xaxes(rangeslider_visible=False, row=3, col=1)

# Display the chart
st.plotly_chart(fig, use_container_width=True)


c1, c2, c3 = st.columns([2, 2, 1])

with c1:
    config_base = st.text_input("Config Base", value=f"macd_bb_v1-{connector_name}-{trading_pair.split('-')[0]}")
with c2:
    config_tag = st.text_input("Config Tag", value="1.1")

# Save the configuration
id = f"{config_base}-{config_tag}"

config = {
    "id": id,
    "connector_name": connector_name,
    "trading_pair": trading_pair,
    "interval": interval,
    "macd_fast": macd_fast,
    "macd_slow": macd_slow,
    "macd_signal": macd_signal,
}

yaml_config = yaml.dump(config, default_flow_style=False)

with c3:
    download_config = st.download_button(
        label="Download YAML",
        data=yaml_config,
        file_name=f'{id.lower()}.yml',
        mime='text/yaml'
    )
    upload_config_to_backend = st.button("Upload Config to BackendAPI")


if upload_config_to_backend:
    backend_api_client = get_backend_api_client()
    backend_api_client.add_controller_config(config)
    st.success("Config uploaded successfully!")
