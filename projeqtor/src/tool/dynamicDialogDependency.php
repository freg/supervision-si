<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2016 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
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
include_once ("../tool/projeqtor.php");
$id=RequestHandler::getId('id',true);
$dep=new Dependency($id);
$delayDep=$dep->dependencyDelay;
$commentDep=$dep->comment;
$pred=new $dep->predecessorRefType($dep->predecessorRefId, true);
$succ=new $dep->successorRefType($dep->successorRefId, true);
?>
<div class="contextMenuDiv" id="contextMenuDiv" style="height:<?php echo (isNewGui())?"195px":"190px";?>;width:295px;z-index:99999999999;">

  <div style="width:285px;border-radius:1px 1px 0px 0px;">
    <div class="section" style="display: inline-block;width:100%; border-radius:0px;<?php if (isNewGui()) echo "background:var(--color-darker) !important;"?>" >
      <p  style="text-align:center;color:white;height:20px;font-size:15px;display:inline-block;<?php if (isNewGui()) echo "position:relative;top:3px;"?>"><?php echo i18n("operationUpdate");?></p>
      <div style="float:right;">
        <?php if (isNewGui()) {?>
        <div onclick="hideDependencyRightClick();" class="dijitDialogCloseIcon"></div>
        <?php } else  {?>
        <a onclick="hideDependencyRightClick();" <?php echo formatSmallButton('Mark') ;?></a>
         <?php } ?>
      </div>
    </div>
  </div>
  <form dojoType="dijit.form.Form" id='dynamicRightClickDependencyForm' name='dynamicRightClickDependencyForm' onSubmit="return false;" style="padding:5px;">
	  <table style="width:100%">
	    <tr style="height:20px;font-size:90%">
  	    <td colspan="3">
  	      <div style="max-width:285px;overflow:hidden;white-space: nowrap; text-overflow: ellipsis">
  	      <?php echo formatSmallButton($dep->predecessorRefType, true, false, true);echo " #$dep->predecessorRefId | $pred->name"; ?> 
  	      </div>
  	    </td>
	    </tr>
  	  <tr style="height:20px;font-size:90%">
  	    <td colspan="3">
  	      <div style="max-width:285px;overflow:hidden;white-space: nowrap; text-overflow: ellipsis">
  	      <?php echo formatSmallButton($dep->successorRefType, true, false, true);echo " #$dep->successorRefId | $succ->name"; ?> 
  	      </div>
  	    </td>
	    </tr>
	  <?php if ($logLevel>=3) {?>
	  <?php }?>
	    <tr style="height:28px;">
	      <td style="text-align:right;">
	        <label for="modeDependency" style="width:100px;margin-top:-4px"><?php echo i18n("colType");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label> 
	      </td>
	      <td>
	      <?php $depType=array('E-S','E-E','S-S');?>
	        <select dojoType="dijit.form.FilteringSelect" class="input" name="dependencyType" id="dependencyType"
	        onChange="<?php foreach ($depType as $type) {?>dojo.byId('dependencyDialog_<?php echo $type?>').style.display=(this.value=='<?php echo $type;?>')?'block':'none';<?php }?>"
	          <?php echo autoOpenFilteringSelect();?> style="width:120px;height:20px">
            <?php 
            foreach ($depType as $type) {
              $select=($dep->dependencyType==$type)?' selected ':'';
              $lib=( (pq_substr($type,0,1)=='E')?i18n('colEnd'):i18n('colStart') ).' - '.( (pq_substr($type,-1)=='E' )?i18n('colEnd'):i18n('colStart') );
              echo "<option value='$type' $select >$lib</option>";
            }?>
          </select>
          <?php foreach ($depType as $type) {?>
          <img style="display:<?php echo ($dep->dependencyType==$type)?"block":"none";?>;float:right; margin: 3px 10px; margin-left: auto;" id="dependencyDialog_<?php echo $type?>" src="../view/css/images/dependency_<?php echo $type?>.png">
          <?php }?>
	      </td>
	    </tr>
	    <tr style="height:25px">
	      <td style="text-align:right; width:100px;">
	        <input id="dependencyRightClickId" name="dependencyRightClickId" type="hidden" value="<?php echo $id;?>" />
          <label for="dependencyDelay" style="width:100px;margin-top:-4px"><?php echo i18n("colDependencyDelay");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
        </td>
        <td style="text-align:left; white-space:nowrap">
	        <input id="delayDependency" name="delayDependency" dojoType="dijit.form.NumberTextBox" constraints="{min:-999, max:999}" 
            style="width:25px; text-align: center;" value="<?php echo $delayDep;?>" />
		      <?php echo i18n("days");?>
		    </td>
      </tr>
	    <tr style="height:10px;">
	      <td colspan="2">
	        <label for="commentDependency" style="text-align: left;"><?php echo i18n("colComment");?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
					<textArea id="commentDependency" style="width:210px;height:33px;resize: none;font-family:verdana;padding:0px 5px;" name="commentDependency"  dojoType="dijit.form.Textarea" ><?php echo $commentDep;?></textArea>
					<div style="float:right;margin-top:10px">
	        <a class="buttonIconNewGui" onclick="removeDependencyRightClick();"><?php echo formatMediumButton('Remove') ;?></a>&nbsp;
	        <a class="buttonIconNewGui" id="dependencyRightClickSave" onclick="saveDependencyRightClick();"><?php echo formatMediumButton('Save') ;?></a>
	        </div> 
        </td>

	    </tr>
    </table>  
  </form>		  
</div>