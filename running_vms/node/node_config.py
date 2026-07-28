import os

#The patch must be writable
PATH_TO_LOG_FILE = os.environ.get('PCMONS_NODE_LOG_FILE', '/var/log/Monitoring_Cloud_Client.log')

#Current ip of the interface listening to requests. Use 0.0.0.0 to listen on
#every interface, or export PCMONS_NODE_LISTEN_IP / PCMONS_NODE_LISTEN_PORT to
#override without editing this file on every node.
LISTEN_IP = os.environ.get('PCMONS_NODE_LISTEN_IP', 'stratus.lrg.ufsc.br')

#Port where this client will listen to requests
LISTEN_PORT = int(os.environ.get('PCMONS_NODE_LISTEN_PORT', 60000))
