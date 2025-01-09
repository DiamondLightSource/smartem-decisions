#!/usr/bin/env bash

# flush the DB
python src/smartem_decisions/model/database.py

#python src/smartem_decisions/simulate_msg.py --help
#python src/smartem_decisions/simulate_msg.py rogue-message
#python src/smartem_decisions/simulate_msg.py rogue-message --no-event-type-missing

python src/smartem_decisions/simulate_msg.py acquisition-start
#python src/smartem_decisions/simulate_msg.py acquisition-start --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py grid-scan-start
#python src/smartem_decisions/simulate_msg.py grid-scan-start --no-legit
sleep 3

python src/smartem_decisions/simulate_msg.py grid-scan-complete
#python src/smartem_decisions/simulate_msg.py grid-scan-complete --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py grid-squares-decision-start
#python src/smartem_decisions/simulate_msg.py grid-squares-decision-start --no-legit
sleep 3

python src/smartem_decisions/simulate_msg.py grid-squares-decision-complete
#python src/smartem_decisions/simulate_msg.py grid-squares-decision-complete --no-legit
sleep 2

python src/smartem_decisions/simulate_msg.py foil-holes-detected
#python src/smartem_decisions/simulate_msg.py foil-holes-detected --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py foil-holes-decision-start
#python src/smartem_decisions/simulate_msg.py foil-holes-decision-start --no-legit
sleep 3

python src/smartem_decisions/simulate_msg.py micrographs-detected
#python src/smartem_decisions/simulate_msg.py micrographs-detected --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py foil-holes-decision-complete
#python src/smartem_decisions/simulate_msg.py foil-holes-decision-complete --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py motion-correction-start
#python src/smartem_decisions/simulate_msg.py motion-correction-start --no-legit
sleep 2

python src/smartem_decisions/simulate_msg.py motion-correction-complete
#python src/smartem_decisions/simulate_msg.py motion-correction-complete --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py ctf-start
#python src/smartem_decisions/simulate_msg.py ctf-complete --no-legit
sleep 2

python src/smartem_decisions/simulate_msg.py ctf-complete
#python src/smartem_decisions/simulate_msg.py ctf-complete --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py particle-picking-start
#python src/smartem_decisions/simulate_msg.py particle-picking-start --no-legit
sleep 3

python src/smartem_decisions/simulate_msg.py particle-picking-complete
#python src/smartem_decisions/simulate_msg.py particle-picking-complete --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py particle-selection-start
#python src/smartem_decisions/simulate_msg.py particle-selection-start --no-legit
sleep 3

python src/smartem_decisions/simulate_msg.py particle-selection-complete
#python src/smartem_decisions/simulate_msg.py particle-selection-complete --no-legit
sleep 1

python src/smartem_decisions/simulate_msg.py acquisition-end
#python src/smartem_decisions/simulate_msg.py acquisition-end --no-legit

exit 0
