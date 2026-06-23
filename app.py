import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from supabase import create_client
from pykrx import stock
from datetime import datetime, timedelta
import requests
import urllib.parse
import xml.etree.ElementTree as ET

st.set_page_config(page_title="문진 투자 대시보드", layout="wide")
st.title("📈 문진 투자 대시보드")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

if "user" not in st.session_state:
    st.session_state.user = None

# 로그인
st.sidebar.header("로그인 / 회원가입")

email = st.sidebar.text_input("이메일")
password = st.sidebar.text_input("비밀번호", type="password")

login_col, signup_col = st.sidebar.columns(2)

with login_col:
    if st.button("로그인"):
        try:
            res = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state.user = res.user
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"로그인 실패: {e}")

with signup_col:
    if st.button("회원가입"):
        try:
            supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            st.sidebar.success("회원가입 완료. 이메일 인증 후 로그인하세요.")
        except Exception as e:
            st.sidebar.error(f"회원가입 실패: {e}")

if st.session_state.user is None:
    st.info("로그인하면 개인 포트폴리오를 저장할 수 있습니다.")
    st.stop()

if st.sidebar.button("로그아웃"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

user_id = st.session_state.user.id
st.sidebar.success(f"로그인 중: {st.session_state.user.email}")

# 종목 추가
st.sidebar.divider()
st.sidebar.header("종목 추가")

stock_name = st.sidebar.text_input("종목명", placeholder="예: 삼성전자")
stock_code = st.sidebar.text_input("종목코드", placeholder="예: 005930")
market = st.sidebar.selectbox("시장", ["코스피", "코스닥"])
buy_price = st.sidebar.number_input("매수가", min_value=0, value=0, step=1000)
quantity = st.sidebar.number_input("보유수량", min_value=0, value=0, step=1)

if st.sidebar.button("포트폴리오 저장"):
    if stock_name and stock_code:
        supabase.table("portfolios").insert({
            "user_id": user_id,
            "stock_name": stock_name,
            "stock_code": stock_code,
            "market": market,
            "buy_price": buy_price,
            "quantity": quantity
        }).execute()
        st.sidebar.success("저장 완료")
        st.rerun()
    else:
        st.sidebar.warning("종목명과 종목코드를 입력하세요.")

# 포트폴리오 불러오기
response = supabase.table("portfolios").select("*").eq("user_id", user_id).execute()
portfolio = response.data

st.subheader("📌 내 포트폴리오")

if not portfolio:
    st.info("왼쪽에서 종목을 추가하세요.")
else:
    result = []

    for item in portfolio:
        suffix = ".KS" if item["market"] == "코스피" else ".KQ"
        yf_code = item["stock_code"] + suffix

        price_data = yf.download(
            yf_code,
            period="5d",
            progress=False,
            auto_adjust=True
        )

        if price_data.empty:
            result.append([
                item["id"], item["stock_name"], item["stock_code"],
                "데이터 없음", "-", int(item["buy_price"]), int(item["quantity"]),
                0, 0, "-"
            ])
            continue

        close = price_data["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = close.dropna()

        if len(close) < 2:
            result.append([
                item["id"], item["stock_name"], item["stock_code"],
                "데이터 부족", "-", int(item["buy_price"]), int(item["quantity"]),
                0, 0, "-"
            ])
            continue

        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])

        daily_rate = ((current_price - prev_price) / prev_price) * 100

        invested = float(item["buy_price"]) * float(item["quantity"])
        current_value = current_price * float(item["quantity"])
        profit = current_value - invested
        profit_rate = (profit / invested * 100) if invested > 0 else 0

        result.append([
            item["id"],
            item["stock_name"],
            item["stock_code"],
            int(current_price),
            round(daily_rate, 2),
            int(item["buy_price"]),
            int(item["quantity"]),
            int(current_value),
            int(profit),
            round(profit_rate, 2)
        ])

    df = pd.DataFrame(result, columns=[
        "ID", "종목", "코드", "현재가", "전일대비(%)",
        "매수가", "보유수량", "평가금액", "평가손익", "수익률(%)"
    ])

    st.dataframe(df.drop(columns=["ID"]), use_container_width=True)

    numeric_df = df[df["현재가"].apply(lambda x: isinstance(x, int))]

    if not numeric_df.empty:
        total_invested = (numeric_df["매수가"] * numeric_df["보유수량"]).sum()
        total_current = numeric_df["평가금액"].sum()
        total_profit = total_current - total_invested
        total_rate = total_profit / total_invested * 100 if total_invested > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 투자금", f"{int(total_invested):,}원")
        c2.metric("평가금액", f"{int(total_current):,}원")
        c3.metric("평가손익", f"{int(total_profit):,}원")
        c4.metric("총 수익률", f"{total_rate:.2f}%")

        st.divider()

        st.subheader("🥧 보유 비중")
        pie_df = numeric_df[numeric_df["평가금액"] > 0]

        if not pie_df.empty:
            fig_pie = px.pie(
                pie_df,
                names="종목",
                values="평가금액",
                title="내 포트폴리오 비중"
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    st.subheader("삭제")
    delete_name = st.selectbox("삭제할 종목", df["종목"].tolist())

    if st.button("선택 종목 삭제"):
        target_id = int(df[df["종목"] == delete_name]["ID"].iloc[0])
        supabase.table("portfolios").delete().eq("id", target_id).execute()
        st.success("삭제 완료")
        st.rerun()

    st.divider()

    st.subheader("📊 종목별 차트")
    chart_name = st.selectbox("차트 볼 종목", df["종목"].tolist())

    chart_item = next(
        item for item in portfolio
        if item["stock_name"] == chart_name
    )

    chart_suffix = ".KS" if chart_item["market"] == "코스피" else ".KQ"
    chart_code = chart_item["stock_code"] + chart_suffix

    period = st.radio("차트 기간", ["1mo", "3mo", "6mo", "1y"], horizontal=True)

    chart_data = yf.download(
        chart_code,
        period=period,
        progress=False,
        auto_adjust=True
    )

    if chart_data.empty:
        st.warning("차트 데이터를 불러오지 못했습니다.")
    else:
        chart_close = chart_data["Close"]

        if isinstance(chart_close, pd.DataFrame):
            chart_close = chart_close.iloc[:, 0]

        chart_close = chart_close.dropna()

        chart_df = pd.DataFrame({
            "날짜": chart_close.index,
            "종가": chart_close.values
        })

        fig = px.line(
            chart_df,
            x="날짜",
            y="종가",
            title=f"{chart_name} 주가 차트"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("🏦 외국인 / 기관 수급")
    supply_name = st.selectbox("수급 볼 종목", df["종목"].tolist())

    supply_item = next(
        item for item in portfolio
        if item["stock_name"] == supply_name
    )

    end = datetime.today()
    start = end - timedelta(days=14)

    try:
        supply = stock.get_market_trading_value_by_date(
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            supply_item["stock_code"]
        )

        if supply.empty:
            st.info("수급 데이터가 없습니다.")
        else:
            supply = supply.reset_index()
            st.dataframe(supply.tail(10), use_container_width=True)

            cols = [c for c in ["기관합계", "외국인합계"] if c in supply.columns]

            if cols:
                fig_supply = px.line(
                    supply,
                    x="날짜",
                    y=cols,
                    title=f"{supply_name} 외국인 / 기관 순매수"
                )
                st.plotly_chart(fig_supply, use_container_width=True)

    except Exception as e:
        st.warning(f"수급 데이터를 불러오지 못했습니다: {e}")

st.divider()

st.subheader("📰 최근 증시 뉴스")

query = urllib.parse.quote("한국 증시 코스피 코스닥 반도체 조선 주식")
rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"

try:
    news_response = requests.get(rss_url, timeout=5)
    root = ET.fromstring(news_response.content)
    items = root.findall(".//item")

    for item in items[:8]:
        title = item.find("title").text
        link = item.find("link").text
        pub_date = item.find("pubDate").text

        st.markdown(f"**[{title}]({link})**")
        st.caption(pub_date)

except Exception as e:
    st.warning(f"뉴스를 불러오지 못했습니다: {e}")