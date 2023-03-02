/*
This program allows the avp user to run a script as postgres using setuid functionality.
To compile and set up do:
gcc avp_setuid.c -o avp_setuid
chown postgres:postgres avp_setuid
chmod 4755 avp_setuid
mv avp_setuid ~postgres/bin
*/
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

int main()
{
   setuid( 0 );
   system( "~postgres/bin/avp_setuid.sh" );
   
   return 0;
}
