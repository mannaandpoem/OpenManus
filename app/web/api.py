from flask import Blueprint, jsonify, request
from ..utils.log_monitor import LogFileMonitor

api_bp = Blueprint('api', __name__)
log_monitors = {}

@api_bp.route('/job/<job_id>/files', methods=['GET'])
def get_job_files(job_id):
    """获取作业生成的文件列表"""
    if job_id not in log_monitors:
        log_monitors[job_id] = LogFileMonitor(job_id)
        log_monitors[job_id].start_monitoring()
    
    files = log_monitors[job_id].get_generated_files()
    return jsonify({"files": files})

@api_bp.route('/job/<job_id>/logs', methods=['GET'])
def get_job_logs(job_id):
    """获取作业的系统日志"""
    if job_id not in log_monitors:
        log_monitors[job_id] = LogFileMonitor(job_id)
        log_monitors[job_id].start_monitoring()
    
    logs = log_monitors[job_id].get_log_entries()
    return jsonify({"logs": logs})
