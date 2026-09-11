<?PHP
use http\Client\Request;

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
scriptLog('   ->/tool/jsonWorkPlan.php');

if (!function_exists('workPlanRtaPeriodOverlaps')) {
  function workPlanRtaPeriodOverlaps($rtaStartDate, $rtaEndDate, $periodStartDate, $periodEndDate) {
    return ($rtaStartDate==null or $rtaStartDate <= $periodEndDate)
        and ($rtaEndDate==null or $rtaEndDate >= $periodStartDate);
  }
}

SqlElement::$_cachedQuery['Ticket']=array();
SqlElement::$_cachedQuery['Activity']=array();
SqlElement::$_cachedQuery['Resource']=array();
SqlElement::$_cachedQuery['PlanningElement']=array();
$objectClass='PlanningElement';
$obj=new $objectClass();
$table=$obj->getDatabaseTableName();
$seeAllResource=false;
$right=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$user->idProfile, 'scope'=>'resourcePlanning'));
if ($right) {
  $list=new ListYesNo($right->rightAccess);
  if ($list->code=='YES') {
    $seeAllResource=true;
  }
}
if (!$seeAllResource) {
  $prfLst=$user->getAllProfiles();
  foreach ($prfLst as $prf) {
    $right=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$prf, 'scope'=>'resourcePlanning'));
    if ($right) {
      $list=new ListYesNo($right->rightAccess);
      if ($list->code=='YES') {
        $seeAllResource=true;
        break;
      }
    }
  }
}
$plannableProjectsList=getSessionUser()->getListOfPlannableProjects();

$isShowDetail = RequestHandler::getBoolean('isShowDetail');

$refType = RequestHandler::getClass('objectClass');
$refId = RequestHandler::getId('objectId');
$isFromPlanning = false;
if($refType and $refId)$isFromPlanning = true;

$print=false;
$saveDates=false;
if (pq_array_key_exists('startDatePlanView',$_REQUEST) and pq_array_key_exists('endDatePlanView',$_REQUEST)) {
  $startDate= RequestHandler::getDatetime('startDatePlanView');
  $endDate= RequestHandler::getDatetime('endDatePlanView');
}

if(!isset($startDate))$startDate='';
if(!isset($endDate))$endDate='';

$projectDate=Parameter::getUserParameter('workPlanProjectDate');
if($projectDate == 'on'){
  $startDate="";
  $endDate="";
}

// Get planning min and max date removed due to display lag
// if(pq_array_key_exists('planningStartDateView',$_REQUEST))$startDate=RequestHandler::getDatetime('planningStartDateView');
// if(pq_array_key_exists('planningEndDateView',$_REQUEST))$endDate= RequestHandler::getDatetime('planningEndDateView');
$scale = Parameter::getUserParameter('planningScale');
if($scale == ''){
  $scale = 'day';
}
$showDetailProject = RequestHandler::getBoolean('showDetailProject');
if($showDetailProject == '')$showDetailProject=false;
$detailProject = RequestHandler::getId('detailProject');
$showDetailElement = RequestHandler::getBoolean('showDetailElement');
if($showDetailElement == '')$showDetailElement=false;
$detailResource=RequestHandler::getId('detailResource');
$showDetailPool=RequestHandler::getBoolean('showDetailPool');
if($showDetailPool == '')$showDetailPool=false;
$selectResource=RequestHandler::getId('selectResourceName');
if(!$isFromPlanning and !$selectResource and sessionValueExists('selectResourceName')){
  $selectResource =pq_trim(getSessionValue('selectResourceName'));
}
$selectPoolName=RequestHandler::getId('selectPoolName');
if(!$isFromPlanning and !$selectPoolName and sessionValueExists('selectPoolName')){
  $selectPoolName =pq_trim(getSessionValue('selectPoolName'));
}
if($selectResource == '' and $selectPoolName)$selectResource=$selectPoolName;
if($detailResource)$selectResource=$detailResource;
$selectedPool=false;
$resource = new ResourceAll($selectResource);
if($resource->id and $resource->isResourceTeam){
  $selectedPool=true;
}
$selectTeam=RequestHandler::getId('teamName');
if(!$isFromPlanning and !$selectTeam and sessionValueExists('teamName')){
  $selectTeam =pq_trim(getSessionValue('teamName'));
}
$selectOrganization=RequestHandler::getId('organizationName');
if(!$isFromPlanning and !$selectOrganization and sessionValueExists('organizationName')){
  $selectOrganization =pq_trim(getSessionValue('organizationName'));
}
if($selectResource){
  $selectTeam=false;
  $selectOrganization=false;
}
if($selectTeam){
  $selectResource=false;
  $selectOrganization=false;
}
if($selectOrganization){
  $selectTeam=false;
  $selectResource=false;
}

$showProject = Parameter::getUserParameter('planningShowProject');
if($showProject=='false'){
  $showProject=false;
}
if($showProject=='true'){
  $showProject=true;
}
if(!$showProject and isset($saveShowProject)){
  $showProject=($saveShowProject==1)?true:false;
  $showDetailProject = false;
}

if (! isset($outMode)) { $outMode=""; }
$showIdleProjects=true;
$showIdle=true;

$showPoolForResource = boolval(Parameter::getUserParameter('workPlanShowPoolForResource'));
$showLateColorPriority = boolval(Parameter::getUserParameter('planningShowLateColorPriority'));
$showResourceWithoutWork = boolval(Parameter::getUserParameter('workPlanShowResourceWithoutWork'));
$hideAssignationWihtoutLeftWork = RequestHandler::getBoolean('hideAssignationWihtoutLeftWork');

// Cache frequently used project list clauses
$visibleProjectsListFull = getVisibleProjectsList(!$showIdleProjects);
$visibleProjectsListDetail = getVisibleProjectsList(!$showIdleProjects, $detailProject);
$adminProjectList = Project::getAdminitrativeProjectList();

$noParam = false;
if(getSessionValue('project') == '*' and !$selectResource and !$selectedPool and !$selectTeam and !$selectOrganization){
  $noParam = true;
}
$skipNoParamCheck = RequestHandler::getBoolean('skipNoParamCheck');
if($noParam and !$skipNoParamCheck){
  echo '<input type="hidden" id="confirmCheckNoParam" name="confirmCheckNoParam" value="" />';
}else{
  $querySelect = '';
  $queryFrom='';
  $queryWhere='';
  $queryGroupBy='';
  $queryOrderBy='';
  $idTab=0;
  
  $pe=new PlanningElement();
  $ass=new Assignment();
  $res=new Resource();
  $wk=new Work();
  $pw=new PlannedWork();
  $p = new Project();
  $cachedResourceAll = array();
  
  $table=array();
  $specific="imputation";
  $includePool=true;
  ob_start();
  include("../tool/drawResourceListForSpecificAccess.php");
  if (ob_get_length()){
    ob_clean();  // Important : clean possible extra char before returning data;
  }
  $allowedResource=$table;
  if ($selectTeam) {
    $team=new Team($selectTeam,true);
    $teamMembers=$team->getMembers(true);
  } else {
    $teamMembers=null;
  }
  if ($selectOrganization) {
    $orga=new Organization($selectOrganization,true);
    $orgaMembers=array_flip($orga->getResourcesOfAllSubOrganizationsListAsArray());
  } else {
    $orgaMembers=null;
  }
  foreach ($allowedResource as $resId=>$resName) {
    if ($selectResource and $selectResource!=$resId) {
      unset($allowedResource[$resId]);
    }
    if ($selectTeam and is_array($teamMembers)) {
      if (!isset($teamMembers[$resId])) {
        unset($allowedResource[$resId]);
      }
    }
    if ($selectOrganization and is_array($orgaMembers)) {
      if (!isset($orgaMembers[$resId])) {
        unset($allowedResource[$resId]);
      }
    }
  }
  
  $rta=new ResourceTeamAffectation();
  $today=date('Y-m-d');
  $assignedRessource = false;
  
  if($refType and $refId and !$selectResource){
    $assignedRessource = true;
    $allowedResource = array();
    $ass = new Assignment();
    if($refType != 'Project'){
      $where=($hideAssignationWihtoutLeftWork)?"refType='$refType' and refId=$refId and leftWork!=0":"refType='$refType' and refId=$refId";
    }else{
      $where=($hideAssignationWihtoutLeftWork)?"idProject in ".getVisibleProjectsList(!$showIdleProjects, $refId)." and leftWork!=0":"idProject in ".getVisibleProjectsList(!$showIdleProjects, $refId);
    }
    $lstAss = $ass->getSqlElementsFromCriteria(null,null,$where);
    foreach ($lstAss as $ass) {
      $allowedResource[$ass->idResource]=SqlList::getNameFromId('ResourceAll', $ass->idResource, false);
    }
  }
  
  if (! $selectResource and ! $selectedPool and ! $selectTeam and ! $selectOrganization ) {
    $crit = "idProject IN ".$visibleProjectsListFull." AND idResource IN ".transformListIntoInClause($allowedResource);
    $affList = SqlList::getListWithCrit('Affectation', $crit, 'idResource');
    // Merge Resources that are assigned even if not allocated
    $assList = SqlList::getListWithCrit('Assignment', $crit, 'idResource');
    $affList=array_unique(array_merge($affList, $assList));
    // Remove not allocated and not assigned resources
    foreach ($allowedResource as $idResource=>$name){
      if(! in_array($idResource, $affList)){
        unset($allowedResource[$idResource]); // PBER - changed this clause as it showed no resource
      }
    }
  }
  
  $skipLimitCalculWeight = RequestHandler::getBoolean('skipLimitCalculWeight');
  $showDetailSkipLimitCalculWeight = getSessionValue('showDetailSkipLimitCalculWeight');
  if($isShowDetail){
    $skipLimitCalculWeight = true;
  }
  if(!$skipLimitCalculWeight)unsetSessionValue('showDetailSkipLimitCalculWeight');
  if($showDetailSkipLimitCalculWeight)$skipLimitCalculWeight = true;
  
  $resourceList = array();
  if($selectedPool){
    $resTeam = new ResourceTeam();
    $resourceList = $resTeam->getResourcesList($selectResource, true);
  }
  if(count($resourceList) <= 0){
    $resourceList = $allowedResource;
  }
  
  $checkWeight = 0;
  $checkWeightQuery = "SELECT
    /* plus petite date de début */
    MIN(COALESCE(
      CASE WHEN ass.plannedStartDate IS NOT NULL AND ass.realStartDate IS NOT NULL AND (ass.plannedStartDate < ass.realStartDate AND ass.leftWork > 0) THEN ass.plannedStartDate END,
      CASE WHEN ass.realStartDate     IS NOT NULL THEN ass.realStartDate     END,
      CASE WHEN ass.plannedStartDate  IS NOT NULL THEN ass.plannedStartDate  END,
      CASE WHEN pe.validatedstartdate IS NOT NULL THEN pe.validatedstartdate END
    )) AS startdate,
      
    /* plus grande date de fin */
    MAX(COALESCE(
      CASE WHEN pe.validatedenddate IS NOT NULL AND ass.plannedEndDate IS NULL AND pe.plannedenddate  IS NOT NULL THEN pe.plannedenddate END,
      CASE WHEN ass.plannedEndDate  IS NOT NULL THEN ass.plannedEndDate  END,
      CASE WHEN pe.validatedenddate IS NOT NULL THEN pe.validatedenddate END
    )) AS enddate
      
  FROM ".$res->getDatabaseTableName() ." usr
  LEFT JOIN ". $ass->getDatabaseTableName() . " ass ON usr.id = ass.idResource
  LEFT JOIN ". $pe->getDatabaseTableName() . " pe ON pe.refType = ass.refType AND pe.refId = ass.refId AND pe.idProject IN ".$visibleProjectsListDetail."
  WHERE usr.id IN ".transformListIntoInClause($resourceList)." AND pe.idProject IS NOT NULL";
  
  $resultCheckWeight=Sql::query($checkWeightQuery);
  if (isset($debugJsonQuery) and $debugJsonQuery) { // Trace in configured to
    debugTraceLog("jsonWorkPlan: ".$checkWeightQuery); // Trace query
    debugTraceLog("  => error (if any) = ".Sql::$lastQueryErrorCode.' - '.Sql::$lastQueryErrorMessage);
    debugTraceLog("  => number of lines returned = ".Sql::$lastQueryNbRows);
  }
  if (Sql::$lastQueryNbRows > 0) {
    $minStartDate = date('Y-m-d');
    $maxEndDate = date('Y-m-d');
    while ($line = Sql::fetchLine($resultCheckWeight)) {
      $checkStartDate = $line['startdate'];
      $checkEndDate = $line['enddate'];
      if($checkStartDate){
        $minWeek = explode('-', weekFormat($checkStartDate));
        $minStartDate = date('Y-m-d', firstDayofWeek($minWeek[1], $minWeek[0]));
      }
      if($checkEndDate){
        $maxWeek = explode('-', weekFormat($checkEndDate));
        $maxEndDate = lastDayofWeek($maxWeek[1], $maxWeek[0]);
      }
    }
    if($startDate){
      $minWeek = explode('-', weekFormat($startDate));
      $minStartDate = date('Y-m-d', firstDayofWeek($minWeek[1], $minWeek[0]));
    }
    if($endDate){
      $maxWeek = explode('-', weekFormat($endDate));
      $maxEndDate = lastDayofWeek($maxWeek[1], $maxWeek[0]);
    }
    if ($maxEndDate < $minStartDate)$maxEndDate = $minStartDate;
    $countDays = dayDiffDates($minStartDate, $maxEndDate);
    $countRes = count($allowedResource);
    $checkWeight = $countDays * $countRes;
  }
  
  // ADD RESOURCES OF SELECTED POOL
  if(!$assignedRessource and $selectedPool){
    foreach ($allowedResource as $resId=>$resName) {
      $rtaList=$rta->getSqlElementsFromCriteria(array('idResourceTeam'=>$resId));
      foreach ($rtaList as $rta) {
        if($rta->idle and !$rta->endDate){
          $rta->endDate = date('Y-m-d', pq_strtotime("yesterday"));
        }
        if (workPlanRtaPeriodOverlaps($rta->startDate, $rta->endDate, $minStartDate, $maxEndDate)) {
          if (!isset($allowedResource[$rta->idResource])) $allowedResource[$rta->idResource]=SqlList::getNameFromId('ResourceAll', $rta->idResource);
        }
      }
    }
  }
  
  if(!$assignedRessource and $selectResource == '' or (!$selectedPool and $selectResource and $showPoolForResource)){
    // ADD POOLS OF SELECTED RESOURCES
    foreach ($allowedResource as $resId=>$resName) {
      $rtaList=$rta->getSqlElementsFromCriteria(array('idResource'=>$resId));
      foreach ($rtaList as $rta) {
        if($rta->idle and !$rta->endDate){
          $rta->endDate = date('Y-m-d', pq_strtotime("yesterday"));
        }
        if (workPlanRtaPeriodOverlaps($rta->startDate, $rta->endDate, $minStartDate, $maxEndDate)) {
              if (!isset($allowedResource[$rta->idResourceTeam]) and !$selectOrganization and !$selectTeam){
                $allowedResource[$rta->idResourceTeam]=SqlList::getNameFromId('ResourceAll', $rta->idResourceTeam);
              }
            }
      }
    }
  }
  
  $resourceOfPool = array();
  foreach ($allowedResource as $resId=>$resName) {
    // Lookup or load ResourceAll from cache
    if (!isset($cachedResourceAll[$resId])) {
      $cachedResourceAll[$resId] = new ResourceAll($resId, true);
    }
    $res = $cachedResourceAll[$resId];
    if($res->isResourceTeam){
      $crit = "idProject IN ".$visibleProjectsListFull." AND idResource = $resId";
      $affList = SqlList::getListWithCrit('Affectation', $crit, 'idResource');
      if(!$affList){
        continue;
      }
      $rtaList=$rta->getSqlElementsFromCriteria(array('idResourceTeam'=>$resId));
      foreach ($rtaList as $rta) {
        //         if ($rta->idle) continue;
        if($rta->idle and !$rta->endDate){
          $rta->endDate = date('Y-m-d', pq_strtotime("yesterday"));
        }
        if (workPlanRtaPeriodOverlaps($rta->startDate, $rta->endDate, $minStartDate, $maxEndDate)) {
              if (!isset($resourceOfPool[$rta->idResource])) $resourceOfPool[$rta->idResource]=$rta->idResource;
            }
      }
    }else{
      continue;
    }
  }
  
  // No limit applied when ratio is not set or set to zero
  $limitCalculWeight = intval(Parameter::getGlobalParameter('limitCalculRatioWorkPlan'));
  if ($limitCalculWeight <= 0) $skipLimitCalculWeight = true;
  if(!$skipLimitCalculWeight and $checkWeight > $limitCalculWeight and !$isShowDetail){
    echo '<input type="hidden" id="confirmCheckCalculTime" name="confirmCheckCalculTime" value="" />';
  }else{
    $querySelect .= "pe.idProject as idProj, pe.id idPe, pe.wbs wbs, pe.wbsSortable wbsSortable,";
    $querySelect .= "pe.idplanningmode idplanningmode, pe.validatedstartdate, pe.validatedenddate, pe.validatedduration, pe.notplannedwork  , ";
    $querySelect .= "pe.plannedenddate as peplannedend, pe.plannedstartdate as peplannedstart, usr.fullName as name, usr.isResourceTeam as isResourceTeam, usr.isMaterial as isMaterial, pe.refName refName, ";
    $querySelect .= "pe.topRefType as topreftype, pe.toprefid as toprefid, pe.topid as topid, pe.paused as paused, ";
    $querySelect .= "ass.id as idAssignment, ass.refType, ass.refId, ass.idResource, ass.plannedStartDate, ass.plannedEndDate, ass.realStartDate, ass.realEndDate, ass.plannedWork, ass.realWork, ass.leftWork,";
    $querySelect .= "p.isUnderConstruction as projectisunderconstruction, p.fixPlanning as projectfixplanning, ";
    $querySelect .= "COALESCE(MAX(w.idResource), MAX(pw.idResource)) as linkedResource";
    
    $queryFrom .= $res->getDatabaseTableName() . " usr ";
    $queryFrom .= "LEFT JOIN ". $ass->getDatabaseTableName() . " ass ON usr.id = ass.idResource ";
    $queryFrom .= "LEFT JOIN ". $pe->getDatabaseTableName() . " pe ON pe.refType = ass.refType AND pe.RefId = ass.refId ";
    $queryFrom .= ($isFromPlanning)?" ":" AND pe.idProject IN ".$visibleProjectsListDetail." ";
    $queryFrom .= "LEFT JOIN ". $pw->getDatabaseTableName() . " pw ON ass.refType = pw.refType AND ass.refId = pw.refId AND ass.idProject = pw.idProject AND ass.id = pw.idAssignment ";
    $queryFrom .= "LEFT JOIN ". $wk->getDatabaseTableName() . " w ON ass.refType = w.refType AND ass.refId = w.refId AND ass.idProject = w.idProject AND ass.id = w.idAssignment ";
    $queryFrom .= "LEFT JOIN ".$p->getDatabaseTableName()." p ON ass.idProject = p.id ";
    
    $queryGroupBy .= "pe.idProject, pe.id, pe.wbs, pe.wbsSortable, pe.idplanningmode, pe.validatedstartdate, pe.validatedenddate, ";
    $queryGroupBy .= "pe.validatedduration, pe.notplannedwork, pe.plannedenddate, pe.plannedstartdate, usr.fullName, ";
    $queryGroupBy .= "usr.isResourceTeam, usr.isMaterial, pe.refName, pe.topRefType, pe.toprefid, pe.topid, pe.paused, ass.id, ass.refType, ";
    $queryGroupBy .= "ass.refId, ass.idResource, ass.plannedStartDate, ass.plannedEndDate, ass.realStartDate, ass.realEndDate, ass.plannedWork, ass.realWork, ass.leftWork, ";
    $queryGroupBy .= "p.isUnderConstruction, p.fixPlanning";
    $queryOrderBy .= " isResourceTeam DESC, name, wbsSortable";
    
    $querySelectUnion = "NULL AS idProj, NULL AS idPe, NULL AS wbs, NULL AS wbsSortable, NULL AS idplanningmode, NULL AS validatedstartdate, NULL AS validatedenddate, NULL AS validatedduration, NULL AS notplannedwork, ";
    $querySelectUnion .= "NULL AS peplannedend, NULL AS peplannedstart, usr.fullName AS name, usr.isResourceTeam AS isResourceTeam, usr.isMaterial as isMaterial, NULL AS refName, NULL AS topreftype, NULL AS toprefid, NULL AS topid, NULL AS paused, ";
    $querySelectUnion .= "NULL AS idAssignment, NULL AS refType, NULL AS refId, usr.id AS idResource, NULL AS plannedStartDate, NULL AS plannedEndDate, NULL AS realStartDate, NULL AS realEndDate, NULL AS plannedWork, NULL AS realWork, NULL AS leftWork, ";
    $querySelectUnion .= "NULL as projectisunderconstruction, NULL as projectfixplanning, NULL AS linkedResource";
    $queryFromUnion = $res->getDatabaseTableName() . " usr ";
    
    $queryWhere="usr.id in ".transformListIntoInClause($allowedResource)." AND pe.idProject IS NOT NULL";
    $queryWhereUnion = "usr.id in ".transformListIntoInClause($allowedResource);
    $queryWhereUnion .= " AND NOT EXISTS ( SELECT 1 FROM ". $ass->getDatabaseTableName() . " ass JOIN ".$pe->getDatabaseTableName()." pe ON pe.refType = ass.refType AND pe.RefId = ass.refId";
    $queryWhereUnion .= ($isFromPlanning)?" ":" AND pe.idProject IN ".$visibleProjectsListDetail." ";
    $queryWhereUnion .= " WHERE ass.idResource = usr.id )";
    
    // constitute query and execute
    $queryWhere=($queryWhere=='')?' 1=1':$queryWhere;
    $arrayFilter=array();
    $cpt=0;
    $applyFilter=false;
    $arrayRestrictWbs=array();
    $query=' ( SELECT ' . $querySelect
    . ' FROM ' . $queryFrom
    . ' WHERE ' . $queryWhere
    . ' GROUP BY '.$queryGroupBy.' ) ';
    // if($selectResource or $selectedPool or $selectTeam or $selectOrganization){
    $query.= ' UNION '
        .' ( SELECT ' . $querySelectUnion
        . ' FROM ' . $queryFromUnion
        . ' WHERE ' . $queryWhereUnion.' ) ';
        // }
        $query.= ' ORDER BY ' . $queryOrderBy;
        $result=Sql::query($query);
        if (isset($debugJsonQuery) and $debugJsonQuery) { // Trace in configured to
          debugTraceLog("jsonWorkPlan: ".$query); // Trace query
          debugTraceLog("  => error (if any) = ".Sql::$lastQueryErrorCode.' - '.Sql::$lastQueryErrorMessage);
          debugTraceLog("  => number of lines returned = ".Sql::$lastQueryNbRows);
        }
        $arrayProject=array();
        $nbRows=0;
        // return result in json format
        $d=new Dependency();
        if (Sql::$lastQueryNbRows == 0) {
          echo i18n('noDataToDisplay');
        } else {
          $collapsedParent=(!RequestHandler::getBoolean('isOpen'))?'1':'0';
          $list=array();
          $workDate=array();
          $weeks=array();
          $ressAll=array();
          $resourceList=array();
          $projectColorList=array();
          $cachedRefObjects=array();
          $cachedProjectTypes=array();
          $idResource="";
          $idProject="";
          $sumReal=0;
          $sumPlanned=0;
          $sumProjReal=0;
          $sumProjPlanned=0;
          $keyProj="";
          $idProj='';
          $keyRes="";
          $keyAll="";
          $idRes='';
          $keyElm="";
          $cptLine=0;
          $canBeAll=false;
          $topidAll='';
          $resAllAr=array();
          $groupConcat='';
          $parentId=RequestHandler::getValue('parentId');
          if(!Sql::isPgsql()){
            $groupConcat = "concat('Resource', '#', idResource)";
            $groupConcat .= ",concat('_Project', '#', idProject)";
            if($showDetailElement){
              $groupConcat .= ",concat('_', refType, '#', refId)";
            }
          }else{
            $groupConcat = "'Resource' || '#' || w.idResource";
            $groupConcat .= " || '_Project' || '#' || w.idProject";
            if($showDetailElement){
              $groupConcat .= "|| '_' || w.refType || '#' || w.refId";
            }
          }
          if($selectedPool and !$detailResource){
            $res=new ResourceAll($selectResource,true);
            if($res->isResourceTeam){
              $resAllAr["refname"]=i18n('ResourceTeamAll');
              $resAllAr["reftype"]='ResourceTeamAll';
              $resAllAr["refid"]='1';
              $keyAll="ResourceTeamAll#1";
              $resAllAr["id"]="RTA".$res->id;
              $topidAll="RTA".$res->id;
              $canBeAll=true;
            }
          }else if($selectTeam and !$detailResource){
            $resAllAr["refname"]=SqlList::getNameFromId('Team', $selectTeam);
            $resAllAr["reftype"]='Team';
            $resAllAr["refid"]=$selectTeam;
            $keyAll="Team#$selectTeam";
            $resAllAr["id"]="T".$selectTeam;
            $topidAll="T".$selectTeam;
            $canBeAll=true;
          }else if($selectOrganization and !$detailResource){
            $resAllAr["refname"]=SqlList::getNameFromId('Organization', $selectOrganization);
            $resAllAr["reftype"]='Organization';
            $resAllAr["refid"]=$selectOrganization;
            $keyAll="Organization#$selectOrganization";
            $resAllAr["id"]="O".$selectOrganization;
            $topidAll="O".$selectOrganization;
            $canBeAll=true;
          }else if($selectResource == '' or ($showPoolForResource and !$detailResource)){
            $resAllAr["refname"]=i18n('allResource');
            $resAllAr["reftype"]='ResourceAll';
            $resAllAr["refid"]='1';
            $keyAll='ResourceAll#1';
            $resAllAr["id"]="RA1";
            $topidAll="RA1";
            $canBeAll=true;
          }
          $resAllAr["elementary"]='0';
          $resAllAr["idle"]='0';
          $resAllAr["wbs"]='';
          $resAllAr["wbssortable"]='';
          $resAllAr["realstartdate"]='';
          $resAllAr["realenddate"]='';
          $resAllAr["plannedstartdate"]='';
          $resAllAr["plannedenddate"]='';
          $resAllAr["realwork"]=0;
          $resAllAr["plannedwork"]=0;
          $resAllAr["topid"]=0;
          $resAllAr["idresource"]=null;
          $resAllAr["isparent"]=false;
          if($canBeAll)$list[$keyAll]=$resAllAr;
          while ($line = Sql::fetchLine($result)) {
            $line=array_change_key_case($line,CASE_LOWER);
            if($line['linkedresource'] and $line['idresource'] != $line['linkedresource']){
              $line['idresource'] = $line['linkedresource'];
              $line['name'] = SqlList::getNameFromId('ResourceAll', $line['linkedresource'], false);
            }
            //florent 4391
            if ($applyFilter and (!isset($arrayRestrictWbs[$line['wbssortable']]))) continue;
            if (! isset($allowedResource[$line['idresource']])) continue;
            $cptLine++;
            if ($line['idresource']!=$idResource) {
              $resourceList[$line['idresource']]=$line['idresource'];
              $idResource=$line['idresource'];
              $resAr=array();
              $resAr["refname"]=$line['name'];
              if ($line['isresourceteam']) {
                $resAr["reftype"]='ResourceTeam';
              } else {
                $resAr["reftype"]='Resource';
              }
              $resAr["refid"]=$idResource;
              $resAr["elementary"]='0';
              $idRes="R".$idResource;
              $resAr["id"]=$idRes;
              $resAr["idle"]='0';
              $resAr['idleFromRTA']=0;
              $resAr["wbs"]='';
              $resAr["wbssortable"]='';
              $resAr["realstartdate"]='';
              $resAr["realenddate"]='';
              $resAr["plannedstartdate"]='';
              $resAr["plannedenddate"]='';
              $resAr["realwork"]=0;
              $resAr["plannedwork"]=0;
              $resAr["idresource"]=$idResource;
              $resAr["topid"]=($topidAll == '' and $parentId != '')?$parentId:$topidAll;
              $resAr["isparent"]=false;
              if ($line['isresourceteam']) {
                $resAr["iconClass"]='ResourceTeam';
              } else if($line['ismaterial']){
                $resAr["iconClass"]='ResourceMaterial';
              } else {
                $resAr["iconClass"]='Resource';
              }
              $keyRes='Resource#'.$idResource;
              if($keyAll != '' and $resAr["topid"] and $line["reftype"]){
                $list[$keyAll]["isparent"]=true;
              }
              $resAr["isadministrative"]=false;
              $list[$keyRes]=$resAr;
              $sumReal=0;
              $sumPlanned=0;
              $idProject="";
            }
            if($line["reftype"]){
              if ($line['idproj']!=$idProject) {
                $idProject=$line['idproj'];
                $keyProj=$keyRes.'_Project#'.$idProject;
                if($showProject){
                  if (pq_array_key_exists($idProject, $arrayProject)) {
                    $prj=$arrayProject[$idProject];
                  } else {
                    $prj=new Project($idProject,false);
                    $arrayProject[$idProject]=$prj;
                  }
                  $resPr=array();
                  $resPr["refname"]=$prj->name;
                  $resPr["reftype"]='Project';
                  $resPr["refid"]=$idProject;
                  $resPr["elementary"]='0';
                  $idProj=$idRes."P".$idProject;
                  $resPr["id"]=$idProj;
                  $resPr["idle"]='0';
                  $resPr["wbs"]=$prj->ProjectPlanningElement->wbs;
                  $resPr["wbssortable"]=$prj->ProjectPlanningElement->wbsSortable;
                  $resPr["realstartdate"]='';
                  $resPr["realenddate"]='';
                  $resPr["plannedstartdate"]='';
                  $resPr["plannedenddate"]='';
                  $resPr["realwork"]=0;
                  $resPr["plannedwork"]=0;
                  $resPr["idresource"]=$idResource;
                  $resPr["topid"]=$idRes;
                  $resPr["isparent"]=false;
                  // Lookup or load ProjectType from cache
                  if (!isset($cachedProjectTypes[$prj->idProjectType])) {
                    $cachedProjectTypes[$prj->idProjectType] = new ProjectType($prj->idProjectType);
                  }
                  $projType = $cachedProjectTypes[$prj->idProjectType];
                  $resPr["isadministrative"]=($projType->code == 'ADM')?true:false;
                  if ($line['projectisunderconstruction']==1) {
                    $resPr['iconClass']='Construction';
                  }
                  if ($line['projectfixplanning']==1) {
                    $resPr['iconClass']='Fixed';
                  } else if ( ! isset($plannableProjectsList[$idProject]) ) {
                    $resPr['iconClass']='Fixed  ';
                  } else if ($prj->ProjectPlanningElement->needReplan and $line['projectfixplanning']!=1 and isset($plannableProjectsList[$idProject])) {
                    $resPr['iconClass']='Replan';
                  }
                  $list[$keyProj]=$resPr;
                  $sumProjReal=0;
                  $sumProjPlanned=0;
                  if($resPr["topid"]){
                    $list[$keyRes]["isparent"]=true;;
                  }
                }
              }
              $line["elementary"]='1';
              if (!isset($line["id"])) $line["id"]=$line["idassignment"];
              if ($line['reftype']=='Meeting' and $line['topreftype']=='PeriodicMeeting') {
                //Do not change topRefType  ;
                $line['topid']=$line['topid'].'_'.$line['idresource'];
              } else {
                if ($line['reftype']=='PeriodicMeeting') {
                  $line["elementary"]='0'; // Will contain meetings
                  $line["id"]=$line["idpe"].'_'.$line['idresource'];
                }
                $line["topreftype"]=($showProject)?'Project':'Resource';
                $line["toprefid"]=($showProject)?$idProject:$idResource;
              }
              if (floatval($line['plannedwork'])==0 and pq_trim($line['plannedstartdate'])=='' and pq_trim($line['peplannedstart'])!='') { $line['plannedstartdate']=$line['peplannedstart'];}
              if (floatval($line['plannedwork'])==0 and pq_trim($line['plannedenddate'])=='' and pq_trim($line['peplannedend'])!='') { $line['plannedenddate']=$line['peplannedend'];}
              if ($line['reftype']=='Meeting' and $line['topreftype']=='PeriodicMeeting') {
                // topid from query
              } else {
                $line["topid"]=($showProject)?$idProj:$idRes;
              }
              if (pq_trim($line["realstartdate"]) and !pq_trim($line["plannedstartdate"])) {
                $line['plannedstartdate']=$line['realstartdate'];
              }
              if ($line['paused']==1) {
                $line['plannedstartdate']='';
                $line['plannedenddate']='';
                $line['iconClass']='Fixed';
              }
              $line['projectname']=SqlList::getNameFromId('Project', $line['idproj']);
              // Lookup or load Project from cache
              if (pq_array_key_exists($line['idproj'], $arrayProject)) {
                $proj=$arrayProject[$line['idproj']];
              } else {
                $proj = new Project($line['idproj'], true);
                $arrayProject[$line['idproj']]=$proj;
              }
              $projectColor = $proj->getColor();
              $line['projectcolor']=$projectColor;
              $projectColorList[$line['idproj']]=$projectColor;
              // Lookup or load ref object from cache
              $refObjKey = $line['reftype'].'_'.$line['refid'];
              if (!isset($cachedRefObjects[$refObjKey])) {
                $cachedRefObjects[$refObjKey] = new $line['reftype']($line['refid'], true);
              }
              $refObject = $cachedRefObjects[$refObjKey];
              $type = SqlElement::getTypeName($line['reftype']);
              $line['type']=$refObject->$type;
              $line['typename']=SqlList::getNameFromId(SqlElement::getTypeClassName($line['reftype']), $refObject->$type);
              $line['progress']=($line["plannedwork"]>0)?round($line["realwork"]/$line["plannedwork"],2):'0';
              $line['planningmodename']=SqlList::getNameFromId('PlanningMode', $line['idplanningmode'], false);
              $line['resourcename']=SqlList::getNameFromId('ResourceAll', $line['idresource']);
              $line['productversion']=(property_exists($line['reftype'], 'idTargetProductVersion'))?$refObject->idTargetProductVersion:'';
              $line['productversionname']=(property_exists($line['reftype'], 'idTargetProductVersion'))?SqlList::getNameFromId('TargetProductVersion', $refObject->idTargetProductVersion):'';
              $line["isparent"]=false;
              if($line["topid"]){
                if($showProject){
                  $list[$keyProj]["isparent"]=true;
                }else{
                  $list[$keyRes]["isparent"]=true;
                }
              }
              // Lookup or load ProjectType from cache
              if (!isset($cachedProjectTypes[$proj->idProjectType])) {
                $cachedProjectTypes[$proj->idProjectType] = new ProjectType($proj->idProjectType);
              }
              $projType = $cachedProjectTypes[$proj->idProjectType];
              $line["isadministrative"]=($projType->code == 'ADM')?true:false;
              $keyElm=$keyProj.'_'.$line['reftype'].'#'.$line['refid'];
              $list[$keyElm]=$line;
              if (! $list[$keyRes]["realstartdate"] or $line['realstartdate'] < $list[$keyRes]["realstartdate"]) {
                if ($line['realstartdate'] and $line['realstartdate']<$line['plannedstartdate']) {
                  $list[$keyRes]["realstartdate"]=$line['realstartdate'];
                }
              }
              if (! $list[$keyRes]["realenddate"] or $line['realenddate'] > $list[$keyRes]["realenddate"]) {
                if ($line['realenddate'] and $line['realenddate']>$line['plannedenddate']) {
                  $list[$keyRes]["realenddate"]=$line['realenddate'];
                }
              }
              if (! $list[$keyRes]["plannedstartdate"] or $line['plannedstartdate'] < $list[$keyRes]["plannedstartdate"]) {
                if ($line['plannedstartdate'] ) {
                  $list[$keyRes]["plannedstartdate"]=$line['plannedstartdate'];
                }
              }
              if (! $list[$keyRes]["plannedenddate"] or $line['plannedenddate'] > $list[$keyRes]["plannedenddate"]) {
                if ($line['plannedenddate']) {
                  $list[$keyRes]["plannedenddate"]=$line['plannedenddate'];
                  if ($list[$keyRes]["plannedenddate"]>$list[$keyRes]["realenddate"]) {
                    $list[$keyRes]["realenddate"]="";
                  }
                }
              }
              if ($showProject) {
                if (! $list[$keyProj]["realstartdate"] or $line['realstartdate'] < $list[$keyProj]["realstartdate"]) {
                  if ($line['realstartdate'] and $line['realstartdate']<$line['plannedstartdate']) {
                    $list[$keyProj]["realstartdate"]=$line['realstartdate'];
                  }
                }
                if (! $list[$keyProj]["realenddate"] or $line['realenddate'] > $list[$keyProj]["realenddate"]) {
                  if ($line['realenddate'] and $line['realenddate']>$line['plannedenddate']) {
                    $list[$keyProj]["realenddate"]=$line['realenddate'];
                  }
                }
                if (! $list[$keyProj]["plannedstartdate"] or $line['plannedstartdate'] < $list[$keyProj]["plannedstartdate"]) {
                  if ($line['plannedstartdate'] ) {
                    $list[$keyProj]["plannedstartdate"]=$line['plannedstartdate'];
                  }
                }
                if (! $list[$keyProj]["plannedenddate"] or $line['plannedenddate'] > $list[$keyProj]["plannedenddate"]) {
                  if ($line['plannedenddate']) {
                    $list[$keyProj]["plannedenddate"]=$line['plannedenddate'];
                    if ($list[$keyProj]["plannedenddate"]>$list[$keyProj]["realenddate"]) {
                      $list[$keyProj]["realenddate"]="";
                    }
                  }
                }
              }
            }
          }
          
          // ============== work dates ================
          // Cache all assignments and planning elements used in work/planned/admin loops
          $cachedAssignments = array();
          $cachedPlanningElements = array();
          $wk=new Work();
          $querySelect = "select SUM(w.work) as work, w.workDate, w.idAssignment,";
          $querySelect .= (Sql::isPgsql())?" string_agg(DISTINCT $groupConcat, ',') as arrayKey":" group_concat(DISTINCT $groupConcat SEPARATOR ',') as arrayKey";
          $queryFrom = " from ".$wk->getDatabaseTableName()." w";
          $queryWhere = " where w.idResource in ".transformListIntoInClause($resourceList);
          $queryWhere .= ($isFromPlanning)?"":" and w.idProject in " . $visibleProjectsListDetail;
          $queryWhere .= " and w.idProject not in " . $adminProjectList;
          $groupBy = " group by w.idResource, w.workDate, w.idProject, w.idAssignment";
          $groupBy .= ($showDetailElement)?", w.refType, w.refId":"";
          $query = $querySelect.$queryFrom.$queryWhere.$groupBy." ORDER BY w.workDate ASC";
          $result=Sql::query($query);
          while ($line = Sql::fetchLine($result)) {
            $line=array_change_key_case($line,CASE_LOWER);
            if($line['workdate'] < $minStartDate or $line['workdate'] > $maxEndDate)continue;
            $idAssignment = $line['idassignment'];
            // Lookup or load Assignment from cache
            if (!isset($cachedAssignments[$idAssignment])) {
              $cachedAssignments[$idAssignment] = new Assignment($idAssignment);
            }
            $ass = $cachedAssignments[$idAssignment];
            // Lookup or load PlanningElement from cache
            $peKey = $ass->refType.'_'.$ass->refId.'_'.$ass->idProject;
            if (!isset($cachedPlanningElements[$peKey])) {
              $cachedPlanningElements[$peKey] = PlanningElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$ass->refType, "refId"=>$ass->refId, "idProject"=>$ass->idProject));
            }
            $pe = $cachedPlanningElements[$peKey];
            $peEndDateOver = '';
            if (PlanningMode::isFixedDuration($pe->idPlanningMode)) {
              if (intval($pe->validatedDuration)>0 and $pe->plannedDuration-$pe->validatedDuration>0) {
                $peEndDateOver=addWorkDaysToDate($pe->plannedStartDate, $pe->validatedDuration, $pe->idProject);
              }
            }
            $dateStatus = $pe->validatedEndDate;
            $overLimitedFixedDuration=false;
            switch ($scale){
              case 'day' :
                $date = $line['workdate'];
                break;
              case 'week' :
                $date = $line['workdate'];
                break;
              case 'month' :
                $date = weekFormat($line['workdate']);
                $dateStatus = weekFormat($pe->validatedEndDate);
                break;
              case 'quarter' :
                $date = weekFormat($line['workdate']);
                $dateStatus = weekFormat($pe->validatedEndDate);
                break;
            }
            if ($peEndDateOver != '' and $peEndDateOver<$line['workdate']) {
              $overLimitedFixedDuration=true;
            }
            if((!$dateStatus or $date <= $dateStatus) and !$overLimitedFixedDuration){
              $statusColor = "#50BB50";
            }else{
              $statusColor = "#BB5050";
              if($showLateColorPriority){
                $statusColor = "#E7E700";
              }
            }
            if (!isset($workDate[$keyAll]))$workDate[$keyAll]=array();
            if(!isset($workDate[$keyAll]['dates']))$workDate[$keyAll]['dates']=array();
            if(!isset($workDate[$keyAll]['dates'][$date]))$workDate[$keyAll]['dates'][$date]=array();
            if(isset($list[$keyAll])){
              $list[$keyAll]["realwork"]+=floatval($line['work']);
              $list[$keyAll]['idresource']=$resourceList;
            }
            $arrayKey = explode(',', $line['arraykey']);
            foreach ($arrayKey as $keys){
              $key = explode('_', $keys);
              $keyRes=(isset($key[0]))?$key[0]:'';
              $keyProj=(isset($key[1]) and $keyRes != '')?$keyRes.'_'.$key[1]:'';
              $keyElm=$keys;
              $idResource = (isset($key[0]))?pq_str_replace('Resource#', '', $key[0]):'';
              $idProject = explode('#', explode('_', $keyProj)[1])[1];
              $projectColor = '#777777';
              if(isset($projectColorList[$idProject])){
                $projectColor = $projectColorList[$idProject];
              }else{
                $proj = new Project($idProject, true);
                $projectColor = $proj->getColor();
                $projectColorList[$idProject] = $projectColor;
              }
              if(!$projectColor)$projectColor='#777777';
              if(!isset($workDate[$keyAll]['dates'][$date]['real']))$workDate[$keyAll]['dates'][$date]['real']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Projects']))$workDate[$keyAll]['dates'][$date]['real']['Projects']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Assignments']))$workDate[$keyAll]['dates'][$date]['real']['Assignments']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Globals']))$workDate[$keyAll]['dates'][$date]['real']['Globals']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Projects'][$projectColor]))$workDate[$keyAll]['dates'][$date]['real']['Projects'][$projectColor]=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Assignments'][$statusColor]))$workDate[$keyAll]['dates'][$date]['real']['Assignments'][$statusColor]=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Projects'][$projectColor]['work'])){
                $workDate[$keyAll]['dates'][$date]['real']['Projects'][$projectColor]['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['real']['Projects'][$projectColor]['work']+=floatval($line['work']);
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Assignments'][$statusColor]['work'])){
                $workDate[$keyAll]['dates'][$date]['real']['Assignments'][$statusColor]['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['real']['Assignments'][$statusColor]['work']+=floatval($line['work']);
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['real']['Globals']['work'])){
                $workDate[$keyAll]['dates'][$date]['real']['Globals']['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['real']['Globals']['work']+=floatval($line['work']);
              }
              if($keyRes != ''){
                if (!isset($workDate[$keyRes]))$workDate[$keyRes]=array();
                if(!isset($workDate[$keyRes]['dates']))$workDate[$keyRes]['dates']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]))$workDate[$keyRes]['dates'][$date]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Projects']))$workDate[$keyRes]['dates'][$date]['real']['Projects']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Assignments']))$workDate[$keyRes]['dates'][$date]['real']['Assignments']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Globals']))$workDate[$keyRes]['dates'][$date]['real']['Globals']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Projects'][$projectColor]))$workDate[$keyRes]['dates'][$date]['real']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Assignments'][$statusColor]))$workDate[$keyRes]['dates'][$date]['real']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Projects'][$projectColor]['work'])){
                  $workDate[$keyRes]['dates'][$date]['real']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['real']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyRes]['dates'][$date]['real']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['real']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['real']['Globals']['work'])){
                  $workDate[$keyRes]['dates'][$date]['real']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['real']['Globals']['work']+=floatval($line['work']);
                }
                if(isset($list[$keyRes]))$list[$keyRes]["realwork"]+=floatval($line['work']);
              }
              if($keyProj != '' and $showDetailProject){
                if (!isset($workDate[$keyProj]))$workDate[$keyProj]=array();
                if(!isset($workDate[$keyProj]['dates']))$workDate[$keyProj]['dates']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]))$workDate[$keyProj]['dates'][$date]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Projects']))$workDate[$keyProj]['dates'][$date]['real']['Projects']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Assignments']))$workDate[$keyProj]['dates'][$date]['real']['Assignments']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Globals']))$workDate[$keyProj]['dates'][$date]['real']['Global']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Projects'][$projectColor]))$workDate[$keyProj]['dates'][$date]['real']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Assignments'][$statusColor]))$workDate[$keyProj]['dates'][$date]['real']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Projects'][$projectColor]['work'])){
                  $workDate[$keyProj]['dates'][$date]['real']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['real']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyProj]['dates'][$date]['real']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['real']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['real']['Globals']['work'])){
                  $workDate[$keyProj]['dates'][$date]['real']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['real']['Globals']['work']+=floatval($line['work']);
                }
                if(isset($list[$keyProj]))$list[$keyProj]["realwork"]+=floatval($line['work']);
              }
              if($keyElm != '' and $showDetailElement){
                if (!isset($workDate[$keyElm]))$workDate[$keyElm]=array();
                if(!isset($workDate[$keyElm]['dates']))$workDate[$keyElm]['dates']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]))$workDate[$keyElm]['dates'][$date]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Projects']))$workDate[$keyElm]['dates'][$date]['real']['Projects']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Assignments']))$workDate[$keyElm]['dates'][$date]['real']['Assignments']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Globals']))$workDate[$keyElm]['dates'][$date]['real']['Global']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Projects'][$projectColor]))$workDate[$keyElm]['dates'][$date]['real']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Assignments'][$statusColor]))$workDate[$keyElm]['dates'][$date]['real']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Projects'][$projectColor]['work'])){
                  $workDate[$keyElm]['dates'][$date]['real']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['real']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyElm]['dates'][$date]['real']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['real']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['real']['Globals']['work'])){
                  $workDate[$keyElm]['dates'][$date]['real']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['real']['Globals']['work']+=floatval($line['work']);
                }
              }
            }
          }
          $wk=new PlannedWork();
          $querySelect = "select SUM(w.work) as work, w.workDate, w.idAssignment, w.surbooked, w.surbookedWork, ";
          $querySelect .= (Sql::isPgsql())?" string_agg(DISTINCT $groupConcat, ',') as arrayKey":" group_concat(DISTINCT $groupConcat SEPARATOR ',') as arrayKey";
          $queryFrom = " from ".$wk->getDatabaseTableName()." w";
          $queryWhere = " where w.idResource in ".transformListIntoInClause($resourceList);
          $queryWhere .= ($isFromPlanning)?"":" and w.idProject in " . $visibleProjectsListDetail;
          $queryWhere .= " and w.idProject not in " . $adminProjectList;
          $groupBy = " group by w.idResource, w.workDate, w.idProject, w.idAssignment, w.surbooked, w.surbookedWork";
          $groupBy .= ($showDetailElement)?", w.refType, w.refId":"";
          $query = $querySelect.$queryFrom.$queryWhere.$groupBy." ORDER BY w.workDate ASC";
          $result=Sql::query($query);
          while ($line = Sql::fetchLine($result)) {
            $line=array_change_key_case($line,CASE_LOWER);
            if($line['workdate'] < $minStartDate or $line['workdate'] > $maxEndDate)continue;
            $idAssignment = $line['idassignment'];
            // Lookup or load Assignment from cache
            if (!isset($cachedAssignments[$idAssignment])) {
              $cachedAssignments[$idAssignment] = new Assignment($idAssignment);
            }
            $ass = $cachedAssignments[$idAssignment];
            // Lookup or load PlanningElement from cache
            $peKey = $ass->refType.'_'.$ass->refId.'_'.$ass->idProject;
            if (!isset($cachedPlanningElements[$peKey])) {
              $cachedPlanningElements[$peKey] = PlanningElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$ass->refType, "refId"=>$ass->refId, "idProject"=>$ass->idProject));
            }
            $pe = $cachedPlanningElements[$peKey];
            $peEndDateOver = '';
            if (PlanningMode::isFixedDuration($pe->idPlanningMode)) {
              if (intval($pe->validatedDuration)>0 and $pe->plannedDuration-$pe->validatedDuration>0) {
                $peEndDateOver=addWorkDaysToDate($pe->plannedStartDate, $pe->validatedDuration, $pe->idProject);
              }
            }
            $dateStatus = $pe->validatedEndDate;
            $overLimitedFixedDuration=false;
            switch ($scale){
              case 'day' :
                $date = $line['workdate'];
                break;
              case 'week' :
                $date = $line['workdate'];
                break;
              case 'month' :
                $date = weekFormat($line['workdate']);
                $dateStatus = weekFormat($pe->validatedEndDate);
                break;
              case 'quarter' :
                $date = weekFormat($line['workdate']);
                $dateStatus = weekFormat($pe->validatedEndDate);
                break;
            }
            if ($peEndDateOver != '' and $peEndDateOver<$line['workdate']) {
              $overLimitedFixedDuration=true;
            }
            if((!$dateStatus or $date <= $dateStatus) and !$overLimitedFixedDuration){
              $statusColor = "#50BB50";
              $isLate = false;
            }else{
              $statusColor = "#BB5050";
              $isLate = true;
              if($showLateColorPriority){
                $statusColor = "#E7E700";
              }
            }
            if (!isset($workDate[$keyAll]))$workDate[$keyAll]=array();
            if(!isset($workDate[$keyAll]['dates']))$workDate[$keyAll]['dates']=array();
            if(!isset($workDate[$keyAll]['dates'][$date]))$workDate[$keyAll]['dates'][$date]=array();
            if(isset($list[$keyAll])){
              $list[$keyAll]["plannedwork"]+=floatval($line['work']);
              $list[$keyAll]['idresource']=$resourceList;
            }
            $arrayKey = explode(',', $line['arraykey']);
            foreach ($arrayKey as $keys){
              $key = explode('_', $keys);
              $keyRes=(isset($key[0]))?$key[0]:'';
              $keyProj=(isset($key[1]) and $keyRes != '')?$keyRes.'_'.$key[1]:'';
              $keyElm=$keys;
              $idResource = (isset($key[0]))?pq_str_replace('Resource#', '', $key[0]):'';
              $idProject = explode('#', explode('_', $keyProj)[1])[1];
              $projectColor = '#777777';
              if(isset($projectColorList[$idProject])){
                $projectColor = $projectColorList[$idProject];
              }else{
                $proj = new Project($idProject, true);
                $projectColor = $proj->getColor();
                $projectColorList[$idProject] = $projectColor;
              }
              if(!$projectColor)$projectColor='#777777';
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Projects']))$workDate[$keyAll]['dates'][$date]['planned']['Projects']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Assignments']))$workDate[$keyAll]['dates'][$date]['planned']['Assignments']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Globals']))$workDate[$keyAll]['dates'][$date]['planned']['Globals']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Projects'][$projectColor]))$workDate[$keyAll]['dates'][$date]['planned']['Projects'][$projectColor]=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]))$workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Projects'][$projectColor]['work'])){
                $workDate[$keyAll]['dates'][$date]['planned']['Projects'][$projectColor]['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['planned']['Projects'][$projectColor]['work']+=floatval($line['work']);
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['work'])){
                $workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['work']+=floatval($line['work']);
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor'])){
                $workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor']=$isLate;
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork'])){
                $workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']=$line['surbookedwork'];
              }else{
                $workDate[$keyAll]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']+=$line['surbookedwork'];
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['planned']['Globals']['work'])){
                $workDate[$keyAll]['dates'][$date]['planned']['Globals']['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['planned']['Globals']['work']+=floatval($line['work']);
              }
              if($keyRes != ''){
                if (!isset($workDate[$keyRes]))$workDate[$keyRes]=array();
                if(!isset($workDate[$keyRes]['dates']))$workDate[$keyRes]['dates']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]))$workDate[$keyRes]['dates'][$date]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Projects']))$workDate[$keyRes]['dates'][$date]['planned']['Projects']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Assignments']))$workDate[$keyRes]['dates'][$date]['planned']['Assignments']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Globals']))$workDate[$keyRes]['dates'][$date]['planned']['Globals']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Projects'][$projectColor]))$workDate[$keyRes]['dates'][$date]['planned']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]))$workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Projects'][$projectColor]['work'])){
                  $workDate[$keyRes]['dates'][$date]['planned']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['planned']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor'])){
                  $workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor']=$isLate;
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork'])){
                  $workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']=$line['surbookedwork'];
                }else{
                  $workDate[$keyRes]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']+=$line['surbookedwork'];
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['planned']['Globals']['work'])){
                  $workDate[$keyRes]['dates'][$date]['planned']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['planned']['Globals']['work']+=floatval($line['work']);
                }
                if(isset($list[$keyRes]))$list[$keyRes]["plannedwork"]+=floatval($line['work']);
              }
              if($keyProj != '' and $showDetailProject){
                if (!isset($workDate[$keyProj]))$workDate[$keyProj]=array();
                if(!isset($workDate[$keyProj]['dates']))$workDate[$keyProj]['dates']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]))$workDate[$keyProj]['dates'][$date]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Projects']))$workDate[$keyProj]['dates'][$date]['planned']['Projects']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Assignments']))$workDate[$keyProj]['dates'][$date]['planned']['Assignments']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Globals']))$workDate[$keyProj]['dates'][$date]['planned']['Globals']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Projects'][$projectColor]))$workDate[$keyProj]['dates'][$date]['planned']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]))$workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Projects'][$projectColor]['work'])){
                  $workDate[$keyProj]['dates'][$date]['planned']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['planned']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor'])){
                  $workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor']=$isLate;
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork'])){
                  $workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']=$line['surbookedwork'];
                }else{
                  $workDate[$keyProj]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']+=$line['surbookedwork'];
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['planned']['Globals']['work'])){
                  $workDate[$keyProj]['dates'][$date]['planned']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['planned']['Globals']['work']+=floatval($line['work']);
                }
                if(isset($list[$keyProj]))$list[$keyProj]["plannedwork"]+=floatval($line['work']);
              }
              if($keyElm != '' and $showDetailElement){
                if (!isset($workDate[$keyElm]))$workDate[$keyElm]=array();
                if(!isset($workDate[$keyElm]['dates']))$workDate[$keyElm]['dates']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]))$workDate[$keyElm]['dates'][$date]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Projects']))$workDate[$keyElm]['dates'][$date]['planned']['Projects']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Assignments']))$workDate[$keyElm]['dates'][$date]['planned']['Assignments']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Globals']))$workDate[$keyElm]['dates'][$date]['planned']['Globals']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Projects'][$projectColor]))$workDate[$keyElm]['dates'][$date]['planned']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]))$workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Projects'][$projectColor]['work'])){
                  $workDate[$keyElm]['dates'][$date]['planned']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['planned']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor'])){
                  $workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['isLateColor']=$isLate;
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork'])){
                  $workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']=$line['surbookedwork'];
                }else{
                  $workDate[$keyElm]['dates'][$date]['planned']['Assignments'][$statusColor]['surbookedWork']+=$line['surbookedwork'];
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['planned']['Globals']['work'])){
                  $workDate[$keyElm]['dates'][$date]['planned']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['planned']['Globals']['work']+=floatval($line['work']);
                }
              }
            }
          }
          $where = "idProject in ".$adminProjectList;
          $act=new Activity();
          $actList=$act->getSqlElementsFromCriteria(null, null, $where);
          $actListId=array(0=>0);
          foreach ($actList as $activity) {
            $actListId[$activity->id]=$activity->id;
          }
          $wk=new Work();
          $querySelect = "select SUM(w.work) as work, w.workDate, w.idAssignment,";
          $querySelect .= (Sql::isPgsql())?" string_agg(DISTINCT $groupConcat, ',') as arrayKey":" group_concat(DISTINCT $groupConcat SEPARATOR ',') as arrayKey";
          $queryFrom = " from ".$wk->getDatabaseTableName()." w";
          $queryWhere = " where refType='Activity' and refId in (".implode(',', $actListId).") and w.idResource in ".transformListIntoInClause($resourceList);
          $queryWhere .= " and w.idProject in " . $adminProjectList;
          $groupBy = " group by w.idResource, w.workDate, w.idProject, w.idAssignment";
          $groupBy .= ($showDetailProject or $showDetailElement)?", w.refType, w.refId":"";
          $query = $querySelect.$queryFrom.$queryWhere.$groupBy." ORDER BY w.workDate ASC";
          $result=Sql::query($query);
          while ($line = Sql::fetchLine($result)) {
            $line=array_change_key_case($line,CASE_LOWER);
            if($line['workdate'] < $minStartDate or $line['workdate'] > $maxEndDate)continue;
            $idAssignment = $line['idassignment'];
            // Lookup or load Assignment from cache
            if (!isset($cachedAssignments[$idAssignment])) {
              $cachedAssignments[$idAssignment] = new Assignment($idAssignment);
            }
            $ass = $cachedAssignments[$idAssignment];
            // Lookup or load PlanningElement from cache
            $peKey = $ass->refType.'_'.$ass->refId.'_'.$ass->idProject;
            if (!isset($cachedPlanningElements[$peKey])) {
              $cachedPlanningElements[$peKey] = PlanningElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$ass->refType, "refId"=>$ass->refId, "idProject"=>$ass->idProject));
            }
            $pe = $cachedPlanningElements[$peKey];
            switch ($scale){
              case 'day' :
                $date = $line['workdate'];
                $dateStatus = $pe->validatedEndDate;
                break;
              case 'week' :
                $date = $line['workdate'];
                $dateStatus = $pe->validatedEndDate;
                break;
              case 'month' :
                $date = weekFormat($line['workdate']);
                $dateStatus = weekFormat($pe->validatedEndDate);
                break;
              case 'quarter' :
                $date = weekFormat($line['workdate']);
                $dateStatus = weekFormat($pe->validatedEndDate);
                break;
            }
            $statusColor = "#2e75bd";
            if (!isset($workDate[$keyAll]))$workDate[$keyAll]=array();
            if(!isset($workDate[$keyAll]['dates']))$workDate[$keyAll]['dates']=array();
            if(!isset($workDate[$keyAll]['dates'][$date]))$workDate[$keyAll]['dates'][$date]=array();
            if(isset($list[$keyAll])){
              $list[$keyAll]["realwork"]+=floatval($line['work']);
              $list[$keyAll]['idresource']=$resourceList;
            }
            $arrayKey = explode(',', $line['arraykey']);
            foreach ($arrayKey as $keys){
              $key = explode('_', $keys);
              $keyRes=(isset($key[0]))?$key[0]:'';
              $keyProj=(isset($key[1]) and $keyRes != '')?$keyRes.'_'.$key[1]:'';
              $keyElm=$keys;
              $idResource = (isset($key[0]))?pq_str_replace('Resource#', '', $key[0]):'';
              $idProject = explode('#', explode('_', $keyProj)[1])[1];
              $projectColor = '#777777';
              if(isset($projectColorList[$idProject])){
                $projectColor = $projectColorList[$idProject];
              }else{
                $proj = new Project($idProject, true);
                $projectColor = $proj->getColor();
                $projectColorList[$idProject] = $projectColor;
              }
              if(!$projectColor)$projectColor='#777777';
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Projects']))$workDate[$keyAll]['dates'][$date]['admin']['Projects']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Assignments']))$workDate[$keyAll]['dates'][$date]['admin']['Assignments']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Globals']))$workDate[$keyAll]['dates'][$date]['admin']['Globals']=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Projects'][$projectColor]))$workDate[$keyAll]['dates'][$date]['admin']['Projects'][$projectColor]=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Assignments'][$statusColor]))$workDate[$keyAll]['dates'][$date]['admin']['Assignments'][$statusColor]=array();
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Projects'][$projectColor]['work'])){
                $workDate[$keyAll]['dates'][$date]['admin']['Projects'][$projectColor]['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['admin']['Projects'][$projectColor]['work']+=floatval($line['work']);
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Assignments'][$statusColor]['work'])){
                $workDate[$keyAll]['dates'][$date]['admin']['Assignments'][$statusColor]['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['admin']['Assignments'][$statusColor]['work']+=floatval($line['work']);
              }
              if(!isset($workDate[$keyAll]['dates'][$date]['admin']['Globals']['work'])){
                $workDate[$keyAll]['dates'][$date]['admin']['Globals']['work']=floatval($line['work']);
              }else{
                $workDate[$keyAll]['dates'][$date]['admin']['Globals']['work']+=floatval($line['work']);
              }
              if($keyRes != ''){
                if (!isset($workDate[$keyRes]))$workDate[$keyRes]=array();
                if(!isset($workDate[$keyRes]['dates']))$workDate[$keyRes]['dates']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]))$workDate[$keyRes]['dates'][$date]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Projects']))$workDate[$keyRes]['dates'][$date]['admin']['Projects']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Assignments']))$workDate[$keyRes]['dates'][$date]['admin']['Assignments']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Globals']))$workDate[$keyRes]['dates'][$date]['admin']['Globals']=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Projects'][$projectColor]))$workDate[$keyRes]['dates'][$date]['admin']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Assignments'][$statusColor]))$workDate[$keyRes]['dates'][$date]['admin']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Projects'][$projectColor]['work'])){
                  $workDate[$keyRes]['dates'][$date]['admin']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['admin']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyRes]['dates'][$date]['admin']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['admin']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyRes]['dates'][$date]['admin']['Globals']['work'])){
                  $workDate[$keyRes]['dates'][$date]['admin']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyRes]['dates'][$date]['admin']['Globals']['work']+=floatval($line['work']);
                }
                if(isset($list[$keyRes]))$list[$keyRes]["realwork"]+=floatval($line['work']);
              }
              if($keyProj != '' and $showDetailProject){
                if (!isset($workDate[$keyProj]))$workDate[$keyProj]=array();
                if(!isset($workDate[$keyProj]['dates']))$workDate[$keyProj]['dates']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]))$workDate[$keyProj]['dates'][$date]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Projects']))$workDate[$keyProj]['dates'][$date]['admin']['Projects']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Assignments']))$workDate[$keyProj]['dates'][$date]['admin']['Assignments']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Globals']))$workDate[$keyProj]['dates'][$date]['admin']['Globals']=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Projects'][$projectColor]))$workDate[$keyProj]['dates'][$date]['admin']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Assignments'][$statusColor]))$workDate[$keyProj]['dates'][$date]['admin']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Projects'][$projectColor]['work'])){
                  $workDate[$keyProj]['dates'][$date]['admin']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['admin']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyProj]['dates'][$date]['admin']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['admin']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyProj]['dates'][$date]['admin']['Globals']['work'])){
                  $workDate[$keyProj]['dates'][$date]['admin']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyProj]['dates'][$date]['admin']['Globals']['work']+=floatval($line['work']);
                }
                if(isset($list[$keyProj]))$list[$keyProj]["realwork"]+=floatval($line['work']);
              }
              if($keyElm != '' and $showDetailElement){
                if (!isset($workDate[$keyElm]))$workDate[$keyElm]=array();
                if(!isset($workDate[$keyElm]['dates']))$workDate[$keyElm]['dates']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]))$workDate[$keyElm]['dates'][$date]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Projects']))$workDate[$keyElm]['dates'][$date]['admin']['Projects']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Assignments']))$workDate[$keyElm]['dates'][$date]['admin']['Assignments']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Globals']))$workDate[$keyElm]['dates'][$date]['admin']['Globals']=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Projects'][$projectColor]))$workDate[$keyElm]['dates'][$date]['admin']['Projects'][$projectColor]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Assignments'][$statusColor]))$workDate[$keyElm]['dates'][$date]['admin']['Assignments'][$statusColor]=array();
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Projects'][$projectColor]['work'])){
                  $workDate[$keyElm]['dates'][$date]['admin']['Projects'][$projectColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['admin']['Projects'][$projectColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Assignments'][$statusColor]['work'])){
                  $workDate[$keyElm]['dates'][$date]['admin']['Assignments'][$statusColor]['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['admin']['Assignments'][$statusColor]['work']+=floatval($line['work']);
                }
                if(!isset($workDate[$keyElm]['dates'][$date]['admin']['Globals']['work'])){
                  $workDate[$keyElm]['dates'][$date]['admin']['Globals']['work']=floatval($line['work']);
                }else{
                  $workDate[$keyElm]['dates'][$date]['admin']['Globals']['work']+=floatval($line['work']);
                }
              }
            }
          }
          $minWeek = explode('-', weekFormat($minStartDate));
          $tmpMinStartDate = date('Y-m-d', firstDayofWeek($minWeek[1], $minWeek[0]));
          $maxWeek = explode('-', weekFormat($maxEndDate));
          $tmpMaxEndDate = lastDayofWeek($maxWeek[1], $maxWeek[0]);
          // ADD RESOURCES OF POOL FROM SELECTED RESOURCE
          //       if($showPoolForResource){
          foreach ($resourceList as $idResource){
            $isResTeam = SqlList::getFieldFromId('ResourceAll', $idResource, 'isResourceTeam');
            if($isResTeam){
              $rtaList=$rta->getSqlElementsFromCriteria(array('idResourceTeam'=>$idResource));
              foreach ($rtaList as $rta) {
                //                 if ($rta->idle) continue;
                if($rta->idle and !$rta->endDate){
                  $rta->endDate = date('Y-m-d', pq_strtotime("yesterday"));
                }
                if (workPlanRtaPeriodOverlaps($rta->startDate, $rta->endDate, $tmpMinStartDate, $tmpMaxEndDate)) {
                      if (!isset($resourceList[$rta->idResource])) $resourceList[$rta->idResource]=$rta->idResource;
                    }
              }
            }
          }
          //       }
          $resourceCalendar = array();
          $resTeamCapacity = array();
          $isResourceTeamOnly = false;
          if(count($resourceList) == 1){
            $idRes = array_key_first($resourceList);
            $res = new ResourceAll($idRes);
            if($res->isResourceTeam)$isResourceTeamOnly=true;
          }
          // Cache admin work per resource+date in one query
          $adminWorkCache = array();
          if (count($actListId) > 0 && count($resourceList) > 0) {
            $wkAdm = new Work();
            $admQuery = "SELECT SUM(w.work) as work, w.workDate, w.idResource"
                ." FROM ".$wkAdm->getDatabaseTableName()." w"
                    ." WHERE w.refType='Activity' AND w.refId IN (".implode(',', $actListId).")"
                        ." AND w.idResource IN ".transformListIntoInClause($resourceList)
                        ." AND w.idProject IN ".$adminProjectList
                        ." AND w.workDate >= '$tmpMinStartDate' AND w.workDate <= '$tmpMaxEndDate'"
                        ." GROUP BY w.workDate, w.idResource";
                        $admResult = Sql::query($admQuery);
                        while ($admLine = Sql::fetchLine($admResult)) {
                          $admLine = array_change_key_case($admLine, CASE_LOWER);
                          $adminWorkCache[$admLine['idresource']][$admLine['workdate']] = floatval($admLine['work']);
                        }
          }
          // Cache RTA lists per resource
          $cachedRtaByRes = array();
          $resTeamAffTmp = new ResourceTeamAffectation();
          $resListInClause = transformListIntoInClause($resourceList);
          foreach ($resourceList as $idResource) {
            $whereRta = "idResource = $idResource and idResourceTeam in ".$resListInClause;
            $cachedRtaByRes[$idResource] = $resTeamAffTmp->getSqlElementsFromCriteria(null, null, $whereRta);
          }
          foreach ($resourceList as $idResource){
            $tmpStart = $tmpMinStartDate;
            $res = new ResourceAll($idResource, true);
            if($res->isResourceTeam and !$isResourceTeamOnly) continue;
            if (!$res->id) continue;
            // Fetch RTA list from cache
            $rtaList = isset($cachedRtaByRes[$idResource]) ? $cachedRtaByRes[$idResource] : array();
            while ($tmpStart <= $tmpMaxEndDate){
              $date = $tmpStart;
              $capacity = $res->getCapacityPeriod($tmpStart);
              $resourceCapacity = $capacity;
              $isResourceOffDay = isOffDay($tmpStart, $res->idCalendarDefinition);
              $capacityForAggregation = ($isResourceOffDay)?0:$capacity;
              // Value of the capacity line on a column that is off on every day : the line then
              // stays at the nominal capacity instead of falling down to zero. Kept apart from
              // the capacity itself, which must stay the real capacity of the column.
              $capacityOnOffDay = $resourceCapacity;
              if($scale == 'month' or $scale == 'quarter'){
                $date = weekFormat($tmpStart);
                $capacity=$capacityForAggregation;
                // On these scales a column holds a whole week : only the days that are open in the
                // weekly pattern must feed the fallback, otherwise a fully off week would show the
                // capacity of 7 days (14d) where an ordinary week shows the one of 5 days (10d).
                if(isWeeklyPatternOffDay($tmpStart, $res->idCalendarDefinition))$capacityOnOffDay = 0;
              }
              $resCapacityOnPool = 0;
              foreach ($rtaList as $rta){
                if (($rta->startDate==null or $tmpStart >= $rta->startDate) and ($rta->endDate==null or $tmpStart <= $rta->endDate)) {
                  $capacityAll = 0;
                  $rtaRate = $rta->rate/100;
                  $capacityAll = $capacityForAggregation*$rtaRate;
                  $capacityAllOnOffDay = $capacityOnOffDay*$rtaRate;
                  // Lookup admin work from pre-loaded cache
                  $adminWork = isset($adminWorkCache[$res->id][$tmpStart]) ? $adminWorkCache[$res->id][$tmpStart] : 0;
                  $adminWork = ($adminWork > 1-$rtaRate)?$adminWork - (1-$rtaRate):0;
                  $resCapacityOnPool += $capacityAll;
                  
                  $keyRTA = "Resource#".$rta->idResourceTeam;
                  if(!isset($workDate[$keyRTA]['dates'][$date]['admin']['Globals']['work'])){
                    $workDate[$keyRTA]['dates'][$date]['admin']['Globals']['work']=$adminWork;
                  }else{
                    $workDate[$keyRTA]['dates'][$date]['admin']['Globals']['work']+=$adminWork;
                  }
                  $keyRes = "Resource#".$idResource;
                  if(isset($list[$keyRes]['idleFromRTA']) and $rta->endDate==null){
                    $list[$keyRes]['idleFromRTA']=$rta->idle;
                  }
                  if(!isset($resTeamCapacity[$rta->idResourceTeam][$date]['capacity'])){
                    $resTeamCapacity[$rta->idResourceTeam][$date]['capacity']=$capacityAll;
                  }else{
                    $resTeamCapacity[$rta->idResourceTeam][$date]['capacity']+=$capacityAll;
                  }
                  if(!isset($resTeamCapacity[$rta->idResourceTeam][$date]['capacityOnOffDay'])){
                    $resTeamCapacity[$rta->idResourceTeam][$date]['capacityOnOffDay']=$capacityAllOnOffDay;
                  }else{
                    $resTeamCapacity[$rta->idResourceTeam][$date]['capacityOnOffDay']+=$capacityAllOnOffDay;
                  }
                  $resTeamCapacity[$rta->idResourceTeam][$date]['hasResource']=1;
                  if(!$isResourceOffDay){
                    $resTeamCapacity[$rta->idResourceTeam][$date]['hasWorkingDay']=1;
                  }
                }else{
                  if(!isset($resTeamCapacity[$rta->idResourceTeam][$date]['capacity'])){
                    $resTeamCapacity[$rta->idResourceTeam][$date]['capacity']=0;
                  }
                }
              }
              if(!isset($resourceCalendar[$idResource][$date]['capacity'])){
                $resourceCalendar[$idResource][$date]['capacity']=$capacity;
              }else{
                $resourceCalendar[$idResource][$date]['capacity']+=$capacity;
              }
              if(!isset($resourceCalendar[$idResource][$date]['capacityOnOffDay'])){
                $resourceCalendar[$idResource][$date]['capacityOnOffDay']=$capacityOnOffDay;
              }else{
                $resourceCalendar[$idResource][$date]['capacityOnOffDay']+=$capacityOnOffDay;
              }
              $resourceCalendar[$idResource][$date]['hasResource']=1;
              if(!$isResourceOffDay){
                $resourceCalendar[$idResource][$date]['hasWorkingDay']=1;
              }
              $capacityAllResources = $capacityForAggregation;
              $addCapacityToAll = (!$selectResource or $selectedPool or $selectResource == $idResource);
              if($addCapacityToAll){
                if(!$selectedPool and $selectResource == $idResource){
                  $capacityAllResources -= $resCapacityOnPool;
                }
                if(!isset($resourceCalendar['all'][$date]['capacity'])){
                  $resourceCalendar['all'][$date]['capacity']=$capacityAllResources;
                }else{
                  $resourceCalendar['all'][$date]['capacity']+=$capacityAllResources;
                }
                if(!isset($resourceCalendar['all'][$date]['capacityOnOffDay'])){
                  $resourceCalendar['all'][$date]['capacityOnOffDay']=$capacityOnOffDay;
                }else{
                  $resourceCalendar['all'][$date]['capacityOnOffDay']+=$capacityOnOffDay;
                }
                $resourceCalendar['all'][$date]['hasResource']=1;
                if(!$isResourceOffDay){
                  $resourceCalendar['all'][$date]['hasWorkingDay']=1;
                }
              }
              if(!isset($resourceCalendar[$idResource][$date]['isoffday'])){
                $resourceCalendar[$idResource][$date]['isoffday']=$isResourceOffDay;
              }else{
                $resourceCalendar[$idResource][$date]['isoffday']+=$isResourceOffDay;
              }
              $tmpStart = addDaysToDate($tmpStart, 1);
            }
          }
          // Same fallback as for teams and for the 'all' line : on a column where the resource is
          // off on every day, the line keeps the nominal capacity rather than zero.
          foreach ($resourceCalendar as $idResourceCalendar=>&$dates){
            if($idResourceCalendar === 'all')continue;
            foreach ($dates as &$calendar){
              $resourceOff = (isset($calendar['hasResource']) and !isset($calendar['hasWorkingDay']));
              if($resourceOff and isset($calendar['capacityOnOffDay']) and $calendar['capacityOnOffDay']!=$calendar['capacity']){
                $calendar['linecapacity']=$calendar['capacityOnOffDay'];
              }
              unset($calendar['capacityOnOffDay'], $calendar['hasResource'], $calendar['hasWorkingDay']);
            }
            unset($calendar);
          }
          unset($dates);
          foreach ($resTeamCapacity as &$dates){
            foreach ($dates as &$calendar){
              $allResourcesOff = (isset($calendar['hasResource']) and !isset($calendar['hasWorkingDay']));
              if($allResourcesOff and $calendar['capacityOnOffDay']!=$calendar['capacity']){
                $calendar['linecapacity']=$calendar['capacityOnOffDay'];
              }
              $calendar['isoffday']=($allResourcesOff)?1:0;
              unset($calendar['capacityOnOffDay'], $calendar['hasResource'], $calendar['hasWorkingDay']);
            }
            unset($calendar);
          }
          unset($dates);
          $resourceCalendar = array_merge_preserve_keys($resourceCalendar, $resTeamCapacity);
          if(!$selectedPool and $selectResource){
            foreach ($resTeamCapacity as $idResTeam=>$dates){
              foreach ($dates as $date=>$value){
                if(isset($resourceCalendar['all'][$date]['capacity'])){
                  if(!isset($resourceCalendar['all'][$date]['linecapacity'])){
                    $resourceCalendar['all'][$date]['linecapacity']=$resourceCalendar['all'][$date]['capacity'];
                  }
                  $resourceCalendar['all'][$date]['capacity'] += $value['capacity'];
                  $resourceCalendar['all'][$date]['linecapacity'] += (isset($value['linecapacity']))?$value['linecapacity']:$value['capacity'];
                }
              }
            }
          }
          if(isset($resourceCalendar['all'])){
            foreach ($resourceCalendar['all'] as &$calendar){
              $allResourcesOff = (isset($calendar['hasResource']) and !isset($calendar['hasWorkingDay']));
              // The line value takes over what the teams merged above, as the capacity did before.
              if($allResourcesOff){
                $calendar['linecapacity']=$calendar['capacityOnOffDay'];
              }
              if(isset($calendar['linecapacity']) and $calendar['linecapacity']==$calendar['capacity']){
                unset($calendar['linecapacity']);
              }
              $calendar['isoffday']=($allResourcesOff)?1:0;
              unset($calendar['capacityOnOffDay'], $calendar['hasResource'], $calendar['hasWorkingDay']);
            }
            unset($calendar);
          }
          // Sort Assignments arrays once before JSON serialization
          foreach ($workDate as &$wdEntry) {
            if (!isset($wdEntry['dates'])) continue;
            foreach ($wdEntry['dates'] as &$dateEntry) {
              foreach (array('real','planned','admin') as $wType) {
                if (isset($dateEntry[$wType]['Assignments'])) {
                  ksort($dateEntry[$wType]['Assignments']);
                }
              }
            }
            unset($dateEntry);
          }
          unset($wdEntry);
          if(count($list) > 0){
            $idToKey=array();
            $childrenByParent=array();
            foreach ($list as $treeKey=>$treeLine) {
              $idToKey[(string)$treeLine['id']]=$treeKey;
            }
            foreach ($list as $treeKey=>$treeLine) {
              $parentKey=(string)($treeLine['topid']??'');
              if (!isset($childrenByParent[$parentKey])) {
                $childrenByParent[$parentKey]=array();
              }
              $childrenByParent[$parentKey][]=$treeKey;
            }
            $orderedKeys=array();
            $visitedKeys=array();
            $appendBranch=function($treeKey) use (&$appendBranch, &$orderedKeys, &$visitedKeys, &$list, &$childrenByParent) {
              if (isset($visitedKeys[$treeKey])) return;
              $visitedKeys[$treeKey]=true;
              $orderedKeys[]=$treeKey;
              $lineId=(string)$list[$treeKey]['id'];
              if (isset($childrenByParent[$lineId])) {
                foreach ($childrenByParent[$lineId] as $childKey) {
                  $appendBranch($childKey);
                }
              }
            };
            foreach ($list as $treeKey=>$treeLine) {
              $parentKey=(string)($treeLine['topid']??'');
              if ($parentKey==='' || $parentKey==='0' || !isset($idToKey[$parentKey])) {
                $appendBranch($treeKey);
              }
            }
            foreach ($list as $treeKey=>$treeLine) {
              $appendBranch($treeKey);
            }
            echo '{"identifier":"id",' ;
            echo ' "items":[';
            $idResource="";
            $idSkippedResource="";
            foreach ($orderedKeys as $key) {
              $line=$list[$key];
              if ($line['idresource']!=$idResource) {
                $idResource=$line['idresource'];
              }
              if($selectedPool){
                if(isset($line['idleFromRTA'])){
                  if($line['idleFromRTA'] == '1' and $line['plannedwork'] == '0' and $line['realwork'] == '0'){
                    $idSkippedResource=$idResource;
                    continue;
                  }
                }
                if($idResource == $idSkippedResource)continue;
              }
              $line['resource']=(is_array($idResource))?implode(',', $idResource):$idResource;
              echo (++$nbRows>1)?',':'';
              echo  '{';
              $nbFields=0;
              $idPe="";
              if (pq_trim($line['plannedenddate'])=='' and pq_trim($line['realenddate'])!='') $line['plannedenddate']=$line['realenddate'];
              if (pq_trim($line['plannedstartdate'])=='' and pq_trim($line['realstartdate'])!='') $line['plannedstartdate']=$line['realstartdate'];
              foreach ($line as $id => $val) {
                $val=(is_array($val))?implode(',', $val):$val;
                if ($val===null) {$val=" ";}
                if ($val=="") {$val=" ";}
                echo (++$nbFields>1)?',':'';
                if ($id=='refname' or $id=='resource' or pq_substr($id,-7)!='display') {
                  $val=htmlEncode(htmlEncodeJson($val));
                } else {
                  $val=htmlEncodeJson($val);
                }
                echo '"' . htmlEncode($id) . '":"' . $val . '"';
                if ($id=='idPe') {$idPe=$val;}
              }
              $collapsed = ($line['topid'] == $parentId)?$collapsedParent:"1";
              echo ',"collapsed":"'.$collapsed.'"';
              echo ', "dates":{';
              $maxWork = 0;
              if(isset($workDate[$key])){
                $lengthWorkDates = count($workDate[$key]['dates']);
                $count = 1;
                foreach ($workDate[$key]['dates'] as $date=>$workDates){
                  echo '"'.$date.'" : '.json_encode($workDates, 999);
                  // Sum work from each type's Globals directly
                  $work = 0;
                  foreach (array('planned','real','admin') as $wType) {
                    if (isset($workDates[$wType]['Globals']['work'])) {
                      $work += $workDates[$wType]['Globals']['work'];
                    }
                  }
                  $maxWork = ($maxWork < $work)?$work:$maxWork;
                  if($count < $lengthWorkDates)echo ',';
                  $count++;
                }
              }
              echo '}';
              echo ', "calendar":{';
              $idRes=(is_array($idResource))?'all':$idResource;
              $maxCapacity = 0;
              if(isset($resourceCalendar[$idRes])){
                $lengthCalendar = count($resourceCalendar[$idRes]);
                $count = 1;
                foreach ($resourceCalendar[$idRes] as $date=>$calendar){
                  $capacity = (isset($calendar['linecapacity']))?$calendar['linecapacity']:$calendar['capacity'];
                  $maxCapacity = ($maxCapacity < $capacity)?$capacity:$maxCapacity;
                  echo '"'.$date.'" : '.json_encode($calendar, 999);
                  if($count < $lengthCalendar)echo ',';
                  $count++;
                }
              }
              echo '}';
              echo ', "maxwork":"'.$maxWork.'"';
              echo ', "maxcapacity":"'.$maxCapacity.'"';
              if(is_array($idResource)){
                foreach ($idResource as $key=>$idRes){
                  $isResTeam = SqlList::getFieldFromId('Resource', $idRes, "isResourceTeam");
                  if($isResTeam)unset($idResource[$key]);
                }
              }else{
                $isResTeam = SqlList::getFieldFromId('Resource', $idResource, "isResourceTeam");
                if($isResTeam)$idResource=$resourceOfPool;
              }
              $nbResource = (is_array($idResource))?count($idResource):1;
              echo ', "nbresource":"'.$nbResource.'"';
              $resStartDate = '';
              $resEndDate = '';
              if(!is_array($idResource)){
                // Lookup or load ResourceAll from cache
                if (!isset($cachedResourceAll[$idResource])) {
                  $cachedResourceAll[$idResource] = new ResourceAll($idResource);
                }
                $res = $cachedResourceAll[$idResource];
                $resStartDate = $res->startDate;
                $resEndDate = $res->endDate;
              }
              echo ', "resourcestartdate":"'.$resStartDate.'"';
              echo ', "resourceenddate":"'.$resEndDate.'"';
              echo '}';
            }
            echo ' ] }';
          }else{
            echo i18n('noDataToDisplay');
          }
        }
  }
}

?>
