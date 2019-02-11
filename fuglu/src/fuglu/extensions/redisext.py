import threading
from time import sleep

try:
    import redis
    from redis import StrictRedis
    STATUS = "redis installed, version: {}".format(redis.__version__)
    ENABLED = True
except:
    STATUS = "redis not installed"
    ENABLED = False


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

        super(RedisKeepAlive, self).__init__(*args, **kwargs)

        # start a thread which will ping the server to keep
        if self._pinginterval > 0:
            self.pingthread = threading.Thread(target=self.ping_and_wait)
            self.pingthread.daemon = True
            self.pingthread.start()

    def ping_and_wait(self):
        """Send a ping to the Redis server to keep connection alive"""
        while True:
            self.ping()
            sleep(self._pinginterval)


