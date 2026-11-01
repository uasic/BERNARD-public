
import difflib
import io
import os
from collections import namedtuple

import bml.params as params


Setting = namedtuple('Setting', ['name', 'kind', 'default', 'minimum', 'maximum',
                                 'choices', 'section', 'help'])


def _setting(name, kind, default=None, minimum=None, maximum=None, choices=None,
             section='Other settings', help=''):
    return Setting(name, kind, default, minimum, maximum, choices, section, help)


SETTINGS = [

    _setting(
        'bernard_input', 'path', section='Input data',
        help='The folder holding the data, or a ZIP archive of it. THE ONLY SETTING THAT MUST BE\n'
             'GIVEN. A folder must contain a raw-data subfolder with metadata.csv and at least one\n'
             'dataset file. The path may be absolute (/home/anna/study), relative to the home\n'
             'folder (~/study) or relative to the work folder given on the command line (./study).\n'
             'A ZIP archive is unpacked into raw-data next to the archive.'),

    _setting(
        'datasets', 'list', section='Input data',
        help='Which dataset files inside raw-data are analysed. By default every file that is not\n'
             'metadata.csv, config.json or covariates.txt is analysed. Give a comma separated list\n'
             'of file names to analyse only some of them, which is the quickest way to try a\n'
             'setting out on one dataset before running the whole collection.\n'
             '    datasets = stool.csv, saliva.csv'),

    _setting(
        'sample_id_column', 'string', section='Meaning of the metadata columns',
        help='The column holding the unique name of each sample. These three settings say what the\n'
             'columns of metadata.csv MEAN, and they are what every calculation is built on. They\n'
             'may be written here, or left in raw-data/config.json as in earlier versions of\n'
             'BERNARD; what is written here wins, and is copied into config.json so that the R\n'
             'scripts see the same thing. Writing them here means one file to edit instead of three.'),

    _setting(
        'study_name', 'string', section='Meaning of the metadata columns',
        help='The BATCH column: what the correction has to REMOVE. Usually which laboratory, run or\n'
             'published study a sample came from (bioproject, batch, centre, plate...).'),

    _setting(
        'factor_of_interest', 'string', section='Meaning of the metadata columns',
        help='The BIOLOGY column: what the correction has to KEEP. Usually the phenotype or the\n'
             'treatment (diagnosis, group, healthy/sick...). A correction that removes the batch\n'
             'effect but also erases this column has destroyed the answer and is rejected.'),

    _setting(
        'covariates', 'list', section='Meaning of the metadata columns',
        help='Extra metadata columns (age, sex, country, diet) that are measured and reported, but\n'
             'are not used to choose the best method. Comma separated. May also be left in\n'
             'raw-data/covariates.txt, one name per line; what is written here wins.\n'
             '    covariates = age, sex, country\n'
             'Write "none" for a dataset that has no extra metadata columns.'),

    _setting(
        'select_thresholdSamples', 'float', default=0.9, minimum=0.0, maximum=1.0,
        section='Cleaning of the raw data',
        help='Samples that are zero or empty in more than this share of the features are dropped.\n'
             '0.9 means "drop a sample that is 90% zeros". Between 0 and 1.'),

    _setting(
        'select_thresholdFeatures', 'float', default=0.9, minimum=0.0, maximum=1.0,
        section='Cleaning of the raw data',
        help='Features (bacteria, genes) that are zero or empty in more than this share of the\n'
             'samples are dropped. Between 0 and 1.'),

    _setting(
        'outlier_contamination', 'float', default=0.05, minimum=0.0, maximum=0.5,
        section='Cleaning of the raw data',
        help='Share of samples that IsolationForest marks as strange and removes, before the\n'
             'cleaned dataset is written. 0.05 removes the 5% most unusual samples; 0 switches\n'
             'outlier removal off entirely.'),

    _setting(
        'correction_methods', 'list', default='all', section='Which correction methods to run',
        help='The batch effect correction methods this run performs: every name listed below that\n'
             'does NOT have a # in front of it. Putting a # in front of a name leaves that method\n'
             'out, which is the quickest way to shorten a run, because all of them together take a\n'
             'long time. Comment them all out and BERNARD stops and says so rather than running\n'
             'something that was not asked for.\n'
             'The same thing may be written on one line instead, comma separated, or as "all":\n'
             '    correction_methods = pyCombat, ConQuR, PLSDA\n'
             'The names are not case sensitive and the order makes no difference.'),

    _setting(
        'exclude_correction_methods', 'list', section='Which correction methods to run',
        help='The other way round: run all the methods EXCEPT these. Useful when one method is not\n'
             'installed on this machine or is known to be slow on this dataset. The names are the\n'
             'ones listed under correction_methods above.\n'
             '    exclude_correction_methods = ConQuR, MetaDICT'),

    _setting(
        'stop_on_method_failure', 'bool', default=False, section='Which correction methods to run',
        help='What happens when a correction method fails (a missing R package, a dataset its\n'
             'mathematics cannot handle). By default BERNARD reports the failure, leaves that\n'
             'method out of the comparison and carries on with the others, so one broken method\n'
             'does not throw away the whole run. Set to Yes to stop at the first failure instead.'),

    _setting(
        'max_parallel_methods', 'int', default=0, minimum=0, maximum=64,
        section='Running several methods at the same time',
        help='How many correction methods are allowed to run at the same time. Each method is a\n'
             'separate program (an R script) that reads the same cleaned data and writes its own\n'
             'result file, so several of them can run side by side on different processor cores\n'
             'and the whole run finishes in a fraction of the time.\n'
             '    0  choose automatically from the number of cores in this machine (the default)\n'
             '    1  one after another, as older versions of BERNARD did\n'
             '    n  at most n at the same time\n'
             'EACH method holds the dataset in memory while it runs, so on a large dataset or a\n'
             'machine with little memory, lower this number. If a run is killed for running out of\n'
             'memory, set it to 1.'),

    _setting(
        'method_timeout_minutes', 'int', default=0, minimum=0, maximum=100000,
        section='Running several methods at the same time',
        help='Stop a correction method that has been running for longer than this many minutes,\n'
             'report it as timed out and carry on with the others. 0 means no limit (the default).\n'
             'Worth setting on a long unattended run, where a single method caught in a loop would\n'
             'otherwise hold up everything that comes after it.'),

    _setting(
        'parallel_analysis', 'bool', default=True,
        section='Running several methods at the same time',
        help='Whether the measuring of a finished method (PERMANOVA, kBET, AUROC...) starts while\n'
             'the remaining methods are still correcting, rather than waiting for all of them.\n'
             'The results do not depend on it: they are always written in the same order, so two\n'
             'runs on the same data give the same tables either way.'),

    _setting(
        'evaluation_space', 'choice', default='zscore-euclidean',
        choices=['zscore-euclidean', 'aitchison', 'braycurtis', 'euclidean'],
        section='How the results are measured',
        help='The space in which the raw dataset and all the corrected datasets are compared with\n'
             'each other. Every method returns its result in its own space (CLR, log, batch mean\n'
             'centred values, percentiles, counts), so the same transformation is applied to all of\n'
             'them first; otherwise a method could score well simply by shrinking the features that\n'
             'carry the batch effect, without removing any batch effect at all.\n'
             '    zscore-euclidean  every feature standardised, then Euclidean distance. Works for\n'
             '                      every method, including those that return negative values.\n'
             '    aitchison         centred log ratio, then Euclidean. The standard choice for\n'
             '                      compositional data.\n'
             '    braycurtis        Bray-Curtis dissimilarity, the usual choice for abundances.\n'
             '    euclidean         no transformation. How earlier BERNARD versions calculated the\n'
             '                      distances, kept for comparison only.'),

    _setting(
        'run_permdisp', 'bool', default=True, section='How the results are measured',
        help='PERMANOVA notices that groups differ, but it cannot tell a shift of the group centres\n'
             '(a real batch effect) from a difference in how spread out the groups are. PERMDISP\n'
             'tests the spread directly. It is considerably slower than PERMANOVA.'),

    _setting(
        'permdisp_permutations', 'int', default=999, minimum=9, maximum=100000,
        section='How the results are measured',
        help='Number of permutations PERMDISP uses. Fewer is faster but gives a coarser p-value.\n'
             'The whole test is repeated for every metadata column and every correction method, so\n'
             'this is the setting to lower first when a run on a large dataset takes too long: the\n'
             'runtime is proportional to it, and 99 permutations still give a p-value to two\n'
             'decimal places.'),

    _setting(
        'permdisp_test', 'choice', default='median', choices=['median', 'centroid'],
        section='How the results are measured',
        help='The centre of a group that PERMDISP measures the spread around. It is recalculated\n'
             'for every permutation, which is what makes the test slow.\n'
             '    median    the spatial (geometric) median, the robust choice and the one earlier\n'
             '              BERNARD versions used.\n'
             '    centroid  the group mean, as in the original PERMDISP. About four times faster,\n'
             '              but more easily pulled about by a single distant sample.'),

    _setting(
        'run_neighbourhood_metrics', 'bool', default=True, section='How the results are measured',
        help='kBET, LISI (iLISI and cLISI) and the graph connectivity. PERMANOVA and the silhouette\n'
             'width describe the dataset as a whole; these describe what a single sample sees around\n'
             'it, which is where a batch effect that survived the correction shows itself first:\n'
             'batches can sit as separate clumps inside a shared space without moving the group\n'
             'centres far enough for PERMANOVA to notice.'),

    _setting(
        'neighbourhood_k', 'int', default=30, minimum=2, maximum=1000,
        section='How the results are measured',
        help='How many nearest neighbours kBET, LISI and the graph connectivity look at. Lowered\n'
             'automatically when a dataset has too few samples for the given value.'),

    _setting(
        'run_stability', 'bool', default=True, section='How the results are measured',
        help='Repeat the whole measurement and the choice of the best method on many random\n'
             'subsamples of the data, to find out whether the winner is a real winner or a coin\n'
             'toss. A single run names one method best, but that verdict comes from one sample of\n'
             'people; if two methods are separated by a fraction of a percent, a slightly different\n'
             'set of samples would have chosen the other one. The report then says "chosen in 34 of\n'
             '100 subsamples" instead of "best", which is the honest form of a close result.\n'
             'The corrections themselves are fitted once on the full dataset and not refitted\n'
             'inside every subsample, so this measures the stability of the DECISION rather than of\n'
             'the whole procedure. Refitting sixteen methods a hundred times would take days.'),

    _setting(
        'stability_resamples', 'int', default=100, minimum=10, maximum=10000,
        section='How the results are measured',
        help='How many subsamples the stability analysis draws. More gives a finer selection\n'
             'frequency: 100 resolves it to a percent, which is enough to tell a clear winner from\n'
             'a close call. Cheap to raise, because the distances are calculated once and reused.'),

    _setting(
        'stability_fraction', 'float', default=0.8, minimum=0.3, maximum=0.95,
        section='How the results are measured',
        help='Share of the samples each subsample keeps, drawn separately from within every\n'
             'combination of batch and phenotype so that the design of the subsample matches the\n'
             'design of the study. Lower values disturb the data more and therefore give a harsher\n'
             'test of stability; 0.8 is the usual choice.'),

    _setting(
        'stability_measures', 'choice', default='all', choices=['all', 'distance'],
        section='How the results are measured',
        help='Which of the twenty-one ranking lists the stability analysis replays inside every\n'
             'subsample. The selection frequency it reports is only the stability of the method\n'
             'BERNARD actually names if it decides the same way BERNARD does, which is what "all"\n'
             'means.\n'
             '    all       all twenty-one lists and the gate: exactly the rule of scoring.py.\n'
             '    distance  only the fourteen lists that come off the distance matrix, plus the\n'
             '              gate. Leaves out PVCA, variance partitioning, the per-feature\n'
             '              association and AUROC, which need the feature matrix and take most of\n'
             '              the time. Roughly ten times faster, and a report that uses it has to\n'
             '              say so, because it is not quite the rule that chose the winner.'),

    _setting(
        'stability_permanova_permutations', 'int', default=199, minimum=9, maximum=100000,
        section='How the results are measured',
        help='Permutations of the PERMANOVA run INSIDE a subsample. It is used only for the two\n'
             'p-values of step 1 (is the batch effect gone, is the biology still there), not for\n'
             'any of the R2 values, which are calculated without permuting. 199 resolves a p-value\n'
             'to 0.005, which is enough for a gate set at 0.05, and it is run once per method per\n'
             'subsample, so raising it is felt directly in the runtime.'),

    _setting(
        'stability_blas_threads', 'int', default=1, minimum=0, maximum=256,
        section='How the results are measured',
        help='How many threads the linear algebra library may use during the stability analysis.\n'
             'The analysis is thousands of SMALL matrix operations, and spreading each of them\n'
             'over every core costs far more in thread synchronisation than it saves: a 76 x 697\n'
             'PCA measured 1.87 s on eleven threads and 0.002 s on one. 1 is therefore the right\n'
             'answer here, unlike almost everywhere else. 0 leaves the library alone.'),

    _setting(
        'stability_jobs', 'int', default=1, minimum=1, maximum=256,
        section='How the results are measured',
        help='How many subsamples are measured at the same time, in separate processes. The\n'
             'subsamples are independent of one another, and the linear algebra has just been\n'
             'pinned to one thread (see stability_blas_threads), so the remaining cores are idle\n'
             'unless this is raised. Raising it is what makes stability_measures = all affordable\n'
             'on a large collection; the measured matrices are shared with the workers rather than\n'
             'copied, so the memory does not multiply with it. 1 runs them one after another.\n'
             'No effect on Windows, where processes cannot be forked and sending the matrices to\n'
             'each worker would cost more than the parallelism saves.'),

    _setting(
        'run_auroc', 'bool', default=True, section='How the results are measured',
        help='Downstream check: a random forest is trained on the features and scored on samples it\n'
             'has not seen, before and after correction. It is the only measure that says whether\n'
             'the corrected data became more USEFUL for the biological question, and not merely\n'
             'differently structured. Two numbers are reported: cv (cross validation over all\n'
             'samples) and lobo (leave one batch out, which shows whether a model built on some\n'
             'studies transfers to a study it has never seen). It is the slowest of the measures.'),

    _setting(
        'random_seed', 'int', default=42, minimum=0, maximum=2147483647,
        section='The fine detail of the statistics',
        help='The number every random choice in the run starts from: the permutations of PERMANOVA\n'
             'and PERMDISP, the random forest, the outlier search, t-SNE and MDS, and the R methods\n'
             'as well. Two runs of the same data with the same seed give exactly the same numbers,\n'
             'which is what makes a result reproducible. Change it to check that a finding does not\n'
             'depend on one particular draw.'),

    _setting(
        'permanova_permutations', 'int', default=999, minimum=9, maximum=100000,
        section='The fine detail of the statistics',
        help='Number of permutations PERMANOVA uses. The p-value can never be finer than\n'
             '1/(permutations+1), so 999 gives p as low as 0.001. Fewer is faster and coarser.'),

    _setting(
        'significance_alpha', 'float', default=0.05, minimum=0.0000001, maximum=0.5,
        section='The fine detail of the statistics',
        help='The p-value below which a result is called significant. Used when counting how many\n'
             'features are associated with a covariate (after correction for multiple testing) and\n'
             'when deciding whether a PERMANOVA result is confounded by a difference in spread.'),

    _setting(
        'kbet_alpha', 'float', default=0.05, minimum=0.0000001, maximum=0.5,
        section='The fine detail of the statistics',
        help='The p-value kBET uses to decide whether the neighbourhood of one sample holds the\n'
             'batches in the same proportion as the whole dataset. Changing it changes what the\n'
             'reported kBET acceptance rate means, so it is best left alone unless the run is being\n'
             'compared against a published kBET result that used a different value.'),

    _setting(
        'auroc_trees', 'int', default=200, minimum=10, maximum=10000,
        section='The fine detail of the statistics',
        help='Number of trees in the random forest behind the AUROC check. More trees give a\n'
             'steadier estimate and take proportionally longer.'),

    _setting(
        'auroc_folds', 'int', default=5, minimum=2, maximum=20,
        section='The fine detail of the statistics',
        help='Number of cross validation folds for the AUROC check. Lowered automatically when the\n'
             'smallest phenotype group has fewer samples than this.'),

    _setting(
        'pvca_variance_threshold', 'float', default=0.8, minimum=0.1, maximum=1.0,
        section='The fine detail of the statistics',
        help='How much of the total variance the PCA directions used by PVCA have to carry between\n'
             'them. 0.8 means "use as many directions as it takes to account for 80% of the\n'
             'variability, then work out where that variability comes from".'),

    _setting(
        'pvca_max_components', 'int', default=10, minimum=1, maximum=200,
        section='The fine detail of the statistics',
        help='The largest number of PCA directions PVCA looks at, whatever the threshold above says.'),

    _setting(
        'tsne_perplexity', 'float', default=0.0, minimum=0.0, maximum=500.0,
        section='The fine detail of the statistics',
        help='The perplexity of the t-SNE plot: roughly how many neighbours each sample is placed\n'
             'in relation to. 0 (the default) chooses it from the number of samples, which is what\n'
             'BERNARD has always done. Set a number to fix it, for example to make the t-SNE plots\n'
             'of two differently sized datasets comparable.'),

    _setting(
        'figure_dpi', 'int', default=300, minimum=72, maximum=1200,
        section='The fine detail of the statistics',
        help='Resolution of the PNG images in the report. 300 is enough for print; a higher value\n'
             'makes the PDF report considerably larger.'),

    _setting(
        'diagnosis_variability_retention', 'float', default=50.0, minimum=0.0, maximum=100.0,
        section='Choosing the best method',
        help='Stability analysis only. How much of the biological signal a method must preserve to\n'
             'count as a candidate inside a resample, as a percentage of the signal in the\n'
             'uncorrected data. It does not affect which method the run itself reports as best.'),

    _setting(
        'diagnosis_variability_lower_limit', 'float', default=10.0, minimum=0.0, maximum=100.0,
        section='Choosing the best method',
        help='Stability analysis only. If no method reaches the requirement above inside a\n'
             'resample, it is lowered step by step, but never below this value; a resample with no\n'
             'candidate left is counted as undecided.'),

    _setting(
        'variability_threshold_step', 'float', default=5.0, minimum=0.1, maximum=50.0,
        section='Choosing the best method',
        help='How far the requirement above is lowered at each step, in percentage points. Kept for\n'
             'settings files that set it; the stability analysis lowers in fixed steps of 5.'),

    _setting(
        'delete_tmp_corrected_data', 'bool', default=True, section='What is written out',
        help='Every method writes a corrected copy of every dataset, which for 16 methods is a lot\n'
             'of files. By default only the corrected data of the winning method is kept. Set to No\n'
             'to keep the corrected data of every method, for example to analyse them elsewhere.'),

    _setting(
        'create_out_zip', 'bool', default=False, section='What is written out',
        help='Pack the whole outputs folder into a ZIP archive at the end of the run.'),

    _setting(
        'runtime_log', 'path', default='bernard-runtimes.xlsx', section='What is written out',
        help='A table of how long everything took, which GROWS across runs: every run adds one\n'
             'row for every dataset it processed, holding the size of that dataset (samples,\n'
             'features, megabytes) and the time of each step (cleaning, every correction method,\n'
             'the choice of the winner, the report, and the run as a whole). Unlike everything\n'
             'else BERNARD writes, it is NOT emptied at the start of a run and it lives outside\n'
             'the outputs folder, so timings from different datasets and different machines\n'
             'accumulate in one place and can be compared. The path may be absolute or relative\n'
             'to the work folder, and the default puts it next to this settings file.\n'
             'Write "none" to switch the timing table off.\n'
             'A correction method corrects every dataset of a run in one program, so its time is\n'
             'measured once per RUN: with several datasets in a run the same number is written\n'
             'into each of their rows, and the "datasets in run" column says so. Run one dataset\n'
             'at a time when the timings themselves are what is being measured.'),
]


SETTINGS_BY_NAME = {setting.name.lower(): setting for setting in SETTINGS}


ERROR = 'ERROR'
WARNING = 'WARNING'

Problem = namedtuple('Problem', ['level', 'where', 'message', 'hint'])


def problem(level, where, message, hint=None):
    return Problem(level, where, message, hint)


TRUE_WORDS = ('yes', 'y', 'true', 't', 'on', '1')
FALSE_WORDS = ('no', 'n', 'false', 'f', 'off', '0')


def _split_list(value):
    if value is None:
        return []

    return [item for item in value.replace(',', ' ').split() if item != '']


def _flatten_blocks(lines):
    out = [line.rstrip('\n') for line in lines]
    index = 0

    while index < len(out):
        line = out[index]
        name, separator, value = line.partition('=')
        setting = SETTINGS_BY_NAME.get(name.strip().lower())

        opens_a_block = (separator == '='
                         and not line[:1].isspace()
                         and value.strip() == ''
                         and setting is not None
                         and setting.kind == 'list')

        if not opens_a_block:
            index = index + 1
            continue

        items = []
        following = index + 1

        while following < len(out):
            item_line = out[following]
            item = item_line.strip()

            if item == '':
                break

            if item.startswith('#'):
                following = following + 1
                continue

            if '=' in item:
                break

            items.append(item)
            out[following] = '#' + item_line
            following = following + 1

        if following == index + 1:
            index = index + 1
            continue

        out[index] = name.strip() + ' = ' + (', '.join(items) if items else 'none')
        index = following

    return [line + '\n' for line in out]


def _read_one(setting, raw, problems):
    where = 'setting ' + setting.name

    if raw is None or str(raw).strip() == '':
        problems.append(problem(
            ERROR, where,
            'is written in the settings file but has no value after the "=".',
            'Either give it a value or delete the line, in which case the default is used'
            + ('' if setting.default is None else ' (' + str(setting.default) + ')') + '.'))
        return setting.default

    raw = str(raw).strip()

    if setting.kind in ('string', 'path'):
        return raw

    if setting.kind == 'list':
        return raw

    if setting.kind == 'bool':
        if raw.lower() in TRUE_WORDS:
            return True
        if raw.lower() in FALSE_WORDS:
            return False
        problems.append(problem(
            ERROR, where, 'is "' + raw + '", which is neither Yes nor No.',
            'Write Yes or No (True and False are also accepted).'))
        return setting.default

    if setting.kind == 'choice':
        for choice in setting.choices:
            if raw.lower() == choice.lower():
                return choice
        suggestion = difflib.get_close_matches(raw.lower(),
                                               [choice.lower() for choice in setting.choices], 1, 0.5)
        problems.append(problem(
            ERROR, where, 'is "' + raw + '", which is not one of the values it accepts.',
            'Accepted values: ' + ', '.join(setting.choices) + '.'
            + ('  Did you mean "' + suggestion[0] + '"?' if suggestion else '')))
        return setting.default

    if setting.kind in ('int', 'float'):
        try:
            value = int(raw) if setting.kind == 'int' else float(raw)
        except ValueError:
            problems.append(problem(
                ERROR, where,
                'is "' + raw + '", which is not '
                + ('a whole number.' if setting.kind == 'int' else 'a number.'),
                'Example: ' + setting.name + ' = ' + str(setting.default)))
            return setting.default

        if setting.minimum is not None and value < setting.minimum:
            problems.append(problem(
                ERROR, where, 'is ' + raw + ', which is below the smallest accepted value '
                + str(setting.minimum) + '.',
                setting.help.splitlines()[0] if setting.help else None))
            return setting.default

        if setting.maximum is not None and value > setting.maximum:
            problems.append(problem(
                ERROR, where, 'is ' + raw + ', which is above the largest accepted value '
                + str(setting.maximum) + '.',
                setting.help.splitlines()[0] if setting.help else None))
            return setting.default

        return value

    return raw


def _unknown_settings(written_names, problems):
    known = list(SETTINGS_BY_NAME.keys())

    for name in written_names:
        if name.lower() in SETTINGS_BY_NAME:
            continue

        close = difflib.get_close_matches(name.lower(), known, 1, 0.6)
        problems.append(problem(
            ERROR, 'setting ' + name, 'is not a setting BERNARD knows about.',
            ('Did you mean "' + close[0] + '"?' if close
             else 'Run BERNARD with --template to see every setting that exists.')))


def _cross_checks(values, problems):
    retention = values.get('diagnosis_variability_retention')
    lower_limit = values.get('diagnosis_variability_lower_limit')

    if retention is not None and lower_limit is not None and lower_limit > retention:
        problems.append(problem(
            ERROR, 'settings diagnosis_variability_retention / diagnosis_variability_lower_limit',
            'the lower limit (' + str(lower_limit) + ') is above the requirement itself ('
            + str(retention) + ').',
            'The requirement is lowered towards the lower limit when no method meets it, so the '
            'lower limit has to be the smaller of the two.'))

    if values.get('select_thresholdSamples') == 0 and values.get('select_thresholdFeatures') == 0:
        problems.append(problem(
            WARNING, 'settings select_thresholdSamples / select_thresholdFeatures',
            'both are 0, which removes every sample and every feature that holds a single zero.',
            'The usual value is 0.9. Values near 0 are only meaningful on data with no zeros at all.'))

    if not values.get('run_permdisp'):
        for unused in ('permdisp_permutations', 'permdisp_test'):
            if values.get(unused) is not None and unused in values.get('_written', ()):
                problems.append(problem(
                    WARNING, 'setting ' + unused,
                    'is set, but run_permdisp is No, so PERMDISP is not calculated and the value '
                    'is unused.'))


def read(cfg_file):
    problems = []

    if cfg_file is None or str(cfg_file).strip() == '':
        problems.append(problem(ERROR, 'command line', 'no settings file was given.',
                                'Usage: BERNARD.py <settings file> [<work folder>]'))
        return {}, problems

    if not os.path.exists(cfg_file):
        problems.append(problem(ERROR, 'settings file', 'the file "' + cfg_file + '" does not exist.',
                                'Run BERNARD.py --template > bernard_cfg.txt to write a new one.'))
        return {}, problems

    if os.path.isdir(cfg_file):
        problems.append(problem(ERROR, 'settings file', '"' + cfg_file + '" is a folder, not a file.',
                                'The first argument is the settings file, the second is the folder '
                                'with the data.'))
        return {}, problems

    try:
        with io.open(cfg_file, 'r', encoding='utf-8', errors='replace') as handle:
            cfg_lines = handle.readlines()
    except Exception as failure:
        problems.append(problem(ERROR, 'settings file',
                                'the file could not be read: ' + str(failure)))
        return {}, problems

    try:
        parse_status = params.read_file(_flatten_blocks(cfg_lines), False)
        params.paramsglb_file = cfg_file
    except SystemExit:
        problems.append(problem(ERROR, 'settings file',
                                'the file could not be read as a settings file.',
                                'Each line has to be either empty, a comment starting with #, or '
                                'of the form   name = value'))
        return {}, problems
    except Exception as failure:
        problems.append(problem(ERROR, 'settings file',
                                'the file could not be read: ' + str(failure)))
        return {}, problems

    for parse_error in parse_status[1]:
        problems.append(problem(ERROR, 'settings file', str(parse_error)))

    try:
        written_names = list(params.paramsglb.options('generic'))
    except Exception:
        written_names = []

    _unknown_settings(written_names, problems)

    values = {}
    for setting in SETTINGS:
        if params.param_exists(setting.name):
            values[setting.name] = _read_one(setting, params.opt_string(setting.name), problems)
        else:
            values[setting.name] = setting.default

    values['_written'] = {name.lower() for name in written_names}

    if values.get('bernard_input') is None:
        problems.append(problem(
            ERROR, 'setting bernard_input', 'is missing, and it is the one setting that is required.',
            'Write the folder holding the data, for example\n'
            '    bernard_input = /home/anna/my_study\n'
            'That folder has to contain a raw-data subfolder.'))

    _cross_checks(values, problems)

    return values, problems


def method_list(values, name):
    return _split_list(values.get(name))


def column_list(values, name):
    items = _split_list(values.get(name))

    if len(items) == 1 and items[0].lower() in ('none', 'empty', '-'):
        return []

    return items


def template():
    import methods as bmethods

    lines = []
    lines.append('# ' + '=' * 95)
    lines.append('# BERNARD settings file')
    lines.append('#')
    lines.append('# Every line is either empty, a comment starting with #, or   name = value')
    lines.append('# A list may also be written one item per line, indented, and then a # in front of')
    lines.append('# an item leaves that item out. That is how the correction methods are chosen.')
    lines.append('# A setting that is commented out uses the default shown next to it, so the shortest')
    lines.append('# working settings file is a single line: bernard_input = /path/to/my/data')
    lines.append('#')
    lines.append('# Run   python3 BERNARD.py --check this_file.txt   to have the file and the data it')
    lines.append('# points at checked from top to bottom, without starting a calculation.')
    lines.append('# ' + '=' * 95)

    printed_sections = set()

    for setting in SETTINGS:
        if setting.section not in printed_sections:
            printed_sections.add(setting.section)
            lines.append('')
            lines.append('')
            lines.append('# ' + '-' * 95)
            lines.append('# ' + setting.section.upper())
            lines.append('# ' + '-' * 95)

        lines.append('')
        for help_line in setting.help.splitlines():
            lines.append('# ' + help_line if help_line else '#')

        if setting.choices:
            lines.append('# Accepted values: ' + ', '.join(setting.choices))
        if setting.minimum is not None or setting.maximum is not None:
            lines.append('# Range: '
                         + ('no lower limit' if setting.minimum is None else str(setting.minimum))
                         + ' to '
                         + ('no upper limit' if setting.maximum is None else str(setting.maximum)))

        if setting.name == 'bernard_input':
            lines.append('bernard_input = /path/to/my/data')
        elif setting.name == 'correction_methods':
            lines.append('correction_methods =')
            for method_name in bmethods.available_methods():
                lines.append('    ' + method_name)
        elif setting.default is None:
            lines.append('#' + setting.name + ' =')
        elif isinstance(setting.default, bool):
            lines.append('#' + setting.name + ' = ' + ('yes' if setting.default else 'no')
                         + '        # default')
        else:
            lines.append('#' + setting.name + ' = ' + str(setting.default) + '        # default')

    lines.append('')

    return '\n'.join(lines) + '\n'
