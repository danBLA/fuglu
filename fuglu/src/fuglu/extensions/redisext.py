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
import threading
from time import sleep

try:
    import redis
    from redis import StrictRedis
    STATUS = "redis installed, version: {}".format(redis.__version__)
    ENABLED = True
except ImportError:
    STATUS = "redis not installed"
    ENABLED = False
    StrictRedis = object
    redis = None


class RedisKeepAlive(StrictRedis):
    """
    Wrap standard Redis client to include a thread that
    will keep sending a ping to the server which will prevent
    connection timeout due to "timeout" setting in "redis.conf"

    Issue on github:
    https://github.com/andymccurdy/redis-py/issues/722
    """

    def __init__(self, *args, **kwargs):

        # check if pinginterval is given in kwargs
        self._pinginterval = kwargs.pop("pinginterval", 0)
        self._noisy = False

        super(RedisKeepAlive, self).__init__(*args, **kwargs)

        # start a thread which will ping the server to keep
        if self._pinginterval > 0:
            self.pingthread = threading.Thread(target=self.ping_and_wait)
            self.pingthread.daemon = True
            self.pingthread.start()

    def ping_and_wait(self):
        """Send a ping to the Redis server to keep connection alive"""
        while True:
            if self._noisy:
                import logging
                logging.getLogger("fuglu.RedisKeepAlive").debug("Sending ping to Redis Server")
            self.ping()
            sleep(self._pinginterval)


