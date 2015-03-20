import time, datetime

from sqlalchemy import Column, BigInteger, Float, DateTime, func

from sqlalchemy.schema import ForeignKey

import akiri.framework.sqlalchemy as meta

from event_control import EventControl
from general import SystemConfig

#from event_control import EventControl

class MetricEntry(meta.Base):
    # pylint: disable=no-init
    __tablename__ = "metrics"

    metricid = Column(BigInteger, unique=True, nullable=False,
                             autoincrement=True, primary_key=True)

    agentid = Column(BigInteger,
                     ForeignKey("agent.agentid", ondelete='CASCADE'),
                     nullable=False)

    cpu = Column(Float)
    creation_time = Column(DateTime, server_default=func.now())

class MetricManager(object):

    def __init__(self, server):
        self.server = server
        self.log = server.log
        self.notifications = self.server.notifications
        self.st_config = SystemConfig(server.system)

    def add(self, agent, cpu):
        session = meta.Session()

        entry = MetricEntry(agentid=agent.agentid, cpu=cpu)
        session.add(entry)
        session.commit()

    def prune(self):
        """Prune/remove old rows from the metrics table."""

        try:
            metric_save_days = self.st_config.metric_save_days
        except ValueError as ex:
            return {'error': str(ex)}

        self.log.debug("metrics: prune save %d days", metric_save_days)

        stmt = ("DELETE FROM metrics " + \
                "WHERE creation_time < NOW() - INTERVAL '%d DAYS'") % \
                (metric_save_days)

        connection = meta.get_connection()
        result = connection.execute(stmt)
        connection.close()

        self.log.debug("metrics: pruned %d rows", result.rowcount)
        return {'status': "OK", 'pruned': result.rowcount}

    def check(self, metric='cpu'):
        # pylint: disable=too-many-locals
        if metric != 'cpu':
            return {'error': 'Unknown metric: %s' % metric}

        try:
            cpu_load_warn = self.st_config.cpu_load_warn
            cpu_load_error = self.st_config.cpu_load_error
            cpu_period_warn = self.st_config.cpu_period_warn
            cpu_period_error = self.st_config.cpu_period_error
        except ValueError as ex:
            return {'error': str(ex)}

        connection = meta.get_connection()

        results = []

        agents = self.server.agentmanager.all_agents()
        for key in agents.keys():
            agent = agents[key]

            error_report = self._cpu_above_threshold(connection,
                                    agent, cpu_load_error,
                                    cpu_period_error)
            self.log.debug("metrics: error_report '%s': %s",
                            agent.displayname, str(error_report))

            if error_report['above'] != 'yes':
                warn_report = self._cpu_above_threshold(connection,
                                    agent, cpu_load_warn,
                                    cpu_period_warn)

                self.log.debug("metrics: warn_report '%s': %s",
                                agent.displayname, str(warn_report))
                if error_report['above'] == 'unknown' and \
                                    warn_report['above'] == 'unknown':
                    results.append({"displayname": agent.displayname,
                                    "status": "unknown",
                                    "info": ("No data yet: " + \
                                    "error/warning %d/%d seconds") % \
                                    (cpu_period_error, cpu_period_warn)})
                    continue

            if error_report['above'] == 'yes':
                color = 'red'
                report_value = error_report['value']
                description = "%d > %d" % (report_value, cpu_load_error)
            elif warn_report['above'] == 'yes':
                color = 'yellow'
                report_value = warn_report['value']
                description = "%d > %d" % (report_value, cpu_load_warn)
            else:
                color = 'green'
                if error_report['above'] != 'unknown':
                    report_value = error_report['value']
                else:
                    report_value = warn_report['value']
                description = "%d" % report_value

            result = self._report('cpu', connection, agent, color,
                                  report_value, description)
            results.append(result)

        connection.close()

        if not len(results):
            return {'status': 'OK', 'info': 'No agents connected.'}
        return {'status': 'OK', 'info': results}

    def _report(self, name, connection, agent, color, report_value,
                description):
        # pylint: disable=too-many-arguments
        """
            Generates an event, if appropriate and updates the
            relevant notification row.

            Arguments:
                text name used for the notifications table and
                debug messages.

            Returns a dictionary for the report.
        """
        notification = self.notifications.get(name, agent.agentid)
        self.log.debug(
            ("metric: %s.  agent '%s', color '%s', " + \
            "notified_color '%s', report_value %d") % \
            (name, agent.displayname, color,
            str(notification.notified_color), report_value))

        if color != notification.notified_color:
            if color != 'green' or \
                        (color == 'green' and notification.notified_color):
                self._gen_event("CPU Load", agent, color, report_value)

                stmt = ("UPDATE notifications " + \
                        "SET color='%s', notified_color='%s', " +
                        "description='%s'" + \
                        "WHERE notificationid=%d") % \
                        (color, color, description, notification.notificationid)

                connection.execute(stmt)

        return {"displayname": agent.displayname,
                "status": color,
                "value": report_value}

    def _cpu_above_threshold(self, connection, agent, threshold, period):
        """Checks the data for the last "period" seconds.
           If the most recent sample does not include data for
           more than "period" seconds, then return "status": "no" since
           the data is too new.

           Otherwise, if the average of the samples is below the threshold,
           then return "no" or if the average of the samples is above
           or equal to the threshold, then return "yes".

           Returns a dictionary:
                above: 'yes', 'no' or 'unknown'
                value: the average, if 'above' value is not 'unknown'
        """

        self.log.debug(
            "metrics: _cpu_above_threshold '%s', threshold %d, period %d",
            agent.displayname, threshold, period)
        if not agent.last_connection_time:
            self.log.error("metrics: no last_connection_time for '%s'",
                            agent.displayname)
            return {"above": "unknown"}

        # Seconds since the epoch
        last_connection_time = (agent.last_connection_time -
                                datetime.datetime.utcfromtimestamp(0)).\
                                total_seconds()

        if time.time() - last_connection_time < period:
            # The agent hasn't been connected at least "period" amount
            # of time.
            self.log.debug("metrics: too short connection: %d - %d < %d = %d",
                            time.time(), last_connection_time, period,
                            time.time() - last_connection_time)
            return {"above": "unknown"}

        stmt = ("SELECT AVG(cpu) FROM metrics WHERE " + \
               "agentid = %d AND " + \
               "creation_time >= NOW() - INTERVAL '%d seconds'") % \
               (agent.agentid, period)

        report_value = -1
        result = connection.execute(stmt)
        for row in result:
            if row[0] == None:
                report_value = -1
            else:
                report_value = int(round(row[0], 0))

        self.log.debug("metrics: '%s' threshold: %d, average: %d",
                        agent.displayname, threshold, report_value)

        if report_value == -1:
            self.log.debug(
                "metrics: No samples for agent '%s'." % agent.displayname)
            return {"above": "unknown"}
        elif report_value < threshold:
            return {"above": "no", "value": report_value}
        else:
            return {"above": 'yes', "value": report_value}

    def _gen_event(self, which, agent, color, value):
        if color == 'green':
            event = EventControl.CPU_LOAD_OKAY
        elif color == 'yellow':
            event = EventControl.CPU_LOAD_ABOVE_LOW_WATERMARK
        elif color == 'red':
            event = EventControl.CPU_LOAD_ABOVE_HIGH_WATERMARK
        else:
            self.log.error("_gen_event: Invalid color: %s", color)
            return

        data = agent.todict()
        data['info'] = "%s: %d" % (which, value)
        self.server.event_control.gen(event, data)
