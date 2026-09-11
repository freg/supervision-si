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
$idProfile=getSessionUser()->idProfile;
$element = null;
$left = false;
if(sessionValueExists('showAttributionWithoutLeft'))$left=getSessionValue('showAttributionWithoutLeft');
$readonly=false;
$canSeeVotes=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array('idProfile'=>$idProfile, 'scope'=>'canManageVotes'));
$idResource=$idUser;
$idClient=0;
if(!$canSeeVotes->id){
  $readonly=true;
  $idClient=0;
}else {
  if(sessionValueExists('userAttributionName')) $idResource =  pq_trim(getSessionValue('userAttributionName'));
  if(sessionValueExists('idClientAttributionFollowUp')) $idClient =  pq_trim(getSessionValue('idClientAttributionFollowUp'));
}
?>

<div dojoType="dijit.layout.BorderContainer" id="votingFollowUpParamDiv" name="votingFollowUpParamDiv">  
  <div dojoType="dijit.layout.ContentPane" region="top" id="votingFollowUpButtonDiv" class="listTitle"  style="overflow-y:auto;">
  <form dojoType="dijit.form.Form" name="votingAttributionFollowUpForm" id="votingAttributionFollowUpForm" action="" method="post">
  <table width="100%" height="64px" class="listTitle">
    <tr height="32px">
      <td style="vertical-align:top; min-width:100px; width:15%;">
        <table>
		      <tr height="32px">
  		      <td width="50px" align="center">
              <?php echo formatIcon('VotingAttributionFollowUp', 32, null, true);?>
            </td>
            <td width="100px"><span class="title"><?php echo i18n('menuVotingAttributionFollowUp');?></span></td>
  		    </tr>
  		    <tr height="32px">
            <td>
              <div style="width:50px"></div>
            </td>
          </tr>
		    </table>
      </td>
	  <td align="right" style="padding:10px;white-space:nowrap;"><?php echo i18n("labelShowAttributionWithoutLetf");?></td>
      <td style="text-align:left;">
          <?php if(isNewGui()){?>
          <div  id="showAttributionWithoutLeftS" name="showAttributionWithoutLeftS" class="colorSwitch" data-dojo-type="dojox/mobile/Switch" value="<?php if($left=='1'){?>on<?php }else{?>off<?php }?>" leftLabel="" rightLabel="">
            <script type="dojo/method" event="onStateChanged" >
              var val=(dijit.byId('showAttributionWithoutLeftS').get('value')=='on')?1:0;
              dojo.byId('showAttributionWithoutLeft').value=val;
              saveDataToSession("showAttributionWithoutLeft",val,true);
              refreshVotingAttributionFollowUp();
            </script>
          </div>
          <?php }else{?>
          <div style="width:50px;text-align:center;"><div class="greyCheck" dojoType="dijit.form.CheckBox" type="checkbox" name="showAttributionWithoutLeftC" id="showAttributionWithoutLeftC">
            <script type="dojo/method" event="onChange" >
              var val=(dijit.byId('showAttributionWithoutLeftC').get('value')=='on')?1:0;
              dojo.byId('showAttributionWithoutLeft').value=val;
              saveDataToSession("showAttributionWithoutLeft",val,true);
              refreshVotingAttributionFollowUp();
            </script>
          </div>

          </div>
          <?php }?>
          <input type="hidden" value="<?php echo $left;?>" id="showAttributionWithoutLeft" name="showAttributionWithoutLeft" >
      </td>
      <td nowrap="nowrap" style="text-align: right;padding-right:15px;"> <?php echo i18n("colIdUser");?> &nbsp;</td>
      <td>
          <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft"  style="width: 175px;" name="userAttributionName" id="userAttributionName"
            <?php echo autoOpenFilteringSelect();?> <?php echo ($readonly)?'readonly':'';?>
            value="<?php echo $idResource?>" <?php echo ($idResource!="")?'selected':''?>>
              <option value=""></option>
                    <?php 
                    $specific='imputationUsers';
                     include '../tool/drawResourceListForSpecificAccess.php';?>  
              <script type="dojo/method" event="onChange" >
                    if(dijit.byId('userAttributionName').get('value').trim()!=''){
                      dijit.byId('idClientAttributionFollowUp').set('value','');
                      dijit.byId('idClientAttributionFollowUp').set('disabled',true);
                    }else{
                      dijit.byId('idClientAttributionFollowUp').set('disabled',false);
                    }
                    saveDataToSession("userAttributionName",dijit.byId('userAttributionName').get('value'),true);
                    refreshVotingAttributionFollowUp();
              </script>
                  
        </select>
      </td>

                </select>
      <?php if($canSeeVotes->id){?>
      <td nowrap="nowrap" style="text-align: right;padding-right:15px;"> <?php echo i18n("colIdClient");?> &nbsp;</td>
      <td>
        <select dojoType="dijit.form.FilteringSelect" class="input" style="width:175px;" 
                <?php echo autoOpenFilteringSelect();?>
                 id="idClientAttributionFollowUp" name="idClientAttributionFollowUp" value="<?php echo $idClient;?>" <?php echo ($idResource)?'disabled':''?>>
                 <?php htmlDrawOptionForReference('idClient', null, null, false);?>
                  <script type="dojo/method" event="onChange" >
                    saveDataToSession("idClientAttributionFollowUp",dijit.byId('idClientAttributionFollowUp').get('value'),true);
                    refreshVotingAttributionFollowUp();
                  </script>
        </select>
      </td>
      <?php }?>
       <td nowrap="nowrap" style="text-align: right;padding-right:5px;"> <?php echo ucfirst(i18n("colElement"));?> &nbsp;</td>
           <td>
             <select dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                id="votingAttributionFollowUpElement" name="votingAttributionFollowUpElement" 
                data-dojo-props="queryExpr: '*${0}*',autoComplete:false"
                value="<?php if(sessionValueExists('votingAttributionFollowUpElement')) echo  getSessionValue('votingAttributionFollowUpElement');?>"  
                style="width: 175px;" class="input">
                <option value=""></option>
                <?php $vote = new VotingItem();
                       $lstClass = $vote->getVotableClassList();
                       foreach ($lstClass as $value){?>
                        <option value="<?php echo $value; ?>"
                          <span ><?php echo htmlEncode(i18n($value));?></span>
                        </option>
                <?php   } ?>
                   <script type="dojo/method" event="onChange" >
                    saveDataToSession("votingAttributionFollowUpElement",dijit.byId('votingAttributionFollowUpElement').get('value'),false);
                    refreshVotingAttributionFollowUp();
                  </script>
               </select>
          </td>
        </tr>
      </table>
    </form>
  </div>
</div>
