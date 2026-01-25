import sys
import os
import tempfile
import io
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea, QDialog)
from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal
from PyQt5.QtGui import QPainter, QBrush, QColor, QFont
from google import genai
from PIL import ImageGrab, Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, RetryCallState


class SettingsDialog(QDialog):
    """Dialog for entering Gemini API key"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_key = None
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("API Key Required")
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setModal(True)
        self.setFixedSize(400, 150)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instructions label
        info_label = QLabel("Please enter your Gemini API key to continue:")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # API key input field
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Paste your API key here...")
        self.api_key_input.setEchoMode(QLineEdit.Password)  # Mask the key for security
        self.api_key_input.returnPressed.connect(self.acceptDialog)
        layout.addWidget(self.api_key_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.acceptDialog)
        button_layout.addWidget(self.ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Focus on input field
        self.api_key_input.setFocus()
    
    def acceptDialog(self):
        """Validate and accept the dialog"""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            # Show error or highlight field
            self.api_key_input.setStyleSheet("border: 2px solid red;")
            return
        
        self.api_key = api_key
        self.accept()
    
    def getApiKey(self):
        """Return the entered API key"""
        return self.api_key


class GeminiWorker(QThread):
    """Worker thread for making async Gemini API calls"""
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    retry_attempt = pyqtSignal(int, float)  # Emits attempt number and wait time
    
    def __init__(self, message, api_key, image_path=None):
        super().__init__()
        self.message = message
        self.api_key = api_key
        self.image_path = image_path  # Optional image for multimodal requests
    
    def _is_service_unavailable(self, exception):
        """Check if exception is a 503 Service Unavailable error"""
        error_msg = str(exception).upper()
        return ("503" in error_msg or "UNAVAILABLE" in error_msg)
    
    def _before_retry(self, retry_state: RetryCallState):
        """Called before each retry attempt"""
        if retry_state.outcome and retry_state.outcome.failed:
            attempt_number = retry_state.attempt_number
            wait_time = retry_state.next_action.sleep if retry_state.next_action else 0
            self.retry_attempt.emit(attempt_number, wait_time)
    
    def _make_api_call(self):
        """Make the API call with retry logic"""
        if not self.api_key:
            raise ValueError("API key not found. Please configure it in settings.")
        
        # Initialize client with API key
        client = genai.Client(api_key=self.api_key)
        
        # Prepare contents - text only or multimodal (text + image)
        if self.image_path and os.path.exists(self.image_path):
            # Load image for multimodal request
            image = Image.open(self.image_path)
            contents = [self.message, image]
        else:
            contents = self.message
        
        # Make API call with retry decorator
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=2, max=10),
            retry=retry_if_exception(self._is_service_unavailable),
        )
        def _call_api():
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents
            )
            return response
        
        response = _call_api()
        
        # Extract response text
        response_text = response.text if hasattr(response, 'text') else str(response)
        return response_text
    
    def run(self):
        """Execute the API call in the background thread"""
        try:
            response_text = self._make_api_call()
            self.response_received.emit(response_text)
            
        except ValueError as e:
            # API key error
            self.error_occurred.emit(str(e))
            
        except Exception as e:
            # Check error type
            error_msg = str(e)
            if "404" in error_msg:
                # Model ID mismatch
                self.error_occurred.emit("Model ID mismatch (404). The model version may not be supported.")
            elif self._is_service_unavailable(e):
                # This should only happen if all retries failed
                self.error_occurred.emit("Server is busy. All retry attempts failed. Please try again later.")
            else:
                self.error_occurred.emit(f"Error: {error_msg}")


class CircularWindow(QWidget):
    def __init__(self):
        super().__init__()
        # State management
        self.is_expanded = False
        self.bubble_position = None
        self.mouse_press_pos = None
        self.dragPosition = None
        self.is_dragging = False
        
        # API worker thread
        self.gemini_worker = None
        
        # API key stored in memory (session only)
        self.api_key = None
        
        self.initUI()
        
        # Show API key dialog on startup if no key is set
        if not self.api_key:
            self.showAPIKeyDialog()
    
    def initUI(self):
        # Set initial window size (bubble state)
        self.setFixedSize(50, 50)
        
        # Make window frameless
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |  # Always on top
            Qt.FramelessWindowHint |   # Remove window frame
            Qt.Tool                    # Keep above all windows
        )
        
        # Make window transparent for circular shape
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set window title
        self.setWindowTitle('AI Assistant')
        
        # Center window on screen
        self.centerWindow()
        
        # Initialize chat UI components (hidden initially)
        self.setupChatUI()
    
    def centerWindow(self):
        # Get screen geometry
        screen = QApplication.primaryScreen().geometry()
        # Calculate center position
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def setupChatUI(self):
        """Setup chat UI components (hidden when in bubble state)"""
        # Main layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)
        
        # Custom title bar
        self.title_bar = self.createTitleBar()
        self.main_layout.addWidget(self.title_bar)
        
        # Chat message area
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("background-color: white; border: none;")
        
        self.message_area = QTextEdit()
        self.message_area.setReadOnly(True)
        self.message_area.setStyleSheet("background-color: white; border: none; padding: 10px;")
        self.chat_scroll.setWidget(self.message_area)
        self.main_layout.addWidget(self.chat_scroll)
        
        # Input area
        self.input_layout = QHBoxLayout()
        self.input_layout.setContentsMargins(10, 10, 10, 10)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message...")
        self.input_field.returnPressed.connect(self.sendMessage)
        self.input_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Send")
        self.send_button.setFixedWidth(60)
        self.send_button.clicked.connect(self.sendMessage)
        self.input_layout.addWidget(self.send_button)
        
        # Screenshot button
        self.screenshot_button = QPushButton("Screenshot")
        self.screenshot_button.setFixedWidth(90)
        self.screenshot_button.clicked.connect(self.captureScreenshot)
        self.input_layout.addWidget(self.screenshot_button)
        
        self.input_container = QWidget()
        self.input_container.setLayout(self.input_layout)
        self.input_container.setStyleSheet("background-color: #f0f0f0;")
        self.main_layout.addWidget(self.input_container)
        
        # Hide chat UI initially
        self.title_bar.hide()
        self.chat_scroll.hide()
        self.input_container.hide()
    
    def createTitleBar(self):
        """Create custom title bar with AI Assistant text and close button"""
        title_bar = QWidget()
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet("background-color: #2c3e50; color: white;")
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(0)
        
        # Title label
        title_label = QLabel("AI Assistant")
        title_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Close button (minimize to bubble)
        close_button = QPushButton("×")
        close_button.setFixedSize(25, 25)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                font-size: 20px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
        """)
        close_button.clicked.connect(self.minimizeToBubble)
        layout.addWidget(close_button)
        
        title_bar.setLayout(layout)
        
        # Enable dragging from title bar
        title_bar.mousePressEvent = self.titleBarMousePress
        title_bar.mouseMoveEvent = self.titleBarMouseMove
        
        return title_bar
    
    def titleBarMousePress(self, event):
        """Handle mouse press on title bar for dragging"""
        if event.button() == Qt.LeftButton:
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def titleBarMouseMove(self, event):
        """Handle mouse move on title bar for dragging"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'dragPosition'):
            if self.is_expanded:
                self.move(event.globalPos() - self.dragPosition)
            event.accept()
    
    def expandToChat(self):
        """Expand bubble to chat window"""
        if self.is_expanded:
            return
        
        # Store bubble position
        self.bubble_position = self.pos()
        
        # Remove transparent background attribute for expanded state
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # Show chat UI
        self.title_bar.show()
        self.chat_scroll.show()
        self.input_container.show()
        
        # Change window flags (keep frameless for custom title bar)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # Resize to chat window size
        current_pos = self.pos()
        self.setFixedSize(400, 600)
        
        # Adjust position to keep top-left corner in place
        self.move(current_pos)
        
        # Update state
        self.is_expanded = True
        
        # Refresh window
        self.show()
        self.update()  # Force repaint
        self.input_field.setFocus()
    
    def minimizeToBubble(self):
        """Minimize chat window back to bubble"""
        if not self.is_expanded:
            return
        
        # Hide chat UI
        self.title_bar.hide()
        self.chat_scroll.hide()
        self.input_container.hide()
        
        # Restore transparent background for circular shape
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Restore frameless window flags
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # Resize back to bubble
        self.setFixedSize(50, 50)
        
        # Restore bubble position or use current position
        if self.bubble_position:
            self.move(self.bubble_position)
        else:
            # Center if no saved position
            self.centerWindow()
        
        # Update state
        self.is_expanded = False
        
        # Refresh window
        self.show()
        self.update()  # Force repaint
    
    def sendMessage(self):
        """Handle sending a message"""
        message = self.input_field.text().strip()
        if not message:
            return
        
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        
        # Add user message to chat
        self.message_area.append(f"<b>You:</b> {message}")
        self.input_field.clear()
        
        # Show loading indicator
        self.message_area.append("<i>AI is typing...</i>")
        
        # Scroll to bottom
        self.scrollToBottom()
        
        # Check if API key is available
        if not self.api_key:
            self.message_area.append("<b>AI:</b> <span style='color: red;'>Error: API key not configured. Please set it in settings.</span>")
            self.scrollToBottom()
            self.input_field.setEnabled(True)
            self.send_button.setEnabled(True)
            return
        
        # Create and start worker thread
        self.gemini_worker = GeminiWorker(message, self.api_key)
        self.gemini_worker.response_received.connect(self.onAIResponse)
        self.gemini_worker.error_occurred.connect(self.onAIError)
        self.gemini_worker.retry_attempt.connect(self.onRetryAttempt)
        self.gemini_worker.finished.connect(self.onWorkerFinished)
        self.gemini_worker.start()
    
    def onAIResponse(self, response_text):
        """Handle successful AI response"""
        # Remove loading indicator
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        # Add AI response
        self.message_area.append(f"<b>AI:</b> {response_text}")
        self.scrollToBottom()
    
    def onRetryAttempt(self, attempt_number, wait_time):
        """Handle retry attempt - show user feedback"""
        # Update loading indicator with retry message
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        # Show retry message
        wait_seconds = int(wait_time) if wait_time >= 1 else round(wait_time, 1)
        self.message_area.append(f"<i>Server busy, retrying... (Attempt {attempt_number}, waiting {wait_seconds}s)</i>")
        self.scrollToBottom()
    
    def onAIError(self, error_message):
        """Handle API error"""
        # Remove loading indicator
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        # Add error message
        self.message_area.append(f"<b>AI:</b> <span style='color: red;'>{error_message}</span>")
        self.scrollToBottom()
    
    def onWorkerFinished(self):
        """Called when worker thread finishes"""
        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.input_field.setFocus()
    
    def scrollToBottom(self):
        """Scroll chat area to bottom"""
        scrollbar = self.message_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def captureScreenshot(self):
        """Capture full screen screenshot and send to AI for analysis"""
        try:
            # Store current window state
            was_expanded = self.is_expanded
            window_pos = self.pos()
            
            # Temporarily hide the window
            self.hide()
            
            # Small delay to ensure window is fully hidden
            QApplication.processEvents()
            
            # Capture full screen
            screenshot = ImageGrab.grab()
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            
            # Save to temp directory
            temp_dir = tempfile.gettempdir()
            filepath = os.path.join(temp_dir, filename)
            screenshot.save(filepath, "PNG")
            
            # Store the screenshot path for AI analysis
            self.last_screenshot_path = filepath
            
            # Restore window
            self.show()
            self.raise_()
            self.activateWindow()
            
            # Restore window state if it was expanded
            if was_expanded:
                # Ensure window is still expanded
                if not self.is_expanded:
                    self.expandToChat()
                self.move(window_pos)
            else:
                # Expand to show the analysis
                self.expandToChat()
            
            # Show confirmation and send to AI for analysis
            self.message_area.append(f"<b>System:</b> Screenshot captured: <code>{filepath}</code>")
            self.message_area.append("<i>Analyzing screenshot...</i>")
            self.scrollToBottom()
            
            # Send screenshot to AI for analysis
            self.analyzeScreenshot(filepath)
                
        except Exception as e:
            # Show error message
            self.show()
            self.raise_()
            if not self.is_expanded:
                self.expandToChat()
            self.message_area.append(f"<b>System:</b> <span style='color: red;'>Error capturing screenshot: {str(e)}</span>")
            self.scrollToBottom()
    
    def analyzeScreenshot(self, filepath):
        """Send screenshot to AI for analysis"""
        if not self.api_key:
            self.message_area.append("<b>AI:</b> <span style='color: red;'>Error: API key not configured.</span>")
            self.scrollToBottom()
            return
        
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.screenshot_button.setEnabled(False)
        
        # Create and start worker thread with image
        prompt = "Describe what you see in this screenshot. Be brief and focus on the main content visible."
        self.gemini_worker = GeminiWorker(prompt, self.api_key, image_path=filepath)
        self.gemini_worker.response_received.connect(self.onScreenshotAnalyzed)
        self.gemini_worker.error_occurred.connect(self.onAIError)
        self.gemini_worker.retry_attempt.connect(self.onRetryAttempt)
        self.gemini_worker.finished.connect(self.onScreenshotWorkerFinished)
        self.gemini_worker.start()
    
    def onScreenshotAnalyzed(self, response_text):
        """Handle screenshot analysis response"""
        # Remove "Analyzing..." indicator
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        # Add AI analysis
        self.message_area.append(f"<b>AI:</b> {response_text}")
        self.scrollToBottom()
    
    def onScreenshotWorkerFinished(self):
        """Called when screenshot worker thread finishes"""
        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.screenshot_button.setEnabled(True)
        self.input_field.setFocus()
    
    def showAPIKeyDialog(self):
        """Show API key dialog and store the key"""
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.api_key = dialog.getApiKey()
        else:
            # User cancelled - show error and exit or retry
            from PyQt5.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("API Key Required")
            msg.setText("API key is required to use this application.")
            msg.setInformativeText("The application will now exit. Please restart and enter your API key.")
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
            msg.exec_()
            sys.exit(0)
    
    def paintEvent(self, event):
        # Only draw circle when in bubble state
        if not self.is_expanded:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw circular background
            brush = QBrush(QColor(100, 150, 200, 255))  # Blue color
            painter.setBrush(brush)
            painter.setPen(Qt.NoPen)
            
            # Draw circle
            painter.drawEllipse(0, 0, 50, 50)
        else:
            # Draw background for expanded window
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor(255, 255, 255))
    
    def mousePressEvent(self, event):
        """Handle mouse press - distinguish between click and drag"""
        if event.button() == Qt.LeftButton:
            self.mouse_press_pos = event.globalPos()
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            self.is_dragging = False
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move - detect drag vs click"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'dragPosition'):
            # Calculate movement distance
            if self.mouse_press_pos:
                delta = (event.globalPos() - self.mouse_press_pos).manhattanLength()
                
                # If moved more than 5 pixels, it's a drag
                if delta > 5:
                    self.is_dragging = True
                    # Only allow dragging when minimized (bubble state)
                    if not self.is_expanded:
                        self.move(event.globalPos() - self.dragPosition)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release - expand on click if not dragging"""
        if event.button() == Qt.LeftButton:
            if not self.is_dragging and not self.is_expanded:
                # Single click on bubble - expand
                self.expandToChat()
            self.is_dragging = False
            self.mouse_press_pos = None
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CircularWindow()
    window.show()
    sys.exit(app.exec_())
