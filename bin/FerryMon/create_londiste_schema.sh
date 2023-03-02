# So far I have not figured out how to modify existing schema within londiste, so I think it will be best
# to remove the schema from all databases and start fresh.

# drop schema londiste,pgq,pgq_ext,pgq_node cascade;
# Drop the londiste schema in all 3 databases
psql -h cherrybranch.dyndns.org -c "drop schema if exists londiste,pgq,pgq_ext,pgq_node cascade;" cherrybranch postgres
psql -h wave.ims.unc.edu -c "drop schema if exists londiste,pgq,pgq_ext,pgq_node cascade;" cherrybranch postgres
psql -h storm.ims.unc.edu -c "drop schema if exists londiste,pgq,pgq_ext,pgq_node cascade;" cherrybranch postgres

# create the londiste schema in the database
londiste3 /etc/londiste3.ini create-root master 'user=postgres password=ims6841 host=cherrybranch.dyndns.org dbname=cherrybranch'

#read -n 1 -p "Would you like to update the branch (slave) database schema as well? [y,N] " toContinue
#toContinue=${toContinue:-"n"}
#if [ "$toContinue" != "y" ]; then
#    exit 1
#fi

londiste3 /etc/londiste3_storm.ini create-branch storm 'user=postgres password=ims6841 host=storm.ims.unc.edu dbname=cherrybranch' --provider='user=postgres password=ims6841 host=cherrybranch.dyndns.org dbname=cherrybranch'
londiste3 /etc/londiste3_wave.ini create-branch wave 'user=postgres password=ims6841 host=wave.ims.unc.edu dbname=cherrybranch' --provider='user=postgres password=ims6841 host=cherrybranch.dyndns.org dbname=cherrybranch'
