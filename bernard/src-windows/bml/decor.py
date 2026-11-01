"""
On-screen decorations.

@author: Bostjan Murovec (bostjan.murovec@fe.uni-lj.si)

This file is distributed as a part of an entire application.
The use of this file is subjected to the same licensing
terms as they apply to the entire application that
this file belongs to. If you obtained this file in isolation
or without an agreement with the above stated author,
then you are not licensed to use this file in any way.
"""


from bml.scrf import scr
from bml.scrf import scrn
from bml.scrf import nlgap

import bml.strings as strings


def main_step(message: str, min_len: int = 70, max_len: int = None):
    """Provide uniform on screen decoration of main step message.

    Optionally prescribe minimal and maximal length of a decoration.
    """
    mlen = strings.largest_line_len(message, min_len, max_len)

    nlgap(10)
    scrn('=' * mlen)
    scrn('=' * mlen)
    nlgap(1)
    scrn(message)
    nlgap(1)
    scrn('=' * mlen)
    scrn('=' * mlen)


def sub_step(message: str, min_len: int = 70, max_len: int = None):
    """Provide uniform on screen decoration of sub step message.

    Optionally prescribe minimal and maximal length of a decoration.
    """
    mlen = strings.largest_line_len(message, min_len, max_len)

    nlgap(5)
    scrn('=' * mlen)
    nlgap(1)
    scrn(message)
    nlgap(1)
    scrn('=' * mlen)


def subsub_step(message: str, min_len: int = 70, max_len: int = None):
    """Provide uniform on screen decoration of subsub step message.

    Optionally prescribe minimal and maximal length of a decoration.
    """
    mlen = strings.largest_line_len(message, min_len, max_len)

    nlgap(3)
    scrn('-' * mlen)
    nlgap(1)
    scrn(message)
    nlgap(1)
    scrn('-' * mlen)


def minor_step(message: str, min_len: int = 70, max_len: int = None):
    """Provide uniform on screen decoration of minor step message.

    Optionally prescribe minimal and maximal length of a decoration.
    """
    mlen = strings.largest_line_len(message, min_len, max_len)

    nlgap(3)
    scrn('-' * mlen)
    scrn(message)
    scrn('-' * mlen)


def exe_step(message: str, min_len: int = None, max_len: int = None):
    """Provide uniform on screen decoration of execution step message.

    Optionally prescribes minimal and maximal length of a decoration.

    Line is not terminated with the newline character,
    so that a status message can be printed on the same line
    upon completion of the execution.
    """
    mlen = strings.largest_line_len(message, min_len, max_len)

    nlgap(2)
    scrn('_' * mlen)
    scr(message)


def major_warning(message: str, min_len: int = None, max_len: int = None):
    """Provide uniform on screen decoration of major warning message.

    Optionally prescribes minimal and maximal length of a decoration.

    Line is not terminated with the newline character,
    so that a status message can be printed on the same line
    upon completion of the execution.
    """
    prepend = '%  WARNING: '

    mlen = strings.largest_line_len(message, min_len, max_len) + prepend + 2

    nlgap(3)
    scrn('%  ' * mlen / 3)
    scrn('%')
    scrn(prepend + message)
    scrn('%')
    scrn('%  ' * mlen / 3)
