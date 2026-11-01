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

require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
require_once '../tool/agileBacklogFunction.php';

$idBacklog=-1;
$user = getSessionUser();
$type="";
$name="";

$idSprint = Parameter::getUserParameter('sprintBacklogIdSprint');
$searchByName = Parameter::getUserParameter('sprintBacklogSearchByName');
$searchByResponsible = Parameter::getUserParameter('sprintBacklogSearchByResponsible');
$searchByTargetProductVersion = Parameter::getUserParameter('sprintBacklogSearchByTargetProductVersion');
$orderBy = Parameter::getUserParameter('sprintBacklogOrderBy');

?>
<input type="hidden" name="objectClassManual" id="objectClassManual" value="SprintBacklog" />
<div class="container" dojoType="dijit.layout.BorderContainer" id="divSprintBacklogAllContainer">
  <div id="sprintBacklogHeader" class="listTitle" style="z-index:3;overflow:visible;min-height:65px;"
    dojoType="dijit.layout.ContentPane" region="top">
    <table width="100%">
      <tr height="100%" style="vertical-align: middle;">
        <td style="width:50px;">          
          <div style="position:absolute;top:2px">
            <?php echo formatIcon('SprintBacklog',32,null,true);?>
          </div>
      	</td>
      	<td style="height:35px;">
          <div style="display:flex; align-items:center; gap:8px; white-space:nowrap;">
            <span class="title"><?php echo i18n('menuSprintBacklog'); ?></span>
          </div>
        </td>
      </tr>
      <tr>
      	<td colspan="2">
    			<div style="width:100%; margin: 0px 10px;">
    				<form dojoType="dijit.form.Form" id="sprintBacklogForm" action="" method="">
    				  <input dojoType="dijit.form.TextBox" type="hidden" id="refreshActionAddSprintBacklog" value="-1" onchange="refreshActionAddSprintBacklog(this)">
    					<input dojoType="dijit.form.TextBox" type="hidden" id="refreshActionAddItemBacklog" value="-1" onchange="refreshActionAddItemBacklog(this)">
    					<?php echo i18n("colIdSprint");?> :
    					<select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 150px;" 
              <?php echo autoOpenFilteringSelect ();?>
              onChange="saveDataToSession('sprintBacklogIdSprint', this.value, true);refreshSprintBacklog();" name="listIdSprintBacklog" id="listIdSprintBacklog" 
              value="<?php echo $idSprint;?>">
                <?php if(is_numeric(getSessionValue("project"))){
                  htmlDrawOptionForReference("idSprint", null, null, false, 'idProject', getSessionValue("project"));
                }else{
                  htmlDrawOptionForReference("idSprint", null);
                }?>
              </select>
              <?php echo i18n("colName");?> : <input dojoType="dijit.form.TextBox" onKeyUp="filterBacklog();saveDataToSession('sprintBacklogSearchByName', dojo.byId('searchByName').value, true);" class="dijit dijitReset dijitInline dijitLeft filterField rounded dijitTextBox" type="text" id="searchByName" value="<?php echo $searchByName;?>">
              <?php echo i18n("colResponsible");?> : 
              <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
                <?php echo autoOpenFilteringSelect ();?>
                style="width: 150px;" onChange="filterBacklog();saveDataToSession('sprintBacklogSearchByResponsible', this.value, true);" name="searchByResponsible" id="searchByResponsible"
                value="<?php echo $searchByResponsible;?>">
                  <option value=""></option>
                    <?php $specific='diary';
                      include '../tool/drawResourceListForSpecificAccess.php';?> 
              </select>
          		<?php echo i18n("colIdVersion"); ?> : 
              <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 150px;" 
              <?php echo autoOpenFilteringSelect ();?>
              onChange="filterBacklog();saveDataToSession('sprintBacklogSearchByTargetProductVersion', this.value, true);" name="searchByTargetProductVersion" id="searchByTargetProductVersion" 
              value="<?php echo $searchByTargetProductVersion;?>">
                <?php
//                 if(is_numeric(getSessionValue("project"))){
//                   htmlDrawOptionForReference("idTargetProductVersion", null, null, false, 'idProject', getSessionValue("project"));
//                 }else{
                  htmlDrawOptionForReference("idTargetProductVersion", null);
//                 }
                ?>
              </select>
              <?php echo i18n('sortedBy'); ?> : 
              <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:150px;margin-right:15px;"
                <?php echo autoOpenFilteringSelect ();?>
              	onChange="saveDataToSession('sprintBacklogOrderBy', this.value, true);filterBacklog(true);" name="sprintBacklogOrderBy" id="sprintBacklogOrderBy">
                <option <?php if($orderBy=="")echo "selected";?> value=""></option>
                <option <?php if($orderBy=="id")echo "selected";?> value="id"><?php echo i18n("colId");?></option>
                <option <?php if($orderBy=="name")echo "selected";?> value="name"><?php echo i18n("colName");?></option>
                <option <?php if($orderBy=="scrumPriority")echo "selected";?> value="scrumPriority"><?php echo i18n("colIdScrumPriority");?></option>
                <option <?php if($orderBy=="storyPointsASC")echo "selected";?> value="storyPointsASC"><?php echo i18n("colStoryPoints")." (".i18n('sortAsc').")";?></option>
                <option <?php if($orderBy=="storyPointsDESC")echo "selected";?> value="storyPointsDESC"><?php echo i18n("colStoryPoints")." (".i18n('sortDesc').")";?></option>
                <option <?php if($orderBy=="businessValueASC")echo "selected";?> value="businessValueASC"><?php echo i18n("colBusinessValue")." (".i18n('sortAsc').")";?></option>
                <option <?php if($orderBy=="businessValueDESC")echo "selected";?> value="businessValueDESC"><?php echo i18n("colBusinessValue")." (".i18n('sortDesc').")";?></option>
              </select>
              <div style="float:right;padding-right:15px;">
                <div dojoType="dijit.form.DropDownButton"							    
                 id="extraButtonSprintBacklog" jsId="extraButtonSprintBacklog" name="extraButtonSprintBacklog" 
                 showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton" 
                 title="<?php echo i18n('extraButtons');?>">
                   <div dojoType="dijit.TooltipDialog" class="white" id="extraButtonSprintBacklogDialog" tyle="position: absolute; top: 50px; right: 40%">        
                     <table style="margin:5px">
                       <tr style="width:100%;">
                        <td><?php sprintBacklogParameterList();?></td>
                       </tr>
                     </table>
                   </div>
                </div>
        			</div>
      			</form>
   			 </div>
        <div dojoType="dijit.layout.ContentPane" id="sprintBacklogJsonData" jsId="sprintBacklogJsonData" style="display: none">
    	  	<?php include '../tool/jsonSprintBacklog.php';?>
    		</div>
      	</td>
      </tr>
    </table>
  </div>
  <div class="container" dojoType="dijit.layout.ContentPane" id="divBacklogContainer" region="center" style=" overflow-x:scroll;">
    <?php include "../view/sprintBacklogView.php";?>
  </div>
</div>