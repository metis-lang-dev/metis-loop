# Ruling: accepted

**planner**, yield_red; the program unit planner/planner.llp.

## The receipt
Programs moved: planner, ei_key holds.

## The fired diff
- First enabled: tick 120, yield_red[Z=z1], beside accel.
- First fired difference: tick 120, planner: the record ['accel'], the candidate ['yield_red[Z=z1]'].
- First differing output: tick 120, planner: the record ['accel'], the candidate [].
- First difference per member: planner at 120, road_director at 121.

## The cases
- surprise.yaml (planner, tick 120): passes in the package's harness; passes on the composition.

## The goldens
11 cases (planner 9, responder 2), none broken, on seeds 1 to 3.

## The certificate
**Open-loop:** every tick of the trace to its first differing output (tick 120), and past it only as a world that obeyed the old command.
**Closed-loop:** not run. This ruling has no world.

## The model's words
(no model was asked: the verdict and the evidence above stand alone)

A person reviews this. Spend: 0.0000 USD.
