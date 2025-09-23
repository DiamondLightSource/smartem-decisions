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
import os
import signal
import sys
import time
from datetime import datetime

from smartem_backend.api_client import SSEAgentClient


def handle_instruction(instruction_data: dict):
    """Handle incoming instructions from the backend"""
    instruction_id = instruction_data.get("instruction_id")
    instruction_type = instruction_data.get("instruction_type")
    payload = instruction_data.get("payload", {})

    print("\nINSTRUCTION RECEIVED:")
    print(f"   ID: {instruction_id}")
    print(f"   Type: {instruction_type}")
    print(f"   Payload: {payload}")
    print(f"   Timestamp: {instruction_data.get('created_at')}")

    # Measure processing time
    start_time = time.time()

    try:
        # Simulate processing the instruction
        if instruction_type == "microscope.control.move_stage":
            stage_position = payload.get("stage_position", {})
            speed = payload.get("speed", "normal")

            x, y, z = stage_position.get("x"), stage_position.get("y"), stage_position.get("z")
            print(f"   Moving stage to position: x={x}, y={y}, z={z}")
            print(f"   Speed: {speed}")

            # Simulate processing time
            time.sleep(0.5)  # Simulate 500ms processing time

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Acknowledge successful processing
            client.acknowledge_instruction(
                instruction_id=instruction_id,
                status="processed",
                result=f"Stage moved to {stage_position}",
                processing_time_ms=processing_time_ms,
            )
            print(f"   Instruction {instruction_id} completed successfully in {processing_time_ms}ms")

        elif instruction_type == "microscope.control.take_image":
            image_params = payload.get("image_params", {})
            print(f"   Taking image with parameters: {image_params}")

            # Simulate image acquisition
            time.sleep(1.0)  # Simulate 1s image acquisition

            processing_time_ms = int((time.time() - start_time) * 1000)

            client.acknowledge_instruction(
                instruction_id=instruction_id,
                status="processed",
                result=f"Image acquired with params {image_params}",
                processing_time_ms=processing_time_ms,
            )
            print(f"   Image acquired in {processing_time_ms}ms")

        elif instruction_type == "microscope.control.reorder_gridsquares":
            gridsquare_ids = payload.get("gridsquare_ids", [])
            priority = payload.get("priority", "normal")
            reason = payload.get("reason", "")
            print(f"   Reordering grid squares: {gridsquare_ids}")
            print(f"   Priority: {priority}, Reason: {reason}")

            # Simulate reordering processing
            time.sleep(0.3)  # Simulate 300ms processing time

            processing_time_ms = int((time.time() - start_time) * 1000)

            client.acknowledge_instruction(
                instruction_id=instruction_id,
                status="processed",
                result=f"Reordered {len(gridsquare_ids)} grid squares with {priority} priority",
                processing_time_ms=processing_time_ms,
            )
            print(f"   Grid squares reordered in {processing_time_ms}ms")

        elif instruction_type == "microscope.control.skip_gridsquares":
            gridsquare_ids = payload.get("gridsquare_ids", [])
            reason = payload.get("reason", "")
            print(f"   Skipping grid squares: {gridsquare_ids}")
            print(f"   Reason: {reason}")

            # Simulate skipping processing
            time.sleep(0.2)  # Simulate 200ms processing time

            processing_time_ms = int((time.time() - start_time) * 1000)

            client.acknowledge_instruction(
                instruction_id=instruction_id,
                status="processed",
                result=f"Skipped {len(gridsquare_ids)} grid squares",
                processing_time_ms=processing_time_ms,
            )
            print(f"   Grid squares skipped in {processing_time_ms}ms")

        elif instruction_type == "microscope.control.reorder_foilholes":
            gridsquare_id = payload.get("gridsquare_id")
            foilhole_ids = payload.get("foilhole_ids", [])
            priority = payload.get("priority", "normal")
            reason = payload.get("reason", "")
            print(f"   Reordering foilholes in grid square {gridsquare_id}: {foilhole_ids}")
            print(f"   Priority: {priority}, Reason: {reason}")

            # Simulate foilhole reordering
            time.sleep(0.4)  # Simulate 400ms processing time

            processing_time_ms = int((time.time() - start_time) * 1000)

            client.acknowledge_instruction(
                instruction_id=instruction_id,
                status="processed",
                result=f"Reordered {len(foilhole_ids)} foilholes in {gridsquare_id}",
                processing_time_ms=processing_time_ms,
            )
            print(f"   Foilholes reordered in {processing_time_ms}ms")

        else:
            # Unknown instruction type
            processing_time_ms = int((time.time() - start_time) * 1000)
            client.acknowledge_instruction(
                instruction_id=instruction_id,
                status="declined",
                error_message=f"Unknown instruction type: {instruction_type}",
                processing_time_ms=processing_time_ms,
            )
            print("   Unknown instruction type, declined")

    except Exception as e:
        # Acknowledge failure if processing fails
        processing_time_ms = int((time.time() - start_time) * 1000)
        client.acknowledge_instruction(
            instruction_id=instruction_id, status="failed", error_message=str(e), processing_time_ms=processing_time_ms
        )
        print(f"   Instruction {instruction_id} failed: {e}")


def handle_connection(connection_data: dict):
    """Handle connection events"""
    print("\nCONNECTED:")
    print(f"   Agent ID: {connection_data.get('agent_id')}")
    print(f"   Session ID: {connection_data.get('session_id')}")
    print(f"   Connection ID: {connection_data.get('connection_id')}")
    print("   Waiting for instructions...")


def handle_error(error: Exception):
    """Handle errors"""
    print(f"\nERROR: {error}")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n\nReceived signal {sig}, shutting down...")
    if client:
        client.stop()
    sys.exit(0)


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Configuration
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")  # SmartEM backend URL
    AGENT_ID = "microscope-01"  # Unique identifier for this agent/microscope
    SESSION_ID = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"  # Current session

    print("SmartEM Agent SSE Client Example")
    print("=" * 50)
    print(f"Backend URL: {BASE_URL}")
    print(f"Agent ID: {AGENT_ID}")
    print(f"Session ID: {SESSION_ID}")
    print()

    # Create session first to ensure it exists
    print("Creating agent session...")
    try:
        import requests

        response = requests.post(
            f"{BASE_URL}/debug/sessions/create-managed",
            json={
                "agent_id": AGENT_ID,
                "name": f"Test Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "description": "Automated test session from SSE client example",
            },
            timeout=10,
        )
        if response.status_code == 200:
            session_data = response.json()
            # Use the session ID returned by the server
            SESSION_ID = session_data["session_id"]
            print(f"Session created successfully: {SESSION_ID}")
        else:
            print(f"Session creation failed ({response.status_code}), using generated ID: {SESSION_ID}")
    except Exception as e:
        print(f"Could not create session ({e}), using generated ID: {SESSION_ID}")

    print("\nPress Ctrl+C to stop\n")

    # Set up signal handling for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create SSE client with enhanced configuration
    client = SSEAgentClient(
        base_url=BASE_URL,
        agent_id=AGENT_ID,
        session_id=SESSION_ID,
        timeout=60,
        max_retries=10,
        initial_retry_delay=1.0,
        max_retry_delay=30.0,
    )

    try:
        # Option 1: Synchronous (blocking) mode
        print("Starting synchronous SSE stream...")
        client.stream_instructions(
            instruction_callback=handle_instruction, connection_callback=handle_connection, error_callback=handle_error
        )

        # Show final statistics
        print("\nFinal Statistics:")
        stats = client.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        client.stop()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        print("Agent client stopped")


async def async_example():
    """Example of using the async version with auto-retry"""
    print("SmartEM Agent SSE Client - Async Example")
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
        print("\nInterrupted by user")
    finally:
        client.stop()
        print("Async agent client stopped")


# To run the async example instead:
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(async_example())
