# -*- coding: UTF-8 -*- #
import unittest
import unittestsetup
from fuglu.stringencode import force_uString, force_bString
from os.path import join, exists
import sys
from io import BytesIO

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

        # --
        # use filename
        # --
        handle = Archivehandle('zip',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        # --
        # use file descriptor
        # --
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

        # --
        # use filename
        # --
        handle = Archivehandle('rar',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        # --
        # use file descriptor
        # --
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

        fsystemencoding = sys.getfilesystemencoding().lower()
        if not fsystemencoding == "utf-8":
            # with gitlab-runner (at least locally) the filesystem is "ascii" and this test
            # fails because of the filename being unicode
            print("==================================================================")
            print("== WARNING                                                      ==")
            print("== Skipping rar extract unicode test because the file           ==")
            print("== is not unicode: %s                                           ==" % fsystemencoding)
            print("== Test will only run if:                                       ==")
            print("== \"python -c \"import sys; print(sys.getfilesystemencoding())\"\" ==")
            print("== returns utf-8                                                ==")
            print("==================================================================")
            return

        archive_filename = force_uString(join(unittestsetup.TESTDATADIR, u"One Földer.rar"))

        # --
        # use filename
        # --
        print(u"filesystem encoding support: %s" % sys.getfilesystemencoding())
        print(u"file %s exists: %s" % (archive_filename, exists(archive_filename)))
        handle = Archivehandle('rar', archive_filename)

        archive_flist = handle.namelist()
        self.assertEqual([u"One Földer/Hélö Wörld.txt", u"One Földer"], archive_flist)

        extracted = handle.extract(archive_flist[0], None)
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
            handle.extract(archive_flist[0], None)
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
            handle.extract(archive_flist[0], None)
        handle.close()

    def test_tarfileextract_gz(self):
        """Test rar file extraction"""
        from fuglu.extensions.filearchives import Archivehandle

        # --
        # use filename
        # --
        archive_filename = join(unittestsetup.TESTDATADIR,"test.tar.gz")

        handle = Archivehandle('tar',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        # --
        # use file descriptor
        # --
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

        # --
        # use filename
        # --
        archive_filename = join(unittestsetup.TESTDATADIR,"test.txt.gz")

        handle = Archivehandle('gz',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        # --
        # use file descriptor
        # --
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

        # --
        # use filename
        # --
        archive_filename = join(unittestsetup.TESTDATADIR,"test.tar.bz2")

        handle = Archivehandle('tar',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

        # --
        # use file descriptor
        # --
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('tar',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()

    def test_7zextract_filename(self):
        """Test 7z file extraction from filename"""
        from fuglu.extensions.filearchives import Archivehandle, SEVENZIP_AVAILABLE

        if not SEVENZIP_AVAILABLE > 0:
            print("=============================================================")
            print("== WARNING                                                 ==")
            print("== Skipping 7z extract test since library is not installed ==")
            print("=============================================================")
            return

        # --
        # use filename
        # --
        archive_filename = join(unittestsetup.TESTDATADIR,"test.7z")

        handle = Archivehandle('7z',archive_filename)
        self.runArchiveChecks(handle)
        handle.close()

    def test_7zextract_fileobject(self):
        """Test 7z file extraction from object"""
        from fuglu.extensions.filearchives import Archivehandle, SEVENZIP_AVAILABLE

        if not SEVENZIP_AVAILABLE > 0:
            print("=============================================================")
            print("== WARNING                                                 ==")
            print("== Skipping 7z extract test since library is not installed ==")
            print("=============================================================")
            return

        archive_filename = join(unittestsetup.TESTDATADIR,"test.7z")

        # --
        # use file descriptor
        # --
        f = open(archive_filename,'rb')
        try:
            handle = Archivehandle('7z',f)
            self.runArchiveChecks(handle)
            handle.close()
        finally:
            f.close()

    def test_7zextract_bytesio(self):
        """Test 7z file extraction from object"""
        from fuglu.extensions.filearchives import Archivehandle, SEVENZIP_AVAILABLE

        if not SEVENZIP_AVAILABLE > 0:
            print("=============================================================")
            print("== WARNING                                                 ==")
            print("== Skipping 7z extract test since library is not installed ==")
            print("=============================================================")
            return

        archive_filename = join(unittestsetup.TESTDATADIR, "test.7z")

        # --
        # use BytesIO as done in attachment manager
        # --
        with open(archive_filename, 'rb') as f:
            buffer = f.read()
        buffer = BytesIO(buffer)
        print("Type of buffer sent to Archivehandler is: %s" % type(buffer))
        handle = Archivehandle('7z', buffer)

        self.runArchiveChecks(handle)
        handle.close()

    def test_7zextract_bytesio_encrypted(self):
        """Test 7z file extraction from object (encrypted)"""
        from fuglu.extensions.filearchives import Archivehandle, SEVENZIP_AVAILABLE

        if not SEVENZIP_AVAILABLE > 0:
            print("================================================")
            print("== WARNING                                    ==")
            print("== Skipping 7z bytesio encrypted extract test ==")
            print("== since library is not installed             ==")
            print("================================================")
            return

        from py7zlib import NoPasswordGivenError

        archive_filename = join(unittestsetup.TESTDATADIR, "test.p_is_secret.7z")

        # --
        # use BytesIO as done in attachment manager
        # --
        with open(archive_filename, 'rb') as f:
            buffer = f.read()
        buffer = BytesIO(buffer)
        handle = Archivehandle('7z', buffer)

        # even though the file is password protected, the filelist is not
        # so it's possible to extract the file list without an exception
        archive_flist = handle.namelist()
        self.assertEqual(["test.txt"],archive_flist)

        # it is however not possible to extract the file
        with self.assertRaises(NoPasswordGivenError):
            extracted = handle.extract(archive_flist[0], 500000)
        handle.close()

    def test_7zextract_bytesio_fullyencrypted(self):
        """Test 7z file extraction from object (encrypted including filenames)"""
        from fuglu.extensions.filearchives import Archivehandle, SEVENZIP_AVAILABLE

        if not SEVENZIP_AVAILABLE > 0:
            print("================================================")
            print("== WARNING                                    ==")
            print("== Skipping 7z bytesio encrypted extract test ==")
            print("== since library is not installed             ==")
            print("================================================")
            return

        from py7zlib import NoPasswordGivenError

        archive_filename = join(unittestsetup.TESTDATADIR, "test.enc_filenames.p_is_secret.7z")

        # --
        # use BytesIO as done in attachment manager
        # --
        with open(archive_filename, 'rb') as f:
            buffer = f.read()
        buffer = BytesIO(buffer)

        # 7z a test.enc_filenames.p_is_secret.7z -psecret -mhe test.txt
        # compresses *.txt files to archive .7 z using password "secret". It also encrypts archive headers(-mhe switch),
        # so filenames will be encrypted. This raises an exception already when creating the handle.
        with self.assertRaises(NoPasswordGivenError):
            _ = Archivehandle('7z', buffer)

