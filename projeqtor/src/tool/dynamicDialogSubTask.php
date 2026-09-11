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
include_once '../tool/formatter.php';

if (! isset ($print) or !$print) {
	$print=false;
	$printWidthDialog="100%";
	$internalWidth='100%';
	$nameWidth="15%";
} else {
  $printWidthDialog=$printWidth.'px';
  $nameWidthValue=120;
  $nameWidth=$nameWidthValue.'px;';
  $internalWidth=($printWidth-$nameWidthValue+8).'px';
}
$context="popup";
if (isset($obj)) {
  $objectClass=get_class($obj);
  $objectId=$obj->id;
  $context="detail";
} else {
  if (! pq_array_key_exists('objectClass',$_REQUEST)) {
  	throwError('Parameter objectClass not found in REQUEST');
  }
  $objectClass=$_REQUEST['objectClass'];
  Security::checkValidClass($objectClass);
  
  if (! pq_array_key_exists('objectId',$_REQUEST)) {
  	throwError('Parameter objectId not found in REQUEST');
  }
  $objectId=$_REQUEST['objectId'];
}
  
$obj= new $objectClass ($objectId);
$showClosedSubTask=(Parameter::getUserParameter('showClosedSubTask_Single')!='' and Parameter::getUserParameter('showClosedSubTask_Single')!='0')?true:false;
$showDoneSubTask=((Parameter::getUserParameter('showDoneSubTask_Single')!='0' or  $showClosedSubTask==true))?true:false;
?>
<?php if (! $print) {?>
<?php if ($context=='popup') {?>
<form id="dialogSubTasklistForm" name="dialogSubTasklistForm" action="">
<?php }} else {?>
<table style="width:<?php echo $printWidthDialog;?>;">
  <tr><td>&nbsp;</td></tr>
  <tr><td class="section"><?php echo i18n("Checklist");?></td></tr>
  <tr style="height:0.5em;font-size:80%"><td>&nbsp;</td></tr>
</table>	
<?php }?> 
<table style="width:<?php echo $printWidthDialog;?>;">
  <tr>
    <td width="100%">
      <div style="position:relative; float:right; top:0px;">
        <label for="showClosedSubTask_Single"  class="dijitTitlePaneTitle" style="border:0;font-weight:normal !important;<?php echo ((isNewGui())?'padding-top:13px':'');?>;height:<?php echo ((isNewGui())?'20':'10');?>px;width:<?php echo((isNewGui())?'50':'150');?>px"><?php echo i18n('labelShowIdle'.((isNewGui())?'Short':''));?>&nbsp;</label>
          <div class="<?php echo ((isNewGui())?"whiteCheck":"");?>" id="showClosedSubTask_Single" style="<?php echo ((isNewGui())?'margin-top:14px':'');?>" 
            dojoType="dijit.form.CheckBox" type="checkbox" <?php echo (($showClosedSubTask)?'checked':'');?> title="<?php echo i18n('labelShowIdle') ;?>" >
            <script type="dojo/connect" event="onChange" args="evt">
              saveUserParameter("showClosedSubTask_Single",((this.checked)?"1":"0"));
              if (checkFormChangeInProgress()) {return false;}
              if (checkFormChangeInProgress()) {return false;}
              dijit.byId('dialogSubTask').hide();
              setTimeout("showSubTask('<?php echo $objectClass;?>');",500);
          </script>
          </div>
      </div>
      <div style="position:relative; float:right; top:0px;">
          <label for="showDoneSubTask_Single"  class="dijitTitlePaneTitle" style="border:0;font-weight:normal !important;<?php echo ((isNewGui())?'padding-top:13px':'');?>;height:<?php echo ((isNewGui())?'20':'10');?>px;width:<?php echo((isNewGui())?'50':'180');?>px"><?php echo i18n('labelShowDone'.((isNewGui())?'Short':''));?>&nbsp;</label>
          <div class="<?php echo ((isNewGui())?"whiteCheck":"");?>" id="showDoneSubTask_Single" style="<?php echo ((isNewGui())?'margin-top:14px':'');?>" <?php if($showClosedSubTask)echo "readonly";?>
            dojoType="dijit.form.CheckBox" type="checkbox" <?php echo (($showDoneSubTask)?'checked':'');?> title="<?php echo i18n('labelShowDone') ;?>" >
            <script type="dojo/connect" event="onChange" args="evt">
              saveUserParameter("showDoneSubTask_Single",((this.checked)?"1":"0"));
              if (checkFormChangeInProgress()) {return false;}
              if (checkFormChangeInProgress()) {return false;}
              dijit.byId('dialogSubTask').hide();
             setTimeout("showSubTask('<?php echo $objectClass;?>');",500);
          </script>
          </div>
      </div>

    </td>
  </tr>
  <tr>
    <td style="width:<?php echo $printWidthDialog;?>;">
        <?php  $rightUpdate=securityGetAccessRightYesNo('menu'.$objectClass,'update',$obj);
          $rightRead=securityGetAccessRightYesNo('menu'.$objectClass,'read',$obj);
       SubTask::drawSubtasksForObject($obj, $objectClass, $objectId,$rightUpdate,$rightRead,false,false,false,true);?>
    </td>
  </tr>
 <tr>
  <td style="width:<?php echo $printWidthDialog;?>;">&nbsp;</td>
 </tr>
<td style="width: 50%;" align="right">
       <button dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogSubTask').hide();">
         <?php echo i18n("close");?>
       </button>
     </td>
</table>
<?php if (! $print and $context=='popup') {?></form><?php }?>
