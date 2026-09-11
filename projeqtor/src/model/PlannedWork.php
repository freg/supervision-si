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

/**
 * ============================================================================
 * Project is the main object of the project managmement.
 * Almost all other objects are linked to a given project.
 */
require_once ('_securityCheck.php');

#[AllowDynamicProperties]
class PlannedWork extends GeneralWork {
  
  public $surbooked;
  
  public $surbookedWork;
  
  public $idLeave;
  
  public $isManual;
  
  public $_noHistory;
  
  public static $_planningInProgress;
  
  public static $_technicalErrors;
  
  // List of fields that will be exposed in general user interface
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%" ># ${id}</th>
    <th field="nameResource" formatter="thumbName22" width="35%" >${resourceName}</th>
    <th field="nameProject" width="35%" >${projectName}</th>
    <th field="rate" width="15%" formatter="percentFormatter">${rate}</th>
    <th field="idle" width="5%" formatter="booleanFormatter" >${idle}</th>
    ';
  
  /**
   * ==========================================================================
   * Constructor
   *
   * @param $id Int
   *          the id of the object in the database (null if not stored yet)
   * @return void
   */
  function __construct($id=NULL, $withoutDependentObjects=false) {
    parent::__construct($id, $withoutDependentObjects);
  }
  
  /**
   * ==========================================================================
   * Destructor
   *
   * @return void
   */
  function __destruct() {
    parent::__destruct();
  }
  
  // ============================================================================**********
  // GET STATIC DATA FUNCTIONS
  // ============================================================================**********
  
  /**
   * ==========================================================================
   * Return the specific layout
   *
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /**
   * ==========================================================================
   * Return the validation sript for some fields
   *
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    $colScript=parent::getValidationScript($colName);
    
    if ($colName=="idle") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      $colScript.='  if (this.checked) { ';
      $colScript.='    if (dijit.byId("PlanningElement_realEndDate").get("value")==null) {';
      $colScript.='      dijit.byId("PlanningElement_realEndDate").set("value", new Date); ';
      $colScript.='    }';
      $colScript.='  } else {';
      $colScript.='    dijit.byId("PlanningElement_realEndDate").set("value", null); ';
      // $colScript .= ' dijit.byId("PlanningElement_realDuration").set("value", null); ';
      $colScript.='  } ';
      $colScript.='  formChanged();';
      $colScript.='</script>';
    }
    return $colScript;
  }
  
  // ============================================================================**********
  // MISCELLANOUS FUNCTIONS
  // ============================================================================**********
  
  /**
   * Run planning calculation for project, starting at start date
   *
   * @static
   * @param string $projectId
   *          id of project to plan
   * @param string $startDate
   *          start date for planning
   * @return string result
   */
  
  // ================================================================================================================================
  // PLAN
  // ================================================================================================================================
  public static function plan($projectIdArray, $startDate, $withCriticalPath=1, $infinitecapacity=false, $simulation=false, $criticalLike=false, $planRefType=null, $planRefId=null) {
    global $strictDependency, $workUnit, $hoursPerDay, $hour, $halfHour, $daysPerWeek, $withProjectRepartition, $globalMaxDate, $globalMinDate;
    global $arrayPlannedWork, $arrayRealWork, $arrayAssignment, $arrayPlanningElement;
    global $listPlan, $fullListPlan, $resources, $topList, $reserved, $arrayNotPlanned, $arrayWarning;
    global $cronnedScript, $listProjectsType, $listProjectsDelay, $inClauseStored, $infinitecapacityStored, $clauseToPurgePlannedWork;
    debugTraceLog("PLAN - start");
    self::$_technicalErrors=null;
    $arrayPlannedWork=array();
    $arrayRealWork=array();
    $arrayAssignment=array();
    $arrayPlanningElement=array();
    $listPlan=array();
    $fullListPlan=array();
    $resources=array();
    $topList=array();
    $reserved=array();
    $arrayNotPlanned=array();
    $arrayWarning=array();
    $inClauseStored=null;
    $clauseToPurgePlannedWork=null;
    $surbooked=null;
    $surbookedWork=null;
    $ass=null;
    $plan=null;
    $arrayPlannedWork=null;
    $changedAss=null;
    $left=null;
    $ress=null;
    self::$_surbookedWorkStored=array();
    
    $forceFDUR=false;
    $forceASAP=false;
    if ($criticalLike) $infinitecapacity=true;
    if ($simulation or $criticalLike) {
      $forceFDUR=true;
      $forceASAP=true;
    }
    $forceInit=$forceFDUR;
    $infiniteInit=$infinitecapacity;
    // $infinitecapacity=true;
    $paramWithCriticalPath=Parameter::getGlobalParameter('paramWithCriticalPath');
    if ($paramWithCriticalPath===false or $paramWithCriticalPath==='false' or $paramWithCriticalPath==='NO') {
      $withCriticalPath=0;
    }
    // --------------------
    // Increase default limits
    projeqtor_set_time_limit(1800);
    if (!is_array($projectIdArray) and $projectIdArray=='*') {
      projeqtor_set_memory_limit('1G');
    } else {
      projeqtor_set_memory_limit('512M');
    }
    
    if (!is_array($projectIdArray)) $projectIdArray=array($projectIdArray);
    // An id matching no project builds an empty Project, whose sub project list is
    // every root : one unknown id would widen the scope to the whole tree. A blank
    // is kept, it is the marker meaning all projects.
    $knownProjects=array();
    foreach ($projectIdArray as $projectId) {
      if (! pq_trim($projectId)) { $knownProjects[]=$projectId; continue; }
      $checkProj=new Project($projectId, true);
      if ($checkProj->id) { $knownProjects[]=$projectId; }
    }
    if (count($knownProjects)==0) { $knownProjects=array(" "); }
    $projectIdArray=$knownProjects;
    // Strict dependency means when B follows A (A->B), B cannot start same date as A ends, but only day after
    $strictDependency=(Parameter::getGlobalParameter('dependencyStrictMode')=='NO')?false:true;
    $projectNotStartBeforeValidatedDate=(Parameter::getGlobalParameter("notStartBeforeValidatedStartDate")=='YES')?true:false;
    $arrayStartProject=array();
    // -- Manage cache
    SqlElement::$_cachedQuery['Resource']=array();
    SqlElement::$_cachedQuery['ResourceAll']=array();
    SqlElement::$_cachedQuery['Project']=array();
    SqlElement::$_cachedQuery['Affectation']=array();
    SqlElement::$_cachedQuery['PlanningMode']=array();
    // PBER - Test : clear all DB cache - for test
    // SqlElement::$_cachedQuery=array();
    
    self::$_planningInProgress=true;
    Resource::resetCache();
    
    // Gets untis
    $workUnit=Work::getWorkUnit();
    $hoursPerDay=floatVal(Work::getHoursPerDay());
    $hour=round(1/$hoursPerDay, 10);
    $halfHour=round(1/$hoursPerDay/2, 10);
    
    // Gives limits to avoid planning too far
    $withProjectRepartition=true;
    $result="";
    $startTime=time();
    $startMicroTime=microtime(true);
    $startOperation=date('Y-m-d H:i:s');
    $maxYears=5;
    $paramMaxYear=Parameter::getGlobalParameter('maxYearsPlanning');
    if ($paramMaxYear) $maxYears=$paramMaxYear;
    $globalMaxDate=date('Y')+$maxYears . "-12-31"; // Don't try to plan after Dec-31 of current year + 3
    $globalMinDate=date('Y')-1 . "-01-01"; // Don't try to plan before Jan-01 of current year -1
    
    // Work arrays
    $arrayPlannedWork=array();
    $arrayRealWork=array();
    $arrayAssignment=array();
    $arrayPlanningElement=array();
    
    // -- Controls (check that current user can run planning)
    $accessRightRead=securityGetAccessRight('menuActivity', 'read');
    $allProjects=false;
    if (count($projectIdArray)==1 and !pq_trim($projectIdArray[0])) $allProjects=true;
    if ($accessRightRead=='ALL' and $allProjects and !$cronnedScript) {
      $listProj=pq_explode(',', getVisibleProjectsList());
      // ticket #5659
      // if (count($listProj)-1 > Parameter::getGlobalParameter('maxProjectsToDisplay')) {
      // $result=i18n('selectProjectToPlan');
      // $result .= '<input type="hidden" id="lastPlanStatus" value="INVALID" />';
      // echo '<div class="messageINVALID" >' . $result . '</div>';
      // return $result;
      // }
    }
    
    // Define number of days per week depending on open days
    $daysPerWeek=7;
    if (Parameter::getGlobalParameter('OpenDaySunday')=='offDays') $daysPerWeek--;
    if (Parameter::getGlobalParameter('OpenDayMonday')=='offDays') $daysPerWeek--;
    if (Parameter::getGlobalParameter('OpenDayTuesday')=='offDays') $daysPerWeek;
    if (Parameter::getGlobalParameter('OpenDayWednesday')=='offDays') $daysPerWeek--;
    if (Parameter::getGlobalParameter('OpenDayThursday')=='offDays') $daysPerWeek--;
    if (Parameter::getGlobalParameter('OpenDayFriday')=='offDays') $daysPerWeek--;
    if (Parameter::getGlobalParameter('OpenDaySaturday')=='offDays') $daysPerWeek--;
    
    // -- Build in list to get a where clause : "idProject in ( ... )"
    $inClause="(";
    $pmCode='';
    if ($planRefType and $planRefId) {
      $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$planRefType, 'refId'=>$planRefId));
      $pm=new PlanningMode($pe->idPlanningMode);
      $pmCode=$pm->code;
    }
    $projectPlHist='';
    if ($planRefType and $planRefId and ($pmCode=='DDUR') and isset($pe)) { // or $pmCode=='CDUR' if single replan allowed
      $inClause.="(refType, refId) in ( ('$planRefType',$planRefId) ";
      $successors=$pe->getSuccessorItemsArray();
      foreach ($successors as $peSuc) {
        $inClause.=", ('$peSuc->refType',$peSuc->refId)";
      }
      $inClause.=" )";
    } else if ($cronnedScript) {
      $inClause.='1=1';
    } else {
      foreach ($projectIdArray as $projectId) {
        $proj=new Project($projectId, true);
        $inClause.=($inClause=="(")?'':' or ';
        $inClause.="idProject in " . transformListIntoInClause($proj->getRecursiveSubProjectsFlatList(true, true));
        $arrayAllProjects=$proj->getRecursiveSubProjectsFlatList(true, true);
        unset($arrayAllProjects['']);
        unset($arrayAllProjects[' ']);
        $projectPlHist.=(count($arrayAllProjects)>0)?implode('#', array_flip($arrayAllProjects)) . '#':'';
      }
    }
    $inClause.=" )";
    // $inClause.=" and " . getAccesRestrictionClause('Activity',false);
    // -- Remove Projects with Fixed Planning flag
    $inClause.=" and idProject not in " . Project::getFixedProjectList();
    $user=getSessionUser();
    if (!$cronnedScript) $inClause.=" and idProject in " . transformListIntoInClause($user->getListOfPlannableProjects());
    // Remove activities with fixed flag
    $pe=new PlanningElement();
    $peTable=$pe->getDatabaseTableName();
    $clauseToResetQuickPlan=$inClause;
    $inClause.=" and (refType, refId) not in (select refType, refId from $peTable peFixed where fixPlanning=1) ";
    // Do not plan "Manual Planning" activities
    $inClause.=" and (refType, refId) not in (select refType, refId from $peTable peFixed where idPlanningMode=23) ";
    // Try and merge the two last conditions
    // $inClause.=" and (refType, refId) not in (select refType, refId from $peTable peFixed where peFixed.fixPlanning=1 or peFixed.idPlanningMode=23) ";
    // -- Purge existing planned work
    $planW=new PlannedWork();
    // if (!$simulation) $planW->purge($inClause); PBER #10281 : move just before insert pw
    $inClauseStored=$inClause;
    $pwTable=$planW->getDatabaseTableName();
    // PBER #11946 Perfs
    $clauseToPurgePlannedWork=$clauseToResetQuickPlan
    // PBER #11946 Perfs - V1
    . " and not exists (select 1 from $peTable peFixed where peFixed.refType=$pwTable.refType and peFixed.refId=$pwTable.refId and (peFixed.fixPlanning=1 or peFixed.idPlanningMode=23)) ";
    // PBER #11946 Perfs - V2
//     . " and not exists (select 1 from $peTable peFixed where (peFixed.fixPlanning=1 or peFixed.idPlanningMode=23)"
//     . " and (peFixed.refType is null or peFixed.refType=$pwTable.refType)"
//     . " and (peFixed.refId is null or peFixed.refId=$pwTable.refId)) ";
    
    //$clauseToPurgePlannedWork=$inClause; // PBER #11946 Perfs
    // -- #697 : moved the administrative project clause after the purge
    // -- Remove administrative projects
    $inClause.=" and idProject not in " . Project::getAdminitrativeProjectList();
    $inClause.=" and idle=0";
    // -- Get the list of all PlanningElements to plan (includes Activity, Projects, Meetings, Test Sessions)
    // $pe=new PlanningElement();
    $clause=$inClause;
    $order="wbsSortable asc";
    $list=$pe->getSqlElementsFromCriteria(null, false, $clause, $order, true);
    if (count($list)==0) {
      $result=i18n('planEmpty');
      $result.='<input type="hidden" id="lastPlanStatus" value="INCOMPLETE" />';
      echo '<div class="messageINCOMPLETE" >' . $result . '</div>';
      return $result;
    }
    // $templateProjects=Project::getTemplateList();
    $fullListPlan=PlanningElement::initializeFullList($list, ($forceASAP or ($planRefType&&$planRefId)));
    $listProjectsPriority=$fullListPlan['_listProjectsPriority'];
    $listProjectsType=$fullListPlan['_listProjectsType'];
    $listProjectsOrder=$fullListPlan['_listProjectsOrder'];
    $listProjectsDelay=array();
    $listPoolExtraCapacity=array();
    unset($fullListPlan['_listProjectsPriority']);
    unset($fullListPlan['_listProjectsType']);
    unset($fullListPlan['_listProjectsOrder']);
    if ($simulation or $criticalLike) CriticalResourceScenarioProject::getScenarioProjectInfo($listProjectsType, $listProjectsDelay);
    if ($simulation or $criticalLike) CriticalResourceScenarioPool::getScenarioPoolInfo($listPoolExtraCapacity, $listPoolExtraCapacityDate);
    $listPlan=self::sortPlanningElements($fullListPlan, $listProjectsPriority, $listProjectsType, $listProjectsDelay, $listProjectsOrder);
    $resources=array();
    $a=new Assignment();
    $topList=array();
    $reserved=array();
    self::storeReservedForRecurring();
    $arrayNotPlanned=array();
    $arrayWarning=array();
    $uniqueResourceAssignment=null;
    if ($projectNotStartBeforeValidatedDate) {
      foreach ($listPlan as $plan) {
        if ($plan->refType=='Project') {
          $arrayStartProject[$plan->refId]=$plan->validatedStartDate;
        }
      }
    }
    foreach ($listProjectsDelay as $idProj=>$delay) {
      if (isset($arrayStartProject[$idProj])) {
        $arrayStartProject[$idProj]=self::shiftValidatedDate($arrayStartProject[$idProj], $delay);
      } else {
        $arrayStartProject[$idProj]=self::shiftValidatedDate($startDate, $delay);
      }
    }
    // -- Treat each PlanningElement ---------------------------------------------------------------------------------------------------
    $startDateGlobal=$startDate;
    $infinitecapacityStored=$infinitecapacity;
    foreach ($listPlan as $plan) {
      if (!$plan->id) {
        continue;
      }
      if ($plan->plannedStartDate=='0000-00-00') $plan->plannedStartDate=null;
      if (isset($fullListPlan['#' . $plan->id])) $plan=$fullListPlan['#' . $plan->id];
      // -- Determine planning profile
      if ($plan->idle) {
        $plan->_noPlan=true;
        $fullListPlan=self::storeListPlan($fullListPlan, $plan);
        continue;
      }
      if (property_exists($plan, '_profile') and $plan->_profile=='FIXED') {
        if ($plan->plannedStartDate==null or $plan->plannedEndDate==null) $plan->_noPlan=false;
        else $fullListPlan=self::storeListPlan($fullListPlan, $plan); // PBER call storeListPlan to update parent dates
      }
      if (isset($plan->_noPlan) and $plan->_noPlan) {
        continue;
      }
      // Scenario for Critical Resource
      $typeProject=$listProjectsType[$plan->idProject]??'';
      $delayProject=$listProjectsDelay[$plan->idProject]??null;
      $infinitecapacity=$infinitecapacityStored;
      $noSurbooking=false;
      $firstPlannedWork=null;
      if ($typeProject=='TMP' or $typeProject=='PRP') {
        // if ($simulation) continue;
        $infinitecapacity=true;
        $noSurbooking=true;
      }
      // Commented part : manual planning tasks were removed in the where clause
      // if ($plan->idPlanningMode==23) { // manual planning
      // $plan->_noPlan=true;
      // $fullListPlan=self::storeListPlan($fullListPlan,$plan);
      // continue;
      // }
      $profile=$plan->_profile;
      $startDate=$startDateGlobal;
      if (($profile=='DDUR') and $plan->validatedStartDate) {
        $startDate=$plan->validatedStartDate;
      }
      if ($profile=='CDUR') {
        $infinitecapacity=true;
        $noSurbooking=true;
        if ($plan->realStartDate and $plan->realStartDate<$plan->validatedStartDate) {
          if ($plan->realStartDate>$startDate) {
            $startDate=$plan->realStartDate;
          }
        } else if ($plan->validatedStartDate and $plan->validatedStartDate>$startDate) {
          $startDate=$plan->validatedStartDate;
        }
      }
      if ($projectNotStartBeforeValidatedDate and $plan->refType!='Project' and isset($arrayStartProject[$plan->idProject]) and pq_trim($arrayStartProject[$plan->idProject])!='') {
        if ($arrayStartProject[$plan->idProject]>$startDate) $startDate=$arrayStartProject[$plan->idProject];
      }
      $startPlan=$startDate;
      $startFraction=0;
      $endPlan=null;
      $step=1;
      $realProfile=$profile; // Store the real profile for START and STARR (Start Required), that is set to ASAP but should respect Validated Start Date, even with E-E dependency
      if ($profile=='ASAP' and $plan->assignedWork==0 and $plan->leftWork==0 and $plan->validatedDuration>0) {
        $profile='FDUR';
      }
      if ($profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART') { // Regular planning
        $startPlan=self::shiftValidatedDate($plan->validatedStartDate, $delayProject);
        $endPlan=self::shiftValidatedDate($plan->validatedEndDate, $delayProject);
        $step=1;
      } else if ($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR') { // Fixed duration
        // #V5.1.0 : removed this option
        // This leads to issue when saving validate dates : it fixed start, which may not be expected
        // If one want Fixed duration with fixed start, use regular beetween dates, or use milestone to define start
        // if ($plan->validatedStartDate) {
        // $startPlan=$plan->validatedStartDate;
        // }
        if (isset($plan->isGlobal) and $plan->isGlobal and count($plan->_directPredecessorList)==0) {
          if ($plan->plannedEndDate>$startDate and !$plan->realEndDate) {
            $startPlan=$plan->plannedEndDate;
          } else if (!$plan->plannedEndDate and self::shiftValidatedDate($plan->validatedEndDate, $delayProject)>$startDate) {
            $startPlan=self::shiftValidatedDate($plan->validatedEndDate, $delayProject);
          }
        } else if (count($plan->_directPredecessorList)==0 and self::shiftValidatedDate($plan->validatedStartDate, $delayProject)>$startDate and !$plan->realStartDate and $plan->validatedStartDate) {
          $startPlan=self::shiftValidatedDate($plan->validatedStartDate, $delayProject);
        }
        $step=1;
      } else if ($profile=='ASAP' or $profile=='GROUP') { // As soon as possible
        // $startPlan=$plan->validatedStartDate;
        $startPlan=$startDate; // V4.5.0 : if validated is fixed, must not be concidered as "Must not start before"
        $endPlan=null;
        $step=1;
      } else if ($profile=='ALAP') { // As late as possible (before end date)
        $startPlan=self::shiftValidatedDate($plan->validatedEndDate, $delayProject);
        $endPlan=$startDate;
        $step=-1;
      } else if ($profile=='FLOAT') { // Floating milestone
        if (count($plan->_predecessorListWithParent)==0 and self::shiftValidatedDate($plan->validatedEndDate, $delayProject)>$startDate and !$plan->realEndDate) $startPlan=self::shiftValidatedDate($plan->validatedEndDate, $delayProject);
        else $startPlan=$startDate;
        $endPlan=null;
        $step=1;
      } else if ($profile=='FIXED') { // Fixed milestone
        if ($plan->refType=='Milestone') {
          $startPlan=self::shiftValidatedDate($plan->plannedEndDate??$plan->validatedEndDate, $delayProject);
          $plan->plannedStartDate=$startPlan;
          $plan->plannedEndDate=$startPlan;
          $fullListPlan=self::storeListPlan($fullListPlan, $plan);
        } else {
          $startPlan=self::shiftValidatedDate($plan->validatedStartDate, $delayProject);
          // $startFraction=$plan->validatedStartFraction; // TODO : implement control of time on meeting
        }
        $endPlan=self::shiftValidatedDate($plan->validatedEndDate, $delayProject);
        $step=1;
      } else if ($profile=='START' or $profile=='STARR') { // Start not before validated date
        $startPlan=self::shiftValidatedDate($plan->validatedStartDate, $delayProject);
        $endPlan=null;
        $step=1;
        $profile='ASAP'; // Once start is set, treat as ASAP mode (as soon as possible)
      } else if ($profile=='RECW') {
        $plan->assignedWork=$plan->realWork;
        $plan->leftWork=0;
        $plan->plannedWork=$plan->realWork;
        $startPlan=null;
        if (isset($reserved['W'][$plan->id]['start']) and $reserved['W'][$plan->id]['start']) {
          $startPlan=$reserved['W'][$plan->id]['start'];
        }
        if (isset($reserved['W'][$plan->id]['end']) and $reserved['W'][$plan->id]['end']) {
          $endPlan=$reserved['W'][$plan->id]['end'];
        }
        if (!$endPlan or !$startPlan) {
          $idPeProj=null;
          $curPe=$plan;
          while (!$idPeProj) {
            if (!$curPe->topId or !isset($fullListPlan['#' . $curPe->topId])) {
              $idPeProj=-1;
              break;
            }
            $topPe=$fullListPlan['#' . $curPe->topId];
            if ($topPe->refType=='Project') {
              $idPeProj=$topPe->id; // Will exit loop, after setting curPe
            }
            $curPe=$topPe;
          }
          if ($idPeProj>0) {
            if (!$endPlan) {
              if ($curPe->plannedEndDate) $endPlan=$curPe->plannedEndDate;
              else $endPlan=self::shiftValidatedDate($curPe->validatedEndDate, $delayProject);
            }
            if (!$startPlan) {
              if ($curPe->plannedStartDate) $startPlan=$curPe->plannedStartDate;
              else $startPlan=self::shiftValidatedDate($curPe->validatedStartDate, $delayProject);
            }
          }
        }
        $plan->plannedStartDate=$startPlan;
        $plan->plannedEndDate=$endPlan;
        $artype=pq_substr($plan->_profile, -1);
        if ((!$endPlan or !$startPlan) and isset($reseved[$artype][$plan->id]['assignments'])) {
          foreach ($reseved[$artype][$plan->id]['assignments'] as $idAssignment) {
            $dates='';
            if (!isset($reserved['W'][$plan->id]['start']) or !$reserved['W'][$plan->id]['start']) {
              $dates="'" . i18n('colStartDate') . "'";
            }
            if (!isset($reserved['W'][$plan->id]['end']) or !$reserved['W'][$plan->id]['end']) {
              if ($dates) $dates.=' ' . pq_mb_strtolower(i18n('AND')) . ' ';
              $dates.="'" . i18n('colEndDate') . "'";
            }
            $arrayNotPlanned[$idAssignment]=i18n('planImpossibleForREC', array($dates));
          }
          $fullListPlan=self::storeListPlan($fullListPlan, $plan);
        }
      } else if (!$plan->elementary) {
        $parentMode=Parameter::getGlobalParameter('planningModeForParent');
        if ($parentMode and $parentMode!='' and $plan->leftWork>0) {
          $profile=$parentMode;
          $realProfile='REGUL';
        } else {
          $profile='REGUL';
          $realProfile='REGUL';
        }
        $plan->_storedValidatedEndDate=$plan->validatedEndDate;
        $plan->validatedStartDate=$plan->plannedStartDate;
        $plan->validatedEndDate=$plan->plannedEndDate;
        if ($plan->plannedStartDate=='0000-00-00') $plan->plannedStartDate=$startDate;
        if ($plan->plannedEndDate=='0000-00-00') $plan->plannedEndDate=$startDate;
        $startPlan=$plan->plannedStartDate;
        $endPlan=$plan->plannedEndDate;
        $plan->validateDuration=workDayDiffDates($startPlan, $endPlan);
        $step=1;
      } else {
        $profile=='ASAP'; // Default is ASAP
        $startPlan=$startDate;
        $endPlan=null;
        $step=1;
      }
      // -- Take into accound predecessors
      $precList=$plan->_predecessorListWithParent;
      if ($profile=='CDUR' and $plan->inheritedStartDate and !$plan->validatedStartDate and $plan->realWork==0 and ($plan->assignedWork>0 or $plan->leftWork>0)) {
        // Do not change inheritedEndDate
      } else {
        $plan->inheritedStartDate=null;
      }
      $isPlanGlobal=(isset($plan->isGlobal) and $plan->isGlobal)?true:false;
      foreach ($precList as $precId=>$precValArray) { // $precValArray = array(dependency delay,dependency type)
        $precVal=$precValArray['delay'];
        $precTyp=$precValArray['type'];
        if (!isset($fullListPlan[$precId])) continue;
        $prec=$fullListPlan[$precId];
        $precEnd=$prec->plannedEndDate;
        $precStart=$prec->plannedStartDate;
        $precFraction=$prec->plannedEndFraction;
        if ($prec->realEndDate and $prec->refType!='Milestone') {
          $precEnd=$prec->realEndDate;
          $precFraction=1;
        }
        if ($prec->realStartDate) {
          $precStart=$prec->realStartDate;
        }
        $isPrecGlobal=(isset($prec->isGlobal) and $prec->isGlobal)?true:false;
        if ($strictDependency or $precVal!=0 or $precFraction==1) {
          if (($prec->refType!='Milestone' and $plan->refType!='Milestone' and !$isPlanGlobal and !$isPrecGlobal) or $precFraction==1 or ($strictDependency and ($plan->refType=='Milestone' or $isPlanGlobal) and ($prec->refType!='Milestone' and !$isPrecGlobal))) {
            $startPossible=addWorkDaysToDate($precEnd, ($precVal>=0 and $precTyp!='E-E')?2+$precVal:1+$precVal, $plan->idProject);
          } else {
            if ($prec->refType=='Milestone' or $isPlanGlobal) {
              $startPossible=addWorkDaysToDate($precEnd, ($precVal>=0)?1+$precVal:$precVal, $plan->idProject);
            } else {
              $startPossible=addWorkDaysToDate($precEnd, 1+$precVal, $plan->idProject);
            }
          }
          $startPossibleFraction=0;
        } else {
          $startPossible=$precEnd;
          $startPossibleFraction=$precFraction;
        }
        if ($precTyp=='S-S') {
          if ($precVal>0) {
            $startPossible=addWorkDaysToDate($precStart, $precVal+1, $plan->idProject);
          } else if ($precVal<0) {
            $startPossible=addWorkDaysToDate($precStart, $precVal, $plan->idProject);
          } else {
            $startPossible=$precStart;
          }
          $startPossibleFraction=0;
        }
        if ($precTyp=='E-E' and ($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR')) {
          $startFromPred=addWorkDaysToDate($precEnd, $plan->validatedDuration*(-1)+1+$precVal, $plan->idProject);
          if (!$plan->realStartDate or $startFromPred<$plan->realStartDate) {
            $startPlan=$startFromPred;
          }
        } else if ($precTyp=='E-E' and ($profile=='ASAP' or $profile=='GROUP')) {
          // $profile='ALAP';
          $step=-1;
          $endPlan=$startPlan;
          if ($precVal>0) {
            $startPlan=addWorkDaysToDate($precEnd, $precVal+1, $plan->idProject);
          } else if ($precVal<0) {
            $startPlan=addWorkDaysToDate($precEnd, $precVal, $plan->idProject);
          } else {
            $startPlan=$precEnd;
          }
        } else if ($precTyp=='E-E' and $profile=='RECW') {
          // Nothing, start / End already set
        } else if ($profile=='ALAP') {
          if ($startPossible>=$endPlan) {
            $endPlan=$startPossible;
            if ($startPlan<$endPlan) {
              $startPlan=$endPlan;
              $endPlan=null;
              $step=1;
              $profile='ASAP';
            }
          }
        } else if ($startPossible>=$startPlan or ($startPossible==$startPlan and $startPossibleFraction>$startFraction)) { // #77
          if ($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR') {
            if (!pq_trim($plan->realStartDate) or $startPossible<$plan->realStartDate) {
              $startPlan=$startPossible;
              $startFraction=$startPossibleFraction;
            }
          } else {
            $startPlan=$startPossible;
            $startFraction=$startPossibleFraction;
          }
        }
        if ($startPossible and (!$plan->inheritedStartDate or $plan->inheritedStartDate<$startPossible)) $plan->inheritedStartDate=$startPossible;
      }
      if (($profile=='DDUR') and $plan->validatedStartDate and $startPlan<$plan->validatedStartDate) $startPlan=$plan->validatedStartDate;
      // if (!$startPlan) $startPlan=date('Y-m-d');
      if ($startPlan and isOffDay($startPlan, null, $plan->idProject)) {
        while (isOffDay($startPlan, null, $plan->idProject)) {
          $startPlan=addDaysToDate($startPlan, 1);
        }
      }
      if ($plan->refType=='Milestone' or $isPlanGlobal) {
        if ($profile!='FIXED') {
          if ($strictDependency) {
            $plan->plannedStartDate=addWorkDaysToDate($startPlan, 1, $plan->idProject);
          } else if ($startFraction==1) {
            if (count($precList)>0) {
              $plan->plannedStartDate=addWorkDaysToDate($startPlan, 2, $plan->idProject);
            } else {
              $plan->plannedStartDate=addWorkDaysToDate($startPlan, 1, $plan->idProject);
            }
            $plan->plannedStartFraction=0;
          } else {
            $plan->plannedStartDate=$startPlan;
            $plan->plannedStartFraction=$startFraction;
          }
          if ($plan->realEndDate) $plan->realStartDate=$plan->realEndDate;
          if ($plan->realStartDate) {
            $plan->plannedStartDate=$plan->realStartDate;
            $plan->plannedStartFraction=0;
            $plan->plannedEndFraction=0;
          }
          $plan->plannedEndDate=$plan->plannedStartDate;
          $plan->plannedEndFraction=$plan->plannedStartFraction;
          $plan->plannedDuration=0;
          // $plan->save();
          $fullListPlan=self::storeListPlan($fullListPlan, $plan);
        }
        if ($profile=='FIXED') { // We are on Milestone ;)
          $plan->plannedEndDate=self::shiftValidatedDate($plan->plannedEndDate??$plan->validatedEndDate, $delayProject);
          $plan->plannedStartDate=$plan->plannedEndDate;
          $plan->plannedEndFraction=$plan->plannedStartFraction;
          $plan->plannedDuration=0;
          if ($plan->realEndDate) $plan->realStartDate=$plan->realEndDate;
          if ($plan->realStartDate) {
            // $plan->plannedStartDate=$plan->realStartDate;
            // $plan->plannedEndDate=$plan->realEndDate;
            // $plan->plannedStartFraction=0;
            // $plan->plannedEndFraction=0;
          }
          // $plan->save();
          $fullListPlan=self::storeListPlan($fullListPlan, $plan);
        }
      } else {
        if (!$plan->realStartDate and $profile!='RECW') {
          // $plan->plannedStartDate=($plan->leftWork>0)?$plan->plannedStartDate:$startPlan;
          if ($plan->plannedWork==0 and $plan->elementary==1) {
            if ($plan->validatedStartDate and $plan->validatedStartDate>$startPlan) {
              $plan->plannedStartDate=$plan->validatedStartDate;
            } else if ($plan->initialStartDate and $plan->initialStartDate>$startPlan) {
              $plan->plannedStartDate=$plan->initialStartDate;
            } else {
              // V5.1.0 : should never start before startplan
              // $plan->plannedStartDate=date('Y-m-d');
              $plan->plannedStartDate=$startPlan;
            }
          }
        }
        if (!$plan->realEndDate and $profile!='RECW') {
          // $plan->plannedEndDate=($plan->plannedWork==0)?$plan->validatedEndDate:$plan->plannedEndDate;
          if ($plan->plannedWork==0 and $plan->elementary==1) {
            if ($plan->validatedEndDate and $plan->validatedEndDate>$startPlan) {
              $plan->plannedEndDate=$plan->validatedEndDate;
            } else if ($plan->initialEndDate and $plan->initialEndDate>$startPlan) {
              $plan->plannedEndDate=$plan->initialEndDate;
            } else {
              // V5.1.0 : should never start before startplan
              // $plan->plannedEndDate=date('Y-m-d');
              $plan->plannedEndDate=$startPlan;
            }
          }
        }
        if (($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR') and $realProfile!='REGUL') {
          if (!$plan->realStartDate or $plan->realStartDate>$startPlan) {
            if ($plan->elementary) {
              if ($plan->plannedWork==0 or (property_exists($plan, 'isManualProgress') and $plan->isManualProgress)) $plan->plannedStartDate=$startPlan;
              $endPlan=addWorkDaysToDate($startPlan, $plan->validatedDuration, $plan->idProject);
            }
          } else {
            $endPlan=addWorkDaysToDate($plan->realStartDate, $plan->validatedDuration, $plan->idProject);
          }
          if (!$plan->realEndDate) {
            $plan->plannedEndDate=$endPlan;
          }
          $fullListPlan=self::storeListPlan($fullListPlan, $plan);
          // $plan->save();
        }
        if ($profile=='ASAP' and $plan->assignedWork==0 and $plan->realWork==0 and $plan->leftWork==0 and $plan->validatedWork>0) {
          if (!$plan->realStartDate) {
            if ($plan->elementary) {
              $plan->plannedStartDate=$startPlan;
              $endPlan=addWorkDaysToDate($startPlan, $plan->validatedWork, $plan->idProject);
            }
          } else {
            $endPlan=addWorkDaysToDate($plan->realStartDate, $plan->validatedWork, $plan->idProject);
          }
          if (!$plan->realEndDate) {
            $plan->plannedEndDate=$endPlan;
          }
          $fullListPlan=self::storeListPlan($fullListPlan, $plan);
          // $plan->save();
        }
        
        // get list of top project to chek limit on each project
        if ($withProjectRepartition) {
          $proj=new Project($plan->idProject, true);
          if ($infinitecapacity or $profile=='CDUR') $listTopProjects=array($plan->idProject);
          else $listTopProjects=$proj->getTopProjectList(true);
        }
        $crit=array("refType"=>$plan->refType, "refId"=>$plan->refId, "idle"=>"0");
        $listAss=$a->getSqlElementsFromCriteria($crit, false, null, 'proportional', false, true);
        $groupAss=array();
        // $groupMaxLeft=0;
        // $groupMinLeft=99999;
        if ($profile=='GROUP') {
          if (count($listAss)<2) {
            $profile='ASAP';
          } else {
            foreach ($listAss as $assTmp) {
              if ($assTmp->isResourceTeam) {
                $profile='ASAP';
                $arrayWarning[$assTmp->id]=i18n("warningPlanningModePool", array(i18n("PlanningModeGROUP")));
                break;
              }
            }
          }
        }
        if ($profile=='GROUP') {
          $resourceOfTheGroup=array();
          foreach ($listAss as $ass) {
            $r=new Resource($ass->idResource, true);
            $resourceOfTheGroup[$ass->idResource]=array('resObj'=>$r, 'capacity'=>array());
            $capacity=($r->capacity)?$r->capacity:1;
            if (isset($resources[$ass->idResource])) {
              $ress=$resources[$ass->idResource];
            } else {
              $ress=$r->getWork($startDate, $withProjectRepartition, $simulation);
              $resources[$ass->idResource]=$ress;
            }
            $assRate=1;
            if ($ass->rate) {
              $assRate=$ass->rate/100;
            }
            // if ($ass->leftWork>$groupMaxLeft) $groupMaxLeft=$ass->leftWork;
            // if ($ass->leftWork<$groupMinLeft) $groupMinLeft=$ass->leftWork;
            if (!isset($groupAss[$ass->idResource])) {
              $groupAss[$ass->idResource]=array();
              $groupAss[$ass->idResource]['leftWork']=$ass->leftWork;
              // $groupAss[$ass->idResource]['TogetherWork']=array();
              $groupAss[$ass->idResource]['capacity']=$capacity;
              $groupAss[$ass->idResource]['ResourceWork']=$ress;
              $groupAss[$ass->idResource]['assRate']=$assRate;
              $groupAss[$ass->idResource]['calendar']=$r->idCalendarDefinition;
            } else {
              $groupAss[$ass->idResource]['leftWork']+=$ass->leftWork;
              $assRate=$groupAss[$ass->idResource]['assRate']+$assRate;
              if ($assRate>1) $assRate=1;
              $groupAss[$ass->idResource]['assRate']=$assRate;
              $groupAss[$ass->idResource]['calendar']=$r->idCalendarDefinition;
            }
            if ($withProjectRepartition) {
              foreach ($listTopProjects as $idProject) {
                $projKey='Project#' . $idProject;
                if (!pq_array_key_exists($projKey, $groupAss[$ass->idResource]['ResourceWork'])) {
                  $groupAss[$ass->idResource]['ResourceWork'][$projKey]=array();
                }
                if (!pq_array_key_exists('rate', $groupAss[$ass->idResource]['ResourceWork'][$projKey])) {
                  $groupAss[$ass->idResource]['ResourceWork'][$projKey]['rate']=$r->getAffectationRate($idProject, $listTopProjects, $infinitecapacity); // Ticket #4549
                }
                $groupAss[$ass->idResource]['ResourceWork']['init' . $projKey]=$groupAss[$ass->idResource]['ResourceWork'][$projKey];
              }
            }
          }
        }
        $plan->notPlannedWork=0;
        $plan->surbooked=0;
        $plan->surbookedWork=0;
        if ($plan->indivisibility==1 and ($profile=='RECW' or $profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR' or $profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART')) {
          $plan->indivisibility=0; // Cannot plan with indivisibility on some modes
        }
        if ($plan->indivisibility==1 and $profile=='GROUP') {
          $stockPlan=clone ($plan);
          $stockPlanStart=$plan->plannedStartDate;
          $stockResources=$resources;
          $stockPlannedWork=$arrayPlannedWork;
          $countRejectedIndivisibility=0;
          $countRejectedIndivisibilityMax=1000;
          $stockGroupAss=$groupAss;
        }
        $lastPlanDate=null; // Limit to plan for ASAP
        if ($profile=='ASAP' and $forceASAP) {
          $lastPlanDate=$plan->getExpectedEndDate($listPlan, $delayProject);
        }
        $restartLoopAllAssignements=true;
        $forceFDUR=$forceInit;
        $infinitecapacity=$infiniteInit;
        if ($profile=='DDUR') { // or $profile=='CDUR'
          $forceFDUR=true;
          $infinitecapacity=true;
        }
        if ($profile=='CDUR') { // or $profile=='CDUR'
          // $forceFDUR=true;
          $infinitecapacity=true; // TODO better planning smoothening
        }
        $proportionalStart=null;
        $proportionalEnd=null;
        while ($restartLoopAllAssignements) {
          //$plan->plannedStartDate=null; // PBER #11631 - Removed as it sets the mess
          if ($plan->indivisibility==1 and $profile=='GROUP') {
            $plan=$stockPlan;
            $plan->plannedStartDate=$stockPlanStart;
            $resources=$stockResources;
            $arrayPlannedWork=$stockPlannedWork;
            $countRejectedIndivisibility++;
            $groupAss=$stockGroupAss;
            if ($countRejectedIndivisibility>$countRejectedIndivisibilityMax) {
              break;
            }
          }
          $restartLoopAllAssignements=false;
          // $idxAss=0;
          // List assignments of $plan : Search for assignment for "unique resource", if found, add virtual assignment for each resource to check
          $supportAssignments=array();
          $increment=0;
          foreach ($listAss as $keyAss=>$ass) {
            if ($ass->supportedAssignment) continue;
            if ($ass->uniqueResource) {
              if ($profile=='GROUP') $profile='ASAP';
              if ($uniqueResourceAssignment===null) $uniqueResourceAssignment=array();
              if (!isset($uniqueResourceAssignment[$ass->id])) $uniqueResourceAssignment[$ass->id]=array();
              if (!isset($resources[$ass->idResource])) {
                $r=new ResourceAll($ass->idResource, true);
                $resources[$ass->idResource]=$r->getWork($startDate, $withProjectRepartition, $simulation);
              }
              $uniqueResourceAss=$ass;
              $asel=new AssignmentSelection();
              $aselList=$asel->getSqlElementsFromCriteria(array('idAssignment'=>$ass->id));
              foreach ($aselList as $asel) {
                $cpAss=clone ($ass);
                $cpAss->idResource=$asel->idResource;
                $cpAss->isResourceTeam=0;
                $cpAss->uniqueResource=0;
                // $cpAss->_isUnique=$ass->idResource;
                // $cpAss->temp=true;
                $uniqueResourceAssignment[$ass->id][$asel->idResource]=array('select'=>$asel);
                $listAss=array_insert_before($listAss, $cpAss, $keyAss+$increment);
                $increment++;
              }
            }
          }
          foreach ($listAss as $keyAss=>$ass) {
            if ($ass->supportedAssignment) continue;
            $uniqueStart=null;
            $uniqueEnd=null;
            if (isset($uniqueResourceAssignment[$ass->id][$ass->idResource])) {
              // UNIQUE RESOURCE TO PLAN
              $resPool=$resources[$uniqueResourceAss->idResource];
              if (isset($resources[$uniqueResourceAss->idResource])) {
                $resPool=$resources[$uniqueResourceAss->idResource];
              } else {
                $rPool=new ResourceAll($uniqueResourceAss->idResource, true);
                $resPool=$rPool->getWork($startDate, $withProjectRepartition, $simulation);
              }
              foreach ($resPool['periods'] as $poolPeriod) {
                if (isset($poolPeriod['idResource'][$ass->idResource])) {
                  $uniqueStartTest=$poolPeriod['start'];
                  $uniqueEndTest=$poolPeriod['end'];
                  if (!$uniqueStart) $uniqueStart=$uniqueStartTest;
                  $uniqueEnd=$uniqueEndTest;
                }
              }
            } else if ($ass->uniqueResource) {
              // POOL : MUST SELECT UNIQUE
              $minEnd='2099-12-31';
              // Selection of resource that gives the soonest planning
              $selectedRes=null;
              foreach ($uniqueResourceAssignment[$ass->id] as $keyAssRes=>$assResSelect) {
                $testAss=$assResSelect['ass'];
                $testAssSelect=$assResSelect['select'];
                if ($testAssSelect->userSelected==1) {
                  if ($testAss->notPlannedWork==0 and isset($arrayNotPlanned[$ass->id])) unset($arrayNotPlanned[$ass->id]);
                  $selectedRes=$keyAssRes;
                  $minEnd='1900-01-01';
                } else if ($testAss->notPlannedWork>0) {
                  $uniqueResourceAssignment[$ass->id][$keyAssRes]['ass']->plannedEndDate=null;
                } else if ($testAss->plannedEndDate<$minEnd) {
                  $selectedRes=$keyAssRes;
                  $minEnd=$testAss->plannedEndDate;
                  if (isset($arrayNotPlanned[$ass->id])) unset($arrayNotPlanned[$ass->id]);
                } else if ($testAss->plannedEndDate==$minEnd) { // equality over date
                  if (isset($arrayNotPlanned[$ass->id])) unset($arrayNotPlanned[$ass->id]);
                  // Take the one with less planned work
                  $selectedWork=self::getPlannedWorkForResource($selectedRes, $startDate);
                  $currentWork=self::getPlannedWorkForResource($keyAssRes, $startDate);
                  if ($currentWork<$selectedWork) {
                    $selectedRes=$keyAssRes;
                    $minEnd=$testAss->plannedEndDate;
                  } else if ($currentWork==$selectedWork) { // equality over planned work
                    // Take the one with less left work to plan
                    $selectedWork=self::getLeftWorkForResource($selectedRes, $startDate);
                    $currentWork=self::getLeftWorkForResource($keyAssRes, $startDate);
                    if ($currentWork<$selectedWork) {
                      $selectedRes=$keyAssRes;
                      $minEnd=$testAss->plannedEndDate;
                    } else if ($currentWork==$selectedWork) { // equality over left work
                      // Take the one with smaller id
                      if ($keyAssRes<$selectedRes) {
                        $selectedRes=$keyAssRes;
                        $minEnd=$testAss->plannedEndDate;
                      }
                    }
                  }
                }
              }
              if ($selectedRes) {
                // $ress=$uniqueResourceAssignment[$ass->id][$selectedRes]['ress'];
                $plan=$uniqueResourceAssignment[$ass->id][$selectedRes]['plan'];
                $resources=$uniqueResourceAssignment[$ass->id][$selectedRes]['resources'];
                $arrayPlannedWork=$uniqueResourceAssignment[$ass->id][$selectedRes]['plannedWork'];
                $assSelected=$uniqueResourceAssignment[$ass->id][$selectedRes]['ass'];
                $ass->plannedStartDate=$assSelected->plannedStartDate;
                $ass->plannedEndDate=$assSelected->plannedEndDate;
                $assSelected->idResource=$ass->idResource;
                $uniqueResourceAssignment[$ass->id][$selectedRes]['SELECTED']='SELECTED';
                $changedAss=true;
                $assSelected->_noHistory=true; // Will only save planning data, so no history required
                $arrayAssignment[]=$assSelected;
                // Clean data that are not usefull any more
                // Attention, table $uniqueResourceAssignment will contain result for each uniqueResource assignement on plan to store assignmentselection data
                foreach ($uniqueResourceAssignment[$ass->id] as $keyAssRes=>$assResSelect) {
                  // unset($uniqueResourceAssignment[$ass->id][$keyAssRes]['ress']);
                  unset($uniqueResourceAssignment[$ass->id][$keyAssRes]['plan']);
                  unset($uniqueResourceAssignment[$ass->id][$keyAssRes]['resources']);
                  unset($uniqueResourceAssignment[$ass->id][$keyAssRes]['plannedWork']);
                  // unset($uniqueResourceAssignment[$ass->id][$keyAssRes]['ass']);
                }
                continue; // Do not treat current assignment, as it was already calculated for each resource, and selected as soonest
              } else { // Could not select resource, plan pool as usual
                // Nothing special to do : will continue to treat the assignment as usual
              }
            }
            if ($ass->notPlannedWork>0) {
              $ass->notPlannedWork=0;
              $changedAss=true;
            }
            if ($ass->surbooked!=0) {
              $ass->surbooked=0;
              $changedAss=true;
            }
            if ($profile=='GROUP' and $withProjectRepartition) {
              foreach ($listAss as $asstmp) {
                foreach ($listTopProjects as $idProject) {
                  $projKey='Project#' . $idProject;
                  $groupAss[$asstmp->idResource]['ResourceWork'][$projKey]=$groupAss[$asstmp->idResource]['ResourceWork']['init' . $projKey];
                }
              }
            }
            $changedAss=true;
            $ass->plannedStartDate=null;
            $ass->plannedEndDate=null;
            $r=new ResourceAll($ass->idResource, true);
            $capacity=($r->capacity)?$r->capacity:1;
            if (isset($resources[$ass->idResource])) {
              $ress=$resources[$ass->idResource];
            } else {
              $ress=$r->getWork($startDate, $withProjectRepartition, $simulation);
            }
            if ($ass->proportional) {
              if ($plan->elementary==0) {
                if (!$proportionalStart) $proportionalStart=$startPlan;
                if (!$proportionalEnd) $proportionalEnd=$endPlan;
              } else if (!$proportionalStart and !$proportionalEnd) { // PBER #11166
                if (isset($startPossible)) $proportionalStart=$startPossible; // $plan->plannedStartDate;
                else $proportionalStart=$startPlan;
                if ($plan->validatedDuration) {
                  if ($plan->realStartDate) $proportionalEnd=addWorkDaysToDate($plan->realStartDate, $plan->validatedDuration, $plan->idProject);
                  else $proportionalEnd=addWorkDaysToDate($proportionalStart, $plan->validatedDuration, $plan->idProject);
                } else
                  $proportionalEnd=$plan->plannedEndDate;
              }
              $ass->calculateProportional('planning', $plan, $r->idCalendarDefinition, $proportionalStart, $proportionalEnd);
              $plan->_hasProportional=true;
            }
            $ress['capacity']=$capacity;
            if ($startPlan>$startDate) {
              $currentDate=$startPlan;
            } else {
              $currentDate=$startDate;
              if ($step==-1) {
                if ($realProfile=='START' or $profile=='STARR') $currentDate=self::shiftValidatedDate($plan->validatedStartDate, $delayProject);
                $step=1;
              }
            }
            if ($profile=='GROUP') {
              foreach ($groupAss as $id=>$grp) {
                $groupAss[$id]['leftWorkTmp']=$groupAss[$id]['leftWork'];
              }
            }
            $assRate=1;
            if ($ass->rate) {
              $assRate=$ass->rate/100;
            }
            // Get data to limit to affectation on each project
            if ($withProjectRepartition) {
              foreach ($listTopProjects as $idProject) {
                $projKey='Project#' . $idProject;
                if (!pq_array_key_exists($projKey, $ress)) {
                  $ress[$projKey]=array();
                }
                if (!pq_array_key_exists('rate', $ress[$projKey])) {
                  $ress[$projKey]['rate']=$r->getAffectationRate($idProject, $listTopProjects, $infinitecapacity); // Ticket #4549
                }
              }
            }
            // $projRate=$ress['Project#' . $ass->idProject]['rate'];
            if ($ress['team']) {
              $capacityRate=$ass->capacity;
            } else {
              $capacityRate=round($assRate*$capacity, 2);
            }
            $keyElt=$ass->refType . '#' . $ass->refId;
            $left=$ass->leftWork;
            $regul=false;
            if ($profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART' or $profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR') {
              $endToTake=$endPlan;
              if ($profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART') {
                $tmpInc=0.1;
                if ($profile=='FULL') $tmpInc=1;
                if ($profile=='HALF') $tmpInc=0.5;
                if ($profile=='QUART') $tmpInc=0.25;
                for ($endToTake=$endPlan; $endToTake>=$currentDate; $endToTake=addDaysToDate($endToTake, -1)) {
                  if (isOffDay($endToTake, $r->idCalendarDefinition)) continue;
                  if (!isset($ress[$endToTake])) break;
                  if ($ress[$endToTake]+$tmpInc<$r->getCapacityPeriod($endToTake)) {
                    break;
                  }
                }
              }
              $delaiTh=workDayDiffDates($currentDate, $endToTake, $plan->idProject);
              $regulTh=0;
              if ($delaiTh and $delaiTh>0) {
                $regulTh=round($ass->leftWork/$delaiTh, 10);
              }
              $delai=0;
              $changeStartDate=true;
              for ($tmpDate=$currentDate; $tmpDate<=$endPlan; $tmpDate=addDaysToDate($tmpDate, 1)) {
                if (isOffDay($tmpDate, $r->idCalendarDefinition)) continue;
                if (isset($ress['real'][$keyElt][$tmpDate])) continue;
                if ($r->endDate and $r->endDate<$tmpDate) continue;
                if ($r->startDate and $r->startDate>$tmpDate) {
                  $currentDate=addDaysToDate($tmpDate, 1);
                  continue;
                }
                $tempCapacity=$capacityRate;
                if ($ass->proportional) $tempCapacity=$capacity;
                // if ($infinitecapacity) {
                // if ($ress['team']==1) { // PBER #8838 - Now $ress['real-'.$tmpDate] returns sum for all Resource of the Pool
                if ($ress['team']==1 or $infinitecapacity) { // PBER #8985 - If infinite capacity, $ress[$tmpDate] not deducted
                  // $tempCapacity=round($assRate*$r->getCapacityPeriod($currentDate),2);
                  // $tempCapacity-=$ress[$tmpDate];
                  // #8838 : why only if infinite capacity
                  if (isset($ress['real-' . $tmpDate])) {
                    $tmpLeftCapacity=$r->getCapacityPeriod($tmpDate)-$ress['real-' . $tmpDate];
                    if ($tmpLeftCapacity<$tempCapacity) $tempCapacity=$tmpLeftCapacity;
                  }
                }
                if (!$infinitecapacity and isset($ress[$tmpDate])) {
                  if ($ress['team']==1) {
                    $max=$r->getCapacityPeriod($currentDate);
                    if (($max-$ress[$tmpDate])<$tempCapacity) $tempCapacity=$max-$ress[$tmpDate];
                  } else {
                    $tempCapacity-=$ress[$tmpDate]-($r->getCapacityPeriod($endToTake)-$capacityRate);
                  }
                }
                if ($tempCapacity<0) $tempCapacity=0;
                // if ($tempCapacity>=$regulTh or $regulTh==0 or $plan->elementary==0 or ($infinitecapacity and $tempCapacity>0)) {
                if ($tempCapacity>=$regulTh or $regulTh==0 or ($infinitecapacity and $tempCapacity>0)) { // PBER #9439
                  $delai+=1;
                } else {
                  $delai+=floor($tempCapacity/$regulTh*10)/10;
                }
                if ($tempCapacity==0 and $changeStartDate) $currentDate=addDaysToDate($tmpDate, 1);
                else $changeStartDate=false;
              }
              if ($delai and $delai>0) {
                // $regul=round(($ass->leftWork/$delai)+0.000005,5);
                $regul=round(($ass->leftWork/$delai), 10);
                $regulDone=0;
                $interval=0;
                $regulTarget=0;
              }
            }
            if ($profile=='RECW') {
              $ass->assignedWork=$ass->realWork;
              $ass->leftWork=0;
              $ass->plannedWork=$ass->realWork;
            }
            $cptThresholdReject=0;
            $cptThresholdRejectMax=100; // will end try to plan if
            if ($plan->indivisibility==1 and $profile!='GROUP') {
              $stockPlan=$plan;
              $stockPlanStart=$plan->plannedStartDate;
              $stockAss=$ass;
              $stockLeft=$left;
              $stockResources=$resources;
              $stockRess=$ress;
              $stockPlannedWork=$arrayPlannedWork;
              $countRejectedIndivisibility=0;
              $countRejectedIndivisibilityMax=1000;
            }
            if ($uniqueResourceAssignment!==null and isset($uniqueResourceAssignment[$ass->id]) and isset($uniqueResourceAssignment[$ass->id][$ass->idResource])) {
              $stockPlan=clone ($plan);
              $stockPlanStart=$plan->plannedStartDate;
              // $stockAss=$ass;
              $stockLeft=$left;
              $stockResources=$resources;
              // $stockRess=$ress;
              $stockPlannedWork=$arrayPlannedWork;
            }
            $regulNotPlanned=0;
            $initialStartDate=$currentDate;
            if ($ass->proportional and $assRate<$regul) { // PBER #11167
              // $regulTh=$regul;
              $assRate=$regul;
              if (!$ress['team']) {
                $capacityRate=round($assRate*$capacity, 2);
              }
            }
            // PLAN EACH DATE
            while (1) {
              if (($realProfile=='START' or $profile=='STARR') and $currentDate<self::shiftValidatedDate($plan->validatedStartDate, $delayProject) and $step==-1) {
                $currentDate=self::shiftValidatedDate($plan->validatedStartDate, $delayProject);
                $step=1;
              }
              // if ($forceASAP and $lastPlanDate and $currentDate<$lastPlanDate) {
              // self::storePlannedWorkLeveled($currentDate, $ass, $plan, $arrayPlannedWork, $changedAss, $left);
              if ($forceASAP and $lastPlanDate and $currentDate>$lastPlanDate and $left>0) {
                self::storePlannedWorkLeveled($startDate, $initialStartDate, $lastPlanDate, $capacity, $ass, $plan, $arrayPlannedWork, $changedAss, $left, $delayProject);
                break;
              }
              if ($regul and isset($ress['real-' . $currentDate]) and $ress['real-' . $currentDate]>=$r->getCapacityPeriod($currentDate)) {
                $currentDate=addDaysToDate($currentDate, $step);
                if ($currentDate<$endPlan and $step==-1) {
                  $currentDate=$endPlan;
                  $step=1;
                }
                continue;
              }
              $surbooked=0;
              $surbookedWork=0;
              $capacityNormal=null;
              if ($withProjectRepartition and isset($reserved['W']) and $profile!='FIXED' and !($forceFDUR and ($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR' or $profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART'))) {
                // $reserved[type='W']['sum'][idResource][day]+=value
                // $reserved[type='W'][idPE][idResource][day]=value
                foreach ($reserved['W'] as $idPe=>$arPeW) {
                  if ($idPe=='sum') continue;
                  if ($arPeW['idProj']!=$plan->idProject) continue;
                  if (!isset($arPeW[$ass->idResource])) continue;
                  $projectKey='Project#' . $plan->idProject;
                  if (!isset($ress[$projectKey]) or Resource::findAffectationRate($ress[$projectKey]['rate'], $currentDate)<=0) continue;
                  if (isset($arPeW['start']) and $arPeW['start'] and $arPeW['start']>$currentDate) continue;
                  if (isset($arPeW['end']) and $arPeW['end'] and $arPeW['end']<$currentDate) continue;
                  $currentsIsPredecessorOfRECW=false;
                  if (property_exists($plan, '_successorList') and isset($plan->_successorList)) {
                    foreach ($plan->_successorList as $idRECW=>$depRECW) {
                      if ($idRECW=='#' . $idPe and $depRECW['type']=='E-S') {
                        $currentsIsPredecessorOfRECW=true;
                        break;
                      }
                    }
                  }
                  if ($currentsIsPredecessorOfRECW) continue;
                  // if ($arPeW['typeProject']=='PRP' or $arPeW['typeProject']=='TMP') continue;
                  $week=getWeekNumberFromDate($currentDate);
                  if (!isset($ress[$projectKey][$week])) {
                    $weeklyReserved=0;
                    $firstDay=date('Y-m-d', firstDayofWeek(pq_substr($week, -2), pq_substr($week, 0, 4)));
                    foreach ($arPeW[$ass->idResource] as $dayOW=>$valReserved) {
                      $dayToTest=($dayOW==1)?$firstDay:addDaysToDate($firstDay, $dayOW-1);
                      if (isOpenDay($dayToTest, $ress['calendar'])) $weeklyReserved+=$valReserved;
                    }
                    if ($infinitecapacity) $weeklyReserved=0;
                    $ress[$projectKey][$week]=$weeklyReserved;
                    $resources[$ass->idResource][$projectKey][$week]=$weeklyReserved;
                  }
                  if (!isset($ress[$projectKey][$currentDate])) {
                    $dayReserved=0;
                    $weekDay=date('N', pq_strtotime($currentDate));
                    if (isset($arPeW[$ass->idResource][$weekDay])) $dayReserved=$arPeW[$ass->idResource][$weekDay];
                    $ress[$projectKey][$currentDate]=$dayReserved;
                    $resources[$ass->idResource][$projectKey][$currentDate]=$dayReserved;
                  }
                }
              }
              // Variable Capacity : retreive the capacity for the current date
              $capacityResource=$r->getCapacityPeriod($currentDate);
              if ($ress['variableCapacity'] or $infinitecapacity) {
                if (!$infinitecapacity) {
                  $capacity=$r->getSurbookingCapacity($currentDate);
                } else {
                  // $capacityNormal=$ress['capacity'];
                  $capacityNormal=$capacityResource;
                  $capacity=999;
                }
                if ($forceFDUR and ($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR' or $profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART')) {
                  $capacityRate=$regul;
                  if ($regulNotPlanned) {
                    $max=$r->getCapacityPeriod($currentDate);
                    if ($capacityRate<$max) {
                      $diff=$max-$capacityRate;
                      $capacityRate=$max;
                      $regulNotPlanned-=$diff;
                    }
                  }
                } else if ($ress['team']) {
                  $capacityRate=$ass->capacity;
                } else {
                  $capacityRate=round($assRate*$r->getCapacityPeriod($currentDate), 2);
                }
              }
              $week=getWeekNumberFromDate($currentDate);
              if (!isset($ress['weekTotalCapacity'][$week])) {
                $rTemp=new ResourceAll($ass->idResource);
                $capaWeek=$rTemp->getWeekCapacity($week, $capacityRate);
                $ress['weekTotalCapacity'][$week]=$capaWeek;
                $resources[$ass->idResource]['weekTotalCapacity'][$week]=$capaWeek;
              }
              // End Variable capacity
              if ($ress['team']) { // For team resource, check if unitary resources have enought availability
                $period=ResourceTeamAffectation::findPeriod($currentDate, $ress['periods']);
                if ($period===null) {
                  $capacity=0;
                } else {
                  $capacity=0;
                  foreach ($ress['members'] as $idMember=>$member) {
                    if (isset($ress['periods'][$period]['idResource'][$idMember])) {
                      $tmpCapa=$ress['periods'][$period]['idResource'][$idMember];
                      if (isset($member[$currentDate])) {
                        $memberWork=$member[$currentDate];
                        if ($profile=='RECW') {
                          // Work surbooked on this member (e.g. by a DDUR/CDUR activity that overrode a recurring
                          // reservation) must not block planning of the recurring activity itself
                          $memberWork-=self::$_surbookedWorkStored[$idMember][$currentDate]??0;
                          if ($memberWork<0) $memberWork=0;
                        }
                        if (isset($resources[$idMember]) and isset($resources[$idMember]['capacity'])) {
                          $capaMember=$resources[$idMember]['capacity'];
                        } else {
                          $capaMember=SqlList::getFieldFromId('Resource', $idMember, 'capacity');
                        }
                        if ($capaMember-$memberWork>=$tmpCapa) {
                          // tmpCapa preserved : enough left
                        } else {
                          $tmpCapa=$capaMember-$memberWork;
                        }
                      }
                      // PBER : must reserve availability for recurring work (RECW) of this unitary resource
                      // even when it has no other work recorded yet for this date (member[$currentDate] not set) :
                      // RECW tasks are planned last on purpose (see sortPlanningElements), relying on this reservation
                      // to still have room left when they are actually computed.
                      if (isset($reserved['W']['sum'][$idMember]) and $profile!='FIXED') {
                        $dow=date('N', pq_strtotime($currentDate));
                        $reservedForMember=$reserved['W']['sum'][$idMember][$dow]??0;
                        if (isset($reserved['W'][$plan->id][$idMember][$dow])) {
                          // Exclude the current recurring activity's own reservation on this member : it must not reserve
                          // availability against itself
                          $reservedForMember-=$reserved['W'][$plan->id][$idMember][$dow];
                        }
                        if ($reservedForMember>0 and !$infinitecapacity) $tmpCapa-=$reservedForMember;
                      }
                      if ($tmpCapa>0) $capacity+=$tmpCapa;
                    }
                  }
                  $capacityNormal=$capacity;
                  // $capacityNormal=$r->getCapacityPeriod($currentDate);
                  if (!$infinitecapacity) {
                    $capacity+=$r->getSurbookingCapacity($currentDate, true);
                  } else {
                    $capacity=999;
                  }
                  if (isset($listPoolExtraCapacity[$ass->idResource])) {
                    $dt=$listPoolExtraCapacityDate[$ass->idResource]??'0000-00-00';
                    if ($currentDate>=$dt) $capacityNormal+=$listPoolExtraCapacity[$ass->idResource];
                  }
                  if ($capacityNormal==$capacity) $capacityNormal=null;
                }
              } else {
                if (!$ress['team'] and isset($ress['isMemberOf']) and count($ress['isMemberOf'])>0) {
                  // Preserve $capacityNormal
                } else {
                  $capacityNormal=null;
                }
              }
              if ($profile=='RECW') {
                if ($currentDate<=$endPlan) {
                  $left=$capacity;
                } else {
                  $left=0;
                }
              }
              // if ($left<0.01 and $profile=='ASAP' and $forceASAP and $currentDate<=$plan->validatedEndDate) {
              // $forceASAPContinue=true;
              // } else
              if ($left<0.01) {
                break;
              }
              if ($profile=='FIXED' and $currentDate>self::shiftValidatedDate($plan->validatedEndDate, $delayProject)) {
                $changedAss=true;
                $ass->notPlannedWork=$left;
                if ($ass->optional==0) {
                  $plan->notPlannedWork+=$left;
                  if ($plan->refType=='Meeting' and self::shiftValidatedDate($plan->plannedEndDate??$plan->validatedEndDate, $delayProject)<date('Y-m-d')) {
                    // No alert for meetings in the past...
                  } else {
                    $arrayNotPlanned[$ass->id]=i18n('planResourceNotAvailable', array(round($left, 2)));
                  }
                }
                $left=0;
                break;
              }
              // Set limits to avoid eternal loop
              if ($currentDate>=$globalMaxDate) {
                $changedAss=true;
                $ass->notPlannedWork=$left;
                $plan->notPlannedWork+=$left;
                $arrayNotPlanned[$ass->id]=i18n('planLeftAfterMaxDate', array(round($left, 2)));
                $left=0;
                break;
              }
              if ($currentDate<=$globalMinDate) {
                $changedAss=true;
                $ass->notPlannedWork=$left;
                $plan->notPlannedWork+=$left;
                $arrayNotPlanned[$ass->id]=i18n('planLeftAfterMaxDate', array(round($left, 2)));
                $left=0;
                break;
              }
              if ($uniqueStart and $uniqueEnd) {
                if ($currentDate<$uniqueStart) {
                  $currentDate=addDaysToDate($currentDate, $step);
                  continue;
                }
                if ($currentDate>$uniqueEnd) {
                  $changedAss=true;
                  $ass->notPlannedWork=$left;
                  $plan->notPlannedWork+=$left;
                  $arrayNotPlanned[$ass->id]=i18n('planLeftAfterMaxDate', array(round($left, 2)));
                  $left=0;
                  break;
                }
              }
              if ($ress['Project#' . $plan->idProject]['rate']==0) {
                break;
              } // Resource allocated to project with rate = 0, cannot be planned
              if (isOpenDay($currentDate, $r->idCalendarDefinition)) {
                $planned=0;
                $plannedReserved=0;
                $plannedReservedProject=0;
                $week=getWeekNumberFromDate($currentDate);
                if (pq_array_key_exists($currentDate, $ress)) {
                  $planned=$ress[$currentDate];
                }
                if ($profile=='RECW') {
                  // Surbooking (e.g. from a DDUR/CDUR activity planned earlier that overrode the availability reserved
                  // for this recurring activity) must not block planning of the recurring activity itself
                  if (!isset(self::$_surbookedWorkStored[$ass->idResource])) self::$_surbookedWorkStored[$ass->idResource]=self::getExistingSurbookedWork($ass->idResource);
                  if (isset(self::$_surbookedWorkStored[$ass->idResource][$currentDate]) and self::$_surbookedWorkStored[$ass->idResource][$currentDate]>0) {
                    $planned-=self::$_surbookedWorkStored[$ass->idResource][$currentDate];
                    if ($planned<0) $planned=0;
                  }
                }
                // Specific reservation for RECW that are not planned yet but will be when start and end are known
                $dow=date('N', pq_strtotime($currentDate));
                $resourceHasReserved=false;
                if ($profile=='GROUP') {
                  foreach ($groupAss as $assIdResource=>$groupData) {
                    if (isset($reserved['W']['sum'][$assIdResource][$dow])) {
                      $resourceHasReserved=true;
                      break;
                    }
                  }
                } else {
                  if (isset($reserved['W']['sum'][$ass->idResource][$dow])) $resourceHasReserved=true;
                }
                
                if ($resourceHasReserved and $profile!='FIXED') {
                  foreach ($reserved['W'] as $idPe=>$arPeW) {
                    if ($idPe=='sum') continue;
                    if ($idPe==$plan->id) continue; // we are treating the one we reserved for
                    $projectKeyTest='Project#' . $arPeW['idProj'];
                    if (isset($ress[$projectKeyTest]) and Resource::findAffectationRate($ress[$projectKeyTest]['rate'], $currentDate)<=0) continue;
                    // === Determine if we must start to reserve work on this task for RECW tasks that will be planned after
                    $startReserving=false;
                    if ($arPeW['start']) { // Start is defined from predecessor
                      if ($arPeW['start']<=$currentDate) { // Start is defined (from predecessor) and passed
                        $startReserving=true;
                      }
                    } else if (count($reserved['W'][$idPe]['pred'])==0) { // No predecessor, so start is start of project
                      $startReserving=true;
                    } else if (isset($reserved['W'][$idPe]['pred'][$plan->id]) and ($reserved['W'][$idPe]['pred'][$plan->id]['type']=='S-S')) { // Current is predecessor type S-S
                      $delayPred=$reserved['W'][$idPe]['pred'][$plan->id]['delay'];
                      if ($delayPred<=0 or addWorkDaysToDate($startPlan, $delayPred+1, $plan->idProject)<=$currentDate) { // ... and delay make it started
                        $startReserving=true;
                      }
                    } else { // Start Date not Set, check if some predecessor exist (but do not count E-E wich are not real predecessors)
                      $cpt=0;
                      foreach ($reserved['W'][$idPe]['pred'] as $idPredTmp=>$predTmp) {
                        if ($predTmp['type']!='E-E') $cpt++;
                      }
                      if ($cpt==0) $startReserving=true;
                    }
                    $typeProjectR=$arPeW['typeProject'];
                    $idProjectR=$arPeW['idProject'];
                    if ($idProjectR!=$plan->idProject and ($typeProjectR=='PRP' or $typeProjectR=='TMP')) $startReserving=false;
                    // === Determine if we must end to reserve work on this task for RECW tasks that will be planned after
                    $endReserving=false;
                    if ($arPeW['end'] and $arPeW['end']<$currentDate) {
                      $endReserving=true;
                    } // NB : cannot take into account E-E with negative delay : we don't know yet when current task will end to determine [end - x days]
                    // OK, reserve work ...
                    if ($startReserving and !$endReserving) {
                      $reservedWork=0;
                      if ($profile=='GROUP') {
                        foreach ($groupAss as $assIdResource=>$groupData) {
                          if (isset($arPeW[$assIdResource]) and isset($arPeW[$assIdResource][$dow]) and $arPeW[$assIdResource][$dow]>$reservedWork) {
                            $reservedWork=$arPeW[$assIdResource][$dow];
                          }
                        }
                      } else if (isset($arPeW[$ass->idResource][$dow])) {
                        $reservedWork=$arPeW[$ass->idResource][$dow];
                      }
                      if (!($typeProjectR=='PRP' or $typeProjectR=='TMP')) $planned+=$reservedWork;
                      $plannedReserved+=$reservedWork;
                      $plannedReservedProject+=$reservedWork;
                    }
                  }
                }
                if ($regul) {
                  if (!isset($ress['real'][$keyElt][$currentDate])) {
                    $interval+=$step;
                  }
                }
                if (!($planned<$capacity or $profile=='RECW')) {
                  if ($plan->indivisibility==1) {
                    if ($profile=='GROUP') {
                      $restartLoopAllAssignements=true;
                      $startPlan=addDaysToDate($currentDate, $step);
                      break (2);
                    } else {
                      $plan=$stockPlan;
                      $plan->plannedStartDate=$stockPlanStart;
                      $ass=$stockAss;
                      $fractionStart=0;
                      $ass->plannedStartDate=null;
                      $left=$stockLeft;
                      $arrayPlannedWork=$stockPlannedWork;
                      $ress=$stockRess;
                      $resources=$stockResources;
                      $countRejectedIndivisibility++;
                      if ($countRejectedIndivisibility>$countRejectedIndivisibilityMax) {
                        break;
                      }
                    }
                  }
                } else {
                  $value=$capacity-$planned;
                  if (isset($ress['real'][$keyElt][$currentDate])) {
                    // $value-=$ress['real'][$keyElt][$currentDate]; // Case 1 remove existing
                    // if ($value<0) $value=0;
                    $value=0; // Case 2 : if real is already defined for the given activity, no more work to plan
                  }
                  if ($profile=='RECW') {
                    $dow=date('N', pq_strtotime($currentDate));
                    if (isset($reserved['W'][$plan->id][$ass->idResource][$dow])) {
                      // $value=$reserved['W'][$plan->id][$ass->idResource][$dow]; // PBE Start of change - Ticket #4092
                      $targetValue=$reserved['W'][$plan->id][$ass->idResource][$dow]; //
                      $value=($targetValue>$value)?$value:$targetValue; // PBE End of change
                      $ass->assignedWork+=$value;
                      $ass->leftWork+=$value;
                      $ass->plannedWork+=$value;
                      $plan->assignedWork+=$value;
                      $plan->leftWork+=$value;
                      $plan->plannedWork+=$value;
                    } else {
                      $value=0;
                    }
                  }
                  if ($value>$capacityRate) {
                    $value=$capacityRate;
                  }
                  if ($withProjectRepartition and $profile!='RECW' and !($forceFDUR and ($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR' or $profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART'))) {
                    foreach ($listTopProjects as $idProject) {
                      $projectKey='Project#' . $idProject;
                      $plannedProj=0;
                      $plannedProjDay=0;
                      $rateProj=1;
                      if (isset($ress[$projectKey][$week])) {
                        $plannedProj=$ress[$projectKey][$week];
                      }
                      if (isset($ress[$projectKey][$currentDate])) {
                        $plannedProjDay=$ress[$projectKey][$currentDate];
                        if ($profile=='CDUR') {
                          if ($ress['team']) {
                            $capaTeam=$r->getCapacityPeriod($currentDate);
                            if ($plannedProjDay+$value>$capaTeam) {
                              $value=$capaTeam-$plannedProjDay;
                            }
                          } else {
                            $leftProjDay=$capacityResource-$plannedProjDay;
                            if ($value>$leftProjDay) $value=$leftProjDay;
                          }
                          if ($value<=0) $value=0;
                        }
                      }
                      $rateProj=(isset($ress[$projectKey]))?Resource::findAffectationRate($ress[$projectKey]['rate'], $currentDate)/100:0;
                      // ATTENTION, if $rateProj < 0, this means there is no affectation left ...
                      if ($rateProj<0) {
                        $changedAss=true;
                        $fixDurPrf=($profile=='FDUR' or $profile=='DDUR' or $profile=='CDUR' or $profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART')?true:false;
                        $plan->notPlannedWork+=$left;
                        if (!$ass->plannedStartDate) $ass->plannedStartDate=($fixDurPrf)?$startPlan:$currentDate;
                        if (!$ass->plannedEndDate) $ass->plannedEndDate=$currentDate;
                        if (!$plan->plannedStartDate) $plan->plannedStartDate=($fixDurPrf)?$startPlan:$currentDate;
                        if (!$plan->plannedEndDate) $plan->plannedEndDate=$currentDate;
                        if (!isset($arrayNotPlanned[$ass->id])) {
                          $arrayNotPlanned[$ass->id]=i18n('planLeftAfterEnd', array(round($left, 2)));
                          $ass->notPlannedWork=$left;
                        }
                        $left=0;
                      }
                      // if ($ress['variableCapacity']) {
                      $capaWeek=$ress['weekTotalCapacity'][getWeekNumberFromDate($currentDate)];
                      // } else {
                      // if ($rateProj==1) {
                      // $capaWeek=7*$capacity;
                      // } else {
                      // $capaWeek=$daysPerWeek*$capacity;
                      // }
                      // }
                      $leftProj=round($capaWeek*$rateProj, 2)-$plannedProj; // capacity for a week
                      if ($value>$leftProj) {
                        $value=$leftProj;
                      }
                    }
                  } else if ($withProjectRepartition and $profile=='RECW') {
                    $projectKey='Project#' . $plan->idProject;
                    $rateProj=(isset($ress[$projectKey]))?Resource::findAffectationRate($ress[$projectKey]['rate'], $currentDate)/100:0;
                    if ($rateProj<=0) $value=0;
                  } else if ($profile=='DDUR') {
                    $projectKey='Project#' . $plan->idProject;
                    $rateProj=(isset($ress[$projectKey]))?Resource::findAffectationRate($ress[$projectKey]['rate'], $currentDate)/100:0;
                    // ATTENTION, if $rateProj < 0, this means there is no affectation left ...
                    if ($rateProj<0) {
                      if (0) { // First way : consider it is surbooking
                        $surbookedWork=$left;
                      } else { // Second way : not planned work
                        $plan->notPlannedWork+=$left;
                        if (!isset($arrayNotPlanned[$ass->id])) {
                          $arrayNotPlanned[$ass->id]=i18n('planLeftAfterEnd', array(round($left, 2)));
                          $ass->notPlannedWork=$left;
                        }
                        $left=0;
                      }
                    }
                  }
                  if ($currentDate==$startPlan and $value>((1-$startFraction)*$capacity)) {
                    $value=((1-$startFraction)*$capacity);
                  }
                  // if ($infinitecapacity and isset($ress['real-'.$currentDate])) {
                  if (isset($ress['real-' . $currentDate])) { // PBER #8838
                    $leftCapacity=$r->getCapacityPeriod($currentDate)-$ress['real-' . $currentDate];
                    if ($leftCapacity<$value) {
                      $tmpRemove=$value-$leftCapacity;
                      $expected=$value;
                      $value-=$tmpRemove;
                      $surbookedWork-=$tmpRemove;
                      if ($value<0) $value=0;
                      if ($surbookedWork<0) $surbookedWork=0;
                      $regulNotPlanned+=$expected-$value;
                    }
                  }
                  if ($regul) {
                    $tmpTarget=$regul;
                    $regulTarget=round(($regul*($interval-1)), 10);
                    if (isset($ress['real'][$keyElt][$currentDate])) {
                      $tmpTarget=0;
                    }
                    $tempCapacity=$r->getCapacityPeriod($currentDate); // PBER #6865 - Fix for Pools
                    if (isset($ress[$currentDate]) and !$infinitecapacity) {
                      $tempCapacity-=$ress[$currentDate];
                    }
                    if ($tempCapacity>$capacityRate) $tempCapacity=$capacityRate; // PBER #6865 - Fix for Pools
                    if ($tempCapacity<0) $tempCapacity=0;
                    if ($tempCapacity<$regulTh and $regulTh!=0 and !$infinitecapacity) {
                      $tmpTarget=round($tmpTarget*$tempCapacity/$regulTh, 10);
                    }
                    $regulTarget=round($regulTarget+$tmpTarget, 10);
                    $toPlan=$regulTarget-$regulDone;
                    if ($value>$toPlan) {
                      $value=$toPlan;
                    }
                    if ($workUnit=='days') {
                      if ($profile=='QUART') $value=ceil($value*100)/100;
                      else {
                        // $value=ceil($value*10)/10;
                        // Strange but in some cases above formula gives incorrect value
                        // Plan 4 days over 10 days duration, gived 0.5 on 1 day : $value=0.4 => ceil($value*10)/10=0.5
                        // Replaced with 2 following lines
                        $value=round($value, 3);
                        $value=ceil($value*10)/10;
                      }
                    } else {
                      $value=round($value/$halfHour/5, 1)*$halfHour*5;
                      $capacityRate=round($capacityRate/$halfHour/5, 1)*$halfHour*5;
                    }
                    if ($profile=='FULL' and $toPlan<1 and $interval<$delaiTh) {
                      $value=0;
                    }
                    if ($profile=='HALF' and $interval<$delaiTh) {
                      if ($toPlan<0.5) {
                        $value=0;
                      } else {
                        $value=(floor($toPlan/0.5))*0.5;
                      }
                    }
                    if ($profile=='QUART' and $interval<$delaiTh) {
                      if ($toPlan<0.25) {
                        $value=0;
                      } else {
                        $value=(floor($toPlan/0.25))*0.25;
                      }
                    }
                    if ($value>$capacityRate and $capacityRate>=0.01) {
                      $value=$capacityRate;
                    }
                    if ($value>($capacity-$planned)) {
                      $value=$capacity-$planned;
                      // if ($value<0.1) $value=0; // Rounding at 0.1, otherwise will wait for sum to be > 0.1
                      if ($workUnit=='day' and $value<0.01) $value=0; // New rounding at 0.01, will generate more smooth planning
                      if ($workUnit=='hour' and $value<0.01/$hoursPerDay) $value=0; // New rounding at 0.01, will generate more smooth planning
                    }
                  }
                  if ($profile=='GROUP') {
                    foreach ($groupAss as $id=>$grp) {
                      $grpCapacity=1;
                      if ($grp['leftWorkTmp']>0) {
                        $grpCapacity=$grp['capacity']*$grp['assRate'];
                        if ($resources[$id]['variableCapacity'] or $infinitecapacity) {
                          if (!isset($resourceOfTheGroup[$id]['capacity'][$currentDate])) {
                            $rTemp=$resourceOfTheGroup[$id]['resObj'];
                            if (!$infinitecapacity) {
                              $resourceOfTheGroup[$id]['capacity'][$currentDate]=$rTemp->getSurbookingCapacity($currentDate);
                            } else {
                              $resourceOfTheGroup[$id]['capacity'][$currentDate]=999;
                            }
                          }
                          $grpCapacity=$resourceOfTheGroup[$id]['capacity'][$currentDate]*$grp['assRate'];
                        }
                        if (isOffDay($currentDate, $grp['calendar'])) {
                          $grpCapacity=0;
                        } else if (isset($grp['ResourceWork'][$currentDate])) {
                          $grpCapacity-=$grp['ResourceWork'][$currentDate];
                        }
                      }
                      if ($value>$grpCapacity-$plannedReserved) {
                        $value=$grpCapacity-$plannedReserved;
                      }
                    }
                    // Check Project Affectation Rate
                    foreach ($groupAss as $id=>$grp) {
                      foreach ($listTopProjects as $idProject) {
                        $projectKey='Project#' . $idProject;
                        $plannedProj=0;
                        $rateProj=1;
                        if (isset($grp['ResourceWork'][$projectKey][$week])) {
                          $plannedProj=$grp['ResourceWork'][$projectKey][$week];
                        }
                        $rateProj=(isset($ress[$projectKey]))?Resource::findAffectationRate($grp['ResourceWork'][$projectKey]['rate'], $currentDate)/100:0;
                        $week=getWeekNumberFromDate($currentDate);
                        if (!isset($resources[$id]['weekTotalCapacity'][$week])) {
                          $rTemp=new Resource($id);
                          $capaWeek=$rTemp->getWeekCapacity($week, $capacityRate);
                          $resources[$id]['weekTotalCapacity'][$week]=$capaWeek;
                        } else {
                          $capaWeek=$resources[$id]['weekTotalCapacity'][$week];
                        }
                        // if ($rateProj==1) {
                        // $leftProj=round(7*$grp['capacity']*$rateProj,2)-$plannedProj; // capacity for a full week
                        // => to be able to plan weekends
                        // } else {
                        // $leftProj=round($daysPerWeek*$grp['capacity']*$rateProj,2)-$plannedProj; // capacity for a week
                        // }
                        $leftProj=round($capaWeek*$rateProj, 2)-$plannedProj; // capacity for a week
                        if ($value>$leftProj) {
                          $value=$leftProj;
                        }
                      }
                    }
                    
                    foreach ($groupAss as $id=>$grp) {
                      $groupAss[$id]['leftWorkTmp']-=$value;
                      // $groupAss[$id]['weekWorkTmp'][$week]+=$value;
                      if ($withProjectRepartition and $value>=0.01) {
                        foreach ($listTopProjects as $idProject) {
                          $projectKey='Project#' . $idProject;
                          $plannedProj=0;
                          if (pq_array_key_exists($week, $grp['ResourceWork'][$projectKey])) {
                            $plannedProj=$grp['ResourceWork'][$projectKey][$week];
                          }
                          $groupAss[$id]['ResourceWork'][$projectKey][$week]=$value+$plannedProj;
                        }
                      }
                    }
                  }
                  // Minimum Threshold
                  if ($plan->minimumThreshold and round($value, 2)<round($plan->minimumThreshold, 2) and $value<$left) {
                    $value=0;
                    $cptThresholdReject++;
                    if ($cptThresholdReject>$cptThresholdRejectMax) {
                      $changedAss=true;
                      $ass->notPlannedWork=$left;
                      if ($ass->optional==0) {
                        $plan->notPlannedWork+=$left;
                        $arrayNotPlanned[$ass->id]=i18n('planThresholdTooSmall', array(
                            round($left, 2),
                            round($plan->minimumThreshold, 2)));
                      }
                      $left=0;
                      break;
                    }
                  } else {
                    $cptThresholdReject=0;
                  }
                  // Incopatible Resource
                  if (count($ress['incompatible'])>0) {
                    if ($profile=='GROUP') { // Activity planned : "work together" with incompatible resources
                      $changedAss=true;
                      $ass->notPlannedWork=$left;
                      $plan->notPlannedWork+=$left;
                      $incompatibleNames="";
                      foreach ($ress['incompatible'] as $inc=>$incValue) {
                        $incompatibleNames.=(($incompatibleNames)?", ":"") . SqlList::getNameFromId('Resource', $inc);
                      }
                      $arrayNotPlanned[$ass->id]=i18n("incompatibleResourceCannotWorkTogether", array(
                          SqlList::getNameFromId('Resource', $ass->idResource),
                          $incompatibleNames));
                      $left=0;
                      break;
                    }
                    foreach ($ress['incompatible'] as $inc=>$incValue) {
                      if ($profile=='RECW') break;
                      if (!isset($resources[$inc])) {
                        $resInc=new ResourceAll($inc);
                        $resources[$inc]=$resInc->getWork($startDate, $withProjectRepartition, $simulation);
                      }
                      $dow=date('N', pq_strtotime($currentDate));
                      $incRes=$resources[$inc];
                      if (isset($incRes[$currentDate]) or isset($reserved['W']['sum'][$inc][$dow])) {
                        // $capaInc=$incRes['normalCapacity'];
                        // $leftInc=$capaInc;
                        // if (isset($incRes[$currentDate])) $leftInc-=$incRes[$currentDate];
                        // if (isset($reserved['W']['sum'][$inc][$dow])) $leftInc-=$reserved['W']['sum'][$inc][$dow];
                        // if (isset($reserved['W']['sum'][$ass->idResource][$dow])) $leftInc-=$reserved['W']['sum'][$ass->idResource][$dow];
                        // if ($leftInc<0) $leftInc=0;
                        // if ($value>$leftInc) {
                        // $value=$leftInc;
                        // }
                        if (isset($incRes[$currentDate])) $value-=$incRes[$currentDate];
                        if (isset($reserved['W']['sum'][$inc][$dow])) $value-=$reserved['W']['sum'][$inc][$dow];
                        // if (isset($reserved['W']['sum'][$ass->idResource][$dow])) $value-=$reserved['W']['sum'][$ass->idResource][$dow];
                        // if ($value>0 and isset($ress[$currentDate])) {
                        // $value-=$ress[$currentDate];
                        // if ($value<0) $value=0;
                        // }
                        if ($value<0) $value=0;
                      }
                    }
                  }
                  // Support Resource
                  if (count($ress['support'])>0) {
                    foreach ($ress['support'] as $sup=>$supRate) {
                      if (!isset($resources[$sup])) {
                        $resSup=new Resource($sup);
                        $resources[$sup]=$resSup->getWork($startDate, $withProjectRepartition, $simulation);
                      }
                      $supRes=$resources[$sup];
                      if (!isOpenDay($currentDate, $supRes['calendar'])) {
                        $value=0;
                      } else if (isset($supRes[$currentDate])) {
                        if ($supRes['variableCapacity']) {
                          $resSup=new Resource($sup);
                          $capaSup=$resSup->getCapacityPeriod($currentDate);
                        } else {
                          $capaSup=$supRes['normalCapacity'];
                        }
                        $leftSup=$capaSup-$supRes[$currentDate];
                        if ($leftSup<0) $leftSup=0;
                        if ($value>($leftSup/$supRate*100)) {
                          $value=round($leftSup/$supRate*100, 3);
                        }
                      }
                    }
                  }
                  if ($value<=0.01 and $plan->indivisibility==1) {
                    if ($profile=='GROUP') {
                      $restartLoopAllAssignements=true;
                      $startPlan=addDaysToDate($currentDate, $step);
                      break (2);
                    } else {
                      $plan=$stockPlan;
                      $plan->plannedStartDate=$stockPlanStart;
                      $ass=$stockAss;
                      $fractionStart=0;
                      $ass->plannedStartDate=null;
                      $left=$stockLeft;
                      $arrayPlannedWork=$stockPlannedWork;
                      $ress=$stockRess;
                      $resources=$stockResources;
                      $countRejectedIndivisibility++;
                      if ($countRejectedIndivisibility>$countRejectedIndivisibilityMax) {
                        break;
                      }
                    }
                  }
                  $value=($value>$left)?$left:$value;
                  if ($value>=0.01) { // Store value on Resource Team if current resource belongs to a Resource Team
                    if (!$ress['team'] and isset($ress['isMemberOf']) and count($ress['isMemberOf'])>0) {
                      // For each Pool current resource is member of
                      foreach ($ress['isMemberOf'] as $idRT=>$rt) {
                        if (!isset($resources[$idRT])) {
                          $rTeam=new ResourceAll($idRT, true);
                          $resources[$idRT]=$rTeam->getWork($startDate, $withProjectRepartition, $simulation);
                        }
                        $period=ResourceTeamAffectation::findPeriod($currentDate, $resources[$idRT]['periods']);
                        // For current date : if 1) some work exists on Pool 2) current resource has not null capacity on Pool
                        // => must check that there is no constraint
                        if ($period and isset($resources[$idRT][$currentDate]) and isset($resources[$idRT]['periods'][$period]['idResource'][$ass->idResource]) and $resources[$idRT]['periods'][$period]['idResource'][$ass->idResource]>0) {
                          $ctrlPlannedWorkOnPool=$resources[$idRT][$currentDate];
                          if ($profile=='RECW') {
                            // Surbooking already stored on the Pool (e.g. from a DDUR/CDUR activity planned earlier that overrode
                            // the availability reserved for this recurring activity) must not block planning of the recurring activity
                            $ctrlPlannedWorkOnPool-=self::$_surbookedWorkStored[$idRT][$currentDate]??0;
                            if ($ctrlPlannedWorkOnPool<0) $ctrlPlannedWorkOnPool=0;
                          }
                          $ctrlCanBeDoneByOthersOnPool=0;
                          $surbookedOther=0;
                          foreach ($resources[$idRT]['members'] as $idMember=>$workMember) {
                            $ctrlCanBeDoneByMember=0;
                            if ($idMember==$ass->idResource) continue; // Do not count work that can be done by current (we count only "others")
                            // PBER #8958
                            if (!isset($resources[$idMember])) {
                              $rMember=new Resource($idMember);
                              $resources[$idMember]=$rMember->getWork($startDate, $withProjectRepartition, $simulation);
                            }
                            // PBER #8958 - End
                            if (isset($resources[$idMember]['capacity'])) {
                              $ctrlCapaMember=$resources[$idMember]['capacity'];
                            } else {
                              $ctrlCapaMember=SqlList::getFieldFromId('Resource', $idMember, 'capacity');
                            }
                            $ctrlCanBeDoneByMember=$ctrlCapaMember; // Limit to own capacity of resource
                            if (isset($resources[$idRT]['periods'][$period]['idResource'][$idMember])) { // If member has capacity on pool on the period
                              $capaMaxMemberOnPool=$resources[$idRT]['periods'][$period]['idResource'][$idMember];
                              // PBER #8958 - Remove real work for member
                              $allreadyBookedForPoolMember=0;
                              if (isset($resources[$idMember]['real-' . $currentDate])) {
                                $allreadyBookedForPoolMember+=$resources[$idMember]['real-' . $currentDate]; // Subtract already done (off days ?) for member
                              }
                              if (isset($resources[$idMember][$currentDate])) {
                                $allreadyBookedForPoolMember+=$resources[$idMember][$currentDate]; // Subtract already planned for member
                              }
                              if ($allreadyBookedForPoolMember>($ctrlCapaMember-$capaMaxMemberOnPool)) {
                                $ctrlCanBeDoneByMember=$ctrlCapaMember-$allreadyBookedForPoolMember;
                              } else if ($capaMaxMemberOnPool<$ctrlCanBeDoneByMember) {
                                $ctrlCanBeDoneByMember=$capaMaxMemberOnPool;
                              }
                              // PBER #8958 - End
                            } else {
                              $ctrlCanBeDoneByMember=0;
                            }
                            if (!$ctrlCanBeDoneByMember or $ctrlCanBeDoneByMember<0) $ctrlCanBeDoneByMember=0;
                            $ctrlCanBeDoneByOthersOnPool+=$ctrlCanBeDoneByMember;
                            if ($infinitecapacity) $surbookedOther+=self::$_surbookedWorkStored[$idMember][$currentDate]??0;
                          }
                          $mustBeDoneByCurrentResourceOnPool=$ctrlPlannedWorkOnPool-$ctrlCanBeDoneByOthersOnPool;
                          $available=$capacity-$mustBeDoneByCurrentResourceOnPool;
                          if (isset($ress[$currentDate])) {
                            $available-=$ress[$currentDate]; // Subtract already planned for current user
                          }
                          if ($infinitecapacity) {
                            $capacityNormalLimit=$capacityNormal;
                            $capacityNormal-=$mustBeDoneByCurrentResourceOnPool-$surbookedOther;
                            if (isset($listPoolExtraCapacity[$idRT])) {
                              $dt=$listPoolExtraCapacityDate[$idRT]??'0000-00-00';
                              if ($currentDate>=$dt) $capacityNormal+=$listPoolExtraCapacity[$idRT];
                            }
                            if ($capacityNormal>$capacityNormalLimit) $capacityNormal=$capacityNormalLimit;
                            if ($capacityNormal<0) $capacityNormal=0;
                          }
                          if ($available<$value) {
                            $value=$available;
                          }
                          if ($value<0) $value=0;
                        }
                      }
                      foreach ($ress['isMemberOf'] as $idRT=>$rt) {
                        // Store detail of already planned for each member (will be used when planning Pool)
                        // Attention, must be done after controlling every Pool, to have the correc $value
                        $period=ResourceTeamAffectation::findPeriod($currentDate, $resources[$idRT]['periods']);
                        if ($period and isset($resources[$idRT]['periods'][$period]['idResource'][$ass->idResource])) {
                          if (!isset($resources[$idRT]['members'][$ass->idResource][$currentDate])) $resources[$idRT]['members'][$ass->idResource][$currentDate]=0;
                          $resources[$idRT]['members'][$ass->idResource][$currentDate]+=$value;
                        }
                      }
                    }
                  }
                  if ($regul and $value>=0.01) $regulDone+=$value;
                  if ($value>=0.01) {
                    if ($firstPlannedWork==null or $firstPlannedWork>$currentDate) {
                      $firstPlannedWork=$currentDate;
                    }
                    self::storePlannedWork($value, $planned, $plannedReserved, $withProjectRepartition, $currentDate, $week, $profile, $r, $capacity, ($capacityNormal??null), $listTopProjects, $surbooked, $surbookedWork, $ass, $plan, $arrayPlannedWork, $changedAss, $left, $ress, null, $infinitecapacity, $startPlan);
                    $surbookedWork=0;
                    $surbooked=0;
                    // Support Resource
                    if (count($ress['support'])>0) {
                      foreach ($ress['support'] as $sup=>$supRate) {
                        $supRes=$resources[$sup];
                        $plannedSup=isset($supRes[$currentDate])?$supRes[$currentDate]:0;
                        $valueSup=round($value*$supRate/100, 3);
                        $surbookedSup=0;
                        $surbookedSupWork=0;
                        $leftSup=0;
                        if ($valueSup>0) {
                          $keySupAss=$ass->id . '#' . $sup;
                          if (!isset($supportAssignments[$keySupAss])) {
                            $supportAss=SqlElement::getSingleSqlElementFromCriteria('Assignment', array(
                                'idResource'=>$sup,
                                'supportedAssignment'=>$ass->id));
                            if (!$supportAss->id) { // Assignment for support does not exist : will create it
                              $rs=SqlElement::getSingleSqlElementFromCriteria('ResourceSupport', array(
                                  'idResource'=>$ass->id,
                                  'idSupport'=>$sup));
                              $supportAss=$rs->manageSupportAssignment($ass);
                            }
                          } else {
                            $supportAss=$supportAssignments[$keySupAss];
                          }
                          if (!$supportAss) continue;
                          self::storePlannedWork($valueSup, $plannedSup, 0, $withProjectRepartition, $currentDate, $week, $profile, null, $supRes['normalCapacity'], null, $listTopProjects, $surbookedSup, $surbookedSupWork, $supportAss, $plan, $arrayPlannedWork, $changedAss, $leftSup, $supRes, $sup, $infinitecapacity, $startPlan);
                          $supportAssignments[$keySupAss]=$supportAss;
                          $resources[$sup]=$supRes;
                        }
                      }
                    }
                  }
                }
              }
              $currentDate=addDaysToDate($currentDate, $step);
              if ($currentDate<$endPlan and $step==-1) {
                $currentDate=$endPlan;
                $step=1;
              }
            } // End loop on date => While (1)
            // If unique Assignment
            if ($uniqueResourceAssignment!==null and isset($uniqueResourceAssignment[$ass->id]) and isset($uniqueResourceAssignment[$ass->id][$ass->idResource])) {
              $uniqueResourceAssignment[$ass->id][$ass->idResource]['plan']=clone ($plan);
              $resources[$ass->idResource]=$ress;
              $uniqueResourceAssignment[$ass->id][$ass->idResource]['resources']=$resources;
              $uniqueResourceAssignment[$ass->id][$ass->idResource]['plannedWork']=$arrayPlannedWork;
              $uniqueResourceAssignment[$ass->id][$ass->idResource]['ass']=clone ($ass);
              $plan=$stockPlan;
              $plan->plannedStartDate=$stockPlanStart;
              $left=$stockLeft;
              $resources=$stockResources;
              $arrayPlannedWork=$stockPlannedWork;
              unset($listAss[$keyAss]);
              continue;
            }
            if ($changedAss) {
              $ass->_noHistory=true; // Will only save planning data, so no history required
              $arrayAssignment[]=$ass;
              if (count($supportAssignments)>0) {
                foreach ($supportAssignments as $supAss) {
                  $arrayAssignment[]=$supAss;
                }
              }
            }
            $resources[$ass->idResource]=$ress;
            if (!$ass->proportional and $ass->leftWork>0 and $ass->notPlannedWork<$ass->leftWork) {
              $proportionalStart=$plan->plannedStartDate;
              $proportionalEnd=$plan->plannedEndDate;
            }
          } // End Loop on each $ass (assignment)
        } // End loop while ($restartLoopAllAssignements)
      }
      // PBER - #8074 - START
      if ($plan->realStartDate) {
        $plan->plannedStartDate=($firstPlannedWork and $firstPlannedWork<$plan->realStartDate)?$firstPlannedWork:$plan->realStartDate;
      }
      if ($plan->plannedEndDate and $plan->realStartDate and $plan->realStartDate>$plan->plannedEndDate) {
        $plan->plannedEndDate=$plan->realStartDate;
      }
      // PBER - #8074 - END
      // if ($profile=='DDUR' and $plan->plannedEndDate and ! $plan->plannedStartDate) $plan->plannedStartDate=$plan->plannedEndDate; // PBER #8812
      if ($profile=='DDUR' and $plan->plannedEndDate and !$plan->plannedStartDate) $plan->plannedStartDate=$startPlan; // PBER #8812
      $fullListPlan=self::storeListPlan($fullListPlan, $plan);
      if (isset($reserved['allPreds'][$plan->id])) {
        foreach ($reserved['W'] as $idPe=>$pe) {
          if (isset($pe['pred'][$plan->id])) {
            $typePred=$pe['pred'][$plan->id]['type'];
            $delayPred=$pe['pred'][$plan->id]['delay'];
            if ($typePred=='E-S') { // TODO : check existing start / end
              $tmpPred=$fullListPlan['#' . $plan->id];
              if ($tmpPred->refType=='Milestone') {
                if ($delayPred>0) {
                  $reserved['W'][$idPe]['start']=addWorkDaysToDate($plan->plannedEndDate, $delayPred+1, $plan->idProject);
                } else {
                  $reserved['W'][$idPe]['start']=addWorkDaysToDate($plan->plannedEndDate, $delayPred, $plan->idProject);
                }
              } else {
                if ($delayPred>=0) {
                  $reserved['W'][$idPe]['start']=addWorkDaysToDate($plan->plannedEndDate, $delayPred+2, $plan->idProject);
                } else {
                  $reserved['W'][$idPe]['start']=addWorkDaysToDate($plan->plannedEndDate, $delayPred+1, $plan->idProject);
                }
              }
            } else if ($typePred=='S-S') {
              if ($delayPred>0) {
                $reserved['W'][$idPe]['start']=addWorkDaysToDate($plan->plannedStartDate, $delayPred+1, $plan->idProject);
              } else { // delay <= 0
                $reserved['W'][$idPe]['start']=addWorkDaysToDate($plan->plannedStartDate, $delayPred, $plan->idProject);
              }
            } else if ($typePred=='E-E') {
              if ($delayPred>0) {
                $reserved['W'][$idPe]['end']=addWorkDaysToDate($plan->plannedEndDate, $delayPred+1, $plan->idProject);
              } else { // delay <= 0
                $reserved['W'][$idPe]['end']=addWorkDaysToDate($plan->plannedEndDate, $delayPred, $plan->idProject);
              }
            }
          }
        }
      }
      if (isset($reserved['W'][$plan->id])) { // remove $reserved when planned for RECW
        foreach ($reserved['W'][$plan->id] as $idRes=>$resRes) {
          if (!is_numeric($idRes)) continue;
          foreach ($resRes as $day=>$val) {
            if (isset($reserved['W']['sum'][$idRes][$day])) {
              $reserved['W']['sum'][$idRes][$day]-=$val;
            }
          }
        }
        unset($reserved['W'][$plan->id]);
      }
      if (isset($reserved['allSuccs'])) {
        // TODO : take into acount E-S dependency to determine end
      }
    }
    // Moved transaction at end of procedure (out of script plan.php) to minimize lock possibilities
    foreach ($fullListPlan as $keyPe=>$pe) {
      if (property_exists($pe, 'fixPlanning') and $pe->fixPlanning) unset($fullListPlan[$keyPe]);
      else if ($pe->idPlanningMode==23) unset($fullListPlan[$keyPe]);
      else {
        if ($pe->refType=='Milestone' and $pe->idPlanningMode==6 and property_exists($pe, '_predecessorListWithParent') and count($pe->_predecessorListWithParent)>0) { // Fixed milestone
          $mileStartCalc=null;
          foreach ($pe->_predecessorListWithParent as $precId=>$precValArray) { // $precValArray = array(dependency delay,dependency type)
            $precVal=$precValArray['delay'];
            $precTyp=$precValArray['type'];
            if (!isset($fullListPlan[$precId])) continue;
            $prec=$fullListPlan[$precId];
            $precEnd=$prec->plannedEndDate;
            $calcDate=addWorkDaysToDate($precEnd, $precVal, $pe->idProject);
            if (!$mileStartCalc or $calcDate>$mileStartCalc) $mileStartCalc=$calcDate;
          }
          if ($mileStartCalc>$pe->plannedStartDate) {
            $arrayWarning['Milestone#' . $pe->refId]=i18n("warningPlanningPredecessorFixed", array(htmlFormatDate($mileStartCalc)));
          }
        }
      }
    }
    // $templateProjectsList=Project::getTemplateList();
    if ($simulation) {
      // $result=array("PlanningElement"=>$fullListPlan,"PlannedWork"=>$arrayPlannedWork,"Assignment"=>$arrayAssignment);
      return "OK";
    }
    debugTraceLog("PLAN - purge planned work");
    Sql::beginTransaction();
    $cpt=0;
    $query='';
    $noPlannedWorkForPrp=true;
    $insertBatchSize=100; // Set to 500 increases Deadloack probability without improving preformance in a measurablke way
    if (!$simulation) $planW->purge($clauseToPurgePlannedWork); // PBER #10281
    debugTraceLog("PLAN - insert planned work ");
    foreach ($arrayPlannedWork as $pw) {
      // if (pq_array_key_exists($pw->idProject, $templateProjectsList)) continue; // Do not save planned work for templates
      if ($noPlannedWorkForPrp and isset($listProjectsType[$pw->idProject]) and ($listProjectsType[$pw->idProject]=='PRP' or $listProjectsType[$pw->idProject]=='TMP')) continue;
      if ($cpt==0) {
        $query='INSERT into ' . $pw->getDatabaseTableName() . ' (idResource,idProject,refType,refId,idAssignment,work,workDate,day,week,month,year,surbooked,surbookedWork)' . ' VALUES ';
      } else {
        $query.=', ';
      }
      $query.='(' . "'" . Sql::fmtId($pw->idResource) . "'," . "'" . Sql::fmtId($pw->idProject) . "'," . "'" . $pw->refType . "'," . "'" . Sql::fmtId($pw->refId) . "'," . "'" . Sql::fmtId($pw->idAssignment) . "'," . "'" . $pw->work . "'," . "'" . $pw->workDate . "'," . "'" . $pw->day . "'," . "'" . $pw->week . "'," . "'" . $pw->month . "'," . "'" . $pw->year . "'," . "'" . $pw->surbooked . "'," . "'" . $pw->surbookedWork . "')";
      $cpt++;
      if ($cpt>=$insertBatchSize) {
        $query.=';';
        SqlDirectElement::execute($query);
        $cpt=0;
        $query='';
      }
    }
    if ($query!='') {
      $query.=';';
      SqlDirectElement::execute($query);
    }
    debugTraceLog("PLAN - save unique resource selected");
    if ($uniqueResourceAssignment!==null) {
      foreach ($uniqueResourceAssignment as $uraAss) {
        foreach ($uraAss as $ura) {
          $select=$ura['select'];
          $ass=$ura['ass'];
          $select->startDate=$ass->plannedStartDate;
          $select->endDate=$ass->plannedEndDate;
          if (isset($ura['SELECTED'])) $select->selected=1;
          else $select->selected=0;
          $select->_noHistory=true;
          $select->save();
        }
      }
    }
    Sql::commitTransaction(); // Commit here, all plannedwork is saved
    debugTraceLog("PLAN - update assignment");
    Sql::beginTransaction(); // PBER #10256 - add commits to reduce deadlocks
    // save Assignment
    $cpt=0;
    // PERF : the same Resource is frequently referenced by many assignments (one resource can be
    // assigned to dozens of activities). Reuse the Resource object instead of re-instantiating
    // (=> re-querying) it for every single assignment ; getActualResourceCost() is still called with
    // the exact same arguments as before, so the returned cost is identical.
    $resourceCacheForCost=array();
    foreach ($arrayAssignment as $ass) {
      $ass->_noHistory=true;
      if ($noPlannedWorkForPrp and isset($listProjectsType[$ass->idProject]) and ($listProjectsType[$ass->idProject]=='PRP' or $listProjectsType[$ass->idProject]=='TMP')) {
        $ass->surbookedWork=0;
        $ass->surbooked=0;
      }
      // PBER - update cost depending on start date
      if (!isset($resourceCacheForCost[$ass->idResource])) {
        $resourceCacheForCost[$ass->idResource]=new Resource($ass->idResource);
      }
      $r=$resourceCacheForCost[$ass->idResource];
      $newCost=$r->getActualResourceCost($ass->idRole, ($ass->realStartDate)?null:$ass->plannedStartDate);
      if ($newCost!=$ass->newDailyCost and !isset($uniqueResourceAssignment[$ass->id])) {
        $ass->newDailyCost=$newCost;
        $ass->leftCost=$ass->leftWork*$newCost;
        $ass->plannedCost=$ass->realCost+$ass->leftCost;
        $ass->save();
      } else {
        // PBER
        $ass->simpleSave(); // Attention ! simpleSave for Assignment will execute direct query
      }
      // PBER #10256 - add commits to reduce deadlocks
      $cpt++;
      if ($cpt>=100) {
        Sql::commitTransaction();
        Sql::beginTransaction();
        $cpt=0;
      }
    }
    Sql::commitTransaction();
    debugTraceLog("PLAN - update planning element");
    Sql::beginTransaction();
    $cpt=0;
    if ($withCriticalPath==1) {
      $projectCriticalPath=[];
      if ($allProjects) {
        $proj=new Project(' ', true);
        $projectCriticalPath=array_keys($proj->getRecursiveSubProjectsFlatList(true, false));
      } else {
        $arrTmp=[];
        foreach ($projectIdArray as $idP) {
          $proj=new Project($idP, true);
          $sub=$proj->getRecursiveSubProjectsFlatList(true, true);
          $arrTmp=array_merge_preserve_keys($arrTmp, $sub);
        }
        $projectCriticalPath=array_keys($arrTmp);
      }
      $paramMethod=Parameter::getGlobalParameter("criticalPathNewMethod");
      $criticalPathMethod=($paramMethod===1 or $paramMethod===true or $paramMethod==='true')?"new":"old";
      if (Tool::afterVersion(Sql::getDbVersion(), "V12.1.9")) $criticalPathMethod="new";
      foreach ($projectCriticalPath as $idP) {
        if ($criticalPathMethod=='old') {
          $startTime=microtime(true);
          $fullListPlan=self::calculateCriticalPath($idP, $fullListPlan);
          $duration=(round(microtime(true)-$startTime, 3));
        } else {
          $startTime=microtime(true);
          self::calculateCriticalPathOptimized($idP, $fullListPlan);
          $duration=(round(microtime(true)-$startTime, 3));
          if ($duration==0) $duration=(round(microtime(true)-$startTime, 4));
        }
      }
    }
    $datesForActivityExpense=array();
    $arrayProj=array();
    foreach ($fullListPlan as $pe) {
      if (property_exists($pe, 'fixPlanning') and $pe->fixPlanning) continue;
      if (property_exists($pe, '_noPlan') and $pe->_noPlan==1) continue;
      if (!$pe->refType) continue;
      if ($noPlannedWorkForPrp and isset($listProjectsType[$pe->idProject]) and ($listProjectsType[$pe->idProject]=='PRP' or $listProjectsType[$pe->idProject]=='TMP')) {
        $pe->surbookedWork=0;
        $pe->surbooked=0;
      }
      if (!$withCriticalPath) $pe->isOnCriticalPath=0;
      if ($pe->refType!='Project' and $pe->idProject) $arrayProj[$pe->idProject]=$pe->idProject;
      if ($pe->refType=='Project' and $pe->refId) $arrayProj[$pe->refId]=$pe->refId;
      $pe->inheritedEndDate=$pe->_expectedEndDate??null;
      $pe->inheritedEndSource=$pe->_expectedEndSource??null;
      if ($pe->validatedEndDate and $pe->elementary) {
        $pe->inheritedEndDate=null;
        $pe->inheritedEndSource=null;
      }
      if ($pe->validatedEndDate and !$pe->elementary and (!property_exists($pe, '_storedValidatedEndDate') or $pe->_storedValidatedEndDate)) {
        $pe->inheritedEndDate=null;
        $pe->inheritedEndSource=null;
      }
      if (Parameter::getGlobalParameter('gestionInheritedEndDate')=='NO') {
        $pe->inheritedEndDate=null;
        $pe->inheritedEndSource=null;
      }
      $pe->quickplanStartDate=null;
      $pe->quickplanEndDate=null;
      $pe->quickplanUpdated=0;
      if ($pe->inheritedEndDate=='N/A') {
        $pe->inheritedEndDate=null;
        $pe->inheritedEndSource=null;
      }
      if ( (property_exists($pe, '_profile') and $pe->_profile=='RECW') or property_exists($pe, '_hasProportional')) {
        $pe->_noHistory=true;
        $resPe=$pe->simpleSave();
        PlanningElement::updateSynthesis($pe->refType, $pe->refId);
      } else {
        $pe->_noHistory=true;
        $resPe=$pe->simpleSave(); // Attention ! simpleSave for PlanningElement will execute direct query
      }
      if ($pe->refType=='Milestone' and method_exists($pe, "updateMilestonableItems")) {
        $pe->updateMilestonableItems();
      }
      if ($pe->refType=='Activity') {
        if (!isset($datesForActivityExpense[$pe->refId])) {
          $datesForActivityExpense[$pe->refId]=array();
        }
        $datesForActivityExpense[$pe->refId]['plannedStartDate']=$pe->plannedStartDate;
        $datesForActivityExpense[$pe->refId]['plannedEndDate']=$pe->plannedEndDate;
        $daysDiff=round(dayDiffDates($pe->plannedStartDate, $pe->plannedEndDate)/2);
        $medianDate=addDaysToDate($pe->plannedStartDate, $daysDiff);
        // Option not provided: if the automatically calculated date falls on a public holiday, take the first working day following.
        // if(isOffDay($medianDate)){
        // while(isOffDay($medianDate)){
        // $medianDate = addDaysToDate($medianDate, 1);
        // }
        // }
        $datesForActivityExpense[$pe->refId]['plannedMedianDate']=$medianDate;
      }
      // PBER #10256 - add commits to reduce deadlocks
      $cpt++;
      if ($cpt>=100) {
        Sql::commitTransaction();
        Sql::beginTransaction();
        $cpt=0;
      }
    }
    Sql::commitTransaction(); // Commit here, all planningelement items are saved
    debugTraceLog("PLAN - insert history");
    Sql::beginTransaction(); // PBER #10256 - add commits to reduce deadlocks
    // Reset QuickPlan Values
    $pe=new PlanningElement();
    $peTable=$pe->getDatabaseTableName();
    $query="UPDATE $peTable " . " SET quickplanStartDate=null, quickplanEndDate=null, quickplanUpdated=0 " . " WHERE (quickplanStartDate is not null or quickplanEndDate is not null or quickplanUpdated=1) and $clauseToResetQuickPlan ;";
    SqlDirectElement::execute($query);
    Sql::commitTransaction(); // Commit here, all planningelement items are saved
    Sql::beginTransaction(); // PBER #10256 - add commits to reduce deadlocks
    foreach ($arrayProj as $idP) {
      Project::unsetNeedReplan($idP);
      // Save history for planning operation
      $hist=new History();
      $hist->idUser=getCurrentUserId();
      $hist->newValue=null;
      $hist->operationDate=date('Y-m-d H:i:s');
      $hist->operation="plan";
      $hist->refType='Project';
      $hist->refId=$idP;
      $hist->isWorkHistory=1;
      $resHist=$hist->save();
    }
    $messageOn=false;
    $endTime=time();
    $endMicroTime=microtime(true);
    $endOperation=date('Y-m-d H:i:s');
    $duration=round(($endMicroTime-$startMicroTime)*1000)/1000;
    if (count($arrayNotPlanned)>0 or count($arrayWarning)>0 or self::$_technicalErrors) {
      $result=i18n('planDoneWithLimits', array($duration));
      $result.='<br/><br/><table style="width:100%">';
      $result.='<tr style="color:#888888;font-weight:bold;border:1px solid #aaaaaa"><td style="width:40%">' . i18n('colElement') . '</td><td style="width:40%">' . i18n('colCause') . '</td><td style="width:20%">' . i18n('colIdResource') . '</td></tr>';
      foreach ($arrayNotPlanned as $assId=>$left) {
        $ass=new Assignment($assId, true);
        $rName=SqlList::getNameFromId('ResourceAll', $ass->idResource);
        $oName=SqlList::getNameFromId($ass->refType, $ass->refId);
        $msg=(is_numeric($left))?i18n('colNotPlannedWork') . ' : ' . Work::displayWorkWithUnit($left):$left;
        $result.='<tr style="border:1px solid #aaaaaa;"><td style="padding:1px 10px;">' . i18n($ass->refType) . ' #' . htmlEncode($ass->refId) . ' : ' . $oName . '</td><td style="padding:1px 10px;">' . $msg . '</td><td style="padding:1px 10px;">' . $rName . '</td></tr>';
      }
      foreach ($arrayWarning as $assId=>$msg) {
        if (pq_substr($assId, 0, 10)=='Milestone#') {
          $rName=null;
          $id=pq_substr($assId, 10);
          $oName=SqlList::getNameFromId('Milestone', $id);
          $ass=new Assignment();
          $ass->refType='Milestone';
          $ass->refId=$id;
        } else {
          $ass=new Assignment($assId, true);
          $rName=SqlList::getNameFromId('ResourceAll', $ass->idResource);
          $oName=SqlList::getNameFromId($ass->refType, $ass->refId);
        }
        $result.='<tr style="border:1px solid #aaaaaa;"><td style="padding:1px 10px;">' . i18n($ass->refType) . ' #' . htmlEncode($ass->refId) . ' : ' . $oName . '</td><td style="padding:1px 10px;">' . $msg . '</td><td style="padding:1px 10px;">' . $rName . '</td></tr>';
      }
      if (self::$_technicalErrors) {
        foreach (self::$_technicalErrors as $err) {
          $oName=SqlList::getNameFromId($err['refType'], $err['refId']);
          $result.='<tr style="border:1px solid #aaaaaa;"><td style="padding:1px 10px;">' . i18n($err['refType']) . ' #' . $err['refId'] . ' : ' . $oName . '</td><td style="padding:1px 10px;">' . $err['msg'] . '</td><td style="padding:1px 10px;">-</td></tr>';
        }
      }
      $result.='</table>';
      $result.='<input type="hidden" id="lastPlanStatus" value="INCOMPLETE" />';
    } else {
      $result=i18n('planDone', array($duration));
      $result.='<input type="hidden" id="lastPlanStatus" value="OK" />';
    }
    // Activity Expense : update target date (planned) from Planning of Activity
    if (count($datesForActivityExpense)>0) {
      $idActivityExpenseType=SqlList::getIdFromName('Type', 'Expense activity');
      $activityExpense=new ActivityExpense();
      $where="idle = 0 and idActivity in " . transformListIntoInClause($datesForActivityExpense);
      $activityExpenseList=$activityExpense->getSqlElementsFromCriteria(null, null, $where);
      foreach ($activityExpenseList as $actExp) {
        $paymentDateMode=new PaymentDateMode($actExp->idPaymentDateMode);
        switch ($paymentDateMode->name) {
          case "paymentStartDateMode" :
            $actExp->expensePlannedDate=$datesForActivityExpense[$actExp->idActivity]['plannedStartDate'];
            break;
          case "paymentMedianDateMode" :
            $actExp->expensePlannedDate=$datesForActivityExpense[$actExp->idActivity]['plannedMedianDate'];
            break;
          case "paymentEndDateMode" :
            $actExp->expensePlannedDate=$datesForActivityExpense[$actExp->idActivity]['plannedEndDate'];
            break;
        }
        $actExp->save();
      }
    }
    
    // Moved transaction at end of procedure (out of script plan.php) to minimize lock possibilities
    $status=getLastOperationStatus($result);
    // Save PlanningHistory
    $PlHist=new PlanningHistory();
    $PlHist->date=date('Y-m-d H:i:s');
    $PlHist->idUser=getCurrentUserId();
    $PlHist->projects=$projectPlHist;
    $PlHist->startDate=$startOperation;
    $PlHist->startTime=$startMicroTime;
    $PlHist->endTime=$endMicroTime;
    $PlHist->result=$status;
    $PlHist->resultDescription=$result;
    $resPlHist=$PlHist->save();
    // PBER #10256 - add commits to reduce deadlocks - Always commit (no need to rollback
    // if ($status == "OK" or $status=="NO_CHANGE" or $status=="INCOMPLETE") {
    Sql::commitTransaction();
    // } else {
    // Sql::rollbackTransaction ();
    // }
    if (!$cronnedScript) {
      // echo '<div class="message' . $status . '" >' . $result . '</div>';
      $status=getLastOperationStatus($result);
      displayOKKOStatus($status, $result);
    }
    self::$_planningInProgress=false;
    // PBER : reinit global arrays
    $arrayPlannedWork=array();
    $arrayRealWork=array();
    $arrayAssignment=array();
    $arrayPlanningElement=array();
    $listPlan=array();
    $fullListPlan=array();
    $resources=array();
    $topList=array();
    $reserved=array();
    $arrayNotPlanned=array();
    $arrayWarning=array();
    $inClauseStored=null;
    $clauseToPurgePlannedWork=null;
    self::$_surbookedWorkStored=array();
    debugTraceLog("PLAN - end");
    return $result;
  }
  
  public static function enterPlannedWorkAsReal($projectIdArray, $startDatePlan) {
    global $cronnedScript;
    $resources=array();
    if (!$cronnedScript) {
      traceLog("enterPlannedWorkAsReal must be called only for cronned calculation");
      return;
    }
    $crit="workDate<'$startDatePlan'";
    if ($projectIdArray!=null and is_array($projectIdArray)) {
      $crit.=" and idProject in " . transformListIntoInClause($projectIdArray);
    }
    $pw=new PlannedWork();
    $pwList=$pw->getSqlElementsFromCriteria(null, false, $crit);
    $arrayAss=array(); // Will store work to remove from left
    $arrayPe=array(); // Will store real start and real end
    foreach ($pwList as $pw) {
      $work=new Work();
      if (isset($resources[$pw->idResource])) {
        $ress=$resources[$pw->idResource];
      } else {
        $r=new Resource($pw->idResource, true);
        $ress=array('isteam'=>$r->isResourceTeam, 'dates'=>array());
        $resources[$pw->idResource]=$ress;
      }
      if (isset($ress['dates'][$pw->workDate])) {
        $haswork=$ress['dates'][$pw->workDate];
      } else {
        $cpt=$work->countSqlElementsFromCriteria(array('idResource'=>$pw->idResource, 'workDate'=>$pw->workDate));
        if ($cpt==0) {
          $haswork=0;
        } else {
          $haswork=1;
        }
        $resources[$pw->idResource]['dates'][$pw->workDate]=$haswork;
      }
      if ($ress['isteam']) {
        continue; // don't enter work planned on Pool
      }
      if ($haswork) {
        continue; // some work exist
      }
      $work->idResource=$pw->idResource;
      $work->idProject=$pw->idProject;
      $work->refType=$pw->refType;
      $work->refId=$pw->refId;
      $work->idAssignment=$pw->idAssignment;
      $work->work=$pw->work;
      $work->workDate=$pw->workDate;
      $work->day=$pw->day;
      $work->week=$pw->week;
      $work->month=$pw->month;
      $work->year=$pw->year;
      $work->dailyCost=$pw->dailyCost;
      $work->cost=$pw->cost;
      $resWork=$work->save();
      if (!isset($arrayAss[$pw->idAssignment])) $arrayAss[$pw->idAssignment]=array(
          'work'=>0,
          'start'=>$pw->workDate,
          'end'=>$pw->workDate);
      $arrayAss[$pw->idAssignment]['work']+=$work->work; // Work to remove from left work
      // if ($pw->workDate<$arrayAss[$pw->idAssignment]['start']) $arrayAss[$pw->idAssignment]['start']=$pw->workDate;
      // if ($pw->workDate>$arrayAss[$pw->idAssignment]['end']) $arrayAss[$pw->idAssignment]['end']=$pw->workDate;
    }
    // Update assiognements to remove left work
    foreach ($arrayAss as $assId=>$assAr) {
      $ass=new Assignment($assId);
      $left=$ass->leftWork-$assAr['work'];
      if ($left<0) $left=0;
      $ass->leftWork=$left;
      // if (! $ass->realStartDate or $assAr['start']<$ass->realStartDate) $ass->realStartDate=$assAr['start'];
      // if ($left==0 and (!$ass->realEndDate or $assAr['end']>$ass->realEndDate)) $ass->realEndDate=$assAr['end'];
      $resAss=$ass->saveWithRefresh();
    }
  }
  
  // End of PLAN
  // ================================================================================================================================
  
  // Functions for PLAN
  
  // Will constitute an array $reserved to be sure to reserve the availability of tasks as RECW that will be planned "after" predecessors to get start and end
  // $reserved[type='W'][idPE][idResource][day]=value // sum of work to reserve for resource on week day for a given task
  // $reserved[type='W'][idPE]['start']=date // start date, that will be set when known
  // $reserved[type='W'][idPE]['end']=date // end date, that will be set when known
  // $reserved[type='W'][idPE]['pred'][idPE]['id']=idPE // id of precedessor PlanningElement
  // $reserved[type='W'][idPE]['pred'][idPE]['delay']=delay // Delay of dependency
  // $reserved[type='W'][idPE]['pred'][idPE]['type']=type // type of dependency (E-E, E-S, S-S)
  // $reserved[type='W'][idPE]['succ'][idPE]['id']=idPE // id of successor PlanningElement
  // $reserved[type='W'][idPE]['succ'][idPE]['delay']=delay // Delay of dependency
  // $reserved[type='W'][idPE]['succ'][idPE]['type']=type // type of dependency (E-E, E-S, S-S)
  // $reserved[type='W']['sum'][idResource][day]=value // sum of work to reserve for resource on week day
  // $reserved['allPreds'][idPE]=idPE // List of all PE who are predecessors of RECW task
  // $reserved['allSuccs'][idPE]=idPE // List of all PE who are successors of RECW task
  private static function storeReservedForRecurring() {
    global $listPlan, $reserved, $listProjectsType, $listProjectsDelay;
    $memberOf=array();
    $poolMembers=array();
    foreach ($listPlan as $plan) { // Store RECW to reserve avaialbility
      $projType=(isset($listProjectsType[$plan->idProject]))?$listProjectsType[$plan->idProject]:'';
      // if ($projType=='PRP' or $projType=='TMP') continue;
      if (property_exists($plan, '_profile') and $plan->_profile=='RECW') { // $plan->_profile may not be set for top Project when calculating for all project (then $plan->id is null)
        $ar=new AssignmentRecurring();
        $artype=pq_substr($plan->_profile, -1);
        $arList=$ar->getSqlElementsFromCriteria(array('refType'=>$plan->refType, 'refId'=>$plan->refId, 'type'=>$artype));
        if (!isset($reserved[$artype])) $reserved[$artype]=array();
        if (!isset($reserved[$artype][$plan->id])) $reserved[$artype][$plan->id]=array();
        if (!isset($reserved[$artype]['sum'])) $reserved[$artype]['sum']=array();
        $reserved[$artype][$plan->id]['typeProject']=$projType;
        $reserved[$artype][$plan->id]['idProject']=$plan->idProject;
        foreach ($arList as $ar) {
          if (!isset($reserved[$artype][$plan->id][$ar->idResource])) $reserved[$artype][$plan->id][$ar->idResource]=array();
          if (!isset($reserved[$artype]['sum'][$ar->idResource])) $reserved[$artype]['sum'][$ar->idResource]=array();
          $reserved[$artype][$plan->id][$ar->idResource][$ar->day]=$ar->value;
          if (!isset($reserved[$artype]['sum'][$ar->idResource][$ar->day])) $reserved[$artype]['sum'][$ar->idResource][$ar->day]=0;
          $reserved[$artype]['sum'][$ar->idResource][$ar->day]+=$ar->value;
          if (!isset($reseved[$artype][$plan->id]['assignments'])) $reseved[$artype][$plan->id]['assignments']=array();
          $reseved[$artype][$plan->id]['assignments'][$ar->idAssignment]=$ar->idAssignment;
          // Get Pools the Resource is member Of
          if (!isset($memberOf[$ar->idResource])) {
            $memberOf[$ar->idResource]=array();
            $rta=new ResourceTeamAffectation();
            $rtaList=$rta->getSqlElementsFromCriteria(array('idResource'=>$ar->idResource, 'idle'=>'0'));
            foreach ($rtaList as $rta) {
              $memberOf[$ar->idResource][]=$rta->idResourceTeam;
            }
          }
          foreach ($memberOf[$ar->idResource] as $idResourceTeam) {
            if (!isset($reserved[$artype]['sum'][$idResourceTeam])) $reserved[$artype]['sum'][$idResourceTeam]=array();
            if (!isset($reserved[$artype]['sum'][$idResourceTeam][$ar->day])) $reserved[$artype]['sum'][$idResourceTeam][$ar->day]=0;
            $reserved[$artype]['sum'][$idResourceTeam][$ar->day]+=$ar->value;
            // Also expand the per-planning-element reservation to the Pool(s) the resource is member of : an activity
            // planned directly on the Pool (e.g. a DDUR/CDUR one) must see this recurring reservation too, otherwise
            // it never respects/overrides it and never gets flagged as surbooked, leaving no room for the recurring activity
            if (!isset($reserved[$artype][$plan->id][$idResourceTeam])) $reserved[$artype][$plan->id][$idResourceTeam]=array();
            if (!isset($reserved[$artype][$plan->id][$idResourceTeam][$ar->day])) $reserved[$artype][$plan->id][$idResourceTeam][$ar->day]=0;
            $reserved[$artype][$plan->id][$idResourceTeam][$ar->day]+=$ar->value;
          }
          // If the recurring activity is itself assigned to a Pool, also push the reservation down to its current
          // members : an activity planned directly on a member (e.g. a DDUR/CDUR one) must see this recurring
          // reservation too, otherwise it never respects/overrides it and never gets flagged as surbooked
          if (!isset($poolMembers[$ar->idResource])) {
            $poolMembers[$ar->idResource]=array();
            $rtaDown=new ResourceTeamAffectation();
            $rtaDownList=$rtaDown->getSqlElementsFromCriteria(array('idResourceTeam'=>$ar->idResource, 'idle'=>'0'));
            foreach ($rtaDownList as $rtaDown) {
              $poolMembers[$ar->idResource][]=$rtaDown->idResource;
            }
          }
          foreach ($poolMembers[$ar->idResource] as $idMemberResource) {
            if (!isset($reserved[$artype]['sum'][$idMemberResource])) $reserved[$artype]['sum'][$idMemberResource]=array();
            if (!isset($reserved[$artype]['sum'][$idMemberResource][$ar->day])) $reserved[$artype]['sum'][$idMemberResource][$ar->day]=0;
            $reserved[$artype]['sum'][$idMemberResource][$ar->day]+=$ar->value;
            if (!isset($reserved[$artype][$plan->id][$idMemberResource])) $reserved[$artype][$plan->id][$idMemberResource]=array();
            if (!isset($reserved[$artype][$plan->id][$idMemberResource][$ar->day])) $reserved[$artype][$plan->id][$idMemberResource][$ar->day]=0;
            $reserved[$artype][$plan->id][$idMemberResource][$ar->day]+=$ar->value;
          }
        }
        $reserved[$artype][$plan->id]['start']=null;
        $reserved[$artype][$plan->id]['end']=null;
        $reserved[$artype][$plan->id]['pred']=array();
        $reserved[$artype][$plan->id]['succ']=array();
        $reserved[$artype][$plan->id]['idProj']=$plan->idProject;
        $crit="successorId=$plan->id or predecessorId=$plan->id";
        $dep=new Dependency();
        $depList=$dep->getSqlElementsFromCriteria(null, false, $crit);
        foreach ($depList as $dep) {
          if ($dep->successorId==$plan->id) {
            if (isset($listPlan['#' . $dep->predecessorId])) {
              $pred=$listPlan['#' . $dep->predecessorId];
              $predEnd=$pred->validatedEndDate;
              if (isset($listProjectsDelay[$plan->idProject])) $predEnd=shiftValidatedDate($predEnd, $listProjectsDelay[$plan->idProject]);
              // If predecessor is a fixed milestone or floating milestone without predecessor, we can guess the end of RECW
              if ($pred->refType=='Milestone' and $pred->validatedEndDate and ($pred->_profile=='FIXED' or ($pred->_profile=='FLOAT' and count($pred->_directPredecessorList)==0))) {
                if ($dep->dependencyType=='E-S' or $dep->dependencyType=='S-S') {
                  if ($dep->dependencyDelay>0) {
                    $reserved[$artype][$plan->id]['start']=addWorkDaysToDate($predEnd, $dep->dependencyDelay+1, $plan->idProject);
                  } else {
                    $reserved[$artype][$plan->id]['start']=addWorkDaysToDate($predEnd, $dep->dependencyDelay, $plan->idProject);
                  }
                } else if ($dep->dependencyType=='E-E') {
                  if ($dep->dependencyDelay>0) {
                    $reserved[$artype][$plan->id]['end']=addWorkDaysToDate($predEnd, $dep->dependencyDelay+1, $plan->idProject);
                  } else {
                    $reserved[$artype][$plan->id]['end']=addWorkDaysToDate($predEnd, $dep->dependencyDelay, $plan->idProject);
                  }
                }
              }
            }
            $reserved[$artype][$plan->id]['pred'][$dep->predecessorId]=array(
                'id'=>$dep->predecessorId,
                'delay'=>$dep->dependencyDelay,
                'type'=>$dep->dependencyType);
            $reserved['allPreds'][$dep->predecessorId]=$dep->predecessorId;
          }
          if ($dep->predecessorId==$plan->id) {
            $reserved[$artype][$plan->id]['succ'][$dep->successorId]=array(
                'id'=>$dep->successorId,
                'delay'=>$dep->dependencyDelay,
                'type'=>$dep->dependencyType);
            $reserved['allSuccs'][$dep->successorId]=$dep->successorId;
          }
        }
      }
    }
  }
  
  // =============================================================================================================================
  // Calculate Critical Path
  // Version optimize - Proposal from ChatGPT
  public static function calculateCriticalPathOptimized($projectId, &$fullListPlan) {
    $peProj=null;
    $today=date('Y-m-d');
    $tasks=[];
    foreach ($fullListPlan as $id=>$pe) {
      if ($pe->realEndDate) continue; // do not include ended tasks
      if ($pe->plannedEndDate<$today) continue; // do not include expected ended tasks
      if ($pe->idle or $pe->cancelled) continue; // do not include idle and cancelled tasks
      if ($pe->paused) continue; // do not include paused tasks / paused cannot be on the critical path
      if ($pe->refType=='Project' and $pe->refId==$projectId) $peProj=$pe;
      else if (($pe->refType!='Project' or $pe->refId!=$projectId) and $pe->idProject==$projectId) {
        // $pe->_predecessorForCriticalPath = $pe->_directPredecessorList;
        // $pe->_predecessorForCriticalPath = $pe->_predecessorListWithParent;
        $pe->_predecessorForCriticalPath=Self::getPredecessors($id, $fullListPlan);
        $tasks[$id]=$pe;
        $fullListPlan[$id]->isOnCriticalPath=0;
      }
    }
    if (!$tasks) return [];
    
    $graph=[];
    $indegree=[];
    $delay=[];
    
    foreach ($tasks as $id=>$pe) {
      $graph[$id]=[];
      $indegree[$id]=0;
    }
    
    // Graphe des dépendances
    foreach ($tasks as $id=>$pe) {
      $dependencies=$pe->_predecessorForCriticalPath;
      foreach ($dependencies as $predId=>$dep) {
        if ($dep['type']=='E-S') $delay[$predId . $id]=$dep['delay'];
        else continue;
        if (isset($graph[$predId])) {
          $graph[$predId][]=$id;
          $indegree[$id]++;
        }
      }
    }
    
    // Tri topologique (Kahn)
    $queue=[];
    foreach ($indegree as $id=>$deg) {
      if ($deg==0) $queue[]=$id;
    }
    
    $sorted=[];
    while (!empty($queue)) {
      $current=array_shift($queue);
      $sorted[]=$current;
      foreach ($graph[$current] as $next) {
        $indegree[$next]--;
        if ($indegree[$next]==0) $queue[]=$next;
      }
    }
    
    if (count($sorted)<count($tasks)) {
      errorLog("Infinite dependency loop detected on Project #$projectId");
      return [];
    }
    
    // Forward pass
    $ES=[];
    $EF=[];
    foreach ($sorted as $id) {
      $es=0;
      $dependencies=$tasks[$id]->_predecessorForCriticalPath;
      foreach ($dependencies as $predId=>$dep) {
        if (isset($EF[$predId])) {
          $es=max($es, $EF[$predId]+$dep['delay']-((isset($tasks[$predId]) and $tasks[$id]->refType!='Milestone' and $tasks[$predId]->refType=='Milestone')?1:0));
        }
      }
      $ES[$id]=$es;
      $duration=(float)$tasks[$id]->plannedDuration;
      if ($duration==0 and $tasks[$id]->refType=='Milestone') $duration=1; // Cas of milestones
      if ($tasks[$id]->plannedStartDate<$today or ($tasks[$id]->realStartDate and $tasks[$id]->realStartDate<$today)) {
        $duration=workDayDiffDates($today, $tasks[$id]->plannedEndDate, $projectId);
      }
      $EF[$id]=$es+$duration;
    }
    
    // Backward pass
    $LF=[];
    $LS=[];
    $projectEnd=max($EF);
    // if ($peProj) $projectEnd = (float)$peProj->plannedDuration;
    $reversed=array_reverse($sorted);
    foreach ($reversed as $id) {
      $lf=$projectEnd;
      foreach ($graph[$id] as $succId) {
        if (isset($LS[$succId])) {
          $lf=min($lf, $LS[$succId]-$delay[$id . $succId]+((isset($tasks[$succId]) and $tasks[$id]->refType=='Milestone' and $tasks[$succId]->refType!='Milestone')?1:0)??0);
        }
      }
      if (empty($graph[$id])) $lf=$projectEnd;
      $LF[$id]=$lf;
      $duration=(float)$tasks[$id]->plannedDuration;
      if ($duration==0 and $tasks[$id]->refType=='Milestone') $duration+=1; // Cas of milestones
      if ($tasks[$id]->plannedStartDate<$today or ($tasks[$id]->realStartDate and $tasks[$id]->realStartDate<$today)) {
        $duration=workDayDiffDates($today, $tasks[$id]->plannedEndDate, $projectId);
      }
      $LS[$id]=$lf-$duration;
    }
    
    // debugTraceLog(" "); foreach($ES as $id=>$val) { debugTraceLog($tasks[$id]->refName." | E ".$ES[$id]."-".$EF[$id]." | L ".$LS[$id]."-".$LF[$id]); }
    // Tâches critiques = celles avec float 0
    $criticalPath=[];
    foreach ($tasks as $id=>$pe) {
      $float=$LS[$id]-$ES[$id];
      if (round($float, 2)<=0.01) {
        $fullListPlan[$id]->isOnCriticalPath=1;
        $criticalPath[]=$id;
      }
    }
    return $criticalPath;
  }
  
  private static function getPredecessors($id, &$fullListPlan) {
    if (!isset($fullListPlan[$id])) return [];
    $pe=$fullListPlan[$id];
    if (!$pe) return [];
    $predList=[];
    if (!property_exists($pe, "_predecessorListWithParent")) return $predList;
    foreach ($pe->_predecessorListWithParent as $idPred=>$dep) {
      if ($dep['type']=='E-S') {
        $predList[$idPred]=$dep;
      } else if ($dep['type']=='S-S') {
        $predList=array_merge_preserve_keys($predList, self::getPredecessors($idPred, $fullListPlan));
      } else if ($dep['type']=='E-E') {
        // continue;
      }
    }
    return $predList;
  }
  
  // Calculate Critical Path : after planning is calculated, re-claculate reversed from end
  // then critical path are tasks that give save start date as forward planning
  private static function calculateCriticalPath($idProject, $fullListPlan) {
    // return $fullListPlan;
    if (!pq_trim($idProject) or $idProject=='*') return $fullListPlan;
    if (!$fullListPlan or count($fullListPlan)==0) return $fullListPlan;
    $projectStart=null;
    $projectEnd=null;
    $peList=array();
    $path=array();
    // Determine Start and end of Project and keep only tasks of 1 and 1 only project
    foreach ($fullListPlan as $id=>$plan) {
      if ($plan->idProject==$idProject and $plan->refType!='Project' and $plan->elementary==1) {
        $peList[$id]=$plan;
        $fullListPlan[$id]->isOnCriticalPath=0;
        $fullListPlan[$id]->latestStart=null;
        $fullListPlan[$id]->latestEnd=null;
      }
      if ($plan->refType=='Project' and $plan->refId==$idProject) {
        $projectStart=$plan->plannedStartDate;
        $projectEnd=$plan->plannedEndDate;
      }
    }
    $last=array();
    foreach ($peList as $id=>$plan) {
      if ($plan->plannedEndDate==$projectEnd) {
        self::getPathsForTask($id, $peList, $path);
        $last[]=$id;
      }
    }
    foreach ($last as $id) {
      $critPathList=$path[$id];
      // if (1) { $critPath=$critPathList[count($critPathList)-1]; // Option 1 : calculate critical path only for longest path
      foreach ($critPathList as $critPath) { // Option 2 : loop to calculate critical path for each branch
        $isOnCriticalPath=true;
        $start='';
        $end='';
        foreach ($critPath as $idCrit=>$data) {
          $type=$data['type'];
          $delay=intval($data['delay']);
          $item=$fullListPlan[$idCrit];
          if (!$type) {
            $start=$item->plannedStartDate;
            $end=$item->plannedEndDate;
          } else if ($item->refType=='Milestone') {
            if ($item->realEndDate) { // Done milestone
              $start=$item->realEndDate;
              $end=$item->realEndDate;
            } else if ($item->idPlanningMode==6) { // Fix milestone
              $start=$item->validatedEndDate;
              $end=$item->validatedEndDate;
            } else { // floating milestone
              // $start=$start;
              $end=addWorkDaysToDate($start, ($delay*(-1)));
              $start=$end;
            }
          } else if ($type=='E-S') {
            $end=addWorkDaysToDate($start, (1+$delay)*(-1));
            $start=addWorkDaysToDate($end, (intval($item->plannedDuration)-1)*(-1));
          } else if ($type=='E-E') {} else if ($type=='S-S') {
            // $start=$start;
            // $end=addWorkDaysToDate($start, ($item->plannedDuration));
          }
          if ($start<=$projectStart) $isOnCriticalPath=true;
          if (!$item->latestStart or $start<$item->latestStart) $fullListPlan[$idCrit]->latestStart=$start;
          if (!$item->latestEnd or $end<$item->latestEnd) $fullListPlan[$idCrit]->latestEnd=$end;
        }
        
        if ($isOnCriticalPath) {
          foreach ($critPath as $idCrit=>$nameCrit) {
            if ($fullListPlan[$idCrit]->latestStart==$fullListPlan[$idCrit]->plannedStartDate and $fullListPlan[$idCrit]->latestEnd==$fullListPlan[$idCrit]->plannedEndDate) $fullListPlan[$idCrit]->isOnCriticalPath=1;
          }
        }
      }
    }
    return $fullListPlan;
  }
  
  private static function getPathsForTask($id, $peList, &$path, $type=null, $delay=null, $succ='') {
    if (isset($path[$id])) return;
    if (!isset($peList[$id])) return;
    $plan=$peList[$id];
    $path[$id . $succ]=array(array($id=>array('name'=>$plan->refName, 'type'=>$type, 'delay'=>$delay)));
    if (!property_exists($plan, '_directPredecessorList') or !is_array($plan->_directPredecessorList)) return;
    foreach ($plan->_directPredecessorList as $idp=>$datap) {
      $typep=$datap['type'];
      $delayp=$datap['delay'];
      self::getPathsForTask($idp, $peList, $path, $typep, $delayp, $id);
      if (isset($path[$idp . $id])) {
        foreach ($path[$idp . $id] as $arrp)
          $path[$id . $succ][]=array_merge($path[$id . $succ][0], $arrp);
      }
    }
  }
  
  private static function calculateCriticalPathOld($idProject, $fullListPlan) {
    if (!pq_trim($idProject) or $idProject=='*') return $fullListPlan;
    $start=null;
    $end=null;
    $arrayNode=array('early'=>null, 'late'=>null, 'before'=>array(), 'after'=>array());
    $arrayTask=array('duration'=>null, 'start'=>null, 'end'=>null, 'type'=>'task', 'class'=>'', 'name'=>'', 'mode'=>'');
    if ($fullListPlan) {
      $peList=array();
      foreach ($fullListPlan as $id=>$plan) {
        if ($plan->idProject==$idProject and $plan->refType!='Project') {
          $peList[$id]=$plan;
        }
        if ($plan->refType=='Project' and $plan->refId==$idProject) {
          $start=$plan->plannedStartDate;
          $end=$plan->plannedEndDate;
        }
      }
    } else {
      $pe=new PlanningElement();
      $peList=$pe->getSqlElementsFromCriteria(null, null, "(idProject=$idProject and refType!='Project') or ( refType=='Project' and refId=$idProject)", "wbsSortable asc", true);
      foreach ($peList as $id=>$plan) {
        if ($plan->refType=='Project' and $plan->refId==$idProject) {
          $start=$plan->plannedStartDate;
          $end=$plan->plannedEndDate;
          unset($peList[$id]);
          break;
        }
      }
      // TODO : get predecessors
    }
    $cp=array('node'=>array(), 'task'=>array());
    $cp['node']['S']=$arrayNode;
    $cp['node']['S']['early']=$start;
    $cp['node']['E']=$arrayNode;
    $cp['node']['E']['early']=$end;
    $cp['node']['E']['late']=$end;
    foreach ($peList as $id=>$plan) {
      $cp['task'][$id]=$arrayTask;
      $cp['task'][$id]['duration']=workDayDiffDates($plan->plannedStartDate, $plan->plannedEndDate, $plan->idProject); // $plan->plannedDuration;
      $cp['task'][$id]['name']=$plan->refName;
      $cp['task'][$id]['class']=$plan->refType;
      $cp['task'][$id]['start']='S' . $id;
      if (!isset($cp['node']['S' . $id])) $cp['node']['S' . $id]=$arrayNode;
      $cp['node']['S' . $id]['early']=$plan->plannedStartDate;
      if (!in_array($id, $cp['node']['S' . $id]['after'])) $cp['node']['S' . $id]['after'][]=$id;
      $cp['task'][$id]['end']='E' . $id;
      if (!isset($cp['node']['E' . $id])) $cp['node']['E' . $id]=$arrayNode;
      $cp['node']['E' . $id]['early']=$plan->plannedEndDate;
      if (!in_array($id, $cp['node']['E' . $id]['before'])) $cp['node']['E' . $id]['before'][]=$id;
      if (property_exists($plan, '_directPredecessorList')) foreach ($plan->_directPredecessorList as $idPrec=>$prec) {
        if (!isset($peList[$idPrec])) continue; // Predecessor not in current project
        if (!isset($cp['task'][$idPrec . '-' . $id])) $cp['task'][$idPrec . '-' . $id]=$arrayTask;
        $cp['task'][$idPrec . '-' . $id]['type']='dependency';
        if ($peList[$idPrec]->refType=='Milestone' or $prec['type']=='S-S' or $prec['type']=='E-E') {
          $cp['task'][$idPrec . '-' . $id]['duration']=$prec['delay'];
        } else {
          $cp['task'][$idPrec . '-' . $id]['duration']=$prec['delay']+1;
        }
        $typS=pq_substr($prec['type'], 0, 1);
        $typE=pq_substr($prec['type'], -1);
        if ($prec['type']!='E-E') {
          $cp['task'][$idPrec . '-' . $id]['start']=$typS . $idPrec;
          if (!isset($cp['node'][$typS . $idPrec])) $cp['node'][$typS . $idPrec]=$arrayNode;
          if (!in_array($idPrec . '-' . $id, $cp['node'][$typS . $idPrec]['after'])) $cp['node'][$typS . $idPrec]['after'][]=$idPrec . '-' . $id;
          $cp['task'][$idPrec . '-' . $id]['end']=$typE . $id;
          if (!isset($cp['node'][$typE . $id])) $cp['node'][$typE . $id]=$arrayNode;
          if (!in_array($idPrec . '-' . $id, $cp['node'][$typE . $id]['before'])) $cp['node'][$typE . $id]['before'][]=$idPrec . '-' . $id;
        } else {
          $cp['task'][$idPrec . '-' . $id]['duration']=$prec['delay'];
          if ($cp['task'][$id]) $cp['task'][$id]['duration'];
          $cp['task'][$idPrec . '-' . $id]['start']='E' . $id;
          if (!isset($cp['node']['E' . $id])) $cp['node']['E' . $id]=$arrayNode;
          if (!in_array($idPrec . '-' . $id, $cp['node']['E' . $id]['after'])) $cp['node']['E' . $id]['after'][]=$idPrec . '-' . $id;
          $cp['task'][$idPrec . '-' . $id]['end']='E' . $idPrec;
          if (!isset($cp['node']['E' . $idPrec])) $cp['node']['E' . $idPrec]=$arrayNode;
          if (!in_array($idPrec . '-' . $id, $cp['node']['E' . $idPrec]['before'])) $cp['node']['E' . $idPrec]['before'][]=$idPrec . '-' . $id;
          if (!isset($cp['task'][$id])) $cp['task'][$id]=$arrayTask;
          $cp['task'][$id]['mode']='reverse';
        }
      }
    }
    foreach ($cp['node'] as $id=>$node) { // Attach loose nodes to S or E
      if ($id=='S' or $id=='E') continue;
      if (count($node['before'])==0) { // No predecessor
        $cp['task']['S-' . $id]=$arrayTask;
        $cp['task']['S-' . $id]['type']='fake';
        $cp['task']['S-' . $id]['duration']=0;
        $cp['task']['S-' . $id]['start']='S';
        $cp['task']['S-' . $id]['end']=$id;
        if (!in_array('S-' . $id, $cp['node']['S']['after'])) $cp['node']['S']['after'][]='S-' . $id;
      }
      if (count($node['after'])==0) { // No successor
        $cp['task'][$id . '-E']=$arrayTask;
        $cp['task'][$id . '-E']['type']='fake';
        $cp['task'][$id . '-E']['duration']=0;
        $cp['task'][$id . '-E']['start']=$id;
        $cp['task'][$id . '-E']['end']='E';
        if (!in_array($id . '-E', $cp['node']['E']['before'])) $cp['node']['E']['before'][]=$id . '-E';
      }
    }
    self::reverse('E', $cp, $idProject);
    foreach ($cp['task'] as $idP=>$plan) {
      if ($plan['type']!='task') continue;
      $pe=$fullListPlan[$idP];
      $pe->latestStartDate=$cp['node'][$plan['start']]['late'];
      $pe->latestEndDate=$cp['node'][$plan['end']]['late'];
      $profile=(isset($pe->_profile))?$pe->_profile:'ASAP';
      if ($profile=='RECW' or $profile=='REGUL' or $profile=='FULL' or $profile=='HALF' or $profile=='QUART' or !property_exists($pe, '_directPredecessorList') or (count($pe->_directPredecessorList)==0 and $pe->latestStartDate>$start) or !$pe->elementary) {
        $pe->isOnCriticalPath=0;
      } else if (($pe->latestStartDate<=$pe->plannedStartDate and $pe->latestEndDate<=$pe->plannedEndDate and $plan['mode']!='reverse') or ($plan['mode']=='reverse' and $pe->latestStartDate<$pe->plannedStartDate)) {
        $pe->isOnCriticalPath=1;
      } else {
        $pe->isOnCriticalPath=0;
      }
      $fullListPlan[$idP]=$pe;
    }
    return $fullListPlan;
  }
  
  // Calculate reverse planning for a task : from end, subtract duration du get "latest start date"
  private static function reverse($nodeId, &$cp, $idProject) {
    $node=$cp['node'][$nodeId];
    $cp['TEST']='OK';
    foreach ($cp['node'][$nodeId]['before'] as $taskId) {
      $task=$cp['task'][$taskId];
      $diff=($task['duration'])?($task['duration'])*(-1):0;
      if ($nodeId=='E' or $nodeId=='S') {
        $diff==0;
      } else if ($task['type']=='task' and $diff!=0) {
        $diff+=1;
      } else if ($diff>0) {
        $diff+=1;
      }
      $start=addWorkDaysToDate($node['late'], $diff, $idProject);
      if (!$cp['node'][$task['start']]['late'] or $start<$cp['node'][$task['start']]['late']) $cp['node'][$task['start']]['late']=$start;
      self::reverse($task['start'], $cp, $idProject);
    }
  }
  
  // Store a plan item (planningelement) into storeListPlan table)
  private static function storeListPlan($listPlan, $plan) {
    scriptLog("storeListPlan(listPlan,$plan->id)");
    $listPlan['#' . $plan->id]=$plan;
    // Update planned dates of parents
    if (($plan->plannedStartDate or $plan->realStartDate) and ($plan->plannedEndDate or $plan->realEndDate)) {
      foreach ($plan->_parentList as $topId=>$topVal) {
        $top=$listPlan[$topId];
        $startDate=($plan->realStartDate)?$plan->realStartDate:$plan->plannedStartDate;
        if (!$top->plannedStartDate or $top->plannedStartDate>$startDate) {
          $top->plannedStartDate=$startDate;
        }
        $endDate=($plan->realEndDate)?$plan->realEndDate:$plan->plannedEndDate;
        if (!$top->plannedEndDate or $top->plannedEndDate<$endDate) {
          $top->plannedEndDate=$endDate;
        }
        $listPlan[$topId]=$top;
      }
    }
    return $listPlan;
  }
  
  private static function sortPlanningElements($list, $listProjectsPriority, $listProjectsType, $listProjectsDelay, $listProjectsOrder) {
    // first sort on simple criterias
    $forceProjectPriority=Parameter::getGlobalParameter('forceProjectPriority'); // Will enforce Project Priority compared to Planning Mode and keep consistency for project
    if (!$forceProjectPriority or $forceProjectPriority=='') $forceProjectPriority='YES'; // On V12.0 - New mode becomes default behavior
    $mainPriority=(Parameter::getGlobalParameter('planningPriorityByEndDate')=='NO')?"priority":"endDate"; // May be set to "endDate" or "priority"
    $str01='00000000';
    $str99='99999999';
    $pmList=SqlList::getList('PlanningMode', 'code', null, true);
    $pmList['']='';
    foreach ($list as $id=>$elt) {
      $expectedEndDate='9999-99-99';
      $expectedStartDate=$elt->validatedStartDate;
      $expectedEndDateTmp=$elt->getExpectedEndDate($list, $listProjectsDelay[$elt->idProject]??null); // PBER
      if ($expectedEndDateTmp=='N/A') $expectedEndDateTmp=null;
      if ($mainPriority=="endDate") $expectedEndDate=$expectedEndDateTmp;
      if ($elt->idPlanningMode and !isset($pmList[$elt->idPlanningMode])) {
        traceLog("Error for planning mode '$elt->idPlanningMode' not found in Planning Mode table");
        $pmList[$elt->idPlanningMode]='ASAP';
      }
      $refPrio='1';
      if (isset($listProjectsType[$elt->idProject])) {
        $typeProject=$listProjectsType[$elt->idProject];
        if ($typeProject=='TMP') $refPrio='6';
        else if ($typeProject=='PRP') $refPrio='5';
      }
      $pm=($elt->idPlanningMode)?$pmList[$elt->idPlanningMode]:'';
      
      if ($elt->elementary==0) {
        $critMode='5.' . $str99;
      } else if ($pm=='FIXED' or $pm=='FLOAT') { // FIXED or FLOAT => Milestones - FLOAT Will be moved depending on predecessors
        $critMode='1.' . $str01;
      } else if ($pm=='REGUL' or $pm=='FULL' or $pm=='HALF' or $pm=='QUART') { // REGUL or FULL or HALF or QUART)
        $critMode='2.' . $str01;
      } else if ($elt->indivisibility==1 and $elt->realWork>0) { // Increase priority for started tasks that should not be split
        $critMode='3.' . $str01;
        // } else if ($pm=='STARR') { // PBER #10262 - not a specific use case any more
        // $critMode='3.'.pq_str_replace('-','',(($elt->validatedStartDate)?$elt->validatedStartDate:'9999-99-99'));
        // } else if ( ($pm=='FDUR' or $pm=='DDUR' or $pm=='CDUR') and $forceProjectPriority=='NO') { // FDUR // PBER #10262 - not a specific use case any more
        // $critMode='4.'.$str01;
      } else if ($pm=='RECW') { // RECW
        $critMode='6.' . $str01; // Lower priority (availability will be reserved)
        // } else if ($pm=='ALAP' and $expectedEndDate and $mainPriority=='endDate' and $forceProjectPriority=='NO') { // PBER #10262 - not a specific use case any more
        // $critMode='5.'.pq_str_replace('-','',(($expectedEndDate)?$expectedEndDate:'9999-99-99'));
      } else { // Others (includes GROUP, wich is not a priority but a constraint)
        $critMode='5.' . $str99;
      }
      $prio=($elt->refType=='Project')?'99999':$elt->priority;
      if (!pq_trim($prio)) $prio=500;
      if (isset($listProjectsPriority[$elt->idProject])) {
        $projPrio=$listProjectsPriority[$elt->idProject];
      } else {
        $projPE=SqlElement::getSingleSqlElementFromCriteria('ProjectPlanningElement', array(
            'refType'=>'Project',
            'refId'=>$elt->idProject), true);
        if ($projPE and $projPE->id and $projPE->priority) {
          $listProjectsPriority[$elt->idProject]=$projPE->priority;
          $projPrio=$projPE->priority;
        } else {
          $listProjectsPriority[$elt->idProject]=500;
          $projPrio=500;
        }
      }
      if (!pq_trim($projPrio)) $projPrio=500;
      if (! $elt->leftWork or $elt->leftWork==0) { // PBER 11631 - This lead to prioritize tasks with onyl material resources
        //$prio=0;
      }
      $critDate=$str99;
      if ($pm=='CDUR' and $expectedStartDate) {
        $critDate=pq_str_replace('-', '', $expectedStartDate);
        // } else if ($pm=='STARR' and $expectedStartDate and $forceProjectPriority!='NO') { // PBER #10262
      } else if ($pm=='STARR' and $expectedStartDate) { // PBER #10262
        $critDate=pq_str_replace('-', '', $expectedStartDate);
      } else if ($mainPriority=='endDate' and $expectedEndDate) {
        $critDate=pq_str_replace('-', '', $expectedEndDate);
      } else if ($mainPriority=='priority' and $pm=='ALAP') {
        $critDate=pq_str_replace('-', '', $expectedEndDate);
      }
      if ($forceProjectPriority=='NO') {
        $crit=$refPrio;
        $crit.='.' . $critMode;
        $crit.='.' . str_pad($projPrio, 5, '0', STR_PAD_LEFT);
        $crit.='.' . str_pad($prio, 5, '0', STR_PAD_LEFT);
        $crit.='.' . $critDate;
        $crit.='.' . $elt->wbsSortable;
      } else {
        $crit=$refPrio;
        $crit.='.' . $critMode;
        $crit.='.' . str_pad($projPrio, 5, '0', STR_PAD_LEFT);
        $crit.='.' . str_pad(($listProjectsOrder[$elt->idProject]??'9999999999'), 10, '0', STR_PAD_LEFT);
        $crit.='.' . (($elt->elementary==0)?'9':'1');
        $crit.='.' . str_pad($prio, 5, '0', STR_PAD_LEFT);
        $crit.='.' . $critDate;
        if (property_exists($elt, '_wbsOrder')) $crit.='.' . str_pad($elt->_wbsOrder, 10, '0', STR_PAD_LEFT); // $crit.='.'.$elt->wbsSortable;
        else $crit.='9999999999';
      }
      $elt->_sortCriteria=$crit;
      $list[$id]=$elt;
    }
    $bool=uasort($list, array(new PlanningElement(), "comparePlanningElementSimple"));
    // self::traceArray($list);
    // then sort on predecessors
    $result=self::specificSort($list);
    // self::traceArray($result);
    return $result;
  }
  
  private static function specificSort($list) {
    // Sort to take dependencies into account
    $waiting=array();
    $result=array(); // target array for sorted elements
    foreach ($list as $id=>$pe) { // Parent wait for Sons
      if (property_exists($pe, '_parentList') and isset($pe->_parentList) and is_array($pe->_parentList)) {
        foreach ($pe->_parentList as $parentId=>$parentPe) {
          if (!isset($list[$parentId])) continue;
          if (!isset($waiting[$id])) $waiting[$id]=array();
          $waiting[$id][$parentId]=$list[$parentId];
        }
      }
    }
    foreach ($list as $id=>$pe) {
      $canInsert=false;
      if (property_exists($pe, '_predecessorListWithParent') and isset($pe->_predecessorListWithParent)) {
        $pe->_tmpPrec=array();
        // retrieve predecessors not sorted yet
        $canInsert=true;
        foreach ($pe->_predecessorListWithParent as $precId=>$precPe) {
          // if ($pe->indivisibility==1 and $pe->realWork>0 and $list[$precId]->indivisibility==0 and $list[$precId]->realWork==0 ) continue; // If current not splitable with already real work but predecessor is not, do not take predecessor into account
          if ($pe->indivisibility==1 and $pe->realWork>0) break; // If current not splitable with already real work but predecessor is not, do not take predecessor into account
          if (!pq_array_key_exists($precId, $result) and pq_array_key_exists($precId, $list)) {
            $canInsert=false;
            if (!isset($waiting[$precId])) $waiting[$precId]=array();
            $waiting[$precId][$id]=$pe;
          }
        }
      } else if (property_exists($pe, 'elementary') and $pe->elementary==0) {
        $canInsert=false;
      } else {
        // no predecessor, so can insert
        $canInsert=true;
      }
      foreach ($waiting as $wId=>$wArr)
        if (isset($wArr[$id])) $canInsert=false;
        if ($pe->idPlanningMode==6) $canInsert=true; // Fixed milestone - do not wait for prédecessors
        if ($canInsert) {
          $result[$id]=$pe;
          // now, must check if can insert waiting ones
          self::insertWaiting($result, $waiting, $id);
        }
    }
    // Search for infinite loop
    foreach ($waiting as $wId=>$wPe) {
      foreach ($wPe as $xId=>$xPe) {
        if (isset($waiting[$xId][$wId])) {
          $pe1=$list[$wId];
          $pe2=$list[$xId];
          $msg=i18n('infiniteLoopError', array(i18n($pe1->refType), $pe1->refId, i18n($pe2->refType), $pe2->refId));
          traceLog($msg);
          self::storeTechnicalError($msg, $pe1->refType, $pe1->refId);
        }
      }
    }
    // in the end, empty wait stack
    foreach ($waiting as $wId=>$wPe) {
      foreach ($wPe as $id=>$pe) {
        $result[$id]=$pe;
      }
    }
    return $result;
  }
  
  private static function insertWaiting(&$result, &$waiting, $id) {
    if (!isset($waiting[$id])) return; // No item waiting for this one
    foreach ($waiting[$id] as $wId=>$wPe) {
      unset($waiting[$id][$wId]);
      $wIdNotWaitingAnymore=true;
      foreach ($waiting as $precId=>$waitingPe) {
        if ($precId==$id) continue;
        if (isset($waiting[$precId][$wId])) {
          $wIdNotWaitingAnymore=false;
          break;
        }
      }
      if ($wIdNotWaitingAnymore) {
        $result[$wId]=$wPe;
        self::insertWaiting($result, $waiting, $wId);
      }
    }
    unset($waiting[$id]); // Ok no more waiting for this one
  }
  
  public static $_surbookedWorkStored=array();
  
  private static function storePlannedWork($value, $planned, $plannedReserved, $withProjectRepartition, $currentDate, $week, $profile, $r, $capacity, $capacityNormal, $listTopProjects, &$surbooked, &$surbookedWork, &$ass, &$plan, &$arrayPlannedWork, &$changedAss, &$left, &$ress, $support=null, $infinitecapacity=false, $startPlan=null) {
    if (!$support) {
      if (!isset(self::$_surbookedWorkStored[$ass->idResource])) self::$_surbookedWorkStored[$ass->idResource]=self::getExistingSurbookedWork($ass->idResource);
      if (!isset(self::$_surbookedWorkStored[$ass->idResource][$currentDate])) {
        self::$_surbookedWorkStored[$ass->idResource][$currentDate]=0;
      }
      if ($capacityNormal!==null) { // For Pools
        if ($value+$planned>$capacityNormal) {
          $surbookedWork=$value+$planned-$capacityNormal-self::$_surbookedWorkStored[$ass->idResource][$currentDate];
        }
      } else if ($value+$planned>$r->getCapacityPeriod($currentDate)) {
        $surbookedWork=$value+$planned-self::$_surbookedWorkStored[$ass->idResource][$currentDate]-$r->getCapacityPeriod($currentDate);
      }
      if ($surbookedWork>$value) $surbookedWork=$value; // Be sure to never store surbookedWork > work
      if ($surbookedWork>0 and $plannedReserved>0 and $infinitecapacity and $profile!='DDUR' and $profile!='CDUR') {
        $surbookedWork-=$plannedReserved;
        if ($surbookedWork<0) $surbookedWork=0;
        $value-=$plannedReserved;
        if ($value<0) $value=0;
      }
      if ($surbookedWork>=0.01) {
        $surbooked=1;
        self::$_surbookedWorkStored[$ass->idResource][$currentDate]+=$surbookedWork;
      } else {
        $surbookedWork=0; // To be sure we won't store negative values
      }
    }
    if ($profile=='FIXED' and $currentDate==$plan->validatedStartDate) {
      $fractionStart=$plan->validatedStartFraction;
    } else {
      $fractionStart=($capacity!=0)?round($planned/$capacity, 2):'0';
    }
    $fraction=($capacity!=0)?round($value/$capacity, 2):'1';
    ;
    $plannedWork=new PlannedWork();
    $plannedWork->idResource=($support)?$support:$ass->idResource;
    $plannedWork->idProject=$ass->idProject;
    $plannedWork->refType=$ass->refType;
    $plannedWork->refId=$ass->refId;
    $plannedWork->idAssignment=$ass->id;
    $plannedWork->work=$value;
    $plannedWork->surbooked=$surbooked;
    $plannedWork->surbookedWork=$surbookedWork;
    $plannedWork->setDates($currentDate);
    $arrayPlannedWork[]=$plannedWork;
    if (!$ass->plannedStartDate or $ass->plannedStartDate>$currentDate) {
      if ($profile=='DDUR' and $startPlan) $ass->plannedStartDate=$startPlan;
      else $ass->plannedStartDate=$currentDate;
      $ass->plannedStartFraction=$fractionStart;
    }
    if (!$ass->plannedEndDate or $ass->plannedEndDate<$currentDate) {
      $ass->plannedEndDate=$currentDate;
      $ass->plannedEndFraction=min(($fractionStart+$fraction), 1);
    }
    if (!$plan->plannedStartDate or $plan->plannedStartDate>$currentDate) {
      if ($profile=='DDUR' and $startPlan) $plan->plannedStartDate=$startPlan;
      else $plan->plannedStartDate=$currentDate;
      $plan->plannedStartFraction=$fractionStart;
    } else if ($plan->plannedStartDate==$currentDate and $plan->plannedStartFraction<$fractionStart) {
      $plan->plannedStartFraction=$fractionStart;
    }
    if ($surbooked and $surbookedWork>=0.01 and !$support) {
      $plan->surbooked=1;
      $ass->surbooked=1;
      $changedAss=true;
    }
    if (!$plan->plannedEndDate or $plan->plannedEndDate<$currentDate) {
      if ($ass->realEndDate&&$ass->realEndDate>$currentDate) {
        $plan->plannedEndDate=$ass->realEndDate;
        $plan->plannedEndFraction=1;
      } else {
        $plan->plannedEndDate=$currentDate;
        $plan->plannedEndFraction=min(($fractionStart+$fraction), 1);
      }
    } else if ($plan->plannedEndDate==$currentDate and $plan->plannedEndFraction<$fraction) {
      $plan->plannedEndFraction=min(($fractionStart+$fraction), 1);
    }
    $changedAss=true;
    if (!$support) $left-=$value;
    $ress[$currentDate]=$value+$planned-$plannedReserved;
    // Set value on each project (from current to top)
    if ($withProjectRepartition and $value>=0.01) {
      foreach ($listTopProjects as $idProject) {
        $projectKey='Project#' . $idProject;
        $plannedProj=0;
        if (!isset($ress[$projectKey])) $ress[$projectKey]=array();
        if (isset($ress[$projectKey][$week])) {
          $plannedProj=$ress[$projectKey][$week];
        }
        $ress[$projectKey][$week]=$value+$plannedProj;
        $plannedProjDay=0;
        if (isset($ress[$projectKey][$currentDate])) {
          $plannedProjDay=$ress[$projectKey][$currentDate];
        }
        $ress[$projectKey][$currentDate]=$value+$plannedProjDay;
      }
    }
  }
  
  private static function getExistingSurbookedWork($idResource) {
    global $infinitecapacityStored, $inClauseStored;
    $res=array();
    if ($infinitecapacityStored) {
      $pws=new PlannedWork();
      $sum=$pws->sumSqlElementsFromCriteria('surbookedWork', null, "idResource=$idResource and not ($inClauseStored)", 'workDate');
      if ($sum) {
        foreach ($sum as $wk) {
          $res[$wk['workdate']]=$wk['sumsurbookedwork'];
        }
      }
    }
    return $res;
  }
  
  private static function storePlannedWorkLeveled($startPlanDate, $expectedStart, $expectedEnd, $capacity, &$ass, &$plan, &$arrayPlannedWork, &$changedAss, &$left, $delay) {
    if ($left==0) return;
    $minDuration=ceil($left);
    $prf=$plan->_profile;
    if ($prf=='FULL' or $prf=='HALF' or $prf=='QUART' or $prf=='REGUL' or $prf=='FIXED') {
      if ($plan->refType=='Milestone') {} else {
        $start=self::shiftValidatedDate($plan->validatedStartDate, $delay);
        $end=self::shiftValidatedDate($plan->validatedEndDate, $delay);
      }
    } else if ($prf=='FDUR' or $prf=='DDUR' or $prf=='CDUR') {
      $end=$expectedEnd;
      $start=addWorkDaysToDate($end, 1-$plan->validatedDuration, $plan->idProject);
    } else {
      $end=$expectedEnd;
      $start=addWorkDaysToDate($end, 1-$minDuration, $plan->idProject);
    }
    if ($start<$startPlanDate) $start=$startPlanDate;
    if ($end>$expectedEnd) $end=$expectedEnd;
    if ($end<$start) $end=$start;
    $duration=workDayDiffDates($start, $end, $plan->idProject);
    if (!$duration or $duration<=0) $duration=1;
    // $regul=ceil($left/$duration*100)/100; // Regular to plan, ceilled at 0.1
    $regul=round($left/$duration, 2);
    $regulLeft=$left;
    $regulDone=0;
    $target=0;
    for ($currentDate=$start; $currentDate<=$end; $currentDate=addDaysToDate($currentDate, 1)) {
      if (isOffDay($currentDate)) continue;
      if ($regulLeft<0.01) break;
      if (!isset(self::$_surbookedWorkStored[$ass->idResource])) self::$_surbookedWorkStored[$ass->idResource]=self::getExistingSurbookedWork($ass->idResource);
      if (!isset(self::$_surbookedWorkStored[$ass->idResource][$currentDate])) self::$_surbookedWorkStored[$ass->idResource][$currentDate]=0;
      // Get Planned Work already stored for that day / that resource / that assignment
      $idPW=null;
      foreach ($arrayPlannedWork as $id=>$plannedWork) {
        if ($plannedWork->idResource==$ass->idResource and $plannedWork->idAssignment==$ass->id and $plannedWork->workDate==$currentDate) {
          $idPW=$id;
          break;
        }
      }
      if (!$idPW) {
        $plannedWork=new PlannedWork();
        $plannedWork->idResource=$ass->idResource;
        $plannedWork->idProject=$ass->idProject;
        $plannedWork->refType=$ass->refType;
        $plannedWork->refId=$ass->refId;
        $plannedWork->idAssignment=$ass->id;
        $plannedWork->work=0;
        $plannedWork->surbooked=0;
        $plannedWork->surbookedWork=0;
        $plannedWork->setDates($currentDate);
      }
      $target+=$regul;
      $toPlan=round($target-$regulDone, 1);
      if ($currentDate==$end) $toPlan=round($regulLeft, 2);
      $regulDone+=$toPlan;
      $plannedWork->work+=$toPlan;
      $plannedWork->surbooked=1;
      $plannedWork->surbookedWork+=$toPlan;
      self::$_surbookedWorkStored[$ass->idResource][$currentDate]+=$toPlan;
      $regulLeft=round($regulLeft-$toPlan, 2);
      if ($idPW) $arrayPlannedWork[$idPW]=$plannedWork;
      else array_push($arrayPlannedWork, $plannedWork);
    }
    if (!$ass->plannedStartDate) {
      $ass->plannedStartDate=$start;
      $ass->plannedStartFraction=null;
    }
    if (!$ass->plannedEndDate) {
      $ass->plannedEndDate=$end;
      $ass->plannedEndFraction=1;
    }
    if (!$plan->plannedStartDate) {
      $plan->plannedStartDate=$start;
      $plan->plannedStartFraction=null;
    }
    if (!$plan->plannedEndDate) {
      $plan->plannedEndDate=$end;
      $plan->plannedEndFraction=1;
    }
    $plan->surbooked=1;
    $ass->surbooked=1;
    $changedAss=true;
    $left=0;
  }
  
  private static function traceArray($list) {
    debugTraceLog('*****traceArray()*****');
    foreach ($list as $id=>$pe) {
      debugTraceLog('|' . $id . '|' . $pe->wbs . '|' . $pe->refType . '#' . $pe->refId . '|' . $pe->refName . '|Prio=' . $pe->priority . '|Left=' . $pe->leftWork . '|' . $pe->_sortCriteria);
      if (property_exists($pe, '_predecessorListWithParent') and count($pe->_predecessorListWithParent)>0) {
        foreach ($pe->_predecessorListWithParent as $idPrec=>$prec) {
          debugTraceLog("||id=$idPrec|delay=" . $prec['delay'] . "|type=" . $prec['type']);
        }
      }
    }
  }
  
  // ================================================================================================================================
  public static function planSaveDates($projectId, $initial, $validated) {
    $user=new User(getCurrentUserId());
    if ($initial=='NEVER' and $validated=='NEVER') {
      $result=i18n('planDatesNotSaved');
      $result.='<input type="hidden" id="lastPlanStatus" value="WARNING" />';
      return $result;
    }
    $cpt=0;
    $proj=new Project($projectId, true);
    $scope='changeValidatedData';
    $listSubproj=$proj->getRecursiveSubProjectsFlatList(true, true);
    $listValidProj=getSessionUser()->getListOfPlannableProjects($scope);
    $validSubProj=array();
    foreach ($listValidProj as $id=>$value) {
      $priority=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array(
          'idProfile'=>$user->getProfile($id),
          'scope'=>'validatePlanning')); // florent
      if (isset($listSubproj[$id]) and $priority->rightAccess==1) {
        $validSubProj[$id]=$listSubproj[$id];
      }
    }
    $inClause="idProject in " . transformListIntoInClause($validSubProj);
    $obj=new PlanningElement();
    $tablePE=$obj->getDatabaseTableName();
    $inClause.=" and " . getAccesRestrictionClause('Activity', $tablePE);
    // Remove administrative projects :
    $inClause.=" and idProject not in " . Project::getAdminitrativeProjectList();
    // Remove Projects with Fixed Planning flag
    $inClause.=" and idProject not in " . Project::getFixedProjectList();
    // Get the list of all PlanningElements to plan (includes Activity and/or Projects)
    $pe=new PlanningElement();
    $order="wbsSortable asc";
    $list=$pe->getSqlElementsFromCriteria(null, false, $inClause, $order, true);
    foreach ($list as $pe) {
      // initial
      if (($initial=='ALWAYS' or ($initial=='IFEMPTY' and !$pe->initialStartDate and !$pe->initialEndDate)) and pq_trim($pe->plannedStartDate) and pq_trim($pe->plannedEndDate)) {
        $pe->initialStartDate=$pe->plannedStartDate;
        $pe->initialEndDate=$pe->plannedEndDate;
        $cpt++;
      }
      // validated
      if (($validated=='ALWAYS' or ($validated=='IFEMPTY' and !$pe->validatedStartDate and !$pe->validatedEndDate)) and pq_trim($pe->plannedStartDate) and pq_trim($pe->plannedEndDate)) {
        $pe->validatedStartDate=$pe->plannedStartDate;
        $pe->validatedEndDate=$pe->plannedEndDate;
        $cpt++;
      }
      $pe->simpleSave();
    }
    if ($cpt>0) {
      $result=i18n('planDatesSaved');
      $result.='<input type="hidden" id="lastPlanStatus" value="OK" />';
    } else {
      $result=i18n('planDatesNotSaved');
      $result.='<input type="hidden" id="lastPlanStatus" value="WARNING" />';
    }
    return $result;
  }
  
  private static function getPlannedWorkForResource($idRes, $startDate) {
    global $resources, $withProjectRepartition;
    if (!isset($resources[$idRes])) {
      $r=new Resource($idRes, true);
      $ress=$r->getWork($startDate, $withProjectRepartition);
      $resources[$idRes]=$ress;
    } else {
      $ress=$resources[$idRes];
    }
    $sum=0;
    foreach ($ress as $dt=>$val) {
      if (pq_strlen($dt)==10 and pq_substr($dt, 4, 1)=='-' and pq_substr($dt, 7, 1)=='-') {
        $sum+=$val;
      }
    }
    return $sum;
  }
  
  private static function getLeftWorkForResource($idRes, $startDate) {
    global $resources, $withProjectRepartition;
    if (!isset($resources[$idRes])) {
      $r=new Resource($idRes, true);
      $ress=$r->getWork($startDate, $withProjectRepartition);
      $resources[$idRes]=$ress;
    } else {
      $ress=$resources[$idRes];
    }
    if (isset($ress['leftWork'])) {
      return $ress['leftWork'];
    }
    $ass=new Assignment();
    $sum=$ass->sumSqlElementsFromCriteria('leftWork', array('idResource'=>$idRes));
    $resources[$idRes]['leftWork']=$sum;
    return $sum;
  }
  
  public static function shiftValidatedDate($date, $delay) {
    if ($delay) {
      $delayedDate=addMonthsToDate($date, $delay);
      if (!isOpenDay($delayedDate)) {
        while (!isOpenDay($delayedDate)) {
          $delayedDate=addDaysToDate($delayedDate, 1);
        }
      }
      return $delayedDate;
    } else {
      return $date;
    }
  }
  
  public static function storeTechnicalError($msg, $refType, $refId) {
    if (self::$_technicalErrors==null) self::$_technicalErrors=array();
    self::$_technicalErrors[]=array('msg'=>$msg, 'refType'=>$refType, 'refId'=>$refId);
  }
  
}
?>