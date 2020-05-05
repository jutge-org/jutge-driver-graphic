#!/usr/bin/python3

import sys
import os
import re
import string
import time
import util
import logging


'''
Checker functions are used to check that a generated output file is correct with
regards to a given correct output file. In general, the checkers return 'AC',
'WA', 'PE', 'IC' or 'IE'. Maybe some special checker could return another value
(points, for instance).
'''


#############################################################################
# graphic checker
#############################################################################


def graphic(file1, file2, diff):
    '''
        The graphic checker is used to check for graphic outputs.
        It returns:

        - AC: if the two images are identical.
        - PE: if the two images are not identical but similar.
        - WA: otherwise.
        - IE: On exception

        In addition, it generates a diff file with the difference
        of the images if not AC.
    '''

    try:
        t1 = util.read_file(file1)
        t2 = util.read_file(file2)
        if t1 == t2:
            return 'AC'

        os.system("identify -format '%%w %%h' %s > identify-1.txt" % file1)
        identify1 = open('identify-1.txt', 'r').read()
        logging.info(identify1)

        os.system("identify -format '%%w %%h' %s > identify-2.txt" % file2)
        identify2 = open('identify-2.txt', 'r').read()
        logging.info(identify2)

        if identify1 != identify2:
            return 'IC'

        os.system("compare -metric RMSE %s %s NULL: 2> compare.txt" % (file1, file2))
        output = open('compare.txt', 'r').read()
        logging.info(output)

        value = float(output.split()[1][1:-1])

        if value == 0:
            return 'AC'

        os.system("compare -compose src %s %s %s" % (file1, file2, diff))
        if value <= 0.05:     # valor patilleru buscat empiricament en cinc minuts
            return 'PE'

        return 'WA'

    except Exception as e:
        logging.info(str(e))
        return 'IE'
