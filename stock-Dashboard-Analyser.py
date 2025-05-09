#Run in google collab 
# Install required packages in Colab
!pip install flask pyngrok yfinance pandas numpy matplotlib seaborn statsmodels scikit-learn plotly --quiet

# Step 1: Set the ngrok auth token as an environment variable
import os
os.environ["NGROK_AUTH_TOKEN"] = "2uwCM03DK0Avho0aKy9d6nojW1e_7H9vHUuCoUAYPyKsCDLbH"

# Step 2: Import libraries
from flask import Flask, render_template_string, request, session
from pyngrok import ngrok, conf
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller
from sklearn.metrics import mean_absolute_error, mean_squared_error
import itertools
import io
import base64
from threading import Thread
import logging
import socket
import re
import time
import subprocess
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, filename="stock_dashboard.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Step 3: Define Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session management

# Step 4: HTML Templates with Enhanced UI
index_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Stock Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; }
        h2 { color: #333; }
        .container { max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        label { font-weight: bold; margin-right: 10px; }
        input[type="text"], input[type="number"], select { padding: 8px; margin: 5px 0; border: 1px solid #ccc; border-radius: 4px; width: 100%; box-sizing: border-box; }
        input[type="submit"] { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; width: 100%; }
        input[type="submit"]:hover { background-color: #45a049; }
        .checkbox-group { margin: 10px 0; }
        .checkbox-group label { font-weight: normal; }
        .error { color: red; }
        @media (max-width: 600px) {
            .container { padding: 10px; }
            h2 { font-size: 1.5em; }
        }
    </style>
</head>
<body>
<div class="container">
    <h2>📈 Stock Market Dashboard</h2>
    <form method="POST" action="/result">
        <label>Stock Symbol:</label>
        <input type="text" name="ticker" value="AAPL" required><br><br>
        <label>Moving Average Period:</label>
        <input type="number" name="ma_period" value="20" min="1" required><br><br>
        <label>Bollinger Band Period:</label>
        <input type="number" name="bb_period" value="20" min="1" required><br><br>
        <label>Compare Stocks:</label><br>
        <div class="checkbox-group">
            {% for stock in stock_list %}
            <input type="checkbox" name="compare_stocks" value="{{ stock }}" {% if stock in ['AAPL','MSFT'] %}checked{% endif %}> {{ stock }}<br>
            {% endfor %}
        </div>
        <label>Risk Tolerance:</label>
        <select name="risk_tolerance">
            <option value="low">Low</option>
            <option value="medium" selected>Medium</option>
            <option value="high">High</option>
        </select><br><br>
        <input type="submit" value="Analyze">
    </form>
</div>
</body>
</html>
'''

result_html = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{ ticker }} Analysis</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; transition: background-color 0.3s, color 0.3s; }
        .light-theme { background-color: #f4f4f9; color: #333; }
        .dark-theme { background-color: #1a1a1a; color: #e0e0e0; }
        .container { display: flex; min-height: 100vh; }
        .sidebar { width: 250px; background-color: #2c3e50; color: white; padding: 20px; position: fixed; height: 100%; overflow-y: auto; }
        .sidebar h3 { margin-top: 0; }
        .sidebar a { color: #ecf0f1; text-decoration: none; display: block; padding: 10px; margin: 5px 0; border-radius: 4px; }
        .sidebar a:hover { background-color: #34495e; }
        .content { margin-left: 270px; padding: 20px; flex: 1; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .dark-theme .chart-container { background: #2c2c2c; box-shadow: 0 0 10px rgba(255,255,255,0.1); }
        .note { font-style: italic; color: #555; margin-bottom: 10px; }
        .dark-theme .note { color: #bbb; }
        .navigation { margin: 20px 0; }
        .navigation button { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        .navigation button:disabled { background-color: #cccccc; cursor: not-allowed; }
        .navigation button:hover:not(:disabled) { background-color: #45a049; }
        .theme-toggle { position: fixed; top: 20px; right: 20px; background-color: #4CAF50; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; }
        .theme-toggle:hover { background-color: #45a049; }
        .stock-switch { margin-bottom: 20px; }
        .stock-switch select { padding: 8px; border-radius: 4px; }
        .download-btn { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-bottom: 20px; }
        .download-btn:hover { background-color: #45a049; }
        .tooltip { position: relative; display: inline-block; cursor: pointer; margin-left: 5px; }
        .tooltip .tooltiptext { visibility: hidden; width: 200px; background-color: #555; color: #fff; text-align: center; border-radius: 6px; padding: 5px; position: absolute; z-index: 1; bottom: 125%; left: 50%; margin-left: -100px; opacity: 0; transition: opacity 0.3s; }
        .tooltip:hover .tooltiptext { visibility: visible; opacity: 1; }
        @media (max-width: 768px) {
            .container { flex-direction: column; }
            .sidebar { width: 100%; position: relative; height: auto; }
            .content { margin-left: 0; }
        }
    </style>
</head>
<body class="light-theme">
    <button class="theme-toggle" onclick="toggleTheme()">Toggle Theme</button>
    <div class="container">
        <div class="sidebar">
            <h3>Analysis Menu</h3>
            {% for analysis in analyses %}
            <a href="/result?page={{ loop.index0 }}">{{ analysis.title }}</a>
            {% endfor %}
        </div>
        <div class="content">
            <h2>📊 Analysis for {{ ticker }}</h2>
            <div class="stock-switch">
                <label>Switch Stock: </label>
                <select onchange="window.location.href='/result?ticker=' + this.value + '&page={{ current_page }}'">
                    {% for stock in stock_list %}
                    <option value="{{ stock }}" {% if stock == ticker %}selected{% endif %}>{{ stock }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="download-btn" onclick="downloadReport()">Download Report as PDF</div>
            <div class="chart-container">
                <h3>{{ current_analysis.title }} <span class="tooltip">ℹ️<span class="tooltiptext">{{ current_analysis.description }}</span></span></h3>
                <p class="note">{{ current_analysis.note }}</p>
                <div id="chart">{{ current_analysis.chart | safe }}</div>
            </div>
            <div class="navigation">
                <button onclick="window.location.href='/result?page={{ current_page - 1 }}'" {% if current_page == 0 %}disabled{% endif %}>Previous Analysis</button>
                <button onclick="window.location.href='/result?page={{ current_page + 1 }}'" {% if current_page == analyses|length - 1 %}disabled{% endif %}>Next Analysis</button>
            </div>
        </div>
    </div>
    <script>
        function toggleTheme() {
            document.body.classList.toggle('dark-theme');
            document.body.classList.toggle('light-theme');
        }
        function downloadReport() {
            window.print();
        }
    </script>
</body>
</html>
'''

# Step 5: Utility - Convert Plotly chart to HTML
def plotly_to_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

# Step 6: Utility - Check if port is in use and find an available port
def find_available_port(start_port=5000, max_attempts=10):
    port = start_port
    for _ in range(max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
            port += 1
    raise RuntimeError("Could not find an available port after {} attempts".format(max_attempts))

# Step 7: Utility - Grid search for ARIMA parameters
def optimize_arima(train, p_range, d_range, q_range):
    best_aic = float("inf")
    best_order = None
    for p, d, q in itertools.product(p_range, d_range, q_range):
        try:
            model = ARIMA(train, order=(p, d, q))
            model_fit = model.fit()
            aic = model_fit.aic
            if aic < best_aic:
                best_aic = aic
                best_order = (p, d, q)
        except Exception as e:
            logging.warning(f"ARIMA failed for order ({p},{d},{q}): {str(e)}")
            continue
    return best_order

# Step 8: Utility - Grid search for SARIMA parameters
def optimize_sarima(train, p_range, d_range, q_range, P_range, D_range, Q_range, s):
    best_aic = float("inf")
    best_params = None
    for p, d, q, P, D, Q in itertools.product(p_range, d_range, q_range, P_range, D_range, Q_range):
        try:
            model = SARIMAX(train, order=(p, d, q), seasonal_order=(P, D, Q, s))
            model_fit = model.fit(disp=False)
            aic = model_fit.aic
            if aic < best_aic:
                best_aic = aic
                best_params = (p, d, q, P, D, Q)
        except Exception as e:
            logging.warning(f"SARIMA failed for order ({p},{d},{q})({P},{D},{Q},{s}): {str(e)}")
            continue
    return best_params

# Step 9: Utility - Technical Analysis Functions
def calculate_rsi(data, periods=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data, slow=26, fast=12, signal=9):
    exp1 = data['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def find_support_resistance(data, window=20):
    support = data['Low'].rolling(window=window).min()
    resistance = data['High'].rolling(window=window).max()
    return support, resistance

def calculate_stochastic_oscillator(data, k_period=14, d_period=3):
    lowest_low = data['Low'].rolling(window=k_period).min()
    highest_high = data['High'].rolling(window=k_period).max()
    k = 100 * (data['Close'] - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    return k, d

# Step 10: Utility - Quantitative Risk Analysis Functions
def calculate_var(returns, confidence_level=0.95):
    if len(returns) == 0:
        return 0
    sorted_returns = np.sort(returns)
    index = int((1 - confidence_level) * len(sorted_returns))
    var = -sorted_returns[index] * 100
    return var

def calculate_beta(stock_data, market_data):
    stock_returns = stock_data['Close'].pct_change().dropna()
    market_returns = market_data['Close'].pct_change().dropna()
    if len(stock_returns) == 0 or len(market_returns) == 0:
        return 0
    covariance = np.cov(stock_returns, market_returns)[0, 1]
    market_variance = np.var(market_returns)
    if market_variance == 0:
        return 0
    beta = covariance / market_variance
    return beta

def calculate_capm(beta, risk_free_rate=0.02, market_return=0.08):
    expected_return = risk_free_rate + beta * (market_return - risk_free_rate)
    return expected_return * 100

def calculate_standard_deviation(returns):
    if len(returns) == 0:
        return 0
    std_dev = np.std(returns) * np.sqrt(252) * 100
    return std_dev

def calculate_risk_reward(stock_data, forecast_price, stop_loss, target_price):
    current_price = stock_data['Close'][-1]
    if stop_loss >= current_price or target_price <= current_price:
        return float('inf')
    risk = (current_price - stop_loss) / current_price
    reward = (target_price - current_price) / current_price
    if risk == 0:
        return float('inf')
    return risk / reward

# Step 11: Utility - Qualitative Risk Analysis Functions
def get_pe_ratio(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        pe_ratio = info.get('trailingPE', 0)
        return pe_ratio if pe_ratio else 0
    except Exception as e:
        logging.error(f"Failed to fetch P/E ratio for {ticker}: {str(e)}")
        return 0

def estimate_market_sentiment(stock_data):
    recent_data = stock_data['Close'][-20:]
    if len(recent_data) < 2:
        return "Neutral"
    price_change = (recent_data[-1] - recent_data[0]) / recent_data[0] * 100
    if price_change > 5:
        return "Bullish"
    elif price_change < -5:
        return "Bearish"
    else:
        return "Neutral"

def risk_tolerance_recommendation(risk_tolerance, beta):
    if risk_tolerance == "low" and beta > 1:
        return "Consider reducing exposure due to high volatility."
    elif risk_tolerance == "high" and beta < 1:
        return "You may increase exposure to seek higher returns."
    else:
        return "Portfolio aligns with your risk tolerance."

# Step 12: Flask Routes
@app.route("/", methods=["GET"])
def index():
    stock_list = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    return render_template_string(index_html, stock_list=stock_list)

@app.route("/result", methods=["GET", "POST"])
def result():
    if request.method == "POST":
        ticker = request.form.get("ticker", "").upper()
        if not re.match(r'^[A-Z]{1,5}$', ticker):
            return "<h3>Invalid ticker symbol: Use 1-5 uppercase letters</h3>"

        try:
            ma = int(request.form.get("ma_period"))
            bb = int(request.form.get("bb_period"))
            if ma <= 0 or bb <= 0:
                return "<h3>Periods must be positive integers</h3>"
        except ValueError:
            return "<h3>Invalid period input: Must be a number</h3>"

        compare_stocks = request.form.getlist("compare_stocks")
        risk_tolerance = request.form.get("risk_tolerance", "medium")

        session['ticker'] = ticker
        session['ma'] = ma
        session['bb'] = bb
        session['compare_stocks'] = compare_stocks
        session['risk_tolerance'] = risk_tolerance
        session['stock_list'] = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    else:
        ticker = request.args.get("ticker", session.get('ticker', "AAPL")).upper()
        session['ticker'] = ticker
        ma = session.get('ma', 20)
        bb = session.get('bb', 20)
        compare_stocks = session.get('compare_stocks', [])
        risk_tolerance = session.get('risk_tolerance', "medium")
        session['stock_list'] = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    try:
        stock = yf.Ticker(ticker)
        stock_data = stock.history(period="1y")
        if stock_data.empty:
            return f"<h3>Invalid stock symbol {ticker}</h3>"
        logging.info(f"Stock data for {ticker}: {stock_data.head()}")
    except Exception as e:
        logging.error(f"Failed to fetch data for {ticker}: {str(e)}")
        return f"<h3>Error fetching data for {ticker}. Check logs.</h3>"

    stock_data = stock_data.dropna()
    if len(stock_data) < max(ma, bb):
        return f"<h3>Not enough data for {ticker} to compute {ma}- or {bb}-day metrics</h3>"

    try:
        market = yf.Ticker("^GSPC")
        market_data = market.history(period="1y")
        market_data = market_data.dropna()
    except Exception as e:
        logging.error(f"Failed to fetch market data: {str(e)}")
        market_data = pd.DataFrame()

    stock_data['RSI'] = calculate_rsi(stock_data)
    stock_data['MACD'], stock_data['Signal'] = calculate_macd(stock_data)
    stock_data['Support'], stock_data['Resistance'] = find_support_resistance(stock_data)
    stock_data['%K'], stock_data['%D'] = calculate_stochastic_oscillator(stock_data)
    stock_data["MA"] = stock_data["Close"].rolling(window=ma).mean()
    stock_data["Middle"] = stock_data["Close"].rolling(window=bb).mean()
    std = stock_data["Close"].rolling(window=bb).std()
    stock_data["Upper"] = stock_data["Middle"] + (2 * std)
    stock_data["Lower"] = stock_data["Middle"] - (2 * std)
    stock_data["Log_Close"] = np.log(stock_data["Close"])

    analyses = []

    # Fixed Candlestick Chart
    try:
        plot_data = stock_data[-60:].copy()
        if len(plot_data) < 2:
            raise ValueError("Not enough data for candlestick chart")
        if not all(col in plot_data.columns for col in ['Open', 'High', 'Low', 'Close']):
            raise ValueError(f"Missing required columns: {plot_data.columns}")
        
        hover_text = [
            f"Date: {date.strftime('%Y-%m-%d')}<br>" +
            f"Open: ${row['Open']:.2f}<br>" +
            f"High: ${row['High']:.2f}<br>" +
            f"Low: ${row['Low']:.2f}<br>" +
            f"Close: ${row['Close']:.2f}<br>" +
            f"Volume: {row['Volume']:,.0f}<br>" +
            f"RSI: {row['RSI']:.2f}<br>" +
            f"MACD: {row['MACD']:.2f}<br>" +
            f"Signal: {row['Signal']:.2f}"
            for date, row in plot_data.iterrows()
        ]
        
        fig = go.Figure(data=[
            go.Candlestick(
                x=plot_data.index,
                open=plot_data['Open'],
                high=plot_data['High'],
                low=plot_data['Low'],
                close=plot_data['Close'],
                name='Candlestick',
                hovertext=hover_text,
                hoverinfo='text'
            )
        ])
        fig.update_layout(
            title=f"{ticker} - Candlestick Chart (Last 60 Days)",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False,
            template="plotly_white"
        )
        candle_chart = plotly_to_html(fig)
        analyses.append({
            "title": " Candlestick Chart",
            "description": "Visualize daily price movements with open, high, low, and close prices. Hover to see detailed stock metrics.",
            "note": "Shows daily price movements (open, high, low, close) over the last 60 days. Green candles indicate price increases, red candles indicate decreases.",
            "chart": candle_chart
        })
        logging.info(f"Successfully generated candlestick chart for {ticker}")
    except Exception as e:
        logging.error(f"Candlestick Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " Candlestick Chart",
            "description": "Visualize daily price movements with open, high, low, and close prices.",
            "note": f"Failed to generate candlestick chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # RSI Chart
    try:
        rsi_data = stock_data['RSI'][-60:].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rsi_data.index, y=rsi_data, mode='lines', name='RSI', line=dict(color='purple')))
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought (70)")
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold (30)")
        fig.update_layout(
            title=f"{ticker} - RSI (14-Day)",
            yaxis_title="RSI",
            yaxis_range=[0, 100],
            template="plotly_white"
        )
        analyses.append({
            "title": " RSI (Relative Strength Index)",
            "description": "Measures momentum on a scale of 0 to 100. Useful for identifying overbought or oversold conditions.",
            "note": "RSI above 70 indicates overbought conditions (potential sell signal), below 30 indicates oversold (potential buy signal).",
            "chart": plotly_to_html(fig)
        })
    except Exception as e:
        logging.error(f"RSI Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " RSI (Relative Strength Index)",
            "description": "Measures momentum on a scale of 0 to 100.",
            "note": f"Failed to generate RSI chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # MACD Chart
    try:
        macd_data = stock_data[['MACD', 'Signal']][-60:].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=macd_data.index, y=macd_data['MACD'], mode='lines', name='MACD', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=macd_data.index, y=macd_data['Signal'], mode='lines', name='Signal Line', line=dict(color='orange')))
        fig.update_layout(
            title=f"{ticker} - MACD (12, 26, 9)",
            yaxis_title="MACD",
            template="plotly_white"
        )
        analyses.append({
            "title": " MACD (Moving Average Convergence Divergence)",
            "description": "Identifies momentum and trend changes using the difference between two moving averages.",
            "note": "A bullish signal occurs when the MACD line crosses above the signal line; a bearish signal when it crosses below.",
            "chart": plotly_to_html(fig)
        })
    except Exception as e:
        logging.error(f"MACD Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " MACD (Moving Average Convergence Divergence)",
            "description": "Identifies momentum and trend changes.",
            "note": f"Failed to generate MACD chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # Volume Chart
    try:
        volume_data = stock_data['Volume'][-60:]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=volume_data.index, y=volume_data, name='Volume', marker_color='gray'))
        fig.update_layout(
            title=f"{ticker} - Trading Volume (Last 60 Days)",
            yaxis_title="Volume",
            template="plotly_white"
        )
        analyses.append({
            "title": " Volume Chart",
            "description": "Shows trading volume over time to gauge market interest.",
            "note": "High volume on price increases suggests strong buying interest; high volume on decreases suggests selling pressure.",
            "chart": plotly_to_html(fig)
        })
    except Exception as e:
        logging.error(f"Volume Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " Volume Chart",
            "description": "Shows trading volume over time.",
            "note": f"Failed to generate Volume chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # Support and Resistance Chart
    try:
        sr_data = stock_data[['Close', 'Support', 'Resistance']][-60:].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=sr_data.index, y=sr_data['Close'], mode='lines', name='Close Price', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=sr_data.index, y=sr_data['Support'], mode='lines', name='Support', line=dict(color='green', dash='dash')))
        fig.add_trace(go.Scatter(x=sr_data.index, y=sr_data['Resistance'], mode='lines', name='Resistance', line=dict(color='red', dash='dash')))
        fig.update_layout(
            title=f"{ticker} - Support and Resistance Levels",
            yaxis_title="Price",
            template="plotly_white"
        )
        analyses.append({
            "title": " Support and Resistance Levels",
            "description": "Identifies key price levels where the stock tends to reverse.",
            "note": "Support is a price floor; resistance is a price ceiling.",
            "chart": plotly_to_html(fig)
        })
    except Exception as e:
        logging.error(f"Support/Resistance Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " Support and Resistance Levels",
            "description": "Identifies key price levels.",
            "note": f"Failed to generate Support/Resistance chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # Stochastic Oscillator Chart
    try:
        stoch_data = stock_data[['%K', '%D']][-60:].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=stoch_data.index, y=stoch_data['%K'], mode='lines', name='%K', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=stoch_data.index, y=stoch_data['%D'], mode='lines', name='%D', line=dict(color='orange')))
        fig.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="Overbought (80)")
        fig.add_hline(y=20, line_dash="dash", line_color="green", annotation_text="Oversold (20)")
        fig.update_layout(
            title=f"{ticker} - Stochastic Oscillator (14, 3)",
            yaxis_title="Stochastic",
            yaxis_range=[0, 100],
            template="plotly_white"
        )
        analyses.append({
            "title": " Stochastic Oscillator",
            "description": "Compares closing price to price range over 14 days to detect overbought/oversold conditions.",
            "note": "Above 80 indicates overbought (sell signal); below 20 indicates oversold (buy signal).",
            "chart": plotly_to_html(fig)
        })
    except Exception as e:
        logging.error(f"Stochastic Oscillator Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " Stochastic Oscillator",
            "description": "Compares closing price to price range.",
            "note": f"Failed to generate Stochastic Oscillator chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # Moving Average Chart
    try:
        ma_data = stock_data[["Close", "MA"]][-60:].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ma_data.index, y=ma_data['Close'], mode='lines', name='Close Price', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=ma_data.index, y=ma_data['MA'], mode='lines', name=f'{ma}-Day MA', line=dict(color='orange', dash='dash')))
        fig.update_layout(
            title=f"{ticker} - Moving Average",
            yaxis_title="Price",
            template="plotly_white"
        )
        analyses.append({
            "title": " Moving Average",
            "description": "Smooths price data to identify trends over a specified period.",
            "note": "The stock price above the moving average suggests an uptrend; below suggests a downtrend.",
            "chart": plotly_to_html(fig)
        })
    except Exception as e:
        logging.error(f"Moving Average Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " Moving Average",
            "description": "Smooths price data to identify trends.",
            "note": f"Failed to generate Moving Average chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # Bollinger Bands Chart
    try:
        bb_data = stock_data[["Close", "Middle", "Upper", "Lower"]][-60:].dropna()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=bb_data.index, y=bb_data['Close'], mode='lines', name='Close Price', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=bb_data.index, y=bb_data['Upper'], mode='lines', name='Upper Band', line=dict(color='red', dash='dash')))
        fig.add_trace(go.Scatter(x=bb_data.index, y=bb_data['Lower'], mode='lines', name='Lower Band', line=dict(color='green', dash='dash')))
        fig.add_trace(go.Scatter(x=bb_data.index, y=bb_data['Upper'], mode='lines', name='Band Fill', fill='tonexty', fillcolor='rgba(128, 128, 128, 0.2)', line=dict(color='rgba(255,255,255,0)')))
        fig.update_layout(
            title=f"{ticker} - Bollinger Bands",
            yaxis_title="Price",
            template="plotly_white"
        )
        analyses.append({
            "title": " Bollinger Bands",
            "description": "Measures volatility using a moving average and standard deviations.",
            "note": "Price touching the upper band may indicate overbought conditions; touching the lower band may indicate oversold conditions.",
            "chart": plotly_to_html(fig)
        })
    except Exception as e:
        logging.error(f"Bollinger Bands Chart Error for {ticker}: {str(e)}")
        analyses.append({
            "title": " Bollinger Bands",
            "description": "Measures volatility.",
            "note": f"Failed to generate Bollinger Bands chart: {str(e)}",
            "chart": "<p>Chart failed to generate.</p>"
        })

    # ARIMA Forecast
    train_size = int(len(stock_data) * 0.8)
    if train_size >= 30:
        train, test = stock_data["Log_Close"][:train_size], stock_data["Log_Close"][train_size:]
        try:
            result = adfuller(train)
            p_value = result[1]
            d = 1 if p_value <= 0.05 else 2
            p_range = range(0, 3)
            d_range = range(d, d+1)
            q_range = range(0, 3)
            best_order = optimize_arima(train, p_range, d_range, q_range)
            if best_order is None:
                raise ValueError("No suitable ARIMA parameters found")

            model = ARIMA(train, order=best_order)
            model_fit = model.fit()
            forecast_log = model_fit.forecast(steps=len(test))
            forecast = np.exp(forecast_log)
            test_actual = np.exp(test)
            forecast_index = test.index

            arima_mae = mean_absolute_error(test_actual, forecast)
            arima_rmse = np.sqrt(mean_squared_error(test_actual, forecast))

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data["Close"], mode='lines', name='Historical', line=dict(color='blue', width=1)))
            fig.add_trace(go.Scatter(x=train.index, y=np.exp(train), mode='lines', name='Train', line=dict(color='green')))
            fig.add_trace(go.Scatter(x=test.index, y=test_actual, mode='lines', name='Test', line=dict(color='orange')))
            fig.add_trace(go.Scatter(x=forecast_index, y=forecast, mode='lines', name='Forecast', line=dict(color='red', dash='dash')))
            fig.add_vline(x=train.index[-1], line_dash="dash", line_color="black")
            fig.update_layout(
                title=f"{ticker} - ARIMA Forecast (Order: {best_order})",
                yaxis_title="Price",
                template="plotly_white"
            )
            analyses.append({
                "title": f" ARIMA Forecast (MAE: {arima_mae:.2f}, RMSE: {arima_rmse:.2f})",
                "description": "Predicts future prices using historical data with an ARIMA model.",
                "note": "Lower MAE/RMSE indicates better forecast accuracy.",
                "chart": plotly_to_html(fig)
            })
        except Exception as e:
            logging.error(f"ARIMA Error for {ticker}: {str(e)}")
            analyses.append({
                "title": " ARIMA Forecast",
                "description": "Predicts future prices using historical data.",
                "note": f"Failed to generate ARIMA forecast: {str(e)}",
                "chart": "<p>Chart failed to generate.</p>"
            })
    else:
        analyses.append({
            "title": " ARIMA Forecast",
            "description": "Predicts future prices using historical data.",
            "note": "Not enough data for forecasting (need at least 30 points).",
            "chart": "<p>Not enough data.</p>"
        })

    # SARIMA Forecast
    if train_size >= 30:
        try:
            result = adfuller(train)
            p_value = result[1]
            d = 1 if p_value <= 0.05 else 2
            D = 1
            p_range = range(0, 2)
            d_range = range(d, d+1)
            q_range = range(0, 2)
            P_range = range(0, 2)
            D_range = range(D, D+1)
            Q_range = range(0, 2)
            s = 5
            best_params = optimize_sarima(train, p_range, d_range, q_range, P_range, D_range, Q_range, s)
            if best_params is None:
                raise ValueError("No suitable SARIMA parameters found")

            p, d, q, P, D, Q = best_params
            model = SARIMAX(train, order=(p, d, q), seasonal_order=(P, D, Q, s))
            model_fit = model.fit(disp=False)
            forecast_log = model_fit.forecast(steps=len(test))
            forecast = np.exp(forecast_log)
            test_actual = np.exp(test)
            forecast_index = test.index

            sarima_mae = mean_absolute_error(test_actual, forecast)
            sarima_rmse = np.sqrt(mean_squared_error(test_actual, forecast))

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data["Close"], mode='lines', name='Historical', line=dict(color='blue', width=1)))
            fig.add_trace(go.Scatter(x=train.index, y=np.exp(train), mode='lines', name='Train', line=dict(color='green')))
            fig.add_trace(go.Scatter(x=test.index, y=test_actual, mode='lines', name='Test', line=dict(color='orange')))
            fig.add_trace(go.Scatter(x=forecast_index, y=forecast, mode='lines', name='Forecast', line=dict(color='purple', dash='dash')))
            fig.add_vline(x=train.index[-1], line_dash="dash", line_color="black")
            fig.update_layout(
                title=f"{ticker} - SARIMA Forecast (Order: ({p},{d},{q})({P},{D},{Q},{s}))",
                yaxis_title="Price",
                template="plotly_white"
            )
            analyses.append({
                "title": f" SARIMA Forecast (MAE: {sarima_mae:.2f}, RMSE: {sarima_rmse:.2f})",
                "description": "Seasonal ARIMA model for forecasting, capturing seasonal patterns.",
                "note": "Captures seasonal patterns in price data.",
                "chart": plotly_to_html(fig)
            })
        except Exception as e:
            logging.error(f"SARIMA Error for {ticker}: {str(e)}")
            analyses.append({
                "title": " SARIMA Forecast",
                "description": "Seasonal ARIMA model for forecasting.",
                "note": f"Failed to generate SARIMA forecast: {str(e)}",
                "chart": "<p>Chart failed to generate.</p>"
            })
    else:
        analyses.append({
            "title": " SARIMA Forecast",
            "description": "Seasonal ARIMA model for forecasting.",
            "note": "Not enough data for forecasting (need at least 30 points).",
            "chart": "<p>Not enough data.</p>"
        })

    # Correlation Heatmap
    if len(compare_stocks) > 1:
        try:
            df = pd.DataFrame()
            for s in compare_stocks:
                prices = yf.Ticker(s).history(period="1y")["Close"]
                if not prices.empty:
                    df[s] = prices
            if not df.empty and df.shape[1] >= 2:
                df = df.dropna()
                corr = df.corr()
                fig = px.imshow(
                    corr,
                    text_auto=True,
                    color_continuous_scale='RdBu_r',
                    title="Market Correlation"
                )
                analyses.append({
                    "title": " Market Correlation",
                    "description": "Shows how the stock moves relative to other selected stocks.",
                    "note": "Values close to 1 indicate strong positive correlation; close to -1 indicate negative correlation.",
                    "chart": plotly_to_html(fig)
                })
            else:
                analyses.append({
                    "title": " Market Correlation",
                    "description": "Shows how the stock moves relative to other selected stocks.",
                    "note": "Not enough data to compute correlation.",
                    "chart": "<p>Not enough data.</p>"
                })
        except Exception as e:
            logging.error(f"Correlation Chart Error for {ticker}: {str(e)}")
            analyses.append({
                "title": " Market Correlation",
                "description": "Shows how the stock moves relative to other selected stocks.",
                "note": f"Failed to generate Correlation chart: {str(e)}",
                "chart": "<p>Chart failed to generate.</p>"
            })
    else:
        analyses.append({
            "title": " Market Correlation",
            "description": "Shows how the stock moves relative to other selected stocks.",
            "note": "Select at least two stocks to compare.",
            "chart": "<p>Select more stocks to compare.</p>"
        })

    # Quantitative Risk Analysis
    returns = stock_data['Close'].pct_change().dropna()
    var_95 = calculate_var(returns, confidence_level=0.95)
    beta = calculate_beta(stock_data, market_data)
    capm = calculate_capm(beta)
    std_dev = calculate_standard_deviation(returns)
    current_price = stock_data['Close'][-1]
    stop_loss = current_price * 0.95
    target_price = current_price * 1.10
    risk_reward = calculate_risk_reward(stock_data, current_price, stop_loss, target_price)

    quantitative_html = f"""
        <div>
        <p>Value at Risk (VaR, 95%): {var_95:.2f}% - Potential loss at 95% confidence level.</p>
        <p>Beta: {beta:.2f} - Measures volatility relative to the market (S&P 500).</p>
        <p>CAPM Expected Return: {capm:.2f}% - Expected return based on market risk.</p>
        <p>Standard Deviation: {std_dev:.2f}% - Annualized volatility of returns.</p>
        <p>Risk/Reward Ratio: {risk_reward:.2f} - Compares potential loss to gain.</p>
        </div>
    """
    analyses.append({
        "title": " Quantitative Risk Analysis",
        "description": "Evaluates financial risk metrics to assess potential losses and volatility.",
        "note": "Provides key risk metrics for investment decision-making.",
        "chart": quantitative_html
    })

    # Qualitative Risk Analysis
    pe_ratio = get_pe_ratio(ticker)
    sentiment = estimate_market_sentiment(stock_data)
    risk_recommendation = risk_tolerance_recommendation(risk_tolerance, beta)

    qualitative_html = f"""
        <div>
        <p>Fundamental Analysis - P/E Ratio: {pe_ratio:.2f} - High P/E may indicate overvaluation.</p>
        <p>Market Sentiment: {sentiment} - Reflects recent price trend (Bullish/Bearish/Neutral).</p>
        <p>Risk Tolerance Recommendation: {risk_recommendation} - Aligns stock with your risk profile.</p>
        </div>
    """
    analyses.append({
        "title": " Qualitative Risk Analysis",
        "description": "Assesses non-numerical factors affecting the stock's risk and potential.",
        "note": "Provides insights into fundamental and market sentiment factors.",
        "chart": qualitative_html
    })

    # Investment Recommendation
    recommendation = "Hold"
    buy_price = current_price
    sell_target = target_price
    expected_profit = ((sell_target - buy_price) / buy_price) * 100
    timeframe = "1-3 months"

    latest_rsi = stock_data['RSI'][-1] if 'RSI' in stock_data else 50
    latest_macd = stock_data['MACD'][-1] if 'MACD' in stock_data else 0
    latest_signal = stock_data['Signal'][-1] if 'Signal' in stock_data else 0
    latest_k = stock_data['%K'][-1] if '%K' in stock_data else 50
    latest_d = stock_data['%D'][-1] if '%D' in stock_data else 50
    latest_support = stock_data['Support'][-1] if 'Support' in stock_data else current_price * 0.9
    latest_resistance = stock_data['Resistance'][-1] if 'Resistance' in stock_data else current_price * 1.1

    if latest_rsi < 30 and latest_macd > latest_signal and latest_k < 20:
        recommendation = f"Buy {ticker}"
        buy_price = min(current_price, latest_support)
        sell_target = latest_resistance
        expected_profit = ((sell_target - buy_price) / buy_price) * 100
        timeframe = "1-2 months"
    elif latest_rsi > 70 and latest_macd < latest_signal and latest_k > 80:
        recommendation = f"Sell {ticker}"
        buy_price = current_price
        sell_target = current_price
        stop_loss = latest_support
        expected_profit = 0
        timeframe = "Immediate"
    if risk_tolerance == "low" and beta > 1:
        recommendation = f"Avoid {ticker} (High Volatility)"
        buy_price = 0
        sell_target = 0
        stop_loss = 0
        expected_profit = 0
        timeframe = "N/A"

    recommendation_html = f"""
        <div>
        <p><strong>Recommendation:</strong> {recommendation}</p>
        <p><strong>Buy Price:</strong> {buy_price:.2f} USD</p>
        <p><strong>Sell Target:</strong> {sell_target:.2f} USD</p>
        <p><strong>Stop Loss:</strong> {stop_loss:.2f} USD</p>
        <p><strong>Expected Profit:</strong> {expected_profit:.2f}%</p>
        <p><strong>Timeframe:</strong> {timeframe}</p>
        </div>
    """
    analyses.append({
        "title": " Investment Recommendation",
        "description": "Provides a trading recommendation based on technical and risk analysis.",
        "note": "Combines technical indicators and risk analysis to suggest buy/sell actions.",
        "chart": recommendation_html
    })

    current_page = int(request.args.get("page", 0))
    if current_page < 0:
        current_page = 0
    if current_page >= len(analyses):
        current_page = len(analyses) - 1

    return render_template_string(
        result_html,
        ticker=ticker,
        analyses=analyses,
        current_analysis=analyses[current_page],
        current_page=current_page,
        stock_list=session['stock_list']
    )

# Step 13: Start Flask + ngrok in Colab
def terminate_existing_ngrok_sessions():
    try:
        ngrok.kill()
        logging.info("Terminated existing ngrok sessions via ngrok.kill()")
        subprocess.run(["pkill", "-9", "ngrok"], check=False)
        logging.info("Forcefully killed ngrok processes using pkill")
        time.sleep(3)
    except Exception as e:
        logging.warning(f"Failed to terminate existing ngrok sessions: {str(e)}")

def terminate_existing_port_processes(port):
    try:
        result = subprocess.run(["lsof", "-i", f":{port}", "-t"], capture_output=True, text=True)
        pids = result.stdout.strip().split("\n")
        for pid in pids:
            if pid:
                subprocess.run(["kill", "-9", pid], check=False)
                logging.info(f"Killed process {pid} using port {port}")
        time.sleep(2)
    except Exception as e:
        logging.warning(f"Failed to terminate processes on port {port}: {str(e)}")

def run_app(port):
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def start_ngrok(port):
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
    if not NGROK_AUTH_TOKEN:
        raise ValueError("NGROK_AUTH_TOKEN not set in environment variables")
    
    terminate_existing_ngrok_sessions()
    
    try:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)
        conf.get_default().max_concurrent_sessions = 1
        public_url = ngrok.connect(port, bind_tls=True)
        print(f"🚀 Your Flask app is live here: {public_url}")
        return public_url
    except Exception as e:
        logging.error(f"Failed to start ngrok: {str(e)}")
        raise

# Step 14: Launch in Colab
if __name__ == "__main__":
    try:
        port = find_available_port(start_port=5000)
        print(f"Using port {port} for Flask app")
    except RuntimeError as e:
        print(f"Error: {str(e)}")
        print("Please restart the Colab runtime and try again.")
        raise

    terminate_existing_port_processes(port)

    flask_thread = Thread(target=run_app, args=(port,))
    flask_thread.daemon = True
    flask_thread.start()
    
    time.sleep(5)
    
    try:
        public_url = start_ngrok(port)
        print(f"Click the link above to access the Stock Dashboard: {public_url}")
    except Exception as e:
        print(f"Failed to start the application: {str(e)}")
        print("Please try restarting the Colab runtime or check your ngrok account for active sessions.")
