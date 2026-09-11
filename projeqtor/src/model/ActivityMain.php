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
 * Action is establised during meeting, to define an action to be followed.
 */
require_once ('_securityCheck.php');
class ActivityMain extends SqlElement {
  
  // List of fields that will be exposed in general user interface
  public $_sec_description;
  public $id; // redefine $id to specify its visible place
  public $reference;
  public $name;
  public $tags;
  public $idProject;
  public $idActivityType;
  public $externalReference;
  public $creationDate;
  public $lastUpdateDateTime;
  public $idUser;
  public $idContact;
  public $Origin;
  public $description;
  public $_sec_treatment;
  public $idActivity;
  public $idStatus;
  public $idResource;
  public $idMilestone;
  public $fixPlanning;
  public $_lib_helpFixPlanning;
  public $paused;
  public $_lib_helpPaused;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $result;
  public $_sec_Assignment;
  public $_spe_showClosedAssignment;
  public $_spe_purgeAssignment;
  public $_spe_resetAssignment;
  public $_Assignment = array();
  public $_sec_Progress;
  public $ActivityPlanningElement; // is an object
  public $isPlanningActivity;
  public $_lib_isPlanningActivity;
  public $workOnRealTime;
  public $_sec_Abacus;
  public $_spe_abacus;
  public $idPhase;
  public $_sec_productComponent;
  public $idProduct;
  public $idComponent;
  public $idTargetProductVersion;
  public $idTargetComponentVersion;
  public $_sec_predecessor;
  public $_Dependency_Predecessor = array();
  public $_sec_successor;
  public $_Dependency_Successor = array();
  public $_sec_subActivity;
  public $_spe_activity;
  public $_spe_isLeaveMngActivity;
  public $_sec_ToDoList;
  public $_SubTask;
  public $_sec_vote;
  public $VotingItem; //is an object
  public $_sec_ActivitySkill;
  public $_spe_activitySkill;
  public $_ActivitySkill = array();
  public $_sec_Link;
  public $_Link = array();
  public $_Attachment = array();
  public $_Note = array();
  public $_nbColMax = 3;
  
  private static $_subTasksList=array();
  private static $_cacheColor=array();
  
  // Define the layout that will be used for lists
  private static $_layout = '
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="10%" >${idProject}</th>
    <th field="nameActivityType" width="10%" >${idActivityType}</th>
    <th field="name" width="25%" >${name}</th>
    <th field="plannedEndDate" from="ActivityPlanningElement" width="10%" formatter="dateFormatter">${plannedEndDate}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>
    <th field="progress" from="ActivityPlanningElement" width="10%" formatter="percentFormatter">${progress}</th>
    <th field="nameResource" formatter="thumbName22" width="15%" >${responsible}</th>
    ';
  
  private static $_fieldsTooltip = array(
      "fixPlanning"=> "tooltipFixPlanningActivity",
      "paused"=>"tooltipPausedActivity",
      "isPlanningActivity"=>"titleIsPlanningActivity",
      "workOnRealTime"=>"tooltipWorkOnRealTime"
  );
  
  private static $_fieldsAttributes = array(
      "id" => "nobr", 
      "reference" => "readonly", 
      "name" => "required", 
      "idProject" => "required", 
      "idActivityType" => "required", 
      "idStatus" => "required", 
      "creationDate" => "required", 
      "fixPlanning"=>"nobr,noExport",
      "handled" => "nobr", 
      "done" => "nobr", 
      "idle" => "nobr", 
      "idleDate" => "nobr", 
      "cancelled" => "nobr",
      "isPlanningActivity" => "title,nobr",
      "_spe_isLeaveMngActivity" => "hidden",
      "paused"=>"nobr",
      "_ActivitySkill"=>'hidden',
  );
  private static $_colCaptionTransposition = array(
      'idUser' => 'issuer', 
      'idResource' => 'responsible', 
      'idActivity' => 'parentActivity', 
      'idContact' => 'requestor', 
      'isPlanningActivity' => 'PlanningActivity'
  );
  
  // private static $_databaseColumnName = array('idResource'=>'idUser');
  private static $_databaseColumnName = array(
      'idTargetProductVersion' => 'idVersion', 
      'idTargetComponentVersion' => 'idComponentVersion');
  
  /**
   * ==========================================================================
   * Constructor
   * 
   * @param $id Int the
   *          id of the object in the database (null if not stored yet)
   * @return void
   */
  function __construct($id = NULL, $withoutDependentObjects = false) {
    parent::__construct ( $id, $withoutDependentObjects );
    if ($withoutDependentObjects)
      return;
    if (Parameter::getGlobalParameter ( 'limitPlanningActivity' ) != "YES") {
      self::$_fieldsAttributes ['isPlanningActivity'] = 'hidden';
    }
    
// MTY - LEAVE SYSTEM
    // If it's an Leave activity (ie : Activity.idProject is the project Leave, id isLeaveSystemProject=1),
    // can't modify a lot of attributes
    $leaveProjectId = Project::getLeaveProjectId();
    if ($leaveProjectId==$this->idProject && $leaveProjectId!=null) {
      self::$_fieldsAttributes ['idActivity'] = 'hidden';
      self::$_fieldsAttributes ['idProject'] = 'readonly';
      self::$_fieldsAttributes ['idActivityType'] = 'hidden';
      self::$_fieldsAttributes ['idStatus'] = 'hidden';
      self::$_fieldsAttributes ['handled'] = 'hidden';
      self::$_fieldsAttributes ['handledDate'] = 'hidden';
      self::$_fieldsAttributes ['idle'] = 'hidden';
      self::$_fieldsAttributes ['idleDate'] = 'hidden';
      self::$_fieldsAttributes ['done'] = 'hidden';
      self::$_fieldsAttributes ['doneDate'] = 'hidden';
      self::$_fieldsAttributes ['cancelled'] = 'hidden';
      self::$_fieldsAttributes ['idResource'] = 'hidden';
      self::$_fieldsAttributes ['idContact'] = 'hidden';
      self::$_fieldsAttributes ['result'] = 'hidden';
      self::$_fieldsAttributes['ActivityPlanningElement'] = 'hidden';
      self::$_fieldsAttributes['isPlanningActivity'] = 'hidden';
      self::$_fieldsAttributes['idProduct'] = 'hidden';
      self::$_fieldsAttributes['idComponent'] = 'hidden';
      self::$_fieldsAttributes['idTargetProductVersion'] = 'hidden';
      self::$_fieldsAttributes['idTargetComponentVersion'] = 'hidden';
      self::$_fieldsAttributes['Origin'] = 'hidden';
      unset($this->_sec_Progress);
      unset($this->sec_productComponent);
      unset($this->_sec_treatment);
      unset($this->_sec_Assignment);      
      unset($this->_Assignment);
      unset($this->_sec_productComponent);
      unset($this->_sec_predecessor);
      unset($this->_Dependency_Predecessor);
      unset($this->_sec_successor);
      unset($this->_Dependency_Successor);
  }
  
// MTY - LEAVE SYSTEM
  }
  
  /**
   * ==========================================================================
   * Destructor
   * 
   * @return void
   */
  function __destruct() {
    parent::__destruct ();
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
  
  /**
   * ==========================================================================
   * Return the specific fieldsAttributes
   * 
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  /**
   * ============================================================================
   * Return the specific colCaptionTransposition
   * 
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld = null) {
    return self::$_colCaptionTransposition;
  }
  
  /**
   * ========================================================================
   * Return the specific databaseColumnName
   * 
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }
  
// MTY - LEAVE SYSTEM  
// =============================================================================================================
// DRAWING FUNCTION
// =============================================================================================================

  /** =========================================================================
   * Draw a specific item for the current class.
   * @param String $item the item. 
   * @return String an html string able to display a specific item
   *  must be redefined in the inherited class
   */
  public function drawSpecificItem($item,$readOnly=false,$refresh=false){
    global $print, $comboDetail;
    $result='';
      if ($item=='isLeaveMngActivity') {
          if (isLeavesSystemActiv()) {
            $leaveProject = (Project::isTheLeaveProject($this->idProject)?1:0);
            echo '<input type="hidden" name="isLeaveMngActivity" id="isLeaveMngActivity" value='.$leaveProject.' />';
          } else { echo '';}
      }else if ($item=='activitySkill'){
        $activitySkill = new ActivitySkill();
        $critArray=array('idActivity'=>(($this->id)?$this->id:'0'));
        $activitySkillList=$activitySkill->getSqlElementsFromCriteria($critArray, false,null);
        drawActivitySkillList($activitySkillList, $this);
      }else if (!$print and $item=='showClosedAssignment'){
        $showClosed=(Parameter::getUserParameter($item)=='1' or Parameter::getUserParameter($item)=='')?true:false;
        $result.='<div style="position:absolute;right:60px;top:3px;">';
        $result.='<label for="'.$item.'" class="dijitTitlePaneTitle" style="border:0;font-weight:normal !important;height:'.((isNewGui())?'20':'10').'px;width:'.((isNewGui())?'50':'150').'px">'.i18n('labelShowIdle'.((isNewGui())?'Short':'')).'</label>';
        if($this->idle == 1){
          $result.=' <div id="'.$item.'" style="'.((isNewGui())?'margin-top:14px':'').'" dojoType="dijit.form.CheckBox" type="checkbox" '.('checked').' readonly';
          $result.=' title="'.i18n('labelShowIdle').'" >';
        }else{
          $result.=' <div id="'.$item.'" style="'.((isNewGui())?'margin-top:14px':'').'" dojoType="dijit.form.CheckBox" type="checkbox" '.(($showClosed)?'checked':'');
          $result.=' title="'.i18n('labelShowIdle').'" >';
          $result.=' <script type="dojo/connect" event="onChange" args="evt">';
          //$result.=' saveUserParameter("'.$item.'",((this.checked)?"1":"0"));';
          //$result.=' if (checkFormChangeInProgress()) {return false;}';
          //$result.=' loadContent("objectDetail.php", "detailDiv", "listForm");';
          $result.=' var callBack=null;';
          $result.=' if (! checkFormChangeInProgress()) callBack=function(){loadContent("objectDetail.php", "detailDiv", "listForm");};';
          $result.=' saveDataToSession("'.$item.'",((this.checked)?"1":"0"),true,callBack);';
          $result.=' </script>';
        }
        $result.='</div>';
        $result.='</div>';
        return $result;
      }else if (!$print and $item=='purgeAssignment' and !$comboDetail){
        $result.='<div style="position:absolute;right:30px;top:45px;">';
        if($this->idle != 1){
          $result .='<a id="'.$item.'" onClick="purgeAssignmentTable()" title="'.i18n('helpPurgeAssignment', array(i18n('colActivity'), $this->id)).'">'.formatMediumButton('Purge').'</a>';
        }
        $result.='</div>';
        return $result;
      }else if (!$print and $item=='resetAssignment' and !$comboDetail){
        $result.='<div style="position:absolute;right:0px;top:45px;">';
        if($this->idle != 1){
          $result .='<a id="'.$item.'" onClick="resetAssignmentTable()" title="'.i18n('helpResetAssignment', array(i18n('colActivity'), $this->id)).'">'.formatMediumButton('Reset').'</a>';
        }
        $result.='</div>';
        return $result;
      }
  }
// MTY - LEAVE SYSTEM  
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /**
   * ==========================================================================
   * Return the validation sript for some fields
   * 
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript ( $colName );
    
    if ($colName == "idProject") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  dojo.byId("ActivityPlanningElement_wbs").value=""; ';
      $colScript .= '  dojo.byId("idActivity").value=""; ';
      //$colScript .= '  if (document.getElementsByName("idActivity") && document.getElementsByName("idActivity")[0]) document.getElementsByName("idActivity")[0].value=""; ';
      $colScript .= '  if (dijit.byId("idActivity")) {dijit.byId("idActivity").set("value",null);} ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName == "idActivity") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  dojo.byId("ActivityPlanningElement_wbs").value=""; ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
      
    } else if ($colName == "idActivityType") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  setDefaultPlanningMode(this.value);';
      $colScript .= '  setDefaultPriority(this.value);';
      $colScript .= '</script>';
    } else if ($colName == "fixPlanning") {
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' dijit.byId("ActivityPlanningElement_fixPlanning").set("value",dijit.byId("fixPlanning").get("value"));';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
      }
    }else if($colName=="paused"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(this.checked){';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",true);';
      $colScript .= '   dijit.byId("fixPlanning").set("checked",true);';
      $colScript .= '   dijit.byId("fixPlanning").set("value",1);';
      $colScript .= ' dijit.byId("ActivityPlanningElement_paused").set("checked",true);';
      $colScript .= ' dijit.byId("ActivityPlanningElement_paused").set("value",1);';
      $colScript .= ' dijit.byId("ActivityPlanningElement_fixPlanning").set("readOnly",true);';
      $colScript .= '  }else{';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",false);';
      $colScript .= '   dijit.byId("fixPlanning").set("checked",false);';
      $colScript .= '   dijit.byId("fixPlanning").set("value",0);';
      $colScript .= ' dijit.byId("ActivityPlanningElement_fixPlanning").set("readOnly",false);';
      $colScript .= '  }';
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
          $colScript .= ' dijit.byId("ActivityPlanningElement_paused").set("value",dijit.byId("paused").get("value"));';
          $colScript .= '  formChanged();';
      }
      $colScript .= '</script>';
    }else if($colName=="workOnRealTime"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(this.checked){';
      $colScript .= '   if(!dojo.byId("hiddenFielsActivityWork")){';
      $colScript .= '     dijit.byId("ActivityPlanningElement_validatedWork").set("value",dijit.byId("ActivityPlanningElement_plannedWork").get("value"));';
      $colScript .= '     dijit.byId("ActivityPlanningElement_validatedWork").set("disabled",true);';
      $colScript .= '   }';
      $colScript .= '   if(!dojo.byId("hiddenFielsActivityCost")){';
      $colScript .= '     dijit.byId("ActivityPlanningElement_validatedCost").set("disabled",true);';
      $colScript .= '   }';
      $colScript .= '   if(dojo.byId("tabActivityWorkUnit"))dojo.byId("tabActivityWorkUnit").parentNode.style.display="none"';
      $colScript .= '  }else{';
      $colScript .= '   if(!dojo.byId("hiddenFielsActivityWork")){';
      $colScript .= '     dijit.byId("ActivityPlanningElement_validatedWork").set("disabled",false);';
      $colScript .= '     dijit.byId("ActivityPlanningElement_validatedWork").set("readOnly",false);';
      $colScript .= '   }';
      $colScript .= '   if(!dojo.byId("hiddenFielsActivityCost")){';
      $colScript .= '     dijit.byId("ActivityPlanningElement_validatedCost").set("disabled",false);';
      $colScript .= '     dijit.byId("ActivityPlanningElement_validatedCost").set("readOnly",false);';
      $colScript .= '   }';
      $colScript .= '   if(dojo.byId("tabActivityWorkUnit"))dojo.byId("tabActivityWorkUnit").parentNode.style.display="table-cell"';
      $colScript .= '  }';
      $colScript .= '   formChanged();';
      $colScript .= '</script>';
    } 
    return $colScript;
  }
  
  /**
   * =========================================================================
   * control data corresponding to Model constraints
   * 
   * @param
   *          void
   * @return "OK" if controls are good or an error message
   *         must be redefined in the inherited class
   */
  public function control() {
    $result = "";
    $old = $this->getOld(false);
    
    //Gautier #4304
    $proj = new Project($this->idProject,true);
    $projType = new ProjectType($proj->idProjectType);
    if($projType->isLeadProject){
      if (!$this->id) {
        $result .= '<br/>' . i18n ( 'cantCreateAnActivityFromLeadProject' );
      }
      if ($this->id && $old->idProject != $this->idProject) {
        //      ==> Can't associated the activity with the project dedicated to the leave
          $result .= '<br/>' . i18n ( 'cantAssociateAnActivityWithLeadProject' );
      }
    }
    // default duration
    $pmName='idActivityPlanningMode';
    if (! $this->ActivityPlanningElement->validatedDuration and PlanningMode::isFixedDuration($this->ActivityPlanningElement->$pmName)) {
      $type=new ActivityType($this->idActivityType);
      if ($type->defaultDuration) $this->ActivityPlanningElement->validatedDuration=$type->defaultDuration;
    }
    
    //Gautier #2505
    if ($this->id && $old->idProject != $this->idProject) {
      $ass = new Assignment();
      $lstAss = $ass->getSqlElementsFromCriteria(array('refType'=>'Activity','refId'=>$this->id,'idle'=>'0'));
      $proj = new Project($this->idProject,true);
      $topProject = $proj->getTopProjectList(true);
      foreach ( $lstAss as $as){
        if($as->isMaterial)continue;
        $aff = new Affectation();
        $where = " idResource = ".$as->idResource." and idProject in " . transformValueListIntoInClause($topProject);
        $affExist = $aff->countSqlElementsFromCriteria(null,$where);
        if($affExist==0){
          $result .= '<br/>' . i18n ( 'cantMoveActivityWithoutAffectedResource', array($as->idResource,SqlList::getNameFromId('Affectable',$as->idResource)) );
          break;
        }
      }
    }
    
    if($this->idActivity){
      $actParent = new Activity($this->idActivity);
      if($actParent->ActivityPlanningElement->hasWorkUnit){
        $result .= '<br/>' . i18n ( 'cantHaveParentWithWorkUnit' );
      }
    }
    if ($this->id and $this->idActivityType != $old->idActivityType and $this->ActivityPlanningElement and ! $this->ActivityPlanningElement->elementary) {
      // Activity is parent => cannot change type to type that does not allow sub-items
      $type=new ActivityType($this->idActivityType);
      if(! $type->canHaveSubActivity){
        $result='<br/>' . i18n('cantHaveSubActivity');
        return $result;
      }
    }
    
// MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
        // Can't create or associate an activity on the project that is dedicated to the leave
        $leaveProjectId = Project::getLeaveProjectId();
        // At creation
        //      => Can't create an activity associated with the project dedicated to the leave
        if (! $this->id && $leaveProjectId == $this->idProject) {
          $result .= '<br/>' . i18n ( 'cantCreateAnActivityFromProjectLeave' );        
        }
        // At Update project
        if ($this->id!=null && $old->idProject != $this->idProject) {
            //      ==> Can't associated the activity with the project dedicated to the leave
            if ($this->idProject == $leaveProjectId) {
              $result .= '<br/>' . i18n ( 'cantAssociateAnActivityWithProjectLeave' );
            }
            //      ==> Can't change project if project is the leaveProject
            if ($old->idProject == $leaveProjectId) {
              $result .= '<br/>' . i18n ( 'cantChangeProjectOfActivityAssociatedWithProjectLeave' );
            }
        }

        // At Update type
        if ($this->id!=null && $old->idActivityType != $this->idActivityType) {
            //      ==> Can't change the type of an activity associated with the project dedicated to the leave
            if ($this->idProject == $leaveProjectId) {
              $result .= '<br/>' . i18n ( 'cantChangeTypeOnActivityAssociatedWithProjectLeave' );
            }
        }

        // At Update Parent Activity
        if ($this->id!=null && $old->idActivity != $this->idActivity) {
            //      ==> Can't change the Parent Activity of an activity associated with the project dedicated to the leave
            if ($this->idProject == $leaveProjectId) {
              $result .= '<br/>' . i18n ( 'cantChangeActivityParentOnActivityAssociatedWithProjectLeave' );
            }
        }

        // At Update Status
        if ($this->id!=null && $old->idStatus != $this->idStatus) {
            //      ==> Can't change the Status of an activity associated with the project dedicated to the leave
            if ($this->idProject == $leaveProjectId) {
              $result .= '<br/>' . i18n ( 'cantChangeStatusOnActivityAssociatedWithProjectLeave' );
            }
        }
    }
    
// MTY - LEAVE SYSTEM
    
    if ($this->id and $this->id == $this->idActivity) {
      $result .= '<br/>' . i18n ( 'errorHierarchicLoop' );
    } else if ($this->ActivityPlanningElement and $this->ActivityPlanningElement->id
      and ($this->idActivity!=$old->idActivity or $this->idProject!=$old->idProject)) {
      if (pq_trim ( $this->idActivity )) {
        $parentType = 'Activity';
        $parentId = $this->idActivity;
      } else {
        $parentType = 'Project';
        $parentId = $this->idProject;
      }
      $result .= $this->ActivityPlanningElement->controlHierarchicLoop ( $parentType, $parentId );
    }
    
    if (pq_trim ( $this->idActivity ) and ! SqlElement::isCopyInProgress()) {
      $parentActivity = new Activity ( $this->idActivity );
      if ($parentActivity->idProject != $this->idProject) {
        $result .= '<br/>' . i18n ( 'msgParentActivityInSameProject' );
      }
    }
    
    $oveIncompatiblePhasing = false;
    if ($this->id && property_exists($this, 'idProject') && property_exists($this, 'idPhase')) {
      if ($old->idPhase && $old->idProject != $this->idProject) {
        $oldProject = new Project($old->idProject, true);
        $oldPhasing = $oldProject->idPhasing;
        
        $newProject = new Project($this->idProject, true);
        $newPhasing = $newProject->idPhasing;
        
        if ($newPhasing) {
          if ($oldPhasing != $newPhasing) {
            $result .= '<br/>' . i18n('errorActivityMoveIncompatiblePhasing');
            $oveIncompatiblePhasing = true;
          }
        }
      }
    }

    if (property_exists($this, 'idPhase') && $this->idPhase && property_exists($this, 'idProject') && $this->idProject) {
      $project = new Project($this->idProject, true);     
      if ($project->idPhasing) {
        $phase = new Phase($this->idPhase, true);       
        if ($phase->idPhasing != $project->idPhasing && $oveIncompatiblePhasing == false) {
          $result .= '<br/>' . i18n('errorPhaseNotInProjectPhasing');
        }
      }
    }
    
    $defaultControl = parent::control ();
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    if ($result == "") {
      $result = 'OK';
    }
    if($this->ActivityPlanningElement->minimumThreshold){
      $ass = new Assignment();
      $assList = $ass->getSqlElementsFromCriteria(array('refType'=>'Activity', 'refId'=>$this->id));
      if($assList){
        $res = new ResourceAll($assList[0]->idResource);
        $maxThreshold = $res->capacity*($assList[0]->rate/100);
        foreach ($assList as $assign){
          $res = new ResourceAll($assign->idResource);
        	if($res->capacity*($assign->rate/100) < $maxThreshold){
        	  $maxThreshold = $res->capacity*($assign->rate/100);
        	}
        }
        if(Work::convertWork($this->ActivityPlanningElement->minimumThreshold) > $maxThreshold){
          $workUnit = Parameter::getGlobalParameter('workUnit');
          $dayTime = 1;
          if($workUnit == 'hours'){
            $dayTime = Parameter::getGlobalParameter('dayTime');
          }
          $result=i18n('minimumThresholdInputError',array(($maxThreshold*$dayTime).Work::displayShortWorkUnit()));
        }
      }
    }

    return $result;
  }
  public function startDateActivity($parentVersion = null){
    
    $pe=new planningElement();
    $where = "refType ='Activity' and refId = $this->id";
    
    $pe = $pe->getSqlElementsFromCriteria(null,null,$where);
    if ($pe[0]->realStartDate) {
      $startDate = $pe[0]->realStartDate;
    }
    elseif ($pe[0]->plannedStartDate) {
      $startDate = $pe[0]->plannedStartDate;
    }
    elseif ($pe[0]->initialStartDate) {
      $startDate = $pe[0]->initialStartDate;
    }
    else{
      $startDate = null;
    }
    
    if ($parentVersion != NULL and empty($startDate)) {
      if ($parentVersion->realStartDate) {
        $startDate = $parentVersion->realStartDate;
      }
      elseif ($parentVersion->plannedStartDate) {
        $startDate = $parentVersion->plannedStartDate;
      }
      elseif ($parentVersion->initialStartDate) {
        $startDate = $parentVersion->initialStartDate;
      }
      else {
        $startDate = $parentVersion->myStartDate;
      }
      $this->ownDate = false;
    }
    
    return $startDate;
  }
  
  public function endDateActivity($parentVersion = null){
    
    $pe=new planningElement();
    $where = "refType ='Activity' and refId = $this->id";
    
    $pe = $pe->getSqlElementsFromCriteria(null,null,$where);
    
    if ($pe[0]->realEndDate) {
      $endDate = $pe[0]->realEndDate;
    }
    elseif ($pe[0]->plannedEndDate) {
      $endDate = $pe[0]->plannedEndDate;
    }
    elseif ($pe[0]->initialEndDate) {
      $endDate = $pe[0]->initialEndDate;
    }
    else{
      $endDate = null;
    }
    
    if ($parentVersion != NULL and empty($endDate)) {
      if ($parentVersion->realDeliveryDate) {
        $endDate= $parentVersion->realDeliveryDate;
      }
      elseif ($parentVersion->plannedDeliveryDate) {
        $endDate= $parentVersion->plannedDeliveryDate;
      }
      elseif ($parentVersion->initialDeliveryDate) {
        $endDate= $parentVersion->initialDeliveryDate;
      }
      else {
        $endDate= $parentVersion->myEndDate;
      }
      $this->ownDate = false;
    }
    return $endDate;
  }
  /**
   * =========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * 
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  
  /**
   * =========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * 
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save($onlyProject=false) {
    $oldResource = null;
    $oldIdle = null;
    $oldIdProject = null;
    $oldIdActivity = null;
    $oldTargetProductVersion = null;
    if ($this->id) {
      $old = $this->getOld (false);
      $oldResource = $old->idResource;
      $oldIdle = $old->idle;
      $oldIdProject = $old->idProject;
      $oldIdActivity = $old->idActivity;
      $oldTargetProductVersion = $old->idTargetProductVersion;
      if($this->fixPlanning!=$old->fixPlanning and $this->fixPlanning!=$this->ActivityPlanningElement->fixPlanning){
        $this->ActivityPlanningElement->fixPlanning=$this->fixPlanning;
      }
      if($this->ActivityPlanningElement->fixPlanning!=$old->ActivityPlanningElement->fixPlanning and $this->fixPlanning!=$this->ActivityPlanningElement->fixPlanning){
        $this->fixPlanning=$this->ActivityPlanningElement->fixPlanning;
      }
      if($old->fixPlanning and $old->ActivityPlanningElement->fixPlanning and !$this->ActivityPlanningElement->fixPlanning){
        $this->fixPlanning = 0;
        $this->ActivityPlanningElement->fixPlanning = 0;
      }
      if($old->idStatus != $this->idStatus){
        $status = new Status ($this->idStatus);
        if($status->fixPlanning and !$this->fixPlanning){
          $this->fixPlanning = 1;
          $this->ActivityPlanningElement->fixPlanning = 1;
        }
      }
    }
    // #305 : need to recalculate before dispatching to PE
    $this->recalculateCheckboxes ();
    $this->ActivityPlanningElement->refName = $this->name;
    $this->ActivityPlanningElement->idProject = $this->idProject;
    $this->ActivityPlanningElement->idle = $this->idle;
    $this->ActivityPlanningElement->done = $this->done;
    $this->ActivityPlanningElement->cancelled = $this->cancelled;
    if ($this->idActivity and pq_trim ( $this->idActivity ) != '') {
      $this->ActivityPlanningElement->topRefType = 'Activity';
      $this->ActivityPlanningElement->topRefId = $this->idActivity;
      $this->ActivityPlanningElement->topId = null;
    } else {
      $this->ActivityPlanningElement->topRefType = 'Project';
      $this->ActivityPlanningElement->topRefId = $this->idProject;
      $this->ActivityPlanningElement->topId = null;
    }
    if ( (pq_trim($this->idProject)!=pq_trim($oldIdProject) and !$onlyProject) or pq_trim($this->idActivity)!=pq_trim( $oldIdActivity )) {
      $this->ActivityPlanningElement->wbs = null;
      $this->ActivityPlanningElement->wbsSortable = null;
    }
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
      if (pq_trim($this->idProject)!=pq_trim($oldIdProject)) {
        $project=new Project($this->idProject, true);
        if ($project->paused==1) {
          $this->paused=1;
          $this->fixPlanning=1;
          $this->ActivityPlanningElement->paused=1;
          $this->ActivityPlanningElement->fixPlanning=1;
        } else {
          $this->paused=0;
          $this->fixPlanning=0;
          $this->ActivityPlanningElement->paused=0;
          $this->ActivityPlanningElement->fixPlanning=0;
        }
      }
      if($this->paused!=$old->paused and  $this->ActivityPlanningElement->paused!=$this->paused){
        $this->ActivityPlanningElement->paused=$this->paused;
      }else if( $this->ActivityPlanningElement->paused!=$old->ActivityPlanningElement->paused and $this->ActivityPlanningElement->paused!=$this->paused){
        $this->paused=$this->ActivityPlanningElement->paused;
      }
      if ($this->paused!=$old->paused and $this->paused==1  and  $this->fixPlanning!=$this->paused){
         $this->fixPlanning=1;
        $this->ActivityPlanningElement->fixPlanning=1;
      }
      if($this->idActivityType and $old->idActivityType!=$this->idActivityType){
        $actType= new ActivityType($this->idActivityType);
        if($actType->activityOnRealTime==1){
          $this->workOnRealTime=1;
        }
      }
      if($this->workOnRealTime==1 and $old->workOnRealTime!=$this->workOnRealTime){
        $this->ActivityPlanningElement->validatedWork=$this->ActivityPlanningElement->plannedWork;
      }
    }else {
      if($this->idActivityType){
        $actType= new ActivityType($this->idActivityType);
        if($actType->activityOnRealTime==1){
          $this->workOnRealTime=1;
        }
      }
    }    
    if ($this->id and $this->handled and $this->handledDate and ! $this->ActivityPlanningElement->validatedStartDate) {
      if ( $this->ActivityPlanningElement->realWork==0 and ($this->ActivityPlanningElement->assignedWork>0 or $this->ActivityPlanningElement->leftWork>0) 
      and ($this->ActivityPlanningElement->idPlanningMode==29 or $this->ActivityPlanningElement->idPlanningMode==30)) {
        // Constrained duration, if activity "started" (handledDate set) and no real work entered and has left work, set validatedStartDate isf not set.
        //$this->ActivityPlanningElement->validatedStartDate=$this->handledDate;
        $this->ActivityPlanningElement->inheritedStartDate=$this->handledDate;
      }
    }
    if(Module::isModuleActive('moduleTechnicalProgress')){
      if (Parameter::getGlobalParameter('automaticChangeTechnicalProgress') == 'YES') {
        $old = $this->getOld();
        $pe = 'ActivityPlanningElement';
        if ($old && $old->idStatus != $this->idStatus) {
          $newStatus = new Status($this->idStatus);
          if ($newStatus->setDoneStatus) {
            if($this->$pe->elementary == 1){
              $idModeTechnicalPogressManual = SqlList::getIdFromTranslatableName('ProgressMode', 'manual');
              $idModeTechnicalPogressCalc   = SqlList::getIdFromTranslatableName('ProgressMode', 'calculated');
              if ($this->$pe->idProgressMode == $idModeTechnicalPogressManual) {
                $this->$pe->unitProgress = 100;
                if ($this->$pe->unitToRealise != null) {
                  $this->$pe->unitLeft     = 0;
                }
              }
              if ($this->$pe->idProgressMode == $idModeTechnicalPogressCalc) {
                $this->$pe->unitRealised = (float)$this->$pe->unitToRealise;
                $this->$pe->unitLeft     = 0;
                $this->$pe->unitProgress = 100;
              }
            }
          }
        }
      }
    }
    
    $result = parent::save ();
    if (! pq_strpos ( $result, 'id="lastOperationStatus" value="OK"' )) {
      return $result;
    }
    
    /// KROWRY HERE
    if ( (Parameter::getGlobalParameter('autoSetAssignmentByResponsible')=="YES" 
         and (!SqlElement::isCopyInProgress() or Synchronization::$_createSyncItemInProgress==true)  
         and !$this->ActivityPlanningElement->isManualProgress)
       or RequestHandler::isCodeSet('selectedResource') ){ 
      $proj=new Project($this->idProject,true);
      $type=new Type($proj->idProjectType);
      $resource=(RequestHandler::isCodeSet('selectedResource'))?RequestHandler::getValue('selectedResource'):$this->idResource;
      if ($type->code!='ADM' and $resource and pq_trim ( $resource ) != '' and ! pq_trim ( $oldResource ) and pq_stripos ( $result, 'id="lastOperationStatus" value="OK"' ) > 0) {
        // Add assignment for responsible
        $habil = SqlElement::getSingleSqlElementFromCriteria ( 'HabilitationOther', array(
            'idProfile' => getSessionUser ()->getProfile ( $this->idProject ), 
            'scope' => 'assignmentEdit') );
        if ($habil and $habil->rightAccess == 1) {
          $ass = new Assignment ();
          $crit = array('idResource' => $resource, 'refType' => 'Activity', 'refId' => $this->id);
          //$lst = $ass->getSqlElementsFromCriteria ( $crit, false );
          //if (count ( $lst ) == 0) {
          $cpt=$ass->countSqlElementsFromCriteria($crit);
          if ($cpt == 0) {
            $ass->idProject = $this->idProject;
            $ass->refType = 'Activity';
            $ass->refId = $this->id;
            $ass->idResource = $resource;
            $ass->assignedWork = 0;
            $ass->realWork = 0;
            $ass->leftWork = 0;
            $ass->plannedWork = 0;
            $ass->notPlannedWork = 0;
            $ass->rate = '100';
            if ($this->ActivityPlanningElement->validatedWork and $this->ActivityPlanningElement->validatedWork>$this->ActivityPlanningElement->assignedWork) {
              $ass->assignedWork=$this->ActivityPlanningElement->validatedWork-$this->ActivityPlanningElement->assignedWork;
              $ass->leftWork=$ass->assignedWork;
            }
            $ass->save ();
          }
        }
      }
    }
    // Change idle or idProject value => update idle and idProject for assignments
    if (($this->idle != $oldIdle) or ($this->idProject != $oldIdProject)) {
      // Add assignment for responsible
      $ass = new Assignment ();
      $crit = array("refType" => "Activity", "refId" => $this->id);
      $assList = $ass->getSqlElementsFromCriteria ( $crit, false );
      
      $sub = new SubTask();
      $subList = $sub->getSqlElementsFromCriteria($crit, false );
      foreach ($subList as $sub) {
        $sub->idProject = $this->idProject;
        $sub->saveForced();
      }
      foreach ( $assList as $ass ) {
        $ass->idle = $this->idle;
        $ass->idProject = $this->idProject;
        $resAssSave=$ass->save();
        // Change idProject value => update idProject for work
        // update not done to PlannedWork : new planning must be calculated
        if ($this->idProject != $oldIdProject) {
          $work = new Work ();
          $crit = array("refType" => "Activity", "refId" => $this->id);
          $workList = $work->getSqlElementsFromCriteria ( $crit, false );
          foreach ( $workList as $work ) {
            $work->idProject = $this->idProject;
            $work->save ();
          }
          $work = new PlannedWork ();
          $crit = array("refType" => "Activity", "refId" => $this->id);
          $workList = $work->getSqlElementsFromCriteria ( $crit, false );
          foreach ( $workList as $work ) {
            $work->idProject = $this->idProject;
            $work->save ();
          }
        }
      }
    }
    if ($this->idProject != $oldIdProject) {
      $lstElt = array('Activity', 'Ticket', 'Milestone', 'PeriodicMeeting', 'Meeting', 'TestSession');
      foreach ( $lstElt as $elt ) {
        $eltObj = new $elt ();
        $crit = array('idActivity' => $this->id);
        $lst = $eltObj->getSqlElementsFromCriteria ( $crit, false, null, null, true );
        foreach ( $lst as $obj ) {
          SqlElement::$_skipAllControls=true;
          $objBis = new $elt ( $obj->id );
          $objBis->idProject = $this->idProject;
          if ($elt=='Activity') {
            $tmpRes = $objBis->save (true);
          } else {
            $tmpRes = $objBis->save ();
          }
        }
      }
      SqlElement::$_skipAllControls=false;
    }
    if ($oldTargetProductVersion != $this->idTargetProductVersion) {
      $vers = new Version ( $this->idTargetProductVersion );
      $idProduct = ($vers->idProduct) ? $vers->idProduct : null;
      $ticket = new Ticket ();
      $ticketList = $ticket->getSqlElementsFromCriteria ( array('idActivity' => $this->id) );
      foreach ( $ticketList as $ticket ) {
        $ticket->idTargetProductVersion = $this->idTargetProductVersion;
        if ($idProduct) {
          $ticket->idProduct = $idProduct;
        }
        $ticket->save ();
      }
    }
    
    /*
    // ticket #2822 - mehdi
    if (Parameter::getGlobalParameter ( 'autoUpdateActivityStatus' ) == 'YES' and isset($old)) {
      if ($this->idActivity) {
        $parent = new Activity ($this->idActivity);
      } else {
        $parent = new Project ($this->idProject,true);
      }
      if ($this->handled and $this->handled!=$old->handled) {
        if ( ! $parent->handled ) {
          $parent->handled = $this->handled;
          $parent->handledDate=date('Y-m-d');
          $allowedStatusList=Workflow::getAllowedStatusListForObject($parent);
          foreach ( $allowedStatusList as $st ) {
            if ($st->setHandledStatus) {
              $parent->idStatus=$st->id;
              $parent->save();
              break;
            }
          }  
        }
      }
      $status = new Status ($this->idStatus);
      $isStatDone=($status->setDoneStatus)?true:false;
      $isStatIdle=($status->setIdleStatus)?true:false;
      $isStatCancelled=($status->setCancelledStatus)?true:false;
      $status = new Status ($old->idStatus);
      $isOldStatDone=($status->setDoneStatus)?true:false;
      $isOldStatIdle=($status->setIdleStatus)?true:false;
      $isOldStatCancelled=($status->setCancelledStatus)?true:false;
      if ( ($isStatDone and $isStatDone!=$isOldStatDone) or ($isStatIdle and $isStatIdle!=$isOldStatIdle) or ($isStatCancelled and $isStatCancelled!=$isOldStatCancelled)) {
        $allDone=true; 
        $allIdle=true; 
        $allCancelled=true;
        
        $sons=$this->getSqlElementsFromCriteria(null, null, "idActivity=$parent->id or ( idActivity is null and idProject=$parent->id)");
        foreach ($sons as $act) {
          if (!$act->done and !$act->cancelled) $allDone=false;
          if (!$act->idle and !$act->cancelled) $allIdle=false;
          if (!$act->cancelled) $allCancelled=false;
        }
        $setToDone=($isStatDone and $isStatDone!=$isOldStatDone and $allDone)?true:false;
        $setToIdle=($isStatIdle and $isStatIdle!=$isOldStatIdle and $allIdle)?true:false;
        $setToCancelled=($isStatCancelled and $isStatCancelled!=$isOldStatCancelled and $allCancelled)?true:false;
        if ($setToDone or $setToIdle or $setToCancelled) {
          $currentParentStatus=new Status($parent->idStatus);
          if ( (! $setToDone or ($setToDone and $currentParentStatus->setDoneStatus) ) 
           and (! $setToIdle or ($setToIdle and $currentParentStatus->setIdleStatus) )  
           and (! $setToCancelled or ($setToCancelled and $currentParentStatus->setCancelledStatus) )) {
            // Nothing to do, already in a status corresponding to target
          } else {
            $allowedStatusList=Workflow::getAllowedStatusListForObject($parent);
            $saveParent=false;
            foreach ( $allowedStatusList as $st ) {
              if ($setToDone and $st->setDoneStatus) {
                $parent->idStatus=$st->id;
                $parent->done=$this->done;
                $parent->doneDate=date('Y-m-d');
                $saveParent=true;
                $setToDone=false;
              }
              if ($setToIdle and $st->setIdleStatus) {
                $parent->idStatus=$st->id;
                $parent->idle=$this->idle;
                $parent->idleDate=date('Y-m-d');
                $saveParent=true;
                $setToIdle=false;
              }  
              if ($setToCancelled and $st->setCancelledStatus) {
                $parent->idStatus=$st->id;
                $parent->cancelled=$this->cancelled;
                $parent->doneDate=date('Y-m-d');
                $saveParent=true;
                $setToCancelled=false;
              }
            }
            if ($saveParent) $parent->save();
          }
        }
      }
    }*/
// MTY - LEAVE SYSTEM
    if (isLeavesSystemActiv()) {
        $leaveProjectId = Project::getLeaveProjectId();
    }
// MTY - LEAVE SYSTEM
    return $result;
  }
  
  public function setAttributes() {
    if(Parameter::getUserParameter('paramLayoutObjectDetail')=="col"){
      self::$_fieldsAttributes["fixPlanning"]='hidden';
    }
    if (!Module::isModuleActive('moduleTargetMilestone') and (! property_exists('Activity','_customFields') or ! in_array('idMilestone', Activity::$_customFields))) {//Parameter::getGlobalParameter('manageMilestoneOnItems') != 'YES'
      self::$_fieldsAttributes["idMilestone"]='hidden';
    }
    if($this->id){
      $displayVote = VotingItem::isVotable('Activity', $this->id,$this->idActivityType);
      if($displayVote or RequestHandler::isCodeSet('customization')){
        self::$_fieldsAttributes ['_sec_vote'] = '';
        self::$_fieldsAttributes ['VotingItem'] = '';
      }else{
        self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
        self::$_fieldsAttributes ['VotingItem'] = 'hidden';
      }
    }else if (! RequestHandler::isCodeSet('customization')) {
        self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
        self::$_fieldsAttributes ['VotingItem'] = 'hidden';
        self::$_fieldsAttributes ['_sec_subActivity'] = 'hidden';
    }
    if (!Module::isModuleActive('moduleTodoList') or Parameter::getUserParameter('displaySubTask')!="YES" 
      or (! $this->id and ! RequestHandler::isCodeSet('customization')) ){//Parameter::getGlobalParameter('activateSubtasksManagement')!='YES'
      self::$_fieldsAttributes ['_SubTask'] = 'hidden';
      self::$_fieldsAttributes ['_sec_ToDoList'] = 'hidden';
      unset($this->_sec_ToDoList);
    } else if ($this->id) {
      $user=getSessionUser();
      $habilSub=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($this),'scope'=>'subtask'));
      $listYesNo=new ListYesNo($habilSub->rightAccess);
      if ($listYesNo->code!='YES') {
        self::$_fieldsAttributes ['_SubTask'] = 'hidden';
        self::$_fieldsAttributes ['_sec_ToDoList'] = 'hidden';
        unset($this->_sec_ToDoList);
      }
    }
    if(!Module::isModuleActive('moduleSkillManagement') or (! $this->id and ! RequestHandler::isCodeSet('customization') ) ){
    	self::$_fieldsAttributes ['_sec_ActivitySkill'] = 'hidden';
    	self::$_fieldsAttributes ['_spe_activitySkill'] = 'hidden';
    	unset($this->_sec_ActivitySkill);
    }
//     if (RequestHandler::isCodeSet('customization')) {
//       self::$_fieldsAttributes ['_ActivitySkill'] = 'hidden';
//       unset($this->_ActivitySkill);
//     }
    if($this->paused==1){
      self::$_fieldsAttributes["fixPlanning"]='readonly,nobr';
    }
    if($this->ActivityPlanningElement->topRefId!=''){
      $parent=new $this->ActivityPlanningElement->topRefType($this->ActivityPlanningElement->topRefId);
    }
    
    if (SqlList::getFieldFromId("Status", $this->idStatus, "setPausedStatus")!=0 or (isset($parent) and $parent->paused==1) ){
      self::$_fieldsAttributes["paused"]="readonly,nobr";
    }
    if(Parameter::getGlobalParameter('activityOnRealTime')!='YES' or $this->ActivityPlanningElement->hasWorkUnit){
      self::$_fieldsAttributes["workOnRealTime"]='hidden';
    }
    if($this->id){
      $proj= new Project();
      $count=$proj->countSqlElementsFromCriteria(array("id"=>$this->idProject,'codeType'=>'ADM'));
      if($count!=0){
        self::$_fieldsAttributes["fixPlanning"]="hidden";
        self::$_fieldsAttributes["workOnRealTime"]='hidden';
        self::$_fieldsAttributes["paused"]="hidden";
        self::$_fieldsAttributes["isPlanningActivity"]="hidden";
        self::$_fieldsAttributes["_Dependency_Predecessor"]="hidden";
        self::$_fieldsAttributes["_Dependency_Successor"]="hidden";
        self::$_fieldsAttributes["idProduct"]="hidden";
        self::$_fieldsAttributes["idComponent"]="hidden";
        self::$_fieldsAttributes["idTargetProductVersion"]="hidden";
        self::$_fieldsAttributes["idTargetComponentVersion"]="hidden";
        unset($this->_sec_predecessor);
        unset($this->_Dependency_Predecessor);
        unset($this->_sec_successor);
        unset($this->_Dependency_Successor);
        unset($this->_sec_productComponent);
      }
    }
    $user = getSessionUser();
    $assignmentView=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($this->idProject), 'scope'=>'assignmentView'));
    $assignmentEdit=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($this->idProject), 'scope'=>'assignmentEdit'));
    $ass=new Assignment();
    $ass->id=1;$ass->idProject=$this->idProject;
    $canUpdate=true;
    if (securityGetAccessRightYesNo('menuAssignment', 'update', $ass)!="YES") $canUpdate=false;
    if (!$this->id or ! $canUpdate or ($assignmentView and $assignmentView->rightAccess!=1) or ($assignmentEdit and $assignmentEdit->rightAccess!=1)) {
      self::$_fieldsAttributes['_spe_purgeAssignment']='hidden';
      self::$_fieldsAttributes['_spe_resetAssignment']='hidden';
    }
    if (!$this->id or securityGetAccessRight('menuAssignment', 'update', $this)=='NO' or ($assignmentView and $assignmentView->rightAccess!=1)) {
      self::$_fieldsAttributes['_spe_showClosedAssignment']='hidden';
    }
    if (!Module::isModuleActive("moduleAbacus")) self::$_fieldsAttributes["_sec_Abacus"]="hidden";
  }
  
  protected function getStaticFieldsTooltip() {
    return self::$_fieldsTooltip;
  }
  
// MTY - LEAVE SYSTEM  
  /**
   * =========================================================================
   * Overrides SqlElement::delete() function to add specific treatments
   * 
   * @see persistence/SqlElement#delete()
   * @param Boolean - withControlLeave = If the delete is made by LeaveTypeMain, then withControlLeave=false
   * @return String the return message of persistence/SqlElement#delete() method
   */
  public function delete($withControlLeave=true) {
      if (isLeavesSystemActiv()) {
        // Can't delete an activity of the leave system project.
        $leaveProjectId = Project::getLeaveProjectId();
        if ($leaveProjectId==$this->idProject && $withControlLeave==true && $leaveProjectId!=null) {
          $returnValue = '<b>' . i18n ( 'messageCantDeleteAnActivityAssociatedToLeaveType' ) . '</b><br/>';
          $returnValue .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
          $returnValue .= '<input type="hidden" id="lastSaveId" value="' . htmlEncode ( $this->id ) . '" />';
          $returnValue .= '<input type="hidden" id="lastOperation" value="delete" />';
          return $returnValue;
         }
      }
      $result = parent::delete();
      if(getLastOperationStatus($result)=="OK"){
        if($this->ActivityPlanningElement->hasWorkUnit){
          $activityWorkUnit = new ActivityWorkUnit();
          $lstActWorkUnit = $activityWorkUnit->getSqlElementsFromCriteria(array('refType'=>'Activity','refId'=>$this->id));
          foreach ($lstActWorkUnit as $actWork){
            if($actWork->idWorkCommand){
              $workCommandDone = SqlElement::getSingleSqlElementFromCriteria('WorkCommandDone', array('idActivityWorkUnit'=>$actWork->id));
              $workCommandDone->delete();
              $newWorkCommandDone = new WorkCommandDone();
              $workCommand = new WorkCommand($actWork->idWorkCommand);
              $lstWorkCommand = $newWorkCommandDone->getSqlElementsFromCriteria(array('idWorkCommand'=>$actWork->idWorkCommand,'idCommand'=>$workCommand->idCommand));
              $quantity = 0;
              foreach ($lstWorkCommand as $comVal){
                $quantity += $comVal->doneQuantity;
              }
              $workCommand->doneQuantity = $quantity;
              $workCommand->doneAmount = $workCommand->unitAmount * $quantity;
              $workCommand->save();
            }
            $actWork->delete();
          }
        }
      }
      return $result;
  }    

  public function deleteControl(){
    //global $deleteObjectInProgress;
    $result="";
    if (SynchronizedItems::getSynchronizedItemKey('Activity',$this->id)!=null) {
      SqlElement::unsetRelationShip('Activity', 'Ticket');
    }
    $result=parent::deleteControl();
    return $result;
  }
  
  public static function getRecursiveSubActivitiesFlatList($id) {
    $list=self::getRecursiveSubActivities($id);
    return implode(',',array_flip($list));
  }
  public static function getRecursiveSubActivities($id) {
    if (isset(self::$_subTasksList[$id])) return self::$_subTasksList[$id];
    $res=SqlList::getListWithCrit('Activity',"idActivity=$id",'name',null,true);
    foreach ($res as $idSub=>$nameSub) {
      $resSub=self::getRecursiveSubActivities($idSub);
      $res=array_merge_preserve_keys($res,$resSub);
    }
    self::$_subTasksList[$id]=$res;
    return $res;
  }
  
  public function copyTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments = false, $withAffectations = false, $toProject = null, $toActivity = null, $copyToWithResult = false, $copyToWithActivityPrice=false, $copyToWithStatus = false,$copyToWithSubTask = false, $moveAfterCreate = null, $copyToWithDependency=false, $copyToWithPredecessor=false, $copyToWithSuccessor=false) {
    self::setCopyInProgress();
    $result=parent::copyTo( $newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments, $withAffectations, $toProject, $toActivity, $copyToWithResult, $copyToWithActivityPrice, $copyToWithStatus,$copyToWithSubTask, $moveAfterCreate);
    if($newClass == 'Activity'){
      if($copyToWithDependency and $result->id){
        // Copy dependencies
        $newDep = new Dependency();
        $newDep->dependencyType = 'E-S';
        $newDep->predecessorRefType='Activity';
        $newDep->predecessorRefId=$this->id;
        $crit=array('refType'=>'Activity', 'refId'=>$this->id);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $newDep->predecessorId=$pe->id;
        $newDep->successorRefType='Activity';
        $newDep->successorRefId=$result->id;
        $crit=array('refType'=>'Activity', 'refId'=>$result->id);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $newDep->successorId=$pe->id;
        $newDep->save();
      }
    }
    if($copyToWithPredecessor and $result->id){
      // Copy predecessors
      $dep=New dependency();
      $crit = array('successorRefType'=>'Activity', 'successorRefId'=>$this->id);
      $deps=$dep->getSqlElementsFromCriteria($crit);
      foreach ($deps as $dep) {
        $newDep = new Dependency();
        $newDep->dependencyType = $dep->dependencyType;
        $newDep->successorRefType='Activity';
        $newDep->successorRefId=$result->id;
        $crit=array('refType'=>'Activity', 'refId'=>$result->id);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $newDep->successorId=$pe->id;
        $newDep->predecessorRefType=$dep->predecessorRefType;
        $newDep->predecessorRefId=$dep->predecessorRefId;
        $newDep->predecessorId=$dep->predecessorId;
        $newDep->save();
      }
    }
    if($copyToWithSuccessor and $result->id){
      // Copy successors
      $dep=New dependency();
      $crit = array('predecessorRefType'=>'Activity', 'predecessorRefId'=>$this->id);
      $deps=$dep->getSqlElementsFromCriteria($crit);
      foreach ($deps as $dep) {
        $newDep = new Dependency();
        $newDep->dependencyType = $dep->dependencyType;
        $newDep->predecessorRefType='Activity';
        $newDep->predecessorRefId=$result->id;
        $crit=array('refType'=>'Activity', 'refId'=>$result->id);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $newDep->predecessorId=$pe->id;
        $newDep->successorRefType=$dep->successorRefType;
        $newDep->successorRefId=$dep->successorRefId;
        $newDep->successorId=$dep->successorId;
        $newDep->save();
      }
    }
    return $result;
  }
  
  public function getColor() {
    if (isset(self::$_cacheColor[$this->id])) return self::$_cacheColor[$this->id];
    $color="#FFFFFF";
    $critArray=array('refType'=>'Activity', 'refId'=>$this->id);
    $planningElement = SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $critArray);
    if ($planningElement && $planningElement->color) {
      $color=$planningElement->color;
    }
    self::$_cacheColor[$this->id]=$color;
    return $color;
  }
  
}
?>
