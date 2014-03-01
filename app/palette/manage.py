import socket

from webob import exc

from akiri.framework.api import RESTApplication, DialogPage
from akiri.framework.config import store

import sqlalchemy
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import meta
from . import Session

from inits import *
from controller.agentstatus import AgentStatusEntry

class ManageApplication(RESTApplication):

    NAME = 'manage'

    def send_cmd(self, cmd):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect(("", CONTROLLER_TELNET_PORT))
        conn.send(cmd + '\n')
        print "sent", cmd
        data = conn.recv(3).strip()
        print "got", data
        if data != 'OK':
            # fix me: do something
            print "Bad result back from the controller."
        conn.close()

    def handle_start(self, req):

        self.send_cmd("start")
        return {}

    def handle_stop(self, req):
        self.send_cmd("stop")
        return {}

    def handle(self, req):
        if req.method != "POST":
            raise exc.HTTPMethodNotAllowed()
        action = req.POST['action'].lower()
        if action == 'start':
            return self.handle_start(req)
        elif action == 'stop':
            return self.handle_stop(req)
        raise exc.HTTPBadRequest()
        
class ManageAdvancedDialog(DialogPage):

    NAME = "manage"
    TEMPLATE = "manage.mako"

    def __init__(self, global_conf):
        super(ManageAdvancedDialog, self).__init__(global_conf)

        self.domainname = store.get('palette', 'domainname')
        print "domainname=" + self.domainname

        db_session = Session()
        self.agents = db_session.query(AgentStatusEntry).all()
        for agent in self.agents:
            if agent.connected():
                agent.last_connection_time_str = str(agent.last_connection_time)[:19] # Cut off fraction
                agent.last_disconnect_time_str = "-"
            else:
                agent.last_connection_time_str = str(agent.last_connection_time)[:19] # Cut off fraction
                agent.last_disconnect_time_str = str(agent.last_disconnect_time)[:19] # Cut off fraction
        db_session.close()
