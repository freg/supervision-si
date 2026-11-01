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
$user=getSessionUser();
$objectClass = RequestHandler::getValue('layoutObjectClass');
//if(pq_strpos($objectClass, 'Planning') !== false)$objectClass='Planning'; // PBER #10872
$layoutId = $user->_arrayLayouts[$objectClass]['id'];
$layoutRef = new Layout($layoutId);
$itemName = $layoutRef->scope;
$objectId = $layoutRef->id;
$user=getSessionUser();
$res=new User();
$scope=Affectable::getVisibilityScope();
$crit="idle=0";
if ($scope=='orga') {
	$crit.=" and idOrganization in (". Organization::getUserOrganisationList().")";
} else if ($scope=='team') {
	$aff=new Affectable(getSessionUser()->id,true);
	$crit.=" and idTeam=".Sql::fmtId($aff->idTeam);
}
$lstRes=$res->getSqlElementsFromCriteria(null,false,$crit,'fullName asc, name asc',true);
$layout=new LayoutForced();
$crit=array("objectClass"=>$objectClass,"idLayout"=>$objectId);
$lstLayout=$layout->getSqlElementsFromCriteria($crit);

if (sessionValueExists('screenHeight') and getSessionValue('screenHeight')) {
	$showHeight = round(getSessionValue('screenHeight') * 0.4)."px";
} else {
	$showHeight="100%";
}

foreach ($lstLayout as $idLayout=>$lay) {
  if (isset($lstRes['#'.$lay->idUser])) {
    $lstLayout['#'.$lay->idUser]=$lstRes['#'.$lay->idUser];
    unset($lstRes['#'.$lay->idUser]);
  } else {
    $lstLayout['#'.$lay->idUser]=new Affectable($lay->idUser);
  }
  unset($lstLayout[$idLayout]);
}

$profile=getSessionUser()->idProfile; // as of today, only take into account default profile

$crit=array('scope' => 'subscription','idProfile' => $profile);
$habilitation=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
$scope=new AccessScopeSpecific($habilitation->rightAccess, true);
if (! $scope->accessCode or $scope->accessCode == 'NO') {
	$lstRes=array(); // No access to this feature ;)
	$lstLayout=array(); // No access to this feature ;)
} else if ($scope->accessCode == 'ALL') {
	// OK
} else if ($scope->accessCode == 'OWN')  {
	$lstRes=array(); // Not for other, should not come here
	$lstLayout=array(); // Not for other, should not come here
} else if ($scope->accessCode == 'PRO') {
	$stockRes=$lstRes;
	$lstRes=array();
	$crit='idProject in ' . transformListIntoInClause($user->getAffectedProjects(true));
	$aff=new Affectation(); 
	$lstAff=$aff->getSqlElementsFromCriteria(null, false, $crit, null, true, true);
	$fullTable=SqlList::getList('Resource');
	foreach ($lstLayout as $id=>$sub) {
	  $sub->_readOnly=true; // Add readonly
		$lstLayout[$id]=$sub;
	}
	foreach ( $lstAff as $id => $aff ) {
		$key='#'.$aff->idResource;
		if (isset($stockRes[$key])) {
		  $lstRes[$key]=$stockRes[$key];
		}
		if (isset($lstLayout[$key])) {
			$sub=$lstLayout[$key];
			if (isset($sub->_readOnly)) {
				unset($sub->_readOnly);
				$lstLayout[$key]=$sub;
			}
		}
	}
} else if ($scope->accessCode == 'TEAM') {
	$lstRes=$user->getManagedTeamResources(true);
	$fullTable=SqlList::getList('Resource');
	foreach ($lstLayout as $id=>$sub) {
	  $sub->_readOnly=true; // Add readonly
		$lstLayout[$id]=$sub;
	}
	foreach ( $lstRes as $id => $res ) {
		$key=$id;
		if (isset($lstLayout[$key])) {
			$sub=$lstLayout[$key];
			if (isset($sub->_readOnly)) {
				unset($sub->_readOnly);
				$lstLayout[$key]=$sub;
			}
			unset($lstRes[$key]);
		}
	}
} else {
  traceHack("unknown access code '$scope->accessCode'");
}

uasort($lstRes,'Affectable::sort');
uasort($lstLayout,'Affectable::sort');
?>
<form id='dialogLayoutForOthersForm' name='dialogLayoutForOthersForm' onSubmit="return false;">
<input type="hidden" id="layoutObjectClass" name="layoutObjectClass" value="<?php echo $objectClass; ?>" />
<table style="width:100%;height:100%;min-height:300px">
<tr><td colspan="2"><label style="float:right;"><?php echo   ucfirst(i18n('layoutName')); ?>&nbsp;&nbsp;&nbsp;</label></td><td> <label style="text-align:left;font-size:16px;font-weight:bold;"> <?php echo $layoutRef->scope;?></label></td></tr>
    <div id='listGroup' dojoType="dijit.layout.ContentPane" region="center" ><div style="height:10px;"></div></div>
     
    <tr style="height:20px">
    <td style="position:relative" colspan="2">
      <label style="float:right;"> <?php echo i18n("remindGroup"); ?>&nbsp;&nbsp;&nbsp;</label>
   </td>
    <td style="position:relative;">
      <div id="layoutGroupForOthersDiv" dojoType="dijit.layout.ContentPane">
        <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="selectGroup" name="selectGroup"  style="width:210px;"
                class="input"  onchange="remindGroup(this.value);" value=" ">
                 <?php htmlDrawOptionForReference('idLayoutGroup', null, null, false);?>
        </select>
      </div>
    </td>
  </tr>
     
<tr><td>&nbsp;</td><td>&nbsp;</td></tr>
  <tr style="height:20px">
    <td class="section" style="width:200px"> <?php echo i18n('titleAvailable'); ?></td>
    <td class="" style="width:50px">&nbsp;</td>
    <td class="section" style="width:200px"> <?php echo i18n('titleSelected'); ?></td>
  </tr>
  <tr style="height:10px"><td colspan="3">&nbsp;</td></tr>
  <tr style="height:20px">
    <td style="position:relative">
    <input dojoType="dijit.form.TextBox" id="layoutAvailableSearch" class="input" style="width:210px" value="" onKeyUp="filterDnDListLayout('layoutAvailableSearch','layoutAvailable','div');" />
    <?php if(!isNewGui()){
            $iconViewPosition = "right:4px;top:3px;";
          }else{
            $iconViewPosition = "right:6px;top:10px;";
          }?>  
      <div id="iconSearchLayout" name="iconSearchLayout"  style="position:absolute;<?php echo $iconViewPosition; ?>;" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>
      <div id="iconCancelLayout" name="iconCancelLayout" style="display:none;position:absolute;<?php echo $iconViewPosition; ?>;" class="iconCancel iconSize16 imageColorNewGuiNoSelection"  onclick="clearFilterDnDListLayout();"></div>
    
    </td>
    <td >&nbsp;</td>
    <td style="position:relative;">
      <input dojoType="dijit.form.TextBox" id="layoutSubscribedSearch" class="input" style="width:210px" value="" onKeyUp="filterDnDListLayout('layoutSubscribedSearch','layoutSubscribed','div');" />
      <div style="position:absolute;<?php echo $iconViewPosition; ?>" class="iconSearch iconSize16 imageColorNewGuiNoSelection"></div>
    </td>
  </tr>
  <tr>
    <td style="position:relative;max-width:200px;vertical-align:top;" class="noteHeader" >
    <?php $imageColorNewGui = "";
      if(isNewGui()){
        $imageColorNewGui = 'imageColorNewGuiNoSelection';
      }?>
      <div style="height:<?php echo $showHeight; ?>;overflow:auto;" id="layoutAvailable"  jsId='layoutAvailable' name="layoutAvailable" dojotype="dojo.dnd.Source" selfCopy="false" dndType="subsription" withhandles="false" data-dojo-props="accept:['layout']">
      <?php foreach($lstRes as $res) {
        drawResourceTile($res,"layoutAvailable");
      }?>
      </div>
    </td>
    
    <td class="" >
      <button title="<?php echo i18n('layoutAll');?>" dojoType="dijit.form.Button"
                id="layoutAll" name="layoutAll" class="resetMargin roundedButton notButton" style="height:24px;width:32px;margin-top:-5px;"
                iconClass="iconAllRight iconSize32 imageColorNewGui" showLabel="false">
              <script type="dojo/connect" event="onClick" args="evt">layoutAll('layoutAvailable');</script>
            </button>
    </td>
    
    <td style="position:relative;max-width:200px;max-height:'.$showHeight.';vertical-align:top;" class="noteHeader" >
      <div style="height:<?php echo $showHeight;?>;overflow:auto;" id="layoutSubscribed" jsId='layoutSubscribed' name="layoutSubscribed" dojotype="dojo.dnd.Source"  selfCopy="false" dndType="subsription" withhandles="false" data-dojo-props="accept:['layout']">
      <?php foreach($lstLayout as $sub) {
        drawResourceTile($sub,"layoutSubscribed");
      }?>
    </td>
  </tr>
  <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
  <tr style="height:20px">
    <td colspan="2" style="position:relative">
      <label style="float:right;"><?php echo i18n("saveGroup"); ?>&nbsp;&nbsp;&nbsp;</label>
    </td>
    <td style="position:relative;">
    <table>
      <tr>
        <td>
          <input dojoType="dijit.form.TextBox" id="saveGroup" name="saveGroup" class="input" style="width:155px" value="" />
        </td>
        <td>
          <button title="<?php echo i18n('saveGroup');?>" dojoType="dijit.form.Button" align="left"
            id="saveGroupButton" name="saveGroupButton" class="resetMargin roundedButton notButton" style="height:24px;margin-top:-5px;"
            iconClass="dijitButtonIcon dijitButtonIconSave imageColorNewGui" showLabel="false">
          <script type="dojo/connect" event="onClick" args="evt">saveGroup();</script>
          </button>
        </td>
        <td id="removeGroupButtonTD" style="display:none;">
          <button title="<?php echo i18n('removeGroup');?>" dojoType="dijit.form.Button" align="left"
            id="removeGroupButton" name="removeGroupButton" class="resetMargin roundedButton notButton" style="height:24px;margin-top:-5px;"
            iconClass="dijitButtonIcon dijitButtonIconDelete imageColorNewGui" showLabel="false">
            <script type="dojo/connect" event="onClick" args="evt">removeGroup();</script>
          </button>
        </td>
      </tr>
    </table>
    </td>
  </tr>
  </table>
  <table>
     <tr><td>&nbsp;</td></tr>
   <tr>
    <td colspan="2"> <table> <tr>  
    <?php if (isNewGui()) { 
    $currentLayout = new Layout($layoutId);
          $isDefaultLayout = "off";
          $isForcedLayout = "off";
          $countDefault = SqlElement::getSingleSqlElementFromCriteria('Layout',array('ObjectClass'=>$objectClass,'isDefault'=>1,'idUser'=>'0','scope'=>$itemName));
          if($countDefault->id){
            $isDefaultLayout="on";
          }
          $layoutForced = new LayoutForced();
          $countForced = $layoutForced->countSqlElementsFromCriteria(array('idLayout'=>$layoutId));
          if($countForced > 0)$isForcedLayout="on";
          ?>
      <div  id="layoutForNewConnexionSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" 
          	value="<?php echo $isForcedLayout;?>" leftLabel="" rightLabel=""  style="margin-left:20px;width:10px;position:relative; left:0px;top:2px;z-index:99;" >
          	<script type="dojo/method" event="onStateChanged" >
              dijit.byId("layoutForNewConnexion").set("checked",(this.value=="on")?true:false);
	          </script>
          	</div>
       <?php }?>
       <?php $checkCo = "false";
             if($isForcedLayout=="on")$checkCo="true";?>
          <input  dojoType="dijit.form.CheckBox" name="layoutForNewConnexion" id="layoutForNewConnexion" checked="<?php echo $checkCo;?>" <?php if (isNewGui()) {?>style="display:none;"<?php }?>/>
            <div style=""><label style="width:396px;margin-left:63px;margin-top:-22px;text-align:left;" for="layoutForNewConnexion" ><?php echo i18n("layoutForNewConnexion"); ?></label></div>
          </tr></table>
          </td>
  </tr>
  <tr><td colspan="2"><div style="border-bottom:solid 1px grey;margin-left:20px;">&nbsp;</div></td></tr>
  <tr><td colspan="2">&nbsp;</td></tr>
   <tr>
    <td colspan="2"> <table> <tr> 
       <?php if (isNewGui()) { ?>
      <div  id="layoutForNewUserSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" 
          	value="<?php echo $isDefaultLayout;?>" leftLabel="" rightLabel=""  style="margin-left:20px;width:10px;position:relative; left:0px;top:2px;z-index:99;" >
          	<script type="dojo/method" event="onStateChanged" >
             dijit.byId("layoutForNewUser").set("checked",(this.value=="on")?true:false);
	          </script>
          	</div>
       <?php } ?>
       <?php $checkNewUser = "false";
             if($isDefaultLayout=="on")$checkNewUser="true";?>
          <input  dojoType="dijit.form.CheckBox" name="layoutForNewUser" id="layoutForNewUser" checked="<?php echo $checkNewUser;?>" <?php if (isNewGui()) {?>style="display:none;"<?php }?>/>
            <label style="margin-left:11px;float:none" for="layoutForNewUser" ><?php echo i18n("layoutForNewUser"); ?></label>
          </tr></table>
          </td>
  </tr>
     
  <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
  <tr>
      <td colspan="2" align="center">
        <input type="hidden" id="dialogLayoutForOthersAction">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogLayoutForOthers').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogLayoutForOtherssubmit" onclick="protectDblClick(this);validateLayoutForOthers();return false;">
          <?php echo i18n("buttonOK");?>
        </button>
      </form>
      </td>
  </tr>
</table>
<?php 


function drawResourceTile($res,$dndSource){
  global $objectClass,$itemName,$objectId,$user;
  if($res->id==0 or !$res->id)return;
  if($res->id == $user->id)return;
  $classSpecific = '';
  if($dndSource=='layoutAvailable'){
    $classSpecific = 'layoutIsAvaible ';
  }
  $name=($res->resourceName)??$res->name;
  $canDnD=(isset($res->_readOnly))?false:true;
  echo '<div class="'.$classSpecific.(($canDnD)?'dojoDndItem':'').' layout" id="layoutForOther'.$res->id.'" value="'.pq_str_replace('"','',$name).'" objectclass="'.$objectClass.'" scope="'.$itemName.'" objectid="'.$objectId.'"  userid="'.$res->id.'" currentuserid="'.getSessionUser()->id.'" dndType="layout" style="display: block;position:relative;padding: 2px 5px 3px 5px;margin:5px;color:#707070;min-height:22px;background-color:#ffffff; border:1px solid #707070" >'
    .formatUserThumb($res->id, "", "")
    .$name
    .'</div>';
}
?>