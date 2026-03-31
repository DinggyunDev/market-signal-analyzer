"""
Watchlist 관리 모듈
JSON 파일 기반으로 사용자의 관심 종목 리스트를 저장/조회/관리합니다.
"""
import json
import os

DEFAULT_WATCHLIST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "watchlist.json"
)


def _load(path=None):
    """watchlist 파일 로드. 없으면 빈 리스트 반환"""
    path = path or DEFAULT_WATCHLIST_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _save(tickers, path=None):
    """watchlist 파일 저장"""
    path = path or DEFAULT_WATCHLIST_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tickers, f, ensure_ascii=False, indent=2)


def get_watchlist(path=None):
    """현재 워치리스트 반환"""
    return _load(path)


def add_tickers(new_tickers, path=None):
    """
    워치리스트에 종목 추가 (중복 무시).
    추가된 종목 리스트 반환.
    """
    current = _load(path)
    current_upper = [t.upper() for t in current]
    added = []
    for t in new_tickers:
        t_upper = t.strip().upper()
        if t_upper and t_upper not in current_upper:
            current.append(t_upper)
            current_upper.append(t_upper)
            added.append(t_upper)
    _save(current, path)
    return added


def remove_tickers(rm_tickers, path=None):
    """
    워치리스트에서 종목 제거.
    제거된 종목 리스트 반환.
    """
    current = _load(path)
    rm_upper = [t.strip().upper() for t in rm_tickers]
    removed = [t for t in current if t.upper() in rm_upper]
    remaining = [t for t in current if t.upper() not in rm_upper]
    _save(remaining, path)
    return removed


def clear_watchlist(path=None):
    """워치리스트 전체 초기화"""
    _save([], path)
