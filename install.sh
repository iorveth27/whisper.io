#!/usr/bin/env bash
# whisper.io — One-line installer
# Usage: curl -sSL https://raw.githubusercontent.com/iorveth27/whisper.io/main/install.sh | bash

set -e

REPO_URL="https://github.com/iorveth27/whisper.io.git"
INSTALL_DIR="$HOME/.whisper.io"

echo "========================================================"
# Print ASCII logo (same as in Python)
echo -e "\033[36m"
cat << "EOF"
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣶⣦⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣤⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣷⡀⠀⠀⠀⠀⠀⠀⠠⣾⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⣸⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⣤⣤⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⡿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠈⣿⣿⣿⣿⣿⠋⠁⠀⠀⠈⠹⣿⣿⣿⣿⣿⡿⠋⠀⠀⠈⠻⣿⣿⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣿⣿⣿⣿⠃⠀⠀⠀⣴⣶⡄⢹⣿⣿⣿⣿⠃⢰⣶⡄⠀⠀⣿⣿⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣿⣿⣿⣿⡆⠀⠀⠀⠹⠿⠁⣸⣿⣿⣿⣿⡀⠘⡿⠃⠀⢀⣿⣿⣿⡆⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣶⣿⣿⣯⣹⣿⣷⣤⣾⣿⣿⣿⣿⣿⣿⣃⣀⣀⣀⣀⠀
⠀⠾⠿⠟⠛⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠛⠋⠉⠉⠋⠀
⠠⣤⣤⣶⡶⠿⠛⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠛⠛⠛⠛⠷⣶⡄
⠀⠀⠉⢀⣠⣶⠾⠟⠉⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠛⠛⠳⢶⣦⣄⡀⠀⠀
⠀⠀⠀⠟⠋⠁⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡏⠁⠀⠀⠀⠀⠀⠀⠀⠉⠁⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⢀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⣸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀
EOF
echo -e "\033[0m"
echo "  whisper.io — Installation Script"
echo "========================================================"
echo ""

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: This application is only supported on macOS." >&2
    exit 1
fi

# Check Apple Silicon
if [[ "$(uname -m)" != "arm64" ]]; then
    echo "Error: This application requires Apple Silicon (M1/M2/M3/M4/etc.)." >&2
    exit 1
fi

# Check git
if ! command -v git &>/dev/null; then
    echo "Error: git is not installed. Please install git or Xcode Command Line Tools first." >&2
    exit 1
fi

# Setup installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    echo "  whisper.io is already installed at $INSTALL_DIR."
    echo "  Updating existing installation..."
    cd "$INSTALL_DIR"
    git fetch --all
    git reset --hard origin/main
else
    echo "  Cloning repository to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo ""
echo "  Running setup script..."
./setup.sh

echo ""
echo "  Configuring global 'whisper' command..."

# Create a wrapper bin directory in home if it doesn't exist, as a fallback
mkdir -p "$HOME/.local/bin"

LINK_CREATED=false

# Method 1: Try writing to /usr/local/bin directly
if [ -w /usr/local/bin ]; then
    ln -sf "$INSTALL_DIR/whisper-dictate.sh" /usr/local/bin/whisper
    echo "  ✅ Created global command: /usr/local/bin/whisper"
    LINK_CREATED=true
fi

# Method 2: Try with sudo
if [ "$LINK_CREATED" = false ]; then
    echo "  Need administrator privileges to place the 'whisper' command in /usr/local/bin."
    echo "  (Please enter your Mac user password if prompted, or press Ctrl+C to fallback to shell alias)"
    if sudo ln -sf "$INSTALL_DIR/whisper-dictate.sh" /usr/local/bin/whisper; then
        echo "  ✅ Created global command: /usr/local/bin/whisper (using sudo)"
        LINK_CREATED=true
    fi
fi

# Method 3: Fallback to zsh alias / user path
if [ "$LINK_CREATED" = false ]; then
    echo "  Could not link to /usr/local/bin. Falling back to local bin / shell alias..."
    
    # Try adding to ~/.local/bin/whisper
    ln -sf "$INSTALL_DIR/whisper-dictate.sh" "$HOME/.local/bin/whisper"
    
    # Ensure ~/.local/bin is in PATH or write alias to .zshrc
    if [[ -f "$HOME/.zshrc" ]]; then
        if ! grep -q "alias whisper=" "$HOME/.zshrc"; then
            echo "" >> "$HOME/.zshrc"
            echo "# whisper.io alias" >> "$HOME/.zshrc"
            echo "alias whisper=\"$INSTALL_DIR/whisper-dictate.sh\"" >> "$HOME/.zshrc"
            echo "  ✅ Added alias to ~/.zshrc."
        else
            echo "  ✅ Alias already exists in ~/.zshrc."
        fi
        echo "  👉 Run 'source ~/.zshrc' or open a new terminal window to start using 'whisper'."
    elif [[ -f "$HOME/.bash_profile" ]]; then
        if ! grep -q "alias whisper=" "$HOME/.bash_profile"; then
            echo "" >> "$HOME/.bash_profile"
            echo "# whisper.io alias" >> "$HOME/.bash_profile"
            echo "alias whisper=\"$INSTALL_DIR/whisper-dictate.sh\"" >> "$HOME/.bash_profile"
            echo "  ✅ Added alias to ~/.bash_profile."
        else
            echo "  ✅ Alias already exists in ~/.bash_profile."
        fi
        echo "  👉 Run 'source ~/.bash_profile' or open a new terminal window to start using 'whisper'."
    else
        echo "  ⚠️  Please add '$HOME/.local/bin' to your PATH or create an alias to '$INSTALL_DIR/whisper-dictate.sh'."
    fi
else
    echo "  👉 You can now run the tool from any directory by typing 'whisper'!"
fi

echo ""
echo "========================================================"
echo "  whisper.io installation complete!"
echo "========================================================"
echo "  To use:"
echo "    whisper          (English)"
echo "    whisper ua       (Ukrainian)"
echo "    whisper spanish  (Spanish)"
echo "    whisper auto     (Auto-detect)"
echo "========================================================"
