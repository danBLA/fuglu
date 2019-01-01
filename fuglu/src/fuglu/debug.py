#   Copyright 2009-2019 Oli Schacher, Fumail Project
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
import threading
import sys
import time
import socket
import logging
import datetime
import traceback
import string
import os
import weakref
from fuglu.stringencode import force_bString, force_uString

try:
    import objgraph
    OBJGRAPH_EXTENSION_ENABLED = True
except ImportError:
    OBJGRAPH_EXTENSION_ENABLED = False
    # dummy object so we can keep objgraph._long_typename
    # as default input method in buildfilter
    class objgraph:
        _long_typename = None
        pass

class ControlServer(object):

    def __init__(self, controller, port=None, address="127.0.0.1"):
        if port is None:
            port = "/tmp/fuglu_control.sock"

        if isinstance(port, str):
            try:
                port = int(port)
            except ValueError:
                pass

        if isinstance(port, int):
            porttype = "inet"
            self.logger = logging.getLogger("fuglu.control.%s" % port)
            self.logger.debug('Starting Control/Info server on port %s' % port)
        else:
            porttype = "unix"
            self.logger = logging.getLogger(
                "fuglu.control.%s" % os.path.basename(port))
            self.logger.debug('Starting Control/Info server on %s' % port)

        self.port = port
        self.controller = controller
        self.stayalive = 1

        try:
            if porttype == "inet":
                addr_f = socket.getaddrinfo(address, 0)[0][0]
                self._socket = socket.socket(
                    addr_f, socket.SOCK_STREAM)
                self._socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._socket.bind((address, port))
            else:
                try:
                    os.remove(port)
                except Exception:
                    pass
                self._socket = socket.socket(
                    socket.AF_UNIX, socket.SOCK_STREAM)
                self._socket.bind(port)

            self._socket.listen(5)
        except Exception as e:
            self.logger.error('Could not start control server: %s' % e)
            sys.exit(1)

    def shutdown(self):
        self.stayalive = False
        self.logger.info("Control Server on port %s shutting down" % self.port)
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            time.sleep(3)
        except Exception:
            pass

    def serve(self):
        threading.currentThread().name = 'ControlServer Thread'
        controller = self.controller

        self.logger.info('Control/Info Server running on port %s' % self.port)
        while self.stayalive:
            try:
                engine = None
                self.logger.debug('Waiting for connection...')
                nsd = self._socket.accept()
                if not self.stayalive:
                    break
                engine = ControlSession(nsd[0], controller)
                self.logger.debug('Incoming connection from %s' % str(nsd[1]))
                engine.handlesession()

            except Exception:
                # When shutdown is called, we just close the socket which will
                # create a socket error that is not a problem and should therefore
                # not be reported
                if self.stayalive:
                    fmt = traceback.format_exc()
                    self.logger.error('Exception in serve(): %s' % fmt)

            finally:
                if engine:
                    del engine


class ControlSession(object):

    def __init__(self, socket, controller):
        self.controller = controller
        self.socket = socket
        self.commands = {
            'workerlist': weakref.WeakMethod(self.workerlist),
            'threadlist': weakref.WeakMethod(self.threadlist),
            'uptime': weakref.WeakMethod(self.uptime),
            'stats': weakref.WeakMethod(self.stats),
            'exceptionlist': weakref.WeakMethod(self.exceptionlist),
            'netconsole': weakref.WeakMethod(self.netconsole),
        }
        self.logger = logging.getLogger('fuglu.controlsession')

    def handlesession(self):
        line = force_uString(self.socket.recv(4096)).strip()
        if line == '':
            self.socket.close()
            return

        self.logger.debug('Control Socket command: %s' % line)
        answer = None
        try:
            if line.startswith("objgraph"):
                # special handling for objgraph
                # -> argument is a dict in json format
                # -> check attributes for commands, don't use list
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    argsdict = ControlSession.json_string_to_obj(parts[1], ForcedType=dict)
                else:
                    argsdict = {}
                self.logger.debug('objgraph_growth: args dict: %s' % argsdict)
                answer = self.handle_command(parts[0], argsdict, checkattr=True)
            else:
                # default handling
                line = line.lower()
                parts = line.split()
                answer = self.handle_command(parts[0], parts[1:])
        except Exception as e:
            if not answer:
                answer = force_uString(e)
            else:
                answer += force_uString(e)
        self.socket.sendall(force_bString(answer))
        self.socket.close()

    def handle_command(self, command, args, checkattr=False):
        if command not in self.commands:
            if checkattr:
                try:
                    return getattr(self, command)(args)
                except AttributeError:
                    pass
            return "ERR no such command: "+str(command)

        res = self.commands[command]()(args)
        return res

    def netconsole(self, args):
        port = 1337
        bind = "127.0.0.1"
        if len(args) > 0:
            port = int(args[0])
        if len(args) > 1:
            bind = args[1]
        nc_thread = threading.Thread(
            name='net console', target=self.controller.run_netconsole, args=(port, bind))
        nc_thread.daemon = True
        nc_thread.start()
        return "Python interactive console starting on %s port %s" % (bind, port)

    def workerlist(self, args):
        """list of mail scanning workers"""
        threadpool = self.controller.threadpool
        res=""
        if threadpool is not None:
            workerlist = "\n%s" % '\n*******\n'.join(map(repr, threadpool.workers))
            res += "Total %s worker threads\n%s" % (len(threadpool.workers), workerlist)

        procpool = self.controller.procpool
        if procpool is not None:
            childstate_dict = procpool.shared_state
            workerlist = "\n%s" % '\n*******\n'.join(["%s: %s"%(procname,procstate) for procname,procstate in childstate_dict.items()])
            res += "Total %s worker processes\n%s" % (len(procpool.workers), workerlist)

        return res

    def threadlist(self, args):
        """list of all threads"""
        threads = threading.enumerate()
        threadinfo = "\n%s" % '\n*******\n'.join(
            map(lambda t: "name=%s alive=%s daemon=%s" % (t.name, t.is_alive(), t.daemon), threads))
        res = "Total %s Threads\n%s" % (len(threads), threadinfo)
        return res

    def uptime(self, args):
        start = self.controller.started
        diff = datetime.datetime.now() - start
        return "Fuglu was started on %s\nUptime: %s" % (start, diff)

    def exceptionlist(self, args):
        """return last stacktrace"""
        excstring = ""
        i = 0
        for excinfo, thetime, threadinfo in CrashStore.exceptions:
            i += 1
            fmt = traceback.format_exception(*excinfo)
            timestr = datetime.datetime.fromtimestamp(thetime).ctime()
            excstring = excstring + \
                "\n[%s] %s : %s\n" % (i, timestr, threadinfo)
            excstring = excstring + "".join(fmt)
        return excstring

    def stats(self, args):
        start = self.controller.started
        runtime = datetime.datetime.now() - start
        stats = self.controller.statsthread.stats
        template = """Fuglu statistics
---------------
Uptime:\t\t${uptime}
Avg scan time:\t${scantime}
Total msgs:\t${totalcount} in:${incount} out:${outcount}
Ham:\t\t${hamcount}
Spam:\t\t${spamcount}
Virus:\t\t${viruscount}
Block:\t\t${blockedcount}
        """
        renderer = string.Template(template)
        vrs = dict(
            uptime=runtime,
            scantime=stats.scantime(),
            totalcount=stats.totalcount,
            hamcount=stats.hamcount,
            viruscount=stats.viruscount,
            spamcount=stats.spamcount,
            incount=stats.incount,
            outcount=stats.outcount,
            blockedcount=stats.blockedcount,
        )
        res = renderer.safe_substitute(vrs)
        return res

    def objgraph_count_types(self, args):
        """
        This function can be used to display the number of objects for one or several types of objects.
        For now this works best for fuglu with thread backend.

        Fuglu has to be running as a daemon.
        "fuglu_control" is used to communicate with the fuglu instance.

        Examples:
            (1) Count ans sum objects given by a list
            -----------------------------------------

            $ fuglu_control objgraph_count_types '{"typelist":["Worker","Suspect","SessionHandler"]}'

            ---------------
            Count suspects:
            ---------------

            params:
            * typelist: Worker,Suspect,SessionHandler

            Object types found in memory:
            Worker : 2
            Suspect : 0
            SessionHandler : 1

        """
        res = u"---------------\n" \
            + u"Count suspects:\n" \
            + u"---------------\n\n"

        defaults = {"typelist": ["Suspect", "Mailattachment", "Mailattachment_mgr"]}

        if OBJGRAPH_EXTENSION_ENABLED:
            if not args:
                args = {}

            # fill filter lists and other vars from dict
            res, inputdict = ControlSession.prepare_objectgraph_list_from_dict(args, res, defaults)

            try:
                res += u"Object types found in memory:\n"
                for otype in inputdict["typelist"]:
                    n_otypes = objgraph.count(otype)
                    res += u"%s : %u\n" % (otype, n_otypes)
            except Exception as e:
                res += u"ERROR: %s" % force_uString(e)
                self.logger.exception(e)
        else:
            res += u"please install module 'objgraph'"
        return res

    def objgraph_leaking_objects(self, args):
        """
        This is supposed to count reference counting bugs in C-level,
        see https://mg.pov.lt/objgraph/#reference-counting-bugs

        Example:

            $ fuglu_control objgraph_leaking_objects '{"nresults": 5}'

            ----------------
            Leaking objects:
            ----------------

            params:
            * nresults: 5
            * lowercase: True
            * dont_startwith:
            * must_startwith:
            * dont_contain:
            * must_contain:

            builtins.dict : 797
            builtins.list : 132
            builtins.tuple : 28
            builtins.method : 13
            builtins.weakref : 12
        """
        res = u"----------------\n" \
            + u"Leaking objects:\n" \
            + u"----------------\n\n"
        if OBJGRAPH_EXTENSION_ENABLED:
            defaults = {"nresults": 20,
                        "lowercase": True,
                        "dont_startwith": ["builtins", "_"],
                        "dont_contain": [],
                        "must_startwith": [],
                        "must_contain": []}

            if not args:
                args = {}

            # fill filter lists and other vars from dict
            res, inputdict = ControlSession.prepare_objectgraph_list_from_dict(args, res, defaults)
            roots = None
            types_list = None
            finalfilter = None
            try:
                roots = objgraph.get_leaking_objects()

                # build filter
                finalfilter = ControlSession.buildfilter(dont_contain=inputdict["dont_contain"],
                                                         dont_startwith=inputdict["dont_startwith"],
                                                         must_contain=inputdict["must_contain"],
                                                         must_startwith=inputdict["must_startwith"],
                                                         lowercase=inputdict["lowercase"])

                types_list = objgraph.most_common_types(objects=roots, limit=inputdict["nresults"],
                                                        shortnames=False, filter=finalfilter)
                for otype in types_list:
                    res += u"%s : %u\n" % otype
            except Exception as e:
                res += force_uString(e)
                self.logger.exception(e)
            finally:
                if roots:
                    del roots
                if types_list:
                    del types_list
                if finalfilter:
                    del finalfilter
        else:
            res = u"please install module 'objgraph'"
        return res

    def objgraph_common_objects(self, args):
        """
        This function can be used to display the most common objects for a running fuglu instance which can
        help finding memory leaks. For now this works best for fuglu with thread backend.

        Fuglu has to be running as a daemon.
        "fuglu_control" is used to communicate with the fuglu instance.

        Examples:
            (1) show most common fuglu objects
            -----------------------------------

            $ fuglu_control objgraph_common_objects '{"must_contain": ["fuglu"], "nresults": 5}'

            ----------------
            Most common objects:
            ----------------

            params:
            * nresults: 5
            * lowercase: True
            * dont_startwith:
            * must_startwith:
            * dont_contain:
            * must_contain: fuglu

            fuglu.extensions.filearchives.classproperty : 6
            fuglu.threadpool.Worker : 2
            fuglu.extensions.filetype.MIME_types_base : 2
            fuglu.debug.ControlSession : 2
            fuglu.connectors.smtpconnector.SMTPServer : 2
        """
        res = u"----------------\n" \
            + u"Most common objects:\n" \
            + u"----------------\n\n"

        if OBJGRAPH_EXTENSION_ENABLED:
            defaults = {"nresults": 20,
                        "lowercase": True,
                        "dont_startwith": ["builtins", "_"],
                        "dont_contain": [],
                        "must_startwith": [],
                        "must_contain": []}

            if not args:
                args = {}

            # fill filter lists and other vars from dict
            res, inputdict = ControlSession.prepare_objectgraph_list_from_dict(args, res, defaults)
            types_list = None
            finalfilter = None
            try:
                # build filter
                finalfilter = ControlSession.buildfilter(dont_contain=inputdict["dont_contain"],
                                                         dont_startwith=inputdict["dont_startwith"],
                                                         must_contain=inputdict["must_contain"],
                                                         must_startwith=inputdict["must_startwith"],
                                                         lowercase=inputdict["lowercase"])

                types_list = objgraph.most_common_types(limit=inputdict["nresults"],
                                                        shortnames=False,
                                                        filter=finalfilter)
                for otype in types_list:
                    res += u"%s : %u\n" % otype
            except Exception as e:
                res += force_uString(e)
                self.logger.exception(e)
            finally:
                if types_list:
                    del types_list
                if finalfilter:
                    del finalfilter
        else:
            res = u"please install module 'objgraph'"
        return res

    def objgraph_growth(self, args):
        """
        This function can be used to display the new objects for a running fuglu instance which can
        help finding memory leaks. For now this works best for fuglu with thread backend.

        Fuglu has to be running as a daemon.
        "fuglu_control" is used to communicate with the fuglu instance.

        Examples:
            (1) show fuglu objects after new fuglu start
            ---------------------------------------------

            $ fuglu_control objgraph_growth '{"must_contain": ["fuglu"], "nresults": 5}'

            --------------
            Object growth:
            --------------

            params:
            * nresults: 5
            * lowercase: True
            * dont_startwith:
            * must_startwith:
            * dont_contain:
            * must_contain: fuglu

            fuglu.extensions.filearchives.classproperty        6        +6
            fuglu.connectors.smtpconnector.SMTPServer          2        +2
            fuglu.threadpool.Worker                            2        +2
            fuglu.addrcheck.Default                            1        +1
            fuglu.addrcheck.Addrcheck                          1        +1

            (2) show new fuglu objects after fuglu processed a message
            ------------------------------------------------------------

            $ fuglu_control objgraph_growth '{"must_contain": ["fuglu"], "nresults": 5}'
            --------------
            Object growth:
            --------------

            params:
            * nresults: 5
            * lowercase: True
            * dont_startwith:
            * must_startwith:
            * dont_contain:
            * must_contain: fuglu

            fuglu.extensions.filetype.MIME_types_base        2        +1
            fuglu.plugins.attachment.RulesCache              1        +1
            fuglu.shared.SuspectFilter                       1        +1

        """
        res = u"--------------\n" \
              + u"Object growth:\n" \
              + u"--------------\n\n"

        if OBJGRAPH_EXTENSION_ENABLED:
            defaults = {"nresults": 20,
                        "lowercase": True,
                        "dont_startwith": ["builtins", "_"],
                        "dont_contain": [],
                        "must_startwith": [],
                        "must_contain": []}

            if not args:
                args = {}

            # fill filter lists and other vars from dict
            res, inputdict = ControlSession.prepare_objectgraph_list_from_dict(args, res, defaults)

            finalfilter = None
            result = None
            try:

                # build filter
                finalfilter = ControlSession.buildfilter(dont_contain=inputdict["dont_contain"],
                                                         dont_startwith=inputdict["dont_startwith"],
                                                         must_contain=inputdict["must_contain"],
                                                         must_startwith=inputdict["must_startwith"],
                                                         lowercase=inputdict["lowercase"])

                result = objgraph.growth(inputdict["nresults"], shortnames=False, filter=finalfilter)

                if result:
                    width = max(len(name) for name, _, _ in result)
                    for name, count, delta in result:
                        res += u'%-*s%9d %+9d\n' % (width, name, count, delta)
                else:
                    res += u'no growth captured'
            except Exception as e:
                res += force_uString(e)
                self.logger.exception(e)
            finally:
                if finalfilter:
                    del finalfilter
                if result:
                    del result
        else:
            res = u"please install module 'objgraph'"
        return res

    def objgraph_creategraph_backrefchain(self, args):
        """
        This function can be used to display what is referencing an object to find why
        an object is not garbage collected. The output is a graph.

        Requirements: objgraph and graphviz installed

        Fuglu has to be running as a daemon.
        "fuglu_control" is used to communicate with the fuglu instance.

        Examples:

            $ fuglu_control objgraph_creategraph_backrefchain '{"typelist": ["SMTPServer"]}'

            ---------------------------------
            Create Graph for backref chain:
            ---------------------------------

            params:
            * typelist: SMTPServer
            * selector: random
            * filename: /tmp/SMTPServer.png

            Graph for one object of type SMTPServer written to /tmp/SMTPServer.png

            SMTPServer.png:

            #-----------------#
            # module __main__ #
            #-----------------#
                   |
                   |   __dict__
                   |
            #---------------#
            # dict 61 items #
            #---------------#
                   |
                   |   controller
                   |
            #--------------------------------------------------#
            # MainController <fuglu.core.MainController objet> #
            #--------------------------------------------------#
                   |
                   |   __dict__
                   |
            #---------------#
            # dict 18 items #
            #---------------#
                   |
                   |   servers
                   |
            #--------------#
            # list 4 items #
            #--------------#
                   |
                   |
                   |
            #--------------------------------------------------------#
            # SMTPServer <fuglu.connectors.smtpconnector.SMTPServer> #
            #--------------------------------------------------------#

        """
        res = u"---------------------------------\n" \
              + u"Create Graph for backref chain:\n" \
              + u"---------------------------------\n\n"

        if OBJGRAPH_EXTENSION_ENABLED:
            defaults = {"max_depth": 20,
                        "filename": "",
                        "selector": "random",
                        "maxobjects": 1,
                        "typelist": ["Suspect"],
                        }

            if not args:
                args = {}

            # fill filter lists and other vars from dict
            res, inputdict = ControlSession.prepare_objectgraph_list_from_dict(args, res, defaults)
            in_chains = None
            chains = None
            backrefchain_ids = None
            all_object_ids = None

            try:
                if not len(inputdict["typelist"]) > 0 or not inputdict["typelist"]:
                    res += "Please define at least one type in 'typelist'"
                    return res

                if not inputdict["filename"]:
                    res += "Please define a non-empty filename in 'filename' key of input dict or don't define key"
                    return res

                if inputdict["selector"] not in ["first", "last", "random", "all"]:
                    res += 'Valid choices for selector are : "first", "last", "random", "all"'
                    return res

                chains = []
                all_object_ids = []
                for otype in inputdict["typelist"]:
                    olist = objgraph.by_type(otype)
                    if not olist:
                        res += u"%s: no objects\n" % otype
                    else:
                        if inputdict["selector"] == "all":
                            examine_objs = olist
                        elif inputdict["selector"] == "first":
                            examine_objs = olist[:inputdict["maxobjects"]]
                        elif inputdict["selector"] == "last":
                            examine_objs = olist[-inputdict["maxobjects"]:]
                        else:
                            import random
                            if inputdict["maxobjects"] <= 1:
                                examine_objs = [random.choice(olist)]
                            else:
                                examine_objs = random.sample(olist, min(inputdict["maxobjects"], len(olist)))

                        if not examine_objs:
                            res += 'WARNING: Object to examine is None for %s' % otype
                            continue

                        for obj in examine_objs:
                            backrefchain = objgraph.find_backref_chain(obj, objgraph.is_proper_module)

                            if not backrefchain:
                                res += 'WARNING: Backref chain is empty for %s' % otype
                                continue

                            chains.append(backrefchain)
                            backrefchain_ids = [id(x) for x in backrefchain if x]
                            all_object_ids.extend(backrefchain_ids)
                            self.logger.debug("chain is: %s" % ",".join([str(i) for i in backrefchain_ids]))
                            del backrefchain
                        del examine_objs

                chains = [chain for chain in chains if chain]  # remove empty ones

                class TmpObj(object):
                    def __init__(self, ids, logger):
                        self.ids = set(ids)
                        self.logger = logger
                        self.logger.debug("allids: %s" % ",".join([str(i) for i in self.ids]))
                    def __call__(self, x):
                        out = id(x) in self.ids
                        return out

                in_chains = TmpObj(all_object_ids, self.logger)

                max_depth = max(map(len, chains)) - 1
                objgraph.show_backrefs([chain[-1] for chain in chains], max_depth=max_depth,
                              filter=in_chains, filename=inputdict["filename"])

                res += 'Graph for one object of type(s) %s written to %s' % (",".join(inputdict["typelist"]),
                                                                             inputdict['filename'])

            except Exception as e:
                self.logger.exception(e)
                res += force_uString(e)
            finally:
                if in_chains:
                    del in_chains
                if chains:
                    del chains
                if backrefchain_ids:
                    del backrefchain_ids
                if all_object_ids:
                    del all_object_ids
        else:
            res = u"please install module 'objgraph' and 'graphviz'"
        return res

    def objgraph_creategraph_backrefs(self, args):
        """
        This function can be used to display what is referencing an objects eventually explaining why
        an object is not garbage collected. The output is a graph.

        Requirements: objgraph and graphviz installed

        Fuglu has to be running as a daemon.
        "fuglu_control" is used to communicate with the fuglu instance.

        Examples:

            $ fuglu_control objgraph_creategraph_backrefs '{"typelist": ["ControlSession"],"dont_startwith":[],"max_depth":5}'
            ---------------------------------
            Create Graph for backref chain:
            ---------------------------------

            params:
            * maxobjects: 20
            * lowercase: True
            * dont_startwith:
            * must_startwith:
            * dont_contain:
            * must_contain:
            * typelist: ControlSession
            * max_depth: 5
            * selector: all
            * filename: /tmp/ControlSession.png

            Graph for one object of type(s) ControlSession written to /tmp/ControlSession.png


        """
        res = u"---------------------------------\n" \
              + u"Create Graph for backref chain:\n" \
              + u"---------------------------------\n\n"

        if OBJGRAPH_EXTENSION_ENABLED:
            defaults = {"max_depth": 3,
                        "filename": "",
                        "selector": "all",
                        "maxobjects": 20,
                        "typelist": ["Suspect"],
                        "lowercase": True,
                        "dont_startwith": ["_"],
                        "dont_contain": [],
                        "must_startwith": [],
                        "must_contain": []
                        }

            if not args:
                args = {}

            # fill filter lists and other vars from dict
            res, inputdict = ControlSession.prepare_objectgraph_list_from_dict(args, res, defaults)

            finalfilter = None
            list_objects = None

            try:
                if not len(inputdict["typelist"]) > 0 or not inputdict["typelist"]:
                    res += "Please define at least one type in 'typelist'"
                    return res

                if not inputdict["filename"]:
                    res += "Please define a non-empty filename in 'filename' key of input dict or don't define key"
                    return res

                if inputdict["selector"] not in ["first", "last", "random", "all"]:
                    res += 'Valid choices for selector are : "first", "last", "random", "all"'
                    return res

                list_objects = []
                for otype in inputdict["typelist"]:
                    olist = objgraph.by_type(otype)
                    if not olist:
                        res += u"%s: no objects\n" % otype
                    else:
                        if inputdict["selector"] == "all":
                            examine_obj = olist
                        elif inputdict["selector"] == "first":
                            examine_obj = olist[:inputdict["maxobjects"]]
                        elif inputdict["selector"] == "last":
                            examine_obj = olist[-inputdict["maxobjects"]:]
                        else:
                            import random
                            if inputdict["maxobjects"] <= 1:
                                examine_obj = [random.choice(olist)]
                            else:
                                examine_obj = random.sample(olist, min(inputdict["maxobjects"], len(olist)))

                        list_objects.extend(examine_obj)

                        del examine_obj
                        del olist

                if not list_objects:
                    res += 'No objects found -> return'
                    return res

                # build filter
                finalfilter = ControlSession.buildfilter(dont_contain=inputdict["dont_contain"],
                                                         dont_startwith=inputdict["dont_startwith"],
                                                         must_contain=inputdict["must_contain"],
                                                         must_startwith=inputdict["must_startwith"],
                                                         lowercase=inputdict["lowercase"])

                objgraph.show_backrefs(list_objects,
                                       max_depth=inputdict["max_depth"],
                                       filter=finalfilter,
                                       filename=inputdict["filename"],
                                       refcounts=True,
                                       shortnames=False)

                res += 'Graph for one object of type(s) %s written to %s' % (",".join(inputdict["typelist"]), inputdict['filename'])


            except Exception as e:
                res += u"Exception: %s" % force_uString(e)
                self.logger.exception(e)
            finally:
                if finalfilter:
                    del finalfilter
                if list_objects:
                    del list_objects
        else:
            res = u"please install module 'objgraph' and 'graphviz'"
        return res

    @staticmethod
    def prepare_objectgraph_list_from_dict(args, res, defaults):

        keys = [k for k in defaults.keys()]
        outdict = {}

        res += "params:\n"

        if "nresults" in keys:
            nresults = int(args.get("nresults", defaults["nresults"]))
            outdict["nresults"] = nresults
            res += "* nresults: %u\n" % nresults

        if "maxobjects" in keys:
            maxobjects = int(args.get("maxobjects", defaults["maxobjects"]))
            outdict["maxobjects"] = maxobjects
            res += "* maxobjects: %u\n" % maxobjects

        if "lowercase" in keys:
            lowercase = args.get("lowercase", defaults["lowercase"])
            outdict["lowercase"] = lowercase
            res += "* lowercase: %s\n" % lowercase

        if "dont_startwith" in keys:
            dont_startwith = ControlSession.preparelist(args, "dont_startwith", defaults["dont_startwith"])
            outdict["dont_startwith"] = dont_startwith
            res += "* dont_startwith: %s\n" % ",".join(dont_startwith)

        if "must_startwith" in keys:
            must_startwith = ControlSession.preparelist(args, "must_startwith", defaults["must_startwith"])
            outdict["must_startwith"] = must_startwith
            res += "* must_startwith: %s\n" % ",".join(must_startwith)

        if "dont_contain" in keys:
            dont_contain = ControlSession.preparelist(args, "dont_contain", defaults["dont_contain"])
            outdict["dont_contain"] = dont_contain
            res += "* dont_contain: %s\n" % ",".join(dont_contain)

        if "must_contain" in keys:
            must_contain = ControlSession.preparelist(args, "must_contain", defaults["must_contain"])
            outdict["must_contain"] = must_contain
            res += "* must_contain: %s\n" % ",".join(must_contain)

        if "typelist" in keys:
            typelist = ControlSession.preparelist(args, "typelist", defaults["typelist"])
            outdict["typelist"] = typelist
            res += "* typelist: %s\n" % ",".join(typelist)

        if "max_depth" in keys:
            maxdepth = int(args.get("max_depth", defaults["max_depth"]))
            outdict["max_depth"] = maxdepth
            res += "* max_depth: %u\n" % maxdepth

        if "selector" in keys:
            selector = force_uString(args.get("selector", defaults["selector"]))
            outdict["selector"] = selector
            res += "* selector: %s\n" % selector

        if "filename" in keys:
            filename = force_uString(args.get("filename", defaults["filename"]))
            if not filename and len(outdict.get("typelist", [])) > 0:
                filename = os.path.join("/tmp", ".".join(outdict["typelist"])+".png")

            outdict["filename"] = filename
            res += "* filename: %s\n" % filename

        res += "\n"

        return res, outdict

    @staticmethod
    def json_string_to_obj(jsonstring, ForcedType=None):
        import json
        pyobject = None
        if jsonstring:
            pyobject = json.loads(jsonstring)
        if ForcedType is not None:
            if not isinstance(pyobject,ForcedType):
                pyobject = ForcedType()
        return pyobject

    @staticmethod
    def preparelist(argsdict, key, default):
        """
        Prepare lists as received in arguments dict for objgraph functions.
        Make sure type is list and it contains strings.

        Args:
            argsdict (dict): arguments dict
            key (str): key in the argsdict dictionary
            default (list): list containing default element

        Returns:
            list

        """

        # force_uString will convert each element of the list ..
        newlist = force_uString(argsdict.get(key, default))
        # ... unless the input is not a list. However force_uString
        # will create a uniocode string in this case. Pack it into a list.
        if not isinstance(newlist, list):
            newlist = [newlist]

        return newlist

    @staticmethod
    def buildfilter(input_to_string=objgraph._long_typename, dont_startwith=[],
                    must_startwith=[], dont_contain=[], must_contain=[], lowercase=True):
        """
        Build a filter that can be passed to the obgraph filter keyword

        Args:
            input_to_string (function): function to convert the filter input to a string
            dont_startwith (list): list of strings, none of them is allowed to appear at the beginning of the line
            must_startwith (list): list of strings, one of them must appear at the beginning of the line
            dont_contain (list): list of strings, none of them is allowed to appear in the line
            must_contain (list): list of strings, one of them has to appear in the line
            lowercase (bool): user lowercase comparison

        Returns:
            function
        """

        # build filter
        filters = []
        for dsw in dont_startwith:
            # dsw=dsw sets the value in the lambda to what is the current
            # value, otherwise it will use the last value from the scope
            if lowercase:
                filters.append(lambda o, dsw=dsw: not o.lower().startswith(dsw.lower()))
            else:
                filters.append(lambda o, dsw=dsw: not o.startswith(dsw))

        if must_startwith:
            # use a help class to combine the filters
            # - we can't create a lambda using a set of lambda's because
            #   the "any_filter" list is mutable
            class TmpConstruct(object):

                def __init__(self, must_startwith):
                    self.any_filter = []
                    for msw in must_startwith:
                        # msw=msw sets the value in the lambda to what is the current
                        # value, otherwise it will use the last value from the scope
                        if lowercase:
                            self.any_filter.append(lambda o, msw=msw: o.lower().startswith(msw.lower()))
                        else:
                            self.any_filter.append(lambda o, msw=msw: o.startswith(msw))

                def __call__(self, o):
                    return any(x(o) for x in self.any_filter)

            filters.append(TmpConstruct(must_startwith))

        for dcn in dont_contain:
            # dcn=dcn sets the value in the lambda to what is the current
            # value, otherwise it will use the last value from the scope
            if lowercase:
                filters.append(lambda o, dcn=dcn: dcn.lower() not in o.lower())
            else:
                filters.append(lambda o, dcn=dcn: dcn not in o)

        if must_contain:
            # use a help class to combine the filters
            class TmpConstruct(object):

                def __init__(self, must_contain):
                    self.any_filter = []
                    for mcn in must_contain:
                        # mcn=mcn sets the value in the lambda to what is the current
                        # value, otherwise it will use the last value from the scope
                        if lowercase:
                            self.any_filter.append(lambda o: mcn.lower() in o.lower())
                        else:
                            self.any_filter.append(lambda o: mcn in o)

                def __call__(self, o):
                    return any(x(o) for x in self.any_filter)

            filters.append(TmpConstruct(must_contain))

        finalfilter = lambda o: all(x(input_to_string(o)) for x in filters)

        return finalfilter


class CrashStore(object):
    exceptions = []

    @staticmethod
    def store_exception(exc_info=None, thread=None):
        if exc_info is None:
            exc_info = sys.exc_info()

        if thread is None:
            thread = threading.currentThread()

        name = thread.getName()
        info = ""
        if hasattr(thread, 'threadinfo'):
            info = thread.threadinfo
        desc = "%s (%s)" % (name, info)

        maxtracebacks = 10
        CrashStore.exceptions.append((exc_info, time.time(), desc),)
        while len(CrashStore.exceptions) > maxtracebacks:
            CrashStore.exceptions.pop(0)

