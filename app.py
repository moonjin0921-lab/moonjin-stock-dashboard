import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="문진 투자 대시보드", layout="wide")

st.title("📈 나만의 투자 포트폴리오")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

st.sidebar.header("종목 추가")

stock_name = st.sidebar.text_input("종목명", placeholder="예: 삼성전자")
stock_code = st.sidebar.text_input("종목코드", placeholder="예: 005930")

market = st.sidebar.selectbox(
    "시장 선택",
    ["코스피", "코스닥"]
)

buy_price = st.sidebar.number_input(
    "매수가",
    min_value=0,
    value=0,
    step=1000
)

quantity = st.sidebar.number_input(
    "보유수량",
    min_value=0,
    value=0,
    step=1
)

if st.sidebar.button("종목 추가"):
    if stock_name == "" or stock_code == "":
        st.sidebar.warning("종목명과 종목코드를 입력해주세요.")
    else:
        suffix = ".KS" if market == "코스피" else ".KQ"
        yf_code = stock_code + suffix

        st.session_state.portfolio.append({
            "종목": stock_name,
            "코드": stock_code,
            "시장": market,
            "야후코드": yf_code,
            "매수가": buy_price,
            "보유수량": quantity
        })

        st.sidebar.success(f"{stock_name} 추가 완료!")

if st.sidebar.button("전체 삭제"):
    st.session_state.portfolio = []
    st.sidebar.success("포트폴리오를 비웠습니다.")

st.subheader("📌 내 포트폴리오")

if len(st.session_state.portfolio) == 0:
    st.info("왼쪽에서 종목을 추가하세요.")
else:
    result = []

    for item in st.session_state.portfolio:
        name = item["종목"]
        yf_code = item["야후코드"]
        buy_price = item["매수가"]
        qty = item["보유수량"]

        data = yf.download(
            yf_code,
            period="5d",
            progress=False,
            auto_adjust=True
        )

        if data.empty:
            result.append([
                name,
                item["코드"],
                item["시장"],
                "데이터 없음",
                buy_price,
                qty,
                0,
                0,
                "-"
            ])
            continue

        close = data["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        if len(close) < 2:
            result.append([
                name,
                item["코드"],
                item["시장"],
                "데이터 부족",
                buy_price,
                qty,
                0,
                0,
                "-"
            ])
            continue

        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])

        daily_change_rate = ((current_price - prev_price) / prev_price) * 100

        invested_amount = buy_price * qty
        current_amount = current_price * qty
        profit_amount = current_amount - invested_amount

        if invested_amount > 0:
            profit_rate = profit_amount / invested_amount * 100
        else:
            profit_rate = 0

        result.append([
            name,
            item["코드"],
            item["시장"],
            int(current_price),
            round(daily_change_rate, 2),
            buy_price,
            qty,
            int(current_amount),
            int(profit_amount),
            round(profit_rate, 2)
        ])

    df = pd.DataFrame(
        result,
        columns=[
            "종목",
            "코드",
            "시장",
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
        if isinstance(value, str):
            return ""
        if value > 0:
            return "color: red"
        elif value < 0:
            return "color: blue"
        return ""

    st.dataframe(
        df.style.map(
            color_rate,
            subset=["전일대비(%)", "평가손익", "수익률(%)"]
        ),
        use_container_width=True
    )

    total_invested = sum(item["매수가"] * item["보유수량"] for item in st.session_state.portfolio)
    total_current = df["평가금액"].sum()
    total_profit = total_current - total_invested
    total_profit_rate = total_profit / total_invested * 100 if total_invested > 0 else 0

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("총 투자금", f"{int(total_invested):,}원")
    col2.metric("현재 평가금액", f"{int(total_current):,}원")
    col3.metric("평가손익", f"{int(total_profit):,}원")
    col4.metric("총 수익률", f"{total_profit_rate:.2f}%")

    st.divider()

    st.subheader("🥧 보유 비중")

    portfolio_df = df[df["평가금액"] > 0]

    if not portfolio_df.empty:
        fig_pie = px.pie(
            portfolio_df,
            names="종목",
            values="평가금액",
            title="내 포트폴리오 비중"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    st.subheader("📊 종목별 차트")

    selected_stock = st.selectbox(
        "차트 볼 종목 선택",
        [item["종목"] for item in st.session_state.portfolio]
    )

    selected_item = next(
        item for item in st.session_state.portfolio
        if item["종목"] == selected_stock
    )

    period = st.radio(
        "차트 기간",
        ["1mo", "3mo", "6mo", "1y"],
        horizontal=True
    )

    chart_data = yf.download(
        selected_item["야후코드"],
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
            title=f"{selected_stock} 주가 차트"
        )

        st.plotly_chart(fig, use_container_width=True)