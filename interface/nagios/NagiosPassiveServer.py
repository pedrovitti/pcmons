'''
    Author: rafael.uriarte@gmail.com/shirlei@gmail.com
    Description: process data and calls send_passive_check_nagios.sh
    Version: 1.0
'''
import commands, logging, sys
from SimpleXMLRPCServer import SimpleXMLRPCServer 
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
import running_vms.cluster.cluster_config as cluster_config
from interface.nagios import services

#nagios return codes
OK, WARNING, CRITICAL = 0, 1, 2

class NagiosPassiveServer:
    def __init__(self, db=None):
        try:
            logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename=cluster_config.PATH_TO_LOG_FILE)
            self.db = db or Db_Connector()
        except:
            e = sys.exc_info()[1]
            print 'NagiosPassiveServer error :', e

    def register_passive_check(self, hostname, service, status, number):
        print './passive_check.sh %s %s %s %s'%(hostname,service,status,number) 
        status, output = commands.getstatusoutput('./send_passive_check_nagios.sh %s %s %s %s'%(hostname,service,status,number) )
        print 'status: ',status
        print 'output: ',output
        if status == 0:
            print 'ok'
        else:
            print'error'


    def process_notification(self,data, ipAddress):
        logging.debug('notification from %s: %s'%(ipAddress, data))
        vm = self.vm_at(ipAddress)
        if vm is None:
            #an agent still reporting from an address the inventory does not
            #have as running: nothing to file the readings against
            logging.error('no running vm at %s; notification dropped'%ipAddress)
            return False

        hostname = "%s_%s_%s"%(vm['user'],vm['instance_id'],vm['node_hostname'])

        #the agent leaves out any probe that failed, so a metric can be missing
        #from an otherwise good notification. Register what did arrive.
        for metric, service in services.PASSIVE_SERVICES:
            if metric not in data:
                continue
            result = self.format_metric(metric, data[metric])
            if result is None:
                continue
            status, output = result
            self.register_passive_check(hostname, service, status, '"%s"'%output)

        return True

    def vm_at(self, address):
        '''
        the running vm reporting from this address, or None
        '''
        found = self.db.get_id_by_ip(address)
        if found is None:
            return None
        return self.db.get_vm_info(found['instance_id'])

    def format_metric(self, metric, reading):
        '''
        (status, output) for a reading, or None if it cannot be read. A probe
        that reports something unexpected costs its own check, not the rest.
        '''
        try:
            return getattr(self, 'format_%s'%metric)(reading)
        except (KeyError, TypeError, ValueError, ZeroDivisionError), error:
            logging.error('cannot read %s: %s (%s)'%(metric, error, reading))
            return None

    def sanitise(self, text):
        #a quote would end the shell argument and a pipe starts nagios
        #performance data; neither belongs in a value read off a vm
        return str(text).replace('"', '').replace('|', '/').strip()

    def format_memory(self, memory):
        total = memory['total']
        if total <= 0:
            raise ValueError('reading has no total')
        percentage = int(100*memory['used']/float(total))
        #kept as it is: nagiosgrapher parses this and holds history against it
        return OK, "%s;%s/%s"%(percentage, memory['used']/1024, total/1024)

    def format_loadavg(self, loadavg):
        if loadavg['1'] >= 3.0:
            status, state = CRITICAL, "CRITICAL"
        elif loadavg['1'] >= 1.5:
            status, state = WARNING, "WARNING"
        else:
            status, state = OK, "OK"
        return status, "%s - load average: %.2f, %.2f, %.2f"%(state, loadavg['1'], loadavg['5'], loadavg['10'])

    def format_http(self, http):
        return OK, "%s"%http['connections']

    def format_sshattempts(self, attempts):
        #counts only: what makes a failed login count alarming is a policy
        #decision, and belongs in the nagios service definition
        return OK, "OK - ssh logins: %s accepted, %s failed"%(
            self.sanitise(attempts['valid']), self.sanitise(attempts['invalid']))

    def format_availability(self, availability):
        return OK, "OK - up %s"%self.sanitise(availability['uptime'])

    def format_backup(self, backup):
        last = self.sanitise(backup['last_performed'])
        if not last:
            return WARNING, "WARNING - no backup recorded"
        return OK, "OK - last backup %s"%last

    def format_encryption(self, encryption):
        if encryption['is_encrypted'] != 'yes':
            return WARNING, "WARNING - disk is not encrypted"
        return OK, "OK - encrypted with %s"%self.sanitise(encryption['cipher'])

    def format_integrity(self, integrity):
        last = self.sanitise(integrity['last_performed'])
        if last in ('', '-'):
            return WARNING, "WARNING - no integrity scan recorded"
        return OK, "OK - last scan %s"%last

    def format_malware(self, malware):
        detected = int(malware['detected'])
        if detected > 0:
            return CRITICAL, "CRITICAL - %d infected file(s)"%detected
        return OK, "OK - no infected files, last scan %s"%self.sanitise(malware['last_scan'])

    def format_password(self, password):
        max_age = int(password['max_age'])
        if max_age <= 0:
            return WARNING, "WARNING - passwords never expire"
        return OK, "OK - passwords expire after %d days"%max_age

    def format_vulnerability(self, vulnerability):
        warn = int(vulnerability['warn'])
        fail = int(vulnerability['fail'])
        if fail > 0:
            return CRITICAL, "CRITICAL - %d failed, %d warned"%(fail, warn)
        if warn > 0:
            return WARNING, "WARNING - %d warned"%warn
        return OK, "OK - no findings"



if __name__ == "__main__":
    server = NagiosPassiveServer()
