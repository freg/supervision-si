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

include_once("../tool/projeqtor.php");
$proj='*';
if(sessionValueExists('project')){
  $proj=getSessionValue('project');
} else {
  setSessionValue('project', "*");
}
$prj=new Project();
$prj->id='*';
//$cpt=$prj->countMenuProjectsList();
$limitToActiveProjects=true;
$critFld=null;
$critVal=null;
if (sessionValueExists('projectSelectorShowIdle') and getSessionValue('projectSelectorShowIdle')==1) {
  $limitToActiveProjects=false;
}
if (sessionValueExists('projectSelectorShowHandlelProject') and getSessionValue('projectSelectorShowHandlelProject')==1) {
	$critFld='handled';
	$critVal=1;
}
// Rows are served by the json endpoint included below. Only their count is
// needed here, to size the popup.
$selectorForSession=Project::getSelectorModelForSession();
$cpt=count(Project::buildSelectorPayload($selectorForSession['model'], $selectorForSession['limitProjectLevel'])['rows']);
$displayMode="standard";
// $paramDisplayMode=Parameter::getUserParameter('projectSelectorDisplayMode');
// if ($paramDisplayMode) {
//   setSessionValue('projectSelectorDisplayMode', $paramDisplayMode);
// }
// if (sessionValueExists('projectSelectorDisplayMode')) {
//   $displayMode=getSessionValue('projectSelectorDisplayMode');
// }
$nbProj=0;
$arrProj=pq_explode(',', $proj);
$first=null;
if ($proj=='*') {
  $nbProj=0;
} else {
  foreach ($arrProj as $idp) {
    if (pq_trim($idp)!='' and pq_trim($idp)!='*') {
      $nbProj++;
      if (! $first) $first=$idp;
    }
  }
}
if ($displayMode!='standard' and $nbProj>1) {
  $proj=$first;
  $nbProj=1;
  setSessionValue('project',$proj);
}
$idFavoriteProjectList = pq_trim(getSessionValue('idFavoriteProjectList'));
$editFavoriteProject = pq_trim(getSessionValue('editFavoriteProject'));
$favoriteProjectArray = pq_trim(Parameter::getUserParameter('favoriteProjectsArray'));
session_write_close();
?>
<?php if ($displayMode=='standard' or $idFavoriteProjectList) {?>
<span maxsize="160px" style="position: absolute; left:0px; top:px; height: 20px; width: 241px; color:#202020;" 
  dojoType="dijit.form.DropDownButton"
  id="selectedProject" jsId="selectedProject" name="selectedProject" showlabel="true" class="">
  <script type="dojo/connect" event="onBlur">
    validateProjectSelectionOnClose();
  </script>
  <script type="dojo/connect" event="onClick">
    if (!this._opened) validateProjectSelectionOnClose();
  </script>
  <span style="width:220px; text-align: left;">
    <div style="width:220px; overflow: hidden; text-align: left;" >
    <?php
    if ($nbProj==0) {
      if($idFavoriteProjectList != ''){
        echo '<i>'.i18n('favoriteProject').'</i>';
      }else{
        echo '<i>' . i18n('allProjects') . '</i>';
      }
    } else if($nbProj > 1){
    	echo '<i>'.i18n('selectedProject').'</i>';
    }else {
    	//$projObject=new Project($proj);
    	echo htmlEncode(SqlList::getNameFromId('Project', $proj));
    }
    ?>
    </div>
  </span>
  <span id="projectListTooltip" dojoType="dijit.TooltipDialog" class="white"
    onCancel="validateProjectSelectionOnClose();"
    <?php echo ($cpt>25)?'style="min-width:275px;max-width:900px;"':'style="min-width:275px;"';?>>
     <div id='saveFavoriteProjectResult' style='width:98%;z-index:9999;position: absolute;display:none'>
          <div id="saveFavoriteMessage" style="padding:15px 15px 15px 53px;" class="messageINVALID"></div>
          <div class="closeBoxIcon" style="right:14px;top:1px;" onClick="dojo.byId('saveFavoriteProjectResult').style.display='none';">&nbsp;</div>
     </div>
     <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 15px; padding-right: 4px;">
        <div style="position: relative; flex: 1 1 auto; min-width: 0;">
          <input type="text" id="projectFilterInput" placeholder="<?php echo ucfirst(i18n('searchProject'));?>" onkeydown="validateSearchProject()" onkeyup="filterProjects()" style="width: 100%; box-sizing: border-box; border: 1px solid var(--color-medium); border-radius: 5px; padding: 5px;" />
          <div class="iconCancel iconSize16 imageColorNewGui" onclick="clearSearchInputSelectorProject();" id="clearSearchSelectorProject" style="position: absolute; right: 8px; top: 50%; margin-top: -8px; cursor: pointer; display:none;"></div>
        </div>
        <a id="projectSelectorComboButtonInPopup" title="<?php echo i18n('searchProject');?>"
           style="flex: 0 0 auto; cursor: pointer; line-height: 0;"
           onclick="showDetail('projectSelectorFiletering', false , 'Project',true,null,true);"><?php echo formatSmallButton('Search', true); ?></a>
     </div>
     <?php $heightSelectorList=(sessionValueExists('screenHeight'))?round(intval(getSessionValue('screenHeight'))*0.80):500; ?>
    <div style="max-height: <?php echo $heightSelectorList;?>px; overflow: hidden">
    <input type="hidden" id="projectSelectorMaxHeight" name="projectSelectorMaxHeight" value="<?php echo $heightSelectorList;?>" />
    <?php
      echo Project::drawSelectorHeader('selectedProject');
    ?>
      <div id="pqSelectorViewport"></div>
      </div>
    </div>
    <div dojoType="dijit.layout.ContentPane" id="projectSelectorJsonData" jsId="projectSelectorJsonData" style="display:none"><?php include '../tool/jsonProjectSelector.php'; ?></div>
    <script type="text/javascript">
      pqSelectorInit();
    </script>
    </div>
  </span>
</span>
    <div id="multiProjectSelector"  dojoType="dijit.form.TextBox" style="display:none" value="">
     <script type="dojo/connect" event="onChange" args="evt">
       setSelectedProject(this.value, '<i>'+i18n('selectedProject')+'</i>', 'selectedProject',true);
     </script>
   </div>
   <div id="projectSelectorFiletering" style="display:none" dojoType="dijit.form.FilteringSelect" >
     <script type="dojo/connect" event="onChange" args="evt">
       setSelectedProject(this.value, this.displayedValue, 'selectedProject',true);
     </script>
     <option value=""></option>
     <?php htmlDrawOptionForReference("idProject", null, null, false, $critFld, $critVal, $limitToActiveProjects,false,false,true,false, false);?>
   </div>
   <input type="hidden" id="projectSelectorMode" value="Standard" />
<?php } else if ($displayMode=='select') {?>
<select dojoType="dijit.form.FilteringSelect" class="input" 
   style="position: absolute; left:4px; top:<?php echo (isNewGui())?'-3':'1';?>px; width: 241px;height:<?php echo (isNewGui())?'20':'22';?>px;" 
   <?php echo autoOpenFilteringSelect();?>
   name="projectSelectorFiletering" id="projectSelectorFiletering" >
   <script type="dojo/connect" event="onChange" args="evt">
    if (this.isValid()) {
      setSelectedProject(this.value, this.displayedValue, null,true);
    }
  </script>
   <option value="*"><?php echo i18n("allProjects");?></option>
   <?php htmlDrawOptionForReference("idProject", $proj, null, true,$critFld, $critVal, $limitToActiveProjects,false,false,true,false,true);?>
</select>
<input type="hidden" id="projectSelectorMode" value="Filtering" />
 <?php if(!isNewGui()){?>
   <div style="text-align:left;position:absolute; top:1px; left:281px; padding:0px;">
      <button id="projectSelectorComboButton" dojoType="dijit.form.Button" showlabel="false " style="position: relative; left:26px; top:-1px; height: 20px"
         title="<?php echo i18n('searchProject');?>" iconClass="iconSearch16 iconSearch iconSize16">
         <script type="dojo/connect" event="onClick" args="evt">        
            showDetail('projectSelectorFiletering', false , 'Project',false,null,true);    
         </script>
       </button>
	</div>
	<?php }?>
<?php } else if($displayMode=="search") {?>
<select id="projectSelectorFiletering" data-dojo-type="dijit.form.FilteringSelect" class="input" style="position: absolute; left:4px; top:<?php echo (isNewGui())?'-3':'1';?>px; width: 241px;height:<?php echo (isNewGui())?'20':'22';?>px;"  
<?php echo autoOpenFilteringSelect();?>
name="projectSelectorFiletering" 
    data-dojo-props="
        queryExpr: '*${0}*',
        autoComplete:false">
  <script type="dojo/connect" event="onChange" args="evt">
    if (this.isValid()) {
      setSelectedProject(this.value, this.displayedValue, null,true);
    }
  </script>
   <option value="*"><?php echo i18n("allProjects");?></option>
   <?php htmlDrawOptionForReference("idProject", $proj, null, true,$critFld, $critVal, $limitToActiveProjects,false,false,true,false,true);?>  
</select>
	<input type="hidden" id="projectSelectorMode" value="Filtering" />
	 <?php if(!isNewGui()){?>
   <div style="text-align:left;position:absolute; top:1px; left:281px; padding:0px;">
      <button id="projectSelectorComboButton" dojoType="dijit.form.Button" showlabel="false " style="position: relative; left:26px; top:-1px; height: 20px"
         title="<?php echo i18n('searchProject');?>" iconClass="iconSearch16 iconSearch iconSize16">
         <script type="dojo/connect" event="onClick" args="evt">        
            showDetail('projectSelectorFiletering', false , 'Project',false,null,true);    
         </script>
       </button>
	</div>
	<?php }?>
<?php } else  {
  ?>
ERROR : Unknown display mode
<?php }?>
