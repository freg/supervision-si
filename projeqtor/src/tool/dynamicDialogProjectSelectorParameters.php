<?php 
use PhpOffice\PhpPresentation\Shape\RichText\Paragraph;
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
$showIdle=(sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1)?1:0;
$showHandlelProject=Parameter::getUserParameter('projectSelectorShowHandlelProject');
$limitProjectLevel=Parameter::getUserParameter('projectSelectorLimitProjectLevel');
$displayMode="standard";
// if (sessionValueExists('projectSelectorDisplayMode')) {
//   $displayMode=getSessionValue('projectSelectorDisplayMode');
// }
$favoriteProject = new FavoriteProjectList();
$favoriteProjectList = $favoriteProject->getSqlElementsFromCriteria(array('idUser'=>$user->id),null,null,'name ASC');
$favoriteProjFlatList = implode(',', SqlList::getListWithCrit('FavoriteProjectList', array('idUser'=>$user->id), 'id'));
$favoriteProjectArray = pq_trim(Parameter::getUserParameter('favoriteProjectsArray'));
$isFavoriteListSelected = 0;
$idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList'));
$favoriteListName = '';
if(pq_trim($idFavoriteProjectList) != ''){
  $favoriteListName = SqlList::getNameFromId('FavoriteProjectList', $idFavoriteProjectList);
  $isFavoriteListSelected=1;
}else if(sessionValueExists("favoriteProjectListName")){
  $favoriteListName=getSessionValue("favoriteProjectListName");
}
$noName = RequestHandler::getBoolean('noName');
if($noName)$favoriteListName='';

$allvisibility=0;
if (securityGetAccessRight('menuProject', 'read')=='ALL') { // If can see ALL projects, can show the "show idle" switch as visibility noe define from (possibly closed) allocation
  $allvisibility=1;
}
$favoriteEditDisabled='';
if($displayMode=="select"){
  $favoriteEditDisabled='display:none';
}
$lastTab = Parameter::getUserParameter('projectSelectorTab');
if(!pq_trim($lastTab) or $lastTab=="favoritesProjectTab"){
  $lastTab = 'selectorFormatTab';
}
?>
<div id="projectSelectorTabContainer" data-dojo-type="dijit/layout/TabContainer" style="width: 630px;Height:236px" doLayout="false">
  <div id="selectorFormatTab" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('SelectorFormat');?>" data-dojo-props="<?php echo ($lastTab == 'selectorFormatTab')?'selected:true':'';?>">
    <script type="dojo/connect" event="onShow" args="evt">
      dijit.byId('projectSelectorTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
        saveDataToSession('projectSelectorTab', newValue.id,true);
      });
    </script> 
    <table style="width:100%">
      <tr><td></td><td>&nbsp;</td></tr>
      <tr>
        <td style="text-align: right;width:250px;white-space:nowrap;">
    	    <?php echo i18n("showHandlelProject");?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;
    	  </td>
    	  <td style="text-align: left; vertical-align: middle;width:280px;white-space:nowrap" title="<?php echo i18n('showHandlelProject');?>">
    	     <div title="<?php echo i18n('showHandlelProject');?>" dojoType="dijit.form.CheckBox" type="checkbox"
             <?php if ($showHandlelProject) echo ' checked ';?>">
    	       <script type="dojo/method" event="onChange" >
           var callBack = function(){
             refreshProjectSelectorList();
             if (dojo.byId('objectClass') ) {
               refreshGrid(true);
             }
           }
           saveDataToSession('projectSelectorShowHandlelProject', ((this.checked)?1:0),true,callBack);
           dijit.byId('dialogProjectSelectorParameters').hide();
         </script>
    	     </div>
    	     <?php echo i18n('helpHandledProject');?>
    	  </td>
      </tr>
      <tr>
        <td style="text-align: right;width:250px;white-space:nowrap;">
    	    <?php echo i18n("limitProjectLevel");?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;
        </td>
        <td style="text-align: left; vertical-align: middle;width:280px;white-space:nowrap" title="<?php echo i18n('limitProjectLevel');?>">
        	  <div style="width:40px; text-align: center; color: #000000;" 
              dojoType="dijit.form.NumberSpinner" 
              constraints="{min:1,max:9,places:0,pattern:'###0'}"
              intermediateChanges="true"
              maxlength="4"
              value="<?php echo ($limitProjectLevel!='' and $limitProjectLevel!='0' and $limitProjectLevel!='10')?$limitProjectLevel:'';?>" smallDelta="1"
              id="limitProjectLevel" name="limitProjectLevel" >
            </div>
            <button class="limitProjectLevelValid" dojoType="dijit.form.Button" >
                <?php echo i18n("buttonValid");?>
              <script type="dojo/method" event="onClick">
            if(dojo.byId('limitProjectLevel').value==0 || dojo.byId('limitProjectLevel').value==10 )dojo.byId('limitProjectLevel').value=null;
             var callBack = function(){
               refreshProjectSelectorList();
               if (dojo.byId('objectClass') ) {
                 refreshGrid(true);
               }
             }
             var lvl=(dojo.byId('limitProjectLevel').value>=1)?"("+dojo.byId('limitProjectLevel').value+")&nbsp;&nbsp":"";
             if(!dojo.byId('limitProjectLevel').value || dojo.byId('limitProjectLevel').value=="" || dojo.byId('limitProjectLevel').value==undefined){
               dojo.byId('toolbar_projectSelector').parentNode.style.left="130px";
             }else{
               if(dojo.byId('toolbar_projectSelector').parentNode.style.left =="130px")dojo.byId('toolbar_projectSelector').parentNode.style.left="160px";
             }
             dojo.byId('limitProjectLevelDiv').innerHTML=lvl;
             
             saveDataToSession('projectSelectorLimitProjectLevel',dojo.byId('limitProjectLevel').value,true,callBack);
             dijit.byId('dialogProjectSelectorParameters').hide();
           </script>
            </button>
            <button class="limitProjectLevelReset" dojoType="dijit.form.Button" >
                <?php echo i18n("buttonReset");?>
              <script type="dojo/method" event="onClick">
            dojo.byId('limitProjectLevel').value=null;
             var callBack = function(){
               refreshProjectSelectorList();
               if (dojo.byId('objectClass') ) {
                 refreshGrid(true);
               }
             }
             var lvl="";
             dojo.byId('toolbar_projectSelector').parentNode.style.left="130px";
             dojo.byId('limitProjectLevelDiv').innerHTML=lvl;
             saveDataToSession('projectSelectorLimitProjectLevel',dojo.byId('limitProjectLevel').value,true,callBack);
             dijit.byId('dialogProjectSelectorParameters').hide();
           </script>
            </button>
        </td>
      </tr>
      <tr><td></td><td>&nbsp;</td></tr>
      <tr style="display:none;">
        <td style="text-align: right;width:250px;white-space:nowrap;white-space:nowrap">
          <?php echo i18n("projectListDisplayMode");?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;
        </td>
        <td style="text-align: left; vertical-align: middle;width:250px; word-wrap: none;white-space:nowrap">
          <table><tr><td>
    	    <input type="radio" data-dojo-type="dijit/form/RadioButton" name="displayModeCkeckbox"
    	     <?php echo ($displayMode=='standard')?'checked':'';?> 
            id="displayModeCkeckboxStandard" value="standard" onClick="changeProjectSelectorType('standard');" />
            </td><td>
            <label class="display" style="background-color: var(--color-background);<?php echo (isNewGui())?'position:relative;left:6px;top:-2px':'';?>" for="displayModeCkeckboxStandard"><?php echo i18n("displayModeStandard")?></label>
            </td></tr><tr><td>
    	    <input type="radio" data-dojo-type="dijit/form/RadioButton" name="displayModeCkeckbox" 
    	     <?php echo ($displayMode=='select')?'checked':'';?> 
            id="displayModeCkeckboxSelect" value="select" onClick="changeProjectSelectorType('select');" />
            </td><td>
            <label class="display" style="background-color: var(--color-background);<?php echo (isNewGui())?'position:relative;left:6px;top:-2px':'';?>" for="displayModeCkeckboxSelect"><?php echo i18n("displayModeSelect")?></label>
            </td></tr><tr><td>
    	    <input type="radio" data-dojo-type="dijit/form/RadioButton" name="displayModeCkeckbox" 
    	     <?php echo ($displayMode=='search')?'checked':'';?> 
            id="displayModeCkeckboxSearch" value="select" onClick="changeProjectSelectorType('search');" />
            </td><td>
            <label class="display" style="background-color: var(--color-background);<?php echo (isNewGui())?'position:relative;left:6px;top:-2px':'';?>" for="displayModeCkeckboxSearch"><?php echo i18n("displayModeSearch")?></label>
            </td></tr></table>
        </td>
      </tr>
      <tr><td></td><td>&nbsp;</td></tr>
    </table>  
  </div>
  <?php if(1==0){?>
  <div id="favoritesProjectTab" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('Favorite');?>" data-dojo-props="<?php echo ($lastTab == 'favoritesProjectTab')?'selected:true':'';?>"> 
    <script type="dojo/connect" event="onShow" args="evt">
      dijit.byId('projectSelectorTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
        saveDataToSession('projectSelectorTab', newValue.id,true);
      });
    </script> 
    <form dojoType="dijit.form.Form" id="favoriteProjectListForm" name="favoriteProjectListForm" onSubmit="return false;">
      <input type="hidden" id="favoriteProjectName" name="favoriteProjectName" />
      <input type="hidden" id="isFavoriteListSelected" name="isFavoriteListSelected" value="<?php echo $isFavoriteListSelected;?>"/>
      <table width="95%" align="center">
        <tr><td></td><td>&nbsp;</td></tr>
        <tr id="favoriteProjectEditRow" style="<?php echo $favoriteEditDisabled; ?>">
          <td style="text-align: right;white-space:nowrap;white-space:nowrap">
            <?php echo i18n("colFavoriteName");?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;
          </td>
          <td style="text-align: left; vertical-align: middle;word-wrap: none;white-space:nowrap">
            <table><tr>
              <td>
                <div type="text" dojoType="dijit.form.ValidationTextBox" name="favoriteProjectListName" id="favoriteProjectListName"
                  style="width:400px;" trim="true" maxlength="100" class="input" value="<?php echo $favoriteListName;?>"></div>
              </td>
              <td>
                <button title="<?php echo i18n('saveFavoriteProjectList');?>" dojoType="dijit.form.Button"
                    id="dialogFavoriteProjectListSave" name="dialogFavoriteProjectListSave" class="resetMargin roundedButton notButton" style="height:24px;width:32px;margin-top:-5px;"
                    iconClass="dijitButtonIcon dijitButtonIconSave imageColorNewGui" showLabel="false">
                  <script type="dojo/connect" event="onClick" args="evt">saveFavoriteProjectList();</script>
                </button>
              </td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td colspan="2">
          <button title="<?php echo i18n('transformFavoriteProjectList');?>" dojoType="dijit.form.Button"
              id="dialogFavoriteProjectListTransform" name="dialogFavoriteProjectListTransform" class="" style="width:400px; margin-bottom: 10px; margin-left:100px;">
              <?php echo i18n("transformFavoriteProjectList");?>
            <script type="dojo/connect" event="onClick" args="evt">
              changedSelectedProjectToFavorite();
            </script>
          </button>
          </td>
        </tr>
        <tr>
          <td colspan="2">
            <table width="100%" align="center">
              <tr style="height:22px;">
                <td colspan="2" class="filterHeader"><?php echo i18n('storedFavoriteProjectList');?></td>
              </tr>
                  <tr>
                    <td colspan="2">
                      <div id="listStoredFavoriteProjectList" name="listStoredFavoriteProjectList" dojoType="dijit.layout.ContentPane" region="center" style="width:100%;height:100px;overflow-y: auto;">
                      <input type="hidden" id="idSelectedFavoriteProject" name="idSelectedFavoriteProject" value="<?php echo $idFavoriteProjectList;?>" />
                      <table width="100%" id="dndListFavoriteSelector" jsId="dndListFavoriteSelector" dojotype="dojo.dnd.Source" withhandles="true" data-dojo-props="accept: ['tableauFavoriteList']">
                        <?php if(count($favoriteProjectList)>0){?>
                        <tr style="height:22px;">
                          <td colspan="3" style="cursor:pointer;<?php echo (!isNewGui())?'font-size:8pt;':'';?>font-style:italic;padding:5px;height: 22px;"
                            class="filterData ganttTaskrow" onClick="selectFavoriteProjectList('<?php echo $favoriteProjectArray;?>', '');" title="<?php echo i18n("resetFavoriteList"); ?>"><?php echo i18n('noFavorite');?></td>
                        </tr>
                          <?php foreach ($favoriteProjectList as $favoriteProject){
                            $favoriteProjectItemList = SqlList::getListWithCrit('FavoriteProjectItem', array('idFavoriteProjectList'=>$favoriteProject->id), 'idProject');
                            $favoriteProjectItemList = implode(',', $favoriteProjectItemList);
                            $selectedListClass = ($favoriteProject->id == $idFavoriteProjectList)?'dojoDndItemAnchor':'';
                            $selectedBackgroundColor = ($favoriteProject->id == $idFavoriteProjectList)?'favoriteProjectListSelected':'';
                          ?>
                          <tr class="dojoDndItem <?php echo $selectedListClass;?> ganttTaskrow" dndType="tableauFavoriteList" id="favoriteList<?php echo $favoriteProject->id;?>">
                            <td style="cursor:pointer;<?php echo (!isNewGui())?'font-size:8pt;':'';?>font-style:italic;padding:5px;height: 22px;"
                              class="filterData <?php echo $selectedBackgroundColor;?>" onClick="selectFavoriteProjectList('<?php echo $favoriteProjectItemList;?>', '<?php echo $favoriteProject->id;?>');" title="<?php echo i18n("selectStoredFavorite"); ?>">
                               <!-- <span class="dojoDndHandle handleCursor"><img style="width:<?php //echo (isNewGui())?'10px;float:left':'6px;';?>" src="css/images/iconDrag.gif" />&nbsp;&nbsp;</span> -->
                               <span id="favoriteProjectName_<?php echo $favoriteProject->id;?>" style="position:relative;top:2px;margin:3px"><?php echo htmlEncode($favoriteProject->name);?></span></td>
                            </td>
                            <td class="filterData dndHidden" width="16px" align="center" style="height: 22px;">
                              <a onClick="selectFavoriteProjectList('<?php echo $favoriteProjectItemList;?>', '<?php echo $favoriteProject->id;?>', true);" title="<?php echo i18n('editStoredFavorite');?>">
                                <?php echo formatSmallButton('Edit');?>
                              </a>
                            </td>
                            <td class="filterData dndHidden" width="16px" align="center" style="height: 22px;">
                              <a onClick="removeFavoriteProjectList('<?php echo $favoriteProjFlatList;?>', '<?php echo htmlEncode($favoriteProject->id);?>')" title="<?php echo i18n('removeStoredFavorite');?>">
                                <?php echo formatSmallButton('Remove');?>
                              </a>
                            </td>
                          </tr>
                        <?php }?>
                      <?php }else{?>
                        <tr style="height:22px;">
                          <td colspan="3" style="cursor:pointer;<?php echo (!isNewGui())?'font-size:8pt;':'';?>font-style:italic;padding:5px;height: 22px;"
                            class="filterData ganttTaskrow" onClick="selectFavoriteProjectList('<?php echo $favoriteProjectArray;?>','');" title="<?php echo i18n("resetFavoriteList"); ?>"><?php echo i18n('noFavorite');?></td>
                        </tr>
                      <?php }?>  
                      </table>
                      </div>
                    </td>
                  </tr>
            </table>
          </td>
        </tr>
      </table>
    </form>
  </div>
  <?php }?>
  <div id="othersTab" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('menuOther');?>" data-dojo-props="<?php echo ($lastTab == 'othersTab')?'selected:true':'';?>"> 
    <script type="dojo/connect" event="onShow" args="evt">
      dijit.byId('projectSelectorTabContainer').watch("selectedChildWidget", function(name, oldValue, newValue) {
        saveDataToSession('projectSelectorTab', newValue.id,true);
      });
    </script> 
    <table style="width:100%">
      <tr><td></td><td>&nbsp;</td></tr>
      <tr>
        <td style="text-align: right;width:250px;white-space:nowrap;">
    	    <?php echo i18n("labelShowIdle");?>&nbsp;<?php echo (isNewGui())?'':':';?>&nbsp;
    	  </td>
    	  <td style="text-align: left; vertical-align: middle;width:250px;white-space:nowrap;" title="<?php echo i18n('helpEnterArchiveMode');?>">
    	     <div title="<?php echo i18n('showIdleElements');?>" dojoType="dijit.form.CheckBox" type="checkbox"
             <?php if ($showIdle) echo ' checked ';?>">
    	       <script type="dojo/method" event="onChange" >
           var callBack = function(){
             var idle =<?php echo json_encode($showIdle); ?>;
             var allVisibility=<?php echo json_encode($allvisibility);?>
             //loadContent("../view/menuProjectSelector.php", 'projectSelectorDiv');
             refreshProjectSelectorList();
             if (dojo.byId('objectClass') ) {
               if(dojo.byId('objectClass').value=='Project'){
                if(!idle){
                  dijit.byId('listShowIdleSwitch').set('value','on');
                  if(allVisibility!=1){
                    dijit.byId('listShowIdleSwitch').set('style','display: inline-block; left: -7px;');
                    dojo.byId('labelShowIdel').style.display="table-row";
                  }
                }else{
                  dijit.byId('listShowIdleSwitch').set('value','off');
                  if(allVisibility!=1){
                    dijit.byId('listShowIdleSwitch').set('style','display: none; left: -7px;');
                    dijit.byId('listShowIdleSwitch').domNode.style.display="none";
                    dojo.byId('labelShowIdel').style.display="none";
                  }
                }
               }
               refreshGrid(true);
             }
           }
           saveDataToSession('projectSelectorShowIdle', ((this.checked)?1:0),false,callBack);
           dijit.byId('dialogProjectSelectorParameters').hide();
           <?php if(isNewGui()){?>
              dojo.byId('archiveOn').style.display=(this.checked)?'':'none';
              dojo.byId('archiveOnSeparator').style.display=(this.checked)?'':'none';
              dojo.byId('archiveOnDiv').style.display=(this.checked)?'':'none';
           <?php } ?>
           if (typeof forcePlanningShowClosedFromArchiveMode == 'function') {
             forcePlanningShowClosedFromArchiveMode(this.checked);
           }
         </script>
    	     </div>
    	     <?php echo i18n('enterArchiveMode');?>
    	  </td>
      </tr>
      <tr style="height:100px"><td></td><td>&nbsp;</td></tr>
    </table>
  </div>
</div>
  <table style="width:100%">
  <tr style="height:20px;border-bottom:2px solid #F0F0F0;"><td></td><td>&nbsp;</td></tr>
  <tr style="height:10px;"><td></td><td>&nbsp;</td></tr>
</table>
<table style="width:100%">
	<tr style="height:10px;">
	  <td align="center">
	   <button class="mediumTextButton" dojoType="dijit.form.Button" onclick="dijit.byId('dialogProjectSelectorParameters').hide();">
	     <?php echo i18n("close");?>
	   </button>&nbsp;
     <button class="dynamicTextButton" dojoType="dijit.form.Button"
     onclick="refreshProjectSelectorList();">
       <?php echo i18n("buttonRefreshList");?>
     </button>
	  </td>
    <td align="center">
    </td>
	</tr>
	<tr>
	<td colspan="2" style="text-align:center;color:#a0a0a0;"><br/><?php echo i18n("helpRefreshList");?></td>
	</tr>
</table>
