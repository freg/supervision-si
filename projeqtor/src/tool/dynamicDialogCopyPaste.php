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
if (! pq_array_key_exists('targetObjectClass',$_REQUEST)) {
  throwError('Parameter targetObjectClass not found in REQUEST');
}
$targetObjectClass=RequestHandler::getClass('targetObjectClass');
if (! pq_array_key_exists('targetObjectClass',$_REQUEST)) {
  throwError('Parameter targetObjectClass not found in REQUEST');
}
$targetObjectId=RequestHandler::getId('targetObjectId');
if (! pq_array_key_exists('targetObjectId',$_REQUEST)) {
  throwError('Parameter targetObjectId not found in REQUEST');
}

$copyObjectArray=RequestHandler::getValue('copyObjectArray');
if (! pq_array_key_exists('copyObjectArray',$_REQUEST)) {
  throwError('No selection found');
}
$copyObjectArray = explode(',', $copyObjectArray);

$copyType=RequestHandler::getValue('copyType');
if($copyType!='copyObjectTo' && $copyType!='copyProject' && $copyType!='copyVersion'){
  traceHack('dynamicDialogCopy: $copyType contains an unexpected valid value');
}
$fromContextMenu = RequestHandler::getBoolean('fromContextMenu');

$lstCopyObjectId = $copyObjectArray;

$newObj = new Activity();
$allowedStatusList = Workflow::getAllowedStatusListForObject($newObj);
$status = new Status();
if(isset($allowedStatusList) and count($allowedStatusList) > 0){
  $status = reset($allowedStatusList);
}
//------------------------------------------------------------------------------------
$toCopy=new $targetObjectClass($targetObjectId);
$pe = $targetObjectClass . 'PlanningElement';
$moveAfterCreate = null;
if (property_exists ( $toCopy, $pe )) {
  $moveAfterCreateObj = PlanningElement::getSingleSqlElementFromCriteria('PlanningElement', array('refType'=>$targetObjectClass, 'refId'=>$targetObjectId));
  if(isset($moveAfterCreateObj->id) and $moveAfterCreateObj->id){
    $moveAfterCreate = $moveAfterCreateObj->id;
  }
}
?>
<table name='generalData'>
	<tr>
		<td>
			<form dojoType="dijit.form.Form" id='copyPasteForm' name='copyPasteForm' onSubmit="return false;">
				<input id="copyPasteFromContextMenu" name="copyPasteFromContextMenu" type="hidden" value="<?php echo $fromContextMenu;?>" />
				<input id="copyToType" name="copyToType" type="hidden" value="" />
				<input id="copyTargetClass" name="copyTargetClass" type="hidden" value="<?php echo $targetObjectClass;?>" />
				<input id="copyTargetId" name="copyTargetId" type="hidden" value="<?php echo $targetObjectId;?>" />
				<input id="copyObjectArray" name="copyObjectArray" type="hidden" value="<?php echo implode(',', $copyObjectArray);?>" />
				<input id="moveAfterCreate" name="moveAfterCreate" type="hidden" value="<?php echo $moveAfterCreate?>" />
        <table name='tableDataCopyPaste'>
          <tr>
            <td class='assignHeader' style='width:200px'><?php echo i18n('dashboardTicketMainTitleType'); ?></td>
            <td class='assignHeader' style='width:30px'><?php echo i18n('colId'); ?></td>
        		<td class='assignHeader' style='width:400px'><?php echo i18n('name'); ?></td>
        		<td class='assignHeader' style='width:200px'><?php echo i18n('colSynchroniseDefinitionActivity'); ?></td>
          </tr>
          	<?php 
          	$first=true;
          	foreach($lstCopyObjectId as $copyObject){
          	  $objectArray = explode('_', $copyObject);
          	  $objClass = $objectArray[0];
          	  $copyId = $objectArray[1];
          	  if($objClass=='Replan' || $objClass=='Construction' || $objClass=='Fixed'){
          	    $objClass = "Project";
          	  }
          	  $obj = new $objClass($copyId);
          	  echo"<tr>";
          	    echo"<td class='assignData'>".i18n($objClass)."</td>";
          	    echo"<td class='assignData'>".$copyId."</td>";
            	  echo"<td class='assignData'>".$obj->name."</td>";
            	  if ($first) echo"<td class='assignData' rowspan='".count($lstCopyObjectId)."'>".i18n($targetObjectClass)." #$targetObjectId<br/>$toCopy->name</td>";
          	  echo"</tr>";
          	  $first=false;
          	}
          	?>
        </table>
        <table name='optionSection' style="width:100%; margin-bottom:10px">
          <tr> 
            <td style="margin-top:5px; margin-bottom:5px;">
        	   <label for="copyWithAssignmentsPaste" style="width:60%;text-align: right;"><?php echo i18n("copyAssignments") ?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
             <?php 
             $isCheckedWithAsignments=Parameter::getUserParameter('isCheckedWithAsignmentsCopyPaste');
             $isCheckedWithAsignments=($isCheckedWithAsignments == "")?false:$isCheckedWithAsignments;
             ?>
             <div id="copyWithAssignmentsPaste" name="copyWithAssignments" dojoType="dijit.form.CheckBox" <?php if ($isCheckedWithAsignments=='true') echo " checked ";?> type="checkbox" >
             	  <script type="dojo/method" event="onChange" >
                    saveDataToSession('isCheckedWithAsignmentsCopyPaste',((this.checked)?true:false),true);
                </script>
             </div>
            </td>
          </tr>
          <tr>
            <td style="margin-top:5px; margin-bottom:5px;">
              <label for="copyToWithStatus" style="width:60%;text-align: right;"><?php echo i18n("CopyWithStatus", array($status->name));?>&nbsp;<?php if(!isNewGui()){?>:<?php }?>&nbsp;</label>
               <?php 
               $isCheckedWithStatus='true';
               $isCheckedWithStatus=Parameter::getUserParameter('isCheckedWithStatusCopyPaste');
               if($isCheckedWithStatus!= 'false' or Parameter::getGlobalParameter('defaultSkipCopyStatus')=="YES") $isCheckedWithStatus=true;
               else if ($isCheckedWithStatus=='false' or Parameter::getGlobalParameter('defaultSkipCopyStatus')=="NO") $isCheckedWithStatus=false;
               ?>
              <div id="copyToWithStatusPaste" name="copyToWithStatus" dojoType="dijit.form.CheckBox" <?php if ($isCheckedWithStatus=='true') echo " checked ";?> 
                   type="checkbox">
              <script type="dojo/method" event="onChange" >
                 saveDataToSession('isCheckedWithStatusCopyPaste',((this.checked)?'true':'false'),true);
              </script>
              </div>
            </td>
          </tr> 
        </table>
      </form>
      <table name='boutonCancelAndOk' align="center">
        <tr>
        	<td>
            <button class="mediumTextButton" dojoType="dijit.form.Button" type="button"
              onclick="dijit.byId('dialogCopyPaste').hide();">
              <?php echo i18n("buttonCancel");?>
            </button>
        	</td>
        	<td style="padding-left:5px">
        		<button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogCopyPasteSubmit" 
        			onclick="protectDblClick(this);copyPasteObjectToSubmit();">
          		<?php echo i18n("buttonOK");?>
          	</button>
        	</td>
        </tr>
    	</table>
		</td>
	</tr>
</table>