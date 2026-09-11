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
 * List of parameter specific to a user.
 * Every user may change these parameters (for his own user only !).
 */
require_once "../tool/projeqtor.php";
scriptLog('   ->/view/parameter.php');

?>
<input
  type="hidden" name="objectClassManual" id="objectClassManual"
  value="DocumentRight" />
<div class="container" dojoType="dijit.layout.BorderContainer">
<div id="parameterButtonDiv" class="listTitle" style="z-index:3;overflow:visible"
  dojoType="dijit.layout.ContentPane" region="top">
<table width="100%">
  <tr height="100%" style="vertical-align: middle;">
    <td width="50px" align="center"><?php echo formatIcon('DocumentRight', 32, null, true);?></td>
    <td><span class="title"><?php echo pq_str_replace(" ","&nbsp;",i18n('menuDocumentRight'))?>&nbsp;</span>
    </td>
    <td width="10px">&nbsp;</td>
    <td width="50px">
    <button id="saveParameterButton" dojoType="dijit.form.Button"
      showlabel="false"
      title="<?php echo i18n('buttonSaveParameters');?>"
      iconClass="dijitButtonIcon dijitButtonIconSave" class="detailButton">
        <script type="dojo/connect" event="onClick" args="evt">              
          submitForm("../tool/saveDocumentRight.php?operation=save&csrftToken="+csrfToken,"resultDivMain", "parameterForm", true);
          if(dojo.byId('lstDocRight') && dojo.byId('lstDocRight').value!='')dojo.byId('lstDocRight').value='';
          if(dojo.byId('lstNewDocRight') && dojo.byId('lstNewDocRight').value!='')dojo.byId('lstNewDocRight').value='';          
        </script>
    </button>
    <div dojoType="dijit.Tooltip" connectId="saveButton"><?php echo i18n("buttonSaveParameter")?></div>
    </td>
    <td style="position:relative;">
    
    </td>
  </tr>
</table>
</div>
<div id="formDiv" dojoType="dijit.layout.ContentPane" region="center" style="overflow:auto;" >
<form dojoType="dijit.form.Form" id="parameterForm" jsId="parameterForm"
  name="parameterForm" encType="multipart/form-data" action="" method="">
  <?php 
      
      DocumentRight::drawAllDocumentRight();
    
  ?></form>
</div>
</div>
