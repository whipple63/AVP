#!/bin/sh -x
# Creates all the database tables that start with hostname
psql -f avp_cast     `hostname` postgres # Has to be first

psql -f avp_depth    `hostname` postgres
psql -f avp_gps      `hostname` postgres
psql -f avp_isco     `hostname` postgres
psql -f avp_lisst    `hostname` postgres
psql -f avp_log      `hostname` postgres
psql -f avp_power    `hostname` postgres
psql -f avp_schedule `hostname` postgres
psql -f avp_sonde    `hostname` postgres
psql -f avp_wind     `hostname` postgres
