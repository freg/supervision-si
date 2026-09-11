<?PHP
/**
 * * COPYRIGHT NOTICE *********************************************************
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
 * FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 * ** DO NOT REMOVE THIS NOTICE ***********************************************
 */

/**
 * ===========================================================================
 * generic functions for json extractions
 */
require_once "../tool/projeqtor.php";
//session_write_close(); // Do not activate : generates issue on saving ProductVersion
function jsonGetFilterArray($filterObjectClass, $comboDetail=false, $idReportLayout=null) {
  $arrayFilter=array();
  if(!$idReportLayout){
    if (!$comboDetail and is_array(getSessionUser()->_arrayFilters)) {
      if (pq_array_key_exists($filterObjectClass, getSessionUser()->_arrayFilters)) {
        $arrayFilter=getSessionUser()->_arrayFilters[$filterObjectClass];
      }
    } else if ($comboDetail and is_array(getSessionUser()->_arrayFiltersDetail)) {
      if (pq_array_key_exists($filterObjectClass, getSessionUser()->_arrayFiltersDetail)) {
        $arrayFilter=getSessionUser()->_arrayFiltersDetail[$filterObjectClass];
      }
    }
    foreach ($arrayFilter as $idx=>$arr) {
      if (isset($arr['sql']['attribute']) && pq_strpos($arr['sql']['attribute'], 'PlanningMode')>0) {
        $arrayFilter[$idx]['sql']['attribute']=pq_str_replace(array(
            'idActivityPlanningMode', 
            'idTestSessionPlanningMode', 
            'idMilestonePlanningMode'), 'idPlanningMode', $arr['sql']['attribute']);
      }
    }
  }else{
    $reportLayout = new ReportLayout($idReportLayout);
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
      $arrayFilter[]=array("disp"=>$arrayDisp,"sql"=>$arraySql,"orOperator"=>$orOperator,"isGroup"=>$filterCriteria->isGroup,"indentLevel"=>$filterCriteria->indentLevel);
    }
  }
  return $arrayFilter;
}

function filterPrepareGroupCriteria($arrayFilter) {
  $result=array();
  $pendingOpen=0;
  $lastConditionIndex=null;
  foreach ($arrayFilter as $crit) {
    if (filterIsGroupOnly($crit)) {
      if (isset($crit['isGroup']) and intval($crit['isGroup'])==1) {
        $pendingOpen++;
      } else if (isset($crit['isGroup']) and intval($crit['isGroup'])==2 and $lastConditionIndex!==null) {
        $result[$lastConditionIndex]['_groupCloseCount']++;
      }
      continue;
    }
    $crit['_groupOpenCount']=$pendingOpen;
    $crit['_groupCloseCount']=0;
    if (isset($crit['isGroup']) and intval($crit['isGroup'])==1) {
      $crit['_groupOpenCount']++;
    } else if (isset($crit['isGroup']) and intval($crit['isGroup'])==2) {
      $crit['_groupCloseCount']++;
    }
    if (isset($crit['sql']['operator']) and $crit['sql']['operator']!='SORT') {
      $pendingOpen=0;
      $result[]=$crit;
      $lastConditionIndex=array_key_last($result);
    } else {
      $result[]=$crit;
    }
  }
  return $result;
}

function jsonBuildSortCriteria(&$querySelect, &$queryFrom, &$queryWhere, &$queryOrderBy, &$idTab, $arrayFilter, $obj) {
  $objectClass=($obj)?get_class($obj):'';
  $table=$obj->getDatabaseTableName();
  $orderClauses = [];
  $groupStack = [];
  foreach ($arrayFilter as $crit) {
    if ($crit['sql']['attribute'] == 'itemName' && $crit['sql']['operator']=='SORT') {
      $queryOrderBy .= ($queryOrderBy == '') ? '' : ', ';
      $queryOrderBy .= " CASE ";
      $ass = new Assignment();
      $assTable = $ass->getDatabaseTableName();
      $queryRefTypes = Sql::query("SELECT DISTINCT refType FROM $assTable");
      $refTypes = [];
      $isPgSql = Sql::isPgsql();
      foreach ($queryRefTypes as $row) {
        if ($isPgSql){
          if (isset($row['reftype']) && !in_array($row['reftype'], $refTypes)) {
            if (class_exists($row['reftype'])) $refTypes[] = $row['reftype'];
          }
        }else{
          if (isset($row['refType']) && !in_array($row['refType'], $refTypes)) {
            if (class_exists($row['refType'])) $refTypes[] = $row['refType'];
          }
        }
      }
      foreach ($refTypes as $refType) {
        $alias = strtoupper(substr($refType, 0, 2));
        $queryOrderBy .= " WHEN $table.refType = '$refType' THEN $alias.name ";
      }
      $queryOrderBy .= " ELSE NULL END " . $crit['sql']['value'];
      continue;
    }
    
    if ($crit['sql']['operator']=='SORT') {
      $doneSort=false;
      $split=pq_explode('_', $crit['sql']['attribute']);
      if (pq_strpos($crit['sql']['attribute'], '__id')>0) $split=array();
      
      if (isset($crit['isGroup']) && $crit['isGroup'] == 1) { // (
        $orderClauses[] = "(";
        array_push($groupStack, true);
      }
      
      if (count($split)>1) {
        $externalClass=$split[0];
        $externalObj=new $externalClass();
        $externalTable=$externalObj->getDatabaseTableName();
        $idTab+=1;
        $externalTableAlias='T'.$idTab;
        $queryFrom.=' left join '.$externalTable.' as '.$externalTableAlias.' on ( '.$externalTableAlias.".refType='".get_class($obj)."' and ".$externalTableAlias.'.refId = '.$table.'.id )';
        $queryOrderBy.=($queryOrderBy=='')?'':', ';
        $queryOrderBy.=" ".$externalTableAlias.'.'.(($split[1]=='wbs' and property_exists($externalObj, 'wbsSortable'))?'wbsSortable':$split[1])." ".$crit['sql']['value'];
        $doneSort=true;
      }
      if (pq_substr($crit['sql']['attribute'], 0, 2)=='id' and pq_strlen($crit['sql']['attribute'])>2) {
        $externalClass=pq_substr($crit['sql']['attribute'], 2);
        if ($externalClass=='MacroStatus') $externalClass='MacroTicketStatus';
        $externalObj=new $externalClass();
        $externalTable=$externalObj->getDatabaseTableName();
        $sortColumn='id';
        if (property_exists($externalObj, 'sortOrder') and $externalClass!='Project') {
          $sortColumn=$externalObj->getDatabaseColumnName('sortOrder');
        } else {
          $sortColumn=$externalObj->getDatabaseColumnName('name');
        }
        $idTab+=1;
        $externalTableAlias='T'.$idTab;
        $queryOrderBy.=($queryOrderBy=='')?'':', ';
        $queryOrderBy.=" ".$externalTableAlias.'.'.$sortColumn." ".pq_str_replace("'", "", $crit['sql']['value']);
        $queryFrom.=' left join '.$externalTable.' as '.$externalTableAlias.' on '.$table.".".$obj->getDatabaseColumnName('id'.$externalClass).' = '.$externalTableAlias.'.'.$externalObj->getDatabaseColumnName('id');
        $doneSort=true;
      }
      if (!$doneSort) {
        $queryOrderBy.=($queryOrderBy=='')?'':', ';
        $queryOrderBy.=" ".$table.".".$obj->getDatabaseColumnName($crit['sql']['attribute'])." ".$crit['sql']['value'];
      }
      
      if (isset($crit['isGroup']) && $crit['isGroup'] == 2) { // )
        if (!empty($groupStack)) {
          array_pop($groupStack);
          $orderClauses[] = ")";
        }
      }
      
    }
  }
}

function jsonBuildWhereCriteria(&$querySelect, &$queryFrom, &$queryWhere, &$queryOrderBy, &$idTab, $arrayFilter, $obj) {
  $objectClass=($obj)?get_class($obj):'';
  $table=$obj->getDatabaseTableName();
  $queryWhereTmp='';
  $filterIsDynamic=false;
  $hasFilterGroup=false;
  $isPgSql = Sql::isPgsql();
  $arrayFilter=filterPrepareGroupCriteria($arrayFilter);
  foreach ($arrayFilter as $crit) {
    if ((isset($crit['_groupOpenCount']) and $crit['_groupOpenCount']>0)
        or (isset($crit['_groupCloseCount']) and $crit['_groupCloseCount']>0)) {
      $hasFilterGroup=true;
    }
    if (pq_array_key_exists('isDynamic', $crit) and $crit['isDynamic']=='1') {
      $filterIsDynamic=true;
      break;
    }
  }
  if (!$filterIsDynamic and count($arrayFilter)>0) {
    $arrayFilter=array_values($arrayFilter);
    for ($i=0; $i<count($arrayFilter); $i++) {
      $crit=$arrayFilter[$i];
      if ( isset($crit['sql']['operator']) and ($crit['sql']['operator']=='IN' || $crit['sql']['operator']=='NOT IN') and $crit['sql']['value']=='0') continue; // Dynamic filter not set
      if (isset($crit['sql']['operator']) and $crit['sql']['operator']!='SORT') { // Sorting already applied previously
        $split=pq_explode('_', $crit['sql']['attribute']);
        if (pq_strpos($crit['sql']['attribute'], '__id')>0) $split=array();
        $critSqlValue=$crit['sql']['value'];
        if (pq_substr($crit['sql']['attribute'], -4, 4)=='Work' and pq_substr($critSqlValue,0,1)!='[' ) {
          if ($objectClass=='Ticket') {
            $critSqlValue=Work::convertImputation(pq_trim($critSqlValue, "'"));
          } else {
            $critSqlValue=Work::convertWork(pq_trim($critSqlValue, "'"));
          }
        }
        if ($crit['sql']['operator']=='IN' and ($crit['sql']['attribute']=='idProduct' or $crit['sql']['attribute']=='idProductOrComponent' or $crit['sql']['attribute']=='idComponent')) {
          $critSqlValue=pq_str_replace(array(' ', '(', ')'), '', $critSqlValue);
          $splitVal=pq_explode(',', $critSqlValue);
          $critSqlValue='(0';
          foreach ($splitVal as $idP) {
            $prod=new Product($idP);
            $critSqlValue.=', '.$idP;
            $list=$prod->getRecursiveSubProductsFlatList(false, false); // Will work only if selected is Product, not for Component
            foreach ($list as $idPrd=>$namePrd) {
              $critSqlValue.=', '.$idPrd;
            }
          }
          $critSqlValue.=')';
        }
        if ( $crit['sql']['attribute']=='idProject' and ($crit['sql']['operator']=='IN' or $crit['sql']['operator']=='NOT IN') ) { // Extend filter on Project to subprojects
          $lstProj=explode(',',pq_trim($critSqlValue,'()'));
          $res=array();
          foreach ($lstProj as $idP) {
            $idP=pq_trim($idP);
            $prj=new Project($idP,true);
            $list=$prj->getRecursiveSubProjectsFlatList(false,true);
            $res=array_merge_preserve_keys($res,$list);
          }
          $critSqlValue=transformListIntoInClause($res);
        }
        if ($crit['sql']['operator']=='IN' and ($critSqlValue==='0' or $critSqlValue==='' or $critSqlValue==')' or $critSqlValue===' ' or $critSqlValue===null)) {
          $critSqlValue='(0)';
        }
        
        if ($crit['sql']['attribute'] == 'itemName') {
          appendLogicalOperator($queryWhereTmp, $arrayFilter, $i, $crit, $hasFilterGroup);
          $queryWhereTmp .= '(';
          $ass = new Assignment();
          $assTable = $ass->getDatabaseTableName();
          $queryRefTypes = Sql::query("SELECT DISTINCT refType FROM $assTable");
          $refTypes = [];
          $isPgSql = Sql::isPgsql();
          foreach ($queryRefTypes as $row) {
            if ($isPgSql){
              if (isset($row['reftype']) && !in_array($row['reftype'], $refTypes)) {
                if (class_exists($row['reftype'])) $refTypes[] = $row['reftype'];
              }
            }else{
              if (isset($row['refType']) && !in_array($row['refType'], $refTypes)) {
                if (class_exists($row['refType'])) $refTypes[] = $row['refType'];
              }
            }
          }
          $conditions = [];
          $operator = strtoupper(trim($crit['sql']['operator']));
          foreach ($refTypes as $refType) {
            $alias = strtoupper(substr($refType, 0, 2));
            $normalizedValue = ($operator === 'LIKE' || $operator === 'NOT LIKE' || $operator === 'ILIKE' || $operator === 'NOT ILIKE') ? normalizeFilterWildcards($critSqlValue) : $critSqlValue;
            $conditions[] = "($table.refType = '$refType' AND $alias.name $operator " . $normalizedValue . ")";
            //$conditions[] = "($table.refType = '$refType' AND $alias.name $operator " .$critSqlValue. ")"; 
          }
          if ($operator == 'IS NULL') {
            $refTypeList = "'" . implode("','", $refTypes) . "'";
            $conditions[] = "($table.refType NOT IN ($refTypeList))";
          }
          $queryWhereTmp .= implode(' OR ', $conditions) . ')';
          appendFilterGroupClose($queryWhereTmp, $crit);
          if (!$hasFilterGroup and isset($crit['orOperator']) and $crit['orOperator']=='1') {
            $queryWhereTmp.=')';
          }
          continue;
        }
        if ($crit['sql']['attribute'] == 'indicatorFileNoteLink') {
          appendLogicalOperator($queryWhereTmp, $arrayFilter, $i, $crit, $hasFilterGroup);
          $aff=new Affectable(getSessionUser()->id,true);
          $idTeamCurrentUser = $aff->idTeam;
          $userId = getSessionUser()->id;
          $note = new Note();
          $noteTable = $note->getDatabaseTableName();
          $link = new Link();
          $linkTable = $link->getDatabaseTableName();
          $attachment = new Attachment();          
          $attachmentTable = $attachment->getDatabaseTableName();
          $operator = strtoupper(trim($crit['sql']['operator']));
          $nullOrNot = ($operator == 'IS NULL') ? '=' : '>';
          $andOr = ($operator == 'IS NULL') ? 'AND' : 'OR';
          $isNullIsNotNull = ($operator == 'IS NULL' || $operator == 'IS NOT NULL') ? true : false;
          $queryWhereTmp.='(';
          if ($operator == 'HASNOTES' || $isNullIsNotNull){
            $queryWhereTmp .= '((SELECT COUNT(n.id) FROM '.$noteTable.' n WHERE n.refType = \'' . $objectClass . '\' AND n.refId = ' . $table . '.id 
	                                      AND (n.idPrivacy=1 OR (n.idPrivacy=2 and n.idTeam=' . Sql::fmtId($idTeamCurrentUser) . ') OR (n.idPrivacy=3 and n.idUser=' . Sql::fmtId($userId) . '))) ' . $nullOrNot . ' 0) ';
            if ($isNullIsNotNull) $queryWhereTmp .= $andOr;
          }
          if ($operator == 'HASATTACHMENTS' || $isNullIsNotNull){
            $queryWhereTmp .= '((SELECT COUNT(a.id) FROM '.$attachmentTable.' a WHERE a.refType = \'' . $objectClass . '\' AND a.refId = ' . $table . '.id
                                        AND (a.idPrivacy=1 OR (a.idPrivacy=2 and a.idTeam=' . Sql::fmtId($idTeamCurrentUser) . ') OR (a.idPrivacy=3 and a.idUser=' . Sql::fmtId($userId) . '))) ' . $nullOrNot . ' 0) ';
            if ($isNullIsNotNull) $queryWhereTmp .=  $andOr;
          }
          if ($operator == 'HASLINKS' || $isNullIsNotNull){
            $queryWhereTmp .= '((SELECT COUNT(l.id) FROM '.$linkTable.' l WHERE (l.ref1Type = \'' . $objectClass . '\' AND l.ref1Id = ' . $table . '.id 
                                        OR l.ref2Type = \'' . $objectClass . '\' AND l.ref2Id = ' . $table . '.id)) ' . $nullOrNot .' 0) ';
          }
          if (!$hasFilterGroup and isset($crit['orOperator']) and $crit['orOperator']=='1') {
            $queryWhereTmp.=')';
          }
          $queryWhereTmp.=')';
          appendFilterGroupClose($queryWhereTmp, $crit);
          continue;
        }
        if (count($split)>1) {
          $externalClass=$split[0];
          $externalObj=new $externalClass();
          $externalTable=$externalObj->getDatabaseTableName();
          $idTab+=1;
          $externalTableAlias='T'.$idTab;
          $queryFrom.=' left join '.$externalTable.' as '.$externalTableAlias.' on ( '.$externalTableAlias.".refType='".get_class($obj)."' and ".$externalTableAlias.'.refId = '.$table.'.id )';
          // FIX #3069 PBE - Start
          // $queryWhereTmp.=($queryWhereTmp=='' or $queryWhereTmp=='(')?'':' and ';
          appendLogicalOperator($queryWhereTmp, $arrayFilter, $i, $crit, $hasFilterGroup);
          $extField=$externalObj->getDatabaseColumnName($split[1]);
          $testField=pq_str_replace(array($externalClass.'_','[',']'),'',$critSqlValue);
          if ($critSqlValue=='['.$externalClass.'_'.$testField.']') { 
            $queryWhereTmp.=$externalTableAlias.".".$extField.' '.$crit['sql']['operator']." $externalTableAlias.$testField";
          }else if ($critSqlValue=='['.$testField.']') {
            $queryWhereTmp.=$externalTableAlias.".".$extField.' '.$crit['sql']['operator']." $table.$testField";
          }else if ($crit['sql']['operator']=='=month+' or $crit['sql']['operator']=='=year+'){
            $queryWhereTmp.=$externalTableAlias.".".$extField.' '.$critSqlValue;
          }else if ($testField and preg_match('/^([A-Za-z_][A-Za-z0-9_]*)\s*([+\-x])\s*(\d+(?:\.\d+)?)$/', $testField, $matches)){
            $fieldName = $matches[1];
            $operatorCompare = $matches[2];
            if ($operatorCompare =="x") $operatorCompare='*';
            $filterCompareValue = $matches[3];
            if (substr($crit['sql']['attribute'], -4) === "Date" || substr($crit['sql']['attribute'], -8) === "DateTime") {
              if ($isPgSql) $queryWhereTmp .= $externalTableAlias . "." . $extField. " " . $crit['sql']['operator'] . " ". $externalTableAlias . "." . $fieldName . " ". $operatorCompare . " INTERVAL '" . $filterCompareValue . " day'";
              else $queryWhereTmp .= $externalTableAlias . "." . $extField. " " . $crit['sql']['operator'] . " ". $externalTableAlias . "." . $fieldName . " ". $operatorCompare . " INTERVAL " . $filterCompareValue . " DAY";
            } else if (substr($crit['sql']['attribute'], -4) === "Cost" || substr($crit['sql']['attribute'], -7) === "revenue" || substr($crit['sql']['attribute'], -6) === "Amount" || substr($crit['sql']['attribute'], -4) === "Work") {
              $queryWhereTmp .= $externalTableAlias . "." . $extField. " " . $crit['sql']['operator'] . " ". $externalTableAlias . "." . $fieldName . " ". $operatorCompare . " " . $filterCompareValue;
            }else{
              $queryWhereTmp .= $externalTableAlias . "." . $extField. " " . $crit['sql']['operator'] . " ". $externalTableAlias . "." . $fieldName . " ". $operatorCompare . " " . $filterCompareValue;
            }
          }else{
            $sqlOp = strtoupper(trim($crit['sql']['operator']));
            if ($sqlOp === 'LIKE' || $sqlOp === 'NOT LIKE' || $sqlOp === 'ILIKE' || $sqlOp === 'NOT ILIKE') {
              $critSqlValue = normalizeFilterWildcards($critSqlValue);
            }
            $queryWhereTmp.=$externalTableAlias.".".$extField.' '.$crit['sql']['operator'].' '.$critSqlValue;
          }
        } else {
          if (! $crit['sql']['attribute'] and pq_trim($crit['sql']['operator'])!='exists' and pq_trim($crit['sql']['operator'])!='not exists') continue;
          appendLogicalOperator($queryWhereTmp, $arrayFilter, $i, $crit, $hasFilterGroup);
          
          if (pq_trim($crit['sql']['operator'])!='exists' and pq_trim($crit['sql']['operator'])!='not exists') {
            $queryWhereTmp.="(".$table.".".$crit['sql']['attribute'].' ';
          }
          $testField=pq_str_replace(array('[',']'),'',$critSqlValue);
          if ($crit['sql']['operator']=='=month+' or $crit['sql']['operator']=='=year+') {
            $queryWhereTmp.=$critSqlValue;
          }else if ($critSqlValue=="[$testField]"){
            $queryWhereTmp.=$crit['sql']['operator']." $table.$testField";
          } else if ($testField and preg_match('/^([A-Za-z_][A-Za-z0-9_]*)\s*([+\-x])\s*(\d+(?:\.\d+)?)$/', $testField, $matches)){
              $fieldName = $matches[1];
              $operatorCompare = $matches[2];
              if ($operatorCompare =="x") $operatorCompare='*';
              $filterCompareValue = $matches[3];
              if (substr($crit['sql']['attribute'], -4) === "Date" || substr($crit['sql']['attribute'], -8) === "DateTime") {
                if ($isPgSql) $queryWhereTmp .= " ".$crit['sql']['operator']." $fieldName $operatorCompare INTERVAL '$filterCompareValue day'";
                else $queryWhereTmp .= " ".$crit['sql']['operator']." $fieldName $operatorCompare INTERVAL $filterCompareValue DAY";
              } else if (substr($crit['sql']['attribute'], -4) === "Cost" || substr($crit['sql']['attribute'], -7) === "revenue" || substr($crit['sql']['attribute'], -6) === "Amount" || substr($crit['sql']['attribute'], -4) === "Work") {
                $queryWhereTmp .= " ".$crit['sql']['operator']." $table.$fieldName $operatorCompare $filterCompareValue";
              }else{
                $queryWhereTmp .= " ".$crit['sql']['operator']." $table.$fieldName $operatorCompare $filterCompareValue";
              }
          }else {
            $sqlOp = strtoupper(trim($crit['sql']['operator']));
            if ($sqlOp === 'LIKE' || $sqlOp === 'NOT LIKE' || $sqlOp === 'ILIKE' || $sqlOp === 'NOT ILIKE') {
              $critSqlValue = normalizeFilterWildcards($critSqlValue);
            }
            $queryWhereTmp.=$crit['sql']['operator'].' '.$critSqlValue;
          }
          if (pq_strlen($crit['sql']['attribute'])>=9 and pq_substr($crit['sql']['attribute'], 0, 2)=='id' and (pq_substr($crit['sql']['attribute'], -7)=='Version' and SqlElement::is_a(pq_substr($crit['sql']['attribute'], 2), 'Version')) and $crit['sql']['operator']=='IN') {
            $scope=pq_substr($crit['sql']['attribute'], 2);
            $vers=new OtherVersion();
            $queryWhereTmp.=" or exists (select 'x' from ".$vers->getDatabaseTableName()." VERS "." where VERS.refType=".Sql::str($objectClass)." and VERS.refId=".$table.".id and scope=".Sql::str($scope)." and VERS.idVersion IN ".$critSqlValue.")";
          } else if ($crit['sql']['attribute']=='idClient' and $crit['sql']['operator']=='IN' and property_exists($objectClass, 'idClient') and property_exists($objectClass, '_OtherClient')) {
            $otherclient=new OtherClient();
            $queryWhereTmp.=" or exists (select 'x' from ".$otherclient->getDatabaseTableName()." other "." where other.refType=".Sql::str($objectClass)." and other.refId=".$table.".id and other.idClient IN ".$critSqlValue.")";
          }
          if ($crit['sql']['operator']=='NOT IN' or $crit['sql']['operator']=='NOT LIKE') {
            $queryWhereTmp.=" or ".$table.".".$crit['sql']['attribute']." IS NULL ";
          }
          if ($crit['sql']['operator']=='=' and ($critSqlValue=="'0'" or $critSqlValue=='0')) {
            $queryWhereTmp.=' or '.$table.".".$crit['sql']['attribute'].' is null ';
          }
          if (pq_trim($crit['sql']['operator'])!='exists' and pq_trim($crit['sql']['operator'])!='not exists') {
            $queryWhereTmp.=")";
          }
        }
        appendFilterGroupClose($queryWhereTmp, $crit);
      }
      if (!$hasFilterGroup and isset($crit['orOperator']) and $crit['orOperator']=='1' and $i!=0) {
        $queryWhereTmp.=')';
      }
    }
    $queryWhere.=$queryWhereTmp;
  }
}

function appendLogicalOperator(&$queryWhereTmp, $arrayFilter, $i, $crit, $hasFilterGroup=false) {
  if ($hasFilterGroup) {
    if ($i!=0 and isset($crit['orOperator']) and $crit['orOperator']=="1") {
      $queryWhereTmp.=' or ';
    } else {
      $queryWhereTmp.=' and ';
    }
  } else if (isset($crit['orOperator']) && $crit['orOperator'] == "1") {
    $queryWhereTmp .= ' or ';
  } else if (count($arrayFilter) > 1 && $i + 1 < count($arrayFilter)
      && isset($arrayFilter[$i + 1]['orOperator']) && $arrayFilter[$i + 1]['orOperator'] == '1') {
        $queryWhereTmp .= ' and ';
        for ($j = $i + 1; $j < count($arrayFilter) && $arrayFilter[$j]['orOperator'] == '1'; $j++) {
          $queryWhereTmp .= '(';
        }
      } else {
        $queryWhereTmp .= ' and ';
      }
  $openCount=isset($crit['_groupOpenCount']) ? intval($crit['_groupOpenCount']) : ((isset($crit['isGroup']) and intval($crit['isGroup'])==1) ? 1 : 0);
  if ($openCount>0) {
    $queryWhereTmp.=str_repeat('(', $openCount);
  }
}

function appendFilterGroupClose(&$queryWhereTmp, $crit) {
  $closeCount=isset($crit['_groupCloseCount']) ? intval($crit['_groupCloseCount']) : ((isset($crit['isGroup']) and intval($crit['isGroup'])==2) ? 1 : 0);
  if ($closeCount>0) {
    $queryWhereTmp.=str_repeat(')', $closeCount);
  }
}

function jsonDumpObj($obj, $included=false, $parentObj=null, $selectedFields=null) {
  $res="";
  if (method_exists($obj, 'setAttributes') and $selectedFields==null) {
    $obj->setAttributes();
  }
  $selectedFieldsTemp=($selectedFields)?array_flip($selectedFields):array();
  foreach ($obj as $fld=>$val) {
    if (is_object($val)) {
      $res.=jsonDumpObj($val, true, $obj,$selectedFields);
    } else if (pq_substr($fld, 0, 1)=='_' or (! $obj->isAttributeSetToField($fld, 'forceExport') and $obj->isAttributeSetToField($fld, 'hidden')) or $obj->isAttributeSetToField($fld, 'noExport') or $fld=='apiKey' or $fld=='password' or $included and ($fld=='id' or $fld=='refType' or $fld=='refId' or $fld=='refName' or $fld=='handled' or $fld=='done' or $fld=='idle' or $fld=='cancelled')) {
      // Nothing
    } else if ($included and $parentObj and property_exists($parentObj, $fld)) {
      // Nothing - filed already exists on parent object, so avoid dupplicate
    } else {
      if ($fld=='name' and property_exists($obj, '_isNameTranslatable') and $obj->_isNameTranslatable) {
        $val=i18n($val);
      }
      $isFk=isForeignKey($fld,get_class($obj));
      $fkwa=foreignKeyWithoutAlias($fld);
      $fkoa=foreignKeyOnlyAlias($fld);
      $fkoaEncode=htmlEncode($fkoa);
      if ($selectedFields==null or (is_array($selectedFields) and in_array($fkoaEncode,$selectedFields))) {
        if ($res!="" or $included) {
          $res.=", ";
        }
        $res.='"'.$fkoaEncode.'":"'.htmlEncodeJson($val).'"';
        if ($selectedFields) {
          unset($selectedFieldsTemp[$fld]);
          if (count($selectedFieldsTemp)==0) break;
        }
      }
      //if (pq_substr($fld, 0, 2)=='id' and pq_strlen($fld)>2) {
      if ($isFk) {
        $fld__=$fkwa;
        $idclass=pq_substr($fld__, 2);
        $classMapping = [
          'SynchronizationItem' => 'SynchronizedItems',
        ];
        if (isset($classMapping[$idclass])) {
          $idclass = $classMapping[$idclass];
        }
        if (pq_strtoupper(pq_substr($idclass, 0, 1))==pq_substr($idclass, 0, 1) and property_exists($idclass, 'name')) {
          if (pq_substr($fkoa,0,2)=='id') {
            $nameFld='name'.pq_substr($fkoa, 2);
          } else {
            $nameFld=$fkoa.'Name';
          }
          if ($selectedFields==null or (is_array($selectedFields) and in_array($nameFld,$selectedFields))) {
            $val2=SqlList::getNameFromId($idclass, $val);
            if ($res!="" or $included) {
              $res.=", ";
            }
            $res.='"'.$nameFld.'":"'.htmlEncodeJson($val2).'"';
            if ($selectedFields) {
              unset($selectedFieldsTemp[$nameFld]);
              if (count($selectedFieldsTemp)==0) break;
            }
          }
        }
      }
    }
  }
  if (property_exists($obj, 'refId') and property_exists($obj, 'refType') and !property_exists($obj, 'refName') and $obj->refId!="" and $obj->refType!="" and !$included) {
    $idclass=$obj->refType;
    if (pq_strtoupper(pq_substr($idclass, 0, 1))==pq_substr($idclass, 0, 1) and property_exists($idclass, 'name')) {
      $res.=", ";
      $res.='"refName":"'.htmlEncodeJson(SqlList::getNameFromId($idclass, $obj->refId)).'"';
    }
  }
  return $res;
}


function normalizeFilterWildcards($value) {
  return strtr($value, ['*' => '%', '?' => '_']);
}

function planningGetFilterObjectClasses() {
  return array('Project', 'Activity', 'Milestone', 'Meeting', 'PeriodicMeeting', 'TestSession');
}

function planningGetFilterPlanningElementClasses() {
  return array('ProjectPlanningElement', 'ActivityPlanningElement', 'MilestonePlanningElement', 'MeetingPlanningElement', 'TestSessionPlanningElement');
}

function planningGetFilterPlanningElementClass($objectClass) {
  if ($objectClass=='PeriodicMeeting') return 'MeetingPlanningElement';
  $planningElementClass=$objectClass.'PlanningElement';
  if (class_exists($planningElementClass)) return $planningElementClass;
  return null;
}

function planningGetFilterAttributeScope($attribute) {
  if (pq_substr($attribute, 0, 15)=='PlanningObject_') return 'object';
  if (pq_substr($attribute, 0, 16)=='PlanningElement_') return 'planning';
  return null;
}

function planningGetFilterAttributeField($attribute) {
  $scope=planningGetFilterAttributeScope($attribute);
  if ($scope=='object') return pq_substr($attribute, 15);
  if ($scope=='planning') return pq_substr($attribute, 16);
  return $attribute;
}

function planningGetFilterReferenceObject($attribute) {
  $scope=planningGetFilterAttributeScope($attribute);
  $field=planningGetFilterAttributeField($attribute);
  if ($scope=='object') {
    foreach (planningGetFilterObjectClasses() as $class) {
      $obj=new $class();
      if (property_exists($obj, $field)) return $obj;
    }
  } else if ($scope=='planning') {
    foreach (planningGetFilterPlanningElementClasses() as $class) {
      $obj=new $class();
      if (property_exists($obj, $field)) return $obj;
    }
  }
  return null;
}

function planningGetFilterFieldDataType($obj, $field) {
  $dataType=$obj->getDataType($field);
  $dataLength=$obj->getDataLength($field);
  if ($dataType=='int' and $dataLength==1) {
    return 'bool';
  } else if ($dataType=='datetime') {
    return 'date';
  } else if (isForeignKey($field, $obj)) {
    return 'list';
  }
  return $dataType;
}

function planningNormalizeFilterField($objectClass, $field) {
  $obj=new $objectClass();
  if (property_exists($obj, $field['id'])) {
    return array('id'=>'PlanningObject_'.$field['id'], 'name'=>$field['name'], 'dataType'=>$field['dataType'], 'scope'=>'object');
  }
  $planningElementClass=planningGetFilterPlanningElementClass($objectClass);
  if ($planningElementClass and pq_substr($field['id'], 0, pq_strlen($planningElementClass.'_'))==$planningElementClass.'_') {
    $planningElementField=pq_substr($field['id'], pq_strlen($planningElementClass.'_'));
    $planningElementObj=new $planningElementClass();
    if (property_exists($planningElementObj, $planningElementField)) {
      $planningElementField=$planningElementObj->getDatabaseColumnName($planningElementField);
      return array('id'=>'PlanningElement_'.$planningElementField, 'name'=>$field['name'], 'dataType'=>$field['dataType'], 'scope'=>'planning');
    }
  }
  return null;
}

function planningGetFilterFieldsFromObjectClass($objectClass) {
  $obj=new $objectClass();
  ob_start();
  listFieldsForFilter($obj, 0);
  $json=ob_get_clean();
  preg_match_all('/\{[^{}]*"id"\s*:\s*"[^"]+"[^{}]*\}/', $json, $matches);
  if (! isset($matches[0]) or count($matches[0])==0) return array();
  $result=array();
  foreach ($matches[0] as $fieldJson) {
    $field=json_decode($fieldJson);
    if (! $field) continue;
    if (! isset($field->id) or ! isset($field->dataType)) continue;
    $normalized=planningNormalizeFilterField($objectClass, array(
        'id'=>$field->id,
        'name'=>(isset($field->name)?$field->name:$field->id),
        'dataType'=>$field->dataType
    ));
    if ($normalized) $result[$normalized['id']]=$normalized;
  }
  return $result;
}

function planningGetCommonFilterFields() {
  $objectCommon=null;
  $planningCandidates=array();
  foreach (planningGetFilterObjectClasses() as $class) {
    $fields=planningGetFilterFieldsFromObjectClass($class);
    $objectFields=array();
    foreach ($fields as $id=>$field) {
      if ($field['scope']=='planning') {
        if (! isset($planningCandidates[$id])) $planningCandidates[$id]=$field;
      } else {
        $objectFields[$id]=$field;
      }
    }
    if ($objectCommon===null) {
      $objectCommon=$objectFields;
      continue;
    }
    foreach ($objectCommon as $id=>$field) {
      if (! isset($objectFields[$id]) or $objectFields[$id]['dataType']!=$field['dataType']) {
        unset($objectCommon[$id]);
      }
    }
  }
  $planningCommon=array();
  foreach ($planningCandidates as $id=>$field) {
    $planningElementField=planningGetFilterAttributeField($id);
    $common=true;
    foreach (planningGetFilterPlanningElementClasses() as $class) {
      $obj=new $class();
      if (! property_exists($obj, $planningElementField) or planningGetFilterFieldDataType($obj, $planningElementField)!=$field['dataType']) {
        $common=false;
        break;
      }
    }
    if ($common) $planningCommon[$id]=$field;
  }
  if ($objectCommon===null) $objectCommon=array();
  return array_values(array_merge($objectCommon, $planningCommon));
}

function planningListFieldsForFilter() {
  global $contextForAttributes, $hideScope;
  $contextForAttributes='global';
  $hideScope='column';
  $requestField=null;
  $requestFieldExists=pq_array_key_exists('field', $_REQUEST);
  if ($requestFieldExists) {
    $requestField=$_REQUEST['field'];
    unset($_REQUEST['field']);
  }
  $fieldType=RequestHandler::getValue('field');
  if ($requestFieldExists) {
    $fieldType=$requestField;
  }
  if ($fieldType) {
    $fieldType=planningGetFilterAttributeField($fieldType);
    if (pq_strpos($fieldType, 'Work')) $fieldType='Work';
    if (pq_strpos($fieldType, 'Cost') or pq_strpos($fieldType, 'Amount')) $fieldType='Cost';
    if (pq_strpos($fieldType, 'Date')) $fieldType='Date';
    if (pq_strpos($fieldType, 'pct') or pq_strpos($fieldType,'progress') or pq_strpos($fieldType,'rate')) $fieldType='Pct';
  }
  $fields=planningGetCommonFilterFields();
  if ($requestFieldExists) {
    $_REQUEST['field']=$requestField;
  }
  $nbRows=0;
  foreach ($fields as $field) {
    if ($fieldType=='Work' and !pq_strpos($field['id'], 'Work')) continue;
    if ($fieldType=='Cost' and (!pq_strpos($field['id'], 'Cost') and !pq_strpos($field['id'], 'Amount'))) continue;
    if ($fieldType=='Date' and !pq_strpos($field['id'], 'Date')) continue;
    if ($fieldType=='Pct' and (!pq_stripos($field['id'], 'pct') and !pq_stripos($field['id'], 'progress') and !pq_stripos($field['id'], 'rate'))) continue;
    if ($nbRows>0) echo ', ';
    echo '{"id":"'.$field['id'].'", "name":'.json_encode(htmlspecialchars_decode($field['name'])).', "dataType":"'.$field['dataType'].'"}';
    $nbRows++;
  }
  return $nbRows;
}

function planningBuildFilterSqlCondition($tableAlias, $dbField, $field, $operator, $value) {
  if ($field=='idProject' and ($operator=='IN' or $operator=='NOT IN')) {
    $lstProj=explode(',', pq_trim($value, '()'));
    $res=array();
    foreach ($lstProj as $idP) {
      $idP=pq_trim($idP);
      if (!$idP) continue;
      $prj=new Project($idP, true);
      $list=$prj->getRecursiveSubProjectsFlatList(false, true);
      $res=array_merge_preserve_keys($res, $list);
    }
    $value=transformListIntoInClause($res);
  }
  if ($operator=='=month+' or $operator=='=year+') {
    return $tableAlias.'.'.$dbField.' '.$value;
  }
  $testField=pq_str_replace(array('[',']'),'',$value);
  if ($value=="[$testField]") {
    $testField=planningGetFilterAttributeField($testField);
    $condition=$tableAlias.'.'.$dbField.' '.$operator.' '.$tableAlias.'.'.$testField;
  } else {
    $sqlOp=strtoupper(trim($operator));
    if ($sqlOp==='LIKE' or $sqlOp==='NOT LIKE' or $sqlOp==='ILIKE' or $sqlOp==='NOT ILIKE') {
      $value=normalizeFilterWildcards($value);
    }
    if (pq_trim($operator)=='exists' or pq_trim($operator)=='not exists') {
      $condition=$operator.' '.$value;
    } else {
      $condition=$tableAlias.'.'.$dbField.' '.$operator.' '.$value;
    }
  }
  if ($operator=='NOT IN' or $operator=='NOT LIKE') {
    $condition='('.$condition.' or '.$tableAlias.'.'.$dbField.' IS NULL)';
  } else if ($operator=='=' and ($value=="'0'" or $value=='0')) {
    $condition='('.$condition.' or '.$tableAlias.'.'.$dbField.' is null)';
  }
  return $condition;
}

function planningBuildWhereCriteria(&$queryFrom, &$queryWhere, &$idTab, $arrayFilter, $planningElementObj) {
  $planningElementTable=$planningElementObj->getDatabaseTableName();
  $queryWhereTmp='';
  $filterIsDynamic=false;
  $hasFilterGroup=false;
  $arrayFilter=filterPrepareGroupCriteria($arrayFilter);
  foreach ($arrayFilter as $crit) {
    if ((isset($crit['_groupOpenCount']) and $crit['_groupOpenCount']>0)
        or (isset($crit['_groupCloseCount']) and $crit['_groupCloseCount']>0)) {
      $hasFilterGroup=true;
    }
    if (pq_array_key_exists('isDynamic', $crit) and $crit['isDynamic']=='1') {
      $filterIsDynamic=true;
      break;
    }
  }
  if ($filterIsDynamic or count($arrayFilter)==0) return;
  $objectAliases=array();
  $arrayFilter=array_values($arrayFilter);
  for ($i=0; $i<count($arrayFilter); $i++) {
    $crit=$arrayFilter[$i];
    if (!isset($crit['sql']['operator']) or $crit['sql']['operator']=='SORT') continue;
    if (($crit['sql']['operator']=='IN' or $crit['sql']['operator']=='NOT IN') and $crit['sql']['value']=='0') continue;
    $attribute=$crit['sql']['attribute'];
    $scope=planningGetFilterAttributeScope($attribute);
    $field=planningGetFilterAttributeField($attribute);
    if (!$scope or !$field) continue;
    if ($scope=='planning') {
      $refObj=planningGetFilterReferenceObject($attribute);
      if (!$refObj or !property_exists($refObj, $field)) continue;
      $dbField=$refObj->getDatabaseColumnName($field);
      appendLogicalOperator($queryWhereTmp, $arrayFilter, $i, $crit, $hasFilterGroup);
      $queryWhereTmp.='('.planningBuildFilterSqlCondition($planningElementTable, $dbField, $field, $crit['sql']['operator'], $crit['sql']['value']).')';
    } else {
      $conditions=array();
      foreach (planningGetFilterObjectClasses() as $class) {
        $obj=new $class();
        if (!property_exists($obj, $field)) continue;
        if (!isset($objectAliases[$class])) {
          $idTab+=1;
          $alias='PFO'.$idTab;
          $objectAliases[$class]=$alias;
          $queryFrom.=' left join '.$obj->getDatabaseTableName().' as '.$alias." on ($planningElementTable.refType='$class' and $planningElementTable.refId=$alias.id)";
        }
        $alias=$objectAliases[$class];
        $dbField=$obj->getDatabaseColumnName($field);
        $conditions[]="($planningElementTable.refType='$class' and ".planningBuildFilterSqlCondition($alias, $dbField, $field, $crit['sql']['operator'], $crit['sql']['value']).')';
      }
      if (count($conditions)>0) {
        appendLogicalOperator($queryWhereTmp, $arrayFilter, $i, $crit, $hasFilterGroup);
        $queryWhereTmp.='('.implode(' or ', $conditions).')';
      }
    }
    appendFilterGroupClose($queryWhereTmp, $crit);
    if (!$hasFilterGroup and isset($crit['orOperator']) and $crit['orOperator']=='1' and $i!=0) {
      $queryWhereTmp.=')';
    }
  }
  $queryWhere.=$queryWhereTmp;
}
