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

//chdir ( "../" );
require_once '../tool/projeqtor.php';
if (!securityCheckDisplayMenu(null, 'PlgInstallAuto')) {
  traceHack ( "installAuto tried access without access right" );
  exit ();
}
$proxy=RequestHandler::getValue('installAutoProxyHost');
$user=RequestHandler::getValue('installAutoProxyUser');
$pass=RequestHandler::getValue('installAutoProxyPass');
Parameter::storeGlobalParameter('paramProxy', $proxy);
Parameter::storeGlobalParameter('paramProxyUser', $user);
Parameter::storeGlobalParameter('paramProxyPassword', $pass);
Parameter::clearGlobalParameters();

$returnValue = '<input type="hidden" id="lastSaveId" value="" />';
$returnValue .= '<input type="hidden" id="lastOperation" value="update" />';
$returnValue .= '<input type="hidden" id="lastOperationStatus" value="OK" />';
$returnValue .= i18n('messageParametersSaved');
echo '<div class="messageOK" >' . $returnValue . '</div>';