# -*- coding: UTF-8 -*-
import unittest
from configparser import RawConfigParser
import logging
import sys

from fuglu.core import MainController
from fuglu.shared import ScannerPlugin, DUNNO
from fuglu.logtools import logConfig
from fuglu.debug import ControlSession


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


        try:
            # Py2
            message = e.exception.message
        except AttributeError:
            # Py3
            message = e.exception.args[0]

        # check exception message
        self.assertEqual(message, "Defaultsection can not be None if it is actually used!")

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

class TestControlSession(unittest.TestCase):
    """Test filter functions, stick to lowercase for testing because that's the normal use case"""
    def test_contain1(self):
        """Single "must_contain"-keyword is contained -> True"""
        teststring = "blablahelloblabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=[],
                                       must_startwith=[], dont_contain=[], must_contain=["hello"])
        self.assertTrue(f(teststring))

    def test_contain2(self):
        """One of two "must_contain"-keywords is contained -> True"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=[],
                                       must_startwith=[], dont_contain=[], must_contain=["nothello", "world"])
        self.assertTrue(f(teststring))

    def test_contain_notfound(self):
        """None of two "must_contain"-keywords is contained -> False"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=[],
                                       must_startwith=[], dont_contain=[], must_contain=["nothello", "notworld"])
        self.assertFalse(f(teststring))

    def test_dont_contain(self):
        """None of "dont_contain"-keywords found -> True"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=[],
                                       must_startwith=[], dont_contain=["nothello", "notworld"], must_contain=[])
        self.assertTrue(f(teststring))

    def test_dont_contain_butfound(self):
        """One of "dont_contain"-keywords found -> False"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=[],
                                       must_startwith=[], dont_contain=["hello", "notworld"], must_contain=[])
        self.assertFalse(f(teststring))

    def test_must_startwith_found_first(self):
        """Line starts with first argument "must_startwith"-keyword -> True"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=[],
                                       must_startwith=["bla", "xxxxx"], dont_contain=[], must_contain=[])
        self.assertTrue(f(teststring))

    def test_must_startwith_found_second(self):
        """Line starts with second argument "must_startwith"-keyword -> True"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=[],
                                       must_startwith=["xxxxx", "bla"], dont_contain=[], must_contain=[])
        self.assertTrue(f(teststring))

    def test_dont_startwith_found_first(self):
        """Line starts with first argument "dont_startwith"-keyword -> False"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=["bla", "xxxxx"],
                                       must_startwith=[], dont_contain=[], must_contain=[])
        self.assertFalse(f(teststring))

    def test_dont_startwith_found_second(self):
        """Line starts with second argument "dont_startwith"-keyword -> False"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=["xxxxx", "bla"],
                                       must_startwith=[], dont_contain=[], must_contain=[])
        self.assertFalse(f(teststring))

    def test_startwith_double_found(self):
        """Matches both "dont_startwith" and "must_startwith" keywords, dont has more weight -> False"""
        teststring = "blabla helloworld blabla"
        f = ControlSession.buildfilter(input_to_string=str, dont_startwith=["xxxxx", "bla"],
                                       must_startwith=["xxxxx", "bla"], dont_contain=[], must_contain=[])
        self.assertFalse(f(teststring))
