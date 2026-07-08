import os
import io
import pandas as pd
import fitz  # PyMuPDF
from flask import Flask, request, send_file, render_template, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def extract_rooms_from_excel(excel_path):
    try:
        dfs = pd.read_excel(excel_path, header=None, sheet_name=None)
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return {}
    
    room_data = {}
    seen_rooms = set()
    duplicate_rooms = set()
    
    for sheet_name, df in dfs.items():
        print(f"Processing sheet: {sheet_name}")
        # 1. Search the first 20 rows to find the actual header row and Room column
        header_row_idx = None
        room_col_idx = None
        attendance_col_idx = None
        reason_col_idx = None
        
        for idx, row in df.head(20).iterrows():
            for col_idx, val in row.items():
                val_str = str(val).lower()
                if 'roomnum' in val_str or 'room' in val_str:
                    room_col_idx = col_idx
                if 'attendance' in val_str or 'presentation' in val_str:
                    attendance_col_idx = col_idx
                if 'reason' in val_str:
                    reason_col_idx = col_idx
                    
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
                            room_data[val_str] = {'underline': False, 'certificado': False, 'promo': False, 'mvg': False}
                            
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
                                room_data[val_str] = {'underline': False, 'certificado': False, 'promo': False, 'mvg': False}
                    except:
                        pass
                    
    print(f"Extracted {len(room_data)} unique rooms")
    return room_data, list(duplicate_rooms)

def highlight_pdf(pdf_path, room_data, output_path):
    doc = fitz.open(pdf_path)
    highlight_color = (0.5, 1.0, 0.5) # Light green color
    red_color = (1.0, 0.4, 0.4) # Light red color

    total_highlights = 0
    total_green = 0
    total_presentations = 0
    total_super_shots = 0
    processed_rooms = set()
    new_members = set()
    checkouts = set()
    
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
        grupo_words = [w for w in words if "grupo" in w[4].lower() and w[1] < header_y_threshold]
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
            
        for w in words:
            word_text = w[4]
            
            # First check if this word is in the Room column and looks like a room number
            is_in_column = False
            if room_header_x0 is not None:
                drift = abs(w[0] - room_header_x0)
                if drift < 25:
                    is_in_column = True
            else:
                if w[0] > page.rect.width / 2:
                    is_in_column = True
                    
            if is_in_column and word_text.isdigit() and len(word_text) >= 3:
                # Check if this line contains MVG or the special rates in the PDF
                # Strict line words for precise status matching (prevents Checked Out / Due Out collisions)
                line_words_raw = [w2 for w2 in words if abs(w2[1] - w[1]) < 5]
                line_words_raw.sort(key=lambda x: x[0])
                line_words = [w2[4].lower() for w2 in line_words_raw]
                
                is_kids_only = False
                if len(line_words) >= 2:
                    if line_words[0] == '0' and line_words[1].isdigit() and int(line_words[1]) > 0:
                        is_kids_only = True
                        
                # Check for F-Suite Candidates
                family_id = next((w2[4].replace(',', '').strip().lower() for w2 in line_words_raw if ',' in w2[4]), None)
                if not family_id:
                    # Fallback to the 7-9 digit reservation/confirmation number on the left side
                    for w2 in line_words_raw:
                        if w2[4].isdigit() and 7 <= len(w2[4]) <= 9:
                            family_id = w2[4]
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
                            
                if family_id and room_type.startswith('F'):
                    f_suite_candidates.append({
                        'page_idx': page_num,
                        'family_id': family_id,
                        'y0': w[1],
                        'y1': w[3],
                        'bracket_x': w[2] + 35  # Safe distance for bracket
                    })
                
                line_text = " ".join(line_words)
                
                # Wide line words to catch wrapped text in the Agency / Company columns
                wide_line_words = [w2[4].lower() for w2 in words if abs(w2[1] - w[1]) < 15]
                wide_line_text = " ".join(wide_line_words)
                
                is_mvg_pdf = 'mvg' in wide_line_text and 'moon' in wide_line_text and 'vacation' in wide_line_text
                is_especiales = 'especial' in wide_line_text
                is_cortesia = 'cortesia' in wide_line_text and 'palace' in wide_line_text
                is_travel = 'travel' in wide_line_text and 'agent' in wide_line_text
                is_employee = 'employee' in wide_line_text and 'special' in wide_line_text
                is_rss = 'rss' in wide_line_text and 'pro' in wide_line_text
                is_agency_direct = 'agency' in wide_line_text and 'direct' in wide_line_text
                is_neteurgt = 'neteurgt' in wide_line_text
                
                is_checked_out = 'checked out' in line_text
                is_transfer = 'transfer' in line_text
                
                strong_red = is_mvg_pdf or is_especiales or is_cortesia or is_travel or is_employee or is_rss or is_agency_direct
                weak_red = any(c in line_words for c in ['va', 'vc', 'm', 'vd', 'vr'])
                
                in_excel = word_text in room_data
                data = room_data.get(word_text, {'underline': False, 'certificado': False, 'promo': False, 'mvg': False})
                
                has_highlight = in_excel or strong_red or weak_red or is_neteurgt
                
                final_color = 'none'
                
                if has_highlight or is_checked_out or is_transfer:
                    if has_highlight:
                        rect = fitz.Rect(w[0], w[1], w[2], w[3])
                        annot = page.add_highlight_annot(rect)
                        
                        # Apply colors based on priority
                        if is_neteurgt:
                            annot.set_colors(stroke=(1, 1, 0)) # Yellow
                            final_color = 'yellow'
                        elif strong_red or data.get('mvg', False):
                            annot.set_colors(stroke=red_color)
                            final_color = 'red'
                        elif in_excel:
                            annot.set_colors(stroke=highlight_color) # green
                            final_color = 'green'
                            if word_text not in processed_rooms:
                                processed_rooms.add(word_text)
                                total_green += 1
                                if data['underline']:
                                    total_presentations += 1
                        elif weak_red:
                            annot.set_colors(stroke=red_color)
                            final_color = 'red'
                            
                        annot.update()
                        
                    # Handle text insertions
                    # Handle text insertions
                    offset_x = 12
                    if is_checked_out and final_color == 'green':
                        page.insert_text(fitz.Point(w[2] + offset_x, w[3] - 2), "C.O", fontsize=8, color=(1, 0, 0))
                        offset_x += 18
                        
                    if is_neteurgt:
                        page.insert_text(fitz.Point(w[2] + offset_x, w[3] - 2), "TO EU", fontsize=8, color=(0, 0, 0))
                        offset_x += 25
                        
                    if is_kids_only:
                        page.insert_text(fitz.Point(w[2] + offset_x, w[3] - 2), "KIDS", fontsize=8, color=(0.53, 0.81, 0.98))
                        offset_x += 20
                        
                    # Handle underline for checked out
                    if is_checked_out:
                        checkouts.add(word_text)
                        for w2 in words:
                            if abs(w2[1] - w[1]) < 5 and w2[4].lower() in ["checked", "out", "checkedout", "checked-out"]:
                                rect2 = fitz.Rect(w2[0], w2[1], w2[2], w2[3])
                                annot2 = page.add_underline_annot(rect2)
                                annot2.set_colors(stroke=(1, 0, 0))
                                annot2.update()
                                
                    # Handle underline for transfer
                    if is_transfer:
                        for w2 in words:
                            if abs(w2[1] - w[1]) < 5 and 'transfer' in w2[4].lower():
                                rect2 = fitz.Rect(w2[0], w2[1], w2[2], w2[3])
                                annot2 = page.add_underline_annot(rect2)
                                annot2.set_colors(stroke=(1.0, 0.65, 0.0)) # Orange
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
                        
                    # Highlight 'M' and write N.M.
                    if is_transfer_m_rule:
                        m_word = None
                        for w2 in words:
                            if abs(w2[1] - w[1]) < 5 and w2[4].lower() == 'm':
                                m_word = w2
                                break
                                
                        if m_word:
                            rect_m = fitz.Rect(m_word[0], m_word[1], m_word[2], m_word[3])
                            annot_m = page.add_highlight_annot(rect_m)
                            annot_m.set_colors(stroke=red_color)
                            annot_m.update()
                            page.insert_text(fitz.Point(m_word[2] + 12, m_word[3] - 2), "N.M.", fontsize=8, color=(1, 0, 0))
                            
                    # Extract membership info for bracket linking
                    membership_text = ""
                    membership_right_edge = None
                    if membership_x0 is not None:
                        # Fixed safe width of 55 points (fits a 7-digit number perfectly) to avoid Room Type column
                        mem_max_x = membership_x0 + 55
                        m_words = [w2 for w2 in words if abs(w2[1] - w[1]) < 5 and (membership_x0 - 25) <= w2[0] <= mem_max_x]
                        if m_words:
                            membership_text = "".join([mw[4] for mw in m_words]).strip()
                            membership_right_edge = max(mw[2] for mw in m_words)
                            
                    # Extract Grupo/Party info for bracket linking
                    grupo_text = ""
                    grupo_right_edge = None
                    if grupo_x0 is not None:
                        # Fixed safe width of 75 points (fits names and 8-digit numbers perfectly) to avoid Membership column
                        grupo_max_x = grupo_x0 + 75
                        g_words = [w2 for w2 in words if abs(w2[1] - w[1]) < 5 and (grupo_x0 - 25) <= w2[0] <= grupo_max_x]
                        if g_words:
                            grupo_text = "".join([gw[4] for gw in g_words]).strip()
                            grupo_right_edge = max(gw[2] for gw in g_words)
                        
                    extracted_rooms_membership.append({
                        "room": word_text,
                        "room_x1": w[2],
                        "color": final_color,
                        "membership": membership_text,
                        "bracket_x": membership_right_edge + 8 if membership_right_edge else (membership_x0 + 50 if membership_x0 else w[0] - 50),
                        "grupo": grupo_text,
                        "g_bracket_x": grupo_right_edge + 8 if grupo_right_edge else (grupo_x0 + 70 if grupo_x0 else w[0] - 100),
                        "page_idx": page.number,
                        "y0": w[1],
                        "y1": w[3],
                        "line_words_raw": line_words_raw,
                        "type_word": type_word,
                        "is_mvg": is_mvg_pdf,
                        "offset_x": offset_x
                    })
                        
                    total_highlights += 1

    print(f"Total highlights made: {total_highlights}")
    
    # Pass 2: Group by Membership Number per page
    from collections import defaultdict
    page_membership_groups = defaultdict(lambda: defaultdict(list))
    page_grupo_groups = defaultdict(lambda: defaultdict(list))
    
    for r in extracted_rooms_membership:
        m_num = r['membership']
        if m_num and len(m_num) >= 4: # Ignore blank or tiny memberships
            page_membership_groups[r['page_idx']][m_num].append(r)
            
        g_text = r['grupo']
        if g_text and len(g_text) >= 4:
            page_grupo_groups[r['page_idx']][g_text].append(r)
            
    # Global groupings for cross-page Super Shots
    global_membership_groups = defaultdict(list)
    global_grupo_groups = defaultdict(list)
    for r in extracted_rooms_membership:
        if r['membership'] and len(r['membership']) >= 4:
            global_membership_groups[r['membership']].append(r)
        if r['grupo'] and len(r['grupo']) >= 4:
            global_grupo_groups[r['grupo']].append(r)
            
    super_shot_memberships = set()
    for m_num, rooms in global_membership_groups.items():
        if any(r['color'] == 'green' for r in rooms) and any(r['is_mvg'] for r in rooms):
            super_shot_memberships.add(m_num)
            
    super_shot_grupos = set()
    for g_text, rooms in global_grupo_groups.items():
        if any(r['color'] == 'green' for r in rooms) and any(r['is_mvg'] for r in rooms):
            super_shot_grupos.add(g_text)
            
    # Distinct bracket colors
    bracket_colors = [
        (0.6, 0.2, 0.8), # Purple
        (0.0, 0.6, 0.6), # Teal
        (1.0, 0.5, 0.0), # Orange
        (0.9, 0.2, 0.6), # Pink
        (0.0, 0.4, 0.8), # Deep Blue
    ]
    
    # Pass 3: Draw brackets
    total_linked_groups = 0
    for page_idx, groups in page_membership_groups.items():
        page = doc[page_idx]
        color_idx = 0
        
        for m_num, rooms in groups.items():
            if len(rooms) > 1:
                # Check if group has at least one Green room
                has_green = any(r['color'] == 'green' for r in rooms)
                if has_green:
                    # Filter rooms: we only bracket rooms that are green or red
                    bracket_rooms = [r for r in rooms if r['color'] in ['green', 'red']]
                    if len(bracket_rooms) > 1:
                        total_linked_groups += 1
                        # Draw bracket for these rooms
                        min_y = min(r['y0'] for r in bracket_rooms)
                        max_y = max(r['y1'] for r in bracket_rooms)
                        
                        bracket_color = bracket_colors[color_idx % len(bracket_colors)]
                        color_idx += 1
                        
                        right_x = max(r['bracket_x'] for r in bracket_rooms)
                        
                        # Draw vertical line spanning from top room to bottom room
                        page.draw_line(fitz.Point(right_x, min_y + 5), fitz.Point(right_x, max_y - 5), color=bracket_color, width=2)
                        
                        
                        # Draw horizontal ticks pointing back to each room
                        for br in bracket_rooms:
                            mid_y = (br['y0'] + br['y1']) / 2
                            page.draw_line(fitz.Point(right_x, mid_y), fitz.Point(right_x - 8, mid_y), color=bracket_color, width=1.5)

    # Pass 3b: Draw Grupo/Party brackets
    teal_color = (0.0, 0.5, 0.5)
    for page_idx, groups in page_grupo_groups.items():
        page = doc[page_idx]
        
        for g_text, rooms in groups.items():
            if len(rooms) > 1:
                has_green = any(r['color'] == 'green' for r in rooms)
                if has_green:
                    bracket_rooms = [r for r in rooms if r['color'] in ['green', 'red']]
                    if len(bracket_rooms) > 1:
                        total_linked_groups += 1
                        min_y = min(r['y0'] for r in bracket_rooms)
                        max_y = max(r['y1'] for r in bracket_rooms)
                        
                        right_x = max(r['g_bracket_x'] for r in bracket_rooms)
                        
                        # Draw vertical line
                        page.draw_line(fitz.Point(right_x, min_y + 5), fitz.Point(right_x, max_y - 5), color=teal_color, width=2)
                        
                        # Draw horizontal ticks
                        for br in bracket_rooms:
                            mid_y = (br['y0'] + br['y1']) / 2
                            page.draw_line(fitz.Point(right_x, mid_y), fitz.Point(right_x - 8, mid_y), color=teal_color, width=1.5)

    # Pass 5: Global Super Shots
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

    # Pass 4: Draw Family Suite (F.S.) brackets
    from collections import defaultdict
    page_fsuite_groups = defaultdict(lambda: defaultdict(list))
    
    for r in f_suite_candidates:
        page_fsuite_groups[r['page_idx']][r['family_id']].append(r)
        
    for page_idx, groups in page_fsuite_groups.items():
        page = doc[page_idx]
        for fid, rooms in groups.items():
            if len(rooms) > 1:
                min_y = min(r['y0'] for r in rooms)
                max_y = max(r['y1'] for r in rooms)
                right_x = max(r['bracket_x'] for r in rooms)
                
                # Draw vertical line (bracket)
                page.draw_line(fitz.Point(right_x, min_y + 5), fitz.Point(right_x, max_y - 5), color=(0.0, 0.5, 0.0), width=2)
                
                # Draw top and bottom prongs (much longer to point clearly at the rooms)
                page.draw_line(fitz.Point(right_x - 12, min_y + 5), fitz.Point(right_x, min_y + 5), color=(0.0, 0.5, 0.0), width=2)
                page.draw_line(fitz.Point(right_x - 12, max_y - 5), fitz.Point(right_x, max_y - 5), color=(0.0, 0.5, 0.0), width=2)
                
                # Add "F.S."
                mid_y = (min_y + max_y) / 2
                page.insert_text(fitz.Point(right_x + 3, mid_y + 3), "F.S.", fontsize=10, color=(0.0, 0.5, 0.0))

    doc.save(output_path)
    doc.close()
    
    # Calculate PDF-specific stats
    pdf_promos = sum(1 for room in processed_rooms if room_data.get(room, {}).get('promo', False))
    pdf_certs = sum(1 for room in processed_rooms if room_data.get(room, {}).get('certificado', False))
    
    super_shots_mvg_list = sorted(list(set([r['room'] for group in super_shot_global_groups for r in group if r['is_mvg']])))
    super_shots_green_list = sorted(list(set([r['room'] for group in super_shot_global_groups for r in group if r['color'] == 'green'])))
    
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
        'checkouts': sorted(list(checkouts)),
        'processed_rooms_list': list(processed_rooms)
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
        # 1. Extract rooms
        rooms, duplicates = extract_rooms_from_excel(excel_path)
        if not rooms:
            return jsonify({'error': 'Could not find any room numbers in the Excel file.'}), 400
            
        # 2. Highlight PDF
        stats = highlight_pdf(pdf_path, rooms, output_pdf_path)
        
        # Filter duplicates: Only show duplicates if that room was actually found in the PDF
        processed_rooms_set = set(stats['processed_rooms_list'])
        stats['duplicates'] = [d for d in duplicates if d in processed_rooms_set]
        
        # Remove the temporary list so we don't send it to the frontend
        del stats['processed_rooms_list']
        
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
        return send_file(file_path, as_attachment=True, mimetype='application/octet-stream')
    return "File not found", 404

if __name__ == '__main__':
    # Listen on all interfaces so it can be accessed from the iPad
    app.run(host='0.0.0.0', port=5000, debug=True)
