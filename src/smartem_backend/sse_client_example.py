#!/usr/bin/env python3
"""
Example usage of the SSEAgentClient for receiving instructions from SmartEM backend.

This demonstrates how an agent (microscope control software) would integrate
with the backend to receive real-time instructions via Server-Sent Events.

Prerequisites:
    pip install -e ".[backend]"  # Installs sse-starlette for server
    pip install -e ".[client]"   # Installs sseclient-py for client
"""

import logging
import signal
import sys
from datetime import datetime

from smartem_backend.api_client import SSEAgentClient


def handle_instruction(instruction_data: dict):
    """Handle incoming instructions from the backend"""
    instruction_id = instruction_data.get("instruction_id")
    instruction_type = instruction_data.get("instruction_type")
    payload = instruction_data.get("payload", {})

    print("\n🔧 INSTRUCTION RECEIVED:")
    print(f"   ID: {instruction_id}")
    print(f"   Type: {instruction_type}")
    print(f"   Payload: {payload}")
    print(f"   Timestamp: {instruction_data.get('created_at')}")

    # Simulate processing the instruction
    if instruction_type == "microscope.control.move_stage":
        stage_position = payload.get("stage_position", {})
        speed = payload.get("speed", "normal")

        x, y, z = stage_position.get("x"), stage_position.get("y"), stage_position.get("z")
        print(f"   🎯 Moving stage to position: x={x}, y={y}, z={z}")
        print(f"   ⚡ Speed: {speed}")

        # Simulate successful processing
        try:
            # Here you would integrate with actual microscope control
            # For demo, we'll just acknowledge success
            client.acknowledge_instruction(
                instruction_id=instruction_id, status="processed", result=f"Stage moved to {stage_position}"
            )
            print(f"   ✅ Instruction {instruction_id} completed successfully")

        except Exception as e:
            # Acknowledge failure if processing fails
            client.acknowledge_instruction(instruction_id=instruction_id, status="failed", error_message=str(e))
            print(f"   ❌ Instruction {instruction_id} failed: {e}")

    else:
        # Unknown instruction type
        client.acknowledge_instruction(
            instruction_id=instruction_id,
            status="declined",
            error_message=f"Unknown instruction type: {instruction_type}",
        )
        print("   ⚠️  Unknown instruction type, declined")


def handle_connection(connection_data: dict):
    """Handle connection events"""
    print("\n🔗 CONNECTED:")
    print(f"   Agent ID: {connection_data.get('agent_id')}")
    print(f"   Session ID: {connection_data.get('session_id')}")
    print(f"   Connection ID: {connection_data.get('connection_id')}")
    print("   Waiting for instructions...")


def handle_error(error: Exception):
    """Handle errors"""
    print(f"\n❌ ERROR: {error}")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n\n🛑 Received signal {sig}, shutting down...")
    if client:
        client.stop()
    sys.exit(0)


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Configuration
    BASE_URL = "http://localhost:8000"  # SmartEM backend URL
    AGENT_ID = "microscope-01"  # Unique identifier for this agent/microscope
    SESSION_ID = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"  # Current session

    print("🔬 SmartEM Agent SSE Client Example")
    print("=" * 50)
    print(f"Backend URL: {BASE_URL}")
    print(f"Agent ID: {AGENT_ID}")
    print(f"Session ID: {SESSION_ID}")
    print("\nPress Ctrl+C to stop\n")

    # Set up signal handling for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create SSE client
    client = SSEAgentClient(base_url=BASE_URL, agent_id=AGENT_ID, session_id=SESSION_ID, timeout=60)

    try:
        # Option 1: Synchronous (blocking) mode
        print("Starting synchronous SSE stream...")
        client.stream_instructions(
            instruction_callback=handle_instruction, connection_callback=handle_connection, error_callback=handle_error
        )

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        client.stop()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("🏁 Agent client stopped")


async def async_example():
    """Example of using the async version with auto-retry"""
    print("🔬 SmartEM Agent SSE Client - Async Example")
    print("=" * 50)

    client = SSEAgentClient(
        base_url="http://localhost:8000",
        agent_id="microscope-02",
        session_id=f"session-async-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        timeout=60,
    )

    try:
        # Option 2: Asynchronous mode with auto-retry
        await client.stream_instructions_async(
            instruction_callback=handle_instruction,
            connection_callback=handle_connection,
            error_callback=handle_error,
            retry_interval=5,  # Retry every 5 seconds
            max_retries=10,  # Up to 10 reconnection attempts
        )
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    finally:
        client.stop()
        print("🏁 Async agent client stopped")


# To run the async example instead:
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(async_example())
