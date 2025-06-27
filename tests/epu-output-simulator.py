#!/usr/bin/env python

# CLI params:
# -template-dir
# -output-dir

# Single command which first writes pre-existing data, then pauses (but script doesn't exit) until
# the user either quits or continues to the next step of the script, which writes out the rest of the template data
# incrementally, throttling writes.

# - prepare output-dir: create dir if it doesn't exist, possibly empty any old contents
#   (behaviour controlled by a bool flag in CLI)
# - scan template-dir contents and split them (randomising) into pre-existing and live data imitations
#   - create a live data manifest that schedules:
#     - live data items order of writes (randomising)
#     - write groupings (files that are written together)
#     - write throttling timeouts (randomising)
# - populate output-dir with template-dir contents that will imitate pre-existing data
# - pause script
# - once resumed - follow the live data manifest and perform writes grouping, ordering
#   and scheduling as per manifest definition
# - (enhancement) smoke test: compare template-dir with output-dir and complete once they match
