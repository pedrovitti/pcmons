import commands
from MemoryMonitor import MemoryMonitor
from SystemLoadMonitor import SystemLoadMonitor
from HTTPConMonitor import HTTPConMonitor
from SSHAccessMonitor import SSHAccessMonitor
from AvailabilityMonitor import AvailabilityMonitor
from BackupMonitor import BackupMonitor
from EncryptionMonitor import EncryptionMonitor
from IntegrityMonitor import IntegrityMonitor
from MalwareMonitor import MalwareMonitor
from PasswordMonitor import PasswordMonitor
from VulnerabilityMonitor import VulnerabilityMonitor

import logging, time, xmlrpclib, datetime
from socket import error as socket_error
import settings

class Monitor:

    def __init__(self):
        self.memoryMonitor = MemoryMonitor()
        self.systemLoadMonitor = SystemLoadMonitor()
        self.httpMonitor = HTTPConMonitor()
        self.sshAccessMonitor = SSHAccessMonitor()
        self.availabilityMonitor = AvailabilityMonitor()
        self.backupMonitor = BackupMonitor()
        self.encryptionMonitor = EncryptionMonitor()
        self.integrityMonitor = IntegrityMonitor()
        self.malwareMonitor = MalwareMonitor()
        self.passwordMonitor = PasswordMonitor()
        self.vulnerabilityMonitor = VulnerabilityMonitor()

    def run(self):
        '''
        collect and report for as long as the vm is up
        '''
        while True:
            #the agent runs detached with its output sent to /dev/null, so the
            #log is where this is read
            logging.debug('collecting at %s'%datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
            data = self.get_monitoring_data()
            self.send_monitoring_data(data)
            time.sleep(300) # 5 minutes for now

    def get_monitoring_data(self):
        probes = (
            ('memory', self.memoryMonitor.get_meminfo),
            ('loadavg', self.systemLoadMonitor.get_loadavg),
            ('http', self.httpMonitor.get_http_connections),
            ('sshattempts', self.sshAccessMonitor.get_ssh_access_attempts),
            ('availability', self.availabilityMonitor.get_availability_info),
            ('backup', self.backupMonitor.get_backup_info),
            ('encryption', self.encryptionMonitor.get_encryption_info),
            ('integrity', self.integrityMonitor.get_integrity_info),
            ('malware', self.malwareMonitor.get_malware_info),
            ('password', self.passwordMonitor.get_password_security),
            ('vulnerability', self.vulnerabilityMonitor.get_vulnerability_info),
        )

        data = {}
        for name, probe in probes:
            try:
                data[name] = probe()
            except Exception, error:
                #a probe whose log file or command is missing must not
                #stop the remaining metrics from being reported
                logging.error('probe %s failed: %s'%(name, error))
        return data

    def send_monitoring_data(self,data):
        '''
        connect to a server to send monitoring data
        '''
        try:
            logging.debug('Connecting to Monitoring Server...')
            server = xmlrpclib.ServerProxy('%s:%s'%(settings.SERVER, settings.SERVER_PORT))
            sent = server.get_vm_notification(data)
        except (socket_error, xmlrpclib.Fault, xmlrpclib.ProtocolError, xmlrpclib.ResponseError), error_code:
            #the agent runs detached with its output sent to /dev/null, so the
            #log is the only place this is ever read
            logging.error('Err: (%s)'%error_code)

if __name__ == "__main__":
    monitor = Monitor()
    monitor.run()
