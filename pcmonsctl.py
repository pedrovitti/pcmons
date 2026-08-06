'''
Asks the cluster what it knows, from a terminal.

Everything the cluster records has until now been readable only through Nagios
or by opening the database by hand: which vms it knows about, what the last
reading from one was, whether an agent has gone quiet. Those are the questions
somebody asks while something is wrong, which is the worst time to be writing
SQL.

    pcmonsctl vms                       every vm, and whether it is still reporting
    pcmonsctl show i-42                 the last reading of every metric
    pcmonsctl history i-42 memory used  one value over time
    pcmonsctl silent [minutes]          vms that have stopped reporting
    pcmonsctl forget i-42               drop the readings kept for a vm

It reads; only forget writes, and it says what it is about to drop.
'''
import sys
sys.path.append('/opt/pcmons/')

#how long a vm may say nothing before it is worth mentioning. The agent
#reports every five minutes, so this is three missed rounds
SILENT_AFTER_MINUTES = 15

#readings shown by history when no count is asked for
DEFAULT_LIMIT = 20


class Console:
    '''
    the commands, over a database and a history. Both are handed in so that
    this can be driven without either
    '''

    def __init__(self, db=None, history=None, out=None):
        self.out = out or sys.stdout
        if db is None:
            from running_vms.cluster.Mysql_Db_Connector import Db_Connector
            db = Db_Connector()
        self.db = db
        if history is None:
            from running_vms.cluster.history import History
            history = History(db)
        self.history = history

    def write(self, line=''):
        self.out.write('%s\n'%line)

    def table(self, headings, rows):
        '''
        columns wide enough for what is in them. A vm whose name is longer
        than the heading is the normal case, not the exception
        '''
        if not rows:
            return
        widths = []
        for column in range(len(headings)):
            widest = max([len(str(row[column])) for row in rows] + [len(headings[column])])
            widths.append(widest)
        self.write('  '.join(str(h).ljust(w) for h, w in zip(headings, widths)).rstrip())
        for row in rows:
            self.write('  '.join(str(v).ljust(w) for v, w in zip(row, widths)).rstrip())

    def vms(self, argv):
        '''every vm in the inventory, and whether it is still reporting'''
        vms = self.db.get_running_vms()
        if not vms:
            self.write('no vms recorded')
            return 0
        rows = []
        for vm in sorted(vms, key=lambda vm: vm['instance_id']):
            seen = self.history.last_seen(vm['instance_id'])
            rows.append((vm['instance_id'], vm.get('user') or '-',
                         vm.get('state') or '-', vm.get('node_hostname') or '-',
                         vm.get('public_dns_name') or '-',
                         seen if seen is not None else 'never'))
        self.table(('INSTANCE', 'USER', 'STATE', 'NODE', 'ADDRESS', 'LAST READING'), rows)
        return 0

    def show(self, argv):
        '''the last value of every field this vm reported'''
        if not argv:
            return self.complain('show needs the instance id of a vm')
        instance_id = argv[0]
        latest = self.history.latest(instance_id)
        if not latest:
            self.write('nothing has been recorded for %s'%instance_id)
            return 1
        rows = []
        for metric in sorted(latest.keys()):
            for field in sorted(latest[metric].keys()):
                rows.append((metric, field, latest[metric][field]))
        self.table(('METRIC', 'FIELD', 'VALUE'), rows)
        self.write()
        seen = self.history.last_seen(instance_id)
        self.write('last reading %s'%seen)
        if self.history.is_silent(instance_id, minutes=SILENT_AFTER_MINUTES):
            #the readings above are the last ones that arrived, which is not
            #the same as the state of the vm now
            self.write('WARNING: nothing has arrived for a while; '
                       'the values above are the last ones seen')
        return 0

    def history_of(self, argv):
        '''one value over time, oldest first'''
        if len(argv) < 3:
            return self.complain('history needs an instance id, a metric and a field')
        instance_id, metric, field = argv[0], argv[1], argv[2]
        limit = DEFAULT_LIMIT
        if len(argv) > 3:
            try:
                limit = int(argv[3])
            except ValueError:
                return self.complain('%r is not a number of readings'%argv[3])
        series = self.history.series(instance_id, metric, field, limit=limit)
        if not series:
            self.write('no %s %s recorded for %s'%(metric, field, instance_id))
            return 1
        self.table(('WHEN', 'VALUE'), series)
        average = self.history.average(instance_id, metric, field, limit=limit)
        peak = self.history.peak(instance_id, metric, field, limit=limit)
        if average is not None:
            #a spike between two calm readings is what the series is read for,
            #and it is easy to miss in a column of numbers
            self.write()
            self.write('average %.2f, peak %.2f over %d readings'%(
                average, peak, len(series)))
        return 0

    def silent(self, argv):
        '''vms that have stopped reporting'''
        minutes = SILENT_AFTER_MINUTES
        if argv:
            try:
                minutes = int(argv[0])
            except ValueError:
                return self.complain('%r is not a number of minutes'%argv[0])
        rows = []
        for vm in self.db.get_running_vms():
            instance_id = vm['instance_id']
            if self.history.is_silent(instance_id, minutes=minutes):
                seen = self.history.last_seen(instance_id)
                rows.append((instance_id, vm.get('node_hostname') or '-',
                             seen if seen is not None else 'never'))
        if not rows:
            self.write('every vm reported within the last %d minutes'%minutes)
            return 0
        self.table(('INSTANCE', 'NODE', 'LAST READING'), sorted(rows))
        return 1

    def forget(self, argv):
        '''drop the readings kept for a vm'''
        if not argv:
            return self.complain('forget needs the instance id of a vm')
        instance_id = argv[0]
        discarded = self.history.forget(instance_id)
        self.write('%s readings discarded for %s'%(discarded, instance_id))
        return 0

    def complain(self, message):
        self.write('pcmonsctl: %s'%message)
        return 2

    def usage(self):
        self.write(__doc__.strip())
        return 2


COMMANDS = {
    'vms': 'vms',
    'show': 'show',
    'history': 'history_of',
    'silent': 'silent',
    'forget': 'forget',
}


def main(argv, console=None, out=None):
    '''
    the exit status: 0 when the answer is yes or the listing is empty, 1 when
    the question has no answer or something is wrong with a vm, 2 when the
    command itself was wrong. A cron entry can act on the difference
    '''
    console = console or Console(out=out)
    if len(argv) < 2:
        return console.usage()
    command = COMMANDS.get(argv[1])
    if command is None:
        console.complain('%r is not a command'%argv[1])
        return console.usage()
    return getattr(console, command)(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
