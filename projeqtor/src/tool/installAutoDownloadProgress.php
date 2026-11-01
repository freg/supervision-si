<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
******************************************************************************
*** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
******************************************************************************
*
* Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
*
* This file is an add-on to ProjeQtOr, packaged as a plug-in module.
* It is NOT distributed under an open source license.
* It is distributed in a proprietary mode, only to the customer who bought
* corresponding licence.
* The company ProjeQtOr remains owner of all add-ons it delivers.
* Any change to an add-ons without the explicit agreement of the company
* ProjeQtOr is prohibited.
* The diffusion (or any kind if distribution) of an add-on is prohibited.
* Violators will be prosecuted.
*
*** DO NOT REMOVE THIS NOTICE ************************************************/

//chdir('../');
require_once "../tool/projeqtor.php";
require_once "installAutoZipList.php";

$listFile=installAutoGetZipListTmp();
$jsonList=json_decode(getRemoteFile("https://projeqtor.org/admin/getInstallableVersions.php?currentVersion=".Sql::getDbVersion()),true);
$arrayToSend=array();
foreach ($listFile as $id=>$val){
	$split1=explode(".zip", $val['name']);
	$split2=explode("projeqtor",$split1[0]);
  $version=$split2[1];
  $valArrayTmp=array();
  if (isset($jsonList[$version]) and isset($jsonList[$version]['size']) and $jsonList[$version]['size']>0) {
    $valArrayTmp['val']=$val['size']/$jsonList[$version]['size']*100;
    $valArrayTmp['name']=$val['name'];
    $arrayToSend[]=$valArrayTmp;
  }
}
if(count($arrayToSend)!=0){
  echo json_encode($arrayToSend);
}else{
  echo 'empty';
}
?>