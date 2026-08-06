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
    def __init__(self, db=None):
        logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename=cluster_config.PATH_TO_LOG_FILE)
        self.db = db or Db_Connector()
        self.server = None

    def serve(self):
        '''
        receives notifications until it is stopped
        '''
        self.server = SimpleXMLRPCServer((cluster_config.LISTEN_IP, cluster_config.LISTEN_PORT), logRequests=True, requestHandler=RequestHandler)
        self.server.register_function(self.get_vm_notification)
        try:
            self.server.serve_forever()
        except:
            e = sys.exc_info()[1]
            logging.error("server execution error in server_passive_checks: %s"%e)

    def get_vm_notification(self, data):
        '''
        Receives monitoring notifications from plugins running on VMs
        and records the data and/or passes to the configured interface
        '''
        return self.handle_notification(data, self.client_address())

    def client_address(self):
        '''
        the address the request being served came from, or None outside one
        '''
        return getattr(self.server, 'notification_address', None)

    def handle_notification(self, data, address):
        #which vm sent this is only known from the address it came from, so a
        #notification without one cannot be filed against anything
        if address is None:
            logging.error('notification with no client address; dropped')
            return False

        #TODO: allow multiple interfaces at a time
        interface = self.build_interface()
        if interface is None:
            logging.error('no interface configured for %s'%cluster_config.INTERFACE)
            return False

        #TODO: record the data in a database for historical purposes
        return interface.process_notification(data, address)

    def build_interface(self):
        if cluster_config.INTERFACE.lower() == 'nagios':
            #imported here rather than at the top: the interface imports the
            #database layer this module already holds open
            from interface.nagios import NagiosPassiveServer as nagios
            return nagios.NagiosPassiveServer()
        return None

class RequestHandler(SimpleXMLRPCRequestHandler):
    def __init__(self, request, client_address, server):
            #the address belongs to the request being served. Kept on the
            #server rather than in a module global, which any other server in
            #the process would have shared.
            server.notification_address = client_address[0]
            SimpleXMLRPCRequestHandler.__init__(self, request, client_address, server)

if __name__ == "__main__":
    server = NotificationServer()
    server.serve()
