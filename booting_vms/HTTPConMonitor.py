import commands

class HTTPConMonitor:
    '''
        Class for HTTP  Connections Monitoring
    '''
    http_connections = {'nconexoes':0}

    def __init__(self):
        self.server = '150.162.63.25'

    def get_http_connections(self):
    	#cmd = 'ps aux |  awk "{ print $1 }" | egrep "httpd|apache" | wc -l'
        cmd = 'netstat -anp |  grep 8080 | wc -l'
        status, output = commands.getstatusoutput(cmd)
        if status == 0:
            self.http_connections['nconexoes'] = output
        return self.http_connections

if __name__=="__main__":
    httpcon = HTTPConMonitor()
    print httpcon.get_http_connections()
