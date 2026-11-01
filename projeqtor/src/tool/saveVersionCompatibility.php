<?php
/*
 *	@author: qCazelles 
 */
require_once "../tool/projeqtor.php";

if (! pq_array_key_exists('versionCompatibilityObjectClass',$_REQUEST)) {
	throwError('versionCompatibilityObjectClass parameter not found in REQUEST');
}
$objectClass=$_REQUEST['versionCompatibilityObjectClass'];
Security::checkValidClass($objectClass);

if (! pq_array_key_exists('versionCompatibilityObjectId',$_REQUEST)) {
	throwError('versionCompatibilityObjectId parameter not found in REQUEST');
}
$objectId=$_REQUEST['versionCompatibilityObjectId'];
Security::checkValidId($objectId);

if (! pq_array_key_exists('versionCompatibilityListClass',$_REQUEST)) {
	throwError('versionCompatibilityListClass parameter not found in REQUEST');
}
$listClass=$_REQUEST['versionCompatibilityListClass'];
Security::checkValidClass($listClass);

if (! pq_array_key_exists('versionCompatibilityListId',$_REQUEST)) {
	throwError('versionCompatibilityListId parameter not found in REQUEST');
}
$listId=$_REQUEST['versionCompatibilityListId'];

$comment="";
if (pq_array_key_exists('versionCompatibilityComment',$_REQUEST)) {
	$comment=$_REQUEST['versionCompatibilityComment'];
}

$arrayId=array();
if (is_array($listId)) {
	$arrayId=$listId;
} else {
	$arrayId[]=$listId;
}
Sql::beginTransaction();

$result="";
// get the modifications (from request)
foreach ($arrayId as $id) {
	$str=new VersionCompatibility();
	$str->idVersionA=$objectId;
	$str->idVersionB=$id;
	$str->comment=$comment;
	$str->idUser=$user->id;
	$str->creationDate=date("Y-m-d");
	$res=$str->save();
	if (!$result) {
		$result=$res;
	} else if (pq_stripos($res,'id="lastOperationStatus" value="OK"')>0 ) {
		if (pq_stripos($result,'id="lastOperationStatus" value="OK"')>0 ) {
			$deb=pq_stripos($res,'#');
			$fin=pq_stripos($res,' ',$deb);
			$resId=pq_substr($res,$deb, $fin-$deb);
			$deb=pq_stripos($result,'#');
			$fin=pq_stripos($result,' ',$deb);
			$result=pq_substr($result, 0, $fin).','.$resId.pq_substr($result,$fin);
		} else {
			$result=$res;
		}
	}
}
// Message of correct saving
displayLastOperationStatus($result);
?>