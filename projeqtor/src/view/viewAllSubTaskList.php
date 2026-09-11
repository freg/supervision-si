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
scriptLog('   ->/view/viewAllSubTaskList.php');

$idProject=0;
$idResource=0;
$idVersion=0;
$element='';
$idPriority=0;
$orderBy=0;

$tab =array("Activity","Ticket","Action");
$ElmentTab=array();
foreach ($tab as $elem){
  $menu=SqlElement::getSingleSqlElementFromCriteria('Menu', array('name'=>'menu'.$elem));
  if (!Module::isMenuActive($menu->name))  continue;
  if (!securityCheckDisplayMenu($menu->id,pq_substr($menu->name,4)))continue;
  $ElmentTab []=$elem;
}
$showClosedSubTask=(pq_trim(Parameter::getUserParameter('showClosedSubTask_Global'))!='' and Parameter::getUserParameter('showClosedSubTask_Global')!='0')?true:false;
$showDoneSubTask=((Parameter::getUserParameter('showDoneSubTask_Global')!='0') or $showClosedSubTask)?true:false;

if(sessionValueExists('project') and getSessionValue('project')!="" and  getSessionValue('project')!="*" ){
    $idProject=getSessionValue('project');
}
?>

<div dojoType="dijit.layout.BorderContainer" id="imputationConsolidationParamDiv" name="imputationConsolidationParamDiv">  
  <div dojoType="dijit.layout.ContentPane" region="top" id="subTasButtonDiv" class="listTitle" >
  <form dojoType="dijit.form.Form" name="SubTaskLisForm" id="SubTaskLisForm" action="" method="post" >
  <table width="100%" class="listTitle">
    <tr>
      <td >
        <table style="vertical-align:top;margin-top:5px; min-width:100px; width:15%;">
	     <tr>
	       <td  align="center">
            <?php echo formatIcon('ViewAllSubTask', 32, null, true);?>
           </td>
           <td width="100px"><span class="title">&nbsp;&nbsp;&nbsp;<?php echo i18n('menuViewAllSubTask');?></span></td>
		 </tr>
		 <tr height="32px">
          <td>
           <?php if(!isNewGui()){?>
            <button id="refreshAllSubTask" dojoType="dijit.form.Button" showlabel="false" title="<?php echo i18n('buttonRefreshList');?>" iconClass="dijitButtonIcon dijitButtonIconRefresh" class="detailButton">
              <script type="dojo/method" event="onClick" args="evt">
	             refreshAllSubTaskList();
              </script>
            </button> 
             <?php }else{ ?>
             <div style="width:40px;"></div>
             <?php }?>
          </td>
        </tr>
		  </table>
      </td>
      <td>   
        
        <table style="margin-left:15px;">
         <tr>
          <td>
            <div>
              <div style="float:left">
                <table><tr>
                <td nowrap="nowrap" style="text-align: right;padding-right:15px;min-width:75px;"> <?php echo i18n("colIdResource");?></td>
                <td>
                <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" 
                  style="width: 175px;"
                  name="userNameSubTask" id="userNameSubTask"
                  <?php echo autoOpenFilteringSelect();?>
                  value="<?php if(sessionValueExists('userNameSubTask')){
                                $idResource =  getSessionValue('userNameSubTask');
                                echo $idResource;
                               }else{
                                echo 0;
                               }?>">
                    <script type="dojo/method" event="onChange" >
                    saveDataToSession("userNameSubTask",dijit.byId('userNameSubTask').get('value'),true);
                    refreshAllSubTaskList();
                  </script>
                <option value=""></option>
                    <?php 
                    $specific='imputation';
                     include '../tool/drawResourceListForSpecificAccess.php';?>  
                </select>
                </td>
                </tr></table>
              </div>
              <div style="float:left;<?php if (! Module::isModuleActive('moduleConfiguration')) echo 'display:none;';?>">
                <table><tr>
                  <td nowrap="nowrap" style="text-align: right;padding-right:15px;padding-left:25px;"><?php echo i18n("colIdProductVersion");?></td>
                  <td>
                    <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 175px;" name="targetProductVersionSubTask" id="targetProductVersionSubTask"
                      <?php echo autoOpenFilteringSelect();?>
                      value="<?php if(sessionValueExists('targetProductVersionSubTask')){
                                    $idVersion =  getSessionValue('targetProductVersionSubTask');
                                    echo $idVersion;
                                   }else{
                                    echo 0;
                                   }?>">
                        <script type="dojo/method" event="onChange" >
                    saveDataToSession("targetProductVersionSubTask",dijit.byId('targetProductVersionSubTask').get('value'),true);
                    refreshAllSubTaskList();
                  </script>
                      <?php htmlDrawOptionForReference('idProductVersion',null)?>
                    </select>
                  </td>
                </tr></table>
              </div>
              <div style="float:left">
                <table><tr>
                  <td nowrap="nowrap" style="text-align: right;padding-right:15px;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <?php echo i18n("colType");?></td>
                  <td>
                   <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 175px;" name="elementSubTask" id="elementSubTask"
                      <?php echo autoOpenFilteringSelect();?>
                      value="<?php if(sessionValueExists('elementSubTask')){
                                    $element =  getSessionValue('elementSubTask');
                                    echo $element;
                                   }else{
                                    echo 0;
                                   }?>">
                        <script type="dojo/method" event="onChange" >
                    saveDataToSession("elementSubTask",dijit.byId('elementSubTask').get('value'),true);
                    refreshAllSubTaskList();
                  </script>
                    <?php 
                        echo ' <option value=" "></option>';
                        foreach ($ElmentTab as $key){
                          echo ' <option value="'.$key.'"><span selected="'.(($key==$element)?'selected':'').'" >'. htmlEncode(i18n($key)) . '</span></option>';
                        }
                    ?>
                    </select>
                  </td>
                </tr></table>
              </div>
              <div style="float:left">
                <table><tr>
                  <td nowrap="nowrap" style="text-align: right;padding-right:15px;">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <?php echo i18n("colIdPriority");?> </td>
                  <td>
                   <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width: 175px;" name="prioritySubTask" id="prioritySubTask"
                      <?php echo autoOpenFilteringSelect();?>
                      value="<?php if(sessionValueExists('prioritySubTask')){
                                    $idPriority =  getSessionValue('prioritySubTask');
                                    echo $idPriority;
                                   }else{
                                    echo 0;
                                   }?>">
                        <script type="dojo/method" event="onChange" >
                    saveDataToSession("prioritySubTask",dijit.byId('prioritySubTask').get('value'),true);
                    refreshAllSubTaskList();
                  </script>
                      <?php htmlDrawOptionForReference('idPriority',null)?>
                    </select>
                  </td>
                </tr></table>
              </div>
              
              <div style="float:left">
                <table><tr>
                  <td>
                     <div style="float:left">
                      <label for="showDoneSubTaskAll"  class="<?php echo((isNewGui())?'dijitTitlePaneTitle;':'');?>" style="border:0;font-weight:normal !important;<?php echo((isNewGui())?'padding-top:14px;':'text-shadow:unset;');?>;height:<?php echo ((isNewGui())?'20':'10');?>px;width:<?php echo((isNewGui())?'50':'150');?>px"><?php echo i18n('done');?>&nbsp;</label>
                      <div class="<?php echo ((isNewGui())?"whiteCheck":"");?>" id="showDoneSubTaskAll" style="<?php echo ((isNewGui())?'margin-top:14px':'');?>" <?php if($showClosedSubTask)echo "readonly";?>
                      dojoType="dijit.form.CheckBox" type="checkbox" <?php echo (($showDoneSubTask)?'checked':'');?> title="<?php echo i18n('done') ;?>" >
                        <script type="dojo/connect" event="onChange" args="evt">
                          saveUserParameter("showDoneSubTask_Global",((this.checked)?"1":"0"));
                          if (checkFormChangeInProgress()) {return false;}
                          refreshAllSubTaskList();
                        </script>
                      </div>
                    </div>
                    <div style="float:left">
                      <label for="showClosedSubTaskAll"  class="<?php echo((isNewGui())?'dijitTitlePaneTitle;':'');?>" style="border:0;font-weight:normal !important;<?php echo((isNewGui())?'padding-top:13px;':'text-shadow:unset;');?>;height:<?php echo ((isNewGui())?'20':'10');?>px;width:<?php echo((isNewGui())?'50':'150');?>px"><?php echo i18n('labelShowIdle'.((isNewGui())?'Short':''));?>&nbsp;</label>
                      <div class="<?php echo ((isNewGui())?"whiteCheck":"");?>" id="showClosedSubTaskAll" style="<?php echo ((isNewGui())?'margin-top:14px':'');?>" 
                      dojoType="dijit.form.CheckBox" type="checkbox" <?php echo (($showClosedSubTask)?'checked':'');?> title="<?php echo i18n('labelShowIdle') ;?>" >
                        <script type="dojo/connect" event="onChange" args="evt">
                          saveUserParameter("showClosedSubTask_Global",((this.checked)?"1":"0"));
                          if(dijit.byId('showDoneSubTaskAll').readOnly==false && this.checked){
                          dijit.byId('showDoneSubTaskAll').set('readOnly',true);
                          dijit.byId('showDoneSubTaskAll').set('checked',true);
                          saveUserParameter("showDoneSubTask_Global",1);
                          }else{ 
                           dijit.byId('showDoneSubTaskAll').set('readOnly',false);
                          //dijit.byId('showDoneSubTaskAll').set('checked',false);
                          }
                          if (checkFormChangeInProgress()) {return false;}
                          refreshAllSubTaskList();
                        </script>
                      </div>
                    </div>
                  </td>
                </tr></table>
              </div>
               <?php if(isNewGui()){?>             
              <div style="float:left;padding-left:25px;">
                <table><tr>
                  <td>
                    <button id="refreshAllSubTaskButton" dojoType="dijit.form.Button" showlabel="false" style="position:absolute; right:10px; top:5px;"
                      title="<?php echo i18n('buttonRefreshList');?>"
                      iconClass="dijitButtonIcon dijitButtonIconRefresh" class="detailButton">
                      <script type="dojo/method" event="onClick" args="evt">
	                     refreshAllSubTaskList();
                      </script>
                    </button> 
                  </td>
                </tr></table>
              </div>
              <?php } ?>
              
         <div>
          <table style="margin-left:15px;">
            <div style="display:flex;">
              <td nowrap="nowrap" style="text-align: right;padding-right:15px;min-width:60px;"><?php echo i18n("sortedBy");?></td>
              <td>
              <select dojoType="dijit.form.FilteringSelect" class="input roundedLeft" style="width:175px;margin-right:15px;"
                <?php echo autoOpenFilteringSelect ();?> name="toDoListOrderBy" id="toDoListOrderBy"
                value="<?php if(sessionValueExists('toDoListOrderBy')){
                               $orderBy =  getSessionValue('toDoListOrderBy');
                               echo $orderBy;
                             } else {
                               echo 0;
                             }?>">
                  <script type="dojo/method" event="onChange" >
                    saveDataToSession("toDoListOrderBy",dijit.byId('toDoListOrderBy').get('value'),true);
                    refreshAllSubTaskList();
                  </script>
                  <option <?php if($orderBy=="")echo "selected";?> value=""></option>                 
                  <option <?php if($orderBy=="name")echo "selected";?> value="name"><?php echo i18n("colName");?></option>
                  <option <?php if($orderBy=="idPriority")echo "selected";?> value="idPriority"><?php echo i18n("colIdPriority");?></option>
                  <option <?php if($orderBy=="idResource")echo "selected";?> value="idResource"><?php echo i18n("colIdResource");?></option>
                  <option <?php if($orderBy=="status")echo "selected";?> value="status"><?php echo i18n("colIdStatus");?></option>
                  <option <?php if($orderBy=="dueDate")echo "selected";?> value="dueDate"><?php echo i18n("colDueDate");?></option>
              </select> 
              </td>   
            </div>
          </table>
         </div>
              
              
            </div>
          </td>
         </tr>         
        </table>
        </div>  
      </td>
    </tr>
  </table>
  </form>
  </div>
</div>