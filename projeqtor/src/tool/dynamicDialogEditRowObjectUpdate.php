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

$detailHeight = 300;
$detailWidth = 400;

$keyDownEventScript=NumberFormatter52::getKeyDownEvent();

$idObj = RequestHandler::getId('editRowObjectId');
$typeObj = RequestHandler::getClass('editRowObjectClass');
$peName = $typeObj.'PlanningElement';
$obj = new $typeObj($idObj);

$currentFormFields = RequestHandler::getValue('currentFormFields');
$currentFormFields = json_decode($currentFormFields);

$extraRequiredFields = RequestHandler::getValue('extraRequiredFields');
$extraRequiredFields = json_decode($extraRequiredFields);

$flatRequired = array();
$requiredField = array();
if($extraRequiredFields){
	$requiredField = array();
	foreach ($extraRequiredFields as $col=>$option){
	 $field = (pq_strpos($col, $peName) > -1)?pq_str_replace($peName.'_', '', $col):$col;
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
<form dojoType="dijit.form.Form" id='editRowObjectResultForm' name='editRowObjectResultForm' action="" method="post"
	onSubmit="return false;">
	<input id="objectClassName" name="objectClassName" type="hidden" value="<?php echo $typeObj;?>">
	<input id="objectIdRow" name="objectIdRow" type="hidden" value="<?php echo $idObj;?>">
	<table style="width: 100%;">
	<tr>
	 <td>
	 <?php foreach ($currentFormFields as $field=>$value){?>
	   <input type="hidden" id="<?php echo $field; ?>" name="<?php echo $field; ?>" value="<?php echo $value; ?>"/>
	 <?php }?>
	 </td>
	</tr>
	<?php 
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
                  $idProject = (isset($obj->idProject))?$obj->idProject:null;
          		  htmlDrawOptionForReference ( $id, $val, null, true, null, $idProject );
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
          id="editRowObjectDescription" name="description" class="input required"></textarea>
        <?php } else if (getEditorType()=="text"){?>
          <textarea dojoType="dijit.form.Textarea" id="description"
					name="description" style="width: 500px;" maxlength="4000"
					class="input required"
					onClick="dijit.byId('description').setAttribute('class','');"></textarea>
        <?php } else {?>
          <textarea dojoType="dijit.form.Textarea" type="hidden"
					id="editRowObjectDescription" name="description" style="display: none;"></textarea>
				<div data-dojo-type="dijit.Editor" id="editRowObjectDescriptionEditor" name="editRowObjectDescriptionEditor"
             data-dojo-props="onChange:function(){window.top.dojo.byId('editRowObjectDescription').value=arguments[0];}
              ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                        'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
              ,onKeyDown:function(event){window.top.onKeyDownFunction(event,'editRowObjectDescriptionEditor',this);}
              ,onBlur:function(event){window.top.editorBlur('editRowObjectDescriptionEditor',this);}
              ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
              style="color:#606060 !important; background:none; 
                padding:3px 0px 3px 3px;margin-right:2px;height:<?php echo $detailHeight;?>px;width:<?php echo $detailWidth;?>px;min-height:16px;overflow:auto;"
              class="input required"></div>
        <?php } ?>
          </td>
        </tr>
        <?php 
         }else if($id=="result"){ ?>
           <tr>
           <td><div class="dialogLabel"><?php echo i18n("colMandatoryResultOnDone");?></div></td>
           		</tr>
           		<tr>
           			<td><input id="resultEditorType" name="resultEditorType"
           				type="hidden" value="<?php if (isNewGui()) echo 'CK'; else echo getEditorType();?>" />
                    <?php if (getEditorType()=="CK" or isNewGui()) {?> 
                     <textarea style="width:<?php echo $detailWidth;?>px; height:<?php echo $detailHeight;?>px"
                     id="editRowObjectResult" name="result" class="input required"></textarea>
                   <?php } else if (getEditorType()=="text"){?>
                     <textarea dojoType="dijit.form.Textarea" id="result"
           					name="result" style="width: 500px;" maxlength="4000"
           					class="input required"
           					onClick="dijit.byId('result').setAttribute('class','');"></textarea>
                   <?php } else {?>
                     <textarea dojoType="dijit.form.Textarea" type="hidden"
           					id="editRowObjectResult" name="result" style="display: none;"></textarea>
           				<div data-dojo-type="dijit.Editor" id="editRowObjectResultEditor" name="editRowObjectResultEditor"
                        data-dojo-props="onChange:function(){window.top.dojo.byId('editRowObjectResult').value=arguments[0];}
                         ,plugins:['removeFormat','bold','italic','underline','|', 'indent', 'outdent', 'justifyLeft', 'justifyCenter', 
                                   'justifyRight', 'justifyFull','|','insertOrderedList','insertUnorderedList','|']
                         ,onKeyDown:function(event){window.top.onKeyDownFunction(event,'editRowObjectResultEditor',this);}
                         ,onBlur:function(event){window.top.editorBlur('editRowObjectResultEditor',this);}
                         ,extraPlugins:['dijit._editor.plugins.AlwaysShowToolbar','foreColor','hiliteColor']"
                         style="color:#606060 !important; background:none; 
                           padding:3px 0px 3px 3px;margin-right:2px;height:<?php echo $detailHeight;?>px;width:<?php echo $detailWidth;?>px;min-height:16px;overflow:auto;"
                         class="input required"></div>
                   <?php }?>
                 </td>
           		</tr>
   		 <?php
         }else{
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
			<td align="center"><input type="hidden" id="dialogEditRowObjectResultAction">
				<button class="mediumTextButton" dojoType="dijit.form.Button"
					type="button"
					onclick="dijit.byId('dialogEditRowObjectUpdate').hide();">
          <?php echo i18n("buttonCancel");?>
        </button>
				<button class="mediumTextButton" id="dialogEditRowObjectUpdateSubmit"
					dojoType="dijit.form.Button" type="submit"
					onclick="protectDblClick(this);JSGantt.saveEditRowObject(true, null);return false;">
          <?php echo i18n("buttonOK");?>
        </button></td>
		</tr>
	</table>
</form>
</div>