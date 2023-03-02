// ferry data scripts display a table of recent data, a clickable calendar
// and current and archived data images

		function on_page_load() {	// Called when page loads.
			_appData = new AppData();
			_appData.load_wind();
			_appData.load_gps();
			_appData.load_flow();
			_appData.load_sonde();
			updateDataDisplay();
			updateMap();
//			updateProfileDisplay();
		}

		function on_page_unload() {  // Called when page unloads.
		}

		// Container object for all data as read from tags created in php code
		function AppData() {
			this.windReadings = new Array();
			this.gpsReadings = new Array();
			this.flowReadings = new Array();
			this.sondeReadings = new Array();
			
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
			
			this.load_flow = function() {
				var readings = document.getElementsByTagName('flow');
				if((readings == undefined) || (readings.length==0)) {
					alert("Failed to locate flow element");
					return;
				}
				for(var i=0; i < readings.length; i++) {
					var reading = readings[i];
					this.flowReadings.push(new FlowReading(reading));
				}
			}
			
			this.load_sonde = function() {
				var readings = document.getElementsByTagName('sonde');
				if((readings == undefined) || (readings.length==0)) {
					alert("Failed to locate sonde element");
					return;
				}
				for(var i=0; i < readings.length; i++) {
					var reading = readings[i];
					this.sondeReadings.push(new SondeReading(reading));
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
			this.speed = e.getAttribute('speed');
			this.track = e.getAttribute('track');
		}
		function FlowReading(e) {
			this.cast_time = e.getAttribute('cast_time');
			this.flow_rate = e.getAttribute('flow_rate');
		}
		function SondeReading(e) {
			this.sample_time = e.getAttribute('sample_time');
			this.tempc = e.getAttribute('tempc');
			this.salppt = e.getAttribute('salppt');
			this.dissolved_o2 = e.getAttribute('dissolved_o2');
			this.turbid = e.getAttribute('turbid');
			this.chl = e.getAttribute('chl');
			this.ph = e.getAttribute('ph');
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
			addRow(tbl, "Wind Speed",             Number(_appData.windReadings[0].speed_scalar * 1.943844492440605).toFixed(1) + " kts ("	
						+ Number(_appData.windReadings[0].speed_scalar * 2.23694).toFixed(1) + " mph)");
			addRow(tbl, "Wind Gust",              Number(_appData.windReadings[0].gust_speed * 1.943844492440605).toFixed(1) + " kts ("
						+ Number(_appData.windReadings[0].gust_speed * 2.23694).toFixed(1) + " mph)");
			
			addRow(tbl, "&nbsp", " ");
			
			addRow(tbl, "GPS Observation Time",   String(_appData.gpsReadings[0].sample_time).substr(0,19));
			var ldeg = Math.floor(_appData.gpsReadings[0].lat);
			var lmin = (_appData.gpsReadings[0].lat - Math.floor(_appData.gpsReadings[0].lat))*60;
			addRow(tbl, "Lat",            ldeg + " " + Number(lmin).toFixed(3) + " N" );
			ldeg = Math.floor(Math.abs(_appData.gpsReadings[0].lon));
			lmin = (Math.abs(_appData.gpsReadings[0].lon) - Math.floor(Math.abs(_appData.gpsReadings[0].lon)))*60;
			addRow(tbl, "Lon",            ldeg + " " + Number(lmin).toFixed(3) + " W" );
			
			addRow(tbl, "&nbsp", " ");
			
			addRow(tbl, "Flow Rate Observation Time", String(_appData.flowReadings[0].cast_time).substr(0,19));
			addRow(tbl, "Flow Rate",              Number(_appData.flowReadings[0].flow_rate).toFixed(1) + " l/min (Shows if water is flowing past our sensor)");
			if (_appData.flowReadings[0].flow_rate < 5) {
				addRow(tbl, "<b><font color=\"red\">Flow rate too slow</font></b>", "<b><font color=\"red\">Water Quality Data may be unreliable</font></b>");
			}
			addRow(tbl, "&nbsp", " ");
			
			addRow(tbl, "Water Observation Time", String(_appData.sondeReadings[0].sample_time).substr(0,19));
			addRow(tbl, "Water Temperature", Number(Number(_appData.sondeReadings[0].tempc) * 9.0/5.0 + 32.0).toFixed(1) + " deg F (" + _appData.sondeReadings[0].tempc + " deg C)");
			addRow(tbl, "Salinity", Number(_appData.sondeReadings[0].salppt) + " (fresh water = 0, ocean water = 35)");
			addRow(tbl, "Dissolved Oxygen", Number(_appData.sondeReadings[0].dissolved_o2) + " milligrams/l (Range: 0 to about 15)");
			addRow(tbl, "Turbidity", Number(_appData.sondeReadings[0].turbid) + " NTU (Low values for clearer water)");
			addRow(tbl, "Chlorophyll", Number(_appData.sondeReadings[0].chl) + " micrograms/l (>40 considered impaired)");
			addRow(tbl, "pH", Number(_appData.sondeReadings[0].ph) + " (normally 7-9)");
			
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

		function updateMap() {
			mapboxgl.accessToken = 'pk.eyJ1Ijoid2hpcHBsZTYzIiwiYSI6ImNqdmR1eGhmZjA3OG0zeXAxZ253dTIwZnoifQ.JORUFdmVMdId8aSTygV0Lg';
			var map = new mapboxgl.Map({
						container: 'map', // container id
						style: 'mapbox://styles/mapbox/streets-v11', // style URL
						center: [mapLon, mapLat], // starting position [lng, lat]
						zoom: mapZoom // starting zoom
						});

			for(var i=0; i < _appData.gpsReadings.length; i++) {
				var lat = _appData.gpsReadings[i].lat;
				var lon = _appData.gpsReadings[i].lon;
				new mapboxgl.Marker( {color: "#808080", scale: 0.2 } )
					.setLngLat([lon, lat])
					.addTo(map);
			}	
						
			var popup = new mapboxgl.Popup({ closeOnClick: false, anchor: 'left', offset: 20})
							.setLngLat([_appData.gpsReadings[0].lon, _appData.gpsReadings[0].lat])
							.setHTML("Speed: " + Number(_appData.gpsReadings[0].speed * 1.94384).toFixed(1) + " kts" +  
								     "<br>Course: " + Number(_appData.gpsReadings[0].track).toFixed(0))
							.addTo(map);
			var marker = new mapboxgl.Marker()
							.setLngLat([_appData.gpsReadings[0].lon, _appData.gpsReadings[0].lat])
							.setPopup(popup)
							.addTo(map);
			popup.addTo(map);

		}
		
		function updateProfileDisplay() {
			( function($) {
			$(document).ready(function(){

				if (typeof lastData == 'undefined') {
					lastData = new Date();
				}
								
				$('#profile_cal').datepicker({
					minDate: firstData,
					maxDate: lastData,
					changeMonth: true,
					changeYear: true,
					onSelect: function(dateText, inst) { drawProfilePlot(); }
				});
				$('#profile_cal').datepicker( "setDate", new Date() );
				drawProfilePlot();
				
				
			})
			} ) ( jQuery );
			;

			
		function drawProfilePlot() {
			var plotFile;
			var selDate = $('#profile_cal').datepicker( "getDate" );
			plotFile = imgfolder + fnprefix + selDate.getFullYear() + pad(selDate.getMonth()+1) + pad(selDate.getDate()) + ".png";
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
