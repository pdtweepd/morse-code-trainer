# Text to Morse Code MP3 Converter

A Python utility that converts text input into Morse code audio files in MP3 format with support for Farnsworth timing and prosigns.

## Features

- **Interactive Configuration**: Prompts for speeds and text at runtime.
- **Random Training Mode**: Generate random groups of 5 characters (letters, numbers, or mixed) for practice.
- **Farnsworth Timing**: Supports independent character speed and effective word speed for better learning.
- **Anti-Click Audio**: Implements 5ms Rise/Fall volume ramps for professional-sounding, click-free audio.
- **Prosign Support**: Handles common prosigns (e.g., `<BT>`, `<AR>`, `<SOS>`) as concatenated characters.

## Installation

To install the program and all its dependencies automatically, run:

```bash
sudo apt install ./morse-converter_1.0.2_all.deb
```

*Note: Using `apt` instead of `dpkg` ensures that system dependencies like `python3-tk` and `espeak` are installed automatically.*

## Usage

Run the script without arguments to start the interactive mode:

```bash
python3 text_to_morse_mp3.py
```

### Interactive Steps:
1. **Character Speed**: Enter the speed at which individual characters are sent (e.g., 12 WPM).
2. **Effective Speed**: Enter the overall word speed (e.g., 5 WPM). If this is lower than the character speed, Farnsworth spacing is applied.
3. **Text**: Enter the text to convert.
4. **Execution**: Confirm with `yes` to generate `morse.mp3`.

## Prosigns & Punctuation

The script supports standard punctuation and common prosigns. Prosigns should be wrapped in `<brackets>` to be played as a single, continuous character.

### Supported Prosigns:
- `<BT>` : New paragraph / Break (`-...-`)
- `<AR>` : End of message (`.-.-.`)
- `<AS>` : Wait (`.-...`)
- `<KN>` : Invitation for specific station (`-.--.`)
- `<SK>` : End of contact (`...-.-`)
- `<SOS>`: Distress signal (`...---...`)
- `<CT>` : Start of transmission (`-.-.-`)
- `<AA>` : New line / Unknown station (`.-.-`)
- `<BK>` : Break-in (`-...-.-`)
- `<CL>` : Closing (`-.-..-..`)

### Example Input:
`VVV <CT> CQ CQ DE MYCALL <BT> HELLO WORLD <AS> K`

## Technical Details

- **Frequency**: 650 Hz
- **Sample Rate**: 44.1 kHz
- **Default Char Speed**: 12 WPM
- **Default Eff. Speed**: 5 WPM
- **Timing**: Standard PARIS word basis (50 units per word).
