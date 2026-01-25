import sys
import os
import tempfile
import io
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea, QDialog, QSizeGrip)
from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal, QRect, QSize, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import (QPainter, QBrush, QColor, QFont, QLinearGradient, 
                        QPen, QPainterPath, QFontMetrics, QGradient)
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGraphicsBlurEffect
from google import genai
from PIL import ImageGrab, Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, RetryCallState


class GlassmorphismTitleBar(QWidget):
    """Title bar with minimalist floating design"""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        radius = 28  # Matches window radius
        
        # Subtle glass tint for the header area
        glass_brush = QBrush(QColor(255, 255, 255, 10))
        border_pen = QPen(QColor(255, 255, 255, 15), 1)
        
        # Rounded top corners path
        path = QPainterPath()
        path.moveTo(0, radius)
        path.arcTo(0, 0, radius * 2, radius * 2, 180, -90)
        path.lineTo(rect.width() - radius, 0)
        path.arcTo(rect.width() - radius * 2, 0, radius * 2, radius * 2, 90, -90)
        path.lineTo(rect.width(), rect.height())
        path.lineTo(0, rect.height())
        path.closeSubpath()
        
        painter.setBrush(glass_brush)
        painter.setPen(border_pen)
        painter.drawPath(path)


class IconButton(QPushButton):
    """Custom button that paints line-art icons"""
    def __init__(self, icon_type, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        # Smaller size for close icon
        if icon_type == "close":
            self.icon_size = 14
        else:
            self.icon_size = 24
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get icon path
        icon_path = self.createIconPath(self.icon_type, self.icon_size)
        
        # Center icon in button - account for boundingRect origin
        button_rect = self.rect()
        icon_rect = icon_path.boundingRect()
        x_offset = (button_rect.width() - icon_rect.width()) / 2 - icon_rect.x()
        y_offset = (button_rect.height() - icon_rect.height()) / 2 - icon_rect.y()
        
        painter.translate(x_offset, y_offset)
        
        # Set pen for line-art style
        if self.icon_type == "send":
            pen = QPen(QColor(255, 255, 255, 255), 2.5)
        elif self.icon_type == "close":
            pen = QPen(QColor(255, 255, 255, 220), 1.5)  # Thinner for close
        else:
            pen = QPen(QColor(255, 255, 255, 220), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        painter.drawPath(icon_path)
    
    def createIconPath(self, icon_type, size):
        """Create line-art icon path"""
        path = QPainterPath()
        half_size = size // 2
        
        if icon_type == "send":
            # Paper plane icon - slightly adjusted for minimalism
            path.moveTo(size * 0.1, half_size)
            path.lineTo(half_size * 0.8, size * 0.9)
            path.lineTo(half_size, size)
            path.lineTo(half_size * 1.2, size * 0.9)
            path.lineTo(size * 0.9, half_size)
            path.lineTo(half_size, half_size * 1.1)
            path.closeSubpath()
        elif icon_type == "camera":
            # Camera icon
            path.addRoundedRect(4, 6, size - 8, size - 10, 2, 2)
            path.addEllipse(half_size - 3, half_size - 1, 6, 6)
        elif icon_type == "close":
            # Minimalist X - draw from origin for proper centering
            path.moveTo(0, 0)
            path.lineTo(size, size)
            path.moveTo(size, 0)
            path.lineTo(0, size)
        elif icon_type == "home":
            # Simple home icon
            path.moveTo(half_size, 4)
            path.lineTo(4, half_size)
            path.lineTo(6, half_size)
            path.lineTo(6, size - 4)
            path.lineTo(size - 6, size - 4)
            path.lineTo(size - 6, half_size)
            path.lineTo(size - 4, half_size)
            path.closeSubpath()
        elif icon_type == "sparkle":
            # Simple sparkle/star
            path.moveTo(half_size, 2)
            path.lineTo(half_size, size - 2)
            path.moveTo(2, half_size)
            path.lineTo(size - 2, half_size)
        
        return path


class GradientSendButton(IconButton):
    """Send button with minimalist white icon and dark glow"""
    def __init__(self, parent=None):
        super().__init__("send", parent)
        self.glow_effect = QGraphicsDropShadowEffect()
        self.glow_effect.setBlurRadius(15)
        self.glow_effect.setColor(QColor(255, 255, 255, 30))
        self.glow_effect.setOffset(0, 0)
        self.setGraphicsEffect(self.glow_effect)
    
    def enterEvent(self, event):
        """Increase glow on hover"""
        self.glow_effect.setBlurRadius(25)
        self.glow_effect.setColor(QColor(138, 43, 226, 200))
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Restore base glow on leave"""
        self.glow_effect.setBlurRadius(15)
        self.glow_effect.setColor(QColor(255, 255, 255, 30))
        super().leaveEvent(event)


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
        
        # Robot face animation state
        self._pulse_value = 0.0  # For glow pulse animation
        self._is_hovered = False
        
        # Pulse animation timer for subtle glow
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._updatePulse)
        self.pulse_timer.start(50)  # 20 FPS for smooth animation
        
        # Dark Mode Glassmorphism colors - Enhanced for minimalist floating look
        self.charcoal_color = QColor(20, 20, 20, 180)  # Extended alpha for transparency
        self.onyx_color = QColor(10, 10, 10, 180)      # Extended alpha for transparency
        self.dark_glass = QColor(0, 0, 0, 100)    # Increased opacity for better contrast with transparent bg
        self.border_white = QColor(255, 255, 255, 30) # Thinner border
        self.rim_light = QColor(255, 255, 255, 15)  # Even more subtle rim lighting
        
        # Robot face colors
        self.robot_primary = QColor(100, 180, 255)  # Soft blue for eyes
        self.robot_glow = QColor(120, 200, 255, 80)  # Glow effect
        
        self.initUI()
        
        # Show API key dialog on startup if no key is set
        if not self.api_key:
            self.showAPIKeyDialog()
    
    def initUI(self):
        # Set initial window size (bubble state)
        self.setFixedSize(40, 40)
        
        # Make window frameless
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |  # Always on top
            Qt.FramelessWindowHint |   # Remove window frame
            Qt.Tool                    # Keep above all windows
        )
        
        # Make window transparent for circular shape and glassmorphism
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
        """Setup integrated capsule input UI"""
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
        self.chat_scroll.setFrameShape(QScrollArea.NoFrame)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        self.message_area = QTextEdit()
        self.message_area.setReadOnly(True)
        self.message_area.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                padding: 15px 25px;
                color: rgba(255, 255, 255, 0.9);
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
        """)
        self.chat_scroll.setWidget(self.message_area)
        self.main_layout.addWidget(self.chat_scroll)
        
        # Integrated Capsule Input area
        self.input_container = QWidget()
        self.input_container.setFixedHeight(60)
        
        container_layout = QHBoxLayout(self.input_container)
        container_layout.setContentsMargins(10, 0, 10, 10)
        
        # The Capsule
        self.capsule = QWidget()
        self.capsule.setFixedHeight(50)
        self.capsule.setStyleSheet("""
            QWidget#capsule {
                background: rgba(0, 0, 0, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 25px;
            }
        """)
        self.capsule.setObjectName("capsule")
        
        capsule_layout = QHBoxLayout(self.capsule)
        capsule_layout.setContentsMargins(15, 0, 5, 0)
        capsule_layout.setSpacing(8)
        capsule_layout.setAlignment(Qt.AlignVCenter)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask about your screen or conversation...")
        self.input_field.returnPressed.connect(self.sendMessage)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: white;
                font-size: 13px;
                padding: 0;
            }
        """)
        capsule_layout.addWidget(self.input_field)
        
        # Small buttons inside capsule
        self.screenshot_button = IconButton("camera", self.capsule)
        self.screenshot_button.setFixedSize(36, 36)
        self.screenshot_button.setStyleSheet("background: transparent; border-radius: 18px;")
        self.screenshot_button.clicked.connect(self.captureScreenshot)
        capsule_layout.addWidget(self.screenshot_button)
        
        self.send_button = GradientSendButton(self.capsule)
        self.send_button.setFixedSize(36, 36)
        self.send_button.clicked.connect(self.sendMessage)
        self.send_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)
        capsule_layout.addWidget(self.send_button)
        
        container_layout.addWidget(self.capsule)
        self.main_layout.addWidget(self.input_container)
        
        # Add Resising Grip
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent; width: 20px; height: 20px;")
        # Position it in the bottom right corner overlapping the layout
        
        # Hide chat UI initially
        self.title_bar.hide()
        self.chat_scroll.hide()
        self.input_container.hide()
        self.size_grip.hide()
    
    def resizeEvent(self, event):
        """Handle resize event to position size grip"""
        if hasattr(self, 'size_grip'):
            rect = self.rect()
            self.size_grip.move(rect.right() - 20, rect.bottom() - 20)
        super().resizeEvent(event)
    
    def createTitleBar(self):
        """Create minimalist header with only Close button"""
        title_bar = GlassmorphismTitleBar(self)
        title_bar.setFixedHeight(46)  # Slightly shorter header
        
        layout = QHBoxLayout()
        # Margins: (left, top, right, bottom)
        # Adjust these values to move the button
        layout.setContentsMargins(0, 5, 14, 0) 
        layout.setSpacing(10)
        
        layout.addStretch()
        
        # Minimalist Close button - smaller size
        close_button = IconButton("close", title_bar)
        close_button.setFixedSize(20, 20)
        close_button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
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
        
        # Keep transparent background for glassmorphism
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Show chat UI
        self.title_bar.show()
        self.chat_scroll.show()
        self.input_container.show()
        self.size_grip.show()
        
        # Change window flags (keep frameless for custom title bar)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # Resize to floating widget size - RESIZEABLE and SMALLER
        current_pos = self.pos()
        self.setMinimumSize(260, 320) # Minimum usable size
        self.resize(280, 380)  # Initial compact size
        
        # Adjust position to keep it floating nicely
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
        self.size_grip.hide()
        
        # Restore transparent background for circular shape
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Restore frameless window flags
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # Resize back to bubble
        self.setFixedSize(40, 40)
        
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
        
        # Add user message with minimalist floating style
        user_message = f"""
        <div style="margin: 8px 0; text-align: right;">
            <span style="background: rgba(0, 100, 255, 0.4); 
                        border: 1px solid rgba(255, 255, 255, 0.1); 
                        border-radius: 18px; 
                        padding: 8px 16px; 
                        color: white;
                        display: inline-block;">
                {message}
            </span>
        </div>
        """
        self.message_area.append(user_message)
        self.input_field.clear()
        
        # Show loading indicator with minimalist style
        loading_msg = """
        <div style="margin: 8px 0; color: rgba(255, 255, 255, 0.5); font-style: italic;">
            AI is thinking...
        </div>
        """
        self.message_area.append(loading_msg)
        
        # Scroll to bottom
        self.scrollToBottom()
        
        # Check if API key is available
        if not self.api_key:
            error_msg = """
            <div style="background: rgba(255, 100, 100, 0.2); 
                        border: 1px solid rgba(255, 150, 150, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        margin-right: 60px;
                        color: rgba(255, 200, 200, 0.95);">
                <b>AI:</b> Error: API key not configured. Please set it in settings.
            </div>
            """
            self.message_area.append(error_msg)
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
        
        # Add AI response with minimalist styling
        ai_message = f"""
        <div style="margin: 12px 0; margin-right: 40px;">
            <div style="color: rgba(255, 255, 255, 0.95); line-height: 1.4;">
                {response_text}
            </div>
        </div>
        """
        self.message_area.append(ai_message)
        self.scrollToBottom()
    
    def onRetryAttempt(self, attempt_number, wait_time):
        """Handle retry attempt - show user feedback"""
        # Update loading indicator with retry message
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        # Show retry message with glassmorphism styling
        wait_seconds = int(wait_time) if wait_time >= 1 else round(wait_time, 1)
        retry_msg = f"""
        <div style="background: rgba(255, 255, 255, 0.1); 
                    border-radius: 16px; 
                    padding: 12px 16px; 
                    margin: 8px 0; 
                    margin-right: 60px;
                    color: rgba(255, 255, 255, 0.7);">
            <i>Server busy, retrying... (Attempt {attempt_number}, waiting {wait_seconds}s)</i>
        </div>
        """
        self.message_area.append(retry_msg)
        self.scrollToBottom()
    
    def onAIError(self, error_message):
        """Handle API error"""
        # Remove loading indicator
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        # Add error message with glassmorphism styling
        error_msg = f"""
        <div style="background: rgba(255, 100, 100, 0.2); 
                    border: 1px solid rgba(255, 150, 150, 0.4); 
                    border-radius: 16px; 
                    padding: 12px 16px; 
                    margin: 8px 0; 
                    margin-right: 60px;
                    color: rgba(255, 200, 200, 0.95);">
            <b>AI:</b> {error_message}
        </div>
        """
        self.message_area.append(error_msg)
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
            system_msg = f"""
            <div style="background: rgba(255, 255, 255, 0.1); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(255, 255, 255, 0.8);">
                <b>System:</b> Screenshot captured: <code style="background: rgba(0, 0, 0, 0.2); padding: 2px 6px; border-radius: 4px;">{filepath}</code>
            </div>
            """
            self.message_area.append(system_msg)
            analyzing_msg = """
            <div style="background: rgba(255, 255, 255, 0.1); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        margin-right: 60px;
                        color: rgba(255, 255, 255, 0.7);">
                <i>Analyzing screenshot...</i>
            </div>
            """
            self.message_area.append(analyzing_msg)
            self.scrollToBottom()
            
            # Send screenshot to AI for analysis
            self.analyzeScreenshot(filepath)
                
        except Exception as e:
            # Show error message
            self.show()
            self.raise_()
            if not self.is_expanded:
                self.expandToChat()
            error_msg = f"""
            <div style="background: rgba(255, 100, 100, 0.2); 
                        border: 1px solid rgba(255, 150, 150, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(255, 200, 200, 0.95);">
                <b>System:</b> Error capturing screenshot: {str(e)}
            </div>
            """
            self.message_area.append(error_msg)
            self.scrollToBottom()
    
    def analyzeScreenshot(self, filepath):
        """Send screenshot to AI for analysis"""
        if not self.api_key:
            error_msg = """
            <div style="background: rgba(255, 100, 100, 0.2); 
                        border: 1px solid rgba(255, 150, 150, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        margin-right: 60px;
                        color: rgba(255, 200, 200, 0.95);">
                <b>AI:</b> Error: API key not configured.
            </div>
            """
            self.message_area.append(error_msg)
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
        
        # Add AI analysis with glassmorphism styling
        ai_message = f"""
        <div style="background: rgba(255, 255, 255, 0.12); 
                    border: 1px solid rgba(255, 255, 255, 0.25); 
                    border-radius: 16px; 
                    padding: 12px 16px; 
                    margin: 8px 0; 
                    margin-right: 60px;
                    color: rgba(255, 255, 255, 0.95);">
            <b style="color: rgba(255, 255, 255, 0.9);">AI:</b> {response_text}
        </div>
        """
        self.message_area.append(ai_message)
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        if not self.is_expanded:
            # Draw glassmorphism bubble
            self.paintBubble(painter)
        else:
            # Draw glassmorphism chat window
            self.paintChatWindow(painter)
    
    def _updatePulse(self):
        """Update pulse animation value for subtle glow effect"""
        import math
        self._pulse_value += 0.03
        if self._pulse_value >= 1.0:
            self._pulse_value = 0.0
        if not self.is_expanded:
            self.update()
    
    def enterEvent(self, event):
        """Handle mouse enter for hover effect"""
        self._is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave"""
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def paintBubble(self, painter):
        """Paint cute robot mascot with white body, dark visor, and bar eyes"""
        import math
        size = 32  # Smaller, compact icon
        center_x, center_y = size // 2, size // 2
        
        # Calculate pulse effect
        pulse = (math.sin(self._pulse_value * 2 * math.pi) + 1) / 2
        
        # === WHITE BODY (outer shell - more circular) ===
        body_gradient = QLinearGradient(0, 0, 0, size)
        body_gradient.setColorAt(0, QColor(255, 255, 255, 255))
        body_gradient.setColorAt(1, QColor(230, 235, 240, 255))
        
        painter.setPen(QPen(QColor(200, 205, 215, 180), 1))
        painter.setBrush(QBrush(body_gradient))
        
        # Draw rounded body (more circular with larger radius)
        body_path = QPainterPath()
        body_path.addRoundedRect(2, 4, size - 4, size - 6, 12, 12)
        painter.drawPath(body_path)
        
        # === SMALL EARS ===
        ear_color = QColor(240, 245, 250, 255)
        painter.setPen(QPen(QColor(200, 205, 215, 150), 1))
        painter.setBrush(QBrush(ear_color))
        
        # Left ear
        left_ear = QPainterPath()
        left_ear.moveTo(6, 10)
        left_ear.lineTo(2, 4)
        left_ear.lineTo(10, 8)
        left_ear.closeSubpath()
        painter.drawPath(left_ear)
        
        # Right ear
        right_ear = QPainterPath()
        right_ear.moveTo(size - 6, 10)
        right_ear.lineTo(size - 2, 4)
        right_ear.lineTo(size - 10, 8)
        right_ear.closeSubpath()
        painter.drawPath(right_ear)
        
        # === TOP ANTENNA/LIGHT BAR (cyan glow) ===
        antenna_alpha = 180 + int(pulse * 75)
        antenna_color = QColor(80, 200, 255, antenna_alpha)
        antenna_pen = QPen(antenna_color, 2)
        antenna_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(antenna_pen)
        painter.setBrush(Qt.NoBrush)
        
        antenna_path = QPainterPath()
        antenna_path.moveTo(center_x - 8, 5)
        antenna_path.quadTo(center_x, 2, center_x + 8, 5)
        painter.drawPath(antenna_path)
        
        # === DARK VISOR ===
        visor_gradient = QLinearGradient(5, 10, size - 5, size - 12)
        visor_gradient.setColorAt(0, QColor(50, 55, 70, 255))
        visor_gradient.setColorAt(0.3, QColor(40, 45, 60, 255))
        visor_gradient.setColorAt(0.6, QColor(55, 60, 75, 255))
        visor_gradient.setColorAt(1, QColor(45, 50, 65, 255))
        
        painter.setPen(QPen(QColor(70, 80, 100, 200), 1))
        painter.setBrush(QBrush(visor_gradient))
        
        visor_path = QPainterPath()
        visor_path.addRoundedRect(6, 10, size - 12, size - 18, 6, 6)
        painter.drawPath(visor_path)
        
        # Diagonal shine lines on visor
        shine_pen = QPen(QColor(80, 90, 110, 60), 1)
        painter.setPen(shine_pen)
        painter.drawLine(10, 12, 18, 22)
        painter.drawLine(14, 11, 24, 23)
        painter.drawLine(20, 11, 30, 21)
        
        # === HORIZONTAL BAR EYES ===
        eye_y = center_y - 1
        eye_width = 6
        eye_height = 2
        eye_spacing = 10
        
        eye_alpha = 200 + int(pulse * 55)
        eye_color = QColor(80, 220, 255, eye_alpha)
        eye_glow = QColor(80, 220, 255, 80 + int(pulse * 50))
        
        left_eye_x = center_x - eye_spacing // 2 - eye_width // 2
        right_eye_x = center_x + eye_spacing // 2 - eye_width // 2
        
        # Eye glow
        glow_pen = QPen(eye_glow, 2)
        glow_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(left_eye_x - 1, eye_y - 1, eye_width + 2, eye_height + 2, 2, 2)
        painter.drawRoundedRect(right_eye_x - 1, eye_y - 1, eye_width + 2, eye_height + 2, 2, 2)
        
        # Eye fill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(eye_color))
        painter.drawRoundedRect(left_eye_x, eye_y, eye_width, eye_height, 1, 1)
        painter.drawRoundedRect(right_eye_x, eye_y, eye_width, eye_height, 1, 1)
        
        # === SMALL SAD/NEUTRAL MOUTH ===
        mouth_y = center_y + 6
        mouth_alpha = 180 + int(pulse * 75)
        mouth_color = QColor(80, 220, 255, mouth_alpha)
        mouth_pen = QPen(mouth_color, 1.5)
        mouth_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(mouth_pen)
        painter.setBrush(Qt.NoBrush)
        
        mouth_path = QPainterPath()
        mouth_path.moveTo(center_x - 4, mouth_y)
        mouth_path.quadTo(center_x, mouth_y + 2, center_x + 4, mouth_y)
        painter.drawPath(mouth_path)
    
    def paintChatWindow(self, painter):
        """Paint minimalist dark mode glassmorphism chat window"""
        rect = self.rect()
        radius = 28.0  # Slightly more rounded for floating feel
        
        # Create rounded rect path for clipping
        clip_path = QPainterPath()
        clip_path.addRoundedRect(0.0, 0.0, float(rect.width()), float(rect.height()), radius, radius)
        
        # Clip painter so everything drawn stays within rounded corners
        painter.setClipPath(clip_path)
        
        # Draw base gradient (very dark and subtle)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, self.charcoal_color)
        gradient.setColorAt(1, self.onyx_color)
        painter.fillRect(rect, QBrush(gradient))
        
        # Glassmorphism container path
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(rect.width()), float(rect.height()), radius, radius)
        
        # Minimal translucent fill
        painter.setBrush(QBrush(self.dark_glass))
        painter.setPen(QPen(self.border_white, 1))
        painter.drawPath(path)
        
        # Very subtle rim lighting
        inner_path = QPainterPath()
        inner_path.addRoundedRect(0.5, 0.5, float(rect.width() - 1), float(rect.height() - 1), radius - 0.5, radius - 0.5)
        painter.setPen(QPen(self.rim_light, 0.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(inner_path)
    
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
    # Enable high DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Set modern sans-serif font as default
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    
    window = CircularWindow()
    window.show()
    sys.exit(app.exec_())
