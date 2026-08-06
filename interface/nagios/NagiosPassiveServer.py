'''
Processes the readings and calls send_passive_check_nagios.sh.
'''
import commands, logging, sys
from SimpleXMLRPCServer import SimpleXMLRPCServer 
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
import running_vms.cluster.cluster_config as cluster_config
from interface.nagios import services
from interface import readings

#kept here as well: this module has always been where they were read from
OK, WARNING, CRITICAL = readings.OK, readings.WARNING, readings.CRITICAL

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
        return self.db.get_vm_by_ip(address)

    def format_metric(self, metric, reading):
        '''
        (status, output) for a reading, or None if it cannot be read. The
        judgement is shared: every interface makes the same one
        '''
        return readings.format_metric(metric, reading)



if __name__ == "__main__":
    server = NagiosPassiveServer()
