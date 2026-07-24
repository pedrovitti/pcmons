class SSHAccessMonitor:
    '''
    Class for SSH Access Attempts Monitoring
    '''
    #LOG_PATH = "/var/log/secure" #CentOS
    LOG_PATH = "/var/log/auth.log" #Ubuntu

    def __init__(self, log_path=None):
        self.access_attempts = {'valid':0, 'invalid':0}
        self.log_path = log_path or self.LOG_PATH

    def get_ssh_access_attempts(self):
        failed_pattern = "Failed password"
        accepted_pattern = "Accepted password"
        log_path = self.log_path

        valid_count = 0
        invalid_count = 0

        f = open(log_path, 'r')
        try:
            for line in f:
                if failed_pattern in line:
                    invalid_count += 1
                elif accepted_pattern in line:
                    valid_count += 1
        finally:
            f.close()

        self.access_attempts['valid'] = str(valid_count)
        self.access_attempts['invalid'] = str(invalid_count)

        return self.access_attempts

if __name__=="__main__":
    sshaccessMon = SSHAccessMonitor()
    print sshaccessMon.get_ssh_access_attempts()
