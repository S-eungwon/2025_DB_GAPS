import pandas as pd
from config import INITIAL_CAPITAL_KR, INITIAL_CAPITAL_US, FEE_RATE_KR, FEE_RATE_US

def get_remaining_cash(trading_log, US=False):
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

def calc_profit_kr(trading_log, price_dict, apply_fee):
    fee_rate = FEE_RATE_KR

    result = []
    grouped = trading_log.sort_values("거래일").groupby("티커")

    for ticker, group in grouped:
        position = []  # 보유 중인 매수 거래들
        buy_date = None  # 현재 포지션에 해당하는 매수일
        end_price = price_dict[ticker]["Close"].iloc[-1]

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

def calc_profit_us(trading_log, price_dict, apply_fee):
    fee_rate = FEE_RATE_US
    result = []
    grouped = trading_log.sort_values("거래일").groupby(['구분',"티커"])

    for ticker, group in grouped:
        ticker = ticker[1]
        position = []  # 보유 중인 매수 거래들
        buy_date = None  # 현재 포지션에 해당하는 매수일
        end_price = price_dict[ticker]["Close"].iloc[-1]

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
    