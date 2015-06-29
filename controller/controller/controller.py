#!/usr/bin/env python

import sys
import os
import SocketServer as socketserver

import json
import time
import datetime

import exc

import httplib
import ntpath
import uuid as uuidbuild

import sqlalchemy
import akiri.framework.sqlalchemy as meta

# These are need for create_all().
# FIXME: these should logically go in __init__.py.
# pylint: disable=unused-import
from agentmanager import AgentManager
from agent import Agent, AgentVolumesEntry
from alert_email import AlertEmail
from auth import AuthManager
from cli_cmd import CliCmd
from cloud import CloudEntry
from config import Config
from passwd import aes_encrypt
from credential import CredentialEntry, CredentialManager
from diskcheck import DiskCheck, DiskException
from datasources import DataSource
from data_source_types import DataSourceTypes
from domain import Domain
from environment import Environment
from event_control import EventControl, EventControlManager
from extracts import ExtractManager
from files import FileManager
from firewall_manager import FirewallManager
from general import SystemConfig
from http_control import HttpControl
from http_requests import HttpRequestEntry, HttpRequestManager
from licensing import LicenseManager, LicenseEntry
from metrics import MetricManager
from notifications import NotificationManager
from ports import PortManager
from profile import UserProfile, Role
from sched import Sched, Crontab
from state import StateManager
from state_control import StateControl
from system import SystemManager
from tableau import TableauStatusMonitor, TableauProcess
from workbooks import WorkbookEntry, WorkbookUpdateEntry, WorkbookManager
from yml import YmlEntry, YmlManager
#pylint: enable=unused-import

from sites import Site
from projects import Project
from data_connections import DataConnection

from place_file import PlaceFile
from get_file import GetFile
from cloud import CloudManager

from clihandler import CliHandler
from util import version, success, failed, sizestr
from rwlock import RWLock

# pylint: disable=no-self-use

class Controller(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # pylint: disable=too-many-public-methods
    # pylint: disable=too-many-instance-attributes

    CLI_URI = "/cli"
    LOGGER_NAME = "main"
    allow_reuse_address = True

    DATA_DIR = "Data"
    BACKUP_DIR = "tableau-backups"
    LOG_DIR = "tableau-logs"
    WORKBOOKS_DIR = "tableau-workbooks"
    PALETTE_DIR = "palette-system"

    STAGING_DIR = "staging"

    FILENAME_FMT = "%Y%m%d_%H%M%S"

    def backup_cmd(self, agent, userid):
        """Perform a backup - not including any necessary migration."""
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-return-statements
        # pylint: disable=too-many-statements

        if userid == None:
            auto = True     # It is an 'automatic/scheduled' backup
        else:
            auto = False    # It was requested by a specific user

        min_disk_needed = agent.tableau_data_size * .3

        # Disk space check.
        try:
            dcheck = DiskCheck(self, agent, self.BACKUP_DIR,
                               FileManager.FILE_TYPE_BACKUP, min_disk_needed)
        except DiskException, ex:
            return self.error(str(ex))

        if dcheck.target_type == FileManager.STORAGE_TYPE_CLOUD:
            self.log.debug("Backup will copy to cloud storage type %s " + \
                           "name '%s' bucket '%s'",
                            dcheck.target_entry.cloud_type,
                            dcheck.target_entry.name,
                            dcheck.target_entry.bucket)
        elif dcheck.target_type == FileManager.STORAGE_TYPE_VOL:
            if dcheck.target_entry.agentid == agent.agentid:
                self.log.debug("Backup will stay on the primary.")
            else:
                self.log.debug(
                    "Backup will copy to target '%s', target_dir '%s'",
                        dcheck.target_agent.displayname, dcheck.target_dir)
        else:
            self.log.error("backup_cmd: Invalid target_type: %s" % \
                           dcheck.target_type)
            return self.error("backup_cmd: Invalid target_type: %s" % \
                              dcheck.target_type)
        # Example name: 20140127_162225.tsbak
        backup_name = time.strftime(self.FILENAME_FMT) + ".tsbak"

        # Example: "c:/ProgramData/Palette/Data/tableau-backups/<name>.tsbak"

        # e.g. E:\\ProgramData\Palette\Data\tableau-backups\<name>.tsbak
        backup_full_path = agent.path.join(dcheck.primary_dir, backup_name)

        cmd = 'tabadmin backup \\\"%s\\\"' % backup_full_path

        backup_start_time = time.time()
        body = self.cli_cmd(cmd, agent, timeout=60*60*2)
        backup_elapsed_time = time.time() - backup_start_time

        if body.has_key('error'):
            body['info'] = 'Backup command elapsed time before failure: %s' % \
                            self.seconds_to_str(backup_elapsed_time)
            return body

        backup_size = 0
        try:
            backup_size_body = agent.filemanager.filesize(backup_full_path)
        except IOError as ex:
            self.log.error("filemanager.filesize('%s') failed: %s",
                            backup_full_path, str(ex))
        else:
            if not success(backup_size_body):
                self.log.error("Failed to get size of backup file '%s': %s" % \
                                (backup_full_path, backup_size_body['error']))
            else:
                backup_size = backup_size_body['size']

        # If the target is not on the primary agent, then after the
        # backup, it will be copied to either:
        #   1) another agent
        # or
        #   2) cloud storage
        place = PlaceFile(self, agent, dcheck, backup_full_path, backup_size,
                          auto)

        body['info'] = place.info
        if place.copy_failed:
            body['copy-failed'] = True

        # Report backup stats
        total_time = backup_elapsed_time + place.copy_elapsed_time

        stats = 'Backup size: %s\n' % sizestr(backup_size)
        stats += 'Backup elapsed time: %s' % \
                  (self.seconds_to_str(backup_elapsed_time))

        if place.copied:
            stats += ' (%.0f%%)\n' % ((backup_elapsed_time / total_time) * 100)
            stats += 'Backup copy elapsed time: %s (%.0f%%)\n' % \
                     (self.seconds_to_str(place.copy_elapsed_time),
                     (place.copy_elapsed_time / total_time) * 100)

            stats += 'Backup total elapsed time: %s' % \
                      self.seconds_to_str(total_time)
        else:
            stats += '\n'

        body['info'] += '\n' + stats

        body['size'] = sizestr(backup_size)
        body['destination_type'] = place.placed_file_entry.storage_type
        if place.placed_file_entry.storage_type == \
                                        FileManager.STORAGE_TYPE_CLOUD:
            # cloud type (s3 or gcs, etc.)
            body['destination_name'] = dcheck.target_entry.cloud_type
            # bucket
            body['destination_location'] = dcheck.target_entry.bucket
        else:
            if not place.copy_failed:
                # displayname
                body['destination_name'] = dcheck.target_agent.displayname
                # volume + pathname
                body['destination_location'] = dcheck.target_dir
            else:
                # Copy failed, so still on the primary
                body['destination_name'] = agent.displayname
                # volume + pathname
                body['destination_location'] = agent.path.dirname(
                                                             place.full_path)
        return body

    def rotate_backups(self):
        """Rotate/delete old auto-generated and then user-generated
           backup files."""
        file_type = FileManager.FILE_TYPE_BACKUP
        st_config = SystemConfig(self.system)
        find_method = self.files.find_by_auto_envid
        find_name = "scheduled"

        info = self.file_rotate(st_config.backup_auto_retain_count,
                                find_method, find_name, file_type)

        find_method = self.files.find_by_non_auto_envid
        find_name = "user generated"

        info += self.file_rotate(st_config.backup_user_retain_count,
                                 find_method, find_name, file_type)

        return info

    def rotate_ziplogs(self):
        """Rotate/delete old ziplog files."""
        file_type = FileManager.FILE_TYPE_ZIPLOG
        st_config = SystemConfig(self.system)
        find_method = self.files.find_by_auto_envid
        find_name = "scheduled"

        info = self.file_rotate(st_config.ziplog_auto_retain_count,
                                find_method, find_name, file_type)

        find_method = self.files.find_by_non_auto_envid
        find_name = "user generated"

        info += self.file_rotate(st_config.ziplog_user_retain_count,
                                 find_method, find_name, file_type)

        return info

    def file_rotate(self, retain_count, find_method, find_name, file_type):
        """Delete the old files."""

        rows = find_method(self.environment.envid, file_type)

        remove_count = len(rows) - retain_count
        if remove_count <= 0:
            remove_count = 0
            info = ""
        else:
            info = ("\nThere are %d %s %s files.  Retaining %d.  " + \
                   "Will remove %d.") % \
                   (len(rows), find_name, file_type,
                   retain_count, remove_count)

            self.log.debug(info)

        for entry in rows[:remove_count]:
            self.log.debug(
                    "file_rotate: deleting %s file type " +
                    "%s name %s fileid %d", find_name, file_type, entry.name,
                    entry.fileid)
            body = self.delfile_cmd(entry)
            if 'error' in body:
                info += '\n' + body['error']
            elif 'stderr' in body and len(body['stderr']):
                info += '\n' + body['stderr']
            else:
                if entry.storage_type == FileManager.STORAGE_TYPE_VOL:
                    info += "\nRemoved %s" % entry.name
                else:
                    cloud_entry = self.cloud.get_by_cloudid(entry.storageid)
                    if not cloud_entry:
                        info += "\nfile_rotate: cloudid not found: %d" % \
                                 entry.storageid
                    else:
                        info += "\nRemoved from %s bucket %s: %s" % \
                                (cloud_entry.cloud_type, cloud_entry.bucket,
                                 entry.name)
        return info

    def seconds_to_str(self, seconds):
        return str(datetime.timedelta(seconds=int(seconds)))

    def delfile_cmd(self, entry):
        """Delete a file, wherever it is
            Argument:
                    entry   The file entry.
        """
        # pylint: disable=too-many-return-statements

        # Delete a file from the cloud
        if entry.storage_type == FileManager.STORAGE_TYPE_CLOUD:
            try:
                self.delete_cloud_file(entry)
            except IOError as ex:
                return {'error': str(ex)}
            try:
                self.files.remove(entry.fileid)
            except sqlalchemy.orm.exc.NoResultFound:
                return {'error': ("fileid %d not found: name=%s cloudid=%d" % \
                        (entry.fileid, entry.name,
                        entry.storageid))}
            return {}

        # Delete a file from an agent.
        vol_entry = AgentVolumesEntry.get_vol_entry_by_volid(entry.storageid)
        if not vol_entry:
            return {"error": "volid not found: %d" % entry.storageid}

        target_agent = None
        agents = self.agentmanager.all_agents()
        for key in agents.keys():
            self.agentmanager.lock()
            if not agents.has_key(key):
                self.log.info(
                    "copy_cmd: agent with conn_id %d is now " + \
                    "gone and won't be checked.", key)
                self.agentmanager.unlock()
                continue
            agent = agents[key]
            self.agentmanager.unlock()

            if agent.agentid == vol_entry.agentid:
                target_agent = agent
                break

        if not target_agent:
            return {'error': "Agentid %d not connected." % vol_entry.agentid}

        file_full_path = entry.name
        self.log.debug("delfile_cmd: Deleting path '%s' on agent '%s'",
                       file_full_path, target_agent.displayname)

        body = self.delete_vol_file(target_agent, file_full_path)

        # We remove the entry from the files table regardless of
        # whether or not the file was successfully removed:
        # If it failed to remove, it was probably because it was already
        # gone.
        try:
            self.files.remove(entry.fileid)
        except sqlalchemy.orm.exc.NoResultFound:
            return {'error': ("fileid %d not found: name=%s agent=%s" % \
                    (entry.fileid, file_full_path,
                        target_agent.displayname))}
        return body

    def status_cmd(self, agent):
        return self.cli_cmd('tabadmin status -v', agent, timeout=60*5)

    def public_url(self):
        """ Generate a url for Tableau that is reportable to a user."""
        url = self.system.get(SystemConfig.TABLEAU_SERVER_URL, default=None)
        if url:
            return url

        key = 'svcmonitor.notification.smtp.canonical_url'
        url = self.yml.get(key, default=None)
        if url:
            return url

        return None

    def local_url(self):
        """ Generate a url for Tableau that the agent can use internally"""

        url = self.public_url()
        if url:
            return url

        key = 'datacollector.apache.url'
        url = self.yml.get(key, default=None)
        if url:
            tokens = url.split('/', 3)
            if len(tokens) >= 3:
                return tokens[0] + '//' + tokens[2]
        return None

    def tabcmd(self, args, agent):
        cred = self.cred.get('primary', default=None)
        if cred is None:
            cred = self.cred.get('secondary', default=None)
            if cred is None:
                errmsg = 'No credentials found.'
                self.log.error('tabcmd: ' + errmsg)
                return {'error': 'No credentials found.'}
        pw = cred.getpasswd()
        if not cred.user or not pw:
            errmsg = 'Invalid credentials.'
            self.log.error('tabcmd: ' + errmsg)
            return {'error': errmsg}
        url = self.local_url()
        if not url:
            errmsg = 'No local URL available.'
            return {'error': errmsg}
        # tabcmd options must come last.
        cmd = ('tabcmd %s -u %s --password %s ' + \
               '--no-cookie --server %s --no-certcheck ') %\
              (args, cred.user, pw, url)
        return self.cli_cmd(cmd, agent, timeout=30*60)

    def kill_cmd(self, xid, agent):
        """Send a "kill" command to an Agent to end a process by XID.
            Returns the body of the reply.
            Called without the connection lock."""

        self.log.debug("kill_cmd")
        aconn = agent.connection
        aconn.lock()
        self.log.debug("kill_cmd got lock")

        data = {'action': 'kill', 'xid': xid}
        send_body = json.dumps(data)

        headers = {"Content-Type": "application/json"}
        uri = self.CLI_URI

        self.log.debug('about to send the kill command, xid %d', xid)
        try:
            aconn.httpconn.request('POST', uri, send_body, headers)
            self.log.debug('sent kill command')
            res = aconn.httpconn.getresponse()
            self.log.debug('command: kill: ' + \
                               str(res.status) + ' ' + str(res.reason))
            body_json = res.read()
            if res.status != httplib.OK:
                self.log.error("kill_cmd: POST failed: %d\n", res.status)
                alert = "Agent command failed with status: " + str(res.status)
                self.remove_agent(agent, alert)
                return self.httperror(res, method="POST",
                                      displayname=agent.displayname,
                                      uri=uri, body=body_json)

            self.log.debug("headers: " + str(res.getheaders()))

        except (httplib.HTTPException, EnvironmentError) as ex:
            # bad agent
            msg = "kill_cmd: failed: " + str(ex)
            self.log.error(msg)
            self.remove_agent(agent, "Command to agent failed. " \
                                  + "Error: " + str(ex))
            return self.error(msg)
        finally:
            # Must call aconn.unlock() even after self.remove_agent(),
            # since another thread may waiting on the lock.
            aconn.unlock()
            self.log.debug("kill_cmd unlocked")

        self.log.debug("done reading.")
        body = json.loads(body_json)
        if body == None:
            return self.error("POST /%s getresponse returned null body" % uri,
                              return_dict={})
        return body

    def copy_cmd(self, source_agentid, source_path, target_agentid, target_dir):
        """Sends a phttp command and checks the status.
           copy from  source_agentid /path/to/file target_agentid target-dir
                                      <source_path>            <target-dir>
           generates:
               phttp.exe GET https://primary-ip:192.168.1.1/file dir/
           and sends it as a cli command to agent:
                target-agentid
           Returns the body dictionary from the status.
        """
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals

        if not len(source_path):
            return self.error("[ERROR] Invalid source path with no length.")

        agents = self.agentmanager.all_agents()
        src = dst = None

        for key in agents.keys():
            self.agentmanager.lock()
            if not agents.has_key(key):
                self.log.info(
                    "copy_cmd: agent with conn_id %d is now " + \
                    "gone and won't be checked.", key)
                self.agentmanager.unlock()
                continue
            agent = agents[key]
            self.agentmanager.unlock()

            if agent.agentid == source_agentid:
                src = agent
            if agent.agentid == target_agentid:
                dst = agent

        msg = ""
        # fixme: make sure the source isn't the same as the target
        if not src:
            msg = "No connected source agent with agentid: %d." % \
              source_agentid
        if not dst:
            msg += "No connected target agent with agentid: %s." % \
              target_agentid

        if not src or not dst:
            return self.error(msg)

        if src.iswin:
            # Enable the firewall port on the source host.
            self.log.debug("Enabling firewall port %d on src host '%s'", \
                                    src.listen_port, src.displayname)
            fw_body = src.firewall.enable([src.listen_port])
            if fw_body.has_key("error"):
                self.log.error(
                    "firewall enable port %d on src host %s failed with: %s",
                        src.listen_port, src.displayname, fw_body['error'])
                data = agent.todict()
                data['error'] = fw_body['error']
                data['info'] = "Port " + str(src.listen_port)
                self.event_control.gen(EventControl.FIREWALL_OPEN_FAILED, data)
                return fw_body

        source_ip = src.ip_address

       # Make sure the target directory on the target agent exists.
        try:
            dst.filemanager.mkdirs(target_dir)
        except (IOError, ValueError) as ex:
            self.log.error(
                "copycmd: Could not create directory: '%s': %s" % (target_dir,
                                                                   ex))
            return self.error(
                "Could not create directory '%s' on target agent '%s': %s" % \
                (target_dir, dst.displayname, ex))

        if src.iswin:
            command = 'phttp GET "https://%s:%s/%s" "%s"' % \
                (source_ip, src.listen_port, source_path, target_dir)
        else:
            command = 'phttp GET "https://%s:%s%s" "%s"' % \
                (source_ip, src.listen_port, source_path, target_dir)

        try:
            entry = meta.Session.query(Agent).\
                filter(Agent.agentid == src.agentid).\
                one()
        except sqlalchemy.orm.exc.NoResultFound:
            self.log.error("Source agent not found!  agentid: %d", src.agentid)
            return self.error("Source agent not found in agent table: %d " % \
                                                                src.agentid)

        env = {u'BASIC_USERNAME': entry.username,
               u'BASIC_PASSWORD': entry.password}

        self.log.debug("agent username: %s, password: %s", entry.username,
                                                            entry.password)
        # Send command to target agent
        copy_body = self.cli_cmd(command, dst, env=env)
        return copy_body

    def restore_cmd(self, agent, backup_full_path, orig_state,
                    no_config=False, userid=None, user_password=None):
        # pylint: disable=too-many-arguments
        """Do a tabadmin restore for the backup_full_path.
           The backup_full_path may be in cloud storage, or a volume
           on some agent.

           The "agent" argument must be the primary agent.

           Returns a body with the results/status.
        """
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements

        data = agent.todict()
        if no_config:
            data['restore_type'] = 'Data only'
        else:
            data['restore_type'] = 'Data and Configuration'

        # If the backup file is not on the primary agent (other agent
        # or cloud storage), copy the file from the other agent or
        # cloud storage to the staging area on the primary.
        try:
            got = GetFile(self, agent, backup_full_path)
        except IOError as ex:
            self.state_manager.update(orig_state)
            return self.error("restore_cmd failure: %s" % str(ex))

        # The restore file is now on the Primary Agent.
        self.event_control.gen(EventControl.RESTORE_STARTED,
                               data, userid=userid)

        reported_status = self.statusmon.get_tableau_status()

        if reported_status == TableauProcess.STATUS_RUNNING:
            # Restore can run only when tableau is stopped.
            self.state_manager.update(StateManager.STATE_STOPPING_RESTORE)
            self.log.debug("----------Stopping Tableau for restore-----------")
            stop_body = self.cli_cmd("tabadmin stop", agent, timeout=60*60)
            if stop_body.has_key('error'):
                self.log.info("Restore: tabadmin stop failed")
                if got.copied:
                    # If the file was copied to the Primary, delete
                    # the temporary backup file we copied to the Primary.
                    self.delete_vol_file(agent, got.primary_full_path)
                self.state_manager.update(orig_state)
                return stop_body

            self.event_control.gen(EventControl.STATE_STOPPED, data,
                                   userid=userid)

        # 'tabadmin restore ...' starts tableau as part of the
        # restore procedure.
        # fixme: Maybe the maintenance web server wasn't running?
        # We currently don't keep track, but assume the maintenance
        # web server may be running if Tableau is stopped.
        maint_msg = ""
        if orig_state == StateManager.STATE_STOPPED:
            maint_body = self.maint("stop")
            if maint_body.has_key("error"):
                self.log.info(
                        "Restore: maint stop failed: " + maint_body['error'])
                # continue on, not a fatal error...
                maint_msg = "Restore: maint stop failed.  Error was: %s" \
                                                    % maint_body['error']

        self.state_manager.update(StateManager.STATE_STARTING_RESTORE)

        cmd = 'tabadmin restore \\\"%s\\\"' % got.primary_full_path
        if user_password:
            cmd += ' --password \\\"%s\\\"' % user_password
        if no_config:
            cmd += ' --no-config'

        try:
            self.log.debug("restore sending command: %s", cmd)
            restore_body = self.cli_cmd(cmd, agent, timeout=60*60*2)
        except httplib.HTTPException, ex:
            restore_body = {"error": "HTTP Exception: " + str(ex)}

        if restore_body.has_key('error'):
            restore_success = False
        else:
            restore_success = True

        if maint_msg != "":
            info = maint_msg
        else:
            info = ""

        # fixme: Do we need to add restore information to the database?
        # fixme: check status before cleanup? Or cleanup anyway?

        if got.copied:
            # If the file was copied to the Primary, delete
            # the temporary backup file we copied to the Primary.
            delete_body = self.delete_vol_file(agent,
                                                 got.primary_full_path)
            if 'error' in delete_body:
                info += '\n' + delete_body['error']

        if restore_success:
#            self.state_manager.update(StateManager.STATE_STARTED)
            self.event_control.gen(EventControl.STATE_STARTED, data,
                                   userid=userid)
        else:
            # On a successful restore, tableau starts itself.
            # fixme: eventually control when tableau is started and
            # stopped, rather than have tableau automatically start
            # during the restore.  (Tableau does not support this currently.)
            self.log.info("Restore: starting tableau after failed restore.")
            start_body = self.cli_cmd("tabadmin start", agent, timeout=60*60*2)
            if 'error' in start_body:
                self.log.info(
                    "Restore: 'tabadmin start' failed after failed restore.")
                msg = "Restore: 'tabadmin start' failed after failed restore."
                msg += " Error was: %s" % start_body['error']
                info += "\n" + msg

                 # The "tableau start" failed.  Go back to the "STOPPED" state.
#                self.state_manager.update(StateManager.STATE_STOPPED)
            else:
                # The "tableau start" succeeded
#                self.state_manager.update(StateManager.STATE_STARTED)
                self.event_control.gen(EventControl.STATE_STARTED, data,
                                       userid=userid)

        if info:
            restore_body['info'] = info.strip()

        return restore_body

    # FIXME: use filemanager.delete() instead?
    def delete_vol_file(self, agent, source_fullpathname):
        """Delete a file, check the error, and return the body result.
           Note: Does not remove the entry from the files table.
           If that is needed, that must be done by the caller."""
        self.log.debug("Removing file '%s'", source_fullpathname)

        # Verify file exists.
        try:
            exists_body = agent.filemanager.filesize(source_fullpathname)
        except IOError as ex:
            self.log.info("filemanager.filesize('%s') failed: %s",
                            source_fullpathname, str(ex))
            return {'error': str(ex)}

        if failed(exists_body):
            self.log.info("filemanager.filesize('%s') error: %s",
                            source_fullpathname, str(exists_body))
            return exists_body

        # Remove file.
        try:
            remove_body = agent.filemanager.delete(source_fullpathname)
        except IOError as ex:
            self.log.info("filemanager.delete('%s') failed: %s",
                            source_fullpathname, str(ex))
            return {'error': str(ex)}

        return remove_body

    # FIXME: move to CloudManager
    def delete_cloud_file(self, file_entry):
        """Note: Does not remove the entry from the files table.
           If that is needed, that must be done by the caller."""
        cloud_entry = self.cloud.get_by_cloudid(file_entry.storageid)
        if not cloud_entry:
            raise IOError("No such cloudid: %d for file %s" % \
                          (file_entry.cloudid, file_entry.name))

        if cloud_entry.cloud_type == CloudManager.CLOUD_TYPE_S3:
            self.cloud.s3.delete_file(cloud_entry, file_entry.name)
        elif cloud_entry.cloud_type == CloudManager.CLOUD_TYPE_GCS:
            self.cloud.gcs.delete_file(cloud_entry, file_entry.name)
        else:
            msg = "delete_cloud_file: Unknown cloud_type %s for file: %s" % \
                  (cloud_entry.cloud_type, file_entry.name)
            self.log.error(msg)
            raise IOError(msg)

    def move_bucket_subdirs_to_path(self, in_bucket, in_path):
        """ Given:
                in_bucket: palette-storage/subdir/dir2
                in_path:   filename
            return:
                bucket:    palette-storage
                path:      subdir/dir2/filename
        """

        if in_bucket.find('/') != -1:
            bucket, rest = in_bucket.split('/', 1)
            path = os.path.join(rest, in_path)
        elif in_bucket.find('\\') != -1:
            bucket, rest = in_bucket.split('\\', 1)
            path = ntpath.join(rest, in_path)
        else:
            bucket = in_bucket
            path = in_path
        return (bucket, path)

    def odbc_ok(self):
        """Reports back True if odbc commands can be run now to
           the postgres database.  odbc commands should be not sent
           in these cases:
            * When the tableau is stopped, since the postgres is also
              stopped when tableau is stopped.
            * When in "UPGRADE" mode.
           The primary should be enabled before doing an odbc connection,
           but that should be been handled in the "get_agent" call.
        """
        main_state = self.state_manager.get_state()
        if main_state in (StateManager.STATE_DISCONNECTED,
                          StateManager.STATE_PENDING,
                          StateManager.STATE_STOPPING,
                          StateManager.STATE_STOPPING_RESTORE,
                          StateManager.STATE_STOPPED,
                          StateManager.STATE_STOPPED_UNEXPECTED,
                          StateManager.STATE_STOPPED_RESTORE,
                          StateManager.STATE_STARTING,
                          StateManager.STATE_STARTING_RESTORE,
                          StateManager.STATE_RESTARTING,
                          StateManager.STATE_UPGRADING):
            return False
        else:
            return True

    def active_directory_verify(self, agent, windomain, username, password):
        data = {'domain': windomain, 'username':username, 'password':password}
        body = agent.connection.http_send_json('/ad', data)
        return json.loads(body)

    def get_pinfo(self, agent, update_agent=False):
        body = self.cli_cmd('pinfo', agent, immediate=True)
        # FIXME: add a function to test cli success (cli_success?)
        if not 'exit-status' in body:
            raise IOError("Missing 'exit-status' from pinfo command response.")
        if body['exit-status'] != 0:
            raise IOError("pinfo failed with exit status: %d" % \
                                                            body['exit-status'])
        json_str = body['stdout']
        try:
            pinfo = json.loads(json_str)
        except ValueError, ex:
            self.log.error("Bad json from pinfo. Error: %s, json: %s", \
                           str(ex), json_str)
            raise IOError("Bad json from pinfo.  Error: %s, json: %s" % \
                          (str(ex), json_str))
        if pinfo is None:
            self.log.error("Bad pinfo output: %s", json_str)
            raise IOError("Bad pinfo output: %s" % json_str)

        # When we are called from init_new_agent(), we don't know
        # the agent_type yet and update_agent_pinfo_vols() needs to
        # know the agent type for the volume table values.
        # When we are called by do_info() we will know the agent type.
        if update_agent:
            if agent.agent_type:
                self.agentmanager.update_agent_pinfo_dirs(agent, pinfo)
                self.agentmanager.update_agent_pinfo_vols(agent, pinfo)
                self.agentmanager.update_agent_pinfo_other(agent, pinfo)
            else:
                self.log.error(
                    "get_pinfo: Could not update agent: unknown " + \
                                    "displayname.  uuid: %s", agent.uuid)
                raise IOError("get_pinfo: Could not update agent: unknown " + \
                        "displayname.  uuid: %s" % agent.uuid)

        return pinfo

    def get_info(self, agent, update_agent=False):
        # FIXME: catch errors.
        body = agent.connection.http_send('GET', '/info')

        try:
            info = json.loads(body)
        except ValueError, ex:
            self.log.error("Bad json from info. Error: %s, json: %s", \
                           str(ex), body)
            raise IOError("Bad json from pinfo.  Error: %s, json: %s" % \
                          (str(ex), body))
        if info is None:
            self.log.error("Bad info output: %s", body)
            raise IOError("Bad info output: %s" % body)

        # When we are called from init_new_agent(), we don't know
        # the agent_type yet and update_agent_pinfo_vols() needs to
        # know the agent type for the volume table values.
        # When we are called by do_info() we will know the agent type.
        if update_agent:
            if agent.agent_type:
                self.agentmanager.update_agent_pinfo_dirs(agent, info)
                self.agentmanager.update_agent_pinfo_vols(agent, info)
                self.agentmanager.update_agent_pinfo_other(agent, info)
            else:
                self.log.error(
                    "get_info: Could not update agent: unknown " + \
                                    "displayname.  uuid: %s", agent.uuid)
                raise IOError("get_pinfo: Could not update agent: unknown " + \
                        "displayname.  uuid: %s" % agent.uuid)

        return info

    def yml_sync(self, agent, set_agent_types=True):
        """Note: Can raise an IOError (if the filemanager.get() fails)."""
        old_gateway_hosts = self.yml.get('gateway.hosts', default=None)
        body = self.yml.sync(agent)
        new_gateway_hosts = self.yml.get('gateway.hosts', default=None)

        if set_agent_types:
            # See if any worker agents need to be reclassified as
            # archive agents or vice versa.
            self.agentmanager.set_all_agent_types()

        if not old_gateway_hosts is None:
            if old_gateway_hosts != new_gateway_hosts:
                # Stop the maintenance web server, to get out of the way
                # of Tableau if the yml has changed from last check.
                self.maint("stop")

        return body

    def sync_cmd(self, agent, check_odbc_state=True):
        """sync/copy tables from tableau to here."""
        # pylint: disable=too-many-branches

        if check_odbc_state and not self.odbc_ok():
            main_state = self.state_manager.get_state()
            self.log.info("Failed.  Current state: %s", main_state)
            raise exc.InvalidStateError(
                "Cannot run command while in state: %s" % main_state)

        error_msg = ""
        sync_dict = {}

        body = Site.sync(agent)
        if 'error' in body:
            error_msg += "Site sync failure: " + body['error']
        else:
            sync_dict['sites'] = body['count']

        body = Project.sync(agent)
        if 'error' in body:
            if error_msg:
                error_msg += ", "
            error_msg += "Project sync failure: " + body['error']
        else:
            sync_dict['projects'] = body['count']

        body = DataConnection.sync(agent)
        if 'error' in body:
            if error_msg:
                error_msg += ", "
            error_msg += "DataConnection sync failure: " + body['error']
        else:
            sync_dict['data-connections'] = body['count']

        body = DataSource.sync(agent)
        if 'error' in body:
            if error_msg:
                error_msg += ", "
            error_msg += "DataSouce sync failure: " + body['error']
        else:
            sync_dict['data-sources'] = body['count']

        if error_msg:
            sync_dict['error'] = error_msg

        if not 'status' in sync_dict:
            if 'error' in sync_dict:
                sync_dict['status'] = 'FAILED'
            else:
                sync_dict['status'] = 'OK'

        return sync_dict

    def maint(self, action, agent=None, send_alert=True):
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        """If agent is not specified, action is done for all gateway agents."""
        if action not in ("start", "stop"):
            self.log.error("Invalid maint action: %s", action)
            return self.error("Bad maint action: %s" % action)

        envid = self.environment.envid

        manager = self.agentmanager
        try:
            gateway_hosts = manager.get_yml_list('gateway.hosts')
        except ValueError:
            self.log.error("maint: %s: No yml entry for 'gateway.hosts' yet.",
                            action)
            return self.error(
                    "maint %s: No yml entry for 'gateway.hosts' yet." % \
                    action)

        # We're going to combine stdout/stderr/error for all gateway hosts.
        body_combined = {'stdout': "",
                         'stderr': "",
                         'error': ""}

        maint_success = True
        send_maint_body = self.set_maint_body(action)

        # We were called with a specific agent so do the maint action only
        # there.
        if agent:
            body = self.send_maint(action, agent, send_maint_body)
            self.update_maint_status(action, body)

            if send_alert:
                self.send_maint_event(action, agent, body)
            return body

        agent_connected = None
        for host in gateway_hosts:
            # This means the primary is the gateway host
            if host == 'localhost' or host == '127.0.0.1':
                agent = manager.agent_by_type(AgentManager.AGENT_TYPE_PRIMARY)
                if not agent:
                    self.log.debug("maint: %s: primary is not [yet] " + \
                                   "fully connected.  Skipping.", action)
                    continue

            else:
                agentid = Agent.get_agentid_from_host(envid, host)
                if not agentid:
                    self.log.info("maint: %s: No such agent found " + \
                                   "for host '%s' from gateway.hosts list: %s",
                                    action, host, str(gateway_hosts))
                    continue

                agent = manager.agent_by_id(agentid)
                if not agent:
                    self.log.debug("maint: %s: Agent host '%s' with " + \
                                   "agentid %d not connected. " + \
                                   "gateway.hosts list: %s",
                                    action, host, agentid, str(gateway_hosts))
                    continue

            # We have a gateway agent.  Do the maint action if possible.
            if not agent.connection:
                self.log.debug("maint: gateway agent not connected: %s. " + \
                               "Skipping '%s'.", host, action)
                continue

            if not agent_connected:
                # The agent to use for the event
                agent_connected = agent

            body = self.send_maint(action, agent, send_maint_body)

            if 'stdout' in body:
                body_combined['stdout'] += '%s: %s\n' % (agent.displayname,
                                                body['stdout'])
            if 'stderr' in body:
                body_combined['stderr'] += '%s: %s\n' % (agent.displayname,
                                                body['stderr'])
            if 'error' in body:
                body_combined['error'] += '%s: %s\n' % \
                                        (agent.displayname, body['error'])
                maint_success = False

        if not agent_connected:
            self.log.debug("maint: No agents are connected.  Did nothing.")
            body_combined['error'] = "No agents are connected."
            return body_combined    # Empty as we did nothing

        if maint_success:
            # The existence of 'error' signifies failure but all succeeded.
            del body_combined['error']

        self.update_maint_status(action, body_combined)

        if send_alert:
            self.send_maint_event(action, agent_connected, body_combined)

        return body_combined

    def update_maint_status(self, action, body):
        if action == 'start':
            if failed(body):
                self.maint_started = False
            else:
                self.maint_started = True

        elif action == 'stop':
            if failed(body):
                self.maint_started = True
            else:
                self.maint_started = False

    def send_maint(self, action, agent, send_maint_body):
        """Does the actual sending of the maint command to the agent,
           returns the body/result.
        """

        self.log.debug("maint: %s for '%s'", action, agent.displayname)
        body = self.send_immediate(agent, "POST", "/maint", send_maint_body)

        return body

    def send_maint_event(self, action, agent, body):
        """Generates the appropriate maint event (start failed, stop
           failed, maint online, maint offline).
        """
        if 'error' in body:
            data = agent.todict()
            if action == "start":
                self.event_control.gen(EventControl.MAINT_START_FAILED,
                                       dict(body.items() + data.items()))
                return
            else:
                self.event_control.gen(EventControl.MAINT_STOP_FAILED,
                                       dict(body.items() + data.items()))
                return

        if action == 'start':
            self.event_control.gen(EventControl.MAINT_ONLINE,
                                   agent.todict())
        else:
            self.event_control.gen(EventControl.MAINT_OFFLINE,
                                   agent.todict())

    def set_maint_body(self, action):
        send_body = {"action": action}

        gateway_ports = self.yml.get('gateway.ports', default=None)
        if gateway_ports:
            ports = gateway_ports.split(';')
            try:
                listen_port = int(ports[0])
                send_body["listen-port"] = listen_port
            except StandardError:
                self.log.error("Invalid yml entry for 'gatway.ports': %s",
                                gateway_ports)

        ssl_enabled = self.yml.get('ssl.enabled', default=None)
        if ssl_enabled != 'true':
            return send_body

        ssl_port = self.yml.get('ssl.port', default=None)
        if ssl_port:
            try:
                ssl_port = int(ssl_port)
                send_body['ssl-listen-port'] = ssl_port
            except StandardError:
                self.log.error("Invalid yml entry for 'ssl.listen.port': %s",
                                ssl_port)

        # Mapping from the yml file to the json to send.
        file_map = {'ssl.cert.file': 'ssl-cert-file',
                    'ssl.key.file': 'ssl-cert-key-file',
                    'ssl.chain.file': 'ssl-cert-chain-file'}

        for key in file_map.keys():
            value = self.yml.get(key, default=None)
            if not value:
                continue

            send_body[file_map[key]] = value

        return send_body

    def archive(self, action, agent=None, port=-1):
        """'start' or 'stop' one or all archive servers."""
        send_body = {"action": action}
        if port > 0:
            send_body["port"] = port

        if agent:
            # Send archive command to just one agent
            return self.send_immediate(agent, "POST", "/archive", send_body)

        # Send archive command to all connected agents
        body_combined = {'stdout': "",
                         'stderr': "",
                         'error': ""}

        archive_success = True
        agents = self.agentmanager.all_agents()
        for key in agents.keys():
            self.agentmanager.lock()
            if not agents.has_key(key):
                self.log.info(
                    "archive: agent with conn_id %d is now " + \
                    "gone and won't be checked.", key)
                self.agentmanager.unlock()
                continue
            agent = agents[key]
            self.agentmanager.unlock()
            body = self.send_immediate(agent, "POST", "/archive", send_body)
            if 'stdout' in body:
                body_combined['stdout'] += '%s: %s\n' % (agent.displayname,
                                                          body['stdout'])
                body_combined['stderr'] += '%s: %s\n' % (agent.displayname,
                                                          body['stderr'])
                body_combined['error'] += '%s: %s\n' % (agent.displayname,
                                                          body['error'])
                archive_success = False

        if archive_success:
            # The existence of 'error' signifies failure but all succeeded.
            del body_combined['error']
        return body_combined

    def ping(self, agent):

        return self.send_immediate(agent, "POST", "/ping")

    def send_immediate(self, agent, method, uri, send_body=""):
        """Sends the request specified by:
                agent:      agent to send to.
                method:     POST, PUT, GET, etc.
                uri:        '/maint', 'firewall', etc.
                send_body:  Body to send in the request.
                            Can be a dictionary or a string.
                            If it is a dictionary, it will be converted
                            to a string (json).
            Returns the body result.
        """

        if type(send_body) == dict:
            send_body = json.dumps(send_body)

        headers = {"Content-Type": "application/json"}

        aconn = agent.connection

        self.log.debug(
            "about to send an immediate command to '%s', conn_id %d, " + \
                "type '%s', method '%s', uri '%s', body '%s'",
                    agent.displayname, aconn.conn_id, agent.agent_type,
                    method, uri, send_body)

        aconn.lock()
        body = {}
        try:
            aconn.httpconn.request(method, uri, send_body, headers)
            res = aconn.httpconn.getresponse()

            rawbody = res.read()
            if res.status != httplib.OK:
                # bad agent
                self.log.error(
                    "immediate command to %s failed with status %d: %s " + \
                    "%s, body: %s:",
                            agent.displayname, res.status, method, uri, rawbody)
                self.remove_agent(agent,\
                    ("Communication failure with agent. " +\
                    "Immediate command to %s, status returned: " +\
                    "%d: %s %s, body: %s") % \
                        (agent.displayname, res.status, method, uri, rawbody))
                return self.httperror(res, method=method,
                                      displayname=agent.displayname,
                                      uri=uri, body=rawbody)
            elif rawbody:
                body = json.loads(rawbody)
            else:
                body = {}
        except (httplib.HTTPException, EnvironmentError) as ex:
            self.log.error("Agent send_immediate command %s %s failed: %s",
                           method, uri, str(ex))
            self.remove_agent(agent, \
                    "Agent send_immediate command %s %s failed: %s" % \
                              (method, uri, str(ex)))
            return self.error("send_immediate method %s, uri %s failed: %s" % \
                              (method, uri, str(ex)))
        finally:
            aconn.unlock()

        self.log.debug(
            "send immediate %s %s success, conn_id %d, response: %s",
                                    method, uri, aconn.conn_id, str(body))
        return body

    def displayname_cmd(self, aconn, uuid, displayname):
        """Sets displayname for the agent with the given hostname. At
           this point assumes uuid is unique in the database."""

        self.agentmanager.set_displayname(aconn, uuid, displayname)

    def ziplogs_cmd(self, agent, userid=None):
        """Run tabadmin ziplogs."""
        # pylint: disable=too-many-locals

        if userid == None:
            auto = True     # It is an 'automatic/scheduled' backup
        else:
            auto = False    # It was requested by a specific user

        # fixme: get more accurate estimate of ziplog size
        min_disk_needed = agent.tableau_data_size * .3
        # Disk space check.
        try:
            dcheck = DiskCheck(self, agent, self.LOG_DIR,
                               FileManager.FILE_TYPE_ZIPLOG, min_disk_needed)
        except DiskException, ex:
            self.log.error("ziplogs_cmd: %s", str(ex))
            return self.error("ziplogs_cmd: %s" % str(ex))

        data = agent.todict()
        self.event_control.gen(EventControl.ZIPLOGS_STARTED,
                               data, userid=userid)

        ziplogs_name = time.strftime(self.FILENAME_FMT) + ".logs.zip"
        ziplogs_full_path = agent.path.join(dcheck.primary_dir, ziplogs_name)
        cmd = 'tabadmin ziplogs -f -l -n -a \\\"%s\\\"' % ziplogs_full_path
        body = self.cli_cmd(cmd, agent, timeout=60*60)
        body[u'info'] = unicode(cmd)

        if success(body):
            ziplog_size = 0
            try:
                ziplog_size_body = agent.filemanager.filesize(ziplogs_full_path)
            except IOError as ex:
                self.log.error("filemanager.filesize('%s') failed: %s",
                                ziplogs_full_path, str(ex))
            else:
                if not success(ziplog_size_body):
                    self.log.error("Failed to get size of ziplogs file %s: %s",
                                   ziplogs_full_path, ziplog_size_body['error'])
                else:
                    ziplog_size = ziplog_size_body['size']

            # Place the file where it belongs (different agent, cloud, etc.)
            place = PlaceFile(self, agent, dcheck, ziplogs_full_path,
                              ziplog_size, auto)
            body['info'] += '\n' + place.info

            rotate_info = self.rotate_ziplogs()
            body['info'] += rotate_info

        if 'error' in body:
            self.event_control.gen(EventControl.ZIPLOGS_FAILED,
                                   dict(body.items() + data.items()),
                                   userid=userid)
        else:
            self.event_control.gen(EventControl.ZIPLOGS_FINISHED,
                                   dict(body.items() + data.items()),
                                   userid=userid)
        return body

    def cleanup_cmd(self, agent, userid=None):
        """Run tabadmin cleanup'."""

        data = agent.todict()
        self.event_control.gen(EventControl.CLEANUP_STARTED, data,
                               userid=userid)
        body = self.cli_cmd('tabadmin cleanup', agent, timeout=60*60)
        if 'error' in body:
            self.event_control.gen(EventControl.CLEANUP_FAILED,
                                   dict(body.items() + data.items()),
                                   userid=userid)
        else:
            self.event_control.gen(EventControl.CLEANUP_FINISHED,
                                   dict(body.items() + data.items()),
                                   userid=userid)
        return body

    # FIXME: allow this to take *args
    def error(self, msg, return_dict=None):
        """Returns error dictionary in standard format.  If passed
           a return_dict, then adds to it, otherwise a new return_dict
           is created."""
        if return_dict is None:
            return_dict = {}
        return_dict['error'] = unicode(msg)
        return return_dict

    def controller_init_events(self):
        """Generate an event if we are running a new version."""
        last_version = self.system.get(SystemConfig.PALETTE_VERSION,
                                       default=None)

        body = {'version_previous': last_version,
                'version_current': self.version}

        controller_initial_start = self.system.get(
                                        SystemConfig.CONTROLLER_INITIAL_START,
                                        default=None)

        if not controller_initial_start:
            self.system.save(SystemConfig.CONTROLLER_INITIAL_START,
                                                                self.version)
            self.event_control.gen(EventControl.CONTROLLER_STARTED, body)

        else:
            self.event_control.gen(EventControl.CONTROLLER_RESTARTED, body)

        if self.version == last_version:
            return last_version, self.version

        self.system.save(SystemConfig.PALETTE_VERSION, self.version)

        self.event_control.gen(EventControl.PALETTE_UPDATED, body)

        return last_version, self.version

    def httperror(self, res, error='HTTP failure',
                  displayname=None, method='GET', uri=None, body=None):
        """Returns a dict representing a non-OK HTTP response."""
        # pylint: disable=too-many-arguments
        if body is None:
            body = res.read()
        data = {
            'error': error,
            'status-code': res.status,
            'reason-phrase': res.reason,
            }
        if method:
            data['method'] = method
        if uri:
            data['uri'] = uri
        if body:
            data['body'] = body
        if displayname:
            data['agent'] = displayname
        return data

    def init_new_agent(self, agent):
        """Agent-related configuration on agent connect.
            Args:
                aconn: agent connection
            Returns:
                pinfo dictionary:  The agent responded correctly.
                False:  The agent responded incorrectly.
        """

        tableau_install_dir = "tableau-install-dir"
        aconn = agent.connection

        pinfo = self.get_pinfo(agent, update_agent=False)

        self.log.debug("info returned from %s: %s",
                       aconn.displayname, str(pinfo))
        # Set the type of THIS agent.
        if tableau_install_dir in pinfo:
            # FIXME: don't duplicate the data
            agent.agent_type = aconn.agent_type \
                = AgentManager.AGENT_TYPE_PRIMARY

            if pinfo[tableau_install_dir].find(':') == -1:
                self.log.error("agent %s is missing ':': %s for %s",
                               aconn.displayname, tableau_install_dir,
                               agent.tableau_install_dir)
                return False
        else:
            if self.agentmanager.is_tableau_worker(agent):
                agent.agent_type = aconn.agent_type = \
                                    AgentManager.AGENT_TYPE_WORKER
            else:
                agent.agent_type = aconn.agent_type = \
                                    AgentManager.AGENT_TYPE_ARCHIVE

        if agent.iswin:
            self.firewall_manager.do_firewall_ports(agent)

        self.clean_xid_dirs(agent)

        # This saves directory-related info from pinfo: it
        # does not save the volume info since we may not
        # know the displayname yet and the displayname is
        # needed for a disk-usage event report.
        self.agentmanager.update_agent_pinfo_dirs(agent, pinfo)

        # Note: Don't call this before update_agent_pinfo_dirs()
        # (needed for agent.tableau_data_dir).
        if agent.agent_type == AgentManager.AGENT_TYPE_PRIMARY:
            # raises an exception on fail
            self.yml_sync(agent, set_agent_types=False)
            # These can all fail as long as they don't get an IOError.
            # For example, if tableau is stopped, these will fail,
            # but we don't know tableau's status yet and it's
            # worth trying, especially to import the users.
            if success(self.auth.load(agent, check_odbc_state=False)):
                self.sync_cmd(agent, check_odbc_state=False)
                self.extract.load(agent, check_odbc_state=False)
            else:
                self.log.debug(
                    "init_new_agent: Couldn't do initial import of " + \
                    "auth, etc. probably due to tableau stopped.")

        # Configuring the 'maint' web server requires the yml file,
        # so this must be done after the "yml_sync()" above.
        self.config_servers(agent)

        return pinfo

    def clean_xid_dirs(self, agent):
        """Remove old XID directories."""
        xid_dir = agent.path.join(agent.data_dir, "XID")
        try:
            body = agent.filemanager.listdir(xid_dir)
        except IOError as ex:
            self.log.error("filemanager.listdir('%s') for the XID " + \
                           "directory failed: %s", xid_dir, str(ex))
            return

        if not success(body):
            self.log.error("Could not list the XID directory '%s': %s",
                           xid_dir, body['error'])
            return

        if not 'directories' in body:
            self.log.error(
                           ("clean_xid_dirs: Filemanager response missing " + \
                             "directories.  Response: %s") % str(body))
            return

        for rem_dir in body['directories']:
            full_path = agent.path.join(xid_dir, rem_dir)
            self.log.debug("Removing %s", full_path)
            try:
                agent.filemanager.delete(full_path)
            except IOError as ex:
                self.log.error("filemanager.delete('%s') failed: %s",
                                full_path, str(ex))

    def config_servers(self, agent):
        """Configure the maintenance and archive servers."""
        if agent.agent_type in (AgentManager.AGENT_TYPE_PRIMARY,
                                AgentManager.AGENT_TYPE_WORKER):
            # Put into a known state if it could possibly be a
            # gateway server.
            body = self.maint("stop", agent=agent, send_alert=False)
            if body.has_key("error"):
                data = agent.todict()
                self.event_control.gen(EventControl.MAINT_STOP_FAILED,
                                       dict(body.items() + data.items()))

        body = self.archive("stop", agent)
        if body.has_key("error"):
            self.event_control.gen(EventControl.ARCHIVE_STOP_FAILED,
                                   dict(body.items() + agent.todict().items()))
        # Get ready.
        body = self.archive("start", agent)
        if body.has_key("error"):
            self.event_control.gen(EventControl.ARCHIVE_START_FAILED,
                                   dict(body.items() + agent.todict().items()))

    def remove_agent(self, agent, reason="", gen_event=True):
        manager = self.agentmanager
        manager.remove_agent(agent, reason=reason, gen_event=gen_event)
        # FIXME: At the least, we need to add the domain to the check
        #        for a primary; better, however, would be to store the
        #        uuid of the status with the status and riff off uuid.
        if not manager.agent_conn_by_type(AgentManager.AGENT_TYPE_PRIMARY):
            session = meta.Session()
            self.statusmon.remove_all_status()
            session.commit()

    def upgrade_version(self, last_version, new_version):
        """Make changes to the database, etc. as required for upgrading
           from last_version to new_version."""

        self.log.debug("Upgrade from %s to %s", last_version, new_version)

        if last_version == new_version:
            return

        if last_version != '1.0.1':
            return

        entry = Domain.getone()
        if not entry.systemid:
            entry.systemid = str(uuidbuild.uuid1())
            meta.Session.commit()

        # Set default mail server type to direct.
        # We do this to match the UI configuration with the configuration
        # of current installations.
        self.system.save(SystemConfig.MAIL_SERVER_TYPE, '1')

        # Migrate/copy system table entry from "log-archive-retain-count"
        # to both:
        #   ZIPLOG_AUTO_RETAIN_COUNT
        #   ZIPLOG_USER_RETAIN_COUNT
        ziplog_retain_count = self.system.get(
                                        SystemConfig.LOG_ARCHIVE_RETAIN_COUNT)
        self.system.save(SystemConfig.ZIPLOG_AUTO_RETAIN_COUNT,
                         ziplog_retain_count)

        self.system.save(SystemConfig.ZIPLOG_USER_RETAIN_COUNT,
                         ziplog_retain_count)

        # The rest is for the s3 cloud entry.
        entry = CloudEntry.get_by_envid_type(self.environment.envid, "s3")
        if not entry:
            return

        try:
            _ = int(entry.secret, 16)
        except ValueError:
            # The secret wasn't a hex digest, so we need to convert it to one.
            entry.secret = aes_encrypt(entry.secret)
            meta.Session.commit()


import logging

class StreamLogger(object):
    """
    File-like stream class that writes to a logger.
    Used for redirecting stdout & stderr to the log file.
    """

    def __init__(self, logger, tag=None):
        self.logger = logger
        self.tag = tag
        # writes are buffered to ensure full lines are printed together.
        self.buf = ''

    def writeln(self, line):
        line = line.rstrip()
        if not line:
            return
        if self.tag:
            line = '[' + self.tag + '] ' + line
        self.logger.log(logging.ERROR, line)

    def write(self, buf):
        buf = self.buf + buf
        self.buf = ''
        for line in buf.splitlines(True):
            if not line.endswith('\r') and not line.endswith('\n'):
                self.buf = self.buf + line
                continue
            self.writeln(line)

    def close(self):
        self.flush()

    def flush(self):
        self.writeln(self.buf)
        self.buf = ''

def main():
    # pylint: disable=too-many-statements,too-many-locals
    # pylint: disable=attribute-defined-outside-init

    import argparse
    import logger

    parser = argparse.ArgumentParser(description='Palette Controller')
    parser.add_argument('config', nargs='?', default=None)
    parser.add_argument('--nostatus', action='store_true', default=False)
    parser.add_argument('--noping', action='store_true', default=False)
    parser.add_argument('--nosched', action='store_true', default=False)
    args = parser.parse_args()

    config = Config(args.config)
    host = config.get('controller', 'host', default='localhost')
    port = config.getint('controller', 'port', default=9000)

    # loglevel at the start, here, is controlled by the INI file,
    # though uses a default.  After the database is available,
    # we reset the log-level, depending on the 'debug-level' value in the
    # system table.
    logger.make_loggers(config)
    log = logger.get(Controller.LOGGER_NAME)
    log.info("Controller version: %s", version())

    # Log stderr to the log file too.
    # NOTE: stdout is not logged so that PDB will work.
    sys.stderr = StreamLogger(log, tag='STD')

    # database configuration
    url = config.get("database", "url")
    echo = config.getboolean("database", "echo", default=False)
    max_overflow = config.getint("database", "max_overflow", default=10)

    # engine is once per single application process.
    # see http://docs.sqlalchemy.org/en/rel_0_9/core/connections.html
    meta.create_engine(url, echo=echo, max_overflow=max_overflow)
    meta.Session.autoflush = False
    meta.Session.expire_on_commit = False

    server = Controller((host, port), CliHandler)
    server.config = config

    # FIXME: deprecated
    # We always use the root logger so use logging. instead of server.log.
    server.log = log
    server.cli_get_status_interval = \
      config.getint('controller', 'cli_get_status_interval', default=10)
    server.noping = args.noping
    server.event_debug = config.getboolean('default',
                                           'event_debug',
                                           default=False)
    Domain.populate()
    server.domainname = config.get('palette', 'domainname')
    server.domain = Domain.get_by_name(server.domainname)
    Environment.populate()
    server.environment = Environment.get()

    server.system = SystemManager(server)
    SystemManager.populate()

    # Set the log level from the system table
    server.st_config = SystemConfig(server.system)
    log.setLevel(server.st_config.debug_level)

    HttpControl.populate()
    StateControl.populate()
    DataSourceTypes.populate()

    server.auth = AuthManager(server)
    server.cred = CredentialManager(server)
    server.extract = ExtractManager(server)
    server.hrman = HttpRequestManager(server)

    # Status of the maintenance web server(s)
    server.maint_started = False

    Role.populate()
    UserProfile.populate()

    # Must be done after auth, since it uses the users table.
    server.alert_email = AlertEmail(server)

    # Must be set before EventControlManager
    server.yml = YmlManager(server)

    EventControl.populate()
    server.event_control = EventControlManager(server)

    server.version = version()
    # Send controller started/restarted and potentially "new version" events.
    old_version, new_version = server.controller_init_events()

    server.upgrade_rwlock = RWLock()

    server.workbooks = WorkbookManager(server)
    server.files = FileManager(server)
    server.cloud = CloudManager(server)
    server.firewall_manager = FirewallManager(server)
    server.license_manager = LicenseManager(server)
    server.state_manager = StateManager(server)

    server.notifications = NotificationManager(server)
    server.metrics = MetricManager(server)

    server.ports = PortManager(server)
    server.ports.populate()

    server.upgrade_version(old_version, new_version)

    clicmdclass = CliCmd(server)
    server.cli_cmd = clicmdclass.cli_cmd

    manager = AgentManager(server)
    server.agentmanager = manager

    manager.update_last_disconnect_time()

    log.debug("Starting agent listener.")
    manager.start()

    # Need to instantiate to initialize state and status tables,
    # even if we don't run the status thread.
    statusmon = TableauStatusMonitor(server, manager)
    server.statusmon = statusmon

    if not args.nosched:
        server.sched = Sched(server)
        server.sched.populate()
        # Make sure the populate finishes before the sched thread starts
        server.sched.start()

    if not args.nostatus:
        log.debug("Starting status monitor.")
        statusmon.start()

    server.serve_forever()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print "\nInterrupted.  Exiting."
        # pylint: disable=protected-access
        os._exit(1)
