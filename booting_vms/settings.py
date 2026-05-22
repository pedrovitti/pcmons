import os

#Address of the notification server the agent reports to. Override without
#editing this file by exporting PCMONS_SERVER / PCMONS_SERVER_PORT, which is
#what the VM image bundle relies on.
SERVER = os.environ.get('PCMONS_SERVER', 'http://150.162.63.32')
SERVER_PORT = os.environ.get('PCMONS_SERVER_PORT', '60001')
