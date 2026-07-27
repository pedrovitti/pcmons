import string

class BackupMonitor:
    '''
    Class for Backup Monitoring based on rsync
    '''
    #defined for each rsync backup (--log-file)
    LOG_PATH = "/var/log/rsync.log"

    def __init__(self, log_path=None):
        self.backup = {'last_performed':""}
        self.log_path = log_path or self.LOG_PATH

    def get_backup_info(self):
        log_path = self.log_path
        
        f = open(log_path, 'r')
        try:
            lines = f.readlines()
        finally:
            f.close()

        #a log that exists but holds no run yet is not a failure to report
        if len(lines) == 0:
            return self.backup

        last_line = lines[-1]
        last_backup = last_line[0:19] #date and time in the form YYYY/MM/DD HH:MM:SS

        self.backup['last_performed'] = last_backup
		
        return self.backup

if __name__=="__main__":
    backupMon = BackupMonitor()
    print backupMon.get_backup_info()
