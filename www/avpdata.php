<?php		
		/*
		 * Reads the database and outputs XML tags into the source HTML that define values read.
		 * These tags will be picked up by the javascript code and used to format the page.
		 */
		$link = pg_Connect("host=storm.ims.unc.edu dbname=$dbname user=ims password=ims6841");
		if($link == "") {
			echo "<B>Failed to connect to database</b><br>";
		}
		
		$result = pg_exec($link, "select * from " . $dbname . "_wind order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search " . $dbname . "_wind</b><br>";
		}		
		$numrows = pg_numrows($result);
		echo "\n\t<wind ";
		// Loop on rows in the result set.
		for($ri = 0; $ri < $numrows; $ri++) {
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
		}
		echo ">\n\t</wind>";
		
		$result = pg_exec($link, "select * from " . $dbname . "_gps order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search " . $dbname . "_gps</b><br>";
		}		
		$numrows = pg_numrows($result);
		echo "\n\t<gps ";
		// Loop on rows in the result set.
		for($ri = 0; $ri < $numrows; $ri++) {
			$row = pg_fetch_array($result, $ri);
			echo "sample_time=\"", $row["sample_time"], "\" ";
			echo "lat=\"", $row["lat"], "\" ";
			echo "lon=\"", $row["lon"], "\" ";
		}
		echo ">\n\t</gps>";

		$result = pg_exec($link, "select * from " . $dbname . "_depth order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search " . $dbname . "_depth</b><br>";
		}		
		$numrows = pg_numrows($result);
		echo "\n\t<depth ";
		// Loop on rows in the result set.
		for($ri = 0; $ri < $numrows; $ri++) {
			$row = pg_fetch_array($result, $ri);
			echo "sample_time=\"", $row["sample_time"], "\" ";
			echo "working_depth=\"", $row["working_depth"], "\" ";
			echo "calculated_depth=\"", $row["calculated_depth"], "\" ";
			echo "calculated_depth_std=\"", $row["calculated_depth_std"], "\" ";
			echo "num_good_pings=\"", $row["num_good_pings"], "\" ";
			echo "temp_c=\"", $row["temp_c"], "\" ";
		}
		echo ">\n\t</depth>";
		
		pg_close($link);
?>
