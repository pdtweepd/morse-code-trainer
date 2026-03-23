import wave
import math
import struct
import os
import re
import random
import subprocess
import tempfile

VERSION = "1.1.0"

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

def get_morse_pulses(text, tu, ts, char_gap, word_gap):
    # Returns a list of (is_signal, duration_units, label)
    text, _ = sanitize_text(text)
    pulses = []
    tokens = re.findall(r'<[^>]+>|.', text)
    for i, token in enumerate(tokens):
        if token == ' ':
            pulses.append((False, word_gap / tu, None))
        else:
            code = MORSE_CODE.get(token, "")
            for j, sym in enumerate(code):
                # Label only the first pulse of the character
                label = token if j == 0 else None
                
                if sym == '.':
                    pulses.append((True, 1, label))
                elif sym == '-':
                    pulses.append((True, 3, label))
                
                # Intra-character gap
                if j < len(code) - 1:
                    pulses.append((False, 1, None))
            
            # Inter-character gap
            if i < len(tokens) - 1 and tokens[i+1] != ' ':
                pulses.append((False, char_gap / tu, None))
    return pulses

class MorseDecoder:
    def __init__(self, wpm):
        self.wpm = wpm
        self.tu = 1.2 / wpm
        self.current_code = ""
        self.last_event_time = 0
        self.is_down = False
        
    def set_wpm(self, wpm):
        self.wpm = wpm
        self.tu = 1.2 / wpm

    def handle_event(self, is_down, timestamp):
        # timestamp is in seconds
        if self.last_event_time == 0:
            self.last_event_time = timestamp
            self.is_down = is_down
            return None

        duration = timestamp - self.last_event_time
        self.last_event_time = timestamp
        
        result = None
        
        if not is_down: # Key released (was down for 'duration')
            # Determine if it was a dit or dash
            if duration < self.tu * 2:
                self.current_code += "."
            else:
                self.current_code += "-"
        else: # Key pressed (was up for 'duration')
            # If gap > 3 units, it's the end of a character
            if duration > self.tu * 2.5:
                result = self.decode_current()
                
        self.is_down = is_down
        return result

    def decode_current(self):
        if not self.current_code:
            return None
            
        char = None
        # Reverse lookup MORSE_CODE
        for c, code in MORSE_CODE.items():
            if code == self.current_code:
                char = c
                break
        
        self.current_code = ""
        return char

    def check_timeout(self, timestamp):
        # Call this periodically to see if a character should be finalized
        if not self.is_down and self.current_code:
            if timestamp - self.last_event_time > self.tu * 3:
                return self.decode_current()
        return None

def generate_morse_wav(text, tu, char_gap, word_gap, frequency=650.0, qrn_level=0.0):
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
            
            # Sine wave signal
            signal = math.sin(2.0 * math.pi * frequency * i / SAMPLE_RATE)
            
            # Mix with QRN (white noise)
            noise = (random.random() * 2.0 - 1.0) * qrn_level
            mixed = (signal * (1.0 - qrn_level)) + noise
            
            value = int(mixed * 32767.0 * current_vol)
            frames.append(struct.pack('<h', value))

    def append_silence(frames, duration):
        num_samples = int(duration * SAMPLE_RATE)
        for i in range(num_samples):
            # Only noise in silence gaps
            noise = (random.random() * 2.0 - 1.0) * qrn_level
            value = int(noise * 32767.0 * 0.2) # Noise is quieter in gaps
            frames.append(struct.pack('<h', value))

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
    # Check for system lame first (best for compatibility across architectures)
    system_lame = "/usr/bin/lame"
    if os.path.exists(system_lame):
        return system_lame
        
    # Fallback to local node-lame paths
    paths = [
        "/usr/share/morse-converter/node_modules/node-lame/vendor/lame/linux-x64/lame",
        "./node_modules/node-lame/vendor/lame/linux-x64/lame"
    ]
    for p in paths:
        if os.path.exists(p): return os.path.abspath(p)
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
