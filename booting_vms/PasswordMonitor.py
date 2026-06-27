
class PasswordMonitor:
    '''
    Class for Password Monitoring
    '''
    def __init__(self):
        self.password_security = {'max_age':0}

    def get_password_security(self):

        #Ubuntu default
        log_path = "/etc/login.defs"

        f = open(log_path, 'r')

        max_age = 0

        try:
            line = f.readline()
            while line:
                if line.find("#") == -1:
                    split = line.split("PASS_MAX_DAYS")
                    if len(split) == 2:
                        max_age = int(split[1])

                line = f.readline()

        finally:
            f.close()

        self.password_security['max_age'] = max_age

        return self.password_security

if __name__=="__main__":
    passwordMonitor = PasswordMonitor()
    print passwordMonitor.get_password_security()
