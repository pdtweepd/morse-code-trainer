# Morse Code Trainer Project Context

This file preserves the state and instructions for the Morse Code Trainer project. Read this first when resuming development.

## Project Overview
A comprehensive Morse code learning and conversion suite featuring a Python-based GUI, Farnsworth timing, Koch method training, and MP3 export capabilities.

## Key Components
- **`morse_logic.py`**: The core engine. Handles timing calculations (Standard & Farnsworth), WAV generation with 5ms anti-click ramps, random text generation (including Koch sequence), and MP3 conversion.
- **`morse_gui.py`**: The `tkinter` interface. Features real-time visual Morse feed, speed sliders, frequency control, and a "Voice Answer Key" toggle (using `espeak`).
- **`build_deb.sh`**: Automation script to build the `morse-converter_1.0.2_all.deb` package. It bundles the `node-lame` encoder and sets up system shortcuts.
- **`text_to_morse_mp3.py`**: The original interactive CLI version (preserved for compatibility).
- **`README.md`**: User-facing documentation.

## Technical Specifications
- **Frequency**: 650 Hz (sine wave).
- **Sample Rate**: 44.1 kHz.
- **Timing Basis**: PARIS standard (50 units).
- **MP3 Encoder**: LAME (via `node-lame`).
- **TTS Engine**: `espeak`.

## Build & Run Instructions
- **Run GUI**: `python3 morse_gui.py`
- **Build Debian Package**: `bash build_deb.sh`
- **Install Package**: `sudo apt install ./morse-converter_1.0.1_all.deb`

## Security Hardening Implemented
- **Secure Temp Files**: Uses `tempfile` to prevent symlink attacks.
- **Injection Prevention**: Uses list-based `subprocess` calls with `--` separators.
- **Path Validation**: Prioritizes absolute system paths for binaries.
- **Sanitization**: Input is filtered through `sanitize_text` to remove unsupported characters.

## Future Development Ideas
- Implement background noise (QRN) simulation.
- Add a "Koch Progress" tracker to save user levels.
- Enhance the visual feed with a scrolling "Waterfall" display.
