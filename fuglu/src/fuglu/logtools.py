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
import logging
import logging.handlers
import logging.config
import os
import multiprocessing
import signal
import sys


def logFactoryProcess(listenerQueue,logQueue):
    """
    This process is responsible for creating the logger listener for the given queue.
    This Listener process is responsible for actually handling all the log messages in the queue.

    You might ask why this is a separate process. This log-implementation satisfies two constraints:
    - it has to work in multiprocessing mode
    - it has to work with TimedRotatingFileHandler
    - it has to at least be possible to change the debug level down to DEBUG

    Even in multiprocessing the subprocess inherits a lot of things from its father process at creation time.
    Using the logging module this can create quite weird effects. Withoug any change, using a TimedRotatingFileHandler
    most processes might still write to the old (archived) log file while the process that actually rotated the file
    and its threads will write to the new one.
    If the separate log process is created directly as a child of the main process is it not possible to recreate the
    log process later to take into account a new configuration, even if using a config server listener. The messages
    received from other processes will not necessarily apply the correct debug level if this has been changed.

    The only "clean" solution found so far is to always create the logging process from a clean process which does not
    have any logging structure stored yet. Therefore, the logFactoryProcess is created at the very beginning and it
    can produce new clean logging processes later that will properly setup with all propagation and level changes.

    Args:
        listenerQueue (multiprocessing.Queue): Queue where the logFactoryProcess will receive a configuration for
                                               which a new logging process will be created replacint the old one
        logQueue (multiprocessing.Queue): The queue where log messages will be sent, handled finally by the logging
                                          process

    """
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    loggerProcess = None
    while True:
        try:
            logConfig = listenerQueue.get()

            # if existing stop last logger process
            if loggerProcess:
                # try to close the old logger
                try:
                    logQueue.put_nowait(None)
                    loggerProcess.join(10) # wait 10 seconds max
                except Exception:
                    loggerProcess.terminate()
                finally:
                    loggerProcess = None

            if logConfig is None:  # We send this as a sentinel to tell the listener to quit.
                break

            # create new logger process
            loggerProcess = multiprocessing.Process(target=listener_process, args=(logConfig,logQueue))
            loggerProcess.daemon = True
            loggerProcess.start()

        except KeyboardInterrupt:
            print("Listener process received KeyboardInterrupt")
            #break
        except Exception:
            import sys, traceback
            print('LogFactoryProcess: Problem:', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    # if existing stop last logger process
    if loggerProcess:
        # try to close the old logger
        try:
            logQueue.put_nowait(None)
            loggerProcess.join(10) # wait 10 seconds max
        except Exception:
            import sys, traceback
            loggerProcess.terminate()
            print('LogFactoryProcess: Problem:', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


class logConfig(object):
    """
    Conig class to easily distinguish logging configuration for lint, foreground and production (from file)
    """
    def __init__(self, lint=False, logConfigFile="none", foreground=False, level=None):
        """
        Setup in lint mode of using a config file
        Args:
            lint (bool): enable lint mode which will print on the screen
            logConfigFile (): load configuration from config file
            foreground (bool): enable foreground mode which will print on the screen like lint (but no level)
        """
        # one option should be true
        assert ((1 if lint else 0) +
                (1 if foreground else 0) +
                (1 if logConfigFile != "none" else 0) == 1)

        self._configFile = logConfigFile
        if lint:
            self._level = logging.ERROR
        else:
            if level == "DEBUG":
                self._level = logging.DEBUG
            elif level == "INFO":
                self._level = logging.INFO
            elif level == "ERROR":
                self._level = logging.ERROR
            else:
                self._level = logging.NOTSET

        self._lint = lint
        self._foreground = foreground

    def configure(self):
        """
        Configure for lint mode or from file. We can not set a "pointer" to the function
        ----
        if self._lint or self._foreground:
            self.configure = self._configure4screen
        elif self._configFile != "none":
            self.configure = self._configure
        else:
            raise Exception("Not implemented!")
        ----
        because objects of this type are sent into the logger queue. Python 2.7 can then
        not pickle the instance.
        """
        if self._lint or self._foreground:
            logConfig._configure4screen(self._level, timeinformat=self._foreground)
        elif self._configFile != "none":
            if not os.path.exists(self._configFile):
                raise FileNotFoundError("Logging config file %s does not exist!" % self._configFile)

            logConfig._configure(self._configFile)
        else:
            raise Exception("Not implemented!")

    @staticmethod
    def _configure4screen(outputlevel, timeinformat=False):
        """
        Configure for stdout (output is on the screen)
        """
        root = logging.getLogger()
        root.setLevel(logging.NOTSET)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(outputlevel)
        if timeinformat:
            formatter = logging.Formatter('[%(process)-5d] %(asctime)s :  %(name)-25s: %(levelname)-s, %(message)s')
        else:
            # set a format which is simpler for console use
            formatter = logging.Formatter('[%(process)-5d] %(name)-25s: %(levelname)-s, %(message)s')
        # tell the handler to use this format
        console.setFormatter(formatter)
        # add the handler to the root logger
        root.addHandler(console)

    @staticmethod
    def _configure(configFile):
        """
        Configure logging using log configuration file
        """
        logging.config.fileConfig(configFile)
        # get root logger once just to make sure this global configuration exists
        root = logging.getLogger()


def listener_process(configurer,queue):
    """
    This is the listener process top-level loop: wait for logging events
    (LogRecords) on the queue and handle them, quit when you get a None for a
    LogRecord.

    Args:
        configurer (logConfig): instance lof logConfig class setting up logging on configure call
        queue (multiprocessing.Queue): The queue where log messages will be received and processed by this same process
    """

    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    configurer.configure()
    root = logging.getLogger()
    root.info("Listener process started")
    logLogger = logging.getLogger("LogListener")
    if logLogger.propagate:
        root.info("No special Log-logger")
        logLogger = None
    else:
        root.info("Using special LogLogger")

    while True:
        try:
            record = queue.get()
            if record is None:  # We send this as a sentinel to tell the listener to quit.
                root.info("Listener process received poison pill")
                break

            if logLogger:
                logLogger.debug("Approx queue size: %u, received record to process -> %s"%(queue.qsize(),record))

            if queue.full():
                root.error("QUEUE IS FULL!!!")
                if logLogger:
                    logLogger.error("QUEUE IS FULL!!!")

            logger = logging.getLogger(record.name)

            # check if this record should be logged or not...
            # the filter function should detect if the level is sufficient, but somehow it fails
            # so the check has to be done manually
            if logger.filter(record) and record.levelno >= logger.getEffectiveLevel():
                logger.handle(record)
        except KeyboardInterrupt:
            print("Listener process received KeyboardInterrupt")
            root.warning("Listener received exception")
            #break
        except Exception as e:
            root.warning("Listener received exception")
            root.exception(e)
    root.info("Listener process stopped")


def client_configurer(queue, level="NOTSET"):
    """
    The client configuration is done at the start of the worker process run.
    Note that on Windows you can't rely on fork semantics, so each process
    will run the logging configuration code when it starts.
    The log level is the minimum applied on the clients, final decision
    will be applied on the log-listener. But if the base-level here is INFO
    then setting the level to "DEBUG" in "logging.conf" will not show DEBUG-level
    messages.

    Args:
        queue (multiprocessing.Queue): queue where to send log messages
        level (str): log-level (DEBUG, INFO, ERROR) for all the clients

    """
    root = logging.getLogger()

    numRootHandlers = len(root.handlers)
    name = createPIDinfo()

    if numRootHandlers == 0:
        try:
            # Python 3
            h = logging.handlers.QueueHandler(queue)  # Just the one handler needed
        except AttributeError:
            # Python 2
            h = QueueHandlerPy3Copy(queue)
        root.addHandler(h)
        # send all messages
        if level == "DEBUG":
            root.setLevel(logging.DEBUG)
        elif level == "INFO":
            root.setLevel(logging.INFO)
        elif level == "ERROR":
            root.setLevel(logging.ERROR)
        else:
            root.setLevel(logging.NOTSET)
            root.info("Log-Level \"%s\" not vaild, setting NOTSET" % level)
        root.info("(%s) Queue handler added to root logger" % name)
    else:
        # on linux config is taken from father process automatically
        root.info("(%s) Root already has a handler -> not adding Queue handler" % name)


#----------------------------------------#
#-- Copied from Python 3 - handlers.py --#
#----------------------------------------#
class QueueHandlerPy3Copy(logging.Handler):
    """
    This handler sends events to a queue. Typically, it would be used together
    with a multiprocessing Queue to centralise logging to file in one process
    (in a multi-process application), so as to avoid file write contention
    between processes.

    This code is new in Python 3.2, but this class can be copy pasted into
    user code for use with earlier Python versions.
    """

    def __init__(self, queue):
        """
        Initialise an instance, using the passed queue.
        """
        logging.Handler.__init__(self)
        self.queue = queue

    def enqueue(self, record):
        """
        Enqueue a record.

        The base implementation uses put_nowait. You may want to override
        this method if you want to use blocking, timeouts or custom queue
        implementations.
        """
        self.queue.put_nowait(record)

    def prepare(self, record):
        """
        Prepares a record for queuing. The object returned by this method is
        enqueued.

        The base implementation formats the record to merge the message
        and arguments, and removes unpickleable items from the record
        in-place.

        You might want to override this method if you want to convert
        the record to a dict or JSON string, or send a modified copy
        of the record while leaving the original intact.
        """
        # The format operation gets traceback text into record.exc_text
        # (if there's exception data), and also puts the message into
        # record.message. We can then use this to replace the original
        # msg + args, as these might be unpickleable. We also zap the
        # exc_info attribute, as it's no longer needed and, if not None,
        # will typically not be pickleable.
        self.format(record)
        record.msg = record.message
        record.args = None
        record.exc_info = None
        return record

    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue, preparing it for pickling first.
        """
        try:
            self.enqueue(self.prepare(record))
        except Exception:
            self.handleError(record)


def createPIDinfo():
    infoString = ""
    if hasattr(os, 'getppid'):  # only available on Unix
        infoString += 'parent process: %u, ' % os.getppid()
    infoString += 'process id: %u' % os.getpid()
    return infoString


class PrependLoggerMsg(object):
    """Prepend something to all log messages of original logger, for example fuglu id"""
    def __init__(self, origlogger, prepend,
                 prependseparator=" ",
                 maxlevel=None,
                 minlevel=None
                 ):
        self._origlogger = origlogger
        self.prepend = prepend
        self.prependseparator = prependseparator
        assert minlevel in [logging.DEBUG, logging.WARNING, logging.INFO, logging.ERROR, None]
        assert maxlevel in [logging.DEBUG, logging.WARNING, logging.INFO, logging.ERROR, None]
        minlevel = minlevel if minlevel is not None else -1000
        maxlevel = maxlevel if maxlevel is not None else 1000

        self.debuglevel = max(min(logging.DEBUG, maxlevel), minlevel)
        self.infolevel= max(min(logging.INFO, maxlevel), minlevel)
        self.warninglevel= max(min(logging.WARNING, maxlevel), minlevel)
        self.errorlevel= max(min(logging.ERROR, maxlevel), minlevel)
        self.criticallevel= max(min(logging.CRITICAL, maxlevel), minlevel)

        self.origroutines = {
            logging.DEBUG: self._origlogger.debug,
            logging.INFO: self._origlogger.info,
            logging.WARNING: self._origlogger.warning,
            logging.ERROR: self._origlogger.error,
            logging.CRITICAL: self._origlogger.critical
        }

    def debug(self, msg, *args, **kwargs):
        self.origroutines[self.debuglevel]("%s%s%s" % (self.prepend, self.prependseparator, msg), *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.origroutines[self.infolevel]("%s%s%s" % (self.prepend, self.prependseparator, msg), *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.origroutines[self.warninglevel]("%s%s%s" % (self.prepend, self.prependseparator, msg), *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.origroutines[self.errorlevel]("%s%s%s" % (self.prepend, self.prependseparator, msg), *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.origroutines[self.criticallevel]("%s%s%s" % (self.prepend, self.prependseparator, msg), *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._origlogger.exception("%s%s%s" % (self.prepend, self.prependseparator, msg), *args, **kwargs)

    def __getattr__(self, attr):
        """if attribute doesn't exist __getattr__ is called, redirect to wrapped logger"""
        return getattr(self._origlogger, attr)


class LoggingContext(object):     
    """to be used for 'with'-statements to temporarily change a logger"""
    def __init__(self, logger, level=None, handler=None, close=True):     
        self.logger = logger     
        self.level = level     
        self.handler = handler     
        self.close = close     
    
    def __enter__(self):     
        if self.level is not None:     
            self.old_level = self.logger.level     
            self.logger.setLevel(self.level)     
        if self.handler:     
            self.logger.addHandler(self.handler)     
    
    def __exit__(self, et, ev, tb):     
        if self.level is not None:     
            self.logger.setLevel(self.old_level)     
        if self.handler:     
            self.logger.removeHandler(self.handler)     
        if self.handler and self.close:     
            self.handler.close()