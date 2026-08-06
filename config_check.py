'''
Checks the configuration before anything depends on it.

The three config modules are plain Python, which means a mistake in one is not
found until something uses it: a port left in quotes fails inside MySQL, an
interface name spelt wrong reports into nothing, and a log path that is not
writable is discovered by a server that has already stopped logging. All of
those are a traceback in production and none of them are a traceback at
startup.

Run it before starting anything:

    python /opt/pcmons/config_check.py

Nothing here connects to anything. It reads the settings, checks what can be
checked from the machine it runs on, and says what it found. Problems are
either errors, which mean something will not work, or warnings, which mean
something is probably not what was meant.
'''
import os, sys
sys.path.append('/opt/pcmons/')

ERROR, WARNING = 'error', 'warning'

#interfaces the notification server can build. Kept as names so that this
#runs on a node or inside a vm, where the interface packages are not installed
KNOWN_INTERFACES = ('nagios', 'email', 'mail')

KNOWN_INFRA = ('eucalyptus', 'opennebula')


class Problem:

    def __init__(self, severity, setting, message):
        self.severity = severity
        self.setting = setting
        self.message = message

    def __str__(self):
        return "%-8s %-32s %s"%(self.severity.upper(), self.setting, self.message)

    def __eq__(self, other):
        return (self.severity, self.setting, self.message) == (
            other.severity, other.setting, other.message)

    def __repr__(self):
        return "Problem(%r, %r, %r)"%(self.severity, self.setting, self.message)


def errors(problems):
    return [problem for problem in problems if problem.severity == ERROR]


def warnings(problems):
    return [problem for problem in problems if problem.severity == WARNING]


#checks small enough to be worth sharing

def missing(config, setting):
    '''
    a problem if the setting is not there at all. A config file older than the
    code is the usual reason, and every other check on that setting would
    otherwise report something misleading
    '''
    if not hasattr(config, setting):
        return Problem(ERROR, setting, 'is not set in this config file')
    return None


def whole_number(config, setting, least=None, most=None):
    value = getattr(config, setting)
    #a bool is an int in python, and a port of True is not a port
    if isinstance(value, bool) or not isinstance(value, int):
        return Problem(ERROR, setting,
                       'must be a number, not %r -- quoting it is what breaks '
                       'the mysql connection'%(value,))
    if least is not None and value < least:
        return Problem(ERROR, setting, 'must be at least %s, not %s'%(least, value))
    if most is not None and value > most:
        return Problem(ERROR, setting, 'must be at most %s, not %s'%(most, value))
    return None


def not_empty(config, setting):
    value = getattr(config, setting)
    if not isinstance(value, basestring) or not value.strip():
        return Problem(ERROR, setting, 'is empty, and something needs it')
    return None


def writable_directory(config, setting):
    '''
    the file need not exist, but the directory it goes in must, and must take
    a write. A log nobody can write is found when the log is read for the
    first time, which is after the thing worth reading about
    '''
    path = getattr(config, setting)
    if not isinstance(path, basestring) or not path.strip():
        return Problem(ERROR, setting, 'is empty, and a path is needed')
    directory = os.path.dirname(path) or '.'
    if not os.path.isdir(directory):
        return Problem(ERROR, setting, '%s is not a directory'%directory)
    if not os.access(directory, os.W_OK):
        return Problem(ERROR, setting, '%s cannot be written to'%directory)
    return None


def existing_path(config, setting, severity=WARNING):
    path = getattr(config, setting)
    if not isinstance(path, basestring) or not path.strip():
        return Problem(severity, setting, 'is empty')
    if not os.path.exists(path):
        return Problem(severity, setting, '%s does not exist on this machine'%path)
    return None


def collect(config, checks):
    '''
    run each check, skipping the ones whose setting is not in the config at
    all -- that is reported once rather than by every check that reads it
    '''
    problems = []
    for setting, check in checks:
        absent = missing(config, setting)
        if absent is not None:
            problems.append(absent)
            continue
        found = check(config, setting)
        if found is not None:
            problems.append(found)
    return problems


def check_agent(config):
    '''
    booting_vms/settings.py, which is what the agent inside a vm reads
    '''
    problems = collect(config, [
        ('SERVER', not_empty),
        ('SERVER_PORT', not_empty),
    ])
    if not errors(problems):
        #xmlrpclib builds the url by joining these two, and refuses one
        #without a scheme with an error naming neither setting
        if not config.SERVER.startswith(('http://', 'https://')):
            problems.append(Problem(ERROR, 'SERVER',
                                    'must start with http:// or https://, or the '
                                    'agent cannot build the address it reports to'))
        if not str(config.SERVER_PORT).strip().isdigit():
            problems.append(Problem(ERROR, 'SERVER_PORT',
                                    'must be a number, not %r'%(config.SERVER_PORT,)))
    return problems


def check_node(config):
    '''
    running_vms/node/node_config.py, read by the plugin on each node host
    '''
    return collect(config, [
        ('PATH_TO_LOG_FILE', writable_directory),
        ('LISTEN_IP', not_empty),
        ('LISTEN_PORT', lambda c, s: whole_number(c, s, least=1, most=65535)),
    ])


def check_cluster(config):
    '''
    running_vms/cluster/cluster_config.py, which almost everything reads
    '''
    problems = collect(config, [
        ('PATH_TO_LOG_FILE', writable_directory),
        ('LISTEN_IP', not_empty),
        ('LISTEN_PORT', lambda c, s: whole_number(c, s, least=1, most=65535)),
        ('VM_TABLE', not_empty),
        ('READING_TABLE', not_empty),
        ('HISTORY_RETENTION_DAYS', lambda c, s: whole_number(c, s, least=0)),
    ])
    problems.extend(check_database(config))
    problems.extend(check_infra(config))
    problems.extend(check_interfaces(config))
    return problems


def check_database(config):
    absent = missing(config, 'DATABASES')
    if absent is not None:
        return [absent]
    settings = config.DATABASES.get('default')
    if not settings:
        return [Problem(ERROR, 'DATABASES', "has no 'default' entry")]

    problems = []
    for key in ('NAME', 'USER', 'HOST'):
        value = settings.get(key)
        if not value:
            problems.append(Problem(ERROR, 'DATABASES.%s'%key,
                                    'is empty, and the connection needs it'))
    if not settings.get('PASSWORD'):
        #a database reachable without one is a decision somebody may have
        #made, so this is not an error
        problems.append(Problem(WARNING, 'DATABASES.PASSWORD', 'is empty'))
    port = settings.get('PORT')
    if isinstance(port, bool) or not isinstance(port, int):
        #the config file has carried a comment about this since 2010
        problems.append(Problem(ERROR, 'DATABASES.PORT',
                                'must be a number, not %r -- mysql refuses a '
                                'quoted port with an unrelated error'%(port,)))
    return problems


def check_infra(config):
    absent = missing(config, 'INFRA')
    if absent is not None:
        return [absent]
    if config.INFRA not in KNOWN_INFRA:
        return [Problem(ERROR, 'INFRA', '%r is not one of %s'%(
            config.INFRA, ', '.join(KNOWN_INFRA)))]
    if config.INFRA == 'opennebula':
        return filter(None, [existing_path(config, 'PATH_TO_OPENNEBULA_CONFIG_FILE')])
    return filter(None, [existing_path(config, 'PATH_TO_EUCALYPTUS_CONFIG_FILE')])


def configured_interfaces(config):
    '''
    the same fallback the notification server makes: INTERFACES, or the older
    INTERFACE when the list is empty
    '''
    names = list(getattr(config, 'INTERFACES', ()) or ())
    if names:
        return names
    single = getattr(config, 'INTERFACE', '')
    if single:
        return [single]
    return []


def check_interfaces(config):
    names = configured_interfaces(config)
    if not names:
        #the readings are still kept, but nothing is told about them
        return [Problem(ERROR, 'INTERFACES',
                        'is empty, so every notification is recorded and then dropped')]

    problems = []
    for name in names:
        if str(name).strip().lower() not in KNOWN_INTERFACES:
            problems.append(Problem(ERROR, 'INTERFACES',
                                    '%r is not an interface; known ones are %s'%(
                                        name, ', '.join(KNOWN_INTERFACES))))
    wanted = [str(name).strip().lower() for name in names]
    if 'nagios' in wanted:
        problems.extend(check_nagios(config))
    if 'email' in wanted or 'mail' in wanted:
        problems.extend(check_mail(config))
    return problems


def check_nagios(config):
    problems = collect(config, [
        ('VMS_NAGIOS_FILE', writable_directory),
        ('NAGIOS_TEMP_CONF', writable_directory),
        ('COMMAND_TO_RELOAD_NAGIOS', not_empty),
    ])
    if getattr(config, 'USING_NAGIOSGRAPHER', False):
        found = existing_path(config, 'PATH_SERVICEEXT_NAGIOSGRAPHER')
        if found is not None:
            problems.append(found)
    return problems


def check_mail(config):
    problems = collect(config, [
        ('MAIL_FROM', not_empty),
        ('SMTP_HOST', not_empty),
        ('SMTP_PORT', lambda c, s: whole_number(c, s, least=1, most=65535)),
        ('MAIL_REPEAT_MINUTES', lambda c, s: whole_number(c, s, least=0)),
    ])
    recipients = list(getattr(config, 'MAIL_TO', ()) or ())
    if not recipients:
        recipients = [address for name, address in getattr(config, 'ADMINS', ())]
    if not recipients:
        problems.append(Problem(ERROR, 'MAIL_TO',
                                'is empty and so is ADMINS, so the alerts have '
                                'nowhere to go'))
    for address in recipients:
        if '@' not in str(address):
            problems.append(Problem(WARNING, 'MAIL_TO',
                                    '%r does not look like an address'%(address,)))
    return problems


def check_all():
    '''
    every config module that can be imported from this machine, as
    (name, problems). A node host has no cluster config and a vm has neither,
    so one that is not there is not a problem
    '''
    found = []
    for name, path, check in (
            ('cluster', ('running_vms', 'cluster', 'cluster_config'), check_cluster),
            ('node', ('running_vms', 'node', 'node_config'), check_node),
            ('agent', ('booting_vms', 'settings'), check_agent)):
        config = load(path)
        if config is None:
            continue
        found.append((name, check(config)))
    return found


def load(path):
    '''
    a config module by path, or None if this machine does not have it
    '''
    root = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(root, *path[:-1])
    if not os.path.isdir(directory):
        return None
    sys.path.insert(0, directory)
    try:
        return __import__(path[-1])
    except ImportError:
        return None
    finally:
        sys.path.remove(directory)


if __name__ == "__main__":
    failed = 0
    for name, problems in check_all():
        print ''
        print '%s configuration'%name
        if not problems:
            print '  nothing to report'
        for problem in problems:
            print '  %s'%problem
        failed += len(errors(problems))
    print ''
    print '%d error(s)'%failed
    sys.exit(1 if failed else 0)
