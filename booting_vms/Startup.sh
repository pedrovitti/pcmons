#!/bin/sh
#Author : Shirlei Chaves
#E-mail : shirlei@gmail.com
#Date: 2010-07-20
#Version : 1.0
#Description : This script sets up monitoring files

touch /root/install_log.txt
DO_INSTALL=1
if [ -e /lib/custom_setup/custom_install.sh ]; then
    . /lib/custom_setup/custom_install.sh
fi

config_monitor(){
    echo "doing config_monitor" >> /root/install_log.txt
    # Creating/moving necessary files
    if [ ! -d /opt/monitoring ] ; then
        mkdir -p /opt/monitoring
        echo "directory /opt/monitoring created" >> /root/install_log.txt
    fi
    
    #running the monitor
    if [ -e /root/monitoring.tar ]; then
        tar -xf /root/monitoring.tar -C /opt/monitoring
        python /opt/monitoring/Monitor.py > /dev/null 2>&1 &
        echo "started Monitor.py" >> /root/install_log.txt
    fi
    
    #removing unecessary files
    rm /root/monitoring.tar
    echo "removed /root/monitoring.tar" >> /root/install_log.txt
}

config_custom_install(){
    echo "doing custom_install" >> /root/install_log.txt
    do_install
    echo "custom_install finished" >> /root/install_log.txt
}

case "$1" in
start)
    config_monitor
    if [ $DO_INSTALL -eq 0 ];then
        config_custom_install
    fi
    ;;
*)
    echo "usage: start"
    exit 1
esac

exit 0

