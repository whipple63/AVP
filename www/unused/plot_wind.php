<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
    <head>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
<title>Plot</title>
<script type="text/javascript" src="jscharts.js"></script>
<script type="text/javascript">
function on_page_load() {
	var myData = new Array([10, 20], [15, 10], [20, 30], [25, 10], [30, 5]);
	var myChart = new JSChart('chartcontainer', 'line');
	myChart.setDataArray(myData);
	myChart.draw();
}
</script>
<style type="text/css">
html, body { height:93%; }
body {
    margin: 5px;
    padding: 5px;
    cursor: auto;
}
</style>
</head>

<body onLoad="on_page_load()">
  <?
  $link = pg_Connect("host=avp3.dyndns.org dbname=avp user=postgres password=sonde");
  $result = pg_exec($link, "select time, speed_scalar from avp3_wind order by \"time\" desc limit 144 offset 0");
  $numrows = pg_numrows($result);
    echo "<wind>";
   // Loop on rows in the result set.
   for($ri = 0; $ri < $numrows; $ri++) {
    echo "<reading ";
    $row = pg_fetch_array($result, $ri);
    echo "time=\"", $row["time"], "\" ";
    echo "speed_scalar=\"", $row["speed_scalar"], "\" ";
    echo "/>\n";
   }
    echo "</wind>";
   pg_close($link);
  ?>


<div id="chartcontainer">This is just a replacement in case Javascript is not available or used for SEO purposes</div>

</body>
</html>
