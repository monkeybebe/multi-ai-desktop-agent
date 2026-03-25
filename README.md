# WA/D - Wisdom Assistor/Distributor

A multi-agent AI desktop assistant capable of observing, reasoning, and interacting with your screen in real time. WA/D sends the same problem to multiple AI models, compares their answers, and selects the best response through a consensus engine.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    WA/D Application                      │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  OpenAI   │  │ Anthropic│  │  Gemini  │  │ Copilot │ │
│  │  Agent    │  │  Agent   │  │  Agent   │  │  Agent  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │              │              │              │      │
│       └──────────────┴──────┬───────┴──────────────┘      │
│                             │                             │
│                    ┌────────▼────────┐                    │
│                    │ Agent Manager   │                    │
│                    └────────┬────────┘                    │
│                             │                             │
│  ┌──────────┐      ┌───────▼────────┐     ┌───────────┐ │
│  │  Screen   │◄────►│ FastAPI Server │◄───►│  Action   │ │
│  │  Parser   │      │  (WebSocket)   │     │Controller │ │
│  └──────────┘      └───────┬────────┘     └───────────┘ │
│                             │                             │
│  ┌──────────┐      ┌───────▼────────┐     ┌───────────┐ │
│  │ Decision  │◄────►│   Web UI       │◄───►│  Safety   │ │
│  │  Engine   │      │  Dashboard     │     │ Monitor   │ │
│  └──────────┘      └───────┬────────┘     └───────────┘ │
│                             │                             │
│                    ┌────────▼────────┐                    │
│                    │  Memory Store   │                    │
│                    │   (SQLite)      │                    │
│                    └─────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

## Features

### Multi-AI Integration
- **OpenAI GPT** - GPT-4o with vision support
- **Anthropic Claude** - Claude with vision support
- **Google Gemini** - Gemini 1.5 Pro with vision support
- **Microsoft Copilot** - Azure OpenAI / compatible endpoints

### Screen Awareness
- Continuous screen capture with monitor selection
- OCR text extraction via Tesseract
- Structured screen state representation
- Multi-monitor support with per-monitor selection

### Consensus Engine
- Sends the same problem to all configured AI agents simultaneously
- Compares answers using text similarity analysis
- Scores confidence based on:
  - Self-reported agent confidence (30%)
  - Agreement between agents (50%)
  - Reasoning quality (20%)
- Selects the best answer with full transparency

### Desktop Automation
- Mouse control (click, double-click, right-click, drag)
- Keyboard input (typing, hotkeys)
- Scrolling
- All actions require explicit user permission

### Learning & Memory
- SQLite-backed persistent memory
- Stores past problems, answers, and outcomes
- Agents can reference previous interactions for context
- Statistics on accuracy and confidence

### Transparency Dashboard
- Real-time view of each agent's response
- Confidence scores and reasoning displayed
- Vote breakdown showing how consensus was reached
- Full decision process visibility

### Safety Controls
- Explicit permission required before any screen control
- Visible automation status indicator
- Pause / Resume / Emergency Stop controls
- Rate limiting on automated actions
- Fail-safe hotkey: `Ctrl+Shift+Escape`

## Setup

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation) (recommended) or pip
- Tesseract OCR (optional, for OCR features)

#### Install Tesseract (optional)

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract

# Windows: Download from https://github.com/tesseract-ocr/tesseract
```

### Installation

```bash
# Clone the repository
git clone https://github.com/monkeybebe/multi-ai-desktop-agent.git
cd multi-ai-desktop-agent

# Install with Poetry (recommended)
poetry install

# Or install with pip
pip install -r requirements.txt
```

### Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Add your API keys to `.env`:
```env
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GOOGLE_API_KEY=your-google-api-key
MICROSOFT_API_KEY=your-microsoft-api-key
```

You only need to configure the AI providers you want to use. At least one API key is required.

API keys can also be configured at runtime through the Settings tab in the UI.

### Running

```bash
# With Poetry
poetry run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Or directly
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Or use the CLI shortcut
poetry run wad
```

Then open your browser to [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Usage

### Quick Start

1. Open the app in your browser
2. Go to the **Settings** tab and enter at least one API key
3. Type a question or instruction in the chat input
4. Check "Include screen capture" to have agents analyze your screen
5. Select which monitor to capture from the dropdown
6. View agent responses, confidence scores, and consensus in the **Agents** tab

### Screen Capture

1. Go to the **Controls** tab
2. Click **Grant Permission** under Screen Capture
3. Select your monitor from the dropdown
4. Check "Include screen capture" in the chat input area
5. Agents will now receive screenshots with your queries

### Desktop Automation

1. Go to the **Controls** tab
2. Click **Enable** under Desktop Automation
3. The automation status indicator in the header will show "Active"
4. Use **Pause** / **Resume** to temporarily control automation
5. Use **EMERGENCY STOP** or press `Ctrl+Shift+Escape` to immediately halt all automation

## Project Structure

```
multi-ai-desktop-agent/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application & API routes
│   ├── config.py             # Configuration management
│   ├── agents/
│   │   ├── base.py           # Base agent interface
│   │   ├── openai_agent.py   # OpenAI GPT agent
│   │   ├── anthropic_agent.py # Anthropic Claude agent
│   │   ├── gemini_agent.py   # Google Gemini agent
│   │   ├── copilot_agent.py  # Microsoft Copilot agent
│   │   └── manager.py        # Agent orchestrator
│   ├── screen/
│   │   ├── capture.py        # Screen capture (mss)
│   │   ├── ocr.py            # OCR processing (Tesseract)
│   │   └── parser.py         # Screen state parser
│   ├── decision/
│   │   └── engine.py         # Consensus / decision engine
│   ├── action/
│   │   └── controller.py     # Desktop automation (PyAutoGUI)
│   ├── memory/
│   │   └── store.py          # SQLite memory store
│   └── safety/
│       └── monitor.py        # Safety constraints & monitoring
├── static/
│   ├── index.html            # Main UI
│   ├── css/style.css         # Styles
│   └── js/app.js             # Frontend application
├── tests/
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve the web UI |
| GET | `/api/agents` | Get agent statuses |
| POST | `/api/agents/key` | Update an agent's API key |
| POST | `/api/query` | Query all agents with consensus |
| POST | `/api/query/upload` | Query with uploaded screenshot |
| GET | `/api/screen/monitors` | List available monitors |
| POST | `/api/screen/permission` | Grant/revoke screen permission |
| GET | `/api/screen/capture` | Capture current screen |
| POST | `/api/action/permission` | Grant/revoke automation permission |
| POST | `/api/action/execute` | Execute a desktop action |
| POST | `/api/action/pause` | Pause automation |
| POST | `/api/action/resume` | Resume automation |
| POST | `/api/action/stop` | Emergency stop |
| GET | `/api/memory/recent` | Get recent memory entries |
| POST | `/api/memory/outcome` | Update outcome of memory entry |
| GET | `/api/memory/stats` | Get memory statistics |
| POST | `/api/memory/clear` | Clear all memory |
| GET | `/api/safety/status` | Get safety status |
| GET | `/api/safety/events` | Get safety events |
| GET | `/api/settings` | Get current settings |
| POST | `/api/settings` | Update settings |
| WS | `/ws` | WebSocket for real-time updates |

## License

MIT
