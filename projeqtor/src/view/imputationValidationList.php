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
 * Presents the list of objects of a given class.
 *
 */
require_once "../tool/projeqtor.php";
require_once "../tool/formatter.php";
scriptLog('   ->/view/imputationValidationList.php');

$user=getSessionUser();
$userName="";
$userTeam="";
$userOrga="";
$showValidated = getSessionValue('showValidatedWork', 2);
$showSubmitted = getSessionValue('showSubmitWork', 2);
$showError = getSessionValue('showErrorWork', 2);
$currentDay=date('Y-m-d');

if(sessionValueExists('startWeekImputationValidation')){
  $currentWeek = weekNumber(getSessionValue('startWeekImputationValidation'));
  $currentYear = date('Y',pq_strtotime(getSessionValue('startWeekImputationValidation')));
  $currentMonth = date('m',pq_strtotime(getSessionValue('startWeekImputationValidation')));
}else{
  $currentWeek = date('W');
  $currentYear = date('Y');
  $currentMonth = date('m');
}
if ($currentWeek==1 and $currentMonth>10 ) {
	$currentYear+=1;
}
if ($currentWeek>50 and $currentMonth==1 ) {
	$currentYear-=1;
}
$firstDay = date('Y-m-d', firstDayofWeek($currentWeek, $currentYear));
if(sessionValueExists('startWeekImputationValidation')){
  $firstDay = getSessionValue('startWeekImputationValidation');
}
$lastDay = '';
if(sessionValueExists('endWeekImputationValidation')){
	$lastDay =getSessionValue('endWeekImputationValidation');
}
$destinationWidth=RequestHandler::getValue('destinationWidth',false,1200);
?>

<div dojoType="dijit.layout.BorderContainer" id="imputationValidationParamDiv" name="imputationValidationParamDiv">  
  <div dojoType="dijit.layout.ContentPane" region="top" id="imputationValidationButtonDiv" class="listTitle" >
  <form dojoType="dijit.form.Form" name="imputValidationForm" id="imputValidationForm" action="" method="post" >
  <table width="100%" height="64px" class="listTitle">
    <tr height="32px">
    <td style="vertical-align:top; min-width:100px; width:15%;">
      <table >
		    <tr height="32px">
  		    <td width="50px" align="center">
            <?php echo formatIcon('ImputationValidation', 32, null, true);?>
          </td>
          <td width="100px;"><div class="title" <?php if ($destinationWidth<=1200){ ?> style="max-width:100px;white-space: normal"<?php }?>><?php echo i18n('menuImputationValidation');?></div></td>
  		  </tr>
  		  <tr height="32px">
          <td>
          <?php if(!isNewGui()){?>
            <button id="refreshImputationValidationButton" dojoType="dijit.form.Button" showlabel="false"
              title="<?php echo i18n('buttonRefreshList');?>"
              iconClass="dijitButtonIcon dijitButtonIconRefresh" class="detailButton">
              <script type="dojo/method" event="onClick" args="evt">
	             refreshImputationValidation(null);
              </script>
            </button> 
           <?php }else{ ?>
           <div style="width:50px"></div>
           <?php } ?>
          </td>
        </tr>
		  </table>
    </td>
      <td>   
        <table>
         <tr>
           <td nowrap="nowrap" style="text-align: right;padding-right:5px;"> <?php echo i18n("colIdProject");?> &nbsp;</td>
           <td>
              <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
                style="width: <?php echo ($destinationWidth<=1200)?150:175; ?>px;" data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                name="idProjectValidation" id="idProjectValidation"
                <?php echo autoOpenFilteringSelect();?>
                value="<?php  if(sessionValueExists('project') and getSessionValue('project')!="" and  getSessionValue('project')!="*" and pq_trim(pq_strpos(getSessionValue('project'),','))==''){
                                 $idProject =  getSessionValue('project');
                                 echo $idProject;
                             }else if(sessionValueExists('idProjectValidation') and pq_trim(getSessionValue('idProjectValidation'))!=''){
                               $idProject =  getSessionValue('idProjectValidation');
                               echo $idProject;
                             }else{
                              $idProject=0;
                              echo $idProject;
                             }?>">
                  <script type="dojo/method" event="onChange" >
                    saveDataToSession("idProjectValidation",dijit.byId('idProjectValidation').get('value'),false);
                    refreshImputationValidation(null);
                  </script>
                  <?php htmlDrawOptionForReference('idProject', null);?>  
              </select>
           </td>
           <td nowrap="nowrap" style="text-align: right;padding-left:20px; padding-right:5px;"><?php echo i18n("weekStartLabel");?></td>
           <td>
             <div dojoType="dijit.form.DateTextBox"
              <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
  							echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
  						 }?>
               id="startWeekImputationValidation" name="startWeekImputationValidation"
               invalidMessage="<?php echo i18n('messageInvalidDate')?>"
               type="text" maxlength="10"
               style="width:100px; text-align: center;" class="input roundedLeft"
               hasDownArrow="true"
               value="<?php echo $firstDay;?>" >
               <script type="dojo/method" event="onChange" >
                 var start=dijit.byId('startWeekImputationValidation').get("value");
                 var end=dijit.byId('endWeekImputationValidation').get('value');
                 saveDataToSession('startWeekImputationValidation',formatDate(start), false);
                 refreshImputationValidation(start, end);
               </script>
             </div>
           </td>
           <td nowrap="nowrap" style="text-align: right;padding-left:5px; padding-right:5px;"><?php echo i18n("weekEndLabel");?></td>
           <td>
           <div dojoType="dijit.form.DateTextBox"
               <?php if (sessionValueExists('browserLocaleDateFormatJs')) {
  							echo ' constraints="{datePattern:\''.getSessionValue('browserLocaleDateFormatJs').'\'}" ';
  						 }?>
               id="endWeekImputationValidation" name="endWeekImputationValidation"
               type="text" maxlength="10" hasDownArrow="true"
               style="width:100px; text-align:center;" class="input roundedLeft"
               value="<?php echo $lastDay;?>" >
               <script type="dojo/method" event="onChange" >
                 var start=dijit.byId('startWeekImputationValidation').get("value");
                 var end = dijit.byId('endWeekImputationValidation').get('value');
                 saveDataToSession('endWeekImputationValidation',formatDate(end), false);
                 refreshImputationValidation(start, end);
               </script>
             </div>
           </td>
           </tr>
           <tr>
             <td nowrap="nowrap" style="text-align: right;padding-right:5px;"><?php echo i18n("colIdResource");?></td>
             <td>
                <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
                  style="width: 150px;"
                  name="userName" id="userName"
                  <?php echo autoOpenFilteringSelect();?>
                  value="<?php if(sessionValueExists('userNameValidation')){
                                $userName =  getSessionValue('userNameValidation');
                                echo $userName;
                               }else{
                                echo $userName;
                               }?>">
                    <script type="dojo/method" event="onChange" >
                    saveDataToSession("userNameValidation",dijit.byId('userName').get('value'),false);
                    refreshImputationValidation(null);
                  </script>
                    <option value=""></option>
                    <?php
                     $specific='imputation';
                     include '../tool/drawResourceListForSpecificAccess.php';?>  
                </select>
             </td>
             <td nowrap="nowrap" style="text-align: right;padding-left:50px; padding-right:5px;"><?php echo i18n("colIdTeam");?></td>
               <td>
                 <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
                    style="width: 150px;"
                    name="idTeam" id="idTeam"
                    <?php echo autoOpenFilteringSelect();?>
                    value="<?php if(sessionValueExists('idTeamValidation')){
                                  echo getSessionValue('idTeamValidation');
                                  $userTeam = getSessionValue('idTeamValidation');
                                 }?>">
                    <script type="dojo/method" event="onChange" >
                      saveDataToSession("idTeamValidation",dijit.byId('idTeam').get('value'),false);
                      refreshImputationValidation(null);
                    </script>
                    <?php htmlDrawOptionForReference('idTeam', null)?>
                </select>
             </td>
              <td nowrap="nowrap" style="text-align: right;padding-left:50px; padding-right:5px;"><?php echo i18n("colIdOrganization");?></td>
               <td>
                 <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
                    style="width: 150px;"
                    name="idOrganization" id="idOrganization"
                    <?php echo autoOpenFilteringSelect();?>
                    value="<?php if(sessionValueExists('idOrganizationValidation')){
                                  echo getSessionValue('idOrganizationValidation');
                                  $userOrga = getSessionValue('idOrganizationValidation');
                                 }?>">
                    <script type="dojo/method" event="onChange" >
                      saveDataToSession("idOrganizationValidation",dijit.byId('idOrganization').get('value'),false);
                      refreshImputationValidation(null);
                    </script>
                    <?php htmlDrawOptionForReference('idOrganization', null)?>
                </select>
             </td>
         </tr>
        </table>
      </td>
      <?php if(isNewGui()){?>
      <td style="vertical-align:top;text-align: right;padding-right: 5px;">
        <div dojoType="dijit.form.DropDownButton" id="extraImputationValidation" jsId="extraImputationValidation" name="extraImputationValidation" 
           showlabel="false" class="comboButton" iconClass="dijitButtonIcon dijitButtonIconExtraButtons" class="detailButton" title="<?php echo i18n('extraButtons');?>">
           <div dojoType="dijit.TooltipDialog" class="white" id="extraButtonImputationValidation" style="position: absolute; top: 50px; right: 40%">
            <table width="100%">
              <tr>
                <td>
                  <table><tr><td>
                  <label for="showUnvalidated" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowUnvalidated');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton"
                  <?php if ($showValidated==0) { echo "checked='checked'"; }?>
                    id="showUnvalidated" name="showValidatedWork" value="0" 
                    onclick="saveDataToSession('showValidatedWork', this.value);refreshImputationValidation(null);"/>
                  </td>
                  <td>
                  <label for="showValidated" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowValidated');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton"
                  <?php if ($showValidated==1) { echo "checked='checked'"; }?>
                    id="showValidated" name="showValidatedWork" value="1"
                    onclick="saveDataToSession('showValidatedWork', this.value);refreshImputationValidation(null);"/>
                    </td><td>
                  <label for="showAllValidated" class="notLabel" style="color:var(--color-list-header-text) !important;width:130px;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowAll');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton"
                  <?php if ($showValidated==2) { echo "checked='checked'"; }?>
                    id="showAllValidated" name="showValidatedWork" value="2"
                    onclick="saveDataToSession('showValidatedWork', this.value);refreshImputationValidation(null);"/>
                   </td> </tr></table>
               </td>
              </tr>
              <tr>
                <td>
                <table><tr><td>
                  <label for="showUnsubmitWork" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowUnsubmitWork');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton"
                  <?php if ($showSubmitted==0) { echo "checked='checked'"; }?>
                    id="showUnsubmitWork" name="showSubmitWork" value="0" 
                    onclick="saveDataToSession('showSubmitWork', this.value);refreshImputationValidation(null);"/>
                   </td><td>
                  <label for="showSubmitted" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowSubmitWork');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton"
                  <?php if ($showSubmitted==1) { echo "checked='checked'"; }?>
                    id="showSubmitted" name="showSubmitWork" value="1"
                    onclick="saveDataToSession('showSubmitWork', this.value);refreshImputationValidation(null);"/>
                   </td><td>
                  <label for="showAllSubmitted" class="notLabel" style="color:var(--color-list-header-text) !important;width:130px;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowAll');?></label>
                  <input type="radio" data-dojo-type="dijit/form/RadioButton"
                  <?php if ($showSubmitted==2) { echo "checked='checked'"; }?>
                    id="showAllSubmitted" name="showSubmitWork" value="2"
                    onclick="saveDataToSession('showSubmitWork', this.value);refreshImputationValidation(null);"/>
                    </td> </tr></table>
                </td>
              </tr>
              <tr>
                <td>
                  <table><tr><td>
                    <label for="showErrorOnly" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowErrorOnly');?></label>
                    <input type="radio" data-dojo-type="dijit/form/RadioButton"
                      <?php if ($showError==1) { echo "checked='checked'"; }?>
                      id="showErrorOnly" name="showErrorWork" value="1" 
                      onclick="saveDataToSession('showErrorWork', this.value);refreshImputationValidation(null);"/>
                  </td><td>
                    <label for="showNoError" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowNoError');?></label>
                    <input type="radio" data-dojo-type="dijit/form/RadioButton"
                      <?php if ($showError==0) { echo "checked='checked'"; }?>
                      id="showNoError" name="showErrorWork" value="0"
                      onclick="saveDataToSession('showErrorWork', this.value);refreshImputationValidation(null);"/>
                  </td><td>
                    <label for="showAllError" class="notLabel" style="color:var(--color-list-header-text) !important;width:130px;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowAll');?></label>
                    <input type="radio" data-dojo-type="dijit/form/RadioButton"
                      <?php if ($showError==2) { echo "checked='checked'"; }?>
                      id="showAllError" name="showErrorWork" value="2"
                      onclick="saveDataToSession('showErrorWork', this.value);refreshImputationValidation(null);"/>
                  </td></tr></table>
                </td>
              </tr>
            </table>
            </div>
          </div>
          </td>
      
          <td  style="vertical-align:top;">
            <button id="refreshImputationValidationButton" dojoType="dijit.form.Button" showlabel="false"
              title="<?php echo i18n('buttonRefreshList');?>"
              iconClass="dijitButtonIcon dijitButtonIconRefresh" class="detailButton">
              <script type="dojo/method" event="onClick" args="evt">
	             refreshImputationValidation(null);
              </script>
            </button> 
          </td>
      
      <?php }else{?>
      <td style="text-align: right; align: right;">
        <table width="100%">
          <tr>
            <td>
              <label for="showUnvalidated" class="notLabel" style="text-shadow: 0px 0px;"><?php echo i18n('colShowUnvalidated');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
              <?php if ($showValidated==='0') { echo "checked='checked'"; }?>
                id="showUnvalidated" name="showValidatedWork" value="0" 
                onchange="saveDataToSession('showValidatedWork', this.value);refreshImputationValidation(null);"/>
              <label for="showValidated" class="notLabel" style="text-shadow: 0px 0px;"><?php echo i18n('colShowValidated');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
              <?php if ($showValidated==='1') { echo "checked='checked'"; }?>
                id="showValidated" name="showValidatedWork" value="1"
                onchange="saveDataToSession('showValidatedWork', this.value);refreshImputationValidation(null);"/>
              <label for="showAllValidated" class="notLabel" style="text-shadow: 0px 0px;"><?php echo i18n('colShowAll');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
              <?php if ($showValidated==='') { echo "checked='checked'"; }?>
                id="showAllValidated" name="showValidatedWork" value=""
                onchange="saveDataToSession('showValidatedWork', this.value);refreshImputationValidation(null);"/>
           </td>
          </tr>
          <tr>
            <td>
              <label for="showUnsubmitWork" class="notLabel" style="text-shadow: 0px 0px;"><?php echo i18n('colShowUnsubmitWork');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
              <?php if ($showSubmitted==='0') { echo "checked='checked'"; }?>
                id="showUnsubmitWork" name="showSubmitWork" value="0" 
                onchange="saveDataToSession('showSubmitWork', this.value);refreshImputationValidation(null);"/>
              <label for="showSubmitted" class="notLabel" style="text-shadow: 0px 0px;"><?php echo i18n('colShowSubmitWork');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
              <?php if ($showSubmitted==='1') { echo "checked='checked'"; }?>
                id="showSubmitted" name="showSubmitWork" value="1"
                onchange="saveDataToSession('showSubmitWork', this.value);refreshImputationValidation(null);"/>
              <label for="showAllSubmitted" class="notLabel" style="text-shadow: 0px 0px;"><?php echo i18n('colShowAll');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
              <?php if ($showSubmitted==='') { echo "checked='checked'"; }?>
                id="showAllSubmitted" name="showSubmitWork" value=""
                onchange="saveDataToSession('showSubmitWork', this.value);refreshImputationValidation(null);"/>
            </td>
          </tr>
          <tr>
          <td>
            <table><tr><td>
              <label for="showErrorOnly" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowErrorOnly');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
                <?php if ($showError==1) { echo "checked='checked'"; }?>
                id="showErrorOnly" name="showErrorWork" value="1" 
                onclick="saveDataToSession('showErrorWork', this.value);refreshImputationValidation(null);"/>
            </td><td>
              <label for="showNoError" class="notLabel" style="color:var(--color-list-header-text) !important;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowNoError');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
                <?php if ($showError==0) { echo "checked='checked'"; }?>
                id="showNoError" name="showErrorWork" value="0"
                onclick="saveDataToSession('showErrorWork', this.value);refreshImputationValidation(null);"/>
            </td><td>
              <label for="showAllError" class="notLabel" style="color:var(--color-list-header-text) !important;width:130px;margin-top:-5px;text-shadow: 0px 0px;"><?php echo i18n('colShowAll');?></label>
              <input type="radio" data-dojo-type="dijit/form/RadioButton"
                <?php if ($showError==2) { echo "checked='checked'"; }?>
                id="showAllError" name="showErrorWork" value="2"
                onclick="saveDataToSession('showErrorWork', this.value);refreshImputationValidation(null);"/>
            </td></tr></table>
          </td>
        </tr>
        </table>
      </td>
      <?php }?>
    </tr>
  </table>
  </form>
  </div>
  <div id="imputationValidationWorkDiv" name="imputationValidationWorkDiv" dojoType="dijit.layout.ContentPane" region="center" >
    <div id="imputListDiv" name="imputListDiv">
      <?php 
      ImputationValidation::drawUserWorkList($userName, $userTeam ,$userOrga, $firstDay, $lastDay,$idProject);?>
    </div>
  </div>  
</div>