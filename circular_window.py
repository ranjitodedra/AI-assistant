import sys
import os
import tempfile
import io
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea, QDialog, QSizeGrip, QMenu)
from PyQt5.QtGui import QCursor, QGuiApplication
from PyQt5.QtCore import Qt, QPoint, QThread, pyqtSignal, QRect, QSize, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QObject
from PyQt5.QtGui import (QPainter, QBrush, QColor, QFont, QLinearGradient, 
                        QPen, QPainterPath, QFontMetrics, QGradient)
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGraphicsBlurEffect
from google import genai
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
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
        elif icon_type == "eye":
            # Eye icon for monitoring toggle
            path.addEllipse(2, half_size - 4, size - 4, 8)  # Eye outline
            path.addEllipse(half_size - 3, half_size - 3, 6, 6)  # Pupil
        
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
    
    def __init__(self, message, api_key, image_path=None, image_data=None, system_prompt=None):
        super().__init__()
        self.message = message
        self.api_key = api_key
        self.image_path = image_path  # Optional image file path
        self.image_data = image_data  # Optional PIL Image object (direct buffer)
        self.system_prompt = system_prompt # Optional system prompt override
    
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
        if not self.api_key or not isinstance(self.api_key, str) or len(self.api_key.strip()) < 10:
            raise ValueError("API key not found or invalid. Please configure it in settings.")
        
        # Flush stdout before API call to prevent buffer pollution
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Initialize client with API key
        client = genai.Client(api_key=self.api_key.strip())
        
        # Prepare contents
        contents = []
        
        # Add system prompt if provided (prepended to message)
        final_message = self.message
        if self.system_prompt:
            # Only format when the placeholder is present; avoids JSON brace errors
            if "{user_message}" in self.system_prompt:
                final_message = self.system_prompt.format(user_message=self.message)
            else:
                final_message = self.system_prompt
            
        contents.append(final_message)
        
        # Add image from path
        if self.image_path and os.path.exists(self.image_path):
            image = Image.open(self.image_path)
            contents.append(image)
        # Add image from buffer (PIL object)
        elif self.image_data:
            contents.append(self.image_data)
        
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


class AnalysisWorker(QThread):
    """Worker thread for silent background screen analysis"""
    finished = pyqtSignal(str)
    
    def __init__(self, image, api_key):
        super().__init__()
        self.image = image
        self.api_key = api_key
        
    def run(self):
        # Guard: API key must be a non-empty string
        if not self.api_key or not isinstance(self.api_key, str) or len(self.api_key.strip()) < 10:
            self.finished.emit("Analysis skipped: Invalid API key")
            return
            
        try:
            # Flush stdout before API call to prevent buffer pollution
            sys.stdout.flush()
            sys.stderr.flush()
            
            client = genai.Client(api_key=self.api_key.strip())
            prompt = "Analyze this screen. What application is this? What is the user trying to do? List key UI elements (buttons, menus, input fields) with their approximate screen positions."
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt, self.image]
            )
            self.finished.emit(response.text)
        except Exception as e:
            # Log error but don't pollute stdout
            self.finished.emit(f"Analysis failed: {str(e)}")


class OverlayShape:
    """Data class for shapes drawn on the overlay"""
    def __init__(self, shape_type, x, y, width, height, color="red", label=None, step=1):
        self.type = shape_type  # "CIRCLE", "RECT", "ARROW"
        self.rect = QRect(int(x), int(y), int(width), int(height))
        self.color_name = color
        self.label = label
        self.step = int(step)
        self.start_time = datetime.now()
        self.opacity = 0.0
        self.max_opacity = 0.9
        self.duration = 20.0  # Longer duration for steps
        self.is_expired = False

class OverlayWindow(QWidget):
    """Transparent full-screen overlay for drawing guidance shapes"""
    def __init__(self):
        super().__init__()
        # Transparent, click-through, always on top
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Full screen geometry (virtual screen for multi-monitor/DPI)
        screen = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(screen.x(), screen.y(), screen.width(), screen.height())
        
        self.shapes = []
        self._pulse_time = 0.0
        self.edit_mode = False
        self._selected_shape = None
        self._drag_offset = None
        
        # Step management
        self.all_shapes = []
        self.current_step = 1
        self.total_steps = 0
        
        # Animation timer (30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateAnimations)
        self.timer.start(33)

    def setEditMode(self, enabled):
        """Enable/disable interactive editing of overlay shapes"""
        self.edit_mode = enabled
        flags = self.windowFlags()
        if enabled:
            flags &= ~Qt.WindowTransparentForInput
        else:
            flags |= Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.show()
        self.update()
        
    def loadShapes(self, shapes):
        """Load a sequence of shapes"""
        self.all_shapes = shapes
        if shapes:
            self.total_steps = max((s.step for s in shapes), default=1)
            self.current_step = 1
            self.updateActiveShapes()
            self.show()
        else:
            self.hide()
            
    def updateActiveShapes(self):
        """Show shapes for current step"""
        now = datetime.now()
        self.shapes = [s for s in self.all_shapes if s.step == self.current_step]
        # Reset start time for fresh fade-in
        for s in self.shapes:
            s.start_time = now
            s.opacity = 0.0
        self.update()
        
    def nextStep(self):
        """Advance to next step or close if finished"""
        if self.current_step < self.total_steps:
            self.current_step += 1
            self.updateActiveShapes()
        else:
            self.closeOverlay()
            
    def closeOverlay(self):
        self.shapes = []
        self.all_shapes = []
        self.hide()
        
    def addShape(self, shape_type, x, y, w, h, color, label=None, step=1):
        # Legacy/direct add capability
        shape = OverlayShape(shape_type, x, y, w, h, color, label, step)
        self.shapes.append(shape)
        self.update()
        
    def clearLayout(self):
        self.shapes = []
        self.all_shapes = []
        self.update()

    def _clampRect(self, rect):
        """Clamp rectangle to overlay bounds"""
        bounds = self.rect()
        x = max(0, min(rect.x(), bounds.width() - 10))
        y = max(0, min(rect.y(), bounds.height() - 10))
        w = max(10, min(rect.width(), bounds.width() - x))
        h = max(10, min(rect.height(), bounds.height() - y))
        return QRect(x, y, w, h)

    def mousePressEvent(self, event):
        if not self.edit_mode or not self.shapes:
            return
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            # Prefer shape under cursor, otherwise first shape
            target = None
            for shape in self.shapes:
                if shape.rect.contains(pos):
                    target = shape
                    break
            if not target:
                target = self.shapes[0]
            self._selected_shape = target
            self._drag_offset = pos - target.rect.topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.edit_mode or not self._selected_shape or not self._drag_offset:
            return
        if event.buttons() == Qt.LeftButton:
            pos = event.pos()
            new_top_left = pos - self._drag_offset
            new_rect = QRect(new_top_left, self._selected_shape.rect.size())
            self._selected_shape.rect = self._clampRect(new_rect)
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event):
        if not self.edit_mode:
            return
        self._selected_shape = None
        self._drag_offset = None

    def wheelEvent(self, event):
        if not self.edit_mode or not self.shapes:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step = 6 if delta > 0 else -6
        shape = self._selected_shape or self.shapes[0]
        rect = shape.rect
        center = rect.center()
        new_w = max(10, rect.width() + step)
        new_h = max(10, rect.height() + step)
        new_rect = QRect(0, 0, new_w, new_h)
        new_rect.moveCenter(center)
        shape.rect = self._clampRect(new_rect)
        self.update()
        
    def updateAnimations(self):
        now = datetime.now()
        active_shapes = []
        has_updates = False
        
        self._pulse_time += 0.1
        
        for shape in self.shapes:
            elapsed = (now - shape.start_time).total_seconds()
            
            # Fade in logic (first 0.3s)
            if elapsed < 0.3:
                shape.opacity = (elapsed / 0.3) * shape.max_opacity
                has_updates = True
            # Fade out logic (last 1s)
            elif elapsed > shape.duration - 1.0:
                remaining = shape.duration - elapsed
                shape.opacity = max(0.0, (remaining / 1.0) * shape.max_opacity)
                has_updates = True
            
            if elapsed < shape.duration:
                active_shapes.append(shape)
            else:
                has_updates = True # Shape expired (removed)
        
        self.shapes = active_shapes
        if has_updates or self.shapes: # Keep updating if shapes exist (for pulse)
            self.update()
            
    def paintEvent(self, event):
        if not self.shapes:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        import math
        # Pulse scale factor (0.95 to 1.05)
        pulse_scale = 1.0 + (math.sin(self._pulse_time) * 0.05)
        
        for shape in self.shapes:
            # Determine color
            c = QColor(shape.color_name)
            if not c.isValid(): c = QColor("red")
            
            # Set opacity
            c.setAlphaF(shape.opacity)
            pen = QPen(c, 3)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            
            # Fill with low opacity
            fill_c = QColor(c)
            fill_c.setAlphaF(shape.opacity * 0.2)
            painter.setBrush(QBrush(fill_c))
            
            # Pulse the size - convert to int for QPainter
            center = shape.rect.center()
            w = int(shape.rect.width() * pulse_scale)
            h = int(shape.rect.height() * pulse_scale)
            x = int(center.x() - w / 2)
            y = int(center.y() - h / 2)
            
            if shape.type == "CIRCLE":
                painter.drawEllipse(x, y, w, h)
            elif shape.type == "RECT":
                painter.drawRoundedRect(x, y, w, h, 8, 8)
            elif shape.type == "ARROW":
                # Draw arrow pointing at center
                # Simple implementation: Triangle pointer
                path = QPainterPath()
                # Assuming rect defines the target area, adjust pointer
                # Points to bottom-right of the rect for 'pointing' effect or center
                # Let's draw an arrow pointing TO the target from bottom-right (cursor style)
                cursor_size = 24 * pulse_scale
                tip = center
                path.moveTo(tip)
                path.lineTo(tip.x() + cursor_size, tip.y() + cursor_size * 0.5)
                path.lineTo(tip.x() + cursor_size * 0.5, tip.y() + cursor_size)
                path.closeSubpath()
                painter.drawPath(path)
            
            # Draw Label
            if shape.label and shape.opacity > 0.4:
                painter.setPen(QColor(255, 255, 255, int(shape.opacity * 255)))
                painter.setBrush(QColor(0, 0, 0, int(shape.opacity * 180)))
                font = painter.font()
                font.setBold(True)
                font.setPointSize(12)
                painter.setFont(font)
                
                fm = QFontMetrics(font)
                text_rect = fm.boundingRect(shape.label)
                text_rect.adjust(-10, -5, 10, 5) # Padding
                text_rect.moveCenter(QPoint(int(center.x()), int(y - 25))) # Place above
                
                painter.drawRoundedRect(text_rect, 5, 5)
                painter.drawText(text_rect, Qt.AlignCenter, shape.label)


class FollowAlongManager:
    """Manages continuous guidance state and verification"""
    def __init__(self, parent):
        self.parent = parent
        self.active = False
        self.last_screen_hash = None
        self.same_screen_count = 0
        self.tts_engine = None
        
        # Guided task state
        self.guided_mode = False
        self.current_task = None  # User's goal (e.g., "open a new document")
        self.current_step = 0  # Which step we're on
        self.total_steps = 0  # Estimated total steps
        self.pending_action = None  # Description of action user needs to take
        self.waiting_for_completion = False  # True when showing overlay, waiting for user action
        self.step_start_hash = None  # Screen hash when step overlay was shown
        
        # Initialize TTS
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            # Set properties (speed, volume)
            self.tts_engine.setProperty('rate', 170)
            self.tts_engine.setProperty('volume', 0.8)
        except ImportError:
            print("pyttsx3 not found. Audio disabled.")
        except Exception as e:
            print(f"TTS Init failed: {e}")

    def start(self):
        self.active = True
        self.last_screen_hash = None
        self.speak("Follow-along mode activated.")

    def stop(self):
        self.active = False
        self.resetGuidedTask()
        self.speak("Guidance stopped.")
    
    def startGuidedTask(self, goal):
        """Start a new guided navigation task"""
        self.guided_mode = True
        self.current_task = goal
        self.current_step = 1
        self.total_steps = 0  # Will be updated from AI response
        self.waiting_for_completion = False
        self.pending_action = None
        self.speak(f"Starting guided task: {goal}")
        print(f"[GuidedNav] Started task: {goal}")
    
    def resetGuidedTask(self):
        """Reset guided task state"""
        self.guided_mode = False
        self.current_task = None
        self.current_step = 0
        self.total_steps = 0
        self.pending_action = None
        self.waiting_for_completion = False
        self.step_start_hash = None
    
    def setStepShown(self, action_description, screen_hash=None):
        """Called when a step overlay is displayed"""
        self.pending_action = action_description
        self.waiting_for_completion = True
        self.step_start_hash = screen_hash
        if action_description:
            self.speak(action_description)
        print(f"[GuidedNav] Step {self.current_step} shown: {action_description}")
    
    def advanceStep(self):
        """Advance to the next step"""
        self.current_step += 1
        self.waiting_for_completion = False
        self.pending_action = None
        print(f"[GuidedNav] Advancing to step {self.current_step}")
    
    def completeTask(self):
        """Mark the guided task as complete"""
        self.speak("Task completed!")
        print(f"[GuidedNav] Task completed: {self.current_task}")
        self.resetGuidedTask()

    def speak(self, text):
        """Speak text using TTS engine"""
        if self.tts_engine:
            try:
                # Run in separate thread to avoid blocking UI
                import threading
                def _speak():
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                threading.Thread(target=_speak, daemon=True).start()
            except Exception as e:
                print(f"TTS Error: {e}")
    
    def checkScreenChange(self, current_image):
        """Check if screen changed significantly"""
        if not self.active or not current_image:
            return False
            
        try:
            # Convert to grayscale and resize for fast comparison
            # Using hash or raw bytes
            from PIL import ImageOps
            
            # Simple hash check
            # Resize to small thumbnail to ignore minor noise
            thumb = current_image.resize((64, 64), Image.Resampling.LANCZOS)
            gray = ImageOps.grayscale(thumb)
            current_hash = hash(gray.tobytes())
            
            is_changed = False
            if self.last_screen_hash is not None:
                # If hash differs (basic check, can be improved with ImageChops)
                if current_hash != self.last_screen_hash:
                    is_changed = True
            
            self.last_screen_hash = current_hash
            return is_changed
        except Exception as e:
            print(f"Diff check failed: {e}")
            return False
    
    def checkStepCompletion(self, current_hash):
        """Check if user completed the current step (screen changed after action)"""
        if not self.waiting_for_completion:
            return False
        
        # If screen hash is different from when we showed the step, user likely took action
        if self.step_start_hash is not None and current_hash != self.step_start_hash:
            print(f"[GuidedNav] Screen changed after step {self.current_step}")
            return True
        return False


class ContextPanel(QWidget):
    """Panel to display real-time AI context analysis"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(140)
        self.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.3);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(6)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.header_label = QLabel("✨ AI Context Logic")
        self.header_label.setStyleSheet("color: rgba(80, 200, 255, 0.8); font-size: 11px; font-weight: bold; border: none; background: transparent;")
        header_layout.addWidget(self.header_label)
        
        
        # Action Buttons
        ctx_actions = QHBoxLayout()
        ctx_actions.setSpacing(8)
        
        # Calibrate Button
        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setFixedSize(70, 20)
        self.calibrate_btn.setCursor(Qt.PointingHandCursor)
        self.calibrate_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.7);
                border-radius: 4px;
                font-size: 10px;
                border: none;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                color: white;
            }
        """)
        ctx_actions.addWidget(self.calibrate_btn)
        
        
        # Follow Along Toggle
        self.follow_btn = QPushButton("Follow Mode: OFF")
        self.follow_btn.setFixedSize(90, 20)
        self.follow_btn.setCursor(Qt.PointingHandCursor)
        self.follow_btn.setCheckable(True)
        self.follow_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.7);
                border-radius: 4px;
                font-size: 10px;
                border: none;
            }
            QPushButton:checked {
                background: rgba(80, 200, 255, 0.3);
                color: white;
                border: 1px solid rgba(80, 200, 255, 0.5);
            }
        """)
        ctx_actions.addWidget(self.follow_btn)
        
        layout.addLayout(header_layout)
        layout.addLayout(ctx_actions)
        
        # App Name
        self.app_label = QLabel("Waiting for analysis...")
        self.app_label.setStyleSheet("color: white; font-weight: 600; font-size: 13px; border: none; background: transparent;")
        layout.addWidget(self.app_label)
        
        # Details (scrollable info)
        self.details_label = QLabel("Screen monitoring active. Analyzing content...")
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 11px; border: none; background: transparent;")
        self.details_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        # Use a scroll area for details
        scroll = QScrollArea()
        scroll.setWidget(self.details_label)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 4px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,0.2); border-radius: 2px; }
        """)
        layout.addWidget(scroll)
    
    def setStatus(self, status):
        """Update status label"""
        if status == "ANALYZING":
            self.app_label.setText("Analyzing...")
            self.app_label.setStyleSheet("color: #80c0ff; font-weight: 600; font-size: 13px; border: none; background: transparent;")
        elif status == "IDLE":
            self.app_label.setStyleSheet("color: white; font-weight: 600; font-size: 13px; border: none; background: transparent;")
    
    def updateContext(self, analysis_text):
        """Update the panel with new analysis data"""
        lines = analysis_text.strip().split('\n')
        summary = lines[0] if lines else "Unknown App"
        if len(summary) > 40: 
            summary = summary[:40] + "..."
        self.app_label.setText(summary)
        clean_text = analysis_text.replace('**', '').replace('##', '')
        self.details_label.setText(clean_text)
            
    def showActionsMenu(self):
        """Show Quick Actions Menu"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgb(40, 45, 60);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(80, 200, 255, 0.2);
            }
        """)
        
        act_guide = menu.addAction("🧭 Guide me through this app")
        act_what = menu.addAction("💡 What can I do here?")
        act_find = menu.addAction("🔍 Find a feature...")
        
        action = menu.exec_(QCursor.pos())
        
        # Determine parent to call
        # Since this is a widget inside layout, traverse up or pass parent reference
        # We know parent is CircularWindow or layout container
        # Best to emit signal or use parent() if reliable
        window = self.window() # Get top level window
        if hasattr(window, 'triggerQuickAction'):
            if action == act_guide:
                window.triggerQuickAction("Guide me through the main workflow of this application.")
            elif action == act_what:
                window.triggerQuickAction("What are the main actionable elements on this screen and what do they do?")
            elif action == act_find:
                # Prompt user for feature name
                from PyQt5.QtWidgets import QInputDialog
                text, ok = QInputDialog.getText(self, "Find Feature", "What are you looking for?")
                if ok and text:
                    window.triggerQuickAction(f"Where is the '{text}' feature located? Provide steps.")

class GlobalHotkeyManager(QObject):
    """Manages system-wide keyboard shortcuts"""
    # Signals for main thread actions
    sig_toggle_overlay = pyqtSignal()
    sig_toggle_overlay_edit = pyqtSignal()
    sig_ask_ai = pyqtSignal()
    sig_next_step = pyqtSignal()
    sig_clear_overlay = pyqtSignal()
    sig_toggle_monitoring = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.listening = False
        
    def start(self):
        try:
            import keyboard
            
            # Remove all previous hotkeys to be safe
            keyboard.unhook_all()
            
            # Register Hotkeys
            # Ctrl+Shift+G: Toggle Overlay
            keyboard.add_hotkey('ctrl+shift+g', self.sig_toggle_overlay.emit)
            # Ctrl+Shift+E: Toggle Overlay Edit Mode
            keyboard.add_hotkey('ctrl+shift+e', self.sig_toggle_overlay_edit.emit)
            # Ctrl+Shift+A: Ask AI about screen
            keyboard.add_hotkey('ctrl+shift+a', self.sig_ask_ai.emit)
            # Ctrl+Shift+N: Next Step
            keyboard.add_hotkey('ctrl+shift+n', self.sig_next_step.emit)
            # Ctrl+Shift+C: Clear Overlays
            keyboard.add_hotkey('ctrl+shift+c', self.sig_clear_overlay.emit)
            # Ctrl+Shift+M: Toggle Monitoring
            keyboard.add_hotkey('ctrl+shift+m', self.sig_toggle_monitoring.emit)
            
            self.listening = True
            print("Global hotkeys registered.")
        except ImportError:
            print("Error: 'keyboard' library not found. Hotkeys disabled. Run 'pip install keyboard'")
        except Exception as e:
            print(f"Hotkey Error: {e}")
            
    def stop(self):
        if self.listening:
            try:
                import keyboard
                keyboard.unhook_all()
            except: pass


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
        
        # Screen monitoring state
        self.screen_monitoring_enabled = False
        self.latest_screenshot = None
        self.last_capture_time = None
        self.is_analyzing = False  # Flag to prevent overlapping analysis calls
        self.last_overlay_query = None
        self.last_overlay_retry = 0
        self.last_overlay_image = None
        self.last_ocr_candidates = None
        self.pending_candidate_selection = None
        self.debug_overlay_candidates = False  # Set True to see all matching OCR boxes
        
        
        # Follow-Along Manager
        self.follow_manager = FollowAlongManager(self)
        
        # Hotkey Manager
        self.hotkey_manager = GlobalHotkeyManager(self)
        self.hotkey_manager.sig_toggle_overlay.connect(self.toggleOverlayVisibility)
        self.hotkey_manager.sig_toggle_overlay_edit.connect(self.toggleOverlayEditMode)
        self.hotkey_manager.sig_ask_ai.connect(self.triggerAskAI)
        self.hotkey_manager.sig_next_step.connect(self.triggerNextStep)
        self.hotkey_manager.sig_clear_overlay.connect(self.triggerClearOverlay)
        self.hotkey_manager.sig_toggle_monitoring.connect(self.toggleScreenMonitoring)
        # Delay start to avoid constructor issues
        QTimer.singleShot(1000, self.hotkey_manager.start)
        
        # Screen monitor timer (3 second interval)
        self.screen_monitor_timer = QTimer(self)
        self.screen_monitor_timer.timeout.connect(self._autoCapture)
        
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
        
        # Calibration mode state
        self.calibration_mode = False
        
        self.initUI()
        
        # Show API key dialog on startup if no key is set
        if not self.api_key:
            self.showAPIKeyDialog()
            
    def initUI(self):
        # Initialize Overlay Window
        self.overlay = OverlayWindow()
        self.overlay.show()
        
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
        screen = QGuiApplication.primaryScreen().geometry()
        # Calculate center position
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def startCalibration(self):
        """Start the interactive calibration process"""
        self.setCalibrationMode(True)

    def addShape(self, *args, **kwargs):
        """Forward shape drawing to overlay"""
        if hasattr(self, 'overlay'):
            self.overlay.addShape(*args, **kwargs)

    def clearLayout(self):
        """Forward clear command to overlay"""
        if hasattr(self, 'overlay'):
            self.overlay.clearLayout()

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
        
        # Screen monitoring toggle button
        self.monitor_toggle = IconButton("eye", self.capsule)
        self.monitor_toggle.setFixedSize(36, 36)
        self.monitor_toggle.setStyleSheet("background: transparent; border-radius: 18px;")
        self.monitor_toggle.clicked.connect(self.toggleScreenMonitoring)
        capsule_layout.addWidget(self.monitor_toggle)
        
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
        capsule_layout.addWidget(self.send_button)
        
        container_layout.addWidget(self.capsule)
        self.main_layout.addWidget(self.input_container)
        
        # Add Context Panel (Hidden by default, shown when monitoring is active)
        self.context_panel = ContextPanel()
        self.context_panel.hide()
        # Connect calibration button
        self.context_panel.calibrate_btn.clicked.connect(self.startCalibration)
        # Connect follow button
        self.context_panel.follow_btn.toggled.connect(self.toggleFollowMode)
        self.main_layout.addWidget(self.context_panel)
        # Add some margin at bottom
        self.main_layout.addSpacing(10)
        
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

        # Handle pending candidate selection by OCR id
        if self.pending_candidate_selection:
            if message.lower() in ("cancel", "clear", "stop"):
                self.pending_candidate_selection = None
                self.message_area.append("""
                <div style="background: rgba(255, 255, 255, 0.1); 
                            border-radius: 12px; 
                            padding: 8px 12px; 
                            margin: 5px 0;
                            color: rgba(255, 255, 255, 0.8);">
                    ✅ Selection cancelled.
                </div>
                """)
                self.scrollToBottom()
                self.input_field.clear()
                return
            if message.isdigit():
                ocr_id = int(message)
                candidates = self.pending_candidate_selection.get("candidates", [])
                padding = self.pending_candidate_selection.get("padding", 5)
                source_image = self.pending_candidate_selection.get("image")
                match = next((c for c in candidates if c.get("ocr_id") == ocr_id), None)
                if match:
                    self.pending_candidate_selection = None
                    self._drawOverlayFromCandidate(match, padding, source_image)
                    self.input_field.clear()
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
        
        # Determine context and prompts
        current_image = None
        system_prompt = None
        is_overlay_command = False
        
        # Get screen resolution
        screen_geom = QGuiApplication.primaryScreen().virtualGeometry()
        res_info = f"Screen Resolution: {screen_geom.width()}x{screen_geom.height()}"
        
        # Check if this is an overlay/highlight command
        overlay_keywords = ['rectangle', 'highlight', 'circle', 'box', 'mark', 'outline', 'draw', 'show me', 'point to', 'where is']
        message_lower = message.lower()
        is_overlay_command = any(keyword in message_lower for keyword in overlay_keywords)
        
        # Use monitored screenshot if available
        if self.latest_screenshot and self.screen_monitoring_enabled:
            current_image = self.latest_screenshot
            
            if is_overlay_command:
                self.last_overlay_query = message
                self.last_overlay_retry = 0
                # Capture a fresh screenshot for accurate placement
                self.last_overlay_image = self._captureOverlayScreenshot()
                self._handleOcrOverlayRequest(message, self.last_overlay_image)
                return
            else:
                # Regular conversational response with screenshot context
                system_prompt = f"""You are a helpful AI assistant. The user has screen monitoring enabled.
{res_info}

Analyze the screenshot if relevant to the user's question and provide a helpful response.

User message: {{user_message}}"""
        
        self.gemini_worker = GeminiWorker(message, self.api_key, image_data=current_image, system_prompt=system_prompt)
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
        
        # Check for task completion in guided mode
        if self.follow_manager.guided_mode and "TASK_COMPLETE" in response_text.upper():
            self.follow_manager.completeTask()
            complete_msg = """
            <div style="background: rgba(80, 200, 100, 0.2); 
                        border: 1px solid rgba(80, 200, 100, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(200, 255, 200, 0.95);">
                ✅ <b>Task Complete!</b>
            </div>
            """
            self.message_area.append(complete_msg)
            self.scrollToBottom()
            return
        
        # Parse SHAPE commands (regex extraction)
        import re
        parsed_shapes = []
        clean_text_lines = []
        action_description = None
        
        # Regex to match SHAPE[...] block
        shape_pattern = re.compile(r'SHAPE\[(.*?)\]')
        # Regex to match ACTION: line
        action_pattern = re.compile(r'^ACTION:\s*(.+)$', re.IGNORECASE | re.MULTILINE)
        
        # Extract action description
        action_match = action_pattern.search(response_text)
        if action_match:
            action_description = action_match.group(1).strip()
        
        lines = response_text.split('\n')
        for line in lines:
            matches = shape_pattern.findall(line)
            if matches:
                 # Line contains shapes
                 clean_line = shape_pattern.sub('', line).strip()
                 if clean_line:
                     clean_text_lines.append(clean_line)
                 
                 for match_str in matches:
                     try:
                         # Parse key:value pairs
                         params = {}
                         parts = match_str.split(',')
                         for part in parts:
                             if ':' in part:
                                 k, v = part.split(':', 1)
                                 k = k.strip()
                                 v = v.strip().strip('"\'')
                                 params[k] = v
                        
                         shape = OverlayShape(
                             shape_type=params.get('type', 'RECT').upper(),
                             x=int(params.get('x', 0)),
                             y=int(params.get('y', 0)),
                             width=int(params.get('w', 100)),
                             height=int(params.get('h', 100)),
                             color=params.get('color', 'green'),
                             label=params.get('label', ''),
                             step=int(params.get('step', 1))
                         )
                         parsed_shapes.append(shape)
                     except Exception as e:
                         print(f"Error parsing shape: {e}")
            else:
                clean_text_lines.append(line)
        
        # Load parsing results into overlay
        if parsed_shapes:
            # COORDINATE VALIDATION
            screen_geom = QGuiApplication.primaryScreen().virtualGeometry()
            sw, sh = screen_geom.width(), screen_geom.height()
            
            valid_shapes = []
            for s in parsed_shapes:
                # Clamp coordinates to screen bounds to prevent off-screen drawing
                rect = s.rect
                nx = max(0, min(rect.x(), sw - 10))
                ny = max(0, min(rect.y(), sh - 10))
                nw = min(rect.width(), sw - nx)
                nh = min(rect.height(), sh - ny)
                
                s.rect = QRect(nx, ny, nw, nh)
                valid_shapes.append(s)
                
            self.overlay.loadShapes(valid_shapes)
            
            # If in guided mode, set step as shown and wait for completion
            if self.follow_manager.guided_mode:
                current_hash = getattr(self, 'last_screen_hash_val', None)
                self.follow_manager.setStepShown(action_description, current_hash)
        
        clean_text = '\n'.join(clean_text_lines)
        
        # Add AI response with minimalist styling
        ai_message = f"""
        <div style="margin: 12px 0; margin-right: 40px;">
            <div style="color: rgba(255, 255, 255, 0.95); line-height: 1.4;">
                {clean_text}
            </div>
        </div>
        """
        self.message_area.append(ai_message)
        self.scrollToBottom()
    
    def onOverlayJSONResponse(self, response_text):
        """Handle JSON overlay response from Gemini"""
        import json
        import re
        
        # DEBUG: Print raw response
        print(f"[DEBUG] Raw AI response: {response_text[:500]}")
        
        # Remove loading indicator
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()
        
        try:
            # Try multiple methods to extract JSON
            clean_response = response_text.strip()
            
            # Method 1: Remove markdown code fences
            if "```" in clean_response:
                # Find content between code fences
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_response)
                if match:
                    clean_response = match.group(1).strip()
            
            # Method 2: Find JSON object with regex
            if not clean_response.startswith('{'):
                # Try to find a JSON object anywhere in the response
                match = re.search(r'\{[\s\S]*"overlays"[\s\S]*\}', clean_response)
                if match:
                    clean_response = match.group(0)
            
            # Parse JSON
            data = json.loads(clean_response)
            
            # Handle list vs dict
            overlays = []
            if isinstance(data, dict):
                overlays = data.get("overlays", [])
            elif isinstance(data, list):
                # Maybe AI returned raw list of overlays?
                overlays = data
            
            if not overlays or not isinstance(overlays, list):
                # No overlays found
                msg = """
                <div style="background: rgba(255, 200, 100, 0.2); 
                            border: 1px solid rgba(255, 200, 100, 0.4); 
                            border-radius: 16px; 
                            padding: 12px 16px; 
                            margin: 8px 0; 
                            color: rgba(255, 255, 200, 0.95);">
                    ⚠️ Could not locate the element on screen.
                </div>
                """
                self.message_area.append(msg)
                self.scrollToBottom()
                return
            
            # Validate and create shapes
            screen_geom = QGuiApplication.primaryScreen().virtualGeometry()
            sw, sh = screen_geom.width(), screen_geom.height()
            # Scale coordinates from screenshot space to screen space (handles DPI scaling)
            sx = 1.0
            sy = 1.0
            source_image = self.last_overlay_image or self.latest_screenshot
            if source_image:
                try:
                    img_w, img_h = source_image.size
                    if img_w > 0 and img_h > 0:
                        sx = sw / float(img_w)
                        sy = sh / float(img_h)
                except Exception:
                    sx = 1.0
                    sy = 1.0
            
            shapes = []
            for overlay in overlays:
                try:
                    x = int(overlay.get("x", 0))
                    y = int(overlay.get("y", 0))
                    w = int(overlay.get("width", 100))
                    h = int(overlay.get("height", 50))
                    color = overlay.get("color", "red")
                    label = overlay.get("label", "")
                    shape_type = overlay.get("type", "rectangle").upper()
                    
                    # Map type names
                    if shape_type in ["RECTANGLE", "BOX", "RECT"]:
                        shape_type = "RECT"
                    elif shape_type in ["CIRCLE", "ELLIPSE"]:
                        shape_type = "CIRCLE"
                    
                    # Scale to screen coordinates (DPI-aware)
                    x = int(x * sx)
                    y = int(y * sy)
                    w = int(w * sx)
                    h = int(h * sy)

                    # Normalize tiny boxes (ensure visible size)
                    min_w = 12
                    min_h = 12
                    if w < min_w:
                        w = min_w
                    if h < min_h:
                        h = min_h

                    # Clamp to screen bounds
                    x = max(0, min(x, sw - 10))
                    y = max(0, min(y, sh - 10))
                    w = min(w, sw - x)
                    h = min(h, sh - y)
                    
                    shape = OverlayShape(shape_type, x, y, w, h, color, label, step=1)
                    shapes.append(shape)
                    
                except (ValueError, TypeError) as e:
                    print(f"Error parsing overlay: {e}")
                    continue
            
            if shapes:
                self.overlay.loadShapes(shapes)
                # Leave edit mode off after new overlays
                self.overlay.setEditMode(False)
                
                # Success message
                msg = f"""
                <div style="background: rgba(80, 200, 100, 0.2); 
                            border: 1px solid rgba(80, 200, 100, 0.4); 
                            border-radius: 16px; 
                            padding: 12px 16px; 
                            margin: 8px 0; 
                            color: rgba(200, 255, 200, 0.95);">
                    ✅ Drew {len(shapes)} overlay(s) on screen
                </div>
                """
                self.message_area.append(msg)
            else:
                msg = """
                <div style="background: rgba(255, 200, 100, 0.2); 
                            border: 1px solid rgba(255, 200, 100, 0.4); 
                            border-radius: 16px; 
                            padding: 12px 16px; 
                            margin: 8px 0; 
                            color: rgba(255, 255, 200, 0.95);">
                    ⚠️ No valid overlays could be created.
                </div>
                """
                self.message_area.append(msg)
            # Warn if overlays are suspiciously small after scaling
            tiny_shapes = [s for s in shapes if s.rect.width() <= 12 or s.rect.height() <= 12]
            if tiny_shapes:
                if self.last_overlay_query and self.last_overlay_retry < 1:
                    self.last_overlay_retry += 1
                    retry_msg = """
                    <div style="background: rgba(80, 200, 255, 0.15); 
                                border: 1px solid rgba(80, 200, 255, 0.3); 
                                border-radius: 12px; 
                                padding: 8px 12px; 
                                margin: 6px 0; 
                                color: rgba(255, 255, 255, 0.9);">
                        🔁 Retrying with a larger bounding box...
                    </div>
                    """
                    self.message_area.append(retry_msg)
                    self.scrollToBottom()
                    self._requestOverlayForMessage(self.last_overlay_query, padding_note="Increase the box by 15% in width and height to fully cover the element.")
                    return
                warn_msg = """
                <div style="background: rgba(255, 180, 80, 0.2); 
                            border: 1px solid rgba(255, 180, 80, 0.4); 
                            border-radius: 12px; 
                            padding: 8px 12px; 
                            margin: 6px 0; 
                            color: rgba(255, 230, 200, 0.95);">
                    ⚠️ The highlight is very small. Try asking for a more specific target.
                </div>
                """
                self.message_area.append(warn_msg)
                
        except json.JSONDecodeError as e:
            # JSON parsing failed
            error_msg = f"""
            <div style="background: rgba(255, 100, 100, 0.2); 
                        border: 1px solid rgba(255, 150, 150, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(255, 200, 200, 0.95);">
                <b>Error:</b> Could not parse response as JSON.<br>
                <small>{str(e)}</small>
            </div>
            """
            self.message_area.append(error_msg)
            print(f"JSON parse error: {e}")
            print(f"Raw response: {response_text[:500]}")
            
        except Exception as e:
            error_msg = f"""
            <div style="background: rgba(255, 100, 100, 0.2); 
                        border: 1px solid rgba(255, 150, 150, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(255, 200, 200, 0.95);">
                <b>Error:</b> {str(e)}
            </div>
            """
            self.message_area.append(error_msg)
            
        self.scrollToBottom()

    def onOcrSelectionResponse(self, response_text):
        """Handle OCR candidate selection response"""
        import json
        import re

        # Remove loading indicator
        cursor = self.message_area.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.BlockUnderCursor)
        cursor.removeSelectedText()

        # Extract JSON
        clean_response = response_text.strip()
        if "```" in clean_response:
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_response)
            if match:
                clean_response = match.group(1).strip()

        try:
            data = json.loads(clean_response)
        except Exception as e:
            self.message_area.append(f"""
            <div style="background: rgba(255, 100, 100, 0.2); 
                        border: 1px solid rgba(255, 150, 150, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(255, 200, 200, 0.95);">
                <b>Error:</b> Could not parse selection JSON.<br>
                <small>{str(e)}</small>
            </div>
            """)
            self.scrollToBottom()
            return

        selection = data.get("selection")
        candidates = self.last_ocr_candidates or []
        source_image = self.last_overlay_image

        # Enforce confidence rule
        if selection and float(selection.get("confidence", 0)) < 0.6:
            selection = None

        # Validate selection against matching rules
        if selection:
            selected_id = selection.get("ocr_id")
            padding = selection.get("padding", 5)
            valid_id = self._validateOcrSelection(selected_id, candidates, self.last_overlay_query)
            if valid_id is None:
                selection = None
            else:
                selected_candidate = next((c for c in candidates if c.get("ocr_id") == valid_id), None)
                if selected_candidate:
                    self._drawOverlayFromCandidate(selected_candidate, padding, source_image)
                    return
                selection = None

        # If selection is null, show top 5 candidates and wait for user
        top_candidates = self._topCandidateList(candidates, self.last_overlay_query, limit=5)
        if not top_candidates:
            self.message_area.append("""
            <div style="background: rgba(255, 200, 100, 0.2); 
                        border: 1px solid rgba(255, 200, 100, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(255, 255, 200, 0.95);">
                ⚠️ No OCR candidates matched. Try a clearer target.
            </div>
            """)
            self.scrollToBottom()
            return

        choices = "".join(
            f"<div>• <b>{c['ocr_id']}</b>: {c['text']}</div>"
            for c in top_candidates
        )
        self.message_area.append(f"""
        <div style="background: rgba(255, 255, 255, 0.08); 
                    border: 1px solid rgba(255, 255, 255, 0.15); 
                    border-radius: 12px; 
                    padding: 10px 12px; 
                    margin: 8px 0; 
                    color: rgba(255, 255, 255, 0.85);">
            I found multiple candidates. Reply with the OCR id to highlight (or type 'cancel'):<br>
            {choices}
        </div>
        """)
        self.scrollToBottom()
        self.pending_candidate_selection = {
            "candidates": top_candidates,
            "padding": 5,
            "image": source_image
        }

    def _tokenize(self, text):
        import re
        return [t for t in re.split(r"[\W_]+", text.lower()) if t]

    def _levenshtein(self, a, b):
        if a == b:
            return 0
        if len(a) == 0:
            return len(b)
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cost = 0 if ca == cb else 1
                cur.append(min(
                    prev[j] + 1,
                    cur[j - 1] + 1,
                    prev[j - 1] + cost
                ))
            prev = cur
        return prev[-1]

    def _validateOcrSelection(self, selected_id, candidates, query):
        if not selected_id or not candidates:
            return None
        query_tokens = self._tokenize(query or "")
        if not query_tokens:
            return None

        exact = []
        fuzzy = []
        for c in candidates:
            text_tokens = self._tokenize(c.get("text", ""))
            if any(qt in text_tokens for qt in query_tokens):
                exact.append(c)
                continue
            if c.get("confidence", 0) >= 0.6:
                for qt in query_tokens:
                    if any(self._levenshtein(qt, tt) <= 2 for tt in text_tokens):
                        fuzzy.append(c)
                        break

        def smallest_area(items):
            return min(items, key=lambda x: x.get("width", 0) * x.get("height", 0), default=None)

        if exact:
            best = smallest_area(exact)
        elif fuzzy:
            best = smallest_area(fuzzy)
        else:
            return None

        if best and best.get("ocr_id") == selected_id:
            return selected_id
        return None

    def _topCandidateList(self, candidates, query, limit=5):
        # Prefer exact matches, then fuzzy, else highest confidence
        query_tokens = self._tokenize(query or "")
        exact = []
        fuzzy = []
        for c in candidates:
            text_tokens = self._tokenize(c.get("text", ""))
            if any(qt in text_tokens for qt in query_tokens):
                exact.append(c)
                continue
            if c.get("confidence", 0) >= 0.6:
                for qt in query_tokens:
                    if any(self._levenshtein(qt, tt) <= 2 for tt in text_tokens):
                        fuzzy.append(c)
                        break
        if exact:
            return sorted(exact, key=lambda x: x.get("width", 0) * x.get("height", 0))[:limit]
        if fuzzy:
            return sorted(fuzzy, key=lambda x: x.get("width", 0) * x.get("height", 0))[:limit]
        return sorted(candidates, key=lambda x: x.get("confidence", 0), reverse=True)[:limit]
    
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

    def _requestOverlayForMessage(self, message, padding_note=None, image_override=None):
        """Send overlay-only request with strict JSON output"""
        screen_geom = QGuiApplication.primaryScreen().virtualGeometry()
        pad_rule = ""
        if padding_note:
            pad_rule = f"\n- {padding_note}"

        image = image_override or self.latest_screenshot
        img_w, img_h = (0, 0)
        if image:
            try:
                img_w, img_h = image.size
            except Exception:
                img_w, img_h = (0, 0)

        system_prompt = f"""Find the exact UI element in this screenshot: "{message}"

Return ONLY this JSON (replace numbers with actual pixel coordinates):
{{"overlays":[{{"type":"rectangle","x":100,"y":200,"width":120,"height":40,"color":"red","label":"target"}}]}}

Rules:
- The rectangle MUST fully cover the element's visible bounds (left/right/top/bottom).
- If the target is a labeled UI item (menu/tab/button), make the box tight around the visible text.
- If unsure, make the box slightly larger to fully cover the element.{pad_rule}
- Use absolute pixel coordinates from the top-left of the screenshot.
- Output ONLY raw JSON, no markdown, no extra text.

Screenshot size is {img_w}x{img_h} pixels.
Screen is {screen_geom.width()}x{screen_geom.height()} pixels.
x=pixels from left, y=pixels from top (use screenshot size for coordinates)."""

        print(f"[DEBUG] Overlay command: {message}")

        self.gemini_worker = GeminiWorker(message, self.api_key, image_data=image, system_prompt=system_prompt)
        self.gemini_worker.response_received.connect(self.onOverlayJSONResponse)
        self.gemini_worker.error_occurred.connect(self.onAIError)
        self.gemini_worker.retry_attempt.connect(self.onRetryAttempt)
        self.gemini_worker.finished.connect(self.onWorkerFinished)
        self.gemini_worker.start()

    def _handleOcrOverlayRequest(self, message, image):
        """Hybrid overlay: try OCR-first, fall back to LLM coordinates if no match"""
        print(f"[DEBUG] _handleOcrOverlayRequest: message='{message}'")
        candidates = self._extractOcrCandidates(image)
        self.last_ocr_candidates = candidates
        print(f"[DEBUG] OCR found {len(candidates)} total candidates")

        # Step 1: Try local OCR matching (no LLM needed)
        matched = self._localOcrMatch(message, candidates)
        print(f"[DEBUG] Local match found {len(matched) if matched else 0} matching candidates")
        
        if matched:
            # Found exact/fuzzy match - use smallest bounding box
            if self.debug_overlay_candidates:
                # Debug: show only matched candidates, not all
                self._renderFilteredCandidates(matched, image)
            
            # Auto-select the smallest box (tightest match)
            best = min(matched, key=lambda c: c["width"] * c["height"])
            self._drawOverlayFromCandidate(best, padding=5, source_image=image)
            
            msg = f"""
            <div style="background: rgba(80, 200, 100, 0.2); 
                        border: 1px solid rgba(80, 200, 100, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(200, 255, 200, 0.95);">
                ✅ Found via OCR: "{best['text']}" (id: {best['ocr_id']})
            </div>
            """
            self.message_area.append(msg)
            self.scrollToBottom()
            # Re-enable input (no worker was used)
            self.input_field.setEnabled(True)
            self.send_button.setEnabled(True)
            self.input_field.setFocus()
            return
        
        # Step 2: OCR didn't find it - fall back to LLM coordinate method
        print(f"[DEBUG] No OCR match, falling back to LLM coordinates")
        fallback_msg = """
        <div style="background: rgba(255, 200, 100, 0.15); 
                    border: 1px solid rgba(255, 200, 100, 0.3); 
                    border-radius: 12px; 
                    padding: 8px 12px; 
                    margin: 6px 0; 
                    color: rgba(255, 255, 200, 0.9);">
            🔄 OCR didn't find a match. Falling back to AI vision...
        </div>
        """
        self.message_area.append(fallback_msg)
        self.scrollToBottom()
        
        # Use the existing LLM coordinate method
        print(f"[DEBUG] Calling _requestOverlayForMessage")
        self._requestOverlayForMessage(message, image_override=image)
    
    def _localOcrMatch(self, query, candidates):
        """Find OCR candidates matching the query locally (no LLM)"""
        import re
        
        if not candidates:
            return []
        
        # Tokenize query: split on whitespace and punctuation
        query_tokens = set(re.split(r'[\s\W]+', query.lower()))
        # Remove common/filler words - be aggressive to focus on actual target
        stop_words = {
            'make', 'rectangle', 'on', 'the', 'a', 'an', 'highlight', 'box', 'draw', 
            'show', 'me', 'over', 'around', 'it', 'this', 'that', 'there', 'is', 'in',
            'vs', 'code', 'option', 'button', 'menu', 'tab', 'click', 'select', 'find',
            'where', 'put', 'place', 'create', 'add', 'to', 'of', 'for', 'with', 'at',
            'and', 'or', 'be', 'can', 'please', 'just', 'only', 'also', 'here', 'top',
            'bottom', 'left', 'right', 'side', 'corner', 'area', 'section', 'part'
        }
        query_tokens = query_tokens - stop_words
        # Also filter out very short tokens (likely noise)
        query_tokens = {t for t in query_tokens if len(t) >= 3}
        
        print(f"[DEBUG] Target tokens after filtering: {query_tokens}")
        
        if not query_tokens:
            print("[DEBUG] No target tokens found after filtering")
            return []
        
        exact_matches = []
        fuzzy_matches = []
        
        for c in candidates:
            text_lower = c["text"].lower().strip()
            
            # Exact full-text match (strongest)
            if text_lower in query_tokens:
                exact_matches.append(c)
                continue
            
            # Token-in-text match
            text_tokens = set(re.split(r'[\s\W]+', text_lower))
            matching_tokens = query_tokens & text_tokens
            if matching_tokens:
                exact_matches.append(c)
                continue
            
            # Fuzzy match (Levenshtein distance <= 2) only for longer tokens
            if c["confidence"] >= 0.6:
                for qt in query_tokens:
                    if len(qt) >= 4:  # Only fuzzy match longer tokens
                        for tt in text_tokens:
                            if len(tt) >= 4 and self._levenshtein(qt, tt) <= 2:
                                fuzzy_matches.append(c)
                                break
                        else:
                            continue
                        break
        
        print(f"[DEBUG] Exact matches: {len(exact_matches)}, Fuzzy matches: {len(fuzzy_matches)}")
        
        # Prefer exact matches
        if exact_matches:
            return exact_matches
        return fuzzy_matches
    
    def _levenshtein(self, s1, s2):
        """Simple Levenshtein distance"""
        if len(s1) < len(s2):
            return self._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]
    
    def _renderFilteredCandidates(self, candidates, source_image):
        """Render only filtered/matching OCR candidates for debug"""
        shapes = []
        for c in candidates:
            label = f"{c['ocr_id']}:{c['text'][:12]}"
            shapes.append(OverlayShape("RECT", c["left"], c["top"], c["width"], c["height"], "lime", label, step=1))
        self._renderOverlayShapes(shapes, source_image)

    def _extractOcrCandidates(self, image):
        """Run OCR and build candidate list"""
        try:
            import pytesseract
        except Exception:
            self.message_area.append("""
            <div style="background: rgba(255, 100, 100, 0.2); 
                        border: 1px solid rgba(255, 150, 150, 0.4); 
                        border-radius: 16px; 
                        padding: 12px 16px; 
                        margin: 8px 0; 
                        color: rgba(255, 200, 200, 0.95);">
                <b>OCR Error:</b> pytesseract not available.
            </div>
            """)
            self.scrollToBottom()
            return []

        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        candidates = []
        ocr_id = 1
        n = len(data.get("text", []))
        for i in range(n):
            text = data["text"][i].strip()
            if not text:
                continue
            conf_raw = data.get("conf", [0])[i]
            try:
                conf_val = float(conf_raw)
            except Exception:
                conf_val = -1.0
            conf = max(0.0, min(1.0, conf_val / 100.0)) if conf_val >= 0 else 0.0
            left = int(data["left"][i])
            top = int(data["top"][i])
            width = int(data["width"][i])
            height = int(data["height"][i])
            candidates.append({
                "ocr_id": ocr_id,
                "text": text,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "confidence": conf
            })
            ocr_id += 1
        return candidates

    def _requestOcrSelection(self, message, candidates, image):
        """Ask LLM to select an OCR candidate by id"""
        import json
        prompt = (
            "You must choose an OCR candidate only from the list below. "
            "Return JSON only and follow the schema exactly. "
            "Do NOT invent coordinates or extra fields.\n\n"
            f"User request: \"{message}\"\n\n"
            "Return JSON schema:\n"
            "{\n"
            "  \"selection\": {\"ocr_id\": 123, \"padding\": 5, \"confidence\": 0.93} | null,\n"
            "  \"candidates\": [ ... ]\n"
            "}\n\n"
            "Rules:\n"
            "- selection must be null if confidence < 0.6\n"
            "- If ambiguous, return selection null and include up to 5 candidates.\n"
            "- Only use ocr_id from candidates.\n\n"
            f"Candidates:\n{json.dumps(candidates)}"
        )

        self.gemini_worker = GeminiWorker(message, self.api_key, image_data=image, system_prompt=prompt)
        self.gemini_worker.response_received.connect(self.onOcrSelectionResponse)
        self.gemini_worker.error_occurred.connect(self.onAIError)
        self.gemini_worker.retry_attempt.connect(self.onRetryAttempt)
        self.gemini_worker.finished.connect(self.onWorkerFinished)
        self.gemini_worker.start()

    def _renderAllCandidates(self, candidates, source_image):
        """Render all OCR candidates for debug"""
        shapes = []
        for c in candidates:
            label = f"{c['ocr_id']}:{c['text'][:12]}"
            shapes.append(OverlayShape("RECT", c["left"], c["top"], c["width"], c["height"], "cyan", label, step=1))
        self._renderOverlayShapes(shapes, source_image)

    def _renderOverlayShapes(self, shapes, source_image):
        """Scale and draw shapes based on screenshot size"""
        print(f"[DEBUG] _renderOverlayShapes: {len(shapes)} shapes")
        screen_geom = QGuiApplication.primaryScreen().virtualGeometry()
        sw, sh = screen_geom.width(), screen_geom.height()
        sx = 1.0
        sy = 1.0
        if source_image:
            try:
                img_w, img_h = source_image.size
                print(f"[DEBUG] Source image: {img_w}x{img_h}, Screen: {sw}x{sh}")
                if img_w > 0 and img_h > 0:
                    sx = sw / float(img_w)
                    sy = sh / float(img_h)
                    print(f"[DEBUG] Scale factors: sx={sx:.3f}, sy={sy:.3f}")
            except Exception:
                sx = 1.0
                sy = 1.0
        scaled = []
        for shape in shapes:
            rect = shape.rect
            x = int(rect.x() * sx)
            y = int(rect.y() * sy)
            w = int(rect.width() * sx)
            h = int(rect.height() * sy)
            x = max(0, min(x, sw - 10))
            y = max(0, min(y, sh - 10))
            w = min(w, sw - x)
            h = min(h, sh - y)
            print(f"[DEBUG] Scaled shape: ({x}, {y}) {w}x{h}")
            scaled.append(OverlayShape(shape.type, x, y, w, h, shape.color_name, shape.label, shape.step))
        print(f"[DEBUG] Loading {len(scaled)} shapes into overlay")
        self.overlay.loadShapes(scaled)
        self.overlay.setEditMode(False)

    def _drawOverlayFromCandidate(self, candidate, padding, source_image):
        """Draw overlay from OCR candidate"""
        print(f"[DEBUG] _drawOverlayFromCandidate: {candidate}")
        pad = max(0, int(padding))
        left = candidate["left"] - pad
        top = candidate["top"] - pad
        width = candidate["width"] + (pad * 2)
        height = candidate["height"] + (pad * 2)
        print(f"[DEBUG] Drawing rect at ({left}, {top}) size ({width}x{height})")
        shape = OverlayShape("RECT", left, top, width, height, "red", "target", step=1)
        self._renderOverlayShapes([shape], source_image)

    def _captureOverlayScreenshot(self):
        """Capture a fresh screenshot for overlay accuracy"""
        try:
            was_expanded = self.is_expanded
            window_pos = self.pos()
            overlay_visible = self.overlay.isVisible()

            # Hide UI to avoid covering target
            self.hide()
            self.overlay.hide()
            QApplication.processEvents()

            screenshot = ImageGrab.grab()

            # Restore UI
            self.show()
            if overlay_visible:
                self.overlay.show()
            if was_expanded:
                self.expandToChat()
                self.move(window_pos)
            return screenshot
        except Exception:
            # Fall back to latest screenshot if capture fails
            return self.latest_screenshot
    
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
    
    def toggleScreenMonitoring(self):
        """Toggle continuous screen monitoring on/off"""
        # Check if API key is set before enabling monitoring
        if not self.screen_monitoring_enabled:
            if not self.api_key or not isinstance(self.api_key, str) or len(self.api_key.strip()) < 10:
                error_msg = """
                <div style="background: rgba(255, 100, 100, 0.15); 
                            border: 1px solid rgba(255, 100, 100, 0.3); 
                            border-radius: 12px; 
                            padding: 8px 12px; 
                            margin: 5px 0;
                            color: rgba(255, 200, 200, 0.9);">
                    ⚠️ Please set your API key first (via Settings)
                </div>
                """
                self.message_area.append(error_msg)
                self.scrollToBottom()
                return
        
        self.screen_monitoring_enabled = not self.screen_monitoring_enabled
        
        if self.screen_monitoring_enabled:
            self.screen_monitor_timer.start(3000)  # 3 seconds
            status_msg = """
            <div style="background: rgba(80, 200, 255, 0.15); 
                        border: 1px solid rgba(80, 200, 255, 0.3); 
                        border-radius: 12px; 
                        padding: 8px 12px; 
                        margin: 5px 0;
                        color: rgba(255, 255, 255, 0.9);">
                👁️ Screen monitoring: <b>ON</b>
            </div>
            """
            # Update button style to show active state
            self.monitor_toggle.setStyleSheet("""
                background: rgba(80, 200, 255, 0.2); 
                border-radius: 18px;
                border: 1px solid rgba(80, 200, 255, 0.4);
            """)
            self.context_panel.show() # Show context panel
        else:
            self.screen_monitor_timer.stop()
            status_msg = """
            <div style="background: rgba(255, 255, 255, 0.1); 
                        border-radius: 12px; 
                        padding: 8px 12px; 
                        margin: 5px 0;
                        color: rgba(255, 255, 255, 0.7);">
                👁️ Screen monitoring: <b>OFF</b>
            </div>
            """
            # Reset button style
            self.monitor_toggle.setStyleSheet("background: transparent; border-radius: 18px;")
            self.context_panel.hide() # Hide context panel
        
        self.message_area.append(status_msg)
        self.scrollToBottom()
    
    def onAnalysisFinished(self, result):
        """Handle completion of background analysis"""
        self.is_analyzing = False
        self.context_panel.setStatus("IDLE") # Reset status
        if self.screen_monitoring_enabled:
            self.context_panel.updateContext(result)
    
    
    def toggleFollowMode(self, checked):
        """Toggle follow-along guidance"""
        if checked:
            self.follow_manager.start()
            self.context_panel.follow_btn.setText("Follow Mode: ON")
            # Ensure monitoring is ON
            if not self.screen_monitoring_enabled:
                self.toggleScreenMonitoring()
        else:
            self.follow_manager.stop()
            self.context_panel.follow_btn.setText("Follow Mode: OFF")
            
    def toggleOverlayVisibility(self):
        """Slot for hotkey to toggle overlay"""
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()

    def triggerNextStep(self):
        """Slot for hotkey to advance step"""
        if self.overlay.isVisible():
            self.overlay.nextStep()

    def triggerClearOverlay(self):
        """Slot for hotkey to clear guidance"""
        self.overlay.closeOverlay()

    def triggerAskAI(self):
        """Slot for hotkey to analyze screen"""
        # Simulate asking "Analyze this screen"
        if not self.screen_monitoring_enabled:
            # Need to capture once if monitoring is off
            pass 
        
        self.input_field.setText("Analyze this screen.")
        self.sendMessage()

    def toggleOverlayEditMode(self):
        """Toggle manual edit mode for overlays"""
        if not hasattr(self, 'overlay'):
            return
        new_state = not self.overlay.edit_mode
        self.overlay.setEditMode(new_state)
        status_msg = """
        <div style="background: rgba(255, 255, 255, 0.1); 
                    border-radius: 12px; 
                    padding: 8px 12px; 
                    margin: 5px 0;
                    color: rgba(255, 255, 255, 0.8);">
            🛠️ Overlay edit mode: <b>{}</b> (drag to move, mouse wheel to resize)
        </div>
        """.format("ON" if new_state else "OFF")
        self.message_area.append(status_msg)
        self.scrollToBottom()

        
    def triggerQuickAction(self, prompt):
        """Execute a quick action via Gemini"""
        self.input_field.setText(prompt)
        self.sendMessage()
        
    def _calculateScreenHash(self, image):
        """Calculate simple hash for screen diffing"""
        try:
            from PIL import ImageOps
            # Resize for performance and noise tolerance
            thumb = image.resize((64, 64), Image.Resampling.LANCZOS)
            gray = ImageOps.grayscale(thumb)
            return hash(gray.tobytes())
        except:
            return 0

    def _autoCapture(self):
        """Auto-capture screenshot for monitoring (silent, no AI call)"""
        try:
            # Capture without hiding window (background capture)
            screenshot = ImageGrab.grab()
            
            # Optimization: Check hash to skip redundant analysis
            current_hash = self._calculateScreenHash(screenshot)
            is_screen_same = (current_hash == getattr(self, 'last_screen_hash_val', None))
            self.last_screen_hash_val = current_hash
            
            self.latest_screenshot = screenshot
            self.last_capture_time = datetime.now()
            
            # GUIDED MODE: Check if user completed the current step
            if self.follow_manager.guided_mode and self.follow_manager.waiting_for_completion:
                step_completed = self.follow_manager.checkStepCompletion(current_hash)
                if step_completed:
                    # User completed the step! Advance and request next step
                    self.follow_manager.advanceStep()
                    self.overlay.closeOverlay()  # Clear current overlay
                    
                    # Auto-request next step from AI
                    print(f"[GuidedNav] Auto-requesting step {self.follow_manager.current_step}")
                    self._requestNextGuidedStep()
                    return  # Skip regular analysis during guided mode
            
            # Follow-Along Logic: Check for screen changes
            if self.follow_manager.active:
                changed = self.follow_manager.checkScreenChange(screenshot)
                if changed and self.overlay.isVisible():
                     pass
            
            # Start analysis if not already running and key is set
            # Skip background analysis during active guided navigation
            if self.follow_manager.guided_mode and self.follow_manager.waiting_for_completion:
                return  # Don't do background analysis during guided steps
            
            # OPTIMIZATION: Only analyze if screen CHANGED
            if not self.is_analyzing and self.api_key:
                if not is_screen_same:
                    self.is_analyzing = True
                    self.context_panel.setStatus("ANALYZING")
                    self.analysis_worker = AnalysisWorker(screenshot, self.api_key)
                    self.analysis_worker.finished.connect(self.onAnalysisFinished)
                    self.analysis_worker.start()
            
        except Exception as e:
            self.is_analyzing = False
            self.context_panel.setStatus("IDLE")
    
    def _requestNextGuidedStep(self):
        """Request the next step in guided navigation from AI"""
        if not self.follow_manager.guided_mode:
            return
        
        task_goal = self.follow_manager.current_task
        step_num = self.follow_manager.current_step
        
        # Show loading indicator
        loading_msg = f"""
        <div style="margin: 8px 0; color: rgba(80, 200, 255, 0.8); font-style: italic;">
            📍 Step {step_num}: Analyzing screen...
        </div>
        """
        self.message_area.append(loading_msg)
        self.scrollToBottom()
        
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        
        # Get screen resolution
        screen_geom = QGuiApplication.primaryScreen().virtualGeometry()
        res_info = f"Screen Resolution: {screen_geom.width()}x{screen_geom.height()}"
        
        system_prompt = f"""You are a step-by-step screen guidance assistant.

USER GOAL: "{task_goal}"
CURRENT STEP NUMBER: {step_num}
{res_info}

Look at the screenshot and find the EXACT UI element the user needs to click.
Estimate the pixel coordinates of that element.

RESPONSE FORMAT (REQUIRED):
ACTION: [what to click]
SHAPE[type:box, x:950, y:330, w:50, h:24, color:green, label:"Click here", step:1]

THE SHAPE LINE ABOVE IS AN EXAMPLE. Replace the numbers with:
- x = pixels from LEFT edge (e.g., 950)
- y = pixels from TOP edge (e.g., 330)
- w = width in pixels (e.g., 50)
- h = height in pixels (e.g., 24)

RULES:
- Provide only ONE step at a time
- x, y, w, h must be NUMBERS, not words
- If task is DONE respond: TASK_COMPLETE

Continue from step {step_num}."""
        
        # Use latest screenshot
        current_image = self.latest_screenshot
        
        self.gemini_worker = GeminiWorker("Continue to next step", self.api_key, image_data=current_image, system_prompt=system_prompt)
        self.gemini_worker.response_received.connect(self.onAIResponse)
        self.gemini_worker.error_occurred.connect(self.onAIError)
        self.gemini_worker.retry_attempt.connect(self.onRetryAttempt)
        self.gemini_worker.finished.connect(self.onWorkerFinished)
        self.gemini_worker.start()
    
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
    
    def setCalibrationMode(self, enabled):
        """Toggle interactive calibration mode"""
        self.calibration_mode = enabled
        if enabled:
            self.setCursor(Qt.CrossCursor)
            # Show toast instruction on overlay
            self.addShape("RECT", 20, 20, 300, 40, "black", "Click anywhere to verify coordinates")
        else:
            self.setCursor(Qt.ArrowCursor)
            self.clearLayout()
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging and expanding"""
        # Calibration mode click (only when explicitly enabled)
        if self.calibration_mode:
            pos = event.pos()
            x, y = pos.x(), pos.y()
            self.clearLayout()
            self.addShape("RECT", x - 50, y, 100, 2, "cyan", f"Actual: {x}, {y}")
            self.addShape("RECT", x, y - 50, 2, 100, "cyan")
            self.addShape("CIRCLE", x - 10, y - 10, 20, 20, "red")
            print(f"Calibration Click: ({x}, {y})")
            QTimer.singleShot(2000, lambda: self.setCalibrationMode(False))
            event.accept()
            return

        # Standard window interaction
        if event.button() == Qt.LeftButton:
            self.mouse_press_pos = event.globalPos()
            self.dragPosition = event.globalPos() - self.frameGeometry().topLeft()
            self.is_dragging = False
            event.accept()
    
    def keyPressEvent(self, event):
        """Handle keyboard input for overlay control"""
        if event.key() in (Qt.Key_Space, Qt.Key_Right):
            if hasattr(self, 'overlay') and self.overlay.isVisible():
                self.overlay.nextStep()
                event.accept()
                return
        
        if event.key() == Qt.Key_Escape:
            if hasattr(self, 'overlay') and self.overlay.isVisible():
                self.overlay.closeOverlay()
                event.accept()
                return
                
        super().keyPressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move - detect drag vs click"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'dragPosition'):
            # Calculate movement distance
            if self.mouse_press_pos:
                delta = (event.globalPos() - self.mouse_press_pos).manhattanLength()
                
                # If moved more than 5 pixels, it's a drag
                if delta > 5:
                    self.is_dragging = True
                    # Allow dragging in both bubble and expanded states
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

    # Manual test note (OCR overlay):
    # 1) Open an app with multiple instances of the word "Terminal".
    # 2) Run: "make rectangle on Terminal"
    # 3) Verify the smallest OCR box containing "Terminal" is selected.
    
    app = QApplication(sys.argv)
    
    # Set modern sans-serif font as default
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    
    window = CircularWindow()
    window.show()
    sys.exit(app.exec_())
