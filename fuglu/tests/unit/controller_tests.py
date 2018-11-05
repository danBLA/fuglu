# -*- coding: UTF-8 -*-
import unittest

try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

import logging
import sys

from fuglu.core import MainController
from fuglu.shared import ScannerPlugin, DUNNO
from fuglu.logtools import logConfig


class Dummy(ScannerPlugin):
    """Dummy plugin to recreate the section=None error"""
    def __init__(self, config, section=None):
        ScannerPlugin.__init__(self, config, section)
        self.section = None
        self.requiredvars = {
            'dummy': {
                'default': 'bla',
                'description': 'blabla',
            },
            'dummy2': {
                'default': 'blabla',
                'description': 'blablablabla',
            },

        }


class Dummy2(ScannerPlugin):
    """Dummy2 plugin to recreate the section=None error"""
    def __init__(self, config, section=None):
        ScannerPlugin.__init__(self, config, section)
        self.requiredvars = {
            'dummy': {
                'default': 'bla',
                'description': 'blabla',
            },
            'dummy2': {
                'default': 'blabla',
                'description': 'blablablabla',
            },

        }

def setup_module():
    loglevel = logging.DEBUG
    root = logging.getLogger()
    root.setLevel(loglevel)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(loglevel)
    formatter = logging.Formatter('%(asctime)s - %(name)s[%(process)d] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)


class TestPropagateDefaultErrors(unittest.TestCase):

    def test_propagate_defaults(self):
        requiredvars = {
            'dummy_blockedfile': {
                'default': '/etc/fuglu/templates/dummy.tmpl',
                'description': 'Dummy template for nothing',
            },

            'senddummy': {
                'default': '1',
                'description': 'Send dummy',
            },

            'dummydir': {
                'default': '/etc/fuglu/dummy',
                'description': 'directory that contains dummy',
            },
        }

        config = RawConfigParser()

        # check for exception
        with self.assertRaises(ValueError) as e:
            MainController.propagate_defaults(requiredvars, config)

        # check exception message
        self.assertEqual(e.exception.message, "Defaultsection can not be None if it is actually used!")

    def test(self):
        # same output as lint
        # log-level is ERROR
        #logConfig._configure4screen(logging.ERROR)
        lc = logConfig(lint=True)
        lc.configure()
        root = logging.getLogger()
        root.setLevel(logging.ERROR)

        config = RawConfigParser()
        #config.read([TESTDATADIR + '/endtoendbasetest.conf'])

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', 'controller_tests.Dummy,controller_tests.Dummy2')
        config.set('main', 'prependers', '')
        config.set('main', 'appenders', '')

        # ------------------- #
        # config: performance #
        # ------------------- #
        config.add_section("performance")
        # minimum scanner threads
        config.set('performance', 'minthreads', 1)
        # maximum scanner threads
        config.set('performance', 'maxthreads', 1)
        # Method for parallelism, either 'thread' or 'process'
        config.set('performance', 'backend', 'process')

        mc = MainController(config)
        mc.propagate_core_defaults()

        mc.lint()
        self.assertEqual(1, len(mc.plugins))
