class EncryptionMonitor:
    '''
    Class for Encryption Monitoring based on dm-crypt
    '''
    def __init__(self):
        self.server = '150.162.63.32'
        self.encryption = {'is_encrypted':"", 'cipher':""}

    def get_encryption_info(self):

        #Ubuntu default
        crypttab_path = "/etc/crypttab"

        is_encrypted = "no"
        cipher = "-"

        f = open(crypttab_path, 'r')
        try:
            for line in f:
                if line.find("#") != -1:
                    continue
                #crypttab fields: target source key options
                fields = line.split()
                if len(fields) < 4:
                    continue

                is_encrypted = "yes"
                cipher = fields[3]
        finally:
            f.close()

        self.encryption['is_encrypted'] = is_encrypted
        self.encryption['cipher'] = cipher

        return self.encryption

if __name__=="__main__":
    encMon = EncryptionMonitor()
    print encMon.get_encryption_info()
