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

require_once "../tool/projeqtor.php";
scriptLog('   ->/view/abacusPhaseMain.php');

$currentScreen='AbacusPhase';
setSessionValue('currentScreen', $currentScreen);
$abacusPhasing = new Phasing();
$selectedPhasingId = getSessionValue('listAbacusPhaseFilter');

$width=RequestHandler::getValue('destinationWidth');
$displayWidthList = 1980;
if (RequestHandler::isCodeSet('destinationWidth')) {
  $displayWidthList = RequestHandler::getNumeric('destinationWidth');
}

$referenceWidth = 50;
if ($displayWidthList < 1400) {
  $referenceWidth = 40;
  if ($displayWidthList < 1250) {
    $referenceWidth = 30;
  }
}
?>
<input type="hidden" name="objectClassManual" id="objectClassManual" value="AbacusPhase" />
<input type="hidden" name="phase" id="phase" value="true" />
  <div id="mainDivContainer" class="container" dojoType="dijit.layout.BorderContainer" onclick="hideDependencyRightClick();">
    <div id="listDiv" dojoType="dijit.layout.ContentPane" region="center" splitter="true" style="overflow-y: none;">
      <div dojoType="dijit.layout.ContentPane" region="center" id="listHeaderDiv" style="width: 100%;">
        <form dojoType="dijit.form.Form" name="abacusPhaseListForm" id="abacusPhaseListForm" action="" method="post">
          <div style="<?php echo ($width)?'max-width:'.$width.'px; overflow-x:auto':'';?>">
          <table width="100%" class="listTitle">
            <tr>
              <td width="5px" style="padding-left:5px;vertical-align:top" align="center">
                <div style="position: absolute; left: 5px; width: 32px; top: 36px; height: 32px;" class="iconHighlight">&nbsp;</div>
                <div style="position:relative; top:2px;left:3px" class="icon<?php echo $currentScreen;?>32 icon<?php echo $currentScreen;?> iconSize32"></div>
              </td>
              <td width="5px" style="vertical-align:top" class="title">
                <div style="width: 100%; height: 100%;position: relative;">
                  <div id="menuName" style="width: 100%;text-overflow: ellipsis; overflow: hidden;position:relative; top:7px;left:5px">
                    <span id="classNameSpan" style="padding-left: 5px;"><?php echo i18n("menuAbacusPhase");?></span>
                  </div>
                </div>
              </td>

              <td style="text-align:center; vertical-align:middle;">
                <div style="display:flex; justify-content:center; align-items:center; gap:10px;">
                  <span class="nobr">&nbsp;&nbsp;&nbsp; <?php echo i18n("colPhasing");?> &nbsp;</span>
                    <select id="listAbacusPhaseFilter" name="listAbacusPhaseFilter" title="<?php echo i18n('filterOnAbacusPhasing')?>" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect"
                      <?php echo autoOpenFilteringSelect();?> data-dojo-props="queryExpr: '*${0}*',autoComplete:false" style="width:<?php echo $referenceWidth*4;?>px"
                      value="<?php echo $selectedPhasingId ? htmlEncode($selectedPhasingId) : ''; ?>">
                      <option value=""></option>
                      <?php 
                      $abacusPhasingList = $abacusPhasing->getSqlElementsFromCriteria(array('idle' => '0'), false, null, 'name ASC');
                      foreach ($abacusPhasingList as $phasing) {
                        echo '<option value="' . $phasing->id . '" >' . htmlEncode($phasing->name) . '</option>';
                      }?>
                    <script type="dojo/method" event="onChange">
                      actionOK = function() {
                        var callBack = function() { 
                          loadAbacusPhases(); 
                        };
                        saveDataToSession('listAbacusPhaseFilter', dijit.byId('listAbacusPhaseFilter').value, false, callBack);
                      };
                      actionCancel = function() {
                        this.set('value', '<?php echo $selectedPhasingId ? htmlEncode($selectedPhasingId) : ''; ?>');
                      };
                      actionSave = function() {
                        saveAbacusPhase();
                        var callBack = function() { 
                          loadAbacusPhases(); 
                        };
                        saveDataToSession('listAbacusPhaseFilter', dijit.byId('listAbacusPhaseFilter').value, false, callBack);
                      };
                      checkFormChangeInProgress(actionOK, actionCancel, actionSave);
                    </script>
                   </select>
                  <button id="managePhaseButton" dojoType="dijit.form.Button" showlabel="false" title="<?php echo i18n('buttonManagePhase');?>"
                    iconClass="imageColorNewGui iconButtonEdit22 iconButtonEdit iconSize22" class="notButton">
                    <script type="dojo/connect" event="onClick" args="evt">
                      loadDialog('dialogPhasing', null, true);
                    </script>
                  </button>
              
                </div>
              </td>
              
              <td style="text-align:right;width:25px;padding:0px 0px 0px 5px">
                <button id="cancelAbacusPhaseButton" dojoType="dijit.form.Button" showlabel="false" title="<?php echo i18n('buttonCancel');?>" iconClass="dijitButtonIcon dijitButtonIconUndo" class="notButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                    cancelAbacusPhase();
                  </script>
                </button>
              </td>
              <td style="text-align:right;width:25px;padding:0px 15px 0px 5px">
                <button id="saveAbacusPhaseButton" dojoType="dijit.form.Button" showlabel="false" title="<?php echo i18n('buttonSaveForQuestionNoSave');?>" iconClass="dijitButtonIcon dijitButtonIconSave" class="notButton">
                  <script type="dojo/connect" event="onClick" args="evt">
                    saveAbacusPhase();
                  </script>
                </button>
              </td>
            </tr>
          </table>
          </div>
        </form>
      </div>
      <div id="abacusPhaseDivView" dojoType="dijit.layout.BorderContainer" name="abacusPhaseDivView" style="height: 100%">
        <div id="abacusPhaseListDiv" class="container" region="center" dojoType="dijit.layout.ContentPane" style="height:95%;width:100%;padding-top:10px;overflow:auto !important;">
            <?php include 'abacusPhaseView.php'?>
        </div>
      </div>
    </div>
  </div>

<div id="dialogPhase" dojoType="dijit.Dialog" title="<?php echo i18n('dialogPhaseTitle'); ?>" style="display: none;">
  <div id="phaseDialogContent" style=""></div>
</div>