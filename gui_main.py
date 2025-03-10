import asyncio
import sys
import os
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTextEdit, 
                            QLineEdit, QPushButton, QVBoxLayout, 
                            QHBoxLayout, QWidget, QLabel, QScrollArea,
                            QSplitter, QFrame, QFileDialog, QListWidget,
                            QListWidgetItem, QMessageBox, QProgressBar, 
                            QDesktopWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QPalette, QTextCharFormat, QBrush

from app.agent.manus import Manus
from app.logger import logger

# Worker thread to run the agent asynchronously
class AgentWorker(QThread):
    update_signal = pyqtSignal(str, str)  # message, level
    file_created_signal = pyqtSignal(str)  # file path
    progress_signal = pyqtSignal(int, int)  # current step, max steps
    task_completed_signal = pyqtSignal()  # Signal when task is completed early
    finished_signal = pyqtSignal()
    
    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self.agent = Manus()
        
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Redirect logger output to our signal
        original_info = logger.info
        original_warning = logger.warning
        
        def custom_info(msg, *args, **kwargs):
            original_info(msg, *args, **kwargs)
            self.update_signal.emit(msg, "info")
            # Check if a file was created
            if "Content successfully saved to" in msg:
                file_path = msg.split("Content successfully saved to", 1)[1].strip()
                self.file_created_signal.emit(file_path)
            # Check for step progress
            if "Executing step" in msg:
                try:
                    parts = msg.split("Executing step", 1)[1].strip().split("/")
                    current = int(parts[0])
                    max_steps = int(parts[1])
                    self.progress_signal.emit(current, max_steps)
                except:
                    pass
            # Check for termination
            if "Special tool 'terminate' has completed the task" in msg:
                # Signal that the task was completed successfully before using all steps
                self.task_completed_signal.emit()
        
        def custom_warning(msg, *args, **kwargs):
            original_warning(msg, *args, **kwargs)
            self.update_signal.emit(msg, "warning")
            
        logger.info = custom_info
        logger.warning = custom_warning
        
        try:
            loop.run_until_complete(self.agent.run(self.prompt))
        except Exception as e:
            self.update_signal.emit(f"ERROR: {str(e)}", "error")
        finally:
            # Restore original logger functions
            logger.info = original_info
            logger.warning = original_warning
            loop.close()
            self.finished_signal.emit()

class ColoredTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Segoe UI", 12))  # Larger font
        
        # Set background color - lighter theme
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor("#FFFFFF"))  # White background
        self.setPalette(palette)
        
        # Create text formats for different message types
        self.info_format = QTextCharFormat()
        self.info_format.setForeground(QBrush(QColor("#2C88D9")))  # Blue
        
        self.warning_format = QTextCharFormat()
        self.warning_format.setForeground(QBrush(QColor("#E69500")))  # Orange
        
        self.error_format = QTextCharFormat()
        self.error_format.setForeground(QBrush(QColor("#E53935")))  # Red
        
        self.tool_format = QTextCharFormat()
        self.tool_format.setForeground(QBrush(QColor("#00897B")))  # Teal
        
        self.success_format = QTextCharFormat()
        self.success_format.setForeground(QBrush(QColor("#43A047")))  # Green

    def append_colored_text(self, text, level="info"):
        cursor = self.textCursor()
        cursor.movePosition(cursor.End)
        
        if level == "info":
            cursor.insertText(text + "\n", self.info_format)
        elif level == "warning":
            cursor.insertText(text + "\n", self.warning_format)
        elif level == "error":
            cursor.insertText(text + "\n", self.error_format)
        elif level == "tool":
            cursor.insertText(text + "\n", self.tool_format)
        elif level == "success":
            cursor.insertText(text + "\n", self.success_format)
        
        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        
    def clear_all(self):
        self.clear()

class FileListWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.files = []
        self.parent_widget = parent
        
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title with icon
        title_label = QLabel("Generated Files")
        title_label.setStyleSheet("font-size: 16px; color: #333333; font-weight: bold;")
        layout.addWidget(title_label)
        
        # File list display
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                color: #2C88D9;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                padding: 5px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #F0F0F0;
            }
            QListWidget::item:hover {
                background-color: #F5F9FF;
            }
            QListWidget::item:selected {
                background-color: #E1F0FF;
                color: #2C88D9;
            }
        """)
        self.file_list.itemDoubleClicked.connect(self.download_file)
        layout.addWidget(self.file_list)
        
        # Instructions label
        instructions = QLabel("Double-click on a file to download it")
        instructions.setStyleSheet("font-size: 12px; color: #666666; font-style: italic;")
        layout.addWidget(instructions)
        
    def add_file(self, file_path):
        if file_path not in self.files:
            self.files.append(file_path)
            item = QListWidgetItem(os.path.basename(file_path))
            item.setData(Qt.UserRole, file_path)  # Store full path as data
            item.setToolTip("Double-click to download")
            
            # Set icon based on file type
            if file_path.lower().endswith('.pdf'):
                item.setIcon(self.style().standardIcon(self.style().SP_FileDialogDetailedView))
            elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                item.setIcon(self.style().standardIcon(self.style().SP_FileDialogListView))
            elif file_path.lower().endswith(('.txt', '.md')):
                item.setIcon(self.style().standardIcon(self.style().SP_FileIcon))
            else:
                item.setIcon(self.style().standardIcon(self.style().SP_FileIcon))
                
            self.file_list.addItem(item)
            
            # Show message in output display
            if hasattr(self.parent_widget, 'output_display'):
                self.parent_widget.output_display.append_colored_text(
                    f"File created: {os.path.basename(file_path)}", "success")
            
    def download_file(self, item):
        file_path = item.data(Qt.UserRole)
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", 
                               f"The file {os.path.basename(file_path)} could not be found.")
            return
            
        # Open file dialog to select save location
        save_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save File", 
            os.path.basename(file_path),
            "All Files (*.*)"
        )
        
        if save_path:
            try:
                # Copy file to selected location
                shutil.copy2(file_path, save_path)
                QMessageBox.information(self, "Success", 
                                      f"File saved to: {save_path}")
                # Show success message in parent if possible
                if hasattr(self.parent_widget, 'output_display'):
                    self.parent_widget.output_display.append_colored_text(
                        f"File saved to: {save_path}", "success")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error saving file: {str(e)}")
                if hasattr(self.parent_widget, 'output_display'):
                    self.parent_widget.output_display.append_colored_text(
                        f"Error saving file: {str(e)}", "error")
            
    def clear_all(self):
        self.file_list.clear()
        self.files = []

class ManusGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # Initialize attributes before calling initUI
        self.max_steps = 30  # Default max steps
        self.task_completed_early = False
        self.worker = None
        self.initUI()
        
    def initUI(self):
        # Main window setup
        self.setWindowTitle('Manus AI Assistant')
        self.setGeometry(100, 100, 1000, 700)
        
        # Center the window
        self.center()
        
        # Set stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F8F9FA;
            }
            QLabel {
                color: #333333;
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            QLineEdit {
                background-color: #FFFFFF;
                color: #333333;
                border: 1px solid #CCCCCC;
                border-radius: 6px;
                padding: 12px;
                font-size: 16px;
            }
            QPushButton {
                background-color: #4A86E8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3D76C9;
            }
            QPushButton:pressed {
                background-color: #2E5CA0;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
            }
            QSplitter::handle {
                background-color: #DDDDDD;
            }
            QScrollArea {
                border: none;
            }
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                text-align: center;
                background-color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4A86E8;
                width: 10px;
                margin: 0.5px;
            }
        """)
        
        # Create central widget
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Add title with icon
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(self.style().standardIcon(self.style().SP_ComputerIcon).pixmap(32, 32))
        title_label = QLabel("Manus AI Assistant")
        title_label.setStyleSheet("font-size: 28px; color: #4A86E8; margin-bottom: 15px;")
        title_layout.addWidget(title_icon)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)
        
        # Create main splitter
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.setHandleWidth(2)
        
        # Input section
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(10, 10, 10, 10)
        
        # Input header with icon
        input_header = QHBoxLayout()
        input_icon = QLabel()
        input_icon.setPixmap(self.style().standardIcon(self.style().SP_MessageBoxQuestion).pixmap(24, 24))
        prompt_label = QLabel("Enter your prompt:")
        prompt_label.setStyleSheet("font-size: 16px; color: #333333;")
        input_header.addWidget(input_icon)
        input_header.addWidget(prompt_label)
        input_header.addStretch()
        input_layout.addLayout(input_header)
        
        # Input field
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Type your request here...")
        self.prompt_input.setMinimumHeight(50)
        self.prompt_input.setStyleSheet("font-size: 16px;")
        self.prompt_input.returnPressed.connect(self.process_prompt)
        input_layout.addWidget(self.prompt_input)
        
        # Create buttons
        button_layout = QHBoxLayout()
        
        self.submit_button = QPushButton("Submit")
        self.submit_button.setMinimumHeight(50)
        self.submit_button.setIcon(self.style().standardIcon(self.style().SP_DialogOkButton))
        self.submit_button.clicked.connect(self.process_prompt)
        
        self.clear_button = QPushButton("Clear All")
        self.clear_button.setMinimumHeight(50)
        self.clear_button.setIcon(self.style().standardIcon(self.style().SP_DialogResetButton))
        self.clear_button.setStyleSheet("""
            background-color: #FF5722;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 12px 24px;
            font-weight: bold;
            font-size: 14px;
        """)
        self.clear_button.clicked.connect(self.clear_all)
        
        button_layout.addWidget(self.submit_button)
        button_layout.addWidget(self.clear_button)
        input_layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_layout = QHBoxLayout()
        progress_label = QLabel("Progress:")
        progress_label.setStyleSheet("font-size: 14px; color: #666666;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.max_steps)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v/%m steps")
        self.progress_bar.setMinimumHeight(20)
        
        self.progress_layout.addWidget(progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        input_layout.addLayout(self.progress_layout)
        
        # Output section
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create horizontal splitter for output sections
        output_splitter = QSplitter(Qt.Horizontal)
        
        # Process status section
        process_widget = QWidget()
        process_layout = QVBoxLayout(process_widget)
        process_layout.setContentsMargins(0, 0, 0, 0)
        
        # Process header with icon
        process_header = QHBoxLayout()
        process_icon = QLabel()
        process_icon.setPixmap(self.style().standardIcon(self.style().SP_FileDialogInfoView).pixmap(24, 24))
        output_label = QLabel("Process Status:")
        output_label.setStyleSheet("font-size: 16px; color: #333333;")
        process_header.addWidget(process_icon)
        process_header.addWidget(output_label)
        process_header.addStretch()
        process_layout.addLayout(process_header)
        
        self.output_display = ColoredTextEdit()
        process_layout.addWidget(self.output_display)
        
        # File list section
        self.file_list_widget = FileListWidget(self)
        
        # Add widgets to horizontal splitter
        output_splitter.addWidget(process_widget)
        output_splitter.addWidget(self.file_list_widget)
        output_splitter.setSizes([600, 400])  # 60% process, 40% files
        
        output_layout.addWidget(output_splitter)
        
        # Add widgets to vertical splitter
        main_splitter.addWidget(input_widget)
        main_splitter.addWidget(output_widget)
        
        # Set initial sizes (30% input, 70% output)
        main_splitter.setSizes([250, 550])
        
        # Add splitter to main layout
        main_layout.addWidget(main_splitter)
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Initialize with welcome message
        self.output_display.append_colored_text("Welcome to Manus AI Assistant!", "info")
        self.output_display.append_colored_text("Enter your prompt above and click Submit to begin.", "info")
        
    def center(self):
        # Center window on screen
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
    def process_prompt(self):
        prompt = self.prompt_input.text()
        if not prompt.strip():
            self.output_display.append_colored_text("Skipping empty prompt.", "warning")
            return
            
        if prompt.lower() in ["exit", "quit"]:
            self.output_display.append_colored_text("Goodbye!", "info")
            QApplication.quit()
            return
            
        # Disable input while processing
        self.prompt_input.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        
        # Clear previous output
        self.output_display.clear()
        self.output_display.append_colored_text(f"Processing prompt: {prompt}", "info")
        self.output_display.append_colored_text("Processing your request...", "warning")
        
        # Reset progress bar and task completion flag
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v/%m steps")
        self.task_completed_early = False
        
        # Reset progress bar style
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                text-align: center;
                background-color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4A86E8;
                width: 10px;
                margin: 0.5px;
            }
        """)
        
        # Create and start worker thread
        self.worker = AgentWorker(prompt)
        self.worker.update_signal.connect(self.update_output)
        self.worker.file_created_signal.connect(self.file_list_widget.add_file)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.task_completed_signal.connect(self.on_task_completed)
        self.worker.finished_signal.connect(self.on_processing_finished)
        self.worker.start()
        
    def clear_all(self):
        # Ask for confirmation
        reply = QMessageBox.question(self, 'Confirm Clear',
                                    'Are you sure you want to clear all content?',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Clear input
            self.prompt_input.clear()
            
            # Clear output
            self.output_display.clear_all()
            self.output_display.append_colored_text("Welcome to Manus AI Assistant!", "info")
            self.output_display.append_colored_text("Enter your prompt above and click Submit to begin.", "info")
            
            # Clear file list
            self.file_list_widget.clear_all()
            
            # Reset progress bar
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("%v/%m steps")
            
            # Reset progress bar style
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #FFFFFF;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #4A86E8;
                    width: 10px;
                    margin: 0.5px;
                }
            """)
            
            # Focus on input
            self.prompt_input.setFocus()
        
    def update_output(self, message, level):
        # Filter out INFO prefix if present
        if message.startswith("[") and "]" in message:
            parts = message.split("]", 1)
            if len(parts) > 1:
                message = parts[1].strip()
        
        # Detect tool usage patterns
        if "Activating tool:" in message and "terminate" in message:
            level = "success"
            message = "Task completed successfully! The agent has determined that all required steps are complete."
        elif "Activating tool:" in message:
            level = "tool"
        elif "Tool" in message and "completed its mission" in message and "terminate" in message:
            level = "success"
            message = "Task completed successfully!"
        elif "Tool" in message and "completed its mission" in message:
            level = "success"
            
        self.output_display.append_colored_text(message, level)
        
    def update_progress(self, current, max_steps):
        self.max_steps = max_steps
        self.progress_bar.setMaximum(max_steps)
        self.progress_bar.setValue(current)
        
        # Update the format to show completion percentage
        completion_percentage = int((current / max_steps) * 100)
        self.progress_bar.setFormat(f"{current}/{max_steps} steps ({completion_percentage}%)")
        
        # If task was completed early, show as complete
        if self.task_completed_early:
            self.progress_bar.setFormat("Task completed successfully!")
            self.progress_bar.setValue(max_steps)  # Show as 100% complete
            # Change progress bar color to green for completed tasks
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #CCCCCC;
                    border-radius: 4px;
                    text-align: center;
                    background-color: #FFFFFF;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #4CAF50;
                    width: 10px;
                    margin: 0.5px;
                }
            """)
    
    def on_task_completed(self):
        self.task_completed_early = True
        self.output_display.append_colored_text(
            "✅ Task completed successfully! The agent has finished the task before using all available steps.", 
            "success")
        
        # Update progress bar to show completion
        self.progress_bar.setFormat("Task completed successfully!")
        self.progress_bar.setValue(self.max_steps)  # Show as 100% complete
        
        # Change progress bar color to green for completed tasks
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                text-align: center;
                background-color: #FFFFFF;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0.5px;
            }
        """)
        
    def on_processing_finished(self):
        # Re-enable input after processing
        self.prompt_input.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.prompt_input.clear()
        self.prompt_input.setFocus()
        
        if not self.task_completed_early:
            self.output_display.append_colored_text("Processing complete. Ready for new prompt.", "success")

def main():
    app = QApplication(sys.argv)
    gui = ManusGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()