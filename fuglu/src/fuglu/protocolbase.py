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
import logging
import pickle
import socket
import threading
from fuglu.scansession import SessionHandler
import traceback
from multiprocessing.reduction import ForkingPickler
import os
try:
    from StringIO import StringIO
except ImportError:
    # Python 3
    from io import BytesIO as StringIO
from fuglu.logtools import createPIDinfo


class ProtocolHandler(object):
    protoname = 'UNDEFINED'

    def __init__(self, socket, config):
        self.socket = socket
        self.config = config
        self.logger = logging.getLogger('fuglu.%s' % self.__class__.__name__)
        self.sess = None

    def remove_tmpfile(self):
        tmpfile = self.get_tmpfile()
        if tmpfile is not None:
            try:
                os.remove(tmpfile)
            except OSError:
                pass

    def get_tmpfile(self):
        if self.sess is not None:
            try:
                tmpfilename = self.sess.tempfilename
            except AttributeError:
                tmpfilename = None
        return tmpfilename

    def get_suspect(self):
        return None

    def commitback(self, suspect):
        pass

    def defer(self, reason):
        pass

    def discard(self, reason):
        pass

    def reject(self, reason):
        pass

class BasicTCPServer(object):

    def __init__(self, controller, port=10125, address="127.0.0.1", protohandlerclass=None):
        if protohandlerclass is None:
            protohandlerclass = ProtocolHandler
        self.protohandlerclass = protohandlerclass
        self.logger = logging.getLogger("fuglu.incoming.%s" % port)
        self.logger.debug('Starting incoming Server on Port %s, protocol=%s' % (
            port, self.protohandlerclass.protoname))
        self.logger.debug('Incoming server process info:  %s' % createPIDinfo())
        self.logger.debug('(%s) Logger id is %s' % (createPIDinfo(),id(self)))
        self.port = port
        self.controller = controller
        self.stayalive = True

        addr_f = socket.getaddrinfo(address, 0)[0][0]

        try:
            self._socket = socket.socket(addr_f, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((address, port))
            self._socket.listen(5)
        except Exception as e:
            self.logger.error('Could not start incoming Server on port %s: %s' % (port, e))
            self.stayalive = False

    def shutdown(self):
        self.logger.info("TCP Server on port %s closing" % self.port)
        self.stayalive = False
        try:
            self._socket.shutdown(1)
            self._socket.close()
        except Exception:
            pass

    def serve(self):
        # Important:
        # -> do NOT create local variables which are copies of member variables like
        # controller = self.controller
        # threadpool = self.controller.threadpool
        # procpool = self.controller.procpool
        # Since thes variables might change while in the stayalive loop the process would get stuck,
        # example: when sending SIGHUP which might recreate the processor pool or threads pool
        #          which would then still point to the wrong (old) memory location and is therefore not served anymore

        threading.currentThread().name = '%s Server on Port %s' % (
            self.protohandlerclass.protoname, self.port)

        self.logger.info('%s Server running on port %s' %
                         (self.protohandlerclass.protoname, self.port))

        while self.stayalive:
            try:
                self.logger.debug('Waiting for connection...')
                nsd = self._socket.accept()
                sock,addr = nsd
                if not self.stayalive:
                    break
                handler_classname = self.protohandlerclass.__name__
                handler_modulename = self.protohandlerclass.__module__
                self.logger.debug('(%s) Incoming connection  [incoming server port: %s, prot: %s]' % (createPIDinfo(),self.port,self.protohandlerclass.protoname))
                if self.controller.threadpool:
                    # this will block if queue is full
                    self.controller.threadpool.add_task_from_socket(sock, handler_modulename, handler_classname, self.port)
                elif self.controller.procpool:
                    self.controller.procpool.add_task_from_socket(sock, handler_modulename, handler_classname, self.port)
                else:
                    ph = self.protohandlerclass(sock, self.controller.config)
                    engine = SessionHandler(ph, self.controller.config, self.controller.prependers,
                                            self.controller.plugins, self.controller.appenders, self.port)
                    engine.handlesession()
            except Exception as e:
                exc = traceback.format_exc()
                self.logger.error('Exception in serve(): %s - %s' % (str(e), exc))


def compress_task(sock, handler_modulename, handler_classname, port):
    """
    Compress all the inputs required for a task into a tuple
    Args:
        sock (socket): Receiving socket
        handler_modulename (str): Modulename of the handler to be used
        handler_classname (str): Classname of the handler to be used
        port (int):  incoming port

    Returns:
        tuple: All information suitable to put as a task in a queue

    """
    """ Pickle a socket This is required to pass the socket in multiprocessing"""
    buf = StringIO()
    ForkingPickler(buf).dump(sock)
    pickled_socket = buf.getvalue()

    task = pickled_socket, handler_modulename, handler_classname, port
    return task


def uncompress_task(task):
    """
    Uncompress a task (which was created by "compress_task"

    Args:
        task (tuple): Tuple containing task information

    Returns:
        tuple: Tuple with uncompressed task objects

    """
    if task is None:
        return None

    pickled_socket, handler_modulename, handler_classname, port = task
    sock = pickle.loads(pickled_socket)
    return sock, handler_modulename, handler_classname, port

