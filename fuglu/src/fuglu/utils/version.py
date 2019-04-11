# -*- coding: utf-8 -*-
#   Copyright 2009-2019 Fumail Project
#
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
#
#
import datetime
import os
import subprocess


VERSION_ALPHA = 'alpha'
VERSION_BETA = 'beta'
VERSION_RC = 'rc'
VERSION_FINAL = 'final'


def get_version(version=None):
    """Return a PEP 440-compliant version number from VERSION."""
    version = get_complete_version(version)

    # Now build the two parts of the version number:
    # main = X.Y.Z
    # sub = .devN - for pre-alpha releases
    #     | {a|b|rc}N - for alpha, beta, and rc releases

    main = get_main_version(version)
    
    sub = ''
    if version[3] in [VERSION_ALPHA, VERSION_BETA]:
        git_changeset = get_git_changeset()
        if git_changeset:
            sub = '.dev%s' % git_changeset

    elif version[3] != VERSION_FINAL:
        mapping = {VERSION_ALPHA: 'a', VERSION_BETA: 'b', VERSION_RC: 'rc'}
        sub = mapping[version[3]] + str(version[4])
    
    return main + sub


def get_main_version(version=None):
    """Return main version (X.Y.Z) from VERSION."""
    version = get_complete_version(version)
    return '.'.join(str(x) for x in version[:3])


def get_complete_version(version=None):
    """
    Return a tuple of the fuglu version. If version argument is non-empty,
    check for correctness of the tuple provided.
    """
    if version is None:
        from fuglu import FUGLU_VERSION as version
    else:
        assert len(version) == 5
        assert version[3] in (VERSION_ALPHA, VERSION_BETA, VERSION_RC, VERSION_FINAL)

    return version


def get_docs_version(version=None):
    version = get_complete_version(version)
    if version[3] != VERSION_FINAL:
        return 'dev'
    else:
        return '%d.%d' % version[:2]


def get_git_changeset():
    """Return a numeric identifier of the latest git changeset.

    The result is the UTC timestamp of the changeset in YYYYMMDDHHMMSS format.
    This value isn't guaranteed to be unique, but collisions are very unlikely,
    so it's sufficient for generating the development version numbers.
    """
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        timestamp = subprocess.check_output(
            'git log --pretty=format:%ct --quiet -1 HEAD',
            shell=True, cwd=repo_dir, universal_newlines=True,
        )
    except subprocess.CalledProcessError:
        return None

    try:
        timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))
    except ValueError:
        return None
    return timestamp.strftime('%Y%m%d%H%M%S')
