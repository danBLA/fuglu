# -*- coding: utf-8 -*-
#   Copyright 2009-2018 Fumail Project
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

from fuglu.shared import ScannerPlugin, DUNNO
import time
import os


class DelayPlugin(ScannerPlugin):

    """Sleep for a given time (debugging)"""

    min_logfrequency = 1e-4
    min_delay        = 1e-6
    def __init__(self, config, section=None):
        ScannerPlugin.__init__(self, config, section)
        self.logger = self._logger()
        try:
            self.delay = config.getfloat(self.section,"delay",)
        except Exception as e:
            self.delay = DelayPlugin.min_delay
            self.logger.debug("No config, setting delay to: %f" % self.delay)

        try:
            self.logfrequency = config.getfloat(self.section,"logfrequency")
        except Exception:
            self.logfrequency = self.delay
            self.logger.debug("No config, setting frequency to: %f" % self.delay)

        self.delay = max(self.delay,DelayPlugin.min_delay)

        self.logfrequency = max(self.logfrequency,DelayPlugin.min_logfrequency)
        self.logfrequency = min(self.logfrequency,self.delay)

        if self.delay > 0:
            self.logger.info("%s: delay = %f, logfrequency = %f" % (os.getpid(),self.delay,self.logfrequency))
        else:
            self.logger.info("%s: delay = %f, logfrequ= %f" % (os.getpid(),self.delay,self.logfrequency))

    def __str__(self):
        return "Delay Message by %f" % self.delay

    def examine(self, suspect):
        delay = self.delay
        outfreq = self.logfrequency

        sumtime = 0.0
        while sumtime < delay:
            remaining = max(delay - sumtime,0.0)
            waitfor = min(outfreq, remaining)
            self.logger.debug("%s: Still waiting (passed: %f, remaining: %f)" % (os.getpid(), sumtime, remaining))
            time.sleep(waitfor)
            sumtime += waitfor
        self.logger.debug("%s: Stop waiting for %f" % (os.getpid(), self.delay))

        return DUNNO

    def lint(self):
        print("""!!! WARNING: You have enabled the DELAYplugin - This will artificially delay the processing. !!!""")
        return True
