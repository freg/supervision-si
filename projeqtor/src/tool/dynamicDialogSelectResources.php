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
 * List of items subscribed by a user.
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
 
$type = RequestHandler::getValue('type');
$project = RequestHandler::getId('idProject');
$values = RequestHandler::getValue('list');
$target = RequestHandler::getValue('target');
if($type == 'resource'){
  
}elseif ($type=='user'){
  
}elseif ($type=='contact'){
  
}else{
  $user=getSessionUser();
  $res=new Affectable();
  $scope=Affectable::getVisibilityScope();
  $crit="idle=0";
  $lstRes=$res->getSqlElementsFromCriteria(null,false,$crit,' UPPER(fullName) asc, UPPER(name) asc ',true);
}
$lstSub= array();
if($values){
  $idAffectable = pq_explode(";", $values);
  $index = 0;
  foreach ($idAffectable as $myId){
    $resA = new Affectable($myId);
    $lstSub[$index] = $resA;
    $index++;
  }
}
if (sessionValueExists('screenHeight') and getSessionValue('screenHeight')) {
	$showHeight = round(getSessionValue('screenHeight') * 0.4)."px";
} else {
	$showHeight="100%";
}

foreach ($lstSub as $idSub=>$sub) {
  if (isset($lstRes['#'.$sub->id])) {
    $lstSub['#'.$sub->id]=$lstRes['#'.$sub->id];
    unset($lstRes['#'.$sub->id]);
  } else {
    $lstSub['#'.$sub->id]=new Affectable($sub->id);
  }
  unset($lstSub[$idSub]);
}


$profile=getSessionUser()->idProfile;
$crit=array('scope' => 'subscription','idProfile' => $profile);
$habilitation=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
$scope=new AccessScopeSpecific($habilitation->rightAccess, true);
if (! $scope->accessCode or $scope->accessCode == 'NO') {
	$lstRes=array(); // No access to this feature ;)
	$lstSub=array(); // No access to this feature ;)
} else if ($scope->accessCode == 'ALL') {
	// OK
} else if ($scope->accessCode == 'OWN')  {
	$lstRes=array(); // Not for other, should not come here
	$lstSub=array(); // Not for other, should not come here
} else if ($scope->accessCode == 'PRO') {
	$stockRes=$lstRes;
	$lstRes=array();
	$crit='idProject in ' . transformListIntoInClause($user->getAffectedProjects(true));
	$aff=new Affectation(); 
	$lstAff=$aff->getSqlElementsFromCriteria(null, false, $crit, null, true, true);
	$fullTable=SqlList::getList('Resource');
	foreach ($lstSub as $id=>$sub) {
	  $sub->_readOnly=true; // Add readonly
		$lstSub[$id]=$sub;
	}
	foreach ( $lstAff as $id => $aff ) {
		$key='#'.$aff->idResource;
		if (isset($stockRes[$key])) {
		  $lstRes[$key]=$stockRes[$key];
		}
		if (isset($lstSub[$key])) {
			$sub=$lstSub[$key];
			if (isset($sub->_readOnly)) {
				unset($sub->_readOnly);
				$lstSub[$key]=$sub;
			}
		}
	}
} else if ($scope->accessCode == 'TEAM') {
	$lstRes=$user->getManagedTeamResources(true);
	$fullTable=SqlList::getList('Resource');
	foreach ($lstSub as $id=>$sub) {
	  $sub->_readOnly=true; // Add readonly
		$lstSub[$id]=$sub;
	}
	foreach ( $lstRes as $id => $res ) {
		$key=$id;
		if (isset($lstSub[$key])) {
			$sub=$lstSub[$key];
			if (isset($sub->_readOnly)) {
				unset($sub->_readOnly);
				$lstSub[$key]=$sub;
			}
			unset($lstRes[$key]);
		}
	}
} else {
  traceHack("unknown access code '$scope->accessCode'");
}

uasort($lstRes,'Affectable::sort');
uasort($lstSub,'Affectable::sort');
echo '<table style="width:100%;height:100%;min-height:300px">';
echo '<tr style="height:20px">';
echo '<td class="section" style="width:200px">'.i18n('titleAvailable').'</td>';
echo '<td class="" style="width:50px">&nbsp;</td>';
echo '<td class="section" style="width:200px">'.i18n('titleSelected').'</td>';
echo '</tr>';
echo '<tr style="height:10px"><td colspan="3">&nbsp;</td></tr>';
echo '<tr style="height:20px">';
echo '<td style="position:relative">';
echo '<input dojoType="dijit.form.TextBox" id="selectResourcesAvailableSearch" class="input" style="width:210px" value="" onKeyUp="filterDnDList(\'selectResourcesAvailableSearch\',\'selectResourcesAvailable\',\'div\');" />';
if(!isNewGui()){
  $iconViewPosition = "right:4px;top:3px;";
}else{
  $iconViewPosition = "right:6px;top:10px;";
}
echo '<div style="position:absolute;'.$iconViewPosition.'" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>';
echo '</td>';
echo '<td >&nbsp;</td>';
echo '<td style="position:relative;">';
echo '<input dojoType="dijit.form.TextBox" id="selectResourcesSelectedSearch" class="input" style="width:210px" value="" onKeyUp="filterDnDList(\'selectResourcesSelectedSearch\',\'selectResourcesSelected\',\'div\');" />';
echo '<div style="position:absolute;'.$iconViewPosition.'" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>';
echo '</td></tr>';
echo '<tr>';
echo '<td style="position:relative;max-width:200px;vertical-align:top;" class="noteHeader" >';
$imageColorNewGui = "";
if(isNewGui()){
  $imageColorNewGui = 'imageColorNewGuiNoSelection';
}
echo '<div style="height:'.$showHeight.';overflow:auto;" id="selectResourcesAvailable" dojotype="dojo.dnd.Source" dndType="subsription" withhandles="false" data-dojo-props="accept: [ \'subscription\' ]">';

foreach($lstRes as $res) {
  drawResourceTile($res,"selectResourcesAvailable");
}
echo '</div>';
echo '</td>';
echo '<td class="" ></td>';
echo '<td style="position:relative;max-width:200px;max-height:'.$showHeight.';vertical-align:top;" class="noteHeader" >';
echo '<div style="height:'.$showHeight.';overflow:auto;" id="selectResourcesSelected" jsId="selectResourcesSelected" dojotype="dojo.dnd.Source" dndType="subsription" withhandles="false" data-dojo-props="accept: [ \'subscription\' ]">';
foreach($lstSub as $sub) {
  drawResourceTile($sub,"selectResourcesSelected");
}
echo '</td>';
echo '</tr>';
echo '</table>';
echo'<br/><table style="width: 100%;" ><tr><td style="width: 100%;" align="center">'
    .'<button dojoType="dijit.form.Button" type="button" onclick="selectResourcesValidated(\''.strval($target).'\',\''.strval($target).'\')">'.i18n("Validated").'</button>'
    .'</td></tr></table>';

function drawResourceTile($res,$dndSource){
  $name=($res->name)?$res->name:$res->userName;
  $canDnD=(isset($res->_readOnly))?false:true;
  echo '<div class="'.(($canDnD)?'dojoDndItem':'').' subscription" id="subscription'.$res->id.'" value="'.pq_str_replace('"','',$name).'"  userid="'.$res->id.'"  dndType="subscription" style="position:relative;padding: 2px 5px 3px 5px;margin:5px;color:#707070;min-height:22px;background-color:#ffffff; border:1px solid #707070" >'
    .formatUserThumb($res->id, "", "")
    .$name
    .'</div>';
}
?>