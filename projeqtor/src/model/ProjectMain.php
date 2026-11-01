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

/** ============================================================================
 * Project is the main object of the project managmement.
 * Almost all other objects are linked to a given project.
 */ 
require_once('_securityCheck.php');

class ProjectMain extends SqlElement {

  public $_sec_Description;
  public $id;
  public $_spe_rf; 
  public $name;
  public $tags;
  public $idProject;
  public $idProjectType;
  public $idOrganization;
  public $idCategory;
  public $organizationInherited;
  public $organizationElementary;
  public $codeType;
  public $idClient;
  public $idContact;
  public $idCatalogUO;
  public $idCalendarDefinition;
  public $projectCode;
  public $contractCode;
  public $clientCode;
  public $idSponsor;
  public $idResource;
  public $idUser;
  public $creationDate;
  public $lastUpdateDateTime;
  public $color;
  public $longitude;
  public $latitude;
  public $description;
  public $objectives;
  public $_sec_Progress;
  public $ProjectPlanningElement; // is an object
  public $_sec_Affectations;
  public $_spe_affectations;
  public $_sec_Proposal;
  public $strength;
  public $weakness;
  public $opportunity;
  public $threats;
  public $_sec_treatment;
  public $idStatus;
  public $strategicValue;
  public $benefitValue;
  public $idRiskLevel;
  public $idHealth;
  public $idQuality;
  public $idTrend;
  public $idOverallProgress;
  public $fixPlanning;
  public $_lib_helpFixPlanning;
  public $paused;
  public $_lib_helpPaused;
  public $fixPerimeter;
  public $_lib_helpFixPerimeter;
  public $allowReduction;
  public $_lib_helpAllowReduction;
  public $isUnderConstruction;
  public $_lib_helpUnderConstruction;
  public $excludeFromGlobalPlanning;
  public $_lib_helpExcludeFromGlobalPlanning;
  public $commandOnValidWork;
  public $_lib_helpCommandOnValidWork;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $_sec_Synchronisation;
  public $_spe_isSynchronised;
  public $_sec_ProjectDailyHours;
  public $_tab_2_2=array('start', 'end', 'morning', 'afternoon');
  public $startAM;
  public $endAM;
  public $startPM;
  public $endPM;
  public $_sec_LocalCurrency;
  public $_tab_3_1_1= array('','','', 'localCurrency');
  public $localCurrency;
  public $_label_localCurrencyPosition;
  public $localCurrencyPosition;
  public $_tab_2_2_1=array('localToGlobal', 'globalToLocal', 'conversionRate', '');
  public $localToGlobalConversion;
  public $globalToLocalConversion;
  public $localToGlobalDisplay;
  public $globalToLocalDisplay;
  public $inheritedCurrency;
  public $_sec_Abacus;
  public $idPhasing;
  public $_spe_abacus;
  public $_sec_RaciMatrix;
  public $idRaciModel;
  public $_spe_raciMatrix;
  public $_raciMatrix_colSpan="2";
  public $_sec_ProductprojectProducts;
  public $_ProductProject=array();
  public $_sec_VersionprojectVersions;
  public $_VersionProject=array();
  public $_sec_Subprojects;
  public $_spe_subprojects;
  public $_sec_restrictTypes;
  public $_spe_restrictTypes;
  public $_sec_restrictLists;
  public $_spe_restrictLists;
  public $_sec_predecessor;
  public $_Dependency_Predecessor=array();
  public $_sec_successor;
  public $_Dependency_Successor=array();
  public $sortOrder;
  public $isLeaveMngProject=0;//Indicate that if it's the project dedicated to store the leave as work
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;
  
  private static $_administrativeProjectList=null;
  public static $_deleteProjectInProgress=false;
  private static $_copyProjectId=null;
  private static $_currencyPerProject=null;
  private static $_currencyPositionPerProject=null;
  private static $_localToGlobalRatePerProject=null;
  private static $_globalToLocalRatePerProject=null;
  private static $_cacheColor=array();
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="wbsSortable" from="ProjectPlanningElement" formatter="sortableFormatter" width="10%" >${wbs}</th>
    <th field="name" width="30%" >${projectName}</th>
    <th field="nameProjectType" width="15%" >${type}</th>
    <th field="color" width="5%" formatter="colorFormatter">${color}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>
    <th field="progress" from="ProjectPlanningElement" width="10%" formatter="percentFormatter">${progress}</th>
    <th field="plannedEndDate" from="ProjectPlanningElement" width="10%" formatter="dateFormatter">${plannedEnd}</th>  
    ';
  
  private static $_fieldsTooltip = array(
      "fixPlanning"=> "tooltipFixPlanning",
      "fixPerimeter"=> "tooltipFixPerimeter",
      "paused"=>"tooltipPaused",
      "allowReduction"=> "tooltipAllowRedution",
      "isUnderConstruction" => "tooltipUnderConstruction",
      "excludeFromGlobalPlanning" => "tooltipExcludeFromGlobalPlanning",
      "commandOnValidWork"=> "tooltipCommandOnValidWork"
  );
// Removed in 1.2.0 
//     <th field="wbs" from="ProjectPlanningElement" width="5%" >${wbs}</th>
// Removed in 2.0.1
//  <th field="nameRecipient" width="10%" >${idRecipient}</th>
  

  private static $_fieldsAttributes=array("name"=>"required",                                   
    "done"=>"nobr",
    "idle"=>"nobr",
    "handled"=>"nobr",
    "sortOrder"=>"hidden",
    "codeType"=>"hidden",
    "idProjectType"=>"required",
    "longitude"=>"hidden", "latitude"=>"hidden",
    "idStatus"=>"required",
    "idleDate"=>"nobr",
    "cancelled"=>"nobr",
    "organizationInherited"=>"hidden",
    "organizationElementary"=>"hidden",
    "fixPlanning"=>"nobr",
    "allowReduction"=>"nobr",
    "paused"=>"",
    "idCatalogUO"=>"hidden",
    "fixPerimeter"=>"nobr",
    "isUnderConstruction"=>"nobr",
    "excludeFromGlobalPlanning"=>"nobr",
    "commandOnValidWork"=>"nobr",
    "isLeaveMngProject"=>"hidden",
    "locked"=>"hidden",
    "paused"=>"nobr",
    "localCurrency"=>"smallWidth",
    "localCurrencyPosition"=>"smallWidth",
    "localToGlobalConversion"=>"nobr,smallWidth",
    "globalToLocalConversion"=>"nobr,smallWidth",
    "localToGlobalDisplay"=>"calculated,readonly,noimport,display",
    "globalToLocalDisplay"=>"calculated,readonly,noimport,display",
    "localToGlobalTitle"=>"calculated,readonly,noimport,display",
    "globalToLocalTitle"=>"calculated,readonly,noimport,display",
    "inheritedCurrency"=>"hidden, noImport"
  );   
 
  private static $_colCaptionTransposition = array('idResource'=>'manager',
   'idProject'=> 'isSubProject',
   'idProjectType'=>'type',
   'idContact'=>'billContact',
   'idRiskLevel'=>'riskLevel',
   'idUser'=>'issuer');

  private static $_subProjectList=array();
  private static $_subProjectFlatList=array();
  private static $_subProjectListWithoutNotSameCatalog=array();
  private static $_subProjectListWithoutNotSameCalendarDefinition=array();
  private static $_drawSubProjectsDone=array();
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    if ($id=='*') {$id='';}
  	parent::__construct($id,$withoutDependentObjects);
  }

   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }

// ============================================================================**********
// GET STATIC DATA FUNCTIONS
// ============================================================================**********
  
  /** ==========================================================================
   * Return the specific layout
   * @return String the layout
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }  

    /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
// ============================================================================**********
// GET VALIDATION SCRIPT
// ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo frameword)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);

    if ($colName=="idle") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.checked) { ';
      $colScript .= '    if (dijit.byId("idleDate").get("value")==null) {';
      $colScript .= '      var curDate = new Date();';
      $colScript .= '      dijit.byId("idleDate").set("value", curDate); ';
      $colScript .= '    }';
//       $colScript .= '    if (! dijit.byId("done").get("checked")) {';
//       $colScript .= '      dijit.byId("done").set("checked", true);';
//       $colScript .= '    }';  
      $colScript .= '  } else {';
      $colScript .= '    dijit.byId("idleDate").set("value", null); ';
      $colScript .= '  } '; 
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="done") {   
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.checked) { ';
      $colScript .= '    if (dijit.byId("doneDate").get("value")==null) {';
      $colScript .= '      var curDate = new Date();';
      $colScript .= '      dijit.byId("doneDate").set("value", curDate); ';
      $colScript .= '    }';
      $colScript .= '  } else {';
      $colScript .= '    dijit.byId("doneDate").set("value", null); ';
//       $colScript .= '    if (dijit.byId("idle").get("checked")) {';
//       $colScript .= '      dijit.byId("idle").set("checked", false);';
//       $colScript .= '    }'; 
      $colScript .= '  } '; 
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="idProject") {   
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  dojo.byId("ProjectPlanningElement_wbs").value=""; ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="idStatus") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= htmlGetJsTable('Status', 'setIdleStatus', 'tabStatusIdle');
      $colScript .= htmlGetJsTable('Status', 'setDoneStatus', 'tabStatusDone');
      $colScript .= '  var setIdle=0;';
      $colScript .= '  var filterStatusIdle=dojo.filter(tabStatusIdle, function(item){return item.id==dijit.byId("idStatus").value;});';
      $colScript .= '  dojo.forEach(filterStatusIdle, function(item, i) {setIdle=item.setIdleStatus;});';
      $colScript .= '  if (setIdle==1) {';
      $colScript .= '    dijit.byId("idle").set("checked", true);';
      $colScript .= '  } else {';
      $colScript .= '    dijit.byId("idle").set("checked", false);';
      $colScript .= '  }';
      $colScript .= '  var setDone=0;';
      $colScript .= '  var filterStatusDone=dojo.filter(tabStatusDone, function(item){return item.id==dijit.byId("idStatus").value;});';
      $colScript .= '  dojo.forEach(filterStatusDone, function(item, i) {setDone=item.setDoneStatus;});';
      $colScript .= '  if (setDone==1) {';
      $colScript .= '    dijit.byId("done").set("checked", true);';
      $colScript .= '  } else {';
      $colScript .= '    dijit.byId("done").set("checked", false);';
      $colScript .= '  }';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';     
    }else if ($colName=="fixPerimeter") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '    var trAllowReduc=dojo.byId("allowReduction").parentNode.parentNode.parentNode;';
      $colScript .= '  if (this.checked) { ';
      $colScript .= '    if(trAllowReduc.style.display=="none")trAllowReduc.style.display="table-row";';
      $colScript .= '    dojo.query(".generalColClass.allowReductionClass").forEach(function(domNode){domNode.style.display="inline-block";});';
      $colScript .= '    var inputAllaowReduc=dojo.byId("allowReduction");';
      $colScript .= '    if (dojo.byId("_lib_helpAllowReduction")) {'; 
      $colScript .= '      inputAllaowReduc.parentNode.insertAdjacentElement("afterend",dojo.byId("_lib_helpAllowReduction"));';
      $colScript .= '      dojo.byId("_lib_helpAllowReduction").style.display="";';
      $colScript .= '    }';
      $colScript .= '  } else if (dojo.byId("_lib_helpAllowReduction")){';
      $colScript .= '    trAllowReduc.style.display="none";';
      $colScript .= '    dojo.query(".allowReductionClass").forEach(function(domNode){domNode.style.display="none";});';
      $colScript .= '     dojo.byId("_lib_helpAllowReduction").style.display="none";';
      $colScript .= '     dijit.byId("allowReduction").set("value", 0);';
      $colScript .= '     dijit.byId("allowReduction").set("checked", "");';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';     
    } else if ($colName=="idProjectType") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  setDefaultCategory(this.value);';
      $colScript .= '</script>';
    }else if ($colName=="paused"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(this.checked){';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",true);';
      $colScript .= '   dijit.byId("fixPlanning").set("checked",true);';
      $colScript .= '   dijit.byId("fixPlanning").set("value",1);';
      $colScript .= '  }else{';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",false);';
      $colScript .= '   dijit.byId("fixPlanning").set("checked",false);';
      $colScript .= '   dijit.byId("fixPlanning").set("value",0);';
      $colScript .= '  }';
      $colScript .= '</script>';
    }else if ($colName=="localToGlobalConversion"){  
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (cancelRecursiveChange_OnGoingChange) return;';
      $colScript .= '  cancelRecursiveChange_OnGoingChange=true;';
      $colScript .= '  if (this.value) {';
      $colScript .= '    reverse=Math.round(100000/this.value)/100000;';
      $colScript .= '    dijit.byId("globalToLocalConversion").set("value",reverse);';
      $colScript .= '  }';
      $colScript .= '  calculateCurrencyConversionDisplay();';
      $colScript .= '  setTimeout("cancelRecursiveChange_OnGoingChange=false;",100);';
      $colScript .= '</script>';
    }else if ($colName=="globalToLocalConversion"){  
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (cancelRecursiveChange_OnGoingChange) return;';
      $colScript .= '  cancelRecursiveChange_OnGoingChange=true;';
      $colScript .= '  if (this.value) {';
      $colScript .= '    reverse=Math.round(100000/this.value)/100000;';
      $colScript .= '    dijit.byId("localToGlobalConversion").set("value",reverse);';
      $colScript .= '  }';
      $colScript .= '  calculateCurrencyConversionDisplay();';
      $colScript .= '  setTimeout("cancelRecursiveChange_OnGoingChange=false;",100);';
      $colScript .= '</script>';
    }else if ($colName=="localCurrency" || $colName=="localCurrencyPosition"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  calculateCurrencyConversionDisplay();';
      $colScript .= '</script>';
    }
    
    return $colScript;
  }
  
// ============================================================================**********
// MISCELLANOUS FUNCTIONS
// ============================================================================**********
  
// MTY - LEAVE SYSTEM

static function getLeaveProject() {
    if (! sessionValueExists('leaveProjectId')) {
      $crit=['isLeaveMngProject' => 1];
      //$prj = SqlElement::getSingleSqlElementFromCriteria('Project', $crit, true);
      $obj=new Project();
      $prjList = $obj->getSqlElementsFromCriteria($crit, false,null,null,false,true);
      if (count($prjList)==1) {
        $prj=reset($prjList);
      } else {
        $prj=null;
        if (count($prjList)>1) {
          errorLog("Cannot retreive Leave Project : too many projects are tagged 'isLeaveMngProject'");
          foreach ($prjList as $tmp) { errorLog("   Project #$tmp->id - $tmp->name");}
        }
      }
      if ($prj and $prj->id!==null) {
        setSessionValue('leaveProjectId', $prj->id);
        setSessionValue('leaveProject', $prj);
      } else {
        setSessionValue('leaveProjectId', -1); // Store -1 to be sure to use cache, otherwise cache not used if module is disabled
        setSessionValue('leaveProject', null);
      }    
    } 
    return getSessionValue('leaveProject');
}
  
  /** ==========================================================================
   * Get the project's id that is the leave project (ie : isLeaveMngProject=1)
   * If not done, store in session this id
   * @return integer The leave project's id
*/
static function getLeaveProjectId() {
    if (! sessionValueExists('leaveProjectId')) {
        Project::getLeaveProject();
    }
    $ret=getSessionValue('leaveProjectId');
    return ($ret==-1)?0:$ret;
}

private function setLeaveProjectId() {
    setSessionValue('leaveProjectId', $this->id);
}

private function setLeaveProject() {
    setSessionValue('leaveProject', $this);
}


/** ==========================================================================
 * Return true if the leave Project is visible for the connected user 
 * @return boolean True if leave system is activ and user is administrator
*/
static function isProjectLeaveVisible() {
    return false;
    $user = getSessionUser();
    $ret = (($user->idProfile==1 and isLeavesSystemActiv())?true:false);
    return $ret;
}

/** ==========================================================================
   * Return true if the project that have the id passed in parameter is the leave project
   * @param $id integer The project's id to test if it's the leave project
   * @return boolean
*/
static function isTheLeaveProject($id=null) {
    if ($id==null) {
        return false;        
    }
    $ret = ($id==self::getLeaveProjectId()?true:false);
    return $ret;
}

// MTY - LEAVE SYSTEM

  
  /** ==========================================================================
   * Retrieves the hierarchic sub-projects of the current project
   * @return Array an array of Projects as sub-projects
   */
  public function getSubProjects($limitToActiveProjects=false, $withoutDependantElement=false) {
  scriptLog("Project($this->id)->getSubProjects($limitToActiveProjects)");  	
    if ($this->id==null or $this->id=='') {
      return array();
    }
    $crit=array();
    if ($this->id=='*') {
      $crit['idProject']='';
    } else {
      $crit['idProject']=$this->id;
    }

    if ($limitToActiveProjects) {
      $crit['idle']='0';
    }
    $sorted=SqlList::getListWithCrit('Project',$crit,'name');
    //$subProjects=$this->getSqlElementsFromCriteria($crit, false);
    //uasort($subProjects,'wbsProjectSort');
    $subProjects=array();
    foreach($sorted as $projId=>$projName) {
// MTY - LEAVE SYSTEM
        if (isLeavesSystemActiv()) {
          if (self::isTheLeaveProject($projId) && !self::isProjectLeaveVisible()) {continue;}
        }
// MTY - LEAVE SYSTEM        
      $subProjects[$projId]=new Project($projId, $withoutDependantElement);
    }
    return $subProjects;
  }

  /** ==========================================================================
   * Retrieves the hierarchic sub-projects of the current project
   * @return Array an array of Projects as sub-projects
   */
  public function getSubProjectsList($limitToActiveProjects=false) {
  scriptLog("Project($this->id)->getSubProjectsList(limitToActiveProjects=$limitToActiveProjects)");
    if ($this->id==null or $this->id=='') {
      return array();
    }
    $crit=array();
    if ($this->id=='*') {
      $crit['idProject']='';
    } else {
      $crit['idProject']=$this->id;
    }
    if ($limitToActiveProjects) {
      $crit['idle']='0';
    }
    $sorted=SqlList::getListWithCrit('Project',$crit,'name', null, ! $limitToActiveProjects);
// MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
        // For the Leave Project, if it's not visible by connected user ==> not taken into account
        if (pq_array_key_exists(self::getLeaveProjectId(), $sorted) && !self::isProjectLeaveVisible()) {
            unset($sorted[self::getLeaveProjectId()]);
        }
    }
// MTY - LEAVE SYSTEM
    
    return $sorted;
  }
  
  /** ==========================================================================
   * Recusively retrieves all the hierarchic sub-projects of the current project
   * @return Array an array containing id, name, subprojects (recursive array)
   */
  public function getRecursiveSubProjects($limitToActiveProjects=false) {
    scriptLog("Project($this->id)->getRecursiveSubProjects($limitToActiveProjects)");
    //$result=$this->getRecursiveSubProjectsOld($limitToActiveProjects);                 // Old way to do
    $result=self::getRecursiveSubProjectsForId($this->id, $limitToActiveProjects);     // OK works, and is fast
    //$result=self::getRecursiveSubProjectsForIdFast($this->id, $limitToActiveProjects); // Should be the fastest, but not working : inherited rights are lost
    return $result;
  }
  public function getRecursiveSubProjectsOld($limitToActiveProjects=false) {
    $key=$this->id.'-'.(($limitToActiveProjects)?'active':'all');
// MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
      if (self::isTheLeaveProject($this->id) && !self::isProjectLeaveVisible()) {return null;}
    }
// MTY - LEAVE SYSTEM
    if (isset(self::$_subProjectList[$key])) {
    	return self::$_subProjectList[$key];
    }    	
    $crit=array('idProject'=>$this->id);
    if ($limitToActiveProjects) {
      $crit['idle']='0';
    }
    //$obj=new Project();
    $subProjects=$this->getSqlElementsFromCriteria($crit, false,null,null,null,true) ;
    $subProjectList=null;
    foreach ($subProjects as $subProj) {
// MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
      if (self::isTheLeaveProject($subProj->id) && !self::isProjectLeaveVisible()) {continue;}
    }  
// MTY - LEAVE SYSTEM
      $recursiveList=null;
      $recursiveList=$subProj->getRecursiveSubProjects($limitToActiveProjects);
      $arrayProj=array('id'=>$subProj->id, 'name'=>$subProj->name, 'subItems'=>$recursiveList);
      $subProjectList[]=$arrayProj;
    }
    self::$_subProjectList[$key]=$subProjectList;
    return $subProjectList;
  }
  
  private static function getRecursiveSubProjectsForId($forProjectId, $limitToActiveProjects=false) {
    // PBER : update in V10.0 so that there is no need to instanciate all sub-projects as we only want to get the name
    scriptLog("Project::getRecursiveSubProjectsForId($forProjectId, $limitToActiveProjects)");
    $key=$forProjectId.'-'.(($limitToActiveProjects)?'active':'all');
    // MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
      if (self::isTheLeaveProject($forProjectId) && !self::isProjectLeaveVisible()) {return null;}
    }
    // MTY - LEAVE SYSTEM
    if (isset(self::$_subProjectList[$key])) {
      return self::$_subProjectList[$key];
    }
    $crit=array('idProject'=>$forProjectId);
    if ($limitToActiveProjects) {
      $crit['idle']='0';
    }
    $subProjects=SqlList::getListWithCrit('Project',$crit,'name',null, ! $limitToActiveProjects);
    $subProjectList=null;
    foreach ($subProjects as $subProjId=>$subProjName) {
      if (isLeavesSystemActiv()) {
        if (self::isTheLeaveProject($subProjId) && !self::isProjectLeaveVisible()) {continue;}
      }
      $recursiveList=null;
      $recursiveList=self::getRecursiveSubProjectsForId($subProjId,$limitToActiveProjects);
      $arrayProj=array('id'=>$subProjId, 'name'=>$subProjName, 'subItems'=>$recursiveList);
      $subProjectList[]=$arrayProj;
    }
    self::$_subProjectList[$key]=$subProjectList;
    return $subProjectList;
  }
  private static function getRecursiveSubProjectsForIdFast($forProjectId, $limitToActiveProjects=false) {
    // PBER : update in V10.0 so that there is no need to instanciate all sub-projects as we only want to get the name
    scriptLog("Project::getRecursiveSubProjectsForIdFast($forProjectId, $limitToActiveProjects)");
    $forProjectId=pq_trim($forProjectId);
    $key=$forProjectId.'-'.(($limitToActiveProjects)?'active':'all');
    // MTY - LEAVE SYSTEM
    $leaveProj=null;
    if (isLeavesSystemActiv()) {
      if (self::isTheLeaveProject($forProjectId) && !self::isProjectLeaveVisible()) {return null;}
      $leaveProj=Project::getLeaveProjectId();
    }
    // MTY - LEAVE SYSTEM
    if (isset(self::$_subProjectList[$key])) {
      if (self::$_subProjectList[$key]=='EMPTY') return null;
      else return self::$_subProjectList[$key];
    }
    
    $prj=new Project();$prjTable=$prj->getDatabaseTableName();
    $query="select id, name, sortOrder as wbs, idProject as parent from $prjTable Where 1=1 ";
    if ($forProjectId) {
      $wbs=SqlList::getFieldFromId('Project',$forProjectId,'sortOrder');
      $query.=" and sortOrder like '$wbs%'";
    }
    if ($limitToActiveProjects) $query.=" and idle=0";
    $query.=' ORDER BY sortOrder';
    $res=Sql::query($query);
    $projects=array();
    $subs=array();
    if (!$forProjectId) $subs['0']=array();
    foreach($res as $row) {
      $id=$row['id'];
      if ($id==$leaveProj) continue;
      $name=$row['name'];
      $wbs=$row['wbs'];
      $parent=$row['parent'];
      $projects[$id]=array('id'=>$id, 'name'=>$name, 'subItems'=>null);
      if (!isset($subs[$id])) $subs[$id]=array();
      if (!$parent) $parent='0';
      //if ($parent) {
        if (isset($subs[$parent])) $subs[$parent][$id]=$name;
        else $subs[$parent]=array($id=>$name);
      //}
    }
    foreach (array_reverse($subs,true) as $id=>$tab) {
      $projects[$id]['subItems']=null;
      if (isset($subs[$id])) {
        if (count($subs[$id])>0) $projects[$id]['subItems']=array();
        foreach($subs[$id] as $subId=>$subName) {
          $projects[$id]['subItems'][]=$projects[$subId];
        }
      }
      $keySub=$id.'-'.(($limitToActiveProjects)?'active':'all');
      if ($projects[$id]['subItems']==null) self::$_subProjectList[$keySub]='EMPTY';
      else self::$_subProjectList[$keySub]=$projects[$id]['subItems'];
    }
    if (count($projects)==0) return null;
    if (! pq_trim($forProjectId)) return $projects['0']['subItems'];
    if (! isset($projects[$forProjectId])) return null;
    return $projects[$forProjectId]['subItems'];
  }
  
  /** ==========================================================================
   * Recusively retrieves all the sub-projects of the current project
   * and presents it as a flat array list of id=>name
   * @return Array an array containing the list of subprojects as id=>name
   * 
   */
  public function getRecursiveSubProjectsFlatList($limitToActiveProjects=false, $includeSelf=false, $tab=null) {
  scriptLog("Project($this->id)->getRecursiveSubProjectsFlatList($limitToActiveProjects,$includeSelf)");   	
    $key=$this->id.'-'.(($limitToActiveProjects)?'active':'all').(($includeSelf)?'-withSelf':'');
    if (isset(self::$_subProjectFlatList[$key])) {
      return self::$_subProjectFlatList[$key];
    }
    if (!$tab) $tab=$this->getRecursiveSubProjects($limitToActiveProjects);
    $list=array();
    if ($includeSelf and $this->id) {
      $list[$this->id]=$this->name;
    }
    if ($tab) {
      foreach($tab as $subTab) {
        $id=$subTab['id'];
        $name=$subTab['name'];
        $list[$id]=$name;
        $subobj=new Project();
        $subobj->id=$id;
        $sublist=$subobj->getRecursiveSubProjectsFlatList($limitToActiveProjects,false,$subTab['subItems']);
        if ($sublist) {
          $list=array_merge_preserve_keys($list,$sublist);
        }
      }
    }
    self::$_subProjectFlatList[$key]=$list;
    return $list;
  }
  
  private static $topProjectListArray=array();
  public function getTopProjectList($includeSelf=false) {
  scriptLog("Project($this->id)->getTopProjectList($includeSelf)");
    if (isset(self::$topProjectListArray[$this->id.'#'.$includeSelf])) {
    	return self::$topProjectListArray[$this->id.'#'.$includeSelf];	
    }
    if ($includeSelf and $this->id) {
      if (isLeavesSystemActiv()) {
        if (!self::isTheLeaveProject($this->id) || self::isProjectLeaveVisible()) {
          return array_merge(array($this->id),$this->getTopProjectList(false));
        }
      } else {
        return array_merge(array($this->id),$this->getTopProjectList(false));            
      }
    }
    if (! $this->idProject) {
      return array();
    } else {
      $topProj=new Project($this->idProject,true);
      $topList=$topProj->getTopProjectList();
      $result=array_merge(array($this->idProject),$topList);
      self::$topProjectListArray[$this->id.'#'.$includeSelf]=$result;
      return $result;
    }
  }
  
  /** ==========================================================================
   * Recusively retrieves all the hierarchic sub-projects of the current project
   * without idCatalogUo
   * @return Array an array containing id, name, subprojects (recursive array)
   */
  public function getRecursiveSubProjectsIdWithSameCatalog($idCatalogUo=false,$limitToActiveProjects=false) {

    $key=$this->id.'-'.(($limitToActiveProjects)?'active':'all');
    if (isLeavesSystemActiv()) {
      if (self::isTheLeaveProject($this->id) && !self::isProjectLeaveVisible()) return null;
    }

    if (isset(self::$_subProjectListWithoutNotSameCatalog[$key])) return self::$_subProjectListWithoutNotSameCatalog[$key];
    
    $where="idProject = ".Sql::fmtId($this->id)." and (idCatalogUO is null";
    $where.=($idCatalogUo)?" or idCatalogUO = ".Sql::fmtId($idCatalogUo).")" :")";
    if ($limitToActiveProjects) $where.=" and idle = 0";
    

    $subProjects=$this->getSqlElementsFromCriteria(null, false,$where,null,null,true) ;
    $projectList=array();
    $cp=0;
    foreach ($subProjects as $subProj) {
      // MTY - LEAVE SYSTEM
      if (isLeavesSystemActiv()) {
        if (self::isTheLeaveProject($subProj->id) && !self::isProjectLeaveVisible()) {continue;}
      }
      $projectList[$subProj->id]=$subProj->id;
      // MTY - LEAVE SYSTEM
      $recursiveList=null;
      $subIdCatalog=($subProj->idCatalogUO)?$subProj->idCatalogUO:false;
      $subProjectList=$subProj->getRecursiveSubProjectsIdWithSameCatalog($subIdCatalog,$limitToActiveProjects);
      $projectList=array_merge_preserve_keys($subProjectList,$projectList);
      $cp++;
    }
    self::$_subProjectListWithoutNotSameCatalog[$key]=$projectList;
    return $projectList;
  }
  /** ==========================================================================
   * Recusively retrieves all the hierarchic sub-projects of the current project
   * without idCatalogUo
   * @return Array an array containing id, name, subprojects (recursive array)
   */
  public function getRecursiveSubProjectsIdWithSameCalendarDefinition($idCalendarDefinition=false,$limitToActiveProjects=false) {
  
    $key=$this->id.'-'.(($limitToActiveProjects)?'active':'all');
    if (isLeavesSystemActiv()) {
      if (self::isTheLeaveProject($this->id) && !self::isProjectLeaveVisible()) return null;
    }
  
    if (isset(self::$_subProjectListWithoutNotSameCalendarDefinition[$key])) return self::$_subProjectListWithoutNotSameCalendarDefinition[$key];
  
    $where="idProject = ".Sql::fmtId($this->id)." and (idCalendarDefinition is null";
    $where.=($idCalendarDefinition)?" or idCalendarDefinition = ".Sql::fmtId($idCalendarDefinition).")" :")";
    if ($limitToActiveProjects) $where.=" and idle = 0";
  
  
    $subProjects=$this->getSqlElementsFromCriteria(null, false,$where,null,null,true) ;
    $projectList=array();
    $cp=0;
    foreach ($subProjects as $subProj) {
      // MTY - LEAVE SYSTEM
      if (isLeavesSystemActiv()) {
        if (self::isTheLeaveProject($subProj->id) && !self::isProjectLeaveVisible()) {continue;}
      }
      $projectList[$subProj->id]=$subProj->id;
      // MTY - LEAVE SYSTEM
      $recursiveList=null;
      $subIdCalendarDefinition=($subProj->idCalendarDefinition)?$subProj->idCalendarDefinition:false;
      $subProjectList=$subProj->getRecursiveSubProjectsIdWithSameCalendarDefinition($subIdCalendarDefinition,$limitToActiveProjects);
      $projectList=array_merge_preserve_keys($subProjectList,$projectList);
      $cp++;
    }
    self::$_subProjectListWithoutNotSameCalendarDefinition[$key]=$projectList;
    return $projectList;
  }
  /** =========================================================================
   * Draw a specific item for the current class.
   * @param String $item the item. Correct values are : 
   *    - subprojects => presents sub-projects as a tree
   * @return String an html string able to display a specific item
   *  must be redefined in the inherited class
   */
  public function drawSpecificItem($item, $readOnly=false){
//scriptLog("Project($this->id)->drawSpecificItem($item)");
    global $drawCheckBox;
    $result="";
    if ($item=='raciMatrix') {
      if (! $this->idRaciModel) {
        return '';
      }
      $model=new RaciModel($this->idRaciModel);
      if (! $model->id) {
        return '';
      }
      return $model->drawMatrix(false, $this->id);
    }
    if ($item=='subprojects') {
      if(isNewGui()){
        $result .="<table style='width:100%'><tr><td >";
      }else{
        $result .="<table><tr><td class='label' valign='top'><label>" . i18n('subProjects') . "&nbsp;:&nbsp;</label>";
        $result .="</td><td>";
      }
      if ($this->id) {
        $drawCheckBox = 'false';
        $result .= $this->drawSubProjects();
      }
      $result .="</td></tr></table>";
      return $result;
    /*} else if ($item=='affectations') {
      $aff=new Affectation();
      $result .="<table><tr><td class='label' valign='top'><label>" . i18n('resources') . "&nbsp;:&nbsp;</label>";
      $result .="</td><td>";
      if ($this->id) {
        $result .= $aff->drawAffectationList(array('idProject'=>$this->id,'idle'=>'0'),'Resource');
      }
      $result .="</td></tr></table>";
      $result .="<table><tr><td class='label' valign='top'><label>" . i18n('contacts') . "&nbsp;:&nbsp;</label>";
      $result .="</td><td>";
      if ($this->id) {
        $result .= $aff->drawAffectationList(array('idProject'=>$this->id,'idle'=>'0'),'Contact');
      }
      $result .="</td></tr></table>";
      return $result;*/
    } else if ($item=='affectations') {
      $aff=new Affectation();
      $critArray=array('idProject'=>(($this->id)?$this->id:'0'));
      $affList=$aff->getSqlElementsFromCriteria($critArray, false);
      drawAffectationsFromObject($affList, $this, 'ResourceAll', false);  
      if (isModernUi()) echo '<br/>';
      drawAffectationsFromObject($affList, $this, 'Contact', false);
      if (isModernUi()) echo '<br/>';
      drawAffectationsFromObject($affList, $this, 'User', false);
      return $result;
    } else if ($item=='rf') { 
    	global $flashReport, $print;
    	if (! $print and $this->id and isset($flashReport) and ($flashReport==true or $flashReport=='true')) {
    		$user=getSessionUser();
    		$crit=array('idProfile'=>$user->getProfile($this->id), 'idReport'=>51);
    		$hr=SqlElement::getSingleSqlElementFromCriteria('HabilitationReport', $crit);
    		if ($hr and $hr->allowAccess=='1') {
	    		$top=30;$left=10;
	    		$result.='<div style="position: absolute; top:'.$top.'px;left:'.$left.'px;">'
	    		  . '<button id="printButtonRf" dojoType="dijit.form.Button" showlabel="false"'
	    		  . ' title="'.i18n('flashReport').'"'
	          . ' iconClass="iconFlash" >'
	          . ' <script type="dojo/connect" event="onClick" args="evt">'
	          . '  showPrint("../report/projectFlashReport.php?idProject='.htmlEncode($this->id).'");'
	          . ' </script>'
	          . '</button>'  
	          . '<button id="printButtonPefRf" dojoType="dijit.form.Button" showlabel="false"'
	          . ' title="'.i18n('flashReport').'"'
	          . ' iconClass="iconFlashPdf" >'
	          . ' <script type="dojo/connect" event="onClick" args="evt">'
	          . '  showPrint("../report/projectFlashReport.php?idProject='.htmlEncode($this->id).'", null, null, "pdf");'
	          . ' </script>'
	          . '</button>'  
	          . '</div>';
    		}
        return $result;
    	}
    } else if ($item=='restrictTypes') {
      global $print;
      if (!$this->id) return '';
      if (!$print) {
        $result.= '<button id="buttonRestrictTypes" dojoType="dijit.form.Button" showlabel="true"'
          . ' title="'.i18n('helpRestrictTypesProject').'" iconClass="iconType16" class="roundedVisibleButton" >'
          . '<span>'.i18n('restrictTypes').'</span>'
          . ' <script type="dojo/connect" event="onClick" args="evt">'
          . '  var params="&idProject='.$this->id.'";'
          . '  params+="&idProjectType="+dijit.byId("idProjectType").get("value");'    
          . '  loadDialog("dialogRestrictTypes", null, true, params);'
          . ' </script>'
          . '</button>';
        $result.= '<span style="font-size:80%">&nbsp;&nbsp;&nbsp;('.i18n('helpRestrictTypesProjectInline').')</span>';
      }
      $result.='<table style="witdh:100%"><tr><td class="label" style="width:220px">'.i18n('existingRestrictions').Tool::getDoublePoint().'</td><td>';
      $result.='<div id="resctrictedTypeClassList" style="position:relative;left:5px;top:2px">';
      $list=Type::getRestrictedTypesClass($this->id,null,null);
      $cpt=0;
      foreach ($list as $cl) {
        $cpt++;
        $result.=(($cpt>1)?', ':'').$cl;
      }
      if ($cpt==0) $result.='<span style="color:#a0a0a0;"><i>'.i18n('paramNone').'</i></span>';
      $result.='</div>';
      $result.='</td></tr><tr><td colspan="2">&nbsp;</td></tr></table>';
      return $result;
    } else if ($item=='restrictLists') {
      global $print;
      if (!$this->id) return '';
      if (!$print) {
        $result.= '<button id="buttonRestrictLists" dojoType="dijit.form.Button" showlabel="true"'
          . ' title="'.i18n('helpRestrictListsProject').'" iconClass="iconType16" class="roundedVisibleButton">'
          . '<span>'.i18n('restrictLists').'</span>'
          . ' <script type="dojo/connect" event="onClick" args="evt">'
          . '  var params="&idProject='.$this->id.'";'
          . '  params+="&idProjectType="+dijit.byId("idProjectType").get("value");'
          . '  loadDialog("dialogRestrictLists", null, true, params);'
          . ' </script>'
          . '</button>';
        $result.= '<span style="font-size:80%; ">&nbsp;&nbsp;&nbsp;('.i18n('helpRestrictListsProjectInline').')</span>';
      }
      $result.='<table style="witdh:100%"><tr><td class="label" style="width:220px">'.i18n('existingRestrictions').Tool::getDoublePoint().'</td><td>';
      $result.='<div id="resctrictedListClassList" style="position:relative;left:5px;top:2px">';
      $list=ListHideValue::getRestrictedLists($this->id);
      $cpt=0;
      foreach ($list as $cl) {
        $cpt++;
        $result.=(($cpt>1)?', ':'').i18n($cl);
      }
      if ($cpt==0) $result.='<span style="color:#a0a0a0;"><i>'.i18n('paramNone').'</i></span>';
      $result.='</div>';
      $result.='</td></tr><tr><td colspan="2">&nbsp;</td></tr></table>';
      return $result;
    } else if ($item=='isSynchronised') {
      global $print;
      if (!$this->id) return '';
      $synch = new Synchronization();
      if(!$synch->isProjectSynchronized($this->id)){
        //Un bouton qui permet dÃ¢â‚¬â„¢accÃƒÂ©der ÃƒÂ  la fenÃƒÂªtre pop-up de dÃƒÂ©finition de la synchronisation.
        if (!$print) {
          $result.= '<button id="buttonShowSynchroniseDefinition" dojoType="dijit.form.Button" showlabel="true"'
                    . ' iconClass="iconType16" class="roundedVisibleButton" >'
                    . '<span>'.i18n('showSynchroniseDefinition').'</span>'
                    . ' <script type="dojo/connect" event="onClick" args="evt">'
                    . '  var params="&idProject='.$this->id.'";'
                    //. '  params+="&idProjectType="+dijit.byId("idProjectType").get("value");'
                    . '  loadDialog("dialogSynchroniseDefinition", null, true, params);'
                    . ' </script>'
                    . '</button>';
          return $result;
        }
     }else{
       $synch = Synchronization::getProjectSynchronizationDefinition($this->id);
       $countNbElement = SynchronizedItems::getNumberSynchronizedItemByProject($this->id);
       $attachAct = $synch->setActivity;
       if($attachAct){
         $attachAct = i18n('displayYes');
       }else{
         $attachAct = i18n('displayNo');
       }
       $result.='<table style="min-width:485px !important;">';
       $result.=' <tr><td class="assignData">'.i18n('colTypedeticketconcerne').'</td><td class="assignData">'.formatColor('Type', $synch->idOrigineType,false).'</td></tr>';
       $result.=' <tr><td class="assignData">'.i18n('colSynchroniseState').'</td><td class="assignData">'.formatColor('Status', $synch->idStatus,false).'</td></tr>';
       $result.=' <tr><td class="assignData">'.i18n('colSynchroniseActivityType').'</td><td class="assignData">'.formatColor('Type', $synch->idTargetType,false).'</td></tr>';
       $result.=' <tr><td class="assignData">'.i18n('SynchroniseActivityPlanning').'</td><td class="assignData" style="text-align:center;">'.$attachAct.'</td></tr>';
       $result.=' <tr><td class="assignData">'.pq_ucfirst(i18n('numberOfSynchElement')).'</td><td class="assignData" style="text-align:center;">'.$countNbElement.'</td></tr>';
       $result.='</table>';
       
         //$result.='<table style="witdh:100%"><tr><td class="label" style="width:220px">'.i18n('numberOfSynchElement').Tool::getDoublePoint().$countNbElement.'</td></tr></table>';
       if (!$print) {
         $result.= '<button id="buttonDisableSynchronizeDefinition" dojoType="dijit.form.Button" showlabel="true"'
                . '  iconClass="iconType16" class="roundedVisibleButton" >'
                . '<span>'.i18n('disableSynchronizeDefinition').'</span>'
                . ' <script type="dojo/connect" event="onClick" args="evt">'
                . '  var params="&idProject='.$this->id.'";'
                . '  loadDialog("dialogDisableSynchronizeDefinition", null, true, params);'
                . ' </script>'
                . '</button>';
       }
       return $result;
     }
    } else if ($item=='abacus'){
      global $print;
      if (!$print) {
        $result .= '<div style="display:flex; justify-content:flex-end;margin-right:10px;">';
        $result .= '  <table><tr>';
        $result .= '    <td style="display:flex; align-items:center;padding-right: 10px;">';
        $result .= '      <span style="display:inline-block;color:var(--color-text);;margin-right:10px;white-space:nowrap;">'. i18n('selectAbacusToAdd') . '</span>'; 
        $result .= '      <select id="selectAbacusToAdd" name="selectAbacusToAdd" dojoType="dijit.form.FilteringSelect" '.autoOpenFilteringSelect().' class="input" style="width:60%;">';  
        $result .= '        <option value=""></option>';
        
        $abacusDef = new AbacusDefinition();
        if ($this->idPhasing) {
          $abacusList = $abacusDef->getSqlElementsFromCriteria(array('idle'=>'0', 'idPhasing'=>$this->idPhasing),false,null,'sortOrder');
        } else {
          $abacusList = $abacusDef->getSqlElementsFromCriteria(array('idle'=>'0'),false,null,'sortOrder');
        }
        
        foreach ($abacusList as $ab) {
          $result .= '      <option value="' . $ab->id . '">'. htmlEncode($ab->name). '</option>';
        }    
        $result .= '      </select>';
        $result .= '    </td>';
            
        $result .= '    <td style="text-align:right;">';
        $result .= '      <a id="buttonAddAbacusLine" title="' . i18n('addAbacusLine') . '" onclick="addAbacusProject('.$this->id.',null, dijit.byId(\'selectAbacusToAdd\').get(\'displayedValue\'));">';
        $result .=          formatSmallButton('Add');
        $result .= '      </a>';
        $result .= '    </td>'; 
        $result .= '  </tr></table>';
        $result .= '</div>';
      }
      
      $abacusProj = new AbacusProject();
      $critArray = array('idProject' => (($this->id)?$this->id:'0'));
      $abacusProjectList =$abacusProj->getSqlElementsFromCriteria($critArray, false);
      $groupedAbacus = array();      
      foreach ($abacusProjectList as $abacus) {
        $groupedAbacus[$abacus->idAbacusDefinition][] = $abacus;
      }
      $abacusDefinitions = array();
      
      foreach (array_keys($groupedAbacus) as $idAbacusDef) {
        $abDef = new AbacusDefinition($idAbacusDef);
        $abacusDefinitions[$idAbacusDef] = $abDef;
      }
      
      uasort($abacusDefinitions, function($a, $b) {
        return $a->sortOrder <=> $b->sortOrder;
      });
      if (!$print && count($abacusDefinitions)>0) {
        
        $result .= '<div style=";isplay:flex;gap:15px;padding: 10px 10px 00px 0px;justify-content: flex-end;">'; 
        $result .= '<button id="createAssignmentsFromAbacus" dojoType="dijit.form.Button" showlabel="true" title="' . i18n('specifyPhasesForActivities') . '" iconClass="iconAbacus" class="roundedVisibleButton" ';
        $result .= ' onclick="createAssignmentsFromAbacus(' . $this->id . ')">';
        $result .= ' <span>' . i18n('buttonCreateAssignmentsFromAbacus') . '</span>';
        $result .= '</button>';
        
        $result .= '<button id="affectAbacusResources" dojoType="dijit.form.Button" showlabel="true" title="' . i18n('buttonAffectAbacusResources') . '" iconClass="iconAffectation" class="roundedVisibleButton"" ';
        $result .= ' onclick="affectAbacusResourcesToProject(' . $this->id . ');">';
        $result .= ' <span>' . i18n('buttonAffectAbacusResources') . '</span>';
        $result .= '</button>';
        $result .= '</div>';
        
        $result .= '<div style=";display:flex;gap:5px;padding: 0px 10px 10px 0px;">'; 
        $result .= '<button id="minusAllAbacus" dojoType="dijit.form.Button" showlabel="false"  title="'.i18n('buttonMinusAllAbacus').'" iconClass="imageColorNewGui iconMinus iconSize16" class="detailButton" onclick="closeAllAbacusSections()"></button>';
        $result .= '<button id="plusAllAbacus" dojoType="dijit.form.Button" showlabel="false" title="'.i18n('buttonPlusAllAbacus').'" iconClass="imageColorNewGui iconPlus iconSize16" class="detailButton" onclick="openAllAbacusSections()"></button>';
        $result .= '</div>';
      }
      foreach ($abacusDefinitions as $idAbacusDef => $abacusDef) {
        $list = $groupedAbacus[$idAbacusDef];
        $result .= drawAbacusFromObject($list, $this, $abacusDef, false);
      }
      return $result;
    }
  }
  

  /** =========================================================================
   * Flat model of the project tree, in display order (depth first).
   * Runs a single query. User rights are applied in the query, not afterwards.
   * @param $restrictToIds array|null extra id filter, intersected with rights
   * @return array id => array(name, idProject, level, hasChildren, reachable, handled)
   */
  public static function getSelectorTree($limitToActiveProjects=false, $limitToUserProjects=true, $restrictToIds=null) {
    scriptLog("Project::getSelectorTree(limitToActiveProjects=$limitToActiveProjects, limitToUserProjects=$limitToUserProjects)");
    $restrictIds=null;   // null = no id restriction
    $reachable=null;     // null = everything is reachable
    if ($limitToUserProjects) {
      $user=getSessionUser();
      if (! $user->_accessControlVisibility) {
        $user->getAccessControlRights(); // Force setup of accessControlVisibility
      }
      $reachable=$user->getVisibleProjects($limitToActiveProjects);
      if ($user->_accessControlVisibility != 'ALL') {
        $hier=$user->getHierarchicalViewOfVisibleProjects($limitToActiveProjects);
        $restrictIds=array();
        foreach ($hier as $key => $val) {
          $restrictIds[pq_substr($key,1)]=1; // hierarchical view keys are prefixed with '#'
        }
      }
    }
    // Extra restriction narrows the rights, it never replaces them
    if ($restrictToIds!==null) {
      if ($restrictIds===null) {
        $restrictIds=$restrictToIds;
      } else {
        foreach ($restrictIds as $id => $val) {
          if (! pq_array_key_exists($id, $restrictToIds)) {
            unset($restrictIds[$id]);
          }
        }
      }
    }
    $obj=new Project();
    $table=$obj->getDatabaseTableName();
    // Mixed case columns are aliased in lower case : PostgreSQL folds unquoted
    // identifiers, so the fetched line would not carry the mixed case key
    $query="select id, name, idProject as idproject, handled, done from " . $table . " where (1=1";
    foreach ($obj->getDatabaseCriteria() as $col => $val) {
      if ($val===null) {
        $query.=' and ' . $table . '.' . $obj->getDatabaseColumnName($col) . ' IS NULL';
      } else {
        $query.=' and ' . $table . '.' . $obj->getDatabaseColumnName($col) . '=' . Sql::str($val);
      }
    }
    if ($limitToActiveProjects) {
      $query.=" and idle=0";
    }
    if ($restrictIds!==null) {
      $query.=" and id in " . transformListIntoInClause($restrictIds);
    }
    // Order by sortOrder, not name : sortOrder carries the project tree order
    $query.=") order by " . $table . ".sortOrder";

    $rows=array();
    $result=Sql::query($query);
    while ($line=Sql::fetchLine($result)) {
      $id=$line['id'];
// MTY - LEAVE SYSTEM
      if (isLeavesSystemActiv()) {
        if (self::isTheLeaveProject($id) and ! self::isProjectLeaveVisible()) { continue; }
      }
// MTY - LEAVE SYSTEM
      $rows[$id]=$line;
    }
    // Group by parent. A node whose parent is out of scope becomes a root.
    $childrenOf=array();
    foreach ($rows as $id => $line) {
      $parent=$line['idproject'];
      if (! $parent or ! isset($rows[$parent])) { $parent=0; }
      $childrenOf[$parent][]=$id;
    }
    $model=array();
    $seen=array();
    self::buildSelectorLevel($rows, $childrenOf, 0, 1, $model, $seen, $reachable);
    return $model;
  }

  /** =========================================================================
   * Depth first walk filling the flat model.
   * $seen guards against parent/child cycles stored in database.
   */
  private static function buildSelectorLevel(&$rows, &$childrenOf, $parentId, $level, &$model, &$seen, &$reachable) {
    if (! isset($childrenOf[$parentId])) { return; }
    foreach ($childrenOf[$parentId] as $id) {
      if (isset($seen[$id])) { continue; }
      $seen[$id]=true;
      $model[$id]=array(
        'name'        => $rows[$id]['name'],
        'idProject'   => $rows[$id]['idproject'],
        'level'       => $level,
        'hasChildren' => isset($childrenOf[$id]),
        'reachable'   => ($reachable===null or pq_array_key_exists($id, $reachable)),
        'handled'     => ($rows[$id]['handled']=='1' and $rows[$id]['done']=='0'),
      );
      self::buildSelectorLevel($rows, $childrenOf, $id, $level+1, $model, $seen, $reachable);
    }
  }

  /** =========================================================================
   * Keeps only handled and not done projects, plus their ancestors.
   * Works in memory, runs no query.
   */
  public static function filterSelectorTreeOnHandled($model) {
    $keep=array();
    foreach ($model as $id => $row) {
      if (! $row['handled']) { continue; }
      $keep[$id]=true;
      $parent=$row['idProject'];
      while ($parent and isset($model[$parent]) and ! isset($keep[$parent])) {
        $keep[$parent]=true;
        $parent=$model[$parent]['idProject'];
      }
    }
    foreach ($model as $id => $row) {
      if (! isset($keep[$id])) { unset($model[$id]); }
    }
    return $model;
  }



  /** =========================================================================
   * Deepest level that fits under $threshold projects.
   * @param $threshold int project count limit, 0 disables the mechanism
   * @return int 0 when everything fits, so no limit has to be applied
   */
  public static function computeAutoLevelLimit($model, $threshold) {
    if (! $threshold or $threshold<=0) { return 0; }
    $counts=array();
    foreach ($model as $row) {
      $lvl=$row['level'];
      $counts[$lvl]=(isset($counts[$lvl])?$counts[$lvl]:0)+1;
    }
    if (count($counts)==0) { return 0; }
    ksort($counts);
    $cumul=0;
    foreach ($counts as $level => $nb) {
      if ($cumul+$nb > $threshold) {
        // Always keep the roots, even when they exceed the threshold on their own
        return ($level-1 < 1) ? 1 : $level-1;
      }
      $cumul+=$nb;
    }
    return 0;
  }

  /** =========================================================================
   * Auto limit threshold, hard coded in the configuration file.
   * @return int 0 disables the mechanism
   */
  public static function getAutoLevelLimitThreshold() {
    global $ProjectSelectorAutoLimiteThreshold;
    if (! isset($ProjectSelectorAutoLimiteThreshold)) { return 500; }
    return (int) $ProjectSelectorAutoLimiteThreshold;
  }

  /** =========================================================================
   * Level setting as an int, 0 meaning no limit.
   */
  public static function normalizeSelectorLevel($value) {
    if ($value===null or $value==='' or $value=='0' or $value=='10') { return 0; }
    return (int) $value;
  }

  /** =========================================================================
   * Tightest of two levels, 0 being the loosest since it means no limit.
   */
  public static function strictestSelectorLevel($a, $b) {
    if (! $a) { return $b; }
    if (! $b) { return $a; }
    return ($a<$b) ? $a : $b;
  }

  /** =========================================================================
   * Level the threshold imposes, stored as the level setting so that the popup
   * and the toolbar show it. A level the user set himself wins when it is
   * tighter ; one this method set before is replaced.
   * @return int level to apply, 0 for none
   */
  public static function resolveAutoLevelLimit($model, $storedLevel) {
    $stored=self::normalizeSelectorLevel($storedLevel);
    $threshold=self::getAutoLevelLimitThreshold();
    if ($threshold<=0) { return $stored; }
    $auto=self::computeAutoLevelLimit($model, $threshold);
    $applied=Parameter::getUserParameter('projectSelectorAutoLimitApplied');
    $applied=($applied===null or $applied==='') ? -1 : (int) $applied;
    $level=($stored===$applied) ? $auto : self::strictestSelectorLevel($stored, $auto);
    if ($level!==$stored) {
      Parameter::storeUserParameter('projectSelectorLimitProjectLevel', ($level>0)?$level:'');
    }
    if ($auto!==$applied) {
      // Stored as a string : an integer 0 would be saved as null, and read back
      // as "never applied"
      Parameter::storeUserParameter('projectSelectorAutoLimitApplied', (string) $auto);
    }
    return $level;
  }

  /** =========================================================================
   * Resolves the auto level limit at connection time, while the session is
   * still writable : the main page closes it before the selector is built.
   */
  public static function applyAutoLevelLimitAtConnection() {
    if (self::getAutoLevelLimitThreshold()<=0) { return; }
    $limitToActiveProjects=true;
    if (sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1) {
      $limitToActiveProjects=false;
    }
    $model=self::getSelectorTree($limitToActiveProjects, true);
    self::resolveAutoLevelLimit($model, Parameter::getUserParameter('projectSelectorLimitProjectLevel'));
  }

  /** =========================================================================
   * Projects of a favorite list : either its stored items, or the result of the
   * filter it is based on.
   * @return array id => id
   */
  public static function getFavoriteProjectArray($idFavoriteProjectList) {
    $obj=new Project();
    $favoriteProjectArray=array();
      $favoriteProjectList = new FavoriteProjectList($idFavoriteProjectList);
      if($favoriteProjectList->idFilter){
        $filterCrit = new FilterCriteria();
        $filterCritList = $filterCrit->getSqlElementsFromCriteria(array('idFilter'=>$favoriteProjectList->idFilter));
        $needPlanningELement=false;
        foreach ($filterCritList as $criteria){
          if ($criteria->sqlOperator=='SORT') continue;
          if(pq_strpos($criteria->sqlAttribute, 'ProjectPlanningElement_') !== false){
            $needPlanningELement=true;
          }
        }
        $table = $obj->getDatabaseTableName();
        $query = " SELECT p.id FROM $table p ";
        if($needPlanningELement){
          $pe = new PlanningElement();
          $peTable = $pe->getDatabaseTableName();
          $query .= " JOIN $peTable pe ON pe.refType = 'Project' AND pe.refId = p.id ";
        }
        $query .= " WHERE 1=1 ";
        foreach ($filterCritList as $criteria){
          if ($criteria->sqlOperator=='SORT') continue;
          $operator = ($criteria->orOperator)?'OR':'AND';
          if ($criteria->sqlAttribute == 'indicatorFileNoteLink') {
            $aff = new Affectable(getSessionUser()->id, true);
            $idTeamCurrentUser = $aff->idTeam;
            $userId = getSessionUser()->id;
            $note = new Note();
            $noteTable = $note->getDatabaseTableName();
            $link = new Link();
            $linkTable = $link->getDatabaseTableName();
            $attachment = new Attachment();
            $attachmentTable = $attachment->getDatabaseTableName();
            $indicatorSubQuery = " CONCAT('#Note#',
                                   (SELECT COUNT(n.id) FROM $noteTable n WHERE n.refType = 'Project' AND n.refId = p.id
                                       AND (n.idPrivacy=1 OR (n.idPrivacy=2 AND n.idTeam=" . Sql::fmtId($idTeamCurrentUser) . ") OR (n.idPrivacy=3 AND n.idUser=" . Sql::fmtId($userId) . "))),
                                   '#Link#',
                                   (SELECT COUNT(l.id) FROM $linkTable l WHERE (l.ref1Type = 'Project' AND l.ref1Id = p.id
                                       OR l.ref2Type = 'Project' AND l.ref2Id = p.id)),
                                   '#Attach#',
                                   (SELECT COUNT(a.id) FROM $attachmentTable a WHERE a.refType = 'Project' AND a.refId = p.id
                                       AND (a.idPrivacy=1 OR (a.idPrivacy=2 AND a.idTeam=" . Sql::fmtId($idTeamCurrentUser) . ") OR (a.idPrivacy=3 AND a.idUser=" . Sql::fmtId($userId) . "))))";
            
            $query .= " $operator ($indicatorSubQuery) $criteria->sqlOperator $criteria->sqlValue";
          }else{
            $attribute = (pq_strpos($criteria->sqlAttribute, 'ProjectPlanningElement_') !== false)?pq_str_replace("ProjectPlanningElement_", 'pe.', $criteria->sqlAttribute):"p.".$criteria->sqlAttribute;
            $query .= " $operator $attribute $criteria->sqlOperator $criteria->sqlValue";
          }
        }
        $resultQuery=Sql::query($query);
        $favoriteProjectArray=array();
        while ($line = Sql::fetchLine($resultQuery)) {
          $favoriteProjectArray[$line['id']]=$line['id'];
        }
      }else{
        $favoriteProjectArray = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$idFavoriteProjectList), 'idProject');
      }
    return $favoriteProjectArray;
  }

  /** =========================================================================
   * Ids to display for a favorite selection : each favorite, its ancestors and its
   * descendants. When a level limit applies, only the favorites themselves are kept,
   * so that each one shows up as a root.
   * @return array id => 1, meant to be passed as $restrictToIds
   */
  public static function expandFavoriteSelection($model, $favoriteIds, $limitProjectLevel=false) {
    $childrenOf=array();
    foreach ($model as $id => $row) {
      $parent=$row['idProject'];
      if ($parent and isset($model[$parent])) { $childrenOf[$parent][]=$id; }
    }
    $keep=array();
    if ($limitProjectLevel) {
      // Level limited : keep the favorites only, and skip any favorite already
      // covered by the descendants of a previous one
      $covered=array();
      foreach ($favoriteIds as $favId) {
        if (! isset($model[$favId])) { continue; } // removed project, or out of rights
        if (isset($covered[$favId])) { continue; }
        $keep[$favId]=1;
        $covered[$favId]=1;
        $stack=array($favId);
        while (count($stack)>0) {
          $current=array_pop($stack);
          if (! isset($childrenOf[$current])) { continue; }
          foreach ($childrenOf[$current] as $child) {
            if (isset($covered[$child])) { continue; }
            $covered[$child]=1;
            $stack[]=$child;
          }
        }
      }
      return $keep;
    }
    foreach ($favoriteIds as $favId) {
      if (! isset($model[$favId])) { continue; } // removed project, or out of rights
      $keep[$favId]=1;
      // Ancestors, so the tree can be drawn down to the favorite
      $parent=$model[$favId]['idProject'];
      $guard=0;
      while ($parent and isset($model[$parent]) and $guard<1000) {
        $keep[$parent]=1;
        $parent=$model[$parent]['idProject'];
        $guard++;
      }
      // Descendants
      $stack=array($favId);
      while (count($stack)>0) {
        $current=array_pop($stack);
        if (! isset($childrenOf[$current])) { continue; }
        foreach ($childrenOf[$current] as $child) {
          if (isset($keep[$child])) { continue; }
          $keep[$child]=1;
          $stack[]=$child;
        }
      }
    }
    return $keep;
  }
  /** =========================================================================
   * Builds the project selector HTML from the flat model.
   * Nodes are nested : each one holds the table of its children inside its own <td>.
   * @param $limitProjectLevel int|false deepest level drawn, false for no limit
   * @return string
   */
  /** =========================================================================
   * Row model of the selector for the current session, with every option
   * applied : active projects, favorite list, handled filter, depth limit.
   * Memoized, so the page and the json endpoint share one computation.
   * @return array array('model'=>..., 'limitProjectLevel'=>...)
   */
  private static $_selectorModelForSession=null;
  public static function getSelectorModelForSession() {
    if (self::$_selectorModelForSession!==null) {
      return self::$_selectorModelForSession;
    }
    $limitToActiveProjects=true;
    if (sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1) {
      $limitToActiveProjects=false;
    }
    $limitProjectLevel=self::normalizeSelectorLevel(Parameter::getUserParameter('projectSelectorLimitProjectLevel'));
    $model=self::getSelectorTree($limitToActiveProjects, true);
    $idFavoriteProjectList=pq_trim(getSessionValue('idFavoriteProjectList'));

    if ($idFavoriteProjectList!='') {
      unsetSessionValue('visibleProjectsList');
      $favoriteProjectArray=self::getFavoriteProjectArray($idFavoriteProjectList);
      $keepFavorites=self::expandFavoriteSelection($model, $favoriteProjectArray, $limitProjectLevel);
      $model=self::getSelectorTree($limitToActiveProjects, true, $keepFavorites);
    }
    if (Parameter::getUserParameter('projectSelectorShowHandlelProject')) {
      $model=self::filterSelectorTreeOnHandled($model);
    }
    self::$_selectorModelForSession=array('model'=>$model, 'limitProjectLevel'=>$limitProjectLevel);
    return self::$_selectorModelForSession;
  }

  /** =========================================================================
   * Serializable payload for the client side selector view.
   * rows holds [id, name, level, reachable, handled] in display order,
   * checked holds the ids selected when the selector opens.
   * @param $limitProjectLevel int|false deepest level kept, false for no limit
   * @return array
   */
  public static function buildSelectorPayload($model, $limitProjectLevel=false) {
    $sessionProject=getSessionValue('project');
    $arrayProjSelected=(pq_strpos($sessionProject, ',') != null)?pq_explode(',', $sessionProject):null;
    $editFavoriteProject=pq_trim(getSessionValue('editFavoriteProject'));
    $favProjItemList=array();
    if ($editFavoriteProject != '') {
      $favProjItemList=SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$editFavoriteProject), 'idProject');
    }
    $rows=array();
    $checked=array();
    foreach ($model as $idPrj => $row) {
      if ($limitProjectLevel and $row['level'] > $limitProjectLevel) { continue; }
      $rows[]=array(
        $idPrj,
        $row['name'],
        $row['level'],
        ($row['reachable'])?1:0,
        ($row['handled'])?1:0
      );
      $isChecked=false;
      if ($arrayProjSelected!==null) {
        $isChecked=in_array($idPrj, $arrayProjSelected);
      } else if ($editFavoriteProject != '' and count($favProjItemList)>0) {
        $isChecked=in_array($idPrj, $favProjItemList);
      } else {
        $isChecked=($sessionProject==$idPrj);
      }
      if ($isChecked) { $checked[]=$idPrj; }
    }
    return array('rows'=>$rows, 'checked'=>$checked);
  }


  /** =========================================================================
   * Header of the project selector : all projects button, favorite pane, title
   * panes, and the opening tag of the scrolling container. Holds no project row.
   * @return string
   */
  public static function drawSelectorHeader($selectField='selectedProject') {
    global $outMode;
    $recursiveCall=false;
    $user=getSessionUser();
    $idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList'));
    $result="";
    $clickEvent=' onClick=""';
    if ($outMode=='html' or $outMode=='pdf') $clickEvent='';
    
    $selectedProject='*';
    if(sessionValueExists('project')){
      $selectedProject=getSessionValue('project');
    }
    $favProjItem = new FavoriteProjectItem();
    $favProjItemList = array();
    $editFavoriteProject = pq_trim(getSessionValue('editFavoriteProject'));
    if($editFavoriteProject != ''){
      $favProjItemList = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$editFavoriteProject), 'idProject');
      Parameter::storeUserParameter('favoriteProjectsArray', implode(',', $favProjItemList));
    }
    $favoriteProjectItemList = implode(',', $favProjItemList);
    
    if ($selectField!=null and ! $recursiveCall) { 
      $collapsedList=Collapsed::getCollaspedList();
      $isFavoriteListSelected = 0;
      $idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList'));
      if(pq_trim($idFavoriteProjectList) != ''){
        $isFavoriteListSelected=1;
      }
      $favoriteName = '';
      $validatedProjectSelection = ($selectedProject == '*')?'':$selectedProject;
      $displayAllProjectButton = ($selectedProject == '*')?'display:none;':'';
      $displayOKButton = 'display:none;';
      $displayFavoriteName = 'none';
      $displaySaveButton = 'display:none;';
      $displayNewSaveButton = 'display:none;';
      $displayEditButton = 'display:none;';
      $displayCancelButton = 'display:none;';
      $favoriteProjectItemList = '';
      if($editFavoriteProject != '' or $selectedProject != "*"){
        $displayFavoriteName='flex';
        $favoriteName = SqlList::getNameFromId('FavoriteProjectList', $editFavoriteProject, false);
      }
      if($idFavoriteProjectList != ''){
        setSessionValue('favoriteProjectListName', $favoriteName);
        $displaySaveButton = 'display:none;';
        $displayEditButton = '';
        $displayCancelButton = '';
      }else if($editFavoriteProject != ''){
        $displaySaveButton = '';
        $displayNewSaveButton = 'display:none;';
        $displayEditButton = 'display:none;';
        $displayCancelButton = '';
      }else if($selectedProject != "*"){
        $displayNewSaveButton = '';
      }
      $result .= '<table style="width:100%"><tr><td>';
      $result .= '<input type="hidden" id="projectSelectorValidatedSelection" value="'.htmlEncode($validatedProjectSelection).'" />';
      $allProject = ($idFavoriteProjectList != '')?i18n('favoriteProject'):i18n('allProjects');
      $clickEvent=' onClick=\'setSelectedProject("*", "<i>' . $allProject . '</i>", "' . $selectField . '");\' ';
      if ($outMode=='html' or $outMode=='pdf') $clickEvent='';
      $result .= '<div style="position: relative; display: flex; flex-direction: column; align-items: flex-start; gap: 2px;">';
      $result .= '  <div ' . $clickEvent . ' class="'.(($outMode=='html' or $outMode=='pdf')?'':'menuTree').'" style="width:100%;'.$displayAllProjectButton.'">';
      $result .= '    <div class="roundedVisibleButton roundedButton noRotate generalColClass generalColClassNotReadonly generalColClassNotRequired"';
      $result .= '      title="'.$allProject.'" style="display:inline-flex;align-items:center;width:95%;white-space:nowrap;height:25px;padding:0 5px;">';
      $result .= '     <div style="padding-right:2px">'.formatIconNewGui('Project', '16').'</div><div style="padding-left:2px">'.$allProject.'</div>';
      $result .= '    </div>';
      $result .= '  </div>';
      $result .= '  <div id="multiProjectSelectButtonDiv" class="'.(($outMode=='html' or $outMode=='pdf')?'':'menuTree').'" style="width:100%;'.$displayOKButton.'">';
      $result .= '    <div id="multiProjectSelectButton" class="roundedVisibleButton roundedButton noRotate generalColClass generalColClassNotReadonly generalColClassNotRequired" onClick="selectedMultiProject();"';
      $result .= '      title="'.i18n('multiProjectSelectHelp').'" style="display:inline-flex;align-items:center;width:95%;white-space:nowrap;height:25px;padding:0 5px;">';
      $result .= '     <div style="padding-right:2px">'.formatIconNewGui('Check','16').'</div><div style="padding-left:2px">'.i18n('validateProjectSelect').'<span id="multiProjectSelectCount"></span></div>';
      $result .=     '</div>';
      $result .= '  </div>';
      if($idFavoriteProjectList != '' or $editFavoriteProject != ''){
        $result .= '  <div id="resetProjectListButtonDiv" class="'.(($outMode=='html' or $outMode=='pdf')?'':'menuTree').'" style="width:100%;">';
        $result .= '    <div id="resetProjectListButton" class="roundedVisibleButton roundedButton noRotate generalColClass generalColClassNotReadonly generalColClassNotRequired" onClick="selectFavoriteProjectList(\'\', \'\', false, false, true);"';
        $result .= '      title="'.i18n('resetFavoriteList').'" style="display:inline-flex;align-items:center;width:95%;white-space:nowrap;height:25px;padding:0 5px;">';
        $result .= '     <div style="padding-right:2px">'.formatIconNewGui('Cancel', '16').'</div><div style="padding-left:2px">'.i18n('backToAllProject').'</div>';
        $result .=     '</div>';
        $result .= '  </div>';
      }
      $result .= '</div>';
      $result .= '</td></tr></table>';
      $result .= '<div dojoType="dijit.TitlePane" id="projectSelectorFavoriteTitlePane" open="'.( pq_array_key_exists("projectSelectorFavoriteTitlePane", $collapsedList)?'false':'true').'"';
      $result .= 'onHide="saveCollapsed(\'projectSelectorFavoriteTitlePane\');resizeTitlePanProjectSelector(false, '.count($favProjItemList).');" onShow="saveExpanded(\'projectSelectorFavoriteTitlePane\');resizeTitlePanProjectSelector(true, '.count($favProjItemList).');" title="'.i18n('Favorite').'" style="width:100%;padding-bottom:5px;">';
      $result .= '<form dojoType="dijit.form.Form" id="favoriteProjectListForm" name="favoriteProjectListForm" onSubmit="return false;">';
      $result .= '  <input type="hidden" id="isFavoriteListSelected" name="isFavoriteListSelected" value="'.$isFavoriteListSelected.'"/>';
      $result .= '  <div style="position: relative; display: flex; align-items: baseline;padding-right:5px;">';
      $result .= '    <div id="favoriteNameListDiv" style="position: relative; width: 90%;">';
      $result .= '      <input type="text" id="favoriteProjectListName" name="favoriteProjectListName" placeholder="'.i18n('colFavoriteProjectName').'" value="'.htmlEncode($favoriteName).'"';
      $result .= '        style="width: 90%; border: 1px solid var(--color-medium); border-radius: 5px; margin-bottom: 15px; padding: 5px; display: '.$displayFavoriteName.'; align-items: center;" class="input required" />';
      $result .= '    </div>';
      $result .= '    <div id="saveFavoriteListButtonDiv" style="z-index:999;padding:5px;background:var(--color-background);'.$displaySaveButton.'">';
      $result .= '      <a id="saveFavoriteListButton" onClick="changedSelectedProjectToFavorite(true);" title="'.i18n('saveFavoriteProjectList').'">';
      $result .=          formatSmallButton('Save');
      $result .= '      </a>';
      $result .= '    </div>';
      $result .= '    <div id="saveNewFavoriteListButtonDiv" style="z-index:999;padding:5px;background:var(--color-background);'.$displayNewSaveButton.'">';
      $result .= '      <a id="saveNewFavoriteListButton" onClick="changedSelectedProjectToFavorite(true);" title="'.i18n('transformFavoriteProjectList').'">';
      $result .=          formatSmallButton('Favoris', true);
      $result .= '      </a>';
      $result .= '    </div>';
      if($editFavoriteProject != '' ){
        $result .= '    <div id="resetFavoriteListButtonDiv" style="z-index:999;padding:5px;background:var(--color-background);'.$displayCancelButton.'">';
        $result .= '      <a id="resetFavoriteListButton" onClick="selectFavoriteProjectList(\'\', \''.$editFavoriteProject.'\', false, false, true);" title="'.i18n('resetFavoriteList').'">';
        $result .=          formatSmallButton('Cancel');
        $result .= '      </a>';
        $result .= '    </div>';
      }
      $result .= '  </div>';
      $result .= '</form>';
      
      $result .= '  <div id="favoriteListDiv" style="max-height:140px;overflow-y:auto;">';
      $result .= '  <div id="favoriteListContentPane" name="favoriteListContentPane" dojoType="dijit.layout.ContentPane" region="center"></div>';
      $result .= '  <table width="100%">';
      
      $fav=new FavoriteProjectList();
      $crit=array('idUser'=> $user->id);
      $orderByFilter = "name ASC";
      $favoriteList=$fav->getSqlElementsFromCriteria($crit,false,null,$orderByFilter);
      $favoriteProjFlatList = implode(',', SqlList::getListWithCrit('FavoriteProjectList', array('idUser'=>$user->id), 'id'));
      $fontSize = (!isNewGui())?'font-size:8pt;':'';
      foreach ($favoriteList as $favoriteProject){
        if($favoriteProject->idFilter){
          $filterCrit = new FilterCriteria();
          $filterCritList = $filterCrit->getSqlElementsFromCriteria(array('idFilter'=>$favoriteProject->idFilter));
          $needPlanningELement=false;
          foreach ($filterCritList as $criteria){
            if ($criteria->sqlOperator=='SORT') continue;
            if(pq_strpos($criteria->sqlAttribute, 'ProjectPlanningElement_') !== false){
              $needPlanningELement=true;
            }
          }
          $tableObjPrj = new Project(); $table = $tableObjPrj->getDatabaseTableName();
          $query = " SELECT p.id FROM $table p ";
          if($needPlanningELement){
            $pe = new PlanningElement();
            $peTable = $pe->getDatabaseTableName();
            $query .= " JOIN $peTable pe ON pe.refType = 'Project' AND pe.refId = p.id ";
          }
          $query .= " WHERE 1=1 ";
          foreach ($filterCritList as $criteria){
            if ($criteria->sqlOperator=='SORT') continue;
            $operator = ($criteria->orOperator)?'OR':'AND';
            if ($criteria->sqlAttribute == 'indicatorFileNoteLink') {
              $aff = new Affectable(getSessionUser()->id, true);
              $idTeamCurrentUser = $aff->idTeam;
              $userId = getSessionUser()->id;
              $note = new Note();
              $noteTable = $note->getDatabaseTableName();
              $link = new Link();
              $linkTable = $link->getDatabaseTableName();
              $attachment = new Attachment();
              $attachmentTable = $attachment->getDatabaseTableName();
              $indicatorSubQuery = " CONCAT('#Note#',
                                   (SELECT COUNT(n.id) FROM $noteTable n WHERE n.refType = 'Project' AND n.refId = p.id
                                       AND (n.idPrivacy=1 OR (n.idPrivacy=2 AND n.idTeam=" . Sql::fmtId($idTeamCurrentUser) . ") OR (n.idPrivacy=3 AND n.idUser=" . Sql::fmtId($userId) . "))),
                                   '#Link#',
                                   (SELECT COUNT(l.id) FROM $linkTable l WHERE (l.ref1Type = 'Project' AND l.ref1Id = p.id
                                       OR l.ref2Type = 'Project' AND l.ref2Id = p.id)),
                                   '#Attach#',
                                   (SELECT COUNT(a.id) FROM $attachmentTable a WHERE a.refType = 'Project' AND a.refId = p.id
                                       AND (a.idPrivacy=1 OR (a.idPrivacy=2 AND a.idTeam=" . Sql::fmtId($idTeamCurrentUser) . ") OR (a.idPrivacy=3 AND a.idUser=" . Sql::fmtId($userId) . "))))";
              
              $query .= " $operator ($indicatorSubQuery) $criteria->sqlOperator $criteria->sqlValue";
            }else{
              $attribute = (pq_strpos($criteria->sqlAttribute, 'ProjectPlanningElement_') !== false)?pq_str_replace("ProjectPlanningElement_", 'pe.', $criteria->sqlAttribute):"p.".$criteria->sqlAttribute;
              $query .= " $operator $attribute $criteria->sqlOperator $criteria->sqlValue";
            }
          }
          $resultQuery=Sql::query($query);
          $favoriteProjectItemList=array();
          while ($line = Sql::fetchLine($resultQuery)) {
            $favoriteProjectItemList[$line['id']]=$line['id'];
          }
        }else{
          $favoriteProjectItemList = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$favoriteProject->id), 'idProject');
        }
        $favoriteProjectItemList = implode(',', $favoriteProjectItemList);
        $selectedBackgroundColor = ($favoriteProject->id == $idFavoriteProjectList)?'favoriteProjectListSelected':'';
        $isFilter = ($favoriteProject->idFilter)?true:false;
        $result .= '<tr class="ganttTaskrow" id="favoriteList'.$favoriteProject->id.'">';
        $result .= '<input type="hidden" id="favoriteProjectList_'.$favoriteProject->id.'" name="favoriteProjectList_'.$favoriteProject->id.'" value="'.$favoriteProjectItemList.'" />';
        $result .= '  <td style="cursor:pointer;'.$fontSize.'font-style:italic;padding:5px;height: 18px;"';
        $result .= '    class="filterData '.$selectedBackgroundColor.'" onClick="selectFavoriteProjectList(\''.$favoriteProjectItemList.'\', \''.$favoriteProject->id.'\', false, true, true);" title="'.i18n("selectStoredFavorite").'">';
        $result .= '     <span id="favoriteProjectName_'.$favoriteProject->id.'" style="position:relative;top:2px;margin:3px">'.htmlEncode($favoriteProject->name).'</span></td>';
        $result .= '  </td>';
        $result .= '  <td class="filterData" width="16px" align="center" style="height: 16px;">';
        if($isFilter){
          $result .= '     <a onClick="showFilterDialog('.htmlEncode($favoriteProject->idFilter).')" title="'.i18n('editStoredFavorite').'">';
          $result .=         formatSmallButton('Filter', true);
          $result .= '     </a>';
        }else{
          $result .= '     <a onClick="selectFavoriteProjectList(\''.$favoriteProjectItemList.'\', \''.$favoriteProject->id.'\', true)" title="'.i18n('editStoredFavorite').'">';
          $result .=         formatSmallButton('Edit');
          $result .= '     </a>';
        }
        $result .= '  </td>';
        $result .= '  <td class="filterData" width="16px" align="center" style="height: 16px;">';
        $result .= '    <a src="css/images/smallButtonRemove.png" onClick="confirmRemoveFavoriteProjectList(\''.htmlEncode($favoriteProject->id).'\', \''.htmlEncode($favoriteProject->name).'\', '.htmlEncode($favoriteProject->idFilter).')" title="'.i18n('removeStoredFavorite').'">';
        $result .=        formatSmallButton('Remove');
        $result .= '    </a>';
        $result .= '  </td>';
        $result .= '</tr>'; 
      }
      $result .= '</table></div>';
      $result .= '</div>';
      $result .= '<div dojoType="dijit.TitlePane" id="projectSelectorProjectTitlePane" open="'.( pq_array_key_exists("projectSelectorProjectTitlePane", $collapsedList)?'false':'true').'"';
      $result .= 'onHide="saveCollapsed(\'projectSelectorProjectTitlePane\');" onShow="saveExpanded(\'projectSelectorProjectTitlePane\');dijit.byId(\'projectSelectorProjectTitlePane\').resize();" title="'.i18n('tabProjects').'" style="width:100%;padding-bottom:5px;">';
      $heightSelectorList=getSessionValue('screenHeight')-400;
      $projTitlePanMaxHeight = (pq_array_key_exists("projectSelectorFavoriteTitlePane", $collapsedList))?'max-height:'.$heightSelectorList.'px;':'';
      $result .= '<div id="projectTitlePaneDiv" style="overflow-x:hidden;overflow-y:auto;'.$projTitlePanMaxHeight.'">';
    }
    return $result;
  }
  /** =========================================================================
   * Specific function to draw a recursive tree for subprojects
   * @return string the html table for the given level of subprojects
   *  must be redefined in the inherited class
   */
  public function drawSubProjects($selectField=null, $recursiveCall=false, $limitToUserProjects=false, $limitToActiveProjects=false, $level=0,$limitProjectLevel=false, $noVAlignTop=false) {
    scriptLog("Project($this->id)->drawSubProjects(selectField=$selectField, recursiveCall=$recursiveCall, limitToUserProjects=$limitToUserProjects, limitToActiveProjects=$limitToActiveProjects)");
    global $outMode, $drawCheckBox, $displayWidth;
  	self::$_drawSubProjectsDone[$this->id]=$this->name;
    if ($limitToUserProjects) {
      $user=getSessionUser();
      if (! $user->_accessControlVisibility) {
        $user->getAccessControlRights(); // Force setup of accessControlVisibility
      }
      if ($user->_accessControlVisibility != 'ALL') {      
        $visibleProjectsList=$user->getHierarchicalViewOfVisibleProjects($limitToActiveProjects);
      } else {
      	$visibleProjectsList=array();
      }
      $reachableProjectsList=$user->getVisibleProjects($limitToActiveProjects);
    } else {  
      $visibleProjectsList=array();
      $reachableProjectsList=array();
    }
    $result="";
    $clickEvent=' onClick=""';
    if ($outMode=='html' or $outMode=='pdf') $clickEvent='';
    $idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList')); 
    if (! $idFavoriteProjectList and $limitToUserProjects and $user->_accessControlVisibility != 'ALL' and ! $recursiveCall) {
      $subList=array();
    	foreach($visibleProjectsList as $idP=>$nameP) {
    		$split=pq_explode('#',$nameP);
    		if (pq_strpos($split[0],'.')==0) {
    		    $proj = new Project(pq_substr($idP,1));
      	        $subList[pq_substr($idP,1)]=$proj->name;
    		}
    	}
    } else if ($idFavoriteProjectList!='') {
      unsetSessionValue('visibleProjectsList');
      $topList=array();
      $favoriteProjectList = new FavoriteProjectList($idFavoriteProjectList);
      if($favoriteProjectList->idFilter){
        $filterCrit = new FilterCriteria();
        $filterCritList = $filterCrit->getSqlElementsFromCriteria(array('idFilter'=>$favoriteProjectList->idFilter));
        $needPlanningELement=false;
        foreach ($filterCritList as $criteria){
          if ($criteria->sqlOperator=='SORT') continue;
          if(pq_strpos($criteria->sqlAttribute, 'ProjectPlanningElement_') !== false){
            $needPlanningELement=true;
          }
        }
        $table = $this->getDatabaseTableName();
        $query = " SELECT p.id FROM $table p ";
        if($needPlanningELement){
          $pe = new PlanningElement();
          $peTable = $pe->getDatabaseTableName();
          $query .= " JOIN $peTable pe ON pe.refType = 'Project' AND pe.refId = p.id ";
        }
        $query .= " WHERE 1=1 ";
        foreach ($filterCritList as $criteria){
          if ($criteria->sqlOperator=='SORT') continue;
          $operator = ($criteria->orOperator)?'OR':'AND';
          if ($criteria->sqlAttribute == 'indicatorFileNoteLink') {
            $aff = new Affectable(getSessionUser()->id, true);
            $idTeamCurrentUser = $aff->idTeam;
            $userId = getSessionUser()->id;
            $note = new Note();
            $noteTable = $note->getDatabaseTableName();
            $link = new Link();
            $linkTable = $link->getDatabaseTableName();
            $attachment = new Attachment();
            $attachmentTable = $attachment->getDatabaseTableName();
            $indicatorSubQuery = " CONCAT('#Note#',
                                   (SELECT COUNT(n.id) FROM $noteTable n WHERE n.refType = 'Project' AND n.refId = p.id
                                       AND (n.idPrivacy=1 OR (n.idPrivacy=2 AND n.idTeam=" . Sql::fmtId($idTeamCurrentUser) . ") OR (n.idPrivacy=3 AND n.idUser=" . Sql::fmtId($userId) . "))),
                                   '#Link#',
                                   (SELECT COUNT(l.id) FROM $linkTable l WHERE (l.ref1Type = 'Project' AND l.ref1Id = p.id
                                       OR l.ref2Type = 'Project' AND l.ref2Id = p.id)),
                                   '#Attach#',
                                   (SELECT COUNT(a.id) FROM $attachmentTable a WHERE a.refType = 'Project' AND a.refId = p.id
                                       AND (a.idPrivacy=1 OR (a.idPrivacy=2 AND a.idTeam=" . Sql::fmtId($idTeamCurrentUser) . ") OR (a.idPrivacy=3 AND a.idUser=" . Sql::fmtId($userId) . "))))";
            
            $query .= " $operator ($indicatorSubQuery) $criteria->sqlOperator $criteria->sqlValue";
          }else{
            $attribute = (pq_strpos($criteria->sqlAttribute, 'ProjectPlanningElement_') !== false)?pq_str_replace("ProjectPlanningElement_", 'pe.', $criteria->sqlAttribute):"p.".$criteria->sqlAttribute;
            $query .= " $operator $attribute $criteria->sqlOperator $criteria->sqlValue";
          }
        }
        $resultQuery=Sql::query($query);
        $favoriteProjectArray=array();
        while ($line = Sql::fetchLine($resultQuery)) {
          $favoriteProjectArray[$line['id']]=$line['id'];
        }
      }else{
        $favoriteProjectArray = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$idFavoriteProjectList), 'idProject');
      }
      $subPrjLimited=array();
      foreach ($favoriteProjectArray as $id){
        $prj = new Project($id,true);
        if (!$prj->id) continue; // Favorite project was removed
        $topPrjList = $prj->getTopProjectList(true);
        if ($limitProjectLevel and ! $recursiveCall) {
          if (isset($subPrjLimited[$id])) continue;
          $topList[]=$id;
          $subPrjLimited=array_merge_preserve_keys($subPrjLimited,$prj->getRecursiveSubProjectsFlatList($limitToActiveProjects,true));
        }else if($topPrjList){
          $topList = array_merge($topList, $topPrjList);
        }
        $subLst=$prj->getRecursiveSubProjectsFlatList($limitToActiveProjects,true);
        if ($subLst and ! $limitProjectLevel) $topList=array_merge($topList, array_keys($subLst));
      }
      unset($subPrjLimited);
      $topList = array_flip($topList);
      //$subList=$this->getSubProjectsList($limitToActiveProjects,true);
      $subList=$this->getRecursiveSubProjectsFlatList($limitToActiveProjects,true);
      foreach ($subList as $idPrj=>$namePrj){
        if(!pq_array_key_exists($idPrj, $topList))unset($subList[$idPrj]);
      }
    } else {
  	  $subList=$this->getSubProjectsList($limitToActiveProjects,true);
  	  //$subList=$this->getRecursiveSubProjectsFlatList($limitToActiveProjects,true);
    }
    
    $selectedProject='*';
    if(sessionValueExists('project')){
      $selectedProject=getSessionValue('project');
    }
    $favProjItem = new FavoriteProjectItem();
    $favProjItemList = array();
    $editFavoriteProject = pq_trim(getSessionValue('editFavoriteProject'));
    if($editFavoriteProject != ''){
      $favProjItemList = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$editFavoriteProject), 'idProject');
      Parameter::storeUserParameter('favoriteProjectsArray', implode(',', $favProjItemList));
    }
    $favoriteProjectItemList = implode(',', $favProjItemList);
    
    if(isNewGui()){
      $result .= '<table style="width:100%;margin-top:15px;" class="smoothResize">';
    }else{
      $result .='<table style="width:100%;">';
    }
    $handled = 0;
    if (count($subList)>0) {
      $level++;
      $showHandlelProject=Parameter::getUserParameter('projectSelectorShowHandlelProject');
      foreach ($subList as $idPrj=>$namePrj) {
        if($showHandlelProject){
          $subProj = new Project($idPrj);
          if($subProj->handled == '1' and $subProj->done == '0'){
          	$handled = 1;
          }else{
          	$checkList = $subProj->getRecursiveSubProjectsFlatList($limitToActiveProjects);
          	if(count($checkList)>0){
          		foreach ($checkList as $idSubPrj=>$nameSubPrj){
          			$obj = new Project($idSubPrj);
          			if($obj->handled == '1' and $obj->done == '0'){
          				$handled = 1;
          			}
          		}
          	}
          }
          if($handled == 0){
          	continue;
          }
          $handled = 0;
        }
        $showLine=true;
        $reachLine=true;
        if (pq_array_key_exists($idPrj,self::$_drawSubProjectsDone)) {
        	$showLine=false;
        }
        if ($limitToUserProjects) {
          if ($user->_accessControlVisibility != 'ALL') {
            if (! pq_array_key_exists('#' . $idPrj,$visibleProjectsList)) {
              $showLine=false;
            }
            if (! pq_array_key_exists($idPrj,$reachableProjectsList)) {
              $reachLine=false;
            }
          }  
        }
        $zindex=1;
        if ($showLine) {
          $checked = '';
          if(pq_strpos(getSessionValue('project'), ',') != null){
            $arrayProj = pq_explode(',', getSessionValue('project'));
            if(in_array($idPrj, $arrayProj))$checked='checked';
          }else if($editFavoriteProject != '' and count($favProjItemList)>0 and in_array($idPrj, $favProjItemList)){
            $checked='checked';
          }else{
            if (getSessionValue('project')==$idPrj) $checked='checked';
            else $checked='';
          }
        	$prj=new Project($idPrj,true);
        	$left = 0;
        	if($level > 1){
        	  $left = -(20*$level);
        	  if($level >= 2){
        	  	$left -= ($level-2)*20;
        	  }
        	}
          $result .='<tr id="forSearchBar" style="height:25px">';
          if(!$drawCheckBox){
            $result .='<td valign="top" width="20px">';
            $result .='<div dojoType="dijit.form.CheckBox" type="checkbox" class="projectSelectorCheckbox" onchange="checkProjectToSelect();"';
            $result .= 'style="float:left;position:relative;left:'.$left.'px" id="checkBoxProj'.$idPrj.'" value="'.$idPrj.'" '.$checked.'>';
            $result .='</div>';
            $result .='<input type="hidden" id="projectSelectorName'.$idPrj.'" name="projectSelectorName'.$idPrj.'" value="'.htmlEncode($prj->name).'"></td>';
          }
          if(!isNewGui()){
            $result .='<td valign="top" width="20px"><img src="css/images/iconList16.png" height="16px" /></td>';
          }else{
            $styleMargin = "margin-right:5px;margin-top:3px;";
            if(!$drawCheckBox){
              $styleMargin = "";
            }
            if ($outMode!='pdf') $result .='<td valign="top" width="20px"><div style="'.$styleMargin.'" class="imageColorNewGuiNoSelection iconProject iconSize16"></div></td>';
            else $result .='<td valign="top" width="20px"><img src="../view/css/images/iconList16.png" style="width:16pxheight:16px" />&nbsp;</td>';
          }
          $displayFavoriteChecked = 'display:none';
          if(count($favProjItemList)>0 and in_array($idPrj, $favProjItemList)){
          	$mode='remove';
          	$color = 'color:var(--color-secondary);';
          	$class="menu__as__Fav";
          	//$displayFavoriteChecked = '';
          }else{
            $color = 'color:black;';
          	$mode='add';
          	$class="menu__add__Fav";
          }
          $isFavoriteSelected = ($idFavoriteProjectList != '')?1:0;
          $mouseover = "";
          $mouseout = "";
//           if(!$idFavoriteProjectList){
//             $mouseover = "highlightFavoriteProject($idPrj, 'mouseover');";
//             $mouseout = "highlightFavoriteProject($idPrj, 'mouseout');";
//           }
          if ($selectField==null) {
            if ($noVAlignTop) $result .= '<td class="classLinkName '.(($outMode=='html' or $outMode=='pdf')?'':'display').'"  NOWRAP><div style="float:left;width:'.(intval($displayWidth)-250).'px">' . (($outMode=='html' or $outMode=='pdf')?htmlEncode($prj->name):htmlDrawLink($prj)).'</div>';
            else $result .= '<td valign="top" class="classLinkName '.(($outMode=='html' or $outMode=='pdf')?'':'display').'"  NOWRAP><div style="float:left;width:'.(intval($displayWidth)-250).'px">' . (($outMode=='html' or $outMode=='pdf')?htmlEncode($prj->name):htmlDrawLink($prj)).'</div>'; 
            
            $objStatus=new Status($prj->idStatus);
            $result .=  '<div class="colorNameData" style="float:right;width:150px;height:20px;">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</div>';
          }
          if(! ($limitProjectLevel and $limitProjectLevel==($level)) ) {
            $result .= $prj->drawSubProjects($selectField,true,$limitToUserProjects,$limitToActiveProjects, $level,$limitProjectLevel,true);
          }
          $result .= '</td>';
          $result .= '</tr>';
          $zindex++;
        }
      }
    }
    $result .='</table>';
    return $result;
  }

  public function drawProjectsList($critArray) {
//scriptLog("Project($this->id)->drawProjectsList(implode('|',$critArray))");  	
    $result="<table>";
    $prjList=$this->getSqlElementsFromCriteria($critArray, false);
    foreach ($prjList as $prj) {
// MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
        // For the Leave Project, if it's not visible by connected user ==> not taken into account
        if (self::isTheLeaveProject($prj->id) && !self::isProjectLeaveVisible()) {continue;}
    }
// MTY - LEAVE SYSTEM        
      $result.= '<tr><td valign="top" width="20px"><img src="css/images/iconList16.png" height="16px" /></td><td>';
      $result.=htmlDrawLink($prj);
      $result.= '</td></tr>';
    }
    $result .="</table>";
    return $result; 
  }
  
   /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save() {
    // #305 : need to recalculate before dispatching to PE
    $old=$this->getOld();
    $this->recalculateCheckboxes();
    if (!$this->id) {
      //$this->isUnderConstruction=1; // Will post this later...
    }
    if(SqlList::getFieldFromId("Status", $this->idStatus, "setHandledStatus")!=0) {
      $this->isUnderConstruction=0;
    }
    //$old=$this->getOld();
    //$oldtype=new ProjectType($old->idProjectType);
    $type=new ProjectType($this->idProjectType);
    
    if (! $this->idProject and $this->inheritedCurrency==1) {
      $this->inheritedCurrency=0;
    } else if ($this->idProject and ! $this->localCurrency) {
      $top=new Project($this->idProject,true);
      if ($top->localCurrency) {
        $this->localCurrency=$top->localCurrency;
        $this->localCurrencyPosition=$top->localCurrencyPosition;
        $this->localToGlobalConversion=$top->localToGlobalConversion;
        $this->globalToLocalConversion=$top->globalToLocalConversion;
      }
    }
      
    $noMoreAdministrative=false;
    if ($this->codeType=='ADM' and $type->code!='ADM') {
    	$noMoreAdministrative=true;
    }
    $this->codeType=$type->code;
    if($this->codeType=="PRP"){
      $this->isUnderConstruction=1;
    }
    $this->ProjectPlanningElement->refName=$this->name;
    $this->ProjectPlanningElement->idProject=$this->id;
    $this->ProjectPlanningElement->idle=$this->idle;
    $this->ProjectPlanningElement->done=$this->done;
    $this->ProjectPlanningElement->cancelled=$this->cancelled;
    if ($this->idProject and pq_trim($this->idProject)!='') {
      $this->ProjectPlanningElement->topRefType='Project';
      $this->ProjectPlanningElement->topRefId=$this->idProject;
      $this->ProjectPlanningElement->topId=null;
    } else {
      $this->ProjectPlanningElement->topId=null;
      $this->ProjectPlanningElement->topRefType=null;
      $this->ProjectPlanningElement->topRefId=null;
    }
    if (pq_trim($this->idProject)!=pq_trim($old->idProject) and !$this->isLeaveMngProject) {   
      $this->ProjectPlanningElement->wbs=null;
      $this->ProjectPlanningElement->wbsSortable=null;
      $this->sortOrder=null;
    } else if (! $this->sortOrder and $this->ProjectPlanningElement->wbsSortable) {
      $this->sortOrder=$this->ProjectPlanningElement->wbsSortable;
    }
    $this->ProjectPlanningElement->color=$this->color;
    
    // Organization
    if ( (!$this->id or $this->idProject!=$old->idProject) and ! pq_trim($this->idOrganization) and $this->idProject ) {
      $topProj=new Project($this->idProject,true);
      $this->idOrganization=$topProj->idOrganization;
    }
    $subProj=$this->getSubProjectsList(false);
    $this->organizationElementary=(count($subProj)==0)?0:1;
    $this->ProjectPlanningElement->idOrganization=$this->idOrganization;
    $this->ProjectPlanningElement->organizationInherited=$this->organizationInherited;
    $this->ProjectPlanningElement->organizationElementary=$this->organizationElementary;
    
    if($this->id){
      if($this->idStatus!=$old->idStatus){
        $newStatusPaused=SqlList::getFieldFromId("Status", $this->idStatus, "setPausedStatus")!=0;
        $oldStatusPaused=SqlList::getFieldFromId("Status", $old->idStatus, "setPausedStatus")!=0;
        if($newStatusPaused and !$oldStatusPaused and $this->paused==0){
          $this->paused=1;
          $this->fixPlanning=1;
        }else if(!$newStatusPaused and $oldStatusPaused and $this->paused==1){
          $this->paused=0;
          $this->fixPlanning=0;
        }
      }
      
      if($this->paused==1 and $this->paused!=$old->paused){
// PBER #10578
//         $this->ProjectPlanningElement->plannedStartDate=null;
//         $this->ProjectPlanningElement->plannedEndDate=null;
        $this->ProjectPlanningElement->paused=1;
      }else if ($this->paused==0 and $this->paused!=$old->paused ){
        $this->ProjectPlanningElement->paused=0;
      }
    }
    if ($this->fixPlanning!=$this->ProjectPlanningElement->fixPlanning) $this->ProjectPlanningElement->fixPlanning=$this->fixPlanning;
    
    if ( (!$this->id or $this->idProject!=$old->idProject) and $this->idProject and !$this->idCatalogUO) {
      $top=new Project($this->idProject,true);
      if ($top->idCatalogUO) {
        $this->idCatalogUO=$top->idCatalogUO;
      }
    }
    if(Module::isModuleActive("moduleGestionCA") and $this->idCatalogUO!=$old->idCatalogUO){
     $this->setRecursiveSubProjectCatalog($this->idCatalogUO, $old->idCatalogUO);
    }
    
    if ( (!$this->id or $this->idProject!=$old->idProject) and $this->idProject and !$this->idCalendarDefinition) {
      $top=new Project($this->idProject,true);
      if ($top->idCalendarDefinition) {
        $this->idCalendarDefinition=$top->idCalendarDefinition;
      }
    }
    if($this->idCalendarDefinition!=$old->idCalendarDefinition){
      $calDef = new CalendarDefinition($this->idCalendarDefinition);
      $this->setRecursiveSubProjectCalendarDefinition($this->idCalendarDefinition, $old->idCalendarDefinition);
    }
    // SAVE
    $result = parent::save();
    if (! pq_strpos($result,'id="lastOperationStatus" value="OK"')) {
      return $result;     
    } 
    if($this->isLeaveMngProject){
      setSessionValue('leaveProjectId', $this->id);
      setSessionValue('leaveProject', $this);
    }
    if (! $old->id or $this->idle!=$old->idle or $this->idProject!=$old->idProject) {
    	if ($old->idProject) {
        User::resetAllVisibleProjects($this->id, null);
    	} else {
    		User::resetAllVisibleProjects(null, null);
    	}
    }
    
    if(!$this->isCopyInProgress()){
    //gautier #2577
      if (Parameter::getGlobalParameter('allocateResponsibleToProject')=="YES") {
          $crit=array('idProject'=>$this->id, 'idResource'=>$this->idResource);
          $aff=new Affectation();
          $affLst=$aff->getSqlElementsFromCriteria($crit, false);
          if(count($affLst) == 0 ){
            if($this->idResource != null){
              $affManag=new Affectation();
              $affManag->idProject=$this->id;
              $affManag->idResource=$this->idResource;
              $affManag->save();
            }
          }
      }
    } 
    // Dispatch Organization 
    if ($this->idOrganization) {
      $this->dispatchOrganizationToSubProjects($old->idOrganization);
    }
    
    if ($this->idle) {
      $crit=array('idProject'=>$this->id, 'idle'=>'0');
      $vp=new VersionProject();
      $vpLst=$vp->getSqlElementsFromCriteria($crit, false);
      foreach ($vpLst as $vp) {
        $vp->idle=$this->idle;
        $vp->save();
      }
    }
    // Create affectation for Manager.
    if ($this->idUser and !$old->id and $this->idUser==getCurrentUserId()) {
      if (securityGetAccessRight('menuProject', 'update', null)!="ALL"){
        $id=($this->id)?$this->id:Sql::$lastQueryNewid;
        $crit=array('idProject'=>$id, 'idResource'=>$this->idUser);
        $aff=SqlElement::getSingleSqlElementFromCriteria('Affectation', $crit);
        if ( ! $aff or ! $aff->id) {
        	$aff=new Affectation();
        	$aff->_automaticCreation=true;
        	$aff->idResource=$this->idUser;
        	$aff->idProject=$id;
        	$profile=getSessionUser()->idProfile;
        	if (self::$_copyProjectId) {
        	  $cpPrf=getSessionUser()->getProfile(self::$_copyProjectId);
        	  if ($cpPrf) $profile=$cpPrf;
        	  self::$_copyProjectId=null;
        	}
        	$aff->idProfile=$profile;
        	$resAff=$aff->save();
        	User::resetAllVisibleProjects(null, null);
        	if (securityGetAccessRightYesNo('menuProject', 'update', $this, getSessionUser()) != "YES") {
        	  $crit=array('idProject'=>$this->idProject, 'idResource'=>$this->idUser);
        	  $affTop=SqlElement::getSingleSqlElementFromCriteria('Affectation', $crit);
        	  $aff->idProfile=$affTop->idProfile;
        	  $resAff=$aff->save();
        	  User::resetAllVisibleProjects(null, null);
        	}       	
        } else if (! $this->idle and $aff->idle) {
          $aff->_automaticCreation=true;
        	$aff->idle=0;
        	$resAff=$aff->save();
        }
      }
    }

    if ($this->idle) {
      Affectation::updateIdle($this->id, null);
    }
    if ($noMoreAdministrative) {
    	 $ass=new Assignment();
    	 $lstAss=$ass->getSqlElementsFromCriteria(array('idProject'=>$this->id));
    	 foreach ($lstAss as $ass) {
    	 	 if ($ass->realWork==0 and $ass->leftWork==0) {
    	 	 	 $ass->delete();
    	 	 }
    	 }
    }
    //gautier #2486
    if(($this->idle)==1){
      $plw=new PlannedWork();
      $clause=('idProject ='.$this->id);
      $purg=$plw->purge($clause);
    }
    //damian
    if($this->fixPerimeter != $old->fixPerimeter){
    	$listProjPerim = $this->getRecursiveSubProjectsFlatList();
    	foreach ($listProjPerim as $id=>$name){
    		$subProj = new Project($id);
    		if($this->id == $subProj->idProject){
    		  $subProj->fixPerimeter = $this->fixPerimeter;
    		}
    		$subProj->save();
    	}
    }
    // MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
    	if ($old->isLeaveMngProject==0 && $this->isLeaveMngProject==1) {
    		$this->setLeaveProjectId();
    		$this->setLeaveProject();
    	}
    }
    // MTY - LEAVE SYSTEM
    
    // report name to project situation
    if ($this->name!=$old->name) {
      $ps=SqlElement::getSingleSqlElementFromCriteria('ProjectSituation', array('idProject'=>$this->id));
      if ($ps->id) {
        $ps->name=i18n('ProjectSituation').' - '.$this->name;
        $ps->save();
      }
    }
    if($this->commandOnValidWork != $old->commandOnValidWork){
      $this->updateValidatedWork(true);
    }

    // PBER #7295
    if ($old->id and $old->idProjectType!=$this->idProjectType) {
      $oldType=SqlList::getFieldFromId('ProjectType', $old->idProjectType, 'code');
      $newType=SqlList::getFieldFromId('ProjectType', $this->idProjectType, 'code');
      if (($oldType=='PRP' and $newType!='PRP') or ($oldType!='PRP' and $newType=='PRP')) {
        $crsp=SqlElement::getSingleSqlElementFromCriteria('CriticalResourceScenarioProject', array('idUser'=>getCurrentUserId(), 'idProject'=>$this->id));
        if ($crsp and $crsp->id and $crsp->proposale!=0) {
          if ($crsp->monthDelay==0) {
            $resCrsp=$crsp->delete();
          } else {
            $crsp->proposale=0;
            $resCrsp=$crsp->save();
          }
        }
      }
    }
    
    if ($this->localCurrency and $this->localToGlobalConversion!=$old->localToGlobalConversion) {
      $this->updateValuesAfterCurrencyChange($old->localToGlobalConversion);
    }
    if ($this->localCurrency!=$old->localCurrency 
     or $this->localToGlobalConversion!=$old->localToGlobalConversion 
        or $this->localCurrencyPosition!=$old->localCurrencyPosition) {
       $this->displachCurrencyToSubProjects();
    }
    $selectedProj = pq_explode(',', getSessionValue('project'));
    if (count($selectedProj)>0 and $selectedProj[0]!='*'){
      if (!$this->idProject or (!in_array($this->idProject, $selectedProj))){
        $selectedProj[] = $this->id;
        setSessionValue('project', implode(',', $selectedProj));
      }
    }
    
    return $result; 

  }
  
  public function delete() {
    // MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
    	if ($this->isLeaveMngProject) {
    		$returnValue = i18n('cantDeleteTheLeaveMngProject');
    		$returnStatus = "INVALID";
    		$returnValue .= '<input type="hidden" id="lastSaveId" value="' . htmlEncode ( $this->id ) . '" />';
    		$returnValue .= '<input type="hidden" id="lastOperation" value="save" />';
    		$returnValue .= '<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    		return $returnValue;
    	}
    }
    // MTY - LEAVE SYSTEM
  	$result = parent::delete();
  	if($this->idProject){
  	  $proj = new Project($this->idProject);
  	  $proj->ProjectPlanningElement->updateCA();
  	}
  	if(getLastOperationStatus($result)=="OK"){
  	  $favoriteProjectItem = new FavoriteProjectItem();
  	  $favList = $favoriteProjectItem->getSqlElementsFromCriteria(array('idProject'=>$this->id));
  	  $affectedFavoriteLists = array();
  	  foreach ($favList as $favItems) {
  	    if ($favItems->id) {
  	      if ($favItems->idFavoriteProjectList && !in_array($favItems->idFavoriteProjectList, $affectedFavoriteLists)) {
  	        $affectedFavoriteLists[] = $favItems->idFavoriteProjectList;
  	      }
  	      $favItems->delete();
  	    }
  	  }
  	  foreach ($affectedFavoriteLists as $idFavList) {
  	    $checkItems = new FavoriteProjectItem();
  	    $remainingItems = $checkItems->getSqlElementsFromCriteria(array('idFavoriteProjectList'=>$idFavList));
  	    if (count($remainingItems) == 0) {
  	      $favProjectList = new FavoriteProjectList($idFavList);
  	      if ($favProjectList->id) $favProjectList->delete();
  	    }
  	  }
  	  $favoriteProjectsArray = getSessionValue('favoriteProjectsArray');
  	  if ($favoriteProjectsArray) {
  	    $favArray = explode(',', $favoriteProjectsArray);
  	    if (in_array($this->id, $favArray)) {
  	      $pos = array_search($this->id, $favArray);
  	      unset($favArray[$pos]);
  	      if (count($favArray) > 0) {
  	        $newFavList = implode(',', $favArray);
  	        setSessionValue('favoriteProjectsArray', implode(',', $favArray));
  	        Parameter::storeUserParameter('favoriteProjectsArray', $newFavList);
  	      } else {
  	        setSessionValue('favoriteProjectsArray', '');
  	        setSessionValue('idFavoriteProjectList', '');
  	        setSessionValue('editFavoriteProject', '');
  	        Parameter::storeUserParameter('favoriteProjectsArray', '');
  	      }
  	    }
  	  }
  	   
  	  if($this->isSelectedProjectMultiple()){
  	    $selectedProj = pq_explode(',', getSessionValue('project'));
  	    if(in_array($this->id, $selectedProj)){
  	      $pos = array_search($this->id, $selectedProj);
  	      unset($selectedProj[$pos]);
  	      if(count($selectedProj) > 0){
  	        setSessionValue('project', implode(',', $selectedProj));
  	        setSessionValue('projectSelected', implode(',', $selectedProj));
  	        Parameter::storeUserParameter('project', implode(',', $selectedProj));
  	        Parameter::storeUserParameter('projectSelected', implode(',', $selectedProj));
  	      }else{
  	        setSessionValue('project', '*');
  	        Parameter::storeUserParameter('project', '*');
  	        Parameter::storeUserParameter('projectSelected', '*');
  	      }
  	    }
  	  }else {
  	    $currentProject = getSessionValue('project');
  	    if ($currentProject == $this->id) {
  	      setSessionValue('project', '*');
  	      setSessionValue('projectSelected', '*');
  	      Parameter::storeUserParameter('projectSelected', '*');
  	      Parameter::storeUserParameter('project', '*');
  	    }
  	  }
  	 User::resetAllVisibleProjects($this->id,null);
  	}
  	
    return $result;
  }
  
  public function dispatchOrganizationToSubProjects($oldOrganization) {
    $subProj=$this->getSubProjects(false,false); // Must refresh subProject, to be sure to get latest values (for instance when moving project, retreive correct WBS)
    foreach ($subProj as $sp) {
      if ( ! $sp->idOrganization or ($sp->organizationInherited and $sp->idOrganization==$oldOrganization) ) {
        $sp->idOrganization=$this->idOrganization;
        $sp->organizationInherited=1;
        $resSp=$sp->simpleSave();
        $sp->dispatchOrganizationToSubProjects($oldOrganization);
      } else if ($sp->organizationInherited) {
        $sp->organizationInherited=0;
        $sp->simpleSave();
      }
    }
  }
  // Ticket #1175
  public function updateValidatedWork($force=false) {
  	if (! $this->id) return;
  	$consolidateValidated=Parameter::getGlobalParameter('consolidateValidated');
  	$lst=null;
  	$sumValidatedWork=0;
  	$sumValidatedCost=0;
  	$projList = $this->getRecursiveSubProjectsFlatList(true, true);
  	$projList = '('.implode(',', array_flip($projList)).')';
  	if($this->commandOnValidWork == 1){
  	  $order=new Command();
  	  $queryWhere='idProject in ' . $projList . ' AND cancelled=0';
  	  $sumValidatedWork=$order->sumSqlElementsFromCriteria('validatedWork', null, $queryWhere);
  	  $sumValidatedCost=$order->sumSqlElementsFromCriteria('totalUntaxedAmount', null, $queryWhere);
  	}else if ($force==true) { // Update when changing mode (commandOnValidWork) or to consolidate Parent
  	  $lst=null;
  	  $prj=new Project();
  	  $queryWhere="topRefType='Project' and topRefId=$this->id and cancelled=0";
  	  $pe=new PlanningElement();
  	  $sumValidatedWork=$pe->sumSqlElementsFromCriteria('validatedWork', null, $queryWhere);
  	  $sumValidatedCost=$pe->sumSqlElementsFromCriteria('validatedCost', null, $queryWhere);
  	} else {
  	  return;
  	}
  	if (isset($this->ProjectPlanningElement)) {
  	  $this->ProjectPlanningElement->validatedWork=$sumValidatedWork;
  	  $this->ProjectPlanningElement->validatedCost=$sumValidatedCost;
  	}
  	
  	if (! $this->ProjectPlanningElement->elementary) {
  		if ($consolidateValidated=="ALWAYS") {
  			$this->ProjectPlanningElement->validatedWork=$sumValidatedWork;
  			$this->ProjectPlanningElement->validatedCost=$sumValidatedCost;
  			$this->ProjectPlanningElement->validatedCalculated=1;
  		} else if ($consolidateValidated=="IFSET") {
  		  $this->ProjectPlanningElement->validatedCalculated=0;
  			if ($sumValidatedWork) {
  				$this->ProjectPlanningElement->validatedWork=$sumValidatedWork;
  				$this->ProjectPlanningElement->validatedCalculated=1;
  			} 
  			if ($sumValidatedCost) {
  				$this->ProjectPlanningElement->validatedCost=$sumValidatedCost;
  				$this->ProjectPlanningElement->validatedCalculated=1;
  			}
  		}
  	}
  	
  	$this->save();
  	
  	if (pq_trim($this->idProject)!='') {
  		$prj=new Project($this->idProject);
  		$prj->updateValidatedWork(true);
  	}
  }
  // Ticket END
  
/** =========================================================================
   * control data corresponding to Model constraints
   * @param void
   * @return "OK" if controls are good or an error message 
   *  must be redefined in the inherited class
   */
  public function control(){
    $result="";
    $old=$this->getOld();
    $fielMessageExist=false;
    //Gautier #4304
    // PBER - disable this control (client request)
//     if($this->idProjectType and $this->id){
//       $projType = new ProjectType($this->idProjectType);
//       if($projType->isLeadProject){
//         //change type of project to lead Project
//         if ($old->idProjectType != $this->idProjectType) {
//           $planElement = new PlanningElement();
//           $cptList = $planElement->countSqlElementsFromCriteria(null,"idProject=$this->id and (refType='Activity' or refType='TestSession')");
//           if($cptList) $result .= '<br/>' . i18n ( 'cantChangeTypeOfProjectToLeadProjectIfYouHaveActivities' );
//         }
//       }
//     }
    
    if($this->codeType=='PRP'){
      if(!$this->strategicValue){
        $result.='<br/>' . i18n('errorStrategicValue');
      }
    }
    
    if ($this->codeType=='PRP' && floatval($this->ProjectPlanningElement->realWork)>0) {
      $result.='<br/>' . i18n('prpProjectCantHaveRealWork');
    }
    // Control for currencies
    if ($this->idProject and $this->idProject!=$old->idProject and $this->localCurrency) {
      $newTop=new Project($this->idProject,true);
      if ($newTop->localCurrency) {
        if ($newTop->localCurrency!=$this->localCurrency or $newTop->localToGlobalConversion!=$this->localToGlobalConversion)
        $result.='<br/>' . i18n('incorrectCurrencyOfParent');
      }
    }
    if ($this->idCatalogUO and $this->localCurrency) {
      $catalog=new CatalogUO($this->idCatalogUO);
      if ($catalog->idProject!=$this->id) {
        $cataProj=new Project($catalog->idProject,true);
        if ($cataProj->localCurrency!=$this->localCurrency or $cataProj->localToGlobalConversion!=$this->localToGlobalConversion) {
          $result.='<br/>' . i18n('incorrectCurrencyOfCatalog');
        }
      }
    }
    if ($this->id and $this->id==$this->idProject) {
      $result.='<br/>' . i18n('errorHierarchicLoop');
    } else if ($this->ProjectPlanningElement and $this->ProjectPlanningElement->id){
      $parent=SqlElement::getSingleSqlElementFromCriteria('PlanningElement',array('refType'=>'Project','refId'=>$this->idProject));
      $parentList=$parent->getParentItemsArray();
      if (pq_array_key_exists('#' . $this->ProjectPlanningElement->id,$parentList)) {
        $result.='<br/>' . i18n('errorHierarchicLoop');
      }
    }
    if ($this->id and $old->idCatalogUO and $this->idCatalogUO!=$old->idCatalogUO) {
      if (CatalogUO::isCatalogUsedOnProject($this->id, $old->idCatalogUO)) {
        $result.='<br/>' . i18n('workUnitCatalogUsedOnProject');
      }
    }
    if ($this->longitude!=null and $this->latitude!=null) {
      if ($this->longitude > 180 || $this->longitude < -180 || $this->latitude < -90 || $this->latitude > 90) {
        $result = i18n('invalidGpsData');
      }
    }
    if ($this->localCurrency) {
      if (! trim($this->localCurrencyPosition)) {
        $result .= '<br/>'. i18n ( 'messageMandatory', array($this->getColCaption ( 'localCurrencyPosition' )) );
        if(!$fielMessageExist){
          self::addFirstErrorField($this,'localCurrencyPosition',$result,Parameter::getUserParameter('paramLayoutObjectDetail'),$fielMessageExist);
        }
      }
      if (! $this->localToGlobalConversion) {
        $result .= '<br/>'. i18n ( 'messageMandatory', array($this->getColCaption ( 'localToGlobalConversion' )) );
        if(!$fielMessageExist){
          self::addFirstErrorField($this,'localToGlobalConversion',$result,Parameter::getUserParameter('paramLayoutObjectDetail'),$fielMessageExist);
        }
      }
      if (! $this->globalToLocalConversion) {
        $result .= '<br/>'. i18n ( 'messageMandatory', array($this->getColCaption ( 'globalToLocalConversion' )) );
        if(!$fielMessageExist){
          self::addFirstErrorField($this,'globalToLocalConversion',$result,Parameter::getUserParameter('paramLayoutObjectDetail'),$fielMessageExist);
        }
      }
    }
    
    if ($this->id and $this->excludeFromGlobalPlanning==1 and $old->excludeFromGlobalPlanning==0) {
      $pe=new PlanningElement();
      $peTable=$pe->getDatabaseTableName();
      $pexStart=PlanningElementExtension::$_startId;
      $dep=new Dependency();
      $depTable=$dep->getDatabaseTableName();
      $where=" idProject=$this->id and exists (select 'x' from $depTable dep "
          ." where (dep.predecessorId=$peTable.id and dep.successorId>$pexStart) or (dep.predecessorId>$pexStart and dep.successorId=$peTable.id)"
          .")";
      $cpt=$pe->countSqlElementsFromCriteria(null,$where);
      if ($cpt>0) {
        $result.='<br/>' .i18n('cannotExcludeFromGlobalPlanning',array($cpt));
      }
    }
    // ELIOTT - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
    	// For the leave system Project (isLeaveMngProject=1)
    	if($this->isLeaveMngProject==1){
    		// Check if there is already one project with the attribute $isLeaveMngProject set to 1
    		//$isLvPrjRequest = $this->getFirstSqlElementFromCriteria('Project', array("isLeaveMngProject"=>1));
    		$isLvPrjRequest = Project::getLeaveProjectId();
    		if (!isset($isLvPrjRequest->id)) {
    			$isLvPrjRequest=null;
    		}
    		if($isLvPrjRequest) {
    			if ($isLvPrjRequest->id != $this->id){
    				$result .= '<br/>' .i18n('leaveMngProjectAlreadyExists');
    			}
    		}
    		// The Leave System Project can't have parent
    		if ($this->idProject>0) {
    			$result .= '<br/>' . i18n('leaveMngProjectCantHaveParentProject');
    		}
    	}
    }
    
    if ($this->id && property_exists($this, 'idPhasing') && $this->idPhasing) {
      if ($old->idPhasing != $this->idPhasing) {
        $abacusProj = new AbacusProject();
        $abacusList = $abacusProj->getSqlElementsFromCriteria(array('idProject' => $this->id),false);        
        if (count($abacusList) > 0) {
          $incompatibleAbacus = array();          
          foreach ($abacusList as $abProj) {
            $abDef = new AbacusDefinition($abProj->idAbacusDefinition, true);
            if ($abDef->idPhasing && $abDef->idPhasing != $this->idPhasing) {
              $incompatibleAbacus[$abDef->id] = $abDef->name;
            }
          }
          if (count($incompatibleAbacus) > 0) {
            $result .= '<br/>' . i18n('errorPhasingChangeIncompatibleAbacus') . ' : ';
            $result .= '<br/>' . implode(', ', $incompatibleAbacus);
          }
        }
      }
    }
    
    // ELIOTT - LEAVE SYSTEM
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public static function getAdminitrativeProjectList($returnResultAsArray=false, $withLeaveProject=true) {
    if (self::$_administrativeProjectList!==null) {
      $arrayProj=self::$_administrativeProjectList;
    } else {
    	$arrayProj=array();
    	$arrayProj[]=0;
      // Ids only : instantiating a Project per row costs far more than the query
      $typeObj=new ProjectType();
      $projObj=new Project();
      $typeTable=$typeObj->getDatabaseTableName();
      $projTable=$projObj->getDatabaseTableName();
      $query="select p.id as id from $projTable p, $typeTable t where p.idProjectType=t.id";
      $query.=" and t.code=" . Sql::str('ADM');
      foreach ($typeObj->getDatabaseCriteria() as $col => $val) {
        $query.=" and t." . $typeObj->getDatabaseColumnName($col) . "=" . Sql::str($val);
      }
      $result=Sql::query($query);
      while ($line=Sql::fetchLine($result)) {
        $id=$line['id'];
  // MTY - LEAVE SYSTEM
                  if (isLeavesSystemActiv()) {
                      $isLvePrjt = self::isTheLeaveProject($id);
                      if ($isLvePrjt and $withLeaveProject==false) {continue;}
                  }
  // MTY - LEAVE SYSTEM
        	$arrayProj[$id]=$id;
      }
    }
    self::$_administrativeProjectList=$arrayProj;
  	if ($returnResultAsArray) return $arrayProj;
  	return '(' . implode(', ',$arrayProj) . ')';
  }

  public static function getFixedProjectList($returnResultAsArray=false) {
    $arrayProj=array();
    $arrayProj[]=0;
    $proj=new Project(); 
    $critProj=array('fixPlanning'=>'1', 'idle'=>'0');
    // Skip dependent objects : the loop needs the id and the sub project list only
    $listProj=$proj->getSqlElementsFromCriteria($critProj, false, null, null, false, true);
    foreach ($listProj as $proj) {
// MTY - LEAVE SYSTEM
      if (isLeavesSystemActiv()) {  
        if (self::isTheLeaveProject($proj->id) && !self::isProjectLeaveVisible()) {continue;}
      }
// MTY - LEAVE SYSTEM        
      $arrayProj[]=$proj->id;
      $sublist=$proj->getRecursiveSubProjectsFlatList(true);
      if ($sublist and count($sublist)>0) {
        foreach($sublist as $subId=>$subName) {
          $arrayProj[]=$subId;
        }
      }
    }
    if ($returnResultAsArray) return $arrayProj;
    return '(' . implode(', ',$arrayProj) . ')';
  }
  
  //damian
  public static function getFixedProjectPerimeterList($returnResultAsArray=false){
    $arrayProj = array();
    $proj = new Project();
    $listProj = $proj->getSqlElementsFromCriteria(array('fixPerimeter'=>'1', 'idle'=>'0'));
    foreach ($listProj as $projPerim){
      $arrayProj[$projPerim->id] = $projPerim->name;
      $sublist = $projPerim->getRecursiveSubProjectsFlatList(true);
      if($sublist and count($sublist) > 0) {
        foreach ($sublist as $subId=>$subName){
          $arrayProj[$subId] = $subName;
        }
      }
    }
    if ($returnResultAsArray) return $arrayProj;
    return '(' . implode(', ',$arrayProj) . ')';
  }
  
  public function getColor() {
    if (isset(self::$_cacheColor[$this->id])) return self::$_cacheColor[$this->id];
    $color="#777777";
    if ($this->color) {
      $color=$this->color;
    } else if ($this->idProject) {
      $top=new Project($this->idProject);
      $color=$top->getColor();
    }
    self::$_cacheColor[$this->id]=$color;
    return $color;
  }
  
  public static function getTemplateList() {
    $result=array();
    $types=SqlList::getListWithCrit('ProjectType',array('code'=>'TMP'));
    foreach($types as $typId=>$typName) {
      $projects=SqlList::getListWithCrit('Project', array('idProjectType'=>$typId));
      $result=array_merge_preserve_keys($result,$projects);
    }
    return $result;
  }
  public static function getProposaleList() {
    $result=array();
    $types=SqlList::getListWithCrit('ProjectType',array('code'=>'PRP'));
    foreach($types as $typId=>$typName) {
      $projects=SqlList::getListWithCrit('Project', array('idProjectType'=>$typId));
      $result=array_merge_preserve_keys($result,$projects);
    }
    return $result;
  }
  public static function getUnderConstructionList() {
    $projects=SqlList::getListWithCrit('Project',array('isUnderConstruction'=>'1'));
    return $projects;
  }
  public static function getTemplateInClauseList() {
    $list=self::getTemplateList();
    $in='(0';
    foreach ($list as $id=>$name) {
      $in.=','.$id;
    }
    $in.=')';
    return $in;
  }
  public static function getProposaleInClauseList() {
    $list=self::getProposaleList();
    $in='(0';
    foreach ($list as $id=>$name) {
      $in.=','.$id;
    }
    $in.=')';
    return $in;
  }
  public static function getUnderConstructionInClauseList() {
    $list=self::getUnderConstructionList();
    $in='(0';
    foreach ($list as $id=>$name) {
      $in.=','.$id;
    }
    $in.=')';
    return $in;
  }
  
// ADD BY Marc TABARY - 2017-03-17 - COPY ACTIVITY PRICE WHEN COPY PROJECT
  public function copyTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments=false, $withAffectations=false,
                         $toProject=null, $toActivity=null, $copyToWithResult=false, $copyToWithActivityPrice=false, $copyToWithStatus=false, $copyToWithVersionProjects=false, $copyToWithSubTask=false, $moveAfterCreate = null) {
    // Control that copy is not directly copied into structure of copied project
    if ($toProject) {
      $sub=$this->getSubProjectsList(false);
      if ($toProject==$this->id or isset($sub[$toProject])) {
        $result=i18n('copyNotAsSubOfCurrent').'<br/>';
        $this->_copyResult=$result;
        return $this;
      }
    }
    self::$_copyProjectId=$this->id;
    $result=parent::copyTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments, $withAffectations ,
    		                 $toProject, $toActivity, $copyToWithResult, $copyToWithActivityPrice, $copyToWithStatus, false, $moveAfterCreate);
    if (!$toProject) $result->idProject=null;
    self::$_copyProjectId=null;
    if($copyToWithVersionProjects==true){
      $vp=new VersionProject();
      $crit=array('idProject'=>$this->id);
      $list=$vp->getSqlElementsFromCriteria($crit);
      foreach ($list as $vp) {
        $vp->idProject=$result->id;
        $vp->id=null;
        $vp->save();
      }
    }
    if($copyToWithActivityPrice==true) {
        $ap = new ActivityPrice();
        $crit=array('idProject'=>$this->id);
        $list=$ap->getSqlElementsFromCriteria($crit);
        foreach ($list as $ap) {
            $ap->idProject=$result->id;
            $ap->id=null;
            $ap->save();
        }
    }
    if($withAffectations==true){
      $aff = new Affectation();
      $crit=array('idProject'=>$this->id);
      $list=$aff->getSqlElementsFromCriteria($crit);
      foreach ($list as $aff) {
	    $res = new ResourceAll($aff->idResource);
	    if ($res->idle) continue;
        $aff->idProject=$result->id;
        $aff->id=null;
        $aff->save();
      }
    }
    
    return $result;
  } 
  
  public static function setNeedReplan($id) {
    if (PlanningElement::$_noDispatch and PlanningElement::$_noDispatch!='needReplan') return;
    $adminProjects=Project::getAdminitrativeProjectList(true);
    if (isset($adminProjects[$id])) return;
    $proj=SqlElement::getSingleSqlElementFromCriteria("ProjectPlanningElement",array('refType'=>'Project','refId'=>$id),true);
    if (!$proj->id or $proj->needReplan==true) return;
    $proj->needReplan=true;
    $proj->simpleSave();
  }
  public static function unsetNeedReplan($id) {
    $proj=SqlElement::getSingleSqlElementFromCriteria("ProjectPlanningElement",array('refType'=>'Project','refId'=>$id),true);
    if (PlannedWork::$_planningInProgress and $id) {
      // Attention, we'll execute direct query to avoid concurrency issues for long duration planning
      // Otherwise, saving planned data may overwrite real work entered on Timesheet for corresponding items.
      $ppe=new ProjectPlanningElement();
      $ppeTable=$ppe->getDatabaseTableName();
      $query="UPDATE $ppeTable SET needReplan=0 WHERE refType='Project' and refId=$id";
      Sql::query($query); 
    } else {
      $proj->needReplan=false;
      $proj->simpleSave();
    }
    if ($proj->topId) {
      $top=new ProjectPlanningElement($proj->topId);
      if ($top->needReplan) {
        $count=$top->countSqlElementsFromCriteria(array('refType'=>'Project','topId'=>$top->id, 'needReplan'=>'1'));
        if ($count==0) {
          self::unsetNeedReplan($top->refId);
        }
      }
    }
  }
  protected function getStaticFieldsTooltip() {
    return self::$_fieldsTooltip;
  }
  private static $_storeAttributes=null;
  public function setAttributes() {
    if (! self::$_storeAttributes)  self::$_storeAttributes=self::$_fieldsAttributes;
    else self::$_fieldsAttributes=self::$_storeAttributes;
    global $availableAttributes, $contextForAttributes;
    if ($contextForAttributes!='global' and $contextForAttributes!='multipleUpdate' and SqlList::getFieldFromId("Status", $this->idStatus, "setHandledStatus")!=0) self::$_fieldsAttributes["isUnderConstruction"]="readonly,nobr";
//     if (Parameter::getGlobalParameter('allowTypeRestrictionOnProject')!='YES') {
//       unset($this->_sec_restrictTypes);
//       unset($this->_spe_restrictTypes);
//     }
    
    if(Parameter::getGlobalParameter('allowTypeRestrictionOnProject')!='YES') {
      self::$_fieldsAttributes["_sec_restrictTypes"]="hidden";
    }
    //     if (Parameter::getGlobalParameter('allowListRestrictionOnProject')!='YES') {
    //       unset($this->_sec_restrictLists);
    //       unset($this->_spe_restrictLists);
    //     }
    
    if (Parameter::getGlobalParameter('allowListRestrictionOnProject')!='YES') {
      self::$_fieldsAttributes["_sec_restrictLists"]="hidden";
    }
    if ($this->ProjectPlanningElement and $this->ProjectPlanningElement->realWork>0) {
      self::$_fieldsAttributes["isUnderConstruction"]="readonly,nobr";
    }
    if($this->fixPerimeter==0){
      self::$_fieldsAttributes["allowReduction"]="invisible";
      self::$_fieldsAttributes["_lib_helpAllowReduction"]="invisible";
    }
    if($this->paused==1){
      self::$_fieldsAttributes["fixPlanning"]="readonly,nobr";
    }
    if($this->ProjectPlanningElement and $this->ProjectPlanningElement->topRefId!=''){
      $parent=new $this->ProjectPlanningElement->topRefType ($this->ProjectPlanningElement->topRefId);
    }
    if ($contextForAttributes!='global' and $contextForAttributes!='multipleUpdate' and SqlList::getFieldFromId("Status", $this->idStatus, "setPausedStatus")!=0 or (isset($parent) and $parent->paused==1)){
      self::$_fieldsAttributes["paused"]="readonly,nobr";
    }
    if (Parameter::getGlobalParameter('projectDailyHours')!='true') {
      self::$_fieldsAttributes["_sec_ProjectDailyHours"]="hidden";
    }
    if(Module::isModuleActive("moduleGestionCA")){
      self::$_fieldsAttributes["idCatalogUO"]="";
    }
    self::$_fieldsAttributes['benefitValue']='size50';
    self::$_fieldsAttributes['strategicValue']='size50';
    if ($this->id) {
      if (isset(self::$_fieldsAttributes['idProject'])) self::$_fieldsAttributes['idProject'].=',doNotAutoFill';
      else self::$_fieldsAttributes['idProject']='doNotAutoFill';
    }
    //gautier
    if (!is_array($availableAttributes)) self::$_fieldsAttributes["_sec_Proposal"]="hidden";
    if (isLeavesSystemActiv()) {
      global $doNotRestrictLeave;
      // Can't see or modify a lot of attributs if this project is the leave project
      if ($this->isLeaveMngProject==1 and ! $doNotRestrictLeave) {
        self::$_fieldsAttributes['idProjectType']='readonly';
        self::$_fieldsAttributes['idProject']='hidden';
        self::$_fieldsAttributes['idStatus']='hidden';
        self::$_fieldsAttributes['idHealth']='hidden';
        self::$_fieldsAttributes['isUnderConstruction']='hidden';
        self::$_fieldsAttributes['fixPerimeter']='hidden';
        self::$_fieldsAttributes['allowReduction']='hidden';
        self::$_fieldsAttributes['_lib_helpAllowReduction']='hidden';
        self::$_fieldsAttributes['excludeFromGlobalPlanning']='hidden';
        self::$_fieldsAttributes['handled']='hidden';
        self::$_fieldsAttributes['handledDate']='hidden';
        self::$_fieldsAttributes['done']='hidden';
        self::$_fieldsAttributes['doneDate']='hidden';
        self::$_fieldsAttributes['idle']='hidden';
        self::$_fieldsAttributes['idleDate']='hidden';
        self::$_fieldsAttributes['cancelled']='hidden';
        self::$_fieldsAttributes['idClient']='hidden';
        self::$_fieldsAttributes['idContact']='hidden';
        self::$_fieldsAttributes['idSponsor']='hidden';
        self::$_fieldsAttributes['idResource']='hidden';
        self::$_fieldsAttributes['fixPlanning']='hidden';
        self::$_fieldsAttributes['paused']='hidden';
        self::$_fieldsAttributes['commandOnValidWork']='hidden';
        self::$_fieldsAttributes['ProjectPlanningElement']='hidden';
        self::$_fieldsAttributes['_sec_treatment']='hidden';
        self::$_fieldsAttributes['_sec_ProjectDailyHours']='hidden';
    
        unset($this->_sec_Progress);
        unset($this->_sec_Affectations);
        unset($this->_spe_affectations);
        unset($this->_lib_cancelled);
        unset($this->_sec_ProductprojectProducts);
        unset($this->_ProductProject);
        unset($this->_sec_VersionprojectVersions);
        unset($this->_VersionProject);
        unset($this->_sec_Subprojects);
        unset($this->_spe_subprojects);
        unset($this->_sec_restrictTypes);
        unset($this->_spe_restrictTypes);
        unset($this->_sec_predecessor);
        unset($this->_Dependency_Predecessor);
        unset($this->_sec_successor);
        unset($this->_Dependency_Successor);
      }
    }
    if($this->codeType=='PRP'){
      self::$_fieldsAttributes["_sec_Proposal"]="";
      // en construction check and readOnly
      self::$_fieldsAttributes["isUnderConstruction"]="readonly,nobr";
      
      self::$_fieldsAttributes["idHealth"]="hidden";
      self::$_fieldsAttributes["idQuality"]="hidden";
      self::$_fieldsAttributes["idTrend"]="hidden";
      self::$_fieldsAttributes["idOverallProgress"]="hidden";
      
      self::$_fieldsAttributes["fixPlanning"]="hidden";
      self::$_fieldsAttributes["paused"]="hidden";
      self::$_fieldsAttributes["fixPerimeter"]="hidden";
      self::$_fieldsAttributes['strategicValue']='required,size50';
      self::$_fieldsAttributes['idRiskLevel']="";
      
      self::$_fieldsAttributes['idCatalogUO']="hidden";
      
      self::$_fieldsAttributes["_sec_Synchronisation"]="hidden";
      self::$_fieldsAttributes["_spe_isSynchronised"]="hidden";
      
    }  else if($this->codeType=='ADM') {
      // Description
      self::$_fieldsAttributes["idClient"]="hidden";
      self::$_fieldsAttributes["idContact"]="hidden";
      self::$_fieldsAttributes["idCatalogUO"]="hidden";
      self::$_fieldsAttributes["idRiskLevel"]="hidden";
      self::$_fieldsAttributes["contractCode"]="hidden";
      self::$_fieldsAttributes["clientCode"]="hidden";
      self::$_fieldsAttributes["idSponsor"]="hidden";
      
      // Traitement
      self::$_fieldsAttributes["strategicValue"]="hidden";
      self::$_fieldsAttributes["benefitValue"]="hidden";
      self::$_fieldsAttributes["idHealth"]="hidden";
      self::$_fieldsAttributes["idQuality"]="hidden";
      self::$_fieldsAttributes["idTrend"]="hidden";
      self::$_fieldsAttributes["idOverallProgress"]="hidden";
      self::$_fieldsAttributes["fixPlanning"]="hidden";
      self::$_fieldsAttributes["paused"]="hidden";
      self::$_fieldsAttributes["fixPerimeter"]="hidden";
      self::$_fieldsAttributes["isUnderConstruction"]="hidden";
      self::$_fieldsAttributes["excludeFromGlobalPlanning"]="hidden";
      self::$_fieldsAttributes["commandOnValidWork"]="hidden";
      
      // Configuration - Produits/version
      self::$_fieldsAttributes["_sec_ProductprojectProducts"]="hidden";
      self::$_fieldsAttributes["_sec_VersionprojectVersions"]="hidden";

      // Detail - Synchronisation
      self::$_fieldsAttributes["_sec_Synchronisation"]="hidden";
      self::$_fieldsAttributes["_spe_isSynchronised"]="hidden";
      
      // Dependances  - Predecesseur/successeur      
      self::$_fieldsAttributes["_sec_predecessor"]="hidden";
      self::$_fieldsAttributes["_sec_successor"]="hidden";
    } else{
        self::$_fieldsAttributes['strategicValue']="size50";
        //self::$_fieldsAttributes['idRiskLevel']="hidden";
    }
    if (Parameter::getGlobalParameter("multiCurrency")!='YES') {
      self::$_fieldsAttributes['_sec_LocalCurrency']='hidden';
    } else if ($this->inheritedCurrency) {
      self::$_fieldsAttributes['localCurrency'].=",readonly";
      self::$_fieldsAttributes['localCurrencyPosition'].=",readonly";
      self::$_fieldsAttributes['localToGlobalConversion'].=",readonly";
      self::$_fieldsAttributes['globalToLocalConversion'].=",readonly";
    } else if (!$this->localCurrency) {
      self::$_fieldsAttributes['localCurrencyPosition'].=",readonly";
      self::$_fieldsAttributes['localToGlobalConversion'].=",readonly";
      self::$_fieldsAttributes['globalToLocalConversion'].=",readonly";
      $this->localToGlobalConversion=null;
      $this->globalToLocalConversion=null;
    } else {
      self::$_fieldsAttributes['localCurrencyPosition'].=",required";
      self::$_fieldsAttributes['localToGlobalConversion'].=",required";
      self::$_fieldsAttributes['globalToLocalConversion'].=",required";
    }
    
    if (!Module::isModuleActive("moduleAbacus")) self::$_fieldsAttributes["_sec_Abacus"]="hidden";
  }
  
  public static function getSelectedProject($clearStarForAll=false,$clearMultiSelection=false) {
    $proj=null;
    if (sessionValueExists('project')) {
      $proj=getSessionValue('project');
    }
    if ($clearStarForAll and $proj=='*') $proj=null; // Selected = all
    else if (! $clearStarForAll and ! $proj) $proj='*';
    if ($clearMultiSelection and pq_strpos($proj,',')!==null) $proj=null; // Selected = multi
    return $proj;
  }
  public static function isSelectedProject() {
    if (sessionValueExists('project')) {
      $proj=getSessionValue('project');
      if ($proj=='*' or !$proj) return false;
      else return true;
    } else {
      return false;
    }
  }
  public static function isSelectedProjectMultiple() {
    if (sessionValueExists('project')) {
      $proj=getSessionValue('project');
      return (pq_strpos($proj,',') !== false);
    }
    return false;
  }
  public static function getSelectedProjectList() {
    $proj=self::getSelectedProject(true,false);
    $projList=pq_explode(',',$proj);
    return $projList;
  }
  public static function setSelectedProject($proj){
    setSessionValue('project', $proj);
  }
  
  public  function setRecursiveSubProjectCatalog($newIdCatalog,$oldIdCatalog=false,$includeSelf=false){
    $lstRec=$this->getRecursiveSubProjectsIdWithSameCatalog($oldIdCatalog);
    foreach ($lstRec as $idx=>$idP) {
      if (CatalogUO::isCatalogUsedOnProject($idP, $oldIdCatalog)) {
        unset($lstRec[$idx]);
      }
    }
    $lstRec=implode(",", $lstRec);
    if($includeSelf and ! CatalogUO::isCatalogUsedOnProject($this->id, $oldIdCatalog)){
      $lstRec=($lstRec!="")?$this->id.",".$lstRec:$this->id;
    }
    if($lstRec!=''){
      $table=$this->getDatabaseTableName();
      $newIdCatalog=($newIdCatalog=='')?'NULL':$newIdCatalog;
      $updateQuery="UPDATE $table SET idCatalogUO = $newIdCatalog WHERE id in ($lstRec)";
      $resQuery=Sql::query($updateQuery);
      $res=($resQuery!=false)?'OK':'ERROR';
    }else{
      $res='NOCHANGE';
    }      
    return $res;
  }
  
  public  function setRecursiveSubProjectCalendarDefinition($newIdCalendarDefinition,$oldIdCalendarDefinition=false,$includeSelf=false){
    $lstRec=$this->getRecursiveSubProjectsIdWithSameCalendarDefinition($oldIdCalendarDefinition);
    foreach ($lstRec as $idx=>$idP) {
      $proj = new Project($idP,true);
      $oldProj = $proj->getOld();
      if ($oldProj->idCalendarDefinition != $oldIdCalendarDefinition) {
        unset($lstRec[$idx]);
      }
    }
    $lstRec=implode(",", $lstRec);
    if($includeSelf){// and ! CatalogUO::isCatalogUsedOnProject($this->id, $oldIdCatalog)
      $lstRec=($lstRec!="")?$this->id.",".$lstRec:$this->id;
    }
    if($lstRec!=''){
      $table=$this->getDatabaseTableName();
      $newIdCalendarDefinition=($newIdCalendarDefinition=='')?'NULL':$newIdCalendarDefinition;
      $updateQuery="UPDATE $table SET idCalendarDefinition = $newIdCalendarDefinition WHERE id in ($lstRec)";
      $resQuery=Sql::query($updateQuery);
      $res=($resQuery!=false)?'OK':'ERROR';
    }else{
      $res='NOCHANGE';
    }
    return $res;
  }
  
  public static function getIdProjectForIdCalendarDefinition(){
    $arrayProject = self::getSelectedProjectList();
    if(!$arrayProject)return null;
    $idCalendarDefinitionList = array();
    $idProjectList = array();
    foreach ($arrayProject as $idProject){
      $project = new Project($idProject,true);
      if($project->idCalendarDefinition)$idCalendarDefinitionList[$project->idCalendarDefinition]=$project->idCalendarDefinition;
      $idProjectList = array_merge_preserve_keys($idProjectList,$project->getRecursiveSubProjectsFlatList());
    }
    foreach ($idProjectList as $idP=>$nameP){
      $project = new Project($idP,true);
      if($project->idCalendarDefinition)$idCalendarDefinitionList[$project->idCalendarDefinition]=$project->idCalendarDefinition;
    }
    if(count($idCalendarDefinitionList)>1){
      return null;
    }else{
      return $arrayProject[array_key_first($arrayProject)];
    }
  }
  
  public static function isMultiCurrencyEnabled() {
    if (Parameter::getGlobalParameter("multiCurrency")=='YES') return true;
    else return false;
  }
  public static function hasProjectCurrency($idProject) {
    if (! self::isMultiCurrencyEnabled()) return false;
    if (self::$_currencyPerProject===null) self::getLocalCurrencies();
    if (isset(self::$_currencyPerProject[$idProject])) return true;
    else return false;
  }
  public static function getProjectCurrency($idProject) {
    if (self::hasProjectCurrency($idProject)) return self::$_currencyPerProject[$idProject];
    else return Parameter::getGlobalParameter("currency");
  }
  public static function getProjectCurrencyWithCss($idProject) {
    if (self::hasProjectCurrency($idProject)) return '<span class="localLabelClass">'.self::$_currencyPerProject[$idProject].'</span>';
    else return Parameter::getGlobalParameter("currency");
  }
  public static function getProjectCurrencyPosition($idProject) {
    if (self::hasProjectCurrency($idProject)) return self::$_currencyPositionPerProject[$idProject];
    else return Parameter::getGlobalParameter("currencyPosition");
  }
  public static function getProjectConversionRate($idProject) {
    if (self::hasProjectCurrency($idProject)) return self::$_localToGlobalRatePerProject[$idProject];
    else return 1;
  }
  public static function getLocalCurrencies() {
    $crit="localCurrency is not null and localCurrency!=''";
    self::$_currencyPerProject=SqlList::getListWithCrit('Project', $crit, 'localCurrency',null, true);
    self::$_currencyPositionPerProject=SqlList::getListWithCrit('Project', $crit, 'localCurrencyPosition',null, true);
    self::$_localToGlobalRatePerProject=SqlList::getListWithCrit('Project', $crit, 'localToGlobalConversion',null, true);
    self::$_globalToLocalRatePerProject=SqlList::getListWithCrit('Project', $crit, 'globalToLocalConversion',null, true);
    foreach (self::$_localToGlobalRatePerProject as $idP=>$val) {
      if (round($val,4)==$val) continue; // Value is not rounded ;)
      if (! isset(self::$_globalToLocalRatePerProject[$idP])) continue;
      $rev=self::$_globalToLocalRatePerProject[$idP];
      if (round($rev,4)==$rev) {
        self::$_localToGlobalRatePerProject[$idP]=1/$rev;
      }
    }    
  }
  public function calculateFieldsForDisplay() {
    $globalCurrency=Parameter::getGlobalParameter('currency');
    $globalCurrencyPosition=Parameter::getGlobalParameter('currencyPosition');
    if (!$this->localCurrency) return;
    
    $this->localToGlobalDisplay=(($this->localCurrencyPosition=='before')?$this->localCurrency:'')." 1 ".(($this->localCurrencyPosition!='before')?$this->localCurrency:'')
    ." = ".(($globalCurrencyPosition=='before')?$globalCurrency:'')." ".(($this->localToGlobalConversion>0)?htmlDisplayNumericWithoutTrailingZeros($this->localToGlobalConversion):'___')." ".(($globalCurrencyPosition!='before')?$globalCurrency:'');
   
    $this->globalToLocalDisplay=(($globalCurrencyPosition=='before')?$globalCurrency:'')." 1 ".(($globalCurrencyPosition!='before')?$globalCurrency:'')
    ." = ".(($this->localCurrencyPosition=='before')?$this->localCurrency:'')." ".(($this->globalToLocalConversion>0)?htmlDisplayNumericWithoutTrailingZeros($this->globalToLocalConversion):'___')." ".(($this->localCurrencyPosition!='before')?$this->localCurrency:'');
  }
  private function displachCurrencyToSubProjects() {
    $pList=$this->getSqlElementsFromCriteria(array('idProject'=>$this->id));
    foreach ($pList as $subProj) {
      $subProj->localCurrency=$this->localCurrency;
      $subProj->localCurrencyPosition=$this->localCurrencyPosition;
      $subProj->localToGlobalConversion=$this->localToGlobalConversion;
      $subProj->globalToLocalConversion=$this->globalToLocalConversion;
      $subProj->inheritedCurrency=($subProj->localCurrency)?1:0;
      $subProj->save();
    }
    
  }
  
  public function updateValuesAfterCurrencyChange($oldConversionValue) {
    $arrayObj=array(
        "Risk", "Opportunity", "ChangeRequest", "Incoming", "ProjectHistory",
        "ActivityPrice", "ComplexityValues", "CatalogUO", "WorkCommand", "TokenDefinition", "WorkTokenClientContract",  
        "BillLine", "Quotation", "Command", "Bill", "Term", "Payment", 
        "CallForTender", "Tender", "ProviderOrder", "ProviderBill", "ProviderTerm", "ProviderPayment",  
        "ExpenseDetail", "IndividualExpense", "ActivityExpense", "ProjectExpense",
        "Work", "WorkElement", "Assignment", 
        "TestSessionPlanningElement", "MeetingPlanningElement", "ActivityPlanningElement", "ProjectPlanningElement"
    );
    self::$_currencyPerProject[$this->id]=$this->localCurrency;
    self::$_localToGlobalRatePerProject[$this->id]=$this->localToGlobalConversion;
    SqlElement::$_skipAllControls=true;
    traceLog("===== Change currency for project $this->id from '$oldConversionValue' to '$this->localToGlobalConversion' | ".count($arrayObj)." objects to update");
    foreach ($arrayObj as $class) {
      $nb=0;
      $obj=new $class();
      $crit="idProject=$this->id";
      if ($class=='ComplexityValues') {
        $cuo=new CatalogUO(); $cuoTable=$cuo->getDatabaseTableName();
        $crit="idCatalogUO in (select id from $cuoTable where idProject=$this->id)";
      } else if ($class=='BillLine') {
        $q=new Quotation();$qTable=$q->getDatabaseTableName();
        $c=new Command();$cTable=$c->getDatabaseTableName();
        $b=new Bill();$bTable=$b->getDatabaseTableName();
        $crit="( refType='Quotation' and refId in (select id from $qTable where idProject=$this->id) )";
        $crit.="or ( refType='Command' and refId in (select id from $cTable where idProject=$this->id) )";
        $crit.="or ( refType='Bill' and refId in (select id from $bTable where idProject=$this->id) )";
      } else if ($class=='WorkTokenClientContract') {
        $cc=new ClientContract(); $ccTable=$cc->getDatabaseTableName();
        $crit="idClientContract in (select id from $ccTable where idProject=$this->id)";
      }
      $objList=$obj->getSqlElementsFromCriteria(null,null,$crit);
      if (count($objList)==0) continue;
      traceLog(" => $class : ".count($objList)." lines to update");
      foreach ($objList as $obj) {
        $fldUpdated=0;
        foreach($obj as $fld=>$val) {  
          if ($obj->isAmount($fld) and $obj->isLocal($fld) and ! $obj->isAttributeSetToField($fld,'calculated')) {
            $globFld=pq_substr($fld,0,-5);
            if (floatval($oldConversionValue)!=0) { // Just change rate => convert Local to Global
              $obj->$globFld=$obj->calculateGlobalFromLocal($obj->$fld,$this->id);
            } else { // New definition, local never set => convert Global to Local
              $obj->$fld=$obj->calculateLocalFromGlobal($obj->$globFld,$this->id);
            }
            $fldUpdated++;
          }
        }
        if ($fldUpdated) {
          $obj->saveForced(true);
          $nb++;
          if ($nb%100==0) traceLog("    $class : $nb lines updated");
        }
      }
      traceLog("    $class : $nb lines updated");
    } 
    SqlElement::$_skipAllControls=false;
  }
  
  
  /**
   * Calculates and creates assignments from project abacuses
   * @return string result message
   */
  public function createAssignmentsFromAbacus() {
    $result = '';
    $returnStatus = 'OK';
    
    if (!$this->id) {
      $result = '<div class="NO_CHANGE">' . i18n('errorProjectNotSaved') . '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
      $result .= '<input type="hidden" id="lastOperation" value="createAssignments" />';
      return $result;
    }
    
    // 1 - Calculate work/rates by resource, phase, and type
    $calculatedValues = $this->calculateAbacusValues();
    
    if (count($calculatedValues) == 0) {
      $result = '<div class="NO_CHANGE">' . i18n('noAbacusDataToProcess') . '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
      $result .= '<input type="hidden" id="lastOperation" value="createAssignments" />';
      return $result;
    }
    
    // 2 - Purge old assignments linked to abacuses
    $purgedCount = $this->purgeAbacusAssignments();
    
    // 3 - Create new assignments
    $createdCount = 0;
    $errors = array();
    $warnings = array();
    
    foreach ($calculatedValues as $idPhase => $phaseData) {
      foreach ($phaseData as $idAffectable => $roleData) {
        foreach ($roleData as $roleKey => $resourceData) {
          $created = $this->createAssignmentsForPhaseAndResource($idPhase, $idAffectable, $resourceData, $errors, $warnings);
          $createdCount += $created;
        }
      }
    }
    
    if (count($errors) > 0) {
      $returnStatus = ($createdCount > 0) ? 'INCOMPLETE' : 'ERROR';
      $result .= implode('<br/>', array_unique($errors));
      if ($createdCount > 0) $result .= '<br/>' . i18n('assignmentsCreatedFromAbacus', array($createdCount, $purgedCount));
      
    } else if ($createdCount == 0 && $purgedCount == 0) {
      $returnStatus =  'NO_CHANGE';
      $result .= i18n('noAbacusChanged');
      if (count($warnings) > 0) $result .= '<br/>' . implode('<br/>', array_unique($warnings));     
    } else {
      $returnStatus = 'OK';
      $result .= i18n('assignmentsCreatedFromAbacus',  array( $createdCount, $purgedCount));
    }
    
    $result .= '<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    $result .= '<input type="hidden" id="lastOperation" value="createAssignments" />';
    $result .= '<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
    
    return $result;
  }
  
  /**
   * Calculates values (work or rates) by resource, phase, and type
   * @return array Structure: [idPhase][idAffectable] = ['fixed'=>value, 'proportional'=>value, 'type'=>type, 'abacusLines'=>array]
   */
  private function calculateAbacusValues() {
    $values = array();
    $abacusProj = new AbacusProject();
    $abacusProjectList = $abacusProj->getSqlElementsFromCriteria(array('idProject' => $this->id, 'idle' => '0'));
    
    if (count($abacusProjectList) == 0) return $values;
    
    foreach ($abacusProjectList as $abProj) {
      $abDef = new AbacusDefinition($abProj->idAbacusDefinition, true);
      if (!$abDef->id || $abDef->idle == 1) continue;
      
      if ($this->idPhasing) {
        if ($abDef->idPhasing && $abDef->idPhasing != $this->idPhasing) continue;       
      }
      
      $abLine = $this->getAbacusLineFromProject($abProj);
      if (!$abLine || !$abLine->id) continue;
           
      $idRole = $this->getAbacusRole($abLine, $abDef);
      $roleKey = $idRole ? $idRole : 'default';
      
      if ($this->idPhasing) {
        $phases = $this->getProjectPhases();
      } else {
        $phases = $this->getAbacusPhases($abDef);
      }
      
      foreach ($phases as $phase) {
        $phaseValue = $this->getAbacusPhaseValue($abLine->id, $phase->id);
        if (!$phaseValue || $phaseValue == 0) continue;
        
        $valueFieldsProduct = $this->getAbacusValueFieldsProduct($abProj, $abDef);
        $quantity = ($abProj->quantity && $abProj->quantity > 0) ? $abProj->quantity : 1;
        $calculatedValue = $phaseValue * $valueFieldsProduct * $quantity;
        if ($calculatedValue == 0) continue;
        
        $resources = $this->getAbacusResources($abProj, $abDef);
        $workType = $abDef->assignmentWorkType;
        
        foreach ($resources as $idResource) {
          if (!isset($values[$phase->id])) $values[$phase->id] = array();
          if (!isset($values[$phase->id][$idResource])) $values[$phase->id][$idResource] = array();
          if (!isset($values[$phase->id][$idResource][$roleKey])) {
            $values[$phase->id][$idResource][$roleKey] = array('abacusLines' => array(), 'idRole' => $idRole);
          }
          
          if ($workType == 'fixed') {
            if (!isset($values[$phase->id][$idResource][$roleKey]['fixed'])) {
              $values[$phase->id][$idResource][$roleKey]['fixed'] = 0;
            }
            $values[$phase->id][$idResource][$roleKey]['fixed'] += $calculatedValue;
          } else {
            if (!isset($values[$phase->id][$idResource][$roleKey]['proportional'])) {
              $values[$phase->id][$idResource][$roleKey]['proportional'] = 0;
            }
            $values[$phase->id][$idResource][$roleKey]['proportional'] += $calculatedValue;
          }
          
          $values[$phase->id][$idResource][$roleKey]['abacusLines'][] = array(
              'idAbacusProject' => $abProj->id,
              'idAbacusDefinition' => $abDef->id,
              'value' => $calculatedValue,
              'assignmentType' => $workType,
              'capacity' => (isset($abProj->capacity) && $abProj->capacity > 0) ? floatval($abProj->capacity) : null,
              'idRole' => $idRole,
          );
        }
      }
    }
    
    return $values;
  }
  
  /**
   * Retrieves abacus phases
   * @param AbacusDefinition $abDef
   * @return array List of phases
   */
  private function getAbacusPhases($abDef) {
    if (!$abDef->idPhasing) return array();
    $phase = new Phase();
    return $phase->getSqlElementsFromCriteria(array('idPhasing' => $abDef->idPhasing, 'idle' => '0'),false, null,'sortOrder ASC');
  }
  
  /**
   * Retrieves the abacus line corresponding to a project line
   * @param AbacusProject $abProj
   * @return AbacusLine|null
   */
  private function getAbacusLineFromProject($abProj) {
    $abLine = new AbacusLine();
    $criteria = array('idAbacusDefinition' => $abProj->idAbacusDefinition);
    $abDef = new AbacusDefinition($abProj->idAbacusDefinition, true);
    for ($i = 1; $i <= 5; $i++) {
      $idField = 'idClassName' . $i;
      $classField = 'className' . $i;
      $idAbacusableField = 'idAbacusable' . $i;
      if ($abDef->$classField == 'Resource')  continue;
      if ($abDef->$idAbacusableField) {
        $abacusable = new Abacusable($abDef->$idAbacusableField);
        if ($abacusable->valueField == 1 && $abacusable->inputField == 0) {
          continue;
        }
      }
      if ($abProj->$idField) {
        $criteria[$idField] = $abProj->$idField;
      }
    }
    $lines = $abLine->getSqlElementsFromCriteria($criteria);
    return (count($lines) > 0) ? $lines[0] : null;
  }
  
  /**
   * Retrieves the phase value for an abacus line
   * @param int $idAbacusLine
   * @param int $idPhase
   * @return float
   */
  private function getAbacusPhaseValue($idAbacusLine, $idPhase) {
    $abValue = new AbacusValue();
    $values = $abValue->getSqlElementsFromCriteria(array('idAbacusLine' => $idAbacusLine, 'idPhase' => $idPhase));
    if (count($values) > 0) return floatval($values[0]->value);
    return 0;
  }
  
  /**
   * Retrieves project phases
   * @return array List of phases
   */
  private function getProjectPhases() {
    if (!$this->idPhasing) return array();
    $phase = new Phase();
    return $phase->getSqlElementsFromCriteria(array('idPhasing' => $this->idPhasing, 'idle' => '0'),false,null,'sortOrder ASC');
  }
  
  /**
   * Retrieves the product of "by value" columns
   * @param AbacusProject $abProj
   * @param AbacusDefinition $abDef
   * @return float
   */
  private function getAbacusValueFieldsProduct($abProj, $abDef) {
    $product = 1;
    for ($i = 1; $i <= 5; $i++) {
      $classField = 'className' . $i;
      $idAbacusableField = 'idAbacusable' . $i;
      $idField = 'idClassName' . $i;
      
      if ($abDef->$classField && $abDef->$idAbacusableField) {
        $abacusable = new Abacusable($abDef->$idAbacusableField, true);
        if ($abacusable->valueField == 1 || $abacusable->inputField == 1) {
          $referencedId = $abProj->$idField;
          if ($referencedId) {
            $referencedClass = $abDef->$classField;
            $obj = new $referencedClass($referencedId, true);
            if (property_exists($obj, 'value')) {
              $value = floatval($obj->value);
              if ($value != 0) {
                $product *= $value;
              }
            }
          }
        }
      }
    }
    
    return $product;
  }
  
  /**
   * Retrieves resources concerned by the abacus line
   * @param AbacusProject $abProj
   * @param AbacusDefinition $abDef
   * @return array List of idAffectable
   */
  private function getAbacusResources($abProj, $abDef) {
    $resources = array();
    
    for ($i = 1; $i <= 5; $i++) {
      $classField = 'className' . $i;
      $idAbacusableField = 'idAbacusable' . $i;
      $idField = 'idClassName' . $i;
      
      if ($abDef->$classField && $abDef->$idAbacusableField) {
        $className = $abDef->$classField;
        if ($className == 'Resource') {
          if ($abProj->$idField) $resources[] = $abProj->$idField;
        }
        // ResourceOrTeam = resource OR pool
        else if ($className == 'ResourceOrTeam') {
          if ($abProj->idClassNameRef) {
            $resources[] = $abProj->idClassNameRef;
          } else if ($abProj->$idField) {
            $resources[] = $abProj->$idField;
          }
        }
        // ResourceFromTeam = always a resource
        else if ($className == 'ResourceFromTeam') {
          if ($abProj->idClassNameRef) {
            $resources[] = $abProj->idClassNameRef;
          }
        }
        // ResourceTeam = pool
        else if ($className == 'ResourceTeam' || $className == 'Team') {
          if ($abProj->$idField) {
            $resources[] = $abProj->$idField;
          }
        }
      }
    }
    return array_unique($resources);
  }
  
  /**
   * Retrieves the role defined in the abacus line, if any
   * @param AbacusLine $abLine
   * @param AbacusDefinition $abDef
   * @return int|null idRole or null if not defined
   */
  private function getAbacusRole($abLine, $abDef) {
    for ($i = 1; $i <= 5; $i++) {
      $classField = 'className' . $i;
      $idField = 'idClassName' . $i;
      if ($abDef->$classField === 'Role') {
        return ($abLine->$idField) ? intval($abLine->$idField) : null;
      }
    }
    return null;
  }
  
  /**
   * Purges assignments created by abacuses
   * @return int Number of deleted assignments
   */
  private function purgeAbacusAssignments() {
    $count = 0;
    $apa = new AbacusProjectAssignment();
    $apaList = $apa->getSqlElementsFromCriteria(array('idProject' => $this->id));
    $assignmentIds = array();
    foreach ($apaList as $item) {
      if ($item->idAssignment && !in_array($item->idAssignment, $assignmentIds)) {
        $assignmentIds[] = $item->idAssignment;
      }
    }
    
    $protectedAssignmentIds = array(); // For Activity handled = 1;
    
    foreach ($assignmentIds as $idAssignment) {
      $assignment = new Assignment($idAssignment);
      if (!$assignment->id) continue;
      
      if ($assignment->refType == 'Activity' && $assignment->refId) {
        $activity = new Activity($assignment->refId, true);
        if ($activity->id && $activity->handled == 1) {
          $protectedAssignmentIds[$idAssignment] = true;
          continue;
        }
      }
      
      $delResult = $assignment->delete();
      if ($delResult && stripos($delResult, 'id="lastOperationStatus" value="OK"') === false) {
        $count++;
      }
    }
    
    foreach ($apaList as $item) {
      if (isset($protectedAssignmentIds[$item->idAssignment])) continue;    
      $item->delete();
    }
    
    return $count;
  }
  
  /**
   * Creates assignments for a phase and a resource
   * @param int $idPhase
   * @param int $idAffectable
   * @param array $resourceData
   * @param array &$errors Array of errors (passed by reference)
   * @return int Number of created assignments
   */
  private function createAssignmentsForPhaseAndResource($idPhase, $idAffectable, $resourceData, &$errors, &$warnings) {
    $count = 0;
       
    $activities = $this->getActivitiesForPhase($idPhase);
    if (count($activities) == 0) {
      $phaseName = ($idPhase) ? SqlList::getNameFromId('Phase', $idPhase) : i18n('noPhase');
      $warnings[] = i18n('noActivityFoundForPhase', array($phaseName));
      return 0;
    }
    
    $assignmentSlots = [];
    if (isset($resourceData['fixed']) && $resourceData['fixed'] > 0) {
      $assignmentSlots[] = [
          'type' => 'fixed',
          'value' => $resourceData['fixed'],
          'abacusLines' => array_values(array_filter($resourceData['abacusLines'], function($l) { return $l['assignmentType'] === 'fixed'; })),
          ];
    }
    if (isset($resourceData['proportional']) && $resourceData['proportional'] > 0) {
      $assignmentSlots[] = [
          'type' => 'proportional',
          'value' => $resourceData['proportional'],
          'abacusLines' => array_values(array_filter($resourceData['abacusLines'], function($l) { return $l['assignmentType'] === 'proportional'; })),
          ];
    }
    
    if (empty($assignmentSlots)) return 0;
       
    foreach ($assignmentSlots as &$slot) {
      $minCapacity = null;
      foreach ($slot['abacusLines'] as $line) {
        if ($line['capacity'] !== null) {
          if ($minCapacity === null || $line['capacity'] < $minCapacity) {
            $minCapacity = $line['capacity'];
          }
        }
      }
      $slot['capacity'] = $minCapacity;
      $slot['idRole'] = $resourceData['idRole'];
    }
    unset($slot);
    
    foreach ($activities as $activity) {

      foreach ($assignmentSlots as $slot) {
        $assignment = new Assignment();
        $assignment->refType = 'Activity';
        $assignment->refId = $activity->id;
        $assignment->idProject = $this->id;
        $assignment->idResource = $idAffectable;
        
        if ($slot['idRole']) {
          $assignment->idRole = $slot['idRole'];
        }
        
        if ($slot['type'] === 'fixed') {
          $assignment->assignedWork = $slot['value'];
          $assignment->realWork = 0;
          $assignment->leftWork = $slot['value'];
        } else {
          $pe = SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType' => 'Activity', 'refId' => $activity->id));
          if (!$pe || !PlanningMode::isProportionable($pe->idPlanningMode)) {
            $phaseName = ($idPhase) ? SqlList::getNameFromId('Phase', $idPhase) : i18n('noPhase');
            $errors[] = i18n('planningModeNotProportional') . ' : ' . $activity->name . ' (' . $phaseName . ')';
            continue;
          }
          $rate = min($slot['value'] * 100, 100);
          $assignment->rate = $rate;
          $assignment->proportional = 1;
          $duration = 0;
          if ($pe->validatedDuration) $duration = floatval($pe->validatedDuration);
          if ($pe->plannedDuration && $pe->plannedDuration > 0) $duration = floatval($pe->plannedDuration);
          $assignedWork = round($duration * ($rate / 100), 2);
          $assignment->assignedWork = $assignedWork;
          $assignment->realWork = 0;
          $assignment->leftWork = $assignedWork;

        }
        
        $resource = new ResourceAll($assignment->idResource);
        if ($resource->isResourceTeam) {
          $assignment->capacity = 1;
          $periods = ResourceTeamAffectation::buildResourcePeriods($idAffectable);
          $today = date('Y-m-d');
          $maxCapacity = 1;
          foreach ($periods as $p) {
            if ($p['end'] > $today && $maxCapacity < $p['rate']) {
              $maxCapacity = $p['rate'];
            }
          }
          if (!$assignment->proportional) {
            $rate = ($assignment->capacity / $maxCapacity) * 100;
            if ($rate > 100) $rate = 100;
            $assignment->rate = $rate;
          }
        }
        
        $assignment->_origin = 'abacus';
        if ($slot['capacity'] !== null) {
          $assignment->capacity = $slot['capacity'];
        }
        
        $saveResult = $assignment->save();
        $saveOk = stripos($saveResult, 'id="lastOperationStatus" value="OK"') !== false || stripos($saveResult, 'id="lastOperationStatus" value="NO_CHANGE"') !== false;
        
        if ($saveOk) {
          $count++;
          $assignmentId = $assignment->id;
          foreach ($slot['abacusLines'] as $abacusLine) {
            $apa = new AbacusProjectAssignment();
            $apa->idAbacusProject = $abacusLine['idAbacusProject'];
            $apa->idAssignment = $assignmentId;
            $apa->idAbacusDefinition = $abacusLine['idAbacusDefinition'];
            $apa->idAffectable = $idAffectable;
            $apa->idProject = $this->id;
            $apa->refType = 'Activity';
            $apa->refId = $activity->id;
            $apa->value = $abacusLine['value'];
            $apaResult = $apa->save();
            $apaOk = stripos($apaResult, 'id="lastOperationStatus" value="OK"') !== false || stripos($apaResult, 'id="lastOperationStatus" value="NO_CHANGE"') !== false;

            if (!$apaOk) {
              $resourceName = SqlList::getNameFromId('Affectable', $idAffectable);
              $phaseName = ($idPhase) ? SqlList::getNameFromId('Phase', $idPhase) : i18n('noPhase');
              $errors[] = i18n('errorCreatingAbacusLink', array($resourceName, $activity->name, $phaseName));
            }
          }
        } else {
          $resourceName = SqlList::getNameFromId('Affectable', $idAffectable);
          $phaseName = ($idPhase) ? SqlList::getNameFromId('Phase', $idPhase) : i18n('noPhase');
          $errors[] = i18n('errorCreatingAssignment', array($resourceName, $activity->name, $phaseName)) . ' - ' . strip_tags($saveResult);
        }
      }
    }
    
    return $count;
  }
  
  /**
   * Retrieves non-started activities for a phase
   * @param int $idPhase
   * @return array List of activities
   */
  private function getActivitiesForPhase($idPhase) {
    $activity = new Activity();
    $critWhere = "idProject = " . Sql::fmtId($this->id);
    if ($idPhase) {
      $critWhere .= " AND idPhase = " . Sql::fmtId($idPhase);
    } else {
      $critWhere .= " AND (idPhase IS NULL OR idPhase = 0)";
    }
    $critWhere .= " AND idle = 0 AND handled = 0";
    $activities = $activity->getSqlElementsFromCriteria(null, false, $critWhere);
    return $activities;
  }
  
  
  /**
   * Automatically assigns all resources used in the project's abacuses
   * @return string Result message
   */
  public function affectAbacusResourcesToProject() {
    $result = '';
    $returnStatus = 'OK';
    $allResources = $this->getAbacusResourcesList();
    
    if (count($allResources) == 0) {
      $result = '<div class="NO_CHANGE">' . i18n('noAbacusResourcesToAffect') . '</div>';
      $result .= '<input type="hidden" id="lastOperationStatus" value="NO_CHANGE" />';
      $result .= '<input type="hidden" id="lastOperation" value="affectResources" />';
      return $result;
    }
    
    $affectation = new Affectation();
    $existingAffectations = $affectation->getSqlElementsFromCriteria(array('idProject' => $this->id, 'idle' => '0'));
    $existingResourceIds = array();
    foreach ($existingAffectations as $aff) {
      if ($aff->idResource) {
        $existingResourceIds[] = $aff->idResource;
      }
    }
    
    $affectedCount = 0;
    $alreadyAffectedCount = 0;
    $errors = array();
    foreach ($allResources as $idResource) {
      if (in_array($idResource, $existingResourceIds)) {
        $alreadyAffectedCount++;
        continue;
      }
      
      $resource = new Affectable($idResource, true);
      if (!$resource->id) {
        $errors[] = i18n('errorResourceNotFound', array($idResource)) ;
        continue;
      }
      
      $newAffectation = new Affectation();
      $newAffectation->idProject = $this->id;
      $newAffectation->idResource = $idResource;
      
      if (property_exists($resource, 'idProfile') && $resource->idProfile) {
        $newAffectation->idProfile = $resource->idProfile;
      }
      
      $newAffectation->rate = 100;
      $newAffectation->idle = 0;
      
      $saveResult = $newAffectation->save();
      if (stripos($saveResult, 'id="lastOperationStatus" value="OK"') !== false || stripos($saveResult, 'id="lastOperationStatus" value="NO_CHANGE"') !== false) {
        $affectedCount++;
      } else {
        $resourceName = SqlList::getNameFromId('Affectable', $idResource);
        $errors[] = i18n('errorAffectingResource', array($resourceName)) . ' - ' . strip_tags($saveResult);
      }
    }
    
    if (count($errors) > 0) {
      $returnStatus = 'ERROR';
      $result .= i18n('resourcesAffectedWithErrors',  array( $affectedCount, $alreadyAffectedCount));
    } else if ($affectedCount == 0) {
      if ($alreadyAffectedCount > 0) {
        $returnStatus = 'NO_CHANGE';
        $result .= i18n('allResourcesAlreadyAffected');
      } else {
        $returnStatus = 'NO_CHANGE';
        $result = '<div class="messageWARNING">' . i18n('noResourcesAffected') . '</div>';
      }
    } else {
      $returnStatus = 'OK';
      $result .= i18n('resourcesAffectedSuccessfully',  array($affectedCount, $alreadyAffectedCount));
    }
    
    $result .= '<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    $result .= '<input type="hidden" id="lastOperation" value="affectResources" />';
    $result .= '<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
    
    return $result;
  }
  
  /**
   * Retrieves the list of all resources used in the project's abacuses
   * @return array Unique list of idResource
   */
  private function getAbacusResourcesList() {
    $allResources = array();
    $abacusProj = new AbacusProject();
    $abacusProjectList = $abacusProj->getSqlElementsFromCriteria(array('idProject' => $this->id, 'idle' => '0'));
    foreach ($abacusProjectList as $abProj) {
      $abDef = new AbacusDefinition($abProj->idAbacusDefinition, true);
      if (!$abDef->id || $abDef->idle == 1) continue;
      $resources = $this->getAbacusResources($abProj, $abDef);
      $allResources = array_merge($allResources, $resources);
    }
    return array_unique($allResources);
  }
}
?>
