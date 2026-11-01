<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

require_once "../tool/projeqtor.php";

$method = RequestHandler::getValue('method');
if($method == 'manual'){
  $code = RequestHandler::getValue('subscribeCodeInput');
}else{
  $code = Parameter::getGlobalParameter('subscriptionCode');
}
$hostedParam=Parameter::getGlobalParameter('hosted');
if ($hostedParam and ($hostedParam==true or $hostedParam=='dedicated')) $code='hosted';
$codeResultArray=array('result'=>'KO', 'resultMessage'=>i18n('messageMandatory',array(i18n("subscriptionCode"))));
if($code){
  if (serverCanAccessRemoteServer()) {
    $mac=System::getUniqueCode();
    $revision=Parameter::getGlobalParameter('lastRevisionInstalled'); 
    $jsonFile=RevisionUpdate::getRemoteFile("https://subscription.projeqtor.org/checkCode.php",$code);
    $codeResultArray=json_decode($jsonFile,true);
  } else {
    if (System::verifyNoRemoteAccessCode($code)) {
      $codeResultArray=array('result'=>'OK', 'resultMessage'=>i18n('colAccepted'));
    } else {
      $codeResultArray=array('result'=>'KO', 'resultMessage'=>i18n('messageInvalidControls'));
    }
  }
}
if(is_array($codeResultArray) and count($codeResultArray) > 0){
  if($codeResultArray['result'] == 'OK'){
    Parameter::storeGlobalParameter('subscriptionCode', $code);
  }else{
    Parameter::storeGlobalParameter('subscriptionCode', '');
  }
  Parameter::storeGlobalParameter('subscriptionCodeStatus', $codeResultArray['result']);
  if($method == 'manual'){
    displayOKKOStatus($codeResultArray['result'], $codeResultArray['resultMessage']);
  }else{
    echo $codeResultArray['result'];
  }
} else {
  if($method == 'manual')displayOKKOStatus("ERROR", "INVALID RESPONSE FOR SUBSCRIPTION CHECK<br/><br/>".$jsonFile);
}