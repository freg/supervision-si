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

if (! $comboDetail and ! $user->_arrayReportLayouts) {
  $user->_arrayReportLayouts=array();
}

// Get the layout info
if (! pq_array_key_exists('reportLayoutObjectClass',$_REQUEST)) {
  throwError('reportLayoutObjectClass parameter not found in REQUEST');
}
$reportLayoutObjectClass=$_REQUEST['reportLayoutObjectClass'];
$objectClass=$reportLayoutObjectClass;

// Get existing layout info
if (!$comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
  $reportLayoutArray=$user->_arrayReportLayouts[$reportLayoutObjectClass];
} else {
  $reportLayoutArray=array();
}
$comment = RequestHandler::getValue('reportLayoutComment');
$directFilterList = RequestHandler::getValue('directFilterList');

$name="";
if (pq_array_key_exists('reportLayoutName',$_REQUEST)) {
  $name=$_REQUEST['reportLayoutName'];
  $name = pq_mb_substr($name,0,100,'UTF-8');
}
$currentReportLayout="";

Sql::beginTransaction();
pq_trim($name);
if (! $name) {
  echo htmlGetErrorMessage((i18n("messageMandatory", array(i18n("reportLayoutName")))));
  return;
} else {
  $crit=array("objectClass"=>$objectClass, "scope"=>$name, "idUser"=>$user->id);
  $reportLayout=ReportLayout::getSingleSqlElementFromCriteria('ReportLayout',$crit);
  $new = false;
  if(!$reportLayout->id){
    $new = true;
    $reportLayout->scope=$name;
    $reportLayout->idUser=$user->id;
    $reportLayout->isShared=0;
  }
  $reportLayout->comment=$comment;
  $reportLayout->directFilter = $directFilterList;
  if (! $comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayFilters)) {
    $filterName = $user->_arrayFilters[$reportLayoutObjectClass . "FilterName"];
    $idFilter = SqlList::getIdFromName('Filter', $filterName);
    if($idFilter){
      $reportLayout->idFilter=$idFilter;
    }else{
      $reportLayout->idFilter=null;
    }
    $crit=array("objectClass"=>$objectClass, "idUser"=>$user->id);
    $sortOrder = $reportLayout->getMaxValueFromCriteria('sortOrder', $crit)+1;
    $reportLayout->sortOrder = $sortOrder;
    $result = $reportLayout->save();
    $status=getLastOperationStatus($result);
    if($status=="OK" and !$idFilter){
      $arrayFilter = $user->_arrayFilters[$reportLayoutObjectClass];
      foreach ($arrayFilter as $filterCrit){
        $filterCriteria = new FilterCriteria();
        $filterCriteria->idFilter = $reportLayout->id;
        $filterCriteria->dispAttribute = $filterCrit['disp']['attribute'];
        $filterCriteria->dispOperator = $filterCrit['disp']['operator'];
        $filterCriteria->dispValue = $filterCrit['disp']['value'];
        $filterCriteria->sqlAttribute = $filterCrit['sql']['attribute'];
        $filterCriteria->sqlOperator = $filterCrit['sql']['operator'];
        $filterCriteria->sqlValue = $filterCrit['sql']['value'];
        $filterCriteria->isDynamic = $filterCrit['isDynamic'];
        $filterCriteria->orOperator = $filterCrit['orOperator'];
        $filterCriteria->isGroup = isset($filterCrit['isGroup']) ? $filterCrit['isGroup'] : 0;
        $filterCriteria->indentLevel = isset($filterCrit['indentLevel']) ? $filterCrit['indentLevel'] : 0;
        $filterCriteria->isReportList = '1';
        $filterCriteria->save();
      }
    }
  }else{
    $crit=array("objectClass"=>$objectClass, "idUser"=>$user->id);
    $sortOrder = $reportLayout->getMaxValueFromCriteria('sortOrder', $crit)+1;
    $reportLayout->sortOrder = $sortOrder;
    $result = $reportLayout->save();
    $status=getLastOperationStatus($result);
  }
  if ($status=="OK"){
    $columnSelector=new ColumnSelector();
    $columnSelectorList = $columnSelector->getSqlElementsFromCriteria($crit);
    $arrayColumn = array();
    foreach ($columnSelectorList as $column){
      if(!$new){
        $crit=array("objectClass"=>$objectClass, "idUser"=>$user->id, "idLayout"=>$reportLayout->id, "field"=>$column->field, 'isReportList'=>'1');
        $layoutColumnSelector=LayoutColumnSelector::getSingleSqlElementFromCriteria('LayoutColumnSelector',$crit);
      }else{
        $layoutColumnSelector= new LayoutColumnSelector();
      }
      $arrayColumn[$column->field]=$column->hidden;
      $layoutColumnSelector->idLayout = $reportLayout->id;
      $layoutColumnSelector->scope = 'list';
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
      $layoutColumnSelector->isReportList = '1';
      $layoutColumnSelector->save();
    }
    $crit=array("objectClass"=>$objectClass, "idUser"=>$user->id, "idLayout"=>$reportLayout->id, 'isReportList'=>'1');
    $layoutColumnSelector= new LayoutColumnSelector();
    $layoutColumnSelectorList=$layoutColumnSelector->getSqlElementsFromCriteria($crit);
    foreach ($layoutColumnSelectorList as $layoutColumnSelector){
      if(!isset($arrayColumn[$layoutColumnSelector->field]))$layoutColumnSelector->delete();
    }
    $reportLayoutArray=array("id"=>$reportLayout->id,"comment"=>$reportLayout->comment,"name"=>$reportLayout->scope);
    $user->_arrayReportLayouts[$reportLayoutObjectClass]=$reportLayoutArray;
    $user->_arrayReportLayouts[$reportLayoutObjectClass . "ReportLayoutName"]=$reportLayout->scope;
    if (! $comboDetail and pq_array_key_exists($reportLayoutObjectClass,$user->_arrayReportLayouts)) {
      $currentReportLayout=$user->_arrayReportLayouts[$reportLayoutObjectClass]['id'];
    }
    $reportList = Report::getSingleSqlElementFromCriteria('Report', array('name'=>$name, 'referTo'=>$reportLayoutObjectClass));
    $idReportCategory = SqlList::getIdFromName('ReportCategory', 'reportCategoryObjectList', true);
    if(!$reportList->id){
      $reportList = new Report();
      $reportList->name = $name;
      $reportList->idReportCategory = $idReportCategory;
      $reportList->file = 'reportObjectList.php?reportLayoutId='.$reportLayout->id;
      $reportList->sortOrder = intval($reportList->getMaxValueFromCriteria('sortOrder', array('idReportCategory'=>$idReportCategory))) + 10;
      $reportList->orientation = 'L';
      $reportList->hasCsv = 1;
      $reportList->hasView = 1;
      $reportList->hasPrint = 1;
      $reportList->hasPdf = 1;
      $reportList->hasToday = 1;
      $reportList->hasFavorite = 1;
      $reportList->hasExcel = 1;
      $reportList->referTo = $reportLayoutObjectClass;
      $reportList->save();
      
      $profile = new Profile();
      $profileList = $profile->getSqlElementsFromCriteria(null, null, "1=1");
      foreach ($profileList as $profile){
        HabilitationReport::$_skipRightControl = true;
        $habiReport = new HabilitationReport();
        $habiReport->idProfile = $profile->id;
        $habiReport->idReport = $reportList->id;
        $habiReport->allowAccess = 1;
        $habiReport->save();
        HabilitationReport::deleteDuplicate();
      }      
    }
  }
}

$reportLayout=new ReportLayout();
$crit=array('idUser'=> $user->id, 'objectClass'=>$objectClass );
$orderByReportLayout = "sortOrder ASC";
$reportLayoutList=$reportLayout->getSqlElementsFromCriteria($crit,false,null,$orderByReportLayout);;
htmlDisplayStoredReportLayout($reportLayoutList,$reportLayoutObjectClass, $currentReportLayout);
echo "<div id='saveReportLayoutResult' align='center' style='z-index:9;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px' >";
displayLastOperationStatus($result);
echo "</div>";
?>
