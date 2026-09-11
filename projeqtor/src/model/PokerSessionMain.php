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
 * Stauts defines list stauts an activity or action can get in (lifecylce).
 */ 
require_once('_securityCheck.php');

class PokerSessionMain extends SqlElement {

  public $_sec_description;
  public $id;
  public $idUser;
  public $name;
  public $idPokerSessionType;
  public $idStatus;
  public $idProject;
  public $pokerSessionDate;
  public $_lib_from;
  public $pokerSessionStartTime;
  public $_lib_to;
  public $pokerSessionEndTime;
  public $_spe_startPokerSession;
  public $_spe_pausePokerSession;
  public $idResource;
  public $handled;
  public $handledDate;
  public $done;
  public $doneDate;
  public $idle;
  public $idleDate;
  public $description;
  public $result;
  public $_sec_Attendees;
  public $_spe_showClosedAssignment;
  public $_Assignment=array();
  public $_sec_pokerItem;
  public $_spe_pokerItem;
  public $_sec_progress_left;
  public $PokerSessionPlanningElement;
  public $pokerSessionStartDateTime;
  public $pokerSessionEndDateTime;
  public $_sec_pokerVote;
  public $_spe_pokerVote;
  public $_sec_predecessor;
  public $_Dependency_Predecessor=array();
  public $_sec_successor;
  public $_Dependency_Successor=array();
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_nbColMax=3;
  
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="name" width="15%">${name}</th>
    <th field="nameProject" width="15%">${idProject}</th>
    <th field="pokerSessionDate" width="10%" formatter="dateFormatter">${date}</th>
    <th field="nameResource" formatter="thumbName22" width="15%">${responsible}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>
    ';
  
  private static $_fieldsAttributes=array(
      "idProject"=>"required",
      "idUser"=>"hidden",
  		"idStatus"=>"required",
  		"idPokerSessionType"=>"required",
  		"pokerSessionDate"=>"required, nobr",
  		"_lib_from"=>'nobr',
  		"pokerSessionStartTime"=>'nobr',
  		"_lib_to"=>'nobr',
  		"idResource"=>"required",
  		"handled"=>"readonly, nobr",
  		"done"=>"readonly, nobr",
  		"idle"=>"nobr",
  		"pokerSessionStartDateTime"=>"hidden",
  		"pokerSessionEndDateTime"=>"hidden",
        "result"=>"hidden"
  );
  
  private static $_colCaptionTransposition = array('idResource'=> 'responsible',
                                                  'attendees'=>'otherAttendees',
                                                  'pokerSessionStartDateTime'=>'pokerSessionStartTime',
                                                  'pokerSessionEndDateTime'=>'pokerSessionEndTime'
  );
  
  public function setAttributes() {
    if(!$this->id){
    	self::$_fieldsAttributes ['_button_startEndPokerSession'] = 'hidden';
    }
  }
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if(!$this->id){
    	$user = getSessionUser();
    	if($user->isResource){
    		$this->idResource = $user->id;
    	}
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
  
  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********
  
  /** ==========================================================================
   * Return the validation sript for some fields
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
  	$colScript = parent::getValidationScript($colName);
  
  	if ($colName=="idStatus") {
  		$colScript .= '<script type="dojo/connect" event="onChange" >';
  		$colScript .= htmlGetJsTable('Status', 'setHandledStatus', 'tabStatusHandled');
  		$colScript .= htmlGetJsTable('Status', 'setIdleStatus', 'tabStatusIdle');
  		$colScript .= htmlGetJsTable('Status', 'setDoneStatus', 'tabStatusDone');
  		$colScript .= '  var setHandled=0;';
  		$colScript .= '  var filterStatusHandled=dojo.filter(tabStatusHandled, function(item){return item.id==dijit.byId("idStatus").value;});';
  		$colScript .= '  dojo.forEach(filterStatusHandled, function(item, i) {setHandled=item.setHandledStatus;});';
  		$colScript .= '  if (setHandled==1) {';
  		$colScript .= '    startPokerSession('.$this->id.')';
  		$colScript .= '  } else {';
  		$colScript .= '    dijit.byId("handled").set("checked", false);';
  		$colScript .= '  }';
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
  		$colScript .= '    stopPokerSession('.$this->id.')';
  		$colScript .= '  } else {';
        $colScript .= '    dijit.byId("done").set("checked", false);';
        $colScript .= '  }';
  		$colScript .= '  formChanged();';
  		$colScript .= '</script>';
  	} else if ($colName=="idle") {
  		$colScript .= '<script type="dojo/connect" event="onChange" >';
  		$colScript .= '  if (this.checked) { ';
  		$colScript .= '    if (dijit.byId("idleDate").get("value")==null) {';
  		$colScript .= '      var curDate = new Date();';
  		$colScript .= '      dijit.byId("idleDate").set("value", curDate); ';
  		$colScript .= '    }';
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
  		$colScript .= '    if (dijit.byId("idle").get("checked")) {';
  		$colScript .= '      dijit.byId("idle").set("checked", false);';
  		$colScript .= '    }';
  		$colScript .= '  } ';
  		$colScript .= '  formChanged();';
  		$colScript .= '</script>';
  	} else if ($colName=="handled") {
  		$colScript .= '<script type="dojo/connect" event="onChange" >';
  		$colScript .= '  if (this.checked) { ';
  		$colScript .= '    if (dijit.byId("handledDate").get("value")==null) {';
  		$colScript .= '      var curDate = new Date();';
  		$colScript .= '      dijit.byId("handledDate").set("value", curDate); ';
  		$colScript .= '    }';
  		$colScript .= '  } else {';
  		$colScript .= '    dijit.byId("handledDate").set("value", null); ';
  		$colScript .= '    if (dijit.byId("idle").get("checked")) {';
  		$colScript .= '      dijit.byId("idle").set("checked", false);';
  		$colScript .= '    }';
  		$colScript .= '  } ';
  		$colScript .= '  formChanged();';
  		$colScript .= '</script>';
  	}
  	return $colScript;
  }
  
  public function save() {
    $result = null;
    $old = $this->getOld (false);
	$oldResource = $old->idResource;
	
	if (! $this->name) {
		$this->name=SqlList::getNameFromId('PokerSessionType',$this->idPokerSessionType) . " " . $this->pokerSessionDate;
	}
	$this->PokerSessionPlanningElement->idle=$this->idle;
	$this->PokerSessionPlanningElement->done=$this->done;
	$this->PokerSessionPlanningElement->validatedStartDate=$this->pokerSessionDate;
	$this->PokerSessionPlanningElement->validatedEndDate=$this->pokerSessionDate;
	if (! $this->PokerSessionPlanningElement->assignedWork) {
		$this->PokerSessionPlanningElement->plannedStartDate=$this->pokerSessionDate;
		$this->PokerSessionPlanningElement->plannedEndDate=$this->pokerSessionDate;
	}
	
	if (pq_trim($this->idProject)!=pq_trim($old->idProject)) {
		$this->PokerSessionPlanningElement->wbs=null;
		$this->PokerSessionPlanningElement->wbsSortable=null;
	}
	
	$this->pokerSessionStartDateTime=$this->pokerSessionDate.' '.$this->pokerSessionStartTime;
	$this->pokerSessionEndDateTime=$this->pokerSessionDate.' '.$this->pokerSessionEndTime;
	
	if(!$this->handled and $this->handledDate)$this->handledDate=null;
	if(!$this->done and $this->doneDate)$this->doneDate=null;
	if(!$this->idle and $this->idleDate)$this->idleDate=null;
	
    $result = parent::save ();
    if (! pq_strpos ( $result, 'id="lastOperationStatus" value="OK"' )) {
      return $result;
    }
	if(!$old->id){
	  $proj=new Project($this->idProject,true);
	  $type=new Type($proj->idProjectType);
	  $resource=$this->idResource;
	  if ($resource and pq_trim ( $resource ) != '' and pq_stripos ( $result, 'id="lastOperationStatus" value="OK"' ) > 0) {
	  	// Add assignment for responsible
	  	$habil = SqlElement::getSingleSqlElementFromCriteria ( 'HabilitationOther', array(
	  			'idProfile' => getSessionUser ()->getProfile ( $this->idProject ),
	  			'scope' => 'assignmentEdit') );
	  	if ($habil and $habil->rightAccess == 1) {
	  		$ass = new Assignment ();
	  		$crit = array('idResource' => $resource, 'refType' => 'PokerSession', 'refId' => $this->id);
	  		$cpt=$ass->countSqlElementsFromCriteria($crit);
	  		if ($cpt == 0) {
	  			$ass->idProject = $this->idProject;
	  			$ass->refType = 'PokerSession';
	  			$ass->refId = $this->id;
	  			$ass->idResource = $resource;
	  			$ass->assignedWork = Work::displayWork(workTimeDiffDateTime('2000-01-01T'.$this->pokerSessionStartTime,'2000-01-01T'.$this->pokerSessionEndTime));
	  			$ass->realWork = 0;
	  			$ass->leftWork = Work::displayWork(workTimeDiffDateTime('2000-01-01T'.$this->pokerSessionStartTime,'2000-01-01T'.$this->pokerSessionEndTime));
	  			$ass->plannedWork = Work::displayWork(workTimeDiffDateTime('2000-01-01T'.$this->pokerSessionStartTime,'2000-01-01T'.$this->pokerSessionEndTime));
	  			$ass->notPlannedWork = 0;
	  			$ass->rate = '100';
	  			if ($this->PokerSessionPlanningElement->validatedWork and $this->PokerSessionPlanningElement->validatedWork>$this->PokerSessionPlanningElement->assignedWork) {
	  				$ass->assignedWork=$this->PokerSessionPlanningElement->validatedWork-$this->PokerSessionPlanningElement->assignedWork;
	  				$ass->leftWork=$ass->assignedWork;
	  			}
	  			$ass->save();
	  		}
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
  	$old= $this->getOld();
  	$pItem = new PokerItem();
  	$nbItem = $pItem->countSqlElementsFromCriteria(array('idPokerSession'=>$this->id));
  	if(!$nbItem){
  	  $status = new Status($this->idStatus);
  	  if($this->idStatus != $old->idStatus and $status->setHandledStatus){
  	    $result.='<br/>' . i18n('msgNoItemInPokerSession');
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
  
  public function drawSpecificItem($item) {
  global $print;
    $canUpdate=securityGetAccessRightYesNo('menuPokerSession', 'update', $this) == "YES";
    $result = "";
    $pItem = new PokerItem();
    $noItem = $pItem->countSqlElementsFromCriteria(array('idPokerSession'=>$this->id));
    if($item=="startPokerSession"){
    	if ($print or !$canUpdate or !$this->id or $this->idle or !$noItem or !$this->handled or $this->done) {
    		return "";
    	}
    	$name=(!$this->handled or $this->done)?i18n('pokerSessionStart'):i18n('pokerSessionStop');
    	$result .= '<tr><td valign="top" class="label"><label></label></td><td>';
    	$result .= '<button id="startPokerSession" dojoType="dijit.form.Button" showlabel="true"';
    	$result .= ' title="' . $name . '" class="roundedVisibleButton">';
    	$result .= '<span>' . $name. '</span>';
    	$result .=  '<script type="dojo/connect" event="onClick" args="evt">';
    	$result .= '   if (checkFormChangeInProgress()) {return false;}';
    	if(!$this->handled or $this->done){
    		$result .=  '  startPokerSession('.$this->id.');';
    	}else{
    		$result .=  '  stopPokerSession('.$this->id.');';
    	}
    	$result .= '</script>';
    	$result .= '</button>';
    	$result .= '</td></tr>';
    	return $result;
    }
    if($item=="pausePokerSession"){
        $st = new Status($this->idStatus);
    	if ($print or !$canUpdate or !$this->id or $this->idle or !$noItem or $this->done or !$st->setHandledStatus) {
    		return "";
    	}
    	$name=($this->handled)?i18n('pokerSessionPauseStart'):i18n('pokerSessionPauseStop');
    	$result .= '<tr><td valign="top" class="label"><label></label></td><td>';
    	$result .= '<button id="pausePokerSession" dojoType="dijit.form.Button" showlabel="true"';
    	$result .= ' title="' . $name . '" class="roundedVisibleButton">';
    	$result .= '<span>' . $name. '</span>';
    	$result .=  '<script type="dojo/connect" event="onClick" args="evt">';
    	$result .= '   if (checkFormChangeInProgress()) {return false;}';
  		$result .=  '  pausePokerSession('.$this->id.');';
    	$result .= '</script>';
    	$result .= '</button>';
    	$result .= '</td></tr>';
    	return $result;
    }
    if($item=="pokerItem"){
    	drawPokerItem($this);
    }
    if($item=="pokerVote"){
    	drawPokerVote($this);
    }
    
    if (!$print and $item=='showClosedAssignment'){
      $showClosed=(Parameter::getUserParameter($item)=='1' or Parameter::getUserParameter($item)=='')?true:false;
      $result.='<div style="position:absolute;right:60px;top:3px;">';
      $result.='<label for="'.$item.'" class="dijitTitlePaneTitle" style="border:0;font-weight:normal !important;height:'.((isNewGui())?'20':'10').'px;width:'.((isNewGui())?'50':'150').'px">'.i18n('labelShowIdle'.((isNewGui())?'Short':'')).'</label>';
      if ($this->idle == 1){
        $result.='<div id="'.$item.'" style="'.((isNewGui())?'margin-top:14px':'').'" dojoType="dijit.form.CheckBox" type="checkbox" '.('checked').' readonly';
        $result.=' title="'.i18n('labelShowIdle').'" >';
      }else{
        $result.='<div id="'.$item.'" style="'.((isNewGui())?'margin-top:14px':'').'" dojoType="dijit.form.CheckBox" type="checkbox" '.(($showClosed)?'checked':'');
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
    }
  }
}?>