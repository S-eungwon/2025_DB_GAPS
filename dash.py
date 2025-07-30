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
INITIAL_CAPITAL_KR = 800000000  # 8억원
INITIAL_CAPITAL_US = 147449  # 147,449달러(2억원)
FEE_RATE_KR = 0.001  # 국내계좌 수수료 0.1%
FEE_RATE_US = 0.002  # 해외계좌 수수료 0.2%
EXCHANGE_RATE = 1379.1

# ---------------------------
# 필요한 데이터 불러오기
# ---------------------------

## 국내 계좌
# 투자 종목 로드
etf_data = pd.read_csv('./data/국내계좌_투자대상_ETF.csv')
ticker_list = etf_data['티커'].tolist()

# 거래 로그 로드
if "trading_log" not in st.session_state:
    if os.path.exists("./data/trading_log.csv"):
        st.session_state.trading_log = pd.read_csv("./data/trading_log.csv", dtype={"티커": str}, parse_dates=["거래일"])
    else:
        st.session_state.trading_log = pd.DataFrame(columns=["구분1", "구분2", "티커", "종목명", "거래일", "거래유형", "거래수량", "평균단가", "금액"])
st.session_state.trading_log["거래일"] = pd.to_datetime(st.session_state.trading_log["거래일"], format="mixed")


# 종가 정보 로드
tickers = st.session_state.trading_log ["티커"].astype(str).unique()
start_date = date(2025, 1, 1)
today = datetime.today().date()
price_dict_KR = {}
for symbol in tickers:
    try:
        data = fdr.DataReader(symbol, start=start_date.isoformat(), end=today.isoformat())
        end_date = data.index[-1].date()
        price_dict_KR[symbol] = data
    except:
        st.warning(f"{symbol} 가격 데이터를 불러오는 데 실패했습니다.")
        price_dict_KR[symbol] = None

## 해외 계좌
# 투자 종목 로드
spx_data = pd.read_csv('./data/해외계좌_투자대상_개별종목.csv',encoding='cp949')
spx_data['티커'] = spx_data['티커'].apply(lambda x: x.split()[0])
spx_ticker_list = spx_data['티커'].tolist()

# 거래 로그 로드
if "trading_log_us" not in st.session_state:
    if os.path.exists("./data/trading_log_us.csv"):
        st.session_state.trading_log_us = pd.read_csv("./data/trading_log_us.csv", dtype={"티커": str}, parse_dates=["거래일"])
    else:
        st.session_state.trading_log_us = pd.DataFrame(columns=["티커", "이름", "거래일", "거래유형","구분", "거래수량", "평균단가", "금액"])
st.session_state.trading_log_us["거래일"] = pd.to_datetime(st.session_state.trading_log_us["거래일"], format="mixed")


# 종가 정보 로드
tickers = st.session_state.trading_log_us ["티커"].astype(str).unique()
start_date = date(2025, 1, 1)
end_date = datetime.today().date()
price_dict_US = {}
for symbol in tickers:
    try:
        data = fdr.DataReader(symbol, start=start_date.isoformat(), end=end_date.isoformat())
        price_dict_US[symbol] = data
    except:
        st.warning(f"{symbol} 가격 데이터를 불러오는 데 실패했습니다.")
        price_dict_US[symbol] = None

# ---------------------------
# 함수 정의
# ---------------------------


# 남은 예수금 계산 
def get_remaining_cash(trading_log, US = False):
    cash = INITIAL_CAPITAL_KR
    fee_rate = FEE_RATE_KR
    if US:
        cash = INITIAL_CAPITAL_US
        fee_rate = FEE_RATE_US
    for _, row in trading_log.iterrows():
        fee = int(row["금액"] * fee_rate)
        if row["거래유형"] == "매수":
            cash -= (row["금액"] + fee)
        elif row["거래유형"] == "매도":
            cash += (row["금액"] - fee)
    return cash

# 투자수익률 계산 함수 
# -> output ['구분1','구분2','티커','종목명','매수일','평균단가','현재가','평가손익','투자수익률(%)','보유수량','현재평가금액]
def calc_profit(trading_log, apply_fee, US=False):
    if US:
        fee_rate = FEE_RATE_US
        result = []
        grouped = trading_log.sort_values("거래일").groupby(['구분',"티커"])

        for ticker, group in grouped:
            ticker = ticker[1]
            position = []  # 보유 중인 매수 거래들
            buy_date = None  # 현재 포지션에 해당하는 매수일
            end_price = price_dict_US[ticker]["Close"].iloc[-1]

            for _, row in group.iterrows():
                if row["거래유형"] == "매수":
                    cost = row["금액"]
                    fee = int(row["금액"] * fee_rate)
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
                profit = eval_value - total_cost_fee - int(eval_value * fee_rate)
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
    else: # 국내 계좌
        fee_rate = FEE_RATE_KR
    
        result = []
        grouped = trading_log.sort_values("거래일").groupby("티커")

        for ticker, group in grouped:
            position = []  # 보유 중인 매수 거래들
            buy_date = None  # 현재 포지션에 해당하는 매수일
            end_price = price_dict_KR[ticker]["Close"].iloc[-1]

            for _, row in group.iterrows():
                if row["거래유형"] == "매수":
                    cost = row["금액"]
                    fee = int(row["금액"] * fee_rate)
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
                profit = eval_value - total_cost_fee - int(eval_value * fee_rate)
                total_return = profit / total_cost_fee if total_cost_fee else 0

            result.append({
                '구분1': group["구분1"].iloc[-1],
                '구분2': group["구분2"].iloc[-1],
                "티커": ticker,
                "종목명": group["종목명"].iloc[-1],
                "매수일": buy_date.strftime("%Y-%m-%d") if buy_date else None,
                "평균단가": f'{int(average_price):,}',
                "현재가": f'{int(end_price):,}',
                "평가손익": f"{int(profit):,}",
                "투자수익률(%)": round(total_return * 100, 2),
                "보유수량": int(remaining_quantity),
                "현재평가금액": f"{int(eval_value):,}"
            })

        return pd.DataFrame(result)

# 실현 손익 구하기
def calc_realized_profit(trading_log, US=False):
    result = []
    total_realized_profit = 0
    grouped = trading_log.sort_values("거래일").groupby("티커")
    fee_rate = FEE_RATE_KR
    if US:
        fee_rate = FEE_RATE_US

    for ticker, group in grouped:
        position = []

        for _, row in group.iterrows():
            if row["거래유형"] == "매수":
                cost = row["금액"]
                fee = int(cost * fee_rate)
                total_cost = cost + fee
                position.append([row["거래수량"], cost, total_cost, row["거래일"]])

            elif row["거래유형"] == "매도":
                sell_qty = row["거래수량"]
                sell_date = row["거래일"]
                total_sell = row["금액"] - int(row["금액"] * fee_rate)

                realized_cost = 0
                realized_cost_fee = 0
                matched_qty = 0
                matched_buy_date = None

                while sell_qty > 0 and position:
                    qty, amt, amt_fee, b_date = position[0]
                    if qty > sell_qty:
                        portion = sell_qty / qty
                        realized_cost += amt * portion
                        realized_cost_fee += amt_fee * portion
                        position[0][0] -= sell_qty
                        position[0][1] -= amt * portion
                        position[0][2] -= amt_fee * portion
                        matched_qty += sell_qty
                        matched_buy_date = b_date
                        sell_qty = 0
                    else:
                        realized_cost += amt
                        realized_cost_fee += amt_fee
                        matched_qty += qty
                        matched_buy_date = b_date
                        sell_qty -= qty
                        position.pop(0)

                if matched_qty > 0:
                    buy_unit_price = realized_cost / matched_qty if matched_qty else 0
                    sell_unit_price = total_sell / matched_qty if matched_qty else 0
                    profit = total_sell - realized_cost_fee
                    return_pct = profit / realized_cost_fee *100
                    total_realized_profit += profit

                    if US:
                        result.append({
                        '구분': group["구분"].iloc[-1],
                        "티커": ticker,
                        "이름": group["이름"].iloc[-1],
                        "매수일": matched_buy_date.strftime("%Y-%m-%d") if matched_buy_date else None,
                        "매도일": sell_date.strftime("%Y-%m-%d") if sell_date else None,
                        "매수단가": f'{int(buy_unit_price):,}',
                        "매도단가": f'{int(sell_unit_price):,}',
                        "실현손익": f"{int(profit):,}",
                        "수익률(%)": return_pct
                        })
                    else:
                        result.append({
                            '구분1': group["구분1"].iloc[-1],
                            '구분2': group["구분2"].iloc[-1],
                            "티커": ticker,
                            "종목명": group["종목명"].iloc[-1],
                            "매수일": matched_buy_date.strftime("%Y-%m-%d") if matched_buy_date else None,
                            "매도일": sell_date.strftime("%Y-%m-%d") if sell_date else None,
                            "매수단가": f'{int(buy_unit_price):,}',
                            "매도단가": f'{int(sell_unit_price):,}',
                            "실현손익": f"{int(profit):,}",
                            "수익률(%)": return_pct
                        })

    return pd.DataFrame(result), int(total_realized_profit)

# ---------------------------
# 초기 페이지 설정
# ---------------------------

st.set_page_config(page_title="투자 대시보드", layout="wide")
st.title("💹 투자 대시보드")
page = st.sidebar.radio("메뉴 선택", ["국내계좌 분석", "해외계좌 분석", "국내계좌 매수/매도 정보 입력", "해외계좌 매수/매도 정보 입력"])

# ---------------------------
# Page1: 국내계좌 분석
# ---------------------------

if page == "국내계좌 분석":
    # ---------------------------
    ## 수익률 계산
    st.subheader("국내계좌 분석")
    st.markdown("### 수익률계산")
    trading_log = st.session_state.trading_log.copy()
    col1, col2 = st.columns([5, 1])  
    with col1:
        apply_fee_KR = st.checkbox("수수료 적용 (0.1%)", value=True)
    with col2:
        st.markdown(f"**기준일:** {end_date}")
    profit_df = calc_profit(trading_log, apply_fee_KR, US=False)
    result_df = profit_df.copy()
    result_df["평가손익_int"] = result_df["평가손익"].str.replace(",", "").astype(int)
    result_df = result_df.sort_values(by='평가손익_int',ascending=False, axis=0).reset_index(drop=True)
    result_df = result_df.drop('평가손익_int',axis=1)
    st.dataframe(result_df)

    # 평가손익 총합 및 현재 자산 계산
    profit_sum = result_df["평가손익"].str.replace(",", "").astype(int).sum()
    eval_sum = result_df["현재평가금액"].str.replace(",", "").astype(int).sum()

    remain_cash = get_remaining_cash(trading_log, US=False)
    total_asset = eval_sum + remain_cash
    total_return = profit_sum / INITIAL_CAPITAL_KR * 100

    realized_profit_df, total_realized_profit = calc_realized_profit(trading_log, US=False)

    st.markdown("#### 손익 실현 내역")
    st.dataframe(realized_profit_df,
                 column_config={
                    "수익률(%)": st.column_config.NumberColumn(
                        label="수익률(%)",
                        format="%.2f%%")})
    
    st.markdown("#### 📊 전체 수익 요약")
    col3, col4= st.columns(2)
    with col3:
        st.metric(label="💹 총 평가손익", value=f"{profit_sum:+,} 원")
    with col4:
        st.metric(label="📈 전체 수익률", value=f"{total_return:.2f} %")
    col5, col6 = st.columns(2)
    with col5:
        st.metric(label="💸 현금", value=f"{remain_cash:,} 원")
    with col6:
        st.metric(label="💰 총 자산", value=f"{total_asset:,} 원")
    st.metric(label="💲 실현 손익 총액", value=f"{total_realized_profit:+,} 원")

    
    # ---------------------------
    ## 목표 수익률 및 기술적 지표 분석
    st.markdown("---")
    st.markdown("### 📈 목표 수익률 및 기술적 지표 분석")
    col7, col8 = st.columns([5, 1])  
    with col8:
        st.markdown(f"**기준일:** {end_date}")
    target_df = profit_df[['구분1','구분2','티커','종목명','매수일','평가손익','투자수익률(%)']]

    tech_indicator = []
    for ticker in target_df['티커']:
        df = price_dict_KR[ticker].copy()
        if df.empty:
            continue

        df['Return'] = df['Close'].pct_change()
        latest_price = df['Close'].iloc[-1]

        buy_date = target_df.loc[target_df['티커']==ticker]['매수일'].values[0]
        category = target_df.loc[target_df['티커']==ticker]['구분2'].values[0]

        recent_window = df.loc[df.index <= buy_date]['Return'].dropna().iloc[-120:]
        avg_r_120 = recent_window.mean()

        r10_80 = max(avg_r_120 * 10 * 0.8, 0.04)
        r10_120 = max(avg_r_120 * 10 * 1.2, 0.06)
        r30_80 = max(avg_r_120 * 30 * 0.8, 0.04)
        r30_120 = max(avg_r_120 * 30 * 1.2, 0.06)
        r60_80 = max(avg_r_120 * 60 * 0.8, 0.04)
        r60_120 = max(avg_r_120 * 60 * 1.2, 0.06)

        cat_trg_10 = []
        cat_trg_30 = ['국내주식_섹터', '해외주식_섹터','해외주식_지수']
        cat_trg_60 = ['국내주식_지수', 'FX 및 원자재', '국내채권_종합', '국내채권_회사채','해외채권_종합','해외채권_회사채','금리연계형/초단기채권']
        if category in cat_trg_10:
            tgt_80, tgt_120 = r10_80, r10_120
            exit_80, exit_120 = r10_80*(-0.5), r10_120*(-0.5)
        elif category in cat_trg_30:
            tgt_80, tgt_120 = r30_80, r30_120
            exit_80, exit_120 = r30_80*(-0.5), r30_120*(-0.5)
        elif category in cat_trg_60:
            tgt_80, tgt_120 = r60_80, r60_120
            exit_80, exit_120 = r60_80*(-0.5), r60_120*(-0.5)
        else:
            tgt_80, tgt_120 = '설정되지 않은 카테고리'
            exit_80, exit_120 = '설정되지 않은 카테고리'

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
    target_df = pd.merge(target_df, tech_indicator, on='티커' )
    target_df = target_df.sort_values('투자수익률(%)',axis=0, ascending=False).reset_index(drop=True)
    target_df = target_df.drop(['구분1','구분2'],axis=1)
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
            if cur <= row["손절가(120%)"]:
                style[columns.index("투자수익률(%)")] = "background-color: orangered"
            elif cur <= row["손절가(80%)"]:
                style[columns.index("투자수익률(%)")] = "background-color: salmon"

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
    
    st.dataframe(target_df.style.apply(highlight_row, axis=1),
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
    
    # ---------------------------
    ## 투자비중 분석
    st.markdown("---")
    st.markdown("## 투자비중 분석")
    remaining_cash= get_remaining_cash(trading_log, US=False)
    total_eval = profit_df['현재평가금액'].str.replace(",", "").astype(int).sum()
    total_asset = remaining_cash + total_eval

    # 구분1
    cat1_ratio_df = profit_df[['구분1','현재평가금액','평균단가','보유수량']]
    cat1_ratio_df['기초평가금액'] = (cat1_ratio_df['평균단가'].str.replace(",", "").astype(int) * cat1_ratio_df['보유수량'])
    cat1_ratio_df = cat1_ratio_df.drop(['평균단가','보유수량'],axis=1)
    cat1_ratio_df['현재평가금액'] =  cat1_ratio_df['현재평가금액'].str.replace(",", "").astype(int)
    cat1_ratio_df = cat1_ratio_df.groupby('구분1').sum().reset_index()
    cat1_ratio_df['수익률'] = (cat1_ratio_df['현재평가금액'] - cat1_ratio_df['기초평가금액']) /cat1_ratio_df['기초평가금액'] *100
    cat1_ratio_df['투자비중'] = cat1_ratio_df['현재평가금액'] / total_asset *100
    cat1_ratio_df['현재평가금액'] = cat1_ratio_df['현재평가금액'].apply(lambda x: f'{x:,}')
    cat1_ratio_df['기초평가금액'] = cat1_ratio_df['기초평가금액'].apply(lambda x: f'{x:,}')
    cat1_ratio_df = cat1_ratio_df.rename(columns = {'구분1':"구분"})

    # 구분2
    cat2_ratio_df =profit_df[['구분2','현재평가금액','평균단가','보유수량']]
    cat2_ratio_df['기초평가금액'] = (cat2_ratio_df['평균단가'].str.replace(",", "").astype(int) * cat2_ratio_df['보유수량'])
    cat2_ratio_df = cat2_ratio_df.drop(['평균단가','보유수량'],axis=1)
    cat2_ratio_df['현재평가금액'] =  cat2_ratio_df['현재평가금액'].str.replace(",", "").astype(int)
    cat2_ratio_df = cat2_ratio_df.groupby('구분2').sum().reset_index()
    cat2_ratio_df['수익률'] = (cat2_ratio_df['현재평가금액'] - cat2_ratio_df['기초평가금액']) /cat2_ratio_df['기초평가금액'] *100
    cat2_ratio_df['투자비중'] = cat2_ratio_df['현재평가금액'] / total_asset *100
    cat2_ratio_df['현재평가금액'] = cat2_ratio_df['현재평가금액'].apply(lambda x: f'{x:,}')
    cat2_ratio_df['기초평가금액'] = cat2_ratio_df['기초평가금액'].apply(lambda x: f'{x:,}')
    cat2_ratio_df = cat2_ratio_df.rename(columns = {'구분2':"구분"})

    # 합치기
    ratio_df = pd.concat([cat1_ratio_df,cat2_ratio_df],axis=0)

    # 상한 설정
    limit_dict = {
    '안전':100,
    '위험':70,
    'FX 및 원자재': 20,
    '국내주식_섹터': 15,
    '국내주식_지수': 30,
    '국내채권_종합': 50,
    '국내채권_회사채': 30,
    '금리연계형/초단기채권': 50,
    '해외주식_섹터': 10,
    '해외주식_지수': 30,
    '해외채권_종합': 50,
    '해외채권_회사채': 30
    }
    ratio_df["상한"] = ratio_df["구분"].map(limit_dict).fillna("-")
    ratio_df = ratio_df.sort_values('상한').reset_index(drop=True)


    def highlight_exceed_limit(row):
        style = [''] * len(row)
        columns = row.index.tolist()

        try:
            if row["상한"] and row['투자비중'] >= row["상한"] * 0.8:
                style[columns.index("투자비중")] = "background-color: salmon"
            style[columns.index("상한")] = "background-color: #f0f0f0"

        except Exception:
            pass

        return style
    
    st.dataframe(ratio_df.style.apply(highlight_exceed_limit, axis=1),
                column_config={
                    "수익률": st.column_config.NumberColumn(
                        label="수익률",
                        format="%.2f%%"),
                    "투자비중": st.column_config.NumberColumn(
                        label="투자비중",
                        format="%.2f%%"),
                    "상한": st.column_config.NumberColumn(
                        label="상한",
                        format="%.2f%%")})
    
# ---------------------------
# Page2: 해외계좌 분석
# ---------------------------
if page == "해외계좌 분석":
    # ---------------------------
    ## 수익률 계산
    st.subheader("해외계좌 분석")
    st.markdown("### 수익률계산")
    trading_log = st.session_state.trading_log_us.copy()
    col1, col2, col3 = st.columns([1, 4, 1])  
    with col1:
        apply_fee_US = st.checkbox("수수료 적용 (0.2%)", value=True)
    with col2:
        apply_KRW = st.checkbox(f"원화 적용({EXCHANGE_RATE}원/$)", value=False)
    with col3:
        st.markdown(f"**기준일:** {datetime.today().strftime('%Y-%m-%d')}")

    result_df = calc_profit(trading_log, apply_fee_US, US=True)
    result_df["현재평가금액_int"] = result_df["현재평가금액"].str.replace(",", "").astype(int)
    result_df = result_df.sort_values(by=['구분','현재평가금액_int'],ascending=False, axis=0).reset_index(drop=True)
    result_df = result_df.drop('현재평가금액_int',axis=1)
    st.dataframe(result_df)

    # 평가손익 총합 및 현재 자산 계산
    profit_sum = result_df["평가손익"].str.replace(",", "").astype(int).sum()
    eval_sum = result_df["현재평가금액"].str.replace(",", "").astype(int).sum()

    remain_cash = get_remaining_cash(trading_log, US=True)
    total_asset = eval_sum + remain_cash
    total_return = profit_sum / INITIAL_CAPITAL_US * 100

    realized_profit_df, total_realized_profit = calc_realized_profit(trading_log, US=True)

    st.markdown("#### 손익 실현 내역")
    st.dataframe(realized_profit_df,
                 column_config={
                    "수익률(%)": st.column_config.NumberColumn(
                        label="수익률(%)",
                        format="%.2f%%")})
    
    st.markdown("#### 📊 전체 수익 요약")
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
    if apply_KRW:
        st.metric(label="💲 실현 손익 총액", value=f"{total_realized_profit*EXCHANGE_RATE:+,} 원")
    else:
        st.metric(label="💲 실현 손익 총액", value=f"{total_realized_profit:+,} 원")
    
    # ---------------------------
    ## 목표수익률 및 지표 확인
    st.markdown('---')
    st.markdown("### 📈 목표 수익률 및 기술적 지표 분석")
    profit_df = calc_profit(trading_log, apply_fee_US, US=True)
    target_df = profit_df[['구분','티커','이름','매수일','평가손익','투자수익률(%)']]
    target_df = target_df.loc[target_df["구분"]=='개별종목']

    tech_indicator = []
    for ticker in target_df['티커']:
        df = price_dict_US[ticker].copy()
        if df.empty:
            continue

        df['Return'] = df['Close'].pct_change()
        latest_price = df['Close'].iloc[-1]

        buy_date = target_df.loc[target_df['티커']==ticker]['매수일'].values[0]

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
    target_df = pd.merge(target_df, tech_indicator, on='티커' )
    target_df = target_df.sort_values('투자수익률(%)',axis=0, ascending=False).reset_index(drop=True)
    target_df = target_df.drop(['구분'],axis=1)
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
    
    st.dataframe(target_df.style.apply(highlight_row, axis=1),
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
    index_eval_begin = (profit_df.loc[profit_df['구분']=='지수구성']['평균단가'].str.replace(",", "").astype(int) * profit_df.loc[profit_df['구분']=='지수구성']['보유수량']).sum()
    index_eval_end =  profit_df.loc[profit_df['구분']=='지수구성']['현재평가금액'].str.replace(",", "").astype(int).sum()
    index_profit = (index_eval_end - index_eval_begin)/index_eval_begin*100
    col9,col10 = st.columns(2)
    with col9:
        st.metric(label="💹 지수구성 평가손익", value=f"{index_eval_end - index_eval_begin:+,} $")
    with col10:
        st.metric(label="📈 지수구성 수익률", value=f"{index_profit:.2f} %")


    
    # ---------------------------
    ## 투자비중 분석
    st.markdown('---')
    st.markdown("### 투자비중 분석")
    st.markdown("#### 지수구성 투자비중")

    ratio_df = calc_profit(trading_log, apply_fee=True, US=True)[['구분','티커','이름','현재평가금액']]
    index_df = ratio_df.loc[ratio_df['구분']=='지수구성']
    index_df = index_df.drop('구분',axis=1)
    index_df['현재평가금액'] = index_df['현재평가금액'].str.replace(",", "").astype(int)

    remaining_cash= get_remaining_cash(trading_log, US=True)
    total_eval = ratio_df['현재평가금액'].str.replace(",", "").astype(int).sum()
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
    
    # 개별종목
    Individ_df =  ratio_df.loc[ratio_df['구분']=='개별종목']
    Individ_df = Individ_df.drop('구분',axis=1)
    Individ_df['현재평가금액'] = Individ_df['현재평가금액'].str.replace(",", "").astype(int)
    Individ_df['투자비중'] = Individ_df['현재평가금액'] / total_asset *100
    if apply_KRW:
        Individ_df['현재평가금액'] = Individ_df['현재평가금액'].apply(lambda x: f'{x*EXCHANGE_RATE:,.0f}원')
    else:
        Individ_df['현재평가금액'] = Individ_df['현재평가금액'].apply(lambda x: f'${x:,}')
    Individ_df = Individ_df.sort_values(by='투자비중',ascending=False).reset_index(drop=True)

    st.markdown("#### 개별종목 투자비중")
    st.dataframe(Individ_df,
            column_config={
                "투자비중": st.column_config.NumberColumn(
                    label="투자비중",
                    format="%.2f%%")})
    
# ---------------------------
# Page3: 국내계좌 매수/매도 금액 입력 (검색 및 등록형)
# ---------------------------
if page == "국내계좌 매수/매도 정보 입력":
    st.subheader("국내계좌 매수/매도 정보 입력")
    st.markdown("로컬에서 입력 후 Push")

    # 티커 또는 종목명 검색
    ticker_input = st.text_input("티커 입력")
    ticker_input = ticker_input.strip().zfill(6)
    ticker_A = 'A' + ticker_input
    if ticker_input:        
        try:
            if ticker_A in ticker_list:
                ticker_input_data = etf_data[etf_data["티커"]== ticker_A]
                name = ticker_input_data['ETF명'].values[0]
                cat1 = ticker_input_data['구분1'].values[0]
                cat2 = ticker_input_data['구분2'].values[0]
                st.success(f"✅ {name} ({ticker_input}) 조회됨")
            
            # 거래 정보 입력
            col1, col2 = st.columns(2)
            with col1:
                trade_type = st.selectbox("거래 유형", ["매수", "매도"])
            with col2:
                trade_date = st.date_input("거래일", value=date.today())

            col3, col4 = st.columns(2)
            with col3:
                quantity = st.number_input("거래 수량 (주)", min_value=0)
            with col4:
                amount = st.number_input("거래 금액 (₩)", min_value=0)

            if st.button("거래로그에 추가"):
                existing = st.session_state.trading_log
                if trade_type == "매수":
                    new_entry = pd.DataFrame.from_records([{
                                "구분1": cat1,
                                "구분2": cat2, 
                                "거래일": pd.to_datetime(trade_date).normalize(),
                                "티커": ticker_input,
                                "종목명": name,
                                '거래유형': trade_type,
                                "거래수량": quantity,
                                "평균단가": round(amount/quantity),
                                "금액": amount
                            }])
                    st.session_state.trading_log = pd.concat([existing, new_entry], ignore_index=True)

                elif trade_type == "매도":
                    total_buy = existing[(existing["티커"] == ticker_input) & (existing["거래유형"] == "매수")]["거래수량"].sum()
                    total_sell = existing[(existing["티커"] == ticker_input) & (existing["거래유형"] == "매도")]["거래수량"].sum()
                    available = total_buy - total_sell                    
                    if quantity > available:
                        st.error(f"❌ 매도 가능 금액({available:,.0f}원)를 초과했습니다.")
                        new_entry = None
                    else:
                        new_entry = pd.DataFrame.from_records([{
                                "구분1": cat1,
                                "구분2": cat2, 
                                "거래일": pd.to_datetime(trade_date).normalize(),
                                "티커": ticker_input,
                                "종목명": name,
                                '거래유형': trade_type,
                                "거래수량": quantity,
                                "평균단가": round(amount/quantity),
                                "금액": amount
                            }])
                        st.session_state.trading_log = pd.concat([existing, new_entry], ignore_index=True)

                if new_entry is not None:
                    st.session_state.trading_log = (st.session_state.trading_log
                                                  .groupby('티커')
                                                  .apply(lambda x: x.sort_values(by='거래일'))
                                                  .reset_index(drop=True))
                    st.session_state.trading_log.to_csv("./data/trading_log.csv", index=False)
                    st.success("✅ 거래 로그가 업데이트되고 저장되었습니다.")

        except Exception as e:
            st.error(f"❌ 종목 정보를 불러올 수 없습니다: {e}")

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
        disabled=["구분1", "구분2","거래일", "티커", "종목명", "거래유형", "거래수량", "평균단가", "금액"],
        use_container_width=True
    )

    if st.button("선택한 거래 삭제"):
        to_delete = edited[edited["삭제"]]
        if not to_delete.empty:
            # 삭제할 행을 제외한 데이터로 갱신
            updated_log = edited[~edited["삭제"]].drop(columns=["삭제"])
            st.session_state.trading_log = updated_log
            st.session_state.trading_log.to_csv("./data/trading_log.csv", index=False)
            st.success(f"🗑️ {len(to_delete)}건의 거래가 삭제되었습니다.")
        else:
            st.warning("❗ 삭제할 거래를 선택하지 않았습니다.")

# ---------------------------
# Page4: 해외계좌 매수/매도 금액 입력 (검색 및 등록형)
# ---------------------------
if page == "해외계좌 매수/매도 정보 입력":
    st.subheader("해외계좌 매수/매도 정보 입력")
    st.markdown("로컬에서 입력 후 Push")

    # 티커 또는 이름 검색
    ticker_input = st.text_input("티커 입력")
    if ticker_input:        
        # try:
        if ticker_input in spx_ticker_list:
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
            existing = st.session_state.trading_log_us
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
                st.session_state.trading_log_us = pd.concat([existing, new_entry], ignore_index=True)

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
                    st.session_state.trading_log_us = pd.concat([existing, new_entry], ignore_index=True)

            if new_entry is not None:
                st.session_state.trading_log_us = (st.session_state.trading_log_us
                                                .groupby('티커')
                                                .apply(lambda x: x.sort_values(by='거래일'))
                                                .reset_index(drop=True))
                st.session_state.trading_log_us.to_csv("./data/trading_log_us.csv", index=False)
                st.success("✅ 거래 로그가 업데이트되고 저장되었습니다.")

        # except Exception as e:
        #     st.error(f"❌ 종목 정보를 불러올 수 없습니다: {e}")

    st.markdown("---")
    st.write("### 거래 기록")

    editable_log = st.session_state.trading_log_us.sort_values(by='거래일',axis=0).reset_index(drop=True)
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
            st.session_state.trading_log_us = updated_log
            st.session_state.trading_log_us.to_csv("./data/trading_log_us.csv", index=False)
            st.success(f"🗑️ {len(to_delete)}건의 거래가 삭제되었습니다.")
        else:
            st.warning("❗ 삭제할 거래를 선택하지 않았습니다.")
