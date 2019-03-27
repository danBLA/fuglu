from unittestsetup import TESTDATADIR
import unittest
try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

from fuglu.shared import Suspect, ScannerPlugin, PrependerPlugin, AppenderPlugin, DUNNO
from fuglu.core import MainController
from fuglu.scansession import SessionHandler


class RaiseExceptionPlugin(ScannerPlugin):
    """Dummy to raise an exception"""
    def examine(self, suspect):
        raise NotImplementedError("Plugin not implemented")


class RaiseExceptionPrepender(PrependerPlugin):

    """Prepender Plugins - Plugins run before the scanners that can influence
    the list of scanners being run for a certain message"""

    def pluginlist(self, suspect, pluginlist):
        """return the modified pluginlist or None for no change"""
        raise NotImplementedError("Prepender Plugin not implemented")

    def appenderlist(self, suspect, appenderlist):
        """return the modified appenderlist or None for no change"""
        raise NotImplementedError("Prepender Plugin not implemented")


class RaiseExceptionAppender(AppenderPlugin):

    """Appender Plugins are run after the scan process (and after the re-injection if the message
    was accepted)"""

    def process(self, suspect, decision):
        raise NotImplementedError("Appender Plugin not implemented")


class ProcessingErrorsTagTest(unittest.TestCase):
    """Tests tagging messages where plugins raise exceptions"""

    def test_plugin(self):
        """Test plugin raising exception"""
        config = RawConfigParser()

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', 'sessionhandler_test.RaiseExceptionPlugin')
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
        ok = mc.load_plugins()

        suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')

        shandler = SessionHandler(None, config, mc.prependers, mc.plugins, mc.appenders, 0)
        pluglist, applist = shandler.run_prependers(suspect)

        shandler.run_plugins(suspect, pluglist)

        ptags = suspect.get_tag("processingerrors")
        self.assertEqual(['Plugin RaiseExceptionPlugin failed: Plugin not implemented'], ptags)

    def test_prepender(self):
        """Test prepender plugin raising exception"""
        config = RawConfigParser()

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', '')
        config.set('main', 'prependers', 'sessionhandler_test.RaiseExceptionPrepender')
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
        ok = mc.load_plugins()

        suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')

        shandler = SessionHandler(None, config, mc.prependers, mc.plugins, mc.appenders, 0)
        pluglist, applist = shandler.run_prependers(suspect)

        shandler.run_plugins(suspect, pluglist)

        ptags = suspect.get_tag("processingerrors")
        self.assertEqual(['Prepender RaiseExceptionPrepender failed: Prepender Plugin not implemented'], ptags)

    def test_appender(self):
        """Test appender plugin raising exception"""
        config = RawConfigParser()

        # -------------#
        # config: main #
        # -------------#
        config.add_section("main")
        config.set('main', 'plugins', '')
        config.set('main', 'prependers', '')
        config.set('main', 'appenders', 'sessionhandler_test.RaiseExceptionAppender')

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
        ok = mc.load_plugins()

        suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')

        shandler = SessionHandler(None, config, mc.prependers, mc.plugins, mc.appenders, 0)

        shandler.run_appenders(suspect, DUNNO, mc.appenders)

        ptags = suspect.get_tag("processingerrors")
        self.assertEqual(['Appender RaiseExceptionAppender failed: Appender Plugin not implemented'], ptags)
