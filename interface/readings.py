'''
Turns a reading into a status and a line of text.

This is the judgement every interface needs and none of them should be making
separately: whether an unencrypted disk is worth waking somebody for is a
property of the reading, not of Nagios or of mail. An interface decides what
to do with a status; it does not decide what the status is.

The status codes are Nagios', because that is where they came from and there
is nothing to gain from a second set.
'''
import logging

#nagios return codes
OK, WARNING, CRITICAL = 0, 1, 2

STATES = {OK:'OK', WARNING:'WARNING', CRITICAL:'CRITICAL'}


def state(status):
    '''the name of a status, for anything writing it out for a person'''
    return STATES.get(status, 'UNKNOWN')


def format_metric(metric, reading):
    '''
    (status, output) for a reading, or None if it cannot be read. A probe
    that reports something unexpected costs its own check, not the rest.
    '''
    formatter = globals().get('format_%s'%metric)
    if formatter is None:
        #the agent ships probes the cluster was not told about
        logging.error('no reading of %s is understood here'%metric)
        return None
    try:
        return formatter(reading)
    except (KeyError, TypeError, ValueError, ZeroDivisionError), error:
        logging.error('cannot read %s: %s (%s)'%(metric, error, reading))
        return None


def sanitise(text):
    #a quote would end the shell argument and a pipe starts nagios
    #performance data; neither belongs in a value read off a vm
    return str(text).replace('"', '').replace('|', '/').strip()


def format_memory(memory):
    total = memory['total']
    if total <= 0:
        raise ValueError('reading has no total')
    percentage = int(100*memory['used']/float(total))
    #kept as it is: nagiosgrapher parses this and holds history against it
    return OK, "%s;%s/%s"%(percentage, memory['used']/1024, total/1024)


def format_loadavg(loadavg):
    if loadavg['1'] >= 3.0:
        status = CRITICAL
    elif loadavg['1'] >= 1.5:
        status = WARNING
    else:
        status = OK
    return status, "%s - load average: %.2f, %.2f, %.2f"%(
        state(status), loadavg['1'], loadavg['5'], loadavg['10'])


def format_http(http):
    return OK, "%s"%http['connections']


def format_sshattempts(attempts):
    #counts only: what makes a failed login count alarming is a policy
    #decision, and belongs in the nagios service definition
    return OK, "OK - ssh logins: %s accepted, %s failed"%(
        sanitise(attempts['valid']), sanitise(attempts['invalid']))


def format_availability(availability):
    return OK, "OK - up %s"%sanitise(availability['uptime'])


def format_backup(backup):
    last = sanitise(backup['last_performed'])
    if not last:
        return WARNING, "WARNING - no backup recorded"
    return OK, "OK - last backup %s"%last


def format_encryption(encryption):
    if encryption['is_encrypted'] != 'yes':
        return WARNING, "WARNING - disk is not encrypted"
    return OK, "OK - encrypted with %s"%sanitise(encryption['cipher'])


def format_integrity(integrity):
    last = sanitise(integrity['last_performed'])
    if last in ('', '-'):
        return WARNING, "WARNING - no integrity scan recorded"
    return OK, "OK - last scan %s"%last


def format_malware(malware):
    detected = int(malware['detected'])
    if detected > 0:
        return CRITICAL, "CRITICAL - %d infected file(s)"%detected
    return OK, "OK - no infected files, last scan %s"%sanitise(malware['last_scan'])


def format_password(password):
    max_age = int(password['max_age'])
    if max_age <= 0:
        return WARNING, "WARNING - passwords never expire"
    return OK, "OK - passwords expire after %d days"%max_age


def format_vulnerability(vulnerability):
    warn = int(vulnerability['warn'])
    fail = int(vulnerability['fail'])
    if fail > 0:
        return CRITICAL, "CRITICAL - %d failed, %d warned"%(fail, warn)
    if warn > 0:
        return WARNING, "WARNING - %d warned"%warn
    return OK, "OK - no findings"
