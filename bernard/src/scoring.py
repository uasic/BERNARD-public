import numpy as np
import pandas as pd

AUROC_PARTS = ['cv', 'lobo']

ACCEPTED_COLUMN = 'accepted'
REASON_COLUMN = 'rejection-reason'
SCORE_COLUMN = 'consensus-score'
RANK_COLUMN = 'final-rank'
BEST_COLUMN = 'Best performance'
GATE_SKIPPED_COLUMN = 'step-1-skipped'
AUROC_MEAN_SUFFIX = '-mean-corrected'


def auroc_mean_column(factor_of_interest):
    return f'AUROC-{factor_of_interest}{AUROC_MEAN_SUFFIX}'


def ranking_lists(study_name, factor_of_interest):
    lisi_batch = f'iLISI-{study_name}-corrected'
    lisi_biology = f'cLISI-{factor_of_interest}-corrected'
    return [
        ('R2-batch',                    f'permanova-{study_name}-R2-corrected',                False),
        ('silhouette-batch',            f'silhouette-{study_name}-corrected',                  False),
        ('kBET-batch',                  f'kBET-{study_name}-acceptance-corrected',             True),
        ('LISI-batch',                  lisi_batch,                                            True),
        ('graph-connectivity-batch',    f'graph-connectivity-{study_name}-corrected',          False),
        ('alignment-score-batch',       f'alignment-score-{study_name}-corrected',             True),
        ('entropy-batch',               f'entropy-score-{study_name}-corrected',               True),
        ('pvca-batch',                  'pvca-batch-percent-corrected',                        False),
        ('varpart-batch',               'varpart-batch-only-corrected',                        False),
        ('features-associated-batch',   f'features-associated-{study_name}-percent-corrected', False),
        ('R2-biology',                  f'permanova-{factor_of_interest}-R2-corrected',                True),
        ('silhouette-biology',          f'silhouette-{factor_of_interest}-corrected',                  True),
        ('kBET-biology',                f'kBET-{factor_of_interest}-acceptance-corrected',             False),
        ('LISI-biology',                lisi_biology,                                                  False),
        ('graph-connectivity-biology',  f'graph-connectivity-{factor_of_interest}-corrected',          True),
        ('alignment-score-biology',     f'alignment-score-{factor_of_interest}-corrected',             False),
        ('entropy-biology',             f'entropy-score-{factor_of_interest}-corrected',               False),
        ('pvca-biology',                'pvca-phenotype-percent-corrected',                            True),
        ('varpart-biology',             'varpart-phenotype-only-corrected',                            True),
        ('features-associated-biology', f'features-associated-{factor_of_interest}-percent-corrected', True),
        ('AUROC-biology',               auroc_mean_column(factor_of_interest),                         True),
    ]


def points_column(list_name):
    return f'points-{list_name}'


def _add_auroc_mean(table, factor_of_interest):
    columns = [f'AUROC-{factor_of_interest}-{part}-corrected' for part in AUROC_PARTS]
    present = [column for column in columns if column in table.columns]
    target = auroc_mean_column(factor_of_interest)
    if not present:
        table[target] = np.nan
        return table
    values = table[present].apply(pd.to_numeric, errors='coerce')
    table[target] = values.mean(axis=1, skipna=True)
    return table


def _gate(table, study_name, factor_of_interest, alpha):
    batch_column = f'permanova-{study_name}-p-value-corrected'
    biology_column = f'permanova-{factor_of_interest}-p-value-corrected'

    for column in (batch_column, biology_column):
        if column not in table.columns:
            table[column] = np.nan
    batch_p = pd.to_numeric(table[batch_column], errors='coerce')
    biology_p = pd.to_numeric(table[biology_column], errors='coerce')

    reasons = []
    for batch_value, biology_value in zip(batch_p, biology_p):
        if pd.isna(batch_value) or pd.isna(biology_value):
            reasons.append('PERMANOVA p-value missing, method cannot be assessed')
        elif batch_value < alpha:
            reasons.append(f'batch effect still significant ({study_name} p = {batch_value:.4g} '
                           f'< {alpha})')
        elif biology_value > alpha:
            reasons.append(f'biological signal lost ({factor_of_interest} p = {biology_value:.4g} '
                           f'> {alpha})')
        else:
            reasons.append(None)

    table[REASON_COLUMN] = reasons
    table[ACCEPTED_COLUMN] = pd.Series([reason is None for reason in reasons],
                                       index=table.index, dtype=object)
    return table


def gate_skipped_datasets(table):
    if GATE_SKIPPED_COLUMN not in table.columns or 'datasetName' not in table.columns:
        return []
    skipped = table[table[GATE_SKIPPED_COLUMN] == True]
    return [str(dataset) for dataset in skipped['datasetName'].dropna().unique()]


def _numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def score_methods(full_calculation, study_name, factor_of_interest, alpha=0.05):
    table = full_calculation.copy()
    table = _add_auroc_mean(table, factor_of_interest)
    table = _gate(table, study_name, factor_of_interest, alpha)

    if 'method' in table.columns:
        is_method = table['method'].notna() & (table['method'].astype(str) != 'uncorrected')
    else:
        is_method = pd.Series(False, index=table.index)
    table.loc[~is_method, ACCEPTED_COLUMN] = None
    table.loc[~is_method, REASON_COLUMN] = None

    lists = ranking_lists(study_name, factor_of_interest)
    for list_name, _, _ in lists:
        table[points_column(list_name)] = np.nan
    table[SCORE_COLUMN] = np.nan
    table[RANK_COLUMN] = np.nan
    table[BEST_COLUMN] = None
    table[GATE_SKIPPED_COLUMN] = None

    ordering_rows = []
    skipped_lists = set()

    for dataset in table['datasetName'].dropna().unique():
        in_dataset = (table['datasetName'] == dataset)
        candidates = table.index[in_dataset & is_method]
        competitors = table.index[in_dataset & is_method & (table[ACCEPTED_COLUMN] == True)]

        gate_was_skipped = len(competitors) == 0 and len(candidates) > 0
        if gate_was_skipped:
            competitors = candidates
        table.loc[candidates, GATE_SKIPPED_COLUMN] = gate_was_skipped

        ordering_row = {'datasetName': dataset,
                        'accepted methods': int((table.loc[candidates, ACCEPTED_COLUMN] == True).sum()),
                        'ranked methods': len(competitors),
                        'step 1': 'skipped, no method passed it' if gate_was_skipped else 'applied'}

        if len(competitors) == 0:
            for list_name, _, _ in lists:
                ordering_row[list_name] = ''
            ordering_rows.append(ordering_row)
            continue

        names = table.loc[competitors, 'method'].astype(str)

        for list_name, column, higher_is_better in lists:
            if column not in table.columns:
                skipped_lists.add((list_name, column))
                table.loc[competitors, points_column(list_name)] = 0.0
                ordering_row[list_name] = ''
                continue
            values = pd.to_numeric(table.loc[competitors, column], errors='coerce').dropna()
            if values.empty:
                table.loc[competitors, points_column(list_name)] = 0.0
                ordering_row[list_name] = ''
                continue

            points = values.rank(ascending=higher_is_better, method='average')
            table.loc[competitors, points_column(list_name)] = 0.0
            table.loc[points.index, points_column(list_name)] = points

            ordered = values.sort_values(ascending=not higher_is_better)
            pieces, run = [], []
            previous = None
            for position, value in ordered.items():
                if previous is not None and value != previous:
                    pieces.append(' = '.join(run))
                    run = []
                run.append(names[position])
                previous = value
            if run:
                pieces.append(' = '.join(run))
            ordering_row[list_name] = ' -> '.join(pieces)

        ordering_rows.append(ordering_row)

        point_columns = [points_column(list_name) for list_name, _, _ in lists]
        totals = table.loc[competitors, point_columns].sum(axis=1)
        table.loc[competitors, SCORE_COLUMN] = totals

        batch_r2_column = f'permanova-{study_name}-R2-corrected'
        if batch_r2_column in table.columns:
            tie_break = pd.to_numeric(table.loc[competitors, batch_r2_column], errors='coerce')
        else:
            tie_break = pd.Series(np.nan, index=competitors)
        order = pd.DataFrame({'score': totals,
                              'tie_break': tie_break.fillna(np.inf),
                              'name': names}).sort_values(
            ['score', 'tie_break', 'name'], ascending=[False, True, True])
        table.loc[order.index, RANK_COLUMN] = np.arange(1, len(order) + 1, dtype=float)

        tied = order['score'].duplicated(keep=False)
        if tied.any():
            print(f'Note: {dataset} has methods on an equal score '
                  f'({", ".join(order.loc[tied, "name"])}). They were separated on the leftover '
                  f'{study_name} variability, the lower the better.')

        if not gate_was_skipped:
            rejected = table.index[in_dataset & is_method & (table[ACCEPTED_COLUMN] == False)]
            table.loc[rejected, [SCORE_COLUMN, RANK_COLUMN]] = 0.0

        table.loc[order.index[0], BEST_COLUMN] = 'Best performance'

    if skipped_lists:
        print('')
        for list_name, column in sorted(skipped_lists):
            print(f'Note: the {list_name} list was left out of the scoring, because the column '
                  f'"{column}" is not in the results table.')

    ranks = pd.to_numeric(table[RANK_COLUMN], errors='coerce')
    table[RANK_COLUMN] = pd.Series([None if pd.isna(value) else int(value) for value in ranks],
                                  index=table.index, dtype=object)
    orderings = pd.DataFrame(ordering_rows,
                             columns=['datasetName', 'accepted methods', 'ranked methods',
                                      'step 1'] +
                                     [list_name for list_name, _, _ in lists])
    return table, orderings


def _report_gate_skipped(ranked, study_name, factor_of_interest, alpha):
    best = ranked[ranked[BEST_COLUMN] == 'Best performance']
    if best.empty:
        best = ranked.iloc[:1]
    row = best.iloc[0]
    name = str(row['method'])
    batch_p = _numeric(row.get(f'permanova-{study_name}-p-value-corrected'))
    biology_p = _numeric(row.get(f'permanova-{factor_of_interest}-p-value-corrected'))
    batch_left = pd.isna(batch_p) or batch_p < alpha
    biology_lost = not pd.isna(biology_p) and biology_p > alpha

    print('')
    if batch_left:
        print(f'    None of the methods removed the batch effect. The best selected method is {name}.')
    else:
        print(f'    None of the methods passed step 1. The best selected method is {name}.')
    if batch_left:
        measured = (f'{study_name} p = {batch_p:.4g} < {alpha}' if not pd.isna(batch_p)
                    else f'the {study_name} p-value could not be measured')
        print(f'    WARNING: the batch effect is still significant after {name} ({measured}).')
        print('    It was reduced but not removed, and the corrected data has to be read knowing that.')
    if biology_lost:
        print(f'    WARNING: the {factor_of_interest} groups no longer separate significantly after '
              f'{name}')
        print(f'    ({factor_of_interest} p = {biology_p:.4g} > {alpha}): part of the biology was '
              f'removed with the batch effect.')


def report_decision(table, study_name, factor_of_interest, alpha):
    print('')
    print('=' * 99)
    print('METHOD SELECTION')
    print('=' * 99)
    print(f'Step 1 rejects a method whose corrected data still separates by {study_name} '
          f'(p < {alpha}),')
    print(f'or no longer separates by {factor_of_interest} (p > {alpha}). The methods that remain')
    print('are ranked on 21 measures and the rank points are added up; the highest total wins.')
    print('If NO method passes step 1, it is skipped and all methods are ranked, so that the best')
    print('of them is still reported - with the warning that it did not pass step 1.')

    for dataset in table['datasetName'].dropna().unique():
        rows = table[table['datasetName'] == dataset]
        rows = rows[rows[ACCEPTED_COLUMN].notna()]
        print('')
        print(f'{dataset}')
        rejected = rows[rows[ACCEPTED_COLUMN] == False]
        for _, row in rejected.iterrows():
            print(f'    rejected  {str(row["method"]):<20} {row[REASON_COLUMN]}')

        skipped = (GATE_SKIPPED_COLUMN in rows.columns
                   and bool((rows[GATE_SKIPPED_COLUMN] == True).any()))
        if skipped:
            print('    Step 1 rejected every method, so it was skipped: all of them were ranked on')
            print('    the 21 measures instead, and the best of them is reported below.')

        places = pd.to_numeric(rows[RANK_COLUMN], errors='coerce').fillna(0)
        ranked = rows[places > 0].sort_values(RANK_COLUMN)
        if ranked.empty:
            print(f'    No method could be ranked, so no best method is reported for {dataset}.')
            continue
        for _, row in ranked.iterrows():
            marker = '  <- best' if row[BEST_COLUMN] == 'Best performance' else ''
            print(f'    rank {int(row[RANK_COLUMN]):<3}  {str(row["method"]):<20} '
                  f'score {row[SCORE_COLUMN]:.1f}{marker}')

        if skipped:
            _report_gate_skipped(ranked, study_name, factor_of_interest, alpha)
