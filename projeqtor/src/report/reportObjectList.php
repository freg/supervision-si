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

// Header
include_once '../tool/projeqtor.php';
include_once '../tool/formatter.php';

$user = getSessionUser();

$reportLayoutId = RequestHandler::getId('reportLayoutId');
$reportLayout = new ReportLayout($reportLayoutId);

$objectClass = $reportLayout->objectClass;
$obj=new $objectClass();

$directFilterArray = json_decode($reportLayout->directFilter);
foreach ($directFilterArray as $key=>$value){
  $_REQUEST[$key]=$value;
}

if(pq_array_key_exists('outMode', $_REQUEST) and $_REQUEST['outMode'] == 'csv'){
  $crit=array("objectClass"=>$objectClass, "idLayout"=>$reportLayoutId, "idUser"=>$reportLayout->idUser, 'isReportList'=>'1');
  $layoutCS = new LayoutColumnSelector();
  $layoutCSList = $layoutCS->getSqlElementsFromCriteria($crit);
  $hiddenFields['CatalogUO']=1;
  foreach ($layoutCSList as $layoutCS){
    $hiddenFields[$layoutCS->attribute]=$layoutCS->hidden;
  }
  $fieldsArray=$obj->getFieldsArray(true);
  if ((isset($fieldsArray['_sec_description']) or isset($fieldsArray['_sec_Description'])) and $objectClass!='Work')  $fieldsArray = array('_sec_description' => '_sec_description') + array('hyperlink' => 'Hyperlink') + $fieldsArray;
  else $fieldsArray = array('_sec_Description' => '_sec_description') + $fieldsArray;
  foreach($fieldsArray as $key => $val) {
    if (pq_substr($val,0,1)=='_') {
      unset($fieldsArray[$key]);
      continue;
    }
    if(isset($fieldsArray[$key]) and pq_substr($fieldsArray[$key],0,1)=="["){
      unset($fieldsArray[$key]);
      continue;
    }
    if(!isset($hiddenFields[$val])){
      $hiddenFields[$key]=1;
    }
  }
  foreach ($hiddenFields as $field=>$hidden){
    if($hidden == 0){
      unset($hiddenFields[$field]);
      continue;
    }else{
      $hiddenFields[$field]=$field;
    }
  }
  $_REQUEST['hiddenFields']=implode(';', $hiddenFields);
}

$_REQUEST['print']=true;
$_REQUEST['reportName'] = $reportLayout->scope;
$_REQUEST['objectClass']=$objectClass;

// Header
$paramProject=pq_trim(RequestHandler::getId('idProject'));
$_REQUEST['objectProject'] = ($paramProject != '')?$paramProject:'*';
$paramResource=pq_trim(RequestHandler::getId('responsible'));
$_REQUEST['objectResource'] = ($paramResource != '')?$paramResource:'';
$paramOrganization=pq_trim(RequestHandler::getId('idOrganization'));
$_REQUEST['objectOrganization'] = ($paramOrganization != '')?$paramOrganization:'';
$paramTeam=pq_trim(RequestHandler::getId('idTeam'));
$_REQUEST['objectTeam'] = ($paramTeam != '')?$paramTeam:'';
$paramType=pq_trim(RequestHandler::getId($obj->getTypeName($objectClass)));
$_REQUEST['objectType'] = ($paramType != '')?$paramType:'';

$headerParameters="";
if ($paramProject!="") {
  $headerParameters.= i18n("colIdProject") . ' : ' . htmlEncode(SqlList::getNameFromId('Project', $paramProject)) . '<br/>';
}
if ($paramResource!="") {
  $headerParameters.= i18n("colResponsible") . ' : ' . htmlEncode(SqlList::getNameFromId('Affectable', $paramResource)) . '<br/>';
}
if ($paramOrganization!="") {
  $headerParameters.= i18n("colIdOrganization") . ' : ' . htmlEncode(SqlList::getNameFromId('Organization', $paramOrganization)) . '<br/>';
}
if ($paramTeam!="") {
  $headerParameters.= i18n("colIdTeam") . ' : ' . htmlEncode(SqlList::getNameFromId('Team', $paramTeam)) . '<br/>';
}
if ($paramType!="") {
  $headerParameters.= i18n("col".ucfirst($obj->getTypeName($objectClass))) . ' : ' . htmlEncode(SqlList::getNameFromId($obj->getTypeClassName($objectClass), $paramType)) . '<br/>';
}

$arrayFilter=array();
if($reportLayout->idFilter){
  $idFilterCriteriaList = SqlList::getListWithCrit('FilterCriteria', array('idFilter'=>$reportLayout->idFilter), 'id');
}else{
  $idFilterCriteriaList = SqlList::getListWithCrit('FilterCriteria', array('idFilter'=>$reportLayout->id, 'isReportList'=>'1'), 'id');
}
foreach ($idFilterCriteriaList as $idFilterCriteria){
  $arrayDisp=array();
  $arraySql=array();
  $filterCriteria = new FilterCriteria($idFilterCriteria);
  $arrayDisp["attribute"]=$filterCriteria->dispAttribute;
  $arrayDisp["operator"]=$filterCriteria->dispOperator;
  $arrayDisp["value"]=$filterCriteria->dispValue;
  $arraySql["attribute"]=$filterCriteria->sqlAttribute;
  $arraySql["operator"]=$filterCriteria->sqlOperator;
  $arraySql["value"]=$filterCriteria->sqlValue;
  $orOperator=$filterCriteria->orOperator;
  $arrayFilter[]=array("disp"=>$arrayDisp,"sql"=>$arraySql,"orOperator"=>$orOperator);
}

$headerFilters="";
$nbFilters=0;
foreach ($arrayFilter as $filter){
  if (!isset($filter['orOperator'])) $filter['orOperator']=0;
  if (!isset($filter['isDynamic'])) $filter['isDynamic']=0;
  if ($filter['orOperator']=='1') {
    $headerFilters.=i18n('OR').' ';
  }
  elseif ($nbFilters==0) { //Nothing is displayed on the first criteria
    $nbFilters+=1;
  }
  else {
    $headerFilters.=i18n('AND').' ';
  }
  $headerFilters.= $filter['disp']['attribute'] . " " .$filter['disp']['operator'] . " " .
                      ($filter['isDynamic']=="1" ? '{'.i18n('dynamicValue').'}' : $filter['disp']['value']).'<br/>';
}

if (pq_array_key_exists('outMode', $_REQUEST) and $_REQUEST['outMode'] == 'csv') {
  include_once "headerFunctions.php";
} else {
  include "header.php";
}

?>
<?php if(pq_array_key_exists('outMode', $_REQUEST) and $_REQUEST['outMode'] != 'csv' and $_REQUEST['outMode'] != 'excel'){?>
<table align="center" style="width:95%;">
    <tr>
      <td>
      <?php }?>
        <?php include '../tool/jsonQuery.php';?>
      <?php if(pq_array_key_exists('outMode', $_REQUEST) and $_REQUEST['outMode'] != 'csv' and $_REQUEST['outMode'] != 'excel'){?>
      </td>
    </tr>
  </table>
<?php }?>