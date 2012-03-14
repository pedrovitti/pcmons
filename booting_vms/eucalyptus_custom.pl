#!/usr/bin/perl
# author: shirlei@gmail.com
# version : 1.0
# date: 16/08/2010
# description: injects in the vm filesystm the necessary files
# for PCMONS monitoring and a web server instalation

$CUSTOM_SETUP_DIR='/lib/custom_setup';
$BOOT_SCRIPTS_DIR='/opt/pcmons/booting_vms';

sub do_custom_setup(){
    $mon = do_monitoring_setup();
    $soft = do_software_setup();
    # debugging purposes
    open(FILE,">$tmpfile/results.txt");
    print FILE "mon: $mon\n";
    print FILE "soft: $soft\n";
    close(FILE);
    return "Custom Setup Done: $mon, $soft";

}

sub do_monitoring_setup(){
    if ( -f "$tmpfile/etc/issue"){
        $res= `cat $tmpfile/etc/issue`;
        if ( $res =~ /CentOS/i ){
            do_centos_mconfig();
        }elsif ( $res =~ /Fedora/i ){
            do_fedora_mconfig();
        }elsif ( $res =~ /Debian/i ){
            do_debian_mconfig();
        }elsif ( $res =~ /Ubuntu/i ){
            do_ubuntu_mconfig();
        }else{
            do_generic_mconfig();
        }       
    }else{
        return "no $tmpfile/etc/issue file found!";
    }
}

sub do_generic_mconfig(){
    print "not implemented yet!";
    return "not implemented yet!";
}

sub do_debian_mconfig(){
    return "not implemented yet!"
}

sub do_fedora_mconfig(){
    return "not implemented yet!"
}
sub do_ubuntu_mconfig(){
    system("/bin/cp $BOOT_SCRIPTS_DIR/Startup.sh $tmpfile/etc/rc2.d/S98Monitoring.sh");
    system("/bin/cp $BOOT_SCRIPTS_DIR/monitoring.tar $tmpfile/root/monitoring.tar");
}

sub do_centos_mconfig(){
    # adding monitoring 
    # in case the original rc.local has exit 0, remove it
    $rc_local_file="$tmpfile/etc/rc.local";
    if (!open(OFH, ">>$rc_local_file")) {
        return "rc local file not opened!";
    }else{
        open(FILE,"<$rc_local_file");
        @LINES = <FILE>;
        close(FILE);
        open(FILE,">$rc_local_file");
        foreach $LINE (@LINES) {
            if ($LINE =~ /^exit 0$/){
                next;
            }else{
                print FILE "$LINE";
            }
        }
        close(FILE); 
     } 
    
    if (!open(OFH, ">>$rc_local_file")) {
        return "rc local file not opened!";
    }else{
        print OFH "\n";
        if (!open(FH, "$BOOT_SCRIPTS_DIR/Startup.sh")) {
            return "cannot read from: $BOOT_SCRIPTS_DIR/Startup.sh"; 
        }else{
            while(<FH>) {
                chomp;
                print OFH "$_\n";
            }
            close(FH);
        }
        close(OFH);
    }
    system("/bin/cp $BOOT_SCRIPTS_DIR/monitoring.tar $tmpfile/root/monitoring.tar");
}

sub do_software_setup(){
    if ( -f "$tmpfile/etc/issue"){
        $res= `cat $tmpfile/etc/issue`;
        if ( $res =~ /CentOS/i ){
            do_centos_sconfig();
        }elsif ( $res =~ /Fedora/i ){
            do_fedora_sconfig();
        }elsif ( $res =~ /Debian/i ){
            do_debian_sconfig();
        }elsif ( $res =~ /Ubuntu/i ){
            do_ubuntu_sconfig();
        }else{
            do_generic_sconfig();
        }       
    }else{
        return "no $tmpfile/etc/issue file found!";
    }
}

sub do_generic_sconfig(){
    return "not implemented yet!";
}

sub do_fedora_sconfig(){
    return "not implemented yet!";
}

sub do_debian_sconfig(){
    return "not implemented yet!";
}

sub do_ubuntu_sconfig(){
    if ( !-d "$tmpfile$CUSTOM_SETUP_DIR" ) {
        system("$MKDIR -p $tmpfile$CUSTOM_SETUP_DIR");
    }
    system("/bin/cp $BOOT_SCRIPTS_DIR/ubuntu9.04/ubuntu9.04lamp.sh $tmpfile$CUSTOM_SETUP_DIR/custom_install.sh");
    system("/bin/cp $BOOT_SCRIPTS_DIR/ubuntu9.04/ubuntu9.04.tar.gz $tmpfile/root/ubuntu9.04.tar.gz");
}

sub do_centos_sconfig(){
    if ( !-d "$tmpfile$CUSTOM_SETUP_DIR" ) {
        system("$MKDIR -p $tmpfile$CUSTOM_SETUP_DIR");
    }
    system("/bin/cp $BOOT_SCRIPTS_DIR/centos5/centos5lamp.sh $tmpfile$CUSTOM_SETUP_DIR/custom_install.sh");
    system("/bin/cp $BOOT_SCRIPTS_DIR/centos5/centos5.tar.gz $tmpfile/root");
}

1;
