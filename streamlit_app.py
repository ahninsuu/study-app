import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Study Tracker", page_icon="📚")

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

st.title("📚 나만의 학습 기록장")

@st.cache_resource
def get_sheets_client():
    # 1. 시크릿(Service Account) 확인 (클라우드/배포 환경용)
    if "gcp_service_account" in st.secrets:
        try:
            # st.secrets에 딕셔너리 형태로 저장된 경우 바로 사용
            return gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        except Exception as e:
            st.error(f"서비스 계정 인증 중 오류 발생: {e}")

    # 1.5. 시크릿(OAuth Token) 확인 (클라우드/배포 환경에서 서비스 계정을 만들 수 없을 때의 대안)
    if "oauth_token" in st.secrets:
        try:
            # 로컬에서 생성된 token.json 내용을 그대로 시크릿에 넣어 활용
            token_info = st.secrets["oauth_token"]
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return gspread.authorize(creds)
        except Exception as e:
            st.error(f"OAuth 시크릿 인증 중 오류 발생: {e}")

    # 2. 로컬 OAuth 인증 (개발 환경용)
    # credentials.json 파일이 없으면 안내 메시지 출력
    if not os.path.exists('credentials.json') and not os.path.exists('token.json'):
         st.error("인증 정보가 없습니다. 클라우드 배포 시에는 'Secrets' 설정을, 로컬 개발 시에는 'credentials.json' 파일을 준비해 주세요.")
         st.stop()

    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return gspread.authorize(creds)

# 1. 인증 진행
try:
    gc = get_sheets_client()
except Exception as e:
    st.error(f"구글 로그인 인증에 실패했습니다! (에러: {e})")
    st.stop()

# 2. 스프레드시트 URL 입력 (초기 1회)
sheet_url = st.text_input("스프레드시트 URL을 입력해주세요 (브라우저 주소창 복사)", placeholder="https://docs.google.com/spreadsheets/d/...")

if sheet_url:
    try:
        sh = gc.open_by_url(sheet_url)
        worksheet = sh.sheet1
        
        # 3. 빈 시트일 경우 헤더 자동 추가
        # gspread에서 빈 시트를 읽을 때 row_values에서 에러가 날 수 있으므로 예외 처리
        try:
            first_row = worksheet.row_values(1)
        except Exception:
            first_row = []
            
        if len(first_row) == 0:
            worksheet.append_row(["날짜", "과목", "공부시간(분)", "메모"])
            
        # 4. 데이터 가져오기 (헤더 제외)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        st.subheader("📝 나의 학습 기록")
        if df.empty:
            st.info("아직 입력된 기록이 없습니다! 아래 폼에서 기록을 추가해보세요.")
        else:
            st.dataframe(df, use_container_width=True)

        st.divider()
        
        # 5. 새 기록 추가 폼
        st.subheader("➕ 새 기록 추가하기")
        with st.form("add_record_form"):
            date_input = st.date_input("날짜", datetime.today())
            subject_input = st.text_input("과목명", placeholder="예: Python, 알고리즘...")
            time_input = st.number_input("공부시간 (분)", min_value=1, value=60)
            memo_input = st.text_area("메모", placeholder="오늘은 어떤 내용을 공부했나요?")
            
            submit_button = st.form_submit_button("저장하기")
            
            if submit_button:
                if not subject_input:
                    st.warning("과목명을 입력해주세요!")
                else:
                    new_row = [str(date_input), subject_input, time_input, memo_input]
                    worksheet.append_row(new_row)
                    st.success("성공적으로 저장되었습니다! 🎈")
                    st.rerun()

    except Exception as e:
        st.error(f"스프레드시트를 불러오는 중 오류가 발생했습니다: {e}\n\n시트 URL이 올바른지 확인해주세요!")
else:
    st.info("시작하려면 데이터를 저장할 구글 스프레드시트를 하나 만들고 위의 칸에 URL을 붙여넣어 주세요.")
    st.markdown("- **참고:** 스프레드시트는 사용자의 구글 계정에 빈 문서로 새로 만들어두시기만 하면 됩니다.")
