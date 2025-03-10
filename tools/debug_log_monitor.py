"""
日志监控调试工具 - 测试日志文件的读取和WebSocket通信
使用方式:
    1. 直接运行: python debug_log_monitor.py job_123456
    2. 指定日志路径: python debug_log_monitor.py job_123456 --log_dir /path/to/logs
"""

import os
import sys
import time
import argparse
from pathlib import Path
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 确定项目根目录
try:
    # 添加项目根目录到Python路径
    project_root = Path(__file__).parent.parent
    sys.path.append(str(project_root))
    
    # 导入项目中的日志监视器
    from app.utils.log_monitor import LogFileMonitor
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保您在项目根目录或tools目录下运行此脚本")
    sys.exit(1)

class DebugEventHandler(FileSystemEventHandler):
    """处理文件系统事件的处理器，专注于日志文件变化"""
    
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
        self.last_position = 0
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path == str(self.log_file_path):
            try:
                with open(event.src_path, 'r', encoding='utf-8') as file:
                    file.seek(self.last_position)
                    new_content = file.read()
                    if new_content:
                        print(f"\n--- 检测到日志变化 ({time.strftime('%H:%M:%S')}) ---")
                        print(f"读取内容: {len(new_content)} 字符")
                        print(f"内容预览: {new_content[:100]}...")
                    self.last_position = file.tell()
            except Exception as e:
                print(f"读取日志文件时出错: {e}")

def test_log_monitor(job_id, log_dir=None):
    """测试日志监视器功能"""
    if not log_dir:
        log_dir = project_root / "logs"
    else:
        log_dir = Path(log_dir)
    
    log_file = log_dir / f"{job_id}.log"
    print(f"[调试] 监控日志文件: {log_file}")
    
    # 检查日志文件是否存在
    if not log_file.exists():
        print(f"[警告] 日志文件不存在: {log_file}")
        print(f"正在创建空白日志文件以便测试...")
        with open(log_file, 'w') as f:
            f.write(f"测试日志文件已创建于 {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
    # 使用自定义处理器直接监控文件变化
    print("[调试] 使用原始Watchdog监控文件变化...")
    event_handler = DebugEventHandler(log_file)
    observer = Observer()
    observer.schedule(event_handler, path=str(log_dir), recursive=False)
    observer.start()
    
    # 使用项目的LogFileMonitor测试
    print("[调试] 使用项目LogFileMonitor监控...")
    log_monitor = LogFileMonitor(job_id, str(log_dir))
    log_observer = log_monitor.start_monitoring()
    
    try:
        # 附加一些测试日志用于验证
        print(f"\n[调试] 写入一些测试日志到文件: {log_file}")
        with open(log_file, 'a') as f:
            for i in range(5):
                test_log = f"{time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | INFO     | test:debug:{i} - 测试日志 #{i+1}\n"
                f.write(test_log)
                f.flush()
                time.sleep(1)
        
        # 等待监控处理
        time.sleep(2)
        
        # 检查LogFileMonitor是否捕获了日志
        logs = log_monitor.get_log_entries()
        print(f"\n[调试] LogFileMonitor捕获的日志条目: {len(logs)}")
        for i, log in enumerate(logs[-5:] if len(logs) > 5 else logs):
            print(f"  {i+1}. {log}")
        
        # 模拟WebSocket消息
        print("\n[调试] 模拟WebSocket消息...")
        ws_data = {
            "status": "processing",
            "system_logs": logs[-5:] if len(logs) > 5 else logs
        }
        print(f"JSON消息长度: {len(json.dumps(ws_data))} 字节")
        print(f"示例消息内容: {json.dumps(ws_data, ensure_ascii=False)[:200]}...")
        
        # 交互式循环，持续监控新日志
        print("\n[调试] 进入监控模式，按回车继续，输入'q'退出...")
        while True:
            choice = input("命令(回车继续，'a'添加日志，'q'退出): ")
            if choice.lower() == 'q':
                break
            elif choice.lower() == 'a':
                # 添加新的测试日志
                with open(log_file, 'a') as f:
                    test_log = f"{time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | INFO     | test:debug:{time.time()} - 手动添加的测试日志\n"
                    f.write(test_log)
                    print(f"已添加测试日志: {test_log.strip()}")
            
            # 获取最新日志
            new_logs = log_monitor.get_log_entries()
            if len(new_logs) > len(logs):
                print(f"\n[调试] 检测到 {len(new_logs) - len(logs)} 条新日志:")
                for log in new_logs[len(logs):]:
                    print(f"  • {log}")
                logs = new_logs
    
    except KeyboardInterrupt:
        print("\n[调试] 用户中断测试")
    
    finally:
        print("[调试] 清理资源...")
        observer.stop()
        observer.join()
        log_observer.stop()
        log_observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日志监控调试工具")
    parser.add_argument("job_id", help="要监控的作业ID，比如 job_12345")
    parser.add_argument("--log_dir", help="日志目录路径", default=None)
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"日志监控调试工具 v1.0")
    print(f"测试job_id: {args.job_id}")
    print(f"日志目录: {args.log_dir if args.log_dir else '默认'}")
    print("=" * 60)
    
    test_log_monitor(args.job_id, args.log_dir)
