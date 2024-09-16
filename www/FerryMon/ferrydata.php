<?php		
		/*
		 * Reads the database and outputs XML tags into the source HTML that define values read.
		 * These tags will be picked up by the javascript code and used to format the page.
		 */
		$link = pg_Connect("host=wave.ims.unc.edu dbname=$dbname user=ims password=ims6841");
		if($link == "") {
			echo "<B>Failed to connect to database</b><br>";
		}
		
		$result = pg_exec($link, "select * from " . $dbname . "_wind order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search " . $dbname . "_wind</b><br>";
		}		
		$numrows = pg_num_rows($result);
		// Loop on rows in the result set.
		for($ri = 0; $ri < $numrows; $ri++) {
			echo "\n\t<wind ";
			$row = pg_fetch_array($result, $ri);
			echo "sample_time=\"", $row["sample_time"], "\" ";
			echo "speed_scalar=\"", $row["speed_scalar"], "\" ";
			echo "dir_unit_vector=\"", $row["dir_unit_vector"], "\" ";
			echo "speed_std=\"", $row["speed_std"], "\" ";
			echo "speed_vector=\"", $row["speed_vector"], "\" ";
			echo "dir_vector=\"", $row["dir_vector"], "\" ";
			echo "gust_speed=\"", $row["gust_speed"], "\" ";
			echo "gust_dir=\"", $row["gust_dir"], "\" ";
			echo "gust_time=\"", $row["gust_time"], "\" ";
			echo ">\n\t</wind>";
		}
		
		$result = pg_exec($link, "select * from " . $dbname . "_gps order by \"sample_time\" desc limit " . $numgps . " offset 0");
		if($result == "") {
			echo "<B>Failed to search " . $dbname . "_gps</b><br>";
		}		
		$numrows = pg_num_rows($result);
		
		/*
		echo "\n\t<DEBUGINFO ";
		echo $numrows;
		echo ">\n\t</DEBUGINFO>";
		*/
		
		// Loop on rows in the result set.
		for($ri = 0; $ri < $numrows; $ri++) {
			echo "\n\t<gps ";
			$row = pg_fetch_array($result, $ri);
			echo "row: " . "$ri ";
			echo "sample_time=\"", $row["sample_time"], "\" ";
			echo "lat=\"", $row["lat"], "\" ";
			echo "lon=\"", $row["lon"], "\" ";
			echo "speed=\"", $row["speed"], "\" ";
			echo "track=\"", $row["track"], "\" ";
			echo ">\n\t</gps>";
		}

		$result = pg_exec($link, "select * from " . $dbname . "_cast order by \"cast_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search " . $dbname . "_cast</b><br>";
		}		
		$numrows = pg_num_rows($result);
		// Loop on rows in the result set.
		for($ri = 0; $ri < $numrows; $ri++) {
			echo "\n\t<flow ";
			$row = pg_fetch_array($result, $ri);
			echo "cast_time=\"", $row["cast_time"], "\" ";
			echo "flow_rate=\"", $row["flow_rate"], "\" ";
			echo ">\n\t</flow	>";
		}

		$result = pg_exec($link, "select * from " . $dbname . "_sonde order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search " . $dbname . "_sonde</b><br>";
		}		
		$numrows = pg_num_rows($result);
		// Loop on rows in the result set.
		for($ri = 0; $ri < $numrows; $ri++) {
			echo "\n\t<sonde ";
			$row = pg_fetch_array($result, $ri);
			echo "sample_time=\"", $row["sample_time"], "\" ";
			echo "tempc=\"", $row["tempc"], "\" ";
			echo "salppt=\"", $row["salppt"], "\" ";
			echo "dissolved_o2=\"", $row["dissolved_o2"], "\" ";
			echo "turbid=\"", $row["turbid"], "\" ";
			echo "chl=\"", $row["chl"], "\" ";
			echo "ph=\"", $row["ph"], "\" ";
			echo ">\n\t</sonde>";
		}
		
		pg_close($link);
?>
