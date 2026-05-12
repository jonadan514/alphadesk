"""
KOSPI 주요 종목 리스트 (KOSPI 100 수준)
yfinance .KS 티커 기준
"""
import pandas as pd

KOSPI_STOCKS = [
    ("005930", "삼성전자",        "Technology"),
    ("000660", "SK하이닉스",       "Technology"),
    ("373220", "LG에너지솔루션",   "Industrials"),
    ("207940", "삼성바이오로직스", "Healthcare"),
    ("005380", "현대차",           "Consumer Cyclical"),
    ("000270", "기아",             "Consumer Cyclical"),
    ("035420", "NAVER",            "Communication Services"),
    ("051910", "LG화학",           "Basic Materials"),
    ("068270", "셀트리온",         "Healthcare"),
    ("028260", "삼성물산",         "Industrials"),
    ("035720", "카카오",           "Communication Services"),
    ("006400", "삼성SDI",          "Technology"),
    ("003550", "LG",               "Industrials"),
    ("105560", "KB금융",           "Financial Services"),
    ("055550", "신한지주",         "Financial Services"),
    ("086790", "하나금융지주",     "Financial Services"),
    ("032830", "삼성생명",         "Financial Services"),
    ("316140", "우리금융지주",     "Financial Services"),
    ("012330", "현대모비스",       "Consumer Cyclical"),
    ("009150", "삼성전기",         "Technology"),
    ("066570", "LG전자",           "Technology"),
    ("017670", "SK텔레콤",         "Communication Services"),
    ("030200", "KT",               "Communication Services"),
    ("096770", "SK이노베이션",     "Energy"),
    ("034730", "SK",               "Industrials"),
    ("000810", "삼성화재",         "Financial Services"),
    ("010130", "고려아연",         "Basic Materials"),
    ("047050", "포스코홀딩스",     "Basic Materials"),
    ("033780", "KT&G",             "Consumer Defensive"),
    ("015760", "한국전력",         "Utilities"),
    ("009540", "한국조선해양",     "Industrials"),
    ("010950", "S-Oil",            "Energy"),
    ("042660", "한화오션",         "Industrials"),
    ("034020", "두산에너빌리티",   "Industrials"),
    ("097950", "CJ제일제당",       "Consumer Defensive"),
    ("028050", "삼성엔지니어링",   "Industrials"),
    ("018880", "한화",             "Industrials"),
    ("011200", "HMM",              "Industrials"),
    ("021240", "코웨이",           "Consumer Defensive"),
    ("282330", "BGF리테일",        "Consumer Defensive"),
    ("271560", "오리온",           "Consumer Defensive"),
    ("139480", "이마트",           "Consumer Defensive"),
    ("004170", "신세계",           "Consumer Cyclical"),
    ("003490", "대한항공",         "Industrials"),
    ("009830", "한화솔루션",       "Technology"),
    ("402340", "SK스퀘어",         "Technology"),
    ("078930", "GS",               "Energy"),
    ("088350", "한화생명",         "Financial Services"),
    ("032640", "LG유플러스",       "Communication Services"),
    ("034220", "LG디스플레이",     "Technology"),
    ("005300", "롯데칠성",         "Consumer Defensive"),
    ("004990", "롯데지주",         "Consumer Cyclical"),
    ("002790", "아모레퍼시픽",     "Consumer Defensive"),
    ("051900", "LG생활건강",       "Consumer Defensive"),
    ("161390", "한국타이어앤테크놀로지", "Consumer Cyclical"),
    ("008770", "호텔신라",         "Consumer Cyclical"),
    ("000100", "유한양행",         "Healthcare"),
    ("068760", "셀트리온제약",     "Healthcare"),
    ("196170", "알테오젠",         "Healthcare"),
    ("086520", "에코프로",         "Basic Materials"),
    ("247540", "에코프로비엠",     "Basic Materials"),
    ("036570", "엔씨소프트",       "Communication Services"),
    ("259960", "크래프톤",         "Communication Services"),
    ("352820", "하이브",           "Communication Services"),
    ("041510", "에스엠",           "Communication Services"),
    ("035900", "JYP Ent.",         "Communication Services"),
    ("079550", "LIG넥스원",        "Industrials"),
    ("004020", "현대제철",         "Basic Materials"),
    ("011780", "금호석유화학",     "Basic Materials"),
    ("000720", "현대건설",         "Industrials"),
    ("006360", "GS건설",           "Industrials"),
    ("024110", "기업은행",         "Financial Services"),
    ("000080", "하이트진로",       "Consumer Defensive"),
    ("001450", "현대해상",         "Financial Services"),
    ("090430", "아모레G",          "Consumer Defensive"),
    ("010140", "삼성중공업",       "Industrials"),
    ("003600", "SK케미칼",         "Healthcare"),
    ("058470", "리노공업",         "Technology"),
    ("263750", "펄어비스",         "Communication Services"),
    ("180640", "한진칼",           "Industrials"),
    ("010060", "OCI홀딩스",        "Basic Materials"),
    ("001040", "CJ",               "Consumer Defensive"),
    ("000120", "CJ대한통운",       "Industrials"),
    ("011170", "롯데케미칼",       "Basic Materials"),
    ("023530", "롯데쇼핑",         "Consumer Cyclical"),
    ("005490", "POSCO홀딩스",      "Basic Materials"),
    ("018260", "삼성SDS",          "Technology"),
]


def get_kospi_list() -> pd.DataFrame:
    rows = [
        {"Symbol": f"{code}.KS", "Code": code, "Name": name, "Sector": sector}
        for code, name, sector in KOSPI_STOCKS
    ]
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = get_kospi_list()
    print(f"총 {len(df)}개 종목")
    print(df.head())
