	$( function(){

			
		// let's try photoswipe
//		openPhotoswipe();		
						
	   var div = document.getElementById("first_data");
		var firstData = div.textContent;
	
	   div = document.getElementById("last_data");
		var lastData = div.textContent;
		
		firstData = new Date(parseInt(firstData.substr(0,4)), parseInt(firstData.substr(4,2)) - 1, parseInt(firstData.substr(6,2)));	
		lastData = new Date(parseInt(lastData.substr(0,4)), parseInt(lastData.substr(4,2)) - 1, parseInt(lastData.substr(6,2)));		
		
		$('#archive_cal').datepicker({
			minDate: firstData,
			maxDate: lastData,
			changeMonth: true,
			changeYear: true,
			onSelect: function(dateText, inst) { 
				var myurl = window.location.href.split('?')[0];
				window.location.href = myurl+"?idate=" +
					dateText.substr(6,4) + dateText.substr(0,2) + dateText.substr(3,2); 
			}
		});
	
		// Construct a date string for the title
		var td = getParameterByName('idate');
		var t;
		if ( td===null || td=="" ) {
			t= new Date();
		} else {
			t= new Date(parseInt(td.substr(0,4)), parseInt(td.substr(4,2))-1, parseInt(td.substr(6,2)));
		}
		document.getElementById("dateTitle").innerHTML = t.toDateString();
		$('#archive_cal').datepicker( "setDate", t );
	});
	
	// utility fn from internet...
	function getParameterByName(name, url) {
	    if (!url) url = window.location.href;
	    name = name.replace(/[\[\]]/g, "\\$&");
	    var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
	        results = regex.exec(url);
	    if (!results) return null;
	    if (!results[2]) return '';
	    return decodeURIComponent(results[2].replace(/\+/g, " "));
	}


	//
	// Set up to use photoswipe
	//
	function openPhotoswipe(image_ix) {
		var pswpElement = document.querySelectorAll('.pswp')[0];
		
		// build items array (this version comes from the demo)
		// Create the items array in the php code and copy in here...
		var div = document.getElementById("pswp_data");
		var items = JSON.parse(div.textContent);

		// define options (if needed)
		var options = {
			 loop: false,
			 showHideOpacity: true,
		    index: parseInt(image_ix)
		};
		
		// Initializes and opens PhotoSwipe
		var gallery = new PhotoSwipe( pswpElement, PhotoSwipeUI_Default, items, options);
		gallery.init();
		gallery.ui.update();
	}
	//
	// end of photoswipe init
	//		
