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
 * Save a filter : call corresponding method in SqlElement Class
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";
$user=getSessionUser();

// $comboDetail=false;
// if (pq_array_key_exists('comboDetail',$_REQUEST)) {
//   $comboDetail=true;
// }
$comboDetail=RequestHandler::isCodeSet('comboDetail');
if (! $comboDetail and ! $user->_arrayFilters) {
  $user->_arrayFilters=array();
} else if ($comboDetail and ! $user->_arrayFiltersDetail) {
  $user->_arrayFiltersDetail=array();
}

// Get the filter info
// if (! pq_array_key_exists('filterObjectClass',$_REQUEST)) {
//   throwError('filterObjectClass parameter not found in REQUEST');
// }
//$filterObjectClass=$_REQUEST['filterObjectClass'];
$idFilterFromFavoriteProject = RequestHandler::getValue('idFilterFromFavoriteProject');
$filterObjectClass=RequestHandler::getClass('filterObjectClass',true);
$objectClass=($filterObjectClass=='Planning' or $filterObjectClass=='PlanningWorkPlan')?'PlanningElement':$filterObjectClass;
$objectClass=($objectClass=='VersionsPlanning' or $objectClass=='ResourcePlanning')?'Activity':$objectClass;
$objectClass=(pq_substr($objectClass,0,7)=='Report_')?pq_substr($objectClass,7):$objectClass;
$objectClass=$filterObjectClass=='ProjectDashboard'? 'Project':$objectClass;

// Get existing filter info
if (!$comboDetail and pq_array_key_exists($filterObjectClass,$user->_arrayFilters)) {
  $filterArray=$user->_arrayFilters[$filterObjectClass];
} else if ($comboDetail and pq_array_key_exists($filterObjectClass,$user->_arrayFiltersDetail)) {
  $filterArray=$user->_arrayFiltersDetail[$filterObjectClass];
} else {
  $filterArray=array();
}

$idLayout=RequestHandler::getId('filterLayout',false,null);
$name="";
if (pq_array_key_exists('filterName',$_REQUEST)) {
  $name=$_REQUEST['filterName'];
}
Sql::beginTransaction();
pq_trim($name);
if (! $name) {
  echo htmlGetErrorMessage((i18n("messageMandatory", array(i18n("filterName")))));
  return;
} else {
  $crit=array("refType"=>$objectClass, "name"=>$name, "idUser"=>$user->id);
  $filter=SqlElement::getSingleSqlElementFromCriteria("Filter", $crit);
  if (! $filter->id) {
    $filter->refType=$objectClass;
    $filter->name=$name;
    $filter->idUser=$user->id;
    $filter->isShared=0;
    //ADD qCazelles - Dynamic filter - Ticket #78
    $filter->isDynamic="0";
    //END ADD qCazelles - Dynamic filter - Ticket #78
    $filt = new Filter();
    $crit2 = $crit=array("refType"=>$objectClass, "idUser"=>$user->id);
    $sortOrder = ($filt->getMaxValueFromCriteria('sortOrder', $crit2))+1;
    $filter->sortOrder = $sortOrder;
  }
  $filter->idLayout=$idLayout;
  $filter->save();
  $criteria=new FilterCriteria();
  $criteria->purge("idFilter='" . $filter->id . "' and isReportList='0'");
  //ADD qCazelles - Dynamic filter - Ticket #78
  $dynamicFilter=0;
  //END ADD qCazelles - Dynamic filter - Ticket #78
  foreach ($filterArray as $filterCriteria) {
    $criteria=new FilterCriteria();
    $criteria->idFilter=$filter->id;
    $criteria->dispAttribute=$filterCriteria["disp"]["attribute"];
    $criteria->dispOperator=$filterCriteria["disp"]["operator"];
    $criteria->dispValue=$filterCriteria["disp"]["value"];
    $criteria->sqlAttribute=$filterCriteria["sql"]["attribute"];
    $criteria->sqlOperator=$filterCriteria["sql"]["operator"];
    $criteria->sqlValue=$filterCriteria["sql"]["value"];
    if ($criteria->sqlValue==null) {
    	if ($criteria->sqlOperator=='is null' or $criteria->sqlOperator=='is not null') {
    		$criteria->sqlValue=null;
    	} else {
    	  $criteria->sqlValue='0';
    	}
    }
    //ADD qCazelles - Dynamic filter - Ticket #78
    $criteria->orOperator=(isset($filterCriteria["orOperator"]))?$filterCriteria["orOperator"]:0;
    $criteria->isDynamic=(isset($filterCriteria["isDynamic"]))?$filterCriteria["isDynamic"]:0;
    $criteria->isGroup=(isset($filterCriteria["isGroup"]))?$filterCriteria["isGroup"]:0;
    $criteria->indentLevel=(isset($filterCriteria["indentLevel"]))?$filterCriteria["indentLevel"]:0;
    
    if (isset($filterCriteria["isDynamic"]) and $filterCriteria["isDynamic"]=="1") {
		  $dynamicFilter=1;
    }
    //END ADD qCazelles - Dynamic filter - Ticket #78
    $criteria->save();
  }
}
//ADD qCazelles - Dynamic filter - Ticket #78
if ($filter->isDynamic!=$dynamicFilter) {
	$filter->isDynamic=$dynamicFilter; //If a criteria is dynamic, the filter is dynamic
	$filter->save();
}
//END ADD qCazelles - Dynamic filter - Ticket #78

echo "<div id='saveFilterResult' style='z-index:999;position: absolute;left:50%;width:100%;margin-left:-50%;top:20px;background: #F6FAF6;' >";
echo '<table width="100%"><tr><td align="center" >';
echo '<span class="messageOK" style="z-index:99;position:relative;top:5px;white-space:nowrap;text-align:left;background: #F6FAF6;" >' . ucfirst(i18n('colFilter')) . " '" . htmlEncode($name) . "' " . i18n('resultUpdated') . ' (#'.htmlEncode($filter->id).')</span>';
echo '</td></tr></table>';
echo "</div>";

if($idFilterFromFavoriteProject){
  $flt=new Filter($idFilterFromFavoriteProject);
  $filterList[]=$flt;
}else{
  $flt=new Filter();
  $crit=array('idUser'=> $user->id, 'refType'=>$objectClass );
  $orderByFilter = "sortOrder ASC";
  $filterList=$flt->getSqlElementsFromCriteria($crit,false,null,$orderByFilter);
}

htmlDisplayStoredFilter($filterList,$filterObjectClass,"","",$comboDetail,$idFilterFromFavoriteProject);
Sql::commitTransaction();
?>
