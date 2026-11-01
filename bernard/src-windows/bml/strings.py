"""
String handling routines.

@author: Bostjan Murovec (bostjan.murovec@fe.uni-lj.si)

This file is distributed as a part of an entire application.
The use of this file is subjected to the same licensing
terms as they apply to the entire application that
this file belongs to. If you obtained this file in isolation
or without an agreement with the above stated author,
then you are not licensed to use this file in any way.
"""


import fnmatch


def has_whitespace(in_str: str):
    """Return True if string contains at least one space of tab."""
    for c in in_str:
        if c in ' \t':
            return True
    return False


def strip_empty_lines(strings: list):
    """Remove leading and trailing blank lines from a collection of strings.

    Whitespaces ares stripped from the remaining lines.
    """
    while len(strings) > 0:
        temp = strings[-1]
        temp = temp.strip('\n\t ')
        if len(temp) != 0:
            break

        del strings[-1]

    while len(strings) > 0:
        temp = strings[0]
        temp = temp.strip('\n\t ')
        if len(temp) != 0:
            break

        del strings[0]

    idx = 0
    stop = len(strings)

    while idx < stop:
        strings[idx] = strings[idx].strip('\n\t ')
        idx = idx + 1

    return strings


def strip_all_empty_lines(strings: list):
    """Remove all blank lines from a collection of strings, not just beginning and ending ones.

    Whitespaces ares stripped from the remaining lines.
    """
    strings = strip_empty_lines(strings)

    seek = 0

    while seek < len(strings):
        if len(strings[seek]) == 0:
            del strings[seek]
        else:
            seek += 1

    return strings


def largest_line_len(message: str, min_len: int = None, max_len: int = None):
    """Split message at newlines and returns the length of the largest line.

    Optionally corrects the length to comply with
    the specified minimal and maximal lengths.
    """
    mlines = message.split('\n')
    mlen = 0

    for m in mlines:
        if len(m) > mlen:
            mlen = len(m)

    if (min_len is not None) and (mlen < min_len):
        mlen = min_len

    if (max_len is not None) and (mlen > max_len):
        mlen = max_len

    return mlen


def concat(*pieces):
    """Concatenate input strings. Skip entries that are None.

    Separator is comma.
    """
    result = ''

    idx = 0
    idx_stop = len(pieces)

    while idx < idx_stop:
        piece = pieces[idx]
        idx = idx + 1

        if piece is None:
            continue

        if len(result) > 0:
            result = result + ','

        result = result + piece

    return result


def add_piece(so_far: str, piece: str = None, separator: str = ' '):
    """Add piece to the so_far string.

    The intention is to concatenate strings for building
    parameters/command line for running external programs
    through bash, but other similar uses are possible.

    If piece is None, an unchanged value of the so_far
    is returned. If so_far is not empty, separator is added
    to it before piece is concatenated.
    """
    if so_far is None:
        so_far = ''

    if piece is None:
        return so_far

    if len(so_far) == 0:
        return piece

    return so_far + separator + piece


def check_keyword(keyword: str, list_of_str: list):
    """Check string in lists_of_str for presence of a keyword.

    If lowercase variant of nay string equals a prescribed keyword,
    then the value of True is returned; False otherwise.
    """
    keyword = keyword.lower()

    for item in list_of_str:
        if item is None:
            continue

        item = item.lower()

        if item == keyword:
            return True

    return False


def check_valid_keywords(keywords: list, entries: str, sep=','):
    """Split entries on sep, and converts them to lowercase.

    Then check that every entry is a keyword from keywords list.
    Returns True if so, and False, if at least one entry is
    not a valid keyword.

    If entries is None, returns True.
    """
    if entries is None:
        return True

    entries = entries.split(sep)

    for entry in entries:
        entry = entry.lower()

        if entry not in keywords:
            return False

    return True


def first_last_lines(list_of_str: list, first_header: str, last_header: str, first_lines: int = 5, last_lines: int = 5):
    """Constellate a list of the first and the last lines.

    Prepoend header and footer to the result.
    """
    result = []

    lines = len(list_of_str)

    if last_lines > lines:
        last_lines = lines

    remaining_lines = lines - last_lines

    if remaining_lines < 0:
        remaining_lines = 0

    if first_lines > remaining_lines:
        first_lines = remaining_lines

#    header_len = 0
#    if first_header is not None:
#        header_len = len(first_header)
#    if last_header is not None:
#        if len(last_header) > header_len:
#            header_len = len(last_header)

    if first_lines > 0:
        if first_header is not None:
            result.append('-' * len(first_header))
            result.append(first_header)
            result.append('-' * len(first_header))

        count = 0

        while count < first_lines:
            result.append(list_of_str[count])
            count = count + 1

    if last_lines > 0:
        if last_header is not None:
            result.append('-' * len(last_header))
            result.append(last_header)
            result.append('-' * len(last_header))

        count = last_lines

        while count > 0:
            result.append(list_of_str[-count])
            count = count - 1

    return result


def datetime_human(datetime):
    """Convert datetime and timedinto string without fractions of seconds."""
    return str(datetime).split('.', 2)[0]


def replace_begin(original: str,
                  begin: str,
                  remove_begin: bool = True,
                  prefix_starts: str = None,
                  prefix_not_starts: str = None):
    """If original begins with begin, begin can be optionally removed from original.

    Then the approprirate prefix is optionally appended to the beginning.
    """
    if original.startswith(begin):
        if remove_begin:
            temp = original[len(begin):]
        else:
            temp = original

        if prefix_starts is None:
            return temp

        return prefix_starts + temp
    else:
        if prefix_not_starts is None:
            return original

        return prefix_not_starts + original


def split_and_trim(in_string: str, delim=','):
    if (in_string is None) or (len(in_string) == 0):
        return []

    in_string = in_string.split(delim)
    in_string = [s.strip() for s in in_string]

    return in_string


def match_file_name(file_name, bash_pattern):
    return fnmatch.fnmatch(file_name, bash_pattern)
