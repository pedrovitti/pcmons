import os,sys

class SystemLoadMonitor:
    '''
        Class for CPU Usage Monitoring
    '''
    loadavg = {'1':0.00, '5':0.00, '10':0.00}

   # def __init__(self):
    #$    self.get_cpu_usage()   

    def get_loadavg(self):

        (d1, d2, d3) = os.getloadavg()
        self.loadavg['1'] = d1
        self.loadavg['5'] = d2
        self.loadavg['10'] = d3
        return self.loadavg

#        if d1 >= 3.0:
 #           output = "CRITICAL - load average: %.2f, %.2f, %.2f" % (d1,d2,d3)
  #      elif d1 >= 1.5:
   #         output =  "WARNING - load average: %.2f, %.2f, %.2f" % (d1,d2,d3)
    #    else:
     #       output = "OK - load average: %.2f, %.2f, %.2f" % (d1,d2,d3)
      #  return output

if __name__=="__main__":
    systemload = SystemLoadMonitor()
    print systemload.get_loadavg()
