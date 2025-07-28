import streamlit as st
import pandas as pd
import os
from datetime import date, datetime
import FinanceDataReader as fdr
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import BollingerBands

# ---------------------------
# 초기 설정
# ---------------------------
INITIAL_CAPITAL = 147449  # 147,449달러(2억원)
FEE_RATE = 0.002  # 수수료 0.2%
EXCHANGE_RATE = 1379.1

# ---------------------------
# 필요한 데이터 불러오기
# ---------------------------

# 투자 종목 로드
spx_data = pd.read_csv('./data/해외계좌_투자대상_개별종목.csv',encoding='cp949')
spx_data['티커'] = spx_data['티커'].apply(lambda x: x.split()[0])
ticker_list = spx_data['티커'].tolist()

# 거래 로그 로드
if "trading_log" not in st.session_state:
    if os.path.exists("./data/trading_log_us.csv"):
        st.session_state.trading_log = pd.read_csv("./data/trading_log_us.csv", dtype={"티커": str}, parse_dates=["거래일"])
    else:
        st.session_state.trading_log = pd.DataFrame(columns=["티커", "이름", "거래일", "거래유형","구분", "거래수량", "평균단가", "금액"])
st.session_state.trading_log["거래일"] = pd.to_datetime(st.session_state.trading_log["거래일"], format="mixed")


# 종가 정보 로드
tickers = st.session_state.trading_log ["티커"].astype(str).unique()
start_date = date(2025, 1, 1)
end_date = datetime.today().date()
price_dict = {}
for symbol in tickers:
    try:
        data = fdr.DataReader(symbol, start=start_date.isoformat(), end=end_date.isoformat())
        price_dict[symbol] = data
    except:
        st.warning(f"{symbol} 가격 데이터를 불러오는 데 실패했습니다.")
        price_dict[symbol] = None

# ---------------------------
# 함수 정의
# ---------------------------

# 투자수익률 계산 함수 
# -> output ['구분','티커','이름','매수일','평균단가','현재가','평가손익','투자수익률(%)','보유수량','현재평가금액]
def calc_profit(df,apply_fee):
    result = []
    grouped = df.sort_values("거래일").groupby(['구분',"티커"])

    for ticker, group in grouped:
        ticker = ticker[1]
        position = []  # 보유 중인 매수 거래들
        buy_date = None  # 현재 포지션에 해당하는 매수일
        end_price = price_dict[ticker]["Close"].iloc[-1]

        for _, row in group.iterrows():
            if row["거래유형"] == "매수":
                cost = row["금액"]
                fee = int(row["금액"] * FEE_RATE)
                cost_fee = row["금액"] + fee

                if not position:  # 새롭게 포지션 시작
                    buy_date = row["거래일"]

                position.append([row["거래수량"], cost, cost_fee])

            elif row["거래유형"] == "매도":
                sell_qty = row["거래수량"]
                while sell_qty > 0 and position:
                    qty, amt, amt_fee = position[0]
                    if qty > sell_qty:
                        portion = sell_qty / qty
                        position[0][0] -= sell_qty
                        position[0][1] -= amt * portion
                        position[0][2] -= amt_fee * portion
                        sell_qty = 0
                    else:
                        sell_qty -= qty
                        position.pop(0)

                if not position:
                    buy_date = None  # 포지션 청산 → 다음 매수에서 다시 설정

        remaining_quantity = sum(q for q, _, __ in position)
        if remaining_quantity == 0:
            continue

        total_cost = sum(amt for _, amt, __ in position)
        total_cost_fee = sum(amt_fee for _, __, amt_fee in position)
        average_price = total_cost / remaining_quantity

        eval_value = end_price * remaining_quantity        
        profit = eval_value - total_cost
        total_return = profit / total_cost if total_cost else 0
        if apply_fee:    
            profit = eval_value - total_cost_fee - int(eval_value * FEE_RATE)
            total_return = profit / total_cost_fee if total_cost_fee else 0

        result.append({
            '구분': group["구분"].iloc[-1],
            "티커": ticker,
            "이름": group["이름"].iloc[-1],
            "매수일": buy_date.strftime("%Y-%m-%d") if buy_date else None,
            "평균단가": f'{int(average_price):,}',
            "현재가": f'{int(end_price):,}',
            "평가손익": f"{int(profit):,}",
            "투자수익률(%)": round(total_return * 100, 2),
            "보유수량": int(remaining_quantity),
            "현재평가금액": f"{int(eval_value):,}"
        })

    return pd.DataFrame(result)

# 남은 예수금 계산 
def get_remaining_cash(trading_log):
    cash = INITIAL_CAPITAL
    for _, row in trading_log.iterrows():
        fee = int(row["금액"] * FEE_RATE)
        if row["거래유형"] == "매수":
            cash -= (row["금액"] + fee)
        elif row["거래유형"] == "매도":
            cash += (row["금액"] - fee)
    return cash

# ---------------------------
# 초기 페이지 설정
# ---------------------------

st.set_page_config(page_title="해외계좌 투자 대시보드", layout="wide")
st.title("💹 투자 대시보드")
page = st.sidebar.radio("메뉴 선택", ["매수/매도 정보 입력", "수익률 계산", "투자비중 분석", "목표수익률 및 지표 확인"])

# ---------------------------
# Page1: 매수/매도 금액 입력 (검색 및 등록형)
# ---------------------------
if page == "매수/매도 정보 입력":
    st.subheader("매수/매도 정보 입력")

    # 티커 또는 이름 검색
    ticker_input = st.text_input("티커 입력")
    if ticker_input:        
        # try:
        if ticker_input in ticker_list:
            name = spx_data[spx_data["티커"] == ticker_input]['이름'].values[0]
            st.success(f"✅ {name} ({ticker_input}) 조회됨")

        # 거래 정보 입력
        col1, col2, col3 = st.columns(3)
        with col1:
            trade_type = st.selectbox("거래 유형", ["매수", "매도"])
        with col2:
            category = st.selectbox("종목 구분", ["지수구성", "개별종목"])
        with col3:
            trade_date = st.date_input("거래일", value=date.today())

        col4, col5 = st.columns(2)
        with col4:
            quantity = st.number_input("거래 수량 (주)", min_value=0)
        with col5:
            amount = st.number_input("거래 금액 ($)", min_value=0.0, format="%.2f")

        if st.button("거래로그에 추가"):
            existing = st.session_state.trading_log
            if trade_type == "매수":
                new_entry = pd.DataFrame.from_records([{
                            "구분": category,
                            "거래일": pd.to_datetime(trade_date).normalize(),
                            "티커": ticker_input,
                            "이름": name,
                            '거래유형': trade_type,
                            "거래수량": quantity,
                            "평균단가": round(amount/quantity, 2),
                            "금액": amount
                        }])
                st.session_state.trading_log = pd.concat([existing, new_entry], ignore_index=True)

            elif trade_type == "매도":
                total_buy = existing[(existing["티커"] == ticker_input) & (existing["거래유형"] == "매수")]["거래수량"].sum()
                total_sell = existing[(existing["티커"] == ticker_input) & (existing["거래유형"] == "매도")]["거래수량"].sum()
                available = total_buy - total_sell                    
                if quantity > available:
                    st.error(f"❌ 매도 가능 금액({available:,.2f}달러)를 초과했습니다.")
                    new_entry = None
                else:
                    new_entry = pd.DataFrame.from_records([{
                            "구분": category,
                            "거래일": pd.to_datetime(trade_date).normalize(),
                            "티커": ticker_input,
                            "이름": name,
                            '거래유형': trade_type,
                            "거래수량": quantity,
                            "평균단가": round(amount/quantity,2),
                            "금액": amount
                        }])
                    st.session_state.trading_log = pd.concat([existing, new_entry], ignore_index=True)

            if new_entry is not None:
                st.session_state.trading_log = (st.session_state.trading_log
                                                .groupby('티커')
                                                .apply(lambda x: x.sort_values(by='거래일'))
                                                .reset_index(drop=True))
                st.session_state.trading_log.to_csv("./data/trading_log_us.csv", index=False)
                st.success("✅ 거래 로그가 업데이트되고 저장되었습니다.")

        # except Exception as e:
        #     st.error(f"❌ 종목 정보를 불러올 수 없습니다: {e}")

    st.markdown("---")
    st.write("### 거래 기록")

    editable_log = st.session_state.trading_log.sort_values(by='거래일',axis=0).reset_index(drop=True)
    editable_log["거래일"] = pd.to_datetime(editable_log["거래일"]).dt.date
    editable_log["삭제"] = False  # 삭제용 체크박스 열 추가

    edited = st.data_editor(
        editable_log,
        column_config={
            "삭제": st.column_config.CheckboxColumn(label="선택", help="삭제할 거래를 선택하세요.")
        },
        disabled=["구분","거래일", "티커", "이름", "거래유형", "거래수량", "평균단가", "금액"],
        use_container_width=True
    )

    if st.button("선택한 거래 삭제"):
        to_delete = edited[edited["삭제"]]
        if not to_delete.empty:
            # 삭제할 행을 제외한 데이터로 갱신
            updated_log = edited[~edited["삭제"]].drop(columns=["삭제"])
            st.session_state.trading_log = updated_log
            st.session_state.trading_log.to_csv("./data/trading_log_us.csv", index=False)
            st.success(f"🗑️ {len(to_delete)}건의 거래가 삭제되었습니다.")
        else:
            st.warning("❗ 삭제할 거래를 선택하지 않았습니다.")

# ---------------------------
# Page2: 수익률 계산
# ---------------------------

if page == "수익률 계산":
    st.subheader("수익률 계산")
    trading_log = st.session_state.trading_log.copy()
    col1, col2 = st.columns([5, 1])  
    with col1:
        apply_fee = st.checkbox("수수료 적용 (0.2%)", value=True)
    with col2:
        st.markdown(f"**기준일:** {datetime.today().strftime('%Y-%m-%d')}")

    result_df = calc_profit(trading_log, apply_fee)
    result_df["현재평가금액_int"] = result_df["현재평가금액"].str.replace(",", "").astype(int)
    result_df = result_df.sort_values(by=['구분','현재평가금액_int'],ascending=False, axis=0).reset_index(drop=True)
    result_df = result_df.drop('현재평가금액_int',axis=1)
    st.dataframe(result_df)

    # 평가손익 총합 및 현재 자산 계산
    profit_sum = result_df["평가손익"].str.replace(",", "").astype(int).sum()
    eval_sum = result_df["현재평가금액"].str.replace(",", "").astype(int).sum()

    remain_cash = get_remaining_cash(trading_log)
    total_asset = eval_sum + remain_cash
    total_return = profit_sum / INITIAL_CAPITAL * 100

    col3, col4= st.columns([3, 1])
    with col3:
        st.markdown("#### 📊 전체 수익 요약")
    with col4:
        apply_KRW = st.checkbox(f"원화 적용({EXCHANGE_RATE}원/$)", value=False)

    col5, col6= st.columns(2)
    with col5:
        if apply_KRW:
            st.metric(label="💹 총 평가손익", value=f"{profit_sum*EXCHANGE_RATE:+,.0f}원")
        else:
            st.metric(label="💹 총 평가손익", value=f"{profit_sum:+,} $")
    with col6:
        st.metric(label="📈 전체 수익률", value=f"{total_return:.2f} %")

    col7, col8 = st.columns(2)
    with col7:
        if apply_KRW:
            st.metric(label="💸 현금", value=f"{remain_cash*EXCHANGE_RATE:,.0f}원")
        else:
            st.metric(label="💸 현금", value=f"${remain_cash:,.2f}")
    with col8:
        if apply_KRW:
            st.metric(label="💰 총 자산", value=f"{total_asset*EXCHANGE_RATE:,.0f}원")
        else:
            st.metric(label="💰 총 자산", value=f"${total_asset:,.2f}")

# ---------------------------
# Page3: 투자비중 분석
# ---------------------------
if page == "투자비중 분석":
    col1, col2 = st.columns([4, 1])  
    with col1:
        st.subheader("지수구성 투자비중")
    with col2:
        apply_KRW = st.checkbox(f"원화 적용({EXCHANGE_RATE}원/$)", value=False)
    trading_log = st.session_state.trading_log.copy()
    df = calc_profit(trading_log, apply_fee=True)[['구분','티커','이름','현재평가금액']]
    index_df = df.loc[df['구분']=='지수구성']
    index_df = index_df.drop('구분',axis=1)
    index_df['현재평가금액'] = index_df['현재평가금액'].str.replace(",", "").astype(int)

    remaining_cash= get_remaining_cash(trading_log)
    total_eval = df['현재평가금액'].str.replace(",", "").astype(int).sum()
    total_asset = remaining_cash + total_eval
    index_df['투자비중'] = index_df['현재평가금액'] / total_asset *100
    if apply_KRW:
        index_df['현재평가금액'] = index_df['현재평가금액'].apply(lambda x: f'{x*EXCHANGE_RATE:,.0f}원')
    else:
        index_df['현재평가금액'] = index_df['현재평가금액'].apply(lambda x: f'${x:,}')

    # 목표
    tgt_dict = {
    'NVDA': "9.25%",
    'MSFT': "8.86%",
    'AAPL': "7.22%",
    'AMZN': "5.70%",
    'GOOG': "5.20%",
    'META': "4.43%",
    'AVGO': "3.05%",
    'TSLA': "2.51%",
    'JPM': "1.92%",
    'WMT': "1.87%"
    }
    index_df["목표비율"] = index_df["티커"].map(tgt_dict).fillna("-")
    index_df = index_df.sort_values(by='투자비중',ascending=False).reset_index(drop=True)
    st.dataframe(index_df,
                column_config={
                    "투자비중": st.column_config.NumberColumn(
                        label="투자비중",
                        format="%.2f%%")})
    
    Individ_df =  df.loc[df['구분']=='개별종목']
    Individ_df = Individ_df.drop('구분',axis=1)
    Individ_df['현재평가금액'] = Individ_df['현재평가금액'].str.replace(",", "").astype(int)
    Individ_df['투자비중'] = Individ_df['현재평가금액'] / total_asset *100
    if apply_KRW:
        Individ_df['현재평가금액'] = Individ_df['현재평가금액'].apply(lambda x: f'{x*EXCHANGE_RATE:,.0f}원')
    else:
        Individ_df['현재평가금액'] = Individ_df['현재평가금액'].apply(lambda x: f'${x:,}')
    Individ_df = Individ_df.sort_values(by='투자비중',ascending=False).reset_index(drop=True)
    st.markdown('---')
    st.subheader("개별종목 투자비중")
    st.dataframe(Individ_df,
            column_config={
                "투자비중": st.column_config.NumberColumn(
                    label="투자비중",
                    format="%.2f%%")})

    
# ---------------------------
# Page4: 목표수익률 및 지표 확인
# ---------------------------
if page == "목표수익률 및 지표 확인":
    st.subheader("📈 목표 수익률 및 기술적 지표 분석")
    trading_log = st.session_state.trading_log.copy()
    col1, col2 = st.columns([5, 1])  
    with col1:
        apply_fee = st.checkbox("수수료 적용 (0.2%)", value=True)
    with col2:
        st.markdown(f"**기준일:** {datetime.today().strftime('%Y-%m-%d')}")
    profit_df = calc_profit(trading_log, apply_fee)[['구분','티커','이름','매수일','평가손익','투자수익률(%)']]
    profit_df = profit_df.loc[profit_df["구분"]=='개별종목']

    tech_indicator = []
    for ticker in profit_df['티커']:
        df = price_dict[ticker].copy()
        if df.empty:
            continue

        df['Return'] = df['Close'].pct_change()
        latest_price = df['Close'].iloc[-1]

        buy_date = profit_df.loc[profit_df['티커']==ticker]['매수일'].values[0]

        recent_window = df.loc[df.index <= buy_date]['Return'].dropna().iloc[-120:]
        avg_r_120 = recent_window.mean()

        r10_80 = max(avg_r_120 * 10 * 0.8, 0.04)
        r10_120 = max(avg_r_120 * 10 * 1.2, 0.06)
        r30_80 = max(avg_r_120 * 30 * 0.8, 0.04)
        r30_120 = max(avg_r_120 * 30 * 1.2, 0.06)
        r60_80 = max(avg_r_120 * 60 * 0.8, 0.04)
        r60_120 = max(avg_r_120 * 60 * 1.2, 0.06)

        tgt_80, tgt_120 = r30_80, r30_120
        exit_80, exit_120 = r30_80*(-0.5), r30_120*(-0.5)

        rsi = RSIIndicator(close=df['Close'], window=14).rsi().iloc[-1]
        rsi_signal = '과매수' if rsi > 70 else '과매도' if rsi < 30 else '중립'

        bb = BollingerBands(close=df['Close'], window=20, window_dev=2)
        bb_signal = '하단돌파(매수신호)' if df['Close'].iloc[-1] < bb.bollinger_lband().iloc[-1] else \
                    '상단돌파(매도경고)' if df['Close'].iloc[-1] > bb.bollinger_hband().iloc[-1] else '정상범위'

        adx = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14).adx().iloc[-1]
        adx_signal = '강한추세' if adx > 20 else '약한추세'

        tech_indicator.append({
            '티커': ticker,
            '목표수익률(80%)': tgt_80*100,
            '목표수익률(120%)': tgt_120*100,
            '손절가(80%)': exit_80*100,
            '손절가(120%)': exit_120*100,
            'RSI신호': rsi_signal,
            '볼린저밴드': bb_signal,
            'ADX신호': adx_signal
        })
    tech_indicator = pd.DataFrame(tech_indicator)
    result_df = pd.merge(profit_df, tech_indicator, on='티커' )
    result_df = result_df.sort_values('투자수익률(%)',axis=0, ascending=False).reset_index(drop=True)
    result_df = result_df.drop(['구분'],axis=1)
    def highlight_row(row):
        style = [''] * len(row)
        columns = row.index.tolist()

        if "투자수익률(%)" in columns and "목표수익률(80%)" in columns and "목표수익률(120%)" in columns:
            cur = row["투자수익률(%)"]
            if cur >= row["목표수익률(120%)"]:
                style[columns.index("투자수익률(%)")] = "background-color: mediumseagreen"
            elif cur >= row["목표수익률(80%)"]:
                style[columns.index("투자수익률(%)")] = "background-color: lightgreen"

        if "투자수익률(%)" in columns and "손절가(80%)" in columns and "손절가(120%)" in columns:
            cur = row["투자수익률(%)"]
            if cur <= row["손절가(80%)"]:
                style[columns.index("투자수익률(%)")] = "background-color: salmon"
            elif cur <= row["손절가(120%)"]:
                style[columns.index("투자수익률(%)")] = "background-color: lightcoral"

        if "RSI신호" in columns:
            if row["RSI신호"] == "과매수":
                style[columns.index("RSI신호")] = "background-color: lightcoral"
            elif row["RSI신호"] == "과매도":
                style[columns.index("RSI신호")] = "background-color: lightblue"

        if "볼린저밴드" in columns:
            if row["볼린저밴드"] == "하단돌파(매수신호)":
                style[columns.index("볼린저밴드")] = "background-color: lightblue"
            elif row["볼린저밴드"] == "상단돌파(매도경고)":
                style[columns.index("볼린저밴드")] = "background-color: lightcoral"

        if "ADX신호" in columns and row["ADX신호"] == "강한추세":
            style[columns.index("ADX신호")] = "background-color: lightgreen"

        return style
    
    st.dataframe(result_df.style.apply(highlight_row, axis=1),
                column_config={
                    "투자수익률(%)": st.column_config.NumberColumn(
                        label="투자수익률(%)",
                        format="%.2f%%"),
                    "손절가(80%)": st.column_config.NumberColumn(
                        label="손절가(80%)",
                        format="%.2f%%"),
                    "손절가(120%)": st.column_config.NumberColumn(
                        label="손절가(120%)",
                        format="%.2f%%"),
                    "목표수익률(80%)": st.column_config.NumberColumn(
                        label="목표수익률(80%)",
                        format="%.2f%%"),
                    "목표수익률(120%)": st.column_config.NumberColumn(
                        label="목표수익률(120%)",
                        format="%.2f%%")
                    },hide_index=True
                )