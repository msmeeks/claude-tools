# wenyan-ultra handoff validation report

Cost/token/latency/drift comparison of baseline (plain-prose Phase 3/4) vs. wenyan-ultra-enabled sdlc review runs across a 10-PR corpus (claude-tools + bible-flashcards, both public repos), each (PR, mode) pair run 2x to estimate run-to-run noise. Baseline runs execute against a disposable git worktree with a plain-prose Phase 3/4 SKILL.md variant — the real repo checkout is never mutated. Metrics are real billed API usage (`--output-format json`), not a word count. No raw diff content or PII/secret values are reproduced below.

---

## PR corpus

- `claude-tools#14` — small
- `claude-tools#15` — small
- `bible-flashcards#52` — small
- `bible-flashcards#57` — small
- `claude-tools#12` — medium
- `bible-flashcards#62` — medium
- `bible-flashcards#33` — medium
- `claude-tools#7` — large
- `claude-tools#8` — large
- `bible-flashcards#35` — large

---

## Per-PR results

### `claude-tools#14`

- baseline rep 1: cost_usd=1.7065078499999993, input=141, cache_read=402263, cache_write=10915, output=6990, latency_s=358.267
- baseline rep 2: cost_usd=0.3013923, input=6009, cache_read=230691, cache_write=31687, output=1562, latency_s=28.205
- wenyan rep 1: cost_usd=0.21745179999999997, input=6005, cache_read=120726, cache_write=24023, output=1231, latency_s=23.949
- wenyan rep 2: cost_usd=0.1281081, input=6003, cache_read=100887, cache_write=7472, output=2293, latency_s=36.558
- drift mismatches: 0
- ship (this PR independently): True

### `claude-tools#15`

- baseline rep 1: cost_usd=0.20098720000000003, input=6005, cache_read=119934, cache_write=22816, output=632, latency_s=15.563
- baseline rep 2: cost_usd=0.1769568, input=6003, cache_read=83626, cache_write=21229, output=392, latency_s=13.678
- wenyan rep 1: cost_usd=0.41239210000000004, input=6148, cache_read=433447, cache_write=28518, output=6146, latency_s=91.376
- wenyan rep 2: cost_usd=0.3795503999999999, input=6150, cache_read=506558, cache_write=19647, output=6043, latency_s=81.772
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#52`

- baseline rep 1: cost_usd=0.18089319999999998, input=6003, cache_read=83594, cache_write=21323, output=616, latency_s=12.829
- baseline rep 2: cost_usd=0.2167059, input=6005, cache_read=121033, cache_write=23443, output=1407, latency_s=28.49
- wenyan rep 1: cost_usd=0.5990247, input=6162, cache_read=871659, cache_write=37638, output=6172, latency_s=106.538
- wenyan rep 2: cost_usd=0.2368749, input=6146, cache_read=373943, cache_write=10656, output=2780, latency_s=48.756
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#57`

- baseline rep 1: cost_usd=0.2494806, input=6009, cache_read=198452, cache_write=24090, output=1784, latency_s=29.036
- baseline rep 2: cost_usd=0.24587789999999998, input=6009, cache_read=199063, cache_write=24099, output=1527, latency_s=24.427
- wenyan rep 1: cost_usd=0.3514563, input=6146, cache_read=424551, cache_write=28730, output=2177, latency_s=47.019
- wenyan rep 2: cost_usd=0.11275279999999999, input=6003, cache_read=100856, cache_write=5814, output=1931, latency_s=30.234
- drift mismatches: 0
- ship (this PR independently): True

### `claude-tools#12`

- baseline rep 1: cost_usd=0.2313506, input=6009, cache_read=197092, cache_write=23275, output=928, latency_s=19.888
- baseline rep 2: cost_usd=0.2128312, input=6007, cache_read=158414, cache_write=23035, output=564, latency_s=16.162
- wenyan rep 1: cost_usd=0.6549324, input=6295, cache_read=917508, cache_write=42269, output=7105, latency_s=119.417
- wenyan rep 2: cost_usd=3.5379642500000004, input=8, cache_read=410132, cache_write=6105, output=2808, latency_s=655.349
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#62`

- baseline rep 1: cost_usd=0.2726033, input=6011, cache_read=237731, cache_write=24688, output=2299, latency_s=46.202
- baseline rep 2: cost_usd=0.1845047, input=6003, cache_read=83709, cache_write=21445, output=805, latency_s=14.442
- wenyan rep 1: cost_usd=0.15353869999999997, input=6003, cache_read=89509, cache_write=15739, output=907, latency_s=14.878
- wenyan rep 2: cost_usd=0.2030176, input=6011, cache_read=256952, cache_write=11066, output=2726, latency_s=42.512
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#33`

- baseline rep 1: cost_usd=0.24358959999999993, input=6011, cache_read=235262, cache_write=23435, output=917, latency_s=20.613
- baseline rep 2: cost_usd=0.1955466, input=5991, cache_read=84282, cache_write=22226, output=1221, latency_s=20.786
- wenyan rep 1: cost_usd=0.22645969999999996, input=6007, cache_read=166229, cache_write=21222, output=2040, latency_s=30.765
- wenyan rep 2: cost_usd=0.1390326, input=6003, cache_read=101252, cache_write=6380, output=3450, latency_s=44.944
- drift mismatches: 0
- ship (this PR independently): True

### `claude-tools#7`

- baseline rep 1: cost_usd=0.48929169999999994, input=6291, cache_read=692339, cache_write=29021, output=5865, latency_s=90.451
- baseline rep 2: cost_usd=0.20339890000000002, input=6005, cache_read=120023, cache_write=22861, output=773, latency_s=17.986
- wenyan rep 1: cost_usd=0.7988213999999999, input=6309, cache_read=1287728, cache_write=36750, output=11497, latency_s=174.912
- wenyan rep 2: cost_usd=0.21914589999999998, input=6009, cache_read=227263, cache_write=15169, output=2754, latency_s=40.793
- drift mismatches: 0
- ship (this PR independently): True

### `claude-tools#8`

- baseline rep 1: cost_usd=0.17761310000000002, input=6003, cache_read=83597, cache_write=21234, output=435, latency_s=10.962
- baseline rep 2: cost_usd=0.23089649999999998, input=6009, cache_read=197155, cache_write=23377, output=857, latency_s=16.775
- wenyan rep 1: cost_usd=1.1068878, input=6595, cache_read=2204666, cache_write=46532, output=9726, latency_s=160.867
- wenyan rep 2: cost_usd=0.1008579, input=6003, cache_read=100623, cache_write=5962, output=1126, latency_s=20.296
- drift mismatches: 0
- ship (this PR independently): True

### `bible-flashcards#35`

- baseline rep 1: cost_usd=0.1715119, input=4399, cache_read=47123, cache_write=21435, output=997, latency_s=15.054
- baseline rep 2: cost_usd=0.1630748, input=4399, cache_read=47126, cache_write=21202, output=526, latency_s=8.889
- wenyan rep 1: cost_usd=0.25709020000000005, input=6007, cache_read=172544, cache_write=21498, output=3847, latency_s=51.846
- wenyan rep 2: cost_usd=0.1713162, input=6005, cache_read=152274, cache_write=14531, output=1321, latency_s=30.018
- drift mismatches: 0
- ship (this PR independently): True

---

## Cost & Token Analysis

- `bible-flashcards#52`: baseline_mean=$0.1988, wenyan_mean=$0.4179, ratio=2.10, noise_floor(stdev)_baseline=$0.0179, noise_floor(stdev)_wenyan=$0.1811
- `bible-flashcards#57`: baseline_mean=$0.2477, wenyan_mean=$0.2321, ratio=0.94, noise_floor(stdev)_baseline=$0.0018, noise_floor(stdev)_wenyan=$0.1194
- `claude-tools#12`: baseline_mean=$0.2221, wenyan_mean=$2.0964, ratio=9.44, noise_floor(stdev)_baseline=$0.0093, noise_floor(stdev)_wenyan=$1.4415
- `claude-tools#14`: baseline_mean=$1.0040, wenyan_mean=$0.1728, ratio=0.17, noise_floor(stdev)_baseline=$0.7026, noise_floor(stdev)_wenyan=$0.0447
- `claude-tools#15`: baseline_mean=$0.1890, wenyan_mean=$0.3960, ratio=2.10, noise_floor(stdev)_baseline=$0.0120, noise_floor(stdev)_wenyan=$0.0164
- `bible-flashcards#62`: baseline_mean=$0.2286, wenyan_mean=$0.1783, ratio=0.78, noise_floor(stdev)_baseline=$0.0440, noise_floor(stdev)_wenyan=$0.0247
- `bible-flashcards#33`: baseline_mean=$0.2196, wenyan_mean=$0.1827, ratio=0.83, noise_floor(stdev)_baseline=$0.0240, noise_floor(stdev)_wenyan=$0.0437
- `claude-tools#7`: baseline_mean=$0.3463, wenyan_mean=$0.5090, ratio=1.47, noise_floor(stdev)_baseline=$0.1429, noise_floor(stdev)_wenyan=$0.2898
- `claude-tools#8`: baseline_mean=$0.2043, wenyan_mean=$0.6039, ratio=2.96, noise_floor(stdev)_baseline=$0.0266, noise_floor(stdev)_wenyan=$0.5030
- `bible-flashcards#35`: baseline_mean=$0.1673, wenyan_mean=$0.2142, ratio=1.28, noise_floor(stdev)_baseline=$0.0042, noise_floor(stdev)_wenyan=$0.0429

**Sign test** on the 10 paired per-PR cost deltas (wenyan vs. baseline, ties dropped): 6 PRs more expensive under wenyan, 4 cheaper, two-sided p=0.7539.

---

## Verdict

**SHIP** — bar is 0 substantive drift mismatches on every PR independently (not corpus-averaged).

---

## Privacy note

Sourced from claude-tools and bible-flashcards (both public). No third-party production user data is reproduced verbatim in this report; any secret- or PII-shaped string surfaced during either run was redacted.
