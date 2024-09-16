<!DOCTYPE html>
<html lang="en-US">
<head>
	<meta charset="utf-8">
	<meta http-equiv="X-UA-Compatible" content="IE=edge">
	
	<title>Southport to Fort Fisher</title>
	<meta name="viewport" content="width=device-width, initial-scale=1,maximum-scale=1,user-scalable=no">

	<link rel='dns-prefetch' href='//its2.unc.edu' />
	<link rel='dns-prefetch' href='//s.w.org' />	
	
	<!-- Mapbox code -->
	<script src="https://api.mapbox.com/mapbox-gl-js/v1.12.0/mapbox-gl.js"></script>
	<link href="https://api.mapbox.com/mapbox-gl-js/v1.12.0/mapbox-gl.css" rel="stylesheet" />

	<!-- Local scripts -->
	<!-- Local scripts -->
	<script src="//ajax.googleapis.com/ajax/libs/jquery/3.1.1/jquery.min.js"></script>
	<script src="//ajax.googleapis.com/ajax/libs/jqueryui/1.12.1/jquery-ui.min.js"></script>
	
	<script>
		var mapLat = 33.947;
		var mapLon = -77.9675;
		var mapZoom= 12;
		
		var imgfolder = "cherrybranch/";
		var fnprefix = "_";
		var firstData = new Date(2019, 6 -1, 01);
		//var lastData = new Date(2017, 7 -1, 26); // removing to allow new deployment
	</script>

	<script src="ferrydata.js"></script>
	<!-- End Local scripts -->
	<!-- End Local scripts -->

	
	<!-- Begin Custom CSS -->
	<!-- Begin Custom CSS -->
	<link rel="stylesheet" href="ferryweb.css">

	<style type="text/css">
	</style>	<!-- End Custom CSS -->
				<!-- End Custom CSS -->
</head>


<body class="home page" onload="on_page_load()">


<div >

<header>
	<h2>Southport to Fort Fisher</h2>
	<i><b>FerryMon:</b></i> <a href="http://wave.ims.unc.edu/FerryMon/Southport2fortFisher_ferry_monitor.php">http://wave.ims.unc.edu/FerryMon/Southport2fortFisher_ferry_monitor.php</a> 
	</header>
	<hr>
		
	<div id="data"><h3>Most Recent Observations</h3></div>

	<div id="map"></div>
			
	<div id="webcam" style="float:left">
		<h3>Most Recent Web Cam Image</h3>
		<img src="webcam_cherrybranch" alt="webcam image" width="100%"max-width="100%">
	</div>
	
	<?php
		$dbname="cherrybranch";
		$numgps=400;
		include 'ferrydata.php';
	?>
	    
</div>

</body>
</html>
