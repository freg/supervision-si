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
/** ===========================================================================
 * Get value of the User Pram for dynamique dialog copy to 
 */
require_once "../tool/projeqtor.php";

$lstParam=(RequestHandler::isCodeSet('parameters'))?RequestHandler::getValue('parameters'):false;
$lstParamName=(RequestHandler::isCodeSet('parametersName'))?RequestHandler::getValue('parametersName'):false;
$objectClass=(RequestHandler::isCodeSet('objectClass'))?RequestHandler::getClass('objectClass'):false;
$idType=(RequestHandler::isCodeSet('idType'))?RequestHandler::getId('idType'):false;
if(!$lstParam or !$lstParamName or !$objectClass){
  traceHack('Direct acces to this file rejected');
  exit;
}


echo '{"identifier":"id",';
echo '"label": "name",';
echo ' "items":[';
$lstParam=pq_explode(",", $lstParam);
$lstParamName=pq_explode(",", $lstParamName);
$values=array();
$cp=1;
$count=count($lstParam);
foreach ($lstParam as $id=>$pram){
  $val=(Parameter::getUserParameter($pram.$objectClass.$idType))?Parameter::getUserParameter($pram.$objectClass.$idType):Parameter::getUserParameter($pram.$objectClass);
  $values[$lstParamName[$id]]=pq_trim($val);
  if($cp!=$count)echo '{"id":"'.$lstParamName[$id].'", "value":"'.$val.'"},';
  else echo '{"id":"'.$lstParamName[$id].'", "value":"'.$val.'"}';
  $cp++;
}
echo ' ] }';

