'''
Exercises the pcmons probes against the fixtures baked into the image.

Every module is imported (which catches syntax and indentation errors) and every
probe is run against a known input, so the parsing is checked against a value we
can predict rather than just "it did not crash".

Run: docker compose run --rm pcmons
'''
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'booting_vms'))

results = []


def check(name, got, expected):
    ok = got == expected
    results.append((ok, name, 'got %r expected %r'%(got, expected)))


def report(name, got):
    results.append((True, name, 'reported %r'%(got,)))


def run(name, fn):
    try:
        fn()
    except Exception:
        results.append((False, name, traceback.format_exc().strip().splitlines()[-1]))


def probe_memory():
    from MemoryMonitor import MemoryMonitor
    m = MemoryMonitor().get_meminfo()
    check('memory: used == total - free', m['used'], m['total'] - m['free'])
    results.append((m['total'] > 0, 'memory: total is positive', 'total=%s'%m['total']))
    #a second reading must not accumulate the cache counter
    second = MemoryMonitor().get_meminfo()
    results.append((second['cache'] < m['total'], 'memory: cache stays bounded',
                    'cache=%s total=%s'%(second['cache'], m['total'])))


def probe_loadavg():
    from SystemLoadMonitor import SystemLoadMonitor
    l = SystemLoadMonitor().get_loadavg()
    check('loadavg: three windows', sorted(l.keys()), ['1', '10', '5'])
    report('loadavg: value', l['1'])


def probe_http():
    from HTTPConMonitor import HTTPConMonitor
    h = HTTPConMonitor().get_http_connections()
    results.append((str(h['nconexoes']).isdigit(), 'http: connection count is numeric',
                    'nconexoes=%r'%h['nconexoes']))


def probe_ssh():
    from SSHAccessMonitor import SSHAccessMonitor
    s = SSHAccessMonitor().get_ssh_access_attempts()
    #fixture holds 3 "Failed password" and 2 "Accepted password" lines, plus
    #cron/sudo noise that must not be counted as a valid login
    check('ssh: failed attempts', s['invalid'], '3')
    check('ssh: valid logins', s['valid'], '2')


def probe_availability():
    from AvailabilityMonitor import AvailabilityMonitor
    a = AvailabilityMonitor().get_availability_info()
    results.append(('up' in a['uptime'], 'availability: uptime parsed', repr(a['uptime'])))


def probe_backup():
    from BackupMonitor import BackupMonitor
    b = BackupMonitor().get_backup_info()
    check('backup: last run from final log line', b['last_performed'], '2026/08/06 02:01:19')


def probe_encryption():
    from EncryptionMonitor import EncryptionMonitor
    e = EncryptionMonitor().get_encryption_info()
    check('encryption: detected', e['is_encrypted'], 'yes')
    #the cipher is the options column, not the fourth character of the line
    check('encryption: cipher from options column', e['cipher'], 'aes-xts-plain64,luks')


def probe_integrity():
    from IntegrityMonitor import IntegrityMonitor
    i = IntegrityMonitor().get_integrity_info()
    check('integrity: tripwire report date', i['last_performed'].strip(), 'Thu Aug  6 03:00:12 2026')


def probe_malware():
    from MalwareMonitor import MalwareMonitor
    m = MalwareMonitor().get_malware_info()
    check('malware: infected count', str(m['detected']).strip(), '2')
    report('malware: last scan', m['last_scan'])


def probe_password():
    from PasswordMonitor import PasswordMonitor
    p = PasswordMonitor().get_password_security()
    check('password: PASS_MAX_DAYS', p['max_age'], 90)


def probe_vulnerability():
    from VulnerabilityMonitor import VulnerabilityMonitor
    v = VulnerabilityMonitor().get_vulnerability_info()
    #must read the NEWEST tiger report (2 WARN, 1 FAIL), not the older one
    check('vulnerability: WARN count from newest report', v['warn'], 2)
    check('vulnerability: FAIL count from newest report', v['fail'], 1)


def node_plugin_listing():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, 'running_vms', 'node'))
    import VM_Monitoring_Node_Plugin as npl
    plugin = npl.VM_Monitoring_Node_Plugin()
    vms = plugin.list_running_vms(lambda d: d.replace('one', 'i'))
    report('node: domains parsed from virsh', [v['instance_id'] for v in vms])
    check('node: both running domains found', len(vms), 2)


def imports_only():
    #modules that need a database or a cloud endpoint: import only.
    #running_vms/node has no __init__.py -- its files are copied to the node
    #hosts standalone -- so it is imported from the path added above.
    import running_vms.cluster.cluster_config
    import node_config
    import settings
    report('config modules import', 'ok')


CHECKS = [
    ('memory', probe_memory),
    ('loadavg', probe_loadavg),
    ('http', probe_http),
    ('ssh', probe_ssh),
    ('availability', probe_availability),
    ('backup', probe_backup),
    ('encryption', probe_encryption),
    ('integrity', probe_integrity),
    ('malware', probe_malware),
    ('password', probe_password),
    ('vulnerability', probe_vulnerability),
    ('node plugin', node_plugin_listing),
    ('config imports', imports_only),
]

if __name__ == '__main__':
    for name, fn in CHECKS:
        run(name, fn)

    print('')
    failed = 0
    for ok, name, detail in results:
        print('%s  %-46s %s'%('PASS' if ok else 'FAIL', name, detail))
        if not ok:
            failed += 1
    print('')
    print('%d checks, %d failed'%(len(results), failed))
    sys.exit(1 if failed else 0)
