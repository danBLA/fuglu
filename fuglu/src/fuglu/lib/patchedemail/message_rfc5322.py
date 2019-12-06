from typing import Optional
from email.message import EmailMessage
from .message import PatchedGenerator
from io import StringIO
from email.policy import Policy


class PatchedMessage(EmailMessage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def as_string(self,
                  unixfrom: bool = False,
                  maxheaderlen: int = 0,
                  policy: Optional[Policy] = None) -> str:
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
