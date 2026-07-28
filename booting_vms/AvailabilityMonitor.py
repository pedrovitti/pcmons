import commands, re, string

class AvailabilityMonitor:
    '''
    Class for Availability Monitoring based on uptime
    '''
    #"HH:MM:SS up 1:04,  0 users,  load average: ..." -- and once the machine
    #has been up for a day the elapsed time itself contains a comma
    UPTIME = re.compile(r'\bup\s+(.*?),\s+\d+\s+users?')

    def __init__(self):
        self.availability = {'uptime':""}

    def get_availability_info(self):
        out = commands.getoutput('uptime')

        self.availability['uptime'] = self.parse_uptime(out)

        return self.availability

    def parse_uptime(self, out):
        match = self.UPTIME.search(out)
        if match:
            return match.group(1)
        return out.split(',')[0].strip()

if __name__=="__main__":
    availabilityMon = AvailabilityMonitor()
    print availabilityMon.get_availability_info()
