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

/** ============================================================================
 * Save Today displayed info list
 */
require_once "../tool/projeqtor.php";
Sql::beginTransaction();
$user=getSessionUser();
$objectClass=(RequestHandler::isCodeSet('refType'))?RequestHandler::getValue('refType'):false;
$objectId=(RequestHandler::isCodeSet('refId'))?RequestHandler::getId('refId'):false;

if($objectClass==false or $objectId==false) exit ;
$obj=new $objectClass($objectId);
if(!securityGetAccessRightYesNo('menu'.$objectClass,'update',$obj) or securityGetAccessRightYesNo('menu'.$objectClass,'update',$obj)!='YES') {
  traceHack("saveSubTaskOrder.php called for $objectClass #$objectId but user has not write access to this item");
  exit;
}
$subTask= new SubTask();
$critArray=array("refType"=>$objectClass,"refId"=>$objectId);
$elment=$subTask->getSqlElementsFromCriteria($critArray,null,null,'sortOrder');

foreach ($elment as $item) {
  
	if (isset($_REQUEST[$objectClass.'_'.$objectId.'_'.$item->id])) {
		$item->sortOrder=$_REQUEST[$objectClass.'_'.$objectId.'_'.$item->id];
		$item->save();
	}
}
Sql::commitTransaction();
?>