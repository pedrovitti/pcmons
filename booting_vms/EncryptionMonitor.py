import string, re

class EncryptionMonitor:
    '''
    Class for Encryption Monitoring based on dm-crypt
    '''
    encryption = {'is_encrypted':"", 'cipher':""}
	
    def __init__(self):
        self.server = '150.162.63.32'
	
    def get_encryption_info(self):	

        #Ubuntu default
        log_path = "/etc/crypttab"
        
        is_encrypted = "no"
        cipher = "-"
        
        f = open(log_path, 'r')
        
        line = f.readline()
        while line:
            if line.find("#") == -1:
                line_trimmed = re.sub(' +',' ', line)
                line_trimmed.split()
				
                is_encrypted = "yes"
                cipher = line_trimmed[3]
                
            line = f.readline()
			
        self.encryption['is_encrypted'] = is_encrypted
	self.encryption['cipher'] = cipher
				
        return self.encryption

if __name__=="__main__":
    encMon = EncryptionMonitor()
    print encMon.get_encryption_info()
