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
scriptLog('   ->/view/abacusLineMain.php');

$currentScreen='AbacusLine';
setSessionValue('currentScreen', $currentScreen);

$abacusDef = new AbacusDefinition();
$selectedAbacusId = getSessionValue('listAbacusDefinitionFilter');

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
<input type="hidden" name="objectClassManual" id="objectClassManual" value="AbacusLine" />
<input type="hidden" name="AbacusLine" id="AbacusLine" value="true" />

<div id="mainDivContainer" class="container" dojoType="dijit.layout.BorderContainer" onclick="hideDependencyRightClick();">
  <div id="listDiv" dojoType="dijit.layout.ContentPane" region="center" splitter="true" style="overflow-y: none;">
    <div dojoType="dijit.layout.ContentPane" region="center" id="listHeaderDiv" style="width: 100%;">
      <table width="100%" class="listTitle">
        <tr>
          <td style="width: 38px;" align="center">
            <div style="position: absolute; left: 0px; width: 43px; top: 0px; height: 36px;" class="iconHighlight">&nbsp;</div>
            <div style="position: absolute; top: 2px; left: 5px;" class="icon<?php echo $currentScreen;?>32 icon<?php echo $currentScreen;?> iconSize32"></div>
          </td>
          <td class="title" style="height: 35px; width: 20%;">
            <div style="width: 100%; height: 100%; position: relative;">
              <div id="menuName" style="width: 100%; position: absolute; top: 8px; text-overflow: ellipsis; overflow: hidden;">
                <span id="classNameSpan" style="padding-left: 5px;"><?php echo i18n("menuAbacusLine");?></span>
              </div>
            </div>
          </td>
          
          <td style="vertical-align: middle; text-align: right;" width="5px" class="allSearchTD parentAbacusSearchTD allSearchFixLength">
            <span class="nobr">&nbsp;&nbsp;&nbsp; <?php echo i18n("colAbacus");?> &nbsp;</span>
          </td>
          <td width="5px" class="allSearchTD parentAbacusSearchTD" style="padding:8px;">
            <select id="listAbacusDefinitionFilter" name="listAbacusDefinitionFilter"  type="text" class="filterField roundedLeft" dojoType="dijit.form.FilteringSelect" 
              <?php echo autoOpenFilteringSelect();?> data-dojo-props="queryExpr: '*${0}*',autoComplete:false" style="width:<?php echo $referenceWidth*4;?>px"
                    value="<?php echo $selectedAbacusId ? htmlEncode($selectedAbacusId) : ''; ?>"
              <option value=""></option>
              <?php $abacusDefList = $abacusDef->getSqlElementsFromCriteria(array('idle' => '0'), false, null, 'sortOrder ASC');
                foreach ($abacusDefList as $def) {
                  echo '<option value="' . $def->id . '" >' . htmlEncode($def->name) . '</option>';
              }?>
              <script type="dojo/method" event="onChange">
                  actionOK = function() {
                    var callBack = function() {
		                  formChangeInProgress = false; 
                      loadAbacusLines(dijit.byId('listAbacusDefinitionFilter').value); 
                    };
                    saveDataToSession('listAbacusDefinitionFilter', dijit.byId('listAbacusDefinitionFilter').value, false, callBack);
                  };
                  actionCancel = function() {
                    this.set('value', '<?php echo $selectedAbacusId ? htmlEncode($selectedAbacusId) : ''; ?>');
                  };
                  actionSave = function() {
                    saveAbacusLine();
                    var callBack = function() { 
                      loadAbacusLines(dijit.byId('listAbacusDefinitionFilter').value); 
                    };
                    saveDataToSession('listAbacusDefinitionFilter', dijit.byId('listAbacusDefinitionFilter').value, false, callBack);
                  };
                  checkFormChangeInProgress(actionOK, actionCancel, actionSave);
              </script>
            </select>
          </td>
          <td style="text-align:right;padding:0;">
            <button id="cancelAbacusLineButton" dojoType="dijit.form.Button" showlabel="false" title="<?php echo i18n('buttonCancel');?>" iconClass="dijitButtonIcon dijitButtonIconUndo" class="notButton">
              <script type="dojo/connect" event="onClick" args="evt">
                cancelAbacusLine();
              </script>
            </button>
            <button id="saveAbacusLineButton" dojoType="dijit.form.Button" showlabel="false" title="<?php echo i18n('buttonSaveForQuestionNoSave');?>" iconClass="dijitButtonIcon dijitButtonIconSave" class="notButton" style="margin-left:4px;padding:0px 10px 0px 0px;">
              <script type="dojo/connect" event="onClick" args="evt">
                saveAbacusLine();
              </script>
            </button>
          </td>
        </tr>
      </table>
    </div>

    <div id="abacusLineDivView" dojoType="dijit.layout.ContentPane" name="abacusLineDivView" style="overflow-x: auto; overflow-y:hidden; height: 100%">
      <?php include 'abacusLineView.php';?>
    </div>
  </div>
</div>
