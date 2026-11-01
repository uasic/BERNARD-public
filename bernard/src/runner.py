
import os
import subprocess
import sys
import threading
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed


Outcome = namedtuple('Outcome', ['method', 'status', 'runtime', 'log_path', 'message'])


_print_lock = threading.Lock()


def say(text):
    with _print_lock:
        print(text, flush=True)


def default_worker_count(method_count):
    try:
        cores = os.cpu_count() or 1
    except Exception:
        cores = 1

    return max(1, min(4, cores - 1, max(1, method_count)))


def _command_for(method, script_folder, bernard_folder):
    if method.script is None:
        return [sys.executable, os.path.join(script_folder, 'pyCombat.py'), bernard_folder]

    return ['Rscript', os.path.join(script_folder, method.script), bernard_folder]


def _last_lines(text, count):
    lines = [line.rstrip() for line in str(text).splitlines() if line.strip() != '']
    return lines[-count:]


def _run_one(method, script_folder, bernard_folder, log_folder, timeout_seconds):
    started = time.time()
    log_path = os.path.join(log_folder, method.name.replace('/', '-') + '.log')
    command = _command_for(method, script_folder, bernard_folder)

    say('    started   ' + method.label)

    try:
        finished = subprocess.run(command, capture_output=True, text=True,
                                  timeout=timeout_seconds if timeout_seconds else None)
        output = (finished.stdout or '') + (finished.stderr or '')
        status = 'completed' if finished.returncode == 0 else 'failed'
        message = (None if status == 'completed'
                   else 'the program stopped with exit code ' + str(finished.returncode))

    except subprocess.TimeoutExpired as expired:
        output = ((expired.stdout or '') if isinstance(expired.stdout, str) else '') \
                 + ((expired.stderr or '') if isinstance(expired.stderr, str) else '')
        status = 'timed out'
        message = ('the method was still running after '
                   + str(round((timeout_seconds or 0) / 60.0, 1)) + ' minutes and was stopped '
                   '(see method_timeout_minutes in the settings file)')

    except FileNotFoundError:
        output = ''
        status = 'failed'
        message = ('the program "' + command[0] + '" was not found on this machine'
                   + ('. R has to be installed to run this method' if command[0] == 'Rscript'
                      else ''))

    except Exception as failure:
        output = ''
        status = 'failed'
        message = 'the method could not be started: ' + str(failure)

    runtime = time.time() - started

    try:
        with open(log_path, 'w') as log_file:
            log_file.write('command: ' + ' '.join(command) + '\n')
            log_file.write('status:  ' + status + '\n')
            log_file.write('runtime: ' + str(round(runtime, 1)) + ' seconds\n')
            log_file.write('-' * 80 + '\n')
            log_file.write(output)
    except Exception:
        log_path = None

    if status == 'completed':
        say('    finished  ' + method.label + '  (' + str(round(runtime, 1)) + ' s)')
    else:
        say('')
        say('    WARNING: ' + method.label + ' ' + status.upper() + ' - ' + str(message) + '.')
        for line in _last_lines(output, 12):
            say('        | ' + line)
        if log_path:
            say('        the whole output of this method is in ' + log_path)
        say('        BERNARD carries on; this method is left out of the comparison.')
        say('')

    return Outcome(method, status, runtime, log_path, message)


def produced_files(corrected_outputs, method):
    try:
        return [name for name in os.listdir(corrected_outputs) if method.suffix in name]
    except Exception:
        return []


def run_methods(selected_methods, script_folder, bernard_folder, corrected_outputs, log_folder,
                max_workers, timeout_seconds=0, analyse=None, analyse_while_running=True,
                stop_on_failure=False):
    try:
        os.makedirs(log_folder, exist_ok=True)
    except Exception:
        pass

    max_workers = max(1, min(int(max_workers or 1), len(selected_methods)))

    if max_workers == 1:
        print('\nRunning ' + str(len(selected_methods))
              + ' correction method(s), one after another.')
    else:
        print('\nRunning ' + str(len(selected_methods)) + ' correction method(s), up to '
              + str(max_workers) + ' at the same time.')

    outcomes = {}
    failures = []

    def measure(outcome):
        files = produced_files(corrected_outputs, outcome.method)

        if outcome.status == 'completed' and not files:
            outcome = outcome._replace(
                status='failed',
                message='the method ended without an error but wrote no corrected file')
            say('    WARNING: ' + outcome.method.label + ' wrote no corrected file and is left '
                'out of the comparison.'
                + ('  See ' + str(outcome.log_path) if outcome.log_path else ''))

        if outcome.status == 'completed' and analyse is not None:
            try:
                analyse(outcome.method)
            except Exception as failure:
                import traceback
                outcome = outcome._replace(
                    status='failed',
                    message='the corrected data could not be measured: ' + str(failure))
                say('    WARNING: the result of ' + outcome.method.label
                    + ' could not be measured: ' + str(failure))
                say('        ' + traceback.format_exc().splitlines()[-1])
                say('        BERNARD carries on; this method is left out of the comparison.')

        outcomes[outcome.method.name] = outcome

        if outcome.status != 'completed':
            failures.append(outcome)

        return outcome

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        submitted = [(method, pool.submit(_run_one, method, script_folder, bernard_folder,
                                          log_folder, timeout_seconds))
                     for method in selected_methods]

        if analyse_while_running:
            futures = {future: method for method, future in submitted}
            for future in as_completed(futures):
                measure(future.result())
        else:
            for _, future in submitted:
                future.result()
            for _, future in submitted:
                measure(future.result())

        if stop_on_failure and failures:
            for _, future in submitted:
                future.cancel()

    if stop_on_failure and failures:
        import bml.conn as con
        con.abort('The correction method ' + failures[0].method.label + ' did not finish: '
                  + str(failures[0].message) + '.\n\n'
                  'The run was stopped because stop_on_method_failure is set to Yes in the '
                  'settings file.\n'
                  + ('The output of the method is in ' + str(failures[0].log_path)
                     if failures[0].log_path else ''))

    return [outcomes.get(method.name,
                         Outcome(method, 'failed', 0.0, None, 'the method was not run'))
            for method in selected_methods]
