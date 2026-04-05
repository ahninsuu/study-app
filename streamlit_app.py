import streamlit as st
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pandas as pd
from datetime import datetime
import json
import time

st.set_page_config(page_title="Study Tracker", page_icon="📚", layout="wide")

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

@st.cache_resource
def get_sheets_client():
    # 1. 시크릿(Service Account) 확인 (클라우드/배포 환경용)
    if "gcp_service_account" in st.secrets:
        try:
            return gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        except Exception as e:
            st.error(f"서비스 계정 인증 중 오류 발생: {e}")

    # 1.5. 시크릿(OAuth Token) 확인 (클라우드/배포 환경에서 서비스 계정을 만들 수 없을 때의 대안)
    if "oauth_token" in st.secrets:
        try:
            token_info = dict(st.secrets["oauth_token"])
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return gspread.authorize(creds)
        except Exception as e:
            st.error(f"OAuth 시크릿 인증 중 오류 발생: {e}")

    # 2. 로컬 OAuth 인증 (개발 환경용)
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
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return gspread.authorize(creds)

try:
    gc = get_sheets_client()
except Exception as e:
    st.error(f"구글 로그인 인증에 실패했습니다! (에러: {e})")
    st.stop()

# 2. 사용할 스프레드시트 주소 (고정)
SHEET_URL = "https://docs.google.com/spreadsheets/d/여기에_실제_주소_붙여넣기"
if "sheet_url" in st.secrets:
    SHEET_URL = st.secrets["sheet_url"]

if SHEET_URL and "여기에_실제_주소_붙여넣기" not in SHEET_URL:
    try:
        sh = gc.open_by_url(SHEET_URL)
        worksheet = sh.sheet1
        
        # --- Data Sync Methods ---
        def sync_to_gsheets(subjects):
            try:
                worksheet.clear()
                data = [["id", "name", "chapters_json"]]
                for sub in subjects:
                    # 빈 리스트 처리 및 json 덤프
                    data.append([
                        str(sub.get("id", "")), 
                        str(sub.get("name", "")), 
                        json.dumps(sub.get("chapters", []), ensure_ascii=False)
                    ])
                worksheet.update(values=data, range_name="A1")
            except Exception as e:
                st.error(f"구글 시트 저장 실패: {e}")

        # --- DB Loading ---
        if "db_loaded" not in st.session_state:
            # 빈 시트일 경우 발생할 수 있는 오류 방어
            try:
                records = worksheet.get_all_records()
            except Exception:
                records = []
                
            if not records:
                default_sub = {
                    "id": f"sub-{int(time.time()*1000)}",
                    "name": "새 과목",
                    "chapters": []
                }
                st.session_state.subjects = [default_sub]
                sync_to_gsheets(st.session_state.subjects)
            else:
                subs = []
                for r in records:
                    try:
                        chaps = json.loads(str(r.get("chapters_json", "[]")))
                    except:
                        chaps = []
                    subs.append({
                        "id": str(r.get("id")),
                        "name": str(r.get("name")),
                        "chapters": chaps
                    })
                st.session_state.subjects = subs
            st.session_state.db_loaded = True

        # 상태 초기화
        if "active_subject_id" not in st.session_state:
             if st.session_state.subjects:
                 st.session_state.active_subject_id = st.session_state.subjects[0]["id"]
             else:
                 st.session_state.active_subject_id = None

        # --- Header ---
        st.title("📚 나만의 학습 매니저")
        
        # --- Subject Selector & Manager ---
        if not st.session_state.subjects:
            if st.button("➕ 새 과목 시작하기"):
                new_sub = {"id": f"sub-{int(time.time()*1000)}", "name": "새 과목", "chapters": []}
                st.session_state.subjects.append(new_sub)
                st.session_state.active_subject_id = new_sub["id"]
                sync_to_gsheets(st.session_state.subjects)
                st.rerun()
            st.stop()

        sub_names = {s["id"]: s["name"] for s in st.session_state.subjects}
        opt_idx = 0
        if st.session_state.active_subject_id in sub_names:
            opt_idx = list(sub_names.keys()).index(st.session_state.active_subject_id)
            
        c1, c2, c3 = st.columns([6, 2, 2])
        selected_sub_id = c1.selectbox("과목 선택", options=list(sub_names.keys()), format_func=lambda x: sub_names[x], index=opt_idx)
        
        if selected_sub_id != st.session_state.active_subject_id:
            st.session_state.active_subject_id = selected_sub_id
            st.rerun()

        if c2.button("➕ 새 과목", use_container_width=True):
            new_sub = {"id": f"sub-{int(time.time()*1000)}", "name": "새 과목", "chapters": []}
            st.session_state.subjects.append(new_sub)
            st.session_state.active_subject_id = new_sub["id"]
            sync_to_gsheets(st.session_state.subjects)
            st.rerun()

        if c3.button("🗑️ 과목 삭제", use_container_width=True):
            if len(st.session_state.subjects) > 1:
                st.session_state.subjects = [s for s in st.session_state.subjects if s["id"] != st.session_state.active_subject_id]
                st.session_state.active_subject_id = st.session_state.subjects[0]["id"]
                sync_to_gsheets(st.session_state.subjects)
                st.rerun()
            else:
                st.error("최소 하나의 과목은 유지되어야 합니다.")
                
        active_subject = next((s for s in st.session_state.subjects if s["id"] == st.session_state.active_subject_id), None)
        
        if active_subject:
            # Active Subject Header
            st.markdown("---")
            nc1, nc2 = st.columns([8, 2])
            new_name = nc1.text_input("현재 과목 이름", value=active_subject["name"], key=f"sname_{active_subject['id']}")
            if new_name != active_subject["name"]:
                active_subject["name"] = new_name
                sync_to_gsheets(st.session_state.subjects)
                st.rerun()

            total_sections = sum(len(ch.get("sections", [])) for ch in active_subject.get("chapters", []))
            completed_sections = sum(sum(1 for sec in ch.get("sections", []) if sec.get("completed")) for ch in active_subject.get("chapters", []))
            progress = int((completed_sections / total_sections) * 100) if total_sections > 0 else 0
            
            st.progress(progress / 100, text=f"🔥 전체 달성률: {progress}% ({completed_sections}/{total_sections} 항목 완료)")

            if st.button("➕ 새 챕터 추가"):
                active_subject.setdefault("chapters", []).append({
                    "id": int(time.time()*1000),
                    "title": "",
                    "expanded": True,
                    "sections": []
                })
                sync_to_gsheets(st.session_state.subjects)
                st.rerun()

            st.write("")
            
            # Chapters
            for ch_idx, chapter in enumerate(active_subject.get("chapters", [])):
                sections = chapter.get("sections", [])
                completed_count = sum(1 for s in sections if s.get("completed"))
                ch_title_display = chapter.get("title", "새 챕터")
                
                with st.expander(f"📁 {ch_title_display} ({completed_count}/{len(sections)})", expanded=True):
                    
                    tc1, tc2 = st.columns([9, 1])
                    new_ch_title = tc1.text_input("챕터 제목", value=chapter.get("title", ""), key=f"ch_title_{chapter['id']}", label_visibility="collapsed")
                    if new_ch_title != chapter.get("title", ""):
                        chapter["title"] = new_ch_title
                        sync_to_gsheets(st.session_state.subjects)
                        st.rerun()
                        
                    if tc2.button("🗑️", key=f"del_ch_{chapter['id']}", help="챕터 삭제"):
                        active_subject["chapters"].remove(chapter)
                        sync_to_gsheets(st.session_state.subjects)
                        st.rerun()

                    st.markdown("---")
                    
                    # Sections
                    for s_idx, section in enumerate(sections):
                        sc1, sc2, sc3, sc4, sc5 = st.columns([1, 4, 3, 1, 1])
                        
                        new_comp = sc1.checkbox("완료", value=section.get("completed", False), key=f"comp_{chapter['id']}_{section['id']}")
                        if new_comp != section.get("completed", False):
                            section["completed"] = new_comp
                            sync_to_gsheets(st.session_state.subjects)
                            st.rerun()
                            
                        sec_title = section.get("title", "")
                        new_sec_title = sc2.text_input("세부 항목", value=sec_title, key=f"stitle_{chapter['id']}_{section['id']}", label_visibility="collapsed", placeholder="세부 내용을 입력하세요")
                        if new_sec_title != sec_title:
                            section["title"] = new_sec_title
                            sync_to_gsheets(st.session_state.subjects)
                            st.rerun()
                            
                        new_date = sc3.date_input("날짜 선택", key=f"sdate_{chapter['id']}_{section['id']}", label_visibility="collapsed")
                        
                        if sc4.button("➕ 날짜", key=f"add_d_{chapter['id']}_{section['id']}", help="선택한 날짜 기록에 추가"):
                            d_str = str(new_date)
                            dates = section.get("dates", [])
                            if d_str not in dates:
                                section.setdefault("dates", []).append(d_str)
                                section["dates"].sort()
                                sync_to_gsheets(st.session_state.subjects)
                                st.rerun()
                                
                        if sc5.button("❌", key=f"del_s_{chapter['id']}_{section['id']}", help="세부 항목 삭제"):
                            chapter["sections"].remove(section)
                            sync_to_gsheets(st.session_state.subjects)
                            st.rerun()
                            
                        # Recorded Dates (Multiselect for viewing & deleting)
                        recorded_dates = section.get("dates", [])
                        if recorded_dates:
                            ms_dates = st.multiselect("기록된 날짜 (지우려면 X 클릭)", options=recorded_dates, default=recorded_dates, key=f"ms_dates_{chapter['id']}_{section['id']}", label_visibility="collapsed")
                            if set(ms_dates) != set(recorded_dates):
                                section["dates"] = sorted(ms_dates)
                                sync_to_gsheets(st.session_state.subjects)
                                st.rerun()
                        st.markdown("<br/>", unsafe_allow_html=True)
                    
                    if st.button("➕ 세부 항목 추가", key=f"add_sec_{chapter['id']}"):
                        chapter.setdefault("sections", []).append({
                            "id": int(time.time()*1000) + ch_idx,
                            "title": "",
                            "dates": [],
                            "completed": False
                        })
                        sync_to_gsheets(st.session_state.subjects)
                        st.rerun()

    except Exception as e:
        st.error(f"스프레드시트를 불러오는 중 오류가 발생했습니다: {e}\n\n시트 URL이 올바른지 확인해주세요!")
else:
    st.info("시작하려면 사용할 구글 스프레드시트의 주소가 필요합니다.")
    st.markdown("- **로컬 환경:** `streamlit_app.py` 파일 내의 `SHEET_URL` 변수에 주소를 직접 붙여넣으세요.")
    st.markdown("- **클라우드 환경:** Streamlit Cloud의 `Secrets` 설정에 `sheet_url = \"...\"` 을 추가하세요.")
    st.markdown("- (참고: 입력될 시트의 첫 번째 행은 컬럼명으로 자동 세팅됩니다.)")
