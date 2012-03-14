#!/bin/sh
# Author: rafael.uriarte@gmail.com
# Version: 1.0
# Description: writes command msgs to the nagios pipe
usage()
{
    echo "Usage: $0 <hostname> <service desc> <severity> <comment>"
    echo "   Severity is,  0 for OK, 1 for Warning and 2 for Critical."
    echo "   comment to place on the event, probably will need to be quoted."
}

if [ $# -lt 4 ]; then
    echo "$0: Too few parameters"
    usage
    exit 1
fi

if [ $# -gt 4 ]; then
    echo "$0: Too many parameters"
    usage
    exit 1
fi

hostname=$1
servicedesc=$2
severity=$3
# command is comment with ; replaced for space
comment_data=${4/;/ }

echocmd="/bin/echo"

CommandFile="/var/spool/nagios/nagios.cmd"

# get the current date/time in seconds since UNIX epoch
datetime=`date +%s`

if [ $severity != 1 -a $severity != 0 -a $severity != 2 ]; then
    echo "Severity must be 1 or 0 or 2"
        usage
            exit 1
            fi

            # create the command line to add to the command file
            cmdline="[$datetime] PROCESS_SERVICE_CHECK_RESULT;$hostname;$servicedesc;$severity;$comment_data"

            # append the command to the end of the command file
            $echocmd $cmdline
            `$echocmd $cmdline >> $CommandFile`
