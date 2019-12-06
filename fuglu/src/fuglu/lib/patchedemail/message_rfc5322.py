from email.message import EmailMessage
from .message import PatchedGenerator
from io import StringIO


class PatchedMessage(EmailMessage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def as_string(self, unixfrom=False, maxheaderlen=0, policy=None):
        """
        Return the entire formatted message as a string.

        Overwrites the original method to use patched version of generator
        """
        policy = self.policy if policy is None else policy
        fp = StringIO()
        g = PatchedGenerator(fp,
                             mangle_from_=False,
                             maxheaderlen=maxheaderlen,
                             policy=policy)
        g.flatten(self, unixfrom=unixfrom)
        return fp.getvalue()
