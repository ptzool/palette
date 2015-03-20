import logger
import string
import threading
import time
import os

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, func
from sqlalchemy.schema import ForeignKey, UniqueConstraint
from sqlalchemy.orm.exc import NoResultFound

from util import traceback_string

import akiri.framework.sqlalchemy as meta

from state import StateManager
from agentmanager import AgentManager
from agent import Agent
from event_control import EventControl
from state_transitions import TRANSITIONS
from general import SystemConfig

class TableauProcess(meta.Base):
    # pylint: disable=no-init
    # NOTE: the above warning is erroneous generated for this class.
    __tablename__ = 'tableau_processes'

    ### Possible status as reported by "tabadmin status [...]"
    STATUS_RUNNING = "RUNNING"
    STATUS_STOPPED = "STOPPED"
    STATUS_DEGRADED = "DEGRADED"
    STATUS_UNKNOWN = "UNKNOWN"    # We set this if we don't know yet.

    name = Column(String, nullable=False, primary_key=True)
    agentid = Column(BigInteger,
                     ForeignKey("agent.agentid", ondelete='CASCADE'),
                     nullable=False, primary_key=True)
    pid = Column(Integer)
    status = Column(String)
    creation_time = Column(DateTime, server_default=func.now())
    modification_time = Column(DateTime, server_default=func.now(),
                               server_onupdate=func.current_timestamp())
    UniqueConstraint('agentid', 'name')

class TableauStatusMonitor(threading.Thread):
    # pylint: disable=too-many-instance-attributes

    # Note: If there is a value in the system table, it is
    # used instead of these defaults.
    # Default interval for checking tableau status (in seconds)
    STATUS_REQUEST_INTERVAL_DEFAULT = 10

    # Minimum amount of time that must elapse while DEGRADED
    # before sending out the DEGRADED event.
    EVENT_DEGRADED_MIN_DEFAULT = 120    # in seconds

    LOGGER_NAME = "status"

    statemap = {
        TableauProcess.STATUS_RUNNING: StateManager.STATE_STARTED,
        TableauProcess.STATUS_STOPPED: StateManager.STATE_STOPPED,
        TableauProcess.STATUS_DEGRADED: StateManager.STATE_DEGRADED,
        TableauProcess.STATUS_UNKNOWN: StateManager.STATE_DISCONNECTED
    }

    def __init__(self, server, manager):
        super(TableauStatusMonitor, self).__init__()
        self.server = server
        self.rwlock = self.server.upgrade_rwlock
        self.manager = manager # AgentManager instance
        self.st_config = SystemConfig(server.system)
        self.log = logger.get(self.LOGGER_NAME)
        self.log.setLevel(self.st_config.debug_level)
        self.envid = self.server.environment.envid

        self.first_degraded_time = None
        self.sent_degraded_event = False

        # Start fresh: status table
        session = meta.Session()
        self.remove_all_status()
        session.commit()

        self.stateman = StateManager(self.server)

    # Remove all entries to get ready for new status info.
    def remove_all_status(self):
        """
            Note a session is passed.  When updating the status table,
            we don't want everything to go away (commit) until we've added
            the new entries.
        """

        # FIXME: Need to figure out how to do this in session.query:
        #        DELETE FROM status USING agent
        #          WHERE status.agentid = agent.agentid
        #            AND agent.domainid = self.domainid;
        #
        # This may do it:
        #
        # subq = session.query(TableauProcess).\
        #   join(Agent).\
        #   filter(Agent.domainid == self.domainid).\
        #   subquery()
        #
        # session.query(TableauProcess).\
        #   filter(TableauProcess.agentid,in_(subq)).\
        #   delete()

        meta.Session.query(TableauProcess).delete()

        # Intentionally don't commit here.  We want the existing
        # rows to be available until the new rows are inserted and
        # committed.

    def _add(self, agentid, name, pid, status):
        """Note a session is passed.  When updating the status table, we
        do remove_all_status, then slowly add in the new status before
        doing the commit, so the table is not every empty/building if
        somebody checks it.
        """

        session = meta.Session()
        entry = TableauProcess(agentid=agentid, name=name,
                               pid=pid, status=status)
        session.add(entry)

    def get_tableau_status(self):
        try:
            return meta.Session().query(TableauProcess).\
                join(Agent).\
                filter(Agent.envid == self.envid).\
                filter(Agent.agent_type == 'primary').\
                filter(TableauProcess.name == 'Status').\
                one().status
        except NoResultFound:
            return TableauProcess.STATUS_UNKNOWN

    def _set_main_state(self, prev_tableau_status, tableau_status, agent, body):
        prev_state = self.stateman.get_state()

        if tableau_status not in (TableauProcess.STATUS_RUNNING,
                                  TableauProcess.STATUS_STOPPED,
                                  TableauProcess.STATUS_DEGRADED):
            self.log.error("status-check: Unknown reported tableau_status " + \
                "from tableau: %s.  prev_state: %s", tableau_status, prev_state)
            return  # fixme: do something more drastic than return?

        if prev_state not in TRANSITIONS:
            self.log.error("status-check: prev state unexpected: %s",
                            prev_state)
            return  # fixme: do something more drastic than return?

        # Get our new state and events to send based on the previous
        # state and new tableau status.
        new_state_info = TRANSITIONS[prev_state][tableau_status]

        self.log.debug("status-check: prev_state: %s, new state info: %s, " + \
                       "prev_tableau_status %s, tableau_status: %s",
                       prev_state, str(new_state_info),
                       prev_tableau_status, tableau_status)

        if 'state' in new_state_info:
            self.stateman.update(new_state_info['state'])

        if 'events' not in new_state_info:
            events = []
        else:
            events = new_state_info['events']
        if type(events) == type(EventControl.INIT_STATE_STARTED):
            events = [events]

        self._send_events(events, agent, body)

        if 'maint-stop' in new_state_info:
            # Make sure the maint server(s) are stopped if tableau
            # is not stopped.  For example, the user stopped
            # tableau via 'tabadmin stop' and then restarted it with
            # 'tabadmin start' without going through the Palette UI.
            self.log.debug("status-check: May stop maint server. " + \
                           "prev_state: %s, new state info: %s, " + \
                           "prev_tableau_status %s, tableau_status: %s, " + \
                           "maint_started: %s",
                           prev_state, str(new_state_info),
                           prev_tableau_status, tableau_status,
                           str(self.server.maint_started))

            if not self.server.maint_started:
                self.log.debug("state-check: maint server not running")
                return

            self.server.maint("stop")

        if 'maint-start' in new_state_info:
            # Make sure the maint server(s) are started if tableau
            # is stopped.  For example, the user stopped
            # tableau via 'tabadmin stop' and then the controller
            # started at that point (small chance, but possible).
            # We want to set the maint_started status.
            # We assume the user wanted the maint server started,
            # but can't be sure.
            self.log.debug("status-check: Will start maint server. " + \
                           "prev_state: %s, new state info: %s, " + \
                           "prev_tableau_status %s, tableau_status: %s, " + \
                           "maint_started: %s",
                           prev_state, str(new_state_info),
                           prev_tableau_status, tableau_status,
                           str(self.server.maint_started))

            if self.server.maint_started:
                self.log.debug("state-check: maint server already running")
                return

            self.server.maint("start")

    def _send_events(self, events, agent, body):
        """Send the events according to the old and new states.
           However, don't send DEGRADED-related events until
           Tableau has a chance to recover, since that's what it does."""
        if events:
            data = agent.todict()

        new_degraded_event = False
        for event in events:
            if event == EventControl.STATE_STARTED_AFTER_DEGRADED and \
                                        not self.sent_degraded_event:
                # We were degraded, and are running now, but never
                # sent out a degraded event, so don't send a
                # "no more degraded" event either.
                continue

            if event != EventControl.STATE_DEGRADED:
                self.server.event_control.gen(event, data)

                if event == EventControl.INIT_STATE_DEGRADED:
                    # If this is an "INIT_STATE_*" event, we send it,
                    # even if it is degraded.
                    self.sent_degraded_event = False
                continue

            new_degraded_event = True

            # Don't send the DEGRADED event until a minimum period of time
            # has elapsed with the state still DEGRADED.
            if not self.first_degraded_time:
                # Remember the time of the first DEGRADED state.
                self.first_degraded_time = time.time()
                continue

            if self.sent_degraded_event:
                # Already sent the degraded event
                continue

            try:
                event_degraded_min = \
                    int(self.server.system.get('event-degraded-min'))
            except ValueError:
                event_degraded_min = self.EVENT_DEGRADED_MIN_DEFAULT

            now = time.time()
            self.log.debug("status-check: now %d, first %d, min %d, diff %d",
                           now, self.first_degraded_time,
                           event_degraded_min,
                           now - self.first_degraded_time)
            if now - self.first_degraded_time >= event_degraded_min:
                self.log.debug("status-check: Sending degraded")
                self.server.event_control.gen(event,
                                      dict(body.items() + data.items()))
                self.sent_degraded_event = True

        if not new_degraded_event:
            self.first_degraded_time = None
            self.sent_degraded_event = False

    def run(self):
        try:
            self.tableau_status_loop()
        except (SystemExit, KeyboardInterrupt, GeneratorExit):
            raise
        except BaseException:
            line = traceback_string(all_on_one_line=False)
            self.server.event_control.gen(EventControl.SYSTEM_EXCEPTION,
                                      {'error': line,
                                       'version': self.server.version})
            self.log.error("status-check: Fatal: " + \
                           "Exiting tableau_status_loop on exception.")
            # pylint: disable=protected-access
            os._exit(93)

    def tableau_status_loop(self):
        while True:
            self.log.debug("status-check: About to timeout or " + \
                           "wait for a new primary to connect")
            try:
                status_request_interval = \
                    int(self.server.system.get('status-request-interval'))
            except ValueError:
                status_request_interval = \
                                self.STATUS_REQUEST_INTERVAL_DEFAULT

            new_primary = self.manager.new_primary_event.wait(
                                        status_request_interval)

            self.log.debug("status-check: new_primary: %s", new_primary)
            if new_primary:
                self.manager.new_primary_event.clear()

            session = meta.Session()
            try:
                # Don't do a 'tabadmin status -v' if upgrading
                acquired = self.rwlock.read_acquire(blocking=False)
                if not acquired:
                    self.log.debug("status-check: Upgrading.  Won't run.")
                    continue
                self.check_status()
            finally:
                if acquired:
                    self.rwlock.read_release()
                session.rollback()
                meta.Session.remove()

    def check_status(self):

        self.log.setLevel(self.st_config.debug_level)
        # FIXME: Tie agent to domain.
        agent = self.manager.agent_by_type(AgentManager.AGENT_TYPE_PRIMARY)
        if not agent:
            self.log.debug("status-check: The primary agent is either " + \
                           "not connected or not enabled.")
            return

        aconn = agent.connection
        if not aconn:
            session = meta.Session()
            self.log.debug(
                    "status-check: No primary agent currently connected.")
            self.remove_all_status()
            session.commit()
            return

        # Don't do a 'tabadmin status -v' if the user is doing an action.
        acquired = aconn.user_action_lock(blocking=False)
        if not acquired:
            self.log.debug(
                "status-check: Primary agent locked for user action. " + \
                "Skipping status check.")
            return

        # We don't force the user to delay starting their request
        # until the 'tabadmin status -v' is finished.
        aconn.user_action_unlock()

        self.check_status_with_connection(agent)

    def check_status_with_connection(self, agent):
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        agentid = agent.agentid

        body = self.server.status_cmd(agent)
        if 'error' in body:
            self.log.error(
                "status-check: Error from tabadmin status command: %s",
                str(body))
            return

        if 'exit-status' in body:
            if body['exit-status']:
                self.log.error("status-check: Failed exit status: %d for " + \
                               "tabadmin status command: %s",
                               body['exit-status'], str(body))
                return
        else:
            self.log.error("status-check: Missing exit-status from " + \
                           "tabadmin status command: %s", str(body))
            return

        if not body.has_key('stdout'):
            # fixme: Probably update the status table to say
            # something's wrong.
            self.log.error("status-check: No output received for " + \
                           "status monitor. body: " + str(body))
            return

        stdout = body['stdout']
        lines = string.split(stdout, '\n')

        session = meta.Session()

        prev_tableau_status = self.get_tableau_status()

        self.remove_all_status()
        # Do not commit until after the table is added to.
        # Otherwise, the table could be empty temporarily.

        tableau_status = None
        for line in lines:
            parts = line.strip().split(' ')

            # 'Tableau Server Repository Database' (1764) is running.
            if parts[0] == "'Tableau" and parts[1] == 'Server':
                if agentid:
                    status = parts[-1:][0]     # "running."
                    status = status[:-1]       # "running" (no period)
                    pid_part = parts[-3:-2][0] # "(1764)"
                    pid_str = pid_part[1:-1]   # "1764"
                    try:
                        pid = int(pid_str)
                    except StandardError:
                        self.log.error("status-check: Bad PID: " + pid_str)
                        continue

                    del parts[0:2]  # Remove 'Tableau' and 'Server'
                    del parts[-3:]  # Remove ['(1764)', 'is', 'running.']
                    name = ' '.join(parts)  # "Repository Database'"
                    if name[-1:] == "'":
                        # Cut off trailing single quote (')
                        name = name[:-1]

                    self._add(agentid, name, pid, status)
                    self.log.debug("status-check: logged: %s, %d, %s", name,
                                   pid, status)
                else:
                    # FIXME: log error
                    pass
            elif parts[0] == 'Status:':
                server_status = parts[1].strip()
                if agentid:
                    self._add(agentid, "Status", 0, server_status)
                    if tableau_status == None or server_status == 'DEGRADED':
                        tableau_status = server_status
                else:
                    # FIXME: log error
                    pass
            else:
                line = line.strip()
                if line[-1:] == ':':
                    # A hostname or IP address is specified: new section
                    host = parts[0].strip().replace(':', '')
                    agentid = Agent.get_agentid_from_host(self.envid, host)
                else:
                    # Example: "Connection error contacting worker 1"
                    if not agentid:
                        self.log.debug("status-check: Can't log due to " + \
                                       "unknown or disabled agent: %s, %d, %s",
                                       line, -1, 'error')
                    else:
                        self._add(agentid, line, -1, 'error')
                        self.log.debug("status-check: logged: %s, %d, %s",
                                       line, -1, 'error')

        aconn = agent.connection
        acquired = aconn.user_action_lock(blocking=False)
        if not acquired:
            # If the user_action_lock is taken, that thread should
            # control the state.  We don't update the tableau process
            # table since state should be consistent with tableau process
            # status.
            self.log.debug(
                "status-check: Primary agent locked for user action " + \
                "after tabadmin status finished.  " + \
                "Will not update state or tableau status.")
            session.rollback()
            return

        if tableau_status is None:
            self.log.error("status-check: Tableau status not valid: %s",
                           str(lines))
            aconn.user_action_unlock()
            session.rollback()
            return

        self._set_main_state(prev_tableau_status, tableau_status, agent, body)
        self.log.debug("status-check: Logging main status: %s", tableau_status)

        session.commit()

        aconn.user_action_unlock()
