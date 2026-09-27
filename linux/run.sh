#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

APP_NAME="YOLO_AutoInstaller_2.0"

if [ -f "$PROJECT_DIR/dist/$APP_NAME" ]; then
    exec "$PROJECT_DIR/dist/$APP_NAME" "$@"
elif [ -f "$PROJECT_DIR/dist/YOLO_AutoInstaller" ]; then
    exec "$PROJECT_DIR/dist/YOLO_AutoInstaller" "$@"
elif [ -f "$PROJECT_DIR/$APP_NAME" ]; then
    exec "$PROJECT_DIR/$APP_NAME" "$@"
else
    exec python3 "$PROJECT_DIR/main.py" "$@"
fi
