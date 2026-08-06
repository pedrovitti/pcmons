from Mysql_Db_Connector import Db_Connector

class VM(object):
    #the columns update_vm_info writes. Each instance gets its own copy: a dict
    #defined here and shared would carry one vm's values onto the next.
    COLUMNS = (
        'node_ip',
        'node_hostname',
        'reservation',
        'user',
        'instance_id',
        'dns_name',
        'private_dns_name',
        'public_dns_name',
        'state',
        'instance_type',
        'launch_time',
        'availability_zone',
        'kernel',
        'ramdisk',
        'last_check',
    )

    def __init__(self, db=None):
        self.db = db or Db_Connector()
        self.attributes = dict.fromkeys(self.COLUMNS)

    def save(self):
        self.db.update_vm_info(self.attributes)

if __name__ == "__main__":
    vm = VM()
    print vm.save()
