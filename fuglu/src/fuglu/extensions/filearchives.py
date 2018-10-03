# -*- coding: UTF-8 -*- #
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# This content has been extracted from attachment.py and refactored
#
# How to use this file:
# For normal use, just import the class "Archivehandle". Check class description
# for more information how to use the class.

import sys
import zipfile
import tarfile
import re
import os.path

STATUS = "available: zip, tar"
ENABLED = True
RARFILE_AVAILABLE = 0
try:
    import rarfile
    RARFILE_AVAILABLE = 1
    STATUS += ", rar"
except (ImportError, OSError):
    pass


SEVENZIP_AVAILABLE = 0
try:
    import py7zlib # installed via pylzma library
    SEVENZIP_AVAILABLE = 1
    STATUS += ", 7z"
except (ImportError, OSError):
    pass

GZIP_AVAILABLE = 0
try:
    import gzip
    import struct
    import os.path
    GZIP_AVAILABLE = 1
    STATUS += ", gz"
except (ImportError, OSError):
    pass


#-------------#
#- Interface -#
#-------------#
class Archive_int(object):
    """
    Archive_int is the interface for the archive handle implementations
    """

    def __init__(self, filedescriptor, archivename=None):
        self._handle = None
        self._archivename = archivename
        if archivename is not None:
            try:
                self._archivename = os.path.basename(str(archivename))
            except Exception:
                pass

    def close(self):
        try:
            self._handle.close()
        except AttributeError:
            pass

    def namelist(self):
        """ Get archive file list

        Returns:
            (list) Returns a list of file paths within the archive
        """
        return []

    def filesize(self, path):
        """get extracted file size

        Args:
            path (str): is the filename in the archive as returned by namelist
        Raises:
            NotImplemented because this routine has to be implemented by classes deriving
        """
        raise NotImplemented

    def extract(self, path, archivecontentmaxsize):
        """extract a file from the archive into memory

        Args:
            path (str): is the filename in the archive as returned by namelist
            archivecontentmaxsize (int): maximum file size allowed to be extracted from archive
        Returns:
            (bytes or None) returns the file content or None if the file would be larger than the setting archivecontentmaxsize

        """
        return None

#---------------------------#
#- Archive implementations -#
#---------------------------#
# Don't forget to add new implementations to the dict "archive_impl" and "archive_avail"
# below the implementations in class Archivehandle

class Archive_zip(Archive_int):
    def __init__(self,filedescriptor,archivename=None):
        super(Archive_zip, self).__init__(filedescriptor, archivename)

        if sys.version_info < (2, 7):
            try:
                # As far as I understand this fix is needed for bytes like objects (io.BytesIO).
                # The routine will fail with AttributeError or IOError or something else for
                # other inputs. For example in the unittests, a filename is sent in which does
                # not have read/truncate/... attributes.
                filedescriptor = Archive_zip.fix_python26_zipfile_bug(filedescriptor)
            except Exception:
                pass
        self._handle = zipfile.ZipFile(filedescriptor)
        if self._archivename is None:
            try:
                self._archivename = os.path.basename(str(filedescriptor))
            except Exception:
                self._archivename = "generic.zip"

    @staticmethod
    def fix_python26_zipfile_bug(zipFileContainer):
        """

        "http://stackoverflow.com/questions/3083235/unzipping-file-results-in-badzipfile-file-is-not-a-zip-file/21996397#21996397"

        HACK: See http://bugs.python.org/issue10694
        The zip file generated is correct, but because of extra data after the 'central directory' section,
        Some version of python (and some zip applications) can't read the file. By removing the extra data,
        we ensure that all applications can read the zip without issue.
        The ZIP format: http://www.pkware.com/documents/APPNOTE/APPNOTE-6.3.0.TXT
        Finding the end of the central directory:
          http://stackoverflow.com/questions/8593904/how-to-find-the-position-of-central-directory-in-a-zip-file
          http://stackoverflow.com/questions/20276105/why-cant-python-execute-a-zip-archive-passed-via-stdin
        This second link is only loosely related, but echos the first,
        "processing a ZIP archive often requires backwards seeking"

        Args:
            zipFileContainer (file-like object):

        Returns:
            modified zip-file bytes content

        """

        content = zipFileContainer.read()
        # reverse find: this string of bytes is the end of the zip's central
        # directory.
        pos = content.rfind('\x50\x4b\x05\x06')
        if pos > 0:
            # +20: see section V.I in 'ZIP format' link above.
            zipFileContainer.seek(pos + 20)
            zipFileContainer.truncate()
            # Zip file comment length: 0 byte length; tell zip applications to
            # stop reading.
            zipFileContainer.write('\x00\x00')
            zipFileContainer.seek(0)
        return zipFileContainer

    def namelist(self):
        """ Get archive file list

        Returns:
            (list) Returns a list of file paths within the archive
        """
        return self._handle.namelist()

    def extract(self, path, archivecontentmaxsize):
        """extract a file from the archive into memory

        Args:
            path (str): is the filename in the archive as returned by namelist
            archivecontentmaxsize (int): maximum file size allowed to be extracted from archive
        Returns:
            (bytes or None) returns the file content or None if the file would be larger than the setting archivecontentmaxsize

        """
        if archivecontentmaxsize is not None and self.filesize(path) > archivecontentmaxsize:
            return None
        return self._handle.read(path)

    def filesize(self, path):
        """get extracted file size

        Args:
            path (str): is the filename in the archive as returned by namelist
        Returns:
            (int) file size in bytes
        """
        return self._handle.getinfo(path).file_size

class Archive_rar(Archive_int):
    def __init__(self, filedescriptor, archivename=None):
        super(Archive_rar, self).__init__(filedescriptor, archivename)
        self._handle = rarfile.RarFile(filedescriptor)
        if self._archivename is None:
            try:
                self._archivename = os.path.basename(str(filedescriptor))
            except Exception:
                self._archivename = "generic.rar"

    def namelist(self):
        """ Get archive file list

        Returns:
            (list) Returns a list of file paths within the archive
        """
        return self._handle.namelist()

    def extract(self, path, archivecontentmaxsize):
        """extract a file from the archive into memory

        Args:
            path (str): is the filename in the archive as returned by namelist
            archivecontentmaxsize (int): maximum file size allowed to be extracted from archive
        Returns:
            (bytes or None) returns the file content or None if the file would be larger than the setting archivecontentmaxsize

        """
        if archivecontentmaxsize is not None and self.filesize(path) > archivecontentmaxsize:
            return None
        return self._handle.read(path)

    def filesize(self, path):
        """get extracted file size

        Args:
            path (str): is the filename in the archive as returned by namelist
        Returns:
            (int) file size in bytes
        """
        return self._handle.getinfo(path).file_size

class Archive_tar(Archive_int):
    def __init__(self, filedescriptor, archivename=None):
        super(Archive_tar, self).__init__(filedescriptor, archivename)
        try:
            self._handle = tarfile.open(fileobj=filedescriptor)
            if self._archivename is None:
                self._archivename = "generic.tar"
        except AttributeError:
            self._handle = tarfile.open(filedescriptor)
            if self._archivename is None:
                try:
                    self._archivename = os.path.basename(str(filedescriptor))
                except Exception:
                    self._archivename = "generic.tar"

    def namelist(self):
        """ Get archive file list

        Returns:
            (list) Returns a list of file paths within the archive
        """
        return self._handle.getnames()

    def extract(self, path, archivecontentmaxsize):
        """extract a file from the archive into memory

        Args:
            path (str): is the filename in the archive as returned by namelist
            archivecontentmaxsize (int): maximum file size allowed to be extracted from archive
        Returns:
            (bytes or None) returns the file content or None if the file would be larger than the setting archivecontentmaxsize

        """
        if archivecontentmaxsize is not None and self.filesize(path) > archivecontentmaxsize:
            return None

        arinfo = self._handle.getmember(path)
        if not arinfo.isfile():
            return None
        x = self._handle.extractfile(path)
        extracted = x.read()
        x.close()
        return extracted

    def filesize(self, path):
        """get extracted file size

        Args:
            path (str): is the filename in the archive as returned by namelist
        Returns:
            (int) file size in bytes
        """
        arinfo = self._handle.getmember(path)
        return arinfo.size

class Archive_7z(Archive_int):
    def __init__(self, filedescriptor, archivename=None):
        super(Archive_7z, self).__init__(filedescriptor, archivename)
        self._fdescriptor = None
        try:
            self._handle = py7zlib.Archive7z(filedescriptor)
        except AttributeError:
            self._fdescriptor = open(filedescriptor,'rb')
            self._handle = py7zlib.Archive7z(self._fdescriptor)

        if self._archivename is None:
            try:
                self._archivename = os.path.basename(str(filedescriptor))
            except Exception:
                self._archivename = "generic.7z"

    def namelist(self):
        """ Get archive file list

        Returns:
            (list) Returns a list of file paths within the archive
        """
        return self._handle.getnames()


    def extract(self, path, archivecontentmaxsize):
        if archivecontentmaxsize is not None and self.filesize(path) > archivecontentmaxsize:
            return None
        arinfo = self._handle.getmember(path)
        return arinfo.read()

    def filesize(self, path):
        """get extracted file size

        Args:
            path (str): is the filename in the archive as returned by namelist
        Returns:
            (int) file size in bytes
        """
        arinfo = self._handle.getmember(path)
        return arinfo.size

    def close(self):
        """
        Close handle
        """
        super(Archive_7z, self).close()
        if self._fdescriptor is not None:
            try:
                self._fdescriptor.close()
            except Exception:
                pass
        self._fdescriptor = None

class Archive_gz(Archive_int):
    def __init__(self, filedescriptor, archivename=None):
        super(Archive_gz, self).__init__(filedescriptor, archivename)
        self._filesize = None
        if sys.version_info > (3,):
            # --
            # Python 3 gzip.open handles both filename and file object
            # --
            self._handle = gzip.open(filedescriptor)
            if isinstance(filedescriptor,(str,bytes)):
                try:
                    self._archivename = os.path.basename(str(filedescriptor))
                except Exception:
                    self._archivename = "generic.gz"
            else:
                if self._archivename is None:
                    # if there is not archive name defined yet
                    try:
                        # eventually it is possible to get the filename from
                        # the GzipFile object
                        self._archivename = os.path.basename(self._handle.name)
                        if not self._archivename:
                            # If input is io.BytesIO then the name attribute
                            # stores an empty string, set generic
                            self._archivename = "generic.gz"
                    except:
                        # any error, set generic
                        self._archivename = "generic.gz"
        else:
            try:
                # --
                # Python 2 gzip.open expects a filename
                # --
                self._handle = gzip.open(filedescriptor)
                # Python 2
                if self._archivename is None:
                    try:
                        self._archivename = os.path.basename(str(filedescriptor))
                    except Exception:
                        self._archivename = "generic.gz"

            except TypeError as e:
                # --
                # Python 2 if input is a file object
                # --

                # if input is not a filename there's a type error
                self._handle = gzip.GzipFile(fileobj=filedescriptor,mode='rb')
                if self._archivename is None:
                    # if there is not archive name defined yet
                    try:
                        # eventually it is possible to get the filename from
                        # the GzipFile object
                        self._archivename = os.path.basename(self._handle.name)
                        if not self._archivename:
                            # If input is io.BytesIO then the name attribute
                            # stores an empty string, set generic
                            self._archivename = "generic.gz"
                    except:
                        # any error, set generic
                        self._archivename = "generic.gz"

    def namelist(self):
        """ Get archive file list

        Returns:
            (list) Returns a list of file paths within the archive
        """

        # try to create a name from the archive name
        # because a gzipped file doesn't have information about the
        # original filename
        # gzipping a file creates the archive name by appending ".gz"
        genericfilename = self._archivename

        if not genericfilename:
            genericfilename = "generic.unknown.gz"

        try:
            # get list of file extensions
            fileendinglist = Archivehandle.avail_archive_extensionlist4type['gz']
            replacedict = {"wmz": "wmf",
                           "emz": "emf"}
            for ending in fileendinglist:
                endingwithdot = "."+ending
                if genericfilename.endswith(endingwithdot):
                    if ending in replacedict:
                        genericfilename = genericfilename[:-len(ending)]+replacedict[ending]
                    else:
                        genericfilename = genericfilename[:-len(endingwithdot)]
                    break

        except Exception as e:
            print(e)
            pass
        return [genericfilename]

    def extract(self, path, archivecontentmaxsize):
        """extract a file from the archive into memory

        Args:
            path (str): is the filename in the archive as returned by namelist
            archivecontentmaxsize (int,None): maximum file size allowed to be extracted from archive
        Returns:
            (bytes or None) returns the file content or None if the file would be larger than the setting archivecontentmaxsize

        """
        if archivecontentmaxsize is not None and self.filesize(path) > archivecontentmaxsize:
            return None

        initial_position = self._handle.fileobj.tell()
        filecontent = self._handle.read()
        self._handle.fileobj.seek(initial_position)
        return filecontent

    def filesize(self, path):
        """get extracted file size

        Args:
            path (str): is the filename in the archive as returned by namelist
        Returns:
            (int) file size in bytes
        """
        try:
            return len(self.extract(path, None))
        except Exception as e:
            return 0

class Archive_tgz():
    """
    Archive combining tar and gzip extractor

    This archive combining gzip/tar extractor arises from a problem created when
    Archive_gz was introduced:  Reason are files with content "application/(x-)gzip".

    implemented_archive_ctypes = {
        ...
        '^application\/gzip': 'gz'
        '^application\/x-gzip': 'gz'
        ...}

    Ctype is checked before file ending, so a file [*].tar.gz is detected as gzip, extracted to
    [*].tar and then needs a second extraction to [*] using tar archive extractor.
    This is inconsistent with previous behavior. A solution currently passing the tests is to
    remove "^application\/gzip","^application\/x-gzip" from the implemented_archive_ctypes dict.
    Like this, the archive extractor is selected based on the file ending which detects "tar.gz"
    as tar before ".gz" (as gzip)

    A second solution is the creation of Archive_tgz which allows to keep the content type detection.
    This extractor will first try tar extractor and if this fails the gz extractor. This has the advantage
    we can keep content detection for gzip and be backward compatible.
    """
    def __init__(self, filedescriptor, archivename=None):
        # first try extract using tar
        # check if it is possible to extract filenames
        try:
            self._archive_impl = Archive_tar(filedescriptor,archivename)
            filenamelist = self._archive_impl.namelist()
        except Exception as e:
            if GZIP_AVAILABLE:
                self._archive_impl = Archive_gz(filedescriptor,archivename)
            else:
                raise e

    def __getattr__(self, name):
        """
        Delegate to implementation stored in self._archive_impl

        Args:
            name (str): name of attribute/method

        Returns:
            delegated result

        """
        return getattr(self._archive_impl, name)

#--                  --#
#- use class property -#
#--                  --#
# inspired by:
# https://stackoverflow.com/questions/128573/using-property-on-classmethods
# Working for static getter implementation in Py2 and Py3
class classproperty(property):
    def __get__(self, obj, objtype=None):
        return super(classproperty, self).__get__(objtype)

#--------------------------------------------------------------------------#
#- The pubic available factory class to produce the archive handler class -#
#--------------------------------------------------------------------------#
class Archivehandle(object):
    """
    Archivehandle is the actually the factory for the archive handle implementations.
    Besides being the factory, Archivehandle provides also dicts and lists of implemented
    and available archives based on different keys (for example file extension).

    (1) Using Archivehandle go get information about available archive handles:

    Examples:
        Archivehandle.avail('tar') # check if tar archives can be handled
        Archivehandle.avail('zip') # check if zip archives can be handled
        Archivehandle.avail_archives_list # returns a list of archives that can be handled, for example
                                          # [ "rar", "zip" ]
        Archivehandle.avail_archive_extensions_list # returns a list of archive extensions (sorted by extension length)
                                                    # for example ['tar.bz2', 'tar.gz', 'tar', 'zip', 'tgz']
        Archivehandle.avail_archive_ctypes_list # returns a list of mail content type regex expressions,
                                                # for example ['^application\\/x-tar', '^application\\/zip',
                                                               '^application\\/x-bzip2', '^application\\/x-gzip']

    (2) Use Archivehandle to create a handle to work with an archive:

    Example:
        handle = Archivehandle('zip','test.zip') # get a handle
        files = handle.namelist()        # get a list of files contained in archive
        firstfileContent = handle.extract(files[0],500000) # extract first file if smaller than 0.5 MB
        print(firstfileContent)          # print content of first file extracted
    """

    # Dict mapping implementations to archive type string
    archive_impl = {"zip": Archive_zip,
                    "rar": Archive_rar,
                    "tar": Archive_tar,
                    "7z" : Archive_7z,
                    "tgz": Archive_tgz,
                    "gz" : Archive_gz}

    # Dict storing if archive type is available
    archive_avail= {"zip": True,
                    "rar": (RARFILE_AVAILABLE > 0),
                    "tar": True,
                    "7z" : (SEVENZIP_AVAILABLE > 0),
                    "gz" : (GZIP_AVAILABLE > 0),
                    "tgz": (GZIP_AVAILABLE > 0)}


    # key: regex matching content type as returned by file magic, value: archive type
    implemented_archive_ctypes = {
        '^application\/zip': 'zip',
        '^application\/x-tar': 'tar',
        '^application\/x-gzip': 'tgz',
        '^application\/x-bzip2': 'tar',
        '^application\/gzip': 'tgz',
        '^application\/x-rar': 'rar',         # available only if RARFILE_AVAILABLE > 0
        '^application\/x-7z-compressed': '7z' # available only if SEVENZIP_AVAILABLE > 0
    }


    # key: file ending, value: archive type
    implemented_archive_extensions = {
        'zip': 'zip',
        'z': 'zip',
        'tar': 'tar',
        'tar.gz': 'tar',
        'tgz': 'tar',
        'tar.bz2': 'tar',
        'gz': 'gz',    # available only if GZIP_AVAILABLE > 0
        'emz': 'gz',    # available only if GZIP_AVAILABLE > 0
        'wmz': 'gz',    # available only if GZIP_AVAILABLE > 0
        'rar': 'rar',  # available only if RARFILE_AVAILABLE > 0
        '7z': '7z',    # available only if SEVENZIP_AVAILABLE > 0
    }

    #--
    # dicts and lists containing information about available
    # archives are setup automatically (see below in metaclass)
    #--

    # "avail_archives_list" is a list of available archives based on available implementations
    _avail_archives_list = None

    # avail_archive_ctypes_list is a list of available ctypes based on available implementations
    _avail_archive_ctypes_list = None

    # avail_archive_ctypes is a dict, set automatically based on available implementations
    # key:   regex matching content type as returned by file magic (see filetype.py)
    # value: archive type
    _avail_archive_ctypes = None

    # "avail_archive_extensions_list" is a list of available filetype extensions.
    # sorted by length, so tar.gz is checked before .gz
    _avail_archive_extensions_list = None

    # "avail_archive_extensions" dict with available archive types for file extensions
    # key: file ending
    # value: archive type
    _avail_archive_extensions = None

    # "avail_archive_extensionlist" dict with list of file extensions for given archive type
    # key: archive type
    # value: list with file endings
    _avail_archive_extensionlist4type = None

    @classproperty
    def avail_archive_extensions_list(cls):
        # first time this list has to be created based on what's available
        if cls._avail_archive_extensions_list is None:
            # sort by length, so tar.gz is checked before .gz
            newList = sorted(cls.avail_archive_extensions.keys(), key=lambda x: len(x), reverse=True)
            cls._avail_archive_extensions_list = newList
        return cls._avail_archive_extensions_list

    @classproperty
    def avail_archives_list(cls):
        # first time this list has to be created based on what's available
        if cls._avail_archives_list is None:
            tlist = []
            for atype,available in iter(Archivehandle.archive_avail.items()):
                if available:
                    tlist.append(atype)
            cls._avail_archives_list = tlist
        return cls._avail_archives_list


    @classproperty
    def avail_archive_ctypes(cls):
        # first time this dict has to be created based on what's available
        if cls._avail_archive_ctypes is None:
            newDict = {}
            for regex,atype in iter(Archivehandle.implemented_archive_ctypes.items()):
                if Archivehandle.avail(atype):
                    newDict[regex] = atype
            cls._avail_archive_ctypes = newDict

        return cls._avail_archive_ctypes

    @classproperty
    def avail_archive_ctypes_list(cls):
        # first time this list has to be created based on what's available
        if cls._avail_archive_ctypes_list is None:
            tlist = []
            for ctype,atype in iter(Archivehandle.avail_archive_ctypes.items()):
                if Archivehandle.avail(atype):
                    tlist.append(ctype)
            cls._avail_archive_ctypes_list = tlist
        return cls._avail_archive_ctypes_list

    @classproperty
    def avail_archive_extensions(cls):
        # first time this dict has to be created based on what's available
        if cls._avail_archive_extensions is None:
            newDict = {}
            for regex,atype in iter(Archivehandle.implemented_archive_extensions.items()):
                if Archivehandle.avail(atype):
                    newDict[regex] = atype
            cls._avail_archive_extensions = newDict

        return cls._avail_archive_extensions

    @classproperty
    def avail_archive_extensionlist4type(cls):
        # first time this dict has to be created based on what's available
        if cls._avail_archive_extensionlist4type is None:
            newDict = {}
            for regex,atype in iter(Archivehandle.implemented_archive_extensions.items()):
                # regex is the file extension
                # atype is the archive type
                if Archivehandle.avail(atype):
                    try:
                        # append ending to list of endings for given archive type
                        newDict[atype].append(regex)
                    except KeyError:
                        # create a new list for given archive type containg current file ending
                        newDict[atype] = [regex]
            cls._avail_archive_extensionlist4type = newDict
        return cls._avail_archive_extensionlist4type

        return cls._avail_archive_extensions
    @staticmethod
    def impl(archive_type):
        """
        Checks if archive type is implemented
        Args:
            archive_type (Str): Archive type to be checked, for example ('zip','rar','tar','7z')

        Returns:
            True if there is an implementation

        """
        return archive_type in Archivehandle.archive_impl

    @staticmethod
    def avail(archive_type):
        """
        Checks if archive type is available
        Args:
            archive_type (Str): Archive type to be checked, for example ('zip','rar','tar','7z')

        Returns:
            True if archive type is available

        """
        if not Archivehandle.impl(archive_type):
            return False
        return Archivehandle.archive_avail[archive_type]

    @staticmethod
    def archive_type_from_content_type(content_type, all_impl = False, custom_ctypes_dict = None):
        """
        Return the corresponding archive type if the content type matches a regex , None otherwise

        Args:
            content_type (str): content type string
            all_impl (bool): check all implementations, not only the ones available
            custom_ctypes_dict (dict): dict with custom mapping (key: regex matching content type as returned by file magic, value: archive type)

        Returns:
            (str or None) archive type

        """

        if content_type is None:
            return None

        archive_type = None
        if all_impl:
            ctypes2check = Archivehandle.implemented_archive_ctypes
        elif custom_ctypes_dict is not None:
            ctypes2check = custom_ctypes_dict
        else:
            ctypes2check = Archivehandle.avail_archive_ctypes

        for regex, atype in iter(ctypes2check.items()):
            if re.match(regex, content_type, re.I):
                archive_type = atype
                break

        return archive_type

    @staticmethod
    def archive_type_from_extension(att_name, all_impl = False, custom_extensions_dict = None):
        """
        Return the corresponding archive type if the extension matches regex , None otherwise

        Args:
            att_name (str): filename
            all_impl (bool): check all implementations, not only the ones available
            custom_ctypes_dict (dict): dict with custom mapping (key: regex matching content type as returned by file magic, value: archive type)

        Returns:
            (str or None) archive type

        """
        if att_name is None:
            return None

        if all_impl:
            sorted_ext_dict = Archivehandle.implemented_archive_extensions
            # sort by length, so tar.gz is checked before .gz
            sorted_ext_list = sorted(sorted_ext_dict.keys(), key=lambda x: len(x), reverse=True)
        elif custom_extensions_dict is not None:
            sorted_ext_dict = custom_extensions_dict
            # sort by length, so tar.gz is checked before .gz
            sorted_ext_list = sorted(sorted_ext_dict.keys(), key=lambda x: len(x), reverse=True)
        else:
            sorted_ext_dict = Archivehandle.avail_archive_extensions
            # this list is already sorted
            sorted_ext_list = Archivehandle.avail_archive_extensions_list

        archive_type = None
        for arext in sorted_ext_list:
            if att_name.lower().endswith('.%s' % arext):
                archive_type = sorted_ext_dict[arext]
                break
        return archive_type

    def __new__(cls,archive_type, filedescriptor, archivename=None):
        """
        Factory method that will produce and return the correct implementation depending
        on the archive type

        Args:
            archive_type (str): archive type ('zip','rar','tar','7z')
            filedescriptor (): file-like object (io.BytesIO) or path-like object (str or bytes with filename including path)
        """

        assert Archivehandle.impl(archive_type), "Archive type %s not in list of supported types: %s" % (archive_type, ",".join(Archivehandle.archive_impl.keys()))
        assert Archivehandle.avail(archive_type), "Archive type %s not in list of available types: %s" % (archive_type, ",".join(Archivehandle.avail_archives_list))
        return Archivehandle.archive_impl[archive_type](filedescriptor,archivename)

