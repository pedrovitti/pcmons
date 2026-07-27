
class IntegrityMonitor:
    '''
    Class for Integrity Monitoring based on tripwire
    '''
    #Ubuntu default
    LOG_PATH = "/var/log/tripwire.log"

    def __init__(self, log_path=None):
        self.integrity = {'last_performed':""}
        self.log_path = log_path or self.LOG_PATH

    def get_integrity_info(self):

        log_path = self.log_path

        f = open(log_path, 'r')
        try:
            lines = f.readlines()
        finally:
            f.close()

        pattern = "Report created on:"
        last_scan = "-"

        for line in lines:
            split_line = line.split(pattern)
            if len(split_line) == 2:
                last_scan = split_line[1]

        self.integrity['last_performed'] = last_scan

        return self.integrity

if __name__=="__main__":
    integrityMon = IntegrityMonitor()
    print integrityMon.get_integrity_info()
