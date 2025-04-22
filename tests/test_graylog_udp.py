# This is the simplest possible test to verify Graylog UDP is receiving (don't forget to set up an input node!)

import logging
import graypy

# Configure the logger
logger = logging.getLogger("test_logger")
logger.setLevel(logging.DEBUG)

# Create graylog handler
handler = graypy.GELFUDPHandler("localhost", 12201)
logger.addHandler(handler)

# Add a console handler too for local verification
console = logging.StreamHandler()
logger.addHandler(console)

# Send some test messages
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
