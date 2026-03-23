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
        
        # 1. GUI 생성 (시작/정지 콜백 연결)
        self.app = SystemVanDashboard(self.root)
        
        # 콜백 함수 연결 (메서드 덮어쓰기 대신)
        self.app.on_start_callback = self.start_bot_thread
        self.app.on_stop_callback = self.stop_bot_thread
        
        # 버튼 커맨드 덮어쓰기
        # van_monitor의 on_start/on_stop을 직접 호출하는 대신
        # 콜백을 실행하도록 수정
        for widget in self.app.root.winfo_children():
            if isinstance(widget, tk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, tk.Button):
                        if child.cget("text") == "관제 시작":
                            child.config(command=self.start_bot_thread)
                        elif child.cget("text") == "관제 정지":
                            child.config(command=self.stop_bot_thread)
        
        # 2. Golden 긁어오기 봇 (회사에서 구현)
        # from golden_scraper import GoldenBot  # ← 公司에서 작성
        # self.bot = GoldenBot()
        
        # 임시 mock (테스트용)
        self.bot = MockScraper()
        
        self.is_scraping = False
        self.seq_counter = 1

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
        self.app.update_status("관제 가동 중", "#27ae60")
        
        # 백그라운드 스레드 실행 (GUI 방 froze 방지)
        t = threading.Thread(target=self.run_scraper_loop, daemon=True)
        t.start()

    def stop_bot_thread(self):
        """스크래퍼 정지"""
        self.is_scraping = False
        self.app.is_running = False
        self.app.update_status("정지", "#e74c3c")

    def run_scraper_loop(self):
        """데이터 스크래핑 무한 루프"""
        interval = self.config.get('refresh', {}).get('interval_ms', 5000) / 1000  # ms → sec
        
        while self.is_scraping:
            try:
                # 1. Golden 프로그램에서 데이터 긁어옴
                raw_text = self.bot.get_latest_data()
                
                if raw_text:
                    # 2. 기존 alarm 수부터 시작 (중복 방지)
                    start_seq = len(self.app.all_alarms) + 1
                    
                    # 3. GUI 처리 함수로 전달
                    self.app.process_raw_alarm(start_seq, raw_text)
                
            except Exception as e:
                print(f"[스크래핑 오류] {e}")
            
            # interval 대기
            time.sleep(interval)


class MockScraper:
    """테스트용 Mock 스크래퍼"""
    def __init__(self):
        self.count = 0
    
    def get_latest_data(self):
        """테스트용 샘플 데이터 반환"""
        self.count += 1
        
        if self.count % 3 == 0:
            # 미등록 알림 테스트
            return """
[한국스마트카드] [오후 3:30] [티머니] 시스템 점검 안내
1. 제목 : 정기 점검
2. 내용 : 새벽 2시 시스템 점검이 있습니다
3. 일시 : 2026/03/21 15:30
4. 기타 : .
"""
        elif self.count % 2 == 0:
            return """
[한국스마트카드] [오후 6:07] [티머니] 중복거절 발생
1. 기관 : 카드사(BCC)
2. 내용 : 중복오류(4건)
3. 일시 : 2026/03/21 18:07
4. 기타 : L6/계좌거래불가상태
"""
        else:
            return """
[한국스마트카드] [오전 12:01] [티머니] 타임아웃 발생
1. 기관 : 카드사(KBC)
2. 내용 : 발생건수(7)
3. 일시 : 2026/03/21 00:01
4. 기타 :
"""


if __name__ == "__main__":
    controller = MainController()
    controller.root.mainloop()
