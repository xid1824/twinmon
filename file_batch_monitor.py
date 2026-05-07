"""
파일/배치 모니터링 모듈 v1.0
- Golden7 클립보드 기반 데이터 파싱
- Thread-Safe UI 업데이트 (queue.Queue)
- Treeview Upsert 로직
- 사용자 활동 시 10초 대기 트리거
"""
import tkinter as tk
from tkinter import ttk
import json
import time
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional

# pyperclip: 클립보드 읽기
try:
    import pyperclip
except ImportError:
    pyperclip = None


class ConfigManager:
    def __init__(self, config_path: str, mapping_path: str):
        self.config_path = config_path
        self.mapping_path = mapping_path
        self.config = self._load_json(config_path)
        self.mapping = self._load_json_safe()
    
    def _load_json(self, path: str) -> dict:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_json_safe(self) -> dict:
        try:
            return self._load_json(self.mapping_path)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "file_batch_links": {},
                "batch_deps": {},
                "file_status_override": {},
                "batch_status_override": {},
                "last_updated": ""
            }
    
    def save_mapping(self):
        self.mapping['last_updated'] = datetime.now().isoformat()
        with open(self.mapping_path, 'w', encoding='utf-8') as f:
            json.dump(self.mapping, f, indent=2, ensure_ascii=False)


class GridParser:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.expected_headers = None
        self._build_expected_headers()
    
    def _build_expected_headers(self):
        file_labels = [v['label'] for v in self.config.config['file_table']['columns'].values()]
        batch_labels = [v['label'] for v in self.config.config['batch_table']['columns'].values()]
        self.expected_headers = file_labels + batch_labels
    
    def validate_clipboard(self, text: str) -> bool:
        """클립보드 데이터가 Golden7 그리드인지 엄격 검증"""
        if not text or '\t' not in text:
            return False
        
        lines = text.strip().split('\n')
        if len(lines) < 2:
            return False
        
        header_line = lines[0]
        header_cols = [h.strip() for h in header_line.split('\t')]
        
        found_count = sum(1 for expected in self.expected_headers if expected in header_cols)
        return found_count >= 2
    
    def parse_clipboard(self, text: str, target: str = 'file') -> List[Dict]:
        if not text:
            return []
        
        lines = text.strip().split('\n')
        if len(lines) < 2:
            return []
        
        header_cols = [h.strip() for h in lines[0].split('\t')]
        data = []
        
        for row in lines[1:]:
            cols = row.split('\t')
            row_dict = {}
            for i, col in enumerate(cols):
                if i < len(header_cols):
                    row_dict[f'COL{i:03d}'] = col.strip()
            data.append(row_dict)
        
        return data
    
    def merge_with_mapping(self, raw_data: List[Dict], target: str = 'file') -> List[Dict]:
        key_col = 'COL001'
        merged = []
        
        for row in raw_data:
            row_id = row.get(key_col, '')
            
            if target == 'file':
                linked = self.config.mapping.get('file_batch_links', {}).get(row_id, [])
                row['_linked_batches'] = linked
                
                override_status = self.config.mapping.get('file_status_override', {}).get(row_id)
                if override_status:
                    status_col = list(self.config.config['file_table']['columns'].keys())[-1]
                    row[status_col] = override_status
            
            elif target == 'batch':
                deps = self.config.mapping.get('batch_deps', {}).get(row_id)
                row['_dependency'] = deps or ''
                
                override_status = self.config.mapping.get('batch_status_override', {}).get(row_id)
                if override_status:
                    status_col = list(self.config.config['batch_table']['columns'].keys())[-1]
                    row[status_col] = override_status
            
            merged.append(row)
        
        return merged


class FileBatchTreeview:
    def __init__(self, parent, config_manager: ConfigManager, pause_callback):
        self.config = config_manager
        self.pause_callback = pause_callback
        
        self.main_frame = tk.Frame(parent)
        
        # 좌측: File Treeview
        left_frame = tk.Frame(self.main_frame)
        
        file_cols = self.config.config['file_table']['columns']
        self.file_col_keys = list(file_cols.keys())
        self.file_col_labels = [v['label'] for v in file_cols.values()]
        self.file_col_widths = [v['width'] for v in file_cols.values()]
        
        self.file_tree = ttk.Treeview(left_frame,
            columns=self.file_col_keys + ['_linked_batches'],
            show='tree headings',
            selectmode='extended')
        
        for key, label, width in zip(self.file_col_keys, self.file_col_labels, self.file_col_widths):
            self.file_tree.heading(key, text=label)
            self.file_tree.column(key, width=width, anchor='w')
        
        self.file_tree.heading('_linked_batches', text='Linked Batches')
        self.file_tree.column('_linked_batches', width=150, anchor='w')
        
        file_vsb = ttk.Scrollbar(left_frame, orient='vertical', command=self.file_tree.yview)
        file_hsb = ttk.Scrollbar(left_frame, orient='horizontal', command=self.file_tree.xview)
        self.file_tree.configure(yscroll=file_vsb.set, xscroll=file_hsb.set)
        
        self.file_tree.pack(side='left', fill='both', expand=True)
        file_vsb.pack(side='right', fill='y')
        file_hsb.pack(side='bottom', fill='x')
        
        self.file_tree.bind('<ButtonRelease-1>', self._on_user_activity)
        self.file_tree.bind('<ButtonPress-3>', self._on_user_activity)
        
        # 중앙: 연결/해제 버튼
        center_frame = tk.Frame(self.main_frame)
        btn_link = tk.Button(center_frame, text='[Link]',
            command=self._link_items, width=10, bg='#e0e0e0')
        btn_unlink = tk.Button(center_frame, text='[Unlink]',
            command=self._unlink_items, width=10, bg='#e0e0e0')
        btn_link.pack(pady=5)
        btn_unlink.pack(pady=5)
        
        # 우측: Batch Treeview
        right_frame = tk.Frame(self.main_frame)
        
        batch_cols = self.config.config['batch_table']['columns']
        self.batch_col_keys = list(batch_cols.keys())
        self.batch_col_labels = [v['label'] for v in batch_cols.values()]
        self.batch_col_widths = [v['width'] for v in batch_cols.values()]
        
        self.batch_tree = ttk.Treeview(right_frame,
            columns=self.batch_col_keys + ['_dependency'],
            show='tree headings',
            selectmode='extended')
        
        for key, label, width in zip(self.batch_col_keys, self.batch_col_labels, self.batch_col_widths):
            self.batch_tree.heading(key, text=label)
            self.batch_tree.column(key, width=width, anchor='w')
        
        self.batch_tree.heading('_dependency', text='Dependency')
        self.batch_tree.column('_dependency', width=100, anchor='w')
        
        batch_vsb = ttk.Scrollbar(right_frame, orient='vertical', command=self.batch_tree.yview)
        batch_hsb = ttk.Scrollbar(right_frame, orient='horizontal', command=self.batch_tree.xview)
        self.batch_tree.configure(yscroll=batch_vsb.set, xscroll=batch_hsb.set)
        
        self.batch_tree.pack(side='left', fill='both', expand=True)
        batch_vsb.pack(side='right', fill='y')
        batch_hsb.pack(side='bottom', fill='x')
        
        self.batch_tree.bind('<ButtonRelease-1>', self._on_user_activity)
        self.batch_tree.bind('<ButtonPress-3>', self._on_user_activity)
        
        # 레이아웃 배치
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        center_frame.pack(side='left', fill='y', padx=5)
        right_frame.pack(side='left', fill='both', expand=True, padx=(5, 0))
        
        # Upsert용 매핑
        self._file_id_to_iid = {}
        self._batch_id_to_iid = {}
    
    def _on_user_activity(self, event):
        self.pause_callback()
    
    def update_file_tree(self, data: List[Dict]):
        """Treeview Upsert 로직"""
        id_col = self.file_col_keys[0]
        new_ids = set(row.get(id_col, '') for row in data)
        
        # 삭제
        for iid in list(self._file_id_to_iid.values()):
            item_id = self.file_tree.item(iid, 'values')[0]
            if item_id not in new_ids:
                self.file_tree.delete(iid)
        
        # 기존 매핑 정리
        self._file_id_to_iid = {fid: iid for fid, iid in self._file_id_to_iid.items() if fid in new_ids}
        
        # 업데이트 또는 추가
        for row in data:
            row_id = row.get(id_col, '')
            if not row_id:
                continue
            
            values = [row.get(col, '') for col in self.file_col_keys]
            linked = row.get('_linked_batches', [])
            values.append(', '.join(linked) if linked else '')
            
            if row_id in self._file_id_to_iid:
                iid = self._file_id_to_iid[row_id]
                current_values = list(self.file_tree.item(iid, 'values'))
                if current_values != values:
                    self.file_tree.item(iid, values=values)
            else:
                iid = self.file_tree.insert('', 'end', values=values)
                self._file_id_to_iid[row_id] = iid
    
    def update_batch_tree(self, data: List[Dict]):
        id_col = self.batch_col_keys[0]
        new_ids = set(row.get(id_col, '') for row in data)
        
        for iid in list(self._batch_id_to_iid.values()):
            item_id = self.batch_tree.item(iid, 'values')[0]
            if item_id not in new_ids:
                self.batch_tree.delete(iid)
        
        self._batch_id_to_iid = {bid: iid for bid, iid in self._batch_id_to_iid.items() if bid in new_ids}
        
        for row in data:
            row_id = row.get(id_col, '')
            if not row_id:
                continue
            
            values = [row.get(col, '') for col in self.batch_col_keys]
            dep = row.get('_dependency', '')
            values.append(dep if dep else '')
            
            if row_id in self._batch_id_to_iid:
                iid = self._batch_id_to_iid[row_id]
                current_values = list(self.batch_tree.item(iid, 'values'))
                if current_values != values:
                    self.batch_tree.item(iid, values=values)
            else:
                iid = self.batch_tree.insert('', 'end', values=values)
                self._batch_id_to_iid[row_id] = iid
    
    def _link_items(self):
        file_sels = self.file_tree.selection()
        batch_sels = self.batch_tree.selection()
        
        if not file_sels or not batch_sels:
            return
        
        file_id = self.file_tree.item(file_sels[0], 'values')[0]
        
        for batch_iid in batch_sels:
            batch_id = self.batch_tree.item(batch_iid, 'values')[0]
            
            if file_id not in self.config.mapping['file_batch_links']:
                self.config.mapping['file_batch_links'][file_id] = []
            
            if batch_id not in self.config.mapping['file_batch_links'][file_id]:
                self.config.mapping['file_batch_links'][file_id].append(batch_id)
        
        self.config.save_mapping()
    
    def _unlink_items(self):
        file_sels = self.file_tree.selection()
        
        if not file_sels:
            return
        
        file_id = self.file_tree.item(file_sels[0], 'values')[0]
        batch_sels = self.batch_tree.selection()
        
        if file_id in self.config.mapping['file_batch_links']:
            if batch_sels:
                for batch_iid in batch_sels:
                    batch_id = self.batch_tree.item(batch_iid, 'values')[0]
                    if batch_id in self.config.mapping['file_batch_links'][file_id]:
                        self.config.mapping['file_batch_links'][file_id].remove(batch_id)
            else:
                del self.config.mapping['file_batch_links'][file_id]
        
        self.config.save_mapping()
    
    def get_frame(self):
        return self.main_frame


class ScrapeController:
    def __init__(self, config_manager: ConfigManager, grid_parser: GridParser,
                 ui_panel: FileBatchTreeview):
        self.config = config_manager
        self.parser = grid_parser
        self.ui = ui_panel
        
        self.ui_queue = queue.Queue()
        self.paused = False
        self.pause_timer = None
        self.running = False
        self._thread = None
    
    def trigger_pause(self):
        self.paused = True
        if self.pause_timer:
            self.pause_timer.cancel()
        self.pause_timer = threading.Timer(
            self.config.config['scrape']['pause_on_activity_sec'],
            self._resume
        )
        self.pause_timer.start()
    
    def _resume(self):
        self.paused = False
    
    def start(self, root_window):
        self.running = True
        self._thread = threading.Thread(target=self._scrape_loop, daemon=True)
        self._thread.start()
        self._poll_ui_queue(root_window)
    
    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
    
    def _poll_ui_queue(self, root_window):
        try:
            while True:
                task = self.ui_queue.get_nowait()
                
                if task['type'] == 'file_update':
                    self.ui.update_file_tree(task['data'])
                elif task['type'] == 'batch_update':
                    self.ui.update_batch_tree(task['data'])
        
        except queue.Empty:
            pass
        
        if self.running:
            root_window.after(100, lambda: self._poll_ui_queue(root_window))
    
    def _scrape_loop(self):
        interval = self.config.config['scrape']['refresh_interval_sec']
        last_clipboard = ''
        
        while self.running:
            if not self.paused and pyperclip:
                try:
                    clipboard_text = pyperclip.paste()
                    
                    if clipboard_text and clipboard_text != last_clipboard:
                        last_clipboard = clipboard_text
                        
                        if self.parser.validate_clipboard(clipboard_text):
                            raw_file = self.parser.parse_clipboard(clipboard_text, target='file')
                            merged_file = self.parser.merge_with_mapping(raw_file, target='file')
                            
                            self.ui_queue.put({
                                'type': 'file_update',
                                'data': merged_file
                            })
                
                except Exception as e:
                    print(f'[ScrapeController] Error: {e}')
            
            time.sleep(interval)
