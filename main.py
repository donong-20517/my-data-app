# main.py
# 어제의 박스오피스를 KOBIS API에서 가져와 보여주는 Streamlit 앱입니다.

import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 기준 · 한국 시간")


# KOBIS 일별 박스오피스 API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------

# 배포 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 Asia/Seoul 시간대를 지정합니다.
KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 오늘에서 하루를 빼서 '어제'를 구합니다.
yesterday = now_kst - timedelta(days=1)

# KOBIS API가 요구하는 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 3. KOBIS API에서 데이터 가져오기
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    KOBIS API에서 특정 날짜의 박스오피스를 가져옵니다.

    ttl=3600:
    같은 날짜의 결과를 약 1시간 동안 캐시해서
    API를 불필요하게 다시 호출하지 않습니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키는 코드에 작성하지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 "
                "Secrets에 KOBIS_KEY가 등록되어 있는지 확인하세요."
            )
        }

    # KOBIS API에 보낼 요청값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # API 호출
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있으면 예외 발생
        response.raise_for_status()

        # JSON 응답으로 변환
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "인터넷 연결, KOBIS API 주소 또는 "
                "KOBIS 서버 상태를 확인하세요.\n\n"
                f"오류 내용: {e}"
            )
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS에서 정상적인 JSON 응답을 받지 못했습니다.\n\n"
                "KOBIS API 서버의 응답 상태를 확인하세요."
            )
        }

    # -----------------------------------------------------
    # 4. 인증키 오류 확인
    # -----------------------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 직접 확인해야 합니다.

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        # faultInfo 안의 오류 메시지를 최대한 읽어옵니다.
        if isinstance(fault_info, dict):
            fault_code = fault_info.get("errorCode", "알 수 없음")
            fault_message = fault_info.get(
                "message",
                "KOBIS API에서 오류를 반환했습니다."
            )

            message = (
                f"KOBIS API 오류가 발생했습니다.\n\n"
                f"- 오류 코드: {fault_code}\n"
                f"- 오류 메시지: {fault_message}\n\n"
                "KOBIS_KEY가 정확한지 확인하세요."
            )
        else:
            message = (
                "KOBIS API에서 faultInfo 오류를 반환했습니다.\n\n"
                "KOBIS_KEY와 API 요청 설정을 확인하세요."
            )

        return {
            "success": False,
            "message": message
        }

    # -----------------------------------------------------
    # 5. 영화 목록 확인
    # -----------------------------------------------------

    boxoffice_result = data.get("boxOfficeResult", {})

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 사용자에게 확인할 사항을 알려줍니다.
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 영화 목록이 없습니다.\n\n"
                "다음 사항을 확인하세요.\n"
                "1. KOBIS에서 해당 날짜의 일별 박스오피스가 집계되었는지\n"
                "2. 조회 날짜가 정상적으로 전달되었는지\n"
                "3. KOBIS API 서버에 문제가 없는지"
            )
        }

    # 정상적으로 데이터를 가져온 경우
    return {
        "success": True,
        "data": movie_list
    }


# ---------------------------------------------------------
# 6. 데이터 가져오기
# ---------------------------------------------------------

result = get_boxoffice(target_date)

# 오류가 발생했다면 빈 화면 대신 안내 메시지를 보여줍니다.
if not result["success"]:
    st.error(result["message"])
    st.stop()


movie_list = result["data"]


# ---------------------------------------------------------
# 7. 데이터프레임 만들기
# ---------------------------------------------------------

df = pd.DataFrame(movie_list)


# KOBIS에서 숫자가 문자열로 오기 때문에
# 실제 숫자형으로 변환합니다.
numeric_columns = [
    "rank",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
    "rankInten"
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0)


# 순위 기준으로 정렬
df = df.sort_values("rank").reset_index(drop=True)


# ---------------------------------------------------------
# 8. 1위 영화 정보
# ---------------------------------------------------------

first_movie = df.iloc[0]

movie_name = first_movie["movieNm"]
audience_count = int(first_movie["audiCnt"])
total_audience = int(first_movie["audiAcc"])
screen_count = int(first_movie["scrnCnt"])


st.subheader(f"🏆 1위: {movie_name}")

st.caption(f"{display_date} 일일 박스오피스")


# 숫자를 보기 편하게 천 단위 콤마로 표시합니다.
card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="어제 관객수",
        value=f"{audience_count:,}명"
    )

with card2:
    st.metric(
        label="누적 관객수",
        value=f"{total_audience:,}명"
    )

with card3:
    st.metric(
        label="스크린수",
        value=f"{screen_count:,}개"
    )


# ---------------------------------------------------------
# 9. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
      .head(5)
      .copy()
)

# 그래프의 가로축에 영화명을 사용합니다.
chart_data = top5.set_index("movieNm")[["audiCnt"]]

# Streamlit의 기본 막대그래프를 사용합니다.
st.bar_chart(chart_data, x_label="영화", y_label="관객수")


# ---------------------------------------------------------
# 10. 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

# 화면에 보여줄 열만 선택합니다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 사용자가 보기 쉬운 한국어 열 이름으로 변경합니다.
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자에 천 단위 콤마를 표시합니다.
# 내부 데이터는 이미 숫자형이므로 정렬/그래프에는 숫자로 사용됩니다.
st.dataframe(
    table_df.style.format(
        {
            "관객수": "{:,.0f}",
            "누적관객": "{:,.0f}",
            "스크린수": "{:,.0f}"
        }
    ),
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 11. 데이터 출처
# ---------------------------------------------------------

st.caption(
    f"조회 기준일: {display_date} · "
    "출처: KOBIS 영화관입장권통합전산망"
)
