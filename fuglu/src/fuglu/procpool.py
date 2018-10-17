# -*- coding: UTF-8 -*-
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
import fuglu.core
import fuglu.logtools as logtools
from fuglu.protocolbase import compress_task, uncompress_task
from fuglu.scansession import SessionHandler
from fuglu.stats import Statskeeper, StatDelta
from fuglu.addrcheck import Addrcheck
try:
    from queue import Empty as EmptyQueue
except ImportError:
    from Queue import Empty as EmptyQueue

import multiprocessing
import multiprocessing.queues
import signal
import time
import logging
import traceback
import threading
import sys
import os

import importlib
try:
    import objgraph
    OBJGRAPH_EXTENSION_ENABLED = True
except ImportError:
    OBJGRAPH_EXTENSION_ENABLED = False



class ProcManager(object):
    def __init__(self, logQueue, numprocs = None, queuesize=100, config = None):
        self._child_id_counter=0
        self._logQueue = logQueue
        self.manager = multiprocessing.Manager()
        self.shared_state = self._init_shared_state()
        self.config = config
        self.numprocs = numprocs
        self.workers = []
        self.queuesize = queuesize
        self.tasks = multiprocessing.Queue(queuesize)
        self.child_to_server_messages = multiprocessing.Queue()

        self.logger = logging.getLogger('%s.procpool' % __package__)
        self._stayalive = True
        self.name = 'ProcessPool'
        self.message_listener = MessageListener(self.child_to_server_messages)
        self.start()

    def _init_shared_state(self):
        shared_state = self.manager.dict()
        return shared_state

    @property
    def stayalive(self):
        return self._stayalive

    @stayalive.setter
    def stayalive(self, value):
        # procpool is shut down -> send poison pill to workers
        if self._stayalive and not value:
            self._stayalive = False
            self._send_poison_pills()
        self._stayalive = value

    def _send_poison_pills(self):
        """flood the queue with poison pills to tell all workers to shut down"""
        for _ in range(len(self.workers)):
            # tasks queue is FIFO queue. As long as nothing is added to the queue
            # anymore the poison pills will be the last elements taken from the queue
            self.tasks.put_nowait(None)

    def add_task(self, session):
        if self._stayalive:
            self.tasks.put(session)

    def add_task_from_socket(self, sock, handler_modulename, handler_classname, port):
        """
        Consistent interface with procpool. Add a new task to the queu
        given the socket to receive the message.

        Args:
            sock (socket): socket to receive the message
            handler_modulename (str): module name of handler
            handler_classname (str): class name of handler
            port (int): original incoming port
        """
        try:
            task = compress_task(sock, handler_modulename, handler_classname, port)
            self.add_task(task)
        except Exception as e:
            self.logger.error("Exception happened trying to add task to queue: %s" % str(e))
            self.logger.exception(e)

    def _create_worker(self):
        self._child_id_counter +=1
        worker_name = "Worker-%s"%self._child_id_counter
        worker = multiprocessing.Process(target=fuglu_process_worker, name=worker_name,
                                         args=(self.tasks, self.config, self.shared_state, self.child_to_server_messages, self._logQueue))
        return worker

    def start(self):
        for i in range(self.numprocs):
            worker = self._create_worker()
            worker.start()
            self.workers.append(worker)

        # Start the child-to-parent message listener
        self.message_listener.start()

    def shutdown(self, newmanager=None):
        # setting stayalive equal to False
        # will send poison pills to all processors
        self.logger.debug("Shutdown procpool -> send poison pills")
        self.stayalive = False

        # add another poison pill for the ProcManager itself removing tasks...
        self.logger.debug("Another poison pill for the ProcManager itself")
        self.tasks.put_nowait(None)

        if newmanager:
            # new manager available. Transfer tasks
            # to new manager
            self.logger.debug("Pass queue items to new manager")
            countmessages = 0
            while True:
                task = self.tasks.get()
                if task is None:  # poison pill
                    break
                newmanager.add_task(task)
                countmessages += 1
            self.logger.info("Moved %u messages to queue of new manager" % countmessages)
        else:
            self.logger.debug("Get rid of items in queue")
            return_message = "Temporarily unavailable... Please try again later."
            mark_defer_counter = 0
            while True:
                # Don't wait
                try:
                    task = self.tasks.get(False)
                except EmptyQueue:
                    self.logger.error("Queue is empty! Take a poison pill!")
                    task = None
                if task is None:  # poison pill
                    self.logger.debug("Got poison pill")
                    break
                self.logger.debug("Got task, mark as defer")
                mark_defer_counter += 1
                sock, handler_modulename, handler_classname = uncompress_task(task)
                handler_class = getattr(importlib.import_module(handler_modulename), handler_classname)
                handler_instance = handler_class(sock, self.config)
                handler_instance.defer(return_message)
            if mark_defer_counter > 0:
                self.logger.info("Marked %s messages as '%s' to close queue" % (mark_defer_counter, return_message))

        # join the workers
        try:
            join_timeout = self.config.getfloat('performance', 'join_timeout')
        except:
            if newmanager:
                join_timeout = 120.0
            else:
                # if there's no new manager then
                # we don't wait, just kill
                join_timeout = 1

        self.logger.debug("Join workers")
        tstart = time.time()
        remaining_timeout = join_timeout
        for worker in self.workers:
            tpassed = time.time()-tstart
            remaining_timeout = max(join_timeout - tpassed, 0.05)
            worker.join(remaining_timeout)
            if worker.is_alive():
                self.logger.error("Could not stop worker %s (pid: %u) with given timeout of %f (%f)"
                                  % (worker, worker.pid, join_timeout, remaining_timeout))
                worker.terminate()

        self.logger.debug("Join message listener")
        self.message_listener.stayalive = False
        # put poison pill into queue otherwise the process will not stop
        # since "stayalive" is only checked after receiving a message from the queue
        self.child_to_server_messages.put_nowait(None)
        self.message_listener.join(join_timeout)
        if self.message_listener.is_alive():
            self.logger.error("Could not stop message_listener %s with given timeout of %f, just go ahead..."
                              % (self.message_listener.name, join_timeout))

        self.logger.debug("Close tasks queue")
        self.tasks.close()

        self.child_to_server_messages.close()
        self.logger.debug("Shutdown multiprocessing manager")
        self.manager.shutdown()
        self.logger.debug("done...")

class MessageListener(threading.Thread):
    def __init__(self, message_queue):
        threading.Thread.__init__(self)
        self.name = "Process Message Listener"
        self.message_queue = message_queue
        self.stayalive = True
        self.statskeeper = Statskeeper()
        self.daemon = True


    def run(self):
        while self.stayalive:
            message = self.message_queue.get()
            if message is None:
                break
            event_type = message['event_type']
            if event_type == 'statsdelta': # increase statistics counters
                try:
                    delta = StatDelta(**message)
                    self.statskeeper.increase_counter_values(delta)
                except Exception:
                    print(traceback.format_exc())


def fuglu_process_worker(queue, config, shared_state, child_to_server_messages, logQueue):


    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    logtools.client_configurer(logQueue)
    logging.basicConfig(level=logging.DEBUG)
    workerstate = WorkerStateWrapper(shared_state,'loading configuration')
    logger = logging.getLogger('fuglu.process.%s(%u)' % (workerstate.process.name, workerstate.process.pid))
    logger.debug("New worker: %s" % logtools.createPIDinfo())


    # Setup address compliance checker
    # -> Due to default linux forking behavior this should already
    #    have the correct setup but it's better not to rely on this
    try:
        address_check = config.get('main','address_compliance_checker')
    except Exception as e:
        # might happen for some tests which do not propagate defaults
        address_check = "Default"
    Addrcheck().set(address_check)


    # load config and plugins
    logger.debug("Create MainController")
    controller = fuglu.core.MainController(config, logQueue=logQueue, nolog=True)
    controller.load_extensions()
    controller.load_plugins()

    prependers = controller.prependers
    plugins = controller.plugins
    appenders = controller.appenders

    # forward statistics counters to parent process
    stats = Statskeeper()
    stats.stat_listener_callback.append(lambda event: child_to_server_messages.put(event.as_message()))

    logger.debug("%s: Enter service loop..." % logtools.createPIDinfo())

    try:
        while True:
            workerstate.workerstate = 'waiting for task'
            logger.debug("%s: Child process waiting for task" % logtools.createPIDinfo())
            task = queue.get()
            if task is None: # poison pill
                logger.debug("%s: Child process received poison pill - shut down" % logtools.createPIDinfo())
                try:
                    # it might be possible it does not work to properly set the workerstate
                    # since this is a shared variable -> prevent exceptions
                    workerstate.workerstate = 'ended (poison pill)'
                except Exception as e:
                    logger.debug("Exception setting workstate while getting poison pill")
                    logger.exception(e)
                    pass
                finally:
                    return
            workerstate.workerstate = 'starting scan session'
            logger.debug("%s: Child process starting scan session" % logtools.createPIDinfo())
            sock, handler_modulename, handler_classname, port = uncompress_task(task)
            handler_class = getattr(importlib.import_module(handler_modulename), handler_classname)
            handler_instance = handler_class(sock, config)
            handler = SessionHandler(handler_instance, config, prependers, plugins, appenders, port)
            handler.handlesession(workerstate)
            del handler
            del handler_instance
            del handler_class
            del handler_modulename
            del handler_classname
            del sock

            # developers only:
            # for debugging memory this can be enabled
            # Note this can NOT be copied to threadpool worker because
            # it will create a memory leak
            if OBJGRAPH_EXTENSION_ENABLED and False:
                debug_procpoolworkermemory(logger, config)

    except KeyboardInterrupt:
        workerstate.workerstate = 'ended (keyboard interrupt)'
        logger.debug("Keyboard interrupt")
    except Exception as e:
        logger.error("Exception in worker process: %s" % str(e))
        workerstate.workerstate = 'crashed'
    finally:
        # this process will not put any object in queue
        queue.close()
        controller.shutdown()

def debug_procpoolworkermemory(logger, config):
    """
    Debug memory usage using the objgraph library, eventually
    write graphs to file in tmp directory

    Args:
        logger (logging.Logger): logger to log into
        config (RawConfigParser): configuration used for temporary file dir

    """
    # now check what remains

    # can be set to true for debugging
    # -> remaining objects will be written to the dot files in the tmp folder
    # -> use "xdot" to visualise the file which contains the objects referencing the corresponding
    #    object instance and preventing direct deallocation because of the reference count
    writedebuggraphs = False

    suspectobjects = objgraph.by_type('Suspect')
    if len(suspectobjects) > 0:
        if writedebuggraphs:
            objgraph.show_backrefs(suspectobjects[-1], max_depth=5,refcounts=True,
                                   filename=os.path.join(config.get('main', 'tempdir'), 'suspects.dot'))
        logger.info("Refcounts on last subject: %u" % sys.getrefcount(suspectobjects[-1]))
    mailattachmentobjects = objgraph.by_type('Mailattachment')
    if len(mailattachmentobjects) > 0:
        if writedebuggraphs:
            objgraph.show_backrefs(mailattachmentobjects[-1], max_depth=5, refcounts=True,
                                   filename=os.path.join(config.get('main', 'tempdir'),
                                                         'mailattachments.dot'))
        logger.info("Refcounts on last mailattachment: %u" % sys.getrefcount(mailattachmentobjects[-1]))
    mailattachmentmanagerobjects = objgraph.by_type('Mailattachment_mgr')
    if len(mailattachmentmanagerobjects) > 0:
        if writedebuggraphs:
            objgraph.show_backrefs(mailattachmentmanagerobjects[-1], max_depth=5, refcounts=True,
                                   filename=os.path.join(config.get('main', 'tempdir'),
                                                         'mailattachmentsmgr.dot'))
        logger.info("Refcounts on last mailattachmentmgr: %u"
                    % sys.getrefcount(mailattachmentmanagerobjects[-1]))
    allobjects = suspectobjects + mailattachmentobjects + mailattachmentmanagerobjects
    if len(allobjects) > 0:
        logger.error('objects in memory: Suspect: %u, MailAttachments: %u, MailAttachment_mgr: %u'
                     % (len(suspectobjects),len(mailattachmentobjects),len(mailattachmentmanagerobjects)))
    else:
        logger.debug('objects in memory: Suspect: %u, MailAttachments: %u, MailAttachment_mrt: %u'
                     % (len(suspectobjects),len(mailattachmentobjects),len(mailattachmentmanagerobjects)))
    del suspectobjects
    del mailattachmentobjects
    del mailattachmentmanagerobjects

class WorkerStateWrapper(object):
    def __init__(self, shared_state_dict, initial_state='created', process=None):
        self._state = initial_state
        self.shared_state_dict = shared_state_dict
        self.process = process
        if not process:
            self.process = multiprocessing.current_process()

        self._publish_state()

    def _publish_state(self):
        try:
            self.shared_state_dict[self.process.name] = self._state
        except EOFError:
            pass

    @property
    def workerstate(self):
        return self._state

    @workerstate.setter
    def workerstate(self, value):
        self._state = value
        self._publish_state()
