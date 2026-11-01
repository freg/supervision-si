<?php
/*
 * @author: qCazelles 
 */

require_once "../tool/projeqtor.php";

$versionCompatibilityId=null;
if (pq_array_key_exists('versionCompatibilityId',$_REQUEST)) {
	$versionCompatibilityId=$_REQUEST['versionCompatibilityId'];
	Security::checkValidId($versionCompatibilityId);
}
$versionCompatibilityId=pq_trim($versionCompatibilityId);
if ($versionCompatibilityId=='') {
	$versionCompatibilityId=null;
}
if ($versionCompatibilityId==null) {
	throwError('versionCompability id parameter not found in REQUEST');
}
Sql::beginTransaction();
$obj=new VersionCompatibility($versionCompatibilityId);
$result=$obj->delete();

// Message of correct saving
displayLastOperationStatus($result);
?>