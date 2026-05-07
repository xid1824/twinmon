# VAN/PG 모니터링 대시보드

## 📁 파일 구조
```
twinoper/
├── van_monitor.py          # GUI 메인 프로그램
├── main.py                 # 컨트롤러 (스레드, 콜백 연동)
├── config.json             # 설정 파일 (테이블 정의, 단축키 등)
├── batch_mapping.json      # 파일-배치 연관 매핑 (자동 생성)
├── file_batch_monitor.py    # 파일/배치 모니터링 모듈
├── golden_bot.py           # Golden7 연동 봇 (회사 구현용)
├── README.md                # 사용 가이드
└── TESTING.md              # 테스트 가이드
```

## 🚀 실행 방법

```bash
python main.py
```

---

## ⚙️ config.json 설정 구조

### 1. 파일/배치 테이블 정의 (file_table, batch_table)
```json
{
    "file_table": {
        "table_name": "FILE_TRANSFER_LOG",
        "columns": {
            "COL001": {"label": "File ID", "width": 100},
            "COL002": {"label": "File Name", "width": 250},
            "COL003": {"label": "File Kind", "width": 80},
            "COL004": {"label": "Deadline", "width": 120},
            "COL005": {"label": "Status", "width": 80}
        }
    },
    "batch_table": {
        "table_name": "BATCH_SCHEDULE",
        "columns": {
            "COL001": {"label": "Batch ID", "width": 100},
            "COL002": {"label": "Batch Name", "width": 200},
            "COL003": {"label": "Cycle", "width": 80},
            "COL004": {"label": "Dependency", "width": 100},
            "COL005": {"label": "Status", "width": 80}
        }
    },
    "scrape": {
        "refresh_interval_sec": 5,
        "pause_on_activity_sec": 10
    }
}
```

### 2. 단축키 변경
```json
"shortcuts": {
    "start_monitoring": "F5",
    "stop_monitoring": "F6",
    "test_data": "F7",
    "toggle_pause": "Ctrl+P"
}
```

### 3. 기관 목록 변경
```json
"org_list": ["전체", "KBC", "BCC", "HDC", "SHC", "HNC", "SSC"]
```

---

## 🗂️ UI 구성 (Notebook 탭)

### 탭 1: 장애 알람 모니터링
- 기존 VAN/PG 장애 알람 실시간 모니터링
- 필터링 (유형, 기관), 우클릭 메뉴 (차단, 상세 보기)
- Treeview 색상: 심각(빨강), 경고(주황), 주의(노랑)

### 탭 2: 파일/배치 모니터링
- 좌측: 파일 목록 (Golden7 그리드 복사 기반)
- 우측: 배치 목록
- 중앙: [Link] / [Unlink] 버튼
- Golden7에서 클립보드 복사 후 자동으로 파싱 렌더링
- 사용자 클릭 시 10초 대기 트리거 (중복 방지)

---

## 🔄 데이터 흐름 (파일/배치 모니터링)

```
[Golden7 Grid]
    → (Ctrl+C 복사)
    → [GridParser.validate_clipboard()] ← 헤더 검증
    → [GridParser.parse_clipboard()]    ← 탭 분리 파싱
    → [merge_with_mapping()]           ← batch_mapping.json 병합
    → [queue.Queue]                    ← Thread-Safe 전달
    → [FileBatchTreeview.update_*_tree()] ← Upsert 렌더링
```

---

## ⌨️ 기본 단축키

| 동작 | 단축키 |
|------|--------|
| 관제 시작 | F5 |
| 관제 정지 | F6 |
| 테스트 데이터 | F7 |
| 일시정지 토글 | Ctrl+P |
| 종료 | Ctrl+Q |

---

## 🖱️ 우클릭 메뉴 (장애 알람)

- 5분간 차단
- 10분간 차단
- 30분간 차단
- 60분간 차단
- 상세 보기

---

## 📦 주요 파일 설명

| 파일 | 설명 |
|------|------|
| `van_monitor.py` | Tkinter GUI (SystemVanDashboard 클래스) |
| `main.py` | MainController (스레드 관리, 콜백 연동) |
| `file_batch_monitor.py` | ConfigManager, GridParser, FileBatchTreeview, ScrapeController |
| `config.json` | 정규식, 컬럼 정의, 단축키 설정 |
| `batch_mapping.json` | 파일-배치 연관 매핑 (자동 저장) |
| `golden_bot.py` | Golden7 연동 봇 (회사 구현용) |

---

## 🏢 Golden7 연동 가이드

### 1. golden_bot.py 구현 (회사 보안 상 별도 배포)
```python
class GoldenBot:
    def connect_app(self):
        # pywinauto로 Golden 프로그램 연결
        pass
    
    def execute_and_fetch(self):
        # 쿼리 실행 후 Edit 컨트롤에서 텍스트 추출
        return raw_text
```

### 2. main.py에서 주석 해제
```python
# from golden_bot import GoldenBot
self.bot = GoldenBot()  # MockBot 대신
```

---

## 📝 batch_mapping.json 구조

매핑 파일은 자동으로 생성되며, 사용자가 UI에서 Link/Unlink하면 자동 저장됩니다.

```json
{
    "file_batch_links": {
        "FILE001": ["BATCH001", "BATCH002"]
    },
    "batch_deps": {
        "BATCH002": "BATCH001"
    },
    "file_status_override": {
        "FILE003": "FORCE_RETRY"
    },
    "batch_status_override": {
        "BATCH001": "SKIP"
    },
    "last_updated": "2026-05-07T10:30:00"
}
```

---

## ⚠️ 주의사항

1. **config.json 수정 시** 컬럼 라벨이 Golden7 헤더와 정확히 일치해야 합니다
2. **파일/배치 모니터링**은 Golden7 그리드 데이터를 클립보드로 복사해야 동작합니다
3. **데이터 조작**은 로컬 JSON에 저장되며 DB 쓰기는 하지 않습니다

---

**v1.2.0** - 2026.05.07
- 파일/배치 모니터링 탭 추가
- ttk.Notebook 구조로 UI 변경
- Thread-Safe queue 기반 UI 업데이트
- Treeview Upsert 로직 (깜빡임 방지)