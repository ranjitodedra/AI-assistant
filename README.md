# AI Assistant - Your Smart Screen Guide

A modern desktop assistant that watches your screen and guides you step-by-step to accomplish tasks. Think of it as having a helpful friend looking over your shoulder, pointing exactly where to click.

![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![AI](https://img.shields.io/badge/AI-Google%20Gemini-orange)

---

## What Does It Do?

Ever struggled to find a setting on your computer? Or wished someone could just show you where to click? This AI Assistant does exactly that:

1. **You tell it what you want to do** - For example: "How do I test my speakers?"
2. **It figures out the steps** - The AI thinks: "First, open Settings, then System, then Sound..."
3. **It looks at your screen** - Takes a quick snapshot to see where you are
4. **It draws a rectangle** - Points exactly where you need to click
5. **You click, then say "next"** - And it guides you to the next step

It's like GPS navigation, but for your computer screen!

---

## Features

### Conversational Guidance
Just type naturally like you're talking to a friend:
- "How do I change my wallpaper?"
- "I want to connect to WiFi"
- "Help me test my audio"

### Smart 6-Step Pipeline
The assistant uses an efficient process:

| Step | What Happens | Uses AI? |
|------|-------------|----------|
| 1 | Figures out what to do next | Yes (no image) |
| 2 | Checks what screen you're on | Yes (quick look) |
| 3 | Decides exact button to click | Yes (no image) |
| 4 | Finds the button on screen | No (OCR only) |
| 5 | Stops analyzing immediately | No |
| 6 | Draws rectangle & waits | No |

### Visual Overlay
- Red rectangles highlight exactly where to click
- Stays on top of all windows
- Clear and easy to see

### Beautiful Dark Glass Design
- Modern "glassmorphism" aesthetic
- Semi-transparent frosted glass effect
- Sleek dark theme that's easy on the eyes

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+M` | Turn screen monitoring on/off |
| `Ctrl+Shift+G` | Show/hide the overlay |
| `Ctrl+Shift+E` | Edit overlay position manually |
| `Ctrl+Shift+C` | Clear all overlays |
| `Ctrl+Shift+A` | Ask AI about current screen |
| `Ctrl+Shift+N` | Go to next step |

---

## How It Works (Simple Explanation)

```
┌─────────────────────────────────────────────────────────────┐
│  YOU: "I want to test my speakers"                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: AI thinks "First step is to Open Settings"         │
│  (No screenshot needed - just logical thinking)             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Takes screenshot, AI says "You're on Desktop"      │
│  (Quick check - just identifies the screen)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: AI decides "Click on Settings icon"                │
│  (Adjusts based on where you actually are)                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4-6: Finds "Settings" text on screen using OCR,       │
│  draws a RED RECTANGLE around it, then STOPS and WAITS      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  YOU: Click on Settings, then type "next"                   │
│  → The cycle repeats for the next step!                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Used (In Plain English)

### The Brain: Google Gemini AI
- **What it is**: A smart AI from Google that can understand text and images
- **What it does here**: Figures out what steps you need and identifies your screen
- **Why it's good**: Very accurate at understanding context and giving helpful answers

### The Eyes: OCR (Optical Character Recognition)
- **What it is**: Technology that reads text from images
- **What it does here**: Finds where buttons and labels are on your screen
- **Tool used**: Tesseract OCR (free and open source)
- **Why it's good**: Fast and works offline once the AI decides what to look for

### The Interface: PyQt5
- **What it is**: A toolkit for building desktop applications
- **What it does here**: Creates the beautiful glass-like chat window
- **Why it's good**: Works on Windows, looks modern, very customizable

### The Overlay: Transparent Window
- **What it is**: An invisible window that sits on top of everything
- **What it does here**: Draws the red rectangles pointing to buttons
- **Why it's good**: Doesn't interfere with your apps, just highlights things

### Screen Capture: PIL (Pillow)
- **What it is**: A Python library for working with images
- **What it does here**: Takes screenshots of your desktop
- **Why it's good**: Fast, reliable, works with all screens

---

## Installation

### Prerequisites

1. **Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)

2. **Tesseract OCR**
   - Download from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
   - Install to `C:\Program Files\Tesseract-OCR\`

3. **Google Gemini API Key**
   - Get one free at [Google AI Studio](https://makersuite.google.com/app/apikey)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the App

```bash
python circular_window.py
```

---

## Quick Start Guide

1. **Launch the app** - A small circular window appears
2. **Click the window** - It expands into the chat interface
3. **Enter your API key** - Click the settings icon (gear) to add your Gemini API key
4. **Start chatting!** - Type something like "how do I check my wifi?"
5. **Follow the rectangles** - Click where it points, then type "next"
6. **Say "done" when finished** - Or "cancel" to stop anytime

---

## Example Conversations

### Testing Speakers
```
You: "I want to test my speakers"
AI: 🎯 Goal: test my speakers
    → Click on Settings
    [Red rectangle appears on Settings icon]

You: "next"
AI: → Click on System
    [Red rectangle appears on System]

You: "next"  
AI: → Click on Sound
    [Red rectangle appears on Sound]

You: "next"
AI: → Click on Test
    [Red rectangle appears on Test button]

You: "done"
AI: Great! Goal completed! 🎉
```

### Changing Wallpaper
```
You: "help me change my wallpaper"
AI: 🎯 Goal: change my wallpaper
    → Click on Settings
    ...
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "API key not configured" | Add your Gemini API key in settings |
| "Could not capture screen" | Make sure no other app is blocking screenshots |
| "Could not read screen text" | Make sure the target window is visible and not minimized |
| Rectangle in wrong place | Try saying "next" to refresh, or move closer to the target |
| App doesn't respond | Check if there's an error in the terminal window |

---

## File Structure

```
AI-assistant/
├── circular_window.py    # Main application (all the code)
├── task_graph.json       # Predefined task templates (optional)
├── guided_task.log       # Debug log file
└── README.md             # This documentation
```

---

## Privacy & Security

- **Screenshots stay local** - They're only sent to Google's AI API for analysis
- **No data stored** - Screenshots are discarded after each analysis
- **API key in memory only** - Not saved to disk (you enter it each session)

---

## Credits

- **UI Framework**: [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- **AI Model**: [Google Gemini](https://deepmind.google/technologies/gemini/)
- **OCR Engine**: [Tesseract](https://github.com/tesseract-ocr/tesseract)
- **Design Style**: Glassmorphism (frosted glass aesthetic)

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Contributing

Found a bug or have an idea? Please read our [CONTRIBUTING](CONTRIBUTING.md) guide before opening an issue or submitting a pull request.

---

Made with ❤️ to make computers easier for everyone.


## Future Plans

- **Audio Chat**: Voice interaction for hands-free guidance.
- **Cursor Control**: Allow the AI to perform clicks for you.
- **MCP Server**: Integrate with Model Context Protocol to use external tools.
- **Cross-Platform Support**: Mac and Linux support.
