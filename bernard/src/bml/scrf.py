"""
Simultaneous write to a screen and to a file.

@author: Bostjan Murovec (bostjan.murovec@fe.uni-lj.si)

This file is distributed as a part of an entire application.
The use of this file is subjected to the same licensing
terms as they apply to the entire application that
this file belongs to. If you obtained this file in isolation
or without an agreement with the above stated author,
then you are not licensed to use this file in any way.
"""


# Storage for screen output until screen dump file is not set.
buffer = []

# File for writting screen messages to.
# It needs to be set by calling set_scr_file().
scr_file = None

# Counts actual number of blank lines on screen.
blank_count = 0


def scr(msg: str):
    """Simultaneously write msg to screen and to a file.

    If file is not yet defined, it stores messages into scr_buffer.
    These are written to file as soon as output file is specified
    by calling set_scr_file().
    This function also count the actual number of blank lines on
    screen for function nlgap()
    """
    if (msg is None) or (len(msg) == 0):
        return

    global buffer, scr_file, blank_count

    has_non_blank = False

    for mchr in msg:
        if (mchr != '\n') and (mchr != '\t') and (mchr != ' '):
            # String contains at least one printable character,
            # so we reset blank lines count.
            # The value of -1 means that the current line is
            # not terminated with a newline character.
            blank_count = -1
            has_non_blank = True
            break

        if mchr == '\n':
            blank_count = blank_count + 1

    if has_non_blank:
        # Count newline characters at the end of msg
        # to properly set scr_blank_count.
        for mchr in reversed(msg):
            if mchr != '\n':
                break

            blank_count = blank_count + 1

    # Do the actual print.
    # print(msg.encode('utf-8'), end='')
    print(msg, end='', flush=True)

    if scr_file is None:
        buffer.append(msg)
    else:
        with open(scr_file, 'a', encoding='utf-8') as file:
            file.write(msg)


def scrn(msg: str = ''):
    """Provide the same functionality as scr() plus newline."""
    if msg is None:
        return

    scr(msg)
    scr('\n')


def nlgap(required_blank_lines: int):
    """Assure the specified number of blank lines on screen.

    If the actual number of blank lines is larger than the
    requested amount, nothing happens.
    """
    if required_blank_lines is None:
        return

    if blank_count >= required_blank_lines:
        return

    bmsg = '\n' * (required_blank_lines - blank_count)

    scr(bmsg)


def set_scr_file(file_name: str):
    """Set file for screen dump.

    The previous contents of the specified file is deleted.

    Any potentially present lines in the global buffer are
    immediately written to the specified file, and buffer
    is no longer used further on.
    """
    global buffer, scr_file

    scr_file = file_name

    with open(scr_file, 'w', encoding='utf-8') as file:
        for msg in buffer:
            file.write(msg)

    buffer = None


def remove_scr_file(file_name: str):
    """Stop using file for screen dump.

    Global buffer becomes operational again, and it can be later on
    written to another filer that is specified with set_scr_file().
    """
    global buffer, scr_file, blank_count

    scr_file = None
    buffer = []
    blank_count = 0
