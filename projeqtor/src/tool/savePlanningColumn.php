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
 * Save some information about planning columns status.
 */
require_once "../tool/projeqtor.php";

$user=getSessionUser();


$action = RequestHandler::getValue('action');
$item= RequestHandler::getField('item');
$objectClass = RequestHandler::getValue('objectClass');
if(!$objectClass)$objectClass='Planning';
$planningType = RequestHandler::getValue('planningType');

Sql::beginTransaction();
if ($action=='status') {
  $column = SqlElement::getSingleSqlElementFromCriteria('ColumnSelector', array('idUser'=>$user->id,'objectClass'=>$objectClass,'field'=>$item));
  $status = RequestHandler::getAlphanumeric('status');
  //$crit=array('idUser'=>$user->id, 'idProject'=>null, 'parameterCode'=>'planningHideColumn'.$item);
  //$param=SqlElement::getSingleSqlElementFromCriteria('Parameter', $crit);
  if ($column and $column->id) {
  	if ($status=='hidden') {
  	  $column->hidden='1';
	  $column->save();
  	} else {
//   	  $column->delete();
  	  $column->hidden='0';
  	  $column->save();
  	}
  } else {
  	if ($status=='hidden') {
  		$col=new ColumnSelector();
  		$col->objectClass = $objectClass;
  		$col->idUser=$user->id;
  		$col->field=$item;
  		$col->attribute = $col->field;
  		$col->name = $col->field;
  		$col->hidden='1';
  		$col->save();
  	}
  }
} else if ($action=='reset') {
  $clause="objectClass='$objectClass' and idUser=$user->id ";
  $columnSelector=new ColumnSelector();
  $resPurge=$columnSelector->purge($clause);
  $desc=Parameter::getPlanningColumnDescription($planningType);
  foreach ($desc as $col=>$attribute){
    if($attribute['defaultShow']==0){
      $cs=new ColumnSelector();
      $cs->objectClass=$objectClass;
      $cs->idUser=$user->id;
      $cs->field=$col;
      $cs->attribute=$col;
      $cs->name=$attribute['name'];
      $cs->hidden='1';
      $cs->widthPct=$attribute['width'];
      $cs->save();
    }
  }
} else if ($action=='width') {
  $column = SqlElement::getSingleSqlElementFromCriteria('ColumnSelector', array('idUser'=>$user->id,'objectClass'=>$objectClass,'field'=>$item));
  $width= RequestHandler::getAlphanumeric('width');
  //$crit=array('idUser'=>$user->id, 'idProject'=>null, 'parameterCode'=>'planningColumnWidth'.$item);
  //$param=SqlElement::getSingleSqlElementFromCriteria('Parameter', $crit);
  $column->widthPct=intval($width);
  $column->name = $column->field;
  $column->scope = 'list';
  $column->save();
}
Sql::commitTransaction();
?>