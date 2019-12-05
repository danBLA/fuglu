# -*- coding: UTF-8 -*-
import unittest
from fuglu.plugins.script import ScriptFilter
import os
from fuglu.shared import DUNNO, REJECT, Suspect
from configparser import RawConfigParser


class ScriptfilterTestCase(unittest.TestCase):

    """Testcases for the Stub Plugin"""

    def setUp(self):
        config = RawConfigParser()

        config.add_section('ScriptFilter')
        config.set('ScriptFilter', 'scriptdir', os.path.abspath(
            os.path.dirname(__file__) + '/testdata/scriptfilter'))

        self.candidate = ScriptFilter(config)

    def test_script_stop(self):
        suspect = Suspect(
            'sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')

        # we expect to find one test script
        self.assertTrue(len(self.candidate.get_scripts()) == 1)
        action, message = self.candidate.examine(suspect)
        self.assertEqual(action, REJECT)
        self.assertEqual(message, 'rejected')

    def test_script_normalexit(self):
        suspect = Suspect(
            'sender@unittests2.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')

        # we expect to find one test script
        self.assertTrue(len(self.candidate.get_scripts()) == 1)
        action, message = self.candidate.examine(suspect)
        self.assertEqual(action, DUNNO)
        self.assertEqual(message, 'accepted')
