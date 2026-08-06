'''
Receives notifications from the vms and passes them to the configured interfaces.
'''
import commands, logging, sys
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
from running_vms.cluster.history import History
import running_vms.cluster.cluster_config as cluster_config
from interface import registry

class NotificationServer:
    def __init__(self, db=None, history=None):
        logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename=cluster_config.PATH_TO_LOG_FILE)
        self.db = db or Db_Connector()
        self.history = history or History(self.db)
        self.interfaces = None
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

        #kept before the interfaces are asked for, so that readings survive a
        #cluster whose interface is misconfigured
        self.record_history(data, address)

        interfaces = self.active_interfaces()
        if not interfaces:
            logging.error('no interface configured; notification dropped')
            return False

        #the agent is told the reading was taken if anything took it. An
        #interface that is down is worth reporting, but not worth failing a
        #notification the others filed
        taken = False
        for name, interface in interfaces:
            try:
                if interface.process_notification(data, address):
                    taken = True
            except:
                error = sys.exc_info()[1]
                logging.error('interface %s could not take the notification from %s: %s'%(name, address, error))
        return taken

    def record_history(self, data, address):
        '''
        keep the readings this notification carries. Returns how many were
        stored. Nothing here is allowed to fail the notification: history is
        worth less than the check result the vm is waiting to have filed
        '''
        if not cluster_config.KEEP_HISTORY:
            return 0
        try:
            vm = self.db.get_id_by_ip(address)
            if vm is None:
                #the interface will report the same thing and drop the
                #notification; there is nothing to file readings against
                logging.error('no running vm at %s; readings not kept'%address)
                return 0
            return self.history.record(vm['instance_id'], data)
        except:
            e = sys.exc_info()[1]
            logging.error('readings from %s not kept: %s'%(address, e))
            return 0

    def active_interfaces(self):
        '''
        the interfaces, built once and kept. An interface holds a database
        connection, and one that reports changes holds what it last saw:
        building them per notification opened a connection every five minutes
        per vm and forgot everything in between
        '''
        if self.interfaces is None:
            self.interfaces = self.build_interfaces()
        return self.interfaces

    def build_interfaces(self):
        '''
        the configured interfaces, in the order they were configured
        '''
        #the interfaces share the server's connection rather than opening one
        #each: they are built once and kept for the life of the process
        return registry.build_all(self.configured_interfaces(), self.db)

    def configured_interfaces(self):
        '''
        the interface names to build. INTERFACE is what a config written
        before there could be more than one sets, and is honoured so that
        upgrading the code does not silently stop a cluster reporting
        '''
        configured = getattr(cluster_config, 'INTERFACES', ())
        if configured:
            return list(configured)
        single = getattr(cluster_config, 'INTERFACE', '')
        if single:
            return [single]
        return []

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
