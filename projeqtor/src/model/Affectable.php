<?php
use LDAP\Result;

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

/*
 * ============================================================================ User is a resource that can connect to the application.
 */
require_once ('_securityCheck.php');

class Affectable extends SqlElement {
  
  // extends SqlElement, so has $id
  public $_sec_Description;

  public $id;
 // redefine $id to specify its visible place
  public $name;
  public $userName;
  public $capacity=1;
  public $idCalendarDefinition;
  public $idProfile;
  public $isResource;
  public $isUser;
  public $isContact;
  public $isResourceTeam;
  public $isMaterial;
  public $email;
  public $idTeam;
  public $idOrganization;
  public $idle;
  public $dummy;
  public $dontReceiveTeamMails;
  public $_sec_Asset;
  public $_spe_asset;
  public $_constructForName=true;
  public $_calculateForColumn=array(
      "name"=>"coalesce(fullName,concat(name,' #'))", 
      "userName"=>"coalesce(name,concat(fullName,' *'))");

  private static $_fieldsAttributes=array(
      "name"=>"required", 
      "isContact"=>"readonly", 
      "isUser"=>"readonly", 
      "isResource"=>"readonly", 
      "isResourceTeam"=>"readonly", 
      "isMaterial"=>"readonly", 
      "idle"=>"hidden",
      "dummy"=>"hidden"
      
  );

  private static $_databaseTableName='resource';

  private static $_databaseColumnName=array('name'=>'fullName', 'userName'=>'name');

  private static $_databaseCriteria=array();

  private static $_visibilityScope=array();
  // ADD BY Marc TABARY - 2017-02-20 - ORGANIZATION VISIBILITY
  private static $_organizationVisibilityScope=array();
  // END ADD BY Marc TABARY - 2017-02-20 - ORGANIZATION VISIBILITY
  private static $_criticalResourceArray=null;
  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="5%"># ${id}</th>
    <th field="name" width="25%">${realName}</th>
    <th field="userName" width="20%">${userName}</th>
    <th field="photo" formatter="thumb32" width="10%">${photo}</th>
    <th field="email" width="25%">${email}</th>  
    <th field="isUser" width="5%" formatter="booleanFormatter">${isUser}</th>
    <th field="isResource" width="5%" formatter="booleanFormatter">${isResource}</th>
    <th field="isContact" width="5%" formatter="booleanFormatter">${isContact}</th>
    ';

  /**
   * ==========================================================================
   * Constructor
   *
   * @param $id Int the
   *          id of the object in the database (null if not stored yet)
   * @return void
   */
  function __construct($id=NULL, $withoutDependentObjects=false) {
    parent::__construct($id, $withoutDependentObjects);
    $this->setName();
  }

  public function setName() {
    if ($this->id and !$this->name and $this->userName) {
      $this->name=$this->userName;
    }
  }

  /**
   * ==========================================================================
   * Destructor
   *
   * @return void
   */
  function __destruct() {
    parent::__destruct();
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
   * ========================================================================
   * Return the specific databaseTableName
   *
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return $paramDbPrefix.self::$_databaseTableName;
  }

  /**
   * ========================================================================
   * Return the specific databaseTableName
   *
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return self::$_databaseColumnName;
  }

  /**
   * ========================================================================
   * Return the specific database criteria
   *
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseCriteria() {
    return self::$_databaseCriteria;
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
  
  // ============================================================================**********
  // THUMBS & IMAGES
  // ============================================================================**********
  
  /**
   *
   * @param String $classAffectable          
   * @param Int $idAffectable          
   * @param String $fileFullName          
   */
  public static function generateThumbs($classAffectable, $idAffectable, $fileFullName=null) {
    $sizes=array(16, 22, 32, 48, 80); // sizes to generate, may be used somewhere
    $thumbLocation='../files/thumbs';
    $attLoc=Parameter::getGlobalParameter('paramAttachmentDirectory');
    if (!$fileFullName) {
      $image=SqlElement::getSingleSqlElementFromCriteria('Attachment', array('refType'=>'Resource', 'refId'=>$idAffectable));
      if ($image->id) {
        $fileFullName=$image->subDirectory.$image->fileName;
      }
    }
    $fileFullName=pq_str_replace('${attachmentDirectory}', $attLoc, $fileFullName);
    $fileFullName=pq_str_replace('\\', '/', $fileFullName);
    if ($fileFullName and isThumbable($fileFullName)) {
      foreach ($sizes as $size) {
        $thumbFile=$thumbLocation."/Affectable_$idAffectable/thumb$size.png";
        createThumb($fileFullName, $size, $thumbFile, true);
      }
    }
  }

  public static function generateAllThumbs() {
    $affList=SqlList::getList('Affectable', 'name', null, true);
    foreach ($affList as $id=>$name) {
      self::generateThumbs('Affectable', $id, null);
    }
  }

  public static function deleteThumbs($classAffectable, $idAffectable, $fileFullName=null) {
    $thumbLocation='../files/thumbs/Affectable_'.$idAffectable;
    purgeFiles($thumbLocation, null);
  }

  public static function getThumbUrl($objectClass, $affId, $size, $nullIfEmpty=false, $withoutUrlExtra=false) {
    $thumbLocation='../files/thumbs';
    $file="$thumbLocation/Affectable_$affId/thumb$size.png";
    if (file_exists($file)) {
      if ($withoutUrlExtra) {
        return $file;
      } else {
        $cache=filemtime($file);
        return "$file?nocache=".$cache."#$affId#&nbsp;#Affectable";
      }
    } else {
      if ($nullIfEmpty) {
        return null;
      } else {
        return 'letter#'.$affId;
        // if ($withoutUrlExtra) {
        // return "../view/img/Affectable/thumb$size.png";
        // } else {
        // return "../view/img/Affectable/thumb$size.png#0#&nbsp;#Affectable";
        // }
      }
    }
  }

  public static function showBigImageEmpty($extraStylePosition, $canAdd=true) {
    $result=null;
    if (isNewGui()) {
      $result.='<div style="position: absolute;'.$extraStylePosition.';width:60px;height:60px;border-radius:40px; border: 1px solid grey;color: grey;font-size:80%; text-align:center;cursor: pointer;"';
      if ($canAdd) {
        $result.='onClick="addAttachment(\'file\',null,null,\'profilePic\');" title="'.i18n('addPhoto').'">';
        $result.='<div style="left: 19px;position:relative;top: 20px;height:22px;width: 22px;" class="iconAdd iconSize22 imageColorNewGui">&nbsp;</div>';
      } else {
        $result.='>';
      }
      $result.='</div>';
    } else {
      $result='<div style="position: absolute;'.$extraStylePosition.';'.'border-radius:40px;width:80px;height:80px;border: 1px solid grey;color: grey;font-size:80%;'.'text-align:center;';
      if ($canAdd) {
        $result.='cursor: pointer;"  onClick="addAttachment(\'file\');" title="'.i18n('addPhoto').'">';
        $result.='<br/><br/><br/>'.i18n('addPhoto').'</div>';
      } else {
        $result.='" ></div>';
      }
    }
    return $result;
  }

  public static function showBigImage($extraStylePosition, $affId, $filename, $attachmentId) {
    global $print;
    $result='<div style="position: absolute;'.$extraStylePosition.'; border-radius:40px;width:80px;height:80px;border: 1px solid grey;">'
  	.'<img style="border-radius:40px;cursor:pointer;" src="'.Affectable::getThumbUrl('Resource', $affId, 80).'" '.' title="'.$filename.'" '
  	. ((!$print)?' onClick="showImage(\'Attachment\',\''.$attachmentId.'\',\''.htmlEncode($filename, 'protectQuotes').'\');" ':'')
  	. '/>'
  	.'</div>';
  	return $result;
  }

  public static function drawSpecificImage($class, $id, $print, $outMode, $largeWidth) {
    $result="";
    $image=SqlElement::getSingleSqlElementFromCriteria('Attachment', array('refType'=>'Resource', 'refId'=>$id, 'isProfilePic'=>'1'));
    if ($image->id and $image->isThumbable()) {
      if (!$print) {
        // $result.='<tr style="height:20px;">';
        // $result.='<td class="label">'.i18n('colPhoto').'&nbsp;:&nbsp;</td>';
        // $result.='<td>&nbsp;&nbsp;';
        $result.='<span class="label" style="position: absolute;top:28px;right:105px;">';
        $result.=i18n('colPhoto').'&nbsp;:&nbsp;';
        $canUpdate=securityGetAccessRightYesNo('menu'.$class, 'update')=="YES";
        if ($id==getSessionUser()->id) $canUpdate=true;
        if ($canUpdate) {
          // $result.='<img src="css/images/smallButtonRemove.png" class="roundedButtonSmall" style="height:12px" '
          // .'onClick="removeAttachment('.htmlEncode($image->id).');" title="'.i18n('removePhoto').'" class="smallButton"/>';
          $result.='<span onClick="removeAttachment('.htmlEncode($image->id).');" title="'.i18n('removePhoto').'" >';
          $result.=formatSmallButton('Remove');
          $result.='</span>';
        }
        
        $horizontal='right:10px';
        $top='30px';
        $result.='</span>';
      } else {
        if ($outMode=='pdf') {
          $horizontal='left:450px';
          $top='100px';
        } else {
          $horizontal='left:400px';
          $top='70px';
        }
      }
      $extraStyle='top:30px;'.$horizontal;
      $result.=Affectable::showBigImage($extraStyle, $id, $image->fileName, $image->id, "profilePic");
      if (!$print) {
        // $result.='</td></tr>';
      }
    } else {
      if ($image->id) {
        $image->delete();
      }
      if (!$print) {
        $horizontal='right:10px';
        // $result.='<tr style="height:20px;">';
        // $result.='<td class="label">'.i18n('colPhoto').'&nbsp;:&nbsp;</td>';
        // $result.='<td>&nbsp;&nbsp;';
        $result.='<span class="label" style="position: absolute;top:28px;right:105px;">';
        $result.=i18n('colPhoto').'&nbsp;:&nbsp;';
        $canUpdate=securityGetAccessRightYesNo('menu'.$class, 'update')=="YES";
        if ($id==getSessionUser()->id) $canUpdate=true;
        if ($canUpdate and !isNewGui()) {
          // KEVIN
          $result.='<span onClick="addAttachment(\'file\');"title="'.i18n('addPhoto').'" >';
          $result.=formatSmallButton('Add');
          $result.='</span>';
        }
        $result.='</span>';
        $extraStyle='top:30px;'.$horizontal;
        $result.=Affectable::showBigImageEmpty($extraStyle, $canUpdate);
      }
    }
    return $result;
  }

  /**
   * =========================================================================
   * Draw a specific item for the current class.
   * 
   * @param String $item the item.
   * @return String an html string able to display a specific item
   *         must be redefined in the inherited class
   */
  public function drawSpecificItem($item) {
    global $print, $outMode, $largeWidth;
    $result="";
    if ($item=='asset') {
      $asset=new Asset();
      $critArray=array('idAffectable'=>(($this->id)?$this->id:'0'));
      $order=" idAssetType asc ";
      $assetList=$asset->getSqlElementsFromCriteria($critArray, false, null);
      drawAssetFromUser($assetList, $this);
    }
    return $result;
  }

  public static function isAffectable($objectClass=null) {
    if ($objectClass) {
      if ($objectClass=='Resource' or $objectClass=='ResourceTeam' or $objectClass=='User' or $objectClass=='Contact' or $objectClass=='Affectable' or $objectClass=='ResourceSelect' or $objectClass=='Accountable' or $objectClass=='Responsible' or $objectClass=='ResourceMaterial') {
        return true;
      }
    }
    return false;
  }
  
  // ADD BY Marc TABARY - 2017-02-20 ORGANIZATION VISIBILITY
  public static function getOrganizationVisibilityScope($scope='List') {
    if (isset(self::$_organizationVisibilityScope[$scope])) return self::$_organizationVisibilityScope[$scope];
    $orga='all';
    $crit=array('idProfile'=>getSessionUser()->idProfile, 'scope'=>'orgaVisibility'.$scope);
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
    if ($habil and $habil->id) {
      $orga=SqlList::getFieldFromId('ListOrgaSubOrga', $habil->rightAccess, 'code', false);
    }
    self::$_organizationVisibilityScope[$scope]=$orga;
    return $orga;
  }
  // END ADD BY Marc TABARY - 2017-02-20 - ORGANIZATION VISIBILITY
  public static function getVisibilityScope($scope='List', $idProject=null) {
    $profile=getSessionUser()->getProfile($idProject);
    if (isset(self::$_visibilityScope[$scope][$profile])) return self::$_visibilityScope[$scope][$profile];
    $res='all';
    $crit=array('idProfile'=>$profile, 'scope'=>'resVisibility'.$scope);
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
    if ($habil and $habil->id) {
      $res=SqlList::getFieldFromId('ListTeamOrga', $habil->rightAccess, 'code', false);
    }
    self::$_visibilityScope[$scope][$profile]=$res;
    return $res;
  }

  public static function sort($aff1, $aff2) {
    $name1=pq_strtolower(($aff1->name)?$aff1->name:$aff1->userName);
    $name2=pq_strtolower(($aff2->name)?$aff2->name:$aff2->userName);
    if ($name1<$name2) {
      return -1;
    } else if ($name1>$name2) {
      return 1;
    } else {
      return 0;
    }
  }

  public static function tranformPlanningResult($scale, $start, $end) {
    global $cronnedScript, $fullListPlan, $arrayPlannedWork, $arrayRealWork, $arrayAssignment;
    SqlElement::$_cachedQuery['ResourceAll']=array();
    SqlElement::$_cachedQuery['PlanningElement']=array();
    SqlElement::$_cachedQuery['ResourceTeamAffectation']=array();
    SqlElement::$_cachedQuery['Calendar']=array();
    SqlElement::$_cachedQuery['Project']=array();
    $res=array();
    $assignmentDate=array();
    $listCodeProject=array();
    $listDateProject=array();
    CriticalResourceScenarioProject::getScenarioProjectInfo($listCodeProject, $listDateProject);
    foreach ($arrayAssignment as $ass) {
      // Don't show PRP & TMP
      if (!isset($listCodeProject[$ass->idProject])) {
        $type=SqlList::getFieldFromId('Project', $ass->idProject, 'idProjectType');
        $code=SqlList::getFieldFromId('ProjectType', $type, 'code');
        $listCodeProject[$ass->idProject]=$code;
      }
      $code=$listCodeProject[$ass->idProject];
      if ($code=='PRP' or $code=='TMP') continue;
      // ============== real planned date =======================//
      $date=SqlList::getFieldFromId('Assignment', $ass->id, 'plannedEndDate');
      $monthPeriod=date('Ym', pq_strtotime($date));
      $weekPeriod=getWeekNumberFromDate($date);
      $year=date('Y', pq_strtotime($date));
      $month=date('m', pq_strtotime($date));
      $quarter=1+intval(($month-1)/3);
      $quarterPeriod=$year.'-Q'.$quarter;
      $assignmentDate['real'][$ass->id]['month']['end']=$monthPeriod;
      $assignmentDate['real'][$ass->id]['week']['end']=$weekPeriod;
      $assignmentDate['real'][$ass->id]['quarter']['end']=$quarterPeriod;
      $assignmentDate['real'][$ass->id]['date']['end']=$date;
      $date=SqlList::getFieldFromId('Assignment', $ass->id, 'plannedStartDate');
      $monthPeriod=date('Ym', pq_strtotime($date));
      $weekPeriod=getWeekNumberFromDate($date);
      $year=date('Y', pq_strtotime($date));
      $month=date('m', pq_strtotime($date));
      $quarter=1+intval(($month-1)/3);
      $quarterPeriod=$year.'-Q'.$quarter;
      $assignmentDate['real'][$ass->id]['month']['start']=$monthPeriod;
      $assignmentDate['real'][$ass->id]['week']['start']=$weekPeriod;
      $assignmentDate['real'][$ass->id]['quarter']['start']=$quarterPeriod;
      $assignmentDate['real'][$ass->id]['date']['start']=$date;
      // ============== ideal planned date =======================//
      $date=$ass->plannedEndDate;
      $monthPeriod=date('Ym', pq_strtotime($date));
      $weekPeriod=getWeekNumberFromDate($date);
      $year=date('Y', pq_strtotime($date));
      $month=date('m', pq_strtotime($date));
      $quarter=1+intval(($month-1)/3);
      $quarterPeriod=$year.'-Q'.$quarter;
      $assignmentDate['ideal'][$ass->id]['month']['end']=$monthPeriod;
      $assignmentDate['ideal'][$ass->id]['week']['end']=$weekPeriod;
      $assignmentDate['ideal'][$ass->id]['quarter']['end']=$quarterPeriod;
      $assignmentDate['ideal'][$ass->id]['date']['end']=$date;
      $date=$ass->plannedStartDate;
      $monthPeriod=date('Ym', pq_strtotime($date));
      $weekPeriod=getWeekNumberFromDate($date);
      $year=date('Y', pq_strtotime($date));
      $month=date('m', pq_strtotime($date));
      $quarter=1+intval(($month-1)/3);
      $quarterPeriod=$year.'-Q'.$quarter;
      $assignmentDate['ideal'][$ass->id]['month']['start']=$monthPeriod;
      $assignmentDate['ideal'][$ass->id]['week']['start']=$weekPeriod;
      $assignmentDate['ideal'][$ass->id]['quarter']['start']=$quarterPeriod;
      $assignmentDate['ideal'][$ass->id]['date']['start']=$date;
    }
    $resourceTeamAffection = array();
    $resourceTeamAffRate=array();
    $idResourceTeam=array();
    $planWork=new PlannedWork();
    $tmpAss=new Assignment();
    $critPlannedWork="idProject not in ".Project::getAdminitrativeProjectList(false);
    $critPlannedWork.=" and workDate>='$start' and workDate<='$end'";
    $lstPlanWork=$planWork->getSqlElementsFromCriteria(null, false, $critPlannedWork,null,null,true);
    $loop['ideal']=array("real"=>$arrayRealWork, "planned"=>$arrayPlannedWork);
    $loop['real']=array("real"=>$arrayRealWork, "planned"=>$lstPlanWork); // PBER : Not sure, possibly to remove back to "real"=>array()
    foreach ($loop as $planType=>$arrayPlan) {
      foreach ($arrayPlan as $type=>$array) {
        foreach ($array as $w) {
          if (!isset($assignmentDate[$planType][$w->idAssignment])) continue;
          if (!isset($listCodeProject[$w->idProject])) {
            $type=SqlList::getFieldFromId('Project', $w->idProject, 'idProjectType');
            $code=SqlList::getFieldFromId('ProjectType', $type, 'code');
            $listCodeProject[$w->idProject]=$code;
          }
          $code=$listCodeProject[$w->idProject];
          if ($code=='PRP' or $code=='TMP') continue;
        	$idR=$w->idResource;
        	$idP=$w->idProject;
        	$idO=$w->refId;
        	$date = $w->workDate;
        	$monthPeriod=pq_substr($date,0,4).pq_substr($date,5,2);
        	$weekPeriod=getWeekNumberFromDate($date);
        	$year=date('Y',pq_strtotime($date));
        	$month=date('m',pq_strtotime($date));
        	$quarter=1+intval(($month-1)/3);
        	$quarterPeriod=$year.'-Q'.$quarter;
        	$refId=$w->refId;
        	$refType = $w->refType;
        	if ($w->workDate<$start or $w->workDate>$end) {continue;}
        	$r=new ResourceAll($idR, true);
        	$capacity = $r->getCapacityPeriod($w->workDate);
        	$isResourceTeam = ($r->isResourceTeam)?true:false;
        	if (!isset($res[$idR])) {
        		$res[$idR]=array('object'=>$r, 'name'=>$r->name,
        				'totalSurbooked'=>0,'totalWork'=>0, 'totalAvailable'=>0, 'plannedSurbooked'=>0,
        				'capacity'=>0, 'totalCapacity'=>0,'isResourceTeam'=>$isResourceTeam, 'resourceTeamMarginSub'=>0,
        				'dates'=>array('month'=>array(),'week'=>array(),'quarter'=>array()),'projects'=>array());
        	}
        	if (!isset($res[$idR]['projects'][$idP])) {
        		$wbs = SqlList::getFieldFromId('Project', $idP, 'sortOrder');
        		$strategicValue=SqlList::getFieldFromId('Project', $idP, 'strategicValue');
        		//$projectPlan = new PlanningElement();
        		$projectPlan = SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refId'=>$idP,'refType'=>'Project'));
        		$validatedEndDate=$projectPlan->validatedEndDate;
        		$plannedEndDate=$projectPlan->plannedEndDate;
        		$priority=$projectPlan->priority;
        		$res[$idR]['projects'][$idP]=array('name'=>SqlList::getNameFromId('Project',$idP),'wbs'=>$wbs, 'priority'=>$priority,'strategicValue'=>$strategicValue,
        		    'validatedEndDate'=>$validatedEndDate,'plannedEndDate'=>$plannedEndDate ,'totalSurbooked'=>0,'totalWork'=>0, 'plannedSurbooked'=>0, 'object'=>array());
        	}
            if($planType == 'real' and $w->work != 0 and !$isResourceTeam){
        	  if(!isset($resourceTeamAffRate[$idR])){
        	    $resTeamAffectation = new ResourceTeamAffectation();
        	    $resTeamAff = $resTeamAffectation->getSingleSqlElementFromCriteria('ResourceTeamAffectation',array('idResource'=>$idR));
        	    $affCapacity = $capacity;
        	    if($resTeamAff->id){
        	      $idResourceTeam[$idR]=$resTeamAff->idResourceTeam;
        	      $affCapacity = ($resTeamAff->rate/100)*$capacity;
        	      $resourceTeamAffRate[$idR]=$resTeamAff;
        	    }
        	  }else{
        	    $affCapacity = ($resourceTeamAffRate[$idR]->rate/100)*$capacity;
        	  }
        	  $workCapacity = ($affCapacity < $capacity)?$w->work-$affCapacity:$w->work;
        	  $workCapacity = ($workCapacity < 0)?0:$workCapacity;
        	  if ($resTeamAff->idResourceTeam) {
          	  if(!isset($resourceTeamAffection[$resTeamAff->idResourceTeam])){
          	    $resourceTeamAffection[$resTeamAff->idResourceTeam]=$workCapacity;
          	  }else{
          	    $resourceTeamAffection[$resTeamAff->idResourceTeam]+=$workCapacity;
          	  }
        	  }
        	}
            if($isResourceTeam){
        	  if(isset($resourceTeamAffection[$idR])){
        	    $res[$idR]['resourceTeamMarginSub']=$resourceTeamAffection[$idR];
        	  }
        	}else {
        	  if(isset($idResourceTeam[$idR]) and isset($res[$idResourceTeam[$idR]]) and isset($resourceTeamAffection[$idResourceTeam[$idR]])) {
        	    $res[$idResourceTeam[$idR]]['resourceTeamMarginSub']=$resourceTeamAffection[$idResourceTeam[$idR]];
        	  }
        	}
        	if($planType == 'real')$res[$idR]['totalWork']+=$w->work;
        	if($planType == 'real')$res[$idR]['projects'][$idP]['totalWork']+=$w->work;
        	if($planType == 'ideal')$res[$idR]['plannedSurbooked']+=$w->work;
        	if (!isset($res[$idR]['projects'][$idP]['object'][$idO])) {
        		$res[$idR]['projects'][$idP]['object'][$idO]=array('name'=>SqlList::getNameFromId($refType,$refId), 'refType'=>$refType, 'refId'=>$refId, 'plan'=>array('ideal'=>array('endDate'=>null, 'startDate'=>null), 'real'=>array('endDate'=>null, 'startDate'=>null)),
        		     'totalSurbooked'=>0,'totalWork'=>0, 'plannedSurbooked'=>0, 'assignedWork'=>null, 'leftWork'=>null,'dates'=>array('month'=>array(),'week'=>array(),'quarter'=>array()));
        	}
        	$res[$idR]['projects'][$idP]['object'][$idO]['refType']=$refType;
        	$res[$idR]['projects'][$idP]['object'][$idO]['refId']=$refId;
        	$res[$idR]['projects'][$idP]['object'][$idO]['plan'][$planType]['endDate']=$assignmentDate[$planType][$w->idAssignment]['date']['end'];
        	$res[$idR]['projects'][$idP]['object'][$idO]['plan'][$planType]['startDate']=$assignmentDate[$planType][$w->idAssignment]['date']['start'];
        	if($planType == 'real')$res[$idR]['projects'][$idP]['object'][$idO]['totalWork']+=$w->work;
        	if($planType == 'ideal' and $type=='planned')$res[$idR]['projects'][$idP]['object'][$idO]['plannedSurbooked']+=$w->work;
        	if(!isset($res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod]['ideal'])){
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod]['ideal']=array('endDate'=>null, 'startDate'=>null, 'totalSurbooked'=>0,'totalWork'=>0);
        	}
        	if(!isset($res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod]['real'])){
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod]['real']=array('endDate'=>null, 'startDate'=>null, 'totalSurbooked'=>0,'totalWork'=>0);
        	}
        	if($planType == 'real')$res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod][$planType]['totalWork']+=$w->work;
        	if ($type=='planned') {
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod][$planType]['totalSurbooked']+=$w->surbookedWork;
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod][$planType]['totalWork']+=$w->work;
        	}
        	if ($res[$idR]['projects'][$idP]['object'][$idO]['assignedWork']===null) {
        	  $res[$idR]['projects'][$idP]['object'][$idO]['assignedWork'] = $tmpAss->sumSqlElementsFromCriteria('assignedWork',array('refType'=>$w->refType, 'refId'=>$w->refId, 'idResource'=>$w->idResource));
        	}
      	  if ($res[$idR]['projects'][$idP]['object'][$idO]['leftWork']===null) {
      	    $res[$idR]['projects'][$idP]['object'][$idO]['leftWork'] = $tmpAss->sumSqlElementsFromCriteria('leftWork',array('refType'=>$w->refType, 'refId'=>$w->refId, 'idResource'=>$w->idResource));
      	  }
        	$res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod][$planType]['endDate']=$assignmentDate[$planType][$w->idAssignment]['month']['end'];
        	$res[$idR]['projects'][$idP]['object'][$idO]['dates']['month'][$monthPeriod][$planType]['startDate']=$assignmentDate[$planType][$w->idAssignment]['month']['start'];
        	if(!isset($res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod]['ideal'])){
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod]['ideal']=array('endDate'=>null, 'startDate'=>null, 'totalSurbooked'=>0,'totalWork'=>0);
        	}
        	if(!isset($res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod]['real'])){
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod]['real']=array('endDate'=>null, 'startDate'=>null, 'totalSurbooked'=>0,'totalWork'=>0);
        	}
        	if($planType == 'real')$res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod][$planType]['totalWork']+=$w->work;
        	if ($type=='planned') {
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod][$planType]['totalSurbooked']+=$w->surbookedWork;
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod][$planType]['totalWork']+=$w->work;
        	}
        	$res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod][$planType]['endDate']=$assignmentDate[$planType][$w->idAssignment]['week']['end'];
        	$res[$idR]['projects'][$idP]['object'][$idO]['dates']['week'][$weekPeriod][$planType]['startDate']=$assignmentDate[$planType][$w->idAssignment]['week']['start'];
        	if(!isset($res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod]['ideal'])){
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod]['ideal']=array('endDate'=>null, 'startDate'=>null, 'totalSurbooked'=>0,'totalWork'=>0);
        	}
        	if(!isset($res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod]['real'])){
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod]['real']=array('endDate'=>null, 'startDate'=>null, 'totalSurbooked'=>0,'totalWork'=>0);
        	}
        	if($planType == 'real')$res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod][$planType]['totalWork']+=$w->work;
        	if ($type=='planned') {
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod][$planType]['totalSurbooked']+=$w->surbookedWork;
        		$res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod][$planType]['totalWork']+=$w->work;
        	}
        	$res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod][$planType]['endDate']=$assignmentDate[$planType][$w->idAssignment]['quarter']['end'];
        	$res[$idR]['projects'][$idP]['object'][$idO]['dates']['quarter'][$quarterPeriod][$planType]['startDate']=$assignmentDate[$planType][$w->idAssignment]['quarter']['start'];
        	if ($type=='planned' and $planType=='ideal') {
         		$res[$idR]['totalSurbooked']+=$w->surbookedWork;
         		$res[$idR]['projects'][$idP]['totalSurbooked']+=$w->surbookedWork;
         		$res[$idR]['projects'][$idP]['object'][$idO]['totalSurbooked']+=$w->surbookedWork;
        	}
        }
      }
    }
    $nbDays=0;
    for ($date=$start; $date<=$end; $date=addDaysToDate($date, 1)) {
      $nbDays++;
      foreach ($res as $idR=>$r) {
        $capa=$r['object']->getCapacityPeriod($date);
        if (!isOffDay($date, $r['object']->idCalendarDefinition)) {
          $res[$idR]['totalAvailable']+=$capa;
        }
        $res[$idR]['totalCapacity']+=$capa;
        $res[$idR]['capacity']=round($res[$idR]['totalCapacity']/$nbDays, 2);
      }
    }
    uasort($res, function ($rA, $rB) {
      $indA=($rA['capacity'])?$rA['totalSurbooked']/$rA['capacity']:0;
      $indB=($rB['capacity'])?$rB['totalSurbooked']/$rB['capacity']:0;
      if ($indA==$indB) {
        return 0;
      } else if ($indA<$indB) {
        return 1;
      } else {
        return -1;
      }
    });
    setSessionValue('tabCriticalGraph',$res);
    self::$_criticalResourceArray=$res;
  }
  
  public static function drawCriticalResourceList($scale, $start, $end, $idProject=null, $limitedRow=null) {
    global $arrayProject;
    if (!isset(self::$_criticalResourceArray)) self::tranformPlanningResult($scale, $start, $end);
    echo '<table>';
    echo '<thead>';
    echo '<tr style="display:block;">';
    echo '<td style="min-width:51px"></td>';
    echo '<td style="min-width:311px"></td>';
    echo '<td style="min-width:71px"></td>';
    echo '<td style="min-width:71px"></td>';
    echo '<td colspan="3" class="reportTableHeader" style="min-width:250px" >'.lcfirst(i18n("colPlannedPeriod")).'</td>';//style="width:195px" 
    echo '<td style="min-width:71px"></td>';
    echo '<td style="min-width:136px"></td>';
    echo '</tr>';
    echo '<tr style="display:block;">';
    echo '<td class="reportTableHeader"><div class="dataContent" style="width:40px">'.i18n("colSortOrderShort").'</div></td>';
    echo '<td class="reportTableHeader"><div class="dataContent" style="width:300px">'.i18n("colIdResource").'</div></td>';
    echo '<td class="reportTableHeader"><div class="dataContent" style="width:60px" title="'.i18n('helpCriticalResourceCapacity').'">'.i18n("colCapacityCriticalResource").'</div></td>';
    echo '<td class="reportTableHeader"><div class="dataContent" style="width:60px" title="'.i18n('helpCriticalResourceAvailable').'">'.lcfirst(i18n("colAvailableCriticalResource")).'</div></td>';
    echo '<td class="reportTableHeader" style="background: #548235 !important;"><div style="width:76px" title="'.i18n('helpCriticalResourceUsed').'">'.lcfirst(i18n("usedMode")).'</div></td>';
    echo '<td class="reportTableHeader" style="background: #C65911 !important;"><div style="width:76px" title="'.i18n('helpCriticalResourceUsedOverbooked').'">'.lcfirst(i18n("overbookedMode")).'</div></td>';
    echo '<td class="reportTableHeader" style="background: #C65911 !important;"><div style="width:76px" title="'.i18n('helpCriticalResourceOverbooked').'">'.lcfirst(i18n("includeOverbooked")).'</div></td>';
    echo '<td class="reportTableHeader"><div class="dataContent" style="width:60px" title="'.i18n('helpCriticalResourceIndice').'">'.i18n("indicatorValue").'</div></td>';
    echo '<td class="reportTableHeader" colspan="2"><div class="dataContent" style="width:125px" title="'.i18n('helpCriticalResourceMargin').'">'.i18n("colMarginWork").'</div></td>';
    echo '</tr>';
    echo '</thead>';
    echo '<tbody style="display:block;overflow-y:auto;height:90%;width:100%;">';
    $isColorBlind = (Parameter::getUserParameter('colorBlindPlanning') == 'YES')?true:false;
    $redColorA = 'linear-gradient(45deg, #63226b 6.25%, #9a3ec9 6.25%, #9a3ec9 43.75%, #63226b 43.75%, #63226b 56.25%, #9a3ec9 56.25%, #9a3ec9 93.75%, #63226b 93.75%);background-size: 8px 8px;';
    $cpt=0;
    $totalArray=count(self::$_criticalResourceArray);
    if ($idProject and pq_trim($idProject[0])=='') unset($idProject[0]);
    if (! is_array($arrayProject)) $arrayProject=array();
    $sortArray = array();
    foreach (self::$_criticalResourceArray as $idRes=>$res) {
      if ($idProject) {
        $inArray=false;
        foreach ($idProject as $idProj) {
            if (!pq_trim($idProj)) continue;
            if (isset($arrayProject[$idProj])) continue;
            $proj=new Project($idProj, true);
            $arrayProject[$idProj]=$proj->name;
            $subList=$proj->getSubProjectsList(true);
            if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
        }
        foreach ($arrayProject as $idProj=>$val) {
          if (isset($res['projects'][$idProj])) {
            $inArray=true;
            break;
          } else {
            continue;
          }
        }
        if (!$inArray) continue;
      }
      $cpt++;
      //if ($limitedRow and $cpt>$limitedRow) continue;
      $total=$res['totalWork'];
      $surbooked=$res['totalSurbooked'];
      $available=$res['totalAvailable'];
      $plannedSurbooked=$res['plannedSurbooked'];
      $margin=$available-$total;
      if($res['isResourceTeam']){
        $margin -= $res['resourceTeamMarginSub'];
      }
      $marginPct=($available!=0)?round($margin/$available*100, 0):0;
      $indice = ($available!=0)?round((($margin-$surbooked)/$available)*100)*-1:0;
      $indiceRed = (getSessionValue('CriticalResourceIndicatorRed'))?getSessionValue('CriticalResourceIndicatorRed'):Parameter::getGlobalParameter('CriticalResourceIndicatorRed');
      $indiceOrange = (getSessionValue('CriticalResourceIndicatorOrange'))?getSessionValue('CriticalResourceIndicatorOrange'):Parameter::getGlobalParameter('CriticalResourceIndicatorOrange');
      $indiceColor = "";
      if($indiceRed > $indiceOrange){
        if($indice >= $indiceOrange and $indice < $indiceRed)$indiceColor = "background:".(($isColorBlind)?'#ad8934':'#FFC000').";color:white;";
        if($indice >= $indiceRed and $indice > $indiceOrange)$indiceColor = "background:".(($isColorBlind)?$redColorA:'#BB5050;')."color:white;";
      }else {
        if($indice >= $indiceOrange and $indice > $indiceRed)$indiceColor = "background:".(($isColorBlind)?'#ad8934':'#FFC000').";color:white;";
        if($indice >= $indiceRed and $indice < $indiceOrange)$indiceColor = "background:".(($isColorBlind)?$redColorA:'#BB5050;')."color:white;";
      }
      $surbookedColor = ($surbooked > 0)?"background:".(($isColorBlind)?'#ad8934':'#FFC000'):'background: #FCE4D6 !important;';
      $result='';
      $result .= '<tr style="height:25px;">';
      $result .= '<td class="reportTableData"><div class="dataContent" style="width:48px">#cptOrder#</div></td>';
      $result .= '<td class="reportTableData dataParentContent" style="text-align:left;"><div class="dataContent" style="width:308px"><div class="dataExtend" style="min-width:260px">'.$res['name'].'</div></div></td>';
      $result .= '<td class="reportTableData"><div class="dataContent" style="width:68px">'.htmlDisplayNumericWithoutTrailingZeros($res['capacity']).'</div></td>';
      $result .= '<td class="reportTableData"><div class="dataContent" style="width:68px">'.Work::displayWorkWithUnit($available).'</div></td>';
      $result .= '<td class="reportTableData" style="background: #E2EFDA !important;"><div class="dataContent" style="width:84px;">'.Work::displayWorkWithUnit($total).'</div></td>';
      $result .= '<td class="reportTableData" style="background: #FCE4D6 !important;"><div class="dataContent" style="width:84px;">'.Work::displayWorkWithUnit($plannedSurbooked).'</div></td>';
      $result .= '<td class="reportTableData" style="'.$surbookedColor.'"><div class="dataContent" style="width:84px">'.Work::displayWorkWithUnit($surbooked).'</div></td>';
      $result .= '<td class="reportTableData"><div class="dataContent" style="width:68px;'.$indiceColor.'">'.numericFormatter(round($indice, 0)).'</div></td>';
      $result .= '<td class="reportTableData" style="color:'.(($margin>=0)?'green':'red').';"><div class="dataContent" style="width:64px">'.Work::displayWorkWithUnit($margin).'</div></td>';
      $result .= '<td class="reportTableData" style="color:'.(($margin>=0)?'green':'red').';"><div class="dataContent" style="width:65px">'.percentFormatter($marginPct).'</div></td>';
      $result .= '</tr>';
      $sortArray[$indice.'.'.$idRes]=$result;
    }
    krsort($sortArray);
    $order = 0;
    foreach ($sortArray as $line){
      $order++;
      $orderLine = pq_str_replace('#cptOrder#', $order, $line);
      if($limitedRow){
        if($order <= $limitedRow)echo $orderLine;
      }else{
        echo $orderLine;
      }
    }
    echo '</tbody>';
    echo '</table>';
  }

  public static function drawCriticalResourceProjectList($scale, $start, $end, $idProject=null, $limitedRow=null) {
    global $arrayProject;
    if (!isset(self::$_criticalResourceArray)) self::tranformPlanningResult($scale, $start, $end);
    echo '<table>';
    echo '  <thead>';
    echo '    <tr style="display:block;">';
    echo '      <td class="reportTableHeader"><div style="width:110px">'.i18n("colIdResource").'</div></td>';
    echo '      <td class="reportTableHeader" title="'.i18n('helpCriticalResourceCapacity').'"><div style="width:105px">'.i18n("colCapacityCriticalResource").'</div></td>';
    echo '      <td class="reportTableHeader" title="'.i18n('helpCriticalResourceAvailable').'"><div style="width:90px">'.lcfirst(i18n("colAvailableCriticalResource")).'</div></td>';
    echo '      <td class="reportTableHeader"><div style="width:231px">'.i18n("colIdProject").'</div></td>';
    echo '      <td class="reportTableHeader" title="'.i18n('helpCriticalResourceUsed').'"><div style="width:80px">'.lcfirst(i18n("used")).'</div></td>';
    echo '      <td class="reportTableHeader"title="'.i18n('helpCriticalResourceOverbooked').'"><div style="width:80px">'.lcfirst(i18n("overbooked")).'</div></td>';
    echo '    </tr>';
    echo '  </thead>';
    echo '  <tbody style="display:block; overflow-y:scroll; height:160px; width:100%;">';
    $cpt=0;
    $totalArray=count(self::$_criticalResourceArray);
    if ($idProject and pq_trim($idProject[0])=='') unset($idProject[0]);
    if (! is_array($arrayProject)) $arrayProject=array();
    foreach (self::$_criticalResourceArray as $res) {
      if ($idProject) {
        $inArray=false;
        foreach ($idProject as $idProj) {
          if (!pq_trim($idProj)) continue;
          if (isset($arrayProject[$idProj])) continue;
          $proj=new Project($idProj, true);
          $arrayProject[$idProj]=$proj->name;
          $subList=$proj->getSubProjectsList(true);
          if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
        }
        foreach ($arrayProject as $idProj=>$val) {
          if (pq_array_key_exists($idProj, $res['projects'])) {
            $inArray=true;
          } else {
            continue;
          }
        }
        if (!$inArray) continue;
      }
      $firstRow=true;
      $cpt++;
      if ($limitedRow and $cpt>$limitedRow) continue;
      uasort($res['projects'], function ($x, $y) {
      	return $x['priority'] <=> $y['priority'];
      });
      foreach ($res['projects'] as $id=>$project) {
        $total=$project['totalWork'];
        $surbooked=$project['totalSurbooked'];
        $available=$res['totalAvailable'];
        $hiddenClass='';
        if (count($res['projects'])>1) {
          $hiddenClass=($firstRow)?'resourceSkillFirstRow':'resourceSkillHiddenRow';
        }
        if (!$firstRow and $cpt==$limitedRow) {
          $hiddenClass='resourceSkillLastRow';
        }
        if ($idProject) {
          $arrayProject=array();
          foreach ($idProject as $idProj) {
            if (!pq_trim($idProj)) continue;
            $proj=new Project($idProj, true);
            $arrayProject[$idProj]=$proj->name;
            $subList=$proj->getSubProjectsList(true);
            if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
          }
          if (!pq_array_key_exists($id, $arrayProject)) continue;
        }
        echo '<tr style="height: 20px;position:relative">';
        if ($firstRow) {
          echo '<td class="reportTableData '.$hiddenClass.'" style="text-align:left;"><div class="dataContent" style="width:118px"><div class="dataExtend" style="min-width:113px">'.$res['name'].'</div></div></td>';
          echo '<td class="reportTableData '.$hiddenClass.'"><div style="width:113px;">'.htmlDisplayNumericWithoutTrailingZeros($res['capacity']).'</div></td>';
          echo '<td class="reportTableData '.$hiddenClass.'"><div style="width:98px;">'.Work::displayWorkWithUnit($available).'</div></td>';
        } else {
          echo '<td class="reportTableData '.$hiddenClass.'"><div style="width:118px;"></div></td>';
          echo '<td class="reportTableData '.$hiddenClass.'"><div style="width:113px;"></div></td>';
          echo '<td class="reportTableData '.$hiddenClass.'"><div style="width:98px;"></div></td>';
        }
        echo '<td class="reportTableData" style="text-align:left; width:225px; position:relative"><div class="dataContent" style="width:239px"><div class="dataExtend" style="min-width:235px">#'.$id.' '.$project['name'].'</div></div></td>';
        echo '<td class="reportTableData"><div style="width:88px;">'.Work::displayWorkWithUnit($total).'</div></td>';
        echo '<td class="reportTableData"><div style="width:77px;">'.Work::displayWorkWithUnit($surbooked).'</div></td>';
        echo '</tr>';
        $firstRow=false;
      }
    }
    echo '</tbody>';
    echo '</table>';
  }
  
  public static function getCriticalArray() {
    return self::$_criticalResourceArray;
  }
  
  public static function drawCriticalResourceGraph($scale, $firstDay, $lastDay, $idResourceSelected,$proj,$outMode) {
    global $arrayProject;
    if($arrayProject == null){
      foreach ($proj as $idProj) {
        if (!pq_trim($idProj)) continue;
        if (isset($arrayProject[$idProj])) continue;
        $proje=new Project($idProj, true);
        $arrayProject[$idProj]=$proje->name;
        $subList=$proje->getSubProjectsList(true);
        if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
      }
    }
    include_once "../report/headerFunctions.php";
    if(!$idResourceSelected){
      echo '</br></br></br>';
      echo '<div style="background: #FFDDDD;font-size:150%;color:#808080;text-align:center;padding:20px">';
      echo i18n ( 'messageNoData', array(i18n ( 'resources' )) );
      echo '</div>';
      return;
    }
    $tabCritical = null;
    if(!self::$_criticalResourceArray){
      if (sessionValueExists('tabCriticalGraph')) {
        $tabCritical= getSessionValue('tabCriticalGraph');
      }
    }
    if(!$tabCritical)$tabCritical=self::$_criticalResourceArray;
    //TAB DATES
    $dates=array();
    for ($date=$firstDay; $date<=$lastDay; $date=addDaysToDate($date, 1)) {
      if ($scale=='month') $period=date('Ym', strtotime($date)); // pq_substr($date,0,4).pq_substr($date,5,2)
      if ($scale=='week') $period=getWeekNumberFromDate($date);
      else if ($scale=='quarter') {
        $year=date('Y', pq_strtotime($date));
        $month=date('m', pq_strtotime($date));
        $quarter=1+intval(($month-1)/3);
        $period=$year.'-Q'.$quarter;
      }
      $dates[$period]=$period;
    }
    //TAB PROJECT VALUE
    $isResourceTeam=false;
    $criticalResourceGraph = new ResourceAll($idResourceSelected);
    if($criticalResourceGraph->isResourceTeam)$isResourceTeam=true;
    $tabProjectSimple = array();
    //$arrayProject=array();
    if (! is_array($arrayProject)) $arrayProject=array();
    $sumProjUnit = array();
    if (pq_trim($proj[0])=='') unset($proj[0]);
    $sortArray = array();
    
    if(!$isResourceTeam){
      foreach ($tabCritical as $idRes=>$res) {
          if($idRes != $idResourceSelected)  continue;
        //order by priority
        uasort($res['projects'], function ($x, $y) {
          return $x['priority'] <=> $y['priority'];
        });
          foreach ($res['projects'] as $id=>$project) {
            //filter by project
            if($arrayProject != null){
              //if(!in_array($id, $proj))continue;
              $showProject = false;
              foreach ($arrayProject as $idProject=>$nameProject){
                if($idProject==$id)$showProject=true;
              }
              if(!$showProject)continue;
            }
            foreach ($project['object'] as $idO=>$object) {
              $realPlanStartDate=$object['plan']['real']['startDate'];
              $realPlanEndDate=$object['plan']['real']['endDate'];
              $idealPlanStartDate=$object['plan']['ideal']['startDate'];
              $idealPlanEndDate=$object['plan']['ideal']['endDate'];
              if ($scale=='month') {
                $realEndPeriod=date('Ym', pq_strtotime($realPlanEndDate));
                $idealEndPeriod=date('Ym', pq_strtotime($idealPlanEndDate));
                $realStartPeriod=date('Ym', pq_strtotime($realPlanStartDate));
                $idealStartPeriod=date('Ym', pq_strtotime($idealPlanStartDate));
              } else if ($scale=='week') {
                $realEndPeriod=getWeekNumberFromDate($realPlanEndDate);
                $idealEndPeriod=getWeekNumberFromDate($idealPlanEndDate);
                $realStartPeriod=getWeekNumberFromDate($realPlanStartDate);
                $idealStartPeriod=getWeekNumberFromDate($idealPlanStartDate);
              } else if ($scale=='quarter') {
                $date=$realPlanEndDate; // $realPlanEndDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $realEndPeriod=$year.'-Q'.$quarter;
                $date=$idealPlanEndDate; // $idealPlanEndDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $idealEndPeriod=$year.'-Q'.$quarter;
                $date=$realPlanStartDate; // $realPlanStartDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $realStartPeriod=$year.'-Q'.$quarter;
                $date=$idealPlanStartDate; // $idealPlanStartDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $idealStartPeriod=$year.'-Q'.$quarter;
              }
              
             foreach ($dates as $period) {
              if (isset($object['dates'][$scale][$period])) {
                $ideal=$object['dates'][$scale][$period]['ideal'];
                $real=$object['dates'][$scale][$period]['real'];
                foreach ($object['plan'] as $type=>$plan) {
                  if ($type=='ideal') {
                    if ($period>=$idealStartPeriod and $period<=$idealEndPeriod) {
                      
                      if ($ideal['totalSurbooked']==0){
                        $workPeriod=round($ideal['totalWork'], 1);
                        if(!isset($sumProjUnit[$id][$period])){
                          $sumProjUnit[$id][$period]=$workPeriod;
                        }else{
                          $sumProjUnit[$id][$period]+=$workPeriod;
                        }
                        
                      } else { // if ($ideal['totalSurbooked']!=0) {
                        $workPeriod=round($ideal['totalSurbooked'], 1);
                        if(!isset($sumProjUnit[$id][$period])){
                          $sumProjUnit[$id][$period]=$workPeriod;
                        }else{
                          $sumProjUnit[$id][$period]+=$workPeriod;
                        }
                      }
                    }
                  } else if ($type=='real') {
                  }
                }
              }
             }
            }
          }
      }
    }else{
      $resTeam = new ResourceTeamAffectation();
      $lstResTeam = $resTeam->getSqlElementsFromCriteria(array('idResourceTeam'=>$idResourceSelected));
      $arrayPoolTeam[0]=$idResourceSelected;
      foreach ($lstResTeam as $res){
        $arrayPoolTeam[]=$res->idResource;
      }
      foreach ($tabCritical as $idRes=>$res) {
        if($idRes != in_array($idRes, $arrayPoolTeam)){
          if($idRes != $idResourceSelected)  continue;
        }
        //order by priority
        uasort($res['projects'], function ($x, $y) {
          return $x['priority'] <=> $y['priority'];
        });
          foreach ($res['projects'] as $id=>$project) {
            if($arrayProject != null){
              //if(!in_array($id, $proj))continue;
              $showProject = false;
              foreach ($arrayProject as $idProject=>$nameProject){
                if($idProject==$id)$showProject=true;
              }
              if(!$showProject)continue;
            }
            foreach ($project['object'] as $idO=>$object) {
              $realPlanStartDate=$object['plan']['real']['startDate'];
              $realPlanEndDate=$object['plan']['real']['endDate'];
              $idealPlanStartDate=$object['plan']['ideal']['startDate'];
              $idealPlanEndDate=$object['plan']['ideal']['endDate'];
              if ($scale=='month') {
                $realEndPeriod=date('Ym', pq_strtotime($realPlanEndDate));
                $idealEndPeriod=date('Ym', pq_strtotime($idealPlanEndDate));
                $realStartPeriod=date('Ym', pq_strtotime($realPlanStartDate));
                $idealStartPeriod=date('Ym', pq_strtotime($idealPlanStartDate));
              } else if ($scale=='week') {
                $realEndPeriod=getWeekNumberFromDate($realPlanEndDate);
                $idealEndPeriod=getWeekNumberFromDate($idealPlanEndDate);
                $realStartPeriod=getWeekNumberFromDate($realPlanStartDate);
                $idealStartPeriod=getWeekNumberFromDate($idealPlanStartDate);
              } else if ($scale=='quarter') {
                $date=$realPlanEndDate; // $realPlanEndDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $realEndPeriod=$year.'-Q'.$quarter;
                $date=$idealPlanEndDate; // $idealPlanEndDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $idealEndPeriod=$year.'-Q'.$quarter;
                $date=$realPlanStartDate; // $realPlanStartDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $realStartPeriod=$year.'-Q'.$quarter;
                $date=$idealPlanStartDate; // $idealPlanStartDate
                $year=date('Y', pq_strtotime($date));
                $month=date('m', pq_strtotime($date));
                $quarter=1+intval(($month-1)/3);
                $idealStartPeriod=$year.'-Q'.$quarter;
              }
              
             foreach ($dates as $period) {
              if (isset($object['dates'][$scale][$period])) {
                $ideal=$object['dates'][$scale][$period]['ideal'];
                $real=$object['dates'][$scale][$period]['real'];
                foreach ($object['plan'] as $type=>$plan) {
                  if ($type=='ideal') {
                    if ($period>=$idealStartPeriod and $period<=$idealEndPeriod) {
                      
                      if ($ideal['totalSurbooked']==0){
                        $workPeriod=round($ideal['totalWork'], 1);
                        if(!isset($sumProjUnit[$idRes][$period])){
                          $sumProjUnit[$idRes][$period]=$workPeriod;
                        }else{
                          $sumProjUnit[$idRes][$period]+=$workPeriod;
                        }
                        
                      } else { // if ($ideal['totalSurbooked']!=0) {
                        $workPeriod=round($ideal['totalSurbooked'], 1);
                        if(!isset($sumProjUnit[$idRes][$period])){
                          $sumProjUnit[$idRes][$period]=$workPeriod;
                        }else{
                          $sumProjUnit[$idRes][$period]+=$workPeriod;
                        }
                      }
                    }
                  } else if ($type=='real') {
                  }
                }
              }
             }
            }
          }
      }
    }
    //end
    $tab=array();
    //if (! testGraphEnabled()) { return;}
    include_once("../external/pChart2/class/pData.class.php");
    include_once("../external/pChart2/class/pDraw.class.php");
    include_once("../external/pChart2/class/pImage.class.php");
    $dataSet=new pData;
    $nbItem=0;
    $arrDates = $dates;
    $arrSum=array();
    foreach ($arrDates as $date) {
      $arrSum[$date]=0;
    }
    $cumul=array();
    $cumulUnit=array();
    $sum=0;
    if($isResourceTeam){
      $nbDate = count($arrDates);
     foreach ($arrDates as $idDate=>$date){
        $arrayVoidDate[$idDate] = 0;
      }
      foreach ($arrayPoolTeam as $idRess){
        if(!isset($sumProjUnit[$idRess])){
          $sumProjUnit[$idRess]=$arrayVoidDate;
        }
      }
    }
    $arrayProjName = array();
    
    foreach($sumProjUnit as $id=>$datess) {
      foreach ($arrDates as $date){
        foreach ($datess as $dateId=>$value){
          if(!isset($sumProjUnit[$id][$date])){
            $sumProjUnit[$id][$date] = 0;
          }
       }
      }
    }

    foreach ($sumProjUnit as $id=>$idProj) {
      foreach ($idProj as $date=>$val){
        if(isset($cumul[$date])){
          $cumul[$date]+=$val;
        }else{
          $cumul[$date]=$val;
        }
      }
    }
    ksort($cumul);
    foreach ($cumul as $date=>$val){
      $sum+=$val;
      $cumulUnit[$date]=$sum;
    }
    $cumulUnitDate = array();
    //CapacityPeriod
    $currentRes = new ResourceAll($idResourceSelected);
    foreach ($cumulUnit as $dateKey=>$val){
      if($scale=='month'){
        $cumulUnitDate[$dateKey]=$currentRes->getMonthCapacityPeriod($dateKey);
      }elseif($scale=='week'){
        $cumulUnitDate[$dateKey]=$currentRes->getWeekCapacityPeriod($dateKey);
      }else{
        $cumulUnitDate[$dateKey]=$currentRes->getTrimestreCapacity($dateKey);
      }
    }
    
    if($isResourceTeam){
      $arrayOrder = array();
      foreach($sumProjUnit as $id=>$vals) {
        $projName = SqlList::getNameFromId('ResourceAll', $id);
        if($id==$idResourceSelected){
          $arrayOrder[$id]=$id;
        }else{
          $arrayOrder[$id]=$projName;
        }
      }
      asort($arrayOrder);
    }else{
      $arrayOrder = $sumProjUnit;
    }
    foreach($arrayOrder as $id=>$vals) {
      $vals=$sumProjUnit[$id];
      ksort($vals);
        if($id==0)continue;
        if($isResourceTeam){
          $projName = SqlList::getNameFromId('ResourceAll', $id);
        }else{
          $projName = SqlList::getNameFromId('Project', $id);
        }
        $arrayProjName[$id]=$projName;
        //$dataSet->setAxisPosition(0,AXIS_POSITION_LEFT);
        $dataSet->addPoints($vals,$projName);
        $dataSet->setSerieDescription($projName,$projName);
        $dataSet->setSerieOnAxis($projName,0);
        $projCol=null;
        if(!$isResourceTeam){
          $proje=new Project($id);
          $projCol = $proje->color;
          $projectColor=$proje->getColor();
          $colorProj=hex2rgb($projectColor);
        }
        if($projCol){
          $serieSettings = array("R"=>$colorProj['R'],"G"=>$colorProj['G'],"B"=>$colorProj['B']);
          $dataSet->setPalette($proj,$serieSettings);
        } else {
          $serieSettings = array("R"=>$rgbPalette[($nbItem % 12)]['R'],"G"=>$rgbPalette[($nbItem % 12)]['G'],"B"=>$rgbPalette[($nbItem % 12)]['B']);
          $dataSet->setPalette($proj,$serieSettings);
        }
        $nbItem++;
    }
    if($nbItem==0)return;
    $arrLabel=array();
    foreach($arrDates as $date){
      if($scale!='quarter'){
        $arrLabel[]=pq_substr($date,0,4) . '-' . pq_substr($date,4,2);
      }else{
        $arrLabel[]=$date;
      }
    }
    $dataSet->addPoints($arrLabel,"dates");
    $dataSet->setAbscissa("dates");
    $width=($outMode=='pdf')?780:1000;
    $legendWidth=300;
    $height=550;
    $legendHeight=100;
    $graph = new pImage($width+$legendWidth, $height,$dataSet);
    /* Draw the background */
    $graph->Antialias = FALSE;
    
    /* Add a border to the picture */
    $settings = array("R"=>240, "G"=>240, "B"=>240, "Dash"=>0, "DashR"=>0, "DashG"=>0, "DashB"=>0);
    $graph->drawRoundedRectangle(5,5,$width+$legendWidth-8,$height-5,5,$settings);
    $graph->drawRectangle(0,0,$width+$legendWidth-1,$height-1,array("R"=>150,"G"=>150,"B"=>150));
    
    /* Set the default font */
    $graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>8));
    $capa = i18n('ResourceCapacity');
    $dataSet->addPoints($cumulUnitDate,$capa);
    /* title */
    $graph->setFontProperties(array("FontName"=>getFontLocation("verdana"),"FontSize"=>8,"R"=>100,"G"=>100,"B"=>100));
    $dataSet->setSerieDrawable($capa,false);
    $graph->drawLegend($width+30,47,array("Mode"=>LEGEND_VERTICAL, "Family"=>LEGEND_FAMILY_BOX ,
        "R"=>255,"G"=>255,"B"=>255,"Alpha"=>100,
        "FontR"=>55,"FontG"=>55,"FontB"=>55,
        "Margin"=>5));
    
    /* Draw the scale */
    $graph->setGraphArea(60,50,$width-20,$height-$legendHeight);
    $formatGrid=array("Mode"=>SCALE_MODE_ADDALL_START0, "GridTicks"=>0,
        "DrawYLines"=>array(0), "DrawXLines"=>true,"Pos"=>SCALE_POS_LEFTRIGHT,
        "LabelRotation"=>90, "GridR"=>200,"GridG"=>200,"GridB"=>200);
    $dataSet->setSerieDrawable($capa,true);
    $graph->drawScale($formatGrid);
    $graph->Antialias = TRUE;
    $dataSet->setSerieDrawable($capa,false);
    $graph->drawStackedBarChart();
    $serie=0;
    foreach($sumProjUnit as $id=>$vals) {
      $serie+=1;
      $dataSet->removeSerie($arrayProjName[$id]);
    }
     $dataSet->setAxisPosition(0,AXIS_POSITION_RIGHT);
//     $dataSet->addPoints($cumulUnitDate,"sum");
//     $dataSet->setSerieDescription(i18n("cumulated"),"sum");
//     $dataSet->setSerieOnAxis("sum",0);
//     $dataSet->setAxisName(0,i18n("cumulated"));
    
//     $formatGrid=array("LabelRotation"=>90,"DrawXLines"=>FALSE,"DrawYLines"=>NONE);
//     $graph->drawScale($formatGrid);
    $dataSet->setSerieDrawable($capa,true);
    $dataSet->setPalette($capa,array("R"=>0,"G"=>0,"B"=>0));
    $graph->drawLineChart();
    $graph->drawPlotChart();
    $graph->drawLegend($width+30,17,array("Mode"=>LEGEND_VERTICAL, "Family"=>LEGEND_FAMILY_BOX ,
        "R"=>255,"G"=>255,"B"=>255,"Alpha"=>100,
        "FontR"=>55,"FontG"=>55,"FontB"=>55,
        "Margin"=>5));
    $imgName=getGraphImgName("criticalResTab");
    $graph->render($imgName);
    echo '<table width="95%" height:"98%;" style="margin-top:50px;" align="center"><tr><td align="center">';
    echo '<img src="' . $imgName . '" />';
    echo '</td></tr></table>';
    echo '<br/>';
    
  }
  
  public static function drawCriticalResourceActivityList($scale, $start, $end, $idProject=null, $limitedRow=null) {
    global $arrayProject;
    if (!isset(self::$_criticalResourceArray)) self::tranformPlanningResult($scale, $start, $end);
    $dates=array();
    for ($date=$start; $date<=$end; $date=addDaysToDate($date, 1)) {
      if ($scale=='month') $period=date('Ym', strtotime($date)); // pq_substr($date,0,4).pq_substr($date,5,2)
      if ($scale=='week') $period=getWeekNumberFromDate($date);
      else if ($scale=='quarter') {
        $year=date('Y', pq_strtotime($date));
        $month=date('m', pq_strtotime($date));
        $quarter=1+intval(($month-1)/3);
        $period=$year.'-Q'.$quarter;
      }
      $dates[$period]=$period;
    }
    $isColorBlind = (Parameter::getUserParameter('colorBlindPlanning') == 'YES')?true:false;
    $redColorA = 'linear-gradient(45deg, #63226b 6.25%, #9a3ec9 6.25%, #9a3ec9 43.75%, #63226b 43.75%, #63226b 56.25%, #9a3ec9 56.25%, #9a3ec9 93.75%, #63226b 93.75%);background-size: 8px 8px;';
    $redColorB = 'linear-gradient(45deg, #9a3ec9 6.25%, #cb9ce3 6.25%, #cb9ce3 43.75%, #9a3ec9 43.75%, #9a3ec9 56.25%, #cb9ce3 56.25%, #cb9ce3 93.75%, #9a3ec9 93.75%);background-size: 8px 8px;';
    echo '<table>';
    echo '<thead style="display:block;">';
    echo '<tr>';
    echo '<td style="min-width:112px"></td>';
    echo '<td style="min-width:54px"></td>';
    echo '<td style="min-width:54px"></td>';
    echo '<td style="min-width:148px"></td>';
    echo '<td style="min-width:148px"></td>';
    echo '<td style="min-width:74px"></td>';
    echo '<td class="reportTableHeader" style="min-width:228px" colspan="3" title="">'.lcfirst(i18n("colPlannedPeriod")).'</td>';
    echo '<td class="reportTableHeader" colspan="'.count($dates).'"><div class="dataContent" style="min-width:51px">'.lcfirst(i18n("colPeriod")).'</div></td>';
    echo '</tr>';
    echo '<tr>';
    echo '<td class="reportTableHeader" style="min-width:110px" >'.i18n("colIdResource").'</td>';
    echo '<td class="reportTableHeader" title="'.i18n('helpCriticalResourceCapacity').'"><div class="dataContent" style="width:54px">'.i18n("colCapacityCriticalResource").'</div></td>';
    echo '<td class="reportTableHeader" title="'.i18n('helpCriticalResourceAvailable').'"><div class="dataContent" style="width:54px">'.lcfirst(i18n("colAvailableCriticalResource")).'</div></td>';
    echo '<td class="reportTableHeader" style="min-width:148px">'.i18n("colIdProject").'</td>';
    echo '<td class="reportTableHeader" style="min-width:148px">'.i18n("colNotifiableItem").'</td>';
    echo '<td class="reportTableHeader" style="background: #305496 !important;"><div style="width:76px" title="'.i18n('helpCriticalLeftToPlan').'">'.lcfirst(i18n("colLeftToPlan")).'</div></td>';
    echo '<td class="reportTableHeader" style="background: #548235 !important;"><div style="width:76px" title="'.i18n('helpCriticalResourceUsed').'">'.lcfirst(i18n("usedMode")).'</div></td>';
    echo '<td class="reportTableHeader" style="background: #C65911 !important;"><div style="width:76px" title="'.i18n('helpCriticalResourceUsedOverbooked').'">'.lcfirst(i18n("overbookedMode")).'</div></td>';
    echo '<td class="reportTableHeader" style="background: #C65911 !important;"><div style="width:76px" title="'.i18n('helpCriticalResourceOverbooked').'">'.lcfirst(i18n("includeOverbooked")).'</div></td>';
    if (count($dates)==0) {
      echo '<td class="reportTableHeader" style="min-width:43px"><div>&nbsp;</div></td>';
    }
    foreach ($dates as $period) {
      $date=pq_substr($period, 4);
      if ($scale=='month') {
        $date=date('M', strtotime($period.'01'));
      }
      if ($scale=='quarter') {
        $date=pq_str_replace('-', '', $date);
      }
      echo '<td class="reportTableHeader" style="width:51px;min-width:51px;padding:unset !important"><div>'.$date.'</div><div>'.pq_substr($period, 0, 4).'</div></td>';
    }
    echo '</tr>';
    echo '</thead>';
    echo '<tbody style="display:block; overflow-y:auto; height:95%; width:100%;">';
    
    $cpt=0;
    if (! is_array($arrayProject)) $arrayProject=array();
    if ($idProject and pq_trim($idProject[0])=='') unset($idProject[0]);
    $sortArray = array();
    foreach (self::$_criticalResourceArray as $idRes=>$res) {
      if ($idProject) {
        $inArray=false;
        foreach ($idProject as $idProj) {
          if (!pq_trim($idProj)) continue;
          if (isset($arrayProject[$idProj])) continue;
          $proj=new Project($idProj, true);
          $arrayProject[$idProj]=$proj->name;
          $subList=$proj->getSubProjectsList(true);
          if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
        }
        foreach ($arrayProject as $idProj=>$val) {
          if (pq_array_key_exists($idProj, $res['projects'])) {
            $inArray=true;
          } else {
            continue;
          }
        }
        if (!$inArray) continue;
      }
      $firstRow=true;
      $cpt++;
      //if ($limitedRow and $cpt>$limitedRow) continue;
      $totalRes=$res['totalWork'];
      $surbookedRes=$res['totalSurbooked'];
      $availableRes=$res['totalAvailable'];
      $marginRes=$availableRes-$totalRes;
      if($res['isResourceTeam']){
        $marginRes -= $res['resourceTeamMarginSub'];
      }
      $indice = ($availableRes!=0)?round((($marginRes-$surbookedRes)/$availableRes)*100)*-1:0;
      uasort($res['projects'], function ($x, $y) {
          return $x['priority'] <=> $y['priority'];
      });
      $countProj=0;
      $cptProject=count($res['projects']);
//       $cptProject=array_map("count", $res['projects']);
//       $cptProject=array_sum($cptProject);
      foreach ($res['projects'] as $id=>$project) {
        $countProj++;
        $cptObject=count($project['object']);
        $countObj=0;
        foreach ($project['object'] as $idO=>$object) {
          $result = '';
          $countObj++;
          $total=$object['totalWork'];
          $plannedSurbooked=$object['plannedSurbooked'];
          $surbooked=$object['totalSurbooked'];
          $available=$res['totalAvailable'];
          $assigned=$object['assignedWork'];
          $leftWork=$object['leftWork'];
          $hiddenClass='';
          if ($cptObject>=1) {
            $hiddenClass=($firstRow)?'resourceSkillFirstRow':'resourceSkillHiddenRow';
          }
          if ($idProject) {
            $arrayProject=array();
            foreach ($idProject as $idProj) {
              if (!pq_trim($idProj)) continue;
              $proj=new Project($idProj, true);
              $arrayProject[$idProj]=$proj->name;
              $subList=$proj->getSubProjectsList(true);
              if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
            }
            if (!pq_array_key_exists($id, $arrayProject)) continue;
          }
          if ((!$firstRow and $cptProject <= 1 and $countObj==$cptObject) or ($firstRow and $cptProject <= 1 and $cptObject <= 1) or (!$firstRow and $cptProject > 1 and $countProj==$cptProject and $countObj==$cptObject)) {
            $hiddenClass='resourceSkillLastRow';
          }
          $result = '<tr style="height: 20px;">';
          if ($firstRow) {
            $result .='<td class="reportTableData '.$hiddenClass.'" style="text-align:left;position:relative"><div class="dataContent" style="width:118px"><div class="dataExtend" style="min-width:113px">'.$res['name'].'</div></div></td>';
            $result .='<td class="reportTableData '.$hiddenClass.'" style="min-width:62px">'.htmlDisplayNumericWithoutTrailingZeros($res['capacity']).'</td>';
            $result .='<td class="reportTableData '.$hiddenClass.'" style="min-width:62px;">'.Work::displayWorkWithUnit($available).'</td>';
          } else {
            $result .='<td class="reportTableData '.$hiddenClass.'" style="min-width:118px"></td>';
            $result .='<td class="reportTableData '.$hiddenClass.'" style="min-width:62px"></td>';
            $result .='<td class="reportTableData '.$hiddenClass.'" style="min-width:62px;"></td>';
          }
          $surbookedColor = ($surbooked > 0)?'background:'.(($isColorBlind)?'#ad8934':'#FFC000'):'background: #FCE4D6 !important;';
          $result .='<td class="reportTableData" style="white-space:nowrap; position:relative; text-align:left"><div class="dataContent" style="width:156px"><div class="dataExtend" style="min-width:152px">#'.$id.' '.$project['name'].'</div></div></td>';
          $result .='<td class="reportTableData" style="white-space:nowrap;position:relative; text-align:left"><div class="dataContent" style="width:156px"><div class="dataExtend" style="min-width:152px">#'.$object['refId'].' '.$object['name'].'</div></div></td>';
          $result .='<td class="reportTableData" style="min-width:84px;background: #D9E1F2 !important;">'.Work::displayWorkWithUnit($leftWork).'</td>';
          $result .='<td class="reportTableData" style="min-width:84px;background: #E2EFDA !important;">'.Work::displayWorkWithUnit($total).'</td>';
          $result .='<td class="reportTableData" style="min-width:84px;background: #FCE4D6 !important;">'.Work::displayWorkWithUnit($plannedSurbooked).'</td>';
          $result .='<td class="reportTableData" style="min-width:84px;'.$surbookedColor.'">'.Work::displayWorkWithUnit($surbooked).'</td>';
          $previousObj=null;
          $realPlanStartDate=$object['plan']['real']['startDate'];
          $realPlanEndDate=$object['plan']['real']['endDate'];
          $idealPlanStartDate=$object['plan']['ideal']['startDate'];
          $idealPlanEndDate=$object['plan']['ideal']['endDate'];
          if ($scale=='month') {
            $realEndPeriod=date('Ym', pq_strtotime($realPlanEndDate));
            $idealEndPeriod=date('Ym', pq_strtotime($idealPlanEndDate));
            $realStartPeriod=date('Ym', pq_strtotime($realPlanStartDate));
            $idealStartPeriod=date('Ym', pq_strtotime($idealPlanStartDate));
          } else if ($scale=='week') {
            $realEndPeriod=getWeekNumberFromDate($realPlanEndDate);
            $idealEndPeriod=getWeekNumberFromDate($idealPlanEndDate);
            $realStartPeriod=getWeekNumberFromDate($realPlanStartDate);
            $idealStartPeriod=getWeekNumberFromDate($idealPlanStartDate);
          } else if ($scale=='quarter') {
            $date=$realPlanEndDate; // $realPlanEndDate
            $year=date('Y', pq_strtotime($date));
            $month=date('m', pq_strtotime($date));
            $quarter=1+intval(($month-1)/3);
            $realEndPeriod=$year.'-Q'.$quarter;
            $date=$idealPlanEndDate; // $idealPlanEndDate
            $year=date('Y', pq_strtotime($date));
            $month=date('m', pq_strtotime($date));
            $quarter=1+intval(($month-1)/3);
            $idealEndPeriod=$year.'-Q'.$quarter;
            $date=$realPlanStartDate; // $realPlanStartDate
            $year=date('Y', pq_strtotime($date));
            $month=date('m', pq_strtotime($date));
            $quarter=1+intval(($month-1)/3);
            $realStartPeriod=$year.'-Q'.$quarter;
            $date=$idealPlanStartDate; // $idealPlanStartDate
            $year=date('Y', pq_strtotime($date));
            $month=date('m', pq_strtotime($date));
            $quarter=1+intval(($month-1)/3);
            $idealStartPeriod=$year.'-Q'.$quarter;
          }
          foreach ($dates as $period) {
            $workPeriod='';
            $result .='<td class="reportTableData" style="height:20px;padding:unset !important;"><table style="height:100%;width:100%">';
            if (isset($object['dates'][$scale][$period])) {
              $ideal=$object['dates'][$scale][$period]['ideal'];
              $real=$object['dates'][$scale][$period]['real'];
              foreach ($object['plan'] as $type=>$plan) {
                $result .='<tr style="height:50%;">';
                // object plan date
                if ($type=='ideal') {
                  $bgColor='';
                  if ($period>=$idealStartPeriod and $period<=$idealEndPeriod) {
                    if ($ideal['totalSurbooked']==0) {
                      $bgColor='background:'.(($isColorBlind)?'#67ff00':'#50BB50');
                    } else { // if ($ideal['totalSurbooked']!=0) {
                      $bgColor='background:'.(($isColorBlind)?'#ad8934':'#FFC000');
                      $workPeriod=Work::displayWorkWithUnit(round($ideal['totalSurbooked'], 1));
                    }
                  }
                  $result .='<td style="color:black;text-shadow: 1px 1px 2px white;'.$bgColor.';min-width:51px;position:relative;"><div style="position:absolute;top:1px;width:100%;height:100%;">'.$workPeriod.'</div></td>';
                } else if ($type=='real') {
                  $workPeriod='';
                  $bgColor='';
                  // may display blanks when no planned work XX_X__XXX
//                   if ($real['totalWork']!=0 and $period>=$idealStartPeriod and $period<=$idealEndPeriod and $realPlanStartDate<=$idealPlanEndDate) {
//                     $bgColor='background-color:#50BB50';
//                   } else if ($real['totalWork']!=0 and $realEndPeriod>$idealEndPeriod) {  // may display blanks when no planned work XX_X__XXX
//                     $bgColor='background-color:#BB5050';
//                   }
                  // Will display only one bar, without blanks XXXXXXXXX
                  if ($period>=$realStartPeriod and $period<=$realEndPeriod) {
                    if ($period<=$idealEndPeriod) {
                      $bgColor='background:'.(($real['totalWork']!=0)?(($isColorBlind)?'#67ff00':'#50BB50'):(($isColorBlind)?'#d1ffb3':'#AEC5AE'));
                      // } else if ($realStartPeriod<=$period and $realEndPeriod>$idealEndPeriod) { // Will display only one bar, without blanks XXXXXXXXX
                    } else { //if ($real['totalWork']!=0 and $realEndPeriod>$idealEndPeriod) {  // may display blanks when no planned work XX_X__XXX
                      $bgColor='background:'.(($real['totalWork']!=0)?(($isColorBlind)?$redColorA:'#BB5050'):(($isColorBlind)?$redColorB:'#BB9099;'));
                    }
                  }
                  $result .='<td style="color:black;text-shadow: 1px 1px 2px white;'.$bgColor.';min-width:51px;">'.$workPeriod.'</td>';
                }
                $result .='</tr>';
              }
            } else {
              $bgColor='';
              if ($period>=$idealStartPeriod and $period<=$idealEndPeriod) {
                $bgColor='background:'.(($isColorBlind)?'#d1ffb3':'#AEC5AE');
              }
              $result .='<tr><td style="color:black;'.$bgColor.';min-width:51px;"></td></tr>';
              $bgColor='';
              if ($period>=$realStartPeriod and $period<=$realEndPeriod) {
                if ($period<=$idealEndPeriod) {
                  $bgColor='background:'.($isColorBlind)?'#d1ffb3':'#AEC5AE';
                } else { 
                  $bgColor='background:'.($isColorBlind)?$redColorB:'#BB9099';
                }
              }          
              $result .='<tr><td style="color:black;'.$bgColor.';min-width:51px;"></td></tr>';
            }
            $result .='</table>';
          }
          $result .='</td></tr>';
          $firstRow=false;
          if(isset($sortArray[$indice.'.'.$idRes])){
            $sortArray[$indice.'.'.$idRes] .= $result;
          }else{
            $sortArray[$indice.'.'.$idRes] = $result;
          }
        }
      }
    }
    krsort($sortArray);
    $order = 0;
    foreach ($sortArray as $line){
      $order++;
      if($limitedRow){
        if($order <= $limitedRow)echo $line;
      }else{
        echo $line;
      }
    }
    echo '</tbody>';
    echo '</table>';
  }

  public static function drawCriticalProjectResourceList($scale, $start, $end, $idProject=null, $limitedRow=null) {
    global $arrayProject;
    if (!isset(self::$_criticalResourceArray)) self::tranformPlanningResult($scale, $start, $end);
    echo '<table _excel-name="'.i18n("menuParameter").'" style="width:100%">';
    $calcuteStartDate = (sessionValueExists('startDateCalculPlanning'))?getSessionValue('startDateCalculPlanning'):date('Y-m-d');
    echo '  <tr>';
    echo '    <td rowspan="4" '.excelFormatCell('header',30).'>'.i18n("menuParameter").'</td>';
    echo '    <td '.excelFormatCell('data',30, null, null, null ,'right').'>'.i18n("calculateStartDate").'</td>';
    echo '    <td '.excelFormatCell('data',20).'>'.htmlFormatDate($calcuteStartDate).'</td>';
    echo '  </tr>';
    echo '  <tr>';
    echo '    <td '.excelFormatCell('data',30, null, null, null ,'right').'>'.i18n("displayStartDate").'</td>';
    echo '    <td '.excelFormatCell('data',20).'>'.htmlFormatDate($start).'</td>';
    echo '  </tr>';
    echo '  <tr>';
    echo '    <td '.excelFormatCell('data',30, null, null, null ,'right').'>'.i18n("displayEndDate").'</td>';
    echo '    <td '.excelFormatCell('data',20).'>'.htmlFormatDate($end).'</td>';
    echo '  </tr>';
    $indicatorValueRed = (getSessionValue('CriticalResourceIndicatorRed'))?getSessionValue('CriticalResourceIndicatorRed'):Parameter::getGlobalParameter('CriticalResourceIndicatorRed');
    echo '  <tr>';
    echo '    <td '.excelFormatCell('data',30, null, null, null ,'right').'>'.i18n("indicatorValueDefinition").'</td>';
    echo '    <td '.excelFormatCell('data',20).'>'.$indicatorValueRed.'</td>';
    echo '  </tr>';
    echo '</table>';
    echo '<table'.excelName('CriticalProjectResourceList').'>';
    echo '  <thead>';
    echo '    <tr style="display:block;">';
    echo '      <td '.excelFormatCell('header',40).' class="reportTableHeader" style="min-width:231px">'.i18n("colIdProject").'</td>';
    echo '      <td '.excelFormatCell('header',10).' class="reportTableHeader"><div style="width:80px" title="'.i18n('helpCriticalResourceLate').'">'.lcfirst(i18n("colLate")).'</div></td>';
    echo '      <td '.excelFormatCell('header',15).' class="reportTableHeader"><div style="width:80px">'.lcfirst(i18n("colStrategicValue")).'</div></td>';
    echo '      <td '.excelFormatCell('header',10).' class="reportTableHeader"><div style="width:80px">'.lcfirst(i18n("Priority")).'</div></td>';
    echo '      <td '.excelFormatCell('header',10).' class="reportTableHeader"><div style="width:80px" title="'.i18n('helpCriticalResourceUsed').'">'.lcfirst(i18n("used")).'</div></td>';
    echo '      <td '.excelFormatCell('header',20).' class="reportTableHeader" style="min-width:110px">'.i18n("colIdResource").'</td>';
    echo '    </tr>';
    echo '  </thead>';
    echo '  <tbody style="display:block; overflow-y:scroll; height:200px; width:100%;">';
    $cpt=0;
    $totalArray=count(self::$_criticalResourceArray);
    if ($idProject and pq_trim($idProject[0])=='') unset($idProject[0]);
    $result=array();
    if (! is_array($arrayProject)) $arrayProject=array();
    foreach (self::$_criticalResourceArray as $idRes=>$res) {
      if ($idProject) {
        $inArray=false;
        foreach ($idProject as $idProj) {
          if (!pq_trim($idProj)) continue;
          if (isset($arrayProject[$idProj])) continue;
          $proj=new Project($idProj, true);
          $arrayProject[$idProj]=$proj->name;
          $subList=$proj->getSubProjectsList(true);
          if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
        }
        foreach ($arrayProject as $idProj=>$val) {
          if (pq_array_key_exists($idProj, $res['projects'])) {
            $inArray=true;
          } else {
            continue;
          }
        }
        if (!$inArray) continue;
      }
      $firstRow=true;
      $cpt++;
      if ($limitedRow and $cpt>$limitedRow) continue;
      uasort($res['projects'], function ($x, $y) {
  			return $x['priority'] <=> $y['priority'];
      });
      foreach ($res['projects'] as $id=>$project) {
        if ($idProject) {
          $arrayProject=array();
          foreach ($idProject as $idProj) {
            if (!pq_trim($idProj)) continue;
            $proj=new Project($idProj, true);
            $arrayProject[$idProj]=$proj->name;
            $subList=$proj->getSubProjectsList(true);
            if (count($subList)>0) $arrayProject=array_merge_preserve_keys($subList, $arrayProject);
          }
          if (!pq_array_key_exists($id, $arrayProject)) continue;
        }
        $wbs=$project['wbs'];
        $total=$project['totalWork'];
        $strategicValue=$project['strategicValue'];
        $validatedEndDate=$project['validatedEndDate'];
        $plannedEndDate=$project['plannedEndDate'];
        $priority=$project['priority'];
        $late='';
        if ($plannedEndDate!='' and $validatedEndDate!='') {
          $late=dayDiffDates($validatedEndDate, $plannedEndDate);
          $late='<div style="color:'.(($late>0)?'#DD0000':'#00AA00').';">'.$late;
          $late.=" ".i18n("shortDay");
          $late.='</div>';
        }
        
        $totalRes=$res['totalWork'];
        $surbooked=$res['totalSurbooked'];
        $available=$res['totalAvailable'];
        $margin=$available-$totalRes;
        if($res['isResourceTeam']){
          $margin -= $res['resourceTeamMarginSub'];
        }
        $indice = ($available!=0)?round((($margin-$surbooked)/$available)*100)*-1:0;
        $indiceRed = (getSessionValue('CriticalResourceIndicatorRed'))?getSessionValue('CriticalResourceIndicatorRed'):Parameter::getGlobalParameter('CriticalResourceIndicatorRed');
        $indiceOrange = (getSessionValue('CriticalResourceIndicatorOrange'))?getSessionValue('CriticalResourceIndicatorOrange'):Parameter::getGlobalParameter('CriticalResourceIndicatorOrange');
        $indiceColor = "";
        if($indiceRed > $indiceOrange){
          if($indice >= $indiceOrange and $indice < $indiceRed)$indiceColor = "orange";
          if($indice >= $indiceRed and $indice > $indiceOrange)$indiceColor = "red";
        }else {
          if($indice >= $indiceOrange and $indice > $indiceRed)$indiceColor = "orange";
          if($indice >= $indiceRed and $indice < $indiceOrange)$indiceColor = "red";
        }
        if($indiceColor!='red')continue;
        if (!isset($result[$priority.$wbs][$idRes])) $result[$priority.$wbs][$idRes]='';
        $result[$priority.$wbs][$idRes].='<tr style="height: 20px;position:relative">';
        $result[$priority.$wbs][$idRes].='<td class="reportTableData" style="text-align:left; width:225px; position:relative"><div class="dataContent" style="width:239px"><div class="dataExtend" style="min-width:235px">#'.$id.' '.$project['name'].'</div></div></td>';
        $result[$priority.$wbs][$idRes].='<td class="reportTableData"><div style="width:88px;">'.$late.'</div></td>';
        $result[$priority.$wbs][$idRes].='<td class="reportTableData"><div style="width:88px;">'.$strategicValue.'</div></td>';
        $result[$priority.$wbs][$idRes].='<td class="reportTableData"><div style="width:88px;">'.$priority.'</div></td>';
        $result[$priority.$wbs][$idRes].='<td class="reportTableData"><div style="width:88px;">'.Work::displayWorkWithUnit($total).'</div></td>';
        $result[$priority.$wbs][$idRes].='<td class="reportTableData" style="text-align:left;"><div class="dataContent" style="width:118px;position:relative"><div class="dataExtend" style="min-width:114px">'.$res['name'].'</div></div></td>';
        $result[$priority.$wbs][$idRes].='</tr>';
      }
    }
    ksort($result);
    foreach ($result as $projectRowList) {
      foreach ($projectRowList as $row) {
        echo $row;
      }
    }
    echo '</tbody>';
    echo '</table>';
  }
  
  public static function storeCriticalResourcePlanningResult($startDay) {
    global $cronnedScript, $fullListPlan, $arrayPlannedWork, $arrayRealWork, $arrayAssignment;
    // setSessionValue("CriticalResourceTable", array($startDay, $fullListPlan, $arrayPlannedWork, $arrayRealWork, $arrayAssignment)); Sauvegarde des donnees en session
    
    $dirLog=Parameter::getGlobalParameter("logFile");
    $dir=getCurrentDir($dirLog);
    
    $allData=array($startDay, $fullListPlan, $arrayPlannedWork, $arrayRealWork, $arrayAssignment);
    
    $file=fopen($dir.'critRes_allData.log', "w");
    file_put_contents($dir.'critRes_allData.log', serialize($allData));
    fclose($file);
    
    /*
     * Sauvegarde des données dans plusieurs fichiers
     * $file = fopen($dir. 'critRes_fullListPlan.log', "w");
     * file_put_contents($dir. 'critRes_fullListPlan.log', serialize($fullListPlan));
     * fclose($file);
     *
     * $file = fopen($dir. 'critRes_arrayPlannedWork.log', "w");
     * file_put_contents($dir. 'critRes_arrayPlannedWork.log', serialize($arrayPlannedWork));
     * fclose($file);
     *
     * $file = fopen($dir. 'critRes_arrayRealWork.log', "w");
     * file_put_contents($dir. 'critRes_arrayRealWork.log', serialize($arrayRealWork));
     * fclose($file);
     *
     * $file = fopen($dir. 'critRes_arrayAssignement.log', "w");
     * file_put_contents($dir. 'critRes_arrayAssignement.log', serialize($arrayAssignment));
     * fclose($file);
     *
     * $file = fopen($dir. 'critRes_startDay.log', "w");
     * file_put_contents($dir. 'critRes_startDay.log', serialize($startDay));
     * fclose($file);
     */
  }

  public static function getCriticalResourcePlanningResult() {
    global $cronnedScript, $fullListPlan, $arrayPlannedWork, $arrayRealWork, $arrayAssignment;
    
    /*
     * Sauvegarde des donnees en session
     * if (! sessionValueExists("CriticalResourceTable")) { return null;}
     * $cr=getSessionValue("CriticalResourceTable");
     * if (!is_array($cr)) return null;
     * $startDay=$cr[0];
     * $fullListPlan=$cr[1];
     * $arrayPlannedWork=$cr[2];
     * $arrayRealWork=$cr[3];
     * $arrayAssignment=$cr[4];
     * return $startDay;
     */
    
    $dirLog=Parameter::getGlobalParameter("logFile");
    $dir=getCurrentDir($dirLog);
    
    if (!file_exists($dir.'critRes_allData.log')) {
      return null;
    }
    
    projeqtor_set_memory_limit((2*filesize($dir.'critRes_allData.log')).'K');
    $array=unserialize(file_get_contents($dir.'critRes_allData.log'));
    if (is_array($array)) {
      $startDay=$array[0];
      $fullListPlan=$array[1];
      $arrayPlannedWork=$array[2];
      $arrayRealWork=$array[3];
      $arrayAssignment=$array[4];
    } else {
      $startDay=date('Y-m-d');
      $fullListPlan=array();
      $arrayPlannedWork=array();
      $arrayRealWork=array();
      $arrayAssignment=array();
    }
    /*
     * Sauvegarde des données dans plusieurs fichiers
     * if (!file_exists($dir.'critRes_fullListPlan.log')) {return null;}
     * if (!file_exists($dir.'critRes_arrayPlannedWork.log')) {return null;}
     * if (!file_exists($dir.'critRes_arrayRealWork.log')) {return null;}
     * if (!file_exists($dir.'critRes_arrayAssignement.log')) {return null;}
     * if (!file_exists($dir.'critRes_startDay.log')) {return null;}
     *
     * $startDay= unserialize(file_get_contents($dir.'critRes_startDay.log'));
     * $fullListPlan= unserialize(file_get_contents($dir.'critRes_fullListPlan.log'));
     * $arrayPlannedWork= unserialize(file_get_contents($dir.'critRes_arrayPlannedWork.log'));
     * $arrayRealWork= unserialize(file_get_contents($dir.'critRes_arrayRealWork.log'));
     * $arrayAssignment= unserialize(file_get_contents($dir.'critRes_arrayAssignement.log'));
     */
    
    return $startDay;
  }

  public static function unsetCriticalResourcePlanningResult() {
    
    /*
     * Sauvegarde des donnees en session
     * if (! sessionValueExists("CriticalResourceTable")) { return false;}
     * unsetSessionValue("CriticalResourceTable");
     */
    $dirLog=Parameter::getGlobalParameter("logFile");
    $dir=getCurrentDir($dirLog);
    
    if (!file_exists($dir.'critRes_allData.log')) {
      return null;
    }
    
    unlink($dir.'critRes_allData.log');
    
    /*
     * Sauvegarde des donnees dans plusieurs fichiers
     * if (!file_exists($dir.'critRes_fullListPlan.log')) {return null;}
     * if (!file_exists($dir.'critRes_arrayPlannedWork.log')) {return null;}
     * if (!file_exists($dir.'critRes_arrayRealWork.log')) {return null;}
     * if (!file_exists($dir.'critRes_arrayAssignement.log')) {return null;}
     * if (!file_exists($dir.'critRes_startDay.log')) {return null;}
     *
     * unlink($dir.'critRes_fullListPlan.log');
     * unlink($dir.'critRes_arrayPlannedWork.log');
     * unlink($dir.'critRes_arrayRealWork.log');
     * unlink($dir.'critRes_arrayAssignement.log');
     * unlink($dir.'critRes_startDay.log');
     */
    
    return true;
  }
  
  /**
   * 
   * @param string $email the email to search (not case sensitive search)
   * @param boolean $exact search case sensitive if true, default is not case sensitive (false)
   * @param string $ifDuplicate how to treat duplicate emails : 
   *        'first' always return first item (sorted by not idle, is user, is resource)
   *        'null'  return null if duplicate exists
   *        'exact' return the first that has the exact case sensitive email
   * @return Affectable object
   */
  public static function getAffectableFromEmail($email, $exactCase=false, $ifDuplicate='first') {
    $aff=new Affectable();
    $crit=($exactCase)?"email='$email'":"LOWER(email)='".pq_strtolower($email)."'";
    $listAff=$aff->getSqlElementsFromCriteria(null,null,$crit,'idle asc, isUser desc, isResource desc');
    if (count($listAff)==0) return $aff;
    if (count($listAff)==1) return reset($listAff);
    if ($ifDuplicate=='first') return $listAff[0];
    if ($ifDuplicate=='null') return $aff;
    $found=$listAff[0];
    foreach ($listAff as $current) {
      if ($current->email===$email) {
        return $current;
      }
    }
    return $found;
  }

}
?>