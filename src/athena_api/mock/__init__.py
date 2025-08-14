"""Athena API mock server for testing and development."""

# Mock server is only available with optional dependencies
try:
    from .server import AthenaAPIServer

    __all__ = ["AthenaAPIServer"]
except ImportError:
    # Provide helpful error message if optional dependencies aren't installed
    def _missing_deps(*args, **kwargs):
        raise ImportError(
            "Mock server dependencies not installed. Install with: pip install 'smartem-decisions[mock]'"
        ) from None

    AthenaAPIServer = _missing_deps
    __all__ = ["AthenaAPIServer"]
