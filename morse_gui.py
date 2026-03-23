try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, scrolledtext
except ImportError:
    print("Error: The 'tkinter' module is missing.")
    print("Please install it by running: sudo apt-get install python3-tk")
    import sys
    sys.exit(1)

import os
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
            
        self.root.geometry("700x750")
        
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
        
        self.create_widgets()
        
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
        
        speed_frame.columnconfigure(1, weight=1)
        
        # Audio Config
        audio_frame = ttk.LabelFrame(main_frame, text="Audio & Trainer Config", padding="10")
        audio_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(audio_frame, text="Frequency (Hz):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(audio_frame, textvariable=self.freq, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Checkbutton(audio_frame, text="Include Voice Answer Key (requires espeak)", variable=self.include_voice).grid(row=0, column=2, sticky=tk.W, padx=20)
        
        # Text Input
        text_frame = ttk.LabelFrame(main_frame, text="Input Text", padding="10")
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
        
        self.koch_label = ttk.Label(rand_frame, text="Koch Lvl:")
        self.koch_label.pack(side=tk.LEFT, padx=(10, 0))
        self.koch_spin = ttk.Spinbox(rand_frame, from_=2, to=40, textvariable=self.koch_level, width=3)
        self.koch_spin.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(rand_frame, text="Generate Practice", command=self.generate_random).pack(side=tk.LEFT, padx=5)
        
        # Visual Morse Display
        vis_frame = ttk.LabelFrame(main_frame, text="Waterfall Display (Scrolling Morse)", padding="10")
        vis_frame.pack(fill=tk.X, pady=5)
        self.canvas = tk.Canvas(vis_frame, height=50, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.X)
        self.pulses = []
        self.scroll_offset = 0
        self.scrolling = False
        
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
        # Take first 20 chars, replace non-alphanumeric with underscore
        snippet = text[:20].strip()
        sanitized = "".join(c if c.isalnum() else "_" for c in snippet)
        return sanitized if sanitized else "practice"

    def update_default_filename(self):
        # Only update if the user hasn't manually browsed for a file in a different directory
        current_path = self.output_file.get()
        home_dir = os.path.expanduser("~")
        
        # If the path is in the home directory, we allow auto-updating the filename
        if os.path.dirname(current_path) == home_dir:
            text = self.text_input.get(1.0, tk.END).strip()
            if text:
                name = self.sanitize_for_filename(text)
                self.output_file.set(os.path.join(home_dir, f"morse_{name}.mp3"))

    def update_visual(self, event=None):
        text = self.text_input.get(1.0, tk.END).strip()
        tu, ts, char_gap, word_gap = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
        self.pulses = morse_logic.get_morse_pulses(text, tu, ts, char_gap, word_gap)
        self.scroll_offset = 0
        self.draw_waterfall()
        self.update_default_filename()

    def draw_waterfall(self):
        self.canvas.delete("all")
        if not self.pulses:
            return
            
        # Playhead position (where the sound "happens")
        playhead_x = 50
        x = playhead_x - self.scroll_offset
        y_mid = 30
        scale = 10 # 1 tu = 10 pixels
        
        # Draw pulses and character labels
        for is_signal, duration, label in self.pulses:
            width = duration * scale
            if x + width > 0 and x < self.canvas.winfo_width():
                if is_signal:
                    self.canvas.create_rectangle(x, y_mid-5, x+width, y_mid+10, fill="#00FF00", outline="")
                
                # Draw the label if this pulse marks the start of a character
                if label:
                    # Filter out prosigns tags like <BT> for display, or show them simply
                    display_label = label.strip('<>') if label.startswith('<') else label
                    self.canvas.create_text(x, y_mid-15, text=display_label, fill="white", font=("Arial", 9, "bold"), anchor="sw")
            x += width
            
        # Draw Playhead (static red line)
        self.canvas.create_line(playhead_x, 0, playhead_x, 50, fill="red", width=2)

    def start_scroll(self):
        self.scrolling = True
        self.scroll_offset = 0 # Start exactly at the first pulse
        self.animate_scroll()

    def animate_scroll(self):
        if not self.scrolling:
            return
            
        tu, _, _, _ = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
        
        # Move 1 pixel at a time for maximum smoothness
        self.scroll_offset += 1
        self.draw_waterfall()
        
        # Calculate total width to know when to stop
        total_width = sum(d for _, d in self.pulses) * 10
        if self.scroll_offset > total_width + 50:
            self.scrolling = False
            self.scroll_offset = 0
            self.draw_waterfall()
        else:
            # Time to move 1 pixel = (tu / scale)
            ms = int((tu / 10) * 1000)
            self.root.after(max(5, ms), self.animate_scroll)

    def generate_random(self):
        text = morse_logic.generate_random_text(self.random_count.get(), self.random_mode.get(), self.koch_level.get())
        self.text_input.delete(1.0, tk.END)
        self.text_input.insert(tk.END, text)
        self.update_visual()
        self.status.config(text=f"Generated {self.random_count.get()} random groups.", foreground="green")

    def browse_file(self):
        filename = filedialog.asksaveasfilename(defaultextension=".mp3", filetypes=[("MP3 files", "*.mp3")])
        if filename:
            self.output_file.set(filename)

    def check_deps(self):
        lame = morse_logic.get_lame_path()
        espeak = os.path.exists("/usr/bin/espeak")
        msg = f"Lame encoder: {'Found' if lame else 'NOT Found'}\n"
        msg += f"espeak (Voice): {'Installed' if espeak else 'NOT Installed'}"
        messagebox.showinfo("Dependencies", msg)

    def play_preview(self):
        text_raw = self.text_input.get(1.0, tk.END).strip()
        if not text_raw:
            messagebox.showwarning("Warning", "Please enter some text.")
            return
            
        text, ignored = morse_logic.sanitize_text(text_raw)
        if ignored:
            self.status.config(text=f"Sanitized: removed {len(ignored)} invalid chars", foreground="orange")
            
        self.status.config(text="Generating preview...", foreground="blue")
        self.root.update_idletasks()
        
        try:
            tu, _, char_g, word_g = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
            morse_wav = morse_logic.generate_morse_wav(text, tu, char_g, word_g, self.freq.get())
            
            wav_to_play = morse_wav
            voice_wav = None
            
            if self.include_voice.get():
                voice_wav = morse_logic.generate_voice_wav(text)
                if voice_wav:
                    combined = morse_logic.combine_wavs([morse_wav, voice_wav], "combined.wav")
                    wav_to_play = combined
            
            self.start_scroll()
            success, msg = morse_logic.play_wav(wav_to_play)
            if success:
                self.status.config(text="Playing Morse...", foreground="green")
            else:
                messagebox.showerror("Error", msg)
                
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def execute(self):
        text_raw = self.text_input.get(1.0, tk.END).strip()
        if not text_raw:
            messagebox.showwarning("Warning", "Please enter some text.")
            return
            
        text, ignored = morse_logic.sanitize_text(text_raw)
        if ignored:
            message = f"Warning: These characters are not supported and will be skipped:\n{', '.join(sorted(ignored))}\n\nContinue?"
            if not messagebox.askyesno("Sanitation Warning", message):
                return
            
        self.status.config(text="Processing...", foreground="blue")
        self.root.update_idletasks()
        
        try:
            tu, _, char_g, word_g = morse_logic.calculate_timings(self.char_wpm.get(), self.eff_wpm.get())
            morse_wav = morse_logic.generate_morse_wav(text, tu, char_g, word_g, self.freq.get())
            
            final_wav = morse_wav
            if self.include_voice.get():
                voice_wav = morse_logic.generate_voice_wav(text)
                if voice_wav:
                    final_wav = morse_logic.combine_wavs([morse_wav, voice_wav], "final.wav")
            
            success, msg = morse_logic.convert_wav_to_mp3(final_wav, self.output_file.get())
            
            # Cleanup temp wavs
            if os.path.exists(morse_wav): os.remove(morse_wav)
            if self.include_voice.get() and voice_wav and os.path.exists(voice_wav): os.remove(voice_wav)
            if final_wav != morse_wav and os.path.exists(final_wav): os.remove(final_wav)
                
            if success:
                self.status.config(text=f"Successfully saved to {os.path.basename(self.output_file.get())}", foreground="green")
                messagebox.showinfo("Success", f"MP3 generated successfully:\n{self.output_file.get()}")
            else:
                self.status.config(text="Conversion failed!", foreground="red")
                messagebox.showerror("Error", msg)
                
        except Exception as e:
            self.status.config(text="Error occurred!", foreground="red")
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = MorseApp(root)
    root.mainloop()
