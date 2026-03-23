"""
Golden 프로그램 데이터 추출 봇
- 클립보드를 사용하지 않고 직접 Edit 컨트롤에서 텍스트를 빼옵니다.
- pywinauto 필요: pip install pywinauto
"""
import time
import pywinauto
from pywinauto.application import Application


class GoldenBot:
    def __init__(self):
        self.main_window = None
        self.app = None
        # self.connect_app()  # 생성자에서 자동 연결 않하고 수동 호출 권장
    
    def connect_app(self):
        """Golden 프로그램 연결"""
        try:
            # 회사 환경에 맞게 프로세스명이나 타이틀 정규식을 수정하세요.
            # 예: "Golden" 또는 "GOLDEN" 또는 partial matching
            self.app = Application(backend="uia").connect(title_re=".*[Gg]olden.*")
            self.main_window = self.app.top_window()
            print("[Bot] Golden 연결 성공!")
            return True
        except pywinauto.findwindows.ElementNotFoundError:
            print("[Bot] Golden 프로그램을 찾을 수 없습니다.")
            self.main_window = None
            return False
        except Exception as e:
            print(f"[Bot] 연결 중 오류 발생: {e}")
            self.main_window = None
            return False

    def execute_and_fetch(self):
        """F5 실행 후 결과 텍스트 추출 (클립보드 미사용)"""
        if not self.main_window:
            if not self.connect_app():
                return None

        try:
            # 1. 쿼리 실행 (단축키가 F5라고 가정)
            self.main_window.send_keys('{F5}')
            
            # DB 조회 대기 시간 (환경에 따라 조정)
            time.sleep(1.5)
            
            # 2. 결과 텍스트 추출 (클립보드 복사 X)
            # 회사 PC 환경에서 print_control_identifiers() 돌렸을 때 나온
            # 타겟 Edit 박스의 정확한 found_index 번호를 넣어주세요.
            # 예: found_index=0 또는 found_index=1
            result_edit = self.main_window.child_window(control_type="Edit", found_index=1)
            raw_text = result_edit.window_text()
            
            return raw_text

        except Exception as e:
            print(f"[Bot] 데이터 조회 및 추출 중 에러 발생: {e}")
            return None

    def disconnect(self):
        """연결 해제"""
        if self.app:
            self.app.detach()
            self.main_window = None
            print("[Bot] Golden 연결 해제")


# ==========================================
# 테스트 실행 (회사 환경에서만)
# ==========================================
if __name__ == "__main__":
    bot = GoldenBot()
    
    # 연결 테스트
    if bot.connect_app():
        # 데이터 추출 테스트
        result = bot.execute_and_fetch()
        if result:
            print(f"\n[결과 데이터]\n{result[:500]}...")
        else:
            print("[결과] 데이터가 없습니다.")
    else:
        print("[테스트] Golden 프로그램을 먼저 실행하세요.")