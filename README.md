# Vehicles missed by failed cameras reshape urban traffic recovery estimates after a typhoon

Zengzhi Zhang, Yue Deng, Mengyao Zhang, Jiayu Bao, Liefeng Zhu, Qi Cao and Gang Ren. Paper DOI: **to be assigned**. Software archive DOI: **to be assigned**.

## Overview

This repository accompanies the paper "Vehicles missed by failed cameras reshape urban traffic recovery estimates after a typhoon". During Typhoon In-Fa (July 2021), many licence-plate recognition cameras in Shangyu, China, stopped recording or missed part of the passing traffic. The study linked GPS traces of 290 taxis to the camera records to measure, camera by camera, the share of taxi passages each camera recorded. It then showed how the choice of which cameras to trust changes estimates of network recovery. The repository contains the analysis code used for the reported results and scripts that redraw every figure from the published source data. A synthetic dataset lets the core analysis run without the restricted records.

## Repository structure

| Directory | Contents |
|---|---|
| `figures/` | Scripts for six main and nine Extended Data figures |
| `source_data/` | Published source tables, with manuscript figure numbering |
| `public_layers/` | Public geographic layers and their attribution |
| `analysis/` | Executed analysis and checking code, organised by analysis round |
| `synthetic/` | Fictitious panel generator and data documentation |
| `config/` | Example configurations for authorised-data use |
| `docs/PAPER_MAP.md` | Figure and table provenance |
| `tools/` | Generic privacy checks |
| `outputs/` | Generated files; ignored by version control |

## Analysis pipeline

The scripts retain their original round-based locations. Follow the nine-step [pipeline](analysis/PIPELINE.md) for the full input/output and manuscript mapping:

1. Restricted raw-record reading, pseudonymisation and parsing.
2. Camera-day, camera-hour and lane panels, and recording-state screening.
3. Taxi GPS to camera linkage and inferred passages.
4. Capture rates at control-selected matchable cameras.
5. Daily network recovery estimators (Table 1).
6. Sustained attainment and break-even recovery.
7. Spatial patterns and vehicle-group analysis.
8. Source-data generation.
9. Drawing the manuscript figures.

## Quick start

Use Python 3.9.12 and install the pinned dependencies:

```sh
python -m pip install -r requirements.txt
```

Redraw the fifteen figures from the source data and public layers:

```sh
python figures/make_all.py
```

Generate fictitious inputs and run the supported original analysis chains:

```sh
python run_synthetic.py
```

Outputs are written under `outputs/`. Synthetic results are **synthetic data, not comparable with the paper's numerical results**. See `synthetic/README.md` for supported entry points and any restricted-data-only scripts. Figure scripts use Arial and DejaVu Sans; install the same fonts to reproduce text layout. Optional author-local figure QA modules are not distributed.

## Data access

The camera records and taxi GPS traces were provided by the Shangyu District Traffic Management Brigade solely for research. Because they record the movements of individual vehicles, they cannot be shared publicly. Requests for access to the pseudonymised records can be made to the corresponding author. Access requires approval from the Brigade and a data-use agreement, and is limited to non-commercial research. Camera-level derived data, including daily recorded counts and capture rates, can be requested on the same terms.

## Running with authorised data

Copy `config/paths.example.yaml` to `config/paths.yaml` and `config/private.example.yaml` to `config/private.yaml`, then populate them locally. These files are ignored by version control. See `analysis/ROUNDS.md` for execution order and each script's inputs and outputs. A path configuration can also be selected with `SHANGYU_PATHS_CONFIG`, and private settings with `SHANGYU_PRIVATE_CONFIG`. If authorised pseudonymisation is required, the key-file location comes from `SHANGYU_HMAC_KEY_FILE`; do not put a key in this repository.

Analysis code is kept as executed. Changes are limited to configuration, privacy and an opt-in synthetic mode that skips assertions on the size of the real sample; `analysis/SANITISATION.md` lists every change.

## Validation

All fifteen figures were redrawn from `source_data/` and `public_layers/` alone and compared with the published figures. The text in every figure is identical, and rendered pixels differ by at most 0.1% at 300 dpi. With the authorised data, the analysis code of the final round reproduces the frozen results value for value. The synthetic data follow the structure and published sample sizes of the pseudonymised panels, with all values set by hand, and `run_synthetic.py` runs the Table 1 estimators, the capture-based expected records and the sustained-attainment and break-even analyses on them. Synthetic results are not comparable with the paper's numbers.

## Licensing, citation and contact

Code: MIT, copyright The authors. Data under `source_data/` and the synthetic data: CC BY 4.0. Public layers retain their individual licences; see `public_layers/README.md`. Cite the accompanying paper and the archived release using `CITATION.cff`.

Correspondence: Gang Ren (see the paper)
