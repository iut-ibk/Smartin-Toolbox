#!/usr/bin/python3
import itertools as it
import string
import collections as c
import datetime as dt
import sys


def log(log_type, msg):
    now = dt.datetime.now()
    print('{}: {}: {}'.format(now, log_type, msg), file=sys.stderr)


def swmm_input_read(f):
    ls = list(_swmm_input_preprocess(f.readlines()))
    nlines = len(ls)

    i = 0
    expect_header = True

    #NOTE: do not mess with section order!
    inp = c.OrderedDict()
    while i < nlines:
        l = ls[i]
        if expect_header:
            if l[0] == '[' and l[-1] == ']':
                name = l[1:-1]
                data = []
                expect_header = False
            else:
                return False, 'internal error: expected \'[\', found: \'' + l + '\''
        else:
            if l[0] == '[':
                inp[name] = data
                expect_header = True
                i -= 1
            else:
                data.append(l.split())
        i += 1

    # remainder
    if data:
        inp[name] = data

    return True, inp


def _swmm_input_preprocess(ls):
    ls = map(lambda l : ''.join(it.takewhile(lambda c : c not in ";\n\r", l)), ls) # get rid of comments ...
    ls = filter(lambda l : any(map(lambda c : c in string.printable, l)), ls)      # ... and blank lines
    return ls


def swmm_input_write(f, inp):
    for name, ls in inp.items():
        f.write('[' + name + ']\n')
        for l in ls:
            f.write(' '.join(l) + '\n')
        f.write('\n')

