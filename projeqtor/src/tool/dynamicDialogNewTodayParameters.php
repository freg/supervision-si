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

$today=new Today();
  $crit=array('idUser'=>$user->id);
  $todayList=$today->getSqlElementsFromCriteria($crit, false,null, 'sortOrder asc');
  $cptStatic=0;
  foreach ($todayList as $todayItem) {
    if ($todayItem->scope=='newGui') {$cptStatic+=1;}
  }
  if ($cptStatic!=count(Today::$staticList)) {
    Today::insertStaticItems();
    $todayList=$today->getSqlElementsFromCriteria($crit, false, null,'sortOrder asc');
  }
  $user=getSessionUser();
  $profile=SqlList::getFieldFromId('Profile', $user->idProfile, 'profileCode',false);
  echo '<form dojoType="dijit.form.Form" id="todayParametersForm" name="todayParametersForm" onSubmit="return false;"><div class="container"  style="max-height:600px;overflow-y:auto;margin:unset;padding:5px;">';
  echo '<table style="width:100%;max-width:500px">';
  echo '<table id="dndTodayParameters" jsId="dndTodayParameters" dojotype="dojo.dnd.Source" dndType="today"
               withhandles="true" class="container" style="height:10px;width:100%;max-width:500px;cellspacing:0; cellpadding:0;">';
  echo '<tr><td class="dialogSection section" colspan="5">'.i18n('listTodayItems').'</td></tr>';
  echo '<tr><td colspan="5">&nbsp;</td></tr>';
  foreach ($todayList as $todayItem) {
     if ($todayItem->scope!='newGui' and $todayItem->scope!='report')continue;
    if ($todayItem->scope=='newGui') {
      //if ($todayItem->staticSection=='Documents' and !securityCheckDisplayMenu(null, 'Document')) continue;
      if ($todayItem->staticSection=='AssignedTasks' and !securityCheckDisplayMenu(null, 'Activity') and !!securityCheckDisplayMenu(null, 'Meeting') ) continue;
      if ($todayItem->staticSection=='AccountableTasks' and !getSessionUser()->isResource) continue;
      if ($todayItem->staticSection=='ResponsibleTasks' and !getSessionUser()->isResource) continue;
      if($todayItem->staticSection=='ResponsibleTodoList' and !Module::isModuleActive('moduleTodoList'))continue;
      if ($todayItem->staticSection=='AssignedTasks'){
        $showSubTask=false;
        foreach ($user->getAllProfiles() as $prof) {
          $showSubTaskObj=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$prof,'scope'=>'subtask'));
          if ($showSubTaskObj and $showSubTaskObj->id and $showSubTaskObj->rightAccess=='1') {
            $showSubTask=true;
          }
        }
        if (!$showSubTask) continue;
      }
    }
    if (($todayItem->scope!="newGui" or $todayItem->staticSection!="ProjectsTasks" or $profile=='PL') and $todayItem->staticSection!='Projects') {
      echo '<tr id="dialogTodayParametersRow' . htmlEncode($todayItem->id). '"
                class="dojoDndItem" dndType="today" style="height:10px;">';
      //echo '<td class="dojoDndHandle handleCursor"><img style="width:6px" src="css/images/iconDrag.gif" />&nbsp;</td>';
      echo '<td>&nbsp;</td>';
      echo '<input type="hidden" name="dialogTodayParametersDelete' . htmlEncode($todayItem->id). '" id="dialogTodayParametersDelete' . htmlEncode($todayItem->id). '" value="0" />';
      echo '<td style="height:10px;">';
      if ($todayItem->scope!='static' and $todayItem->scope!='newGui') {
        echo "<div style='width:24px;".((isNewGui())?'position:relative;top:0px;':'')."'>";
        $image=(isNewGui())?'../view/css/customIcons/new/iconRemove.svg':'../view/css/images/smallButtonRemove.png';
        echo '<img class="roundedButtonSmall imageColorNewGui iconSize16" src="'.$image.'" onClick="setTodayParameterDeleted(' . htmlEncode($todayItem->id). ');" />';
        echo "</div>";
      }
      echo '</td>';
//       echo '<td style="width:16px;height:10px;"><div name="dialogTodayParametersIdle' . htmlEncode($todayItem->id). '" 
//                  dojoType="dijit.form.CheckBox" type="checkbox" '.(($todayItem->idle=='0')?' checked="checked"':'').'>
//                 </div>'.'</td>';
//       echo '<td>';
      
      
      echo '<td> <div id="dialogTodayParametersIdle'.htmlEncode($todayItem->id).'" 
                      leftLabel="" rightLabel="" style="width:25px;"
                      name="dialogTodayParametersIdle'.htmlEncode($todayItem->id). '"
                      class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                      '.(($todayItem->idle=='0')?'value="on"':'value="off"').'>
                </div></td>';
      echo'<td>&nbsp;&nbsp;</td>';
      echo '<td style="padding-bottom:4px;">';
      
      
      if ($todayItem->scope=="newGui") {
        if($todayItem->staticSection=='Documents'){
          echo "<span class='nobr'>".i18n('TodayApprovers')."</span>";
        }else if ($todayItem->idReport){
          $rpt=new Report($todayItem->idReport);
          echo "<table><tr><td>";
          echo "<span class='nobr'>".i18n('colReport').' "'.i18n($rpt->name).'"</span>';
          echo "</td><td>&nbsp;&nbsp;&nbsp;</td><td style='font-size:80%'>";
          $params=TodayParameter::returnTodayReportParameters($todayItem);
          ReportParameter::displayParameters($params);
          echo "</td></tr></table>";
        }else{
          echo "<span class='nobr'>".i18n('today'.$todayItem->staticSection)."</span>";
        }
      }  else {
        echo "unknown today scope";
      }
      echo '<input type="hidden" style="width:100px" 
       id="dialogTodayParametersOrder' . htmlEncode($todayItem->id). '" name="dialogTodayParametersOrder' . htmlEncode($todayItem->id). '" 
       value="' . htmlEncode($todayItem->sortOrder). '"/>';
      echo '</td>';
      echo '</tr>';
    }else if($todayItem->staticSection=='Projects'){
      echo '<tr id="dialogTodayParametersRow' . htmlEncode($todayItem->id). '" style="height:10px;">';
      echo '<td >&nbsp;</td>';
      echo '<input type="hidden" name="dialogTodayParametersDelete' . htmlEncode($todayItem->id). '" id="dialogTodayParametersDelete' . htmlEncode($todayItem->id). '" value="0" />';
      echo '<td style="height:10px;">';
      echo '</td>';
//       echo '<td style="width:16px;height:10px;"><div name="dialogTodayParametersIdle' . htmlEncode($todayItem->id). '"
//                  dojoType="dijit.form.CheckBox" type="checkbox" '.(($todayItem->idle=='0')?' checked="checked"':'').'>
//                 </div>'.'</td>';
//       echo '<td>';
      
      echo '<td> <div id="dialogTodayParametersIdle'.htmlEncode($todayItem->id).'"
                      leftLabel="" rightLabel="" style="width:25px;"
                      name="dialogTodayParametersIdle'.htmlEncode($todayItem->id). '"
                      class="colorSwitch" data-dojo-type="dojox/mobile/Switch"
                      '.(($todayItem->idle=='0')?'value="on"':'value="off"').'>
                </div></td>';
      echo'<td>&nbsp;</td>';
      echo '<td style="padding-bottom:4px;">';
      
      
      if ($todayItem->scope=="newGui") {
        echo "<span class='nobr'>".i18n('today'.$todayItem->staticSection)."</span>";
      } 
      echo '<input type="hidden" style="width:100px"
       id="dialogTodayParametersOrder' . htmlEncode($todayItem->id). '" name="dialogTodayParametersOrder' . htmlEncode($todayItem->id). '"
       value="' . htmlEncode($todayItem->sortOrder). '"/>';
      echo '</td>';
      echo '</tr>';
    }
  }
  echo '</table>'; 
  echo '<table style="width:100%">';
   echo '<tr style="border-bottom:2px solid #F0F0F0;"><td></td><td>&nbsp;</td></tr>';
  echo '<tr style="height:10px;"><td></td><td>&nbsp;</td></tr>';
  echo '</table>';
  echo '<table width="100%">';
  echo '  <tr style="height:10px;">';
  echo '    <td align="center">';
  ?>
    <button id="resetTodayDiv" dojoType="dijit.form.Button" showlabel="true"
        title="<?php echo i18n('titleResetList');?>" >
        <span><?php echo i18n('reset');?></span>
              <script type="dojo/connect" event="onClick" args="evt">
                resetTodayDiv();
              </script>
            </button>
    <?php 
  echo '      <button dojoType="dijit.form.Button" onclick="dijit.byId(\'dialogNewTodayParameters\').hide();">';
  echo          i18n("buttonCancel");
  echo '      </button>';
  echo '      <button dojoType="dijit.form.Button" type="submit" id=dialogNewTodayParametersSubmit" onclick="protectDblClick(this);saveTodayParametersSwitch();return false;">';
  echo          i18n("buttonOK");
  echo '      </button>';
  echo '    </td>';
  echo '  </tr>';
  echo '</table></div>';
  echo '</form>';
  ?>