import commands

class HTTPConMonitor:
    '''
        Class for HTTP  Connections Monitoring
    '''
    def __init__(self):
        self.http_connections = {'connections':0}

    def get_http_connections(self):
        #cmd = 'ps aux |  awk "{ print $1 }" | egrep "httpd|apache" | wc -l'
        cmd = 'netstat -anp |  grep 8080 | wc -l'
        status, output = commands.getstatusoutput(cmd)
        if status == 0:
            #wc prints the count padded on some platforms; the key is a number
            try:
                self.http_connections['connections'] = int(output.strip())
            except ValueError:
                pass
        return self.http_connections

if __name__=="__main__":
    httpcon = HTTPConMonitor()
    print httpcon.get_http_connections()
