'''
Exercises Db_Connector against a real MySQL server.

Covers the round trip the cluster controller actually performs (insert, read,
update, mark terminated) and specifically checks that values containing quotes
survive, which is what the move to bound parameters was for.

Run: docker compose -f docker/docker-compose.yml run --rm dbtest
'''
import datetime
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
#Mysql_Db_Connector does a plain "import cluster_config", so the module it
#binds is the one found on this path -- not running_vms.cluster.cluster_config.
#Patch that one, or the edits below land on a different module object.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'running_vms', 'cluster'))

import cluster_config

#point the shipped config at the compose service instead of editing the repo
cluster_config.DATABASES['default'].update({
    'HOST': os.environ.get('PCMONS_DB_HOST', 'db'),
    'NAME': os.environ.get('PCMONS_DB_NAME', 'manager'),
    'USER': os.environ.get('PCMONS_DB_USER', 'manager'),
    'PASSWORD': os.environ.get('PCMONS_DB_PASSWORD', 'cloudmanager'),
    'PORT': int(os.environ.get('PCMONS_DB_PORT', 3306)),
})
cluster_config.PATH_TO_LOG_FILE = '/tmp/pcmons-dbtest.log'

from Mysql_Db_Connector import Db_Connector

results = []


def check(name, got, expected):
    results.append((got == expected, name, 'got %r expected %r'%(got, expected)))


def sample(instance_id, user="oneadmin"):
    return {
        'reservation': 'r-001', 'user': user, 'instance_id': instance_id,
        'dns_name': 'vm.example.org', 'private_dns_name': '10.0.0.10',
        'public_dns_name': '150.162.63.90', 'state': 'running',
        'instance_type': 'm1.small', 'launch_time': '2026-08-06T00:00:00',
        'availability_zone': 'cluster1', 'kernel': 'eki-1', 'ramdisk': 'eri-1',
    }


def main():
    db = Db_Connector()
    db.cur.execute("DELETE FROM vmmonitor_vm")
    db.db.commit()

    #insert then read back
    db.insert_new_vm(sample('i-100'))
    row = db.get_vm_info('i-100')
    check('insert then read back', row['instance_id'], 'i-100')
    check('state stored', row['state'], 'running')

    #a quote in a value must round trip rather than break the statement.
    #this is exactly what string interpolated SQL could not survive.
    nasty = "o'brien"
    db.insert_new_vm(sample('i-101', user=nasty))
    check('quote in a value survives', db.get_vm_info('i-101')['user'], nasty)

    #and a value that would have been an injection with the old code
    inject = "x'; DROP TABLE vmmonitor_vm; --"
    db.insert_new_vm(sample('i-102', user=inject))
    check('injection attempt stored as data', db.get_vm_info('i-102')['user'], inject)
    db.cur.execute("SELECT COUNT(*) AS n FROM vmmonitor_vm")
    check('table still exists after injection attempt', db.cur.fetchone()['n'], 3)

    #update
    updated = sample('i-100')
    updated['state'] = 'shutting-down'
    db.update_stored_vm_info(updated)
    check('update applied', db.get_vm_info('i-100')['state'], 'shutting-down')

    #node placement
    db.update_vm_Ip_hostname('10.0.0.2', 'node01', 'i-101')
    row = db.get_vm_info('i-101')
    check('node ip recorded', row['node_ip'], '10.0.0.2')
    check('node hostname recorded', row['node_hostname'], 'node01')

    #vms without an ip: i-100 and i-102 were never given one.
    #this is the query that used "node_ip=NULL" and always came back empty.
    ids = sorted(r['instance_id'] for r in db.get_stored_vms_ids_without_IP())
    check('vms missing an ip are found', ids, ['i-100', 'i-102'])

    #terminate
    db.set_status_terminated('i-102')
    check('terminated flag set', db.get_vm_info('i-102')['state'], 'terminated')
    running = sorted(r['instance_id'] for r in db.get_running_vms())
    check('terminated vm excluded from running', running, ['i-100', 'i-101'])

    #writes must survive a fresh connection
    other = Db_Connector()
    check('writes persisted for a new connection',
          other.get_vm_info('i-101')['node_hostname'], 'node01')

    #i-100 was left shutting-down above, and the sample vms all report from one
    #address; give it a state and an address of its own for the queries below
    restored = sample('i-100')
    restored['public_dns_name'] = '150.162.63.91'
    db.update_stored_vm_info(restored)

    #the monitoring queries the Nagios interface and the config generator use
    monitoring = db.get_info_for_monitoring_running_Vms()
    check('running vms listed for monitoring',
          sorted(row['instance_id'] for row in monitoring), ['i-100', 'i-101'])
    check('monitoring rows carry the columns nagios needs',
          sorted(monitoring[0].keys()),
          ['instance_id', 'node_hostname', 'node_ip', 'public_dns_name', 'user'])

    old = db.get_info_for_monitoring_old_Vms()
    check('terminated vms listed separately',
          [row['instance_id'] for row in old], ['i-102'])

    #get_id_by_ip is the first thing every notification does: the agent reports
    #from an address, and this turns it into the vm it belongs to
    check('vm found by the address it reports from',
          db.get_id_by_ip('150.162.63.91')['instance_id'], 'i-100')

    #a terminated vm must not answer, or a recycled address would file another
    #vm's readings against it
    db.cur.execute("UPDATE vmmonitor_vm SET public_dns_name='150.162.63.99' WHERE instance_id='i-102'")
    db.db.commit()
    check('terminated vm not matched by address', db.get_id_by_ip('150.162.63.99'), None)

    #and an address belonging to no vm at all
    check('unknown address answers with nothing', db.get_id_by_ip('10.9.9.9'), None)

    #update_vm_info writes a whole record at once; this is the path vms.VM.save
    #takes, and the only writer that sets node placement and last_check together
    record = {
        'instance_id':'i-100', 'node_ip':'10.0.0.3', 'node_hostname':'node02',
        'last_check':'2026-08-06 10:00:00', 'state':'running',
    }
    db.update_vm_info(record)
    stored = db.get_vm_info('i-100')
    check('whole record update applied', stored['node_hostname'], 'node02')
    check('whole record update sets every column given', stored['last_check'], '2026-08-06 10:00:00')
    check('whole record update leaves other columns alone', stored['user'], 'oneadmin')

    #connect() is called again by nothing today, but a long running controller
    #that reconnects must come back with a working cursor
    db.connect()
    check('reconnecting gives a usable cursor', db.get_vm_info('i-100')['node_hostname'], 'node02')

    readings(db)


def readings(db):
    '''
    the history half: what a notification leaves behind, and the queries drawn
    from it. The in memory fakes cannot catch a wrong GROUP BY or a datetime
    that does not survive the column, so those are checked here
    '''
    from history import History

    db.cur.execute("DELETE FROM vmmonitor_reading")
    db.db.commit()
    history = History(db)

    #two rounds from one vm, five minutes apart, as the agent would send them
    first = datetime.datetime(2026, 8, 6, 12, 0, 0)
    second = first + datetime.timedelta(minutes=5)
    history.record('i-100', {'memory':{'used':512, 'total':1024},
                             'loadavg':{'1':0.5, '5':0.4, '10':0.3}}, when=first)
    kept = history.record('i-100', {'memory':{'used':768, 'total':1024},
                                    'loadavg':{'1':2.5, '5':0.4, '10':0.3}}, when=second)
    check('a notification is stored one row per field', kept, 5)

    db.cur.execute("SELECT COUNT(*) AS n FROM vmmonitor_reading")
    check('both rounds are on disk', db.cur.fetchone()['n'], 10)

    #the greatest-per-group query: every field at its newest value
    latest = history.latest('i-100')
    check('the last value of every field comes back',
          latest['memory'], {'used':'768', 'total':'1024'})
    check('every metric is grouped under its name',
          sorted(latest.keys()), ['loadavg', 'memory'])

    #a datetime has to survive the column, or every window query is wrong
    check('the time of a reading round trips', history.last_seen('i-100'), second)

    #the series a graph is drawn from, oldest first
    check('a series comes back in order',
          [value for when, value in history.series('i-100', 'memory', 'used')],
          ['512', '768'])
    check('a float survives the trip',
          history.numeric_series('i-100', 'loadavg', '1')[1][1], 2.5)
    check('a spike between readings is kept',
          history.peak('i-100', 'loadavg', '1'), 2.5)

    #the window clause, which the fakes only approximate
    check('a window leaves out what came before it',
          [value for when, value in
           history.series('i-100', 'memory', 'used', since=second)],
          ['768'])
    check('a limit counts back from the newest reading',
          [value for when, value in
           history.series('i-100', 'memory', 'used', limit=1)],
          ['768'])

    #one vm must not see another's readings
    history.record('i-101', {'memory':{'used':1, 'total':2}}, when=second)
    check('one vm does not see another', history.latest('i-101')['memory']['used'], '1')
    check('vms with readings are listed',
          sorted(history.instance_ids()), ['i-100', 'i-101'])

    #a value wider than the column is cut rather than refused by the server
    history.record('i-101', {'availability':{'uptime':'x'*400}}, when=second)
    check('an over wide value is stored cut',
          len(history.latest('i-101')['availability']['uptime']), 255)

    #retention
    history.record('i-100', {'memory':{'used':1, 'total':2}},
                   when=second - datetime.timedelta(days=40))
    discarded = history.purge(days=30, now=second)
    check('readings past the window are discarded', discarded, 2)
    check('readings inside the window are kept',
          [value for when, value in history.series('i-100', 'memory', 'used')],
          ['512', '768'])

    history.forget('i-100')
    check('forgetting a vm drops its readings', history.latest('i-100'), {})
    check('forgetting one vm leaves the others alone',
          history.latest('i-101')['memory']['used'], '1')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        results.append((False, 'db round trip', traceback.format_exc().strip().splitlines()[-1]))

    print('')
    failed = 0
    for ok, name, detail in results:
        print('%s  %-44s %s'%('PASS' if ok else 'FAIL', name, detail))
        if not ok:
            failed += 1
    print('')
    print('%d checks, %d failed'%(len(results), failed))
    sys.exit(1 if failed else 0)
