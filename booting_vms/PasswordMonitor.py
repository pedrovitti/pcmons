
class PasswordMonitor:
    '''
    Class for Password Monitoring
    '''
    #Ubuntu default
    LOGIN_DEFS_PATH = "/etc/login.defs"

    def __init__(self, login_defs_path=None):
        self.password_security = {'max_age':0}
        self.login_defs_path = login_defs_path or self.LOGIN_DEFS_PATH

    def get_password_security(self):

        log_path = self.login_defs_path

        f = open(log_path, 'r')

        max_age = 0

        try:
            line = f.readline()
            while line:
                if line.find("#") == -1:
                    split = line.split("PASS_MAX_DAYS")
                    if len(split) == 2:
                        try:
                            max_age = int(split[1])
                        except ValueError:
                            pass

                line = f.readline()

        finally:
            f.close()

        self.password_security['max_age'] = max_age

        return self.password_security

if __name__=="__main__":
    passwordMonitor = PasswordMonitor()
    print passwordMonitor.get_password_security()
