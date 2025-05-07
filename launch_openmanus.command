#!/bin/bash

# Launch script for OpenManus on macOS
# This script sets up the virtual environment and launches OpenManus

# Change to the directory where the script is located
cd "$(dirname "$0")"

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Setting up OpenManus...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed. Please install Python 3.12 or newer.${NC}"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python $REQUIRED_VERSION or newer is required. You have Python $PYTHON_VERSION.${NC}"
    read -p "Press Enter to exit..."
    exit 1
fi

# Remove existing virtual environment if it exists
if [ -d ".venv" ]; then
    echo -e "${YELLOW}Removing existing virtual environment...${NC}"
    rm -rf .venv
fi

# Create virtual environment using built-in venv module
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv .venv

if [ $? -ne 0 ] || [ ! -d ".venv" ]; then
    echo -e "${RED}Error: Failed to create virtual environment.${NC}"
    read -p "Press Enter to exit..."
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Upgrade pip within the virtual environment
echo -e "${YELLOW}Upgrading pip in virtual environment...${NC}"
python -m pip install --upgrade pip

if [ $? -ne 0 ]; then
    echo -e "${RED}Warning: Failed to upgrade pip. Continuing anyway...${NC}"
fi

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
python -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to install dependencies.${NC}"
    read -p "Press Enter to exit..."
    exit 1
fi

# Install Playwright if needed
echo -e "${YELLOW}Installing Playwright...${NC}"
python -m pip install playwright

if [ $? -eq 0 ]; then
    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    python -m playwright install

    if [ $? -ne 0 ]; then
        echo -e "${RED}Warning: Failed to install Playwright browsers. Browser features may not work.${NC}"
    fi
else
    echo -e "${RED}Warning: Failed to install Playwright. Browser features will not work.${NC}"
fi

# Check if config.toml exists
if [ ! -f "config/config.toml" ]; then
    echo -e "${YELLOW}Creating default configuration file...${NC}"
    cp config/config.example-model-ollama.toml config/config.toml
    echo -e "${YELLOW}Created default configuration for Ollama.${NC}"
    echo -e "${YELLOW}Edit config/config.toml to customize your settings.${NC}"
fi

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${YELLOW}Warning: Ollama doesn't appear to be running.${NC}"
    echo -e "${YELLOW}Please start Ollama before continuing.${NC}"
    read -p "Press Enter to continue once Ollama is running, or Ctrl+C to exit..."
fi

# Launch OpenManus
echo -e "${GREEN}Launching OpenManus...${NC}"
python main.py

# Deactivate virtual environment when done
deactivate
