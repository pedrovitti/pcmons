from SimpleXMLRPCServer import SimpleXMLRPCServer
import commands
import re, sys
import logging
import node_config

class VM_Monitoring_Node_Plugin:
    """
    Class starts a XMLRPC server that answer the current running vms on this node
    """
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename=node_config.PATH_TO_LOG_FILE)
        server = SimpleXMLRPCServer((node_config.LISTEN_IP, node_config.LISTEN_PORT), logRequests=True)
        server.register_function(self.do_default)
        server.register_function(self.get_vms)
        server.register_function(self.get_monitoring_data)
        try:
            server.serve_forever()
        except:
            e = sys.exec_info()[1]
            logging.error("server execution error: %s"%e)

    def eucalyptus(self):
        '''
        This function get information about vms managed by eucalyptus
        '''
        hostname = commands.getoutput('hostname')
        vms = [ ]
        vm = { }
        vms_running_host = commands.getoutput("virsh list | cut -c5-14")
        vms_running_host  = vms_running_host.split()[3:]
        for vm in vms_running_host:
            vm = {'node_hostname':hostname,'instance_id':vm,}
            vms.append(vm)
        if len(vms) > 0:
            logging.debug("Vms returned :%s"%vms)
        else:
            logging.debug("No vm was returned")

        return vms

    def opennebula(self):
        return 'Not implemented yet'

    def do_default(self):
        msg = 'Please, provide one of the following values:'
        for value in values:
            msg = msg + value
        return msg


    def get_vms(self, infra = 'eucalyptus'):
        logging.debug('Parameter provided: %s'%infra)
        #values = {'eucalyptus': self.eucalyptus,'opennebula': self.opennebula,}
        if infra == 'eucalyptus':
            return self.eucalyptus()
        else:
            return 'no implemented'
        #return values.get(infra, self.do_default)

    def get_monitoring_data(self,data):
        logging.debug('monitoring data: %s'%data)
        return True


if __name__ == "__main__":
    client = VM_Monitoring_Node_Plugin()
    sys.exit()
