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
 * Presents the action buttons of an object.
 * 
 */ 
  require_once "../tool/projeqtor.php";
  scriptLog('   ->/view/objectMultipleUpdate.php');

  $objectClass=$_REQUEST['objectClass'];
  Security::checkValidClass($objectClass);
  if (!$objectClass) exit;
  $displayWidth='98%';
  $spaceWidth='33%';
  $helpWidth=25;
  $labelWidth=250;
  if (isNewGui()) {
    $labelWidth=300;
    $helpWidth=60;
  }
  $labelSelect=i18n("selectedItemsCount");
  $currentScreen=getSessionValue('currentScreen');
  if ($currentScreen=='Object') $currentScreen=$objectClass;
  if(Parameter::getUserParameter("paramScreen_".$currentScreen)){
    $paramDetailDiv=Parameter::getUserParameter("paramScreen_".$currentScreen);
  }else{
    $paramDetailDiv=Parameter::getUserParameter("paramScreen");
  }
  $layout=($paramDetailDiv=='left')?'vertical':'horizontal';
  if (pq_array_key_exists('destinationWidth',$_REQUEST)) {
    $width=RequestHandler::getValue("destinationWidth");
    if ($layout=='vertical') $displayWidth=intval($width)-30;
    else $displayWidth=floor($width*0.6);
    if ($displayWidth<650) $labelSelect=i18n("selectedItemsCountShort");
    //if (isNewGui()) $labelWidth=max(300,($displayWidth/2)-15);
    $fieldWidth=$displayWidth-$labelWidth-15-15;
    $spaceWidth=$displayWidth-775;
    if ($spaceWidth<0) $spaceWidth=0;
    //else $spaceWidth=$spaceWidth.'px';
    $spaceWidth=$spaceWidth.'px';
    if ($fieldWidth<150) {
      $labelWidth=$labelWidth-150+$fieldWidth;
      $fieldWidth=150;
    }
  } 
  $obj=new $objectClass();
  $keyDownEventScript=NumberFormatter52::getKeyDownEvent();
?>


<div dojoType="dijit.layout.BorderContainer" class="background" id="objetMultipleUpdate">
  <input hidden id="showActicityStream" name="showActicityStream" value="<?php echo getSessionValue('showActicityStream');?>">
    <div id="buttonDiv" dojoType="dijit.layout.ContentPane" region="top" 
		style="z-index: 3; height: 35px; position: relative; overflow: visible !important;">
<!--     <div dojoType="dijit.layout.BorderContainer" > -->
      <div>
        <table width="100%" class="listTitle" >
          <tr valign="middle" height="32px"> 
            <td width="50px" align="center" class="iconHighlight" >
            <?php if (isNewGui()) {?>
              <div style="position: absolute; top: 7px; left: 14px">
              <?php echo formatIcon($objectClass, 22,null,false);?> 
              </div>
            <?php } else {?>
              <div style="position: absolute; top: 7px; left: 14px">
              <?php echo formatIcon($objectClass, 22,null,false);?> 
              </div>    
            <?php }?>
            </td>
            <td valign="middle"><span class="title"><?php echo i18n('labelMultipleMode');?></span></td>
            <td width="50px">&nbsp;</td>
            <td style="white-space;nowrap"">
              <?php echo $labelSelect;?> :
              <input type="text" id="selectedCount"
                style="font-weight: bold;background: transparent;border: 0px;width:10%;min-width:35px;<?php if (! isNewGui()) echo 'color: white;';?>" 
                value="0" readOnly />
            </td>
            <td width="15px">&nbsp;</td>
            <td><span class="nobr"><div id="buttonDivContainerDiv" style="float:right;position:relative;width:fit-content;white-space:nowrap;padding-right: 15px;">
            <button id="selectAllButton" dojoType="dijit.form.Button" showlabel="false" 
               title="<?php echo i18n('buttonSelectAll');?>"
               iconClass="iconSelectAll" class="detailButton" >
                <script type="dojo/connect" event="onClick" args="evt">
                   hideExtraButtons('extraButtonsDetail');
                   selectAllRows('objectGrid');
                   updateSelectedCountMultiple();
                </script>
              </button>
              <button id="unselectAllButton" dojoType="dijit.form.Button" showlabel="false" 
               title="<?php echo i18n('buttonUnselectAll');?>"
               iconClass="iconUnselectAll" class="detailButton" >
                <script type="dojo/connect" event="onClick" args="evt">
                   hideExtraButtons('extraButtonsDetail');
                   unselectAllRows('objectGrid');
                   updateSelectedCountMultiple();
                </script>
              </button>    
<!--             </span></td> -->
<!--            <td style="width:<?php //echo $spaceWidth;?>">&nbsp;</td> -->
<!--             <td><span class="nobr"> -->
              <button id="saveButtonMultiple" dojoType="dijit.form.Button" showlabel="false"
               title="<?php echo i18n('buttonSaveMultiple');?>"
               iconClass="dijitButtonIcon dijitButtonIconSave" class="detailButton" >
                <script type="dojo/connect" event="onClick" args="evt">
                  hideExtraButtons('extraButtonsDetail');
                  saveMultipleUpdateMode("<?php echo $objectClass;?>");  
                </script>
              </button>
              <?php organizeButtons();?>
              <button id="deleteButtonMultiple" dojoType="dijit.form.Button" showlabel="false"
               title="<?php echo i18n('buttonDeleteMultiple');?>"
               iconClass="dijitButtonIcon dijitButtonIconDelete" class="detailButton" >
                <script type="dojo/connect" event="onClick" args="evt">
                  hideExtraButtons('extraButtonsDetail');
                  deleteMultipleUpdateMode("<?php echo $objectClass;?>");  
                </script>
              </button>
              <?php 
              if(Parameter::getUserParameter('paramRightDiv_'.$currentScreen)){
                $paramRightDiv=Parameter::getUserParameter('paramRightDiv_'.$currentScreen);
              }else{
                $paramRightDiv=Parameter::getUserParameter('paramRightDiv');
              }
              $showActivityStream=false;
              if($paramRightDiv=="bottom"){
                $activityStreamSize=getHeightLayoutActivityStream($currentScreen);
                $activityStreamDefaultSize=getDefaultLayoutSize('contentPaneRightDetailDivHeight');
              }else{
                $activityStreamSize=getWidthLayoutActivityStream($currentScreen);
                $activityStreamDefaultSize=getDefaultLayoutSize('contentPaneRightDetailDivWidth');
              }
              
              ?>
              <?php organizeButtonsEnd();?>
              <button id="undoButtonMultiple" dojoType="dijit.form.Button" showlabel="false"
               title="<?php echo i18n('buttonQuitMultiple');?>"
               iconClass="dijitButtonIcon dijitButtonIconExit" class="detailButton" >
                <script type="dojo/connect" event="onClick" args="evt">
                  hideExtraButtons('extraButtonsDetail');
                  if(dojo.byId('showActicityStream').value=='show'){
                    saveDataToSession('showActicityStream','hide');
                    hideStreamMode('true','<?php echo $paramRightDiv;?>','<?php echo $activityStreamDefaultSize;?>',false);
                  }
                  dojo.byId("undoButtonMultiple").blur();
                  endMultipleUpdateMode("<?php echo $objectClass;?>");
                </script>
              </button>    
            </div></span></td>

          </tr>
        </table>

    </div>
   <div id="detailBarShow" class="dijitAccordionTitle" onMouseover="hideList('mouse');" onClick="hideList('click');">
     <div id="detailBarIcon" align="center">
   </div>
      </div>
      <div dojoType="dijit.layout.ContentPane" region="center" 
       style="z-index: 3; height: 35px; position: absolute !important; overflow: visible !important;">
      </div>
<!--     </div> -->
  </div>
  <div dojoType="dijit.layout.ContentPane" region="center" >
    <div dojoType="dijit.layout.BorderContainer" class="background">
      <div dojoType="dijit.layout.ContentPane" region="center" style="overflow-y: auto">
        <form dojoType="dijit.form.Form" id="objectFormMultiple" jsId="objectFormMultiple" 
          name="objectFormMultiple" encType="multipart/form-data" action="" method="">
          <script type="dojo/method" event="onSubmit">
            return false;        
          </script>
          <input type="hidden" id="selection" name="selection" value=""/>
          <input type="hidden" id="selectionIdMultipleInsert" name="selectionIdMultipleInsert" value=""/>
          <input type="hidden" id="selectionValueMultipleInsert" name="selectionValueMultipleInsert" value=""/>
          <input type="hidden" id="dataTypeSelected"  />
          <div style="width: 100%; padding-top:10px;" >
           <table style="width:100%" >
             <tr style="height:30px">
              <td style="text-align-last:center;"><div><span style="position:relative;"><?php echo i18n("forField");?></span></div></td>
             </tr>
             <tr>
              <td style="text-align-last:center;">
                <div dojoType="dojo.data.ItemFileReadStore" jsId="attributeMultipleUpadteStore" 
                  url="../tool/jsonList.php?listType=object&actualView=MultipleUpadate&objectClass=<?php echo  $objectClass;?><?php echo Security::addTokenIndexToUrl();?>" 
                  searchAttr="name" >
                </div>
                <select dojoType="dijit.form.FilteringSelect" 
                 <?php echo autoOpenFilteringSelect();?>
                  id="idMultipleUpdateAttribute" name="idMultipleUpdateAttribute" 
                  missingMessage="<?php echo i18n('attributeNotSelected');?>"
                  class="input" value="" style="width: <?php echo (isNewGui())?'180':'200';?>px;" store="attributeMultipleUpadteStore">
                    <script type="dojo/method" event="onChange" >
                    multipleUpadteSelectAtribute(this.value);
                  </script>              
                 </select>
              </td>
            </tr>
            <tr style="height:50px">
             <td id="operatorTd" style="text-align-last:center;">
               <div id="multipleUpdateOperateur"  >
               </div>
             </td>
             </tr>
             <tr>
             <td >
               <div id="divListElement" style="text-align:-webkit-center;tex-align:-moz-center;">
                <textarea dojoType="dijit.form.Textarea" id="multipleUpdateTextArea" name="multipleUpdateTextArea" style="width:90%;min-width:300px;min-height:150px;font-size: 90%; background:#ffffff;display:none;" 
                class="input" maxlength="4000" ></textarea>
                <div style="margin-right: 18%;width: 60%;margin-left: 22%;">
                  <select id="multipleUpdateValueList" name="multipleUpdateValueList[]" value=""  dojoType="dijit.form.MultiSelect" 
                   style="width:90%;font-size:10pt;color:#555555;height:150px;display:none;float:left;" size="10" class="selectList">
                  </select>
                  <button style="display:none;width:<?php echo (isNewGui())?"1%":"22px";?>;margin-left:2%;float:left;" id="showDetailInMultipleUpdate" dojoType="dijit.form.Button" showlabel="false"
                        title="<?php echo i18n('showDetail')?>" class="resetMargin notButton notButtonRounded"
                        iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                        <script type="dojo/connect" event="onClick" args="evt">
                        var objectName = dijit.byId('showDetailInMultipleUpdate').get('value');
                        if( objectName ){
                          var objectClass=objectName[0].substr(2);
                          if (objectName[0].indexOf('__id')>=0) {
                            objectClass=objectName[0].substr(objectName[0].indexOf('__id')+4);
                          }  
                          if (objectClass=='TargetProductVersion' || objectClass=='OriginalProductVersion') objectClass='ProductVersion';
                          if (objectClass=='TargetComponentVersion' || objectClass=='OriginalComponentVersion') objectClass='ComponentVersion';
                          dijit.byId('multipleUpdateValueList').reset();
                          showDetail('multipleUpdateValueList',0,objectClass,false);
                        }
                      </script>
                    </button>
                </div>
          			<a id="multipleInsert" name="multipleInsert" onClick="addMultipleInsert()" title="" class="roundedButtonSmall" style="display:none;"><?php echo formatMediumButton('Add') ?></a>
                <input id="newMultipleUpdateValue" name="newMultipleUpdateValue" value=""    dojoType="dijit.form.TextBox"  style="width:320 px;display:none;" />
                <div id="newMultipleUpdateValueNum" name="newMultipleUpdateValueNum" value=""    dojoType="dijit.form.NumberTextBox"  
                 class="input" hasDownArrow="true"style="width:200px;display:none;"><?php echo $keyDownEventScript;?></div>
                <div id="formatInputation" style="display:none;">&nbsp;<?php echo Work::displayShortImputationUnit();?></div>
                <div id="formatWork" style="display:none;">&nbsp;<?php echo Work::displayShortWorkUnit();?></div>
                <input id="isLongText" name="isLongText" value=""  dojoType="dijit.form.TextBox"  style="width:320 px;display:none;" />
                <div>
                <?php if (isNewGui()) {?>
                  <div  id="multipleUpdateValueCheckboxSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="off" hidden
                 leftLabel="" rightLabel="" style="width:10px;position:relative; top:0px;left:5px;z-index:99;display:none;" >
  		           <script type="dojo/method" event="onStateChanged" >
  		             dijit.byId("multipleUpdateValueCheckbox").set("checked",(this.value=="on")?true:false);
  		           </script>
  		          </div>
  		          <?php }?>
  		          <input type="checkbox" id="multipleUpdateValueCheckbox" name="multipleUpdateValueCheckbox" value=""  dojoType="dijit.form.CheckBox" style="padding-top:7px;margin-left:5px;display:none;";/> 
                </div>
                <input id="multipleUpdateValueDate" name="multipleUpdateValueDate" value=""  dojoType="dijit.form.DateTextBox" constraints="{datePattern:browserLocaleDateFormatJs}"  style="width:100px;display:none;" />
                <input id="multipleUpdateValueTime" name="multipleUpdateValueTime" value=""  dojoType="dijit.form.TimeTextBox"   style="width:75px;display:none;margin-top:15px;" />
                <input id="multipleUpdateColorButtonInput" name="multipleUpdateColorButtonInput" value=""  dojoType="dijit.form.TextBox"   style="width:75px;display:none;margin-top:15px;" />
                <input type="color" id="multipleUpdateColorButton" name="multipleUpdateColorButton" onChange="dojo.byId('multipleUpdateColorButtonInput').value = this.value;formChanged()" value="" style="width:32px;height:32px; display:none; border-radius: 5px 5px 5px 5px; cursor: pointer; border-color: gray;"/> 
                 <!-- 
                 old input, palette color, dosent use now,
                 for rework need change id "multipleUpdateColorButton2" to "multipleUpdateColorButton"  and in projeqtorDialog.js 
                 where "dojo.style(dojo.byId('multipleUpdateColorButton')," to " dojo.style(dijit.byId('multipleUpdateColorButton').domNode," 
                 -->
                 <div id="multipleUpdateColorButton2" dojoType="dijit.form.DropDownButton" style="position:relative;<?php echo (isNewGui())?'border:0 !important;width:60px;':'width:40px';?>;display:none;"
                 title="<?php echo i18n('selectColor');?>"showlabel="false" iconClass="colorSelector" class="dropDownNoBorder">
                  <div dojoType="dijit.ColorPalette" style="<?php echo (isNewGui())?'border:0;':'';?>">
                    <script type="dojo/method" event="onChange" >
                      var fld=dojo.byId("multipleUpdateColorButton");
                      fld.style.color=this.value;
                      fld.style.backgroundColor=this.value;
                      fld.value=this.value;
                      dijit.byId('multipleUpdateColorButtonInput').set('value',this.value);
                    </script>
                  </div>
                </div>
                
                <div id="multipleUpdateValueHatch" name="multipleUpdateValueHatch" dojoType="dijit.form.Select" labelType="html" spanLabel="true" style="display:none;width:70px;">
				  <span value=" "></span>
    			  <span value="slashDark"><img src="images/hatchPatternSlashDark.png"/></span>
          		  <span value="backslashDark"><img src="images/hatchPatternBackslashDark.png" /></span>
                  <span value="verticalDark"><img src="images/hatchPatternVerticalDark.png" /></span>
                  <span value="slashDarkLarge"><img src="images/hatchPatternSlashDarkLarge.png" /></span>
                  <span value="backslashDarkLarge"><img src="images/hatchPatternBackslashDarkLarge.png" /></span>
                  <span value="verticalDarkLarge"><img src="images/hatchPatternVerticalDarkLarge.png" /></span>
                  <span value="slash"><img src="images/hatchPatternSlash.png" /></span>
                  <span value="backslash"><img src="images/hatchPatternBackslash.png" /></span>
                  <span value="vertical"><img src="images/hatchPatternVertical.png" /></span>
                  <span value="slashLarge"><img src="images/hatchPatternSlashLarge.png" /></span>
                  <span value="backslashLarge"><img src="images/hatchPatternBackslashLarge.png" /></span>
                  <span value="verticalLarge"><img src="images/hatchPatternVerticalLarge.png" /></span>
			    </div>
                
              </div>
             </td>
            </tr>
           <?php  //gautier #533
            if(get_class($obj)=="User" and property_exists(get_class($obj), 'password') and securityGetAccessRightYesNo('menu'.get_class($obj), 'update', $obj)=='YES'){?>
            <tr><td><div>&nbsp;</div></td></tr>
            <tr class="detail">
              <td style="text-align-last:center;">
                <button id="resetPassword" dojoType="dijit.form.Button" showlabel="true"' 
                        class="generalColClass" title="<?php echo i18n('resetPassword');?>" >
                  <span><?php echo i18n('resetPassword');?></span>
                  <script type="dojo/connect" event="onClick" args="evt">
                    multipleUpdateResetPwd("<?php echo $objectClass;?>");
                  </script>
                </button>
              </td>
            </tr>
          <?php  } ?>  
          </table>
          </div>
        </form>
      </div>
      <div dojoType="dijit.layout.ContentPane" id="resultDivMultiple" 
      region="<?php echo ($layout=='vertical')?'bottom':'right';?>" class="listTitle multipleResultDiv" 
      style="<?php echo ($layout=='vertical')?'height:50%;border-top:1px solid var(--color-detail-header-border);':'width:38%;border-left:1px solid var(--color-detail-header-border);';?>">
         <span class="labelMessageEmptyArea" style=""><?php echo i18n('resultArea');?></span>
      </div>
    </div>
  </div> 
</div>
<?php 
function organizeButtons($nbButton=1) {
	global $displayWidthButton, $cptButton,$showAttachment,$extendedZone, $obj;
	$buttonWidth=34;
	$cptButton+=$nbButton;
	$requiredWidth=$cptButton*$buttonWidth;
	if ($showAttachment and $obj->id) {
		$requiredWidth+=44;
	}
	if ( ($requiredWidth>($displayWidthButton/3) and $displayWidthButton<1000)
	or (isNewGui() and $cptButton>3) ) {
		if (! $extendedZone) {
			$extendedZone=true;
			echo '<div dojoType="dijit.form.Button" showlabel="false" title="'. i18n('extraButtonsBar'). '" '
					.' iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton"'
							.' id="extraButtonsDetail" onClick="showExtraButtons(\'extraButtonsDetail\')" '
									.'></div>';
			echo '<div class="statusBar" id="extraButtonsDetailDiv" style="display:none;position:absolute;'.((isNewGui())?'width:34px;':'width:36px;').'">';
		} else {
			echo '<div></div>';
		}
	}

}

function organizeButtonsEnd() {
	global $displayWidth, $cptButton,$showAttachment,$extendedZone;
	if ($extendedZone) {
		echo '</div>';
	}
}
?>

