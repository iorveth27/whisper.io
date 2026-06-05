#!/usr/bin/env python3
"""
Whisper Dictate — Local voice-to-text for macOS.

Hold a hotkey, speak, release — text appears at your cursor.
Supports two backends:
  - MLX Whisper (Apple Silicon, fastest)
  - faster-whisper (NVIDIA CUDA or CPU fallback)
"""

import argparse
import atexit
import select
import subprocess
import sys
import termios
import threading
import time
import tty
from pathlib import Path

import Quartz

import numpy as np
import pyaudio
import pyperclip
import yaml
from pynput import keyboard

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "model": "mlx-community/whisper-small-mlx",
    "language": "en",
    "hotkey": "fn",
    "sound_on_start": True,
    "sound_on_stop": True,
    "auto_paste": True,
    "trailing_space": True,
    "backend": "mlx",
    "show_overlay": True,
}

# macOS fn/Globe key virtual keycode (not exposed as a pynput Key constant)
VK_FN = 63

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16

KEY_MAP = {
    "fn": keyboard.KeyCode.from_vk(VK_FN),
    "globe": keyboard.KeyCode.from_vk(VK_FN),
    "esc": keyboard.Key.esc,
    "escape": keyboard.Key.esc,
    "space": keyboard.Key.space,
    "enter": keyboard.Key.enter,
    "tab": keyboard.Key.tab,
    "ctrl": keyboard.Key.ctrl_l,
    "ctrl_l": keyboard.Key.ctrl_l,
    "ctrl_r": keyboard.Key.ctrl_r,
    "shift": keyboard.Key.shift_l,
    "shift_l": keyboard.Key.shift_l,
    "shift_r": keyboard.Key.shift_r,
    "alt": keyboard.Key.alt_l,
    "alt_l": keyboard.Key.alt_l,
    "alt_r": keyboard.Key.alt_r,
    "option": keyboard.Key.alt_l,
    "option_l": keyboard.Key.alt_l,
    "option_r": keyboard.Key.alt_r,
    "cmd": keyboard.Key.cmd_l,
    "cmd_l": keyboard.Key.cmd_l,
    "cmd_r": keyboard.Key.cmd_r,
    "f1": keyboard.Key.f1, "f2": keyboard.Key.f2, "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4, "f5": keyboard.Key.f5, "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7, "f8": keyboard.Key.f8, "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10, "f11": keyboard.Key.f11, "f12": keyboard.Key.f12,
    "caps_lock": keyboard.Key.caps_lock,
    "caps": keyboard.Key.caps_lock,
}


def _match_fn_key(key) -> bool:
    """Check if a key event is the fn/Globe key (vk=63)."""
    vk = getattr(key, "vk", None)
    return vk == VK_FN


def parse_hotkey(key_str: str):
    """Parse a key name into a pynput Key or KeyCode."""
    key_str = key_str.strip().lower()
    if key_str.startswith("key."):
        key_str = key_str[4:]
    if key_str in KEY_MAP:
        return KEY_MAP[key_str]
    elif len(key_str) == 1:
        return keyboard.KeyCode.from_char(key_str)
    else:
        print(f"  Warning: Unknown key '{key_str}', defaulting to fn")
        return KEY_MAP["fn"]


def load_config(config_path: str = "config.yaml") -> dict:
    config = DEFAULT_CONFIG.copy()
    path = Path(config_path)
    config_dir = path.parent.resolve()
    if path.exists():
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
        config.update(user_config)
    # Resolve relative model paths against the config file's directory
    model = config.get("model", "")
    if model and not Path(model).is_absolute():
        candidate = config_dir / model
        if candidate.exists():
            config["model"] = str(candidate)
    # Normalize "auto" to None for language
    if config.get("language") in ("auto", "Auto"):
        config["language"] = None
    return config


# ---------------------------------------------------------------------------
# Audio Recording
# ---------------------------------------------------------------------------

class AudioRecorder:
    def __init__(self, device_index: int | None = None):
        self.device_index = device_index
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.frames: list[bytes] = []
        self.is_recording = False
        self._lock = threading.Lock()

    def start(self):
        """Start recording audio using direct read (like claude-whisper)."""
        with self._lock:
            if self.is_recording:
                return
            self.frames = []
            self.is_recording = True

        # Record in a background thread using stream.read() directly
        # This approach works even when get_default_input_device_info() fails
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()

    def _record_loop(self):
        """Background thread that reads audio chunks."""
        try:
            stream_kwargs = {
                "format": FORMAT,
                "channels": CHANNELS,
                "rate": SAMPLE_RATE,
                "input": True,
                "frames_per_buffer": CHUNK_SIZE,
            }
            if self.device_index is not None:
                stream_kwargs["input_device_index"] = self.device_index

            stream = self.pa.open(**stream_kwargs)
            self.stream = stream

            while self.is_recording:
                try:
                    data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception:
                    break

            stream.stop_stream()
            stream.close()
            self.stream = None
        except OSError as e:
            print(f"  Audio error: {e}")
            self.is_recording = False

    def stop(self) -> np.ndarray | None:
        with self._lock:
            if not self.is_recording:
                return None
            self.is_recording = False

        # Wait for record thread to finish
        if hasattr(self, '_record_thread') and self._record_thread.is_alive():
            self._record_thread.join(timeout=2)

        if not self.frames:
            return None

        audio_data = b"".join(self.frames)
        return np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

    def list_devices(self):
        print("\nAvailable audio input devices:\n")
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                marker = " (DEFAULT)" if i == self.pa.get_default_input_device_info()["index"] else ""
                print(f"  [{i}] {info['name']}{marker}")
        print()

    def cleanup(self):
        self.pa.terminate()


# ---------------------------------------------------------------------------
# Transcription — MLX Backend
# ---------------------------------------------------------------------------

class MLXTranscriber:
    def __init__(self, model: str, language: str | None = None,
                 task: str = "transcribe", verbose: bool = False):
        self.model = model
        self.language = language
        self.task = task
        self.verbose = verbose

    def warmup(self):
        print(f"Loading model: {self.model}")
        print("(First run downloads the model — this may take a minute...)\n")
        import mlx_whisper
        silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
        mlx_whisper.transcribe(silence, path_or_hf_repo=self.model,
                               language=self.language, task=self.task)
        print("Model loaded and ready!\n")

    def transcribe(self, audio: np.ndarray) -> str:
        import mlx_whisper
        t0 = time.time()
        result = mlx_whisper.transcribe(audio, path_or_hf_repo=self.model,
                                        language=self.language, task=self.task)
        elapsed = time.time() - t0
        text = result.get("text", "").strip()
        if self.verbose and text:
            duration = len(audio) / SAMPLE_RATE
            print(f"  Transcribed {duration:.1f}s audio in {elapsed:.2f}s: \"{text}\"")
        return text


# ---------------------------------------------------------------------------
# Transcription — faster-whisper Backend
# ---------------------------------------------------------------------------

class FasterWhisperTranscriber:
    def __init__(self, model: str, language: str | None = None,
                 task: str = "transcribe", verbose: bool = False):
        self.model_path = model
        self.language = language
        self.task = task
        self.verbose = verbose
        self.model = None

    def warmup(self):
        print(f"Loading model: {self.model_path}")
        print("(First run may download the model — this may take a minute...)\n")
        from faster_whisper import WhisperModel
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        print(f"  Device: {device}, Compute: {compute_type}")
        self.model = WhisperModel(self.model_path, device=device, compute_type=compute_type)
        print("Model loaded and ready!\n")

    def transcribe(self, audio: np.ndarray) -> str:
        t0 = time.time()
        segments, info = self.model.transcribe(audio, language=self.language,
                                               task=self.task, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        elapsed = time.time() - t0
        if self.verbose and text:
            duration = len(audio) / SAMPLE_RATE
            print(f"  Transcribed {duration:.1f}s audio in {elapsed:.2f}s: \"{text}\"")
        return text


# ---------------------------------------------------------------------------
# Text Injection
# ---------------------------------------------------------------------------

def inject_text(text: str, auto_paste: bool = True):
    pyperclip.copy(text)
    if auto_paste:
        time.sleep(0.05)
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'],
            capture_output=True,
        )


# ---------------------------------------------------------------------------
# Sound Feedback
# ---------------------------------------------------------------------------

def play_sound(sound_file: str):
    path = Path(__file__).parent / "sounds" / sound_file
    if path.exists():
        subprocess.Popen(["afplay", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
# Overlay
# ---------------------------------------------------------------------------

def show_overlay():
    try:
        overlay_script = Path(__file__).parent / "overlay.py"
        return subprocess.Popen(
            [sys.executable, str(overlay_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None


def hide_overlay(proc):
    if proc:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class DictateApp:
    def __init__(self, config: dict, device: int | None = None, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.recorder = AudioRecorder(device_index=device)
        self.backend = config.get("backend", "mlx")

        task = config.get("task", "transcribe")

        if self.backend == "faster-whisper":
            self.transcriber = FasterWhisperTranscriber(
                model=config["model"], language=config.get("language"),
                task=task, verbose=verbose)
        else:
            self.transcriber = MLXTranscriber(
                model=config["model"], language=config.get("language"),
                task=task, verbose=verbose)

        self.hotkey = parse_hotkey(config["hotkey"])
        # fn key needs vk-based matching since pynput doesn't always use ==
        self._use_fn_matching = config.get("hotkey", "").strip().lower() in ("fn", "globe")
        self._recording = False
        self._processing = False
        self._overlay_proc = None
        self._lock = threading.Lock()

        atexit.register(self._cleanup_overlay)

    def _cleanup_overlay(self):
        hide_overlay(self._overlay_proc)
        self._overlay_proc = None

    def _start_recording(self):
        with self._lock:
            if self._recording or self._processing:
                return
            self._recording = True
        if self.config.get("sound_on_start"):
            play_sound("start.wav")
        if self.config.get("show_overlay", True):
            self._overlay_proc = show_overlay()
        try:
            self.recorder.start()
        except OSError as e:
            print(f"  Microphone error: {e}")
            hide_overlay(self._overlay_proc)
            self._overlay_proc = None
            self._recording = False
            return
        print("  Recording... (speak now)")

    def _stop_recording(self):
        with self._lock:
            if not self._recording:
                return
            self._recording = False
            self._processing = True

        hide_overlay(self._overlay_proc)
        self._overlay_proc = None

        if self.config.get("sound_on_stop"):
            play_sound("stop.wav")

        print("  Processing...")
        audio = self.recorder.stop()

        if audio is not None and len(audio) > SAMPLE_RATE * 0.3:
            text = self.transcriber.transcribe(audio)
            if text:
                if self.config.get("trailing_space", True):
                    text += " "
                inject_text(text, auto_paste=self.config.get("auto_paste", True))
                print(f"  >> {text.strip()}")
                print("  (copied to clipboard)")
            else:
                print("  (no speech detected)")
        elif audio is not None:
            print("  (too short, skipped)")
        else:
            print("  (no audio captured)")

        self._processing = False

    def _print_banner(self, mode: str, hotkey_label: str):
        print("=" * 56)
        print("  Whisper Dictate — Local Voice-to-Text")
        print("=" * 56)
        print()
        backend_label = "faster-whisper (CUDA/CPU)" if self.backend == "faster-whisper" else "MLX (Apple Silicon)"
        model_label = self.config["model"].split("/")[-1]
        print(f"  Backend:  {backend_label}")
        print(f"  Model:    {model_label}")
        lang = self.config.get("language")
        lang_label = f"{LANGUAGES.get(lang, lang)} ({lang})" if lang else "auto-detect"
        task = self.config.get("task", "transcribe")
        target = self.config.get("target_language")
        if task == "translate":
            target_label = f"{LANGUAGES.get(target, target)} ({target})" if target else "English"
            print(f"  Speak:    {lang_label}")
            print(f"  Output:   {target_label} (translate)")
        else:
            print(f"  Language: {lang_label}")
        print(f"  Mode:     {mode}")
        print(f"  Hotkey:   {hotkey_label}")
        print(f"  Paste:    {'auto' if self.config.get('auto_paste') else 'clipboard only'}")
        print()

    # --- Global hotkey mode (pynput or Quartz) ---

    def run_global(self):
        """Run with global hotkey. Uses Quartz event tap for fn key (true
        hold-to-talk), pynput for all other keys."""
        hotkey_name = self.config["hotkey"]
        self._print_banner("global hotkey", hotkey_name)
        self.transcriber.warmup()

        print("-" * 56)
        print(f"  Ready! Hold [{hotkey_name}] and speak (works in any app).")
        print("  Press Ctrl+C to quit.")
        print("-" * 56)
        print()

        if self._use_fn_matching:
            self._run_global_fn()
        else:
            self._run_global_pynput()

    def _run_global_pynput(self):
        """Global hotkey via pynput (for non-fn keys)."""
        listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        listener.start()

        try:
            listener.join()
        except KeyboardInterrupt:
            pass

        listener.stop()
        self._cleanup_overlay()
        self.recorder.cleanup()
        print("\nGoodbye!")

    def _run_global_fn(self):
        """Global fn key via Quartz event tap — detects true press/release
        by monitoring the NSEventModifierFlagFunction flag bit."""
        # fn modifier flag: bit 23 (0x800000) = NX_SECONDARYFNMASK
        FN_FLAG = 0x800000
        self._fn_held = False

        def callback(proxy, event_type, event, refcon):
            flags = Quartz.CGEventGetFlags(event)
            fn_down = bool(flags & FN_FLAG)

            if fn_down and not self._fn_held:
                self._fn_held = True
                threading.Thread(target=self._start_recording, daemon=True).start()
            elif not fn_down and self._fn_held:
                self._fn_held = False
                threading.Thread(target=self._stop_recording, daemon=True).start()

            return event

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged),
            callback,
            None,
        )

        if tap is None:
            print("  ERROR: Could not create event tap.")
            print("  Grant Accessibility permission to your terminal in:")
            print("  System Settings > Privacy & Security > Accessibility")
            sys.exit(1)

        source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopDefaultMode)
        Quartz.CGEventTapEnable(tap, True)

        try:
            Quartz.CFRunLoopRun()
        except KeyboardInterrupt:
            pass

        self._cleanup_overlay()
        self.recorder.cleanup()
        print("\nGoodbye!")

    def _key_matches(self, key) -> bool:
        """Check if key matches configured hotkey."""
        if self._use_fn_matching:
            return _match_fn_key(key)
        return key == self.hotkey

    def _on_press(self, key):
        try:
            if self.verbose:
                vk = getattr(key, "vk", None)
                print(f"  [key press: {key!r}  vk={vk}]")
            if self._key_matches(key):
                self._start_recording()
        except Exception as e:
            print(f"  Error on key press: {e}")

    def _on_release(self, key):
        try:
            if self._key_matches(key) and self._recording:
                self._stop_recording()
        except Exception as e:
            print(f"  Error on key release: {e}")

    # --- Terminal mode (raw stdin, no permissions needed) ---

    def run_terminal(self):
        """Run with terminal key detection (no special permissions needed).
        Hold SPACE to record, release to process. Key release is detected
        by the absence of key-repeat characters within a short timeout.
        """
        self._print_banner("terminal (hold SPACE to record)", "SPACE")
        self.transcriber.warmup()

        print("-" * 56)
        print("  Ready! Hold [SPACE] and speak, release to transcribe.")
        print("  Press 'q' or Ctrl+Q to quit.")
        print("-" * 56)
        print()

        # macOS initial key-repeat delay is typically 300-500ms depending on
        # system settings.  We need to wait longer than that so we don't
        # mistake the pre-repeat gap for a key release.
        KEY_RELEASE_TIMEOUT = 0.6
        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)

        def drain_stdin():
            """Drain any buffered characters from stdin so they don't
            trigger a new recording cycle after we finish processing."""
            while select.select([sys.stdin], [], [], 0.05)[0]:
                sys.stdin.buffer.read(1)

        try:
            tty.setraw(fd)

            while True:
                # Wait for any key (longer timeout when idle)
                ready = select.select([sys.stdin], [], [], 0.1)[0]
                if not ready:
                    continue

                ch = sys.stdin.buffer.read(1)
                if ch in (b'q', b'\x03', b'\x11'):  # q, Ctrl+C, Ctrl+Q
                    break

                if ch == b' ' and not self._recording and not self._processing:
                    # Key pressed — start recording
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
                    self._start_recording()
                    tty.setraw(fd)

                    # Hold loop: keep recording while SPACE repeats
                    while True:
                        ready = select.select([sys.stdin], [], [], KEY_RELEASE_TIMEOUT)[0]
                        if ready:
                            repeat_ch = sys.stdin.buffer.read(1)
                            if repeat_ch == b' ':
                                continue  # Still held
                            # Different key pressed while holding — treat as release
                            break
                        else:
                            # Timeout — key was released
                            break

                    # Key released — stop and transcribe
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
                    self._stop_recording()

                    # Drain any leftover key-repeat chars that arrived during
                    # transcription so they don't start a new recording.
                    tty.setraw(fd)
                    drain_stdin()

        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

        if self._recording:
            self._stop_recording()
        self._cleanup_overlay()
        self.recorder.cleanup()
        print("\nGoodbye!")

    # --- Debug keys mode ---

    def run_debug_keys(self):
        """Print every key event pynput sees — for diagnosing permission issues."""
        print("=" * 56)
        print("  Key Debug Mode (pynput)")
        print("=" * 56)
        print()
        print("  If you press keys and nothing appears below,")
        print("  pynput cannot see your keyboard.")
        print()
        print("  Fix: System Settings > Privacy & Security > Input Monitoring")
        print("  Add your terminal app (Terminal, iTerm2, etc.)")
        print()
        print("  Press keys now... (Ctrl+C to quit)")
        print()

        def on_press(key):
            vk = getattr(key, 'vk', None)
            print(f"  PRESS:   {key!r}  (type={type(key).__name__}, vk={vk})")

        def on_release(key):
            vk = getattr(key, 'vk', None)
            print(f"  RELEASE: {key!r}  (type={type(key).__name__}, vk={vk})")

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

        try:
            listener.join()
        except KeyboardInterrupt:
            pass

        listener.stop()
        print("\nDone.")


# ---------------------------------------------------------------------------
# Language Selection
# ---------------------------------------------------------------------------

LANGUAGES = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "pl": "Polish",
    "tr": "Turkish",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "uk": "Ukrainian",
}


def _print_language_menu(default: str | None = "en"):
    """Print the language menu and return (codes, default_idx)."""
    codes = list(LANGUAGES.keys())
    print("  [0]  Auto-detect (any language)")
    for i, code in enumerate(codes, 1):
        marker = " *" if code == default else ""
        print(f"  [{i:>2}] {LANGUAGES[code]} ({code}){marker}")
    print()

    if default is None or default == "auto":
        default_idx = 0
    elif default in codes:
        default_idx = codes.index(default) + 1
    else:
        default_idx = 0

    return codes, default_idx


def _pick_language(prompt: str, codes: list[str], default_idx: int) -> str | None:
    """Ask user to pick a language. Returns code or None for auto-detect."""
    try:
        choice = input(f"  {prompt} [{default_idx}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    if choice == "":
        idx = default_idx
    else:
        try:
            idx = int(choice)
        except ValueError:
            low = choice.lower()
            if low in LANGUAGES:
                return low
            if low == "auto":
                return None
            print(f"  Unknown choice, using default.")
            idx = default_idx

    if idx == 0:
        return None
    elif 1 <= idx <= len(codes):
        return codes[idx - 1]
    else:
        print(f"  Invalid choice, using default.")
        return None if default_idx == 0 else codes[default_idx - 1]


def prompt_language(default: str | None = "en") -> dict:
    """Interactive language selector. Returns dict with language, target_language, task."""
    print("=" * 56)
    print("  Language Setup")
    print("=" * 56)
    print()
    print("  What language will you speak?")
    print()

    codes, default_idx = _print_language_menu(default)
    source = _pick_language("Speak", codes, default_idx)

    source_label = f"{LANGUAGES[source]} ({source})" if source else "auto-detect"
    print(f"  -> {source_label}")
    print()

    # Ask for output language
    print("  What language should the text be in?")
    print()
    print("  [0]  Same as spoken language")
    print("  [1]  English (translate to English)")
    print()

    try:
        choice = input("  Output [0]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)

    if choice == "" or choice == "0":
        # Same language — transcribe
        print("  -> Same as spoken")
        print()
        return {"language": source, "target_language": None, "task": "transcribe"}
    elif choice == "1":
        # Translate to English
        if source == "en":
            print("  -> Already English, transcribing")
            print()
            return {"language": "en", "target_language": None, "task": "transcribe"}
        print("  -> Translate to English")
        print()
        return {"language": source, "target_language": "en", "task": "translate"}
    else:
        print("  -> Same as spoken (default)")
        print()
        return {"language": source, "target_language": None, "task": "transcribe"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Whisper Dictate — Local voice-to-text for macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dictate.py                                    # Terminal mode (hold SPACE)
  python dictate.py --global                           # Global mode, hold fn in any app
  python dictate.py --global --hotkey esc              # Global with ESC key
  python dictate.py --model models/whisper-large-v3-turbo-mlx
  python dictate.py --language en --verbose
  python dictate.py --list-devices
  python dictate.py --debug-keys                       # Check if pynput can see keys
  python dictate.py --test                             # Self-test mode
        """,
    )
    parser.add_argument("--backend", choices=["mlx", "faster-whisper"],
                        help="Transcription backend")
    parser.add_argument("--model", help="Model path or HuggingFace repo")
    parser.add_argument("--language", help="Language code (e.g., 'en')")
    parser.add_argument("--hotkey", help="Hotkey (e.g., fn, esc, ctrl_r, alt_r)")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--device", type=int, help="Audio input device index")
    parser.add_argument("--list-devices", action="store_true", help="List audio input devices")
    parser.add_argument("--no-auto-paste", action="store_true", help="Clipboard only, no auto-paste")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show timing and key events")
    parser.add_argument("--global", dest="global_mode", action="store_true",
                        help="Global hotkey mode via pynput (needs Input Monitoring permission)")
    parser.add_argument("--debug-keys", action="store_true",
                        help="Debug: show all key events pynput detects")
    parser.add_argument("--test", action="store_true",
                        help="Self-test: overlay, record 3s, transcribe, exit")

    args = parser.parse_args()

    if args.list_devices:
        recorder = AudioRecorder()
        recorder.list_devices()
        recorder.cleanup()
        sys.exit(0)

    config = load_config(args.config)
    if args.backend:
        config["backend"] = args.backend
    if args.model:
        config["model"] = args.model
    if args.language:
        config["language"] = None if args.language.lower() == "auto" else args.language
    if args.hotkey:
        config["hotkey"] = args.hotkey
    if args.no_auto_paste:
        config["auto_paste"] = False

    if args.debug_keys:
        app = DictateApp(config, device=args.device, verbose=True)
        app.run_debug_keys()
        return

    # Interactive language selection (skip if --language was passed)
    if not args.language and not args.test:
        lang_settings = prompt_language(config.get("language", "en"))
        config["language"] = lang_settings["language"]
        config["target_language"] = lang_settings["target_language"]
        config["task"] = lang_settings["task"]

    device = args.device if args.device is not None else config.get("device")
    app = DictateApp(config, device=device, verbose=args.verbose)

    if args.test:
        run_self_test(app)
    elif args.global_mode:
        app.run_global()
    else:
        # Default: terminal mode
        app.run_terminal()


def run_self_test(app: DictateApp):
    print("=" * 56)
    print("  SELF-TEST MODE")
    print("=" * 56)
    print()

    print("[1/4] Loading model...")
    app.transcriber.warmup()

    print("[2/4] Showing overlay for 3 seconds...")
    overlay = show_overlay()
    time.sleep(3)
    print("  Overlay visible? (check top-center of screen)")
    hide_overlay(overlay)
    print("  Overlay hidden.")

    print("[3/4] Recording 3 seconds of audio...")
    try:
        app.recorder.start()
        time.sleep(3)
        audio = app.recorder.stop()
    except OSError as e:
        print(f"  Microphone error: {e}")
        print("  Using 3s of silence for transcription test.")
        audio = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)

    if audio is None or len(audio) < SAMPLE_RATE * 0.3:
        print("  No audio captured — check your microphone.")
        app.recorder.cleanup()
        return

    duration = len(audio) / SAMPLE_RATE
    print(f"  Captured {duration:.1f}s of audio.")

    print("[4/4] Transcribing...")
    text = app.transcriber.transcribe(audio)
    if text:
        print(f"  Result: \"{text}\"")
    else:
        print("  (no speech detected)")

    print()
    print("Self-test complete!")
    app.recorder.cleanup()


if __name__ == "__main__":
    main()
