from SimpleXMLRPCServer import SimpleXMLRPCServer
import commands
import re, sys
import logging
import node_config

class VM_Monitoring_Node_Plugin:
    """
    Class starts a XMLRPC server that answer the current running vms on this node
    """
    SUPPORTED_INFRA = ('eucalyptus', 'opennebula')

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
        output = commands.getoutput("virsh list")

        #virsh prints a header and a dashed rule before the domains; take the
        #name column of every row below the rule rather than slicing by column
        #position, which varies between libvirt versions
        domains = []
        past_header = False
        for line in output.splitlines():
            stripped = line.strip()
            if not past_header:
                if stripped and stripped == '-'*len(stripped):
                    past_header = True
                continue
            columns = stripped.split()
            if len(columns) >= 2:
                domains.append(columns[1])

        vms = []
        for domain in domains:
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
        return 'Please, provide one of the following values: %s'%(', '.join(self.SUPPORTED_INFRA))


    def get_vms(self, infra = 'eucalyptus'):
        logging.debug('Parameter provided: %s'%infra)
        if infra == 'eucalyptus':
            return self.eucalyptus()
        elif infra == 'opennebula':
            return self.opennebula()
        else:
            return self.do_default()

    def get_monitoring_data(self,data):
        logging.debug('monitoring data: %s'%data)
        return True


if __name__ == "__main__":
    client = VM_Monitoring_Node_Plugin()
    sys.exit()
