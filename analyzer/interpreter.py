import math


def _is_valid_number(value):
    """None/NaN/inf를 안전하게 검사"""
    if value is None:
        return False
    try:
        return not (math.isnan(value) or math.isinf(value))
    except TypeError:
        return False


def _safe_get(indicators, key, default=None):
    """indicators에서 유효한 숫자만 반환, 아니면 default"""
    val = indicators.get(key)
    return val if _is_valid_number(val) else default


def interpret_indicators(price, indicators):
    """
    계산된 지표 수치들을 바탕으로 해석.
    각 지표별 세분화된 구간 판정 + 교차 시그널 탐지 + 종합 시나리오 해석.
    """
    # price가 유효하지 않으면 안전한 기본값 사용
    if not _is_valid_number(price):
        price = 0.0

    labels = {}

    # ================================================================
    # 1. VWAP — 괴리율 기반 세분화
    # ================================================================
    vwap = indicators.get('vwap')
    if vwap is not None and _is_valid_number(vwap) and vwap > 0:
        gap_pct = ((price - vwap) / vwap) * 100
        if gap_pct > 2.0:
            labels['vwap_status'] = f"현재가가 VWAP 대비 {gap_pct:+.1f}% 상방 이탈"
            labels['vwap_desc'] = "당일 강한 매수 우위. 단기 차익 실현 압력 가능성 존재"
        elif gap_pct > 0:
            labels['vwap_status'] = f"현재가가 VWAP 소폭 상회 ({gap_pct:+.1f}%)"
            labels['vwap_desc'] = "당일 매수 우위 흐름이나 아직 강한 괴리는 아님"
        elif gap_pct > -2.0:
            labels['vwap_status'] = f"현재가가 VWAP 소폭 하회 ({gap_pct:+.1f}%)"
            labels['vwap_desc'] = "당일 매도 우위 흐름이나 지지 가능 구간"
        else:
            labels['vwap_status'] = f"현재가가 VWAP 대비 {gap_pct:+.1f}% 하방 이탈"
            labels['vwap_desc'] = "당일 강한 매도 압력. 추가 하락 경계 필요"
    else:
        labels['vwap_status'] = "장중 거래 데이터 없음 (휴장 또는 장전)"
        labels['vwap_desc'] = "실시간 VWAP을 계산할 수 없는 상태"

    # ================================================================
    # 2. 거래량 — 배율 기반 5단계 세분화
    # ================================================================
    vol_ratio = _safe_get(indicators, 'vol_ratio')
    if vol_ratio is not None:
        labels['vol_status'] = f"최근 20일 평균 거래량 대비 {vol_ratio:.2f}배"
        if vol_ratio >= 3.0:
            labels['vol_desc'] = "이례적 거래 폭증. 대형 이벤트(뉴스/공시/외부 충격) 가능성"
        elif vol_ratio >= 1.5:
            labels['vol_desc'] = "거래 참여 뚜렷한 증가. 추세 전환 또는 강화 신호 가능"
        elif vol_ratio >= 1.0:
            labels['vol_desc'] = "평균 수준의 거래 흐름"
        elif vol_ratio >= 0.5:
            labels['vol_desc'] = "거래 참여가 다소 위축된 상태"
        else:
            labels['vol_desc'] = "극도로 낮은 거래량. 유동성 부족 주의"
    else:
        labels['vol_status'] = "거래량 데이터 부족"
        labels['vol_desc'] = "비교할 평균 거래량이 없습니다"

    # ================================================================
    # 3. 모멘텀 — 강도 기반 4단계
    # ================================================================
    mom = _safe_get(indicators, 'momentum')
    if mom is not None:
        if price > 0:
            mom_pct = (mom / price) * 100
        else:
            mom_pct = 0

        if mom > 0:
            if mom_pct > 5:
                labels['mom_desc'] = "강한 상승 모멘텀. 10일 전 대비 가격 상승폭이 큰 구간"
            else:
                labels['mom_desc'] = "양(+)의 모멘텀 유지. 상승 탄력이 살아있는 상태"
        else:
            if mom_pct < -5:
                labels['mom_desc'] = "강한 하락 모멘텀. 10일 전 대비 낙폭이 큰 구간"
            else:
                labels['mom_desc'] = "음(-)의 모멘텀. 상승 탄력이 둔화되거나 하락 압력 존재"
    else:
        labels['mom_desc'] = "모멘텀 데이터 부족"

    # ================================================================
    # 4. 스토캐스틱 — 크로스 오버 해석 포함
    # ================================================================
    sk = _safe_get(indicators, 'stoch_k')
    sd = _safe_get(indicators, 'stoch_d')
    if sk is not None and sd is not None:
        cross_info = ""
        if sk > sd:
            cross_info = " (%K > %D: 단기 상승 우위)"
        elif sk < sd:
            cross_info = " (%K < %D: 단기 하락 우위)"

        if sk > 80:
            if sk > 90:
                labels['stoch_desc'] = f"극단적 과매수 구간 (K={sk:.0f}){cross_info}"
            else:
                labels['stoch_desc'] = f"과매수 구간 진입 (K={sk:.0f}){cross_info}"
        elif sk < 20:
            if sk < 10:
                labels['stoch_desc'] = f"극단적 과매도 구간 (K={sk:.0f}){cross_info}"
            else:
                labels['stoch_desc'] = f"과매도 구간 진입 (K={sk:.0f}){cross_info}"
        elif sk > 50:
            labels['stoch_desc'] = f"중립 상단 (K={sk:.0f}). 매수 심리 소폭 우위{cross_info}"
        else:
            labels['stoch_desc'] = f"중립 하단 (K={sk:.0f}). 매도 심리 소폭 우위{cross_info}"
    else:
        labels['stoch_desc'] = "스토캐스틱 데이터 부족"

    # ================================================================
    # 5. 이격도 — 구간 세분화 및 평균 회귀 해석
    # ================================================================
    disp = _safe_get(indicators, 'disparity')
    if disp is not None:
        labels['disp_status'] = f"20일 이동평균 대비 {disp:.1f}%"
        if disp > 110:
            labels['disp_desc'] = "심각한 과열. 평균 회귀(하락 조정) 압력이 매우 높음"
        elif disp > 105:
            labels['disp_desc'] = "과열 구간. 차익 실현에 의한 눌림 가능성 존재"
        elif disp > 100:
            labels['disp_desc'] = "이동평균 위에서 정상적 추세 유지"
        elif disp > 95:
            labels['disp_desc'] = "이동평균 부근으로 수렴 중. 방향성 탐색 구간"
        elif disp > 90:
            labels['disp_desc'] = "과매도 구간. 평균 회귀(반등) 기대 가능"
        else:
            labels['disp_desc'] = "심각한 이격. 투매 또는 급락에 의한 깊은 침체 구간"
    else:
        labels['disp_status'] = "이격도 데이터 부족"
        labels['disp_desc'] = "-"

    # ================================================================
    # 6. MACD — 4사분면 + depth_ratio + 시그널 교차
    # ================================================================
    macd_val = _safe_get(indicators, 'macd')
    macd_sig = _safe_get(indicators, 'macd_signal')
    hist_val = _safe_get(indicators, 'macd_hist')

    if macd_val is not None and hist_val is not None:
        if _is_valid_number(price) and price > 0:
            depth_ratio = macd_val / price
        else:
            depth_ratio = 0

        # 시그널 교차 방향 판정
        cross = ""
        if macd_sig is not None:
            if macd_val > macd_sig:
                cross = " (MACD > Signal: 골든크로스 영역)"
            else:
                cross = " (MACD < Signal: 데드크로스 영역)"

        if macd_val > 0:
            if hist_val > 0:
                labels['macd_desc'] = f"상승 추세 강화. 히스토그램 확대 중{cross}"
            else:
                labels['macd_desc'] = f"상승 추세이나 모멘텀 둔화. 히스토그램 축소 중{cross}"
        else:
            if hist_val > 0:
                if depth_ratio < -0.1:
                    labels['macd_desc'] = f"깊은 하락 후 바닥 탐색. 기술적 반등 시도 중{cross}"
                else:
                    labels['macd_desc'] = f"하락세 진정. 단기 상방 전환 시도 중{cross}"
            else:
                if depth_ratio < -0.2:
                    labels['macd_desc'] = f"추세적 폭락 구간. 투매 주의{cross}"
                else:
                    labels['macd_desc'] = f"하락 추세 지속. 히스토그램 확대 중{cross}"
    else:
        labels['macd_desc'] = "MACD 데이터 부족"

    # ================================================================
    # 7. RSI — 5구간 세분화
    # ================================================================
    rsi = _safe_get(indicators, 'rsi')
    if rsi is not None:
        if rsi > 80:
            labels['rsi_desc'] = f"강한 과매수 (RSI {rsi:.0f}). 단기 조정 확률 높음"
        elif rsi > 70:
            labels['rsi_desc'] = f"과매수 진입 (RSI {rsi:.0f}). 추가 상승 여지는 있으나 경계 필요"
        elif rsi > 50:
            labels['rsi_desc'] = f"중립 상단 (RSI {rsi:.0f}). 매수 심리 우위"
        elif rsi > 30:
            labels['rsi_desc'] = f"중립 하단 (RSI {rsi:.0f}). 매도 심리 우위"
        elif rsi > 20:
            labels['rsi_desc'] = f"과매도 진입 (RSI {rsi:.0f}). 기술적 반등 가능 구간"
        else:
            labels['rsi_desc'] = f"극단적 과매도 (RSI {rsi:.0f}). 패닉 수준이나 강한 반등 기대 가능"
    else:
        labels['rsi_desc'] = "RSI 데이터 부족"

    # ================================================================
    # 8. OBV — 방향별 수급 해석
    # ================================================================
    obv_data = indicators.get('obv')
    if isinstance(obv_data, dict):
        trend = obv_data.get('trend', '데이터부족')
    else:
        trend = '데이터부족'
    labels['obv_trend'] = trend

    if trend == "상승":
        labels['obv_desc'] = "거래량 기반 자금 유입세. 매집 또는 추세 지속 가능성"
    elif trend == "하락":
        labels['obv_desc'] = "거래량 기반 자금 유출세. 이탈 또는 투매 진행 가능"
    elif trend == "횡보":
        labels['obv_desc'] = "자금 흐름 중립. 뚜렷한 방향성 부재"
    else:
        labels['obv_desc'] = "OBV 추세 판단 불가"

    # ================================================================
    # 종합 해석 — 스코어링 + 교차 신호 + 시나리오 서술
    # ================================================================
    summary_trend = trend

    # --- 추세 스코어 (0~3) ---
    trend_score = 0
    if vwap is not None and price > vwap:
        trend_score += 1
    if _safe_get(indicators, 'momentum', 0) > 0:
        trend_score += 1
    if _safe_get(indicators, 'macd_hist', 0) > 0:
        trend_score += 1

    # --- 수급 스코어 (0~2) ---
    supply_score = 0
    if summary_trend == "상승":
        supply_score += 1
    if _safe_get(indicators, 'vol_ratio', 0) > 1.0:
        supply_score += 1

    # --- 과매수/과매도 카운트 ---
    rsi_val = _safe_get(indicators, 'rsi')
    sk_val = _safe_get(indicators, 'stoch_k')
    disp_val = _safe_get(indicators, 'disparity')

    overbought = 0
    if rsi_val is not None and rsi_val > 70:
        overbought += 1
    if sk_val is not None and sk_val > 80:
        overbought += 1
    if disp_val is not None and disp_val > 105:
        overbought += 1

    oversold = 0
    if rsi_val is not None and rsi_val < 30:
        oversold += 1
    if sk_val is not None and sk_val < 20:
        oversold += 1
    if disp_val is not None and disp_val < 95:
        oversold += 1

    summary = []

    # 1. 추세 + 수급 종합 판단
    if trend_score == 3 and supply_score == 2:
        summary.append("추세/수급/거래량 모두 강세. 현재 구간은 상승 추세가 확실하게 확인됩니다.")
    elif trend_score >= 2 and supply_score >= 1:
        summary.append("추세와 수급 모두 양호한 상태입니다. 상승 흐름이 유지되고 있습니다.")
    elif trend_score >= 2:
        summary.append("가격 추세는 살아있으나 수급(거래량/OBV)이 뒷받침되지 않고 있어 주의가 필요합니다.")
    elif supply_score >= 1 and trend_score >= 1:
        summary.append("추세가 약해지고 있으나 일부 수급 신호가 남아있어 방향 전환을 관찰할 필요가 있습니다.")
    elif trend_score <= 1 and supply_score == 0:
        summary.append("추세와 수급 모두 약세 구간입니다. 시장의 관심이 이탈된 상태로 판단됩니다.")
    else:
        summary.append("혼조세 구간입니다. 뚜렷한 방향성이 보이지 않아 관망이 유리합니다.")

    # 2. 과매수/과매도 경고
    if overbought >= 2:
        if overbought == 3:
            summary.append("경고: RSI/스토캐스틱/이격도 모두 과열. 단기 고점 형성 가능성이 높습니다.")
        else:
            summary.append("주의: 복수 지표가 과매수 영역 진입. 차익 실현 압력에 대비하세요.")
    elif oversold >= 2:
        if oversold == 3:
            summary.append("주목: RSI/스토캐스틱/이격도 모두 과매도. 기술적 반등 확률이 높은 구간입니다.")
        else:
            summary.append("참고: 복수 지표가 과매도 영역. 바닥 확인 후 기술적 반등을 기대할 수 있습니다.")

    # 3. 교차 시그널 (추세 vs 수급 다이버전스)
    if trend_score >= 2 and summary_trend == "하락":
        summary.append("참고: 가격은 상승세이나 OBV는 하락 중 (약세 다이버전스). 추세 지속력에 의문이 있습니다.")
    elif trend_score <= 1 and summary_trend == "상승":
        summary.append("참고: 가격은 약세이나 OBV는 상승 중 (강세 다이버전스). 저점 매집 가능성을 시사합니다.")

    # 4. 거래량 이상 감지
    vol_r = _safe_get(indicators, 'vol_ratio')
    if vol_r is not None and vol_r >= 3.0:
        summary.append("주의: 거래량이 평소 대비 3배 이상 급증. 대형 이벤트 또는 세력 개입 가능성을 확인하세요.")

    labels['total_summary'] = "\n- ".join(summary)

    # 4. 요약 시그널 (Short Label)
    if oversold >= 2:
        labels['signal_short'] = "과매도(침체)"
    elif overbought >= 2:
        labels['signal_short'] = "과열(주의)"
    elif trend_score >= 2 and supply_score >= 1:
        labels['signal_short'] = "강세"
    elif trend_score >= 2:
        labels['signal_short'] = "신호혼조(추세만)"
    elif supply_score >= 1 and trend_score >= 1:
        labels['signal_short'] = "바닥탈출시도"
    elif trend_score <= 1 and supply_score == 0:
        labels['signal_short'] = "조정/약세"
    else:
        labels['signal_short'] = "관망/혼조"

    return labels
