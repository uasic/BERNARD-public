import os
import sys
import contextlib

import numpy as np
import pandas as pd

import glb
import scoring as bscoring
import bernard_library as bl


MEASURE_SETS = ('all', 'distance')


def _limit_blas_threads(threads):
    if not threads or threads < 1:
        return None
    try:
        from threadpoolctl import threadpool_limits
        return threadpool_limits(limits=int(threads), user_api='blas')
    except Exception:
        return None


@contextlib.contextmanager
def _quiet():
    with open(os.devnull, 'w') as sink:
        with contextlib.redirect_stdout(sink):
            yield


class _MethodSpace:

    def __init__(self, name, table, covariates):
        self.name = name
        self.table = table
        self.distance = {}

        for covariate in covariates:
            with _quiet():
                prepared = bl._prepare_for_distance_tests(table, covariate)
            if prepared is None:
                self.distance[covariate] = None
                continue
            matrix, _, labels = prepared
            row_of_sample = {sample: row for row, sample in enumerate(labels.index)}
            positions = np.array([row_of_sample.get(sample, -1) for sample in table.index],
                                 dtype=int)
            self.distance[covariate] = (matrix, np.asarray(labels.values), positions)

    def block(self, covariate, chosen):
        prepared = self.distance.get(covariate)
        if prepared is None:
            return None, None
        matrix, labels, positions = prepared
        rows = positions[chosen]
        rows = rows[rows >= 0]
        if len(rows) < 3:
            return None, None
        return matrix[np.ix_(rows, rows)], labels[rows]


def _permanova_p_value(block, labels, permutations):
    from skbio.stats.distance import DistanceMatrix
    from skbio.stats.distance import permanova as skbio_permanova
    if len(np.unique(labels)) < 2:
        return None
    try:
        matrix_object = DistanceMatrix(block, ids=[str(i) for i in range(block.shape[0])])
        with _quiet():
            result = skbio_permanova(matrix_object, grouping=list(labels),
                                     permutations=int(permutations),
                                     **bl._seed_kwargs(skbio_permanova))
        return float(result['p-value'])
    except Exception:
        return None


def _row_for_method(space, chosen, dataset_name, study_name, factor_of_interest,
                    measures, permutations):
    row = {'datasetName': dataset_name, 'method': space.name}

    for covariate in (study_name, factor_of_interest):
        block, labels = space.block(covariate, chosen)
        if block is None:
            continue
        lisi = bl.lisi_name(covariate, study_name, factor_of_interest)
        row[f'permanova-{covariate}-R2-corrected'] = bl._r2_from_distance(block, labels)
        row[f'permanova-{covariate}-p-value-corrected'] = _permanova_p_value(block, labels,
                                                                             permutations)
        try:
            row[f'silhouette-{covariate}-corrected'] = bl._silhouette_from_distance(block, labels)
        except Exception:
            pass
        try:
            with _quiet():
                neighbourhood = bl._neighbourhood_metrics_from_distance(block, labels)
            row[f'kBET-{covariate}-acceptance-corrected'] = neighbourhood.get('kBET')
            row[f'{lisi}-{covariate}-corrected'] = neighbourhood.get('LISI')
            row[f'graph-connectivity-{covariate}-corrected'] = neighbourhood.get('graph-connectivity')
            row[f'alignment-score-{covariate}-corrected'] = neighbourhood.get('alignment-score')
            row[f'entropy-score-{covariate}-corrected'] = neighbourhood.get('entropy-score')
        except Exception:
            pass

    if measures != 'all':
        return row

    subset = space.table.iloc[chosen]
    for covariate in (study_name, factor_of_interest):
        try:
            with _quiet():
                row[f'features-associated-{covariate}-percent-corrected'] = \
                    bl.feature_association(subset, covariate)
        except Exception:
            pass
    try:
        with _quiet():
            components = bl.pvca(subset, study_name, factor_of_interest)
        for component, value in (components or {}).items():
            row[f'pvca-{component}-percent-corrected'] = value
    except Exception:
        pass
    try:
        with _quiet():
            parts = bl.variance_partitioning(subset, study_name, factor_of_interest)
        for part, value in (parts or {}).items():
            row[f'varpart-{part}-corrected'] = value
    except Exception:
        pass
    if getattr(glb, 'run_auroc', True):
        try:
            with _quiet():
                auroc = bl.classification_auroc(subset, dataset_name=dataset_name,
                                                method=space.name)
            row[f'AUROC-{factor_of_interest}-cv-corrected'] = auroc.get('cv')
            row[f'AUROC-{factor_of_interest}-lobo-corrected'] = auroc.get('lobo')
        except Exception:
            pass
    return row


_WORKER_SPACES = {}
_WORKER_ORDER = []
_WORKER_SETTINGS = {}


def _rows_for_resample(chosen):
    return [_row_for_method(_WORKER_SPACES[name], chosen,
                            _WORKER_SETTINGS['dataset_name'],
                            _WORKER_SETTINGS['study_name'],
                            _WORKER_SETTINGS['factor_of_interest'],
                            _WORKER_SETTINGS['measures'],
                            _WORKER_SETTINGS['permutations'])
            for name in _WORKER_ORDER]


def _resample_tables(resamples, jobs):
    if jobs is None or jobs <= 1:
        for chosen in resamples:
            yield _rows_for_resample(chosen)
        return
    try:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor
        context = multiprocessing.get_context('fork')
    except (ImportError, ValueError):
        for chosen in resamples:
            yield _rows_for_resample(chosen)
        return
    with ProcessPoolExecutor(max_workers=int(jobs), mp_context=context) as pool:
        for rows in pool.map(_rows_for_resample, resamples, chunksize=1):
            yield rows


def _load_tables(dataset_name, raw_data_folder, corrected_outputs, cleaned_folder,
                 sample_id_column, study_name, factor_of_interest):
    import glob
    import methods as bmethods

    metadata = pd.read_csv(f"{raw_data_folder}/metadata.csv").set_index(sample_id_column)
    keep = [study_name, factor_of_interest]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
        keep.extend(line.strip() for line in covariate_file)
    metadata = metadata[[column for column in keep if column in metadata.columns]]

    def load(path):
        table = pd.read_csv(path, low_memory=False)
        table = table.rename(columns={"Unnamed: 0": sample_id_column})
        if sample_id_column in table.columns:
            table = table.set_index(sample_id_column)
        return bl.merge_dataframes(metadata[metadata.index.isin(table.index)], table)

    cleaned = glob.glob(f"{cleaned_folder}/clean-{dataset_name}.csv") or \
        [f for f in glob.glob(f"{cleaned_folder}/*.csv")
         if bl.dataset_key(os.path.basename(f)) == dataset_name]
    if not cleaned:
        print(f"Stability analysis: no cleaned dataset found for {dataset_name}, skipping.")
        return None

    tables = {'uncorrected': load(cleaned[0])}
    for path in sorted(glob.glob(f"{corrected_outputs}/*.csv")):
        found = _match_corrected_file(os.path.basename(path), dataset_name)
        if found is not None and found not in tables:
            tables[found] = load(path)
    return tables


_DATE_STAMP = r'-\d{4}-\d{2}-\d{2}-\d{6}'


def _match_corrected_file(filename, dataset_name):
    import re
    import methods as bmethods

    if not filename.lower().endswith('.csv'):
        return None
    stem = filename[:-len('.csv')]
    for method in sorted(bmethods.ALL_METHODS, key=lambda m: -len(m.suffix)):
        base = method.suffix[:-len('-tmp')] if method.suffix.endswith('-tmp') else method.suffix
        position = stem.rfind(base)
        if position < 0:
            continue
        trailing = stem[position + len(base):]
        if trailing not in ('', '-tmp') and not re.fullmatch(_DATE_STAMP, trailing):
            continue
        if bl.dataset_key(stem[:position]) == dataset_name:
            return method.method
    return None


def analyse(dataset_name, raw_data_folder, corrected_outputs, sample_id_column,
            study_name, factor_of_interest, cleaned_folder,
            repeats=None, fraction=None, measures=None, permutations=None, alpha=None,
            jobs=None):

    repeats = int(repeats if repeats is not None else getattr(glb, 'stability_resamples', 100))
    fraction = float(fraction if fraction is not None else getattr(glb, 'stability_fraction', 0.8))
    measures = str(measures if measures is not None
                   else getattr(glb, 'stability_measures', 'all')).lower()
    permutations = int(permutations if permutations is not None
                       else getattr(glb, 'stability_permanova_permutations', 199))
    alpha = float(alpha if alpha is not None else getattr(glb, 'significance_alpha', 0.05))
    jobs = int(jobs if jobs is not None else getattr(glb, 'stability_jobs', 1) or 1)
    if measures not in MEASURE_SETS:
        measures = 'all'
    rng = np.random.default_rng(getattr(glb, 'random_seed', 42))

    tables = _load_tables(dataset_name, raw_data_folder, corrected_outputs, cleaned_folder,
                          sample_id_column, study_name, factor_of_interest)
    if tables is None:
        return None
    if len(tables) < 3:
        print(f"Stability analysis: fewer than two corrected datasets for {dataset_name}, skipping.")
        return None

    common = None
    for table in tables.values():
        table.index = table.index.astype(str)
        common = table.index if common is None else common.intersection(table.index)
    common = pd.Index(sorted(pd.Index(common).unique()))
    if len(common) < 20:
        print(f"Stability analysis: only {len(common)} samples shared by all methods, skipping.")
        return None
    tables = {name: table.loc[common] for name, table in tables.items()}

    reference = tables['uncorrected']
    batch_labels = reference[study_name].astype(str).to_numpy()
    phenotype_labels = reference[factor_of_interest].astype(str).to_numpy()
    if len(np.unique(batch_labels)) < 2 or len(np.unique(phenotype_labels)) < 2:
        print("Stability analysis: needs at least two batches and two phenotype groups, skipping.")
        return None

    resamples = bl._stratified_resamples(batch_labels, phenotype_labels, fraction, repeats, rng)
    method_names = [name for name in tables if name != 'uncorrected']
    print(f"Stability analysis on {dataset_name}: {repeats} subsamples of "
          f"{int(round(fraction * 100))}% of {len(common)} samples, "
          f"{len(method_names)} methods, measures = {measures}"
          + (f", {jobs} in parallel" if jobs > 1 else "") + ".")

    spaces = {}
    for name, table in tables.items():
        spaces[name] = _MethodSpace(name, table, (study_name, factor_of_interest))

    limiter = _limit_blas_threads(getattr(glb, 'stability_blas_threads', 1))

    wins = {name: 0 for name in method_names}
    passed_gate = {name: 0 for name in method_names}
    scores = {name: [] for name in method_names}
    retention_batch = {name: [] for name in method_names}
    retention_phenotype = {name: [] for name in method_names}
    rankings = []
    gate_skipped = 0
    undecided = 0

    batch_r2_column = f'permanova-{study_name}-R2-corrected'
    phenotype_r2_column = f'permanova-{factor_of_interest}-R2-corrected'

    global _WORKER_SPACES, _WORKER_ORDER, _WORKER_SETTINGS
    _WORKER_SPACES = spaces
    _WORKER_ORDER = ['uncorrected'] + method_names
    _WORKER_SETTINGS = {'dataset_name': dataset_name, 'study_name': study_name,
                        'factor_of_interest': factor_of_interest, 'measures': measures,
                        'permutations': permutations}

    for number, rows in enumerate(_resample_tables(resamples, jobs), start=1):
        table = pd.DataFrame(rows)

        baseline = table[table['method'] == 'uncorrected']
        raw_batch = pd.to_numeric(baseline.get(batch_r2_column), errors='coerce').iloc[0] \
            if batch_r2_column in table.columns else np.nan
        raw_phenotype = pd.to_numeric(baseline.get(phenotype_r2_column), errors='coerce').iloc[0] \
            if phenotype_r2_column in table.columns else np.nan

        with _quiet():
            scored, _ = bscoring.score_methods(table, study_name, factor_of_interest, alpha)

        candidates = scored[scored['method'] != 'uncorrected']
        if candidates.empty:
            undecided += 1
            continue
        if bool(candidates[bscoring.GATE_SKIPPED_COLUMN].iloc[0]):
            gate_skipped += 1

        winner = candidates[candidates[bscoring.BEST_COLUMN] == 'Best performance']
        if winner.empty:
            undecided += 1
        else:
            wins[str(winner['method'].iloc[0])] += 1

        for _, entry in candidates.iterrows():
            name = str(entry['method'])
            if name not in scores:
                continue
            if entry[bscoring.ACCEPTED_COLUMN] == True:
                passed_gate[name] += 1
            scores[name].append(float(entry[bscoring.SCORE_COLUMN] or 0.0))
            if pd.notna(raw_batch) and raw_batch:
                value = pd.to_numeric(entry.get(batch_r2_column), errors='coerce')
                if pd.notna(value):
                    retention_batch[name].append(100.0 * value / raw_batch)
            if pd.notna(raw_phenotype) and raw_phenotype:
                value = pd.to_numeric(entry.get(phenotype_r2_column), errors='coerce')
                if pd.notna(value):
                    retention_phenotype[name].append(100.0 * value / raw_phenotype)

        ranked = sorted(int(entry[bscoring.RANK_COLUMN])
                        for _, entry in candidates.iterrows() if entry[bscoring.RANK_COLUMN])
        number_of_methods = len(method_names)
        shared_last = (len(ranked) + 1 + number_of_methods) / 2.0
        places = {}
        for _, entry in candidates.iterrows():
            rank = entry[bscoring.RANK_COLUMN]
            places[str(entry['method'])] = float(rank) if rank else shared_last
        if len(places) == number_of_methods:
            rankings.append([places[name] for name in method_names])

        if number % 10 == 0 or number == repeats:
            print(f"   {number}/{repeats} subsamples", end='\r', flush=True)
    print()

    if limiter is not None:
        limiter.restore_original_limits()

    decided = repeats - undecided

    def interval(values):
        if not values:
            return (None, None, None)
        array = np.asarray(values, dtype=float)
        return (float(np.median(array)), float(np.percentile(array, 2.5)),
                float(np.percentile(array, 97.5)))

    summary = []
    for name in method_names:
        median_batch, low_batch, high_batch = interval(retention_batch[name])
        median_phenotype, low_phenotype, high_phenotype = interval(retention_phenotype[name])
        median_score, low_score, high_score = interval(scores[name])
        summary.append({
            'method': name,
            'selection-frequency': (wins[name] / decided) if decided else None,
            'wins': wins[name],
            'resamples-decided': decided,
            'passed-gate-frequency': (passed_gate[name] / decided) if decided else None,
            'consensus-score-median': median_score,
            'consensus-score-low': low_score,
            'consensus-score-high': high_score,
            'batch-retention-median': median_batch,
            'batch-retention-low': low_batch,
            'batch-retention-high': high_batch,
            'phenotype-retention-median': median_phenotype,
            'phenotype-retention-low': low_phenotype,
            'phenotype-retention-high': high_phenotype,
        })
    summary.sort(key=lambda row: (-(row['selection-frequency'] or 0), row['method']))

    return {'dataset': dataset_name, 'resamples': repeats, 'decided': decided,
            'fraction': fraction, 'measures': measures, 'methods': summary,
            'gate-skipped-resamples': gate_skipped,
            'kendalls-w': bl.kendalls_w(rankings)}


def _apply_settings(values):
    for name in ('run_permdisp', 'permdisp_permutations', 'run_neighbourhood_metrics',
                 'neighbourhood_k', 'evaluation_space', 'run_auroc', 'random_seed',
                 'permanova_permutations', 'significance_alpha', 'kbet_alpha', 'auroc_trees',
                 'auroc_folds', 'pvca_variance_threshold', 'pvca_max_components',
                 'stability_resamples', 'stability_fraction', 'stability_measures',
                 'stability_permanova_permutations', 'stability_blas_threads', 'stability_jobs'):
        if name in values:
            setattr(glb, name, values[name])
    glb.run_permdisp = False


def _datasets_on_disk(cleaned_folder):
    import glob
    names = []
    for path in sorted(glob.glob(f"{cleaned_folder}/*.csv")):
        names.append(bl.dataset_key(os.path.basename(path)))
    return names


def main(argv=None):
    import argparse
    import json
    import time

    import bml.files as bfiles
    import settings as bsettings
    import validation as bvalidation

    parser = argparse.ArgumentParser(
        description='Run only the stability analysis over a finished BERNARD run.')
    parser.add_argument('cfg_file', help='the same bernard_cfg.txt the run used')
    parser.add_argument('work_dir', nargs='?', default=None,
                        help='base for relative paths in the settings file '
                             '(default: the folder the settings file is in)')
    parser.add_argument('--datasets', default=None,
                        help='comma separated dataset names (default: every dataset of the run)')
    parser.add_argument('--resamples', type=int, default=None,
                        help='how many subsamples to draw (default: stability_resamples)')
    parser.add_argument('--fraction', type=float, default=None,
                        help='share of samples each subsample keeps (default: stability_fraction)')
    parser.add_argument('--measures', choices=MEASURE_SETS, default=None,
                        help='"all" replays all 21 ranking lists, "distance" only the 14 that come '
                             'off the distance matrix (faster, and it has to be said so in the '
                             'report). Default: stability_measures, or "all".')
    parser.add_argument('--permutations', type=int, default=None,
                        help='PERMANOVA permutations inside a subsample, for the gate p-values '
                             '(default: 199)')
    parser.add_argument('--jobs', type=int, default=None,
                        help='measure this many subsamples at the same time, in separate '
                             'processes (default: stability_jobs, or 1). What makes '
                             '--measures all affordable on a large collection.')
    parser.add_argument('--out', default=None,
                        help='where to write the tables and figures (default: the run\'s outputs)')
    args = parser.parse_args(argv)

    work_dir = (args.work_dir.rstrip('/') if args.work_dir
                else os.path.dirname(os.path.abspath(args.cfg_file)))

    values, problems = bsettings.read(args.cfg_file)
    if bvalidation.has_errors(problems):
        bvalidation.report(problems, 'The settings file ' + args.cfg_file)
        return 2

    bernard_input = values.get('bernard_input')
    if not bernard_input:
        print('Error: bernard_input is not set in the settings file.')
        return 2
    if bernard_input.startswith('~'):
        bernard_input = os.path.expanduser(bernard_input)
    elif bernard_input.startswith('.'):
        bernard_input = work_dir + bernard_input[1:]
    elif not os.path.isabs(bernard_input):
        bernard_input = work_dir + '/' + bernard_input
    bernard_folder = bernard_input.rstrip('/')
    if bfiles.split(bernard_folder)['ext'].lower() == '.zip':
        bernard_folder = bfiles.split(bernard_folder)['dir']

    glb.bernard_folder = bernard_folder
    glb.raw_data_folder = bernard_folder + '/raw-data'
    _apply_settings(values)

    raw_data_folder = glb.raw_data_folder
    outputs = bernard_folder + '/outputs'
    cleaned_folder = outputs + '/cleaned'
    corrected_outputs = outputs + '/corrected'
    output_path = (args.out.rstrip('/') if args.out else outputs)

    for folder in (raw_data_folder, cleaned_folder, corrected_outputs):
        if not os.path.isdir(folder):
            print(f'Error: {folder} does not exist. '
                  f'The stability analysis reads what a finished run left behind, so run BERNARD '
                  f'on this input folder first.')
            return 2
    os.makedirs(output_path, exist_ok=True)
    os.makedirs(output_path + '/report', exist_ok=True)

    with open(f'{raw_data_folder}/config.json', 'r') as config_file:
        config = json.load(config_file)
    study_name = str(config['study_name'])
    factor_of_interest = str(config['factor_of_interest'])
    sample_id_column = str(config['sample_id_column'])

    datasets = ([name.strip() for name in args.datasets.split(',') if name.strip()]
                if args.datasets else _datasets_on_disk(cleaned_folder))
    if not datasets:
        print(f'Error: no cleaned datasets found in {cleaned_folder}.')
        return 2

    measures = args.measures or getattr(glb, 'stability_measures', 'all')
    date = time.strftime('%Y-%m-%d-%H%M%S')
    print(f'\nStability analysis only, on {bernard_folder}')
    print(f'   batch column "{study_name}", biology column "{factor_of_interest}"')
    print(f'   {len(datasets)} dataset(s): {", ".join(datasets)}\n')

    skipped, written = [], []
    for dataset in datasets:
        start = time.time()
        try:
            result = analyse(dataset, raw_data_folder, corrected_outputs, sample_id_column,
                             study_name, factor_of_interest, cleaned_folder,
                             repeats=args.resamples, fraction=args.fraction,
                             measures=measures, permutations=args.permutations,
                             jobs=args.jobs)
        except Exception as failure:
            print(f'ERROR: stability analysis failed for {dataset}: {failure}')
            skipped.append((dataset, str(failure)))
            continue
        if not result:
            skipped.append((dataset, 'not enough corrected data on disk to compare methods'))
            continue

        table = pd.DataFrame(result['methods'])
        excel = f'{output_path}/stability-{dataset}-{date}.xlsx'
        table.to_excel(excel, index=False)
        bl.stability_plot(result, output_path, f'{dataset}-stability-{date}')
        written.append(excel)

        top = result['methods'][0]
        print(f"\n{dataset}: {top['method']} chosen in {top['wins']} of {result['decided']} "
              f"subsamples ({100 * (top['selection-frequency'] or 0):.0f}%)"
              + (f", Kendall's W {result['kendalls-w']:.2f}"
                 if result['kendalls-w'] is not None else '')
              + f"   [{time.time() - start:.0f}s]")
        if (top['selection-frequency'] or 0) < 0.5:
            print(f'WARNING: no method wins a majority of the subsamples for {dataset}. '
                  f'The single best method should be reported as one of several defensible '
                  f'choices.')
        if result['gate-skipped-resamples']:
            print(f"NOTE: in {result['gate-skipped-resamples']} of {result['decided']} subsamples "
                  f"no method passed step 1, and the winner there is the best of a field in which "
                  f"none succeeded.")

    print('')
    print('=' * 99)
    for path in written:
        print(f'   written  {path}')
    for dataset, reason in skipped:
        print(f'   skipped  {dataset} - {reason}')
    if skipped:
        print('\nA dataset is skipped when the corrected data of its methods is no longer on disk. '
              '\nThat is what delete_tmp_corrected_data = yes does at the end of a run; set it to '
              'no to keep\nevery method and make the stability analysis repeatable afterwards.')
    return 0 if written else 1


if __name__ == '__main__':
    sys.exit(main())
