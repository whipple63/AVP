#!/bin/bash -x
#
# Little utility script to rebuild and untar the java brokers
#

rm /home/avp/javp-*.tar.gz
rm -R /home/avp/javp-*
pushd .
cd /home/avp/javp
rm *.tar.gz
ant publish
cd ..
cp javp/javp-*.tar.gz .
tar xvf javp-*.tar.gz
popd
