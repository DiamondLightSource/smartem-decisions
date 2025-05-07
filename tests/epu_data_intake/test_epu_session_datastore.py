import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import logging

from src.epu_data_intake.model.schemas import (
    GridData,
    AcquisitionData
)
from src.epu_data_intake.model.store import InMemoryDataStore


class TestInMemoryDataStore(unittest.TestCase):
    def setUp(self):
        # Set up a mock logger
        self.logger_patcher = patch('src.epu_data_intake.model.store.logger')
        self.mock_logger = self.logger_patcher.start()

        # Create the InMemoryDataStore with a temp root dir
        self.store = InMemoryDataStore(root_dir="/temp/epu_root")

        # Create actual grid objects with data_dir and atlas_dir attributes
        self.grid1 = GridData(
            data_dir=Path("/temp/epu_root/grid1/data"),
            atlas_dir=Path("/temp/epu_root/grid1/atlas")
        )
        self.grid1.uuid = "grid1-uuid"

        self.grid2 = GridData(
            data_dir=Path("/temp/epu_root/grid2/data"),
            atlas_dir=Path("/temp/epu_root/grid2/atlas")
        )
        self.grid2.uuid = "grid2-uuid"

        # Add grids to the store
        self.store.grids = {
            "grid1-uuid": self.grid1,
            "grid2-uuid": self.grid2
        }

        # Set up acquisition relationship
        self.store.acquisition_rels[self.store.acquisition.uuid] = {
            "grid1-uuid",
            "grid2-uuid"
        }

    def tearDown(self):
        # Stop all patchers
        self.logger_patcher.stop()

    def test_get_grid_by_path_finds_grid_in_data_dir(self):
        # Test a path in grid1's data_dir
        path = "/temp/epu_root/grid1/data/file.mrc"
        result = self.store.get_grid_by_path(path)
        self.assertEqual(result, "grid1-uuid")

    def test_get_grid_by_path_finds_grid_in_atlas_dir(self):
        # Test a path in grid2's atlas_dir
        path = "/temp/epu_root/grid2/atlas/atlas.xml"
        result = self.store.get_grid_by_path(path)
        self.assertEqual(result, "grid2-uuid")

    def test_get_grid_by_path_with_nested_paths(self):
        # Test a deeply nested path
        path = "/temp/epu_root/grid1/data/subfolder/deep/file.mrc"
        result = self.store.get_grid_by_path(path)
        self.assertEqual(result, "grid1-uuid")

    def test_get_grid_by_path_returns_none_for_no_match(self):
        # Test a path that isn't in any grid's directories
        path = "/temp/epu_root/other/random/file.txt"
        result = self.store.get_grid_by_path(path)
        self.assertIsNone(result)

    def test_get_grid_by_path_with_similar_prefix(self):
        # Test a path that has a similar prefix but isn't actually in the directory
        path = "/temp/epu_root/grid1/data_extra/file.mrc"  # Note the 'data_extra' instead of 'data'
        result = self.store.get_grid_by_path(path)
        self.assertIsNone(result)

    def test_logging_when_no_grid_found(self):
        # Test that we log a debug message when no grid is found
        path = "/temp/nonexistent/path"
        result = self.store.get_grid_by_path(path)
        self.assertIsNone(result)
        self.mock_logger.debug.assert_called_once_with(f"No grid found for path: {Path(path)}")

    def test_create_grid(self):
        # Create a new grid
        new_grid = GridData(data_dir=Path("/temp/epu_root/grid3/data"))
        new_grid.uuid = "grid3-uuid"

        # Add it to the store
        self.store.create_grid(new_grid)

        # Check that it was added to the grids dictionary
        self.assertIn("grid3-uuid", self.store.grids)
        self.assertEqual(self.store.grids["grid3-uuid"], new_grid)

        # Check that the relationship was created
        self.assertIn("grid3-uuid", self.store.acquisition_rels[self.store.acquisition.uuid])

    def test_remove_grid(self):
        # Remove an existing grid
        self.store.remove_grid("grid1-uuid")

        # Check that it was removed from the grids dictionary
        self.assertNotIn("grid1-uuid", self.store.grids)

        # Check that the relationship was removed
        self.assertNotIn("grid1-uuid", self.store.acquisition_rels[self.store.acquisition.uuid])

    def test_find_gridsquare_by_id(self):
        # Set up the gridsquares dictionary with some test data
        from src.epu_data_intake.model.schemas import GridSquareData

        gs1 = GridSquareData(id="GS1", grid_uuid="grid1-uuid")
        gs1.uuid = "gs1-uuid"

        gs2 = GridSquareData(id="GS2", grid_uuid="grid1-uuid")
        gs2.uuid = "gs2-uuid"

        self.store.gridsquares = {
            "gs1-uuid": gs1,
            "gs2-uuid": gs2
        }

        # Test finding by ID
        result = self.store.find_gridsquare_by_natural_id("GS1")
        self.assertEqual(result, gs1)

        # Test finding non-existent ID
        result = self.store.find_gridsquare_by_natural_id("NONEXISTENT")
        self.assertIsNone(result)

    def test_string_representation(self):
        # Test that the __str__ method works correctly
        import json

        string_rep = str(self.store)
        data = json.loads(string_rep)

        self.assertEqual(data["type"], "InMemoryDataStore")
        self.assertEqual(data["root_dir"], "/temp/epu_root")
        self.assertEqual(data["entities"]["grids"], 2)


class TestPersistentDataStore(unittest.TestCase):
    @patch('src.epu_data_intake.core_http_api_client.SmartEMAPIClient')
    def setUp(self, mock_api_client):
        from src.epu_data_intake.model.store import PersistentDataStore

        # Configure the mock API client
        self.mock_api_client_instance = MagicMock()
        mock_api_client.return_value = self.mock_api_client_instance

        # Create the PersistentDataStore with a temp root dir
        self.store = PersistentDataStore(root_dir="/temp/epu_root", api_url="http://test-api.com")

        # Create a grid for testing
        self.grid = GridData(data_dir=Path("/temp/epu_root/grid1/data"))
        self.grid.uuid = "grid1-uuid"

    def test_create_grid_calls_api(self):
        # Create a grid
        self.store.create_grid(self.grid)

        # Verify that the parent class method was called
        self.assertIn("grid1-uuid", self.store.grids)

        # Verify that the API client was called
        self.mock_api_client_instance.create.assert_called_once_with(
            "grid",
            "grid1-uuid",
            self.grid,
            parent=("acquisition", self.store.acquisition.uuid)
        )

    def test_update_grid_calls_api(self):
        # First create a grid
        self.store.create_grid(self.grid)

        # Reset the mock to clear the call history
        self.mock_api_client_instance.create.reset_mock()

        # Update the grid
        self.store.update_grid("grid1-uuid", self.grid)

        # Verify that the API client was called
        self.mock_api_client_instance.update.assert_called_once_with(
            "grid",
            "grid1-uuid",
            self.grid,
            parent=("acquisition", self.store.acquisition.uuid)
        )

    def test_close_calls_api_client_close(self):
        # Call the close method
        self.store.close()

        # Verify that the API client's close method was called
        self.mock_api_client_instance.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
