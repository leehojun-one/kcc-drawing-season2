import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import platform
import re
import io
import base64
import gspread  # 💡 구글 시트 연동용 패키지
from google.oauth2.service_account import Credentials  # 💡 구글 인증용 패키지
from datetime import datetime
import os
import urllib.request
import matplotlib.font_manager as fm

# ==========================================
# 1. 페이지 기본 설정 및 환경 세팅
# ==========================================
st.set_page_config(page_title="KCC홈씨씨 창호도면 자동화 시스템", layout="wide")

# 💡 [한글 깨짐 최종 해결] 리눅스 서버에서도 한글이 절대 깨지지 않도록 폰트 강제 주입 엔진 작동
if platform.system() == 'Windows':
    plt.rc('font', family='Malgun Gothic')
elif platform.system() == 'Darwin':
    plt.rc('font', family='AppleGothic')
else:
    # 스트림릿 클라우드(리눅스) 환경인 경우, 구글 공식 저장소에서 나눔고딕을 직접 다운로드하여 주입합니다.
    font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    font_path = "NanumGothic.ttf"
    
    if not os.path.exists(font_path):
        try:
            urllib.request.urlretrieve(font_url, font_path)
        except Exception as e:
            st.error(f"폰트 다운로드 실패: {e}")
            
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        font_name = fm.FontProperties(fname=font_path).get_name()
        plt.rc('font', family=font_name)
    else:
        plt.rc('font', family='sans-serif')

plt.rcParams['axes.unicode_minus'] = False 

HOMECC_SLOGAN = "공간에 가치를 더하는 프리미엄 창호, KCC글라스 홈씨씨창호"

# 💡 [디테일 4&5] 통바 배경은 더 연하게, 텍스트는 진한 맞춤 색상으로!
TONGBA_INFO = {
    "CB-101*100": {"thick": 100, "color": "#E0F2FE", "text_color": "#1E3A8A", "scale": 1.3}, 
    "CB-100*45": {"thick": 60, "color": "#FEF9C3", "text_color": "#991B1B", "scale": 1.5},   
    "CB-45*45": {"thick": 60, "color": "#DCFCE7", "text_color": "#14532D", "scale": 1.5},    
    "CB-135": {"thick": 60, "color": "#F3E8FF", "text_color": "#991B1B", "scale": 1.4}       
}

# ==========================================
# 🔒 구글 스프레드시트 보안/로그 연동 엔진
# ==========================================
def init_gsheet():
    """Streamlit Secrets에 저장된 구글 서비스 계정 키로 시트에 연결합니다."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds_info = st.secrets["gcp_service_account"]
        sheet_url = st.secrets["gsheet_url"]
        
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(sheet_url)
        return spreadsheet
    except Exception as e:
        st.error(f"🛑 구글 클라우드 보안 연동 실패! 시스템 관리자(이호준 팀장님)에게 문의하세요. 에러 내용: {e}")
        return None

def log_usage(partner_name, site_address, doc_count):
    """도면을 구울 때마다 누가 얼마나 썼는지 구글 시트에 기록합니다."""
    try:
        sheet = init_gsheet()
        if sheet:
            log_sheet = sheet.worksheet("Usage_Log")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_name = st.session_state.get("user_name", "알수없음")
            user_sabun = st.session_state.get("user_sabun", "알수없음")
            
            row_data = [now_str, user_name, user_sabun, partner_name, site_address, doc_count]
            log_sheet.append_row(row_data)
    except Exception as e:
        pass 

# 로그인 상태 초기화
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_name"] = ""
    st.session_state["user_sabun"] = ""

# 🛑 로그인 차단 벽 가동 (승인된 직원만 통과)
if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("🔐 KCC홈씨씨 창호도면 자동화 시스템 로그인")
        st.info("본 프로그램은 승인된 KCC글라스 임직원 및 파트너사만 이용 가능합니다.")
        
        input_sabun = st.text_input("🔑 사번(또는 승인번호)을 입력하세요", type="password")
        
        if st.button("🚀 시스템 접속하기", type="primary", use_container_width=True):
            if not input_sabun.strip():
                st.warning("사번을 입력해주세요.")
            else:
                with st.spinner("구글 보안 서버에서 권한을 검증 중입니다..."):
                    sheet = init_gsheet()
                    if sheet:
                        try:
                            user_sheet = sheet.worksheet("User_List")
                            records = user_sheet.get_all_records()
                            df_users = pd.DataFrame(records)
                            
                            df_users['사번'] = df_users['사번'].astype(str).str.strip()
                            target_user = df_users[df_users['사번'] == input_sabun.strip()]
                            
                            if not target_user.empty:
                                status = str(target_user.iloc[0].get('승인여부', 'X')).upper().strip()
                                name = target_user.iloc[0].get('이름', '사용자')
                                
                                if status == 'O':
                                    st.session_state["logged_in"] = True
                                    st.session_state["user_name"] = name
                                    st.session_state["user_sabun"] = input_sabun.strip()
                                    st.success(f"🎉 인증 성공! {name}님 환영합니다.")
                                    st.rerun()
                                else:
                                    st.error("🛑 승인 보류 계정입니다. 이호준 팀장님께 승인 활성화를 요청하세요.")
                            else:
                                st.error("❌ 등록되지 않은 사번입니다. 입력 정보를 다시 확인하세요.")
                        except Exception as e:
                            st.error(f"인증 데이터 읽기 실패: {e}")
    st.stop()

# ==========================================
# 2. 파싱 및 스마트 매칭 엔진
# ==========================================
def clean_kcc_name(name):
    return re.sub(r'^HW\s*ONE\s*(\(V\))?[_\s]*', '', str(name), flags=re.IGNORECASE).strip()

def get_tongba_style(model_str):
    t = str(model_str).upper().replace(" ", "")
    if 'CB-101*100' in t or 'CB101*100' in t: return TONGBA_INFO['CB-101*100']
    if 'CB-100*45' in t or 'CB100*45' in t: return TONGBA_INFO['CB-100*45']
    if 'CB-45*45' in t or 'CB45*45' in t: return TONGBA_INFO['CB-45*45']
    if 'CB-135' in t or 'CB135' in t or '각도' in t: return TONGBA_INFO['CB-135']
    return {"thick": 50, "color": "#F3F4F6", "text_color": "#374151", "scale": 1.3} 

def parse_tongba_input(t_str, default_len):
    if not t_str or str(t_str).strip() == "": return []
    items = []
    parts = str(t_str).split(',')
    
    for p in parts:
        p_raw = p.strip()
        if not p_raw: continue
        
        qty = 1
        t_len = default_len 
        base_name = p_raw
        
        match_qty = re.search(r'[xX*]\s*([0-9]+)$', base_name)
        if match_qty:
            qty = int(match_qty.group(1)) 
            base_name = base_name[:match_qty.start()].strip() 
            
        match_len = re.search(r'[\[\(]([0-9]+)[\]\)]', base_name)
        if match_len:
            t_len = int(match_len.group(1))
            base_name = base_name.replace(match_len.group(0), '').strip()
            
        clean_name = clean_kcc_name(base_name)
        style = get_tongba_style(p_raw)
        
        items.append({
            'name': clean_name, 
            'qty': qty, 
            'thick': style['thick'], 
            'color': style['color'], 
            'text_color': style['text_color'], 
            'scale': style['scale'],
            'len': t_len 
        })
    return items

def parse_any_quotation(file_buffer):
    df_raw = pd.read_excel(file_buffer, header=None)
    
    partner_name, site_address = "", ""
    for r_idx in range(min(15, len(df_raw))):
        row_vals = [str(x) for x in df_raw.iloc[r_idx].values if pd.notnull(x) and str(x).strip()]
        for i, val in enumerate(row_vals):
            if '공급받는자' in val or '파트너' in val: partner_name = row_vals[i+1] if i+1 < len(row_vals) else ""
            if '현장주소' in val or '현장명' in val: site_address = row_vals[i+1] if i+1 < len(row_vals) else ""

    header_idx = df_raw[df_raw.isin(['설치위치']).any(axis=1)].index[0]
    df = df_raw.iloc[header_idx+1:].copy()
    df.columns = [str(c).replace('\n', '').replace(' ', '') for c in df_raw.iloc[header_idx]]
    df = df[pd.to_numeric(df['순번'], errors='coerce').notnull()]
    
    windows_for_drawing = []
    tongba_bom = []
    all_tongbas = []
    
    for _, row in df.iterrows():
        prod_orig = clean_kcc_name(str(row.get('제품명', '')).strip())
        if '기타견적' in prod_orig.replace(" ", ""): continue
            
        loc = str(row.get('설치위치', '')).strip() if pd.notnull(row.get('설치위치')) else ""
        model_orig = clean_kcc_name(str(row.get('모델명', '')).strip())
        w_shape_orig = str(row.get('창형태', '')).strip()
        
        is_independent = '통바ㅁ' in w_shape_orig.replace(" ","") or '통바ㄷ' in w_shape_orig.replace(" ","")
        is_supplementary_tongba = not is_independent and ('CB-' in model_orig.upper() or '각도바' in model_orig)
        
        w_val_raw = pd.to_numeric(row.get('길이(W)'), errors='coerce')
        w_val = int(w_val_raw) if pd.notnull(w_val_raw) else 0
        
        h_val_raw = pd.to_numeric(row.get('높이(H)'), errors='coerce')
        h_val = int(h_val_raw) if pd.notnull(h_val_raw) else 0
        
        qty_raw = pd.to_numeric(row.get('수량'), errors='coerce')
        qty = int(qty_raw) if pd.notnull(qty_raw) and qty_raw > 0 else 1
        
        if is_supplementary_tongba:
            length = max(w_val, h_val)
            zajae_name = model_orig if model_orig else prod_orig
            tongba_bom.append({'위치': loc, '자재명': zajae_name, '길이': length, '수량': qty})
            for _ in range(qty): 
                all_tongbas.append({'loc': loc, 'code': zajae_name, 'len': length, 'used': False})

    for seq, group in df.groupby('순번'):
        main_row = group.iloc[0]
        prod_orig = clean_kcc_name(str(main_row.get('제품명', '')))
        if '기타견적' in prod_orig.replace(" ", ""): continue
            
        seq_num = int(pd.to_numeric(main_row.get('순번'), errors='coerce'))
        loc = str(main_row.get('설치위치', '')).strip() if pd.notnull(main_row.get('설치위치')) else ""
        model_name = clean_kcc_name(str(main_row.get('모델명', '')).strip())
        w_shape_orig = str(main_row.get('창형태', ''))
        
        # 💡 [버그 완치 부위] 날짜 및 최종계산일 행을 완전히 스킵하고 오직 순수 유리 사양 셀만 정밀 타격하는 보안 필터
        def clean_glass_val(val):
            val_str = str(val).strip()
            if val_str in ['nan', 'None', 'X', '0', '-', '', '디폴트']:
                return ""
            if re.match(r'^\d{4}[.\-/]\d{2}[.\-/]\d{2}', val_str) or '최종계산일' in val_str:
                return ""
            return val_str
                
        # 팀장님 설명대로 이중창은 1번째 행(내부)과 2번째 행(외부)의 셀 텍스트를 정확히 낚아챕니다.
        glass_list = []
        if len(group) >= 1:
            g1 = clean_glass_val(group.iloc[0].get('내부유리종류', ''))
            if g1: glass_list.append(g1)
        if len(group) >= 2:
            loc_val2 = str(group.iloc[1].get('설치위치', '')).strip()
            if '비고' not in loc_val2:  # 비고 행 오염 방지
                g2 = clean_glass_val(group.iloc[1].get('내부유리종류', ''))
                if g2: glass_list.append(g2)
        
        glass_in = glass_list[0] if len(glass_list) > 0 else ""
        glass_out = glass_list[1] if len(glass_list) > 1 else ""
        
        is_independent = '통바ㅁ' in w_shape_orig.replace(" ","") or '통바ㄷ' in w_shape_orig.replace(" ","")
        is_supplementary_tongba = not is_independent and ('CB-' in model_name.upper() or '각도바' in model_name)
        if is_supplementary_tongba: continue
        
        w_val_raw = pd.to_numeric(main_row.get('길이(W)'), errors='coerce')
        w_val = int(w_val_raw) if pd.notnull(w_val_raw) else 0
        
        h_val_raw = pd.to_numeric(main_row.get('높이(H)'), errors='coerce')
        h_val = int(h_val_raw) if pd.notnull(h_val_raw) else 0
        
        w1_val = 0
        if len(group) >= 2:
            w1_raw = pd.to_numeric(group.iloc[1].get('길이(W)'), errors='coerce')
            if pd.notnull(w1_raw) and w1_raw > 0:
                w1_val = int(w1_raw)
        
        handle_height = ""
        if len(group) >= 3:
            for val in group.iloc[2].values:
                try:
                    num = float(val)
                    if 100 <= num <= 3000: handle_height = int(num); break
                except: pass

        vent_dir = str(group.iloc[1].get('창형태')).strip() if len(group) >= 2 and pd.notnull(group.iloc[1].get('창형태')) else ""
        has_screen = True if pd.notnull(main_row.get('방충망')) and str(main_row.get('방충망')).strip().upper() not in ['', 'X', 'NONE', '0'] else False

        auto_t_top, auto_t_bot, auto_t_left, auto_t_right = [], [], [], []
        
        def find_one_matching_bar(target_len, target_loc):
            for t in all_tongbas:
                if not t.get('used', False) and t.get('len') == target_len and target_loc and t.get('loc') == target_loc:
                    t['used'] = True; return f"{t.get('code')}({t.get('len')})"
            for t in all_tongbas:
                if not t.get('used', False) and t.get('len') == target_len and not t.get('loc'):
                    t['used'] = True; return f"{t.get('code')}({t.get('len')})"
            for t in all_tongbas:
                if not t.get('used', False) and t.get('len') == target_len:
                    t['used'] = True; return f"{t.get('code')}({t.get('len')})"
            return None

        if not is_independent:
            m1 = find_one_matching_bar(w_val, loc)
            if m1: auto_t_top.append(m1)
            
            m2 = find_one_matching_bar(w_val, loc)
            if m2: auto_t_bot.append(m2) 
            
            m3 = find_one_matching_bar(h_val, loc)
            if m3: auto_t_left.append(m3)
            
            m4 = find_one_matching_bar(h_val, loc)
            if m4: auto_t_right.append(m4) 

        windows_for_drawing.append({
            '순번': seq_num, '위치': loc, '제품명': prod_orig, '모델명': model_name, '형태': w_shape_orig, 
            'glass_in': glass_in, 'glass_out': glass_out,
            '가로(W)': w_val, '세로(H)': h_val, 'w1': w1_val, '핸들높이': handle_height, 'vent_dir': vent_dir, 'has_screen': has_screen,
            'auto_top': ",".join(auto_t_top), 'auto_bot': ",".join(auto_t_bot),
            'auto_left': ",".join(auto_t_left), 'auto_right': ",".join(auto_t_right)
        })
        
    windows_for_drawing.sort(key=lambda x: x['순번'])
    
    unused_tongbas = [f"{t.get('code')}({t.get('len')})" for t in all_tongbas if not t.get('used', False)]
    
    overall_max_w, overall_max_h = 2500, 2500 
    if windows_for_drawing:
        overall_max_w = max(max(win['가로(W)'] for win in windows_for_drawing), 2500)
        overall_max_h = max(max(win['세로(H)'] for win in windows_for_drawing), 2500)
            
    return windows_for_drawing, tongba_bom, unused_tongbas, (overall_max_w, overall_max_h), partner_name, site_address

# ==========================================
# 3. 렌더링 엔진
# ==========================================
def render_window_on_ax(ax, seq, w, h, w1, win_type, loc, product, model_name, glass_in, glass_out, handle_h, vent_dir, has_screen, t_top_str, t_bot_str, t_left_str, t_right_str, scale_bounds):
    
    overall_max_w, overall_max_h = scale_bounds
    t_upper = str(win_type).upper().replace(" ", "")
    glass_combined = str(glass_in) + str(glass_out)
    
    mist_color, mist_alpha, mist_hatch = '#BAE6FD', 0.5, '....'
    txt_bbox = dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.85)
    
    TEXT_SIZE = 4.0

    is_left_vent = "좌" in vent_dir
    is_right_vent = "우" in vent_dir
    
    splits = []
    is_turning = "우핸들좌힌지" in (t_upper + str(vent_dir) + str(product).replace(" ", "")) or "좌핸들우힌지" in (t_upper + str(vent_dir) + str(product).replace(" ", ""))

    if '통바ㅁ' not in t_upper and '통바ㄷ' not in t_upper and not is_turning:
        if "2W" in t_upper:
            if w1 > 0:  
                splits = [w1] if is_left_vent else [w - w1]
            else:
                if "1:2" in t_upper:
                    if is_right_vent and not is_left_vent:
                        splits = [w * 2 / 3]  
                    else:
                        splits = [w / 3]      
                else:
                    splits = [w / 2]
                
        elif "3W" in t_upper:
            if w1 > 0:
                splits = [w1, w - w1] 
            else:
                splits = [w / 4, w - w / 4] 
                
        elif "4W" in t_upper:
            splits = [w / 4, 2 * w / 4, 3 * w / 4]

    if "미스트" in glass_combined:
        if not splits:
            ax.add_patch(patches.Rectangle((0, 0), w, h, facecolor=mist_color, hatch=mist_hatch, edgecolor='none', alpha=mist_alpha))
        else:
            prev_x = 0
            for sp in splits:
                ax.add_patch(patches.Rectangle((prev_x, 0), sp - prev_x, h, facecolor=mist_color, hatch=mist_hatch, edgecolor='none', alpha=mist_alpha))
                prev_x = sp
            ax.add_patch(patches.Rectangle((prev_x, 0), w - prev_x, h, facecolor=mist_color, hatch=mist_hatch, edgecolor='none', alpha=mist_alpha))

    if '통바ㄷ' in t_upper:
        ax.plot([0, 0, w, w], [0, h, h, 0], color='black', linewidth=1.2)
    else:
        rect = patches.Rectangle((0, 0), w, h, linewidth=1.0, edgecolor='black', facecolor='none')
        ax.add_patch(rect)

    if '통바ㅁ' not in t_upper and '통바ㄷ' not in t_upper:
        door_info_raw = str(win_type) + str(vent_dir) + str(product)
        door_info = door_info_raw.replace(" ", "")
        
        if "우핸들좌힌지" in door_info:
            hy = handle_h if handle_h else h/2
            ax.plot([w, 0, w], [h, hy, 0], color='#9CA3AF', linestyle='--', linewidth=1.0, alpha=0.8)
            ax.add_patch(patches.Rectangle((w - 80, hy - 120), 40, 240, facecolor='#6B7280', edgecolor='black', zorder=3))
            d_txt = "미는문 / 우핸들좌힌지" if "미는문" in door_info else ("당기는문 / 우핸들좌힌지" if "당기는문" in door_info else "우핸들좌힌지")
            ax.text(w/2, h * 0.33, d_txt, ha='center', va='center', color='black', fontsize=11, fontweight='bold', bbox=txt_bbox)
            
        elif "좌핸들우힌지" in door_info:
            hy = handle_h if handle_h else h/2
            ax.plot([0, w, 0], [h, hy, 0], color='#9CA3AF', linestyle='--', linewidth=1.0, alpha=0.8)
            ax.add_patch(patches.Rectangle((40, hy - 120), 40, 240, facecolor='#6B7280', edgecolor='black', zorder=3))
            d_txt = "미는문 / 좌핸들우힌지" if "미는문" in door_info else ("당기는문 / 좌핸들우힌지" if "당기는문" in door_info else "좌핸들우힌지")
            ax.text(w/2, h * 0.33, d_txt, ha='center', va='center', color='black', fontsize=11, fontweight='bold', bbox=txt_bbox)
            
        else:
            for sp in splits:
                ax.plot([sp, sp], [0, h], color='black', linewidth=0.8)
                
            if "2W" in t_upper:
                sw = splits[0]
                _is_left, _is_right = is_left_vent, is_right_vent
                if not _is_left and not _is_right: _is_right = True 
                
                if _is_left:
                    ax.text(sw/2, h/2, "▶ 좌", ha='center', va='center', fontsize=11, fontweight='bold', bbox=txt_bbox)
                    if w1 > 0: ax.text(sw/2, h/2 - 200, f"{w1}", ha='center', va='center', fontsize=12, fontweight='bold', color='red')
                    # 💡 [보존] 팀장님 전용 최적 간격 수치인 +250 영구 박제!
                    if has_screen: ax.text(sw/2, h/2 + 250, "#(망)", ha='center', va='center', fontsize=11, fontweight='bold', color='red', bbox=txt_bbox)
                
                if _is_right:
                    ax.text(sw + (w-sw)/2, h/2, "◀ 우", ha='center', va='center', fontsize=11, fontweight='bold', bbox=txt_bbox)
                    if w1 > 0: ax.text(sw + (w-sw)/2, h/2 - 200, f"{w1}", ha='center', va='center', fontsize=12, fontweight='bold', color='red')
                    # 💡 [보존] 팀장님 전용 최적 간격 수치인 +250 영구 박제!
                    if has_screen: ax.text(sw + (w-sw)/2, h/2 + 250, "#(망)", ha='center', va='center', fontsize=11, fontweight='bold', color='red', bbox=txt_bbox)
                    
            elif "3W" in t_upper:
                ax.text((splits[0] + splits[1])/2, h/2, t_upper, ha='center', va='center', color='black', fontsize=10, fontweight='bold', bbox=txt_bbox)
                
                _is_left, _is_right = is_left_vent, is_right_vent
                if not _is_left and not _is_right: _is_left, _is_right = True, True
                
                if _is_left:
                    ax.text(splits[0]/2, h/2, "▶", ha='center', va='center', fontsize=11, fontweight='bold', bbox=txt_bbox)
                    if w1 > 0: ax.text(splits[0]/2, h/2 - 200, f"{w1}", ha='center', va='center', fontsize=12, fontweight='bold', color='red')
                    if has_screen: ax.text(splits[0]/2, h/2 + 250, "#(망)", ha='center', va='center', fontsize=11, fontweight='bold', color='red', bbox=txt_bbox)
                if _is_right:
                    ax.text(splits[1] + (w-splits[1])/2, h/2, "◀", ha='center', va='center', fontsize=11, fontweight='bold', bbox=txt_bbox)
                    if w1 > 0: ax.text(splits[1] + (w-splits[1])/2, h/2 - 200, f"{w1}", ha='center', va='center', fontsize=12, fontweight='bold', color='red')
                    if has_screen: ax.text(splits[1] + (w-splits[1])/2, h/2 + 250, "#(망)", ha='center', va='center', fontsize=11, fontweight='bold', color='red', bbox=txt_bbox)

        if handle_h and not ("핸들" in door_info and "힌지" in door_info):
            ax.plot([0, w], [handle_h, handle_h], color='red', linestyle='--', linewidth=0.8, alpha=0.6)
            ax.text(w + 50, handle_h, f"핸들: {handle_h}", color='red', va='center', fontweight='bold', fontsize=9, bbox=txt_bbox)

    if "미스트" in glass_combined:
        ax.text(w/2, h * 0.8, "미스트", ha='center', va='center', color='red', fontsize=11, fontweight='bold', bbox=txt_bbox)
    
    if re.search(r'고정창', product, re.IGNORECASE) or "FIX" in t_upper:
        ax.text(w/2, h/2, "Fix", ha='center', va='center', fontsize=16, fontweight='bold', color='black')

    t_top_list = parse_tongba_input(t_top_str, w)
    t_bot_list = parse_tongba_input(t_bot_str, w)
    t_left_list = parse_tongba_input(t_left_str, h)
    t_right_list = parse_tongba_input(t_right_str, h)

    # 상부 통바
    current_y = h
    for t in t_top_list:
        thick_v = t['thick'] * t['scale'] 
        t_len = t['len']
        start_x = (w - t_len) / 2 
        ax.add_patch(patches.Rectangle((start_x, current_y), t_len, thick_v, facecolor=t['color'], edgecolor='black', linewidth=1.0))
        
        full_text = f"{t['name']} ({t['len']})" + (f" X{t['qty']}" if t['qty'] > 1 else "")
        ax.text(w/2, current_y + thick_v/2, full_text, ha='center', va='center', fontsize=TEXT_SIZE, color=t['text_color'], fontweight='bold', stretch='condensed')
        current_y += thick_v

    # 하부 통바
    current_y = 0
    for t in t_bot_list:
        thick_v = t['thick'] * t['scale']
        current_y -= thick_v
        t_len = t['len']
        start_x = (w - t_len) / 2 
        ax.add_patch(patches.Rectangle((start_x, current_y), t_len, thick_v, facecolor=t['color'], edgecolor='black', linewidth=1.0))
        
        full_text = f"{t['name']} ({t['len']})" + (f" X{t['qty']}" if t['qty'] > 1 else "")
        ax.text(w/2, current_y + thick_v/2, full_text, ha='center', va='center', fontsize=TEXT_SIZE, color=t['text_color'], fontweight='bold', stretch='condensed')

    # 좌측 통바
    current_x = 0
    for t in t_left_list:
        thick_v = t['thick'] * t['scale']
        current_x -= thick_v
        t_len = t['len']
        start_y = 0 
        ax.add_patch(patches.Rectangle((current_x, start_y), thick_v, t_len, facecolor=t['color'], edgecolor='black', linewidth=1.0))
        
        full_text = f"{t['name']} ({t['len']})" + (f" X{t['qty']}" if t['qty'] > 1 else "")
        ax.text(current_x + thick_v/2, start_y + t_len/2, full_text, ha='center', va='center', rotation=90, fontsize=TEXT_SIZE, color=t['text_color'], fontweight='bold', stretch='condensed')
    
    left_idx_x = current_x / 2 if t_left_list else -100

    # 우측 통바
    current_x = w
    for t in t_right_list:
        thick_v = t['thick'] * t['scale']
        t_len = t['len']
        start_y = 0 
        ax.add_patch(patches.Rectangle((current_x, start_y), thick_v, t_len, facecolor=t['color'], edgecolor='black', linewidth=1.0))
        
        full_text = f"{t['name']} ({t['len']})" + (f" X{t['qty']}" if t['qty'] > 1 else "")
        ax.text(current_x + thick_v/2, start_y + t_len/2, full_text, ha='center', va='center', rotation=90, fontsize=TEXT_SIZE, color=t['text_color'], fontweight='bold', stretch='condensed')
        current_x += thick_v
    
    right_idx_x = (w + current_x) / 2 if t_right_list else w + 100

    # 💡 [레이아웃 완전 복원 부위] 인위적인 분할을 걷어내고, 오리지널의 무결점 정렬 엔진으로 회귀했습니다!
    display_name = model_name if model_name else product
    
    # 1. 상단 메인 헤더: 순번, 설치위치, 모델명 / 창형태 통합 렌더링 (\n 단일 블록으로 자간 왜곡 100% 진압)
    top_title_text = f"[{seq}] {loc}\n{display_name} / {win_type}"
    ax.text(w/2, h + 350, top_title_text, ha='center', va='bottom', fontsize=11, fontweight='bold', linespacing=1.3)
    
    # 2. 유리사양 문자열 스마트 빌드 (이중창은 중간에 '/' 삽입, 단창은 한 줄 출력, 접두사 전면 삭제)
    if glass_in and glass_out:
        glass_text = f"{glass_in} / {glass_out}"
    elif glass_in:
        glass_text = glass_in
    elif glass_out:
        glass_text = glass_out
    else:
        glass_text = ""
        
    # 3. 하단 유리 헤더: 핵심 키워드 유무에 따라 라인 통채색 처리 (자간 왜곡 원천 차단형 컬러링 기술)
    if glass_text:
        glass_color = 'black'
        if '미스트' in glass_text:
            glass_color = '#DC2626'  # ❤️ 미스트 단어가 식별되면 라인 전체를 빨간색으로!
        elif '로이' in glass_text or '컬러로이' in glass_text or '더블로이' in glass_text:
            glass_color = '#1D4ED8'  # 💙 로이 시리즈 단어가 식별되면 라인 전체를 파란색으로!
            
        ax.text(w/2, h + 150, glass_text, ha='center', va='bottom', fontsize=9, fontweight='bold', color=glass_color)
    
    total_bot_offset = sum(t['thick'] * t['scale'] for t in t_bot_list)
    ax.text(w/2, -260 - total_bot_offset, f"{w} x {h}", ha='center', va='top', fontsize=11, fontweight='bold', color='#1E3A8A')
    
    left_stacked_texts = [f"X{t['qty']}" for t in t_left_list if t['qty'] > 1]
    right_stacked_texts = [f"X{t['qty']}" for t in t_right_list if t['qty'] > 1]
    
    if left_stacked_texts:
        left_txt = "\n".join(left_stacked_texts)
        ax.text(left_idx_x, -30 - total_bot_offset, left_txt, ha='center', va='top', fontsize=8, fontweight='bold', color='red', bbox=txt_bbox)
        
    if right_stacked_texts:
        right_txt = "\n".join(right_stacked_texts)
        ax.text(right_idx_x, -30 - total_bot_offset, right_txt, ha='center', va='top', fontsize=8, fontweight='bold', color='red', bbox=txt_bbox)
    
    MARGIN_X = 400  
    MARGIN_Y_TOP = 450 
    MARGIN_Y_BOT = 550  
    
    VIEW_W = overall_max_w + (MARGIN_X * 2)
    VIEW_H = overall_max_h + MARGIN_Y_TOP + MARGIN_Y_BOT
    
    ZOOM_OUT = 1.0 
    
    VIEW_W = VIEW_W * ZOOM_OUT
    VIEW_H = VIEW_H * ZOOM_OUT
    
    x_center = w / 2
    
    y_max_view = h + MARGIN_Y_TOP 
    y_min_view = y_max_view - VIEW_H
    
    ax.set_xlim(x_center - VIEW_W / 2, x_center + VIEW_W / 2)
    ax.set_ylim(y_min_view, y_max_view) 
    ax.set_aspect('equal', anchor='C') 
    ax.axis('off')

# ==========================================
# 4. 출력 엔진 
# ==========================================
def generate_a3_pdf_and_images(draw_data, p_name, s_addr, scale_bounds):
    pdf_buf = io.BytesIO()
    img_bufs = []
    
    with PdfPages(pdf_buf) as pdf:
        chunks = [draw_data[i:i + 12] for i in range(0, len(draw_data), 12)]
        
        for page_num, chunk in enumerate(chunks):
            fig, axes = plt.subplots(nrows=3, ncols=4, figsize=(16.53, 11.69))
            
            fig.patches.extend([patches.Rectangle((0.015, 0.02), 0.97, 0.96, fill=False, color='#1E293B', lw=2.5, transform=fig.transFigure, figure=fig)])
            fig.patches.extend([patches.Rectangle((0.015, 0.92), 0.97, 0.06, fill=True, color='#F8FAFC', ec='#1E293B', lw=2.5, transform=fig.transFigure, figure=fig)])
            
            author_name = st.session_state.get("user_name", "")
            fig.text(0.5, 0.95, f"🏢 파트너: {p_name}      |      📍 현장: {s_addr}      |      ✍️ 작성자: {author_name}", ha='center', va='center', fontsize=16, fontweight='bold', color='#0F172A')
            
            axes_flat = axes.flatten()
            for idx, ax in enumerate(axes_flat):
                if idx < len(chunk):
                    win = chunk[idx]
                    render_window_on_ax(
                        ax, win['순번'], win['가로(W)'], win['세로(H)'], win['w1'], win['형태'], win['위치'],
                        win['제품명'], win['모델명'], win['glass_in'], win['glass_out'], win.get('핸들높이'), win['vent_dir'], win['has_screen'],
                        win['auto_top'], win['auto_bot'], win['auto_left'], win['auto_right'],
                        scale_bounds
                    )
                else:
                    ax.axis('off') 
            
            footer_text = f"💡 {HOMECC_SLOGAN}   (Page {page_num+1}/{len(chunks)})"
            fig.text(0.5, 0.035, footer_text, ha='center', fontsize=13, color='#1E3A8A', fontweight='bold')
            
            fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.05, wspace=0.05, hspace=0.25)
            
            pdf.savefig(fig)
            
            img_buf = io.BytesIO()
            fig.savefig(img_buf, format='png', dpi=600, bbox_inches='tight')
            img_bufs.append(img_buf.getvalue())
            
            plt.close(fig)
            
    return pdf_buf.getvalue(), img_bufs

# ==========================================
# 5. UI 및 상태 관리
# ==========================================
def set_status_editing(uid): st.session_state[f"status_{uid}"] = "editing"
def confirm_auto(uid): st.session_state[f"status_{uid}"] = "confirmed"
def save_edits(uid):
    st.session_state[f"saved_top_{uid}"] = st.session_state.get(f"in_top_{uid}", "")
    st.session_state[f"saved_bot_{uid}"] = st.session_state.get(f"in_bot_{uid}", "")
    st.session_state[f"saved_left_{uid}"] = st.session_state.get(f"in_left_{uid}", "")
    st.session_state[f"saved_right_{uid}"] = st.session_state.get(f"in_right_{uid}", "")
    st.session_state[f"status_{uid}"] = "confirmed"

st.title(f"🪟 KCC홈씨씨 창호도면 자동화 시스템 (사용자: {st.session_state.get('user_name', '')})")

if st.button("🔄 시스템 초기화 (새로고침)", type="primary", use_container_width=True):
    for key in list(st.session_state.keys()):
        if key not in ["logged_in", "user_name", "user_sabun"]:
            del st.session_state[key]
    st.rerun()

uploaded_file = st.file_uploader("📂 견적서 엑셀 파일 업로드", type=['xlsx', 'xls'])

if uploaded_file:
    if "last_file_id" not in st.session_state or st.session_state["last_file_id"] != uploaded_file.file_id:
        for key in list(st.session_state.keys()):
            if key.startswith("saved_") or key.startswith("status_"):
                del st.session_state[key]
        st.session_state["last_file_id"] = uploaded_file.file_id
        
    draw_data, tongba_bom, unused_tongbas, overall_scale_bounds, ext_partner, ext_address = parse_any_quotation(uploaded_file)
    
    tab1, tab2 = st.tabs(["💻 1단계: 도면 작업대", "🖨️ 2단계: 출력 및 카톡 전송 센터"])
    
    with tab1:
        col_main, col_side = st.columns([8.5, 1.5])
        
        with col_side:
            st.markdown("#### 📦 발주 통바 내역")
            if tongba_bom: 
                st.dataframe(pd.DataFrame(tongba_bom)[['자재명', '길이', '수량']], hide_index=True, use_container_width=True)
                
                total_bom_qty = sum(item['수량'] for item in tongba_bom)
                total_used_qty = 0
                
                for uid in range(len(draw_data)):
                    t_top = st.session_state.get(f"saved_top_{uid}", draw_data[uid]['auto_top'])
                    t_bot = st.session_state.get(f"saved_bot_{uid}", draw_data[uid]['auto_bot'])
                    t_left = st.session_state.get(f"saved_left_{uid}", draw_data[uid]['auto_left'])
                    t_right = st.session_state.get(f"saved_right_{uid}", draw_data[uid]['auto_right'])
                    
                    for t_str in [t_top, t_bot, t_left, t_right]:
                        items = parse_tongba_input(t_str, 0) 
                        for item in items:
                            total_used_qty += item['qty']
                
                st.divider()
                st.markdown("#### 📊 수량 검증 알람")
                if total_bom_qty == total_used_qty:
                    st.success(f"✅ 완벽 일치!\n(발주 {total_bom_qty}개 = 도면 {total_used_qty}개)")
                else:
                    st.error(f"🚨 불일치!\n발주내역: {total_bom_qty}개\n도면적용: {total_used_qty}개")
            else: 
                st.info("통바 내역 없음")
            
            st.divider()
            st.markdown("#### 📊 미배정 대기소")
            if unused_tongbas:
                st.warning("사이즈가 달라 배정되지 못한 통바입니다.")
                for t in unused_tongbas:
                    st.code(t)
            else:
                st.success("모든 통바가 도면에 완벽하게 1차 매칭되었습니다! 🎉")
                
        with col_main:
            st.subheader("🤖 프리미엄 카탈로그 뷰: 통바 편집 및 확인")
            
            for i in range(0, len(draw_data), 3):
                cols = st.columns(3) 
                
                for j in range(3):
                    if i + j < len(draw_data):
                        win = draw_data[i+j]
                        seq = win['순번']
                        uid = i + j 
                        
                        if f"saved_top_{uid}" not in st.session_state:
                            st.session_state[f"saved_top_{uid}"] = win['auto_top']
                            st.session_state[f"saved_bot_{uid}"] = win['auto_bot']
                            st.session_state[f"saved_left_{uid}"] = win['auto_left']
                            st.session_state[f"saved_right_{uid}"] = win['auto_right']
                        
                        with cols[j]: 
                            st.markdown(f"**[{seq}] {win['위치']}**")
                            status = st.session_state.get(f"status_{uid}", "pending")
                            
                            curr_top = st.session_state[f"saved_top_{uid}"]
                            curr_bot = st.session_state[f"saved_bot_{uid}"]
                            curr_left = st.session_state[f"saved_left_{uid}"]
                            curr_right = st.session_state[f"saved_right_{uid}"]
                                
                            fig, ax = plt.subplots(figsize=(5.5, 5.5))
                            
                            render_window_on_ax(
                                ax, seq, win['가로(W)'], win['세로(H)'], win['w1'], win['형태'], win['위치'],
                                win['제품명'], win['모델명'], win['glass_in'], win['glass_out'], win.get('핸들높이'), win['vent_dir'], win['has_screen'],
                                curr_top, curr_bot, curr_left, curr_right, overall_scale_bounds 
                            )
                            
                            fig.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.05)
                            st.pyplot(fig, use_container_width=True)
                            plt.close(fig) 
                            
                            if status == "pending":
                                c1, c2 = st.columns(2)
                                c1.button("✅ 확정", key=f"ok_{uid}", on_click=confirm_auto, args=(uid,), type="primary")
                                c2.button("✏️ 수정", key=f"edit_{uid}", on_click=set_status_editing, args=(uid,))
                            elif status == "confirmed":
                                st.success("✅ 배치 확정됨")
                                st.button("🔄 다시 수정", key=f"re_edit_{uid}", on_click=set_status_editing, args=(uid,))
                            elif status == "editing":
                                st.text_input("상부", value=curr_top, key=f"in_top_{uid}")
                                st.text_input("하부", value=curr_bot, key=f"in_bot_{uid}")
                                st.text_input("좌측", value=curr_left, key=f"in_left_{uid}")
                                st.text_input("우측", value=curr_right, key=f"in_right_{uid}")
                                st.button("💾 저장", key=f"save_{uid}", on_click=save_edits, args=(uid,), type="primary")
                                
                            st.divider()

    with tab2:
        st.subheader("🖨️ A3 출력 및 카톡 전송 센터")
        st.info("사무실 출력용(PDF) 파일과 현장 카톡 전송용 이미지를 추출합니다.")
        
        c1, c2 = st.columns([1, 1])
        with c1: partner_input = st.text_input("🏢 파트너명 (도면 헤더용)", value=ext_partner)
        with c2: address_input = st.text_input("📍 현장주소 (도면 헤더용)", value=ext_address)
        
        if st.button("📄 도면 굽기 (출력용 PDF & 카톡용 이미지 추출)", type="primary", use_container_width=True):
            with st.spinner("도면 생성 중..."):
                final_draw_data = []
                for uid, win in enumerate(draw_data):
                    win_copy = win.copy()
                    win_copy['auto_top'] = st.session_state.get(f"saved_top_{uid}", win['auto_top'])
                    win_copy['auto_bot'] = st.session_state.get(f"saved_bot_{uid}", win['auto_bot'])
                    win_copy['auto_left'] = st.session_state.get(f"saved_left_{uid}", win['auto_left'])
                    win_copy['auto_right'] = st.session_state.get(f"saved_right_{uid}", win['auto_right'])
                    final_draw_data.append(win_copy)
                
                pdf_bytes, img_bytes_list = generate_a3_pdf_and_images(final_draw_data, partner_input, address_input, overall_scale_bounds)
                log_usage(partner_input, address_input, len(final_draw_data))
                
                st.success("🎉 도면 생성 완료! 사용 로그가 성공적으로 기록되었습니다.")
                
                st.download_button(
                    label="📥 A3 도면 PDF 다운로드 (사무실 출력용)",
                    data=pdf_bytes,
                    file_name="KCC홈씨씨_현장도면_A3_마스터출력.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                
                st.divider()
                st.markdown("### 📱 카카오톡 전송용 이미지 갤러리")
                
                for idx, img_bytes in enumerate(img_bytes_list):
                    st.markdown(f"#### 📄 도면 페이지 {idx + 1}")
                    st.image(img_bytes, use_column_width=True, caption=f"페이지 {idx + 1} 미리보기")
                    
                    st.download_button(
                        label=f"📥 페이지 {idx + 1} 초고화질 이미지 저장 (.png)",
                        data=img_bytes,
                        file_name=f"도면_카톡전송용_페이지_{idx+1}_8K.png",
                        mime="image/png",
                        key=f"dl_img_{idx}"
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
