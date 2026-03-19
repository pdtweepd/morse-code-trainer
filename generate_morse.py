import wave
import math
import struct

def generate_morse_wav(text, filename="morse.wav"):
    MORSE_CODE = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
        'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
        'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
        'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
        'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.---', '2': '..---',
        '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
        '8': '---..', '9': '----.', ' ': '/'
    }

    SAMPLE_RATE = 44100
    FREQUENCY = 650.0
    
    # 12 WPM Character Speed
    UNIT_DURATION = 0.1 
    DOT_DURATION = UNIT_DURATION
    DASH_DURATION = UNIT_DURATION * 3
    INTRA_GAP = UNIT_DURATION
    
    # 5 WPM Effective Speed (Farnsworth timing)
    # T_s = (60/5 - 31*0.1) / 19 = 0.4684
    CHAR_GAP = 1.405
    WORD_GAP = 3.279

    def append_tone(frames, duration, frequency, volume=0.5):
        num_samples = int(duration * SAMPLE_RATE)
        for i in range(num_samples):
            value = int(volume * 32767.0 * math.sin(2.0 * math.pi * frequency * i / SAMPLE_RATE))
            frames.append(struct.pack('<h', value))

    def append_silence(frames, duration):
        num_samples = int(duration * SAMPLE_RATE)
        for i in range(num_samples):
            frames.append(struct.pack('<h', 0))

    frames = []
    text = text.upper()
    
    for char in text:
        if char in MORSE_CODE:
            code = MORSE_CODE[char]
            if code == '/':
                # Word gap is total 3.279s. 
                # Since we already appended CHAR_GAP after the previous character,
                # we only need to append the difference.
                append_silence(frames, WORD_GAP - CHAR_GAP)
            else:
                for i, bit in enumerate(code):
                    if bit == '.':
                        append_tone(frames, DOT_DURATION, FREQUENCY)
                    elif bit == '-':
                        append_tone(frames, DASH_DURATION, FREQUENCY)
                    
                    if i < len(code) - 1:
                        append_silence(frames, INTRA_GAP)
                
                append_silence(frames, CHAR_GAP)

    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(b''.join(frames))

if __name__ == "__main__":
    generate_morse_wav("Joke is de liefste van de wereld!")
