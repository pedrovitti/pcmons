import string

class BackupMonitor:
    '''
    Class for Backup Monitoring based on rsync
    '''
    def __init__(self):
        self.server = '150.162.63.32'
        self.backup = {'last_performed':""}
	
    def get_backup_info(self):	
        #defined for each rsync backup (--log-file)
        log_path = "/var/log/rsync.log" 
        
        f = open(log_path, 'r')
        lines = f.readlines()
		
        last_line = lines[-1]
        last_backup = last_line[0:19] #date and time in the form YYYY/MM/DD HH:MM:SS

        self.backup['last_performed'] = last_backup
		
        return self.backup

if __name__=="__main__":
    backupMon = BackupMonitor()
    print backupMon.get_backup_info()
