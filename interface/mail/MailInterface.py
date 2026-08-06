'''
Mails the administrators when a vm reports something wrong.

The second interface, and the reason the readings are judged in one place
rather than inside the Nagios one: what counts as a problem is a property
of the reading, and both interfaces have to agree on it or an operator
gets mail about a vm whose dashboard is green.

Nagios answers "what is the state of everything"; this answers "something
changed and you were not looking". So it sends nothing while a vm is
healthy, sends when a metric turns bad, sends again when it recovers, and
otherwise stays quiet: an alert that arrives every five minutes for a week
is one nobody reads.

The package is called mail rather than email because a package named email
inside this one would shadow the standard library module of that name for
everything importing it.
'''
import datetime, logging, smtplib, sys
sys.path.append('/opt/pcmons/')
from running_vms.cluster.Mysql_Db_Connector import Db_Connector
import running_vms.cluster.cluster_config as cluster_config
from interface.nagios import services
from interface import readings


class SmtpMailer:
    '''
    sends through the configured smtp server. Kept apart from the interface
    so that what is sent can be tested without one
    '''

    def send(self, sender, recipients, message):
        server = smtplib.SMTP(cluster_config.SMTP_HOST, cluster_config.SMTP_PORT)
        try:
            server.sendmail(sender, recipients, message)
        finally:
            server.quit()


class MailInterface:

    def __init__(self, db=None, mailer=None):
        self.db = db or Db_Connector()
        self.mailer = mailer or SmtpMailer()
        #what each metric of each vm was last reported as, so that a state
        #that has not changed is not reported twice
        self.reported = {}

    def process_notification(self, data, address, now=None):
        now = now or datetime.datetime.now()
        vm = self.db.get_vm_by_ip(address)
        if vm is None:
            logging.error('no running vm at %s; nothing to mail about'%address)
            return False

        changes = self.changes(vm['instance_id'], self.judge(data), now)
        if changes:
            self.send(vm, changes, now)
        return True

    def judge(self, data):
        '''
        (metric, service, status, output) for every reading in a notification
        that can be read. The judgement is the shared one, so a vm that is
        critical here is critical on the dashboard too
        '''
        judged = []
        for metric, service in services.PASSIVE_SERVICES:
            if metric not in data:
                continue
            result = readings.format_metric(metric, data[metric])
            if result is None:
                continue
            status, output = result
            judged.append((metric, service, status, output))
        return judged

    def changes(self, instance_id, judged, now):
        '''
        the readings worth mailing about: those that turned bad, those that
        recovered, and those still bad but not reported for long enough that
        a reminder is wanted. Everything else is left alone
        '''
        changes = []
        for metric, service, status, output in judged:
            key = (instance_id, metric)
            last = self.reported.get(key)
            if status >= readings.WARNING:
                if last is None or last[0] != status or self.due(last[1], now):
                    changes.append((service, status, output))
                    self.reported[key] = (status, now)
            else:
                if last is not None and last[0] >= readings.WARNING:
                    #the recovery is worth as much as the alert: without it an
                    #operator has to go and look to find out it is over
                    changes.append((service, status, output))
                self.reported[key] = (status, now)
        return changes

    def due(self, reported_at, now):
        '''
        whether a state that has not changed is worth repeating. A vm that
        stays critical for a week should not send an alert every five minutes
        '''
        repeat = getattr(cluster_config, 'MAIL_REPEAT_MINUTES', 0)
        if not repeat:
            return False
        return (now - reported_at) >= datetime.timedelta(minutes=repeat)

    def recipients(self):
        '''
        who hears about it. ADMINS is the list the rest of the cluster
        already keeps
        '''
        configured = getattr(cluster_config, 'MAIL_TO', None)
        if configured:
            return list(configured)
        return [address for name, address in cluster_config.ADMINS]

    def subject(self, vm, changes):
        worst = max(status for service, status, output in changes)
        return "[pcmons] %s %s on %s: %s"%(
            readings.state(worst), vm['instance_id'], vm['node_hostname'],
            self.summarise(changes))

    def summarise(self, changes):
        names = [service for service, status, output in changes]
        if len(names) == 1:
            return names[0]
        return "%s and %d more"%(names[0], len(names) - 1)

    def body(self, vm, changes, now):
        lines = []
        for service, status, output in changes:
            lines.append("%-9s %-18s %s"%(readings.state(status), service, output))
        lines.append("")
        lines.append("vm %s (%s) on %s, %s"%(
            vm['instance_id'], vm['user'], vm['node_hostname'],
            now.strftime("%d-%m-%Y %H:%M:%S")))
        return "\n".join(lines)

    def message(self, sender, recipients, vm, changes, now):
        '''
        the mail as it goes on the wire. Built by hand rather than with the
        standard library's mime machinery: this is plain text with no
        attachments, and the headers below are the whole of what it needs
        '''
        headers = [
            "From: %s"%sender,
            "To: %s"%", ".join(recipients),
            "Subject: %s"%self.subject(vm, changes),
        ]
        return "%s\n\n%s\n"%("\n".join(headers), self.body(vm, changes, now))

    def send(self, vm, changes, now):
        sender = getattr(cluster_config, 'MAIL_FROM', 'pcmons')
        recipients = self.recipients()
        if not recipients:
            logging.error('nobody is configured to receive alerts')
            return False
        try:
            self.mailer.send(sender, recipients,
                             self.message(sender, recipients, vm, changes, now))
        except:
            #a mail server that is down must not fail the notification: the
            #readings are already kept and already on the dashboard
            error = sys.exc_info()[1]
            logging.error('could not mail about %s: %s'%(vm['instance_id'], error))
            return False
        return True
