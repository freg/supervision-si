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
 * Move task (from before to)
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/tool/movePlanningColumn.php');
if (! pq_array_key_exists('orderedList',$_REQUEST)) {
  throwError('orderedList parameter not found in REQUEST');
}
$list=RequestHandler::getValue('orderedList');
$objectClass = RequestHandler::getValue('objectClass');
if(!$objectClass)$objectClass='Planning';

$arrayList=pq_explode("|", $list);
$user=getSessionUser();
Sql::beginTransaction();
$sortedArray = array();
$sortOrder = 1;
foreach ($arrayList as $order=>$col) {
  $field = pq_trim($col);
  if(pq_strpos($field, 'hidden') === false){
    $sortedArray[$sortOrder]=$col;
    unset($arrayList[$order]);
    $sortOrder++;
  }
}
$sortedArray = array_merge($sortedArray, $arrayList);
foreach ($sortedArray as $order=>$col) {
	$field = pq_trim($col);
	$hidden=false;
	if(pq_strpos($field, 'hidden') !== false){
	  $hidden=true;
	  $field = pq_str_replace('hidden', '', $field);
	}
	if ($field) {
	  $col=Security::checkValidField($field);
  	//$critArray=array('idUser'=>$user->id, 'parameterCode'=>'planningColumnOrder'.$col);
  	//$param=SqlElement::getSingleSqlElementFromCriteria('Parameter', $critArray);
  	//$param->parameterValue=$order+1;
      $column = SqlElement::getSingleSqlElementFromCriteria('ColumnSelector', array('idUser'=>$user->id,'objectClass'=>$objectClass,'field'=>$field));
      $column->sortOrder = $order;
      $column->name = $field;
      $column->attribute = $field;
      $column->scope = 'list';
      $column->hidden = ($hidden)?'1':'0';
      $result=$column->save();
	}
}

displayLastOperationStatus($result);
?>