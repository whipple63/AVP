#!/usr/bin/perl -w
#
use XML::Simple;

# Parse the mi.rss file
#$ref=XMLin("/home/rlauzon/tmp/KGRR.xml");
$ref=XMLin("/tmp/KORD.xml");

# Get the warning description
$obstime=$$ref{"observation_time"};
$weather=$$ref{"weather"};
$temperature=$$ref{"temperature_string"};
$wind=$$ref{"wind_string"};
$gust=$$ref{"wind_gust_mph"};
$heat_index=$$ref{"heat_index_string"};
$wind_chill=$$ref{"windchill_string"};

print "$obstime - $weather - $temperature - $wind ";
if ($gust eq "NA") {
	print "- ";
} else {
	print "gusting to $gust - ";
}
if ($heat_index ne "NA") {
	print "Heat index $heat_index - ";
}
if ($wind_chill ne "NA") {
	print "Wind chill $wind_chill - ";
}
