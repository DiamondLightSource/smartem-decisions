#!/bin/bash

# Check if source directory is provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 source_directory [output.iso]"
    exit 1
fi

SOURCE_DIR="$1"
ISO_NAME="${2:-${SOURCE_DIR%/}.iso}"

# Check if the source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory '$SOURCE_DIR' not found"
    exit 1
fi

# Check for mkisofs or genisoimage
ISO_CMD=""
if command -v mkisofs &> /dev/null; then
    ISO_CMD="mkisofs"
elif command -v genisoimage &> /dev/null; then
    ISO_CMD="genisoimage"
else
    echo "Error: Neither mkisofs nor genisoimage found. Please install one of them."
    echo "  For Debian/Ubuntu: sudo apt-get install genisoimage"
    echo "  For RHEL/CentOS: sudo yum install genisoimage"
    exit 1
fi

echo "Creating ISO from '$SOURCE_DIR' to '$ISO_NAME'..."
$ISO_CMD -o "$ISO_NAME" -J -r -V "$(basename "$SOURCE_DIR")" "$SOURCE_DIR"

if [ $? -eq 0 ]; then
    echo "ISO created successfully: $ISO_NAME"
    echo "Size: $(du -h "$ISO_NAME" | cut -f1)"
else
    echo "Error creating ISO"
    exit 1
fi
