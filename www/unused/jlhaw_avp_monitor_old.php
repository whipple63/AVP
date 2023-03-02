<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
    <head>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
	
	<title>Jordan Lake Autonomous Vertical Profilers</title>

	<script src="//ajax.googleapis.com/ajax/libs/jquery/1.10.2/jquery.min.js"></script>
	<script src="//ajax.googleapis.com/ajax/libs/jqueryui/1.10.3/jquery-ui.min.js"></script>
	<link href="css/vader/jquery-ui-1.10.4.custom.css" rel="stylesheet">
	
	<script>
		function on_page_load() {	// Called when page loads.
			_appData = new AppData();
			_appData.load_wind();
			_appData.load_gps();
			_appData.load_depth();
			updateDataDisplay();
			updateProfileDisplay();
		}

		function on_page_unload() {  // Called when page unloads.
		}

		// Container object for all data as read from tags created in php code
		function AppData() {
			this.windReadings = new Array();
			this.gpsReadings = new Array();
			this.depthReadings = new Array();
			
			this.load_wind = function() {
				var readings = document.getElementsByTagName('wind');
				if((readings == undefined) || (readings.length==0)) {
					alert("Failed to locate wind element");
					return;
				}
				for(var i=0; i < readings.length; i++) {
					var reading = readings[i];
					this.windReadings.push(new WindReading(reading));
				}
			}
			
			this.load_gps = function() {
				var readings = document.getElementsByTagName('gps');
				if((readings == undefined) || (readings.length==0)) {
					alert("Failed to locate gps element");
					return;
				}
				for(var i=0; i < readings.length; i++) {
					var reading = readings[i];
					this.gpsReadings.push(new GpsReading(reading));
				}
			}
			
			this.load_depth = function() {
				var readings = document.getElementsByTagName('depth');
				if((readings == undefined) || (readings.length==0)) {
					alert("Failed to locate depth element");
					return;
				}
				for(var i=0; i < readings.length; i++) {
					var reading = readings[i];
					this.depthReadings.push(new DepthReading(reading));
				}
			}
		}

		function WindReading(e) {
			this.sample_time = e.getAttribute('sample_time');
			this.speed_scalar = e.getAttribute('speed_scalar');
			this.dir_unit_vector = e.getAttribute('dir_unit_vector');
			this.speed_std = e.getAttribute('speed_std');
			this.speed_vector = e.getAttribute('speed_vector');
			this.dir_vector = e.getAttribute('dir_vector');
			this.gust_speed = e.getAttribute('gust_speed');
			this.gust_dir = e.getAttribute('gust_dir');
			this.gust_time = e.getAttribute('gust_time');
		}
		function GpsReading(e) {
			this.sample_time = e.getAttribute('sample_time');
			this.lat = e.getAttribute('lat');
			this.lon = e.getAttribute('lon');
		}
		function DepthReading(e) {
			this.sample_time = e.getAttribute('sample_time');
			this.working_depth = e.getAttribute('working_depth');
			this.calculated_depth = e.getAttribute('calculated_depth');
			this.calculated_depth_std = e.getAttribute('calculated_depth_std');
			this.num_good_pings = e.getAttribute('num_good_pings');
			this.temp_c = e.getAttribute('temp_c');
		}

		var windDirs = new Array("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW");
		function updateDataDisplay() {
			var layersDiv = document.getElementById('data');
			var tbl = document.createElement('table');
			tbl.setAttribute('id', 'data_table');
			tbl.setAttribute('border', '2');
			layersDiv.appendChild(tbl);

			addRow(tbl, "Wind Observation Time",  String(_appData.windReadings[0].sample_time).substr(0,19));
			var wdirIndex = Math.round((_appData.windReadings[0].dir_unit_vector - 11.25) / 22.5);
			var wdirTxt = windDirs[wdirIndex];
			addRow(tbl, "Wind Direction (from)",  Number(_appData.windReadings[0].dir_unit_vector).toFixed(0) + " ("+wdirTxt+")");
			addRow(tbl, "Wind Speed",             Number(_appData.windReadings[0].speed_scalar * 1.943844492440605).toFixed(1) + " kts");
			addRow(tbl, "Wind Gust",              Number(_appData.windReadings[0].gust_speed * 1.943844492440605).toFixed(1) + " kts");
			addRow(tbl, "&nbsp", " ");
			addRow(tbl, "Depth Observation Time", String(_appData.depthReadings[0].sample_time).substr(0,19));
			addRow(tbl, "Water Depth",            Number(_appData.depthReadings[0].calculated_depth * 3.280839895013123).toFixed(1) + " ft");
			addRow(tbl, "Surface Temp",           Number(_appData.depthReadings[0].temp_c * 9/5 + 32).toFixed(0) + " Deg. F");
			addRow(tbl, "&nbsp", " ");
			addRow(tbl, "GPS Observation Time",   String(_appData.gpsReadings[0].sample_time).substr(0,19));
			var ldeg = Math.floor(_appData.gpsReadings[0].lat);
			var lmin = (_appData.gpsReadings[0].lat - Math.floor(_appData.gpsReadings[0].lat))*60;
			addRow(tbl, "Lat",            ldeg + " " + Number(lmin).toFixed(3) + " N" );
			ldeg = Math.floor(Math.abs(_appData.gpsReadings[0].lon));
			lmin = (Math.abs(_appData.gpsReadings[0].lon) - Math.floor(Math.abs(_appData.gpsReadings[0].lon)))*60;
			addRow(tbl, "Lon",            ldeg + " " + Number(lmin).toFixed(3) + " W" );
		}
		function addRow(tbl, name, value) {
			var tr = document.createElement('tr');
			tbl.appendChild(tr);
			var td = document.createElement('td');
			tr.appendChild(td);
			td.innerHTML = name;
			td = document.createElement('td');
			tr.appendChild(td);
			td.innerHTML = value;
		}

		function updateProfileDisplay() {
			$(document).ready(function(){
				$('#profile_cal').datepicker({
					minDate: new Date(2017, 4, 17),
					maxDate: new Date(),
					changeMonth: true,
					changeYear: true,
					onSelect: function(dateText, inst) { drawProfilePlot(); }
				});
				$('#profile_cal').datepicker( "setDate", new Date() );
				drawProfilePlot();
			});
			
		function drawProfilePlot() {
			var plotFile;
			var selDate = $('#profile_cal').datepicker( "getDate" );
			plotFile = "jlhaw/" + "AVP3_" + selDate.getFullYear() + pad(selDate.getMonth()+1) + pad(selDate.getDate()) + ".png";
			$('#profiles').attr('src', plotFile);
			$.ajax({
				url: plotFile,
				success: function(data) {document.getElementById('img_status').innerHTML = ""; },
				error: function(data) {document.getElementById('img_status').innerHTML = "Profile image does not exist for " + selDate.toDateString(); }
				});
				
		}

		function pad(n) {
			return (n < 10) ? ("0" + n) : n;
		}
		
		}
	</script>


	<style type="text/css">
	html, body { height:93%; }
	body {
		font-family: Verdana, sans-serif;
		margin: 5px;
		padding: 5px;
		cursor: auto;
	}
	#data {
		float: left;
		overflow: auto;
		background: #cccccc;
		clear: left;
		font-family: Verdana, sans-serif;
		font-size: 1.0em;
	}
	td {
		padding:3px;
	}
	#profile_cal {
		margin: 5px;
		float: left;
		font-size: 0.8em;
	}
	#profile_img {
		margin: 5px;
		float: left;
		font-size: 0.8em;
	}
	#img_status {
		float: left;
		font-family: Verdana, sans-serif;
		font-size: 1.0em;
		}
	#pic {
		float: left;
		clear: left;
		width: 150px;
		height: 150px;
	}
	img{
		display:block;
	}
	#header {
		font-family: Verdana, sans-serif;
		clear:right;
	}
	#avp_image {
			width: 100%;
			height: 100%;
	}
	</style>
	
</head>

<body onload="on_page_load()">
	<h1>Jordan Lake Autonomous Vertical Profilers</h1>
	<p><a href="AVP Locations.jpg"><img src="AVP Locations.jpg" style="float:right;width: 800px;height:400px;"/></a>
	The Autonomous Vertical Profilers (AVPs) use a YSI Multi-Parameter Sonde to measure water temperature, 
	salinity, pH, dissolved oxygen concentration, chlorophyll concentration, and turbidity from surface to bottom every
	30 minutes.  There is also an anemometer for wind speed and direction, and a consumer-grade depth sounder
	reporting water depth and surface temperature.</p>
	<h2><a href="jlwhiteoak_avp_monitor.php">White Oak</a> --- <a href="jlnewhope_avp_monitor.php">New Hope</a> --- <a href="jlhaw_avp_monitor.php">Haw River</a></h2>
	
	<div id="pic"><img id="avp_image" src="Haw AVP Small.jpg"></div>
	
	<div id="header">
	<h2>Haw River Profiler - Recent Conditions</h2>
	<p>This page shows data acquired from the station located in the Haw River section of B. Everett Jordan Reservoir.  Data are available in
	real-time upon collection.  Wind and depth are averages taken every ten minutes.  Profile images are updated every
	30 minutes and can be reviewed by date using the calendar below.  Profiler graphics are always in EST whereas the data in the table follows local time.
	</p>
	<p><i>Refresh the page for updated data.</i></p>
	<p>Here are some links to some USGS discharge data for above and below Jordan Lake:</p>
	<ul>
	<li><a href="https://waterdata.usgs.gov/nwis/uv?02096960">Haw River near Bynum, NC</a></li>
	<li><a href="https://waterdata.usgs.gov/usa/nwis/uv?02098206">Haw River near Moncure, NC (Below the dam)</a></li>
	<li><a href="https://waterdata.usgs.gov/nwis/uv?site_no=0209782609">White Oak Cr at mouth near Green Level, NC</a></li>
	<li><a href="https://waterdata.usgs.gov/nwis/uv?site_no=0209741955">Northeast Cr near Genlee, NC</a></li>
	<li><a href="https://waterdata.usgs.gov/usa/nwis/uv?site_no=02097314">New Hope Cr near Blands, NC</a></li>
	<li><a href="https://waterdata.usgs.gov/nwis/uv?site_no=02097517">Morgan Cr near Chapel Hill, NC</a></li>
	</ul>
	<p><b><u><font color="red">NOTE:</u></b> Data for the Haw River are available from 17-May-2017 to 26-Jul-2017</font></p>
	</div>
	
	<div id="data"><h3>Most Recent Observations</h3></div>
	
	<div id="profile_cal"><h3>Select Date for Profile Graph</h3></div>
	<div id="profile_img"><img id="profiles"></div>
	<p id="img_status"></p>

		
	<?php
		/*
		 * Reads the database and outputs XML tags into the source HTML that define values read.
		 * These tags will be picked up by the javascript code and used to format the page.
		 */
		$link = pg_Connect("host=storm.ims.unc.edu dbname=jlhaw user=ims password=ims6841");
		if($link == "") {
			echo "<B>Failed to connect to database</b><br>";
		}
		
		$result = pg_exec($link, "select * from jlhaw_wind order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search jlhaw_wind</b><br>";
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
		
		$result = pg_exec($link, "select * from jlhaw_gps order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search jlhaw_gps</b><br>";
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

		$result = pg_exec($link, "select * from jlhaw_depth order by \"sample_time\" desc limit 1 offset 0");
		if($result == "") {
			echo "<B>Failed to search jlhaw_depth</b><br>";
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
	  
	</body>
</html>
