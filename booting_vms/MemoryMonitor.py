import commands, os, sys, string, re

class MemoryMonitor:
    '''
        Class for Memory Usage Monitoring
    '''
    memory = {'used':0,'free':0,'cache':0,'total':0}

    def __init__(self):
        self.server = '150.162.63.25'

    def get_memory_usage(self):
        cmd = 'free -m | grep ^-'
        status, output = commands.getstatusoutput(cmd)
        if status == 0:
            return output
        return None

    def get_meminfo(self):
        memory = {'used':0,'free':0,'cache':0,'total':0}
        lines = self.parseSplitFile('/proc/meminfo')
        for line in lines:
            if re.match('MemFree',line[0]):
                memory['free'] = int(line[1])
            elif re.match('MemTotal', line[0]):
                memory['total'] = int(line[1])
            elif re.match('Buffer|Cached', line[0]):
                memory['cache'] = memory['cache'] + int(line[1])
        memory['used'] = memory['total'] - memory['free']
        self.memory = memory
        return self.memory

    def parseSplitFile(self,filename):
        f = open(filename, "rb")
        try:
            lines = f.readlines()
        finally:
            f.close()
        lines = map(lambda x: x.strip().split(), lines)
        return lines


if __name__=="__main__":
    memory = MemoryMonitor()
    print memory.get_meminfo()
