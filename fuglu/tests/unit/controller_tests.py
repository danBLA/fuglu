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


class Dummy3(ScannerPlugin):
    """Dummy3 plugin which has a requiredvar without default"""
    def __init__(self, config, section=None):
        ScannerPlugin.__init__(self, config, section)
        self.requiredvars = {
            'dummy': {
                'default': 'bla',
                'description': 'blabla',
            },
            'dummy2': {
                'description': 'this var has to be defined',
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
    """Test config propagation and linting for MainController and Plugins"""

    def test_lint_noproblems(self):
        """Test lint where config is all fine"""
        lc = logConfig(lint=True)
        lc.configure()
        root = logging.getLogger()
        root.setLevel(logging.ERROR)

        config = RawConfigParser()

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', 'controller_tests.Dummy2')
        config.set('main', 'prependers', '')
        config.set('main', 'appenders', '')

        mc = MainController(config)
        errors = mc.lint()
        self.assertEqual(0, errors)

    def test_lint_nodefault(self):
        """Plugin with missing required var without default"""
        lc = logConfig(lint=True)
        lc.configure()
        root = logging.getLogger()
        root.setLevel(logging.ERROR)

        config = RawConfigParser()

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', 'controller_tests.Dummy3')
        config.set('main', 'prependers', '')
        config.set('main', 'appenders', '')

        mc = MainController(config)
        errors = mc.lint()
        self.assertEqual(1, errors)

    def test_lint_nodefault_butset(self):
        """Plugin where missing required var without default is set"""
        lc = logConfig(lint=True)
        lc.configure()
        root = logging.getLogger()
        root.setLevel(logging.ERROR)

        config = RawConfigParser()

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', 'controller_tests.Dummy3')
        config.set('main', 'prependers', '')
        config.set('main', 'appenders', '')

        config.add_section("Dummy3")
        config.set('Dummy3', 'dummy2', 'explicit value')

        mc = MainController(config)
        errors = mc.lint()
        self.assertEqual(0, errors)

    def test_lint_nosec(self):
        """Test if plugin with section=None triggers error by default"""
        lc = logConfig(lint=True)
        lc.configure()
        root = logging.getLogger()
        root.setLevel(logging.ERROR)

        config = RawConfigParser()

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', 'controller_tests.Dummy,controller_tests.Dummy2')
        config.set('main', 'prependers', '')
        config.set('main', 'appenders', '')

        mc = MainController(config)
        errors = mc.lint()
        self.assertEqual(1, errors)

    def test_alldefault_lint(self):
        """Test lint command for default config"""
        lc = logConfig(lint=True)
        lc.configure()
        root = logging.getLogger()
        root.setLevel(logging.ERROR)

        config = RawConfigParser()

        mc = MainController(config)
        errors = mc.lint()
        self.assertEqual(2, errors, "With all default, 1 error for SAPlugin and 1 error for ClamavPlugin are expected")


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
