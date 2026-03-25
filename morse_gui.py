try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, scrolledtext
except ImportError:
    print("Error: The 'tkinter' module is missing.")
    print("Please install it by running: sudo apt-get install python3-tk")
    import sys
    sys.exit(1)

import os
import time
import subprocess
import tempfile
import threading
import select
import glob
import struct
import morse_logic

class MorseApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Morse Code Trainer v{morse_logic.VERSION}")
        
        # High DPI scaling
        try:
            self.root.tk.call('tk', 'scaling', 1.5)
        except:
            pass
            
        self.root.geometry("750x850")
        
        # Variables
        self.char_wpm = tk.IntVar(value=12)
        self.eff_wpm = tk.IntVar(value=5)
        self.freq = tk.DoubleVar(value=650)
        
        # Default to home directory
        home_dir = os.path.expanduser("~")
        self.output_file = tk.StringVar(value=os.path.join(home_dir, "morse_practice.mp3"))
        
        self.random_count = tk.IntVar(value=10)
        self.random_mode = tk.StringVar(value="mixed")
        self.koch_level = tk.IntVar(value=2)
        self.include_voice = tk.BooleanVar(value=False)
        self.vband_enabled = tk.BooleanVar(value=False)
        self.qrn_level = tk.DoubleVar(value=0.0)
        
        self.decoder = morse_logic.MorseDecoder(self.char_wpm.get())
        self.user_pulses = [] # [(is_signal, duration, start_time)]
        self.sidetone_proc = None # For real-time VBand audio feedback
        self.scrolling = False
        self.scroll_offset = 0
        self.pulses = []
        self._pending_temp_files = []
        self._dongle_stop = threading.Event()
        self._dongle_thread = None

        self.create_widgets()
        self.bind_keys()
        self.vband_enabled.trace_add('write', self._on_vband_toggle)
        self.check_decoder_timeout()

    # ------------------------------------------------------------------ #
    #  Evdev constants for reading raw Linux input events                 #
    # ------------------------------------------------------------------ #
    _INPUT_EVENT_FMT = '@qqHHi'  # timeval(sec, usec), type, code, value
    _INPUT_EVENT_SIZE = struct.calcsize('@qqHHi')
    _EV_KEY = 1

    def bind_keys(self):
        for key in ['bracketleft', 'bracketright', 'period', 'comma', 'slash', 'space']:
            self.root.bind(f'<KeyPress-{key}>', self.on_key_press)
            self.root.bind(f'<KeyRelease-{key}>', self.on_key_release)

    # ---------- dongle discovery ---------- #

    def _find_dongle(self):
        """Return the /dev/input/eventN path for the VBand HID dongle (413d:2107), or None."""
        for vendor_path in glob.glob('/sys/class/input/event*/device/id/vendor'):
            try:
                vendor = open(vendor_path).read().strip()
                product = open(vendor_path.replace('vendor', 'product')).read().strip()
                if vendor == '413d' and product == '2107':
                    event_name = vendor_path.split('/sys/class/input/')[1].split('/')[0]
                    return f'/dev/input/{event_name}'
            except Exception:
                pass
        return None

    # ---------- dongle reader thread ---------- #

    def _dongle_reader(self, device_path, stop_event):
        try:
            with open(device_path, 'rb') as f:
                while not stop_event.is_set():
                    r, _, _ = select.select([f], [], [], 0.1)
                    if not r:
                        continue
                    data = f.read(self._INPUT_EVENT_SIZE)
                    if len(data) < self._INPUT_EVENT_SIZE:
                        break
                    _, _, evtype, _code, value = struct.unpack(self._INPUT_EVENT_FMT, data)
                    if evtype == self._EV_KEY:
                        if value == 1:    # key down
                            self.root.after(0, self._handle_key_down)
                        elif value == 0:  # key up
                            self.root.after(0, self._handle_key_up)
        except PermissionError:
            self.root.after(0, lambda: self.status.config(
                text="Dongle error: permission denied — run: sudo usermod -aG input $USER",
                foreground="red"))
        except Exception:
            pass

    # ---------- shared key handlers (keyboard + dongle) ---------- #

    def _handle_key_down(self):
        if not self.vband_enabled.get(): return
        if self.decoder.is_down: return  # Prevent auto-repeat
        now = time.time()
        self.user_pulses.append([True, 0, now])
        char = self.decoder.handle_event(True, now)
        if char:
            self.decoded_text.insert(tk.END, char)
            self.decoded_text.see(tk.END)
        if not self.sidetone_proc:
            try:
                freq = self.freq.get()
                if not hasattr(self, '_tone_path') or getattr(self, '_tone_freq', None) != freq:
                    if hasattr(self, '_tone_path') and os.path.exists(self._tone_path):
                        os.remove(self._tone_path)
                    self._tone_path = morse_logic.generate_tone_wav(10.0, freq)
                    self._tone_freq = freq
                self.sidetone_proc = subprocess.Popen(["/usr/bin/aplay", "-q", self._tone_path])
            except Exception:
                pass

    def _handle_key_up(self):
        if not self.vband_enabled.get(): return
        if self.sidetone_proc:
            try:
                self.sidetone_proc.terminate()
            except Exception:
                pass
            self.sidetone_proc = None
        now = time.time()
        self.decoder.handle_event(False, now)
        if self.user_pulses and self.user_pulses[-1][0]:
            self.user_pulses[-1][1] = now - self.user_pulses[-1][2]
            self.user_pulses.append([False, 0, now])

    def on_key_press(self, event):
        self._handle_key_down()

    def on_key_release(self, event):
        self._handle_key_up()

    # ---------- VBand toggle ---------- #

    def _on_vband_toggle(self, *args):
        vband_keys = ['bracketleft', 'bracketright', 'period', 'comma', 'slash', 'space']
        if self.vband_enabled.get():
            self.decoder.reset()
            self.user_pulses = []
            # Block VBand keys from typing into the text input
            for key in vband_keys:
                self.text_input.bind(f'<KeyPress-{key}>', lambda e: "break")
                self.text_input.bind(f'<KeyRelease-{key}>', lambda e: "break")
            # Start dongle reader thread
            device = self._find_dongle()
            if device:
                self._dongle_stop.clear()
                self._dongle_thread = threading.Thread(
                    target=self._dongle_reader,
                    args=(device, self._dongle_stop),
                    daemon=True)
                self._dongle_thread.start()
                self.status.config(text=f"VBand active — dongle: {device}", foreground="green")
            else:
                self.status.config(text="VBand active — dongle not found, keyboard only", foreground="orange")
        else:
            self._dongle_stop.set()
            for key in vband_keys:
                self.text_input.unbind(f'<KeyPress-{key}>')
                self.text_input.unbind(f'<KeyRelease-{key}>')
            self.status.config(text="Ready", foreground="blue")

    def check_decoder_timeout(self):
        if self.vband_enabled.get():
            now = time.time()
            self.decoder.set_wpm(self.char_wpm.get())
            char = self.decoder.check_timeout(now)
            if char:
                self.decoded_text.insert(tk.END, char)
                self.decoded_text.see(tk.END)
            
            # Update current live pulse/gap
            if self.user_pulses:
                self.user_pulses[-1][1] = now - self.user_pulses[-1][2]
                if len(self.user_pulses) > 100:
                    self.user_pulses = self.user_pulses[-50:]
            
            self.draw_waterfall()
            
        self.root.after(30, self.check_decoder_timeout)

    def create_widgets(self):
        style = ttk.Style()
        style.configure('TLabel', font=('Arial', 10))
        style.configure('TButton', font=('Arial', 10))
        
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Speed Controls
        speed_frame = ttk.LabelFrame(main_frame, text="Speed Configuration", padding="10")
        speed_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(speed_frame, text="Character Speed (WPM):").grid(row=0, column=0, sticky=tk.W)
        ttk.Scale(speed_frame, from_=5, to=50, variable=self.char_wpm, orient=tk.HORIZONTAL).grid(row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Label(speed_frame, textvariable=self.char_wpm).grid(row=0, column=2)
        
        ttk.Label(speed_frame, text="Effective Speed (WPM):").grid(row=1, column=0, sticky=tk.W)
        ttk.Scale(speed_frame, from_=1, to=50, variable=self.eff_wpm, orient=tk.HORIZONTAL).grid(row=1, column=1, sticky=tk.EW, padx=5)
        ttk.Label(speed_frame, textvariable=self.eff_wpm).grid(row=1, column=2)
        
        # Presets
        preset_frame = ttk.Frame(speed_frame)
        preset_frame.grid(row=2, column=0, columnspan=3, pady=(10, 0))
        ttk.Label(preset_frame, text="Presets:").pack(side=tk.LEFT, padx=5)
        for wpm in [5, 12, 18, 20, 25]:
            ttk.Button(preset_frame, text=f"{wpm} WPM", width=8, 
                       command=lambda w=wpm: [self.char_wpm.set(w), self.eff_wpm.set(w)]).pack(side=tk.LEFT, padx=2)
        
        speed_frame.columnconfigure(1, weight=1)
        
        # Audio Config
        audio_frame = ttk.LabelFrame(main_frame, text="Audio & VBand Config", padding="10")
        audio_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(audio_frame, text="Frequency (Hz):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(audio_frame, textvariable=self.freq, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Checkbutton(audio_frame, text="Include Voice Answer Key", variable=self.include_voice).grid(row=0, column=2, sticky=tk.W, padx=20)
        ttk.Checkbutton(audio_frame, text="Enable VBand Adapter", variable=self.vband_enabled).grid(row=1, column=2, sticky=tk.W, padx=20)
        
        ttk.Label(audio_frame, text="QRN (Static) Level:").grid(row=2, column=0, sticky=tk.W)
        ttk.Scale(audio_frame, from_=0.0, to=0.5, variable=self.qrn_level, orient=tk.HORIZONTAL).grid(row=2, column=1, sticky=tk.EW, padx=5)
        ttk.Label(audio_frame, textvariable=self.qrn_level).grid(row=2, column=2, sticky=tk.W)
        
        audio_frame.columnconfigure(1, weight=1)
        
        # Decoded Input
        decoded_frame = ttk.LabelFrame(main_frame, text="Decoded VBand Input", padding="10")
        decoded_frame.pack(fill=tk.X, pady=5)
        self.decoded_text = tk.Text(decoded_frame, height=2, font=('Arial', 12), bg="#e8f4f8")
        self.decoded_text.pack(fill=tk.X)
        ttk.Button(decoded_frame, text="Clear", command=lambda: self.decoded_text.delete(1.0, tk.END)).pack(side=tk.RIGHT)
        
        # Text Input
        text_frame = ttk.LabelFrame(main_frame, text="Input Text (to Generate)", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.text_input = scrolledtext.ScrolledText(text_frame, height=6, font=('Courier New', 11))
        self.text_input.pack(fill=tk.BOTH, expand=True)
        self.text_input.bind('<KeyRelease>', self.update_visual)
        
        # Random Generator
        rand_frame = ttk.Frame(text_frame)
        rand_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(rand_frame, text="Random:").pack(side=tk.LEFT)
        ttk.Entry(rand_frame, textvariable=self.random_count, width=4).pack(side=tk.LEFT, padx=5)
        
        self.mode_menu = ttk.OptionMenu(rand_frame, self.random_mode, "mixed", "letters", "numbers", "punctuation", "koch", "mixed")
        self.mode_menu.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(rand_frame, text="Koch Lvl:").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Spinbox(rand_frame, from_=2, to=40, textvariable=self.koch_level, width=3).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(rand_frame, text="Generate Practice", command=self.generate_random).pack(side=tk.LEFT, padx=5)
        
        # Visual Morse Display
        vis_frame = ttk.LabelFrame(main_frame, text="Waterfall Display", padding="10")
        vis_frame.pack(fill=tk.X, pady=5)
        self.canvas = tk.Canvas(vis_frame, height=50, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.X)
        
        # Output File
        out_frame = ttk.Frame(main_frame)
        out_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(out_frame, text="Output:").pack(side=tk.LEFT)
        ttk.Entry(out_frame, textvariable=self.output_file).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(out_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT)
        
        # Action Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="Play Preview", command=self.play_preview).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(btn_frame, text="Generate MP3", command=self.execute).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(btn_frame, text="Check Dependencies", command=self.check_deps).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Status
        self.status = ttk.Label(main_frame, text="Ready", foreground="blue")
        self.status.pack(pady=5)

    def sanitize_for_filename(self, text):
        snippet = text[:20].strip()
        sanitized = "".join(c if c.isalnum() else "_" for c in snippet)
        return sanitized if sanitized else "practice"

    def update_default_filename(self):
        current_path = self.output_file.get()
        home_dir = os.path.expanduser("~")
        if os.path.dirname(current_path) == home_dir:
            text = self.text_input.get(1.0, tk.END).strip()
            if text:
                name = self.sanitize_for_filename(text)
                self.output_file.set(os.path.join(home_dir, f"morse_{name}.mp3"))

    def _cleanup_temp_files(self):
        for f in self._pending_temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        self._pending_temp_files = []

    def update_visual(self, event=None):
        text = self.text_input.get(1.0, tk.END).strip()
        tu, ts, char_gap, word_gap = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
        self.pulses = morse_logic.get_morse_pulses(text, tu, ts, char_gap, word_gap)
        self.scroll_offset = 0
        self.draw_waterfall()
        self.update_default_filename()

    def draw_waterfall(self):
        self.canvas.delete("all")
        playhead_x = 50
        y_mid = 25
        scale = 10 
        tu, _, _, _ = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())

        # 1. Generated Pulses
        if self.pulses:
            x = playhead_x - self.scroll_offset
            for is_signal, duration, label in self.pulses:
                width = duration * scale
                if x + width > 0 and x < self.canvas.winfo_width():
                    if is_signal:
                        self.canvas.create_rectangle(x, y_mid-12, x+width, y_mid-2, fill="#00FF00", outline="")
                    if label:
                        display_label = label.strip('<>') if label.startswith('<') else label
                        self.canvas.create_text(x, y_mid-22, text=display_label, fill="white", font=("Arial", 8, "bold"), anchor="sw")
                x += width

        # 2. User Pulses
        if self.vband_enabled.get() and self.user_pulses:
            now = time.time()
            for is_signal, duration, start_time in reversed(self.user_pulses):
                units_ago = (now - start_time) / tu
                x_start = playhead_x - (units_ago * scale)
                width = (duration / tu) * scale
                if x_start + width < 0: break
                if is_signal:
                    self.canvas.create_rectangle(x_start, y_mid+2, x_start+width, y_mid+12, fill="#FFA500", outline="")
            
        self.canvas.create_line(playhead_x, 0, playhead_x, 50, fill="red", width=2)

    def start_scroll(self):
        self.scrolling = True
        self.scroll_offset = 0
        self.animate_scroll()

    def animate_scroll(self):
        if not self.scrolling: return
        tu, _, _, _ = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
        self.scroll_offset += 1
        self.draw_waterfall()
        total_width = sum(d for _, d, _ in self.pulses) * 10
        if self.scroll_offset > total_width + 50:
            self.scrolling = False
            self.scroll_offset = 0
            self.draw_waterfall()
        else:
            ms = int((tu / 10) * 1000)
            self.root.after(max(5, ms), self.animate_scroll)

    def generate_random(self):
        text = morse_logic.generate_random_text(self.random_count.get(), self.random_mode.get(), self.koch_level.get())
        self.text_input.delete(1.0, tk.END)
        self.text_input.insert(tk.END, text)
        self.update_visual()

    def browse_file(self):
        filename = filedialog.asksaveasfilename(defaultextension=".mp3", filetypes=[("MP3 files", "*.mp3")])
        if filename: self.output_file.set(filename)

    def check_deps(self):
        lame = morse_logic.get_lame_path()
        espeak = os.path.exists("/usr/bin/espeak")
        dongle = self._find_dongle()
        msg = f"Lame encoder: {'Found' if lame else 'NOT Found'}\n"
        msg += f"espeak (Voice): {'Installed' if espeak else 'NOT Installed'}\n"
        msg += f"VBand dongle (413d:2107): {'Found at ' + dongle if dongle else 'NOT Found'}"
        messagebox.showinfo("Dependencies", msg)

    def play_preview(self):
        text_raw = self.text_input.get(1.0, tk.END).strip()
        if not text_raw: return
        text, _ = morse_logic.sanitize_text(text_raw)
        self._cleanup_temp_files()
        try:
            tu, _, char_g, word_g = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
            morse_wav = morse_logic.generate_morse_wav(text, tu, char_g, word_g, self.freq.get(), self.qrn_level.get())
            self._pending_temp_files.append(morse_wav)
            wav_to_play = morse_wav
            if self.include_voice.get():
                voice_wav = morse_logic.generate_voice_wav(text)
                if voice_wav:
                    self._pending_temp_files.append(voice_wav)
                    wav_to_play = morse_logic.combine_wavs([morse_wav, voice_wav], "combined.wav")
                    self._pending_temp_files.append(wav_to_play)
            self.start_scroll()
            morse_logic.play_wav(wav_to_play)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def execute(self):
        text_raw = self.text_input.get(1.0, tk.END).strip()
        if not text_raw: return
        text, ignored = morse_logic.sanitize_text(text_raw)
        if ignored and not messagebox.askyesno("Sanitation Warning", f"Skip {len(ignored)} invalid characters?"): return
        self._cleanup_temp_files()
        try:
            tu, _, char_g, word_g = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
            morse_wav = morse_logic.generate_morse_wav(text, tu, char_g, word_g, self.freq.get(), self.qrn_level.get())
            self._pending_temp_files.append(morse_wav)
            final_wav = morse_wav
            if self.include_voice.get():
                voice_wav = morse_logic.generate_voice_wav(text)
                if voice_wav:
                    self._pending_temp_files.append(voice_wav)
                    final_wav = morse_logic.combine_wavs([morse_wav, voice_wav], "final.wav")
                    self._pending_temp_files.append(final_wav)
            success, msg = morse_logic.convert_wav_to_mp3(final_wav, self.output_file.get())
            if success: messagebox.showinfo("Success", f"Saved to {self.output_file.get()}")
            else: messagebox.showerror("Error", msg)
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = MorseApp(root)
    root.mainloop()
