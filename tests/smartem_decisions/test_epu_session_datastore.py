import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.epu_data_intake.data_model import EpuSession


class TestEpuSessionGetGridByPath(unittest.TestCase):

    def setUp(self):
        # Set up a mock EntityStore for our tests
        self.mock_store = {}

        # Patch the EntityStore class
        self.patcher = patch('epu_data_intake.data_model.EntityStore', return_value=self.mock_store)
        self.mock_entity_store = self.patcher.start()

        # Create the EpuSession with a temp root dir
        self.session = EpuSession(root_dir="/temp/epu_root")

        # Create mock grid objects with data_dir and atlas_dir attributes
        self.grid1 = MagicMock()
        self.grid1.data_dir = Path("/temp/epu_root/grid1/data")
        self.grid1.atlas_dir = Path("/temp/epu_root/grid1/atlas")

        self.grid2 = MagicMock()
        self.grid2.data_dir = Path("/temp/epu_root/grid2/data")
        self.grid2.atlas_dir = Path("/temp/epu_root/grid2/atlas")

        # Add grids to the mock store
        self.mock_store["grid1"] = self.grid1
        self.mock_store["grid2"] = self.grid2

        # Make items() method return the test data
        self.session.grids.items = MagicMock(return_value=self.mock_store.items())

    def tearDown(self):
        # Stop the patcher
        self.patcher.stop()

    def test_get_grid_by_path_finds_grid_in_data_dir(self):
        # Test a path in grid1's data_dir
        path = "/temp/epu_root/grid1/data/file.mrc"
        result = self.session.get_grid_by_path(path)
        self.assertEqual(result, "grid1")

    def test_get_grid_by_path_finds_grid_in_atlas_dir(self):
        # Test a path in grid2's atlas_dir
        path = "/temp/epu_root/grid2/atlas/atlas.xml"
        result = self.session.get_grid_by_path(path)
        self.assertEqual(result, "grid2")

    def test_get_grid_by_path_with_nested_paths(self):
        # Test a deeply nested path
        path = "/temp/epu_root/grid1/data/subfolder/deep/file.mrc"
        result = self.session.get_grid_by_path(path)
        self.assertEqual(result, "grid1")

    def test_get_grid_by_path_returns_none_for_no_match(self):
        # Test a path that isn't in any grid's directories
        path = "/temp/epu_root/other/random/file.txt"
        result = self.session.get_grid_by_path(path)
        self.assertIsNone(result)

    def test_get_grid_by_path_with_similar_prefix(self):
        # Test a path that has a similar prefix but isn't actually in the directory
        path = "/temp/epu_root/grid1/data_extra/file.mrc"  # Note the 'data_extra' instead of 'data'
        result = self.session.get_grid_by_path(path)
        self.assertIsNone(result)

    @patch('logging.Logger.debug')
    def test_logging_when_no_grid_found(self, mock_debug):
        # Test that we log a debug message when no grid is found
        path = "/temp/nonexistent/path"
        result = self.session.get_grid_by_path(path)
        self.assertIsNone(result)
        mock_debug.assert_called_once_with(f"No grid found for path: {path}")


if __name__ == '__main__':
    unittest.main()
