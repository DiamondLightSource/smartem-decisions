#!/usr/bin/env python3
"""
External Message Simulator for SmartEM Decisions System

This tool simulates external data processing systems by publishing realistic messages
to RabbitMQ queues that the SmartEM backend consumer will process. It enables
end-to-end testing of the message transformation pipeline without requiring
actual ML pipelines or image processing systems.

Usage:
    python -m smartem_backend.external_message_simulator --help
"""

import json
import random
import time
import uuid
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

from smartem_backend.utils import setup_rabbitmq

app = typer.Typer(help="Simulate external messages for SmartEM system testing")
console = Console()


class ExternalMessageSimulator:
    """Simulates external data processing messages for system testing"""

    def __init__(self):
        """Initialize the simulator with RabbitMQ connection"""
        try:
            self.publisher, _ = setup_rabbitmq()
            console.print("[green]✓[/green] Connected to RabbitMQ")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to connect to RabbitMQ: {e}")
            raise typer.Exit(1) from e

    def publish_message(self, message_type: str, payload: dict, routing_key: str = None) -> bool:
        """Publish a message to RabbitMQ with proper formatting"""
        import pika

        if routing_key is None:
            routing_key = f"external.{message_type.lower()}"

        message = {
            "message_id": str(uuid.uuid4()),
            "event_type": message_type,
            "timestamp": datetime.now().isoformat(),
            "source": "external_simulator",
            "payload": payload,
        }

        try:
            self.publisher.connect()
            # Publish to the smartem_backend queue that the consumer is listening to
            self.publisher.channel().basic_publish(
                exchange="",  # Use default exchange for direct routing
                routing_key="smartem_backend",  # Route to the backend queue
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type="application/json",
                ),
            )
            return True
        except Exception as e:
            console.print(f"[red]Failed to publish message: {e}[/red]")
            return False

    def generate_motion_correction_complete(self, gridsquare_id: str = None, quality_score: float = None) -> dict:
        """Generate MOTION_CORRECTION_COMPLETE message"""
        if gridsquare_id is None:
            gridsquare_id = f"GS_{random.randint(1, 20):03d}_{random.randint(1, 50):03d}"
        if quality_score is None:
            quality_score = random.uniform(0.3, 0.95)

        return {
            "gridsquare_id": gridsquare_id,
            "micrograph_id": f"mic_{random.randint(1000, 9999)}",
            "processing_results": {
                "total_motion": round(random.uniform(0.5, 5.0), 2),
                "average_motion": round(random.uniform(0.2, 2.0), 2),
                "motion_correction_quality": quality_score,
                "drift_per_frame": [round(random.uniform(0.1, 0.8), 3) for _ in range(10)],
            },
            "processing_time_seconds": round(random.uniform(15.0, 45.0), 1),
            "software_version": "MotionCor2_v1.6.4",
        }

    def generate_ctf_complete(self, gridsquare_id: str = None, resolution: float = None) -> dict:
        """Generate CTF_COMPLETE message"""
        if gridsquare_id is None:
            gridsquare_id = f"GS_{random.randint(1, 20):03d}_{random.randint(1, 50):03d}"
        if resolution is None:
            resolution = random.uniform(2.5, 8.0)

        return {
            "gridsquare_id": gridsquare_id,
            "micrograph_id": f"mic_{random.randint(1000, 9999)}",
            "ctf_results": {
                "resolution_estimate": round(resolution, 2),
                "defocus_u": round(random.uniform(-3.0, -1.0), 3),
                "defocus_v": round(random.uniform(-3.0, -1.0), 3),
                "astigmatism": round(random.uniform(0.0, 0.5), 3),
                "phase_shift": round(random.uniform(0.0, 180.0), 2),
                "confidence": round(random.uniform(0.6, 0.99), 3),
            },
            "processing_time_seconds": round(random.uniform(8.0, 25.0), 1),
            "software_version": "CTFFIND4_v4.1.14",
        }

    def generate_particle_picking_complete(self, gridsquare_id: str = None, particle_count: int = None) -> dict:
        """Generate PARTICLE_PICKING_COMPLETE message"""
        if gridsquare_id is None:
            gridsquare_id = f"GS_{random.randint(1, 20):03d}_{random.randint(1, 50):03d}"
        if particle_count is None:
            particle_count = random.randint(50, 800)

        return {
            "gridsquare_id": gridsquare_id,
            "micrograph_id": f"mic_{random.randint(1000, 9999)}",
            "picking_results": {
                "particles_picked": particle_count,
                "particle_density": round(particle_count / random.uniform(8.0, 12.0), 1),
                "average_particle_size": round(random.uniform(150.0, 300.0), 1),
                "picking_confidence": round(random.uniform(0.7, 0.95), 3),
                "template_correlation": round(random.uniform(0.6, 0.9), 3),
            },
            "processing_time_seconds": round(random.uniform(30.0, 120.0), 1),
            "software_version": "crYOLO_v1.9.6",
        }

    def generate_particle_selection_complete(self, gridsquare_id: str = None, selection_ratio: float = None) -> dict:
        """Generate PARTICLE_SELECTION_COMPLETE message"""
        if gridsquare_id is None:
            gridsquare_id = f"GS_{random.randint(1, 20):03d}_{random.randint(1, 50):03d}"
        if selection_ratio is None:
            selection_ratio = random.uniform(0.4, 0.85)

        total_particles = random.randint(200, 1000)
        selected_particles = int(total_particles * selection_ratio)

        return {
            "gridsquare_id": gridsquare_id,
            "micrograph_id": f"mic_{random.randint(1000, 9999)}",
            "selection_results": {
                "total_particles": total_particles,
                "selected_particles": selected_particles,
                "rejected_particles": total_particles - selected_particles,
                "selection_ratio": round(selection_ratio, 3),
                "quality_threshold": round(random.uniform(0.5, 0.8), 2),
                "average_selected_quality": round(random.uniform(0.7, 0.95), 3),
            },
            "processing_time_seconds": round(random.uniform(20.0, 60.0), 1),
            "software_version": "RELION_v4.0.1",
        }

    def generate_gridsquare_model_prediction(self, gridsquare_id: str = None, prediction_score: float = None) -> dict:
        """Generate GRIDSQUARE_MODEL_PREDICTION message"""
        if gridsquare_id is None:
            gridsquare_id = f"GS_{random.randint(1, 20):03d}_{random.randint(1, 50):03d}"
        if prediction_score is None:
            prediction_score = random.uniform(0.1, 0.95)

        return {
            "gridsquare_id": gridsquare_id,
            "grid_uuid": f"grid-{uuid.uuid4()}",
            "prediction_results": {
                "quality_score": round(prediction_score, 3),
                "ice_thickness_score": round(random.uniform(0.2, 0.9), 3),
                "contamination_score": round(random.uniform(0.1, 0.8), 3),
                "particle_distribution_score": round(random.uniform(0.3, 0.95), 3),
                "overall_suitability": round(prediction_score, 3),
                "confidence": round(random.uniform(0.75, 0.98), 3),
            },
            "model_info": {
                "model_name": "GridSquareQualityNet_v2.1",
                "model_version": "2.1.0",
                "training_date": "2025-08-15",
                "feature_count": 128,
            },
            "processing_time_seconds": round(random.uniform(2.0, 8.0), 1),
        }

    def generate_foilhole_model_prediction(self, gridsquare_id: str = None, foilhole_count: int = None) -> dict:
        """Generate FOILHOLE_MODEL_PREDICTION message"""
        if gridsquare_id is None:
            gridsquare_id = f"GS_{random.randint(1, 20):03d}_{random.randint(1, 50):03d}"
        if foilhole_count is None:
            foilhole_count = random.randint(8, 25)

        foilhole_predictions = []
        for i in range(foilhole_count):
            foilhole_predictions.append(
                {
                    "foilhole_id": f"FH_{i + 1:03d}",
                    "quality_score": round(random.uniform(0.2, 0.95), 3),
                    "ice_thickness": round(random.uniform(50.0, 200.0), 1),
                    "hole_diameter": round(random.uniform(1.0, 2.5), 2),
                    "contamination_level": round(random.uniform(0.0, 0.6), 3),
                    "targeting_priority": random.randint(1, foilhole_count),
                }
            )

        # Sort by quality score for realistic priority ordering
        foilhole_predictions.sort(key=lambda x: x["quality_score"], reverse=True)
        for i, fh in enumerate(foilhole_predictions):
            fh["targeting_priority"] = i + 1

        return {
            "gridsquare_id": gridsquare_id,
            "grid_uuid": f"grid-{uuid.uuid4()}",
            "foilhole_predictions": foilhole_predictions,
            "prediction_summary": {
                "total_foilholes": foilhole_count,
                "high_quality_count": len([fh for fh in foilhole_predictions if fh["quality_score"] > 0.7]),
                "average_quality": round(sum(fh["quality_score"] for fh in foilhole_predictions) / foilhole_count, 3),
                "recommended_sequence": [fh["foilhole_id"] for fh in foilhole_predictions[:5]],
            },
            "model_info": {
                "model_name": "FoilHoleTargetingNet_v1.8",
                "model_version": "1.8.2",
                "prediction_confidence": round(random.uniform(0.8, 0.96), 3),
            },
            "processing_time_seconds": round(random.uniform(5.0, 15.0), 1),
        }

    def generate_model_parameter_update(self, model_name: str = None) -> dict:
        """Generate MODEL_PARAMETER_UPDATE message"""
        if model_name is None:
            model_name = random.choice(["GridSquareQualityNet", "FoilHoleTargetingNet", "IceThicknessClassifier"])

        return {
            "model_name": model_name,
            "update_type": "parameter_refinement",
            "parameter_updates": {
                "quality_threshold": round(random.uniform(0.6, 0.8), 2),
                "ice_thickness_max": round(random.uniform(120.0, 180.0), 1),
                "contamination_threshold": round(random.uniform(0.3, 0.7), 2),
                "confidence_minimum": round(random.uniform(0.7, 0.9), 2),
            },
            "update_reason": random.choice(
                ["performance_optimization", "facility_calibration", "dataset_expansion", "user_feedback"]
            ),
            "model_version": f"{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 5)}",
            "effective_date": (datetime.now() + timedelta(minutes=random.randint(1, 30))).isoformat(),
            "validation_metrics": {
                "accuracy": round(random.uniform(0.85, 0.95), 3),
                "precision": round(random.uniform(0.82, 0.94), 3),
                "recall": round(random.uniform(0.80, 0.92), 3),
                "f1_score": round(random.uniform(0.83, 0.93), 3),
            },
        }


# CLI Commands


@app.command()
def motion_correction(
    gridsquare_id: str = typer.Option(None, help="Grid square ID"),
    quality_score: float = typer.Option(None, help="Motion correction quality score (0.0-1.0)"),
    count: int = typer.Option(1, help="Number of messages to send"),
):
    """Simulate MOTION_CORRECTION_COMPLETE messages"""
    simulator = ExternalMessageSimulator()

    for i in range(count):
        payload = simulator.generate_motion_correction_complete(gridsquare_id, quality_score)
        success = simulator.publish_message("motion_correction.completed", payload)

        if success:
            console.print(f"[green]✓[/green] Published MOTION_CORRECTION_COMPLETE {i + 1}/{count}")
            console.print(f"  Grid Square: {payload['gridsquare_id']}")
            console.print(f"  Quality: {payload['processing_results']['motion_correction_quality']:.3f}")
        else:
            console.print(f"[red]✗[/red] Failed to publish message {i + 1}")

        if count > 1 and i < count - 1:
            time.sleep(1)


@app.command()
def ctf_complete(
    gridsquare_id: str = typer.Option(None, help="Grid square ID"),
    resolution: float = typer.Option(None, help="CTF resolution estimate (Angstroms)"),
    count: int = typer.Option(1, help="Number of messages to send"),
):
    """Simulate CTF_COMPLETE messages"""
    simulator = ExternalMessageSimulator()

    for i in range(count):
        payload = simulator.generate_ctf_complete(gridsquare_id, resolution)
        success = simulator.publish_message("ctf.completed", payload)

        if success:
            console.print(f"[green]✓[/green] Published CTF_COMPLETE {i + 1}/{count}")
            console.print(f"  Grid Square: {payload['gridsquare_id']}")
            console.print(f"  Resolution: {payload['ctf_results']['resolution_estimate']:.2f}Å")
        else:
            console.print(f"[red]✗[/red] Failed to publish message {i + 1}")

        if count > 1 and i < count - 1:
            time.sleep(1)


@app.command()
def particle_picking(
    gridsquare_id: str = typer.Option(None, help="Grid square ID"),
    particle_count: int = typer.Option(None, help="Number of particles picked"),
    count: int = typer.Option(1, help="Number of messages to send"),
):
    """Simulate PARTICLE_PICKING_COMPLETE messages"""
    simulator = ExternalMessageSimulator()

    for i in range(count):
        payload = simulator.generate_particle_picking_complete(gridsquare_id, particle_count)
        success = simulator.publish_message("particle_picking.completed", payload)

        if success:
            console.print(f"[green]✓[/green] Published PARTICLE_PICKING_COMPLETE {i + 1}/{count}")
            console.print(f"  Grid Square: {payload['gridsquare_id']}")
            console.print(f"  Particles: {payload['picking_results']['particles_picked']}")
        else:
            console.print(f"[red]✗[/red] Failed to publish message {i + 1}")

        if count > 1 and i < count - 1:
            time.sleep(1)


@app.command()
def particle_selection(
    gridsquare_id: str = typer.Option(None, help="Grid square ID"),
    selection_ratio: float = typer.Option(None, help="Particle selection ratio (0.0-1.0)"),
    count: int = typer.Option(1, help="Number of messages to send"),
):
    """Simulate PARTICLE_SELECTION_COMPLETE messages"""
    simulator = ExternalMessageSimulator()

    for i in range(count):
        payload = simulator.generate_particle_selection_complete(gridsquare_id, selection_ratio)
        success = simulator.publish_message("particle_selection.completed", payload)

        if success:
            console.print(f"[green]✓[/green] Published PARTICLE_SELECTION_COMPLETE {i + 1}/{count}")
            console.print(f"  Grid Square: {payload['gridsquare_id']}")
            console.print(f"  Selected: {payload['selection_results']['selected_particles']}")
        else:
            console.print(f"[red]✗[/red] Failed to publish message {i + 1}")

        if count > 1 and i < count - 1:
            time.sleep(1)


@app.command()
def gridsquare_prediction(
    gridsquare_id: str = typer.Option(None, help="Grid square ID"),
    prediction_score: float = typer.Option(None, help="Quality prediction score (0.0-1.0)"),
    count: int = typer.Option(1, help="Number of messages to send"),
):
    """Simulate GRIDSQUARE_MODEL_PREDICTION messages"""
    simulator = ExternalMessageSimulator()

    for i in range(count):
        payload = simulator.generate_gridsquare_model_prediction(gridsquare_id, prediction_score)
        success = simulator.publish_message("gridsquare.model_prediction", payload)

        if success:
            console.print(f"[green]✓[/green] Published GRIDSQUARE_MODEL_PREDICTION {i + 1}/{count}")
            console.print(f"  Grid Square: {payload['gridsquare_id']}")
            console.print(f"  Quality Score: {payload['prediction_results']['quality_score']:.3f}")
        else:
            console.print(f"[red]✗[/red] Failed to publish message {i + 1}")

        if count > 1 and i < count - 1:
            time.sleep(1)


@app.command()
def foilhole_prediction(
    gridsquare_id: str = typer.Option(None, help="Grid square ID"),
    foilhole_count: int = typer.Option(None, help="Number of foilholes to predict"),
    count: int = typer.Option(1, help="Number of messages to send"),
):
    """Simulate FOILHOLE_MODEL_PREDICTION messages"""
    simulator = ExternalMessageSimulator()

    for i in range(count):
        payload = simulator.generate_foilhole_model_prediction(gridsquare_id, foilhole_count)
        success = simulator.publish_message("foilhole.model_prediction", payload)

        if success:
            console.print(f"[green]✓[/green] Published FOILHOLE_MODEL_PREDICTION {i + 1}/{count}")
            console.print(f"  Grid Square: {payload['gridsquare_id']}")
            console.print(f"  Foilholes: {payload['prediction_summary']['total_foilholes']}")
            console.print(f"  High Quality: {payload['prediction_summary']['high_quality_count']}")
        else:
            console.print(f"[red]✗[/red] Failed to publish message {i + 1}")

        if count > 1 and i < count - 1:
            time.sleep(1)


@app.command()
def model_update(
    model_name: str = typer.Option(None, help="Model name to update"),
    count: int = typer.Option(1, help="Number of messages to send"),
):
    """Simulate MODEL_PARAMETER_UPDATE messages"""
    simulator = ExternalMessageSimulator()

    for i in range(count):
        payload = simulator.generate_model_parameter_update(model_name)
        success = simulator.publish_message("gridsquare.model_parameter_update", payload)

        if success:
            console.print(f"[green]✓[/green] Published MODEL_PARAMETER_UPDATE {i + 1}/{count}")
            console.print(f"  Model: {payload['model_name']}")
            console.print(f"  Version: {payload['model_version']}")
        else:
            console.print(f"[red]✗[/red] Failed to publish message {i + 1}")

        if count > 1 and i < count - 1:
            time.sleep(1)


@app.command()
def workflow_simulation(
    gridsquare_id: str = typer.Option("GS_001_001", help="Grid square ID for simulation"),
    delay: float = typer.Option(2.0, help="Delay between messages in seconds"),
):
    """Simulate a complete workflow for a single grid square"""
    simulator = ExternalMessageSimulator()

    console.print(f"[blue]Starting workflow simulation for {gridsquare_id}[/blue]")

    # Step 1: Motion correction
    console.print("\n[yellow]Step 1: Motion Correction[/yellow]")
    payload = simulator.generate_motion_correction_complete(gridsquare_id, 0.85)
    simulator.publish_message("motion_correction.completed", payload)
    console.print(f"Motion quality: {payload['processing_results']['motion_correction_quality']:.3f}")
    time.sleep(delay)

    # Step 2: CTF estimation
    console.print("\n[yellow]Step 2: CTF Estimation[/yellow]")
    payload = simulator.generate_ctf_complete(gridsquare_id, 3.2)
    simulator.publish_message("ctf.completed", payload)
    console.print(f"Resolution: {payload['ctf_results']['resolution_estimate']:.2f}Å")
    time.sleep(delay)

    # Step 3: Particle picking
    console.print("\n[yellow]Step 3: Particle Picking[/yellow]")
    payload = simulator.generate_particle_picking_complete(gridsquare_id, 450)
    simulator.publish_message("particle_picking.completed", payload)
    console.print(f"Particles picked: {payload['picking_results']['particles_picked']}")
    time.sleep(delay)

    # Step 4: Particle selection
    console.print("\n[yellow]Step 4: Particle Selection[/yellow]")
    payload = simulator.generate_particle_selection_complete(gridsquare_id, 0.72)
    simulator.publish_message("particle_selection.completed", payload)
    console.print(f"Selected: {payload['selection_results']['selected_particles']}")
    time.sleep(delay)

    # Step 5: Grid square prediction
    console.print("\n[yellow]Step 5: Grid Square Prediction[/yellow]")
    payload = simulator.generate_gridsquare_model_prediction(gridsquare_id, 0.88)
    simulator.publish_message("gridsquare.model_prediction", payload)
    console.print(f"Quality score: {payload['prediction_results']['quality_score']:.3f}")
    time.sleep(delay)

    # Step 6: Foilhole prediction
    console.print("\n[yellow]Step 6: Foilhole Prediction[/yellow]")
    payload = simulator.generate_foilhole_model_prediction(gridsquare_id, 12)
    simulator.publish_message("foilhole.model_prediction", payload)
    console.print(f"Foilholes predicted: {payload['prediction_summary']['total_foilholes']}")

    console.print(f"\n[green]✓ Complete workflow simulation finished for {gridsquare_id}[/green]")


@app.command()
def batch_simulation(
    gridsquare_count: int = typer.Option(5, help="Number of grid squares to simulate"),
    scenario: str = typer.Option("mixed", help="Simulation scenario: 'good', 'poor', 'mixed'"),
):
    """Simulate batch processing of multiple grid squares"""
    simulator = ExternalMessageSimulator()

    console.print(f"[blue]Starting batch simulation: {gridsquare_count} grid squares ({scenario} quality)[/blue]")

    for i in range(gridsquare_count):
        gridsquare_id = f"GS_001_{i + 1:03d}"

        # Adjust quality based on scenario
        if scenario == "good":
            quality_base = random.uniform(0.75, 0.95)
        elif scenario == "poor":
            quality_base = random.uniform(0.2, 0.5)
        else:  # mixed
            quality_base = random.uniform(0.3, 0.9)

        console.print(f"\n[cyan]Processing {gridsquare_id}[/cyan]")

        # Generate predictions that will trigger different instruction types
        if quality_base > 0.7:
            # High quality - should trigger reordering
            payload = simulator.generate_gridsquare_model_prediction(gridsquare_id, quality_base)
            simulator.publish_message("gridsquare.model_prediction", payload)
            console.print(f"  High quality ({quality_base:.3f}) - should trigger reordering")

            # Follow up with foilhole predictions
            payload = simulator.generate_foilhole_model_prediction(gridsquare_id, random.randint(8, 16))
            simulator.publish_message("foilhole.model_prediction", payload)

        elif quality_base < 0.4:
            # Poor quality - should trigger skipping
            payload = simulator.generate_gridsquare_model_prediction(gridsquare_id, quality_base)
            simulator.publish_message("gridsquare.model_prediction", payload)
            console.print(f"  Poor quality ({quality_base:.3f}) - should trigger skipping")

        else:
            # Medium quality - continue with normal processing
            payload = simulator.generate_motion_correction_complete(gridsquare_id, quality_base)
            simulator.publish_message("motion_correction.completed", payload)
            console.print(f"  Medium quality ({quality_base:.3f}) - continue processing")

        time.sleep(1)

    console.print("\n[green]✓ Batch simulation complete[/green]")


@app.command()
def list_messages():
    """List all available message types and their descriptions"""
    table = Table(title="Available External Message Types")
    table.add_column("Message Type", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Triggers", style="yellow")

    table.add_row(
        "motion_correction.completed", "Motion correction processing finished", "Quality assessment decisions"
    )
    table.add_row("ctf.completed", "CTF estimation completed", "Resolution-based filtering")
    table.add_row("particle_picking.completed", "Particle identification finished", "Density evaluation")
    table.add_row("particle_selection.completed", "Particle quality assessment done", "Selection ratio decisions")
    table.add_row("gridsquare.model_prediction", "ML prediction for grid square quality", "Reorder/skip grid squares")
    table.add_row("foilhole.model_prediction", "ML prediction for foilhole targeting", "Reorder foilholes")
    table.add_row("gridsquare.model_parameter_update", "ML model parameter updates", "Threshold adjustments")

    console.print(table)


if __name__ == "__main__":
    app()
