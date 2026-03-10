"Various utilities"

import inspect
import os
import re
import sys
from functools import wraps
from keyword import iskeyword

class Color:
    "Colors for the console"
    @staticmethod
    def red(text):
        "red"
        return f"\033[1;31m{text}\033[0m"
    @staticmethod
    def green(text):
        "green"
        return f"\033[1;32m{text}\033[0m"
    @staticmethod
    def blue(text):
        "blue"
        return f"\033[1;34m{text}\033[0m"
    @staticmethod
    def bold(text):
        "bold"
        return f"\033[1m{text}\033[0m"


BEGIN_CODE = "#>>> PLACE YOUR CODE BELOW THIS LINE. DO NOT REMOVE THIS LINE!\n"
END_CODE = "#<<< PLACE YOUR CODE ABOVE THIS LINE. DO NOT REMOVE THIS LINE!\n"

def read(file_):
    "Read file helper"
    with open(file_, encoding='utf-8') as text_io_wrapper:
        return text_io_wrapper.read()

def readlines(file_):
    "Return the file split on lines"
    with open(file_, encoding='utf-8') as text_io_wrapper:
        return text_io_wrapper.readlines()

def write(file_, data, mode='w'):
    "Write file helper"
    with open(file_, mode=mode, encoding='utf-8') as text_io_wrapper:
        return text_io_wrapper.write(data)

def error(msg: str, exit_code: int=None):
    "Write error message on stderr and exit if exit is not None"
    sys.stderr.write(f'{Color.bold("half-orm ERROR")}: {Color.red(msg)}')
    if exit_code:
        sys.exit(exit_code)

def warning(msg: str, context="half-orm"):
    "Write warning message on stderr"
    sys.stderr.write(f'{Color.bold(context + " WARNING")}: {msg}')

class TraceDepth: #pragma: no coverage
    "Trace dept class"
    __depth = 0
    on = False

    @classmethod
    def increase(cls):
        "Add 1 to the depth"
        cls.__depth += 1
    @classmethod
    def decrease(cls):
        "Remove 1 from the depth"
        cls.__depth -= 1
    @classmethod
    def depth(cls):
        "Returns the depth"
        return cls.__depth

def trace(fct): #pragma: no coverage
    """Property used to trace the construction of the SQL requests
    """
    @wraps(fct)
    def wrapper(self, *args, **kwargs):
        callerframerecord = inspect.stack()[1]
        frame = callerframerecord[0]
        info = inspect.getframeinfo(frame)
        context = ''
        if info.code_context:
            context = info.code_context[0]
            warn_msg = f'\n{info.filename}:{info.lineno}, in {info.function}\n{context}\n'
        sys.stderr.write(warn_msg)
        TraceDepth.increase()
        res = fct(self, *args, **kwargs)
        TraceDepth.decrease()
        return res
    return wrapper


def _ho_deprecated(fct=None, *, replacement=None):
    """Decorator marking a method as deprecated.

    Usage:
        @_ho_deprecated                        # replacement auto-computed as ho_<name>
        @_ho_deprecated(replacement='@singleton')  # custom replacement message
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            name = f.__name__
            repl = replacement if replacement is not None else f'ho_{name}'
            callerframerecord = inspect.stack()[1]
            frame = callerframerecord[0]
            info = inspect.getframeinfo(frame)
            warn_msg = (f'HalfORM WARNING! "{Color.bold(name)}" is deprecated. '
                'It will be removed in half_orm 1.0.\n'
                f'Use "{Color.bold(repl)}" instead.\n')
            if info.code_context:
                warn_msg += (f'{info.filename}:{info.lineno}, in {info.function}\n'
                    f'{info.code_context[0]}\n')
            sys.stderr.write(warn_msg)
            return f(*args, **kwargs)
        return wrapper
    if fct is not None:  # used as @_ho_deprecated without arguments
        return decorator(fct)
    return decorator  # used as @_ho_deprecated(replacement='...')

def check_attribute_name(string: str):
    err = None
    if not string.isidentifier():
        err = f'"{string}" is not a valid identifier in Python.'
    if iskeyword(string):
        err = f'"{string}" is a reserved keyword in Python.'
    return err

def get_caller_info(skip_frames=2):
    """Extract caller information for SQL trace.

    This function finds the first caller outside of the half_orm package
    to show where the SQL query was actually triggered in user code.

    Args:
        skip_frames: Minimum number of frames to skip in the stack (default: 2)
                    The function will skip at least this many frames, then
                    continue until it finds a frame outside of half_orm.

    Returns:
        dict: Contains 'filename', 'lineno', 'function', 'code_context'
              or None if no caller info is available
    """
    try:
        stack = inspect.stack()
        if len(stack) <= skip_frames:
            return None

        # Find the first frame outside of half_orm
        for i in range(skip_frames, len(stack)):
            frame = stack[i]
            frame_info = inspect.getframeinfo(frame[0])

            # Skip frames that are inside half_orm package
            if 'half_orm' in frame_info.filename and '/half_orm/' in frame_info.filename:
                continue

            # Found a frame outside half_orm
            code_line = ''
            if frame_info.code_context:
                code_line = frame_info.code_context[0].strip()

            return {
                'filename': frame_info.filename,
                'lineno': frame_info.lineno,
                'function': frame_info.function,
                'code_context': code_line
            }

        # If no external frame found, return the frame at skip_frames position
        caller_frame = stack[skip_frames]
        frame_info = inspect.getframeinfo(caller_frame[0])
        code_line = ''
        if frame_info.code_context:
            code_line = frame_info.code_context[0].strip()

        return {
            'filename': frame_info.filename,
            'lineno': frame_info.lineno,
            'function': frame_info.function,
            'code_context': code_line
        }
    except (IndexError, OSError, TypeError):
        return None
