import wave
import math
import struct
import sys
import subprocess
import os
import re
import random

VERSION = "1.0.2"

def check_dependencies():
    missing = []
    if subprocess.run(["which", "node"], capture_output=True).returncode != 0:
        missing.append("node")
    if subprocess.run(["which", "npm"], capture_output=True).returncode != 0:
        missing.append("npm")
    
    lame_path = "./node_modules/node-lame/vendor/lame/linux-x64/lame"
    if not os.path.exists(lame_path):
        missing.append("node-lame")

    if not missing:
        return True

    print(f"\nMissing dependencies identified: {', '.join(missing)}")
    confirm = input("Would you like to attempt to install them now? (yes/no): ").lower().strip()
    
    if confirm not in ['yes', 'y']:
        print("Installation cancelled. The script may not function correctly.")
        return False

    if "node" in missing or "npm" in missing:
        print("\nInstalling Node.js and npm via apt (requires sudo)...")
        try:
            if subprocess.run(["which", "apt-get"], capture_output=True).returncode == 0:
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs", "npm"], check=True)
            else:
                print("Error: apt-get not found. Please install Node.js and npm manually for your OS.")
                return False
        except subprocess.CalledProcessError as e:
            print(f"Failed to install system dependencies: {e}")
            return False

    if "node-lame" in missing:
        print("\nInstalling node-lame npm package...")
        try:
            subprocess.run(["npm", "install", "node-lame"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install node-lame: {e}")
            return False

    print("\nDependencies installed successfully.\n")
    return True

def calculate_timings(wpm_char, wpm_eff):
    tu = 1.2 / wpm_char
    if wpm_eff >= wpm_char:
        return tu, tu, tu * 3, tu * 7
    ts = (60.0 / wpm_eff - 31.0 * tu) / 19.0
    char_gap = 3.0 * ts
    word_gap = 7.0 * ts
    return tu, tu, char_gap, word_gap

def generate_random_text(count=10, mode="mixed"):
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    numbers = "0123456789"
    if mode == "letters":
        pool = letters
    elif mode == "numbers":
        pool = numbers
    else:
        pool = letters + numbers
    
    groups = []
    for _ in range(count):
        group = "".join(random.choice(pool) for _ in range(5))
        groups.append(group)
    return " ".join(groups)

def generate_morse_wav(text, tu, intra_gap, char_gap, word_gap, filename="temp_morse.wav"):
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

    SAMPLE_RATE = 44100
    FREQUENCY = 650.0
    RAMP_TIME = 0.005 # 5ms Rise/Fall time to prevent key clicks

    def append_tone(frames, duration, frequency, volume=0.5):
        num_samples = int(duration * SAMPLE_RATE)
        ramp_samples = int(RAMP_TIME * SAMPLE_RATE)
        
        for i in range(num_samples):
            # Apply linear volume ramp
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
                        append_tone(frames, tu, FREQUENCY)
                    elif bit == '-':
                        append_tone(frames, tu * 3, FREQUENCY)
                    if i < len(code) - 1:
                        append_silence(frames, tu)
                append_silence(frames, char_gap)

    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(b''.join(frames))

def convert_wav_to_mp3(wav_filename, mp3_filename):
    lame_path = "./node_modules/node-lame/vendor/lame/linux-x64/lame"
    try:
        subprocess.run([lame_path, "-S", wav_filename, mp3_filename], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during MP3 conversion: {e}")
        return False

if __name__ == "__main__":
    if not check_dependencies():
        print("Dependency check failed. Exiting.")
        sys.exit(1)

    while True:
        try:
            print(f"\n--- Morse Code MP3 Generator (Training Edition) v{VERSION} ---")
            char_speed = float(input("Enter Character Speed (WPM) [default 12]: ") or 12)
            eff_speed = float(input("Enter Effective Word Speed (WPM) [default 5]: ") or 5)
            
            raw_input = input("Enter Text (or type 'random' for practice groups): ")
            
            if raw_input.lower().strip() == 'random':
                count = int(input("How many groups of 5? [default 10]: ") or 10)
                m_type = input("Mode (letters/numbers/mixed) [default mixed]: ").lower() or "mixed"
                text = generate_random_text(count, m_type)
            else:
                text = raw_input
            
            if not text:
                print("Text cannot be empty.")
                continue

            print(f"\nConfiguration:")
            print(f"- Text/Practice: '{text}'")
            print(f"- Character Speed: {char_speed} WPM")
            print(f"- Effective Speed: {eff_speed} WPM")
            
            confirm = input("\nExecute script? (yes/no): ").lower().strip()
            
            if confirm in ['yes', 'y']:
                tu, intra, char_g, word_g = calculate_timings(char_speed, eff_speed)
                output_filename = "morse.mp3"
                temp_wav = "temp_morse.wav"
                
                print(f"Generating Morse code...")
                generate_morse_wav(text, tu, intra, char_g, word_g, temp_wav)
                
                if convert_wav_to_mp3(temp_wav, output_filename):
                    print(f"Successfully saved to {output_filename}")
                    if raw_input.lower().strip() == 'random':
                        print(f"ANSWER KEY: {text}")
                
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
                break
            else:
                print("Restarting configuration...\n")
                
        except ValueError:
            print("Invalid input. Please enter numbers where required.")
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(0)
