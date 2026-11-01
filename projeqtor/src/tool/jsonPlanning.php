<?PHP
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
 * Get the list of objects, in Json format, to display the grid list
 */
  require_once "../tool/projeqtor.php";
  session_write_close();
  require_once "../tool/jsonFunctions.php";
  include_once "../tool/formatter.php";
  
  scriptLog('   ->/tool/jsonPlanning.php');
  SqlElement::$_cachedQuery['Project']=array();
  SqlElement::$_cachedQuery['Ticket']=array();
  SqlElement::$_cachedQuery['Activity']=array();
  SqlElement::$_cachedQuery['Resource']=array();
  SqlElement::$_cachedQuery['ResourceAll']=array();
  SqlElement::$_cachedQuery['PlanningElement']=array();
  
  if (! isset($portfolio)) {
    $portfolio=false;
  }
  if ( pq_array_key_exists('portfolio',$_REQUEST) ) {
    $portfolio=true;
  }
  
  $global=RequestHandler::getBoolean('global');
  $objectClass='PlanningElement';
  $target="planning";
  if ($portfolio) $target="portfolio";
  else if ($global) $target="global";
  $columnsDescription=Parameter::getPlanningColumnDescription($target);
  $obj=new $objectClass();
  $table=$obj->getDatabaseTableName();
  $displayResource=Parameter::getUserParameter('displayResourcePlan');
  if (!$displayResource) $displayResource="initials";
  $print=false;
  if ( pq_array_key_exists('print',$_REQUEST) ) {
    $print=true;
    $displayLikePlanning=false;
    include_once('../tool/formatter.php');
    if(RequestHandler::isCodeSet('displayAsGanttScreen') && RequestHandler::getBoolean('displayAsGanttScreen')==true)$displayLikePlanning=true;
    if(RequestHandler::isCodeSet('showIdle') && RequestHandler::getBoolean('showIdle')==true)$idleItemOnReport=true;
  }
  $queryStartLine=RequestHandler::getNumeric('jsonQueryStartLine',false,null);
  $queryNbLines=RequestHandler::getNumeric('jsonQueryNbLines',false,null);
  $queryHiddenLines=RequestHandler::getBoolean('jsonQueryHiddenLines',false,false);
  $immediateRefresh=RequestHandler::getBoolean('immediateRefresh',false,false);
  $saveDates=false;
  if ( pq_array_key_exists('listSaveDates',$_REQUEST) ) {
    $saveDates=true;
  }
  if ($portfolio) {
    $queryNbLines*=100;
    $queryHiddenLines=0;
  }
//   $showResource=false;
//   if ( pq_array_key_exists('showResource',$_REQUEST) ) {
//     $showResource=true;
//   }
  $showResource = RequestHandler::getValue('listShowResource');
  $showClosed = RequestHandler::getBoolean('idle');

  $plannableProjectsList=getSessionUser()->getListOfPlannableProjects();
  $startDate="";
  $endDate="";
  $projectDate=RequestHandler::getValue('projectDate');
  if (pq_array_key_exists('startDatePlanView',$_REQUEST) and pq_array_key_exists('endDatePlanView',$_REQUEST)) {
    $startDate=pq_trim($_REQUEST['startDatePlanView']);
  	Security::checkValidDateTime($startDate);
    $endDate= pq_trim($_REQUEST['endDatePlanView']);
	  Security::checkValidDateTime($endDate);
    $user=getSessionUser();
    $paramStart=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningStartDate'));
    $paramEnd=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningEndDate'));
    if ($saveDates) {
      $paramStart->parameterValue=$startDate;
      $paramStart->save();
      $paramEnd->parameterValue=$endDate;
      $paramEnd->save();
    } else {
      if ($paramStart->id) {
        $paramStart->delete();
      }
      if ($paramEnd->id) {
        $paramEnd->delete();
      }
    }
  }
  $baselineTop=null;
  if (pq_array_key_exists('selectBaselineTop',$_REQUEST)) {
    $baselineTop=pq_trim($_REQUEST['selectBaselineTop']);
  } else {
    $baselineTop=pq_trim(getSessionValue('planningBaselineTop'));
  }
  $baselineBottom=null;
  if (pq_array_key_exists('selectBaselineBottom',$_REQUEST)) {
    $baselineBottom=pq_trim($_REQUEST['selectBaselineBottom']);
  } else {
    $baselineBottom=pq_trim(getSessionValue('planningBaselineBottom'));
  }
  // Header
  if (pq_array_key_exists('outMode', $_REQUEST) && $_REQUEST['outMode'] == 'csv') {
    $outMode = 'csv';
  } else if (! isset($outMode) ) {
    $outMode = "html";
  }
  if ( pq_array_key_exists('report',$_REQUEST) ) {
    $headerParameters="";
    if (pq_array_key_exists('startDate',$_REQUEST) and pq_trim($_REQUEST['startDate'])!="") {
  		Security::checkValidDateTime(pq_trim($_REQUEST['startDate']));
      $headerParameters.= i18n("colStartDate") . ' : ' . dateFormatter($_REQUEST['startDate']) . '<br/>';
    }
    if (pq_array_key_exists('endDate',$_REQUEST) and pq_trim($_REQUEST['endDate'])!="") {
		  Security::checkValidDateTime(pq_trim($_REQUEST['endDate']));
      $headerParameters.= i18n("colEndDate") . ' : ' . dateFormatter($_REQUEST['endDate']) . '<br/>';
    }
    if (pq_array_key_exists('format',$_REQUEST)) {
      if(! RequestHandler::getValue("format")){
          echo '<div style="background: #FFDDDD;font-size:150%;margin-top:20px;color:#808080;text-align:center;padding:20px">';
          echo i18n('messageNoData',array(i18n('colFormat'))); // TODO i18n message
          echo '</div>';
          exit;
      }
		  Security::checkValidPeriodScale(pq_trim($_REQUEST['format']));
      $headerParameters.= i18n("colFormat") . ' : ' . i18n($_REQUEST['format']) . '<br/>';
    }
    if (pq_array_key_exists('idProject',$_REQUEST) and pq_trim($_REQUEST['idProject'])!="") {
      Security::checkValidId(pq_trim($_REQUEST['idProject']));
      $headerParameters.= i18n("colIdProject") . ' : ' . (SqlList::getNameFromId('Project', $_REQUEST['idProject'])) . '<br/>';
    }
  	if($outMode == 'csv') {
        include_once "../report/headerFunctions.php";
    } else {
  	  include "../report/header.php";
  	}
  }
  if (! isset($outMode)) { $outMode=""; }
  $directObjectClass=RequestHandler::getClass('gotoElementObjectClass',false,null);
  $directObjectId=RequestHandler::getId('gotoElementObjectId',false,null);
  $directObjectParents=array();
  if ($directObjectClass and $directObjectId) {
    $peTemp=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$directObjectClass, 'refId'=>$directObjectId));
    $directObjectParents=$peTemp->getParentItemsArray();
  }
  
  $showIdleProjects=(sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1)?1:0;
//   $showIdle=true;
//   if (pq_array_key_exists('idle',$_REQUEST)) {
//     $showIdle=true;
//   }
  $showIdle = RequestHandler::getValue('idle');
  
//  $showProjectModel = RequestHandler::getValue('showProjectModel');
  $selectedProject=getSessionValue('project');
  $prfCode=SqlList::getFieldFromId('Profile',$user->idProfile,'profileCode');
  $showProjectModel = RequestHandler::getValue('showProjectModel');
  if ($selectedProject=='*') {
    $showProjectModel=($showProjectModel=='true' or $showProjectModel=='on')?'own':'no';
    if ($showProjectModel=='own' and $prfCode=='PL') $showProjectModel='all';
  }
  
  if ($portfolio) {
  	$accessRightRead=securityGetAccessRight('menuProject', 'read');
  } else {
    $accessRightRead=securityGetAccessRight('menuActivity', 'read');
  }
  if ( ! ( $accessRightRead!='ALL' or (sessionValueExists('project') and getSessionValue('project')!='*'))
   and ( ! pq_array_key_exists('idProject',$_REQUEST) or pq_trim($_REQUEST['idProject'])=="") and !$portfolio and pq_strpos(getSessionValue('project'), ",") === null) {
      $listProj=pq_explode(',',getVisibleProjectsList(! $showIdleProjects));
  }
  $querySelect = '';
  $queryFrom='';
  $queryWhere='';
  $queryOrderBy='';
  $idTab=0;
  //gautier #6878
  if($showIdle==1)$showIdle='true';
  if (!$showIdle or $showIdle=='false') {
    if(isset($idleItemOnReport)){
      if(!$idleItemOnReport)$queryWhere= $table . ".idle=0 ";
    }else{
      $queryWhere= $table . ".idle=0 ";
    }
  }
  $queryWhere.= ($queryWhere=='')?'':' and ';
  if ($portfolio) {
//   	$queryWhere.="( (refType='Project' and ".getAccesRestrictionClause('Project',$table).")";
//   	$queryWhere.=" OR (refType='Milestone' and ".getAccesRestrictionClause('Milestone',$table,$showIdleProjects).") )";
    // restriction on acces is applied on query in the FROM
    if ($startDate) {
      $startDateMile=addDaysToDate($startDate, -30);
      $queryWhere.="( refType='Project' or (refType='Milestone' and (plannedEndDate>'$startDateMile' or realEndDate>'$startDateMile') ) )";
    } else {
      $queryWhere.="( refType='Project' or refType='Milestone')";
    }
  } else {
    if ($global) $queryWhere.="(1=1)"; // on GlobalPlanning, restriction on acces is applied on query in the FROM 
    else {
      $queryWhere.='( ('.getAccesRestrictionClause('Activity',$table,$showIdleProjects).')';
      if($showProjectModel=='all') $queryWhere.=  ' or '.$table . ".idProject in " . Project::getTemplateInClauseList() ;
      else if($showProjectModel=='no') $queryWhere.=  ' and '.$table . ".idProject not in " . Project::getTemplateInClauseList() ;
      $queryWhere.=')';
    }
  }
  if ( pq_array_key_exists('report',$_REQUEST) ) {
    if (pq_array_key_exists('idProject',$_REQUEST) and $_REQUEST['idProject']!=' ') {
      $queryWhere.= ($queryWhere=='')?'':' and ';
      $queryWhere.=  $table . ".idProject in " . getVisibleProjectsList(! $showIdleProjects, $_REQUEST['idProject']) ;
    }
  } else {
  	$queryWhere.= ($queryWhere=='')?'':' and ';
    $queryWhere.=  '( (' . $table . ".idProject in " . getVisibleProjectsList(! $showIdleProjects).')' ;
    // Show Templates
    if($showProjectModel=='all') $queryWhere.= ' or '.$table . ".idProject in " . Project::getTemplateInClauseList() ;
    else if($showProjectModel=='no') $queryWhere.=  ' and '.$table . ".idProject not in " . Project::getTemplateInClauseList() ;
    $queryWhere.= ')';
  }
  // Remove administrative projects :
  $queryWhere.= ($queryWhere=='')?'':' and ';
  $queryWhere.=  $table . ".idProject not in " . Project::getAdminitrativeProjectList() ;

  $querySelect .= $table . ".* ";
  $queryOrderBy .= $table . ".wbsSortable ";
  if ($global) {
    $queryFrom .= GlobalPlanningElement::getTableNameQuery() .' as '. $table;
  } else {
    $queryFrom .= $table;
  }
  
  $showMilestone=false;
  if ($portfolio) {
  	$queryWhere.=' and ( refType=\'Project\' ';
    if (pq_array_key_exists('showMilestone',$_REQUEST) ) {
      $showMilestone=pq_trim($_REQUEST['showMilestone']);
    } else if (pq_array_key_exists('listShowMilestone',$_REQUEST) ) {
      $showMilestone=pq_trim($_REQUEST['listShowMilestone']);
    } else {
  	  $showMilestoneObj=SqlElement::getSingleSqlElementFromCriteria('Parameter',array('idUser'=>$user->id,'idProject'=>null,'parameterCode'=>'planningShowMilestone'));
      $showMilestone=pq_trim($showMilestoneObj->parameterValue);
    }
    if ($showMilestone) {
  	  $queryWhere.=' or refType=\'Milestone\' ';
    }
  	$queryWhere.=')';
  }
  // Retreive baseline info
  $arrayBase=array();
  $arrayBase['top']=array();
  $arrayBase['bottom']=array();
  $arrayBase['list']=array();
  if ($baselineTop) $arrayBase['list']['top']=$baselineTop;
  if ($baselineBottom) $arrayBase['list']['bottom']=$baselineBottom;
  $peb=new PlanningElementBaseline();
  $pebTable=$peb->getDatabaseTableName();
  foreach ($arrayBase['list'] as $pos=>$id) {
    $query='select refType as itemtype, refId as itemid,' 
    . ' coalesce(plannedStartDate,validatedStartDate,initialStartDate) as startdate,'
    . ' coalesce(plannedEndDate,validatedEndDate,initialEndDate) as enddate'
    . ' from ' . $pebTable
    . ' where ' . pq_str_replace('planningelement','planningelementbaseline',$queryWhere) . ' and idBaseline='.Sql::fmtId($id)
    . ' order by ' . pq_str_replace('planningelement','planningelementbaseline',$queryOrderBy);
    $resBase=Sql::query($query);
   while ($base = Sql::fetchLine($resBase)) {
     if ($base['startdate'] and $base['enddate'] and $base['itemtype'] and $base['itemid']) {
       $arrayBase[$pos][$base['itemtype'].'_'.$base['itemid']]=array('start'=>$base['startdate'],'end'=>$base['enddate']);
     }
   }
  }
  
 // Apply restrictions on Filter
  $filterPlanningElement=new PlanningElement();
  $filterPlanningElementTable=$filterPlanningElement->getDatabaseTableName();
  $querySelectFilter="$filterPlanningElementTable.id as id, $filterPlanningElementTable.wbsSortable as wbs";
  $queryFromFilter="$filterPlanningElementTable";
  $queryWhereFilter="1=1 ";
  $queryOrderByFilter="$filterPlanningElementTable.id asc";
  $applyFilter=false;
  $arrayFilter=jsonGetFilterArray('Planning', false);
  foreach ($arrayFilter as $key=>$filter) {
    $filterAttribute=(isset($filter['sql']['attribute']))?$filter['sql']['attribute']:'';
    $filterOperator=(isset($filter['sql']['operator']))?$filter['sql']['operator']:'';
    if ($filterOperator=='SORT') {
      unset($arrayFilter[$key]);
      continue;
    }
    if (!$filterAttribute) {
      unset($arrayFilter[$key]);
      continue;
    }
    if (!planningGetFilterAttributeScope($filterAttribute)) {
      if (property_exists($filterPlanningElement, $filterAttribute)) {
        $arrayFilter[$key]['sql']['attribute']='PlanningElement_'.$filterAttribute;
      } else {
        unset($arrayFilter[$key]);
      }
    }
  }
  $arrayRestrictWbs=array();
  $cpt=0;
  if (count($arrayFilter)>0 and ! $portfolio and !$global) {
    $applyFilter=true;
    planningBuildWhereCriteria($queryFromFilter,$queryWhereFilter,$cpt,$arrayFilter,$filterPlanningElement);
    $queryFilter='select ' . $querySelectFilter
    . ' from ' . $queryFromFilter
    . ' where ' . $queryWhereFilter
    . ' order by ' . $queryOrderByFilter;
    $resultFilter=Sql::query($queryFilter);
    $lstFilterWbs="('0'";
    while ($line = Sql::fetchLine($resultFilter)) {
      //$arrayRestrictWbs[$line['wbs']]=$line['id'];
      $wbsExplode=pq_explode('.',$line['wbs']);
      $wbsParent="";
      foreach ($wbsExplode as $wbsTemp) {
        $wbsParent=$wbsParent.(($wbsParent)?'.':'').$wbsTemp;
        if (!isset($arrayRestrictWbs[$wbsParent])) {
          $arrayRestrictWbs[$wbsParent]=$line['id'];
          $lstFilterWbs.=",'$wbsParent'";
        } else {
          //$arrayRestrictWbs[$wbsParent].=','.$line['id'];
        }
      }
    }
    $lstFilterWbs.=")";
    //$queryWhere.=" and wbs in $lstFilterWbs";
    ksort($arrayRestrictWbs);
  }
  $limitDisplay=(Parameter::getGlobalParameter('limitDisplayPlanning')!='')?Parameter::getGlobalParameter('limitDisplayPlanning'):2000;
  $limitDisplayQuery=$limitDisplay+1;
  // Extra fields for Activities
  $act=new Activity();$actTable=$act->getDatabaseTableName();
  $querySelectLeftAct=", $actTable.idStatus as activitystatus, $actTable.idActivityType as activitytype, $actTable.idActivity as activityparent "
                     .", $actTable.fixPlanning as activityfixplanning, $actTable.workOnRealTime as activityworkonrealtime "
                     .", $actTable.tags as activitytags ";
  $queryFromLeftAct=" left join $actTable on $table.refType='Activity' and $table.refId=$actTable.id ";
  $querySelectLeftOrigin="";
  $queryFromLeftOrigin="";
  if ($target=='planning') {
    $origin=new Origin();
    $originTable=$origin->getDatabaseTableName();
    $querySelectLeftOrigin=", originplan.originType as origintype, originplan.originId as originid ";
    $queryFromLeftOrigin=" left join $originTable as originplan on $table.refType='Activity' and $table.refId=originplan.refId and originplan.refType='Activity' and originplan.idle=0 ";
  }
  // Extra fields for Project
  $proj=new Project();$projTable=$proj->getDatabaseTableName();
  $querySelectLeftProj=", $projTable.idStatus as projectstatus, $projTable.idProjectType as projecttype"
                      .", $projTable.isUnderConstruction as projectisunderconstruction, $projTable.fixPlanning as projectfixplanning"
                      .", $projTable.tags as projecttags";
  if ($portfolio) $querySelectLeftProj.=", $projTable.idHealth as projecthealth, $projTable.idQuality as projectquality";
  if ($portfolio) $querySelectLeftProj.=", $projTable.idTrend as projecttrend, $projTable.idOverallProgress as projectoverallprogress";
  
  if($target=='planning'){
    $listActivityFields = $act->getFieldsList();
    //$listProjectFields = SqlList::getListWithCrit('ColumnSelector', array('objectClass'=>'PortfolioPlanning', 'idUser'=>$user->id, 'hidden'=>'0'), 'attribute');
    foreach ($listActivityFields as $fld){
      $dataType = $act->getDataType($fld);
      $dataLength = $act->getDataLength($fld);
      $field = $fld;
      $databaseField = $act->getDatabaseColumnName($field);
      $lowField = pq_strtolower($field);
      if(pq_strpos($querySelectLeftAct, $field))continue;
      if($act->isAttributeSetToField($field, "hidden"))continue;
      if(pq_strpos($lowField, "unit") !== false or $field == 'tags' or $field == 'idWeightMode' or $field == 'idProject' or $field == 'idActivityType' or $field=='color' or $field=='idActivityPlanningMode' or $field == 'originId'
          or $field == 'originType' or $field == 'idResource' or $field == 'targetValue' or $field == 'actualValue' or $field == 'nbVoted' or $field == 'pctRate')continue;
      if($dataType == 'undefined' or ((($dataType == 'varchar' or $dataType == 'mediumtext') and $dataLength > 200) and $field!='tags'))continue;
      if(property_exists($act, $field))$querySelectLeftAct.=", $actTable.$databaseField as $lowField";
    }
    $act = new Activity();
    $listActivityFields = SqlList::getListWithCrit('ColumnSelector', array('objectClass'=>'Planning', 'idUser'=>$user->id, 'hidden'=>'0'), 'attribute');
  }
  
  if($portfolio){
    $listProjectFields = $proj->getFieldsList();
    //$listProjectFields = SqlList::getListWithCrit('ColumnSelector', array('objectClass'=>'PortfolioPlanning', 'idUser'=>$user->id, 'hidden'=>'0'), 'attribute');
    foreach ($listProjectFields as $field){
      $dataType = $proj->getDataType($field);
      $dataLength = $proj->getDataLength($field);
      if($field == 'tags' or $field == 'isUnderConstruction' or $field == 'idProjectType' or $field == 'fixPlanning' or $field=='color'
      or $field == 'idQuality' or $field == 'idHealth' or $field == 'idTrend' or $field == 'idOverallProgress')continue;
      if($dataType == 'undefined' or ((($dataType == 'varchar' or $dataType == 'mediumtext') and $dataLength > 200) and $field!='tags'))continue;
      if(pq_strpos($querySelectLeftProj, $field))continue;//property_exists('ProjectPlanningElement', $field) or 
      if($proj->isAttributeSetToField($field, "hidden"))continue;
      $lowField = pq_strtolower($field);
      $querySelectLeftProj.=", $projTable.$field as $lowField";
    }
    $proj = new Project();
    //$listProjectFields = $proj->getFieldsArray(true);
    $listProjectFields = SqlList::getListWithCrit('ColumnSelector', array('objectClass'=>'PortfolioPlanning', 'idUser'=>$user->id, 'hidden'=>'0'), 'attribute');
  }
  $queryFromLeftProj=" left join $projTable on $table.refType='Project' and $table.refId=$projTable.id ";
  if ($portfolio) $querySelectLeftAct="";
  if ($portfolio) $queryFromLeftAct="";
  if (count($arrayRestrictWbs)>0 and pq_strlen($lstFilterWbs)<100000) $queryWhere.=(($queryWhere=='')?'':' and ').' wbsSortable in '.$lstFilterWbs; // Avoid too long Query
  $queryWhere=($queryWhere=='')?' 1=1':$queryWhere;
  // constitute query and execute
  $query='SELECT ' . $querySelect . $querySelectLeftAct . $querySelectLeftOrigin . $querySelectLeftProj
       . "\n FROM " . $queryFrom . $queryFromLeftAct . $queryFromLeftOrigin . $queryFromLeftProj
       . "\n WHERE " . $queryWhere
       . "\n ORDER BY " . $queryOrderBy;
  if($outMode != 'csv' ) {
    //if ($queryNbLines) $query.= "\n LIMIT ".$queryStartLine.','.$queryNbLines;
  }
  if($outMode != 'csv' and getSessionValue('showAllGanttLines')!='true' and count($arrayRestrictWbs)==0 and !$portfolio) $query.= "\n LIMIT ".$limitDisplayQuery;
  
  $result=Sql::query($query);
  if (isset($debugJsonQuery) and $debugJsonQuery) { // Trace in configured to
     debugTraceLog("jsonPlanning: ".$query); // Trace query
     debugTraceLog("  => error (if any) = ".Sql::$lastQueryErrorCode.' - '.Sql::$lastQueryErrorMessage);
     debugTraceLog("  => number of lines returned = ".Sql::$lastQueryNbRows);
  }
  $nbQueriedRows=Sql::$lastQueryNbRows;
  if ($applyFilter and count($arrayRestrictWbs)==0) {
    $nbQueriedRows=0;
  }
    
  $nbRows=0;
  if ($print) {
    if ( pq_array_key_exists('report',$_REQUEST) ) {
      $test=array();
      if ($nbQueriedRows > 0) $test[]="OK";
      if (checkNoData($test))  exit;
    }
    if ($outMode=='mpp') {
    	exportGantt($result,$displayLikePlanning);
    } else {
    	displayGantt($result,$displayLikePlanning);
    }
  } else {
    // return result in json format
    $na=Parameter::getUserParameter('notApplicableValue');
    $planningDecimalSeparator=(pq_strtolower(pq_substr($currentLocale, 0, 2))=='fr')?',':'.';
    $projectNotStartBeforeValidatedDate=(Parameter::getGlobalParameter("notStartBeforeValidatedStartDate")=='YES')?true:false;
    $arrayProjectStart=array();
    $na=pq_trim($na,"'");
    if (!$na) $na=null;
    $arrayObj=array();
    $rootWbsArray=array();
    $d=new Dependency();
    echo '{"identifier":"id",' ;
    echo ' "items":[';
    $cptQueryLines=0;
    $cptFullLines=0;
    $lastFullLine=0;
    $firstFullLine=0;
    $cptPartialLines=0;
    $cptHiddenLines=0;
    $firstHiddenLine=0;
    $lastHiddenLine=0;
    $cptVisible=0;
    $needRefresh=false;
    if ($nbQueriedRows > 0 and ($queryStartLine==null or $queryStartLine<$nbQueriedRows)) {
    	$collapsedList=Collapsed::getCollaspedList();
    	$topProjectArray=array();
      $cp=0;
      $currentCollapsedWbs=null;
      $planningPage=Parameter::getPlanningPageLineCount();
      $largeQuery=($planningPage and $nbQueriedRows>$planningPage)?true:false; // SET VALUE FOR LARGE QUERIES
      $arrayTopIdProject=array();
      //if ($portfolio) $largeQuery=true;
      while ($line = Sql::fetchLine($result)) {
        //$queryNbLine;
        $line['health']='';
        $line['quality']='';
        $line['trend']='';
        $line['overallprogress']='';
      	$line=array_change_key_case($line,CASE_LOWER);
        $line['tags']='';
        if (isset($columnsDescription['Tags']) and $columnsDescription['Tags']['show']==1) {
          if ($line['reftype']=='Activity' and isset($line['activitytags'])) {
            $line['tags']=$line['activitytags'];
          } else if ($line['reftype']=='Project' and isset($line['projecttags'])) {
            $line['tags']=$line['projecttags'];
          } else if (property_exists($line['reftype'], 'tags')) {
            $line['tags']=SqlList::getFieldFromId($line['reftype'], $line['refid'], 'tags');
          }
        }
      	if ($portfolio && $line['reftype']=='Project') $arrayTopIdProject[$line['refid']]=$line['id'];
      	if ($line['reftype']=='Milestone' and $portfolio and $showMilestone and $showMilestone!='all' ) {
      	  if (SqlList::getFieldFromId('Milestone', $line['refid'], 'idMilestoneType')!=$showMilestone) {
      	    continue;
      	  }
      	}
      	if ($portfolio and $line['reftype']=='Milestone' and $line['topreftype']!='Project' && !isset($topProjectArray[$line['idproject']]) ) { // Case project is closed containing non closed Milestone
      	  continue;
      	}
//       	if ($portfolio and $line['reftype']=='Milestone' and $startDate) { // $startDate never set ???
//       	  $pStart="2000-01-01";
//       	  if (trim($line['realstartdate'])) $pStart=$line['realstartdate'];
//       	  else if (trim($line['plannedstartdate'])) $pStart=$line['plannedstartdate'];
//       	  else if (trim($line['validatedstartdate'])) $pStart=$line['validatedstartdate'];
//       	  if ($pStart<$startDate) continue;
//       	}
      	$cptQueryLines++;
      	//if (!$portfolio or $line['reftype']!='Milestone') $cptQueryLines++;
      	//if ($queryStartLine!==null and $cptQueryLines<$queryStartLine) continue;
      	if ($largeQuery and $queryHiddenLines and $queryNbLines!==null and $cptFullLines>=$queryNbLines) {
      	  $needRefresh=true;
      	  break;	
      	}
      	//if ($queryHiddenLines and $queryNbLines!==null and $cptFullLines>=$queryNbLines) break;
      	if ($currentCollapsedWbs and pq_substr($line['wbssortable'],0,pq_strlen($currentCollapsedWbs))==$currentCollapsedWbs) {
          // OK  
      	}  else {
      	  $currentCollapsedWbs=null;
      	}
      	//if ($immediateRefresh and $queryStartLine!==null and $cptQueryLines<$queryStartLine) continue; // NEW
      	if ($applyFilter and !isset($arrayRestrictWbs[$line['wbssortable']])) continue; // Filter applied and item is not selected and not a parent of selected
      	if ( $largeQuery and (
      	     ($queryHiddenLines==false and $currentCollapsedWbs)
      	     // ($queryHiddenLines==false and ($currentCollapsedWbs and (!$portfolio or $line['reftype']=='Project') ) )
      	  or $cptVisible>=$queryNbLines 
      	  or ($queryHiddenLines==true and $cptQueryLines<$queryStartLine)
      	  or ($immediateRefresh and $queryStartLine!==null and $cptQueryLines<$queryStartLine)
      	   ) ) {
      	  if ($queryHiddenLines==false and $currentCollapsedWbs) {
      	    $cptHiddenLines++;
      	    $lastHiddenLine=$cptQueryLines;
      	    if (!$firstHiddenLine) $firstHiddenLine=$cptQueryLines;
      	    $needRefresh=true;
      	  }
      	  $cptPartialLines++;
      	  echo (++$nbRows>1)?',':'';
      	  echo  '{';
    	    echo '"id":"'.$line['id'].'","partialQuery":"1"';
    	    echo ',"reftype":"'.$line['reftype'].'","refid":"'.$line['refid'].'","refname":"'.htmlEncode(htmlEncodeJson($line['refname'])).'"';
    	    if ($portfolio and $line['reftype']=='Milestone' and isset($arrayTopIdProject[$line['idproject']])) {
    	      echo ',"topid":"'.htmlEncode($arrayTopIdProject[$line['idproject']]).'","topreftype":"Project","toprefid":"'.$line['idproject'].'"';
    	    } else {
    	      echo ',"topid":"'.htmlEncode($line['topid']).'","topreftype":"'.$line['topreftype'].'","toprefid":"'.$line['toprefid'].'"';
    	    }
    	    echo ',"elementary":"'.$line['elementary'].'"';
    	    echo ',"wbssortable":"'.htmlEncode($line['wbssortable']).'","wbs":"'.htmlEncode($line['wbs']).'"';
    	    echo ',"validatedstartdate":"'.$line['validatedstartdate'].'","validatedenddate":"'.$line['validatedenddate'].'"';
    	    echo ',"plannedstartdate":"'.$line['plannedstartdate'].'","plannedenddate":"'.$line['plannedenddate'].'"';
    	    echo ',"realstartdate":"'.$line['realstartdate'].'","realenddate":"'.$line['realenddate'].'"';
    	    echo ',"inheritedenddate":"'.($line['inheritedenddate']??'').'"';
    	    echo ',"color":"'.pq_trim($line['color'],'#').'"';
    	    echo ',"idplanningmode":"'.$line['idplanningmode'].'"';
    	    echo ',"done":"'.$line['done'].'"';
    	    $refItem=$line['reftype'].'_'.$line['refid'];
    	    $refItemCollapsed=pq_str_replace(array('Fixed','Replan','Construction'), 'Project', $refItem);
    	    $scope = 'Planning_'.$refItemCollapsed;
    	    if (isset($collapsedList[$scope])) {
    	      echo ',"collapsed":"1"';
  	          Collapsed::collapse($scope);
    	    } else {
    	      echo ',"collapsed":"0"';
  	          Collapsed::expand($scope);
    	    }
    	    //
    	    echo '}';
    	    //if (!$portfolio or $line['reftype']!='Milestone') $cp++;
    	    $cp++;
    	    if($cp>=$limitDisplay && getSessionValue('showAllGanttLines')!='true' && (!$portfolio or $line['reftype']!='Milestone')){
    	      echo ',{"id":"0","msgErrorDisplay":"'.i18n('limitedDisplay',array($limitDisplay)).'"}';
    	      break;
    	    }
    	    continue;
      	}
      	//if ($queryNbLines!==null and $cptVisible>$queryNbLines) {continue;}
      	if ($line['id'] and !$line['refname']) { // If refName not set, delete corresponding PE (results from incorrect delete
      	  $peDel=new PlanningElement($line['id'],true);
      	  $peDel->delete();
      	  continue;
      	}
        //$cptFullLines++;
        if (!$portfolio or $line['reftype']!='Milestone') $cptFullLines++;
        if (!$firstFullLine) $firstFullLine=$cptQueryLines;
        $lastFullLine=$cptQueryLines;
        echo (++$nbRows>1)?',':'';
        echo  '{';
        $nbFields=0;
        $idPe='';
        
        // NEW
        if (isset($line['isglobal']) and $line['isglobal']==1 and $line['progress']==$na) {
          // If real is set, start must be lower...
          if (pq_trim($line['realenddate']) and $line['realenddate']!=$na) {
            if (pq_trim($line['realstartdate']) and $line['realstartdate']!=$na and $line['realstartdate']>$line['realenddate']) {
              $line['realstartdate']=$line['realenddate'];
            }
            if (pq_trim($line['plannedstartdate']) and $line['plannedstartdate']!=$na and $line['plannedstartdate']>$line['realenddate']) {
              $line['plannedstartdate']=$line['realenddate'];
            }
            if (pq_trim($line['plannedenddate']) and $line['plannedenddate']!=$na and $line['plannedenddate']>$line['realenddate']) {
              $line['plannedenddate']=$line['realenddate'];
            }
          }
          if ($line['reftype']=='Ticket' and $line['validatedwork']>0 and $line['realwork']>0) {// Ticket by work
            if (pq_trim($line['realenddate'])!='' and $line['realenddate']!=$na and $line['leftwork']==0) {
              $line['progress']='100';
            } else {
              $line['progress']=round(100*$line['realwork']/$line['validatedwork'],0);
            }
          } else if (pq_trim($line['realenddate']) and $line['realenddate']!=$na) { // is started, so try and get progress from duration
            $line['progress']='100';
          } else if (pq_trim($line['realstartdate']) and $line['realstartdate']!=$na) { // is started, so try and get progress from duration 
            $pStart='';
            $pStart=(pq_trim($line['initialstartdate'])!='' and $line['initialstartdate']!=$na)?$line['initialstartdate']:$pStart;
            $pStart=(pq_trim($line['validatedstartdate'])!='' and $line['validatedstartdate']!=$na)?$line['validatedstartdate']:$pStart;
            $pStart=(pq_trim($line['plannedstartdate'])!='' and $line['plannedstartdate']!=$na)?$line['plannedstartdate']:$pStart;
            $pStart=(pq_trim($line['realstartdate']!='' and $line['realstartdate']!=$na)!='')?$line['realstartdate']:$pStart;
            if (pq_trim($line['plannedstartdate'])!='' and $line['plannedstartdate']!=$na 
            and pq_trim($line['realstartdate'])!='' and $line['realstartdate']!=$na
            and $line['plannedstartdate']<$line['realstartdate'] ) {
              $pStart=$line['plannedstartdate'];
            }
            $pEnd='';
            $pEnd=(pq_trim($line['initialenddate'])!='' and $line['initialenddate']!=$na)?$line['initialenddate']:$pEnd;
            $pEnd=(pq_trim($line['validatedenddate'])!='' and $line['validatedenddate']!=$na)?$line['validatedenddate']:$pEnd;
            $pEnd=(pq_trim($line['plannedenddate'])!='' and $line['plannedenddate']!=$na)?$line['plannedenddate']:$pEnd;
            $pEnd=(pq_trim($line['realenddate'])!='' and $line['realenddate']!=$na)?$line['realenddate']:$pEnd;
            //if ($pEnd=='') {$pEnd=date('Y-m-d');}
            if ($line['reftype']=='Milestone') {
              $pStart=$pEnd;
            }
            $pStart=pq_substr($pStart,0,10);
            $pEnd=pq_substr($pEnd,0,10);
            if ($line['reftype']=='Decision') {
              if ($line['done']==1) $line['progress']='100';
              else $line['progress']='0';
            } else if (pq_trim($line['realenddate'])!='' and $line['realenddate']!=$na) {
              $line['progress']='100';
            } else if ($pStart==$pEnd) {
              $line['progress']='50';
            } else {
              $taskLength=dayDiffDates($pStart,$pEnd)+1;
              if ($taskLength>0) {
                $progressLength=dayDiffDates($pStart,date('Y-m-d'))+1;
                $line['progress']=round($progressLength/$taskLength*100,0);
              } else {
                $line['progress']='50';
              }
            }
          } else {
            $line['progress']='0';
          }
          if (intval($line['progress'])>100) $line['progress']='100';
          if (pq_strpos($line['wbs'],'._#')!==false) {
            $rootWbs=pq_substr($line['wbs'],0,pq_strpos($line['wbs'],'._#'));
            if (! isset($rootWbsArray[$rootWbs])) {
              $rootWbsSortable=formatSortableWbs($rootWbs);
              $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('wbsSortable'=>$rootWbsSortable));
              $topId=$pe->id;
              //$max=pq_substr($pe->getMaxValueFromCriteria('wbsSortable',array('topId'=>$topId)),-3);
              //$rootWbsArray[$rootWbs]=array('topId'=>$topId,'val'=>$max);
              $rootWbsArray[$rootWbs]=array('topId'=>$topId,'val'=>0);
            }
            $rootWbsArray[$rootWbs]['val']+=1;
            $wbsVal=$rootWbsArray[$rootWbs]['val'];
            $line['wbs']=$rootWbs.'._'.$wbsVal;
            $line['wbs']=''; // Hide WBS
            $line['wbssortable']=formatSortableWbs($line['wbs']);
            $line['topid']= $rootWbsArray[$rootWbs]['topId'];
          }
        } else if ($line['plannedwork']>0 and $line['leftwork']==0 and $line['elementary']==1 ) {
          $pmCode=SqlList::getFieldFromId('PlanningMode',$line['idplanningmode'],'code');
          if ($pmCode!='FDUR' and $pmCode!='DDUR' and $pmCode!='CDUR') {
            $line['plannedstartdate']='';
        	  $line['plannedenddate']='';
          }
        }
        if ($projectNotStartBeforeValidatedDate) {
          if ($line['reftype']=='Project') {
            $arrayProjectStart[$line['refid']]=$line['validatedstartdate'];
          } 
        }
        if (! $line['plannedduration'] and $line['validatedduration']) { // Initialize planned duration to validated
          if (!$line['plannedstartdate']) {
            $pStart=date('Y-m-d');
            if (isset($arrayProjectStart[$line['idproject']]) and pq_trim($arrayProjectStart[$line['idproject']])!='') {
              $pStart=$arrayProjectStart[$line['idproject']];
            }
            $line['plannedstartdate']=($line['validatedstartdate'])?$line['validatedstartdate']:$pStart;
          }
          $line['plannedduration']=$line['validatedduration'];
          $line['plannedenddate']=addWorkDaysToDate($line['plannedstartdate'], $line['validatedduration'], $line['idproject']);
        }
        
        $line['validatedworkdisplay']=($line['validatedwork']==$na)?$na:Work::displayWorkWithUnit($line['validatedwork']);
        $line['assignedworkdisplay']=($line['assignedwork']==$na)?$na:Work::displayWorkWithUnit($line['assignedwork']);
        $line['realworkdisplay']=($line['realwork']==$na)?$na:Work::displayWorkWithUnit($line['realwork']);
        $line['leftworkdisplay']=($line['leftwork']==$na)?$na:Work::displayWorkWithUnit($line['leftwork']);
        $line['plannedworkdisplay']=($line['plannedwork']==$na)?$na:Work::displayWorkWithUnit($line['plannedwork']);
        $line['validatedcostdisplay']=($line['validatedcost']==$na)?$na:htmlDisplayCurrency($line['validatedcost'],true);
        $line['assignedcostdisplay']=($line['assignedcost']==$na)?$na:htmlDisplayCurrency($line['assignedcost'],true);
        $line['realcostdisplay']=($line['realcost']==$na)?$na:htmlDisplayCurrency($line['realcost'],true);
        $line['leftcostdisplay']=($line['leftcost']==$na)?$na:htmlDisplayCurrency($line['leftcost'],true);
        $line['plannedcostdisplay']=($line['plannedcost']==$na)?$na:htmlDisplayCurrency($line['plannedcost'],true);
        $line['validateddurationdisplay']=($line['validatedduration']==$na)?$na:Work::displayWorkWithUnit($line['validatedduration']);
        if (isset($line['unitweight'])) {
          $line['unitweightdisplay']=pq_str_replace('.', $planningDecimalSeparator, $line['unitweight']);
        }
        if (isset($line['minimumthreshold'])) {
          $line['minimumthresholddisplay']=pq_str_replace('.', $planningDecimalSeparator, $line['minimumthreshold']);
        }
        if ($line['reftype']=='Milestone') {
          $line['validateddurationdisplay']='-';
          $line['planneddurationdisplay']='-';
          $line['realdurationdisplay']='-';
        }
        $line['hidden']=0;
        if ($columnsDescription['IdStatus']['show']==1 or $columnsDescription['Type']['show']==1 
        or ($columnsDescription['IdHealthStatus']['show']==1 and $portfolio)
        or ($columnsDescription['QualityLevel']['show']==1 and $portfolio ) 
        or ($columnsDescription['IdTrend']['show']==1 and $portfolio) 
        or ($columnsDescription['IdOverallProgress']['show']==1 and $portfolio)
        or Parameter::getGlobalParameter('hideItemTypeRestrictionOnProject')=='YES' ) {
          $ref=$line['reftype'];
          //$type='id'.$ref.'Type';
          $type=SqlElement::getTypeName($ref);
          if (Parameter::getGlobalParameter('hideItemTypeRestrictionOnProject')=='YES' 
          and property_exists($ref, $type) and property_exists($ref, 'idProject')) {
            $prj=($ref=='Project')?$line['refid']:$line['idproject'];
            if (! RestrictType::isTypeVisibleForProject($ref, SqlList::getFieldFromId($ref,$line['refid'],$type), $prj)) {
              $line['hidden']=1;
            }            
          }
          if($columnsDescription['IdStatus']['show']==1 or $columnsDescription['Type']['show']==1){
            $fldStatus=strtolower($ref.'status');
            $fldType=strtolower($ref.'type');
            if (isset($line['idstatus']) and isset($line['idtype']) and $line['idstatus']) {
              $line['status']=SqlList::getNameFromId('Status',$line['idstatus']).'#split#'.SqlList::getFieldFromId('Status',$line['idstatus'],'color');
              $line['type']=SqlList::getNameFromId('Type',$line['idtype']);
            } else if (isset($line[$fldStatus]) and isset($line[$fldType]) ) {
              $line['status']=SqlList::getNameFromId('Status',$line[$fldStatus]).'#split#'.SqlList::getFieldFromId('Status',$line[$fldStatus],'color');
              $line['type']=SqlList::getNameFromId('Type',$line[$fldType]);
            } else {
              $line['status']=null;
              $line['idstatus']=null;
              if (property_exists($ref,'idStatus')) {
                $line['idstatus']=SqlList::getFieldFromId($ref, $line['refid'], 'idStatus');
                $line['status']=SqlList::getNameFromId('Status',$line['idstatus']).'#split#'.SqlList::getFieldFromId('Status',$line['idstatus'],'color');
              }
              $line['type']=null;
              $line['idtype']=null;
              if (property_exists($ref,$type)) {
                $line['idtype']=SqlList::getFieldFromId($ref, $line['refid'], $type);
                $line['type']=SqlList::getNameFromId('Type',$line['idtype']);
              }
            }
          }
          if($columnsDescription['IdHealthStatus']['show']==1 and $portfolio){
            $line['health']=null;
            $fldHealth=strtolower($ref.'health');
            if (property_exists($ref,'idHealth') and isset($line[$fldHealth])) {
              //$line['idhealth']=SqlList::getFieldFromId($ref,$line['refid'],'idHealth');
              $line['health']=SqlList::getNameFromId('Health',$line[$fldHealth]).'#split#'.SqlList::getFieldFromId('Health',$line[$fldHealth],'color');
            }
          }
          if($columnsDescription['QualityLevel']['show']==1 and $portfolio ){
            $line['quality']=null;
            $fldQuality=strtolower($ref.'quality');
            if (property_exists($ref,'idQuality') and isset($line[$fldQuality])) {
              //$line['idquality']=SqlList::getFieldFromId($ref,$line['refid'],'idQuality');       
              $line['quality']=SqlList::getNameFromId('Quality',$line[$fldQuality]).'#split#'.SqlList::getFieldFromId('Quality',$line[$fldQuality],'color');
            }
          }
          if($columnsDescription['IdTrend']['show']==1 and $portfolio ){
            $line['trend']=null;
            $fldTrend=strtolower($ref.'trend');
            if (property_exists($ref,'idTrend') and isset($line[$fldTrend])) {
              //$line['idtrend']=SqlList::getFieldFromId($ref,$line['refid'],'idTrend');
              $line['trend']=SqlList::getNameFromId('Trend',$line[$fldTrend]).'#split#'.SqlList::getFieldFromId('Trend',$line[$fldTrend],'color');
            }
          }
          if($columnsDescription['IdOverallProgress']['show']==1 and $portfolio ){
            $line['overallprogress']=null;
            $fldOverallProgress=strtolower($ref.'overallprogress');
            if (property_exists($ref,'idOverallProgress') and isset($line[$fldOverallProgress])) {
              //$line['idoverallprogress']=SqlList::getFieldFromId($ref,$line['refid'],'idOverallProgress');
              $line['overallprogress']=SqlList::getNameFromId('OverallProgress',$line[$fldOverallProgress]);
            }
          }
        }
        $line['iconClass']=$line['reftype'];
        if (isset($line['tags'])) $line['tagsdisplay']=tagFormatter($line['tags']);
        $line['planningmode']=SqlList::getNameFromId('PlanningMode',$line['idplanningmode']);
        if ($target=='planning' and $line['reftype']=='Activity' and isset($line['activityfixplanning'])) {
          $line['fixplanning']=$line['activityfixplanning'];
        } else if ($target=='planning' and $line['reftype']=='Project' and isset($line['projectfixplanning'])) {
          $line['fixplanning']=$line['projectfixplanning'];
        }
        if ($line['reftype']=='Project') {
        	$topProjectArray[$line['refid']]=$line['id'];
        	//$proj=new Project($line['refid'],true);
        	$isParentFixed = false;
        	if (isset($line['topid']) && $line['topid']) {
        	  $parentProjectObj = new ProjectPlanningElement($line['topid'], true);
        	  if ($parentProjectObj->fixPlanning == 1) {
        	    $isParentFixed = true;
        	  }
        	}
        	if ($line['projectisunderconstruction']==1) {
        	  $line['reftype']='Construction';
        	  $line['iconClass']='Construction';
        	}
        	if ($line['projectfixplanning']==1 || $isParentFixed) {
        	  $line['reftype']='Fixed';
        	  $line['iconClass']='Fixed';
        	} else if ( ! isset($plannableProjectsList[$line['refid']]) ) {
        	  $line['reftype']='Fixed';
        	  $line['iconClass']='Fixed  ';
        	} else if ($line['needreplan'] and $line['projectfixplanning']!=1 and isset($plannableProjectsList[$line['refid']])) {
        	  $line['reftype']='Replan';
        	  $line['iconClass']='Replan';
        	}
        } else if ($portfolio and $line['reftype']=='Milestone' and $line['topreftype']!='Project') {
          if (! isset($topProjectArray[$line['idproject']])) { // Case project is closed containing non closed Milestone
            $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>'Project','refId'=>$line['idproject']));
            $topProjectArray[$line['idproject']]=$pe->id;
          }
          $line['topid']=$topProjectArray[$line['idproject']];
        }else if($line['reftype']=='Activity'){
          //$activity=new Activity($line['refid'],true);
          if ($line['activityfixplanning']==1) {
            $line['iconClass']='Fixed';
          }
          if($line['activityworkonrealtime']==1 and Parameter::getGlobalParameter('activityOnRealTime')=='YES'){
            $line['iconClass']='OnRealTime';
          }
        }
        if($target == 'planning'){
          foreach ($listActivityFields as $field){
            $dataType = $act->getDataType($field);
            $dataLength = $act->getDataLength($field);
            $lowField = pq_strtolower($field);
            if(pq_substr($field, 0, 1) == '_')continue;
            if(pq_strpos($lowField, "unit") !== false or $lowField == 'tags' or $lowField == 'idWeightMode' or $lowField == 'idactivitytype' or $lowField == 'idresource' or $lowField=='idactivityplanningmode' or $lowField == 'originid'
                or $field == 'originType' or $field == 'idResource' or $field == 'targetValue' or $field == 'actualValue' or $field == 'nbVoted' or $field == 'pctRate')continue;
            if($dataType == 'undefined' or ((($dataType == 'varchar' or $dataType == 'mediumtext') and $dataLength > 200) and $field!='tags'))continue;
            if(!isset($line[$lowField]) && $lowField != 'idactivity')continue;
            if(pq_substr($field,0,4) != 'idle' and isForeignKey(lcfirst($field)) ){
              $className = pq_substr(foreignKeyWithoutAlias(lcfirst($field)), 2);
              if(Security::checkValidClass($className)){
                if(property_exists('Activity','_customFields')){
                  if(in_array(lcfirst($field), Activity::$_customFields) and property_exists($className, 'color')){
                    $line[$lowField."color"]=htmlEncode(htmlEncodeJson(SqlList::getNameFromId($className,$line[$lowField]))).'#split#'.SqlList::getFieldFromId($className,$line[$lowField],'color');
                  }else{
                    if($lowField == 'idcontact'){
                      $line[$lowField.'display'] = htmlEncode(htmlEncodeJson(SqlList::getNameFromId('Affectable', $line[$lowField])));
                    }else if($lowField == 'idtargetproductversion' or $lowField == 'idtargetcomponentversion'){
                      $line[$lowField.'display'] = htmlEncode(htmlEncodeJson(SqlList::getNameFromId($className, $line[$lowField])));
                    }else if($lowField == 'idproject' or $lowField == 'idactivity'){
                      $val = ($lowField == 'idactivity')?$line['activityparent']:$line[$lowField];
                      $line[$lowField.'display'] = htmlEncode(htmlEncodeJson(SqlList::getFieldFromId($className, $val, $field)));
                    }else{
                      $line[$lowField] = htmlEncode(htmlEncodeJson(SqlList::getFieldFromId($className, $line[$lowField], $field)));
                    }
                  }
                }else{
                  if($lowField == 'idcontact'){
                    $line[$lowField.'display'] = htmlEncode(htmlEncodeJson(SqlList::getNameFromId('Affectable', $line[$lowField])));
                  }else if($lowField == 'idtargetproductversion' or $lowField == 'idtargetcomponentversion'){
                    $line[$lowField.'display'] = htmlEncode(htmlEncodeJson(SqlList::getNameFromId($className, $line[$lowField])));
                  }else if($lowField == 'idproject' or $lowField == 'idactivity'){
                    $val = ($lowField == 'idactivity')?$line['activityparent']:$line[$lowField];
                    $line[$lowField.'display'] = htmlEncode(htmlEncodeJson(SqlList::getFieldFromId($className, $val, $field)));
                  }else{
                    $line[$lowField] = htmlEncode(htmlEncodeJson(SqlList::getFieldFromId($className, $line[$lowField], $field)));
                  }
                }
              }else{
                $line[$lowField]='';
              }
            }
            if (false !== pq_strpos($lowField, 'cost') or false !== pq_strpos($lowField, 'bill') or false !== pq_strpos($lowField, 'expense')) {
              if($lowField != 'validatedcost' and $lowField != 'assignedcost' and $lowField != 'realcost' and $lowField != 'leftcost' and $lowField != 'plannedcost'){
                $line[$lowField."display"]=htmlDisplayCurrency($line[$lowField]);
              }
            }
            if (false !== pq_strpos($lowField, 'work') or false !== pq_strpos($lowField, 'duration')) {
              if($lowField != 'validatedwork' and $lowField != 'assignedwork' and $lowField != 'realwork' and $lowField != 'leftwork' and $lowField != 'plannedwork'){
                $line[$lowField."display"]=Work::displayWorkWithUnit($line[$lowField]);
              }
            }
          }
          $line['origin']='';
          $line['origindisplay']='';
          if ($line['reftype']=='Activity' and isset($line['origintype']) and isset($line['originid']) and $line['origintype'] and $line['originid']) {
            $line['origin']=$line['origintype'].'#'.$line['originid'];
            $line['origindisplay']=i18n($line['origintype']).'#'.$line['originid'];
          }
        }
        
        if($portfolio){
          foreach ($listProjectFields as $field){
            $dataType = $proj->getDataType($field);
            $dataLength = $proj->getDataLength($field);
            $lowField = pq_strtolower($field);
            if(pq_substr($field, 0, 1) == '_')continue;
            if($field == 'tags' or $field == 'isUnderConstruction' or $field == 'idProjectType' or $field == 'fixPlanning' or $field == 'idQuality' or $field == 'idHealth' or $field == 'idTrend' or $field == 'idOverallProgress' or $field == 'IdResource')continue;
            if($dataType == 'undefined' or ((($dataType == 'varchar' or $dataType == 'mediumtext') and $dataLength > 200) and $field!='tags'))continue;
            if(!isset($line[$lowField]))continue; 
            if(pq_substr($field,0,4) != 'idle' and isForeignKey(lcfirst($field)) ){
              $className = pq_substr(foreignKeyWithoutAlias(lcfirst($field)), 2);
              if(Security::checkValidClass($className)){
                if(property_exists('Project','_customFields')){
                  if(in_array(lcfirst($field), Project::$_customFields) and property_exists($className, 'color')){
                    $line[$lowField."color"]=htmlEncode(htmlEncodeJson(SqlList::getNameFromId($className,$line[$lowField]))).'#split#'.SqlList::getFieldFromId($className,$line[$lowField],'color');
                  }else{
                    $line[$lowField] = htmlEncode(htmlEncodeJson(SqlList::getFieldFromId($className, $line[$lowField], $field)));
                  }
                }else{
                  $line[$lowField] = htmlEncode(htmlEncodeJson(SqlList::getFieldFromId($className, $line[$lowField], $field)));
                }
              }else{
                $line[$lowField]='';
              }
//             }else if($dataType == 'date'){
//               $line[$lowField] = htmlFormatDate($line[$lowField]);
//             }else if($dataType == 'datetime'){
//               $line[$lowField] = htmlFormatDateTime($line[$lowField]);
            }
            if (false !== pq_strpos($lowField, 'cost') or false !== pq_strpos($lowField, 'bill')) {
              if($lowField != 'validatedcost' and $lowField != 'assignedcost' and $lowField != 'realcost' and $lowField != 'leftcost' and $lowField != 'plannedcost'){
                $line[$lowField."display"]=htmlDisplayCurrency($line[$lowField]);
              }
            }
            if (false !== pq_strpos($lowField, 'work')) {
              if($lowField != 'validatedwork' and $lowField != 'assignedwork' and $lowField != 'realwork' and $lowField != 'leftwork' and $lowField != 'plannedwork'){
                $line[$lowField."display"]=Work::displayWorkWithUnit($line[$lowField]);
              }
            }
          }
        }
        foreach ($line as $id => $val) {
          if ($val===null) {$val=' ';}
          if ($val=='') {$val=' ';}
          echo (++$nbFields>1)?',':'';
          //echo '"' . htmlEncode($id) . '":"' . htmlEncodeJson(($val)) . '"';
          if ($id=='refname' or $id=='resource') {
          	$val=htmlEncode(htmlEncodeJson($val));
          } else {
          	$val=htmlEncodeJson($val);
          }
          echo '"'.htmlEncode($id).'":"'.$val.'"';
          if ($id=='id') {$idPe=$val;}
        }
        //add expanded status
//         if($portfolio){
//            echo',"idhealthstatus":"sdfs"';
//            echo',"qualitylevel":"fffffff"';
//            echo',"idtrend":"dsfdsfsdfds"';
//         }
        $refItem=$line['reftype'].'_'.$line['refid'];
        $refItemCollapsed=pq_str_replace(array('Fixed','Replan','Construction'), 'Project', $refItem);
        $scope = 'Planning_'.$refItemCollapsed;
        if (isset($collapsedList[$scope]) and !isset($directObjectParents['#'.$line['id']]) ) {
        	echo ',"collapsed":"1"';
      	    Collapsed::collapse($scope);
        	if (!$currentCollapsedWbs) {
        	  $currentCollapsedWbs=$line['wbssortable'];
        	}
        } else {
        	echo ',"collapsed":"0"';
        	Collapsed::expand($scope);
        }
        if ($baselineTop and isset($arrayBase['top'][$refItem])) {
          echo ',"baseTopStart":"'.$arrayBase['top'][$refItem]['start'].'"';
          echo ',"baseTopEnd":"'.$arrayBase['top'][$refItem]['end'].'"';
        }
        if ($baselineBottom and isset($arrayBase['bottom'][$refItem])) {
          echo ',"baseBottomStart":"'.$arrayBase['bottom'][$refItem]['start'].'"';
          echo ',"baseBottomEnd":"'.$arrayBase['bottom'][$refItem]['end'].'"';
        }
        if ($line['reftype']!='Project' and $line['reftype']!='Fixed' and $line['reftype']!='Construction' and $line['reftype']!='Replan') {
          $arrayResource=array();
          // if ($showResource) { //
          if (isset($line['idresource']) and $line['idresource'] ) {
            $ass=new Assignment();
            $ass->idResource=$line['idresource'];
            $assList=array($line['idresource']=>$ass);
            $resp=$line['idresource'];
          } else { // Must always retreive resource to display value in column, even if not displayed
          	$crit=array('refType'=>$line['reftype'], 'refId'=>$line['refid'],'idle'=>'0');
            $ass=new Assignment();
            $assList=$ass->getSqlElementsFromCriteria($crit,false); 
            $resp="";	        
  	        if (isset($arrayObj[$line['reftype']])) {
  	          $objElt=$arrayObj[$line['reftype']];
  	        } else {
              $objElt=new $line['reftype']();
              if (! property_exists($objElt,'idResource')) {
                $objElt=null;
              }
              $arrayObj[$line['reftype']]=$objElt;
  	        }
  	        if ($objElt) {
  	          $resp=SqlList::getFieldFromId($line['reftype'], $line['refid'], 'idResource');
  	        }
          }

          $noAssignment=false;
          if (count($assList)==0) {
            $ass=new Assignment();
            $ass->idResource=$resp;
            $assList=array('0'=>$ass);
            $noAssignment=true;
          }
          
	        foreach ($assList as $ass) {       	
	        	$res=new ResourceAll($ass->idResource,true);
	        	if ($res->id and ! isset($arrayResource[$res->id])) {
  	        	$display=($displayResource=='NO')?null:$res->$displayResource;
  	        	if ($displayResource=='initials' and ! $display) {
  	        	  //$encoding=mb_detect_encoding($res->name, 'ISO-8859-1, UTF-8');
  	        	  //$display=$encoding;
  	        	  if ($res->name) 
  	        	    $words=pq_mb_split(' ',pq_str_replace(array('"',"'"), ' ', $res->name));
  	        	  else 
  	        	    $words=array();
  	        	  $display='';
  	        	  foreach ($words as $word) {
  	        	    $display.=(pq_mb_substr($word,0,1,'UTF-8'));
  	        	  }
  	        	}
  	        	if ($display)	{
  	        	  $arrayResource[$res->id]=htmlEncode(htmlEncodeJson($display));
  	        	  if ($resp and $resp==$res->id and !$noAssignment) {
  	        		  $arrayResource[$res->id]='<b>'.htmlEncode(htmlEncodeJson($display)).'</b>';
  	        	  } else if ($noAssignment) {
  	        	    $arrayResource[$res->id]='<i>'.htmlEncode(htmlEncodeJson($display)).'</i>';
  	        	  }
  	        	}
  	        }
          }
	        //$res=new Resource($ass->idResource);
	        echo ',"resource":"' . (implode(', ',$arrayResource)) . '"';
        } else {
          echo ',"resource":""';
        }
        if (!$portfolio) {
          if (isset($line['idresource']) and $line['idresource'] ) {
            $resp=$line['idresource'];
          } else { // Must always retreive responsible to display value in column, even if not displayed
            $resp="";
            $classRefType=($line['reftype']=='Fixed' or $line['reftype']=='Construction' or $line['reftype']=='Replan')?'Project':$line['reftype'];
            if (isset($arrayObj[$line['reftype']])) {
              $objElt=$arrayObj[$line['reftype']];
            } else {
              $objElt=new $classRefType();
              if (! property_exists($objElt,'idResource')) {
                $objElt=null;
              }
            }
            if ($objElt) {
              $resp=SqlList::getFieldFromId($classRefType, $line['refid'], 'idResource');
            }
          }
          if($resp){
            $responsible = SqlList::getNameFromId('Affectable', $resp);
            $display=SqlList::getFieldFromId('ResourceAll', $resp, 'initials');
            if(!$display or (is_numeric($display) and Security::checkValidId($display))){
              $display='';
              $words=pq_mb_split(' ',pq_str_replace(array('"',"'"), ' ', $responsible));
              foreach ($words as $word) {
                $display.=(pq_mb_substr($word,0,1,'UTF-8'));
              }
            }
            if($responsible){
              $responsible=pq_str_replace('"','\"',$responsible);
              echo ',"responsible":"'.$resp.'"';
              echo ',"responsibledisplay":"' .  strip_tags($responsible). '"';
            }
            if($display)echo ',"respinitial":"' . strip_tags($display). '"';
          }else{
            echo ',"responsible":""';
            echo ',"respinitial":""';
          }
        }else{
          if (isset($line['idresource']) and $line['idresource'] ) {
            $resp=$line['idresource'];
          }else { // Must always retreive responsible to display value in column, even if not displayed
            $resp="";
            $classRefType=($line['reftype']=='Fixed' or $line['reftype']=='Construction' or $line['reftype']=='Replan')?'Project':$line['reftype'];
            if (isset($arrayObj[$line['reftype']])) {
              $objElt=$arrayObj[$line['reftype']];
            } else {
              $objElt=new $classRefType();
              if (! property_exists($objElt,'idResource')) {
                $objElt=null;
              }
            }
            if ($objElt) {
              $resp=SqlList::getFieldFromId($classRefType, $line['refid'], 'idResource');
            }
          }
          if($resp){
            echo ',"responsible":"'.$resp.'"';
            $responsible = SqlList::getNameFromId('Affectable', $resp);
            if($responsible) echo ',"responsibledisplay":"' . strip_tags($responsible). '"';
            echo ',"respinitial":""';
          }else{
            echo ',"responsible":""';
            echo ',"respinitial":""';
          }
        }
        if (is_numeric($idPe) and floatval($idPe)==$idPe) {
          $crit="successorId=$idPe or predecessorId=$idPe";
        } else {
          $crit="successorId=0";
        }
        $listPred="";
        $listSucc="";
        $predecessor = "";
        $successor = "";
        $depList=$d->getSqlElementsFromCriteria(null,false, $crit);
        foreach ($depList as $dep) {
          if ( !$showClosed && $dep->idle) continue;
          if ($dep->successorId==$idPe) {
            $listPred.=($listPred!="")?',':'';           
            $listPred.="$dep->predecessorId#$dep->id#$dep->dependencyDelay#$dep->dependencyType";
            // For Predecessors Edition
            $predecessor.=($predecessor!="")?';':'';
            $predecessorValue=$dep->predecessorRefType."#";
            if ($dep->predecessorRefType=='Activity') $predecessorValue="A";
            else if ($dep->predecessorRefType=='Project') $predecessorValue="P";
            else if ($dep->predecessorRefType=='Milestone') $predecessorValue="M";
            else if ($dep->predecessorRefType=='PokerSession') $predecessorValue="PS";
            else if ($dep->predecessorRefType=='TestSession') $predecessorValue="TS";
            else if ($dep->predecessorRefType=='PeriodicMeeting') $predecessorValue="PM";
            else if ($dep->predecessorRefType=='Meeting') $predecessorValue="MG";
            $predecessor.= $predecessorValue.$dep->predecessorRefId;
          } else {
            $listSucc.=($listSucc!="")?',':'';
            $listSucc.="$dep->successorId#$dep->id#$dep->dependencyDelay#$dep->dependencyType";
            $successor.=($successor!="")?';':'';
            $successorValue=$dep->successorRefType."#";
            if ($dep->successorRefType=='Activity') $successorValue="A";
            else if ($dep->successorRefType=='Project') $successorValue="P";
            else if ($dep->successorRefType=='Milestone') $successorValue="M";
            else if ($dep->successorRefType=='PokerSession') $successorValue="PS";
            else if ($dep->successorRefType=='TestSession') $successorValue="TS";
            else if ($dep->successorRefType=='PeriodicMeeting') $successorValue="PM";
            else if ($dep->successorRefType=='Meeting') $successorValue="MG";
            $successor.= $successorValue.$dep->successorRefId;
          }
        }         
        //echo ', "depend":"' . $listPred . '"';
        echo ', "dependPred":"' . $listPred . '"';
        echo ', "dependSucc":"' . $listSucc . '"';
        echo ', "predecessor":"' . $predecessor . '"';
        echo ', "successor":"' . $successor . '"';
        
        $lineColor = pq_trim(((isset($line['color']))?$line['color']:''),'#');
        
        if((Parameter::getUserParameter('showColorTypeActivity')=="YES") || (Parameter::getUserParameter('showColorTypeActivity')=="NO") ){
          $ParamDefaultTypeColor=Parameter::getUserParameter('showColorTypeActivity');
        }else{
          $ParamDefaultTypeColor=Parameter::getGlobalParameter('showColorTypeActivity');
        }
        if (!$line['color'] and ($ParamDefaultTypeColor=="YES") and $line['reftype']=='Activity') {
          $ref=$line['reftype'];
          $item=new $ref($line['refid'],true); // TODO Remove
          $colorType=SqlList::getFieldFromId('ActivityType', $item->idActivityType, 'color');
          if ($colorType) $line['color']=$colorType;
          $lineColor = pq_trim($colorType,'#');
        }
      //  if((Parameter::getUserParameter('showColorActivity')=="0") and ($ParamDefaultTypeColor=="NO")){
      //    $line['color']="";
      //    $lineColor=((isset($line['color']))?pq_trim($line['color'],'#'):'');
      //  }
        echo ', "color":"'.$lineColor.'"'; 
        $hatchPattern = getPlanningHatchPattern($line);
        echo ', "hatchPattern":"'.htmlEncode($hatchPattern).'"';
        echo '}';
        //if (!$portfolio or $line['reftype']!='Milestone') $cp++;
        $cp++;
        if (! isset($line['hidden']) or $line['hidden']==0) $cptVisible++;
        if($cp>=$limitDisplay && getSessionValue('showAllGanttLines')!='true' && (!$portfolio or $line['reftype']!='Milestone')){
          echo ',{"id":"0","msgErrorDisplay":"'.i18n('limitedDisplay',array($limitDisplay)).'"}';
          break;
        }
      }
    }
    echo ' ]';
    // totalRows = number on lines in the Query
    // hiddenLines = number of line returned with partial data because hidden (wbs closed)
    // partialLines = number of line returned with partial data (whatever the reason)
    // firstFullLine = number of the first row returned with full data
    // lastFullLine = number of the last row returned  with full data
    echo ',"totalRows":"'.$nbQueriedRows.'"';
    echo ',"firstFullLine":"'.$firstFullLine.'"';
    echo ',"lastFullLine":"'.$lastFullLine.'"';
    echo ',"fullLines":"'.$cptFullLines.'"';
    echo ',"partialLines":"'.$cptPartialLines.'"';
    echo ',"hiddenLines":"'.$cptHiddenLines.'"';
    echo ',"firstHiddenLine":"'.$firstHiddenLine.'"';
    echo ',"lastHiddenLine":"'.$lastHiddenLine.'"';
    if ($immediateRefresh) $needRefresh=false;
    echo ',"needRefresh":"'.(($needRefresh)?1:0).'"';
    echo ',"immediateRefresh":"'.(($immediateRefresh)?1:0).'"';
    echo '}';
  }

  function displayGantt($result,$displayLikePlanning) {
  	global $displayResource, $outMode, $showMilestone, $portfolio,  $columnsDescription, $nbQueriedRows;
  	$csvSep=Parameter::getGlobalParameter('csvSeparator');
  	$projectNotStartBeforeValidatedDate=(Parameter::getGlobalParameter("notStartBeforeValidatedStartDate")=='YES')?true:false;
  	$arrayProjectStart=array();
    //$showWbs=false;
    if(!isset($limitDisplay))$limitDisplay=(Parameter::getGlobalParameter('limitDisplayPlanning')!='')?Parameter::getGlobalParameter('limitDisplayPlanning'):2000;
//     if (pq_array_key_exists('showWBS',$_REQUEST) ) {
//       $showWbs=true;
//     }
    $showWbs=RequestHandler::getValue("showWBS");
    //$showResource=false;
//     if ( pq_array_key_exists('showResource',$_REQUEST) ) {
//       $showResource=true;
//     }
    $showResource = RequestHandler::getValue('$showResource');
    // calculations
    $startDate=date('Y-m-d');
    if (pq_array_key_exists('startDate',$_REQUEST)) {
      $startDate=$_REQUEST['startDate'];
	    Security::checkValidDateTime($startDate);
    }
    $endDate='';
    if (pq_array_key_exists('endDate',$_REQUEST)) {
      $endDate=$_REQUEST['endDate'];
	    Security::checkValidDateTime($endDate);
    }
    $format='day';
    if (pq_array_key_exists('format',$_REQUEST)) {
      $format=$_REQUEST['format'];
	    Security::checkValidPeriodScale($format);
    }
    if($format == 'day') {
      $colWidth = 18;
      $colUnit = 1;
      $topUnit=7;
    } else if($format == 'week') {
      $colWidth = 50;
      $colUnit = 7;
      $topUnit=7;
    } else if($format == 'month') {
      $colWidth = 60;
      $colUnit = 30;
      $topUnit=30;
    } else if($format == 'quarter') {
      $colWidth = 30;
      $colUnit = 30;
      $topUnit=90;
    }
    $maxDate = '';
    $minDate = '';
    if ($nbQueriedRows > 0) {
      $resultArray=array();
      $cp=0;
      while ($line = Sql::fetchLine($result)) {
      	$line=array_change_key_case($line,CASE_LOWER);
        $line['tags']='';
        if (isset($columnsDescription['Tags']) and $columnsDescription['Tags']['show']==1) {
          if ($line['reftype']=='Activity' and isset($line['activitytags'])) {
            $line['tags']=$line['activitytags'];
          } else if ($line['reftype']=='Project' and isset($line['projecttags'])) {
            $line['tags']=$line['projecttags'];
          } else if (property_exists($line['reftype'], 'tags')) {
            $line['tags']=SqlList::getFieldFromId($line['reftype'], $line['refid'], 'tags');
          }
        }
        if ($line['reftype']=='Milestone' and $portfolio and $showMilestone and $showMilestone!='all' ) {   
          $mile=new Milestone($line['refid'],true);
          if ($mile->idMilestoneType!=$showMilestone) {
            continue;
          }
        }
        if ($line["plannedwork"]>0 and $line["leftwork"]==0) {
          $line["plannedstartdate"]='';
          $line["plannedenddate"]='';
        }
        $pStart="";
        $pStart=(pq_trim($line['initialstartdate'])!="")?$line['initialstartdate']:$pStart;
        $pStart=(pq_trim($line['validatedstartdate'])!="")?$line['validatedstartdate']:$pStart;
        $pStart=(pq_trim($line['plannedstartdate'])!="")?$line['plannedstartdate']:$pStart;
        $pStart=(pq_trim($line['realstartdate'])!="")?$line['realstartdate']:$pStart;
        if (pq_trim($line['plannedstartdate'])!=""
        and pq_trim($line['realstartdate'])!=""
        and $line['plannedstartdate']<$line['realstartdate'] ) {
          $pStart=$line['plannedstartdate'];
        }
        $pEnd="";
        $pEnd=(pq_trim($line['initialenddate'])!="")?$line['initialenddate']:$pEnd;
        $pEnd=(pq_trim($line['validatedenddate'])!="")?$line['validatedenddate']:$pEnd;
        $pEnd=(pq_trim($line['plannedenddate'])!="")?$line['plannedenddate']:$pEnd;
        $pEnd=(pq_trim($line['realenddate'])!="")?$line['realenddate']:$pEnd;
        //if ($pEnd=="") {$pEnd=date('Y-m-d');}
        if ($line['reftype']=='Milestone') {
          $pStart=$pEnd;
        }
        if (pq_strlen($pStart)>10) $pStart=pq_substr($pStart,0,10);
        if (pq_strlen($pEnd)>10) $pStart=pq_substr($pEnd,0,10);
        if (pq_trim($line['realstartdate']) and isset($line['isglobal']) and $line['isglobal']==1 and ! $line['progress']) {
          if ($pStart==$pend) {
            $line['progress']='50';
          } else {
            $taskLength=dayDiffDates($pStart,$pend);
            if ($taskLength>0) {
              $progressLength=dayDiffDates($pStart,date('Y-m-d'));
              $line['progress']=round($progressLength/$taskLength*100,0);
            } else {
              $line['progress']='50';
            }
          } 
        }
        if ($projectNotStartBeforeValidatedDate) {
          if ($line['reftype']=='Project') {
            $arrayProjectStart[$line['refid']]=$line['validatedstartdate'];
          } else if (! $pStart) {
            if (isset($arrayProjectStart[$line['idproject']]) and pq_trim($arrayProjectStart[$line['idproject']])!='') {
              $pStart=$arrayProjectStart[$line['idproject']];
            } 
          }
        }
        $line['pstart']=$pStart;
        $line['pend']=$pEnd;
        $line['type'] = '';
        if($line['reftype'] == 'Project') {
            $project = new Project($line['refid']);
            $line['color'] = $project->color;
            $type = new Type($project->idProjectType);
            $line['type'] = $type->name;
            $status = new Status($project->idStatus);
            $line['status'] = $status->name;
            $line['statuscolor'] = $status->color;
            if($portfolio){
              $health= new Health($project->idHealth);
              $line['health'] = $health->name;
              $quality= new Quality($project->idQuality);
              $line['quality'] = $quality->name;
              $crit=array('id'=>$project->idTrend);
              $trend=SqlElement::getSingleSqlElementFromCriteria('Trend', $crit);
              $line['trend'] = $trend->name;
              $overallProgress= new OverallProgress($project->idOverallProgress);
              $line['overallprogress'] = $overallProgress->name;
            }
            if (! RestrictType::isTypeVisibleForProject('Project', $project->idProjectType, $project->id)) {
              $line["hidden"]=1;
            }
        } else if ($columnsDescription['IdStatus']['show']==1 or $columnsDescription['Type']['show']==1 or Parameter::getGlobalParameter('hideItemTypeRestrictionOnProject')=='YES'
          or (($columnsDescription['IdHealthStatus']['show']==1 or $columnsDescription['QualityLevel']['show']==1 or $columnsDescription['IdTrend']['show']==1 or $columnsDescription['IdOverallProgress']['show']==1) and $portfolio)) {
          $ref=$line['reftype'];
          if ($ref=='PeriodicMeeting') $ref='Meeting';
          $type=SqlElement::getTypeName($ref);
          $item=new $ref($line['refid'],true);
          if (Parameter::getGlobalParameter('hideItemTypeRestrictionOnProject')=='YES'
          and property_exists($ref, $type) and property_exists($ref, 'idProject')) {
            $prj=($ref=='Project')?$item->id:$item->idProject;
            if (! RestrictType::isTypeVisibleForProject($ref, $item->$type, $prj)) {
              $line["hidden"]=1;
            }
          }
          if($columnsDescription['IdStatus']['show']==1 or $columnsDescription['Type']['show']==1 ){
            $line["type"]=SqlList::getNameFromId('Type',$item->$type);
            if (property_exists($item,"idStatus")) {
              $status = new Status($item->idStatus);
              $line['status'] = $status->name;
              $line['statuscolor'] = $status->color;
            } else {
              $line['status'] = '';
              $line['statuscolor'] = '';
            }
          }
          if($columnsDescription['IdHealthStatus']['show']==1 and $portfolio){
            if (property_exists($item,"idHealth")) {
              $health = new Health ($item->idHealth);
              $line['health'] = $health->name;
              $line['healthcolor'] = $health->color;
            }else{
              $line['health'] = '';
              $line['healthcolor'] = '';
            }
          }
          if($columnsDescription['QualityLevel']['show']==1 and $portfolio){
            if (property_exists($item,"idQuality")) {
              $quality = new Quality($item->idQuality);
              $line['quality'] = $quality->name;
              $line['qualitycolor'] = $quality->color;
            }else{
              $line['quality'] = '';
              $line['qualitycolor'] = '';
            }
          }
          if($columnsDescription['IdTrend']['show']==1 and $portfolio){
            if (property_exists($item,"idTrend")) {
              $trend = new Trend($item->idTrend);
              $line['trend'] = $trend->name;
              $line['trendcolor'] = $trend->color;
            }else{
              $line['trend'] = '';
              $line['trendcolor'] = '';
            }
          }
          if($columnsDescription['IdOverallProgress']['show']==1 and $portfolio){
            if (property_exists($item,"idOverallProgress")) {
              $overallProgress = new OverallProgress($item->idOverallProgress);
              $line['overallprogress'] = $overallProgress->name;
            }else{
              $line['overallprogress'] = '';
            }
          }
          
        }
        if ($line['reftype']!='Project' and $line['reftype']!='Fixed' and $line['reftype']!='Construction' and $line['reftype']!='Replan') { // 'Fixed' and 'Construction' are projects !!!!
          $arrayResource=array();
          if (isset($columnsDescription['Resource']) and $columnsDescription['Resource']['show']==1) { // Must always retreive resource to display value in column, even if not displayed
            $crit=array('refType'=>$line['reftype'], 'refId'=>$line['refid']);
            $ass=new Assignment();
            $assList=$ass->getSqlElementsFromCriteria($crit,false);
            $resp="";
            if (isset($arrayObj[$line['reftype']])) {
              $objElt=$arrayObj[$line['reftype']];
            } else {
              $objElt=new $line['reftype']();
              if (! property_exists($objElt,'idResource')) {
                $objElt=null;
              }
              $arrayObj[$line['reftype']]=$objElt;
            }
            if ($objElt) {
              $resp=SqlList::getFieldFromId($line['reftype'], $line['refid'], 'idResource');
            }
            foreach ($assList as $ass) {
              $res=new Resource($ass->idResource,true);
              if (! isset($arrayResource[$res->id])) {
                $display=$res->$displayResource;
                if ($displayResource=='initials' and ! $display) {
                  $words=pq_mb_split(' ',pq_str_replace(array('"',"'"), ' ', $res->name));
                  $display='';
                  if ($words) foreach ($words as $word) {
                    $display.=(pq_mb_substr($word,0,1,'UTF-8'));
                  }
                }
                if ($display)	{
                  $arrayResource[$res->id]=htmlEncode($display);
                  if ($resp and $resp==$res->id ) {
                    $arrayResource[$res->id]='<b>'.htmlEncode($display).'</b>';
                  }
                }
              }
            }
          }
          //$res=new Resource($ass->idResource);
          $line["resource"]= htmlEncodeJson(implode(', ',$arrayResource));
        } else {
          $line["resource"]="";
        }
        
        if (!$portfolio and $line['reftype']!='Fixed' and $line['reftype']!='Construction' and $line['reftype']!='Replan') {
          if (isset($line['idresource']) and $line['idresource'] ) {
            $resp=$line['idresource'];
          } else { // Must always retreive responsible to display value in column, even if not displayed
            $resp="";
            if (isset($arrayObj[$line['reftype']])) {
              $objElt=$arrayObj[$line['reftype']];
            } else {
              $objElt=new $line['reftype']();
              if (! property_exists($objElt,'idResource')) {
                $objElt=null;
              }
            }
            if ($objElt) {
              $resp=SqlList::getFieldFromId($line['reftype'], $line['refid'], 'idResource');
            }
          }
          if($resp){
            $responsible = SqlList::getNameFromId('Affectable', $resp);
            $words=pq_mb_split(' ',pq_str_replace(array('"',"'"), ' ', $responsible));
            $display='';
            foreach ($words as $word) {
              $display.=(pq_mb_substr($word,0,1,'UTF-8'));
            }
            $line["responsible"]=  $responsible;
            $line["respinitial"]= $display;
          }else{
            $line["responsible"]= '';
            $line["respinitial"]= '';
          }
        }else{
          $line["responsible"]= '';
          $line["respinitial"]= '';
        }
        $line['origin']='';
        $line['origindisplay']='';
        if ($line['reftype']=='Activity' and isset($line['origintype']) and isset($line['originid']) and $line['origintype'] and $line['originid']) {
          $line['origin']=$line['origintype'].'#'.$line['originid'];
          $line['origindisplay']=i18n($line['origintype']).'#'.$line['originid'];
        }
        $line['successor']='';
        if (isset($columnsDescription['Successor']) and $columnsDescription['Successor']['show']==1 and is_numeric($line['id']) and floatval($line['id'])==$line['id']) {
          $dependency=new Dependency();
          $depList=$dependency->getSqlElementsFromCriteria(array('predecessorId'=>$line['id']), false);
          foreach ($depList as $dep) {
            $line['successor'].=($line['successor']!="")?';':'';
            $successorValue=$dep->successorRefType."#";
            if ($dep->successorRefType=='Activity') $successorValue="A";
            else if ($dep->successorRefType=='Project') $successorValue="P";
            else if ($dep->successorRefType=='Milestone') $successorValue="M";
            else if ($dep->successorRefType=='PokerSession') $successorValue="PS";
            else if ($dep->successorRefType=='TestSession') $successorValue="TS";
            else if ($dep->successorRefType=='PeriodicMeeting') $successorValue="PM";
            else if ($dep->successorRefType=='Meeting') $successorValue="MG";
            $line['successor'].=$successorValue.$dep->successorRefId;
          }
        }
        $resultArray[]=$line;
        if ($maxDate=='' or $maxDate<$pEnd) {$maxDate=$pEnd;}
        //if ($minDate=='' or $minDate>$pStart) {$minDate=$pStart;}
        if ($minDate=='' or ($minDate>$pStart and pq_trim($pStart)))  $minDate=$pStart;
        $cp++;
        if($cp==$limitDisplay and $outMode != 'csv'){
          $totalspan=0;
          $displayIsLimited=true;
          break;
        }
      }
      if ($minDate<$startDate) {
        $minDate=$startDate;
      }
      if ($endDate and $maxDate>$endDate) {
        $maxDate=$endDate;
      }
      if ($format=='day' or $format=='week') {
        //$minDate=addDaysToDate($minDate,-1);
        $minDate=date('Y-m-d',firstDayofWeek(weekNumber($minDate),pq_substr($minDate,0,4)));
        //$maxDate=addDaysToDate($maxDate,+1);
        $maxDate=date('Y-m-d',firstDayofWeek(weekNumber($maxDate),pq_substr($maxDate,0,4)));
        $maxDate=addDaysToDate($maxDate,+6);
      } else if ($format=='month') {
        //$minDate=addDaysToDate($minDate,-1);
        $minDate=pq_substr($minDate,0,8).'01';
        //$maxDate=addDaysToDate($maxDate,+1);
        $maxDate=addMonthsToDate($maxDate,+1);
        $maxDate=pq_substr($maxDate,0,8).'01';
        $maxDate=addDaysToDate($maxDate,-1);
      } else if ($format=='quarter') {
        $arrayMin=array("01-01"=>"01-01","02-01"=>"01-01","03-01"=>"01-01",
                        "04-01"=>"04-01","05-01"=>"04-01","06-01"=>"04-01",
                        "07-01"=>"07-01","08-01"=>"07-01","09-01"=>"07-01",
                        "10-01"=>"10-01","11-01"=>"10-01","12-01"=>"10-01");
      	$arrayMax=array("01-31"=>"03-31","02-28"=>"03-31","02-29"=>"03-31","03-31"=>"03-01",
                        "04-30"=>"06-30","05-31"=>"06-30","06-30"=>"06-30",
                        "07-31"=>"09-30","08-31"=>"09-30","09-30"=>"09-30",
                        "10-31"=>"12-31","11-30"=>"12-31","12-31"=>"12-31");
        //$minDate=addDaysToDate($minDate,-1);
        $minDate=pq_substr($minDate,0,8).'01';
        $minDate=pq_substr($minDate,0,5).$arrayMin[pq_substr($minDate,5)];
        //$maxDate=addDaysToDate($maxDate,+1);
        $maxDate=addMonthsToDate($maxDate,+1);
        $maxDate=pq_substr($maxDate,0,8).'01';
        $maxDate=addDaysToDate($maxDate,-1);
        $maxDate=pq_substr($maxDate,0,5).$arrayMax[pq_substr($maxDate,5)];
      }
      $numDays = (dayDiffDates($minDate, $maxDate) +1);
      $numUnits = round($numDays / $colUnit);
      $topUnits = round($numDays / $topUnit);
      $days=array();
      $openDays=array();
      $day=$minDate;
      for ($i=0;$i<$numDays; $i++) {
        $days[$i]=$day;
        $openDays[$i]=isOpenDay($day,'1');
        $day=addDaysToDate($day,1);
      }
      //echo "mindate:$minDate maxdate:$maxDate numDays:$numDays numUnits:$numUnits topUnits:$topUnits" ;
      // Header
      //$sortArray=Parameter::getPlanningColumnOrder();
	  $sortArray=array_merge(array(), Parameter::getPlanningColumnOrder());
    $cptSort=0;
    unset($columnsDescription['ObjectType']);
    unset($columnsDescription['ExterRes']);
    if(!$portfolio){
      unset($columnsDescription['IdHealthStatus']);
      unset($columnsDescription['QualityLevel']);
      unset($columnsDescription['IdTrend']);
      unset($columnsDescription['IdOverallProgress']);
    }
    foreach ($columnsDescription as $ganttColName=>$ganttCol) { 
      if ($ganttCol['show']==1) $cptSort++; 
    }
    //$resultArray
    $arrayVisible=array();
    for ($i = (count($resultArray)) - 1; $i>=0; $i--) {
      $item = $resultArray[$i];
      if ($item['id']==0){continue;}
      $wbs=$item['wbssortable'];
      if (! isset($item['hidden']) or $item['hidden']=="0" or $item['hidden']=="" or !$item['hidden']) {
        while (pq_strlen($wbs)>=5 and ! isset($arrayVisible[$wbs]) ) {
          $arrayVisible[$wbs]=$wbs;
          $wbs=pq_substr($wbs, 0, -6);
        }
      } 
    }
	  if($outMode != 'csv') {
      //echo '<table dojoType="dojo.dnd.Source" id="wishlistNode" class="container ganttTable" style="border: 1px solid #AAAAAA; margin: 0px; padding: 0px;">';
      echo '<div style="overflow:hidden;">';
      echo '<table style="font-size:80%; border: 1px solid #AAAAAA; margin: 0px; padding: 0px;">';
      echo '<tr style="height: 20px;"><td colspan="' . ($cptSort+1) . '">&nbsp;</td>';
      $day=$minDate;
      for ($i=0;$i<$topUnits;$i++) {
        $span=$topUnit;
        $title="";
        if ($format=='month') {
          $title=pq_substr($day,0,4);
          $span=numberOfDaysOfMonth($day);
        } else if($format=='week') {
          $title=pq_substr($day,2,2) . " #" . weekNumber($day);
        } else if ($format=='day') {
          $tDate = pq_explode("-", $day);
          $date= mktime(0, 0, 0, $tDate[1], $tDate[2]+1, $tDate[0]);
          $title=pq_substr($day,0,4) . " #" . weekNumber($day);
          $title.=' (' . pq_substr(i18n(date('F', $date)),0,4) . ')';
        } else if ($format=='quarter') {
          $arrayQuarter=array("01"=>"1","02"=>"1","03"=>"1",
                        "04"=>"2","05"=>"2","06"=>"2",
                        "07"=>"3","08"=>"3","09"=>"3",
                        "10"=>"4","11"=>"4","12"=>"4");
        
        	$title="Q";
        	$title.=$arrayQuarter[pq_substr($day,5,2)];
        	$title.=" ".pq_substr($day,0,4);
        	$span=numberOfDaysOfMonth($day)+numberOfDaysOfMonth(addMonthsToDate($day,1))+numberOfDaysOfMonth(addMonthsToDate($day,2));
        	$span=3*30/5;
        }
        if(isset($displayIsLimited) and $displayIsLimited)$totalspan+=$span;
        echo '<td class="reportTableHeader" colspan="' . $span . '">';
        echo $title;
        echo '</td>';
        if ($format=='month') {
          $day=addMonthsToDate($day,1);
        } else if ($format=='quarter') {
        	$day=addMonthsToDate($day,3);
        } else {
          $day=addDaysToDate($day,$topUnit);
        }
      }
      echo '</tr>';
      echo '<TR style="height: 20px;">';
      echo '  <TD class="reportTableHeader" style="width:15px; border-right:0px;"></TD>';
      echo '  <TD class="reportTableHeader" style="width:150px; border-left:0px; text-align: left;">' . i18n('colTask') . '</TD>';
      foreach ($sortArray as $col) {
        if (isset($columnsDescription[$col]) and $columnsDescription[$col]['show']!=1) continue; 
        if ($col=='ValidatedWork') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colValidated') . '</TD>' ;
      	if ($col=='AssignedWork') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colAssigned') . '</TD>' ;
        if ($col=='RealWork') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colReal') . '</TD>' ;
        if ($col=='LeftWork') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colLeft') . '</TD>' ;
        if ($col=='PlannedWork') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colReassessed') . '</TD>' ;
        if ($col=='ValidatedCost') echo '  <TD class="reportTableHeader" style="width:30px">'. i18n('colValidatedCost') . '</TD>' ;
        if ($col=='AssignedCost') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colAssignedCost') . '</TD>' ;
        if ($col=='RealCost') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colRealCost') . '</TD>' ;
        if ($col=='LeftCost') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colLeftCost') . '</TD>' ;
        if ($col=='PlannedCost') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colPlannedCost') . '</TD>' ;
        if ($col=='Type') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colType') . '</TD>' ;
        if ($col=='IdStatus') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colIdStatus') . '</TD>' ;
        if ($col=='IdHealthStatus'  and $portfolio) echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colIdHealthStatus') . '</TD>' ;
        if ($col=='QualityLevel'  and $portfolio) echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colQualityLevel') . '</TD>' ;
        if ($col=='IdTrend' and $portfolio) echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colIdTrend') . '</TD>' ;
        if ($col=='IdOverallProgress'  and $portfolio) echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colProgress') . '</TD>' ;
        if ($col=='Duration') echo '  <TD class="reportTableHeader" style="width:30px">' . i18n('colDuration') . '</TD>' ;
        if ($col=='Progress') echo '  <TD class="reportTableHeader" style="width:30px">'  . i18n('colPct') . '</TD>' ;
        if ($col=='StartDate') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colStart') . '</TD>' ;
        if ($col=='EndDate') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colEnd') . '</TD>' ;
        if ($col=='Tags') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colTags') . '</TD>' ;
        if ($col=='IdContact') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colRequestor') . '</TD>' ;
        if ($col=='IdActivity') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colParentActivity') . '</TD>' ;
        if ($col=='UnitToRealise') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colUnitToRealise') . '</TD>' ;
        if ($col=='UnitWeight') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colUnitWeight') . '</TD>' ;
        if ($col=='Origin') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colOrigin') . '</TD>' ;
        if ($col=='Successor') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colSuccessor') . '</TD>' ;
        if ($col=='ValidatedStartDate') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colValidatedStart') . '</TD>' ;
        if ($col=='ValidatedEndDate') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colValidatedEnd') . '</TD>' ;
        if ($col=='ValidatedDuration') echo '  <TD class="reportTableHeader" style="width:30px" >' . i18n('colValidatedDuration')  . '</TD>' ;
        if ($col=='Resource') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colResource') . '</TD>' ;
        if ($col=='Responsible') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colResponsible') . '</TD>' ;
        if ($col=='RespInitial') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colRespInitial') . '</TD>' ;
        if ($col=='Priority') echo '  <TD class="reportTableHeader" style="width:50px">'  . i18n('colPriorityShort') . '</TD>' ;
        if ($col=='IdPlanningMode') echo '  <TD class="reportTableHeader" style="width:150px">'  . i18n('colIdPlanningMode') . '</TD>' ;
        if ($col=='Id') echo '  <TD class="reportTableHeader" style="width:18px">'  . i18n('colId') . '</TD>' ;
      }
      $weekendColor="#cfcfcf";
      $day=$minDate;
      for ($i=0;$i<$numUnits;$i++) {
        $color="";
        $span=$colUnit;
        if ($format=='month') {
          $tDate = pq_explode("-", $day);
          $date= mktime(0, 0, 0, $tDate[1], $tDate[2]+1, $tDate[0]);
          $title=i18n(date('F', $date));
          $span=numberOfDaysOfMonth($day);
        } else if($format=='week') {
          $title=pq_substr(htmlFormatDate($day),0,5);
        } else if ($format=='day') {
          $color=($openDays[$i]==1)?'':'background-color:' . $weekendColor . ';';
          $title=pq_substr($days[$i],-2);
        } else if ($format=='quarter') {
          $tDate = pq_explode("-", $day);
          $date= mktime(0, 0, 0, $tDate[1], $tDate[2]+1, $tDate[0]);
          $title=pq_substr($day,5,2);
          $span=numberOfDaysOfMonth($day);
          $span=30/5;
        }
        echo '<td class="reportTableColumnHeader" colspan="' . $span . '" style="width:' . $colWidth . 'px;magin:0px;padding:0px;' . $color . '">';
        echo $title . '</td>';
        if ($format=='month') {
          $day=addMonthsToDate($day,1);
        } else if ($format=='quarter') {
          $day=addMonthsToDate($day,1);
        } else {
          $day=addDaysToDate($day,$topUnit);
        }
      }
      echo '</TR>';
	  } else {
	      $currency=' ('.Parameter::getGlobalParameter('currency').')';
	      $workUnit=' ('.Work::displayShortWorkUnit().')';
        echo chr(239) . chr(187) . chr(191); // Needed by Microsoft Excel to make it CSV
        echo i18n('colElement') . $csvSep . i18n('colId') . $csvSep . i18n('colTask') . $csvSep  ; 
        foreach ($sortArray as $col) {
          if (isset($columnsDescription[$col]) and $columnsDescription[$col]['show']!=1) continue; 
          if ($col=='ValidatedWork') echo i18n('colValidatedWork') . $workUnit . $csvSep ;
          if ($col=='AssignedWork') echo i18n('colAssignedWork') . $workUnit . $csvSep ;
          if ($col=='RealWork') echo i18n('colRealWork') . $workUnit . $csvSep ;
          if ($col=='LeftWork') echo i18n('colLeftWork') . $workUnit . $csvSep ;
          if ($col=='PlannedWork') echo i18n('colPlannedWork') . $workUnit . $csvSep ;
          if ($col=='ValidatedCost') echo i18n('colValidatedCost') . $currency . $csvSep ;
          if ($col=='AssignedCost') echo i18n('colAssignedCost') . $currency . $csvSep ;
          if ($col=='RealCost') echo i18n('colRealCost') . $currency . $csvSep ;
          if ($col=='LeftCost') echo i18n('colLeftCost') . $currency . $csvSep ;
          if ($col=='PlannedCost') echo i18n('colPlannedCost') . $currency . $csvSep ;
          if ($col=='Type') echo i18n('colType') . $csvSep ;
          if ($col=='IdStatus') echo i18n('colIdStatus') . $csvSep . i18n('colStatusColor') . $csvSep ;
          if ($col=='IdHealthStatus'  and $portfolio) echo i18n('colIdHealthStatus') . $csvSep . i18n('colHealthStatusColor') . $csvSep ;
          if ($col=='QualityLevel'  and $portfolio) echo i18n('colQualityLevel') . $csvSep . i18n('colQualityLevelColor') . $csvSep ;
          if ($col=='IdTrend' and $portfolio) echo i18n('colIdTrend') . $csvSep . i18n('colTrendColor') . $csvSep ;
          if ($col=='IdOverallProgress'  and $portfolio) echo i18n('colProgress') . $csvSep ;
          if ($col=='Duration') echo i18n('colDuration') . ' ('.i18n('shortDay') . ')' . $csvSep ;
          if ($col=='Progress') echo i18n('colProgress'). ' (' .i18n('colPct') . ')' . $csvSep ;
          if ($col=='StartDate') echo i18n('colStart') . $csvSep ;
          if ($col=='EndDate') echo i18n('colEnd') . $csvSep ;
          if ($col=='Tags') echo i18n('colTags') . $csvSep ;
          if ($col=='IdContact') echo i18n('colRequestor') . $csvSep ;
          if ($col=='IdActivity') echo i18n('colParentActivity') . $csvSep ;
          if ($col=='UnitToRealise') echo i18n('colUnitToRealise') . $csvSep ;
          if ($col=='UnitWeight') echo i18n('colUnitWeight') . $csvSep ;
          if ($col=='Origin') echo i18n('colOrigin') . $csvSep ;
          if ($col=='Successor') echo i18n('colSuccessor') . $csvSep ;
          if ($col=='ValidatedStartDate') echo i18n('colValidatedStart') . $csvSep ;
          if ($col=='ValidatedEndDate') echo i18n('colValidatedEnd') . $csvSep ;
          if ($col=='ValidatedDuration') echo i18n('colValidatedDuration')  . $csvSep ;
          if ($col=='Resource') echo i18n('colResource') . $csvSep ;
          if ($col=='Responsible') echo i18n('colResponsible') . $csvSep ;
          if ($col=='RespInitial') echo i18n('colRespInitial') . $csvSep ;
          if ($col=='Priority') echo i18n('colPriority') . $csvSep ;
          if ($col=='IdPlanningMode') echo i18n('colIdPlanningMode') . $csvSep ;
          //if ($col=='Id' and !$portfolio) echo i18n('colId') . $csvSep ;
        }

        echo "\n";
      }
      // lines
      $width=round($colWidth/$colUnit) . "px;";
      $collapsedList=array();
      if($displayLikePlanning)$collapsedList=Collapsed::getCollaspedList();
      $closedWbs='';
      $level=1;
      $wbsLevelArray=array();
      foreach ($resultArray as $line) {
        $wbs=$line['wbssortable'];
        if (!isset($arrayVisible[$wbs])) continue;
        $pEnd=$line['pend'];
        $pStart=$line['pstart'];
        $realWork=$line['realwork'];
        $plannedWork=$line['plannedwork'];
        $progress=$line['progress'];

        // pGroup : is the task a group one ?
        $pGroup=($line['elementary']=='0')?1:0;
        if ($line['reftype']=='Project') $pGroup=1;
        if ($line['reftype']=='Fixed') $pGroup=1;
        if ($line['reftype']=='Replan') $pGroup=1;
        if ($line['reftype']=='Construction') $pGroup=1;
        if ($closedWbs and pq_strlen($line['wbssortable'])<=pq_strlen($closedWbs)) {
          $closedWbs="";
        }
        $scope='Planning_'.$line['reftype'].'_'.$line['refid'];
        $scope=pq_str_replace(array('Fixed','Replan','Construction'), 'Project', $scope);
        $collapsed=false;
        if ($pGroup and pq_array_key_exists($scope, $collapsedList)) {
          $collapsed=true;
          if (! $closedWbs) {
            $closedWbs=$line['wbssortable'];
          }
        }
        $compStyle="";
        $bgColor="";
        if( $pGroup) {
          $rowType = "group";
          $compStyle="font-weight: bold; background: #E8E8E8;";
          $bgColor="background: #E8E8E8;";
        } else if( $line['reftype']=='Milestone'){
          $rowType  = "mile";
        } else {
          $rowType  = "row";
        }
        $wbs=$line['wbssortable'];
        $wbsTest=$wbs;
        $level=1;
        while (pq_strlen($wbsTest)>3) {
        	$wbsTest=pq_substr($wbsTest,0,pq_strlen($wbsTest)-6);
        	if (pq_array_key_exists($wbsTest, $wbsLevelArray)) {
        		$level=$wbsLevelArray[$wbsTest]+1;
        		$wbsTest="";
        	}
        }
        $wbsLevelArray[$wbs]=$level;
        //$level=(pq_strlen($wbs)+1)/4;
        $tab="";
        for ($i=1;$i<$level;$i++) {
          $tab.='<span class="ganttSep" >&nbsp;&nbsp;&nbsp;&nbsp;</span>';
        }
        $pName=($showWbs)?$line['wbs']." ":"";
        $pName.= htmlEncode($line['refname']);
        
        $durationNumeric=($rowType=='mile' or $pStart=="" or $pEnd=="")?'-':workDayDiffDates($pStart, $pEnd, $line['idproject']);
        $duration=$durationNumeric . "&nbsp;" . i18n("shortDay");
        //echo '<TR class="dojoDndItem ganttTask' . $rowType . '" style="margin: 0px; padding: 0px;">';

        if ($closedWbs and $closedWbs!=$line['wbssortable']) {
          //echo ' display:none;';
          continue;
        }
		if($outMode != 'csv') {
        echo '<TR style="height:18px;' ;

        echo '">';
        echo '  <TD class="reportTableData" style="border-right:0px;' . $compStyle . '">'.formatIcon($line['reftype'], 16).'</TD>';
        echo '  <TD class="reportTableData" style="border-left:0px; text-align: left;' . $compStyle . '"><span class="nobr">' . $tab ;
        echo '<span style="width: 16px;height:100%;vertical-align:middle;">';
        if ($pGroup) {
          if ($collapsed) {
            echo '<img style="width:12px" src="../view/css/images/plus.gif" />';
          } else {
            echo '<img style="width:12px" src="../view/css/images/minus.gif" />';
          }
        } else {
          if ($line['reftype']=='Milestone') {
            echo '<img style="width:12px" src="../view/css/images/mile.gif" />';
          } else {
            echo '<img style="width:12px" src="../view/css/images/none.gif" />';
          }
        }
        //<div style="float: left;width:16px;">&nbsp;</div></span>';
        echo '</span>&nbsp;';
        echo $pName . '</span></TD>';
        foreach ($sortArray as $col) {
          if (isset($columnsDescription[$col]) and $columnsDescription[$col]['show']!=1) continue;
          if ($col=='ValidatedWork') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' . Work::displayWorkWithUnit($line["validatedwork"])  . '</TD>' ;
          if ($col=='AssignedWork') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  Work::displayWorkWithUnit($line["assignedwork"])  . '</TD>' ;
          if ($col=='RealWork') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  Work::displayWorkWithUnit($line["realwork"])  . '</TD>' ;
          if ($col=='LeftWork') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  Work::displayWorkWithUnit($line["leftwork"])  . '</TD>' ;
          if ($col=='PlannedWork') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  Work::displayWorkWithUnit($line["plannedwork"])  . '</TD>' ;
          if ($col=='ValidatedCost') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' . costFormatter($line["validatedcost"])  . '</TD>' ;
          if ($col=='AssignedCost') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  costFormatter($line["assignedcost"])  . '</TD>' ;
          if ($col=='RealCost') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  costFormatter($line["realcost"])  . '</TD>' ;
          if ($col=='LeftCost') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  costFormatter($line["leftcost"])  . '</TD>' ;
          if ($col=='PlannedCost') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  costFormatter($line["plannedcost"])  . '</TD>' ;
          if ($col=='Type') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' . ($line["type"])  . '</TD>' ;
          if ($col=='IdStatus') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  ($line["status"])  . '</TD>' ;
          if ($col=='IdHealthStatus' and $portfolio) echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  ($line["health"])  . '</TD>' ;
          if ($col=='QualityLevel' and $portfolio) echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  ($line["quality"])  . '</TD>' ;
          if ($col=='IdTrend' and $portfolio) echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  ($line["trend"])  . '</TD>' ;
          if ($col=='IdOverallProgress' and $portfolio) echo '  <TD class="reportTableData" style="' . $compStyle . '" >' .  ($line["overallprogress"])  . '</TD>' ;
          if ($col=='Duration') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' . $duration  . '</TD>' ;
          if ($col=='Progress') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' . percentFormatter($progress) . '</TD>' ;
          if ($col=='StartDate') echo '  <TD class="reportTableData" style="' . $compStyle . '">'  . (($pStart)?dateFormatter($pStart):'-') . '</TD>' ;
          if ($col=='EndDate') echo '  <TD class="reportTableData" style="' . $compStyle . '">'  . (($pEnd)?dateFormatter($pEnd):'-') . '</TD>' ;
          if ($col=='Tags') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '">'  . tagFormatter($line['tags']) . '</TD>' ;
          if ($col=='IdContact') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '">' . ((isset($line['idcontactdisplay']))?$line['idcontactdisplay']:'') . '</TD>' ;
          if ($col=='IdActivity') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '">' . ((isset($line['idactivitydisplay']))?$line['idactivitydisplay']:'') . '</TD>' ;
          if ($col=='UnitToRealise') echo '  <TD class="reportTableData" style="text-align:right;' . $compStyle . '">' . ((isset($line['unittorealise']))?$line['unittorealise']:'') . '</TD>' ;
          if ($col=='UnitWeight') echo '  <TD class="reportTableData" style="text-align:right;' . $compStyle . '">' . ((isset($line['unitweight']))?$line['unitweight']:'') . '</TD>' ;
          if ($col=='Origin') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '">' . ((isset($line['origindisplay']))?$line['origindisplay']:'') . '</TD>' ;
          if ($col=='Successor') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '">' . ((isset($line['successor']))?$line['successor']:'') . '</TD>' ;
          if ($col=='ValidatedStartDate') echo '  <TD class="reportTableData" style="' . $compStyle . '">'  . (($line['validatedstartdate'])?dateFormatter($line['validatedstartdate']):'-') . '</TD>' ;
          if ($col=='ValidatedEndDate') echo '  <TD class="reportTableData" style="' . $compStyle . '">'  . (($line['validatedenddate'])?dateFormatter($line['validatedenddate']):'-') . '</TD>' ;
          if ($col=='ValidatedDuration') echo '  <TD class="reportTableData" style="' . $compStyle . '" >' . $line['validatedduration']  . '</TD>' ;
          if ($col=='Resource') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '" >' . $line["resource"]  . '</TD>' ;
          if ($col=='Responsible') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '" >' . $line["responsible"]  . '</TD>' ;
          if ($col=='RespInitial') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '" >' . $line["respinitial"]  . '</TD>' ;
          if ($col=='Priority') echo '  <TD class="reportTableData" style="text-align:center;' . $compStyle . '" >' . $line["priority"]  . '</TD>' ;
          if ($col=='IdPlanningMode') echo '  <TD class="reportTableData" style="text-align:left;' . $compStyle . '" ><span class="nobr">' . SqlList::getNameFromId('PlanningMode', $line["idplanningmode"])  . '</span></TD>' ;
          if ($col=='Id') echo '  <TD class="reportTableData" style="text-align:right;' . $compStyle . '" >' . $line["id"] . '</TD>' ;
        }
		    if ($pGroup) {
          $pColor='#505050;';
          //$pBackground='background:#505050 url(../view/img/grey.png) repeat-x;';
          $pBackground='background-color:#505050;';
        } else {
          if ($line['notplannedwork']>0) {        		
        		$pColor='#9933CC';
        		$pBackground='background-color:#9933CC;';
        	} else if (pq_trim($line['validatedenddate'])!="" && $line['validatedenddate'] < $pEnd) {
            $pColor='#BB5050';
            //$pBackground='background:#BB5050 url(../view/img/red.png) repeat-x;';
            $pBackground='background-color:#BB5050;';
          } else  {
            $pColor="#50BB50";
            //$pBackground='background:#50BB50 url(../view/img/green.png) repeat-x;';
            $pBackground='background-color:#50BB50;';
          }
        }
        $dispCaption=false;
        for ($i=0;$i<$numDays;$i++) {
          $color=$bgColor;
          $noBorder="border-left: 0px;";
          if ($format=='month') {
            $fontSize='90%';
            if ( $i<($numDays-1) and pq_substr($days[($i+1)],-2)!='01' ) {
              $noBorder="border-left: 0px;border-right: 0px;";
            }
          } else  if ($format=='quarter') {
            $fontSize='90%';
            if ( pq_substr($days[($i)],-2)!='26' or (pq_substr($days[($i)],5,2)!='03' and pq_substr($days[($i)],5,2)!='06' and pq_substr($days[($i)],5,2)!='09' and pq_substr($days[($i)],5,2)!='12') ) {
               $noBorder="border-left: 0px;border-right: 0px;";
            }
          } else if($format=='week') {
            $fontSize='90%';
            if ( ( ($i+1) % $colUnit)!=0) {
              $noBorder="border-left: 0px;border-right: 0px;";
            }
          } else if ($format=='day') {
            $fontSize='150%';
            $color=($openDays[$i]==1)?$bgColor:'background-color:' . $weekendColor . ';';
          }
          $height=($pGroup)?'8':'12';
          if ($days[$i]>=$pStart and $days[$i]<=$pEnd) {
            if ($rowType=="mile") {
              echo '<td class="reportTableData" style="font-size: ' . $fontSize . ';' . $color . $noBorder . ';color:' . $pColor . ';">';
              if($progress < 100) {
                echo '&loz;' ;
              } else {
                echo '&diams;' ;
              }
            } else {
              $subHeight=round((18-$height)/2);
              echo '<td class="reportTableData" style="width:' . $width .';padding:0px;' . $color . '; vertical-align: middle;' . $noBorder . '">';
              if ($pGroup and ($days[$i]==$pStart or $days[$i]==$pEnd) and $outMode!='pdf') {
                echo '<div class="ganttTaskgroupBarExtInvisible" style="float:left; height:4px"></div>';
              }
              echo '<table width="100%" >';
              echo '<tr height="' . $height . 'px"><td style="width:100%; ' . $pBackground . 'height:' .  $height . 'px;"></td></tr>';
              echo '</table>';
              if ($pGroup and $days[$i]==$pStart and $outMode!='pdf') {
                if ($format=='quarter' or $format=='month') {
                  echo '<div class="" style="float:left; height:4px"></div>';
                } else { 
                  echo '<div class="ganttTaskgroupBarExt" style="float:left; height:4px"></div>';
                }
              }
              if ($pGroup and $days[$i]==$pEnd and $outMode!='pdf') {
                if ($format=='quarter' or $format=='month') {
                  echo '<div class="" style="float:left; height:4px"></div>';
                } else { 
                  echo '<div class="ganttTaskgroupBarExt" style="float:right; height:4px"></div>';
                }
	            }
              $dispCaption=($showResource)?true:false;
            }
          } else {
            echo '<td class="reportTableData" width="' . $width .'" style="width: ' . $width . $color . $noBorder . '">';
          }
          echo '</td>';
          if ($format=="quarter") {
            $dom=intval(pq_substr($days[$i],8,2));
            if ($dom>=26) {
              $lastDayOfMonth=date('t',pq_strtotime($days[$i]));
              $i=array_search(pq_substr($days[$i],0,8).$lastDayOfMonth,$days);
            } else {
              $i+=4;
            }
          }
        }
        echo '</TR>';
      } else {
          echo i18n($line['reftype']) . $csvSep . $line['refid'] . $csvSep . html_entity_decode(strip_tags($tab), ENT_QUOTES, 'UTF-8') . html_entity_decode($pName, ENT_QUOTES, 'UTF-8') . $csvSep;
          foreach ($sortArray as $col) {          
            if (isset($columnsDescription[$col]) and $columnsDescription[$col]['show']!=1) continue;
            if ($col=='ValidatedWork') echo formatNumericOutput(Work::displayWork($line["validatedwork"]))  . $csvSep;
            if ($col=='AssignedWork') echo formatNumericOutput(Work::displayWork($line["assignedwork"]))  . $csvSep;
            if ($col=='RealWork') echo formatNumericOutput(Work::displayWork($line["realwork"]))  . $csvSep;
            if ($col=='LeftWork') echo formatNumericOutput(Work::displayWork($line["leftwork"]))  . $csvSep;
            if ($col=='PlannedWork') echo formatNumericOutput(Work::displayWork($line["plannedwork"]))  . $csvSep;
            if ($col=='ValidatedCost') echo formatNumericOutput($line["validatedcost"])  . $csvSep;
            if ($col=='AssignedCost') echo formatNumericOutput($line["assignedcost"])  . $csvSep;
            if ($col=='RealCost') echo formatNumericOutput($line["realcost"])  . $csvSep;
            if ($col=='LeftCost') echo formatNumericOutput($line["leftcost"])  . $csvSep;
            if ($col=='PlannedCost') echo formatNumericOutput($line["plannedcost"])  . $csvSep;
            if ($col=='Type') echo $line["type"]  . $csvSep;
            if ($col=='IdStatus') echo $line["status"]  . $csvSep . $line["statuscolor"]  . $csvSep;
            if ($col=='IdHealthStatus' and $portfolio) echo $line["health"]  . $csvSep . ((isset($line["healthcolor"]))?$line["healthcolor"]:'')  . $csvSep;
            if ($col=='QualityLevel' and $portfolio) echo $line["quality"]  . $csvSep . ((isset($line["qualitycolor"]))?$line["qualitycolor"]:'')  . $csvSep;
            if ($col=='IdTrend' and $portfolio) echo $line["trend"]  . $csvSep . ((isset($line["trendcolor"]))?$line["trendcolor"]:'')  . $csvSep;
            if ($col=='IdOverallProgress' and $portfolio) echo $line["overallprogress"]  . $csvSep ;
            if ($col=='Duration') echo $durationNumeric . $csvSep;
            if ($col=='Progress') echo $progress . $csvSep;
            if ($col=='StartDate') echo (($pStart)?dateFormatter($pStart):'-'). $csvSep;
            if ($col=='EndDate') echo (($pEnd)?dateFormatter($pEnd):'-'). $csvSep;
            if ($col=='Tags') echo tagFormatter($line['tags']) . $csvSep;
            if ($col=='IdContact') echo ((isset($line['idcontactdisplay']))?strip_tags($line['idcontactdisplay']):'') . $csvSep;
            if ($col=='IdActivity') echo ((isset($line['idactivitydisplay']))?strip_tags($line['idactivitydisplay']):'') . $csvSep;
            if ($col=='UnitToRealise') echo ((isset($line['unittorealise']))?$line['unittorealise']:'') . $csvSep;
            if ($col=='UnitWeight') echo ((isset($line['unitweight']))?$line['unitweight']:'') . $csvSep;
            if ($col=='Origin') echo ((isset($line['origindisplay']))?$line['origindisplay']:'') . $csvSep;
            if ($col=='Successor') echo ((isset($line['successor']))?$line['successor']:'') . $csvSep;
            if ($col=='ValidatedStartDate') echo (($line['validatedstartdate'])?dateFormatter($line['validatedstartdate']):'-'). $csvSep;
            if ($col=='ValidatedEndDate') echo (($line['validatedenddate'])?dateFormatter($line['validatedenddate']):'-'). $csvSep;
            if ($col=='ValidatedDuration') echo $line['validatedduration'] . $csvSep;
            if ($col=='Resource') echo strip_tags($line["resource"])  . $csvSep;
            if ($col=='Responsible') echo strip_tags($line["responsible"])  . $csvSep;
            if ($col=='RespInitial') echo strip_tags($line["respinitial"])  . $csvSep;
            if ($col=='Priority') echo $line["priority"]  . $csvSep;
            if ($col=='IdPlanningMode') echo SqlList::getNameFromId('PlanningMode', $line["idplanningmode"])  . $csvSep;
          }
          echo "\n";
		}
      }
    }
  	if($outMode != 'csv') {
  	  if(isset($displayIsLimited) and $displayIsLimited){
  	    $spanMessage=$cptSort+$totalspan;
  	    echo '<td colspan="'.$spanMessage.'" style="background:#FFDDDD;font-size:150%;color:#808080;text-align:left;padding: 10px 50px 10px;">';
  	    echo i18n('limitedDisplay',array($limitDisplay));
  	    echo '</td>';
  	  }
  	  echo "</table></div>";
  	}
  }

  function exportGantt($result,$displayLikePlanning) {
    global $nbQueriedRows,$applyFilter,$arrayRestrictWbs;
  	$paramDbDisplayName=Parameter::getGlobalParameter('paramDbDisplayName');
  	$currency=Parameter::getGlobalParameter('currency');
  	$currencyPosition=Parameter::getGlobalParameter('currencyPosition');
  	$exportAssignments=true;
  	if (Parameter::getGlobalParameter('doNotExportAssignmentsForXMLFormat')===true) $exportAssignments=false;
  	if (Parameter::getUserParameter('exportAssignmentsForXMLFormat')=='NO') $exportAssignments=false;
  	$nl="\n";
  	$tab="\t";
  	$hoursPerDay=Parameter::getGlobalParameter('dayTime');
  	if(!$hoursPerDay)$hoursPerDay=8;
    $startDate=date('Y-m-d');
    $startAM=getDailyHours(null, 'startAM', true);
    $endAM=getDailyHours(null, 'endAM', true);
    $startPM=getDailyHours(null, 'startPM', true);
    $endPM=getDailyHours(null, 'endPM', true);
    $name="export_planning_" . date('Ymd_His') . ".xml";
    $now=date('Y-m-d').'T'.date('H:i:s');
    if (pq_array_key_exists('startDate',$_REQUEST)) {
      $startDate=$_REQUEST['startDate'];
	    Security::checkValidDateTime($startDate);
    }
    $endDate='';
    if (pq_array_key_exists('endDate',$_REQUEST)) {
      $endDate=$_REQUEST['endDate'];
	    Security::checkValidDateTime($endDate);
    }
    $maxDate = '';
    $minDate = '';
    $resultArray=array();
    $selectItems="('',0)";
    $allItems=array();
    if ($nbQueriedRows > 0) {
      while ($line = Sql::fetchLine($result)) {
      	$line=array_change_key_case($line,CASE_LOWER);
      	$allItems[$line['id']]=$line['id'];
      	$selectItems.=",('".$line['reftype']."',".$line['refid'].")";
      	if ($applyFilter and !isset($arrayRestrictWbs[$line['wbssortable']])) continue; // Filter applied and item is not selected and not a parent of selected
        $pStart="";
        $pStart=(pq_trim($line['initialstartdate'])!="")?$line['initialstartdate']:$pStart;
        $pStart=(pq_trim($line['validatedstartdate'])!="")?$line['validatedstartdate']:$pStart;
        $pStart=(pq_trim($line['plannedstartdate'])!="")?$line['plannedstartdate']:$pStart;
        $pStart=(pq_trim($line['realstartdate'])!="")?$line['realstartdate']:$pStart;
        if (pq_trim($line['plannedstartdate'])!=""
        and pq_trim($line['realstartdate'])!=""
        and $line['plannedstartdate']<$line['realstartdate'] ) {
          $pStart=$line['plannedstartdate'];
        }
        $pEnd="";
        $pEnd=(pq_trim($line['initialenddate'])!="")?$line['initialenddate']:$pEnd;
        $pEnd=(pq_trim($line['validatedenddate'])!="")?$line['validatedenddate']:$pEnd;
        $pEnd=(pq_trim($line['plannedenddate'])!="")?$line['plannedenddate']:$pEnd;
        $pEnd=(pq_trim($line['realenddate'])!="")?$line['realenddate']:$pEnd;
        if ($line['reftype']=='Milestone') {
          $pStart=$pEnd;
        }
        if (! $pStart) $pStart=date('Y-m-d');
        if (! $pEnd) $pEnd=date('Y-m-d');
        $line['pstart']=$pStart;
        $line['pend']=$pEnd;
        $line['pduration']=workDayDiffDates($pStart,$pEnd, $line['idproject']);
        if ($line['reftype']=='Milestone') {
          $line['pduration']=0;
        }        
        if (Parameter::getGlobalParameter('hideItemTypeRestrictionOnProject')=='YES') {
          $ref=$line['reftype'];
          if ($ref=='PeriodicMeeting') $ref='Meeting';
          $type=SqlElement::getTypeName($ref);
          $item=new $ref($line['refid'],true);
          if (property_exists($ref, $type) and property_exists($ref, 'idProject')) {
            $prj=($ref=='Project')?$item->id:$item->idProject;
            if (! RestrictType::isTypeVisibleForProject($ref, $item->$type, $prj)) {
              $line["hidden"]=1;
            }
          }
        }
        $resultArray[]=$line;
        if ($maxDate=='' or $maxDate<$pEnd) {$maxDate=$pEnd;}
        if ($minDate=='' or $minDate>$pStart) {$minDate=$pStart;}
      }
      if ($endDate and $maxDate>$endDate) {
        //$maxDate=$endDate; // PBE : REMOVED, SETS THE MESS
      }
    }
    $globalProgress=0;
    $globalStart='';
    $globalPlanWork=0;
    $globalRealWork=0;
    $globalLeftWork=0;
    $globalDuration=0;
    $arrayVisible=array();
    for ($i = (count($resultArray)) - 1; $i>=0; $i--) {
      $item = $resultArray[$i];
      if ($item['id']==0){continue;}
      $wbs=$item['wbssortable'];
      if (! isset($item['hidden']) or $item['hidden']=="0" or $item['hidden']=="" or !$item['hidden']) {
        while (pq_strlen($wbs)>=5 and ! isset($arrayVisible[$wbs]) ) {
          $arrayVisible[$wbs]=$wbs;
          $wbs=pq_substr($wbs, 0, -6);
        }
      }
    }
    for ($i=0;$i<count($resultArray);$i++) {
      $wbs=$resultArray[$i]['wbssortable'];
      if ($i==0) {
        $globalProgress=($resultArray[$i]['plannedwork']>0)?round(100*$resultArray[$i]['realwork']/$resultArray[$i]['plannedwork'],2):'0';
        $globalStart=$resultArray[$i]['pstart'];
        $globalPlanWork=$resultArray[$i]['plannedwork'];
        $globalRealWork=$resultArray[$i]['realwork'];
        $globalLeftWork=$resultArray[$i]['leftwork'];
        $globalDuration=$resultArray[$i]['pduration'];
      }
      for ($j=$i+1;$j<count($resultArray);$j++) {
        if (pq_substr($resultArray[$j]['wbssortable'],0,pq_strlen($wbs))!=$wbs) break;
        if ($resultArray[$j]['pstart']<$resultArray[$i]['pstart']) {
          $resultArray[$i]['pstart']=$resultArray[$j]['pstart'];
          $resultArray[$i]['pduration']=workDayDiffDates($resultArray[$i]['pstart'],$resultArray[$i]['pend'], $resultArray[$i]['idproject']);
        }
        if ($resultArray[$j]['pend']>$resultArray[$i]['pend']) {
          $resultArray[$i]['pend']=$resultArray[$j]['pend'];
          $resultArray[$i]['pduration']=workDayDiffDates($resultArray[$i]['pstart'],$resultArray[$i]['pend'], $resultArray[$i]['idproject']);
        }
      }
    }
    if (getSessionValue('project') and getSessionValue('project')!='*' and pq_strpos(getSessionValue('project'), ",") === null) {
      $prj=new Project(getSessionValue('project'), true);
      $lstTopPrj=$prj->getTopProjectList(true);
      $in=transformValueListIntoInClause($lstTopPrj);
      $where="idProject in " . $in;
      $aff=new Affectation();
      $affList=$aff->getSqlElementsFromCriteria(null,false, $where, " id asc");
      $resourceList=array();
      foreach ($affList as $aff) {
        if (isset($resourceList[$aff->idResource])) return;
        $resourceList[$aff->idResource]=new ResourceAll($aff->idResource,true);
      }
    } else {
      $res=new ResourceAll();
      $asTemp=new Assignment();
      $asTable=$asTemp->getDatabaseTableName();
      $crit="id in ( select idResource from $asTable asx where (asx.refType, asx.refId) in ($selectItems) )";
      $resourceList=$res->getSqlElementsFromCriteria(null, false, $crit, " id asc");
    }

    echo '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' . $nl;
    echo '<Project xmlns="http://schemas.microsoft.com/project">' . $nl;
    echo $tab.'<SaveVersion>14</SaveVersion>' . $nl;
    echo $tab.'<Name>' . htmlEncode($name,'xml') . '</Name>' . $nl;
    echo $tab.'<Title>' . htmlEncode($paramDbDisplayName,'xml') . '</Title>' . $nl;
    echo $tab.'<CreationDate>' . $now . '</CreationDate>' . $nl;
    echo $tab.'<LastSaved>' . $now . '</LastSaved>' . $nl;
    echo $tab.'<ScheduleFromStart>1</ScheduleFromStart>' . $nl;
    echo $tab.'<StartDate>' . $minDate . 'T'.$startAM.'</StartDate>' . $nl;
    echo $tab.'<FinishDate>' . $maxDate . 'T'.$endPM.'</FinishDate>' . $nl;
    echo $tab.'<FYStartDate>1</FYStartDate>' . $nl;
    echo $tab.'<CriticalSlackLimit>0</CriticalSlackLimit>' . $nl;
    echo $tab.'<CurrencyDigits>2</CurrencyDigits>' . $nl;
    echo $tab.'<CurrencySymbol>' . $currency . '</CurrencySymbol>' . $nl;
    $currencyCode = getCurrencyCode($currency);
    if($currencyCode){
      echo $tab.'<CurrencyCode>' . getCurrencyCode($currency) . '</CurrencyCode>' . $nl;
    }
    echo $tab.'<CurrencySymbolPosition>' . (($currencyPosition=='before')?'2':'3') . '</CurrencySymbolPosition>' . $nl;
    echo $tab.'<CalendarUID>0</CalendarUID>' . $nl;
    echo $tab.'<DefaultStartTime>' . $startAM . '</DefaultStartTime>' . $nl;
    echo $tab.'<DefaultFinishTime>' . $endPM . '</DefaultFinishTime>' . $nl;
    echo $tab.'<MinutesPerDay>' . ($hoursPerDay*60) . '</MinutesPerDay>' . $nl;
    echo $tab.'<MinutesPerWeek>' . ($hoursPerDay*60*5) . '</MinutesPerWeek>' . $nl;
    echo $tab.'<DaysPerMonth>20</DaysPerMonth>' . $nl;
    echo $tab.'<DefaultTaskType>2</DefaultTaskType>' . $nl;
    echo $tab.'<DefaultFixedCostAccrual>2</DefaultFixedCostAccrual>' . $nl;
    echo $tab.'<DefaultStandardRate>10</DefaultStandardRate>' . $nl;
    echo $tab.'<DefaultOvertimeRate>15</DefaultOvertimeRate>' . $nl;
    echo $tab.'<DurationFormat>'.getDurationFormat().'</DurationFormat>' . $nl;
    echo $tab.'<WorkFormat>'.getWorkFormat().'</WorkFormat>' . $nl;
    echo $tab.'<EditableActualCosts>0</EditableActualCosts>' . $nl;
    echo $tab.'<HonorConstraints>0</HonorConstraints>' . $nl;
    // echo $tab.'<EarnedValueMethod>0</EarnedValueMethod>' . $nl;
    echo $tab.'<InsertedProjectsLikeSummary>0</InsertedProjectsLikeSummary>' . $nl;
    echo $tab.'<MultipleCriticalPaths>0</MultipleCriticalPaths>' . $nl;
    echo $tab.'<NewTasksEffortDriven>0</NewTasksEffortDriven>' . $nl;
    echo $tab.'<NewTasksEstimated>0</NewTasksEstimated>' . $nl;
    echo $tab.'<SplitsInProgressTasks>0</SplitsInProgressTasks>' . $nl;
    echo $tab.'<SpreadActualCost>0</SpreadActualCost>' . $nl;
    echo $tab.'<SpreadPercentComplete>0</SpreadPercentComplete>' . $nl;
    echo $tab.'<TaskUpdatesResource>1</TaskUpdatesResource>' . $nl;
    echo $tab.'<FiscalYearStart>0</FiscalYearStart>' . $nl;
    echo $tab.'<WeekStartDay>1</WeekStartDay>' . $nl;
    echo $tab.'<MoveCompletedEndsBack>0</MoveCompletedEndsBack>' . $nl;
    echo $tab.'<MoveRemainingStartsBack>0</MoveRemainingStartsBack>' . $nl;
    echo $tab.'<MoveRemainingStartsForward>0</MoveRemainingStartsForward>' . $nl;
    echo $tab.'<MoveCompletedEndsForward>0</MoveCompletedEndsForward>' . $nl;
    echo $tab.'<BaselineForEarnedValue>0</BaselineForEarnedValue>' . $nl;
    echo $tab.'<AutoAddNewResourcesAndTasks>1</AutoAddNewResourcesAndTasks>' . $nl;
    echo $tab.'<CurrentDate>' . $now . '</CurrentDate>' . $nl;
    echo $tab.'<MicrosoftProjectServerURL>1</MicrosoftProjectServerURL>' . $nl;
    echo $tab.'<Autolink>1</Autolink>' . $nl;
    echo $tab.'<NewTaskStartDate>0</NewTaskStartDate>' . $nl;
    echo $tab.'<NewTasksAreManual>1</NewTasksAreManual>'. $nl;
    echo $tab.'<DefaultTaskEVMethod>0</DefaultTaskEVMethod>' . $nl;
    echo $tab.'<ProjectExternallyEdited>1</ProjectExternallyEdited>' . $nl;
    //echo $tab.'<ExtendedCreationDate>'.$now.'</ExtendedCreationDate>' . $nl;
    echo $tab.'<ExtendedCreationDate>1984-01-01T00:00:00</ExtendedCreationDate>' . $nl;
    echo $tab.'<ActualsInSync>0</ActualsInSync>' . $nl;
    echo $tab.'<RemoveFileProperties>0</RemoveFileProperties>' . $nl;
    echo $tab.'<AdminProject>0</AdminProject>' . $nl;
    echo $tab.'<UpdateManuallyScheduledTasksWhenEditingLinks>0</UpdateManuallyScheduledTasksWhenEditingLinks>'. $nl;
	  echo $tab.'<KeepTaskOnNearestWorkingTimeWhenMadeAutoScheduled>0</KeepTaskOnNearestWorkingTimeWhenMadeAutoScheduled>'. $nl;
	  if (Parameter::getUserParameter('lang')=='fr') {
    echo $tab.'<Views>' . $nl;
    echo $tab.$tab.'<View>' . $nl;
    echo $tab.$tab.$tab.'<Name>Gantt with chronology</Name>' . $nl;
    echo $tab.$tab.'</View>' . $nl;
    echo $tab.$tab.'<View>' . $nl;
    echo $tab.$tab.$tab.'<Name>Gantt Diagram</Name>' . $nl;
    //echo $tab.$tab.$tab.'<IsCustomized>true</IsCustomized>' . $nl;
    echo $tab.$tab.'</View>' . $nl;
    echo $tab.$tab.'<View>' . $nl;
    echo $tab.$tab.$tab.'<Name>Chronology</Name>' . $nl;
    echo $tab.$tab.'<IsCustomized>true</IsCustomized>' . $nl;
    echo $tab.$tab.'</View>' . $nl;
    echo $tab.'</Views>' . $nl;
    echo $tab.'<Filters>' . $nl;
    echo $tab.$tab.'<Filter>' . $nl;
    echo $tab.$tab.$tab.'<Name>All tasks</Name>' . $nl;
    echo $tab.$tab.'</Filter>' . $nl;
    echo $tab.$tab.'<Filter>' . $nl;
    echo $tab.$tab.$tab.'<Name>All resources</Name>' . $nl;
    echo $tab.$tab.'</Filter>' . $nl;
    echo $tab.'</Filters>' . $nl;
    echo $tab.'<Groups>' . $nl;
    echo $tab.$tab.'<Group>' . $nl;
    echo $tab.$tab.$tab.'<Name>No group</Name>' . $nl;
    echo $tab.$tab.'</Group>' . $nl;
    echo $tab.$tab.'<Group>' . $nl;
    echo $tab.$tab.$tab.'<Name>No group</Name>' . $nl;
    echo $tab.$tab.'</Group>' . $nl;
    echo $tab.'</Groups>' . $nl;
    echo $tab.'<Tables>' . $nl;
    echo $tab.$tab.'<Table>' . $nl;
    echo $tab.$tab.$tab.'<Name>Entry</Name>' . $nl;
    echo $tab.$tab.'</Table>' . $nl;
    echo $tab.'</Tables>' . $nl;
	  }
    echo $tab.'<Maps/>' . $nl;
    echo $tab.'<Reports/>' . $nl;
    echo $tab.'<Drawings/>' . $nl;
    echo $tab.'<DataLinks/>' . $nl;
    echo $tab.'<VBAProjects/>' . $nl;
	  
    echo $tab.'<OutlineCodes/>' . $nl;
    echo $tab.'<WBSMasks/>' . $nl;
    echo $tab.'<ExtendedAttributes/>' . $nl;
    /*<ExtendedAttributes>
        <ExtendedAttribute>
            <FieldID>188743731</FieldID>
            <FieldName>Text1</FieldName>
        </ExtendedAttribute>
    </ExtendedAttributes>*/
    $cal=new CalendarDefinition();
    $calList=$cal->getSqlElementsFromCriteria(array('idle'=>'0'));
    echo $tab.'<Calendars>' . $nl;
    foreach($calList as $cal) {
      echo $tab.$tab.'<Calendar>' . $nl;
      echo $tab.$tab.$tab.'<UID>'.($cal->id -1).'</UID>' . $nl;
      echo $tab.$tab.$tab.'<Name>'.$cal->name.'</Name>' . $nl;
      echo $tab.$tab.$tab.'<IsBaseCalendar>1</IsBaseCalendar>' . $nl;
      echo $tab.$tab.$tab.'<IsBaselineCalendar>0</IsBaselineCalendar>' .$nl;
      echo $tab.$tab.$tab.'<BaseCalendarUID>-1</BaseCalendarUID>' . $nl;
      echo $tab.$tab.$tab.'<WeekDays>' . $nl;
      for ($i=1;$i<=7;$i++) {
        echo $tab.$tab.$tab.$tab.'<WeekDay>' . $nl;
        echo $tab.$tab.$tab.$tab.$tab.'<DayType>' . $i . '</DayType>' . $nl;
        $ofDays = false;
        if($i==1 or $i==7) $ofDays= true;
        if($i==2 and $cal->dayOfWeek1==1){
          $ofDays= true;
        }
        if($i==3 and $cal->dayOfWeek2==1){
          $ofDays= true;
        }
        if($i==4 and $cal->dayOfWeek3==1){
          $ofDays= true;
        }
        if($i==5 and $cal->dayOfWeek4==1){
          $ofDays= true;
        }
        if($i==6 and $cal->dayOfWeek5==1){
          $ofDays= true;
        }
        if( $ofDays  ){
        	echo $tab.$tab.$tab.$tab.$tab.'<DayWorking>0</DayWorking>' . $nl;
        } else {
  	      echo $tab.$tab.$tab.$tab.$tab.'<DayWorking>1</DayWorking>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.'<WorkingTimes>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.'<WorkingTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.$tab.'<FromTime>' . $startAM . '</FromTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.$tab.'<ToTime>' . $endAM . '</ToTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.'</WorkingTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.'<WorkingTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.$tab.'<FromTime>' . $startPM . '</FromTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.$tab.'<ToTime>' . $endPM . '</ToTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.$tab.'</WorkingTime>' . $nl;
  	      echo $tab.$tab.$tab.$tab.$tab.'</WorkingTimes>' . $nl;
        }
        echo $tab.$tab.$tab.$tab.'</WeekDay>' . $nl;
      }
      $calDay=new Calendar();
      $dayList=$calDay->getSqlElementsFromCriteria(array('idCalendarDefinition'=>$cal->id),null,null,'calendarDate asc');
      foreach ($dayList as $calDay) {
        echo $tab.$tab.$tab.$tab.'<WeekDay>' . $nl;
  			echo $tab.$tab.$tab.$tab.$tab.'<DayType>0</DayType>' . $nl;
  			echo $tab.$tab.$tab.$tab.$tab.'<DayWorking>'.(($calDay->isOffDay)?0:1).'</DayWorking>' . $nl;
  			echo $tab.$tab.$tab.$tab.$tab.'<TimePeriod>' . $nl;
  			echo $tab.$tab.$tab.$tab.$tab.$tab.'<FromDate>'.$calDay->calendarDate.'T00:00:00</FromDate>' . $nl;
  			echo $tab.$tab.$tab.$tab.$tab.$tab.'<ToDate>'.$calDay->calendarDate.'T23:59:00</ToDate>' . $nl;
  			echo $tab.$tab.$tab.$tab.$tab.'</TimePeriod>' . $nl;
  			echo $tab.$tab.$tab.$tab.'</WeekDay>'.$nl;
      }
      echo $tab.$tab.$tab.'</WeekDays>' . $nl;
      echo $tab.$tab.'</Calendar>' . $nl;
      foreach ($resourceList as $resource) {
        if($resource->idCalendarDefinition != $cal->id) continue;
        if ($exportAssignments==false) continue;
      	echo $tab.$tab."<Calendar>" . $nl;
        echo $tab.$tab.$tab."<UID>" . htmlEncode($resource->id,'xml') . "</UID>" . $nl;
        echo $tab.$tab.$tab."<Name>" . htmlEncode($resource->name,'xml') . "</Name>" . $nl;
        echo $tab.$tab.$tab."<IsBaseCalendar>0</IsBaseCalendar>" . $nl;
        echo $tab.$tab.$tab."<IsBaselineCalendar>0</IsBaselineCalendar>". $nl;
        echo $tab.$tab.$tab."<BaseCalendarUID>".($resource->idCalendarDefinition -1)."</BaseCalendarUID>" . $nl;
        $work = new Work();
        $where1 = " idResource = ".$resource->id." and idProject in " . Project::getAdminitrativeProjectList(false, false);    
        $lstWork = $work->getSqlElementsFromCriteria(null,false,$where1);
        if(count($lstWork)>0)echo $tab.$tab.$tab.'<WeekDays>' . $nl;
        foreach ($lstWork as $admWork){
          echo $tab.$tab.$tab.$tab.'<WeekDay>' . $nl;
          echo $tab.$tab.$tab.$tab.$tab.'<DayType>0</DayType>' . $nl;
          if($admWork->work < 1 ){
            echo $tab.$tab.$tab.$tab.$tab.'<DayWorking>1</DayWorking>' . $nl;
          }else{
            echo $tab.$tab.$tab.$tab.$tab.'<DayWorking>0</DayWorking>' . $nl;
          }
          echo $tab.$tab.$tab.$tab.$tab.'<TimePeriod>' . $nl;
          echo $tab.$tab.$tab.$tab.$tab.$tab.'<FromDate>'.$admWork->workDate.'T00:00:00</FromDate>' . $nl;
          echo $tab.$tab.$tab.$tab.$tab.$tab.'<ToDate>'.$admWork->workDate.'T23:59:00</ToDate>' . $nl;
          echo $tab.$tab.$tab.$tab.$tab.'</TimePeriod>' . $nl;
          if($admWork->work < 1 ){
            (float)$nbHourWork = $admWork->work;
            $hourEnd = round($nbHourWork*(float)$hoursPerDay,PHP_ROUND_HALF_EVEN);
            $explodeValue = pq_explode(':',$startAM);
            $valueFloat = (float)$explodeValue[0] + $hourEnd;
            echo $tab.$tab.$tab.$tab.$tab.'<WorkingTimes>' . $nl;
            echo $tab.$tab.$tab.$tab.$tab.$tab.'<WorkingTime>' . $nl;
            echo $tab.$tab.$tab.$tab.$tab.$tab.$tab.'<FromTime>'.$startAM.'</FromTime>' . $nl;
            echo $tab.$tab.$tab.$tab.$tab.$tab.$tab.'<ToTime>'.$valueFloat.':00:00</ToTime>' . $nl;
            echo $tab.$tab.$tab.$tab.$tab.$tab.'</WorkingTime>' . $nl;
            echo $tab.$tab.$tab.$tab.$tab.'</WorkingTimes>' . $nl;
          }
          echo $tab.$tab.$tab.$tab.'</WeekDay>'.$nl;
        }
         if(count($lstWork)>0)echo $tab.$tab.$tab.'</WeekDays>' . $nl;
        //
        echo $tab.$tab."</Calendar>" . $nl;
      }
    }
    echo $tab.'</Calendars>'.$nl;
    echo $tab.'<Tasks>' . $nl;
    // First task for project
    echo $tab.$tab.'<Task>' . $nl;
    echo $tab.$tab.$tab.'<UID>0</UID>' . $nl;
    echo $tab.$tab.$tab.'<ID>0</ID>' . $nl;
    echo $tab.$tab.$tab.'<Name>' . htmlEncode($paramDbDisplayName,'xml') . '</Name>' . $nl;
    echo $tab.$tab.$tab.'<Active>1</Active>' . $nl;
    echo $tab.$tab.$tab.'<Manual>1</Manual>' . $nl;
    echo $tab.$tab.$tab.'<Type>1</Type>' . $nl;
    echo $tab.$tab.$tab.'<IsNull>0</IsNull>' . $nl;
    echo $tab.$tab.$tab.'<CreateDate>'.$now.'</CreateDate>' . $nl;
    echo $tab.$tab.$tab.'<WBS>0</WBS>' . $nl;
    echo $tab.$tab.$tab.'<OutlineNumber>0</OutlineNumber>' . $nl;
    echo $tab.$tab.$tab.'<OutlineLevel>0</OutlineLevel>' . $nl;
    echo $tab.$tab.$tab.'<Priority>500</Priority>' . $nl;
    echo $tab.$tab.$tab.'<Start>'.date('Y-m-d').'T00:00:00</Start>' . $nl;
    echo $tab.$tab.$tab.'<Finish>'.date('Y-m-d').'T00:00:00</Finish>' . $nl;
    echo $tab.$tab.$tab.'<Duration>'.formatDuration($globalDuration,$hoursPerDay).'</Duration>' . $nl;
    echo $tab.$tab.$tab.'<ManualStart>'.date('Y-m-d').'T00:00:00</ManualStart>' . $nl;
    echo $tab.$tab.$tab.'<ManualFinish>'.date('Y-m-d').'T00:00:00</ManualFinish>' . $nl;
    echo $tab.$tab.$tab.'<ManualDuration>PT0H0M0S</ManualDuration>' . $nl;
    echo $tab.$tab.$tab.'<DurationFormat>21</DurationFormat>' . $nl;
    echo $tab.$tab.$tab.'<Work>PT'.formatWork($globalPlanWork,$hoursPerDay).'</Work>' . $nl;
    echo $tab.$tab.$tab.'<Stop>'.$globalStart.'T'.$startAM.'</Stop>' . $nl;
    echo $tab.$tab.$tab.'<Resume>'.$globalStart.'T'.$startAM.'</Resume>' . $nl;
    echo $tab.$tab.$tab.'<FreeformDurationFormat>7</FreeformDurationFormat>' . $nl;
    echo $tab.$tab.$tab.'<ResumeValid>0</ResumeValid>' . $nl;
    echo $tab.$tab.$tab.'<EffortDriven>0</EffortDriven>' . $nl;
    echo $tab.$tab.$tab.'<Recurring>0</Recurring>' . $nl;
    echo $tab.$tab.$tab.'<OverAllocated>0</OverAllocated>' . $nl;
    echo $tab.$tab.$tab.'<Estimated>0</Estimated>' . $nl;
    echo $tab.$tab.$tab.'<Milestone>0</Milestone>' . $nl;
    echo $tab.$tab.$tab.'<Summary>1</Summary>' . $nl;
    echo $tab.$tab.$tab.'<DisplayAsSummary>0</DisplayAsSummary>' . $nl;
    echo $tab.$tab.$tab.'<Critical>0</Critical>' . $nl;
    echo $tab.$tab.$tab.'<IsSubproject>0</IsSubproject>' . $nl;
    echo $tab.$tab.$tab.'<IsSubprojectReadOnly>0</IsSubprojectReadOnly>' . $nl;
    echo $tab.$tab.$tab.'<ExternalTask>0</ExternalTask>' . $nl;
    echo $tab.$tab.$tab.'<EarlyStart>'.$pStart.'T00:00:00</EarlyStart>' . $nl;
    echo $tab.$tab.$tab.'<EarlyFinish>'.date('Y-m-d').'T00:00:00</EarlyFinish>' . $nl;
    echo $tab.$tab.$tab.'<LateStart>'.$pStart.'T'.$startAM.'</LateStart>' . $nl;
    echo $tab.$tab.$tab.'<LateFinish>'.date('Y-m-d').'T00:00:00</LateFinish>' . $nl;
    echo $tab.$tab.$tab.'<StartVariance>0</StartVariance>' . $nl;
    echo $tab.$tab.$tab.'<FinishVariance>0</FinishVariance>' . $nl;
    echo $tab.$tab.$tab.'<WorkVariance>0.00</WorkVariance>' . $nl;
    echo $tab.$tab.$tab.'<FreeSlack>0</FreeSlack>' . $nl;
    echo $tab.$tab.$tab.'<TotalSlack>0</TotalSlack>' . $nl;
    echo $tab.$tab.$tab.'<StartSlack>0</StartSlack>' . $nl;
    echo $tab.$tab.$tab.'<FinishSlack>0</FinishSlack>' . $nl;
    echo $tab.$tab.$tab.'<FixedCost>0</FixedCost>' . $nl;
    echo $tab.$tab.$tab.'<FixedCostAccrual>2</FixedCostAccrual>' . $nl;
    echo $tab.$tab.$tab.'<PercentComplete>0</PercentComplete>' . $nl;
    echo $tab.$tab.$tab.'<PercentWorkComplete>'.round($globalProgress,0).'</PercentWorkComplete>' . $nl;
    echo $tab.$tab.$tab.'<Cost>0</Cost>' . $nl;
    echo $tab.$tab.$tab.'<OvertimeCost>0</OvertimeCost>' . $nl;
    echo $tab.$tab.$tab.'<OvertimeWork>PT0H0M0S</OvertimeWork>' . $nl;
    echo $tab.$tab.$tab.'<ActualStart>'.$globalStart.'T'.$startAM.'</ActualStart>' . $nl;
    echo $tab.$tab.$tab.'<ActualDuration>PT0H0M0S</ActualDuration>' . $nl;
    echo $tab.$tab.$tab.'<ActualCost>0</ActualCost>' . $nl;
    echo $tab.$tab.$tab.'<ActualOvertimeCost>0</ActualOvertimeCost>' . $nl;
    echo $tab.$tab.$tab.'<ActualWork>PT'.formatWork($globalRealWork,$hoursPerDay).'</ActualWork>' . $nl;
    echo $tab.$tab.$tab.'<ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>' . $nl;
    echo $tab.$tab.$tab.'<RegularWork>PT'.formatWork($globalPlanWork,$hoursPerDay).'</RegularWork>' . $nl;
    echo $tab.$tab.$tab.'<RemainingDuration>PT0H0M0S</RemainingDuration>' . $nl;
    echo $tab.$tab.$tab.'<RemainingCost>0</RemainingCost>' . $nl;
    echo $tab.$tab.$tab.'<RemainingWork>PT'.formatWork($globalLeftWork,$hoursPerDay).'</RemainingWork>' . $nl;
    echo $tab.$tab.$tab.'<RemainingOvertimeCost>0</RemainingOvertimeCost>' . $nl;
    echo $tab.$tab.$tab.'<RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>' . $nl;
    echo $tab.$tab.$tab.'<ACWP>0.00</ACWP>' . $nl;
    echo $tab.$tab.$tab.'<CV>0.00</CV>' . $nl;
    echo $tab.$tab.$tab.'<ConstraintType>0</ConstraintType>' . $nl;
    echo $tab.$tab.$tab.'<CalendarUID>-1</CalendarUID>' . $nl;
    echo $tab.$tab.$tab.'<LevelAssignments>1</LevelAssignments>' . $nl;
    echo $tab.$tab.$tab.'<LevelingCanSplit>1</LevelingCanSplit>' . $nl;
    echo $tab.$tab.$tab.'<LevelingDelay>0</LevelingDelay>' . $nl;
    echo $tab.$tab.$tab.'<LevelingDelayFormat>8</LevelingDelayFormat>' . $nl;
    echo $tab.$tab.$tab.'<IgnoreResourceCalendar>0</IgnoreResourceCalendar>' . $nl;
    echo $tab.$tab.$tab.'<HideBar>0</HideBar>' . $nl;
    echo $tab.$tab.$tab.'<Rollup>0</Rollup>' . $nl;
    echo $tab.$tab.$tab.'<BCWS>0.00</BCWS>' . $nl;
    echo $tab.$tab.$tab.'<BCWP>0.00</BCWP>' . $nl;
    echo $tab.$tab.$tab.'<PhysicalPercentComplete>0</PhysicalPercentComplete>' . $nl;
    echo $tab.$tab.$tab.'<EarnedValueMethod>0</EarnedValueMethod>' . $nl;
    echo $tab.$tab.$tab.'<IsPublished>0</IsPublished>' . $nl;
    echo $tab.$tab.$tab.'<CommitmentType>0</CommitmentType>' . $nl;
    echo $tab.$tab.'</Task>' . $nl;
    
    $cpt=0;
    $arrayTask=array();
    
    foreach ($resultArray as $line) {
      $wbs=$line['wbssortable'];
      if (!isset($arrayVisible[$wbs])) continue;
      
    	$cpt++;
    	$arrayTask[$line['reftype'].'#'.$line['refid']]=array('id'=>$line['id']);
    	$pct=($line['plannedwork']>0)?round(100*$line['realwork']/$line['plannedwork'],0):'';
    	if (!$pct) $pct='0';
    	if (!$pct and $line['plannedwork']==0 and $line['realwork']==0 and pq_trim($line['realenddate'])) {
    	  $pct=100;
    	}
    	if ($line['leftwork']==0) $pct=100;
    	//if ($line['realwork']>0 and $line['leftwork']==0) $pct=100;
    	if ($line['reftype']=='Milestone') {
    	  if ($line['realenddate']) $pct=100;
    	  else $pct=0;
    	}
    	if ($line['plannedwork']==0 and $line['reftype']!='Milestone') {
    	  //$line['plannedwork']=0.01;
    	}
      echo $tab.$tab.'<Task>' . $nl;
      echo $tab.$tab.$tab.'<UID>' . $line['id'] . '</UID>' . $nl;
      echo $tab.$tab.$tab.'<projeqtorType>' . $line['reftype'] . '</projeqtorType>' . $nl;
      //gautier #4648
      if ($line['reftype']=='Activity') {
        echo $tab.$tab.$tab.'<projeqtorPlanningMode>' . $line['idplanningmode'] . '</projeqtorPlanningMode>' . $nl;
        $activ = new Activity($line['refid'],true);
        echo $tab.$tab.$tab.'<projeqtorActivityType>' . $activ->idActivityType . '</projeqtorActivityType>' . $nl;
      }
      //end Gautier
      echo $tab.$tab.$tab.'<ID>' . $cpt . '</ID>' . $nl;  // TODO : should be order of the tack in the list
      echo $tab.$tab.$tab.'<Name>' . htmlEncode($line['refname'],'xml') . '</Name>' . $nl;
      echo $tab.$tab.$tab.'<Active>1</Active>'. $nl;
      echo $tab.$tab.$tab.'<Manual>1</Manual>'. $nl;
      echo $tab.$tab.$tab.'<Type>1</Type>' . $nl; // TODO : 0=Fixed Units, 1=Fixed Duration, 2=Fixed Work.
      echo $tab.$tab.$tab.'<IsNull>0</IsNull>' . $nl;
      echo $tab.$tab.$tab.'<CreateDate>'.date('Y-m-d').'T'.date('H:i:s').'</CreateDate>'. $nl;
      echo $tab.$tab.$tab.'<WBS>' . $line['wbs'] . '</WBS>' . $nl;
      echo $tab.$tab.$tab.'<OutlineNumber>' . $line['wbs'] . '</OutlineNumber>' . $nl;
      echo $tab.$tab.$tab.'<OutlineLevel>' . (substr_count($line['wbs'],'.')+1) . '</OutlineLevel>' . $nl;
      $reversedPriority=($line['priority'])?(1000-intval($line['priority'])):'';
      echo $tab.$tab.$tab.'<Priority>' . $reversedPriority . '</Priority>' . $nl;
      echo $tab.$tab.$tab.'<Start>' . $line['pstart'] . 'T' . $startAM . '</Start>' . $nl;
      echo $tab.$tab.$tab.'<Finish>' . $line['pend'] . 'T' . (($line['reftype']=='Milestone')?$startAM:$endPM) . '</Finish>' . $nl;
      echo $tab.$tab.$tab.'<Duration>' . formatDuration($line['pduration'],$hoursPerDay) . '</Duration>' . $nl;
      echo $tab.$tab.$tab.'<ManualStart>' . $line['pstart'] . 'T' . $startAM . '</ManualStart>' . $nl;
      echo $tab.$tab.$tab.'<ManualFinish>' . $line['pend'] . 'T' . (($line['reftype']=='Milestone')?$startAM:$endPM) . '</ManualFinish>' . $nl;
      echo $tab.$tab.$tab.'<ManualDuration>' . formatDuration($line['pduration'],$hoursPerDay) . '</ManualDuration>' . $nl;
      echo $tab.$tab.$tab.'<DurationFormat>'.getDurationFormat().'</DurationFormat>' . $nl;
      echo $tab.$tab.$tab.'<Work>PT' . formatWork($line['plannedwork'],$hoursPerDay).'</Work>' . $nl;
      if ($cpt==1) echo $tab.$tab.$tab.'<Stop>'.$globalStart.'T'.$startAM.'</Stop>' . $nl;
      if ($cpt==1) echo $tab.$tab.$tab.'<Resume>'.$globalStart.'T'.$startAM.'</Resume>' . $nl;
      echo $tab.$tab.$tab.'<FreeformDurationFormat>'.getDurationFormat().'</FreeformDurationFormat>' . $nl;
      $arrayTask[$line['reftype'].'#'.$line['refid']]['start']=$line['pstart'] . 'T' . $startAM ;
      $arrayTask[$line['reftype'].'#'.$line['refid']]['end']=$line['pend'] . 'T' . $endPM;
      $arrayTask[$line['reftype'].'#'.$line['refid']]['duration']=formatDuration($line['pduration'],$hoursPerDay);
      $arrayTask[$line['reftype'].'#'.$line['refid']]['pct']=$pct;
      //$actualDuration=$line['pduration'];
      //$remainingDuration=0;
      // TRY PBE
      $totalDuration=$line['pduration'];
      $actualDuration=$totalDuration*$pct/100;
      $remainingDuration=$totalDuration-$actualDuration;
      if ($pct==100) echo $tab.$tab.$tab.'<Stop>' . $line['pend'] . 'T' . (($line['reftype']=='Milestone')?$startAM:$endPM) . '</Stop>' . $nl;
      //else echo $tab.$tab.$tab.'<Stop></Stop>' . $nl;
      if ($pct==100) echo $tab.$tab.$tab.'<Resume>' . $line['pend'] . 'T' . (($line['reftype']=='Milestone')?$startAM:$endPM) . '</Resume>' . $nl;
      $pctDuration=0;
      $work = new Work();
      $lstWork = $work->getSqlElementsFromCriteria(array('refType'=>$line['reftype'],'refId'=>$line['refid']));
      $minWorkDate='';
      $maxWorkDate='';
      foreach ($lstWork as $wk){
        if ($minWorkDate=='' or $wk->workDate<$minWorkDate) $minWorkDate=$wk->workDate;
        if ($maxWorkDate=='' or $wk->workDate>$maxWorkDate) $maxWorkDate=$wk->workDate;
      }
      if ($minWorkDate and $maxWorkDate and isset($line['duration']) and $line['duration']>0) {
        $actualDuration=workDayDiffDates($minWorkDate, $maxWorkDate, $line['idproject']);
        $pctDuration=$actualDuration/$line['duration']*100;
      }
      echo $tab.$tab.$tab.'<ResumeValid>0</ResumeValid>' . $nl;
      echo $tab.$tab.$tab.'<EffortDriven>1</EffortDriven>' . $nl;
      echo $tab.$tab.$tab.'<Recurring>0</Recurring>' . $nl;
      echo $tab.$tab.$tab.'<OverAllocated>0</OverAllocated>' . $nl;
      echo $tab.$tab.$tab.'<Estimated>0</Estimated>' . $nl;
      echo $tab.$tab.$tab.'<Milestone>' . (($line['reftype']=='Milestone')?'1':'0') . '</Milestone>' . $nl;
      echo $tab.$tab.$tab.'<Summary>' . (($line['elementary'])?'0':'1') . '</Summary>' . $nl;
      echo $tab.$tab.$tab.'<DisplayAsSummary>' . (($line['elementary'])?'0':'1') . '</DisplayAsSummary>' . $nl;
      echo $tab.$tab.$tab.'<Critical>0</Critical>' . $nl;
      echo $tab.$tab.$tab.'<IsSubproject>0</IsSubproject>' . $nl;
      echo $tab.$tab.$tab.'<IsSubprojectReadOnly>0</IsSubprojectReadOnly>' . $nl;
      echo $tab.$tab.$tab.'<ExternalTask>0</ExternalTask>' . $nl;
      echo $tab.$tab.$tab.'<EarlyStart>' . $line['pstart'] . 'T' . $startAM . '</EarlyStart>' . $nl;
      echo $tab.$tab.$tab.'<EarlyFinish>' . $line['pend'] . 'T' . (($line['reftype']=='Milestone')?$startAM:$endPM) . '</EarlyFinish>' . $nl;
      echo $tab.$tab.$tab.'<LateStart>' . $line['pstart'] . 'T' . $startAM . '</LateStart>' . $nl;
      echo $tab.$tab.$tab.'<LateFinish>' . $line['pend'] . 'T' . (($line['reftype']=='Milestone')?$startAM:$endPM) . '</LateFinish>' . $nl;
      echo $tab.$tab.$tab.'<StartVariance>0</StartVariance>' . $nl;
      echo $tab.$tab.$tab.'<FinishVariance>0</FinishVariance>' . $nl;
      //echo $tab.$tab.$tab.'<WorkVariance>'.(round($line['plannedwork']*$hoursPerDay,0)*60*1000).'.00</WorkVariance>' . $nl;
      echo $tab.$tab.$tab.'<WorkVariance>0</WorkVariance>' . $nl;
      echo $tab.$tab.$tab.'<FreeSlack>0</FreeSlack>' . $nl;
      echo $tab.$tab.$tab.'<TotalSlack>0</TotalSlack>' . $nl;
      echo $tab.$tab.$tab.'<StartSlack>0</StartSlack>' . $nl;
      echo $tab.$tab.$tab.'<FinishSlack>0</FinishSlack>' . $nl;
      echo $tab.$tab.$tab.'<FixedCost>0</FixedCost>' . $nl;
      echo $tab.$tab.$tab.'<FixedCostAccrual>2</FixedCostAccrual>' . $nl;
      echo $tab.$tab.$tab.'<PercentComplete>'.round($pctDuration,0).'</PercentComplete>' . $nl;
      echo $tab.$tab.$tab.'<PercentWorkComplete>'.$pct.'</PercentWorkComplete>' . $nl;
      echo $tab.$tab.$tab.'<Cost>0</Cost>' . $nl;
      echo $tab.$tab.$tab.'<OvertimeCost>0</OvertimeCost>' . $nl;
      echo $tab.$tab.$tab.'<OvertimeWork>PT0H0M0S</OvertimeWork>' . $nl;
      //if ($pct>0) echo $tab.$tab.$tab.'<ActualStart>' .  $line['pstart'] . 'T' . $startAM . '</ActualStart>' . $nl;
      echo $tab.$tab.$tab.'<ActualStart>' . (($line['pstart'])?$line['pstart'] . 'T' . $startAM:'') . '</ActualStart>' . $nl;
      if ($pct==100) echo $tab.$tab.$tab.'<ActualFinish>' . $line['pend'] . 'T' . (($line['reftype']=='Milestone')?$startAM:$endPM) . '</ActualFinish>' . $nl;
      echo $tab.$tab.$tab.'<ActualDuration>'.formatDuration($actualDuration,$hoursPerDay) .'</ActualDuration>' . $nl;
      echo $tab.$tab.$tab.'<ActualCost>0</ActualCost>' . $nl;
      echo $tab.$tab.$tab.'<ActualOvertimeCost>0</ActualOvertimeCost>' . $nl;
      echo $tab.$tab.$tab.'<ActualWork>PT' . formatWork($line['realwork'],$hoursPerDay) . '</ActualWork>' . $nl;
      echo $tab.$tab.$tab.'<ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>' . $nl;
      echo $tab.$tab.$tab.'<RegularWork>PT' . formatWork($line['plannedwork'],$hoursPerDay) . '</RegularWork>' . $nl;
      //echo $tab.$tab.$tab.'<RemainingDuration>' .  formatDuration($remainingDuration,$hoursPerDay) . '</RemainingDuration>' . $nl;
      echo $tab.$tab.$tab.'<RemainingDuration>' .  formatDuration($remainingDuration,$hoursPerDay) . '</RemainingDuration>' . $nl;
      echo $tab.$tab.$tab.'<RemainingCost>0</RemainingCost>' . $nl;
      echo $tab.$tab.$tab.'<RemainingWork>PT' . formatWork($line['leftwork'],$hoursPerDay) . '</RemainingWork>' . $nl;
      echo $tab.$tab.$tab.'<RemainingOvertimeCost>0</RemainingOvertimeCost>' . $nl;
      echo $tab.$tab.$tab.'<RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>' . $nl;
      echo $tab.$tab.$tab.'<ACWP>0.00</ACWP>' . $nl;
      echo $tab.$tab.$tab.'<CV>0.00</CV>' . $nl;
      echo $tab.$tab.$tab.'<ConstraintType>' . (($line['elementary'])?'0':'2') . '</ConstraintType>' . $nl;
      echo $tab.$tab.$tab.'<CalendarUID>-1</CalendarUID>' . $nl;
      if (1 or $line['elementary']) { echo $tab.$tab.$tab.'<ConstraintDate>' . $line['pstart'] . 'T' . $startAM . '</ConstraintDate>' . $nl;}
      echo $tab.$tab.$tab.'<LevelAssignments>0</LevelAssignments>' . $nl;
      echo $tab.$tab.$tab.'<LevelingCanSplit>0</LevelingCanSplit>' . $nl;
      echo $tab.$tab.$tab.'<LevelingDelay>0</LevelingDelay>' . $nl;
      echo $tab.$tab.$tab.'<LevelingDelayFormat>8</LevelingDelayFormat>' . $nl;
      echo $tab.$tab.$tab.'<IgnoreResourceCalendar>1</IgnoreResourceCalendar>' . $nl;
      echo $tab.$tab.$tab.'<HideBar>0</HideBar>' . $nl;
      echo $tab.$tab.$tab.'<Rollup>0</Rollup>' . $nl;
      echo $tab.$tab.$tab.'<BCWS>0.00</BCWS>' . $nl;
      echo $tab.$tab.$tab.'<BCWP>0.00</BCWP>' . $nl;
      echo $tab.$tab.$tab.'<PhysicalPercentComplete>'.(($line['elementary']==1)?$pct:$pct).'</PhysicalPercentComplete>' . $nl;
      echo $tab.$tab.$tab.'<EarnedValueMethod>0</EarnedValueMethod>' . $nl;
      /*<ExtendedAttribute>
        <FieldID>188743731</FieldID>
        <Value>lmk</Value>
        </ExtendedAttribute>*/
      //echo $tab.$tab.$tab.'<ActualWorkProtected>PT0H0M0S</ActualWorkProtected>' . $nl;
      //echo $tab.$tab.$tab.'<ActualOvertimeWorkProtected>PT0H0M0S</ActualOvertimeWorkProtected>' . $nl;
      $crit=array('successorId'=>$line['id']);
      $d=new Dependency();
      $depList=$d->getSqlElementsFromCriteria($crit,false);
      $nbHour = Parameter::getGlobalParameter('dayTime');
      foreach ($depList as $dep) {
        if (! isset($allItems[$dep->predecessorId])) continue;
        if ($dep->idle and (!$showIdle or $showIdle=='false')) continue;
        echo $tab.$tab.$tab.'<PredecessorLink>' . $nl;
        echo $tab.$tab.$tab.$tab.'<PredecessorUID>' . htmlEncode($dep->predecessorId) . '</PredecessorUID>' . $nl;
        echo $tab.$tab.$tab.$tab.'<Type>1</Type>' . $nl;
        echo $tab.$tab.$tab.$tab.'<CrossProject>0</CrossProject>' . $nl;
        $delai = 0;
        if($dep->dependencyDelay){
          $delai = $nbHour*$dep->dependencyDelay*600;
        }
        echo $tab.$tab.$tab.$tab.'<LinkLag>'.$delai.'</LinkLag>' . $nl;
        echo $tab.$tab.$tab.$tab.'<LagFormat>7</LagFormat>' . $nl;
        echo $tab.$tab.$tab.'</PredecessorLink>' . $nl;
      }
      echo $tab.$tab.$tab.'<IsPublished>1</IsPublished>' . $nl;
      echo $tab.$tab.$tab.'<CommitmentType>0</CommitmentType>' . $nl;
      if ($line['reftype']!='Milestone') {
        echo $tab.$tab.$tab.'<TimephasedData>' . $nl;
        echo $tab.$tab.$tab.'<Type>11</Type>' . $nl;
        echo $tab.$tab.$tab.'<UID>'.$line['id'].'</UID>' . $nl;
        echo $tab.$tab.$tab.'<Start>' . $minWorkDate . 'T' . $startAM . '</Start>' . $nl;
        echo $tab.$tab.$tab.'<Finish>' . $maxWorkDate . 'T' . $endPM . '</Finish>' . $nl;
        echo $tab.$tab.$tab.'<Unit>3</Unit>' . $nl;
        echo $tab.$tab.$tab.'<Value>'.$pctDuration.'</Value>' . $nl;
        echo $tab.$tab.$tab.'</TimephasedData>' . $nl;
      }
      echo $tab.$tab.$tab.'<projeqtorPlanningModeId>'.$line["idplanningmode"].'</projeqtorPlanningModeId>'. $nl;
      echo $tab.$tab.$tab.'<projeqtorPlanningModeName>'.SqlList::getNameFromId('PlanningMode',$line['idplanningmode']).'</projeqtorPlanningModeName>'. $nl;
      echo $tab.$tab.'</Task>' . $nl;
    }
    echo $tab.'</Tasks>' . $nl;
    $arrayRessource=array();
    echo $tab.'<Resources>' . $nl;
    foreach ($resourceList as $resource) {
      if ($exportAssignments==false) continue;
      $arrayResource[$resource->id]=$resource;
      echo $tab.$tab."<Resource>" . $nl;
      echo $tab.$tab.$tab."<UID>" . htmlEncode($resource->id) . "</UID>" . $nl;
      echo $tab.$tab.$tab."<ID>" . htmlEncode($resource->id) . "</ID>" . $nl;
      echo $tab.$tab.$tab."<Name>" . htmlEncode($resource->name,'xml') . "</Name>" . $nl;
      echo $tab.$tab.$tab."<Type>1</Type>" . $nl;
      echo $tab.$tab.$tab."<IsNull>0</IsNull>" . $nl;
      echo $tab.$tab.$tab."<Initials>" . htmlEncode($resource->initials,'xml') . "</Initials>" . $nl;
      echo $tab.$tab.$tab."<Group>" . htmlEncode(SqlList::getNameFromId('Team',$resource->idTeam),'xml') . "</Group>" . $nl;
      echo $tab.$tab.$tab."<WorkGroup>0</WorkGroup>" . $nl;
      echo $tab.$tab.$tab."<EmailAddress>" . htmlEncode($resource->email,'xml') . "</EmailAddress>" . $nl;
      echo $tab.$tab.$tab."<MaxUnits>" . htmlEncode($resource->capacity) . "</MaxUnits>" . $nl;
      echo $tab.$tab.$tab."<PeakUnits>0</PeakUnits>" . $nl;
      echo $tab.$tab.$tab."<OverAllocated>0</OverAllocated>" . $nl;
      echo $tab.$tab.$tab."<CanLevel>1</CanLevel>" . $nl;
      echo $tab.$tab.$tab."<AccrueAt>3</AccrueAt>" . $nl;
      echo $tab.$tab.$tab."<Work>PT0H0M0S</Work>" . $nl;
      echo $tab.$tab.$tab."<RegularWork>PT0H0M0S</RegularWork>" . $nl;
      echo $tab.$tab.$tab."<OvertimeWork>PT0H0M0S</OvertimeWork>" . $nl;
      echo $tab.$tab.$tab."<ActualWork>PT0H0M0S</ActualWork>" . $nl;
      echo $tab.$tab.$tab."<RemainingWork>PT0H0M0S</RemainingWork>" . $nl;
      echo $tab.$tab.$tab."<ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>" . $nl;
      echo $tab.$tab.$tab."<RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>" . $nl;
      echo $tab.$tab.$tab."<PercentWorkComplete>0</PercentWorkComplete>" . $nl;
      $rate=0;
      $critCost=array('idResource'=>$resource->id, 'endDate'=>null);
      $rc=new ResourceCost();
      $rcList=$rc->getSqlElementsFromCriteria($critCost, false, null, ' startDate desc');
      if (count($rcList)>0) {
      	$rate=($hoursPerDay)?round($rcList[0]->cost / $hoursPerDay,2):0;

      }
      echo $tab.$tab.$tab."<StandardRate>" . $rate . "</StandardRate>" . $nl;
      echo $tab.$tab.$tab."<StandardRateFormat>3</StandardRateFormat>" . $nl;
      echo $tab.$tab.$tab."<Cost>0</Cost>" . $nl;
      echo $tab.$tab.$tab."<OvertimeRate>0</OvertimeRate>" . $nl;
      echo $tab.$tab.$tab."<OvertimeRateFormat>3</OvertimeRateFormat>" . $nl;
      echo $tab.$tab.$tab."<OvertimeCost>0</OvertimeCost>" . $nl;
      echo $tab.$tab.$tab."<CostPerUse>0</CostPerUse>" . $nl;
      echo $tab.$tab.$tab."<ActualCost>0</ActualCost>" . $nl;
      echo $tab.$tab.$tab."<ActualOvertimeCost>0</ActualOvertimeCost>" . $nl;
      echo $tab.$tab.$tab."<RemainingCost>0</RemainingCost>" . $nl;
      echo $tab.$tab.$tab."<RemainingOvertimeCost>0</RemainingOvertimeCost>" . $nl;
      echo $tab.$tab.$tab."<WorkVariance>0</WorkVariance>" . $nl;
      echo $tab.$tab.$tab."<CostVariance>0</CostVariance>" . $nl;
      echo $tab.$tab.$tab."<SV>0</SV>" . $nl;
      echo $tab.$tab.$tab."<CV>0</CV>" . $nl;
      echo $tab.$tab.$tab."<ACWP>0</ACWP>" . $nl;
      echo $tab.$tab.$tab."<CalendarUID>" . htmlEncode($resource->id) . "</CalendarUID>" . $nl;
      echo $tab.$tab.$tab."<BCWS>0</BCWS>" . $nl;
      echo $tab.$tab.$tab."<BCWP>0</BCWP>" . $nl;
      echo $tab.$tab.$tab."<IsGeneric>0</IsGeneric>" . $nl;
      echo $tab.$tab.$tab."<IsInactive>0</IsInactive>" . $nl;
      echo $tab.$tab.$tab."<IsEnterprise>0</IsEnterprise>" . $nl;
      echo $tab.$tab.$tab."<BookingType>0</BookingType>" . $nl;
      //echo "<ActualWorkProtected>PT0H0M0S</ActualWorkProtected>" . $nl;
      //echo "<ActualOvertimeWorkProtected>PT0H0M0S</ActualOvertimeWorkProtected>" . $nl;
      //echo "<CreationDate></CreationDate>" . $nl;
      echo $tab.$tab."</Resource>" . $nl;
    }
    echo $tab."</Resources>" . $nl;
    $ass=new Assignment();
    $clauseWhere="(refType,refId) in ($selectItems)";
    $lstAss=$ass->getSqlElementsFromCriteria(null, false, $clauseWhere, 'refType, refId, idResource', true);
    $currentKey=null;
    $precId=null;
    // Merge assignments for same resource on same activity
    foreach ($lstAss as $idAss=>$ass) {
      $key="$ass->refType#$ass->refId#$ass->idResource";
      if ($precId and $currentKey==$key) {
        $precAss=$lstAss[$precId];
        $precAss->assignedWork+=$ass->assignedWork;
        $precAss->realWork+=$ass->realWork;
        $precAss->leftWork+=$ass->leftWork;
        $precAss->plannedWork+=$ass->plannedWork;
        if ($ass->realStartDate and $ass->realStartDate<$precAss->realStartDate) $precAss->realStartDate=$ass->realStartDate;
        if ($ass->plannedStartDate and $ass->plannedStartDate<$precAss->plannedStartDate) $precAss->plannedStartDate=$ass->plannedStartDate;
        if ($ass->realEndDate and $ass->realEndDate>$precAss->realEndDate) $precAss->realEndDate=$ass->realEndDate;
        if ($ass->plannedEndDate and $ass->plannedEndDate>$precAss->plannedEndDate) $precAss->plannedEndDate=$ass->plannedEndDate;
        unset($lstAss[$idAss]);
        $lstAss[$precId]=$precAss;
      } else {
        $precId=$idAss;
        $currentKey=$key;
      }
    }
    echo $tab.'<Assignments>' . $nl;
    foreach ($lstAss as $ass) {
      if ($exportAssignments==false) continue;
      //if ($ass->plannedWork==0) continue;
    	if (pq_array_key_exists($ass->refType . '#' . $ass->refId, $arrayTask)) {
    	  $task=$arrayTask[$ass->refType . '#' . $ass->refId];
    	  if (isset($arrayResource[$ass->idResource])) {
          $res=$arrayResource[$ass->idResource];
    	  } else {
    	    $res=new Resource($ass->idResource,true);
    	    $arrayResource[$ass->idResource]=$res;
    	  }
    	  // From Assignment
    	  $pctAss=(floatval($ass->plannedWork))?round($ass->realWork/$ass->plannedWork*100,2):(($ass->leftWork==0)?100:0);
    	  $assStart=($ass->realStartDate)?$ass->realStartDate:$ass->plannedStartDate;
    	  $assEnd=($ass->leftWork==0)?$ass->realEndDate:$ass->plannedEndDate;
    	  $assPlan=$ass->plannedWork;
    	  $assReal=$ass->realWork;
    	  $assLeft=$ass->leftWork;
    	  // From Activity
    	  $pctAss=$task['pct'];
    	  //$assStart=$task['start'];
    	  //$assEnd=$task['end'];
    	  //$assPlan=$ass->plannedWork;
    	  //$assReal=$assPlan*$pctAss/100;
    	  //$assLeft=$assPlan-$assReal;
	      echo $tab.$tab."<Assignment>" . $nl;
	      echo $tab.$tab.$tab."<UID>" . htmlEncode($ass->id) . "</UID>" . $nl;
	      echo $tab.$tab.$tab."<TaskUID>" . $arrayTask[$ass->refType . '#' . $ass->refId]['id'] . "</TaskUID>" . $nl;
	      echo $tab.$tab.$tab."<ResourceUID>" . htmlEncode($ass->idResource) . "</ResourceUID>" . $nl;	      
	      echo $tab.$tab.$tab."<PercentWorkComplete>".(($pctAss==100 or $pctAss==0)?'':$pctAss)."</PercentWorkComplete>" . $nl;
	      echo $tab.$tab.$tab."<ActualCost>0</ActualCost>" . $nl;
	      echo $tab.$tab.$tab."<ActualOvertimeCost>0</ActualOvertimeCost>" . $nl;
	      echo $tab.$tab.$tab."<ActualOvertimeWork>PT0H0M0S</ActualOvertimeWork>" . $nl;
	      echo $tab.$tab.$tab."<ActualStart>" . (($assStart)?$assStart . "T" . $startAM:'') . "</ActualStart>" . $nl;
	      echo $tab.$tab.$tab."<ActualWork>PT" . formatWork($assReal,$hoursPerDay) ."</ActualWork>" . $nl;
	      echo $tab.$tab.$tab."<ACWP>0</ACWP>" . $nl;
	      echo $tab.$tab.$tab."<Confirmed>0</Confirmed>" . $nl;
	      echo $tab.$tab.$tab."<Cost>0</Cost>" . $nl;
	      echo $tab.$tab.$tab."<CostRateTable>0</CostRateTable>" . $nl;
	      echo $tab.$tab.$tab."<RateScale>0</RateScale>" . $nl;
	      echo $tab.$tab.$tab."<CostVariance>0</CostVariance>" . $nl;
	      echo $tab.$tab.$tab."<CV>0</CV>" . $nl;
	      echo $tab.$tab.$tab."<Delay>0</Delay>" . $nl;
	      echo $tab.$tab.$tab."<Finish>" . htmlEncode($assEnd) . "T" . $endPM . "</Finish>" . $nl;
	      echo $tab.$tab.$tab."<FinishVariance>0</FinishVariance>" . $nl;
	      //echo $tab.$tab.$tab."<WorkVariance>".(round($ass->plannedWork*$hoursPerDay,0)*60*1000).".00</WorkVariance>" . $nl;
	      echo $tab.$tab.$tab."<WorkVariance>0.00</WorkVariance>" . $nl;
	      echo $tab.$tab.$tab."<HasFixedRateUnits>1</HasFixedRateUnits>" . $nl;
	      echo $tab.$tab.$tab."<FixedMaterial>0</FixedMaterial>" . $nl;
	      echo $tab.$tab.$tab."<LevelingDelay>0</LevelingDelay>" . $nl;
	      echo $tab.$tab.$tab."<LevelingDelayFormat>39</LevelingDelayFormat>" . $nl;
	      echo $tab.$tab.$tab."<LinkedFields>0</LinkedFields>" . $nl;
	      echo $tab.$tab.$tab."<Milestone>".(($ass->refType=='Milestone')?'1':'0')."</Milestone>" . $nl;
	      echo $tab.$tab.$tab."<Overallocated>0</Overallocated>" . $nl;
	      echo $tab.$tab.$tab."<OvertimeCost>0</OvertimeCost>" . $nl;
	      echo $tab.$tab.$tab."<OvertimeWork>PT0H0M0S</OvertimeWork>" . $nl;
	      echo $tab.$tab.$tab."<RegularWork>PT" . formatWork($assPlan,$hoursPerDay) . "</RegularWork>" . $nl;
	      echo $tab.$tab.$tab."<RemainingCost>0</RemainingCost>" . $nl;
	      echo $tab.$tab.$tab."<RemainingOvertimeCost>0</RemainingOvertimeCost>" . $nl;
	      echo $tab.$tab.$tab."<RemainingOvertimeWork>PT0H0M0S</RemainingOvertimeWork>" . $nl;
	      echo $tab.$tab.$tab."<RemainingWork>PT" . formatWork($assLeft,$hoursPerDay) ."</RemainingWork>" . $nl;
	      echo $tab.$tab.$tab."<ResponsePending>0</ResponsePending>" . $nl;
	      echo $tab.$tab.$tab.'<Start>'. (($assStart)?$assStart . "T" . $startAM:'') . '</Start>'. $nl;
	      if ($pctAss==100) echo $tab.$tab.$tab."<Stop>" . htmlEncode($assEnd) . "T" . $endPM . "</Stop>" . $nl;
	      //else echo $tab.$tab.$tab.'<Stop></Stop>' . $nl;
	      if ($pctAss==100) echo $tab.$tab.$tab."<Resume>" . htmlEncode($assEnd) . "T" . $endPM . "</Resume>" . $nl;
	      //else echo $tab.$tab.$tab.'<Resume></Resume>' . $nl;
// 	      if ($pctAss) {
// 	        $length=dayDiffDates($assStart, $assEnd)+1;
// 	        $lengthPct=$length*$pctAss/100;
// 	        $lengthDays=floor($lengthPct);
// 	        $lengthHours=$lengthPct-$lengthDays;
// 	        $lengthHH=floor($lengthHours*$hoursPerDay);
// 	        $lengthMM=floor((($lengthHours*$hoursPerDay)-$lengthHH)*60);
// 	        $stopDate=addDaysToDate($assStart, $lengthDays);
// 	        $stop=($pctAss)?$stopDate."T".htmlFixLengthNumeric(pq_substr($startAM,0,2)+$lengthHH,2).":".htmlFixLengthNumeric($lengthMM,2).":00":'';
// 	        $resume=($pctAss<100)?$stop:'';
// 	        echo $tab.$tab.$tab."<Stop>" . $stop . "</Stop>" . $nl;
// 	        echo $tab.$tab.$tab."<Resume>" . $resume . "</Resume>" . $nl;
// 	      } else {
// 	        echo $tab.$tab.$tab.'<Stop></Stop>' . $nl;
// 	        echo $tab.$tab.$tab.'<Resume></Resume>' . $nl;
// 	      }
	      
	      
// 	      if ($pctAss) {
// 	        echo $tab.$tab.$tab."<Stop>" . htmlEncode($task['stop']) . "</Stop>" . $nl;
// 	        echo $tab.$tab.$tab."<Resume>" . htmlEncode($task['stop']) . "</Resume>" . $nl;
// 	      } else {
// 	        echo $tab.$tab.$tab.'<Stop>'. (($assStart)?$assStart . "T" . $startAM:'') .'</Stop>' . $nl;
// 	        echo $tab.$tab.$tab.'<Resume>'. (($assStart)?$assStart . "T" . $startAM:'') .'</Resume>' . $nl;
// 	      }
	      echo $tab.$tab.$tab."<StartVariance>0</StartVariance>" . $nl;
	      echo $tab.$tab.$tab."<Units>" . round(($res->capacity * $ass->rate / 100),1) . "</Units>" . $nl;
	      echo $tab.$tab.$tab."<UpdateNeeded>0</UpdateNeeded>" . $nl;
	      echo $tab.$tab.$tab."<VAC>0.00</VAC>" . $nl;
	      echo $tab.$tab.$tab."<Work>PT" . formatWork($ass->plannedWork,$hoursPerDay) . "</Work>" . $nl;
	      echo $tab.$tab.$tab."<WorkContour>0</WorkContour>" . $nl;
	      echo $tab.$tab.$tab."<BCWS>0</BCWS>" . $nl;
	      echo $tab.$tab.$tab."<BCWP>0</BCWP>" . $nl;
	      echo $tab.$tab.$tab."<BookingType>0</BookingType>" . $nl;
	      //echo "<ActualWorkProtected>PT0H0M0S</ActualWorkProtected>" . $nl;
	      //echo "<ActualOvertimeWorkProtected>PT0H0M0S</ActualOvertimeWorkProtected>" . $nl;
	      //echo "<CreationDate>2011-11-18T21:06:00</CreationDate>" . $nl;
	      //echo "<TimephasedData>" . $nl;
	      //echo "<Type>1</Type>" . $nl;
	      //echo "<UID>1</UID>" . $nl;
	      //echo "<Start>" . htmlEncode($ass->plannedStartDate) . "T08:00:00</Start>" . $nl;
	      //echo "<Finish>" . htmlEncode($ass->plannedEndDate) . "T08:00:00</Finish>" . $nl;
	      //echo "<Unit>2</Unit>" . $nl;
	      //echo "<Value>PT8H0M0S</Value>" . $nl;
	      //echo "</TimephasedData>" . $nl;
        $work = new Work();
        $lstWork = $work->getSqlElementsFromCriteria(array('idAssignment'=>$ass->id,'idResource'=>$ass->idResource));
        foreach ($lstWork as $wk){
  	      echo $tab.$tab.$tab."<TimephasedData>" . $nl;
  	      echo $tab.$tab.$tab.$tab."<Type>2</Type>" . $nl;
  	      echo $tab.$tab.$tab.$tab."<UID>" . htmlEncode($wk->id) . "</UID>" . $nl;
  	      echo $tab.$tab.$tab.$tab."<Start>" . htmlEncode($wk->workDate) . "T".$startAM."</Start>" . $nl;
  	      echo $tab.$tab.$tab.$tab."<Finish>" . htmlEncode($wk->workDate) . "T".$endPM."</Finish>" . $nl;
  	      echo $tab.$tab.$tab.$tab."<Unit>1</Unit>" . $nl;
  	      echo $tab.$tab.$tab.$tab."<Value>PT" . formatWork($wk->work,$hoursPerDay) ."</Value>" . $nl;
  	      echo $tab.$tab.$tab."</TimephasedData>" . $nl;
        }
        echo $tab.$tab."</Assignment>" . $nl;
    	}
    }
    echo $tab."</Assignments>" . $nl;
    echo '</Project>' . $nl;
  }

  function formatDuration($duration, $hoursPerDay) {
    $hourDuration=$duration*$hoursPerDay;
  	$res = 'PT' . round($hourDuration,0) . 'H0M0S';
  	return $res;
  }
  function formatWork($work, $hoursPerDay) {
    //if ($work<0.01) return '0H0M0S';
    $hWork=$work*$hoursPerDay;
    $h=floor($hWork);
    $m=floor(($hWork-$h)*60);
    return $h.'H'.$m.'M0S';
  }
  
  function getCurrencyCode($currency) {
    if ($currency=='€') return 'EUR';
    else if ($currency=='$') return 'USD';
    else if ($currency=='£') return 'GBP';
  }
  function getDurationFormat() {
    return 7; // Dureation must always be in days
    if (Work::getWorkUnit()=='days') return 7;
    else if  (Work::getWorkUnit()=='hours') return 5;
    return 7; // By default return 7, but should not be reached
  }
  function getWorkFormat() {
    if (Work::getWorkUnit()=='days') return 3;
    else if  (Work::getWorkUnit()=='hours') return 2;
    return 3; // By default return 7, but should not be reached
  }
  
  function getPlanningHatchPattern($line) {
    if (!isset($line['reftype']) || $line['reftype'] != 'Activity') return '';
    
    if (isset($line['hatchpattern']) && trim((string)$line['hatchpattern']) !== '') {
      return $line['hatchpattern'];
    }
    
    if (!isset($line['refid']) || !$line['refid']) return '';
    
    $activity = new Activity($line['refid'], true);
    
    if (!empty($activity->idActivityType)) {
      $typeHatch = SqlList::getFieldFromId('ActivityType', $activity->idActivityType, 'hatchPattern');
      if (!empty($typeHatch)) return $typeHatch;
    }
    
    return '';
  }
?>
