import wave
import math
import struct
import os
import re
import random
import subprocess
import tempfile

VERSION = "1.0.2"

MORSE_CODE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.---', '2': '..---',
    '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..', '9': '----.', ' ': '/',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', '!': '-.-.--',
    '/': '-..-.', '(': '-.--.', ')': '-.--.-', '&': '.-...', ':': '---...',
    ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-', '_': '..--.-',
    '"': '.-..-.', '$': '...-..-', '@': '.--.-.',
    '<AA>': '.-.-', '<AR>': '.-.-.', '<AS>': '.-...', '<BT>': '-...-',
    '<CL>': '-.-..-..', '<CT>': '-.-.-', '<KN>': '-.--.', '<SK>': '...-.-',
    '<SOS>': '...---...', '<BK>': '-...-.-'
}

# Standard Koch character order
KOCH_SEQUENCE = "KMRSUAPTLOWI.NJEF0Y,VG5/Q9ZH38B?427C16"

def calculate_timings(wpm_char, wpm_eff):
    tu = 1.2 / wpm_char
    if wpm_eff >= wpm_char:
        return tu, tu, tu * 3, tu * 7
    ts = (60.0 / wpm_eff - 31.0 * tu) / 19.0
    char_gap = 3.0 * ts
    word_gap = 7.0 * ts
    return tu, tu, char_gap, word_gap

def sanitize_text(text):
    text = text.upper()
    sanitized = []
    ignored = set()
    tokens = re.findall(r'<[^>]+>|.', text)
    for token in tokens:
        if token in MORSE_CODE:
            sanitized.append(token)
        elif token.startswith('<') and token.endswith('>'):
            inner = token[1:-1]
            valid_inner = True
            for char in inner:
                if char not in MORSE_CODE:
                    valid_inner = False
                    ignored.add(char)
            if valid_inner and inner:
                sanitized.append(token)
            else:
                ignored.add(token)
        elif token.isspace():
            sanitized.append(' ')
        else:
            ignored.add(token)
    return "".join(sanitized), ignored

def get_visual_morse(text):
    text, _ = sanitize_text(text)
    visual = []
    tokens = re.findall(r'<[^>]+>|.', text)
    for token in tokens:
        if token == ' ':
            visual.append("   ")
        else:
            code = MORSE_CODE.get(token, "")
            visual.append(code + " ")
    return "".join(visual)

def generate_random_text(count=10, mode="mixed", koch_level=2):
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    numbers = "0123456789"
    punctuation = ".,?!/()&:;=+-_\"$@"
    
    if mode == "letters":
        pool = letters
    elif mode == "numbers":
        pool = numbers
    elif mode == "punctuation":
        pool = punctuation
    elif mode == "koch":
        pool = KOCH_SEQUENCE[:max(2, min(koch_level, len(KOCH_SEQUENCE)))]
    else: # mixed
        pool = letters + numbers + punctuation
    
    groups = []
    for _ in range(count):
        group = "".join(random.choice(pool) for _ in range(5))
        groups.append(group)
    return " ".join(groups)

def generate_morse_wav(text, tu, char_gap, word_gap, frequency=650.0):
    SAMPLE_RATE = 44100
    RAMP_TIME = 0.005 # 5ms

    def append_tone(frames, duration, frequency, volume=0.5):
        num_samples = int(duration * SAMPLE_RATE)
        ramp_samples = int(RAMP_TIME * SAMPLE_RATE)
        for i in range(num_samples):
            current_vol = volume
            if i < ramp_samples:
                current_vol = volume * (i / ramp_samples)
            elif i > num_samples - ramp_samples:
                current_vol = volume * ((num_samples - i) / ramp_samples)
            value = int(current_vol * 32767.0 * math.sin(2.0 * math.pi * frequency * i / SAMPLE_RATE))
            frames.append(struct.pack('<h', value))

    def append_silence(frames, duration):
        num_samples = int(duration * SAMPLE_RATE)
        for i in range(num_samples):
            frames.append(struct.pack('<h', 0))

    frames = []
    tokens = re.findall(r'<[^>]+>|.', text.upper())
    
    for token in tokens:
        if token == ' ':
            append_silence(frames, max(0, word_gap - char_gap))
            continue
            
        code = MORSE_CODE.get(token)
        if not code and token.startswith('<') and token.endswith('>'):
            alt_token = token[1:-1]
            code = "".join(MORSE_CODE.get(c, "") for c in alt_token)
        
        if code:
            if code == '/':
                append_silence(frames, max(0, word_gap - char_gap))
            else:
                for i, bit in enumerate(code):
                    if bit == '.':
                        append_tone(frames, tu, frequency)
                    elif bit == '-':
                        append_tone(frames, tu * 3, frequency)
                    if i < len(code) - 1:
                        append_silence(frames, tu)
                append_silence(frames, char_gap)

    fd, path = tempfile.mkstemp(suffix=".wav", prefix="morse_")
    try:
        with os.fdopen(fd, 'wb') as tmp:
            with wave.open(tmp, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(b''.join(frames))
        return path
    except Exception as e:
        if os.path.exists(path): os.remove(path)
        raise e

def generate_voice_wav(text):
    """Generates a WAV file using espeak TTS."""
    # Clean text for espeak (remove prosign brackets)
    clean_text = re.sub(r'[<>]', ' ', text)
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="voice_")
    os.close(fd) # Close it so espeak can write to it
    try:
        # Use espeak to generate speech. -w writes to wav.
        subprocess.run(["espeak", "-w", path, clean_text], check=True)
        return path
    except Exception:
        if os.path.exists(path): os.remove(path)
        return None

def combine_wavs(wav_list, output_filename):
    """Combines multiple WAV files into one."""
    data = []
    params = None
    for wav_file in wav_list:
        if not wav_file or not os.path.exists(wav_file): continue
        with wave.open(wav_file, 'rb') as w:
            if params is None:
                params = w.getparams()
            # If files have different sample rates, this simple join will fail.
            # But espeak and our gen both use standard rates.
            data.append(w.readframes(w.getnframes()))
    
    if not data: return None
    
    fd, path = tempfile.mkstemp(suffix=".wav", prefix="combined_")
    try:
        with os.fdopen(fd, 'wb') as tmp:
            with wave.open(tmp, 'wb') as output:
                output.setparams(params)
                for d in data:
                    output.writeframes(d)
        return path
    except Exception as e:
        if os.path.exists(path): os.remove(path)
        raise e

def get_lame_path():
    paths = [
        "/usr/share/morse-converter/node_modules/node-lame/vendor/lame/linux-x64/lame",
        "./node_modules/node-lame/vendor/lame/linux-x64/lame"
    ]
    for p in paths:
        abs_p = os.path.abspath(p)
        if os.path.exists(abs_p): return abs_p
    return None

def convert_wav_to_mp3(wav_filename, mp3_filename):
    lame_path = get_lame_path()
    if not lame_path: return False, "Lame encoder not found."
    if not os.path.isabs(mp3_filename): mp3_filename = os.path.join(".", mp3_filename)
    try:
        subprocess.run([lame_path, "-S", wav_filename, mp3_filename], check=True)
        return True, "Success"
    except subprocess.CalledProcessError as e:
        return False, f"Error: {e}"

def play_wav(wav_filename):
    try:
        subprocess.Popen(["/usr/bin/aplay", "-q", "--", wav_filename])
        return True, "Playing..."
    except Exception as e:
        return False, f"Playback error: {e}"
