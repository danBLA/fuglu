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
import threading
import time
try:
    import queue
except ImportError:
    import Queue as queue
import logging
import weakref
import importlib
from fuglu.protocolbase import compress_task, uncompress_task
from fuglu.scansession import SessionHandler

class ThreadPool(threading.Thread):

    def __init__(self, controller, minthreads=1, maxthreads=20, queuesize=100):
        self.workers = []
        self.queuesize = queuesize
        self.tasks = queue.Queue(queuesize)
        self.minthreads = minthreads
        self.maxthreads = maxthreads
        assert self.minthreads > 0
        assert self.maxthreads > self.minthreads

        self.logger = logging.getLogger('%s.threadpool' % __package__)
        self.threadlistlock = threading.Lock()
        self.checkinterval = 10
        self.threadcounter = 0
        self._stayalive = True
        self.laststats = 0
        self.statinverval = 60
        self.controller = weakref.ref(controller)  # keep a weak reference to controller
        threading.Thread.__init__(self)
        self.name = 'Threadpool'
        self.daemon = False
        self.start()

    @property
    def stayalive(self):
        return self._stayalive

    @stayalive.setter
    def stayalive(self, value):
        # threadpool is shut down -> send poison pill to workers
        if self._stayalive and not value:
            self._stayalive = False
            self._send_poison_pills()
        self._stayalive = value

    def _send_poison_pills(self):
        """flood the queue with poison pills to tell all workers to shut down"""
        for _ in range(self.maxthreads):
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
            port (int) : incoming port
        """
        try:
            task = compress_task(sock, handler_modulename, handler_classname, port)
            self.add_task(task)
        except Exception as e:
            self.logger.error("Exception happened trying to add task to queue: %s" % str(e))
            self.logger.exception(e)

    def get_task_sessionhandler(self):
        """
        Get task from queue, create a session handler and return it

        Returns:
            SessionHandler: a session handler to handle the task

        """
        if self._stayalive:
            task = self.tasks.get(True)
            if task is None:
                # Poison pill
                return None
            sock, handler_modulename, handler_classname, port = uncompress_task(task)
            handler_class = getattr(importlib.import_module(handler_modulename), handler_classname)

            controller = self.controller()
            if controller is None:
                # weak ref will point to None once object has been removed
                return None

            handler_instance = handler_class(sock, controller.config)
            handler = SessionHandler(handler_instance, controller.config, controller.prependers,
                                     controller.plugins, controller.appenders, port)
            return handler
        else:
            return None

    def run(self):
        self.logger.debug('Threadpool initializing. minthreads=%s maxthreads=%s maxqueue=%s checkinterval=%s' % (
            self.minthreads, self.maxthreads, self.queuesize, self.checkinterval))

        while self._stayalive:
            curthreads = self.workers
            numthreads = len(curthreads)

            # check the minimum boundary
            requiredminthreads = self.minthreads
            if numthreads < requiredminthreads:
                diff = requiredminthreads - numthreads
                self._add_worker(diff)
                continue

            # check the maximum boundary
            if numthreads > self.maxthreads:
                diff = numthreads - self.maxthreads
                self._remove_worker(diff)
                continue

            changed = False
            # ok, we are within the boundaries, now check if we can dynamically
            # adapt something
            queuesize = self.tasks.qsize()

            # if there are more tasks than current number of threads, we try to
            # increase
            workload = float(queuesize) / float(numthreads)

            if workload > 1 and numthreads < self.maxthreads:
                self._add_worker()
                numthreads += 1
                changed = True

            if workload < 1 and numthreads > self.minthreads:
                self._remove_worker()
                numthreads -= 1
                changed = True

            # log current stats
            if changed or time.time() - self.laststats > self.statinverval:
                workerlist = "\n%s" % '\n'.join(map(repr, self.workers))
                self.logger.debug('queuesize=%s workload=%.2f workers=%s workerlist=%s' % (
                    queuesize, workload, numthreads, workerlist))
                self.laststats = time.time()

            time.sleep(self.checkinterval)

        self.logger.info('Threadpool shut down')

    def _remove_worker(self, num=1):
        self.logger.debug('Removing %s workerthread(s)' % num)
        for bla in range(0, num):
            worker = self.workers[0]
            worker.stayalive = False
            worker.join(120)
            del self.workers[0]

    def _add_worker(self, num=1):
        self.logger.debug('Adding %s workerthread(s)' % num)
        for bla in range(0, num):
            self.threadcounter += 1
            worker = Worker("[%s]" % self.threadcounter, self)
            self.workers.append(worker)
            worker.start()

    def shutdown(self, newmanager=None):
        """
        Shutdown manager, transfer queue to a new manager if available. Otherwise
        mark messages as defer.

        Keyword Args:
            newmanager (ProcManager or ThreadPool): has to provide add_task accepting a pickled socket
        """

        # set stayalive to False, this will send
        # poison pills to the workers
        self.stayalive = False

        # now remove elements from the queue
        # first, put another poison pill for the Threadpool itself
        self.tasks.put_nowait(None)

        if newmanager:
            # new manager available. Transfer tasks to new manager
            countmessages = 0
            while True:
                # don't use the get_task_sessionhandler from Threadpool since this will
                # not give anything once stayalive is False
                task = self.tasks.get(True)
                if task is None:  # poison pill
                    break
                newmanager.add_task(task)
                countmessages += 1
            self.logger.info("Moved %u messages to queue of new manager" % countmessages)
        else:
            return_message = "Temporarily unavailable... Please try again later."
            mark_defer_counter = 0
            while True:
                # don't use the get_task_sessionhandler from Threadpool since this will
                # not give anything once stayalive is False
                sesshandler = self.tasks.get(True)
                if sesshandler is None:  # poison pill -> shut down
                    break
                mark_defer_counter += 1
                sesshandler.protohandler.defer(return_message)

            self.logger.info("Marked %s messages as '%s' to close queue" % (mark_defer_counter,return_message))

        # remove all the workers (joins them also)
        for worker in self.workers:
            worker.stayalive = False
            worker.join(120)  # wait 120 seconds max

class Worker(threading.Thread):

    def __init__(self, workerid, pool):
        threading.Thread.__init__(self, name='Pool worker %s' % workerid)
        self.workerid = workerid
        self.birth = time.time()
        self.pool = pool
        self.stayalive = True
        self.logger = logging.getLogger('%s.threads.worker.%s' % (__package__, workerid))
        self.logger.debug('thread init')
        self.noisy = False
        self.setDaemon(False)
        self.workerstate = 'created'

    def __repr__(self):
        return "%s: %s" % (self.workerid, self.workerstate)

    def run(self):
        self.logger.debug('thread start')

        while self.stayalive:
            self.workerstate = 'waiting for task'
            if self.noisy:
                self.logger.debug('Getting new task...')
            sesshandler = self.pool.get_task_sessionhandler()
            if sesshandler == None:  # poison pill -> shut down
                if self.noisy:
                    self.logger.debug("got a poison pill .. good bye world")
                self.stayalive = False
                continue

            if self.noisy:
                self.logger.debug('Doing work')
            try:
                sesshandler.handlesession(self)
            except Exception as e:
                self.logger.error('Unhandled Exception : %s' % e)
            self.workerstate = 'task completed'

            del sesshandler

        self.workerstate = 'ending'
        self.logger.debug('thread end')
