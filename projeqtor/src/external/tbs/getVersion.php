<?php
function tbsGetVersion() {
	$file=file_get_contents(__DIR__."/tbs_class.php");
	$deb=strpos($file,'@version');
	$fin=strpos($file,"for PHP",$deb+1);
	$msg=substr($file,$deb,$fin-$deb);
	$split=explode(' ',$msg);
	$version=$split[1];
	$version=trim($version);
	return $version;
}