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
?>

<div dojoType="dijit/layout/TabContainer"  region="center" id="criticalTabContainer" style="width: 100%; height: 100%;">

  <div id="criticalResourceTab" onHide="dojo.byId('criticalLegend2').style.display='none';" onShow="dojo.byId('criticalLegend2').style.display='block';saveDataToSession('criticalSelectedTab','criticalResourceTab');" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('Resource');?>" <?php if ($selectedTab=='criticalResourceTab' or !$selectedTab){ ?> data-dojo-props="selected:true" <?php }?>>
    <div style="margin-left:2%;width:95%;display:inline-block;">
      <span class="title" style="margin-top:25px;margin-bottom:10px;display:block;"><?php echo i18n('listCriticalResources');?></span>
      <div style="height:100%; overflow-x:auto;">
      <?php Affectable::drawCriticalResourceList($scale, $firstDay, $lastDay, $proj, $maxResources); ?>
      </div>
    </div>
  </div>
    
  <div id="criticalPlanningTab" onHide="dojo.byId('criticalLegend').style.display='none';" onShow="dojo.byId('criticalLegend').style.display='block';saveDataToSession('criticalSelectedTab','criticalPlanningTab');" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('Planning');?>" <?php if ($selectedTab=='criticalPlanningTab'){ ?> data-dojo-props="selected:true" <?php }?>>   
    <div style="margin-left:2%; height:90%; margin-top:25px;margin-bottom:20px; width:95%;">
        <span class="title" style="margin:5px;display:block;"><?php  echo i18n('listCriticalResourcesByScale');?></span>
        <div style="height:100%; overflow-y:auto;">
          <?php Affectable::drawCriticalResourceActivityList($scale, $firstDay, $lastDay, $proj, $maxResources); ?>
        </div>
    </div>
  </div> 
   
  <div id="criticalExportTab" onShow="saveDataToSession('criticalSelectedTab','criticalExportTab');" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('tabExport');?>" <?php if ($selectedTab=='criticalExportTab'){ ?> data-dojo-props="selected:true" <?php }?>>   
    <div style="margin-left:2%; height:85%; margin-top:25px; width:95%;">
            <button title="<?php echo i18n('criticalResourcePrintExcel')?>"
               dojoType="dijit.form.Button" type="button"
               id="criticalResourcePrintExcel" name="criticalResourcePrintExcel"
               iconClass="dijitButtonIcon dijitButtonIconExcel" class="detailButton whiteBackground" showLabel="false">
               <script type="dojo/connect" event="onClick" args="evt">
                  showPrint("../view/criticalResourceExport.php",'criticalResource',null,'excel','X');
               </script>
            </button>
            <?php echo i18n('criticalResourcePrintExcel');?>
    </div>
  </div> 
     
   <div id="criticalScenarioTab" onShow="saveDataToSession('criticalSelectedTab','criticalScenarioTab');" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('Scenario');?>" <?php if ($selectedTab=='criticalScenarioTab'){ ?> data-dojo-props="selected:true" <?php }?>>
     <table style="width:100%"><tr><td style="width:60%; vertical-align:top">
     <?php CriticalResourceScenarioProject::drawProjectList(); ?>
     </td><td style="width:40%;vertical-align:top">
     <?php CriticalResourceScenarioPool::drawPoolList(); ?>
     </td></tr></table>
   </div>
    
   <div id="criticalGraphTab"   onHide="dojo.byId('criticalLegend3').style.display='none';" onShow="resourceListTransformation('criticalResourceGraph');dojo.byId('criticalLegend3').style.display='block';saveDataToSession('criticalSelectedTab','criticalGraphTab');" data-dojo-type="dijit/layout/ContentPane" title="<?php echo i18n('GlobalWorkPlanning');?>" <?php if ($selectedTab=='criticalGraphTab'){ ?> data-dojo-props="selected:true" <?php }?>>
     <div style="margin-left:2%; height:85%; margin-top:25px; width:95%;">
     
                    <div id="criticalLegend3" name="criticalLegend3" style="display:none;position:absolute;right:20px;padding:5px 10px;top:-0px;;border:1px solid #cccccc;background:#ffffffE0;" >
                    <table>
                      <tr style="height:20px" title="<?php echo i18n("criticalResourceLateHint");?>">
                        <td   class="dialogLabel"  ><div style="width:80px;height:20px;">
                          <?php echo i18n("colIdResource");  ?></div></td>
                      <td> 
                <div dojoType="dijit.form.FilteringSelect" 
               <?php echo autoOpenFilteringSelect();?>
                data-dojo-props="labelAttr:'label', labelType:'html'"
                id="criticalResourceGraph" name="criticalResourceGraph" 
                onChange="saveDataToSession('criticalResourceSelected', this.value, false);loadDiv('../view/refreshCriticalResourceGraphDiv.php','criticalGraphTabGraph','criticalResourcesForm');"
                class="input" style="width:150px;"
                <?php if (getSessionValue('criticalResourceSelected')){
                        $idResourceSelected = getSessionValue('criticalResourceSelected');
                      } else {
                        $idResourceSelected = '';
                      } ?>
                      value="<?php echo $idResourceSelected;?>"
                 <?php  htmlDrawOptionForReference('idCriticalResource',$idResourceSelected, null,null,null,null,null,null,null,null,null,true);?>
               </div> </td>
                      </tr>
                    </table>
                  </div>
     
       <div id="criticalGraphTabGraph" name="criticalGraphTabGraph">
       <?php  if (getSessionValue('criticalResourceSelected')){
                $idResourceSelected = getSessionValue('criticalResourceSelected');
              } else {
                $idResourceSelected = '';
              }
              Affectable::drawCriticalResourceGraph($scale,$firstDay,$lastDay,$idResourceSelected,$proj,'html');?>
       </div>
     </div>
   </div>
    
     <?php /* 
      if(!$hide){?>
      <div style="width:47%;max-width:766px;display:inline-block;margin-left:2%;">
        <span class="title" style="margin:5px;display:block;"><?php  echo i18n('listCriticalResourcesByProject');?></span>
        <div style="height:100%; border:0.1em solid grey;  overflow-x:auto;">
          <?php 
          //Affectable::drawCriticalResourceProjectList($scale, $firstDay, $lastDay, $proj, $maxResources);
          ?>
        </div>
      </div>
    </div>
     <div style="margin-left:2%; height:245px; margin-top:50px; width:45%;max-width:740px;">
        <span class="title" style="margin:5px;display:block;"><?php  echo i18n('listCriticalProjectResourcesList');?></span>
        <div style="height:100%; border:0.1em solid grey; overflow-y:hidden;">
          <?php //Affectable::drawCriticalProjectResourceList($scale, $firstDay, $lastDay, $proj, $maxResources); ?>
        </div>
        <br/><br/>
    </div>
     <?php }
     */?>
     
</div>