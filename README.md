# **BERNARD**
## Batch Effect Removal and Noise-Reducing Algorithm for Raw Datasets

### :books: Batch effect correction methods

Batch effect, an unwanted source of variations caused by biological (e.g., sex, age), technical (e.g., sample collection methods, DNA sequencing platforms), and computational (e.g., software and software version) factors, undermine the reproducibility of human microbiome studies ([Wang and LeCao, 2020](https://pubmed.ncbi.nlm.nih.gov/31776547/), [Wang and LeCao, 2023](https://pubmed.ncbi.nlm.nih.gov/36653900/)). We present Batch Effect Removal and Noise-reducing Algorithm for Raw Datasets (BERNARD) computational tool, a pipeline for batch effect removal that implements and compares 16 correction methods:

- **pyCombat** — Python implementation of ComBat ([Behdenna et al., 2023](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-023-05578-5))
- **BMC** — Batch Mean Centering, from the Microbiome Batch Effects Correction Suite (MBECS) ([Olbrich et al., 2023](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-023-05252-w))
- **RemoveBatchEffect** — removeBatchEffect() from limma ([Ritchie et al., 2015](https://pubmed.ncbi.nlm.nih.gov/25605792/))
- **ConQuR** — Conditional Quantile Regression ([Ling et al., 2022](https://www.nature.com/articles/s41467-022-33071-9))
- **ConQuR-LASSO** — ConQuR with its penalized fitting strategy: logistic LASSO, LASSO quantile regression and interpolation ([Ling et al., 2022](https://www.nature.com/articles/s41467-022-33071-9))
- **RUV3** — Remove Unwanted Variation 3, from MBECS ([Olbrich et al., 2023](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-023-05252-w))
- **PLSDA** — PLSDA-batch ([Wang and Le Cao, 2023](https://pubmed.ncbi.nlm.nih.gov/36653900/))
- **sPLSDA** — sparse PLSDA-batch ([Wang and Le Cao, 2023](https://pubmed.ncbi.nlm.nih.gov/36653900/))
- **wPLSDA** — weighted PLSDA-batch, for unbalanced designs ([Wang and Le Cao, 2023](https://pubmed.ncbi.nlm.nih.gov/36653900/))
- **PN** — Percentile Normalisation, from MBECS ([Olbrich et al., 2023](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-023-05252-w))
- **MetaDICT** — shared dictionary learning that avoids overcorrection in the presence of unobserved confounders ([Yuan and Wang, 2025](https://doi.org/10.1038/s41467-025-63425-y))
- **ComBat-Seq** — negative-binomial variant of ComBat for raw count data ([Zhang, Parmigiani and Johnson, 2020](https://academic.oup.com/nargab/article/2/3/lqaa078/5909519))
- **MMUPHin** — meta-analysis batch-adjustment framework for microbial abundance profiles ([Ma et al., 2022](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-022-02753-4))
- **RUV-III-NB** — negative-binomial extension of RUV-III ([Salim et al., 2022](https://academic.oup.com/nar/article/50/16/e96/6618546))
- **FSQN** — feature-specific quantile normalisation against a reference batch ([Franks, Cai and Whitfield, 2018](https://academic.oup.com/bioinformatics/article/34/11/1868/4816109))
- **FAbatch** — model-based batch adjustment for a binary factor of interest ([Hornung, Boulesteix and Causeur, 2016](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-015-0870-z))
- **DEBIAS-M** — learns batch-specific multiplicative correction factors jointly with a phenotype model ([Austin et al., 2025](https://www.nature.com/articles/s41564-025-01954-4))

The pipeline evaluates all selected methods in a single run and identifies the most effective approach for a given dataset. The effect of each method is measured against the source of batch effect and the biological factor of interest (PERMANOVA, PERMDISP, silhouette width, kBET, iLISI/cLISI, graph connectivity, PVCA, variance partitioning, AUROC and others). A successful correction reduces batch-related variability while preserving the variability linked to the factor of interest. The best method is chosen by a gated consensus ranking (see [How the best method is chosen](#how-the-best-method-is-chosen)). BERNARD is extensible, allowing integration of additional methods.

<img width="818" alt="Screenshot 2025-05-11 at 15 18 16" src="https://github.com/user-attachments/assets/d988f057-cf17-40f2-87e3-847db6250625" />

### :star: Acknowledgments
This work is in part supported by ARIS large project J7-50230 to B.Stres BENEWt (Building Effective NCD Early Warning tools)

The authors gratefully acknowledge the HPC RIVR consortium (www.hpc-rivr.si) and EuroHPC JU (eurohpc-ju.europa.eu) for funding this research by providing computing resources of the HPC system Vega at the Institute of Information Science (www.izum.si).

### :hammer_and_wrench: Requirements
[![Python (tested on MacOS)](https://img.shields.io/badge/Python%20(tested%20on%20MacOS)-3.12.2-F9B6A6?logo=python&logoColor=CF7D6A)](https://www.python.org/)

[![Python (tested on Windows)](https://img.shields.io/badge/Python%20(tested%20on%20Windows)-3.11.9-F9B6A6?logo=python&logoColor=CF7D6A)](https://www.python.org/)

[![Python (tested on Linux)](https://img.shields.io/badge/Python%20(tested%20on%20Linux)-3.12.3-F9B6A6?logo=python&logoColor=CF7D6A)](https://www.python.org/)

[![R](https://img.shields.io/badge/R-4.5.2-F9B6A6?logo=r&logoColor=CF7D6A)](https://www.r-project.org/)

Detailed packages with their versions for Linux, Windows and MacOS are listed in corresponding requirements txt file. 

### :arrow_down: Installing Bernard

#### :window: Windows
```
# Set up and activate virtual environment
PS C:\Users\user\Desktop> python -m venv bernardTestEnvo
PS C:\Users\user\Desktop> bernardTestEnvo\Scripts\activate 

# Clone BERNARD repository
(bernardTestEnvo) PS C:\Users\user\Desktop> git clone https://github.com/uasic/BERNARD.git

# Move to BERNARD/requirements repository
(bernardTestEnvo) PS C:\Users\user\Desktop> cd .\BERNARD\
(bernardTestEnvo) PS C:\Users\user\Desktop\BERNARD> cd .\requirements\

# Install requirements for windows and R packages
(bernardTestEnvo) PS C:\Users\user\Desktop\BERNARD\requirements> pip install -r requirements-windows.txt
(bernardTestEnvo) PS C:\Users\user\Desktop\BERNARD\requirements> Rscript RPackages.R

# Verify if Python and R are available.
Rscript --version
python --version

# Add R to PATH if needed (edit Path under system variables)
```
#### :green_apple: MacOS
```
# Set up and activate virtual environment
user-MacBook-Pro ~ % python3 -m venv bernardTestEnvo
user-MacBook-Pro ~ % source bernardTestEnvo/bin/activate

# Clone BERNARD repository
(bernardTestEnvo) user-MacBook-Pro ~ % git clone https://github.com/uasic/BERNARD.git

# Move to BERNARD/requirements repository
(bernardTestEnvo) user-MacBook-Pro % cd BERNARD/
(bernardTestEnvo) user-MacBook-Pro BERNARD % cd requirements

# Install requirements for MacOS and R packages
(bernardTestEnvo) user-MacBook-Pro requirements % pip install -r requirements-macOS.txt
(bernardTestEnvo) user-MacBook-Pro requirements % Rscript RPackages.R

# Verify if Python and R are available.
Rscript --version
python --version
```

#### :penguin: Linux
```
# Set up virtual environment
python3 -m venv bernardTestEnvo

# Activate virtual environment
source bernardTestEnvo/bin/activate

# Clone BERNARD repository
git clone https://github.com/uasic/BERNARD.git

# Move to requirements directory
cd BERNARD/requirements

# Install Python requirements for Linux
pip install -r requirements-linux.txt

# Install required R packages
Rscript RPackages.R

# Verify if Python and R are available.
R --version
python3 --version
```

<b>Note:</b> Rscript RPackages.R may need to be run multiple times before all required packages are successfully installed.

## :file_folder: BERNARD: Repository Structure

```
├── **README.md**
├── **sequence2dataframe/**
│ ├── sra2fastq.py                          # script for converting SRA to FASTQ
├── **requirements/**                       # requirements for BERNARD pipeline
│ ├── Dockerfile
│ ├── requirements-linux.txt
│ ├── requirements-macOS.txt
│ ├── requirements-windows.txt
│ ├── RPackages.R
├── **bernard/**                            # main BERNARD folder
│ ├── src/                                  # pipeline source (macOS/Linux)
│ ├── src-windows/                          # pipeline source (Windows)
│ ├── run-many.sh
│ ├── run-many-windows.sh
│ ├── my_analysis_template.txt              # example of config file
│ ├── bernard_cfg_reduced-dim-demo.txt      # config file for reduced-dim-demo dataset
│ ├── bernard_cfg_demo.txt                  # config file for demo dataset
│ ├── reduced-dim-demo/                     # demo with reduced number of batch variables 
│ │ ├── outputs/                            # demo with reduced number of batch variables output data from BERNARD
│ │ ├── raw-data/                           # demo with reduced number of batch variables input data for BERNARD
│ ├── demo/
│ │ ├── raw-data/                           # demo input data for BERNARD
│ │ ├── outputs/                            # demo output data from BERNARD
├── **batch-reduction/**                    # PCA reduction of several batch columns into one (see its README.md)
│ ├── src-pca-bernard/                      # source code for reducing number of batch-related variables
│ ├── inputs
│ ├──── outputs/                            # output data with reduced sources of batch effect from batch-pca.py
│ ├──── raw-data/                           # dataset with multiple sources of batch effect for batch-pca.py
│ ├── bernard_pca_cfg.txt                   # configuration file for batch-pca.py
│ ├── README.md
```
## :computer: Application guide
### Before running BERNARD: Key checks
- Check if all samples present in a dataset are also included in metadata.
- Sample names must be strings.
- Check if the columns named in the settings file (`sample_id_column`, `study_name`, `factor_of_interest`, `covariates`) match your actual data.
- metadata should be stored as **metadata.csv** file in raw-data folder.

BERNARD pipeline is run from the terminal with the path to the BERNARD.py script and the path to a settings file; the data folder is given inside the settings file (`bernard_input`):

```
python3 bernard/src/BERNARD.py bernard/bernard_cfg_demo.txt
```

## :bookmark_tabs: BERNARD: User Guide

### Notation
- Factor of interest: Target feature (value). It can be diagnosis, treatment, phenotype...
- Source of batch effect: Feature that causes an unwanted variability you want to remove. It can be study ID, protocol ID... 

### One settings file

All parameters can be set in one **configuration file** (see cfg file), in lines of the form `name = value`.

Start from a complete, documented settings file (delete header line *Bernard V1.0, date 2025_04_24* before using the file):

```
python3 bernard/src/BERNARD.py --template > my_analysis.txt
```

This will generate a template config file that can be populated with configuration settings. The template is also provided
in repository as my_analysis_template.txt file.

The shortest file that works contains path to data only; all other parameters have a
default value:

```
bernard_input = /home/user/my_study
```

Run BERNARD on my_analysis.txt file with:

```
python3 bernard/src/BERNARD.py my_analysis.txt
```

### Checking a settings file and the data before running

A full run takes minutes to hours, and nearly everything that goes wrong is a mistake in the
settings file or in the data. `--check` reads both, reports if anything is wrong with either, and stops
without calculating anything or touching the existing `outputs` folder:

```
python3 bernard/src/BERNARD.py --check my_analysis.txt
```

It catches, among other things, a misspelled setting (and suggests the right name), a value outside
the range that makes sense, a column named in the settings that is not in the data (and suggests the
closest column that is), sample IDs in the measurements that match nothing in `metadata.csv`, a batch
column with only one value, a `config.json` that is not valid JSON, and a missing R installation.

An unexpected errors are printed to `outputs/bernard-error.log`.

### Running several datasets one after the other

One settings file describes one collection of data, so two datasets whose metadata columns differ
need two settings files. `run-many.sh` takes any number of them and runs them in turn, unattended:

```
bash bernard/run-many.sh study-a.txt study-b.txt study-c.txt
```

A queue that is run again and again is better kept in a list file of its own, one settings file per
line, and given with `--list`:

```
bash bernard/run-many.sh --list bernard/my-runs.txt
```

```
# my-runs.txt - the datasets of the January analysis, in the order they run
bernard_cfg_curated.txt
bernard_cfg_controls.txt
#bernard_cfg_HGMA.txt
```

Blank lines and lines beginning with `#` are ignored.

Before the first calculation it runs `--check` on **all** of the settings files and their data, and
starts nothing until every one of them passes. If a run does fail, the queue carries on with the
next dataset. At the end it prints which runs succeeded, which failed and how long each took:

```
    ok           study-a.txt  (0h 41m 12s)
    FAILED       study-b.txt  (exit code)
    ok           study-c.txt  (1h 07m 55s)
```

| option | |
|---|---|
| `--no-check` | do not check the settings files first |
| `--stop-on-error` | stop at the first run that fails instead of carrying on |
| `--check-only` | check everything and calculate nothing: a dry run of the whole queue |
| `--list <file>` | read the settings files from a list file, one per line |
| `--log-dir <dir>` | also write the full output of each run to `<dir>/<settings file name>.log` |

### Running the correction methods in parallel

The correction methods do not depend on each other, so BERNARD runs several of them at the same
time. `max_parallel_methods` sets how many. `0` is the default value that chooses from the number of processor
cores. `1` switch paralelization off and methods will be executed one after another.

A method that fails is reported and left out of the comparison. The remaining methods carry on.
The full output of every method is written into `outputs/logs/`. 
Set `stop_on_method_failure = yes` to stop at the first failure instead.

### Reproducibility

Every stochastic step is seeded, so repeated runs on the same data return identical results. The
seed is the `random_seed` setting (42 by default) and covers both halves of the run: in Python it
drives `IsolationForest()`, `PCA()`, `MDS()`, `TSNE()` and the PERMANOVA and PERMDISP permutation
tests, and BERNARD writes it into `raw-data/config.json` so that every R correction script starts
from the same seed. Each run also writes `outputs/run-manifest-<date>.json`, recording every
setting used, the library versions and the fate of each method.

### Plot colours

Plot colours can be set in `bernard_library.py`; see
https://matplotlib.org/stable/gallery/color/named_colors.html

## How the best method is chosen

Every method that ran is put through five steps. The whole rule lives in `bernard/src/scoring.py`
and every intermediate number it uses is written to `outputs/final-calculations-<date>.xlsx`, so
the decision can be checked line by line.

**Step 1 - the gate.** Two PERMANOVA p-values, measured on the corrected data, decide whether a
method is allowed to compete at all:

| | verdict |
|---|---|
| batch `p < significance_alpha` | **Rejected** - the batches still separate significantly, the batch effect is not gone |
| factor of interest `p > significance_alpha` | **Rejected** - the phenotype groups no longer separate, the biology was scrubbed out |
| batch `p >= alpha` **and** factor of interest `p <= alpha` | **Accepted** |

A rejected method cannot make up for it by scoring well below - unless *every* method is rejected,
in which case the gate is skipped and the whole field is ranked (see "When no method passes step 1"
below). The reason a method was rejected is written into the `rejection-reason` column.
`significance_alpha` defaults to 0.05.

**Step 2 - twenty-one rankings.** Eleven measures are read twice, once against the batch and once
against the factor of interest, which gives 21 lists (AUROC is only defined against the factor of
interest, so it contributes one list rather than two). In each list the accepted methods are put
in order, best first. An effective correction has to *remove* the
batch structure and *keep* the biological structure:

| Measure | best against the batch | best against the factor of interest |
|---|---|---|
| PERMANOVA R² | lowest | highest |
| silhouette width | lowest | highest |
| kBET acceptance | highest | lowest |
| LISI (iLISI / cLISI) | highest | lowest |
| graph connectivity | lowest | highest |
| alignment score | highest | lowest |
| entropy score | highest | lowest |
| PVCA share | lowest | highest |
| variance partitioning (batch-only / phenotype-only) | lowest | highest |
| % features associated | lowest | highest |
| AUROC (mean of cv and lobo) | — | highest |

The 21 lists are written out in readable form, one row per dataset, on the **`ranking-lists`**
sheet of the results workbook: `method1 -> method2 -> method3 -> ...`, best first.

**Step 3 - points.** In each list the best method scores *n* points, the next *n-1*, down to 1 for
the worst, where *n* is how many methods that list includes.

**Step 4 - the sum.** The 21 point scores are added up per method, into a `consensus-score`.

**Step 5 - the final rank.** The methods are ordered by that sum, highest first, into `final-rank`:
1 is the winner, and that row is also labelled as `Best performance` and highlighted in the workbook.
The ranking is strict, 1 to *n*; two methods on the same sum are separated on the leftover batch
variability, the lower the better. **Methods rejected in step 1 are marked `0`.**

**When no method passes step 1.** Step 1 is then *skipped* for that dataset and steps 2 to 5 are
run over the whole field instead of over the survivors, so the dataset still gets a winner: one of
the methods did remove more of the batch effect than the rest, or hold on to more of the biology,
and reporting nothing would throw that away. The winner comes with the warning that it did not
pass the gate, meaning that either batch effect is still significant or that the effect of target variable
was lost.

```
demo
    rejected  pyCombat             batch effect still significant (batch p = 0.002 < 0.05)
    rejected  bmc                  batch effect still significant (batch p = 0.004 < 0.05)
    rejected  pn                   batch effect still significant (batch p = 0.001 < 0.05)
    Step 1 rejected every method, so it was skipped: all of them were ranked on
    the 21 measures instead, and the best of them is reported below.
    rank 1    bmc                  score 9.0  <- best
    rank 2    pyCombat             score 6.0
    rank 3    pn                   score 3.0

    None of the methods removed the batch effect. The best selected method is bmc.
    WARNING: the batch effect is still significant after bmc (batch p = 0.004 < 0.05).
    It was reduced but not removed, and the corrected data has to be read knowing that.
```

## Checking stability of a winner

A single run names one method best, but that verdict comes from one particular set of samples. The
stability analysis redraws the samples many times and repeats **the whole decision** on each
subsample, so the report can say "chosen in 83 of 100 subsamples" instead of "best".

It uses the same rule as the full run: every subsample rebuilds the measurement table and hands it to the same
`score_methods()` that chose the winner, with the same step-1 gate and the same 21 lists. What
comes out is therefore the stability of the method BERNARD actually names.

| setting | default | what it does |
|---|---|---|
| `run_stability` | yes | run the analysis at all |
| `stability_resamples` | 100 | how many subsamples to draw |
| `stability_fraction` | 0.8 | share of samples each subsample keeps, drawn within every batch × phenotype cell |
| `stability_measures` | all | `all` = all 21 lists, exactly the rule that chose the winner. `distance` = only the 14 that come off the distance matrix, roughly ten times faster; a report that uses it has to say so |

### Running only the stability analysis

The analysis needs the cleaned dataset, the corrected dataset of every method and the settings
file - all of which a finished run has already left on disk. So it can be repeated on its own,
without re-running any correction:

```
python3 bernard/src/stability.py bernard/bernard_cfg_HGMAsplit.txt
```

It writes the same `stability-<dataset>-<date>.xlsx` and `report/<dataset>-stability-<date>.png` a
full run writes.

> **One thing can be missing.** `delete_tmp_corrected_data = yes` (the default) deletes the
> corrected data of every method except the winner at the end of a run. The stability analysis
> compares the methods against each other, so it cannot be repeated on such a run: it says which
> datasets it had to skip rather than reporting a selection frequency of 100% for the only method
> left on disk. Set `delete_tmp_corrected_data = no` if the analysis is to be repeatable.

## Selecting batch effect correction methods

By default BERNARD runs every batch effect correction method it knows and then reports the best performing one. A run over all of them takes a long time, so only some of the methods can be chosen in bernard_cfg.txt. Users can run only selected methods and skip those that clearly violate assumptions.

The settings file lists all seventeen of them under `correction_methods`, one per line, and a method with a `#` in front of its name is not run.
```
correction_methods =
    pyCombat
    BMC
    RemoveBatchEffect
#   ConQuR
    RUV3
    PLSDA
    ...
```

The same thing may be written on one line, which is shorter when only a few methods are wanted:
```
correction_methods = pyCombat, ConQuR, PLSDA
```

or all of them can be kept and only the ones to be skipped listed, whichever is the shorter list to write:
```
exclude_correction_methods = ConQuR, MetaDICT
```

## Adjusting individual batch effect correction methods

### Adjusting PN.R file

```
Consider original documentation here: https://www.bioconductor.org/packages/devel/bioc/vignettes/MBECS/inst/doc/mbecs_vignette.html
```


#### Adjusting PLSDA.R file

```
Consider original documentation here: https://www.bioconductor.org/packages/devel/bioc/vignettes/PLSDAbatch/inst/doc/brief_vignette.html
```


#### Adjusting ConQuR.R and ConQuR-LASSO.R files

```
Consider original documentation here: https://wdl2459.github.io/ConQuR/ConQuR.Vignette.html
```

ConQuR.R refuses a dataset in which every batch holds a single value of `factor_of_interest`
(for example, each study sampled only one breed). There the factor is a combination of the batch
columns, standard ConQuR's quantile regression fails on a singular design for every taxon, and
ConQuR silently returns the taxa unchanged. ConQuR.R stops with "factor of interest ... is nested
in batch; standard ConQuR cannot separate them, use ConQuR-LASSO" instead, so that the uncorrected
table is not scored as a correction. ConQuR-LASSO.R handles such data.

#### Adjusting BMC.R file

```
Consider original documentation here: https://www.bioconductor.org/packages/devel/bioc/vignettes/MBECS/inst/doc/mbecs_vignette.html
```

#### Adjusting RemoveBatchEffect().R file
```
Consider original documentation here: https://rdrr.io/bioc/limma/man/removeBatchEffect.html
```

#### Adjusting RUV3.R file

```
Consider original documentation here: https://www.bioconductor.org/packages/devel/bioc/vignettes/MBECS/inst/doc/mbecs_vignette.html
```

#### Adjusting sPLSDA.R file

```
Consider original documentation here: https://www.bioconductor.org/packages/devel/bioc/vignettes/PLSDAbatch/inst/doc/brief_vignette.html
```

##### Adjusting wPLSDA.R file

```
Consider original documentation here: https://www.bioconductor.org/packages/devel/bioc/vignettes/PLSDAbatch/inst/doc/brief_vignette.html
```

#### Adjusting pyCombat.py file

```
Consider original documentation here: https://github.com/epigenelabs/inmoose
```

#### Adjusting MetaDICT.R file

```
MetaDICT needs a taxa dissimilarity structure (phylogenetic tree, taxonomy table, or
precomputed distance matrix) to build its sequencing-similarity graph. BERNARD's generic
per-dataset input does not include taxonomy/tree data, so MetaDICT.R falls back to a
Euclidean distance computed between each feature's abundance profile across samples. If
real taxonomy or a phylogenetic tree is available for a dataset, pass it via the
`taxonomy=`/`tree=` argument instead of `distance_matrix=` in MetaDICT.R for a more
biologically meaningful similarity structure.

Consider original documentation here: https://github.com/BoYuan07/MetaDICT
```

#### Adjusting ComBatSeq.R file

```
ComBat_seq() models raw sequencing counts, so BERNARD's cleaned tables are rounded to
non-negative integers before use, matching the convention already used for ConQuR.R.
Batch is study_name and group is factor_of_interest; extra covariates are not passed
(matching BMC.R/ConQuR.R's simpler single-covariate style).

Consider original documentation here: https://rdrr.io/bioc/sva/man/ComBat_seq.html
```

#### Adjusting MMUPHin.R file

```
adjust_batch() is called with batch=study_name and covariates=factor_of_interest only.

Consider original documentation here: https://www.bioconductor.org/packages/release/bioc/vignettes/MMUPHin/inst/doc/MMUPHin.html
```

#### Adjusting RUVIIINB.R file

```
Like RUV3.R, every feature is treated as a negative control (ctl = all features) and
counts are rounded to non-negative integers before fitting. The number of unwanted
factors (k) defaults to 2 and can be edited directly in the script.

Consider original documentation here: https://github.com/limfuxing/ruvIIInb
```

#### Adjusting FSQN.R file

```
The reference batch used for quantile normalization is the first (alphabetically
sorted) level of study_name, mirroring ConQuR.R's `batch_ref <- levels(batchid)[1]`
convention. No external FSQN package is required; the per-feature quantile mapping is
implemented directly in the script.

Consider original documentation here: https://academic.oup.com/bioinformatics/article/34/11/1868/4816109
```

#### Adjusting FAbatch.R file

```
FAbatch requires a binary factor_of_interest and more variable features than the
largest study_name group; both are checked explicitly and reported as a skipped file
if unmet. Feature values are CLR-transformed first via mixOmics::logratio.transfo(),
the same helper PLSDA.R/sPLSDA.R/wPLSDA.R already use.

Consider original documentation here: https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-015-0870-z
```

#### Adjusting DEBIASM.R file

```
DEBIAS-M is a Python/PyTorch package, not an R package, so DEBIASM.R bridges to it via
reticulate rather than calling an R library. Install its optional Python dependency
first with `pip install -r requirements/requirements-debias.txt` into whichever Python
environment reticulate resolves (RETICULATE_PYTHON env var, then a project ".venv",
then python3/python on PATH). If that dependency is missing, this method fails
gracefully for every dataset in the run (caught by the same per-file tryCatch every
other method uses) rather than aborting the whole pipeline.

Consider original documentation here: https://korem-lab.github.io/DEBIAS-M/
```

## :bulb: Contributions to BERNARD
We are welcoming all bug reports, feature and enhancements suggestions, and documentation improvement ideas.