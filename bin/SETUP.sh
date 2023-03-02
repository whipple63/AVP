#Run this as root for initial setup

cd /home/avp
# Fix permissions
chown -R avp:avp .ssh aio bin pertd2 python
chmod 600 .ssh/authorized_keys
chmod 774 bin/*.sh
chmod 775 bin/*.sh pertd2/pertd2

# Compile avp_setuid
cd bin
gcc avp_setuid.c -o avp_setuid
chown postgres:postgres avp_setuid*
chmod 6755 avp_setuid
ln -s  avp_setuid* ~postgres/bin

# Make links
ln -s /home/avp/aio/aio /usr/local/bin/aio
ln -s /home/avp/bin/cast_sched.sh /usr/local/bin/cast_sched
ln -s /home/avp/bin/cons.sh /usr/local/bin/cons
ln -s /home/avp/pertd2/pertd2 /usr/local/bin/pertd2
ln -s /home/avp/bin/super.sh /usr/local/bin/super
ln -s /home/avp/bin/init_all_socat.sh init_all_socat

# set up  log directory
mkdir /data/log
chmod 775 /data/log
chown avp:avp /data/log
ln -s /home/avp/bin/clearlogs.sh /data/log/clearlogs.sh
ln -s /data/log /home/avp/log