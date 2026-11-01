"""
Read users' parameters from file.

@author: Bostjan Murovec (bostjan.murovec@fe.uni-lj.si)

This file is distributed as a part of an entire application.
The use of this file is subjected to the same licensing
terms as they apply to the entire application that
this file belongs to. If you obtained this file in isolation
or without an agreement with the above stated author,
then you are not licensed to use this file in any way.
"""


import bml.conn as con

from bml.scrf import nlgap as nlgap
from bml.scrf import scrn as scrn

import configparser
import shlex


paramsglb = None
paramsglb_file = None


paramsglb = configparser.ConfigParser(allow_no_value=True, strict=True, empty_lines_in_values=False)


def read_file(file: str, true_file: bool):
    """Read parameters from a file.

    If true_file is false, then file should be a list of txt lines
    consisting of configuration file.
    """
    global paramsglb
    global paramsglb_file

    if (file is None) or (true_file and (file.strip() == '')):
        con.abort('Missing config file specification.')

    try:
        if true_file:
            paramsglb_file = file

            with open(file, "r") as cfg_file:
                data_in = cfg_file.readlines()

        else:
            paramsglb_file = 'Internally synthesized configuration file'
            data_in = file

        skip_level = 0

        data_out = []

        line_count = -1

        config_errors = []

        while True:
            line_count = line_count + 1

            if line_count >= len(data_in):
                break

            line_in = data_in[line_count]

            stripped_line = (line_in.strip()).lower()

            if stripped_line == 'abort':
                this_line = '#---------------   Abort directive   ---------------'
                this_len = len(this_line) - 1
                data_out.append('#' + '-' * this_len + '\n')
                data_out.append(this_line + '\n')
                data_out.append('#' + '-' * this_len + '\n')

                skip_level = 0
                break

            if stripped_line == 'skip':
                skip_level = skip_level + 1

                this_line = '#---------------   Skip directive   ---------------'
                this_len = len(this_line) - 1
                data_out.append('#' + '-' * this_len + '\n')
                data_out.append(this_line + '\n')
                data_out.append('#' + '-' * this_len + '\n')
                continue

            if stripped_line == 'unskip':
                skip_level = skip_level - 1

                if skip_level < 0:
                    this_line = '#----------   WARNING: unmatched Unskip directive   ----------'
                    config_errors.append('WARNING: unmatched Unskip directive in config file on line ' + str(line_count + 1))
                    skip_level = 0
                else:
                    this_line = '#---------------   Unskip directive   ---------------'

                this_len = len(this_line) - 1
                data_out.append('#' + '-' * this_len + '\n')
                data_out.append(this_line + '\n')
                data_out.append('#' + '-' * this_len + '\n')
                continue

            if skip_level > 0:
                data_out.append('#' + 'skip|' * skip_level + ' ' + line_in)
                continue

            if stripped_line == 'stop':
                this_line = '#---------------   Stop directive   ---------------'
                this_len = len(this_line) - 1
                data_out.append('#' + '-' * this_len + '\n')
                data_out.append(this_line + '\n')
                data_out.append('#' + '-' * this_len + '\n')
                break

            while (len(stripped_line) > 0) and (stripped_line[0] != '#'):
                parted = stripped_line.partition('=')

                if parted[1] != '=':
                    break

                parted = line_in.partition('=')

                line_in = parted[0].lower() + '=' + parted[2]
                break

            data_out.append(line_in)

        config_string = '[generic]\n' + ''.join(data_out)

        paramsglb.read_string(config_string)
    except configparser.Error as err:
        message = 'ERROR ' + err.message
        bracket_pos = message.find('[')

        if (bracket_pos > 0) and message[bracket_pos - 1] == ' ':
            message_list = list(message)
            message_list[bracket_pos - 1] = '\n'
            message = ''.join(message_list)

        con.abort(message)
    except Exception as err:
        message = 'ERROR ' + str(err)
        con.abort(message)

    if len(paramsglb.sections()) != 1:
        con.abort('Config file\n    ' + file + '\ndoes not exist, is unreadable or has invalid contents.')

    if skip_level != 0:
        config_errors.append('WARNING: config file contains more directives "skip" than directives "unskip".')

    return [data_out, config_errors]


def param_exists(param: str):
    """Return True if parameter param is defined in a file."""
    return paramsglb.has_option('generic', param)


def req_param(param: str):
    """Read required parameter of an unspecified type from a file."""
    if not paramsglb.has_option('generic', param):
        con.abort('Config file\n    ' + paramsglb_file + '\ndoes not contain parameter ' + param + '.')


def req_string(param: str):
    """Read required string parameter from a file."""
    req_param(param)
    return paramsglb.get('generic', param)


def req_bool(param: str):
    """Read required bool parameter from a file."""
    req_param(param)

    try:
        return paramsglb.getboolean('generic', param)
    except configparser.Error:
        con.abort('Parameter ' + param + ' does not evaluate to Yes or No.')


def req_int(param: str):
    """Read required int parameter from a file."""
    req_param(param)

    try:
        return paramsglb.getint('generic', param)
    except configparser.Error:
        con.abort('Parameter ' + param + ' does not evaluate to an integer.')


def req_float(param: str):
    """Read required float parameter from a file."""
    req_param(param)

    try:
        return paramsglb.getfloat('generic', param)
    except configparser.Error:
        con.abort('Parameter ' + param + ' does not evaluate to a floating point number.')


def opt_string(param: str, default: str = None):
    """Read optional string parameter from a file."""
    if paramsglb.has_option('generic', param):
        param_value = paramsglb.get('generic', param)
        return param_value

    return default


def opt_bool(param: str):
    """Read optional bool parameter from a file, set to None if it does not exist."""
    raw = opt_string(param)
    if raw is None:
        return None

    try:
        return paramsglb.getboolean('generic', param)
    except configparser.Error:
        con.abort('Parameter ' + param + ' does not evaluate to Yes or No.')


def opt_bool_YN(param: str, default: bool):
    """Read optional bool parameter from a file, set to default if it does not exist."""
    value = opt_bool(param)

    if value is None:
        return default

    return value


def opt_bool_N(param: str):
    """Read optional bool parameter from a file, set to False if it does not exist."""
    value = opt_bool(param)

    if value is None:
        return False

    return value


def opt_bool_Y(param: str):
    """Read optional bool parameter from a file, set to True if it does not exist."""
    value = opt_bool(param)

    if value is None:
        return True

    return value


def opt_int(param: str, default: int = None):
    """Read optional int parameter from a file."""
    raw = opt_string(param)
    if raw is None:
        return default

    try:
        return int(raw)
    except ValueError:
        con.abort('Parameter ' + param + ' does not evaluate to an integer.')


def opt_nonneg_int(param: str, default: int = None, adjust: bool = True):
    """Read optional non negative int parameter from a file. If adjust, then value is auto adjusted to comply."""
    value = opt_int(param, default)

    if value is None:
        return None

    if value < 0:
        if adjust:
            value = 0
        else:
            con.abort('Parameter ' + param + ' is negative.')
    return value


def opt_pos_int(param: str, default: int = None, adjust: bool = True):
    """Read optional positive int parameter from a file. If adjust, then value is auto adjusted to comply."""
    value = opt_int(param, default)

    if value is None:
        return None

    if value <= 0:
        if adjust:
            value = 1
        else:
            con.abort('Parameter ' + param + ' is not positive.')
    return value


def opt_range_int(param: str, default: int = None, valMin: int = None, valMax: int = None, adjust: bool = True):
    """Read optional int parameter within a range from a file. If adjust, then value is auto adjusted to comply."""
    value = opt_int(param, default)

    if value is None:
        return None

    if (valMin is not None) and (value < valMin):
        if adjust:
            value = valMin
        else:
            con.abort('Parameter ' + param + ' is smaller than ' + str(valMin) + '.')
    if (valMax is not None) and (value > valMax):
        if adjust:
            value = valMax
        else:
            con.abort('Parameter ' + param + ' is larger than ' + str(valMax) + '.')
    return value


def opt_float(param: str, default: float = None):
    """Read optional float parameter from a file."""
    raw = opt_string(param)
    if raw is None:
        return default

    try:
        return float(raw)
    except ValueError:
        con.abort('Parameter ' + param + ' does not evaluate to a floating point number.')


def opt_nonneg_float(param: str, default: float = None, adjust: bool = True):
    """Read optional non negative float parameter from a file. If adjust, then value is auto adjusted to comply."""
    value = opt_float(param, default)

    if value is None:
        return None

    if value < 0.:
        if adjust:
            value = 0
        else:
            con.abort('Parameter ' + param + ' is negative.')

    return value


def opt_pos_float(param: str, default: float = None):
    """Read optional positive float parameter from a file."""
    value = opt_float(param, default)

    if value is None:
        return None

    if value <= 0.:
        con.abort('Parameter ' + param + ' is not positive.')
    return value


def opt_range_float(param: str, default: float = None, valMin: float = None, valMax: float = None, adjust: bool = True):
    """Read optional float parameter within a range from a file. If adjust, then value is auto adjusted to comply."""
    value = opt_float(param, default)

    if value is None:
        return None

    if (valMin is not None) and (value < valMin):
        if adjust:
            value = valMin
        else:
            con.abort('Parameter ' + param + ' is smaller than ' + str(valMin) + '.')
    if (valMax is not None) and (value > valMax):
        if adjust:
            value = valMax
        else:
            con.abort('Parameter ' + param + ' is larger than ' + str(valMax) + '.')
    return value


def paramstr(param: str, optional: bool = True):
    """Read a string which is a command-line (sub)string for some other command."""
    result = opt_string(param)
    if result is not None:
        result = shlex.quote(result)
        result = result.strip('"\'\t ')
        result = " ".join(result.split())

    return result


def get_param_from_msg(msg: str, param: str = None):
    """Convert human-readable msg to param by making it lower case and replacing spaces with _."""
    if param is not None:
        return param

    param = msg.lower()
    return param.replace(' ', '_')


def get_specific_param(param_name: str, msg_prepend: str = None, param_default: str = None, scrn_gap: int = 1):
    """Read arbitrary param from config file and print is on screen."""
    param = paramstr(param_name)

    if msg_prepend is not None:
        msg = msg_prepend + ' ' + param_name
    else:
        msg = param_name

    if param is not None:
        con.print_sep_not_none(msg + ': ', param)
    elif param_default is not None:
        param = param_default
        con.print_sep_not_none(msg + ' (default):', param)

    return param


def get_params(msg: str, params_root: str = None, params_default: str = None, scrn_gap: int = 1):
    """Read program params from config file and print them on screen."""
    params_root = get_param_from_msg(msg, params_root)

    params = paramstr('params_' + params_root)
    if params is not None:
        con.print_sep_not_none(msg + ' relevant params:', params, scrn_gap=scrn_gap)
    elif params_default is not None:
        params = params_default
        con.print_sep_not_none(msg + ' default params:', params, scrn_gap=scrn_gap)

    return params


def get_enabled_disabled(msg: str, param_name: str = None, default: bool = False, scrn_gap: int = 1):
    """Read bool param from file and print enabled/disabled accordingly."""
    param_name = get_param_from_msg(msg, param_name)

    state = opt_bool_YN(param_name, default)

    nlgap(scrn_gap)

    if state:
        scrn(msg + ' is enabled.')
    else:
        scrn(msg + ' is disabled.')

    return state


def get_deleted_preserved(msg: str, param_name: str, default: bool = False, scrn_gap: int = 1):
    """Read bool param from file and print deleted/preserved accordingly."""
    param_name = get_param_from_msg(msg, param_name)

    state = opt_bool_YN(param_name, default)

    nlgap(scrn_gap)

    if state:
        scrn(msg + ' will be DELETED.')
    else:
        scrn(msg + ' will be preserved.')

    return state
