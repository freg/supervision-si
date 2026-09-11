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
 * RiskType defines the type of a risk.
 */ 
require_once('_securityCheck.php');
class ImputationWork extends Work {

  public $leftWork;
  
  private static $_colCaptionTransposition = array(
      'workDate'=>'date'
  );
  
  private static $_fieldsAttributes=array(
      "id"=>"hidden,noExport,noImport",
      "day"=>"hidden,noExport,noImport",
      "week"=>"hidden,noExport,noImport",
      "month"=>"hidden,noExport,noImport",
      "year"=>"hidden,noExport,noImport",
      "dailyCost"=>"hidden,noExport,noImport",
      "cost"=>"hidden,noExport,noImport",
      "idWorkElement"=>"hidden,noExport,noImport",  
      "idBill"=>"hidden,noExport,noImport",
      "manual"=>"hidden,noExport,noImport",
      "idLeave"=>"hidden,noExport,noImport",
      "inputUser"=>"hidden,noExport,noImport",
      "inputDateTime"=>"hidden,noExport,noImport",
      "idProject"=>"hidden,noExport,noImport"
  );
  
  private static $_databaseTableName = 'work';
   
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
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

  /** ========================================================================
   * Return the specific databaseTableName
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return $paramDbPrefix . self::$_databaseTableName;
  }

   /** ==========================================================================
   * Destructor
   * @return void
   */ 
  function __destruct() {
    parent::__destruct();
  }
  
  public function saveImputationWork() {
    $leftWork = $this->leftWork;
    unset($this->leftWork);
    
    // -- Control max days per day and per week on Import
    $resource = new Resource($this->idResource);
    if ($resource->maxDailyWork > 0) {
      $w = new Work();
      $existingDay = $w->sumSqlElementsFromCriteria('work', ['idResource' => $this->idResource,'workDate' => $this->workDate,]);
      if ($this->id) {
        $old = new Work($this->id);
        $existingDay -= $old->work;
      }
      if (round($existingDay + $this->work, 2) > round($resource->maxDailyWork, 2)) {
        $result  = '<div class="INVALID">';
        $result .= i18n('maxDailyWorkError',[Work::displayImputationWithUnit($resource->maxDailyWork)]);
        $result .= '</div>';
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        $result .= '<input type="hidden" id="lastOperation" value="save" />';
        return $result;
      }
    }  
    if ($resource->maxWeeklyWork > 0) {
      $week = date('oW', strtotime($this->workDate));
      $w = new Work();
      $existingWeek = $w->sumSqlElementsFromCriteria('work', ['idResource' => $this->idResource,'week'=> $week,]);
      if ($this->id) {
        $old = new Work($this->id);
        $existingWeek -= $old->work;
      }
      if (round($existingWeek + $this->work, 2) > round($resource->maxWeeklyWork, 2)) {
        $result  = '<div class="INVALID">';
        $result .= i18n('maxWeeklyWorkError',[Work::displayImputationWithUnit($resource->maxWeeklyWork)]);
        $result .= '</div>';
        $result .= '<input type="hidden" id="lastOperationStatus" value="INVALID" />';
        $result .= '<input type="hidden" id="lastOperation" value="save" />';
        return $result;
      }
    }
    // ---
       
    if($this->idAssignment){
      if ($this->refType and $this->refId and $this->idResource) {
        $crit=array('refType'=>$this->refType,'refId'=>$this->refId,'idResource'=>$this->idResource);
        $ass=SqlElement::getSingleSqlElementFromCriteria('Assignment', $crit);
        if($this->idAssignment != $ass->id){
          return i18n('idAssignmentNoMatchResourceElement');
        }
      }
    }
    $result = parent::saveWork();
    $this->updateAssignmentImputation($leftWork);
    return $result;
  }
  
  public function updateAssignmentImputation($leftWork) {
    $ass=new Assignment($this->idAssignment);
    if($leftWork!==null){
      $ass->leftWork=$leftWork;
    }
    if(isset($this->leftWork))unset($this->leftWork);
    if ($ass->leftWork<0) $ass->leftWork=0;
    $resultAss=$ass->saveWithRefresh();
    return $resultAss;
  }
}