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
$user=getSessionUser();
$reportLayoutObjectClass=RequestHandler::getValue('objectClass');
?>
<table style="<?php if (isNewGui()) echo 'width:780px';?>">
    <tr>
     <td class="section"><?php echo i18n("sectionStoredReportLayout");?></td>
    </tr>
    <?php if (isNewGui()) {?><tr><td><div style="height:6px"></div></td></tr><?php }?>
    <tr>
      <td>
        <div id='listStoredReportLayouts' dojoType="dijit.layout.ContentPane" region="center" ><div style="height:250px">loading...</div></div>
      </td>
    </tr>
    <tr><td>&nbsp;</td></tr>
    <tr>
      <td>
        <div id='listSharedReportLayouts' dojoType="dijit.layout.ContentPane" region="center"></div>
      </td>
    </tr>
    <tr><td>&nbsp;</td></tr>
</table>
<table style="<?php if (isNewGui()) echo 'width:780px';?>">
    <tr>
     <td class="section"><?php echo i18n("sectionActiveReportLayout");?></td>
    </tr>
    <tr>
      <td style="margin: 2px;"> 
        <form id='dialogReportLayoutForm' name='dialogReportLayoutForm' onSubmit="return false;">
         <input type="hidden" id="reportLayoutObjectClass" name="reportLayoutObjectClass" value="<?php echo $reportLayoutObjectClass;?>"/>
         <input type="hidden" id="reportLayoutName" name="reportLayoutName" />
         <div id='listSelectedReportLayout' dojoType="dijit.layout.ContentPane" region="center" style="overflow:hidden;max-height:127px;overflow-y:auto"></div>
        </form>
      </td>
    </tr>
    <?php if (isNewGui()) {?><tr><td><div style="height:6px"></div></td></tr><?php }?>
    <tr style="height:32px">
      <td align="center">
        <table><tr>
          <td>
            <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogReportLayout').hide();">
              <?php echo i18n("comboCloseButton");?>
            </button>
          </td>
        </tr></table>
      </td>
    </tr>
  </table>