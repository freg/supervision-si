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

class TicketMain extends SqlElement {

  public $_sec_description;
  public $id; 
  public $reference;
  public $name;
  public $tags;
  public $idProject;
  public $idTicketType;
  public $externalReference;
  public $idUrgency;
  public $creationDateTime;
  public $lastUpdateDateTime;
  public $idUser;
  public $idContact;
  public $Origin;
  public $idTicket;
  public $idContext1;
  public $idContext2;
  public $idContext3;
  public $description;
  public $_sec_treatment;
  public $idActivity;
  public $idStatus;
  public $idResolution;
  public $isRegression;
  public $idAccountable;
  public $idResource;
  public $idCriticality;
  public $idPriority;
  public $idMilestone;
  public $_tab_2_1 = array('initial', 'actual','dueDate');
  public $initialDueDateTime; 
  public $actualDueDateTime;
  public $delayReadOnly;
  public $WorkElement;
  public $handled;
  public $handledDateTime;
  public $paused;
  public $pausedDateTime;
  public $_button_showStatusPeriod;
  public $done;
  public $doneDateTime;
  public $solved;
  public $_lib_colSolved;
  public $idle;
  public $idleDateTime;
  public $cancelled;
  public $_lib_cancelled;
  public $result;
  public $_sec_productComponent;
  public $idProduct;
  public $idComponent;
  public $idOriginalProductVersion;
  public $_OtherOriginalProductVersion=array();
  public $idOriginalComponentVersion;
  public $_OtherOriginalComponentVersion=array();
  public $idTargetProductVersion;
  public $_OtherTargetProductVersion=array();
  public $idTargetComponentVersion;
  public $_OtherTargetComponentVersion=array();
  public $_sec_ToDoList;
  public $_SubTask;
  public $_sec_vote;
  public $VotingItem;
  public $_sec_Link;
  public $_Link=array();
  public $_Attachment=array();
  public $_Note=array();
  public $_OtherClient=array();
  public $_nbColMax=3;
  
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%" ># ${id}</th>
    <th field="nameProject" width="15%">${idProject}</th>
    <th field="nameTicketType" width="15%" >${idTicketType}</th>
    <th field="name" width="25%">${name}</th>
    <th field="colorNameStatus" width="15%" formatter="colorNameFormatter">${idStatus}</th>
    <th field="actualDueDateTime" width="10%" formatter="dateTimeFormatter">${actualDueDateTime}</th>
    <th field="nameResource" formatter="thumbName22" width="15%">${responsible}</th>
    ';

  private static $_fieldsAttributes=array("id"=>"nobr", "reference"=>"readonly",
                                  "name"=>"required", 
                                  "idProject"=>"required",
                                  "idTicketType"=>"required",
                                  "idStatus"=>"required",
                                  "creationDateTime"=>"required",
                                  "handled"=>"nobr",
                                  "done"=>"nobr",
                                  "idle"=>"nobr",
                                  "idleDateTime"=>"nobr",
                                  "cancelled"=>"nobr",
                                  "idContext1"=>"nobr,size1/3,title",
                                  "idContext2"=>"nobr,size1/3,title",
                                  "idContext3"=>"size1/3,title",
                                  "doneDateTime"=>"nobr",
                                  "solved"=>"nobr",
                                  "idActivity"=>"title",
                                  "delayReadOnly"=>"hidden",
                                  "paused"=>"nobr",
                                  "pausedDateTime"=>"nobr",
  );  
  
  private static $_colCaptionTransposition = array('idUser'=>'issuer', 
                                                   'idResource'=> 'responsible',
                                                   'idActivity' => 'planningActivity',
                                                   'idContact' => 'requestor',
                                                   'idTargetVersion'=>'targetVersion',
                                                   'idOriginalVersion'=>'originalVersion',
                                                   'idTicket'=>'duplicateTicket',
                                                   'idContext1'=>'idContext',
                                                    'paused'=>'inPaused');
  
  private static $_databaseColumnName = array('idTargetVersion'=>'idVersion');
    
  private static $_fieldsTooltip = array(
      "idActivity"=> ""
  );
  
   /** ==========================================================================
   * Constructor
   * @param $id Int the id of the object in the database (null if not stored yet)
   * @return void
   */ 
  function __construct($id = NULL, $withoutDependentObjects=false) {
    parent::__construct($id,$withoutDependentObjects);
    if ($withoutDependentObjects) return;
    if ($this->idActivity and is_object($this->WorkElement) and $this->WorkElement->realWork>0) {
      self::$_fieldsAttributes['idActivity']='readonly';
    }
    if (Parameter::getGlobalParameter('realWorkOnlyForResponsible')=='YES') {
      if ($this->id and $this->idResource != getSessionUser()->id) {
        WorkElement::lockRealWork();
      }
    }
    if (!$this->id) {
      $this->idContact=getSessionUser()->id;
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
  
  protected function getStaticFieldsTooltip() {
    return self::$_fieldsTooltip;
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
   * @return String the validation javascript (for dojo framework)
   */
  public function getValidationScript($colName) {
    $colScript = parent::getValidationScript($colName);
    if ($colName=="idCriticality" or $colName=="idUrgency") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';  
      $colScript .= htmlGetJsTable('Urgency', 'value');
      $colScript .= htmlGetJsTable('Criticality', 'value');
      $colScript .= htmlGetJsTable('Priority', 'value');
      $colScript .= '  var urgencyValue=0; var criticalityValue=0; var priorityValue=0;';
      $colScript .= '  var filterUrgency=dojo.filter(tabUrgency, function(item){return item.id==dijit.byId("idUrgency").value;});';
      $colScript .= '  var filterCriticality=dojo.filter(tabCriticality, function(item){return item.id==dijit.byId("idCriticality").value;});';
      $colScript .= '  dojo.forEach(filterUrgency, function(item, i) {urgencyValue=item.value;});';
      $colScript .= '  dojo.forEach(filterCriticality, function(item, i) {criticalityValue=item.value;});';
      $colScript .= '  calculatedValue = Math.round(urgencyValue*criticalityValue/2);';
      $colScript .= '  var filterPriority=dojo.filter(tabPriority, function(item){return item.value==calculatedValue;});';
      $colScript .= '  if ( filterPriority.length==0) {';
      $colScript .= '    filterPriority=dojo.filter(tabPriority, function(item,i){if (i==0) return true; else return item.value<=calculatedValue;});';
      $colScript .= '  }';
      $colScript .= '  if (trim(dijit.byId("idUrgency").value) && trim(dijit.byId("idCriticality").value))';
      $colScript .= '    dojo.forEach(filterPriority, function(item, i) {dijit.byId("idPriority").set("value",item.id);});';
      $colScript .= '  else dijit.byId("idPriority").reset();';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    } else if ($colName=="actualDueDateTime") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var upd=dijit.byId("initialDueDateTime");';
      $colScript .= '  if (upd && upd.get("value")==null) { ';
      $colScript .= '    upd.set("value", this.value); ';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';      
      $colScript .= '</script>';     
    } else if ($colName=="actualDueDateTimeBis") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var upd=dijit.byId("initialDueDateTimeBis");';
      $colScript .= '  if (upd && upd.get("value")==null) { ';
      $colScript .= '    upd.set("value", this.value); ';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';     
    } else if ($colName=="initialDueDateTime") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var upd=dijit.byId("actualDueDateTime");';
      $colScript .= '  if (upd && upd.get("value")==null) { ';
      $colScript .= '    upd.set("value", this.value); ';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';     
    } else if ($colName=="initialDueDateTimeBis") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var upd=dijit.byId("actualDueDateTimeBis");';
      $colScript .= '  if (upd && upd.get("value")==null) { ';
      $colScript .= '    upd.set("value", this.value); ';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';     
    } else if ($colName=="idProduct" or $colName=="idComponent") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  if (this.value) {';
      $colScript .= '    var idP=dijit.byId("idProduct").get("value");';
      $colScript .= '    var idC=dijit.byId("idComponent").get("value");';
      $colScript .= '    var idR=dijit.byId("idResource").get("value");';
      $colScript .= '    dojo.xhrGet({';
      $colScript .= '      url: "../tool/getSingleData.php?dataType=responsible&idProduct="+idP+"&idComponent="+idC+"&idResource="+idR+addTokenIndexToUrl(),';
      $colScript .= '      handleAs: "text",';
      $colScript .= '      load: function (data) {';
      $colScript .= '        if (data) {';
      $colScript .= '          refreshList("idResource", "idProject", dijit.byId("idProject").get("value"), data, null, dijit.byId("idResource").get("required"));';
      $colScript .= '          dijit.byId("idResource").set("value",data);';
      $colScript .= '        }';
      $colScript .= '      }';
      $colScript .= '    });';
      $colScript .= '  };';
      
      //ADD by qCazelles - Business features
      if ($colName=="idProduct") $colScript .= 'if (dijit.byId("idBusinessfeature")) {dijit.byId("idBusinessfeature").set("value", "");refreshList("idBusinessfeature", "idProduct", dijit.byId("idProduct").get("value"));}';
      //END ADD
      
      $colScript .= '</script>';
    }
    
    if ($colName=="done") {
      $colScript .= '<script type="dojo/connect" event="onChange" >';
      $colScript .= '  var done=dijit.byId("done").get("checked");';
      $colScript .= '  var real=dijit.byId("WorkElement_realWork").get("value");';
      $colScript .= '  var planned=dijit.byId("WorkElement_plannedWork").get("value");';
      $colScript .= '  if (done) {';
      $colScript .= '    dijit.byId("WorkElement_leftWork").set("value", 0);';
      $colScript .= '  } else {';
      $colScript .= '    var left=planned-real;';
      $colScript .= '    if (left<0) left=0;';
      $colScript .= '    dijit.byId("WorkElement_leftWork").set("value", left);';
      $colScript .= '  } ';
      $colScript .= '  formChanged();';
      $colScript .= '</script>';
    }
    return $colScript;
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
    // TODO : if planned changed so that left is null, control still blocks
    // if (isset($this->WorkElement)) {
    //   $this->WorkElement->leftWork=$this->WorkElement->plannedWork-$this->WorkElement->realWork;
    // }
    if (pq_trim($this->idActivity)) {    
      $parentActivity=new Activity($this->idActivity);
      if ($parentActivity->idProject!=$this->idProject and ! SqlElement::$_skipProjectControl) {
        if (SynchronizedItems::getSynchronizedItemKey('Ticket',$this->id)==null) $result.='<br/>' . i18n('msgPlanningActivityInSameProject');
      }
    }
    if ($this->id and pq_trim($old->idActivity) and pq_trim($this->idActivity)!=pq_trim($old->idActivity) and $this->WorkElement->realWork>0)  {
      $result .='<br/>' . i18n ( 'msgPlanningActivityWithWork' );
    }
    
    if ($this->idTicket) {
    	if ($this->idTicket==$this->id) {
    		$result.='<br/>' . i18n('duplicateIsSame');
    	} else {
    	  $duplicate=new Ticket($this->idTicket);
    	  if ($duplicate->idTicket and $duplicate->idTicket!=$this->id) {
    		  $result.='<br/>' . i18n('duplicateAlreadyLinked');
    	  }
    	}
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
    $canDeleteRealWork = false;
    $crit = array('idProfile' => getSessionUser()->getProfile ( $this ), 'scope' => 'canDeleteRealWork');
    $habil = SqlElement::getSingleSqlElementFromCriteria ( 'HabilitationOther', $crit );
    if ($habil and $habil->id and $habil->rightAccess == '1') {
    	$canDeleteRealWork = true;
    }
    if ($this->WorkElement and $this->WorkElement->realWork>0 and !$canDeleteRealWork) {
      $result.='<br/>' . i18n('msgUnableToDeleteRealWork');
    }
    if ($result=='') {
      $result .= parent::deleteControl();
    }
    return $result;
  }
  public function save() {
  	$old=$this->getOld();
  	if (! pq_trim($this->creationDateTime)) {
  	  $this->creationDateTime=date('Y-m-d H:i');
  	}
  	//delay
  	if ($this->idTicketType != $old->idTicketType or $this->idUrgency != $old->idUrgency
  	    or $this->creationDateTime != $old->creationDateTime or $this->idProject != $old->idProject) {
  	      //find with project
  	      $critArray=array('idTicketType'=>$this->idTicketType, 'idUrgency'=>$this->idUrgency, 'idle'=>'0', 'idProject'=>$this->idProject);
  	      $myDelai = $this->getSingleSqlElementFromCriteria('TicketDelay', $critArray);
  	      if($myDelai->id){
  	        $unit=new DelayUnit($myDelai->idDelayUnit);
  	        $this->initialDueDateTime=addDelayToDatetime($this->creationDateTime,$myDelai->value, $unit->code, $this->idProject);
  	        if (! pq_trim($this->actualDueDateTime) or ($old->actualDueDateTime==$old->initialDueDateTime
  	            and $old->actualDueDateTime==$this->actualDueDateTime) ) {
  	          $this->actualDueDateTime=$this->initialDueDateTime;
  	          $this->delayReadOnly = 1;
  	        }
  	      }else{
    	      //find without
    	      $crit=array('idTicketType'=>$this->idTicketType, 'idUrgency'=>$this->idUrgency, 'idle'=>'0','idProject'=>null);
            $ticketDelay = new TicketDelay();
            $delayList=$ticketDelay->getSqlElementsFromCriteria($crit);
            foreach ($delayList as $delay){
          		if ($delay and !$delay->id) {
          		  $proj = new Project($this->idProject);
          		  if($proj->idProject){
          		    $topList = $proj->getTopProjectList(true);
          		  	foreach ($topList as $id){
          		  		$crit=array('idTicketType'=>$this->idTicketType, 'idUrgency'=>$this->idUrgency, 'idle'=>'0', 'idProject'=>$id);
          		  		$delay=SqlElement::getSingleSqlElementFromCriteria('TicketDelay', $crit);
          		  		if($delay and $delay->id){
          		  			break;
          		  		}
          		  	}
          		  }else{
          		    $crit=array('idTicketType'=>$this->idTicketType, 'idUrgency'=>$this->idUrgency, 'idle'=>'0','idProject'=>'');
          		    $delay=SqlElement::getSingleSqlElementFromCriteria('TicketDelay', $crit);
          		  }
          		}
        		if ($delay and $delay->id and $delay->idMacroTicketStatus == 2) {
        			$unit=new DelayUnit($delay->idDelayUnit);
        			$this->initialDueDateTime=addDelayToDatetime($this->creationDateTime,$delay->value, $unit->code, $this->idProject);
        			if (! pq_trim($this->actualDueDateTime) or ($old->actualDueDateTime==$old->initialDueDateTime 
        			                                     and $old->actualDueDateTime==$this->actualDueDateTime) ) {
        			  $this->actualDueDateTime=$this->initialDueDateTime;   
        			  $this->delayReadOnly = 1;                           	
        			}
        		}
          }
  	  }
  	}
  	if (isset($this->WorkElement)) {
  	  $this->WorkElement->done=$this->done;
  	  $this->WorkElement->idle=$this->idle;
  	}
  	if ($old->idActivity!=$this->idActivity and $this->idActivity) {
  		$act=new Activity($this->idActivity);
  		if ($act->idTargetProductVersion) {
  			$this->idTargetProductVersion=$act->idTargetProductVersion;
  			$vers=new Version($act->idTargetProductVersion);
  			if ($vers->idProduct) {
  				$this->idProduct=$vers->idProduct;
  			}
  		}
  	}
  	$responsibleFromProduct=Parameter::getGlobalParameter('responsibleFromProduct');
  	if (!$responsibleFromProduct) $responsibleFromProduct='always';
  	if ($responsibleFromProduct=='always' or ($responsibleFromProduct=='ifempty' and !pq_trim($this->idResource))) { 
  	  $comp=new Component($this->idComponent,true);
  	  if ($comp->idResource) {
  	    $this->idResource=$comp->idResource;
  	  } else {
  	    $prod=new Product($this->idProduct,true);
  	    if ($prod->idResource) {
  	      $this->idResource=$prod->idResource;
  	    }
  	  }
  	}
  	if ($this->idResource and ! $this->idAccountable) { // Set Accountable (if not set) to Responsible (if set) 
  	  $this->idAccountable=$this->idResource;
  	}
  	//ADD qCazelles - Assign auto CV to ticket - Ticket 95
    if ($this->idComponent and $this->idTargetProductVersion and !$this->idTargetComponentVersion and Parameter::getGlobalParameter('autoSetUniqueComponentVersion')!='NO') {
      $pvs = new ProductVersionStructure();
      $crit = array('idProductVersion' => $this->idTargetProductVersion);
      $pvss = $pvs->getSqlElementsFromCriteria($crit, false);
      if (count($pvss) > 0) {
        $clauseWhere = 'id in (0';
        foreach ($pvss as $pvs) {
          $clauseWhere .= ','.$pvs->idComponentVersion;
        }
        $clauseWhere .= ')';
        $cv = new ComponentVersion();
        $cvs = $cv->getSqlElementsFromCriteria(null, false, $clauseWhere);
        $cvAssigned = null;
        foreach ($cvs as $cv) {
          if ($cv->idComponent == $this->idComponent) {
            if ($cvAssigned == null) {
              $cvAssigned = $cv;
            } else {
              $cvAssigned = null;
              break;
            }
          }
        }
        if ($cvAssigned != null) {
          $this->idTargetComponentVersion = $cvAssigned->id;
        }
      }
    }
  	//END ADD qCazelles - Assign auto CV to ticket - Ticket 95
  	$result=parent::save();
    if (! pq_strpos($result,'id="lastOperationStatus" value="OK"')) {
      return $result;     
    }
  	if (pq_trim($this->idTicket) and ! pq_trim($old->idTicket)) {
      $duplicate=new Ticket($this->idTicket);
      if (! $duplicate->idTicket) {
      	$duplicate->idTicket=$this->id;
      	$duplicate->save();
      }
  	}
  	if ($old->idActivity and $old->idActivity!=$this->idActivity) {
  		// if top activity changed, must update corresponding Planning element for ticket work summary
  		$ape = SqlElement::getSingleSqlElementFromCriteria ( 'ActivityPlanningElement', array (
  				'refType' => 'Activity',
  				'refId' => $old->idActivity
  		) );
  		if ($ape and $ape->id) {
  			$ape->updateWorkElementSummary ();
  		} 
  	}

    if($this->idActivity){
  	  $act = new Activity($this->idActivity);
  	  $act->isPlanningActivity = "1";
  	  $act->save();
  	}elseif(isset($old->idActivity)){
      $act = new Activity($old->idActivity);
  	  $act->isPlanningActivity = "0";
  	  $act->save();
    }
    
    if ($this->id and $old->idProject != $this->idProject) {
      $sub = new SubTask();
      $subList = $sub->getSqlElementsFromCriteria(array('refType' => 'Ticket', 'refId' => $this->id),false);
      foreach ($subList as $sub) {
        $sub->idProject = $this->idProject;
        $sub->saveForced();
      }
    }
    
    if(!$old->id){
      $newStatPeriod = new StatusPeriod();
      $newStatPeriod->refId = $this->id;
      $newStatPeriod->refType = get_class($this);
      $newStatPeriod->active = 0;
      $newStatPeriod->startDate = date('Y-m-d H:i:s', pq_strtotime('now'));
      $newStatPeriod->type = 'recorded';
      $newStatPeriod->idStatusStart = $this->idStatus;
      $newStatPeriod->idUserStart = getSessionUser()->id;
      $newStatPeriod->save();
    }
  	return $result;
  }

  public function getTitle($col) {
  	if (pq_substr($col,0,9)=='idContext') {
  	  return SqlList::getNameFromId('ContextType', pq_substr($col, 9));
  	} else {
  		return parent::getTitle($col);
  	} 
  	
  }
  
  public function setAttributes() {
    if ($this->delayReadOnly == 1) {
      self::$_fieldsAttributes['initialDueDateTime']='readonly';     
    }  
    if (Parameter::getGlobalParameter('manageAccountable')!='YES') {
      self::$_fieldsAttributes['idAccountable']='hidden';
    }
    if (!Module::isModuleActive('moduleTargetMilestone')) {
      self::$_fieldsAttributes["idMilestone"]='hidden';
    }
    
    if($this->id){
      $displayVote = VotingItem::isVotable('Ticket', $this->id,$this->idTicketType);
      if($displayVote or RequestHandler::isCodeSet('customization')){
        self::$_fieldsAttributes ['_sec_vote'] = '';
        self::$_fieldsAttributes ['VotingItem'] = '';
      }else{
      self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
      self::$_fieldsAttributes ['VotingItem'] = 'hidden';
      }
    }else if (! RequestHandler::isCodeSet('customization')){
      self::$_fieldsAttributes ['_sec_vote'] = 'hidden';
      self::$_fieldsAttributes ['VotingItem'] = 'hidden';
    }
    if(! Module::isModuleActive('moduleTodoList') or Parameter::getUserParameter('displaySubTask')!="YES" or ($this->id=='' and ! RequestHandler::isCodeSet('customization'))){ //Parameter::getGlobalParameter('activateSubtasksManagement')!='YES'
      self::$_fieldsAttributes ['_SubTask'] = 'hidden';
      self::$_fieldsAttributes ['_sec_ToDoList'] = 'hidden';
      unset($this->_SubTask);
      unset($this->_sec_ToDoList);
    }else if ($this->id) {
      $user=getSessionUser();
      $habilSub=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($this),'scope'=>'subtask'));
      $listYesNo=new ListYesNo($habilSub->rightAccess);
      if ($listYesNo->code!='YES') {
        self::$_fieldsAttributes ['_SubTask'] = 'hidden';
        self::$_fieldsAttributes ['_sec_ToDoList'] = 'hidden';
        unset($this->_sec_ToDoList);
        unset($this->_SubTask);
      }
    }
    
    if ($this->id) {
      $user=getSessionUser();
      $habilSub=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$user->getProfile($this),'scope'=>'canWorkOnTicket'));
      if ($habilSub->rightAccess==1) {
      }
    }
    
    if(!$this->id and ! RequestHandler::isCodeSet('customization')){
      self::$_fieldsAttributes ['_button_showStatusPeriod'] = 'hidden';
    }
    //Display HINT idActivity
    if($this->id and $this->idActivity){
      $isWork = false;
      $synchItem = new SynchronizedItems();
      $synch = $synchItem->countSqlElementsFromCriteria(array('ref2Type'=>'Ticket','ref2Id'=>$this->id));
      if($synch){
        self::$_fieldsAttributes ['idActivity'] = 'readonly';
        self::$_fieldsTooltip ['idActivity'] = 'hintIdActivitySycnh';
        $isWork = true;
      }
      if(!$isWork){
        $work = new Work();
        $lstWork = $work->getSqlElementsFromCriteria(array('refType'=>'Activity','refId'=>$this->idActivity));
        foreach ($lstWork as $work){
          if($isWork)break;
          $workElement = new WorkElement($work->idWorkElement);
          if($workElement->refType=='Ticket' and $workElement->refId == $this->id)$isWork = true;
        }
        if($isWork) self::$_fieldsTooltip ['idActivity'] = 'hintIdActivityWork';
      }
    }
  }
  
  public function drawSpecificItem($item) {
  	if ($item=='showStatusPeriod') {
  		echo '<div id="'.$item.'" title="' . i18n('showStatusPeriod') . '" style="float:right;padding:2px 2px 0px 0px;" >';
  		echo '<button id="' . $item . 'Button" dojoType="dijit.form.Button" style="width:200px;vertical-align: middle;" class="roundedVisibleButton">';
  		echo '<span>' . i18n('showStatusPeriod') . '</span>';
    	echo '<script type="dojo/connect" event="onClick" args="evt">';
    	echo 'showStatusPeriod(\'Ticket\','.$this->id.');';
    	echo '</script>';
    	echo '</button>';
  		echo '</div>';
  	}
  }
  
  public function delete() {
  	$statusPeriod = new StatusPeriod();
  	$listSPeriod = $statusPeriod->getSqlElementsFromCriteria(array("refType"=>"Ticket", "refId"=>$this->id));
  	foreach ($listSPeriod as $sPeriod){
  	  $sPeriod->delete();
  	}
  	$result = parent::delete();
  	// After delete,; remove dupplicate from others
  	$lst=$this->getSqlElementsFromCriteria(array('idTicket'=>$this->id));
  	foreach ($lst as $tkt) {
  	  $tkt->idTicket=null;
  	  $tkt->save();
  	}
  	return $result;
  }
}
?>