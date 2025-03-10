import os
import re
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogFileMonitor:
    def __init__(self, job_id=None, log_dir='logs'):
        # 优先使用环境变量中的任务ID
        self.job_id = job_id or os.environ.get("OPENMANUS_TASK_ID")
        self.log_dir = log_dir
        
        # 优先使用环境变量中的日志文件路径
        env_log_file = os.environ.get("OPENMANUS_LOG_FILE")
        if env_log_file and os.path.exists(env_log_file):
            self.log_file = env_log_file
        else:
            self.log_file = os.path.join(log_dir, f"{self.job_id}.log")
            
        self.generated_files = []
        self.log_entries = []
        self.file_pattern = re.compile(r"Content successfully saved to (.+)")
        self.last_update_time = 0
        
    def start_monitoring(self):
        # 确保日志文件目录存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # 如果日志文件已存在，先读取现有内容
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as file:
                    for line in file:
                        self.parse_log_line(line.strip())
            except Exception as e:
                print(f"读取现有日志文件时出错: {e}")
        
        # 创建观察者来监控日志文件的变化
        event_handler = LogEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, self.log_dir, recursive=False)
        observer.start()
        return observer
        
    def parse_log_line(self, line):
        # 解析日志行
        self.log_entries.append(line)
        self.last_update_time = time.time()
        
        # 检查是否有生成的文件
        file_match = self.file_pattern.search(line)
        if file_match:
            filename = file_match.group(1)
            if filename not in self.generated_files:
                self.generated_files.append(filename)
                
    def get_generated_files(self):
        return self.generated_files
        
    def get_log_entries(self):
        return self.log_entries
        
    def get_new_entries_since(self, timestamp):
        """获取指定时间戳之后的新日志条目"""
        if not self.log_entries:
            return []
        
        # 如果没有新条目，返回空列表
        if self.last_update_time <= timestamp:
            return []
        
        # 找出新添加的条目
        new_entries = []
        for i in range(len(self.log_entries)-1, -1, -1):
            # 这里简化处理，假设所有新条目都是连续添加的
            # 实际实现可能需要在日志条目中添加时间戳
            if i >= len(self.log_entries) - 10:  # 最多返回最新的10条
                new_entries.insert(0, self.log_entries[i])
            else:
                break
                
        return new_entries

class LogEventHandler(FileSystemEventHandler):
    def __init__(self, monitor):
        self.monitor = monitor
        self.last_position = 0
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path == self.monitor.log_file:
            try:
                with open(event.src_path, 'r', encoding='utf-8') as file:
                    file.seek(self.last_position)
                    for line in file:
                        self.monitor.parse_log_line(line.strip())
                    self.last_position = file.tell()
            except Exception as e:
                print(f"读取修改的日志文件时出错: {e}")
                
    def on_created(self, event):
        # 如果是新创建的目标日志文件
        if not event.is_directory and event.src_path == self.monitor.log_file:
            try:
                with open(event.src_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        self.monitor.parse_log_line(line.strip())
                    self.last_position = file.tell()
            except Exception as e:
                print(f"读取新创建的日志文件时出错: {e}")
