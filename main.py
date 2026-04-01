import os
import sys
import certifi
import math
import time
from datetime import datetime
from tabulate import tabulate
from analyzer.data_fetcher import fetch_stock_data
from analyzer.indicators import calculate_all_indicators
from analyzer.interpreter import interpret_indicators
from analyzer.watchlist import get_watchlist, add_tickers, remove_tickers, clear_watchlist

VERSION = "1.0.0"


def fmt_num(value, precision=2, signed=False):
    """
    숫자를 안전하게 포맷팅합니다.
    작은 수(1 미만)는 자동으로 정밀도를 높여 '0'으로 표시되는 것을 방지합니다.
    """
    if value is None:
        return "N/A"
    try:
        if not math.isfinite(value):
            return "N/A"
        
        # 작은 수(소수점 이하가 중요한 경우) 자동 정밀도 조정
        abs_v = abs(value)
        ext_precision = precision
        if 0 < abs_v < 1:
            if abs_v < 0.01:
                ext_precision = max(precision, 5)
            else:
                ext_precision = max(precision, 3)
        
        sign = "+" if signed and value > 0 else ""
        return f"{sign}{value:,.{ext_precision}f}"
    except (TypeError, ValueError):
        return "N/A"


def print_banner():
    """시작 배너 출력"""
    print("=" * 50)
    print(f"   시장 신호 분석기 v{VERSION}")
    print(f"   Market Signal Analyzer")
    print("=" * 50)
    print()
    print("  사용법:")
    print("    티커 입력    삼성전자: 005930 / 미국: TSLA")
    print("    다종목 비교  AAPL, MSFT, NVDA")
    print("    워치리스트   wl add 005930 TSLA  /  wl")
    print("    도움말       help")
    print("    종료         q 또는 exit")
    print()


def print_help():
    """도움말 출력"""
    print()
    print("-" * 50)
    print("  [명령어 안내]")
    print("-" * 50)
    print()
    print("  <티커>              단일 종목 상세 분석")
    print("  <티커>,<티커>,...   다종목 요약 비교 테이블")
    print()
    print("  [입력 예시]")
    print("    005930            삼성전자 (코스피)")
    print("    035720            카카오 (코스닥)")
    print("    TSLA              테슬라 (미국)")
    print("    AAPL, MSFT, NVDA  다종목 비교")
    print()
    print("  [워치리스트]")
    print("    wl                워치리스트 종목 일괄 분석")
    print("    wl list           저장된 종목 목록 보기")
    print("    wl add <종목>     종목 추가 (복수 가능)")
    print("    wl rm <종목>      종목 제거")
    print("    wl clear          전체 초기화")
    print()
    print("  [기타 명령어]")
    print("    help              이 도움말 표시")
    print("    clear / cls       화면 정리")
    print("    q / quit / exit   프로그램 종료")
    print()
    print("  [분석 지표]")
    print("    VWAP, 거래량, 모멘텀(10), 스토캐스틱")
    print("    이격도(20), MACD, RSI(14), OBV")
    print()
    print("  [참고]")
    print("    한국 주식은 6자리 종목코드를 입력하면")
    print("    코스피(.KS)/코스닥(.KQ)을 자동 검색합니다.")
    print()


def clear_screen():
    """화면 정리"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_detail_report(ticker_data):
    """
    단일 종목에 대한 상세 보고서를 출력합니다.
    """
    ticker = ticker_data['ticker']
    price = ticker_data['current_price']
    indicators = calculate_all_indicators(ticker_data)
    
    # [수정] 포괄적 상태 체크 및 예외 처리
    status = indicators.get('status')
    if status == "no_daily_data":
        print(f"\n[오류] {ticker}: 해당 종목의 데이터를 찾을 수 없습니다.")
        return
    elif status == "invalid_columns":
        print(f"\n[오류] {ticker}: {indicators.get('message')}")
        return
    elif status == "insufficient_data":
        print(f"\n[알림] {ticker}: 지표 분석을 위한 충분한 기간(최소 35일)의 데이터가 부족합니다.")
        return
    elif status == "calculation_error":
        print(f"\n[에러] {ticker}: 지표 계산 중 오류 발생 ({indicators.get('message')})")
        return

    labels = interpret_indicators(price, indicators)
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    market = ticker_data.get('market', '')
    market_label = {"KRX": "한국", "US": "미국"}.get(market, market)
    
    print()
    print("=" * 40)
    print(f"  Ticker: {ticker}")
    if market_label:
        print(f"  Market: {market_label}")
    print(f"  Date:   {now}")
    
    # 데이터 선택 정보 출력
    selection = ticker_data.get('selection_info')
    if selection:
        print(f"  Status: {selection['selection_label']}")
        print(f"  Bar:    {selection['used_daily_date']}")
        
    print(f"  Price:  {fmt_num(price)}")
    print("=" * 40)
    print("\n[지표 현황]")
    
    # VWAP
    vwap = indicators.get('vwap')
    print(f"VWAP: {fmt_num(vwap, 3)}")
    print(f"- {labels['vwap_status']}")
    print(f"- {labels['vwap_desc']}")
    
    # 거래량
    vol_display = ticker_data.get('volume')
    print(f"\n거래량: {fmt_num(vol_display, 0)}")
    print(f"- {labels['vol_status']}")
    print(f"- {labels['vol_desc']}")
    
    # 모멘텀
    mom = indicators.get('momentum')
    print(f"\n모멘텀(10): {fmt_num(mom, 3, signed=True)}")
    print(f"- {labels['mom_desc']}")
    
    # 스토캐스틱
    sk, sd = indicators.get('stoch_k'), indicators.get('stoch_d')
    if sk is not None and sd is not None:
        print(f"\n스토캐스틱 %K / %D: {fmt_num(sk)} / {fmt_num(sd)}")
    else:
        print("\n스토캐스틱 %K / %D: N/A")
    print(f"- {labels['stoch_desc']}")
    
    # 이격도
    disp = indicators.get('disparity')
    print(f"\n이격도(20): {fmt_num(disp)}%")
    print(f"- {labels['disp_status']}")
    print(f"- {labels['disp_desc']}")
    
    # MACD
    macd, msig, mhist = indicators.get('macd'), indicators.get('macd_signal'), indicators.get('macd_hist')
    if macd is not None and msig is not None and mhist is not None:
        print(f"\nMACD: {macd:.3f} / Signal: {msig:.3f} / Hist: {mhist:+.3f}")
    else:
        print("\nMACD: N/A")
    print(f"- {labels['macd_desc']}")
    
    # RSI
    rsi = indicators.get('rsi')
    print(f"\nRSI(14): {fmt_num(rsi, 1)}")
    print(f"- {labels['rsi_desc']}")
    
    # OBV (딕셔너리 구조 반영)
    print(f"\nOBV: {labels['obv_trend']} 추세")
    print(f"- {labels['obv_desc']}")
    
    print("\n[종합 해석]")
    print(f"- {labels['total_summary']}")
    print()

def print_summary_table(tickers):
    """
    여러 종목에 대한 요약 테이블을 출력합니다.
    """
    table_data = []
    headers = ["Ticker", "Price", "RSI", "MACD Hist", "Stoch K", "OBV", "Signal"]
    
    total = len(tickers)
    for i, t in enumerate(tickers, 1):
        print(f"  ({i}/{total}) {t.strip().upper()} 분석 중...", end="\r")
        data = fetch_stock_data(t.strip())
        if not data:
            continue
            
        indicators = calculate_all_indicators(data)
        
        status = indicators.get('status')
        if status != "ok":
            table_data.append([data['ticker'], fmt_num(data.get('current_price')), "-", "-", "-", "-", f"분석불가({status})"])
            continue

        price = data['current_price']
        rsi = indicators.get('rsi')
        mhist = indicators.get('macd_hist')
        sk = indicators.get('stoch_k')
        obv_trend = indicators.get('obv', {}).get('trend', '-')
        
        # 지표 해석 및 종합 시그널 생성 (interpreter 연동)
        labels = interpret_indicators(price, indicators)
        signal = labels.get('signal_short', '판단불가')

        table_data.append([
            data['ticker'],
            fmt_num(price),
            fmt_num(rsi, 1) if rsi is not None else "-",
            fmt_num(mhist, 1, signed=True) if mhist is not None else "-",
            fmt_num(sk, 1) if sk is not None else "-",
            obv_trend,
            signal
        ])
    
    # 진행 표시 줄 정리
    print(" " * 50, end="\r")
    
    print("\n[전 종목 요약 리포트]")
    print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    print("\n  * 상세 분석은 종목을 하나만 입력하세요.")

def configure_ca_bundle():
    """
    EXE 실행 환경에서 SSL 인증서 경로(cacert.pem)를 올바르게 설정합니다.
    yfinance(curl_cffi/libcurl)의 SSL 검증 오류(curl 77)를 해결합니다.
    """
    import os
    import sys
    try:
        import certifi
        if getattr(sys, "frozen", False):
            ca_path = certifi.where()
            os.environ["SSL_CERT_FILE"] = ca_path
            os.environ["CURL_CA_BUNDLE"] = ca_path
            os.environ["REQUESTS_CA_BUNDLE"] = ca_path
    except ImportError:
        pass


def main():
    configure_ca_bundle()
    print_banner()

    while True:
        # 명령줄 인자가 있을 경우 최초 1회만 처리하고 이후에는 입력을 기다림
        if len(sys.argv) >= 2:
            input_str = sys.argv[1]
            sys.argv = [sys.argv[0]] # 인자 초기화 (다음 루프부터는 input() 사용)
        else:
            now_str = datetime.now().strftime("%H:%M")
            print("-" * 50)
            input_str = input(f"[{now_str}] 티커 입력 (help: 도움말): ").strip()
            
        cmd = input_str.lower()
        
        # 내장 명령어 처리
        if cmd in ('exit', 'quit', 'q'):
            print("\n프로그램을 종료합니다.")
            break
        
        if cmd == 'help':
            print_help()
            continue
            
        if cmd in ('clear', 'cls'):
            clear_screen()
            print_banner()
            continue
            
        if not input_str:
            continue

        # --- 워치리스트 명령어 처리 ---
        if cmd == 'wl' or cmd == 'watchlist':
            wl = get_watchlist()
            if not wl:
                print("\n  워치리스트가 비어있습니다. 'wl add <종목>' 으로 추가하세요.")
            else:
                print(f"\n  워치리스트 {len(wl)}개 종목 분석을 시작합니다.")
                start_time = time.time()
                print_summary_table(wl)
                elapsed = time.time() - start_time
                print(f"  분석 완료 ({elapsed:.1f}초)")
            print()
            continue

        if cmd.startswith('wl ') or cmd.startswith('watchlist '):
            parts = input_str.split()
            sub = parts[1].lower() if len(parts) > 1 else ''
            args = [t.strip().upper() for t in parts[2:] if t.strip()]

            if sub == 'list' or sub == 'ls':
                wl = get_watchlist()
                if not wl:
                    print("\n  워치리스트가 비어있습니다.")
                else:
                    print(f"\n  [워치리스트] {len(wl)}개 종목")
                    for i, t in enumerate(wl, 1):
                        print(f"    {i}. {t}")
                print()

            elif sub == 'add':
                if not args:
                    print("\n  사용법: wl add <종목1> <종목2> ...")
                else:
                    added = add_tickers(args)
                    if added:
                        print(f"\n  추가됨: {', '.join(added)}")
                    else:
                        print("\n  이미 등록된 종목입니다.")
                    wl = get_watchlist()
                    print(f"  현재 워치리스트: {', '.join(wl)} ({len(wl)}개)")
                print()

            elif sub in ('rm', 'del', 'remove', 'delete'):
                if not args:
                    print("\n  사용법: wl rm <종목>")
                else:
                    removed = remove_tickers(args)
                    if removed:
                        print(f"\n  제거됨: {', '.join(removed)}")
                    else:
                        print(f"\n  '{' '.join(args)}'은(는) 워치리스트에 없습니다.")
                    wl = get_watchlist()
                    if wl:
                        print(f"  현재 워치리스트: {', '.join(wl)} ({len(wl)}개)")
                    else:
                        print("  워치리스트가 비어있습니다.")
                print()

            elif sub == 'clear':
                clear_watchlist()
                print("\n  워치리스트를 초기화했습니다.")
                print()

            else:
                # wl 뒤에 종목을 바로 적은 경우 → 추가로 해석
                all_args = [t.strip().upper() for t in parts[1:] if t.strip()]
                added = add_tickers(all_args)
                if added:
                    print(f"\n  추가됨: {', '.join(added)}")
                    wl = get_watchlist()
                    print(f"  현재 워치리스트: {', '.join(wl)} ({len(wl)}개)")
                else:
                    print(f"\n  알 수 없는 워치리스트 명령: '{sub}'")
                    print("  사용법: wl [list|add|rm|clear]")
                print()

            continue
            
        tickers = [t.strip().upper() for t in input_str.split(',') if t.strip()]
        
        try:
            start_time = time.time()
            
            if len(tickers) == 1:
                # 단일 종목 상세 보고서
                print(f"\n  {tickers[0]} 데이터 수집 중...")
                data = fetch_stock_data(tickers[0])
                if data:
                    print_detail_report(data)
                else:
                    print(f"\n  [!] '{tickers[0]}' 종목을 찾을 수 없습니다.")
                    if tickers[0].isdigit():
                        print(f"      한국 주식은 6자리 코드를 입력하세요. (예: 005930)")
                    else:
                        print(f"      티커가 정확한지 확인해 주세요. (예: TSLA, AAPL)")
            else:
                # 다수 종목 요약 테이블
                print(f"\n  {len(tickers)}개 종목 분석을 시작합니다.")
                print_summary_table(tickers)
            
            elapsed = time.time() - start_time
            print(f"  분석 완료 ({elapsed:.1f}초)")
            print()
            
        except KeyboardInterrupt:
            print("\n\n  분석이 중단되었습니다.")
            continue
        except Exception as e:
            print(f"\n  [오류] 분석 중 문제가 발생했습니다: {e}")
        
    print()
    input("종료하려면 엔터를 누르세요...")

if __name__ == "__main__":
    main()
