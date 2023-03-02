#!/bin/bash
JAR_FILE="$1"
VER="$2"
DIR="javp-"$VER
echo $DIR
rm -rf $DIR
mkdir $DIR
mkdir $DIR/bin
mkdir $DIR/lib
cp $JAR_FILE $DIR/lib/.
cp lib/*.conf $DIR/bin/.
cp lib/*.jar $DIR/lib/.
cp RELEASE $DIR/.
mkdir $DIR/doc
cp doc/*.html $DIR/doc/.
#cp -r doc/javadoc $DIR/doc/.
mkdir $DIR/doc/src
cp -r doc/src/* $DIR/doc/src/.
cp doc/README $DIR/.
#
START_FILE=$DIR"/bin/dashboard"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.dashboard.Dashboard \$MY_DIR/db.conf \$MY_DIR/dashboard.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/wind_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/wind.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/ysi_sonde_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/ysi_sonde.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/aio_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/aio.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/io_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar:\$MY_DIR/../lib/pi4j-core.jar:\$MY_DIR/../lib/pi4j-service.jar:\$MY_DIR/../lib/slf4j-api-1.7.25.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/io.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/mm3_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/mm3.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/sounder_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/sounder.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/gpsd_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/gpsd.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/isco_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/isco.conf"  >> $START_FILE
chmod +x $START_FILE
#
START_FILE=$DIR"/bin/lisst_broker"
echo "#!/bin/bash" >> $START_FILE
echo "MY_DIR=\`dirname \$0\`" >> $START_FILE
echo "java -cp \$MY_DIR/../lib/javp-$VER.jar:\$MY_DIR/../lib/json-1.0.jar:\$MY_DIR/../lib/postgresql-8.4-701.jdbc3.jar edu.unc.ims.avp.Broker \$MY_DIR/db.conf \$MY_DIR/lisst.conf"  >> $START_FILE
chmod +x $START_FILE
#
tar czf $DIR.tar.gz $DIR
rm -rf $DIR
