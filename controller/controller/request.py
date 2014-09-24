import json

from sqlalchemy import Column, String, BigInteger, DateTime, func

# pylint: disable=import-error,no-name-in-module
from akiri.framework.ext.sqlalchemy import meta
# pylint: enable=import-error,no-name-in-module

class XIDEntry(meta.Base):
    #pylint: disable=no-init
    __tablename__ = 'xid'

    xid = Column(BigInteger, unique=True, nullable=False, \
                 autoincrement=True, primary_key=True)
    # FIXME: Enumerate valid state values.
    state = Column(String, default='started')
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(), \
                               server_onupdate=func.current_timestamp())

class Request(object):
    """Represents a request.
       Creates a body and adds:
        command: <command>
        xid: <xid>
        body: <body>
    """

    def __init__(self, action, send_body_dict=None, xid=None):
        self.action = action

        session = meta.Session()
        entry = None
        if xid:
            entry = session.query(XIDEntry).\
                filter(XIDEntry.xid == xid).\
                one()
        else:
            entry = XIDEntry()
            session.add(entry)
            session.commit()
        self.xid = entry.xid

        if send_body_dict is None:
            send_body_dict = {}
        send_body_dict["action"] = action
        send_body_dict["xid"] = self.xid
        self.send_body = json.dumps(send_body_dict)

        if send_body_dict["action"] == 'cleanup':
            entry.state = "finished"
            session.commit()

    def __repr__(self):
        return "<action: %s, body_dict: %s, xid: %d>" % \
            (self.action, self.send_body, self.xid)

class CliStartRequest(Request):
    def __init__(self, cli_command, env=None, immediate=False):
        d = {"cli": cli_command}
        if env:
            d["env"] = env
        if immediate:
            d["immediate"] = immediate
        super(CliStartRequest, self).__init__("start", d)

class CleanupRequest(Request):
    def __init__(self, xid):
        super(CleanupRequest, self).__init__("cleanup", xid=xid)
