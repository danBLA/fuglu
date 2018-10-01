#   Copyright 2009-2018 Oli Schacher
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

from fuglu.shared import DUNNO, ACCEPT, REJECT, DEFER, DELETE, Suspect
from fuglu.debug import CrashStore
import logging
from fuglu.stats import Statskeeper, StatDelta
import sys
import traceback
import tempfile
import time
import os
import datetime

class TrackTimings(object):
    def __init__(self, enable=False, port=-1):
        """
        Constructor, setting function handles to real functions or dummies

        Args:
            enable (bool): enable/disable time tracker
            port (int): incoming port
        """
        self.timings_logger = logging.getLogger("%s.Timings" % __package__)

        # timings
        self._enabletimetracker= False
        self.enabletimetracker = enable

        self.timetracker = time.time()
        self.timings = []
        self.port = port if port is not None else -1

    @property
    def enabletimetracker(self):
        return self._enabletimetracker

    @enabletimetracker.setter
    def enabletimetracker(self, enabled):

        if not enabled:
            self._enabletimetracker = False
            self.tracktime = self._dummy_noreturn
            self.gettime = self._dummy_returnlist
            self.sumtime = self._dummy_returnzero
            self.report_timings = self._dummy_noreturn
            self.report_plugintime = self._dummy_noreturn
        else:
            self._enabletimetracker = True
            self.tracktime = self._tracktime
            self.gettime = self._gettime
            self.sumtime = self._sumtime
            self.report_timings = self._report_timings
            self.report_plugintime = self._report_plugintime
            self.timetracker = time.time()
            self.timings = []

    def _dummy_noreturn(self, *args, **kwargs):
        return

    def _dummy_returnlist(self, *args, **kwargs):
        return []

    def _dummy_returnzero(self, *args, **kwargs):
        return 0.0

    def _tracktime(self, tagname, plugin=False, prepender=False, appender=False):
        """
        Given a tag name, track and store time since last call of same function

        Args:
            tagname (str): String with tag name

        Keyword Args:
            plugin (bool): tag belongs to plugin timing (default=False)
            prepender (bool): tag belongs to prepender timing (default=False)
            appender (bool): tag belongs to appender timing (default=False)
        """
        newtime = time.time()
        difftime = newtime - self.timetracker
        self.timetracker = newtime
        self.timings.append((tagname, difftime, plugin, prepender, appender))

    def _gettime(self, plugins=None, prependers=None, appenders=None):
        """
        Get a list of timings stored (all/only plugins/exclude plugins)

        Keyword Args:
            plugins (bool or None): 'None': ignore this restriction, True: timing must have 'plugin' tag, False: timing must not have plugin tag
            prependers (bool or None): 'None': ignore this restriction, True: timing must have 'plugin' tag, False: timing must not have plugin tag
            appenders (bool or None): 'None': ignore this restriction, True: timing must have 'plugin' tag, False: timing must not have plugin tag

        Returns:
            list of tuples (name, time)

        """
        timing_list = []
        for timeitem in self.timings:
            if plugins is not None and timeitem[2] != plugins:
                continue
            if prependers is not None and timeitem[3] != prependers:
                continue
            if appenders is not None and timeitem[4] != appenders:
                continue
            timing_list.append(timeitem[:2])
        return timing_list

    def _sumtime(self, plugins=None, prependers=None, appenders=None):
        """
        Get total time spent.

        Keyword Args:
            plugins (bool or None): For 'None' return total time, True: time spent in plugins, False: time spent outside plugins
            appenders (bool or None): For 'None' return total time, True: time spent in appenders, False: time spent outside appenders
            prependers (bool or None): For 'None' return total time, True: time spent in prependers, False: time spent outside prependers

        Returns:
            float: total time spent, given restriction

        """
        puretimings = [a[1] for a in self.gettime(plugins=plugins, prependers=prependers, appenders=appenders)]
        if len(puretimings) == 0:
            return 0.0
        else:
            return reduce(lambda x, y: (x + y), puretimings)

    def _report_timings(self, suspectid):
        """
        Report all the timings collected
        Args:
            suspectid (id):  the suspect id

        """
        self.timings_logger.info('port: %u, id: %s, total: %.3f' % (self.port, suspectid, self.sumtime()))
        self.timings_logger.info('port: %u, id: %s, overhead: %.3f' % (self.port, suspectid,
                                                                       self.sumtime(plugins=False,
                                                                                    prependers=False,
                                                                                    appenders=False)))
        all_prependertimes = self.gettime(prependers=True)
        for prependertime in all_prependertimes:
            self.timings_logger.info('port: %u, id: %s, (PRE) %s: %.3f' % (self.port, suspectid, prependertime[0],
                                                                           prependertime[1]))
        all_plugintimes = self.gettime(plugins=True)
        for plugintime in all_plugintimes:
            self.timings_logger.info('port: %u, id: %s, (PLG) %s: %.3f' % (self.port, suspectid, plugintime[0],
                                                                           plugintime[1]))
        all_appendertimes = self.gettime(appenders=True)
        for appendertime in all_appendertimes:
            self.timings_logger.info('port: %u, id: %s, (APP) %s: %.3f' % (self.port, suspectid, appendertime[0],
                                                                           appendertime[1]))
        all_overheadtimes = self.gettime(plugins=False, prependers=False, appenders=False)
        for overheadtime in all_overheadtimes:
            self.timings_logger.debug('port: %u, id: %s, %s: %.3f' % (self.port, suspectid, overheadtime[0],
                                                                      overheadtime[1]))

    def _report_plugintime(self, suspectid, pluginname, end=True):
        """
        Report timings inside plugin

        Args:
            suspectid (str): the id of the suspect
            pluginname (str): plugin name

        Keyword Args:
            end (bool): if true another timing called 'end' will be created before the report
        """
        if end:
            self.tracktime('end')
        all_timings = self.gettime()
        for itime in all_timings:
            self.timings_logger.debug('port: %u, id: %s, [%s] %s: %.3f' %
                                      (self.port, suspectid, pluginname, itime[0], itime[1]))


class SessionHandler(TrackTimings):

    """thread handling one message"""

    def __init__(self, protohandler, config, prependers, plugins, appenders, port):
        TrackTimings.__init__(self, port=port)
        self.logger = logging.getLogger("fuglu.SessionHandler")
        self.action = DUNNO
        self.config = config
        self.prependers = prependers
        self.plugins = plugins
        self.appenders = appenders
        self.stats = Statskeeper()
        self.worker = None
        self.message = None
        self.protohandler = protohandler

        try:
            self.enabletimetracker = config.getboolean('main', 'scantimelogger')
        except Exception as e:
            self.enabletimetracker = False

        self.logger.debug("enabletimetracker = %s" % self.enabletimetracker)


    def set_workerstate(self, status):
        if self.worker is not None:
            self.worker.workerstate = status

    def handlesession(self, worker=None):
        self.worker = worker

        prependheader = self.config.get('main', 'prependaddedheaders')
        try:
            suspect = None
            self.set_workerstate('receiving message')
            self.tracktime("SessionHandler-Setup")
            suspect = self.protohandler.get_suspect()
            if suspect is None:
                self.logger.error('No Suspect retrieved, ending session')
                return
            self.tracktime("Message-Receive-Suspect")
            self.stats.increase_counter_values(StatDelta(in_=1))

            if len(suspect.recipients) != 1:
                self.logger.warning('Notice: Message from %s has %s recipients. Plugins supporting only one recipient will see: %s' % (
                    suspect.from_address, len(suspect.recipients), suspect.to_address))
            self.logger.debug("Message from %s to %s: %s bytes stored to %s" % (
                suspect.from_address, suspect.to_address, suspect.size, suspect.tempfile))
            self.set_workerstate("Handling message %s" % suspect)
            # store incoming port to tag, could be used to disable plugins
            # based on port
            try:
                port = self.protohandler.socket.getsockname()[1]
                if port is not None:
                    suspect.tags['incomingport'] = port
            except Exception as e:
                self.logger.warning('Could not get incoming port: %s' % str(e))

            pluglist = self.run_prependers(suspect)

            starttime = time.time()
            self.run_plugins(suspect, pluglist)

            # Set fuglu spam status if wanted
            if self.config.getboolean('main', 'spamstatusheader'):
                if suspect.is_spam():
                    suspect.addheader("%sSpamstatus" % prependheader, 'YES')
                else:
                    suspect.addheader("%sSpamstatus" % prependheader, 'NO')

            # how long did it all take?
            difftime = time.time() - starttime
            suspect.tags['fuglu.scantime'] = "%.4f" % difftime

            # Debug info to mail
            if self.config.getboolean('main', 'debuginfoheader'):
                debuginfo = str(suspect)
                suspect.addheader("%sDebuginfo" % prependheader, debuginfo)

            # add suspect id for tracking
            if self.config.getboolean('main', 'suspectidheader'):
                suspect.addheader('%sSuspect' % prependheader, suspect.id)
            self.tracktime("Adding-Headers")

            # checks done.. print out suspect status
            logformat = self.config.get('main', 'logtemplate')
            if logformat.strip() != '':
                self.logger.info(suspect.log_format(logformat))
            suspect.debug(suspect)
            self.tracktime("Debug-Suspect")

            # check if one of the plugins made a decision
            result = self.action

            self.set_workerstate("Finishing message %s" % suspect)

            message_is_deferred = False
            if result == ACCEPT or result == DUNNO:
                try:
                    self.protohandler.commitback(suspect)
                    self.tracktime("Commitback")
                    self.stats.increase_counter_values(StatDelta(out=1))
                    self.tracktime("Increase-Stats")

                except KeyboardInterrupt:
                    sys.exit()
                except Exception as e:
                    message_is_deferred = True
                    trb = traceback.format_exc()
                    self.logger.error("Could not commit message. Error: %s" % trb)
                    self.logger.exception(e)
                    self._defer()

            elif result == DELETE:
                self.logger.info("MESSAGE DELETED: %s" % suspect.id)
                retmesg = 'OK: (%s)' % suspect.id
                if self.message is not None:
                    retmesg = self.message
                self.protohandler.discard(retmesg)
            elif result == REJECT:
                retmesg = "Rejected by content scanner"
                if self.message is not None:
                    retmesg = self.message
                self.protohandler.reject(retmesg)
            elif result == DEFER:
                message_is_deferred = True
                self._defer(self.message)
            else:
                self.logger.error(
                    'Invalid Message action Code: %s. Using DEFER' % result)
                message_is_deferred = True
                self._defer()

            # run appenders (stats plugin etc) unless msg is deferred
            if not message_is_deferred:
                self.stats.increasecounters(suspect)
                self.tracktime("Increase-Counters")
                self.run_appenders(suspect, result)
            else:
                self.logger.warning("DEFERRED %s" % suspect.id)

            # clean up
            try:
                os.remove(suspect.tempfile)
                self.logger.debug('Removed tempfile %s' % suspect.tempfile)
                suspect.tempfile = None
                self.tracktime("Remove-tempfile")
            except OSError:
                self.logger.warning('Could not remove tempfile %s' % suspect.tempfile)
        except KeyboardInterrupt:
            sys.exit(0)
        except ValueError:
            # Error in envelope send/receive address
            try:
                address_compliance_fail_action = self.config.get('main','address_compliance_fail_action').lower()
            except Exception:
                address_compliance_fail_action = "defer"

            try:
                message = self.config.get('main','address_compliance_fail_message')
            except Exception:
                message = "invalid sender or recipient address"

            if address_compliance_fail_action   == "defer":
                self._defer(message)
            elif address_compliance_fail_action == "reject":
                self._reject(message)
            elif address_compliance_fail_action == "discard":
                self._discard(message)
            else:
                self._defer(message)

        except Exception as e:
            exc = traceback.format_exc()
            self.logger.error('Exception %s: %s' % (e, exc))
            self._defer()

        finally:
            # finally is also executed if there's a return statement somewhere in try-except

            try:
                remove_tmpfiles_on_error = self.config.getboolean('main', 'remove_tmpfiles_on_error')
            except Exception:
                remove_tmpfiles_on_error = True

            if suspect is None:
                # if there was an error creating the suspect, check if the filename can be
                # extracted from the protohandler
                tmpfilename = self.protohandler.get_tmpfile()
                if tmpfilename is None:
                    tmpfilename = ""
                if remove_tmpfiles_on_error:
                    self.logger.debug('Remove tmpfile: %s for failed message' % tmpfilename)
                    self.protohandler.remove_tmpfile()
                else:
                    self.logger.warning('Keep tmpfile: %s for failed message' % tmpfilename)

            elif suspect.tempfile is not None:
                # suspect was created but not stopped cleanly
                if remove_tmpfiles_on_error:
                    try:
                        os.remove(suspect.tempfile)
                        self.logger.debug('Removed tempfile %s' % suspect.tempfile)
                    except OSError:
                        self.logger.warning('Could not remove tempfile %s' % suspect.tempfile)
                else:
                    self.logger.warning('Keep tempfile %s for failed message' % suspect.tempfile)

            # try to remove the suspect
            try:
                self.logger.debug('Remove suspect (current refs): %u' % sys.getrefcount(suspect))
                suspectid = suspect.id
                del suspect
            except Exception as e:
                suspectid = "unknown"
                pass

            # ---------------#
            # report timings #
            # ---------------#
            self.report_timings(suspectid)


        self.logger.debug('Session finished')


    def _discard(self, message=None):
        if message is None:
            message="internal problem - discard"

        # try to end the session gracefully, but this might cause the same exception again,
        # in case of a broken pipe for example
        try:
            self.protohandler.discard(message)
        except Exception:
            pass

    def _reject(self, message=None):
        if message is None:
            message="internal problem - reject"

        # try to end the session gracefully, but this might cause the same exception again,
        # in case of a broken pipe for example
        try:
            self.protohandler.reject(message)
        except Exception:
            pass

    def _defer(self, message=None):
        if message is None:
            message="internal problem - message deferred"

        # try to end the session gracefully, but this might cause the same exception again,
        # in case of a broken pipe for example
        try:
            self.protohandler.defer(message)
        except Exception:
            pass


    def trash(self, suspect, killerplugin=None):
        """copy suspect to trash if this is enabled"""
        trashdir = self.config.get('main', 'trashdir').strip()
        if trashdir == "":
            return

        if not os.path.isdir(trashdir):
            try:
                os.makedirs(trashdir)
            except OSError:
                self.logger.error(
                    "Trashdir %s does not exist and could not be created" % trashdir)
                return
            self.logger.info('Created trashdir %s' % trashdir)

        trashfilename = ''
        try:
            handle, trashfilename = tempfile.mkstemp(
                prefix=suspect.id, dir=self.config.get('main', 'trashdir'))
            with os.fdopen(handle, 'w+b') as trashfile:
                trashfile.write(suspect.get_source())
            self.logger.debug('Message stored to trash: %s' % trashfilename)
        except Exception as e:
            self.logger.error(
                "could not create file %s: %s" % (trashfilename, e))

        # TODO: document main.trashlog
        if self.config.has_option('main', 'trashlog') and self.config.getboolean('main', 'trashlog'):
            try:
                with open('%s/00-fuglutrash.log' % self.config.get('main', 'trashdir'), 'a') as handle:
                    # <date> <time> <from address> <to address> <plugin that said "DELETE"> <filename>
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    handle.write("%s %s %s %s %s" % (
                        now, suspect.from_address, suspect.to_address, killerplugin, trashfilename))
                    handle.write("\n")
            except Exception as e:
                self.logger.error("Could not update trash log: %s" % e)

    def run_plugins(self, suspect, pluglist):
        """Run scannerplugins on suspect"""
        suspect.debug('Will run plugins: %s' % pluglist)
        self.tracktime("Before-Plugins")
        for plugin in pluglist:
            try:
                self.logger.debug('Running plugin %s' % plugin)
                self.set_workerstate(
                    "%s : Running Plugin %s" % (suspect, plugin))
                suspect.debug('Running plugin %s' % str(plugin))
                starttime = time.time()
                ans = plugin.examine(suspect)
                plugintime = time.time() - starttime
                suspect.tags['scantimes'].append((plugin.section, plugintime))
                message = None
                if type(ans) is tuple:
                    result, message = ans
                else:
                    result = ans

                if result is None:
                    result = DUNNO

                suspect.tags['decisions'].append((plugin.section, result))

                if result == DUNNO:
                    suspect.debug('Plugin makes no final decision')
                elif result == ACCEPT:
                    suspect.debug(
                        'Plugin accepts the message - skipping all further tests')
                    self.logger.debug(
                        'Plugin says: ACCEPT. Skipping all other tests')
                    self.action = ACCEPT
                    break
                elif result == DELETE:
                    suspect.debug(
                        'Plugin DELETES this message - no further tests')
                    self.logger.debug(
                        'Plugin says: DELETE. Skipping all other tests')
                    self.action = DELETE
                    self.message = message
                    self.trash(suspect, str(plugin))
                    break
                elif result == REJECT:
                    suspect.debug(
                        'Plugin REJECTS this message - no further tests')
                    self.logger.debug(
                        'Plugin says: REJECT. Skipping all other tests')
                    self.action = REJECT
                    self.message = message
                    break
                elif result == DEFER:
                    suspect.debug(
                        'Plugin DEFERS this message - no further tests')
                    self.logger.debug(
                        'Plugin says: DEFER. Skipping all other tests')
                    self.action = DEFER
                    self.message = message
                    break
                else:
                    self.logger.error(
                        'Invalid Message action Code: %s. Using DUNNO' % result)

            except Exception as e:
                CrashStore.store_exception()
                exc = traceback.format_exc()
                self.logger.error('Plugin %s failed: %s' % (str(plugin), exc))
                suspect.debug(
                    'Plugin failed : %s . Please check fuglu log for more details' % e)
            finally:
                self.tracktime(str(plugin), plugin=True)

    def run_prependers(self, suspect):
        """Run prependers on suspect"""
        plugcopy = self.plugins[:]
        self.tracktime("Before-Prependers")
        for plugin in self.prependers:
            try:
                self.logger.debug('Running prepender %s' % plugin)
                self.set_workerstate(
                    "%s : Running Prepender %s" % (suspect, plugin))
                starttime = time.time()
                result = plugin.pluginlist(suspect, plugcopy)
                plugintime = time.time() - starttime
                suspect.tags['scantimes'].append((plugin.section, plugintime))
                if result is not None:
                    plugcopyset = set(plugcopy)
                    resultset = set(result)
                    removed = list(plugcopyset - resultset)
                    added = list(resultset - plugcopyset)
                    if len(removed) > 0:
                        self.logger.debug(
                            'Prepender %s removed plugins: %s' % (plugin, list(map(str, removed))))
                    if len(added) > 0:
                        self.logger.debug(
                            'Prepender %s added plugins: %s' % (plugin, list(map(str, added))))
                    plugcopy = result

            except Exception:
                CrashStore.store_exception()
                exc = traceback.format_exc()
                self.logger.error(
                    'Prepender plugin %s failed: %s' % (str(plugin), exc))
            finally:
                self.tracktime(str(plugin), prepender=True)
        return plugcopy

    def run_appenders(self, suspect, finaldecision):
        """Run appenders on suspect"""
        if suspect.get_tag('noappenders'):
            return

        self.tracktime("Before-Appenders")
        for plugin in self.appenders:
            try:
                self.logger.debug('Running appender %s' % plugin)
                suspect.debug('Running appender %s' % plugin)
                self.set_workerstate(
                    "%s : Running appender %s" % (suspect, plugin))
                starttime = time.time()
                plugin.process(suspect, finaldecision)
                plugintime = time.time() - starttime
                suspect.tags['scantimes'].append((plugin.section, plugintime))
            except Exception:
                CrashStore.store_exception()
                exc = traceback.format_exc()
                self.logger.error(
                    'Appender plugin %s failed: %s' % (str(plugin), exc))
            finally:
                self.tracktime(str(plugin), appender=True)
