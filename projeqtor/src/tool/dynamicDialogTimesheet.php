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

/*
 * ============================================================================
 * Habilitation defines right to the application for a menu and a profile.
 */
require_once "../tool/projeqtor.php";

$detailHeight = 350;
$detailWidth = 600;

if(RequestHandler::isCodeSet('idActivity')) {
  $idActivity = RequestHandler::getValue('idActivity');
} else {
  echo 'Erreur manque Activity';
}

if(RequestHandler::isCodeSet('newLeft')) {
  $newLeft=$_REQUEST['newLeft'];
} else {
  echo 'Erreur manque newLeft';
}
if(RequestHandler::isCodeSet('newReal')) {
  $newReal=$_REQUEST['newReal'];
} else {
  echo 'Erreur manque newReal';
}
if(RequestHandler::isCodeSet('idAssignment')) {
  $idAssignment=$_REQUEST['idAssignment'];
} else {
  echo 'Erreur manque idAssignment';
}

if(RequestHandler::isCodeSet('rowId')) {
  $rowId=$_REQUEST['rowId'];
} else {
  echo 'Erreur manque rowId';
}

?>
<div class="container"  style="max-height:800px;overflow:auto;margin:unset;padding:5px;">
  <form dojoType="dijit.form.Form" id='timesheetForm' name='timesheetForm' action="" method="post" onSubmit="return false;">
    <table style="width: 100%;">
      <tr>
        <td><div class="dialogLabel"><?php echo i18n("colMandatoryResultOnDone");?></div></td>
      </tr>
      <tr style="height:100%;">
			  <td>
			    <input id="timesheetResultEditorType" name="timesheetResultEditorType" type="hidden" value="<?php if (isNewGui()) echo 'CK'; else echo getEditorType();?>" />
            <?php  if (getEditorType()=="CK" or getEditorType()=="CKInline") {?> 
            <textarea style="width:<?php echo $detailWidth;?>px; height:<?php echo $detailHeight;?>px" name="timesheetResult" class="required" id="timesheetResult" required></textarea>
            <?php  } else if (getEditorType()=="text"){ ?>
            <textarea dojoType="dijit.form.Textarea" id="timesheetResult" name="timesheetResult" style="width: 500px;" maxlength="4000" class="input required" required onClick="dijit.byId('timesheet').setAttribute('class','');"></textarea>
            <?php } else { ?>
            <textarea dojoType="dijit.form.Textarea" type="hidden" id="timesheetResult" name="timesheetResult" style="display: none;" class="required" required></textarea>
            
				      <div data-dojo-type="dijit.Editor" id="timesheetResultEditor"
              data-dojo-props="onChange:function(){window.top.dojo.byId('timesheet').value=arguments[0];}
              ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
              ,onKeyDown:function(event){window.top.onKeyDownFunction(event,'kanbanResultEditor',this);}
              ,onBlur:function(event){window.top.editorBlur('kanbanResultEditor',this);}
              ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
              style="color:#606060 !important; background:none; 
                padding:3px 0px 3px 3px;margin-right:2px;height:<?php echo $detailHeight;?>px;width:<?php echo $detailWidth;?>px;min-height:16px;overflow:auto;"
              class="input required"></div>
            <?php  }?>
        </td>
		  </tr>
  	</table>
  	<table style="width: 100%;">
		  <tr>
			  <td align="center"><input type="hidden" id="dialogTimesheetResultAction">
				  <button class="mediumTextButton" dojoType="dijit.form.Button" type="button"  onclick="dijit.byId('dialogTimesheet').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
				<button class="mediumTextButton" id="dialogTimesheetSubmit" dojoType="dijit.form.Button" type="submit" onclick="saveTimesheetResult(<?php echo $idActivity; ?>,<?php echo $newReal; ?>,<?php echo $newLeft; ?>,<?php echo $idAssignment; ?>,<?php echo $rowId; ?>)">
          <?php echo i18n("buttonOK");?>
        </button></td>
		  </tr>
	  </table>
	</form>