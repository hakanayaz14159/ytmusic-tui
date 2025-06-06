# YTMusic CLI

A modern command-line interface with Terminal User Interface (TUI) for YouTube Music, built with Python.

## 🎵 Features

- **Terminal User Interface (TUI)** - Beautiful, interactive interface built with Textual
- **Music Playback** - Stream and download music from YouTube Music
- **Playlist Management** - Create, manage, and sync playlists
- **Search & Discovery** - Search for songs, artists, albums, and playlists
- **Local Database** - Store preferences and playlist data locally
- **Cross-platform** - Works on Linux, macOS, and Windows

## 🚀 Installation

### Prerequisites

- Python 3.11 or higher
- Poetry (recommended) or pip

### Install with Poetry (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/ytmusic-cli.git
cd ytmusic-cli

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

### Install with pip

```bash
# Clone the repository
git clone https://github.com/yourusername/ytmusic-cli.git
cd ytmusic-cli

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

## 📖 Usage

### Launch the TUI

```bash
ytmusic-cli
```

### Command Line Options

```bash
# Start with debug mode
ytmusic-cli --debug

# Show version
ytmusic-cli --version

# Show help
ytmusic-cli --help
```

### Key Bindings

- `q` or `Ctrl+C` - Quit application
- `↑/↓` - Navigate lists
- `Enter` - Select/Play
- `Space` - Play/Pause
- `s` - Search
- `p` - Show playlists
- `h` - Show help

## 🛠️ Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/yourusername/ytmusic-cli.git
cd ytmusic-cli

# Install with development dependencies
poetry install --with dev

# Activate virtual environment
poetry shell

# Install pre-commit hooks
pre-commit install
```

### Code Formatting and Linting

```bash
# Format code with black
black src/

# Sort imports with isort
isort src/

# Run linting with ruff
ruff check src/

# Type checking with mypy
mypy src/

# Run all checks
make lint
```

### Testing

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_main.py
```

### Project Structure

```
ytmusic-cli/
├── src/
│   ├── main.py              # Application entry point
│   ├── db/                  # Database models and operations
│   │   └── user.py         # User preferences and data
│   ├── tui/                # Textual UI components
│   ├── music/              # Music playback and management
│   └── utils/              # Utility functions
├── tests/                  # Test files
├── docs/                   # Documentation
├── pyproject.toml          # Project configuration
└── README.md              # This file
```

### Available Make Commands

```bash
make install     # Install dependencies
make dev-install # Install with dev dependencies
make format      # Format code (black + isort)
make lint        # Run all linters
make test        # Run tests
make clean       # Clean build artifacts
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the linting and tests (`make lint && make test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Code Style

- Follow PEP 8
- Use Black for code formatting
- Use isort for import sorting
- Add type hints where appropriate
- Write docstrings for functions and classes

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Your Name** - _Initial work_ - [hakanayaz14159@gmail.com](mailto:hakanayaz14159@gmail.com)

## 🙏 Acknowledgments

- [Textual](https://github.com/Textualize/textual) - For the amazing TUI framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - For YouTube downloading capabilities
- [Peewee](https://github.com/coleifer/peewee) - For the lightweight ORM

## 📊 Roadmap

- [ ] Basic TUI interface
- [ ] Music search functionality
- [ ] Playlist management
- [ ] Audio playback integration
- [ ] User authentication
- [ ] Offline mode
- [ ] Custom themes
- [ ] Plugin system

## 🐛 Known Issues

See [Issues](https://github.com/yourusername/ytmusic-cli/issues) for a list of known issues and feature requests.

## 📚 Documentation

For more detailed documentation, visit our [docs](docs/) directory or check the [Wiki](https://github.com/yourusername/ytmusic-cli/wiki).
