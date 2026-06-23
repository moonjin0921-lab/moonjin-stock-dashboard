import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="문진 투자 대시보드", layout="wide")

st.title("📈 문진 투자 대시보드")

stocks = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "HD한국조선해양": "009540.KS",
    "에코프로비엠": "247540.KQ",
    "리노공업": "058470.KQ",
    "CMTX": "388210.KQ"
}

st.sidebar.header("내 보유 정보 입력")

buy_prices = {}
quantities = {}

for name in stocks.keys():
    st.sidebar.subheader(name)
    buy_prices[name] = st.sidebar.number_input(
        f"{name} 매수가",
        min_value=0,
        value=0,
        step=1000,
        key=f"{name}_buy"
    )
    quantities[name] = st.sidebar.number_input(
        f"{name} 보유수량",
        min_value=0,
        value=0,
        step=1,
        key=f"{name}_qty"
    )

result = []

for name, ticker in stocks.items():
    data = yf.download(
        ticker,
        period="5d",
        progress=False,
        auto_adjust=True
    )

    if data.empty:
        result.append([name, ticker, "-", "-", "-", "-", "-", "-"])
        continue

    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    if len(close) < 2:
        result.append([name, ticker, "-", "-", "-", "-", "-", "-"])
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
        profit_rate = (profit_amount / invested_amount) * 100
    else:
        invested_amount = 0
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
    columns=[
        "종목",
        "코드",
        "현재가",
        "전일대비(%)",
        "매수가",
        "보유수량",
        "평가금액",
        "평가손익",
        "수익률(%)"
    ]
)

def color_rate(value):
    if value == "-" or isinstance(value, str):
        return ""
    if value > 0:
        return "color: red"
    elif value < 0:
        return "color: blue"
    return ""

st.subheader("📌 관심종목 / 내 보유 현황")

st.dataframe(
    df.style.map(
        color_rate,
        subset=["전일대비(%)", "평가손익", "수익률(%)"]
    ),
    use_container_width=True
)

total_invested = 0
total_current = 0

for name in stocks.keys():
    buy_price = buy_prices[name]
    qty = quantities[name]

    if buy_price > 0 and qty > 0:
        row = df[df["종목"] == name]
        if not row.empty and row.iloc[0]["현재가"] != "-":
            current_price = row.iloc[0]["현재가"]
            total_invested += buy_price * qty
            total_current += current_price * qty

total_profit = total_current - total_invested

if total_invested > 0:
    total_profit_rate = (total_profit / total_invested) * 100
else:
    total_profit_rate = 0

st.divider()

col1, col2, col3 = st.columns(3)

col1.metric("총 투자금", f"{int(total_invested):,}원")
col2.metric("현재 평가금액", f"{int(total_current):,}원")
col3.metric("총 수익률", f"{total_profit_rate:.2f}%")

st.divider()

st.subheader("📊 종목별 차트")

selected_name = st.selectbox("차트 볼 종목 선택", list(stocks.keys()))

period = st.radio(
    "차트 기간 선택",
    ["1mo", "3mo", "6mo", "1y"],
    horizontal=True
)

chart_data = yf.download(
    stocks[selected_name],
    period=period,
    progress=False,
    auto_adjust=True
)

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

    fig = px.line(
        chart_df,
        x="날짜",
        y="종가",
        title=f"{selected_name} 주가 차트"
    )

    st.plotly_chart(fig, use_container_width=True)