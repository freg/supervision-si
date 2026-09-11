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
$needRessource = false;
if (pq_array_key_exists ( 'needRessource', $_REQUEST )) {
	$needRessource = true;
}

$needResult = false;
if (pq_array_key_exists ( 'needResult', $_REQUEST )) {
	$needResult = true;
}

$needResolution = false;
if (pq_array_key_exists ( 'needResolution', $_REQUEST )) {
	$needResolution = true;
}

if (! pq_array_key_exists ( 'typeDynamic', $_REQUEST )) {
	throwError ( 'Parameter typeDynamic not found in REQUEST' );
}
$typeDynamic = $_REQUEST ['typeDynamic'];
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();

if ($typeDynamic == 'update') {
	$detailHeight = 350;
	$detailWidth = 600;
	
	$objectClass = RequestHandler::getClass('objectClass');
	$objectId = RequestHandler::getId('objectId');
	$itemID = RequestHandler::getValue('itemID');
	$oldColumn = RequestHandler::getValue('oldColumn');
	$newColumn = RequestHandler::getValue('newColumn');
	$columnType = RequestHandler::getValue('columnType');
	$forceWorkflow = RequestHandler::getValue('forceWorkflow');
	
	$obj = new $objectClass ( $objectId );
	
	$extraRequiredFields = RequestHandler::getValue('extraRequiredFields');//ticket,activité,action,exigence
	$flatRequired = array();
	$requiredField = array();
	if($extraRequiredFields){
		$extraRequiredFields = pq_explode(',', $extraRequiredFields);
		$requiredField = array();
		foreach ($extraRequiredFields as $field){
	     $requiredField[pq_trim($field)]=$obj->getDataType(pq_trim($field));
	     $flatRequired[pq_trim($field)]=pq_trim($field);
		}
	}
	$flatRequired = pq_trim(implode(',', $flatRequired));
	$dateWidth='72';
	if (isNewGui()) $dateWidth='85';
	$verySmallWidth='44';
	if (isNewGui()) $verySmallWidth='54';
	$smallWidth='72';
	if (isNewGui()) $verySmallWidth='82';
	$mediumWidth='197';
	if (isNewGui()) $mediumWidth='207';
	$largeWidth='300';
	if (isNewGui()) $largeWidth='310';
	$labelWidth=(isNewGui())?175:160;
?>

<div class="container"  style="overflow-x:auto;margin:unset;padding:5px;">
<form dojoType="dijit.form.Form" id='kanbanResultForm' name='kanbanResultForm' action="" method="post"
	onSubmit="return false;">
	<input type="hidden" id="objectClass" name="objectClass" value="<?php echo $objectClass;?>" />
	<input type="hidden" id="objectId" name="objectId" value="<?php echo $objectId;?>" />
	<input type="hidden" id="newColumn" name="newColumn" value="<?php echo $newColumn;?>" />
	<input type="hidden" id="columnType" name="columnType" value="<?php echo $columnType;?>" />
	<input type="hidden" id="forceWorkflow" name="forceWorkflow" value="<?php echo ($forceWorkflow?'1':'');?>" />
	<table style="width: 100%;">
	<tr><td><input type="hidden" id="extraRequiredFields" name="extraRequiredFields" value="<?php echo $flatRequired; ?>"/></td></tr>
<?php
	if ($needRessource) {
		?>
<tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("colMandatoryResourceOnHandled");?></div>
			</td>
		</tr>
		<tr>
			<td><select dojoType="dijit.form.FilteringSelect"
				class="input required" required="true"
				<?php echo autoOpenFilteringSelect ();?> name="kanbanResourceList"
				id="kanbanResourceList">
    <?php
		htmlDrawOptionForReference ( "idResource", getSessionUser ()->isResource ? getSessionUser ()->id : null, null, true, "idProject", $obj->idProject );
		?>
    </select></td>
		</tr>
<?php
	}
	if ($needResult) {
		?>
<tr>
			<td><div class="dialogLabel"><?php echo i18n("colMandatoryResultOnDone");?></div></td>
		</tr>
		<tr>
			<td><input id="kanbanResultEditorType" name="kanbanResultEditorType"
				type="hidden" value="<?php if (isNewGui()) echo 'CK'; else echo getEditorType();?>" />
         <?php if (getEditorType()=="CK" or isNewGui()) {?> 
          <textarea style="width:<?php echo $detailWidth;?>px; height:<?php echo $detailHeight;?>px"
          name="kanbanResult" class="required" id="kanbanResult"></textarea>
        <?php } else if (getEditorType()=="text"){?>
          <textarea dojoType="dijit.form.Textarea" id="kanbanResult"
					name="kanbanResult" style="width: 500px;" maxlength="4000"
					class="input required"
					onClick="dijit.byId('kanbanResult').setAttribute('class','');"></textarea>
        <?php } else {?>
          <textarea dojoType="dijit.form.Textarea" type="hidden"
					id="kanbanResult" name="kanbanResult" style="display: none;"></textarea>
				<div data-dojo-type="dijit.Editor" id="kanbanResultEditor"
             data-dojo-props="onChange:function(){window.top.dojo.byId('kanbanResult').value=arguments[0];}
              ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                        'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
              ,onKeyDown:function(event){window.top.onKeyDownFunction(event,'kanbanResultEditor',this);}
              ,onBlur:function(event){window.top.editorBlur('kanbanResultEditor',this);}
              ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
              style="color:#606060 !important; background:none; 
                padding:3px 0px 3px 3px;margin-right:2px;height:<?php echo $detailHeight;?>px;width:<?php echo $detailWidth;?>px;min-height:16px;overflow:auto;"
              class="input required"></div>
        <?php }?>

      </td>
		</tr>
<?php
	}
	if ($needResolution) {
		?>
<tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("colIdResolution");?></div>
			</td>
		</tr>
		<tr>
			<td><select dojoType="dijit.form.FilteringSelect"
				class="input required" required="true" name="kanbanResolutionList"
				id="kanbanResolutionList">
    <?php echo autoOpenFilteringSelect ();?>
    <?php htmlDrawOptionForReference("idResolution", null, null ,true);?>
    </select></td>
		</tr>
<?php
	}
	if(count($requiredField)>0){
      foreach ($requiredField as $id=>$type){
        if(pq_substr($id, 0, 2) == 'id' and $type == 'int'){
          ?>
          <tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("col".pq_ucfirst($id));?></div>
			</td>
		  </tr>
		  <tr>
			<td>
  			 <select dojoType="dijit.form.FilteringSelect"
  				class="input required" required="true"
  				<?php echo autoOpenFilteringSelect ();?> name="<?php echo $id;?>"
  				id="<?php echo $id;?>">
                <?php
                  $val = (isset($obj->$id))?$obj->$id:null;
                  htmlDrawOptionForReference ( $id, $val, null, true, null, $obj->idProject );
          		?>
              </select>
            </td>
		  </tr>
          <?php
        }else if($type == 'date'){
          ?>
          <tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("col".pq_ucfirst(pq_trim($id)));?></div>
			</td>
		  </tr>
		  <tr>
			<td>
		  <?php 
          $val = (isset($obj->$id))?$obj->$id:date('Y-m-d');
          $name=' id="'.$id.'" name="'.$id.'" ';
          if ($id=='creationDate' or !$val) {
          	$val=date('Y-m-d');
          }
          $negative='';
          if (property_exists($obj, 'validatedEndDate')) {
          	$negative=($id=="plannedEndDate" and $obj->plannedEndDate and $obj->validatedEndDate and $obj->plannedEndDate>$obj->validatedEndDate)?'background-color: #FFAAAA !important;':'';
          }
          // BEGIN - ADD BY TABARY - TOOLTIP
          //echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
          // END - ADD BY TABARY - TOOLTIP
          echo '<div dojoType="dijit.form.DateTextBox" ';
          echo $name;
          echo 'required="true"';
          $dataLength = $obj->getDataLength($id);
          echo ' invalidMessage="'.i18n('messageInvalidDate').'"';
          echo ' type="text" maxlength="'.$dataLength.'" ';
          if (sessionValueExists('browserLocaleDateFormatJs')) {
          	$min='';
          	if (pq_substr($id, -7)=="EndDate") {
          		$start=pq_str_replace("EndDate", "StartDate", $id);
          		if (property_exists($obj, $start)&&property_exists($obj, 'refType')&&$obj->refType!="Milestone") {
          			$min=$obj->$start;
          		} else {
          			$start=pq_str_replace("EndDate", "EisDate", $id);
          			if (property_exists($obj, $start)) {
          				$min=$obj->$start;
          			}
          		}
          		if ($val and $val<$min) $val=$min;
          		if ($min) echo ' dropDownDefaultValue="'.$min.'" ';
          	}
          	echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\', min:\''.$min.'\' }" ';
          }
          echo ' style="'.$negative.'width:'.$dateWidth.'px; text-align: center;" class="input required generalColClass" ';
          echo ' value="'.htmlEncode($val).'" ';
          echo ' hasDownArrow="false" ';
          echo ' >';
          $colScript=$obj->getValidationScript($id);
          echo $colScript;
          echo '</div>';
          ?>
          </td>
		  </tr>
          <?php
        }else if($type == 'datetime'){
          ?>
          <tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("col".pq_ucfirst(pq_trim($id)));?></div>
			</td>
		  </tr>
		  <tr>
			<td>
		  <?php 
          $val = (isset($obj->$id))?$obj->$id:date('Y-m-d H:i');
          $name=' id="'.$id.'" name="'.$id.'" ';
          $nameBis=' id="'.$id.'Bis" name="'.$id.'Bis" ';
          if (pq_strlen($val>11)) {
          	$valDate=pq_substr($val, 0, 10);
          	$valTime=pq_substr($val, 11);
          } else {
          	$valDate=$val;
          	$valTime='';
          }
          if ($id=='creationDateTime' and ($val=='' or $val==null) and !$obj->id) {
          	$valDate=date('Y-m-d');
          	$valTime=date("H:i");
          }
          // BEGIN - ADD BY TABARY - TOOLTIP
          //echo htmlDisplayTooltip($toolTip, $fieldId, $print, $outMode);
          // END - ADD BY TABARY - TOOLTIP
          echo '<div dojoType="dijit.form.DateTextBox" ';
          echo $name;
          echo 'required="true"';
          echo ' invalidMessage="'.i18n('messageInvalidDate').'"';
          echo ' type="text" maxlength="10" ';
          if (sessionValueExists('browserLocaleDateFormatJs')) {
          	echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
          }
          $dateWidth='72';
          if (isNewGui()) $dateWidth='85';
          echo ' style="width:'.$dateWidth.'px; text-align: center;" class="input required generalColClass" ';
          echo ' value="'.$valDate.'" ';
          echo ' hasDownArrow="false" ';
          echo ' >';
          $colScript=$obj->getValidationScript($id);
          echo $colScript;
          echo '</div>';
          $fmtDT='time'; // valTime=pq_substr($valTime,0,5);
          echo '<div dojoType="dijit.form.'.(($fmtDT=='time')?'Time':'').'TextBox" ';
          echo $nameBis;
          echo 'required="true"';
          echo ' invalidMessage="'.i18n('messageInvalidTime').'"';
          echo ' type="text" maxlength="8" ';
          if (sessionValueExists('browserLocaleTimeFormat')) {
          	echo ' constraints="{timePattern:\''.getSessionValue('browserLocaleTimeFormat').'\'}" ';
          }
          // echo ' constraints="{datePattern:\'yy-MM-dd\'}" ';
          echo ' style="width:45px; text-align: center;" class="input required" ';
          echo ' value="'.(($fmtDT=='time')?'T':'').$valTime.'" ';
          echo ' hasDownArrow="false" ';
          echo ' >';
          $colScriptBis=$obj->getValidationScript($id."Bis");
          echo $colScriptBis;
          echo '</div>';
          ?>
          </td>
          	</tr>
          <?php
        }else if($type == 'time'){
          ?>
          <tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("col".pq_ucfirst(pq_trim($id)));?></div>
			</td>
		  </tr>
		  <tr>
			<td>
		  <?php 
          $val = (isset($obj->$id))?$obj->$id:date('H:i');
          $name=' id="'.$id.'" name="'.$id.'" ';
          if ($id=='creationTime' and ($val=='' or $val==null) and !$obj->id) {
          	$val=date("H:i");
          }
          $fmtDT='time'; // valTime=pq_substr($valTime,0,5);
          echo '<div dojoType="dijit.form.'.(($fmtDT=='time')?'Time':'').'TextBox" ';
          echo $name;
          echo 'required="true"';
          echo ' invalidMessage="'.i18n('messageInvalidTime').'"';
          $dataLength = $obj->getDataLength($id);
          echo ' type="text" maxlength="'.$dataLength.'" ';
          if (sessionValueExists('browserLocaleTimeFormat')) {
          	echo ' constraints="{timePattern:\''.getSessionValue('browserLocaleTimeFormat').'\'}" ';
          }
          echo ' style="width:'.(($fmtDT=='time')?'60':'65').'px; text-align: center;" class="input required generalColClass" ';
          echo ' value="'.(($fmtDT=='time')?'T':'').$val.'" ';
          echo ' hasDownArrow="false" ';
          echo ' >';
          $colScript=$obj->getValidationScript($id);
          echo $colScript;
          echo '</div>';
          ?>
          </td>
          	</tr>
          <?php
        }else if($type=='int' and $obj->getDataLength($id) == 1){
          ?>
          <tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("col".pq_ucfirst(pq_trim($id)));?></div>
			</td>
		  </tr>
		  <tr>
			<td>
		  <?php
		  $val = (isset($obj->$id))?$obj->$id:null;
          $name=' id="'.$id.'" name="'.$id.'" ';
          if ($id=='cancelled' or $id=='solved') echo "&nbsp;&nbsp;&nbsp;";
          echo '<div dojoType="dijit.form.CheckBox" type="checkbox" ';
          echo $name;
          echo 'required="true"';
          echo ' class="greyCheck generalColClass"';
          if ($val!='0' and !$val==null) {
          	echo 'checked';
          }
          echo ' >';
          $colScript=$obj->getValidationScript($id);
          echo $colScript;
          if (!pq_strpos('formChanged()', $colScript)) {
          	echo '<script type="dojo/connect" event="onChange" args="evt">';
          	echo '    formChanged();';
          	echo '</script>';
          }
          echo '</div>';
          ?>
          </td>
          	</tr>
          <?php
        }else if($type=='int' or $type=='decimal'){ ?>
          <tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("col".pq_ucfirst(pq_trim($id)));?></div>
			</td>
		  </tr>
		  <tr>
			<td colspan="2"> <?php
			$isWork=false;
			$isCost=false;
			if(pq_strpos($id, 'Work'))$isWork=true;
			if(pq_strpos($id, 'Cost'))$isCost=true;
			$currency=Parameter::getGlobalParameter('currency');
			$currencyPosition=Parameter::getGlobalParameter('currencyPosition');
			$val = (isset($obj->$id))?$obj->$id:null;
			if($isWork){
				$val = Work::displayImputation($val);
			}
			$name=' id="'.$id.'" name="'.$id.'" ';
			if($isCost and $currencyPosition=='before'){
				echo '<span style="width:1px;text-align:left;">'.$currency.'&nbsp;</span>';
			}
            echo '<div dojoType="dijit.form.NumberTextBox" class="input required" required="true" style="width:50px;" value="'.$val.'"';
            echo $name.'>';
            echo $keyDownEventScript;
            echo '</div>';
            if($isWork){
              echo '<span style="width:1px;text-align:left;">&nbsp;'.Work::displayShortImputationUnit().'</span>';
            }else if($isCost and $currencyPosition=='after'){
              echo '<span style="width:1px;text-align:left;">&nbsp;'.$currency.'</span>';
            }
           ?></td>
      	 </tr>
            <?php
        }else if($id == 'description') {?>
          <tr>
			<td><div class="dialogLabel"><?php echo i18n("colDescription");?></div></td>
		</tr>
		<tr>
			<td><input id="descriptionEditorType" name="descriptionEditorType"
				type="hidden" value="<?php if (isNewGui()) echo 'CK'; else echo getEditorType();?>" />
         <?php if (getEditorType()=="CK" or isNewGui()) {?> 
          <textarea style="width:<?php echo $detailWidth;?>px; height:<?php echo $detailHeight;?>px"
          name="kanbanDescription" class="required" id="kanbanDescription"></textarea>
        <?php } else if (getEditorType()=="text"){?>
          <textarea dojoType="dijit.form.Textarea" id="description"
					name="description" style="width: 500px;" maxlength="4000"
					class="input required"
					onClick="dijit.byId('description').setAttribute('class','');"></textarea>
        <?php } else {?>
          <textarea dojoType="dijit.form.Textarea" type="hidden"
					id="kanbanDescription" name="kanbanDescription" style="display: none;"></textarea>
				<div data-dojo-type="dijit.Editor" id="kanbanDescriptionEditor"
             data-dojo-props="onChange:function(){window.top.dojo.byId('kanbanDescription').value=arguments[0];}
              ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                        'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
              ,onKeyDown:function(event){window.top.onKeyDownFunction(event,'kanbanDescriptionEditor',this);}
              ,onBlur:function(event){window.top.editorBlur('kanbanDescriptionEditor',this);}
              ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
              style="color:#606060 !important; background:none; 
                padding:3px 0px 3px 3px;margin-right:2px;height:<?php echo $detailHeight;?>px;width:<?php echo $detailWidth;?>px;min-height:16px;overflow:auto;"
              class="input required"></div>
        <?php } ?>
          </td>
        </tr>
        <?php 
         } else{
          ?>
          <tr>
			<td>
				<div class="dialogLabel"><?php echo i18n("col".pq_ucfirst(pq_trim($id)));?></div>
			</td>
		  </tr>
		  <tr>
			<td>
		  <?php
		  $val = (isset($obj->$id))?$obj->$id:'';
		  $name=' id="'.$id.'" name="'.$id.'" ';
          echo '<span dojoType="dijit.form.TextBox" type="text"  ';
          echo $name;
          echo 'required="true"';
          echo ' class="input required generalColClass" ';
          echo ' tabindex="-1" style="width: '.$largeWidth.'px;" ';
          echo ' value="'.$val.'" ></span>';
          ?>
          </td>
          	</tr>
          <?php
        } 
      }
    }
	?>
			<tr><td>&nbsp;</td></tr>
    <tr>
			<td align="center"><input type="hidden" id="dialogKanbanResultAction">
				<button class="mediumTextButton" dojoType="dijit.form.Button"
					type="button"
					onclick="dijit.byId('dialogKanbanUpdate').hide();formChangeInProgress=false;refreshKanban('<?php echo $oldColumn;?>', '<?php echo $newColumn;?>');">
          <?php echo i18n("buttonCancel");?>
        </button>
				<button class="mediumTextButton" id="dialogKanbanUpdateSubmit"
					dojoType="dijit.form.Button" type="submit"
					onclick="protectDblClick(this);saveKanbanResult('<?php echo $oldColumn;?>', '<?php echo $newColumn;?>', '<?php echo $itemID;?>');return false;">
          <?php echo i18n("buttonOK");?>
        </button></td>
		</tr>
	</table>
</form>
<?php
} else if ($typeDynamic == "addKanban") {
	?>
<div style="display: flex; justify-content: center; align-items: center;">
  <form id="kanbanResultForm" name="kanbanResultForm" onSubmit="return false;" >
    <div style="display: flex; align-items: center; height: <?php echo (isNewGui())?'34':'30';?>px; margin: 10px 40px 10px 15px;">
      <label class="dialogLabel" style="text-align: right; margin-right: 10px;position: relative;top:-15%;align-items: center"><?php echo i18n("colName");?> <?php if (!isNewGui()) echo ': ';?></label> 
      <input id="kanbanName" name="kanbanName" style="width: 100%;" type="text" dojoType="dijit.form.TextBox" class="input required" value="" maxlength="50"/>
    </div>
    <div style="display: flex; align-items: center; height: <?php echo (isNewGui())?'34':'30';?>px; margin: 0 40px 10px 15px;">
      <label class="dialogLabel" style="text-align: right; margin-right: 10px;position: relative;top:-15%;"><?php echo i18n("colRefType");?> <?php if (!isNewGui()) echo ': ';?></label>
      <select dojoType="dijit.form.FilteringSelect" class="input required" required="true" <?php echo autoOpenFilteringSelect();?> name="kanbanReffList" id="kanbanReffList" style="width: 100%;">
        <?php if (Security::checkDisplayMenuForUser('Ticket',false)) {?><option value="Ticket"><?php echo i18n('Ticket');?></option><?php }?>
        <?php if (Security::checkDisplayMenuForUser('Activity',false)) {?><option value="Activity"><?php echo i18n('Activity');?></option><?php }?>
        <?php if (Security::checkDisplayMenuForUser('Action',false)) {?><option value="Action"><?php echo i18n('menuAction');?></option><?php }?>
        <?php if (Security::checkDisplayMenuForUser('Requirement',false)) {?><option value="Requirement"><?php echo i18n('menuRequirement');?></option><?php }?>
        <script type="dojo/connect" event="onChange" args="evt">
          var param = dijit.byId('kanbanReffList').get('value');
          if(!param) return;
          dijit.byId('kanbanTypeList').store;
          dojo.byId("kanbanTypeList").value="";
          kanbanRefreshListType("kanbanReffList", "kanbanTypeList", param, "Activity");
        </script>
      </select>
    </div>
    <div style="display: flex; align-items: center; height: <?php echo (isNewGui())?'34':'30';?>px; margin: 0 40px 10px 15px;">
      <label class="dialogLabel" style="text-align: right; margin-right: 10px;position: relative;top:-15%;"><?php echo i18n("colType");?> <?php if (!isNewGui()) echo ': ';?></label> 
      <select dojoType="dijit.form.Select" class="input required" required="true" default="" style="width: 100%;" name="kanbanTypeList" id="kanbanTypeList">
        <option value=""></option>
        <option value="Status"><?php echo i18n("colIdStatus");?></option>
        <option value="TargetProductVersion"><?php echo i18n("colIdTargetProductVersion"); ?></option>
        <option value="Activity"><?php echo i18n("colPlanningActivity");?></option>
        <?php if(Module::isModuleActive('moduleTargetMilestone')){?>
          <option value="Milestone"><?php echo i18n("colIdTargetMilestone");?></option>
        <?php }?>
      </select>
    </div>
    <div style="display: flex; align-items: center; margin: 0px 40px 20px 15px;">
      <label class="dialogLabel" style="text-align: center;"><?php echo i18n("kanbanSharedCheck");?> <?php if (!isNewGui()) echo ': ';?></label>
      <div id="kanbanShared" style="position: relative; right: 58px;" name="kanbanShared" type="checkbox" dojoType="dijit.form.CheckBox" ></div>
    </div>
    <table style="width: 100%; margin-bottom:10px;">
      <tr>
        <td align="center">
          <input type="hidden" id="dialogKanbanResultAction">
          <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogKanbanUpdate').hide();">
            <?php echo i18n("buttonCancel");?>
          </button>
          <button class="mediumTextButton" id="dialogKanbanUpdateSubmit" dojoType="dijit.form.Button" type="submit" onclick="protectDblClick(this);plgAddKanban();return false;">
            <?php echo i18n("buttonOK");?>
          </button>
        </td>
      </tr>
    </table>
  </form>
</div>
	
<?php
} else if ($typeDynamic == "addColumnKanban") {
  $limitPlanning=Parameter::getGlobalParameter('limitPlanningActivity');
	if (! pq_array_key_exists ( 'typeD', $_REQUEST )) {
		throwError ( 'Parameter typeD not found in REQUEST' );
	}
	$typeD = $_REQUEST ['typeD'];
	if (! pq_array_key_exists ( 'idKanban', $_REQUEST )) {
		throwError ( 'Parameter idKanban not found in REQUEST' );
	}
	$idFrom = - 1;
	if (pq_array_key_exists ( 'idFrom', $_REQUEST )) {
		$idFrom = $_REQUEST ['idFrom'];
	}
	$idKanban = $_REQUEST ['idKanban'];
	$kanban = new Kanban ( $idKanban, true );
	$json = json_decode ( $kanban->param, true );
	$listForbiden = array ();
	$kanbanColumnName = array();
	if (isset ( $json ['column'] ))
		foreach ( $json ['column'] as $line ) {
			$listForbiden [] = $line ['from'];
			$kanbanColumnName[$line['from']] = $line['name'];
		}
	$typeData = $json ['typeData'];
	if ($typeD == 'Status') {
		$status = new Status ();
		$tableName = $status->getDatabaseTableName ();
		$workflowStatus = new WorkflowStatus ();
		$tableName2 = $workflowStatus->getDatabaseTableName ();
		$type = new Type ();
		$tableName3 = $type->getDatabaseTableName ();
		$result = Sql::query ( "SELECT s.id as id, s.name as name from $tableName s where s.idle=0 and (s.id in (select idStatusFrom from $tableName2 w, $tableName3 t where t.idWorkflow=w.idWorkflow and t.scope='$typeData')
      or s.id in (select idStatusTo from $tableName2 w, $tableName3 t where t.idWorkflow=w.idWorkflow and t.scope='$typeData') ) order by s.sortOrder" );
		$listToHave = array ();
		while ( $line = Sql::fetchLine ( $result ) ) {
			$listToHave [$line ['id']] = $line ['name'];
		}
	} else {
		$crit = array (
				'idle' => '0' 
		);
		$selectedProject=Project::getSelectedProject();
		if ($typeD != 'Project' and property_exists ( $typeD, 'idProject' ) 
		and $selectedProject and $selectedProject!= '*' and pq_strpos($selectedProject,',')===false) {
			$crit ['idProject'] = $selectedProject;
		}
		// if ($limitPlanning=='YES' and $typeD=='Activity' and $typeData=='Ticket') {  // This if we want restriction only if restriction parameter is set
		if ($typeD=='Activity' and $typeData=='Ticket') { // This if we want restriction whatever the restriction parameter : we'll list only Actual Planning Activities
		  $crit['isPlanningActivity']='1';
		}
		$listToHave=array();
		if ($typeD == 'Milestone') {
		  $where = 'idle = 0 and idProject in '.getVisibleProjectsList();
		  $milestone = new Milestone();
		  $milestoneList = $milestone->getSqlElementsFromCriteria(null,null,$where);
		  foreach ($milestoneList as $ms){
		    $listToHave[$ms->id] = $ms->name;
		  }
		}else{
		  $listToHave = SqlList::getListWithCrit ( $typeD, $crit );
		}
		if ($typeD == 'TargetProductVersion') {
			$restrictArray = getSessionUser ()->getVisibleVersions ();
			$listToHave = array_intersect_key ( $listToHave, $restrictArray );
		}
		if ($typeD == 'TargetProductVersion' or $typeD == 'Milestone' or $typeD == 'Activity') {
            $listToHave[0] = i18n('undefinedValue');
            ksort($listToHave);
        }
	}
	$listFinal = array ();
	foreach ( $listToHave as $elmId => $elmName ) {
		$find = false;
		for($iterateur = 0; $iterateur < count ( $listForbiden ) && ! $find; $iterateur ++) {
			$find = $listForbiden [$iterateur] == $elmId;
		}
		if (! $find and $elmId !=0) {
			$listFinal [$elmId] = $elmName;
		}
	}
	$valText = '';
	if ($idFrom != - 1) {
		if (isset ( $json ['column'] ))
			foreach ( $json ['column'] as $line ) {
				if ($line ['from'] == $idFrom)
					$valText = $line ['name'] != null ? $line ['name'] : '';
			}
	}
	?>
<form id='kanbanResultForm' name='kanbanResultForm' onSubmit="return false;" style="overflow:hidden;text-align:center">
	<table style="width: 100%;">
<?php
/*	if ($typeD !== "Status") {
      echo '<div style="height:'.((isNewGui())?'34':'30').'px;"><label class="dialogLabel">' . i18n ( "colName" );?> <?php if (!isNewGui()) echo ': ';?></label>
		  <input id="kanbanName" name="kanbanName" style="width: 150px" type="text" dojoType="dijit.form.TextBox" class="input" value="<?php echo $valText;?>" />
	  </div>
<?php
	  if ($idFrom == - 1) {
		$trad = "colIdTargetProductVersion";
		if ($typeD == "Activity") $trad = "colPlanningActivity";
		if ($typeD == "Status")	$trad = "colIdStatus";
		
		echo '<div style="height:40px;"><label class="dialogLabel">' . i18n ( $trad ); ?> <?php if (!isNewGui()) echo ': ';?></label>
  		  <select dojoType="dijit.form.Select" class="input required" required="true" style="width: 150px;" name="kanbanTypeList"	id="kanbanTypeList">
          <?php foreach ($listFinal as $elmId => $elmName){?>
            <option value="<?php echo $elmId;?>"><?php echo $elmName;?></option>
          <?php }?>
          </select>
		</div>
	    <tr><td>&nbsp;</td></tr>
        <?php }
    }*/?>
	  	<?php $limitPlanning=Parameter::getGlobalParameter('limitPlanningActivity');?>
      <tr style="overflow:auto">
        <div>
          <table id="idTableKanbanColumn" style="margin:10px; display:block;overflow:auto;height:auto;text-align:left">
            <thead style="border-right:1px solid">
              <tr>
              <?php foreach ($listToHave as $id => $stat) {
                 if (in_array($stat, $listFinal)) { ?>
                  <td id="rowKanban_<?php echo $id; ?>" style="border-bottom: 1px solid black;border-top:1px solid black;">
                  <div id="divNameColumn_<?php echo $id;?>" style="padding:5px;display:none;">
                <?php } else { 
                   if ($typeD !== "Status" ) { ?>
                 <td id="rowKanban_<?php echo $id ?>" style="border-bottom: 1px solid black;border-top:1px solid black;border-left: 1px solid black;border-right: 1px solid black;">
                  <div id="divNameColumn_<?php echo $id;?>" style="padding:5px;">
                   <?php } else { ?>
                 <td id="rowKanban_<?php echo $id ?>" style="border-bottom: 1px solid black;border-top:1px solid black;border-left: 1px solid black;">
                  <div id="divNameColumn_<?php echo $id;?>" style="padding:5px;">
                   <?php }?>
                <?php   }?>
                  <label id="labelNameColumn_<?php echo $id;?>" for="nameColumn_<?php echo $id;?>" style="width:auto; margin-left:5px;"><?php echo i18n('columnName');?></label>
                  <input id="nameColumn_<?php echo $id;?>" style="width:100px; margin-left:5px;" data-dojo-type="dijit/form/TextBox" class="input required" type="text" name="nameColumn_<?php echo $id;?>" value="<?php echo isset($kanbanColumnName[$id])?$kanbanColumnName[$id]: $stat;?>"/>
                </div>
              </td>
            <?php }?>
              </tr>
            </thead>
            <tbody>
              <tr> 
                <?php foreach ($listToHave as $id => $stat) {?>
                    <td id="formKanbanColumn_<?php echo $id;?>" style="border: 1px solid black; position:relative; min-width:180px; max-width:auto;min-height:40px; padding:10px;">
                      <table style="width: 100%;">
                        <tr>
                          <td style="padding-right: 10px;width:26px">
                            <input id="checkboxKanban_<?php echo $id;?>" type="checkbox" <?php if ($id == array_key_first($listToHave)) { ?>readonly='true'<?php } ?> data-dojo-type="dijit/form/CheckBox" class="whitecheck" name="checkboxKanbanColumn" value="<?php echo ($id == 0) ? 'n' : $id; ?>" <?php if (!in_array($stat, $listFinal)) echo 'checked'; ?> onclick="changeStatKanban(<?php echo $id; echo ($typeD == 'Status') ? ',true' : ''; ?>);" />
                          </td>
                          <td>
                            <label for="checkboxKanban_<?php echo $id;?>" style="width:auto;text-align:left;margin-top:2px"><?php echo $stat; ?></label>
                          </td>
                        </tr>
                      </table>
                    </td>
                <?php }?>
              </tr>
            </tbody>
          </table>
        </div>
      </tr>
      <tr>
			<td><input type="hidden" id="dialogKanbanResultAction">
				<button class="mediumTextButton" dojoType="dijit.form.Button"
					type="button"
					onclick="dijit.byId('dialogKanbanUpdate').hide();formChangeInProgress=false;">
                  <?php echo i18n("buttonCancel");?>
                </button>
				<button class="mediumTextButton" id="dialogKanbanUpdateSubmit"
					dojoType="dijit.form.Button" type="submit"
					onclick="protectDblClick(this);plgEditColumnKanban(<?php echo $idKanban;?>,<?php echo $idFrom;?>,<?php echo $typeD=="Status"?'true':'false';?>,'<?php echo $typeD;?>');return false;">
                  <?php echo i18n("buttonOK");?>
                </button>
             </td>
		</tr>
	</table>
</form>
<?php
} else if ($typeDynamic == "editKanban") {
	$idKanban = $_REQUEST ['idKanban'];
	$kanban = new Kanban ( $idKanban );
	$paramJson = json_decode ( $kanban->param, true );
	if (! isset ( $paramJson ['typeData'] )) {
		$paramJson ['typeData'] = 'Ticket';
		$kanban->param = json_encode ( $paramJson );
		$kanban->save ();
	}
	?>
<form id='kanbanResultForm' name='kanbanResultForm'
	onSubmit="return false;">
	<div style="height: 40px;">
		<label class="dialogLabel"><?php echo i18n("colName");?> <?php if (!isNewGui()) echo ': ';?></label><input
			id="kanbanName" name="kanbanName" style="width: 150px;" type="text"
			dojoType="dijit.form.TextBox" class="input required"
			value="<?php echo $kanban->name;?>" />
	</div>
	<table style="width: 100%;">
		<tr>
			<td>
				<div style="height: 40px;">
					<label class="dialogLabel"><?php echo i18n("colReffType");?> <?php if (!isNewGui()) echo ': ';?></label>
					<select dojoType="dijit.form.FilteringSelect"
						class="input required" required="true" readonly
						<?php echo autoOpenFilteringSelect ();?> name="kanbanReffList"
						id="kanbanReffList">
							<?php foreach (array('Ticket','Activity','Action','Requirement') as $typ) {
  					    if ($paramJson['typeData']==$typ or Security::checkDisplayMenuForUser($typ,false)) {?>
  					      <option value="<?php echo $typ;?>" <?php echo ($paramJson['typeData']==$typ)?'selected':'';?> ><?php echo i18n($typ);?></option>
  					    <?php }?>
					    <?php }?>  
					</select>
				</div>
			</td>
		</tr>
		<tr><td>&nbsp;</td></tr>
		<tr>
			<td align="center"><input type="hidden" id="dialogKanbanResultAction">
				<button class="mediumTextButton" dojoType="dijit.form.Button"
					type="button" onclick="dijit.byId('dialogKanbanUpdate').hide();">
                    <?php echo i18n("buttonCancel");?>
                </button>
				<button class="mediumTextButton" id="dialogKanbanUpdateSubmit"
					dojoType="dijit.form.Button" type="submit"
					onclick="protectDblClick(this);saveEditKanban(<?php echo $idKanban;?>);return false;">
                    <?php echo i18n("buttonOK");?>
        </button></td>
		</tr>
	</table>
</form>
</div>
<?php
}
?>