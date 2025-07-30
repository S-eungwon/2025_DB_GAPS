import streamlit as st
import pandas as pd
from datetime import date

from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import BollingerBands

from utils.finance import calc_profit_us, get_remaining_cash, calc_realized_profit
from utils.data_loader import get_price, load_spx_data
from utils.config import INITIAL_CAPITAL_US, EXCHANGE_RATE

def show_us_analysis():
    # ---------------------------
    # 필요한 정보 불러오기

    # 거래로그
    trading_log = st.session_state.trading_log_us.copy()

    # 가격 데이터
    price_dict_US = get_price(market="US")

    # 현재 날짜
    first_ticker = list(price_dict_US.keys())[0]
    first_ticker_df = price_dict_US[first_ticker]
    latest_date = first_ticker_df.index.max().date()

    # ---------------------------
    ## 수익률 계산
    st.subheader("해외계좌 분석")
    st.markdown("### 수익률계산")
    col1, col2, col3 = st.columns([1, 4, 1])  
    with col1:
        apply_fee = st.checkbox("수수료 적용 (0.2%)", value=True)
    with col2:
        apply_KRW = st.checkbox(f"원화 적용({EXCHANGE_RATE}원/$)", value=False)
    with col3:
        st.markdown(f"**기준일:** {latest_date}")

    # 수익률 데이터프레임
    profit_df = calc_profit_us(trading_log, price_dict_US, apply_fee)

    # 평가손익 기준 정렬
    result_df = profit_df.copy()
    result_df["현재평가금액_int"] = result_df["현재평가금액"].str.replace(",", "").astype(int)
    result_df = result_df.sort_values(by=['구분','현재평가금액_int'],ascending=False, axis=0).reset_index(drop=True)
    result_df = result_df.drop('현재평가금액_int',axis=1)
    st.dataframe(result_df)

    # ---------------------------
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
    
    # ---------------------------
    # 전체 수익 요약 
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
        st.metric(label="💲 실현 손익 총액", value=f"${total_realized_profit*EXCHANGE_RATE:+,}")
    else:
        st.metric(label="💲 실현 손익 총액", value=f"{total_realized_profit:+,} 원")
    
    # ---------------------------
    ## 목표수익률 및 지표 확인
    st.markdown('---')
    st.markdown("### 📈 목표 수익률 및 기술적 지표 분석")
    target_df = profit_df[['구분','티커','이름','매수일','평가손익','투자수익률(%)']]
    target_df = target_df.loc[target_df["구분"]=='개별종목']

    # 종목별 계산
    tech_indicator = []
    for ticker in target_df['티커']:
        df = price_dict_US[ticker].copy()
        if df.empty:
            continue

        df['Return'] = df['Close'].pct_change()

        buy_date = target_df.loc[target_df['티커']==ticker]['매수일'].values[0]

        recent_window = df.loc[df.index <= buy_date]['Return'].dropna().iloc[-120:]
        avg_r_120 = recent_window.mean()

        # 목표 수익률 및 손절가 계산
        r10_80 = max(avg_r_120 * 10 * 0.8, 0.04)
        r10_120 = max(avg_r_120 * 10 * 1.2, 0.06)
        r30_80 = max(avg_r_120 * 30 * 0.8, 0.04)
        r30_120 = max(avg_r_120 * 30 * 1.2, 0.06)
        r60_80 = max(avg_r_120 * 60 * 0.8, 0.04)
        r60_120 = max(avg_r_120 * 60 * 1.2, 0.06)

        tgt_80, tgt_120 = r30_80, r30_120
        exit_80, exit_120 = r30_80*(-0.5), r30_120*(-0.5)

        # 기술적 지표 계산
        rsi = RSIIndicator(close=df['Close'], window=14).rsi().iloc[-1]
        rsi_signal = '과매수' if rsi > 70 else '과매도' if rsi < 30 else '중립'

        bb = BollingerBands(close=df['Close'], window=20, window_dev=2)
        bb_signal = '하단돌파(매수신호)' if df['Close'].iloc[-1] < bb.bollinger_lband().iloc[-1] else \
                    '상단돌파(매도경고)' if df['Close'].iloc[-1] > bb.bollinger_hband().iloc[-1] else '정상범위'

        adx = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14).adx().iloc[-1]
        adx_signal = '강한추세' if adx > 20 else '약한추세'

        # 기술적 지표와 목표 수익률을 데이터프레임에 추가
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

    # 목표수익률 및 손절가 도달 표시 하이라이트 함수
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
    
    # 지수구성 포트폴리오 평가
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

    ratio_df = profit_df[['구분','티커','이름','현재평가금액']]
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

def show_us_input():
    # 투자 가능 SPX 데이터 로드
    spx_data = load_spx_data()
    spx_ticker_list = spx_data['티커'].tolist()

    st.subheader("해외계좌 매수/매도 정보 입력")
    st.markdown("로컬에서 입력 후 Push")

    # 티커 또는 이름 검색
    ticker_input = st.text_input("티커 입력")
    if ticker_input:        
        try:
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

        except Exception as e:
            st.error(f"❌ 종목 정보를 불러올 수 없습니다: {e}")

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