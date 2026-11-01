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

$user=getSessionUser();

$comboDetail=false;
if (pq_array_key_exists('comboDetail',$_REQUEST)) {
  $comboDetail=true;
}

if (! $comboDetail and ! $user->_arrayLayouts) {
  $user->_arrayLayouts=array();
}

// Get the layout info
if (! pq_array_key_exists('layoutObjectClass',$_REQUEST)) {
  throwError('layoutObjectClass parameter not found in REQUEST');
}
$layoutObjectClass=$_REQUEST['layoutObjectClass'];
//if(pq_strpos($layoutObjectClass, 'Planning') !== false)$layoutObjectClass='Planning';
$objectClass=$layoutObjectClass;

// Get existing layout info
if (!$comboDetail and pq_array_key_exists($layoutObjectClass,$user->_arrayLayouts)) {
  $layoutArray=$user->_arrayLayouts[$layoutObjectClass];
} else {
  $layoutArray=array();
}
$comment = RequestHandler::getValue('layoutComment');

$name="";
if (pq_array_key_exists('layoutName',$_REQUEST)) {
  $name=$_REQUEST['layoutName'];
  $name = pq_mb_substr($name,0,100,'UTF-8');
}
Sql::beginTransaction();
pq_trim($name);
if (! $name) {
  echo htmlGetErrorMessage((i18n("messageMandatory", array(i18n("layoutName")))));
  return;
} else {
  $crit=array("objectClass"=>$objectClass, "scope"=>$name, "idUser"=>$user->id);
  $layout=Layout::getSingleSqlElementFromCriteria('Layout',$crit);
  if(!$layout->id){
    $layout->scope=$name;
    $layout->idUser=$user->id;
    $layout->isShared=0;
  }
  
  $layout->comment=$comment;
  $crit=array("objectClass"=>$objectClass, "idUser"=>$user->id);
  $sortOrder = $layout->getMaxValueFromCriteria('sortOrder', $crit)+1;
  $layout->sortOrder = $sortOrder;
  $result = $layout->save();
  $status=getLastOperationStatus($result);
  
  if ($status=="OK"){
    $columnSelector=new ColumnSelector();
    $columnSelectorList = $columnSelector->getSqlElementsFromCriteria($crit);
    $arrayColumn = array();
    foreach ($columnSelectorList as $column){
      if($layout->id){
        $crit=array("objectClass"=>$objectClass, "idUser"=>$user->id, "idLayout"=>$layout->id, "field"=>$column->field, 'isReportList'=>'0');
        $layoutColumnSelector=LayoutColumnSelector::getSingleSqlElementFromCriteria('LayoutColumnSelector',$crit);
      }else{
        $layoutColumnSelector= new LayoutColumnSelector();
      }
      $arrayColumn[$column->field]=$column->hidden;
      $layoutColumnSelector->idLayout = $layout->id;
      $layoutColumnSelector->scope = $column->scope;
      $layoutColumnSelector->objectClass = $column->objectClass;
      $layoutColumnSelector->idUser = $column->idUser;
      $layoutColumnSelector->field = $column->field;
      $layoutColumnSelector->attribute = $column->attribute;
      $layoutColumnSelector->hidden = $column->hidden;
      $layoutColumnSelector->sortOrder = $column->sortOrder;
      $layoutColumnSelector->widthPct = $column->widthPct;
      $layoutColumnSelector->name = $column->name;
      $layoutColumnSelector->subItem = $column->subItem;
      $layoutColumnSelector->formatter = $column->formatter;
      $layoutColumnSelector->save();
    }
    $crit=array("objectClass"=>$objectClass, "idUser"=>$user->id, "idLayout"=>$layout->id, 'isReportList'=>'0');
    $layoutColumnSelector= new LayoutColumnSelector();
    $layoutColumnSelectorList=$layoutColumnSelector->getSqlElementsFromCriteria($crit);
    foreach ($layoutColumnSelectorList as $layoutColumnSelector){
      if(!isset($arrayColumn[$layoutColumnSelector->field]))$layoutColumnSelector->delete();
    }
    $layoutArray=array("id"=>$layout->id,"comment"=>$layout->comment,"name"=>$layout->scope);
    $user->_arrayLayouts[$layoutObjectClass]=$layoutArray;
    $user->_arrayLayouts[$layoutObjectClass . "LayoutName"]=$layout->scope;
    $currentLayout="";
    if (! $comboDetail and pq_array_key_exists($layoutObjectClass,$user->_arrayLayouts)) {
      $currentLayout=$user->_arrayLayouts[$layoutObjectClass]['id'];
    }
  }
}

$lyt=new Layout();
$crit=array('idUser'=> $user->id, 'objectClass'=>$objectClass );
$orderByLayout = "sortOrder ASC";
$layoutList=$lyt->getSqlElementsFromCriteria($crit,false,null,$orderByLayout);;
htmlDisplayStoredLayout($layoutList,$layoutObjectClass, $currentLayout);
echo "<div id='saveLayoutResult' align='center' style='z-index:9;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
displayLastOperationStatus($result);
echo "</div>";
?>