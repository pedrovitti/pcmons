from xml.etree import ElementTree as ET
import logging, os, time, commands, datetime
import sys
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
import running_vms.cluster.cluster_config


class Generate_VMs_Nagios_Conf:
    hostnames = []
    nodes_group = []
    
    def __init__(self):
        self.db = Db_Connector()
        self.create_nagios_conf_running_vms();
        self.reload_nagios_if_necessary()
    
    def reload_nagios_if_necessary(self):
        # getting date for logging purposes
        now = datetime.datetime.now()
        print now.strftime("%d-%m-%Y %H:%M:%S")
        if os.path.isfile(running_vms.cluster.cluster_config.VMS_NAGIOS_FILE):
            md5a = commands.getoutput("md5sum "+running_vms.cluster.cluster_config.NAGIOS_TEMP_CONF+" | awk '{ print $1 }'")
            md5b = commands.getoutput("md5sum %s | awk ' { print $1 }'"%running_vms.cluster.cluster_config.VMS_NAGIOS_FILE)
            if md5a != md5b:
                print 'Moving File'
                os.system('mv '+running_vms.cluster.cluster_config.NAGIOS_TEMP_CONF + ' %s'%running_vms.cluster.cluster_config.VMS_NAGIOS_FILE)
                self.reload_nagios()
            else:
                print 'no changes'
        else:
            os.system('mv '+running_vms.cluster.cluster_config.NAGIOS_TEMP_CONF + ' %s'%running_vms.cluster.cluster_config.VMS_NAGIOS_FILE)
            self.reload_nagios()

    def reload_nagios(self):
        os.system(running_vms.cluster.cluster_config.COMMAND_TO_RELOAD_NAGIOS)


    def create_nagios_conf_running_vms(self):
        vms = self.db.get_info_for_monitoring_running_Vms()
        if len(vms) > 0:
            try:
                fh = open(running_vms.cluster.cluster_config.NAGIOS_TEMP_CONF,'w')

                try:
                    tree = ET.parse('basic_monitoring.xml')
                except TypeError, e:
                    print 'error :',e

                for vm in vms:
                    #Check if the machine has a valide ip address, if not , it's not possible to monitorate
                    if vm['public_dns_name'] != '0.0.0.0':
                        hostname = "%s_%s_%s"%(vm['user'],vm['instance_id'],vm['node_hostname'])
                        self.hostnames.append(hostname)
                        alias = "%s/%s(%s-%s)"%(vm['user'],vm['instance_id'],vm['node_hostname'],vm['node_ip'])
                        if vm['node_ip'] != '':
                            vm_host = [vm['node_ip'],hostname]
                            self.nodes_group.append(vm_host)
                        host_def = self.define_host(hostname, alias, vm['public_dns_name'])
                        fh.write(host_def)
                        service = tree.findall('services/service')
                        for s in service:
                            child = s.getchildren()
                            services = self.define_passive_service(hostname, child)
                            fh.write(services)
        
                hostgroup = self.define_hostgroup()
                fh.write(hostgroup)
        
                fh.close()
            except IOError, (errno, strerror):
                print "I/O error ({0}): {1}".format(errno,strerror)
    

    def define_passive_service(self, host, data):
        service_conf = "define service {\n  "
        service_conf = service_conf + "\t host_name %s \n "%(host)
        for d in data:
            service_conf =  service_conf + "\t %s  \t %s \n "%(d.tag, d.text)
        service_conf = service_conf + "}\n"
        return service_conf

    def define_host(self, hostname, alias, address):
        conf = "define host {\n \
                    use linux-server     \n \
                    address                %s\n \
                    host_name               %s\n \
                    alias                   %s\n \
                }\n" % (address, hostname, alias)
        return conf
   
    # for now, define_service_group is not being used
    def define_service_group(self, ids):
        service_group = "define servicegroup {\n \
                            servicegroup_name	Virtual Machines\n \
                            alias	vms\n \
                            members	%s\n \
                        }\n"%ids
        return service_group
    
    def define_hostgroup(self):
        nodes = []
        hosts = ''
        #Create host groups for all vms
        for vm_host in self.nodes_group:
            hosts = hosts +  vm_host[1] + ","
        print hosts

        hostgroup = "define hostgroup {\n \
                        hostgroup_name	Virtual Machines\n \
                        alias   vms\n \
                        members	%s\n \
                    }\n"%hosts

        #Get unique nodes
        for node in self.nodes_group:
           nodes.append(node[0])
        nodes_unique = set(nodes)

        #Create a host group for each node
        for node in nodes_unique:
            vms_nodes_str = ''
            for vm in self.nodes_group:
                if node == vm[0]:
                    vms_nodes_str = vms_nodes_str + "%s, "%vm[1]
 
            hostgroup = hostgroup + "define hostgroup {\n \
                            hostgroup_name Node	%s\n \
                            alias   Vms on Node %s\n \
                            members	%s\n \
                         }\n"%(node,node,vms_nodes_str)


        return hostgroup
    
    def remove_old_conf(self):
        if running_vms.cluster.cluster_config.USING_NAGIOSGRAPHER:
            hostnames_equals_file_names = []
            
            path=running_vms.cluster.cluster_config.PATH_SERVICEEXT_NAGIOSGRAPHER
            dirList=os.listdir(path)
            sure_to_remove = []
            terminated_vms = self.db.get_info_for_monitoring_old_Vms()
            for file in dirList:
                for terminated_vm in terminated_vms:
                    terminated_vm_id = terminated_vm['instance_id'].replace('-','_')
                    if terminated_vm_id in file:
                        sure_to_remove.append(file)
            for file_to_remove in sure_to_remove:
                print "Removing File: ",(path+'/'+file_to_remove)   
                os.remove(path+'/'+file_to_remove)   

if __name__ == "__main__":
    generate_conf = Generate_VMs_Nagios_Conf()
    sys.exit(0)
