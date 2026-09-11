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
 * Presents an object. 
 */
  require_once "../tool/projeqtor.php";
  scriptLog('   ->/view/importData.php');
  
  require_once "../model/ImportProgress.php";
  $idUser = getCurrentUserId();
  if (is_object($idUser)) { $idUser = $idUser->id; }
  $existingProgress = ImportProgress::get($idUser);
  
  $lastResult = ($existingProgress) ? null : ImportProgress::getLastResult($idUser);

  $elementType = pq_trim(RequestHandler::getValue('elementType'));
  if(!$elementType){
    $elementType=null;
  }
  if($elementType){
    $elementType = SqlList::getIdFromName('Importable', $elementType);
  }
?>
<input type="hidden" name="objectClassManual" id="objectClassManual" value="Import" />
<div class="container" dojoType="dijit.layout.BorderContainer">
  <div id="importDiv" class="listTitle" dojoType="dijit.layout.ContentPane" region="top" splitter="false">
    <form dojoType="dijit.form.Form" id="importDataForm" 
      ENCTYPE="multipart/form-data" method=POST
      action="../tool/import.php<?php echo Security::addTokenIndexToUrl('?');?>"
      target="resultImportData"
      onSubmit="return importData();" >
    <table width="100%">
      <tr height="100%" style="vertical-align: middle;">
        <td width="50px" align="center">
          <?php echo formatIcon('ImportData',32,null,true);?>
        </td>
        <td><span class="title">
          <?php echo i18n('menuImportData')?>&nbsp;&nbsp;&nbsp;
        </td>
        <td width="5%" >&nbsp;
        </td>
        <td class="white" width="15%" nowrap align="right" >
          <?php echo i18n("colImportElementType") ?>&nbsp;&nbsp;
        </td>
        <td width="10%" >
          <select dojoType="dijit.form.FilteringSelect" 
            id="elementType" name="elementType" 
            <?php echo autoOpenFilteringSelect();?>
            class="input" value="<?php echo $elementType;?>" style="width: 200px;">
            <?php htmlDrawOptionForReference('idImportable', $elementType, null, true);?>
           </select> 
        </td>
        <td width="20%" align="left"> 
          <button id="helpImportData" class="detailButton" iconClass="imageColorNewGui iconHelp iconSize<?php echo (isNewGui())?'22':'16';?>" dojoType="dijit.form.Button" type="button" showlabel="false"
          <?php if (isNewGui()) {?> style="position:relative;top:-1px;width:24px;height:24px;"<?php }?>
          title="<?php echo i18n('helpImport');?>">
             <script type="dojo/connect" event="onClick" args="evt">
               showHelpImportData();
               return false;
             </script>
          </button>        
        </td>
      </tr>
      <tr>
        <td colspan="3">
        </td>
        <td class="white" nowrap align="right">
          <?php echo i18n("colImportFileType") ?>&nbsp;&nbsp;
        </td>
        <td width="10px" >
          <select dojoType="dijit.form.FilteringSelect" 
            id="fileType" name="fileType" 
            <?php echo autoOpenFilteringSelect();?>
            class="input" value="csv" style="width: 200px;">
              <option value="csv"><?php echo i18n('csvFile')?></option>
              <option value="xlsx"><?php echo i18n('xlsxFile')?></option>
           </select> 
        </td>
        <td></td>
      </tr>
      <tr height="30px">
        <td colspan="3">
        </td>
        <td class="white" nowrap align="right">
         <?php echo i18n("colFile");?>&nbsp;&nbsp;
        </td>
        <td colspan="2">
         <input type="hidden" name="MAX_FILE_SIZE" value="<?php echo Parameter::getGlobalParameter('paramAttachmentMaxSize');?>" />     
         <input MAX_FILE_SIZE="<?php echo Parameter::getGlobalParameter('paramAttachmentMaxSize');?>"
          dojoType="dojox.form.FileInput" type="file" 
          style="color: #000000;<?php if (isNewGui()) echo "position:relative;top:-3px;";?>" 
          name="importFile" id="importFile" 
          cancelText="<?php echo i18n("buttonReset");?>"
          label="<?php echo i18n("buttonBrowse");?>"
          title="<?php echo i18n("helpSelectFile");?>" />
        </td>
      </tr>
			<tr>
        <td colspan="4">
          <span id="importInProgressMessage" style="display:none;padding:10px 16px;background:#9bd771;color:#0a7611;border-radius:8px;font-weight:600;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.08);position:relative;top:-35px;right: -20px;">
            <?php echo i18n('importInProgressMessage');?>
          </span>
        </td>
        <td>
          <button id="runImportData" dojoType="dijit.form.Button" style="color: #000000;" type="submit" class="dynamicTextButton">
            <?php echo i18n("buttonImportData");?>
          </button>
         </td>
       <td></td>
      </tr>
    </table>
    </form>
  </div>
  <div id="detailDiv" dojoType="dijit.layout.ContentPane" region="center">
   <iframe width="100%" height="100%" name="resultImportData" id="resultImportData" onload="importFinished();"></iframe>
  </div>
</div>  

