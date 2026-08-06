
class IntegrityMonitor:
    '''
    Class for Integrity Monitoring based on tripwire
    '''
    def __init__(self):
        self.integrity = {'last_performed':""}

    def get_integrity_info(self):

        #Ubuntu default
        log_path = "/var/log/tripwire.log"

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
