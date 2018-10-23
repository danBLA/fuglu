import unittest
import unittestsetup
from fuglu.stringencode import force_uString
from os.path import join

class FileArchiveHandle(unittest.TestCase):
    def runArchiveChecks(self,handle):
        archive_flist = handle.namelist()
        self.assertEqual(["test.txt"],archive_flist)

        # file should not be extracted if maximum size to extract a file is 0
        extracted = handle.extract(archive_flist[0],0)
        self.assertEqual(None,extracted)
        extracted = handle.extract(archive_flist[0],500000)
        self.assertEqual(u"This is a test\n",force_uString(extracted))

    def test_zipfileextract(self):
        """Test zip file extraction"""
        from fuglu.extensions.filearchives import Archivehandle

        archive_filename = join(unittestsetup.TESTDATADIR,"test.zip")

        #--
        # use filename
        #--
        handle = Archivehandle('zip',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        #--
        # use file descriptor
        #--
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('zip',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()

    def test_rarfileextract(self):
        """Test rar file extraction"""
        from fuglu.extensions.filearchives import Archivehandle, RARFILE_AVAILABLE

        if not RARFILE_AVAILABLE > 0:
            print("==============================================================")
            print("== WARNING                                                  ==")
            print("== Skipping rar extract test since library is not installed ==")
            print("==============================================================")
            return

        archive_filename = join(unittestsetup.TESTDATADIR,"test.rar")

        #--
        # use filename
        #--
        handle = Archivehandle('rar',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        #--
        # use file descriptor
        #--
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('rar',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()

    def test_rarfileextract_unicode(self):
        """Test rar file extraction"""
        from fuglu.extensions.filearchives import Archivehandle, RARFILE_AVAILABLE

        if not RARFILE_AVAILABLE > 0:
            print("==============================================================")
            print("== WARNING                                                  ==")
            print("== Skipping rar extract test since library is not installed ==")
            print("==============================================================")
            return

        archive_filename = join(unittestsetup.TESTDATADIR, "One Földer.rar")

        # --
        # use filename
        # --
        handle = Archivehandle('rar', archive_filename)

        archive_flist = handle.namelist()
        self.assertEqual([u"One Földer/Hélö Wörld.txt", u"One Földer"], archive_flist)

        # file should not be extracted if maximum size to extract a file is 0
        extracted = handle.extract(archive_flist[0])
        self.assertEqual(u"bla bla bla\n", force_uString(extracted))
        handle.close()

    def test_rarfileextract_unicode_password(self):
        """Test rar file extraction for encrypted (only files and not filelist) rar"""
        from fuglu.extensions.filearchives import Archivehandle, RARFILE_AVAILABLE

        if not RARFILE_AVAILABLE > 0:
            print("==============================================================")
            print("== WARNING                                                  ==")
            print("== Skipping rar extract test since library is not installed ==")
            print("==============================================================")
            return

        import rarfile

        archive_filename = join(unittestsetup.TESTDATADIR, "password.rar")

        # --
        # use filename
        # --
        handle = Archivehandle('rar', archive_filename)

        archive_flist = handle.namelist()
        self.assertEqual([u"One Földer/Hélö Wörld.txt", u"One Földer"], archive_flist)

        with self.assertRaises(rarfile.PasswordRequired):
            handle.extract(archive_flist[0])
        handle.close()

    def test_rarfileextract_unicode_password2(self):
        """Test rar file extraction for encrypted (files and filelist) rar"""
        from fuglu.extensions.filearchives import Archivehandle, RARFILE_AVAILABLE

        if not RARFILE_AVAILABLE > 0:
            print("==============================================================")
            print("== WARNING                                                  ==")
            print("== Skipping rar extract test since library is not installed ==")
            print("==============================================================")
            return

        archive_filename = join(unittestsetup.TESTDATADIR, "password2.rar")

        # --
        # use filename
        # --
        handle = Archivehandle('rar', archive_filename)

        archive_flist = handle.namelist()
        self.assertEqual([], archive_flist)
        handle.close()

    def test_rarfileextract_emptydir(self):
        """Test rar file extraction for encrypted (only files and not filelist) rar"""
        from fuglu.extensions.filearchives import Archivehandle, RARFILE_AVAILABLE

        if not RARFILE_AVAILABLE > 0:
            print("==============================================================")
            print("== WARNING                                                  ==")
            print("== Skipping rar extract test since library is not installed ==")
            print("==============================================================")
            return

        archive_filename = join(unittestsetup.TESTDATADIR, "EmptyDir.rar")

        # --
        # use filename
        # --
        handle = Archivehandle('rar', archive_filename)

        archive_flist = handle.namelist()
        self.assertEqual([u"EmptyDir"], archive_flist)

        with self.assertRaises(TypeError):
            handle.extract(archive_flist[0])
        handle.close()

    def test_tarfileextract_gz(self):
        """Test rar file extraction"""
        from fuglu.extensions.filearchives import Archivehandle

        #--
        # use filename
        #--
        archive_filename = join(unittestsetup.TESTDATADIR,"test.tar.gz")

        handle = Archivehandle('tar',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        #--
        # use file descriptor
        #--
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('tar',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()

    def test_gzipfileextract_gz(self):
        """Test gzip file extraction"""
        from fuglu.extensions.filearchives import Archivehandle

        #--
        # use filename
        #--
        archive_filename = join(unittestsetup.TESTDATADIR,"test.txt.gz")

        handle = Archivehandle('gz',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        #--
        # use file descriptor
        #--
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('gz',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()

    def test_tarfileextract_bz2(self):
        """Test rar file extraction"""
        from fuglu.extensions.filearchives import Archivehandle

        #--
        # use filename
        #--
        archive_filename = join(unittestsetup.TESTDATADIR,"test.tar.bz2")

        handle = Archivehandle('tar',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        #--
        # use file descriptor
        #--
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('tar',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()

    def test_7zextract(self):
        """Test rar file extraction"""
        from fuglu.extensions.filearchives import Archivehandle, SEVENZIP_AVAILABLE

        if not SEVENZIP_AVAILABLE > 0:
            print("=============================================================")
            print("== WARNING                                                 ==")
            print("== Skipping 7z extract test since library is not installed ==")
            print("=============================================================")
            return

        #--
        # use filename
        #--
        archive_filename = join(unittestsetup.TESTDATADIR,"test.7z")

        handle = Archivehandle('7z',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        #--
        # use file descriptor
        #--
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('7z',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()
