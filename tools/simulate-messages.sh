#!/usr/bin/env bash

python src/core/simulate_msg.py --help

python src/core/simulate_msg.py rogue-message
python src/core/simulate_msg.py rogue-message --no-event-type-missing

python src/core/simulate_msg.py motion-correction-complete
python src/core/simulate_msg.py motion-correction-complete --no-legit

python src/core/simulate_msg.py particle-picking-complete
python src/core/simulate_msg.py particle-picking-complete --no-legit

python src/core/simulate_msg.py particle-selection-complete
python src/core/simulate_msg.py particle-selection-complete --no-legit
