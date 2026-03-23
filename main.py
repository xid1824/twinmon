"""
VAN/PG 모니터링 메인 컨트롤러
- 완벽한 MVC 패턴 (UI와 봇 로직 분리)
- 클립보드 오염 방지 및 중복 알람 차단
"""
import tkinter as tk
from tkinter import messagebox
import threading
import time
import os
import json

from van_monitor import SystemVanDashboard
# from golden_bot import GoldenBot  # ← 회사에서golden_bot.py 구현 후 주석 해제


class MockBot:
    """테스트용 Mock 봇"""
    def __init__(self):
        self.main_window = True  # 연결됨
    
    def execute_and_fetch(self):
        import random
        data_list = [
            """[한국스마트카드] [오전 12:01] [티머니] 타임아웃 발생
1. 기관 : 카드사(KBC)
2. 내용 : 발생건수(7)
3. 일시 : 2026/03/21 00:01
4. 기타 : """,
            """[한국스마트카드] [오후 6:07] [티머니] 중복거절 발생
1. 기관 : 카드사(BCC)
2. 내용 : 중복오류(4건)
3. 일시 : 2026/03/21 18:07
4. 기타 : L6/계좌거래불가상태""",
            """[티머니] 배치프로그램 점검!!
1. 프로그램 : BC_ProcBL
2. 설명 : 신용 현대카드 BL파일(VHBLmmdd) 처리
3. 상태 : 배치프로그램 수행 실패 !
4. 일시 : 03/22 10:29"""
        ]
        return random.choice(data_list)


class MainController:
    def __init__(self):
        self.root = tk.Tk()
        self.config = self.load_config()
        
        # 1. View (GUI) 생성
        self.app = SystemVanDashboard(self.root)
        
        # 2. 버튼 훅(Hook) 연결 (직접 함수 주입)
        self.app.on_start_cmd = self.start_bot_thread
        self.app.on_stop_cmd = self.stop_bot_thread
        
        # 3. Model (기능 봇) 생성
        # self.bot = GoldenBot()  # ← 公司 구현 후 주석 해제
        self.bot = MockBot()  # 테스트용
        
        # 제어 상태 변수
        self.is_scraping = False
        
        # 중복 방지를 위한 이전 텍스트 캐시
        self.last_fetched_text = ""
    
    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"refresh": {"interval_ms": 5000}}

    def start_bot_thread(self):
        if self.is_scraping:
            return
        
        # Golden 연결 체크 (실제 환경에서만)
        # if not self.bot.main_window:
        #     self.bot.connect_app()
        #     if not self.bot.main_window:
        #         messagebox.showerror("오류", "Golden 프로그램이 실행되지 않았습니다.")
        #         self.app.update_status("정지", "#e74c3c")
        #         return
        
        self.is_scraping = True
        self.app.is_running = True
        self.app.update_status("모니터링 가동 중", "#27ae60")
        
        t = threading.Thread(target=self.run_scraper_loop, daemon=True)
        t.start()
        
        messagebox.showinfo("안내", "모니터링을 시작합니다.")

    def stop_bot_thread(self):
        self.is_scraping = False
        self.app.is_running = False
        self.app.update_status("정지", "#e74c3c")
        
        messagebox.showinfo("안내", "모니터링을 정지합니다.")

    def run_scraper_loop(self):
        interval = self.config.get('refresh', {}).get('interval_ms', 5000) / 1000
        
        while self.is_scraping:
            try:
                # 봇에게 데이터 조회 지시
                raw_text = self.bot.execute_and_fetch()
                
                # 데이터가 있고, 이전 데이터와 다를 경우에만 UI로 전송
                if raw_text and raw_text.strip() != self.last_fetched_text.strip():
                    if len(raw_text.strip()) > 10:
                        start_seq = len(self.app.all_alarms) + 1
                        self.app.process_raw_alarm(start_seq, raw_text)
                        
                        # 새로운 데이터를 캐싱 갱신
                        self.last_fetched_text = raw_text
                
            except Exception as e:
                print(f"[스크래핑 오류] {e}")
            
            time.sleep(interval)


if __name__ == "__main__":
    controller = MainController()
    controller.root.mainloop()