
from collections import namedtuple

import bml.conn as con


Method = namedtuple('Method', ['name', 'label', 'script', 'suffix', 'method'])


ALL_METHODS = [
    Method('pyCombat',          'pyCombat',            None,                     '_pyCombat-tmp',          'pyCombat'),
    Method('BMC',               'BMC',                 'BMC.R',                  '_bmc-tmp',               'bmc'),
    Method('RemoveBatchEffect', 'RemoveBatchEffect()', 'RemoveBatchEffect().R',  '_RemoveBatchEffect-tmp', 'RemoveBatchEffect()'),
    Method('ConQuR',            'ConQuR',              'ConQuR.R',               '_ConQuR-tmp',            'ConQuR'),
    Method('RUV3',              'RUV3',                'RUV3.R',                 '_ruv3-tmp',              'RUV3'),
    Method('PLSDA',             'PLSDA',               'PLSDA.R',                '_PLSDA-tmp',             'PLSDA'),
    Method('sPLSDA',            'sPLSDA',              'sPLSDA.R',               '_sPLSDA-tmp',            'sPLSDA'),
    Method('wPLSDA',            'wPLSDA',              'wPLSDA.R',               '_wPLSDA-tmp',            'wPLSDA'),
    Method('PN',                'PN',                  'PN.R',                   '_pn-tmp',                'pn'),
    Method('MetaDICT',          'MetaDICT',            'MetaDICT.R',             '_MetaDICT-tmp',          'MetaDICT'),
    Method('ComBat-Seq',        'ComBat-Seq',          'ComBatSeq.R',            '_ComBatSeq-tmp',         'ComBatSeq'),
    Method('MMUPHin',           'MMUPHin',             'MMUPHin.R',              '_MMUPHin-tmp',           'MMUPHin'),
    Method('RUV-III-NB',        'RUV-III-NB',          'RUVIIINB.R',             '_RUVIIINB-tmp',          'RUVIIINB'),
    Method('FSQN',              'FSQN',                'FSQN.R',                 '_FSQN-tmp',              'FSQN'),
    Method('FAbatch',           'FAbatch',             'FAbatch.R',              '_FAbatch-tmp',           'FAbatch'),
    Method('DEBIAS-M',          'DEBIAS-M',            'DEBIASM.R',              '_DEBIASM-tmp',           'DEBIASM'),
]

ALIASES = {
    'combat': 'pyCombat',
    'batchmeancentering': 'BMC',
    'limma': 'RemoveBatchEffect',
    'ruviii': 'RUV3',
    'plsdabatch': 'PLSDA',
    'splsdabatch': 'sPLSDA',
    'wplsdabatch': 'wPLSDA',
    'percentilenormalisation': 'PN',
    'percentilenormalization': 'PN',
    'ruv3nb': 'RUV-III-NB',
    'featurespecificquantilenormalisation': 'FSQN',
    'featurespecificquantilenormalization': 'FSQN',
}


def normalise(name: str):
    return ''.join(character for character in name.lower() if character.isalnum())


def split_list(value: str):
    if value is None:
        return []

    return [name for name in value.replace(',', ' ').split() if name != '']


def available_methods():
    return [method.name for method in ALL_METHODS]


def lookup(name: str, param: str):
    by_name = {normalise(method.name): method for method in ALL_METHODS}

    normalised = normalise(name)

    if normalised in ALIASES:
        normalised = normalise(ALIASES[normalised])

    if normalised not in by_name:
        con.abort('Parameter ' + param + ' contains an unknown batch effect correction method: '
                  + name + '.\n\nAvailable methods are:\n    '
                  + '\n    '.join(available_methods())
                  + '\n\nWrite "all" to run all of them.')

    return by_name[normalised]


def select_methods(selected: str, excluded: str = None):
    selected_names = split_list(selected)

    if (len(selected_names) == 0) or (len(selected_names) == 1 and normalise(selected_names[0]) == 'all'):
        chosen = list(ALL_METHODS)
    elif len(selected_names) == 1 and normalise(selected_names[0]) == 'none':
        chosen = []
    else:
        wanted = {lookup(name, 'correction_methods').name for name in selected_names}
        chosen = [method for method in ALL_METHODS if method.name in wanted]

    unwanted = {lookup(name, 'exclude_correction_methods').name
                for name in split_list(excluded) if normalise(name) != 'none'}
    chosen = [method for method in chosen if method.name not in unwanted]

    if len(chosen) == 0:
        con.abort('No batch effect correction method is left to run.\n\n'
                  'Check parameters correction_methods and exclude_correction_methods '
                  'in the config file.\n\nAvailable methods are:\n    '
                  + '\n    '.join(available_methods()))

    return chosen
