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
class Work extends GeneralWork {

	 public $idBill;
	 public $idWorkElement;
   public $idLeave;//Eliott - LEAVE MANAGEMENT	 
   public $inputUser;
   public $inputDateTime;
   public $isManual;
   private static $_skipLockControl=false;
   
	 private static $_colCaptionTransposition = array(
	     'workDate'=>'date'
	 );
	 private static $_fieldsAttributes=array(
	     "day"=>"hidden,noExport,noImport",
	     "week"=>"hidden,noExport,noImport",
	     "month"=>"hidden,noExport,noImport",
	     "year"=>"hidden,noExport,noImport",
	     "dailyCost"=>"hidden,noExport,noImport",
	     "dailyCostLocal"=>"hidden,noExport,noImport",
	     "idWorkElement"=>"hidden,noExport,noImport",
	     "idBill"=>"hidden,noExport"
	 );
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
  // ================================================================================================
  //
  // ================================================================================================
  
  public function control(){
    $result="";
//     $crit=array('periodRange'=>'week', 'periodValue'=>$this->week,'idResource'=>$this->idResource);
//     $obj=SqlElement::getSingleSqlElementFromCriteria('WorkPeriod', $crit);
//     if ($obj->validated=='1' or $obj->submitted=='1') {
//       $result.='<br/>' . i18n('errorWeekValidated');
//     }
    if (! $this->refType or ! $this->refId) {
      if (! $this->refType) $result.='<br/>' . i18n('messageMandatory', array(i18n('colRefType')));
      if (! $this->refId) $result.='<br/>' . i18n('messageMandatory', array(i18n('colRefId')));
      return $result;
    }
    if (! $this->idResource) {
      $result.='<br/>' . i18n('messageMandatory', array(i18n('colIdResource')));
      return $result;
    }
    if (! SqlElement::class_exists($this->refType)) {
      $result.='<br/>' . i18n('invalidClassName', array($this->refType,''));
      return $result;
    }
    $lockedPeriod=WorkPeriod::isLockedDate($this->workDate, $this->idResource);
    if ($lockedPeriod and ! self::$_skipLockControl) {
      $result.='<br/>' . i18n('error'.pq_ucfirst($lockedPeriod).'Validated'); 
    }
    $lockedImputation=LockedImputation::isLockedPeriodForProject($this->workDate, $this->idProject);
    if ($lockedImputation and ! self::$_skipLockControl) {
      $result.='<br/>' . i18n('errorMonthValidated'). ' ('.i18n($lockedImputation).')';
    }
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
    if ($this->idAssignment and !$this->idWorkElement) {
      $ass=new Assignment($this->idAssignment);
      if ($ass->idResource != $this->idResource) { // Resource of work different from resource of assignment 
        $res=new ResourceAll($ass->idResource); 
        if ($res->id and ! $res->isResourceTeam ) {
          $msg=i18n('errorWorkResource',array($this->idResource,$ass->idResource,htmlFormatDate($this->workDate),null,null,i18n($this->refType),$this->refId));
          $result.='<br/>'.$msg;
          errorLog("------------------------------");
          errorLog($msg);
          errorLog(i18n('Work'));
          errorLog($this);
          errorLog(i18n('Assignment'));
          errorLog($ass);
          errorLog("------------------------------");
        }
      }
    }
    $res=new Affectable($this->idResource,true);
    if (! $res->isResource) {
      $msg=i18n("errorCreateRights")."<br/>   ".i18n("Work")." : $this->work | $this->workDate <br/>   ".i18n("Resource")." : #$res->id - $res->name";
      errorLog("Try to store Work for non resource #$this->idResource - $res->name");
      errorLog("  Current user : #".getCurrentUserId());
      errorLog("  Current script : ".$_SERVER["SCRIPT_FILENAME"]);
      errorLog("  Message : ".str_replace('<br/>',' >>> ',$msg));
      $result.='<br/>'.$msg;
    }
    $defaultControl=parent::control();
    if ($defaultControl!='OK') {
      $result.=$defaultControl;
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }
  
  public function deleteControl() {
    $result='';
    // #8853 : Delete of line of work where work = 0 should never be rejected
    if (! $this->work) return 'OK';
    $lockedPeriod=WorkPeriod::isLockedDate($this->workDate, $this->idResource);
    if ($lockedPeriod and ! self::$_skipLockControl) {
      $result.='<br/>' . i18n('error'.pq_ucfirst($lockedPeriod).'Validated');
    }
    $lockedImputation=LockedImputation::isLockedPeriodForProject($this->workDate, $this->idProject);
    if ($lockedImputation and ! self::$_skipLockControl) {
      $result.='<br/>' . i18n('errorMonthValidated'). ' ('.i18n($lockedImputation).')';
    }
    if ($result=='') {
      $result .= parent::deleteControl();
    } else {
      $result .= '<br/>('.i18n('operationDelete').' '.i18n('Work').' | '.htmlFormatDate($this->workDate).' | '.i18n($this->refType).' #'.$this->refId.' | '.i18n('colWork').'='.Work::displayImputationWithUnit($this->work);
    }
    return $result;
  }
  
  function save() {
    Assignment::$_skipRightControl=true;
    // On saving remove corresponding planned work if exists
    $oldWork=0;
    $toDay=date("Y-m-d");
    if ($this->id) { // Update existing
      $old=new Work($this->id);
      $oldWork=$old->work;
    }
    $manualPlan=false;
    $additionalWork=$this->work-$oldWork;
    if ($additionalWork>0) {
      //florent
      $pe=new PlanningElement();
      $critArray=array('refType'=>$this->refType, 'refId'=>$this->refId);
      $pe=$pe->getSingleSqlElementFromCriteria('PlanningElement', $critArray);
      if($pe->idPlanningMode=='23'){
        $manualPlan=true;
      }
      //
      $crit=array('idAssignment'=>$this->idAssignment, 
                  'refType'=>$this->refType, 'refId'=>$this->refId, 
                  'idResource'=>$this->idResource,
                  'workDate'=>$this->workDate);
      $pw=new PlannedWork();
      $list=$pw->getSqlElementsFromCriteria($crit, null, null, 'workDate asc');
      $needReplanOtherProjects=(count($list)==0)?true:false;
      //$deletManPlan=false;
      if ($manualPlan) {
        foreach ($list as $pw) {
          $pw->delete();
        }
      } else {
        while ($additionalWork>0 and count($list)>0) {
          $pw=array_shift($list);
          if ($pw->work > $additionalWork) {
            $pw->work-=$additionalWork;
            $pw->save();
            $additionalWork=0;
          } else {
            $additionalWork-=$pw->work;
            $pw->delete();
          }
          if (count($list)==0 and isset($crit['workDate']) ) {
            $needReplanOtherProjects=true;
            unset($crit['workDate']);
            $list=$pw->getSqlElementsFromCriteria($crit, null, null, 'workDate asc');
          }
        }
      }
      //florent
      $pw=new PlannedWork();
      $pwm= new PlannedWorkManual();
      if($manualPlan){
        $pwmTable=$pwm->getDatabaseTableName();
        $pwTable=$pw->getDatabaseTableName();
        $w=new Work();
        $wTable=$w->getDatabaseTableName();
        $date=($this->workDate>$toDay)?$toDay:$this->workDate;
        $where="idAssignment=$this->idAssignment and refType='$this->refType' and refId=$this->refId and idResource=$this->idResource and workDate<='$date'";
        $wherePw=$where." and exists (select 'x' from $wTable w where w.workDate=$pwTable.workDate and w.idResource=$pwTable.idResource)";
        $wherePwm=$where." and exists (select 'x' from $wTable w where w.workDate=$pwmTable.workDate and w.idResource=$pwmTable.idResource)";
        $pw->purge($wherePw);
        //$pwm->purge($wherePwm);
      }
      if($this->workDate<=$toDay and $this->refType=='Activity'){
        $critArray=array("idResource"=>$this->idResource, "workDate"=>$this->workDate);
        $where="idAssignment<>$this->idAssignment and refType<>'$this->refType' and refId<>$this->refId'";
        $pwExist=$pw->getSqlElementsFromCriteria($critArray,null,$where);
        foreach ($pwExist as $value){
          $critPe=array("refType"=>$value->refType,"refId"=>$value->refId,"idProject"=>$value->idProject);
          $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $critPe);
          if($pe->idPlanningMode=="23"){
            $value->delete();
          }
        }
      }
      //
      if ($needReplanOtherProjects) {
        $idProj=($this->idProject)?$this->idProject:0;
        $where="idResource=$this->idResource and workDate='$this->workDate' and idProject!=$idProj";
        $list=$pw->getSqlElementsFromCriteria(null, null, $where, 'workDate asc');
        $arrayProjTreated=array();
        foreach ($list as $pw) {
          if (!isset($arrayProjTreated[$pw->idProject])) {
            $arrayProjTreated[$pw->idProject]=$pw->idProject;
            Project::setNeedReplan($pw->idProject);
          }
        }
      }
    }   
    global $cronnedScript;
    $this->inputUser=($cronnedScript==true)?null:getCurrentUserId();
    $this->inputDateTime=date('Y-m-d H:i:s');
    self::$_skipLockControl=false;
    if ($this->id and isset($old) and $old->work==$this->work) self::$_skipLockControl=true;
    $result=parent::save();
    self::$_skipLockControl=false;
    return $result;
  }
  
  public function saveWork() {
    Assignment::$_skipRightControl=true;
    if ($this->id) { // update existing work
      $old=$this->getOld();
      $result=$this->save();
      $this->updateAssignment($this->work-$old->work);
      return $result;
    } else { // add new work
      if (! $this->idResource and ! $this->idAssignment) { // idResource Mandatory
        return i18n('messageMandatory',array('idResource'));
      }
      if (! $this->workDate) { 
        if ($this->day) {
          $this->workDate=pq_substr($this->day,0,4).'-'.pq_substr($this->day,4,2).'-'.pq_substr($this->day,6,2);
        } else { // Work Date is mandatory
          return i18n('messageMandatory',array('workDate'));
        }
      }
      if (!$this->idAssignment) { // unknown assignment
        if ($this->refType and $this->refId) {
          $crit=array('refType'=>$this->refType,'refId'=>$this->refId,'idResource'=>$this->idResource);
          $ass = new Assignment();//SqlElement::getSingleSqlElementFromCriteria('Assignment', $crit);
          $assList = $ass->getSqlElementsFromCriteria($crit,null,null, 'leftWork DESC, id DESC');
          if(count($assList)>0)$ass=$assList[0];
          if ($ass->id) {
            $this->idAssignment=$ass->id;
          } else {
          	$crit=array('refType'=>$this->refType,'refId'=>$this->refId);
            $we = new WorkElement();//SqlElement::getSingleSqlElementFromCriteria('WorkElement', $crit);
            $weList = $we->getSqlElementsFromCriteria($crit,null,null, 'leftWork DESC, id DESC');
            if(count($weList)>0)$we=$weList[0];
            if ($we->id) {
              $this->idWorkElement=$we->id;
            } else {
              return i18n('noAssigmentForResourceElement',array(i18n($this->refType),$this->refId)); // could not retrieve assignment or workelement, so is mandatory
            }
          }
        }
      } else { // refType & refId can be retreived from assignment
        $ass=new Assignment($this->idAssignment);
        $this->refType=$ass->refType;
        $this->refId=$ass->refId;
        $this->idResource=$ass->idResource;
      }
      //$crit=array('idAssignment'=>$this->idAssignment,'workDate'=>$this->workDate); // retreive work for this assignment & day (assignment includes resource)
      //$work=SqlElement::getSingleSqlElementFromCriteria('Work', $crit);
      if ($this->idAssignment) {
        $crit=array('idAssignment'=>$this->idAssignment,'workDate'=>$this->workDate); // retreive work for this assignment & day (assignment includes resource)
        if (isset($ass)) {
          if ($ass->idResource!=$this->idResource) {
            return i18n('workDefinedWrongResourceElement',array('colIdAssigment',$this->idResource,$ass->id,$ass->idResource));//"ERROR work defined for Resource $this->idResource linked to Assignment $ass->id dedicated to resource $ass->idResource";
          }
          if ($ass->refType!=$this->refType or $ass->refId!=$this->refId) {
            return i18n('workReferingWrongResourceElement',array('colIdAssigment', i18n($this->refType),$this->refId,i18n($ass->refType),$ass->refId));//"ERROR work refering to $this->refType #$this->refId linked to Assignment refering to $ass->refType #$ass->refId";
          }
        }
      } else {
        $crit=array('idWorkElement'=>$this->idWorkElement,'workDate'=>$this->workDate); // retreive work for this assignment & day (assignment includes resource)
        if (isset($we)) {
          if ($we->refType!=$this->refType or $we->refId!=$this->refId) {
            return i18n('workReferingWrongResourceElement',array('colWorkElement', i18n($this->refType),$this->refId,i18n($we->refType),$we->refId));//"ERROR work refering to $this->refType #$this->refId linked to WorkElement refering to $we->refType #$we->refId";
          }
        }
      }
      $work=SqlElement::getSingleSqlElementFromCriteria('Work', $crit);
      if (isset($we) and $we->id) {
        $we->realWork+=$this->work;
        $we->save(true);
      }
      if ($work->id) {
        $work->work+=$this->work;
        $result=$work->save();
        $work->updateAssignment($this->work);
        return $result;
      } else {
        $this->setDates($this->workDate);
        $result=$this->save();
        $work->updateAssignment($this->work);
        return $result;
      }
    }
  }
   
  public function deleteWork() {
    Assignment::$_skipRightControl=true;
    $result=$this->delete();
    $this->updateAssignment($this->work*(-1));
    return $result;
  }
  
  public function delete() {
    $result=parent::delete();
    $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$this->refType,'refId'=>$this->refId));
    if ($pe->id and $pe->realEndDate and $pe->realEndDate==$this->workDate) {
      $pe->realEndDate=null;
      $pe->simpleSave();
    }
    return $result;
  }

  public function updateAssignment($decrementLeftWork=0) {
    Assignment::$_skipRightControl=true;
    $ass=new Assignment($this->idAssignment);
    $ass->leftWork-=$decrementLeftWork; // Remove current work from left work
    if ($ass->leftWork<0) $ass->leftWork=0;
    $resultAss=$ass->saveWithRefresh();
    return $resultAss;
  }
  
  public function getMenuClass() {
    return "menuActivity";
  }
}
?>