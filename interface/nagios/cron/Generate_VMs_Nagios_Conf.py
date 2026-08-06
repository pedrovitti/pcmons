'''
    Authors: shirlei@gmail.com/rafael.uriarte@gmail.com
    Description: Generates nagios config file for monitored VMs
    Version: 1.0
'''
import logging, os, time, commands, datetime
import sys
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
import running_vms.cluster.cluster_config
#not writtinf for now, doing testsssss
class Generate_VMs_Nagios_Conf:

    def __init__(self, db=None):
        self.db = db or Db_Connector()

    def run(self):
        '''
        regenerate the configuration and hand it to nagios if it changed
        '''
        self.create_nagios_conf_running_vms()
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
        try:
            fh = open(running_vms.cluster.cluster_config.NAGIOS_TEMP_CONF,'w')
            try:
                fh.write(self.build_conf(vms))
            finally:
                fh.close()
            self.remove_old_conf()
        except IOError as (errno, strerror):
            print "I/O error ({0}): {1}".format(errno,strerror)

    def build_conf(self, vms):
        '''
        the whole configuration for the running vms, as text
        '''
        conf = ''
        vms_str = ''
        nodes_groups = []
        for vm in vms:
            #a vm without a real address cannot be monitored
            if vm['public_dns_name'] == '0.0.0.0':
                continue

            hostname = "%s_%s_%s"%(vm['user'],vm['instance_id'],vm['node_hostname'])
            alias = "%s/%s(%s-%s)"%(vm['user'],vm['instance_id'],vm['node_hostname'],vm['node_ip'])

            conf = conf + self.define_host(vm['public_dns_name'], hostname, alias)
            conf = conf + self.define_service(hostname,'PING','check_ping!100.0,20%!500.0,60%')
            conf = conf + self.define_service_passive(hostname)

            vms_str = vms_str + "%s, "%hostname
            nodes_groups.append([hostname, vm['node_ip']])

        return conf + self.define_hostgroup(vms_str, nodes_groups)

    def define_host(self, address, hostname, alias):
        return "define host {\n \
                                    use linux-server     \n \
                                    address                %s\n \
                                    host_name               %s\n \
                                    alias                   %s\n \
                                }\n" % (address, hostname, alias)

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
                    #delimited, or terminating i-1 takes i-10's graphs with it:
                    #the files are named user_instanceid_node-Service.ncfg
                    if '_%s_'%terminated_vm_id in file:
                        sure_to_remove.append(file)
            for file_to_remove in sure_to_remove:
                print "Removing File: ",(path+'/'+file_to_remove)   
                os.remove(path+'/'+file_to_remove)   

    def define_service(self, host,service,check_command):
        service_conf = "define service {\n \
                            max_check_attempts	4 \n \
                            host_name		%s\n \
                            service_description	%s\n \
                            contact_groups          admins\n \
                            notification_options    w,u,c,r,n\n \
                            notification_interval   60\n \
                            notification_period     24x7\n \
                            check_command		%s\n \
                        }\n"%(host,service,check_command)
        return service_conf

    def define_service_passive(self, host):
        service_conf = "define service {\n \
                            max_check_attempts	4 \n \
                            host_name		%s\n \
                            service_description	RAM\n \
                            contact_groups          admins\n \
                            notification_options    w,u,c,r,n\n \
                            notification_interval   60\n \
                            notification_period     24x7\n \
                            check_command           check_dummy\n \
                            active_checks_enabled 0\n   passive_checks_enabled 1\n \
                        }\n"%(host)
        service_conf = service_conf+"define service {\n \
                            max_check_attempts	4 \n \
                            host_name		%s\n \
                            service_description	Cpu_Load\n \
                            contact_groups          admins\n \
                            notification_options    w,u,c,r,n\n \
                            notification_interval   60\n \
                            notification_period     24x7\n \
                            check_command           check_dummy!2\n \
                            active_checks_enabled 0\n \
                            passive_checks_enabled 1\n  }\n"%(host)
        service_conf = service_conf+"define service {\n \
                            max_check_attempts	4 \n \
                            host_name		%s\n \
                            service_description	HTTP_Connections\n \
                            contact_groups          admins\n \
                            notification_options    w,u,c,r,n\n \
                            notification_interval   60\n \
                            notification_period     24x7\n \
                            check_command           check_dummy!2\n \
                            active_checks_enabled 0\n \
                            passive_checks_enabled 1\n  }\n"%(host)
        service_conf = service_conf+"define service {\n \
                            max_check_attempts	4 \n \
                            host_name		%s\n \
                            service_description	SSH\n \
                            contact_groups          admins\n \
                            notification_options    w,u,c,r,n\n \
                            notification_interval   60\n \
                            notification_period     24x7\n \
                            check_command           check_ssh!\n \
                            active_checks_enabled 1\n \
                            }\n"%(host)
        return service_conf

    def define_service_group(self, ids):
        service_group = "define servicegroup {\n \
                            servicegroup_name	Virtual Machines\n \
                            alias	vms\n \
                            members	%s\n \
                        }\n"%ids
        return service_group

    def define_hostgroup(self, ids, nodes_groups):
        nodes = []
        #Create host groups for all vms
        hostgroup = "define hostgroup {\n \
                        hostgroup_name	Virtual Machines\n \
                        alias   vms\n \
                        members	%s\n \
                    }\n"%ids

        #Get unique nodes
        for node in nodes_groups:
           nodes.append(node[1])
        nodes_unique = set(nodes)

        #Create a host group for each node
        for node in nodes_unique:
            vms_nodes_str = ''
            for vm in nodes_groups:
                if node == vm[1]:
                    vms_nodes_str = vms_nodes_str + "%s, "%vm[0]
 
            hostgroup = hostgroup + "define hostgroup {\n \
                            hostgroup_name Node	%s\n \
                            alias   Vms on Node %s\n \
                            members	%s\n \
                         }\n"%(node,node,vms_nodes_str)


                        
        return hostgroup

if __name__ == "__main__":
    createFile = Generate_VMs_Nagios_Conf()
    createFile.run()
    sys.exit()
