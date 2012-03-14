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
    def __init__(self):
        try:
            logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename=cluster_config.PATH_TO_LOG_FILE)
            self.db = Db_Connector()
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
        print 'data : ' , data
        instance_id = self.db.get_id_by_ip(ipAddress)
        vm = self.db.get_vm_info(instance_id['instance_id'])
        hostname = "%s_%s_%s"%(vm['user'],vm['instance_id'],vm['node_hostname'])

        memPercentage = int( 100*(data['memory']['used'])/float(data['memory']['total']))
        self.register_passive_check(hostname, 'RAM', 0, '"'+str(memPercentage) + ';'+str((data['memory']['used']/1024))+'/'+str((data['memory']['total']/1024))+'"')

        #CPU
        if data['loadavg']['1'] >= 3.0:
            output = "CRITICAL - load average: %.2f, %.2f, %.2f" % (data['loadavg']['1'],data['loadavg']['5'],data['loadavg']['10'])
        elif data['loadavg']['1'] >= 1.5:
            output =  "WARNING - load average: %.2f, %.2f, %.2f" % (data['loadavg']['1'],data['loadavg']['5'],data['loadavg']['10'])
        else:
            
            print 'data: ', data['loadavg']['1']
            output = "OK - load average: %.2f, %.2f, %.2f" % (data['loadavg']['1'],data['loadavg']['5'],data['loadavg']['10'])

        self.register_passive_check(hostname, 'Cpu_Load', 0, '"'+output+'"')
        
        #HTTP Connections
        self.register_passive_check(hostname, 'HTTP_Connections', 0, '"'+data['http']['nconexoes']+'"')

        return True



if __name__ == "__main__":
    server = NagiosPassiveServer()
