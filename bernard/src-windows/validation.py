
import difflib
import json
import os
import shutil
import sys
from collections import namedtuple

from settings import ERROR, WARNING, Problem, problem


NON_DATASET_FILES = ('metadata', 'config', 'covariates', 'tag')

DATASET_EXTENSIONS = ('.csv', '.tsv')

FEW_SAMPLES = 20
TOO_FEW_SAMPLES = 5


def has_errors(problems):
    return any(entry.level == ERROR for entry in problems)


def _wrap(text, width, indent):
    words = str(text).split()
    lines = []
    current = ''

    for word in words:
        if current == '':
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = current + ' ' + word
        else:
            lines.append(current)
            current = word

    if current != '':
        lines.append(current)

    return ('\n' + indent).join(lines) if lines else ''


def report(problems, headline='Problems found with this run'):
    if not problems:
        return

    errors = [entry for entry in problems if entry.level == ERROR]
    warnings = [entry for entry in problems if entry.level == WARNING]

    print('')
    print('=' * 99)
    print(headline + ':  ' + str(len(errors)) + ' error(s), ' + str(len(warnings)) + ' warning(s)')
    print('=' * 99)

    for entry in errors + warnings:
        print('')
        print(entry.level + '  in ' + entry.where)
        print('    ' + _wrap(entry.message, 90, '    '))
        if entry.hint:
            for hint_line in str(entry.hint).splitlines():
                print('    -> ' + _wrap(hint_line, 86, '       '))

    print('')
    print('=' * 99)


def _did_you_mean(name, candidates):
    candidates = [str(candidate) for candidate in candidates]
    close = difflib.get_close_matches(str(name), candidates, 3, 0.6)

    if close:
        return 'The closest column name(s) in the file: ' + ', '.join('"' + c + '"' for c in close)

    shown = candidates[:8]
    return ('The columns in the file are: ' + ', '.join('"' + c + '"' for c in shown)
            + (' ... and ' + str(len(candidates) - len(shown)) + ' more' if len(candidates) > len(shown) else ''))


def check_layout(bernard_folder, problems):
    if bernard_folder is None:
        return None

    if not os.path.exists(bernard_folder):
        problems.append(problem(
            ERROR, 'setting bernard_input',
            'the folder "' + bernard_folder + '" does not exist.',
            'Check the path for a typo. A path that does not start with / is taken relative to '
            'the work folder given as the second argument on the command line.'))
        return None

    if not os.path.isdir(bernard_folder):
        problems.append(problem(
            ERROR, 'setting bernard_input',
            '"' + bernard_folder + '" is a file, not a folder.',
            'Give either a folder holding a raw-data subfolder, or a .zip archive of one.'))
        return None

    raw_data_folder = os.path.join(bernard_folder, 'raw-data')

    if not os.path.isdir(raw_data_folder):
        looks_like_data = [name for name in _safe_listdir(bernard_folder)
                           if name.lower().endswith(DATASET_EXTENSIONS)]
        problems.append(problem(
            ERROR, 'input folder',
            'there is no raw-data subfolder inside "' + bernard_folder + '".',
            'BERNARD expects   ' + bernard_folder + '/raw-data/   holding metadata.csv, '
            'config.json, covariates.txt and the dataset files.'
            + ('\nThis folder does hold data files (' + ', '.join(looks_like_data[:3])
               + '); they most likely belong in a raw-data subfolder.' if looks_like_data else '')))
        return None

    if not os.access(raw_data_folder, os.R_OK):
        problems.append(problem(ERROR, 'input folder',
                                'the raw-data folder cannot be read (no permission).'))
        return None

    try:
        parent_writable = os.access(bernard_folder, os.W_OK)
    except Exception:
        parent_writable = True

    if not parent_writable:
        problems.append(problem(
            ERROR, 'input folder',
            'the folder "' + bernard_folder + '" cannot be written to.',
            'BERNARD writes its results into an outputs subfolder next to raw-data.'))

    return raw_data_folder


def _safe_listdir(folder):
    try:
        return sorted(os.listdir(folder))
    except Exception:
        return []


def read_columns_definition(raw_data_folder, values, problems):
    import settings as bsettings

    from_config = {}
    config_path = os.path.join(raw_data_folder, 'config.json') if raw_data_folder else None

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as config_file:
                loaded = json.load(config_file)
            if isinstance(loaded, dict):
                from_config = {key: str(value) for key, value in loaded.items()
                               if value is not None}
            else:
                problems.append(problem(
                    ERROR, 'raw-data/config.json',
                    'the file does not hold a set of name/value pairs.',
                    'It has to look like:\n'
                    '    {"study_name": "bioproject", "factor_of_interest": "diagnosis", '
                    '"sample_id_column": "run"}'))
        except json.JSONDecodeError as failure:
            problems.append(problem(
                ERROR, 'raw-data/config.json',
                'the file is not valid JSON: ' + failure.msg + ' (line ' + str(failure.lineno)
                + ', column ' + str(failure.colno) + ').',
                'The usual causes are a missing comma, a missing quotation mark, or a comma after '
                'the last entry. It has to look like:\n'
                '    {"study_name": "bioproject", "factor_of_interest": "diagnosis", '
                '"sample_id_column": "run"}'))
        except Exception as failure:
            problems.append(problem(ERROR, 'raw-data/config.json',
                                    'the file could not be read: ' + str(failure)))

    definition = {}
    for key in ('study_name', 'factor_of_interest', 'sample_id_column'):
        chosen = values.get(key) or from_config.get(key)

        if chosen is None or str(chosen).strip() == '':
            problems.append(problem(
                ERROR, 'column definitions',
                '"' + key + '" is not defined anywhere.',
                'Write it in the settings file:\n    ' + key + ' = the_column_name\n'
                'or in raw-data/config.json.'))
            chosen = None
        else:
            chosen = str(chosen).strip()

        definition[key] = chosen

    if definition['sample_id_column'] == 'Unnamed: 0':
        problems.append(problem(
            ERROR, 'column definitions',
            '"Unnamed: 0" cannot be used as the name of the sample ID column.',
            'That name is what pandas invents for a column that has no name at all. Give the '
            'first column of metadata.csv a real name and use that.'))

    named = [name for name in definition.values() if name]
    for name in set(named):
        if named.count(name) > 1:
            problems.append(problem(
                ERROR, 'column definitions',
                'the column "' + name + '" is used for more than one purpose.',
                'sample_id_column, study_name and factor_of_interest have to be three different '
                'columns.'))

    covariates = None

    if 'covariates' in values.get('_written', ()):
        covariates = bsettings.column_list(values, 'covariates')
    else:
        covariates_path = os.path.join(raw_data_folder, 'covariates.txt') if raw_data_folder else None
        if covariates_path and os.path.exists(covariates_path):
            try:
                with open(covariates_path, 'r') as covariate_file:
                    covariates = [line.strip() for line in covariate_file if line.strip() != '']
            except Exception as failure:
                problems.append(problem(ERROR, 'raw-data/covariates.txt',
                                        'the file could not be read: ' + str(failure)))
                covariates = []
        else:
            covariates = []
            problems.append(problem(
                WARNING, 'raw-data/covariates.txt',
                'there is no covariates.txt and no covariates setting, so no extra metadata '
                'columns are reported.',
                'This is fine if the metadata holds nothing beyond the batch and the factor of '
                'interest. Otherwise list them:\n    covariates = age, sex, country'))

    deduplicated = []
    for name in covariates:
        if name in (definition['study_name'], definition['factor_of_interest'],
                    definition['sample_id_column']):
            problems.append(problem(
                WARNING, 'covariates',
                'the column "' + name + '" is listed as a covariate although it is already used '
                'as the batch, the factor of interest or the sample ID.',
                'It is removed from the covariates; the results are unaffected.'))
            continue
        if name in deduplicated:
            problems.append(problem(WARNING, 'covariates',
                                    'the column "' + name + '" is listed more than once.'))
            continue
        deduplicated.append(name)

    definition['covariates'] = deduplicated

    return definition


def write_columns_definition(raw_data_folder, definition, values=None):
    config_path = os.path.join(raw_data_folder, 'config.json')
    covariates_path = os.path.join(raw_data_folder, 'covariates.txt')

    contents = {'study_name': definition['study_name'],
                'factor_of_interest': definition['factor_of_interest'],
                'sample_id_column': definition['sample_id_column']}

    if values:
        contents['random_seed'] = int(values.get('random_seed') or 42)

    try:
        with open(config_path, 'w') as config_file:
            json.dump(contents, config_file, indent=4)
    except Exception as failure:
        return 'raw-data/config.json could not be written: ' + str(failure)

    try:
        with open(covariates_path, 'w') as covariate_file:
            covariate_file.write('\n'.join(definition['covariates']))
            if definition['covariates']:
                covariate_file.write('\n')
    except Exception as failure:
        return 'raw-data/covariates.txt could not be written: ' + str(failure)

    return None


MISSING_VALUES = frozenset(['', 'na', 'n/a', 'nan', 'null', 'none', '-'])


def _is_missing(value):
    return value is None or str(value).strip().lower() in MISSING_VALUES


def _separator(path):
    return '\t' if path.lower().endswith('.tsv') else ','


def _read_header(path):
    import csv
    import sys

    csv.field_size_limit(sys.maxsize)

    try:
        with open(path, newline='') as table:
            for row in csv.reader(table, delimiter=_separator(path)):
                return [name.strip() for name in row], None
        return [], 'the file is empty.'
    except UnicodeDecodeError:
        return None, ('the file is not text in a readable encoding. A spreadsheet saved as .xlsx '
                      'and renamed to .csv is the usual cause; export it as CSV instead.')
    except Exception as failure:
        return None, str(failure)


def _read_columns(path, wanted):
    import csv
    import sys

    csv.field_size_limit(sys.maxsize)

    try:
        with open(path, newline='') as table:
            reader = csv.reader(table, delimiter=_separator(path))

            try:
                header = [name.strip() for name in next(reader)]
            except StopIteration:
                return {}, 0, 'the file is empty.'

            positions = {name: header.index(name) for name in wanted if name in header}
            values = {name: [] for name in positions}
            row_count = 0

            for row in reader:
                if len(row) == 0:
                    continue
                row_count = row_count + 1
                for name, position in positions.items():
                    values[name].append(row[position] if position < len(row) else None)

            return values, row_count, None

    except UnicodeDecodeError:
        return None, 0, ('the file is not text in a readable encoding. A spreadsheet saved as '
                         '.xlsx and renamed to .csv is the usual cause; export it as CSV instead.')
    except Exception as failure:
        return None, 0, str(failure)


def _counts(values):
    from collections import Counter

    return Counter(str(value).strip() for value in values if not _is_missing(value))


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return float('inf')


def dataset_files(raw_data_folder, values, problems):
    import settings as bsettings

    wanted = bsettings.column_list(values, 'datasets')
    found = []

    for name in _safe_listdir(raw_data_folder):
        if name.startswith('.'):
            continue
        if os.path.isdir(os.path.join(raw_data_folder, name)):
            continue
        lowered = name.lower()
        if any(marker in lowered for marker in NON_DATASET_FILES):
            continue

        if not lowered.endswith(DATASET_EXTENSIONS):
            problems.append(problem(
                WARNING, 'raw-data folder',
                'the file "' + name + '" is not a .csv or .tsv file and is not analysed.',
                'Everything in raw-data that is not metadata.csv, config.json or covariates.txt is '
                'treated as a dataset. Move this file elsewhere, or name the files to analyse with '
                'the "datasets" setting.'))
            continue

        found.append(name)

    found.sort(key=lambda name: (_file_size(os.path.join(raw_data_folder, name)), name))

    if wanted:
        missing = [name for name in wanted if name not in found]
        for name in missing:
            problems.append(problem(
                ERROR, 'setting datasets',
                'the file "' + name + '" is not in the raw-data folder.',
                'The files that are: ' + (', '.join(found) if found else '(none)')))
        found = [name for name in found if name in wanted]

    if not found:
        problems.append(problem(
            ERROR, 'raw-data folder',
            'there is no dataset file to analyse in "' + raw_data_folder + '".',
            'Next to metadata.csv, config.json and covariates.txt there has to be at least one '
            '.csv or .tsv file holding the measurements, one row per sample.'))

    return found


def check_metadata(raw_data_folder, definition, problems):
    path = os.path.join(raw_data_folder, 'metadata.csv')

    if not os.path.exists(path):
        problems.append(problem(
            ERROR, 'raw-data/metadata.csv',
            'the file does not exist.',
            'It holds one row per sample with the batch, the factor of interest and any extra '
            'metadata columns, and is what every measurement is grouped by.'))
        return None

    if os.path.getsize(path) == 0:
        problems.append(problem(ERROR, 'raw-data/metadata.csv', 'the file is empty.'))
        return None

    columns, failure = _read_header(path)

    if columns is None:
        problems.append(problem(ERROR, 'raw-data/metadata.csv',
                                'the file could not be read: ' + str(failure)))
        return None

    declared = [definition['sample_id_column'], definition['study_name'],
                definition['factor_of_interest']]

    for name in declared:
        if name and name not in columns:
            problems.append(problem(
                ERROR, 'raw-data/metadata.csv',
                'the column "' + name + '" is declared but the file does not have it.',
                _did_you_mean(name, columns)))

    for name in definition['covariates']:
        if name not in columns:
            problems.append(problem(
                ERROR, 'raw-data/metadata.csv',
                'the covariate column "' + name + '" is not in the file.',
                _did_you_mean(name, columns)))

    sample_id_column = definition['sample_id_column']

    if not sample_id_column or sample_id_column not in columns:
        return None

    values, row_count, failure = _read_columns(path, [sample_id_column])

    if values is None:
        problems.append(problem(ERROR, 'raw-data/metadata.csv',
                                'the file could not be read: ' + str(failure)))
        return None

    if row_count == 0:
        problems.append(problem(ERROR, 'raw-data/metadata.csv',
                                'the file holds column names but not a single sample.'))
        return None

    identifiers = values[sample_id_column]
    counted = _counts(identifiers)

    repeated = [value for value, count in counted.items() if count > 1]
    if repeated:
        problems.append(problem(
            ERROR, 'raw-data/metadata.csv',
            'the sample ID column "' + sample_id_column + '" holds '
            + str(len(repeated)) + ' repeated value(s), for example '
            + ', '.join(str(value) for value in repeated[:3]) + '.',
            'Every row has to describe a different sample: a repeated ID multiplies the rows when '
            'the metadata is joined to the measurements.'))

    empty = sum(1 for value in identifiers if _is_missing(value))
    if empty:
        problems.append(problem(
            WARNING, 'raw-data/metadata.csv',
            str(empty) + ' row(s) have no sample ID and are dropped.'))

    return set(counted.keys())


def check_dataset(raw_data_folder, name, definition, metadata_identifiers, problems):
    path = os.path.join(raw_data_folder, name)
    where = 'dataset ' + name

    try:
        if os.path.getsize(path) == 0:
            problems.append(problem(ERROR, where, 'the file is empty.'))
            return
    except OSError as failure:
        problems.append(problem(ERROR, where, 'the file cannot be read: ' + str(failure)))
        return

    columns, failure = _read_header(path)

    if columns is None:
        problems.append(problem(
            ERROR, where, 'the file could not be read: ' + str(failure),
            'It has to be a plain text table, comma separated for .csv and tab separated for .tsv, '
            'with the column names in the first line.'))
        return

    if len(columns) < 2:
        problems.append(problem(
            ERROR, where,
            'only one column was found, so the separator is probably not the expected one.',
            'A .csv file has to be comma separated and a .tsv file tab separated. The first line '
            'reads: ' + (str(columns[0])[:70] if columns else '(empty)')))
        return

    seen = set()
    duplicated_columns = []
    for column in columns:
        if column in seen and column not in duplicated_columns:
            duplicated_columns.append(column)
        seen.add(column)

    if duplicated_columns:
        problems.append(problem(
            WARNING, where,
            'the column name(s) ' + ', '.join(str(c) for c in duplicated_columns[:5])
            + ' appear more than once; only the first of each is used when the columns are read '
              'by name.'))

    sample_id_column = definition['sample_id_column']
    study_name = definition['study_name']
    factor_of_interest = definition['factor_of_interest']

    required = [column for column in (sample_id_column, study_name, factor_of_interest) if column]
    missing = [column for column in required if column not in columns]

    unnamed_index = 'Unnamed: 0' in columns or (len(columns) > 0 and columns[0] == '')

    for column in missing:
        if column == sample_id_column and unnamed_index:
            continue
        problems.append(problem(
            ERROR, where,
            'the column "' + column + '" is declared but the file does not have it.',
            _did_you_mean(column, columns)))

    if [column for column in missing if not (column == sample_id_column and unnamed_index)]:
        return

    wanted = [column for column in required if column in columns]
    values, samples, failure = _read_columns(path, wanted)

    if values is None:
        problems.append(problem(WARNING, where,
                                'the declared columns could not be read for checking: '
                                + str(failure)))
        return

    features = len(columns) - len(wanted) - (1 if unnamed_index else 0)

    if samples < TOO_FEW_SAMPLES:
        problems.append(problem(
            ERROR, where,
            'the file holds only ' + str(samples) + ' sample(s), which is too few for any of the '
            'measurements BERNARD makes.',
            'PERMANOVA, the silhouette width and the nearest neighbour measures all need groups '
            'with several samples in them.'))
        return

    if samples < FEW_SAMPLES:
        problems.append(problem(
            WARNING, where,
            'the file holds only ' + str(samples) + ' samples. The measurements are calculated but '
            'their p-values and R2 values are unstable at this size.'))

    if features <= 0:
        problems.append(problem(
            ERROR, where,
            'apart from the metadata columns there are no feature columns, so there is nothing to '
            'correct.',
            'The dataset file holds the measurements: one row per sample, one column per feature '
            '(bacterium, gene), plus the sample ID, the batch and the factor of interest.'))
        return

    if study_name in values:
        batch_counts = _counts(values[study_name])

        if len(batch_counts) < 2:
            only = list(batch_counts)[0] if batch_counts else None
            problems.append(problem(
                ERROR, where,
                'the batch column "' + study_name + '" has '
                + ('only one value (' + str(only) + ')' if only is not None
                   else 'no values at all') + '.',
                'With a single batch there is no batch effect to remove and nothing to compare. '
                'Check that study_name names the column holding the study, run or laboratory.'))
        else:
            tiny = [(value, count) for value, count in batch_counts.items() if count < 3]
            if tiny:
                problems.append(problem(
                    WARNING, where,
                    str(len(tiny)) + ' batch(es) hold fewer than 3 samples ('
                    + ', '.join(str(value) + ': ' + str(count) for value, count in tiny[:3]) + ').',
                    'Several correction methods estimate a mean and a spread per batch, which a '
                    'batch of one or two samples cannot support.'))

    if factor_of_interest in values:
        factor_counts = _counts(values[factor_of_interest])

        if len(factor_counts) < 2:
            only = list(factor_counts)[0] if factor_counts else None
            problems.append(problem(
                ERROR, where,
                'the factor of interest "' + factor_of_interest + '" has '
                + ('only one value (' + str(only) + ')' if only is not None
                   else 'no values at all') + '.',
                'BERNARD chooses the best method by how much of the variability explained by this '
                'column survives the correction, which needs at least two groups to compare.'))
        elif len(factor_counts) > max(2, samples // 4):
            problems.append(problem(
                WARNING, where,
                'the factor of interest "' + factor_of_interest + '" has '
                + str(len(factor_counts)) + ' different values over ' + str(samples) + ' samples.',
                'It looks like a continuous measurement or a free text field rather than a group. '
                'The measurements treat it as a set of groups, one per distinct value.'))

    if study_name in values and factor_of_interest in values:
        try:
            per_batch = {}
            for batch, factor in zip(values[study_name], values[factor_of_interest]):
                if _is_missing(batch) or _is_missing(factor):
                    continue
                per_batch.setdefault(str(batch).strip(), set()).add(str(factor).strip())

            if len(per_batch) > 1 and all(len(found) <= 1 for found in per_batch.values()):
                problems.append(problem(
                    WARNING, where,
                    'every batch holds only one value of "' + factor_of_interest + '": the batch '
                    'and the biology are completely confounded.',
                    'No correction method can tell them apart, because removing the batch '
                    'difference necessarily removes the biological difference with it. The results '
                    'of this dataset cannot be interpreted as a batch effect correction.'))
        except Exception:
            pass

    if metadata_identifiers is not None and sample_id_column in values:
        counted = _counts(values[sample_id_column])
        identifiers = set(counted.keys())
        shared = identifiers & metadata_identifiers

        if not shared:
            problems.append(problem(
                ERROR, where,
                'not one of the ' + str(len(identifiers)) + ' sample IDs appears in metadata.csv.',
                'The two files are joined on "' + sample_id_column + '", so the IDs have to be '
                'written the same way in both. Examples from this file: '
                + ', '.join(sorted(identifiers)[:3])))
        elif len(shared) < len(identifiers) * 0.5:
            problems.append(problem(
                WARNING, where,
                'only ' + str(len(shared)) + ' of ' + str(len(identifiers)) + ' sample IDs appear '
                'in metadata.csv; the rest are dropped.',
                'Check for a difference in how the IDs are written (extra spaces, a prefix, upper '
                'and lower case).'))

        repeated = sum(count - 1 for count in counted.values() if count > 1)
        if repeated:
            problems.append(problem(
                WARNING, where,
                str(repeated) + ' sample ID(s) appear more than once in the file.',
                'Repeated IDs become repeated rows after the join with the metadata.'))


def check_r_available(selected_methods, problems):
    r_methods = [method.label for method in selected_methods if method.script is not None]

    if not r_methods:
        return

    if shutil.which('Rscript') is None:
        problems.append(problem(
            ERROR, 'R installation',
            'Rscript was not found, and ' + str(len(r_methods)) + ' of the selected correction '
            'methods are R scripts (' + ', '.join(r_methods[:4])
            + ('...' if len(r_methods) > 4 else '') + ').',
            'Either install R and the packages listed in requirements/RPackages.R, or run only the '
            'methods that do not need it:\n    correction_methods = pyCombat'))


def check_scripts_present(script_folder, selected_methods, problems):
    for method in selected_methods:
        if method.script is None:
            continue
        if not os.path.exists(os.path.join(script_folder, method.script)):
            problems.append(problem(
                ERROR, 'correction method ' + method.label,
                'its script "' + method.script + '" is missing from ' + script_folder + '.',
                'Exclude the method with\n    exclude_correction_methods = ' + method.name))


IMPORT_NAMES = {'scikit-bio': 'skbio', 'scikit-learn': 'sklearn'}

Combination = namedtuple('Combination', ['level', 'package', 'package_at_least', 'package_below',
                                         'needs', 'needs_at_least', 'needs_below',
                                         'used_by', 'because', 'symptom'])


def _combination(level, package, needs, package_at_least=None, package_below=None,
                 needs_at_least=None, needs_below=None, used_by=None, because='', symptom=None):
    return Combination(level, package, package_at_least, package_below,
                       needs, needs_at_least, needs_below, used_by, because, symptom)


COMBINATIONS = (
    _combination(
        ERROR, 'inmoose', 'numpy', package_at_least=(0, 9), needs_at_least=(2, 0),
        used_by='pyCombat',
        because='inmoose 0.9 and newer use numpy.dtypes.StringDType, which numpy has from '
                'version 2.0 onwards',
        symptom="AttributeError: module 'numpy.dtypes' has no attribute 'StringDType'"),
    _combination(
        WARNING, 'inmoose', 'numpy', package_below=(0, 9), needs_below=(2, 1),
        used_by='pyCombat',
        because='inmoose below 0.9 is built against numpy 1.x and asks for numpy < 2.1'),
)


def _version_numbers(text):
    numbers = []
    for part in str(text).split('.'):
        digits = ''
        for character in part:
            if not character.isdigit():
                break
            digits = digits + character
        if digits == '':
            break
        numbers.append(int(digits))
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers[:3])


def _version_family(text):
    numbers = _version_numbers(text)
    return numbers[:2] if numbers[0] == 0 else numbers[:1]


def _at_least(version, bound):
    if bound is None:
        return True
    return _version_numbers(version) >= _version_numbers('.'.join(str(part) for part in bound))


def _below(version, bound):
    if bound is None:
        return True
    return _version_numbers(version) < _version_numbers('.'.join(str(part) for part in bound))


def _in_range(version, at_least, below):
    return _at_least(version, at_least) and _below(version, below)


def _range_in_words(at_least, below):
    lower = '.'.join(str(part) for part in at_least) + ' or newer' if at_least else ''
    upper = 'below ' + '.'.join(str(part) for part in below) if below else ''
    return (lower + ' but ' + upper) if lower and upper else (lower or upper or 'any version')


def _installed_version(distribution):
    from importlib import metadata
    try:
        return metadata.version(distribution)
    except Exception:
        return None


def _imported_from(distribution):
    module_name = IMPORT_NAMES.get(distribution, distribution.replace('-', '_'))
    module = sys.modules.get(module_name)

    if module is not None and getattr(module, '__file__', None):
        return os.path.dirname(module.__file__)

    try:
        import importlib.util
        found = importlib.util.find_spec(module_name)
        if found is None:
            return None
        if found.origin and found.origin not in ('built-in', 'frozen'):
            return os.path.dirname(found.origin)
        if found.submodule_search_locations:
            return list(found.submodule_search_locations)[0]
    except Exception:
        return None
    return None


def _requirements_file():
    if sys.platform.startswith('win'):
        name = 'requirements-windows.txt'
    elif sys.platform == 'darwin':
        name = 'requirements-macOS.txt'
    else:
        name = 'requirements-linux.txt'

    folder = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        candidate = os.path.join(folder, 'requirements', name)
        if os.path.exists(candidate):
            return candidate, name
        folder = os.path.dirname(folder)
    return None, name


def _pinned_versions(path):
    pinned = {}
    with open(path, 'r', encoding='utf-8', errors='replace') as requirements:
        for line in requirements:
            line = line.split('#')[0].strip()
            if '==' not in line:
                continue
            name, _, version = line.partition('==')
            name = name.split('[')[0].strip()
            version = version.split(';')[0].strip()
            if name and version:
                pinned[name] = version
    return pinned


def _install_lines(install_command):
    activate = ('    bernardEnv\\Scripts\\activate' if sys.platform.startswith('win')
                else '    source bernardEnv/bin/activate')
    return ['Install the tested set of packages in a virtual environment of its own, so that it is '
            'not mixed with the packages of the operating system:',
            '    python3 -m venv bernardEnv',
            activate,
            '    ' + install_command]


def check_python_packages(selected_methods, problems):
    path, name = _requirements_file()
    pinned = _pinned_versions(path) if path else {}
    install_command = 'pip install -r ' + (path if path else 'requirements/' + name)

    looked_at = set(pinned)
    for rule in COMBINATIONS:
        looked_at.update((rule.package, rule.needs))
    installed = {distribution: _installed_version(distribution) for distribution in looked_at}

    missing = [distribution for distribution in sorted(pinned)
               if installed[distribution] is None and _imported_from(distribution) is None]
    if missing:
        problems.append(problem(
            ERROR, 'Python packages',
            str(len(missing)) + ' of the packages BERNARD imports are not installed: '
            + ', '.join(missing) + '.',
            '\n'.join(_install_lines(install_command))))

    selected = None if selected_methods is None else {method.name for method in selected_methods}
    for rule in COMBINATIONS:
        if rule.used_by and selected is not None and rule.used_by not in selected:
            continue
        have, other = installed.get(rule.package), installed.get(rule.needs)
        if have is None or other is None:
            continue
        if not _in_range(have, rule.package_at_least, rule.package_below):
            continue
        if _in_range(other, rule.needs_at_least, rule.needs_below):
            continue

        message = (rule.package + ' ' + have + ' needs ' + rule.needs + ' '
                   + _range_in_words(rule.needs_at_least, rule.needs_below) + ', but ' + rule.needs
                   + ' ' + other + ' is installed'
                   + (' (' + rule.because + ')' if rule.because else '') + '.')
        if rule.symptom:
            message = (message + ' ' + (rule.used_by or rule.package) + ' stops with "'
                       + rule.symptom + '", in the middle of the run.')

        hint = []
        for distribution in (rule.package, rule.needs):
            imported_from = _imported_from(distribution)
            if imported_from:
                hint.append(distribution + ' is imported from ' + imported_from)
        hint.extend(_install_lines(install_command))
        if rule.used_by:
            hint.append('Or leave the method that needs it out of the run:')
            hint.append('    exclude_correction_methods = ' + rule.used_by)
        problems.append(problem(rule.level, 'Python packages', message, '\n'.join(hint)))

    differing = []
    for distribution in sorted(pinned):
        have = installed.get(distribution)
        if have is None or _version_family(have) == _version_family(pinned[distribution]):
            continue
        imported_from = _imported_from(distribution)
        differing.append(distribution + ' ' + have + ' installed, ' + pinned[distribution]
                         + ' tested' + ('   (' + imported_from + ')' if imported_from else ''))
    if differing:
        problems.append(problem(
            WARNING, 'Python packages',
            str(len(differing)) + ' of the packages are a whole version away from the ones this '
            'platform was tested with. The run goes ahead, but if something inside one of them '
            'goes wrong later, the version is the first thing to look at.',
            '\n'.join(differing + [install_command])))


def check_input(bernard_folder, values, selected_methods, script_folder):
    problems = []
    definition = {'study_name': None, 'factor_of_interest': None, 'sample_id_column': None,
                  'covariates': []}
    datasets = []

    try:
        check_python_packages(selected_methods, problems)
        check_r_available(selected_methods, problems)
        check_scripts_present(script_folder, selected_methods, problems)

        raw_data_folder = check_layout(bernard_folder, problems)

        if raw_data_folder is None:
            return problems, definition, datasets

        definition = read_columns_definition(raw_data_folder, values, problems)
        datasets = dataset_files(raw_data_folder, values, problems)

        if not definition['sample_id_column']:
            return problems, definition, datasets

        metadata_identifiers = check_metadata(raw_data_folder, definition, problems)

        for name in datasets:
            check_dataset(raw_data_folder, name, definition, metadata_identifiers, problems)

    except Exception as failure:
        import traceback
        problems.append(problem(
            WARNING, 'input checks',
            'the checks of the input data could not be completed: ' + str(failure),
            'The run continues, but the input data has not been fully checked.\n'
            + traceback.format_exc().splitlines()[-1]))

    return problems, definition, datasets
