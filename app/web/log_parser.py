"""
Log parser module for extracting execution information from OpenManus log files.
"""
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

class LogParser:
    """Parser for OpenManus log files to extract execution status and progress."""
    
    def __init__(self, log_path: str):
        """
        Initialize the log parser with a log file path.
        
        Args:
            log_path: Path to the log file to parse
        """
        self.log_path = log_path
        self.log_content = ""
        self.plan_id = None
        self.plan_title = ""
        self.steps = []
        self.step_statuses = []
        self.current_step = 0
        self.total_steps = 0
        self.completed_steps = 0
        self.tool_executions = []
        self.errors = []
        self.warnings = []
        
    def parse(self) -> Dict[str, Any]:
        """
        Parse the log file and extract execution information.
        
        Returns:
            Dict containing parsed information about the execution
        """
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                self.log_content = f.read()
                
            # Extract plan information
            self._extract_plan_info()
            
            # Extract step information
            self._extract_step_info()
            
            # Extract tool executions
            self._extract_tool_executions()
            
            # Extract errors and warnings
            self._extract_errors_warnings()
            
            return {
                "plan_id": self.plan_id,
                "plan_title": self.plan_title,
                "steps": self.steps,
                "step_statuses": self.step_statuses,
                "current_step": self.current_step,
                "total_steps": self.total_steps,
                "completed_steps": self.completed_steps,
                "progress_percentage": self._calculate_progress(),
                "tool_executions": self.tool_executions,
                "errors": self.errors,
                "warnings": self.warnings,
                "timestamp": self._extract_timestamp(),
                "status": self._determine_status()
            }
        except Exception as e:
            return {
                "error": f"Failed to parse log file: {str(e)}",
                "status": "error"
            }
    
    def _extract_plan_info(self) -> None:
        """Extract plan ID and title from the log."""
        # Extract plan ID
        plan_id_match = re.search(r"Creating initial plan with ID: (plan_\d+)", self.log_content)
        if plan_id_match:
            self.plan_id = plan_id_match.group(1)
        
        # Extract plan title
        plan_title_match = re.search(r"Plan: (.*?) \(ID: plan_\d+\)", self.log_content)
        if plan_title_match:
            self.plan_title = plan_title_match.group(1)
    
    def _extract_step_info(self) -> None:
        """Extract step information from the log."""
        # Extract steps list
        steps_section = re.search(r"Steps:\n(.*?)(?:\n\n|\Z)", self.log_content, re.DOTALL)
        if steps_section:
            steps_text = steps_section.group(1)
            step_lines = steps_text.strip().split('\n')
            
            for line in step_lines:
                # Match step pattern: "0. [ ] Define the objective of task 11"
                step_match = re.match(r'\d+\.\s+\[([ ✓→!])\]\s+(.*)', line)
                if step_match:
                    status_symbol = step_match.group(1)
                    step_text = step_match.group(2)
                    
                    self.steps.append(step_text)
                    
                    # Convert status symbol to status text
                    if status_symbol == "✓":
                        self.step_statuses.append("completed")
                        self.completed_steps += 1
                    elif status_symbol == "→":
                        self.step_statuses.append("in_progress")
                    elif status_symbol == "!":
                        self.step_statuses.append("blocked")
                    else:  # Empty space
                        self.step_statuses.append("not_started")
        
        # Extract total steps
        self.total_steps = len(self.steps)
        
        # Extract current step from execution logs
        current_step_matches = re.findall(r"Executing step (\d+)/(\d+)", self.log_content)
        if current_step_matches:
            # Get the latest execution step
            latest_match = current_step_matches[-1]
            self.current_step = int(latest_match[0])
            
            # Update total steps if available from execution log
            if int(latest_match[1]) > self.total_steps:
                self.total_steps = int(latest_match[1])
        
        # Extract completed steps from marking logs
        completed_step_matches = re.findall(r"Marked step (\d+) as completed", self.log_content)
        if completed_step_matches:
            # Count unique completed steps
            self.completed_steps = len(set(completed_step_matches))
    
    def _extract_tool_executions(self) -> None:
        """Extract tool execution information from the log."""
        # Match tool execution patterns
        tool_patterns = [
            r"🛠️ Manus selected \d+ tools to use",
            r"🧰 Tools being prepared: \['([^']+)'\]",
            r"🔧 Activating tool: '([^']+)'...",
            r"🎯 Tool '([^']+)' completed its mission!"
        ]
        
        for pattern in tool_patterns:
            matches = re.finditer(pattern, self.log_content)
            for match in matches:
                if "'" in pattern:
                    tool_name = match.group(1)
                    self.tool_executions.append({
                        "tool": tool_name,
                        "timestamp": self._extract_timestamp_for_line(match.group(0))
                    })
                else:
                    self.tool_executions.append({
                        "action": match.group(0),
                        "timestamp": self._extract_timestamp_for_line(match.group(0))
                    })
    
    def _extract_errors_warnings(self) -> None:
        """Extract errors and warnings from the log."""
        # Extract errors (ERROR level logs)
        error_matches = re.finditer(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| ERROR\s+\| (.*)", self.log_content)
        for match in error_matches:
            self.errors.append({
                "message": match.group(1),
                "timestamp": self._extract_timestamp_for_line(match.group(0))
            })
        
        # Extract warnings (WARNING level logs)
        warning_matches = re.finditer(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| WARNING\s+\| (.*)", self.log_content)
        for match in warning_matches:
            self.warnings.append({
                "message": match.group(1),
                "timestamp": self._extract_timestamp_for_line(match.group(0))
            })
    
    def _calculate_progress(self) -> int:
        """Calculate the progress percentage based on completed steps."""
        if self.total_steps == 0:
            return 0
        return min(int((self.completed_steps / self.total_steps) * 100), 100)
    
    def _extract_timestamp(self) -> str:
        """Extract the timestamp from the log file name or content."""
        # Try to extract from filename first (format: YYYYMMDD_HHMMSS.log)
        filename = os.path.basename(self.log_path)
        timestamp_match = re.search(r"(\d{8}_\d{6})\.log", filename)
        if timestamp_match:
            timestamp_str = timestamp_match.group(1)
            try:
                dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                return dt.isoformat()
            except ValueError:
                pass
        
        # Try to extract from first log line
        first_line_match = re.search(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", self.log_content)
        if first_line_match:
            timestamp_str = first_line_match.group(1)
            try:
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
                return dt.isoformat()
            except ValueError:
                pass
        
        # Fallback to file modification time
        try:
            mtime = os.path.getmtime(self.log_path)
            return datetime.fromtimestamp(mtime).isoformat()
        except:
            return datetime.now().isoformat()
    
    def _extract_timestamp_for_line(self, line: str) -> str:
        """Extract timestamp for a specific log line."""
        timestamp_match = re.search(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
        if timestamp_match:
            timestamp_str = timestamp_match.group(1)
            try:
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
                return dt.isoformat()
            except ValueError:
                pass
        return ""
    
    def _determine_status(self) -> str:
        """Determine the overall status of the execution."""
        if self.errors:
            return "error"
        
        # Check for completion markers
        if "task processing completed" in self.log_content.lower() or "plan completed" in self.log_content.lower():
            return "completed"
        
        # Check if all steps are completed
        if self.completed_steps >= self.total_steps and self.total_steps > 0:
            return "completed"
        
        # Check for termination
        if "terminate" in self.log_content.lower() and "completed its mission" in self.log_content.lower():
            return "completed"
        
        # Default to in_progress
        return "in_progress"


def parse_log_file(log_path: str) -> Dict[str, Any]:
    """
    Parse a single log file and return the execution information.
    
    Args:
        log_path: Path to the log file
        
    Returns:
        Dict containing parsed information about the execution
    """
    parser = LogParser(log_path)
    return parser.parse()


def get_latest_log_info(logs_dir: str = None) -> Dict[str, Any]:
    """
    Get information from the latest log file.
    
    Args:
        logs_dir: Directory containing log files (default: project's logs directory)
        
    Returns:
        Dict containing parsed information about the latest execution
    """
    if logs_dir is None:
        # Default to project's logs directory
        logs_dir = Path(__file__).parent.parent.parent / "logs"
    
    # Find the latest log file
    log_files = []
    for entry in os.scandir(logs_dir):
        if entry.is_file() and entry.name.endswith('.log'):
            log_files.append({
                "path": entry.path,
                "modified": entry.stat().st_mtime
            })
    
    if not log_files:
        return {"error": "No log files found", "status": "unknown"}
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x["modified"], reverse=True)
    latest_log = log_files[0]["path"]
    
    # Parse the latest log file
    return parse_log_file(latest_log)


def get_all_logs_info(logs_dir: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get information from all log files, sorted by modification time (newest first).
    
    Args:
        logs_dir: Directory containing log files (default: project's logs directory)
        limit: Maximum number of logs to return
        
    Returns:
        List of dicts containing parsed information about each execution
    """
    if logs_dir is None:
        # Default to project's logs directory
        logs_dir = Path(__file__).parent.parent.parent / "logs"
    
    # Find all log files
    log_files = []
    for entry in os.scandir(logs_dir):
        if entry.is_file() and entry.name.endswith('.log'):
            log_files.append({
                "path": entry.path,
                "modified": entry.stat().st_mtime
            })
    
    if not log_files:
        return [{"error": "No log files found", "status": "unknown"}]
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x["modified"], reverse=True)
    
    # Parse each log file (up to the limit)
    results = []
    for log_file in log_files[:limit]:
        log_info = parse_log_file(log_file["path"])
        log_info["file_path"] = log_file["path"]
        log_info["file_name"] = os.path.basename(log_file["path"])
        results.append(log_info)
    
    return results
