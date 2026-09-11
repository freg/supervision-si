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
?>

<form id="importFacturXForm"
      method="post"
      enctype="multipart/form-data"
      action="../tool/importFacturX.php?csrfToken=<?php echo getSessionValue('Token');?>"
      target="importFacturXFrame"
>
	<table style="width:400px";>
    <tr>
      <!-- label -->
      <td align="center"><?php echo i18n("importFacturXlabel"); ?></td>
    </tr>
    <tr>
     <!-- input -->
      <td style="position:relative">
        <div id="importFacturXPicker" style="display:flex; align-items:center; gap:10px; margin-top:15px; margin-bottom:15px; margin-left:20px;">
          <span style="position:relative; display:inline-block;">
            <button type="button" class="mediumTextButton" dojoType="dijit.form.Button"> <?php echo i18n("buttonBrowse"); ?></button>
            <input id="pdfFacturxExtract" name="pdfFacturxExtract" type="file" required style="position:absolute; left:0; top:0; width:100%; height:100%; opacity:0; cursor:pointer;" onchange="importFacturXOnFileChange(this);" />
          </span>
            <div id="importFacturXFileLabel"
                 style="flex:1; padding:6px 10px; border:1px solid #EEEEEE; border-radius: 5px; color:#999; font-style:italic;
                        white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
                 ondragenter="importFacturXDragEnter(event);"
                 ondragover="importFacturXDragOver(event);"
                 ondragleave="importFacturXDragLeave(event);"
                 ondrop="importFacturXDrop(event);"
            >
              <?php echo i18n("noFileSelected"); ?>
            </div>
        </div>
      </td>
    </tr>
    <tr>
     <!-- button cancel | ok -->
      <td align="center">
        <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogImportFacturX').hide();">
          <?php echo i18n("buttonCancel"); ?>
        </button>
          <button id="dialogImportFacturXSubmit" dojoType="dijit.form.Button" type="submit" class="mediumTextButton" onclick="protectDblClick(this); showWait(); dojo.byId('importFacturXForm').submit();">
          <?php echo i18n("buttonOK"); ?>
        </button>
      </td>
    </tr>
	</table>
</form>
<!-- iframe return -->
<iframe id="importFacturXFrame" name="importFacturXFrame" style="display:none;"></iframe>


