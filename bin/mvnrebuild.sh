#!/bin/bash

# rebuilds java code using maven

pushd .
cd /home/avp/javp

# use the clean command below to start fresh
#mvn clean
mvn package

# Brokers can be run using the following command:
# (Apart from the jar, the rest of the classpath is built into the manifest file by maven.)
# (sudo is only necessary for the I/O broker due to its use of low level pi I/O)
# sudo java -cp /home/avp/javp/target/javp-1.1-SNAPSHOT.jar edu.unc.ims.avp.Broker /home/avp/javp/target/lib/db.conf /home/avp/javp/target/lib/io.conf
#

popd
