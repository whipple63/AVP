// avp data scripts display a table of recent data, a clickable calendar
// and current and archived data images

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
