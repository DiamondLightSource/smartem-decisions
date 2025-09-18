#!/usr/bin/env python3
"""
Example usage script for fsrecorder acceleration features.

This script demonstrates practical usage patterns and shows how to use
different playback modes for various scenarios:

1. --dev-mode: Maximum acceleration for development/testing
2. --fast: 100x speed with reasonable delays (DEFAULT)
3. --exact: Preserve original timing exactly
4. Custom speed/delay combinations

Run this script to see fsrecorder in action and understand the performance
characteristics of different acceleration modes.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and show its output"""
    print(f"\n{'=' * 50}")
    print(f"🚀 {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'=' * 50}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
    except subprocess.CalledProcessError as e:
        print(f"   Command failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")


def create_sample_recording():
    """Create a sample recording with various file operations"""
    print("📁 Creating sample recording...")

    # Create test directory
    test_dir = Path("demo_source")
    test_dir.mkdir(exist_ok=True)

    # Start recording in background
    recording_proc = subprocess.Popen(
        [sys.executable, "fsrecorder.py", "record", str(test_dir), "-o", "demo_recording.tar.gz"]
    )

    # Wait for recording to start
    time.sleep(2)

    # Simulate file operations with delays
    print("      Creating files...")
    (test_dir / "file1.txt").write_text("Initial content")
    time.sleep(3)  # 3 second delay

    print("📝 Appending to file...")
    with open(test_dir / "file1.txt", "a") as f:
        f.write("\nAppended content")
    time.sleep(2)  # 2 second delay

    print("📁 Creating directory and nested file...")
    (test_dir / "subdir").mkdir(exist_ok=True)
    (test_dir / "subdir" / "nested.txt").write_text("Nested file content")
    time.sleep(4)  # 4 second delay

    print("   Modifying file...")
    (test_dir / "file1.txt").write_text("Completely new content")
    time.sleep(1)  # 1 second delay

    # Stop recording
    recording_proc.terminate()
    recording_proc.wait()

    print("   Recording completed!")
    return "demo_recording.tar.gz"


def demo_playback_modes(recording_file):
    """Demonstrate different playback acceleration modes"""

    # Show recording info
    run_command([sys.executable, "fsrecorder.py", "info", recording_file], "Recording Information")

    # 0. Default mode (now --fast)
    run_command(
        [sys.executable, "fsrecorder.py", "replay", recording_file, "target_default"],
        "Default Mode Replay (Fast Mode - 100x Speed)",
    )

    # 1. Development mode (maximum speed)
    run_command(
        [sys.executable, "fsrecorder.py", "replay", recording_file, "target_dev", "--dev-mode"],
        "Development Mode Replay (Maximum Speed)",
    )

    # 2. Fast mode (explicit)
    run_command(
        [sys.executable, "fsrecorder.py", "replay", recording_file, "target_fast", "--fast"],
        "Fast Mode Replay (Explicit --fast)",
    )

    # 3. Custom high speed with delay cap
    run_command(
        [
            sys.executable,
            "fsrecorder.py",
            "replay",
            recording_file,
            "target_custom",
            "--speed",
            "500",
            "--max-delay",
            "0.5",
        ],
        "Custom Mode (500x Speed, 0.5s Max Delay)",
    )

    # 4. Burst mode
    run_command(
        [sys.executable, "fsrecorder.py", "replay", recording_file, "target_burst", "--burst"],
        "Burst Mode (As Fast As Possible)",
    )

    # 5. Exact timing (for comparison)
    print(f"\n{'=' * 50}")
    print("      Exact Mode Replay (Original Timing)")
    print("Note: This would take ~10 seconds with original delays")
    print("Skipping for demo, but you can run:")
    print(f"python fsrecorder.py replay {recording_file} target_exact --exact")
    print(f"{'=' * 50}")


def main():
    """Main example function"""
    print("🎬 FSRecorder Usage Examples")
    print("=" * 50)

    # Create sample recording
    recording_file = create_sample_recording()

    # Demo different playback modes
    demo_playback_modes(recording_file)

    print("\n🎉 Examples completed!")
    print("\nGenerated files:")
    print(f"  📦 {recording_file} - Recording archive")
    print("  📁 target_dev/ - Development mode replay")
    print("  📁 target_fast/ - Fast mode replay")
    print("  📁 target_custom/ - Custom speed replay")
    print("  📁 target_burst/ - Burst mode replay")

    print("\n💡 Usage tips:")
    print("  • Default mode is --fast (100x speed) - good for most development")
    print("  • Use --dev-mode for maximum speed during rapid iteration")
    print("  • Use --exact when you need to reproduce exact timing")
    print("  • Use --speed X --max-delay Y for custom acceleration")


if __name__ == "__main__":
    main()
