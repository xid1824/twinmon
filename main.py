"""
VAN/PG 모니터링 메인 컨트롤러
- GUI (van_monitor) + 기능 로직 (GoldenBot) 연동
- threading으로 GUI 방 froze 방지
"""
import tkinter as tk
import threading
import time
import os
import json

# GUI 모듈 임포트
from van_monitor import SystemVanDashboard


class MainController:
    def __init__(self):
        self.root = tk.Tk()
        
        # 설정 로드 (interval_ms 등)
        self.config = self.load_config()
        
        # GUI 생성
        self.app = SystemVanDashboard(self.root)
        
        # 버튼 커맨드 연결 (스레드 시작/정지)
        for widget in self.app.root.winfo_children():
            if isinstance(widget, tk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, tk.Button):
                        if child.cget("text") == "관제 시작":
                            child.config(command=self.start_bot_thread)
                        elif child.cget("text") == "관제 정지":
                            child.config(command=self.stop_bot_thread)
        
        # Golden 스크래퍼 (公司에서 구현)
        # from golden_scraper import GoldenBot
        # self.bot = GoldenBot()
        
        self.is_scraping = False

    def load_config(self):
        """config.json 로드"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"refresh": {"interval_ms": 5000}}

    def start_bot_thread(self):
        """백그라운드에서 스크래퍼 실행"""
        if self.is_scraping:
            return
        
        self.is_scraping = True
        self.app.is_running = True
        self.app.update_status("모니터링 가동 중", "#27ae60")
        
        t = threading.Thread(target=self.run_scraper_loop, daemon=True)
        t.start()

    def stop_bot_thread(self):
        """스크래퍼 정지"""
        self.is_scraping = False
        self.app.is_running = False
        self.app.update_status("정지", "#e74c3c")

    def run_scraper_loop(self):
        """데이터 스크래핑 무한 루프"""
        interval = self.config.get('refresh', {}).get('interval_ms', 5000) / 1000
        
        while self.is_scraping:
            try:
                raw_text = self.bot.get_latest_data()
                
                if raw_text:
                    start_seq = len(self.app.all_alarms) + 1
                    self.app.process_raw_alarm(start_seq, raw_text)
                
            except Exception as e:
                print(f"[스크래핑 오류] {e}")
            
            time.sleep(interval)


if __name__ == "__main__":
    controller = MainController()
    controller.root.mainloop()
