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
 * Shell of the prospection screen : the containers and the filters, the content
 * being drawn once this markup is injected.
 */
  require_once "../tool/projeqtor.php";
  scriptLog('   ->/view/prospectionViewMain.php');

  $currentScreen='ProspectionView';
  setSessionValue('currentScreen', $currentScreen);

  // The filters are kept as user parameters, so leaving the screen does not lose
  // them. An unset one comes back null : cast before it reaches a string function.
  // Trimmed, because the blank entry of a reference list is a space, not an empty
  // string : left as is it passes for a value and htmlDrawOptionForReference then
  // appends a second blank option, selected, at the end of the list.
  $filterName          =trim((string)Parameter::getUserParameter('prospectionViewFilterName'));
  $filterDomain        =trim((string)Parameter::getUserParameter('prospectionViewFilterDomain'));
  $filterSource        =trim((string)Parameter::getUserParameter('prospectionViewFilterSource'));
  $filterQualification =trim((string)Parameter::getUserParameter('prospectionViewFilterQualification'));
  $filterEngagement    =trim((string)Parameter::getUserParameter('prospectionViewFilterEngagement'));
  $filterStatus        =trim((string)Parameter::getUserParameter('prospectionViewFilterStatus'));
  $filterResponsible   =trim((string)Parameter::getUserParameter('prospectionViewFilterResponsible'));

  // Blocs replies, une liste de cles separees par des virgules. Trime comme les
  // filtres : une valeur qui n'est ni vide ni significative ferait des degats.
  $collapsedBlocks     =trim((string)Parameter::getUserParameter('prospectionViewCollapsedBlocks'));

  session_write_close();
?>
<input type="hidden" name="objectClassManual" id="objectClassManual" value="ProspectionView" />
<div id="prospectionViewScreen" class="prospectionViewScreen">

  <div id="prospectionViewTitle" class="listTitle prospectionViewTitle">
    <table style="width:100%;">
      <tr style="vertical-align:middle;">
        <td align="center" style="width:50px;">
          <div style="position:absolute;top:2px;"><?php echo formatIcon('ProspectionView', 32, null, true); ?></div>
        </td>
        <td class="title" style="height:35px;">
          <span id="classNameSpan"><?php echo i18n('menuProspectionView'); ?></span>
          <span id="prospectionViewCount" class="prospectionViewCount"></span>
        </td>
        <td style="width:1%; white-space:nowrap; text-align:right;">
          <div class="prospectionViewLegend">
            <span class="prospectionViewLegendLabel"><?php echo i18n('legend'); ?> :</span>
            <span class="prospectionViewLegendItem prospectionViewLegendProspect"><?php echo i18n('menuProspect'); ?></span>
            <span class="prospectionViewLegendItem prospectionViewLegendClient"><?php echo i18n('menuClient'); ?></span>
            <span class="prospectionViewLegendItem prospectionViewLegendContact"><?php echo i18n('menuContact'); ?></span>
          </div>
        </td>
      </tr>
    </table>

    <div class="prospectionViewFilters">
      <span class="prospectionViewFilter">
        <label for="prospectionViewFilterName"><?php echo i18n('colName'); ?> :</label>
        <input dojoType="dijit.form.TextBox" type="text" id="prospectionViewFilterName"
          class="dijit dijitReset dijitInline dijitLeft filterField rounded dijitTextBox" style="width:150px"
          value="<?php echo htmlEncode($filterName); ?>"
          onKeyUp="prospectionViewApplyFilters();prospectionViewSaveFilter('prospectionViewFilterName', this.value, true);" />
      </span>

      <span class="prospectionViewFilter">
        <label for="prospectionViewFilterDomain"><?php echo i18n('colIdDomainProspect'); ?> :</label>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;"
          <?php echo autoOpenFilteringSelect(); ?>
          id="prospectionViewFilterDomain" name="prospectionViewFilterDomain"
          value="<?php echo htmlEncode($filterDomain); ?>"
          onChange="prospectionViewApplyFilters();prospectionViewSaveFilter('prospectionViewFilterDomain', this.value, false);">
          <?php htmlDrawOptionForReference('idDomainProspect', $filterDomain); ?>
        </select>
      </span>

      <span class="prospectionViewFilter">
        <label for="prospectionViewFilterSource"><?php echo i18n('colIdProspectionSource'); ?> :</label>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;"
          <?php echo autoOpenFilteringSelect(); ?>
          id="prospectionViewFilterSource" name="prospectionViewFilterSource"
          value="<?php echo htmlEncode($filterSource); ?>"
          onChange="prospectionViewApplyFilters();prospectionViewSaveFilter('prospectionViewFilterSource', this.value, false);">
          <?php htmlDrawOptionForReference('idProspectionSource', $filterSource); ?>
        </select>
      </span>

      <span class="prospectionViewFilter">
        <label for="prospectionViewFilterQualification"><?php echo i18n('colIdProspectQualification'); ?> :</label>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;"
          <?php echo autoOpenFilteringSelect(); ?>
          id="prospectionViewFilterQualification" name="prospectionViewFilterQualification"
          value="<?php echo htmlEncode($filterQualification); ?>"
          onChange="prospectionViewApplyFilters();prospectionViewSaveFilter('prospectionViewFilterQualification', this.value, false);">
          <?php htmlDrawOptionForReference('idProspectQualification', $filterQualification); ?>
        </select>
      </span>

      <span class="prospectionViewFilter">
        <label for="prospectionViewFilterEngagement"><?php echo i18n('colIdEngagement'); ?> :</label>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;"
          <?php echo autoOpenFilteringSelect(); ?>
          id="prospectionViewFilterEngagement" name="prospectionViewFilterEngagement"
          value="<?php echo htmlEncode($filterEngagement); ?>"
          onChange="prospectionViewApplyFilters();prospectionViewSaveFilter('prospectionViewFilterEngagement', this.value, false);">
          <?php htmlDrawOptionForReference('idEngagement', $filterEngagement); ?>
        </select>
      </span>

      <span class="prospectionViewFilter">
        <label for="prospectionViewFilterStatus"><?php echo i18n('colIdStatus'); ?> :</label>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;"
          <?php echo autoOpenFilteringSelect(); ?>
          id="prospectionViewFilterStatus" name="prospectionViewFilterStatus"
          value="<?php echo htmlEncode($filterStatus); ?>"
          onChange="prospectionViewApplyFilters();prospectionViewSaveFilter('prospectionViewFilterStatus', this.value, false);">
          <?php htmlDrawOptionForReference('idStatus', $filterStatus); ?>
        </select>
      </span>

      <span class="prospectionViewFilter">
        <label for="prospectionViewFilterResponsible"><?php echo i18n('colResponsible'); ?> :</label>
        <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;"
          <?php echo autoOpenFilteringSelect(); ?>
          id="prospectionViewFilterResponsible" name="prospectionViewFilterResponsible"
          value="<?php echo htmlEncode($filterResponsible); ?>"
          onChange="prospectionViewApplyFilters();prospectionViewSaveFilter('prospectionViewFilterResponsible', this.value, false);">
          <?php htmlDrawOptionForReference('idResource', $filterResponsible); ?>
        </select>
      </span>

      <a class="roundedButtonSmall prospectionViewReset" onclick="prospectionViewResetFilters();"
        title="<?php echo i18n('reset'); ?>"><?php echo formatSmallButton('Cancel'); ?></a>
    </div>
  </div>

  <input type="hidden" id="prospectionViewCollapsedBlocks"
    value="<?php echo htmlEncode($collapsedBlocks); ?>" />
  <div id="prospectionViewContainer" class="prospectionView">
    <div id="prospectionViewMessage" class="prospectionViewMessage"></div>
    <div id="prospectionViewBody"></div>
  </div>

  <!-- Draws the screen on every entry path, some injecting this shell with no
       callback. A pane, because the destination does not run plain scripts, and
       startup, which an empty pane fires where onLoad does not. -->
  <div id="prospectionViewHook" dojoType="dijit.layout.ContentPane" style="display:none;">
    <script type="dojo/connect" event="startup" args="evt">
      prospectionViewInit();
    </script>
  </div>

</div>
