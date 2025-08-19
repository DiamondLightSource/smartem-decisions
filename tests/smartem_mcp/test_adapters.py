"""
Tests for SmartEM MCP adapters (filesystem and API)
"""

from pathlib import Path

import pytest

from smartem_mcp.server import FilesystemAdapter


@pytest.mark.asyncio
async def test_filesystem_adapter_parse_epu_directory():
    """Test filesystem adapter with EPU directory parsing"""
    adapter = FilesystemAdapter()

    # Use test dataset - adjust path as needed for CI/testing
    test_datasets_dir = Path(__file__).parent.parent.parent / "smartem-decisions-test-datasets"
    test_path = test_datasets_dir / "bi37708-28-copy" / "Supervisor_20250129_134723_36_bi37708-28_grid7_EPU"

    if not test_path.exists():
        pytest.skip(f"Test dataset not found at {test_path}")

    result = await adapter.parse_epu_directory(str(test_path))

    assert result.success is True
    assert result.source == "filesystem"
    assert result.data is not None
    assert "grid_count" in result.data
    assert "grids" in result.data
    assert result.data["grid_count"] > 0


@pytest.mark.asyncio
async def test_filesystem_adapter_invalid_path():
    """Test filesystem adapter with invalid path"""
    adapter = FilesystemAdapter()

    result = await adapter.parse_epu_directory("/nonexistent/path")

    assert result.success is False
    assert result.source == "filesystem"
    assert "does not exist" in result.error


@pytest.mark.asyncio
async def test_filesystem_adapter_quality_metrics():
    """Test filesystem adapter quality metrics query"""
    adapter = FilesystemAdapter()

    test_datasets_dir = Path(__file__).parent.parent.parent / "smartem-decisions-test-datasets"
    test_path = test_datasets_dir / "bi37708-28-copy" / "Supervisor_20250129_134723_36_bi37708-28_grid7_EPU"

    if not test_path.exists():
        pytest.skip(f"Test dataset not found at {test_path}")

    result = await adapter.query_quality_metrics(str(test_path), threshold=0.5)

    assert result.success is True
    assert result.source == "filesystem"
    assert result.data is not None
    assert "threshold" in result.data
    assert "low_quality_items" in result.data
    assert result.data["threshold"] == 0.5
