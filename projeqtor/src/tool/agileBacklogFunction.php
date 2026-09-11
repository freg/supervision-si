<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
******************************************************************************
*** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
******************************************************************************
*
* Copyright 2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
*
* This file is an add-on to ProjeQtOr, packaged as a plug-in module.
* It is NOT distributed under an open source license.
* It is distributed in a proprietary mode, only to the customer who bought
* corresponding licence.
* The company ProjeQtOr remains owner of all add-ons it delivers.
* Any change to an add-ons without the explicit agreement of the company
* ProjeQtOr is prohibited.
* The diffusion (or any kind if distribution) of an add-on is prohibited.
* Violators will be prosecuted.
*
*** DO NOT REMOVE THIS NOTICE ************************************************/

function drawSprintBacklogColumn(){
  $status = new Status();
  $statusList=SqlList::getList('Status','name',null,true);
  $agileStatusList = $status->getSqlElementsFromCriteria(array('forAgileScrum'=>'1'),null,null,"sortOrder ASC");
  $json = '{"column":[{"from":'.array_key_first($statusList).',"name":"Backlog", "cantDelete":1, "setIdleStatus":0},';
  $countStatus = 0;
  foreach ($agileStatusList as $agileStatus){
    $countStatus++;
    $json .= '{"from":'.$agileStatus->id.',"name":"'.ucfirst($agileStatus->name).'", "setIdleStatus":'.$agileStatus->setIdleStatus.'}';
    if($countStatus < count($agileStatusList))$json.=',';
  }
  $json .= '],"typeData":"UserStory"}';
  $type='Status';
  $jsonD=json_decode($json,true);
  
  $hideBacklog = (Parameter::getUserParameter ( "sprintBacklogHideBacklog" )=='off' or Parameter::getUserParameter ( "sprintBacklogHideBacklog" )=='0')?1:0;
  $hideClosed = (Parameter::getUserParameter ( "sprintBacklogHideClosed" )=='' or Parameter::getUserParameter ( "sprintBacklogHideClosed" )=='off' or Parameter::getUserParameter ( "sprintBacklogHideClosed" )=='0')?1:0;
  $hideStoryPointsAndBusiness = Parameter::getUserParameter("sprintBacklogHideStoryPointsAndBusiness");
  $hideStoryPointsAndBusiness = ($hideStoryPointsAndBusiness=='on' or $hideStoryPointsAndBusiness=='')?true:false;
  
  $allowedStatus=array();
  if(is_array($jsonD) and is_array($jsonD['column']) and count($jsonD['column'])!=0){
    $jsonArray=array();
    $keyJsonOrder=array();
    $sortedColumns=array();
    foreach ($jsonD['column'] as $key=>$itemSprintBacklog) {
      if($itemSprintBacklog['from']!='n'){
        $obj = new $type($itemSprintBacklog['from'],true);
        if(isset($obj->sortOrder)){
          $jsonArray[str_pad($obj->sortOrder,5,'0', STR_PAD_LEFT).'-'.$obj->id]=$itemSprintBacklog;
        }else{
          $jsonArray[$obj->name.'-'.$obj->id]=$itemSprintBacklog;
        }
      }else{
        $jsonArray['00000-'.$itemSprintBacklog['from']]=$itemSprintBacklog;
      }
    }
    ksort($jsonArray);
    foreach ($jsonArray as $key=>$itemSprintBacklog) {
      $keyJsonOrder[]=$key;
      $sortedColumns[]=$itemSprintBacklog;
    }
    $mapAccept=array();
    $accept="[";
    $iterateur=0;
    $user=getSessionUser();
    $mapWorkflow=array();
    for ($i=0;$i<count($sortedColumns);$i++) {
      $itemSprintBacklog=$sortedColumns[$i];
      $idFrom=$itemSprintBacklog['from'];
      $allowedStatus[$idFrom]=array($idFrom=>$idFrom);
      $found=false;
      foreach ($statusList as $idS=>$nameS) {
        if ($found) {
          if (isset($sortedColumns[$i+1]) and $idS==$sortedColumns[$i+1]['from']) {
            break;
          } else {
            $allowedStatus[$idFrom][$idS]=$idS;
          }
        } else if ($idS==$idFrom) {
          $found=true;
        }
      }
    }
    foreach ($user->getAllProfiles() as $idProfile){ // For each profile of the user (on any project)
      foreach (SqlList::getList("Status",'id') as $idStatus){ // For every status
        foreach (SqlList::getList("UserStoryType",'id') as $idUserStoryType){ // For every type (Ticket type or Activity Type)
          $workflowId=SqlList::getFieldFromId("UserStoryType", $idUserStoryType, 'idWorkflow');
          if(!isset($mapWorkflow[$workflowId])){
            $woTmp=new Workflow($workflowId);
            $mapWorkflow[$workflowId]=$woTmp->getWorkflowstatusArray();
          }
          foreach ($jsonD['column'] as $itemSprintBacklog) { // For all defined columns on the Backlog (id of status is in the from field
            foreach ($allowedStatus[$itemSprintBacklog['from']] as $idStatusTo) {
              $toPut="";
              if($idStatusTo!=$idStatus) {
                if(isset($idProfile)
                    && isset($mapWorkflow[$workflowId][$idStatus])
                    && isset($mapWorkflow[$workflowId][$idStatus][$idStatusTo])) {
                      if(isset($mapWorkflow[$workflowId][$idStatus][$idStatusTo][$idProfile])
                          && $mapWorkflow[$workflowId][$idStatus][$idStatusTo][$idProfile]) {
                            $toPut='column'.$idStatus;
                          }
                    }
              }
              if($toPut!=""){
                $exist=false;
                if(isset($mapAccept[$itemSprintBacklog['from']]))if(pq_strpos($mapAccept[$itemSprintBacklog['from']], $toPut) !== false)$exist=true;
                if(!$exist){
                  if(!isset($mapAccept[$itemSprintBacklog['from']])){
                    $mapAccept[$itemSprintBacklog['from']]="'$toPut'";
                  }else{
                    $mapAccept[$itemSprintBacklog['from']].=",'$toPut'";
                  }
                }
              }
            }
          }
        }
      }
    }
    $accept.="]";
    $iterateur=0;
    foreach ($jsonArray as $itemSprintBacklog) {
      $nbItems=0;
      $acceptTmp=$accept;
      if(isset($mapAccept[$itemSprintBacklog['from']]))$acceptTmp='['.$mapAccept[$itemSprintBacklog['from']].']';
      if($type=="Sprint")$acceptTmp="[".SqlList::getFieldFromId("Sprint", $itemSprintBacklog['from'], "idProject")."]";
      $destHeight=RequestHandler::getValue('destinationHeight');
      $destWidth=RequestHandler::getValue('destinationWidth');
      if ($destHeight) {
        $maxHeight=($destHeight-((RequestHandler::getValue('xhrPostDestination')=='divSprintBacklogContainer')?76:161));
        if ($hideStoryPointsAndBusiness) $maxHeight-=30;
        $maxHeight.='px';
      } else {
        $maxHeight='100%';
      }
      if ($destWidth) {
        $nbCols=count($jsonD['column']);
        $maxWidth=((($destWidth)/$nbCols)-20)."px";
      } else {
        $maxWidth="332px";
      }
      $name=$itemSprintBacklog['name'];
      $from=$itemSprintBacklog['from'];
      $setIdleStatus = $itemSprintBacklog['setIdleStatus'];
      $status = new Status($from);
      $backgroundColor = ($name == 'Backlog')?'#9b9b9b':$status->color;
      $columnClass = '';
      $columnClass = ($name == 'Backlog')?'isBacklogColumn':'';
      $columnClass = ($name != 'Backlog' and $setIdleStatus)?'isClosedColumn':$columnClass;
      echo '<td class="'.$columnClass.'" style="vertical-align:top;;width:'.$maxWidth.';min-width:355px;'.((($hideBacklog and $name == 'Backlog') or ($hideClosed and $setIdleStatus))?'display:none;':'').'">
            <table style="width:100%;"><tr style="min-height:47px;height:47px;max-height:47px;">
            <td class="kanbanColumn backlogColumnHeader" oncontextmenu="openBacklogColumnContextMenu(event,'.intval($from).',\''.addslashes($type).'\',\''.addslashes($name).'\');" style="position:relative;background-color:'.((isNewGui())?$backgroundColor.';border-radius:10px 10px 0 0':$backgroundColor).';padding:3px 8px 0px;border-bottom:2px solid #ffffff;min-width:355px;">';
      $addHeight='';
      echo '<div style="margin-bottom:10px;'.$addHeight.'font-weight: bold;color: white;text-shadow: #656565 1px 1px 2px;>';
      echo '  <h2 style="font-size: 14px;font-weight:bold;margin: 8px 8px 2px;color:#4d4d4d">'.htmlEncode($name).'</h2>';
      echo '<div id="badgeColumnItem'.$from.'" class="sectionBadge">'.$nbItems.'</div>';
      echo '<div class="backlogItemStoryPointAndBusiness" style="position: relative;top: 5px;font-size: 11px;'.(($hideStoryPointsAndBusiness)?'':'display:none;').'">';
      echo '  <table style="width: 100%;">';
      echo '    <tr>';
      echo '      <td class="linkHeader" style="padding:3px;cursor:auto;width: 50%;height: 10px !important;border-radius: 6px 0px 0px; 0px;border: unset;border-right: 1px solid #AAAAAA;border-bottom: 1px solid #AAAAAA;">'.i18n('colStoryPoints').'</td>';
      echo '      <td class="linkHeader" style="padding:3px;cursor:auto;width: 50%;height: 10px !important;border-radius: 0px 6px 0px 0px;border: unset;border-bottom: 1px solid #AAAAAA;">'.i18n('colBusinessValue').'</td>';
      echo '    </tr>';
      echo '    <tr>';
      echo '      <td id="storyPointsColumn'.$from.'" class="linkData" style="height: 10px !important;color: black;text-shadow: none;font-weight: 400;text-align:center;border: unset;border-right: 1px solid #AAAAAA;">0</td>';
      echo '      <td id="businessValuesColumn'.$from.'" class="linkData" style="height: 10px !important;color: black;text-shadow: none;font-weight: 400;text-align:center;border: unset;">0</td>';
      echo '    </tr>';
      echo '  </table>';
      echo '</div>';
      echo '</div>';
      echo '</td></tr><tr>';
      echo '
        <td class="kanbanColumn backlogColumnBody" oncontextmenu="openBacklogColumnContextMenu(event,'.intval($from).',\''.addslashes($type).'\',\''.addslashes($name).'\');" style="overflow-y:scroll;overflow-x:hidden;display:block; height:'.$maxHeight.';max-height:'.$maxHeight.'; position:relative;background-color:'.((isNewGui())?'var(--color-light);border:2px solid var(--color-light);border-radius:0 0 10px 10px':'#e2e4e6').';padding:6px 0px 6px 4px;width:auto;min-width:355px;" id="backlogColumn'.$itemSprintBacklog['from']. '"
        jsId="backlogColumn'.$itemSprintBacklog['from']. '" columnTarget="'.$itemSprintBacklog['from'].'" columnType="'.$type.'" dojotype="dojo.dnd.Source" dndType="column'.$itemSprintBacklog['from']. '" withhandles="false"
        '.($acceptTmp!='[]' ? 'data-dojo-props="accept: '.$acceptTmp.',singular:true, horizontal:true, withHandles: false"':'data-dojo-props="singular:true, horizontal:true, withHandles: false"').' width="'.((100/count($jsonArray))).'%" valign="top">';
      echo '
      <script type="dojo/connect" event="onDndStart" args="evt">
        anchorTmp=evt.anchor;
        evt.anchor.style.display=\'none\';
        return true;
      </script>
      <script type="dojo/connect" event="onDndCancel" args="evt">
      anchorTmp.style.display=\'block\';
        return true;
      </script>';
      echo '</td></tr></table>
      </td>';
      $iterateur++;
      if($iterateur==(count($jsonArray)-1))$columnClass='isClosedColumn';
      if ($iterateur<count($jsonArray)) {
        echo '
        <td class="'.$columnClass.'" style="min-width:10px;max-width:10px;width:10px;'.((($hideBacklog and $name == 'Backlog') or ($hideClosed and $setIdleStatus))?'display:none;':'').'" width="10px"></td>';
      }
    }
  }
}

function sprintBacklogParameterList(){
  $hideBacklog = Parameter::getUserParameter("sprintBacklogHideBacklog");
  $hideBacklog = ($hideBacklog=='' or $hideBacklog=='on' or $hideBacklog=='1')?true:false;
  
  $hideClosed = Parameter::getUserParameter("sprintBacklogHideClosed");
  $hideClosed = ($hideClosed=='on' or $hideClosed=='1')?true:false;
  
  $showIdle = Parameter::getUserParameter("sprintBacklogShowIdle");
  $showIdle = ($showIdle=='on' or $showIdle=='1')?true:false;
  
  $fullWidthElement = Parameter::getUserParameter("sprintBacklogFullWidthElement");
  $fullWidthElement = ($fullWidthElement=='on' or $fullWidthElement=='1')?true:false;
  
  $hideStatus = Parameter::getUserParameter("sprintBacklogHideStatus");
  $hideStatus = ($hideStatus=='on' or $hideStatus=='')?true:false;
  
  $hideSprint = Parameter::getUserParameter("sprintBacklogHideSprint");
  $hideSprint = ($hideSprint=='on' or $hideSprint=='')?true:false;
  
  $hideEpic = Parameter::getUserParameter("sprintBacklogHideSprint");
  $hideEpic = ($hideEpic=='on' or $hideEpic=='')?true:false;
  
  $hideProduct = Parameter::getUserParameter("sprintBacklogHideProduct");
  $hideProduct = ($hideProduct=='on' or $hideProduct=='')?true:false;
  
  $hideResponsible = Parameter::getUserParameter("sprintBacklogHideResponsible");
  $hideResponsible = ($hideResponsible=='on' or $hideResponsible=='')?true:false;
  
  $hideStoryPointsAndBusiness = Parameter::getUserParameter("sprintBacklogHideStoryPointsAndBusiness");
  $hideStoryPointsAndBusiness = ($hideStoryPointsAndBusiness=='on' or $hideStoryPointsAndBusiness=='')?true:false;
  
  $hideType = Parameter::getUserParameter("sprintBacklogHideType");
  $hideType = ($hideType=='on' or $hideType=='')?true:false;
  
  $hideProjectName = Parameter::getUserParameter("sprintBacklogHideProjectName");
  $hideProjectName = ($hideProjectName=='on' or $hideProjectName=='')?true:false;
  
  $hideScrumPriority = Parameter::getUserParameter("sprintBacklogHideScrumPriority");
  $hideScrumPriority = ($hideScrumPriority=='on' or $hideScrumPriority=='')?true:false;
  
  echo '<table style="width:100%;">';
  echo '  <tr>';
  echo '    <td style="vertical-align:top;">';
  echo '<table style="width:240px;margin:0px 15px 5px 5px;display:inline-block;">';
  echo '  <tr>';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanban iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanban').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideBacklog" name="sprintBacklogHideBacklog" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideBacklog)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideBacklog(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideBacklog\');">'.pq_ucfirst(i18n("labelKanbanHideBacklog")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideClosed" name="sprintBacklogHideClosed" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideClosed)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideClosed(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideClosed\');">'.pq_ucfirst(i18n("labelBacklogHideClosed")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="spintBacklogShowIdle" name="spintBacklogShowIdle" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showIdle)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogShowIdle(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'listShowIdle\');">'.pq_ucfirst(i18n("labelKanbanShowIdle")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogFullWidthElement" name="sprintBacklogFullWidthElement" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($fullWidthElement)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogFullWidthElement(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogFullWidthElement\');">'.pq_ucfirst(i18n("labelKanbanFullWidthElement")).'</span></td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '    <td rowspan="2" style="vertical-align:top;">';
  echo '<table style="width:240px;margin:5px 5px 0px 5pxpx;display:inline-block;">';
  echo '  <tr style="padding:5px;">';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanbanTiles iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanbanTiles').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideStatus" name="sprintBacklogHideStatus" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideStatus)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideStatus(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideStatus\');">'.pq_ucfirst(i18n("labelKanbanHideStatus")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideEpic" name="sprintBacklogHideEpic" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideEpic)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideEpic(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideEpic\');">'.pq_ucfirst(i18n("labelBacklogHideEpic")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideSprint" name="sprintBacklogHideSprint" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideSprint)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideSprint(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideSprint\');">'.pq_ucfirst(i18n("labelBacklogHideSprint")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideProduct" name="sprintBacklogHideProduct" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideProduct)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideProduct(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideProduct\');">'.pq_ucfirst(i18n("labelKanbanHideProduct")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideResponsible" name="sprintBacklogHideProduct" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideResponsible)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideResponsible(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideResponsible\');">'.pq_ucfirst(i18n("labelKanbanHideResponsible")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideStoryPointsAndBusiness" name="sprintBacklogHideStoryPointsAndBusiness" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideStoryPointsAndBusiness)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideStoryPointsAndBusiness(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideStoryPointsAndBusiness\');">'.pq_ucfirst(i18n("labelKanbanHidePointsAndBusiness")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideType" name="sprintBacklogHideType" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideType)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideType(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideType\');">'.pq_ucfirst(i18n("labelKanbanHideType")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideScrumPriority" name="sprintBacklogHideScrumPriority" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideScrumPriority)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideScrumPriority(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideScrumPriority\');">'.pq_ucfirst(i18n("labelKanbanHideScrumPriority")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="sprintBacklogHideProjectName" name="sprintBacklogHideProjectName" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideProjectName)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          sprintBacklogHideProjectName(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'sprintBacklogHideProjectName\');">'.pq_ucfirst(i18n("labelKanbanHideProjectName")).'</span></td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="vertical-align:top;">';
  echo '<table style="width:240px;margin:5px 15px 0px 5px;display:inline-block;">';
  echo '  <tr>';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanbanManagement iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanbanManagement').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td colspan="2">';
  echo '      <table style="width:100%;text-align:center;margin-top: 5px;">';
  echo '        <tr>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
  echo '            onclick="addSprintFromBacklog()">'.formatIcon('Sprint',32,i18n('addSprintBacklog')).'</div>';
  echo '          </td>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
  echo '            onclick="addEpicFromBacklog()">'.formatIcon('Epic',32,i18n('addEpicBacklog')).'</div>';
  echo '          </td>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
  echo '            onclick="addUserStoryFromBacklog()">'.formatIcon('UserStory',32, i18n('addUserStoryBacklog')).'</div>';
  echo '          </td>';
  echo '        </tr>';
  echo '        <tr>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('addSprintBacklog').'</td>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('addEpicBacklog').'</td>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('addUserStoryBacklog').'</td>';
  echo '        </tr>';
  echo '      </table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
}

function drawProductBacklogColumn(){
  $status = new Status();
  $sprint = new Sprint();
  $where = "idle = 0 and idProject in ".getVisibleProjectsList();
  $sprintList = $sprint->getSqlElementsFromCriteria(null, null, $where);
  $json = '{"column":[{"from":0,"name":"Backlog", "cantDelete":1}';
  $countSprintList = count($sprintList);
  $countSprint = 0;
  if($countSprintList > 0){
    $json.=',';
    foreach ($sprintList as $sprint){
      $countSprint++;
      $json .= '{"from":'.$sprint->id.',"name":"'.ucfirst($sprint->name).'"}';
      if($countSprint < $countSprintList)$json.=',';
    }
  }
  $json .= '],"typeData":"Sprint"}';
  $type='Sprint';
  $jsonD=json_decode($json,true);
  
  $hideBacklog = (Parameter::getUserParameter ( "productBacklogHideBacklog" )=='off' or Parameter::getUserParameter ( "productBacklogHideBacklog" )=='0')?1:0;
  $hideStoryPointsAndBusiness = Parameter::getUserParameter("productBacklogHideStoryPointsAndBusiness");
  $hideStoryPointsAndBusiness = ($hideStoryPointsAndBusiness=='on' or $hideStoryPointsAndBusiness=='')?true:false;
  
  if(count($jsonD['column'])!=0){
    $jsonArray=array();
    $keyJsonOrder=array();
    $sortedColumns=array();
    $fromArray = array();
    foreach ($jsonD['column'] as $key=>$itemProductBacklog) {
      if($itemProductBacklog['from']!='0'){
        $obj = new $type($itemProductBacklog['from'],true);
        $status = new Status($obj->idStatus);
        if(isset($status->sortOrder)){
          $jsonArray[str_pad($status->sortOrder,5,'0', STR_PAD_LEFT).'-'.$obj->id]=$itemProductBacklog;
        }else{
          $jsonArray[$obj->name.'-'.$obj->id]=$itemProductBacklog;
        }
      }else{
        $jsonArray['00000-'.$itemProductBacklog['from']]=$itemProductBacklog;
      }
    }
    
    $backlogKey = '00000-0';
    $backlogItem = null;
    if (isset($jsonArray[$backlogKey])) {
      $backlogItem = [$backlogKey => $jsonArray[$backlogKey]];
      unset($jsonArray[$backlogKey]);
    }
    
    uksort($jsonArray, function($k1, $k2) use ($jsonArray) {
      // sortOrde
      $s1 = (int)explode('-', $k1)[0];
      $s2 = (int)explode('-', $k2)[0];
      if ($s1 !== $s2) {
        return $s2 <=> $s1; // DESC
      }
      // name
      $n1 = isset($jsonArray[$k1]['name']) ? (string)$jsonArray[$k1]['name'] : '';
      $n2 = isset($jsonArray[$k2]['name']) ? (string)$jsonArray[$k2]['name'] : '';
      return strcasecmp($n1, $n2); // ASC
    });
    
    if ($backlogItem) {
      $jsonArray = $backlogItem + $jsonArray;
    }
    
    foreach ($jsonArray as $key=>$itemProductBacklog) {
      $keyJsonOrder[]=$key;
      $sortedColumns[]=$itemProductBacklog;
      $fromArray[]=$itemProductBacklog['from'];
    }

    $noRefeshColumnOrder = RequestHandler::getBoolean('NoRefreshColumnOrder');
    if($noRefeshColumnOrder){
      $productBacklogColumnOrder = Parameter::getUserParameter('productBacklogColumnOrder');
      if($productBacklogColumnOrder){
        $productBacklogColumnOrder = json_decode($productBacklogColumnOrder, true);
        
        $byId = [];
        foreach ($jsonArray as $k => $v) {
          $pos = strrpos($k, '-');
          if ($pos === false) continue;
          $id = substr($k, $pos + 1);
          $byId[(int)$id] = ['key' => $k, 'value' => $v];
        }
        
        $sorted = [];
        foreach ($productBacklogColumnOrder as $id) {
          $id = (int)$id;
          if (isset($byId[$id])) {
            $sorted[$byId[$id]['key']] = $byId[$id]['value'];
            unset($byId[$id]);
          }
        }
        
        foreach ($byId as $rest) {
          $sorted[$rest['key']] = $rest['value'];
        }
        
        $jsonArray = $sorted;
      }
    }else{
      Parameter::storeUserParameter('productBacklogColumnOrder', json_encode($fromArray));
    }
    
    $keyJsonOrder=array();
    $sortedColumns=array();
    foreach ($jsonArray as $key=>$itemProductBacklog) {
      $keyJsonOrder[]=$key;
      $sortedColumns[]=$itemProductBacklog;
    }
    
    $accept="[";
    $iterateur=0;
    foreach ($jsonD['column'] as $itemKanban) {
      $accept.='\'column'.$itemKanban['from'].'\'';
      if($iterateur!=count($jsonD['column'])-1)$accept.=',';
    }
    $accept.="]";
    $iterateur=0;
    foreach ($jsonArray as $itemProductBacklog) {
      $nbItems=0;
      $destHeight=RequestHandler::getValue('destinationHeight');
      $destWidth=RequestHandler::getValue('destinationWidth');
      if ($destHeight) {
        $maxHeight=($destHeight-((RequestHandler::getValue('xhrPostDestination')=='divBacklogContainer')?76:161));
        if ($hideStoryPointsAndBusiness) $maxHeight-=30;
        $maxHeight.='px';
      } else {
        $maxHeight='100%';
      }
      if ($destWidth) {
        $nbCols=count($jsonD['column']);
        $maxWidth=((($destWidth)/$nbCols)-20)."px";
      } else {
        $maxWidth="332px";
      }
      $name=$itemProductBacklog['name'];
      $from=$itemProductBacklog['from'];
      $obj = new $type($itemProductBacklog['from']);
      $pe = $type.'PlanningElement';
      $status = new Status($obj->idStatus);
      $sprintColor = ($obj->id and $obj->$pe->color != "")?$obj->$pe->color:$status->color;
      $backgroundColor = ($name == 'Backlog')?'#9b9b9b':$sprintColor;
      $columnClass = '';
      $columnClass = ($name == 'Backlog')?'isBacklogColumn':'';
      echo '<td class="'.$columnClass.'" style="vertical-align:top;;width:'.$maxWidth.';min-width:355px;'.(($hideBacklog and $name == 'Backlog')?'display:none;':'').'">
            <table style="width:100%;"><tr style="min-height:47px;height:47px;max-height:47px;">
            <td class="kanbanColumn backlogColumnHeader" style="'.(($name != 'Backlog')?'cursor:pointer;':'').'position:relative;background-color:'.((isNewGui())?$backgroundColor.';border-radius:10px 10px 0 0':$backgroundColor).';padding:3px 8px 0px;border-bottom:2px solid #ffffff;min-width:355px;"'
                .(($name != 'Backlog')?'onclick="gotoSprintBacklog('.$from.');"':'').' '.(($name != 'Backlog')?'oncontextmenu="openBacklogContextMenu(null, \''.$from.'\', \'Sprint\', null, \'column\');"':'').'>';
      $addHeight='';
      echo '<div style="margin-bottom:10px;'.$addHeight.'font-weight: bold;color: white;text-shadow: #656565 1px 1px 2px;>';
      echo '  <h2 style="font-size: 14px;font-weight:bold;margin: 8px 8px 2px;color:#4d4d4d">'.htmlEncode($name).'</h2>';
      echo '<div id="badgeColumnItem'.$from.'" class="sectionBadge">'.$nbItems.'</div>';
      echo '<div class="backlogItemStoryPointAndBusiness" style="position: relative;top: 5px;cursor: unset !important;'.(($hideStoryPointsAndBusiness)?'':'display:none;').'">';
      echo '  <table style="width: 100%;">';
      echo '    <tr>';
      echo '      <td class="linkHeader" style="padding:3px;cursor:auto;width: 50%;height: 10px !important;border-radius: 6px 0px 0px; 0px;border: unset;border-right: 1px solid #AAAAAA;border-bottom: 1px solid #AAAAAA;">'.i18n('colStoryPoints').'</td>';
      echo '      <td class="linkHeader" style="padding:3px;cursor:auto;width: 50%;height: 10px !important;border-radius: 0px 6px 0px 0px;border: unset;border-bottom: 1px solid #AAAAAA;">'.i18n('colBusinessValue').'</td>';
      echo '    </tr>';
      echo '    <tr>';
      echo '      <td id="storyPointsColumn'.$from.'" class="linkData" style="height: 10px !important;color: black;text-shadow: none;font-weight: 400;text-align:center;border: unset;border-right: 1px solid #AAAAAA;">0</td>';
      echo '      <td id="businessValuesColumn'.$from.'"class="linkData" style="height: 10px !important;color: black;text-shadow: none;font-weight: 400;text-align:center;border: unset;">0</td>';
      echo '    </tr>';
      echo '  </table>';
      echo '</div>';
      echo '</div>';
      echo '</td></tr><tr>';
      echo '
        <td class="kanbanColumn backlogColumnBody" oncontextmenu="openBacklogColumnContextMenu(event,'.intval($from).',\''.addslashes($type).'\',\''.addslashes($name).'\');" style="overflow-y:scroll;overflow-x:hidden;display:block; height:'.$maxHeight.';max-height:'.$maxHeight.'; position:relative;background-color:'.((isNewGui())?'var(--color-light);border:2px solid var(--color-light);border-radius:0 0 10px 10px':'#e2e4e6').';padding:6px 0px 6px 4px;width:auto;min-width:355px;" id="backlogColumn'.$itemProductBacklog['from']. '"
        jsId="backlogColumn'.$itemProductBacklog['from']. '" columnTarget="'.$itemProductBacklog['from'].'" columnType="'.$type.'" dojotype="dojo.dnd.Source" dndType="column'.$itemProductBacklog['from']. '" withhandles="false"
        '.($accept!='[]' ? 'data-dojo-props="accept: '.$accept.',singular:true, horizontal:true,withHandles: false"':'data-dojo-props="singular:true, horizontal:true, withHandles: false"').' width="'.((100/count($jsonArray))).'%" valign="top">';
      echo '
      <script type="dojo/connect" event="onDndStart" args="evt">
        anchorTmp=evt.anchor;
        evt.anchor.style.display=\'none\';
        return true;
      </script>
      <script type="dojo/connect" event="onDndCancel" args="evt">
      anchorTmp.style.display=\'block\';
        return true;
      </script>';
      echo '</td></tr></table>
      </td>';
      $iterateur++;
      if ($iterateur<count($jsonArray)) {
        echo '
        <td class="'.$columnClass.'" style="min-width:10px;max-width:10px;width:10px;'.(($hideBacklog and $name == 'Backlog')?'display:none;':'').'" width="10px"></td>';
      }
    }
  }
}

function productBacklogParameterList(){
  $hideBacklog = Parameter::getUserParameter("productBacklogHideBacklog");
  $hideBacklog = ($hideBacklog=='' or $hideBacklog=='on' or $hideBacklog=='1')?true:false;
  
  $showIdle = Parameter::getUserParameter("productBacklogShowIdle");
  $showIdle = ($showIdle=='on' or $showIdle=='1')?true:false;
  
  $fullWidthElement = Parameter::getUserParameter("productBacklogFullWidthElement");
  $fullWidthElement = ($fullWidthElement=='on' or $fullWidthElement=='1')?true:false;
  
  $hideEpicItems = Parameter::getUserParameter("productBacklogHideEpicItem");
  $hideEpicItems = ($hideEpicItems=='off' or $hideEpicItems=='0')?false:true;
  
  $hideStatus = Parameter::getUserParameter("productBacklogHideStatus");
  $hideStatus = ($hideStatus=='on' or $hideStatus=='')?true:false;
  
  $hideSprint = Parameter::getUserParameter("productBacklogHideSprint");
  $hideSprint = ($hideSprint=='on' or $hideSprint=='')?true:false;
  
  $hideEpic = Parameter::getUserParameter("sprintBacklogHideSprint");
  $hideEpic = ($hideEpic=='on' or $hideEpic=='')?true:false;
  
  $hideProduct = Parameter::getUserParameter("productBacklogHideProduct");
  $hideProduct = ($hideProduct=='on' or $hideProduct=='')?true:false;
  
  $hideResponsible = Parameter::getUserParameter("productBacklogHideResponsible");
  $hideResponsible = ($hideResponsible=='on' or $hideResponsible=='')?true:false;
  
  $hideStoryPointsAndBusiness = Parameter::getUserParameter("productBacklogHideStoryPointsAndBusiness");
  $hideStoryPointsAndBusiness = ($hideStoryPointsAndBusiness=='on' or $hideStoryPointsAndBusiness=='')?true:false;
  
  $hideType = Parameter::getUserParameter("productBacklogHideType");
  $hideType = ($hideType=='on' or $hideType=='')?true:false;
  
  $hideProjectName = Parameter::getUserParameter("productBacklogHideProjectName");
  $hideProjectName = ($hideProjectName=='on' or $hideProjectName=='')?true:false;
  
  $hideScrumPriority = Parameter::getUserParameter("productBacklogHideScrumPriority");
  $hideScrumPriority = ($hideScrumPriority=='on' or $hideScrumPriority=='')?true:false;
  
  echo '<table style="width:100%;">';
  echo '  <tr>';
  echo '    <td style="vertical-align:top;">';
  echo '<table style="width:240px;margin:0px 15px 5px 5px;display:inline-block;">';
  echo '  <tr>';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanban iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanban').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideBacklog" name="productBacklogHideBacklog" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideBacklog)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideBacklog(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideBacklog\');">'.pq_ucfirst(i18n("labelKanbanHideBacklog")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="spintBacklogShowIdle" name="spintBacklogShowIdle" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showIdle)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogShowIdle(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'listShowIdle\');">'.pq_ucfirst(i18n("labelKanbanShowIdle")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogFullWidthElement" name="productBacklogFullWidthElement" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($fullWidthElement)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogFullWidthElement(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogFullWidthElement\');">'.pq_ucfirst(i18n("labelKanbanFullWidthElement")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideEpicItem" name="productBacklogHideEpicItem" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideEpicItems)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideEpicItem(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideEpicItem\');">'.pq_ucfirst(i18n("labelBacklogHideEpicItem")).'</span></td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '    <td rowspan="2" style="vertical-align:top;">';
  echo '<table style="width:240px;margin:5px 5px 0px 5pxpx;display:inline-block;">';
  echo '  <tr style="padding:5px;">';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanbanTiles iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanbanTiles').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideStatus" name="productBacklogHideStatus" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideStatus)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideStatus(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideStatus\');">'.pq_ucfirst(i18n("labelKanbanHideStatus")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideEpic" name="productBacklogHideEpic" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideEpic)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideEpic(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideEpic\');">'.pq_ucfirst(i18n("labelBacklogHideEpic")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideSprint" name="productBacklogHideSprint" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideSprint)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideSprint(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideSprint\');">'.pq_ucfirst(i18n("labelBacklogHideSprint")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideProduct" name="productBacklogHideProduct" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideProduct)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideProduct(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideProduct\');">'.pq_ucfirst(i18n("labelKanbanHideProduct")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideResponsible" name="productBacklogHideProduct" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideResponsible)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideResponsible(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideResponsible\');">'.pq_ucfirst(i18n("labelKanbanHideResponsible")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideStoryPointsAndBusiness" name="productBacklogHideStoryPointsAndBusiness" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideStoryPointsAndBusiness)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideStoryPointsAndBusiness(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideStoryPointsAndBusiness\');">'.pq_ucfirst(i18n("labelKanbanHidePointsAndBusiness")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideType" name="productBacklogHideType" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideType)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideType(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideType\');">'.pq_ucfirst(i18n("labelKanbanHideType")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideScrumPriority" name="productBacklogHideScrumPriority" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideScrumPriority)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideScrumPriority(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideScrumPriority\');">'.pq_ucfirst(i18n("labelKanbanHideScrumPriority")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="productBacklogHideProjectName" name="productBacklogHideProjectName" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideProjectName)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          productBacklogHideProjectName(this.value)';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'productBacklogHideProjectName\');">'.pq_ucfirst(i18n("labelKanbanHideProjectName")).'</span></td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="vertical-align:top;">';
  echo '<table style="width:240px;margin:5px 15px 0px 5px;display:inline-block;">';
  echo '  <tr>';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanbanManagement iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanbanManagement').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td colspan="2">';
  echo '      <table style="width:100%;text-align:center;margin-top: 5px;">';
  echo '        <tr>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
  echo '            onclick="addSprintFromBacklog()">'.formatIcon('Sprint',32,i18n('addSprintBacklog')).'</div>';
  echo '          </td>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
  echo '            onclick="addEpicFromBacklog()">'.formatIcon('Epic',32,i18n('addEpicBacklog')).'</div>';
  echo '          </td>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
  echo '            onclick="addUserStoryFromBacklog()">'.formatIcon('UserStory',32, i18n('addUserStoryBacklog')).'</div>';
  echo '          </td>';
  echo '        </tr>';
  echo '        <tr>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('addSprintBacklog').'</td>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('addEpicBacklog').'</td>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('addUserStoryBacklog').'</td>';
  echo '        </tr>';
  echo '      </table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
}
?>