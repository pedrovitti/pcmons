'''
Author: shirlei@gmail.com
Description: receives notifications from the vms and passes to the interface
Version: 1.0
'''
import commands, logging, sys
from SimpleXMLRPCServer import SimpleXMLRPCServer 
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
import running_vms.cluster.cluster_config as cluster_config

class NotificationServer:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename=cluster_config.PATH_TO_LOG_FILE)
        self.db = Db_Connector()
        server = SimpleXMLRPCServer((cluster_config.LISTEN_IP, cluster_config.LISTEN_PORT), logRequests=True, requestHandler=RequestHandler)
        server.register_function(self.get_vm_notification)
        try:
            server.serve_forever()
        except:
            e = sys.exc_info()[1]
            logging.error("server execution error in server_passive_checks: %s"%e)

    def get_vm_notification(self, data):
        '''
        Receives monitoring notifications from plugins running on VMs
        and records the data and/or passes to the configured interface
        '''
        #TODO: allow multiple interfaces at a time
        if cluster_config.INTERFACE.lower() == 'nagios':
            from interface.nagios import Nagios_Passive_Server as nagios
            nagios_service = nagios.NagiosPassiveServer()
            return nagios_service.process_notification(data,ipAddress[0])
            

        #TODO: record the data in a database for historical purposes

class RequestHandler(SimpleXMLRPCRequestHandler):
    def __init__(self, request, client_address, server):
            global ipAddress
            ipAddress = client_address
            SimpleXMLRPCRequestHandler.__init__(self, request, client_address, server)

if __name__ == "__main__":
    server = NotificationServer()
