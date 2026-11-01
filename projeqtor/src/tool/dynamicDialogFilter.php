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

$idFilterFromFavoriteProject = RequestHandler::getValue('idFilterFromFavoriteProject');
$keyDownEventScript=NumberFormatter52::getKeyDownEvent();
?>
<table style="">
    <tr>
      <td style=""> 
               
        <form id='dialogFilterForm' name='dialogFilterForm' onSubmit="return false;">
         <input type="hidden" id="filterObjectClass" name="filterObjectClass" />
         <input type="hidden" id="filterClauseId" name="filterClauseId" />
         <input type="hidden" id="filterDataType" name="filterDataType" />         
         <input type="hidden" id="filterName" name="filterName" />
         <input type="hidden" id="filterLayout" name="filterLayout" />
         <input type="hidden" id="filterEditId" name="filterEditId" />
         <input type="hidden" id="filterInsertPosition" name="filterInsertPosition" />
         <input type="hidden" id="idFilterFromFavoriteProject" name="idFilterFromFavoriteProject" value="<?php echo $idFilterFromFavoriteProject; ?>" />
         <input type="hidden" id="isGroup" name="isGroup" value="0" />
         <input type="hidden" id="indentLevel" name="indentLevel" value="0" />
         
         
         <table width="100%" style="">
           <tr>
            <td colspan="5" class="titleFilterCriteria"><?php echo i18n("addFilterClauseTitle");?></td>
           </tr>
           <tr class='' style='border-top:solid 1px;color:var(--color-medium);'></tr>
           <tr class='' style='height: 8px;'></tr>
           <tr style="vertical-align: top;height:auto;">
             <?php //ADD qCazelles - Dynamic filter - Ticket #78?>
           	 <td style="width:<?php echo (isNewGui())?'67':'80';?>px;" title="<?php echo i18n('helpOrInput');?>" >
           	  <div id="filterLogicalOperator" style="width: <?php echo (isNewGui())?'65':'80';?>px;display: none; overflow-x:hidden; overflow-y:auto">
           	 	<select dojoType="dijit.form.FilteringSelect"
           	 		id="orOperator" name="orOperator"
           	 		class="input" style="width: <?php echo (isNewGui())?'45px;position:relative;left:5px;':'70px;';?>" value="0">
           	 		<?php echo autoOpenFilteringSelect();?> 
           	 		<script type="dojo/method" event="onChange">
           	 		  updatePendingFilterLogicalOperator();
           	 		</script>
           	 		<!-- BOITE DE DIALOGUE A METTRE SUR LE OR -->						<!-- TODO TODO TODO -->
           	 		<option value="0" selected><?php echo i18n('AND');?></option> <!-- TRANSLATION qCazelles -->
           	 		<option value="1"><?php echo i18n('OR');?></option>			  <!-- TRANSLATION qCazelles -->
           	 	</select>
           	  </div>
           	 </td>

               <td style="padding: 0px 5px 0px 0px">
                 <div id="filterGroupButtons">
                   <button class="filterGroupButton" title="<?php echo i18n('openGroupFilter') ?>" dojoType="dijit.form.Button" id="dialogFilterOpenGroup" name="dialogFilterOpenGroup" onClick="changeFilterGroup('open');">
                     <?php echo i18n("openGroup");?>
                   </button>
                   <button class="filterGroupButton" title="<?php echo i18n('closeGroupFilter') ?>" dojoType="dijit.form.Button" id="dialogFilterCloseGroup" name="dialogFilterCloseGroup" onClick="changeFilterGroup('close');">
                     <?php echo i18n("closeGroup");?>
                   </button>
                 </div>
               </td>

             <?php //END ADD qCazelles - Dynamic filter - Ticket #78?>
             <td style="width: <?php echo (isNewGui())?'197':'210';?>px;" >
               <div dojoType="dojo.data.ItemFileReadStore" jsId="attributeStore" url="../tool/jsonList.php?listType=empty<?php echo Security::addTokenIndexToUrl(); ?>" searchAttr="name" >
               </div>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="idFilterAttribute" name="idFilterAttribute" 
                missingMessage="<?php echo i18n('attributeNotSelected');?>"
                class="input" value="" style="width: <?php echo (isNewGui())?'180':'200';?>px;" store="attributeStore">
                  <script type="dojo/method" event="onChange" >
                    filterSelectAtribute(this.value);
                  </script>              
               </select>
             </td>
             <td style="width: <?php echo (isNewGui())?'117':'110';?>px;">
               <div dojoType="dojo.data.ItemFileReadStore" jsId="operatorStore" url="../tool/jsonList.php?listType=empty<?php echo Security::addTokenIndexToUrl(); ?>" searchAttr="name" >
               </div>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="idFilterOperator" name="idFilterOperator" 
                missingMessage="<?php echo i18n('valueNotSelected');?>"
                class="input" value="" style="width: 100px;" store="operatorStore">
                  <script type="dojo/method" event="onChange" >
                    filterSelectOperator(this.value);
                  </script>        
               </select>
             </td>
             <td style="width:<?php echo (isNewGui())?'370':'320';?>px;position:relative;">
             <?php //ADD qCazelles - Dynamic filter - Ticket #78?>
               <div id="filterDynamicParameterPane" dojoType="dijit.layout.ContentPane" region="top" 
                style="<?php if (isNewGui()) echo 'position:absolute;left:200px;top:9px;width:160px;overflow:hidden;z-index:20;'?>">
                <?php if (isNewGui()) {?>
                  <div  id="filterDynamicParameterSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" 
                    title="<?php echo i18n("dynamicValue");?>"
                    value="off" 
                    leftLabel="" rightLabel="" style="width:10px;position:relative; left:0px;top:2px;z-index:99;" >
  		              <script type="dojo/method" event="onStateChanged" >
                        lastDynamicSwitchManualChange = new Date().getTime();
  		                dijit.byId("filterDynamicParameter").set("checked",(this.value=="on")?true:false);

                      if (this.value=="on") {
                        dojo.byId('filterCompareParameterPane').style.display='none';
                        dijit.byId('filterValueList').set("value", []); 
                      } else { 
                        var dataTpe=dojo.byId('filterDataType').value;
                        if (dataTpe=="date" || dataType=="decimal") {
                           dojo.byId('filterCompareParameterPane').style.display='block';
                        }
                      }
  		              </script>
  		             </div>
  		          <?php }?>
               	<input type="checkbox" id="filterDynamicParameter" name="filterDynamicParameter" value=""
               	 	dojoType="dijit.form.CheckBox" style="<?php if (isNewGui()) echo 'display:none;'?>"/>
               	 	<label class="checkLabel" for="filterDynamicParameter" 
               	 	style="<?php if (isNewGui()) echo 'font-size:90%;text-align:left;float:none;position:absolute;left:37px;top:1px;text-overflow:ellipsis'?>"><?php echo i18n('dynamicValue');?></label>
               	</div>
               <?php //END ADD qCazelles - Dynamic filter - Ticket #78?>
               
               <?php // #6012?>
               <div id="filterCompareParameterPane" dojoType="dijit.layout.ContentPane" region="top" 
                style="<?php if (isNewGui()) echo 'position:absolute;left:200px;top:30px;width:200px;overflow:hidden;z-index:20;'?>">
                <?php if (isNewGui()) {?>
                  <div  id="filterCompareParameterSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" 
                    title="<?php echo i18n("CompareValue");?>"
                    value="off" 
                    leftLabel="" rightLabel="" style="width:10px;position:relative; left:0px;top:2px;z-index:99;" >
  		              <script type="dojo/method" event="onStateChanged" >
  		                dijit.byId("filterCompareParameter").set("checked",(this.value=="on")?true:false);
                      if (this.value=="on")  {
                         dojo.byId('filterDynamicParameterPane').style.display='none';
                         dojo.byId('filterCompareParameterPane').style.top="9px";
                      } else { 
                         dojo.byId('filterDynamicParameterPane').style.display='block';
                         dojo.byId('filterCompareParameterPane').style.top="30px";
                         filterSelectOperator(dijit.byId('idFilterOperator').get('value'));
                      }
                      filterActiveCompareField();
  		              </script>
  		          </div>
  		          <?php }?>
               	  <input type="checkbox" id="filterCompareParameter" name="filterCompareParameter" value=""
               	  dojoType="dijit.form.CheckBox" style="<?php if (isNewGui()) echo 'display:none;'?>"/>
               	  <label class="checkLabel" for="filterCompareParameter" 
               	  style="<?php if (isNewGui()) echo 'font-size:90%;text-align:left;float:none;position:absolute;left:37px;top:1px;text-overflow:hidden; width:200px'?>"><?php echo i18n('CompareValue');?></label>
               </div>
               <?php // #6012?>
               
               <input id="filterValue" name="filterValue" value=""  
                 dojoType="dijit.form.TextBox" 
                 style="width:<?php echo (isNewGui())?'180':'320';?>px" />
               <select id="filterValueList" name="filterValueList[]" value=""  onChange="var dw = dijit.byId('filterDynamicParameterSwitch'); var now = new Date().getTime(); if (dw && dw.get('value') === 'on' && now - lastDynamicSwitchManualChange > 300) {dw.set('value', 'off');}"
                 dojoType="dijit.form.MultiSelect" multiple
                 style="<?php echo (isNewGui())?'width:350px;font-size:10pt;padding:30px 0px 0px 0px;color:#555555;':'width:325px;';?>height:150px;" size="10" class="selectList">
               </select>
               <?php if (isNewGui()) {?>
                 <div id="filterValueListHideTop" style="position:absolute;top:1px;left:1px;width:330px;height:25px;background:#ffffff;z-index:15;display:none" ></div>
               <?php }?>
               <?php if (isNewGui()) {?>
               <div  id="filterValueCheckboxSwitch" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="off" 
                 leftLabel="" rightLabel="" style="width:10px;position:relative; top:0px;left:5px;z-index:99;display:none;" >
  		           <script type="dojo/method" event="onStateChanged" >
  		             dijit.byId("filterValueCheckbox").set("checked",(this.value=="on")?true:false);
  		           </script>
  		         </div>
               <?php }?>
               <input type="checkbox" id="filterValueCheckbox" name="filterValueCheckbox" value=""  
                 dojoType="dijit.form.CheckBox" style="padding-top:7px;<?php echo (isNewGui())?'margin-left:5px;display:none;':'';?>";/> 
               <input id="filterValueDate" name="filterValueDate" value=""  
                 dojoType="dijit.form.DateTextBox" 
                 constraints="{datePattern:browserLocaleDateFormatJs}"
                 style="width:100px" />
               <select id="filterSortValueList" name="filterSortValueList" value="asc"  
                 dojoType="dijit.form.FilteringSelect"
                 <?php echo autoOpenFilteringSelect();?>
                 missingMessage="<?php echo i18n('valueNotSelected');?>" 
                 style="width:320px" class="input">
                  <option value="asc" SELECTED><?php echo i18n('sortAsc');?></option>
                  <option value="desc"><?php echo i18n('sortDesc');?></option>
               </select> 
               
               <?php // #6012 ?>
               <div dojoType="dojo.data.ItemFileReadStore" jsId="attributeStoreCompare" url="../tool/jsonList.php?listType=empty<?php echo Security::addTokenIndexToUrl(); ?>" searchAttr="name" >
               </div>
               <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="FilterCompareAttribute" name="FilterCompareAttribute" 
                missingMessage="<?php echo i18n('attributeNotSelected');?>"
                class="input" value="test" style="width: <?php echo (isNewGui())?'180':'200';?>px;" store="attributeStoreCompare">
                  <script type="dojo/method" event="onChange" >
                  </script>              
               </select>
               <?php // #6012 ?>
               
               <div id="filterCompareValueInput" style="margin-left:-5px;">
  						   <div style="display: flex; align-items: center; gap: 7px;">
    						   <select dojoType="dijit.form.FilteringSelect" id="operatorCompare" name="operatorCompare"
             	 				class="input" style="width: <?php echo (isNewGui())?'45px;position:relative;left:5px;':'70px;';?>" value="plus">
             	 				<?php echo autoOpenFilteringSelect();?> 
             	 					<option value="plus" selected>+</option>
             	 					<option value="minus">-</option>
             	 					<script type="dojo/method" event="onChange" args="val">
                          handleOperatorChange(val);
                        </script>
             	 		 </select>
                   <div data-dojo-type="dijit.form.NumberTextBox" id="filterCompareValue" name="filterCompareValue" 
                   style="width:120px;font-size:12px;" placeholder="0" ><?php echo $keyDownEventScript; ?></div>
                   <span id="compareUnit" name="compareUnit" style="font-size:14px;color:#666;"><?php i18n('days')?></span>
                </div>
              </div>
              
            <div id="filterValueHatch" name="filterValueHatch" dojoType="dijit.form.Select" labelType="html" spanLabel="true" style="display:none;width:70px;">
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
               
             </td>
             <td style="position:relative;width:25px; text-align: center;vertical-align:<?php echo (isNewGui())?'top':'middle';?>;" align="center"> 
               <table>
                 <tr>
                   <td>
                     <a id="buttonSaveFieldEdition" src="css/images/smallButtonSave.png" style="display:none;padding:0 0 10px 8px;<?php echo (isNewGui())?'z-index:100;position:relative;right:6px;top:7px;':'margin-top:3px;';?>" onClick="addfilterClause(null,true);" title="<?php echo i18n('saveEditFilterClause');?>" >
                     <?php echo (isNewGui())?formatMediumButton('Save'):formatSmallButton('Save');?>
                     </a> 
                     <a src="css/images/smallButtonAdd.png" style="<?php echo (isNewGui())?'z-index:100;position:relative;right:6px;top:7px;padding-left:8px;':'margin-top:3px;';?>" onClick="addfilterClause();" title="<?php echo i18n('addFilterClause');?>">
                     <?php echo (isNewGui())?formatMediumButton('Add'):formatSmallButton('Add');?>
                     </a>

                   </td>
                  </tr>
                  <tr>
                    <td style="position: absolute;<?php echo (isNewGui())?'top:118px;left:-21px;':'margin-top:-60px;margin-left:-2px;';?>">
                      <button style="display:block;" id="showDetailInFilter" dojoType="dijit.form.Button" showlabel="false"
                              title="<?php echo i18n('showDetail')?>" class="resetMargin notButton notButtonRounded"
                              iconClass="iconSearch22 iconSearch iconSize22 imageColorNewGui">
                        <script type="dojo/connect" event="onClick" args="evt">
                        var objectName = dijit.byId('showDetailInFilter').get('value');
                        var paramRequestorLimitToContact='<?php echo Parameter::getGlobalParameter('requestorLimitToContact');?>';
                        if (! paramRequestorLimitToContact) paramRequestorLimitToContact='NO';
                        if( objectName ){
                          var objectClass=objectName[0].substr(2);
                          if (objectName[0].indexOf('__id')>=0) {
                            objectClass=objectName[0].substr(objectName[0].indexOf('__id')+4);
                          }
                          if (objectClass =='Contact' && paramRequestorLimitToContact!='YES') objectClass = 'Affectable';
                          if (objectClass=='TargetProductVersion' || objectClass=='OriginalProductVersion') objectClass='ProductVersion';
                          if (objectClass=='ResourceSelect') objectClass='ResourceAllNoMaterial';
                          dijit.byId('filterValueList').reset();
                          showDetail('filterValueList',0,objectClass,true);
                        }
                      </script>
                      </button>
                    </td>
                 </tr>
               </table> 
             </td>     
           </tr>        
         </table>
        </form>
        
        <div id='listFilterClauses' dojoType="dijit.layout.ContentPane" region="center" style="overflow-x: hidden; max-height:25vh; overflow-y:auto;padding-top: 17px; max-width:830px; "></div>
        
      </td>
    </tr>
    <?php if (isNewGui()) {?><tr><td><div style="height:6px"></div></td></tr><?php }?>
    <tr style="height:32px">
      <td style="padding-right: 8px;">
        <table style="width: 100%;">
          <tr>
            <td style="padding-right: 8px;">
                <div style="display: flex; gap: 10px;justify-content: flex-end;width: 100%;padding:13px 0px 2px 0px;">
                  <button class="mediumTextButton" style=" width: auto !important;" dojoType="dijit.form.Button" onclick="clearFilter();">
                    <?php echo i18n("reset");?>
                  </button>
                  <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="cancelFilter();">
                    <?php echo i18n("buttonCancel");?>
                  </button>
                  <?php if(!$idFilterFromFavoriteProject){?>
                  <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogFilterSubmit"
                    onclick="if (!validateFilterParentheses())return false;protectDblClick(this);selectFilter(true);validateLayoutListColumn((dojo.byId('divKanbanContainer'))?'kanban':null);return false;">
                    <?php echo i18n("buttonApply");?>
                  </button>
									<?php }?>
              </div>
            </td>
          </tr>
        </table>
        <div id='filterNameLayoutDiv' dojoType="dijit.layout.ContentPane" region="center" style="display:flex; justify-content: space-evenly; align-items:center;vertical-align:middle; font-size:100%; height:35px; margin:10px 6px; background-color:#f0f0f0; border-radius:10px; padding:5px;overflow:hidden; width:98%;"></div>
      </td>
    </tr>
  </table>
  
  <table style="">
    <?php if (isNewGui()) {?><tr><td><div style="height:6px"></div></td></tr><?php }?>
    <div style="display:flex; gap:10px; width:100%; height:auto;padding-top: 2px;">
      <div id="listStoredFilters" 
           dojoType="dijit.layout.ContentPane" 
           style="flex:1; min-width:360px;padding:5px;">
        <div style="height:250px;">loading...</div>
      </div>
      <div id="listSharedFilters" 
           dojoType="dijit.layout.ContentPane" 
           style="flex:1; min-width:360px; padding:5px;">
      </div>
    </div>
    
    <tr><td style="height: 4px;"></td></tr>
</table>
