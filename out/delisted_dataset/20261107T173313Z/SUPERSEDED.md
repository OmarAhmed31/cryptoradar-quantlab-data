# SUPERSEDED — do not consume this run

This first build still contains `hourly/USDC-USDT.csv.gz`. USDC-USDT is **not** a delisted pair (ledger correction #2).

The authoritative dataset is **`out/delisted_dataset/20261107T192715Z_rebuild/`**. It was rebuilt offline from this run's raw files: all 2,055 were verified against their sha256 first. Its `hourly/` folder contains exactly the 141 dataset pairs. The 141 hourly files are byte-identical to the ones here once decompressed.

This run is kept only as a record. Its raw files are in GitHub release `delisted-raw-20261107T173313Z`.
