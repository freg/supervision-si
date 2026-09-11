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
 * Save a layout : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";
Sql::beginTransaction();
$user=getSessionUser();

if (! $user->_arrayLayouts) {
  $user->_arrayLayouts=array();
}

// Get the layout info
if (! pq_array_key_exists('layoutObjectClass',$_REQUEST)) {
  throwError('layoutObjectClass parameter not found in REQUEST');
}
$layoutObjectClass=$_REQUEST['layoutObjectClass'];
$objectClass=$layoutObjectClass;

// Get existing layout info
if (pq_array_key_exists($layoutObjectClass,$user->_arrayLayouts)) {
  $layoutArray=$user->_arrayLayouts[$layoutObjectClass];
} else {
  $layoutArray=array();
}
$colArray=array();
if(count($layoutArray)>0){
  $isShared = SqlList::getFieldFromId('Layout', $layoutArray['id'], 'isShared');
  //$idUser = (!$isShared)?$user->id:SqlList::getFieldFromId('Layout', $layoutArray['id'], 'idUser');
  //$crit=array("idLayout"=>$layoutArray['id'] ,"objectClass"=>$objectClass, "idUser"=>$idUser);
  $crit=array("idLayout"=>$layoutArray['id'] ,"objectClass"=>$objectClass, 'isReportList'=>'0');
  $layoutColumnSelector=new LayoutColumnSelector();
  $layoutColumnSelectorList = $layoutColumnSelector->getSqlElementsFromCriteria($crit);
  if(pq_strpos($objectClass, 'Planning') < 0){
    foreach ($layoutColumnSelectorList as $cls){
      $crit=array("objectClass"=>$objectClass , "idUser"=>$user->id, "field"=>$cls->field);
      $cs=ColumnSelector::getSingleSqlElementFromCriteria('ColumnSelector', $crit);
      $colArray[]="$cls->field,$cls->widthPct";
      $cs->scope = $cls->scope;
      $cs->objectClass = $cls->objectClass;
      $cs->idUser = $user->id;
      $cs->field = $cls->field;
      $cs->attribute = $cls->attribute;
      $cs->sortOrder = $cls->sortOrder;
      $cs->widthPct = $cls->widthPct;
      $cs->name = $cls->name;
      $cs->subItem = $cls->subItem;
      $cs->formatter = $cls->formatter;
      $cs->hidden=$cls->hidden;
      $cs->save();
    }
  }else{
    $columnSelector=new ColumnSelector();
    $crit=array("objectClass"=>$objectClass , "idUser"=>$user->id);
    $columnSelectorList = $columnSelector->getSqlElementsFromCriteria($crit);
    foreach ($columnSelectorList as $column){
      $column->delete();
    }
    foreach ($layoutColumnSelectorList as $cls){
      $cs = new ColumnSelector();
      $colArray[]="$cls->field,$cls->widthPct";
      $cs->scope = $cls->scope;
      $cs->objectClass = $cls->objectClass;
      $cs->idUser = $user->id;
      $cs->field = $cls->field;
      $cs->attribute = $cls->attribute;
      $cs->sortOrder = $cls->sortOrder;
      $cs->widthPct = $cls->widthPct;
      $cs->name = $cls->name;
      $cs->subItem = $cls->subItem;
      $cs->formatter = $cls->formatter;
      $cs->hidden=$cls->hidden;
      $cs->save();
    }
  }
  $colArray = implode('#', $colArray);
  echo $colArray;
}
Sql::commitTransaction();
setSessionUser($user);
?>