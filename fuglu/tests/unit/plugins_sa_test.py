from unittestsetup import TESTDATADIR

import unittest
import tempfile
import os

try:
    from unittest.mock import patch
    from unittest.mock import MagicMock
except ImportError:
    from mock import patch
    from mock import MagicMock

try:
    from configparser import RawConfigParser
except ImportError:
    from ConfigParser import RawConfigParser

from fuglu.plugins.sa import SAPlugin
from fuglu.shared import Suspect, DUNNO
from email.message import Message
from email.header import Header


class SATestCase(unittest.TestCase):

    def setUp(self):
        config = RawConfigParser()
        config.add_section('main')
        config.set('main', 'disablebounces', '1')
        config.set('main', 'nobouncefile', '')
        config.add_section('SAPlugin')
        # current tests don't need config options, add them here later if
        # necessary
        self.config = config

    def tearDown(self):
        pass

    def test_extract_spamstatus(self):
        """Test if the spam status header gets extracted correctly"""

        candidate = SAPlugin(self.config)
        suspect = Suspect(
            'sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')
        headername = 'X-Spam-Status'
        headertests = [  # tuple header content, expected spamstatus, expected spam score
            ('YES', True, None),  # _YESNOCAPS_
            ('NO', False, None),  # _YESNOCAPS_
            (' Yes, score=13.37', True, 13.37),  # _YESNO_, score=_SCORE_
            (' No, score=-2.826', False, -2.826),  # _YESNO_, score=_SCORE_
            # with test names, bug #24
            ("No, score=1.9 required=8.0 tests=BAYES_00,FROM_EQ_TO,TVD_SPACE_RATIO,TVD_SPACE_RATIO_MINFP autolearn=no autolearn_force=no version=3.4.0",
             False, 1.9),
        ]

        for headercontent, expectedspamstatus, expectedscore in headertests:
            msgrep = Message()
            msgrep[headername] = Header(headercontent).encode()
            spamstatus, score, report = candidate._extract_spamstatus(
                msgrep, headername, suspect)
            self.assertEqual(spamstatus, expectedspamstatus, "spamstatus should be %s from %s" % (
                expectedspamstatus, headercontent))
            self.assertEqual(score, expectedscore, "spamscore should be %s from %s" % (
                expectedscore, headercontent))

    def test_extract_spamstatus_fail(self):
        """Test correct return if extracting spamstatus fails because of missing header"""
        candidate = SAPlugin(self.config)
        suspect = Suspect(
            'sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')
        headername = 'X-Spam-Status'
        msgrep = Message()
        spamstatus, score, report = candidate._extract_spamstatus(msgrep, headername, suspect)


class SAPluginTestCase(unittest.TestCase):

    """Testcases for the Plugin"""

    def setUp(self):
        """Tests a message that is stripped and forwared in a modified way"""

        config = RawConfigParser()
        config.add_section('main')
        config.set('main', 'prependaddedheaders', 'X-Fuglu-')

        config.add_section('SAPlugin')
        config.set('SAPlugin', 'host', '127.0.0.1')
        config.set('SAPlugin', 'port', '783')
        config.set('SAPlugin', 'timeout', '5')
        config.set('SAPlugin', 'retries', '3')
        config.set('SAPlugin', 'peruserconfig', '0')
        config.set('SAPlugin', 'maxsize', '50')
        config.set('SAPlugin', 'spamheader', 'X-Spam-Status')
        config.set('SAPlugin', 'lowspamaction', 'DUNNO')
        config.set('SAPlugin', 'highspamaction', 'REJECT')
        config.set('SAPlugin', 'problemaction', 'DEFER')
        config.set('SAPlugin', 'highspamlevel', '15')
        config.set('SAPlugin', 'forwardoriginal', 'False')
        config.set('SAPlugin', 'scanoriginal', 'False')
        config.set('SAPlugin', 'rejectmessage', '')
        config.set('SAPlugin', 'strip_oversize', '1')
        config.set('SAPlugin', 'spamheader_prepend', 'X-Spam-')

        saplug = SAPlugin(config)
        saplug.safilter = MagicMock()
        saplug.safilter.return_value = b'Received: from localhost by unknown\n' \
                                       b'\twith SpamAssassin (version 3.4.2);\n' \
                                       b'\tWed, 28 Nov 2018 08:43:56 +0100\n' \
                                       b'X-Spam-Checker-Version: SpamAssassin 3.4.2 (2018-09-13) on unknown\n' \
                                       b'X-Spam-Flag: YES\n' \
                                       b'X-Spam-Level: *********\n' \
                                       b'X-Spam-Status: Yes, score=9.8 required=5.0 tests=EMPTY_MESSAGE,\n' \
                                       b'\tMIME_HEADER_CTYPE_ONLY,MISSING_DATE,MISSING_FROM,MISSING_HEADERS,\n' \
                                       b'\tMISSING_MID,MISSING_SUBJECT,NO_HEADERS_MESSAGE,NO_RECEIVED,NO_RELAYS\n' \
                                       b'\tautolearn=no autolearn_force=no version=3.4.2\n' \
                                       b'MIME-Version: 1.0\n' \
                                       b'Content-Type: multipart/mixed; boundary="----------=_5BFE473C.76E9108C"\n' \
                                       b'\n' \
                                       b'This is a multi-part message in MIME format.\n' \
                                       b'\n' \
                                       b'------------=_5BFE473C.76E9108C\n' \
                                       b'Content-Type: text/plain; charset=iso-8859-1\n' \
                                       b'Content-Disposition: inline\n' \
                                       b'Content-Transfer-Encoding: 8bit\n' \
                                       b'\n' \
                                       b'Spam detection software, running on the system "unknown",\n' \
                                       b'has identified this incoming email as possible spam.  The original\n' \
                                       b'message has been attached to this so you can view it or label\n' \
                                       b'similar future email.  If you have any questions, see\n' \
                                       b'@@CONTACT_ADDRESS@@ for details.\n' \
                                       b'\n' \
                                       b'Content preview:  \n' \
                                       b'\n' \
                                       b'Content analysis details:   (9.8 points, 5.0 required)\n' \
                                       b'\n' \
                                       b' pts rule name              description\n' \
                                       b'---- ---------------------- --------------------------------------------------\n' \
                                       b'-0.0 NO_RELAYS              Informational: message was not relayed via SMTP\n' \
                                       b' 1.2 MISSING_HEADERS        Missing To: header\n' \
                                       b' 1.4 MISSING_DATE           Missing Date: header\n' \
                                       b' 2.0 MIME_HEADER_CTYPE_ONLY \'Content-Type\' found without required\n' \
                                       b'                            MIME headers\n' \
                                       b' 1.8 MISSING_SUBJECT        Missing Subject: header\n' \
                                       b' 1.0 MISSING_FROM           Missing From: header\n' \
                                       b' 0.1 MISSING_MID            Missing Message-Id: header\n' \
                                       b' 2.3 EMPTY_MESSAGE          Message appears to have no textual parts and no\n' \
                                       b'                            Subject: text\n' \
                                       b'-0.0 NO_RECEIVED            Informational: message has no Received headers\n' \
                                       b' 0.0 NO_HEADERS_MESSAGE     Message appears to be missing most RFC-822\n' \
                                       b'                            headers\n' \
                                       b'\n' \
                                       b'The original message was not completely plain text, and may be unsafe to\n' \
                                       b'open with some email clients; in particular, it may contain a virus,\n' \
                                       b'or confirm that your address can receive spam.  If you wish to view\n' \
                                       b'it, it may be safer to save it to a file and open it with an editor.\n' \
                                       b'\n' \
                                       b'\n' \
                                       b'------------=_5BFE473C.76E9108C\n' \
                                       b'Content-Type: message/rfc822; x-spam-type=original\n' \
                                       b'Content-Description: original message before SpamAssassin\n' \
                                       b'Content-Disposition: attachment\n' \
                                       b'Content-Transfer-Encoding: 8bit\n' \
                                       b'\n' \
                                       b'Content-Type: multipart/mixed; boundary="========' \
                                       b'\n------------=_5BFE473C.76E9108C--\n' \
                                       b'\n'
        self.saplugin = saplug

    def test_forward_modified_stripped(self):
        suspect = Suspect('sender@unittests.fuglu.org','recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        action, message = self.saplugin.examine(suspect)
        self.assertEqual(DUNNO, action)
        try:
            self.assertIsNotNone(suspect.get_tag('SAPlugin.report'))
        except AttributeError:
            # Python 2.6
            self.assertTrue(suspect.get_tag('SAPlugin.report') is not None)


    def test_contenttype_problem_message(self):
        """Should just not crash. There was bug in handling such messages."""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org',
                          TESTDATADIR + '/contentproblem.eml')
        action, message = self.saplugin.examine(suspect)
