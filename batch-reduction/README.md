# Batch-source reduction with PCA

A preprocessing step run **before** BERNARD for datasets whose batch effect has more than one
source — e.g. study, country, continent and sequencing instrument all recorded as separate
metadata columns. BERNARD's correction methods remove **one** batch column (`study_name`); this
step compresses several categorical batch columns into a single numeric `batch` column with PCA,
so that the combined batch structure can be passed to BERNARD as one variable.

## How it works

For every dataset in `raw-data/`:

1. The columns listed in `batches.txt` are one-hot encoded (`pandas.get_dummies`).
2. PCA with **one component** is fitted on the encoded matrix (`sklearn.decomposition.PCA`).
3. The first principal-component score of each sample becomes the new `batch` column; the original
   batch columns are dropped.
4. Two files are written to `outputs/`: the full dataset with the reduced `batch` column, and a
   small metadata table (`sample_id`, `batch`, `factor_of_interest`).

Samples with the same combination of batch values always get the same score, so the `batch`
column behaves as a categorical label (one value per observed combination) even though it is
numeric. In the demo, the four columns `bioProject`, `locationCountry`, `locationContinent` and
`instrument` collapse into four distinct `batch` values.

## Input layout

```
<bernard_input>/
  raw-data/
    <dataset>.csv     # features AND metadata columns in one table (see below)
    config.json       # sample_id_column and factor_of_interest
    batches.txt       # names of the batch columns to combine, one per line
    tag.txt           # optional, copied into outputs/
  outputs/            # wiped and recreated on every run
```

- **`<dataset>.csv`** — unlike BERNARD's own input, the batch columns are read from the dataset
  table itself, not from a separate `metadata.csv`. It must contain the sample-ID column, the
  factor of interest, every column named in `batches.txt`, and the features. Every file in
  `raw-data/` is processed as a comma-separated table, except hidden files, `*.txt`, `*.json` and
  files with `metadata` in the name.
- **Batch columns must not have empty cells.** Every sample needs a value in every column listed in
  `batches.txt`. Before the PCA, the script checks this for each dataset; if any cell is empty
  (missing, or only whitespace) it lists the affected samples per column and stops with an
  error. Fill in the missing values, or remove those samples, before running. If a column named in
  `batches.txt` is not in the dataset at all, it also stops with an error.
- **`config.json`**:
  ```json
  {
  "sample_id_column": "run",
  "factor_of_interest": "diagnosis"
  }
  ```
- **`batches.txt`** — one column name per line, no blank lines:
  ```
  locationCountry
  locationContinent
  instrument
  bioProject
  ```

## Running

The cfg file needs a single setting, `bernard_input` (absolute, or relative to the work dir):

```
bernard_input = /path/to/BERNARD/batch-reduction/inputs
```

From the repository root:

```
python3 batch-reduction/src-pca-bernard/batch-pca.py batch-reduction/bernard_pca_cfg.txt batch-reduction
```

General form: `batch-pca.py <cfg> <work_dir>`; both arguments are required. `work_dir` is used
only to resolve relative paths in the cfg. `bernard_input` may also point at a `.zip` holding the
`raw-data/` files; it is extracted into a `raw-data/` folder next to the zip, and `outputs/` is
created there as well. Dependencies are `pandas` and `scikit-learn`, already
in BERNARD's `requirements/`.

## Outputs

For an input file `demo.csv`:

| file | contents |
|---|---|
| `outputs/demo-reduced.csv` | the dataset with the batch columns replaced by one `batch` column (last column) |
| `outputs/metadata-demo-reduced.csv` | `<sample_id_column>`, `batch`, `<factor_of_interest>` |

## Passing the result to BERNARD

1. Create a new BERNARD input folder with a `raw-data/` subfolder.
2. Copy the reduced dataset into it as is (BERNARD names the dataset after the file, here
   `demo-reduced`), and the metadata file as `raw-data/metadata.csv`.
3. In the BERNARD cfg set `study_name = batch`, plus the same `sample_id_column` and
   `factor_of_interest` as above.
4. Run BERNARD as usual: `python3 bernard/src/BERNARD.py <cfg>`.

`bernard/reduced-dim-demo/` with `bernard/bernard_cfg_reduced-dim-demo.txt` is a worked example
of this, built from `batch-reduction/inputs/` (both are gitignored, so they exist only locally).

## Limitations

- **One component only.** PC1 captures the largest share of variance in the encoded batch
  matrix, not all of it; the explained-variance ratio is not reported. When the batch columns are
  largely nested (as in the demo: each `bioProject` fixes country, continent and instrument)
  little is lost, but for independent batch sources PC1 can merge combinations that BERNARD
  should treat as different batches. Check the number of distinct `batch` values against the
  number of observed combinations before running BERNARD.
- **Sign and scale are arbitrary.** The `batch` values are PCA scores; only which samples share a
  value is meaningful, not the values themselves.
