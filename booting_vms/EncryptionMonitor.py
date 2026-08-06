class EncryptionMonitor:
    '''
    Class for Encryption Monitoring based on dm-crypt
    '''
    #Ubuntu default
    CRYPTTAB_PATH = "/etc/crypttab"

    def __init__(self, crypttab_path=None):
        self.encryption = {'is_encrypted':"", 'cipher':""}
        self.crypttab_path = crypttab_path or self.CRYPTTAB_PATH

    def get_encryption_info(self):

        crypttab_path = self.crypttab_path

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
