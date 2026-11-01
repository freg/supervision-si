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

/* ============================================================================
 * Menu defines list of items to present to users.
 */ 
require_once('_securityCheck.php');
class Module extends SqlElement {

  // extends SqlElement, so has $id
  public $id;    // redefine $id to specify its visible place 
  public $name;
  public $idModule;
  public $sortOrder=0;
  public $active;
  public $parentActive;
  public $notActiveAlone;
  public $idle;
  
  public $_isNameTranslatable = true;
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }

  
   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }
    
  public function save() {
    $old=$this->getOld();
    $result=parent::save();
    $moduleMenu=new ModuleMenu();
    $moduleMenuList=$moduleMenu->getSqlElementsFromCriteria(array('idModule'=>$this->id));
    foreach ($moduleMenuList as $moduleMenu) {
      $moduleMenu->active=$this->active;
      $moduleMenu->save();
    }
    $moduleReport=new ModuleReport();
    $moduleReportList=$moduleReport->getSqlElementsFromCriteria(array('idModule'=>$this->id));
    foreach ($moduleReportList as $moduleReport) {
      $moduleReport->active=$this->active;
      $moduleReport->save();
    }
    // MTY - LEAVE SYSTEM
    if ($this->id==12 and $old->active!=$this->active) { // HR Module
      include_once '../tool/projeqtor-hr.php';
      $result=initPurgeLeaveSystemElements(($this->active)?'YES':'NO');
      $status = getLastOperationStatus($result);
      if ($status=="OK") {
        unsetSessionValue("visibleProjectsList");
      } elseif ($status=="NO_CHANGE") {
        $status="OK";
      }
      traceLog("Change LeaveSystemActiv to ".(($this->active)?'YES':'NO').' :'.$status);
      if ($status!='OK') traceLog($result); 
    }
    
    if ($this->id==20 and $this->active and !$old->active) {
      $projectList = getVisibleProjectsList(true);
      $projectList = pq_str_replace('(', '', $projectList);
      $projectList = pq_str_replace(')', '', $projectList);
      $projectList = pq_explode(',', $projectList);
      foreach ($projectList as $id=>$idProj){
        if(!$idProj)continue;
        $proj = new Project($idProj);
        $proj->ProjectPlanningElement->updateCA();
      }
    }
    
    if($this->id==37){
      $idle = ($this->active)?0:1;
      $status = new Status();
      $statusList = $status->getSqlElementsFromCriteria(array('forAgileScrum'=>'1'));
      foreach ($statusList as $st){
        $st->idle = $idle;
        $st->save();
      }
    }
      // MTY - LEAVE SYSTEM
    unsetSessionValue('menuInactiveList',true);
    unsetSessionValue('reportInactiveList',true);
    unsetSessionValue('moduleList',true);
    return $result;
  }
  public static function isMenuActive($menu) {
    if (! sessionValueExists('menuInactiveList',true)) {
      self::initializeMenuInactiveList();
    }
    $list=getSessionValue('menuInactiveList',null,true);
    if (isset($list[$menu])) return false;
    else return true;
  }
  public static function isModuleActive($module) {
    if (! sessionValueExists('moduleList',true)) {
      self::initializeModuleList();
    }
    $list=getSessionValue('moduleList',null,true);
    if (isset($list[$module]) and $list[$module]==1) return true;
    else return false;
  }
  public static function moduleExists($module) {
    if (! sessionValueExists('moduleList',true)) {
      self::initializeModuleList();
    }
    $list=getSessionValue('moduleList',null,true);
    if (isset($list[$module])) return true;
    else return false;
  }
  public static function resetMenuInactiveList() {
    unsetSessionValue('menuInactiveList');
    self::initializeMenuInactiveList();
  }
  private static function initializeMenuInactiveList() {
    $moduleMenu=new ModuleMenu();
    $list=$moduleMenu->countGroupedSqlElementsFromCriteria(null, array('idMenu','active'),'1=1');
    $arrayCpt=array();
    foreach ($list as $key=>$cpt) {
      $split=pq_explode('|',$key);
      $menu=SqlList::getNameFromId('Menu', $split[0],false);
      $active=$split[1];
      if (!isset($arrayCpt[$menu])) $arrayCpt[$menu]=array('0'=>0,'1'=>0);
      $arrayCpt[$menu][$active]=$cpt;
    }
   
    $result=array();
    foreach($arrayCpt as $menu=>$tab) {
      if ($tab['1']>0) {
        // At least one active
      } else {
        $result[$menu]=$menu;
      }
    }
    setSessionValue('menuInactiveList', $result,true);
  }
  
  public static function isReportActive($report) {
    if (! sessionValueExists('reportInactiveList',true)) {
      self::initializeReportInactiveList();
    }
    $list=getSessionValue('reportInactiveList',null,true);
    if (isset($list[$report])) return false;
    else return true;
  }
  private static function initializeReportInactiveList() {
    $moduleReport=new ModuleReport();
    $list=$moduleReport->countGroupedSqlElementsFromCriteria(null, array('idReport','active'),'1=1');
    $arrayCpt=array();
    foreach ($list as $key=>$cpt) {
      $split=pq_explode('|',$key);
      $report=SqlList::getNameFromId('Report', $split[0],false);
      $active=$split[1];
      if (!isset($arrayCpt[$report])) $arrayCpt[$report]=array('0'=>0,'1'=>0);
      $arrayCpt[$report][$active]=$cpt;
    }
    $result=array();
    foreach($arrayCpt as $report=>$tab) {
      if ($tab['1']>0) {
        // At least one active
      } else {
        $result[$report]=$report;
      }
    }
    setSessionValue('reportInactiveList', $result,true);
  }
  
  private static function initializeModuleList() {
    $result=array();
    $module=new Module();
    $list=$module->getSqlElementsFromCriteria(null,null,"1=1");
    foreach ($list as $module) {
      $result[$module->name]=$module->active;
    }
    setSessionValue('moduleList', $result,true);
  }
  
  public static function applyModuleRestrictionsOnParametersList(&$list) {
    if (! Module::isModuleActive('moduleConfiguration')) {
      self::unsetTab($list, 'tabConfiguration');
    }
    if (! Module::isModuleActive('moduleFinancial')) {
      self::unsetTab($list, 'tabFinancial');
    }
    if (! Module::isModuleActive('moduleExpenses')) {
      self::unsetSection($list, 'sectionFinancialProvider');
      self::unsetSection($list, 'sectionFinancialAutomation');
    }  
    if (! Module::isModuleActive('moduleIncomes')) {
      self::unsetSection($list, 'sectionFinancialClient');
    }
    if (! Module::isModuleActive('moduleAbsence')) {
      self::unsetSection($list, 'sectionLeaves');
    }
    if (! Module::isModuleActive('moduleNotification')) {
      unset($list['cronCheckNotifications']);
    }
     //if (! Module::isModuleActive('moduleOrganization')) {
       //self::unsetSection($list, 'sectionOrganization');
     //}
    if (! Module::isModuleActive('moduleGestionCA')) {
      self::unsetSection($list, 'sectionFinancialWorkUnit');
    }
  }
  public static function unsetTab(&$list, $tab) {
    $tabFound=false;
    foreach ($list as $key=>$val) {
      if ($key==$tab) {
        $tabFound=true; // Start
      } else if ($val=='tab') {
        $tabFound=false; // Stop
      }
      if ($tabFound) unset($list[$key]);
    }
  }
  public static function unsetSection(&$list, $tab) {
    $tabFound=false;
    foreach ($list as $key=>$val) {
      if ($key==$tab) {
        $tabFound=true; // Start
      } else if ($val=='tab' or $val=='section' or $val=='newColumn' or $val=='newColumnFull') {
        $tabFound=false; // Stop
      }
      if ($tabFound) unset($list[$key]);
    }
  }
  
  public static function getListOfFieldsToHide($class) {
    $list=array();
    if (! Module::isModuleActive('moduleConfiguration')) {
      $tstFld=array( '_sec_productComponent', 'idProduct', 'idComponent', 'idProductVersion','idOriginalProductVersion','idTargetProductVersion', 
                     'idComponentVersion', 'idOriginalComponentVersion', 'idTargetComponentVersion',
                      '_sec_ProductprojectProducts','_ProductProject','_sec_VersionprojectVersions','_VersionProject'
      );
      foreach ($tstFld as $fld) {
        if (property_exists($class,$fld)) {
          $list[$fld]=$fld;
        }
      }
    }
    if ($class=="Delivery" and ! Module::isModuleActive('modulePlanning')) {
      $list['_sec_Link_Activity']='_sec_Link_Activity' ;
      $list['_Link_Activity']='_Link_Activity';
    }
    if (isSimpleUi()) {
      $list['Origin']='Origin';
      $list['idOrganization']='idOrganization';
      $list['idCategory']='idCategory';
      $list['idClient']='idClient';
      $list['externalReference']='externalReference';
      $list['idCatalogUO']='idCatalogUO';
      $list['idCalendarDefinition']='idCalendarDefinition';
      $list['projectCode']='projectCode';
      $list['contractCode']='contractCode';
      $list['clientCode']='clientCode';
      $list['idSponsor']='idSponsor';
      $list['idContact']='idContact';
      $list['initialStartDate']='initialStartDate';
      $list['initialEndDate']='initialEndDate';
      $list['initialDuration']='initialDuration';
      $list['validatedCost']='validatedCost';
      $list['expenseValidatedAmount']='expenseValidatedAmount';
      $list['totalValidatedCost']='totalValidatedCost';
      $list['assignedCost']='assignedCost';
      $list['expenseAssignedAmount']='expenseAssignedAmount';
      $list['totalAssignedCost']='totalAssignedCost';
      $list['realCost']='realCost';
      $list['expenseRealAmount']='expenseRealAmount';
      $list['totalRealCost']='totalRealCost';
      $list['leftCost']='leftCost';
      $list['expenseLeftAmount']='expenseLeftAmount';
      $list['totalLeftCost']='totalLeftCost';
      $list['reserveAmount']='reserveAmount';
      $list['plannedCost']='plannedCost';
      $list['expensePlannedAmount']='expensePlannedAmount';
      $list['totalPlannedCost']='totalPlannedCost';
      $list['expectedProgress']='expectedProgress';
      //$list['wbs']='wbs';
      $list['marginCost']='marginCost';
      $list['marginCostPct']='marginCostPct';
      $list['_separator_sectionRevenue_marginTop']='_separator_sectionRevenue_marginTop';
      $list['revenue']='revenue';
      $list['commandSum']='commandSum';
      $list['billSum']='billSum';
      $list['idRevenueMode']='idRevenueMode';
      $list['_sec_Proposal']='_sec_Proposal';
      $list['strength']='strength';
      $list['weakness']='weakness';
      $list['opportunity']='opportunity';
      $list['threats']='threats';
      $list['strategicValue']='strategicValue';
      $list['benefitValue']='benefitValue';
      $list['fixPlanning']='fixPlanning';
      $list['paused']='paused';
      $list['fixPerimeter']='fixPerimeter';
      $list['allowReduction']='allowReduction';
      $list['isUnderConstruction']='isUnderConstruction';
      $list['excludeFromGlobalPlanning']='excludeFromGlobalPlanning';
      $list['commandOnValidWork']='commandOnValidWork';
      $list['handled']='handled';
      $list['handledDate']='handledDate';
      $list['done']='done';
      $list['doneDate']='doneDate';
      $list['_sec_Synchronisation']='_sec_Synchronisation';
      $list['_sec_LocalCurrency']='_sec_LocalCurrency';
      $list['_sec_Abacus']='_sec_Abacus';
      $list['_sec_ProductprojectProducts']='_sec_ProductprojectProducts';
      $list['_sec_VersionprojectVersions']='_sec_VersionprojectVersions';
      $list['idMilestone']='idMilestone';
      $list['unitToDeliver']='unitToDeliver';
      $list['unitToRealise']='unitToRealise';
      $list['unitRealised']='unitRealised';
      $list['unitLeft']='unitLeft';
      $list['unitProgress']='unitProgress';
      $list['idProgressMode']='idProgressMode';
      $list['unitWeight']='unitWeight';
      $list['idWeightMode']='idWeightMode';
      $list['_label_weight']='_label_weight';
      $list['minimumThreshold']='minimumThreshold';
      $list['indivisibility']='indivisibility';
      $list['isPlanningActivity']='isPlanningActivity';
      $list['_spe_idWorkUnits']='_spe_idWorkUnits';
      $list['idProduct']='idProduct';
      $list['idComponent']='idComponent';
      $list['idProductVersion']='idProductVersion';
      $list['idTargetProductVersion']='idTargetProductVersion';
      $list['idTargetComponentVersion']='idTargetComponentVersion';
      $list['_sec_productComponent']='_sec_productComponent';
      $list['_sec_vote']='_sec_vote';
      $list['_sec_ActivitySkill']='_sec_ActivitySkill';
      $list['_sec_ProjectDailyHours']='_sec_ProjectDailyHours';
      $list['']='';
      
    }
    return $list;
  }
}
?>