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
	print "Initializing Node Plugin.."
        server = SimpleXMLRPCServer((node_config.LISTEN_IP, node_config.LISTEN_PORT), logRequests=True)
        server.register_function(self.do_default)
        server.register_function(self.get_vms)
        server.register_function(self.get_monitoring_data)
	try:
            server.serve_forever()
        except:
            e = sys.exc_info()[1]
            logging.error("server execution error: %s"%e)

    def list_running_vms(self, rename_instance_id=None):
        '''
        Lists the vms libvirt reports as running on this node. rename_instance_id
        maps the hypervisor domain name to the id the cloud platform uses.
        '''
        hostname = commands.getoutput('hostname')
        vms_running_host = commands.getoutput("virsh list | cut -c5-14")
        #drops the two header lines virsh prints before the domain list
        vms_running_host = vms_running_host.split()[3:]

        vms = []
        for domain in vms_running_host:
            instance_id = domain
            if rename_instance_id is not None:
                instance_id = rename_instance_id(domain)
            vms.append({'node_hostname':hostname,'instance_id':instance_id,})

        if len(vms) > 0:
            logging.debug("Vms returned :%s"%vms)
        else:
            logging.debug("No vm was returned")

        return vms

    def eucalyptus(self):
        '''
        This function get information about vms managed by eucalyptus
        '''
        return self.list_running_vms()

    def opennebula(self):
        '''
        This function get information about vms managed by opennebula
        '''
        #opennebula domains are named one-xxx, the cloud reports them as i-xxx
        return self.list_running_vms(lambda domain: domain.replace('one','i'))

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
        elif infra == 'opennebula':
            return self.opennebula()
	else:
	    return 'not implemented yet'
        #return values.get(infra, self.do_default)

    def get_monitoring_data(self,data):
        logging.debug('monitoring data: %s'%data)
        return True


if __name__ == "__main__":
    client = VM_Monitoring_Node_Plugin()
    sys.exit()
