import string

class SSHAccessMonitor:
    '''
    Class for SSH Access Attempts Monitoring
    '''
    access_attempts = {'valid':0, 'invalid':0}

    def __init__(self):
        self.server = '150.162.63.32'

    def get_ssh_access_attempts(self):	
        pattern = "Failed password"
        #log_path = "/var/log/secure" #CentOS
        log_path = "/var/log/auth.log" #Ubuntu
        
        f = open(log_path, 'r')
        line = f.readline()
        
        valid_count = 0
        invalid_count = 0
		
        while line:
            if string.find(line, pattern) != -1:
                invalid_count += 1
            else:
                valid_count += 1
            line = f.readline()
		
        self.access_attempts['valid'] = str(valid_count)
        self.access_attempts['invalid'] = str(invalid_count)
		
        return self.access_attempts

if __name__=="__main__":
    sshaccessMon = SSHAccessMonitor()
    print sshaccessMon.get_ssh_access_attempts()
