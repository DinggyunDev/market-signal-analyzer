import pandas as pd
import pandas_ta as ta
import numpy as np

def safe_value(value):
    """
    NaN, inf 값을 None으로 변환하고 나머지는 float으로 변환함
    """
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return float(value)

def calculate_all_indicators(data):
    """
    지표 계산 안정성, 필수 컬럼 검증, 신규 상장주 예외 처리가 완벽히 적용된 최종 엔진입니다.
    """
    try:
        daily = data.get("daily")
        intraday = data.get("intraday")

        # [필수 검증 1] 데이터 존재 여부 체크
        if daily is None or daily.empty:
            return {"status": "no_daily_data"}

        # [필수 검증 2] 필수 컬럼 존재 여부 체크 (KeyError 방지)
        required_columns = ["Open", "High", "Low", "Close", "Volume"]
        missing_columns = [col for col in required_columns if col not in daily.columns]
        if missing_columns:
            return {"status": "invalid_columns", "message": f"필수 컬럼 누락: {', '.join(missing_columns)}"}

        # [필수 검증 3] 데이터 길이 체크 (지표 안정화 기준)
        if len(daily) < 35:
            return {"status": "insufficient_data"}

        results = {"status": "ok", "ticker": data.get("ticker", "").upper()}

        # 1. VWAP (원본 보존 및 제로 디비전 방어)
        results["vwap"] = None
        if intraday is not None and not intraday.empty:
            # 인트라데이 필수 컬럼 확인
            if all(col in intraday.columns for col in ["High", "Low", "Close", "Volume"]):
                total_volume = intraday["Volume"].sum()
                if total_volume > 0:
                    intraday_tp = (intraday["High"] + intraday["Low"] + intraday["Close"]) / 3
                    vwap_val = (intraday_tp * intraday["Volume"]).sum() / total_volume
                    results["vwap"] = safe_value(vwap_val)

        # 2. 거래량 및 비율
        curr_vol = daily["Volume"].iloc[-1]
        avg_vol = daily["Volume"].rolling(window=20).mean().iloc[-1]
        results["volume"] = safe_value(curr_vol)
        results["vol_ratio"] = safe_value(curr_vol / avg_vol) if pd.notna(avg_vol) and avg_vol > 0 else None

        # 3. 모멘텀
        mom_10_series = ta.mom(daily["Close"], length=10)
        results["momentum"] = safe_value(mom_10_series.iloc[-1] if mom_10_series is not None and not mom_10_series.empty else None)

        # 4. 스토캐스틱 (컬럼 존재 여부 체크 강화)
        stoch = ta.stoch(daily["High"], daily["Low"], daily["Close"], k=14, d=3, smooth_k=3)
        if (
            stoch is not None
            and not stoch.empty
            and "STOCHk_14_3_3" in stoch.columns
            and "STOCHd_14_3_3" in stoch.columns
        ):
            results["stoch_k"] = safe_value(stoch["STOCHk_14_3_3"].iloc[-1])
            results["stoch_d"] = safe_value(stoch["STOCHd_14_3_3"].iloc[-1])
        else:
            results["stoch_k"] = results["stoch_d"] = None

        # 5. 이격도 (결측치 방어)
        sma_20 = ta.sma(daily["Close"], length=20)
        if sma_20 is not None and not sma_20.empty and pd.notna(sma_20.iloc[-1]) and sma_20.iloc[-1] > 0:
            results["disparity"] = safe_value((daily["Close"].iloc[-1] / sma_20.iloc[-1]) * 100)
        else:
            results["disparity"] = None

        # 6. MACD (컬럼별 안전 접근)
        macd_df = ta.macd(daily["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            results["macd"] = safe_value(macd_df["MACD_12_26_9"].iloc[-1]) if "MACD_12_26_9" in macd_df.columns else None
            results["macd_signal"] = safe_value(macd_df["MACDs_12_26_9"].iloc[-1]) if "MACDs_12_26_9" in macd_df.columns else None
            results["macd_hist"] = safe_value(macd_df["MACDh_12_26_9"].iloc[-1]) if "MACDh_12_26_9" in macd_df.columns else None
        else:
            results["macd"] = results["macd_signal"] = results["macd_hist"] = None

        # 7. RSI
        rsi_14_series = ta.rsi(daily["Close"], length=14)
        results["rsi"] = safe_value(rsi_14_series.iloc[-1] if rsi_14_series is not None and not rsi_14_series.empty else None)

        # 8. OBV (데이터 구조 확장 및 NaN 체크 강화)
        obv_series = ta.obv(daily["Close"], daily["Volume"])
        if (
            obv_series is not None
            and len(obv_series) >= 5
            and pd.notna(obv_series.iloc[-2]) # 최근 5거래일 비교 (iloc[-1]과 iloc[-5] 사이의 노이즈 감안)
            and pd.notna(obv_series.iloc[-5])
        ):
            curr_obv = obv_series.iloc[-1]
            prev_obv = obv_series.iloc[-5]

            trend = "횡보"
            if curr_obv > prev_obv:
                trend = "상승"
            elif curr_obv < prev_obv:
                trend = "하락"
                
            results["obv"] = {
                "value": safe_value(curr_obv),
                "prev": safe_value(prev_obv),
                "trend": trend
            }
        else:
            results["obv"] = {"value": None, "prev": None, "trend": "데이터부족"}

        return results

    except Exception as e:
        # [포괄적 예외 처리] 시스템의 비정상 종료를 막고 에러를 상위로 전송
        return {"status": "calculation_error", "message": str(e)}
