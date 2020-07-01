#!/usr/bin/python3

# Python3 script that is used to check the correctness of the submission

import py_compile
import sys

# Compile the python script to check the code correctness
py_compile.compile(sys.argv[1])
