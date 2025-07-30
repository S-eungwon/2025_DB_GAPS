import pandas as pd
import os
import streamlit as st
from datetime import date, datetime
import FinanceDataReader as fdr

def load_etf_data():
    return pd.read_csv('./data/국내계좌_투자대상_ETF.csv')

def load_spx_data():
    df = pd.read_csv('./data/해외계좌_투자대상_개별종목.csv', encoding='cp949')
    df['티커'] = df['티커'].apply(lambda x: x.split()[0])
    return df

def get_price(market: str = "KR"):
    """
    market: "KR" 또는 "US"
    """
    if market == "KR":
        df = st.session_state.trading_log
    elif market == "US":
        df = st.session_state.trading_log_us
    else:
        raise ValueError("market은 'KR' 또는 'US' 중 하나여야 합니다.")

    tickers = df["티커"].astype(str).unique()
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

    return price_dict

def load_trading_log():
    # 국내 거래 로그 로드
    if "trading_log" not in st.session_state:
        path_kr = "./data/trading_log.csv"
        if os.path.exists(path_kr):
            st.session_state.trading_log = pd.read_csv(
                path_kr,
                dtype={"티커": str},
                parse_dates=["거래일"]
            )
        else:
            st.session_state.trading_log = pd.DataFrame(columns=[
                "구분1", "구분2", "티커", "종목명", "거래일", "거래유형", "거래수량", "평균단가", "금액"
            ])
    st.session_state.trading_log["거래일"] = pd.to_datetime(
        st.session_state.trading_log["거래일"], format="mixed"
    )

    # 해외 거래 로그 로드
    if "trading_log_us" not in st.session_state:
        path_us = "./data/trading_log_us.csv"
        if os.path.exists(path_us):
            st.session_state.trading_log_us = pd.read_csv(
                path_us,
                dtype={"티커": str},
                parse_dates=["거래일"]
            )
        else:
            st.session_state.trading_log_us = pd.DataFrame(columns=[
                "티커", "이름", "거래일", "거래유형", "구분", "거래수량", "평균단가", "금액"
            ])
    st.session_state.trading_log_us["거래일"] = pd.to_datetime(
        st.session_state.trading_log_us["거래일"], format="mixed"
    )