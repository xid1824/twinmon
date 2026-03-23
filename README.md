# VAN/PG 모니터링 대시보드

## 📁 파일 구조
```
twinoper/
├── van_monitor.py   # 메인 프로그램
├── config.json      # 설정 파일
└── README.md        # 사용 가이드
```

## 🚀 실행 방법
```bash
python van_monitor.py
```

## ⚙️ 설정 (config.json)

### 단축키 변경
```json
"shortcuts": {
    "start_monitoring": "F5",
    "stop_monitoring": "F6", 
    "test_data": "F7",
    "toggle_pause": "Ctrl+P"
}
```

### 기관 목록 변경
```json
"org_list": ["전체", "KBC", "BCC", "HDC", "SHC", "HNC", "SSC"]
```

### 자동 새로고침 간격
```json
"refresh": {
    "interval_ms": 5000,  // 5초
    "auto_start": true
}
```

## ⌨️ 기본 단축키

| 동작 | 단축키 |
|------|--------|
| 관제 시작 | F5 |
| 관제 정지 | F6 |
| 테스트 데이터 | F7 |
| 일시정지 토글 | Ctrl+P |
| 종료 | Ctrl+Q |

## 🎨 UI 구성

1. **상단 상태바**: 단축키 표시 + 현재 상태
2. **제어 패널**: 시작/정지/일시정지
3. **필터 영역**: 장애 유형 + 기관 선택
4. **데이터 그리드**: 알람 목록 (심각/경고/주의 색상)

## 🖱️ 우클릭 메뉴

- 5분간 차단
- 10분간 차단
- 30분간 차단
- 60분간 차단
- 상세 보기

## 📦 주요 파일

| 파일 | 설명 |
|------|------|
| `van_monitor.py` | GUI 메인 프로그램 |
| `config.json` | 정규식, 기관, 알람 유형 설정 |
| `main.py` | 컨트롤러 (스레드, 콜백 연동) |
| `README.md` | 사용 가이드 |

## 🏢 회사 연동 가이드

Golden 프로그램을 연동하려면:

1. **golden_scraper.py** 파일 생성 (公司에서 작성)
```python
class GoldenBot:
    def get_latest_data(self):
        # pywinauto로 Golden 윈도우에서 데이터 긁어옴
        return raw_text  # van_monitor 형식
```

2. **main.py**에서 import 추가
```python
from golden_scraper import GoldenBot
self.bot = GoldenBot()
```

## 📝 정규식 패턴 추가 (config.json)

신규 알림 유형이 등록되면:
1. config.json의 `regex_patterns.alarm_type`에 패턴 추가
2. `severity_mapping`에 중요도 추가

---
**v1.1.0** - 2026.03.21
