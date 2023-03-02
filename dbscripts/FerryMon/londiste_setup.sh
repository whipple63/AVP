#!/bin/sh
# This script should be run on the remote machine.
# It sets up table replication

echo "Adding to master..."
londiste3 /etc/londiste3.ini add-table `hostname`_cast
londiste3 /etc/londiste3.ini add-table `hostname`_gps
londiste3 /etc/londiste3.ini add-table `hostname`_isco
londiste3 /etc/londiste3.ini add-table `hostname`_log
londiste3 /etc/londiste3.ini add-table `hostname`_power
londiste3 /etc/londiste3.ini add-table `hostname`_sonde
londiste3 /etc/londiste3.ini add-table `hostname`_wind

echo "Adding to storm..."
londiste3 /etc/londiste3_storm.ini add-table `hostname`_cast
londiste3 /etc/londiste3_storm.ini add-table `hostname`_gps
londiste3 /etc/londiste3_storm.ini add-table `hostname`_isco
londiste3 /etc/londiste3_storm.ini add-table `hostname`_log
londiste3 /etc/londiste3_storm.ini add-table `hostname`_power
londiste3 /etc/londiste3_storm.ini add-table `hostname`_sonde
londiste3 /etc/londiste3_storm.ini add-table `hostname`_wind

echo "Adding to wave..."
londiste3 /etc/londiste3_wave.ini add-table `hostname`_cast
londiste3 /etc/londiste3_wave.ini add-table `hostname`_gps
londiste3 /etc/londiste3_wave.ini add-table `hostname`_isco
londiste3 /etc/londiste3_wave.ini add-table `hostname`_log
londiste3 /etc/londiste3_wave.ini add-table `hostname`_power
londiste3 /etc/londiste3_wave.ini add-table `hostname`_sonde
londiste3 /etc/londiste3_wave.ini add-table `hostname`_wind
