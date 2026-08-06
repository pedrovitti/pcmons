'''
Discards kept readings past the retention window.

Meant for cron, nightly:
    0 4 * * * python /opt/pcmons/running_vms/cluster/Purge_History.py

Takes the window from cluster_config.HISTORY_RETENTION_DAYS, or from a
number of days given on the command line, which is how a cluster short of
disk is cleared out by hand without editing the config.
'''
import logging, sys
sys.path.append('/opt/pcmons/')
from running_vms.cluster.history import History
import running_vms.cluster.cluster_config as cluster_config


def parse_days(argv):
    '''
    the window asked for on the command line, or None to use the configured
    one. A window that is not a number is refused rather than guessed at:
    purging is not undoable
    '''
    if len(argv) < 2:
        return None
    try:
        days = int(argv[1])
    except ValueError:
        raise ValueError('retention window must be a number of days, got %r'%argv[1])
    if days < 0:
        raise ValueError('retention window cannot be negative: %s'%days)
    return days


def purge(days=None, history=None):
    history = history or History()
    discarded = history.purge(days)
    logging.debug('%s readings discarded'%discarded)
    return discarded


if __name__ == "__main__":
    try:
        days = parse_days(sys.argv)
    except ValueError:
        e = sys.exc_info()[1]
        print 'Purge_History error :', e
        sys.exit(2)
    print '%s readings discarded'%purge(days)
