import commands
from MemoryMonitor import MemoryMonitor
from SystemLoadMonitor import SystemLoadMonitor
from HTTPConMonitor import HTTPConMonitor
import logging, time, xmlrpclib, datetime
from socket import error as socket_error
import settings

class Monitor:

    def __init__(self):
        self.memoryMonitor = MemoryMonitor()
        self.systemLoadMonitor = SystemLoadMonitor()       
        self.httpMonitor = HTTPConMonitor()       
        while True:
            now = datetime.datetime.now()
            print now.strftime("%d-%m-%Y %H:%M:%S")
            data = self.get_monitoring_data()
            self.send_monitoring_data(data)
            time.sleep(300) # 5 minutes for now

    def get_monitoring_data(self):
        data = {}
        #data.append(self.memoryMonitor.get_memory_usage())
        data['memory']= self.memoryMonitor.get_meminfo()
        data['loadavg'] = self.systemLoadMonitor.get_loadavg()
        data['http'] = self.httpMonitor.get_http_connections()
        return data

    def send_monitoring_data(self,data):
        '''
            connect to a server to send monitoring data
        '''
        try:
            logging.debug('Connecting to Monitoring Server...')
            server = xmlrpclib.ServerProxy('%s:%s'%(settings.SERVER, settings.SERVER_PORT))
            sent = server.get_vm_notification(data)
        except (socket_error, xmlrpclib.Fault, xmlrpclib.ProtocolError, xmlrpclib.ResponseError), error_code:   
            print error_code
            logging.error('Err: (%s)'%error_code)


if __name__ == "__main__":
    monitor = Monitor()
