# Bundled original source files

The project contains unchanged copies of all five supplied source files. No
original source-device paths are stored. Geographic data is from GeoNames; the
original schema, licence and source statements are preserved in Metadata.txt
and Read Me.txt. Copying the brief does not adopt its additional instructions.

| File (relative to repository root) | Purpose |
|---|---|
| `docs/Project_2627T1.pdf` | Original project brief and course requirements. |
| `docs/Metadata.txt` | GeoNames field definitions, licence and dataset metadata. |
| `docs/Read Me.txt` | Original dataset provenance and supporting references. |
| `submission/inputs/MY.txt` | Full 71,709-record GeoNames text dataset, read by the generator. |
| `submission/inputs/MY-All-columns_with_header.xlsx` | Original header-added spreadsheet for manual inspection; not needed by the Java loader. |

## Integrity manifest

SHA-256 hashes identify the supplied bytes. Sizes are in bytes.

| File | Size | SHA-256 |
|---|---:|---|
| `docs/Project_2627T1.pdf` | 254094 | `0a4065461a422c01898f9149e5f816c9709132b4995fc91951c25ecdd90908bb` |
| `docs/Metadata.txt` | 8842 | `e250d95a2f8d3c77ade39b8acbdc7205e0f8f08adb6d2473ec667b05f8bd9f38` |
| `docs/Read Me.txt` | 439 | `97511ade7f86c232ba9721e996271b283036ccbdffd21f4ed0235ade7a33e811` |
| `submission/inputs/MY.txt` | 8968732 | `0102511fbe91060bf3c67b3962ccd2ba1d9f887afe81b7aff8e184061c1280f6` |
| `submission/inputs/MY-All-columns_with_header.xlsx` | 7089041 | `74deb277bab1add4a16954b8786785e004f73628bd0a23943202445b1e55e165` |


Run from the repository root, using the included full dataset:

```sh
./submission/run.sh --generate inputs/MY.txt --count 25 --selection random --seed 42
./submission/run.sh --algorithm greedy --duration-minutes 180
```

Generation replaces only the active scenario under `submission/data/`. It does
not change either full input dataset or the original documentation. Normal
solving reads the active scenario; it does not reread the full dataset or Excel
workbook. The inputs and documents are included alongside source, tests and
project guides so teammates can work from a single checkout.
