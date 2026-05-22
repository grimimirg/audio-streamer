# Contributing to Audio Streamer

Thank you for your interest in contributing to Audio Streamer! This document provides technical instructions for developers who want to contribute to the project.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Architecture](#project-architecture)
- [Adding a New Language](#adding-a-new-language)
- [Creating a New API Endpoint](#creating-a-new-api-endpoint)
- [Code Style Guidelines](#code-style-guidelines)
- [Submitting Changes](#submitting-changes)

---

## Development Setup

### Prerequisites
- Python 3.9+
- PortAudio development libraries (for PyAudio)
- Git

### Backend Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/grimimirg/audio-streamer.git
   cd audio-streamer
   ```

2. **Install system dependencies:**
   ```bash
   # On Ubuntu/Debian
   sudo apt update
   sudo apt install -y python3-dev portaudio19-dev

   # On Fedora/RHEL
   sudo dnf install -y python3-devel portaudio-devel

   # On macOS
   brew install portaudio
   ```

3. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   nano .env
   ```

6. **Run the application:**
   ```bash
   python app.py
   ```

The application will be available at `http://localhost:4986`

### Frontend Development

The frontend is vanilla JavaScript located in the `html-client/` directory. No build process is required - simply edit the JavaScript files and refresh your browser.

**Frontend structure:**
- `html-client/src/` - JavaScript source files
- `html-client/templates/` - HTML templates
- `html-client/static/` - Static assets (CSS, images)

**Development workflow:**
1. Make changes to JavaScript files in `html-client/src/`
2. Refresh your browser to see changes
3. For CSS changes, edit files in `html-client/static/`

---

## Project Architecture

Audio Streamer follows a clean modular architecture with clear separation of concerns:

### Backend Structure (Python/Flask)

```
audio-streamer/
├── app.py                      # Main entry point
├── classes/                    # Core application logic
│   ├── ApplicationController.py    # Main application controller
│   ├── AudioHttpFacade.py         # HTTP API facade
│   ├── handlers/                  # Request handlers
│   │   ├── AuthHandler.py         # Authentication
│   │   ├── CoverUploadHandler.py  # Album cover upload
│   │   ├── LiquidMusicHandler.py  # File-based music playback
│   │   ├── LocalizationHandler.py # Internationalization
│   │   └── StreamHandler.py       # Audio streaming
│   └── streamer/                  # Audio streaming engines
│       ├── AudioStreamerFactory.py
│       └── streamers/
│           ├── MicrophoneStreamer.py
│           ├── AudioInterfaceStreamer.py
│           └── LiquidMusicStreamer.py
├── utilities/                 # Shared utilities
│   ├── Constants.py           # Application constants
│   └── Logger.py              # Logging utilities
└── locales/                   # Translation files
    ├── en.yaml
    ├── it.yaml
    └── de.yaml
```

### Frontend Structure (JavaScript)

```
html-client/
├── src/                       # JavaScript source files
│   ├── index.js              # Main entry point
│   ├── player.js             # Audio player logic
│   ├── dashboard.js          # Dashboard functionality
│   ├── dashboard_liquid.js   # Liquid music dashboard
│   ├── i18n.js               # Internationalization
│   └── spectrum.js           # Audio spectrum visualization
├── templates/                # HTML templates
│   ├── index.html            # Main player page
│   ├── dashboard.html        # Dashboard page
│   └── dashboard_liquid.html # Liquid music dashboard
└── static/                   # Static assets
    ├── css/                  # Stylesheets
    └── js/                   # Compiled JavaScript
```

### Layer Responsibilities

**Application Layer** (`ApplicationController.py`)
- Initializes the application
- Manages startup and shutdown
- Coordinates between components

**HTTP Layer** (`AudioHttpFacade.py`)
- Handles HTTP requests and responses
- Manages WebSocket connections
- Routes requests to appropriate handlers

**Handler Layer** (`handlers/`)
- Implements specific business logic
- Processes user requests
- Manages state for different features

**Streamer Layer** (`streamer/`)
- Abstracts audio capture from different sources
- Implements audio processing
- Manages audio streaming to clients

**Utility Layer** (`utilities/`)
- Provides shared functionality
- Constants and configuration
- Logging and error handling

---

## Adding a New Language

Audio Streamer uses YAML files for internationalization. Adding a new language involves three steps:

### Step 1: Create the Translation File

Create a new YAML file in the `locales/` directory with the language code (e.g., `fr.yaml` for French):

```bash
touch locales/fr.yaml
```

Copy the structure from an existing language file (e.g., `en.yaml`) and translate all values:

```yaml
# locales/fr.yaml
player:
  title: "Lecteur Audio"
  play: "Lecture"
  pause: "Pause"
  stop: "Arrêt"
  # ... translate all other keys

dashboard:
  title: "Tableau de Bord"
  # ... translate all other keys
```

### Step 2: Register the Language

Edit `html-client/src/i18n.js` to add the new language to the available languages:

```javascript
const availableLanguages = {
    en: 'English',
    it: 'Italiano',
    de: 'Deutsch',
    fr: 'Français'  // Add your new language
};
```

### Step 3: Test the Translation

1. Start the application: `python app.py`
2. Open the web interface: `http://localhost:4986`
3. Select your new language from the dropdown
4. Verify all text is translated correctly

---

## Creating a New API Endpoint

This guide shows how to add a new API endpoint following the handler/facade pattern.

### Example: Adding a "Volume Control" Feature

#### Step 1: Define the Handler

Create a new handler in `classes/handlers/` (or extend an existing one):

```python
# classes/handlers/VolumeHandler.py
from utilities.Logger import Logger

class VolumeHandler:
    def __init__(self):
        self.current_volume = 100  # Default volume (0-100)
    
    def set_volume(self, volume):
        """Set the audio volume level.
        
        Args:
            volume (int): Volume level between 0 and 100
            
        Returns:
            dict: Response with status and message
        """
        try:
            if not 0 <= volume <= 100:
                return {
                    'success': False,
                    'message': 'Volume must be between 0 and 100'
                }
            
            self.current_volume = volume
            Logger.info(f"Volume set to {volume}%")
            
            return {
                'success': True,
                'message': f'Volume set to {volume}%',
                'volume': self.current_volume
            }
        except Exception as e:
            Logger.error(f"Error setting volume: {e}")
            return {
                'success': False,
                'message': 'Failed to set volume'
            }
    
    def get_volume(self):
        """Get the current volume level.
        
        Returns:
            dict: Response with current volume
        """
        return {
            'success': True,
            'volume': self.current_volume
        }
```

#### Step 2: Register the Handler in the Facade

Add the handler to `AudioHttpFacade.py`:

```python
from handlers.VolumeHandler import VolumeHandler

class AudioHttpFacade:
    def __init__(self):
        # ... existing handlers
        self.volume_handler = VolumeHandler()
    
    def setup_routes(self, app):
        # ... existing routes
        
        # Volume control routes
        @app.route('/api/volume', methods=['GET'])
        def get_volume():
            return jsonify(self.volume_handler.get_volume())
        
        @app.route('/api/volume', methods=['POST'])
        def set_volume():
            data = request.get_json()
            volume = data.get('volume', 100)
            return jsonify(self.volume_handler.set_volume(volume))
```

#### Step 3: Test the Endpoint

```bash
# Get current volume
curl http://localhost:4986/api/volume

# Set volume to 50%
curl -X POST http://localhost:4986/api/volume \
  -H "Content-Type: application/json" \
  -d '{"volume": 50}'
```

#### Step 4: Add Frontend Integration (Optional)

Update the relevant JavaScript file in `html-client/src/` to use the new API:

```javascript
// Example in dashboard.js
async function setVolume(volume) {
    try {
        const response = await fetch('/api/volume', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ volume: volume })
        });
        const data = await response.json();
        if (data.success) {
            console.log(data.message);
        }
    } catch (error) {
        console.error('Error setting volume:', error);
    }
}
```

---

## Code Style Guidelines

### Python (Backend)
- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for all functions and classes
- Maximum line length: 100 characters
- Use meaningful variable and function names
- Use the existing Logger utility for logging (no print statements)

### JavaScript (Frontend)
- Use ES6+ syntax
- Write JSDoc comments for complex functions
- Use meaningful variable and function names
- Follow existing patterns in the codebase
- Use async/await for asynchronous operations

### General
- Write clear, descriptive commit messages
- Keep functions small and focused
- Don't repeat yourself (DRY principle)
- Add comments for complex logic
- Remove unused code and imports
- Test your changes before submitting

---

## Submitting Changes

### Branch and Issue Workflow

1. **Check for existing issues:**
   - Search the [GitHub Issues](https://github.com/grimimirg/audio-streamer/issues) to see if your feature or bug fix is already being discussed
   - If not, create a new issue describing the change you want to make

2. **Fork the repository** on GitHub

3. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/audio-streamer.git
   cd audio-streamer
   ```

4. **Add the upstream remote:**
   ```bash
   git remote add upstream https://github.com/grimimirg/audio-streamer.git
   ```

5. **Create a feature branch** from the main branch:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/your-feature-name
   ```
   
   **Branch naming conventions:**
   - `feature/feature-name` - New features
   - `fix/bug-name` - Bug fixes
   - `docs/update-name` - Documentation updates
   - `refactor/component-name` - Code refactoring

6. **Make your changes** following the guidelines above

7. **Test your changes:**
   - Ensure the application starts without errors
   - Test the specific feature you modified
   - Check that existing functionality still works
   - Test on different audio input modes if applicable

8. **Commit your changes** with clear messages:
   
   **Commit Message Format:**
   ```
   type(scope): brief description
   
   Detailed explanation (if needed)
   
   References #issue-number
   ```
   
   **Available commit types:**
   - `feat` - New feature
   - `fix` - Bug fix
   - `docs` - Documentation changes
   - `refactor` - Code refactoring
   - `style` - Code style changes (formatting, etc.)
   - `test` - Test additions or changes
   - `chore` - Maintenance tasks
   
   **Example commit messages:**
   ```bash
   # Feature addition
   git commit -m "feat(dashboard): add volume control slider"
   
   # Bug fix
   git commit -m "fix(streamer): resolve audio buffer overflow issue"
   
   # Documentation
   git commit -m "docs(readme): update installation instructions for macOS"
   ```

9. **Push to your branch:**
   ```bash
   git push origin feature/your-feature-name
   ```

10. **Open a Pull Request** on GitHub with:
    - Clear title describing the change
    - Detailed description of what you changed and why
    - Reference to the related issue (e.g., "Closes #123")
    - Screenshots for UI changes (if applicable)
    - List of testing performed

11. **Respond to review feedback:**
    - Address any comments or suggestions
    - Make additional commits if needed
    - Keep the PR updated until it's merged

12. **After merge:**
    - Update your local main branch:
      ```bash
      git checkout main
      git pull upstream main
      ```
    - Delete your feature branch:
      ```bash
      git branch -d feature/your-feature-name
      ```

### Pull Request Guidelines

- **One PR per feature/fix** - Keep changes focused
- **Small, incremental PRs** are easier to review
- **Include tests** for new features (when applicable)
- **Update documentation** if your change affects user-facing behavior
- **Follow the existing code style**
- **Write clear commit messages** (use `git rebase -i` to clean up history if needed)

### Getting Help

If you need help contributing:
- Check existing issues for similar problems
- Read the [User Manual](USER_MANUAL.md) for technical details
- Ask questions in GitHub Issues (tag with `question`)
- Review existing PRs to understand the contribution patterns

---

Thank you for contributing to Audio Streamer! Your contributions help make this project better for everyone.
