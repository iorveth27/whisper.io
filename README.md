# Whisper Dictate

Local voice-to-text dictation for macOS. Hold a key, speak, release -- text appears at your cursor. Runs 100% locally using Whisper on Apple Silicon. No internet required.

![Whisper Dictate Demo](assets/demo.gif)

## Quick Start

### Option A: Automated setup

```bash
git clone https://github.com/GuigsEvt/whisper-dictate.git
cd whisper-dictate
chmod +x setup.sh download-model.sh
./setup.sh
```

### Option B: Manual setup with pip

```bash
git clone https://github.com/GuigsEvt/whisper-dictate.git
cd whisper-dictate
brew install portaudio
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Option C: Manual setup with uv

```bash
git clone https://github.com/GuigsEvt/whisper-dictate.git
cd whisper-dictate
brew install portaudio
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Download a model (optional)

```bash
./download-model.sh
```

Models auto-download from HuggingFace on first run if you skip this step.

### Run

```bash
source venv/bin/activate   # or .venv/bin/activate if using uv

# Terminal mode (default) -- hold SPACE to record, release to transcribe
python dictate.py

# Global mode -- hold fn key in any app (needs Input Monitoring permission)
python dictate.py --global

# Skip language prompt (use English directly)
python dictate.py --language en

# Auto-detect any language
python dictate.py --language auto

# Global mode with a different hotkey
python dictate.py --global --hotkey esc

# Use a local model
python dictate.py --model models/whisper-small-mlx
```

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- Homebrew
- PortAudio (`brew install portaudio`)

## Modes

| Mode | Command | How It Works | Permissions |
|------|---------|--------------|-------------|
| **Terminal** (default) | `python dictate.py` | Hold SPACE to record | None |
| **Global** | `python dictate.py --global` | Hold fn key in any app | Input Monitoring |

Terminal mode uses raw stdin -- works immediately, no permissions needed. Global mode uses Quartz event tap for the fn key and [pynput](https://github.com/moses-palmer/pynput) for other keys -- works in any app.

## Language

On launch, Whisper Dictate asks two questions:

**1. What language will you speak?**

```
  [0]  Auto-detect (any language)
  [1]  English (en) *
  [2]  French (fr)
  [3]  German (de)
  ...
  Speak [1]:
```

**2. What language should the text be in?**

```
  [0]  Same as spoken language
  [1]  English (translate to English)
  Output [0]:
```

This means you can:
- Speak French and get French text (transcription)
- Speak French and get English text (translation)
- Speak any language with auto-detect and get text in that language
- Skip both prompts with `--language en` or `--language auto` on the command line

Translation to English uses Whisper's built-in translation model -- no extra tools needed.

Supported: English, French, German, Spanish, Italian, Portuguese, Dutch, Japanese, Chinese, Korean, Russian, Arabic, Hindi, Polish, Turkish, Swedish, Danish, Norwegian, Finnish, Ukrainian -- or any language code Whisper supports.

## Models

| Model | Size | Accuracy | Command |
|-------|------|----------|---------|
| tiny | ~75 MB | Good | `--model mlx-community/whisper-tiny-mlx` |
| base | ~150 MB | Better | `--model mlx-community/whisper-base-mlx` |
| **small** | ~500 MB | **Great** | `--model mlx-community/whisper-small-mlx` |
| medium | ~1.5 GB | Excellent | `--model mlx-community/whisper-medium-mlx` |
| large-v3 | ~3 GB | Best | `--model mlx-community/whisper-large-v3-mlx` |
| large-v3-turbo | ~1.6 GB | Best tradeoff | `--model mlx-community/whisper-large-v3-turbo-mlx` |

Start with **small** (default). Upgrade to **large-v3-turbo** for better accuracy.

Use `./download-model.sh` to save models locally in `models/` for offline use. Otherwise they auto-download to `~/.cache/huggingface/` on first run.

## Configuration

Edit `config.yaml`:

```yaml
backend: "mlx"                              # mlx or faster-whisper
model: "mlx-community/whisper-small-mlx"    # HuggingFace repo or local path
language: "en"                              # en, fr, de, etc. or null for auto-detect
hotkey: "fn"                                # fn key (bottom-left on Mac)
auto_paste: true                            # auto Cmd+V after transcription
show_overlay: true                          # floating "Listening..." indicator
sound_on_start: true
sound_on_stop: true
trailing_space: true
```

### Hotkey Options

`fn` (default), `caps_lock`, `esc`, `ctrl_r`, `ctrl_l`, `alt_r`, `alt_l`, `cmd_r`, `shift_r`, `space`, `tab`, `enter`, `f1`-`f12`, or any single character.

Legacy `Key.xxx` format (e.g. `Key.ctrl_r`) also works.

### fn Key Setup

The fn (Globe) key is the bottom-left key on Mac keyboards. By default macOS maps it to the emoji picker, so you need to disable that:

**System Settings > Keyboard > "Press fn key to" > "Do Nothing"**

This frees the fn key for Whisper Dictate to use.

## CLI Reference

```
python dictate.py [options]

--global              Global hotkey mode (hold key in any app)
--hotkey KEY          Hotkey for global mode (default: fn). Options: fn, esc, ctrl_r, etc.
--model PATH          Model path or HuggingFace repo
--language LANG       Language code (default: en). Use "auto" for auto-detect. Skips interactive prompt.
--backend BACKEND     mlx or faster-whisper
--config FILE         Config file path (default: config.yaml)
--device N            Audio input device index
--list-devices        List available microphones
--no-auto-paste       Copy to clipboard only, no Cmd+V
--verbose, -v         Show timing and key events
--debug-keys          Show all key events pynput detects
--test                Self-test: load model, show overlay, record, transcribe
```

## Overlay

When recording, a floating "Listening..." indicator with a pulsing red dot appears at the top-center of your screen. Disable with `show_overlay: false` in `config.yaml`.

## faster-whisper Backend

For NVIDIA GPU or CPU-only systems:

1. Edit `requirements.txt` -- comment out `mlx-whisper`, uncomment `faster-whisper`
2. Reinstall: `pip install -r requirements.txt`
3. Set `backend: "faster-whisper"` in `config.yaml`
4. Use Systran models: `--model Systran/faster-whisper-small`

## macOS Permissions

**Terminal mode** (default) works without any special permissions.

**Global mode** (`--global`) requires:

1. **Microphone** -- System Settings > Privacy & Security > Microphone > enable your terminal
2. **Accessibility** -- System Settings > Privacy & Security > Accessibility > add your terminal
3. **Input Monitoring** -- System Settings > Privacy & Security > Input Monitoring > add your terminal

Restart your terminal after granting. Use `--debug-keys` to verify pynput can see your keystrokes.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `portaudio.h not found` | `brew install portaudio` then `pip install pyaudio` |
| `ModuleNotFoundError` | Activate venv: `source venv/bin/activate` |
| Hotkey not detected (global mode) | Grant Input Monitoring, restart terminal. Test with `--debug-keys` |
| No audio devices | `python dictate.py --list-devices` -- check mic is connected |
| Poor accuracy | Use a larger model: `--model mlx-community/whisper-large-v3-turbo-mlx` |
| First transcription slow | Model downloads on first use (~500MB for small), cached after |
| SPACE triggers multiple recordings | Update to latest version (fixed key-repeat timeout) |

## Project Structure

```
dictate.py              Main app -- hotkey, recording, transcription, paste
overlay.py              Floating "Listening..." indicator (PyObjC)
config.yaml             User configuration
download-model.sh       Interactive model downloader
setup.sh                Automated setup script
requirements.txt        Python dependencies
test_e2e.py             End-to-end test (simulates key events via Quartz)
models/                 Downloaded models (git-ignored)
sounds/
  start.wav             Recording start feedback
  stop.wav              Recording stop feedback
```

## License

MIT
