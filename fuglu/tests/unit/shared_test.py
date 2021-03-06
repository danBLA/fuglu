# -*- coding: UTF-8 -*-
from unittestsetup import TESTDATADIR
import unittest
import string
from fuglu.shared import Suspect, SuspectFilter, string_to_actioncode, actioncode_to_string, apply_template, REJECT, FileList
from fuglu.addrcheck import Addrcheck
import email
import os
import sys
import datetime
from fuglu.stringencode import force_uString, force_bString
from email.header import Header
from configparser import ConfigParser
from unittest.mock import patch

# expected return types
#
# the explicit types for Python 2 and 3 are defined
# in the test for stringencode, see "stringencode_test"
stringtype = type(force_uString("test"))
bytestype = type(force_bString("test"))


class SuspectTestCase(unittest.TestCase):

    """Test Suspect functions"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_id(self):
        """Check the length and uniqueness of the generated id"""
        s = Suspect('sender@example.com', 'recipient@example.com', '/dev/null')
        known = []
        for i in range(10000):
            suspect_id = s._generate_id()
            self.assertTrue(
                suspect_id not in known, 'duplicate id %s generated' % suspect_id)
            known.append(suspect_id)
            self.assertEqual(len(suspect_id), 32)
            for c in suspect_id:
                self.assertTrue(c in string.hexdigits)

    def test_from_to_parsing(self):
        s = Suspect('sender@example.com', 'recipient@example.com', '/dev/null')

        self.assertEqual("sender@example.com", s.from_address)
        self.assertEqual("sender", s.from_localpart)
        self.assertEqual("example.com", s.from_domain)

        self.assertEqual("recipient@example.com", s.to_address)
        self.assertEqual("recipient", s.to_localpart)
        self.assertEqual("example.com", s.to_domain)

        for sender in (None, ''):
            s = Suspect(sender, 'recipient@example.com', '/dev/null')
            self.assertEqual("", s.from_address)
            self.assertEqual("", s.from_localpart)
            self.assertEqual("", s.from_domain)

            self.assertEqual("recipient@example.com", s.to_address)
            self.assertEqual("recipient", s.to_localpart)
            self.assertEqual("example.com", s.to_domain)

    def test_from_to_local_addr(self):
        """Make sure local senders / recipients are accepted"""
        s = Suspect('bob@localhost', 'root@localhost', '/dev/null')
        self.assertEqual("bob@localhost", s.from_address)
        self.assertEqual("bob", s.from_localpart)
        self.assertEqual("localhost", s.from_domain)

        self.assertEqual("root@localhost", s.to_address)
        self.assertEqual("root", s.to_localpart)
        self.assertEqual("localhost", s.to_domain)


    def test_from_to_illegal(self):
        """Make sure invalid sender/recipient addresses raise a ValueError"""
        self.assertRaises(ValueError, Suspect, "sender@example.com", None, '/dev/null')
        self.assertRaises(ValueError, Suspect, "sender@example.com", "recipient", '/dev/null')
        self.assertRaises(ValueError, Suspect, "sender", "recipient@example.com", '/dev/null')
        self.assertRaises(ValueError, Suspect, "sender@example.net", "recipient@example.com@example.org", '/dev/null')

    def test_special_local_part(self):
        """Make sure Sender/Receiver with quoted local part are received correctly and can contain '@'"""
        Addrcheck().set("Default")
        self.assertRaises(ValueError, Suspect, "sender@example.net", "recipient@example.com@example.org", '/dev/null')

        Addrcheck().set("LazyLocalPart")
        self.assertRaises(ValueError, Suspect, '"bob@remotehost"@localhost', "'root@localhost'@remotehost", '/dev/null')

        s = Suspect('"bob@remotehost"@localhost', '"root@localhost"@remotehost', '/dev/null')
        self.assertEqual('"bob@remotehost"@localhost', s.from_address)
        self.assertEqual('"bob@remotehost"', s.from_localpart)
        self.assertEqual("localhost", s.from_domain)

        self.assertEqual('"root@localhost"@remotehost', s.to_address)
        self.assertEqual('"root@localhost"', s.to_localpart)
        self.assertEqual("remotehost", s.to_domain)

    def test_return_types(self):
        """Test main routine return types for Python 2/3 consistency"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        headerstring = suspect.get_headers()
        self.assertEqual(type(headerstring),stringtype,"Wrong return type for get_headers")

        source = suspect.get_source()
        self.assertEqual(type(source),bytestype,"Wrong return type for get_source")

        source = suspect.get_original_source()
        self.assertEqual(type(source),bytestype,"Wrong return type for get_original_source")

    def test_set_source(self):
        """Test main set_source for Python 2/3 consistency with different input types"""
        suspect = Suspect( 'sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')

        suspectorig = Suspect('sender@unittests.fuglu.org',
                              'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        test_source_binary = suspectorig.get_source()
        test_source_unicode = force_uString(test_source_binary)

        suspect.set_source(test_source_binary)
        self.assertEqual(type(suspect.get_source()),bytestype,"Wrong return type for get_source after setting binary source")
        self.assertEqual(suspect.get_source(),test_source_binary,"Binary source content has to remain the same")

        suspect.set_source(test_source_unicode)
        self.assertEqual(type(suspect.get_source()),bytestype,"Wrong return type for get_source after setting unicode source")
        self.assertEqual(suspect.get_source(),test_source_binary,"Binary source content has to remain the same as the unicode content sent in")

    def test_add_header(self):
        """Test add_header for Python 2/3 consistency with different input types"""
        suspectorig = Suspect('sender@unittests.fuglu.org',
                              'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        newheader = ("x-new-0","just a test for default string type")
        newheaderb = (b"x-new-1",b"just a test encoded strings")
        newheaderu = (u"x-new-2",u"just a test unicode strings")

        # new dummy suspect with a copy of data from helloworld
        suspect = Suspect( 'sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', '/dev/null')
        suspect.setSource(suspectorig.get_original_source())

        suspect.add_header(*newheader,immediate=True)
        suspect.add_header(*newheaderb,immediate=True)
        suspect.add_header(*newheaderu,immediate=True)

        # check headers just set
        msg = suspect.get_message_rep()
        self.assertEqual(force_uString( newheader[1]),msg["x-new-0"])
        self.assertEqual(force_uString(newheaderb[1]),msg["x-new-1"])
        self.assertEqual(force_uString(newheaderu[1]),msg["x-new-2"])

    def test_message_flatten(self):
        """Python-3.x seems to have a problem to flatten some messages"""

        # Until https://bugs.python.org/issue27321 is merged we need
        # a patched version already implementing this fix
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/contentproblem.eml')
        mailobj = suspect.get_message_rep()
        mailstr = mailobj.as_string()

    def test_message_flatten_patchneeded(self):
        """Development: check if fix is still needed!"""

        # see "test_message_flatten" test
        with patch('fuglu.shared.PatchedMessage', wraps=email.message.Message):
            suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/contentproblem.eml')
            mailobj = suspect.get_message_rep()
            with self.assertRaises(KeyError, msg="If there's no KeyError anymore change the import shared.py "
                                                 "-> PatchedMessage is not needed for versions > (%u,%u,%u)"
                                                 % (sys.version_info.major, sys.version_info.minor,
                                                    sys.version_info.micro)):
                mailstr = mailobj.as_string()

    def test_message_flatten_patchneeded2(self):
        """Development: check if fix is still needed even using EmailMessage object!"""

        # see "test_message_flatten" test
        with patch('fuglu.shared.PatchedMessage', wraps=email.message.EmailMessage):
            suspect = Suspect('sender@unittests.fuglu.org',
                              'recipient@unittests.fuglu.org', TESTDATADIR + '/contentproblem.eml')
            mailobj = suspect.get_message_rep()
            with self.assertRaises(KeyError, msg="If there's no KeyError anymore change the import shared.py "
                                                 "-> PatchedMessage is not needed for versions > (%u,%u,%u)"
                                                 % (sys.version_info.major, sys.version_info.minor,
                                                    sys.version_info.micro)):
                mailstr = mailobj.as_string()

    def test_suspect_decode_msg_header(self):
        """Test static function "decode_msg_header" of suspect"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        # check headers just set
        msg = suspect.get_message_rep()

        newheader0 = u"test direct string"
        newheader1 = u"direct string in header object"
        newheader2 = u"unicode chars: ünicödé chàrs"

        msg["x-new-0"] = newheader0
        msg["x-new-1"] = Header(newheader1).encode()
        msg["x-new-2"] = Header(newheader2, charset='utf-8').encode()

        self.assertEqual(newheader0, Suspect.decode_msg_header(msg["x-new-0"]))
        self.assertEqual(newheader1, Suspect.decode_msg_header(msg["x-new-1"]))
        self.assertEqual(newheader2, Suspect.decode_msg_header(msg["x-new-2"]))

        # check if it's possible to apply strip (should be string, so ok)

        self.assertEqual(newheader0.strip(), Suspect.decode_msg_header(msg["x-new-0"]).strip())
        self.assertEqual(newheader1.strip(), Suspect.decode_msg_header(msg["x-new-1"]).strip())
        self.assertEqual(newheader2.strip(), Suspect.decode_msg_header(msg["x-new-2"]).strip())

    def test_suspect_decode_msg_header_strip(self):
        """Test static function "decode_msg_header" of suspect with strip function applied"""

        # originates from a bug report where the return type Header did not
        # have "strip" as a member function

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        # check headers just set
        msg = suspect.get_message_rep()

        newheader0 = u"test direct string"
        newheader1 = u"direct string in header object"
        newheader2 = u"unicode chars: ünicödé chàrs"

        msg["x-new-0"] = u"   "+newheader0+u" "
        msg["x-new-1"] = Header(u"   "+newheader1+u" ").encode()
        msg["x-new-2"] = Header(u"   "+newheader2+u" ", charset='utf-8').encode()

        self.assertEqual(newheader0, Suspect.decode_msg_header(msg["x-new-0"]).strip())
        self.assertEqual(newheader1, Suspect.decode_msg_header(msg["x-new-1"]).strip())
        self.assertEqual(newheader2, Suspect.decode_msg_header(msg["x-new-2"]).strip())

        # check if it's possible to apply strip (should be string, so ok)

        self.assertEqual(newheader0.strip(), Suspect.decode_msg_header(msg["x-new-0"]).strip())
        self.assertEqual(newheader1.strip(), Suspect.decode_msg_header(msg["x-new-1"]).strip())
        self.assertEqual(newheader2.strip(), Suspect.decode_msg_header(msg["x-new-2"]).strip())

    def test_suspect_decode_msg_header(self):
        """Test static function "decode_msg_header" for message with two encodings plus an unencoded part"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        # check headers just set
        msg = suspect.get_message_rep()

        encodedheader = u"AAA; AAA: AAAA AAAAAAAAAAA AAAAAAA =?utf-8?Q?AAAAAAAA=C3=BCAAA?= " \
                        u"=?utf-8?Q?A_A=C3=BCA?= AA-AAAAAAAAA DDDD"

        expected = u"AAA; AAA: AAAA AAAAAAAAAAA AAAAAAA AAAAAAAAüAAAA AüA AA-AAAAAAAAA DDDD"

        msg["x-new-2"] = encodedheader

        self.assertEqual(expected, Suspect.decode_msg_header(msg["x-new-2"]))

    def test_suspect_decode_msg_header2(self):
        """Test static function "decode_msg_header" for header with only two characters being encoded"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        # check headers just set
        msg = suspect.get_message_rep()

        encodedheader = "aa aaaaaaaa aaaaaaa : aa aaa =?iso-8859-1?q?aa=E9aa_aaaa_aaaaa_=E0?= " \
                        "aaaa aa aaaa aaaaaa aaaaaaaaa aaaaaaa aa aaaa"

        expected = u"aa aaaaaaaa aaaaaaa : aa aaa aaéaa aaaa aaaaa à aaaa aa aaaa aaaaaa aaaaaaaaa aaaaaaa aa aaaa"

        msg["x-new-2"] = encodedheader
        out = Suspect.decode_msg_header(msg["x-new-2"])

        self.assertEqual(expected, out)

    def test_suspect_decode_msg_header_ignorechar(self):
        """By default, replace unknown characters in decode_msg_headers"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        # check headers just set
        msg = suspect.get_message_rep()

        encodedheader = "=?UTF-8?B?Y2hlY2sgdGhpcyBjaGFyOiDiiIA=?="
        expected = u"check this char: ∀"
        msg["x-new-1"] = encodedheader
        out = Suspect.decode_msg_header(msg["x-new-1"])
        self.assertEqual(expected, out, "The original case with correct encoding")

        encodedheader = "=?UTF-8?B?Y2hlY2sgdGhpcyBjaGFyOiDiiI?="
        expected = u"check this char: �"

        msg["x-new-2"] = encodedheader
        out = Suspect.decode_msg_header(msg["x-new-2"])
        self.assertEqual(expected, out, "Due to the broken encoding the corrupted char should be replaced")

    def test_multiline_from(self):
        """Test parsing of from header, encoded and split on two lines"""

        file = os.path.join(TESTDATADIR, "from_subject_2lines.eml")
        suspect = Suspect('sender@fuglu.org', 'recipient@fuglu.org', file)
        source = force_uString(suspect.get_source())
        print(source)

        # From mail header, encoded and split on two lines
        #
        # From: "=?UTF-8?B?dGhpcyBpcyBmcm9tOiA=?=
        #  =?UTF-8?B?RlVHTFU=?=" <fuglu_from@evil1.unittests.fuglu.org>

        found_mail_list = suspect.parse_from_type_header()
        self.assertEqual([(u'this is from: FUGLU', u'fuglu_from@evil1.unittests.fuglu.org')], found_mail_list)

    def test_unicode_from_encoding(self):
        """Test parsing of from header with unicode in display name"""

        file = os.path.join(TESTDATADIR, "unicode_from_to.eml")
        suspect = Suspect('sender@fuglu.org', 'recipient@fuglu.org', file)
        source = force_uString(suspect.get_source())
        print(source)

        found_mail_list = suspect.parse_from_type_header()
        self.assertEqual([(u'sänder', u'sender@unittests.fuglu.org')], found_mail_list)

    def test_unicode_to_noencoding(self):
        """Test parsing of to header with unicode in display name but no encoding"""

        file = os.path.join(TESTDATADIR, "unicode_from_to.eml")
        suspect = Suspect('sender@fuglu.org', 'recipient@fuglu.org', file)
        source = force_uString(suspect.get_source())
        print(source)

        found_mail_list = suspect.parse_from_type_header(header="To")
        print(found_mail_list)
        # display name will not be correct, but mail address should be correclty detected
        self.assertEqual(u'recipient@unittests.fuglu.org', found_mail_list[0][1])

    def test_unicode_to_noencoding_comma(self):
        """Test parsing of to header with unicode in display name but no encoding"""

        file = os.path.join(TESTDATADIR, "unicode_from_to.eml")
        suspect = Suspect('sender@fuglu.org', 'recipient@fuglu.org', file)
        source = force_uString(suspect.get_source())
        print(source)

        found_mail_list = suspect.parse_from_type_header(header="Reply-To")
        print(found_mail_list)
        # display name will not be correct, but mail address should be correctly detected
        self.assertEqual(u'recipient@unittests.fuglu.org', found_mail_list[0][1])

    def test_from_header_doublebracket(self):
        """Test extraction of a from header with address given like <<address>>"""
        # start with hello world template
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()
        # delete existing From header
        del msg["From"]
        # add new From header
        msg["From"] = "Sender <<sender@fuglu.org>>"
        suspect.set_message_rep(msg)
        sender_list = suspect.parse_from_type_header(header="From")
        self.assertEqual([("Sender", "sender@fuglu.org")], sender_list)

    def test_from_header_bad(self):
        """Don't get confused by < in display name"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()
        # delete existing From header
        del msg["From"]
        # add new From header
        msg["From"] = "Sender <noreply.abcd <sender@fuglu.org>"
        suspect.set_message_rep(msg)
        sender_list = suspect.parse_from_type_header(header="From")
        self.assertEqual([("Sender noreply.abcd", "sender@fuglu.org")], sender_list)

    def test_from_header_combine_and_multiple(self):
        """Pushing bad entries to the display part should also work with 2 addresses"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()
        # delete existing From header
        del msg["To"]
        # add new From header
        msg["To"] = "Palim <palim <sender@fuglu.org>, Sender <sender@fuglu.org"
        suspect.set_message_rep(msg)
        receiver_list = suspect.parse_from_type_header(header="To")
        self.assertEqual([('Palim palim', 'sender@fuglu.org'), ('Sender', 'sender@fuglu.org')], receiver_list)

    def test_from_header_combine_and_multiple_extended(self):
        """Pushing bad entries to the display par """
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()
        # delete existing From header
        del msg["To"]
        # add new From header
        msg["To"] = "Receiver <receiver[at]fuglu.org>, Palim <palim <sender@fuglu.org>, Sender <sender@fuglu.org"
        suspect.set_message_rep(msg)
        receiver_list = suspect.parse_from_type_header(header="To")
        self.assertEqual([('Receiver receiver at fuglu.org Palim palim', 'sender@fuglu.org'), ('Sender', 'sender@fuglu.org')], receiver_list)

    def test_empty_from_header(self):
        """Test empty from header"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()
        # delete existing From header
        del msg["From"]
        # add new From header
        msg["From"] = "Sender <>"
        suspect.set_message_rep(msg)
        sender_list = suspect.parse_from_type_header(header="From")

        # in this case there's not valid address extracted
        self.assertEqual([], sender_list)

    def test_empty_from_header_noval(self):
        """Test empty from header without validation"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()
        # delete existing From header
        del msg["From"]
        # add new From header
        msg["From"] = "Sender <>"
        suspect.set_message_rep(msg)
        sender_list = suspect.parse_from_type_header(header="From")

        # without validation we can still extract the display name and the empty address
        sender_list = suspect.parse_from_type_header(header="From", validate_mail=False)
        self.assertEqual([("Sender", "")], sender_list)

    def test_to_header_unicode_noencoding(self):
        """Test parsing of "to"-header containing a special char but no encoding"""

        file = os.path.join(TESTDATADIR, "nonascii_env_rcpt.eml")
        suspect = Suspect('sender@fuglu.org', 'recipient@fuglu.org', file)
        source = force_uString(suspect.get_source())

        found_mail = suspect.parse_from_type_header(header='to',)[0][1]
        self.assertEqual(u'a{IGNORE}aa.aaaaaa@aaaaaa.aa', found_mail[:1]+"{IGNORE}"+found_mail[2:])
        # Note the original to-header looks like:
        #
        # To: aüaa.aaaaaa@aaaaaa.aa
        #
        # which is not allowed. So the character that is extracted for "ü" seems to depend on
        # python version, so in this test it is ignored and replaced by {IGNORE}

    def test_with_comment(self):
        """Test empty from header without validation"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()
        # delete existing From header
        del msg["From"]
        # add new From header
        msg["From"] = '"AAAAAAAAAAA" <sender@fuglu.org> (BBBBBBBBBBB)'
        suspect.set_message_rep(msg)
        sender_list = suspect.parse_from_type_header(header="From")

        # without validation we can still extract the display name and the empty address
        sender_list = suspect.parse_from_type_header(header="From", validate_mail=False)
        self.assertEqual([("AAAAAAAAAAA", "sender@fuglu.org")], sender_list)

    def test_from_type_header_encoded(self):
        """Test extraction when whole header is encoded, not only displaypart"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        msg = suspect.get_message_rep()

        fromheader_raw = "Foo Bar <foo.bar@domain.invalid>"
        print("From header before encoding: %s" % fromheader_raw)
        fromheader_enc = Header(fromheader_raw, charset='utf-8', header_name="From", continuation_ws=' ').encode()
        print("From header encoded: %s" % fromheader_enc)

        # delete existing From header
        del msg["From"]
        # add new From header
        msg["From"] = fromheader_enc
        suspect.set_message_rep(msg)

        # There should be nothing found because only addresses with valid mail are reported
        receiver_list = suspect.parse_from_type_header(header="From")
        self.assertEqual(0, len(receiver_list))

        # There should be one address found with everything in displaypart
        receiver_list = suspect.parse_from_type_header(header="From", validate_mail=False)
        self.assertEqual([(fromheader_raw, '')], receiver_list)

    def test_strip_attachments(self):
        """Test is attachment is stripped and therefore message smaller"""
        suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', TESTDATADIR + '/6mbzipattachment.eml')

        source_stripped_attachments = suspect.source_stripped_attachments()
        print("Size original/stripped message: %u/%u"
              % (len(suspect.get_original_source()), len(source_stripped_attachments)))
        self.assertTrue(len(source_stripped_attachments) < len(suspect.get_source()) / 10,
                        "after stripping zip attachment, size should be less than 10% of original mail")

    def test_strip_attachments_maxsize(self):
        """Test is attachment is stripped and max size applied"""
        suspect = Suspect('sender@unittests.fuglu.org', 'recipient@unittests.fuglu.org', TESTDATADIR + '/6mbzipattachment.eml')

        source_stripped_attachments = suspect.source_stripped_attachments(maxsize=100)
        print("Size original/stripped message: %u/%u"
              % (len(suspect.get_original_source()), len(source_stripped_attachments)))
        self.assertEqual(100,len(source_stripped_attachments),
                        "after stripping zip attachment and limiting size, size should be 100")

class SuspectFilterTestCase(unittest.TestCase):

    """Test Suspectfilter"""

    def setUp(self):
        self.candidate = SuspectFilter(TESTDATADIR + '/headertest.regex')

    def tearDown(self):
        pass

    def test_sf_get_args(self):
        """Test SuspectFilter files"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        suspect.tags['testtag'] = 'testvalue'

        headermatches = self.candidate.get_args(suspect)
        self.assertTrue(
            'Sent to unittest domain!' in headermatches, "To_domain not found in headercheck")
        self.assertTrue('Envelope sender is sender@unittests.fuglu.org' in headermatches,
                        "Envelope Sender not matched in header chekc")
        self.assertTrue('Mime Version is 1.0' in headermatches,
                        "Standard header Mime Version not found")
        self.assertTrue(
            'A tag match' in headermatches, "Tag match did not work")
        self.assertTrue(
            'Globbing works' in headermatches, "header globbing failed")
        self.assertTrue(
            'body rule works' in headermatches, "decoded body rule failed")
        self.assertTrue(
            'full body rule works' in headermatches, "full body failed")
        self.assertTrue('mime rule works' in headermatches, "mime rule failed")
        self.assertFalse('this should not match in a body rule' in headermatches,
                         'decoded body rule matched raw body')

        # perl style advanced rules
        self.assertTrue('perl-style /-notation works!' in headermatches,
                        "new rule format failed: %s" % headermatches)
        self.assertTrue('perl-style recipient match' in headermatches,
                        "new rule format failed for to_domain: %s" % headermatches)
        self.assertFalse('this should not match' in headermatches,
                         "rule flag ignorecase was not detected")

        # TODO: raw body rules

    def test_sf_matches(self):
        """Test SuspectFilter extended matches"""

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        (match, info) = self.candidate.matches(suspect, extended=True)
        self.assertTrue(match, 'Match should return True')
        field, matchedvalue, arg, regex = info
        self.assertTrue(field == 'to_domain')
        self.assertTrue(matchedvalue == 'unittests.fuglu.org')
        self.assertTrue(arg == 'Sent to unittest domain!')
        self.assertTrue(regex == 'unittests\.fuglu\.org')

    def test_sf_get_field(self):
        """Test SuspectFilter field extract"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        # additional field tests
        self.assertEqual(self.candidate.get_field(
            suspect, 'clienthelo')[0], 'helo1')
        self.assertEqual(self.candidate.get_field(
            suspect, 'clientip')[0], '10.0.0.1')
        self.assertEqual(self.candidate.get_field(
            suspect, 'clienthostname')[0], 'rdns1')

        #--------------------------------#
        #- testing input & return types -#
        #--------------------------------#

        #--
        # headers
        #--
        get_field_return = self.candidate.get_field( suspect,'Received')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(4,len(get_field_return),"Number of received headers has to match the helloworld.eml example")
        for item in get_field_return:
            self.assertEqual(stringtype,type(item),"List element returned by get_field has to be unicode")

        get_field_return_u = self.candidate.get_field( suspect,u'Received')
        self.assertEqual(get_field_return,get_field_return_u,"Unicode input to get_field should not change output")

        get_field_return_b = self.candidate.get_field( suspect,b'Received')
        self.assertEqual(get_field_return,get_field_return_b,"Bytes input to get_field should not change output")

        #--
        # envelope data
        #--
        get_field_return = self.candidate.get_field( suspect, 'clienthelo')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(1,len(get_field_return),"get_field on envelope data should return a list containing only 1 element")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")

        get_field_return = self.candidate.get_field( suspect, b'clienthelo')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(1,len(get_field_return),"get_field on envelope data should return a list containing only 1 element")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")

        get_field_return = self.candidate.get_field( suspect, u'clienthelo')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(1,len(get_field_return),"get_field on envelope data should return a list containing only 1 element")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")

        #--
        # tags
        #--
        suspect.tags['testtag' ] = 'testvalue'
        suspect.tags['testtagb'] = b'testvalue'
        suspect.tags['testtagu'] = u'testvalue'

        get_field_return = self.candidate.get_field(suspect, '@testtag')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")
        self.assertEqual(force_uString(suspect.tags['testtagb']),get_field_return[0])

        get_field_return = self.candidate.get_field(suspect, '@testtagb')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")
        self.assertEqual(force_uString(suspect.tags['testtagb']),get_field_return[0])

        get_field_return = self.candidate.get_field(suspect, '@testtagu')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")
        self.assertEqual(force_uString(suspect.tags['testtagu']),get_field_return[0])

        #--
        # body rules
        #--
        get_field_return = self.candidate.get_field(suspect, 'body:raw')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(1,len(get_field_return),"get_field for body:raw should return a list containing only 1 element")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")

        get_field_returnb = self.candidate.get_field(suspect, b'body:raw')
        self.assertEqual(get_field_return,get_field_returnb,"get_field output has to be the same independent of headername input type")
        get_field_returnu = self.candidate.get_field(suspect, u'body:raw')
        self.assertEqual(get_field_return,get_field_returnu,"get_field output has to be the same independent of headername input type")

        get_field_return = self.candidate.get_field(suspect, 'body')
        self.assertEqual(list,type(get_field_return),"Return type of get_field has to be a list")
        self.assertEqual(1,len(get_field_return),"get_field for body should return a list containing only 1 element")
        self.assertEqual(stringtype,type(get_field_return[0]),"List element returned by get_field has to be unicode")

        get_field_returnb = self.candidate.get_field(suspect, b'body')
        self.assertEqual(get_field_return,get_field_returnb,"get_field output has to be the same independent of headername input type")
        get_field_returnu = self.candidate.get_field(suspect, u'body')
        self.assertEqual(get_field_return,get_field_returnu,"get_field output has to be the same independent of headername input type")

    def test_strip(self):
        html = """foo<a href="bar">bar</a><script language="JavaScript">echo('hello world');</script>baz"""
        htmlu=u"""foo<a href="bar">bar</a><script language="JavaScript">echo('hello world');</script>baz"""
        htmlb=b"""foo<a href="bar">bar</a><script language="JavaScript">echo('hello world');</script>baz"""

        declarationtest = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="de">
  <head>
    <title>greetings</title>
  </head>
  <body>
    <font color="red">well met!</font>
  </body>
</html>
"""
        # word generated empty message
        wordhtml = """<html xmlns:v=3D"urn:schemas-microsoft-com:vml"
xmlns:o=3D"urn:schemas-microsoft-com:office:office"
xmlns:w=3D"urn:schemas-microsoft-com:office:word"
xmlns:m=3D"http://schemas.microsoft.com/office/2004/12/omml"
xmlns=3D"http://www.w3.org/TR/REC-html40"><head><META
HTTP-EQUIV=3D"Content-Type" CONTENT=3D"text/html;
charset=3Dus-ascii"><meta name=3DGenerator content=3D"Microsoft Word 15
(filtered medium)"><style><!--
/* Font Definitions */
@font-face
	{font-family:"Cambria Math";
	panose-1:2 4 5 3 5 4 6 3 2 4;}
@font-face
	{font-family:Calibri;
	panose-1:2 15 5 2 2 2 4 3 2 4;}
/* Style Definitions */
p.MsoNormal, li.MsoNormal, div.MsoNormal
	{margin:0cm;
	margin-bottom:.0001pt;
	font-size:11.0pt;
	font-family:"Calibri",sans-serif;
	mso-fareast-language:EN-US;}
a:link, span.MsoHyperlink
	{mso-style-priority:99;
	color:#0563C1;
	text-decoration:underline;}
a:visited, span.MsoHyperlinkFollowed
	{mso-style-priority:99;
	color:#954F72;
	text-decoration:underline;}
span.E-MailFormatvorlage17
	{mso-style-type:personal-compose;
	font-family:"Calibri",sans-serif;
	color:windowtext;}
.MsoChpDefault
	{mso-style-type:export-only;
	font-family:"Calibri",sans-serif;
	mso-fareast-language:EN-US;}
@page WordSection1
	{size:612.0pt 792.0pt;
	margin:70.85pt 70.85pt 2.0cm 70.85pt;}
div.WordSection1
	{page:WordSection1;}
--></style><!--[if gte mso 9]><xml>
<o:shapedefaults v:ext=3D"edit" spidmax=3D"1026" />
</xml><![endif]--><!--[if gte mso 9]><xml>
<o:shapelayout v:ext=3D"edit">
<o:idmap v:ext=3D"edit" data=3D"1" />
</o:shapelayout></xml><![endif]--></head><body lang=3DDE-CH
link=3D"#0563C1" vlink=3D"#954F72"><div class=3DWordSection1><p
class=3DMsoNormal><o:p> </o:p></p></div></body></html>"""

        for use_bfs in [True, False]:
            stripped = self.candidate.strip_text(html, use_bfs=use_bfs)
            self.assertEqual(stripped, 'foobarbaz')

            docstripped = self.candidate.strip_text(
                declarationtest, use_bfs=use_bfs)
            self.assertEqual(
                docstripped.split(), ['greetings', 'well', 'met!'])

            wordhtmstripped = self.candidate.strip_text(
                wordhtml, use_bfs=use_bfs)
            self.assertEqual(wordhtmstripped.strip(), '')

        # check input type conversions and return type
        remove_tagsu = [u'script', u'style']
        remove_tagsb = [b'script', b'style']
        stripped = self.candidate.strip_text(htmlu,remove_tags=remove_tagsu)
        self.assertEqual(stringtype,type(stripped))
        self.assertEqual('foobarbaz',stripped)
        stripped = self.candidate.strip_text(htmlu,remove_tags=remove_tagsb)
        self.assertEqual(stringtype,type(stripped))
        self.assertEqual('foobarbaz',stripped)
        stripped = self.candidate.strip_text(htmlb,remove_tags=remove_tagsb)
        self.assertEqual(stringtype,type(stripped))
        self.assertEqual('foobarbaz',stripped)
        stripped = self.candidate.strip_text(htmlb,remove_tags=remove_tagsu)
        self.assertEqual(stringtype,type(stripped))
        self.assertEqual('foobarbaz',stripped)

    def test_sf_get_decoded_textparts(self):
        """Test return type for Python 2/3 consistency (list of unicode strings)"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        textpartslist = self.candidate.get_decoded_textparts(suspect)
        self.assertEqual(list,type(textpartslist),"return type has to be list of unicode strings, but it's not a list")
        self.assertEqual(1,len(textpartslist),"for given example there is one text part, therefore list size has to be 1")
        self.assertEqual(stringtype,type(textpartslist[0]),"return type has to be list of unicode strings, but list doesn't contain a unicode string")

    def test_sf_get_decoded_textparts_cache(self):
        """Test enabled (default) cache for the decoded text buffers"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        textpartslist  = self.candidate.get_decoded_textparts(suspect)
        textpartslist2 = self.candidate.get_decoded_textparts(suspect)
        self.assertEqual(id(textpartslist[0]),id(textpartslist2[0]),"with caching the same object should be returned")

    def test_sf_get_decoded_textparts_nocache(self):
        """Test disabled cache for the decoded text buffers"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')

        # disable caching for "decoded_buffer_text" property
        for obj in suspect.att_mgr.get_objectlist():
            obj.set_cachelimit("decoded_buffer_text","nocache",True)

        textpartslist  = self.candidate.get_decoded_textparts(suspect)
        textpartslist2 = self.candidate.get_decoded_textparts(suspect)
        self.assertNotEqual(id(textpartslist[0]),id(textpartslist2[0]),"with no caching there should be different objects returned")

    def test_textparts_noattachments(self):
        """Extract text parts which are not attachements"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/lorem_attached.eml')

        # no attached textparts
        textpartslist = self.candidate.get_decoded_textparts(suspect, attachment=False)
        print(textpartslist)
        # <html>\r\n
        #    <head>\r\n
        #        <meta http-equiv="content-type" content="text/html; charset=UTF-8">\r\n
        #    </head>\r\n
        #    <body text="#000000" bgcolor="#FFFFFF">\r\n
        #        <p>body text<br>\r\n
        #        </p>\r\n
        #    </body>\r\n
        # </html>\r\n
        self.assertEqual(1, len(textpartslist))
        self.assertTrue("body text<br>" in textpartslist[0])

    def test_textparts_attachments(self):
        """Extract text parts which are attachements"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/lorem_attached.eml')

        # only attached textparts
        textpartslist = self.candidate.get_decoded_textparts(suspect, attachment=True)
        print(textpartslist)
        self.assertEqual(1, len(textpartslist))
        self.assertTrue("Lorem ipsum" in textpartslist[0])

    def test_textparts_no_attachments(self):
        """Extract text parts which are not attachements"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/lorem_inline.eml')

        # no attached textparts
        textpartslist = self.candidate.get_decoded_textparts(suspect, attachment=False)
        print(textpartslist)
        self.assertEqual(2, len(textpartslist))
        self.assertTrue("body text<br>" in textpartslist[0] or "body text<br>" in textpartslist[1])
        self.assertTrue("Lorem ipsum" in textpartslist[0] or "Lorem ipsum" in textpartslist[1])

    def test_textparts_only_attachments(self):
        """Extract text parts which are attachements"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/lorem_inline.eml')

        # no attached textparts
        textpartslist = self.candidate.get_decoded_textparts(suspect, attachment=True)
        print(textpartslist)
        self.assertEqual(0, len(textpartslist))

    def test_textparts_inline(self):
        """Extract text parts which are inline. Note the difference to test_textparts_no_attachments."""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/lorem_inline.eml')

        # no attached textparts
        textpartslist = self.candidate.get_decoded_textparts(suspect, inline=True)
        print(textpartslist)
        self.assertEqual(1, len(textpartslist))
        self.assertTrue("Lorem ipsum" in textpartslist[0])


class ActionCodeTestCase(unittest.TestCase):

    def test_defaultcodes(self):
        """test actioncode<->string conversion"""
        conf = ConfigParser()
        conf.add_section('spam')
        conf.add_section('virus')
        conf.set('spam', 'defaultlowspamaction', 'REJEcT')
        conf.set('spam', 'defaulthighspamaction', 'REjECT')
        conf.set('virus', 'defaultvirusaction', 'rejeCt')
        self.assertEqual(
            string_to_actioncode('defaultlowspamaction', conf), REJECT)
        self.assertEqual(
            string_to_actioncode('defaulthighspamaction', conf), REJECT)
        self.assertEqual(
            string_to_actioncode('defaultvirusaction', conf), REJECT)
        self.assertEqual(string_to_actioncode('nonexistingstuff'), None)
        self.assertEqual(actioncode_to_string(REJECT), 'REJECT')
        self.assertEqual(
            actioncode_to_string(string_to_actioncode('discard')), 'DELETE')


class TemplateTestcase(unittest.TestCase):

    """Test Templates"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_template(self):
        """Test Basic Template function"""

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        suspect.tags['nobounce'] = True

        reason = "a three-headed monkey stole it"

        template = """Your message '${subject}' from ${from_address} to ${to_address} could not be delivered because ${reason}"""

        result = apply_template(template, suspect, dict(reason=reason))
        expected = """Your message 'Hello world!' from sender@unittests.fuglu.org to recipient@unittests.fuglu.org could not be delivered because a three-headed monkey stole it"""
        self.assertEqual(
            result, expected), "Got unexpected template result: %s" % result


    def test_tag_templates(self):
        """Test Templates with suspect tag expansion"""

        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        suspect.tags['hello'] = ['World', "is it me you're looking for"]
        suspect.tags['SAPlugin.spamscore']="13.37"

        def valfunc(data):
            if '@removeme' in data:
                del data['@removeme']
            if '@changeme' in data:
                data['@changeme']='elephant'
            return data

        today=str(datetime.date.today())
        suspect.tags['removeme']='disappearing rabbit'
        suspect.tags['changeme']='an uninteresting value'
        cases=[
            ('${subject}','Hello world!'),
            ('${@SAPlugin.spamscore}','13.37'),
            ('${blubb}',''),
            ('${@hello}','World'),
            ('${date}',today), #builtin function with same name as header: builtin should win
            ('${header:date}', 'Tue, 12 Nov 2013 01:12:11 +0200'),  # with explicit header: prefix the message header should be available
            ('The quick brown ${from_address} received on ${date} jumps over the ${@removeme}. Uh ${@changeme}', 'The quick brown sender@unittests.fuglu.org received on %s jumps over the . Uh elephant'%today),
        ]
        for c in cases:
            template,expected = c
            result = apply_template(template, suspect, valuesfunction=valfunc)
            self.assertEqual(result, expected), "Got unexpected template result: %s. Should be: %s" % (result,expected)


class ClientInfoTestCase(unittest.TestCase):

    """Test client info detection"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_parse_rcvd_header(self):
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', '/dev/null')
        self.assertEqual(suspect._parse_rcvd_header(
            "from helo1 (rdns1 [10.0.0.1])"), ('helo1', 'rdns1', '10.0.0.1'))
        self.assertEqual(suspect._parse_rcvd_header("from mx0.slc.paypal.com (mx1.slc.paypal.com [173.0.84.226])"), (
            'mx0.slc.paypal.com', 'mx1.slc.paypal.com', '173.0.84.226'))
        self.assertEqual(suspect._parse_rcvd_header("from mail1a.tilaa.nl (mail1a.tilaa.nl [IPv6:2a02:2770:6:0:21a:4aff:fea8:1328])"), (
            'mail1a.tilaa.nl', 'mail1a.tilaa.nl', '2a02:2770:6:0:21a:4aff:fea8:1328'))

    def test_client_info(self):
        """Test client info using eml file"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/helloworld.eml')
        helo, ip, revdns = suspect.client_info_from_rcvd(None, 0)
        self.assertEqual(helo, 'helo1')
        self.assertEqual(ip, '10.0.0.1')
        self.assertEqual(revdns, 'rdns1')

        helo, ip, revdns = suspect.client_info_from_rcvd(None, 1)
        self.assertEqual(helo, 'helo2')
        self.assertEqual(ip, '10.0.0.2')
        self.assertEqual(revdns, 'rdns2')

        helo, ip, revdns = suspect.client_info_from_rcvd('10\.0\.0\.2', 1)
        self.assertEqual(helo, 'helo3')
        self.assertEqual(ip, '10.0.0.3')
        self.assertEqual(revdns, 'rdns3')

    def test_utf8_received(self):
        """Test parsing received header with utf8 char"""
        suspect = Suspect('sender@unittests.fuglu.org',
                          'recipient@unittests.fuglu.org', TESTDATADIR + '/nonascii_env_rcpt.eml')
        helo, ip, revdns = suspect.client_info_from_rcvd(None, 0)
        self.assertEqual(helo, 'dcba.gfedcba.aa')
        self.assertEqual(ip, '10.0.0.1')
        self.assertEqual(revdns, 'abcd.abcdefg.aa')


class FileListTestCase(unittest.TestCase):

    def setUp(self):
        testdata = """CASE?
{whitespace}stripped ?{whitespace}
{whitespace}

{whitespace}# no comment!
""".format(whitespace='    ')
        self.filename = '/tmp/fuglufilelisttest.txt'
        open(self.filename, 'w').write(testdata)

    def tearDown(self):
        os.unlink(self.filename)

    def test_filelist(self):
        self.assertEqual(FileList(filename=self.filename, strip=True, skip_empty=True, skip_comments=True,
                                  lowercase=False, additional_filters=None).get_list(), ['CASE?', 'stripped ?'])
        self.assertEqual(FileList(filename=self.filename, strip=False, skip_empty=True, skip_comments=True,
                                  lowercase=False, additional_filters=None).get_list(), ['CASE?', '    stripped ?    ', '    '])
        self.assertEqual(FileList(filename=self.filename, strip=True, skip_empty=False, skip_comments=False,
                                  lowercase=False, additional_filters=None).get_list(), ['CASE?', 'stripped ?', '', '', '# no comment!'])
        self.assertEqual(FileList(filename=self.filename, strip=True, skip_empty=True, skip_comments=True,
                                  lowercase=True, additional_filters=None).get_list(), ['case?', 'stripped ?'])

class StaticFunctionTests(unittest.TestCase):
    """Unit tests for static functions"""

    @staticmethod
    def old_add_header_use_python_mail(content, header_name, header_value):
        msgrep = email.message_from_bytes(content)
        msgrep.add_header(header_name, header_value)
        msg = msgrep.as_bytes()
        return msg

    def test_prepend_ascii_header_to_source(self):
        """Test header with a simple us-ascii value"""

        source = b""
        expected = b'fancy-test-header: Fancy Value\r\n'
        outsource = Suspect.prepend_header_to_source("fancy-test-header", "Fancy Value", source)
        self.assertEqual(expected, outsource)

    def test_prepend_header_to_source(self):
        """Test header with a value that has to be encoded"""
        source = b""
        expected = b'fancy-test-header: =?utf-8?b?RsOkbnNpIFbDpGxqdQ==?=\r\n'
        outsource = Suspect.prepend_header_to_source("fancy-test-header", u"Fänsi Välju", source)
        self.assertEqual(expected, outsource)


    def test_header_with_python_email(self):
        """Compare result to the test method converting mail first to python email object"""
        inputfile = TESTDATADIR + '/helloworld.eml'
        msg_bstring = open(inputfile, 'rb').read()

        expected = b'fancy-test-header: =?utf-8?b?RsOkbnNpIFbDpGxqdQ==?='

        source1 = Suspect.prepend_header_to_source("fancy-test-header", u"Fänsi Välju", msg_bstring)
        source2 = StaticFunctionTests.old_add_header_use_python_mail(msg_bstring, "fancy-test-header", u"Fänsi Välju")

        self.assertIn(expected, source1)
        self.assertIn(expected, source2)

        print(source1[:20])
        print(source2[:20])

        index1 = source1.index(expected)
        index2 = source2.index(expected)
        print("position prepend: %u, position python.email: %u" % (index1, index2))

    def test_prepend_to_corrupted_mail(self):
        """Corrupted mail, still it should be possible to prepend a header"""
        inputfile = TESTDATADIR + '/new_ascii_error.eml'
        msg_bstring = open(inputfile, 'rb').read()

        expected = b'fancy-test-header: Fancy Value'

        source1 = Suspect.prepend_header_to_source("fancy-test-header", u"Fancy Value", msg_bstring)
        self.assertIn(expected, source1)
        with self.assertRaises(UnicodeEncodeError, msg="Test can be changed if newer Python "
                                                       "version don't create an exception anymore"):
            source2 = StaticFunctionTests.old_add_header_use_python_mail(msg_bstring,
                                                                         "fancy-test-header",
                                                                         u"Fancy Value")

