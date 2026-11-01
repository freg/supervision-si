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
if(!pq_array_key_exists("installAutoVersion", $_REQUEST)){
  throwError ( 'Parameter installAutoVersion not found in REQUEST' );
}
$jsonList=json_decode(getRemoteFile("https://projeqtor.org/admin/getInstallableVersions.php?currentVersion=".Sql::getDbVersion()),true);
if(!isset($jsonList[$_REQUEST['installAutoVersion']]) || !isset($jsonList[$_REQUEST['installAutoVersion']]['url']))throwError ( 'Url not found in JSONList' );
$url=$jsonList[$_REQUEST['installAutoVersion']]['url'];
$file_path = "..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."tmp".DIRECTORY_SEPARATOR."projeqtor".$_REQUEST['installAutoVersion'].".zip";
projeqtor_set_time_limit(0);
ignore_user_abort(1);
error_reporting(0);
session_write_close();
$fileInfo = getFileInfo($url);
if($fileInfo['http_code'] == 200){
  if(fileDownload($url, $file_path)){
    enableCatchErrors();
    $renameResult=@rename($file_path, "..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."projeqtor".$_REQUEST['installAutoVersion'].".zip");
    disableCatchErrors();
    if ($renameResult) {
      echo "OK";
    } else {
      errorLog("file transfer issue : cannot rename ".$file_path. ' into '."..".DIRECTORY_SEPARATOR."files".DIRECTORY_SEPARATOR."version".DIRECTORY_SEPARATOR."projeqtor".$_REQUEST['installAutoVersion'].".zip");
      errorLog("Check access rights to target folder");
      echo i18n('installAutoErrorWrite');
    }
  }else{
    errorLog("file transfer issue : download not complete");
    kill ($file_path);
    echo i18n('installAutoErrorDownload').'<br/>(error code 200)';
  }
} else {
  errorLog("file transfer issue : return code ".$fileInfo['http_code']." instead of 200");
  errorLog($fileInfo);
  echo i18n('installAutoErrorDownload').'<br/>(error code '.$fileInfo['http_code'].')';
}


?>