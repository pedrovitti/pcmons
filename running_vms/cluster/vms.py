from Mysql_Db_Connector import Db_Connector

class VM(object):
    attributes = {
        'node_ip':None,
        'node_hostname':None,
        'reservation':None,
        'user':None,
        'instance_id':None,
        'dns_name':None,
        'private_dns_name':None,
        'public_dns_name':None,
        'state': None,
        'instance_type':None,
        'launch_time':None,
        'availability_zone':None,
        'kernel':None,
        'ramdisk':None,
        'last_check':None,
    }
    
    def __init__(self):
        self.db = Db_Connector()

    def save(self):
        self.db.update_vm_info(self.attributes)

if __name__ == "__main__":
    vm = VM()
    print vm.save()

