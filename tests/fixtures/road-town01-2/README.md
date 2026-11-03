# road-town01-2: a committed road trace, its first segment

`seg-0.jsonl` (k 0..199, the three members responder, planner, road_director) and `checkpoints/k0.json`, copied as
they are from metis-worlds `road/tests/fixtures/sort-town01-2/trace/` at 9e2f509 (the round-3 run Town01, seed 2,
protocol 99f429e38aa3fa2c). The chat's /commands are tested on it (tests/test_chat.py, loop-chat s-f6c32d0c step 2):
`metis.trace timeline` and `blame` read a trace without the members' programs, so no road world is needed here.
