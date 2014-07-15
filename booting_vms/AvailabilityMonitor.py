import commands, string

class AvailabilityMonitor:
    '''
    Class for Availability Monitoring based on uptime
    '''
    availability = {'uptime':""}
		
    def __init__(self):
        self.server = '150.162.63.32'	
		
    def get_availability_info(self):	
        out = commands.getoutput('uptime')
        uptime = out.split(',')[0]
			
        self.availability['uptime'] = uptime
		
        return self.availability

if __name__=="__main__":
    availabilityMon = AvailabilityMonitor()
    print availabilityMon.get_availability_info()
