# -*- coding: UTF-8 -*-
import os
import sys

UNITTESTDIR = os.path.dirname(os.path.realpath(__file__))
CODEDIR = os.path.abspath(UNITTESTDIR + '../../../src')
TESTDATADIR = os.path.abspath(UNITTESTDIR + '/../unit/testdata')
CONFDIR = os.path.abspath(CODEDIR + '/../conf')

sys.path.insert(0, CODEDIR)
