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

require_once "../tool/kanbanConstructPrinc.php";

//function of kanbanView origine
function myKanban($idKanban){
  $kanban = new Kanban($idKanban,true);
  return $kanban->idUser==getSessionUser()->id;
}

function kanbanListSelect($user,$name,$type,$idKanban) {
  global $typeKanbanC;
  $kanban=new Kanban();
  $mineList=$kanban->getSqlElementsFromCriteria(null, false," idUser=$user->id ");
  $res= new Resource();
  $reTable= $res->getDatabaseTableName();
  $clauseWhere=" idUser in (Select id from $reTable where id!=$user->id and idle=0 ) AND isShared=1 ";
  $kanbanList=$kanban->getSqlElementsFromCriteria(null, false,$clauseWhere, "idUser ASC");
  $kanbanName = ($idKanban != -1)?SqlList::getNameFromId('Kanban', $idKanban, false):i18n("noKanbanSelected");
  // Display Result
  echo '<div style="float:left;">
            <div dojoType="dijit.form.DropDownButton"
              style="min-width:75px;height:24px;margin:0 auto;color:#000;float:left;margin-right:15px;'.(($idKanban == -1)?'font-style:italic;':'').'"
              id="kanbanListSelect" name="entity">
              <span>'.$kanbanName.'</span>
                <div data-dojo-type="dijit/TooltipDialog">';
  $iterateur=0;
  echo '<span class="kanbanTextTitle" style="float:left;height:15px;font-weight:bold;" disabled="disabled" value="-2" '
      . ' title="' . i18n("kanbanSelectKanban") . '" >'.i18n("kanbanMine").'</span><br/>';
  if(count($mineList)==0)echo '<span disabled="disabled" onclick="dijit.byId(\'kanbanListSelect\').closeDropDown();" style="float:left;height:15px;" '
      . ' >&nbsp;&nbsp;&nbsp;&nbsp;'.i18n('noDataFound').'</span><br/>';
  echo '<div style="position:absolute;top:20px;right:'. (empty($mineList) ? '10' : '70') .'px;"';
  echo 'onclick="loadDialog(\'dialogKanbanUpdate\', function(){kanbanFindTitle(\'addKanban\');}, true, \'&typeDynamic=addKanban\', true, false);" title="'.i18n('kanbanAdd').'">'.formatSmallButton('KanbanAdd',true).'</div>';
  foreach ($mineList as $line) {
    $jsonDecode=json_decode($line->param,true);
    if(!isset($jsonDecode['typeData'])){
      $jsonDecode['typeData']='Ticket';
      $line->param=json_encode($jsonDecode);
      $line->save();
    }
    $typeKanbanCTmp=$jsonDecode['typeData'];
    if (isNewGui()) echo '<div style="margin-top:5px">';
    echo '
    <div class="imageColorNewGuiNoSelection icon'.$typeKanbanCTmp.'16 icon'.$typeKanbanCTmp.' iconSize16" style="width:16px;height:16px;float:left"></div>
    <span onclick="kanbanGoToKan('.$line->id.');dijit.byId(\'kanbanListSelect\').closeDropDown();" class="kanbanMenuTree" style="float:left;height:15px;'.((isNewGui())?'position:relative;top:-2px;':'').'" '
        . ' >&nbsp;&nbsp'
            . htmlEncode($line->name)
            . "</span>";
    echo '  <a class="" onClick="copyKanban('.$line->id.')" title="' . i18n('kanbanCopy'). '" >'
        .formatSmallButton('Copy')
        .'</a> ';
    echo '  <a class="" onClick="editKanban('.$line->id.')" title="' . i18n('kanbanEdit'). '" >'
        .formatSmallButton('Edit')
        .'</a> ';
    if($line->isShared==0) echo '  <a class="" onClick="kanbanShared('.$line->id.')" title="' . i18n('kanbanShare'). '" >'
        .formatSmallButton('Share')
        .'</a> ';
    if($line->isShared==1) echo '  <a class="" onClick="kanbanShared('.$line->id.')" title="' . i18n('kanbanUnshare'). '" >'
        .formatSmallButton('Shared')
        .'</a> ';
    echo '  <a class="" onClick="delKanban('.$line->id.', \''.i18n("kanbanDel").'\')" title="' . i18n('kanbanDelete'). '" >'
        .formatSmallButton('Remove')
        .'</a> ';
    if (isNewGui()) echo '</div>';
    else echo "<br/>";
  }
  echo '<span style="float:left;height:15px;" value="-1" '
      . ' title="' . i18n("kanbanSelectKanban") . '" ></span><br/>';
  echo '<span class="kanbanTextTitle" style="float:left;height:15px;font-weight:bold;" disabled="disabled" value="-2" '
      . ' title="' . i18n("kanbanSelectKanban") . '" >'.i18n("kanbanShared").'</span><br/>';
  if(count($kanbanList)==0)echo '<span disabled="disabled" onclick="dijit.byId(\'kanbanListSelect\').closeDropDown();" style="float:left;height:15px;" '
      . ' >&nbsp;&nbsp;&nbsp;&nbsp;'.i18n('noDataFound').'</span><br/><br/>';
  $lastUser="";
  foreach ($kanbanList as $line) {
    if($lastUser!=$line->idUser){
      $lastUser=$line->idUser;
      echo '<div style="width:100%;height:18px;" ><span class="kanbanTextTitle" style="float:left;height:15px;font-weight:bold;margin-top:4px;">'.htmlEncode(SqlList::getNameFromId('Affectable', $lastUser)).'</span></div>';
    }
    $jsonDecode=json_decode($line->param,true);
    if(!isset($jsonDecode['typeData'])){
      $jsonDecode['typeData']='Ticket';
      $line->param=json_encode($jsonDecode);
      $line->save();
    }
    $typeKanbanCTmp=$jsonDecode['typeData'];
    if (isNewGui()) echo '<div style="margin-top:5px">';
    echo '
        <div class="imageColorNewGuiNoSelection icon'.$typeKanbanCTmp.'16 icon'.$typeKanbanCTmp.' iconSize16" style="width:16px;height:16px;float:left;"></div>
        <span onclick="kanbanGoToKan('.$line->id.');dijit.byId(\'kanbanListSelect\').closeDropDown();" class="kanbanMenuTree" style="float:left;height:15px;'.((isNewGui())?'position:relative;top:-2px;':'').'" '
            . ' >&nbsp;&nbsp'
                . htmlEncode($line->name)
                . "</span>";
    echo '  <a onClick="copyKanban('.$line->id.')" title="' . i18n('kanbanCopy'). '" class="">'
        .formatSmallButton('Copy')
        .'</a> ';
    if (isNewGui()) echo '</div>';
    else echo "<br/>";
  }
  echo "</div></div>";
  // }
}

function kanbanParameterList($idKanban){
  global $typeKanbanC, $type;
  $seeWork=Parameter::getUserParameter("kanbanSeeWork");
  $seeWork=($seeWork=='on' or $seeWork=='1')?true:false;
  if($seeWork && PlanningElement::getWorkVisibiliy(getSessionUser()->idProfile)=="ALL")$seeWork=true; else $seeWork=false;
  if ($typeKanbanC=='Requirement' or $typeKanbanC=='Action'){
    $seeWork=false;
    Parameter::storeUserParameter("kanbanSeeWork", $seeWork);
  }

  $showIdle = Parameter::getUserParameter("kanbanShowIdle");
  $showIdle = ($showIdle=='on' or $showIdle=='1')?true:false;

  $fullWidthElement = Parameter::getUserParameter("kanbanFullWidthElement");
  $fullWidthElement = ($fullWidthElement=='on' or $fullWidthElement=='1')?true:false;

  $hideBacklog = Parameter::getUserParameter("kanbanHideBacklog");
  $hideBacklog = ($hideBacklog=='' or $hideBacklog=='on' or $hideBacklog=='1')?true:false;

  $hideParentActivities = Parameter::getUserParameter("kanbanHideParentActivities");
  $hideParentActivities = ($hideParentActivities=='on' or $hideParentActivities=='1')?true:false;

  $hideStatus = Parameter::getUserParameter("kanbanHideStatus");
  $hideStatus = ($hideStatus=='on' or $hideStatus=='')?true:false;

  $hideProduct = Parameter::getUserParameter("kanbanHideProduct");
  $hideProduct = ($hideProduct=='on' or $hideProduct=='')?true:false;

  $hideActivityPlanning = Parameter::getUserParameter("kanbanHideActivityPlanning");
  $hideActivityPlanning = ($hideActivityPlanning=='on' or $hideActivityPlanning=='')?true:false;

  $hideResponsible = Parameter::getUserParameter("kanbanHideResponsible");
  $hideResponsible = ($hideResponsible=='on' or $hideResponsible=='')?true:false;

  $hidePriority = Parameter::getUserParameter("kanbanHidePriority");
  $hidePriority = ($hidePriority=='on' or $hidePriority=='')?true:false;

  $hideCriticality = Parameter::getUserParameter("kanbanHideCriticality");
  $hideCriticality = ($hideCriticality=='on' or $hideCriticality=='')?true:false;

  $hidePlannedDate = Parameter::getUserParameter("kanbanHidePlannedDate");
  $hidePlannedDate = ($hidePlannedDate=='on' or $hidePlannedDate=='')?true:false;

  $hidedeType = Parameter::getUserParameter("kanbanHideType");
  $hidedeType = ($hidedeType=='on' or $hidedeType=='')?true:false;

  $hideProjectName = Parameter::getUserParameter("kanbanHideProjectName");
  $hideProjectName = ($hideProjectName=='on' or $hideProjectName=='')?true:false;

  $modeColorTitle = Parameter::getUserParameter( "kanbanModeColorTitle" . Parameter::getUserParameter("kanbanIdKanban") );
  $modeColorTitle = (!$modeColorTitle)? 'noColor' : $modeColorTitle;

  $hideColorTitle = Parameter::getUserParameter("kanbanHideColorTitle");
  $hideColorTitle = ($hideColorTitle=='on')?true:false;
  
  $showColorOnTitleOrFullTile = Parameter::getUserParameter("kanbanColorOnTitleOrFullTile");
  $showColorOnTitleOrFullTile = ($showColorOnTitleOrFullTile=='on')?true:false;

  echo '<table style="width:100%;">';
  echo '  <tr>';
  echo '    <td style="vertical-align:top;">';
  echo '<table style="width:250px;margin:5px 15px 5px 5px;display:inline-block;">';
  echo '  <tr>';
  echo '    <td style="width:40px;"><div class="iconDisplayOnKanban iconSize32 imageColorNewGuiNoSelection" style="border:0"></div></td>';
  echo '    <td class="dependencyHeader planningDialogTitle" style="width:200px;text-align:left;padding-left: 5px;">'.i18n('displayOnKanban').'</td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:10px;">';
  echo '      <div id="kanbanSeeWork" name="kanbanSeeWork" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($seeWork)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideWorks(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanSeeWork\');">'.pq_ucfirst(i18n("kanbanSeeWork")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanShowIdle" name="kanbanShowIdle" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showIdle)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanShowIdle(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'listShowIdle\');">'.pq_ucfirst(i18n("labelKanbanShowIdle")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanFullWidthElement" name="kanbanFullWidthElement" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($fullWidthElement)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanFullWidthElement(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanFullWidthElement\');">'.pq_ucfirst(i18n("labelKanbanFullWidthElement")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHideBacklog" name="kanbanHideBacklog" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideBacklog)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideBacklog(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideBacklog\');">'.pq_ucfirst(i18n("labelKanbanHideBacklog")).'</span></td>';
  echo '  </tr>';
  if($typeKanbanC == 'Activity'){
    echo '  <tr>';
    echo '    <td style="padding-top:2px;">';
    echo '      <div id="kanbanHideParentActivities" name="kanbanHideParentActivities" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideParentActivities)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
    echo '        <script type="dojo/method" event="onStateChanged" >';
    echo '          kanbanHideParentActivities(this.value);';
    echo '        </script>';
    echo '      </div>';
    echo '    </td>';
    echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideParentActivities\');">'.pq_ucfirst(i18n("labelKanbanHideParentActivities")).'</span></td>';
    echo '  </tr>';
  }
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
  echo '      <div id="kanbanHideStatus" name="kanbanHideStatus" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideStatus)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideStatus(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideStatus\');">'.pq_ucfirst(i18n("labelKanbanHideStatus")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHideProduct" name="kanbanHideProduct" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideProduct)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideProduct(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideProduct\');">'.pq_ucfirst(i18n("labelKanbanHideProduct")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHideActivityPlanning" name="kanbanHideActivityPlanning" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideActivityPlanning)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideActivityPlanning(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideActivityPlanning\');">'.pq_ucfirst(i18n("labelKanbanHideActivityPlanning")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHideResponsible" name="kanbanHideProduct" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideResponsible)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideResponsible(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideResponsible\');">'.pq_ucfirst(i18n("labelKanbanHideResponsible")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHidePriority" name="kanbanHidePriority" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hidePriority)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHidePriority(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHidePriority\');">'.pq_ucfirst(i18n("labelKanbanHidePriority")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
echo '      <div id="kanbanHideCriticality" name="kanbanHideProduct" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideCriticality)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideUrgency(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideCriticality\');">'.pq_ucfirst(i18n("labelKanbanHideUrgency")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHidePlannedDate" name="kanbanHidePlannedDate" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hidePlannedDate)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHidePlannedDate(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHidePlannedDate\');">'.pq_ucfirst(i18n("labelKanbanHidePlannedDate")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHideType" name="kanbanHideType" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hidedeType)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideType(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideType\');">'.pq_ucfirst(i18n("labelKanbanHideType")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHideProjectName" name="kanbanHideProjectName" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideProjectName)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideProjectName(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanHideProjectName\');">'.pq_ucfirst(i18n("labelKanbanHideProjectName")).'</span></td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanHideColorTitle" name="kanbanHideColorTitle" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($hideColorTitle)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanHideColorTitle(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '      <td colspan="2" style="padding-left:5px;"><span class="checkboxLabel" onclick="invertSwitchValue(\'kanbanHideColorTitle\');">'.pq_ucfirst(i18n("labelKanbanHideColorTitle")).'</span>';
  echo '        <select id="kanbanModeColorTitle" name="kanbanModeColorTitle" class="comboButton" dojoType="dijit.form.FilteringSelect" style="width:75px;" value="'.$modeColorTitle.'">';
  $arrOpt=array(
      "noColor"=>" ",
      "colorProject"=>'Replan',
      "colorItem"=>'sectionActivity',
      "colorPlanned"=>'plannedColor',
      "colorType"=>'colType',
      "colorPriority"=>'colPriority',
      "colorUrgency"=>"colUrgency");
  foreach ($arrOpt as $key=>$val){
    if ($key == 'noColor') {
      $label = '&nbsp;';
    } else {
      $label = ucfirst(i18n($val));
    }
    if ($key == 'colorItem' && $typeKanbanC != 'Activity') continue;
    if ($key == 'colorPlanned' && $typeKanbanC != 'Activity') continue;
    if ($key == 'colorUrgency' && ($typeKanbanC == 'Activity' || $typeKanbanC == 'Action')) continue;
    if ($key == 'colorPriority' && $typeKanbanC == 'Activity') continue;
    if ($key == 'colorType' && ($typeKanbanC == 'Action' || $typeKanbanC == 'Ticket' || $typeKanbanC == 'Requirement')) continue;
    echo '        <option value="'.$key.'">'.$label.'</option>';
  }
  echo '        <script type="dojo/method" event="onChange" >';
  echo '          kanbanModeColorTitle(this.value);';
  echo '          if (this.value == "noColor") {';
  echo '            dijit.byId("kanbanHideColorTitle").set("value", "off");';
  //echo '            saveDataToSession("kanbanHideColorTitle","off",true);';
  echo '          } else {';
  echo '            dijit.byId("kanbanHideColorTitle").set("value", "on");';
  //echo '            saveDataToSession("kanbanHideColorTitle","on",true);';
  echo '          }';
  echo '        </script>';
  echo '        </select>';
  echo '      </td>';
  echo '  </tr>';
  echo '  <tr>';
  echo '    <td style="padding-top:2px;">';
  echo '      <div id="kanbanColorOnTitleOrFullTile" name="kanbanColorOnTitleOrFullTile" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" '.(($showColorOnTitleOrFullTile)?'value="on"':'value="off"').' leftLabel="" rightLabel="" style="width:25px;">';
  echo '        <script type="dojo/method" event="onStateChanged" >';
  echo '          kanbanColorOnTitleOrFullTile(this.value);';
  echo '        </script>';
  echo '      </div>';
  echo '    </td>';
  echo '    <td style="padding-left:5px;" class="checkboxLabel"><span onclick="invertSwitchValue(\'kanbanColorOnTitleOrFullTile\');">'.pq_ucfirst(i18n("labelkanbanColorOnTitleOrFullTile")).'</span></td>';
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
  if($idKanban!=-1){
    echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
    echo '            onclick="addKanbanFromKanban();">'.formatIcon('KanbanAdd',32,i18n('kanbanAdd')).'</div>';
  }
  echo '          </td>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  if($idKanban!=-1 && myKanban($idKanban)){
    echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
    echo '            onclick="managedKanbanColumn('.$idKanban.',\''.$type.'\');">'.formatIcon('KanbanAddColumns',32,i18n('kanbanAddColumn')).'</div>';
  }
  echo '          </td>';
  echo '          <td style="width:80px;text-align:center;vertical-align:top;">';
  if($idKanban!=-1){
    echo '          <div dojoType="dijit.form.Button" class="detailButton" style="position:relative;cursor:pointer;padding-right: 5px"';
    echo '            onclick="addItemFromKanban(\''.$typeKanbanC.'\');">'.formatIcon('KanbanAdd'.$typeKanbanC,32, i18n('kanbanAdd'.$typeKanbanC)).'</div>';
  }
  echo '          </td>';
  echo '        </tr>';
  echo '        <tr>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('kanbanAddShort').'</td>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('kanbanAddColumnShort').'</td>';
  echo '          <td style="font-size:80%;color:#a0a0a0;vertical-align: top;">'.i18n('kanbanAdd'.$typeKanbanC.'Short').'</td>';
  echo '        </tr>';
  echo '      </table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table>';
}

function getLastStatus(){
  $status=new Status();
  $tableName=$status->getDatabaseTableName();
  $result=Sql::query("SELECT t.id as id
      FROM $tableName t where idle=0 order by t.sortOrder desc");
  while ($line = Sql::fetchLine($result)) {
    return $line["id"];
  }
  return '';
}

function drawColumnKanban($type,$jsonD,$idKanban){
  global $typeKanbanC;
  $statusList=SqlList::getList('Status','name',null,true);
  $allowedStatus=array();
  $kanbanFullWidthElement = Parameter::getUserParameter ( "kanbanFullWidthElement" );
  $hideBacklog = (Parameter::getUserParameter ( "kanbanHideBacklog" )=='off' or Parameter::getUserParameter ( "kanbanHideBacklog" )=='0')?1:0;
  
  $seeWork=Parameter::getUserParameter("kanbanSeeWork");
  $seeWork=($seeWork=='on' or $seeWork=='1')?true:false;
  
  if(count($jsonD['column'])!=0){
    $jsonArray=array();
    $keyJsonOrder=array();
    $sortedColumns=array();
    foreach ($jsonD['column'] as $key=>$itemKanban) {
      if($itemKanban['from']=="n")$itemKanban['from']='0';
      $hideParam = "kanbanHideColumn_".$idKanban."_".$itemKanban['from'];
      $itemKanban['hide']=Parameter::getUserParameter($hideParam);
      if($itemKanban['from']!='0'){
        $obj = new $type($itemKanban['from'],true);
        if(isset($obj->sortOrder)){
          $jsonArray[str_pad($obj->sortOrder,5,'0', STR_PAD_LEFT).'-'.$obj->id]=$itemKanban;
        }else{
          $jsonArray[$obj->name.'-'.$obj->id]=$itemKanban;
        }
      }else{
        $jsonArray['00000-'.$itemKanban['from']]=$itemKanban;
      }
    }
    ksort($jsonArray);
    foreach ($jsonArray as $key=>$itemKanban) {
      $keyJsonOrder[]=$key;
      $sortedColumns[]=$itemKanban;
    }
    $isStatus=$type=="Status";
    $mapAccept=array();
    $accept="[";
    $iterateur=0;
    if(!$isStatus){ // Form Kanban on other than Status, Accept is simple : no restriction for moves
      foreach ($jsonD['column'] as $itemKanban) {
        if($itemKanban['from']=="n")$itemKanban['from']='0';
        $accept.='\'column'.$itemKanban['from'].'\'';
        if($iterateur!=count($jsonD['column'])-1)$accept.=',';
      }
    }else{ // For Kanban on Status, Accept must respect workflow, corresponding to user profile
      $user=getSessionUser();
      $mapWorkflow=array();
      for ($i=0;$i<count($sortedColumns);$i++) {
        $itemKanban=$sortedColumns[$i];
        $idFrom=$itemKanban['from'];
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
      //$visibleProjects=pq_explode(',',pq_trim(getVisibleProjectsList(true),'()'));
      foreach ($user->getAllProfiles() as $idProfile){ // For each profile of the user (on any project)
        //$idProfil=$user->getProfile($idProject);
        foreach (SqlList::getList("Status",'id') as $idStatus){ // For every status
          foreach (SqlList::getList($typeKanbanC."Type",'id') as $idTicketType){ // For every type (Ticket type or Activity Type)
            $workflowId=SqlList::getFieldFromId($typeKanbanC."Type", $idTicketType, 'idWorkflow');
            if(!isset($mapWorkflow[$workflowId])){
              $woTmp=new Workflow($workflowId);
              $mapWorkflow[$workflowId]=$woTmp->getWorkflowstatusArray();
            }
            foreach ($jsonD['column'] as $itemKanban) { // For all defined columns on the Kanban (id of status is in the from field
              if($itemKanban['from']=="n")$itemKanban['from']='0';
              foreach ($allowedStatus[$itemKanban['from']] as $idStatusTo) {
                $toPut="";
                if($idStatusTo!=$idStatus) {
                  if(isset($idProfile)
                      && isset($mapWorkflow[$workflowId][$idStatus])
                      && isset($mapWorkflow[$workflowId][$idStatus][$idStatusTo])) {
                        if(isset($mapWorkflow[$workflowId][$idStatus][$idStatusTo][$idProfile])
                            && $mapWorkflow[$workflowId][$idStatus][$idStatusTo][$idProfile]) {
                              $toPut='column'.$idStatus;//.'-'.$idTicketType.'-'.pq_trim($idProfile)
                            }
                      }
                }
                if($toPut!=""){
                  $exist=false;
                  if(isset($mapAccept[$itemKanban['from']]))if(pq_strpos($mapAccept[$itemKanban['from']], $toPut) !== false)$exist=true;
                  if(!$exist){
                    if(!isset($mapAccept[$itemKanban['from']])){
                      $mapAccept[$itemKanban['from']]="'$toPut'";
                    }else{
                      $mapAccept[$itemKanban['from']].=",'$toPut'";
                    }
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
    foreach ($jsonArray as $itemKanban) {
      $nextFrom=$itemKanban['from'];
      if($iterateur<count($jsonArray)-1 && $isStatus){
        $nextFrom=getNextFrom($itemKanban['from'],$jsonArray[$keyJsonOrder[$iterateur+1]]['from'],$type); //bug offset too high
      }else if($isStatus){
        $nextFrom=getLastStatus();
      }
      $nbItems=0;
      $acceptTmp=$accept;
      if(isset($mapAccept[$itemKanban['from']]))$acceptTmp='['.$mapAccept[$itemKanban['from']].']';
      if($type=="Activity")$acceptTmp="['column".SqlList::getFieldFromId("Activity", $itemKanban['from'], "idProject")."']";
      if($itemKanban['from']=="0" || $type=="TargetProductVersion")$acceptTmp="[";
      if($type=="TargetProductVersion")$acceptTmp.="'column0',";
      if($itemKanban['from']=="0" || $type=="TargetProductVersion"){
        $iterateur2=0;
        foreach($jsonD['column'] as $keyy=>$vall){
          if($vall['from']=="n")$vall['from']='0';
          if($vall['from']!='0'){
            if($type=='Activity')$acceptTmp.="'column".SqlList::getFieldFromId('Activity', $vall['from'], 'idProject')."'";
            else $acceptTmp.="'column".$vall['from']."'";
            $iterateur2++;
            if($iterateur2!=count($jsonD['column'])-1)$acceptTmp.=",";
          }
        }
      }
      if($itemKanban['from']=="0" || $type=="TargetProductVersion")$acceptTmp.="]";
      if($type=="Milestone"){
        $projectList = getVisibleProjectsList();
        $projectList = pq_str_replace('(', '', $projectList);
        $projectList = pq_str_replace(')', '', $projectList);
        $arrayIdProj = explode(',', $projectList);
        $arrayColumnProj = array();
        foreach ($arrayIdProj as $idProj){
          $idProj = pq_trim($idProj);
          $arrayColumnProj[]="'column$idProj'";
        }
        $projectList = implode(',', $arrayColumnProj);
        $acceptTmp = "[".$projectList."]";
      }
      $destHeight=RequestHandler::getValue('destinationHeight');
      $destWidth=RequestHandler::getValue('destinationWidth');
      if ($destHeight) {
         $maxHeight=($destHeight-((RequestHandler::getValue('xhrPostDestination')=='divKanbanContainer')?76:161));
         $hidedMaxHeight = $destHeight-101;
         if ($seeWork){
           $maxHeight-=42;
         }else{
           $maxHeight -= 4;
         }
//          if (isNewGui()) $maxHeight-=6;
         $maxHeight.='px';
         $hidedMaxHeight.='px';
      } else {
        $maxHeight='100%';
        $hidedMaxHeight = $maxHeight;
      }
      if ($destWidth) {
        $nbCols=count($jsonD['column']);
        $maxWidth=((($destWidth)/$nbCols)-20)."px";
      } else {
        $maxWidth="332px";
      }
      $minWidth="335px";
      $isHided = $itemKanban['hide'];
      if($isHided){
        $maxWidth="15px";
        $minWidth="15px";
      }
      $name=$itemKanban['name'];
      $from=$itemKanban['from'];
      $titleStyle = 'font-size: 12px;color:#4d4d4d;';
      $backgroundColor = (isNewGui())?'var(--color-light);':'#e2e4e6';
//       if($type == 'Status'){
//         $status = new Status($from);
//         $backgroundColor = $status->color;
//         $titleStyle = 'color:white;text-shadow: #000000 1px 1px 2px;';
//       }
      $columnClass = (isset($itemKanban['cantDelete']) or $name == 'Backlog')?'isBacklogColumn':'';
      //$name = (isset($itemKanban['cantDelete']) or $name == 'Backlog')?'Backlog':$name;
      if($columnClass){
        $backgroundColor = '#9b9b9b';
        $titleStyle = 'color:white;text-shadow: #000000 1px 1px 2px;';
      }
      $nameN=SqlList::getNameFromId(((pq_substr($type,-7)=='Version')?'Version':$type), $from);
      if($name!='')$nameN=$name;
      echo '<td '.(($isHided)?'align="center"':'').' class="'.(($isHided)?'hidedColumn':'').' '.$columnClass.'" style="position:relative;vertical-align:top;width:'.$maxWidth.';min-width:'.$minWidth.';'.(($hideBacklog and $name == 'Backlog')?'display:none;':'').'">';
      if(!$isHided){
        echo '<table style="width:100%;"><tr style="min-height:47px;height:47px;max-height:47px;">';
        echo '<td class="kanbanColumn kanbanColumnHeader" oncontextmenu="openKanbanColumnContextMenu(event,\''.addslashes($typeKanbanC).'\','.intval($from).',\''.addslashes($type).'\',\''.addslashes($nameN).'\');" style="position:relative;background-color:'.((isNewGui())?$backgroundColor.';border-radius:10px 10px 0 0':$backgroundColor).';padding:3px 8px 0px;border-bottom:2px solid #ffffff;min-width:355px;">';
        echo '<div style="margin-bottom:10px;">';
        echo ' <div style="display:flex;margin: 8px 0px 0px;align-items: baseline;">';
        echo '  <div style="font-weight:bold;margin-right: 5px;'.$titleStyle.'">'.htmlEncode($nameN).'</div>';
        if($type == 'Status'){
          //echo '  <div style="font-size: 10px;font-weight:bold;"></div>';
          //         echo '  <div style="font-size: 10px;font-weight:bold;">';
          $colorFrom = SqlList::getFieldFromId('Status', $from, 'color');
          $colorTo = SqlList::getFieldFromId('Status', $nextFrom, 'color');
          $statusTitle = i18n('from').' '.SqlList::getNameFromId($type, $from).' '.i18n("to").' '.SqlList::getNameFromId($type, $nextFrom);
          echo '<div style="display:flex;align-items: center;" title="'.$statusTitle.'">';
          echo    '<div style="margin:2px;width: 70px;text-align: center;" title="'.$statusTitle.'">'.formatColorRounded ($colorFrom, 15  , 8, 'left', $statusTitle, SqlList::getNameFromId ( "Status", $from ), 7).'</div>';
          if($from != $nextFrom){
            echo '<div style="margin:2px;width: 70px;text-align: center;" title="'.$statusTitle.'">'.formatColorRounded ($colorTo, 15  , 8, 'left', $statusTitle, SqlList::getNameFromId ( "Status", $nextFrom ), 7).'</div>';
          }
          echo '</div>';
        }
        echo '</div>';
        echo '<div id="badgeColumnItem'.$from.'" class="sectionBadge">'.$nbItems.'</div>';
        if(myKanban($idKanban)){
          echo '<div class="columnOptionButton" >';
          echo '  <div dojoType="dijit.form.DropDownButton" showlabel="false" class="comboButton detailButton noArrow" iconClass="imageColorNewGui iconOptionsH iconSize22" title="'.i18n('extraButtons').'">';
          echo '    <div dojoType="dijit.TooltipDialog" class="white" tyle="position: absolute; top: 50px; right: 40%">';
          echo '      <table>';
          if(!isset($itemKanban['cantDelete'])){
          echo '        <tr class="contextMenuRow" style="width:100%;" onclick="hideKanbanColumn('.$idKanban.','.$from.', true);">';
          echo '          <td style="padding-top:5px;padding-bottom:5px;">'.formatSmallButton('NoView', false, false).'</td>';
          echo '          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;">'.i18n('kanbanHideColumn').'</td>';
          echo '        </tr>';
          }
          echo '        <tr class="contextMenuRow" style="width:100%;" onclick="editKanbanColumn('.$idKanban.',\''.$type.'\',\''.$from.'\');">';
          echo '          <td style="padding-top:5px;padding-bottom:5px;">'.formatSmallButton('Edit', false, false).'</td>';
          echo '          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;">'.i18n('kanbanColumnEdit').'</td>';
          echo '        </tr>';
          if(!isset($itemKanban['cantDelete'])){
          echo '        <tr class="contextMenuRow" style="width:100%;" onclick="delKanban('.$idKanban.', \''.i18n("kanbanDelColumn").'\','.$from.');">';
          echo '          <td style="padding-top:5px;padding-bottom:5px;">'.formatSmallButton('Remove', false, false).'</td>';
          echo '          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;">'.i18n('kanbanColumnDelete').'</td>';
          echo '        </tr>';
          }
          echo '      </table>';
          echo '    </div>';
          echo '  </div>';
          echo '</div>';
        }
        echo '<div class="backlogItemWorks" style="position: relative;top: 5px;font-size: 11px;'.(($type != 'Status')?'margin-top: 5px;':'').''.(($seeWork)?'':'display:none;').'">';
        echo '  <table style="width: 100%;">';
        echo '    <tr>';
        echo '      <td class="linkHeader" style="padding:3px;cursor:auto;width: 33%;height: 10px !important;border-radius: 6px 0px 0px; 0px;border: unset;border-right: 1px solid #AAAAAA;border-bottom: 1px solid #AAAAAA;">'.i18n('colEstimated').'</td>';
        echo '      <td class="linkHeader" style="padding:3px;cursor:auto;width: 33%;height: 10px !important;border: unset;border-bottom: 1px solid #AAAAAA;border-right: 1px solid #AAAAAA;">'.i18n('colReal').'</td>';
        echo '      <td class="linkHeader" style="padding:3px;cursor:auto;width: 33%;height: 10px !important;border-radius: 0px 6px 0px 0px;border: unset;border-bottom: 1px solid #AAAAAA;">'.i18n('colLeft').'</td>';
        echo '    </tr>';
        echo '    <tr>';
        echo '      <td id="plannedWorkColumn'.$from.'" class="linkData" style="height: 10px !important;color: black;text-shadow: none;font-weight: 400;text-align:center;border: unset;border-right: 1px solid #AAAAAA;">0</td>';
        echo '      <td id="realWorkColumn'.$from.'" class="linkData" style="height: 10px !important;color: black;text-shadow: none;font-weight: 400;text-align:center;border: unset;border-right: 1px solid #AAAAAA;">0</td>';
        echo '      <td id="leftWorkColumn'.$from.'" class="linkData" style="height: 10px !important;color: black;text-shadow: none;font-weight: 400;text-align:center;border: unset;">0</td>';
        echo '    </tr>';
        echo '  </table>';
        echo '</div>';
        echo '</div>';
        echo '</td></tr><tr>';
        echo '
        <td class="kanbanColumn kanbanColumnBody" oncontextmenu="openKanbanColumnContextMenu(event,\''.addslashes($typeKanbanC).'\','.intval($from).',\''.addslashes($type).'\',\''.addslashes($nameN).'\');" style="overflow-y:scroll;overflow-x:hidden;display:block; height:'.$maxHeight.';max-height:'.$maxHeight.'; position:relative;background-color:'.((isNewGui())?'var(--color-light);border:2px solid var(--color-light);border-radius:0 0 10px 10px':'#e2e4e6').';padding:'.(($kanbanFullWidthElement=='on')?'8px':'6px 0px 6px 4px').';width:auto;min-width:355px;" id="kanbanColumn'.$itemKanban['from']. '"
        jsId="kanbanColumn'.$itemKanban['from']. '" columnTarget="'.$itemKanban['from'].'" columnType="'.$type.'" dojotype="dojo.dnd.Source" dndType="column'.$itemKanban['from']. '" withhandles="false"
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
        //getItemsFromTypeIdKanban($itemKanban['from'], $nextFrom, $type,$isStatus,$result,$jsonD);
        echo '</td></tr></table>';
      }else{
        if($columnClass){
          $backgroundColor = '#9b9b9b';
          $titleStyle = 'color:white;text-shadow: #000000 1px 1px 2px;';
        }
        if($type == 'Status' && $from != '0'){
          $statusColor = SqlList::getFieldFromId('Status', $from, 'color');
          if($statusColor){
            $backgroundColor = $statusColor;
            $titleStyle = 'color:'.getForeColor($backgroundColor).';';//text-shadow: #000000 1px 1px 2px;
          }
        }
        echo '<div id="kanbanColumn'.$itemKanban['from']. '" class="kanbanHiddenColumnBar" title="'.i18n('kanbanShowColumn', array($nameN)).'" onclick="hideKanbanColumn('.$idKanban.','.$from.', false);" oncontextmenu="openKanbanColumnContextMenu(event,\''.addslashes($typeKanbanC).'\','.intval($from).',\''.addslashes($type).'\',\''.addslashes($nameN).'\');" style="background-color:'.$backgroundColor.';height:'.$hidedMaxHeight.';"';
        echo 'jsId="kanbanColumn'.$itemKanban['from']. '" columnTarget="'.$itemKanban['from'].'" columnType="'.$type.'" dojotype="dojo.dnd.Source" dndType="column'.$itemKanban['from']. '" withhandles="false"
             '.($acceptTmp!='[]' ? 'data-dojo-props="accept: '.$acceptTmp.',singular:true, horizontal:true, withHandles: false"':'data-dojo-props="singular:true, horizontal:true, withHandles: false"').'>';
        echo '  <span class="kanbanHiddenColumnLabel" style="'.$titleStyle.'">'.htmlEncode($nameN).'</span>';
        echo '</div>';
      }
      echo '</td>';
      $iterateur++;
      $hideSeparator = false;
      if(isset($keyJsonOrder[$iterateur]) and isset($jsonArray[$keyJsonOrder[$iterateur]])){
        $nextColumn = $jsonArray[$keyJsonOrder[$iterateur]];
        if($nextColumn['hide'] or $itemKanban['hide']){
          $hideSeparator=true;
        }
      }
      if ($iterateur<count($jsonArray)) {
        echo '<td class="'.$columnClass.'"  style="position:relative;min-width:10px;max-width:10px;width:10px;'.((($hideBacklog and $name == 'Backlog') or $hideSeparator)?'display:none;':'').'" width="10px"></td>';
      }
    }
  }
}

function getNextFrom($from,$next,$type){
  global $typeKanbanC;
  $min=SqlList::getFieldFromId($type, $from, "sortOrder");

  $obT=new $type();
  $tableName=$obT->getDatabaseTableName();
  if ($type=='Status') {
    $workflowStatus = new WorkflowStatus ();
    $tableName2 = $workflowStatus->getDatabaseTableName ();
    $type = new Type ();
    $tableName3 = $type->getDatabaseTableName ();
    $result = Sql::query ( "SELECT s.id as typen, s.sortOrder as sortorder from $tableName s where s.idle=0 and (s.id in (select idStatusFrom from $tableName2 w, $tableName3 t where t.idWorkflow=w.idWorkflow and t.scope='$typeKanbanC')
        or s.id in (select idStatusTo from $tableName2 w, $tableName3 t where t.idWorkflow=w.idWorkflow and t.scope='$typeKanbanC') ) order by s.sortOrder" );
  } else {
    $result=Sql::query("SELECT t.id as typen, t.sortOrder as sortorder FROM $tableName t WHERE t.sortOrder>=$min order by t.sortOrder ");
  }
  $ite=0;
  $listId=array();
  while ($line = Sql::fetchLine($result)) {
    $listId[]=$line;
  }
  $last=-1;
  foreach($listId as $line){
    if(count($listId)-1!=$ite+1){
      if(isset($listId[$ite+1]) && $listId[$ite+1]['typen']==$next) {
        return $line['typen'];
      }
    }
    $last=$line['typen'];
    $ite++;
  }
  return $last;
}
?>
