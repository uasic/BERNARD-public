"""
Console utilities.

@author: Bostjan Murovec (bostjan.murovec@fe.uni-lj.si)

This file is distributed as a part of an entire application.
The use of this file is subjected to the same licensing
terms as they apply to the entire application that
this file belongs to. If you obtained this file in isolation
or without an agreement with the above stated author,
then you are not licensed to use this file in any way.
"""


from bml.scrf import nlgap
from bml.scrf import scrn
from bml.scrf import scr

import bml.decor as decor
import bml.strings as strings

import sys
import subprocess


def abort(msg: str = '', sys_exit_code: int = 1):
    """Print msg on screen and abort execution."""
    generic_abort_msg = 'Aborting !'

    if msg == '':
        msg = generic_abort_msg
    else:
        msg = generic_abort_msg + '\n\n' + msg + '\n\n' + generic_abort_msg

    decor.main_step(msg, 40, 70)

    nlgap(2)
    sys.exit(sys_exit_code)


def print_sep_not_none(line1, line2, scrn_gap: int = 1, indent1: str = None, indent2: str = '    '):
    """Print lin1 and line2 on separate lines, if both are not None.

    scrn_gap: number of empty lines before

    indent1, indent2: str to print before the two respective lines
    """
    if (line1 is None) or (line2 is None):
        return

    nlgap(scrn_gap)
    scr(indent1)
    scrn(line1)
    scr(indent2)
    scrn(line2)


def print_deleted_preserved(msg: str, deleted: bool = False, scrn_gap: int = 1):
    """Print msg deleted or preserved depending on the value of parameter deleted."""
    nlgap(scrn_gap)
    scr(msg + ' will be ')
    if deleted:
        scrn('DELETED.')
    else:
        scrn('preserved.')


def bash(cmd_line: str, temp_dir: str = None):
    """Run external program through a bash shell.

    Provide stdout, stderr and exit_code to a caller.
    """
    exception = None

    try:
        proc = subprocess.run(cmd_line,
                              cwd=temp_dir,
                              universal_newlines=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              stdin=None,
                              input=None,
                              shell=True,
                              executable='/bin/bash',
                              timeout=None,
                              check=False)
    except KeyboardInterrupt:
        abort("Terminated on user's request (Ctrl-C interrupt).")
    except Exception as exc:
        exception = exc

    std_ln = proc.stdout.split('\n')
    std_ln = strings.strip_empty_lines(std_ln)

    err_ln = proc.stderr.split('\n')
    err_ln = strings.strip_empty_lines(err_ln)

    out = {}
    out['stdout'] = std_ln
    out['stderr'] = err_ln
    out['exit_code'] = proc.returncode
    out['exception'] = exception

    return out


def add_param(so_far_params: str, new_param: str, new_value: str = None, sepParam: str = ' ', sepValue: str = ' '):
    """Append new_param with optional new_value to the so_far_param.

    Insert space separator if needed. Handle None gracefully.
    """
    if so_far_params is None:
        so_far_params = ''

    if not isinstance(so_far_params, str):
        so_far_params = str(so_far_params)

    so_far_params = so_far_params.strip()

    if new_param is None:
        # If new_param is empty, then ignore new_value
        return so_far_params

    if not isinstance(new_param, str):
        new_param = str(new_param)

    new_param = new_param.strip()

    if new_param == '':
        # If new_param is empty, then ignore new_value
        return so_far_params

    if so_far_params != '':
        so_far_params = so_far_params + sepParam + new_param
    else:
        so_far_params = new_param

    if new_value is None:
        return so_far_params

    if not isinstance(new_value, str):
        new_value = str(new_value)

    return so_far_params + sepValue + new_value.strip()


def add_param_if_value(so_far_params: str, new_param: str, new_value, sepParam: str = ' ', sepValue: str = ' '):
    """Append new_param with new_value to the so_far_param, if new_value is not None."""
    if new_value is None:
        return so_far_params

    return add_param(so_far_params, new_param, new_value, sepParam=sepParam, sepValue=sepValue)


def add_param_or_default(so_far_params: str, new_param: str, new_value, default, sepParam: str = ' ', sepValue: str = ' '):
    """If new_value is not None, append new_param with new_value to the so_far_param.

    If new_value is None, append new_param with default value.
    """
    if new_value is None:
        return add_param(so_far_params, new_param, default, sepParam=sepParam, sepValue=sepValue)

    return add_param(so_far_params, new_param, new_value, sepParam=sepParam, sepValue=sepValue)


def add_lparam(so_far_params: list, new_param: str, new_value: str = None):
    """Append new_param with optional new_value to the so_far_params list. Handle None gracefully."""
    if so_far_params is None:
        so_far_params = []
    elif not isinstance(so_far_params, list):
        so_far_params = [so_far_params]

    count = 0
    while count < len(so_far_params):
        if not isinstance(so_far_params[count], str):
            so_far_params[count] = str(so_far_params[count])
        count += 1

    if new_param is None:
        # If new_param is empty, then ignore new_value
        return so_far_params

    if not isinstance(new_param, str):
        new_param = str(new_param)

    new_param = new_param.strip()

    if new_param == '':
        # If new_param is empty, then ignore new_value
        return so_far_params

    so_far_params.append(new_param)

    if new_value is not None:
        if not isinstance(new_value, str):
            new_value = str(new_value)

        so_far_params.append(new_value)

    return so_far_params


def add_lparam_if_value(so_far_params: list, new_param: str, new_value):
    """Append new_param with new_value to the so_far_params, if new_value is not None."""
    if new_value is None:
        return so_far_params

    return add_lparam(so_far_params, new_param, new_value)


def add_lparam_or_default(so_far_params: list, new_param: str, new_value, default):
    """If new_value is not None, append new_param with new_value to the so_far_params.

    If new_value is None, append new_param with default value.
    """
    if new_value is None:
        return add_lparam(so_far_params, new_param, default)

    return add_lparam(so_far_params, new_param, new_value)


def add_lparam_list(so_far_params: list, new_params: list):
    """Append list of new_params to the so_far_params."""
    if so_far_params is None:
        so_far_params = []
    elif not isinstance(so_far_params, list):
        so_far_params = [so_far_params]

    count = 0
    while count < len(so_far_params):
        if not isinstance(so_far_params[count], str):
            so_far_params[count] = str(so_far_params[count])
        count += 1

    if new_params is None:
        return so_far_params

    if not isinstance(new_params, list):
        new_params = [new_params]

    count = 0
    while count < len(new_params):
        if not isinstance(new_params[count], str):
            new_params[count] = str(new_params[count])
        count += 1

    so_far_params.extend(new_params)

    return so_far_params
