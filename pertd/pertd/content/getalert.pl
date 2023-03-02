#!/usr/bin/perl -w
#
use XML::Simple;

# Parse the rss file
$ref=XMLin("/tmp/cookalerts.rss");

# Get the warning description
$channel=$$ref{"channel"}{"item"}{"description"};

# Break up by newlines
@stuff=split(/\n/,$channel);

# Write out the non-zero length string
foreach $line (@stuff) {
	if (length($line) > 0) {
		$line =~ s/<BR>/ /ig;
		$line =~ s/<a .*>//ig;
		print "$line\n";
	}
}
