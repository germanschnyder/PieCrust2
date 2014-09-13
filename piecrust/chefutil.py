import time
from colorama import Fore


def format_timed(start_time, message, colored=True):
    end_time = time.clock()
    time_str = '%8.1f ms' % ((end_time - start_time) * 1000.0)
    if colored:
        return '[%s%s%s] %s' % (Fore.GREEN, time_str, Fore.RESET, message)
    return '[%s] %s' % (time_str, message)


def log_friendly_exception(logger, ex):
    indent = ''
    while ex:
        logger.error('%s%s' % (indent, str(ex)))
        indent += '  '
        ex = ex.__cause__


def print_help_item(s, title, description, margin=4, align=25):
    s.write(margin * ' ')
    s.write(title)
    spacer = (align - margin - len(title) - 1)
    if spacer <= 0:
        s.write("\n")
        s.write(' ' * align)
    else:
        s.write(' ' * spacer)
    s.write(description)
    s.write("\n")

