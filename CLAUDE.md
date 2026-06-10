# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Picople** is a local, encrypted photo and video management desktop application for Windows, built with Python and PySide6 (Qt6). All processing is on-device — no cloud, no HTTP API.

## Commands

```bash
# Run the application
python -m picople.app.main

# Lint
ruff check src/

# Format
black src/

# Type check
mypy src/

# Run tests
pytest

# Admin CLI (database management)
python -m picople.app.admin info
python -m picople.app.admin purge
python -m picople.app.admin wipe-people [--vacuum] [--drop]
python -m picople.app.admin migrate
python -m picople.app.admin wipe-table <name> [--drop] [--vacuum]
python -m picople.app.admin wipe-all [--drop] [--vacuum]
```

The virtual environment is at `.venv/`. Python 3.10+ required.

## Architecture

### Layer Structure

```
src/picople/
├── app/          # Qt application shell (main, main_window, event_bus, admin CLI)
│   ├── controllers/  # Qt models + data classes (MediaListModel, AlbumListModel, MediaItem)
│   └── views/        # All QWidget views and delegates
├── core/         # Cross-cutting utilities (config, theme, paths, formats, fonts, log)
├── infrastructure/ # DB, indexing, thumbnails, face scan
│   ├── db.py           # SQLCipher connection + all media/album CRUD
│   ├── people_store.py # Person/face/suggestion CRUD
│   ├── indexer.py      # IndexerWorker (QThread): filesystem traversal + thumbnail generation
│   ├── face_scan.py    # FaceScanWorker (QThread): face detection + embeddings
│   └── thumbs.py       # Thumbnail generation (Pillow for images, FFmpeg for videos)
└── features/     # Reserved feature module stubs (currently empty)
```

### Navigation

`MainWindow` uses a `QStackedWidget` for page navigation. `_navigate(key)` switches the visible page. Sidebar buttons map to view instances stored in `self._pages`. The last active section is saved to `QSettings` and restored on launch.

### Database

SQLCipher (encrypted SQLite) is the single source of truth. The `Database` class in `infrastructure/db.py` manages the connection, schema creation, and all queries. Key tables: `media`, `folders`, `albums`, `album_media`, `persons`, `faces`, `person_alias`, `face_suggestions`, `face_scan_state`.

Workers (IndexerWorker, FaceScanWorker) open their own `Database` connections — do not pass the main-thread connection to QThread workers.

### Threading

Long operations run in QThread workers: `IndexerWorker` (indexing + thumbnailing) and `FaceScanWorker` (face detection, triggered by a 30s idle timer). Workers emit Qt signals to update the UI.

### State Management

- **QSettings**: persists theme, window geometry, root dirs, tile size, last section
- **Event bus** (`app/event_bus.py`): singleton `bus` QObject; currently carries `favoriteChanged(path, bool)` for cross-view sync
- **Qt models**: `MediaListModel` and `AlbumListModel` bridge DB data to views; `MediaListModel.append_items()` supports infinite scroll

### Theme System

Light and dark QSS stylesheets are defined in `core/theme.py` and reapplied at runtime. Theme choice is persisted via QSettings.

### Media Viewers

- `ImageView`: Pillow-based rendering with zoom, rotation, and drag-pan
- `VideoView`: FFmpeg-based playback (imageio-ffmpeg)
- `MediaViewer`: container that switches between the two based on `MediaItem.kind`
- `ViewerOverlay`: full-screen overlay wrapping MediaViewer (double-click to open, ✕ to close)

### Asset Resolution

`core/resources.py` provides `asset_path(*parts)`, a context manager that resolves assets from the package first, then falls back to `./assets/` in the repo root.
