# Merged Discovery Measurement Summary

Generated solely from validated append-only JSONL rows.

## Evidence qualification

- Complete physical fleet pairs: 36.
- Fleet evidence: `representative` and `repeated_rounds`.
- Emulator evidence: `synthetic_mdns_lower_bound` and `single_round`; it is a synthetic mDNS lower bound, not representative fleet evidence.
- Exact measured fleet implementation revision: `1abe9902b4a20f290d33af6189eb2c1c66dab5e4, 23a9f62bbb961b21e87062f76c89931e3c8da27b, 39bad58c42627ac3612868503bb5fb9305b04cc3, 650dbd2c889e4874f0221da4981feab43d524951, 8ddb5ea5a93328fc2f668caad8533d15cdfab2a5, ed2035fb5a75bedb180d43d3edbc29e58ce999fa`.
- Fleet quiescence: `not_quiesced`.
- Fleet confounds: `background_pollers, busy_network, wireless_interference`.
- Fleet baseline-count variance: `variable_baseline_counts` (advisory only; no pass/fail threshold).
- FIND-08 disposition: `no_eligible_find08_population`; missing eligible physical WiFi population is a non-gating gap.
- The mDNS liveness concurrency cap of 16 is a reasoned D-07 safety bound, not a measured optimum.

## Pair deltas

Deltas are merged minus direct-UDP baseline observations.

| Scenario | Pair | Round | Environment | Completion delta ns | First-result delta ns | Unique delta |
|---|---|---:|---|---:|---:|---:|
| emulator-1abe9902b4a2-8b51026b6fd6 | emulator-1abe9902b4a2-8b51026b6fd6-round-1 | 1 | emulator | +3838251 | +2836834 | +0 |
| emulator-23a9f62bbb96-44ef15e16457 | emulator-23a9f62bbb96-44ef15e16457-round-1 | 1 | emulator | +3220501 | +3790625 | +0 |
| emulator-39bad58c4262-ecb92d9f541e | emulator-39bad58c4262-ecb92d9f541e-round-1 | 1 | emulator | +21792 | +522292 | +0 |
| emulator-650dbd2c889e-2f741144ffbd | emulator-650dbd2c889e-2f741144ffbd-round-1 | 1 | emulator | +8652750 | +5027041 | +0 |
| emulator-8ddb5ea5a933-716240f12b9f | emulator-8ddb5ea5a933-716240f12b9f-round-1 | 1 | emulator | +1041999 | -130708 | +0 |
| emulator-ed2035fb5a75-3f938a35f4cd | emulator-ed2035fb5a75-3f938a35f4cd-round-1 | 1 | emulator | +1199000 | +558041 | +0 |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-1 | 1 | fleet | -227328291 | -3903042 | +13 |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-2 | 2 | fleet | -22183584 | -3126250 | +12 |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-3 | 3 | fleet | -100407250 | +3600041 | +6 |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-4 | 4 | fleet | +84265916 | +10268166 | +20 |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-5 | 5 | fleet | +28379374 | +4014374 | +17 |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-6 | 6 | fleet | +12376000 | -5046542 | +4 |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-1 | 1 | fleet | +59590584 | +5498167 | +14 |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-2 | 2 | fleet | -272988958 | +2398834 | +16 |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-3 | 3 | fleet | -301599416 | -4341875 | +6 |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-4 | 4 | fleet | -78257709 | +4931499 | +15 |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-5 | 5 | fleet | -915078709 | +759958 | +6 |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-6 | 6 | fleet | -226276167 | -65876 | +8 |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-1 | 1 | fleet | +33903500 | -6165041 | +8 |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-2 | 2 | fleet | -119789000 | +21363833 | +9 |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-3 | 3 | fleet | -387872875 | +2627958 | +4 |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-4 | 4 | fleet | -38599416 | -7403124 | +17 |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-5 | 5 | fleet | +15724332 | -5867417 | +10 |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-6 | 6 | fleet | -183856042 | -7871458 | +4 |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-1 | 1 | fleet | -232198375 | -7437708 | +9 |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-2 | 2 | fleet | -224221667 | -838334 | +11 |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-3 | 3 | fleet | +28633291 | -2208208 | +6 |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-4 | 4 | fleet | -12586417 | -5385708 | +8 |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-5 | 5 | fleet | -47361208 | +5066751 | +5 |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-6 | 6 | fleet | +32481416 | +893625 | +10 |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-1 | 1 | fleet | -133080083 | -810749 | +12 |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-2 | 2 | fleet | -193309499 | +14448792 | +10 |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-3 | 3 | fleet | -319003625 | +15006833 | +6 |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-4 | 4 | fleet | -169146125 | -4950959 | +16 |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-5 | 5 | fleet | -48349000 | +3408541 | -1 |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-6 | 6 | fleet | -37291000 | -10740500 | +3 |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-1 | 1 | fleet | -326353625 | +16584 | +14 |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-2 | 2 | fleet | -68115375 | +562042 | +5 |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-3 | 3 | fleet | -117649042 | +3509541 | +3 |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-4 | 4 | fleet | -475998543 | -7592625 | +5 |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-5 | 5 | fleet | -370534042 | -14613750 | +10 |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-6 | 6 | fleet | -46837333 | -5478708 | +8 |

## Raw observations

Source counts are alias-only contributions from each exact timed call.

| Scenario | Pair | Round | Arm | Elapsed ns | First result ns | Unique | UDP | mDNS | Overlap | UDP wins | mDNS wins | Qualification |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| emulator-1abe9902b4a2-8b51026b6fd6 | emulator-1abe9902b4a2-8b51026b6fd6-round-1 | 1 | baseline | 11604271166 | 102731583 | 2 | 2 | 0 | 0 | 2 | 0 | clean |
| emulator-1abe9902b4a2-8b51026b6fd6 | emulator-1abe9902b4a2-8b51026b6fd6-round-1 | 1 | merged | 11608109417 | 105568417 | 2 | 2 | 1 | 1 | 1 | 1 | clean |
| emulator-23a9f62bbb96-44ef15e16457 | emulator-23a9f62bbb96-44ef15e16457-round-1 | 1 | baseline | 11604750666 | 103700375 | 2 | 2 | 0 | 0 | 2 | 0 | clean |
| emulator-23a9f62bbb96-44ef15e16457 | emulator-23a9f62bbb96-44ef15e16457-round-1 | 1 | merged | 11607971167 | 107491000 | 2 | 2 | 1 | 1 | 1 | 1 | clean |
| emulator-39bad58c4262-ecb92d9f541e | emulator-39bad58c4262-ecb92d9f541e-round-1 | 1 | baseline | 11603650167 | 102646875 | 2 | 2 | 0 | 0 | 2 | 0 | clean |
| emulator-39bad58c4262-ecb92d9f541e | emulator-39bad58c4262-ecb92d9f541e-round-1 | 1 | merged | 11603671959 | 103169167 | 2 | 2 | 1 | 1 | 1 | 1 | clean |
| emulator-650dbd2c889e-2f741144ffbd | emulator-650dbd2c889e-2f741144ffbd-round-1 | 1 | baseline | 11605248084 | 102992834 | 2 | 2 | 0 | 0 | 2 | 0 | clean |
| emulator-650dbd2c889e-2f741144ffbd | emulator-650dbd2c889e-2f741144ffbd-round-1 | 1 | merged | 11613900834 | 108019875 | 2 | 2 | 1 | 1 | 1 | 1 | clean |
| emulator-8ddb5ea5a933-716240f12b9f | emulator-8ddb5ea5a933-716240f12b9f-round-1 | 1 | baseline | 11603367834 | 103114000 | 2 | 2 | 0 | 0 | 2 | 0 | clean |
| emulator-8ddb5ea5a933-716240f12b9f | emulator-8ddb5ea5a933-716240f12b9f-round-1 | 1 | merged | 11604409833 | 102983292 | 2 | 2 | 1 | 1 | 1 | 1 | clean |
| emulator-c484a023f419-2f6caf206d92 | emulator-c484a023f419-2f6caf206d92-round-1 | 1 | baseline | 11604683917 | 103729958 | 2 | 2 | 0 | 0 | 2 | 0 | clean |
| emulator-ed2035fb5a75-3f938a35f4cd | emulator-ed2035fb5a75-3f938a35f4cd-round-1 | 1 | baseline | 11602815958 | 102108042 | 2 | 2 | 0 | 0 | 2 | 0 | clean |
| emulator-ed2035fb5a75-3f938a35f4cd | emulator-ed2035fb5a75-3f938a35f4cd-round-1 | 1 | merged | 11604014958 | 102666083 | 2 | 2 | 1 | 1 | 1 | 1 | clean |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-1 | 1 | baseline | 15237967583 | 169726250 | 35 | 35 | 0 | 0 | 35 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-1 | 1 | merged | 15010639292 | 165823208 | 48 | 41 | 24 | 17 | 34 | 14 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-2 | 2 | baseline | 15087429042 | 164265125 | 41 | 41 | 0 | 0 | 41 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-2 | 2 | merged | 15065245458 | 161138875 | 53 | 46 | 20 | 13 | 42 | 11 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-3 | 3 | baseline | 15103233042 | 170196792 | 43 | 43 | 0 | 0 | 43 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-3 | 3 | merged | 15002825792 | 173796833 | 49 | 42 | 18 | 11 | 42 | 7 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-4 | 4 | baseline | 15019078750 | 168969625 | 35 | 35 | 0 | 0 | 35 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-4 | 4 | merged | 15103344666 | 179237791 | 55 | 48 | 24 | 17 | 42 | 13 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-5 | 5 | baseline | 15010311917 | 165942292 | 35 | 35 | 0 | 0 | 35 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-5 | 5 | merged | 15038691291 | 169956666 | 52 | 42 | 24 | 14 | 37 | 15 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-6 | 6 | baseline | 15035894917 | 169013250 | 50 | 50 | 0 | 0 | 50 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-1abe9902b4a2-0be7f1eee236 | fleet-1abe9902b4a2-0be7f1eee236-round-6 | 6 | merged | 15048270917 | 163966708 | 54 | 47 | 24 | 17 | 39 | 15 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-1 | 1 | baseline | 15030931791 | 169479083 | 32 | 32 | 0 | 0 | 32 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-1 | 1 | merged | 15090522375 | 174977250 | 46 | 40 | 23 | 17 | 34 | 12 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-2 | 2 | baseline | 15274657125 | 169457208 | 31 | 31 | 0 | 0 | 31 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-2 | 2 | merged | 15001668167 | 171856042 | 47 | 41 | 18 | 12 | 41 | 6 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-3 | 3 | baseline | 15303700750 | 172264750 | 42 | 42 | 0 | 0 | 42 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-3 | 3 | merged | 15002101334 | 167922875 | 48 | 42 | 19 | 13 | 42 | 6 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-4 | 4 | baseline | 15081799875 | 169336709 | 35 | 35 | 0 | 0 | 35 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-4 | 4 | merged | 15003542166 | 174268208 | 50 | 43 | 23 | 16 | 41 | 9 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-5 | 5 | baseline | 15917903000 | 169964125 | 35 | 35 | 0 | 0 | 35 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-5 | 5 | merged | 15002824291 | 170724083 | 41 | 35 | 11 | 5 | 35 | 6 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-6 | 6 | baseline | 15229977125 | 170603417 | 38 | 38 | 0 | 0 | 38 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-23a9f62bbb96-5d6fa0d45c93 | fleet-23a9f62bbb96-5d6fa0d45c93-round-6 | 6 | merged | 15003700958 | 170537541 | 46 | 40 | 23 | 17 | 35 | 11 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-1 | 1 | baseline | 15023589167 | 169449583 | 38 | 38 | 0 | 0 | 38 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-1 | 1 | merged | 15057492667 | 163284542 | 46 | 40 | 23 | 17 | 38 | 8 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-2 | 2 | baseline | 15219196792 | 149045417 | 39 | 39 | 0 | 0 | 39 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-2 | 2 | merged | 15099407792 | 170409250 | 48 | 42 | 22 | 16 | 37 | 11 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-3 | 3 | baseline | 15400371916 | 169478958 | 33 | 33 | 0 | 0 | 33 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-3 | 3 | merged | 15012499041 | 172106916 | 37 | 30 | 18 | 11 | 24 | 13 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-4 | 4 | baseline | 15122074125 | 165243166 | 33 | 33 | 0 | 0 | 33 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-4 | 4 | merged | 15083474709 | 157840042 | 50 | 43 | 23 | 16 | 37 | 13 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-5 | 5 | baseline | 15059886334 | 167465042 | 38 | 38 | 0 | 0 | 38 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-5 | 5 | merged | 15075610666 | 161597625 | 48 | 42 | 23 | 17 | 37 | 11 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-6 | 6 | baseline | 15278648375 | 170244333 | 42 | 42 | 0 | 0 | 42 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-39bad58c4262-9c211057e08d | fleet-39bad58c4262-9c211057e08d-round-6 | 6 | merged | 15094792333 | 162372875 | 46 | 40 | 23 | 17 | 37 | 9 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-1 | 1 | baseline | 15321444333 | 169773708 | 40 | 40 | 0 | 0 | 40 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-1 | 1 | merged | 15089245958 | 162336000 | 49 | 43 | 23 | 17 | 41 | 8 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-2 | 2 | baseline | 15300146833 | 168746000 | 41 | 41 | 0 | 0 | 41 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-2 | 2 | merged | 15075925166 | 167907666 | 52 | 46 | 22 | 16 | 46 | 6 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-3 | 3 | baseline | 15047932584 | 171116875 | 43 | 43 | 0 | 0 | 43 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-3 | 3 | merged | 15076565875 | 168908667 | 49 | 43 | 21 | 15 | 39 | 10 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-4 | 4 | baseline | 15031683459 | 167381542 | 40 | 40 | 0 | 0 | 40 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-4 | 4 | merged | 15019097042 | 161995834 | 48 | 42 | 23 | 17 | 36 | 12 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-5 | 5 | baseline | 15114227417 | 166635208 | 42 | 42 | 0 | 0 | 42 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-5 | 5 | merged | 15066866209 | 171701959 | 47 | 41 | 17 | 11 | 41 | 6 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-6 | 6 | baseline | 15047371667 | 167946250 | 39 | 39 | 0 | 0 | 39 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-650dbd2c889e-6ea4cf21b655 | fleet-650dbd2c889e-6ea4cf21b655-round-6 | 6 | merged | 15079853083 | 168839875 | 49 | 43 | 23 | 17 | 35 | 14 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-1 | 1 | baseline | 15134186708 | 168859708 | 37 | 37 | 0 | 0 | 37 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-1 | 1 | merged | 15001106625 | 168048959 | 49 | 39 | 23 | 13 | 37 | 12 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-2 | 2 | baseline | 15194313291 | 161309125 | 38 | 38 | 0 | 0 | 38 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-2 | 2 | merged | 15001003792 | 175757917 | 48 | 38 | 23 | 13 | 35 | 13 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-3 | 3 | baseline | 15322903500 | 167254209 | 38 | 38 | 0 | 0 | 38 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-3 | 3 | merged | 15003899875 | 182261042 | 44 | 38 | 21 | 15 | 32 | 12 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-4 | 4 | baseline | 15171670042 | 159356292 | 36 | 36 | 0 | 0 | 36 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-4 | 4 | merged | 15002523917 | 154405333 | 52 | 46 | 23 | 17 | 45 | 7 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-5 | 5 | baseline | 15051295334 | 169960209 | 45 | 45 | 0 | 0 | 45 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-5 | 5 | merged | 15002946334 | 173368750 | 44 | 38 | 19 | 13 | 34 | 10 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-6 | 6 | baseline | 15039378250 | 171053125 | 43 | 43 | 0 | 0 | 43 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-8ddb5ea5a933-f43a2dd62938 | fleet-8ddb5ea5a933-f43a2dd62938-round-6 | 6 | merged | 15002087250 | 160312625 | 46 | 40 | 16 | 10 | 40 | 6 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-1 | 1 | baseline | 15327900000 | 165962916 | 37 | 37 | 0 | 0 | 37 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-1 | 1 | merged | 15001546375 | 165979500 | 51 | 43 | 24 | 16 | 38 | 13 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-2 | 2 | baseline | 15070024500 | 165833333 | 45 | 45 | 0 | 0 | 45 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-2 | 2 | merged | 15001909125 | 166395375 | 50 | 43 | 24 | 17 | 37 | 13 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-3 | 3 | baseline | 15119531667 | 169298334 | 38 | 38 | 0 | 0 | 38 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-3 | 3 | merged | 15001882625 | 172807875 | 41 | 33 | 24 | 16 | 22 | 19 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-4 | 4 | baseline | 15477047709 | 169400000 | 37 | 37 | 0 | 0 | 37 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-4 | 4 | merged | 15001049166 | 161807375 | 42 | 35 | 20 | 13 | 32 | 10 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-5 | 5 | baseline | 15372171459 | 174396375 | 38 | 38 | 0 | 0 | 38 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-5 | 5 | merged | 15001637417 | 159782625 | 48 | 40 | 21 | 13 | 39 | 9 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-6 | 6 | baseline | 15047801708 | 166671708 | 36 | 36 | 0 | 0 | 36 | 0 | confounded (background_pollers, wireless_interference, busy_network) |
| fleet-ed2035fb5a75-da80260dbd91 | fleet-ed2035fb5a75-da80260dbd91-round-6 | 6 | merged | 15000964375 | 161193000 | 44 | 37 | 12 | 5 | 37 | 7 | confounded (background_pollers, wireless_interference, busy_network) |
