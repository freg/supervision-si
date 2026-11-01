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

$maintenance=true;
//chdir ( "../" );
require_once '../tool/projeqtor.php';
require_once "../db/maintenanceFunctions.php";
require_once "installAutoZipList.php";
/*if (securityGetAccessRightYesNo('menuPlgInstallAuto','read')!='YES') {
  traceHack ( "installAuto tried access without access right" );
  exit ();
}*/

$oneFile=null;
if (isset($_REQUEST['file']) ) {
  $oneFile=urldecode($_REQUEST['file']);
  $oneFile=Security::checkValidFileName($oneFile);
}
$user=getSessionUser();
$profile=new Profile($user->idProfile);
if ($profile->profileCode!='ADM') {
  echo 'Call to installAutoDelete.php for non Admin user.<br/>This action and your IP has been traced.';
  traceHack('Call to installAutoDelete.php for non Admin user');
	exit;
}

Sql::$maintenanceMode=true;
$files=installAutoGetZipList($oneFile);
$result="";
foreach ($files as $file) {
  if (@kill($file['path'])) {
    echo 'OK';
  } else {
    echo i18n("installAutoErrorDelete");
  }
  
}
