from fuglu.stringencode import force_uString, force_bString
import unittest
import sys

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
    bytestype = str # which is equal to type bytes

class ConversionTest(unittest.TestCase):
    """Tests for string encode/decode routines from stringencode module"""

    def test_decode2unicode(self):
        """Test if strings are correctly decoded to unicode string"""
        self.assertEqual(ustringtype,type(force_uString("bla")),"After conversion, type has to be unicode")
        self.assertEqual(ustringtype,type(force_uString(u"bla")),"After conversion, type has to be unicode")
        self.assertEqual(ustringtype,type(force_uString(b"bla")),"After conversion, type has to be unicode")

        mixedlist = ["bla",u"bla",b"bla"]
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