import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import urllib.parse
import xml.etree.ElementTree as ET
import requests

try:
    from pykrx import stock
except:
    stock = None

st.set_page_config(page_title="문진 투자 대시보드", layout="wide")
st.title("📈 문진 투자 대시보드")

stocks = {
    "삼성전자": {"yf": "005930.KS", "krx": "005930"},
    "SK하이닉스": {"yf": "000660.KS", "krx": "000660"},
    "HD한국조선해양": {"yf": "009540.KS", "krx": "009540"},
    "에코프로비엠": {"yf": "247540.KQ", "krx": "247540"},
    "리노공업": {"yf": "058470.KQ", "krx": "058470"},
    "CMTX": {"yf": "388210.KQ", "krx": "388210"},
}

st.sidebar.header("내 보유 정보 입력")

buy_prices = {}
quantities = {}

for name in stocks.keys():
    st.sidebar.subheader(name)
    buy_prices[name] = st.sidebar.number_input(f"{name} 매수가", min_value=0, value=0, step=1000, key=f"{name}_buy")
    quantities[name] = st.sidebar.number_input(f"{name} 보유수량", min_value=0, value=0, step=1, key=f"{name}_qty")

result = []

for name, codes in stocks.items():
    ticker = codes["yf"]

    data = yf.download(ticker, period="5d", progress=False, auto_adjust=True)

    if data.empty:
        result.append([name, ticker, "-", "-", buy_prices[name], quantities[name], 0, 0, "-"])
        continue

    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    if len(close) < 2:
        result.append([name, ticker, "-", "-", buy_prices[name], quantities[name], 0, 0, "-"])
        continue

    current_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    daily_change_rate = ((current_price - prev_price) / prev_price) * 100

    buy_price = buy_prices[name]
    qty = quantities[name]

    if buy_price > 0 and qty > 0:
        invested_amount = buy_price * qty
        current_amount = current_price * qty
        profit_amount = current_amount - invested_amount
        profit_rate = profit_amount / invested_amount * 100
    else:
        current_amount = 0
        profit_amount = 0
        profit_rate = "-"

    result.append([
        name,
        ticker,
        int(current_price),
        round(daily_change_rate, 2),
        buy_price,
        qty,
        int(current_amount),
        int(profit_amount),
        round(profit_rate, 2) if profit_rate != "-" else "-"
    ])

df = pd.DataFrame(
    result,
    columns=["종목", "코드", "현재가", "전일대비(%)", "매수가", "보유수량", "평가금액", "평가손익", "수익률(%)"]
)

def color_rate(value):
    if isinstance(value, str):
        return ""
    if value > 0:
        return "color: red"
    elif value < 0:
        return "color: blue"
    return ""

st.subheader("📌 관심종목 / 내 보유 현황")

st.dataframe(
    df.style.map(color_rate, subset=["전일대비(%)", "평가손익", "수익률(%)"]),
    use_container_width=True
)

total_invested = sum(buy_prices[name] * quantities[name] for name in stocks.keys())
total_current = df["평가금액"].sum()
total_profit = total_current - total_invested
total_profit_rate = total_profit / total_invested * 100 if total_invested > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("총 투자금", f"{int(total_invested):,}원")
col2.metric("현재 평가금액", f"{int(total_current):,}원")
col3.metric("평가손익", f"{int(total_profit):,}원")
col4.metric("총 수익률", f"{total_profit_rate:.2f}%")

st.divider()

# 3. 보유 종목 비중 원형 차트
st.subheader("🥧 보유 종목 비중")

portfolio_df = df[df["평가금액"] > 0]

if portfolio_df.empty:
    st.info("매수가와 보유수량을 입력하면 보유 비중 차트가 표시됩니다.")
else:
    fig_pie = px.pie(
        portfolio_df,
        names="종목",
        values="평가금액",
        title="내 포트폴리오 비중"
    )
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# 4. 총 자산 추이 그래프
st.subheader("📈 총 자산 추이")

period_asset = st.radio("총 자산 추이 기간", ["1mo", "3mo", "6mo", "1y"], horizontal=True)

asset_history = None

for name, codes in stocks.items():
    qty = quantities[name]

    if qty <= 0:
        continue

    hist = yf.download(codes["yf"], period=period_asset, progress=False, auto_adjust=True)

    if hist.empty:
        continue

    close = hist["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    value_series = close * qty
    value_series.name = name

    if asset_history is None:
        asset_history = value_series.to_frame()
    else:
        asset_history = asset_history.join(value_series, how="outer")

if asset_history is None:
    st.info("보유수량을 입력하면 총 자산 추이 그래프가 표시됩니다.")
else:
    asset_history = asset_history.fillna(method="ffill")
    asset_history["총 자산"] = asset_history.sum(axis=1)

    asset_chart_df = pd.DataFrame({
        "날짜": asset_history.index,
        "총 자산": asset_history["총 자산"].values
    })

    fig_asset = px.line(
        asset_chart_df,
        x="날짜",
        y="총 자산",
        title="내 보유 종목 기준 총 자산 추이"
    )

    st.plotly_chart(fig_asset, use_container_width=True)

st.divider()

# 종목별 차트
st.subheader("📊 종목별 주가 차트")

selected_name = st.selectbox("차트 볼 종목 선택", list(stocks.keys()))
period = st.radio("주가 차트 기간", ["1mo", "3mo", "6mo", "1y"], horizontal=True)

chart_data = yf.download(stocks[selected_name]["yf"], period=period, progress=False, auto_adjust=True)

if chart_data.empty:
    st.warning("차트 데이터를 불러오지 못했습니다.")
else:
    close_chart = chart_data["Close"]
    if isinstance(close_chart, pd.DataFrame):
        close_chart = close_chart.iloc[:, 0]

    chart_df = pd.DataFrame({
        "날짜": close_chart.index,
        "종가": close_chart.values
    })

    fig = px.line(chart_df, x="날짜", y="종가", title=f"{selected_name} 주가 차트")
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# 2. 외국인 / 기관 수급
st.subheader("🏦 외국인 / 기관 수급")

if stock is None:
    st.warning("pykrx가 설치되지 않았습니다. requirements.txt에 pykrx를 추가하세요.")
else:
    selected_supply = st.selectbox("수급 볼 종목 선택", list(stocks.keys()), key="supply_select")

    end_date = datetime.today()
    start_date = end_date - timedelta(days=14)

    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    krx_code = stocks[selected_supply]["krx"]

    try:
        supply = stock.get_market_trading_value_by_date(start, end, krx_code)

        if supply.empty:
            st.info("수급 데이터를 불러오지 못했습니다.")
        else:
            supply = supply.reset_index()

            display_cols = ["날짜"]
            for col in ["기관합계", "외국인합계", "개인"]:
                if col in supply.columns:
                    display_cols.append(col)

            st.dataframe(supply[display_cols].tail(10), use_container_width=True)

            chart_cols = [col for col in ["기관합계", "외국인합계"] if col in supply.columns]

            if chart_cols:
                fig_supply = px.line(
                    supply,
                    x="날짜",
                    y=chart_cols,
                    title=f"{selected_supply} 외국인 / 기관 순매수 추이"
                )
                st.plotly_chart(fig_supply, use_container_width=True)

    except Exception as e:
        st.warning(f"수급 데이터를 불러오지 못했습니다: {e}")

st.divider()

# 1. 뉴스 자동 표시
st.subheader("📰 관심종목 뉴스")

selected_news = st.selectbox("뉴스 볼 종목 선택", list(stocks.keys()), key="news_select")

query = urllib.parse.quote(selected_news + " 주식")
rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"

try:
    response = requests.get(rss_url, timeout=5)
    root = ET.fromstring(response.content)

    items = root.findall(".//item")

    if not items:
        st.info("뉴스를 찾지 못했습니다.")
    else:
        for item in items[:5]:
            title = item.find("title").text
            link = item.find("link").text
            pub_date = item.find("pubDate").text

            st.markdown(f"**[{title}]({link})**")
            st.caption(pub_date)

except Exception as e:
    st.warning(f"뉴스를 불러오지 못했습니다: {e}")