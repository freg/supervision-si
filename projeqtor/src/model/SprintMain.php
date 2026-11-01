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
require_once('_securityCheck.php');

class SprintMain extends SqlElement {

  public $_sec_description;
  public $id;
  public $reference;
  public $name;
  public $idProject;
  public $idSprintType;
  public $creationDate;
  public $lastUpdateDateTime;
  public $idUser;
  public $description;
  public $_sec_treatment;
  public $idStatus;
  public $idResource;
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
  public $_sec_UserStory;
  public $_spe_UserStory;
  public $_sec_Progress;
  public $SprintPlanningElement;
  public $_sec_productComponent;
  public $idProduct;
  public $idComponent;
  public $idTargetProductVersion;
  public $idTargetComponentVersion;
  public $_sec_predecessor;
  public $_Dependency_Predecessor = array();
  public $_sec_successor;
  public $_Dependency_Successor = array();
  public $_sec_Link;
  public $_Link = array();
  public $_Attachment = array();
  public $_Note = array();
  public $_nbColMax=3;
  
  private static $_cacheColor=array();
  
  private static $_layout = '
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="10%" >${idProject}</th>
    <th field="name" width="25%" >${name}</th>
    <th field="plannedEndDate" from="SprintPlanningElement" width="10%" formatter="dateFormatter">${plannedEndDate}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>';
  
  private static $_fieldsAttributes = array(
      "id" => "nobr",
      "reference" => "readonly", 
      "name" => "required",
      "idSprintType"=>"required",
      "idProject" => "required",
      "idStatus" => "required",
      "creationDate" => "required",
      "fixPlanning"=>"nobr,noExport",
      "handled" => "nobr",
      "done" => "nobr",
      "idle" => "nobr",
      "idleDate" => "nobr",
      "cancelled" => "nobr",
      "paused"=>"nobr",
  );
  
  private static $_colCaptionTransposition = array(
      'idUser' => 'issuer',
      'idResource' => 'scrumMaster',
  );
  
  // private static $_databaseColumnName = array('idResource'=>'idUser');
  private static $_databaseColumnName = array(
      'idTargetProductVersion' => 'idVersion',
      'idTargetComponentVersion' => 'idComponentVersion');
  

  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
  }
  function __destruct() { 
    parent::__destruct();
  }
  
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
      $colScript .= '  dojo.byId("SprintPlanningElement_wbs").value=""; ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName == "fixPlanning") {
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
        $colScript .= '<script type="dojo/connect" event="onChange" >';
        $colScript .= ' dijit.byId("SprintPlanningElement_fixPlanning").set("value",dijit.byId("fixPlanning").get("value"));';
        $colScript .= '  formChanged();';
        $colScript .= '</script>';
      }
    } else if($colName=="paused"){
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if(this.checked){';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",true);';
      $colScript .= '   dijit.byId("fixPlanning").set("checked",true);';
      $colScript .= '   dijit.byId("fixPlanning").set("value",1);';
      $colScript .= ' dijit.byId("SprintPlanningElement_paused").set("checked",true);';
      $colScript .= ' dijit.byId("SprintPlanningElement_paused").set("value",1);';
      $colScript .= ' dijit.byId("SprintPlanningElement_fixPlanning").set("readOnly",true);';
      $colScript .= '  }else{';
      $colScript .= '   dijit.byId("fixPlanning").set("readOnly",false);';
      $colScript .= '   dijit.byId("fixPlanning").set("checked",false);';
      $colScript .= '   dijit.byId("fixPlanning").set("value",0);';
      $colScript .= ' dijit.byId("SprintPlanningElement_fixPlanning").set("readOnly",false);';
      $colScript .= '  }';
      if(Parameter::getUserParameter('paramLayoutObjectDetail')=="tab"){
        $colScript .= ' dijit.byId("SprintPlanningElement_paused").set("value",dijit.byId("paused").get("value"));';
        $colScript .= '  formChanged();';
      }
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

    if ($this->id && $old->idProject != $this->idProject) {
      $ass = new Assignment();
      $lstAss = $ass->getSqlElementsFromCriteria(array('refType'=>'Sprint','refId'=>$this->id,'idle'=>'0'));
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
    
    // default duration
    if (! $this->SprintPlanningElement->validatedDuration and PlanningMode::isFixedDuration($this->SprintPlanningElement->idSprintPlanningMode)) {
      $type=new SprintType($this->idSprintType);
      if ($type->defaultDuration) $this->SprintPlanningElement->validatedDuration=$type->defaultDuration;
    }
    
    $defaultControl = parent::control ();
    if ($defaultControl != 'OK') {
      $result .= $defaultControl;
    }
    if ($result == "") {
      $result = 'OK';
    }
    return $result;
  }
  
  /* =========================================================================
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
    $oldTargetProductVersion = null;
    if ($this->id) {
      $old = $this->getOld (false);
      $oldResource = $old->idResource;
      $oldIdle = $old->idle;
      $oldIdProject = $old->idProject;
      $oldTargetProductVersion = $old->idTargetProductVersion;
      if($this->fixPlanning!=$old->fixPlanning and $this->fixPlanning!=$this->SprintPlanningElement->fixPlanning){
        $this->SprintPlanningElement->fixPlanning=$this->fixPlanning;
      }
      if($this->SprintPlanningElement->fixPlanning!=$old->SprintPlanningElement->fixPlanning and $this->fixPlanning!=$this->SprintPlanningElement->fixPlanning){
        $this->fixPlanning=$this->SprintPlanningElement->fixPlanning;
      }
      if($old->fixPlanning and $old->SprintPlanningElement->fixPlanning and !$this->SprintPlanningElement->fixPlanning){
        $this->fixPlanning = 0;
        $this->SprintPlanningElement->fixPlanning = 0;
      }
      if($old->idStatus != $this->idStatus){
        $status = new Status ($this->idStatus);
        if($status->fixPlanning and !$this->fixPlanning){
          $this->fixPlanning = 1;
          $this->SprintPlanningElement->fixPlanning = 1;
        }
      }
    }
    // #305 : need to recalculate before dispatching to PE
    $this->recalculateCheckboxes ();
    $this->SprintPlanningElement->refName = $this->name;
    $this->SprintPlanningElement->idProject = $this->idProject;
    $this->SprintPlanningElement->idle = $this->idle;
    $this->SprintPlanningElement->done = $this->done;
    $this->SprintPlanningElement->cancelled = $this->cancelled;
    $this->SprintPlanningElement->topRefType = 'Project';
    $this->SprintPlanningElement->topRefId = $this->idProject;
    $this->SprintPlanningElement->topId = null;
    if ( (pq_trim($this->idProject)!=pq_trim($oldIdProject) and !$onlyProject)) {
      $this->SprintPlanningElement->wbs = null;
      $this->SprintPlanningElement->wbsSortable = null;
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
      if($this->paused!=$old->paused and  $this->SprintPlanningElement->paused!=$this->paused){
        $this->SprintPlanningElement->paused=$this->paused;
      }else if( $this->SprintPlanningElement->paused!=$old->SprintPlanningElement->paused and $this->SprintPlanningElement->paused!=$this->paused){
        $this->paused=$this->SprintPlanningElement->paused;
      }
      if ($this->paused!=$old->paused and $this->paused==1  and  $this->fixPlanning!=$this->paused){
        $this->fixPlanning=1;
        $this->SprintPlanningElement->fixPlanning=1;
      }
    }
    if ($this->id and $this->handled and $this->handledDate and ! $this->SprintPlanningElement->validatedStartDate) {
      if ( $this->SprintPlanningElement->realWork==0 and ($this->SprintPlanningElement->assignedWork>0 or $this->SprintPlanningElement->leftWork>0)
          and ($this->SprintPlanningElement->idPlanningMode==29 or $this->SprintPlanningElement->idPlanningMode==30)) {
            // Constrained duration, if activity "started" (handledDate set) and no real work entered and has left work, set validatedStartDate isf not set.
            $this->SprintPlanningElement->inheritedStartDate=$this->handledDate;
          }
    }
    $result = parent::save ();
    if (! pq_strpos ( $result, 'id="lastOperationStatus" value="OK"' )) {
      return $result;
    }
    
    /// KROWRY HERE
    if ( (Parameter::getGlobalParameter('autoSetAssignmentByResponsible')=="YES"
        and (!SqlElement::isCopyInProgress() or Synchronization::$_createSyncItemInProgress==true)
        and !$this->SprintPlanningElement->isManualProgress)
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
              $crit = array('idResource' => $resource, 'refType' => 'Sprint', 'refId' => $this->id);
              //$lst = $ass->getSqlElementsFromCriteria ( $crit, false );
              //if (count ( $lst ) == 0) {
              $cpt=$ass->countSqlElementsFromCriteria($crit);
              if ($cpt == 0) {
                $ass->idProject = $this->idProject;
                $ass->refType = 'Sprint';
                $ass->refId = $this->id;
                $ass->idResource = $resource;
                $ass->assignedWork = 0;
                $ass->realWork = 0;
                $ass->leftWork = 0;
                $ass->plannedWork = 0;
                $ass->notPlannedWork = 0;
                $ass->rate = '100';
                if ($this->SprintPlanningElement->validatedWork and $this->SprintPlanningElement->validatedWork>$this->SprintPlanningElement->assignedWork) {
                  $ass->assignedWork=$this->SprintPlanningElement->validatedWork-$this->SprintPlanningElement->assignedWork;
                  $ass->leftWork=$ass->assignedWork;
                }
                $ass->save ();
              }
              }
            }
          }
          if ($this->idProject != $oldIdProject) {
            $lstElt = array('Epic', 'UserStory');
            foreach ( $lstElt as $elt ) {
              $eltObj = new $elt ();
              $crit = array('idSprint' => $this->id);
              $lst = $eltObj->getSqlElementsFromCriteria ( $crit, false, null, null, true );
              foreach ( $lst as $obj ) {
                SqlElement::$_skipAllControls=true;
                $objBis = new $elt ( $obj->id );
                $objBis->idProject = $this->idProject;
                if ($elt=='Sprint') {
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
            $userStory = new UserStory();
            $userStoryList = $userStory->getSqlElementsFromCriteria ( array('idSprint' => $this->id) );
            foreach ( $userStoryList as $userStory ) {
              $userStory->idTargetProductVersion = $this->idTargetProductVersion;
              if ($idProduct) {
                $userStory->idProduct = $idProduct;
              }
              $userStory->save ();
            }
          }
          return $result;
    }
    
    public function getUserStoryList(){
      if(!$this->id)return array();
      $userStory = new UserStory();
      $where = "idSprint = ".$this->id;
      $userStoryList = $userStory->getSqlElementsFromCriteria(null,null,$where);
      return $userStoryList;
    }
    
    public function updateStatusFromUserStory() {
      $list = $this->getUserStoryList();
      $countUs = count($list);
      if (!$list || !$countUs) {
        $statusList = SqlList::getStatusList(get_class($this));
        $lowestStatus = array_key_first($statusList);
        if ((int)$this->idStatus !== (int)$lowestStatus) {
          $this->idStatus = (int)$lowestStatus;
          $this->save();
        }
        return;
      }
      
      $maxSort = null;
      $maxSortDoneOrIdle = null;
      $maxStatusId = null;
      $maxDoneOrIdleStatus = null;
      $sameStatus = true;
      $previousStatus = null;
      
      foreach ($list as $us) {
        $status = new Status($us->idStatus, true);
        $sid  = $status->id;
        $sort = $status->sortOrder;
        $doneOrIdle = ($status->setIdleStatus || $status->setDoneStatus)?true:false;
        if(!$previousStatus)$previousStatus=$sid;
        if($sid != $previousStatus)$sameStatus=false;
        
        if (!$doneOrIdle and ($maxSort === null || $sort > $maxSort || ($sort === $maxSort && $sid > $maxStatusId))) {
          $maxSort = $sort;
          $maxStatusId = $sid;
        }
        
        if ($doneOrIdle and ($maxSortDoneOrIdle === null || $sort > $maxSortDoneOrIdle || ($sort === $maxSortDoneOrIdle && $sid > $maxDoneOrIdleStatus))) {
          $maxSortDoneOrIdle = $sort;
          $maxDoneOrIdleStatus=$sid;
        }
        
        $previousStatus = $sid;
      }
      
      if($maxDoneOrIdleStatus and $sameStatus){
        $maxStatusId = $maxDoneOrIdleStatus;
      }
      
      if (!$maxStatusId) return;
      
      if ($this->idStatus != $maxStatusId) {
        $this->idStatus = $maxStatusId;
        $this->save();
      }
    }
  
  /** =========================================================================
   * Draw a specific item for the current class.
   * @param String $item the item.
   * @return String an html string able to display a specific item
   *  must be redefined in the inherited class
   */
  public function drawSpecificItem($item,$readOnly=false,$refresh=false){
    global $print, $comboDetail;
    $result='';
    if($item == "UserStory"){
      drawUserStoryFromObject($this);
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
        $result .='<a id="'.$item.'" onClick="purgeAssignmentTable()" title="'.i18n('helpPurgeAssignment', array(i18n('colSprint'), $this->id)).'">'.formatMediumButton('Purge').'</a>';
      }
      $result.='</div>';
      return $result;
    }else if (!$print and $item=='resetAssignment' and !$comboDetail){
      $result.='<div style="position:absolute;right:0px;top:45px;">';
      if($this->idle != 1){
        $result .='<a id="'.$item.'" onClick="resetAssignmentTable()" title="'.i18n('helpResetAssignment', array(i18n('colSprint'), $this->id)).'">'.formatMediumButton('Reset').'</a>';
      }
      $result.='</div>';
      return $result;
    }
  }
 
  
  public function getColor() {
    if (isset(self::$_cacheColor[$this->id])) return self::$_cacheColor[$this->id];
    $color="#FFFFFF";
    $critArray=array('refType'=>'Sprint', 'refId'=>$this->id);
    $planningElement = SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $critArray);
    if ($planningElement && $planningElement->color) {
      $color=$planningElement->color;
    }
    self::$_cacheColor[$this->id]=$color;
    return $color;
  }
 }
