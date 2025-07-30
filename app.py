import streamlit as st
from data_loader import load_trading_log
from pages_module.page_kr import show_kr_analysis, show_kr_input
from pages_module.page_us import show_us_analysis, show_us_input

# 거래로그 로드
load_trading_log()

st.set_page_config(page_title="투자 대시보드", layout="wide")
st.title("💹 투자 대시보드")
page = st.sidebar.radio("메뉴 선택", ["국내계좌 분석", "해외계좌 분석", "국내계좌 매수/매도 정보 입력", "해외계좌 매수/매도 정보 입력"])

if page == "국내계좌 분석":
    show_kr_analysis()
elif page == "해외계좌 분석":
    show_us_analysis()
elif page == "국내계좌 매수/매도 정보 입력":
    show_kr_input()
elif page == "해외계좌 매수/매도 정보 입력":
    show_us_input()