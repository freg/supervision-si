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
 * Action is establised during meeting, to define an action to be followed.
 */ 
require_once('_securityCheck.php');

class MilestoneMain extends SqlElement {

  // List of fields that will be exposed in general user interface
  public $_sec_description;
  public $id;    // redefine $id to specify its visible place 
  public $reference;
  public $name;
  public $idProject;
  public $idMilestoneType;
  public $creationDate;
  public $lastUpdateDateTime;
  public $idUser;
  public $Origin;
  public $description;
  public $_sec_treatment;
  public $idActivity;
  public $idStatus;
  public $idResource;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $idTargetProductVersion;
  public $result;
  public $_sec_Progress;
  public $MilestonePlanningElement; // is an object
  public $_sec_predecessor;
  public $_Dependency_Predecessor=array();
  public $_sec_successor;
  public $_Dependency_Successor=array();
  public $_sec_TargetMilestone;
  public $_spe_DependencyObject;
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();  
  public $_nbColMax=3;
  
  private static $_cacheColor=array();
  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="20%" >${idProject}</th>
    <th field="nameMilestoneType" width="10%" >${idMilestoneType}</th>
    <th field="name" width="40%" >${name}</th>
    <th field="plannedEndDate" from="MilestonePlanningElement" width="10%" formatter="dateFormatter">${plannedDueDate}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>
    ';

  private static $_fieldsAttributes=array("id"=>"nobr", "reference"=>"readonly",
                                  "name"=>"required", 
                                  "idProject"=>"required",
                                  "idStatus"=>"required",
                                  "idMilestoneType"=>"required",
                                  "creationDate"=>"required",
                                  "handled"=>"nobr",
                                  "done"=>"nobr",
                                  "idle"=>"nobr",
                                  "idleDate"=>"nobr",
                                  "cancelled"=>"nobr"
  );  
  
  private static $_colCaptionTransposition = array('idUser'=>'issuer', 
                                                   'idResource'=> 'responsible',
                                                   'idActivity' => 'parentActivity',
                                                   'idTargetProductVersion'=>'targetVersion');
  
  private static $_databaseColumnName = array('idTargetProductVersion'=>'idVersion');
    
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if (!$withoutDependentObjects) {
      $this->excludeDependentObjects();
    }
    if ($withoutDependentObjects) return; // No real use yet, but no to forget as item has $Origin
  }
  
  private function excludeDependentObjects() {
    $idleModuleTargetMilestone = SqlElement::getRefField('module', '23', 'active');
    if ($idleModuleTargetMilestone != 1) {
      unset($this->_sec_TargetMilestone);
      unset($this->_spe_DependencyObject);
    }
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
  
  /** ==========================================================================
   * Return the specific fieldsAttributes
   * @return Array the fieldsAttributes  
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }
  
  /** ============================================================================
   * Return the specific colCaptionTransposition
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return self::$_colCaptionTransposition;
  }

  /** ========================================================================
   * Return the specific databaseColumnName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
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

    if ($colName=="idProject") {   
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  dojo.byId("MilestonePlanningElement_wbs").value=""; ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="idActivity") {   
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  dojo.byId("MilestonePlanningElement_wbs").value=""; ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="idMilestoneType") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  setDefaultPlanningMode(this.value);';
      $colScript .= '</script>';
    } 
    return $colScript;
  }

  /**=========================================================================
   * Overrides SqlElement::save() function to add specific treatments
   * @see persistence/SqlElement#save()
   * @return String the return message of persistence/SqlElement#save() method
   */
  public function save() {
    // #305 : need to recalculate before dispatching to PE
    $this->recalculateCheckboxes();
    $old=$this->getOld();
    $this->MilestonePlanningElement->refName=$this->name;
    $this->MilestonePlanningElement->idProject=$this->idProject;
    $this->MilestonePlanningElement->idle=$this->idle;
    $this->MilestonePlanningElement->done=$this->done;
    $this->MilestonePlanningElement->cancelled=$this->cancelled;
    if ($this->idActivity and pq_trim($this->idActivity)!='') {
      $this->MilestonePlanningElement->topRefType='Activity';
      $this->MilestonePlanningElement->topRefId=$this->idActivity;
      $this->MilestonePlanningElement->topId=null;
    } else {
      $this->MilestonePlanningElement->topRefType='Project';
      $this->MilestonePlanningElement->topRefId=$this->idProject;
      $this->MilestonePlanningElement->topId=null;;
    } 
    if (pq_trim($this->idProject)!=pq_trim($old->idProject) or pq_trim($this->idActivity)!=pq_trim($old->idActivity)) {
      $this->MilestonePlanningElement->wbs=null;
      $this->MilestonePlanningElement->wbsSortable=null;
    }
    $result=parent::save();
    
    if ($this->idResource!=$old->idResource and Parameter::getGlobalParameter('updateIncomingResponsibleFromMilestone')!='NO') {
      $link=new Link();
      $crit=array("ref2Type"=>"Milestone","ref2Id"=>$this->id,"ref1Type"=>"Incoming");
      $list=$link->getSqlElementsFromCriteria($crit);
      foreach ($list as $link) {
        $incom=new Incoming($link->ref1Id);
        if ($incom->idResource!=$this->idResource) {
          $incom->idResource=$this->idResource;
          $incom->save();
        }
      }
    }
    if ($this->idResource!=$old->idResource and Parameter::getGlobalParameter('updateDeliverableResponsibleFromMilestone')!='NO') {
      $link=new Link();
      $crit=array("ref2Type"=>"Milestone","ref2Id"=>$this->id,"ref1Type"=>"Deliverable");
      $list=$link->getSqlElementsFromCriteria($crit);
      foreach ($list as $link) {
        $deliv=new Deliverable($link->ref1Id);
        if ($deliv->idResource!=$this->idResource) {
          $deliv->idResource=$this->idResource;
          $deliv->save();
        }
      }
    }
    return $result;
  }
  
/** =========================================================================
   * control data corresponding to Model constraints
   * @param void
   * @return "OK" if controls are good or an error message 
   *  must be redefined in the inherited class
   */
  public function control(){
    $result="";
    $old=$this->getOld();
    if ($this->MilestonePlanningElement and $this->MilestonePlanningElement->id
      and ($this->idActivity!=$old->idActivity or $this->idProject!=$old->idProject)){
      if (pq_trim($this->idActivity)) {
        $parentType='Activity';
        $parentId=$this->idActivity;
      } else {
        $parentType='Project';
        $parentId=$this->idProject;
      }
      $result.=$this->MilestonePlanningElement->controlHierarchicLoop($parentType, $parentId);
    }
    if (pq_trim($this->idActivity) and ! SqlElement::isCopyInProgress()) {
      $parentActivity=new Activity($this->idActivity);
      if ($parentActivity->idProject!=$this->idProject) {
        $result.='<br/>' . i18n('msgParentActivityInSameProject');
      }
    }
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function getColor() {
    if (isset(self::$_cacheColor[$this->id])) return self::$_cacheColor[$this->id];
    $color="#FFFFFF";
    $critArray=array('refType'=>'Milestone', 'refId'=>$this->id);
    $planningElement = SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $critArray);
    if ($planningElement && $planningElement->color) {
      $color=$planningElement->color;
    }
    self::$_cacheColor[$this->id]=$color;
    return $color;
  }
  
  public function drawSpecificItem($item){
    global $print, $comboDetail;
    $result='';
    $array = array('Activity', 'ChangeRequest', 'Deliverable', 'Delivery', 'IncomingMain', 'ProductVersion', 'Requirement', 'Ticket');
    $idleModuleTargetMilestone=SqlElement::getRefField('module', '23', 'active');
    if ($idleModuleTargetMilestone == 1){
      if ($item=='DependencyObject' and $this->id) {
        $result.= '<table style="width:100%;"><tr>';
        $result.= '<td class="linkHeader sortable" style="width:20%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colElement').'</td>';
        $result.= '<td class="linkHeader sortable" style="width:55%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
        $result.= '<td class="linkHeader" style="width:15%">'.i18n('colState').'</td>';
        $result.= '<td class="linkHeader" style="width:15%">'.i18n('colResponsibleShort').'</td>';
        $result.= '</tr>';
        foreach ($array as $class){
          $obj = new $class();
          $lst=$obj->getSqlElementsFromCriteria(array('idMilestone'=>$this->id));
          foreach ($lst as $ob){
            $result.= '<tr style="width:100 %";>';
            $result.= '<td class="linkData" style="vertical-align:middle;" ><table style="width:100%">';
            if ($class=='IncomingMain'){
              $class='Incoming';
            }
            $result.= '<tr><td style="z-index:500;width:16px;height:16px;"><div onclick="gotoElement(\''.$class.'\',\''.$ob->id.'\')" class="imageColorNewGui icon'. $class .'16 icon'. $class .' iconSize16"></div></td>';
            $result.= '<td  class="classLinkName" onclick="gotoElement(\''.$class.'\',\''.$ob->id.'\');" style="padding-left:5px;">' .i18n($class). ' #'.$ob->id. '</td></tr></table></td>';
            $result.= '<td class="linkData classLinkName" onclick="gotoElement(\''.$class.'\',\''.$ob->id.'\');" style="vertical-align:middle;padding-left:5px;" >' .$ob->name. '</td>';
            if (isset($ob->idStatus)){
              $colorState=SqlList::getFieldFromId('status', $ob->idStatus, 'color');
              $foreColor=getForeColor($colorState);
              $result.= '<td class="linkData" style="text-align:center;vertical-align:middle;background-color:' .$colorState. ';color:'.$foreColor.';" >' .SqlList::getFieldFromId('status', $ob->idStatus, 'name'). '</td>';
            }else{
              $result.= '<td class="linkData"></td>';
            }
            if (isset($ob->idResource)){
              $result.= '<td class="linkData" style="text-align:center;vertical-align:middle;"><span style="display:inline-block;">'.formatUserThumb($ob->idResource, SqlList::getNameFromId('resource', $ob->idResource), 'Responsible').'</span></td>';
            }else{
              $result.= '<td class="linkData"></td>';
            }
            $result.= '</tr>';
          }
        }
        $result.= '</table>';
      }
    }
    return $result;
  }
  
  public function copyTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments = false, $withAffectations = false, $toProject = null, $toActivity = null, $copyToWithResult = false, $copyToWithActivityPrice=false, $copyToWithStatus = false,$copyToWithSubTask = false, $moveAfterCreate = null, $copyToWithDependency=false, $copyToWithPredecessor=false, $copyToWithSuccessor=false) {
    self::setCopyInProgress();
    $result=parent::copyTo( $newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments, $withAffectations, $toProject, $toActivity, $copyToWithResult, $copyToWithActivityPrice, $copyToWithStatus,$copyToWithSubTask, $moveAfterCreate);
    if($newClass == 'Milestone'){
      if($copyToWithDependency and $result->id){
        // Copy dependencies
        $newDep = new Dependency();
        $newDep->dependencyType = 'E-S';
        $newDep->predecessorRefType='Milestone';
        $newDep->predecessorRefId=$this->id;
        $crit=array('refType'=>'Milestone', 'refId'=>$this->id);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $newDep->predecessorId=$pe->id;
        $newDep->successorRefType='Milestone';
        $newDep->successorRefId=$result->id;
        $crit=array('refType'=>'Milestone', 'refId'=>$result->id);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $crit);
        $newDep->successorId=$pe->id;
        $newDep->save();
      }
    }
    if($copyToWithPredecessor and $result->id){
      // Copy predecessors
      $dep=New dependency();
      $crit = array('successorRefType'=>'Milestone', 'successorRefId'=>$this->id);
      $deps=$dep->getSqlElementsFromCriteria($crit);
      foreach ($deps as $dep) {
        $newDep = new Dependency();
        $newDep->dependencyType = $dep->dependencyType;
        $newDep->successorRefType='Milestone';
        $newDep->successorRefId=$result->id;
        $crit=array('refType'=>'Milestone', 'refId'=>$result->id);
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
      $crit = array('predecessorRefType'=>'Milestone', 'predecessorRefId'=>$this->id);
      $deps=$dep->getSqlElementsFromCriteria($crit);
      foreach ($deps as $dep) {
        $newDep = new Dependency();
        $newDep->dependencyType = $dep->dependencyType;
        $newDep->predecessorRefType='Milestone';
        $newDep->predecessorRefId=$result->id;
        $crit=array('refType'=>'Milestone', 'refId'=>$result->id);
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
}
?>