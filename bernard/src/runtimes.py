
import os

from openpyxl import Workbook, load_workbook


LEADING_COLUMNS = [
    'dataset',
    'run',
    'samples',
    'features',
    'samples after cleaning',
    'features after cleaning',
    'size MB',
    'cleaning s',
    'cleaning with statistics s',
]

TRAILING_COLUMNS = [
    'correction total s',
    'correction and scoring s',
    'method selection s',
    'report s',
    'BERNARD total s',
    'methods at a time',
    'datasets in run',
    'methods run',
]


def file_size_mb(path):
    try:
        return round(os.path.getsize(path) / (1024.0 * 1024.0), 3)
    except Exception:
        return None


def _seconds(value):
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def build_rows(datasets, method_runtimes, shared):
    method_columns = [(label + ' s', _seconds(runtime)) for label, runtime in method_runtimes]

    rows = []
    for dataset in datasets:
        row = {
            'dataset':                    dataset.get('name'),
            'run':                        shared.get('run'),
            'samples':                    dataset.get('samples'),
            'features':                   dataset.get('features'),
            'samples after cleaning':     dataset.get('samples_after'),
            'features after cleaning':    dataset.get('features_after'),
            'size MB':                    dataset.get('size_mb'),
            'cleaning s':                 _seconds(dataset.get('cleaning')),
            'cleaning with statistics s': _seconds(dataset.get('cleaning_with_statistics')),
        }

        for column, value in method_columns:
            row[column] = value

        row.update({
            'correction total s': _seconds(sum(runtime for _, runtime in method_runtimes)),
            'correction and scoring s': _seconds(shared.get('correction_and_scoring')),
            'method selection s': _seconds(shared.get('selection')),
            'report s':           _seconds(shared.get('report')),
            'BERNARD total s':    _seconds(shared.get('total')),
            'methods at a time':  shared.get('max_parallel_methods'),
            'datasets in run':    len(datasets),
            'methods run':        ', '.join(label for label, _ in method_runtimes),
        })

        rows.append(row)

    return rows


def _existing(path):
    if not os.path.exists(path):
        return [], []

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)

        try:
            header = next(rows)
        except StopIteration:
            return [], []

        columns = [str(name) for name in header if name is not None]

        records = []
        for values in rows:
            if all(value is None for value in values):
                continue
            records.append({column: value for column, value
                            in zip(columns, values) if column is not None})

        return columns, records
    finally:
        workbook.close()


def _column_order(existing_columns, new_rows):
    columns = list(existing_columns)
    seen = set(columns)

    def add(name):
        if name not in seen:
            columns.append(name)
            seen.add(name)

    if not columns:
        for name in LEADING_COLUMNS:
            add(name)
        for row in new_rows:
            for name in row:
                if name not in LEADING_COLUMNS and name not in TRAILING_COLUMNS:
                    add(name)
        for name in TRAILING_COLUMNS:
            add(name)
        return columns

    for row in new_rows:
        for name in row:
            add(name)

    return columns


def append(path, rows):
    if not rows:
        return None

    try:
        folder = os.path.dirname(os.path.abspath(path))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)

        try:
            existing_columns, existing_rows = _existing(path)
        except Exception as failure:
            kept = path + '.unreadable'
            try:
                os.replace(path, kept)
                print('\nWARNING: the runtime table ' + path + ' could not be read ('
                      + str(failure) + ').')
                print('    It has been kept as ' + kept + ' and a new table started.')
            except Exception:
                print('\nWARNING: the runtime table ' + path + ' could not be read ('
                      + str(failure) + ') and could not be renamed either.')
                return None
            existing_columns, existing_rows = [], []

        columns = _column_order(existing_columns, rows)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'runtimes'
        sheet.append(columns)

        for record in existing_rows + rows:
            sheet.append([record.get(column) for column in columns])

        sheet.freeze_panes = 'A2'

        temporary = path + '.writing'
        workbook.save(temporary)
        os.replace(temporary, path)

        return len(existing_rows) + len(rows)

    except Exception as failure:
        print('\nWARNING: the runtime table could not be written to ' + str(path)
              + ': ' + str(failure))
        print('    The results of this run are not affected.')
        if 'Permission' in type(failure).__name__ or 'permission' in str(failure).lower():
            print('    The file is most likely open in another program.')
        return None
