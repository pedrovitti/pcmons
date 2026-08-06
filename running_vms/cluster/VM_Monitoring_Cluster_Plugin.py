#!/usr/bin/env python
from Mysql_Db_Connector import Db_Connector
import logging
import time
import xmlrpclib
from socket import error as socket_error
import boto.ec2.regioninfo
import boto
import cluster_config
import vms
import sys
import commands, subprocess
import socket

class VM_Monitoring_Cluster_Plugin:
    """
    Class to controll all the process of getting info from the IaaS provider and each of its nodes. Currently it supports eucalyptus and opennebula.
    """
    def __init__(self):
        self.db = Db_Connector()
       	# Using boto ec2 library to get info about running vms in an EC2 compatible environment
        region = boto.ec2.regioninfo.RegionInfo(name=cluster_config.INFRA, endpoint=cluster_config.IP_CLOUD_CONTROLLER)
        self.connection = boto.connect_ec2(aws_access_key_id=cluster_config.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=cluster_config.AWS_SECRET_ACCESS_KEY,
                              is_secure=False,
                              region=region,
                              port=cluster_config.EC2_INTERFACE_PORT_ON_CLOUD_CONTROLLER,
                              path=cluster_config.PATH_TO_EC2_SERVICE)
	self.nodes = self.grepNodes()
        #Set up logging
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename=cluster_config.PATH_TO_LOG_FILE)

    def run(self):
        '''
        poll the cloud and keep the stored inventory in step with it
        '''
        while True:
            vms = self.get_running_vms()
            self.store_vms_info(vms)
            self.mark_terminated_vms(vms)
            # Checks if any running vm has missing information (node placement, for example)
            self.update_vms_info()
            time.sleep(60)


    def get_running_vms(self):
        '''
        Gets the information about running information (as provided by EC2
        compatible cloud platform, like eucalyptus or opennebula
        '''
        list_reservations = self.connection.get_all_instances()
        vm = {}
        vms = []
        for i in list_reservations:
            for x in i.instances:
                vm={
                    'reservation':i.id,
                    'user':i.owner_id,
                    'availability_zone':x.placement,
                    'instance_id':x.id,
                    'launch_time':x.launch_time,
                    'dns_name':x.dns_name,
                    'private_dns_name':x.private_dns_name,
                    'public_dns_name':x.public_dns_name,
                    'instance_type':x.instance_type,
                    'kernel':x.kernel,
                    'ramdisk':x.ramdisk,
                    'state':x.state,
                }
                vms.append(vm) #one reservation for each instance? (bug?) (fixed)
        return vms

    def grepNodes(self, infra=cluster_config.INFRA, file=cluster_config.PATH_TO_EUCALYPTUS_CONFIG_FILE, pattern="NODES"):
        '''
        the nodes of this cloud, as addresses
        '''
        if infra == 'eucalyptus':
            return self.eucalyptus_nodes(file, pattern)
        elif infra == 'opennebula':
            return self.opennebula_nodes()

        logging.error('no node discovery for %s'%infra)
        return []

    def eucalyptus_nodes(self, file, pattern="NODES"):
        #the eucalyptus config carries them on one line: NODES="10.0.0.2 10.0.0.3"
        fileConf = open(file,'r')
        try:
            for line in fileConf:
                if pattern in line:
                    quoted = line.split('\"')
                    if len(quoted) > 1:
                        return quoted[1].split()
        finally:
            fileConf.close()

        #a config with no NODES line is a cloud with no nodes, not a crash:
        #this used to fall off the end and return None, and the caller stores
        #it and iterates it in the next breath
        logging.error('no %s line in %s'%(pattern, file))
        return []

    def opennebula_nodes(self):
        command = cluster_config.PATH_TO_OPENNEBULA + "/bin/onehost list | grep '  on' | awk {' print $2 '}"
        nodes = []
        for name in commands.getoutput(command).split("\n"):
            name = name.strip()
            if not name:
                continue
            try:
                nodes.append(socket.gethostbyname(name))
            except socket.error, error:
                #one node that does not resolve must not stop the controller
                logging.error('cannot resolve node %s: %s'%(name, error))
        return nodes


    def get_vm_list_running_on_node(self, node):
        '''
        queries the node for specific information abour its running vms
        '''
        vms = []
        try:
            logging.debug('Connecting to node %s'%node)
            node_server = xmlrpclib.ServerProxy('http://'+node+':'+cluster_config.PORT_PLUGINS_ON_NODES)
            vms = node_server.get_vms('opennebula') #cluster_config.INFRA - 'eucalyptus'
        except (socket_error, xmlrpclib.Fault, xmlrpclib.ProtocolError, xmlrpclib.ResponseError), error_code:
            logging.error('Err: (%s)'%error_code)
        return vms


    def store_vms_info(self, vms):
        '''
        store running vm info, for later query or historical purposes
        '''
        # adding or updating vms
        for vm in vms:
            result = self.db.get_vm_info(vm['instance_id'])
            if result != None :
                self.db.update_stored_vm_info(vm)
            else:
                self.db.insert_new_vm(vm)

    def update_opennebula_vms_info(self):
	'''
   	    testando metodo
        '''
	for node in self.nodes:
	    vms_on_node = self.get_vm_list_running_on_node(node)
            if len(vms_on_node) > 0:
	        for vm_on_node in vms_on_node:
		    self.db.update_vm_Ip_hostname(node, hostname=vm_on_node['node_hostname'], instance_id=vm_on_node['instance_id'])
         
    def update_vms_info(self):
        '''
        checks if there are some missing information about a stored vm and tries to update it by querying the node
        where the vm is running
        '''
        up_vms = []
        for row in self.db.get_running_vms():
            #one record per row: a single VM reused here would end up holding
            #the last row's values, saved once per row
            vm = vms.VM()
            incomplete = False
            for key, value in row.iteritems():
                if key in vm.attributes:
                    vm.attributes[key] = value
                    if value == '':
                        incomplete = True

            if not incomplete:
                continue

            logging.debug('vm %s has missing information; asking the nodes'%row['instance_id'])
            for node in self.nodes:
                for vm_on_node in self.get_vm_list_running_on_node(node):
                    if vm_on_node['instance_id'] == row['instance_id']:
                        vm.attributes['node_hostname'] = vm_on_node['node_hostname']
                        vm.attributes['node_ip'] = node
            up_vms.append(vm)

        for up_vm in up_vms:
            up_vm.save()
	if(cluster_config.INFRA == 'opennebula'):
	    self.update_opennebula_vms_info()

    def mark_terminated_vms(self, vms):
        running_vms = self.db.get_info_for_monitoring_running_Vms()
        running_vms_ids = [running_vm['instance_id'] for running_vm in running_vms]
        vms_ids = [vm['instance_id'] for vm in vms]

        #a vm the db still has as running but the cloud no longer reports is
        #gone, and so is one the cloud reports as terminated outright
        terminated_list = set(id for id in running_vms_ids if id not in vms_ids)
        terminated_list.update(vm['instance_id'] for vm in vms if vm['state'] == 'terminated')

        for terminated_vm_id in terminated_list:
            self.db.set_status_terminated(terminated_vm_id)

if __name__ == "__main__":
    controller = VM_Monitoring_Cluster_Plugin()
    controller.run()
    sys.exit()
