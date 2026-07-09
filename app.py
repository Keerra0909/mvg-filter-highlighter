import os
import io
import re
import pandas as pd
import fitz  # PyMuPDF
from flask import Flask, request, send_file, render_template, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def extract_rooms_from_excel(excel_path, target_lobby=None):
    try:
        dfs = pd.read_excel(excel_path, header=None, sheet_name=None)
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return {}, []
    
    room_data = {}
    seen_rooms = set()
    duplicate_rooms = set()
    
    for sheet_name, df in dfs.items():
        if target_lobby:
            t_lobby = target_lobby.lower()
            s_name = sheet_name.lower()
            if t_lobby == 'grand' and 'grand' not in s_name and 'zmgr' not in s_name:
                continue
            if t_lobby == 'sunrise' and 'sunrise' not in s_name and 'zmsu' not in s_name:
                continue
            if t_lobby == 'nizuc' and 'nizuc' not in s_name and 'zmni' not in s_name:
                continue
                
        print(f"Processing sheet: {sheet_name}")
        # 1. Search the first 20 rows to find the actual header row and Room column
        header_row_idx = None
        room_col_idx = None
        attendance_col_idx = None
        reason_col_idx = None
        last_name_col_idx = None
        first_name_col_idx = None
        full_name_col_idx = None
        
        for idx, row in df.head(20).iterrows():
            for col_idx, val in row.items():
                val_str = str(val).lower()
                if 'roomnum' in val_str or 'room' in val_str:
                    room_col_idx = col_idx
                if 'attendance' in val_str or 'presentation' in val_str:
                    attendance_col_idx = col_idx
                if 'reason' in val_str:
                    reason_col_idx = col_idx
                if 'lasname' in val_str or 'lastname' in val_str:
                    last_name_col_idx = col_idx
                if 'firstname' in val_str:
                    first_name_col_idx = col_idx
                if 'full name' in val_str or 'fullname' in val_str:
                    full_name_col_idx = col_idx
                    
            if room_col_idx is not None:
                header_row_idx = idx
                break
                
        if room_col_idx is not None:
            print(f"Found room col: {room_col_idx}, attendance col: {attendance_col_idx}, reason col: {reason_col_idx} starting from row {header_row_idx + 1}")
            # Extract values starting from the row after the header
            for idx_row in range(header_row_idx + 1, len(df)):
                val = df.iloc[idx_row, room_col_idx]
                if pd.isna(val):
                    continue
                try:
                    val_str = str(val).strip()
                    if val_str.endswith('.0'):
                        val_str = val_str[:-2]
                    val_str = val_str.replace(',', '')
                    
                    if val_str.isdigit() and len(val_str) >= 3:
                        needs_underline = False
                        has_certificado = False
                        has_promo = False
                        has_mvg = False
                        
                        if attendance_col_idx is not None:
                            att_val = df.iloc[idx_row, attendance_col_idx]
                            if pd.notna(att_val) and str(att_val).strip().lower() == 'yes':
                                needs_underline = True
                                
                        if reason_col_idx is not None:
                            reason_val = df.iloc[idx_row, reason_col_idx]
                            if pd.notna(reason_val):
                                reason_str = str(reason_val).lower()
                                if 'certificado' in reason_str:
                                    has_certificado = True
                                if 'black' in reason_str and 'friday' in reason_str:
                                    has_promo = True
                                elif 'promo black' in reason_str:
                                    has_promo = True
                                if 'mvg' in reason_str and 'moon vacation getaway' in reason_str:
                                    has_mvg = True
                                    
                                if has_certificado or has_promo or has_mvg:
                                    print(f"Matched promo/cert/mvg for room {val_str}: {reason_str}")
                                
                        if val_str in seen_rooms:
                            duplicate_rooms.add(val_str)
                        else:
                            seen_rooms.add(val_str)
                            
                        if val_str not in room_data:
                            room_data[val_str] = {'underline': False, 'certificado': False, 'promo': False, 'mvg': False, 'name_tokens': set()}
                            
                            name_text = ""
                            if last_name_col_idx is not None:
                                name_text += " " + str(df.iloc[idx_row, last_name_col_idx])
                            if first_name_col_idx is not None:
                                name_text += " " + str(df.iloc[idx_row, first_name_col_idx])
                            if full_name_col_idx is not None and not name_text.strip():
                                name_text += " " + str(df.iloc[idx_row, full_name_col_idx])
                                
                            if name_text.strip() and str(name_text).lower() != 'nan':
                                clean_text = re.sub(r'[^a-zA-Z\s]', ' ', name_text.lower())
                                tokens = set(w for w in clean_text.split() if len(w) > 2)
                                room_data[val_str]['name_tokens'].update(tokens)
                            
                        if needs_underline: room_data[val_str]['underline'] = True
                        if has_certificado: room_data[val_str]['certificado'] = True
                        if has_promo: room_data[val_str]['promo'] = True
                        if has_mvg: room_data[val_str]['mvg'] = True
                except:
                    pass
        else:
            print("Fallback: Scanning all cells for room numbers")
            # Fallback: scan all cells for something that looks like a 4 or 5 digit room number
            for col in df.columns:
                for val in df[col].dropna():
                    try:
                        val_str = str(val).strip()
                        if val_str.endswith('.0'):
                            val_str = val_str[:-2]
                        val_str = val_str.replace(',', '')
                        
                        if val_str.isdigit() and 3 <= len(val_str) <= 6:
                            if val_str in seen_rooms:
                                duplicate_rooms.add(val_str)
                            else:
                                seen_rooms.add(val_str)
                                
                            if val_str not in room_data:
                                room_data[val_str] = {'underline': False, 'certificado': False, 'promo': False, 'mvg': False, 'name_tokens': set()}
                    except:
                        pass
                    
    print(f"Extracted {len(room_data)} unique rooms")
    return room_data, list(duplicate_rooms)

def highlight_pdf(pdf_path, room_data, output_path, lobby='sunrise'):
    doc = fitz.open(pdf_path)
    highlight_color = (0.5, 1.0, 0.5) # Light green color
    red_color = (1.0, 0.4, 0.4) # Light red color

    total_highlights = 0
    total_green = 0
    total_presentations = 0
    total_super_shots = 0
    processed_rooms = set()
    green_painted_rooms = set()
    new_members = set()
    checkouts = set()
    no_shows = set()
    
    f_suite_candidates = []
    
    extracted_rooms_membership = []
    last_grupo_x0 = None
    last_membership_x0 = None
    last_room_type_header_x0 = None
    
    for page_num, page in enumerate(doc):
        words = page.get_text("words")
        # Find the headers, restricting to the upper half of the page to avoid footers
        header_y_threshold = page.rect.height / 2
        
        # Find the x-coordinate of the "Room Type" column header
        room_type_header_x0 = None
        type_words = [w for w in words if "type" in w[4].lower() and w[1] < header_y_threshold]
        if type_words:
            room_type_header_x0 = type_words[0][0]
            last_room_type_header_x0 = room_type_header_x0
            print(f"Found Room Type header at x0: {room_type_header_x0}")
        else:
            room_type_header_x0 = last_room_type_header_x0
            
        # Find the x-coordinate of the standalone "Room" column header
        room_header_x0 = None
        room_words = [w for w in words if "room" in w[4].lower() and w[1] < header_y_threshold]
        
        membership_x0 = None
        membership_words = [w for w in words if "membership" in w[4].lower() and w[1] < header_y_threshold]
        if membership_words:
            membership_x0 = membership_words[0][0]
            last_membership_x0 = membership_x0
        else:
            membership_x0 = last_membership_x0
            
        grupo_x0 = None
        # Search for 'Grupo' or 'Party' column header — different lobbies use different names
        grupo_words = [w for w in words if ("grupo" in w[4].lower() or "party" in w[4].lower()) and w[1] < header_y_threshold]
        if grupo_words:
            grupo_x0 = grupo_words[0][0]
            last_grupo_x0 = grupo_x0
        else:
            grupo_x0 = last_grupo_x0
        
        standalone_rooms = []
        for rw in room_words:
            is_part_of_room_type = False
            for tw in type_words:
                # Check if "Type" is immediately to the right of this "Room"
                if abs(rw[1] - tw[1]) < 10 and 0 < (tw[0] - rw[0]) < 40:
                    is_part_of_room_type = True
                    break
            if not is_part_of_room_type:
                standalone_rooms.append(rw)
                
        if standalone_rooms:
            room_header_x0 = max(w[0] for w in standalone_rooms)
            print(f"Found Room header at x0: {room_header_x0}")
            
        page_room_y = []
        for w in words:
            is_in_column = False
            if room_header_x0 is not None:
                if abs(w[0] - room_header_x0) < 25:
                    is_in_column = True
            elif w[0] > page.rect.width / 2:
                is_in_column = True
            if is_in_column and w[4].isdigit() and len(w[4]) >= 3:
                page_room_y.append(w[1])
        page_room_y.sort()
        
        for w in words:
            word_text = w[4]
            
            is_in_column = False
            if room_header_x0 is not None:
                if abs(w[0] - room_header_x0) < 25:
                    is_in_column = True
            elif w[0] > page.rect.width / 2:
                is_in_column = True
                    
            if is_in_column and word_text.isdigit() and len(word_text) >= 3:
                idx = page_room_y.index(w[1])
                next_y = page_room_y[idx+1] if idx + 1 < len(page_room_y) else page.rect.height
                
                # Check if this line contains MVG or the special rates in the PDF
                # Strict line words for precise status matching (prevents Checked Out / Due Out collisions)
                line_words_raw = [w2 for w2 in words if abs(w2[1] - w[1]) < 5]
                line_words_raw.sort(key=lambda x: x[0])
                line_words = [w2[4].lower() for w2 in line_words_raw]
                
                is_kids_only = False
                if len(line_words) >= 2:
                    # Scan the whole line for '0' adults followed by '>0' minors
                    for i in range(len(line_words) - 1):
                        if line_words[i] == '0' and line_words[i+1].isdigit() and int(line_words[i+1]) > 0:
                            is_kids_only = True
                            break

                room_idx = -1
                for i, w2 in enumerate(line_words_raw):
                    if w2[0] == w[0] and w2[1] == w[1]:
                        room_idx = i
                        break
                        
                room_type = ""
                type_word = None
                if room_idx > 0:
                    type_word = line_words_raw[room_idx - 1]
                    room_type = type_word[4].upper()
                    if not room_type.startswith('F') and room_idx > 1:
                        if line_words_raw[room_idx - 2][4].upper().startswith('F'):
                            type_word = line_words_raw[room_idx - 2]
                            room_type = type_word[4].upper()
                            
                            
                line_text = " ".join(line_words)
                
                # Wide line words to catch wrapped text in the Agency / Company columns (up to next_y)
                wide_line_words = [w2[4].lower() for w2 in words if -5 <= (w2[1] - w[1]) < (next_y - w[1] - 2)]
                wide_line_text = " ".join(wide_line_words)
                
                is_mvg_pdf = ('mvg' in wide_line_text and 'moon' in wide_line_text and 'vacation' in wide_line_text) or ('main' in wide_line_text and 'moon' in wide_line_text)
                is_especiales = 'especial' in wide_line_text
                is_cortesia = 'cortesia' in wide_line_text and 'palace' in wide_line_text
                is_travel = 'travel' in wide_line_text and 'agent' in wide_line_text
                is_employee = 'employee' in wide_line_text and 'special' in wide_line_text
                is_rss = 'rss' in wide_line_text and 'pro' in wide_line_text
                is_agency_direct = 'agency' in wide_line_text and 'direct' in wide_line_text
                is_neteurgt = 'neteurg' in wide_line_text
                is_netcysgt = 'netcys' in wide_line_text and 'british' in wide_line_text and 'airways' in wide_line_text
                is_wow = 'wow' in wide_line_words
                is_uso_casa = 'uso' in wide_line_text and 'casa' in wide_line_text
                is_certmvg = 'certmvg' in wide_line_text
                is_to_eu = 'to' in line_words and 'eu' in line_words
                
                is_checked_out = False
                checked_out_rects = []
                
                # First check if it's on the exact same line
                if 'checked out' in line_text or 'checkedout' in line_text:
                    is_checked_out = True
                    for w2 in line_words_raw:
                        if w2[4].lower() in ["checked", "out", "checkedout", "checked-out"]:
                            checked_out_rects.append(fitz.Rect(w2[0], w2[1], w2[2], w2[3]))
                else:
                    checked_words = [w2 for w2 in words if w2[4].lower() == 'checked' and abs(w2[1] - w[1]) < 15]
                    out_words = [w2 for w2 in words if w2[4].lower() == 'out' and abs(w2[1] - w[1]) < 15]
                    for cw in checked_words:
                        for ow in out_words:
                            # CHECKED must be above OUT and roughly aligned horizontally
                            if cw[1] <= ow[1] + 2 and abs(cw[0] - ow[0]) < 20:
                                is_checked_out = True
                                checked_out_rects.append(fitz.Rect(cw[0], cw[1], cw[2], cw[3]))
                                checked_out_rects.append(fitz.Rect(ow[0], ow[1], ow[2], ow[3]))
                                break
                                
                is_no_show = False
                no_show_rects = []
                if 'no' in line_words and 'show' in line_words:
                    is_no_show = True
                    for w2 in line_words_raw:
                        if w2[4].lower() in ['no', 'show', 'noshow']:
                            no_show_rects.append(fitz.Rect(w2[0], w2[1], w2[2], w2[3]))
                                
                is_transfer = 'transfer' in wide_line_text.replace(' ', '')
                is_free = 'free' in line_words
                
                strong_red = is_mvg_pdf or is_especiales or is_cortesia or is_travel or is_employee or is_rss or is_agency_direct or is_neteurgt or is_netcysgt or is_uso_casa or is_certmvg or is_free
                if lobby in ['nizuc', 'grand'] and is_wow:
                    strong_red = True
                    
                weak_red = any(c in line_words for c in ['va', 'vc', 'm', 'vd', 'vr'])
                
                in_excel = word_text in room_data
                if in_excel and word_text not in processed_rooms:
                    processed_rooms.add(word_text)
                    
                data = room_data.get(word_text, {'underline': False, 'certificado': False, 'promo': False, 'mvg': False})
                
                has_highlight = in_excel or strong_red or weak_red or is_neteurgt or is_netcysgt or is_to_eu
                
                final_color = 'none'
                offset_x = 8 # Add a small buffer after the last word
                
                if has_highlight or is_checked_out or is_transfer or is_kids_only or is_no_show:
                    if has_highlight:
                        rect = fitz.Rect(w[0], w[1], w[2], w[3])
                        annot = page.add_highlight_annot(rect)
                        
                        # Apply colors based on priority
                        if is_neteurgt or is_netcysgt or is_to_eu:
                            annot.set_colors(stroke=(1, 1, 0)) # Yellow
                            final_color = 'yellow'
                        elif in_excel:
                            annot.set_colors(stroke=highlight_color) # green
                            final_color = 'green'
                            if word_text not in green_painted_rooms:
                                green_painted_rooms.add(word_text)
                                total_green += 1
                                if data['underline']:
                                    total_presentations += 1
                        elif strong_red or data.get('mvg', False) or weak_red:
                            annot.set_colors(stroke=red_color)
                            final_color = 'red'
                            
                        annot.update()
                        
                    # Handle text insertions
                    right_words = [w2 for w2 in line_words_raw if w2[0] >= w[0]]
                    base_x = max(w2[2] for w2 in right_words) if right_words else w[2]
                    
                    if is_checked_out and final_color == 'green':
                        page.insert_text(fitz.Point(base_x + offset_x, w[3] - 2), "C.O", fontsize=8, color=(1, 0, 0))
                        offset_x += 18
                        
                    if is_no_show and final_color == 'green':
                        page.insert_text(fitz.Point(base_x + offset_x, w[3] - 2), "N.S.", fontsize=8, color=(1, 0, 0))
                        offset_x += 18
                        no_shows.add(word_text)
                        
                    if (is_neteurgt or is_netcysgt) and not is_to_eu:
                        page.insert_text(fitz.Point(base_x + offset_x, w[3] - 2), "TO EU", fontsize=8, color=(0, 0, 0))
                        offset_x += 25
                        
                    if is_kids_only and final_color in ('green', 'none'):
                        page.insert_text(fitz.Point(base_x + offset_x, w[3] - 2), "KIDS", fontsize=8, color=(0.53, 0.81, 0.98))
                        offset_x += 20
                        

                    # Handle underline for checked out
                    if is_checked_out and final_color == 'green':
                        checkouts.add(word_text)
                        for rect in checked_out_rects:
                            annot2 = page.add_underline_annot(rect)
                            annot2.set_colors(stroke=(1, 0, 0))
                            annot2.update()
                            
                    # Handle underline for no show
                    if is_no_show and final_color == 'green':
                        for rect in no_show_rects:
                            annot2 = page.add_underline_annot(rect)
                            annot2.set_colors(stroke=(1, 0, 0))
                            annot2.update()
                                
                    # Handle underline for transfer
                    if is_transfer:
                        for w2 in words:
                            if abs(w2[1] - w[1]) < 15 and w2[4].lower() in ['transfer', 'transfe']:
                                rect2 = fitz.Rect(w2[0], w2[1], w2[2], w2[3])
                                annot2 = page.add_underline_annot(rect2)
                                annot2.set_colors(stroke=(1.0, 1.0, 0.0)) # Yellow
                                annot2.update()
                    
                    if data['underline']:
                        p1 = fitz.Point(rect.x0, rect.y1 + 1.5)
                        p2 = fitz.Point(rect.x1, rect.y1 + 1.5)
                        page.draw_line(p1, p2, color=(0, 0, 0), width=1.5)
                        
                    # Highlight Room Type if needed
                    is_transfer_m_rule = is_transfer and final_color == 'green' and 'm' in line_words
                    if is_transfer_m_rule:
                        new_members.add(word_text)
                    
                    if data['certificado'] or data['promo'] or is_transfer_m_rule:
                        type_word = None
                        if room_type_header_x0 is not None:
                            candidates = [w2 for w2 in words if abs(w2[1] - w[1]) < 5 and abs(w2[0] - room_type_header_x0) < 50]
                            if candidates:
                                type_word = min(candidates, key=lambda w2: abs(w2[0] - room_type_header_x0))
                                
                        if type_word is None:
                            # Fallback: Find the word immediately to the left of the room number
                            left_words = [w2 for w2 in words if abs(w2[1] - w[1]) < 5 and w2[2] < w[0]]
                            if left_words:
                                left_words.sort(key=lambda x: x[2], reverse=True)
                                type_word = left_words[0]
                                
                        if type_word:
                            print(f"Highlighting room type {type_word[4]} for room {word_text}")
                            type_rect = fitz.Rect(type_word[0], type_word[1], type_word[2], type_word[3])
                            type_annot = page.add_highlight_annot(type_rect)
                            
                            if is_transfer_m_rule:
                                type_annot.set_colors(stroke=red_color) # Red
                            elif data['certificado'] and data['promo']:
                                type_annot.set_colors(stroke=(1.0, 0.6, 0.8)) # Pink
                            elif data['certificado']:
                                type_annot.set_colors(stroke=(0.4, 0.7, 1.0)) # Blue
                            elif data['promo']:
                                type_annot.set_colors(stroke=(0.8, 0.4, 1.0)) # Purple
                                
                            type_annot.update()
                        else:
                            print(f"WARNING: Could not find Room Type text for room {word_text}")
                        
                    # Highlight 'M' and write N.M. at end of row (after Language column)
                    if is_transfer_m_rule:
                        m_word = None
                        for w2 in words:
                            if abs(w2[1] - w[1]) < 5 and w2[4].lower() == 'm':
                                m_word = w2
                                break
                                
                        if m_word:
                            rect_m = fitz.Rect(m_word[0], m_word[1], m_word[2], m_word[3])
                            annot_m = page.add_highlight_annot(rect_m)
                            annot_m.set_colors(stroke=(1, 0, 0)) # Red highlight
                            annot_m.update()
                            # Place N.M. at the far right end of the full row (after Language col)
                            full_row_words = [w2 for w2 in words if abs(w2[1] - w[1]) < 15]
                            nm_x = max(w2[2] for w2 in full_row_words) + 6 if full_row_words else m_word[2] + 12
                            page.insert_text(fitz.Point(nm_x, m_word[3] - 2), "N.M.", fontsize=8, color=(1, 0, 0))
                            
                # Extract membership info for bracket linking
                membership_text = ""
                membership_right_edge = None
                if membership_x0 is not None:
                    import re
                    # Strict left boundary: start AT membership_x0 (never reach into Grupo column)
                    # Strict right boundary: stop before Room Type header
                    mem_left = membership_x0
                    mem_right = membership_x0 + 75
                    if room_type_header_x0 and room_type_header_x0 > membership_x0:
                        mem_right = min(mem_right, room_type_header_x0 - 5)
                    w_mid = (w[1] + w[3]) / 2
                    # Require the middle of the Room text to intersect the Y-bounds of the membership text
                    m_words = [w2 for w2 in words if w2[1] - 3 <= w_mid <= w2[3] + 3 and mem_left <= w2[0] <= mem_right]
                    if m_words:
                        raw_mem = "".join([mw[4] for mw in m_words]).strip()
                        mem_match = re.search(r'\d{4,}', raw_mem)
                        if "OUT" not in raw_mem.upper():
                            if mem_match:
                                membership_text = mem_match.group(0)
                            elif len(raw_mem) > 5:
                                # Fallback for text-based memberships: normalize alphanumeric characters
                                membership_text = re.sub(r'[^a-zA-Z0-9]', '', raw_mem).upper()
                                
                            if membership_text:
                                membership_right_edge = max(mw[2] for mw in m_words)
                    print(f"  Room {word_text}: mem_left={mem_left:.1f}, mem_right={mem_right:.1f}, raw='{raw_mem if m_words else ''}', membership='{membership_text}'")
                        
                # Extract Grupo/Party info for bracket linking
                grupo_text = ""
                grupo_key = ""  # numeric-only key for grouping
                grupo_right_edge = None
                if grupo_x0 is not None:
                    import re
                    # Stop Grupo extraction before Membership column starts
                    grupo_max_x = grupo_x0 + 120
                    if membership_x0 and membership_x0 > grupo_x0:
                        grupo_max_x = min(grupo_max_x, membership_x0 - 5)
                    # Only grab words on the SAME line (we only need the number now, multiline names don't matter)
                    g_words = [w2 for w2 in words if w2[1] - 3 <= w_mid <= w2[3] + 3 and (grupo_x0 - 5) <= w2[0] <= grupo_max_x]
                    if g_words:
                        raw_grp = " ".join([gw[4] for gw in sorted(g_words, key=lambda x: (x[1], x[0]))]).strip()
                        # VALIDATION: try to find a 4+ digit sequence first
                        grp_match = re.search(r'\d{4,}', raw_grp)
                        if "OUT" not in raw_grp.upper():
                            if grp_match:
                                grupo_text = raw_grp
                                grupo_key = grp_match.group(0)  # use ONLY the number for grouping
                            elif len(raw_grp) > 5:
                                grupo_text = raw_grp
                                # Fallback for text-based groups: normalize alphanumeric characters
                                grupo_key = re.sub(r'[^a-zA-Z0-9]', '', raw_grp).upper()
                                
                            if grupo_key:
                                grupo_right_edge = max(gw[2] for gw in g_words)
                    
                extracted_rooms_membership.append({
                    "room": word_text,
                    "room_x1": w[2],
                    "color": final_color,
                    "membership": membership_text,
                    "bracket_x": membership_right_edge + 8 if membership_right_edge else (membership_x0 + 50 if membership_x0 else w[0] - 50),
                    "grupo": grupo_text,
                    "grupo_key": grupo_key,  # numeric-only for grouping
                    "g_bracket_x": grupo_right_edge + 8 if grupo_right_edge else (grupo_x0 + 70 if grupo_x0 else w[0] - 100),
                    "page_idx": page.number,
                    "y0": w[1],
                    "y1": w[3],
                    "line_words_raw": line_words_raw,
                    "type_word": type_word,
                    "is_mvg": is_mvg_pdf,
                    "offset_x": offset_x,
                    "membership_x0": membership_x0,
                    "grupo_x0": grupo_x0
                })
                    
                if has_highlight or is_checked_out or is_transfer or is_kids_only:
                    total_highlights += 1
    print(f"Total highlights made: {total_highlights}")
    
    # Pass 2: Group by Membership Number per page
    from collections import defaultdict
    page_membership_groups = defaultdict(lambda: defaultdict(list))
    page_grupo_groups = defaultdict(lambda: defaultdict(list))
    
    for r in extracted_rooms_membership:
        m_num = r['membership']
        if m_num and len(m_num) >= 4:
            page_membership_groups[r['page_idx']][m_num].append(r)
            
        # Use grupo_key (numeric only) so '19244015 GARCI' and '19244015 PATEL' group together
        g_key = r.get('grupo_key', '')
        if g_key and len(g_key) >= 4:
            page_grupo_groups[r['page_idx']][g_key].append(r)
            
    # Global groupings for cross-page Super Shots
    global_membership_groups = defaultdict(list)
    global_grupo_groups = defaultdict(list)
    
    for r in extracted_rooms_membership:
        if r['membership'] and len(r['membership']) >= 4:
            global_membership_groups[r['membership']].append(r)
        g_key = r.get('grupo_key', '')
        if g_key and len(g_key) >= 4:
            global_grupo_groups[g_key].append(r)
            
    # SUPER SHOT RULE: A group qualifies ONLY if it has:
    #   - At least one room that is RED and is_mvg (occupied MVG room in PDF)
    #   - At least one room that is GREEN (available room in Excel)
    # Simply having MVG in agency text is NOT enough — the room must actually be highlighted RED.
    super_shot_memberships = set()
    for m_num, rooms in global_membership_groups.items():
        has_red_mvg = any(r['color'] == 'red' and r['is_mvg'] for r in rooms)
        has_green   = any(r['color'] == 'green' for r in rooms)
        if has_red_mvg and has_green:
            super_shot_memberships.add(m_num)
            
    super_shot_grupos = set()
    for g_key, rooms in global_grupo_groups.items():
        has_red_mvg = any(r['color'] == 'red' and r['is_mvg'] for r in rooms)
        has_green   = any(r['color'] == 'green' for r in rooms)
        if has_red_mvg and has_green:
            super_shot_grupos.add(g_key)

            
    # Pass 2.5: Apply Global Super Shots BEFORE drawing brackets
    super_shot_global_groups = []
    processed_ss_rooms = set()
    
    for m_num in super_shot_memberships:
        rooms = global_membership_groups[m_num]
        room_ids = tuple(sorted(r['room'] for r in rooms))
        if room_ids not in processed_ss_rooms:
            super_shot_global_groups.append(rooms)
            processed_ss_rooms.add(room_ids)
            
    for g_text in super_shot_grupos:
        rooms = global_grupo_groups[g_text]
        room_ids = tuple(sorted(r['room'] for r in rooms))
        if room_ids not in processed_ss_rooms:
            super_shot_global_groups.append(rooms)
            processed_ss_rooms.add(room_ids)
            
    # NOTE: Family Suites (f_id / same last name) are intentionally excluded from Super Shot groups

    # We will filter out invalid texts before adding to groups in Pass 2
    for rooms in super_shot_global_groups:
        for r in rooms:
            if r['color'] in ['green', 'red']:
                r['color'] = 'green' # Red becomes green
            
    # Distinct bracket colors
    bracket_colors = [
        (0.6, 0.2, 0.8), # Purple
        (0.0, 0.6, 0.6), # Teal
        (1.0, 0.5, 0.0), # Orange
        (0.9, 0.2, 0.6), # Pink
        (0.0, 0.4, 0.8), # Deep Blue
    ]
    
    # Pass 3: Draw brackets for membership groups
    total_linked_groups = 0
    for page_idx, groups in page_membership_groups.items():
        page = doc[page_idx]
        color_idx = 0
        
        for m_num, rooms in groups.items():
            if len(rooms) > 1:
                # Draw bracket for any 2+ rooms sharing membership (green+green, red+red, or mixed)
                bracket_rooms = [r for r in rooms if r['color'] in ['green', 'red']]
                
                # Universal rule: Do not link if all rooms are red (must have at least one green)
                if not any(r['color'] == 'green' for r in bracket_rooms):
                    continue
                    
                if len(bracket_rooms) > 1:
                    total_linked_groups += 1
                    min_y = min(r['y0'] for r in bracket_rooms)
                    max_y = max(r['y1'] for r in bracket_rooms)
                    
                    has_green = any(r['color'] == 'green' for r in bracket_rooms)
                    bracket_color = bracket_colors[color_idx % len(bracket_colors)] if has_green else (0.5, 0.5, 0.5)
                    color_idx += 1
                    
                    type_xs = [r['type_word'][0] for r in bracket_rooms if r['type_word']]
                    fallback_xs = [r['room_x1'] - 40 for r in bracket_rooms]
                    min_type_x = min(type_xs) if type_xs else min(fallback_xs)
                    
                    # Find rightmost text in the vertical span — adapts to any lobby layout
                    page_words = page.get_text("words")
                    span_words = [w for w in page_words if (min_y - 5) <= w[1] and w[3] <= (max_y + 5) and w[2] < min_type_x - 5]
                    
                    if span_words:
                        right_x = max(w[2] for w in span_words) + 8
                    else:
                        right_x = min_type_x - 20
                        
                    if right_x > min_type_x - 6:
                        right_x = min_type_x - 6
                    
                    # Draw vertical line spanning from top room to bottom room
                    page.draw_line(fitz.Point(right_x, min_y + 5), fitz.Point(right_x, max_y - 5), color=bracket_color, width=2)
                    
                    # Draw horizontal ticks pointing at each room
                    for br in bracket_rooms:
                        mid_y = (br['y0'] + br['y1']) / 2
                        page.draw_line(fitz.Point(right_x, mid_y), fitz.Point(right_x - 8, mid_y), color=bracket_color, width=1.5)

    # Pass 3b: Draw Grupo/Party brackets
    grupo_colors = [
        (0.0, 0.5, 0.5), # Teal
        (0.8, 0.2, 0.2), # Dark Red
        (0.2, 0.6, 0.2), # Green
        (0.2, 0.2, 0.8), # Blue
        (0.7, 0.4, 0.0), # Brown
    ]
    for page_idx, groups in page_grupo_groups.items():
        page = doc[page_idx]
        color_idx = 0
        
        for g_text, rooms in groups.items():
            if len(rooms) > 1:
                # Avoid double grouping if they already share a membership
                valid_mems = [r['membership'] for r in rooms if r['membership'] and len(r['membership']) >= 4]
                if len(valid_mems) == len(rooms) and len(set(valid_mems)) == 1:
                    continue
                    
                bracket_rooms = [r for r in rooms if r['color'] in ['green', 'red']]
                
                # Universal rule: Do not link if all rooms are red (must have at least one green)
                if not any(r['color'] == 'green' for r in bracket_rooms):
                    continue
                        
                if len(bracket_rooms) > 1:
                        total_linked_groups += 1
                        bracket_color = grupo_colors[color_idx % len(grupo_colors)]
                        color_idx += 1
                        
                        min_y = min(r['y0'] for r in bracket_rooms)
                        max_y = max(r['y1'] for r in bracket_rooms)
                        
                        type_xs = [r['type_word'][0] for r in bracket_rooms if r['type_word']]
                        fallback_xs = [r['room_x1'] - 40 for r in bracket_rooms]
                        min_type_x = min(type_xs) if type_xs else min(fallback_xs)
                        
                        m_x0 = max([r.get('membership_x0') or 0 for r in bracket_rooms])
                        g_x0 = max([r.get('grupo_x0') or 0 for r in bracket_rooms])
                        boundary_x = m_x0 + 60 if m_x0 > 0 else (g_x0 + 80 if g_x0 > 0 else min_type_x - 30)
                        
                        # Find the absolute rightmost edge of ANY text to the left of the boundary
                        page_words = page.get_text("words")
                        left_words = [w for w in page_words if (min_y - 5) <= w[1] and w[3] <= (max_y + 5) and w[0] < boundary_x]
                        
                        if left_words:
                            right_x = max(w[2] for w in left_words) + 14 # Extra offset for Grupo brackets
                        else:
                            right_x = boundary_x + 6
                            
                        if right_x > min_type_x - 6:
                            right_x = min_type_x - 6
                        
                        # Draw vertical line
                        page.draw_line(fitz.Point(right_x, min_y + 5), fitz.Point(right_x, max_y - 5), color=bracket_color, width=2)
                        
                        # Draw horizontal ticks
                        for br in bracket_rooms:
                            mid_y = (br['y0'] + br['y1']) / 2
                            page.draw_line(fitz.Point(right_x, mid_y), fitz.Point(right_x - 8, mid_y), color=bracket_color, width=1.5)

    # Pass 5: Global Super Shots
    # The groups were already determined and color-mutated in Pass 2.5
    # Here we just apply the pink agency highlight and multi-page stars
    total_super_shots = len(super_shot_global_groups)
    
    for rooms in super_shot_global_groups:
        is_multi_page = len(set(r['page_idx'] for r in rooms)) > 1
        
        for r in rooms:
            page = doc[r['page_idx']]
            
            # 1. Highlight Agency Text
            agency_words = [w for w in r['line_words_raw'] if w[2] < 200]
            if agency_words:
                a_min_x = min(w[0] for w in agency_words)
                a_max_x = max(w[2] for w in agency_words)
                a_rect = fitz.Rect(a_min_x, r['y0'], a_max_x, r['y1'])
                a_annot = page.add_highlight_annot(a_rect)
                a_annot.set_colors(stroke=(1.0, 0.6, 0.8)) # Pink
                a_annot.update()
                
            # 2. Draw Multi-page Star
            if is_multi_page:
                linked_rooms = [r2['room'] for r2 in rooms if r2['room'] != r['room']]
                if linked_rooms:
                    text_str = "* " + ", ".join(linked_rooms)
                    text_x = r['room_x1'] + r['offset_x'] + 5
                    # Use a dark golden-yellow so it's visible on white paper
                    page.insert_text(fitz.Point(text_x, r['y1'] - 1), text_str, fontsize=8.5, color=(0.85, 0.65, 0.0))

    # Pass 4: Fuzzy Name Matching for Missing Rooms
    missing_rooms = [r for r in room_data.keys() if r not in processed_rooms]
    moved_rooms_log = []
    if missing_rooms:
        print(f"Pass 4: Searching for {len(missing_rooms)} missing rooms by name...")
        for page_num, page in enumerate(doc):
            words = page.get_text("words")
            
            # Find Room column boundary
            room_words = [w for w in words if "room" in w[4].lower() and w[1] < page.rect.height / 2]
            room_header_x0 = max(w[0] for w in room_words) if room_words else None
            
            page_rooms = []
            for w in words:
                word_text = w[4]
                is_in_column = False
                if room_header_x0 is not None:
                    if abs(w[0] - room_header_x0) < 25:
                        is_in_column = True
                elif w[0] > page.rect.width / 2:
                    is_in_column = True
                        
                if is_in_column and word_text.isdigit() and len(word_text) >= 3:
                    page_rooms.append(w)
                    
            page_rooms.sort(key=lambda x: x[1])
            
            for i, w_room in enumerate(page_rooms):
                word_text = w_room[4]
                if word_text in processed_rooms:
                    continue
                    
                next_y = page_rooms[i+1][1] if i + 1 < len(page_rooms) else page.rect.height
                block_words = [w2 for w2 in words if w_room[1] - 5 <= w2[1] < next_y - 2]
                
                block_text = " ".join([w2[4] for w2 in block_words])
                clean_block = re.sub(r'[^a-zA-Z\s]', ' ', block_text.lower())
                block_tokens = set(clean_block.split())
                
                matched_room = None
                for m_room in missing_rooms:
                    m_tokens = room_data[m_room].get('name_tokens', set())
                    if len(m_tokens) >= 2 and m_tokens.issubset(block_tokens):
                        matched_room = m_room
                        break
                        
                if matched_room:
                    print(f"FUZZY MATCH: Found missing room {matched_room} at new room {word_text}")
                    moved_rooms_log.append({'old': matched_room, 'new': word_text})
                    
                    rect = fitz.Rect(w_room[0], w_room[1], w_room[2], w_room[3])
                    annot = page.add_highlight_annot(rect)
                    annot.set_colors(stroke=highlight_color)
                    annot.update()
                    
                    main_line_words = [w2 for w2 in words if abs(w2[1] - w_room[1]) < 5 and w2[0] >= w_room[0]]
                    base_x = max(w2[2] for w2 in main_line_words) if main_line_words else w_room[2]
                    page.insert_text(fitz.Point(base_x + 8, w_room[3] - 2), "MOVED", fontsize=8, color=(0, 0.5, 0))
                    
                    processed_rooms.add(word_text)  # Mark the new room as processed!
                    processed_rooms.add(matched_room) # Mark the old room as processed so it counts as found
                    missing_rooms.remove(matched_room)
                    total_green += 1
                    if room_data.get(matched_room, {}).get('underline'):
                        total_presentations += 1
                        page.draw_line(fitz.Point(w_room[0], w_room[3] + 1), fitz.Point(w_room[2], w_room[3] + 1), color=red_color, width=1.5)

    doc.save(output_path)
    doc.close()
    
    # Calculate PDF-specific stats
    pdf_promos = sum(1 for room in processed_rooms if room_data.get(room, {}).get('promo', False))
    pdf_certs = sum(1 for room in processed_rooms if room_data.get(room, {}).get('certificado', False))
    
    super_shots_mvg_list = sorted(list(set([r['room'] for group in super_shot_global_groups for r in group if r['is_mvg']])))
    super_shots_green_list = sorted(list(set([r['room'] for group in super_shot_global_groups for r in group if r['color'] == 'green' and not r['is_mvg']])))
    
    green_rooms = set(r['room'] for r in extracted_rooms_membership if r['color'] == 'green')
    green_checkouts = [room for room in checkouts if room in green_rooms]
    
    return {
        'total_rooms_found': len(processed_rooms),
        'total_green': total_green,
        'total_presentations': total_presentations,
        'total_linked_groups': total_linked_groups,
        'total_promos': pdf_promos,
        'total_certs': pdf_certs,
        'total_super_shots': total_super_shots,
        'super_shots_mvg': super_shots_mvg_list,
        'super_shots_green': super_shots_green_list,
        'new_members': sorted(list(new_members)),
        'checkouts': sorted(green_checkouts),
        'no_shows': sorted(list(no_shows)),
        'processed_rooms_list': list(processed_rooms),
        'moved_rooms': moved_rooms_log
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_files():
    if 'excel_file' not in request.files or 'pdf_file' not in request.files:
        return jsonify({'error': 'Missing files'}), 400
        
    excel_file = request.files['excel_file']
    pdf_file = request.files['pdf_file']
    
    if excel_file.filename == '' or pdf_file.filename == '':
        return jsonify({'error': 'No files selected'}), 400
        
    excel_filename = secure_filename(excel_file.filename)
    pdf_filename = secure_filename(pdf_file.filename)
    
    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], excel_filename)
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
    output_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'highlighted_' + pdf_filename)
    
    excel_file.save(excel_path)
    pdf_file.save(pdf_path)
    
    try:
        lobby = request.form.get('lobby', 'sunrise')
        
        # 1. Extract rooms
        rooms, duplicates = extract_rooms_from_excel(excel_path, target_lobby=lobby)
        if not rooms:
            return jsonify({'error': 'Could not find any room numbers in the Excel file for this lobby.'}), 400
            
        # 2. Highlight PDF
        stats = highlight_pdf(pdf_path, rooms, output_pdf_path, lobby)
        
        # Filter duplicates: Only show duplicates if that room was actually found in the PDF
        processed_rooms_set = set(stats['processed_rooms_list'])
        stats['duplicates'] = [d for d in duplicates if d in processed_rooms_set]
        
        stats['excel_total'] = len(rooms) + len(duplicates)
        
        # Add the lobby name so the frontend can display it in the summary image
        stats['lobby'] = lobby.title()
        if stats['lobby'] == 'Grand':
            stats['lobby'] = 'The Grand'
            
        # Remove the temporary list so we don't send it to the frontend
        del stats['processed_rooms_list']
        
        # Calculate missing rooms
        stats['missing_rooms'] = sorted(list(set(rooms) - processed_rooms_set))
        
        # 3. Clean up input files
        os.remove(excel_path)
        os.remove(pdf_path)
        
        return jsonify({
            'success': True,
            'message': 'Success',
            'download_url': f'/download/{secure_filename("highlighted_" + pdf_filename)}',
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype='application/pdf')
    return "File not found", 404

if __name__ == '__main__':
    # Listen on all interfaces so it can be accessed from the iPad
    app.run(host='0.0.0.0', port=5000, debug=True)
