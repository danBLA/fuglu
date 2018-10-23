# -*- coding: UTF-8 -*-
from unittestsetup import TESTDATADIR
from fuglu.stringencode import force_uString, force_bString, EncodingTrialError, CHARDET_AVAILABLE, ForceUStringError
from fuglu.shared import Suspect
import unittest
import sys
import os
import logging

if sys.version_info > (3,):
    # Python 3 and larger
    # the basic "str" type is unicode
    ustringtype = str
    bytestype = bytes
else:
    # Python 2.x
    # the basic "str" type is bytes, unicode
    # has its own type "unicode"
    ustringtype = unicode
    bytestype = str  # which is equal to type bytes

def setup_module():
    loglevel = logging.DEBUG
    root = logging.getLogger()
    root.setLevel(loglevel)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(loglevel)
    formatter = logging.Formatter('%(asctime)s - %(name)s[%(process)d] - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

class ConversionTest(unittest.TestCase):
    """Tests for string encode/decode routines from stringencode module"""

    def test_decode2unicode(self):
        """Test if strings are correctly decoded to unicode string"""
        self.assertEqual(ustringtype,type(force_uString("bla")),"After conversion, type has to be unicode")
        self.assertEqual(ustringtype,type(force_uString(u"bla")),"After conversion, type has to be unicode")
        self.assertEqual(ustringtype,type(force_uString(b"bla")),"After conversion, type has to be unicode")

        mixedlist = ["bla", u"bla", b"bla"]
        for item in force_uString(mixedlist):
            self.assertEqual(ustringtype,type(item),"After conversion, type has to be unicode")
            self.assertEqual(u"bla",item,"String has to match the test string u\"bla\"")


    def test_encode2bytes(self):
        """Test if strings are correctly encoded"""
        self.assertEqual(bytestype,type(force_bString("bla")),"After byte conversion, type has to be bytes")
        self.assertEqual(bytestype,type(force_bString(u"bla")),"After byte conversion, type has to be bytes")
        self.assertEqual(bytestype,type(force_bString(b"bla")),"After byte conversion, type has to be bytes")

        mixedlist = ["bla",u"bla",b"bla"]
        for item in force_bString(mixedlist):
            self.assertEqual(bytestype,type(item),"After byte conversion, type has to be bytes")
            self.assertEqual(b"bla",item,"String has to match the test string b\"bla\"")

    def test_nonstringinput(self):
        self.assertEqual(ustringtype,type(force_uString(1)),"After conversion, type has to be unicode")
        self.assertEqual(ustringtype,type(force_uString(1.3e-2)),"After conversion, type has to be unicode")

        class WithUnicode(object):
            def __unicode__(self):
                return u"I have unicode"
            def __str__(self):
                return "I also have str"

        class WithStr(object):
            def __str__(self):
                return "I have str"

        print(force_uString(WithUnicode()))
        print(force_uString(WithStr()))

        self.assertEqual(ustringtype,type(force_uString(WithUnicode())),"Class has __unicode__ and __str__ (Py2: __unicode__ / Py3: __str__")
        self.assertEqual(ustringtype,type(force_uString(WithStr())),"Class has __str__ (Py2/3: __str__")

        for item in force_uString([int(1), "bla", 1.3e-2]):
            self.assertEqual(ustringtype,type(item),"After conversion, type has to be unicode")

    def test_nonstringinputerror(self):
        """bad implicit unicode conversions"""

        class WithUnicode(object):
            def __unicode__(self):
                # to be correct this would have to be unicode
                return "I have ünicööde"

        class WithStr(object):
            def __str__(self):
                return u"I have ünicööde".encode("utf-8")

        class WithStrNone(object):
            def __str__(self):
                return None

        class WithUnicodeStr(object):
            def __unicode__(self):
                # to be correct this would have to be unicode
                return "I have ünicööde"
            def __str__(self):
                return u"I have ünicööde"

        class WithRepr(object):
            def __repr__(self):
                return u"I have ünicööde"

        class WithUnicodeStrRepr(object):
            def __unicode__(self):
                # to be correct this would have to be unicode
                return "I have ünicööde"

            def __str__(self):
                # to be correct this should NOT be unicode
                return u"I have ünicööde"

            def __repr__(self):
                return "I have ünicööde"

        # As long as there is one correct representation (unicode/str) it should work
        # In the two examples below the correct implementation comes from deriving from object
        out = force_uString(WithUnicode())

        with self.assertRaises(ForceUStringError, msg="Bad return type should be cached and raise"
                                                      "ForceUStringError which has a good error message"):
            out = force_uString(WithStrNone())

        if sys.version_info > (3,):
            with self.assertRaises(ForceUStringError, msg="If str returns bytes Py3 will have a problem "
                                                          "whereas str equals bytes in Py2"):
                out = force_uString(WithStr())

        if sys.version_info < (3,):
            with self.assertRaises(ForceUStringError, msg="If unicode returns a string with non-unicode "
                                                          "chars this should raise a TypeError exception"
                                                          "containing a good error message"):
                out = force_uString(WithUnicodeStr())
        else:
            out = force_uString(WithUnicodeStr())

        # if __repr__ returns a string with unicode chars it's not a problem because first
        # unicode/str are used
        out = force_uString(WithRepr())

        if sys.version_info < (3,):
            with self.assertRaises(ForceUStringError, msg="If unicode returns a string with non-unicode "
                                                          "chars this should raise a TypeError exception"
                                                          "containing a good error message"):
                out = force_uString(WithUnicodeStrRepr())
        else:
            out = force_uString(WithUnicodeStrRepr())


class TestTrialError(unittest.TestCase):
    """Test Trial & Error for finding encoding"""

    def test_trialerror(self):
        payload = b'\x1b$B|O2qD9\x1b(B\r\n'

        # This is a string where chardet typically fails.
        # >>> payload = b'\x1b$B|O2qD9\x1b(B\r\n'
        # >>> chardet.detect(payload)
        # {'confidence': 0.99, 'language': 'Japanese', 'encoding': 'ISO-2022-JP'}
        # >>> payload.decode('ISO-2022-JP')
        # Traceback(most recent call last):
        #     File "<input>", line 1, in < module >
        # UnicodeDecodeError: 'iso2022_jp' codec can 't decode bytes in position 3-4: illegal multibyte sequence

        working_encodings = EncodingTrialError.test_all(payload)
        print("%u of total %u encodings have worked without error -> %.1f" %
              (len(working_encodings), len(EncodingTrialError.all_encodings_list),
               100.*float(len(working_encodings))/float(len(EncodingTrialError.all_encodings_list))) + "%")

        try:
            self.assertGreater(len(working_encodings), 0)
        except AttributeError:
            # Python 2.6
            self.assertTrue(len(working_encodings) > 0)

        # For each encoding:
        # - it's possible to decode without error
        # - it's possible to re-encode without error
        # - the re-encoded string has to be equal the original encoded string
        for enc in working_encodings:
            decoded = payload.decode(enc, "strict")
            reencoded = decoded.encode(enc, "strict")
            self.assertEqual(payload, reencoded)

    def test_forceustring(self):
        payload = b'\x1b$B|O2qD9\x1b(B\r\n'

        force_uString(payload, encodingGuess='ISO-2022-JP')
