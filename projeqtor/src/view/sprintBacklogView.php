<?php 
/*** COPYRIGHT NOTICE *********************************************************
 *
******************************************************************************
*** WARNING *** T H I S    F I L E    I S    N O T    O P E N    S O U R C E *
******************************************************************************
*
* Copyright 2015 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
require_once '../tool/agileBacklogFunction.php';

?>
<div id="sprintBacklogContainer" style="height:100%;padding:8px;" onscroll="SprintBacklogScrollTop=this.scrollTop">
  <table width="100%" style="min-height:100%;">
    <tr>
      <?php drawSprintBacklogColumn();?>
    </tr>
  </table>
  <div class="contextMenuClass comboButtonInvisible" dojoType="dijit.form.DropDownButton" id="backlogContextMenu" name="backlogContextMenu" style="position:absolute;top:0px;left:0px;width:0px;height:0px;overflow:hidden;">
    <div dojoType="dijit.TooltipDialog" id="dialogBacklogContextMenu" tabindex="0"" onMouseEnter="clearTimeout(hideBacklogContextMenuTimeout);" onMouseLeave="hideBacklogContextMenu(200)" onfocusout="hideElementOnFocusOut(null, hideBacklog(200))">
      <input type="hidden" id="contextMenuRefId" name="contextMenuRefId" value="" />
      <input type="hidden" id="contextMenuRefType" name="contextMenuRefType" value="" />
      <input type="hidden" id="objectClassRow" name="objectClassRow" value="" />
      <input type="hidden" id="objectIdRow" name="objectIdRow" value="" />
      <input type="hidden" id="objectClass" name="objectClass" value="" />
      <input type="hidden" id="objectId" name="objectId" value="" />
      <table style="width:100%;height:100%">
        <tr id='addUserStoryFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('UserStory', true, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='addUserStoryFromBacklog_label'><?php echo i18n('addUserStoryBacklog');?></td>
        </tr>
        <tr id='addEpicFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Epic', true, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='addEpicFromBacklog_label'><?php echo i18n('addEpicBacklog');?></td>
        </tr>
        <tr id='editFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Edit', false, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='editFromBacklog_label'><?php echo i18n('contextMenuButtonEdit');?></td>
        </tr>
        <tr id='copyFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Copy', false, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='copyFromBacklog_label'><?php echo i18n('contextMenuButtonCopy');?></td>
        </tr>
        <tr id='removeFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Remove', false, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='removeFromBacklog_label'><?php echo i18n('contextMenuButtonDelete');?></td>
        </tr>
        <tr id='addCommentFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('AddComment', false, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='addCommentFromBacklog_label'><?php echo i18n('commentImputationAdd');?></td>
        </tr>
        <tr id='printFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Print', true , false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='printFromBacklog_label'><?php echo i18n('contextMenuButtonPrint');?></td>
        </tr>
        <tr id='printPdfFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Pdf', false, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='printPdfFromBacklog_label'><?php echo i18n('reportPrintPdf');?></td>
        </tr>
        <tr id='gotoFromBacklog' class='contextMenuRow' onClick=''>
          <td style="padding-top:5px;padding-bottom:5px;"><?php echo formatSmallButton('Goto', true, false);?></td>
          <td style="padding-left:10px;padding-top:5px;padding-bottom:5px;" id='gotoFromBacklog_label'><?php echo i18n('contextMenuButtonGoto');?></td>
        </tr>
      </table>
    </div>
  </div>
</div>