#!/bin/bash
# setup_pi.sh - Script to set up the tldr environment on a Raspberry Pi

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate && \
python3 -m pip install --upgrade pip && \
python3 -m pip install -r requirements.txt && \
echo "Dependencies installed."

echo "Running setup_config.py to create .config from template..."
python3 setup_config.py

echo ""
echo "Setup complete!"
echo "IMPORTANT: Remember to edit the .config file with your credentials."
echo "You may need to deactivate and reactivate the virtual environment for changes to take full effect in this terminal:"
echo "  deactivate"
echo "  source .venv/bin/activate"
