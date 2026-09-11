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

class EpicMain extends SqlElement {
  public $_sec_Description;
  public $id;
  public $reference;
  public $name;
  public $idProject;
  public $idEpicType;
  public $idSprint;
  public $description;
  public $creationDate;
  public $lastUpdateDateTime;
  public $idUser;
  public $_sec_treatment;
  public $idStatus;
  public $storyPoints;
  public $businessValue;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $cancelled;
  public $_lib_cancelled;
  public $result;
  public $_sec_UserStory;
  public $_spe_UserStory;
  public $_nbColMax=3;
  
  private static $_inStatusRecalc = false;
  
  private static $_layout = '
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="10%" >${idProject}</th>
    <th field="name" width="25%" >${name}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>';
  
  private static $_fieldsAttributes = array(
      "id" => "nobr",
      "reference" => "readonly", 
      "name" => "required",
      "idEpicType"=>"required",
      "idProject" => "required",
      "idStatus" => "required",
      "storyPoints" => "readonly",
      "businessValue" => "readonly",
      "creationDate" => "required",
      "handled" => "nobr",
      "done" => "nobr",
      "idle" => "nobr",
      "idleDate" => "nobr",
      "cancelled" => "nobr"
  );
  
  private static $_colCaptionTransposition = array(
      'idUser' => 'issuer'
  );

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
  
  function save() {
    $old = $this->getOld (false);
    SqlElement::$_skipWorkflowControl=true;
    if($old->idSprint != $this->idSprint){
      $userStoryList = $old->getUserStoryList(true, true);
      foreach ($userStoryList as $userStory){
        $userStory->idSprint = $this->idSprint;
        $userStory->save();
      }
    }
    
    $result = parent::save ();
    
    if ($old->idSprint != $this->idSprint && !self::$_inStatusRecalc) {
      self::$_inStatusRecalc = true;
      $this->updateStatusFromUserStory();
      self::$_inStatusRecalc = false;
    }
    
    SqlElement::$_skipWorkflowControl=false;
    $userStoryList = $this->getUserStoryList();
    $storyPoints = 0;
    $businessValue = 0;
    foreach ($userStoryList as $userStory){
      $storyPoints += $userStory->storyPoints;
      $businessValue += $userStory->businessValue;
    }
    $this->storyPoints = $storyPoints;
    $this->businessValue = $businessValue;
    
    return $result;
  }
  
  public function getUserStoryList($withSameSprint=false, $notDone=false){
    if(!$this->id)return array();
    $userStory = new UserStory();
    $where = "idEpic = ".$this->id;
    if($withSameSprint){
      $where .= ($this->idSprint)?" AND idSprint = '".$this->idSprint."'":" AND idSprint IS NULL";
    }
    $where .= ($notDone)?" AND done = '0'":"";
    $userStoryList = $userStory->getSqlElementsFromCriteria(null,null,$where);
    return $userStoryList;
  }
  
  public function updateStoryPointAndBusinessValue(){
    $userStoryList = $this->getUserStoryList();
    $storyPoints = 0;
    $businessValue = 0;
    foreach ($userStoryList as $userStory){
      $storyPoints += $userStory->storyPoints;
      $businessValue += $userStory->businessValue;
    }
    $this->storyPoints = $storyPoints;
    $this->businessValue = $businessValue;
    $this->save();
  }
  
  public function updateStatusFromUserStory() {
    $list = $this->getUserStoryList();
    if (!$list || !count($list))return;
    
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
    if($item == "UserStory"){
      drawUserStoryFromObject($this);
    }
  }
}
