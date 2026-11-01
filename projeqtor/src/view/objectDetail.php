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

/*
 * ============================================================================ Presents the detail of an object, for viewing or editing purpose.
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
$reorg=(isset($paramReorg) and $paramReorg==false)?false:true;
$leftPane="";
$rightPane="";
$extraPane="";
$bottomPane="";
$historyPane="";
$panes=array();
$arrayPanes=array('paneDescription','paneTreatment','paneAllocation','paneProgress','paneProposal','paneConfiguration','paneDetail','paneDependency','paneCheckList','paneLink','paneFichier','paneNote','paneHistory');
// $panes['detail']="";
// $panes['description']="";
// $panes['link']="";
// $panes['treatment']="";
// $panes['dependency']="";
// $panes['progress']="";
// $panes['note']="";
// $panes['allocation']="";
// $panes['configuration']="";
// $panes['fichier']="";
// $panes['history']="";
// $panes['checkList']="";
$arrayGroupe=array();
$layout=Parameter::getUserParameter('paramLayoutObjectDetail');
if (isIE()) $layout='col';
scriptLog('   ->/view/objectDetail.php');
if (!isset($comboDetail)) {
  $comboDetail=false;
}
$collapsedList=Collapsed::getCollaspedList();
$readOnly=false;
if (false===function_exists('lcfirst')) {

  function lcfirst($str) {
    $str[0]=pq_strtolower($str[0]);
    return (string)$str;
  }
}
$preseveHtmlFormatingForPDF=true;
// ********************************************************************************************************
// MAIN PAGE
// ********************************************************************************************************
// fetch information depending on, request
$objClass=$_REQUEST['objectClass'];
$objClass=Security::checkValidClass($objClass, 'objectClass');
if (isset($_REQUEST['noselect']) or !$objClass) {
  $noselect=true;
}
// MTY - LEAVE SYSTEM
$canReadLeave=true;
// MTY - LEAVE SYSTEM

if (!isset($noselect)) {
  $noselect=false;
}
$currentPlanning='';
if(RequestHandler::isCodeSet('currentPlanning')){
  $currentPlanning=RequestHandler::getValue('currentPlanning');
}
//gautier
$objInsert = false;
$selectedResource=null;
$insertPlanningItem = RequestHandler::getValue('insertItem');
if($insertPlanningItem){
  $currentItemParent = RequestHandler::getId('currentItemParent');
  $classItemParent = RequestHandler::getClass('originClass');
  if (SqlElement::class_exists($classItemParent)) $objInsert = new $classItemParent($currentItemParent);
  if(isset($objInsert) and $currentPlanning=='ResourcePlanning'){
      $selectedResource=RequestHandler::getValue('resourcePlanningSelectedResource');
  }
}
$sourceItem=RequestHandler::getValue('sourceItem',false,null);
if ($sourceItem) {
  $sourceItemSplit=explode('_',$sourceItem);
  $sourceItemClass=$sourceItemSplit[0];
  $sourceItemId=$sourceItemSplit[1];
  $objInsert=new $sourceItemClass($sourceItemId);
}
$print=false;
if (pq_array_key_exists('print', $_REQUEST) or isset($callFromMail)) {
  $print=true;
}

$displayWidth='98%';
if ($print) $reorg=false;
if ($print and isset($outMode) and $outMode=='pdf') {
  $reorg=false;
  if (isset($orientation) and $orientation=='L') $printWidth=1080;
  else $printWidth=760;
} else {
  if (isset($outModeBack) and $outModeBack=='pdf') {
    $printWidth='980';
  } else {
    $printWidth=980;
  }
}
if (pq_array_key_exists('destinationWidth', $_REQUEST)) {
  $width=$_REQUEST['destinationWidth'];
  $width-=30;
  $displayWidth=$width.'px';
} else {
  if (sessionValueExists('screenWidth')) {
    $detailWidth=round((getSessionValue('screenWidth')*0.8)-15); // 80% of screen - split barr - padding (x2)
  } else {
    $displayWidth='98%';
  }
}
if ($print) {
  $displayWidth=$printWidth.'px'; // must match iFrame size (see main.php)
}
$colWidth=intval($displayWidth); // Initialized to be sure...

if ($noselect) {
  $objId="";
  $obj=null;
  $profile=getSessionUser()->idProfile;
} else {
  $objId=$_REQUEST['objectId'];
  if ($objClass=='GlobalView') {
    $expl=pq_explode('|', $objId);
    $objClass=$expl[0];
    $objId=$expl[1];
  }
  $obj=new $objClass($objId);
  $profile=getSessionUser()->getProfile($obj);
// MTY - LEAVE SYSTEM
  if (isLeavesSystemActiv()) {
    if (property_exists($obj, 'idProject')) {
        if (Project::isTheLeaveProject($obj->idProject) && !Project::isProjectLeaveVisible()) {
          $canReadLeave=false;
        }
    }
  }
// MTY - LEAVE SYSTEM  
  //gautier   
  if ($objClass=='Resource' and $obj->isResourceTeam) {
    $objClass='ResourceTeam';
    $obj=new ResourceTeam($objId);
  }
  if (pq_array_key_exists('refreshComplexities', $_REQUEST)) {
      $nbComplexities = RequestHandler::getValue('nb');
      $complexity = new Complexity();
      $list = $complexity->getSqlElementsFromCriteria(array('idCatalogUO'=>$obj->id));
      drawComplexities($nbComplexities,$obj,$list,true);
      exit();
  }
  if (pq_array_key_exists('refreshComplexitiesValues', $_REQUEST)) {
        $wu = new WorkUnit();
        $listWorkUnit = $wu->getSqlElementsFromCriteria(array('idCatalogUO'=>$obj->id));
        $complexity = new Complexity();
        $listComplexity = $complexity->getSqlElementsFromCriteria(array('idCatalogUO'=>$obj->id));
        drawWorkUnits($obj,$listWorkUnit,$listComplexity,true);
        exit();
  }
  if(pq_array_key_exists('refreshWorkTokenMarkup', $_REQUEST)){
    WorkTokenMarkup::drawWorkTokenMarkup($obj, $print);
    exit();
  }
  if(pq_array_key_exists('refreshWorkClientContract', $_REQUEST)){
    WorkTokenClientContract::drawWorkTokenClientContract($obj, $print);
    exit();
  }
  if (pq_array_key_exists('refreshNotes', $_REQUEST)) {
    $nbColMax=1;
    drawNotesFromObject($obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshBillLines', $_REQUEST)) {
    drawBillLinesFromObject($obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshJobDefinition', $_REQUEST)) {
    drawJobDefinitionFromObject($obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshChecklistDefinitionLines', $_REQUEST)) {
    drawChecklistDefinitionLinesFromObject($obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshRaciMatrix', $_REQUEST)) {
    echo $obj->drawSpecificItem('raciMatrix');
    exit();
  }
  if (pq_array_key_exists('refreshAttachments', $_REQUEST)) {
    drawAttachmentsFromObject($obj, true);
    exit();
  }
  /*
   * On assignment change refresh all item if (pq_array_key_exists ( 'refreshAssignment', $_REQUEST )) { drawAssignmentsFromObject($obj->_Assignment, $obj, true ); exit (); }
   */
  if (pq_array_key_exists('refreshResourceCost', $_REQUEST)) {
    drawResourceCostFromObject($obj->$_ResourceCost, $obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshVersionProject', $_REQUEST)) {
    drawVersionProjectsFromObject($obj->$_VersionProject, $obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshProductProject', $_REQUEST)) {
    drawProductProjectsFromObject($obj->$_ProductProject, $obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshDocumentVersion', $_REQUEST)) {
    drawVersionFromObjectFromObject($obj->$_DocumentVersion, $obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshTestCaseRun', $_REQUEST)) {
    drawTestCaseRunFromObject($obj->_TestCaseRun, $obj, true);
    exit();
  }
  if (pq_array_key_exists('refreshLinks', $_REQUEST)) {
    $refreshLinks=$_REQUEST['refreshLinks'];
    if (property_exists($obj, '_Link_'.$refreshLinks)) {
      $lnkFld='_Link_'.$refreshLinks;
      drawLinksFromObject($obj->$lnkFld, $obj, $refreshLinks, true);
    } else if (property_exists($obj, '_Link') && $refreshLinks) {
      drawLinksFromObject($obj->_Link, $obj, null, true);
    }
    exit();
  }
  if (pq_array_key_exists('refreshHistory', $_REQUEST)) {
    $treatedObjects[]=$obj;
    foreach ($obj as $col=>$val) {
      if (is_object($val)) {
        $treatedObjects[]=$val;
      }
    }
    drawHistoryFromObjects(true);
    if (isset($dynamicDialogHistory) and $dynamicDialogHistory and function_exists('showCloseButton')) {
      showCloseButton();
    }
    exit();
  }
  if (pq_array_key_exists('comboDetailAssignment', $_REQUEST)) {
    if(pq_array_key_exists('objectClass', $_REQUEST) and pq_array_key_exists('objectId', $_REQUEST)){
      $objectClass=$_REQUEST['objectClass'];
      $objectId=$_REQUEST['objectId'];
      $obj = new $objectClass($objectId);
    }
    drawAssignmentsFromObject($obj->_Assignment, $obj, false, true);
    if (isset($dynamicDialogEditAssignment) and $dynamicDialogEditAssignment and function_exists('showCloseButton')) {
      showCloseButton();
    }
    exit();
  }
  if (pq_array_key_exists('comboDetailAffectation', $_REQUEST)) {
    $aff=new Affectation();
    $critArray=array('idProject'=>(($obj->id)?$obj->id:'0'));
    $affList=$aff->getSqlElementsFromCriteria($critArray, false);
    drawAffectationsFromObject($affList, $obj, 'ResourceAll', false, true);
    if (isModernUi()) echo '<br/>';
    drawAffectationsFromObject($affList, $obj, 'Contact', false, true);
    if (isModernUi()) echo '<br/>';
    drawAffectationsFromObject($affList, $obj, 'User', false, true);
    if (isset($dynamicDialogEditAffectation) and $dynamicDialogEditAffectation and function_exists('showCloseButton')) {
      showCloseButton();
    }
    exit();
  }
}
// save the current object in session
if (!$print and $obj) {
  if (!$comboDetail) {
    SqlElement::setCurrentObject($obj);
  } else {
    SqlElement::setCurrentObject($obj, true);
  }
}
$refresh=false;
if (pq_array_key_exists('refresh', $_REQUEST)) {
  $refresh=true;
}

$treatedObjects=array();

if ($print) {
  echo '<br/>';
  echo '<div class="reportTableHeader" style="width:'.($printWidth-10).'px;font-size:150%;color:#ffffff;">'.i18n($objClass).' #'.($objId+0).((property_exists($objClass, 'name') and $obj->name)?'&nbsp;-&nbsp;'.htmlEncode($obj->name):'').'</div>';
  echo '<br/>';
}

// New refresh method
if (pq_array_key_exists('refresh', $_REQUEST)) {
  if (!$print) {
    echo '<input type="hidden" id="objectClassName" name="objectClassName" value="'.$objClass.'" />'.$cr;
  }
  drawTableFromObject($obj);
//   drawChecklistFromObject($obj);
//   drawJoblistFromObject($obj);
  exit();
}
?>

<div <?php echo ($print)?'x':'';?>
	dojoType="dijit.layout.BorderContainer">
  <?php
  if (!$refresh and !$print) {
    echo '<input type="hidden" id="ckeditorType" value="'.getEditorType().'" />';
    ?>
  <div id="buttonDiv" dojoType="dijit.layout.ContentPane" region="top" 
		style="z-index: 3; height: 36px; position: relative; overflow: visible !important;">
		<?php  include 'objectButtons.php'; ?>
  </div>
<div id="formDiv" dojoType="dijit.layout.ContentPane" region="center" style="overflow:<?php if($layout=='tab' ){echo 'hidden';}else{echo 'auto';}?>;"
	  ondragover="dropFilesFormOnDragOver();" 
	  ondragleave="dropFilesFormOnDragLeave();" 
	       ondrop="dropFilesFormOnDrop();">
  <div id="dropFilesInfoDiv" style="pointer-events: none;" ondrop="return false;">
    <div style="position:absolute;top:50%;margin-top:-25px;height:px;width:100%;text-align:center;style="pointer-events: none;"><?php echo i18n('dragAndDrop');?></div>
  </div>
	<?php
  }
  if (!$print) {
    ?>  
<form dojoType="dijit.form.Form" id="objectForm" jsId="objectForm" ondragover="event.preventDefault();" ondrop="event.preventDefault();"
			name="objectForm" encType="multipart/form-data" action="" method="">
			<script type="dojo/method" event="onShow">
        if (dijit.byId('name') && dojo.byId('id') && ! dojo.byId('id').value) setTimeout("dijit.byId('name').focus()",100);;
      </script>
			<script type="dojo/method" event="onSubmit">
        // Don't do anything on submit, just cancel : no button is default => must click
		    //submitForm("../tool/saveObject.php"+addTokenIndexToUrl('?'),"resultDivMain", "objectForm", true);
		    return false;        
        </script>
			<div style="width: 100%; height: 100%;">
				<div id="detailFormDiv" dojoType="dijit.layout.ContentPane"
					region="top" style="width: 100%; height: 100%;"
					onmouseout="hideGraphStatus();">
          <?php
  }
  $noData=htmlGetNoDataMessage($objClass);
  $canRead=securityGetAccessRightYesNo('menu'.get_class($obj), 'read', $obj)=="YES";
  if (!$obj->id) {
    $canRead=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
    $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj, $user)=="YES";
    if (!$canRead or !$canUpdate) {
      $accessRightRead=securityGetAccessRight('menu'.get_class($obj), 'read', $obj, $user);
      $accessRightUpdate=securityGetAccessRight('menu'.get_class($obj), 'update', null, $user);
      if (($accessRightRead=='OWN' or $accessRightUpdate=='OWN') and property_exists($obj, 'idUser')) {
        $canRead=true;
        $obj->idUser=$user->id;
      } else if (($accessRightRead=='RES' or $accessRightUpdate=='RES') and property_exists($obj, 'idResource')) {
        $canRead=true;
        $obj->idResource=$user->id;
      }
    }
  }
  
  if (get_class($obj)=='Project' and isset($obj->codeType) and $obj->codeType=='TMP') {
    $canRead=true;
  }
  if ($noselect) {
    echo "$noData<input type='hidden' id='noDataInObjectDetail' />";
// MTY - LEAVE SYSTEM    
//  } else if (!$canRead) {
  } else if (!$canRead || !$canReadLeave) {
// MTY - LEAVE SYSTEM    
    echo htmlGetNoAccessMessage($objClass);
    echo "</div></form>";
    exit();
  } else if ($objId and !$obj->id) {
    echo htmlGetDeletedMessage($objClass);
    echo "</div></form>";
    exit();
  } else {
    if (!$print or $comboDetail) {
      echo '<input type="hidden" id="objectClassName" name="objectClassName" value="'.$objClass.'" />'.$cr;
    }
    drawTableFromObject($obj);
//       drawChecklistFromObject($obj);
//       drawJoblistFromObject($obj);
  }
  
  if (!$print) {
    echo'</div></div></form>';
  }
  if (!$print) echo '<div style="display:none; width: '.$displayWidth.'" dojoType="dijit.TitlePane">';
  else echo "<div>";
  echo '</div>';  

  if ( ! $refresh and  ! $print) {
    echo '</div>';
  }
  echo '</div>';

/**
 * ===========================================================================
 * Draw all the properties of object as html elements, depending on type of data
 *
 * @param $obj object to present
 * @param $included boolean
 *          indicating wether the function is called recursively or not
 * @return void
 */
function drawTableFromObject($obj, $included=false, $parentReadOnly=false, $parentHidden=false) {
  scriptLog("drawTableFromObject(obj, included=$included, parentReadOnly=$parentReadOnly)");
  global $toolTip, $cr, $print, $treatedObjects, $displayWidth, $outMode, $outModeBack, $comboDetail, $collapsedList, $printWidth, $profile, $detailWidth, $readOnly, $largeWidth, $widthPct, $nbColMax, $preseveHtmlFormatingForPDF, $reorg,$paneDetail, $leftPane, $rightPane, $extraPane, $bottomPane, $historyPane,$panes,$arrayGroupe, $nbColMax, $section, $beforeAllPanes, $colWidth,$objInsert,$currentPlanning,$layout,$selectedResource;
  global $section, $prevSection;
  // Extra performance 
  SqlElement::$_cachedQuery['OtherVersion']=array(); // PBE : performance improvments
  
  $ckEditorNumber=0; // Will be used only if getEditor=="CK" for CKEditor
  //gautier
  if($objInsert){
    if(get_class($objInsert)=='Project'){
      if(pq_substr(get_class($obj), 0, 7)== 'Project'){
        $obj->idProject = $objInsert->idProject;
      }else{
        $obj->idProject = $objInsert->id;
      }
    }else{
      $obj->idProject = $objInsert->idProject;
    }
    if (property_exists($obj, 'idActivity') and property_exists($objInsert, 'idActivity')) {
      $obj->idActivity = $objInsert->idActivity;
    }
    //florent
    if($currentPlanning =='ResourcePlanning'){
      if(property_exists($objInsert, '_Assignment') and property_exists($obj, '_Assignment') ){
        foreach ($objInsert->_Assignment as $val){
          foreach ($val as $id=>$value){
            if($id=='idResource' and $value==$selectedResource ){
              echo '<input type="hidden" id="resourcePlanningAssignment" value="'.$selectedResource.'" />';
              break;
            }
          }
        }
      }
    } else if($currentPlanning =='VersionsPlanning'){
      if(property_exists($obj, 'idProduct')and  property_exists($objInsert, 'idProduct') ){
        $obj->idProduct=$objInsert->idProduct;
      }
      if(property_exists($obj, 'idComponent')and  property_exists($objInsert, 'idComponent') ){
        $obj->idComponent=$objInsert->idComponent;
      }
      if(property_exists($obj, 'idTargetProductVersion')and  property_exists($objInsert, 'idTargetProductVersion') ){
        $obj->idTargetProductVersion=$objInsert->idTargetProductVersion;
      }
      if(property_exists($obj, 'idTargetComponentVersion')and  property_exists($objInsert, 'idTargetComponentVersion') ){
        $obj->idTargetComponentVersion=$objInsert->idTargetComponentVersion;
      }
    }
    $planningElementClass = get_class($objInsert).'PlanningElement';
    if (property_exists(get_class($objInsert), $planningElementClass)) {
      $idPlanningElementOrigin = $objInsert->$planningElementClass->id;
      echo "<input type='hidden' name='moveToAfterCreate' value='$idPlanningElementOrigin' />";
    }
  }

  if (property_exists($obj, '_sec_Assignment')) {
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'assignmentView'));
    if ($habil and $habil->rightAccess!=1) {
      //gautier #directAccess
      $ass = new Assignment();
      $assigned = $ass->countSqlElementsFromCriteria(array('idResource'=>getCurrentUserId(),'refId'=>$obj->id,'refType'=>get_class($obj)));
      if(!$assigned){
        unset($obj->_sec_Assignment);
      }
    }
  }
  if ($print) $obj->_nbColMax=1;
  $currencyGlobal=Parameter::getGlobalParameter('currency');
  $currencyPositionGlobal=Parameter::getGlobalParameter('currencyPosition');
  $currency=$currencyGlobal;
  $currencyPosition=$currencyPositionGlobal;
  $showThumb=Parameter::getUserParameter('paramShowThumb'); // show thumb between label and field ?
  if ($showThumb=='NO') {
    $showThumb=false;
  } else {
    $showThumb=true;
  }
  $treatedObjects[]=$obj;
  $dateWidth='72';
  if (isNewGui()) $dateWidth='85';
  $verySmallWidth='44';
  if (isNewGui()) $verySmallWidth='60';
  $smallWidth='72';
  if (isNewGui()) $smallWidth='100';          
  $mediumWidth='197';
  if (isNewGui()) $mediumWidth='227';
  $largeWidth='300';
  if (isNewGui()) $largeWidth='310';
  $labelWidth=(isNewGui())?175:160; // To be changed if changes in css file (label and .label) + = width in css + 15
  
  if ($outMode=='pdf') {
    // $labelWidth=40;
    // $labelStyleWidth=$labelWidth . 'px;';
  }
  if ($print and !isNewGui()) {
    $labelWidth=225;
    $labelStyleWidth='230px';
  }
  $labelStyleWidth=($labelWidth-((isNewGui())?-7:15)).'px';
  $fieldWidth=$smallWidth;
  $extName="";
  $user=getSessionUser();
  $displayComboButton=false;
  $habil=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile'=>$profile, 'scope'=>'combo'));
  if ($habil) {
    $list=new ListYesNo($habil->rightAccess);
    if ($list->code=='YES') {
      $displayComboButton=true;
    }
  }
  if ($comboDetail) {
    $extName="_detail";
  }
  $detailWidth=null; // Default detail div width
                     // Check screen resolution, to determine max field width (largeWidth)
  if (pq_array_key_exists('destinationWidth', $_REQUEST)) {
    $detailWidth=$_REQUEST['destinationWidth'];
  } else {
    if (sessionValueExists('screenWidth')) {
      $detailWidth=round((getSessionValue('screenWidth')*0.8)-15); // 80% of screen - split barr - padding (x2)
    }
  }
  // Set some king of responsive design : number of display columns depends on screen width
  $nbColMax=getNbColMax($displayWidth, $print, $printWidth, $obj);
  $currentCol=0;
  $nbCol=$nbColMax;
  
  // Define internalTable values, to present data as a table
  $internalTable=0;
  $internalTableCols=0;
  $internalTableRows=0;
  $internalTableCurrentRow=0;
  $internalTableSpecial='';
  $internalTablePrintCompact=false;
  $internalTableRowsCaptions=array();
  $classObj=get_class($obj);
  if ($obj->id=='0') {
    $obj->id=null;
  }
  //$type=$classObj.'Type';
  //if ($classObj=="PeriodicMeeting") $type="MeetingType";
  $type=SqlElement::getTypeClassName($classObj);
  //$idType='id'.$type;
  $idType=SqlElement::getTypeName($classObj);
  $objType=null;
  global $defaultProject;
  if (!$included) $defaultProject=null;
  if (!$defaultProject and sessionValueExists('project') and getSessionValue('project')!='*') {
    $defaultProject=getSessionValue('project');
    if(pq_strpos($defaultProject, ",") != null){
      $defaultProject=explode(',',$defaultProject)[0];
    }
  } else if (! $defaultProject) { // May be retreived if included
    $table=SqlList::getList('Project', 'name', null);
    $restrictArray=array();
    if (! Project::isProjectLeaveVisible()) unset($table[Project::getLeaveProjectId()]);
    if (!$user->_accessControlVisibility) {
      $user->getAccessControlRights(); // Force setup of accessControlVisibility
    }
    if ($user->_accessControlVisibility!='ALL') {
      $restrictArray=$user->getVisibleProjects(true);
    }
    if($objInsert){
      if (get_class($obj)=='Project' or get_class($obj)=='ProjectPlanningElement') $defaultProject = $obj->id;
      else $defaultProject = $obj->idProject;
    } else if (count($table)>0 and property_exists($obj, 'idProject')) {
      $firstId=null;
      $menuClass=pq_str_replace(array('PlanningElement','WorkElement'),'',$obj->getMenuClass());
      foreach ($table as $idTable=>$valTable) {
        if (count($restrictArray)==0 or isset($restrictArray[$idTable])) {
          if (! $obj->id) {
            if (property_exists($obj, 'refType') and $obj->refType) { 
              $refType=$obj->refType;
              $tmpObj=new $refType(); 
            } else { 
              $tmpObj=clone($obj); 
            }
            if (get_class($tmpObj)=='Project') { $tmpObj->id=$idTable; } 
            else { $tmpObj->idProject=$idTable; }
            $controlRightsTable=$user->getAccessControlRights($tmpObj);
            if (isset($controlRightsTable[$menuClass])) {
              $controlRights=$controlRightsTable[$menuClass];
              if (isset($controlRights["create"]) and $controlRights["create"]=='NO') {
                continue;
              }
            }
          }
          $firstId=$idTable;
          break;
        }
      }
      if (get_class($obj)=='Project' or get_class($obj)=='ProjectPlanningElement') $defaultProject = $obj->id;
      else $defaultProject=$firstId;
    }
  }
  if (property_exists($obj, $idType)) {
    if (!$obj->id) {
      if (SqlElement::class_exists($type)) {
        $listRestrictType=Type::listRestritedTypesForClass($type, $defaultProject, null, null);
        $listType=SqlList::getList($type);
        foreach ($listType as $keyType=>$valType) {
          if (in_array($keyType, $listRestrictType) or count($listRestrictType)==0) {
            $objType=new $type($keyType);
            break;
          }
        }
      }
    } else {
      if (SqlElement::class_exists($type)) $objType=new $type($obj->$idType);
    }
  } else if ($included) {
    $type=$obj->refType.'Type';
    $idType='id'.$type;
    if (!$obj->id) {
      if (SqlElement::class_exists($type)) {
        $listRestrictType=Type::listRestritedTypesForClass($type, $defaultProject, null, null);
        $listType=SqlList::getList($type);
        foreach ($listType as $keyType=>$valType) {
          if (in_array($keyType, $listRestrictType) or count($listRestrictType)==0) {
            $objType=new $type($keyType);
            break;
          }
        }
      }
    } else {
      if (SqlElement::class_exists($obj->refType)) {
        $orig=new $obj->refType($obj->refId,true);
        if (SqlElement::class_exists($type)) $objType=new $type($orig->$idType);
      }
    }
  }
  if (Project::isMultiCurrencyEnabled() and !$obj->id and Project::hasProjectCurrency($defaultProject) and property_exists($obj, 'idProject') and get_class($obj)!='Project') {
    $obj->idProject=$defaultProject;
  } 
  if (!$included) $section='';
  $nbLineSection=0;
  if (SqlElement::is_subclass_of($obj, 'PlanningElement')) { 
    $obj->setVisibility(getSessionUser()->getProfile(($obj->idProject)?$obj->idProject:$defaultProject));
    $workVisibility=$obj->_workVisibility;
    $costVisibility=$obj->_costVisibility;
    //if (get_class($obj)=="MeetingPlanningElement" or get_class($obj)=="PeriodicMeetingPlanningElement") {
    //  $obj->setAttributes($workVisibility, $costVisibility);
    //} else 
    if (method_exists($obj, 'setAttributes')) {
      $obj->setAttributes();
    }
    if (method_exists($obj, 'calculateFieldsForDisplay')) {
      $obj->calculateFieldsForDisplay();
    }
    
    // ADD BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY
    if(property_exists($obj, '_separator_sectionCostWork_marginTop')){//#3897 Gautier damian
      $isSeparatorWork = false;
      $countCost = false;
      $countWork = false;
      foreach ($obj->getFieldsList() as $col) {
        if($col == "_separator_sectionCostWork_marginTop"){
          $isSeparatorWork = true;
        }
        if(!$isSeparatorWork)continue;
        if(pq_substr($col, -4) == 'Work'){
          if(!$obj->isAttributeSetTofield($col, 'hidden')){
            $countWork = true;
          }
        }
        if(pq_substr($col, -4) == 'Cost'){
          if(!$obj->isAttributeSetTofield($col, 'hidden')){
            $countCost = true;
          }
        }
        if($col=="_separator_menuReview_marginTop"){
          break;
        }
      }
    }
    if(property_exists($obj, '_separator_menuTechnicalProgress_marginTop')){
      if(($obj->isAttributeSetTofield("_separator_menuTechnicalProgress_marginTop", 'hidden'))) unset($obj->_separator_menuTechnicalProgress_marginTop);
    }
    if(property_exists($obj, '_separator_sectionRevenue_marginTop')){
      if(($obj->isAttributeSetTofield("_separator_sectionRevenue_marginTop", 'hidden'))) unset($obj->_separator_sectionRevenue_marginTop);
    }
  } else if (SqlElement::is_subclass_of($obj, 'BudgetElement')) {
    $obj->setVisibility();
    $workVisibility=$obj->_workVisibility;
    $costVisibility=$obj->_costVisibility;
    if (get_class($obj)=="OrganizationBudgetElement" or get_class($obj)=="OrganizationBudgetElementCurrent") {
      $obj->setAttributes();
    }
    // END ADD BY Marc TABARY - 2017-02-16 - WORK AND COST VISIBILITY
  } else if (method_exists($obj, 'setAttributes')) {
    $obj->setAttributes();
  }
  if (method_exists($obj, 'setAttributesForBudget')) {
    $obj->setAttributesForBudget();
  }
  if (method_exists($obj, 'calculateFieldsForDisplay')) {
    $obj->calculateFieldsForDisplay();
  }
  $nobr=false;
  if (!$obj->id) {
    $canUpdate=(securityGetAccessRightYesNo('menu'.$classObj, 'create', $obj)=='YES');
  } else {
    $canUpdate=(securityGetAccessRightYesNo('menu'.$classObj, 'update', $obj)=='YES');
  }
  if ((isset($obj->locked) and $obj->locked and $classObj!='User') or isset($obj->_readOnly)) {
    $canUpdate=false;
  }
  $obj->setAllDefaultValues();
  
  // field array split by ',' and value to corresponding to field array position
  $paramField=RequestHandler::getValue('paramField');
  $paramVal=RequestHandler::getValue('paramVal');
  if($paramField and $paramVal){
    $field = explode(',', $paramField);
    $val = explode(',', $paramVal);
    foreach ($field as $key=>$fld){
      $obj->$fld=$val[$key];
    }
  }
  $arrayRequired=$obj->getExtraRequiredFields(($objType)?$objType->id:null); // will define extra required fields, depending on status, planning mode...
  $extraHiddenFields=$obj->getExtraHiddenFields(($objType)?$objType->id:null);
  $extraReadonlyFields=$obj->getExtraReadonlyFields(($objType)?$objType->id:null);
  
  // BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
  //if ((isNotificationSystemActiv() and isNotifiable($classObj)) {
  if ((property_exists($classObj, "_sec_Notification") or property_exists($classObj, "_Notification")) and isNotificationSystemActiv() and isNotifiable($classObj)) {
    $arrayClass=getUserVisibleObjectClassWithFieldDateType();
    if (in_array($classObj, $arrayClass)) {
      $arrayFields=getObjectClassFieldsList($classObj, true, true);
      if (!in_array("_sec_Notification", $arrayFields)) {
        $obj->{"_sec_Notification"}=null;
      }
      if (!in_array("_Notification", $arrayFields)) {
        $obj->{"_Notification"}=null;
      }
    }
  }  
  // END - ADD BY TABARY - NOTIFICATION SYSTEM
  if( $layout=='tab' and $included==false and !$print){
    echo '<div id ="tabDetailContainer" dojoType="dijit.layout.TabContainer">';
  }
  $validatedWorkReadOnly=false;
  $validatedCostReadOnly=false;

  // Check for unset
  $varSet=array();
  foreach ($obj as $col=>$val) {
    $varSet[$col]='set';
  }
  $lineStarted=false;
  // Loop on each property of the object
  foreach ($obj->getFieldsList() as $col) {
    if (! property_exists($obj, $col)) continue;
    if (! isset($varSet[$col])) continue;
    $val=(property_exists($obj, $col) and isset($obj->$col))?$obj->$col:null;
    if ($detailWidth) {
      $colWidth=round((intval($displayWidth))/$nbCol); // 3 columns should be displayable
      $maxWidth=$colWidth-$labelWidth; // subtract label width
      if (isNewGui()) $maxWidth-=13;
      if ($maxWidth>=$mediumWidth) {
        $largeWidth=$maxWidth;
      } else {
        $largeWidth=$mediumWidth;
      }
    }
    $currency=$obj->getCurrency($col);
    $currencyPosition=$obj->getCurrencyPosition($col);
    if (isNewGui()) $largeWidth-=25;
    // BEGIN - ADD BY TABARY - TOOLTIP
    $toolTip=$obj->getFieldTooltip($col);
    // END - ADD BY TABARY - TOOLTIP
    
    //PBER #7023
    if(pq_substr($col,0,11)=="_separator_"){
      $hide=true;
      $found=false;
      foreach ($obj->getFieldsList() as $tmpCol) {
        if ($tmpCol==$col) {
          $found=true;
          continue;
        }
        if (! $found) continue;
        if (pq_substr($tmpCol,0,11)=="_separator_" or pq_substr($tmpCol,0,5)=="_sec_") {
          break;
        }
        if (pq_substr($tmpCol,0,1)=="_") continue;
        if ( ! $obj->isAttributeSetTofield($tmpCol, 'hidden') and ! in_array($tmpCol, $extraHiddenFields) ) {
          $hide=false;
          break;
        }
      }
      if ($hide) continue;
    }//end
    
    $style=$obj->getDisplayStyling($col);
    $labelStyle=$style["caption"];
    $fieldStyle=$style["field"];
    $hide=false;
    $invisible=false;
    $notReadonlyClass=" generalColClassNotReadonly ";
    $notRequiredClass=" generalColClassNotRequired ";
    $nobr_before=$nobr;
    $nobr=false;
    if ($included and ($col=='id' or $col=='refId' or $col=='refType' or $col=='refName')) {
      $hide=true;
    }
    if ($col=='idOrganization'  and ! Module::isModuleActive('moduleOrganization')) {
      $hide=true;
    }
    // For PDF Export : hide line if section is hidden
    $hiddenSection=false;
    if ($section) {
      if ($parentHidden or $obj->isAttributeSetToField('_sec_'.$section, 'hidden') or in_array('_sec_'.$section, $extraHiddenFields)) {
        //$hide=true;
        $hiddenSection=true;
      }
    }
    if (pq_substr($col,0,9)=='_lib_help') { // Hide if corresponding field is hidden
      $helper=array(lcfirst(pq_substr($col,9)), 'is'.pq_substr($col,9));
      $helperField=null;
      
      foreach( $helper as $helpTest) {
        if (property_exists($obj, $helpTest)) {
          $helperField=$helpTest;
          break;
        }
      }
      if ($helperField and $obj->isAttributeSetToField($helperField, 'hidden') or in_array($helperField, $extraHiddenFields)) {
        $hide=true;
      }
      if($helperField and $obj->isAttributeSetToField($helperField, 'invisible')){
        $invisible=true;
      }
    }
    if (pq_substr($col, 0, 7)=='_label_') {
      $attFld=pq_substr($col, 7);
      if ($attFld=='expected') $attFld='expectedProgress';
      else if ($attFld=='planning') $attFld='id'.pq_str_replace('PlanningElement', '', get_class($obj)).'PlanningMode';
      if (property_exists(get_class($obj), $attFld) and $obj->isAttributeSetToField($attFld, "hidden")) {
        $hide=true;
      } else if (in_array($attFld, $extraHiddenFields)) {
        $hide=true;
      }
    }
    if (pq_substr($col, 0, 5)=='_lib_') {
      $attFld=pq_substr($col, 5);
      if (pq_substr($attFld, 0, 3)=='col' and pq_substr($attFld, 3, 1)==pq_strtoupper(pq_substr($attFld, 3, 1))) $attFld=lcfirst(pq_substr($attFld, 3));
      if (pq_substr($attFld, 0, 3)=='col' and pq_ucfirst(pq_substr($attFld, 3, 1))==pq_substr($attFld, 3, 1)) $attFld=pq_substr($attFld, 3);
      if (property_exists(get_class($obj), $attFld) and $obj->isAttributeSetToField($attFld, "hidden")) {
        $hide=true;
      } else if (in_array($attFld, $extraHiddenFields)) {
        $hide=true;
      }
    }
    // If field is _tab_x_y, start a table presentation with x columns and y lines
    // the field _tab_x_y must be an array containing x + y values :
    // - the x column headers
    // - the y line headers
    
    // gautier #3251
    if (pq_substr($col, 0, 4)=='_tab') {
      // BEGIN - ADD BY TABARY - FORCE HEADER TAB VISIBLE
      $forceHeader=$obj->isAttributeSetToField($col, "forceHeader");
      // END - ADD BY TABARY - FORCE HEADER TAB VISIBLE
      $decomp=pq_explode("_", $col);
      $internalTableCols=$decomp[2];
      $internalTableRows=$decomp[3];
      $allowWrap=false;
      if (count($decomp)>4) {
        if (pq_strtolower($decomp[4])=='allowwrap') $allowWrap=true;
      }
      // ADD qCazelles - dateComposition
      // if (count($val) == 8 and $val[4]=='startDate' and $val[5]=='deliveryDate' and Parameter::getGlobalParameter('displayMilestonesStartDelivery') != 'YES') $internalTableRows -= 2;
      // END ADD qCazelles - dateComposition
      $internalTableSpecial='';
      if (count($decomp)>4) {
        $internalTableSpecial=$decomp[4];
      }
      // Determine how many items to be displayed per line and column
      $arrTab=array('rows'=>array(), 'cols'=>array());
      $arrStart=-99;
      $arrStop=$internalTableCols*$internalTableRows;
      for ($ii=0; $ii<$internalTableCols; $ii++) {
        $arrTab['cols'][$ii]=0;
      }
      for ($ii=0; $ii<$internalTableRows; $ii++) {
        $arrTab['rows'][$ii]=0;
      }
      foreach ($obj->getFieldsList() as $arrCol) {
        if ($arrCol==$col) {
          $arrStart=-1;
          continue;
        }
        if ($arrStart<-1) continue;
        $arrStart++;
        if ($arrStart>=$arrStop) break;
        if (pq_substr($arrCol, 0, 6)=='_void_' or (pq_substr($arrCol, 0, 7)=='_label_' and $outMode!='pdf') or pq_substr($arrCol, 0, 8)=='_button_') {
          continue;
        }
        if ($hiddenSection) continue;
        // BEGIN - CHANGE BY TABARY - FORCE HEADER TAB VISIBLE
        // $spinnerAttr = $obj->getSpinnerAttributes($arrCol);
        // $showLabelInTab = (pq_strpos($spinnerAttr,'showLabelInTab')===false?false:true);
        // if ($obj->isAttributeSetToField($arrCol, "hidden") or $parentHidden) continue;
        if (($obj->isAttributeSetToField($arrCol, "hidden") and !$forceHeader and ! ($obj->hasCurrency() and $obj->isLocal($arrCol))) or $parentHidden) continue;
        // END - CHANGE BY TABARY - FORCE HEADER TAB VISIBLE
        // if ($obj->isAttributeSetToField($arrCol, "hidden") or $parentHidden) continue;
        // END - ADD BY TABARY - IF ISSPINNER AND HIDE
        if (in_array($arrCol, $extraHiddenFields)) continue;
        $indCol=$arrStart%$internalTableCols;
        $indLin=floor($arrStart/$internalTableCols);
        $arrTab['rows'][$indLin]++;
        $arrTab['cols'][$indCol]++;
      }
      //
      $internalTable=$internalTableCols*$internalTableRows;
      // ADD qCazelles - dateComposition
      // if (count($val) == 8 and $val[4]=='startDate' and $val[5]=='deliveryDate' and Parameter::getGlobalParameter('displayMilestonesStartDelivery') != 'YES') {
      // unset($val[4]);
      // unset($val[5]);
      // }
      // END ADD qCazelles - dateComposition
      $internalTableRowsCaptions=($val and is_array($val))?array_slice($val, $internalTableCols):'';
      $internalTableCurrentRow=0;
      $colWidth=($detailWidth)/$nbCol;
      // #3538 - This part is no use any more since genericity of display of headers
      // if (SqlElement::is_subclass_of($obj, 'PlanningElement') and $internalTableRows>3) {
      // for ($i=0; $i<$internalTableRows; $i++) {
      // $testRowCaption=pq_strtolower($internalTableRowsCaptions[$i]);
      // if ($workVisibility=='NO' and SqlElement::isWork($testRowCaption)) {
      // $internalTableRowsCaptions[$i]='';
      // }
      // if ($costVisibility=='NO' and (pq_substr($testRowCaption, -4)=='cost' or pq_substr($testRowCaption, -7)=='expense')) {
      // $internalTableRowsCaptions[$i]='';
      // }
      // if ($costVisibility!='ALL' and pq_substr($testRowCaption, 0, 13)=='reserveamount') {
      // $internalTableRowsCaptions[$i]='';
      // }
      // }
      // if ($workVisibility!='ALL' and $costVisibility!='ALL') {
      // $val[2]='';
      // $val[5]='';
      // }
      // }
      $internalTablePrintCompact=false;
      $internalTablePrintCompactStyle=($internalTablePrintCompact)?' style="width:auto;margin-left:auto;margin-right:auto;"':'';
      echo '</table><table id="'.$col.'" class="detail internalTable"'.$internalTablePrintCompactStyle.'>';
      echo '<tr class="detail">';
      $lineStarted=true;
      echo '<td class="detail"></td>'; // Empty label, to have column header in front of columns
                                       // $internalTableBorderTitle=($print)?'border:1px solid #A0A0A0;':'';
      $internalTableBorderTitle=($print)?'padding-top:5px;text-decoration: underline;padding-bottom:2px;':'';
      // Optimize width column
      if ($internalTableCols<=4) {
        $minWidth=300/$internalTableCols;
      } else {
        $minWidth=75;
      }
      if (isNewGui()) $minWidth=25;
//       if ($print) {
//         $minWidth*=1.5;
//       }
      for ($i=0; $i<$internalTableCols; $i++) { // draw table headers
                                                // echo '<td class="detail" style="min-width:75px;' . $internalTableBorderTitle . '">';
        $internalTableColumnWidth=(isNewGui())?(($internalTablePrintCompact)?'45':'200'):'';
        echo '<td class="detail" style="'.(($internalTableColumnWidth)?'width:'.$internalTableColumnWidth.'px;':'').$internalTableBorderTitle.'">';
        if ($arrTab['cols'][$i]==0) {
          echo '<div class=""></div>';
          // CHANGE BY Marc TABARY - 2017-03-31 - COLEMPTY
        } else if (isset($val[$i]) and $val[$i]!='empty') {
          // old
          // } else if ($val [$i]) {
          // END CHANGE BY Marc TABARY - 2017-03-31 - COLEMPTY
          $extraLocalClass=($obj->isLocal($val[$i]))?' localLabelClass':'';
          echo '<div class="tabLabel '.$extraLocalClass.'" style="min-width:'.$minWidth.'px;text-align:'.(($print)?'center':'left').';'.(($allowWrap)?'':'white-space:nowrap;').'">'.htmlEncode($obj->getColCaption($val[$i])).'</div>';
        } else {
          echo '<div class="tabLabel" style="text-align:left;white-space:nowrap;"></div>';
        }
        if ($i<$internalTableCols-1) {
          echo '</td>';
        }
      }
      // echo '</tr>'; NOT TO DO HERE - WILL BE DONE AFTER
    } else if (pq_substr($col, 0, 5)=='_sec_' and (!$comboDetail or $col!='_sec_Link')) { // if field is _section, draw a new section bar column
      if ($col=='_sec_language' and Parameter::getGlobalParameter('displayLanguage')!='YES') continue;
      if ($col=='_sec_context' and Parameter::getGlobalParameter('displayContext')!='YES') continue;
      if ($col=='_sec_ProductBusinessFeatures' and Parameter::getGlobalParameter('displayBusinessFeature')!='YES') continue;
      if (($col=='_sec_TicketsClient' or $col=='_sec_TicketsContact') and Parameter::getGlobalParameter('manageTicketCustomer')!='YES') continue;
      if ($col=='_sec_ProductVersionCompatibility' and Parameter::getGlobalParameter('versionCompatibility')!='YES') continue;
      // if ($col=='_sec_delivery' and Parameter::getGlobalParameter('productVersionOnDelivery') != 'YES') continue;
      if (($print||$outMode=='pdf')&&pq_substr($col, 0, 5)==="_sec_"&&$obj->isAttributeSetToField($col, 'noPrint')) { continue; }
      $prevSection=$section;
      $currentCol+=1;
      if (pq_strlen($col)>8) {
        $section=pq_substr($col, 5);
      } else {
        $section='';
      }
      // Determine number of items to be displayed in Header
      // ADD BY Marc TABARY - 2017-02-22 - OBJECTS LINKED BY ID TO MAIN OBJECT
      if (\pq_strpos($section, 'sOfObject')>0) {
        // It's a section that draws the object linked by be to the 'main object'
        // naming rule to draw list of objects linked by id ('foreign key') to the object
        // _sec_ : For section (it's generic to the FrameWork
        // _xxxs : xxx the object linked by id - Don't forget the 's' at the end
        // OfObject : indicate, it's a section for linked by id object
        $sectionField='_'.pq_substr($section, 0, pq_strpos($section, 'sOfObject'));
      } else {
        // END ADD BY Marc TABARY - 2017-02-22 - OBJECTS LINKED BY ID TO MAIN OBJECT
        $sectionField='_'.$section;
      }
      if ($section=='Attendees') $sectionField="_Assignment";
      $sectionFieldDep='_Dependency_'.pq_ucfirst($section);
      $sectionFieldDoc='_Document'.$section;
      $sectionFieldVP='_VersionProject';
      if ($section=='trigger') {
        $sectionFieldDep='_Dependency_Predecessor';
      }
      if (pq_substr($section, 0, 14)=="Versionproject") {
        $sectionField='_VersionProject';
      }
      $cpt=null;
      if (property_exists($obj, $sectionField) && isset($obj->$sectionField) && is_array($obj->$sectionField)) {
        $cptt = 0;
        if($sectionField == "_Link"){
          $cptt = 0;
          $findme   = '_Link_';
          foreach ($obj as $idVal=>$listVal){
            $finded = strstr($idVal, $findme);
            if($finded){
              if(is_array($listVal)){
                $cptt+= count($listVal);
              }
            }
          }
        }
        $cpt=count($obj->$sectionField)-$cptt;
      } else if (property_exists($obj, $sectionFieldDep)&&is_array($obj->$sectionFieldDep)) {
        $cpt=count($obj->$sectionFieldDep);
      } else if (property_exists($obj, $sectionFieldDoc)&&is_array($obj->$sectionFieldDoc)) {
        $cpt=count($obj->$sectionFieldDoc);
      } else if (pq_substr($section, 0, 14)=='Versionproject' and property_exists($obj, $sectionFieldVP) and is_array($obj->$sectionFieldVP)) {
        $cpt=count($obj->$sectionFieldVP);
      } else if ($section=='Affectations') {
        $crit=array('idProject=>'=>'0', 'idResource'=>'0');
        if ($classObj=='Project') {
          $crit=array('idProject'=>$obj->id);
        } else {
          $crit=array('idResource'=>$obj->id, 'idle'=>'0');
        }
        $aff=new Affectation();
        $cpt=$aff->countSqlElementsFromCriteria($crit);
      }else if($section == 'ExpenseBudgetDetail'){
        $expense = new ProjectExpense();
        $cpt= $expense->countSqlElementsFromCriteria(array("idBudgetItem"=>$obj->id));
      } else if ($section=='AffectationsResourceTeam') {
        $crit=array('idResourceTeam'=>$obj->id);
        $aff=new ResourceTeamAffectation();
        $cpt=$aff->countSqlElementsFromCriteria($crit);
      } else if ($section=='resourceCapacity') {
        $crit=array('idResource'=>$obj->id);
        $resCap=new ResourceCapacity();
        $cpt=$resCap->countSqlElementsFromCriteria($crit);
      } else if ($section=='resourceSurbooking') {
        $crit=array('idResource'=>$obj->id);
        $resSur=new ResourceSurbooking();
        $cpt=$resSur->countSqlElementsFromCriteria($crit);
      } else if ($section=='affectationResourceTeamResource') {
        $crit=array('idResource'=>$obj->id);
        $aff=new ResourceTeamAffectation();
        $cpt=$aff->countSqlElementsFromCriteria($crit);
      } else if ($section=='resourceIncompatible') {
        $crit=array('idResource'=>$obj->id);
        $resInc=new ResourceIncompatible();
        $cpt=$resInc->countSqlElementsFromCriteria($crit);
      } else if ($section=='resourceSupport') {
        $crit=array('idResource'=>$obj->id);
        $resSup=new ResourceSupport();
        $cpt=$resSup->countSqlElementsFromCriteria($crit);
      } else if ($section=='Asset') {
        $crit=array('idAffectable'=>$obj->id);
        $asset=new Asset();
        $cpt=$asset->countSqlElementsFromCriteria($crit);
      } else if ($section=='AssetModel') {
        $crit=array('idModel'=>$obj->id);
        $asset=new Asset();
        $cpt=$asset->countSqlElementsFromCriteria($crit);
      } else if ($section=='Modelbrand') {
        $crit=array('idBrand'=>$obj->id);
        $asset=new Model();
        $cpt=$asset->countSqlElementsFromCriteria($crit);
      } else if ($section=='situation') {
        $crit=array('refId'=>$obj->id, 'refType'=>get_class($obj));
        $situation=new Situation();
        $cpt=$situation->countSqlElementsFromCriteria($crit);
      } else if ($section=='languageSkill'){
          $localizationTranslatorLanguage = new LocalizationTranslatorLanguage();
          $cpt = $localizationTranslatorLanguage->countSqlElementsFromCriteria(array("idTranslator"=>$obj->id));
      } else if ($section =='linkedLocalizationItems'){
          $localizationItem = new LocalizationItem();
          $cpt = $localizationItem->countSqlElementsFromCriteria(array("idLocalizationRequest"=> $obj->id));
      }else if ($section=='HierarchicOrganizationProjects'){
        $orgList = $obj->getRecursiveSubOrganizationInString(false, true);
        $showIdle = (Parameter::getUserParameter('showClosedOrgaProject'))?'':' and idle=0';
        $whereClose = 'idOrganization in '.$orgList.$showIdle;
        $prj = new Project();
        $cpt = $prj->countSqlElementsFromCriteria(null,$whereClose);
      } else if ($section=='ResourceSkill') {
        $crit=array('idResource'=>$obj->id);
        $resSkill=new ResourceSkill();
        $cpt=$resSkill->countSqlElementsFromCriteria($crit);
      }else {
        // ADD BY Marc TABARY - 2017-03-16 - FORCE SECTION ITEM'S COUNT
        // Want a item's count on section header
        // => In the section's declaration in the class : _sec_XXXXXXXX='itemsCount=method to call to count item'
        // Ex : Fields declaration in model class
        // $_sec_MySection='itemCount=getItemCount'
        // Sample : See OrganizationMain.php :
        // - Attributs declaration
        if (pq_strpos($val, 'itemsCount=')!==false) {
          $cpt=null;
          $methodToCall=pq_substr($val, pq_strpos($val, '=')+1);
          if (method_exists($obj, $methodToCall)) {
            $cpt=count($obj->$methodToCall());
          }
        }
        // END ADD BY Marc TABARY - 2017-03-16 - FORCE SECTION ITEM'S COUNT
      }
      // Determine colSpan
      $colSpan=null;
      $colSpanSection='_'.lcfirst($section).'_colSpan';
      if (property_exists($obj, $colSpanSection)) {
        $colSpan=$obj->$colSpanSection;
      }
      $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj, $colSpan);
      if ($col=='_sec_void') {
        if ($prevSection) {
          echo '</table>';
          if (!$print) {
            echo '</div>';
          } else {
            echo '<br/>';
          }
        }
        if (!$print) {
          echo '<div style="float:left;width:'.$widthPct.'" ><table><tr><td>&nbsp;</td></tr>';
        } else {
          echo '<table>';
        }
      } else {
        startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, $cpt, $included, $obj);
      }
      // ADD qCazelles - Manage ticket at customer level - Ticket #87
    } else if (pq_substr($col, 0, 10)=='_separator') {    //Doris #3687
      if ($parentHidden) continue;
      $decomp=pq_explode("_", $col);
      $name = i18n($decomp[2]);
      if($decomp[2] == 'sectionCostWork'){
        $cptCost=0;
        $cptWork=0;
        foreach ($extraHiddenFields as $valHidden){
          if(pq_substr($valHidden, -4) == 'Work'){
            $cptWork++;
          }
          if(pq_substr($valHidden, -4) == 'Cost'){
            $cptCost++;
          }
        }
        $countCost=true;
        $countWork=true;
        if($cptCost == 5)$countCost=false;
        if($cptWork == 5)$countWork=false;
        if(!$countWork and !$countCost){
          continue;
        }
        if($countWork and !$countCost){
          $name = i18n('sectionWork');
        }
        if(!$countWork and $countCost){
          $name = i18n('sectionCost');
        }
      }
      $margin = "";
      if(1 or isset($decomp[3])){
        $margin = "margin-top:5px;";
      }
      echo '<tr><td colspan="2" style="font-size:3px;">&nbsp;</td></tr>'; 
      echo '<tr><td colspan="2">';
      if (!$widthPct) $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj, "2");
      echo '  <table style="width:'.$widthPct.'" class="separatorSection"><tr><td class="assignHeader" id="'.$col.'" style="width:100%;height:14px; padding: 3px; margin-bottom:5px;'.$margin.';vertical-align:middle; border:'.((isModernUi())?'0':'1').'px solid grey;">'.$name.'</td></tr></table>';
      echo '</td></tr>';
    } else if ($col=='_spe_tickets' and !$obj->isAttributeSetTofield($col, 'hidden')) {
      drawTicketsList($obj);
      // END ADD qCazelles - Manage ticket at customer level - Ticket #87
      // Add mOlives - ticket 215 - 09/05/2018
    } else if ($col == '_spe_subscriptions') {
      $limitToActive = true;
      if (isset($_REQUEST['showClosedSub']) and $_REQUEST['showClosedSub'] == true) $limitToActive = false;
      drawSubscriptionsList($obj, false, $limitToActive);
    } else if ($col=='_spe_activity' and !$obj->isAttributeSetTofield($col, 'hidden') and !in_array($col, $extraHiddenFields)) {
      drawActivityList($obj);
      // End mOlives - ticket 215 - 09/05/2018
    } else if (pq_substr($col, 0, 5)=='_spe_') { // if field is _spe_xxxx, draw the specific item xxx
      $item=pq_substr($col, 5);
      $projectRaciSpecific=(get_class($obj)=='Project' and $item=='raciMatrix');
      $separateSpecific=(!$internalTable and $projectRaciSpecific);
      if ($internalTable) {
        if ($internalTable%$internalTableCols==0) {
          echo '</td><td>'.$cr;
          if ($projectRaciSpecific) echo '<div id="Project_RaciMatrix" dojoType="dijit.layout.ContentPane" style="width:100%;overflow:auto;">';
          $internalTableCurrentRow++;
        } else {
          echo '</td><td>';
          if ($projectRaciSpecific) echo '<div id="Project_RaciMatrix" dojoType="dijit.layout.ContentPane" style="width:100%;overflow:auto;">';
        }
      } else if ($separateSpecific) {
        echo '</table><div id="Project_RaciMatrix" dojoType="dijit.layout.ContentPane" style="width:100%;overflow:auto;">';
      } else {
        echo '<tr><td colspan=2>';
      }
      // CHANGE BY Marc TABARY - 2017-03-08 - FORCE DRAWING A SPECIFIC ITEM
      if ((!$hide and !$parentHidden and !$obj->isAttributeSetToField($col, 'hidden') and !in_array($col, $extraHiddenFields)) or $obj->isAttributeSetToField($col, 'drawforce')==true) {
        echo $obj->drawSpecificItem($item, ($included?$parentReadOnly:$readOnly)); // the method must be implemented in the corresponidng class
      }
      // Old
      // if (!$hide and !$obj->isAttributeSetToField($col,'hidden')) {echo $obj->drawSpecificItem($item);} // the method must be implemented in the corresponidng class
      // END CHANGE BY Marc TABARY - 2017-03-08 - FORCE DRAWING A SPECIFIC ITEM
      if ($internalTable) {
        if ($projectRaciSpecific) echo '</div>';
        // echo '<td>';
      } else if ($separateSpecific) {
        echo '</div><table class="detail" style="width:'.$widthPct.';">';
      } else {
        echo '</td></tr>';
      }
    } else if (pq_substr($col, 0, 6)=='_calc_') { // if field is _calc_xxxx, draw calculated item
      $item=pq_substr($col, 6);
      echo $obj->drawCalculatedItem($item); // the method must be implemented in the corresponidng class
      if (isNewGui()) echo "&nbsp;&nbsp;";
    } else if (pq_substr($col, 0, 5)=='_lib_') { // if field is just a caption
      $item=pq_substr($col, 5);
      if (pq_strpos($obj->getFieldAttributes($col), 'nobr')!==false and $obj->getFieldAttributes($col)!='hidden' and !$hide and ! in_array($col, $extraHiddenFields)) {
        $nobr=true;
      }
      if ($obj->getFieldAttributes($col)!='hidden' and !$invisible and !$hide ) {
        if ($nobr) echo '&nbsp;';
        echo '<span id="'.$col.'" class="tabLabel" style="font-weight:normal;">'.i18n($item).'</span>';
        echo '&nbsp;';
      }else if ($invisible and !$hide ){
        if ($nobr) echo '&nbsp;';
        echo '<span id="'.$col.'" class="tabLabel" style="font-weight:normal;display:none;">'.i18n($item).'</span>';
        echo '&nbsp;';
      }
      //if (!$nobr and ((!$hide and !$invisible) or !$print)) { /// PBER #9517  
      //if (! ($nobr or ( ($hide or $invisible) and $print) ) ) {
      if (! $nobr and $lineStarted){
        echo "</td></tr>";
      }
    } else if (pq_substr($col, 0, 5)=='_Link' and !$comboDetail) { // Display links to other objects
      $linkClass=null;
      if (pq_strlen($col)>5) {
        $linkClass=pq_substr($col, 6);
      }
      drawLinksFromObject($val, $obj, $linkClass);
    } else if ($col=='_productComposition' and !$obj->isAttributeSetToField($col, "hidden")) { // Display Composition of Product (structure)
      drawStructureFromObject($obj, false, 'composition', 'Product');
      // ADD qCazelles - Lang-Context
    } else if ($col=='_productLanguage' and Parameter::getGlobalParameter('displayLanguage')=='YES') {
      drawLanguageSection($obj);
    } else if ($col=='_languageSkill') {
        drawLanguageSection($obj);
    } else if ($col =='_localizationItem'){
        drawLocalizationItemSection($obj);
    } else if ($col=='_productContext' and Parameter::getGlobalParameter('displayContext')=='YES') {
      drawContextSection($obj);
      // END ADD qCazelles - Lang-Context
      // ADD by qCazelles - Business features
    } else if ($col=='_productBusinessFeatures' and Parameter::getGlobalParameter('displayBusinessFeature')=='YES') {
      drawBusinessFeatures($obj);
      // END ADD
      // ADD qCazelles - Version compatibility
    } else if ($col=='_productVersionCompatibility' and Parameter::getGlobalParameter('versionCompatibility')=='YES') {
      drawVersionCompatibility($obj);
      // END ADD qCazelles - Version compatibility
      // ADD qCazelles
    } else if ($col=='_versionDelivery' and Parameter::getGlobalParameter('productVersionOnDelivery')=='YES') {
      drawDeliverysFromObject($obj);
      // END ADD qCazelles
    } else if ($col=='_componentComposition' and !$obj->isAttributeSetToField($col, "hidden")) { // Display Composition of component (structure)
      drawStructureFromObject($obj, false, 'composition', 'Component');
    } else if ($col=='_componentStructure' and !$obj->isAttributeSetToField($col, "hidden")) { // Display Structure of component (structure)
      drawStructureFromObject($obj, false, 'structure', 'Component');
    } else if ($col=='_productVersionComposition' and !$obj->isAttributeSetToField($col, "hidden")) { // Display ProductVersionStructure (structure)
      drawVersionStructureFromObject($obj, false, 'composition', 'ProductVersion');
    } else if ($col=='_componentVersionStructure' and !$obj->isAttributeSetToField($col, "hidden")) { // Display ProductVersionStructure (structure)
      drawVersionStructureFromObject($obj, false, 'structure', 'ComponentVersion');
      //Gautier #4404
    } else if ($col=='_componentVersionStructureAsset' and !$obj->isAttributeSetToField($col, "hidden")) { // Display ProductVersionStructure (structure)
      drawVersionStructureFromObjectAsset($obj, false, 'structure', 'ComponentVersion');
    } else if ($col=='_assetComposition' and !$obj->isAttributeSetToField($col, "hidden")) { // Display ProductVersionStructure (structure)
      drawAssetComposition($obj);
    } else if ($col=='_componentVersionComposition' and !$obj->isAttributeSetToField($col, "hidden")) { // Display ProductVersionStructure (structure)
      drawVersionStructureFromObject($obj, false, 'composition', 'ComponentVersion');
    } else if (pq_substr($col, 0, 11)=='_Assignment') { // Display Assignments
      drawAssignmentsFromObject($val, $obj);
    } else if (pq_substr($col, 0, 11)=='_Approver') { // Display Assignments
      drawApproverFromObject($val, $obj);
    } else if (pq_substr($col, 0, 15)=='_VersionProject') { // Display Version Project
      drawVersionProjectsFromObject($val, $obj);
    } else if (pq_substr($col, 0, 15)=='_ProductProject') { // Display Version Project
      drawProductProjectsFromObject($val, $obj);
    } else if (pq_substr($col, 0, 11)=='_Dependency') { // Display Dependencies
      $depType=(pq_strlen($col)>11)?pq_substr($col, 12):"";
      drawDependenciesFromObject($val, $obj, $depType);
    } else if ($col=='_ResourceCost') { // Display ResourceCost
      drawResourceCostFromObject($val, $obj, false);
    } else if ($col=='_BillLineTerm') {
      if (get_class($obj)=='ProviderBill') {
        $providerTerm=new ProviderTerm();
        $listProvTerm=$providerTerm->getSqlElementsFromCriteria(array("idProviderBill"=>$obj->id));
        $lines=array();
        $nbLines=0;
        foreach ($listProvTerm as $term) {
          $providerTerm=new ProviderTerm($term->id);
          $nbLines+=count($providerTerm->_BillLineTerm);
          array_push($lines, $providerTerm->_BillLineTerm);
        }
        if ($obj->id and $nbLines>0) {
          $prevSection=$section;
          $section="BillLineTerm";
          $colSpanSection='_'.lcfirst($section).'_colSpan';
          if (property_exists($obj, $colSpanSection)) {
            $colSpan=$obj->$colSpanSection;
          }
          $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj, "2");         
          startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, count($val), $included, $obj);
          drawBillLinesProviderTerms($obj, false);
        }
      } else {
        $prevSection=$section;
        $section="BillLineTerm";
        $colSpanSection='_'.lcfirst($section).'_colSpan';
        if (property_exists($obj, $colSpanSection)) {
          $colSpan=$obj->$colSpanSection;
        }
        $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj, "2");
        startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, count($val), $included, $obj);
        drawBillLinesProviderTerms($obj, false);
      }
    } else if ($col=='_DocumentVersion') { // Display
      drawDocumentVersionFromObject($val, $obj, false);
    } else if ($col=='_ExpenseDetail') { // Display ExpenseDetail
      if ($obj->getFieldAttributes($col)!='hidden') {
        drawExpenseDetailFromObject($val, $obj, false);
      }
    } else if (pq_substr($col, 0, 12)=='_TestCaseRun') { // Display TestCaseRun
      drawTestCaseRunFromObject($val, $obj);
    } else if (pq_substr($col, 0, 13)=='_ProviderTerm') {
      drawProviderTermFromProviderBill($val, $obj);
    } else if (pq_substr($col, 0, 11)=='_Attachment' and !$comboDetail) {
      if (!isset($isAttachmentEnabled)) {
        $isAttachmentEnabled=true; // allow attachment
        if (!Parameter::getGlobalParameter('paramAttachmentDirectory') or !Parameter::getGlobalParameter('paramAttachmentMaxSize')) {
          $isAttachmentEnabled=false;
        }
      }
      if ($isAttachmentEnabled and !$comboDetail) {
        if ($obj->isAttributeSetToField('_Attachment', 'hidden') or in_array('_Attachment', $extraHiddenFields)) continue;
        $prevSection=$section;
        $section="Attachment";
        $ress=new Resource(getCurrentUserId());
        $cpt=0;
        foreach ($obj->_Attachment as $cptObjTmp) {
          if ($cptObjTmp->isProfilePic == 0 and ($user->id==$cptObjTmp->idUser or $cptObjTmp->idPrivacy==1 or ($cptObjTmp->idPrivacy==2 and $ress->idTeam==$cptObjTmp->idTeam))) {
            $cpt++;
          }
        }
        startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, $cpt, $included, $obj);
        drawAttachmentsFromObject($obj, false);
      }
      // ADD qCazelles - Lang
    } else if ($col=='idLanguage' and (strpos(get_class($obj),'Component')!==false or strpos(get_class($obj),'Component')!==false) and Parameter::getGlobalParameter('displayLanguage')!='YES') {
      continue;
      // END ADD qCazelles - Lang
    } else if (pq_substr($col, 0, 5)=='_Note' and !$comboDetail) {
      if ($obj->isAttributeSetToField('_Note', 'hidden') or in_array('_Note', $extraHiddenFields)) continue;
      $prevSection=$section;
      $section="Note";
      $ress=new Resource(getCurrentUserId());
      $cpt=0;
      foreach ($obj->_Note as $cptObjTmp) {
        if ($user->id==$cptObjTmp->idUser or $cptObjTmp->idPrivacy==1 or ($cptObjTmp->idPrivacy==2 and $ress->idTeam==$cptObjTmp->idTeam)) {
          $cpt++;
        }
      }
      startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, $cpt, $included, $obj);
      drawNotesFromObject($obj, false);
    } else if ($col=='_BillLine') {
      if (get_class($obj)=='ProviderBill') {
        $providerTerm=new ProviderTerm();
        $listProvTerm=$providerTerm->getSqlElementsFromCriteria(array("idProviderBill"=>$obj->id));
        $lines=array();
        foreach ($listProvTerm as $term) {
          $providerTerm=new ProviderTerm($term->id);
          array_push($lines, $providerTerm->_BillLineTerm);
        }
        if (1 or !$lines) { // PBER : Detail lines should always be visible
          $prevSection=$section;
          $section="BillLine";
          $colSpanSection='_'.lcfirst($section).'_colSpan';
          if (property_exists($obj, $colSpanSection)) {
            $colSpan=$obj->$colSpanSection;
          }
          $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj, "2");
          startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, count($val), $included, $obj);
          drawBillLinesFromObject($obj, false);
        }
      } else {
        $prevSection=$section;
        $section="BillLine";
        $colSpanSection='_'.lcfirst($section).'_colSpan';
        if (property_exists($obj, $colSpanSection)) {
          $colSpan=$obj->$colSpanSection;
        }
        $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj, "2");
        startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, count($val), $included, $obj);
        drawBillLinesFromObject($obj, false);
      }
      // BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
    } else if ($col==='_Notification') {
      drawNotificationsLinkedToObject($obj);
      // END - ADD BY TABARY - NOTIFICATION SYSTEM
      
      // ADD BY Marc TABARY - 2017-02-23 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT
    }else if($col==='_SubTask' and $obj->getFieldAttributes($col)!='hidden' ){ //florent ticket #5139
      $rightUpdate=securityGetAccessRightYesNo('menu'.$classObj,'update',$obj);
      $rightRead=securityGetAccessRightYesNo('menu'.$classObj,'read',$obj);
    	SubTask::drawSubtasksForObject($obj,$classObj,$obj->id,$rightUpdate,$rightRead);
    }else if($col==='_WorkTokenMarkup' and $obj->getFieldAttributes($col)!='hidden' ){ //florent ticket #5139
      WorkTokenMarkup::drawWorkTokenMarkup($obj, $print);
    }else if($col==='_WorkTokenClientContract' and $obj->getFieldAttributes($col)!='hidden'){
      WorkTokenClientContract::drawWorkTokenClientContract($obj, $print);   
    } else if($col==='_DocumentRight' and $obj->getFieldAttributes($col)!='hidden' ){ //florent ticket #5139
        $dR=new DocumentRight();
        $classDR=get_class($dR);
        $menu=SqlElement::getSingleSqlElementFromCriteria('Menu', array('name'=>'menu'.get_class($obj)));
        $rightUpdate=securityGetAccessRightYesNo($menu->name,'update',$obj);
        $rightRead=securityGetAccessRightYesNo($menu->name,'read',$obj);
        if ( securityCheckDisplayMenu(null, $classDR) and $rightRead=="YES") {
            DocumentRight::drawDocumentRight($obj,$rightRead,$rightUpdate,$dR,$classDR);
        }
    }else if (pq_substr($col, 0, 1)=='_' and pq_strpos($section, 'sOfObject')>0 and SqlElement::class_exists(pq_substr($col, 1))) {
      drawObjectLinkedByIdToObject($obj, pq_substr($col, 1), false);
      // END ADD BY Marc TABARY - 2017-02-23 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT
    } else if (pq_substr($col, 0, 1)=='_' and pq_substr($col, 0, 6)!='_void_' and pq_substr($col, 0, 7)!='_label_' and pq_substr($col, 0, 8)!='_button_' and pq_substr($col, 0, 7)!='_byMet_') {   
      // Nothing ?
    } else {
      $attributes='';
      // ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER
      $isSpinner=($obj->getSpinnerAttributes($col)==''?false:true);
      // END ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER
      $isRequired=false;
      $readOnly=false;
      $specificStyle='';
      $specificStyleWithoutCustom='';
      if (($col=="idle" or $col=="done" or $col=="handled" or $col=="cancelled" or $col=="solved" or ($col=="paused" and get_class($obj)=='Ticket')) and $objType and property_exists($obj, 'idStatus')) {
        $lock='lock'.pq_ucfirst($col);
        if (!$obj->id or (property_exists($objType, $lock) and $objType->$lock)) {
          $attributes.=' readonly tabindex="-1"';
          $notReadonlyClass="";
          $readOnly=true;
        }
      }
      // ADD qCazelles - Ticket #53
      if (($col=="realStartDate" or $col=="isStarted") and $objType) {
        $lock='lockHandled';
        if (!$obj->id or (property_exists($objType, $lock) and $objType->$lock)) {
          $attributes.=' readonly tabindex="-1"';
          $notReadonlyClass="";
          $readOnly=true;
        }
      }
      if (($col=="realDeliveryDate" or $col=="isDelivered") and $objType) {
        $lock='lockDone';
        if (!$obj->id or (property_exists($objType, $lock) and $objType->$lock)) {
          $attributes.=' readonly tabindex="-1"';
          $notReadonlyClass="";
          $readOnly=true;
        }
      }
      if (($col=="realEisDate" or $col=="isEis") and $objType) {
        $lock='lockIntoservice';
        if (!$obj->id or (property_exists($objType, $lock) and $objType->$lock)) {
          $attributes.=' readonly tabindex="-1"';
          $notReadonlyClass="";
          $readOnly=true;
        }
      }
      if (($col=="realEndDate" or $col=="idle") and $objType and property_exists($obj, 'idStatus')) {
        $lock='lockIdle';
        if (!$obj->id or (property_exists($objType, $lock) and $objType->$lock)) {
          $attributes.=' readonly tabindex="-1"';
          $notReadonlyClass="";
          $readOnly=true;
        }
      }
      // END ADD qCazelles - Ticket #53
      if (pq_strpos($obj->getFieldAttributes($col), 'required')!==false) {
        // $attributes.=' required="true" missingMessage="' . i18n('messageMandatory', array($obj->getColCaption($col))) . '" invalidMessage="' . i18n('messageMandatory', array($obj->getColCaption($col))) . '"';
        $isRequired=true;
        $notRequiredClass="";
      }
      if (pq_array_key_exists($col, $arrayRequired)) {
        $attributes.=' required="true" missingMessage="'.i18n('messageMandatory', array($obj->getColCaption($col))).'" invalidMessage="'.i18n('messageMandatory', array(
            $obj->getColCaption($col))).'"';
        $isRequired=true;
      }
      if (pq_strpos($obj->getFieldAttributes($col), 'hidden')!==false) { // TODO : adapt so that $obj->getFieldAttributes($col), 'hidden')!==false is treated like in_array($col, $extraHiddenFields)
      //if ($obj->isAttributeSetToField($col,'hidden')) {
        if (!$print and property_exists($obj, '_dynamicHiddenFields') and in_array($col,$obj->_dynamicHiddenFields)) {
          $specificStyle.=' display:none';
        } else {
          $hide=true;
        }
      } else if (in_array($col, $extraHiddenFields)) {
        $specificStyle.=' display:none';
        if ($print) $hide=true;
      }
      if ($col=='idBusinessFeature' and Parameter::getGlobalParameter('displayBusinessFeature')!='YES') {
        $hide=true;
      }
      if ($col=='idProject') {
        $uniqueProjectRestriction=false;
        $lstIdProject = array();
        if(pq_strpos(getSessionValue('project'), ",") != null){
          $lstIdProject = pq_explode(',', getSessionValue('project'));
        }
        if (getSessionValue('project')!="" and getSessionValue('project')!="*" and Parameter::getGlobalParameter('projectRestriction')=='YES') {
          if(pq_strpos(getSessionValue('project'), ",") != -1){
            foreach ($lstIdProject as $idProj){
              $proj=new Project($idProj, true);
              $subProjs=$proj->getSubProjectsList();
            }
          }else{
            $proj=new Project(getSessionValue('project'),true);
            $subProjs=$proj->getSubProjectsList();
          }
          if (count($subProjs)==0) {
            $uniqueProjectRestriction=true;
            $hide=true;
          }
        }
      }
      if (( ($col=='idUser' and $classObj!='Affectation') or $col=='creationDate' or $col=='creationDateTime' or $col=='lastUpdateDateTime') and !$print) {
        $hide=true;
      }
      // PBER #11354 : if hidden but nobr_before, keep nobre if set = case : idle | idleDate(hidden) | cancel | lib_cancelled
      //if ($obj->isAttributeSetToField($col, 'nobr') and ! $obj->isAttributeSetToField($col,'hidden') and !$hide and ! in_array($col, $extraHiddenFields)) {
      if ($obj->isAttributeSetToField($col, 'nobr') and ( ( ! $obj->isAttributeSetToField($col,'hidden') and !$hide and ! in_array($col, $extraHiddenFields) ) or $nobr_before ) ) {
        $nobr=true;
        $tempCurrentFound=false;
        foreach ($obj->getFieldsList() as $tmpCol) {
          if ($tmpCol==$col) {
            $tempCurrentFound=true;
            continue;
          } else if ($tempCurrentFound==false) {
            continue;
          }
          // Here current was found and
          if ($obj->isAttributeSetToField($tmpCol, 'hidden') or in_array($tmpCol, $extraHiddenFields)) {
            if (!$obj->isAttributeSetToField($tmpCol, 'nobr')) {
              $nobr=false; // Current is NOBR but next is hidden and not NOBR (no next on same line) : remove NOBR
              break;
            }
          } else {
            break; // OK current is NOBR and next is visible
          }
        }
      }
      if ($obj->isAttributeSetToField($col, 'invisible')) {
        $specificStyle.=' display:none';
      }
      if (pq_strpos($obj->getFieldAttributes($col), 'title')!==false) {
        $attributes.=' title="'.$obj->getTitle($col).'"';
      }
      if ($col=='idComponent' or $col=='idComponentVersion' or $col=='idOriginalComponentVersion' or $col=='idTargetComponentVersion') {
        if (Component::canViewComponentList($obj)!='YES') {
          $hide=true;
        }
      }
      if ($parentHidden) {
        $hide=true;
      }
      // CHANGE BY Marc TABARY - 2017-03-01 - DATA CONSTRUCTED BY FUNCTION
      if (!$canUpdate or (pq_strpos($obj->getFieldAttributes($col), 'readonly')!==false) or $parentReadOnly or (property_exists($obj, 'idle') and ($obj->idle==1 and $col!='idle' and $col!='idStatus')) or pq_substr($col, 0, 7)=='_byMet_') {
        // END CHANGE BY Marc TABARY - 2017-03-01 - DATA CONSTRUCTED BY FUNCTION
        // COMMENT BY Marc TABARY - 2017-03-01 - DATA CONSTRUCTED BY FUNCTION
        // Old
        // if (!$canUpdate or (pq_strpos($obj->getFieldAttributes($col), 'readonly') !== false) or $parentReadOnly or ($obj->idle == 1 and $col != 'idle' and $col != '')) {
        // END COMMENT BY Marc TABARY - 2017-03-01 - DATA CONSTRUCTED BY FUNCTION
        // ADD BY Marc TABARY - 2017-03-09 - PERIODIC YEAR BUDGET ELEMENT
        if ((pq_strpos($obj->getFieldAttributes($col), 'forceInput')!==false and pq_substr($col, 0, 7)=='_byMet_' and !$parentReadOnly) or (pq_strpos($obj->getFieldAttributes($col), 'superforceInput')!==false and pq_substr($col, 0, 7)=='_byMet_')) {} else {
          // END ADD BY Marc TABARY - 2017-03-09 - PERIODIC YEAR BUDGET ELEMENT
          $attributes.=' readonly tabindex="-1"';
          $notReadonlyClass="";
          $readOnly=true;
        }
      } else if (in_array($col, $extraReadonlyFields)) {
        $attributes.=' readonly tabindex="-1"';
        $readOnly=true;
      }
      if(get_class($obj)=='ActivityPlanningElement' and ($col=='validatedCost' or $col=='validatedWork')){
        if(pq_trim(pq_strpos($obj->getFieldAttributes($col), 'readonly'))!='' or in_array($col, $extraReadonlyFields)){
          if($col=='validatedWork'){
            $validatedWorkReadOnly=true;
          }else if ($col=='validatedCost'){
             $validatedCostReadOnly=true;
          }
        }
      }
  
      // ADD BY Marc TABARY - 2017-02-28 - DATA CONSTRUCTED BY FUNCTION
      if (pq_substr($col, 0, 7)=='_byMet_') {
        if (SqlElement::isWork($col) or SqlElement::isPct($col) or SqlElement::isAmount($col)) {
          $dataType='decimal';
          $dataLengthWithDec='14,5';
          $dataLength=14;
        }
        if (pq_substr($col, -4, 4)=='Name') {
          $dataType='varchar';
          $dataLength=400;
          $dataLengthWithDec=400;
        }
      } else {
        // END ADD BY Marc TABARY - 2017-02-28 - DATA CONSTRUCTED BY FUNCTION
        $dataType=$obj->getDataType($col);
        $dataLengthWithDec=$obj->getDataLength($col);
        $dataLength=intval($dataLengthWithDec);
      }
      if ($obj->isAttributeSetToField($col, 'calculated') and SqlElement::isAmount($col)) {
        $dataType='decimal';
      }
      if (SqlElement::isLocal($col) and SqlElement::isPct($col)) {
        $dataType='decimal';
        $dataLengthWithDec='5,2';
        $dataLength=intval($dataLengthWithDec);
      }
      if (SqlElement::isLocal($col) and SqlElement::isWork($col)) {
        $dataType='decimal';
        $dataLengthWithDec='12,2';
        $dataLength=intval($dataLengthWithDec);
      }
      if (SqlElement::isLocal($col) and SqlElement::isDate($col)) {
        $dataType='date';
        $dataLengthWithDec='10';
        $dataLength=intval($dataLengthWithDec);
      }
      if ($obj->isAttributeSetToField($col, 'invisible')) {
        $nobr=0;
        $specificStyle.=";display:none";
      }
      if ($internalTable==0) {
        if (!is_object($val) and !is_array($val) and !$hide and !$nobr_before) {
          echo '<tr class="detail'.((!$nobr)?' generalRowClass '.$col.'Class':'').'" style="'.((!$nobr)?$specificStyle:'').'">';
          $lineStarted=true;
          $isPdfDetailRow=($print and (($outMode=='pdf') or (isset($outModeBack) and $outModeBack=='pdf')));
          $pdfDetailCellSpacing=(isNewGui() and $isPdfDetailRow)?'padding-top:9px;padding-bottom:9px;vertical-align:middle;':'';
          if ($dataLength>4000 and getEditorType()!='text') {
            // Will have to add label
            echo '<td colspan="2" style="position:relative">';
          } else {
            echo '<td class="label" style="position:relative;width:'.$labelStyleWidth.';'.$pdfDetailCellSpacing.'">';
            $thumbRes=SqlElement::isThumbableField($col);
            $thumbColor=SqlElement::isColorableField($col,$val);
            $thumbIcon=SqlElement::isIconableField($col,$val); 
            $formatedThumb='';
            if ($thumbIcon) {
              $formatedThumb=formatIconThumb(SqlList::getFieldFromId(pq_substr(foreignKeyWithoutAlias($col),2), $val, 'icon') , ((isNewGui())?32:22), 'right');
            } else if ($thumbRes) {
              $formatedThumb=formatUserThumb($val, null, null, ((isNewGui())?32:22), 'right');
            } else if ($thumbColor) {
              $formatedThumb=formatColorThumb(foreignKeyWithoutAlias($col), $val, ((isNewGui())?25:20), 'right');
            }
            $thumb=(! $print && $val && ($thumbRes or $thumbColor or $thumbIcon) && $showThumb && $formatedThumb)?true:false;
            $extraLocalClass=($obj->isLocal($col))?' localLabelClass':'';
            echo '<label for="'.$col.'" class="'.(($thumb)?'labelWithThumb ':'').'generalColClass '.$col.'Class '.$extraLocalClass.'" style="'.$specificStyle.';'.$labelStyle.'">';
            if ($outMode=='pdf') {
              echo pq_str_replace(' ', '&nbsp;', htmlEncode($obj->getColCaption($col), 'stipAllTags'));
            } else {
              echo htmlEncode($obj->getColCaption($col), 'stipAllTags');
            }
            echo '&nbsp;'.(($thumb or isNewGui())?'':':&nbsp;').'</label>'.$cr;
            if ($thumb) {
              // echo $formatedThumb;
              $pos=(isNewGui() and $thumbColor and !$thumbIcon)?'-2':'0';
              if (!$print) {
                if (get_class($obj)=='InputMailboxTicket' and $col=='idStatus') echo '<div style="position:absolute;top:6px;right:'.$pos.'px;float:right;">';
                else echo '<div style="position:absolute;top:1px;right:'.$pos.'px;float:right;">';
              }
              if ($col=='idStatus') {
                echo '<div onClick="drawGraphStatus();" class="graphStatusDivContainer">';
              }
              echo $formatedThumb;
              if ($col=='idStatus') {
                echo '</div>';
                echo '<div id="graphStatusDiv" dojoType="dijit.layout.ContentPane" region="center" class="graphStatusDiv">';
                echo '</div>';
              }
              if (!$print) echo "</div>";
            }
            echo '</td>';
            // Keep the historical screen/print height. For PDF, vertical padding
            // gives a similar interline without making HTML2PDF treat the table
            // rows as fixed-height blocks and move the first section to page 2.
            $printDetailRowHeight=(isNewGui())?(($isPdfDetailRow)?$pdfDetailCellSpacing:'height:37px;'):'';
            if ($print and $outMode=="pdf") {
              $printFieldWidth=($largeWidth+10);
              if (in_array($col, array('expectedProgress', 'idActivityPlanningMode', 'hatchPattern', 'indivisibility'))) {
                $printFieldWidth=90;
              }
              echo '<td style="width:'.$printFieldWidth.'px;'.$printDetailRowHeight.'">';
            } else {
              echo '<td style="width:'.($largeWidth+10).'px;'.$printDetailRowHeight.'">';
            }
          }
        }
      } else {
        // $internalTableBorder=($print)?'border:1px dotted #A0A0A0;':'';
        $internalTableBorder='';
        $alignForNumber='';
        if ($dataType=='decimal' and $print and SqlElement::isAmountOrWork($col)) {
          $alignForNumber='text-align:right;';
        }
        $isPrintCostWorkTable=false;
        if ($print and $internalTable and in_array($col, array(
          'validatedWork', 'assignedWork', 'realWork', 'leftWork', 'plannedWork',
          'validatedCost', 'assignedCost', 'realCost', 'leftCost', 'plannedCost',
          'validatedCostLocal', 'assignedCostLocal', 'realCostLocal', 'leftCostLocal', 'plannedCostLocal',
          'expenseValidatedAmount', 'expenseAssignedAmount', 'expenseRealAmount', 'expenseLeftAmount', 'expensePlannedAmount',
          'expenseValidatedAmountLocal', 'expenseAssignedAmountLocal', 'expenseRealAmountLocal', 'expenseLeftAmountLocal', 'expensePlannedAmountLocal'
        ))) {
          $isPrintCostWorkTable=true;
          $alignForNumber='text-align:left;';
        }
        $printInternalCellPadding=($print)?(($isPrintCostWorkTable)?'padding-right:4px;':'padding-right:20px;'):'';
        $printInternalRowSpacing=($print)?'padding-top:3px;padding-bottom:3px;vertical-align:middle;':'';
        if ($internalTable%$internalTableCols==0) {
          echo '</td></tr>'.$cr;
          echo '<tr class="detail">';
          $lineStarted=true;
          if (isset($internalTableRowsCaptions[$internalTableCurrentRow]) and $internalTableRowsCaptions[$internalTableCurrentRow] and $arrTab['rows'][$internalTableCurrentRow]>0) {
            $internalTableRowLabelWidth=($internalTablePrintCompact)?'70px':$labelStyleWidth;
            echo '<td class="labelPadding '.$internalTableSpecial.'" style="text-align:right;width:'.$internalTableRowLabelWidth.';'.$printInternalRowSpacing.'">';
            // ADD BY Marc TABARY - 2017-03-10 - NO ':' IF LABEL IS EMPTY
            $theLabelTab=htmlEncode($obj->getColCaption($internalTableRowsCaptions[$internalTableCurrentRow]));
            if ($internalTableRowsCaptions[$internalTableCurrentRow]=='empty') {
              $theLabelTab='';
            }
            if ($internalTableRowsCaptions[$internalTableCurrentRow]=='priority' and in_array('priority', $extraHiddenFields) and SqlElement::is_a($obj,'PlanningElement')) $theLabelTab='';
            if ($theLabelTab=='') {
              $extraLocalClass=($obj->isLocal($internalTableRowsCaptions[$internalTableCurrentRow]))?' localLabelClass':'';
              echo '<label class="label '.$internalTableSpecial.$extraLocalClass.'">'.$theLabelTab.'&nbsp;&nbsp;</label>';
            } else {
              $extraLocalClass=($obj->isLocal($internalTableRowsCaptions[$internalTableCurrentRow]))?' localLabelClass':'';
              // END ADD BY Marc TABARY - 2017-03-10 - NO ':' IF LABEL IS EMPTY
              echo '<label class="label '.$internalTableSpecial.$extraLocalClass.'">'.htmlEncode($obj->getColCaption($internalTableRowsCaptions[$internalTableCurrentRow])).'&nbsp;'.((isNewGui())?'':':&nbsp;').'</label>';
            }
          } else {
            $internalTableRowLabelWidth=($internalTablePrintCompact)?'70px':$labelStyleWidth;
            echo '<td class="" style="width:'.$internalTableRowLabelWidth.';'.$printInternalRowSpacing.'">';            
          }
          $internalTableFirstCellWidth=($internalTablePrintCompact)?'width:45px;':'width:90%;';
          echo '</td><td style="'.$alignForNumber.$internalTableFirstCellWidth.'white-space:nowrap;'.$printInternalCellPadding.$printInternalRowSpacing.$internalTableBorder.'">';
          $internalTableCurrentRow++;
        } else {
          if ($obj->isAttributeSetToField($col, "colspan3")) {
            $internalTableColspanStyle=($internalTablePrintCompact)?'width:135px;':'';
            echo '</td><td class="detail" colspan="3" style="'.$alignForNumber.$internalTableColspanStyle.$printInternalRowSpacing.'">';
            $internalTable-=2;
          } else {
            $internalTableDataCellWidth=($internalTablePrintCompact)?'width:45px;':'';
            echo '</td><td class="detail" style="'.$alignForNumber.$internalTableDataCellWidth.'white-space:nowrap;'.$printInternalCellPadding.$printInternalRowSpacing.$internalTableBorder.'">';
          }
        }
      }
      // echo $col . "/" . $dataType . "/" . $dataLength;
      if ($dataLength) {
        if ($dataLength<=3) {
          $fieldWidth=$verySmallWidth;
        } else if ($dataLength<=6) {
          $fieldWidth=$smallWidth;
        } else if ($dataLength<=16) {
          $fieldWidth=$mediumWidth;
        } else {
          $fieldWidth=$largeWidth;
        }
      }
      if (isNewGui()) $fieldWidth-=10; 
      //if (pq_substr($col, 0, 2)=='id' and $dataType=='int' and pq_strlen($col)>2 and pq_substr($col, 2, 1)==pq_strtoupper(pq_substr($col, 2, 1))) {
      if (isForeignKey($col, $obj)) {
        $fieldWidth=$largeWidth;
      }
      if (pq_strpos($obj->getFieldAttributes($col), 'Width')!==false) {
        if (pq_strpos($obj->getFieldAttributes($col), 'smallWidth')!==false) {
          $fieldWidth=$smallWidth;
        }
        if (pq_strpos($obj->getFieldAttributes($col), 'mediumWidth')!==false) {
          $fieldWidth=$mediumWidth;
        }
        if (pq_strpos($obj->getFieldAttributes($col), 'truncatedWidth')!==false) {
          $pos=pq_strpos($obj->getFieldAttributes($col), 'truncatedWidth');
          $truncValue=pq_substr($obj->getFieldAttributes($col), $pos+14, 3);
          $fieldWidth-=$truncValue;
        }
      }
      // echo $dataType . '(' . $dataLength . ') ';
      if ($included) {
        $name=' id="'.$classObj.'_'.$col.'" name="'.$classObj.'_'.$col.$extName.'" ';
        $nameBis=' id="'.$classObj.'_'.$col.'Bis" name="'.$classObj.'_'.$col.'Bis'.$extName.'" ';
        $fieldId=$classObj.'_'.$col;
      } else {
        $name=' id="'.$col.'" name="'.$col.$extName.'" ';
        $nameBis=' id="'.$col.'Bis" name="'.$col.'Bis'.$extName.'" ';
        $fieldId=$col;
      }
      // prepare the javascript code to be executed
      $colScript="";
      if ($outMode!='pdf') $colScript=$obj->getValidationScript($col);
      $colScriptBis="";
      if ($dataType=='datetime' and $outMode!='pdf') {
        $colScriptBis=$obj->getValidationScript($col."Bis");
      }
      // if ($comboDetail) {
      // $colScript=pq_str_replace($col,$col . $extName,$colScript);
      // $colScriptBis=pq_str_replace($col,$col . $extName,$colScriptBis);
      // }
      $specificStyleWithoutCustom=$specificStyle;
      $specificStyle.=";".$fieldStyle;
      //if (! isNewGui()) $fieldWidth-=15;   
      if (pq_strpos($obj->getFieldAttributes($col), 'size1/3')!==false) {
        $fieldWidth=$fieldWidth/3-3;
      } else if (pq_strpos($obj->getFieldAttributes($col), 'size1/2')!==false) {
        $fieldWidth=$fieldWidth/2-2;
      } else if (($nobr_before or $nobr) and $fieldWidth>$mediumWidth) {
        $fieldWidth=($nobr_before and $nobr)?intval($fieldWidth/3-3):intval($fieldWidth/2-2);
      }
      if (pq_strpos($obj->getFieldAttributes($col), 'size50')!==false) {
        $fieldWidth=$fieldWidth+50;
      }
      if (is_object($val)) {
        if ($col=='Origin' and !$hide and ! $obj->isAttributeSetToField($col, 'hidden') and ! in_array($col, $extraHiddenFields)) {
          drawOrigin($obj->Origin, $val->originType, $val->originId, $obj, $col, $print);
        } else {
          // Draw an included object (recursive call) =========================== Type Object
          $visibileSubObject=true;
          if (get_class($val)=='WorkElement') {
            $hWork=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'work'));
            if ($hWork and $hWork->id) {
              $visibility=SqlList::getFieldFromId('VisibilityScope', $hWork->rightAccess, 'accessCode', false);
              if ($visibility!='ALL') {
                $visibileSubObject=false;
              }
              $canWorkT=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'canWorkOnTicket'));
              if ($canWorkT and $canWorkT->id) {
                if($canWorkT->rightAccess == 1){
                  $visibileSubObject=true;
                }else if($canWorkT->rightAccess == 2 and $visibility=='ALL'){
                  $readOnly=true;
                }
              }
            }
          }
          if ($hide or $obj->isAttributeSetToField($col, 'hidden') or in_array($col, $extraHiddenFields)) {
            $visibileSubObject=false;
          }
          drawTableFromObject($val, true, $readOnly, !$visibileSubObject);
          $hide=true; // to avoid display of an extra field for the object and an additional carriage return
                        // }
        }
        // }
      } else if (is_array($val)) {
        // Draw an array ====================================================== Type Array
        traceLog("Error : array fileds management not implemented for fiels $col");
      } else if (pq_substr($col, 0, 6)=='_void_') {
        // Empty field for tabular presentation
        // echo $col . ' is an array' . $cr;
        //
      } else if (pq_substr($col, 0, 7)=='_label_') {
        $captionName=pq_substr($col, 7);
        if (pq_substr($captionName,-5)=='Local') {
          $captionName=pq_substr($captionName,0,-5);
        }
        if (!$hide) {
          $extraLocalClass=($obj->isLocal($col))?' localLabelClass':'';
          if ($obj->isAttributeSetToField($col, 'leftAlign')) {
            echo '<span class=" '.$col.'Class '.$extraLocalClass.'" style="'.$specificStyle.'">&nbsp;'.i18n('col'.pq_ucfirst($captionName)).'</span>';
          } else {
            echo '<label class="label '.(($obj->isAttributeSetToField($col, 'longLabel'))?'':'shortlabel').' '.$col.'Class '.$extraLocalClass.'" style="'.$specificStyle.'">'.i18n('col'.pq_ucfirst($captionName)).'&nbsp;'.((isNewGui())?'':':').'&nbsp;</label>';
          }
        }
      } else if (pq_substr($col, 0, 8)=='_button_') {
        if (!$print and !$comboDetail and !$obj->isAttributeSetToField($col, 'hidden') and !$hide) {
          $item=pq_substr($col, 8);
          echo $obj->drawSpecificItem($item);
        }
      } else if ($col=='tags' and !$hide and ! $obj->isAttributeSetToField('tags', 'hidden')) {
        //echo '<tr><td class="label"><label>'.i18n('colTags').'&nbsp;:&nbsp;</label></td><td>';
        $tagListContainerStyle='padding:2px 2px;width:97%;min-height:20px;height:100%;position:relative;';
        if ($print) $tagListContainerStyle.='border:0;background:transparent;';
        echo '<div id="tagListContainer" class="input" style="'.$tagListContainerStyle.'">';
       
        echo '<span id="tagList" style="position:relative;">';
        $tags=pq_explode('#',pq_nvl($val));
        foreach ($tags as $tag) {
          if (pq_trim($tag)) {
            $tag=htmlEncode($tag);
            $tagStyle=($print)?'display:inline-block;float:none;background:#F7F7FA;border:2px solid #6F6FA0;border-radius:10px;color:#47477F;padding:2px 4px 2px 8px;margin:1px 4px 1px 0;line-height:14px;white-space:nowrap;':'';
            echo '<span class="docLineTag'.(($print)?' printTag':'').'" id="'.$tag.'TagDiv" style="'.$tagStyle.'">';
            echo $tag.'&nbsp;';
            if ($print) echo '<span class="docLineTagPin" style="display:inline-block;width:9px;height:9px;margin-left:2px;border:1px solid #CFCFD8;border-radius:5px;background:#FFFFFF;vertical-align:middle;">&nbsp;</span>';
            if (! $print and $canUpdate) echo '<div class="docLineTagRemove" onClick="removeDocumentTag(\''.$tag.'\');"><div style="position: relative;top: -1px;">x</div></div>';
            echo '</span>';
          }
        }
        echo '</span>';
        if (!$print and $canUpdate and ! $obj->isAttributeSetToField('tags', 'hidden')) {
          echo '<select dojoType="dijit.form.ComboBox" xclass="input" name="tagInput" id="tagInput" hasDownArrow="false" style="float:left;padding-top:0px;padding-left:10px;background:none;border:none;width:25%;" placeholder="'.i18n('newTag').'">';
          echo '<option value=""></option>';
          if(Parameter::getGlobalParameter('listTagsPerProject')=="YES"){
            $critTag=array('refType'=>Tag::getRefType(get_class($obj)),'idProject'=>$obj->idProject);
          }else{
            $critTag=array('refType'=>Tag::getRefType(get_class($obj)));
          }
          $lst=SqlList::getListWithCrit('Tag',$critTag);
          foreach ($lst as $tag) {
            echo '<option value="'.$tag.'">'.$tag.'</option>';
          }
          echo '<script type="dojo/method" event="onClick">';
          echo ' dijit.byId("tagInput").toggleDropDown();';
          echo '</script>';
          echo '<script type="dojo/connect" event="onChange">';
          echo ' formChanged();';
          echo ' addDocumentTag(this.value);';
          echo '</script>';
          echo '<script type="dojo/method" event="onKeyPress">';
          echo '  if(event.keyCode==13){';
          echo '    var activeElement = document.activeElement;';
          echo '    if(activeElement.id == \'tagInput\'){';
          echo '    var tagInput = dijit.byId(\'tagInput\');';
          echo '      if(tagInput){';
          echo '        tagInput.toggleDropDown();';
          echo '      }';
          echo '    }';
          echo '  }else{';
          echo '    setTimeout(\'dojo.byId("widget_tagInput").style.width=dijit.byId("tagInput").get("value").length+" ch";\',100);';
          echo '  }';
          echo '</script>';          
          echo '</select>';
        }
        echo '</div>';
        //echo '<input type="hidden" name="tags" id="tags" value="'.$val.'" />';
        echo '<input type="hidden" name="tags'.$extName.'" id="tags" value="'.$val.'" />';
        //echo '</td></tr>';
      } else if ($print) {
        // ============================================================================================================
        // ================================================
        // ================================================ PRINT
        // ================================================
        // ============================================================================================================
        if ($hide) { // hidden field
                       // nothing
        } else if (pq_strpos($obj->getFieldAttributes($col), 'displayHtml')!==false) {
          // Display full HTML ================================================== Hidden field
          // echo '<div class="displayHtml">';
          echo '<span style="'.$fieldStyle.'">';
          if ($outMode=='pdf') {
            echo htmlRemoveDocumentTags($val);
          } else {
            echo $val;
          }
          echo '</span>';
        } else if ($col=='id') { // id
          echo '<span style="color:grey;'.$fieldStyle.'">#'.$val."&nbsp;&nbsp;&nbsp;</span>";
        } else if ($col=='password') {
          echo "..."; // nothing
        } else if ($dataType=='date' and $val!=null and $val!='') {
          echo '<span style="'.$fieldStyle.'">';
          echo htmlFormatDate($val);
          echo '</span>';
        } else if ($dataType=='datetime' and $val!=null and $val!='') {
          // echo pq_str_replace(' ','&nbsp;',htmlFormatDateTime($val, false));
          echo '<span style="'.$fieldStyle.'">';
          echo htmlFormatDateTime($val, false);
          echo '</span>';
        } else if ($dataType=='time' and $val!=null and $val!='') {
          echo '<span style="'.$fieldStyle.'">';
          echo htmlFormatTime($val, false);
          echo '</span>';
        } else if ( ($col=='color' or (pq_substr($col,0,5)=='color' and pq_strlen($col)>5 and pq_strtoupper(pq_substr($col,5,1))==pq_substr($col,5,1) ) ) and $dataType=='varchar' and $dataLength==7) { // color
          echo '<table><tr><td style="width: 100px;">';
          echo '<div class="colorDisplay" readonly tabindex="-1" ';
          echo '  value="'.htmlEncode($val).'" ';
          echo '  style="width:'.($smallWidth/2).'px; border-radius:10px;';
          echo ' color: '.$val.'; ';
          echo ' background-color: '.$val.';"';
          echo ' >';
          echo '</div>';
          echo '</td>';
          if ($val!=null and $val!='') {
            // echo '<td class="detail">&nbsp;(' . htmlEncode($val) . ')</td>';
          }
          echo '</tr></table>';
        } else if ($dataType=='int' and $dataLength==1) { // boolean
          $checkClass="booleanCheckBox";
          // image checkbox for any print (pdf AND html print) so print matches the pdf export
          $isPdfBoolean=$print;
          $isChecked=($val!='0' and !$val==null);
          // In modernUI the on screen validated checkbox is green : use the colored image for PDF too.
          $pdfCheckedImg=(isModernUi())?'checkboxModernCheckedColor.png':'checkboxModernChecked.png';
          $checkContent=($isPdfBoolean)?'<img src="../view/img/'.(($isChecked)?$pdfCheckedImg:'checkboxModernUnchecked.png').'" width="16" height="16" style="vertical-align:middle;" />':'';
          $checkStyle=($isPdfBoolean)
            ? 'white-space:nowrap;'
            : 'display:inline-block;background-image:url(../view/css/images/checkmarkNoBorderGrey.png);background-repeat:no-repeat;background-position:-16px;background-color:#FFFFFF;border:1px solid #d4d4d4;border-radius:5px;width:16px;height:16px;margin:0;padding:0;vertical-align:middle;';
          if ($isChecked) {
            $checkClass.=' booleanCheckBoxChecked';
            if (!$isPdfBoolean) {
              $checkStyle='display:inline-block;background-image:url(../view/css/images/checkmarkNoBorderGrey.png);background-repeat:no-repeat;background-position:0px;background-color:#FFFFFF;border:1px solid #d4d4d4;border-radius:5px;width:16px;height:16px;margin:0;padding:0;vertical-align:middle;';
            }
          }
          if ($col=='cancelled' or $col=='solved') echo "&nbsp;&nbsp;&nbsp;";
          echo '&nbsp;<span class="'.$checkClass.'" style="'.$checkStyle.'">'.$checkContent.'</span>&nbsp;';
          if ($col=='idle' && $classObj == "PeriodicMeeting") echo '</td></tr>';
          // BEGIN - REPLACE BY TABARY - USE isForeignKey GENERIC FUNCTION
        } else if (isForeignKey($col, $obj)) { // Idxxx
                                               // } else if (pq_substr($col, 0, 2) == 'id' and $dataType == 'int' and pq_strlen($col) > 2 and pq_substr($col, 2, 1) == pq_strtoupper(pq_substr($col, 2, 1))) { // Idxxx
                                               // END - REPLACE BY TABARY - USE isForeignKey GENERIC FUNCTION
          echo '<span style="'.$fieldStyle.'">';
          // BEGIN - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES SAME idXXXX IN THE SAME OBJECT
          echo htmlEncode(SqlList::getNameFromId(pq_substr(foreignKeyWithoutAlias($col), 2), $val));
          // echo htmlEncode(SqlList::getNameFromId(pq_substr($col, 2), $val));
          // END - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES SAME idXXXX IN THE SAME OBJECT
          echo '</span>';
        } else if ($dataLength>4000) {
          // echo '</td></tr><tr><td colspan="2">';
          echo '<div style="text-align:left;font-weight:normal;'.(($print)?'border:0':'').'" class="tabLabel longTextLabel">'.htmlEncode($obj->getColCaption($col), 'stipAllTags').'&nbsp;:&nbsp;</div>';
          echo '<div style="border:1px dotted #AAAAAA;width:'.($colWidth-20).'px;padding:5px;'.$fieldStyle.'">';
          if (isTextFieldHtmlFormatted($val)) $val=htmlEncode($val, 'formatted');
          if ($outMode=="pdf") { // Must purge data, otherwise will never be generated
            if ($preseveHtmlFormatingForPDF) {
              $val='<div>'.$val.'</div>';
            } else {
              $val=htmlEncode($val, 'pdf'); // remove all tags but line breaks
            }
          }
          echo $val.'&nbsp;';
          echo '</div>';
        } else if ($dataLength>100) { // Text Area (must reproduce BR, spaces, ...
          echo '<span style="'.$fieldStyle.'">';
          echo htmlEncode($val, 'print');
          $fldFull='_'.$col.'_full';
          if ($outMode=='pdf' and isset($obj->$fldFull)) {
            echo '<img src="../view/css/images/doubleArrowDown.png" />';
          }
          echo '</span>';
        } else if ($dataType=='decimal' and SqlElement::isAmount($col)) {
          echo '<span style="'.$fieldStyle.'">';
          echo costFormatter($val);
          //if ($currencyPosition=='after') {
          //  echo htmlEncode($val, 'print').' '.$currency;
          //} else {
          //  echo $currency.' '.htmlEncode($val, 'print');
          //}
          echo '</span>';
        } else if ($dataType=='decimal' and SqlElement::isWork($col)) {
          echo '<span style="'.$fieldStyle.'">';
          if ($classObj=='WorkElement' or $classObj=='TokenDefinition' or $classObj=='Resource') {
            echo Work::displayImputation($val).' '.Work::displayShortImputationUnit();
          } else {
            echo Work::displayWork($val).' '.Work::displayShortWorkUnit();
          }
          echo '</span>';
        } else if (SqlElement::isPct($col)) {
          echo '<span style="'.$fieldStyle.'">';
          echo $val.'&nbsp;%';
          echo '</span>';
        } else if ($col=='icon') {
          if ($val) {
            echo '<img src="../view/icons/'.$val.'" />';
          }
        } else {
          if ($obj->isFieldTranslatable($col)) {
            $val=i18n($val);
          }
          if (0 and $internalTable==0) {
            echo '<div style="width: 80%;'.$fieldStyle.'"> ';
            if (pq_strpos($obj->getFieldAttributes($col), 'html')!==false) {
              echo $val;
            } else {
              echo htmlEncode($val, 'print');
            }
            echo '</div>';
          } else {
            echo '<span style="'.$fieldStyle.'">';
            if (pq_strpos($obj->getFieldAttributes($col), 'html')!==false) {
              echo $val;
            } else {
              echo htmlEncode($val, 'print');
            }
            echo '</span>';
          }
        }
        // ============================================================================================================
        // ================================================
        // ================================================ END OF PRINT : Entering general case
        // ================================================
        // ============================================================================================================
      } else if ($hide) {
        // Don't draw the field =============================================== Hidden field
        if (!$print) {
          if ($col=='creationDate' and ($val=='' or $val==null) and !$obj->id) {
            $val=date('Y-m-d');
          }
          if ($col=='creationDateTime' and ($val=='' or $val==null) and !$obj->id) {
              $val=convertServerTimeToUserTimezone(date('Y-m-d H:i:s'));
          } else if ($dataType=='datetime' and $val) {
            $val=convertServerTimeToUserTimezone($val);
          } else if ($dataType=='time' and $val) {
            $val=convertServerTimeToUserTimezone($val);
          }
          if ($col=='idUser' and ($val=='' or $val==null) and !$obj->id) {
            $val=$user->id;
          }
          // BEGIN - ADD BY TABARY - IF SPINNER AND HIDE => Draw but display:none
          if ($isSpinner and is_integer(intval($val))) {
            $title=' title="'.$obj->getTitle($col).'"';
            echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
            echo htmlDrawSpinner($col, $val, $obj->getSpinnerAttributes($col), $obj->getFieldAttributes($col), $name, $title, $smallWidth, $colScript);
          } else {
            // END - ADD BY TABARY - IF SPINNER AND HIDE => Draw but display:none
            echo '<div dojoType="dijit.form.TextBox" type="hidden"  ';
            echo $name;
            if ($dataType=='decimal' and SqlElement::isWork($col)) {
              if ($classObj=='WorkElement' or $classObj=='TokenDefinition' or $classObj=='Resource') {
                $val=Work::displayImputation($val);
              } else {
                $val=Work::displayWork($val);
              }
            }
            echo ' value="'.htmlEncode($val).'" ></div>';
          }
        }
      } else if (pq_strpos($obj->getFieldAttributes($col), 'displayHtml')!==false) {
        // Display full HTML ================================================== Simple Display html field
        echo '<div class="displayHtml generalColClass '.$col.'Class" style="'.$specificStyle.'">';
        echo $val;
        echo '</div>';
      } else if ($col=='id') {
        // Draw Id (only visible) ============================================= ID
        // id is only visible
        $ref=$obj->getReferenceUrl();
        echo '<span id="objectDetailObjectId" class="roundedButton" style="padding:1px 5px 5px 5px;font-size:8pt; height: 50px; color:#AAAAAA;'.$specificStyle.'" >';
//         echo '  <a  href="'.$ref.'" onClick="copyDirectLinkUrl(\'Detail\');return false;"'.' title="'.i18n("rightClickToCopy").'" style="cursor: pointer;">';
        echo '  <a href="'.$ref.'" onClick="if(this._clicked)return false;this._clicked=true;setTimeout(()=>this._clicked=false,1000);copyDirectLinkUrl(\'Detail\');return false;" ondblclick="return false;" title="'.i18n("rightClickToCopy").'" style="cursor: pointer;">';
        echo '    <span style="color:grey;vertical-align:middle;padding: 2px 0px 2px 0px !important;'.$specificStyle.'">#</span>';
        echo '    <span dojoType="dijit.form.TextBox" type="text"  ';
        echo $name;
        echo '     class="display pointer" ';
        echo '     readonly tabindex="-1" style="background: transparent; border: 0; cursor: pointer !important;width: '.$smallWidth.'px;'.$specificStyle.'" ';
        echo '     value="'.htmlEncode($val).'" >';
        echo '    </span>';
        echo '  </a>';
        echo '</span>';
        echo '<input readOnly type="text" onClick="this.select();" id="directLinkUrlDivDetail" style="display:none;font-size:10pt; color: #000000;position :absolute; top: 28px; left: 187px; border: 0;background: transparent;width:100%;" value="'.$ref.'" />';
        $alertLevelArray=$obj->getAlertLevel(true,false);
        $alertLevel=$alertLevelArray['level'];
        $colorAlert="background-color:#FFFFFF";
        if ($alertLevel!='NONE') {
          if ($alertLevel=='ALERT') {
            $colorAlert='background-color:#FFAAAA;';
          } else if ($alertLevel=='WARNING') {
            $colorAlert='background-color:#FFFFAA;';
          }
          echo '<span style="width:20px; position: absolute; left: 5px;" id="alertId" >';
          if ($alertLevel=='ALERT') {
            echo '<image style="z-index:3;position:relative" src="../view/css/images/indicatorAlert32.png" />';
          } else {
            echo '<image style="z-index:3;position:relative" src="../view/css/images/indicatorWarning32.png" />';
          }
          echo '</span>';
          echo '<div dojoType="dijit.Tooltip" connectId="alertId" position="below">';
          echo $alertLevelArray['description'];
          echo '</div>';
        }
      } else if ($col=='reference' and ! $obj->isAttributeSetToField($col, 'canChangeReference')) {
        // Draw reference (only visible) ============================================= ID
        // id is only visible
        echo '<span dojoType="dijit.form.TextBox" type="text"  ';
        echo $name;
        echo ' class="display generalColClass '.$col.'Class" ';
        $refWidth=$largeWidth-$smallWidth-40;
        if ($fieldWidth<$refWidth) $refWidth=$fieldWidth;
        echo ' readonly tabindex="-1" style="'.$specificStyle.';width: '.$refWidth.'px;" ';
        echo ' value="'.htmlEncode($val).'" ></span>';
      } else if ($col=='localCurrencyPosition') {
        //if (!$val) $val=Parameter::getGlobalParameter('currencyPosition');
        echo '<select dojoType="dijit.form.FilteringSelect" class="input '.(($isRequired)?'required':'').' generalColClass '.$col.'Class" ';
        echo '  style="width: '.($fieldWidth).'px;'.$specificStyle.'"';
        echo autoOpenFilteringSelect($comboDetail);
        echo $attributes;
        echo $name;
        echo ' value="'.$val.'" ';
        echo ' >';
        echo '<option value=" "></option>';
        echo '<option value="after">'.i18n('after').'</option>';
        echo '<option value="before">'.i18n('before').'</option>';
        echo '</select>';
      } else if ($col=='password') {
        //$paramDefaultPassword=Parameter::getGlobalParameter('paramDefaultPassword');
        // Password specificity ============================================= PASSWORD
        if ($canUpdate) {
          echo '<button id="resetPassword" dojoType="dijit.form.Button" showlabel="true"';
          echo ' class="roundedVisibleButton generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" style="'.$specificStyleWithoutCustom.'"';
          echo $attributes;
          $salt=hash('sha256', "projeqtor".date('YmdHis'));
          $newPwd = User::getRandomPassword();
          echo ' title="'.i18n('helpResetPassword').'" >';
          echo '<span>'.i18n('resetPassword').'</span>';
          echo '<script type="dojo/connect" event="onClick" args="evt">';
          echo '  dijit.byId("salt").set("value","'.$salt.'");';
          //echo '  dijit.byId("crypto").set("value","sha256");';
          echo '  dijit.byId("crypto").set("value",null);';
          //echo '  dojo.byId("password").value="'.hash('sha256', $paramDefaultPassword.$salt).'";';
          echo '  dojo.byId("password").value="'.$newPwd.'";';
          echo '  formChanged();';
          echo '  showInfo("'.i18n('passwordReset', array($newPwd)).'");';
          echo '</script>';
          echo '</button>';
        }
        // password not visible
        echo '<input type="password"  ';
        echo $name;
        echo ' class="display generalColClass '.$col.'Class" style="width:150px;position:relative; left: 3px;'.$specificStyle.'"';
        echo ' readonly tabindex="-1" ';
        echo ' value="'.htmlEncode($val).'" />';
      } else if($col=='pwdImap'){
        if (!$readOnly) $newWidth = $largeWidth-35;
        else $newWidth= $largeWidth-10;
        echo ' <div class="dijit dijitReset dijitInline dijitLeft input required generalColClass generalColClassNotReadonly userImapClass dijitTextBox dijitValidationTextBox" style="'.(($readOnly)?'background-color:#f0f0f0 !important;':'').'width:'.$newWidth.'px">';
        echo '<input type="password" autocomplete="new-password" style="max-width:'.($largeWidth-40).'px;border:1px solid blue;"  ';
        echo $attributes;
        echo $name;
        echo ' class="dijitReset dijitInputInner" data-dojo-attach-point="textbox,focusNode"  maxlength="100" tabindex="0" ';
        echo ' value="'.htmlEncode(decryptPwd($val)).'" />';
        echo ' </div>';
        if($canUpdate and !$readOnly){
          echo '<div class="iconView imageColorNewGui iconSize22" style="cursor:pointer;float:right;position:relative;top:6px;margin-right:4px;" onClick="dojo.setAttr(\''.$col.'\',\'type\',((dojo.getAttr(\''.$col.'\',\'type\')==\'password\')?\'text\':\'password\'));" ></div>';
          echo '</div>';
        }
      } else if($col=='securityConstraint'){
        if(!$val)$val = 1;
        echo '<table style="margin-top:5px;margin-bottom:5px">';
        echo '    <tr>';
        echo '      <td style="text-align:right;  width:5%" class="tabLabel" >';
        echo '        <input onClick="changeValueSecurityConstraint(1);" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='1')?'checked':'').' name="securityConstraintHidden" id="securityConstraint1" value="1" />';
        echo'       </td>';
        echo '      <td style="text-align:left;" >';
        echo '        '.i18n('securityConstraint1');
        echo '      </td>';
        echo '    </tr>';
        echo '    <tr>';
        echo '      <td style="text-align:right; width:5%" class="tabLabel">';
        echo '        <input onClick="changeValueSecurityConstraint(2);" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='2')?'checked':'').' name="securityConstraintHidden" id="securityConstraint2" value="2" />';
        echo'       </td>';
        echo '      <td style="text-align:left;">';
        echo '        '.i18n('securityConstraint2');
        echo '      </td>';
        echo '    </tr>';
        echo '    <tr>';
        echo '      <td style="text-align:right; width:5%" class="tabLabel">';
        echo '        <input onClick="changeValueSecurityConstraint(3);" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='3')?'checked':'').' name="securityConstraintHidden" id="securityConstraint3" value="3" />';
        echo'       </td>';
        echo '      <td style="text-align:left;">';
        echo '        '.i18n('securityConstraint3');
        echo '      </td>';
        echo '    </tr>';
        echo '</table>';
        echo '<input type="hidden" '.$name.' value="'.htmlEncode($val).'"  />';
      } else if($col=='actionOK' or $col=='actionKO'){
        if(!$val)$val = 'READ';
        echo '<table style="margin-top:5px;margin-bottom:5px">';
        if($col=='actionKO'){
          echo '    <tr>';
          echo '      <td style="text-align:right;  width:5%" class="tabLabel" >';
          echo '        <input onClick="changeValueActionMail(\''.$col.'\',\'NONE\');" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='NONE')?'checked':'').' name="'.$col.'Hidden" id="'.$col.'NONE" value="NONE" />';
          echo'       </td>';
          echo '      <td style="text-align:left;" >';
          echo '        '.i18n('actionMailNONE');
          echo '      </td>';
          echo '    </tr>';
        }
        echo '    <tr>';
        echo '      <td style="text-align:right; width:5%" class="tabLabel">';
        echo '        <input onClick="changeValueActionMail(\''.$col.'\',\'READ\');" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='READ')?'checked':'').' name="'.$col.'Hidden" id="'.$col.'READ" value="READ" />';
        echo'       </td>';
        echo '      <td style="text-align:left;">';
        echo '        '.i18n('actionMailREAD');
        echo '      </td>';
        echo '    </tr>';
        echo '    <tr>';
        echo '      <td style="text-align:right; width:5%" class="tabLabel">';
        echo '        <input onClick="changeValueActionMail(\''.$col.'\',\'DELETE\');" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='DELETE')?'checked':'').' name="'.$col.'Hidden" id="'.$col.'DELETE" value="DELETE" />';
        echo'       </td>';
        echo '      <td style="text-align:left;">';
        echo '        '.i18n('actionMailDELETE');
        echo '      </td>';
        echo '    </tr>';
        echo '</table>';
        echo '<input type="hidden" '.$name.' value="'.htmlEncode($val).'"  />';
      } else if($col=='reopenCondition'){
        if(!$val)$val = 'IDLE';
        echo '<table style="margin-top:5px;margin-bottom:5px">';
        echo '    <tr>';
        echo '      <td style="text-align:right;  width:5%" class="tabLabel" >';
        echo '        <input onClick="changeValueActionMail(\''.$col.'\',\'IDLE\');" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='IDLE')?'checked':'').' name="'.$col.'Hidden" id="'.$col.'IDLE" value="IDLE" />';
        echo'       </td>';
        echo '      <td style="text-align:left;" >';
        echo '        '.i18n('changeStatusIdle');
        echo '      </td>';
        echo '    </tr>';
        echo '    <tr>';
        echo '      <td style="text-align:right; width:5%" class="tabLabel">';
        echo '        <input onClick="changeValueActionMail(\''.$col.'\',\'DONE\');" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='DONE')?'checked':'').' name="'.$col.'Hidden" id="'.$col.'DONE" value="DONE" />';
        echo'       </td>';
        echo '      <td style="text-align:left;">';
        echo '        '.i18n('changeStatusDone');
        echo '      </td>';
        echo '    </tr>';
        echo '    <tr>';
        echo '      <td style="text-align:right; width:5%" class="tabLabel">';
        echo '        <input onClick="changeValueActionMail(\''.$col.'\',\'ALWAYS\');" type="radio" dojoType="dijit.form.RadioButton" '.(($val=='ALWAYS')?'checked':'').' name="'.$col.'Hidden" id="'.$col.'ALWAYS" value="ALWAYS" />';
        echo'       </td>';
        echo '      <td style="text-align:left;">';
        echo '        '.i18n('changeStatusAlways');
        echo '      </td>';
        echo '    </tr>';
        echo '</table>';
        echo '<input type="hidden" '.$name.' value="'.htmlEncode($val).'"  />';
      }else if (($col=='color' or (pq_substr($col,0,5)=='color' and pq_strlen($col)>5 and pq_strtoupper(pq_substr($col,5,1))==pq_substr($col,5,1) ) ) and $dataType=='varchar' and $dataLength==7) {
        //remi
        // Draw a color selector ============================================== COLOR
        echo '<table class="generalColClass '.$col.'Class" style="'.$specificStyleWithoutCustom.'"><tr><td class="detail">';
        // BEGIN - ADD BY TABARY - TOOLTIP
//         echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        if ($included) {
          $nameColor=$classObj.'_'.$col;
        } else {
          $nameColor=$col;
        }
        $colorWidth = 32;
        $border=intval($colorWidth/15);
                                                                      // !! $name = "name=".$namecolor."; !!
        //true input val save
        echo '<input type="hidden" '.$name.' value="'.$val.'" />';
        if (!$readOnly) {
          $valPicker = ($val)?$val:'#fefefe';
          //input view
          echo '<input type="color" id="detailColorPicker" name="detailColorPicker" onChange="dojo.byId('.$nameColor.').value = this.value;formChanged()" value="'.$valPicker.'" style="width:'.$colorWidth.'px;height:'.$colorWidth.'px; border-radius: 5px 5px 5px 5px; cursor: pointer; border-color: gray;"/>'; 
          echo '</td><td class="detail">';
          //the picker table ! display none !
          echo '<div id="'.'colorButton'.$nameColor.'" dojoType="dijit.form.DropDownButton"  ';
          if (isNewGui()) echo ' showlabel="false" iconClass="colorSelector" style="position:relative; height:25px;width:47px;top:0px;display:none;">';
          else echo ' showlabel="false" iconClass="colorSelector" style="position:relative;top:-2px;height:19px">';
          echo '  <span>'.i18n('selectColor').'</span>';
          echo '  <div dojoType="dijit.ColorPalette" id="colorPicker'.$nameColor.'" >';
          echo '    <script type="dojo/method" event="onChange" >';
          echo '      var fldView=dojo.byId("detailColorPicker");';
          echo '      var fldValue=dojo.byId("'.$nameColor.'");';
          echo '      fldView.value=this.value;';
          echo '      fldValue.value=this.value;';
          echo '      formChanged();';
          echo '    </script>';
          echo '  </div>';
          echo '</div>';
        } else {
          echo '<div class="colorDisplay" readonly tabindex="-1" ';
          echo '  value="'.htmlEncode($val).'" ';
          echo '  style="width:25px; height:20px; border: 1px solid #777777;';
          echo ' color: '.$val.'; ';
          echo ' background-color: '.$val.';"';
          echo ' >';
          echo '</div>';
        }
         echo '</td><td>';
        if (!$readOnly) {
          //reset color
          echo '<button id="resetColor'.$nameColor.'" dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton" style="min-width:80px;max-width:150px;margin:0px 5px;';
          echo ' title="'.i18n('helpResetColor').'" >';
          echo '<span>'.i18n('resetColor').'</span>';
          echo '<script type="dojo/connect" event="onClick" args="evt">';
          echo '      var fld=dojo.byId("'.$nameColor.'");';
          echo '      fld.value="";';
          echo '      var fld=dojo.byId("detailColorPicker");';
          echo '      fld.value="#fefefe";';
          echo '      formChanged();';
          echo '</script>';
          echo '</button>';
        }
//         echo '</td></tr></table>';
        echo '</td></tr></table>';
      } else if ($col=='durationSla') {
        // Draw a color selector ============================================== SLA as a duration
        echo '<div class="generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" style="width: 30px;'.$specificStyleWithoutCustom.'">';
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo '<div dojoType="dijit.form.TextBox" class="colorDisplay generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" type="text"  ';
        echo $name;
        echo $attributes;
        echo '  value="'.htmlEncode($val).'" ';
        echo '  style="width: 30px;'.$specificStyle.'"';
        echo ' >';
        echo '</div>';
        echo i18n("shortDay")."  ";
        echo '<div dojoType="dijit.form.TextBox" class="colorDisplay" type="text"  ';
        echo $attributes;
        echo '  value="'.htmlEncode($val).'" ';
        echo '  style="width: 30px; "';
        echo ' >';
        echo '</div>';
        echo i18n("shortHour")."  ";
        echo '<div dojoType="dijit.form.TextBox" class="colorDisplay" type="text"  ';
        echo $attributes;
        echo '  value="'.htmlEncode($val).'" ';
        echo '  style="width: 30px; "';
        echo ' >';
        echo '</div>';
        echo i18n("shortMinute")."  ";
        echo "</div>";
      } else if ($dataType=='date') {
        // Draw a date ======================================================== DATE
        if ($col=='creationDate' and ($val=='' or $val==null) and !$obj->id) {
          $val=date('Y-m-d');
        }
        $negative='';
        if (property_exists($obj, 'validatedEndDate') and $col=="plannedEndDate") {
          $negative=($obj->plannedEndDate and $obj->validatedEndDate and $obj->plannedEndDate>$obj->validatedEndDate)?'background-color: #FFAAAA !important;':'';
        }
        if (property_exists($obj, 'validatedStartDate') and property_exists($obj, 'idPlanningMode') and $col=="plannedStartDate" ) {
          $codePM=SqlList::getFieldFromId('PlanningMode', $obj->idPlanningMode, 'code');
          $negative='';
          if ($codePM=='START' and $obj->plannedStartDate<$obj->validatedStartDate) $negative='background-color: #FFAAAA !important;';
          if ($codePM=='STARR' and $obj->plannedStartDate!=$obj->validatedStartDate) $negative='background-color: #FFAAAA !important;';
        }
        
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo '<div dojoType="dijit.form.DateTextBox" ';
        echo $name;
        echo $attributes;
        if ($col=='validatedEndDate' and !$val and property_exists($obj,'inheritedEndDate') and $obj->inheritedEndDate) {
          $inheritedEndTitle=i18n('inheritedEndDate');
          if (property_exists($obj, 'inheritedEndSource') and $obj->inheritedEndSource) {
            $sourceParts=pq_explode('|', $obj->inheritedEndSource);
            $sourceReference=(isset($sourceParts[1]))?pq_explode('#', $sourceParts[1]):array();
            if (count($sourceParts)==2 and count($sourceReference)==2) {
              $sourceOriginKeys=array(
                  'SUCCESSOR'=>'Successor',
                  'PREDECESSOR'=>'Predecessor',
                  'PARENT'=>'Parent',
              );
              $sourceOrigin=pq_strtoupper(pq_trim($sourceParts[0]));
              $sourceClass=pq_trim($sourceReference[0]);
              $sourceId=pq_trim($sourceReference[1]);
              $sourceOriginKey=$sourceOriginKeys[$sourceOrigin]??$sourceOrigin;
              $formattedSource=lcfirst(i18n($sourceOriginKey)).' '.i18n($sourceClass).' #'.$sourceId;
              $inheritedEndTitle=i18n('inheritedEndDateWithSource', array($formattedSource));
            }
          }
          echo ' placeHolder="'.htmlFormatDate($obj->inheritedEndDate).'" title="'.htmlEncode($inheritedEndTitle).'" ';
          $negative=($obj->inheritedEndDate and $obj->plannedEndDate>$obj->inheritedEndDate)?'background-color: #FFE0EA !important;':'';
        }
        echo ' invalidMessage="'.i18n('messageInvalidDate').'"';
        echo autoClearDateTextbox($comboDetail);
        echo ' type="text" maxlength="'.$dataLength.'" ';
        if (sessionValueExists('browserLocaleDateFormatJs')) {
          $min='';
          if (pq_substr($col, -7)=="EndDate" and !$readOnly) {
            $start=pq_str_replace("EndDate", "StartDate", $col);
            if (property_exists($obj, $start)&&property_exists($obj, 'refType')&&$obj->refType!="Milestone") {
              $min=$obj->$start;
            } else {
              $start=pq_str_replace("EndDate", "EisDate", $col);
              if (property_exists($obj, $start)) {
                $min=$obj->$start;
              }
            }
            // Babynus - For test purpose
            if ($val and $val<$min) $val=$min;
            if ($min) echo ' dropDownDefaultValue="'.$min.'" ';
          }
          echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\', min:\''.$min.'\' }" ';
        }
        // PBER : add class noDownArrow to avoid arrow on planning view
        echo ' style="'.$negative.'width:'.$dateWidth.'px; text-align: center;'.$specificStyle.'" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class noDownArrow" ';
        echo ' value="'.htmlEncode($val).'" ';
        echo ' hasDownArrow="false" '; // If removed, also remove noDownArrow class
        echo ' >';
        echo $colScript;
        echo '</div>';
      } else if ($dataType=='datetime') {
        // Draw a date ======================================================== DATETIME
        $val=convertServerTimeToUserTimezone($val);
        if (pq_strlen($val>11)) {
          $valDate=pq_substr($val, 0, 10);
          $valTime=pq_substr($val, 11);
        } else {
          $valDate=$val;
          $valTime='';
        }
        if ($col=='creationDateTime' and ($val=='' or $val==null) and !$obj->id) {
          $valDate=date('Y-m-d');
          $valTime=date("H:i");
        }
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo '<div dojoType="dijit.form.DateTextBox" ';
        echo $name;
        echo $attributes;
        echo ' invalidMessage="'.i18n('messageInvalidDate').'"';
        echo ' type="text" maxlength="10" ';
        if (sessionValueExists('browserLocaleDateFormatJs')) {
          echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
        }
        echo ' style="width:'.$dateWidth.'px; text-align: center;'.$specificStyle.'" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" ';
        echo ' value="'.$valDate.'" ';
        echo ' hasDownArrow="false" ';
        echo ' >';
        echo $colScript;
        echo '</div>';
        $fmtDT=($classObj=="Audit"&&pq_strlen($valTime)>5&&pq_strpos($attributes, 'readonly')!==false)?'text':'time'; // valTime=pq_substr($valTime,0,5);
        $hideHoursTicketDueDates='NO';
        if (($col=='initialDueDateTime' || $col=='actualDueDateTime')) $hideHoursTicketDueDates=Parameter::getGlobalParameter('hideHoursTicketDueDates');
        if ($hideHoursTicketDueDates!='YES'){
          echo '<div dojoType="dijit.form.'.(($fmtDT=='time')?'Time':'').'TextBox" ';
          echo $nameBis;
          echo $attributes;
          echo ' invalidMessage="'.i18n('messageInvalidTime').'"';
          echo ' type="text" maxlength="8" ';
          if (sessionValueExists('browserLocaleTimeFormat')) {
            echo ' constraints="{timePattern:\''.getSessionValue('browserLocaleTimeFormat').'\'}" ';
          }
          // echo ' constraints="{datePattern:\'yy-MM-dd\'}" ';
          echo ' style="width:45px; text-align: center;'.$specificStyle.'" class="input '.(($isRequired)?'required':'').'" ';
          echo ' value="'.(($fmtDT=='time')?'T':'').$valTime.'" ';
          echo ' hasDownArrow="false" ';
          echo ' >';
          echo $colScriptBis;
          echo '</div>';
        }
      } else if ($dataType=='time') {
        // Draw a date ======================================================== TIME
        $val=convertServerTimeToUserTimezone($val);
        if ($col=='creationTime' and ($val=='' or $val==null) and !$obj->id) {
          $val=date("H:i");
        }
        $fmtDT=($classObj=="Audit"&&pq_strlen($val)>5&&pq_strpos($attributes, 'readonly')!==false)?'text':'time'; // valTime=pq_substr($valTime,0,5);
                                                                                                            // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo '<div dojoType="dijit.form.'.(($fmtDT=='time')?'Time':'').'TextBox" ';
        echo $name;
        echo $attributes;
        echo ' invalidMessage="'.i18n('messageInvalidTime').'"';
        echo ' type="text" maxlength="'.$dataLength.'" ';
        if (sessionValueExists('browserLocaleTimeFormat')) {
          echo ' constraints="{timePattern:\''.getSessionValue('browserLocaleTimeFormat').'\'}" ';
        }
        // echo ' constraints="{datePattern:\'yy-MM-dd\'}" ';
        echo ' style="width:'.(($fmtDT=='time')?'60':'65').'px; text-align: center;'.$specificStyle.'" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" ';
        echo ' value="'.(($fmtDT=='time')?'T':'').$val.'" ';
        echo ' hasDownArrow="false" ';
        echo ' >';
        echo $colScript;
        echo '</div>';
      } else if ($dataType=='int' and $dataLength==1) {
        if ($col=='cancelled' or $col=='solved') echo "&nbsp;&nbsp;&nbsp;";
        // Draw a boolean (as a checkbox ====================================== BOOLEAN
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode, 'after');
        // END - ADD BY TABARY - TOOLTIP
        echo '<div dojoType="dijit.form.CheckBox" type="checkbox" ';
        echo $name;
        echo ' class="greyCheck generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class"';
        echo $attributes;
        echo ' style="'.$specificStyle.';'.((isNewGui())?'':'').'" ';
        // echo ' value="' . $col . '" ' ;
        if ($val!='0' and !$val==null) {
          echo 'checked';
        }
        echo ' >';
        echo $colScript;
        if (!pq_strpos('formChanged()', $colScript)) {
          echo '<script type="dojo/connect" event="onChange" args="evt">';
          echo '    formChanged();';
          echo '</script>';
        }
        echo '</div>';
        // BEGIN - REPLACE BY TABARY - USE isForeignKey GENERIC FUNCTION
      } else if (isForeignKey($col, $obj) or $col=="hatchPattern") {
        // } else if (pq_substr($col, 0, 2) == 'id' and $dataType == 'int' and pq_strlen($col) > 2 and pq_substr($col, 2, 1) == pq_strtoupper(pq_substr($col, 2, 1))) {
        // END - REPLACE BY TABARY - USE isForeignKey GENERIC FUNCTION
        // Draw a reference to another object (as combo box) ================== IDxxxxx => ComboBox (as a FilteringSelect)
        $displayComboButtonCol=$displayComboButton;
        $displayDirectAccessButton=true;
        $canCreateCol=false;
        $canListCol=false;
        //if ($comboDetail or pq_strpos($attributes, 'readonly')!==false) {
        if ($comboDetail) {
          $displayComboButtonCol=false; 
        }
        if (pq_strpos($obj->getFieldAttributes($col), 'nocombo')!==false) {
          $displayComboButtonCol=false;
          $displayDirectAccessButton=false;
        }
        if ($displayComboButtonCol or $displayDirectAccessButton) {
          // BEGIN - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
          $colWithoutAlias=foreignKeyWithoutAlias($col);
          $idMenu='menu'.pq_substr($colWithoutAlias, 2);
          $comboClass=pq_substr($colWithoutAlias, 2);
          // $idMenu='menu' . pq_substr($col, 2);
          // $comboClass=pq_substr($col, 2);
          // END - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
          if ($col=="idResourceSelect" or ($col=="idResource" and $classObj=='Assignment')) {
            $idMenu='menuResource';
            $comboClass='ResourceAll';            
          } else if ($col=='idAccountable' or $col=='idResponsible') {
            $idMenu='menuResource';
            $comboClass='Resource';
          } else if ($col=='idAffectable') {
            $idMenu='menuResource';
            $comboClass='Affectable';
          } else if ($col=='idSponsor' and get_class($obj)=='Project'){
            $idMenu='menuProject';
            $comboClass='Contact';
          } else if ($col=='idVersion' and get_class($obj)=='TestCase' ){
            $idMenu='menuProductVersion';
            $comboClass='ProductVersion';
          } else if ($col=='idVersion' and get_class($obj)=='TestSession' ){
            $idMenu='menuProductVersion';
            $comboClass='ProductVersion';
          } else if (pq_substr($col, -14)=="ProductVersion") {
            $idMenu='menuProductVersion';
            $comboClass='ProductVersion';
          } else if (pq_substr($col, -16)=="ComponentVersion") {
            $idMenu='menuComponentVersion';
            $comboClass='ComponentVersion';
          } else if ($col=='idBudgetItem') {
            $idMenu='menuBudget';
          }else if ($col=='idContactContract' and get_class($obj)=='SupplierContract') {
             $idMenu='menuSupplierContract';
             $comboClass='Contact';
          }else if ($col=='idContactContract' and get_class($obj)=='ClientContract') {
             $idMenu='menuClientContract';
             $comboClass='Contact';
          }else if ($col=='idContact' and Parameter::getGlobalParameter('requestorLimitToContact')!="YES") {
            //$idMenu='menuClientContract';
            $comboClass='Affectable';
          }else if ($col=='idSituation') {
            $refType = get_class($obj);
            if ($refType=='CallForTender' or $refType=='Tender' or $refType=='ProviderOrder' or $refType=='ProviderBill') {
              $idMenu='menuProjectSituationExpense';
              $comboClass='ProjectSituationExpense';
            }else{
              $idMenu='menuProjectSituationIncome';
              $comboClass='ProjectSituationIncome';
            }
          }
          $menu=SqlElement::getSingleSqlElementFromCriteria('Menu', array('name'=>$idMenu));
          $crit=array();
          $crit['idProfile']=$profile;
          $crit['idMenu']=$menu->id;
          $habil=SqlElement::getSingleSqlElementFromCriteria('Habilitation', $crit);
          if ($habil and $habil->allowAccess) {
            $accessRight=SqlElement::getSingleSqlElementFromCriteria('AccessRight', array(
                'idMenu'=>$menu->id, 
                'idProfile'=>$profile));
            if ($accessRight) {
              $accessProfile=new AccessProfileAll($accessRight->idAccessProfile);
              if ($accessProfile) {
                $accessScope=new AccessScope($accessProfile->idAccessScopeCreate);
                if ($accessScope and $accessScope->accessCode!='NO') {
                  $canCreateCol=true;
                }
                $accessScope=new AccessScope($accessProfile->idAccessScopeRead);
                if ($accessScope and $accessScope->accessCode!='NO') {
                  $canListCol=true;
                }
              }
            }
            // ADD BY Marc TABARY - 2017-02-22 - ORGANIZATION PARENT
            // Special case for Organization Parent - Can access to parent only if the user is link
            // directly (idOrganization) to the parent or on one of the parent's of the parent organization
            if ($col=='idOrganization' and $val) {
              $orga=new Organization();
              $listOrga=$orga->getUserOrganizationsListAsArray();
              if (!pq_array_key_exists($val, $listOrga)) {
                $displayComboButtonCol=false;
                $displayDirectAccessButton=false;
              }
            }
            // END ADD BY Marc TABARY - 2017-02-22 - ORGANIZATION PARENT
            
            // Special case for idResource, idLocker, idAuthor, idResponsive, idAccountable, idEmployee
            // Don't see or access to the resource if is not visible for the user connected (respect of HabilitationOther - teamOrga)
            // Add idEmployee for LEAVE SYSTEM
            $arrayIdSpecial=array('idResource', 'idLocker', 'idAuthor', 'idResponsible', 'idAccountable', 'idEmployee');
            if (in_array($col, $arrayIdSpecial) or pq_substr($col,-12)=='__idResource') {
// MTY - LEAVE SYSTEM
              if ($col=="idEmployee") {
              // Limits list to Resource with isEmployee = 1  
                $idList = getUserVisibleResourcesList(true, "List",'', false, true);
              } else {
                $idList=getUserVisibleResourcesList(true, "List");
              }
// MTY - LEAVE SYSTEM  
              if ($val and !pq_array_key_exists($val, $idList)) {
                $displayComboButtonCol=false;
                $displayDirectAccessButton=false;
              }
            }
          } else {
            $displayComboButtonCol=false;
            $displayDirectAccessButton=false;
          }
          if (SqlElement::is_subclass_of($comboClass, 'PlgCustomList')) {
            //$displayComboButtonCol=false;
            //$displayDirectAccessButton=false;
            $canListCol=false; // PBER #8678
            $menu=SqlElement::getSingleSqlElementFromCriteria('Menu', array('name'=>'menuScreenCustomization'));
            $crit=array();
            $crit['idProfile']=$user->idProfile;
            $crit['idMenu']=$menu->id;
            $habil=SqlElement::getSingleSqlElementFromCriteria('Habilitation', $crit);
            if ($habil and $habil->allowAccess) {
              $canListCol=true; // PBER #8678
              $canCreateCol=true;
              $displayComboButtonCol= $displayComboButton;
            }
          }
        }
        if ($col=="idSituation" or $col=='idWorkCommand') {
          $canListCol=false;
        }
        if (pq_strpos($attributes, 'readonly')!==false) {
          $canCreateCol=false;
          //$canListCol=false;
        }
        if ($obj->isAttributeSetToField($col, 'canSearchForAll')) {
          $displayComboButtonCol='force';
          //$displayDirectAccessButton=false;
        }
        if ($col=='idProfile' and !$obj->id and !$val and ($classObj=='Resource' or $classObj=='User')) { // set default
          $val=Parameter::getGlobalParameter('defaultProfile');
        }
        if ($col=='idProject') {
          if ($obj->id==null) {
            if(pq_strpos(getSessionValue('project'), ",") != null){
            	$projSelected=new Project();
            }else{
              $projSelected=new Project(getSessionValue('project'));
            }
            if ((sessionValueExists('project') and !$obj->$col) and $projSelected->idle!='1') {
              if(pq_strpos(getSessionValue('project'), ",") != null){
              	$val='*';
              }else{
                $val=getSessionValue('project');
              }
            }
            $accessRight=securityGetAccessRight('menu'.$classObj, 'create'); // TODO : study use of this variable...
          } else {
            $accessRight=securityGetAccessRight('menu'.$classObj, 'update'); // TODO : study use of this variable...
          }
          if (securityGetAccessRight('menu'.$classObj, 'read')=='PRO' and $classObj!='Project') {
            $isRequired=true; // TODO : study condition above : why security for 'read'', why not for project, ...
          }
          $controlRightsTable=$user->getAccessControlRights();
          if (isset($controlRightsTable['menu'.$classObj])) {
            $controlRights=$controlRightsTable['menu'.$classObj];
            if ($classObj=='Project' and $controlRights["create"]!="ALL" and $controlRights["create"]!="PRO") {
              $isRequired=true;
            }
          }
        }
        $critFld=null;
        $critVal=null;
        $valStore='';
        if ($col=='idResource' or pq_substr($col,-12)=='__idResource' or $col=='idAffectable' or $col=="idAccountable" 
         or $col=='idContact'  or $col=='idUser' or $col=='idProjectExpense' or $col=='idProjectExpense'
         or $col=='idActivity' or $col=='idMilestone' or $col=='idTicket' or $col=='idTestCase' or $col=='idRequirement' 
         or $col=='idProduct' or $col=='idComponent' or $col=='idProductOrComponent' 
         or $col=='idProductVersion' or $col=='idComponentVersion' or $col=='idVersion' or $col=='idOriginalVersion' or $col=='idTargetVersion' 
         or $col=='idOriginalProductVersion' or $col=='idTargetProductVersion' or $col=='idOriginalComponentVersion' or $col=='idTargetComponentVersion' 
         or $col==SqlElement::getTypeName($classObj) or $col=='idSprint' or $col=='idEpic') {
          if ($col=='idContact' and property_exists($obj, 'idClient') and $obj->idClient) {
            $critFld='idClient';
            $critVal=$obj->idClient;
          } else if ($col=='idContact' and property_exists($obj, 'idProvider') and $obj->idProvider) {
            $critFld='idProvider';
            $critVal=$obj->idProvider;
          } else if (property_exists($obj, 'idProject') and get_class($obj)!='Project' and get_class($obj)!='Affectation') {
            //gautier #2620
            if ($obj->idProject) {
              $critFld='idProject';
              $critVal=$obj->idProject;
            } else if ($obj->isAttributeSetToField('idProject', 'required') or (sessionValueExists('project') and getSessionValue('project')!='*')) {
              if ($defaultProject) {
                $critFld='idProject';
                $critVal=$defaultProject;
              }
            }
          }
        } 
        if ($col=='idDocumentDirectory' and ! $obj->id and $defaultProject) {
          $obj->idProject=$defaultProject;
          $critFld=null;
        }
// MTY - LEAVE SYSTEM
        // Restrict list to Employee (isEmployee=1) if col is idEmployee
        if ($col=="idEmployee") {
            $critFld="isEmployee";
            $critVal="1";
        } 
// MTY - LEAVE SYSTEM
        
        if ($col=='idComponent' and isset($obj->idProduct)) {
          $critFld='idProduct';
          $critVal=$obj->idProduct;
        }
        // if version and idProduct exists and is set : criteria is product
        if ((isset($obj->idProduct) or isset($obj->idComponent) or isset($obj->idProductOrComponent)) and ($col=='idVersion' or $col=='idProductVersion' or $col=='idComponentVersion' or $col=='idOriginalVersion' or $col=='idTargetVersion' or $col=='idOriginalProductVersion' or $col=='idTargetProductVersion' or $col=='idOriginalComponentVersion' or $col=='idTargetComponentVersion' or $col=='idTestCase' or ($col=='idRequirement' and (isset($obj->idProductOrComponent) or isset($obj->idProduct))))) {
          if (isset($obj->idProduct) and ($col=='idVersion' or $col=='idTargetVersion' or $col=='idProductVersion' or $col=='idOriginalProductVersion' or $col=='idTargetProductVersion' or $col=='idRequirement')) {
            if ($critFld=='idProject') {
              $critFld=array($critFld,'idProduct');
              $critVal=array($critVal,$obj->idProduct);
            } else {
              $critFld='idProduct';
              $critVal=$obj->idProduct;
            }
          } else if (isset($obj->idComponent) and ($col=='idComponentVersion' or $col=='idOriginalComponentVersion' or $col=='idTargetComponentVersion')) {
            $critFld='idProduct';
            $critVal=$obj->idComponent;
          } else if (isset($obj->idProductOrComponent)) {
            $critFld='idProduct';
            $critVal=$obj->idProductOrComponent;
          }
        }
        if (pq_substr($col, -16)=='ComponentVersion') {
          $prodVers=pq_str_replace('Component', 'Product', $col);
          if (property_exists($obj, $prodVers) and $obj->$prodVers) {
            $critFld='idProductVersion';
            $critVal=$obj->$prodVers;
          }
          if (property_exists($obj, 'idComponent') and $obj->idComponent) {
            $critFld=array($critFld, 'idComponent');
            $critVal=array($critVal, $obj->idComponent);
          }
        }
        if (get_class($obj)=='IndicatorDefinition') {
          if ($col=='idIndicator') {
            $critFld='idIndicatorable';
            $critVal=$obj->idIndicatorable;
          }
          if ($col=='idType') {
            $critFld='scope';
            $critVal=SqlList::getNameFromId('Indicatorable', $obj->idIndicatorable);
          }
          if ($col=='idWarningDelayUnit' or $col=='idAlertDelayUnit') {
            $critFld='idIndicator';
            $critVal=$obj->idIndicator;
          }
        }
        if (get_class($obj)=='VotingUseRule' or get_class($obj)=='VotingUseRulePerProject') {
          if ($col=='idType') {
            $critFld='scope';
            //$critVal=SqlList::getNameFromId('Type', $obj->refType, false);
            $critVal=($obj->refType)?$obj->refType:'Ticket';
          }
        }
        if (get_class($obj)=='PredefinedNote') {
          if ($col=='idType') {
            $critFld='scope';
            $critVal=SqlList::getNameFromId('Textable', $obj->idTextable, false);
          }
        }
        if (get_class($obj)=='PredefinedSituation') {
        	if ($col=='idType') {
        		$critFld='idSituationable';
        		$critVal=SqlList::getNameFromId('Situationable', $obj->idSituationable, false);
        	}
        }
        if (get_class($obj)=='StatusMail' or property_exists($obj,'idMailable')) {
          if ($col=='idType') {
            $critFld='scope';
            $critVal=SqlList::getNameFromId('Mailable', $obj->idMailable, false);
            // BEGIN add Gmartin Ticket #157
          } else if ($col=='idEmailTemplate') {
            $critFld[]='idMailable';
            $critVal[]=$obj->idMailable;
            $critFld[]='idType';
            $critVal[]=$obj->idType;
          }
        }
        if (get_class($obj)=='EmailTemplate') {
          if ($col=='idType') {
            $critFld='scope';
            $critVal=SqlList::getNameFromId('Mailable', $obj->idMailable, false);
          }
        }
        // END add Gmartin
        if (get_class($obj)=='ChecklistDefinition'||get_class($obj)=='JoblistDefinition') { // Can be replaced by a specific table Joblistable if needed
          if ($col=='idType') {
            $critFld='scope';
            $critVal=SqlList::getNameFromId('Checklistable', $obj->idChecklistable, false);
          }
        }
        // ADD by qCazelles - Business features
        if ($col=='idBusinessFeature') {
          $critFld='idProduct';
          $critVal=$obj->idProduct;
        }
        if($col=='idContactContract' ){
          if(get_class($obj)=='ClientContract'){
            $critFld='idClient';
            $critVal=$obj->idClient;
          }elseif (get_class($obj)=='SupplierContract') {
            $critFld='idProvider';
            $critVal=($obj->idProvider)?$obj->idProvider:'0';
          }
        }
        if ($col=='idProspectOrigin' and property_exists($obj,'idProspectionSource')) {
          $lst=SqlList::getList('ProspectionSource','id');
          $default=reset($lst);
          $critFld='idProspectionSource';
          $critVal=($obj->idProspectionSource)??$default;
        }
        // END ADD qCazelles
        
        if (SqlElement::is_a($obj, 'PlanningElement')) {
          $planningModeName='id'.$obj->refType.'PlanningMode';
          if ($col==$planningModeName and !$obj->id and $objType) {
            if (property_exists($objType, $planningModeName)) {
              $obj->$planningModeName=$objType->$planningModeName;
              $val=$obj->$planningModeName;
            }
          }
        }
        if (!isNewGui()) {
          if ($displayComboButtonCol) {
            if ($displayDirectAccessButton) {
              $fieldWidth-=50;
            } else {
              $fieldWidth-=30;
            }
          } else if ($displayDirectAccessButton) {
            $fieldWidth-=30;
          }
        } else {
        	if (pq_strpos($obj->getFieldAttributes($col), 'size1/3')!==false) {
        	  $fieldWidth-=10;
        	} else if (pq_strpos($obj->getFieldAttributes($col), 'size1/2')!==false) {
        	  $fieldWidth-=10;
        	} else if (($nobr_before or $nobr) and $fieldWidth>$mediumWidth) {
        	  $fieldWidth-=10;
        	} else {
        	  $fieldWidth-=10;
        	}
        }
        $hasOtherVersion=false;
        $versionType='';
        $otherVersion='';
        if ((pq_substr($col, 7)=='Version' and SqlElement::is_a(pq_substr($col, 2), 'Version')) or ($col=='idOriginalVersion' or $col=='idOriginalProductVersion' or $col=='idOriginalComponentVersion') or ($col=='idTargetVersion' or $col=='idTargetProductVersion' or $col=='idTargetComponentVersion')) {
          $versionType=pq_substr($col, 2);
          $otherVersion='_Other'.$versionType;
          if (isset($obj->$otherVersion) and !$obj->isAttributeSetToField($col, 'hidden') and !$obj->isAttributeSetToField($col, 'readonly') and !$readOnly and !$hide and $canUpdate and !$obj->idle) {
            $hasOtherVersion=true;
            $fieldWidth-=28;
          }
        }
        $hasOtherClient=false;
        $otherClient='';
        if ($col=='idClient') {
          $otherClient='_OtherClient';
          if (isset($obj->$otherClient) and !$obj->isAttributeSetToField($col, 'hidden') and !$obj->isAttributeSetToField($col, 'readonly') and !$readOnly and !$hide and $canUpdate and !$obj->idle) {
            $hasOtherClient=true;
            $fieldWidth-=28;
          }
          if(pq_trim(RequestHandler::getId('idClient')) != '')$val = RequestHandler::getId('idClient');
        }
        $showExtraButton=false;
// MTY - Forgot readonly in condition
        $buttonFieldWidth=0;        
        if (($col=='idStatus' or foreignKeyWithoutAlias($col)=='idResource' or foreignKeyWithoutAlias($col)=='idAccountable' or foreignKeyWithoutAlias($col)=='idResponsible') and !$readOnly) {
          if ((($col=='idStatus') or ((foreignKeyWithoutAlias($col)=='idResource' or foreignKeyWithoutAlias($col)=='idAffectable' or foreignKeyWithoutAlias($col)=='idAccountable' or foreignKeyWithoutAlias($col)=='idResponsible') and $user->isResource and $user->id!=$val and $obj->id and $classObj!='Affectation')) and $classObj!='Document' and $classObj!='StatusMail' and $classObj!="TicketSimple" and $canUpdate) {
            if (!$readOnly) $showExtraButton=true;
            $fieldWidth=round($fieldWidth/2)-5;
            $buttonFieldWidth=$fieldWidth;
          }
        }
        
        // BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
        if (($col=='idStatusNotification' and $classObj!='StatusNotification'  and !$readOnly) or $col=='idProgressMode' or $col=='idWeightMode' or $col=='idRevenueMode') {
          if (!$readOnly) $showExtraButton=true;
          $fieldWidth=round($fieldWidth/2)-23;
          if($fieldWidth<85)$fieldWidth=85;
        }
        if($col =='idResource' and $classObj == 'LocalizationTranslator'){
            $showExtraButton=false; // do not show assign to me - hide extra button for LocalizationTranslator object
        }
        // END - ADD BY TABARY - NOTIFICATION SYSTEM
        $maxButtonWidth=max(min(2*$fieldWidth/3,350),250);
        if ($buttonFieldWidth>$maxButtonWidth) {
          $fieldWidth=$fieldWidth+$buttonFieldWidth-$maxButtonWidth;
          $buttonFieldWidth=$maxButtonWidth;
        }
        if($col == 'idMacroTicketStatus'){
          if(isNewGui()){
            echo '<input id="'.$col.'" name="'.$col.'" type="hidden" class="input '.(($isRequired)?'required':'').'" value="'.(($obj->idMacroTicketStatus)?$obj->idMacroTicketStatus:2).'"/>';
        	echo '<ul id="'.$col.'List" data-dojo-type="dojox/mobile/TabBar" data-dojo-props=\'barType:"segmentedControl"\' center="false">';
            	echo '<li id="isHandledStatus" onClick="dojo.byId(\''.$col.'\').value=\'1\';" data-dojo-type="dojox/mobile/TabBarButton" style="width: 80px !important;"';
            	if($obj->idMacroTicketStatus==1){
            		echo "data-dojo-props='selected:true'";
            	}
            	echo '>'.i18n('macroStatusHandled').'</li>';
            	echo '<li id="isDoneStatus" onClick="dojo.byId(\''.$col.'\').value=\'2\';" data-dojo-type="dojox/mobile/TabBarButton" style="width: 80px !important;"';
            	if($obj->idMacroTicketStatus==2 or !$obj->idMacroTicketStatus){
            		echo "data-dojo-props='selected:true'";
            	}
            	echo '>'.i18n('macroStatusDone').'</li>';
            	echo '<li  id="isIdleStatus" onClick="dojo.byId(\''.$col.'\').value=\'3\';" data-dojo-type="dojox/mobile/TabBarButton" style="width: 80px !important;"';
            	if($obj->idMacroTicketStatus==3){
            		echo "data-dojo-props='selected:true'";
            	}
            	echo '>'.i18n('macroStatusIdle').'</li>';
        	echo '</ul>';
          }else{
            echo '<table id="'.$col.'List">';
            echo '<tr><td>';
            echo ' <label for="isHandledStatus" class="dialogLabel " style="text-align:right;">'.i18n('colHandled').Tool::getDoublePoint().'</label>';
            echo ' <input type="radio" data-dojo-type="dijit/form/RadioButton" id="isHandledStatus" name="'.$col.'" value="1"'.(($obj->idMacroTicketStatus==1)?"checked":"").' style="padding-top: 7px;"/></td></tr>';
            echo '<tr><td>';
            echo ' <label for="isDoneStatus" class="dialogLabel " style="text-align:right;">'.i18n('colDone').Tool::getDoublePoint().'</label>';
            echo ' <input type="radio" data-dojo-type="dijit/form/RadioButton" id="isDoneStatus" name="'.$col.'" value="2"'.(($obj->idMacroTicketStatus==2)?"checked":"").' style="padding-top: 7px;"/></td></tr>';
            echo '<tr><td>';
            echo ' <label for="isIdleStatus" class="dialogLabel " style="text-align:right;">'.i18n('colIdle').Tool::getDoublePoint().'</label>';
            echo ' <input type="radio" data-dojo-type="dijit/form/RadioButton" id="isIdleStatus" name="'.$col.'" value="3"'.(($obj->idMacroTicketStatus==3)?"checked":"").' style="padding-top: 7px;"/></td>';
            echo '</tr></table>';
          }
        }else if($col=="hatchPattern") {
          echo '<div dojoType="dijit.form.Select" class="input generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" ';
          echo '  style="width: 70px;'.$specificStyle.'"';
          echo ' labelType="html" spanLabel=true  ';
          echo $name;
          echo $attributes;
          echo $valStore;
          echo autoOpenFilteringSelect($comboDetail);
          echo ' value="'.$val.'">';
          echo '<span value=" "></span>' ;
          echo '<span value="slashDark"><img src="images/hatchPatternSlashDark.png" /></span>' ;
          echo '<span value="backslashDark"><img src="images/hatchPatternBackslashDark.png" /></span>' ;
          echo '<span value="verticalDark"><img src="images/hatchPatternVerticalDark.png" /></span>' ;
          echo '<span value="slashDarkLarge"><img src="images/hatchPatternSlashDarkLarge.png" /></span>' ;
          echo '<span value="backslashDarkLarge"><img src="images/hatchPatternBackslashDarkLarge.png" /></span>' ;
          echo '<span value="verticalDarkLarge"><img src="images/hatchPatternVerticalDarkLarge.png" /></span>' ;
          echo '<span value="slash"><img src="images/hatchPatternSlash.png" /></span>' ;
          echo '<span value="backslash"><img src="images/hatchPatternBackslash.png" /></span>' ;
          echo '<span value="vertical"><img src="images/hatchPatternVertical.png" /></span>' ;
          echo '<span value="slashLarge"><img src="images/hatchPatternSlashLarge.png" /></span>' ;
          echo '<span value="backslashLarge"><img src="images/hatchPatternBackslashLarge.png" /></span>' ;
          echo '<span value="verticalLarge"><img src="images/hatchPatternVerticalLarge.png" /></span>' ;
          echo '</div>';
        }else{
          echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
          echo '<select dojoType="dijit.form.FilteringSelect" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" ';
//           if($col=="hatchPattern") {
//             $fieldWidth=$smallWidth;
//             echo ' labelType="html"   ';
//           }
          echo '  style="width: '.($fieldWidth).'px;'.$specificStyle.'"';
          if ($col=='idBusinessFeature' or $col=='idProject' or $col=='idSkill' or $col=='idOrganization' or $col=='idBudgetItem') echo 'data-dojo-props="queryExpr: \'*${0}*\', autoComplete:false"';
          echo $name;
          echo $attributes;
          echo $valStore;
          echo autoOpenFilteringSelect($comboDetail);
          if (! $displayComboButtonCol) $canListCol=false;
          if (isNewGui() and !$comboDetail and $canListCol) echo ' onmouseover="showActionSelect(\''.$comboClass.'\',\''.$val.'\',\''.$fieldId.'\','.(($canCreateCol)?'true':'false').','.(($canUpdate)?'true':'false').');"';
          if (isNewGui() and !$comboDetail and $canListCol) echo ' onmouseout="hideActionSelect(\''.$comboClass.'\',\''.$val.'\',\''.$fieldId.'\');"';
          if (isNewGui() and !$comboDetail and $canListCol) echo ' onfocus="hideActionSelect(\''.$comboClass.'\',\''.$val.'\',\''.$fieldId.'\');"';
          echo ' >';
          if ($isRequired and $obj->isAttributeSetToField($col, 'doNotAutoFill')) {
            echo '<option value=" " ></option>';
          }
          if ($classObj=='IndividualExpense' and $col=='idResource' and securityGetAccessRight('menuIndividualExpense', 'read', $obj, $user)=='OWN') {
            $next=htmlDrawOptionForReference($col, $val, $obj, $isRequired, 'id', $user->id);
          }else if (($classObj=='SupplierContract' or $classObj=='ClientContract') and $col=='idContactContract' or $col=='idUnitContract' or $col=='idUnitNotice') {
            if($col=='idUnitContract' or $col=='idUnitNotice'){
              $next=htmlDrawOptionForReference($col, $val, $obj,true, $critFld, $critVal);
            }else{
              $next=htmlDrawOptionForReference($col, $val, $obj, $isRequired, $critFld, $critVal);
            }
          }else if($col=='idSituation'){
            $next=htmlDrawOptionForReference($col, $val, $obj, $isRequired, $critFld, $critVal);
            $projSituation = SqlElement::getSingleSqlElementFromCriteria('ProjectSituation', array('idProject'=>$obj->idProject));
            $val = $projSituation->id;
          }else if (($classObj=='ActivityPlanningElement' or $classObj=='ProjectPlanningElement') and ($col=='idWeightMode' or $col=='idProgressMode' or $col=='idRevenueMode')) {
            $next=htmlDrawOptionForReference($col, $val, $obj,true, $critFld, $critVal);
          }else {
            if ($col=='idResource' and $classObj=='Assignment') $col='idResourceAll';
            if (Parameter::getGlobalParameter('requestorLimitToContact')!="YES"){
              if ($col=='idContact') $col='idAffectable';
            }
            if ($col=='idRole' and $classObj=='Assignment' and  Parameter::getGlobalParameter('selectFonction')=="YES"){
              $critFld = 'fromAssignementForIdRole';
              $critVal = $obj->idResource ? $obj->idResource : $critVal;
            }
            $next=htmlDrawOptionForReference($col, $val, $obj, $isRequired, $critFld, $critVal);
          }
          if ($col=='idProduct' and !$obj->id and $obj->isAttributeSetToField($col, 'required')) $obj->idProduct=$next;
          echo $colScript;
          echo '</select>';
        }
        
        if (isNewGui() and !$comboDetail and $canListCol) echo '<span style="width:1px;position:relative;">';
        if (isNewGui() and !$comboDetail and $canListCol) echo '<div id="toolbar_'.$fieldId.'" class="fade-in dijitTextBox toolbarForSelect" style=""';
        if (isNewGui() and !$comboDetail and $canListCol) echo ' onmouseover="showActionSelect(\''.pq_substr($col,2).'\',\''.$val.'\',\''.$fieldId.'\');"';
        if (isNewGui() and !$comboDetail and $canListCol) echo ' onmouseout="hideActionSelect(\''.pq_substr($col,2).'\',\''.$val.'\',\''.$fieldId.'\');"';
        if (isNewGui() and !$comboDetail and $canListCol) echo '>...</div>';
        if (isNewGui() and !$comboDetail and $canListCol) echo '</span>';
        if ($displayDirectAccessButton and ! isNewGui()) {
          echo '<div id="'.$col.'ButtonGoto" ';
          echo ' title="'.i18n('showDirectAccess').'" style="float:right;margin-right:3px;'.$specificStyleWithoutCustom.'"';
          echo ' class="roundedButton  generalColClass '.$col.'Class">';
          echo '<div class="iconGoto iconSize16" ';
          $jsFunction="var sel=dijit.byId('$fieldId');"."if (sel && trim(sel.get('value'))) {"." gotoElement('".$comboClass."','$val');"."} else {"." showAlert(i18n('cannotGoto'));"."}";
          echo ' onclick="'.$jsFunction.'"';
          echo '></div>';
          echo '</div>';
        }
        if ($displayComboButtonCol and !isNewGui()) {
          echo '<div id="'.$col.'ButtonDetail" onmouseleave="hideIconViewSubMenu(\''.$col.'\');"';
          echo ' title="'.i18n('showDetail').'" style="float:right;margin-right:3px;'.$specificStyleWithoutCustom.'"';
          echo ' class="roundedButton generalColClass '.$col.'Class">';
          
          if (isNewGui()) {
            echo '<div class="iconHideStream22 iconHideStream iconSize22"  style="opacity:40%;margin-top:5px;margin-left:-10px;"';
            echo ' onMouseOver="event.preventDefault();showIconViewSubMenu(\''.$col.'\');"></div>';
          } else {
            echo '<div class="iconView iconSize16 imageColorNewGui" ';
            echo ' onclick="showDetail(\''.$col.'\','.(($canCreateCol)?1:0).',\''.$comboClass.'\',false,null,'.(($obj->isAttributeSetToField($col, 'canSearchForAll'))?'true':'false').')"';
            echo 'oncontextmenu="event.preventDefault();showIconViewSubMenu(\''.$col.'\');"></div>';
          }
          echo '</div>';
          echo '<div id="'.$col.'IconViewSubMenu" name="'.$col.'IconViewSubMenu" style="height:auto;overflow-y:auto;position:absolute;z-index: 999999999;display:none;width:160px;background-color:white;border:1px solid grey;"
                onmouseleave="dojo.byId(\''.$col.'IconViewSubMenu\').style.display=\'none\';" onmouseenter="dojo.byId(\''.$col.'IconViewSubMenu\').style.display=\'block\';clearTimeout(hideIconViewSubMenuTimeOut);">';
          echo  '<div id="'.$col.'SubViewItem" name="subViewItem" onClick="showDetail(\''.$col.'\','.(($canCreateCol)?1:0).',\''.$comboClass.'\',false,null,false);" style="cursor:pointer;">';
          echo '  <table style="width:100%">
                    <tr>
                      <td style="width:24px;padding-top:2px;padding-left:2px;">
                        <div class="iconFollowup16">&nbsp;</div>
                      </td>
                      <td class="emailHistorical"  style="vertical-align:middle;">'.i18n('showItem').'</td>
                    </tr>
                  </table>';
          echo '</div>';
          echo  '<div id="'.$col.'SubSearchItem" name="subSearchItem" onClick="showDetail(\''.$col.'\','.(($canCreateCol)?1:0).',\''.$comboClass.'\',false,null,true);" style="cursor:pointer;">';
          echo '  <table style="width:100%">
                    <tr>
                      <td style="width:24px;padding-top:2px;padding-left:2px;">
                        <div class="iconView iconSize16 imageColorNewGui">&nbsp;</div>
                      </td>
                      <td class="emailHistorical"  style="vertical-align:middle;">'.i18n('comboSearchButton').'</td>
                    </tr>
                  </table>';
          echo '</div>';
          echo  '<div id="'.$col.'SubAddItem" name="subAddItem" onClick="showDetail(\''.$col.'\','.(($canCreateCol)?1:0).',\''.$comboClass.'\',false,null,'.(($obj->isAttributeSetToField($col, 'canSearchForAll'))?'true':'false').');newDetailItem();" style="cursor:pointer;">';
          echo '  <table style="width:100%">
                    <tr>
                      <td style="width:24px;padding-top:2px;padding-left:2px;">
                        <div class="iconButtonAdd16">&nbsp;</div>
                      </td>
                      <td class="emailHistorical"  style="vertical-align:middle;">'.i18n('comboNewButton').'</td>
                    </tr>
                  </table>';
          echo '</div>';
          echo '</div>';
        }
        if ($hasOtherVersion) {
          if ($obj->id and $canUpdate) {
            echo '<a class="generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" style="float:right;'.((isNewGui())?'margin-right:7px;margin-top:6px;':'margin-right:5px;').$specificStyleWithoutCustom.'" ';
            echo ' onClick="addOtherVersion('."'".$versionType."'".');" ';
            echo ' title="'.i18n('otherVersionAdd').'">';
            if (isNewGui()) echo formatMediumButton('Add');
            else echo formatSmallButton('Add');
            echo '</a>';
          }
          if (count($obj->$otherVersion)>0) {
            drawOtherVersionFromObject($obj->$otherVersion, $obj, $versionType);
          }
        }
        if ($hasOtherClient) {
          if ($obj->id and $canUpdate) {
            echo '<a class="generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" style="float:right;'.((isNewGui())?'position:relative;right:5px;top:10px;':'margin-right:5px;').$specificStyleWithoutCustom.'" ';
            $canSeeClient=securityCheckDisplayMenu(null, 'Client');
            $directAccessClient=($canSeeClient)?'true':'false';
            //$directAccessClient='false';
            $paramDirectAccessClient=Parameter::getGlobalParameter("directAccessClient");
            if ($paramDirectAccessClient!==null and $paramDirectAccessClient!=='') $directAccessClient='false';
            echo ' onClick="addOtherClient('.$directAccessClient.');" ';
            echo ' title="'.i18n('otherClientAdd').'">';
            if (isNewGui()) echo formatMediumButton('Add');
            else echo formatSmallButton('Add');
            echo '</a>';
          }
          if (count($obj->$otherClient)>0) {
            drawOtherClientFromObject($obj->$otherClient, $obj);
          }
        }
        $newGuiStyle=(isNewGui())?'position:relative;margin-top:5px;margin-right:8px;height:25px;padding-left:5px;':'';
        $newGuiStyleImg=(isNewGui())?'top:4px;width:16px;height:16px':'';
        if ($col=='idStatus' and $next and $showExtraButton and $classObj!='InputMailboxTicket') {
          echo '<div class="roundedVisibleButton roundedButton generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class"';
          echo ' title="'.i18n("moveStatusTo", array(SqlList::getNameFromId('Status', $next))).'"';
          echo ' style="text-align:left;float:right;margin-right:10px; width:'.($buttonFieldWidth-5).'px;'.$newGuiStyle.$specificStyleWithoutCustom.'"';
          $saveFunction=($comboDetail)?'window.top.saveDetailItem();':'saveObject()';
          echo ' onClick="dijit.byId(\''.$fieldId.'\').set(\'value\','.$next.');setTimeout(\''.$saveFunction.'\',100);">';
          if (isNewGui()) echo '<img src="css/customIcons/new/iconMoveTo.svg" class="imageColorNewGui" style="position:relative;left:5px;top:2px;'.$newGuiStyleImg.'"/>';
          else echo '<img src="css/images/iconMoveTo.png" style="position:relative;left:5px;top:2px;"/>';
          echo '<div style="position:relative;top:-16px;left:25px;width:'.($buttonFieldWidth-30).'px">'.SqlList::getNameFromId('Status', $next).'</div>';
          echo '</div>';
        }
        // BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
        if ($col=='idStatusNotification' and $next and $showExtraButton) {
          echo '<div class="roundedVisibleButton roundedButton generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class"';
          echo ' title="'.i18n("moveStatusTo", array(SqlList::getNameFromId('StatusNotification', $next))).'"';
          echo ' style="text-align:left;float:right;margin-right:10px;width:'.($fieldWidth-5).'px;'.$newGuiStyle.$specificStyleWithoutCustom.'"';
          $saveFunction=($comboDetail)?'window.top.saveDetailItem();':'saveObject()';
          echo ' onClick="dijit.byId(\''.$fieldId.'\').set(\'value\','.$next.');setTimeout(\''.$saveFunction.'\',100);">';
          if (isNewGui()) echo '<img src="css/customIcons/new/iconMoveTo.svg" class="imageColorNewGui" style="position:relative;left:5px;top:2px;'.$newGuiStyleImg.'"/>';
          else echo '<img src="css/images/iconMoveTo.png" style="position:relative;left:5px;top:2px;"/>';
          echo '<div style="position:relative;top:-16px;left:25px;width:'.($fieldWidth-30).'px">'.i18n(SqlList::getNameFromId('StatusNotification', $next)).'</div>';
          echo '</div>';
        }
        // END - ADD BY TABARY - NOTIFICATION SYSTEM
        // BEGIN - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
        $colWithoutAlias=foreignKeyWithoutAlias($col);
        if (($colWithoutAlias=='idResource' or $colWithoutAlias=='idAffectable' or $colWithoutAlias=='idAccountable' or $colWithoutAlias=='idResponsible') and $next and $showExtraButton) {
          // if (($col == 'idResource' or $col == 'idAccountable' or $col == 'idResponsible') and $next and $showExtraButton) {
          // END - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
          // ADD BY Marc TABARY - 2017-03-09 - EXTRA BUTTON (Assign to me) IS VISIBLE EVEN IDLE=1
          if ($classObj=='Organization' and property_exists($obj, 'idle') and $obj->idle==1) {
            // exclusion
          } else {
            // END ADD BY Marc TABARY - 2017-03-09 - EXTRA BUTTON (Assign to me) IS VISIBLE EVEN IDLE=1
            echo '<div class="roundedVisibleButton roundedButton generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class"';
            echo ' title="'.i18n("assignToMe").'"';
            echo ' style="text-align:left;float:right;margin-right:10px; width:'.($buttonFieldWidth-5).'px;'.$newGuiStyle.$specificStyle.'"';
            $saveFunction=($comboDetail)?'window.top.saveDetailItem();':'saveObject()';
            echo ' onClick="dijit.byId(\''.$fieldId.'\').set(\'value\','.htmlEncode($user->id).');setTimeout(\''.$saveFunction.'\',100);"';
            echo '>';
            if (isNewGui()) echo '<img src="css/customIcons/new/iconMoveTo.svg" class="imageColorNewGui" style="position:relative;left:5px;top:2px;'.$newGuiStyleImg.'"/>';
            else echo '<img src="css/images/iconMoveTo.png" style="position:relative;left:5px;top:2px;"/>';
            echo '<div style="position:relative;top:-16px;left:25px;width:'.($buttonFieldWidth-30).'px">'.i18n('assignToMeShort').'</div>';
            echo '</div>';
          }
        }
      } else if (pq_strpos($obj->getFieldAttributes($col), 'display')!==false) {
        if (isNewGui()) echo "<table style='width:100%'><tr style='height:32px'><td>";
        echo '<div ';
        // echo ' class="display generalColClass input'.$col.'Class" style="'.$specificStyle.'width: '.$fieldWidth.'px;"';
        echo ' class="display generalColClass input'.$col.'Class" style="'.$specificStyle.';white-space:nowrap;"';
        if ($col=="wbs") echo ' title="'.htmlEncode($val).'"';
        echo ' >';
        
        if (pq_strpos($obj->getFieldAttributes($col), 'html')!==false) {
          echo $val;
        } else if ($dataType=='decimal' and SqlElement::isWork($col)) {
          if ($classObj=='WorkElement' or $classObj=='TokenDefinition' or $classObj=='Resource') {
            echo Work::displayImputationWithUnit($val);
          } else {
            echo Work::displayWorkWithUnit($val);
          }
        } else {
          echo htmlEncode($val);
        }
        if (!$print) {
          // BEGIN - ADD BY TABARY - TOOLTIP
          echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
          // END - ADD BY TABARY - TOOLTIP
          echo '<input type="hidden" '.$name.' value="'.htmlEncode($val).'" />';
        }
        if (SqlElement::isPct($col)) {
          echo '&nbsp;%';
        }
        echo '</div>';
        if (isNewGui()) echo "</td><td style='min-width:5px'>&nbsp;</td></tr></table>";
        // ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER
      } else if ($isSpinner and is_integer(intval($val))) {
        // Draw an integer as spinner ================================================ SPINNER
        $title=' title="'.$obj->getTitle($col).'"';
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo htmlDrawSpinner($col, $val, $obj->getSpinnerAttributes($col), $obj->getFieldAttributes($col), $name, $title, $smallWidth, $colScript);
        // END ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER
      } else if ($dataType=='int' or $dataType=='decimal') {
        // Draw a number field ================================================ NUMBER
        $colScript=($outMode!='pdf')?NumberFormatter52::completeKeyDownEvent($colScript):'';
        $isCost=false;
        $isAmount=false; // Amount will have 2 decimals
        $isWork=false;
        $isDuration=false;
        $isPercent=false;
        $isProgress=false;   
        $uo=false;
        if (SqlElement::is_a($obj, 'PlanningElement')) {
          if ($col=='priority' and !$obj->id and $objType) {
            if (property_exists($objType, 'priority')&&$objType->priority) {
              $obj->priority=$objType->priority;
              $val=$obj->priority;
            }
          }
        }
        if ($dataType=='decimal' and SqlElement::isAmount($col)) {
          $isCost=true;
          $fieldWidth=$smallWidth;
          if ( (pq_substr($col, -6)=='Amount' or pq_substr($col, -11)=='AmountLocal' or $col=='amount' or $col=='amountLocal') and ! SqlElement::is_a($obj, 'PlanningElement')) {
            $isAmount=true;
          }
        }
        if ($dataType=='decimal' AND (SqlElement::isWork($col) OR $col=='minimumThreshold') ){
          $isWork=true;
          $fieldWidth=$smallWidth;
        }
        if(Module::isModuleActive('moduleTechnicalProgress')){
          $isProgress=true;
          if($col=='unitToDeliver' or $col=='unitToRealise' or $col=='unitRealised' or $col=='unitWeight'){
            $uo=true;
          }
        }
        if ($dataType=='int' and (pq_substr($col, -8, 8)=='Duration')) {
          $isDuration=true;
          $fieldWidth=$smallWidth-25;
        }
        
        if ($dataType=='int' and (pq_substr($col, -9, 9)=='DurationY') or (pq_substr($col, -9, 9)=='DurationM')) {
          $isDuration=true;
          $fieldWidth=$smallWidth;
        }
        if( $dataType=='decimal' and $col=='duration' and $classObj=="TokenDefinition"){//
          $isWork=true;
          $fieldWidth=$smallWidth;
        }
        
        if (SqlElement::isPct($col)) {
          $isPercent=true;
          // ADD BY Marc TABARY - 2017-03-01 - DIM CORRECT Pct
          if (pq_substr($col, -3, 3)=='Pct' or pq_substr($col, -4, 4)=='Rate') {
            $fieldWidth=$smallWidth;
          }
          // END ADD BY Marc TABARY - 2017-03-01 - DIM CORRECT Pct
        }
        if ($isCost or $isWork or $isPercent or $uo ) {
          $possibleWidth=intval($widthPct)-80;
          if ($internalTable) {
            if (isNewGui()) $possibleWidth=round(($possibleWidth-25)/$internalTableCols, 0)-($internalTableCols*5);
            else $possibleWidth=round($possibleWidth/$internalTableCols, 0)-($internalTableCols*3);
          }
          $expected=100;
          //if ($isAmount) $expected+=20;
          if ($possibleWidth>$expected) {
            $fieldWidth=$expected;
          } else {
            $fieldWidth=$possibleWidth;
          }
        }
        if (($isWork or $isDuration or $isPercent) and $internalTable!=0 and $displayWidth<1600) {
          $fieldWidth-=12;
        }
        $spl=pq_explode(',', $dataLengthWithDec);
        $dec=0;
        if (count($spl)>1) {
          $dec=intval($spl[1]);
        }
        $ent=intval($spl[0])-$dec;
        $max=pq_substr('99999999999999999999', 0, $ent);
        if (($isCost or $isAmount) and $currencyPosition=='before') {
          $extraLocalClass=($obj->isLocal($col))?' localLabelClass ':'';
         	echo '<span class="generalColClass '.$col.'Class '.$extraLocalClass.'" style="display:inline-block;'.$specificStyleWithoutCustom.$labelStyle.';position:relative;top:1px">&nbsp'.$currency.'</span>';
        }
        // ADD BY Marc TABARY - 2017-03-01 - COLOR PERCENT WITH ATTRIBUTE 'alertOverXXXwarningOverXXXokUnderXXX'
        if ($isPercent and (pq_strpos($obj->getFieldAttributes($col), 'alertOver')!==false or pq_strpos($obj->getFieldAttributes($col), 'warningOver')!==false or pq_strpos($obj->getFieldAttributes($col), 'okUnder')!==false)) {
          // Note : reuse $negative (it's pratical)
          $negative='';
          $colAttributes=$obj->getFieldAttributes($col);
          // alertOver
          $posAWO=pq_strpos($colAttributes, 'alertOver');
          if ($posAWO and $val!==null) {
            $overValue=pq_substr($colAttributes, $posAWO+9, 3);
            if (is_numeric($overValue) and $val>intval($overValue)) {
              // Red
              $negative='background-color: #FFAAAA !important;';
            } else {
              // warningOver
              $posAWO=pq_strpos($colAttributes, 'warningOver');
              if ($posAWO) {
                $overValue=pq_substr($colAttributes, $posAWO+11, 3);
                if (is_numeric($overValue) and $val>intval($overValue)) {
                  // Orange
                  $negative='background-color: #FFBE00 !important;';
                } else {
                  // okUnder
                  $posAWO=pq_strpos($colAttributes, 'okUnder');
                  if ($posAWO) {
                    $overValue=pq_substr($colAttributes, $posAWO+7, 3);
                    if (is_numeric($overValue) and $val<intval($overValue)) {
                      // Green
                      $negative='background-color: #B5DE8E !important;';
                    }
                  }
                }
              }
            }
          }
        } else {
          $negative=(($isCost or $isWork) and $val<0)?'color: #AA0000 !important;':'';
        }
        // END ADD BY Marc TABARY - 2017-03-01 - COLOR PERCENT WITH ATTRIBUTE 'alertOverXXXwarningOverXXXokUnderXXX'
        // COMMENT BY Marc TABARY - 2017-03-01 - COLOR PERCENT WITH ATTRIBUTE 'alertOverXXXwarningOverXXXokUnderXXX'
        // $negative=(($isCost or $isWork) and $val<0)?'background-color: #FFAAAA !important;':'';
        // END COMMENT BY Marc TABARY - 2017-03-01 - COLOR PERCENT WITH ATTRIBUTE 'alertOverXXXwarningOverXXXokUnderXXX'
        if ($col=='workElementEstimatedWork' and property_exists($obj, 'assignedWork')) {
          $negative=($obj->workElementEstimatedWork>$obj->assignedWork)?'background-color: #FFAAAA !important;':'';
        }
        if ($col=='workElementLeftWork' and property_exists($obj, 'leftWork')) {
          $negative=($obj->workElementLeftWork>$obj->leftWork)?'background-color: #FFAAAA !important;':'';
        }
        if($col=='commandSum'){
          $negative=($obj->commandSum < $obj->revenue)?'background-color: #FFAAAA !important;':'';
        }
        if($col=='billSum'){
        	$negative=($obj->billSum > $obj->revenue)?'background-color: #FFAAAA !important;':'';
        }
        if (property_exists($obj, 'validatedDuration') and $col=="plannedDuration" and property_exists($obj, 'idActivityPlanningMode') 
        and ($obj->idActivityPlanningMode==8 or $obj->idActivityPlanningMode==14 or $obj->idActivityPlanningMode==27 or $obj->idActivityPlanningMode==28
             or $obj->idActivityPlanningMode==29 or $obj->idActivityPlanningMode==30)) {
          $negative=($obj->plannedDuration and $obj->validatedDuration and $obj->plannedDuration>$obj->validatedDuration)?'background-color: #FFAAAA !important;':'';
        }
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        // gautier #work
        echo '<div dojoType="dijit.form.NumberTextBox" ';
        echo $name;
        echo $attributes;
        // echo ' style="text-align:right; width: ' . $fieldWidth . 'px;' . $specificStyle . '" ';
        echo ' style="'.$negative.'width: '.$fieldWidth.'px;'.$specificStyle.'" ';
        // ADD BY Marc TABARY - 2017-03-06 - PATTERN FOR YEAR
        //gautier manualProgress
        if($isPercent and pq_strtolower(pq_substr($col, -8, 8))=='progress'){
          echo ' constraints="{min:0,max:100}")';
        }
        $isYear=false;
        if (pq_strpos(pq_strtolower($col), 'year')!==false) {
          $posYear=pq_strpos($col, 'Year');
          $first="uc";
          if ($posYear===false) {
            $posYear=pq_strpos($col, 'year');
            $first="lc";
          }
          if (pq_strlen($col)==4) {
            // Field year
            $isYear=true;
          } else if ($first="uc" and pq_strlen($col)==4+$posYear) {
            // Field xxxxxYear
            $isYear=true;
          } else if (pq_substr($col,$posYear,1)==pq_strtoupper(pq_substr($col,$posYear,1))) {
            // Field xxxxxYearYyyyy or yearYyyy
            $isYear=true;
          }
        }
        if ($isYear) {
          echo ' constraints="{min:2000,max:2100,pattern:\'###0\'}" ';
        } else if ($max) {
          //gautier min amount
          $arrayPossibleNegativeAmounts=array('update1Amount','update1FullAmount','update2Amount','update2FullAmount',
          		                                'update3Amount','update3FullAmount','update4Amount','update4FullAmount',
                                              'addUntaxedAmount','addFullAmount','availableAmount','availableFullAmount',
                                              'leftAmount','leftFullAmount','reserveAmount','totalLeftCost', 'totalPlannedCost',
          		                                'marginCost','marginWork','validatedCost',
                                              'untaxedAmount','taxAmount','fullAmount',
                                              'addUntaxedAmount','addTaxAmount','addFullAmount',
                                              'totalUntaxedAmount','totalTaxAmount','totalFullAmount',
                                              'realAmount','realTaxAmount','realFullAmount',
                                              'paymentAmount','paymentFeeAmount','paymentCreditAmount',
                                              'benefitValue'
                    );
          if ($obj->isAttributeSetToField($col, 'hidden') or $obj->isAttributeSetToField($col, 'readonly')) $arrayPossibleNegativeAmounts[]=$col;
          if(($isAmount or $isCost) and !in_array($col,$arrayPossibleNegativeAmounts) and $classObj != 'Bill'){
              echo ' constraints="{min:0,max:'.$max.(($isAmount)?',places:2':'').'}" ';
          } else if( ! in_array($col,$arrayPossibleNegativeAmounts) or $col=='minimumThreshold' or pq_substr($col,-10)=='Conversion'){
              echo ' constraints="{min:0,max:'.$max.',places:\'0,'.$dec.'\'}" ';
          } else {
            echo ' constraints="{min:-'.$max.',max:'.$max.(($isAmount)?',places:2':'').'}" ';
          }
        } else if ($isAmount) {
          echo ' constraints="{places:2}" ';
        } else if ($dec>0) {
          echo ' constraints="{places:\'0,'.$dec.'\'}" ';
        }
        $extraLocalClass=($obj->isLocal($col))?' localFieldClass ':'';
        echo ' class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class'.$extraLocalClass.'" ';
        // echo ' layoutAlign ="right" ';
        if ($isWork) {
          if ($classObj=='WorkElement' or $classObj=='TokenDefinition' or $classObj=='Resource') {
            $dispVal=Work::displayImputation($val);
          } else {
            $dispVal=Work::displayWork($val);
          }
        } else if ($dataLength>4000) {
          $dispVal=htmlEncode($val, 'formatted');
        } else {
          $dispVal=htmlEncode($val);
        }
        echo ' value="'.$dispVal.'" ';
        // echo ' value="' . htmlEncode($val) . '" ';
        echo ' >';
        echo $colScript;
        echo '</div>';
        if (($isCost or $isAmount) and $currencyPosition=='after') {
          $extraLocalClass=($obj->isLocal($col))?' localLabelClass ':'';
          echo '<span class="generalColClass '.$col.'Class '.$extraLocalClass.'" style="'.$specificStyleWithoutCustom.';position:relative;top:1px">'.$currency.'&nbsp'.'</span>';
        }
        if ($isWork or $isDuration or $isPercent) {
          echo '<span class="generalColClass '.$col.'Class" style="'.$specificStyleWithoutCustom.';position:relative;top:2px">';
        }
        if($uo){
          if($col!=='unitWeight'){
            echo '&nbsp;&nbsp;';
          }else{
            echo '&nbsp;';
          }
        }
//         if ($isProgress and $col=='unitProgress') {
//             echo '%&nbsp;';
//         }
        if ($isWork) {
          if ($classObj=='WorkElement' or $classObj=='TokenDefinition' or $classObj=='Resource') {
            echo Work::displayShortImputationUnit().((isNewGui())?'&nbsp;':'');
          } else {
            echo Work::displayShortWorkUnit().((isNewGui())?'&nbsp;':'');
          }
        }
        if ($isDuration) {
          if((pq_substr($col, -9, 9)=='DurationY')){
            echo i18n("colYears").((isNewGui())?'&nbsp;':'');
          }elseif((pq_substr($col, -9, 9)=='DurationM')){
            echo i18n("colMonths").((isNewGui())?'&nbsp;':'');
          }else{
            echo i18n("shortDay").((isNewGui())?'&nbsp;':'');
          }
        }
        if ($isPercent) {
            echo '%&nbsp;';
        }
        if ($isWork or $isDuration or $isPercent) {
          echo '</span>';
        }
      } else if ($dataLength>200 and ($dataLength<=4000 or getEditorType()=='text')) {
        // Draw a long text (as a textarea) =================================== TEXTAREA
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo '<textarea dojoType="dijit.form.Textarea" ';
        echo ' onKeyPress="if (dojo.isFF || isEditingKey(event)) {formChanged();}" '; // hard coding default event
        echo $name;
        echo $attributes;
        if (pq_strpos($attributes, 'readonly')>0) {
          $specificStyle.=' color:#606060 !important; background:none; background-color: #F0F0F0; ';
        }
        echo ' rows="2" style="max-height:150px;width: '.$largeWidth.'px;'.$specificStyle.'" ';
        echo ' maxlength="'.$dataLength.'" ';
        echo ' class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" >';
        /*
         * if (isTextFieldHtmlFormatted($val)) {
         * $text=new Html2Text($val);
         * $val=$text->getText();
         * echo htmlEncode($val);
         * } else {
         * echo pq_str_replace(array("\n",'<br/>','<br/>','<br />'),array("","\n","\n","\n"),$val);
         * }
         */
        if ($dataLength>4000) echo formatAnyTextToPlainText($val);
        else echo $val;
        echo '</textarea>';
      } else if ($dataLength>4000) {
        // Draw a long text (as a textarea) =================================== TEXTAREA
        // No real need to hide and apply class : long fields will be hidden while hiding row
        // class="generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" style="'.$specificStyle.'"
        if (getEditorType()=="CK" || getEditorType()=="CKInline") {
          // if (isIE() and ! $val) $val='<div></div>';
          $caption=htmlEncode($obj->getColCaption($col), 'stipAllTags');
          echo '<div style="text-align:left;font-weight:normal;width:'.(pq_strlen($caption)+2).'ex;text-align:center;" class="tabLabel longTextLabel">'.$caption.'</div>';
          if (isNewGui()) {
            if ($obj->id) {
              echo '<div style="width:60px;top:4px;xbottom:2px; z-index:999;position:absolute;right:0px;text-align:right;opacity:75%" >'
                  .'  <div onClick="displayFullScreenCK(\''.$col.'\');" class="externalEditorButtonContainer">'
                  .'    <div class="iconButton imageColorNewGui iconFullScreen iconSize16" ></div> '
                  .'  </div>'
                  .'  <div onClick="CKEDITOR.instances[\''.$col.'\'].execCommand(\'print\');" class="externalEditorButtonContainer">'
                  .'    <div class="iconButton imageColorNewGui iconPrint iconSize16"></div> '
                  .'  </div>' 
                  .'</div>';
              }else{
                echo '<style>
                    .cke_button__projeqtorfullscreen {
                      display: none !important;
                    }
                    </style>';
              }
          }
          $ckEditorNumber++;
          // gautier
          $ckeDivheight=Parameter::getUserParameter('ckeditorHeight'.$classObj.$col.$extName);
          $ckeDivheight=($ckeDivheight)?(intval($ckeDivheight)+((isNewGui())?75:0)).'':((isSimpleUi())?'300':'180');
          echo '<input type="hidden" id="ckeditorObj'.$ckEditorNumber.'" value="'.$classObj.$col.$extName.'" />';
          // BEGIN - ADD BY TABARY - TOOLTIP
          echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
          // END - ADD BY TABARY - TOOLTIP
//           if (getEditorType()=="CKInline" and isNewGui() and ! $comboDetail) {
//             echo '<div style="position:absolute;z-index:9999;right:10px;top:10px;" onClick="displayFullScreenCK(\''.$col.$extName.'\',\''.$caption.'\');">X</div>';
//           }
          echo '<textarea style="height:300px"'; // Important to set big height to retreive correct scroll position after save
          echo ' name="'.$col.$extName.'" ';
          echo ' id="'.$col.$extName.'" ';
          echo ' class="input '.(($isRequired)?'required':'').'" style="z-index:99999"';
          // echo $name.' '.$attributes;
          echo ' maxlength="'.$dataLength.'"';
          echo '>';
          if (!isTextFieldHtmlFormatted($val)) {
            echo formatPlainTextForHtmlEditing($val);
          } else {
            echo pq_htmlspecialchars($val);
          }
          echo '</textarea>';
          // echo pq_str_replace( "\n", '<br/>', $val );
          echo '<input type="hidden" id="ckeditor'.$ckEditorNumber.'" value="'.$col.$extName.'" />';
          if ($readOnly) {
            echo '<input type="hidden" id="ckeditor'.$ckEditorNumber.'ReadOnly" value="true" />';
          }
          echo '<input type="hidden" id="ckeditorType'.$ckEditorNumber.'" value="'.getEditorType().'" />';
          echo '<input type="hidden" id="ckeditorHeight'.$ckEditorNumber.'" value="'.$ckeDivheight.'" />';
        } else {
          $val=pq_str_replace("\n", "", $val);
          
          // BEGIN - ADD BY TABARY - TOOLTIP
          echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
          // END - ADD BY TABARY - TOOLTIP
          
          echo '<textarea style="display:none; visibility:hidden;" ';
          echo ' maxlength="'.$dataLength.'" ';
          echo $name;
          echo $attributes;
          echo '>';
          if (!isTextFieldHtmlFormatted($val)) {
            echo formatPlainTextForHtmlEditing($val, 'single');
          } else {
            echo ($val);
          }
          echo '</textarea>';
          if (isIE() and !$val) $val='<div></div>';
          echo '<div style="text-align:left;font-weight:normal; width:300px;" class="tabLabel">'.htmlEncode($obj->getColCaption($col), 'stipAllTags').'</div>';
          if (getEditorType()=="Dojo") {
            echo '<div data-dojo-type="dijit.Editor"'; // TEST
            echo ' id="'.$fieldId.'Editor" ';
            echo ' title="'.i18n('clickToEditRichText').'"';
            if ($readOnly) echo ' disabled=true';
            echo ' data-dojo-props="height:\'200px\'';
            if ($readOnly) echo ', disabled:true';
            echo ',onChange:function(){dojo.byId(\''.$fieldId.'\').value=arguments[0];formChanged();}';
            echo ",plugins:['bold','italic','underline','removeFormat'";
            echo ",'|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 'justifyRight', 'justifyFull'";
            echo ",'|','insertOrderedList','insertUnorderedList','|']";
            echo ',onKeyDown:function(event){onKeyDownFunction(event,\''.$fieldId.'\',this);}'; // hard coding default event
                                                                                                // echo ',onBlur:function(event){window.top.editorBlur(\'' . $fieldId . '\',this)}'; // hard coding default event
            echo ",extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor'";
            // Full screen mode disabled : sets many issues on some keys : tab, esc or ctrl+S, ...
            echo ",'|','print'";
            echo ",'fullScreen'";
            // Font Choice ...
            if (0) echo ",'fontName','fontSize'";
            // Print option
            
            // echo ",{name: 'LocalImage', uploadable: true, uploadUrl: '../../form/tests/UploadFile.php', baseImageUrl: '../../form/tests/', fileMask: '*.jpg;*.jpeg;*.gif;*.png;*.bmp'}";
            echo "]";
            echo '" ';
            echo $attributes;
            if (pq_strpos($attributes, 'readonly')>0) {
              $specificStyle.=' color:#606060 !important; background:none; background-color: #F0F0F0; ';
            }
            echo ' rows="2" style="min-height:16px;width: '.($largeWidth+145).'px;'.$specificStyle.'" ';
            echo ' maxlength="'.$dataLength.'" ';
            echo ' class="input '.(($isRequired)?'required':'').'" ';
            // echo ' style="background: none; background-color: #AAAAFF" ';
            echo '>';
          } else { // getEditorType()=="DojoInline"
            echo '<div data-dojo-type="dijit.InlineEditBox"'; // TEST
                                                              // echo '<div data-dojo-type="dijit.Editor"'; // TEST
            echo ' id="'.$fieldId.'Editor" ';
            echo ' height="50px" title="'.i18n('clickToEditRichText').'"';
            echo ' data-dojo-props="editor:\'dijit/Editor\',renderAsHtml:true';
            if ($readOnly) echo ', disabled:true';
            echo ',onChange:function(){dojo.byId(\''.$fieldId.'\').value=arguments[0];formChanged();}';
            echo ",editorParams:{height:'200px',plugins:['bold','italic','underline','removeFormat'";
            echo ",'|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 'justifyRight', 'justifyFull'";
            echo ",'|','insertOrderedList','insertUnorderedList','|']";
            echo ',onKeyDown:function(event){onKeyDownFunction(event,\''.$fieldId.'\',this);}'; // hard coding default event
            echo ',onBlur:function(event){editorBlur(\''.$fieldId.'\',this)}'; // hard coding default event
            echo ",extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor'";
            echo ",'|','print'";
            echo ",'fullScreen'";
            // Font Choice ...
            if (0) echo ",'fontName','fontSize'";
            // echo ",{name: 'LocalImage', uploadable: true, uploadUrl: '../../form/tests/UploadFile.php', baseImageUrl: '../../form/tests/', fileMask: '*.jpg;*.jpeg;*.gif;*.png;*.bmp'}";
            echo "]}";
            echo '" ';
            echo $attributes;
            if (pq_strpos($attributes, 'readonly')>0) {
              $specificStyle.=' color:#606060 !important; background:none; background-color: #F0F0F0; ';
            }
            echo ' rows="2" style="padding:3px 0px 3px 3px;margin-right:2px;max-height:150px;min-height:16px;overflow:auto;width: '.($largeWidth+145).'px;'.$specificStyle.'" ';
            echo ' maxlength="'.$dataLength.'" ';
            echo ' class="input '.(($isRequired)?'required':'').'" ';
            echo ' style="background: none; background-color: #AAAAFF" ';
            echo '>';
          }
          // echo ' <script type="dojo/connect" event="onKeyPress" args="evt">';
          // echo ' alert("OK");';
          // echo ' </script>';
          if (!isTextFieldHtmlFormatted($val)) {
            echo formatPlainTextForHtmlEditing($val, 'single');
          } else {
            echo ($val);
          }
          // echo $val;
          echo '</div>';
        }
      } else if ($col=='icon') {
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo '<div dojoType="dijit.form.Select" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" ';
        echo '  style="width: '.($fieldWidth).'px;'.$specificStyle.'"';
        echo $name;
        echo $attributes;
        echo ' >';
        // htmlDrawOptionForReference($col, $val, $obj, $isRequired,$critFld, $critVal);
        echo '<span value=""> </span>';
        if ($handle=opendir(getcwd().'/icons')) {
          $listIcons=array();
          while (false!==($entry=readdir($handle))) {
            if ($entry!="."&&$entry!="..") {
              $listIcons[]=$entry;
            }
          }
          sort($listIcons);
          foreach ($listIcons as $entry) {
            $ext=pq_strtolower(pathinfo($entry, PATHINFO_EXTENSION));
            if ($ext=="png" or $ext=="gif" or $ext=="jpg" or $ext=="jpeg") {
              echo '<span value="'.$entry.'" '.(($entry==$val)?'selected="selected"':'').'><img src="../view/icons/'.$entry.'" /></span>';
            }
          }
          closedir($handle);
        }
        echo $colScript;
        echo '</div>';
      } else {
        // Draw defaut data (text medium size) ================================ TEXT (default)
        if ($obj->isFieldTranslatable($col)) {
          $fieldWidth=$fieldWidth/2;
        }
        // BEGIN - ADD BY TABARY - TOOLTIP
        echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
        // END - ADD BY TABARY - TOOLTIP
        echo '<div type="text" dojoType="dijit.form.ValidationTextBox" ';
        echo $name;
        echo $attributes;
        echo '  style="width: '.$fieldWidth.'px;'.$specificStyle.';" ';
        echo ' trim="true" maxlength="'.$dataLength.'" class="input '.(($isRequired)?'required':'').' generalColClass '.$notReadonlyClass.$notRequiredClass.$col.'Class" ';
        echo ' value="'.htmlEncode($val).'" ';
        if ($obj->isFieldTranslatable($col)) {
          echo ' title="'.i18n("msgTranslatable").'" ';
        }
        echo ' >';
        echo $colScript;
        echo '</div>';
        if ($obj->isFieldTranslatable($col)) {
          echo '<div dojoType="dijit.form.TextBox" type="text"  ';
          echo ' class="display" ';
          echo ' readonly tabindex="-1" style="width: '.$fieldWidth.'px;" ';
          echo ' title="'.i18n("msgTranslation").'" ';
          echo ' value="'.htmlEncode(i18n($val)).'" ></div>';
        }
      }
      if ($internalTable>0) {
        $internalTable--;
        if ($internalTable==0) {
          if (!$widthPct) $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj, "2");
          echo '</td></tr></table><table  style="width:'.$widthPct.'">';
        }
      } else {
        if ($internalTable==0 and !$hide and !$nobr) {
          echo '</td></tr>'.$cr;
        }
      }
    }
    if (! $hide and ! $nobr) {
      $lineStarted=false;
    }
  }

  if( $classObj=='ActivityPlanningElement' and ($validatedWorkReadOnly or $validatedCostReadOnly)){
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$profile,'scope'=>'changeValidatedData'));
    if($habil and ($habil->rightAccess == 2 or ! $habil->id )){
      $fieldHidden='';
      if($validatedWorkReadOnly){
        echo '<input id="hiddenFielsActivityWork" type="hidden" value="readonly" /> ';
      }
      if($validatedCostReadOnly){
        $fieldHidden .='validatedCost';
        echo '<input id="hiddenFielsActivityCost" type="hidden" value="readonly" /> ';
      }
    }
  }
  if (!$included) {
    if ($currentCol==0) {
      if ($section and !$print) {
        echo '</div>';
      }
      echo '</table>';
    } else {
      echo '</table>';
      if ($section and !$print) {
        echo '</div>';
      }
      // echo '</td></tr></table>';
    }
  }

  if (!$included) {
    endBuffering($section, $included);
    startBuffering();
    drawChecklistFromObject($obj,$nbCol);
    endBuffering('Checklist', $included);
    startBuffering();
    drawJoblistFromObject($obj,$nbCol);
    endBuffering('Joblist', $included);
    if (pq_substr(Parameter::getUserParameter('displayHistory'),0,3)=='YES') {
      startBuffering();
      drawHistoryFromObjects(false);
      endBuffering('History', $included);
    }
    finalizeBuffering();
  }
  
  
  if ($outMode=='pdf') {
    $cpt=0;
    foreach ($obj->getFieldsList() as $col) {
      if (! property_exists($obj, $col)) continue;
      if (! isset($varSet[$col])) continue;
      $val=(property_exists($obj, $col) and isset($obj->$col))?$obj->$col:null;
      if (pq_substr($col, 0, 1)=='_' and pq_substr($col, -5)=='_full') {
        $cpt++;
        $section=pq_substr($col, 1, pq_strlen($col)-6);
        // echo '</page><page>';
        if ($cpt==1) echo '<page><br/>';
        echo '<table style="width:'.$printWidth.'px;"><tr><td class="section">'.$obj->getColCaption($section).'</td></tr></table>';
        echo htmlEncode($val, 'print');
        echo '<br/><br/>';
      }
    }
    if ($cpt>0) echo '</page>';
  }
}

function startTitlePane($classObj, $section, $collapsedList, $widthPct, $print, $outMode, $prevSection, $nbCol, $nbBadge=null, $included=null, $obj=null) {
  //scriptLog("startTitlePane(classObbj=$classObj, section=$section, collapsedList=array, widthPct=$widthPct, print=$print, outMode=$outMode, prevSection=$prevSection, nbCol=$nbCol, nbBadge=$nbBadge)");
  global $comboDetail, $currentColumn, $reorg,$paneDetail, $leftPane, $rightPane, $extraPane, $bottomPane, $historyPane,$panes, $beforeAllPanes,$type, $arrayGroupe, $layout,$profile;
  if (!$currentColumn) $currentColumn=0;
  if ($prevSection) {
    echo '</table>';
    if (!$print) {
      echo '</div>';
    } else {
      echo '<br/>';
    }
  }
  endBuffering($prevSection, $included);
  $sectionName=$section;
  if(strstr($sectionName,'Link_')){
    $split=pq_explode('_', $sectionName);
    $sectionName=$split[0].$split[1];
  }
  if (pq_strpos($sectionName, '_')!=0) {
    $split=pq_explode('_', $sectionName);
    $sectionName=$split[0];
  }
  if (!$obj) $obj=new $classObj();
  if ($section=='Note' or $section=='Attachment') {
    $style=$obj->getDisplayStyling('_'.$section);
  } else {
    $style=$obj->getDisplayStyling('_sec_'.$section);
  }
  $labelStyle=$style["caption"];
  $extraHiddenFields=$obj->getExtraHiddenFields();
  if (!$print) {
    $float='left';
    $clear='none';
    $lc=pq_strtolower($section);
    $titlePane=$classObj."_".$section;
    if ($classObj=='Project' and $section=='RaciMatrix') {
      $titlePane='Project_RaciMatrixSection';
    }
    startBuffering($included);
    $display='inline-block';
    if ($obj->isAttributeSetToField('_sec_'.$section, 'hidden') or in_array('_sec_'.$section, $extraHiddenFields)) {
      $display='none';
    }
    $attrs=splitCssAttributes($labelStyle);
    $fontSize=(isset($attrs['font-size']))?intval($attrs['font-size']):'';
    $margin=0;
    //florent ticket 4102
    //if( $layout=='tab' and $included==false and !$print){
    if( $layout=='tab' and !$print){
      $margin=4;
      $tabName="Detail";
      if(isset($arrayGroupe[$lc]['99'])){
        $tabName=pq_ucfirst($arrayGroupe[$lc]['99']);
      }
      $sessionTabName='detailTab'.$classObj;
      $selectedTab=($obj->id)?getSessionValue($sessionTabName,'Description'):'Description';
      $paneName='pane'.$tabName;
      $paneIndex=lcfirst($tabName);
      $extName=($comboDetail)?"_detail":'';
      if (!isset($panes[$paneIndex]) or $panes[$paneIndex]=='') {
        $nbBadgeTab=$nbBadge;
        if ($obj and $section=='predecessor') {
          if (property_exists($obj,'_Dependency_Predecessor') and property_exists($obj,'_Dependency_Successor')) {
            $nbBadgeTab=count($obj->_Dependency_Predecessor)+count($obj->_Dependency_Successor);
          }
        }
        echo '<div id="'.$tabName.$extName.'" dojoType="dijit.layout.ContentPane" class="detailTabClass" ';
        echo ' title="'.i18n('tab'.pq_ucfirst($tabName)).(($nbBadge!==null )?'<div id=\''.$section.'BadgeTab\' class=\'sectionBadge\' style=\'right:0px;top:0px;width:auto;padding:0px 7px;font-weight:normal;zoom:0.9; -moz-transform: scale(0.9);'.(($nbBadgeTab==0)?'opacity:0.5;':'').'\' >'.$nbBadgeTab.'</div>':'').'" style="width:100%;height:100%;overflow:auto;" '.(($tabName==$selectedTab)?' selected="true" ':'').'>';
        echo ' <script type="dojo/method" event="onShow" >'; 
        echo '   saveDataToSession(\''.$sessionTabName.'\',\''.$tabName.'\');';
        echo '   hideEmptyTabs();';
        echo ' </script>';
        echo '  <div>';
      }
    }
    // gautier #resourceTeam
    if($section=='Assignment'){
      $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'assignmentView'));
      if ($habil and $habil->rightAccess!=1) {
        $nbBadge=null;
      }
    }
    echo '<div dojoType="dijit.TitlePane" title="'.i18n('section'.pq_ucfirst($sectionName)).(($nbBadge!==null)?'<div id=\''.$section.'Badge\' class=\'sectionBadge\'>'.$nbBadge.'</div>':'').'"';
    echo ' open="'.(pq_array_key_exists($titlePane, $collapsedList)?'false':'true').'" ';
    echo ' id="'.$titlePane.'" ';
    echo ' class="titlePaneFromDetail generalColClass'.(($obj->isAttributeSetToField('_sec_'.$section, 'hidden'))?'Hidden':'').' _sec_'.$section.'Class" ';
    echo ' titleStyle="'.$labelStyle.'"';
    echo ' style="display:'.$display.';position:relative;width:'.$widthPct.';float: '.$float.';clear:'.$clear.';margin: '.$margin.'px 0 4px '.((isNewGui())?'15':'4').'px; padding: 0;top:0px;"';
    echo ' onHide="saveCollapsed(\''.$titlePane.'\');"';
    echo ' onShow=";saveExpanded(\''.$titlePane.'\');refreshSectionCount(\''.$sectionName.'\')">';
    $titleHeight=($fontSize)?$fontSize*1.6:'';
    echo ' <script type="dojo/method" event="titlePaneHandler" > setAttributeOnTitlepane(\''.$titlePane.'\',\''.$labelStyle.'\',\''.$titleHeight.'\');</script>';
    echo '<table class="detail"  style="width: 100%;" >';
  } else {
    $hide=false;
    $display='';
    if ($obj->isAttributeSetToField('_sec_'.$section, 'hidden') or in_array('_sec_'.$section, $extraHiddenFields)) {
      $display='display:none;';
      $hide=true;
    }
    if (!$hide) {
      echo '<table class="detail" style="width:'.$widthPct.';'.$display.'" >';
      echo '<tr><td class="section">'.i18n('section'.pq_ucfirst($sectionName)).'</td></tr>';
      echo '<tr class="detail" style="height:2px;font-size:2px;">';
      echo '<td class="detail" >&nbsp;</td>';
      echo '</tr>';
      echo '</table>';
    }
    echo '<table class="detail" style="width:'.$widthPct.';'.$display.'" >';
  }
}

function drawDocumentVersionFromObject($list, $obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->locked) {
    $canUpdate=false;
  }
  // if ($obj->idle==1) {$canUpdate=false;}
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  $typeEvo="EVO";
  $type=new VersioningType($obj->idVersioningType);
  $typeEvo=$type->code;
  $num="";
  $vers=new DocumentVersion($obj->idDocumentVersion);
  if ($typeEvo=='SEQ') {
    $num=intVal($vers->name)+1;
  }
  //echo '<thead>';
  echo '<tr>';
  if (!$print) {
    $statusTable=SqlList::getList('Status', 'name', null);
    reset($statusTable);
    echo '<td class="assignHeader" style="width:10%">';
    if ($obj->id!=null and !$print and $canUpdate and !$obj->idle) {
      echo '<a onClick="addDocumentVersion('."'".key($statusTable)."'".",'".$typeEvo."'".",'".$num."'".",'".htmlEncode($vers->name,'protectQuotes')."'".",'".htmlEncode($vers->name,'protectQuotes')."',".$obj->locked.');" ';
      echo ' title="'.i18n('addDocumentVersion').'" id="buttonAddDocument"> ';
      echo formatSmallButton('Add');
      echo '</a>';
    }else if(!$canUpdate and $obj->idLocker == $user->id){
      echo '<a onClick="addDocumentVersion('."'".key($statusTable)."'".",'".$typeEvo."'".",'".$num."'".",'".htmlEncode($vers->name,'protectQuotes')."'".",'".htmlEncode($vers->name,'protectQuotes')."',".$obj->locked.');" ';
      echo ' title="'.i18n('addDocumentVersion').'" id="buttonAddDocument"> ';
      echo formatSmallButton('Add');
      echo '</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:15%">'.i18n('colIdVersion').'</td>';
  echo '<td class="assignHeader" style="width:15%" >'.i18n('colDate').'</td>';
  echo '<td class="assignHeader" style="width:15%">'.i18n('colIdStatus').'</td>';
  echo '<td class="assignHeader" style="width:'.(($print)?'55':'45').'%">'.i18n('colFile').'</td>';
  echo '</tr>';
  //echo '</thead>';
  //echo '<tbody>';
  $preserveFileName=Parameter::getGlobalParameter('preserveUploadedFileName');
  if (!$preserveFileName) {
    $preserveFileName="NO";
  }
  rsort($list);
  foreach ($list as $version) {
    echo '<tr>';
    $canDownload = false;
    if ($obj->locked){
      $forbidDownload = Parameter::getGlobalParameter('lockDocumentDownload');
      if(($forbidDownload == "YES" and $obj->idLocker == $user->id) or $forbidDownload == "NO" or $forbidDownload == ""){
        $canDownload = true;
      }
    }else {
      $canDownload = true;
    }
    if (!$print) {
      echo '<td class="assignData" style="text-align:center; white-space: nowrap;vertical-align:top;">';
      //damian    
      if (!$print and $canDownload and $version->fileName!='noFileNameAdmitted') {
        //echo '<a href="../tool/download.php?class=DocumentVersion&id='.htmlEncode($version->id).Security::addTokenIndexToUrl().'"';
        //echo ' target="printFrame" title="'.i18n('helpDownload')."\n".(($preserveFileName=='YES')?$version->fileName:$version->fullName).'">'.formatSmallButton('Download').'</a>';
        if ( ! file_exists($version->getUploadFileName()) ) {
          echo '<span class="" title="'.i18n('errorNotFoundAttachment')."\n".$version->getUploadFileName().'">';
          echo formatSmallButton('Mark',false,false).'</span>';
        } else {
          echo '<a onClick="dojo.byId(\'printFrame\').src=\'../tool/download.php?class=DocumentVersion&id='.htmlEncode($version->id).Security::addTokenIndexToUrl().'\';" ';
          echo ' title="'.i18n('helpDownload')."\n".(($preserveFileName=='YES')?$version->fileName:$version->fullName).'">'.formatSmallButton('Download').'</a>';
        }
      }else if (!$print and $version->fileName=='noFileNameAdmitted'){
        echo '<span style="width:20px;display: inline-block;"></span>';
      }
      if ($canUpdate and !$print and (!$obj->idle or $obj->idDocumentVersion==$version->id)) {
        echo '  <a onClick="editDocumentVersion('."'".htmlEncode($version->id)."'".",'".htmlEncode($version->version)."'".",'".htmlEncode($version->revision)."'".",'".htmlEncode($version->draft)."'".",'".htmlEncode($version->versionDate)."'".",'".htmlEncode($version->idStatus)."'".",'".$version->isRef."'".",'".$typeEvo."'".",'".htmlEncode($version->name,'protectQuotes')."'".",'".htmlEncode($version->name,'protectQuotes')."'".",'".htmlEncode($version->name,'protectQuotes')."'".');" '.'title="'.i18n('editDocumentVersion').'" >'.formatSmallButton('Edit').'</a> ';
      }
      if ($canUpdate and !$print and !$obj->idle) {
        echo '  <a onClick="removeDocumentVersion('."'".htmlEncode($version->id)."'".', \''.htmlEncode($version->name,'protectQuotes').'\');" '.'title="'.i18n('removeDocumentVersion').'" >'.formatSmallButton('Remove').'</a> ';
      }
      if (count($obj->_Approver)>=1) {
        echo '  <a onClick="displayListOfApprover('."'".htmlEncode($version->id)."'".');" '.'title="'.i18n('dialogApproverByVersion').'" >'.formatSmallButton('ListApprover').'</a> ';
      }
      echo '<input type="hidden" id="documentVersion_'.htmlEncode($version->id).'" name="documentVersion_'.htmlEncode($version->id).'" value="'.htmlEncode($version->description).'"/>';
      echo '</td>';
    }
    echo '<td class="assignData">'.(($version->isRef)?'<b>':'').htmlEncode($version->name).(($version->isRef)?'</b>':'');
    if ($version->approved) {
      echo '&nbsp;&nbsp;<img src="../view/img/check.png" style="height:12px;position:relative;top:1px" title="'.i18n('approved').'"/>';
    }else if ($version->disapproved) {
      echo '&nbsp;&nbsp;<img src="../view/img/uncheck.png" style="height:12px;position:relative;top:1px" title="'.i18n('disapproved').'"/>';
    }
    echo '</td>';
    echo '<td class="assignData">'.htmlFormatDate($version->versionDate).'</td>';
    $objStatus=new Status($version->idStatus);
    echo '<td class="assignData colorNameData" style="width:15%">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</td>';
    echo '<td class="assignData" title="'.htmlencode($version->description).'">';
    echo '<table style="width:100%"><tr><td style="width:20px">';
    if ($version->isThumbable() and !$print) {
      $ext=pathinfo($version->fileName, PATHINFO_EXTENSION);
      if (file_exists("../view/img/mime/$ext.png")) {
        $img="../view/img/mime/$ext.png";
      } else {
        $img="../view/img/mime/unknown.png";
      }
      echo '<img src="'.$img.'" '.' title="'.htmlEncode($version->fileName).'" style="float:left;cursor:pointer"'.' onClick="showImage(\'DocumentVersion\',\''.htmlEncode($version->id).'\',\''.htmlEncode($version->fileName, 'protectQuotes').'\');" />';
    } else {
      if ($version->fileName!='noFileNameAdmitted') echo htmlGetMimeType($version->mimeType, $version->fileName, ($canDownload)?$version->id:null, 'DocumentVersion');
    }
    echo '</td><td>';
    if ($version->fileName!='noFileNameAdmitted') echo htmlEncode($version->fileName, 'print');
    if ($version->description and !$print) {
      echo formatCommentThumb($version->description);
    }
    echo '</td></tr></table>';
    echo '</td></tr>';
  }
  //echo '</tbody>';
  echo '</table></td></tr>';
}

function drawOrigin($list, $refType, $refId, $obj, $col, $print) {
  echo '<tr class="detail"><td class="label" style="">';
  echo '<label for="'.$col.'" style="margin:auto">'.htmlEncode($obj->getColCaption($col), 'stipAllTags').'&nbsp;'.((isNewGui())?'':':&nbsp;').'</label>';
  echo '</td>';
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if ($print) {
    echo '<td style="width: 120px;">';
  } else {
    echo '<td style="'.((isNewGui())?'padding-top:10px;padding-bottom:5px;width:100%':'').'">';
  }
  if ($refType and $refId) {
    $origObjClass=null;
    $origObjId=null;
    if ($list->originType==get_class($obj) and $list->originId==$obj->id) {
      // $origObj=new $list->refType($list->refId);
      $origObjClass=$list->refType;
      $origObjId=$list->refId;
    } else {
      // $origObj=new $list->originType($list->originId);
      $origObjClass=$list->originType;
      $origObjId=$list->originId;
    }
    //florent ticket#2948
    if($origObjClass == 'DocumentVersion'){
      $origObjClass = 'Document';
      $doc = new DocumentVersion($origObjId,true);
      $origObjId = $doc->idDocument;
    }
    //Gautier hide removeOrigin if Synch
    if(get_class($obj)=='Activity' and $refType=='Ticket'){
      $synch = new SynchronizedItems();
      $isSynch = $synch->countSqlElementsFromCriteria(array('ref1Type'=>'Activity','ref1Id'=>$obj->id,'ref2Type'=>'Ticket','ref2Id'=>$refId));
      if($isSynch)$canUpdate = false;
    }
    $gotoE=' onClick="gotoElement('."'".$origObjClass."','".htmlEncode($origObjId)."'".');" ';
    echo '<table style="width:100%;"><tr height="20px;min-height:20px;border:1px solid red"><td xclass="noteData" width="1%" valign="'.((isNewGui())?'top':'middle').'">';
    if (!$print and $canUpdate) {
      echo '<a onClick="removeOrigin(\''.$obj->$col->id.'\',\''.$refType.'\',\''.$refId.'\');" title="'.i18n('removeOrigin').'" > '.formatSmallButton('Remove').'</a>';
    }
    echo '</td><td width="30%" class="noteData '.((isNewGui() and isset($gotoE) and $gotoE!='')?'classLinkName':'').'" valign="top" style="border:none;white-space:nowrap;padding:0px 5px;max-width:200px;cursor:pointer;" '.$gotoE.'>';
    echo i18n($refType).'&nbsp;#'.$refId.'';
    echo '</td><td class="noteData '.((isNewGui() and isset($gotoE) and $gotoE!='')?'classLinkName':'').'" valign="top" '.$gotoE.' style="border:none;height: 15px;cursor:pointer; padding:0px 5px">';
    $orig=new $refType($refId, true);
    echo htmlEncode($orig->name);
    echo '</td></tr></table>';
  } else {
    echo '<table style=""><tr height="20px"><td>';
    if ($obj->id and !$print and $canUpdate) {
      echo '<a onClick="addOrigin();" title="'.i18n('addOrigin').'" '.((isNewGui())?'style="position:relative;top:-2px;"':'').'class="roundedButtonSmall"> '.((isNewGui())?formatMediumButton('Add'):formatSmallButton('Add')).'</a>';
    }
    echo '</td></tr></table>';
  }
}

function drawHistoryFromObjects($refresh=false) {
  global $cr, $print, $outMode, $printWidth, $treatedObjects, $comboDetail, $displayWidth,$collapsedList, $paneHistory, $included, $layout, $classObj;
  $mainObj=null;
  $doc=false;
  $histList=array();
  $histListApprover=array();
  $showArchiveValue=1;
  $showArchive=false;
  if(getSessionValue('showArchive')=="1"){
      $showArchive=true;
      $showArchiveValue=0;
  }
  if (isset($treatedObjects[0])) $mainObj=$treatedObjects[0];
  $widthPct=setWidthPct($displayWidth, $print, $printWidth, $mainObj, "2");
  $displayHistory='REQ';
  $paramDisplayHistory=Parameter::getUserParameter('displayHistory');
  if ($paramDisplayHistory) {
    $displayHistory=$paramDisplayHistory;
  }
  if ($mainObj and (property_exists($mainObj, '_noHistory') or property_exists($mainObj, '_noDisplayHistory'))) {
    $displayHistory='NO';
  }
  if ($print and Parameter::getUserParameter('printHistory')!='YES') {
    $displayHistory='NO';
  }
  if ($displayHistory=='NO') return;
  if ($comboDetail) return;
  if (!$mainObj or !$mainObj->id) return;
  
  $maxWidth=($displayWidth and pq_substr($displayWidth,-2)=='px')?(intval($displayWidth)/2)-180:500;
  SqlElement::$_cachedQuery['Note']=array();
  SqlElement::$_cachedQuery['Attachment']=array();

  $inList="( ('x',0)"; // initialize with non existing element, to avoid error if 1 only object involved
  foreach ($treatedObjects as $obj) {
    // $inList.=($inList=='')?'(':', ';
    if ($obj->id) {
      $inList.=", ('".get_class($obj)."', ".Sql::fmtId($obj->id).")";
    }
  }
  if ($mainObj && property_exists($mainObj, '_SubTask')) {
    $subTaskList = new SubTask();
    $subTasks = $subTaskList->getSqlElementsFromCriteria(
        array('refType' =>  get_class($mainObj) , 'refId' => $mainObj->id)
        );
    
    foreach ($subTasks as $subTask) {
      if ($subTask->id) {
        $inList .= ", ('SubTask', " . Sql::fmtId($subTask->id) . ")";
      }
    }
  }
  $showWorkHistory=false;
  $paramDisplayHistory=Parameter::getUserParameter('displayHistory');
  if (($paramDisplayHistory=='REQ' and getSessionValue('showWorkHistory')) or $paramDisplayHistory=='YESW') {
    $showWorkHistory=true;
  }
  $inList.=')';
  $where=' (refType, refId) in '.$inList;
  $order=' operationDate desc, id asc';
  $hist=new History();
  $historyList=$hist->getSqlElementsFromCriteria(null, false, $where, $order);
  $historyList=array_merge($historyList,$histList,$histListApprover);
  //florent
  if($showArchive==true){
    $histArchive= new HistoryArchive();
    $histArchiveList=$histArchive->getSqlElementsFromCriteria(null, false, $where, $order);
    if(count($histArchiveList)==0){
      //$showArchive=false;
      //$showArchiveValue=1;
    }
    $historyList=array_merge($historyList, $histArchiveList);
  }
  if ($print) {
    echo '<table width="'.$printWidth.'px;"><tr><td class="section">'.i18n('elementHistory').'</td></tr></table>';
  } else if (!$refresh) {
    $titlePane=get_class($mainObj)."_history";
    $section='History';
    $selectedTab=null;
    $tabName="History";
    $sessionTabName='detailTab'.get_class($obj);
    $selectedTab=($obj->id)?getSessionValue($sessionTabName,'Description'):'Description';
    $paneName='pane'.$tabName;
    echo '<div style="width: '.$displayWidth.';padding:4px;overflow:auto;position:relative;" dojoType="dijit.TitlePane" '; 
    echo ' title="'.(($layout=='tab')?i18n('tabHistory'):i18n('elementHistory')).'" ';
    echo (($tabName==$selectedTab)?' selected="true" ':'');
    if($layout!='tab') echo ' open="'.((pq_array_key_exists($titlePane, $collapsedList))?'false':'true').'" ';
    echo ' id="'.$titlePane.'" ';         
    echo ' onHide="saveCollapsed(\''.$titlePane.'\');"';
    echo ' >';
    echo ' <script type="dojo/method" event="onShow" >';
    echo '   saveDataToSession(\''.$sessionTabName.'\',\''.$tabName.'\');';
    echo '   saveExpanded(\''.$titlePane.'\');';
    echo '   hideEmptyTabs();';
    echo ' </script>';

  }
  if ($print) 
    echo '<table style="width:'.$printWidth.'px;">';
  else   
  echo '<table style="width:100%;margin-right:10px;position:relative;">';
  echo '<tr>';
  echo '<td class="historyHeader" style="width:10%">'.i18n('colOperation').'</td>';
  echo '<td class="historyHeader" style="width:15%">'.i18n('colColumn').'</td>';
  echo '<td class="historyHeader" style="width:25%">'.i18n('colValueBefore').'</td>';
  echo '<td class="historyHeader" style="width:25%">'.i18n('colValueAfter').'</td>';
  echo '<td class="historyHeader" style="width:10%">'.i18n('colDate').'</td>';
  echo '<td class="historyHeader" style="width:15%">'.i18n('colUser').'</td>';
  if( (RequestHandler::isCodeSet('dialog') and RequestHandler::getValue('dialog')=='dialogHistory') or $print ){
    // Done on dynamicDialogHistory
  }else{
    echo '<div style="position:absolute;right:6px;'.((isNewGui())?'top:15px;':'top:3px;').'">';
    if($showArchive==true){
      echo '  <button id="historyArchiveDetail" title="'.i18n('helpCloseHistoryArchive').'" region="center" dojoType="dijit.form.Button" class="detailButton"  iconClass="imageColorNewGui iconButtonMark16 iconButtonMark  iconHistArchiveNo iconSize16" > ';
    }else{
      echo '<button id="historyArchiveDetail" title="'.i18n('helpShowHistoryArchive').'" region="center" dojoType="dijit.form.Button"  class="detailButton" iconClass="imageColorNewGui iconHistArchive16 iconHistArchive iconSize16" > ';
    }
    echo '     <script type="dojo/connect" event="onClick" args="evt">';
    echo '         var callBack=function() {loadContent("objectDetail.php?refreshHistory=true", dojo.byId("objectClass").value+"_history", "listForm");};';
    echo '         saveDataToSession("showArchive","'.$showArchiveValue.'",false,callBack);';
    echo '     </script>';
    echo '  </button>';
    echo '</div>';
  }
 
  echo '</tr>';
  $stockDate=null;
  $stockUser=null;
  $stockOper=null;
  $idNote=0;
  $idUser=getSessionUser()->id;
  $teamUser=getSessionUser()->idTeam;
  foreach ($historyList as $hist) {
    if (pq_substr($hist->colName, 0, 6)=='|Note|' || pq_substr($hist->colName, 0, 10)=='note|Note|') {
      $idNote=pq_substr($hist->colName, 6,10 );
      if(pq_substr($hist->colName, 0, 10)=='note|Note|'){
        $idNote=pq_substr($hist->colName, 10,13 );
      }
      $myNote=SqlElement::getSingleSqlElementFromCriteria("note", array('id'=>$idNote));
          if( $myNote->idPrivacy==3 || $hist->operation=="delete" ){
        if($idUser!=$hist->idUser){
        continue; 
        }
      }
      if( $myNote->idPrivacy=="" || $hist->operation=="delete" ){
        if($idUser!=$hist->idUser){
          continue;
        }
      }
      if( $myNote->idPrivacy=="2" ){
        if($teamUser!=$myNote->idTeam){
          continue;
        }
      }
    }
    if (pq_substr($hist->colName, 0, 24)=='subDirectory|Attachment|' or pq_substr($hist->colName, 0, 18)=='idTeam|Attachment|' or pq_substr($hist->colName, 0, 25)=='subDirectory|Attachement|' or pq_substr($hist->colName, 0, 19)=='idTeam|Attachement|') {
      continue;
    }
    if ($hist->colName=='plannedStartFraction' or $hist->colName=='plannedEndFraction' or $hist->colName=='latestStartDate' or $hist->colName=='latestEndDate') {
      continue;
    }
    if (($hist->refType=='VotingItem' or $hist->colName=='minimumThreshold') and !$hist->oldValue and (!$hist->newValue or $hist->newValue=='0')) continue;
    $colName=($hist->colName==null)?'':$hist->colName;
    $split=pq_explode('|', $colName);
    if (count($split)==3) {
      $colName=$split[0];
      $refType=$split[1];
      $refId=$split[2];
      $refObject='';
    } else if (count($split)==4) {
      $refObject=$split[0];
      $colName=$split[1];
      $refType=$split[2];
      $refId=$split[3];
    } else {
      $refType='';
      $refId='';
      $refObject='';
    }
    if ($refType=='Attachement') {
      $refType='Attachment'; // New in V5 : change Class name, must preserve display for history
    }
    $curObj=null;
    $dataType="";
    $dataLength=0;
    $hide=false;
    $oper=i18n('operation'.pq_ucfirst($hist->operation));
    $user=$hist->idUser;
    $user=SqlList::getNameFromId('Affectable', $user);
    $date=htmlFormatDateTime($hist->operationDate);
    $class="NewOperation";
    if ($stockDate==$hist->operationDate and $stockUser==$hist->idUser and $stockOper==$hist->operation) {
      $oper="";
      $user="";
      $date="";
      $class="ContinueOperation";
    }
    if ($colName!='' or $refType!="") {
      if ($refType) {
        if ($refType=="TestCase") {
          $curObj=new TestCaseRun();
        } else {
          $curObj=new $refType();
        }
      } else {
        $curObj=new $hist->refType();
      }
      if ($curObj) {
        if (method_exists($curObj, 'setAttributes')) {
        	$curObj->setAttributes();
        }
        if ($refType) {
          $colCaption=i18n($refType).' #'.$refId.' '.$curObj->getColCaption($colName);
          if ($refObject) {
            $colCaption=i18n($refObject).' - '.$colCaption;
          }
        } else {
          $colCaption=$curObj->getColCaption($colName);
        }
        $dataType=$curObj->getDataType($colName);
        $dataLength=$curObj->getDataLength($colName);
        if($hist->refType == 'Component' and $colName == 'idComponent'){
          $hide=false;
        }else if (pq_strpos($curObj->getFieldAttributes($colName), 'hidden')!==false) {
          $hide=true;
        }
      }
    } else {
      $colCaption='';
    }
//     if(($hist->refType=='Affectation' or $hist->refType=='Assignment') and ($hist->operation == 'update')) $hide=true;
    if (pq_substr($hist->refType, -15)=='PlanningElement' and $hist->operation=='insert') {
      $hide=true;
    }
    if ($hist->isWorkHistory and !$showWorkHistory) {
      $hide=true;
    }
    if (pq_substr($hist->colName, 0, 6)=='|Note|' or pq_substr($hist->colName, 0, 12)=='|Attachment|') {
      $expl=pq_explode('|', $hist->colName);
      if (count($expl)==3) {
        $clSub=$expl[1];
        $idSub=$expl[2];
        $sub=new $clSub($idSub);
        if (property_exists($sub, 'idPrivacy') and $sub->idPrivacy==3 and $sub->idUser!=getCurrentUserId()) {
          $hide=true;
        } else if (property_exists($sub, 'idPrivacy') and $sub->idPrivacy==2 and property_exists($sub, 'idTeam') and $sub->idTeam!=getSessionUser()->idTeam) {
          $hide=true;
        }
      }
    }
    if (SqlElement::isLocal($colName) and !$obj->hasCurrency()) $hide=true;
    if ($print and $outMode=='pdf') $class='';
    if (!$hide) {
      echo '<tr>';
      echo '<td class="historyData'.$class.'" style="width:10%;">'.$oper.'</td>';
      //florent
      if($hist->refType=='Approver'){
          $colCaption=$hist->refType;
      }
      echo '<td class="historyData" style="width:15%">'.$colCaption.'</td>';
      $oldValue=$hist->oldValue;
      $newValue=$hist->newValue;
      $oldValue=pq_str_replace(array('<style','/style>'),array('<nostyle','/nostyle>'),$oldValue);
      $newValue=pq_str_replace(array('<style','/style>'),array('<nostyle','/nostyle>'),$newValue);
      if ($dataType=='int' and $dataLength==1) { // boolean
        $oldValue=htmlDisplayCheckbox($oldValue);
        $newValue=htmlDisplayCheckbox($newValue);
      } else if (pq_substr($colName, 0, 2)=='id' and pq_strlen($colName)>2 and pq_strtoupper(pq_substr($colName, 2, 1))==pq_substr($colName, 2, 1)) {
        if ($oldValue!=null and $oldValue!='') {
          if ($oldValue==0 and $colName=='idStatus') {
            $oldValue='';
          } else {
            // BEGIN - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
            $colWithoutAlias=foreignKeyWithoutAlias($colName);
            $colOldExtClass=pq_substr($colWithoutAlias, 2);
            $oldValue=(SqlElement::class_exists($colOldExtClass))?SqlList::getNameFromId($colOldExtClass, intval($oldValue)):"#$oldValue";
            // END - REPLACE BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
            // $oldValue=SqlList::getNameFromId(pq_substr($colName, 2), $oldValue);
          }
        }
        if ($newValue!=null and $newValue!='') {
          // BEGIN - ADD BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
          $colWithoutAlias=foreignKeyWithoutAlias($colName);
          $colNewExtClass=pq_substr($colWithoutAlias, 2);
          $newValue=(SqlElement::class_exists($colNewExtClass))?SqlList::getNameFromId($colNewExtClass, intval($newValue)):"#$newValue";
          // $newValue=SqlList::getNameFromId(pq_substr($colName, 2), $newValue);
          // END - ADD BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
        }
      } else if ($colName=="color") {
        $oldValue=htmlDisplayColoredFull("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", $oldValue);
        $newValue=htmlDisplayColoredFull("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", $newValue);
      } else if ($dataType=='date') {
        $oldValue=htmlFormatDate($oldValue);
        $newValue=htmlFormatDate($newValue);
      } else if ($dataType=='datetime') {
        $oldValue=htmlFormatDateTime($oldValue,null,null,false);
        $newValue=htmlFormatDateTime($newValue,null,null,false);
      } else if ($dataType=='decimal' and isset($colName) and SqlElement::isWork($colName)) {
        if ($classObj=='WorkElement' or $classObj=='TokenDefinition' or $classObj=='Resource') {
          $oldValue=Work::displayImputation($oldValue).' '.Work::displayShortImputationUnit();
          $newValue=Work::displayImputation($newValue).' '.Work::displayShortImputationUnit();
        } else {
          $oldValue=Work::displayWork($oldValue).' '.Work::displayShortWorkUnit();
          $newValue=Work::displayWork($newValue).' '.Work::displayShortWorkUnit();
        }
      } else if ($dataType=='decimal' and SqlElement::isAmount($colName)) {
        if (SqlElement::isLocal($colName)) {
          $oldValue=htmlDisplayLocalCurrency($obj->idProject, null, $oldValue);
          $newValue=htmlDisplayLocalCurrency($obj->idProject, null, $newValue);
        } else {
          $oldValue=htmlDisplayCurrency($oldValue);
          $newValue=htmlDisplayCurrency($newValue);
        }
      } else if (pq_substr($colName, -8, 8)=='Duration') {
        $oldValue=$oldValue.' '.i18n('shortDay');
        $newValue=$newValue.' '.i18n('shortDay');
      } else if (pq_substr($colName, -8, 8)=='Progress') {
        $oldValue=$oldValue.' '.i18n('colPct');
        $newValue=$newValue.' '.i18n('colPct');
      } else if ($dataLength>4000 or $refType=='Note') {
        $oldValue='<div style="max-width:'.$maxWidth.'px;overflow:auto;">'.$oldValue.'</div>';
        $newValue='<div style="max-width:'.$maxWidth.'px;overflow:auto">'.$newValue.'</div>';
      } else if ($colName=='password' or $colName=='apiKey') {
        $allstars="**********";
        if ($oldValue) $oldValue=pq_substr($oldValue, 0, 5).$allstars.pq_substr($oldValue, -5);
        if ($newValue) $newValue=pq_substr($newValue, 0, 5).$allstars.pq_substr($newValue, -5);
      } else if(pq_substr($colName, pq_strlen($colName)-4)=='Link' and (pq_substr($colName, 0, 3)=='add' or pq_substr($colName, 0, 6)=='delete')){
        if ($oldValue!=null and $oldValue!='' and intval($oldValue)) {
        	if ($oldValue==0 and $colName=='idStatus') {
        		$oldValue='';
        	} else {
        		$colNameWhitoutChar=pq_substr($colName, 3, -4);
        		if(pq_substr($colName, 0, 6)=='delete')$colNameWhitoutChar=pq_substr($colName, 6, -4);
        		$oldValue='#'.intval($oldValue).' - '.SqlList::getNameFromId($colNameWhitoutChar, intval($oldValue));
        	}
        }
        if ($newValue!=null and $newValue!='' and intval($newValue)) {
        	$colNameWhitoutChar=pq_substr($colName, 3, -4);
        	if(pq_substr($colName, 0, 6)=='delete')$colNameWhitoutChar=pq_substr($colName, 6, -4);
        	$newValue='#'.intval($newValue).' - '.SqlList::getNameFromId($colNameWhitoutChar, intval($newValue));
        }
      } else {
        // $diff=diffValues($oldValue,$newValue);
        $oldValue=htmlEncode($oldValue, 'print');
        $newValue=htmlEncode($newValue, 'print');
      }
      echo '<td class="historyData'.(($colName=="color")?' colorNameData':'').'" style="width:25%">'.$oldValue.'</td>';
      echo '<td class="historyData'.(($colName=="color")?' colorNameData':'').'" style="width:25%">'.$newValue.'</td>';
      echo '<td class="historyData'.$class.'" style="width:10%">';
      // echo formatDateThumb($creationDate, $updateDate);
      echo $date.'</td>';
      echo '<td class="historyData'.$class.'" style="border-right: 1px solid #AAAAAA;width:15%">';
      if ($user) {
        echo formatUserThumb($hist->idUser, $user, null, '16', 'left').'&nbsp;';
      }
      echo $user;
      echo '</td>';
      echo '</tr>';
      $stockDate=$hist->operationDate;
      $stockUser=$hist->idUser;
      $stockOper=$hist->operation;
    }
  }
  echo '<tr>';
  echo '<td class="historyDataClosetable" style="width:10%">&nbsp;</td>';
  echo '<td class="historyDataClosetable" style="width:15%">&nbsp;</td>';
  echo '<td class="historyDataClosetable" style="width:25%">&nbsp;</td>';
  echo '<td class="historyDataClosetable" style="width:25%">&nbsp;</td>';
  echo '<td class="historyDataClosetable" style="width:10%">&nbsp;</td>';
  echo '<td class="historyDataClosetable" style="width:15%">&nbsp;</td>';
  echo '</tr>';
  echo '</table>';
  if (!$print and !$refresh) {
    echo '</div>';
    echo '<br />';
  }
}

// ADD BY Marc TABARY - 2017-02-23 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT
/**
 * =====================================================================================
 * Draw section of an object linked by an id with the object to which we draw the detail
 * Sample : drawObjectLinkedByIdToObject($obj, 'Project', true)
 * Draw a section for projects with idxxxx (where xxxx the name of the $obj's classe)
 * --------------------------------------------------------------------------------------
 *
 * @global type $cr
 * @global type $print
 * @global type $outMode
 * @global type $comboDetail
 * @global type $displayWidth
 * @global type $printWidth
 * @param object $obj
 *          : The object's instance to which we draw the detail
 * @param object $objLinkedByIdObject
 *          : The name of the object's classe to which we draw the section
 * @param boolean $refresh          
 * @return void
 */
function drawObjectLinkedByIdToObject($obj, $objLinkedByIdObject='', $refresh=false) {
  global $cr, $print, $outMode, $comboDetail, $displayWidth, $printWidth;
  if ($comboDetail) {
    return;
  }
  
  if (!class_exists($objLinkedByIdObject)) {
    return;
  }
  
  // ADD BY Marc TABARY - 2017-03-10 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - href
  $goto='';
  // END ADD BY Marc TABARY - 2017-03-10 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - href
  $theClassName='_'.$objLinkedByIdObject;
  // Get the visible list of linked Object
  $listVisibleLinkedObj=getUserVisibleObjectsList($objLinkedByIdObject);
//MTY - LEAVE SYSTEM 
  if ($obj->idle==1) {
    $canUpdate=false;
  } else {
    $canUpdate = true;
  }      
  if ($canUpdate) {
    $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  }    
  if ($canUpdate) {
    $canUpdate=securityGetAccessRightYesNo('menu'.$objLinkedByIdObject, 'update', $obj)=="YES";
  }
  if ($canUpdate) {
    // MTY - Test if attribute of the LinkedByIdObject is readonly => If it's , can't update  
    $theObjClass = get_class($obj);
    if (pq_strpos($obj->getFieldAttributes($theClassName),"readonly")!==false) {
        $canUpdate = false;
    }
  }  
  if (isset($obj->$theClassName)) {
    $objects=$obj->$theClassName;
  } else {
    $objects=array();
  }
  if (get_class($obj) =='Organization'){
    $listContact = SqlList::getListWithCrit("Affectable", array("idOrganization"=>$obj->id, "isContact"=>1, "isResource"=>0));
    $objectsContact=array();
    foreach ($listContact as $id => $name){
      $contact = new Contact($id);
      $objectsContact[] = $contact;
    }
  }
  if (!$refresh and !$print) echo '<tr><td colspan="2">';
  echo '<input type="hidden" id="objectIdle" value="'.htmlEncode($obj->idle).'" />';
  
  if (!$print) {
    echo '<table width="99.9%">';
  }
  echo '<tr>';
  if (!$print) {
    echo '<td class="assignHeader smallButtonsGroup" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      // Parameters passed at addLinkObjectToObject
      // 1 - The main object's class name
      // 2 - The id of main object
      // 3 - The linked object's class name
      echo '<a onClick="addLinkObjectToObject(\''.get_class($obj).'\',\''.htmlEncode($obj->id).'\',\''.$objLinkedByIdObject.'\');" title="'.i18n('addLinkObject').'" >'.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:5%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader sortable" style="width:'.(($print)?'85':'80').'%;cursor:pointer"  onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  // ADD BY Marc TABARY - 2017-03-16 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - idle
  echo '<td class="assignHeader" style="width:'.(($print)?'10':'10').'%">'.i18n('colIdle').'</td>';
  // ADD BY Marc TABARY - 2017-03-16 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - idle
  echo '</tr>';
  $nbObjects=0;
  foreach ($objects as $theObj) {
    if (! pq_array_key_exists($theObj->id, $listVisibleLinkedObj)) continue;
    $nbObjects++;
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData smallButtonsGroup">';
      if (!$print and $canUpdate and pq_array_key_exists($theObj->id, $listVisibleLinkedObj)) {        
        // Implement to following rule :
        // A manager of an organization can't be remove from it
        if (get_class($obj)=='Organization' and get_class($theObj)=='Resource' and $obj->idResource==$theObj->id) {
          echo ' <a title="'.i18n('isOrganizationManager').'" >'.formatSmallButton('Blocked').'</a>';
        } else {
          // ADD BY Marc TABARY - 2017-03-16 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - idle
          if ($theObj->idle==0) {
            // END ADD BY Marc TABARY - 2017-03-16 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - idle
            // Parameters passed at removeLinkObjectFromObject
            // 1 - The main object's class name
            // 2 - The linked object's class name
            // 3 - The id of the selected linked object
            // 4 - The name of the selected linked object
            if ($objLinkedByIdObject=='Resource') $objLinkedByIdObject='Affectable';
            echo ' <a onClick="removeLinkObjectFromObject(\''.get_class($obj).'\',\''.$objLinkedByIdObject.'\',\''.htmlEncode($theObj->id).'\',\''.htmlEncode($theObj->name).'\');" title="'.i18n('removeLinkObject').'" > '.formatSmallButton('Remove').'</a>';
          }
        }
      }
      echo '</td>';
    }
    if (pq_array_key_exists($theObj->id, $listVisibleLinkedObj)) {
      $classSub=get_class($theObj);
      if ($classSub=='ResourceAll') $classSub=($theObj->isResourceTeam)?'ResourceTeam':'Resource';
      if (!$print and securityCheckDisplayMenu(null, $classSub) and securityGetAccessRightYesNo('menu'.$classSub, 'read', '')=="YES") {
        if($theObj->isMaterial == "1"){
          $goto=' onClick="gotoElement(\'ResourceMaterial\',\''.htmlEncode($theObj->id).'\');" ';
        }else{
          $goto=' onClick="gotoElement(\''.$classSub.'\',\''.htmlEncode($theObj->id).'\');" ';
        }
      }
      
      echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:5%" '.$goto.'>#'.htmlEncode($theObj->id).'</td>';
      // ADD BY Marc TABARY - 2017-03-10 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - href

      // END ADD BY Marc TABARY - 2017-03-10 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - href
      // CHANGE BY Marc TABARY - 2017-03-10 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - href
      echo '<td '.$goto.' class="assignData hyperlink '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:'.(($print)?'85':'80').'%">'.htmlEncode($theObj->name).'</td>';
      // Old
      // echo '<td class="assignData" style="width:' . (($print)?'95':'85') . '%">' . htmlEncode($theObj->name) . '</td>';
      // END CHANGE BY Marc TABARY - 2017-03-10 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - href
    } else {
      echo '<td class="assignData" style="width:5%"></td>';
      echo '<td class="assignData" style="width:'.(($print)?'85':'80').'%">'.i18n('isNotVisible').'</td>';
    }
    // ADD BY Marc TABARY - 2017-03-16 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - idle
    echo '<td class="assignData dijitButtonText" style="width:'.(($print)?'10':'10').'%">'.htmlDisplayCheckbox($theObj->idle).'</td>';
    // END ADD BY Marc TABARY - 2017-03-16 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT - idle
    
    echo '</tr>';
  }
  
  foreach ($objectsContact as $theObj) {
    $nbObjects++;
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData smallButtonsGroup">';
      if (!$print and $canUpdate) {
        if ($theObj->idle==0) {
          if ($objLinkedByIdObject=='Resource') $objLinkedByIdObject='Affectable';
            echo ' <a onClick="removeLinkObjectFromObject(\''.get_class($obj).'\',\''.$objLinkedByIdObject.'\',\''.htmlEncode($theObj->id).'\',\''.htmlEncode($theObj->name).'\');" title="'.i18n('removeLinkObject').'" > '.formatSmallButton('Remove').'</a>';
        } 
      }
      echo '</td>';
    }
    $classSub=get_class($theObj);
    if ($classSub=='ResourceAll') $classSub=($theObj->isResourceTeam)?'ResourceTeam':'Resource';
    if (!$print and securityCheckDisplayMenu(null, $classSub) and securityGetAccessRightYesNo('menu'.$classSub, 'read', '')=="YES") {
      $goto=' onClick="gotoElement(\''.$classSub.'\',\''.htmlEncode($theObj->id).'\');" ';
    }
    echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:5%" '.$goto.'>#'.htmlEncode($theObj->id).'</td>';
    echo '<td '.$goto.' class="assignData hyperlink '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:'.(($print)?'85':'80').'%">'.htmlEncode($theObj->name).'</td>';
    echo '<td class="assignData dijitButtonText" style="width:'.(($print)?'10':'10').'%">'.htmlDisplayCheckbox($theObj->idle).'</td>';
    echo '</tr>';
  }

  if (!$print) {
    echo '</table>';
  }
  if (!$refresh and !$print) echo '</td></tr>';
  if (!$print) {
    echo '<input id="ObjectSectionCount" type="hidden" value="'.$nbObjects.'" />';
  }
}
// END ADD BY Marc TABARY - 2017-02-23 - DRAW LIST OF OBJECTS LINKED BY ID TO MAIN OBJECT

// BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
/**
 * =====================================================================================
 * Draw section of Notification for the object passed in parameter
 * --------------------------------------------------------------------------------------
 *
 * @global type $print
 * @global type $comboDetail
 * @param object $obj
 *          : The object's instance to which we draw the notifications
 * @param boolean $unreadOnly
 *          : If True, draw only the unread notifications
 * @param boolean $refresh          
 * @return void
 */
function drawNotificationsLinkedToObject($obj, $unreadOnly=true, $refresh=false) {
  global $print, $comboDetail;
  if ($comboDetail) {
    return;
  }
  
  if (get_class($obj)===null) {
    return;
  }
  
  $notificationObjClass=get_class($obj);
  
  // The 'unread' status
  // $idStatus = SqlElement::getSingleSqlElementFromCriteria("Status", array("name" => "unread"))->id;
  $idStatusNotification=1;
  
  // The notifiable's id
  $idNotificationObjClass=SqlElement::getSingleSqlElementFromCriteria("Notifiable", array("notifiableItem"=>$notificationObjClass))->id;
  
  // The connected user
  $userId=getSessionUser()->id;
  
  $crit=array('idle'=>'0', 'idNotifiable'=>$idNotificationObjClass, 'idUser'=>$userId, 'notifiedObjectId'=>$obj->id);
  
  if ($unreadOnly) {
    // $crit['idStatus'] = $idStatus;
    $crit['idStatusNotification']=$idStatusNotification;
  }
  
  $notif=new Notification();
  $list=$notif->getSqlElementsFromCriteria($crit);
  
  $canUpdate=securityGetAccessRightYesNo('menuNotification', 'update')=="YES";
  if (!$refresh) {
    echo '<tr><td colspan="4">';
  }
  echo '<table style="width:100%;">';
  echo '<tr>';
  $listClass='Notification';
  echo '<td class="linkHeader" style="width:10%">'.i18n('colId').'</td>';
  echo '<td class="linkHeader sortable" style="width:50%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="linkHeader" style="width:20%">'.i18n('colType').'</td>';
  echo '<td class="linkHeader" style="width:20%">'.i18n('colIdStatus').'</td>';
  echo '</tr>';
  
  foreach ($list as $notif) {
    
    $notificationDefinition=new NotificationDefinition($notif->idNotificationDefinition);
    
    $canGoto=(securityCheckDisplayMenu(null, $listClass) and securityGetAccessRightYesNo('menu'.$listClass, 'read', $notif)=="YES")?true:false;
    echo '<tr>';
    $classCompName=i18n($listClass);
    echo '<td class="linkData" style="white-space:nowrap;width:10%">&nbsp;#'.$notif->id.'</td>';
    $goto="";
    if (!$print and $canGoto) {
      $goto=' onClick="gotoElement('."'".$listClass."','".htmlEncode($notif->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="position:relative;width:50%">';
    echo htmlEncode($notificationDefinition->name);
    echo '</td>';
    echo '<td class="linkData colorNameData" style="position:relative;width:20%;">';
    echo colorNameFormatter(i18n(SqlList::getNameFromId('Type', $notif->idNotificationType))."#split#".SqlList::getFieldFromId('Type', $notif->idNotificationType, 'color'));
    echo '</td>';
    $changeStatus='';
    if (!$print and $canUpdate) {
      $changeStatus=' onClick="changeStatusNotification('."'".htmlEncode($notif->id)."','".htmlEncode($notif->idStatusNotification)."'".');" style="cursor:pointer;" ';
    }
    echo '<td class="linkData colorNameData" '.$changeStatus.' style="position:relative;width:20%;">';
    echo colorNameFormatter(i18n(SqlList::getNameFromId('StatusNotification', $notif->idStatusNotification))."#split#".SqlList::getFieldFromId('StatusNotification', $notif->idStatusNotification, 'color'));
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="NotificationSectionCount" type="hidden" value="'.count($list).'" />';
  }
}// END - ADD BY TABARY - NOTIFICATION SYSTEM
function drawNotesFromObject($obj, $refresh=false) {
  global $cr, $print, $outMode, $user, $comboDetail, $displayWidth, $printWidth, $preseveHtmlFormatingForPDF;
  $widthPct=setWidthPct($displayWidth, $print, $printWidth, $obj);
  $widthPctNote=((intval($widthPct)-2)*0.85)-40;
  if (RequestHandler::isCodeSet('refreshNotes')) $widthPctNote+=30;
  $widthPctNote.='px';
  //$widthPctNote=((pq_substr($widthPct, 0, pq_strlen($widthPct)-2)*0.85)+5).'px';
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $userNote = $user->getProfile($obj);
  $canAddNoteClosedElement = SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$userNote,'scope'=>'canAddNoteClosedEl'));
  $canAddNoteReadOnlyElement = SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$userNote,'scope'=>'canAddNoteReadOnlyEl'));
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (isset($obj->_Note)) {
    $notes=$obj->_Note;
  } else {
    $notes=array();
  }
  if (!$refresh and !$print) echo '<tr><td colspan="2">';
  echo '<input type="hidden" id="noteIdle" value="'.htmlEncode($obj->idle).'" />';
  if (!$print) {
    echo '<table width="100%">';
  }
  echo '<tr>';
  $canAddNote = ($canUpdate or ($obj->idle==1 and $canAddNoteClosedElement->rightAccess=='1') or ($canAddNoteReadOnlyElement->rightAccess=='1' and $obj->idle!=1))?true:false;
  if (!$print) {
    echo '<td class="noteHeader smallButtonsGroup" style="width:10%">';
    if ($obj->id!=null and !$print) {
      $styleAdd = ($canAddNote)?'':'display:none;';
      $styleFS = ($canAddNote)?'':'margin-top:-8px;';
      $noteFunction = "changeNoteSize(" . "'" . get_class($obj) . "'" . ");";
      echo '<a style="position:absolute;right:10px;'.$styleFS.'" onClick=' . $noteFunction . ' title="Change size">'.formatSmallButton('ButtonCollapseOpen', true).'</a>';
      echo '<a onClick="addNote(false);" title="'.i18n('addNote').'" style="'.$styleAdd.'">'.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="noteHeader" style="width:5%">'.i18n('colId').'</td>';
  echo '<td colspan="6" class="noteHeader" style="width:'.(($print)?'95':'85').'%">'.i18n('colNote').'</td>';
  // echo '<td class="noteHeader" style="width:15%">' . i18n ( 'colDate' ) . '</td>';
  // echo '<td class="noteHeader" style="width:15%">' . i18n ( 'colUser' ) . '</td>';
  echo '</tr>';
  $nbNotes=0;
  $ress=new Resource($user->id);
  //damian
  $noteDiscussionMode = Parameter::getUserParameter('userNoteDiscussionMode');
  if($noteDiscussionMode == null){
  	$noteDiscussionMode = Parameter::getGlobalParameter('globalNoteDiscussionMode');
  }
  
  if($noteDiscussionMode == 'YES'){
    $notes = sortNotesRecentBranchFirst($notes);
  }
  foreach ($notes as $note) {
    //florent
    $userCanChange=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$user->idProfile,'scope'=>'canChangeNote'));
    if ($user->id==$note->idUser or $note->idPrivacy==1 or ($note->idPrivacy==2 and $ress->idTeam==$note->idTeam)   ) {
    //
      $nbNotes++;
      $userId=$note->idUser;
      $userName=SqlList::getNameFromId('Affectable', $userId);
      $creationDate=$note->creationDate;
      $updateDate=$note->updateDate;
      if ($updateDate==null) {
        $updateDate='';
      }
      echo '<tr>';
      if (!$print) {
      	echo '<td class="noteData smallButtonsGroup">';
      	if ($obj->id!=null and !$print and ($canUpdate or ($canAddNote and $note->idUser==$user->id))) {
      		echo ' <a onClick="addNote(true,'.htmlEncode($note->id).');" title="'.i18n('replyToThisNote').'" > '.formatSmallButton('Reply').'</a>';
      	}
      	if (($note->idUser==$user->id or $userCanChange->rightAccess=='1') and !$print and ($canUpdate or ($canAddNote and $note->idUser==$user->id))) {
      		echo ' <a onClick="editNote('.htmlEncode($note->id).','.htmlEncode($note->idPrivacy).');" title="'.i18n('editNote').'" > '.formatSmallButton('Edit').'</a>';
      		echo ' <a onClick="removeNote('.htmlEncode($note->id).');" title="'.i18n('removeNote').'" > '.formatSmallButton('Remove').'</a>';
      	}
      	echo '</td>';
      }
      echo '<td class="noteData" style="width:5%; text-align: center;">#'.htmlEncode($note->id).'</td>';
      if($noteDiscussionMode == 'YES'){
        for($i=0; $i<$note->replyLevel; $i++){
        	if($i >= 5){
        		break;
        	}
        	echo '<td class="noteData" colspan="1" style="width:3%;border-bottom:0px;border-top:0px;border-right:solid 2px;!important;"></td>';//border-bottom:0px;border-top:0px;!important
        }
        echo '<td colspan="'.(6-$note->replyLevel).'" class="noteData" style="width:'.(($print)?(95-(3*$note->replyLevel)):(85-(3*$note->replyLevel))).'%">';
      }else{
        echo '<td colspan="6" class="noteData" style="width:'.(($print)?'95':'85').'%">';
      }
      echo "<div style='right:".((isNewGui())?'10':'3')."px;top:2px;'>";
      echo formatUserThumb($userId, $userName, 'Creator');
      echo formatDateThumb($creationDate, $updateDate);
      echo formatPrivacyThumb($note->idPrivacy, $note->idTeam);
      if($noteDiscussionMode != 'YES'){
        if($note->idNote != null){
          if ($print) {
        	  echo '<span style="position:relative;float:left;white-space:nowrap">'.formatIcon('Reply', 16, i18n('replyToNote').' #'.$note->idNote).'</span>';
        	  if ($outMode=="pdf") {
        	    echo '<span style="position:relative;height:18px;">&nbsp;'.i18n('replyToNote').' #'.$note->idNote.'</span><br/>';
        	  } else {
        	    echo '<div style="position:relative;height:18px;">&nbsp;'.i18n('replyToNote').' #'.$note->idNote.'</div>';
        	  }
          } else {
            echo '<span style="position:relative;float:right;padding-right:3px">'.formatIcon('Reply', 16, i18n('replyToNote').' #'.$note->idNote).'</span>';
          }
        }
      }
      echo "</div>";
      if (!$print) echo '<div style="min-height:23px;max-width:'.$widthPctNote.';overflow-x:auto;" >';
      $strDataHTML=$note->note;
      $strDataHTML=pq_str_replace(array('<style','/style>'),array('<nostyle','/nostyle>'),$strDataHTML);
      if ($print and $outMode=="pdf") {
        if ($strDataHTML) $strDataHTML=preg_replace("/\<([a-zA-Z0-9-]*@[a-zA-Z0-9-]*\.[a-zA-Z0-9-]*)\>/", "&lt;$1&gt;", $strDataHTML);
      	if ($preseveHtmlFormatingForPDF) {
      	} else {
      		$strDataHTML=htmlEncode($strDataHTML, 'pdf');
      	}
      } else {
//       	if (!isTextFieldHtmlFormatted($strDataHTML)) {
//       		$strDataHTML=htmlEncode($strDataHTML, 'plainText');
//       	} else {
      		$strDataHTML=preg_replace('@(https?://([-\w\.]<+[-\w])+(:\d+)?(/([\w/_\.#-]*(\?\S+)?[^\.\s])?)?)@', '<a href="$1" target="_blank">$1</a>', pq_nvl($strDataHTML));
//         }
      	//$sub = pq_substr($strDataHTML, pq_strpos($strDataHTML,'src="')+pq_strlen('scr="'),pq_strlen($strDataHTML));
      	//$imageUrl = pq_substr($sub,$sub+5,pq_strpos($sub,'.png"')+4);
      	//$imageName = pq_substr($imageUrl,pq_strpos($imageUrl,'../files/images/')+pq_strlen('../files/images/'),pq_strpos($sub,'.png"')+4);
      	//$strDataHTML = pq_str_replace('<img', '<img onClick="showImage(\'Note\',\''.$imageUrl.'\',\''.$imageName.'\');"', $strDataHTML);
      	if (!$print) $strDataHTML=htmlSetClickableImages($strDataHTML,(intval($widthPctNote)-32).'px');
      }
      echo $strDataHTML;
      if (!$print) echo '</div>';
      echo '</td>';
      echo '</tr>';
    }
  }
  echo '<tr>';
  if (!$print) {
    echo '<td colspan = "6" class="noteDataClosetable">&nbsp;</td>';
  }
  echo '<td colspan="'.(($print)?'2':'3').'" class="noteDataClosetable">&nbsp;</td>';
  echo '</tr>';
  if (!$print) {
    echo '</table>';
  }
  if (!$refresh and !$print) echo '</td></tr>';
  if (!$print) {
    echo '<input id="NoteSectionCount" type="hidden" value="'.count($notes).'" />';
  }
}

function drawBillLinesFromObject($obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $widthPct;
  $canUpdate=securityGetAccessRightYesNo('menu' . get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  $lock=false;
  if ($obj->done or $obj->idle or (property_exists($obj, 'billingType') and $obj->billingType=="N")) {
    $lock=true;
  }
  if (isset($obj->_BillLine)) {
    $lines=$obj->_BillLine;
  } else {
    $lines=array();
  }
  if (!$print) {
    echo '<input type="hidden" id="billLineIdle" value="'.htmlEncode($obj->idle).'" />';
    if ($refresh) echo '<table width="100%">';
  }
  echo '<tr>';
  $billingType='M';
  if (property_exists($obj, 'billingType') and $obj->billingType) {
    $billingType=$obj->billingType;
  }
  if (!$print) {
    echo '<td class="noteHeader" style="width:5%;white-space:nowrap">'; // changer le header
    if ($obj->id!=null and !$print and !$lock and $canUpdate) {
      echo '<a onClick="addBillLine(\'M\');" title="'.i18n('addLine').'" > '.formatSmallButton('Add').'</a>';
      if ($billingType!='M') {
        // echo '<a onClick="addBillLine(\''.$billingType.'\');" title="' . i18n('addFormattedBillLine') . '" style="cursor: pointer;display: inline-block;margin-left:5px;" class="roundedButtonSmall"> '.formatIcon('Bill',16).'</a>';
        echo '<a onClick="addBillLine(\''.$billingType.'\');" title="'.i18n('addFormattedBillLine').'" > '.formatSmallButton('Bill', true).'</a>';
      }
    }
    echo '</td>';
  }
  $extraLocalClass=($obj->hasCurrency())?' localLabelClass ':'';
  echo '<td class="noteHeader" style="width:5%">'.i18n('colId').'</td>';
  echo '<td class="noteHeader" style="width:5%">'.i18n('colLineNumber').'</td>';
  echo '<td class="noteHeader" style="width:20%">'.i18n('colDescription').'</td>';
  echo '<td class="noteHeader" style="width:25%">'.i18n('colDetail').'</td>';
  echo '<td class="noteHeader '.$extraLocalClass.'" style="width:10%">'.i18n('colUnitPrice').'</td>';
  echo '<td class="noteHeader" style="width:10%">'.i18n('colQuantity').'</td>';
  echo '<td class="noteHeader '.$extraLocalClass.'" style="width:10%">'.pq_strtolower(i18n('sum')).'</td>';
  if (get_class($obj)!='Tender' and get_class($obj)!='ProviderOrder' and get_class($obj)!='ProviderBill') {
    echo '<td class="noteHeader" style="width:15%">'.i18n('colDays').'</td>';
  }
  echo '</tr>';
  
  $fmt=getNumberFormatter52($browserLocale, NumberFormatter52::INTEGER);
  $fmtd=getNumberFormatter52($browserLocale, NumberFormatter52::DECIMAL);
  $lines=array_reverse($lines);
  foreach ($lines as $line) {
    $unit=new MeasureUnit($line->idMeasureUnit);
    echo '<tr>';
    if (!$print) {
      echo '<td class="noteData" style="text-align:center;white-space:nowrap">';
      if ($lock==0) {
        echo ' <a onClick="editBillLine('.htmlEncode($line->id).',\''.htmlEncode(($line->billingType)?$line->billingType:$billingType).'\');" ';
        echo '  title="'.i18n('editLine').'" > '.formatSmallButton('Edit').'</a>';
        if (get_class($obj)=='ProviderOrder') {
          $providerTerm=new ProviderTerm();
          $listProvTerm=$providerTerm->getSqlElementsFromCriteria(array("idProviderOrder"=>$obj->id));
          $billLineTerm=new BillLine();
          $hide=false;
          foreach ($listProvTerm as $providerTerms) {
            $billLineList=$billLineTerm->getSqlElementsFromCriteria(array("refType"=>"ProviderTerm", "refId"=>$providerTerms->id));
            if ($billLineList) {
              $hide=true;
            }
          }
          if ($hide==false) {
            echo ' <a onClick="removeBillLine('.htmlEncode($line->id).');"'.' ';
            echo '  title="'.i18n('removeLine').'" > '.formatSmallButton('Remove').'</a>';
          }
        } else {
          echo ' <a onClick="removeBillLine('.htmlEncode($line->id).');"'.' ';
          echo '  title="'.i18n('removeLine').'" > '.formatSmallButton('Remove').'</a>';
        }
      }
      echo '</td>';
    }
    echo '<td class="noteData" style="width:5%">#'.htmlEncode($line->id).'</td>';
    echo '<td class="noteData" style="width:5%">'.htmlEncode($line->line).'</td>';
    echo '<td class="noteData" style="width:20%">'.htmlEncode($line->description, 'withBR');
    if (!$print) {
      echo '<input type="hidden" id="billLineDescription_'.htmlEncode($line->id).'" value="'.htmlEncode($line->description).'" />';
    }
    echo '</td>';
    echo '<td class="noteData" style="width:25%">'.htmlEncode($line->detail, 'withBR');
    if (!$print) {
      echo '<input type="hidden" id="billLineDetail_'.htmlEncode($line->id).'" value="'.htmlEncode($line->detail).'" />';
    }
    echo '</td>';
    $unitPrice=($unit->name)?' / '.$unit->name:'';
    $hasLocal=Project::hasProjectCurrency($obj->idProject);
    echo '<td class="noteData" style="width:10%">'.htmlDisplayLocalCurrency($obj->idProject,$line->price,$line->priceLocal).$unitPrice.'</td>';
    $unitQuantity=($unit->name)?' '.(($line->quantity>1)?$unit->pluralName:$unit->name):'';
    echo '<td class="noteData" style="width:10%">'.htmlDisplayNumericWithoutTrailingZeros($line->quantity).$unitQuantity.'</td>';
    echo '<td class="noteData" style="width:10%">'.htmlDisplayLocalCurrency($obj->idProject,$line->amount,$line->amountLocal).'</td>';
    if (get_class($obj)!='Tender' and get_class($obj)!='ProviderOrder' and get_class($obj)!='ProviderBill') {
      echo '<td class="noteData" style="width:15%">'.htmlDisplayNumericWithoutTrailingZeros($line->numberDays).'</td>';
    }
    echo '</tr>';
  }
  echo '<tr>';
  if (!$print) {
    echo '<td class="noteDataClosetable">&nbsp;</td>';
  }
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '</tr>';
  if (!$print) {
    if ($refresh) echo '</table>';
  }
}

function drawBillLinesProviderTerms($obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $widthPct;
  if (get_class($obj)=='ProviderBill') {
    $providerTerm=new ProviderTerm();
    $listProvTerm=$providerTerm->getSqlElementsFromCriteria(array("idProviderBill"=>$obj->id));
    $lines=array();
    $i=0;
    foreach ($listProvTerm as $term) {
      $providerTerm=new ProviderTerm($term->id);
      if ($providerTerm->idProviderOrder) {
        $providerOrder=new ProviderOrder($providerTerm->idProviderOrder);
        $discountRate[$i]=$providerOrder->discountRate;
      } else {
        $discountRate[$i]=0;
      }
      $i++;
      array_push($lines, $providerTerm->_BillLineTerm);
    }
  } else {
    if (isset($obj->_BillLineTerm)) {
      $providerBill=new ProviderBill($obj->idProviderBill);
      $lines=$obj->_BillLineTerm;
    } else {
      $lines=array();
    }
  }
  if (!$print) {
    echo '<input type="hidden" id="billLineIdle" value="'.htmlEncode($obj->idle).'" />';
    if ($refresh) echo '<table width="100%">';
  }
  echo '<tr>';
  echo '  <td class="noteHeader" style="width:5%">'.i18n('colId').'</td>';
  echo '  <td class="noteHeader" style="width:5%">'.i18n('colLineNumber').'</td>';
  echo '  <td class="noteHeader" style="width:20%">'.i18n('colDescription').'</td>';
  echo '  <td class="noteHeader" style="width:20%">'.i18n('colDetail').'</td>';
  echo '  <td class="noteHeader" style="width:10%">'.i18n('colInitialAmount').'</td>';
  echo '  <td class="noteHeader" style="width:8%">'.i18n('colRate').'</td>';
  echo '  <td class="noteHeader" style="width:8%">'.i18n('colTermAmount').'</td>';
  echo '  <td class="noteHeader" style="width:8%">'.i18n('colDiscount').'</td>';
  echo '  <td class="noteHeader" style="width:8%">'.i18n('colTaxAmount').'</td>';
  echo '  <td class="noteHeader" style="width:8%">'.i18n('colFullAmount').'</td>';
  echo '</tr>';
  
  $fmt=getNumberFormatter52($browserLocale, NumberFormatter52::INTEGER);
  $fmtd=getNumberFormatter52($browserLocale, NumberFormatter52::DECIMAL);
  $discountRate=0;
  if (get_class($obj)!='ProviderBill') {
    $lines=array_reverse($lines);
    if (isset($obj->idProviderOrder)) {
      $providerOrder=new ProviderOrder($obj->idProviderOrder);
      $discountRate=$providerOrder->discountRate;
    }
  }
  if (get_class($obj)=='ProviderBill') {
    $i=0;
    foreach ($lines as $line) {
      foreach ($line as $linee) {
        $billLine=new BillLine($linee->idBillLine);
        $unit=new MeasureUnit($linee->idMeasureUnit);
        if ($linee->rate==0) {
          continue;
        }
        echo '<tr>';
        echo '<td class="noteData" style="width:5%">#'.htmlEncode($linee->id).'</td>';
        echo '<td class="noteData" style="width:5%">'.htmlEncode($billLine->line).'</td>';
        echo '<td class="noteData" style="width:20%">'.htmlEncode($billLine->description, 'withBR');
        if (!$print) {
          echo '<input type="hidden" id="billLineDescription_'.htmlEncode($linee->id).'" value="'.htmlEncode($linee->description).'" />';
        }
        echo '</td>';
        echo '<td class="noteData" style="width:20%">'.htmlEncode($billLine->detail, 'withBR');
        if (!$print) {
          echo '<input type="hidden" id="billLineDetail_'.htmlEncode($linee->id).'" value="'.htmlEncode($linee->detail).'" />';
        }
        echo '</td>';
        echo '<td class="noteData" style="width:10%">'.htmlDisplayLocalCurrency($obj->idProject, $billLine->amount, $billLine->amountLocal).'</td>';
        echo '<td class="noteData" style="width:8%">'.htmlDisplayPct($linee->rate).'</td>';
        echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,$linee->price, $linee->priceLocal).'</td>';
        echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,$linee->price*$discountRate/100,$linee->priceLocal*$discountRate/100).'</td>';
        echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,(($linee->price)-($linee->price*$discountRate/100))*$obj->taxPct/100,(($linee->priceLocal)-($linee->priceLocal*$discountRate/100))*$obj->taxPct/100).'</td>';
        echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,(($linee->price)-($linee->price*$discountRate/100))*$obj->taxPct/100+($linee->price-($linee->price*$discountRate/100)),(($linee->priceLocal)-($linee->priceLocal*$discountRate/100))*$obj->taxPct/100+($linee->priceLocal-($linee->priceLocal*$discountRate/100))).'</td>';
        echo '</tr>';
      }
      $i++;
    }
  } else {
    foreach ($lines as $linee) {
      $billLine=new BillLine($linee->idBillLine);
      $unit=new MeasureUnit($linee->idMeasureUnit);
      echo '<tr>';
      echo '<td class="noteData" style="width:5%">#'.htmlEncode($linee->id).'</td>';
      echo '<td class="noteData" style="width:5%">'.htmlEncode($billLine->line).'</td>';
      echo '<td class="noteData" style="width:20%">'.htmlEncode($billLine->description, 'withBR');
      if (!$print) {
        echo '<input type="hidden" id="billLineDescription_'.htmlEncode($linee->id).'" value="'.htmlEncode($linee->description).'" />';
      }
      echo '</td>';
      echo '<td class="noteData" style="width:20%">'.htmlEncode($billLine->detail, 'withBR');
      if (!$print) {
        echo '<input type="hidden" id="billLineDetail_'.htmlEncode($linee->id).'" value="'.htmlEncode($linee->detail).'" />';
      }
      echo '</td>';
      echo '<td class="noteData" style="width:10%">'.htmlDisplayLocalCurrency($obj->idProject,$billLine->amount,$billLine->amountLocal).'</td>';
      echo '<td class="noteData" style="width:8%">'.htmlDisplayPct($linee->rate).'</td>';
      echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,$linee->price,$linee->priceLocal).'</td>';
      echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,$linee->price*$discountRate/100,$linee->priceLocal*$discountRate/100).'</td>';
      echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,(($linee->price)-($linee->price*$discountRate/100))*$obj->taxPct/100,(($linee->priceLocal)-($linee->priceLocal*$discountRate/100))*$obj->taxPct/100).'</td>';
      echo '<td class="noteData" style="width:8%">'.htmlDisplayLocalCurrency($obj->idProject,(($linee->price)-($linee->price*$discountRate/100))*$obj->taxPct/100+($linee->price-($linee->price*$discountRate/100)),(($linee->priceLocal)-($linee->priceLocal*$discountRate/100))*$obj->taxPct/100+($linee->priceLocal-($linee->priceLocal*$discountRate/100))).'</td>';
      echo '</tr>';
      $newRefId=$linee->refId;
    }
  }
  
  echo '<tr>';
  if (!$print) {
    echo '<td class="noteDataClosetable">&nbsp;</td>';
  }
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '</tr>';
  if (!$print) {
    if ($refresh) echo '</table>';
  }
}

function drawChecklistDefinitionLinesFromObject($obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $outMode;
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (isset($obj->_ChecklistDefinitionLine)) {
    $lines=$obj->_ChecklistDefinitionLine;
  } else {
    $lines=array();
  }
  echo '<input type="hidden" id="ChecklistDefinitionIdle" value="'.htmlEncode($obj->idle).'" />';
  echo '<table width="100%">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="noteHeader" style="width:5%">'; // changer le header
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addChecklistDefinitionLine('.htmlEncode($obj->id).');"'.' title="'.i18n('addLine').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="noteHeader sortable" style="width:25%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="noteHeader" style="width:'.(($print)?'65':'60').'%">'.i18n('colChoices').'</td>';
  echo '<td class="noteHeader" style="width:5%">'.i18n('colRequiredShort').'</td>';
  echo '<td class="noteHeader" style="width:5%">'.i18n('colExclusiveShort').'</td>';
  
  echo '</tr>';
  
  usort($lines, "ChecklistDefinitionLine::sort");
  foreach ($lines as $line) {
    
    echo '<tr>';
    if (!$print) {
      echo '<td class="noteData" style="width:5%;text-align:center;white-space:nowrap">';
      if ($canUpdate) {
        echo ' <a onClick="editChecklistDefinitionLine('.htmlEncode($obj->id).','.htmlEncode($line->id).');"'.' title="'.i18n('editLine').'" > '.formatSmallButton('Edit').'</a>';
        echo ' <a onClick="removeChecklistDefinitionLine('.htmlEncode($line->id).');"'.' title="'.i18n('removeLine').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    if ($line->check01) {
      echo '<td class="noteData" style="width:25%;border-right:0; text-align:right" title="'.htmlEncode($line->title).'">';
      if ($outMode!='pdf') echo '<div style="position: relative;">';
      echo htmlEncode($line->name);
      if ($outMode!='pdf') echo '<div style="position:absolute;top:0px; left:0px; color: #AAAAAA;">'.htmlEncode($line->sortOrder).'</div>';
      echo Tool::getDoublePoint();
      if ($outMode!='pdf') echo '</div>';
      echo '</td>';
      echo '<td class="noteData" style="width:'.(($print)?'65':'60').'%;border-left:0;">';
      echo '<table witdh="100%"><tr>';
      for ($i=1; $i<=5; $i++) {
        $check='check0'.$i;
        $title='title0'.$i;
        echo '<td style="min-width:100px;float:left; white-space:nowrap;vertical-align:top; " '.(($line->$title)?'title="'.$line->$title.'"':'').'>';
        if ($line->$check) {
          echo "<table><tr><td>".htmlDisplayCheckbox(0)."&nbsp;</td><td valign='top'>".$line->$check."&nbsp;&nbsp;</td></tr></table>";
        }
        echo '</td>';
      }
      echo '</tr></table>';
      echo '</td>';
      echo '<td class="noteData" style="width:5%;">'.htmlDisplayCheckbox($line->required).'</td>';
      echo '<td class="noteData" style="width:5%;">'.htmlDisplayCheckbox($line->exclusive).'</td>';
    } else {
      echo '<td class="reportTableHeader" colspan="4" style="width:'.(($print)?'100':'95').'%,text-align:center" title="'.htmlEncode($line->title).'">'.htmlEncode($line->name).'</td>';
    }
    echo '</tr>';
  }
  echo '<tr>';
  if (!$print) {
    echo '<td class="noteDataClosetable">&nbsp;</td>';
  }
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '</tr>';
  echo '</table>';
}

function drawAttachmentsFromObject($obj, $refresh=false) {
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  echo '<input type="hidden" id="attachmentIdle" value="'.htmlEncode($obj->idle).'" />';
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  $userCanDeleteAttachment=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther',array('idProfile'=>$user->idProfile,'scope'=>'canDeleteAttachment'));
//   if($canUpdate==false){
//     $canUpdate=true;
//   }
  if (isset($obj->_Attachment)) {
    $attachments=$obj->_Attachment;
  } else {
    $attachments=array();
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table width="100%">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="attachmentHeader smallButtonsGroup" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addAttachment(\'file\');" title="'.i18n('addAttachment').'"> '.formatSmallButton('Add').'</a>';
      echo '<a onClick="addAttachment(\'link\');" title="'.i18n('addHyperlink').'" > '.formatSmallButton('Link').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="attachmentHeader" style="width:5%">'.i18n('colId').'</td>';
  echo '<td colspan="2" class="attachmentHeader" style="width:'.(($print)?'95':'85').'%">'.i18n('colFile').'</td>';
  echo '</tr>';
  foreach ($attachments as $key=>$attachment) {
   if ($attachment->isProfilePic==1) {
     //remove from list when is resource and is profile picture #10328
     unset($attachments[$key]);
   }else{
    $userId=$attachment->idUser;
    $ress=new Resource($user->id);
    if ($user->id==$attachment->idUser or $attachment->idPrivacy==1 or ($attachment->idPrivacy==2 and $ress->idTeam==$attachment->idTeam) ) {
      $userName=SqlList::getNameFromId('Affectable', $userId);
      $creationDate=$attachment->creationDate;
      $updateDate=null;
      echo '<tr>';
      if (!$print) {
        echo '<td class="attachmentData smallButtonsGroup" style="width:5%"">';
        if ($attachment->fileName and $attachment->subDirectory and !$print) {
          echo '<a href="../tool/download.php?class=Attachment&id='.htmlEncode($attachment->id).Security::addTokenIndexToUrl().'"';
          echo ' target="printFrame" title="'.i18n('helpDownload').'">'.formatSmallButton('Download').'</a>';
        }
        if ($attachment->link and !$print) {
          echo '<a href="'.htmlEncodeUrl($attachment->link).'"';
          echo ' target="#" title="'.urldecode($attachment->link).'">'.formatSmallButton('Link').'</a>';
        }
        if (($attachment->idUser==$user->id or $userCanDeleteAttachment->rightAccess==1) and !$print and $canUpdate) {
          echo ' <a onClick="editAttachment('.htmlEncode($attachment->id).');" title="'.i18n('editAttachment').'" >'.formatSmallButton('Edit').'</a>';
          echo ' <a onClick="removeAttachment('.htmlEncode($attachment->id).');" title="'.i18n('removeAttachment').'" >'.formatSmallButton('Remove').'</a>';
        }
        echo '</td>';
      }
      echo '<td class="attachmentData" style="width:5%;">#'.htmlEncode($attachment->id).'</td>';
      echo '<td class="attachmentData" style="width:5%;border-right:none;text-align:center;min-width:21px;max-width:21px">';
      if ($attachment->isThumbable()) {
        $img = getImageThumb($attachment->getFullPathFileName(), 32);
          echo '<img src="'.$img.'" '.' title="'.htmlEncode($attachment->fileName).'" style="float:left;cursor:pointer;max-width:32px;max-height:32px"'
            .((!$print)?' onClick="showImage(\'Attachment\',\''.htmlEncode($attachment->id).'\',\''.htmlEncode($attachment->fileName, 'protectQuotes').'\');"':'')
            .' />';
      } else if ($attachment->link and !$print) {
        echo '<div style="float:left;cursor:pointer" onClick="showLink(\''.htmlEncodeUrl(str_replace("'","\'",($attachment->link))).'\');">';
        echo '<img src="../view/img/mime/html.png" title="'.htmlEncode($attachment->link).'" />';
        echo '</div>';
      } else {
        $fileName=$attachment->fileName;
        if (pq_substr($fileName, -10)=='.projeqtor') {
          $fileName=pq_substr($fileName,0,pq_strlen($fileName)-10);
        }
        if (pq_substr($fileName, -14)=='.projeqtor.txt') {
          $fileName=pq_substr($fileName,0,pq_strlen($fileName)-14);
        }
        echo htmlGetMimeType($attachment->mimeType, $fileName, $attachment->id);
      }
      echo '</td><td class="attachmentData" style="border-left:none;width:'.(($print)?'90':'80').'%" >';
      echo formatUserThumb($userId, $userName, 'Creator');
      echo formatDateThumb($creationDate, $updateDate);
      echo formatPrivacyThumb($attachment->idPrivacy, $attachment->idTeam);
      if ($attachment->link) {
        $fileName=htmlEncode(urldecode($attachment->link), 'print');
      } else {
        $fileName=htmlEncode($attachment->fileName, 'print');
        if (pq_substr($fileName, -10)=='.projeqtor') {
          $fileName=pq_substr($fileName,0,pq_strlen($fileName)-10);
        }
        if (pq_substr($fileName, -14)=='.projeqtor.txt') {
          $fileName=pq_substr($fileName,0,pq_strlen($fileName)-14);
        }
      }
      if ($attachment->description and !$print) {
        echo formatCommentThumb($fileName);
        echo htmlEncode($attachment->description, 'print');
      } else {
        echo $fileName;
      } 
      echo '</td>';
      echo '</tr>';
    }
   }
  }
  echo '<tr>';
  if (!$print) {
    echo '<td class="attachmentDataClosetable">&nbsp;';
    echo '<input type="hidden" name="nbAttachments" id="nbAttachments" value="'.count($attachments).'" />';
    echo '</td>';
  }
  echo '<td class="attachmentDataClosetable">&nbsp;</td>';
  echo '<td class="attachmentDataClosetable">&nbsp;</td>';
  echo '<td class="attachmentDataClosetable">&nbsp;</td>';
  echo '</tr>';
  echo '</table>';
  if (!$refresh) echo "</td></tr>";
  if (!$print) {
    echo '<input id="AttachmentSectionCount" type="hidden" value="'.count($attachments).'" />';
  }
}

function drawLinksFromObject($list, $obj, $classLink, $refresh=false) {
  if ($obj->isAttributeSetToField("_Link", "hidden")) {
    return;
  }
  global $cr, $outMode, $outModeBack, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  
  $cptt = 0;
  if($classLink==""){
    $findme   = '_Link_';
    foreach ($obj as $idVal=>$listVal){
      $finded = strstr($idVal, $findme);
      if($finded){
        if(is_array($listVal)){
          $cptt+= count($listVal);
        }
      }
    }
  }
  $alreadyExistsArray=array();
  foreach($list as $lnkTest) {
    if ($lnkTest->ref1Type=='Document' and $lnkTest->ref1Id==$obj->id) {
      $alreadyExistsArray[]=$lnkTest->ref2Type.'#'.$lnkTest->ref2Id;
    } else {
      $alreadyExistsArray[]=$lnkTest->ref1Type.'#'.$lnkTest->ref1Id;
    }
  }
  if (get_class($obj)=='Document') {
    $dv=new DocumentVersion();
    $lstVers=$dv->getSqlElementsFromCriteria(array('idDocument'=>$obj->id));
    foreach ($lstVers as $dv) {
      $crit="(ref1Type='DocumentVersion' and ref1Id=".htmlEncode($dv->id).")";
      $crit.="or (ref2Type='DocumentVersion' and ref2Id=".htmlEncode($dv->id).")";
      $lnk=new Link();
      $lstLnk=$lnk->getSqlElementsFromCriteria(null, null, $crit);
      foreach ($lstLnk as $lnk) {
        if ($lnk->ref1Type=='DocumentVersion') {
          $lnk->ref1Type='Document';
          $lnk->ref1Id=$obj->id;
          if (in_array($lnk->ref2Type.'#'.$lnk->ref2Id, $alreadyExistsArray)) continue;
        } else {
          $lnk->ref2Type='Document';
          $lnk->ref2Id=$obj->id;
          if (in_array($lnk->ref1Type.'#'.$lnk->ref1Id, $alreadyExistsArray)) continue;
        }
        $list[]=$lnk;
      }
    }
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $paramLock=Parameter::getGlobalParameter('lockLinksForProfiles');
  if ($paramLock) {
    $locked=explode(',',$paramLock);
    $user=getSessionUser();
    if (in_array($user->getProfile($obj),$locked)) $canUpdate=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      $linkable=SqlElement::getSingleSqlElementFromCriteria('Linkable', array('name'=>get_class($obj)));
      $default=$linkable->idDefaultLinkable;
      echo '<a onClick="addLink('."'".$classLink."','".$default."'".');" title="'.i18n('addLink').'" class="roundedButtonSmall">'.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  if (!$classLink) {
    echo '<td class="linkHeader" style="width:'.(($print)?'20':'15').'%">'.i18n('colElement').'</td>';
  } else {
    echo '<td class="linkHeader" style="width:'.(($print)?'10':'5').'%">'.i18n('colId').'</td>';
  }
  
  echo '<td class="linkHeader sortable" style="width:'.(($classLink)?'65':'55').'%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  if (! $classLink or property_exists($classLink, 'idStatus')) {
    echo '<td class="linkHeader" style="width:15%">'.i18n('colIdStatus').'</td>';
  }
  if (! $classLink or property_exists($classLink, 'idResource')) {
    echo '<td class="linkHeader" style="width:10%">'.i18n('colResponsibleShort').'</td>';
  }
  // }
  // echo '<td class="linkHeader" style="width:15%">' . i18n('colDate') . '</td>';
  // echo '<td class="linkHeader" style="width:15%">' . i18n('colUser') . '</td>';
  echo '</tr>';
  $classObj=get_class($obj);
  if ($classObj=='TicketSimple') $classObj='Ticket';
  foreach ($list as $link) {
    $linkObj=null;
    if ($link->ref1Type==$classObj and $link->ref1Id==$obj->id) {
      $linkObj=new $link->ref2Type($link->ref2Id);
    } else {
      $linkObj=new $link->ref1Type($link->ref1Id);
    }
    $userId=$link->idUser;
    $userName=SqlList::getNameFromId('Affectable', $userId);
    $creationDate=$link->creationDate;
    $prop='_Link_'.get_class($linkObj);
    if ($classLink or !property_exists($obj, $prop)) {
      $gotoObj=(get_class($linkObj)=='DocumentVersion')?new Document($linkObj->idDocument):$linkObj;
      $canGoto=(securityCheckDisplayMenu(null, get_class($gotoObj)) and securityGetAccessRightYesNo('menu'.get_class($gotoObj), 'read', $gotoObj)=="YES")?true:false;
      if (!$canGoto and get_class($gotoObj)=='Ticket') {
        $gotoObj=new TicketSimple($gotoObj->id);
        $canGoto=(securityCheckDisplayMenu(null, get_class($gotoObj)) and securityGetAccessRightYesNo('menu'.get_class($gotoObj), 'read', $gotoObj)=="YES")?true:false;
      }
      echo '<tr>';
      if (pq_substr(get_class($linkObj), 0, 7)=='Context') {
        $classLinkName=SqlList::getNameFromId('ContextType', pq_substr(get_class($linkObj), 7, 1));
      } else {
        $classLinkName=i18n(get_class($linkObj));
      }
      if (!$print) {
        echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
        if ($canGoto and (get_class($linkObj)=='DocumentVersion' or get_class($linkObj)=='Document') and isset($gotoObj->idDocumentVersion) and $gotoObj->idDocumentVersion) {
          $canDownload = true;
          $forbidDownload = Parameter::getGlobalParameter('lockDocumentDownload');
          if($forbidDownload=="YES" and $gotoObj->locked and $gotoObj->idLocker!=getCurrentUserId()){
            $canDownload = false;
          }
          if ($canDownload) {
            echo '<a href="../tool/download.php?class='.get_class($linkObj).'&id='.htmlEncode($linkObj->id).Security::addTokenIndexToUrl().'"';
            echo ' target="printFrame" title="'.i18n('helpDownload').'">'.formatSmallButton('Download').'</a>';
          }
        }
        if ($canUpdate) {
          if(!$classLink)$classLink="";
          echo '  <a onClick="editLink('."'".htmlEncode($link->id)."','".$default."','".$classLink."'".');" title="'.i18n('editLink').'" > '.formatSmallButton('Edit').'</a>';
          echo '  <a onClick="removeLink('."'".htmlEncode($link->id)."','".get_class($linkObj)."','".htmlEncode($linkObj->id)."','".$classLinkName."','".$classLink."'".');" title="'.i18n('removeLink').'" > '.formatSmallButton('Remove').'</a>';
        }
        echo '</td>';
      }
      $goto="";
      if (!$print and $canGoto) {
        $goto=' onClick="hideTooltip(this);gotoElement('."'".get_class($gotoObj)."','".htmlEncode($gotoObj->id)."'".');" ';
      }
      if (!$classLink) {
        echo '<td class="linkData" style="white-space:nowrap;width:'.(($print)?'20':'15').'%"><table style="width:100%"><tr><td style="width:20%">';
        
        if (get_class($linkObj)=='DocumentVersion' or get_class($linkObj)=='Document') {
          if (get_class($linkObj)=='DocumentVersion') $version=$linkObj;
          else $version=new DocumentVersion($linkObj->idDocumentVersion);
          if ($version->isThumbable() and !$print) {
            $ext=pathinfo($version->fileName, PATHINFO_EXTENSION);
            if (file_exists("../view/img/mime/$ext.png")) {
              $img="../view/img/mime/$ext.png";
            } else {
              $img="../view/img/mime/unknown.png";
            }
            echo '<img src="'.$img.'" '.' title="'.htmlEncode($version->fileName).'" style="float:left;cursor:pointer"'.' onClick="showImage(\'DocumentVersion\',\''.htmlEncode($version->id).'\',\''.htmlEncode($version->fileName, 'protectQuotes').'\');" />';
          } else {
            echo htmlGetMimeType($version->mimeType, $version->fileName, $version->id, 'DocumentVersion');
          }
        } else {
          echo '<div '.$goto.' class="linkIconHover "  >';
          echo formatIcon(get_class($linkObj), 16);
          echo '</div>';
        }
        echo '</td><td '.$goto.' style="'.(($goto)?'cursor: pointer;':'').(($print and $outMode=='pdf' and $outModeBack!='pdf')?'font-size:90%;':'').'padding-left:5px" class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">'.$classLinkName.' #'.$linkObj->id.'</td></tr></table>';
      } else {
        echo '<td '.$goto.' class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="white-space:nowrap;width:'.(($print)?'10':'5').'%">#'.$linkObj->id;
      }
      echo '</td>';      
      $linkedVersionName = '';
      $isLinkedDocumentVersion = false;
      
      if (get_class($linkObj)=='DocumentVersion') {
        $isLinkedDocumentVersion = true;
        $linkedVersionName = $linkObj->name;
        $linkObj = new Document($linkObj->idDocument);
      } else if (get_class($linkObj)=='Document' and isset($linkObj->idDocumentVersion) and $linkObj->idDocumentVersion) {
        $docVersion = new DocumentVersion($linkObj->idDocumentVersion);
        if ($docVersion->id and $docVersion->version) {
          $linkedVersionName = $docVersion->name;
        }
      }
      $projectDep = new Project();
      if (property_exists($linkObj, 'idProject')) $projectDep = new Project($linkObj->idProject);
      $planningMode = new PlanningMode ();
      $pe = get_class($linkObj).'PlanningElement';
      if (property_exists(get_class($linkObj),$pe)){
        $objectInfo = json_encode($linkObj->$pe);
        $planningMode = new PlanningMode($linkObj->$pe->idPlanningMode);
        if ($linkObj->$pe->refType == 'Project') $projectDep = $linkObj;
      } else {
        $objectInfo = json_encode($linkObj);
      }
      $res = new Resource ();
      $productVersion = new ProductVersion();
      $type= new Type();
      $idType = 'id'.get_class($linkObj).'Type';
      if (property_exists($linkObj, $idType)) $type= new Type($linkObj->$idType);
      if (property_exists($linkObj, 'idResource')) $res = new Resource ($linkObj->idResource);
      if (property_exists($linkObj, 'idTargetProductVersion')) $productVersion = new ProductVersion($linkObj->idTargetProductVersion);
      //#10899
      $lastVersion = null;
      $versionLabel = null;
      
      if (isset($linkedVersionName) and $linkedVersionName) {
        $lastVersion = $linkedVersionName;
        $versionLabel = ($isLinkedDocumentVersion) ? 'colVersion' : 'colCurrentDocumentVersion';
      }
      
      echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.'   onmouseout="hideTooltip(this)" onmouseenter="showTooltip(this, ' . htmlEncode(json_encode($projectDep)) . ', ' . htmlEncode($objectInfo) . ', ' . htmlEncode(json_encode($res)) . ', ' . htmlEncode(json_encode($productVersion)) . ', ' . htmlEncode(json_encode($type)) . ', ' . htmlEncode(json_encode($planningMode)) . ', ' . htmlEncode(json_encode($lastVersion)) . ', ' . htmlEncode(json_encode($versionLabel)) . ')" onmouseleave="hideTooltip(this)" onfocusout="hideTooltip(this)" style="width:'.(($classLink)?'65':'55').'%">';
      echo formatCommentThumb($link->comment);
      echo htmlEncode($linkObj->name);
      
      if ($linkedVersionName) {
        echo ' <span style="margin-left:6px;color:#666;white-space:nowrap;">('.htmlEncode($linkedVersionName).')</span>';
      }

      echo formatUserThumb($userId, $userName, 'Creator');
      echo formatDateThumb($creationDate, null);

          if(!$print){
        //remi #9938
        if ($link->idSynchronizationItem){
          echo "<span style='position:relative;float:right;padding-right:3px;'>
                <div title='" . i18n('linkSynchronized') . "' class='iconSize22 iconRefresh imageColorNewGui'></div>
              </span>";
        }
      }else{
        if ($link->idSynchronizationItem){
          echo "<span style='margin-left:340px;'>".formatIcon('Refresh', 16)."</span>";   
        }
      }
      
      $idStatus='idStatus';
      $statusClass='Status';
      if (!property_exists($linkObj, $idStatus) and property_exists($linkObj, 'id'.get_class($linkObj).'Status')) {
        $idStatus='id'.get_class($linkObj).'Status';
        $statusClass=get_class($linkObj).'Status';
      }
      echo '</td>';
      if (! $classLink or property_exists($classLink, 'idStatus')) {
        if (property_exists($linkObj, $idStatus)) {
          $objStatus=new $statusClass($linkObj->$idStatus);
          echo '<td class="linkData colorNameData"  style="width:15%">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</td>';
        } else {
          echo '<td class="linkData"  style="width:15%">&nbsp;</td>';
        }
      }
      // //KROWRY
      if (! $classLink or property_exists($classLink, 'idResource')) {
        if (property_exists($linkObj, 'idResource')&&$linkObj->idResource!=null) {
          $objR=get_class($linkObj);
          $objResp=new $objR($linkObj->id);
          //echo '<td class="dependencyData"  style="width:10%">'.formatLetterThumb($objResp->idResource, 22).'</td>';
          if(!$print){
           echo '<td class="dependencyData"  style="width:10%;text-align:center;"><span style="display:inline-block;">'.formatUserThumb($objResp->idResource, SqlList::getNameFromId('Affectable', $objResp->idResource), 'Responsible').'</span></td>';
          }else{
            echo '<td class="dependencyData"  style="width:10%;text-align:center;"><span style="display:inline-block;">'.SqlList::getNameFromId('Affectable', $objResp->idResource).'</span></td>';
          }
        } else {
          echo '<td class="dependencyData"  style="width:10%">&nbsp;</td>';
        }
      }
      echo '</tr>';
    }
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    $valueTotal = count($list)-$cptt;
    echo '<input id="'.$classLink.'LinkSectionCount" type="hidden" value="'.$valueTotal.'" />';
  }
}

function drawStructureFromObject($obj, $refresh=false, $way=null, $item=null) {
  $crit=array();
  if ($way=='composition') {
    $crit['idProduct']=$obj->id;
  } else if ($way=='structure') {
    $crit['idComponent']=$obj->id;
  } else {
    errorLog("unknown way=$way in drawStructureFromObject()");
  }
  $showClosedStructure=Parameter::getUserParameter('showClosedStructure');
  $showClosedComposition=Parameter::getUserParameter('showClosedComposition');
  $pcs=new ProductStructure();
  $list=$pcs->getSqlElementsFromCriteria($crit);
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  // TEST TICKET #2680
  $canUpdateComp=securityGetAccessRightYesNo('menuComponent', 'update', $obj)=="YES";
  //
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    // TEST TICKET #2680
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addProductStructure(\''.$way.'\');" title="'.i18n('addProductStructure').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  $listClass=($item=='Product')?'Component':(($way=='structure')?'ProductOrComponent':'Component');
  echo '<td class="linkHeader" style="width:'.(($print)?'20':'15').'%">'.i18n($listClass).'</td>';
  echo '<td class="linkHeader sortable" style="width:80%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '</tr>';
  foreach ($list as $comp) {
    $compObj=null;
    if ($way=='structure') {
      $compObj=new ProductOrComponent($comp->idProduct);
    } else {
      $compObj=new ProductOrComponent($comp->idComponent);
    }
    if ($compObj->scope=='Product') $compObj=new Product($compObj->id);
    else $compObj=new Component($compObj->id);
    if($compObj->idle and ((!$showClosedStructure and $way=='structure') or (!$showClosedComposition and $way=='composition'))){
      continue;
    }
    $userId=$comp->idUser;
    $userName=SqlList::getNameFromId('Affectable', $userId);
    $creationDate=$comp->creationDate;
    $canGoto=(securityCheckDisplayMenu(null, get_class($compObj)) and securityGetAccessRightYesNo('menu'.get_class($compObj), 'read', $compObj)=="YES")?true:false;
    echo '<tr>';
    $classCompName=i18n(get_class($compObj));
    if (!$print) {
      echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
      if ($canUpdate) {
        echo '  <a onClick="editProductStructure(\''.$way.'\','.htmlEncode($comp->id).');" '.'title="'.i18n('editProductStructure').'" > '.formatSmallButton('Edit').'</a>';
        echo '  <a onClick="removeProductStructure('."'".htmlEncode($comp->id)."','".get_class($compObj)."','".htmlEncode($compObj->id)."','".$classCompName."'".');" '.'title="'.i18n('removeProductStructure').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    // echo '<td class="linkData" style="white-space:nowrap;width:' . (($print)?'20':'15') . '%"><img src="css/images/icon'.get_class($compObj).'16.png" />&nbsp;'.$classCompName .' #' . $compObj->id;
    $goto="";
    if (!$print and $canGoto) {
      $goto=' onClick="gotoElement('."'".get_class($compObj)."','".htmlEncode($compObj->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="white-space:nowrap;width:'.(($print)?'20':'15').'%"><table><tr>';
    echo '<td>'.formatIcon(get_class($compObj), 16).'</td><td style="vertical-align:top">&nbsp;'.'#'.$compObj->id.'</td></tr></table>';
    echo '</td>';
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="position:relative;">';
    echo htmlEncode($compObj->name);
    echo formatUserThumb($userId, $userName, 'Creator');
    echo formatDateThumb($creationDate, null);
    echo formatCommentThumb($comp->comment);
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="'.get_class($obj).pq_ucfirst($way).'SectionCount" type="hidden" value="'.count($list).'" />';
  }
}

// ADD by qCazelles - Business features
function drawBusinessFeatures($obj, $refresh=false) {
  $crit=array();
  $crit['idProduct']=$obj->id;
  $pcs=new BusinessFeature();
  $list=$pcs->getSqlElementsFromCriteria($crit, null, null, 'name asc');
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addBusinessFeature();" title="'.i18n('addBusinessFeature').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="linkHeader" style="width:'.(($print)?'20':'15').'%">'.i18n('colId').'</td>';
  echo '<td class="linkHeader" style="width:80%">'.i18n('BusinessFeature').'</td>';
  echo '</tr>';
  
  foreach ($list as $bf) {
    $userId=$bf->idUser;
    $userName=SqlList::getNameFromId('Affectable', $userId);
    $creationDate=$bf->creationDate;
    echo '<tr>';
    if (!$print) {
      echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
      if ($canUpdate) {
        // ADD qCazelles - Business Feature (Correction) - Ticket #96
        echo '  <a onClick="editBusinessFeature('.htmlEncode($bf->id).');" '.'title="'.i18n('editBusinessFeature').'" > '.formatSmallButton('Edit').'</a>';
        // END ADD qCazelles - Business Feature (Correction) - Ticket #96
        // CHANGE qCazelles - Business Feature (Correction) - Ticket #96
        // Old
        // echo ' <a onClick="removeBusinessFeature(' . "'" . htmlEncode($bf->id) . "','" . get_class($bf) . "'" . ');" '
        // .'title="' . i18n('removeBusinessFeature') . '" > '.formatSmallButton('Remove').'</a>';
        // New
        $crit=array('idBusinessFeature'=>$bf->id);
        $ticket=new Ticket();
        $listBfTicket=$ticket->getSqlElementsFromCriteria($crit);
        if (count($listBfTicket)==0) {
          echo '  <a onClick="removeBusinessFeature('."'".htmlEncode($bf->id)."','".get_class($bf)."'".');" '.'title="'.i18n('removeBusinessFeature').'" > '.formatSmallButton('Remove').'</a>';
        }
        // END CHANGE qCazelles - Business Feature (Correction) - Ticket #96
      }
      echo '</td>';
    }
    echo '<td class="linkData" style="white-space:nowrap;width:'.(($print)?'20':'15').'%"><table><tr>';
    // echo '<td>IMG</td><td style="vertical-align:top">&nbsp;'.'#' . $bf->id.'</td></tr></table>';
    echo '<td style="vertical-align:top">&nbsp;'.'#'.$bf->id.'</td></tr></table>';
    echo '</td>';
    echo '<td class="linkData" style="cursor: pointer;">';
    echo htmlEncode($bf->name);
    echo formatUserThumb($userId, $userName, 'Creator');
    echo formatDateThumb($creationDate, null);
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="BusinessFeatureSectionCount" type="hidden" value="'.count($list).'" />';
  }
}
// END ADD qCazelles

function drawLocalizationItemSection($obj, $refresh = false){
    global $cr, $print, $user, $comboDetail;
    $crit=array('idLocalizationRequest'=>$obj->id);
    $localizationItem = new LocalizationItem();

    $listLocalizationItems = $localizationItem->getSqlElementsFromCriteria($crit);

    global $cr, $print, $user, $comboDetail;
    if ($comboDetail) {
        return;
    }
    if (!$refresh) echo '<tr><td colspan="2">';
    echo '<table style="width:100%;">';
    echo '<tr>';
    if (!$print) {
        echo '<td class="linkHeader" style="width:5%">';
        echo '</td>';
    }
    $listClass='LocalizationItem';
    echo '<td class="linkHeader" style="width:'.(($print)?'20':'15').'%">'.i18n($listClass).'</td>';
    echo '<td class="linkHeader sortable" style="width:45%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
    echo '<td class="linkHeader" style="width:20%">'.i18n('colIdStatus').'</td>';
    echo '<td class="linkHeader" style="width:15%">'.i18n('colIdLocalizationTranslator').'</td>';
    echo '</tr>';
    foreach ($listLocalizationItems as $localizationItem) {
        $status = new Status($localizationItem->idStatus);
        $translator = new LocalizationTranslator($localizationItem->idLocalizationTranslator);
        $translatorName = $translator->name;
        $goto="";
        $canGoto=(securityCheckDisplayMenu(null, get_class($localizationItem)) and securityGetAccessRightYesNo('menu'.get_class($localizationItem), 'read', $localizationItem)=="YES")?true:false;
        if (!$print and $canGoto) {
            $goto=' onClick="gotoElement('."'".get_class($localizationItem)."','".htmlEncode($localizationItem->id)."'".');" style="cursor: pointer;" ';
        }

        echo '<tr>';
        if (!$print) {
            echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
            echo '</td>';
        }
        echo '<td class="linkData" '.$goto.' style="white-space:nowrap;width:'.(($print)?'20':'15').'%"><table><tr>';
        echo '<td>'.formatIcon(get_class($localizationItem), 16).'</td><td style="vertical-align:top">&nbsp;'.'#'.$localizationItem->id.'</td></tr></table>';
        echo '</td>';
        echo '<td class="linkData" '.$goto.' style="position:relative;">';
        echo htmlEncode($localizationItem->name);
        echo '</td>';
        echo '<td class="noteData" style="text-align:center;background-color:'.$status->color.';" >' .htmlFormatDateTime($status->name). '</td>';
        echo '</td>';
        $canGoto=(securityCheckDisplayMenu(null, get_class($translator)) and securityGetAccessRightYesNo('menu'.get_class($translator), 'read', $localizationItem)=="YES")?true:false;
        $goto ='';
        if (!$print and $canGoto and $translator->id) {
            $goto=' onClick="gotoElement('."'".get_class($translator)."','".htmlEncode($translator->id)."'".');" style="cursor: pointer;" ';
        }
        echo '<td class="dependencyData"' . $goto .'>'.$translatorName;
        if ($translator->id){
            echo formatLetterThumb($localizationItem->idLocalizationTranslator, 16);
        }
        echo '</td>';

        echo '</tr>';
    }
    
    echo '</table>';
    if (!$refresh) echo '</td></tr>';
    if (!$print) {
        echo '<input id="LocalizationItemSectionCount" type="hidden" value="'.count($listLocalizationItems).'" />';
    }
}
// ADD qCazelles - Lang-Context
function drawLanguageSection($obj, $refresh=false) {
  $crit=array();
  $scope=get_class($obj);
  if ($scope=='Product' or $scope=='Component') {
    $crit['idProduct']=$obj->id;
    // $crit['scope']=$scope; // useless because an idProduct can't be the same for Component and Product
    $langClass='ProductLanguage';
  } else if (get_class($obj)=='ProductVersion' or get_class($obj)=='ComponentVersion') {
    $crit['idVersion']=$obj->id;
    $crit['scope']=pq_str_replace('Version', '', $scope);
    $langClass='VersionLanguage';
  } else if (get_class($obj)=='LocalizationTranslator'){
      $crit['idTranslator']=$obj->id;
      $langClass='LocalizationTranslatorlanguage';
  } else {
    errorLog("drawLanguageSection for item not taken into account : ".get_class($obj));
  }
  $langsProduct=new $langClass();
  $list=$langsProduct->getSqlElementsFromCriteria($crit);
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
       echo '<a onClick=addLanguage("' . get_class($obj) . '"); title="'.i18n('addLanguage').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  $listClass='Language';
  echo '<td class="linkHeader" style="width:'.(($print)?'20':'15').'%">'.i18n($listClass).'</td>';

  if (get_class($obj)=='LocalizationTranslator'){
      echo '<td class="linkHeader sortable" style="width:40%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
      echo '<td class="linkHeader" style="width:40%">'.i18n('colLevelLanguageSkill').'</td>';
  }else{
      echo '<td class="linkHeader" style="width:80%">'.i18n('colName').'</td>';
  }
  echo '</tr>';


  foreach ($list as $lang) { // $lang is ProductLanguage or LocalizationTranslatorLanguage
    $langObj=new Language($lang->idLanguage);
    $userId=$lang->idUser;
    $userName=SqlList::getNameFromId('Affectable', $userId);
    $creationDate=$lang->creationDate;
    $canGoto=(securityCheckDisplayMenu(null, get_class($langObj)) and securityGetAccessRightYesNo('menu'.get_class($langObj), 'read', $langObj)=="YES")?true:false;
    echo '<tr>';
    $classLangName=i18n(get_class($langObj));
    if (!$print) {
      echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
      if ($canUpdate) {
        echo '  <a onClick="editLanguage(' . "'" . htmlEncode($lang->id) . "','" . get_class($obj) . "'" . ');" ' . 'title="' . i18n('editLanguage') . '" > ' . formatSmallButton('Edit') . '</a>';
        echo '  <a onClick="removeLanguage(' . "'" . htmlEncode($lang->id) . "','" . get_class($obj) . "'" . ');" ' . 'title="' . i18n('removeLanguage') . '" > ' . formatSmallButton('Remove') . '</a>';
      }
      echo '</td>';
    }
    echo '<td class="linkData" style="white-space:nowrap;width:'.(($print)?'20':'15').'%"><table><tr>';
    echo '<td>'.formatIcon(get_class($langObj), 16).'</td><td style="vertical-align:top">&nbsp;'.'#'.$langObj->id.'</td></tr></table>';
    echo '</td>';
    $goto="";
    if (!$print and $canGoto) {
      $goto=' onClick="gotoElement('."'".get_class($langObj)."','".htmlEncode($langObj->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="position:relative;">';
    echo htmlEncode($langObj->name);
    if (get_class($obj)=='LocalizationTranslator'){
        echo '</td>';
        echo '<td class="linkData" '.$goto.' style="position:relative;">';
        $lsl = new LanguageSkillLevel($lang->idLanguageSkillLevel);
        echo htmlEncode($lsl->name);;
    }
    echo formatUserThumb($userId, $userName, 'Creator');
    echo formatDateThumb($creationDate, null);
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
      if (!get_class($obj)=='LocalizationTranslator') {
          echo '<input id="ProductLanguageSectionCount" type="hidden" value="' . count($list) . '" />';
      }
  }
}

function drawContextSection($obj, $refresh=false) {
  $crit=array();
  $scope=get_class($obj);
  if ($scope=='Product' or $scope=='Component') {
    $crit['idProduct']=$obj->id;
    $crit['scope']=$scope;
    $langClass='ProductContext';
  } else if (get_class($obj)=='ProductVersion' or get_class($obj)=='ComponentVersion') {
    $crit['idVersion']=$obj->id;
    $crit['scope']=pq_str_replace('Version', '', $scope);
    $langClass='VersionContext';
  } else {
    errorLog("drawLanguageSection for item not taken into account : ".get_class($obj));
  }
  $contextProduct=new $langClass();
  $list=$contextProduct->getSqlElementsFromCriteria($crit);
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addProductContext();" title="'.i18n('addProductContext').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  $listClass='Context';
  echo '<td class="linkHeader" style="width:'.(($print)?'20':'15').'%">'.i18n($listClass).'</td>';
  echo '<td class="linkHeader sortable" style="width:80%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '</tr>';
  foreach ($list as $context) { // $context is a ProductContext
    $contextObj=new Context($context->idContext);
    $userId=$context->idUser;
    $userName=SqlList::getNameFromId('Affectable', $userId);
    $creationDate=$context->creationDate;
    $canGoto=(securityCheckDisplayMenu(null, get_class($contextObj)) and securityGetAccessRightYesNo('menu'.get_class($contextObj), 'read', $contextObj)=="YES")?true:false;
    echo '<tr>';
    $classLangName=i18n(get_class($contextObj));
    if (!$print) {
      echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
      if ($canUpdate) {
        echo '  <a onClick="editProductContext('.htmlEncode($context->id).');" '.'title="'.i18n('editProductContext').'" > '.formatSmallButton('Edit').'</a>';
        echo '  <a onClick="removeProductContext('."'".htmlEncode($context->id)."','".get_class($obj)."'".');" '.'title="'.i18n('removeProductContext').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    echo '<td class="linkData" style="white-space:nowrap;width:'.(($print)?'20':'15').'%"><table><tr>';
    echo '<td>'.formatIcon(get_class($contextObj), 16).'</td><td style="vertical-align:top">&nbsp;'.'#'.$contextObj->id.'</td></tr></table>';
    echo '</td>';
    $goto="";
    if (!$print and $canGoto) {
      $goto=' onClick="gotoElement('."'".get_class($contextObj)."','".htmlEncode($contextObj->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="position:relative;">';
    echo htmlEncode($contextObj->name);
    echo formatUserThumb($userId, $userName, 'Creator');
    echo formatDateThumb($creationDate, null);
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="ProductContextSectionCount" type="hidden" value="'.count($list).'" />';
  }
}
// END qCazelles - Lang-Context

function drawSubscriptionsList($obj, $refresh=false, $limitToActive=null) {
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
 	$checked = '';
 	if (isset($_REQUEST['showClosedSub']) and $_REQUEST['showClosedSub'] == true) $checked = ' checked ';
 	if (! $print) {
   	echo '<div style="position:absolute;right:5px;top:3px;">';
   	echo '<label for="showClosedSub" class="dijitTitlePaneTitle" style="border:0;font-weight:normal !important;height:'.((isNewGui())?'20':'10').'px;width:'.((isNewGui())?'50':'150').'px">' . i18n('labelShowIdle'.((isNewGui())?'Short':'')) . '</label>';
   	echo '<div class="whiteCheck" title="'.i18n('labelShowIdle') .'" type="checkbox" id="showClosedSub" name="showClosedSub" value="showClosedSub" style="'.((isNewGui())?'margin-top:14px':'position:relative;left:5px').'" dojoType="dijit.form.CheckBox"'.$checked.'>';
   	echo '<script type="dojo/method" event="onChange"> loadContent("objectDetail.php?&showClosedSub='.(($checked=='')?true:false).'", "detailDiv", "listForm"); </script>';
   	echo '</div>';
   	echo '</div>';
 	}
  if (!$refresh) echo '<tr><td colspan="4">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  echo '<td class="linkHeader" style="width:25%">'.i18n('colType').'</td>';
  echo '<td class="linkHeader" style="width:15%">'.i18n('colId').'</td>';
  echo '<td class="linkHeader sortable" style="width:60%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '</tr>';
  if (!$obj->id) {
    $list=array();
  } else if (get_class($obj)=='Contact') {
    $where = 'idAffectable = ' . $obj->id;
    $orderBy = 'refType, refId';
    $sub=new Subscription();
    $list=$sub->getSqlElementsFromCriteria(null, false, $where, $orderBy);
  }
  if (!isset($list)) $list=array();
  
  foreach ($list as $subscription) {
    $item = new $subscription->refType($subscription->refId);
    if (!$item or !$item->id or ($limitToActive and $item->idle == 1)) continue;
    $canGoto=(securityCheckDisplayMenu(null, $subscription->refType) and securityGetAccessRightYesNo('menu'. $subscription->refType, 'read', $subscription)=="YES")?true:false;
    $goto="";
    if (!$print and $canGoto) {
      $goto=' onClick="gotoElement('."'" . $subscription->refType ."','" . htmlEncode($item->id) . "'".');" style="cursor: pointer;" ';
    }
    echo '<tr>';
    echo '<td class="linkData" style="white-space:nowrap;width:25%" ><table><tr><td>' . htmlEncode(i18n($subscription->refType)) . '</td></tr></table>';
    echo '</td><td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="white-space:nowrap;width:15%" ' . $goto . '><table><tr><td>' . formatIcon($subscription->refType, 16) . '</td><td style="vertical-align:top">&nbsp;'.'#' . $item->id . '</td></tr></table>';
    echo '</td>';

    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative">'; 
    echo htmlEncode($item->name);
    echo '</td>';
    echo '</tr>';
  }
  
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="SubscriptionSectionCount" type="hidden" value="'.count($list).'" />';
  }
}

// ADD qCazelles - Manage ticket at customer level - Ticket #87
function drawTicketsList($obj, $refresh=false) {
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  $listClass='Ticket';
  echo '<td class="linkHeader" style="width:15%">'.i18n($listClass).'</td>';
  echo '<td class="linkHeader sortable" style="width:60%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="linkHeader" style="width:25%">'.i18n('colIdStatus').'</td>';
  echo '</tr>';
  if (!$obj->id) {
    $list=array();
  } else if (get_class($obj)=='Contact') {
    $crit=array('idContact'=>$obj->id, 'idle'=>'0');
    $ticket=new Ticket();
    $list=$ticket->getSqlElementsFromCriteria($crit);
  } else if (get_class($obj)=='Client') {
    $contact=new Contact();
    $crit=array('idClient'=>$obj->id);
    $listContacts=$contact->getSqlElementsFromCriteria($crit);
    if (count($listContacts)>0) {
      $clauseWhere='idContact in (0';
      foreach ($listContacts as $contact) {
        $clauseWhere.=",".$contact->id;
      }
      $clauseWhere.=') and idle=0';
    } else {
      $clauseWhere='1=0';
    }
    $ticket=new Ticket();
    if (property_exists('Ticket', 'idClient')) {
      $clauseWhere='idle=0 and (idClient='.Sql::fmtId($obj->id).' ';
      if (property_exists('Ticket', '_OtherClient')) {
        $otherclient=new OtherClient();
        $clauseWhere.=" or exists (select 'x' from ".$otherclient->getDatabaseTableName()." other "." where other.refType='Ticket' and other.refId=".$ticket->getDatabaseTableName().".id and other.idClient=".Sql::fmtId($obj->id).")";
      }
      $clauseWhere.=')';
    }
    $list=$ticket->getSqlElementsFromCriteria(null, false, $clauseWhere);
  } else if (get_class($obj)=='Product' or get_class($obj)=='Component') {
    $crit=array('id'.get_class($obj)=>$obj->id);
    $ticket=new Ticket();
    $list=$ticket->getSqlElementsFromCriteria($crit);
  } else if (get_class($obj)=='ProductVersion' or get_class($obj)=='ComponentVersion') {
    $crit=array('idTarget'.get_class($obj)=>$obj->id);
    $ticket=new Ticket();
    $list=$ticket->getSqlElementsFromCriteria($crit);
  }
  if (!isset($list)) $list=array();
  foreach ($list as $ticket) {
    $canGoto=(securityCheckDisplayMenu(null, $listClass) and securityGetAccessRightYesNo('menu'.$listClass, 'read', $ticket)=="YES")?true:false;
    echo '<tr>';
    $classCompName=i18n($listClass);
    $goto="";
    if (!$print and $canGoto) {
      $goto=' onClick="gotoElement('."'".$listClass."','".htmlEncode($ticket->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="white-space:nowrap;width:15%"  '.$goto.'>';
    echo '<table><tr><td>'.formatIcon($listClass, 16).'</td><td style="vertical-align:top">&nbsp;'.'#'.$ticket->id.'</td></tr></table>';
    echo '</td>';
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="position:relative;width:60%">';
    echo htmlEncode($ticket->name);
    echo '</td>';
    echo '<td class="linkData colorNameData" style="width:25%">';
    // $objStatus=new $statusClass($linkObj->$idStatus);
    echo colorNameFormatter(SqlList::getNameFromId('Status', $ticket->idStatus)."#split#".SqlList::getFieldFromId('Status', $ticket->idStatus, 'color'));
    echo '</td>';
    echo '</tr>';
  }
  
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="TicketSectionCount" type="hidden" value="'.count($list).'" />';
  }
}
// END ADD qCazelles - Manage ticket at customer level - Ticket #87

// Add mOlives - ticket 215 - 09/05/2018
function drawActivityList($obj, $refresh=false) {
  global $cr, $print, $user, $comboDetail, $outMode;
  if ($comboDetail) {
    return;
  }
//   $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
//   if ($obj->idle==1) {
//     $canUpdate=false;
//   }
  $listClass='Activity';
  if (!$refresh) echo '<tr><td colspan="4">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  echo '<td class="linkHeader" style="width:10%">'.i18n('colId').'</td>';
  echo '<td class="linkHeader sortable" style="width:55%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="linkHeader" style="width:15%">'.i18n('colProgress').'</td>';
  echo '<td class="linkHeader" style="width:20%">'.i18n('colIdStatus').'</td>';
  echo '</tr>';
  if (!$obj->id) {
    $list=array();
  } else if (get_class($obj)=='ComponentVersion') {
    $crit=array('idTarget'.get_class($obj)=>$obj->id);
    $activity=new Activity();
    $list=$activity->getSqlElementsFromCriteria($crit);
    $showClosedActivity=Parameter::getUserParameter('showClosedActivity');
  } else if (get_class($obj)=='Activity') {
    $crit=array('idActivity'=>$obj->id);
    $activity=new Activity();
    $list=$activity->getSqlElementsFromCriteria($crit);
    $showClosedActivity=1;
  }
  if (!isset($list)) $list=array();
  
  foreach ($list as $activity) {
    if ($showClosedActivity==1 or ($showClosedActivity==0 and $activity->idle==0)) {
      $canGoto=(securityCheckDisplayMenu(null, $listClass) and securityGetAccessRightYesNo('menu'.$listClass, 'read', $activity)=="YES")?true:false;
      echo '<tr>';
      $classCompName=i18n($listClass);
      echo '<td class="linkData" style="white-space:nowrap;width:10%">';
      echo '<table><tr><td>'.formatIcon($listClass, 16).'</td><td style="vertical-align:top">&nbsp;'.'#'.$activity->id.'</td></tr></table>';
      echo '</td>';
      $goto="";
      if (!$print and $canGoto) {
        $goto=' onClick="gotoElement('."'".$listClass."','".htmlEncode($activity->id)."'".');" style="cursor: pointer;" ';
      }
      echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="position:relative;width:55%;">';
      echo htmlEncode($activity->name);
      echo '</td>';
      echo '<td class="linkData" style="width:15%">';
      //$pe=new PlanningElement();
      //$crit=array('refId'=>$activity->id);
      //$arrayActivity=$pe->getSqlElementsFromCriteria($crit);
      //$act=reset($arrayActivity);
      $activityProgress=$activity->ActivityPlanningElement->progress;
      if ($print and isset($outMode) and $outMode=='pdf' and $activityProgress!==null) {
        // HTML2PDF does not keep the absolutely-positioned progress bar next
        // to its text. A small table reproduces the print layout reliably.
        $activityProgressPct=max(0, min(100, intval($activityProgress, 10)));
        echo '<div style="width:100%;text-align:center;line-height:12px;">'.$activityProgressPct.'&nbsp;%</div>';
        echo '<table style="width:100%;height:3px;border-collapse:collapse;margin:0;padding:0;"><tr>';
        if ($activityProgressPct>0) {
          echo '<td style="width:'.$activityProgressPct.'%;height:3px;font-size:1px;line-height:3px;padding:0;background-color:#AAFFAA;">&nbsp;</td>';
        }
        if ($activityProgressPct<100) {
          echo '<td style="width:'.(100-$activityProgressPct).'%;height:3px;font-size:1px;line-height:3px;padding:0;background-color:#FFAAAA;">&nbsp;</td>';
        }
        echo '</tr></table>';
      } else {
        echo progressFormatter($activityProgress, null);
      }
      echo '</td>';
      echo '<td class="linkData colorNameData" style="width:20%">';  
      echo colorNameFormatter(SqlList::getNameFromId('Status', $activity->idStatus)."#split#".SqlList::getFieldFromId('Status', $activity->idStatus, 'color'));
      echo '</td>';
      echo '</tr>';
    }
  }
  
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="ActivitySectionCount" type="hidden" value="'.count($list).'" />';
  }
}
// END mOlives - ticket 215 - 09/05/2018

//gautier #4404
function drawAssetComposition($obj,$refresh=false){
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  $canGoto = (securityCheckDisplayMenu(null, get_class($obj)) and securityGetAccessRightYesNo('menu' . get_class($obj), 'read', $obj) == "YES") ? true : false;
  $crit['idAsset']=$obj->id;
  $asset=new Asset();
  $list = array();
  if($obj->id){
    $list=$asset->getSqlElementsFromCriteria($crit);
  }
    
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
        echo '<a onClick="addAssetComposition(\''.$obj->id.'\');" title="'.i18n('addAsset').'" > '.formatSmallButton('Add').'</a>';
      }
    echo '</td>';
  }
  echo '<td class="linkHeader sortable" style="width:20%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="linkHeader" style="width:20%">'.i18n('colAssetType').'</td>';
  echo '<td class="linkHeader" style="width:20%">'.i18n('colBrand').'</td>';
  echo '<td class="linkHeader" style="width:20%">'.i18n('colModel').'</td>';
  echo '<td class="linkHeader" style="width:15%">'.i18n('colUser').'</td>';
  echo '</tr>';
  foreach ($list as $ass) {
    echo '<tr>';
    if (! $print) {
      echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
      if ($canUpdate) {
        echo '  <a onClick="removeAssetComposition(' . htmlEncode($ass->id) . ');" ' . 'title="' . i18n('removeProductStructure') . '" > ' . formatSmallButton('Remove') . '</a>';
      }
      echo '</td>';
      $goto = "";
        if (! $print and $canGoto) {
        $goto = ' onClick="gotoElement(' . "'" . get_class($ass) . "','" . htmlEncode($ass->id) . "'" . ');" style="cursor: pointer;" ';
      }
      echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
      echo htmlEncode($ass->name);
      echo'</td>';
      echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
      echo SqlList::getNameFromId('Type', $ass->idAssetType);
      echo'</td>';
      echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
      echo SqlList::getNameFromId('Brand', $ass->idBrand);
      echo'</td>';
      echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
      echo SqlList::getNameFromId('Model', $ass->idModel);
      echo'</td>';
      echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
      echo SqlList::getNameFromId('Affectable', $ass->idAffectable);
      echo'</td>';
    }
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
}

function drawVersionStructureFromObject($obj, $refresh=false, $way=null, $item=null) {
  $crit=array();
  if ($way=='composition') {
    $crit['idProductVersion']=$obj->id;
  } else if ($way=='structure') {
    $crit['idComponentVersion']=$obj->id;
  } else {
    errorLog("unknown way=$way in drawVersionStructureFromObject()");
  }
  $pcs=new ProductVersionStructure();
  $list=$pcs->getSqlElementsFromCriteria($crit);
  // ADD qCazelles - Sort version composition-structure - Ticket 142
  if (Parameter::getGlobalParameter('sortCompositionStructure')=='YES') {
    if ($way=='composition') {
      SqlElement::$_cachedQuery['ComponentVersion']=array(); // PBE : performance improvments
      SqlElement::$_cachedQuery['ComponentVersionType']=array(); // PBE : performance improvments
      // UPDATE tLaguerie ticket 366 and 367
      usort($list, "ProductVersionStructure::sortCompositionComponentVersionListOnId");
    } else if ($way=='structure') {
      SqlElement::$_cachedQuery['Version']=array(); // PBE : performance improvments
      SqlElement::$_cachedQuery['Type']=array(); // PBE : performance improvments
      // UPDATE tLaguerie ticket 366 and 367
      usort($list, "ProductVersionStructure::sortStructureComponentVersionListOnId");
    }
  }
  // END ADD qCazelles - Sort version composition-structure - Ticket 142
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<thead>';
  echo '<tr>';
  // ADD dFayolle ticket 366 and 367
  $actualStatus = '';
  // END dFayolle ticket 366 and 367
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate and $obj->idStatus) {
      //$critStatus = array('id' => $obj->idStatus);
      //$actualStatus = SqlElement::getSingleSqlElementFromCriteria ( 'status', $critStatus);
      $actualStatus=new Status($obj->idStatus);
      if ( ( (get_class($obj)!='ComponentVersion' && get_class($obj)!='ProductVersion') || $actualStatus->setIntoserviceStatus!=1) || ($way!='composition')) {
        echo '<a onClick="addProductVersionStructure(\''.$way.'\');" title="'.i18n('addProductVersionStructure').'" > '.formatSmallButton('Add').'</a>';
        if ($way=='composition' and count($list)>0) {
          echo '<a onClick="upgradeProductVersionStructure(null,false);" title="'.i18n('upgradeProductVersionStructure').'" > '.formatSmallButton('Switch').'</a>';
        }
      }
    }
    echo '</td>';
  }
  $listClass=($item=='ProductVersion')?'ComponentVersion':(($way=='structure')?'Version':'ComponentVersion');
  echo '<td class="linkHeader '.(($item=='ProductVersion')?'':'headerCompProdStruct').'" style="width:5%">'.i18n($listClass).'</td>';
  echo '<td onclick="onColumnHeaderClickedSort(event)" class="linkHeader headerCompProdStruct sortable" style="width:40%;cursor:pointer">'.i18n('colName').'</td>';
  // ADD tLAGUERIE AND dFAYOLLE ticket 366 and 367
  echo '<td class="linkHeader '.(($item=='ProductVersion')?'':'headerCompProdStruct').'" style="width:10%">' . i18n('colIdStatus') . '</td>';
  echo '<td class="linkHeader '.(($item=='ProductVersion')?'':'headerCompProdStruct').'" style="width:10%">' . i18n('colType') . '</td>';
  echo '<td class="linkHeader '.(($item=='ProductVersion')?'':'headerCompProdStruct').'" style="width:10%">' . i18n('colPlannedDeliveryDate') . '</td>';
  echo '<td class="linkHeader '.(($item=='ProductVersion')?'':'headerCompProdStruct').'" style="width:15">' . i18n('colVersionDeliveryDate') . '</td>';
  // END tLAGUERIE AND dFAYOLLE ticket 366 and 367
  echo '</tr>';
  echo '</thead>';
  echo '<tbody>';
  // ADD tlaguerie & dFayolle ticket 366 and 367
  $showClosedItemComposition = Parameter::getUserParameter('showClosedItemComposition'); // Show closed items of composition of ComponentVersion
  $showClosedItemStructure = Parameter::getUserParameter('showClosedItemStructure'); // Show closed items of structure of Component Version
  $showClosedItemCompositionProduct = Parameter::getUserParameter('showClosedItemCompositionProduct'); // Show closed items of composition of ProductVersion
  // END tlaguerie & dFayolle ticket 366 and 367
  foreach ($list as $comp) {
    // UPDATE ADD tLaguerie & dFayolle ticket 366 and 367
    $critVersionType = array('id' => $obj->idVersionType);
    $typeVersion = SqlElement::getSingleSqlElementFromCriteria('type',$critVersionType);
    
    $compObj=null;
    $paramItem=null;
    if ($way=='structure') {
      $compObj=new Version($comp->idProductVersion);
      $paramItem = $showClosedItemStructure;
    } else {
      $compObj=new Version($comp->idComponentVersion);
      if($typeVersion->scope=='ComponentVersion') {
        $paramItem = $showClosedItemComposition;
      } else if ($typeVersion->scope=='ProductVersion') {
        $paramItem = $showClosedItemCompositionProduct;
      }
    }
    if ($compObj->scope=='Product') $compObj=new ProductVersion($compObj->id);
    else $compObj=new ComponentVersion($compObj->id);
    if($paramItem==1 or !$compObj->idle) {
      drawElementIntoVersionStructureFromObject($comp, $compObj, $print, $canUpdate, $obj, $way, $actualStatus);
    }
    // UPDATE END tLaguerie & dFayolle ticket 366 and 367
  }
  echo '</tbody>';
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="ProductVersionStructureSectionCount" type="hidden" value="'.count($list).'" />';
  }
}
//gautier #4404
function drawVersionStructureFromObjectAsset($obj, $refresh=false, $way=null, $item=null) {
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $crit=array();
  if ($way=='composition') {
    $crit['idProductVersion']=$obj->id;
  } else if ($way=='structure') {
    $crit['idAsset']=$obj->id;
  } else {
    errorLog("unknown way=$way in drawVersionStructureFromObject()");
  }
  $pcs=new ProductAsset();
  $list=$pcs->getSqlElementsFromCriteria($crit);
  if (Parameter::getGlobalParameter('sortCompositionStructure')=='YES') {
    if ($way=='composition') {
      SqlElement::$_cachedQuery['ComponentVersion']=array(); 
      SqlElement::$_cachedQuery['ComponentVersionType']=array(); 
      usort($list, "ProductVersionStructure::sortCompositionComponentVersionListOnId");
    } else if ($way=='structure') {
      SqlElement::$_cachedQuery['Version']=array();
      SqlElement::$_cachedQuery['Type']=array(); 
      usort($list, "ProductVersionStructure::sortStructureComponentVersionListOnId");
    }
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  $actualStatus = '';
  if (!$print) {
    echo '<td class="linkHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      $critStatus = array('id' => $obj->idStatus);
      $actualStatus = SqlElement::getSingleSqlElementFromCriteria ( 'status', $critStatus);
      if ( ( (get_class($obj)!='ComponentVersion' && get_class($obj)!='ProductVersion') || $actualStatus->setIntoserviceStatus!=1) || ($way!='composition')) {
        echo '<a onClick="addProductVersionStructure(\''.$way.'\');" title="'.i18n('addProductVersionStructure').'" > '.formatSmallButton('Add').'</a>';
        if ($way=='composition' and count($list)>0) {
          echo '<a onClick="upgradeProductVersionStructure(null,false);" title="'.i18n('upgradeProductVersionStructure').'" > '.formatSmallButton('Switch').'</a>';
        }
      }
    }
    echo '</td>';
  }
  $listClass=($item=='ProductVersion')?'ComponentVersion':(($way=='structure')?'Version':'ComponentVersion');
  echo '<td class="linkHeader" style="width:5%">'.i18n($listClass).'</td>';
  echo '<td class="linkHeader sortable" style="width:40%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="linkHeader" style="width:10%">' . i18n('colIdStatus') . '</td>';
  echo '<td class="linkHeader" style="width:10%">' . i18n('colType') . '</td>';
  echo '</tr>';
  $showClosedItemComposition = Parameter::getUserParameter('showClosedItemComposition'); // Show closed items of composition of ComponentVersion
  $showClosedItemStructure = Parameter::getUserParameter('showClosedItemStructure'); // Show closed items of structure of Component Version
  $showClosedItemCompositionProduct = Parameter::getUserParameter('showClosedItemCompositionProduct'); // Show closed items of composition of ProductVersion
  foreach ($list as $comp) {
    //$critVersionType = array('id' => $obj->idVersionType);
    //$typeVersion = SqlElement::getSingleSqlElementFromCriteria('type',$critVersionType);
    
    $compObj=null;
    $paramItem=null;
    if ($way=='structure') {
      $compObj=new Version($comp->idProductVersion);
      $paramItem = $showClosedItemStructure;
    } else {
      $compObj=new Version($comp->idComponentVersion);
      if($typeVersion->scope=='ComponentVersion') {
        $paramItem = $showClosedItemComposition;
      } else if ($typeVersion->scope=='ProductVersion') {
        $paramItem = $showClosedItemCompositionProduct;
      }
    }
    if ($compObj->scope=='Product') $compObj=new ProductVersion($compObj->id);
    else $compObj=new ComponentVersion($compObj->id);
    if($paramItem==1 or !$compObj->idle) {
      drawElementIntoVersionStructureFromObject($comp, $compObj, $print, $canUpdate, $obj, $way, $actualStatus);
    }
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="ProductVersionStructureSectionCount" type="hidden" value="'.count($list).'" />';
  }
}
// UPDATE tLaguerie & dFayolle
// Used in function drawVersionStructureFromObject above.
// Draw an element into section Structure and Composition of ComponentVersion and Composition of ProductVersion
function drawElementIntoVersionStructureFromObject($comp, $compObj, $print, $canUpdate, $obj, $way, $actualStatus) {
  $userId = $comp->idUser;
  $userName = SqlList::getNameFromId('Affectable', $userId);
  $creationDate = $comp->creationDate;
  $canGoto = (securityCheckDisplayMenu(null, get_class($compObj)) and securityGetAccessRightYesNo('menu' . get_class($compObj), 'read', $compObj) == "YES") ? true : false;
  echo '<tr>';
  $classCompName = i18n(get_class($compObj));
  
  if (! $print) {
    echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
    if ($canUpdate && (((get_class($obj) != 'ComponentVersion' && get_class($obj) != 'ProductVersion') || $actualStatus->setIntoserviceStatus != 1) || ($way != 'composition'))) {
      if(get_class($obj)=='Asset'){
        echo '  <a onClick="editProductVersionStructureAsset(' . htmlEncode($comp->id) . ');" ' . 'title="' . i18n('editProductStructureAsset') . '" > ' . formatSmallButton('Edit') . '</a>';
      }else{
        echo '  <a onClick="editProductVersionStructure(\'' . $way . '\',' . htmlEncode($comp->id) . ');" ' . 'title="' . i18n('editProductStructure') . '" > ' . formatSmallButton('Edit') . '</a>';
      }
      if(get_class($obj)=='Asset'){
        echo '  <a onClick="removeProductVersionStructureAsset(' . "'" . htmlEncode($comp->id) . "','" . get_class($compObj) . "','" . htmlEncode($compObj->id) . "','" . $classCompName . "'" . ');" ' . 'title="' . i18n('removeProductStructure') . '" > ' . formatSmallButton('Remove') . '</a>';
      }else{
        echo '  <a onClick="removeProductVersionStructure(' . "'" . htmlEncode($comp->id) . "','" . get_class($compObj) . "','" . htmlEncode($compObj->id) . "','" . $classCompName . "'" . ');" ' . 'title="' . i18n('removeProductStructure') . '" > ' . formatSmallButton('Remove') . '</a>';
      }
      if ($way == 'composition') {
        echo '<a onClick="upgradeProductVersionStructure(\'' . $comp->id . '\',false);" title="' . i18n('upgradeProductVersionStructureSingle') . '" > ' . formatSmallButton('Switch') . '</a>';
      }
    }
    echo '</td>';
  }
  $goto = "";
  if (! $print and $canGoto) {
    $goto = ' onClick="gotoElement(' . "'" . get_class($compObj) . "','" . htmlEncode($compObj->id) . "'" . ');" style="cursor: pointer;" ';
  }
  
  // echo '<td class="linkData" style="white-space:nowrap;width:' . (($print)?'20':'15') . '%"><img src="css/images/icon'.get_class($compObj).'16.png" />&nbsp;'.$classCompName .' #' . $compObj->id;
  echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').' ' . $goto . ' " style="white-space:nowrap;width:' . (($print) ? '20' : '15') . '%"><table><tr><td>' . formatIcon(get_class($compObj), 16) . '</td><td style="vertical-align:top">&nbsp;' . '#' . $compObj->id . '</td></tr></table>';
  echo '</td>';
  echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
  echo htmlEncode($compObj->name);
  echo formatUserThumb($userId, $userName, 'Creator');
  echo formatDateThumb($creationDate, null);
  echo formatCommentThumb($comp->comment);
  // ADD tLAGUERIE AND dFAYOLLE
  $sts = new Status($compObj->idStatus);
  $nameStatus = $sts->name;
  $colorStatus = $sts->color;
  echo '<td class="dependencyData colorNameData"  style="width:10%">' . colorNameFormatter($nameStatus . "#split#" . $colorStatus) . '</td>';
  echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
  $nameType = SqlList::getNameFromId('Type', $compObj->idVersionType);
  echo htmlEncode($nameType);
  if(get_class($obj) != 'Asset'){
  echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
  echo htmlFormatDate($compObj->plannedDeliveryDate);
  echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" ' . $goto . ' style="position:relative;">';
  
  // END tLAGUERIE AND dFAYOLLE
  // ADD qCazelles - dateComposition
  
  if (Parameter::getGlobalParameter('displayMilestonesStartDelivery') == 'YES' and property_exists($compObj, 'realDeliveryDate')) {
    if ($compObj->realDeliveryDate) {
      $deliveryDate = $compObj->realDeliveryDate;
    } elseif ($compObj->plannedDeliveryDate) {
      $deliveryDate = $compObj->plannedDeliveryDate;
    } elseif ($compObj->initialDeliveryDate) {
      $deliveryDate = $compObj->initialDeliveryDate;
    }
    
    $errorDatesDelivery = false;
    if ($way == 'composition') {
      // CHANGE qCazelles - Correction red dates - Ticket 186
      // Old
      // if (isset ( $deliveryDate ) and $obj->plannedDeliveryDate and $obj->plannedDeliveryDate < $deliveryDate) {
      // New
      if (isset($deliveryDate) and (($obj->isDelivered and $obj->realDeliveryDate < $deliveryDate) or (! $obj->isDelivered and $obj->plannedDeliveryDate and $obj->plannedDeliveryDate < $deliveryDate))) {
        // END CHANGE qCazelles - Correction red dates - Ticket 186
        $errorDatesDelivery = true;
      }
    } elseif ($way == 'structure') {
      // CHANGE qCazelles - Correction red dates - Ticket 186
      // Old
      // if (isset ( $deliveryDate ) and $obj->plannedDeliveryDate and $obj->plannedDeliveryDate > $deliveryDate) {
      // New
      if (isset($deliveryDate) and (($obj->isDelivered and $obj->realDeliveryDate > $deliveryDate) or (! $obj->isDelivered and $obj->plannedDeliveryDate and $obj->plannedDeliveryDate > $deliveryDate))) {
        // END CHANGE qCazelles - Correction red dates - Ticket 186
        $errorDatesDelivery = true;
      }
    }
    
    if (isset($deliveryDate)) {
      echo (($errorDatesDelivery) ? '<span style="color: red;">' : '') . htmlFormatDate($deliveryDate) . (($errorDatesDelivery) ? '</span>' : '') . ' ';
      // ADD qCazelles - DeliveryDateXLS - Ticket #126
      unset($deliveryDate);
      // END ADD qCazelles - DeliveryDateXLS - Ticket #126
    }
  }
  
  // END ADD qCazelles - dateComposition
  
  echo '</td>';
  }
  echo '</tr>';
}
//END UPDATE tLaguerie & dFayolle

// ADD qCazelles - Version compatibility
function drawVersionCompatibility($obj, $refresh=false) {
  global $idObj;
  $vcs=new VersionCompatibility();
  $crit=array();
  $crit['idVersionA']=$obj->id;
  $list=$vcs->getSqlElementsFromCriteria($crit);
  
  $crit=array();
  $crit['idVersionB']=$obj->id;
  foreach ($vcs->getSqlElementsFromCriteria($crit) as $vc) {
    $list[]=$vc;
  }
  $idObj=$obj->id;
  
  SqlElement::$_cachedQuery['ProductVersion']=array(); // PBE : performance improvments
  usort($list, "ProductVersionStructure::sortProductVersionList");
  
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if (!$refresh) echo '<tr><td colspan="2">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="linkHeader" style="width:10%;white-space:nowrap">';
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addVersionCompatibility();" title="'.i18n('addVersionCompatibility').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '<button dojoType="dijit.form.Button" title="'.i18n('exportVersionCompatibilities').'" iconClass="imageColorNewGui dijitButtonIcon dijitButtonIconCsv" class=" noRotate roundedButtonSmall" style="border:0">';
    echo '<script type="dojo/connect" event="onClick" args="evt">';
    $page='../report/productVersionCompatibility.php?objectClass='.get_class($obj).'&objectId='.$obj->id;
    echo "var url='$page';";
    echo 'url+="&format=csv";';
    echo 'showPrint(url, null, null, "csv", "P");';
    echo '</script>';
    echo '</button>';
    echo '</td>';
  }
  $listClass='ProductVersion';
  echo '<td class="linkHeader" style="width:'.(($print)?'20':'15').'%">'.i18n($listClass).'</td>';
  echo '<td class="linkHeader sortable" style="width:80%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '</tr>';
  
  foreach ($list as $vc) {
    $userId=$vc->idUser;
    $userName=SqlList::getNameFromId('Affectable', $userId);
    $creationDate=$vc->creationDate;
    if ($vc->idVersionA==$obj->id) {
      $vcObj=new ProductVersion($vc->idVersionB);
    } else {
      $vcObj=new ProductVersion($vc->idVersionA);
    }
    $canGoto=(securityCheckDisplayMenu(null, get_class($vcObj)) and securityGetAccessRightYesNo('menu'.get_class($vcObj), 'read', $vcObj)=="YES")?true:false;
    echo '<tr>';
    $classVersionName=i18n(get_class($vcObj));
    if (!$print) {
      echo '<td class="linkData" style="text-align:center;width:5%;white-space:nowrap;">';
      if ($canUpdate) {
        echo '  <a onClick="removeVersionCompatibility('."'".htmlEncode($vc->id)."','".get_class($vcObj)."','".htmlEncode($vcObj->id)."','".$classVersionName."'".');" '.'title="'.i18n('removeVersionCompatibility').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    echo '<td class="linkData" style="white-space:nowrap;width:'.(($print)?'20':'15').'%"><table><tr><td>'.formatIcon(get_class($vcObj), 16).'</td><td style="vertical-align:top">&nbsp;'.'#'.$vcObj->id.'</td></tr></table>';
    echo '</td>';
    $goto="";
    if (!$print and $canGoto) {
      $goto=' onClick="gotoElement('."'".get_class($vcObj)."','".htmlEncode($vcObj->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<td class="linkData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" '.$goto.' style="position:relative;">';
    echo htmlEncode($vcObj->name);
    echo formatUserThumb($userId, $userName, 'Creator');
    echo formatDateThumb($creationDate, null);
    echo formatCommentThumb($vc->comment);
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="VersionCompatibilitySectionCount" type="hidden" value="'.count($list).'" />';
  }
}
// END ADD qCazelles - Version compatibility

// ADD qCazelles
function drawDeliverysFromObject($obj) {
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  
  echo '<tr>';
  echo '<td class="linkHeader" style="width:'.(($print)?'10':'5').'%">'.i18n('Delivery').'</td>';
  echo '<td class="linkHeader sortable" style="width:40%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="linkHeader" style="width:50%">'.i18n('colIdDeliveryStatus').'</td>';
  echo '</tr>';
  
  $delivery=new Delivery();
  $list=$delivery->getSqlElementsFromCriteria(array('idProductVersion'=>$obj->id), false, null, 'creationDateTime desc');
  
  $userId=$delivery->idUser;
  $user=new User($userId);
  $userName=$user->name;
  
  foreach ($list as $delivery) {
    $status=new Status($delivery->idStatus);
    echo '<tr onClick="gotoElement('."'Delivery','".htmlEncode($delivery->id)."'".');" style="cursor: pointer;">';
    echo '<td class="linkData">#'.htmlEncode($delivery->id).'</td>';
    echo '<td class="linkData">'.htmlEncode($delivery->name).'</td>';
    echo '<td class="linkData">'.htmlEncode($status->name);
    echo formatUserThumb($userId, $userName, 'Creator');
    
    // CHANGE qCazelles - Ticket #170
    // Old
    // if ($delivery->idle) {
    // echo formatDateThumb($delivery->idleDateTime, null);
    // } else if ($delivery->done) {
    // echo formatDateThumb($delivery->doneDateTime, null);
    // } else if ($delivery->handled) {
    // echo formatDateThumb($delivery->handledDateTime, null);
    // } else if ($delivery->plannedDate) {
    // echo formatDateThumb($delivery->plannedDate, null);
    // } else {
    // echo formatDateThumb($delivery->creationDateTime, null);
    // }
    // New
    if ($delivery->idle) {
      echo formatDateThumbWithText($delivery->idleDateTime, 'thumbIdleDateTitle');
    } else if ($delivery->cancelled) {
      echo formatDateThumbWithText(null, 'cancelled');
    } else if ($delivery->done) {
      echo formatDateThumbWithText($delivery->doneDateTime, 'thumbDoneDateTitle');
    } else if ($delivery->handled) {
      echo formatDateThumbWithText($delivery->handledDateTime, 'thumbHandledDateTitle');
    } else if ($delivery->plannedDate) {
      echo formatDateThumbWithText($delivery->plannedDate, 'thumbPlannedDateTitle');
    } else {
      echo formatDateThumb($delivery->creationDateTime, null);
    }
    // END CHANGE qCazelles - Ticket #170
    echo '</td>';
    echo '</tr>';
  }
}
// END ADD qCazelles
function drawApproverFromObject($list, $obj, $refresh=false) {
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="dependencyHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addApprover();" title="'.i18n('addApprover').'" class="roundedButtonSmall"> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="dependencyHeader" style="width:'.(($print)?'10':'5').'%">'.i18n('colId').'</td>';
  echo '<td class="dependencyHeader sortable" style="width:40%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="dependencyHeader" style="width:50%">'.i18n('colIdStatus').'</td>';
  echo '</tr>';
  if ($obj and get_class($obj)=='Document') {
    $docVers=new DocumentVersion($obj->idDocumentVersion);
  }
  foreach ($list as $app) {
    $appName=SqlList::getNameFromId('Affectable', $app->idAffectable);
    echo '<tr>';
    if (!$print) {
      echo '<td class="dependencyData" style="text-align:center;">';
      if ($canUpdate) {
        echo '  <a onClick="removeApprover('."'".htmlEncode($app->id)."','".$appName."'".');" title="'.i18n('removeApprover').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    echo '<td class="dependencyData">#'.htmlEncode($app->id).'</td>';
    echo '<td class="dependencyData">'.htmlEncode($appName).'</td>';
    echo '<td class="dependencyData">';
    $approved=0;
    $disapproved=0;
    $compMsg="";
    $approvedDate="";
    $disapprovedDate="";
    $approverId=null;
    if ($obj and get_class($obj)=='Document') {
      $crit=array('refType'=>'DocumentVersion', 'refId'=>$obj->idDocumentVersion, 'idAffectable'=>$app->idAffectable);
      $versApp=SqlElement::getSingleSqlElementFromCriteria('Approver', $crit);
      if ($versApp->id) {
        $approved=$versApp->approved;
        $disapproved=$versApp->disapproved;
        $compMsg=' '.$docVers->name;
        $approvedDate=" (".htmlFormatDateTime($versApp->approvedDate, false).")";
        $disapprovedDate=" (".htmlFormatDateTime($versApp->disapprovedDate, false).")";
        $approverId=$versApp->id;
      }
    } else if($obj and get_class($obj)=='Decision'){ 
      $crit=array('refType'=>'Decision', 'refId'=>$obj->id, 'idAffectable'=>$app->idAffectable);
      $versApp=SqlElement::getSingleSqlElementFromCriteria('Approver', $crit);
      if ($versApp->id) {
      	$approved=$versApp->approved;
      	$disapproved=$versApp->disapproved;
      	//$compMsg=' '.$obj->name;
      	$approvedDate=" (".htmlFormatDateTime($versApp->approvedDate, false).")";
      	$disapprovedDate=" (".htmlFormatDateTime($versApp->disapprovedDate, false).")";
      	$approverId=$versApp->id;
      }
      
    }else if ($obj and get_class($obj)=='OutgoingMail'){
      $crit=array('refType'=>'OutgoingMail', 'refId'=>$obj->id, 'idAffectable'=>$app->idAffectable);
      $versApp=SqlElement::getSingleSqlElementFromCriteria('Approver', $crit);
      if ($versApp->id) {
        $approved=$versApp->approved;
        $disapproved=$versApp->disapproved;
        //$compMsg=' '.$obj->name;
        $approvedDate=" (".htmlFormatDateTime($versApp->approvedDate, false).")";
        $disapprovedDate=" (".htmlFormatDateTime($versApp->disapprovedDate, false).")";
        $approverId=$versApp->id;
      }
    }else if ($obj and get_class($obj)=='IncomingMail'){   
      $crit=array('refType'=>'IncomingMail', 'refId'=>$obj->id, 'idAffectable'=>$app->idAffectable);
      $versApp=SqlElement::getSingleSqlElementFromCriteria('Approver', $crit);
      if ($versApp->id) {
        $approved=$versApp->approved;
        $disapproved=$versApp->disapproved;
        //$compMsg=' '.$obj->name;
        $approvedDate=" (".htmlFormatDateTime($versApp->approvedDate, false).")";
        $disapprovedDate=" (".htmlFormatDateTime($versApp->disapprovedDate, false).")";
        $approverId=$versApp->id;
      }
    }else {
      $approved=$app->approved;
      $disapproved=$app->disapproved;
      $approverId=$app->id;
      $approvedDate=" (".htmlFormatDateTime($app->approvedDate, false).")";
      $disapprovedDate=" (".htmlFormatDateTime($app->disapprovedDate, false).")";
    }
    echo '<table style="width:100%"><tr>';
    if ($approved and !$disapproved) {
      echo '<td>';
      echo '<img src="../view/img/check.png" style="position:relative;height:12px;top:2px;"/>&nbsp;';
      echo i18n("approved").$compMsg.$approvedDate;
      echo '</td>';
    }else if(!$approved and $disapproved){
      echo '<td style="white-space:nowrap"><img src="../view/img/uncheck.png" style="position:relative;height:12px;top:2px;"/>&nbsp;'.formatCommentThumb($versApp->disapprovedComment).'</td>';
      echo '<td>'.i18n("disapproved").$compMsg.$disapprovedDate.'&nbsp;</td>';
      if ($user->id==$app->idAffectable and !$print and $versApp->id) {
      	echo '<td><button dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">';
      	echo i18n('approveNow');
      	echo '  <script type="dojo/connect" event="onClick" args="evt">';
      	echo '   approveItem('.$approverId.', \'approved\');';
      	echo '  </script>';
      	echo '</button></td>';
      }
    } else {
      echo '<td>';
      echo i18n("notApproved").$compMsg;
      if ($user->id==$app->idAffectable and !$print  and $versApp->id) {
        echo '&nbsp;&nbsp;<button dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">';
        echo i18n('approveNow');
        echo '  <script type="dojo/connect" event="onClick" args="evt">';
        echo '   approveItem('.$approverId.', \'approved\');';
        echo '  </script>';
        echo '</button>';
        echo '&nbsp;&nbsp;<button dojoType="dijit.form.Button" showlabel="true" class="roundedVisibleButton">';
        echo i18n('disapproveNow');
        echo '  <script type="dojo/connect" event="onClick" args="evt">';
        echo '   disapproveItem('.$approverId.');';
        echo '  </script>';
        echo '</button>';
      }
      echo '</td>';
    }
    echo '</tr></table>';
    echo '</td>';
    echo '</tr>';
  }
  echo '</table></td></tr>';
}

function compareByTimeStamp($time1, $time2){
  if (pq_strtotime($time1) < pq_strtotime($time2))
    return 1;
  else if (pq_strtotime($time1) > pq_strtotime($time2))
    return -1;
  else
    return 0;
}

function drawDependenciesFromObject($list, $obj, $depType, $refresh=false) {
  global $cr, $print, $user, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canEdit=$canUpdate;
  if (get_class($obj)=="Term" or get_class($obj)=="Requirement" or get_class($obj)=="TestCase") {
    $canEdit=false;
  }
  if (get_class($obj)=="Term") {
    if ($obj->idBill) $canUpdate=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$refresh) echo '<tr><td colspan=2 style="width:100%;">';
  $dependencyTableWidth=($print and $depType=="Successor")?'98%':'100%';
  echo '<table style="width:'.$dependencyTableWidth.';">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="dependencyHeader" style="width:10%">';
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addDependency('."'".$depType."'".');" title="'.i18n('addDependency'.$depType).'"> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  $dependencyElementWidth=($print)?(($depType=="Predecessor")?'25':'30'):'20';
  $dependencyNameWidth=($print)?(($depType=="Predecessor")?'45':'55'):'40';
  $dependencyStatusWidth=($print)?'15':'15';
  echo '<td class="dependencyHeader" style="width:'.$dependencyElementWidth.'%">'.i18n('colElement').'</td>';
  echo '<td class="dependencyHeader sortable" style="width:'.$dependencyNameWidth.'%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="dependencyHeader" style="width:'.$dependencyStatusWidth.'%">'.i18n('colIdStatus').'</td>';
  //gautier #3562
  if($depType=="Predecessor"){
    $tabGlobalElement = array();
    $tabGlobalElement['Decision']= 'decisionDate';
    $tabGlobalElement['Action']= 'actualDueDate';
    $tabGlobalElement['Delivery']= 'validationDate';
    $tabGlobalElement['Issue']= 'actualEndDate';
    $tabGlobalElement['Opportunity']= 'actualEndDate';
    $tabGlobalElement['Question']= 'actualDueDate';
    $tabGlobalElement['Risk']= 'actualEndDate';
    $tabGlobalElement['Ticket']= 'actualDueDateTime';
    echo '<td class="dependencyHeader" style="width:15%">'.i18n('colEndDate').'</td>';
    $datePredecessor = array();
    $allTabSameDate = false;
    $endDateObj = array();
    $endDateDelay = null;
    foreach ($list as $dep) {
      $depObj=new $dep->predecessorRefType($dep->predecessorRefId);
      $planningObj=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', array('refId'=>$depObj->id, 'refType'=>get_class($depObj),'idProject'=>(get_class($depObj)=='Project')?$depObj->id:$depObj->idProject));
      if(pq_array_key_exists($dep->predecessorRefType,$tabGlobalElement)){
        $date = $tabGlobalElement[$dep->predecessorRefType];
        if($depObj->$date){
          $endDate=$depObj->$date;
          $datePredecessor[$dep->predecessorRefType."#".$depObj->id] = $endDate;
        }else{
          $endDate=null;
        }
      }else{
        if($planningObj->realEndDate){
          $endDate = $planningObj->realEndDate;
        }elseif ($planningObj->plannedEndDate){
          $endDate = $planningObj->plannedEndDate;
        }elseif ($planningObj->validatedEndDate){
          $endDate = $planningObj->validatedEndDate;
        }else{
          $endDate = null;
        }
      }
      if($dep->dependencyDelay>1){
        $datePredecessor[$planningObj->id]=addWorkDaysToDate($endDate,$dep->dependencyDelay+1);
      }else{
        $datePredecessor[$planningObj->id]=addWorkDaysToDate($endDate,$dep->dependencyDelay);
      }
      $endDateObj[$dep->id.get_class($depObj)]= $endDate;
    }
    usort($datePredecessor, "compareByTimeStamp");
    if(count($datePredecessor)>1){
      foreach ($datePredecessor as $val){
        if($val != $datePredecessor[0]){
          $allTabSameDate = true;
        }
      }
    }
  }
  echo '</tr>';
  foreach ($list as $dep) {
    $depObj=null;
    if ($dep->predecessorRefType==get_class($obj) and $dep->predecessorRefId==$obj->id) {
      $depObj=new $dep->successorRefType($dep->successorRefId);
      // $depType="Successor";
    } else {
      $depObj=new $dep->predecessorRefType($dep->predecessorRefId);
      // $depType="Predecessor";
    }
    echo '<tr>';
    $securityCheckDisplayMenu = securityCheckDisplayMenu(null, get_class($depObj));
    $securityGetAccessRightYesNo = securityGetAccessRightYesNo('menu'.get_class($depObj), 'read', $depObj);
    if (!$print) {
      echo '<td class="dependencyData" style="text-align:center;white-space:nowrap;">';
      if ($canEdit and  $securityGetAccessRightYesNo=="YES") {
        echo '  <a onClick="editDependency(\''.$depType.'\',\''.htmlEncode($dep->id).'\',\''.SqlList::getIdFromName('Dependable', i18n(get_class($depObj))).'\',\''.get_class($depObj).'\',\''.htmlEncode($depObj->id).'\',\''.htmlEncode($dep->dependencyDelay).'\',\''.$dep->dependencyType.'\');" title="'.i18n('editDependency'.$depType).'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canUpdate and  $securityGetAccessRightYesNo=="YES") {
        echo '  <a onClick="removeDependency('."'".htmlEncode($dep->id)."','".get_class($depObj)."','".htmlEncode($depObj->id)."'".');" '.'title="'.i18n('removeDependency'.$depType).'"/> '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    $goto="";

    if ($securityCheckDisplayMenu and $securityGetAccessRightYesNo=="YES" and !$print) {
      $goto=' onClick="hideTooltip(this);gotoElement('."'".get_class($depObj)."','".htmlEncode($depObj->id)."'".');" ';
    }
    $dependencyElementStyle=($print)?'white-space:normal;width:'.$dependencyElementWidth.'%;cursor: pointer;':'white-space:nowrap;cursor: pointer;';
    echo '<td class="dependencyData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="'.$dependencyElementStyle.'" '.$goto.'><table><tr><td>'.formatIcon(get_class($depObj), 16).'</td><td>&nbsp;'.i18n(get_class($depObj)).' #'.htmlEncode($depObj->id).'</td></tr></table></td>';
    
    $projectObjId = $obj->idProject;
    $projectDepId = $depObj->idProject;
    $projectDep = new Project($depObj->idProject);
    $projectNameDep = $projectDep->name;
    $pe = get_class($depObj).'PlanningElement';
    $planningMode = new PlanningMode ();
    if (property_exists(get_class($depObj),$pe)){
      $objectInfo = json_encode($depObj->$pe);
      $planningMode = new PlanningMode($depObj->$pe->idPlanningMode);
      if ($depObj->$pe->refType == 'Project') $projectDep = $depObj;
    }else {
      $objectInfo = json_encode($depObj);
    }
    $res = new Resource ();
    $productVersion = new ProductVersion();
    $type= new Type();
    $idType = 'id'.get_class($depObj).'Type';
    if (property_exists($depObj, $idType)) $type= new Type($depObj->$idType);
    if (property_exists($depObj, 'idResource')) $res = new Resource ($depObj->idResource);
    if (property_exists($depObj, 'idTargetProductVersion')) $productVersion = new ProductVersion($depObj->idTargetProductVersion);

    $dependencyNameStyle=($print)?'cursor: pointer; border-left:0px; width:'.$dependencyNameWidth.'%; white-space:normal;':'cursor: pointer; border-left:0px; display:flex;';
    echo '<td class="dependencyData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="'.$dependencyNameStyle.'" '.$goto.'>';
    if($projectDepId != $projectObjId){
      echo '<div style="margin-right:10px;" title="'.$projectNameDep.'">'.formatIcon("Project", 16, $projectNameDep).'</div>';
    }
    echo '<div class="dependencyName"  onmouseout="hideTooltip(this)" onmouseenter="showTooltip(this, ' . htmlEncode(json_encode($projectDep)) . ', ' . htmlEncode($objectInfo) . ', ' . htmlEncode(json_encode($res)) . ', ' . htmlEncode(json_encode($productVersion)) . ', ' . htmlEncode(json_encode($type)) . ', ' . htmlEncode(json_encode($planningMode)) . ')" onmouseleave="hideTooltip(this)" style="justify-self:start;'.(($print)?'white-space:normal;':'').'" onfocusout="hideTooltip(this)">'.htmlEncode($depObj->name).'</div>';

    //KEVIN TICKET #2038
    $titleType=(pq_substr($dep->dependencyType, 0, 1)=='E')?i18n('colEnd'):i18n('colStart');
    $titleType.='-';
    $titleType.=(pq_substr($dep->dependencyType, -1)=='E')?i18n('colEnd'):i18n('colStart');
    echo '<img style="float:right; margin: 0px 2px; margin-left: auto;" title="'.$titleType.'" src="../view/css/images/dependency_'.$dep->dependencyType.'.png"/>';
    if ($dep->dependencyDelay!=0 and $canEdit) {
      echo '<span style="float:right;background-color:#FFF8DC; color:#696969; border:1px solid #A9A9A9;" title="'.i18n("colDependencyDelay").'">&nbsp;'.htmlEncode($dep->dependencyDelay).'&nbsp;'.i18n('shortDay').'&nbsp;</span>';
    }
    if ($dep->comment) {
      echo '<div style="float:right;margin: 0px 2px;">'.formatCommentThumb($dep->comment).'</div>';
    }
    echo '</td>';
    
    
    if (property_exists($depObj, 'idStatus')) {
      $objStatus=new Status($depObj->idStatus);
    } else {
      $objStatus=new Status();
    }
    // $color=$objStatus->color;
    // $foreColor=getForeColor($color);
    // echo '<td class="dependencyData"><table><tr><td style="background-color: ' . htmlEncode($objStatus->color) . '; color:' . $foreColor . ';">' . htmlEncode($objStatus->name) . '</td></tr></table></td>';
    // echo '<td class="dependencyData" style="background-color: ' . htmlEncode($objStatus->color) . '; color:' . $foreColor . ';">' . htmlEncode($objStatus->name) . '</td>';
    echo '<td class="dependencyData colorNameData" style="width:'.$dependencyStatusWidth.'%">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</td>';
    if($depType=="Predecessor"){    
      if($allTabSameDate==true and $datePredecessor and count($datePredecessor)>1 and $datePredecessor[0]== addWorkDaysToDate($endDateObj[$dep->id.get_class($depObj)],($dep->dependencyDelay>1)?$dep->dependencyDelay+1:$dep->dependencyDelay)){
        echo '<td class="dependencyData" style="text-align:center; width:15%; color:red">'.htmlFormatDate($endDateObj[$dep->id.get_class($depObj)],true).'</td>';
      }else{
        echo '<td class="dependencyData" style="text-align:center; width:15%">'.htmlFormatDate($endDateObj[$dep->id.get_class($depObj)],true).'</td>';
      }
    }
    echo '</tr>';
  }
  echo '</table>';
  if (!$refresh) echo '</td></tr>';
  if (!$print) {
    echo '<input id="'.$depType.'DependencySectionCount" type="hidden" value="'.count($list).'" />';
  }
}

function drawAssignmentsFromObject($list, $obj, $refresh=false, $comboDetailAssignment=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail, $section, $collapsedList, $widthPct, $outMode, $profile;
  if ($comboDetail) {
    //return;
  }
  if ($list==null) {
    $list=array();
    if ($obj and $obj->id) {
      $ass=new Assignment();
      $list=$ass->getSqlElementsFromCriteria(array('refType'=>get_class($obj),'refId'=>$obj->id));
    }
  }
//   if(get_class($obj)=='PokerSession'){
//     $ass = new Assignment();
//     $list = $ass->getSqlElementsFromCriteria(array('refType'=>'PokerSession', 'refId'=>$obj->id));
//   }
  $dialogEdit = ($comboDetailAssignment)?'dialogEdit_':'';
  $showClosedAssignment=Parameter::getUserParameter('showClosedAssignment');
  if($showClosedAssignment == '')$showClosedAssignment=true;

  if ($obj->idle == 1){
    $showClosedAssignment=true;
  }
  if(get_class($obj)=='PeriodicMeeting')$showClosedAssignment=true;
  $pluginObjectClass='Assignment';
  
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  
  $today = date('Y-m-d');
  if(get_class($obj)=='Meeting'){
    $today = $obj->meetingDate;
  }
  $firstDay = date('Y-m-d', firstDayofWeek(pq_substr($today, 4, 2),pq_substr($today, 0, 4)));
  
  $tableObject=array();
  //gautier #accesImputation
  $canSeeDirectAcces = false;
  foreach ($list as $assignment) {
    if(!$showClosedAssignment and $assignment->idle)continue;
    if($assignment->idResource == $user->id and !$assignment->isMaterial){
      $canSeeDirectAcces = true;
      $idAssignment = $assignment->id;
    }
    $name=SqlList::getNameFromId('ResourceAll', $assignment->idResource);
    $tableObject[$name.'_'.$assignment->id]=$assignment;
  }
  ksort($tableObject,SORT_STRING );
  $list=$tableObject;
  $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'assignmentView'));
  if ($habil and $habil->rightAccess!=1) {
    if($canSeeDirectAcces){
      $goto="
        if (checkFormChangeInProgress()) {
          return;
        }
        if(dijit.byId('dialogEditAssignmentPlanning')){
          dijit.byId('dialogEditAssignmentPlanning').hide();
        }
        var callback = accessImputationCallBack();
        saveDataToSession('userName',$user->id,false, function() {
        saveDataToSession('yearSpinner',".intval(pq_substr($today, 0, 4)).",false, function() {
          saveDataToSession('weekSpinner',".pq_substr(weekFormat($today), 5, 2).",false, function() {
  		   saveDataToSession('dateSelector','$firstDay',false, function() {
  		    loadContent('../view/imputationMain.php?idAssignment=".$idAssignment."','centerDiv',null,null,null,null,null,callback);}); }); }); });";
      
      echo'<tr> <td style="width:10%;"><a onClick="'.$goto.'" style="cursor: pointer;" title="'.i18n('gotoMyImputation').'" > '.formatBigButton('Goto',true).'</a> </td>
           <td> '.i18n('gotoMyImputation'). '</td></tr>';
    }
    return;
  }
  // $section='Assignment';
  // startTitlePane(get_class ( $obj ), $section, $collapsedList, $widthPct, $print, $outMode, "yes", $nbCol);
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'assignmentEdit'));
  if ($habil and $habil->rightAccess!=1) {
    $canUpdate=false;
  }
  if ($comboDetail) {$canUpdate=false;}
  // PBER #7080 : New right on V10.3 : now has full rights definition on Assignment object (due to addition of new Screen)
  $ass=new Assignment();
  $ass->id=1;$ass->idProject=$obj->idProject;
  if (securityGetAccessRightYesNo('menuAssignment', 'update', $ass)!="YES") $canUpdate=false;
  // PBER #7080
  $pe=new PlanningElement();
  $pe->setVisibility($profile);
  $workVisible=($pe->_workVisibility=='ALL')?true:false;  
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  $planningMode=null;
  $peName=get_class($obj).'PlanningElement';
  if (property_exists($obj, $peName)) {
    $idPm=$obj->$peName->idPlanningMode;
    $pmObj=new PlanningMode($idPm);
    $planningMode=$pmObj->code;
  }
  //gautier #6022
  if (!$print and $canUpdate and $obj->id) {
    echo '<tr style="margin-bottom:5px;"><td colspan=2>'.i18n('automaticAssignment');
    $valueSwitch= null;
    if(get_class($obj)=='PeriodicMeeting'){
      $peName = 'MeetingPlanningElement';
    }
    $onOff = $obj->$peName->automaticAssignment;
    if($onOff == 1)$valueSwitch = true;
    $nameSwitch = $dialogEdit.get_class($obj).$obj->id.'automaticAssignment';
    htmlDrawSwitchAssign($nameSwitch,$valueSwitch,get_class($obj),$obj->id);
    echo '</td></tr><tr><td>&nbsp;&nbsp;</td></tr>';
  }
  echo '<input id="'.$dialogEdit.'automaticAssignment1" name="'.$dialogEdit.'automaticAssignment1" type="hidden" value="1"/>';
  echo '<input id="'.$dialogEdit.'planningMode" name="'.$dialogEdit.'planningMode" type="hidden" value="'.$planningMode.'"/>';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (!$print and $canUpdate) {
    echo '<td class="assignHeader" style="width:10%;vertical-align:middle;white-space:nowrap">';
    if ($obj->id!=null and !$print and $canUpdate and !$obj->idle and $workVisible) {
      echo '<a onClick="addAssignment(\''.Work::displayShortWorkUnit().'\',\''.Work::getWorkUnit().'\',\''.Work::getHoursPerDay().'\', false, false, false, false);" ';
      echo ' title="'.i18n('addAssignment').'" > '.formatSmallButton('Add').'</a>';
      echo '<a onClick="addAssignment(\''.Work::displayShortWorkUnit().'\',\''.Work::getWorkUnit().'\',\''.Work::getHoursPerDay().'\', true, false, false, false);" ';
      echo ' title="'.i18n('addAssignmentTeam').'" > '.formatSmallButton('Team', true).'</a>';
      echo '<a onClick="addAssignment(\''.Work::displayShortWorkUnit().'\',\''.Work::getWorkUnit().'\',\''.Work::getHoursPerDay().'\', false, true, false, false);" ';
      echo ' title="'.i18n('addAssignmentOrganization').'" > '.formatSmallButton('Organization', true).'</a>';
      echo '<a onClick="addAssignment(\''.Work::displayShortWorkUnit().'\',\''.Work::getWorkUnit().'\',\''.Work::getHoursPerDay().'\', false, false, true, false);" ';
      echo ' title="'.i18n('addAssignmentResourceTeam').'" > '.formatSmallButton('ResourceTeam', true).'</a>';
      echo '<a onClick="addAssignment(\''.Work::displayShortWorkUnit().'\',\''.Work::getWorkUnit().'\',\''.Work::getHoursPerDay().'\', false, false, false, true);" ';
      echo ' title="'.i18n('addAssignmentResourceMaterial').'" > '.formatSmallButton('ResourceMaterial', true).'</a>';
    }
    if($canSeeDirectAcces){
      $goto="
            if (checkFormChangeInProgress()) {
              return;
            }
            if(dijit.byId('dialogEditAssignmentPlanning')){
              dijit.byId('dialogEditAssignmentPlanning').hide();
            }
            var callback = accessImputationCallBack(); 
             saveDataToSession('userName',$user->id,false, function() {
             saveDataToSession('yearSpinner',".intval(pq_substr($today, 0, 4)).",false, function() {
  		       saveDataToSession('weekSpinner',".pq_substr(weekFormat($today), 5, 2).",false, function() {
      		   saveDataToSession('dateSelector','$firstDay',false, function() {
      		   loadContent('../view/imputationMain.php?idAssignment=".$idAssignment."','centerDiv',null,null,null,null,null,callback);}); }); }); });";
      echo '<a onClick="'.$goto.'" style="cursor: pointer;" ';
      echo ' title="'.i18n('gotoMyImputation').'" > '.formatSmallButton('Goto',true).'</a>';
    }
    echo '</td>';
  } else if(!$print and !$canUpdate and $canSeeDirectAcces){
    echo '<td class="assignHeader" style="width:10%;vertical-align:middle;">';
    if($canSeeDirectAcces){
          $goto="
          if (checkFormChangeInProgress()) {
            return;
          }
          if(dijit.byId('dialogEditAssignmentPlanning')){
            dijit.byId('dialogEditAssignmentPlanning').hide();
          }
          var callback = accessImputationCallBack();
          saveDataToSession('userName',$user->id,false, function() {
          saveDataToSession('yearSpinner',".intval(pq_substr($today, 0, 4)).",false, function() {
  		    saveDataToSession('weekSpinner',".pq_substr(weekFormat($today), 5, 2).",false, function() {
          		   saveDataToSession('dateSelector','$firstDay',false, function() {
          		   loadContent('../view/imputationMain.php?idAssignment=".$idAssignment."','centerDiv',null,null,null,null,null,callback);}); }); }); });";
      echo '<a onClick="'.$goto.'" style="cursor: pointer;" ';
      echo ' title="'.i18n('gotoMyImputation').'" > '.formatSmallButton('Goto',true).'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader sortable" style="width:'.(($print)?'40':'30').'%" onclick="onColumnHeaderClickedSort(event)">'.i18n('colIdResource').'</td>';
  echo '<td class="assignHeader" style="width:15%" >'.i18n('colRateOrEtp').'</td>';
  if ($workVisible) {
    echo '<td class="assignHeader" style="width:15%">'.i18n('colAssigned').' ('.Work::displayShortWorkUnit().')'.'</td>';
    echo '<td class="assignHeader"style="width:15%">'.i18n('colReal').' ('.Work::displayShortWorkUnit().')'.'</td>';
    echo '<td class="assignHeader" style="width:15%">'.i18n('colLeft').' ('.Work::displayShortWorkUnit().')'.'</td>';
  }
  echo '</tr>';
  $fmt=getNumberFormatter52($browserLocale, NumberFormatter52::DECIMAL);
  foreach ($list as $assignment) {
    $idleClass=($assignment->idle or $assignment->supportedAssignment)?' affectationIdleClass':'';
    echo '<tr height="29px">';
    $isResource=true;
    $resName=SqlList::getNameFromId('Resource', $assignment->idResource);
    if ($resName==$assignment->idResource) {
      $affName=SqlList::getNameFromId('Affectable', $assignment->idResource);
      if ($affName!=$resName) {
        $isResource=false;
        $resName=$affName;
      }
    }
    if (!$print and ($canUpdate or $canSeeDirectAcces)) {
      echo '<td class="assignData'.$idleClass.'" style="width:10%;text-align:center;white-space:nowrap;vertical-align:middle">';
      if ($canUpdate and !$print and $workVisible and !$assignment->supportedAssignment) {
        echo '  <a onClick="editAssignment('."'".htmlEncode($assignment->id)."'".",'".htmlEncode($assignment->idResource)."'".",'".htmlEncode($assignment->idRole)."'".",'".($assignment->dailyCost*100)."'".",'".htmlEncode($assignment->rate)."'".",'".(Work::displayWork($assignment->assignedWork)*100)."'".",'".(Work::displayWork($assignment->realWork)*100)."'".",'".(Work::displayWork($assignment->leftWork)*100)."'".",'".Work::displayShortWorkUnit()."'".",".$assignment->optional.');" '.'title="'.i18n('editAssignment').'" > '.formatSmallButton('Edit').'</a>';
        echo '<textarea style="display:none" id="'.$dialogEdit.'comment_assignment_'.htmlEncode($assignment->id).'" >'.htmlEncode($assignment->comment)."</textarea>";
      }
      if ($assignment->realWork==0 and $canUpdate and !$print and $workVisible and !$assignment->supportedAssignment) {
        echo '  <a onClick="removeAssignment('."'".htmlEncode($assignment->id)."','".(Work::displayWork($assignment->realWork)*100)."','".htmlEncode($resName, 'quotes')."'".');" '.'title="'.i18n('removeAssignment').'" > '.formatSmallButton('Remove').'</a>';
      }
      if ($canUpdate and !$print and $workVisible and !$assignment->idle) {
        if($planningMode != 'MAN'  and !$assignment->supportedAssignment){
          echo '  <a onClick="divideAssignment('.htmlEncode($assignment->id).',\''.Work::displayShortWorkUnit().'\');" '.'title="'.i18n('divideAssignment').'" > '.formatSmallButton('Split').'</a>';
        }
        //gautier #directAcces
        $listUser=getListForSpecificRights('imputation');
        if(!$assignment->isResourceTeam and isset($listUser[$assignment->idResource]) and !$assignment->isMaterial){
          $goto=" 
              if (checkFormChangeInProgress()) {
                return;
              }
              if(dijit.byId('dialogEditAssignmentPlanning')){
                dijit.byId('dialogEditAssignmentPlanning').hide();
              }
              var callback = accessImputationCallBack();
             saveDataToSession('userName',$assignment->idResource,false, function() {
             saveDataToSession('yearSpinner',".intval(pq_substr($today, 0, 4)).",false, function() {
  		       saveDataToSession('weekSpinner',".pq_substr(weekFormat($today), 5, 2).",false, function() {
      		   saveDataToSession('dateSelector','$firstDay',false, function() {
      		   loadContent('../view/imputationMain.php?idAssignment=".$assignment->id."','centerDiv',null,null,null,null,null,callback);}); }); }); });";
          echo '<a onClick="'.$goto.'" style="cursor: pointer;" ';
          echo ' title="'.i18n('gotoImputation').'" > '.formatSmallButton('Goto',true).'</a>';
        }
        echo '</td>';
      }else{
        if ($assignment->idle) {
          echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
        } else {
          echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
        }
        echo '</td>';
      }
    }elseif(!$print and !$canUpdate and $workVisible and !$assignment->idle and !$assignment->supportedAssignment and $canSeeDirectAcces){
      echo '<td class="assignData'.$idleClass.'" style="width:10%;text-align:center;white-space:nowrap;vertical-align:middle">';
        //gautier #directAcces
        $listUser=getListForSpecificRights('imputation');
        if(!$assignment->isResourceTeam and isset($listUser[$assignment->idResource])){
          $goto=" 
          if (checkFormChangeInProgress()) {
            return;
          }
          if(dijit.byId('dialogEditAssignmentPlanning')){
            dijit.byId('dialogEditAssignmentPlanning').hide();
          }
          var callback = accessImputationCallBack();
          saveDataToSession('userName',$assignment->idResource,false, function() {
          saveDataToSession('yearSpinner',".intval(pq_substr($today, 0, 4)).",false, function() {
  		    saveDataToSession('weekSpinner',".pq_substr(weekFormat($today), 5, 2).",false, function() {
          saveDataToSession('dateSelector','$firstDay',false, function() {
          loadContent('../view/imputationMain.php?idAssignment=".$assignment->id."','centerDiv',null,null,null,null,null,callback);}); }); }); });";
          echo '<a onClick="'.$goto.'" style="cursor: pointer;" ';
          echo ' title="'.i18n('gotoImputation').'" > '.formatSmallButton('Goto',true).'</a>';
        }
        echo '</td>';
    }
    echo '<td class="assignData'.$idleClass.'" style="width:'.(($print)?'40':'30').'%;vertical-align:middle">';
    echo '<table width="100%"><tr>';
    $goto="";
    $resource=new ResourceAll($assignment->idResource);
    if ($resource->isResourceTeam) {
      if (securityCheckDisplayMenu(null, 'ResourceTeam') and securityGetAccessRightYesNo('menuResourceTeam', 'read', '')=="YES") {
        $goto=' onClick="if(dijit.byId(\'dialogEditAssignmentPlanning\')){dijit.byId(\'dialogEditAssignmentPlanning\').hide();}gotoElement(\'ResourceTeam\',\''.htmlEncode($assignment->idResource).'\');" style="cursor: pointer;" ';
      }
    } else if($resource->isMaterial){
      if (!$print and securityCheckDisplayMenu(null, 'ResourceMaterial') and securityGetAccessRightYesNo('menuResourceMaterial', 'read', '')=="YES") {
        $goto=' onClick="if(dijit.byId(\'dialogEditAssignmentPlanning\')){dijit.byId(\'dialogEditAssignmentPlanning\').hide();}gotoElement(\'ResourceMaterial\',\''.htmlEncode($assignment->idResource).'\');" style="cursor: pointer;" ';
      }
    } else {
      if (!$print and $isResource and securityCheckDisplayMenu(null, 'Resource') and securityGetAccessRightYesNo('menuResource', 'read', '')=="YES") {
        $goto=' onClick="if(dijit.byId(\'dialogEditAssignmentPlanning\')){dijit.byId(\'dialogEditAssignmentPlanning\').hide();}gotoElement(\'Resource\',\''.htmlEncode($assignment->idResource).'\');" style="cursor: pointer;" ';
      }
    }
    echo '<td '.$goto.' class="'.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'">'.$resName;
    echo ($assignment->idRole)?' ('.SqlList::getNameFromId('Role', $assignment->idRole).')':'';
    if($assignment->isMaterial){
      echo '<div style="float:right; vertical-align:middle;"> '.formatIcon('ResourceMaterial', 16, i18n('ResourceMaterial')).'</div>';
    }
    echo '</td>';
    if ($assignment->notPlannedWork>0) {
      echo '<td>';
      echo '&nbsp;<span style="float:right;background-color:#9933CC; color:#FFFFFF; border:1px solid #A9A9A9;" title="'.i18n("colNotPlannedWork").'">&nbsp;'.Work::displayWorkWithUnit($assignment->notPlannedWork).'&nbsp;</span>';
      echo '</td>';
    }
    if ($assignment->comment and !$print) {
      echo '<td>';
      echo formatCommentThumb($assignment->comment);
      echo '</td>';
    }
    $resInc = new ResourceIncompatible();
    $incompatible = $resInc->getSqlElementsFromCriteria(array('idResource'=>$assignment->idResource));
    if ($incompatible and !$print) {
        $listImcompatible=i18n('ResourceIncompatible').' :</br>';
        foreach ($incompatible as $id=>$val){
          $res = new ResourceAll($val->idIncompatible);
          $listImcompatible .= '&nbsp;&nbsp;&nbsp;#'.$res->id.' '.$res->name.'</br>';
        }
    	echo '<td title="'.i18n('resourceIncompatible').'" onmouseover="showBigImage(null,null,this, \''.$listImcompatible.'\');" onmouseout="hideBigImage();">';
    	echo formatIcon('Incompatible', 22);
    	echo '</td>';
    }
    $resSupp = new ResourceSupport();
    $support = $resSupp->getSqlElementsFromCriteria(array('idResource'=>$assignment->idResource));
    if ($support and !$print and $assignment->isManual!=1) {
        $listSupport=i18n('ResourceSupport').' :</br>';
        foreach ($support as $id=>$val){
        	$res = new ResourceAll($val->idSupport);
        	$listSupport .= '&nbsp;&nbsp;&nbsp;#'.$res->id.' '.$res->name.'</br>';
        }
    	echo '<td onmouseover="showBigImage(null,null,this, \''.$listSupport.'\');" onmouseout="hideBigImage();">';
    	echo formatIcon('Support', 22);
    	echo '</td>';
    }
    if ($assignment->supportedResource) {
      $supported=i18n('SupportedResource').' :</br>';
      $supported.="&nbsp;&nbsp;&nbsp;#".$assignment->supportedResource.' '.SqlList::getNameFromId('Resource', $assignment->supportedResource);
      echo '<td onmouseover="showBigImage(null,null,this, \''.$supported.'\');" onmouseout="hideBigImage();">';
      echo formatIcon('Supported', 22);
      echo '</td>';
    }
    // gautier #1702
    if (!$assignment->optional and (get_class($obj)=='Meeting' or get_class($obj)=='PeriodicMeeting')) {
      echo '<td>';
      echo '<a style="float:right; vertical-align:middle;"> '.formatIcon('Favorite', 16, i18n('mandatoryAttendant'),null,true).'</a>';
      echo '</td>';
    }
    // resourceTeam
    if ($resource->isResourceTeam or $assignment->uniqueResource) {
      echo '<td style="position:retalive;width:16px;">';
      echo '<div style="position:relative;vertical-align:middle;width:16px;height:16px;"> '.formatIcon('Team', 16, i18n('ResourceTeam').(($assignment->uniqueResource)?"\n(".i18n('uniqueResource').')':''));
      if ($assignment->uniqueResource) {
        echo '<div style="position:absolute;top:11px;right:-3px;color:#E97B2C;font-weight:bold;">1</div>';
      }
      echo '</div>';
      echo '</td>';
    }
    echo '</tr></table></td>';
    // gautier #resourceTeam
    $propIcon=($outMode!='pdf')?'<div style="float:right;"> '.formatIcon('Proportional', 16, i18n('proportional')).'</div>'
                      :'<span style="margin-left:20px;"> '.formatIcon('Proportional', 16, i18n('proportional')).'</span>';
    if ($resource->isResourceTeam and !$assignment->uniqueResource) {
      echo '<td class="assignData'.$idleClass.'" align="center" style="width:15%;vertical-align:middle;text-align:center;">';
      echo htmlDisplayNumericWithoutTrailingZeros($assignment->capacity).' '.i18n('unitCapacity');
      if ($assignment->proportional) echo ' - '.htmlEncode($assignment->rate).' '.i18n('percent');
      if ($assignment->proportional) echo $propIcon;
      echo '</td>';
    } else {
      echo '<td class="assignData'.$idleClass.'" align="center" style="width:15%;vertical-align:middle;text-align:center;">';
      echo htmlEncode($assignment->rate).' '.i18n('percent');
      if ($assignment->proportional) echo $propIcon;
      echo '</td>';
    }
    if ($workVisible) {
      $keyDownEventScript=NumberFormatter52::getKeyDownEvent();
      // echo '<td class="assignData" align="right" style="vertical-align:middle">'
      // mehdi======================ticket#1776
      if (!$print) {
        
       // remi #7585
        $backgroundRestLeft='';
        if(isset($obj->$peName->validatedEndDate)){
        if ($assignment->plannedEndDate > $obj->$peName->validatedEndDate ) {
          $backgroundRestLeft='background-color: #FFAAAA !important;';
        }}
        
        echo '<input type="hidden" id="'.$dialogEdit.'initAss_'.$assignment->id.'" value="'.Work::displayWork($assignment->assignedWork).'"/>';
        echo '<input style="" type="hidden" id="'.$dialogEdit.'initleft_'.$assignment->id.'" value="'.Work::displayWork($assignment->leftWork).'"/>';
      }
      echo '<td class="assignData'.$idleClass.'" align="right" style="width:15%;vertical-align:middle;">';
      $inputSizing=(isNewGui())?'font-size:12px;padding: 0px;margin:-1px 0px;max-width:95%;':'box-sizing:border-box;margin:2px 0px;padding:1px;max-width:100%;';
      if ($canUpdate and get_class($obj)!='PeriodicMeeting' and !$print and $planningMode!='RECW' and $planningMode !="MAN" and !$assignment->idle and ! $assignment->proportional) {
        echo '<img id="'.$dialogEdit.'idImageAssignedWork'.$assignment->id.'" src="../view/img/savedOk.png" 
                style="display: none; position:relative;top:2px;left:5px; height:16px;float:left;"/>';
        echo '<div dojoType="dijit.form.NumberTextBox" id="'.$dialogEdit.'assAssignedWork_'.$assignment->id.'" name="'.$dialogEdit.'assAssignedWork_'.$assignment->id.'"
    						  class="dijitReset dijitInputInner dijitNumberTextBox assignmentNumber"
      					  value="'.Work::displayWork($assignment->assignedWork).'"
                  style="background:none;max-width:100%;display:block;border:1px solid #A0A0A0 !important;'.$inputSizing.'" >
                   <script type="dojo/method" event="onChange">
                    assUpdateLeftWork('.$assignment->id.', '.$comboDetailAssignment.'); 
                    saveLeftWork('.$assignment->id.',\'AssignedWork\', '.$comboDetailAssignment.'); 
                    //saveLeftWork('.$assignment->id.',\'LeftWork\', '.$comboDetailAssignment.');
                   </script>';
        echo $keyDownEventScript;
        echo '</div>';
      } else {
        echo $fmt->format(Work::displayWork($assignment->assignedWork));
      }
      echo '</td>';
      
      echo '<input type="hidden" id="'.$dialogEdit.'RealWork_'.$assignment->id.'" value="'.Work::displayWork($assignment->realWork).'"/>';
      echo '<td class="assignData'.$idleClass.'" align="right" style="width:15%;vertical-align:middle;">'.$fmt->format(Work::displayWork($assignment->realWork)).'</td>';
      
      if (!$print) echo '<input type="hidden" id="'.$dialogEdit.'initLeft_'.$assignment->id.'" value="'.Work::displayWork($assignment->leftWork).'"/>';
      echo '<td class="assignData'.$idleClass.'" align="right" style="width:15%;vertical-align:middle;">';
      $habil=SqlElement::getSingleSqlElementFromCriteria('habilitationOther', array('idProfile' => $user->getProfile($obj->idProject),'scope' => 'lockedLeftWork'));
      if ($canUpdate and get_class($obj)!='PeriodicMeeting' and !$print and $planningMode!='RECW' and $planningMode !="MAN" and !$assignment->idle and $habil->rightAccess == '1' and ! $assignment->proportional) {
        echo '<img  id="'.$dialogEdit.'idImageLeftWork'.$assignment->id.'" src="img/savedOk.png" style="display: none; position:relative;top:2px;left:5px; height:16px;float:left;"/>';
        echo '<img  id="'.$dialogEdit.'idImageLeftWorkKO'.$assignment->id.'" src="img/nocheck.png" style="display: none; position:relative;top:7px;left:8px; height:8px;float:left;"/>';
        echo '<div dojoType="dijit.form.NumberTextBox" id="'.$dialogEdit.'assLeftWork_'.$assignment->id.'" name="'.$dialogEdit.'assLeftWork_'.$assignment->id.'"
        				class="dijitReset dijitInputInner dijitNumberTextBox"
        				value="'.Work::displayWork($assignment->leftWork).'"
                style="'.$backgroundRestLeft.'display:block;border:1px solid #A0A0A0 !important;'.$inputSizing.'"  >
                <script type="dojo/method" event="onChange">
                    assUpdateLeftWorkDirect('.$assignment->id.', '.$comboDetailAssignment.');
                    saveLeftWork('.$assignment->id.',\'LeftWork\', '.$comboDetailAssignment.');
                </script>';
        echo $keyDownEventScript;
        echo '</div>';
      } else {
        if($canUpdate and get_class($obj)!='PeriodicMeeting' and !$print and $planningMode!='RECW' and $planningMode !="MAN" and !$assignment->idle and ! $assignment->proportional){
          $style='color: #606060 !important;background-color: #F0F0F0 !important; ';
          echo '<img  id="'.$dialogEdit.'idImageLeftWork'.$assignment->id.'" src="img/savedOk.png" style="display: none; position:relative;top:2px;left:5px; height:16px;float:left;"/>';
          echo '<img  id="'.$dialogEdit.'idImageLeftWorkKO'.$assignment->id.'" src="img/nocheck.png" style="display: none; position:relative;top:7px;left:8px; height:8px;float:left;"/>';
          echo '<div dojoType="dijit.form.NumberTextBox" id="'.$dialogEdit.'assLeftWork_'.$assignment->id.'" name="'.$dialogEdit.'assLeftWork_'.$assignment->id.'" readonly
        				class="dijitReset dijitInputInner "
        				value="'.Work::displayWork($assignment->leftWork).'"
                style="display:block;block;border:1px solid #A0A0A0 !important;'.$style.$inputSizing.'" >
                <script type="dojo/method" event="onChange">
                    assUpdateLeftWorkDirect('.$assignment->id.', '.$comboDetailAssignment.');
                    saveLeftWork('.$assignment->id.',\'LeftWork\', '.$comboDetailAssignment.');
                </script>';
          echo '</div>';
        }else{
          echo $fmt->format(Work::displayWork($assignment->leftWork));
        }
      }
      echo '</td>';
    }
    echo '</tr>';
  }
  echo '</table></td></tr>';
}

function drawExpenseDetailFromObject($list, $obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail,$profile;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  // $pe=new PlanningElement();
  // $pe->setVisibility($profile);
  // $workVisible=($pe->_workVisibility=='ALL')?true:false;
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  $scope=pq_str_replace('expense', '', pq_strtolower(get_class($obj)));
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="assignHeader" style="width:5%">';
    // if ($obj->id!=null and ! $print and $canUpdate and !$obj->idle and $workVisible) {
    if ($obj->id!=null and !$print and $canUpdate and !$obj->idle) {
      
      echo '<a onClick="addExpenseDetail('."'".$scope."','".get_class($obj)."','".$obj->id."'".');" title="'.i18n('addExpenseDetail').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:'.(($print)?'13':'8').'%">'.i18n('colDate').'</td>';
  echo '<td class="assignHeader" style="width:10%">'.i18n('colReference').'</td>';
  echo '<td class="assignHeader sortable" style="width:30%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="assignHeader" style="width:12%" >'.i18n('colType').'</td>';
  echo '<td class="assignHeader" style="width:25%">'.i18n('colDetail').'</td>';
  // if ($workVisible) {
  echo '<td class="assignHeader '.(($obj->hasCurrency())?'localLabelClass':'').'" style="width:10%" >'.i18n('colAmount').'</td>';
  // }
  echo '</tr>';
  $fmt=getNumberFormatter52($browserLocale, NumberFormatter52::DECIMAL);
  foreach ($list as $expenseDetail) {
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData" style="text-align:center;white-space:nowrap;width:5%">';
      // if ($canUpdate and ! $print and $workVisible) {
      if ($canUpdate and !$print) {
        echo '  <a onClick="editExpenseDetail('."'".$scope."','".htmlEncode($expenseDetail->id)."','".get_class($obj)."','".$obj->id."'".');" title="'.i18n('editExpenseDetail').'" > '.formatSmallButton('Edit').'</a>';
      }
      // if ($canUpdate and ! $print and $workVisible ) {
      if ($canUpdate and !$print) {
        echo '  <a onClick="removeExpenseDetail('."'".htmlEncode($expenseDetail->id)."'".');" '.'title="'.i18n('removeExpenseDetail').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    echo '<td class="assignData" style="width:'.(($print)?'13':'8').'%">'.htmlFormatDate($expenseDetail->expenseDate).'</td>';
    echo '<td class="assignData" style="width:10%">'.$expenseDetail->externalReference.'</td>';
    echo '<td class="assignData" style="width:30%"';
    echo '>'.$expenseDetail->name;
    if ($expenseDetail->description and !$print) {
      echo formatCommentThumb($expenseDetail->description);
    }
    echo '<input type="hidden" id="expenseDetail_'.htmlEncode($expenseDetail->id).'" value="'.htmlEncode($expenseDetail->name, 'none').'"/>';
    echo '<input type="hidden" id="expenseDetailRef_'.htmlEncode($expenseDetail->id).'" value="'.htmlEncode($expenseDetail->externalReference, 'none').'"/>';
    
    echo '</td>';
    echo '<td class="assignData" style="width:12%">'.SqlList::getNameFromId('ExpenseDetailType', $expenseDetail->idExpenseDetailType).'</td>';
    echo '<td class="assignData" style="width:25%">';
    echo $expenseDetail->getFormatedDetail();
    echo '</td>';
    echo '<td class="assignData" style="text-align:right;width:10%"">'.htmlDisplayLocalCurrency($obj->idProject, $expenseDetail->amount,$expenseDetail->amountLocal).'</td>';
    echo '</tr>';
  }
  echo '</table></td></tr>';
}

function drawResourceCostFromObject($list, $obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail,$profile;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $pe=new PlanningElement();
  $pe->setVisibility($profile);
  $costVisible=($pe->_costVisibility=='ALL')?true:false;
  if (!$costVisible) return;
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  // Sort list
  $sortedList=array();
  foreach ($list as $rcost) {
    $key=SqlList::getNameFromId('Role', $rcost->idRole);
    $key.='#';
    $key.=($rcost->startDate)?$rcost->startDate:'1900-01-01';
    $sortedList[$key]=$rcost;
  }
  ksort($sortedList);
  $list=$sortedList;
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  $funcList=' ';
  foreach ($list as $rcost) {
    $key='#'.htmlEncode($rcost->idRole).'#';
    if (pq_strpos($funcList, $key)===false) {
      $funcList.=$key;
    }
  }
  if (!$print) {
    echo '<td class="assignHeader" style="width:10%">';
    if ($obj->id!=null and !$print and $canUpdate and !$obj->idle) {
      echo '<a onClick="addResourceCost(\''.htmlEncode($obj->id).'\', \''.htmlEncode($obj->idRole).'\',\''.$funcList.'\');" title="'.i18n('addResourceCost').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:'.(($print)?'40':'30').'%">'.i18n('colIdRole').'</td>';
  echo '<td class="assignHeader" style="width:20%">'.i18n('colCost').'</td>';
  echo '<td class="assignHeader" style="width:20%">'.i18n('colStartDate').'</td>';
  echo '<td class="assignHeader" style="width:20%">'.i18n('colEndDate').'</td>';
  
  echo '</tr>';
  $fmt=getNumberFormatter52($browserLocale, NumberFormatter52::DECIMAL);
  foreach ($list as $rcost) {
    $role = new Role($rcost->idRole);
    $idleClass=($role->idle)?' affectationIdleClass':'';
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space:nowrap">';
      if (!$role->idle and !$rcost->endDate and $canUpdate and !$print) {
        echo '  <a onClick="editResourceCost('."'".htmlEncode($rcost->id)."'".",'".htmlEncode($rcost->idResource)."'".",'".htmlEncode($rcost->idRole)."'".",'".($rcost->cost*100)."'".",'".htmlEncode($rcost->startDate)."'".",'".htmlEncode($rcost->endDate)."'".');" '.'title="'.i18n('editResourceCost').'" > '.formatSmallButton('Edit').'</a>';
      }
      if (!$rcost->endDate and $canUpdate and !$print) {
        echo '  <a onClick="removeResourceCost('."'".htmlEncode($rcost->id)."'".",'".htmlEncode($rcost->idRole)."'".",'".SqlList::getNameFromId('Role', $rcost->idRole)."'".",'".htmlFormatDate($rcost->startDate)."'".');" '.'title="'.i18n('removeResourceCost').'" > '.formatSmallButton('Remove').'</a>';
      }
      if ($role->idle) {
        echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
      } else {
        echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
      }
      echo '</td>';
    }
    echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').$idleClass.'" align="left">'.SqlList::getNameFromId('Role', $rcost->idRole).'</td>';
    echo '<td class="assignData'.$idleClass.'" align="right">'.htmlDisplayCurrency($rcost->cost);
    echo " / ".i18n('shortDay');
    echo '</td>';
    echo '<td class="assignData'.$idleClass.'" align="center">'.htmlFormatDate($rcost->startDate).'</td>';
    echo '<td class="assignData'.$idleClass.'" align="center">'.htmlFormatDate($rcost->endDate).'</td>';
    echo '</tr>';
  }
  echo '</table></td></tr>';
}

function drawVersionProjectsFromObject($list, $obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;

  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Project') {
    $idProj=$obj->id;
    $idVers=null;
  } else if (SqlElement::is_a($obj, 'Version')) {
    $idProj=null;
    $idVers=$obj->id;
  }
  if (!$print) {
    echo '<td class="assignHeader" style="width:10%">';
    if ($obj->id!=null and !$print and $canUpdate and !$obj->idle) {
      echo '<a onClick="addVersionProject(\''.$idVers.'\', \''.$idProj.'\');" title="'.i18n('addVersionProject').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  if ($idProj) {
    echo '<td class="assignHeader" style="width:'.(($print)?'60':'50').'%">'.i18n('colIdVersion').'</td>';
  } else {
    echo '<td class="assignHeader" style="width:'.(($print)?'60':'50').'%">'.i18n('colIdProject').'</td>';
  }
  echo '<td class="assignHeader" style="width:15%">'.i18n('colStartDate').'</td>';
  echo '<td class="assignHeader" style="width:15%">'.i18n('colEndDate').'</td>';
  echo '<td class="assignHeader" style="width:10%">'.i18n('colIdle').'</td>';
  
  echo '</tr>';
  if (get_class($obj)=='Project') {
    SqlElement::$_cachedQuery['Version']=array(); // PBE : performance improvments
                                                  // ADD qCazelles - Sorting Project versions list - Ticket 182
    usort($list, "ProductVersionStructure::sortVersionList");
    // END ADD qCazelles - Sorting Project versions list - Ticket 182
  }
  foreach ($list as $vp) {
    $vers=new Version($vp->idVersion);
    if ($vers->scope!='Product') continue;
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData" style="text-align:center;white-space:nowrap">';
      if ($canUpdate and !$print) {
        echo '  <a onClick="editVersionProject('."'".htmlEncode($vp->id)."'".",'".htmlEncode($vp->idVersion)."'".",'".htmlEncode($vp->idProject)."'".');" '.'title="'.i18n('editVersionProject').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canUpdate and !$print) {
        echo '  <a onClick="removeVersionProject('."'".htmlEncode($vp->id)."'".');" '.'title="'.i18n('removeVersionProject').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    $goto="";
    if ($idProj) {
      if (!$print and securityCheckDisplayMenu(null, 'ProductVersion') and securityGetAccessRightYesNo('menuProductVersion', 'read', '')=="YES") {
        $goto=' onClick="gotoElement(\'ProductVersion\',\''.htmlEncode($vp->idVersion).'\');" style="cursor: pointer;" ';
      }
      echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" '.$goto.'>'.htmlEncode(SqlList::getNameFromId('Version', $vp->idVersion)).'</td>';
    } else {
      if (!$print and securityCheckDisplayMenu(null, 'Project') and securityGetAccessRightYesNo('menuProject', 'read', '')=="YES") {
        $goto=' onClick="gotoElement(\'Project\',\''.htmlEncode($vp->idProject).'\');" style="cursor: pointer;" ';
      }
      echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" '.$goto.'>'.htmlEncode(SqlList::getNameFromId('Project', $vp->idProject)).'</td>';
    }
    // CHANGE qCazelles - Ticket #119
    // Old
    // echo '<td class="assignData" align="center">' . htmlFormatDate($vp->startDate) . '</td>';
    // echo '<td class="assignData" align="center">' . htmlFormatDate($vp->endDate) . '</td>';
    // New
    if (Parameter::getGlobalParameter('displayMilestonesStartDelivery')!='YES') {
      echo '<td class="assignData" align="center">'.htmlFormatDate($vp->startDate).'</td>';
      echo '<td class="assignData" align="center">'.htmlFormatDate($vp->endDate).'</td>';
    } else {
      $hasStartDate=false;
      if ($vers->isStarted) {
        $startDate=$vers->realStartDate;
        $hasStartDate=true;
      } else if ($vers->plannedStartDate) {
        $startDate=$vers->plannedStartDate;
      } else {
        $startDate='';
      }
      $hasEndDate=false;
      if ($vers->isDelivered) {
        $endDate=$vers->realDeliveryDate;
        $hasEndDate=true;
      } else if ($vers->plannedDeliveryDate) {
        $endDate=$vers->plannedDeliveryDate;
      } else {
        $endDate='';
      }
      echo '<td class="assignData" align="center">';
      if (!$hasStartDate and $startDate!='') echo '<span style="color: red;">[';
      echo htmlFormatDate($startDate);
      if (!$hasStartDate and $startDate!='') echo ']</span>';
      echo '</td>';
      echo '<td class="assignData" align="center">';
      if (!$hasEndDate and $endDate!='') echo '<span style="color: red;">[';
      echo htmlFormatDate($endDate);
      if (!$hasEndDate and $endDate!='') echo ']</span>';
      echo '</td>';
    }
    // END CHANGE qCazelles - Ticket #119
    echo '<td class="assignData" align="center"><img src="../view/img/checked'.(($vp->idle)?'OK':'KO').'.png" /></td>';
    
    echo '</tr>';
  }
  echo '</table></td></tr>';
}

function drawAbacusFromObject($list, $obj, $abacusDef, $refresh=false) {
  global $print, $comboDetail;
  
  if (! Module::isModuleActive('moduleAbacus')) return;
  if ($comboDetail) return;
  $canUpdate = securityGetAccessRightYesNo('menu'.get_class($obj),'update',$obj)=="YES";
  if ($obj->idle==1) $canUpdate=false;
  $sectionId = 'abacusSection_' . $abacusDef->id . '_' . $obj->id;
  $sessionKey = 'abacus_' . $sectionId;
  
  $sessionState = getSessionValue($sessionKey);
  $isClosed = ($sessionState == 'closed');
  $isIdle = $abacusDef->idle ? " (".i18n('idle').")" : '';
  $iconClass = $isClosed ? 'iconRight16 iconRight imageColorNewGui iconSize16' : 'iconDown16 iconDown imageColorNewGui iconSize16';
  $iconProportional = '' ;
  $titlePorportional = '';
  if ($abacusDef->assignmentWorkType == 'proportional' ){
    $iconProportional = 'imageColorNewGui iconProportional16 iconProportional iconSize16';
    $titlePorportional = i18n('proportional');
  }
  
  $html='';
  $html.= '<table style="width:100%;"><tr><td colspan="2" style="width:100%;">';
  $html.= '  <div style="padding:5px 5px 5px 10px;margin:0px 0 10px 0;background-color: var(--color-light-secondary);color: var(--color-detail-header-text);display:flex;gap:8px;align-items:center;cursor:pointer;"
                  onclick="toggleAbacusSection(\''.$sectionId.'\')">';
  $html.= '    <span id="icon_'.$sectionId.'" class="'.$iconClass.'" style="cursor:pointer;"></span>';
  $html.= '    <span>'. i18n('sectionAbacus') .': '.htmlEncode($abacusDef->name). $isIdle . ' </span>';
  $html.= '    <span class="' . $iconProportional .'" title="' . $titlePorportional . '" style="position:absolute;right:20px;" ></span>';
  $html.= '  </div>';
  $display = $isClosed ? 'none' : 'block';
  $html.= '<div id="'.$sectionId.'" style="display:'.$display.';padding-bottom:20px;">';
  $html.= '<table style="width:100%;">';
  
  $html.= '<tr>';
  if (!$print) {
    $html.= '<td class="assignHeader" style="width:5%;">';
    if ($obj->id and $canUpdate and !$obj->idle && !$abacusDef->idle) {
      $html .= '<a onClick="addAbacusProject(\''.$obj->id.'\', \''.$abacusDef->id.'\', \''.$abacusDef->name.'\');"title="'.i18n('addAbacusProject').'">'.formatSmallButton('Add').'</a>';
    }
    $html.= '</td>';
  }
  
  if ($abacusDef->className1) $html.= '<td class="assignHeader" style="width:15%;">'.i18n(htmlEncode($abacusDef->className1)).'</td>';
  if ($abacusDef->className2) $html.= '<td class="assignHeader" style="width:15%;">'.i18n(htmlEncode($abacusDef->className2)).'</td>';
  if ($abacusDef->className3) $html.= '<td class="assignHeader" style="width:15%;">'.i18n(htmlEncode($abacusDef->className3)).'</td>';
  if ($abacusDef->className4) $html.= '<td class="assignHeader" style="width:15%;">'.i18n(htmlEncode($abacusDef->className4)).'</td>';
  if ($abacusDef->className5) $html.= '<td class="assignHeader" style="width:15%;">'.i18n(htmlEncode($abacusDef->className5)).'</td>';
  $html.= '<td class="assignHeader" style="width:10%;">'.ucfirst(i18n('quantity')).'</td>';
  
  $html.= '<td class="assignHeader" style="width:10%;position:relative;" >' .ucfirst($abacusDef->assignmentWorkType == 'proportional' ? i18n('workPlanGanttAverage'): i18n('colCountTotal')) ;
  $html.= '<span id="infoIconTotal" class="iconInfo12 iconInfo iconSize12 imageColorNewGui" style="cursor:help;top:3px;position:absolute;right:3px;" title = "'.htmlEncode(i18n('tooltipTotalAbacus')).'"></span>';
  $html.= '</td>';
  
  $html.= '<td class="assignHeader" style="width:10%;">'.ucfirst(i18n('colComment')).'</td>';
  $html.= '<td class="assignHeader" style="width:5%;">'.i18n('colId').'</td>';
  
  $html.= '</tr>';
  foreach ($list as $abacusProj) {
    $idleClass=$abacusProj->idle?' affectationIdleClass':'';
    $html.= '<tr>';
    
    if (!$print) {
      $html.= '<td class="assignData '.$idleClass.'" style="text-align:center;">';
      if ($canUpdate) {
        $html .= '<a onClick="editAbacusProject(\''.htmlEncode($abacusProj->id).'\',\''.htmlEncode($abacusDef->name).'\');" title="'.i18n('editAbacusProject').'">'.formatSmallButton('Edit').'</a>';
        $html .= '<a onClick="deleteAbacusProject(\''.htmlEncode($abacusProj->id).'\');" title="'.i18n('deleteAbacusProject').'">'.formatSmallButton('Remove').'</a>';
      }
      $html.= '</td>';
    }
    
    if ($abacusDef->className1) $html.= '<td class="assignData '.$idleClass.'">'.getAbacusDisplayName($abacusDef->className1,$abacusProj->idClassName1,$abacusProj->idClassNameRef, $abacusDef->idAbacusable1).'</td>';
    if ($abacusDef->className2) $html.= '<td class="assignData '.$idleClass.'">'.getAbacusDisplayName($abacusDef->className2,$abacusProj->idClassName2,$abacusProj->idClassNameRef, $abacusDef->idAbacusable2).'</td>';
    if ($abacusDef->className3) $html.= '<td class="assignData '.$idleClass.'">'.getAbacusDisplayName($abacusDef->className3,$abacusProj->idClassName3,$abacusProj->idClassNameRef, $abacusDef->idAbacusable3).'</td>';
    if ($abacusDef->className4) $html.= '<td class="assignData '.$idleClass.'">'.getAbacusDisplayName($abacusDef->className4,$abacusProj->idClassName4,$abacusProj->idClassNameRef, $abacusDef->idAbacusable4).'</td>';
    if ($abacusDef->className5) $html.= '<td class="assignData '.$idleClass.'">'.getAbacusDisplayName($abacusDef->className5,$abacusProj->idClassName5,$abacusProj->idClassNameRef, $abacusDef->idAbacusable5).'</td>';
    $html.= '<td class="assignData '.$idleClass.'" align="center">'.htmlDisplayNumericWithoutTrailingZeros($abacusProj->quantity).'</td>';
    
    $apa = new AbacusProjectAssignment();
    $apaLines = $apa->getSqlElementsFromCriteria(array('idAbacusProject' => $abacusProj->id));
    
    $total = 0;
    $count = 0;
    $detailByPhase = array();
    $countByPhase = array();
    $activityCache = array();
    foreach ($apaLines as $apaLine) {
      $total += floatval($apaLine->value);
      $count++;
      if (!isset($activityCache[$apaLine->refId])) {
        $activityCache[$apaLine->refId] = new Activity($apaLine->refId);
      }
      $activity = $activityCache[$apaLine->refId];
      $phaseName = $activity->idPhase? SqlList::getNameFromId('Phase', $activity->idPhase): i18n('noPhase');
      if (!isset($detailByPhase[$phaseName])) {
        $detailByPhase[$phaseName] = 0;
        $countByPhase[$phaseName] = 0;
      }
      $detailByPhase[$phaseName] += floatval($apaLine->value);
      $countByPhase[$phaseName]++;
    }
    
    $tooltip = '';
    foreach ($detailByPhase as $phaseName => $val) {
      if ($abacusDef->assignmentWorkType == 'proportional') {
        $avg = $countByPhase[$phaseName] ? $val / $countByPhase[$phaseName] : 0;
        $displayVal = htmlDisplayNumericWithoutTrailingZeros(round($avg * 100, 2)) . '% (' . $countByPhase[$phaseName] . ')';
      } else {
        $displayVal = htmlDisplayNumericWithoutTrailingZeros($val) . ' ' . i18n('d');
      }
      $tooltip .= $phaseName . ' : ' . $displayVal . "\n";
    }
    
    $displayTotal = $abacusDef->assignmentWorkType == 'proportional' ? htmlDisplayNumericWithoutTrailingZeros(round(($count ? $total / $count : 0) * 100, 2)) . '%' : htmlDisplayNumericWithoutTrailingZeros($total) . ' ' . i18n('d');
    $html .= '<td class="assignData" style="text-align:center;" title="' . htmlEncode($tooltip) . '">' . $displayTotal .  '</td>';
    
    $html.= '<td class="assignData '.$idleClass.'">';
    $abacusLine = new AbacusLine();
    $where = $abacusDef->getAbacusLineWhere($abacusProj->idClassName1, $abacusProj->idClassName2, $abacusProj->idClassName3,$abacusProj->idClassName4, $abacusProj->idClassName5);
    $matchingLine = $abacusLine->getSqlElementsFromCriteria(null, false, $where);
    $matchingLine = count($matchingLine) > 0 ? $matchingLine[0] : null;
    if ($abacusProj->comment) {
      $html.= '<div style="float:right;margin: 0px 2px;">'.formatCommentThumb($abacusProj->comment).'</div>';
    }
    if ($matchingLine) {
      if ($matchingLine->assumption) {
        $html.= '<div style="float:right;margin: 0px 2px;">'.formatCommentThumb($matchingLine->assumption,false,false,'Assumption').'</div>';
      }
      if ($matchingLine->example) {
        $html.= '<div style="float:right;margin: 0px 2px;">'.formatCommentThumb($matchingLine->example,false,false,'Example').'</div>';
      }
    }
    if ($abacusProj->assignmentReference) {
      $user = new Resource(getCurrentUserId());
      $userProfile = new Profile($user->idProfile);
      $isAdmin = true;
      if($userProfile->profileCode == 'ADM'){
        $isAdmin = true;
      }
      if ($isAdmin) $html.= '<div style="float:right;margin: 0px 2px;">'.formatCommentThumb($abacusProj->assignmentReference,false,false,'Team').'</div>';
    }
    
    $html.= '<td class="assignData '.$idleClass.'" style="text-align:center;">'.htmlEncode($abacusProj->id).'</td>';
    
    $html.='</td>';
    
    $html.= '</tr>';
  }
  
  $html.= '</table>';
  $html.= '</td></tr></table>';
  $html.= '</div>';
  
  return $html;
}

function drawProductProjectsFromObject($list, $obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Project') {
    $idProj=$obj->id;
    $idProd=null;
  } else if (get_class($obj)=='Product') {
    $idProj=null;
    $idProd=$obj->id;
  }
  if (!$print) {
    echo '<td class="assignHeader" style="width:10%">';
    if ($obj->id!=null and !$print and $canUpdate and !$obj->idle) {
      echo '<a onClick="addProductProject(\''.$idProd.'\', \''.$idProj.'\');" title="'.i18n('addProductProject').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  if ($idProj) {
    echo '<td class="assignHeader" style="width:'.(($print)?'60':'50').'%">'.i18n('colIdProduct').'</td>';
  } else {
    echo '<td class="assignHeader" style="width:'.(($print)?'60':'50').'%">'.i18n('colIdProject').'</td>';
  }
  echo '<td class="assignHeader" style="width:15%">'.i18n('colStartDate').'</td>';
  echo '<td class="assignHeader" style="width:15%">'.i18n('colEndDate').'</td>';
  echo '<td class="assignHeader" style="width:10%">'.i18n('colIdle').'</td>';
  
  echo '</tr>';
  foreach ($list as $pp) {
    // $prod=new Product($pp->idProduct);
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData" style="text-align:center;white-space:nowrap">';
      if ($canUpdate and !$print) {
        echo '  <a onClick="editProductProject('."'".htmlEncode($pp->id)."'".",'".htmlEncode($pp->idProduct)."'".",'".htmlEncode($pp->idProject)."'".');" '.'title="'.i18n('editProductProject').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canUpdate and !$print) {
        echo '  <a onClick="removeProductProject('."'".htmlEncode($pp->id)."'".');" '.'title="'.i18n('removeProductProject').'"> '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    $goto="";
    if ($idProj) {
      $p=new Product($pp->idProduct, true);
      if (!$print and securityCheckDisplayMenu(null, 'Product') and securityGetAccessRightYesNo('menuProduct', 'read', $p)=="YES") {
        $goto=' onClick="gotoElement(\'Product\',\''.htmlEncode($pp->idProduct).'\');" style="cursor: pointer;" ';
      }
      echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left"'.$goto.'>'.htmlEncode(SqlList::getNameFromId('Product', $pp->idProduct)).'</td>';
    } else {
      $p=new Project($pp->idProject, true);
      if (!$print and securityCheckDisplayMenu(null, 'Project') and securityGetAccessRightYesNo('menuProject', 'read', $p)=="YES") {
        $goto=' onClick="gotoElement(\'Project\',\''.htmlEncode($pp->idProject).'\');" style="cursor: pointer;" ';
      }
      echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left"'.$goto.'>'.htmlEncode(SqlList::getNameFromId('Project', $pp->idProject)).'</td>';
    }
    echo '<td class="assignData" align="center">'.htmlFormatDate($pp->startDate).'</td>';
    echo '<td class="assignData" align="center">'.htmlFormatDate($pp->endDate).'</td>';
    echo '<td class="assignData" align="center"><img src="../view/img/checked'.(($pp->idle)?'OK':'KO').'.png" /></td>';
    
    echo '</tr>';
  }
  echo '</table></td></tr>';
}

#asset Tab
function drawAssetFromModel($list, $obj) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Model';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  if ($comboDetail) {
    return;
  }
  $typeAsset='Asset';
  $typeAssetType = 'AssetType';
  echo '<table style="width:100%">';
  echo '<tr>';
  echo '<td class="assignHeader" style="width:50%">'.i18n('dashboardTicketMainTitleType').'</td>';
  echo '<td class="assignHeader" style="width:50%">'.i18n('colAsset').'</td>';
  //order by alphabetic
  asort($list);
  $tabType = array();
  $listType = array();
  $listIdle = array();
  foreach ($list as $model) {
    $tabType[$model->idAssetType][$model->id]=$model->name;
    $listType[$model->idAssetType]=$model->idAssetType;
    if($model->idle)$listIdle[]=$model->id;
  }
  foreach ($listType as $myType){
    asort($tabType[$myType]);
  }
  
  foreach ($tabType as $id=>$val){
    foreach ($val as  $idVal=>$value){
      $idleClass=(in_array($idVal, $listIdle))?' affectationIdleClass':'';
      echo '<tr>';
      $goto="";
      if (!$print and securityCheckDisplayMenu(null, $typeAsset) and securityGetAccessRightYesNo('menu'.$typeAsset, 'read', '')=="YES") {
        $goto=' onClick="gotoElement(\''.$typeAsset.'\',\''.htmlEncode($idVal).'\');" style="cursor: pointer;" ';
      }
      $nameType=SqlList::getNameFromId('Type', $id);
      $gotoType="";
      if (!$print and securityCheckDisplayMenu(null, $typeAssetType) and securityGetAccessRightYesNo('menu'.$typeAssetType, 'read', '')=="YES") {
        $gotoType=' onClick="gotoElement(\''.$typeAssetType.'\',\''.htmlEncode($id).'\');" style="cursor: pointer;" ';
      }
      echo '  <td '.$gotoType.' class="assignData'.$idleClass.' '.((isNewGui() and isset($gotoType) and $gotoType!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">'.htmlEncode($nameType).'</td>';
      echo '  <td '.$goto.' class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">#'.$idVal.'  '.htmlEncode($value).'</td>';
      echo '</tr>';
    }
  }
  echo '</table>';
}

function drawForcedLayout($obj,$list) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Model';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  if ($comboDetail) {
    return;
  }
  echo '<table style="width:100%">';
  echo '  <tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '  <tr>';
  echo '    <td class="assignHeader" style="width:20%">'.i18n('name').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('menu').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('creator').'</td>';
  echo "  </tr>";
  foreach ($list as $val) {
    echo "  <tr>";
    echo '    <td  class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode(SqlList::getFieldFromId('Layout', $val->idLayout,'scope')).'</td>';
    echo '    <td  class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode(i18n($val->objectClass)).'</td>';
    echo '    <td  class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode(SqlList::getNameFromId('Affectable', $val->idCreator)).'</td>';
    echo "  </tr>";
  }
  echo '  </table></td></tr>';
  echo '</table>';
}

function drawAttributionVote($obj,$list) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Model';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  if ($comboDetail) {
    return;
  }
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  
  echo '<table style="width:100%">';
  echo '  <tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '  <tr>';
  
  if (!$print) {
    echo '<td class="assignHeader" style="width:15%">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      echo '<a onClick="addAttributionVote(\''.get_class($obj).'\',\''.$obj->id.'\');" title="'.i18n('addAttributionVote').'" /> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '    <td class="assignHeader" style="width:20%">'.i18n('VotingAttributionRule').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('colCountTotal').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('used').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('colLeft').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('lastAttributionDate').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('nextAttributionDate').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('endDate').'</td>';
  echo '    <td class="assignHeader" style="width:10%">'.i18n('nextAttributionValue').'</td>';
  echo "  </tr>";
  foreach ($list as $val) {
    $ruleVoting = new VotingAttributionRule($val->idVotingAttributionRule);
    $date = $val->lastAttributionDate;
    if($ruleVoting->dailyValue){
      $nextValue=$ruleVoting->dailyValue;
      $nextDate = date("Y-m-d", pq_strtotime($date." + 1 day"));
    }elseif($ruleVoting->weeklyValue){
      $nextValue=$ruleVoting->weeklyValue;
      $nextDate = date("Y-m-d", pq_strtotime($date." + 7 day"));
    }elseif($ruleVoting->monthlyValue){
      $nextValue= $ruleVoting->monthlyValue;
      $nextDate = date("Y-m-d", pq_strtotime($date." + 1 month"));
    }elseif($ruleVoting->yearlyValue){
      $nextValue = $ruleVoting->yearlyValue;
      $nextDate = date("Y-m-d", pq_strtotime($date." + 1 year"));
    }else{
      $nextValue=0;
      $nextDate = null;
    }
    //if(!$val->lastAttributionDate)$val->lastAttributionDate='';
    echo '  <tr>';

    if (!$print) {
      echo '<td class="assignData" style="text-align:center;white-space: nowrap;vertical-align: middle;">';
      if ($canUpdate) {
        echo '  <a onClick="editAttributionVote(\''.$val->id.'\');" '.'title="'.i18n('editAttributionVote').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canDelete) {
        echo '<a onClick="removeAttributionVote(\''.$val->id.'\');" '.'title="'.i18n('removeAttributionVote').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }

    echo '    <td  class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode(SqlList::getNameFromId('VotingAttributionRule', $val->idVotingAttributionRule)).'</td>';
    echo '    <td  class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode($val->totalValue).'</td>';
    echo '    <td  class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode($val->usedValue).'</td>';
    echo '    <td  class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode($val->totalValue - $val->usedValue).'</td>';
    echo '    <td class="assignData" align="center" style="white-space: nowrap;vertical-align: middle;">'.htmlFormatDate($val->lastAttributionDate).'</td>';
    $colorDate='';
    if ($val->endAttributionDate and $nextDate>$val->endAttributionDate) $colorDate='color:#CC0000;';
    else if ($nextDate<date('Y-m-d')) $colorDate='color:#00AA00;';
    echo '    <td class="assignData" align="center" style="'.$colorDate.'white-space: nowrap;vertical-align: middle;">'.htmlFormatDate($nextDate).'</td>';
    echo '    <td class="assignData" align="center" style="white-space: nowrap;">'.htmlFormatDate($val->endAttributionDate).'</td>';
    echo '    <td class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode($nextValue).'</td>';
    echo "  </tr>";
  }
  echo '  </table></td></tr>';
  echo '</table>';
}

function drawAssetFromUser($list, $obj) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Model';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  if ($comboDetail) {
    return;
  }
  $typeAsset='Asset';
  $typeAssetType = 'AssetType';
  $typeModel = 'Model';
  $typeBrand = 'Brand';
  echo '<table style="width:100%">';
  echo '<tr>';
  echo '<td class="assignHeader" style="width:25%">'.i18n('dashboardTicketMainTitleType').'</td>';
  echo '<td class="assignHeader" style="width:25%">'.i18n('colAsset').'</td>';
  echo '<td class="assignHeader" style="width:25%">'.i18n('colBrand').'</td>';
  echo '<td class="assignHeader" style="width:25%">'.i18n('colModel').'</td>';
  echo "</tr>";
  //order by alphabetic
  asort($list);
  $tabType = array();
  $listType = array();
  $listIdle = array();
  foreach ($list as $model) {
    $tabType[$model->idAssetType][$model->id]=$model->name;
    $listType[$model->idAssetType]=$model->idAssetType;
    if($model->idle)$listIdle[]=$model->id;
  }
  foreach ($listType as $myType){
    asort($tabType[$myType]);
  }

  foreach ($tabType as $id=>$val){
    foreach ($val as  $idVal=>$value){
      $currentAsset = new Asset($idVal);
      $idleClass=(in_array($idVal, $listIdle))?' affectationIdleClass':'';
      echo '<tr>';
      $goto="";
      if (!$print and securityCheckDisplayMenu(null, $typeAsset) and securityGetAccessRightYesNo('menu'.$typeAsset, 'read', '')=="YES") {
        $goto=' onClick="gotoElement(\''.$typeAsset.'\',\''.htmlEncode($idVal).'\');" style="cursor: pointer;" ';
      }
      $nameType=SqlList::getNameFromId('Type', $id);
      $gotoType="";
      if (!$print and securityCheckDisplayMenu(null, $typeAssetType) and securityGetAccessRightYesNo('menu'.$typeAssetType, 'read', '')=="YES") {
        $gotoType=' onClick="gotoElement(\''.$typeAssetType.'\',\''.htmlEncode($id).'\');" style="cursor: pointer;" ';
      }
      $gotoBrand="";
      if (!$print and securityCheckDisplayMenu(null, $typeBrand) and securityGetAccessRightYesNo('menu'.$typeBrand, 'read', '')=="YES") {
        $gotoBrand=' onClick="gotoElement(\''.$typeBrand.'\',\''.htmlEncode($currentAsset->idBrand).'\');" style="cursor: pointer;" ';
      }
      $gotoModel="";
      if (!$print and securityCheckDisplayMenu(null, $typeModel) and securityGetAccessRightYesNo('menu'.$typeModel, 'read', '')=="YES") {
        $gotoModel=' onClick="gotoElement(\''.$typeModel.'\',\''.htmlEncode($currentAsset->idModel).'\');" style="cursor: pointer;" ';
      }
      echo '  <td '.$gotoType.' class="assignData'.$idleClass.' '.((isNewGui() and isset($gotoType) and $gotoType!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">'.htmlEncode($nameType).'</td>';
      echo '  <td '.$goto.' class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">#'.$idVal.'  '.htmlEncode($value).'</td>';
      echo '  <td '.$gotoBrand.' class="assignData'.$idleClass.' '.((isNewGui() and isset($gotoBrand) and $gotoBrand!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">'.htmlEncode(SqlList::getNameFromId('Brand', $currentAsset->idBrand)).'</td>';
      echo '  <td '.$gotoModel.' class="assignData'.$idleClass.' '.((isNewGui() and isset($gotoModel) and $gotoModel!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">'.htmlEncode(SqlList::getNameFromId('Model', $currentAsset->idModel)).'</td>';
      echo '</tr>';
    }
  }
  echo '</table>';
}

function drawSkillFromUser($list, $obj){
  global $cr, $print, $user, $browserLocale, $comboDetail;
  
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
  	$canCreate=false;
  	$canUpdate=false;
  	$canDelete=false;
  }
  if ($obj->idle==1) {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  if (get_class($obj)=='GlobalView') {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Resource') {
  	$idRess=$obj->id;
  } else {
  	$idRess=null;
  }
  if (!$print) {
  	echo '<td class="assignHeader" style="width:20%">';
  	if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
  		echo '<a onClick="addResourceSkill(\''.$idRess.'\');" title="'.i18n('addResourceSkill').'" /> '.formatSmallButton('Add').'</a>';
  	}
  	echo '</td>';
  }
  echo '<td class="assignHeader" style="width:25%;">'.i18n('colIdSkill').'</td>';
  echo '<td class="assignHeader" style="width:25%;">'.i18n('colIdSkillLevel').'</td>';
  echo '<td class="assignHeader" style="width:15%">'.i18n('useSince').'</td>';
  echo '<td class="assignHeader" style="width:15%">'.i18n('useUntil').'</td>';
  echo '</tr>';
  
  foreach ($list as $resSkill) {
  	echo '<tr>';
  	$idleClass=($resSkill->idle)?' affectationIdleClass':'';
  	if (!$print) {
  		echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space: nowrap;vertical-align: middle;">';
  		if ($canUpdate) {
  			echo '  <a onClick="editResourceSkill(\''.$resSkill->id.'\',\''.$obj->id.'\');" '.'title="'.i18n('editResourceSkill').'" > '.formatSmallButton('Edit').'</a>';
  		}
  		if ($canDelete) {
  			echo '<a onClick="removeResourceSkill(\''.$resSkill->id.'\');" '.'title="'.i18n('removeResourceSkill').'" > '.formatSmallButton('Remove').'</a>';
  		}
  		if ($resSkill->comment) {
  			echo '<div style="float:right">'.formatCommentThumb($resSkill->comment).'</div>';
  		}
  		if ($resSkill->idle) {
  			echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
  		} else {
  			echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
  		}
  	}
  	echo '</td>';
  	$goto=' onClick="gotoElement(\'Skill\',\''.htmlEncode($resSkill->idSkill).'\');" ';
  	echo ' <td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" style="white-space: nowrap;vertical-align: middle;"  '.$goto.'>'.htmlEncode(SqlList::getNameFromId('Skill', $resSkill->idSkill)).'</td>';
  	$goto=' onClick="gotoElement(\'SkillLevel\',\''.htmlEncode($resSkill->idSkillLevel).'\');" ';
  	$skillLevel = new SkillLevel($resSkill->idSkillLevel, true);
  	echo ' <td align="center" class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="white-space: nowrap; cursor:pointer;vertical-align: middle;" '.$goto.'>';
  	echo '<div style="height: 10px;position: relative;font-style: italic;">'.htmlEncode(SqlList::getNameFromId('SkillLevel', $resSkill->idSkillLevel)).'</div><div style="position: relative;height: 20px;"><img src="icons/'.$skillLevel->icon.'" alt="'.$skillLevel->name.'" style="height: 24px;"></div>';
  	echo '</td>';
  	echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;vertical-align: middle;">'.htmlFormatDate($resSkill->useSince).'</td>';
  	echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;vertical-align: middle;">'.htmlFormatDate($resSkill->useUntil).'</td>';
  	echo '</tr>';
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawActivitySkillList($list, $obj){
  global $cr, $print, $user, $browserLocale, $comboDetail;
  
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
  	$canCreate=false;
  	$canUpdate=false;
  	$canDelete=false;
  }
  if ($obj->idle==1) {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  if (get_class($obj)=='GlobalView') {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Activity') {
  	$idActivity=$obj->id;
  } else {
  	$idActivity=null;
  }
  if (!$print) {
  	echo '<td class="assignHeader" style="width:20%">';
  	if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
  		echo '<a onClick="addActivitySkill(\''.$idActivity.'\');" title="'.i18n('addActivitySkill').'" /> '.formatSmallButton('Add').'</a>';
  	}
  	echo '</td>';
  }
  echo '<td class="assignHeader" style="width:50%;">'.i18n('colIdSkill').'</td>';
  echo '<td class="assignHeader" style="width:50%;">'.i18n('colIdSkillLevel').'</td>';
  echo '</tr>';
  
  foreach ($list as $activitySkill) {
  	echo '<tr>';
  	if (!$print) {
  		echo '<td class="assignData" style="text-align:center;white-space: nowrap;vertical-align: middle;">';
  		if ($canUpdate) {
  			echo '  <a onClick="editActivitySkill(\''.$activitySkill->id.'\',\''.$obj->id.'\');" '.'title="'.i18n('editActivitySkill').'" > '.formatSmallButton('Edit').'</a>';
  		}
  		if ($canDelete) {
  			echo '<a onClick="removeActivitySkill(\''.$activitySkill->id.'\');" '.'title="'.i18n('removeActivitySkill').'" > '.formatSmallButton('Remove').'</a>';
  		}
  		echo '</td>';
  	}
  	$goto=' onClick="gotoElement(\'Skill\',\''.htmlEncode($activitySkill->idSkill).'\');" ';
  	echo ' <td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" style="white-space: nowrap;vertical-align: middle; width:50%;"  '.$goto.'>'.htmlEncode(SqlList::getNameFromId('Skill', $activitySkill->idSkill)).'</td>';
  	$goto=' onClick="gotoElement(\'SkillLevel\',\''.htmlEncode($activitySkill->idSkillLevel).'\');" ';
  	$skillLevel = new SkillLevel($activitySkill->idSkillLevel, true);
  	echo ' <td align="center" class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="white-space: nowrap; cursor:pointer;vertical-align: middle; width:50%;" '.$goto.'>';
  	echo '<div style="height: 10px;position: relative;font-style: italic;">'.htmlEncode(SqlList::getNameFromId('SkillLevel', $activitySkill->idSkillLevel)).'</div><div style="position: relative;height: 20px;"><img src="icons/'.$skillLevel->icon.'" alt="'.$skillLevel->name.'" style="height: 24px;"></div>';
  	echo '</td>';
  	echo '</tr>';
  }
  echo '</table>';
}

function drawInputMailboxHistory($list, $obj) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='InputMailboxTicket';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  if ($comboDetail) {
    return;
  }
  echo '<table style="width:99.5%">';
  echo '<tr>';
  echo '<td class="assignHeader" style="width:40%">'.i18n('colEmail').'</td>';
  echo '<td class="assignHeader" style="width:20%">'.i18n('colDate').'</td>';
  echo '<td class="assignHeader" style="width:40%">'.i18n('colResult').'</td>';
  echo '</tr>';
  foreach ($list as $id=>$val){
    $idTicket = pq_explode('#', $val->result);
    $firstPart=pq_trim($idTicket[0]??"");
    $split=pq_explode(' ', $firstPart);
    $class=$split[count($split)-1];
    if (! SqlElement::class_exists($class)) $class='Ticket';
    $val->result=pq_str_replace($class, i18n($class), $val->result);
    $goto="";
    if (count($idTicket)>1 and $val->refType=="ticket" and !$print and securityCheckDisplayMenu(null, 'Ticket') and securityGetAccessRightYesNo('menuTicket', 'read', '')=="YES") {
      $goto=' onClick="gotoElement(\''.$class.'\',\''.htmlEncode($idTicket[1]).'\');" style="cursor: pointer;" ';
    }
      echo '<tr>';
      echo '  <td  class="assignData" align="left" style="white-space: nowrap;">'.htmlEncode($val->adress).'</td>';
      echo '  <td  class="assignData" align="left" style="white-space: nowrap;">'.htmlEncode($val->date).'</td>';
      echo '  <td  '.$goto.' class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="">'.htmlEncode($val->result).'</td>';
      echo '</tr>';
  }
  echo '</table>';
}

function drawModelFromBrand($list, $obj) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Brand';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  if ($comboDetail) {
    return;
  }
  $typeModel='Model';
  $typeAsset = 'AssetType';
  echo '<table style="width:100%">';
  echo '<tr>';
  echo '<td class="assignHeader" style="width:50%">'.i18n('dashboardTicketMainTitleType').'</td>';
  echo '<td class="assignHeader" style="width:50%">'.i18n('colModel').'</td>';
  echo '</tr>';
  
  //order by alphabetic
  asort($list);
  $tabType = array();
  $listType = array();
  $listIdle = array();
  foreach ($list as $model) {
   $tabType[$model->idAssetType][$model->id]=$model->name;
   $listType[$model->idAssetType]=$model->idAssetType;
   if($model->idle)$listIdle[]=$model->id;
  }
  foreach ($listType as $myType){
    asort($tabType[$myType]);
  }
  
  foreach ($tabType as $id=>$val){
    foreach ($val as  $idVal=>$value){
      $idleClass=(in_array($idVal, $listIdle))?' affectationIdleClass':'';
      echo '<tr>';
      $goto="";
      if (!$print and securityCheckDisplayMenu(null, $typeModel) and securityGetAccessRightYesNo('menu'.$typeModel, 'read', '')=="YES") {
        $goto=' onClick="gotoElement(\''.$typeModel.'\',\''.htmlEncode($idVal).'\');" style="cursor: pointer;" ';
      }
      $nameType=SqlList::getNameFromId('Type', $id);
      $gotoType="";
      if (!$print and securityCheckDisplayMenu(null, $typeAsset) and securityGetAccessRightYesNo('menu'.$typeAsset, 'read', '')=="YES") {
        $gotoType=' onClick="gotoElement(\''.$typeAsset.'\',\''.htmlEncode($id).'\');" style="cursor: pointer;" ';
      }
      echo '  <td '.$gotoType.' class="assignData'.$idleClass.' '.((isNewGui() and isset($gotoType) and $gotoType!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">'.htmlEncode($nameType).'</td>';
      echo '  <td '.$goto.' class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;">'.htmlEncode($value).'</td>';
      echo '</tr>';
    }
  }
  echo '</table>';
}

// gautier #resourceTeam
function drawAffectationsResourceTeamFromObject($list, $obj, $type, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Affectation';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  $list=array();
  foreach ($listTemp as $aff) {
    $name=SqlList::getNameFromId('Resource', $aff->idResource);
    $aff->name=$name;
    $list[$name.'#'.$aff->id]=$aff;
  }
  ksort($list);
  if ($comboDetail) {
    return;
  }
  $canCreate=securityGetAccessRightYesNo('menuAffectation', 'create')=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  if (get_class($obj)=='GlobalView') {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Resource' or get_class($obj)=='ResourceTeam') {
    $idRess=$obj->id;
  } else {
    $idRess=null;
  }
  if (!$print) {
    echo '<td class="assignHeader" style="width:15%">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      echo '<a onClick="addAffectationResourceTeam(\''.get_class($obj).'\',\''.$type.'\',\''.$idRess.'\');" title="'.i18n('addAffectationResourceTeam').'" /> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:8%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader sortable" style="width:39%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="assignHeader" style="width:13%">'.i18n('colStartDate').'</td>';
  echo '<td class="assignHeader" style="width:13%">'.i18n('colEndDate').'</td>';
  echo '<td class="assignHeader" style="width:12%">'.i18n('colRate').'</td>';
  
  echo '</tr>';
  foreach ($list as $aff) {
    $canUpdate=securityGetAccessRightYesNo('menuResourceTeam', 'update', $aff)=="YES";
    $canDelete=securityGetAccessRightYesNo('menuResourceTeam', 'delete', $aff)=="YES";
    if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
      $canCreate=false;
      $canUpdate=false;
      $canDelete=false;
    }
    if ($obj->idle==1) {
      $canUpdate=false;
      $canCreate=false;
      $canDelete=false;
    }
    $idleClass=($aff->idle or ($aff->endDate and $aff->endDate<$dateNow=date("Y-m-d")))?' affectationIdleClass':'';
    $res=new Resource($aff->idResource);
    $isResource=($res->id)?true:false;
    $goto="";
    $name=$aff->name;
    $typeAffectable='Resource';
    if (!$print and securityCheckDisplayMenu(null, $typeAffectable) and securityGetAccessRightYesNo('menu'.$typeAffectable, 'read', '')=="YES") {
      $goto=' onClick="gotoElement(\''.$typeAffectable.'\',\''.htmlEncode($aff->idResource).'\');" style="cursor: pointer;" ';
    }
    if ($aff->idResource!=$name and pq_trim($name)) {
      echo '<tr>';
      if (!$print) {
        echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space: nowrap;">';
        if ($canUpdate and !$print) {
          echo '  <a onClick="editAffectationResourceTeam('."'".htmlEncode($aff->id)."'".",'".get_class($obj)."'".",'".$type."'".",'".htmlEncode($aff->idResource)."'".",'".htmlEncode($aff->rate)."'".",'".htmlEncode($aff->idle)."'".",'".$aff->startDate."'".",'".htmlEncode($aff->endDate)."'".');" '.'title="'.i18n('editAffectationResourceTeam').'" > '.formatSmallButton('Edit').'</a>';
        }
        if ($canDelete and !$print) {
          echo '  <a onClick="removeAffectationResourceTeam('."'".htmlEncode($aff->id)."'".',\''.$aff->idResource.'\');" '.'title="'.i18n('removeAffectationResourceTeam').'" > '.formatSmallButton('Remove').'</a>';
        }
        if ($aff->idle) {
          echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
        } else {
          echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
        }
        echo '</td>';
      }
      echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" '.$goto.'>'.htmlEncode($aff->idResource).'</td>';
      
      echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left"'.$goto.'>';
      if ($aff->description and !$print) {
        echo '<div style="float:right">'.formatCommentThumb($aff->description).'</div>';
      }
      echo htmlEncode($name);
      echo '</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->startDate).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->endDate).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlEncode($aff->rate).'</td>';
      echo '</tr>';
    }
  }
  echo '</table></td></tr>';
  echo '</table>';
}
//gautier #Work Unit
function drawComplexities($nbComplexities,$obj,$list,$refresh=false) {
  $tabComplexities = array();
  foreach ($list as $val){
    $tabComplexities[]=$val->name;
  }
  $nbComplexity = count($tabComplexities);
  echo '<table style="width:33%">';
  echo '  <tr>';
  echo '    <td class="assignHeader" style="width:15%">'.i18n('complexities').'</td>';
  echo '  </tr>';
  for($i=1; $i<11; $i++){
    $value = null;
    $visible = "";
    if($i <= $nbComplexity ){
      $value = $tabComplexities[$i-1];
    }
    if($i>$nbComplexities)$visible= "style='display:none'";
    echo '  <tr '.$visible.' id="trComplexity'.$i.'">';
    echo '    <td>';
    echo '      <input dojoType="dijit.form.TextBox"  type="text" id="complexity'.$i.'" name="complexity'.$i.'"  class="input" style="width:100%;" value="'.$value.'" onchange="saveComplexity('.$obj->id.','.$i.');" />';
    echo '    </td>';
    echo '  </tr>';
  }
  echo '</table>';
}

function drawActivityWorkUnit($listActWU,$obj,$refresh=false,$visibility=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $paramEnableWorkUnit = Parameter::getGlobalParameter('enableWorkCommandManagement');
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  $loc=($obj->hasCurrency())?true:false;
  $locClass=($loc)?' localLabelClass ':'';
  $locClassDispl=($loc)?' localDisplayClass ':'';
  $proj=$obj->idProject;
  echo '<table style="width:100%" id="tabActivityWorkUnit">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="height:100%;width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="assignHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      echo '<a onClick="addActivityWorkUnit(\''.$obj->id.'\',\''.$visibility.'\');" title="'.i18n('addWorkUnit').'" /> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:12%">'.i18n('colWorkUnits').'</td>';
  echo '<td class="assignHeader" style="width:12%">'.i18n('colComplexity').'</td>';
  echo '<td class="assignHeader" style="width:12%">'.i18n('colQuantity').'</td>';
  if($paramEnableWorkUnit=='true'){
    echo '<td class="assignHeader" style="width:12%">'.i18n('colWorkCommand').'</td>';
  }
  echo '<td class="assignHeader" style="width:12%">'.i18n('charge').'</td>';
  echo '<td class="assignHeader" style="width:12%">'.i18n('colDuration').'</td>';
  if($visibility!='NO')echo '<td class="assignHeader '.$locClass.'" style="width:12%">'.i18n('colPrice').'</td>';
  echo'</tr>';
  $totalCharge = 0;
  $totalDuration = 0;
  foreach ($listActWU as $val){
    echo '<tr style="height:100%">';
    if (!$print) {
      echo '  <td class="assignData" style="width:5%;white-space:nowrap">';
      if ($canUpdate) {
        echo '  <a onClick="editActivityWorkUnit(\''.$val->id.'\',\''.$obj->id.'\',\''.$visibility.'\');" '.'title="'.i18n('editWorkUnit').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canDelete) {
        echo '  <a onClick="removeActivityWorkUnit(\''.$val->id.'\');" '.'title="'.i18n('removeWorkUnit').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '  </td>';
    }
    echo '<td style="text-align:center;" class="assignData">'.SqlList::getNameFromId('WorkUnit', $val->idWorkUnit) .'</td>';
  	echo '<td style="text-align:center;" class="assignData">'.SqlList::getNameFromId('Complexity', $val->idComplexity) .'</td>';
  	echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($val->quantity).'</td>';
  	if($paramEnableWorkUnit=='true'){
  	  if($val->idWorkCommand){
  	    $workCom = new WorkCommand($val->idWorkCommand);
  	    $command = new Command($workCom->idCommand);
  	    $ref = $command->reference;
  	    $name = $workCom->name;
  	    echo '<td style="text-align:center;" class="assignData"> '.$ref.' - '.$name.' </td>';
  	  }else{
  	    echo '<td style="text-align:center;" class="assignData"></td>';
  	  }
  	}
  	$complex = new Complexity($val->idComplexity);
  	$complexValue = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array('idComplexity'=>$val->idComplexity,'idWorkUnit'=>$val->idWorkUnit,'idCatalogUO'=>$complex->idCatalogUO));
  	echo '<td style="text-align:right;" class="assignData">'.Work::displayWorkWithUnit($complexValue->charge*$val->quantity).'</td>';
  	echo '<td style="text-align:right;" class="assignData">'.Work::displayWorkWithUnit($complexValue->duration*$val->quantity).'</td>';
  	if($visibility!='NO')echo '<td style="text-align:right;" class="assignData">'.htmlDisplayLocalCurrency($proj,$complexValue->price*$val->quantity,$complexValue->priceLocal*$val->quantity).'</td>';
    echo'</tr>';
    $totalCharge += $complexValue->charge*$val->quantity;
    $totalDuration += $complexValue->duration*$val->quantity;
  }
  $colspan = 4;
  if($paramEnableWorkUnit=='true' ){
    $colspan = 5;
  }
  if($print )$colspan--;
  //if($visibility=='NO')$colspan--;
  if(count($listActWU) > 0){
    echo'<tr>';
    echo '  <td colspan='.$colspan.' style="text-align:right;" class="assignHeader">'.pq_strtolower(i18n('sum')).'&nbsp;&nbsp;&nbsp;</td>';
    echo '  <td style="text-align:right;" class="assignHeader">'.Work::displayWorkWithUnit($totalCharge).'&nbsp</td>';
    echo '  <td style="text-align:right;" class="assignHeader">'.Work::displayWorkWithUnit($totalDuration).'&nbsp</td>';
    if($visibility!='NO')echo '  <td style="text-align:right;" class="assignHeader">'.htmlDisplayLocalCurrency($proj,$obj->ActivityPlanningElement->revenue,$obj->ActivityPlanningElement->revenueLocal).'&nbsp;</td>';
    echo'</tr>';
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawWorkUnits($obj,$listWorkUnit,$listComplexity,$refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="height:100%;width:100%;">';
  echo '<tr>';
  if (!$print) {
    echo '<td class="assignHeader" style="width:5%">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      echo '<a onClick="addWorkUnit(\''.$obj->id.'\');" title="'.i18n('addWorkUnit').'" /> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:12%">'.i18n('colWorkUnits').'</td>';
  foreach ($listComplexity as $comp){
    echo '<td class="assignHeader" style="width:12%">'.$comp->name.'</td>';
  }
  echo'</tr>';
  foreach ($listWorkUnit as $val){
    $idleClass = "";
    echo '<tr  style="height:100%;">';
    
    if($val->idle)$idleClass= ' background:#EAEAEA; ';
    if (!$print) {
      echo '  <td class="assignData" style="'.$idleClass.'width:5%;white-space:nowrap">';
        if ($canUpdate) {
          echo '  <a onClick="editWorkUnit(\''.$val->id.'\',\''.$obj->id.'\',\''.$val->validityDate.'\',\''.$val->idle.'\');" '.'title="'.i18n('editWorkUnit').'" > '.formatSmallButton('Edit').'</a>';
        }
        if ($canDelete) {
          echo '  <a onClick="removeWorkUnit(\''.$val->id.'\');" '.'title="'.i18n('removeWorkUnit').'" > '.formatSmallButton('Remove').'</a>';
        }
      echo '  </td>';
    }
    echo '  <td class="assignData" style="'.$idleClass.'width:12%">'.$val->reference.'</td>';
    foreach ($listComplexity as $comp){
      $idleClass2="";
      $compValu = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array('idWorkUnit'=>$val->id,'idComplexity'=>$comp->id));
      if(!$compValu->price and !$compValu->charge and !$compValu->duration)$idleClass2 = ' background:#EAEAEA; ';
      if($idleClass2==$idleClass){
        echo '  <td style="height:100%;padding:0;'.$idleClass2.'" class="assignData">';
      }else{
        echo '  <td style="height:100%;padding:0;'.$idleClass2.$idleClass.'" class="assignData">';
      }
      if($idleClass2== ""){
        $work=null;
        if($compValu->charge)$work = Work::displayWorkWithUnit($compValu->charge);
        if (Project::hasProjectCurrency($obj->idProject)) $price = ($compValu->price)?htmlDisplayLocalCurrency($obj->idProject, $compValu->price, $compValu->priceLocal):''; 
        else $price = ($compValu->price)?htmlDisplayCurrency($compValu->price):'';
        $duration = null;
        if($compValu->duration)$duration = $compValu->duration.' '.i18n('shortDay');
        echo '    <table style="width:100%;height:100%;text-align:right;" ><tr style="width:100%;">
                    <td title="'.i18n('charge').'" style="width:25%;border-right:1px solid #AAAAAA;padding:8px;">'.$work.'</td>
                    <td title="'.i18n('price').'" style="width:50%;border-right:1px solid #AAAAAA; padding:8px;">'.$price.'</td>
                    <td title="'.i18n('duration').'" style="width:25%;padding:8px;">'.$duration.'</td>
                    </tr></table>';
      }
      echo '  </td>';
    }
    echo'</tr>';
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawWorkUnitCatalogPhase($catalogUO,$listWorkUnitCatalogPhase,$object,$refresh=false) {
  $objectClass=RequestHandler::getClass('objectClass');
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($catalogUO), 'delete', $catalogUO)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($catalogUO), 'update', $catalogUO)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($catalogUO), 'create', $catalogUO)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($catalogUO), 'update', $catalogUO)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($catalogUO->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  if ($objectClass == "WorkCommand"){
    $complexityValues = new ComplexityValues();
    $compValues = SqlElement::getSingleSqlElementFromCriteria('ComplexityValues', array("idComplexity"=>$object->idComplexity,"idWorkUnit"=>$object->idWorkUnit));
  }
  $sumRatioPct =0;
  $sumRatioQt=0;
  $sumRatioAmount=0;
  $sumRatioAmountLocal=0;
  $sumCharge = 0;
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="height:100%;width:100%;">';
  echo '<tr>';
  if (!$print and $objectClass == "CatalogUO") {
    echo '<td class="assignHeader" style="width:5%;">';
    if ($catalogUO->id!=null and !$print and $canCreate and !$catalogUO->idle) {
      echo '<a onClick="addWorkUnitCatalogPhase(\''.$catalogUO->id.'\');" title="'.i18n('addWorkUnitCatalogPhase').'" /> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:50%;">'.i18n('colWorkUnitCatalogPhases').'</td>';
  echo '<td class="assignHeader" style="width:10%">'.i18n('percent').'</td>';
  
  if ($objectClass == "WorkCommand"){
    echo '<td class="assignHeader" style="width:10%">'.i18n('colShortQuantity').'</td>';
    $extraLocalClass=($object->hasCurrency())?' localLabelClass ':'';
    echo '<td class="assignHeader '.$extraLocalClass.'" style="width:10%">'.i18n('colAmount').'</td>';
    echo '<td class="assignHeader style="width:10%">'.i18n('charge').' ('.Work::displayShortWorkUnit().')</td>';
  }

  echo'</tr>';
  foreach ($listWorkUnitCatalogPhase as $val){
    $idleClass = "";
    echo '<tr  style="height:100%;">';
  
    if (!$print and $objectClass == "CatalogUO") {
      echo '  <td class="assignData" style="'.$idleClass.';white-space:nowrap">';
      if ($canUpdate) {
        echo '  <a onClick="editWorkUnitCatalogPhase(\''.$val->id.'\',\''.$catalogUO->id.'\');" '.'title="'.i18n('editWorkUnitCatalogPhase').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canDelete) {
        echo '  <a onClick="removeWorkUnitCatalogPhase(\''.$val->id.'\');" '.'title="'.i18n('removeWorkUnitCatalogPhase').'" > '.formatSmallButton('Remove').'</a>';
      }
      echo '  </td>';
    }
    echo '  <td class="assignData" style="'.$idleClass.'">'.$val->name.'</td>';
    echo '  <td class="assignData" style="'.$idleClass.'text-align: center;">'. (!empty($val->ratioPct) ? $val->ratioPct : '0') .' '.i18n('percent').'</td>';
    $sumRatioPct +=$val->ratioPct;
    
    if ($objectClass == "WorkCommand"){      
      $commandAmount= ($val->ratioPct * $object->commandAmount) / 100;
      $commandAmountLocal= ($val->ratioPct * $object->commandAmountLocal) / 100;
      $amountDisplay=htmlDisplayLocalCurrency($object->idProject,$commandAmount,$commandAmountLocal);
      echo '  <td class="assignData" style="'.$idleClass.'text-align: center;">'.($val->ratioPct * $object->commandQuantity) / 100 .'</td>';
      echo '  <td class="assignData" style="'.$idleClass.'text-align: center;">' .$amountDisplay. '</td>';
      echo '  <td class="assignData" style="'.$idleClass.'text-align: center;">' .work::displayWorkWithUnit((($val->ratioPct * $object->commandQuantity) / 100) * $compValues->charge). '</td>';
      $sumRatioQt += (($val->ratioPct * $object->commandQuantity) / 100 );
      $sumRatioAmount += $commandAmount;
      $sumRatioAmountLocal += $commandAmountLocal;
      $sumCharge += (($val->ratioPct * $object->commandQuantity) / 100) * $compValues->charge;
    }
    
    echo'</tr>';
  }
  
  if (!empty($listWorkUnitCatalogPhase)){
    if (!$print and $objectClass == "CatalogUO") {
      echo '<td class="assignData" style="width:10%;border-left: none;border-bottom: none;"></td>';
    }
    echo '<td class="assignData"  ><strong>' . ucfirst(i18n('colCountTotal')) . '</strong></td>';
    echo '<td class="assignData" style="text-align: center; background-color:' . ($sumRatioPct > 100 ? '#ffaaaa' : '#FFFFFF') . ';"><strong> ' .$sumRatioPct. '  '.i18n('percent').'</strong></td>';
    
    if ($objectClass == "WorkCommand"){
      echo '<td class="assignData" style="text-align: center; background-color:' . ($sumRatioPct > 100 ? '#ffaaaa' : '#FFFFFF') . ';"><strong> ' .$sumRatioQt. ' </strong></td>';
      echo '<td class="assignData" style="text-align: center; background-color:' . ($sumRatioPct > 100 ? '#ffaaaa' : '#FFFFFF') . ';"><strong> ' .htmlDisplayLocalCurrency($object->idProject,$sumRatioAmount,$sumRatioAmountLocal). '</strong></td>';
      echo '<td class="assignData" style="text-align: center; background-color:' . ($sumRatioPct > 100 ? '#ffaaaa' : '#FFFFFF') . ';"><strong> ' .work::displayWorkWithUnit($sumCharge). '</strong></td>';   
    } 
  }
  
  echo '</table></td></tr>';
  echo '</table>';
}

//gautier #ResourceCapacity
function drawResourceCapacity($list, $obj, $type, $refresh=false) {
	global $cr, $print, $user, $browserLocale, $comboDetail;
	$pluginObjectClass='Affectation';
	//$tableObject=$list;
	$lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
	foreach ($lstPluginEvt as $script) {
		require $script; // execute code
	}

	$canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
	$canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
	$canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
	if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
		$canCreate=false;
		$canUpdate=false;
		$canDelete=false;
	}
	if ($obj->idle==1) {
		$canUpdate=false;
		$canCreate=false;
		$canDelete=false;
	}
	if (get_class($obj)=='GlobalView') {
		$canUpdate=false;
		$canCreate=false;
		$canDelete=false;
	}

	echo '<table style="width:100%">';
	echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
	echo '<tr>';
	if (get_class($obj)=='Resource' or get_class($obj)=='ResourceTeam') {
		$idRess=$obj->id;
	} else {
		$idRess=null;
	}
	if (!$print) {
		echo '<td class="assignHeader" style="width:15%">';
		if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
			echo '<a onClick="addResourceCapacity(\''.get_class($obj).'\',\''.$type.'\',\''.$idRess.'\');" title="'.i18n('addResourceCapacity').'" /> '.formatSmallButton('Add').'</a>';
		}
		echo '</td>';
	}
	echo '<td class="assignHeader" style="width:12%">'.i18n('colId').'</td>';
	echo '<td class="assignHeader" style="width:35%">'.i18n('colCapacity').'</td>';
	echo '<td class="assignHeader" style="width:19%">'.i18n('colStartDate').'</td>';
	echo '<td class="assignHeader" style="width:19%">'.i18n('colEndDate').'</td>';
	echo '</tr>';

	foreach ($list as $resCap) {
		$idleClass=($resCap->idle or ($resCap->endDate and $resCap->endDate<date("Y-m-d")))?' affectationIdleClass':'';
		echo '<tr>';
		if (!$print) {
			echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space: nowrap;">';
			if ($canUpdate) {
				echo '  <a onClick="editResourceCapacity(\''.$resCap->id.'\',\''.$obj->id.'\',\''.$resCap->capacity.'\',\''.$resCap->idle.'\',\''.$resCap->startDate.'\',\''.$resCap->endDate.'\');" '.'title="'.i18n('editResourceCapacity').'" > '.formatSmallButton('Edit').'</a>';
			}
			if ($canDelete) {
				echo '  <a onClick="removeResourceCapacity(\''.$resCap->id.'\',\''.$resCap->idResource.'\');" '.'title="'.i18n('removeResourceCapacity').'" > '.formatSmallButton('Remove').'</a>';
			}
			if ($resCap->idle) {
			  echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
			} else {
			  echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
			}
			if ($resCap->description) {
				echo '<div style="float:right">'.formatCommentThumb($resCap->description).'</div>';
			}
			echo '</td>';
		}
		
		echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.$resCap->id.'</td>';
		echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlDisplayNumericWithoutTrailingZeros($resCap->capacity).'</td>';
		echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($resCap->startDate).'</td>';
		echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($resCap->endDate).'</td>';
		echo '</tr>';
	}
	echo '</table></td></tr>';
	echo '</table>';
}

function drawResourceSurbooking($list, $obj, $type, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Affectation';
  //$tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }

  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  if (get_class($obj)=='GlobalView') {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }

  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Resource' or get_class($obj)=='ResourceTeam') {
    $idRess=$obj->id;
  } else {
    $idRess=null;
  }
  if (!$print) {
    echo '<td class="assignHeader" style="width:15%">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      echo '<a onClick="addResourceSurbooking(\''.get_class($obj).'\',\''.$type.'\',\''.$idRess.'\');" title="'.i18n('addResourceSurbooking').'" /> '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:12%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader" style="width:35%">'.i18n('colSurbooking').'</td>';
  echo '<td class="assignHeader" style="width:19%">'.i18n('colStartDate').'</td>';
  echo '<td class="assignHeader" style="width:19%">'.i18n('colEndDate').'</td>';
  echo '</tr>';

  foreach ($list as $resSur) {//ouiii
    $idleClass=($resSur->idle or ($resSur->endDate and $resSur->endDate<date("Y-m-d")))?' affectationIdleClass':'';
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space: nowrap;">';
      if ($canUpdate) {
        echo '  <a onClick="editResourceSurbooking(\''.$resSur->id.'\',\''.$obj->id.'\',\''.$resSur->capacity.'\',\''.$resSur->idle.'\',\''.$resSur->startDate.'\',\''.$resSur->endDate.'\');" '.'title="'.i18n('editResourceSurbooking').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canDelete) {
        echo '  <a onClick="removeResourceSurbooking(\''.$resSur->id.'\',\''.$resSur->idResource.'\');" '.'title="'.i18n('removeResourceSurbooking').'" > '.formatSmallButton('Remove').'</a>';
      }
      if ($resSur->idle) {
        echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
      } else {
        echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
      }
      if ($resSur->description) {
        echo '<div style="float:right">'.formatCommentThumb($resSur->description).'</div>';
      }
    }
    echo '</td>';
    echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.$resSur->id.'</td>';
    echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlDisplayNumericWithoutTrailingZeros($resSur->capacity).'</td>';
    echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($resSur->startDate).'</td>';
    echo ' <td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($resSur->endDate).'</td>';
    echo '</tr>';
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawIncompatibleResource($list, $obj, $type, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Affectation';
  //$tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
  	require $script; // execute code
  }
  
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
  	$canCreate=false;
  	$canUpdate=false;
  	$canDelete=false;
  }
  if ($obj->idle==1) {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  if (get_class($obj)=='GlobalView') {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Resource' or get_class($obj)=='ResourceMaterial') {
  	$idRess=$obj->id;
  } else {
  	$idRess=null;
  }
  if (!$print) {
  	echo '<td class="assignHeader" style="width:15%">';
  	if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
  		echo '<a onClick="addResourceIncompatible(\''.$idRess.'\');" title="'.i18n('addIncompatibleResource').'" /> '.formatSmallButton('Add').'</a>';
  	}
  	echo '</td>';
  }
  echo '<td class="assignHeader" style="width:12%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader sortable" style="width:73%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '</tr>';
  
  foreach ($list as $resInc) {
  	echo '<tr>';
  	if (!$print) {
  		echo '<td class="assignData" style="text-align:center;white-space: nowrap;">';
  		if ($canDelete) {
  			echo '<a onClick="removeResourceIncompatible(\''.$resInc->id.'\');" '.'title="'.i18n('removeResourceIncompatible').'" > '.formatSmallButton('Remove').'</a>';
  		}
  		if ($resInc->description) {
  			echo '<div style="float:right">'.formatCommentThumb($resInc->description).'</div>';
  		}
  	}
  	echo '</td>';
  	$res = new ResourceAll($resInc->idIncompatible);
  	$classRes=($res->isMaterial)?'ResourceMaterial':'Resource';
  	$goto=' onClick="gotoElement(\''.$classRes.'\',\''.htmlEncode($res->id).'\');" ';
  	echo ' <td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" style="white-space: nowrap;" '.$goto.'>'.htmlEncode($res->id).'</td>';
  	echo ' <td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="white-space: nowrap;" '.$goto.'>'.htmlEncode($res->name);
  	if($res->isMaterial){
  	  echo '<div style="float:right; vertical-align:middle;"> '.formatIcon('ResourceMaterial', 16, i18n('ResourceMaterial')).'</div>';
  	}
  	echo '</td>';
  	echo '</tr>';
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawResourceSupport($list, $obj, $type, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Affectation';
  //$tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
  	require $script; // execute code
  }
  
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
  	$canCreate=false;
  	$canUpdate=false;
  	$canDelete=false;
  }
  if ($obj->idle==1) {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  if (get_class($obj)=='GlobalView') {
  	$canUpdate=false;
  	$canCreate=false;
  	$canDelete=false;
  }
  
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Resource' or get_class($obj)=='ResourceMaterial') {
  	$idRess=$obj->id;
  } else {
  	$idRess=null;
  }
  if (!$print) {
  	echo '<td class="assignHeader" style="width:15%">';
  	if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
  		echo '<a onClick="addResourceSupport(\''.$idRess.'\');" title="'.i18n('addSupportResource').'" /> '.formatSmallButton('Add').'</a>';
  	}
  	echo '</td>';
  }
  echo '<td class="assignHeader" style="width:12%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader sortable" style="width:54%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="assignHeader" style="width:19%">'.i18n('colRate').'</td>';
  echo '</tr>';
  
  foreach ($list as $resSup) {
  	echo '<tr>';
  	if (!$print) {
  		echo '<td class="assignData" style="text-align:center;white-space: nowrap;">';
  		if ($canUpdate) {
  			echo '  <a onClick="editResourceSupport(\''.$resSup->id.'\',\''.$resSup->idResource.'\');" '.'title="'.i18n('editResourceSupport').'" > '.formatSmallButton('Edit').'</a>';
  		}
  		if ($canDelete) {
  			echo '<a onClick="removeResourceSupport(\''.$resSup->id.'\');" '.'title="'.i18n('removeResourceSupport').'" > '.formatSmallButton('Remove').'</a>';
  		}
  		if ($resSup->description) {
  			echo '<div style="float:right">'.formatCommentThumb($resSup->description).'</div>';
  		}
  	}
  	echo '</td>';
  	$res = new ResourceAll($resSup->idSupport);
  	$classRes=($res->isMaterial)?'ResourceMaterial':'Resource';
  	$goto=' onClick="gotoElement(\''.$classRes.'\',\''.htmlEncode($res->id).'\');" ';
  	echo ' <td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" style="white-space: nowrap;"  '.$goto.'>'.htmlEncode($res->id).'</td>';
  	echo ' <td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" style="white-space: nowrap; cursor:pointer;" '.$goto.'>'.htmlEncode($res->name);
  	if($res->isMaterial){
  	  echo '<div style="float:right; vertical-align:middle;"> '.formatIcon('ResourceMaterial', 16, i18n('ResourceMaterial')).'</div>';
  	}
  	echo '</td>';
  	echo ' <td class="assignData" align="center" style="white-space: nowrap;">'.htmlEncode($resSup->rate).'</td>';
  	echo '</tr>';
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawProjectSituation($type, $obj){
	global $cr, $print, $outMode, $user, $comboDetail, $displayWidth, $printWidth;
	if ($comboDetail) {
		return;
	}
	$classList=null;
	if($type=='Expense'){
	  $classList = '(\'CallForTender\',\'Tender\',\'ProviderOrder\',\'ProviderBill\')';
	}else if($type=='Income'){
	  $classList = '(\'Bill\',\'Quotation\',\'Command\')';
	}
	$situationList = array();
	$situation = new Situation();
	$clauseWhere = 'idProject = '.Sql::fmtId($obj->idProject).' and refType in '.$classList;
	$situationList = $situation->getSqlElementsFromCriteria(null,null,$clauseWhere, ' date desc');
	$situationOrderedList = array();
	foreach ($situationList as $sit){
	  $class = $sit->refType;
	  $element = new $class($sit->refId);
	  if($element->idSituation == $sit->id){
	  	$situationOrderedList[$element->idSituation] = $sit;
	  }
	}
	$classElementList = pq_explode(',', pq_str_replace(array("'", "(", ")"), array("","",""), $classList));
	$elementList = array();
	foreach ($classElementList as $class){
	  $object = new $class();
      $critWhere = array('idProject'=>$obj->idProject, 'idSituation'=>null);
	  $objectList = $object->getSqlElementsFromCriteria($critWhere,null,null,null);
      if(count($objectList)>0){
      	$elementList = array_merge($elementList, $objectList);
      }
	}
	echo '<table width="99.9%">';
	echo '<tr>';
	echo '<td class="noteHeader" style="width:30%">' . i18n('colElement') . '</td>';
	echo '<td class="noteHeader" style="width:5%">' . i18n('colIdStatus') . '</td>';
	echo '<td class="noteHeader" style="width:15%">' . i18n('colDate') . '</td>';
	echo '<td class="noteHeader" style="width:20%">' . i18n('colSituation') . '</td>';
	echo '<td class="noteHeader" style="width:20%">' . i18n('colComment') . '</td>';
	echo '<td class="noteHeader" style="width:10%">' . i18n('colResponsible') . '</td>';
	echo '</tr>';
  	foreach ($situationOrderedList as $situation){
  	  $class = $situation->refType;
      $element = new $class($situation->refId);
      if($class == 'Tender'){
       if($element->idCallForTender){
         $selectedTenderStatusList = SqlList::getListWithCrit('TenderStatus', array('isSelected'=>1));
         $crit="idCallForTender=$element->idCallForTender and idTenderStatus in ".transformListIntoInClause($selectedTenderStatusList);
         $selectedTenderList = $element->getSqlElementsFromCriteria(null,null,$crit);
         if(count($selectedTenderList)>=1){
           if(! isset($selectedTenderStatusList[$element->idTenderStatus])){
             continue;
           }
         }
       }
      }
      if($situation->id){
   		$item = new $class($situation->refId);
   		$status= new Status($item->idStatus);
   		echo '<tr>';
   		echo '<td class="noteData" style="text-align:left;">';
   		echo '<table style="width:100%;">';
     		echo '<tr>';
         		echo '<td style="padding-right: 5px;width:5%;">'.formatIcon($class, "16").'</td>';
         		echo '<td style="width:75%;">'.htmlEncode(i18n($class)).' #'.htmlEncode($item->id).' - '.htmlEncode($item->name).'</td>';
         		if(!$print){
             		echo '<td style="width:5%;"><div style="padding-left: 15px;" onClick="gotoElement(\''.$situation->refType.'\',\''.htmlEncode($situation->refId).'\');">'.formatSmallButton('Goto', true).'</div></td>';
             		echo '<td style="width:5%;"><div style="padding-left: 5px;" class="roundedButtonSmall iconView iconSize16 imageColorNewGui" onclick="showDetail(\'idSituation\',0,\''.$situation->refType.'\',false,'.$situation->refId.',false)"></div></td>';
         		}    		
       		echo '</tr>';
   		echo '</table>';
   		echo '</td>';
   		echo '<td class="noteData" style="text-align:center;background-color:'.$status->color.';" >' .htmlFormatDateTime($status->name). '</td>';
   		echo '<td class="noteData" style="text-align:center">' . htmlFormatDateTime($situation->date) . '</td>';
   		echo '<td class="noteData" style="text-align:left">'.htmlEncode($situation->name).'</td>';
   		echo '<td class="noteData" style="text-align:left">'.$situation->comment.'</td>';
   		$responsible = new ResourceAll($situation->idResource);
   		echo '<td class="noteData" style="text-align:center">' . htmlEncode($responsible->name) . '</td>';
   		echo '</tr>';
   	  }
	}
	foreach ($elementList as $element){
		$class = get_class($element);
		if($class == 'Tender'){
			if($element->idCallForTender){
				$selectedTenderStatusList = SqlList::getListWithCrit('TenderStatus', array('isSelected'=>1));
				$crit="idCallForTender=$element->idCallForTender and idTenderStatus in ".transformListIntoInClause($selectedTenderStatusList);
				$selectedTenderList = $element->getSqlElementsFromCriteria(null,null,$crit);
				if(count($selectedTenderList)>=1){
					if(! isset($selectedTenderStatusList[$element->idTenderStatus])){
						continue;
					}
				}
			}
		}
		echo '<tr>';
		echo '<td class="noteData" style="text-align:left;">';
		echo '<table style="width:100%;">';
		echo '<tr>';
		echo '<td style="padding-right: 5px;width:5%;">'.formatIcon($class, "16").'</td>';
		echo '<td style="width:75%;">'.htmlEncode(i18n($class)).' #'.htmlEncode($element->id).' - '.htmlEncode($element->name).'</td>';
		echo '<td style="width:5%;"><div style="padding-left: 15px;" onClick="gotoElement(\''.$class.'\',\''.$element->id.'\');">'.formatSmallButton('Goto', true).'</div></td>';
		echo '<td style="width:5%;"><div style="padding-left: 5px;" class="roundedButtonSmall iconView iconSize16 imageColorNewGui" onclick="showDetail(\'idSituation\',0,\''.$class.'\',false,'.$element->id.',false)"></div></td>';
		echo '</tr>';
		echo '</table>';
		echo '</td>';
		$statusEl= new Status($element->idStatus);
		echo '<td class="noteData" style="text-align:center;background-color:'.$statusEl->color.';">'.htmlFormatDateTime($statusEl->name).'</td>';
		echo '<td class="noteData" style="text-align:center"></td>';
		echo '<td class="noteData" style="text-align:left"></td>';
		echo '<td class="noteData" style="text-align:left"></td>';
		echo '<td class="noteData" style="text-align:center"></td>';
		echo '</tr>';
	}
	echo '</table>';
}

function drawClientElementList($item, $object){
  echo '<table width="99.9%">';
  echo '<tr>';
  echo '<td class="noteHeader sortable" style="width:30%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">' . i18n('colName') . '</td>';
  $colDate = ($item == 'Command')?'colReceptionDate':'colSendDate';
  echo '<td class="noteHeader" style="width:15%">' . i18n($colDate) . '</td>';
  echo '<td class="noteHeader" style="width:20%">' . i18n('colUntaxedAmount') . '</td>';
  echo '<td class="noteHeader" style="width:20%">' . i18n('colFullAmount') . '</td>';
  echo '<td class="noteHeader" style="width:15%">' . i18n('colIdStatus') . '</td>';
  echo '</tr>';
  
  //$itemList = SqlList::getListWithCrit($item, array('idClient'=>$object->id), 'id',null, true);
  $objItem = new $item();
  $orderByDate = ($item=='Bill')?'date asc':null;
  $itemList = $objItem->getSqlElementsFromCriteria(array('idClient'=>$object->id),null,null,$orderByDate);
  $totalUntaxedAmount = 0;
  $totalFullAmount = 0;
  $totalUntaxedAmountLocal = 0;
  $totalFullAmountLocal = 0;
  foreach ($itemList as $obj){
    //$obj = new $item($id);
    $goto="";
    if (securityGetAccessRightYesNo('menu'.$item, 'read', '')=="YES") {
    	$goto=' onClick="gotoElement('."'".$item."','".htmlEncode($obj->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<tr '.$goto.'>';
    echo '<td class="noteData" style="text-align:left;">'.$obj->name.'</td>';
    $date = ($item == 'Command')?$obj->receptionDate:$obj->sendDate;
    echo '<td class="noteData" style="text-align:center;">'.htmlFormatDate($date).'</td>';
    echo '<td class="noteData" style="text-align:right;">'.htmlDisplayLocalCurrency($obj->idProject,$obj->untaxedAmount,$obj->untaxedAmountLocal).'</td>';
    echo '<td class="noteData" style="text-align:right;">'.htmlDisplayLocalCurrency($obj->idProject,$obj->fullAmount,$obj->fullAmountLocal).'</td>';
    $objStatus=new Status($obj->idStatus);
    echo '<td class="noteData colorNameData" style="text-align:left;"><div style="word-wrap: break-word; height:100%; overflow:auto;">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</div></td>';
    echo '</tr>';
    $totalUntaxedAmount += $obj->untaxedAmount;
    $totalFullAmount += $obj->fullAmount;
    $totalUntaxedAmountLocal += $obj->untaxedAmountLocal;
    $totalFullAmountLocal += $obj->fullAmountLocal;
  }
  echo '</table>';
  if(count($itemList)>0){
    echo '<table width="99.9%">';
  	echo '<tr>';
  	echo '<td class="noteData affectationIdleClass" style="text-align:center;width:45%;border-top: 0px;">' . i18n('sum') . '</td>';
  	echo '<td class="noteData affectationIdleClass" style="text-align:right;width:20%;border-top: 0px;">' .htmlDisplayLocalCurrency($obj->idProject,$totalUntaxedAmount,null) . '</td>';
  	echo '<td class="noteData affectationIdleClass" style="text-align:right;width:20%;border-top: 0px;">' . htmlDisplayLocalCurrency($obj->idProject,$totalFullAmount,null) . '</td>';
  	echo '<td class="noteData affectationIdleClass" style="width:15%;border-top: 0px;"></td>';
  	echo '</tr>';
  	echo '</table>';
  }
}

function drawProspectEstimateList($object){
  echo '<table width="99.9%">';
  echo '<tr>';
  echo '<td class="noteHeader sortable" style="width:40%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">' . i18n('colName') . '</td>';
  echo '<td class="noteHeader" style="width:20%">' . i18n('colUntaxedAmount') . '</td>';
  echo '<td class="noteHeader" style="width:20%">' . i18n('colFullAmount') . '</td>';
  echo '<td class="noteHeader" style="width:20%">' . i18n('colIdStatus') . '</td>';
  echo '</tr>';

  $objItem = new ProspectEstimate();
  $itemList = $objItem->getSqlElementsFromCriteria(array('idProspect'=>$object->id));
  $totalUntaxedAmount = 0;
  $totalFullAmount = 0;
  foreach ($itemList as $obj){
    $goto="";
    if (securityGetAccessRightYesNo('menuProspectEstimate', 'read', '')=="YES") {
      $goto=' onClick="gotoElement('."'ProspectEstimate','".htmlEncode($obj->id)."'".');" style="cursor: pointer;" ';
    }
    echo '<tr '.$goto.'>';
    echo '<td class="noteData" style="text-align:left;">'.$obj->name.'</td>';
    echo '<td class="noteData" style="text-align:right;">'.htmlDisplayLocalCurrency($obj->idProject,$obj->untaxedAmount,$obj->untaxedAmountLocal).'</td>';
    echo '<td class="noteData" style="text-align:right;">'.htmlDisplayLocalCurrency($obj->idProject,$obj->fullAmount,$obj->fullAmountLocal).'</td>';
    $objStatus=new Status($obj->idStatus);
    echo '<td class="noteData colorNameData" style="text-align:left;"><div style="word-wrap: break-word; height:100%; overflow:auto;">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</div></td>';
    echo '</tr>';
    $totalUntaxedAmount += $obj->untaxedAmount;
    $totalFullAmount += $obj->fullAmount;
  }
  echo '</table>';
  if(count($itemList)>0){
    echo '<table width="99.9%">';
    echo '<tr>';
    echo '<td class="noteData affectationIdleClass" style="text-align:center;width:40%;border-top: 0px;">' . i18n('sum') . '</td>';
    echo '<td class="noteData affectationIdleClass" style="text-align:right;width:20%;border-top: 0px;">' . htmlDisplayLocalCurrency($obj->idProject,$totalUntaxedAmount,null) . '</td>';
    echo '<td class="noteData affectationIdleClass" style="text-align:right;width:20%;border-top: 0px;">' . htmlDisplayLocalCurrency($obj->idProject,$totalFullAmount,null) . '</td>';
    echo '<td class="noteData affectationIdleClass" style="width:20%;border-top: 0px;"></td>';
    echo '</tr>';
    echo '</table>';
  }
}

function drawWorkCommand($list, $obj) {
    global $cr, $print, $user, $browserLocale, $comboDetail;
    $canCreate = securityGetAccessRightYesNo('menu'.get_class($obj), 'create', $obj) == "YES";
    $canUpdate = securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj) == "YES";
    $canDelete = securityGetAccessRightYesNo('menu'.get_class($obj), 'delete', $obj) == "YES";

    $orphanChildren = array_filter($list, function($workCom) {
        return $workCom->elementary == 1 && is_null($workCom->idWorkCommand);
    });
    $mothers = array_filter($list, function($workCom) {
        return $workCom->elementary == 0 && is_null($workCom->idWorkCommand);
    });
    $children = array_filter($list, function($workCom) {
        return $workCom->elementary == 1 && !is_null($workCom->idWorkCommand);
    });

    $childrenByMother = [];
    $totalAmountChild = [];
    foreach ($children as $child) {
        $childrenByMother[$child->idWorkCommand][] = $child;
    }
    $loc=($obj->hasCurrency())?true:false;
    $locClass=($loc)?' localLabelClass ':'';
    $locClassDispl=($loc)?' localDisplayClass ':'';
    $proj=$obj->idProject;
    echo '<table style="width:100%">';
    echo '<tr>';
    echo '  <td colspan=3 class="reportTableHeader" style="width:40%">' . pq_ucfirst(i18n('colWorkCommand')) . '</td>';
    echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('ordered')) . '</td>';
    echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('used')) . '</td>';
    echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('colAccepted')) . '</td>';
    echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('colBilled')) . '</td>';
    echo '</tr>';

    echo '<tr>';
    echo '  <td class="noteHeader" style="width:10%">';
    if ($canUpdate && !$obj->idle) {
      echo ' <div style="display: flex; justify-content: center;gap:10px">';
        echo '    <a onClick="addWorkCommand(\''.$obj->id.'\');" title="'.i18n('addProviderTerm').'" > '.formatSmallButton('Add').'</a>';
        echo '    <a onClick="addParentWorkCommand (\''.$obj->id.'\');" title="'.i18n('addParentWorkCommand').'" > '.formatSmallButton('Organization', true).'</a>';
      echo ' </div>';
    }
    echo ' </td>';
    echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colId')) . '</td>';
    echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colName')) . '</td>';
    echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
    echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
    echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
    echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
    echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
    echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
    echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
    echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
    echo '</tr>';

    $amountCommand = 0;
    $amountBilledCommand = 0;
    $amountDoneCommand = 0;
    $amountAcceptedCommand = 0;
    $amountCommandLocal = 0;
    $amountBilledCommandLocal = 0;
    $amountDoneCommandLocal = 0;
    $amountAcceptedCommandLocal = 0;

    foreach ($orphanChildren as $orphan) {
      displayWorkCommandRow($orphan, $canUpdate, $canDelete, $obj, false);
  
      $amountCommand += $orphan->commandAmount;
      $amountDoneCommand += $orphan->doneAmount;
      $amountAcceptedCommand += $orphan->acceptedAmount;
      $amountBilledCommand += $orphan->billedAmount;
      $amountCommandLocal += $orphan->commandAmountLocal;
      $amountDoneCommandLocal += $orphan->doneAmountLocal;
      $amountAcceptedCommandLocal += $orphan->acceptedAmountLocal;
      $amountBilledCommandLocal += $orphan->billedAmountLocal;
    }

    foreach ($mothers as $mother) {
      $motherTotals = calculateChildTotals($childrenByMother[$mother->id] ?? []);
      $sumChildrenQuantity = $motherTotals['commandQuantity'];
      $sumChildrenAmount = $motherTotals['commandAmount'];
      displayWorkCommandRow($mother, $canUpdate, $canDelete, $obj, true, false, $sumChildrenQuantity, $sumChildrenAmount);
      
      $amountCommand +=  $mother->commandAmount;
      $amountDoneCommand += $mother->doneAmount;
      $amountAcceptedCommand += $mother->acceptedAmount;
      $amountBilledCommand += $mother->billedAmount;
      $amountCommandLocal +=  $mother->commandAmountLocal;
      $amountDoneCommandLocal += $mother->doneAmountLocal;
      $amountAcceptedCommandLocal += $mother->acceptedAmountLocal;
      $amountBilledCommandLocal += $mother->billedAmountLocal;
      if (isset($childrenByMother[$mother->id])) {
          foreach ($childrenByMother[$mother->id] as $child) {
              displayWorkCommandRow($child, $canUpdate, $canDelete, $obj, false, true);
          }
      }
    }
    
    echo '<tr>';
    echo '  <td colspan=4 class="noteHeader">' . pq_ucfirst(i18n('colCountTotal')) . '</td>';
    echo '  <td colspan=2 style="text-align:right;" class="noteHeader '.$locClassDispl.'">'.htmlDisplayLocalCurrency($proj,$amountCommand,$amountCommandLocal).'&nbsp;</td>';
    echo '  <td colspan=2 style="text-align:right;" class="noteHeader '.$locClassDispl.'">'.htmlDisplayLocalCurrency($proj,$amountDoneCommand,$amountDoneCommandLocal).'&nbsp;</td>';
    echo '  <td colspan=2 style="text-align:right;" class="noteHeader '.$locClassDispl.'">'.htmlDisplayLocalCurrency($proj,$amountAcceptedCommand, $amountAcceptedCommandLocal).'&nbsp;</td>';
    echo '  <td colspan=2 style="text-align:right;" class="noteHeader '.$locClassDispl.'">'.htmlDisplayLocalCurrency($proj,$amountBilledCommand,$amountBilledCommandLocal).'&nbsp;</td>';
    echo '</tr>';
    echo '</table>';
}

function displayWorkCommandRow($workCom, $canUpdate, $canDelete, $obj, $isMother = false, $isIndented = false,$sumChildrenQuantity=null, $sumChildrenAmount=null) {
  $loc=($obj->hasCurrency())?true:false;
  $locClass=($loc)?' localDisplayClass ':'';
  $proj=$obj->idProject;
    echo '<tr><td class="assignData" style="text-align:center;white-space: nowrap;">';
    if ($canUpdate && !$obj->idle) {
      $isWorkCommandParent = ($workCom->elementary == 1) ? false : true; 
      echo '<a onClick="editWorkCommand(\''.$obj->id.'\',\''.$workCom->id.'\',\''.$workCom->idWorkUnit.'\',\''.$workCom->idComplexity.'\',\''.$workCom->commandQuantity.'\',\''.$workCom->unitAmount.'\',\''.$workCom->commandAmount.'\',\''.$workCom->unitAmountLocal.'\',\''.$workCom->commandAmountLocal.'\', \''.$workCom->idWorkCommand.'\',\''.$workCom->name.'\', \'' .$isWorkCommandParent.'\');" title="'.i18n('editWorkCommand').'" > '.formatSmallButton('Edit').'</a>';
    }
    if ($canDelete && !$obj->idle) {
        echo '<a onClick="removeWorkCommand(\''.$workCom->id.'\');" title="'.i18n('removeWorkCommand').'" > '.formatSmallButton('Remove').'</a>';
    }
    echo '</td>';
    $indentation = $isIndented ? 'padding-left:15px' : '';
    $fontWeight = $isMother ? 'font-weight:bold;' : '';
    if ($sumChildrenQuantity != null ){
      if ($sumChildrenQuantity < $workCom->commandQuantity) $backgroundColorQuantity = 'background-color: rgb(255, 217, 170)';
      elseif ($sumChildrenQuantity > $workCom->commandQuantity) $backgroundColorQuantity = 'background-color: rgb(255, 170, 170)';
      else $backgroundColorQuantity = '';
    }else $backgroundColorQuantity = '';
    
    if ($sumChildrenAmount != null ){
      if ($sumChildrenAmount < $workCom->commandAmount) $backgroundColorAmount = 'background-color: rgb(255, 217, 170)';
      elseif ($sumChildrenAmount > $workCom->commandAmount) $backgroundColorAmount = 'background-color: rgb(255, 170, 170)';
      else $backgroundColorAmount = '';
    }else $backgroundColorAmount = '';
    
    echo '<td class="assignData" style="text-align:center;'.$fontWeight.'">'.'#'.$workCom->id.'</td>';
    if ($isMother){
      echo '<td class="assignData" style="'. $fontWeight .'">' . $workCom->name . '<br><span style="color:gray;font-size:88%">'.SqlList::getNameFromId('WorkUnit', $workCom->idWorkUnit).' - '.SqlList::getNameFromId('Complexity', $workCom->idComplexity).'</span></td>';
    }else{
      echo '<td class="assignData" style="'.$indentation.'">'.$workCom->name.'<br><span style="color:gray;font-size:88%">'.SqlList::getNameFromId('WorkUnit', $workCom->idWorkUnit).' - '.SqlList::getNameFromId('Complexity', $workCom->idComplexity).'</span></td>';
    }
    echo '<td style="vertical-align: middle;text-align:center;'.$fontWeight.'; '.$backgroundColorQuantity.'" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->commandQuantity).'</td>';
    echo '<td style="vertical-align: middle;text-align:right;'.$fontWeight.'; '.$backgroundColorAmount.'" class="assignData'.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->commandAmount,$workCom->commandAmountLocal).'</td>';
    echo '<td style="vertical-align: middle;text-align:center;'.$fontWeight.'" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->doneQuantity).'</td>';
    echo '<td style="vertical-align: middle;text-align:right;'.$fontWeight.'" class="assignData'.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->doneAmount,$workCom->doneAmountLocal).'</td>';
    echo '<td style="vertical-align: middle;text-align:center;'.$fontWeight.'" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->acceptedQuantity).'</td>';
    echo '<td style="vertical-align: middle;text-align:right;'.$fontWeight.'" class="assignData'.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->acceptedAmount,$workCom->acceptedAmountLocal).'</td>';
    echo '<td style="vertical-align: middle;text-align:center;'.$fontWeight.'" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->billedQuantity).'</td>';
    echo '<td style="vertical-align: middle;text-align:right;'.$fontWeight.'" class="assignData'.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->billedAmount,$workCom->billedAmountLocal).'</td>';
    echo '</tr>';
}

function calculateChildTotals($children) {
    $totals = [
        'commandQuantity' => 0, 'commandAmount' => 0, 
        'doneQuantity' => 0, 'doneAmount' => 0, 
        'acceptedQuantity' => 0, 'acceptedAmount' => 0, 
        'billedQuantity' => 0, 'billedAmount' => 0
    ];   
    foreach ($children as $child) {
        $totals['commandQuantity'] += $child->commandQuantity;
        $totals['commandAmount'] += $child->commandAmount;
        $totals['doneQuantity'] += $child->doneQuantity;
        $totals['doneAmount'] += $child->doneAmount;
        $totals['acceptedQuantity'] += $child->acceptedQuantity;
        $totals['acceptedAmount'] += $child->acceptedAmount;
        $totals['billedQuantity'] += $child->billedQuantity;
        $totals['billedAmount'] += $child->billedAmount;
    }   
    return $totals;
}


function drawBilledWorkCommand($list,$obj){
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create',$obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update',$obj)=="YES";
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete',$obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  $loc=($obj->hasCurrency())?true:false;
  $locClass=($loc)?' localLabelClass ':'';
  $locClassDispl=($loc)?' localDisplayClass ':'';
  $proj=$obj->idProject;
  echo '<table style="width:100%">';
  echo '<tr>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:40%">' . pq_ucfirst(i18n('colWorkCommand')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:20%">' . pq_ucfirst(i18n('ordered')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:20%">' . pq_ucfirst(i18n('used')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:20%">' . pq_ucfirst(i18n('colBilled')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:20%">' . pq_ucfirst(i18n('colCurrentBilled')) . '</td>';
  echo '</tr>';
  echo '<tr>';
  echo '  <td class="noteHeader" style="width:10%">';
  if($canUpdate){
    echo '    <a onClick="addBilledWorkCommand(\''.$obj->id.'\');" title="'.i18n('addProviderTerm').'" > '.formatSmallButton('Add').'</a>';
  }
  echo ' </td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colName')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '</tr>';
  $amountCommandArray = array();
  $amountBilledCommandAcutal = 0;
  $amountBilledCommandAcutalLocal = 0;
  foreach ($list as $billedWorkCom){
    $workCom = new WorkCommand($billedWorkCom->idWorkCommand);
    echo '<tr><td class="assignData" style="text-align:center;white-space: nowrap;">';
    if ($canUpdate) {
      echo '<a onClick="editBilledWorkCommand(\''.$obj->id.'\',\''.$billedWorkCom->id.'\',\''.$billedWorkCom->idWorkCommand.'\',\''.$billedWorkCom->billedQuantity.'\');" '.'title="'.i18n('editWorkCommand').'" > '.formatSmallButton('Edit').'</a>';
  	}
  	if ($canDelete) {
      echo '<a onClick="removeBilledWorkCommand(\''.$billedWorkCom->id.'\',\''.$billedWorkCom->idWorkCommand.'\');" '.'title="'.i18n('removeWorkCommand').'" > '.formatSmallButton('Remove').'</a>';
  	}
    echo '</td>';
    echo '<td class="assignData '.$locClass.'">'.$workCom->name.'</td>';
  	echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->commandQuantity).'</td>';
  	echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->commandAmount,$workCom->commandAmountLocal).'</td>';
  	echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->doneQuantity).'</td>';
  	echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->doneAmount,$workCom->doneAmountLocal).'</td>';
  	echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->billedQuantity).'</td>';
  	echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->billedAmount,$workCom->billedAmountLocal).'</td>';
    echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($billedWorkCom->billedQuantity).'</td>';
    echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$billedWorkCom->billedQuantity*$workCom->unitAmount,$billedWorkCom->billedQuantity*$workCom->unitAmountLocal).'</td></tr>';
    $amountBilledCommandAcutal +=  $billedWorkCom->billedQuantity*$workCom->unitAmount;
    $amountBilledCommandAcutalLocal +=  $billedWorkCom->billedQuantity*$workCom->unitAmountLocal;
    $amountCommandArray[$workCom->id]['commandAmount']=$workCom->commandAmount;
    $amountCommandArray[$workCom->id]['amountDoneCommand']=$workCom->doneAmount;
    $amountCommandArray[$workCom->id]['amountBilledCommand']=$workCom->billedAmount;
    $amountCommandArray[$workCom->id]['commandAmountLocal']=$workCom->commandAmountLocal;
    $amountCommandArray[$workCom->id]['amountDoneCommandLocal']=$workCom->doneAmountLocal;
    $amountCommandArray[$workCom->id]['amountBilledCommandLocal']=$workCom->billedAmountLocal;
  }
  $amountCommand = 0;
  $amountDoneCommand = 0;
  $amountBilledCommand = 0;
  $amountCommandLocal = 0;
  $amountDoneCommandLocal = 0;
  $amountBilledCommandLocal = 0;
  foreach ($amountCommandArray as $val){
    $amountCommand += $val['commandAmount'];
    $amountDoneCommand += $val['amountDoneCommand'];
    $amountBilledCommand  += $val['amountBilledCommand'];
    $amountCommandLocal += $val['commandAmountLocal'];
    $amountDoneCommandLocal += $val['amountDoneCommandLocal'];
    $amountBilledCommandLocal  += $val['amountBilledCommandLocal'];
  }
  echo '<tr>';
  echo '  <td colspan=2 class="noteHeader">' .pq_ucfirst(i18n('colCountTotal')) . '</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountCommand,$amountCommandLocal).'&nbsp;</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountDoneCommand,$amountDoneCommandLocal).'&nbsp;</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountBilledCommand,$amountBilledCommandLocal).'&nbsp;</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountBilledCommandAcutal,$amountBilledCommandAcutalLocal).'&nbsp;</td>';
  echo '</tr>';

  echo '</table>';

}

function drawAcceptedWorkCommand($list,$obj){
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $canCreate=securityGetAccessRightYesNo('menu'.get_class($obj), 'create',$obj)=="YES";
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update',$obj)=="YES";
  $canDelete=securityGetAccessRightYesNo('menu'.get_class($obj), 'delete',$obj)=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  $loc=($obj->hasCurrency())?true:false;
  $locClass=($loc)?' localLabelClass ':'';
  $locClassDispl=($loc)?' localDisplayClass ':'';
  $proj=$obj->idProject;
  echo '<table style="width:100%">';
  echo '<tr>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:40%">' . pq_ucfirst(i18n('colWorkCommand')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('ordered')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('used')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('colAccepted')) . '</td>';
  echo '  <td colspan=2 class="reportTableHeader" style="width:15%">' . pq_ucfirst(i18n('colCurrentAccepted')) . '</td>';
  echo '</tr>';
  echo '<tr>';
  echo '  <td class="noteHeader" style="width:10%">';
  if($canUpdate){
    echo '    <a onClick="addAcceptedWorkCommand(\''.$obj->id.'\');" title="'.i18n('addProviderTerm').'" > '.formatSmallButton('Add').'</a>';
  }
  echo ' </td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colName')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '  <td class="noteHeader">' . pq_ucfirst(i18n('colQty')) . '</td>';
  echo '  <td class="noteHeader '.$locClass.'">' . pq_ucfirst(i18n('colAmount')) . '</td>';
  echo '</tr>';
  $amountCommandArray = array();
  $amountAcceptedCommandAcutal = 0;
  $amountAcceptedCommandAcutalLocal = 0;
  foreach ($list as $acceptedWorkCom){
    $workCom = new WorkCommand($acceptedWorkCom->idWorkCommand);
    echo '<tr><td class="assignData" style="text-align:center;white-space: nowrap;">';
    if ($canUpdate) {
      echo '<a onClick="editAcceptedWorkCommand(\''.$obj->id.'\',\''.$acceptedWorkCom->id.'\',\''.$acceptedWorkCom->idWorkCommand.'\',\''.$acceptedWorkCom->acceptedQuantity.'\');" '.'title="'.i18n('editWorkCommand').'" > '.formatSmallButton('Edit').'</a>';
    }
    if ($canDelete) {
      echo '<a onClick="removeAcceptedWorkCommand(\''.$acceptedWorkCom->id.'\',\''.$acceptedWorkCom->idWorkCommand.'\');" '.'title="'.i18n('removeWorkCommand').'" > '.formatSmallButton('Remove').'</a>';
    }
    echo '</td>';
    echo '<td class="assignData '.$locClass.'">'.$workCom->name .'</td>';
    echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->commandQuantity).'</td>';
    echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->commandAmount,$workCom->commandAmountLocal).'</td>';
    echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->doneQuantity).'</td>';
    echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->doneAmount,$workCom->doneAmountLocal).'</td>';
    echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($workCom->acceptedQuantity).'</td>';
    echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$workCom->acceptedAmount,$workCom->acceptedAmountLocal).'</td>';
    echo '<td style="text-align:center;" class="assignData">'.htmlDisplayNumericWithoutTrailingZeros($acceptedWorkCom->acceptedQuantity).'</td>';
    echo '<td style="text-align:right;" class="assignData '.$locClass.'">'.htmlDisplayLocalCurrency($proj,$acceptedWorkCom->acceptedQuantity*$workCom->unitAmount,$acceptedWorkCom->acceptedQuantity*$workCom->unitAmountLocal).'</td></tr>';
    $amountAcceptedCommandAcutal +=  $acceptedWorkCom->acceptedQuantity*$workCom->unitAmount;
    $amountAcceptedCommandAcutalLocal +=  $acceptedWorkCom->acceptedQuantity*$workCom->unitAmountLocal;
    $amountCommandArray[$workCom->id]['commandAmount']=$workCom->commandAmount;
    $amountCommandArray[$workCom->id]['amountDoneCommand']=$workCom->doneAmount;
    $amountCommandArray[$workCom->id]['amountAcceptedCommand']=$workCom->acceptedAmount;
    $amountCommandArray[$workCom->id]['commandAmountLocal']=$workCom->commandAmountLocal;
    $amountCommandArray[$workCom->id]['amountDoneCommandLocal']=$workCom->doneAmountLocal;
    $amountCommandArray[$workCom->id]['amountAcceptedCommandLocal']=$workCom->acceptedAmountLocal;
  }
  $amountCommand = 0;
  $amountDoneCommand = 0;
  $amountAcceptedCommand = 0;
  $amountCommandLocal = 0;
  $amountDoneCommandLocal = 0;
  $amountAcceptedCommandLocal = 0;
  foreach ($amountCommandArray as $val){
    $amountCommand += $val['commandAmount'];
    $amountDoneCommand += $val['amountDoneCommand'];
    $amountAcceptedCommand  += $val['amountAcceptedCommand'];
    $amountCommandLocal += $val['commandAmountLocal'];
    $amountDoneCommandLocal += $val['amountDoneCommandLocal'];
    $amountAcceptedCommandLocal  += $val['amountAcceptedCommandLocal'];
  }
  echo '<tr>';
  echo '  <td colspan=2 class="noteHeader">' .pq_ucfirst(i18n('colCountTotal')) . '</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountCommand,$amountCommandLocal).'&nbsp;</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountDoneCommand,$amountDoneCommandLocal).'&nbsp;</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountAcceptedCommand,$amountAcceptedCommandLocal).'&nbsp;</td>';
  echo '  <td colspan=2 style="text-align:right;" class="noteHeader">'.htmlDisplayLocalCurrency($proj,$amountAcceptedCommandAcutal,$amountAcceptedCommandAcutalLocal).'&nbsp;</td>';
  echo '</tr>';

  echo '</table>';

}

// gautier #ProviderTerm
function drawProviderTermFromObject($list, $obj, $type, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='ProviderTerm';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  $list=array();
  foreach ($listTemp as $term) {
    $list['#'.$term->id]=$term;
  }
  ksort($list);
  if ($comboDetail) {
    return;
  }
  $canCreate=securityGetAccessRightYesNo('menuAffectation', 'create')=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  
  if (get_class($obj)=='ProviderOrder') {
    $idProviderOrder=$obj->id;
  } else {
    $idProviderOrder=null;
  }
  
  echo '<table style="width:100%">';
  // echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  echo '<td class="assignHeader" style="width:10%">';
  
  $provTerm=new ProviderTerm();
  $billLine=new BillLine();
  $critArray=array("idProviderOrder"=>$obj->id);
  $listProvTerm=$provTerm->getSqlElementsFromCriteria($critArray);
  $test=false;
  $y=0;
  foreach ($listProvTerm as $prov) {
    $y=1;
    $critArray2=array("refType"=>"ProviderTerm", "refId"=>$prov->id);
    $cpt=$billLine->countSqlElementsFromCriteria($critArray2);
    if ($cpt!=0) {
      $test=true;
    }
  }
  $isLineProviderTerm='test';
  if ($obj->totalUntaxedAmount!=0) {
    if ($test!=true or $y==0) {
      $isLineProviderTerm=false;
      echo '<a onClick="addProviderTerm(\''.get_class($obj).'\',\''.$type.'\',\''.$idProviderOrder.'\',\'false\');" title="'.i18n('addProviderTerm').'" > '.formatSmallButton('Add').'</a>';
    }
    $billLineO=new BillLine();
    $billLineList=$billLineO->getSqlElementsFromCriteria(array("refType"=>"ProviderOrder", "refId"=>$obj->id));
    if ($billLineList) {
      if ($y==0 or $test==true) {
        $isLineProviderTerm=true;
        echo '<a onClick="addProviderTerm(\''.get_class($obj).'\',\''.$type.'\',\''.$idProviderOrder.'\',\'true\');" title="'.i18n('addProviderTermLine').'" > '.formatSmallButton('Split').'</a>';
      }
    }
  }
  echo '</td>';
  echo '<td class="assignHeader" style="width:10%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader" style="width:15%">'.i18n('colStatusDateTime').'</td>';
  echo '<td class="assignHeader '.(($obj->hasCurrency())?' localLabelClass ':'').'" style="width:20%" >'.i18n('colValidatedAmount').'</td>';
  echo '<td class="assignHeader" style="width:45%">'.i18n('colIdProviderBill').'</td>';
  $sumTermAmount=0;
  $sumTermAmountLocal=0;
  echo '</tr>';
  foreach ($list as $term) {
    $canUpdate=securityGetAccessRightYesNo('menuProvideTerm', 'update', $term)=="YES";
    $canDelete=securityGetAccessRightYesNo('menuProvideTerm', 'delete', $term)=="YES";
    if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
      $canCreate=false;
      $canUpdate=false;
      $canDelete=false;
    }
    if ($obj->idle==1) {
      $canUpdate=false;
      $canCreate=false;
      $canDelete=false;
    }
    if ($term->idProviderBill) {
      $canUpdate=false;
      $canDelete=false;
    }
    
    $idleClass=($term->idle)?' affectationIdleClass':'';
    $goto="";
    $typeAffectable='ProviderTerm';
    if (!$print and securityCheckDisplayMenu(null, $typeAffectable) and securityGetAccessRightYesNo('menu'.$typeAffectable, 'read', '')=="YES") {
      $goto=' onClick="gotoElement(\''.$typeAffectable.'\',\''.htmlEncode($term->id).'\');" style="cursor: pointer;" ';
    }
    $goto2="";
    $typeAffectable2='ProviderBill';
    if (!$print and securityCheckDisplayMenu(null, $typeAffectable2) and securityGetAccessRightYesNo('menu'.$typeAffectable2, 'read', '')=="YES") {
      $goto2=' onClick="gotoElement(\''.$typeAffectable2.'\',\''.htmlEncode($term->idProviderBill).'\');" ';
    }
    echo '<tr>';
    if (!$print) {
      echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space: nowrap;">';
      if ($canUpdate and !$print) {
        echo '  <a onClick="editProviderTerm(\''.get_class($obj).'\',\''.$obj->id.'\',\''.$isLineProviderTerm.'\',\''.$term->id.'\',\''.$term->name.'\',\''.$term->date.'\',\''.htmlDisplayNumericWithoutTrailingZeros($term->taxPct).'\',\''.htmlDisplayNumericWithoutTrailingZeros($obj->discountRate).'\',\''.$term->untaxedAmount.'\',\''.$term->taxAmount.'\',\''.$term->fullAmount.'\',\''.$obj->totalUntaxedAmount.'\');" '.'title="'.i18n('editProviderTerm').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canDelete and !$print) {
        echo '  <a onClick="removeProviderTerm('."'".htmlEncode($term->id)."'".');" '.'title="'.i18n('removeProviderTerm').'" > '.formatSmallButton('Remove').'</a>';
      }
//       if ($term->idle) {
//         echo '<div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div>';
//       } else {
//         echo '<div style="display:table-cell;width:20px;">&nbsp;</div>';
//       }
      if ($term->isPaid) {
        echo i18n('colIsPaid');
      } else if ($term->isBilled) {
        echo i18n('colIsBilled');
      }
      echo '</td>';
    }
    echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" '.$goto.'>#'.htmlEncode($term->id).'</td>';
    echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" '.$goto.' style="white-space: nowrap;">'.htmlFormatDate($term->date).'</td>';
    echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="right" '.$goto.' style="white-space: nowrap;">'.htmlDisplayLocalCurrency($obj->idProject,$term->fullAmount,$term->fullAmountLocal).'</td>';
    $sumTermAmount+=$term->fullAmount;
    $sumTermAmountLocal+=$term->fullAmountLocal;
    if ($term->idProviderBill) {
      $bill=new ProviderBill($term->idProviderBill);
      $objStatus=new Status($bill->idStatus);
      echo '<td class="assignData '.((isNewGui() and isset($goto2) and $goto2!='')?'classLinkName':'').'" align="center" '.$goto2.' style="white-space:nowrap; padding:0px !important;color: red;'.(($goto2)?"cursor:pointer;":"").'" >';
      echo '<table style="width:100%;padding:0;marin:0;"><tr>';
      echo '<td class="assignData" style="width:10%;border:0;">#'.htmlEncode($term->idProviderBill).'</td>';
      echo '<td class="assignData" style="width:50%;border:0;">'.htmlEncode($bill->externalReference).'</td>';
      echo '<td class="assignData colorNameData" style="width:40%;border:0;">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</td>';
      echo '</tr></table>';
      echo '</td>';
    } else {
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;"></td>';
    }
    echo '</tr>';
  }
  // Summ for terms
  if (count($list)>0) {
    echo '<tr>';
    echo '<td colspan="'.(($print)?'2':'3').'" class="assignHeader" style="text-align:right">'.i18n('sum').'&nbsp;</td>';
    echo '<td class="assignData" style="font-weight:bold;vertical-align:middle;" align="right">'.htmlDisplayLocalCurrency($obj->idProject,$sumTermAmount,$sumTermAmountLocal).'</td>';
    echo '<td class="assignHeader" >&nbsp;</td>';
    echo '</tr>';
  }
  // echo '</table></td></tr>';
  echo '</table>';
}

function drawAffectationsResourceTeamResourceFromObject($list, $obj, $type, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Affectation';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  $list=array();
  foreach ($listTemp as $aff) {
    $name=SqlList::getNameFromId('ResourceTeam', $aff->idResourceTeam);
    $aff->name=$name;
    $list[$name.'#'.$aff->id]=$aff;
  }
  ksort($list);
//   if ($comboDetail) {
//     return;
//   }
  $canCreate=securityGetAccessRightYesNo('menuAffectation', 'create')=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Resource' or get_class($obj)=='ResourceTeam') {
    $idRess=$obj->id;
  } else {
    $idRess=null;
  }
  
  echo '<td class="assignHeader" style="width:8%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader sortable" style="width:39%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="assignHeader" style="width:13%">'.i18n('colStartDate').'</td>';
  echo '<td class="assignHeader" style="width:13%">'.i18n('colEndDate').'</td>';
  echo '<td class="assignHeader" style="width:12%">'.i18n('colRate').'</td>';
  
  echo '</tr>';
  foreach ($list as $aff) {
    $idleClass=($aff->idle or ($aff->endDate and $aff->endDate<$dateNow=date("Y-m-d")))?' affectationIdleClass':'';
    $res=new Resource($aff->idResource);
    $isResource=($res->id)?true:false;
    $goto="";
    $name=$aff->name;
    $typeAffectable='ResourceTeam';
    if (!$print and securityCheckDisplayMenu(null, $typeAffectable) and securityGetAccessRightYesNo('menu'.$typeAffectable, 'read', '')=="YES") {
      $goto=' onClick="gotoElement(\''.$typeAffectable.'\',\''.htmlEncode($aff->idResourceTeam).'\');" style="cursor: pointer;" ';
    }
    if ($aff->idResource!=$name and pq_trim($name)) {
      echo '<tr>';
      echo '<td class="assignData'.$idleClass.'" align="center">'.htmlEncode($aff->id);
      if ($aff->idle) {
        echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:2px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
      } else {
        echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
      }
      echo '</td>';
      echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left"'.$goto.'>';
      if ($aff->description and !$print) {
        echo '<div style="float:right">'.formatCommentThumb($aff->description).'</div>';
      }
      echo htmlEncode($name);
      echo '</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->startDate).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->endDate).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlEncode($aff->rate).'</td>';
      echo '</tr>';
    }
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawAffectationsFromObject($list, $obj, $type, $refresh=false, $comboDetailAffectation=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  $pluginObjectClass='Affectation';
  $tableObject=$list;
  $lstPluginEvt=Plugin::getEventScripts('list', $pluginObjectClass);
  foreach ($lstPluginEvt as $script) {
    require $script; // execute code
  }
  $listTemp=$tableObject;
  $list=array();
  foreach ($listTemp as $aff) {
    if ($type=='Project') {
      $name=SqlList::getNameFromId($type, $aff->idProject);
    } else {
      $name=SqlList::getNameFromId($type, $aff->idResource);
    }
    if ($aff->idResource==$name and $type=='Resource') {
      $name=SqlList::getNameFromId('Affectable', $aff->idResource);
      $typeAffectable='User';
      if ($aff->idResource!=$name and pq_trim($name)) {
        $name.=" (".i18n('User').")";
      }
    }
    $aff->name=$name;
    $list[$name.'#'.$aff->id]=$aff;
  }
  ksort($list);
  if ($comboDetail and !$comboDetailAffectation) {
    return;
  }
  $canCreate=securityGetAccessRightYesNo('menuAffectation', 'create')=="YES";
  if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
    $canCreate=false;
    $canUpdate=false;
    $canDelete=false;
  }
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  if ($type=='User') {
    $canUpdate=false;
    //$canCreate=false;
    $canDelete=false;
  }
  if ($comboDetail) {
    $canUpdate=false;
    $canDelete=false;
    $canCreate=false;
  }
  echo '<table style="width:100%">';
  echo '<tr><td colspan=2 style="width:100%;"><table style="width:100%;">';
  echo '<tr>';
  if (get_class($obj)=='Project') {
    $idProj=$obj->id;
    $idRess=null;
  } else if (get_class($obj)=='Resource' or get_class($obj)=='ResourceTeam' or get_class($obj)=='Contact' or get_class($obj)=='User' or get_class($obj)=='ResourceMaterial') {
    $idProj=null;
    $idRess=$obj->id;
  } else {
    $idProj=null;
    $idRess=null;
  }
  
  if (!$print) {
    echo '<td class="assignHeader" style="width:15%">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      echo '<a onClick="addAffectation(\''.get_class($obj).'\',\''.$type.'\',\''.$idRess.'\', \''.$idProj.'\',false,false);" title="'.i18n('addAffectation').'" /> '.formatSmallButton('Add').'</a>';
      if (get_class($obj)=='Project') {
        echo '<a onClick="addAffectation(\''.get_class($obj).'\',\''.$type.'\',\''.$idRess.'\', \''.$idProj.'\', true, false);" ';
        echo ' title="'.i18n('addAffectationTeam').'" > '.formatSmallButton('Team', true).'</a>';
        if(Module::isModuleActive('moduleOrganization')){
          echo '<a onClick="addAffectation(\''.get_class($obj).'\',\''.$type.'\',\''.$idRess.'\', \''.$idProj.'\', false, true);" ';
          echo ' title="'.i18n('addAffectationOrganization').'" > '.formatSmallButton('Organization', true).'</a>';
        }
      }
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" style="width:8%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader" style="width:'.(($print)?'35':'20').'%">'.i18n('colId'.$type).'</td>';
  echo '<td class="assignHeader" style="width:18%">'.i18n('colIdProfile').'</td>';
  echo '<td class="assignHeader" style="width:13%">'.i18n('colStartDate').'</td>';
  echo '<td class="assignHeader" style="width:13%">'.i18n('colEndDate').'</td>';
  if ($type=='User' or $type=='Contact' or get_class($obj)=='User' or get_class($obj)=='Contact') echo '<td class="" style="width:12%"></td>';
  else echo '<td class="assignHeader" style="width:12%">'.i18n('colRate').'</td>';
  // echo '<td class="assignHeader" style="width:10%">' . i18n('colIdle'). '</td>';
  
  echo '</tr>';
  $displayed=0;
  foreach ($list as $aff) {
    if($aff->hideAffectation)continue;
    $canUpdate=securityGetAccessRightYesNo('menuAffectation', 'update', $aff)=="YES";
    $canDelete=securityGetAccessRightYesNo('menuAffectation', 'delete', $aff)=="YES";
    if (!(securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES")) {
      $canCreate=false;
      $canUpdate=false;
      $canDelete=false;
    }
    
    if ($obj->idle==1 or $comboDetail) {
      $canUpdate=false;
      $canCreate=false;
      $canDelete=false;
    }
    $idleClass=($aff->idle or ($aff->endDate and $aff->endDate<$dateNow=date("Y-m-d")))?' affectationIdleClass':'';
    $res=new Resource($aff->idResource);
    $isResource=($res->id)?true:false;
    if ($type=='User' or $type=='Contact') {
      $affected=new Affectable($aff->idResource);
      if ($type=='Contact' and $affected->isResource) {
        continue;
      } else if ($type=='User' and ($affected->isResource or $affected->isContact)) {
        continue;
      }
    }
    $goto="";
    $idToShow=$aff->id;
    $classToShow='Affectation';
    if ($type=='Project') {
      $name=$aff->name;
      if (!$print and securityCheckDisplayMenu(null, 'Project') and securityGetAccessRightYesNo('menuProject', 'read', '')=="YES") {
        $goto=' onClick="gotoElement(\'Project\',\''.htmlEncode($aff->idProject).'\');" style="cursor: pointer;" ';
      }
      $idToShow=$aff->idProject;
      $classToShow='Project';
    } else {
      $name=$aff->name;
      $typeAffectable=$type;
      // resourceTeam
      $idToShow=$aff->idResource;
      $classToShow='Resource';
      if ($typeAffectable=='ResourceAll') {
        $resource=new ResourceAll($aff->idResource);
        if ($resource->isResourceTeam) {
          if (securityCheckDisplayMenu(null, 'ResourceTeam') and securityGetAccessRightYesNo('menuResourceTeam', 'read', '')=="YES") {
            $goto=' onClick="gotoElement(\'ResourceTeam\',\''.htmlEncode($aff->idResource).'\');" ';
          }
          $classToShow='ResourceTeam';
        } else {
          if (!$print and $isResource and securityCheckDisplayMenu(null, 'Resource') and securityGetAccessRightYesNo('menuResource', 'read', '')=="YES") {
            $goto=' onClick="gotoElement(\'Resource\',\''.htmlEncode($aff->idResource).'\');" ';
          }
          $classToShow='Resource';
        }
      } else {
        if (!$print and securityCheckDisplayMenu(null, $typeAffectable) and securityGetAccessRightYesNo('menu'.$typeAffectable, 'read', '')=="YES") {
          $goto=' onClick="gotoElement(\''.$typeAffectable.'\',\''.htmlEncode($aff->idResource).'\');"  ';
        }
        $classToShow=$typeAffectable;
      }
    }
    if ($aff->idResource!=$name and pq_trim($name)) {
      // Florent ticket 4009
      if ( $aff->idle != '1'and get_class($obj)=='Resource'){
      echo '<tr>';
      if (!$print) {
        echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space: nowrap;">';
        if ($canUpdate and !$print) {
          echo '  <a onClick="editAffectation('."'".htmlEncode($aff->id)."'".",'".get_class($obj)."'".",'".$type."'".",'".htmlEncode($aff->idResource)."'".",'".htmlEncode($aff->idProject)."'".",'".htmlEncode($aff->rate)."'".",'".htmlEncode($aff->idle)."'".",'".$aff->startDate."'".",'".htmlEncode($aff->endDate)."'".','.(($aff->idProfile !=null )?htmlEncode($aff->idProfile):'null').','. (($aff->idResourceTeam !=null )?htmlEncode($aff->idUser):'null').')" title="'.i18n('editAffectation').'" > '.formatSmallButton('Edit').'</a>';
        }
        if ($canDelete and !$print) {
          echo '  <a onClick="removeAffectation(\''.htmlEncode($aff->id).'\','.(($aff->idResource==getSessionUser()->id)?'1':'0').',\''.$classToShow.'\',\''.$idToShow.'\');" '.'title="'.i18n('removeAffectation').'" > '.formatSmallButton('Remove').'</a>';
        }
        if ($canUpdate and !$print  and !$aff->idle) {
          echo '  <a onClick="replaceAffectation('."'".htmlEncode($aff->id)."'".",'".get_class($obj)."'".",'".$type."'".",'".htmlEncode($aff->idResource)."'".",'".htmlEncode($aff->idProject)."'".",'".htmlEncode($aff->rate)."'".",'".htmlEncode($aff->idle)."'".",'".$aff->startDate."'".",'".htmlEncode($aff->endDate)."'".','.htmlEncode($aff->idProfile).');" '.'title="'.i18n('replaceAffectation').'" > '.formatSmallButton('SwitchUser').'</a>';
        } else {
          if ($aff->idle) {
            echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
          } else {
            echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
          }
        }
        
        echo '</td>';
      }
      echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" '.$goto.'>'.htmlEncode($idToShow).'</td>';
      /*
       * if ($idProj) {
       * echo '<td class="assignData' . $idleClass . '" align="left"' . $goto . '>' . htmlEncode($name) . '</td>';
       * } else {
       * echo '<td class="assignData' . $idleClass . '" align="left"' . $goto . '>' . htmlEncode($name) . '</td>';
       * }
       */
      echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" '.$goto.'>';
      // resourceTeam
      if (isset($typeAffectable)=='ResourceAll') {
        $resource=new ResourceAll($aff->idResource);
        if ($resource->isResourceTeam) {
          echo '<div style="float:right; vertical-align:middle;"> '.formatIcon('Team', 16, i18n('ResourceTeam')).'</div>';
        }
      }
      if ($aff->description and !$print) {
        echo '<div style="float:right">'.formatCommentThumb($aff->description).'</div>';
      }
      echo htmlEncode($name);
      echo '</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" >'.SqlList::getNameFromId('Profile', $aff->idProfile, true).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->startDate).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->endDate).'</td>';
      if ($type=='User' or $type=='Contact' or get_class($obj)=='User' or get_class($obj)=='Contact') echo '<td class="" ></td>';
      else echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlEncode($aff->rate).'</td>';
      // echo '<td class="assignData" align="center"><img src="../view/img/checked' . (($aff->idle)?'OK':'KO') . '.png" /></td>';
      echo '</tr>';
    }elseif(get_class($obj)!='Resource'){
      echo '<tr>';
      if (!$print) {
        echo '<td class="assignData'.$idleClass.'" style="text-align:center;white-space: nowrap;">';
        if ($canUpdate and !$print) {
          echo '  <a onClick="editAffectation('."'".htmlEncode($aff->id)."'".",'".get_class($obj)."'".",'".$type."'".",'".htmlEncode($aff->idResource)."'".",'".htmlEncode($aff->idProject)."'".",'".htmlEncode($aff->rate)."'".",'".htmlEncode($aff->idle)."'".",'".$aff->startDate."'".",'".htmlEncode($aff->endDate)."'".','.(($aff->idProfile !=null )?htmlEncode($aff->idProfile):'null').','.(($res->isResourceTeam !=null )?htmlEncode($res->isResourceTeam):'null').')" title="'.i18n('editAffectation').'" > '.formatSmallButton('Edit').'</a>';
        }
        if ($canDelete and !$print) {
          echo '  <a onClick="removeAffectation(\''.htmlEncode($aff->id).'\','.(($aff->idResource==getSessionUser()->id)?'1':'0').',\''.$classToShow.'\',\''.$idToShow.'\');" '.'title="'.i18n('removeAffectation').'" > '.formatSmallButton('Remove').'</a>';
        }
        if ($canUpdate and !$print  and !$aff->idle) {
          echo '  <a onClick="replaceAffectation('."'".htmlEncode($aff->id)."'".",'".get_class($obj)."'".",'".$type."'".",'".htmlEncode($aff->idResource)."'".",'".htmlEncode($aff->idProject)."'".",'".htmlEncode($aff->rate)."'".",'".htmlEncode($aff->idle)."'".",'".$aff->startDate."'".",'".htmlEncode($aff->endDate)."'".','.htmlEncode($aff->idProfile).');" '.'title="'.i18n('replaceAffectation').'" > '.formatSmallButton('SwitchUser').'</a>';
        } else {
          if ($aff->idle) {
            echo '<a><div style="display:table-cell;width:20px;"><img style="position:relative;top:4px;left:2px" src="css/images/tabClose.gif" '.'title="'.i18n('colIdle').'"/></div></a>';
          } else {
            echo '<a><div style="display:table-cell;width:20px;">&nbsp;</div></a>';
          }
        }
      
        echo '</td>';
      }
      echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" '.$goto.'>'.htmlEncode($idToShow).'</td>';
      /*
       * if ($idProj) {
      * echo '<td class="assignData' . $idleClass . '" align="left"' . $goto . '>' . htmlEncode($name) . '</td>';
      * } else {
      * echo '<td class="assignData' . $idleClass . '" align="left"' . $goto . '>' . htmlEncode($name) . '</td>';
      * }
      */
      echo '<td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left" '.$goto.'>';
      // resourceTeam
      if (isset($typeAffectable)=='ResourceAll') {
        $resource=new ResourceAll($aff->idResource);
        if ($resource->isResourceTeam) {
          echo '<div style="float:right; vertical-align:middle;"> '.formatIcon('Team', 16, i18n('ResourceTeam')).'</div>';
        }
      }
      if ($aff->description and !$print) {
        echo '<div style="float:right">'.formatCommentThumb($aff->description).'</div>';
      }
      echo htmlEncode($name);
      echo '</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" >'.SqlList::getNameFromId('Profile', $aff->idProfile, true).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->startDate).'</td>';
      echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlFormatDate($aff->endDate).'</td>';
      if ($type=='User' or $type=='Contact' or get_class($obj)=='User' or get_class($obj)=='Contact') echo '<td class="" ></td>';
      else echo '<td class="assignData'.$idleClass.'" align="center" style="white-space: nowrap;">'.htmlEncode($aff->rate).'</td>';
      // echo '<td class="assignData" align="center"><img src="../view/img/checked' . (($aff->idle)?'OK':'KO') . '.png" /></td>';
      echo '</tr>';
      
    }
    $displayed++;
  }
  }
  if ($displayed==0 and isNewGui() and $type!='Project') {
    $msg="msgAffectation".(($type=='ResourceAll')?"Resource":$type);
    $colSpan=($print)?6:7;
    if ($type=='User' or $type=='Contact' or get_class($obj)=='User' or get_class($obj)=='Contact') $colSpan--;
    echo '<tr><td class="assignData" colSpan="'.$colSpan.'" style="text-align:center;color:#aaaaaa;font-style:italic;">'.i18n($msg).'</td></tr>';
  }
  echo '</table></td></tr>';
  echo '</table>';
}

function drawTestCaseRunFromObject($list, $obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail, $displayWidth;
  if ($comboDetail) {
    return;
  }
  $class=get_class($obj);
  $otherClass=($class=='TestCase')?'TestSession':'TestCase';
  $nameWidth=($print)?45:25;
  $canCreate=securityGetAccessRightYesNo('menu'.$class, 'update', $obj)=="YES";
  $canUpdate=$canCreate;
  $canDelete=$canCreate;
  if ($obj->idle==1) {
    $canUpdate=false;
    $canCreate=false;
    $canDelete=false;
  }
  usort($list, "TestCaseRun::sort");
  echo '<tr><td colspan="2" style="width:100%;">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print and $class=='TestSession') {
    echo '<td class="assignHeader" style="width:8%;">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      echo '<a onClick="addTestCaseRun();" title="'.i18n('addTestCaseRun').'" > '.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader sortable" colspan="1" style="width:10%;cursor:pointer;" onclick="onColumnHeaderClickedSort(event)" >'.i18n('colSortOrderShort').'</td>';
  echo '<td class="assignHeader sortable" colspan="1" style="width:20%;cursor:pointer;" onclick="onColumnHeaderClickedSort(event)">'.i18n('colType').'</td>';
  echo '<td class="assignHeader sortable" colspan="1" style="width:6%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colId').'</td>';
  echo '<td class="assignHeader sortable" colspan="1" style="width:20%;cursor:pointer;" onclick="onColumnHeaderClickedSort(event)">'.i18n('col'.$otherClass).'</td>';
  // gautier #1716
  echo '<td class="assignHeader " colspan="1" style="width:10%;" >'.i18n('colResult').'</td>';
  echo '<td class="assignHeader " colspan="1" style="width:10%;" >'.i18n('colComment').'</td>';
  //
  if (!$print and $class=='TestSession') {
    echo '<td class="assignHeader" style="width:10%;">'.i18n('colDetail').'</td>';
  }
  echo '<td class="assignHeader sortable" colspan="1" style="width:8%;cursor:pointer;" onclick="onColumnHeaderClickedSort(event)">'.i18n('colIdStatus').'</td>';
  echo '<td class="assignHeader sortable" colspan="1" style="width:8%;cursor:pointer;" onclick="onColumnHeaderClickedSort(event)">'.i18n('colTicket').'</td>';
  echo '</tr>';
  $directEdit=Parameter::getUserParameter('directEditTestCaseRun');
  $directEdit=(! $directEdit or $directEdit=='YES')?true:false;
  //if (count($list)>100) $directEdit=false;
  $arraySt=array();
  foreach ($list as $tcr) {
    if ($otherClass=='TestCase') {
      $tc=new TestCase($tcr->idTestCase, true);
    } else {
      $tc=new TestSession($tcr->idTestSession,true);
    }
    $st=$arraySt[$tcr->idRunStatus]??(new RunStatus($tcr->idRunStatus));
    echo '<tr>';
    if (!$print and $class=='TestSession') {
      echo '<td class="assignData" style="width:10%;text-align:center;">';
      echo '<table style="width:100%"><tr><td style="width:50%;">';
      if ($canUpdate and !$print) {
        echo '  <a onClick="editTestCaseRun(\''.htmlEncode($tcr->id).'\', null, null);" '.'title="'.i18n('editTestCaseRun').'" > '.formatSmallButton('Edit').'</a>';
      }
      if ($canDelete and !$print) {
        echo '  <a onClick="removeTestCaseRun('."'".htmlEncode($tcr->id)."'".",'".htmlEncode($tcr->idTestCase)."'".');" '.'title="'.i18n('removeTestCaseRun').'" > '.formatSmallButton('Remove').'</a>';
      }
      if (!$print) {
        echo '<input type="hidden" id="comment_'.htmlEncode($tcr->id).'" value="'.htmlEncode($tcr->comment, 'none').'"/>';
      }
      echo '</td><td>&nbsp;</td><td style="width:50%;">';
      if ($tcr->idRunStatus==1 or $tcr->idRunStatus==3 or $tcr->idRunStatus==4) {
        echo '  <a onClick="passedTestCaseRun(\''.htmlEncode($tcr->id).'\');" '.'title="'.i18n('passedTestCaseRun').'" /> '.formatSmallButton('Passed',false,true,true).'</a>';
      }
      if ($tcr->idRunStatus==1 or $tcr->idRunStatus==4) {
        echo '  <a onClick="failedTestCaseRun(\''.htmlEncode($tcr->id).'\');" '.'title="'.i18n('failedTestCaseRun').'" > '.formatSmallButton('Failed',false,true,true).'</a>';
      }
      if ($tcr->idRunStatus==1 or $tcr->idRunStatus==3) {
        echo '  <a onClick="blockedTestCaseRun(\''.htmlEncode($tcr->id).'\');" '.'title="'.i18n('blockedTestCaseRun').'" > '.formatSmallButton('Blocked',false,true,true).'</a>';
      }
      echo '</td></tr></table>';
      echo '</td>';
    }
    $goto="";
    if (!$print and securityCheckDisplayMenu(null, 'TestCase') and securityGetAccessRightYesNo('menuTestCase', 'read', $tc)=="YES") {
      $goto=' onClick="gotoElement(\''.$otherClass.'\',\''.htmlEncode($tc->id).'\');" style="cursor: pointer;" ';
    }
    $typeClass='id'.$otherClass.'Type';
    echo '<td class="assignData" align="center" style="width:5%">'.htmlEncode($tcr->sortOrder).'</td>';
    echo '<td class="assignData" align="center" style="width:10%">'.htmlEncode(SqlList::getNameFromId($otherClass.'Type', $tc->$typeClass)).'</td>';
    echo '<td class="assignData" align="center" style="width:5%">#'.htmlEncode($tc->id).'</td>';
    echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="left"'.$goto.' style="width:'.$nameWidth.'%" >'.htmlEncode($tc->name).'</td>';
    // gautier #1716
    $checkImg='savedOk.png';
    $commentWidth='200';
    if (intval($displayWidth)/10<200) $commentWidth=round(intval($displayWidth)/10,0);
    if ($otherClass=='TestSession') $commentWidth=$commentWidth/2;
    echo '<td class="assignData" style="width:10%;font-size:9pt;position:relative;'.(($directEdit)?' cursor:pointer;" id="tdTcrResult_'.$tcr->id.'" onclick="tcrDirectEdit('.$tcr->id.',\'Result\','.$commentWidth.');" ':'"').'>';
//     if (!$print or $tcr->result) {
//       if ($directEdit and !$print) {
//         echo '<textarea dojoType="dijit.form.Textarea" id="tcrResult_'.$tcr->id.'" name="tcrResult_'.$tcr->id.'"
//                 style="float:left;width:100%;min-width:'.$commentWidth.'px;min-height: 25px;font-size: 90%; background:none;display:block;border:none;" maxlength="4000" onchange="saveTcrData('.$tcr->id.',\'Result\');">';
//         echo $tcr->result;
//         echo '</textarea>';
//         echo '<img  id="idImageResult'.$tcr->id.'" src="../view/img/'.$checkImg.'" style="display: none; float:right; top:2px;right:5px; height:16px;"/>';
//       } else {
        echo htmlEncode($tcr->result);
//       }
//     }
    echo '</td>';
    
    //echo '<td class="assignData" style="width:10%">';
    echo '<td class="assignData" style="width:10%;min-width:35px;font-size:9pt;position:relative;'.(($directEdit)?' cursor:pointer;" id="tdTcrComment_'.$tcr->id.'" onclick="tcrDirectEdit('.$tcr->id.',\'Comment\','.$commentWidth.');" ':'"').'>';
//     if (!$print or $tcr->comment) {
//       if ($directEdit and !$print) {
//         echo '<img  id="idImageComment'.$tcr->id.'" src="../view/img/'.$checkImg.'" style="display: none; float:right; top:2px;right:5px; height:16px;"/>';
//         echo '<textarea dojoType="dijit.form.Textarea" id="tcrComment_'.$tcr->id.'" name="tcrComment_'.$tcr->id.'"
//                 style="float:left;width:100%;min-width:'.$commentWidth.'px;min-height: 25px;font-size: 90%; background:none;display:block;border:none;" maxlength="4000" onchange="saveTcrData('.$tcr->id.',\'Comment\');">';
//         echo $tcr->comment;
//         echo '</textarea>';
//       } else {
        echo htmlEncode($tcr->comment);
//       }
//     }
    echo '</td>';
    //
    // echo '</td>';
    if (!$print and $class=='TestSession') {
      echo '<td class="assignData" style="width:10%; " align="center">';
      if (isset($tc->prerequisite) and $tc->prerequisite) {
        echo formatCommentThumb('<b>'.i18n('colPrerequisite').":</b>\n\n".$tc->prerequisite, '../view/css/images/prerequisite.png');
        // echo '<img src="../view/css/images/prerequisite.png" title="' . i18n('colPrerequisite') . ":\n\n" . htmlEncode($tc->prerequisite,'protectQuotes') . '" alt="desc" />';
      }
      if ($tc->description) {
        echo formatCommentThumb('<b>'.i18n('colDescription').":</b>\n\n".$tc->description, '../view/css/images/description.png');
        // echo '<img src="../view/css/images/description.png" title="' . i18n('colDescription') . ":\n\n" . htmlEncode($tc->description) . '" alt="desc" />';
        echo '&nbsp;';
      }
      if ($tc->result) {
        echo formatCommentThumb('<b>'.i18n('colExpectedResult').":</b>\n\n".$tc->result, '../view/css/images/result.png');
        // echo '<img src="../view/css/images/result.png" title="' . i18n('colExpectedResult') . ":\n\n" . htmlEncode($tc->result,'protectQuotes') . '" alt="desc" />';
        echo '&nbsp;';
      }
      echo '</td>';
    }
    echo '<td class="assignData colorNameData" style="width:8%;text-align:left;border-right:0px;">';
    if ($st->id) echo colorNameFormatter(i18n($st->name).'#split#'.$st->color);
    echo '</td>';
    if ($tcr->idTicket && $tcr->idRunStatus == '3'){
      echo '<td class="assignData classLinkName" style="width:7%; border-left:0px; text-align:center; font-size:100%; cursor:pointer" onClick="gotoElement(\'Ticket\', ' . $tcr->idTicket . ')" >';
    }else {
      echo '<td class="assignData" style="width:7%; border-left:0px; text-align:center; font-size:80%;" >';
    }
    if ($tcr->idTicket and $tcr->idRunStatus=='3') {
      echo i18n('Ticket').' #'.$tcr->idTicket;
    } else if ($tcr->statusDateTime) {
      echo ' <i>('.htmlFormatDateTime($tcr->statusDateTime, false).')</i> ';
    }
    if ($tcr->idUser) {
      $user = new User($tcr->idUser);
      echo formatUserThumb($user->id, $user->name, $user->name, 22, 'right; margin:5px;');
    }
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
  echo '</td></tr>';
}
// gautier #providerTerm
function drawProviderTermFromProviderBill($list, $obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $class=get_class($obj);
  
  $canCreate=securityGetAccessRightYesNo('menu'.$class, 'update', $obj)=="YES";
  $canDelete=$canCreate;
  $canUpdate=$canCreate;
  if ($obj->idle==1) {
    $canCreate=false;
    $canDelete=false;
    $canUpdate=false;
  }
  echo '<tr><td colspan="2" style="width:100%;">';
  echo '<table style="width:100%;">';
  echo '<tr>';
  if (!$print and $class=='ProviderBill') {
    $provTerm=new ProviderTerm();
    $billLine=new BillLine();
    $critArray=array("idProviderBill"=>$obj->id);
    $listProvTerm=$provTerm->getSqlElementsFromCriteria($critArray);
    $test=false;
    $y=0;
    foreach ($listProvTerm as $prov) {
      $y=1;
      $critArray2=array("refType"=>"ProviderTerm", "refId"=>$prov->id);
      $cpt=$billLine->countSqlElementsFromCriteria($critArray2);
      if ($cpt!=0) {
        $test=true;
      }
    }
    if (get_class($obj)=='ProviderBill') {
      $idProviderBill=$obj->id;
    } else {
      $idProviderBill=null;
    }
    $isLineProviderTerm='test';
    echo '<td class="assignHeader" style="width:10%;">';
    if ($obj->id!=null and !$print and $canCreate and !$obj->idle) {
      $depType='ProviderTerm';
      if ($obj->totalUntaxedAmount!=0) {
        if ($test!=true or $y==0) {
          $isLineProviderTerm=false;
          echo '<a onClick="addProviderTerm(\''.get_class($obj).'\',\'\',\''.$idProviderBill.'\',\'false\');" title="'.i18n('addProviderTerm').'" > '.formatSmallButton('Add').'</a>';
        }
      }
      echo '<a onClick="addProviderTermFromProviderBill();" title="'.i18n('addDependency'.$depType).'"> '.formatSmallButton('List').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader" colspan="1" style="width:10%">'.i18n('colId').'</td>';
  echo '<td class="assignHeader sortable" colspan="1" style="width:15%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colDate').'</td>';
  echo '<td class="assignHeader '.(($obj->hasCurrency())?' localLabelClass ':'').'" colspan="1" style="width:20%">'.i18n('colAmount').'</td>';
  echo '<td class="assignHeader" colspan="1" style="width:45%">'.i18n('colIdProviderOrder').'</td>';
  echo '</tr>';
  $sumTermAmount=0;
  $sumTermAmountLocal=0;
  foreach ($list as $prT) {
    $goto="";
    $typeAffectable='ProviderOrder';
    if (!$print and securityCheckDisplayMenu(null, $typeAffectable) and securityGetAccessRightYesNo('menu'.$typeAffectable, 'read', '')=="YES") {
      $goto=' onClick="gotoElement(\''.$typeAffectable.'\',\''.htmlEncode($prT->idProviderOrder).'\');" ';
    }
    $goto2="";
    $typeAffectable2='ProviderTerm';
    if (!$print and securityCheckDisplayMenu(null, $typeAffectable2) and securityGetAccessRightYesNo('menu'.$typeAffectable2, 'read', '')=="YES") {
      $goto2=' onClick="gotoElement(\''.$typeAffectable2.'\',\''.htmlEncode($prT->id).'\');" style="cursor: pointer;" ';
    }
    echo '<tr>';
    echo '  <td class="assignData" align="center" style="width:10%;white-space:nowrap">';
    if ($obj->id!=null and $canUpdate and !$print and !$obj->idle and !$prT->idProviderOrder) {
      echo '  <a onClick="editProviderTerm(\''.get_class($obj).'\',\''.$obj->id.'\',\''.$isLineProviderTerm.'\',\''.$prT->id.'\',\''.$prT->name.'\',\''.$prT->date.'\',\''.htmlDisplayNumericWithoutTrailingZeros($prT->taxPct).'\',\''.htmlDisplayNumericWithoutTrailingZeros($obj->discountRate).'\',\''.$prT->untaxedAmount.'\',\''.$prT->taxAmount.'\',\''.$prT->fullAmount.'\',\''.$obj->totalUntaxedAmount.'\');" '.'title="'.i18n('editProviderTerm').'" > '.formatSmallButton('Edit').'</a>';
    }
    if ($canDelete and !$print) {
      if ($prT->idProviderOrder) {
        echo '  <a onClick="removeProviderTermFromBill('."'".htmlEncode($prT->id)."'".');" '.'title="'.i18n('removeProviderTermFromBill').'" > '.formatSmallButton('Mark').'</a>';
      } else { 
        echo '  <a onClick="removeProviderTerm('."'".htmlEncode($prT->id)."'".',true);" '.'title="'.i18n('removeProviderTerm').'" > '.formatSmallButton('Remove').'</a>';
      }
    }
    if ($prT->isPaid) {
      echo i18n('colIsPaid');
    }
    echo '   </td>';
    echo '  <td class="assignData '.((isNewGui() and isset($goto2) and $goto2!='')?'classLinkName':'').'" align="center" '.$goto2.' style="width:10%">#'.htmlEncode($prT->id).'</td>';
    echo '  <td class="assignData '.((isNewGui() and isset($goto2) and $goto2!='')?'classLinkName':'').'" align="center" '.$goto2.' style="width:15%">'.htmlFormatDate($prT->date).'</td>';
    echo '  <td class="assignData '.((isNewGui() and isset($goto2) and $goto2!='')?'classLinkName':'').'" align="right" '.$goto2.' style="width:20%;text-align:right;">'.htmlDisplayLocalCurrency($obj->idProject, $prT->fullAmount, $prT->fullAmountLocal).'</td>';
    $sumTermAmount+=$prT->fullAmount;
    $sumTermAmountLocal+=$prT->fullAmountLocal;
    if ($prT->idProviderOrder) {
      //echo '  <td class="assignData" align="center"'.$goto.' style="width:45%">#'.htmlEncode($prT->idProviderOrder).'</td>';
      $order=new ProviderOrder($prT->idProviderOrder);
      $objStatus=new Status($order->idStatus);
      echo '<td class="assignData " align="center" '.$goto.' style="white-space:nowrap; padding:0px !important;'.(($goto)?'cursor: pointer;':'').'" >';
      echo '<table style="width:100%;padding:0;marin:0;'.((isNewGui())?'height:26px':'').'"><tr>';
      echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:10%;border:0;">#'.htmlEncode($prT->idProviderOrder).'</td>';
      echo '<td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:50%;border:0;">'.htmlEncode($order->name).'</td>';
      echo '<td class="assignData colorNameData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" style="width:40%;border:0;">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</td>';
      echo '</tr></table>';
      echo '</td>';
    } else {
      echo '  <td class="assignData" align="center" style="width:45%"></td>';
    }
    echo '</tr>';
  }
  if (count($list)>0) {
    echo '<tr>';
    echo '<td colspan="'.(($print)?'2':'3').'" class="assignHeader" style="text-align:right">'.i18n('sum').'&nbsp;</td>';
    echo '<td class="assignData" style="font-weight:bold;vertical-align:middle;" align="right">'.htmlDisplayLocalCurrency($obj->idProject,$sumTermAmount,$sumTermAmountLocal).'</td>';
    echo '<td class="assignHeader" >&nbsp;</td>';
    echo '</tr>';
  }
  echo '</table>';
  echo '</td></tr>';
}

function drawTabExpense($obj, $refresh=false) {
  global $cr, $print, $outMode, $user, $browserLocale, $comboDetail;
  if ($comboDetail) {
    return;
  }
  $class=get_class($obj);
  //echo '<tr><td colspan="2" style="width:100%;">';
  $locClass=($obj->hasCurrency())?' localLabelClass ':'';
  echo '<table style="width:100%;">';
  echo '  <tr>';
  echo '    <td class="" style="width:40%"></td>';
  echo '    <td class="assignHeader '.$locClass.'" style="width:20%">'.i18n('colUntaxedAmount').'</td>';
  echo '    <td class="assignHeader '.$locClass.'" style="width:20%">'.i18n('colFullAmount').'</td>';
  echo '    <td class="assignHeader" style="width:20%">'.i18n('colWorkElementCount').'</td>';
  echo '  </tr>';
  
  //damian Tab
  $tabTender = array();
  $tabOrder = array();
  $tabBill = array();
  $tabTerm = array();
  $tabPayment = array();
  
  $clauseStatus=transformListIntoInClause(SqlList::getListWithCrit('tenderStatus', array('isSelected'=>'1')));
  $providerTender = new Tender();
  $listTender = $providerTender->getSqlElementsFromCriteria(null,false,"idProjectExpense=$obj->id ");
  $untaxedAmount = 0;
  $fullAmount = 0;
  $untaxedAmountLocal = 0;
  $fullAmountLocal = 0;
  foreach ($listTender as $tender ){
    $untaxedAmount += $tender->totalUntaxedAmount;
    $fullAmount += $tender->totalFullAmount;
    $untaxedAmountLocal += $tender->totalUntaxedAmountLocal;
    $fullAmountLocal += $tender->totalFullAmountLocal;
    $tabTender[$tender->id]['tender'] = $tender->id;
  }
  echo '  <tr>';
  echo '    <td class="assignHeader">'.i18n('menuTender').'</td>';
  echo '    <td class="assignData" align="right">'.htmlDisplayLocalCurrency($obj->idProject,$untaxedAmount,$untaxedAmountLocal).'</td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject,$fullAmount,$fullAmountLocal).'</td>';
  echo '    <td class="assignData" align="center" >'.count($listTender).'</td>';
  echo '  </tr>';
  $untaxedAmountTerm = 0;
  $fullAmountTerm =0;
  $untaxedAmountTermLocal = 0;
  $fullAmountTermLocal =0;
  $nbTerm = 0;
  $providerOrder = new ProviderOrder();
  $listProviderOrder = $providerOrder->getSqlElementsFromCriteria(array("idProjectExpense"=>$obj->id, "cancelled" => "0"));
  $untaxedAmount = 0;
  $fullAmount = 0;
  $untaxedAmountLocal = 0;
  $fullAmountLocal = 0;
  $clauseProviderBill=transformListIntoInClause(SqlList::getListWithCrit('providerBill', array('idProvider'=>$obj->id)));
  $arrayTerm=array();
  $arrayPayment = array();
  foreach ($listProviderOrder as $order ){
    $untaxedAmount += $order->totalUntaxedAmount;
    $fullAmount += $order->totalFullAmount;
    $untaxedAmountLocal += $order->totalUntaxedAmountLocal;
    $fullAmountLocal += $order->totalFullAmountLocal;
    $tabOrder[$order->id]['bill']= $order->id;
    $providerTerm = new ProviderTerm();
    $listProviderTerm = $providerTerm->getSqlElementsFromCriteria(null, false,'idProviderOrder='.$order->id);
    foreach ($listProviderTerm as $term){
    	$arrayTerm[$term->id]=$term;
    }
  }
  echo '  <tr>';
  echo '    <td class="assignHeader" >'.i18n('menuProviderOrder').'</td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject, $untaxedAmount, $untaxedAmountLocal).'</td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject,$fullAmount, $fullAmountLocal).'</td>';
  echo '    <td class="assignData" align="center" >'.count($listProviderOrder).'</td>';
  echo '  </tr>';
  $providerBill = new ProviderBill();
  $listProviderBill = $providerBill->getSqlElementsFromCriteria(array("idProjectExpense"=>$obj->id));
  $untaxedAmount = 0;
  $fullAmount = 0;
  $fullAmountPayment =0;
  $untaxedAmountLocal = 0;
  $fullAmountLocal = 0;
  $fullAmountPaymentLocal =0;
  $nbPayment = 0;
  foreach ($listProviderBill as $bill ){
    $tabBill[$bill->id]['term']= $bill->id;
    $untaxedAmount += $bill->totalUntaxedAmount;
    $fullAmount += $bill->totalFullAmount;
    $untaxedAmountLocal += $bill->totalUntaxedAmountLocal;
    $fullAmountLocal += $bill->totalFullAmountLocal;
    $payment = new ProviderPayment();
    $listProviderPayment = $payment->getSqlElementsFromCriteria(array("idProviderBill"=>$bill->id));
    foreach ($listProviderPayment as $provPayment){
      $arrayPayment[$provPayment->id]=$provPayment; 
      $nbPayment++;
      $fullAmountPayment += $provPayment->paymentAmount;
      $fullAmountPaymentLocal += $provPayment->paymentAmountLocal;
    }
    $providerTerm = new ProviderTerm();
    $listProviderTerm = $providerTerm->getSqlElementsFromCriteria(array("idProviderBill"=>$bill->id));
    foreach ($listProviderTerm as $term){
      $tabTerm[$term->id]['payment']= $term->id;
      $arrayTerm[$term->id]=$term;
    }
  }

  foreach ($arrayTerm as $term){
    $nbTerm++;
    $untaxedAmountTerm += $term->untaxedAmount;
    $fullAmountTerm += $term->fullAmount;
    $untaxedAmountTermLocal += $term->untaxedAmountLocal;
    $fullAmountTermLocal += $term->fullAmountLocal;
  }
  echo '  <tr>';
  echo '    <td class="assignHeader" >'.i18n('menuProviderBill').'</td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject,$untaxedAmount,$untaxedAmountLocal).'</td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject,$fullAmount,$fullAmountLocal).'</td>';
  echo '    <td class="assignData" align="center" >'.count($listProviderBill).'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td class="assignHeader" >'.i18n('menuProviderTerm').'</td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject,$untaxedAmountTerm,$untaxedAmountTermLocal).'</td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject,$fullAmountTerm,$fullAmountTermLocal).'</td>';
  echo '    <td class="assignData" align="center" >'.$nbTerm.'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td class="assignHeader" >'.i18n('menuProviderPayment').'</td>';
  echo '    <td class="assignHeader" align="right" ></td>';
  echo '    <td class="assignData" align="right" >'.htmlDisplayLocalCurrency($obj->idProject,$fullAmountPayment,$fullAmountPaymentLocal).'</td>';
  echo '    <td class="assignData" align="center" >'.$nbPayment.'</td>';
  echo '  </tr>';
  echo '</table>';
  //echo '</td></tr>';
  $showExpenseProjectDetail=(Parameter::getUserParameter('showExpenseProjectDetail')!='0')?true:false;
  if($showExpenseProjectDetail){
    //echo '<tr><td colspan="2"><br/></td></tr>';
    //damian
    echo '<br/>';
    echo '<table style="width:100%;border:solid #AAAAAA 1px;">';
    echo '  <tr>';
    echo '    <td class="assignHeader" colspan="5" style="width:40%">'.i18n('colName').'</td>';
    echo '    <td class="assignHeader" colspan="1" style="width:10%">'.i18n('colDate').'</td>';
    echo '    <td class="assignHeader" colspan="1" style="width:20%">'.i18n('colExternalReference').'</td>';
    echo '    <td class="assignHeader'.$locClass.'" colspan="1" style="width:10%">'.i18n('colUntaxedAmount').'</td>';
    echo '    <td class="assignHeader'.$locClass.'" colspan="1" style="width:10%">'.i18n('colTaxAmount').'</td>';
    echo '    <td class="assignHeader'.$locClass.'" colspan="1" style="width:10%">'.i18n('colFullAmount').'</td>';
    echo '  </tr>';
   
   //TERM with payment
    foreach ($tabTerm as $id=>$term){
    	unset($tabTerm[$id]['payment']);
    }
    foreach ($arrayPayment as $payment){
     if($payment->idProviderTerm){
      if (!isset($tabTerm[$payment->idProviderTerm])) $tabTerm[$payment->idProviderTerm]=array();
     	$tabTerm[$payment->idProviderTerm][$payment->id]=$payment->id;
     	if (isset($tabTerm[$payment->idProviderTerm]['payment'])) unset($tabTerm[$payment->idProviderTerm]['payment']);
     }else{
      if (!isset($tabBill[$payment->idProviderBill])) $tabBill[$payment->idProviderBill]=array();
     	$tabBill[$payment->idProviderBill][$payment->id]=$payment->id;
     	if (isset($tabBill[$payment->idProviderBill]['payment'])) unset($tabBill[$payment->idProviderBill]['payment']);
     }
    }
   //BILL with TERM
    foreach ($tabBill as $id=>$bill){
    	if (isset($tabBill[$id]['term'])) unset($tabBill[$id]['term']);
    }
    foreach ($arrayTerm as $providerTerm){
      if($providerTerm->idProviderBill){
        if (!isset($tabBill[$providerTerm->idProviderBill])) $tabBill[$providerTerm->idProviderBill]=array();
        if (!isset($tabTerm[$providerTerm->id])) $tabTerm[$providerTerm->id]=array();
        $tabBill[$providerTerm->idProviderBill]['t'.$providerTerm->id]=$tabTerm[$providerTerm->id];
        if (isset($tabBill[$providerTerm->idProviderBill]['term'])) unset($tabBill[$providerTerm->idProviderBill]['term']);
      }else{
        if (!isset($tabOrder[$providerTerm->idProviderOrder])) $tabOrder[$providerTerm->idProviderOrder]=array();
        $tabOrder[$providerTerm->idProviderOrder]['t'.$providerTerm->id] = $providerTerm->id;
        if (isset($tabOrder[$providerTerm->idProviderOrder]['term'])) unset($tabOrder[$providerTerm->idProviderOrder]['term']);
      }
    }
    $link = new Link();
    //ORDER with Bill
    foreach ($listProviderOrder as $order){
    	$listLink = $link->getSqlElementsFromCriteria(array('ref1Type'=>'ProviderBill','ref2Type'=>'ProviderOrder','ref2Id'=>$order->id));
    	foreach ($listLink as $billLinked){
    	  $billExpense = new ProviderBill($billLinked->ref1Id,true);
    	  if($billExpense->idProjectExpense != $obj->id)continue;
    	  if (!isset($tabOrder[$order->id])) $tabOrder[$order->id]=array();
    	  if(isset($tabBill[$billLinked->ref1Id])){
    	    $tabOrder[$order->id][$billLinked->ref1Id]=$tabBill[$billLinked->ref1Id];
    	  }else{
    	    $tabOrder[$order->id][$billLinked->ref1Id]=$billLinked->ref1Id;
    	  }
    		
    	}
    	if (isset($tabOrder[$order->id]['bill'])) unset($tabOrder[$order->id]['bill']);
    }
    
    //TENDER with Order
    foreach ($listTender as $tender){
      $listLink = $link->getSqlElementsFromCriteria(array('ref1Type'=>'ProviderOrder','ref2Type'=>'Tender','ref2Id'=>$tender->id));
      foreach ($listLink as $orderLinked){
        $orderExpense = new ProviderOrder($orderLinked->ref1Id,true);
        if($orderExpense->idProjectExpense != $obj->id)continue;
        if (!isset($tabTender[$tender->id])) $tabTender[$tender->id]=array();
        $tabTender[$tender->id][$orderLinked->ref1Id]=$tabOrder[$orderLinked->ref1Id];
      }
      if (isset($tabTender[$tender->id]['tender'])) unset($tabTender[$tender->id]['tender']);
    }
    
    //DISPLAY
    foreach ($tabTender as $idTender=>$tenders){
      drawProjectExpenseDetailLine('Tender',$idTender, 0);
      foreach ($tenders as $idOrder=>$orders){
        drawProjectExpenseDetailLine('ProviderOrder',$idOrder, 1);
        unset($tabOrder[$idOrder]);
      	foreach ($orders as $id=>$objs){
      	  $object = 'ProviderBill';
      	  if(pq_substr($id, 0,1)== 't'){
      	    $object = 'ProviderTerm';
      	    $id = pq_substr($id,1);
      	  }
      	  drawProjectExpenseDetailLine($object,$id, 2);
      	  unset($tabBill[$id]);
      	  if(is_array($objs) == 1){
        	  foreach ($objs as $idTerm=>$terms){
      	      drawProjectExpenseDetailLine('ProviderTerm',pq_substr($idTerm,1), 3);
        	    unset($tabBill[$id]);
        	    if(is_array($terms) == 1){
          	    foreach ($terms as $idPayment=>$payment){
          	      drawProjectExpenseDetailLine('ProviderPayment', $idPayment, 4);
          	      unset($tabTerm[$idPayment]);
          	    }
        	    }
        	  }
      	  }
      	}
       }
    }

    foreach ($tabOrder as $idOrder=>$orders){
      drawProjectExpenseDetailLine('ProviderOrder',$idOrder, 0);
      foreach ($orders as $id=>$bills){
        if(pq_substr($id, 0,1)== 't'){
        	$object = 'ProviderTerm';
        	$id = pq_substr($id,1);
        	unset($tabOrder[$id]);
        	drawProjectExpenseDetailLine($object,$id, 1);
        }else{
          $object = 'ProviderBill';
          drawProjectExpenseDetailLine($object,$id, 1);
          unset($tabBill[$id]);
          foreach ($bills as $idObj=>$objs){
            if(pq_substr($idObj, 0,1)== 't'){
            	$object = 'ProviderTerm';
            	$id = pq_substr($idObj,1);
            	drawProjectExpenseDetailLine($object,$id, 2);
            	unset($tabBill[$idObj]);
            	if(is_array($objs) == 1){
              	foreach ($objs as $idPayment=>$payment){
              		drawProjectExpenseDetailLine('ProviderPayment',$idPayment, 3);
              	}
            	}
            }else{
              $object = 'ProviderPayment';
              drawProjectExpenseDetailLine($object,$id, 2);
              unset($tabBill[$idObj]);
            }
         }
        }
      }
    }
    
    foreach ($tabBill as $idBill=>$bills){
      drawProjectExpenseDetailLine('ProviderBill',$idBill, 0);
      foreach ($bills as $id=>$objs){
        if(pq_substr($id, 0,1)== 't'){
        	$object = 'ProviderTerm';
        	$id = pq_substr($id,1);
        	drawProjectExpenseDetailLine($object,$id, 1);
        	foreach ($objs as $idPayment=>$payment){
        		drawProjectExpenseDetailLine('ProviderPayment',$idPayment, 2);
        	}
        }else{
          $object = 'ProviderPayment';
          drawProjectExpenseDetailLine($object,$id, 1);
        }
      }
    }
    echo '</table>';
    //echo '</tr></td>';
  }
  
}
function drawProjectExpenseDetailLine($class,$id, $level){
  global $print, $outMode;
	$obj = new $class($id);
	$date = '';
	if(isset($obj->date)){
		$date = htmlFormatDate($obj->date,true);
	}
	if($class == 'ProviderOrder'){
	  $date = htmlFormatDate($obj->sendDate,true);
	}
	if($class == 'Tender'){
  	$date = htmlFormatDate($obj->receptionDateTime,true);
	}
	if($class == 'ProviderPayment'){
	  $date = htmlFormatDate($obj->paymentDate,true);
	}
	$ref = '';
	if(isset($obj->externalReference)){
		$ref = $obj->externalReference;
	}
	$untaxed = '';
	$taxAmount = '';
	$fullAmount = '';
	
	if ($class == 'Tender') {
	  if(isset($obj->untaxedAmount)){
	    $untaxed = htmlDisplayLocalCurrency($obj->idProject, $obj->totalUntaxedAmount, $obj->totalUntaxedAmountLocal);
	  }
	  if(isset($obj->taxAmount)){
	    $taxAmount = htmlDisplayLocalCurrency($obj->idProject, $obj->totalTaxAmount, $obj->totalTaxAmountLocal);
	  }
	  if(isset($obj->fullAmount)){
	    $fullAmount = htmlDisplayLocalCurrency($obj->idProject, $obj->totalFullAmount, $obj->totalFullAmountLocal);
	  }
	} else {
  	if(isset($obj->untaxedAmount)){
  	  $untaxed = htmlDisplayLocalCurrency($obj->idProject, $obj->untaxedAmount, $obj->untaxedAmountLocal);
  	}
  	if(isset($obj->taxAmount)){
  	  $taxAmount = htmlDisplayLocalCurrency($obj->idProject, $obj->taxAmount, $obj->taxAmountLocal);
  	}
  	if(isset($obj->fullAmount)){
  	  $fullAmount = htmlDisplayLocalCurrency($obj->idProject, $obj->fullAmount, $obj->fullAmountLocal);
  	}
  	if(isset($obj->paymentAmount)){
  	  $fullAmount = htmlDisplayLocalCurrency($obj->idProject, $obj->paymentAmount, $obj->paymentAmountLocal);
  	}
	}
	$goto= '';
	if (securityCheckDisplayMenu(null, $class) and securityGetAccessRightYesNo('menu'.$class, 'read', $obj)=="YES") {
		$goto = ' onClick="gotoElement('."'".$class."','".htmlEncode($id)."'".');" ';
	}
	echo '  <tr>';
	for($i=0; $i<$level; $i++){
		echo '<td class="assignData" style="width:3%;height:20px;border-bottom:0px;border-top:0px;border-right:solid 2px;"></td>';
	}
	$width=40-(3*$level);
	echo '    <td class="assignData '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" colspan="'.(5-$level).'"'.$goto.'style="width:'.$width.'%;height:20px;'.(($goto!='')?'cursor:pointer;':'').'">';
	echo '      <table width="100%"><tr><td width="6%" float="right">'.formatIcon(get_class($obj), 16).'</td>';
	echo '      <td width="94%"style="text-aglign:left;">'.i18n(get_class($obj)).' #'.$obj->id.' - '.$obj->name.'</td></tr></table>';
	echo '    </td>';
	echo '    <td class="assignData" align="center" colspan="1" style="width:10%;height:20px;">'.$date.'</td>';
	echo '    <td class="assignData" align="center" colspan="1" style="width:20%;height:20px;">'.$ref.'</td>';
	echo '    <td class="assignData" align="right" colspan="1" style="width:10%;height:20px;">'.$untaxed.'</td>';
	echo '    <td class="assignData" align="right" colspan="1" style="width:10%;height:20px;">'.$taxAmount.'</td>';
	echo '    <td class="assignData" align="right" colspan="1" style="width:10%;height:20px;">'.$fullAmount.'</td>';
	echo '  </tr>';
}

function drawExpenseBudgetDetail($obj) {
	global $print, $user;
	$class=get_class($obj);
	$projectExpense = new ProjectExpense();
	$listProjectExpense = $projectExpense->getSqlElementsFromCriteria(array("idBudgetItem"=>$obj->id));
	//gautier #4346
	$individualExpense = new IndividualExpense();
	$listindividualExpense = $individualExpense->getSqlElementsFromCriteria(array("idBudgetItem"=>$obj->id));
	
	$activityExpense = new ActivityExpense();
	$listactivityExpense = $activityExpense->getSqlElementsFromCriteria(array("idBudgetItem"=>$obj->id));
	
	echo '<table style="width:100%;"><tr><td colspan="2" style="width:100%;">';
	echo '<table style="width:100%;">';
	echo '  <tr>';
	echo '    <td class="assignHeader sortable" colspan="1" style="width:25%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
	echo '    <td class="assignHeader" colspan="1" style="width:10%"></td>';
	echo '    <td class="assignHeader" colspan="1" style="width:10%">'.i18n('colDate').'</td>';
	echo '    <td class="assignHeader" colspan="1" style="width:20%">'.i18n('colUntaxedAmount').'</td>';
	echo '    <td class="assignHeader" colspan="1" style="width:15%">'.i18n('colTaxAmount').'</td>';
	echo '    <td class="assignHeader" colspan="1" style="width:20%">'.i18n('colFullAmount').'</td>';
	echo '  </tr>';
	foreach ($listProjectExpense as $expense){
		drawBudgetExpenseDetailLine(get_class($expense), $expense->id);
	}
	foreach ($listindividualExpense as $expenseIndividual){
	  drawBudgetExpenseDetailLine(get_class($expenseIndividual), $expenseIndividual->id);
	}
	foreach ($listactivityExpense as $expenseActivity){
	  drawBudgetExpenseDetailLine(get_class($expenseActivity), $expenseActivity->id);
	}
	echo '</table>';
	echo '</td>';
	echo '</tr></table>';
}
//Gautier RGPD
function drawFollowupSynthesis($obj) {
  global $print, $user;
  $messageLegalFollowup = new MessageLegalFollowup();
  $listMessageLegalFollowup= $messageLegalFollowup->getSqlElementsFromCriteria(array('idMessageLegal'=>$obj->id));
  $tabOrderByUser = array();
  foreach ($listMessageLegalFollowup as $id=>$mess){
    $tabOrderByUser[SqlList::getNameFromId('Affectable', $mess->idUser).'#'.$id]=$mess;
  }
  ksort($tabOrderByUser);
  echo '<tr><td colspan="2" style="width:100%;">';
  echo '<table style="width:100%;">';
  echo '  <tr>';
  echo '    <td class="assignHeader" colspan="1" style="width:31%">';
  echo '<table style="width:100%;">';  
  echo '  <tr> <td style="width:10%"> ';
  $lstFollowUp = $messageLegalFollowup->countSqlElementsFromCriteria(array('idMessageLegal'=>$obj->id));
  if($lstFollowUp>0){
    echo '<a onClick="removeFollowup('.$obj->id.',true);" '.'title="'.i18n('removeFollowupAll').'" > '.formatSmallButton('Remove').'</a>';
  }
  echo' </td> <td width:90%> '.i18n('colUser').'</td> </tr> </table>';
  echo '    <td class="assignHeader" colspan="1" style="width:23%">'.i18n('colFirstViewDate').'</td>';
  echo '    <td class="assignHeader" colspan="1" style="width:23%">'.i18n('colLastViewDate').'</td>';
  echo '    <td class="assignHeader" colspan="1" style="width:23%">'.i18n('colAcceptedDate').'</td>';
  echo '  </tr>';
  foreach ($tabOrderByUser as $mess){
    echo '  <tr>';
    echo ' <td class="assignData" style="width:31%">';
    echo '<table style="width:100%;">';
    echo '  <tr>';
    echo '  <td style="width:5%">';
    if($mess->acceptedDate){
      echo '<a onClick="removeFollowup('.$mess->id.',false);" '.'title="'.i18n('removeFollowup').'" > '.formatSmallButton('Remove').'</a>';
    }
    echo '</td><td style="width:95%">'.SqlList::getNameFromId('Affectable', $mess->idUser).'</td></tr></table>';
    echo '    <td class="assignData" align="center" style="width:23%">'.htmlFormatDate($mess->firstViewDate).'</td>';
    echo '    <td class="assignData" align="center" style="width:23%">'.htmlFormatDate($mess->lastViewDate).'</td>';
    echo '    <td class="assignData" align="center" style="width:23%"> ';
      echo '<table style="width:100%;">';
      echo '  <tr>';
      echo '  <td align="center" style="width:90%">'.htmlFormatDate($mess->acceptedDate).'</td>';
      if($mess->accepted){
        echo '  <td style="width:10%">'.formatIcon('Submitted',16).'</td>';
      }else{
        echo '  <td style="width:10%">'.formatIcon('Unsubmitted',16).'</td>';
      }
      echo '  </tr>';
      echo '</table>';
    echo '</td>';
    echo '  </tr>';
  }
  echo '</table>';
  echo '</tr>';
}

function drawBudgetExpenseDetailLine($class,$id){
	$obj = new $class($id);
	$plannedDate = '';
	if(isset($obj->expensePlannedDate)){
		$plannedDate = htmlFormatDate($obj->expensePlannedDate);
	}
	$realDate = '';
	if(isset($obj->expenseRealDate)){
		$realDate = htmlFormatDate($obj->expenseRealDate);
	}
	$plannedAmount = '';
	if(isset($obj->plannedAmount)){
		$plannedAmount = htmlDisplayCurrency($obj->plannedAmount);
	}
	$realAmount = '';
	if(isset($obj->realAmount)){
		$realAmount = htmlDisplayCurrency($obj->realAmount);
	}
	$plannedFullAmount = '';
	if(isset($obj->plannedFullAmount)){
		$plannedFullAmount = htmlDisplayCurrency($obj->plannedFullAmount);
	}
	$realFullAmount = '';
	if(isset($obj->realFullAmount)){
		$realFullAmount = htmlDisplayCurrency($obj->realFullAmount);
	}
	$plannedTaxAmount = '';
	if(isset($obj->plannedTaxAmount)){
		$plannedTaxAmount = htmlDisplayCurrency($obj->plannedTaxAmount);
	}
	$realTaxAmount = '';
	if(isset($obj->realTaxAmount)){
		$realTaxAmount = htmlDisplayCurrency($obj->realTaxAmount);
	}

	$goto= '';
	if (securityCheckDisplayMenu(null, $class) and securityGetAccessRightYesNo('menu'.$class, 'read', $obj)=="YES") {
	  $goto = ' onClick="gotoElement('."'".$class."','".htmlEncode($id)."'".');" ';
	}
	$idleClass = ($obj->idle)?' affectationIdleClass':'';
	echo ' <tr>';
	echo '    <td class="assignData'.$idleClass.' '.((isNewGui() and isset($goto) and $goto!='')?'classLinkName':'').'" align="center" rowspan="2"'.$goto.'style="width:25%;height:20px;cursor:pointer;vertical-align:middle">';
	echo '      <table width="100%"><tr><td width="10%" float="right">'.formatIcon(get_class($obj), 16).'</td>';
	echo '      <td width="90%"style="text-aglign:left;padding-left:5px;">#'.$obj->id.' - '.$obj->name.'</td></tr></table>';
	echo '    </td>';
	echo '    <td class="assignData'.$idleClass.'" align="center" style="width:10%;height:20px;font-style:italic;">'.i18n('colPlanned').'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:10%;height:20px;font-style:italic;">'.$plannedDate.'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:20%;height:20px;font-style:italic;">'.$plannedAmount.'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:15%;height:20px;font-style:italic;">'.$plannedTaxAmount.'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:20%;height:20px;font-style:italic;">'.$plannedFullAmount.'</td>';
	echo '</tr>';

	echo ' <tr>';
	echo '    <td class="assignData'.$idleClass.'" align="center" style="width:10%;height:20px;">'.i18n('colReal').'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:10%;height:20px;">'.$realDate.'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:20%;height:20px;">'.$realAmount.'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:15%;height:20px;">'.$realTaxAmount.'</td>';
	echo '    <td class="assignData'.$idleClass.'" align="right" style="width:20%;height:20px;">'.$realFullAmount.'</td>';
	echo '</tr>';
}


function drawOtherVersionFromObject($otherVersion, $obj, $type) {
  global $print;
  usort($otherVersion, "OtherVersion::sort");
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$otherVersion or count($otherVersion)==0) return;
  echo '<table>';
  foreach ($otherVersion as $vers) {
    if ($vers->id) {
      echo '<tr>';
      if ($obj->id and $canUpdate and !$print) {
        echo '<td style="width:20px">';
        echo '<a onClick="removeOtherVersion('."'".htmlEncode($vers->id)."'".', \''.SqlList::getNameFromId('Version', $vers->idVersion).'\''.', \''.htmlEncode($vers->scope).'\''.');" '.'title="'.i18n('otherVersionDelete').'" > '.formatSmallButton('Remove').'</a>';
        echo '</td>';
        echo '<td style="width:20px">';
        echo '<a onClick="swicthOtherVersionToMain('."'".htmlEncode($vers->id)."'".', \''.SqlList::getNameFromId('Version', $vers->idVersion).'\''.', \''.htmlEncode($vers->scope).'\''.');" '.'title="'.i18n('otherVersionSetMain').'" > '.formatSmallButton('Switch').'</a>';
        echo '</td>';
      }
      echo '<td>'.htmlEncode(SqlList::getNameFromId('Version', $vers->idVersion)).'</td>';
      echo '</tr>';
    }
  }
  echo '</table>';
}

function drawOtherClientFromObject($otherClient, $obj) {
  global $print;
  usort($otherClient, "OtherClient::sort");
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (!$otherClient or count($otherClient)==0) return;
  echo '<table>';
  foreach ($otherClient as $client) {
    if ($client->id) {
      echo '<tr>';
      if ($obj->id and $canUpdate and !$print) {
        echo '<td style="width:20px">';
        echo '<a onClick="removeOtherClient('."'".htmlEncode($client->id)."'".', \''.SqlList::getNameFromId('Client', $client->idClient).'\');" '.'title="'.i18n('otherClientDelete').'" > '.formatSmallButton('Remove').'</a>';
        echo '</td>';
        echo '<td style="width:20px">';
        echo '<a onClick="swicthOtherClientToMain('."'".htmlEncode($client->id)."'".', \''.SqlList::getNameFromId('Client', $client->idClient).'\');" '.'title="'.i18n('otherClientSetMain').'" > '.formatSmallButton('Switch').'</a>';
        echo '</td>';
      }
      echo '<td>'.htmlEncode(SqlList::getNameFromId('Client', $client->idClient)).'</td>';
      echo '</tr>';
    }
  }
  echo '</table>';
}

function drawChecklistFromObject($obj,$nbCol=3) {
  global $print, $outMode, $noselect, $collapsedList, $displayWidth, $printWidth, $profile, $comboDetail, $layout;
  if (!$obj or !$obj->id) return; // Don't try and display checklist for non existant objects
  $crit="nameChecklistable='".get_class($obj)."' and idle=0";
  $type='id'.get_class($obj).'Type';
  if (property_exists($obj, $type)) {
    $crit.=' and (idType is null ';
    if ($obj->$type) {
      $crit.=" or idType=".$obj->$type;
    }
    $crit.=')';
  }
  $cd=new ChecklistDefinition();
  $cdList=$cd->getSqlElementsFromCriteria(null, false, $crit);
  if (count($cdList)==0) return; // Don't display checklist if non definition exist for it
  $user=getSessionUser();
  $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'checklist'));
  $list=new ListYesNo($habil->rightAccess);
  $moduleCheckList = Module::isModuleActive('moduleChecklist');
  $displayChecklist=(Parameter::getUserParameter('displayChecklist')!='')?Parameter::getUserParameter('displayChecklist'):'YES';
  if($moduleCheckList and $displayChecklist=='YES'){
    if (!$noselect and $obj->id and $list->code=='YES' or $print) {
      if ($print) {
        echo '<table class="detail" width="'.$printWidth.'px;">';
        echo '<tr><td>';
        include_once "../tool/dynamicDialogChecklist.php";
        echo '</td></tr>';
        echo '</table>';
      } else {
        $titlePane=get_class($obj)."_checklist";
        $selectedTab=null;
        $tabName="Checklist";
        $sessionTabName='detailTab'.get_class($obj);
        $selectedTab=($obj->id)?getSessionValue($sessionTabName,'Description'):'Description';
        $paneName='pane'.$tabName;
        $extName=($comboDetail)?"_detail":'';
        $paneWidth=$displayWidth;
        if ( $layout!='tab' and $nbCol==3) $paneWidth=intval(intval($displayWidth)*2/3).'px';
        echo '<div style="width:'.$paneWidth.';padding:4px;overflow:auto" dojoType="dijit.TitlePane"';
        echo ' title="'.i18n('sectionChecklist').'" ';
        echo (($tabName==$selectedTab)?' selected="true" ':'');
        if($layout!='tab') echo ' open="'.((pq_array_key_exists($titlePane, $collapsedList))?'false':'true').'"';
        echo ' id="'.$titlePane.'"';
        echo ' onHide="saveCollapsed(\''.$titlePane.'\');"';
        echo ' onShow="saveExpanded(\''.$titlePane.'\');"';
        echo '>';
        if($layout=='tab' and !$print){
          echo ' <script type="dojo/method" event="onShow" >';
          echo '   saveDataToSession(\''.$sessionTabName.'\',\''.$tabName.'\');';
          echo '   hideEmptyTabs();';
          echo ' </script>';
        }
        $count=null;
        include_once "../tool/dynamicDialogChecklist.php";
        echo '</div>';
      }
    }
  }
}

function setWidthPct($displayWidth, $print, $printWidth, $obj, $colSpan=null) {
  // scriptLog("setWidthPct(displayWidth=$displayWidth, print=$print, printWidth=$printWidth, obj,colSpan=$colSpan)");
  if (intval($displayWidth)<=0 and intval($printWidth)>0) {
    $displayWidth=(intval($printWidth)-50).'px';
  }
  $nbCol=intval(getNbColMax($displayWidth, $print, $printWidth, $obj));
  if ($print) {
    $nbCol=1;
  }
  $widthPct=round(99/$nbCol)."%";
  if ($nbCol==1) {
    $widthPct=$displayWidth;
  }
  if (pq_substr($displayWidth, -2, 2)=="px" and $nbCol>0) {
    $val=intval($displayWidth);
    $widthPct=floor(($val/$nbCol)-($nbCol+1));
    if (isNewGui()) $widthPct-=15;
    $widthPct.="px";
  }
  if ($colSpan and $nbCol>=$colSpan) {
    $widthPct=$colSpan*pq_substr($widthPct, 0, pq_strlen($widthPct)-2)."px";
  }
  if ($print) {
    $widthPct=round(($printWidth/$nbCol)-2*($nbCol-1))."px";
  }
  return $widthPct;
}

function getNbColMax($displayWidth, $print, $printWidth, $obj) {
  global $nbColMax,$layout;
  $displayWidth=intval($displayWidth);
  if (isNewGui()) {
    if ($displayWidth>1650) {
      $nbColMax=3;
    } else if ($displayWidth>1100) {
      $nbColMax=2;
    } else {
      $nbColMax=1;
    }
  } else {
    if ($displayWidth>1380) {
      $nbColMax=3;
    } else if ($displayWidth>900) {
      $nbColMax=2;
    } else {
      $nbColMax=1;
    }
  }
  if (property_exists($obj, '_nbColMax')) {
    if ($nbColMax>$obj->_nbColMax) {
      $nbColMax=$obj->_nbColMax;
    }
  } else {
    if ($nbColMax>2) {
      $nbColMax=2;
    }
  }
  $paramMax=Parameter::getUserParameter('maxColumns');
  if ($paramMax and $paramMax<$nbColMax) $nbColMax=$paramMax;
  if($layout=='tab' and !$print){
    $nbColMax=1;
  }
  return $nbColMax;
}

function startBuffering() {
  global $reorg,$paneDetail, $leftPane, $rightPane, $extraPane, $bottomPane, $historyPane,$panes, $paneHistory, $paneCheckList, $nbColMax, $section,$arrayGroupe;
  if (!$reorg) return;
  ob_start();
}

function endBuffering($prevSection, $included) {
  //scriptLog("endBuffering($prevSection, $included)");
  global $print, $reorg,$paneDetail, $leftPane, $rightPane, $extraPane, $bottomPane, $historyPane, $panes, $nbColMax, $section, $beforeAllPanes, $arrayGroupe, $layout; 
  $sectionPosition=SqlElement::setSectionPosition();
  $arrayGroupe=$sectionPosition;

  // ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
  // if(Parameter::getGlobalParameter('useOrganizationBudgetElement')==="YES") {
  // $sectionPosition['hierarchicorganizationprojects'] = array('2'=>'bottom', '3'=>'extra');
  // }
  if (!$reorg) return;
  $display=ob_get_clean();
  if (!$prevSection and !$included) {
    $beforeAllPanes=$display;
    return;
  }
  $sectionName=pq_strtolower($prevSection);
  $sectionName=pq_str_replace('_right','',$sectionName);
  //if($layout=='tab' and !$included and ! $print ){
  if($layout=='tab' and ! $print ){
    $groupe='detail';
    if(isset($sectionPosition[$sectionName]['99'])){
      $groupe=$sectionPosition[$sectionName]['99'];
    }
    if (! isset($panes[$groupe])) $panes[$groupe]="";
    $panes[$groupe].=$display;
//     if($groupe=='description'){
//       $paneDescription.=$display;
//     }else if($groupe=='treatment'){
//       $paneTreatment.=$display;
//     }else if($groupe=='dependency'){
//       $paneDependency.=$display;
//     }else if($groupe=='progress'){
//       $paneProgress.=$display;
//     }else if($groupe=='note'){
//       $paneNote.=$display;
//     }else if($groupe=='allocation'){
//       $paneAllocation.=$display;
//     }else if($groupe=='link'){
//       $paneLink.=$display;
//     }else if($groupe=='detail'){
//       $paneDetail.=$display;
//     }else if($groupe=='fichier'){
//       $paneFichier.=$display;
//     }else if($groupe=='configuration'){
//       $paneConfiguration.=$display;
//     }else if($groupe=='checklist') {
//       $paneCheckList.=$display;      
//     }else if ($groupe=='history') {
//       $paneHistory.=$display;     
//     }
  }else{
    if ($nbColMax==1) {
      $leftPane.=$display;
    } else {
      $position='right'; // Not placed sections are located right (default)
      if (isset($sectionPosition[$sectionName]) and isset($sectionPosition[$sectionName][$nbColMax])) {
        $position=$sectionPosition[$sectionName][$nbColMax];
      } else {
        if (pq_substr($sectionName,-5)=='_left') {
          $position='left';
        } else if (pq_substr($sectionName,-5)=='_center') {
          $position='center';
        } 
      }
      if ($position=='extra') {
        $extraPane.=$display;
      } else if ($position=='bottom') {
        $bottomPane.=$display;
      } else if ($position=='right') {
        $rightPane.=$display;
      } else if ($position=='left') {
        $leftPane.=$display;
      } else if ($position=='history') {
        $historyPane.=$display;
      } else {
        traceLog("ERROR at endBuffering() : '$position' is not an expected position");
      }
    }
  }
}

function finalizeBuffering() {
  global $print,$reorg,$paneDetail, $leftPane, $rightPane, $extraPane, $bottomPane, $historyPane, $arrayPanes, $panes, $arrayGroupe, $nbColMax, $section, $beforeAllPanes,$layout;
  if (!$reorg) return;
  if (!$leftPane and $rightPane) {
    $leftPane=$rightPane;
    $rightPane='';
  }
  // $leftPane="";$rightPane="";$extraPane="";$bottomPane="";
  echo $beforeAllPanes;
  echo '<table style="width=100%">';
  $showBorders=false;
  if($layout=='tab' and !$print){ // Attention, panes start with DIV that is not closed
    foreach ($panes as $paneName=>$paneContent) {
      if($paneContent!=''){     
        echo '<tr><td style="width:100%;vertical-align: top;'.(($showBorders)?'border:1px solid green':'').'">'.$paneContent.'</div></div></td></tr>';
      }
    }
//     foreach ($arrayPanes as $paneName) {
//       if(isset($$paneName) and $$paneName){
//         echo '<tr><td style="width:100%;vertical-align: top;'.(($showBorders)?'border:1px solid green':'').'">'.$$paneName.'</div></div></td></tr>';
//       }
//     }  
  }else{
    if ($nbColMax==1) {
      echo '<tr><td style="width:100%;vertical-align: top;'.(($showBorders)?'border:1px solid red':'').'">'.$leftPane.'</td></tr>';
      if ($rightPane) {
        echo '<tr><td style="width:100%;vertical-align: top;'.(($showBorders)?'border:1px solid green':'').'">'.$rightPane.'</td></tr>';
      }
      if ($bottomPane) {
        echo '<tr><td style="width:100%;vertical-align: top;'.(($showBorders)?'border:1px solid yellow':'').'">'.$bottomPane.'</td></tr>';
      }
      if ($extraPane) {
        echo '<tr><td style="width:100%;vertical-align: top;'.(($showBorders)?'border:1px solid blue':'').'">'.$extraPane.'</td></tr>';
      }
      echo '<tr><td colspan="1" style="width:66%;vertical-align: top;'.(($showBorders)?'border:1px solid yellow':'').'">'.$historyPane.'</td></tr>';
    } else if ($nbColMax==2) {
      echo '<tr><td style="width:50%;vertical-align: top;'.(($showBorders)?'border:1px solid red':'').'">'.$leftPane.'</td>'.'<td style="width:50%;vertical-align: top;'.(($showBorders)?'border:1px solid green':'').'">'.$rightPane.'</td>'.'</tr>';
      echo '<tr><td colspan="2" style="width:100%;vertical-align: top;'.(($showBorders)?'border:1px solid yellow':'').'">'.$bottomPane.'</td></tr>';
      if ($extraPane) {
        echo '<tr><td colspan="2" style="vertical-align: top;'.(($showBorders)?'border:1px solid blue':'').'">'.$extraPane.'</td></tr>';
      }
      echo '<tr><td colspan="2" style="width:66%;vertical-align: top;'.(($showBorders)?'border:1px solid yellow':'').'">'.$historyPane.'</td></tr>';
    } else if ($nbColMax==3) {
      echo '<tr style="height:10px">'.'<td style="width:33%;vertical-align: top;'.(($showBorders)?'border:1px solid red':'').'">'.$leftPane.'</td>'.'<td style="width:33%;vertical-align: top;'.(($showBorders)?'border:1px solid green':'').'">'.$rightPane.'</td>'.'<td rowspan="2" style="width:34%;vertical-align: top;'.(($showBorders)?'border:1px solid blue':'').'">'.$extraPane.'</td>'.'</tr>';
      echo '<tr><td colspan="2" style="width:66%;vertical-align: top;'.(($showBorders)?'border:1px solid yellow':'').'">'.$bottomPane.'</td></tr>';
      echo '<tr><td colspan="3" style="width:66%;vertical-align: top;'.(($showBorders)?'border:1px solid yellow':'').'">'.$historyPane.'</td></tr>';
    } else {
      traceLog("ERROR at finalizeBuffering() : '$nbColMax' is not an expected max column count");
    }
 }
  echo '</table>';
  
}

function drawJobDefinitionFromObject($obj, $refresh=false) {
  global $cr, $print, $user, $browserLocale;
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
    $canUpdate=false;
  }
  if (isset($obj->_JobDefinition)) {
    $lines=$obj->_JobDefinition;
  } else {
    $lines=array();
  }
  echo '<input type="hidden" id="JoblistDefinitionIdle" value="'.$obj->idle.'" />';
  echo '<table width="100%">';
  echo '<tr>';
  if (!$print) {
    echo '<th class="noteHeader" style="width:5%">'; // changer le header
    if ($obj->id!=null and !$print and $canUpdate) {
      echo '<a onClick="addJobDefinition('.$obj->id.');"'.' title="'.i18n('addLine').'" class="roundedButtonSmall">'.formatSmallButton('Add').'</a>';
    }
    echo '</th>';
  }
  echo '<th class="noteHeader" style="width: 20%">'.i18n('colSortOrder').'</th>';
  echo '<th class="noteHeader sortable" style="width:'.(($print)?'60':'55').'%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</th>';
  echo '<th class="noteHeader" style="width: 20%">'.i18n('colDaysBeforeWarning').'</th>';
  echo '</tr>';
  
  usort($lines, "JobDefinition::sort");
  foreach ($lines as $line) {
    echo '<tr>';
    if (!$print) {
      echo '<td class="noteData" style="text-align:center;">';
      if ($canUpdate) {
        echo ' <a onClick="editJobDefinition('.$obj->id.','.$line->id.');"'.' title="'.i18n('editLine').'" class="roundedButtonSmall">'.formatSmallButton('Edit').'</a>';
        echo ' <a onClick="removeJobDefinition('.$line->id.');"'.' title="'.i18n('removeLine').'" class="roundedButtonSmall"> '.formatSmallButton('Remove').'</a>';
      }
      echo '</td>';
    }
    echo '<td class="noteData" title="'.$line->title.'">'.$line->sortOrder.'</td>';
    echo '<td class="noteData" title="'.$line->title.'">';
    echo "<table><tr><td>".htmlDisplayCheckbox(0)."&nbsp;</td><td valign='top'>".htmlEncode($line->name)."</td></tr></table>";
    echo '</td>';
    echo '<td class="noteData">';
    echo $line->daysBeforeWarning.' '.i18n('shortDay');
    echo '</td>';
    echo '</tr>';
  }
  echo '<tr>';
  if (!$print) {
    echo '<td class="noteDataClosetable">&nbsp;</td>';
  }
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '<td class="noteDataClosetable">&nbsp;</td>';
  echo '</tr>';
  echo '</table>';
}

function drawJoblistFromObject($obj,$nbCol=3) {
  global $print, $outMode, $noselect, $collapsedList, $displayWidth, $printWidth, $profile, $comboDetail,$layout;
  if (!$obj or !$obj->id) return; // Don't try and display joblist for non existing objects
  $crit="nameChecklistable='".get_class($obj)."' and idle=0";
  $type='id'.get_class($obj).'Type';
  if (property_exists($obj, $type)) {
    $crit.=' and (idType is null ';
    if ($obj->$type) {
      $crit.=" or idType=".$obj->$type;
    }
    $crit.=')';
  }
  $cd=new JoblistDefinition();
  $cdList=$cd->getSqlElementsFromCriteria(null, false, $crit);
  if (count($cdList)==0) return; // Don't display joblist if no definition exists for it
  $user=getSessionUser();
  $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$profile, 'scope'=>'joblist'));
  $list=new ListYesNo($habil->rightAccess);
  if (!$noselect and $obj->id and $list->code=='YES') {
    if ($print) {
      echo '<table class="detail" width="'.$printWidth.'px;">';
      echo '<tr><td>';
      include_once "../tool/dynamicDialogJoblist.php";
      echo '</td></tr>';
      echo '</table>';
    } else {
      $titlePane=get_class($obj)."_joblist";
      $count=null;  
      $selectedTab=null;
      $tabName="Joblist";
      $sessionTabName='detailTab'.get_class($obj);
      $selectedTab=($obj->id)?getSessionValue($sessionTabName,'Description'):'Description';
      $paneName='pane'.$tabName;
      $extName=($comboDetail)?"_detail":'';
      $paneWidth=$displayWidth;
      if ($layout!='tab' and !$print and $nbCol==3) $paneWidth=intval(intval($displayWidth)*2/3).'px';
      echo '<div style="width:'.$paneWidth.';padding:4px;overflow:auto" dojoType="dijit.TitlePane"';
      echo ' title="'.(($layout=='tab')?i18n('tabJoblist'):i18n('Joblist')).'" ';
      echo (($tabName==$selectedTab)?' selected="true" ':'');
      if($layout!='tab') echo ' open="'.((pq_array_key_exists($titlePane, $collapsedList))?'false':'true').'"';
      echo ' id="'.$titlePane.'"';
      echo ' onHide="saveCollapsed(\''.$titlePane.'\');"';
      echo ' onShow="saveExpanded(\''.$titlePane.'\');"';
      echo '>';
      if($layout=='tab'){
        echo ' <script type="dojo/method" event="onShow" >';
        echo '   saveDataToSession(\''.$sessionTabName.'\',\''.$tabName.'\');';
        echo '   hideEmptyTabs();';
        echo ' </script>';
      }
      include_once "../tool/dynamicDialogJoblist.php";
      echo '</div>';
    }
  }
}

function drawPokerVote($obj){
  global $print;
  if($print)return;
  if (!$obj->id or !$obj->handled){
    echo '<div class="container" style="height:200px"><div class="labelMessageEmptyArea" style="top:50px">'.i18n('emptyPokerVote').'</div></div>';
    return;
  }
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
  	$canUpdate=false;
  }
  $user = getSessionUser();
  $pokerItem = new PokerItem();
  $critArray = array('idPokerSession'=>$obj->id, 'isOpen'=>'1');
  $itemList = $pokerItem->getSqlElementsFromCriteria($critArray);
  $pokerItemList = SqlList::getListWithCrit('PokerItem', $critArray, 'id');
  $list = implode(',', $pokerItemList);
  if($itemList)$pokerItem = $itemList[0];
  $pokerComplexity = new PokerComplexity();
  $pokerComplexityList = $pokerComplexity->getSqlElementsFromCriteria(array('idle'=>'0'), null, null, "sortOrder ASC");
  
  $pos = array_search("$pokerItem->id", $itemList);
  if($pos < 0)$pos=0;
  $previous = ($pos>0)?true:false;
  $lenght = count($itemList)-1;
  if($lenght < 0)$lenght=0;
  $next = ($pos<$lenght)?true:false;
  $pos +=1;
  
  $pokerMember = new PokerResource();
  $pokerMember = $pokerMember->getSingleSqlElementFromCriteria('PokerResource', array('idPokerSession'=>$obj->id, 'idResource'=>$user->id));
  $pokerMemberList = $pokerMember->getSqlElementsFromCriteria(array('idPokerSession'=>$obj->id));
  $pokerVote = new PokerVote();
  $pokerVote = $pokerVote->getSingleSqlElementFromCriteria('PokerVote', array('idPokerSession'=>$obj->id, 'idResource'=>$user->id, 'idPokerItem'=>$pokerItem->id));
  $pokerVoteList = SqlList::getListWithCrit('pokerVote', array('idPokerSession'=>$obj->id, 'idPokerItem'=>$pokerItem->id), 'value');
  $lowVote = 0;
  $highVote = 0;
  if(count($pokerVoteList) > 0){
    sort($pokerVoteList);
    if(isset($pokerVoteList[0])){
      $lowVote = $pokerVoteList[0];
      $lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$lowVote));
      if($lowCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$lowVote=false;
      if(isset($pokerVoteList[count($pokerVoteList)-1])){
      	$highVote = $pokerVoteList[count($pokerVoteList)-1];
      	$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$highVote));
      	if($highCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$highVote=false;
      }
    }else if (isset($pokerVoteList[1])){
      unset($pokerVoteList[0]);
      $lowVote = $pokerVoteList[1];
      $lowCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$lowVote));
      if($lowCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$lowVote=false;
      if(isset($pokerVoteList[count($pokerVoteList)])){
      	$highVote = $pokerVoteList[count($pokerVoteList)];
      	$highCount = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idPokerItem'=>$pokerItem->id, 'value'=>$highVote));
      	if($highCount > (count($pokerMemberList)/2) and count($pokerMemberList) > 2)$highVote=false;
      }
    }
  }
  if($pokerItem->id){
    $refObj = new $pokerItem->refType($pokerItem->refId);
    $nbVoted = $pokerVote->countSqlElementsFromCriteria(array('idPokerSession'=>$obj->id,'idResource'=>$user->id));
    $nbItem = count($itemList);
    $nbLeft = ($nbItem-$nbVoted);
    if($nbLeft < 0)$nbLeft=0;
    echo '<div id="pokerVoteDiv" dojoType="dijit.layout.ContentPane" region="center" align="center" style="width: 100%;">';
    echo '<table style="width: 100%;"><tr><td>';
    echo '<div id="pokerVoteDescription" dojoType="dijit.layout.ContentPane" region="center" align="center" style="width: 100%;overflow:hidden"><table style="width: 100%;"><tr><td>';
    echo '<div style="width: 100%;padding-bottom: 20px;" align="center">';
    echo '  <div style="float:left">';
    echo '    <div style="padding-bottom: 5px;font-size: 9pt;">'.i18n('nbPokerVote').'</div>';
    echo '    <div style="font-size: 15pt;color: var(--color-dark);">'.$nbLeft.'</div>';
    echo '  </div>';
    $disabled='';
    if(!$previous){
    	$disabled = 'disabled';
    }
    echo ' <div id="previousItem" dojoType="dijit.form.Button" class="roundedVisibleButton" style="vertical-align: middle;width: 140px;height: 24px;padding-bottom: 5px;margin-right: 10px;margin-top: 8px;" '.$disabled.'>';
    echo '   <div class="dijitButtonIcon dijitButtonIconPrevious" style="float:left;padding-top: 6px;"></div><span style="padding-left: 15px;">' . i18n('previousItem') . '</span>';
    echo '   <script type="dojo/connect" event="onClick" args="evt">';
    echo '     pokerItemNav('.$obj->id.','.$pokerItem->id.',\''.$list.'\', \'previous\');';
    echo '   </script>';
    echo ' </div>';
    $disabled='';
    if(!$next){
    	$disabled = 'disabled';
    }
    echo ' <div id="nextItem" dojoType="dijit.form.Button" style="padding-bottom: 5px;vertical-align: middle;width: 140px;height: 24px;margin-left: 10px;margin-top: 8px;" class="roundedVisibleButton" '.$disabled.'>';
    echo '   <span style="padding-right: 15px;">' . i18n('nextItem') . '</span><div class="dijitButtonIcon dijitButtonIconNext" style="float:right;padding-top: 6px;"></div>';
    echo '   <script type="dojo/connect" event="onClick" args="evt">';
    echo '     pokerItemNav('.$obj->id.','.$pokerItem->id.',\''.$list.'\', \'next\');';
    echo '   </script>';
    echo ' </div>';
    echo '  <div id="refreshPokerDiv" dojoType="dijit.form.Button" showlabel="false" style="float:right;"';
    echo '  title="'.i18n('refreshPokerVote').'" iconClass="iconRefresh iconSize32 imageColorNewGui" class="detailButton">';
    echo   '  <script type="dojo/connect" event="onClick" args="evt">';
    echo   '    pokerItemNav('.$obj->id.','.$pokerItem->id.',\''.$list.'\', null);';
    echo   '  </script>';
    echo '  </div>';
    echo '</div>';
    echo '<div style="width: 100%;padding-top:15px">';
    echo '  <table style="width: 100%;"><tr>';
    echo '    <td class="assignHeader" style="width:5%">';
    echo '      <div title="'.i18n('showItem').'" style="width:100%;" class="roundedButton roundedIconButton generalColClass">';
    echo '        <input type="hidden" id="refId'.get_class($refObj).'" name="refId'.get_class($refObj).'" value="'.$refObj->id.'"/>';
    echo '        <div style="width:100%;" class="imageColorNewGui iconToolbarView" onclick="showDetail(\'refId'.get_class($refObj).'\', 0, \''.get_class($refObj).'\', false,null, false);"></div>';
    echo '      </div>';
    echo '    </td>';
    echo '    <td class="assignHeader" style="width:30%">'.i18n('colReference').'</td>';
    echo '    <td class="assignHeader" style="width:40%">'.i18n('colName').'</td>';
    echo '    <td class="assignHeader" style="width:25%">'.i18n('colComment').'</td>';
    echo '  </tr><tr>';
    echo '<td class="noteData" style="width:5%;vertical-align: middle;" align="center">'.$pos.'/'.count($itemList).'</td>';
    echo '<td class="noteData" style="width:30%; text-align: left;height:22px;vertical-align: middle;">';
    $gotoE=' onClick="gotoElement('."'".get_class($refObj)."','".htmlEncode($refObj->id)."'".');" style="cursor:pointer" class="classLinkName"';
    echo '  <table><tr><td style="padding-right:10px">'.formatIcon(get_class($refObj), 22).'</td><td'.$gotoE.'>'.i18n(get_class($refObj)).' #'.htmlEncode($refObj->id).'</td></tr></table></td>';
    echo '<td class="noteData" style="width:40%; text-align: left;height:22px;">'.htmlEncode($refObj->name).'</td>';
    echo '<td class="noteData" style="width:25%; text-align: left;height:22px;">'.htmlEncode($pokerItem->comment).'</td>';
    echo '  </tr></table>';
    echo '</div>';
    echo '<div id="pokerVoteList" dojoType="dijit.layout.ContentPane" region="center" style="width: 100%;padding-top: 20px;padding-left: 10px;">';
    echo '<div style="width: 95%;padding-bottom: 20px;" align="right">';
    if($canUpdate and $obj->idResource == $user->id and !$pokerItem->value){
        if(count($pokerVoteList) > 0){
          $name = i18n('flipPokerVote');
          if($pokerItem->flipped){
          	$name = i18n('resetPokerVote');
          }
          echo ' <button id="flipPokerVote" dojoType="dijit.form.Button" style="vertical-align: middle;" class="roundedVisibleButton">';
          $icon = '&curarr;&nbsp;';
          if($pokerItem->flipped)$icon='&orarr;&nbsp;';
          echo '   <span style="padding: 0px 5px 0px 5px;">'.$icon . $name . '</span>';
          echo '   <script type="dojo/connect" event="onClick" args="evt">';
          if(!$pokerItem->flipped){
          	echo '     flipPokerVote('.$obj->id.','.$pokerItem->id.',\''.$list.'\');';
          }else{
          	echo '     resetPokerVote('.$obj->id.','.$pokerItem->id.',\''.$list.'\');';
          }
          echo '   </script>';
          echo ' </button>';
        }
        if($pokerItem->flipped){
        	echo ' <button id="closePokerVote" dojoType="dijit.form.Button" style="vertical-align: middle;margin-right: 10px;" class="roundedVisibleButton">';
        	echo '   <span style="padding: 0px 5px 0px 5px;">' . i18n('validatePokerVote') . '</span>';
        	echo '   <script type="dojo/connect" event="onClick" args="evt">';
        	echo '     closePokerItemVote('.$pokerItem->id.','.$obj->id.', false);';
        	echo '   </script>';
        	echo ' </button>';
    	}
    }
    echo '</div>';
    foreach ($pokerMemberList as $member){
      echo '<div style="float:left;padding: 0px 5px 10px 5px;"><table><tr>';
      echo '<td>';
      $pVote = PokerVote::getSingleSqlElementFromCriteria('PokerVote', array('idPokerItem'=>$pokerItem->id, 'idPokerSession'=>$obj->id, 'idResource'=>$member->idResource));
      $pComplex = PokerComplexity::getSingleSqlElementFromCriteria('PokerComplexity', array('value'=>$pVote->value));
      $style='';
      $color='white';
      if($lowVote == $pComplex->value and count($pokerVoteList) > 1){
      	$color='#84ea9b';
      }else if($highVote == $pComplex->value and count($pokerVoteList) > 1){
      	$color='#ff6565';
      }
      if($pVote->id and $pComplex->id and $pokerItem->flipped){
        $style='background-color:'.$pComplex->color.';color:'.$color;
      }else if($pVote->id and !$pokerItem->flipped){
        $style='background-color:var(--color-medium);';
      }
      echo '<div class="card-on-table">';
        echo '<div class="card-wrapper-mini">';
          echo '<div class="card-container-mini">';
            echo '<div class="card-mini card-face" style="'.$style.'" align="center">';
              if($pVote->id and $pokerItem->flipped){
                echo '<div class="text-center player-vote-mini"><span>'.$pComplex->name.'</span></div>';
              }else if($pVote->id and !$pokerItem->flipped){
                echo '<div style="position: absolute;top: 20px;left: 8px;"><img style="height:32px;width:32px;" src="img/logoSmallWhite.png"></div>';
              }
            echo '</div>';
          echo '</div>';
        echo '</div>';
      echo '</div>';
      echo '</td>';
      echo '<td><div style="padding-left: 10px;width: 55px;">'.SqlList::getNameFromId('Affectable', $member->idResource).'</div></td>';
      echo '</tr></table></div>';
    }
    echo '</div>';
    echo '</div></td></tr>';
    echo '<tr><td><br></td></tr>';
    echo '<tr><td>';
    echo '<div id="pokerVoteResult" dojoType="dijit.layout.ContentPane" region="center" align="center" style="width: 100%;height: 100%;padding: 10px 0px 10px 0px;overflow: hidden;">';
    if($pokerMember->id and !$obj->done){
        foreach ($pokerComplexityList as $pokerComplexity){
          $selected = ($pokerVote->id and $pokerVote->value == $pokerComplexity->value)?'selected':'';
          $onclick=(!$pokerItem->flipped)?'voteToPokerItem('.$obj->id.','.$pokerItem->id.',\''.$list.'\', '.$pokerComplexity->value.');':'';
          if($selected)$onclick='';
          $style='background-color:'.$pokerComplexity->color.';';
          if($selected)$style='background-color:white;color:'.$pokerComplexity->color.';';
          echo '<div class="card-in-hand '.$selected.'" onclick="'.$onclick.'">';
            echo '<div class="card-wrapper">';
              echo '<div class="card-container">
                      <div class="card card-face" style="'.$style.'">
                          <div class="small-card-id"><span>'.$pokerComplexity->value.'</span></div>
                          <div class="text-center player-vote"><span>'.$pokerComplexity->name.'</span></div>
                      </div>
                    </div>';
            echo '</div>';
          echo '</div>';
      }
    }
    echo '</table>';
    echo '</div>';
    echo '</table>';
    echo '</div>';
  }else{
    echo '<div class="container" style="height:200px"><div class="labelMessageEmptyArea" style="top:50px">'.i18n('emptyPokerVote').'</div></div>';
  }
}

function drawPokerItem($obj){
  global $print;
  $canUpdate=securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) {
  	$canUpdate=false;
  }
  $pokerItem = new PokerItem();
  $critArray = array('idPokerSession'=>$obj->id);
  $itemList = $pokerItem->getSqlElementsFromCriteria($critArray);
  $pokerItemList = SqlList::getListWithCrit('PokerItem', $critArray, 'id');
  $list = implode(',', $pokerItemList);
  echo '<table style="width: 100%;"><tr>';
  if (!$print) {
  	echo '<td class="assignHeader smallButtonsGroup" style="width:10%">';
  	if ($obj->id!=null and !$print and $canUpdate) {
  		echo '<a onClick="addPokerItem(null, null, '.$obj->id.');" title="'.i18n('addPokerItem').'" >'.formatSmallButton('Add').'</a>';
  	}
  	echo '</td>';
  }
  echo '<td class="assignHeader sortable" style="width:30%;cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="assignHeader" style="width:30%">'.i18n('colReference').'</td>';
  echo '<td class="assignHeader" style="width:30%">'.i18n('colValue').'</td>';
  $globalOpenItem = '';
  if($itemList and !$print){
    $globalOpenItem = '<button id="globalOpenPokerVote" dojoType="dijit.form.Button" style="min-width:130px;vertical-align: middle;" class="roundedVisibleButton">';
    $globalOpenItem .= '   <span style="padding: 0px 5px 0px 5px;">' . i18n('globalOpenPokerVote') . '</span>';
    $globalOpenItem .= '   <script type="dojo/connect" event="onClick" args="evt">';
    $globalOpenItem .= '     startPokerSession('.$obj->id.');';
    $globalOpenItem .= '   </script>';
    $globalOpenItem .= ' </button>';
  }
  echo '<td>'.$globalOpenItem.'</td>';
  echo '</tr>';
  foreach ($itemList as $item){
    echo '<tr style="">';
    echo '<td class="noteData smallButtonsGroup" style="width:10%;height:22px;">';
    if(!$print)echo ' <a onClick="editPokerItem('.htmlEncode($item->id).', \'\', \'\');" title="'.i18n('editPokerItem').'" > '.formatSmallButton('Edit').'</a>';
    if (!$print and $canUpdate) {
    	echo ' <a onClick="removePokerItem('.htmlEncode($item->id).', \'\', \'\');" title="'.i18n('removePokerItem').'" > '.formatSmallButton('Remove').'</a>';
    	if($item->isOpen){
          echo ' <a onClick="gotoPokerItem('.$obj->id.','.$item->id.',\''.$list.'\');" title="'.i18n('gotoPokerItem').'" >'.formatSmallButton('Goto', true).'</a>';
    	}
    }
    echo '</td>';
    $refObj = new $item->refType($item->refId);
    $gotoE=' onClick="gotoElement('."'".get_class($refObj)."','".htmlEncode($refObj->id)."'".');" style="cursor:pointer" class="noteData classLinkName"';
    echo '<td style="width:30%; text-align: left;height:22px;" '.$gotoE.'>'.htmlEncode(get_class($refObj)).' #'.htmlEncode($refObj->id).' '.formatCommentThumb($item->comment).'</td>';
    echo '<td class="noteData" style="width:30%; text-align: left;height:22px;">'.htmlEncode($refObj->name).'</td>';
    echo '<td class="noteData" style="width:30%; text-align: center;height:22px;">'.htmlEncode($item->value).'</td>';
    echo '<td style="">';
    if(!$item->isOpen and !$item->value and !$print){
      echo ' <button id="openPokerVote' . $item->id . '" dojoType="dijit.form.Button" style="min-width:130px;vertical-align: middle;" class="roundedVisibleButton">';
      echo '   <span style="padding: 0px 5px 0px 5px;">' . i18n('openPokerVote') . '</span>';
      echo '   <script type="dojo/connect" event="onClick" args="evt">';
      echo '     openPokerItemVote('.$item->id.','.$obj->id.');';
      echo '   </script>';
      echo ' </button>';
	}else if($item->isOpen and !$item->value and $item->flipped and !$print){
      echo ' <button id="openPokerVote' . $item->id . '" dojoType="dijit.form.Button" style="min-width:130px;vertical-align: middle;" class="roundedVisibleButton">';
      echo '   <span style="padding: 0px 5px 0px 5px;">' . i18n('closePokerVote') . '</span>';
      echo '   <script type="dojo/connect" event="onClick" args="evt">';
      echo '     closePokerItemVote('.$item->id.','.$obj->id.', true);';
      echo '   </script>';
      echo ' </button>';
    }
    echo '</td>';
    echo '</tr>';
  }
  echo '</table>';
}

function drawUserStoryFromObject($obj){
  global $print, $comboDetail;
  if(!$obj->id) return;
  
  $canUpdate = securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=="YES";
  if ($obj->idle==1) $canUpdate=false;
  
  $userStory = new UserStory();
  $objectClass = get_class($obj);
  $critArray = array('id'.$objectClass=>$obj->id);
  $itemList = $userStory->getSqlElementsFromCriteria($critArray);
  
  echo '<table style="width:100%;table-layout:fixed;"><colgroup>';
  
  if (!$print and !$comboDetail) {
    echo '<col style="width:10%;">'; // name
    echo '<col style="width:35%;">'; // nom
    echo '<col style="width:15%;">'; // story points
    echo '<col style="width:15%;">'; // business value
    echo '<col style="width:25%;">'; // status
  } else {
    echo '<col style="width:40%;">'; // name
    echo '<col style="width:20%;">'; // story points
    echo '<col style="width:20%;">'; // business value
    echo '<col style="width:20%;">'; // status
  }
  echo '</colgroup>';
  
  echo '<tr>';
  if (!$print and !$comboDetail) {
    echo '<td class="assignHeader smallButtonsGroup">';
    if ($obj->id!=null && $canUpdate) {
      echo '<a onClick="addUserStory(\''.$objectClass.'\', '.$obj->id.');" title="'.i18n('addUserStory').'" >'.formatSmallButton('Add').'</a>';
    }
    echo '</td>';
  }
  echo '<td class="assignHeader sortable" style="cursor:pointer" onclick="onColumnHeaderClickedSort(event)">'.i18n('colName').'</td>';
  echo '<td class="assignHeader">'.i18n('colStoryPoints').'</td>';
  echo '<td class="assignHeader">'.i18n('colBusinessValue').'</td>';
  echo '<td class="assignHeader">'.i18n('colIdStatus').'</td>';
  echo '</tr>';
  
  foreach ($itemList as $userStory){
    echo '<tr>';
    
    if (!$print and !$comboDetail) {
      echo '<td class="noteData smallButtonsGroup" style="height:22px;">';
      if ($canUpdate) {
        echo ' <a onClick="removeUserStory(\''.$objectClass.'\','.htmlEncode($userStory->id).');" title="'.i18n('removePokerItem').'" > '.formatSmallButton('Remove').'</a>';
        echo ' <a onClick="gotoElement('."'".get_class($userStory)."','".htmlEncode($userStory->id)."'".');" title="'.i18n('gotoTo').'" >'.formatSmallButton('Goto', true).'</a>';
      }
      echo '</td>';
    }
    
    $goto="";
    $canGoto=(securityCheckDisplayMenu(null, get_class($userStory)) and securityGetAccessRightYesNo('menu'.get_class($userStory), 'read', $userStory)=="YES");
    if (!$print and !$comboDetail and $canGoto) {
      $goto=' onClick="hideTooltip(this);gotoElement('."'".get_class($userStory)."','".htmlEncode($userStory->id)."'".');" ';
    }
    
    $projectDep = new Project();
    if (property_exists($userStory, 'idProject')) $projectDep = new Project($userStory->idProject);
    
    $planningMode = new PlanningMode();
    $pe = get_class($userStory).'PlanningElement';
    if (property_exists(get_class($userStory),$pe)){
      $objectInfo = json_encode($userStory->$pe);
      $planningMode = new PlanningMode($userStory->$pe->idPlanningMode);
      if ($userStory->$pe->refType == 'Project') $projectDep = $userStory;
    } else {
      $objectInfo = json_encode($userStory);
    }
    
    $res = new Resource();
    $productVersion = new ProductVersion();
    $type= new Type();
    $idType = 'id'.get_class($userStory).'Type';
    if (property_exists($userStory, $idType)) $type= new Type($userStory->$idType);
    if (property_exists($userStory, 'idResource')) $res = new Resource ($userStory->idResource);
    if (property_exists($userStory, 'idTargetProductVersion')) $productVersion = new ProductVersion($userStory->idTargetProductVersion);
    
    echo '<td class="linkData classLinkName" '.$goto.'
      onmouseout="hideTooltip(this)"
      onmouseenter="showTooltip(this, ' . htmlEncode(json_encode($projectDep)) . ', ' . htmlEncode($objectInfo) . ', ' . htmlEncode(json_encode($res)) . ', ' . htmlEncode(json_encode($productVersion)) . ', ' . htmlEncode(json_encode($type)) . ', ' . htmlEncode(json_encode($planningMode)) . ')"
      onmouseleave="hideTooltip(this)"
      onfocusout="hideTooltip(this)">'.htmlEncode($userStory->name).'</td>';
    
    echo '<td class="noteData" style="text-align:right;">'.htmlEncode($userStory->storyPoints).'</td>';
    echo '<td class="noteData" style="text-align:right;">'.htmlEncode($userStory->businessValue).'</td>';
    
    $objStatus=new Status($userStory->idStatus);
    echo '<td class="linkData colorNameData">'.colorNameFormatter($objStatus->name."#split#".$objStatus->color).'</td>';
    
    echo '</tr>';
  }
  
  echo '</table>';
}
?>
