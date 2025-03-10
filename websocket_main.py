#!/usr/bin/env python
"""
WebSocket Server for Super-Py

This script launches a WebSocket server for the Super-Py agent.
Clients can connect and interact with agents via WebSocket messages.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.websocket_server import start_server


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Start the Super-Py WebSocket server")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host address to bind the server to"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind the server to"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"Starting Super-Py WebSocket server on {args.host}:{args.port}...")
    print("Press Ctrl+C to stop the server")
    start_server(host=args.host, port=args.port)