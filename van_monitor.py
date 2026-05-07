"""
VAN/PG 모니터링 대시보드 v1.2
- MVC 패턴 적용 (UI 렌더링 독립)
- 트레이 아이콘 기능 포함
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import time
import threading

# pystray → 선택적 import (트레이 미사용 시 오류 방지)
try:
    import pystray
    from PIL import Image, ImageDraw
    PYTRAY_AVAILABLE = True
except ImportError:
    PYTRAY_AVAILABLE = False


class SystemVanDashboard:
    def __init__(self, root):
        self.root = root
        self.config = self.load_config()
        
        self.root.title(f"{self.config['app_name']} v{self.config['version']}")
        self.root.geometry(f"{self.config['window']['width']}x{self.config['window']['height']}")
        
        # 메인 컨트롤러와 연결될 콜백 함수 (Main에서 덮어 씌움)
        self.on_start_cmd = None
        self.on_stop_cmd = None
        
        self.is_running = False
        self.is_paused = tk.BooleanVar(value=False)
        self.noti_type = tk.StringVar(value="toast")
        
        self.all_alarms = []
        self.snoozed_alarms = {}
        
        self.setup_ui()
        self.setup_shortcuts()
        
        # X 버튼 누를 때 트레이로 숨기기 이벤트 연결
        self.root.protocol('WM_DELETE_WINDOW', self.hide_to_tray)
        
        if self.config['refresh']['auto_start']:
            self.auto_refresh()
    
    # ---------------- 설정 로드 ----------------
    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "app_name": "VAN/PG 모니터링 대시보드", "version": "1.2.0",
            "org_list": ["전체", "KBC", "BCC", "HDC", "SHC", "HNC", "SSC"],
            "alarm_types": ["전체", "타임아웃", "지연응답", "회원사장애", "중복거절", "배치"],
            "refresh": {"interval_ms": 5000, "auto_start": True},
            "shortcuts": {"start_monitoring": "F5", "stop_monitoring": "F6", "test_data": "F7", "toggle_pause": "Ctrl+P"},
            "window": {"width": "1200", "height": "600"}
        }

    # ---------------- UI 구성 ----------------
    def setup_ui(self):
        # 1. 상단 상태바
        status_frame = tk.Frame(self.root, bg="#2c3e50", pady=5)
        status_frame.pack(fill="x")
        
        tk.Label(status_frame, text=f"[ {self.config['app_name']} ]", 
                bg="#2c3e50", fg="white", font=("맑은 고딕", 11, "bold")).pack(side="left", padx=10)
        
        self.status_label = tk.Label(status_frame, text="정지", 
                bg="#2c3e50", fg="#e74c3c", font=("맑은 고딕", 10, "bold"))
        self.status_label.pack(side="left", padx=10)
        
        shortcut_text = f"시작:{self.config['shortcuts'].get('start_monitoring', 'F5')} | "
        shortcut_text += f"정지:{self.config['shortcuts'].get('stop_monitoring', 'F6')} | "
        shortcut_text += f"일시정지:{self.config['shortcuts'].get('toggle_pause', 'Ctrl+P')}"
        
        tk.Label(status_frame, text=shortcut_text, 
                bg="#2c3e50", fg="#bdc3c7", font=("Consolas", 9)).pack(side="right", padx=10)

        # 2. 제어 패널
        ctrl_frame = tk.Frame(self.root, pady=10)
        ctrl_frame.pack(fill="x", padx=10)
        
        tk.Button(ctrl_frame, text="모니터링 시작", width=12, command=self.on_start, bg="#27ae60", fg="white").pack(side="left", padx=5)
        tk.Button(ctrl_frame, text="모니터링 정지", width=12, command=self.on_stop, bg="#e74c3c", fg="white").pack(side="left", padx=5)
        tk.Button(ctrl_frame, text="테스트 데이터", width=15, command=self.receive_test_data).pack(side="left", padx=20)
        
        chk_pause = tk.Checkbutton(ctrl_frame, text="알람 팝업 일시정지", 
                variable=self.is_paused, fg="#e67e22", font=("맑은 고딕", 10, "bold"))
        chk_pause.pack(side="right", padx=10)
        
        radio_frame = tk.Frame(ctrl_frame)
        radio_frame.pack(side="right", padx=20)
        tk.Radiobutton(radio_frame, text="토스트", variable=self.noti_type, value="toast").pack(side="left")
        tk.Radiobutton(radio_frame, text="팝업", variable=self.noti_type, value="popup").pack(side="left")
        tk.Radiobutton(radio_frame, text="끄기", variable=self.noti_type, value="log_only").pack(side="left")

        # 3. 필터링 영역
        filter_frame = tk.LabelFrame(self.root, text="장애 알람 필터링", padx=10, pady=10)
        filter_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(filter_frame, text="장애 유형:").pack(side="left", padx=5)
        self.combo_type = ttk.Combobox(filter_frame, values=self.config['alarm_types'], width=15, state="readonly")
        self.combo_type.current(0)
        self.combo_type.pack(side="left", padx=5)
        
        tk.Label(filter_frame, text="대상 기관:").pack(side="left", padx=15)
        self.combo_org = ttk.Combobox(filter_frame, values=self.config['org_list'], width=10, state="readonly")
        self.combo_org.current(0)
        self.combo_org.pack(side="left", padx=5)
        
        tk.Button(filter_frame, text="조회 적용", width=12, command=self.apply_filter).pack(side="left", padx=20)
        tk.Button(filter_frame, text="차단 목록", width=12, command=self.show_snoozed_list).pack(side="right", padx=5)

        # 4. Notebook (탭 구조)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # ----- 탭 1: 장애 알람 -----
        tab_alarm = ttk.Frame(self.notebook)
        self.notebook.add(tab_alarm, text='[장애 알람 모니터링]')
        
        columns = ("seq", "time", "type", "org", "details")
        self.tree = ttk.Treeview(tab_alarm, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("seq", text="No")
        self.tree.heading("time", text="발생 일시")
        self.tree.heading("type", text="장애 유형")
        self.tree.heading("org", text="발생 기관")
        self.tree.heading("details", text="상세 내용")
        
        self.tree.column("seq", width=50, anchor="center")
        self.tree.column("time", width=150, anchor="center")
        self.tree.column("type", width=130, anchor="center")
        self.tree.column("org", width=80, anchor="center")
        self.tree.column("details", width=500, anchor="w")
        
        vsb = ttk.Scrollbar(tab_alarm, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(fill="both", expand=True)
        
        self.tree.tag_configure("심각", background="#ffcccc") 
        self.tree.tag_configure("경고", background="#ffd9b3") 
        self.tree.tag_configure("주의", background="#ffffcc") 
        
        self.build_context_menu()
        self.tree.bind("<Double-1>", self.on_double_click)
        
        # ----- 탭 2: 파일/배치 모니터링 (main.py에서 주입) -----
        self.tab_file_batch = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_file_batch, text='[파일/배치 모니터링]')
        
        # 트레이 아이콘 변수
        self.tray_icon = None

    # ---------------- 트레이 아이콘 기능 ----------------
    def hide_to_tray(self):
        """창을 트레이로 숨기기"""
        self.root.withdraw()
        if self.noti_type.get() != "log_only":
            self.show_toast("시스템 트레이에서 백그라운드 모니터링을 유지합니다.")
        if PYTRAY_AVAILABLE and getattr(self, 'tray_icon', None) is None:
            self.create_tray_icon()

    def create_tray_icon(self):
        """트레이 아이콘 생성"""
        try:
            image = Image.new('RGB', (64, 64), color=(44, 62, 80))
            d = ImageDraw.Draw(image)
            d.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
            
            menu = pystray.Menu(
                pystray.MenuItem("대시보드 열기", self.show_from_tray, default=True),
                pystray.MenuItem("완전 종료", self.quit_from_tray)
            )
            
            self.tray_icon = pystray.Icon("VAN_Monitor", image, "VAN/PG 모니터링", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"[트레이 아이콘 오류] {e}")

    def show_from_tray(self, icon=None, item=None):
        """트레이에서 창 복원"""
        if hasattr(self, 'tray_icon') and self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.deiconify)

    def quit_from_tray(self, icon=None, item=None):
        """트레이에서 완전 종료"""
        if hasattr(self, 'tray_icon') and self.tray_icon is not None:
            self.tray_icon.stop()
        self.is_running = False
        self.root.quit()

    # ---------------- 단축키 ----------------
    def setup_shortcuts(self):
        shortcuts = self.config.get('shortcuts', {})
        
        key_mappings = {
            "start_monitoring": self.on_start,
            "stop_monitoring": self.on_stop,
            "test_data": self.receive_test_data,
            "toggle_pause": self.toggle_pause,
        }
        
        for name, func in key_mappings.items():
            key = shortcuts.get(name, "")
            if key:
                tk_key = key.replace("Ctrl+", "Control-").replace("Shift+", "Shift-").replace("Alt+", "Alt-")
                if "Control-" in tk_key or "Alt-" in tk_key or "Shift-" in tk_key:
                    parts = tk_key.split("-")
                    tk_key = f"{parts[0]}-{parts[1].lower()}"
                try:
                    self.root.bind(f"<{tk_key}>", lambda e, f=func: f())
                except Exception as e:
                    pass

    # ---------------- 컨텍스트 메뉴 ----------------
    def build_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        
        snooze_menu = tk.Menu(self.context_menu, tearoff=0)
        for mins in self.config.get('snooze', {}).get('options', [5, 10, 30, 60]):
            snooze_menu.add_command(label=f"{mins}분간 차단", 
                    command=lambda m=mins: self.snooze_selected_alarm(m))
        
        self.context_menu.add_cascade(label="알림 차단", menu=snooze_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="상세 보기", command=self.show_alarm_details)
        
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def toggle_pause(self):
        self.is_paused.set(not self.is_paused.get())
        status = "일시정지 중" if self.is_paused.get() else "모니터링 가동 중"
        self.update_status(status, "#e67e22" if self.is_paused.get() else "#27ae60")

    def update_status(self, text, color="#e74c3c"):
        self.status_label.config(text=text, fg=color)

    def snooze_selected_alarm(self, minutes):
        selected = self.tree.selection()
        if not selected:
            return
        item_values = self.tree.item(selected[0], "values")
        alarm_type, alarm_org = item_values[2], item_values[3]
        
        snooze_key = f"{alarm_type}_{alarm_org}"
        self.snoozed_alarms[snooze_key] = time.time() + (minutes * 60)
        
        messagebox.showinfo("알림 차단", f"[{alarm_type}] - [{alarm_org}] 알림이 {minutes}분간 차단됩니다.")

    def show_snoozed_list(self):
        current_time = time.time()
        active_snoozes = {k: v for k, v in self.snoozed_alarms.items() if v > current_time}
        
        if not active_snoozes:
            messagebox.showinfo("차단 목록", "현재 차단된 알람이 없습니다.")
            return
        
        msg = "현재 차단된 알람:\n\n"
        for key, expiry in active_snoozes.items():
            remain_min = int((expiry - current_time) / 60)
            msg += f"- {key} (약 {remain_min}분 남음)\n"
        
        if messagebox.askyesno("차단 목록", msg + "\n모든 차단을 해제하시겠습니까?"):
            self.snoozed_alarms.clear()

    # ---------------- 상세창 ----------------
    def show_alarm_details(self):
        selected = self.tree.selection()
        if not selected:
            return
        
        item_values = self.tree.item(selected[0], "values")
        alarm_time, alarm_type, alarm_org, alarm_details = item_values[1], item_values[2], item_values[3], item_values[4]
        
        detail_win = tk.Toplevel(self.root)
        detail_win.title("장애 알람 상세 리포트")
        detail_win.geometry("500x380")
        detail_win.configure(bg="#f8f9fa")
        detail_win.grab_set()
        
        header_frame = tk.Frame(detail_win, bg="#2c3e50", height=60)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text=f"[{alarm_type}] 상세 리포트", 
                bg="#2c3e50", fg="white", font=("맑은 고딕", 13, "bold")).pack(side="left", padx=20, pady=15)
        
        content_frame = tk.Frame(detail_win, bg="white", padx=25, pady=20)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        info_font = ("맑은 고딕", 11)
        tk.Label(content_frame, text=f"발생 일시 : {alarm_time}", bg="white", font=info_font).pack(anchor="w", pady=4)
        tk.Label(content_frame, text=f"발생 기관 : {alarm_org}", bg="white", font=info_font).pack(anchor="w", pady=4)
        
        tk.Frame(content_frame, bg="#e9ecef", height=2).pack(fill="x", pady=15)
        
        tk.Label(content_frame, text="상세 내용", bg="white", 
                font=("맑은 고딕", 10, "bold"), fg="#7f8c8d").pack(anchor="w", pady=(0,5))
        
        detail_text = tk.Text(content_frame, wrap="word", height=4, font=("맑은 고딕", 11), 
                bg="#f1f3f5", fg="#2d3436", relief="flat", padx=15, pady=15)
        detail_text.pack(fill="both", expand=True)
        detail_text.insert(tk.END, alarm_details)
        detail_text.config(state=tk.DISABLED)
        
        btn_frame = tk.Frame(detail_win, bg="#f8f9fa")
        btn_frame.pack(fill="x", pady=(0, 20))
        
        tk.Button(btn_frame, text="이 기관/유형 10분 차단", bg="#e67e22", fg="white", relief="flat", 
                font=("맑은 고딕", 10, "bold"), padx=10, pady=5, cursor="hand2",
                command=lambda: [self.snooze_specific_alarm(alarm_type, alarm_org, 10), detail_win.destroy()]).pack(side="left", padx=20)
        
        tk.Button(btn_frame, text="닫기", bg="#95a5a6", fg="white", relief="flat", 
                font=("맑은 고딕", 10, "bold"), width=10, pady=5, cursor="hand2",
                command=detail_win.destroy).pack(side="right", padx=20)

    def on_double_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.show_alarm_details()

    def snooze_specific_alarm(self, alarm_type, alarm_org, minutes):
        snooze_key = f"{alarm_type}_{alarm_org}"
        self.snoozed_alarms[snooze_key] = time.time() + (minutes * 60)
        
        if self.noti_type.get() != "log_only":
            self.show_toast(f"[{alarm_type}] - [{alarm_org}]\n알림이 {minutes}분간 차단되었습니다.")

    # ---------------- 백엔드 로직 ----------------
    def process_raw_alarm(self, seq_no, raw_text):
        parsed_data = self.parse_text(seq_no, raw_text)
        self.all_alarms.append(parsed_data)
        
        if parsed_data.get("is_unknown", False):
            self.handle_unknown_alarm(parsed_data)
        
        self.apply_filter()
        
        if self.is_paused.get() or self.noti_type.get() == "log_only":
            return
        
        alarm_key = f"{parsed_data['type']}_{parsed_data['org']}"
        if parsed_data.get("is_unknown", False):
            alarm_key = f"UNKNOWN_{parsed_data['org']}"
        
        if alarm_key in self.snoozed_alarms:
            if time.time() < self.snoozed_alarms[alarm_key]:
                return
            else:
                del self.snoozed_alarms[alarm_key]
        
        msg = f"[{parsed_data['type']}] {parsed_data['org']}\n{parsed_data['details']}"
        if parsed_data.get("is_unknown", False):
            msg = f"[미등록 알림] {parsed_data.get('suggested_type', 'UNKNOWN')}\n{parsed_data['details']}"
        
        if self.noti_type.get() == "toast":
            self.show_toast(msg)
        elif self.noti_type.get() == "popup":
            self.show_popup(msg)

    def parse_text(self, seq_no, raw_text):
        import re
        from datetime import datetime
        
        parsed = {"seq": seq_no, "time": "", "type": "기타", "org": "-", 
                 "details": "", "raw_text": raw_text, "is_unknown": False, "suggested_type": None}
        
        patterns = self.config.get('regex_patterns', {})
        alarm_patterns = patterns.get('alarm_type', {})
        
        # 알람 유형 판별
        detected_type = None
        for type_name, pattern in alarm_patterns.items():
            if re.search(pattern, raw_text):
                detected_type = type_name
                break
        
        if detected_type:
            parsed["type"] = detected_type
        else:
            parsed["type"] = "UNKNOWN"
            parsed["is_unknown"] = True
            unknown_match = re.search(r'\[티머니\]\s*([^\n]+)', raw_text)
            if unknown_match:
                parsed["suggested_type"] = unknown_match.group(1).strip()

        # 배치 vs 온라인 분기
        is_batch = "배치" in parsed["type"] or "배치프로그램" in raw_text

        if is_batch:
            prog_match = re.search(r'1\.\s*프로그램\s*:\s*([^\n]+)', raw_text)
            desc_match = re.search(r'2\.\s*설명\s*:\s*([^\n]+)', raw_text)
            stat_match = re.search(r'3\.\s*상태\s*:\s*([^\n]+)', raw_text)
            time_match = re.search(r'4\.\s*일시\s*:\s*([^\n]+)', raw_text)

            parsed["org"] = prog_match.group(1).strip() if prog_match else "내부배치"
            
            details_list = []
            if desc_match: details_list.append(desc_match.group(1).strip())
            if stat_match: details_list.append(stat_match.group(1).strip())
            parsed["details"] = " / ".join(details_list)

            if time_match:
                time_str = time_match.group(1).strip()
                if len(time_str) <= 11:
                    time_str = f"{datetime.now().year}/{time_str}"
                parsed["time"] = time_str
        else:
            # 온라인 파싱
            org_patterns = patterns.get('org_code', {})
            detected_org = None
            for org_name, pattern in org_patterns.items():
                if re.search(pattern, raw_text):
                    detected_org = org_name
                    break
            if detected_org:
                parsed["org"] = detected_org
            
            time_match = re.search(patterns.get('time', r'(3\.\s*일시\s*:\s*|일시\s*:\s*)([^\n]+)'), raw_text)
            if time_match:
                parsed["time"] = time_match.group(2).strip()
            
            details_match = re.search(patterns.get('details', r'2\.\s*내용\s*:\s*([^\n]+)'), raw_text)
            if details_match:
                parsed["details"] = details_match.group(1).strip()
            
            etc_match = re.search(r'4\.\s*기타\s*:\s*([^\n]*)', raw_text)
            if etc_match and etc_match.group(1).strip():
                etc_content = etc_match.group(1).strip()
                parsed["details"] = f"{parsed['details']} / {etc_content}" if parsed["details"] else etc_content
        
        if not parsed["time"]:
            parsed["time"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        
        return parsed

    def handle_unknown_alarm(self, parsed):
        suggested = parsed.get('suggested_type', 'UNKNOWN')
        
        if not hasattr(self, 'unknown_alarms'):
            self.unknown_alarms = []
        self.unknown_alarms.append({"seq": parsed["seq"], "time": parsed["time"], "suggested_type": suggested})
        
        msg = f"[미등록 알림 감지] 유형: {suggested}\nconfig.json에 패턴 추가가 필요합니다.\n내용: {parsed['details']}"
        
        if self.is_paused.get() or self.noti_type.get() == "log_only":
            return
        if self.noti_type.get() == "toast":
            self.show_toast(msg)
        elif self.noti_type.get() == "popup":
            self.show_popup(msg)

    def apply_filter(self):
        f_type = self.combo_type.get()
        f_org = self.combo_org.get()
        
        selected_seq = None
        if self.tree.selection():
            selected_seq = self.tree.item(self.tree.selection()[0], "values")[0]
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        severity_map = self.config.get('severity_mapping', 
            {"타임아웃": "심각", "지연응답": "주의", "회원사장애": "경고", "중복거절": "주의", "배치": "경고"})
        
        item_to_select = None
        for alarm in reversed(self.all_alarms):
            if f_type != "전체" and f_type not in alarm["type"]:
                continue
            if f_org != "전체" and f_org not in alarm["org"]:
                continue
            
            tag = "심각" if alarm.get("is_unknown", False) else severity_map.get(alarm["type"], "주의")
            
            inserted_item = self.tree.insert("", tk.END, 
                values=(alarm["seq"], alarm["time"], alarm["type"], alarm["org"], alarm["details"]), tags=(tag,))
            
            if str(alarm["seq"]) == str(selected_seq):
                item_to_select = inserted_item

        if item_to_select:
            self.tree.selection_set(item_to_select)

    def show_toast(self, message):
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.geometry(f"300x80+{self.root.winfo_screenwidth() - 320}+{self.root.winfo_screenheight() - 130}")
        toast.configure(bg="#e74c3c")
        tk.Label(toast, text=message, fg="white", bg="#e74c3c", 
                font=("맑은 고딕", 10), justify="left").pack(expand=True, fill="both", padx=10, pady=10)
        toast.after(3500, toast.destroy)

    def show_popup(self, message):
        messagebox.showwarning("운영 시스템 경고", message)

    # ---------------- 콜백 위임 ----------------
    def on_start(self):
        if self.on_start_cmd:
            self.on_start_cmd()

    def on_stop(self):
        if self.on_stop_cmd:
            self.on_stop_cmd()

    def auto_refresh(self):
        interval = self.config.get('refresh', {}).get('interval_ms', 5000)
        self.apply_filter()
        self.root.after(interval, self.auto_refresh)

    def receive_test_data(self):
        seq = len(self.all_alarms) + 1
        
        raw_text_1 = """
[한국스마트카드] [오전 12:01] [티머니] 타임아웃 발생
1. 기관 : 카드사(KBC)
2. 내용 : 발생건수(7)
3. 일시 : 2026/03/21 00:01
4. 기타 :
"""
        raw_text_2 = """
[한국스마트카드] [오후 6:07] [티머니] 중복거절 발생
1. 기관 : 카드사(BCC)
2. 내용 : 중복오류(4건)
3. 일시 : 2026/03/21 18:07
4. 기타 : L6/계좌거래불가상태
"""
        raw_text_unknown = """
[한국스마트카드] [오후 3:30] [티머니] 시스템 점검 안내
1. 제목 : 정기 점검
2. 내용 : 새벽 2시 시스템 점검이 있습니다
3. 일시 : 2026/03/21 15:30
4. 기타 : .
"""
        raw_text_batch = """
[티머니] 배치프로그램 점검!!
1. 프로그램 : BC_ProcBL
2. 설명 : 신용 현대카드 BL파일(VHBLmmdd) 처리
3. 상태 : 배치프로그램 수행 실패 !
4. 일시 : 03/22 10:29
"""
        
        self.process_raw_alarm(seq, raw_text_1)
        self.process_raw_alarm(seq+1, raw_text_2)
        self.process_raw_alarm(seq+2, raw_text_unknown)
        self.process_raw_alarm(seq+3, raw_text_batch)


if __name__ == "__main__":
    root = tk.Tk()
    app = SystemVanDashboard(root)
    root.mainloop()