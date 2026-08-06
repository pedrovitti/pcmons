'''
The Nagios services the agents report into.

Both ends of the interface read this list. Generate_VMs_Nagios_Conf defines a
passive service per entry so Nagios knows about it, and NagiosPassiveServer
registers a check result under the same name. A name that exists on only one
side is either a check for a service Nagios does not have, which it discards,
or a service that is never updated and sits stale on the dashboard forever.

Each entry maps the key the agent sends to the service name Nagios shows.
'''

#metric key in the notification -> nagios service name
PASSIVE_SERVICES = (
    ('memory', 'RAM'),
    ('loadavg', 'Cpu_Load'),
    ('http', 'HTTP_Connections'),
    ('sshattempts', 'SSH_Attempts'),
    ('availability', 'Availability'),
    ('backup', 'Backup'),
    ('encryption', 'Encryption'),
    ('integrity', 'Integrity'),
    ('malware', 'Malware'),
    ('password', 'Password_Policy'),
    ('vulnerability', 'Vulnerabilities'),
)


def service_names():
    return [service for metric, service in PASSIVE_SERVICES]
