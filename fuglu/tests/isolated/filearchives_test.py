import unittestsetup
import unittest

try:
    from unittest.mock import patch
    from unittest.mock import MagicMock
except ImportError:
    from mock import patch
    from mock import MagicMock


importMockingMessage = """
NOTE:
If the module import tests fails it might be also because of the system running the tests.
Modifying sys.modules can create strange behavior and errors:

Looks like it has something to do with running tests in parallel and modifying sys.module.
In PyCharm for example this will cause other tests to fail. Luckily there is a solution:

Run the nosetest with "--with-isolation" flag. However, this flag has its own drawbacks.
- On one hand it is not possible to run the tests with the coverage flag.
- More importantly, there might be strange errors in decoding strings because codecs are unloaded (Python 2.7)

The solution is to run the tests in folder "unit" without "--with-isolation" flag and the tests
in folder "isolated" using the flag. If you see this error please check if you run with the correct
flags.
"""

class FileArchiveBase(unittest.TestCase):
    def test_tar(self):
        """Tests if 'tar' archive is correctly detected and assigned to file extension/content"""

        from fuglu.extensions.filearchives import Archivehandle

        self.assertTrue("tar" in Archivehandle.archive_avail, "'tar' archive handing has to be available!")

        #-----------#
        # extension #
        #-----------#
        extensionsHandles = ["tar","tar.gz","tar.bz2","tgz"]

        # archive extensions
        for ext in extensionsHandles:
            self.assertTrue(ext in Archivehandle.avail_archive_extensions_list,
                            "archives with ending '%s' has to be handled (%s)!"%(ext,Archivehandle.avail_archive_extensions_list))

        # archive extension assignment to 'tar'
        for ext in extensionsHandles:
            self.assertEqual("tar",Archivehandle.avail_archive_extensions[ext],
                             "'%s' file endings has to be handled by 'tar' archive"%ext)

        #---------#
        # content #
        #---------#
        contentHandles = ['^application\/x-tar','^application\/x-bzip2']

        # mail content regex as used in attachment
        for cnt in contentHandles:
            self.assertTrue(cnt in Archivehandle.avail_archive_ctypes_list,
                            "content regex '%s' has to be handled (%s)"%(cnt,Archivehandle.avail_archive_ctypes_list))

        # mail content regex assigned to 'tar' as used in attachment
        for cnt in contentHandles:
            self.assertEqual("tar",Archivehandle.avail_archive_ctypes[cnt],
                             "'%s' content regex has to be handled by 'tar' archive"%cnt)

        #'^application\/x-7z-compressed': '7z' # available only if SEVENZIP_AVAILABLE > 0

    def test_zip(self):
        """Tests if 'zip' archive is correctly detected and assigned to file extension/content"""

        from fuglu.extensions.filearchives import Archivehandle

        self.assertTrue("zip" in Archivehandle.archive_avail, "'zip' archive handling has to be available!")


        #-----------#
        # extension #
        #-----------#
        extensionsHandles = ["zip","z"]

        # archive extensions
        for ext in extensionsHandles:
            self.assertTrue(ext in Archivehandle.avail_archive_extensions_list,
                            "archives with ending '%s' has to be handled (%s)!"%(ext,Archivehandle.avail_archive_extensions_list))

        # archive extension assignment to 'zip'
        for ext in extensionsHandles:
            self.assertEqual("zip",Archivehandle.avail_archive_extensions[ext],
                             "'%s' file endings has to be handled by 'zip' archive"%ext)

        #---------#
        # content #
        #---------#
        contentHandles = ['^application\/zip']

        # mail content regex as used in attachment
        for cnt in contentHandles:
            self.assertTrue(cnt in Archivehandle.avail_archive_ctypes_list,
                            "content regex '%s' has to be handled (%s)"%(cnt,Archivehandle.avail_archive_ctypes_list))

        # mail content regex assigned to 'zip' as used in attachment
        for cnt in contentHandles:
            self.assertEqual("zip",Archivehandle.avail_archive_ctypes[cnt],
                             "'%s' content regex has to be handled by 'zip' archive"%cnt)


    def test_rar_unavailable(self):
        """Tests what happens if rar is not available"""

        # patch system modules import dict to make sure importing rarfile module fails
        with patch.dict('sys.modules',{'rarfile':None}):
            from fuglu.extensions.filearchives import Archivehandle

            self.assertFalse(Archivehandle.avail('rar'),"rar archive should be unavailable!%s"%importMockingMessage)

            #-----------#
            # extension #
            #-----------#
            extensionsHandles = ["rar"]

            # archive extensions
            for ext in extensionsHandles:
                self.assertFalse(ext in Archivehandle.avail_archive_extensions_list,
                                "archives with ending '%s' can not be handled (%s)!"%(ext,Archivehandle.avail_archive_extensions_list))


            #---------#
            # content #
            #---------#
            contentHandles = ['^application\/x-rar']

            # mail content regex as used in attachment
            for cnt in contentHandles:
                self.assertFalse(cnt in Archivehandle.avail_archive_ctypes_list,
                                "content regex '%s' can not be handled (%s)"%(cnt,Archivehandle.avail_archive_ctypes_list))


    def test_rar_available(self):
        """Tests if 'rar' archive is correctly detected and assigned to file extension/content"""

        # patch system modules import dict to make sure importing "rarfile" module is success
        # ("rarfile" is just a mock, but only successful import is needed for this test...)
        mock = MagicMock()
        with patch.dict('sys.modules',{'rarfile':mock}):
            from fuglu.extensions.filearchives import Archivehandle

            self.assertTrue(Archivehandle.avail('rar'),"rar archive should unavailable!%s"%importMockingMessage)

            #-----------#
            # extension #
            #-----------#
            extensionsHandles = ["rar"]

            # archive extensions
            for ext in extensionsHandles:
                self.assertTrue(ext in Archivehandle.avail_archive_extensions_list,
                                "archives with ending '%s' has to be handled (%s)!"%(ext,Archivehandle.avail_archive_extensions_list))

            # archive extension assignment to 'zip'
            for ext in extensionsHandles:
                self.assertEqual("rar",Archivehandle.avail_archive_extensions[ext],
                                 "'%s' file endings has to be handled by 'rar' archive"%ext)

            #---------#
            # content #
            #---------#
            contentHandles = ['^application\/x-rar']

            # mail content regex as used in attachment
            for cnt in contentHandles:
                self.assertTrue(cnt in Archivehandle.avail_archive_ctypes_list,
                                "content regex '%s' has to be handled (%s)"%(cnt,Archivehandle.avail_archive_ctypes_list))

            # mail content regex assigned to 'rar' as used in attachment
            for cnt in contentHandles:
                self.assertEqual("rar",Archivehandle.avail_archive_ctypes[cnt],
                                 "'%s' content regex has to be handled by 'rar' archive"%cnt)

    def test_7z_unavailable(self):
        """Tests what happens if 7z is not available"""

        # patch system modules import dict to make sure importing py7zlib module fails
        with patch.dict('sys.modules',{'py7zlib':None}):
            from fuglu.extensions.filearchives import Archivehandle

            self.assertFalse(Archivehandle.avail('7z'),"7z archive should be unavailable!%s"%importMockingMessage)

            #-----------#
            # extension #
            #-----------#
            extensionsHandles = ["7z"]

            # archive extensions
            for ext in extensionsHandles:
                self.assertFalse(ext in Archivehandle.avail_archive_extensions_list,
                                 "archives with ending '%s' can not be handled (%s)!"%(ext,Archivehandle.avail_archive_extensions_list))


            #---------#
            # content #
            #---------#
            contentHandles = ['^application\/x-7z-compressed']

            # mail content regex as used in attachment
            for cnt in contentHandles:
                self.assertFalse(cnt in Archivehandle.avail_archive_ctypes_list,
                                 "content regex '%s' can not be handled (%s)"%(cnt,Archivehandle.avail_archive_ctypes_list))


    def test_7z_available(self):
        """Tests if '7z' archive is correctly detected and assigned to file extension/content"""

        # patch system modules import dict to make sure importing "py7zlib" module is success
        # ("py7zlib" is just a mock, but only successful import is needed for this test...)
        mock = MagicMock()
        with patch.dict('sys.modules',{'py7zlib':mock}):
            from fuglu.extensions.filearchives import Archivehandle

            self.assertTrue(Archivehandle.avail('7z'),"7z archive should unavailable!%s"%importMockingMessage)

            #-----------#
            # extension #
            #-----------#
            extensionsHandles = ["7z"]

            # archive extensions
            for ext in extensionsHandles:
                self.assertTrue(ext in Archivehandle.avail_archive_extensions_list,
                                "archives with ending '%s' has to be handled (%s)!"%(ext,Archivehandle.avail_archive_extensions_list))

            # archive extension assignment to '7z'
            for ext in extensionsHandles:
                self.assertEqual("7z",Archivehandle.avail_archive_extensions[ext],
                                 "'%s' file endings has to be handled by '7z' archive"%ext)

            #---------#
            # content #
            #---------#
            contentHandles = ['^application\/x-7z-compressed']

            # mail content regex as used in attachment
            for cnt in contentHandles:
                self.assertTrue(cnt in Archivehandle.avail_archive_ctypes_list,
                                "content regex '%s' has to be handled (%s)"%(cnt,Archivehandle.avail_archive_ctypes_list))

            # mail content regex assigned to 'rar' as used in attachment
            for cnt in contentHandles:
                self.assertEqual("7z",Archivehandle.avail_archive_ctypes[cnt],
                                 "'%s' content regex has to be handled by 'rar' archive"%cnt)
