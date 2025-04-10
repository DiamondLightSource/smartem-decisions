#!/usr/bin/env bash

# flush the DB
python -m smartem_decisions.model.database

#python -m smartem_decisions.simulate_msg --help
#python -m smartem_decisions.simulate_msg rogue-message
#python -m smartem_decisions.simulate_msg rogue-message --no-event-type-missing

python -m smartem_decisions.simulate_msg acquisition-start
#python -m smartem_decisions.simulate_msg acquisition-start --no-legit
sleep 1

python -m smartem_decisions.simulate_msg grid-scan-start
#python -m smartem_decisions.simulate_msg grid-scan-start --no-legit
sleep 3

python -m smartem_decisions.simulate_msg grid-scan-complete
#python -m smartem_decisions.simulate_msg grid-scan-complete --no-legit
sleep 1

python -m smartem_decisions.simulate_msg grid-squares-decision-start
#python -m smartem_decisions.simulate_msg grid-squares-decision-start --no-legit
sleep 3

python -m smartem_decisions.simulate_msg grid-squares-decision-complete
#python -m smartem_decisions.simulate_msg grid-squares-decision-complete --no-legit
sleep 2

python -m smartem_decisions.simulate_msg foil-holes-detected
#python -m smartem_decisions.simulate_msg foil-holes-detected --no-legit
sleep 1

python -m smartem_decisions.simulate_msg foil-holes-decision-start
#python -m smartem_decisions.simulate_msg foil-holes-decision-start --no-legit
sleep 3

python -m smartem_decisions.simulate_msg micrographs-detected
#python -m smartem_decisions.simulate_msg micrographs-detected --no-legit
sleep 1

python -m smartem_decisions.simulate_msg foil-holes-decision-complete
#python -m smartem_decisions.simulate_msg foil-holes-decision-complete --no-legit
sleep 1

python -m smartem_decisions.simulate_msg motion-correction-start
#python -m smartem_decisions.simulate_msg motion-correction-start --no-legit
sleep 2

python -m smartem_decisions.simulate_msg motion-correction-complete
#python -m smartem_decisions.simulate_msg motion-correction-complete --no-legit
sleep 1

python -m smartem_decisions.simulate_msg ctf-start
#python -m smartem_decisions.simulate_msg ctf-complete --no-legit
sleep 2

python -m smartem_decisions.simulate_msg ctf-complete
#python -m smartem_decisions.simulate_msg ctf-complete --no-legit
sleep 1

python -m smartem_decisions.simulate_msg particle-picking-start
#python -m smartem_decisions.simulate_msg particle-picking-start --no-legit
sleep 3

python -m smartem_decisions.simulate_msg particle-picking-complete
#python -m smartem_decisions.simulate_msg particle-picking-complete --no-legit
sleep 1

python -m smartem_decisions.simulate_msg particle-selection-start
#python -m smartem_decisions.simulate_msg particle-selection-start --no-legit
sleep 3

python -m smartem_decisions.simulate_msg particle-selection-complete
#python -m smartem_decisions.simulate_msg particle-selection-complete --no-legit
sleep 1

python -m smartem_decisions.simulate_msg acquisition-end
#python -m smartem_decisions.simulate_msg acquisition-end --no-legit
