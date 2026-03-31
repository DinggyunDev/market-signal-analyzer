import yfinance as yf
import pandas as pd
import requests_cache
import pytz
from datetime import datetime, time, timedelta

# 로컬 캐시 설정 (5분간 유지)
requests_cache.install_cache(
    'yfinance_cache',
    expire_after=timedelta(minutes=5)
)

# ================================================================
# 유틸리티
# ================================================================

def _is_valid_number(val):
    """None, NaN, Inf 여부 체크"""
    if val is None:
        return False
    try:
        fval = float(val)
        import math
        return not (math.isnan(fval) or math.isinf(fval))
    except (ValueError, TypeError):
        return False


# ================================================================
# 시장 판별
# ================================================================

def is_krx_ticker(ticker):
    """틱커가 한국 시장(KOSPI/KOSDAQ) 소속인지 확인"""
    t = ticker.upper()
    return t.endswith(".KS") or t.endswith(".KQ") or (t.isdigit() and len(t) == 6)


def is_us_ticker(ticker):
    """틱커가 미국 시장 소속인지 확인 (KRX가 아닌 알파벳 티커)"""
    t = ticker.upper()
    if is_krx_ticker(t):
        return False
    # .KS, .KQ 등 접미사가 없는 알파벳 티커는 미국으로 간주
    return t.replace(".", "").replace("-", "").isalpha()


def detect_market(ticker):
    """
    틱커의 시장을 판별합니다.
    반환: 'KRX', 'US', 'UNKNOWN'
    """
    if is_krx_ticker(ticker):
        return "KRX"
    elif is_us_ticker(ticker):
        return "US"
    return "UNKNOWN"


# ================================================================
# 시장별 Phase 판별
# ================================================================

def get_krx_market_phase(now_kst):
    """현재 시각(KST) 기준 한국 시장 상태 판별"""
    if now_kst.weekday() >= 5:
        return "holiday"
    
    curr_time = now_kst.time()
    if curr_time < time(9, 0):
        return "pre_market"
    elif curr_time < time(15, 30):
        return "during_market"
    else:
        return "after_market"


def get_us_market_phase(now_et):
    """
    현재 시각(ET) 기준 미국 시장 상태 판별.
    NYSE/NASDAQ 정규장: 09:30~16:00 ET
    """
    if now_et.weekday() >= 5:
        return "holiday"
    
    curr_time = now_et.time()
    if curr_time < time(9, 30):
        return "pre_market"
    elif curr_time < time(16, 0):
        return "during_market"
    else:
        return "after_market"


# ================================================================
# 확정 일봉 선택 (시장 공통)
# ================================================================

def select_confirmed_daily_data(daily, phase, today_dt):
    """
    시장 상태에 따라 확정된 일봉 데이터만 선택.
    KRX와 US 시장 모두 동일한 로직을 사용합니다.
    """
    if daily is None or daily.empty:
        return daily, "none", False

    last_idx_date = daily.index[-1].date()
    today_date = today_dt.date()
    
    is_delayed = False
    mode = "confirmed_previous"

    if phase == "during_market":
        if last_idx_date == today_date:
            daily = daily.iloc[:-1]
        if daily.empty:
            return daily, "none", False
        mode = "market_open_previous"
    elif phase == "pre_market":
        if last_idx_date == today_date:
            daily = daily.iloc[:-1]
        mode = "confirmed_previous"
    elif phase == "holiday":
        if last_idx_date == today_date:
            daily = daily.iloc[:-1]
        mode = "holiday_previous"
    else:  # after_market
        if last_idx_date == today_date:
            mode = "confirmed_today"
        else:
            is_delayed = True
            mode = "delayed_previous"

    return daily, mode, is_delayed


# ================================================================
# 데이터 선택 정보 생성 (시장별 라벨)
# ================================================================

def build_selection_info(mode, is_delayed, used_date, market="KRX"):
    """구조화된 데이터 선택 정보 생성. market에 따라 라벨 분기."""
    
    if market == "KRX":
        label_map = {
            "confirmed_today": "[확정:당일]",
            "confirmed_previous": "[확정:직전영업일]",
            "delayed_previous": "[지연:직전영업일]",
            "market_open_previous": "[장중:직전영업일]",
            "holiday_previous": "[휴장:직전거래일]",
            "none": "[데이터없음]"
        }
    else:  # US / UNKNOWN
        label_map = {
            "confirmed_today": "[Confirmed: Today]",
            "confirmed_previous": "[Confirmed: Prev Close]",
            "delayed_previous": "[Delayed: Prev Close]",
            "market_open_previous": "[Market Open: Prev Close]",
            "holiday_previous": "[Closed: Last Trading Day]",
            "none": "[No Data]"
        }
    
    return {
        "selection_mode": mode,
        "selection_label": label_map.get(mode, "[Unknown]"),
        "is_delayed": is_delayed,
        "market": market,
        "used_daily_date": used_date.strftime("%Y-%m-%d") if used_date else "N/A"
    }


# ================================================================
# 메인 데이터 수집 함수
# ================================================================

def fetch_stock_data(ticker):
    """
    야후 파이낸스에서 종목 데이터를 수집하고 시장 규칙에 맞게 데이터를 정제합니다.
    KRX와 US 시장 모두 확정 일봉 선택 규칙을 적용합니다.
    """
    search_tickers = [ticker]
    if ticker.isdigit() and len(ticker) == 6:
        search_tickers = [f"{ticker}.KS", f"{ticker}.KQ"]

    try:
        final_daily = None
        final_intraday = None
        used_ticker = ticker
        used_stock = None

        for t in search_tickers:
            stock = yf.Ticker(t)
            daily = stock.history(period="1y")
            
            if not daily.empty:
                daily = daily.sort_index()
                daily = daily.dropna(subset=["Close", "Volume"])
                
                if not daily.empty:
                    final_daily = daily
                    used_ticker = t
                    used_stock = stock
                    final_intraday = stock.history(period="1d", interval="1m")
                    break
        
        if final_daily is None or final_daily.empty:
            return None

        if len(final_daily) < 35:
            return None

        # --- 시장별 확정 일봉 선택 규칙 적용 ---
        market = detect_market(used_ticker)
        selection_info = None

        if market == "KRX":
            tz = pytz.timezone('Asia/Seoul')
            now_local = datetime.now(tz)
            phase = get_krx_market_phase(now_local)
            final_daily, mode, is_delayed = select_confirmed_daily_data(final_daily, phase, now_local)

            if final_daily.empty:
                return None
            used_date = final_daily.index[-1]
            selection_info = build_selection_info(mode, is_delayed, used_date, market="KRX")

        elif market == "US":
            tz = pytz.timezone('US/Eastern')
            now_local = datetime.now(tz)
            phase = get_us_market_phase(now_local)
            final_daily, mode, is_delayed = select_confirmed_daily_data(final_daily, phase, now_local)

            if final_daily.empty:
                return None
            used_date = final_daily.index[-1]
            selection_info = build_selection_info(mode, is_delayed, used_date, market="US")

        else:
            # 미분류 시장: 선택 규칙 없이 마지막 일봉 기준
            used_date = final_daily.index[-1]
            selection_info = build_selection_info("confirmed_previous", False, used_date, market="UNKNOWN")

        # --- 수치 정합성 레이어 (데이터 일관성 확보) ---
        # 기본적으로 리포트에 표시할 가격과 거래량은 분석 대상이 된 '기준 봉(Bar)'의 데이터를 사용합니다.
        # 이렇게 해야 'Bar: YYYY-MM-DD' 날짜와 실제 출력되는 수치가 일치하며 지표 계산 결과와도 정합성이 맞습니다.
        current_price = final_daily['Close'].iloc[-1]
        current_vol = final_daily['Volume'].iloc[-1]

        # '오늘' 자 데이터를 분석하는 모드(확정당일 또는 장중)일 때만 실시간 정보(fast_info)로 보정 시도
        if selection_info and selection_info['selection_mode'] in ('confirmed_today', 'during_market', 'market_open_previous'):
            try:
                if used_stock is not None:
                    fast_info = used_stock.fast_info
                    # 실시간 가격이 존재하면 갱신
                    f_price = fast_info.get('lastPrice')
                    if _is_valid_number(f_price) and f_price > 0:
                        current_price = f_price
                    
                    # 실시간 거래량이 존재하고 0보다 클 때만 갱신 (장전 0 방지)
                    f_vol = fast_info.get('lastVolume')
                    if _is_valid_number(f_vol) and f_vol > 0:
                        current_vol = f_vol
            except Exception:
                pass

        if not _is_valid_number(current_price):
            return None
        
        return {
            'ticker': used_ticker.upper(),
            'market': market,
            'daily': final_daily,
            'intraday': final_intraday,
            'current_price': current_price,
            'volume': current_vol,
            'selection_info': selection_info
        }
        
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None
