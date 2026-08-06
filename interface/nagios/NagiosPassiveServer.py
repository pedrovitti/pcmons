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
        instance_id = self.db.get_id_by_ip(ipAddress)
        vm = self.db.get_vm_info(instance_id['instance_id'])
        hostname = "%s_%s_%s"%(vm['user'],vm['instance_id'],vm['node_hostname'])

        #the agent leaves out any probe that failed, so a metric can be missing
        #from an otherwise good notification. Register what did arrive.
        if 'memory' in data:
            self.register_memory_check(hostname, data['memory'])

        if 'loadavg' in data:
            self.register_load_check(hostname, data['loadavg'])

        if 'http' in data:
            self.register_passive_check(hostname, 'HTTP_Connections', 0, '"%s"'%data['http']['connections'])

        return True

    def register_memory_check(self, hostname, memory):
        total = memory['total']
        if total <= 0:
            logging.error('memory reading has no total: %s'%memory)
            return
        percentage = int(100*memory['used']/float(total))
        self.register_passive_check(hostname, 'RAM', 0,
            '"%s;%s/%s"'%(percentage, memory['used']/1024, total/1024))

    def register_load_check(self, hostname, loadavg):
        if loadavg['1'] >= 3.0:
            state = "CRITICAL"
        elif loadavg['1'] >= 1.5:
            state = "WARNING"
        else:
            state = "OK"
        output = "%s - load average: %.2f, %.2f, %.2f"%(state, loadavg['1'], loadavg['5'], loadavg['10'])
        self.register_passive_check(hostname, 'Cpu_Load', 0, '"'+output+'"')



if __name__ == "__main__":
    server = NagiosPassiveServer()
