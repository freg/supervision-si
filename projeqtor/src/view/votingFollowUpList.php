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

$idUser=getSessionUser()->id;
$showClosedVotingFollowUp=(pq_trim(Parameter::getUserParameter('showClosedVotingFollowUp'))!='' and Parameter::getUserParameter('showClosedVotingFollowUp')!='0')?true:false;
$showStatus=Parameter::getUserParameter('votingFollowUpStatus');
$showSorting=Parameter::getUserParameter('votingFollowUpSorting');
$element = null;
$showIdle = false;
$limit=getSessionValue('votingFollowUpLimit'); 
if (!$limit) $limit=100;
?>

<div dojoType="dijit.layout.BorderContainer" id="votingFollowUpParamDiv" name="votingFollowUpParamDiv">  
  <div dojoType="dijit.layout.ContentPane" region="top" id="votingFollowUpButtonDiv" class="listTitle" >
  <form dojoType="dijit.form.Form" name="votingFollowUpForm" id="votingFollowUpForm" action="" method="post">
  <table width="100%" height="64px" class="listTitle">
    <tr height="32px">
      <td style="vertical-align:top; min-width:100px; width:15%;">
        <table>
		      <tr height="32px">
  		      <td width="50px" align="center">
              <?php echo formatIcon('VotingFollowUp', 32, null, true);?>
            </td>
            <td width="100px"><span class="title"><?php echo i18n('menuVotingFollowUp');?></span></td>
  		    </tr>
  		    <tr height="32px">
            <td>
              <div style="width:50px"></div>
            </td>
          </tr>
		    </table>
      </td>
      <td><table>
        <tr>
          <td nowrap="nowrap" style="text-align: right;padding-right:5px;"> <?php echo ucfirst(i18n("colElement"));?> &nbsp;</td>
          <td>
             <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="votingFollowUpElement" name="votingFollowUpElement" 
                data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                value="<?php if(sessionValueExists('votingFollowUpElement')){
                                        $element =  getSessionValue('votingFollowUpElement');
                                        echo $element; }?>"  style="width: 100px;" class="input">
                <option value=" ">
                </option>
                <?php $vote = new VotingItem();
                       $lstClass = $vote->getVotableClassList();
                       foreach ($lstClass as $value){?>
                <option value="<?php echo $value; ?>"
                  <span ><?php echo htmlEncode(i18n($value));?></span>
                </option>
                <?php } ?>
                   <script type="dojo/method" event="onChange" >
                    saveDataToSession("votingFollowUpElement",dijit.byId('votingFollowUpElement').get('value'),false);
                    refreshVotingFollowUpList();
                  </script>
               </select>
          </td>
         </tr>
         <td nowrap="nowrap" style="text-align: right;padding-right:5px;"> <?php echo i18n("colLimitOfHistory");?> &nbsp;</td>
          <td>
             <div dojoType="dijit.form.NumberTextBox" id="votingFollowUpLimit" name="votingFollowUpLimit" 
                constraints="{min:10,max:1000,places:0,pattern:\'###0\'}"
                value="<?php echo $limit;?>"  
                style="width: 100px;" class="input">
                  <script type="dojo/method" event="onChange" >
                    saveDataToSession("votingFollowUpLimit",dijit.byId('votingFollowUpLimit').get('value'),false);
                    refreshVotingFollowUpList();
                  </script>
               </div>
          </td>
         </tr>
       </table></td>
       <td>   
        <table>
          <tr>
           <td nowrap="nowrap" style="text-align:left;padding-right:5px;padding-left:15px;"></td>
           <td>
                  <div style="position:relative;text-align:left;">
                      <input type="radio" data-dojo-type="dijit/form/RadioButton" style="margin:5px;float:left;"
                      <?php if ($showStatus=='all') { echo "checked='checked'"; }?>
                        id="votingFollowUpStatusAll" name="votingFollowUpStatus" value="all" 
                        onclick="var callBack=function() {refreshVotingFollowUpList();}; saveDataToSession('votingFollowUpStatus', this.value, false,callBack);"/>
                   <label for="votingFollowUpStatusAll" class="notLabel" style="color:var(--color-list-header-text) !important;text-shadow: 0px 0px;text-align:left;"><?php echo i18n('all');?></label>
                  </div>
               </td>
              </tr>
              <tr>
                <td nowrap="nowrap" style="text-align:left;padding-right:5px;padding-left:15px;"><?php echo ucfirst(i18n("lockStatus"));?>&nbsp;</td>
                <td>
                    <div style="position:relative;text-align:left;">
                        <input type="radio" data-dojo-type="dijit/form/RadioButton" style="margin:5px;float:left;"
                        <?php if ($showStatus=='notLock') { echo "checked='checked'"; }?>
                          id="votingFollowUpStatusNotLock" name="votingFollowUpStatus" value="notLock"
                          onclick="var callBack=function() {refreshVotingFollowUpList();}; saveDataToSession('votingFollowUpStatus', this.value, false,callBack);"/>
                        <label for="votingFollowUpStatusNotLock" class="notLabel" style="color:var(--color-list-header-text) !important;text-shadow: 0px 0px;text-align:left;"><?php echo i18n('notLocked');?></label>
                    </div>
                </td>
              </tr>
              <tr>
                <td nowrap="nowrap" style="text-align:left;padding-right:5px;padding-left:15px;">&nbsp;</td>
                <td>
                    <div style="position:relative;text-align:left;">
                        <input type="radio" data-dojo-type="dijit/form/RadioButton" style="margin:5px;float:left;"
                        <?php if ($showStatus=='lock') { echo "checked='checked'"; }?>
                          id="votingFollowUpStatusLock" name="votingFollowUpStatus" value="lock"
                          onclick="var callBack=function() {refreshVotingFollowUpList();}; saveDataToSession('votingFollowUpStatus', this.value, false,callBack);"/>
                    </div>
                     <label for="votingFollowUpStatusLock" class="notLabel" style="color:var(--color-list-header-text) !important;text-shadow: 0px 0px;text-align:left;"><?php echo i18n('locked');?></label>
                  </td>
               </tr> 
             </table>
          </td>
            
          <td>   
            <table>
              <tr>
               <td nowrap="nowrap" style="text-align:left;padding-right:5px;"></td>
               <td>
                  <div style="text-align:left;">
                      <input type="radio" data-dojo-type="dijit/form/RadioButton" style="margin:5px;float:left"
                      <?php if ($showSorting=='class') { echo "checked='checked'"; }?>
                        id="votingFollowUpSortingClass" name="votingFollowUpSorting" value="class" 
                        onclick="var callBack=function() {refreshVotingFollowUpList();}; saveDataToSession('votingFollowUpSorting', this.value, false,callBack);"/>
                   <label for="votingFollowUpSortingClass" class="notLabel" style="color:var(--color-list-header-text) !important;text-shadow: 0px 0px;text-align:left;"><?php echo i18n('byClassId');?></label>
                  </div>
                 </td>
                </tr>
                  <tr>
                    <td nowrap="nowrap" style="text-align:left;padding-right:5px;"><?php echo ucfirst(i18n("sorting"));?>&nbsp;</td>
                    <td>
                        <div style="text-align:left;">
                            <input type="radio" data-dojo-type="dijit/form/RadioButton" style="margin:5px;float:left"
                            <?php if ($showSorting=='pct') { echo "checked='checked'"; }?>
                              id="votingFollowUpSortingPct" name="votingFollowUpSorting" value="pct"
                              onclick="var callBack=function() {refreshVotingFollowUpList();}; saveDataToSession('votingFollowUpSorting', this.value, false,callBack);"/>
                            <label for="votingFollowUpSortingPct" class="notLabel" style="color:var(--color-list-header-text) !important;text-shadow: 0px 0px;text-align:left;"><?php echo i18n('byPct');?></label>
                        </div>
                    </td>
                  </tr>
                  <tr>
                    <td nowrap="nowrap" style="text-align:left;padding-right:5px;">&nbsp;</td>
                    <td>
                        <div style="text-align:left;">
                            <input type="radio" data-dojo-type="dijit/form/RadioButton" style="margin:5px;float:left"
                            <?php if ($showSorting=='value') { echo "checked='checked'"; }?>
                              id="votingFollowUpSortingValue" name="votingFollowUpSorting" value="value"
                              onclick="var callBack=function() {refreshVotingFollowUpList();}; saveDataToSession('votingFollowUpSorting', this.value, false,callBack);"/>
                        </div>
                         <label for="votingFollowUpSortingValue" class="notLabel" style="color:var(--color-list-header-text) !important;text-shadow: 0px 0px;text-align:left;"><?php echo i18n('byValue');?></label>
                      </td>
                   </tr> 
                 </table>
            </td>
            
            <td align="top">
            <div style="position:absolute;right:<?php echo((isNewGui())?'80':'10');?>px;top:0px;">
              <label for="showClosedVotingFollowUp"  class="<?php echo((isNewGui())?'dijitTitlePaneTitle;':'');?>" style="border:0;font-weight:normal !important;<?php echo((isNewGui())?'padding-top:13px;':'text-shadow:unset;');?>;height:<?php echo ((isNewGui())?'20':'10');?>px;width:<?php echo((isNewGui())?'50':'150');?>px"><?php echo i18n('labelShowIdle'.((isNewGui())?'Short':''));?>&nbsp;</label>
              <div class="<?php echo ((isNewGui())?"whiteCheck":"");?>" id="showClosedVotingFollowUp" style="<?php echo ((isNewGui())?'margin-top:14px':'');?>" 
              dojoType="dijit.form.CheckBox" type="checkbox" <?php echo (($showClosedVotingFollowUp)?'checked':'');?> title="<?php echo i18n('labelShowIdle') ;?>" >
                <script type="dojo/connect" event="onChange" args="evt">
                  var callBack=function() {refreshVotingFollowUpList();};
                  saveDataToSession('showClosedVotingFollowUp', ((this.checked)?'on':'off'), false,callBack);
                </script>
              </div>
            </div>
          </td>
        </tr>
      </table>
    </form>
  </div>
  <div id="votingFollowUpDiv" name="votingFollowUpDiv" dojoType="dijit.layout.ContentPane" region="center">
    <div id="votingFollowUpAttributionRules" name="votingFollowUpAttributionRules">
      <?php VotingAttribution::drawVotingFollowUpAttributionRules($idUser); ?>
    </div>
    <div id="votingFollowUpItems" name="votingFollowUpItems">
      <?php VotingAttribution::drawVotingFollowUpItems($idUser,$element,$showStatus,$showSorting,$showIdle,$limit); ?>
    </div>
  </div>
</div>
