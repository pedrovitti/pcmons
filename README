PCMONS - Private Clouds MONitoring Systems

I.   SUMMARY
II.  PREREQUISITES
III.  INSTALLATION

I. SUMMARY:
-----------------------------------------------------------------
Considering the lack of generic and open-source solutions for management and monitoring of private clouds, PCMONS was developed. It is intended to be an extensible and modular monitoring system for private clouds. In its first release, PCMONS acts principally retrieving, gathering and preparing relevant information for monitoring data visualization and is specially on virtual machines.

Authors: 
Shirlei Chaves (shirlei@inf.ufsc.br), 
Rafael Uriarte (rafael.uriarte@inf.ufsc.br)
Pedro Vitti (pedrovitti@gmail.com.br)

Site: http://code.google.com/p/pcmons/
 

II. PREREQUISITES:
-----------------------------------------------------------------
The first release of PCMONS is compatible with Eucalyptus (IaaS platform) and Nagios (used specially to visualize monitoring data). However, its development considers easily integration with other toolkit or cloud frameworks, like OpenNebula, through the development of extensions.

Eucalyptus >= 1.6.1
Nagios

Python == 2.6.x (greater than 2.6.x may work, less than probably will not; neither is tested)
MySQL
MySQL-python
python-boto

You can use packager manager to install these packages.

Ex: 
Fedora: 
        $ yum install python MySQL-python python-boto mysql-server

Ubuntu/Debian: 
        $ sudo apt-get install python python-mysqld python-boto mysql-server 

To install Eucalyptus and Nagios you can follow the steps at the official eucalyptus/nagios documentation according to your GNU/Linux distribution.

Eucalyptus - http://open.eucalyptus.com/wiki/EucalyptusInstallation_v2.0
Nagios 	   - http://nagios.sourceforge.net/docs/3_0/quickstart.html
 

III. INSTALLATION:
------------------------------------------------------------------
1. Configure an user in the MySQL database and in the cluster configuration ($PCMONS/running_vms/cluster/cluster_config.py).
By default the user is 'manager' and the password is 'cloudmanager'.
 
You can execute the command below at a mysql shell to do that:
        $ mysql: CREATE USER 'manager'@'localhost' IDENTIFIED BY 'cloudmanager';

2. Create the database and MySQL tables 
You can run the vmmonitor_vm.sql script through a tool like phpMyAdmin (Just open a query window and copy and paste the content of the text file in there). phpMyAdmin and possibly other frontends will also allow to upload a *.sql file through the web browser. In phpMyAdmin click on the SQL tab.

If you don't have any such front end installed, you can also use the mysql shell.
Execute this command and you'll be fine: 

        $ mysql <my_db_name> -u<user_name> -p<password> vmm_monitor_vm.sql

3. Change the Eucalyptus add_key.pl by the one in the third-parties directory. Usually it's locate in /usr/share/eucalyptus folder.

4. Copy all files in the node folder ($PCMONS/running_vms/node/) to the node hosts and run it (python VM_Monitoring_Node_Plugin.py).

5. Run the others files in the cluster/cloud controller host (where Nagios is installed).

