This is the service script that works for my system (Mandriva 2006).

It goes in /etc/init.d.

Then in /etc/rc.d/rc5.d do
ln -s /etc/init.d/pertd S98pertd

Now everything set.  When you restart your system, the pertd daemon
will start automatically.
