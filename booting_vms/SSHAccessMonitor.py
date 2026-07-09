class SSHAccessMonitor:
    '''
    Class for SSH Access Attempts Monitoring
    '''
    def __init__(self):
        self.server = '150.162.63.32'
        self.access_attempts = {'valid':0, 'invalid':0}

    def get_ssh_access_attempts(self):
        failed_pattern = "Failed password"
        accepted_pattern = "Accepted password"
        #log_path = "/var/log/secure" #CentOS
        log_path = "/var/log/auth.log" #Ubuntu

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
