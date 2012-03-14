import logging
import MySQLdb
import cluster_config

class Db_Connector:

    def __init__(self):
        # Set up logging
        logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',datefmt='%m-%d %H:%M',filename=cluster_config.PATH_TO_LOG_FILE,filemode='w')
        self.connect()

    def connect(self):    
        self.db = MySQLdb.connect(host=cluster_config.DATABASES['default']['HOST'], port=cluster_config.DATABASES['default']['PORT'], user=cluster_config.DATABASES['default']['USER'],passwd=cluster_config.DATABASES['default']['PASSWORD'], db=cluster_config.DATABASES['default']['NAME'])
        #self.cur = self.db.cursor()
        self.cur = self.db.cursor(cursorclass=MySQLdb.cursors.DictCursor)

    def get_vm_info(self, instance_id):
        sql = "SELECT * FROM %s WHERE instance_id='%s'"%(cluster_config.VM_TABLE, instance_id)
        self.cur.execute(sql)
        result = self.cur.fetchone()
        return result

    def update_stored_vm_info(self,vm):
        sql = "UPDATE %s SET last_check=now(), reservation='%s', dns_name='%s', private_dns_name='%s', public_dns_name='%s', state='%s', instance_type='%s', availability_zone='%s' WHERE instance_id='%s'"%(cluster_config.VM_TABLE, vm['reservation'], vm['dns_name'], vm['private_dns_name'], vm['public_dns_name'], vm['state'], vm['instance_type'], vm['availability_zone'], vm['instance_id'])
        result = self.cur.execute(sql)
        if result == 1:
            logging.debug('vm %s updated'%vm)
        else:
            logging.debug('vm %s was not updated'%vm)
        return result

    def insert_new_vm(self, vm):
        sql = "INSERT INTO vmmonitor_vm(reservation,user,instance_id,dns_name,private_dns_name,public_dns_name,state,instance_type,launch_time,availability_zone,kernel,ramdisk,last_check) values('%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s',now())"%(vm['reservation'],vm['user'],vm['instance_id'],vm['dns_name'],vm['private_dns_name'],vm['public_dns_name'],vm['state'],vm['instance_type'],vm['launch_time'],vm['availability_zone'],vm['kernel'],vm['ramdisk'])
        result = self.cur.execute(sql)
        if result == 1:
            logging.debug('vm %s inserted in the db'%vm)
        else:
            logging.debug('vm %s was not inserted'%vm)
        return result
    def get_stored_vms_ids_without_IP(self):
        sql = "SELECT instance_id FROM %s WHERE node_ip='' or node_ip=NULL"%cluster_config.VM_TABLE
        self.cur.execute(sql)
        ids = self.cur.fetchall()
        return ids

    def update_vm_Ip_hostname(self,ip, hostname, instance_id):
        sql = "UPDATE %s set node_ip='%s', node_hostname='%s' WHERE instance_id='%s'"%(cluster_config.VM_TABLE,ip, hostname,instance_id)
        result = self.cur.execute(sql)
        if result == 1:
            logging.debug('vm %s from node %s updated'%(instance_id, ip))
        else:
            logging.debug('vm %s from node %s was not updated'%(instance_id, ip))
        return result
    def get_info_for_monitoring_running_Vms(self):
        sql = "SELECT instance_id, user, public_dns_name, node_hostname, node_ip FROM %s WHERE state='running'"%(cluster_config.VM_TABLE)
        self.cur.execute(sql)
        vms = self.cur.fetchall()
        return vms

    def get_info_for_monitoring_old_Vms(self):
        sql = "SELECT instance_id, user, public_dns_name, node_hostname, node_ip FROM %s WHERE state='terminated'"%(cluster_config.VM_TABLE)
        self.cur.execute(sql)
        vms = self.cur.fetchall()
        return vms

    def get_id_by_ip(self, ip):
        sql = "SELECT instance_id FROM %s WHERE public_dns_name='%s' AND state='running' "%(cluster_config.VM_TABLE,ip)
        self.cur.execute(sql)
        vms = self.cur.fetchall()
        return vms[0]

    def set_status_terminated(self,instance_id):
        sql = "UPDATE %s set state='terminated' WHERE instance_id='%s'"%(cluster_config.VM_TABLE,instance_id)
        result = self.cur.execute(sql)
        if result == 1:
            logging.debug('vm %s status set to terminated'%(instance_id))
        else:
            logging.debug('vm %s status not set to terminated'%(instance_id))
        return result


# new methods introduced in 07102010 (maybe they will stay, maybe not!)

    def update_vm_info(self, vm_info):
        str = " "
        for key, value in vm_info.iteritems():
            str = "%s %s = '%s', "%(str, key,value)
        sql_update = "UPDATE vmmonitor_vm set %s WHERE instance_id='%s'"%(str[:-2], vm_info['instance_id'])
        
        result = self.cur.execute(sql_update)
        if result == 1:
            logging.debug('vm %s status updated'%(vm_info['instance_id']))
        else:
            logging.debug('vm %s status not updated'%(vm_info['instance_id']))
        print sql_update

    def get_running_vms(self):
        sql = "SELECT * FROM vmmonitor_vm WHERE state!='terminated'"
        self.cur.execute(sql)
        vms = self.cur.fetchall()
        return vms
