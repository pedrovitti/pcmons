'''
Exercises Db_Connector against a real MySQL server.

Covers the round trip the cluster controller actually performs (insert, read,
update, mark terminated) and specifically checks that values containing quotes
survive, which is what the move to bound parameters was for.

Run: docker compose -f docker/docker-compose.yml run --rm dbtest
'''
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
