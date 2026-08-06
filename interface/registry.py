'''
The interfaces a notification can be handed to.

An interface takes the readings a vm reported and does something with them:
files them as Nagios check results, mails somebody, writes them somewhere.
This is the one place that knows which names exist and what each one builds,
so adding an interface is a name here rather than an edit to the server that
receives the notifications.

An interface has one method:

    process_notification(data, address) -> whether it took the readings

It is handed the notification whole, including metrics it has no use for.
'''
import logging, sys

#the interfaces built by name. Kept as names rather than classes because
#building one opens a database connection, and a cluster configured for
#Nagios alone should not be paying for the rest
KNOWN = ('nagios',)


def names():
    return KNOWN


def build(name):
    '''
    an interface by name, or None if there is no interface by that name. The
    name is matched regardless of case: it is typed into a config file by
    hand, and 'Nagios' means what it looks like it means
    '''
    name = str(name).strip().lower()
    if name == 'nagios':
        #imported here rather than at the top: an interface pulls in the
        #database layer and whatever client it talks to, and a cluster that
        #does not use it should not have to have those installed
        from interface.nagios import NagiosPassiveServer as nagios
        return nagios.NagiosPassiveServer()
    logging.error('no interface called %s; known interfaces are %s'%(name, ', '.join(KNOWN)))
    return None


def build_all(configured):
    '''
    (name, interface) for each name that could be built, in the order they
    were configured. A name that is not an interface is left out rather than
    stopping the rest: one typo in a config file must not cost every
    notification the cluster receives
    '''
    built = []
    for name in configured:
        try:
            interface = build(name)
        except:
            #an interface whose client library is missing, or whose server is
            #down, must not take the others with it
            error = sys.exc_info()[1]
            logging.error('interface %s could not be built: %s'%(name, error))
            continue
        if interface is not None:
            built.append((name, interface))
    return built
