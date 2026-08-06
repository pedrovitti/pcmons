pcmons
=========

Considering the lack of generic and open-source solutions for management and monitoring 
of private clouds, pcmons (Private Cloud MONitoring System) was developed. It is intended 
to be an extensible and modular monitoring system for private clouds. pcmons acts 
principally retrieving, gathering and preparing relevant information for monitoring data 
visualization, with a special focus on virtual machines.

Authors:

* Shirlei Chaves (shirlei@inf.ufsc.br)
* Rafael Uriarte (rafael.uriarte@inf.ufsc.br)
* Pedro Vitti (pedrovitti@gmail.com)

Site: https://github.com/pedrovitti/pcmons


Repository layout
--------

    booting_vms/      agent that ships inside the monitored VM (Monitor.py polls the
                      probe classes and pushes the readings over XML-RPC)
    running_vms/
      cluster/        cluster controller: queries the IaaS platform through the EC2
                      API, keeps the vmmonitor_vm table in sync, talks to the nodes
      node/           XML-RPC plugin that runs on each node host and reports the
                      VMs currently running there
      Notification_Server.py  receives the agent notifications and hands them to the
                      configured interface
    interface/nagios/ turns monitoring data into Nagios passive checks and generates
                      the Nagios configuration for the monitored VMs
    third-parties/    Eucalyptus add_key.pl replacement
    vmmonitor_vm.sql  schema for the VM inventory table

Configuration lives in `running_vms/cluster/cluster_config.py`,
`running_vms/node/node_config.py` and `booting_vms/settings.py`.


Prerequisites
--------


PCMONS is compatible with Eucalyptus and Opennebula (IaaS platform) and Nagios (used to visualize monitoring data). 
However, its development considers easy integration with other toolkits or cloud frameworks through the development 
of extensions.

**Prerequisites:**

    * Eucalyptus >= 1.6.1 or OpenNebula >= 3.0
    * Nagios
    * Python == 2.6.x (greater than 2.6.x may work, less than probably will not; neither is tested)
    * mysql
    * mysql-python
    * python-boto

You can use package manager to install these packages.

**Fedora:**

    $ yum install python mysql-python python-boto mysql-server

**Ubuntu/Debian:**

    $ sudo apt-get install python python-mysqldb python-boto mysql-server
    

To install Eucalyptus or OpenNebula and Nagios you can follow the steps at the official documentation according to your GNU/Linux distribution.

**Eucalyptus** - [http://open.eucalyptus.com/wiki/EucalyptusInstallation_v2.0](http://open.eucalyptus.com/wiki/EucalyptusInstallation_v2.0 "http://open.eucalyptus.com/wiki/EucalyptusInstallation_v2.0") <br>
**Nagios** 	   - [http://nagios.sourceforge.net/docs/3_0/quickstart.html](http://nagios.sourceforge.net/docs/3_0/quickstart.html "http://nagios.sourceforge.net/docs/3_0/quickstart.html") <br>
**OpenNebula** - [http://opennebula.org/documentation:rel4.0](http://opennebula.org/documentation:rel4.0 "http://opennebula.org/documentation:rel4.0") <br>

Installation
--------


1. Configure an user in the MySQL database and in the cluster configuration ($PCMONS/running_vms/cluster/cluster_config.py). By default the user is 'manager' and the password is 'cloudmanager'.
 
    You can execute the command below at a mysql shell to do that:

        mysql> CREATE DATABASE manager;
        mysql> CREATE USER 'manager'@'localhost' IDENTIFIED BY 'cloudmanager';
        mysql> GRANT ALL PRIVILEGES ON manager.* TO 'manager'@'localhost';

    The same database name, user and password must be filled in under
    DATABASES['default'] in cluster_config.py.

2. Create the database and MySQL tables 

    You can run the vmmonitor_vm.sql script through a tool like phpMyAdmin (Just open a query window and copy and paste the content of the text file in there). phpMyAdmin and possibly other frontends will also allow to upload a *.sql file through the web browser. 
    
    In phpMyAdmin click on the SQL tab. If you don't have any such front end installed, you can also use the mysql shell.
    
    Execute this command and you'll be fine: 

        $ mysql -u<user_name> -p<password> <my_db_name> < vmmonitor_vm.sql

3. If you are using Eucalyptus, replace the add_key.pl file with the one in the third-parties directory. It is usually located in the /usr/share/eucalyptus folder.

4. Copy all files in the node folder ($PCMONS/running_vms/node/) to the node hosts and run it (python VM_Monitoring_Node_Plugin.py).

5. Run the other files in the cluster/cloud controller host (where Nagios is installed).


Configuration
--------


Every setting lives in a plain Python module, so it can be edited directly. The addresses
each component binds to or reports to can also be set from the environment, which avoids
editing a file that gets copied to every node or baked into a VM image:

| Variable | Overrides | Default |
| --- | --- | --- |
| `PCMONS_SERVER` | address the in-VM agent reports to (`booting_vms/settings.py`) | `http://150.162.63.32` |
| `PCMONS_SERVER_PORT` | port of that server | `60001` |
| `PCMONS_LISTEN_IP` | address `Notification_Server.py` binds to (`cluster_config.py`) | `150.162.63.32` |
| `PCMONS_LISTEN_PORT` | port it binds to | `60001` |
| `PCMONS_NODE_LISTEN_IP` | address the node plugin binds to (`node_config.py`) | `stratus.lrg.ufsc.br` |
| `PCMONS_NODE_LISTEN_PORT` | port it binds to | `60000` |
| `PCMONS_NODE_LOG_FILE` | node plugin log file | `/var/log/Monitoring_Cloud_Client.log` |

Use `0.0.0.0` as a listen address to accept requests on every interface.

The remaining settings — database credentials, IaaS platform, Nagios paths — have no
environment override and must be edited in `running_vms/cluster/cluster_config.py`.


Information
--------


More information about monitoring of private clouds and pcmons architecture:
 * http://www.tede.ufsc.br/teses/PGCC0911-D.pdf (Portuguese)
 * https://projetos.inf.ufsc.br/arquivos_projetos/projeto_1285/Principal.pdf (Portuguese)
 * http://ieeexplore.ieee.org/xpl/articleDetails.jsp?arnumber=6094017&sortType%3Dasc_p_Sequence%26filter%3DAND%28p_IS_Number%3A6093994%29 (English)


