# Benchmark Chart Investigation Report (2026-05-06)

## Step 1 — Trace Every Chart Number to Source
| Code | Strategy | Value (%) | Source File | Row Count | How Computed |
| --- | --- | --- | --- | --- | --- |
| ERF (amsci2) | simple | 100 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 136 strategy rows (file total=272) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'simple'` (lines 1-136); formula: `(sum(case_match) / count(rows)) * 100 = (136/136)*100`; then written as derived value into `benchmark_summary.csv` row for ERF/amsci2/simple. |
| ERF (amsci2) | hierarchical | 100 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 136 strategy rows (file total=272) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'hierarchical'` (lines 137-272); formula: `(sum(case_match) / count(rows)) * 100 = (136/136)*100`; then written as derived value into `benchmark_summary.csv` row for ERF/amsci2/hierarchical. |
| ERF (cborg) | simple | 47.0588235294 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 136 strategy rows (file total=272) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'simple'` (lines 1-136); formula: `(sum(case_match) / count(rows)) * 100 = (64/136)*100`; then written as derived value into `benchmark_summary.csv` row for ERF/cborg/simple. |
| ERF (cborg) | hierarchical | 50.7352941176 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 136 strategy rows (file total=272) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'hierarchical'` (lines 137-272); formula: `(sum(case_match) / count(rows)) * 100 = (69/136)*100`; then written as derived value into `benchmark_summary.csv` row for ERF/cborg/hierarchical. |
| PeleLMeX (amsci2_faiss0) | simple | 98.8636363636 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | 88 strategy rows (file total=176) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'simple'` (lines 1-88); formula: `(sum(case_match) / count(rows)) * 100 = (87/88)*100`; then written as derived value into `benchmark_summary.csv` row for PeleLMeX/amsci2_faiss0/simple. |
| PeleLMeX (amsci2_faiss0) | hierarchical | 13.6363636364 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | 88 strategy rows (file total=176) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'hierarchical'` (lines 89-176); formula: `(sum(case_match) / count(rows)) * 100 = (12/88)*100`; then written as derived value into `benchmark_summary.csv` row for PeleLMeX/amsci2_faiss0/hierarchical. |
| REMORA (amsci2_faiss0) | simple | 41.6666666667 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | 24 strategy rows (file total=48) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'simple'` (lines 1-24); formula: `(sum(case_match) / count(rows)) * 100 = (10/24)*100`; then written as derived value into `benchmark_summary.csv` row for REMORA/amsci2_faiss0/simple. |
| REMORA (amsci2_faiss0) | hierarchical | 41.6666666667 | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | 24 strategy rows (file total=48) | Computed from raw rows in `results.jsonl` filtered by `strategy == 'hierarchical'` (lines 25-48); formula: `(sum(case_match) / count(rows)) * 100 = (10/24)*100`; then written as derived value into `benchmark_summary.csv` row for REMORA/amsci2_faiss0/hierarchical. |

## Step 2 — File Provenance and Integrity Checks
### Source File: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl`
- Last Modified: `2026-04-30T15:08:07.503792-07:00`
- Size: `1920.96 KB`
- Row Count: `176`

Key identifier column checks:
| Column | Nulls | Blanks | Unique Values | Top Frequency | Top Value (preview) |
| --- | --- | --- | --- | --- | --- |
| row_id | 0 | 0 | 88 | 2 | 0d1a5f1c84e20e16 |
| prompt_text | 0 | 0 | 88 | 2 | Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt |
| target_case_relpath | 0 | 0 | 28 | 36 | Exec/RegTests/PeriodicCases |
| target_inputs_relpath | 0 | 0 | 88 | 2 | Exec/Plasma/FlameSheetIons/input.2d-regt |
| target_inputs_filename | 0 | 0 | 62 | 30 | input.2d-regt |
| selected_case | 0 | 0 | 28 | 33 | Exec/RegTests/FlameSheet |
| selected_inputs | 0 | 10 | 28 | 28 | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp |
| strategy | 0 | 0 | 2 | 88 | simple |

- ⚠️ POSSIBLE INPUT GENERATION ISSUE — column `selected_inputs`: nulls=0, blanks=10, unique=28, top_freq=28

Path/index/source-like columns and unique values:
- `target_case_relpath`: `Exec/Plasma/FlameSheetIons` (4), `Exec/Plasma/IonizedAirWave` (4), `Exec/Plasma/PremBunsen3DKuhl` (8), `Exec/Production/ChallengeProblem` (4), `Exec/Production/CounterFlow` (4), `Exec/Production/CounterFlowSpray` (2), `Exec/Production/DiffBunsen2D` (2), `Exec/Production/JetInCrossflow` (12), `Exec/Production/NormalJet_OpenDomain` (2), `Exec/Production/PremBunsen2D` (2), `Exec/Production/PremBunsen3D` (2), `Exec/Production/SwirlFlowWallInteractions` (2), `Exec/RegTests/EB_EnclosedFlame` (6), `Exec/RegTests/EB_EnclosedVortex` (8), `Exec/RegTests/EB_FlowPastCylinder` (18), `Exec/RegTests/EB_PipeFlow` (6), `Exec/RegTests/EnclosedFlame` (4), `Exec/RegTests/EnclosedInjection` (2), `Exec/RegTests/FlameSheet` (12), `Exec/RegTests/HotBubble` (8), `Exec/RegTests/PeriodicCases` (36), `Exec/RegTests/SprayTest` (2), `Exec/RegTests/TaylorGreen` (6), `Exec/RegTests/TripleFlame` (2), `Exec/RegTests/TurbInflow` (10), `Exec/RegTests/Unit` (4), `Exec/UnitTests/DodecaneLu` (2), `Exec/UnitTests/EB_SphericalFlame` (2)
- `target_inputs_relpath`: `Exec/Plasma/FlameSheetIons/input.2d-regt` (2), `Exec/Plasma/FlameSheetIons/input.2d-regt_flipped` (2), `Exec/Plasma/IonizedAirWave/input.2d-regt` (2), `Exec/Plasma/IonizedAirWave/input.2d-regt_wave` (2), `Exec/Plasma/PremBunsen3DKuhl/input.3d_lean` (2), `Exec/Plasma/PremBunsen3DKuhl/input.3d_rich` (2), `Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich` (2), `Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich_EF` (2), `Exec/Production/ChallengeProblem/input.3d` (2), `Exec/Production/ChallengeProblem/input.3d_Hypre` (2), `Exec/Production/CounterFlow/input.2d-regt` (2), `Exec/Production/CounterFlow/input_coolflow.2d-regt` (2), `Exec/Production/CounterFlowSpray/input.2d-regt` (2), `Exec/Production/DiffBunsen2D/input.2d-regt` (2), `Exec/Production/JetInCrossflow/input.3d` (2), `Exec/Production/JetInCrossflow/input.3d_reacting` (2), `Exec/Production/JetInCrossflow/input_all.inp` (2), `Exec/Production/JetInCrossflow/input_les_additions.inp` (2), `Exec/Production/JetInCrossflow/input_reacting_additions.inp` (2), `Exec/Production/JetInCrossflow/input_turbinflow_additions.inp` (2), `Exec/Production/NormalJet_OpenDomain/inputs.3d-regt` (2), `Exec/Production/PremBunsen2D/input.2d-regt` (2), `Exec/Production/PremBunsen3D/input.3d` (2), `Exec/Production/SwirlFlowWallInteractions/input.3d` (2), `Exec/RegTests/EB_EnclosedFlame/input.2d-regt` (2), `Exec/RegTests/EB_EnclosedFlame/input.2d-regt_Hypre` (2), `Exec/RegTests/EB_EnclosedFlame/input.3d-regt` (2), `Exec/RegTests/EB_EnclosedVortex/input.2d-regt` (2), `Exec/RegTests/EB_EnclosedVortex/input.2d-regt_Hypre` (2), `Exec/RegTests/EB_EnclosedVortex/input.2d-regt_incomp` (2), `Exec/RegTests/EB_EnclosedVortex/input.3d-regt` (2), `Exec/RegTests/EB_FlowPastCylinder/input.2d-Re500` (2), `Exec/RegTests/EB_FlowPastCylinder/input.2d-regt` (2), `Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreMAC` (2), `Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreNodal` (2), `Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_WallBump` (2), `Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_isoT` (2), `Exec/RegTests/EB_FlowPastCylinder/input.3d-regt` (2), `Exec/RegTests/EB_FlowPastCylinder/input.3d-regtY` (2), `Exec/RegTests/EB_FlowPastCylinder/input.3d-regt_WallBump` (2), `Exec/RegTests/EB_PipeFlow/input.2d-regt` (2), `Exec/RegTests/EB_PipeFlow/input.3d-Poiseuille` (2), `Exec/RegTests/EB_PipeFlow/input.3d-regt` (2), `Exec/RegTests/EnclosedFlame/input.2d-regt` (2), `Exec/RegTests/EnclosedFlame/input.3d-regt` (2), `Exec/RegTests/EnclosedInjection/input.2d-regt` (2), `Exec/RegTests/FlameSheet/input.2d-regt` (2), `Exec/RegTests/FlameSheet/input.3d-regt` (2), `Exec/RegTests/FlameSheet/input.manifold` (2), `Exec/RegTests/FlameSheet/input.manifold.cvar` (2), `Exec/RegTests/FlameSheet/inputs.3d_Dodecane` (2), `Exec/RegTests/FlameSheet/inputs.3d_DodecaneQSS` (2), `Exec/RegTests/HotBubble/input.2d-regt` (2), `Exec/RegTests/HotBubble/input.2d-regt_sym` (2), `Exec/RegTests/HotBubble/input.2d-regt_symRZ` (2), `Exec/RegTests/HotBubble/input.3d-regt` (2), `Exec/RegTests/PeriodicCases/input.2d_CoGauS` (2), `Exec/RegTests/PeriodicCases/input.2d_CoGauSAMR` (2), `Exec/RegTests/PeriodicCases/input.2d_CoGauT` (2), `Exec/RegTests/PeriodicCases/input.2d_CoGauTAMR` (2), `Exec/RegTests/PeriodicCases/input.2d_CoTanHSAMR` (2), `Exec/RegTests/PeriodicCases/input.2d_CoTanHTAMR` (2), `Exec/RegTests/PeriodicCases/input.2d_CoVo` (2), `Exec/RegTests/PeriodicCases/input.2d_CoVoAMR` (2), `Exec/RegTests/PeriodicCases/input.2d_CoVoIncomp` (2), `Exec/RegTests/PeriodicCases/input.2d_DiffGauS` (2), `Exec/RegTests/PeriodicCases/input.2d_DiffGauSAMR` (2), `Exec/RegTests/PeriodicCases/input.2d_DiffGauSRef` (2), `Exec/RegTests/PeriodicCases/input.2d_DiffGauT` (2), `Exec/RegTests/PeriodicCases/input.2d_DiffGauTAMR` (2), `Exec/RegTests/PeriodicCases/input.3d_CoVo` (2), `Exec/RegTests/PeriodicCases/input.3d_CoVo_InflowGen` (2), `Exec/RegTests/PeriodicCases/input.3d_CoVo_PlaneInput` (2), `Exec/RegTests/PeriodicCases/input.3d_CoVo_PltInput` (2), `Exec/RegTests/SprayTest/input.2d` (2), `Exec/RegTests/TaylorGreen/input.3d_BDS` (2), `Exec/RegTests/TaylorGreen/input.3d_PLM` (2), `Exec/RegTests/TaylorGreen/input.3d_PPM` (2), `Exec/RegTests/TripleFlame/input.2d-regt` (2), `Exec/RegTests/TurbInflow/input.3d` (2), `Exec/RegTests/TurbInflow/input.3d_BoxLoZ` (2), `Exec/RegTests/TurbInflow/input.3d_posX` (2), `Exec/RegTests/TurbInflow/input.3d_twoInjs` (2), `Exec/RegTests/TurbInflow/input.3d_twoInjsOverlap` (2), `Exec/RegTests/Unit/input` (2), `Exec/RegTests/Unit/input.diffusion` (2), `Exec/UnitTests/DodecaneLu/inputs.3d` (2), `Exec/UnitTests/EB_SphericalFlame/input.3d-regt` (2)

First 5 rows (selected fields):
```json
[
  {
    "row_id": "0d1a5f1c84e20e16",
    "strategy": "simple",
    "category": "Plasma",
    "prompt_text": "Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt",
    "target_case_relpath": "Exec/Plasma/FlameSheetIons",
    "target_inputs_filename": "input.2d-regt",
    "target_inputs_relpath": "Exec/Plasma/FlameSheetIons/input.2d-regt",
    "selected_case": "Exec/Plasma/FlameSheetIons",
    "selected_inputs": "Exec/Plasma/FlameSheetIons/input.2d-regt",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 1
  },
  {
    "row_id": "4d2843a6c6926ca2",
    "strategy": "simple",
    "category": "Plasma",
    "prompt_text": "Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt_flipped",
    "target_case_relpath": "Exec/Plasma/FlameSheetIons",
    "target_inputs_filename": "input.2d-regt_flipped",
    "target_inputs_relpath": "Exec/Plasma/FlameSheetIons/input.2d-regt_flipped",
    "selected_case": "Exec/Plasma/FlameSheetIons",
    "selected_inputs": "Exec/Plasma/FlameSheetIons/input.2d-regt",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 2
  },
  {
    "row_id": "dc8d8225950a1bfd",
    "strategy": "simple",
    "category": "Plasma",
    "prompt_text": "Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt",
    "target_case_relpath": "Exec/Plasma/IonizedAirWave",
    "target_inputs_filename": "input.2d-regt",
    "target_inputs_relpath": "Exec/Plasma/IonizedAirWave/input.2d-regt",
    "selected_case": "Exec/Plasma/IonizedAirWave",
    "selected_inputs": "Exec/Plasma/IonizedAirWave/input.2d-regt_wave",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 3
  },
  {
    "row_id": "74ba9feb56efd323",
    "strategy": "simple",
    "category": "Plasma",
    "prompt_text": "Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt_wave",
    "target_case_relpath": "Exec/Plasma/IonizedAirWave",
    "target_inputs_filename": "input.2d-regt_wave",
    "target_inputs_relpath": "Exec/Plasma/IonizedAirWave/input.2d-regt_wave",
    "selected_case": "Exec/Plasma/IonizedAirWave",
    "selected_inputs": "Exec/Plasma/IonizedAirWave/input.2d-regt_wave",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 4
  },
  {
    "row_id": "93dddd9cc1500cbd",
    "strategy": "simple",
    "category": "Plasma",
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_lean",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_filename": "input.3d_lean",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_lean",
    "selected_case": "Exec/Plasma/PremBunsen3DKuhl",
    "selected_inputs": "Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 5
  }
]
```
Last 5 rows (selected fields):
```json
[
  {
    "row_id": "449339b0bef68d23",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_twoInjsOverlap",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_filename": "input.3d_twoInjsOverlap",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_twoInjsOverlap",
    "selected_case": "Exec/RegTests/EB_PipeFlow",
    "selected_inputs": "Exec/RegTests/EB_PipeFlow/input.3d-regt",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 172
  },
  {
    "row_id": "a22762f98dd236c0",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use PeleLMeX case Exec/RegTests/Unit with input",
    "target_case_relpath": "Exec/RegTests/Unit",
    "target_inputs_filename": "input",
    "target_inputs_relpath": "Exec/RegTests/Unit/input",
    "selected_case": "Exec/RegTests/TaylorGreen",
    "selected_inputs": "Exec/RegTests/TaylorGreen/input.3d_PPM",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 173
  },
  {
    "row_id": "0a953c129d3fc627",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use PeleLMeX case Exec/RegTests/Unit with input.diffusion",
    "target_case_relpath": "Exec/RegTests/Unit",
    "target_inputs_filename": "input.diffusion",
    "target_inputs_relpath": "Exec/RegTests/Unit/input.diffusion",
    "selected_case": "Exec/RegTests/FlameSheet",
    "selected_inputs": "Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 174
  },
  {
    "row_id": "d4d9f6b22420e1e8",
    "strategy": "hierarchical",
    "category": "UnitTests",
    "prompt_text": "Use PeleLMeX case Exec/UnitTests/DodecaneLu with inputs.3d",
    "target_case_relpath": "Exec/UnitTests/DodecaneLu",
    "target_inputs_filename": "inputs.3d",
    "target_inputs_relpath": "Exec/UnitTests/DodecaneLu/inputs.3d",
    "selected_case": "Exec/UnitTests/EB_SphericalFlame",
    "selected_inputs": "Exec/UnitTests/EB_SphericalFlame/input.3d-regt",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 175
  },
  {
    "row_id": "2ff0b30f0144e7cf",
    "strategy": "hierarchical",
    "category": "UnitTests",
    "prompt_text": "Use PeleLMeX case Exec/UnitTests/EB_SphericalFlame with input.3d-regt",
    "target_case_relpath": "Exec/UnitTests/EB_SphericalFlame",
    "target_inputs_filename": "input.3d-regt",
    "target_inputs_relpath": "Exec/UnitTests/EB_SphericalFlame/input.3d-regt",
    "selected_case": "Exec/UnitTests/EB_SphericalFlame",
    "selected_inputs": "Exec/UnitTests/EB_SphericalFlame/input.3d-regt",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 176
  }
]
```

### Source File: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl`
- Last Modified: `2026-04-30T12:16:52.592481-07:00`
- Size: `382.35 KB`
- Row Count: `48`

Key identifier column checks:
| Column | Nulls | Blanks | Unique Values | Top Frequency | Top Value (preview) |
| --- | --- | --- | --- | --- | --- |
| row_id | 0 | 0 | 24 | 2 | a617add54e5dfdbb |
| prompt_text | 0 | 0 | 24 | 2 | Use REMORA case Exec/Advection with inputs |
| target_case_relpath | 0 | 0 | 14 | 10 | Exec/IdealMiniGrid |
| target_inputs_relpath | 0 | 0 | 24 | 2 | Exec/Advection/inputs |
| target_inputs_filename | 0 | 0 | 10 | 28 | inputs |
| selected_case | 0 | 0 | 14 | 12 | Exec/Upwelling_ML |
| selected_inputs | 0 | 2 | 15 | 10 | Exec/Upwelling_ML/inputs |
| strategy | 0 | 0 | 2 | 24 | simple |

- ⚠️ POSSIBLE INPUT GENERATION ISSUE — column `selected_inputs`: nulls=0, blanks=2, unique=15, top_freq=10

Path/index/source-like columns and unique values:
- `target_case_relpath`: `Exec/Advection` (4), `Exec/BlankProblem` (2), `Exec/BoundaryLayer` (2), `Exec/Channel_Test` (4), `Exec/Dogbone` (2), `Exec/DogboneAnalytic` (8), `Exec/DoubleGyre` (2), `Exec/DoublyPeriodic` (2), `Exec/IdealMiniGrid` (10), `Exec/IdealRivGrid` (2), `Exec/ParticlesOverSeaMount` (2), `Exec/Seamount` (2), `Exec/Upwelling` (4), `Exec/Upwelling_ML` (2)
- `target_inputs_relpath`: `Exec/Advection/inputs` (2), `Exec/Advection/inputs_ml` (2), `Exec/BlankProblem/inputs` (2), `Exec/BoundaryLayer/inputs` (2), `Exec/Channel_Test/inputs` (2), `Exec/Channel_Test/inputs_orlanski` (2), `Exec/Dogbone/inputs` (2), `Exec/DogboneAnalytic/inputs` (2), `Exec/DogboneAnalytic/inputs_ml` (2), `Exec/DogboneAnalytic/inputs_ml_mid` (2), `Exec/DogboneAnalytic/inputs_ml_quad` (2), `Exec/DoubleGyre/inputs` (2), `Exec/DoublyPeriodic/inputs` (2), `Exec/IdealMiniGrid/inputs` (2), `Exec/IdealMiniGrid/inputs_cf_orlanski` (2), `Exec/IdealMiniGrid/inputs_chapman_flather` (2), `Exec/IdealMiniGrid/inputs_clim_nudg` (2), `Exec/IdealMiniGrid/inputs_frc` (2), `Exec/IdealRivGrid/inputs` (2), `Exec/ParticlesOverSeaMount/inputs` (2), `Exec/Seamount/inputs` (2), `Exec/Upwelling/inputs` (2), `Exec/Upwelling/inputs_gls` (2), `Exec/Upwelling_ML/inputs` (2)

First 5 rows (selected fields):
```json
[
  {
    "row_id": "a617add54e5dfdbb",
    "strategy": "simple",
    "category": "Advection",
    "prompt_text": "Use REMORA case Exec/Advection with inputs",
    "target_case_relpath": "Exec/Advection",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/Advection/inputs",
    "selected_case": "Exec/Advection",
    "selected_inputs": "Exec/Advection/inputs",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 1
  },
  {
    "row_id": "62ec1c41ae20e1ce",
    "strategy": "simple",
    "category": "Advection",
    "prompt_text": "Use REMORA case Exec/Advection with inputs_ml",
    "target_case_relpath": "Exec/Advection",
    "target_inputs_filename": "inputs_ml",
    "target_inputs_relpath": "Exec/Advection/inputs_ml",
    "selected_case": "Exec/Upwelling_ML",
    "selected_inputs": "Exec/Upwelling_ML/inputs",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 2
  },
  {
    "row_id": "def9c633363a4b8e",
    "strategy": "simple",
    "category": "BlankProblem",
    "prompt_text": "Use REMORA case Exec/BlankProblem with inputs",
    "target_case_relpath": "Exec/BlankProblem",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/BlankProblem/inputs",
    "selected_case": "Exec/BlankProblem",
    "selected_inputs": "Exec/BlankProblem/inputs",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 3
  },
  {
    "row_id": "6950b792af338a18",
    "strategy": "simple",
    "category": "BoundaryLayer",
    "prompt_text": "Use REMORA case Exec/BoundaryLayer with inputs",
    "target_case_relpath": "Exec/BoundaryLayer",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/BoundaryLayer/inputs",
    "selected_case": "Exec/BoundaryLayer",
    "selected_inputs": "Exec/BoundaryLayer/inputs",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 4
  },
  {
    "row_id": "a445447b6cc4cca9",
    "strategy": "simple",
    "category": "Channel_Test",
    "prompt_text": "Use REMORA case Exec/Channel_Test with inputs",
    "target_case_relpath": "Exec/Channel_Test",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/Channel_Test/inputs",
    "selected_case": "Exec/Channel_Test",
    "selected_inputs": "Exec/Channel_Test/inputs",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 5
  }
]
```
Last 5 rows (selected fields):
```json
[
  {
    "row_id": "720475e996cb5079",
    "strategy": "hierarchical",
    "category": "ParticlesOverSeaMount",
    "prompt_text": "Use REMORA case Exec/ParticlesOverSeaMount with inputs",
    "target_case_relpath": "Exec/ParticlesOverSeaMount",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/ParticlesOverSeaMount/inputs",
    "selected_case": "Exec/ParticlesOverSeaMount",
    "selected_inputs": "Exec/ParticlesOverSeaMount/inputs",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 44
  },
  {
    "row_id": "3013bff38a87e9e9",
    "strategy": "hierarchical",
    "category": "Seamount",
    "prompt_text": "Use REMORA case Exec/Seamount with inputs",
    "target_case_relpath": "Exec/Seamount",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/Seamount/inputs",
    "selected_case": "Exec/Upwelling",
    "selected_inputs": "Exec/Upwelling/inputs",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 45
  },
  {
    "row_id": "4f215d9076a7f652",
    "strategy": "hierarchical",
    "category": "Upwelling",
    "prompt_text": "Use REMORA case Exec/Upwelling with inputs",
    "target_case_relpath": "Exec/Upwelling",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/Upwelling/inputs",
    "selected_case": "Exec/Upwelling_ML",
    "selected_inputs": "",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 46
  },
  {
    "row_id": "f62335bf44744aa7",
    "strategy": "hierarchical",
    "category": "Upwelling",
    "prompt_text": "Use REMORA case Exec/Upwelling with inputs_gls",
    "target_case_relpath": "Exec/Upwelling",
    "target_inputs_filename": "inputs_gls",
    "target_inputs_relpath": "Exec/Upwelling/inputs_gls",
    "selected_case": "Exec/Upwelling",
    "selected_inputs": "Exec/Upwelling/inputs",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 47
  },
  {
    "row_id": "f06a806d73e779c6",
    "strategy": "hierarchical",
    "category": "Upwelling_ML",
    "prompt_text": "Use REMORA case Exec/Upwelling_ML with inputs",
    "target_case_relpath": "Exec/Upwelling_ML",
    "target_inputs_filename": "inputs",
    "target_inputs_relpath": "Exec/Upwelling_ML/inputs",
    "selected_case": "Exec/Upwelling_ML",
    "selected_inputs": "",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 48
  }
]
```

### Source File: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl`
- Last Modified: `2026-04-29T13:15:31.581171-07:00`
- Size: `170.10 KB`
- Row Count: `272`

Key identifier column checks:
| Column | Nulls | Blanks | Unique Values | Top Frequency | Top Value (preview) |
| --- | --- | --- | --- | --- | --- |
| row_id | 0 | 0 | 136 | 2 | 9d54aad7fa6c374f |
| prompt_text | 0 | 0 | 136 | 2 | Use ERF case Exec/CanonicalTests/ABL with inputs_DataSampler |
| target_case_relpath | 0 | 0 | 35 | 48 | Exec/CanonicalTests/ABL |
| target_inputs_relpath | 0 | 0 | 136 | 2 | Exec/CanonicalTests/ABL/inputs_DataSampler |
| target_inputs_filename | 0 | 0 | 119 | 16 | inputs |
| selected_case | 0 | 0 | 35 | 48 | Exec/CanonicalTests/ABL |
| selected_inputs | 0 | 0 | 101 | 20 | Exec/RegTests/WitchOfAgnesi/inputs |
| strategy | 0 | 0 | 2 | 136 | simple |

- No null/blank/constant-column flags in prompt/case identifier fields.

Path/index/source-like columns and unique values:
- `target_case_relpath`: `Exec/CanonicalTests/ABL` (48), `Exec/CanonicalTests/Canonical_LES/Convective_ABL` (4), `Exec/CanonicalTests/Canonical_LES/Neutral_ABL` (4), `Exec/CanonicalTests/Canonical_LES/Stable_ABL` (2), `Exec/CanonicalTests/Channel_DNS` (2), `Exec/CanonicalTests/DensityCurrent` (16), `Exec/CanonicalTests/EkmanSpiral` (6), `Exec/CanonicalTests/Idealized_Terrain/ScharMountain` (2), `Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi` (2), `Exec/CanonicalTests/Real_Terrain/Altamont` (2), `Exec/CanonicalTests/Real_Terrain/Askervein` (2), `Exec/CanonicalTests/SquallLine_2D` (10), `Exec/CanonicalTests/SuperCell_3D` (2), `Exec/RegTests/Bubble` (26), `Exec/RegTests/Couette_Poiseuille` (8), `Exec/RegTests/EB_Poiseuille` (2), `Exec/RegTests/EB_SquareCylinder` (4), `Exec/RegTests/FlowInABox` (2), `Exec/RegTests/ImmersedForcingTest` (6), `Exec/RegTests/InitFromNCFile` (2), `Exec/RegTests/IsentropicVortex` (14), `Exec/RegTests/MetGrid` (2), `Exec/RegTests/MovingTerrain` (2), `Exec/RegTests/MultiSpeciesBubble` (8), `Exec/RegTests/ParticleTests` (4), `Exec/RegTests/Radiation` (2), `Exec/RegTests/ScalarAdvDiff` (32), `Exec/RegTests/SineMassFlux` (2), `Exec/RegTests/StokesSecondProblem` (4), `Exec/RegTests/TaylorGreenVortex` (6), `Exec/RegTests/Terrain2d_Cylinder` (8), `Exec/RegTests/Terrain3d_Hemisphere` (10), `Exec/RegTests/TurbulentInflow` (2), `Exec/RegTests/WPS_Test` (4), `Exec/RegTests/WitchOfAgnesi` (20)
- `target_inputs_relpath`: `Exec/CanonicalTests/ABL/inputs_DataSampler` (2), `Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff` (2), `Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25` (2), `Exec/CanonicalTests/ABL/inputs_GABLS1_ysu` (2), `Exec/CanonicalTests/ABL/inputs_anel_most` (2), `Exec/CanonicalTests/ABL/inputs_canopy` (2), `Exec/CanonicalTests/ABL/inputs_deardorff` (2), `Exec/CanonicalTests/ABL/inputs_deardorff_msf` (2), `Exec/CanonicalTests/ABL/inputs_deardorff_no_msf` (2), `Exec/CanonicalTests/ABL/inputs_ml_most` (2), `Exec/CanonicalTests/ABL/inputs_most` (2), `Exec/CanonicalTests/ABL/inputs_most_bomex` (2), `Exec/CanonicalTests/ABL/inputs_most_msf` (2), `Exec/CanonicalTests/ABL/inputs_most_no_msf` (2), `Exec/CanonicalTests/ABL/inputs_most_pbl` (2), `Exec/CanonicalTests/ABL/inputs_most_test` (2), `Exec/CanonicalTests/ABL/inputs_numdiff` (2), `Exec/CanonicalTests/ABL/inputs_omp` (2), `Exec/CanonicalTests/ABL/inputs_sample` (2), `Exec/CanonicalTests/ABL/inputs_smagorinsky` (2), `Exec/CanonicalTests/ABL/inputs_smagorinsky_msf` (2), `Exec/CanonicalTests/ABL/inputs_smagorinsky_no_msf` (2), `Exec/CanonicalTests/ABL/inputs_terrain` (2), `Exec/CanonicalTests/ABL/inputs_vel_avg` (2), `Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_flux` (2), `Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_heating_rate` (2), `Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_anelastic` (2), `Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_compressible` (2), `Exec/CanonicalTests/Canonical_LES/Stable_ABL/inputs_with_const_massflux` (2), `Exec/CanonicalTests/Channel_DNS/inputs_channel` (2), `Exec/CanonicalTests/DensityCurrent/inputs_amr` (2), `Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain` (2), `Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain_zlev` (2), `Exec/CanonicalTests/DensityCurrent/inputs_fft` (2), `Exec/CanonicalTests/DensityCurrent/inputs_hybrid` (2), `Exec/CanonicalTests/DensityCurrent/inputs_hybrid_zlev` (2), `Exec/CanonicalTests/DensityCurrent/inputs_refsoln` (2), `Exec/CanonicalTests/DensityCurrent/inputs_wrf_baseline` (2), `Exec/CanonicalTests/EkmanSpiral/inputs_custom` (2), `Exec/CanonicalTests/EkmanSpiral/inputs_ideal` (2), `Exec/CanonicalTests/EkmanSpiral/inputs_input_sounding` (2), `Exec/CanonicalTests/Idealized_Terrain/ScharMountain/inputs` (2), `Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi/inputs_WoA` (2), `Exec/CanonicalTests/Real_Terrain/Altamont/inputs_terrain` (2), `Exec/CanonicalTests/Real_Terrain/Askervein/inputs_anel` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_ml` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Gabersek` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Morrison` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_SAM` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_WRF` (2), `Exec/CanonicalTests/SuperCell_3D/inputs_moisture_Tissaoui` (2), `Exec/RegTests/Bubble/inputs_BF02_dry_bubble` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Kessler` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Morrison` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_OpenBC` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoIce` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoPrecip_NoIce` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM_multi_injections_unimodal_NaCl` (2), `Exec/RegTests/Bubble/inputs_grav2d_x` (2), `Exec/RegTests/Bubble/inputs_squall2d_x` (2), `Exec/RegTests/Bubble/inputs_test_outflow` (2), `Exec/RegTests/Couette_Poiseuille/inputs_couette_x` (2), `Exec/RegTests/Couette_Poiseuille/inputs_couette_y` (2), `Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_x` (2), `Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_y` (2), `Exec/RegTests/EB_Poiseuille/inputs_compressible` (2), `Exec/RegTests/EB_SquareCylinder/inputs_anelastic` (2), `Exec/RegTests/EB_SquareCylinder/inputs_multilevel` (2), `Exec/RegTests/FlowInABox/inputs` (2), `Exec/RegTests/ImmersedForcingTest/inputs_if_building` (2), `Exec/RegTests/ImmersedForcingTest/inputs_if_terrain` (2), `Exec/RegTests/ImmersedForcingTest/inputs_if_terrain_plusBuilding` (2), `Exec/RegTests/InitFromNCFile/inputs` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting_ml` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting_msf` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting_no_msf` (2), `Exec/RegTests/IsentropicVortex/inputs_stationary` (2), `Exec/RegTests/IsentropicVortex/inputs_stationary_msf` (2), `Exec/RegTests/IsentropicVortex/inputs_stationary_no_msf` (2), `Exec/RegTests/MetGrid/inputs_metgrid` (2), `Exec/RegTests/MovingTerrain/inputs` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.01species` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.02species` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.01species` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.02species` (2), `Exec/RegTests/ParticleTests/inputs_over_flat` (2), `Exec/RegTests/ParticleTests/inputs_over_hill` (2), `Exec/RegTests/Radiation/inputs_radiation` (2), `Exec/RegTests/ScalarAdvDiff/inputs_WENO` (2), `Exec/RegTests/ScalarAdvDiff/inputs_WENO_Z` (2), `Exec/RegTests/ScalarAdvDiff/inputs_adv_diff_uniformU` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advdiffinflowoutflow` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_no_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_no_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_gaussian` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_no_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_sine` (2), `Exec/RegTests/ScalarAdvDiff/inputs_ml` (2), `Exec/RegTests/ScalarAdvDiff/inputs_test_rayleigh` (2), `Exec/RegTests/SineMassFlux/inputs_SDM_condBE` (2), `Exec/RegTests/StokesSecondProblem/inputs` (2), `Exec/RegTests/StokesSecondProblem/inputs_stretched_z_levels` (2), `Exec/RegTests/TaylorGreenVortex/inputs_advdiff` (2), `Exec/RegTests/TaylorGreenVortex/inputs_advonly` (2), `Exec/RegTests/TaylorGreenVortex/inputs_multilevel` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs_most_test` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs_stretched_z_levels` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs_verification_final` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_EB` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_EB_twolevel` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_FittedMesh` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_most_test` (2), `Exec/RegTests/TurbulentInflow/inputs_multilevel_ABL_source` (2), `Exec/RegTests/WPS_Test/inputs_wps` (2), `Exec/RegTests/WPS_Test/inputs_wps_noahmp` (2), `Exec/RegTests/WitchOfAgnesi/inputs` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic_twolevel` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_multilevel` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_x` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_y` (2), `Exec/RegTests/WitchOfAgnesi/inputs_FittedMesh` (2), `Exec/RegTests/WitchOfAgnesi/inputs_most_test` (2), `Exec/RegTests/WitchOfAgnesi/inputs_static_twolevel` (2), `Exec/RegTests/WitchOfAgnesi/inputs_zlevels` (2)

First 5 rows (selected fields):
```json
[
  {
    "row_id": "9d54aad7fa6c374f",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_DataSampler",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_DataSampler",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_DataSampler",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_DataSampler",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 1
  },
  {
    "row_id": "5d00f979d031dfe3",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_deardorff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_GABLS1_deardorff",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 2
  },
  {
    "row_id": "224c4249dd7298ca",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_mynn25",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_GABLS1_mynn25",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 3
  },
  {
    "row_id": "86d89bc4b0195acd",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_ysu",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_GABLS1_ysu",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_ysu",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_GABLS1_ysu",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 4
  },
  {
    "row_id": "c7efaf20e3f6a4ad",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_anel_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_anel_most",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_anel_most",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_anel_most",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 5
  }
]
```
Last 5 rows (selected fields):
```json
[
  {
    "row_id": "8bb187ab2fe052ee",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_y",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_EB_y",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_y",
    "selected_case": "Exec/RegTests/WitchOfAgnesi",
    "selected_inputs": "Exec/RegTests/WitchOfAgnesi/inputs",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 268
  },
  {
    "row_id": "096e193d4c26a46f",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_FittedMesh",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_FittedMesh",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_FittedMesh",
    "selected_case": "Exec/RegTests/WitchOfAgnesi",
    "selected_inputs": "Exec/RegTests/WitchOfAgnesi/inputs",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 269
  },
  {
    "row_id": "8713bb629c310ac3",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_most_test",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_most_test",
    "selected_case": "Exec/RegTests/WitchOfAgnesi",
    "selected_inputs": "Exec/RegTests/WitchOfAgnesi/inputs",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 270
  },
  {
    "row_id": "6c5555e3ba011821",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_static_twolevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_static_twolevel",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_static_twolevel",
    "selected_case": "Exec/RegTests/WitchOfAgnesi",
    "selected_inputs": "Exec/RegTests/WitchOfAgnesi/inputs",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 271
  },
  {
    "row_id": "8f109351917b36ed",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_zlevels",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_zlevels",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_zlevels",
    "selected_case": "Exec/RegTests/WitchOfAgnesi",
    "selected_inputs": "Exec/RegTests/WitchOfAgnesi/inputs",
    "case_match": 1,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 272
  }
]
```

### Source File: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl`
- Last Modified: `2026-04-28T10:43:03.108909-07:00`
- Size: `2951.50 KB`
- Row Count: `272`

Key identifier column checks:
| Column | Nulls | Blanks | Unique Values | Top Frequency | Top Value (preview) |
| --- | --- | --- | --- | --- | --- |
| row_id | 0 | 0 | 136 | 2 | 9d54aad7fa6c374f |
| prompt_text | 0 | 0 | 136 | 2 | Use ERF case Exec/CanonicalTests/ABL with inputs_DataSampler |
| target_case_relpath | 0 | 0 | 35 | 48 | Exec/CanonicalTests/ABL |
| target_inputs_relpath | 0 | 0 | 136 | 2 | Exec/CanonicalTests/ABL/inputs_DataSampler |
| target_inputs_filename | 0 | 0 | 119 | 16 | inputs |
| selected_case | 0 | 0 | 49 | 50 | Exec/CanonicalTests/ABL |
| selected_inputs | 0 | 3 | 95 | 20 | Exec/RegTests/Terrain3d_Hemisphere/inputs |
| strategy | 0 | 0 | 2 | 136 | simple |

- ⚠️ POSSIBLE INPUT GENERATION ISSUE — column `selected_inputs`: nulls=0, blanks=3, unique=95, top_freq=20

Path/index/source-like columns and unique values:
- `target_case_relpath`: `Exec/CanonicalTests/ABL` (48), `Exec/CanonicalTests/Canonical_LES/Convective_ABL` (4), `Exec/CanonicalTests/Canonical_LES/Neutral_ABL` (4), `Exec/CanonicalTests/Canonical_LES/Stable_ABL` (2), `Exec/CanonicalTests/Channel_DNS` (2), `Exec/CanonicalTests/DensityCurrent` (16), `Exec/CanonicalTests/EkmanSpiral` (6), `Exec/CanonicalTests/Idealized_Terrain/ScharMountain` (2), `Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi` (2), `Exec/CanonicalTests/Real_Terrain/Altamont` (2), `Exec/CanonicalTests/Real_Terrain/Askervein` (2), `Exec/CanonicalTests/SquallLine_2D` (10), `Exec/CanonicalTests/SuperCell_3D` (2), `Exec/RegTests/Bubble` (26), `Exec/RegTests/Couette_Poiseuille` (8), `Exec/RegTests/EB_Poiseuille` (2), `Exec/RegTests/EB_SquareCylinder` (4), `Exec/RegTests/FlowInABox` (2), `Exec/RegTests/ImmersedForcingTest` (6), `Exec/RegTests/InitFromNCFile` (2), `Exec/RegTests/IsentropicVortex` (14), `Exec/RegTests/MetGrid` (2), `Exec/RegTests/MovingTerrain` (2), `Exec/RegTests/MultiSpeciesBubble` (8), `Exec/RegTests/ParticleTests` (4), `Exec/RegTests/Radiation` (2), `Exec/RegTests/ScalarAdvDiff` (32), `Exec/RegTests/SineMassFlux` (2), `Exec/RegTests/StokesSecondProblem` (4), `Exec/RegTests/TaylorGreenVortex` (6), `Exec/RegTests/Terrain2d_Cylinder` (8), `Exec/RegTests/Terrain3d_Hemisphere` (10), `Exec/RegTests/TurbulentInflow` (2), `Exec/RegTests/WPS_Test` (4), `Exec/RegTests/WitchOfAgnesi` (20)
- `target_inputs_relpath`: `Exec/CanonicalTests/ABL/inputs_DataSampler` (2), `Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff` (2), `Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25` (2), `Exec/CanonicalTests/ABL/inputs_GABLS1_ysu` (2), `Exec/CanonicalTests/ABL/inputs_anel_most` (2), `Exec/CanonicalTests/ABL/inputs_canopy` (2), `Exec/CanonicalTests/ABL/inputs_deardorff` (2), `Exec/CanonicalTests/ABL/inputs_deardorff_msf` (2), `Exec/CanonicalTests/ABL/inputs_deardorff_no_msf` (2), `Exec/CanonicalTests/ABL/inputs_ml_most` (2), `Exec/CanonicalTests/ABL/inputs_most` (2), `Exec/CanonicalTests/ABL/inputs_most_bomex` (2), `Exec/CanonicalTests/ABL/inputs_most_msf` (2), `Exec/CanonicalTests/ABL/inputs_most_no_msf` (2), `Exec/CanonicalTests/ABL/inputs_most_pbl` (2), `Exec/CanonicalTests/ABL/inputs_most_test` (2), `Exec/CanonicalTests/ABL/inputs_numdiff` (2), `Exec/CanonicalTests/ABL/inputs_omp` (2), `Exec/CanonicalTests/ABL/inputs_sample` (2), `Exec/CanonicalTests/ABL/inputs_smagorinsky` (2), `Exec/CanonicalTests/ABL/inputs_smagorinsky_msf` (2), `Exec/CanonicalTests/ABL/inputs_smagorinsky_no_msf` (2), `Exec/CanonicalTests/ABL/inputs_terrain` (2), `Exec/CanonicalTests/ABL/inputs_vel_avg` (2), `Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_flux` (2), `Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_heating_rate` (2), `Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_anelastic` (2), `Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_compressible` (2), `Exec/CanonicalTests/Canonical_LES/Stable_ABL/inputs_with_const_massflux` (2), `Exec/CanonicalTests/Channel_DNS/inputs_channel` (2), `Exec/CanonicalTests/DensityCurrent/inputs_amr` (2), `Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain` (2), `Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain_zlev` (2), `Exec/CanonicalTests/DensityCurrent/inputs_fft` (2), `Exec/CanonicalTests/DensityCurrent/inputs_hybrid` (2), `Exec/CanonicalTests/DensityCurrent/inputs_hybrid_zlev` (2), `Exec/CanonicalTests/DensityCurrent/inputs_refsoln` (2), `Exec/CanonicalTests/DensityCurrent/inputs_wrf_baseline` (2), `Exec/CanonicalTests/EkmanSpiral/inputs_custom` (2), `Exec/CanonicalTests/EkmanSpiral/inputs_ideal` (2), `Exec/CanonicalTests/EkmanSpiral/inputs_input_sounding` (2), `Exec/CanonicalTests/Idealized_Terrain/ScharMountain/inputs` (2), `Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi/inputs_WoA` (2), `Exec/CanonicalTests/Real_Terrain/Altamont/inputs_terrain` (2), `Exec/CanonicalTests/Real_Terrain/Askervein/inputs_anel` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_ml` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Gabersek` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Morrison` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_SAM` (2), `Exec/CanonicalTests/SquallLine_2D/inputs_moisture_WRF` (2), `Exec/CanonicalTests/SuperCell_3D/inputs_moisture_Tissaoui` (2), `Exec/RegTests/Bubble/inputs_BF02_dry_bubble` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Kessler` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Morrison` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_OpenBC` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoIce` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoPrecip_NoIce` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM` (2), `Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM_multi_injections_unimodal_NaCl` (2), `Exec/RegTests/Bubble/inputs_grav2d_x` (2), `Exec/RegTests/Bubble/inputs_squall2d_x` (2), `Exec/RegTests/Bubble/inputs_test_outflow` (2), `Exec/RegTests/Couette_Poiseuille/inputs_couette_x` (2), `Exec/RegTests/Couette_Poiseuille/inputs_couette_y` (2), `Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_x` (2), `Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_y` (2), `Exec/RegTests/EB_Poiseuille/inputs_compressible` (2), `Exec/RegTests/EB_SquareCylinder/inputs_anelastic` (2), `Exec/RegTests/EB_SquareCylinder/inputs_multilevel` (2), `Exec/RegTests/FlowInABox/inputs` (2), `Exec/RegTests/ImmersedForcingTest/inputs_if_building` (2), `Exec/RegTests/ImmersedForcingTest/inputs_if_terrain` (2), `Exec/RegTests/ImmersedForcingTest/inputs_if_terrain_plusBuilding` (2), `Exec/RegTests/InitFromNCFile/inputs` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting_ml` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting_msf` (2), `Exec/RegTests/IsentropicVortex/inputs_advecting_no_msf` (2), `Exec/RegTests/IsentropicVortex/inputs_stationary` (2), `Exec/RegTests/IsentropicVortex/inputs_stationary_msf` (2), `Exec/RegTests/IsentropicVortex/inputs_stationary_no_msf` (2), `Exec/RegTests/MetGrid/inputs_metgrid` (2), `Exec/RegTests/MovingTerrain/inputs` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.01species` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.02species` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.01species` (2), `Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.02species` (2), `Exec/RegTests/ParticleTests/inputs_over_flat` (2), `Exec/RegTests/ParticleTests/inputs_over_hill` (2), `Exec/RegTests/Radiation/inputs_radiation` (2), `Exec/RegTests/ScalarAdvDiff/inputs_WENO` (2), `Exec/RegTests/ScalarAdvDiff/inputs_WENO_Z` (2), `Exec/RegTests/ScalarAdvDiff/inputs_adv_diff_uniformU` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advdiffinflowoutflow` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_no_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_no_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_gaussian` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_no_msf` (2), `Exec/RegTests/ScalarAdvDiff/inputs_diffuse_sine` (2), `Exec/RegTests/ScalarAdvDiff/inputs_ml` (2), `Exec/RegTests/ScalarAdvDiff/inputs_test_rayleigh` (2), `Exec/RegTests/SineMassFlux/inputs_SDM_condBE` (2), `Exec/RegTests/StokesSecondProblem/inputs` (2), `Exec/RegTests/StokesSecondProblem/inputs_stretched_z_levels` (2), `Exec/RegTests/TaylorGreenVortex/inputs_advdiff` (2), `Exec/RegTests/TaylorGreenVortex/inputs_advonly` (2), `Exec/RegTests/TaylorGreenVortex/inputs_multilevel` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs_most_test` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs_stretched_z_levels` (2), `Exec/RegTests/Terrain2d_Cylinder/inputs_verification_final` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_EB` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_EB_twolevel` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_FittedMesh` (2), `Exec/RegTests/Terrain3d_Hemisphere/inputs_most_test` (2), `Exec/RegTests/TurbulentInflow/inputs_multilevel_ABL_source` (2), `Exec/RegTests/WPS_Test/inputs_wps` (2), `Exec/RegTests/WPS_Test/inputs_wps_noahmp` (2), `Exec/RegTests/WitchOfAgnesi/inputs` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic_twolevel` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_multilevel` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_x` (2), `Exec/RegTests/WitchOfAgnesi/inputs_EB_y` (2), `Exec/RegTests/WitchOfAgnesi/inputs_FittedMesh` (2), `Exec/RegTests/WitchOfAgnesi/inputs_most_test` (2), `Exec/RegTests/WitchOfAgnesi/inputs_static_twolevel` (2), `Exec/RegTests/WitchOfAgnesi/inputs_zlevels` (2)

First 5 rows (selected fields):
```json
[
  {
    "row_id": "9d54aad7fa6c374f",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_DataSampler",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_DataSampler",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_DataSampler",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_DataSampler",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 1
  },
  {
    "row_id": "5d00f979d031dfe3",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_deardorff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_GABLS1_deardorff",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 2
  },
  {
    "row_id": "224c4249dd7298ca",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_mynn25",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_GABLS1_mynn25",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 3
  },
  {
    "row_id": "86d89bc4b0195acd",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_ysu",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_GABLS1_ysu",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_ysu",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_GABLS1_ysu",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 4
  },
  {
    "row_id": "c7efaf20e3f6a4ad",
    "strategy": "simple",
    "category": "CanonicalTests",
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_anel_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_filename": "inputs_anel_most",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_anel_most",
    "selected_case": "Exec/CanonicalTests/ABL",
    "selected_inputs": "Exec/CanonicalTests/ABL/inputs_anel_most",
    "case_match": 1,
    "inputs_match": 1,
    "wave_id": "wave0",
    "_line_no": 5
  }
]
```
Last 5 rows (selected fields):
```json
[
  {
    "row_id": "8bb187ab2fe052ee",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_y",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_EB_y",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_y",
    "selected_case": "Exec/RegTests/Terrain3d_Hemisphere",
    "selected_inputs": "Exec/RegTests/Terrain3d_Hemisphere/inputs",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 268
  },
  {
    "row_id": "096e193d4c26a46f",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_FittedMesh",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_FittedMesh",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_FittedMesh",
    "selected_case": "Exec/RegTests/Terrain3d_Hemisphere",
    "selected_inputs": "Exec/RegTests/Terrain3d_Hemisphere/inputs",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 269
  },
  {
    "row_id": "8713bb629c310ac3",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_most_test",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_most_test",
    "selected_case": "Exec/Production/PistonBowl",
    "selected_inputs": "Exec/Production/PistonBowl/inputs/example.inp",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 270
  },
  {
    "row_id": "6c5555e3ba011821",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_static_twolevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_static_twolevel",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_static_twolevel",
    "selected_case": "Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi",
    "selected_inputs": "Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi/inputs_WoA",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 271
  },
  {
    "row_id": "8f109351917b36ed",
    "strategy": "hierarchical",
    "category": "RegTests",
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_zlevels",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_filename": "inputs_zlevels",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_zlevels",
    "selected_case": "Exec/Production/NormalJet_OpenDomain",
    "selected_inputs": "Exec/Production/NormalJet_OpenDomain/inputs.3d-regt",
    "case_match": 0,
    "inputs_match": 0,
    "wave_id": "wave0",
    "_line_no": 272
  }
]
```

## Step 3 — Input Consistency Across Result Sets
| Result Set | Total Rows | Unique Prompt Strings | Strategy Counts |
| --- | --- | --- | --- |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | 176 | 88 | hierarchical:88, simple:88 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | 48 | 24 | hierarchical:24, simple:24 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 272 | 136 | hierarchical:136, simple:136 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 272 | 136 | hierarchical:136, simple:136 |

Prompt set overlap (pairwise intersection counts):
| Set A | Set B | Shared Prompt Count | Shared/A | Shared/B |
| --- | --- | --- | --- | --- |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | 0 | 0/88 | 0/24 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 0 | 0/88 | 0/136 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 0 | 0/88 | 0/136 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 0 | 0/24 | 0/136 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 0 | 0/24 | 0/136 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 136 | 136/136 | 136/136 |

Rows that differ across sets (canonical key = prompt_text + target_case_relpath + target_inputs_relpath + strategy):
- Total canonical rows in union: `496`
- Rows not present in all four sets: `496`

Detailed diff listing (all rows that appear in some sets but not others):
```json
[
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_DataSampler",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_DataSampler",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_DataSampler",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_DataSampler",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_deardorff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_deardorff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_deardorff",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_mynn25",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_mynn25",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_mynn25",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_ysu",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_ysu",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_GABLS1_ysu",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_GABLS1_ysu",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_anel_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_anel_most",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_anel_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_anel_most",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_canopy",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_canopy",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_canopy",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_canopy",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_deardorff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_deardorff",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_deardorff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_deardorff",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_deardorff_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_deardorff_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_deardorff_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_deardorff_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_deardorff_no_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_deardorff_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_deardorff_no_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_deardorff_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_ml_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_ml_most",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_ml_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_ml_most",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_bomex",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_bomex",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_bomex",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_bomex",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_no_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_no_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_pbl",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_pbl",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_pbl",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_pbl",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_test",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_test",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_most_test",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_most_test",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_numdiff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_numdiff",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_numdiff",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_numdiff",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_omp",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_omp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_omp",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_omp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_sample",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_sample",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_sample",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_sample",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_smagorinsky",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_smagorinsky",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_smagorinsky",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_smagorinsky",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_smagorinsky_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_smagorinsky_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_smagorinsky_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_smagorinsky_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_smagorinsky_no_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_smagorinsky_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_smagorinsky_no_msf",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_smagorinsky_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_terrain",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_terrain",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_terrain",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_terrain",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_vel_avg",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_vel_avg",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/ABL with inputs_vel_avg",
    "target_case_relpath": "Exec/CanonicalTests/ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/ABL/inputs_vel_avg",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Convective_ABL with inputs_specified_flux",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_flux",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Convective_ABL with inputs_specified_flux",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_flux",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Convective_ABL with inputs_specified_heating_rate",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_heating_rate",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Convective_ABL with inputs_specified_heating_rate",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Convective_ABL/inputs_specified_heating_rate",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Neutral_ABL with inputs_anelastic",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_anelastic",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Neutral_ABL with inputs_anelastic",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_anelastic",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Neutral_ABL with inputs_compressible",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_compressible",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Neutral_ABL with inputs_compressible",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Neutral_ABL/inputs_compressible",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Stable_ABL with inputs_with_const_massflux",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Stable_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Stable_ABL/inputs_with_const_massflux",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Canonical_LES/Stable_ABL with inputs_with_const_massflux",
    "target_case_relpath": "Exec/CanonicalTests/Canonical_LES/Stable_ABL",
    "target_inputs_relpath": "Exec/CanonicalTests/Canonical_LES/Stable_ABL/inputs_with_const_massflux",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Channel_DNS with inputs_channel",
    "target_case_relpath": "Exec/CanonicalTests/Channel_DNS",
    "target_inputs_relpath": "Exec/CanonicalTests/Channel_DNS/inputs_channel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Channel_DNS with inputs_channel",
    "target_case_relpath": "Exec/CanonicalTests/Channel_DNS",
    "target_inputs_relpath": "Exec/CanonicalTests/Channel_DNS/inputs_channel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_amr",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_amr",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_amr",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_amr",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_crse_halfdomain",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_crse_halfdomain",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_crse_halfdomain_zlev",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain_zlev",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_crse_halfdomain_zlev",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_crse_halfdomain_zlev",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_fft",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_fft",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_fft",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_fft",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_hybrid",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_hybrid",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_hybrid",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_hybrid",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_hybrid_zlev",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_hybrid_zlev",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_hybrid_zlev",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_hybrid_zlev",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_refsoln",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_refsoln",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_refsoln",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_refsoln",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_wrf_baseline",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_wrf_baseline",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/DensityCurrent with inputs_wrf_baseline",
    "target_case_relpath": "Exec/CanonicalTests/DensityCurrent",
    "target_inputs_relpath": "Exec/CanonicalTests/DensityCurrent/inputs_wrf_baseline",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/EkmanSpiral with inputs_custom",
    "target_case_relpath": "Exec/CanonicalTests/EkmanSpiral",
    "target_inputs_relpath": "Exec/CanonicalTests/EkmanSpiral/inputs_custom",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/EkmanSpiral with inputs_custom",
    "target_case_relpath": "Exec/CanonicalTests/EkmanSpiral",
    "target_inputs_relpath": "Exec/CanonicalTests/EkmanSpiral/inputs_custom",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/EkmanSpiral with inputs_ideal",
    "target_case_relpath": "Exec/CanonicalTests/EkmanSpiral",
    "target_inputs_relpath": "Exec/CanonicalTests/EkmanSpiral/inputs_ideal",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/EkmanSpiral with inputs_ideal",
    "target_case_relpath": "Exec/CanonicalTests/EkmanSpiral",
    "target_inputs_relpath": "Exec/CanonicalTests/EkmanSpiral/inputs_ideal",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/EkmanSpiral with inputs_input_sounding",
    "target_case_relpath": "Exec/CanonicalTests/EkmanSpiral",
    "target_inputs_relpath": "Exec/CanonicalTests/EkmanSpiral/inputs_input_sounding",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/EkmanSpiral with inputs_input_sounding",
    "target_case_relpath": "Exec/CanonicalTests/EkmanSpiral",
    "target_inputs_relpath": "Exec/CanonicalTests/EkmanSpiral/inputs_input_sounding",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Idealized_Terrain/ScharMountain with inputs",
    "target_case_relpath": "Exec/CanonicalTests/Idealized_Terrain/ScharMountain",
    "target_inputs_relpath": "Exec/CanonicalTests/Idealized_Terrain/ScharMountain/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Idealized_Terrain/ScharMountain with inputs",
    "target_case_relpath": "Exec/CanonicalTests/Idealized_Terrain/ScharMountain",
    "target_inputs_relpath": "Exec/CanonicalTests/Idealized_Terrain/ScharMountain/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi with inputs_WoA",
    "target_case_relpath": "Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi/inputs_WoA",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi with inputs_WoA",
    "target_case_relpath": "Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/CanonicalTests/Idealized_Terrain/WitchOfAgnesi/inputs_WoA",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Real_Terrain/Altamont with inputs_terrain",
    "target_case_relpath": "Exec/CanonicalTests/Real_Terrain/Altamont",
    "target_inputs_relpath": "Exec/CanonicalTests/Real_Terrain/Altamont/inputs_terrain",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Real_Terrain/Altamont with inputs_terrain",
    "target_case_relpath": "Exec/CanonicalTests/Real_Terrain/Altamont",
    "target_inputs_relpath": "Exec/CanonicalTests/Real_Terrain/Altamont/inputs_terrain",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Real_Terrain/Askervein with inputs_anel",
    "target_case_relpath": "Exec/CanonicalTests/Real_Terrain/Askervein",
    "target_inputs_relpath": "Exec/CanonicalTests/Real_Terrain/Askervein/inputs_anel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/Real_Terrain/Askervein with inputs_anel",
    "target_case_relpath": "Exec/CanonicalTests/Real_Terrain/Askervein",
    "target_inputs_relpath": "Exec/CanonicalTests/Real_Terrain/Askervein/inputs_anel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_ml",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_ml",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_ml",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_ml",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_Gabersek",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Gabersek",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_Gabersek",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Gabersek",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_Morrison",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Morrison",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_Morrison",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_Morrison",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_SAM",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_SAM",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_SAM",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_SAM",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_WRF",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_WRF",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SquallLine_2D with inputs_moisture_WRF",
    "target_case_relpath": "Exec/CanonicalTests/SquallLine_2D",
    "target_inputs_relpath": "Exec/CanonicalTests/SquallLine_2D/inputs_moisture_WRF",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SuperCell_3D with inputs_moisture_Tissaoui",
    "target_case_relpath": "Exec/CanonicalTests/SuperCell_3D",
    "target_inputs_relpath": "Exec/CanonicalTests/SuperCell_3D/inputs_moisture_Tissaoui",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/CanonicalTests/SuperCell_3D with inputs_moisture_Tissaoui",
    "target_case_relpath": "Exec/CanonicalTests/SuperCell_3D",
    "target_inputs_relpath": "Exec/CanonicalTests/SuperCell_3D/inputs_moisture_Tissaoui",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_dry_bubble",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_dry_bubble",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_dry_bubble",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_dry_bubble",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_Kessler",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Kessler",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_Kessler",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Kessler",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_Morrison",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Morrison",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_Morrison",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_Morrison",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_OpenBC",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_OpenBC",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_OpenBC",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_OpenBC",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SAM",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SAM",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SAM_NoIce",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoIce",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SAM_NoIce",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoIce",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SAM_NoPrecip_NoIce",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoPrecip_NoIce",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SAM_NoPrecip_NoIce",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SAM_NoPrecip_NoIce",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SDM",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SDM",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SDM_multi_injections_unimodal_NaCl",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM_multi_injections_unimodal_NaCl",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_BF02_moist_bubble_SDM_multi_injections_unimodal_NaCl",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_BF02_moist_bubble_SDM_multi_injections_unimodal_NaCl",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_grav2d_x",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_grav2d_x",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_grav2d_x",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_grav2d_x",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_squall2d_x",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_squall2d_x",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_squall2d_x",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_squall2d_x",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_test_outflow",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_test_outflow",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Bubble with inputs_test_outflow",
    "target_case_relpath": "Exec/RegTests/Bubble",
    "target_inputs_relpath": "Exec/RegTests/Bubble/inputs_test_outflow",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_couette_x",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_couette_x",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_couette_x",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_couette_x",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_couette_y",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_couette_y",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_couette_y",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_couette_y",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_poiseuille_x",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_x",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_poiseuille_x",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_x",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_poiseuille_y",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_y",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Couette_Poiseuille with inputs_poiseuille_y",
    "target_case_relpath": "Exec/RegTests/Couette_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/Couette_Poiseuille/inputs_poiseuille_y",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/EB_Poiseuille with inputs_compressible",
    "target_case_relpath": "Exec/RegTests/EB_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/EB_Poiseuille/inputs_compressible",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/EB_Poiseuille with inputs_compressible",
    "target_case_relpath": "Exec/RegTests/EB_Poiseuille",
    "target_inputs_relpath": "Exec/RegTests/EB_Poiseuille/inputs_compressible",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/EB_SquareCylinder with inputs_anelastic",
    "target_case_relpath": "Exec/RegTests/EB_SquareCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_SquareCylinder/inputs_anelastic",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/EB_SquareCylinder with inputs_anelastic",
    "target_case_relpath": "Exec/RegTests/EB_SquareCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_SquareCylinder/inputs_anelastic",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/EB_SquareCylinder with inputs_multilevel",
    "target_case_relpath": "Exec/RegTests/EB_SquareCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_SquareCylinder/inputs_multilevel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/EB_SquareCylinder with inputs_multilevel",
    "target_case_relpath": "Exec/RegTests/EB_SquareCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_SquareCylinder/inputs_multilevel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/FlowInABox with inputs",
    "target_case_relpath": "Exec/RegTests/FlowInABox",
    "target_inputs_relpath": "Exec/RegTests/FlowInABox/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/FlowInABox with inputs",
    "target_case_relpath": "Exec/RegTests/FlowInABox",
    "target_inputs_relpath": "Exec/RegTests/FlowInABox/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ImmersedForcingTest with inputs_if_building",
    "target_case_relpath": "Exec/RegTests/ImmersedForcingTest",
    "target_inputs_relpath": "Exec/RegTests/ImmersedForcingTest/inputs_if_building",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ImmersedForcingTest with inputs_if_building",
    "target_case_relpath": "Exec/RegTests/ImmersedForcingTest",
    "target_inputs_relpath": "Exec/RegTests/ImmersedForcingTest/inputs_if_building",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ImmersedForcingTest with inputs_if_terrain",
    "target_case_relpath": "Exec/RegTests/ImmersedForcingTest",
    "target_inputs_relpath": "Exec/RegTests/ImmersedForcingTest/inputs_if_terrain",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ImmersedForcingTest with inputs_if_terrain",
    "target_case_relpath": "Exec/RegTests/ImmersedForcingTest",
    "target_inputs_relpath": "Exec/RegTests/ImmersedForcingTest/inputs_if_terrain",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ImmersedForcingTest with inputs_if_terrain_plusBuilding",
    "target_case_relpath": "Exec/RegTests/ImmersedForcingTest",
    "target_inputs_relpath": "Exec/RegTests/ImmersedForcingTest/inputs_if_terrain_plusBuilding",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ImmersedForcingTest with inputs_if_terrain_plusBuilding",
    "target_case_relpath": "Exec/RegTests/ImmersedForcingTest",
    "target_inputs_relpath": "Exec/RegTests/ImmersedForcingTest/inputs_if_terrain_plusBuilding",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/InitFromNCFile with inputs",
    "target_case_relpath": "Exec/RegTests/InitFromNCFile",
    "target_inputs_relpath": "Exec/RegTests/InitFromNCFile/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/InitFromNCFile with inputs",
    "target_case_relpath": "Exec/RegTests/InitFromNCFile",
    "target_inputs_relpath": "Exec/RegTests/InitFromNCFile/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting_ml",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting_ml",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting_ml",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting_ml",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting_no_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_advecting_no_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_advecting_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_stationary",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_stationary",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_stationary",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_stationary",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_stationary_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_stationary_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_stationary_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_stationary_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_stationary_no_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_stationary_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/IsentropicVortex with inputs_stationary_no_msf",
    "target_case_relpath": "Exec/RegTests/IsentropicVortex",
    "target_inputs_relpath": "Exec/RegTests/IsentropicVortex/inputs_stationary_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MetGrid with inputs_metgrid",
    "target_case_relpath": "Exec/RegTests/MetGrid",
    "target_inputs_relpath": "Exec/RegTests/MetGrid/inputs_metgrid",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MetGrid with inputs_metgrid",
    "target_case_relpath": "Exec/RegTests/MetGrid",
    "target_inputs_relpath": "Exec/RegTests/MetGrid/inputs_metgrid",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MovingTerrain with inputs",
    "target_case_relpath": "Exec/RegTests/MovingTerrain",
    "target_inputs_relpath": "Exec/RegTests/MovingTerrain/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MovingTerrain with inputs",
    "target_case_relpath": "Exec/RegTests/MovingTerrain",
    "target_inputs_relpath": "Exec/RegTests/MovingTerrain/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_dry_bubble.01species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.01species",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_dry_bubble.01species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.01species",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_dry_bubble.02species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.02species",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_dry_bubble.02species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_dry_bubble.02species",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_moist_bubble.01species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.01species",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_moist_bubble.01species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.01species",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_moist_bubble.02species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.02species",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/MultiSpeciesBubble with inputs_moist_bubble.02species",
    "target_case_relpath": "Exec/RegTests/MultiSpeciesBubble",
    "target_inputs_relpath": "Exec/RegTests/MultiSpeciesBubble/inputs_moist_bubble.02species",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ParticleTests with inputs_over_flat",
    "target_case_relpath": "Exec/RegTests/ParticleTests",
    "target_inputs_relpath": "Exec/RegTests/ParticleTests/inputs_over_flat",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ParticleTests with inputs_over_flat",
    "target_case_relpath": "Exec/RegTests/ParticleTests",
    "target_inputs_relpath": "Exec/RegTests/ParticleTests/inputs_over_flat",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ParticleTests with inputs_over_hill",
    "target_case_relpath": "Exec/RegTests/ParticleTests",
    "target_inputs_relpath": "Exec/RegTests/ParticleTests/inputs_over_hill",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ParticleTests with inputs_over_hill",
    "target_case_relpath": "Exec/RegTests/ParticleTests",
    "target_inputs_relpath": "Exec/RegTests/ParticleTests/inputs_over_hill",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Radiation with inputs_radiation",
    "target_case_relpath": "Exec/RegTests/Radiation",
    "target_inputs_relpath": "Exec/RegTests/Radiation/inputs_radiation",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Radiation with inputs_radiation",
    "target_case_relpath": "Exec/RegTests/Radiation",
    "target_inputs_relpath": "Exec/RegTests/Radiation/inputs_radiation",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_WENO",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_WENO",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_WENO",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_WENO",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_WENO_Z",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_WENO_Z",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_WENO_Z",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_WENO_Z",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_adv_diff_uniformU",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_adv_diff_uniformU",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_adv_diff_uniformU",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_adv_diff_uniformU",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advdiffinflowoutflow",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advdiffinflowoutflow",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advdiffinflowoutflow",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advdiffinflowoutflow",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_shearU",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_shearU",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_shearU_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_shearU_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_shearU_no_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_shearU_no_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_shearU_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_uniformU",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_uniformU",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_uniformU_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_uniformU_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_uniformU_no_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_advect_uniformU_no_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_advect_uniformU_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_gaussian",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_gaussian",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_gaussian",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_gaussian",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_no_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_no_msf",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_no_msf",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_no_msf",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_sine",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_sine",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_diffuse_sine",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_diffuse_sine",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_ml",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_ml",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_ml",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_ml",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_test_rayleigh",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_test_rayleigh",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/ScalarAdvDiff with inputs_test_rayleigh",
    "target_case_relpath": "Exec/RegTests/ScalarAdvDiff",
    "target_inputs_relpath": "Exec/RegTests/ScalarAdvDiff/inputs_test_rayleigh",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/SineMassFlux with inputs_SDM_condBE",
    "target_case_relpath": "Exec/RegTests/SineMassFlux",
    "target_inputs_relpath": "Exec/RegTests/SineMassFlux/inputs_SDM_condBE",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/SineMassFlux with inputs_SDM_condBE",
    "target_case_relpath": "Exec/RegTests/SineMassFlux",
    "target_inputs_relpath": "Exec/RegTests/SineMassFlux/inputs_SDM_condBE",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/StokesSecondProblem with inputs",
    "target_case_relpath": "Exec/RegTests/StokesSecondProblem",
    "target_inputs_relpath": "Exec/RegTests/StokesSecondProblem/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/StokesSecondProblem with inputs",
    "target_case_relpath": "Exec/RegTests/StokesSecondProblem",
    "target_inputs_relpath": "Exec/RegTests/StokesSecondProblem/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/StokesSecondProblem with inputs_stretched_z_levels",
    "target_case_relpath": "Exec/RegTests/StokesSecondProblem",
    "target_inputs_relpath": "Exec/RegTests/StokesSecondProblem/inputs_stretched_z_levels",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/StokesSecondProblem with inputs_stretched_z_levels",
    "target_case_relpath": "Exec/RegTests/StokesSecondProblem",
    "target_inputs_relpath": "Exec/RegTests/StokesSecondProblem/inputs_stretched_z_levels",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TaylorGreenVortex with inputs_advdiff",
    "target_case_relpath": "Exec/RegTests/TaylorGreenVortex",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreenVortex/inputs_advdiff",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TaylorGreenVortex with inputs_advdiff",
    "target_case_relpath": "Exec/RegTests/TaylorGreenVortex",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreenVortex/inputs_advdiff",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TaylorGreenVortex with inputs_advonly",
    "target_case_relpath": "Exec/RegTests/TaylorGreenVortex",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreenVortex/inputs_advonly",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TaylorGreenVortex with inputs_advonly",
    "target_case_relpath": "Exec/RegTests/TaylorGreenVortex",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreenVortex/inputs_advonly",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TaylorGreenVortex with inputs_multilevel",
    "target_case_relpath": "Exec/RegTests/TaylorGreenVortex",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreenVortex/inputs_multilevel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TaylorGreenVortex with inputs_multilevel",
    "target_case_relpath": "Exec/RegTests/TaylorGreenVortex",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreenVortex/inputs_multilevel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs_most_test",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs_most_test",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs_stretched_z_levels",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs_stretched_z_levels",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs_stretched_z_levels",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs_stretched_z_levels",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs_verification_final",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs_verification_final",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain2d_Cylinder with inputs_verification_final",
    "target_case_relpath": "Exec/RegTests/Terrain2d_Cylinder",
    "target_inputs_relpath": "Exec/RegTests/Terrain2d_Cylinder/inputs_verification_final",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_EB",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_EB",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_EB",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_EB",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_EB_twolevel",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_EB_twolevel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_EB_twolevel",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_EB_twolevel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_FittedMesh",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_FittedMesh",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_FittedMesh",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_FittedMesh",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_most_test",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/Terrain3d_Hemisphere with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/Terrain3d_Hemisphere",
    "target_inputs_relpath": "Exec/RegTests/Terrain3d_Hemisphere/inputs_most_test",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TurbulentInflow with inputs_multilevel_ABL_source",
    "target_case_relpath": "Exec/RegTests/TurbulentInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbulentInflow/inputs_multilevel_ABL_source",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/TurbulentInflow with inputs_multilevel_ABL_source",
    "target_case_relpath": "Exec/RegTests/TurbulentInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbulentInflow/inputs_multilevel_ABL_source",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WPS_Test with inputs_wps",
    "target_case_relpath": "Exec/RegTests/WPS_Test",
    "target_inputs_relpath": "Exec/RegTests/WPS_Test/inputs_wps",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WPS_Test with inputs_wps",
    "target_case_relpath": "Exec/RegTests/WPS_Test",
    "target_inputs_relpath": "Exec/RegTests/WPS_Test/inputs_wps",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WPS_Test with inputs_wps_noahmp",
    "target_case_relpath": "Exec/RegTests/WPS_Test",
    "target_inputs_relpath": "Exec/RegTests/WPS_Test/inputs_wps_noahmp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WPS_Test with inputs_wps_noahmp",
    "target_case_relpath": "Exec/RegTests/WPS_Test",
    "target_inputs_relpath": "Exec/RegTests/WPS_Test/inputs_wps_noahmp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_anelastic",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_anelastic",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_anelastic_twolevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic_twolevel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_anelastic_twolevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_anelastic_twolevel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_multilevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_multilevel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_multilevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_multilevel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_x",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_x",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_x",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_x",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_y",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_y",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_EB_y",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_EB_y",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_FittedMesh",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_FittedMesh",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_FittedMesh",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_FittedMesh",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_most_test",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_most_test",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_most_test",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_static_twolevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_static_twolevel",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_static_twolevel",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_static_twolevel",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_zlevels",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_zlevels",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use ERF case Exec/RegTests/WitchOfAgnesi with inputs_zlevels",
    "target_case_relpath": "Exec/RegTests/WitchOfAgnesi",
    "target_inputs_relpath": "Exec/RegTests/WitchOfAgnesi/inputs_zlevels",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl",
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt",
    "target_case_relpath": "Exec/Plasma/FlameSheetIons",
    "target_inputs_relpath": "Exec/Plasma/FlameSheetIons/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt",
    "target_case_relpath": "Exec/Plasma/FlameSheetIons",
    "target_inputs_relpath": "Exec/Plasma/FlameSheetIons/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt_flipped",
    "target_case_relpath": "Exec/Plasma/FlameSheetIons",
    "target_inputs_relpath": "Exec/Plasma/FlameSheetIons/input.2d-regt_flipped",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt_flipped",
    "target_case_relpath": "Exec/Plasma/FlameSheetIons",
    "target_inputs_relpath": "Exec/Plasma/FlameSheetIons/input.2d-regt_flipped",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt",
    "target_case_relpath": "Exec/Plasma/IonizedAirWave",
    "target_inputs_relpath": "Exec/Plasma/IonizedAirWave/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt",
    "target_case_relpath": "Exec/Plasma/IonizedAirWave",
    "target_inputs_relpath": "Exec/Plasma/IonizedAirWave/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt_wave",
    "target_case_relpath": "Exec/Plasma/IonizedAirWave",
    "target_inputs_relpath": "Exec/Plasma/IonizedAirWave/input.2d-regt_wave",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt_wave",
    "target_case_relpath": "Exec/Plasma/IonizedAirWave",
    "target_inputs_relpath": "Exec/Plasma/IonizedAirWave/input.2d-regt_wave",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_lean",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_lean",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_lean",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_lean",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_rich",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_rich",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_rich",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_rich",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_stoich",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_stoich",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_stoich_EF",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich_EF",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_stoich_EF",
    "target_case_relpath": "Exec/Plasma/PremBunsen3DKuhl",
    "target_inputs_relpath": "Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich_EF",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/ChallengeProblem with input.3d",
    "target_case_relpath": "Exec/Production/ChallengeProblem",
    "target_inputs_relpath": "Exec/Production/ChallengeProblem/input.3d",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/ChallengeProblem with input.3d",
    "target_case_relpath": "Exec/Production/ChallengeProblem",
    "target_inputs_relpath": "Exec/Production/ChallengeProblem/input.3d",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/ChallengeProblem with input.3d_Hypre",
    "target_case_relpath": "Exec/Production/ChallengeProblem",
    "target_inputs_relpath": "Exec/Production/ChallengeProblem/input.3d_Hypre",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/ChallengeProblem with input.3d_Hypre",
    "target_case_relpath": "Exec/Production/ChallengeProblem",
    "target_inputs_relpath": "Exec/Production/ChallengeProblem/input.3d_Hypre",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/CounterFlow with input.2d-regt",
    "target_case_relpath": "Exec/Production/CounterFlow",
    "target_inputs_relpath": "Exec/Production/CounterFlow/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/CounterFlow with input.2d-regt",
    "target_case_relpath": "Exec/Production/CounterFlow",
    "target_inputs_relpath": "Exec/Production/CounterFlow/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/CounterFlow with input_coolflow.2d-regt",
    "target_case_relpath": "Exec/Production/CounterFlow",
    "target_inputs_relpath": "Exec/Production/CounterFlow/input_coolflow.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/CounterFlow with input_coolflow.2d-regt",
    "target_case_relpath": "Exec/Production/CounterFlow",
    "target_inputs_relpath": "Exec/Production/CounterFlow/input_coolflow.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/CounterFlowSpray with input.2d-regt",
    "target_case_relpath": "Exec/Production/CounterFlowSpray",
    "target_inputs_relpath": "Exec/Production/CounterFlowSpray/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/CounterFlowSpray with input.2d-regt",
    "target_case_relpath": "Exec/Production/CounterFlowSpray",
    "target_inputs_relpath": "Exec/Production/CounterFlowSpray/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/DiffBunsen2D with input.2d-regt",
    "target_case_relpath": "Exec/Production/DiffBunsen2D",
    "target_inputs_relpath": "Exec/Production/DiffBunsen2D/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/DiffBunsen2D with input.2d-regt",
    "target_case_relpath": "Exec/Production/DiffBunsen2D",
    "target_inputs_relpath": "Exec/Production/DiffBunsen2D/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input.3d",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input.3d",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input.3d",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input.3d",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input.3d_reacting",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input.3d_reacting",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input.3d_reacting",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input.3d_reacting",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_all.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_all.inp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_all.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_all.inp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_les_additions.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_les_additions.inp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_les_additions.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_les_additions.inp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_reacting_additions.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_reacting_additions.inp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_reacting_additions.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_reacting_additions.inp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_turbinflow_additions.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_turbinflow_additions.inp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/JetInCrossflow with input_turbinflow_additions.inp",
    "target_case_relpath": "Exec/Production/JetInCrossflow",
    "target_inputs_relpath": "Exec/Production/JetInCrossflow/input_turbinflow_additions.inp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/NormalJet_OpenDomain with inputs.3d-regt",
    "target_case_relpath": "Exec/Production/NormalJet_OpenDomain",
    "target_inputs_relpath": "Exec/Production/NormalJet_OpenDomain/inputs.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/NormalJet_OpenDomain with inputs.3d-regt",
    "target_case_relpath": "Exec/Production/NormalJet_OpenDomain",
    "target_inputs_relpath": "Exec/Production/NormalJet_OpenDomain/inputs.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/PremBunsen2D with input.2d-regt",
    "target_case_relpath": "Exec/Production/PremBunsen2D",
    "target_inputs_relpath": "Exec/Production/PremBunsen2D/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/PremBunsen2D with input.2d-regt",
    "target_case_relpath": "Exec/Production/PremBunsen2D",
    "target_inputs_relpath": "Exec/Production/PremBunsen2D/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/PremBunsen3D with input.3d",
    "target_case_relpath": "Exec/Production/PremBunsen3D",
    "target_inputs_relpath": "Exec/Production/PremBunsen3D/input.3d",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/PremBunsen3D with input.3d",
    "target_case_relpath": "Exec/Production/PremBunsen3D",
    "target_inputs_relpath": "Exec/Production/PremBunsen3D/input.3d",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/SwirlFlowWallInteractions with input.3d",
    "target_case_relpath": "Exec/Production/SwirlFlowWallInteractions",
    "target_inputs_relpath": "Exec/Production/SwirlFlowWallInteractions/input.3d",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/Production/SwirlFlowWallInteractions with input.3d",
    "target_case_relpath": "Exec/Production/SwirlFlowWallInteractions",
    "target_inputs_relpath": "Exec/Production/SwirlFlowWallInteractions/input.3d",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedFlame/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedFlame/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.2d-regt_Hypre",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedFlame/input.2d-regt_Hypre",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.2d-regt_Hypre",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedFlame/input.2d-regt_Hypre",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedFlame/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedFlame/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt_Hypre",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.2d-regt_Hypre",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt_Hypre",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.2d-regt_Hypre",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt_incomp",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.2d-regt_incomp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt_incomp",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.2d-regt_incomp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_EnclosedVortex",
    "target_inputs_relpath": "Exec/RegTests/EB_EnclosedVortex/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-Re500",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-Re500",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-Re500",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-Re500",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_HypreMAC",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreMAC",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_HypreMAC",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreMAC",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_HypreNodal",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreNodal",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_HypreNodal",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreNodal",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_WallBump",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_WallBump",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_WallBump",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_WallBump",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_isoT",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_isoT",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_isoT",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_isoT",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regtY",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.3d-regtY",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regtY",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.3d-regtY",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regt_WallBump",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.3d-regt_WallBump",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regt_WallBump",
    "target_case_relpath": "Exec/RegTests/EB_FlowPastCylinder",
    "target_inputs_relpath": "Exec/RegTests/EB_FlowPastCylinder/input.3d-regt_WallBump",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_PipeFlow",
    "target_inputs_relpath": "Exec/RegTests/EB_PipeFlow/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EB_PipeFlow",
    "target_inputs_relpath": "Exec/RegTests/EB_PipeFlow/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.3d-Poiseuille",
    "target_case_relpath": "Exec/RegTests/EB_PipeFlow",
    "target_inputs_relpath": "Exec/RegTests/EB_PipeFlow/input.3d-Poiseuille",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.3d-Poiseuille",
    "target_case_relpath": "Exec/RegTests/EB_PipeFlow",
    "target_inputs_relpath": "Exec/RegTests/EB_PipeFlow/input.3d-Poiseuille",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_PipeFlow",
    "target_inputs_relpath": "Exec/RegTests/EB_PipeFlow/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EB_PipeFlow",
    "target_inputs_relpath": "Exec/RegTests/EB_PipeFlow/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EnclosedFlame with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EnclosedFlame/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EnclosedFlame with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EnclosedFlame/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EnclosedFlame with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EnclosedFlame/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EnclosedFlame with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/EnclosedFlame",
    "target_inputs_relpath": "Exec/RegTests/EnclosedFlame/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EnclosedInjection with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EnclosedInjection",
    "target_inputs_relpath": "Exec/RegTests/EnclosedInjection/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/EnclosedInjection with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/EnclosedInjection",
    "target_inputs_relpath": "Exec/RegTests/EnclosedInjection/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.manifold",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.manifold",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.manifold",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.manifold",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.manifold.cvar",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.manifold.cvar",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with input.manifold.cvar",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/input.manifold.cvar",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with inputs.3d_Dodecane",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/inputs.3d_Dodecane",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with inputs.3d_Dodecane",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/inputs.3d_Dodecane",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with inputs.3d_DodecaneQSS",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/inputs.3d_DodecaneQSS",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/FlameSheet with inputs.3d_DodecaneQSS",
    "target_case_relpath": "Exec/RegTests/FlameSheet",
    "target_inputs_relpath": "Exec/RegTests/FlameSheet/inputs.3d_DodecaneQSS",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt_sym",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.2d-regt_sym",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt_sym",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.2d-regt_sym",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt_symRZ",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.2d-regt_symRZ",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt_symRZ",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.2d-regt_symRZ",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/HotBubble with input.3d-regt",
    "target_case_relpath": "Exec/RegTests/HotBubble",
    "target_inputs_relpath": "Exec/RegTests/HotBubble/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauS",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauS",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauS",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauS",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauSAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauSAMR",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauSAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauSAMR",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauT",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauT",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauT",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauT",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauTAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauTAMR",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauTAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoGauTAMR",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoTanHSAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoTanHSAMR",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoTanHSAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoTanHSAMR",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoTanHTAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoTanHTAMR",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoTanHTAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoTanHTAMR",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVo",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoVo",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVo",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoVo",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVoAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoVoAMR",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVoAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoVoAMR",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVoIncomp",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoVoIncomp",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVoIncomp",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_CoVoIncomp",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauS",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauS",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauS",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauS",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauSAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauSAMR",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauSAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauSAMR",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauSRef",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauSRef",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauSRef",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauSRef",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauT",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauT",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauT",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauT",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauTAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauTAMR",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauTAMR",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.2d_DiffGauTAMR",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_InflowGen",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo_InflowGen",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_InflowGen",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo_InflowGen",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_PlaneInput",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo_PlaneInput",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_PlaneInput",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo_PlaneInput",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_PltInput",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo_PltInput",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_PltInput",
    "target_case_relpath": "Exec/RegTests/PeriodicCases",
    "target_inputs_relpath": "Exec/RegTests/PeriodicCases/input.3d_CoVo_PltInput",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/SprayTest with input.2d",
    "target_case_relpath": "Exec/RegTests/SprayTest",
    "target_inputs_relpath": "Exec/RegTests/SprayTest/input.2d",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/SprayTest with input.2d",
    "target_case_relpath": "Exec/RegTests/SprayTest",
    "target_inputs_relpath": "Exec/RegTests/SprayTest/input.2d",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_BDS",
    "target_case_relpath": "Exec/RegTests/TaylorGreen",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreen/input.3d_BDS",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_BDS",
    "target_case_relpath": "Exec/RegTests/TaylorGreen",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreen/input.3d_BDS",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_PLM",
    "target_case_relpath": "Exec/RegTests/TaylorGreen",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreen/input.3d_PLM",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_PLM",
    "target_case_relpath": "Exec/RegTests/TaylorGreen",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreen/input.3d_PLM",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_PPM",
    "target_case_relpath": "Exec/RegTests/TaylorGreen",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreen/input.3d_PPM",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_PPM",
    "target_case_relpath": "Exec/RegTests/TaylorGreen",
    "target_inputs_relpath": "Exec/RegTests/TaylorGreen/input.3d_PPM",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TripleFlame with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/TripleFlame",
    "target_inputs_relpath": "Exec/RegTests/TripleFlame/input.2d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TripleFlame with input.2d-regt",
    "target_case_relpath": "Exec/RegTests/TripleFlame",
    "target_inputs_relpath": "Exec/RegTests/TripleFlame/input.2d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_BoxLoZ",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_BoxLoZ",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_BoxLoZ",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_BoxLoZ",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_posX",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_posX",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_posX",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_posX",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_twoInjs",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_twoInjs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_twoInjs",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_twoInjs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_twoInjsOverlap",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_twoInjsOverlap",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_twoInjsOverlap",
    "target_case_relpath": "Exec/RegTests/TurbInflow",
    "target_inputs_relpath": "Exec/RegTests/TurbInflow/input.3d_twoInjsOverlap",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/Unit with input",
    "target_case_relpath": "Exec/RegTests/Unit",
    "target_inputs_relpath": "Exec/RegTests/Unit/input",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/Unit with input",
    "target_case_relpath": "Exec/RegTests/Unit",
    "target_inputs_relpath": "Exec/RegTests/Unit/input",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/Unit with input.diffusion",
    "target_case_relpath": "Exec/RegTests/Unit",
    "target_inputs_relpath": "Exec/RegTests/Unit/input.diffusion",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/RegTests/Unit with input.diffusion",
    "target_case_relpath": "Exec/RegTests/Unit",
    "target_inputs_relpath": "Exec/RegTests/Unit/input.diffusion",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/UnitTests/DodecaneLu with inputs.3d",
    "target_case_relpath": "Exec/UnitTests/DodecaneLu",
    "target_inputs_relpath": "Exec/UnitTests/DodecaneLu/inputs.3d",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/UnitTests/DodecaneLu with inputs.3d",
    "target_case_relpath": "Exec/UnitTests/DodecaneLu",
    "target_inputs_relpath": "Exec/UnitTests/DodecaneLu/inputs.3d",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/UnitTests/EB_SphericalFlame with input.3d-regt",
    "target_case_relpath": "Exec/UnitTests/EB_SphericalFlame",
    "target_inputs_relpath": "Exec/UnitTests/EB_SphericalFlame/input.3d-regt",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use PeleLMeX case Exec/UnitTests/EB_SphericalFlame with input.3d-regt",
    "target_case_relpath": "Exec/UnitTests/EB_SphericalFlame",
    "target_inputs_relpath": "Exec/UnitTests/EB_SphericalFlame/input.3d-regt",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Advection with inputs",
    "target_case_relpath": "Exec/Advection",
    "target_inputs_relpath": "Exec/Advection/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Advection with inputs",
    "target_case_relpath": "Exec/Advection",
    "target_inputs_relpath": "Exec/Advection/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Advection with inputs_ml",
    "target_case_relpath": "Exec/Advection",
    "target_inputs_relpath": "Exec/Advection/inputs_ml",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Advection with inputs_ml",
    "target_case_relpath": "Exec/Advection",
    "target_inputs_relpath": "Exec/Advection/inputs_ml",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/BlankProblem with inputs",
    "target_case_relpath": "Exec/BlankProblem",
    "target_inputs_relpath": "Exec/BlankProblem/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/BlankProblem with inputs",
    "target_case_relpath": "Exec/BlankProblem",
    "target_inputs_relpath": "Exec/BlankProblem/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/BoundaryLayer with inputs",
    "target_case_relpath": "Exec/BoundaryLayer",
    "target_inputs_relpath": "Exec/BoundaryLayer/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/BoundaryLayer with inputs",
    "target_case_relpath": "Exec/BoundaryLayer",
    "target_inputs_relpath": "Exec/BoundaryLayer/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Channel_Test with inputs",
    "target_case_relpath": "Exec/Channel_Test",
    "target_inputs_relpath": "Exec/Channel_Test/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Channel_Test with inputs",
    "target_case_relpath": "Exec/Channel_Test",
    "target_inputs_relpath": "Exec/Channel_Test/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Channel_Test with inputs_orlanski",
    "target_case_relpath": "Exec/Channel_Test",
    "target_inputs_relpath": "Exec/Channel_Test/inputs_orlanski",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Channel_Test with inputs_orlanski",
    "target_case_relpath": "Exec/Channel_Test",
    "target_inputs_relpath": "Exec/Channel_Test/inputs_orlanski",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Dogbone with inputs",
    "target_case_relpath": "Exec/Dogbone",
    "target_inputs_relpath": "Exec/Dogbone/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Dogbone with inputs",
    "target_case_relpath": "Exec/Dogbone",
    "target_inputs_relpath": "Exec/Dogbone/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs_ml",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs_ml",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs_ml",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs_ml",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs_ml_mid",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs_ml_mid",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs_ml_mid",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs_ml_mid",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs_ml_quad",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs_ml_quad",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DogboneAnalytic with inputs_ml_quad",
    "target_case_relpath": "Exec/DogboneAnalytic",
    "target_inputs_relpath": "Exec/DogboneAnalytic/inputs_ml_quad",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DoubleGyre with inputs",
    "target_case_relpath": "Exec/DoubleGyre",
    "target_inputs_relpath": "Exec/DoubleGyre/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DoubleGyre with inputs",
    "target_case_relpath": "Exec/DoubleGyre",
    "target_inputs_relpath": "Exec/DoubleGyre/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DoublyPeriodic with inputs",
    "target_case_relpath": "Exec/DoublyPeriodic",
    "target_inputs_relpath": "Exec/DoublyPeriodic/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/DoublyPeriodic with inputs",
    "target_case_relpath": "Exec/DoublyPeriodic",
    "target_inputs_relpath": "Exec/DoublyPeriodic/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_cf_orlanski",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_cf_orlanski",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_cf_orlanski",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_cf_orlanski",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_chapman_flather",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_chapman_flather",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_chapman_flather",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_chapman_flather",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_clim_nudg",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_clim_nudg",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_clim_nudg",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_clim_nudg",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_frc",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_frc",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealMiniGrid with inputs_frc",
    "target_case_relpath": "Exec/IdealMiniGrid",
    "target_inputs_relpath": "Exec/IdealMiniGrid/inputs_frc",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealRivGrid with inputs",
    "target_case_relpath": "Exec/IdealRivGrid",
    "target_inputs_relpath": "Exec/IdealRivGrid/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/IdealRivGrid with inputs",
    "target_case_relpath": "Exec/IdealRivGrid",
    "target_inputs_relpath": "Exec/IdealRivGrid/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/ParticlesOverSeaMount with inputs",
    "target_case_relpath": "Exec/ParticlesOverSeaMount",
    "target_inputs_relpath": "Exec/ParticlesOverSeaMount/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/ParticlesOverSeaMount with inputs",
    "target_case_relpath": "Exec/ParticlesOverSeaMount",
    "target_inputs_relpath": "Exec/ParticlesOverSeaMount/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Seamount with inputs",
    "target_case_relpath": "Exec/Seamount",
    "target_inputs_relpath": "Exec/Seamount/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Seamount with inputs",
    "target_case_relpath": "Exec/Seamount",
    "target_inputs_relpath": "Exec/Seamount/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Upwelling with inputs",
    "target_case_relpath": "Exec/Upwelling",
    "target_inputs_relpath": "Exec/Upwelling/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Upwelling with inputs",
    "target_case_relpath": "Exec/Upwelling",
    "target_inputs_relpath": "Exec/Upwelling/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Upwelling with inputs_gls",
    "target_case_relpath": "Exec/Upwelling",
    "target_inputs_relpath": "Exec/Upwelling/inputs_gls",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Upwelling with inputs_gls",
    "target_case_relpath": "Exec/Upwelling",
    "target_inputs_relpath": "Exec/Upwelling/inputs_gls",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Upwelling_ML with inputs",
    "target_case_relpath": "Exec/Upwelling_ML",
    "target_inputs_relpath": "Exec/Upwelling_ML/inputs",
    "strategy": "hierarchical",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  },
  {
    "prompt_text": "Use REMORA case Exec/Upwelling_ML with inputs",
    "target_case_relpath": "Exec/Upwelling_ML",
    "target_inputs_relpath": "Exec/Upwelling_ML/inputs",
    "strategy": "simple",
    "present_in": [
      "/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    ]
  }
]
```

Missing-row counts by pair (A rows absent from B):
| A | B | Count of A rows missing from B |
| --- | --- | --- |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | 176 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 176 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 176 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | 48 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 48 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 48 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | 272 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | 272 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | 0 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl | 272 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl | 272 |
| /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl | /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl | 0 |

FAISS/retrieval index provenance columns in `results.jsonl`:
- `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl`: present=[]; missing=['faiss_db_path', 'faiss_index', 'retrieval_index', 'index_name', 'run_id', 'timestamp', 'git_sha', 'version']
- `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl`: present=[]; missing=['faiss_db_path', 'faiss_index', 'retrieval_index', 'index_name', 'run_id', 'timestamp', 'git_sha', 'version']
- `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl`: present=[]; missing=['faiss_db_path', 'faiss_index', 'retrieval_index', 'index_name', 'run_id', 'timestamp', 'git_sha', 'version']
- `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl`: present=[]; missing=['faiss_db_path', 'faiss_index', 'retrieval_index', 'index_name', 'run_id', 'timestamp', 'git_sha', 'version']

Run metadata found in companion `summary.json` (git SHA, timestamps, FAISS provenance):
- Result set: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl`
  - summary.json: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/summary.json`
  - audit.started_at: `2026-04-30T19:16:52.735330+00:00`
  - audit.finished_at: `2026-04-30T22:08:07.273170+00:00`
  - audit.git.sha: `0aad617b8b5982445b1498aa69056a2811630a64`
  - audit.git.dirty: `True`
  - audit.faiss_provenance.path: `None`
  - audit.faiss_provenance.digest: `None`
- Result set: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl`
  - summary.json: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/summary.json`
  - audit.started_at: `2026-04-30T18:06:35.236438+00:00`
  - audit.finished_at: `2026-04-30T19:16:52.510752+00:00`
  - audit.git.sha: `0aad617b8b5982445b1498aa69056a2811630a64`
  - audit.git.dirty: `True`
  - audit.faiss_provenance.path: `None`
  - audit.faiss_provenance.digest: `None`
- Result set: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl`
  - summary.json: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/summary.json`
  - audit.started_at: `2026-04-29T16:09:59.618029+00:00`
  - audit.finished_at: `2026-04-29T20:15:31.433186+00:00`
  - audit.git.sha: `6cd45ade15b710c756f4a48acc0e94492fd3adfd`
  - audit.git.dirty: `True`
  - audit.faiss_provenance.path: `None`
  - audit.faiss_provenance.digest: `None`
- Result set: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl`
  - summary.json: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/summary.json`
  - audit.started_at: `2026-04-27T20:21:52.483602+00:00`
  - audit.finished_at: `2026-04-28T17:43:02.432759+00:00`
  - audit.git.sha: `7c42d6029b28eae8e6f272a5ccea54f2e84f2a32`
  - audit.git.dirty: `True`
  - audit.faiss_provenance.path: `None`
  - audit.faiss_provenance.digest: `None`

## Step 4 — PeleLMeX Hierarchical Anomaly Investigation
- Source file: `/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl`
- Hierarchical rows: `88`
- Non-matching hierarchical rows: `76`

Every non-matching hierarchical row:
| row_id | category | input prompt | expected case | returned case | expected inputs | returned inputs | run_directory |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0d1a5f1c84e20e16 | Plasma | Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt | Exec/Plasma/FlameSheetIons | Exec/Plasma/IonizedAirWave | Exec/Plasma/FlameSheetIons/input.2d-regt | Exec/Plasma/IonizedAirWave/input.2d-regt_wave | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_130516_563944 |
| 4d2843a6c6926ca2 | Plasma | Use PeleLMeX case Exec/Plasma/FlameSheetIons with input.2d-regt_flipped | Exec/Plasma/FlameSheetIons | Exec/Plasma/PremBunsen3DKuhl | Exec/Plasma/FlameSheetIons/input.2d-regt_flipped | Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_130621_299915 |
| dc8d8225950a1bfd | Plasma | Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt | Exec/Plasma/IonizedAirWave | Exec/Plasma/PremBunsen3DKuhl | Exec/Plasma/IonizedAirWave/input.2d-regt | Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_130736_311385 |
| 74ba9feb56efd323 | Plasma | Use PeleLMeX case Exec/Plasma/IonizedAirWave with input.2d-regt_wave | Exec/Plasma/IonizedAirWave | Exec/Plasma/PremBunsen3DKuhl | Exec/Plasma/IonizedAirWave/input.2d-regt_wave | Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_130854_497237 |
| d02353d6b44e0dfc | Plasma | Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_stoich_EF | Exec/Plasma/PremBunsen3DKuhl | unknown | Exec/Plasma/PremBunsen3DKuhl/input.3d_stoich_EF |  | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_131108_007055 |
| 99dac579b8333a79 | Production | Use PeleLMeX case Exec/Production/ChallengeProblem with input.3d | Exec/Production/ChallengeProblem | Exec/Production/JetInCrossflow | Exec/Production/ChallengeProblem/input.3d | Exec/Production/JetInCrossflow/input_all.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_131229_969119 |
| 471a7516be79d914 | Production | Use PeleLMeX case Exec/Production/ChallengeProblem with input.3d_Hypre | Exec/Production/ChallengeProblem | Exec/Production/JetInCrossflow | Exec/Production/ChallengeProblem/input.3d_Hypre | Exec/Production/JetInCrossflow/input_all.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_131354_234841 |
| a3c412bc8e5b4e2a | Production | Use PeleLMeX case Exec/Production/CounterFlow with input.2d-regt | Exec/Production/CounterFlow | Exec/Production/JetInCrossflow | Exec/Production/CounterFlow/input.2d-regt | Exec/Production/JetInCrossflow/input_all.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_131532_054780 |
| a548b40389583400 | Production | Use PeleLMeX case Exec/Production/CounterFlow with input_coolflow.2d-regt | Exec/Production/CounterFlow | Exec/Production/JetInCrossflow | Exec/Production/CounterFlow/input_coolflow.2d-regt | Exec/Production/JetInCrossflow/input_all.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_131702_729563 |
| b86076b127faac30 | Production | Use PeleLMeX case Exec/Production/CounterFlowSpray with input.2d-regt | Exec/Production/CounterFlowSpray | Exec/Production/CounterFlow | Exec/Production/CounterFlowSpray/input.2d-regt |  | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical |
| 89332daf7d193cd9 | Production | Use PeleLMeX case Exec/Production/DiffBunsen2D with input.2d-regt | Exec/Production/DiffBunsen2D | Exec/Production/PremBunsen2D | Exec/Production/DiffBunsen2D/input.2d-regt | Exec/Production/PremBunsen2D/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_132140_260808 |
| 8e97a654a7a84af9 | Production | Use PeleLMeX case Exec/Production/JetInCrossflow with input.3d | Exec/Production/JetInCrossflow | Exec/Production/CounterFlow | Exec/Production/JetInCrossflow/input.3d | Exec/Production/CounterFlow/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_132258_960213 |
| 8769622bbdc52fa6 | Production | Use PeleLMeX case Exec/Production/JetInCrossflow with input_all.inp | Exec/Production/JetInCrossflow | Exec/Production/CounterFlow | Exec/Production/JetInCrossflow/input_all.inp | Exec/Production/CounterFlow/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_132733_992380 |
| 9f2098302bb64081 | Production | Use PeleLMeX case Exec/Production/JetInCrossflow with input_les_additions.inp | Exec/Production/JetInCrossflow | Exec/Production/CounterFlow | Exec/Production/JetInCrossflow/input_les_additions.inp | Exec/Production/CounterFlow/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_132912_458866 |
| f9c1e07b987d754c | Production | Use PeleLMeX case Exec/Production/JetInCrossflow with input_reacting_additions.inp | Exec/Production/JetInCrossflow | Exec/Production/CounterFlow | Exec/Production/JetInCrossflow/input_reacting_additions.inp | Exec/Production/CounterFlow/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_133045_900814 |
| 77205646371ac751 | Production | Use PeleLMeX case Exec/Production/JetInCrossflow with input_turbinflow_additions.inp | Exec/Production/JetInCrossflow | Exec/Production/CounterFlow | Exec/Production/JetInCrossflow/input_turbinflow_additions.inp | Exec/Production/CounterFlow/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_133224_267138 |
| 3e97238b2b3292a4 | Production | Use PeleLMeX case Exec/Production/NormalJet_OpenDomain with inputs.3d-regt | Exec/Production/NormalJet_OpenDomain | Exec/Production/JetInCrossflow | Exec/Production/NormalJet_OpenDomain/inputs.3d-regt | Exec/Production/JetInCrossflow/input_all.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_133359_260158 |
| f1c2b38e6e745e67 | Production | Use PeleLMeX case Exec/Production/PremBunsen2D with input.2d-regt | Exec/Production/PremBunsen2D | Exec/Production/PremBunsen3D | Exec/Production/PremBunsen2D/input.2d-regt | Exec/Production/PremBunsen3D/input.3d | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_133519_557008 |
| a08232c609b82853 | Production | Use PeleLMeX case Exec/Production/PremBunsen3D with input.3d | Exec/Production/PremBunsen3D | Exec/Production/PremBunsen2D | Exec/Production/PremBunsen3D/input.3d | Exec/Production/PremBunsen2D/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_133650_517368 |
| 80a26f99b18c5ead | Production | Use PeleLMeX case Exec/Production/SwirlFlowWallInteractions with input.3d | Exec/Production/SwirlFlowWallInteractions | Exec/Production/CounterFlow | Exec/Production/SwirlFlowWallInteractions/input.3d | Exec/Production/CounterFlow/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_133804_450379 |
| e856c6f1d4b83b55 | RegTests | Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.2d-regt | Exec/RegTests/EB_EnclosedFlame | Exec/RegTests/FlameSheet | Exec/RegTests/EB_EnclosedFlame/input.2d-regt |  | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical |
| f43c72cbb1ffd9ff | RegTests | Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.2d-regt_Hypre | Exec/RegTests/EB_EnclosedFlame | Exec/RegTests/FlameSheet | Exec/RegTests/EB_EnclosedFlame/input.2d-regt_Hypre |  | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical |
| 07ce162d1f0c126d | RegTests | Use PeleLMeX case Exec/RegTests/EB_EnclosedFlame with input.3d-regt | Exec/RegTests/EB_EnclosedFlame | Exec/RegTests/FlameSheet | Exec/RegTests/EB_EnclosedFlame/input.3d-regt |  | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical |
| 4390d81337dcb07f | RegTests | Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt | Exec/RegTests/EB_EnclosedVortex | Exec/RegTests/TaylorGreen | Exec/RegTests/EB_EnclosedVortex/input.2d-regt | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_134307_382766 |
| 64b1695328fbeb1f | RegTests | Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt_Hypre | Exec/RegTests/EB_EnclosedVortex | Exec/RegTests/EB_EnclosedFlame | Exec/RegTests/EB_EnclosedVortex/input.2d-regt_Hypre | Exec/RegTests/EB_EnclosedFlame/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_134435_761460 |
| 103944f5fabc2e90 | RegTests | Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.2d-regt_incomp | Exec/RegTests/EB_EnclosedVortex | Exec/RegTests/EB_EnclosedFlame | Exec/RegTests/EB_EnclosedVortex/input.2d-regt_incomp | Exec/RegTests/EB_EnclosedFlame/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_134607_610722 |
| 7229b3475a4b3332 | RegTests | Use PeleLMeX case Exec/RegTests/EB_EnclosedVortex with input.3d-regt | Exec/RegTests/EB_EnclosedVortex | Exec/RegTests/TaylorGreen | Exec/RegTests/EB_EnclosedVortex/input.3d-regt | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_134725_931264 |
| 4704436be144362d | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-Re500 | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/FlameSheet | Exec/RegTests/EB_FlowPastCylinder/input.2d-Re500 | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_134842_217638 |
| e3ea1e7083e74444 | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/FlameSheet | Exec/RegTests/EB_FlowPastCylinder/input.2d-regt | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135010_359901 |
| 5ed803e933104e27 | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_HypreMAC | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/FlameSheet | Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreMAC | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135120_438835 |
| 32c12071b63d7c96 | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_HypreNodal | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/EB_PipeFlow | Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_HypreNodal | Exec/RegTests/EB_PipeFlow/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135236_877667 |
| 6adfaaae367d42f6 | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_WallBump | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/FlameSheet | Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_WallBump | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135351_445360 |
| b5dda3bcb3850b47 | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.2d-regt_isoT | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/FlameSheet | Exec/RegTests/EB_FlowPastCylinder/input.2d-regt_isoT | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135459_152138 |
| a61c3b37f3a725a7 | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regt | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/TaylorGreen | Exec/RegTests/EB_FlowPastCylinder/input.3d-regt | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135603_345181 |
| 817261f3e1fcf60d | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regtY | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/FlameSheet | Exec/RegTests/EB_FlowPastCylinder/input.3d-regtY | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135715_692682 |
| a35aeac2cf2561b4 | RegTests | Use PeleLMeX case Exec/RegTests/EB_FlowPastCylinder with input.3d-regt_WallBump | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/EB_PipeFlow | Exec/RegTests/EB_FlowPastCylinder/input.3d-regt_WallBump | Exec/RegTests/EB_PipeFlow/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_135830_153335 |
| 81953d73b769a039 | RegTests | Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.2d-regt | Exec/RegTests/EB_PipeFlow | Exec/RegTests/FlameSheet | Exec/RegTests/EB_PipeFlow/input.2d-regt | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_140003_564920 |
| b078e084f29dade3 | RegTests | Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.3d-Poiseuille | Exec/RegTests/EB_PipeFlow | Exec/RegTests/EB_FlowPastCylinder | Exec/RegTests/EB_PipeFlow/input.3d-Poiseuille | Exec/RegTests/EB_FlowPastCylinder/input.2d-Re500 | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_140136_257375 |
| 3d5b2437aeed3fe3 | RegTests | Use PeleLMeX case Exec/RegTests/EB_PipeFlow with input.3d-regt | Exec/RegTests/EB_PipeFlow | Exec/RegTests/FlameSheet | Exec/RegTests/EB_PipeFlow/input.3d-regt | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_140306_016268 |
| 14ade9759c1111a4 | RegTests | Use PeleLMeX case Exec/RegTests/EnclosedFlame with input.2d-regt | Exec/RegTests/EnclosedFlame | Exec/RegTests/FlameSheet | Exec/RegTests/EnclosedFlame/input.2d-regt |  | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical |
| e4a6bdb5707115ae | RegTests | Use PeleLMeX case Exec/RegTests/EnclosedFlame with input.3d-regt | Exec/RegTests/EnclosedFlame | Exec/RegTests/FlameSheet | Exec/RegTests/EnclosedFlame/input.3d-regt |  | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical |
| f4ab0af236013934 | RegTests | Use PeleLMeX case Exec/RegTests/EnclosedInjection with input.2d-regt | Exec/RegTests/EnclosedInjection | Exec/RegTests/TaylorGreen | Exec/RegTests/EnclosedInjection/input.2d-regt | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_140725_795150 |
| d5a5b4ddefc9e97d | RegTests | Use PeleLMeX case Exec/RegTests/FlameSheet with input.3d-regt | Exec/RegTests/FlameSheet | Exec/RegTests/TaylorGreen | Exec/RegTests/FlameSheet/input.3d-regt | Exec/RegTests/TaylorGreen/input.3d_PPM | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_140955_649238 |
| 3cc317eee876cd96 | RegTests | Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt | Exec/RegTests/HotBubble | Exec/RegTests/FlameSheet | Exec/RegTests/HotBubble/input.2d-regt | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_141532_055056 |
| 2e128d11df257672 | RegTests | Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt_sym | Exec/RegTests/HotBubble | Exec/RegTests/FlameSheet | Exec/RegTests/HotBubble/input.2d-regt_sym | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_141705_564246 |
| 82d50cbc8f8d0539 | RegTests | Use PeleLMeX case Exec/RegTests/HotBubble with input.2d-regt_symRZ | Exec/RegTests/HotBubble | Exec/RegTests/FlameSheet | Exec/RegTests/HotBubble/input.2d-regt_symRZ | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_141812_031914 |
| 37a236b489e90b61 | RegTests | Use PeleLMeX case Exec/RegTests/HotBubble with input.3d-regt | Exec/RegTests/HotBubble | Exec/RegTests/TaylorGreen | Exec/RegTests/HotBubble/input.3d-regt | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_141924_466418 |
| a6605541cc2cd999 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauS | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_CoGauS | Exec/RegTests/TaylorGreen/input.3d_PPM | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_142056_339565 |
| 42518c8bd7dd5c7e | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauSAMR | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_CoGauSAMR | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_142234_069432 |
| f977ffe90b566cf8 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoGauT | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_CoGauT | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_142401_666143 |
| 17c2e72f9a451009 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoTanHSAMR | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_CoTanHSAMR | Exec/RegTests/TaylorGreen/input.3d_PPM | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_142637_031971 |
| 589447c34bbc9f35 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoTanHTAMR | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_CoTanHTAMR | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_142807_443898 |
| bf5ba1656ec5ec38 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVo | Exec/RegTests/PeriodicCases | Exec/RegTests/FlameSheet | Exec/RegTests/PeriodicCases/input.2d_CoVo | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_142927_661721 |
| ac441c335f44d5d8 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVoAMR | Exec/RegTests/PeriodicCases | Exec/RegTests/FlameSheet | Exec/RegTests/PeriodicCases/input.2d_CoVoAMR | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_143106_544772 |
| 353fdb39fe8e30c0 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_CoVoIncomp | Exec/RegTests/PeriodicCases | Exec/RegTests/FlameSheet | Exec/RegTests/PeriodicCases/input.2d_CoVoIncomp | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_143242_812139 |
| f4be7bc5af1c689a | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauS | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_DiffGauS | Exec/RegTests/TaylorGreen/input.3d_PPM | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_143413_853220 |
| c4d65775ba101da9 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauSAMR | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_DiffGauSAMR | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_143558_312344 |
| e1502fb616136d07 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauSRef | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_DiffGauSRef | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_143747_449787 |
| 2e7bd548f3e1afd9 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauT | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_DiffGauT | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_143940_738313 |
| b4ee72ef4075dd97 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.2d_DiffGauTAMR | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.2d_DiffGauTAMR | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_144108_804350 |
| 145d86475f987e9f | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo | Exec/RegTests/PeriodicCases | Exec/RegTests/FlameSheet | Exec/RegTests/PeriodicCases/input.3d_CoVo | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_144234_259973 |
| 1b8c9016f7022ea7 | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_InflowGen | Exec/RegTests/PeriodicCases | Exec/RegTests/TurbInflow | Exec/RegTests/PeriodicCases/input.3d_CoVo_InflowGen | Exec/RegTests/TurbInflow/input.3d | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_144415_762893 |
| 019be92c0eabdfca | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_PlaneInput | Exec/RegTests/PeriodicCases | Exec/RegTests/EB_EnclosedVortex | Exec/RegTests/PeriodicCases/input.3d_CoVo_PlaneInput | Exec/RegTests/EB_EnclosedVortex/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_144559_180025 |
| 746bfe7989a6ba1a | RegTests | Use PeleLMeX case Exec/RegTests/PeriodicCases with input.3d_CoVo_PltInput | Exec/RegTests/PeriodicCases | Exec/RegTests/TaylorGreen | Exec/RegTests/PeriodicCases/input.3d_CoVo_PltInput | Exec/RegTests/TaylorGreen/input.3d_BDS | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_144745_747790 |
| 4c3e369ddec259dd | RegTests | Use PeleLMeX case Exec/RegTests/SprayTest with input.2d | Exec/RegTests/SprayTest | Exec/RegTests/FlameSheet | Exec/RegTests/SprayTest/input.2d | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_144913_947934 |
| cbeb1e2ece45e535 | RegTests | Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_BDS | Exec/RegTests/TaylorGreen | Exec/RegTests/EB_EnclosedVortex | Exec/RegTests/TaylorGreen/input.3d_BDS | Exec/RegTests/EB_EnclosedVortex/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_145039_795991 |
| a93e5e375de16c53 | RegTests | Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_PLM | Exec/RegTests/TaylorGreen | Exec/RegTests/TripleFlame | Exec/RegTests/TaylorGreen/input.3d_PLM | Exec/RegTests/TripleFlame/tripleflame-2d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_145233_394255 |
| 0208d15104e07b77 | RegTests | Use PeleLMeX case Exec/RegTests/TaylorGreen with input.3d_PPM | Exec/RegTests/TaylorGreen | Exec/RegTests/TripleFlame | Exec/RegTests/TaylorGreen/input.3d_PPM | Exec/RegTests/TripleFlame/tripleflame-2d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_145434_506941 |
| f536ea75978f3bbb | RegTests | Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d | Exec/RegTests/TurbInflow | Exec/RegTests/EB_PipeFlow | Exec/RegTests/TurbInflow/input.3d | Exec/RegTests/EB_PipeFlow/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_145754_420903 |
| 105c0eb76ca40d27 | RegTests | Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_BoxLoZ | Exec/RegTests/TurbInflow | Exec/RegTests/EB_EnclosedVortex | Exec/RegTests/TurbInflow/input.3d_BoxLoZ | Exec/RegTests/EB_EnclosedVortex/input.2d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_145857_656102 |
| 813c016a6f0f76be | RegTests | Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_posX | Exec/RegTests/TurbInflow | Exec/RegTests/EB_PipeFlow | Exec/RegTests/TurbInflow/input.3d_posX | Exec/RegTests/EB_PipeFlow/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_150011_971241 |
| b4ffa6b3aabff3a0 | RegTests | Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_twoInjs | Exec/RegTests/TurbInflow | Exec/RegTests/EB_PipeFlow | Exec/RegTests/TurbInflow/input.3d_twoInjs | Exec/RegTests/EB_PipeFlow/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_150146_501653 |
| 449339b0bef68d23 | RegTests | Use PeleLMeX case Exec/RegTests/TurbInflow with input.3d_twoInjsOverlap | Exec/RegTests/TurbInflow | Exec/RegTests/EB_PipeFlow | Exec/RegTests/TurbInflow/input.3d_twoInjsOverlap | Exec/RegTests/EB_PipeFlow/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_150317_636837 |
| a22762f98dd236c0 | RegTests | Use PeleLMeX case Exec/RegTests/Unit with input | Exec/RegTests/Unit | Exec/RegTests/TaylorGreen | Exec/RegTests/Unit/input | Exec/RegTests/TaylorGreen/input.3d_PPM | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_150439_640516 |
| 0a953c129d3fc627 | RegTests | Use PeleLMeX case Exec/RegTests/Unit with input.diffusion | Exec/RegTests/Unit | Exec/RegTests/FlameSheet | Exec/RegTests/Unit/input.diffusion | Exec/RegTests/FlameSheet/flamesheet-drm19-3d.inp | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_150600_655423 |
| d4d9f6b22420e1e8 | UnitTests | Use PeleLMeX case Exec/UnitTests/DodecaneLu with inputs.3d | Exec/UnitTests/DodecaneLu | Exec/UnitTests/EB_SphericalFlame | Exec/UnitTests/DodecaneLu/inputs.3d | Exec/UnitTests/EB_SphericalFlame/input.3d-regt | benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/run_20260430_150730_287910 |

Clustering analysis:
- By category:
| Category | Non-match count |
| --- | --- |
| RegTests | 55 |
| Production | 15 |
| Plasma | 5 |
| UnitTests | 1 |

- By expected case prefix:
| Expected prefix | Non-match count |
| --- | --- |
| RegTests | 55 |
| Production | 15 |
| Plasma | 5 |
| UnitTests | 1 |

- By returned case prefix:
| Returned prefix | Non-match count |
| --- | --- |
| RegTests | 55 |
| Production | 15 |
| Plasma | 4 |
| unknown | 1 |
| UnitTests | 1 |

- Top expected input filenames among non-matches:
| Expected input filename | Non-match count |
| --- | --- |
| input.2d-regt | 13 |
| input.3d-regt | 7 |
| input.3d | 5 |
| input.2d-regt_Hypre | 2 |
| input.2d-regt_flipped | 1 |
| input.2d-regt_wave | 1 |
| input.3d_stoich_EF | 1 |
| input.3d_Hypre | 1 |
| input_coolflow.2d-regt | 1 |
| input_all.inp | 1 |
| input_les_additions.inp | 1 |
| input_reacting_additions.inp | 1 |
| input_turbinflow_additions.inp | 1 |
| inputs.3d-regt | 1 |
| input.2d-regt_incomp | 1 |
| input.2d-Re500 | 1 |
| input.2d-regt_HypreMAC | 1 |
| input.2d-regt_HypreNodal | 1 |
| input.2d-regt_WallBump | 1 |
| input.2d-regt_isoT | 1 |

- Top returned case names among non-matches:
| Returned case name | Non-match count |
| --- | --- |
| Exec/RegTests/FlameSheet | 22 |
| Exec/RegTests/TaylorGreen | 18 |
| Exec/Production/CounterFlow | 7 |
| Exec/RegTests/EB_PipeFlow | 6 |
| Exec/Production/JetInCrossflow | 5 |
| Exec/Plasma/PremBunsen3DKuhl | 3 |
| Exec/RegTests/EB_EnclosedVortex | 3 |
| Exec/Production/PremBunsen2D | 2 |
| Exec/RegTests/EB_EnclosedFlame | 2 |
| Exec/RegTests/TripleFlame | 2 |
| Exec/Plasma/IonizedAirWave | 1 |
| unknown | 1 |
| Exec/Production/PremBunsen3D | 1 |
| Exec/RegTests/EB_FlowPastCylinder | 1 |
| Exec/RegTests/TurbInflow | 1 |
| Exec/UnitTests/EB_SphericalFlame | 1 |

- Cross-code/path leakage check result: potential out-of-domain returned cases detected:
| row_id | returned_case | category | prompt |
| --- | --- | --- | --- |
| d02353d6b44e0dfc | unknown | Plasma | Use PeleLMeX case Exec/Plasma/PremBunsen3DKuhl with input.3d_stoich_EF |

## Step 5 — Summary of Findings
Trustworthiness verdict:
The chart values are **partially trustworthy** for describing the exact runs represented, because each bar is reproducibly computed from raw `results.jsonl` rows and matches the derived `benchmark_summary.csv`. However, they are **not currently trustworthy for direct cross-code or provider performance claims** because the bars come from different prompt matrices and row universes (ERF vs REMORA vs PeleLMeX), and only one provider is shown for REMORA/PeleLMeX in this chart. The PeleLMeX hierarchical anomaly is real in the data and should be treated as an investigation target before any comparative conclusion.

⚠️ Flags (ordered by severity):
- ⚠️ [HIGH] Cross-code bars are computed from different prompt matrices and different row universes (ERF=136/strategy, REMORA=24/strategy, PeleLMeX=88/strategy), so direct leaderboard interpretation is not apples-to-apples.
- ⚠️ [HIGH] Provider comparison is not apples-to-apples across codes: REMORA and PeleLMeX use provider `amsci2_faiss0` only in this chart; no cborg bars are present for those codes.
- ⚠️ [HIGH] PeleLMeX hierarchical anomaly is extreme (12/88 case-match) and requires investigation before reporting as model quality.
- ⚠️ [MEDIUM] /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl: column `selected_inputs` has nulls=0, blanks=10, unique=28, top_freq=28
- ⚠️ [MEDIUM] /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl: column `selected_inputs` has nulls=0, blanks=2, unique=15, top_freq=10
- ⚠️ [MEDIUM] /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl: column `selected_inputs` has nulls=0, blanks=3, unique=95, top_freq=20
- ⚠️ [LOW] /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).
- ⚠️ [LOW] /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).
- ⚠️ [LOW] /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).
- ⚠️ [LOW] /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).

Recommended next actions per flag:
- fix before next run: Cross-code bars are computed from different prompt matrices and different row universes (ERF=136/strategy, REMORA=24/strategy, PeleLMeX=88/strategy), so direct leaderboard interpretation is not apples-to-apples.
- fix before next run: Provider comparison is not apples-to-apples across codes: REMORA and PeleLMeX use provider `amsci2_faiss0` only in this chart; no cborg bars are present for those codes.
- fix before next run: PeleLMeX hierarchical anomaly is extreme (12/88 case-match) and requires investigation before reporting as model quality.
- investigate but not blocking: /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl: column `selected_inputs` has nulls=0, blanks=10, unique=28, top_freq=28
- investigate but not blocking: /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl: column `selected_inputs` has nulls=0, blanks=2, unique=15, top_freq=10
- investigate but not blocking: /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl: column `selected_inputs` has nulls=0, blanks=3, unique=95, top_freq=20
- investigate but not blocking: /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).
- investigate but not blocking: /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).
- investigate but not blocking: /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_amsci2_20260429T160959Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).
- investigate but not blocking: /home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf/benchmark_v2/results/full_cborg_20260427T202152Z/results.jsonl: results.jsonl lacks explicit provenance columns for FAISS index/git SHA/run timestamp (faiss_db_path, faiss_index, retrieval_index, index_name, run_id, timestamp, git_sha, version absent).
## Update — 2026-05-06 Fix Confirmation (PeleLMeX Hierarchical)
- Original hierarchical run: `benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z`
  - `case_match=12/88 (13.6%)`
- Fixed hierarchical run: `benchmark_pelelmex/results/diagnostic88_hierarchical_amsci2_faiss0_20260506T154239Z`
  - `case_match=87/88 (98.9%)`
  - `inputs_match=25/88 (28.4%)`
  - `blank selected_inputs=0`
  - per-row provenance columns present (`run_id`, `git_sha`, `faiss_index_path`, `frozen_input_file`)
- Interpretation: case-drift behavior tied to `parameter_resolution_retry` no longer dominates hierarchical case selection after the retry-lock fix.
