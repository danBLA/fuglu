# -*- coding: UTF-8 -*-
import glob
import os
import sys

from setuptools import find_packages, setup

sys.path.insert(0, 'src')
FUGLU_VERSION = __import__('fuglu').get_version()


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as handler:
        return handler.read()

setup(
    name='fuglu',
    version=FUGLU_VERSION,
    description='FuGlu Mail Content Scanner',
    long_description=read('README.md'),
    author='O. Schacher',
    url='http://www.fuglu.org',
    download_url='https://gitlab.com/fumail/fuglu/-/archive/master/fuglu-master.tar.gz',
    author_email='oli@fuglu.org',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    include_package_data=True,
    data_files=[
        ('/etc/fuglu', glob.glob('conf/*.dist')),
        ('/etc/fuglu/templates', glob.glob('conf/templates/*.dist')),
        ('/etc/fuglu/rules', glob.glob('conf/rules/*.dist')),
    ],
    scripts=[
        'src/startscript/fuglu',
        'src/tools/fuglu_debug',
        'src/tools/fuglu_control',
        'src/tools/fuglu_conf',
        'src/tools/fuglu_suspectfilter',
        'src/tools/fuglu_client'
    ],
    python_requires='>=2.7',
    install_requires=[
        'packaging>=16.8',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Communications :: Email',
        'Topic :: Communications :: Email :: Filters',
        'Topic :: Communications :: Email :: Mail Transport Agents',
    ],
    license='Apache Software License',
)
