# -*- coding: UTF-8 -*-
from integrationtestsetup import TESTDATADIR, CONFDIR, DummySMTPServer

import unittest

try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser


import logging
import sys
import time
from fuglu.core import MainController

def setup_module():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

class ReloadTest(unittest.TestCase):

    def test_backend_reload(self):
        config = RawConfigParser()
        config.add_section('performance')
        # minimum scanner threads
        config.set('performance', 'minthreads', 2)
        # maximum scanner threads
        config.set('performance', 'maxthreads', 40)
        # Method for parallelism, either 'thread' or 'process'
        config.set('performance', 'backend', 'process')
        # Initial number of processes when backend='process'.
        # If 0 (the default), automatically selects twice the number of available virtual cores.
        # Despite its 'initial'-name, this number currently is not adapted automatically.
        config.set('performance', 'initialprocs', 0)

        mc = MainController(config)
        mc.propagate_core_defaults()

        # usually the backend is loaded by "startup()" which is run
        # in a separate thread because it goes to the event loop. I'll just
        # directly start a the threadpool here...
        mc.threadpool = mc._start_threadpool()
        time.sleep(0.1)
        try:
            self.assertIsNone(mc.procpool)
            self.assertIsNotNone(mc.threadpool)
        except AttributeError:
            # Python 2.6
            self.assertTrue(mc.procpool is None)
            self.assertTrue(mc.threadpool is not None)

        # now reload will replace the threadpool by a procpool
        mc.reload()
        time.sleep(0.1)
        try:
            self.assertIsNone(mc.threadpool)
            self.assertIsNotNone(mc.procpool)
        except AttributeError:
            # Python 2.6
            self.assertTrue(mc.threadpool is None)
            self.assertTrue(mc.procpool is not None)
        config.set('performance', 'backend', 'thread')

        # now reload will replace the procpool by a threadpool
        mc.reload()
        time.sleep(0.1)
        try:
            self.assertIsNone(mc.procpool)
            self.assertIsNotNone(mc.threadpool)
        except AttributeError:
            # Python 2.6
            self.assertTrue(mc.procpool is None)
            self.assertTrue(mc.threadpool is not None)
        mc.shutdown()

class MultipleMCsTest(unittest.TestCase):
    """
    Even if there are multiple MainControllers they should not cause crashes as long as they
    don't start control servers...
    """
    def test_multiple_mcs(self):
        """Just start multiple controllsers """

        config = RawConfigParser()
        mclist = []
        for i in range(10):
            mc = MainController(config)
            mc.propagate_core_defaults()
            mclist.append(mc)

        for mc in mclist:
            # usually the backend is loaded by "startup()" which is run
            # in a separate thread because it goes to the event loop. I'll just
            # directly start a the threadpool here...
            mc.threadpool = mc._start_threadpool()
        time.sleep(0.1)

        for mc in mclist:
            mc.shutdown()

    def test_multiple_mcs_reload(self):
        """
        Even if there are multiple MainControllers they should not cause crashes as long as they
        don't start control servers...

        Returns:

        """
        config = RawConfigParser()
        config.add_section('performance')
        # minimum scanner threads
        config.set('performance', 'minthreads', 2)
        # maximum scanner threads
        config.set('performance', 'maxthreads', 40)
        # Method for parallelism, either 'thread' or 'process'
        config.set('performance', 'backend', 'process')
        # Initial number of processes when backend='process'.
        # If 0 (the default), automatically selects twice the number of available virtual cores.
        # Despite its 'initial'-name, this number currently is not adapted automatically.
        config.set('performance', 'initialprocs', 0)

        config = RawConfigParser()
        mclist = []
        for i in range(3):
            mc = MainController(config)
            mc.propagate_core_defaults()
            mclist.append(mc)

        for mc in mclist:
            # usually the backend is loaded by "startup()" which is run
            # in a separate thread because it goes to the event loop. I'll just
            # directly start a the threadpool here...
            mc.threadpool = mc._start_threadpool()
        time.sleep(0.1)
        for mc in mclist:
            mc.reload()
        time.sleep(0.1)

        for mc in mclist:
            mc.shutdown()
